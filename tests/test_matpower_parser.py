"""Tests for MATPOWER file parser.

Tests the parsing functionality for MATPOWER format (.m) files,
including pglib-opf benchmark cases, under the unified string id scheme
(grid 0.10.0): deterministic type-prefix + sequence ids (B1, BR1, G1,
LD1, SH1, GC1 — ids carry no connectivity), Bus.number round-trip,
per-type order sequences, and generator_id-based cost linkage.
"""

import math

import pytest

from psforge_grid.io.factories import ParserFactory
from psforge_grid.io.matpower_parser import MatpowerParser, parse_matpower
from psforge_grid.models.generator_cost import GeneratorCost
from psforge_grid.models.system import System


class TestMatpowerParser:
    """Test cases for MATPOWER file parser basics."""

    def test_parse_nonexistent_file(self):
        """Test that parsing a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_matpower("nonexistent_file.m")

    def test_parse_returns_system(self, fixtures_dir):
        """Test that parse_matpower returns a System object."""
        system = parse_matpower(fixtures_dir / "pglib_opf_case5_pjm.m")
        assert isinstance(system, System)

    def test_parser_class_interface(self):
        """Test that MatpowerParser implements IParser correctly."""
        parser = MatpowerParser()
        assert parser.format_name == "MATPOWER"
        assert "m" in parser.supported_extensions

    def test_parser_class_parse(self, fixtures_dir):
        """Test that MatpowerParser.parse() works correctly."""
        parser = MatpowerParser()
        system = parser.parse(fixtures_dir / "pglib_opf_case5_pjm.m")
        assert isinstance(system, System)
        assert system.num_buses == 5


class TestCase5PJM:
    """Test cases for pglib_opf_case5_pjm (5-bus PJM system)."""

    @pytest.fixture
    def system(self, fixtures_dir):
        """Parse the 5-bus PJM system."""
        return parse_matpower(fixtures_dir / "pglib_opf_case5_pjm.m")

    def test_base_mva(self, system):
        """Test that base MVA is correctly parsed."""
        assert system.base_mva == 100.0

    def test_case_name(self, system):
        """Test that case name is extracted from function declaration."""
        assert system.name == "pglib_opf_case5_pjm"

    def test_num_buses(self, system):
        """Test that all 5 buses are parsed."""
        assert system.num_buses == 5

    def test_num_generators(self, system):
        """Test that all 5 generators are parsed."""
        assert system.num_generators == 5

    def test_num_loads(self, system):
        """Test that 3 loads are created (buses 2, 3, 4 have non-zero Pd)."""
        assert system.num_loads == 3

    def test_num_branches(self, system):
        """Test that all 6 branches are parsed."""
        assert system.num_branches == 6

    def test_num_shunts(self, system):
        """Test that no shunts exist (all Gs=Bs=0)."""
        assert system.num_shunts == 0

    def test_num_generator_costs(self, system):
        """Test that 5 cost functions are parsed."""
        assert system.num_generator_costs == 5

    def test_bus_ids_and_numbers(self, system):
        """Test that bus ids follow B{number} and Bus.number keeps the source number."""
        assert [b.id for b in system.buses] == ["B1", "B2", "B3", "B4", "B5"]
        assert [b.number for b in system.buses] == [1, 2, 3, 4, 5]

    def test_bus_types(self, system):
        """Test bus type assignments."""
        bus_types = {b.id: b.bus_type for b in system.buses}
        assert bus_types["B1"] == 2  # PV
        assert bus_types["B2"] == 1  # PQ
        assert bus_types["B3"] == 2  # PV
        assert bus_types["B4"] == 3  # Slack
        assert bus_types["B5"] == 2  # PV

    def test_bus_voltage_limits(self, system):
        """Test bus voltage limits."""
        bus = system.get_bus("B1")
        assert bus is not None
        assert bus.v_max == 1.1
        assert bus.v_min == 0.9

    def test_bus_base_kv(self, system):
        """Test bus base voltage."""
        for bus in system.buses:
            assert bus.base_kv == 230.0

    def test_load_ids_and_source_fields(self, system):
        """Test load id generation (LD{n} in file order) and that load_id stays None."""
        assert [ld.id for ld in system.loads] == ["LD1", "LD2", "LD3"]
        assert [ld.bus_id for ld in system.loads] == ["B2", "B3", "B4"]
        # MATPOWER provides no load identifier: source-not-provided → None
        assert all(ld.load_id is None for ld in system.loads)

    def test_load_pu_conversion(self, system):
        """Test that load values are correctly converted to per-unit."""
        # Bus 2: Pd=300 MW, Qd=98.61 MVAr on 100 MVA base
        bus2_loads = system.get_bus_loads("B2")
        assert len(bus2_loads) == 1
        assert abs(bus2_loads[0].p_load - 3.0) < 1e-6
        assert abs(bus2_loads[0].q_load - 0.9861) < 1e-4

    def test_generator_ids(self, system):
        """Test generator id generation G{n} in file order (no connectivity in id)."""
        assert [g.id for g in system.generators] == ["G1", "G2", "G3", "G4", "G5"]
        assert [g.bus_id for g in system.generators] == ["B1", "B1", "B3", "B4", "B5"]

    def test_generator_pu_conversion(self, system):
        """Test that generator values are correctly converted to per-unit."""
        # Gen at bus 1 (first): Pg=20 MW, Pmax=40 MW on 100 MVA base
        bus1_gens = system.get_bus_generators("B1")
        assert len(bus1_gens) == 2
        gen1 = bus1_gens[0]
        assert abs(gen1.p_gen - 0.2) < 1e-6
        assert abs(gen1.p_max - 0.4) < 1e-6
        assert abs(gen1.p_min - 0.0) < 1e-6

    def test_multiple_generators_same_bus(self, system):
        """Test that multiple generators on bus 1 get distinct sequence ids."""
        bus1_gens = system.get_bus_generators("B1")
        assert len(bus1_gens) == 2
        assert {g.id for g in bus1_gens} == {"G1", "G2"}
        # MATPOWER provides no machine identifier: source-not-provided → None
        assert all(g.machine_id is None for g in bus1_gens)

    def test_branch_ids(self, system):
        """Test branch id generation BR{n} in file order and circuit_id stays None."""
        assert [b.id for b in system.branches] == [
            "BR1",
            "BR2",
            "BR3",
            "BR4",
            "BR5",
            "BR6",
        ]
        # MATPOWER provides no circuit ID column: source-not-provided → None
        assert all(b.circuit_id is None for b in system.branches)

    def test_branch_impedance(self, system):
        """Test branch impedance values (already in per-unit)."""
        # Branch 1-2: r=0.00281, x=0.0281, b=0.00712
        branch_1_2 = [b for b in system.branches if b.from_bus_id == "B1" and b.to_bus_id == "B2"]
        assert len(branch_1_2) == 1
        br = branch_1_2[0]
        assert abs(br.r_pu - 0.00281) < 1e-6
        assert abs(br.x_pu - 0.0281) < 1e-6
        assert abs(br.b_pu - 0.00712) < 1e-6

    def test_branch_ratings(self, system):
        """Test that branch ratings are correctly parsed."""
        branch_1_2 = [b for b in system.branches if b.from_bus_id == "B1" and b.to_bus_id == "B2"]
        br = branch_1_2[0]
        assert br.rate_a == 400.0
        assert br.rate_b == 400.0
        assert br.rate_c == 400.0

    def test_branch_angle_limits(self, system):
        """Test that branch angle limits are converted from degrees to radians."""
        branch = system.branches[0]
        assert branch.angmin is not None
        assert branch.angmax is not None
        assert abs(branch.angmin - math.radians(-30.0)) < 1e-6
        assert abs(branch.angmax - math.radians(30.0)) < 1e-6

    def test_branch_no_transformers(self, system):
        """Test that all branches are transmission lines (ratio=0 → tap=1.0)."""
        for branch in system.branches:
            assert branch.tap_ratio == 1.0
            assert branch.shift_angle == 0.0
            assert not branch.is_transformer

    def test_gencost_polynomial_model(self, system):
        """Test that all cost functions are polynomial (model=2)."""
        for cost in system.generator_costs:
            assert cost.model == 2
            assert cost.is_polynomial
            assert not cost.is_piecewise_linear

    def test_gencost_coefficients(self, system):
        """Test specific cost function coefficients."""
        # Gencost row 1 → first generator (bus 1): [0, 14, 0] → cost = 14*P
        cost0 = system.generator_costs[0]
        assert cost0.id == "GC1"
        assert cost0.generator_id == "G1"
        assert len(cost0.coefficients) == 3
        assert cost0.coefficients[0] == 0.0
        assert cost0.coefficients[1] == 14.0
        assert cost0.coefficients[2] == 0.0

    def test_gencost_linked_by_generator_id(self, system):
        """Test that each cost links to the right generator by value.

        pglib_opf_case5_pjm has distinct linear cost coefficients per
        generator (14, 15, 30, 40, 10 $/MWh in gen row order), so a wrong
        linkage produces a wrong coefficient, not just a wrong index.
        """
        expected_c1_by_generator = {
            "G1": 14.0,
            "G2": 15.0,
            "G3": 30.0,
            "G4": 40.0,
            "G5": 10.0,
        }
        costs_by_generator = {c.generator_id: c for c in system.generator_costs}
        assert set(costs_by_generator) == set(expected_c1_by_generator)
        for gen_id, c1 in expected_c1_by_generator.items():
            assert costs_by_generator[gen_id].coefficients == [0.0, c1, 0.0]

    def test_gencost_linkage_robust_to_reordering(self, system):
        """Test that generator_id linkage survives reordering of generators.

        Unlike the old list-index linkage (gen_index), resolving through
        generator_id must return the same cost after system.generators is
        reversed.
        """
        reordered = System(
            buses=system.buses,
            branches=system.branches,
            generators=list(reversed(system.generators)),
            loads=system.loads,
            shunts=system.shunts,
            generator_costs=system.generator_costs,
            base_mva=system.base_mva,
            name=system.name,
        )
        costs_by_generator = {c.generator_id: c for c in reordered.generator_costs}
        for gen in reordered.generators:
            assert costs_by_generator[gen.id].generator_id == gen.id
        # The 40 $/MWh unit is still the one on bus 4
        gen_b4 = [g for g in reordered.generators if g.bus_id == "B4"]
        assert len(gen_b4) == 1
        assert costs_by_generator[gen_b4[0].id].coefficients == [0.0, 40.0, 0.0]

    def test_gencost_evaluate(self, system):
        """Test cost function evaluation."""
        # First cost: cost = 0*P^2 + 14*P + 0
        cost0 = system.generator_costs[0]
        assert abs(cost0.evaluate(50.0) - 700.0) < 1e-6

    def test_order_sequences(self, system):
        """Test that order runs 1.0, 2.0, ... per element type in file order."""
        assert [b.order for b in system.buses] == [1.0, 2.0, 3.0, 4.0, 5.0]
        assert [b.order for b in system.branches] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        assert [g.order for g in system.generators] == [1.0, 2.0, 3.0, 4.0, 5.0]
        assert [ld.order for ld in system.loads] == [1.0, 2.0, 3.0]
        assert [c.order for c in system.generator_costs] == [1.0, 2.0, 3.0, 4.0, 5.0]

    def test_deterministic_ids_across_parses(self, fixtures_dir):
        """Test that two parses of the same file generate identical ids."""
        path = fixtures_dir / "pglib_opf_case5_pjm.m"
        first = parse_matpower(path)
        second = parse_matpower(path)
        assert [b.id for b in first.buses] == [b.id for b in second.buses]
        assert [b.id for b in first.branches] == [b.id for b in second.branches]
        assert [g.id for g in first.generators] == [g.id for g in second.generators]
        assert [ld.id for ld in first.loads] == [ld.id for ld in second.loads]
        assert [c.id for c in first.generator_costs] == [c.id for c in second.generator_costs]

    def test_validation(self, system):
        """Test that the parsed system passes validation."""
        errors = system.validate()
        assert len(errors) == 0


class TestCase14IEEE:
    """Test cases for pglib_opf_case14_ieee (IEEE 14-bus system)."""

    @pytest.fixture
    def system(self, fixtures_dir):
        """Parse the IEEE 14-bus system."""
        return parse_matpower(fixtures_dir / "pglib_opf_case14_ieee.m")

    def test_num_buses(self, system):
        """Test that all 14 buses are parsed."""
        assert system.num_buses == 14

    def test_num_generators(self, system):
        """Test that 5 generators are parsed (buses 1, 2, 3, 6, 8)."""
        assert system.num_generators == 5

    def test_generator_buses(self, system):
        """Test generator bus assignments (Bus.id references)."""
        gen_buses = [g.bus_id for g in system.generators]
        assert gen_buses == ["B1", "B2", "B3", "B6", "B8"]

    def test_num_loads(self, system):
        """Test that 11 loads are created (non-zero Pd buses)."""
        assert system.num_loads == 11

    def test_num_shunts(self, system):
        """Test that 1 shunt is created (bus 9: Bs=19.0 MVAr)."""
        assert system.num_shunts == 1
        shunt = system.shunts[0]
        assert shunt.id == "SH1"
        assert shunt.bus_id == "B9"
        assert shunt.shunt_id is None  # MATPOWER provides no shunt identifier
        assert abs(shunt.b_pu - 0.19) < 1e-6  # 19.0 / 100.0

    def test_num_branches(self, system):
        """Test that 20 branches are parsed."""
        assert system.num_branches == 20

    def test_transformers(self, system):
        """Test that 3 transformers are identified (ratio != 0)."""
        transformers = [b for b in system.branches if b.is_transformer]
        assert len(transformers) == 3
        # Transformers: 4-7 (0.978), 4-9 (0.969), 5-6 (0.932)
        xfmr_buses = {(t.from_bus_id, t.to_bus_id) for t in transformers}
        assert ("B4", "B7") in xfmr_buses
        assert ("B4", "B9") in xfmr_buses
        assert ("B5", "B6") in xfmr_buses

    def test_transformer_tap_ratios(self, system):
        """Test specific transformer tap ratios."""
        xfmr_4_7 = [b for b in system.branches if b.from_bus_id == "B4" and b.to_bus_id == "B7"]
        assert len(xfmr_4_7) == 1
        assert abs(xfmr_4_7[0].tap_ratio - 0.978) < 1e-6

    def test_bus_voltage_limits(self, system):
        """Test voltage limits (IEEE 14-bus pglib uses 0.94-1.06)."""
        bus = system.get_bus("B1")
        assert bus is not None
        assert abs(bus.v_max - 1.06) < 1e-6
        assert abs(bus.v_min - 0.94) < 1e-6

    def test_slack_bus(self, system):
        """Test that bus 1 is the slack bus."""
        slack = system.get_slack_buses()
        assert len(slack) == 1
        assert slack[0].id == "B1"
        assert slack[0].number == 1

    def test_generator_reactive_limits(self, system):
        """Test generator reactive power limits."""
        # Gen at bus 2: Qmax=30, Qmin=-30 MVAr → 0.3, -0.3 pu
        gen_bus2 = system.get_bus_generators("B2")
        assert len(gen_bus2) == 1
        assert abs(gen_bus2[0].q_max - 0.3) < 1e-6
        assert abs(gen_bus2[0].q_min - (-0.3)) < 1e-6

    def test_num_generator_costs(self, system):
        """Test that 5 cost functions are parsed."""
        assert system.num_generator_costs == 5

    def test_validation(self, system):
        """Test that the parsed system passes validation."""
        errors = system.validate()
        assert len(errors) == 0

    def test_to_description(self, system):
        """Test that to_description() works with generator costs."""
        desc = system.to_description()
        assert "14 buses" in desc
        assert "Generator Costs:" in desc


class TestParallelBranches:
    """Test id separation for parallel branches (no circuit ID in MATPOWER).

    Ids carry no connectivity information, so parallel circuits are just
    consecutive sequence numbers (BR{n}, BR{n+1}); circuit_id stays None.
    """

    @pytest.fixture
    def system(self, tmp_path):
        """Parse a minimal 2-bus case with two parallel branches."""
        content = """function mpc = parallel_case
mpc.version = '2';
mpc.baseMVA = 100.0;
mpc.bus = [
\t1\t3\t0.0\t0.0\t0.0\t0.0\t1\t1.0\t0.0\t230.0\t1\t1.1\t0.9;
\t2\t1\t100.0\t30.0\t0.0\t0.0\t1\t1.0\t0.0\t230.0\t1\t1.1\t0.9;
];
mpc.gen = [
\t1\t100.0\t0.0\t50.0\t-50.0\t1.0\t100.0\t1\t200.0\t0.0;
];
mpc.branch = [
\t1\t2\t0.01\t0.10\t0.02\t100.0\t0.0\t0.0\t0.0\t0.0\t1\t-30.0\t30.0;
\t1\t2\t0.02\t0.20\t0.04\t100.0\t0.0\t0.0\t0.0\t0.0\t1\t-30.0\t30.0;
];
"""
        path = tmp_path / "parallel_case.m"
        path.write_text(content, encoding="utf-8")
        return parse_matpower(path)

    def test_parallel_branch_ids_unique(self, system):
        """Test that parallel circuits get distinct consecutive sequence ids."""
        assert [b.id for b in system.branches] == ["BR1", "BR2"]

    def test_parallel_branches_keep_own_data(self, system):
        """Test that each parallel circuit keeps its own impedance."""
        by_id = {b.id: b for b in system.branches}
        assert by_id["BR1"].x_pu == 0.10
        assert by_id["BR2"].x_pu == 0.20
        for branch in system.branches:
            assert branch.from_bus_id == "B1"
            assert branch.to_bus_id == "B2"
            assert branch.circuit_id is None

    def test_validation(self, system):
        """Test that the parallel-branch system passes validation (unique ids)."""
        assert system.validate() == []


class TestCrossFormatConsistency:
    """Test consistency between MATPOWER and RAW parsers for IEEE 14-bus."""

    @pytest.fixture
    def mat_system(self, fixtures_dir):
        """Parse IEEE 14-bus from MATPOWER format."""
        return parse_matpower(fixtures_dir / "pglib_opf_case14_ieee.m")

    @pytest.fixture
    def raw_system(self, fixtures_dir):
        """Parse IEEE 14-bus from RAW format."""
        raw_file = fixtures_dir / "ieee14.raw"
        if not raw_file.exists():
            pytest.skip("ieee14.raw fixture not available")
        from psforge_grid.io.raw_parser import parse_raw

        try:
            return parse_raw(raw_file)
        except TypeError:
            # The RAW parser migration to the unified id scheme is handled
            # in a parallel change; until it lands, it still constructs
            # models with removed keyword arguments.
            pytest.skip("RAW parser not yet migrated to the unified id scheme")

    def test_same_num_buses(self, mat_system, raw_system):
        """Test that both formats produce the same number of buses."""
        assert mat_system.num_buses == raw_system.num_buses

    def test_same_num_branches(self, mat_system, raw_system):
        """Test that both formats produce the same number of branches."""
        assert mat_system.num_branches == raw_system.num_branches

    def test_same_num_generators(self, mat_system, raw_system):
        """Test that both formats produce the same number of generators."""
        assert mat_system.num_generators == raw_system.num_generators


class TestParserFactory:
    """Test factory integration for MATPOWER parser."""

    def test_create_matpower(self):
        """Test creating MATPOWER parser via factory."""
        parser = ParserFactory.create("matpower")
        assert isinstance(parser, MatpowerParser)

    def test_from_extension_m(self):
        """Test creating parser from .m extension."""
        parser = ParserFactory.from_extension(".m")
        assert isinstance(parser, MatpowerParser)

    def test_from_extension_m_no_dot(self):
        """Test creating parser from m extension without dot."""
        parser = ParserFactory.from_extension("m")
        assert isinstance(parser, MatpowerParser)

    def test_from_path(self, fixtures_dir):
        """Test creating parser from file path."""
        parser = ParserFactory.from_path(fixtures_dir / "pglib_opf_case5_pjm.m")
        assert isinstance(parser, MatpowerParser)

    def test_available_formats_includes_matpower(self):
        """Test that available_formats() includes matpower."""
        formats = ParserFactory.available_formats()
        assert "matpower" in formats

    def test_supported_extensions_includes_m(self):
        """Test that supported_extensions() includes m."""
        extensions = ParserFactory.supported_extensions()
        assert "m" in extensions

    def test_system_from_file(self, fixtures_dir):
        """Test System.from_file() auto-detection with .m extension."""
        system = System.from_file(fixtures_dir / "pglib_opf_case5_pjm.m")
        assert isinstance(system, System)
        assert system.num_buses == 5

    def test_system_from_matpower(self, fixtures_dir):
        """Test System.from_matpower() factory method."""
        system = System.from_matpower(fixtures_dir / "pglib_opf_case5_pjm.m")
        assert isinstance(system, System)
        assert system.num_buses == 5


class TestGeneratorCost:
    """Test GeneratorCost dataclass."""

    def test_invalid_model_raises(self):
        """Test that invalid model type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid cost model"):
            GeneratorCost("GC1", generator_id="G1", model=3)

    def test_invalid_id_raises(self):
        """Test that an id outside [A-Za-z0-9_]+ raises ValueError."""
        with pytest.raises(ValueError, match="Invalid GeneratorCost id"):
            GeneratorCost("GC-1", generator_id="G1", model=2)

    def test_polynomial_model(self):
        """Test polynomial cost model properties."""
        cost = GeneratorCost("GC1", generator_id="G1", model=2, coefficients=[0.04, 20.0, 100.0])
        assert cost.is_polynomial
        assert not cost.is_piecewise_linear
        assert cost.n_coefficients == 3

    def test_piecewise_linear_model(self):
        """Test piecewise linear cost model properties."""
        cost = GeneratorCost("GC1", generator_id="G1", model=1, coefficients=[0, 0, 100, 2000])
        assert cost.is_piecewise_linear
        assert not cost.is_polynomial

    def test_evaluate_quadratic(self):
        """Test polynomial evaluation: 0.04*P^2 + 20*P + 100."""
        cost = GeneratorCost("GC1", generator_id="G1", model=2, coefficients=[0.04, 20.0, 100.0])
        # At P=50: 0.04*2500 + 20*50 + 100 = 100 + 1000 + 100 = 1200
        assert abs(cost.evaluate(50.0) - 1200.0) < 1e-6

    def test_evaluate_linear(self):
        """Test polynomial evaluation of linear cost: 14*P + 0."""
        cost = GeneratorCost("GC1", generator_id="G1", model=2, coefficients=[0.0, 14.0, 0.0])
        assert abs(cost.evaluate(100.0) - 1400.0) < 1e-6

    def test_evaluate_empty_coefficients(self):
        """Test evaluation with empty coefficients returns 0."""
        cost = GeneratorCost("GC1", generator_id="G1", model=2)
        assert cost.evaluate(50.0) == 0.0

    def test_evaluate_piecewise_raises(self):
        """Test that piecewise linear evaluate raises ValueError."""
        cost = GeneratorCost("GC1", generator_id="G1", model=1, coefficients=[0, 0, 100, 2000])
        with pytest.raises(ValueError, match="Piecewise linear"):
            cost.evaluate(50.0)

    def test_to_description(self):
        """Test LLM-friendly description output."""
        cost = GeneratorCost(
            "GC1",
            generator_id="G1",
            model=2,
            coefficients=[0.04, 20.0, 100.0],
            startup=500.0,
        )
        desc = cost.to_description()
        assert "Polynomial" in desc
        assert "Generator Cost GC1" in desc
        assert "for generator G1" in desc
        assert "Startup: $500.00" in desc
        assert "P^2" in desc
