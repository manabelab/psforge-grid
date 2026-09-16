"""Tests for PSS/E RAW file parser.

Tests the parsing functionality for PSS/E RAW format files.
"""

import pytest

from psforge_grid.io.raw_parser import parse_raw
from psforge_grid.models.system import System


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


class TestNewEngland39Bus:
    """Test cases for the New England 39-bus system (v34 format).

    This is the v34 fixture and the only one in the suite that PSS/E itself
    wrote (``PSS(R)E-34.8``), so it is what shows the parser reads what other
    tools produce rather than only what psforge writes. Terms: BSD 3-Clause,
    recorded in ``tests/fixtures/NOTICE.md``.
    """

    def test_parse_39bus_returns_system(self, fixtures_dir):
        """Test that parsing the 39-bus case returns a System object."""
        system = parse_raw(fixtures_dir / "39bus.raw")
        assert isinstance(system, System)

    def test_parse_39bus_base_mva(self, fixtures_dir):
        """Test that base MVA is correctly parsed."""
        system = parse_raw(fixtures_dir / "39bus.raw")
        assert system.base_mva == 100.0

    def test_parse_39bus_buses(self, fixtures_dir):
        """Test that all 39 buses are correctly parsed."""
        system = parse_raw(fixtures_dir / "39bus.raw")
        assert len(system.buses) == 39

        # Check bus types
        slack_buses = system.get_slack_buses()
        pv_buses = system.get_pv_buses()
        pq_buses = system.get_pq_buses()

        assert len(slack_buses) == 1
        assert slack_buses[0].bus_id == 39
        assert len(pv_buses) == 9
        assert len(pq_buses) == 29

    def test_parse_39bus_generators(self, fixtures_dir):
        """Test that all 10 generators are correctly parsed."""
        system = parse_raw(fixtures_dir / "39bus.raw")
        assert len(system.generators) == 10

        # Check generator locations
        gen_buses = {g.bus_id for g in system.generators}
        assert gen_buses == {30, 31, 32, 33, 34, 35, 36, 37, 38, 39}

        # Check total generation (approx 6205 MW)
        total_p, _ = system.total_generation()
        assert abs(total_p * system.base_mva - 6205.177) < 0.1

    def test_parse_39bus_loads(self, fixtures_dir):
        """Test that all 19 loads are correctly parsed."""
        system = parse_raw(fixtures_dir / "39bus.raw")
        assert len(system.loads) == 19

        # Check total load (6150.5 MW)
        total_p, _ = system.total_load()
        assert abs(total_p * system.base_mva - 6150.5) < 0.1

    def test_parse_39bus_branches(self, fixtures_dir):
        """Test that all 46 branches (34 lines + 12 transformers) are parsed."""
        system = parse_raw(fixtures_dir / "39bus.raw")
        assert len(system.branches) == 46

        # Check that transmission lines have non-zero B (charging susceptance)
        lines_with_charging = [b for b in system.branches if b.b_pu > 0]
        assert len(lines_with_charging) == 34

        # Check that transformers have zero B
        transformers = [b for b in system.branches if b.b_pu == 0]
        assert len(transformers) == 12

    def test_parse_39bus_is_xfmr_flag(self, fixtures_dir):
        """Test that is_xfmr=True is set for transformers parsed from RAW.

        The 39-bus case has 12 transformers, several with tap_ratio=1.0 on
        system base. Without is_xfmr, these would be misidentified as
        transmission lines. The RAW parser sets is_xfmr=True for all branches
        from TRANSFORMER DATA.
        """
        system = parse_raw(fixtures_dir / "39bus.raw")

        xfmr_branches = [b for b in system.branches if b.is_xfmr is True]
        assert len(xfmr_branches) == 12

        # All is_xfmr=True branches should also return is_transformer=True
        for b in xfmr_branches:
            assert b.is_transformer is True

        # Lines should have is_xfmr=None (not set by BRANCH DATA section)
        line_branches = [b for b in system.branches if b.is_xfmr is None]
        assert len(line_branches) == 34
        for b in line_branches:
            assert b.is_transformer is False

    def test_parse_39bus_power_balance(self, fixtures_dir):
        """Test that generation exceeds load (accounting for losses).

        The 39-bus fixture carries a solved operating point, so this holds.
        It does not hold for the pglib-derived fixtures, which carry an
        unsolved starting point -- see TestIEEE14Bus.
        """
        system = parse_raw(fixtures_dir / "39bus.raw")

        total_gen, _ = system.total_generation()
        total_load, _ = system.total_load()

        # Generation should exceed load (difference is losses)
        assert total_gen > total_load


class TestIEEE14Bus:
    """Test cases for IEEE 14-bus system (v33 format).

    The fixture is written by psforge's own RawWriter from
    ``pglib_opf_case14_ieee.m`` (CC BY 4.0). It therefore carries pglib's
    **unsolved** starting point: bus voltages are flat and generation does not
    cover load. Assertions about a solved operating point belong on
    ``39bus.raw`` instead -- see TestNewEngland39Bus.
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

    def test_parse_ieee14_dispatch_is_an_unsolved_starting_point(self, fixtures_dir):
        """The fixture carries pglib's starting dispatch, not a solved one.

        pglib states P at 170 + 29.5 = 199.5 MW against 259 MW of load, so
        generation does **not** cover load. Asserting otherwise would silently
        pass only as long as nobody regenerated the fixture from its source.
        """
        system = parse_raw(fixtures_dir / "ieee14.raw")

        total_gen, _ = system.total_generation()
        total_load, _ = system.total_load()

        assert total_gen * system.base_mva == pytest.approx(199.5)
        assert total_gen < total_load


class TestIEEE118Bus:
    """Test cases for IEEE 118-bus system (v33 format).

    The fixture is written by psforge's own RawWriter from
    ``pglib_opf_case118_ieee.m`` (CC BY 4.0). Unlike the 14-bus case, pglib's
    118-bus file carries real base voltages (138 / 161 / 345 kV), so this is
    the fixture that exercises a multi-voltage-level network.
    """

    def test_parse_ieee118_returns_system(self, fixtures_dir):
        """Test that parsing IEEE 118-bus returns a System object."""
        system = parse_raw(fixtures_dir / "ieee118.raw")
        assert isinstance(system, System)

    def test_parse_ieee118_buses(self, fixtures_dir):
        """Test that all 118 buses are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee118.raw")
        assert len(system.buses) == 118

    def test_parse_ieee118_generators(self, fixtures_dir):
        """Test that all 54 generators are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee118.raw")
        assert len(system.generators) == 54

    def test_parse_ieee118_branches(self, fixtures_dir):
        """Test that all 186 branches are parsed."""
        system = parse_raw(fixtures_dir / "ieee118.raw")
        assert len(system.branches) == 186

    def test_parse_ieee118_shunts(self, fixtures_dir):
        """Test that all 14 shunts are parsed."""
        system = parse_raw(fixtures_dir / "ieee118.raw")
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
        # The 39-bus case uses v34 format with explicit section markers
        system = parse_raw(fixtures_dir / "39bus.raw")
        assert len(system.buses) == 39

    def test_both_formats_produce_valid_systems(self, fixtures_dir):
        """Test that both formats produce systems with all required data."""
        s33 = parse_raw(fixtures_dir / "ieee14.raw")
        s34 = parse_raw(fixtures_dir / "39bus.raw")

        for system in [s33, s34]:
            assert len(system.buses) > 0
            assert len(system.generators) > 0
            assert len(system.branches) > 0

        # Only the solved fixture can be asked whether generation covers load.
        gen_p, _ = s34.total_generation()
        load_p, _ = s34.total_load()
        assert gen_p >= load_p
