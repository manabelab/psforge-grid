"""Tests for DSSWriter (System → .dss export).

Tests verify that:
1. DSSWriter generates valid OpenDSS scripts that can be compiled
2. Round-trip (System → .dss → DSSParser → System) preserves data
3. Cross-format conversion works (RAW/MATPOWER/Pop → .dss)
"""

from __future__ import annotations

import math
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

FIXTURES = Path(__file__).parent / "fixtures"


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

    def _make_simple_system(self) -> System:
        """Create a simple 3-bus system for testing."""
        return System(
            buses=[
                Bus(bus_id=1, bus_type=3, base_kv=230.0, v_magnitude=1.0, name="Swing"),
                Bus(bus_id=2, bus_type=2, base_kv=230.0, v_magnitude=1.0, name="Gen2"),
                Bus(bus_id=3, bus_type=1, base_kv=230.0, v_magnitude=1.0, name="Load3"),
            ],
            branches=[
                Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1, b_pu=0.02),
                Branch(from_bus=2, to_bus=3, r_pu=0.02, x_pu=0.2, b_pu=0.04),
            ],
            generators=[
                Generator(bus_id=1, p_gen=1.0, q_gen=0.5, v_setpoint=1.0),
                Generator(bus_id=2, p_gen=0.5, q_gen=0.2, v_setpoint=1.0),
            ],
            loads=[
                Load(bus_id=3, p_load=1.5, q_load=0.7),
            ],
            shunts=[
                Shunt(bus_id=3, b_pu=0.1),
            ],
            base_mva=100.0,
            name="TestSystem",
            frequency_hz=60.0,
        )

    def test_generates_circuit(self):
        system = self._make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "New Circuit.TestSystem" in content
        assert "basekv=230.0000" in content
        assert "basefreq=60.0" in content

    def test_generates_lines(self):
        system = self._make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "New Line." in content
        assert "bus1=" in content
        assert "bus2=" in content

    def test_generates_generators(self):
        system = self._make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        # Swing bus generator is used as Circuit source, so only non-swing gen
        assert "New Generator." in content

    def test_generates_loads(self):
        system = self._make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "New Load." in content

    def test_generates_capacitors(self):
        system = self._make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "New Capacitor." in content

    def test_generates_voltage_bases(self):
        system = self._make_simple_system()
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "Set VoltageBases=" in content
        assert "CalcVoltageBases" in content

    def test_write_to_file(self):
        system = self._make_simple_system()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            write_dss(system, path)
            assert path.exists()
            content = path.read_text()
            assert "New Circuit." in content

    def test_system_facade_to_dss(self):
        system = self._make_simple_system()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            assert path.exists()

    def test_transformer_output(self):
        """Test transformer branch generates New Transformer element."""
        system = System(
            buses=[
                Bus(bus_id=1, bus_type=3, base_kv=500.0, name="HV"),
                Bus(bus_id=2, bus_type=1, base_kv=220.0, name="LV"),
            ],
            branches=[
                Branch(
                    from_bus=1,
                    to_bus=2,
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
            generators=[Generator(bus_id=1, p_gen=1.0)],
            loads=[Load(bus_id=2, p_load=0.8)],
            base_mva=100.0,
            name="XfmrTest",
        )
        writer = DSSWriter()
        content = writer.to_string(system)
        assert "New Transformer." in content
        assert "delta wye" in content.lower() or "delta" in content.lower()
        assert "500" in content
        assert "220" in content

    def test_sanitize_names_with_spaces(self):
        """Test that bus/element names with spaces are sanitized."""
        system = System(
            buses=[
                Bus(bus_id=1, bus_type=3, base_kv=230.0, name="Bus 1"),
                Bus(bus_id=2, bus_type=1, base_kv=230.0, name="Bus 2"),
            ],
            branches=[Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1)],
            generators=[Generator(bus_id=1, p_gen=1.0)],
            loads=[Load(bus_id=2, p_load=0.5)],
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
        import subprocess
        import sys

        script = (
            "import opendssdirect as dss; "
            "dss.Basic.ClearAll(); "
            f"r = dss.run_command('Compile \"{dss_path.resolve()}\"'); "
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
                Bus(bus_id=1, bus_type=3, base_kv=230.0, name="Swing"),
                Bus(bus_id=2, bus_type=1, base_kv=230.0, name="Load"),
            ],
            branches=[Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1, b_pu=0.02)],
            generators=[Generator(bus_id=1, p_gen=1.0)],
            loads=[Load(bus_id=2, p_load=0.5, q_load=0.2)],
            base_mva=100.0,
            name="Simple",
        )
        error = self._compile_system(system)
        assert error is None, f"OpenDSS compilation failed: {error}"

    def test_compile_ieee14(self):
        system = System.from_raw(FIXTURES / "ieee14.raw")
        error = self._compile_system(system)
        assert error is None, f"IEEE 14-bus compilation failed: {error}"

    def test_compile_case5(self):
        system = System.from_matpower(FIXTURES / "pglib_opf_case5_pjm.m")
        error = self._compile_system(system)
        assert error is None, f"case5_pjm compilation failed: {error}"

    def test_compile_case14(self):
        system = System.from_matpower(FIXTURES / "pglib_opf_case14_ieee.m")
        error = self._compile_system(system)
        assert error is None, f"case14_ieee compilation failed: {error}"

    @pytest.mark.skipif(
        not (FIXTURES / "WEST10peak.pop").exists(),
        reason="WEST10peak.pop not available",
    )
    def test_compile_west10(self):
        system = System.from_pop(FIXTURES / "WEST10peak.pop")
        error = self._compile_system(system)
        assert error is None, f"WEST10peak compilation failed: {error}"


# ============================================================================
# Round-trip tests (System → .dss → DSSParser → System)
# ============================================================================


class TestDSSRoundTrip:
    """Test round-trip: System → .dss → DSSParser → System.

    Uses subprocess isolation because opendssdirect.py segfaults
    on consecutive Compile calls within the same process.
    """

    @staticmethod
    def _round_trip_counts(dss_path: Path) -> dict[str, float]:
        """Parse .dss in subprocess and return element counts as JSON."""
        import json
        import subprocess
        import sys

        script = (
            "import json; "
            "from psforge_grid.models import System; "
            f's = System.from_dss("{dss_path.resolve()}"); '
            "print(json.dumps({"
            '"num_buses": len(s.buses), '
            '"num_branches": len(s.branches), '
            '"num_generators": len(s.generators), '
            '"num_loads": len(s.loads), '
            '"num_shunts": len(s.shunts), '
            '"frequency_hz": s.frequency_hz'
            "}))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Round-trip subprocess failed: {result.stderr}")
        data: dict[str, float] = json.loads(result.stdout.strip())
        return data

    def test_round_trip_preserves_load_count(self):
        system = System.from_raw(FIXTURES / "ieee14.raw")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            counts = self._round_trip_counts(path)
        assert counts["num_loads"] == system.num_loads()

    def test_round_trip_preserves_shunt_count(self):
        system = System.from_raw(FIXTURES / "ieee14.raw")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            counts = self._round_trip_counts(path)
        assert counts["num_shunts"] == system.num_shunts()

    def test_round_trip_preserves_branch_count(self):
        """Branch count should be preserved (lines + transformers)."""
        system = System.from_raw(FIXTURES / "ieee14.raw")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            counts = self._round_trip_counts(path)
        assert counts["num_branches"] == system.num_branches()

    def test_round_trip_preserves_bus_count(self):
        """Bus count should be preserved (internal buses filtered out)."""
        system = System.from_raw(FIXTURES / "ieee14.raw")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            counts = self._round_trip_counts(path)
        assert counts["num_buses"] == system.num_buses()

    def test_round_trip_preserves_generator_count(self):
        """Generator count should be preserved (including swing bus generator)."""
        system = System.from_raw(FIXTURES / "ieee14.raw")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            counts = self._round_trip_counts(path)
        assert counts["num_generators"] == system.num_generators()

    def test_round_trip_swing_bus_type(self):
        """Swing bus should be recovered as bus_type=3."""
        system = System.from_raw(FIXTURES / "ieee14.raw")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            # Extended subprocess to check bus types
            counts = self._round_trip_detail(path)
        assert counts["swing_bus_count"] == 1
        assert counts["pv_bus_count"] >= 1

    @staticmethod
    def _round_trip_detail(dss_path: Path) -> dict[str, float]:
        """Parse .dss in subprocess and return detailed info as JSON."""
        import json
        import subprocess
        import sys

        script = (
            "import json; "
            "from psforge_grid.models import System; "
            f's = System.from_dss("{dss_path.resolve()}"); '
            "print(json.dumps({"
            '"swing_bus_count": sum(1 for b in s.buses if b.bus_type == 3), '
            '"pv_bus_count": sum(1 for b in s.buses if b.bus_type == 2), '
            '"pq_bus_count": sum(1 for b in s.buses if b.bus_type == 1)'
            "}))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Round-trip subprocess failed: {result.stderr}")
        data: dict[str, float] = json.loads(result.stdout.strip())
        return data

    def test_round_trip_frequency(self):
        system = System(
            buses=[Bus(bus_id=1, bus_type=3, base_kv=230.0)],
            branches=[],
            generators=[Generator(bus_id=1, p_gen=1.0)],
            loads=[],
            base_mva=100.0,
            name="FreqTest",
            frequency_hz=50.0,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.dss"
            system.to_dss(path)
            counts = self._round_trip_counts(path)
        assert counts["frequency_hz"] == pytest.approx(50.0)
