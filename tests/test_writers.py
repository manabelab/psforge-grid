"""Round-trip tests for IWriter implementations.

Tests the write → parse cycle for each format to verify data integrity.
For each format: parse fixture → write to temp → parse temp → compare.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from psforge_grid.io.factories import WriterFactory
from psforge_grid.io.protocols import IWriter
from psforge_grid.models.system import System

FIXTURES = Path(__file__).parent / "fixtures"


# =============================================================================
# Helper: compare two System objects
# =============================================================================


def assert_systems_approx_equal(
    s1: System,
    s2: System,
    *,
    atol: float = 1e-4,
) -> None:
    """Assert two System objects are approximately equal.

    Compares component counts, then field values with tolerance.
    """
    assert s1.num_buses == s2.num_buses, f"Bus count mismatch: {s1.num_buses} vs {s2.num_buses}"
    assert s1.num_branches == s2.num_branches, (
        f"Branch count mismatch: {s1.num_branches} vs {s2.num_branches}"
    )
    assert s1.num_generators == s2.num_generators, (
        f"Generator count mismatch: {s1.num_generators} vs {s2.num_generators}"
    )
    assert s1.num_loads == s2.num_loads, f"Load count mismatch: {s1.num_loads} vs {s2.num_loads}"
    assert abs(s1.base_mva - s2.base_mva) < atol, (
        f"base_mva mismatch: {s1.base_mva} vs {s2.base_mva}"
    )

    # Sort buses by unified id for comparison. Same-format round-trips must
    # regenerate identical ids (deterministic generation), so id equality is
    # itself part of the contract under test.
    buses1 = sorted(s1.buses, key=lambda b: b.id)
    buses2 = sorted(s2.buses, key=lambda b: b.id)
    for b1, b2 in zip(buses1, buses2, strict=True):
        assert b1.id == b2.id
        assert b1.number == b2.number, f"Bus {b1.id} number: {b1.number} vs {b2.number}"
        assert b1.bus_type == b2.bus_type, f"Bus {b1.id} type: {b1.bus_type} vs {b2.bus_type}"
        assert abs(b1.v_magnitude - b2.v_magnitude) < atol, (
            f"Bus {b1.id} v_magnitude: {b1.v_magnitude} vs {b2.v_magnitude}"
        )
        assert abs(b1.v_angle - b2.v_angle) < atol, (
            f"Bus {b1.id} v_angle: {b1.v_angle} vs {b2.v_angle}"
        )
        assert abs(b1.base_kv - b2.base_kv) < 0.5, (
            f"Bus {b1.id} base_kv: {b1.base_kv} vs {b2.base_kv}"
        )

    # Sort branches by unified id for comparison
    branches1 = sorted(s1.branches, key=lambda br: br.id)
    branches2 = sorted(s2.branches, key=lambda br: br.id)
    for br1, br2 in zip(branches1, branches2, strict=True):
        assert br1.id == br2.id
        assert br1.from_bus_id == br2.from_bus_id
        assert br1.to_bus_id == br2.to_bus_id
        assert abs(br1.r_pu - br2.r_pu) < atol, f"Branch {br1.id} r_pu: {br1.r_pu} vs {br2.r_pu}"
        assert abs(br1.x_pu - br2.x_pu) < atol, f"Branch {br1.id} x_pu: {br1.x_pu} vs {br2.x_pu}"
        assert abs(br1.b_pu - br2.b_pu) < atol, f"Branch {br1.id} b_pu: {br1.b_pu} vs {br2.b_pu}"
        assert abs(br1.tap_ratio - br2.tap_ratio) < atol
        assert abs(br1.shift_angle - br2.shift_angle) < atol

    # Sort generators by unified id for comparison
    gens1 = sorted(s1.generators, key=lambda g: g.id)
    gens2 = sorted(s2.generators, key=lambda g: g.id)
    for g1, g2 in zip(gens1, gens2, strict=True):
        assert g1.id == g2.id
        assert g1.bus_id == g2.bus_id
        assert abs(g1.p_gen - g2.p_gen) < atol, f"Gen {g1.id} p_gen: {g1.p_gen} vs {g2.p_gen}"
        assert abs(g1.v_setpoint - g2.v_setpoint) < atol

    # Sort loads by unified id
    loads1 = sorted(s1.loads, key=lambda ld: ld.id)
    loads2 = sorted(s2.loads, key=lambda ld: ld.id)
    for l1, l2 in zip(loads1, loads2, strict=True):
        assert l1.id == l2.id
        assert l1.bus_id == l2.bus_id
        assert abs(l1.p_load - l2.p_load) < atol, f"Load {l1.id} p_load: {l1.p_load} vs {l2.p_load}"
        assert abs(l1.q_load - l2.q_load) < atol


# =============================================================================
# WriterFactory tests
# =============================================================================


class TestWriterFactory:
    """Tests for WriterFactory."""

    def test_create_raw(self) -> None:
        writer = WriterFactory.create("raw")
        assert isinstance(writer, IWriter)
        assert writer.format_name == "PSS/E RAW"

    def test_create_matpower(self) -> None:
        writer = WriterFactory.create("matpower")
        assert isinstance(writer, IWriter)
        assert writer.format_name == "MATPOWER"

    def test_create_pop(self) -> None:
        writer = WriterFactory.create("pop")
        assert isinstance(writer, IWriter)
        assert writer.format_name == "CPAT Pop"

    def test_create_dyna(self) -> None:
        writer = WriterFactory.create("dyna")
        assert isinstance(writer, IWriter)
        assert writer.format_name == "CPAT Dyna"

    def test_create_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown format"):
            WriterFactory.create("unknown")

    def test_from_extension(self) -> None:
        writer = WriterFactory.from_extension(".raw")
        assert writer.format_name == "PSS/E RAW"

    def test_from_path(self) -> None:
        writer = WriterFactory.from_path("output.m")
        assert writer.format_name == "MATPOWER"

    def test_available_formats(self) -> None:
        formats = WriterFactory.available_formats()
        assert "raw" in formats
        assert "matpower" in formats
        assert "pop" in formats
        assert "dyna" in formats
        assert "dss" in formats

    def test_supported_extensions(self) -> None:
        exts = WriterFactory.supported_extensions()
        assert "raw" in exts
        assert "m" in exts
        assert "pop" in exts
        assert "dyna" in exts
        assert "dss" in exts


# =============================================================================
# IWriter interface tests
# =============================================================================


class TestIWriterInterface:
    """Tests that all writers implement IWriter correctly."""

    @pytest.mark.parametrize("fmt", ["raw", "matpower", "pop", "dyna", "dss"])
    def test_writer_has_required_properties(self, fmt: str) -> None:
        writer = WriterFactory.create(fmt)
        assert isinstance(writer.supported_extensions, list)
        assert len(writer.supported_extensions) > 0
        assert isinstance(writer.format_name, str)
        assert len(writer.format_name) > 0


# =============================================================================
# Round-trip tests: RAW format
# =============================================================================


class TestRawWriterRoundtrip:
    """Round-trip tests for RawWriter: parse → write → parse → compare."""

    def test_ieee14_roundtrip(self, tmp_path: Path) -> None:
        system1 = System.from_raw(FIXTURES / "ieee14.raw")
        output = tmp_path / "ieee14_out.raw"
        system1.to_raw(output)
        system2 = System.from_raw(output)
        assert_systems_approx_equal(system1, system2)

    def test_ieee9_roundtrip(self, tmp_path: Path) -> None:
        system1 = System.from_raw(FIXTURES / "ieee9.raw")
        output = tmp_path / "ieee9_out.raw"
        system1.to_raw(output)
        system2 = System.from_raw(output)
        assert_systems_approx_equal(system1, system2)

    def test_facade_to_file(self, tmp_path: Path) -> None:
        """Test System.to_file() auto-detection for .raw."""
        system1 = System.from_raw(FIXTURES / "ieee14.raw")
        output = tmp_path / "ieee14_auto.raw"
        system1.to_file(output)
        system2 = System.from_raw(output)
        assert_systems_approx_equal(system1, system2)


# =============================================================================
# Round-trip tests: MATPOWER format
# =============================================================================


class TestMatpowerWriterRoundtrip:
    """Round-trip tests for MatpowerWriter."""

    def test_case14_roundtrip(self, tmp_path: Path) -> None:
        system1 = System.from_matpower(FIXTURES / "pglib_opf_case14_ieee.m")
        output = tmp_path / "case14_out.m"
        system1.to_matpower(output)
        system2 = System.from_matpower(output)
        assert_systems_approx_equal(system1, system2)

    def test_case5_roundtrip(self, tmp_path: Path) -> None:
        system1 = System.from_matpower(FIXTURES / "pglib_opf_case5_pjm.m")
        output = tmp_path / "case5_out.m"
        system1.to_matpower(output)
        system2 = System.from_matpower(output)
        assert_systems_approx_equal(system1, system2)

    def test_generator_costs_preserved(self, tmp_path: Path) -> None:
        """Verify generator cost data survives the round trip."""
        system1 = System.from_matpower(FIXTURES / "pglib_opf_case14_ieee.m")
        if not system1.generator_costs:
            pytest.skip("No generator costs in fixture")
        output = tmp_path / "case14_costs.m"
        system1.to_matpower(output)
        system2 = System.from_matpower(output)
        assert len(system2.generator_costs) == len(system1.generator_costs)
        for gc1, gc2 in zip(system1.generator_costs, system2.generator_costs, strict=True):
            assert gc1.model == gc2.model
            assert abs(gc1.startup - gc2.startup) < 1e-4
            assert len(gc1.coefficients) == len(gc2.coefficients)

    def test_facade_to_file(self, tmp_path: Path) -> None:
        """Test System.to_file() auto-detection for .m."""
        system1 = System.from_matpower(FIXTURES / "pglib_opf_case14_ieee.m")
        output = tmp_path / "case14_auto.m"
        system1.to_file(output)
        system2 = System.from_matpower(output)
        assert_systems_approx_equal(system1, system2)


# =============================================================================
# Round-trip tests: Pop format
# =============================================================================


class TestPopWriterRoundtrip:
    """Round-trip tests for PopWriter."""

    def test_west10_roundtrip(self, tmp_path: Path) -> None:
        system1 = System.from_pop(FIXTURES / "WEST10peak.pop")
        output = tmp_path / "west10_out.pop"
        system1.to_pop(output)
        system2 = System.from_pop(output)
        assert_systems_approx_equal(system1, system2)

    def test_facade_to_file(self, tmp_path: Path) -> None:
        """Test System.to_file() auto-detection for .pop."""
        system1 = System.from_pop(FIXTURES / "WEST10peak.pop")
        output = tmp_path / "west10_auto.pop"
        system1.to_file(output)
        system2 = System.from_pop(output)
        assert_systems_approx_equal(system1, system2)


# =============================================================================
# Round-trip tests: Dyna format
# =============================================================================


class TestDynaWriterRoundtrip:
    """Round-trip tests for DynaWriter."""

    def test_cpat_model11_roundtrip(self, tmp_path: Path) -> None:
        system1 = System.from_dyna(FIXTURES / "cpat_model11.dyna")
        output = tmp_path / "cpat_model11_out.dyna"
        system1.to_dyna(output)
        system2 = System.from_dyna(output)
        assert_systems_approx_equal(system1, system2)

    def test_facade_to_file(self, tmp_path: Path) -> None:
        """Test System.to_file() auto-detection for .dyna."""
        system1 = System.from_dyna(FIXTURES / "cpat_model11.dyna")
        output = tmp_path / "cpat_model11_auto.dyna"
        system1.to_file(output)
        system2 = System.from_dyna(output)
        assert_systems_approx_equal(system1, system2)


# =============================================================================
# Cross-format tests
# =============================================================================


def assert_systems_core_equal(
    s1: System,
    s2: System,
    *,
    atol: float = 1e-4,
    check_angles: bool = True,
    check_bus_type: bool = True,
    check_base_kv: bool = True,
) -> None:
    """Assert core electrical data is preserved across format conversion.

    More lenient than assert_systems_approx_equal:
    - Load count may differ (formats aggregate/filter differently)
    - Total load P/Q per bus is compared instead of individual loads
    - Voltage angles can be skipped (Pop/Dyna don't preserve them)
    - Bus type can be skipped (Pop/Dyna reconstruct from gen data)
    - Base kV can be skipped (Dyna doesn't store it)
    """
    # Component counts (loads excluded — formats handle differently)
    assert s1.num_buses == s2.num_buses, f"Bus count: {s1.num_buses} vs {s2.num_buses}"
    assert s1.num_branches == s2.num_branches, (
        f"Branch count: {s1.num_branches} vs {s2.num_branches}"
    )
    assert s1.num_generators == s2.num_generators, (
        f"Generator count: {s1.num_generators} vs {s2.num_generators}"
    )
    assert abs(s1.base_mva - s2.base_mva) < atol

    # Bus data. All formats in the cross-format matrix are bus-number based,
    # so the deterministic ids ("B{number}") must agree across formats too.
    buses1 = sorted(s1.buses, key=lambda b: b.id)
    buses2 = sorted(s2.buses, key=lambda b: b.id)
    for b1, b2 in zip(buses1, buses2, strict=True):
        assert b1.id == b2.id
        assert b1.number == b2.number
        if check_bus_type:
            assert b1.bus_type == b2.bus_type, f"Bus {b1.id} type: {b1.bus_type} vs {b2.bus_type}"
        assert abs(b1.v_magnitude - b2.v_magnitude) < atol, (
            f"Bus {b1.id} Vm: {b1.v_magnitude} vs {b2.v_magnitude}"
        )
        if check_angles:
            assert abs(b1.v_angle - b2.v_angle) < atol, (
                f"Bus {b1.id} Va: {b1.v_angle} vs {b2.v_angle}"
            )
        if check_base_kv:
            assert abs(b1.base_kv - b2.base_kv) < 0.5, (
                f"Bus {b1.id} base_kv: {b1.base_kv} vs {b2.base_kv}"
            )

    # Branch data. Circuit identifiers travel differently between formats,
    # so branches are matched by terminals plus impedance order, not by id.
    def branch_key(br: object) -> tuple[str, str, float]:
        return (br.from_bus_id, br.to_bus_id, br.x_pu)  # type: ignore[attr-defined]

    branches1 = sorted(s1.branches, key=branch_key)
    branches2 = sorted(s2.branches, key=branch_key)
    for br1, br2 in zip(branches1, branches2, strict=True):
        assert br1.from_bus_id == br2.from_bus_id
        assert br1.to_bus_id == br2.to_bus_id
        assert abs(br1.r_pu - br2.r_pu) < atol, f"Branch {br1.id} r: {br1.r_pu} vs {br2.r_pu}"
        assert abs(br1.x_pu - br2.x_pu) < atol, f"Branch {br1.id} x: {br1.x_pu} vs {br2.x_pu}"
        assert abs(br1.tap_ratio - br2.tap_ratio) < atol
        assert abs(br1.shift_angle - br2.shift_angle) < atol

    # Generator data. Machine identifiers travel differently between
    # formats, so generators are matched by bus plus output order.
    gens1 = sorted(s1.generators, key=lambda g: (g.bus_id, g.p_gen, g.v_setpoint))
    gens2 = sorted(s2.generators, key=lambda g: (g.bus_id, g.p_gen, g.v_setpoint))
    for g1, g2 in zip(gens1, gens2, strict=True):
        assert g1.bus_id == g2.bus_id
        assert abs(g1.p_gen - g2.p_gen) < atol, f"Gen bus {g1.bus_id} Pg: {g1.p_gen} vs {g2.p_gen}"
        assert abs(g1.v_setpoint - g2.v_setpoint) < atol

    # Total load P/Q per bus (instead of individual Load objects)
    def _total_load_by_bus(system: System) -> dict[str, tuple[float, float]]:
        result: dict[str, tuple[float, float]] = {}
        for load in system.loads:
            p, q = result.get(load.bus_id, (0.0, 0.0))
            result[load.bus_id] = (p + load.p_load, q + load.q_load)
        return result

    loads1 = _total_load_by_bus(s1)
    loads2 = _total_load_by_bus(s2)
    all_load_buses = set(loads1.keys()) | set(loads2.keys())
    for bus_id in all_load_buses:
        p1, q1 = loads1.get(bus_id, (0.0, 0.0))
        p2, q2 = loads2.get(bus_id, (0.0, 0.0))
        assert abs(p1 - p2) < atol, f"Bus {bus_id} total Pload: {p1} vs {p2}"
        assert abs(q1 - q2) < atol, f"Bus {bus_id} total Qload: {q1} vs {q2}"


# =============================================================================
# Cross-format conversion tests
# =============================================================================

# Format capability flags
_ANGLE_PRESERVING = {"raw", "matpower"}  # Pop/Dyna don't store voltage angles
_BUS_TYPE_PRESERVING = {"raw", "matpower"}  # Pop/Dyna reconstruct from gen data
_BASE_KV_PRESERVING = {"raw", "matpower", "pop"}  # Dyna doesn't store base_kv

# Source fixtures for cross-format tests
_CROSS_FORMAT_SOURCES = [
    ("raw", FIXTURES / "ieee14.raw"),
    ("matpower", FIXTURES / "pglib_opf_case14_ieee.m"),
    ("pop", FIXTURES / "WEST10peak.pop"),
    ("dyna", FIXTURES / "cpat_model11.dyna"),
]

# Target formats to write
_TARGET_FORMATS = ["raw", "matpower", "pop", "dyna"]

# Extension mapping
_FORMAT_EXT = {"raw": ".raw", "matpower": ".m", "pop": ".pop", "dyna": ".dyna"}


def _cross_format_id(source_fmt: str, target_fmt: str) -> str:
    return f"{source_fmt}_to_{target_fmt}"


def _make_cross_params() -> list[tuple[str, Path, str]]:
    """Generate (source_fmt, fixture_path, target_fmt) for all valid pairs."""
    params = []
    for src_fmt, fixture in _CROSS_FORMAT_SOURCES:
        for tgt_fmt in _TARGET_FORMATS:
            if src_fmt != tgt_fmt:
                params.append(
                    pytest.param(
                        src_fmt,
                        fixture,
                        tgt_fmt,
                        id=_cross_format_id(src_fmt, tgt_fmt),
                    )
                )
    return params


class TestCrossFormat:
    """Test that core data is preserved when converting between formats.

    For each (source, target) pair:
    1. Parse source fixture
    2. Write to target format
    3. Parse the written file
    4. Compare core electrical data

    Note:
        - Pop/Dyna don't preserve voltage angles → check_angles=False
        - Load counts may differ → total load per bus is compared
        - Charging susceptance (b_pu) may differ between formats
    """

    @pytest.mark.parametrize(
        ("source_fmt", "fixture", "target_fmt"),
        _make_cross_params(),
    )
    def test_cross_format_conversion(
        self,
        tmp_path: Path,
        source_fmt: str,
        fixture: Path,
        target_fmt: str,
    ) -> None:
        """Parse source → write target → parse target → compare core data."""
        system1 = System.from_file(fixture)

        ext = _FORMAT_EXT[target_fmt]
        output = tmp_path / f"cross_{source_fmt}_to_{target_fmt}{ext}"

        system1.to_file(output)
        system2 = System.from_file(output)

        # Check only properties that BOTH source and target formats preserve
        check_angles = source_fmt in _ANGLE_PRESERVING and target_fmt in _ANGLE_PRESERVING
        check_bus_type = source_fmt in _BUS_TYPE_PRESERVING and target_fmt in _BUS_TYPE_PRESERVING
        check_base_kv = source_fmt in _BASE_KV_PRESERVING and target_fmt in _BASE_KV_PRESERVING

        assert_systems_core_equal(
            system1,
            system2,
            check_angles=check_angles,
            check_bus_type=check_bus_type,
            check_base_kv=check_base_kv,
        )

    def test_chain_raw_matpower_pop_dyna(self, tmp_path: Path) -> None:
        """Chain conversion: RAW → MATPOWER → Pop → Dyna → RAW.

        Verify data survives multiple format conversions.
        """
        # RAW → MATPOWER
        s1 = System.from_raw(FIXTURES / "ieee14.raw")
        p1 = tmp_path / "step1.m"
        s1.to_matpower(p1)
        s2 = System.from_matpower(p1)

        # MATPOWER → Pop
        p2 = tmp_path / "step2.pop"
        s2.to_pop(p2)
        s3 = System.from_pop(p2)

        # Pop → Dyna
        p3 = tmp_path / "step3.dyna"
        s3.to_dyna(p3)
        s4 = System.from_dyna(p3)

        # Dyna → RAW
        p4 = tmp_path / "step4.raw"
        s4.to_raw(p4)
        s5 = System.from_raw(p4)

        # Compare first and last: core data should survive the full chain
        assert s5.num_buses == s1.num_buses
        assert s5.num_branches == s1.num_branches
        assert s5.num_generators == s1.num_generators

        # Bus voltage magnitudes should be preserved (matched by unified id,
        # which survives the chain because every step is bus-number based)
        buses1 = {b.id: b for b in s1.buses}
        buses5 = {b.id: b for b in s5.buses}
        assert set(buses1) == set(buses5)
        for bus_id in buses1:
            assert abs(buses1[bus_id].v_magnitude - buses5[bus_id].v_magnitude) < 1e-4, (
                f"Bus {bus_id} Vm: {buses1[bus_id].v_magnitude} vs {buses5[bus_id].v_magnitude}"
            )

        # Branch impedances should be preserved
        def _branch_key(br: object) -> tuple[str, str, float]:
            return (br.from_bus_id, br.to_bus_id, br.x_pu)  # type: ignore[attr-defined]

        br1 = sorted(s1.branches, key=_branch_key)
        br5 = sorted(s5.branches, key=_branch_key)
        for b1, b5 in zip(br1, br5, strict=True):
            assert abs(b1.r_pu - b5.r_pu) < 1e-4
            assert abs(b1.x_pu - b5.x_pu) < 1e-4

        # Total system load should be preserved
        total_p1 = sum(ld.p_load for ld in s1.loads)
        total_p5 = sum(ld.p_load for ld in s5.loads)
        assert abs(total_p1 - total_p5) < 1e-3, f"Total Pload: {total_p1} vs {total_p5}"

        total_q1 = sum(ld.q_load for ld in s1.loads)
        total_q5 = sum(ld.q_load for ld in s5.loads)
        assert abs(total_q1 - total_q5) < 1e-3, f"Total Qload: {total_q1} vs {total_q5}"
