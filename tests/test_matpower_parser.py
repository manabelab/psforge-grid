"""Tests for MATPOWER file parser.

Tests the parsing functionality for MATPOWER format (.m) files,
including pglib-opf benchmark cases.
"""

import math
from pathlib import Path

import pytest

from psforge_grid.io.factories import ParserFactory
from psforge_grid.io.matpower_parser import MatpowerParser, parse_matpower
from psforge_grid.models.generator_cost import GeneratorCost
from psforge_grid.models.system import System


@pytest.fixture
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


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
        assert system.num_buses() == 5


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
        assert system.num_buses() == 5

    def test_num_generators(self, system):
        """Test that all 5 generators are parsed."""
        assert system.num_generators() == 5

    def test_num_loads(self, system):
        """Test that 3 loads are created (buses 2, 3, 4 have non-zero Pd)."""
        assert system.num_loads() == 3

    def test_num_branches(self, system):
        """Test that all 6 branches are parsed."""
        assert system.num_branches() == 6

    def test_num_shunts(self, system):
        """Test that no shunts exist (all Gs=Bs=0)."""
        assert system.num_shunts() == 0

    def test_num_generator_costs(self, system):
        """Test that 5 cost functions are parsed."""
        assert system.num_generator_costs() == 5

    def test_bus_types(self, system):
        """Test bus type assignments."""
        bus_types = {b.bus_id: b.bus_type for b in system.buses}
        assert bus_types[1] == 2  # PV
        assert bus_types[2] == 1  # PQ
        assert bus_types[3] == 2  # PV
        assert bus_types[4] == 3  # Slack
        assert bus_types[5] == 2  # PV

    def test_bus_voltage_limits(self, system):
        """Test bus voltage limits."""
        bus = system.get_bus(1)
        assert bus is not None
        assert bus.v_max == 1.1
        assert bus.v_min == 0.9

    def test_bus_base_kv(self, system):
        """Test bus base voltage."""
        for bus in system.buses:
            assert bus.base_kv == 230.0

    def test_load_pu_conversion(self, system):
        """Test that load values are correctly converted to per-unit."""
        # Bus 2: Pd=300 MW, Qd=98.61 MVAr on 100 MVA base
        bus2_loads = system.get_bus_loads(2)
        assert len(bus2_loads) == 1
        assert abs(bus2_loads[0].p_load - 3.0) < 1e-6
        assert abs(bus2_loads[0].q_load - 0.9861) < 1e-4

    def test_generator_pu_conversion(self, system):
        """Test that generator values are correctly converted to per-unit."""
        # Gen at bus 1 (first): Pg=20 MW, Pmax=40 MW on 100 MVA base
        bus1_gens = system.get_bus_generators(1)
        assert len(bus1_gens) == 2
        gen1 = bus1_gens[0]
        assert abs(gen1.p_gen - 0.2) < 1e-6
        assert abs(gen1.p_max - 0.4) < 1e-6
        assert abs(gen1.p_min - 0.0) < 1e-6

    def test_multiple_generators_same_bus(self, system):
        """Test that multiple generators on bus 1 get unique gen_ids."""
        bus1_gens = system.get_bus_generators(1)
        assert len(bus1_gens) == 2
        gen_ids = {g.gen_id for g in bus1_gens}
        assert gen_ids == {"1", "2"}

    def test_branch_impedance(self, system):
        """Test branch impedance values (already in per-unit)."""
        # Branch 1-2: r=0.00281, x=0.0281, b=0.00712
        branch_1_2 = [b for b in system.branches if b.from_bus == 1 and b.to_bus == 2]
        assert len(branch_1_2) == 1
        br = branch_1_2[0]
        assert abs(br.r_pu - 0.00281) < 1e-6
        assert abs(br.x_pu - 0.0281) < 1e-6
        assert abs(br.b_pu - 0.00712) < 1e-6

    def test_branch_ratings(self, system):
        """Test that branch ratings are correctly parsed."""
        branch_1_2 = [b for b in system.branches if b.from_bus == 1 and b.to_bus == 2]
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
        # Gen 0 (bus 1, first): [0, 14, 0] → cost = 14*P
        cost0 = system.generator_costs[0]
        assert cost0.gen_index == 0
        assert len(cost0.coefficients) == 3
        assert cost0.coefficients[0] == 0.0
        assert cost0.coefficients[1] == 14.0
        assert cost0.coefficients[2] == 0.0

    def test_gencost_evaluate(self, system):
        """Test cost function evaluation."""
        # Gen 0: cost = 0*P^2 + 14*P + 0
        cost0 = system.generator_costs[0]
        assert abs(cost0.evaluate(50.0) - 700.0) < 1e-6

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
        assert system.num_buses() == 14

    def test_num_generators(self, system):
        """Test that 5 generators are parsed (buses 1, 2, 3, 6, 8)."""
        assert system.num_generators() == 5

    def test_generator_buses(self, system):
        """Test generator bus assignments."""
        gen_buses = [g.bus_id for g in system.generators]
        assert gen_buses == [1, 2, 3, 6, 8]

    def test_num_loads(self, system):
        """Test that 11 loads are created (non-zero Pd buses)."""
        assert system.num_loads() == 11

    def test_num_shunts(self, system):
        """Test that 1 shunt is created (bus 9: Bs=19.0 MVAr)."""
        assert system.num_shunts() == 1
        shunt = system.shunts[0]
        assert shunt.bus_id == 9
        assert abs(shunt.b_pu - 0.19) < 1e-6  # 19.0 / 100.0

    def test_num_branches(self, system):
        """Test that 20 branches are parsed."""
        assert system.num_branches() == 20

    def test_transformers(self, system):
        """Test that 3 transformers are identified (ratio != 0)."""
        transformers = [b for b in system.branches if b.is_transformer]
        assert len(transformers) == 3
        # Transformers: 4-7 (0.978), 4-9 (0.969), 5-6 (0.932)
        xfmr_buses = {(t.from_bus, t.to_bus) for t in transformers}
        assert (4, 7) in xfmr_buses
        assert (4, 9) in xfmr_buses
        assert (5, 6) in xfmr_buses

    def test_transformer_tap_ratios(self, system):
        """Test specific transformer tap ratios."""
        xfmr_4_7 = [b for b in system.branches if b.from_bus == 4 and b.to_bus == 7]
        assert len(xfmr_4_7) == 1
        assert abs(xfmr_4_7[0].tap_ratio - 0.978) < 1e-6

    def test_bus_voltage_limits(self, system):
        """Test voltage limits (IEEE 14-bus pglib uses 0.94-1.06)."""
        bus = system.get_bus(1)
        assert bus is not None
        assert abs(bus.v_max - 1.06) < 1e-6
        assert abs(bus.v_min - 0.94) < 1e-6

    def test_slack_bus(self, system):
        """Test that bus 1 is the slack bus."""
        slack = system.get_slack_buses()
        assert len(slack) == 1
        assert slack[0].bus_id == 1

    def test_generator_reactive_limits(self, system):
        """Test generator reactive power limits."""
        # Gen at bus 2: Qmax=30, Qmin=-30 MVAr → 0.3, -0.3 pu
        gen_bus2 = system.get_bus_generators(2)
        assert len(gen_bus2) == 1
        assert abs(gen_bus2[0].q_max - 0.3) < 1e-6
        assert abs(gen_bus2[0].q_min - (-0.3)) < 1e-6

    def test_num_generator_costs(self, system):
        """Test that 5 cost functions are parsed."""
        assert system.num_generator_costs() == 5

    def test_validation(self, system):
        """Test that the parsed system passes validation."""
        errors = system.validate()
        assert len(errors) == 0

    def test_to_description(self, system):
        """Test that to_description() works with generator costs."""
        desc = system.to_description()
        assert "14 buses" in desc
        assert "Generator Costs:" in desc


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

        return parse_raw(raw_file)

    def test_same_num_buses(self, mat_system, raw_system):
        """Test that both formats produce the same number of buses."""
        assert mat_system.num_buses() == raw_system.num_buses()

    def test_same_num_branches(self, mat_system, raw_system):
        """Test that both formats produce the same number of branches."""
        assert mat_system.num_branches() == raw_system.num_branches()

    def test_same_num_generators(self, mat_system, raw_system):
        """Test that both formats produce the same number of generators."""
        assert mat_system.num_generators() == raw_system.num_generators()


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
        assert system.num_buses() == 5

    def test_system_from_matpower(self, fixtures_dir):
        """Test System.from_matpower() factory method."""
        system = System.from_matpower(fixtures_dir / "pglib_opf_case5_pjm.m")
        assert isinstance(system, System)
        assert system.num_buses() == 5


class TestGeneratorCost:
    """Test GeneratorCost dataclass."""

    def test_invalid_model_raises(self):
        """Test that invalid model type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid cost model"):
            GeneratorCost(gen_index=0, model=3)

    def test_polynomial_model(self):
        """Test polynomial cost model properties."""
        cost = GeneratorCost(gen_index=0, model=2, coefficients=[0.04, 20.0, 100.0])
        assert cost.is_polynomial
        assert not cost.is_piecewise_linear
        assert cost.n_coefficients == 3

    def test_piecewise_linear_model(self):
        """Test piecewise linear cost model properties."""
        cost = GeneratorCost(gen_index=0, model=1, coefficients=[0, 0, 100, 2000])
        assert cost.is_piecewise_linear
        assert not cost.is_polynomial

    def test_evaluate_quadratic(self):
        """Test polynomial evaluation: 0.04*P^2 + 20*P + 100."""
        cost = GeneratorCost(gen_index=0, model=2, coefficients=[0.04, 20.0, 100.0])
        # At P=50: 0.04*2500 + 20*50 + 100 = 100 + 1000 + 100 = 1200
        assert abs(cost.evaluate(50.0) - 1200.0) < 1e-6

    def test_evaluate_linear(self):
        """Test polynomial evaluation of linear cost: 14*P + 0."""
        cost = GeneratorCost(gen_index=0, model=2, coefficients=[0.0, 14.0, 0.0])
        assert abs(cost.evaluate(100.0) - 1400.0) < 1e-6

    def test_evaluate_empty_coefficients(self):
        """Test evaluation with empty coefficients returns 0."""
        cost = GeneratorCost(gen_index=0, model=2)
        assert cost.evaluate(50.0) == 0.0

    def test_evaluate_piecewise_raises(self):
        """Test that piecewise linear evaluate raises ValueError."""
        cost = GeneratorCost(gen_index=0, model=1, coefficients=[0, 0, 100, 2000])
        with pytest.raises(ValueError, match="Piecewise linear"):
            cost.evaluate(50.0)

    def test_to_description(self):
        """Test LLM-friendly description output."""
        cost = GeneratorCost(gen_index=0, model=2, coefficients=[0.04, 20.0, 100.0], startup=500.0)
        desc = cost.to_description()
        assert "Polynomial" in desc
        assert "gen_index=0" in desc
        assert "Startup: $500.00" in desc
        assert "P^2" in desc
