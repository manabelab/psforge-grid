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
    assert s1.num_buses() == s2.num_buses(), (
        f"Bus count mismatch: {s1.num_buses()} vs {s2.num_buses()}"
    )
    assert s1.num_branches() == s2.num_branches(), (
        f"Branch count mismatch: {s1.num_branches()} vs {s2.num_branches()}"
    )
    assert s1.num_generators() == s2.num_generators(), (
        f"Generator count mismatch: {s1.num_generators()} vs {s2.num_generators()}"
    )
    assert s1.num_loads() == s2.num_loads(), (
        f"Load count mismatch: {s1.num_loads()} vs {s2.num_loads()}"
    )
    assert abs(s1.base_mva - s2.base_mva) < atol, (
        f"base_mva mismatch: {s1.base_mva} vs {s2.base_mva}"
    )

    # Sort buses by ID for comparison
    buses1 = sorted(s1.buses, key=lambda b: b.bus_id)
    buses2 = sorted(s2.buses, key=lambda b: b.bus_id)
    for b1, b2 in zip(buses1, buses2, strict=True):
        assert b1.bus_id == b2.bus_id
        assert b1.bus_type == b2.bus_type, f"Bus {b1.bus_id} type: {b1.bus_type} vs {b2.bus_type}"
        assert abs(b1.v_magnitude - b2.v_magnitude) < atol, (
            f"Bus {b1.bus_id} v_magnitude: {b1.v_magnitude} vs {b2.v_magnitude}"
        )
        assert abs(b1.v_angle - b2.v_angle) < atol, (
            f"Bus {b1.bus_id} v_angle: {b1.v_angle} vs {b2.v_angle}"
        )
        assert abs(b1.base_kv - b2.base_kv) < 0.5, (
            f"Bus {b1.bus_id} base_kv: {b1.base_kv} vs {b2.base_kv}"
        )

    # Sort branches by (from_bus, to_bus, circuit_id) for comparison
    def branch_key(br):
        return (br.from_bus, br.to_bus, br.circuit_id)

    branches1 = sorted(s1.branches, key=branch_key)
    branches2 = sorted(s2.branches, key=branch_key)
    for br1, br2 in zip(branches1, branches2, strict=True):
        assert br1.from_bus == br2.from_bus
        assert br1.to_bus == br2.to_bus
        assert abs(br1.r_pu - br2.r_pu) < atol, (
            f"Branch {br1.from_bus}-{br1.to_bus} r_pu: {br1.r_pu} vs {br2.r_pu}"
        )
        assert abs(br1.x_pu - br2.x_pu) < atol, (
            f"Branch {br1.from_bus}-{br1.to_bus} x_pu: {br1.x_pu} vs {br2.x_pu}"
        )
        assert abs(br1.b_pu - br2.b_pu) < atol, (
            f"Branch {br1.from_bus}-{br1.to_bus} b_pu: {br1.b_pu} vs {br2.b_pu}"
        )
        assert abs(br1.tap_ratio - br2.tap_ratio) < atol
        assert abs(br1.shift_angle - br2.shift_angle) < atol

    # Sort generators by (bus_id, gen_id) for comparison
    gens1 = sorted(s1.generators, key=lambda g: (g.bus_id, g.gen_id))
    gens2 = sorted(s2.generators, key=lambda g: (g.bus_id, g.gen_id))
    for g1, g2 in zip(gens1, gens2, strict=True):
        assert g1.bus_id == g2.bus_id
        assert abs(g1.p_gen - g2.p_gen) < atol, (
            f"Gen at bus {g1.bus_id} p_gen: {g1.p_gen} vs {g2.p_gen}"
        )
        assert abs(g1.v_setpoint - g2.v_setpoint) < atol

    # Sort loads by bus_id
    loads1 = sorted(s1.loads, key=lambda ld: (ld.bus_id, ld.load_id))
    loads2 = sorted(s2.loads, key=lambda ld: (ld.bus_id, ld.load_id))
    for l1, l2 in zip(loads1, loads2, strict=True):
        assert l1.bus_id == l2.bus_id
        assert abs(l1.p_load - l2.p_load) < atol, (
            f"Load at bus {l1.bus_id} p_load: {l1.p_load} vs {l2.p_load}"
        )
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

    def test_supported_extensions(self) -> None:
        exts = WriterFactory.supported_extensions()
        assert "raw" in exts
        assert "m" in exts
        assert "pop" in exts
        assert "dyna" in exts


# =============================================================================
# IWriter interface tests
# =============================================================================


class TestIWriterInterface:
    """Tests that all writers implement IWriter correctly."""

    @pytest.mark.parametrize("fmt", ["raw", "matpower", "pop", "dyna"])
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


class TestCrossFormat:
    """Test writing in one format and reading in another (where applicable)."""

    def test_raw_to_matpower_roundtrip(self, tmp_path: Path) -> None:
        """Parse RAW → write MATPOWER → parse MATPOWER → compare core data."""
        system1 = System.from_raw(FIXTURES / "ieee14.raw")
        output = tmp_path / "ieee14_from_raw.m"
        system1.to_matpower(output)
        system2 = System.from_matpower(output)

        # Basic structure should be preserved
        assert system2.num_buses() == system1.num_buses()
        assert system2.num_branches() == system1.num_branches()
        assert system2.num_generators() == system1.num_generators()
        # Load count may differ: MATPOWER embeds loads in bus matrix
        # so a bus with P=0 Q=0 won't create a Load object
