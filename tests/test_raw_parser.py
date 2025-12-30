"""Tests for PSS/E RAW file parser.

Tests the parsing functionality for PSS/E RAW format files.
"""

from pathlib import Path

import pytest

from psforge_grid.io.raw_parser import parse_raw
from psforge_grid.models.system import System


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestRawParser:
    """Test cases for RAW file parser."""

    def test_parse_nonexistent_file(self):
        """Test that parsing a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_raw("nonexistent_file.raw")

    def test_parse_returns_system(self):
        """Test that parse_raw returns a System object."""
        # Note: This test will be expanded once test fixtures are available
        # For now, we test the basic structure
        pass

    def test_parser_handles_comments(self):
        """Test that parser correctly handles comment lines."""
        # Note: This will be tested with actual fixture files
        pass

    def test_parser_handles_empty_sections(self):
        """Test that parser handles files with missing sections."""
        # Note: This will be tested with actual fixture files
        pass


class TestIEEE9Bus:
    """Test cases for IEEE 9-bus system (v34 format)."""

    def test_parse_ieee9_returns_system(self, fixtures_dir):
        """Test that parsing IEEE 9-bus returns a System object."""
        system = parse_raw(fixtures_dir / "ieee9.raw")
        assert isinstance(system, System)

    def test_parse_ieee9_base_mva(self, fixtures_dir):
        """Test that base MVA is correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee9.raw")
        assert system.base_mva == 100.0

    def test_parse_ieee9_buses(self, fixtures_dir):
        """Test that all 9 buses are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee9.raw")
        assert len(system.buses) == 9

        # Check bus types
        slack_buses = system.get_slack_buses()
        pv_buses = system.get_pv_buses()
        pq_buses = system.get_pq_buses()

        assert len(slack_buses) == 1
        assert slack_buses[0].bus_id == 1
        assert len(pv_buses) == 2
        assert len(pq_buses) == 6

    def test_parse_ieee9_generators(self, fixtures_dir):
        """Test that all 3 generators are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee9.raw")
        assert len(system.generators) == 3

        # Check generator locations
        gen_buses = {g.bus_id for g in system.generators}
        assert gen_buses == {1, 2, 3}

        # Check total generation (approx 320 MW)
        total_p, _ = system.total_generation()
        assert abs(total_p * system.base_mva - 319.94) < 0.1

    def test_parse_ieee9_loads(self, fixtures_dir):
        """Test that all 3 loads are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee9.raw")
        assert len(system.loads) == 3

        # Check load locations
        load_buses = {load.bus_id for load in system.loads}
        assert load_buses == {5, 6, 8}

        # Check total load (315 MW)
        total_p, _ = system.total_load()
        assert abs(total_p * system.base_mva - 315.0) < 0.1

    def test_parse_ieee9_branches(self, fixtures_dir):
        """Test that all 9 branches (6 lines + 3 transformers) are parsed."""
        system = parse_raw(fixtures_dir / "ieee9.raw")
        assert len(system.branches) == 9

        # Check that transmission lines have non-zero B (charging susceptance)
        lines_with_charging = [b for b in system.branches if b.b_pu > 0]
        assert len(lines_with_charging) == 6

        # Check that transformers have zero B
        transformers = [b for b in system.branches if b.b_pu == 0]
        assert len(transformers) == 3

    def test_parse_ieee9_power_balance(self, fixtures_dir):
        """Test that generation exceeds load (accounting for losses)."""
        system = parse_raw(fixtures_dir / "ieee9.raw")

        total_gen, _ = system.total_generation()
        total_load, _ = system.total_load()

        # Generation should exceed load (difference is losses)
        assert total_gen > total_load


class TestIEEE14Bus:
    """Test cases for IEEE 14-bus system (v33 format).

    Source: ITI/models repository (University of Washington Archive)
    https://github.com/ITI/models/blob/master/electric-grid/physical/reference/ieee-14bus/
    """

    def test_parse_ieee14_returns_system(self, fixtures_dir):
        """Test that parsing IEEE 14-bus returns a System object."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert isinstance(system, System)

    def test_parse_ieee14_base_mva(self, fixtures_dir):
        """Test that base MVA is correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert system.base_mva == 100.0

    def test_parse_ieee14_buses(self, fixtures_dir):
        """Test that all 14 buses are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert len(system.buses) == 14

        # Check bus types: 1 slack, 4 PV (gens at buses 2,3,6,8), 9 PQ
        slack_buses = system.get_slack_buses()
        pv_buses = system.get_pv_buses()
        pq_buses = system.get_pq_buses()

        assert len(slack_buses) == 1
        assert slack_buses[0].bus_id == 1
        assert len(pv_buses) == 4
        assert len(pq_buses) == 9

    def test_parse_ieee14_generators(self, fixtures_dir):
        """Test that all 5 generators are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert len(system.generators) == 5

        # Check generator locations
        gen_buses = {g.bus_id for g in system.generators}
        assert gen_buses == {1, 2, 3, 6, 8}

    def test_parse_ieee14_loads(self, fixtures_dir):
        """Test that all 11 loads are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert len(system.loads) == 11

        # Check total load (approximately 259 MW)
        total_p, _ = system.total_load()
        assert abs(total_p * system.base_mva - 259.0) < 1.0

    def test_parse_ieee14_branches(self, fixtures_dir):
        """Test that all 20 branches are parsed (17 lines + 3 transformers)."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert len(system.branches) == 20

    def test_parse_ieee14_shunts(self, fixtures_dir):
        """Test that the shunt capacitor at bus 9 is parsed."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert len(system.shunts) == 1
        assert system.shunts[0].bus_id == 9
        # 19 MVAr capacitor -> positive B
        assert system.shunts[0].b_pu > 0

    def test_parse_ieee14_power_balance(self, fixtures_dir):
        """Test that generation exceeds load (accounting for losses)."""
        system = parse_raw(fixtures_dir / "ieee14.raw")

        total_gen, _ = system.total_generation()
        total_load, _ = system.total_load()

        # Generation should exceed load (difference is losses)
        assert total_gen > total_load


class TestIEEE118Bus:
    """Test cases for IEEE 118-bus system (v33 format, alternative source).

    Source: powsybl/powsybl-distribution repository
    https://github.com/powsybl/powsybl-distribution/blob/main/resources/PSSE/IEEE_118_bus.raw
    """

    def test_parse_ieee118_returns_system(self, fixtures_dir):
        """Test that parsing IEEE 118-bus returns a System object."""
        system = parse_raw(fixtures_dir / "ieee118_powsybl.raw")
        assert isinstance(system, System)

    def test_parse_ieee118_buses(self, fixtures_dir):
        """Test that all 118 buses are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee118_powsybl.raw")
        assert len(system.buses) == 118

    def test_parse_ieee118_generators(self, fixtures_dir):
        """Test that all 54 generators are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee118_powsybl.raw")
        assert len(system.generators) == 54

    def test_parse_ieee118_branches(self, fixtures_dir):
        """Test that all 186 branches are parsed."""
        system = parse_raw(fixtures_dir / "ieee118_powsybl.raw")
        assert len(system.branches) == 186

    def test_parse_ieee118_shunts(self, fixtures_dir):
        """Test that all 14 shunts are parsed."""
        system = parse_raw(fixtures_dir / "ieee118_powsybl.raw")
        assert len(system.shunts) == 14


class TestParserTolerance:
    """Test parser tolerance for different RAW file formats.

    The parser should correctly handle:
    - v33 format (bus data immediately after case ID)
    - v34 format (explicit "BEGIN XXX DATA" markers)
    - Mixed styles (v33 header with v34-style section markers)
    """

    def test_v33_format_no_begin_marker(self, fixtures_dir):
        """Test that v33 format without explicit BEGIN BUS DATA marker works."""
        # IEEE 14-bus uses v33 format where bus data starts after line 3
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert len(system.buses) == 14

    def test_v34_format_with_begin_markers(self, fixtures_dir):
        """Test that v34 format with BEGIN markers works."""
        # IEEE 9-bus uses v34 format with explicit section markers
        system = parse_raw(fixtures_dir / "ieee9.raw")
        assert len(system.buses) == 9

    def test_both_formats_produce_valid_systems(self, fixtures_dir):
        """Test that both formats produce systems with all required data."""
        s33 = parse_raw(fixtures_dir / "ieee14.raw")
        s34 = parse_raw(fixtures_dir / "ieee9.raw")

        # Both should have valid power balance
        for system in [s33, s34]:
            assert len(system.buses) > 0
            assert len(system.generators) > 0
            assert len(system.branches) > 0
            gen_p, _ = system.total_generation()
            load_p, _ = system.total_load()
            assert gen_p >= load_p  # Generation covers load
