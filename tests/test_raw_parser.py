"""Tests for PSS/E RAW file parser.

Tests the parsing functionality for PSS/E RAW format files, including the
unified identifier scheme (grid 0.10.0): deterministic string ids, order
assignment, source-data round-trip fields (number, circuit_id, machine_id,
load_id, shunt_id) and writer symmetry.
"""

import pytest

from psforge_grid.io.raw_parser import parse_raw
from psforge_grid.io.raw_writer import write_raw
from psforge_grid.models.bus import Bus
from psforge_grid.models.system import System


class TestRawParser:
    """Test cases for RAW file parser."""

    def test_parse_nonexistent_file(self):
        """Test that parsing a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_raw("nonexistent_file.raw")


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
        assert slack_buses[0].id == "B1"
        assert slack_buses[0].number == 1
        assert len(pv_buses) == 2
        assert len(pq_buses) == 6

    def test_parse_ieee9_generators(self, fixtures_dir):
        """Test that all 3 generators are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee9.raw")
        assert len(system.generators) == 3

        # Check generated ids (type prefix + appearance order) and bus
        # references (Bus.id strings)
        assert [g.id for g in system.generators] == ["G1", "G2", "G3"]
        assert {g.bus_id for g in system.generators} == {"B1", "B2", "B3"}
        # Source machine ID is preserved for round-trip
        assert all(g.machine_id == "1" for g in system.generators)

        # Check total generation (approx 320 MW)
        total_p, _ = system.total_generation()
        assert abs(total_p * system.base_mva - 319.94) < 0.1

    def test_parse_ieee9_loads(self, fixtures_dir):
        """Test that all 3 loads are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee9.raw")
        assert len(system.loads) == 3

        # Check generated ids (appearance order) and bus references
        assert [ld.id for ld in system.loads] == ["LD1", "LD2", "LD3"]
        assert {ld.bus_id for ld in system.loads} == {"B5", "B6", "B8"}
        # Source load ID is preserved for round-trip
        assert all(ld.load_id == "1" for ld in system.loads)

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

    def test_parse_ieee9_branch_ids_reference_buses(self, fixtures_dir):
        """Test that branch ids and bus references follow the id scheme.

        First branch in the file is 4-5 circuit '1 ': id BR1 (first branch
        in appearance order), endpoints expressed as Bus.id strings, and
        the stripped circuit ID preserved.
        """
        system = parse_raw(fixtures_dir / "ieee9.raw")
        first = system.branches[0]
        assert first.id == "BR1"
        assert first.from_bus_id == "B4"
        assert first.to_bus_id == "B5"
        assert first.circuit_id == "1"

    def test_parse_ieee9_is_xfmr_flag(self, fixtures_dir):
        """Test that is_xfmr=True is set for transformers parsed from RAW.

        IEEE 9-bus has 3 step-up transformers with tap_ratio=1.0 on system base.
        Without is_xfmr, these would be misidentified as transmission lines.
        The RAW parser sets is_xfmr=True for all branches from TRANSFORMER DATA.
        """
        system = parse_raw(fixtures_dir / "ieee9.raw")

        xfmr_branches = [b for b in system.branches if b.is_xfmr is True]
        assert len(xfmr_branches) == 3

        # All is_xfmr=True branches should also return is_transformer=True
        for b in xfmr_branches:
            assert b.is_transformer is True

        # Lines should have is_xfmr=None (not set by BRANCH DATA section)
        line_branches = [b for b in system.branches if b.is_xfmr is None]
        assert len(line_branches) == 6
        for b in line_branches:
            assert b.is_transformer is False

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

        # Ids are generated from the source bus numbers, which are preserved
        assert [b.id for b in system.buses] == [f"B{n}" for n in range(1, 15)]
        assert [b.number for b in system.buses] == list(range(1, 15))

        # Check bus types: 1 slack, 4 PV (gens at buses 2,3,6,8), 9 PQ
        slack_buses = system.get_slack_buses()
        pv_buses = system.get_pv_buses()
        pq_buses = system.get_pq_buses()

        assert len(slack_buses) == 1
        assert slack_buses[0].id == "B1"
        assert slack_buses[0].number == 1
        assert len(pv_buses) == 4
        assert len(pq_buses) == 9

    def test_parse_ieee14_generators(self, fixtures_dir):
        """Test that all 5 generators are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert len(system.generators) == 5

        # Check generator ids (appearance order) and bus references
        assert [g.id for g in system.generators] == ["G1", "G2", "G3", "G4", "G5"]
        assert {g.bus_id for g in system.generators} == {"B1", "B2", "B3", "B6", "B8"}
        assert all(g.machine_id == "1" for g in system.generators)

    def test_parse_ieee14_loads(self, fixtures_dir):
        """Test that all 11 loads are correctly parsed."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert len(system.loads) == 11

        # First load in the file sits on bus 2 with source ID '1 '
        first = system.loads[0]
        assert first.id == "LD1"
        assert first.bus_id == "B2"
        assert first.load_id == "1"

        # Check total load (approximately 259 MW)
        total_p, _ = system.total_load()
        assert abs(total_p * system.base_mva - 259.0) < 1.0

    def test_parse_ieee14_branches(self, fixtures_dir):
        """Test that all 20 branches are parsed (17 lines + 3 transformers)."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert len(system.branches) == 20

        # First branch is 1-2 circuit '1 ': deterministic id (appearance
        # order), Bus.id references, and the stripped circuit ID preserved
        first = system.branches[0]
        assert first.id == "BR1"
        assert first.from_bus_id == "B1"
        assert first.to_bus_id == "B2"
        assert first.circuit_id == "1"

    def test_parse_ieee14_shunts(self, fixtures_dir):
        """Test that the shunt capacitor at bus 9 is parsed."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        assert len(system.shunts) == 1
        shunt = system.shunts[0]
        assert shunt.id == "SH1"
        assert shunt.bus_id == "B9"
        assert shunt.shunt_id == "1"
        # 19 MVAr capacitor -> positive B
        assert shunt.b_pu > 0

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

    def test_parse_ieee118_ids_unique_across_types(self, fixtures_dir):
        """Test that generated ids are unique across all element types."""
        system = parse_raw(fixtures_dir / "ieee118_powsybl.raw")
        all_ids = (
            [b.id for b in system.buses]
            + [b.id for b in system.branches]
            + [g.id for g in system.generators]
            + [ld.id for ld in system.loads]
            + [s.id for s in system.shunts]
        )
        assert len(all_ids) == 118 + 186 + 54 + len(system.loads) + 14
        assert len(set(all_ids)) == len(all_ids)


class TestUnifiedIdScheme:
    """Test the unified identifier scheme contract (grid 0.10.0).

    Parsers must generate deterministic ids (same file, same ids), assign
    per-type sequential order values, and keep source identifiers for
    round-trip.
    """

    def test_ids_are_deterministic(self, fixtures_dir):
        """Parsing the same file twice yields identical ids for every element."""
        s1 = parse_raw(fixtures_dir / "ieee14.raw")
        s2 = parse_raw(fixtures_dir / "ieee14.raw")

        assert [b.id for b in s1.buses] == [b.id for b in s2.buses]
        assert [b.id for b in s1.branches] == [b.id for b in s2.branches]
        assert [g.id for g in s1.generators] == [g.id for g in s2.generators]
        assert [ld.id for ld in s1.loads] == [ld.id for ld in s2.loads]
        assert [s.id for s in s1.shunts] == [s.id for s in s2.shunts]
        # Guard against vacuous pass on empty lists
        assert len(s1.buses) == 14
        assert len(s1.branches) == 20

    def test_order_is_sequential_per_element_type(self, fixtures_dir):
        """Order is 1.0, 2.0, ... in file appearance order, per element type."""
        system = parse_raw(fixtures_dir / "ieee14.raw")

        assert [b.order for b in system.buses] == [float(i) for i in range(1, 15)]
        assert [b.order for b in system.branches] == [float(i) for i in range(1, 21)]
        assert [g.order for g in system.generators] == [1.0, 2.0, 3.0, 4.0, 5.0]
        assert [ld.order for ld in system.loads] == [float(i) for i in range(1, 12)]
        assert [s.order for s in system.shunts] == [1.0]

    def test_order_continues_across_branch_and_transformer_sections(self, fixtures_dir):
        """v34 transformer branches continue the branch order sequence.

        IEEE 9-bus (v34) has 6 lines in BRANCH DATA followed by 3
        transformers in TRANSFORMER DATA; all are Branch elements and share
        one order sequence 1.0 ... 9.0.
        """
        system = parse_raw(fixtures_dir / "ieee9.raw")
        assert [b.order for b in system.branches] == [float(i) for i in range(1, 10)]
        # The last three (7.0-9.0) are the transformers
        assert [b.is_xfmr for b in system.branches[6:]] == [True, True, True]

    def test_all_ids_unique_across_types(self, fixtures_dir):
        """All generated ids are unique across the whole system."""
        system = parse_raw(fixtures_dir / "ieee14.raw")
        all_ids = (
            [b.id for b in system.buses]
            + [b.id for b in system.branches]
            + [g.id for g in system.generators]
            + [ld.id for ld in system.loads]
            + [s.id for s in system.shunts]
        )
        assert len(all_ids) == 14 + 20 + 5 + 11 + 1
        assert len(set(all_ids)) == len(all_ids)


class TestRawRoundTrip:
    """Round-trip tests: parse -> write -> parse must preserve identity data.

    The unified string id itself is not written to RAW (the format has no
    field for it); the round-trip works because the writer preserves the
    element list order and ids are generated from appearance order (plus
    ``Bus.number`` for buses), so the parser regenerates identical ids.
    """

    def test_ieee14_round_trip_regenerates_same_ids(self, fixtures_dir, tmp_path):
        """Writing and re-parsing IEEE 14-bus reproduces all ids and numbers."""
        original = parse_raw(fixtures_dir / "ieee14.raw")
        out = tmp_path / "ieee14_roundtrip.raw"
        write_raw(original, out)
        reparsed = parse_raw(out)

        assert reparsed.base_mva == original.base_mva
        assert [b.number for b in reparsed.buses] == [b.number for b in original.buses]
        assert [b.id for b in reparsed.buses] == [b.id for b in original.buses]
        assert [b.id for b in reparsed.branches] == [b.id for b in original.branches]
        assert [g.id for g in reparsed.generators] == [g.id for g in original.generators]
        assert [ld.id for ld in reparsed.loads] == [ld.id for ld in original.loads]
        assert [s.id for s in reparsed.shunts] == [s.id for s in original.shunts]

        # Power totals survive the unit conversions (pu -> MW -> pu)
        p_orig, q_orig = original.total_load()
        p_rt, q_rt = reparsed.total_load()
        assert abs(p_rt - p_orig) < 1e-6
        assert abs(q_rt - q_orig) < 1e-6

    def test_writer_assigns_numbers_to_unnumbered_buses(self, tmp_path):
        """Buses without a source number get the lowest unused integers.

        A hand-built system has no Bus.number at all; the writer must
        assign 1, 2, ... in list order so the file is valid RAW, and the
        re-parsed system carries those numbers.
        """
        system = System(
            buses=[
                Bus("Alpha", bus_type=3),
                Bus("Beta", bus_type=1),
            ]
        )
        out = tmp_path / "unnumbered.raw"
        write_raw(system, out)
        reparsed = parse_raw(out)

        assert [b.number for b in reparsed.buses] == [1, 2]
        assert [b.id for b in reparsed.buses] == ["B1", "B2"]
        assert [b.bus_type for b in reparsed.buses] == [3, 1]


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
