"""Tests for DSSWriter (System → .dss export) and DSSParser id generation.

Tests verify that:
1. DSSWriter generates valid OpenDSS scripts that can be compiled
2. Round-trip (System → .dss → DSSParser → System) preserves data
3. DSSParser generates deterministic unified ids and sequential order values

Note:
    Cross-format tests (RAW/MATPOWER/Pop → .dss) were removed while those
    parsers are being migrated to the unified identity scheme in parallel;
    they should be restored once the other parsers are migrated. The systems
    under test here are constructed directly with the new schema.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from psforge_grid.io.dss_writer import DSSWriter, write_dss
from psforge_grid.io.factories import WriterFactory
from psforge_grid.models import System
from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt


def _make_simple_system() -> System:
    """Create a simple 3-bus system for testing."""
    return System(
        buses=[
            Bus("B1", bus_type=3, base_kv=230.0, v_magnitude=1.0, name="Swing"),
            Bus("B2", bus_type=2, base_kv=230.0, v_magnitude=1.0, name="Gen2"),
            Bus("B3", bus_type=1, base_kv=230.0, v_magnitude=1.0, name="Load3"),
        ],
        branches=[
            Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, b_pu=0.02),
            Branch("BR2", "B2", "B3", r_pu=0.02, x_pu=0.2, b_pu=0.04),
        ],
        generators=[
            Generator("G1", bus_id="B1", p_gen=1.0, q_gen=0.5, v_setpoint=1.0),
            Generator("G2", bus_id="B2", p_gen=0.5, q_gen=0.2, v_setpoint=1.0),
        ],
        loads=[
            Load("LD1", bus_id="B3", p_load=1.5, q_load=0.7),
        ],
        shunts=[
            Shunt("SH1", bus_id="B3", b_pu=0.1),
        ],
        base_mva=100.0,
        name="TestSystem",
        frequency_hz=60.0,
    )


def _make_two_level_system() -> System:
    """Create a two-voltage-level system with transformer and parallel lines.

    Includes the structural features the DSS round-trip must preserve:
    parallel circuits (circuit_id disambiguation), a transformer, a
    capacitor and a reactor shunt.
    """
    return System(
        buses=[
            Bus("B1", bus_type=3, base_kv=230.0, v_magnitude=1.0, name="SwingHV"),
            Bus("B2", bus_type=2, base_kv=230.0, name="GenHV"),
            Bus("B3", bus_type=1, base_kv=230.0, name="MidHV"),
            Bus("B4", bus_type=1, base_kv=115.0, name="LoadLV"),
        ],
        branches=[
            Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, b_pu=0.02, circuit_id="1"),
            Branch("BR2", "B1", "B2", r_pu=0.01, x_pu=0.1, b_pu=0.02, circuit_id="2"),
            Branch("BR3", "B2", "B3", r_pu=0.02, x_pu=0.2, b_pu=0.04),
            Branch(
                "BR4",
                "B3",
                "B4",
                r_pu=0.005,
                x_pu=0.08,
                tap_ratio=1.02,
                winding_connection="wye-wye",
                nomv_from=230.0,
                nomv_to=115.0,
                sbase_mva=150.0,
            ),
        ],
        generators=[
            Generator("G1", bus_id="B1", p_gen=1.2, v_setpoint=1.0),
            Generator("G2", bus_id="B2", p_gen=0.6, q_gen=0.1, v_setpoint=1.0),
        ],
        loads=[
            Load("LD1", bus_id="B3", p_load=0.9, q_load=0.3),
            Load("LD2", bus_id="B4", p_load=0.7, q_load=0.2),
        ],
        shunts=[
            Shunt("SH1", bus_id="B3", b_pu=0.1),
            Shunt("SH2", bus_id="B4", b_pu=-0.05),
        ],
        base_mva=100.0,
        name="TwoLevelTest",
        frequency_hz=60.0,
    )


# ============================================================================
# Factory and interface tests
# ============================================================================


class TestDSSWriterFactory:
    """Test DSSWriter factory integration."""

    def test_create_via_factory(self):
        writer = WriterFactory.create("dss")
        assert isinstance(writer, DSSWriter)

    def test_from_extension(self):
        writer = WriterFactory.from_extension("dss")
        assert isinstance(writer, DSSWriter)

    def test_from_path(self):
        writer = WriterFactory.from_path("output.dss")
        assert isinstance(writer, DSSWriter)

    def test_supported_extensions(self):
        writer = DSSWriter()
        assert "dss" in writer.supported_extensions

    def test_format_name(self):
        writer = DSSWriter()
        assert writer.format_name == "OpenDSS Script"

    def test_dss_in_available_formats(self):
        assert "dss" in WriterFactory.available_formats()


# ============================================================================
# DSSWriter output tests
# ============================================================================


class TestDSSWriterOutput:
    """Test DSSWriter generates valid .dss scripts."""

    def test_generates_circuit(self):
        system = _make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "New Circuit.TestSystem" in content
        assert "basekv=230.0000" in content
        assert "basefreq=60.0" in content

    def test_generates_lines(self):
        system = _make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "New Line." in content
        assert "bus1=" in content
        assert "bus2=" in content

    def test_bus_names_come_from_name_not_id(self):
        """OpenDSS bus names are generated from Bus.name when available."""
        system = _make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "bus1=Swing" in content
        assert "bus2=Gen2" in content

    def test_unnamed_bus_falls_back_to_id(self):
        """A bus without a name uses its unified id as the OpenDSS name."""
        system = System(
            buses=[
                Bus("B1", bus_type=3, base_kv=230.0),
                Bus("B2", bus_type=1, base_kv=230.0),
            ],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
            generators=[Generator("G1", bus_id="B1", p_gen=1.0)],
            loads=[Load("LD1", bus_id="B2", p_load=0.5)],
            base_mva=100.0,
            name="NoNames",
        )
        content = DSSWriter().to_string(system)
        assert "bus1=B1" in content
        assert "bus2=B2" in content

    def test_generates_generators(self):
        system = _make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        # Swing bus generator is used as Circuit source, so only non-swing gen
        assert "New Generator." in content

    def test_generates_loads(self):
        system = _make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "New Load." in content

    def test_generates_capacitors(self):
        system = _make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "New Capacitor." in content

    def test_generates_reactor_for_negative_susceptance(self):
        system = _make_two_level_system()
        content = DSSWriter().to_string(system)
        assert "New Reactor." in content
        # Reactor rating is the absolute value: |-0.05| * 100 MVA * 1000
        assert "kvar=5000.00" in content

    def test_parallel_branches_get_distinct_names(self):
        """Parallel circuits must not produce duplicate OpenDSS element names."""
        system = _make_two_level_system()
        content = DSSWriter().to_string(system)
        line_names = [
            token.split(".", 1)[1]
            for row in content.splitlines()
            for token in row.split()
            if token.startswith("Line.")
        ]
        assert len(line_names) == 3
        assert len(set(line_names)) == 3

    def test_generates_voltage_bases(self):
        system = _make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "Set VoltageBases=" in content
        assert "CalcVoltageBases" in content

    def test_write_to_file(self):
        system = _make_simple_system()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            write_dss(system, path)
            assert path.exists()
            content = path.read_text()
            assert "New Circuit." in content

    def test_system_facade_to_dss(self):
        system = _make_simple_system()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            assert path.exists()

    def test_transformer_output(self):
        """Test transformer branch generates New Transformer element."""
        system = System(
            buses=[
                Bus("B1", bus_type=3, base_kv=500.0, name="HV"),
                Bus("B2", bus_type=1, base_kv=220.0, name="LV"),
            ],
            branches=[
                Branch(
                    "BR1",
                    "B1",
                    "B2",
                    r_pu=0.001,
                    x_pu=0.1,
                    tap_ratio=1.05,
                    shift_angle=math.pi / 6,
                    winding_connection="delta-wye",
                    nomv_from=500.0,
                    nomv_to=220.0,
                    sbase_mva=200.0,
                ),
            ],
            generators=[Generator("G1", bus_id="B1", p_gen=1.0)],
            loads=[Load("LD1", bus_id="B2", p_load=0.8)],
            base_mva=100.0,
            name="XfmrTest",
        )
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "New Transformer." in content
        assert "delta wye" in content.lower() or "delta" in content.lower()
        assert "500" in content
        assert "220" in content
        # %loadloss sets both winding resistances (not %R which only sets one)
        assert "%loadloss=" in content
        assert "%R=" not in content

    def test_sanitize_names_with_spaces(self):
        """Test that bus/element names with spaces are sanitized."""
        system = System(
            buses=[
                Bus("B1", bus_type=3, base_kv=230.0, name="Bus 1"),
                Bus("B2", bus_type=1, base_kv=230.0, name="Bus 2"),
            ],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
            generators=[Generator("G1", bus_id="B1", p_gen=1.0)],
            loads=[Load("LD1", bus_id="B2", p_load=0.5)],
            base_mva=100.0,
            name="Test System",
        )
        writer = DSSWriter()
        content = writer.to_string(system)
        # No spaces in identifiers
        assert "Bus 1" not in content
        assert "Bus_1" in content or "Bus1" in content


# ============================================================================
# OpenDSS compilation tests (require opendssdirect.py)
# ============================================================================


class TestDSSCompilation:
    """Test that generated .dss scripts compile in OpenDSS.

    Uses subprocess isolation to avoid segfaults from consecutive
    OpenDSS Compile calls within the same process.
    """

    def _compile_dss_file(self, dss_path: Path) -> str | None:
        """Compile a .dss file in a subprocess. Returns error or None."""
        safe_path = str(dss_path.resolve()).replace("\\", "/")
        script = (
            "import opendssdirect as dss; "
            "dss.Basic.ClearAll(); "
            f"r = dss.run_command('Compile \"{safe_path}\"'); "
            "import sys; "
            "sys.exit(1 if r and 'error' in r.lower() else 0)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return result.stderr or result.stdout or "compilation failed"
        return None

    def _compile_system(self, system: System) -> str | None:
        """Write system to .dss and compile in OpenDSS subprocess."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            return self._compile_dss_file(path)

    def test_compile_simple_system(self):
        system = System(
            buses=[
                Bus("B1", bus_type=3, base_kv=230.0, name="Swing"),
                Bus("B2", bus_type=1, base_kv=230.0, name="Load"),
            ],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, b_pu=0.02)],
            generators=[Generator("G1", bus_id="B1", p_gen=1.0)],
            loads=[Load("LD1", bus_id="B2", p_load=0.5, q_load=0.2)],
            base_mva=100.0,
            name="Simple",
        )
        error = self._compile_system(system)
        assert error is None, f"OpenDSS compilation failed: {error}"

    def test_compile_two_level_system(self):
        """Transformer, parallel lines, capacitor and reactor all compile."""
        system = _make_two_level_system()
        error = self._compile_system(system)
        assert error is None, f"Two-level system compilation failed: {error}"


# ============================================================================
# Round-trip tests (System → .dss → DSSParser → System)
# ============================================================================


def _run_json_subprocess(script: str) -> dict[str, object]:
    """Run a Python script in a subprocess and parse its JSON stdout.

    Subprocess isolation is required because opendssdirect.py segfaults
    on consecutive Compile calls within the same process.
    """
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Subprocess failed: {result.stderr}")
    data: dict[str, object] = json.loads(result.stdout.strip())
    return data


def _parse_dss_summary(dss_path: Path) -> dict[str, object]:
    """Parse .dss in a subprocess and return ids, orders and counts."""
    # Use forward slashes for cross-platform compatibility (Windows \U = unicode escape)
    safe_path = str(dss_path.resolve()).replace("\\", "/")
    script = (
        "import json; "
        "from psforge_grid.models import System; "
        f's = System.from_dss("{safe_path}"); '
        "print(json.dumps({"
        '"num_buses": len(s.buses), '
        '"num_branches": len(s.branches), '
        '"num_generators": len(s.generators), '
        '"num_loads": len(s.loads), '
        '"num_shunts": len(s.shunts), '
        '"frequency_hz": s.frequency_hz, '
        '"bus_ids": [b.id for b in s.buses], '
        '"bus_names": [b.name for b in s.buses], '
        '"branch_names": [b.name for b in s.branches], '
        '"branch_ids": [b.id for b in s.branches], '
        '"generator_ids": [g.id for g in s.generators], '
        '"load_ids": [ld.id for ld in s.loads], '
        '"shunt_ids": [sh.id for sh in s.shunts], '
        '"bus_orders": [b.order for b in s.buses], '
        '"branch_orders": [b.order for b in s.branches], '
        '"generator_orders": [g.order for g in s.generators], '
        '"load_orders": [ld.order for ld in s.loads], '
        '"shunt_orders": [sh.order for sh in s.shunts], '
        '"bus_numbers": [b.number for b in s.buses], '
        '"branch_from_to": [[b.from_bus_id, b.to_bus_id] for b in s.branches], '
        '"gen_bus_ids": [g.bus_id for g in s.generators], '
        '"swing_bus_count": sum(1 for b in s.buses if b.bus_type == 3), '
        '"pv_bus_count": sum(1 for b in s.buses if b.bus_type == 2), '
        '"pq_bus_count": sum(1 for b in s.buses if b.bus_type == 1)'
        "}))"
    )
    return _run_json_subprocess(script)


@pytest.fixture(scope="module")
def round_trip_summary() -> dict[str, object]:
    """Write the two-level system to .dss and parse it back once."""
    system = _make_two_level_system()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.dss"
        system.to_dss(path)
        return _parse_dss_summary(path)


@pytest.fixture(scope="module")
def simple_summary() -> dict[str, object]:
    """Write the simple 3-bus system to .dss and parse it back once."""
    system = _make_simple_system()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.dss"
        system.to_dss(path)
        return _parse_dss_summary(path)


class TestDSSRoundTrip:
    """Test round-trip: System → .dss → DSSParser → System.

    Uses subprocess isolation because opendssdirect.py segfaults
    on consecutive Compile calls within the same process.
    """

    def test_round_trip_preserves_bus_count(self, round_trip_summary):
        """Bus count should be preserved (internal buses filtered out)."""
        assert round_trip_summary["num_buses"] == _make_two_level_system().num_buses

    def test_round_trip_preserves_branch_count(self, round_trip_summary):
        """Branch count should be preserved (lines + transformers)."""
        assert round_trip_summary["num_branches"] == _make_two_level_system().num_branches

    def test_round_trip_preserves_generator_count(self, round_trip_summary):
        """Generator count should be preserved (including swing bus generator)."""
        assert round_trip_summary["num_generators"] == _make_two_level_system().num_generators

    def test_round_trip_preserves_load_count(self, round_trip_summary):
        assert round_trip_summary["num_loads"] == _make_two_level_system().num_loads

    def test_round_trip_preserves_shunt_count(self, round_trip_summary):
        assert round_trip_summary["num_shunts"] == _make_two_level_system().num_shunts

    def test_round_trip_swing_bus_type(self, round_trip_summary):
        """Swing bus should be recovered as bus_type=3."""
        assert round_trip_summary["swing_bus_count"] == 1
        assert round_trip_summary["pv_bus_count"] >= 1

    def test_round_trip_frequency(self):
        system = System(
            buses=[Bus("B1", bus_type=3, base_kv=230.0)],
            branches=[],
            generators=[Generator("G1", bus_id="B1", p_gen=1.0)],
            loads=[],
            base_mva=100.0,
            name="FreqTest",
            frequency_hz=50.0,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            summary = _parse_dss_summary(path)
        assert summary["frequency_hz"] == pytest.approx(50.0)


# ============================================================================
# Unified identity tests (deterministic ids, order, number)
# ============================================================================


class TestDSSParserIdentity:
    """Test the unified identity scheme in DSSParser output.

    Ids are a type prefix plus the 1-based appearance order within the
    type: B{n}/BR{n}/G{n}/LD{n}/SH{n}. The original DSS names (which
    OpenDSS lowercases) are kept in the ``name`` field.
    """

    def test_parse_generates_expected_bus_ids(self, simple_summary):
        """Bus ids are B{n} in appearance order after internal-bus filtering."""
        assert simple_summary["bus_ids"] == ["B1", "B2", "B3"]

    def test_parse_keeps_dss_names_in_name_field(self, simple_summary):
        """Ids no longer embed names; the DSS name lives in ``name``."""
        assert simple_summary["bus_names"] == ["swing", "gen2", "load3"]
        assert simple_summary["branch_names"] == ["br1", "br2"]

    def test_parse_generates_expected_branch_ids(self, simple_summary):
        """Branch ids are BR{n}: Lines first, then Transformers."""
        assert simple_summary["branch_ids"] == ["BR1", "BR2"]

    def test_parse_generates_expected_generator_ids(self, simple_summary):
        """Vsource swing generator comes first (G1), then Generator elements."""
        assert simple_summary["generator_ids"] == ["G1", "G2"]

    def test_parse_generates_expected_load_and_shunt_ids(self, simple_summary):
        assert simple_summary["load_ids"] == ["LD1"]
        assert simple_summary["shunt_ids"] == ["SH1"]

    def test_parse_references_use_bus_ids(self, simple_summary):
        """Branch/generator references hold Bus.id strings."""
        assert simple_summary["branch_from_to"] == [
            ["B1", "B2"],
            ["B2", "B3"],
        ]
        assert simple_summary["gen_bus_ids"] == ["B1", "B2"]

    def test_parse_ids_stable_across_reparses(self):
        """Parsing the same file twice yields identical ids (determinism)."""
        system = _make_simple_system()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            first = _parse_dss_summary(path)
            second = _parse_dss_summary(path)
        for key in ("bus_ids", "branch_ids", "generator_ids", "load_ids", "shunt_ids"):
            assert first[key] == second[key]

    def test_parse_write_parse_regenerates_same_ids(self):
        """parse → write → parse regenerates identical ids (round-trip stable)."""
        system = _make_simple_system()
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = Path(tmpdir) / "first.dss"
            path2 = Path(tmpdir) / "second.dss"
            system.to_dss(path1)
            first = _parse_dss_summary(path1)
            # Re-write the parsed system in a subprocess (single Compile per
            # process; opendssdirect segfaults on consecutive Compile calls)
            safe1 = str(path1.resolve()).replace("\\", "/")
            safe2 = str(path2.resolve()).replace("\\", "/")
            script = (
                "from psforge_grid.models import System; "
                f's = System.from_dss("{safe1}"); '
                f's.to_dss("{safe2}")'
            )
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, f"re-write subprocess failed: {result.stderr}"
            second = _parse_dss_summary(path2)
        for key in ("bus_ids", "branch_ids", "generator_ids", "load_ids", "shunt_ids"):
            assert first[key] == second[key]

    def test_parse_assigns_sequential_order(self, simple_summary):
        """order runs 1.0, 2.0, ... per element type in appearance order."""
        assert simple_summary["bus_orders"] == [1.0, 2.0, 3.0]
        assert simple_summary["branch_orders"] == [1.0, 2.0]
        assert simple_summary["generator_orders"] == [1.0, 2.0]
        assert simple_summary["load_orders"] == [1.0]
        assert simple_summary["shunt_orders"] == [1.0]

    def test_parse_leaves_bus_number_none(self, simple_summary):
        """OpenDSS has no bus numbers; Bus.number must stay None."""
        assert simple_summary["bus_numbers"] == [None, None, None]

    def test_same_dss_name_yields_distinct_sequential_ids(self):
        """A Line and a Transformer sharing a DSS name get distinct BR{n} ids."""
        dss_text = "\n".join(
            [
                "Clear",
                "New Circuit.ColTest basekv=230.0 pu=1.0 phases=3 bus1=b1 "
                "basefreq=60.0 Mvasc3=1e10 Mvasc1=1e10",
                "New Line.T1 bus1=b1 bus2=b2 phases=3 r1=0.5 x1=5.0 length=1 units=none",
                "New Transformer.T1 phases=3 windings=2 buses=(b2, b3) "
                'conns="wye wye" kvs="230.0 115.0" kvas="100000 100000" XHL=8.0',
                "Set VoltageBases=[230.0, 115.0]",
                "CalcVoltageBases",
                "",
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "collision.dss"
            path.write_text(dss_text, encoding="utf-8")
            summary = _parse_dss_summary(path)
        # Lines are extracted before transformers; sequential ids stay unique
        # even though both elements are named "t1" (the name lives in `name`)
        assert summary["branch_ids"] == ["BR1", "BR2"]
        assert summary["branch_names"] == ["t1", "t1"]
        assert summary["branch_orders"] == [1.0, 2.0]
