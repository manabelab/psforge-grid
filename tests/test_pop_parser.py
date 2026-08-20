"""Tests for CPAT .pop format parser.

Test data: IEEJ WEST 10-Machine Model (Peak) standard test system.
Reference: IEEJ Technical Report, CPAT-GUI format.

System characteristics:
    - 27 buses (10 generator buses + 17 load/intermediate buses)
    - 25 transmission lines + 10 transformers = 35 branches
    - 10 generators (G1-G10), G10 is swing
    - 17 loads on intermediate buses
    - Base MVA: 1000
    - Frequency: 60 Hz
"""

from __future__ import annotations

from pathlib import Path

import pytest

from psforge_grid.io.pop.archive import PopArchive
from psforge_grid.io.pop.case_data import parse_case_data
from psforge_grid.io.pop.control_data import parse_control_data
from psforge_grid.io.pop.topology import parse_topology
from psforge_grid.io.pop_parser import PopParser, parse_pop
from psforge_grid.models.system import System

FIXTURE_DIR = Path(__file__).parent / "fixtures"
WEST10_POP = FIXTURE_DIR / "WEST10peak.pop"


@pytest.fixture
def west10_archive() -> PopArchive:
    """Open WEST10peak.pop archive for testing."""
    return PopArchive(WEST10_POP)


@pytest.fixture
def west10_system() -> System:
    """Parse WEST10peak.pop into a System object."""
    return parse_pop(WEST10_POP)


# ============================================================
# Archive tests
# ============================================================


class TestPopArchive:
    """Tests for ZIP archive extraction."""

    def test_open_valid_pop(self, west10_archive: PopArchive) -> None:
        """Archive should successfully open and parse all 3 XML files."""
        assert west10_archive.pnsd_root is not None
        assert west10_archive.pnsw_root is not None
        assert west10_archive.pnsj_root is not None

    def test_open_nonexistent_file(self) -> None:
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            PopArchive("nonexistent.pop")

    def test_pnsd_has_control_data(self, west10_archive: PopArchive) -> None:
        """data.pnsd should contain ControlData section."""
        cd = west10_archive.pnsd_root.find("ControlData")
        assert cd is not None

    def test_pnsd_has_dict_sections(self, west10_archive: PopArchive) -> None:
        """data.pnsd should contain expected Dict sections."""
        root = west10_archive.pnsd_root
        assert root.find("DictDataNodeValue") is not None
        assert root.find("DictDataTransmissionLine") is not None
        assert root.find("DictDataTransformer") is not None
        assert root.find("DictDataGenerator") is not None
        assert root.find("DictDataLoad") is not None


# ============================================================
# Control data tests
# ============================================================


class TestControlData:
    """Tests for ControlData and VolDataSet parsing."""

    def test_base_mva(self, west10_archive: PopArchive) -> None:
        """System base MVA should be 1000."""
        control = parse_control_data(west10_archive.pnsd_root)
        assert control.base_mva == 1000.0

    def test_frequency(self, west10_archive: PopArchive) -> None:
        """System frequency should be 60 Hz."""
        control = parse_control_data(west10_archive.pnsd_root)
        assert control.frequency_hz == 60.0

    def test_header(self, west10_archive: PopArchive) -> None:
        """System header should contain model name."""
        control = parse_control_data(west10_archive.pnsd_root)
        assert "WEST" in control.header
        assert "10" in control.header

    def test_voltage_classes(self, west10_archive: PopArchive) -> None:
        """VolDataSet should have 10 voltage classes (0-9)."""
        control = parse_control_data(west10_archive.pnsd_root)
        assert len(control.voltage_classes) == 10
        # Index 9 = 30 kV (used by all WEST10 buses)
        assert control.voltage_classes[9] == 30.0
        # Index 0 = 1000 kV (EHV)
        assert control.voltage_classes[0] == 1000.0


# ============================================================
# Topology tests
# ============================================================


class TestTopology:
    """Tests for .pnsw topology parsing."""

    def test_node_count(self, west10_archive: PopArchive) -> None:
        """Should find 27 node clusters (buses)."""
        topo = parse_topology(west10_archive.pnsw_root)
        assert len(topo.nodes) == 27

    def test_transmission_line_count(self, west10_archive: PopArchive) -> None:
        """Should find 25 transmission line clusters."""
        topo = parse_topology(west10_archive.pnsw_root)
        assert len(topo.transmission_lines) == 25

    def test_transformer_count(self, west10_archive: PopArchive) -> None:
        """Should find 10 transformer clusters."""
        topo = parse_topology(west10_archive.pnsw_root)
        assert len(topo.transformers) == 10

    def test_generator_count(self, west10_archive: PopArchive) -> None:
        """Should find 10 generator clusters."""
        topo = parse_topology(west10_archive.pnsw_root)
        assert len(topo.generators) == 10

    def test_code_to_cluster_mapping(self, west10_archive: PopArchive) -> None:
        """CodeNumber → ClusterIndex mapping should exist for all nodes."""
        topo = parse_topology(west10_archive.pnsw_root)
        assert len(topo.code_to_cluster) == 27
        # Bus 21 (NODE21) should have a valid ClusterIndex
        assert 21 in topo.code_to_cluster

    def test_branch_from_to_resolution(self, west10_archive: PopArchive) -> None:
        """Branch from/to should resolve to valid bus CodeNumbers."""
        topo = parse_topology(west10_archive.pnsw_root)
        for _ci, cluster in topo.transmission_lines.items():
            from_bus, to_bus = topo.get_branch_from_to(cluster)
            assert from_bus in topo.code_to_cluster
            assert to_bus in topo.code_to_cluster

    def test_transformer_from_to_resolution(self, west10_archive: PopArchive) -> None:
        """Transformer from/to should resolve to valid bus CodeNumbers."""
        topo = parse_topology(west10_archive.pnsw_root)
        for _ci, cluster in topo.transformers.items():
            from_bus, to_bus = topo.get_branch_from_to(cluster)
            assert from_bus in topo.code_to_cluster
            assert to_bus in topo.code_to_cluster


# ============================================================
# Case data tests
# ============================================================


class TestCaseData:
    """Tests for .pnsj case data parsing."""

    def test_swing_bus_designation(self, west10_archive: PopArchive) -> None:
        """Bus 30 (G10) should be designated as swing bus."""
        case = parse_case_data(west10_archive.pnsj_root)
        assert case.has_swing is True
        assert case.nodes[30].is_swing is True

    def test_generator_dispatch(self, west10_archive: PopArchive) -> None:
        """Generator P dispatch should match expected values."""
        case = parse_case_data(west10_archive.pnsj_root)
        # G1 at bus 21: Pgo = 13.5 p.u. on 1000 MVA base
        assert case.nodes[21].p_gen_pu == pytest.approx(13.5)
        # G10 at bus 30 (swing): Pgo = 27.0
        assert case.nodes[30].p_gen_pu == pytest.approx(27.0)

    def test_load_values(self, west10_archive: PopArchive) -> None:
        """Load P values should match expected values."""
        case = parse_case_data(west10_archive.pnsj_root)
        # Bus 1: Plo = 12.0 p.u.
        assert case.nodes[1].p_load_pu == pytest.approx(12.0)
        # Bus 9: Plo = 28.3 p.u. (largest load)
        assert case.nodes[9].p_load_pu == pytest.approx(28.3)

    def test_voltage_setpoints(self, west10_archive: PopArchive) -> None:
        """Generator buses should have voltage setpoints."""
        case = parse_case_data(west10_archive.pnsj_root)
        # Generator buses have V=1.03
        assert case.nodes[21].voltage_pu == pytest.approx(1.03)

    def test_node_count(self, west10_archive: PopArchive) -> None:
        """Should have 27 nodes in case data."""
        case = parse_case_data(west10_archive.pnsj_root)
        assert len(case.nodes) == 27


# ============================================================
# Integration tests (full parse)
# ============================================================


class TestPopParserIntegration:
    """End-to-end tests for PopParser."""

    def test_system_bus_count(self, west10_system: System) -> None:
        """WEST10 should have 27 buses."""
        assert west10_system.num_buses == 27

    def test_system_branch_count(self, west10_system: System) -> None:
        """WEST10 should have 42 branches (32 lines + 10 transformers).

        The 32 lines come from 18 single-circuit lines (NL=1) plus
        7 double-circuit lines (NL=2) expanded to 14 branch objects.
        """
        assert west10_system.num_branches == 42

    def test_system_generator_count(self, west10_system: System) -> None:
        """WEST10 should have 10 generators."""
        assert west10_system.num_generators == 10

    def test_system_load_count(self, west10_system: System) -> None:
        """WEST10 should have 17 loads."""
        assert west10_system.num_loads == 17

    def test_base_mva(self, west10_system: System) -> None:
        """System base MVA should be 1000."""
        assert west10_system.base_mva == 1000.0

    def test_system_name(self, west10_system: System) -> None:
        """System name should contain model identifier."""
        assert "WEST" in west10_system.name

    def test_slack_bus(self, west10_system: System) -> None:
        """Bus 30 should be the slack bus."""
        slack = west10_system.get_slack_buses()
        assert len(slack) == 1
        assert slack[0].id == "B30"
        assert slack[0].number == 30
        assert slack[0].bus_type == 3

    def test_pv_buses(self, west10_system: System) -> None:
        """Should have 9 PV buses (G1-G9)."""
        pv = west10_system.get_pv_buses()
        assert len(pv) == 9
        assert {b.id for b in pv} == {"B21", "B22", "B23", "B24", "B25", "B26", "B27", "B28", "B29"}
        assert {b.number for b in pv} == {21, 22, 23, 24, 25, 26, 27, 28, 29}

    def test_pq_buses(self, west10_system: System) -> None:
        """Should have 17 PQ buses."""
        pq = west10_system.get_pq_buses()
        assert len(pq) == 17

    def test_bus_voltage_setpoints(self, west10_system: System) -> None:
        """Generator buses should have V=1.03, load buses V=1.0."""
        bus_map = {b.number: b for b in west10_system.buses}
        # Generator bus
        assert bus_map[21].v_magnitude == pytest.approx(1.03)
        # Load bus
        assert bus_map[1].v_magnitude == pytest.approx(1.0)

    def test_bus_base_kv(self, west10_system: System) -> None:
        """All WEST10 buses should be 30 kV."""
        for bus in west10_system.buses:
            assert bus.base_kv == pytest.approx(30.0)

    def test_generator_properties(self, west10_system: System) -> None:
        """Generator G1 should have correct machine parameters."""
        g1 = next(g for g in west10_system.generators if g.name == "G1")
        assert g1.id == "G1"
        assert g1.bus_id == "B21"
        assert g1.machine_id == "G1"
        assert g1.p_gen == pytest.approx(13.5)
        assert g1.v_setpoint == pytest.approx(1.03)
        assert g1.mbase == pytest.approx(15000.0)
        # Machine parameters (on machine base)
        assert g1.xd_pu == pytest.approx(1.7)
        assert g1.xdp_pu == pytest.approx(0.35)
        assert g1.xdpp_pu == pytest.approx(0.25)

    def test_generator_g10_swing(self, west10_system: System) -> None:
        """G10 (swing) should have largest dispatch."""
        g10 = next(g for g in west10_system.generators if g.name == "G10")
        assert g10.id == "G10"
        assert g10.bus_id == "B30"
        assert g10.p_gen == pytest.approx(27.0)
        assert g10.mbase == pytest.approx(30000.0)

    def test_transmission_line_impedance(self, west10_system: System) -> None:
        """Transmission line impedances should be correct."""
        # Find a line between bus 1 and bus 2 (double circuit: codes 20, 21)
        lines_1_2 = [
            b for b in west10_system.branches if b.from_bus_id == "B1" and b.to_bus_id == "B2"
        ]
        assert len(lines_1_2) == 2  # Double circuit
        assert {b.id for b in lines_1_2} == {"BR1", "BR2"}
        assert {b.circuit_id for b in lines_1_2} == {"20", "21"}
        for line in lines_1_2:
            assert line.r_pu == pytest.approx(0.0042)
            assert line.x_pu == pytest.approx(0.126)
            # CPAT Y1C=0.061 is Y/2; psforge converts to total B = 2*Y1C = 0.122
            assert line.b_pu == pytest.approx(0.122)

    def test_parallel_circuit_expansion(self, west10_system: System) -> None:
        """NL=2 lines should create 2 branches with per-circuit impedance.

        LINE130 (bus 13→3, CodeNumber 130) has NL=2 in the .pop file.
        The stored per-circuit impedance (r=0.0021, x=0.063) should be
        used directly and 2 branch objects with distinct ids and
        per-circuit circuit_ids should be created.
        """
        lines_13_3 = [
            b for b in west10_system.branches if b.from_bus_id == "B13" and b.to_bus_id == "B3"
        ]
        assert len(lines_13_3) == 2, "NL=2 should produce 2 branches"
        assert {b.id for b in lines_13_3} == {"BR6", "BR7"}
        assert {b.circuit_id for b in lines_13_3} == {"130_1", "130_2"}
        for line in lines_13_3:
            assert line.r_pu == pytest.approx(0.0021)
            assert line.x_pu == pytest.approx(0.063)

    def test_transformer_impedance(self, west10_system: System) -> None:
        """Transformer G1-TR (21→1) should have correct reactance."""
        g1_tr = next(
            b for b in west10_system.branches if b.from_bus_id == "B21" and b.to_bus_id == "B1"
        )
        assert g1_tr.id == "BR33"  # first transformer, after the 32 lines
        assert g1_tr.circuit_id == "910"  # CPAT CodeNumber preserved as data
        assert g1_tr.r_pu == pytest.approx(0.0)
        assert g1_tr.x_pu == pytest.approx(0.00932)

    def test_load_values(self, west10_system: System) -> None:
        """Load values should be in p.u. on system base."""
        load_map = {ld.bus_id: ld for ld in west10_system.loads}
        # Bus 1: largest load on intermediate bus (first in pnsj DictN order)
        assert load_map["B1"].id == "LD1"
        assert load_map["B1"].p_load == pytest.approx(12.0)
        # Bus 9: largest load overall
        assert load_map["B9"].p_load == pytest.approx(28.3)

    def test_power_balance(self, west10_system: System) -> None:
        """Total generation should approximately equal total load (pre-solve)."""
        total_gen = sum(g.p_gen for g in west10_system.generators)
        total_load = sum(ld.p_load for ld in west10_system.loads)
        # Generation: 13.5+9.0*7+4.5+27.0 = 13.5+63+4.5+27 = 108.0
        assert total_gen == pytest.approx(108.0, abs=0.1)
        # Load: 107.8 p.u. (slightly less than gen due to losses)
        assert total_load == pytest.approx(107.8, abs=0.1)
        assert total_load > 0


# ============================================================
# Unified identifier scheme tests (grid 0.10.0)
# ============================================================


class TestPopUnifiedIds:
    """Tests for the unified string identifier scheme."""

    def test_bus_ids_derived_from_cpat_numbers(self, west10_system: System) -> None:
        """Every bus id should be B{number} with the CPAT number preserved."""
        assert len(west10_system.buses) == 27
        for bus in west10_system.buses:
            assert bus.number is not None
            assert bus.id == f"B{bus.number}"
        assert {b.number for b in west10_system.buses} == (
            {1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17, 18, 19} | set(range(21, 31))
        )

    def test_ids_unique_across_all_element_types(self, west10_system: System) -> None:
        """All element ids must be unique across the whole system."""
        all_ids = (
            [b.id for b in west10_system.buses]
            + [b.id for b in west10_system.branches]
            + [g.id for g in west10_system.generators]
            + [ld.id for ld in west10_system.loads]
        )
        assert len(all_ids) == 27 + 42 + 10 + 17
        assert len(set(all_ids)) == len(all_ids)

    def test_ids_deterministic_across_parses(self) -> None:
        """Parsing the same file twice must generate identical ids."""
        first = parse_pop(WEST10_POP)
        second = parse_pop(WEST10_POP)
        assert [b.id for b in first.buses] == [b.id for b in second.buses]
        assert [b.id for b in first.branches] == [b.id for b in second.branches]
        assert [g.id for g in first.generators] == [g.id for g in second.generators]
        assert [ld.id for ld in first.loads] == [ld.id for ld in second.loads]

    def test_sequence_ids_match_order(self, west10_system: System) -> None:
        """BR/G/LD ids carry the per-type sequence number (= int(order))."""
        for br in west10_system.branches:
            assert br.order is not None
            assert br.id == f"BR{int(br.order)}"
        for gen in west10_system.generators:
            assert gen.order is not None
            assert gen.id == f"G{int(gen.order)}"
        for load in west10_system.loads:
            assert load.order is not None
            assert load.id == f"LD{int(load.order)}"

    def test_bus_orders_are_sequential(self, west10_system: System) -> None:
        """Bus order values should be 1.0 .. 27.0 (file occurrence order)."""
        orders = sorted(b.order for b in west10_system.buses if b.order is not None)
        assert orders == [float(i) for i in range(1, 28)]

    def test_branch_orders_are_sequential(self, west10_system: System) -> None:
        """Branch order values should be 1.0 .. 42.0 (file occurrence order)."""
        orders = sorted(b.order for b in west10_system.branches if b.order is not None)
        assert orders == [float(i) for i in range(1, 43)]

    def test_generator_and_load_orders_are_sequential(self, west10_system: System) -> None:
        """Generator/load order values should be per-type 1.0, 2.0, ..."""
        gen_orders = sorted(g.order for g in west10_system.generators if g.order is not None)
        assert gen_orders == [float(i) for i in range(1, 11)]
        load_orders = sorted(ld.order for ld in west10_system.loads if ld.order is not None)
        assert load_orders == [float(i) for i in range(1, 18)]

    def test_diagram_keys_use_unified_ids(self, west10_system: System) -> None:
        """Diagram positions/routes must be keyed by Bus.id / Branch.id."""
        diagram = west10_system.diagram_schematic
        assert diagram is not None
        bus_ids = {b.id for b in west10_system.buses}
        branch_ids = {b.id for b in west10_system.branches}
        # WEST10 has diagram coordinates for every bus and branch
        assert set(diagram.bus_positions) == bus_ids
        assert set(diagram.branch_routes) == branch_ids


# ============================================================
# Factory and convenience method tests
# ============================================================


class TestPopParserFactory:
    """Tests for ParserFactory and System.from_pop() integration."""

    def test_parser_factory_create(self) -> None:
        """ParserFactory should create PopParser for 'pop' format."""
        from psforge_grid.io.factories import ParserFactory

        parser = ParserFactory.create("pop")
        assert isinstance(parser, PopParser)

    def test_parser_factory_from_extension(self) -> None:
        """ParserFactory should detect .pop extension."""
        from psforge_grid.io.factories import ParserFactory

        parser = ParserFactory.from_extension(".pop")
        assert isinstance(parser, PopParser)

    def test_system_from_pop(self) -> None:
        """System.from_pop() should load the system."""
        system = System.from_pop(WEST10_POP)
        assert system.num_buses == 27

    def test_system_from_file_auto_detect(self) -> None:
        """System.from_file() should auto-detect .pop format."""
        system = System.from_file(WEST10_POP)
        assert system.num_buses == 27
        assert system.base_mva == 1000.0

    def test_pop_parser_format_name(self) -> None:
        """PopParser should report correct format name."""
        parser = PopParser()
        assert parser.format_name == "CPAT Pop"

    def test_pop_parser_extensions(self) -> None:
        """PopParser should support .pop extension."""
        parser = PopParser()
        assert "pop" in parser.supported_extensions

    def test_available_formats_includes_pop(self) -> None:
        """ParserFactory should list 'pop' in available formats."""
        from psforge_grid.io.factories import ParserFactory

        assert "pop" in ParserFactory.available_formats()
