"""Tests for power system data models.

Tests the fundamental data classes: Bus, Branch, Generator, Load, Shunt,
GeneratorCost, and System, including the unified string-identifier scheme
(``id``, ``order``, ``tags``, system-wide uniqueness).
"""

import pytest

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.diagram import (
    BranchRoute,
    BusPosition,
    DiagramData,
    DiagramLabel,
)
from psforge_grid.models.generator import Generator
from psforge_grid.models.generator_cost import GeneratorCost
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt
from psforge_grid.models.system import System


class TestBus:
    """Test cases for Bus class."""

    def test_bus_creation(self):
        """Test that a Bus object can be created with valid parameters."""
        bus = Bus("B1", bus_type=3, v_magnitude=1.05, base_kv=138.0, number=1, name="Bus1")
        assert bus.id == "B1"
        assert bus.bus_type == 3
        assert bus.v_magnitude == 1.05
        assert bus.base_kv == 138.0
        assert bus.number == 1
        assert bus.name == "Bus1"

    def test_bus_default_values(self):
        """Test that Bus uses correct default values."""
        bus = Bus("B1", bus_type=1)
        assert bus.v_magnitude == 1.0
        assert bus.v_angle == 0.0
        assert bus.base_kv == 1.0
        assert bus.area == 1
        assert bus.zone == 1
        assert bus.v_max == 1.1
        assert bus.v_min == 0.9
        assert bus.number is None
        assert bus.order is None
        assert bus.tags == []
        assert bus.name is None

    def test_bus_invalid_type(self):
        """Test that invalid bus_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid bus_type"):
            Bus("B1", bus_type=5)

        with pytest.raises(ValueError, match="Invalid bus_type"):
            Bus("B1", bus_type=0)

    def test_bus_invalid_id_characters(self):
        """Ids outside [A-Za-z0-9_]+ are rejected at construction."""
        with pytest.raises(ValueError, match="Invalid Bus id"):
            Bus("B-1", bus_type=1)  # hyphen not allowed

        with pytest.raises(ValueError, match="Invalid Bus id"):
            Bus("", bus_type=1)  # empty id not allowed

        with pytest.raises(ValueError, match="Invalid Bus id"):
            Bus("母線1", bus_type=1)  # non-ASCII not allowed

    def test_bus_types(self):
        """Test all valid bus types."""
        bus_pq = Bus("B1", bus_type=1)  # PQ bus
        bus_pv = Bus("B2", bus_type=2)  # PV bus
        bus_slack = Bus("B3", bus_type=3)  # Slack bus
        bus_isolated = Bus("B4", bus_type=4)  # Isolated bus

        assert bus_pq.bus_type == 1
        assert bus_pv.bus_type == 2
        assert bus_slack.bus_type == 3
        assert bus_isolated.bus_type == 4

    def test_bus_type_properties(self):
        """Test bus type convenience properties."""
        bus_pq = Bus("B1", bus_type=1)
        bus_pv = Bus("B2", bus_type=2)
        bus_slack = Bus("B3", bus_type=3)
        bus_isolated = Bus("B4", bus_type=4)

        assert bus_pq.is_pq is True
        assert bus_pq.is_pv is False
        assert bus_pv.is_pv is True
        assert bus_slack.is_slack is True
        assert bus_isolated.is_isolated is True

    def test_bus_with_area_zone(self):
        """Test bus with area and zone."""
        bus = Bus("B1", bus_type=1, area=2, zone=3)
        assert bus.area == 2
        assert bus.zone == 3

    def test_bus_tags_and_order_are_preserved(self):
        """tags and order fields hold the values given at construction."""
        bus = Bus("B1", bus_type=1, order=1.5, tags=["area:kansai", "voltage:500kV"])
        assert bus.order == 1.5
        assert bus.tags == ["area:kansai", "voltage:500kV"]

    def test_bus_tags_default_is_independent(self):
        """The default tags list is per-instance, not shared."""
        bus_a = Bus("B1", bus_type=1)
        bus_b = Bus("B2", bus_type=1)
        bus_a.tags.append("area:kansai")
        assert bus_a.tags == ["area:kansai"]
        assert bus_b.tags == []


class TestBranch:
    """Test cases for Branch class."""

    def test_branch_creation(self):
        """Test that a Branch object can be created with valid parameters."""
        branch = Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, b_pu=0.02, rate_a=100.0)
        assert branch.id == "BR1"
        assert branch.from_bus_id == "B1"
        assert branch.to_bus_id == "B2"
        assert branch.r_pu == 0.01
        assert branch.x_pu == 0.1
        assert branch.b_pu == 0.02
        assert branch.rate_a == 100.0

    def test_branch_default_values(self):
        """Test that Branch uses correct default values."""
        branch = Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)
        assert branch.b_pu == 0.0
        assert branch.tap_ratio == 1.0
        assert branch.shift_angle == 0.0
        assert branch.rate_a is None
        assert branch.rate_b is None
        assert branch.rate_c is None
        assert branch.status == 1
        assert branch.circuit_id is None
        assert branch.order is None
        assert branch.tags == []
        assert branch.name is None

    def test_branch_invalid_id_characters(self):
        """Ids outside [A-Za-z0-9_]+ are rejected at construction."""
        with pytest.raises(ValueError, match="Invalid Branch id"):
            Branch("BR-1", "B1", "B2", r_pu=0.01, x_pu=0.1)  # hyphen

        with pytest.raises(ValueError, match="Invalid Branch id"):
            Branch("", "B1", "B2", r_pu=0.01, x_pu=0.1)  # empty

        with pytest.raises(ValueError, match="Invalid Branch id"):
            Branch("線路1", "B1", "B2", r_pu=0.01, x_pu=0.1)  # non-ASCII

    def test_branch_circuit_id_is_preserved(self):
        """circuit_id keeps the source-format key for lossless round-trip."""
        branch = Branch("BR2", "B1", "B2", r_pu=0.01, x_pu=0.1, circuit_id="2")
        assert branch.circuit_id == "2"

    def test_branch_transformer(self):
        """Test transformer with non-unity tap ratio."""
        transformer = Branch("BR1", "B1", "B2", r_pu=0.001, x_pu=0.05, tap_ratio=1.05)
        assert transformer.tap_ratio == 1.05
        assert transformer.is_transformer is True

    def test_branch_is_transformer_property(self):
        """Test is_transformer property."""
        line = Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)
        xfmr_tap = Branch("BR2", "B1", "B2", r_pu=0.0, x_pu=0.05, tap_ratio=1.02)
        xfmr_shift = Branch("BR3", "B1", "B2", r_pu=0.0, x_pu=0.05, shift_angle=0.1)

        assert line.is_transformer is False
        assert xfmr_tap.is_transformer is True
        assert xfmr_shift.is_transformer is True

    def test_branch_is_xfmr_flag(self):
        """Test is_xfmr explicit transformer flag.

        When is_xfmr=True, is_transformer returns True even if tap_ratio=1.0
        and shift_angle=0.0. This covers step-up transformers in PSS/E RAW
        format where tap ratios are on system base (WINDV1/WINDV2=1.0).
        """
        # is_xfmr=None (default): behaves like before
        line_default = Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)
        assert line_default.is_xfmr is None
        assert line_default.is_transformer is False

        # is_xfmr=True with unity tap: still a transformer
        xfmr_unity_tap = Branch("BR2", "B1", "B2", r_pu=0.0, x_pu=0.05, tap_ratio=1.0, is_xfmr=True)
        assert xfmr_unity_tap.is_xfmr is True
        assert xfmr_unity_tap.is_transformer is True

        # is_xfmr=False with unity tap: not a transformer
        line_explicit = Branch("BR3", "B1", "B2", r_pu=0.01, x_pu=0.1, is_xfmr=False)
        assert line_explicit.is_transformer is False

        # is_xfmr=False but non-unity tap: still a transformer (tap overrides)
        xfmr_tap_override = Branch(
            "BR4", "B1", "B2", r_pu=0.0, x_pu=0.05, tap_ratio=1.05, is_xfmr=False
        )
        assert xfmr_tap_override.is_transformer is True

    def test_branch_is_xfmr_branch_type_name(self):
        """Test branch_type_name with is_xfmr flag."""
        xfmr = Branch("BR1", "B1", "B2", r_pu=0.0, x_pu=0.05, is_xfmr=True)
        assert xfmr.branch_type_name == "Transformer"

        line = Branch("BR2", "B1", "B2", r_pu=0.01, x_pu=0.1)
        assert line.branch_type_name == "Transmission Line"

    def test_branch_status(self):
        """Test branch status."""
        branch_in = Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, status=1)
        branch_out = Branch("BR2", "B1", "B2", r_pu=0.01, x_pu=0.1, status=0)

        assert branch_in.is_in_service is True
        assert branch_out.is_in_service is False

    def test_branch_invalid_status(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, status=2)

    def test_branch_zero_tap_ratio(self):
        """Test that zero tap_ratio raises ValueError."""
        with pytest.raises(ValueError, match="tap_ratio cannot be zero"):
            Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, tap_ratio=0.0)


class TestGenerator:
    """Test cases for Generator class."""

    def test_generator_creation(self):
        """Test that a Generator object can be created with valid parameters."""
        gen = Generator("G1", bus_id="B1", p_gen=1.0, v_setpoint=1.05, p_max=1.5, p_min=0.0)
        assert gen.id == "G1"
        assert gen.bus_id == "B1"
        assert gen.p_gen == 1.0
        assert gen.v_setpoint == 1.05
        assert gen.p_max == 1.5
        assert gen.p_min == 0.0

    def test_generator_default_values(self):
        """Test that Generator uses correct default values."""
        gen = Generator("G1", bus_id="B1", p_gen=1.0)
        assert gen.q_gen == 0.0
        assert gen.v_setpoint == 1.0
        assert gen.p_max is None
        assert gen.p_min is None
        assert gen.q_max is None
        assert gen.q_min is None
        assert gen.mbase == 100.0
        assert gen.status == 1
        assert gen.machine_id is None
        assert gen.order is None
        assert gen.tags == []
        assert gen.name is None

    def test_generator_machine_id_is_preserved(self):
        """machine_id keeps the source-format key for lossless round-trip."""
        gen = Generator("G2", bus_id="B1", p_gen=1.0, machine_id="2")
        assert gen.machine_id == "2"

    def test_generator_tags_and_order_are_preserved(self):
        """tags and order fields hold the values given at construction."""
        gen = Generator("G1", bus_id="B1", p_gen=1.0, order=3.0, tags=["facility:shin_osaka"])
        assert gen.order == 3.0
        assert gen.tags == ["facility:shin_osaka"]

    def test_generator_status(self):
        """Test generator status."""
        gen_in = Generator("G1", bus_id="B1", p_gen=1.0, status=1)
        gen_out = Generator("G2", bus_id="B1", p_gen=1.0, status=0)

        assert gen_in.is_in_service is True
        assert gen_out.is_in_service is False

    def test_generator_invalid_status(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            Generator("G1", bus_id="B1", p_gen=1.0, status=2)

    def test_generator_q_limits(self):
        """Test Q limit checking."""
        gen = Generator("G1", bus_id="B1", p_gen=1.0, q_max=0.5, q_min=-0.3)

        # Within limits
        within, val = gen.check_q_limits(0.2)
        assert within is True
        assert val == 0.2

        # Above max
        within, val = gen.check_q_limits(0.8)
        assert within is False
        assert val == 0.5

        # Below min
        within, val = gen.check_q_limits(-0.5)
        assert within is False
        assert val == -0.3


class TestLoad:
    """Test cases for Load class."""

    def test_load_creation(self):
        """Test that a Load object can be created."""
        load = Load("LD1", bus_id="B2", p_load=0.5, q_load=0.2, name="Load1")
        assert load.id == "LD1"
        assert load.bus_id == "B2"
        assert load.p_load == 0.5
        assert load.q_load == 0.2
        assert load.name == "Load1"

    def test_load_default_values(self):
        """Test that Load uses correct default values."""
        load = Load("LD1", bus_id="B2", p_load=0.5)
        assert load.q_load == 0.0
        assert load.status == 1
        assert load.load_id is None
        assert load.order is None
        assert load.tags == []
        assert load.name is None

    def test_load_status(self):
        """Test load status."""
        load_in = Load("LD1", bus_id="B2", p_load=0.5, status=1)
        load_out = Load("LD2", bus_id="B2", p_load=0.5, status=0)

        assert load_in.is_in_service is True
        assert load_out.is_in_service is False

    def test_load_invalid_status(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            Load("LD1", bus_id="B2", p_load=0.5, status=2)

    def test_load_apparent_power(self):
        """Test apparent power calculation."""
        load = Load("LD1", bus_id="B2", p_load=0.3, q_load=0.4)
        assert load.apparent_power == pytest.approx(0.5)

    def test_load_power_factor(self):
        """Test power factor calculation."""
        load = Load("LD1", bus_id="B2", p_load=0.8, q_load=0.6)
        assert load.power_factor == pytest.approx(0.8)

        # Zero load
        zero_load = Load("LD2", bus_id="B2", p_load=0.0, q_load=0.0)
        assert zero_load.power_factor == 1.0


class TestShunt:
    """Test cases for Shunt class."""

    def test_shunt_creation(self):
        """Test that a Shunt object can be created."""
        shunt = Shunt("SH1", bus_id="B1", g_pu=0.01, b_pu=0.5, name="Cap1")
        assert shunt.id == "SH1"
        assert shunt.bus_id == "B1"
        assert shunt.g_pu == 0.01
        assert shunt.b_pu == 0.5
        assert shunt.name == "Cap1"

    def test_shunt_default_values(self):
        """Test that Shunt uses correct default values."""
        shunt = Shunt("SH1", bus_id="B1")
        assert shunt.g_pu == 0.0
        assert shunt.b_pu == 0.0
        assert shunt.status == 1
        assert shunt.shunt_id is None
        assert shunt.order is None
        assert shunt.tags == []
        assert shunt.name is None

    def test_shunt_capacitor(self):
        """Test capacitor (positive B)."""
        cap = Shunt("SH1", bus_id="B1", b_pu=0.5)
        assert cap.b_pu > 0  # Capacitor: positive susceptance

    def test_shunt_reactor(self):
        """Test reactor (negative B)."""
        reactor = Shunt("SH1", bus_id="B1", b_pu=-0.3)
        assert reactor.b_pu < 0  # Reactor: negative susceptance

    def test_shunt_invalid_status(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            Shunt("SH1", bus_id="B1", status=2)


class TestGeneratorCost:
    """Test cases for GeneratorCost class."""

    def test_generator_cost_creation(self):
        """GeneratorCost references its generator by id, not list index."""
        cost = GeneratorCost("GC1", generator_id="G1", model=2, coefficients=[0.04, 20.0, 100.0])
        assert cost.id == "GC1"
        assert cost.generator_id == "G1"
        assert cost.model == 2
        assert cost.coefficients == [0.04, 20.0, 100.0]

    def test_generator_cost_default_values(self):
        """Test that GeneratorCost uses correct default values."""
        cost = GeneratorCost("GC1", generator_id="G1", model=2)
        assert cost.startup == 0.0
        assert cost.shutdown == 0.0
        assert cost.coefficients == []
        assert cost.order is None
        assert cost.tags == []
        assert cost.name is None

    def test_generator_cost_invalid_id_characters(self):
        """Ids outside [A-Za-z0-9_]+ are rejected at construction."""
        with pytest.raises(ValueError, match="Invalid GeneratorCost id"):
            GeneratorCost("GC-1", generator_id="G1", model=2)

    def test_generator_cost_evaluate_polynomial(self):
        """Quadratic cost 0.04*P^2 + 20*P + 100 evaluated at 50 MW."""
        cost = GeneratorCost("GC1", generator_id="G1", model=2, coefficients=[0.04, 20.0, 100.0])
        assert cost.evaluate(50.0) == pytest.approx(1200.0)


class TestSystem:
    """Test cases for System class."""

    def test_system_creation(self):
        """Test that a System object can be created with components."""
        bus1 = Bus("B1", bus_type=3)
        bus2 = Bus("B2", bus_type=1)
        branch = Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)
        gen = Generator("G1", bus_id="B1", p_gen=1.0)
        load = Load("LD1", bus_id="B2", p_load=0.8)
        shunt = Shunt("SH1", bus_id="B2", b_pu=0.1)

        system = System(
            buses=[bus1, bus2],
            branches=[branch],
            generators=[gen],
            loads=[load],
            shunts=[shunt],
            base_mva=100.0,
        )

        assert system.num_buses == 2
        assert system.num_branches == 1
        assert system.num_generators == 1
        assert system.num_loads == 1
        assert system.num_shunts == 1
        assert system.base_mva == 100.0

    def test_system_default_values(self):
        """Test that System uses correct default values."""
        system = System()
        assert system.num_buses == 0
        assert system.num_branches == 0
        assert system.num_generators == 0
        assert system.num_loads == 0
        assert system.num_shunts == 0
        assert system.base_mva == 100.0
        assert system.name == ""
        assert system.id is None
        assert system.order is None
        assert system.tags == []
        assert system.case_time is None

    def test_system_identity_fields_are_preserved(self):
        """id/order/tags/case_time hold the values given at construction."""
        system = System(
            id="west10_2030peak",
            order=2.0,
            tags=["area:west", "study:2030peak"],
            case_time="2026-08",
        )
        assert system.id == "west10_2030peak"
        assert system.order == 2.0
        assert system.tags == ["area:west", "study:2030peak"]
        assert system.case_time == "2026-08"

    def test_system_get_bus(self):
        """Test get_bus method."""
        bus1 = Bus("B1", bus_type=3)
        bus2 = Bus("B2", bus_type=1)
        system = System(buses=[bus1, bus2])

        assert system.get_bus("B1") is bus1
        assert system.get_bus("B2") is bus2
        assert system.get_bus("B3") is None

    def test_system_get_bus_index(self):
        """Test get_bus_index method."""
        bus1 = Bus("B1", bus_type=3)
        bus2 = Bus("B2", bus_type=1)
        system = System(buses=[bus1, bus2])

        assert system.get_bus_index("B1") == 0
        assert system.get_bus_index("B2") == 1

        with pytest.raises(ValueError, match="Bus 'B3' not found"):
            system.get_bus_index("B3")

    def test_system_get_bus_ids(self):
        """Test get_bus_ids method."""
        bus1 = Bus("B1", bus_type=3)
        bus2 = Bus("B5", bus_type=1)
        system = System(buses=[bus1, bus2])

        assert system.get_bus_ids() == ["B1", "B5"]

    def test_system_get_bus_generators(self):
        """Test get_bus_generators method."""
        gen1 = Generator("G1", bus_id="B1", p_gen=1.0, machine_id="1")
        gen2 = Generator("G2", bus_id="B1", p_gen=0.5, machine_id="2")
        gen3 = Generator("G3", bus_id="B2", p_gen=0.8)
        gen_out = Generator("G4", bus_id="B1", p_gen=0.3, machine_id="3", status=0)

        system = System(generators=[gen1, gen2, gen3, gen_out])

        # In-service only (default)
        gens = system.get_bus_generators("B1")
        assert len(gens) == 2
        assert gen1 in gens
        assert gen2 in gens
        assert gen_out not in gens

        # Including out-of-service
        gens_all = system.get_bus_generators("B1", in_service_only=False)
        assert len(gens_all) == 3

    def test_system_get_bus_loads(self):
        """Test get_bus_loads method."""
        load1 = Load("LD1", bus_id="B2", p_load=0.5, load_id="A")
        load2 = Load("LD2", bus_id="B2", p_load=0.3, load_id="B")
        load_out = Load("LD3", bus_id="B2", p_load=0.1, load_id="C", status=0)

        system = System(loads=[load1, load2, load_out])

        loads = system.get_bus_loads("B2")
        assert len(loads) == 2
        assert load_out not in loads

    def test_system_get_bus_shunts(self):
        """Test get_bus_shunts method."""
        shunt1 = Shunt("SH1", bus_id="B3", b_pu=0.5, shunt_id="1")
        shunt2 = Shunt("SH2", bus_id="B3", b_pu=-0.2, shunt_id="2")

        system = System(shunts=[shunt1, shunt2])

        shunts = system.get_bus_shunts("B3")
        assert len(shunts) == 2

    def test_system_get_branches_at_bus(self):
        """Test get_branches_at_bus method."""
        b1 = Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)
        b2 = Branch("BR2", "B2", "B3", r_pu=0.02, x_pu=0.2)
        b3 = Branch("BR3", "B1", "B3", r_pu=0.03, x_pu=0.3)

        system = System(branches=[b1, b2, b3])

        # Branches at bus B1
        branches1 = system.get_branches_at_bus("B1")
        assert len(branches1) == 2
        assert b1 in branches1
        assert b3 in branches1

        # Branches at bus B2
        branches2 = system.get_branches_at_bus("B2")
        assert len(branches2) == 2
        assert b1 in branches2
        assert b2 in branches2

    def test_system_power_injection(self):
        """Test power injection calculations."""
        gen1 = Generator("G1", bus_id="B1", p_gen=2.0, q_gen=0.5)
        load1 = Load("LD1", bus_id="B1", p_load=0.8, q_load=0.2)

        system = System(generators=[gen1], loads=[load1])

        p_inj = system.get_bus_p_injection("B1")
        q_inj = system.get_bus_q_injection("B1")

        assert p_inj == pytest.approx(1.2)  # 2.0 - 0.8
        assert q_inj == pytest.approx(0.3)  # 0.5 - 0.2

    def test_system_shunt_admittance(self):
        """Test shunt admittance calculation."""
        shunt1 = Shunt("SH1", bus_id="B1", g_pu=0.01, b_pu=0.5)
        shunt2 = Shunt("SH2", bus_id="B1", g_pu=0.02, b_pu=-0.2)

        system = System(shunts=[shunt1, shunt2])

        g, b = system.get_bus_shunt_admittance("B1")
        assert g == pytest.approx(0.03)
        assert b == pytest.approx(0.3)

    def test_system_get_buses_by_type(self):
        """Test getting buses by type."""
        bus1 = Bus("B1", bus_type=3)  # Slack
        bus2 = Bus("B2", bus_type=2)  # PV
        bus3 = Bus("B3", bus_type=1)  # PQ
        bus4 = Bus("B4", bus_type=1)  # PQ

        system = System(buses=[bus1, bus2, bus3, bus4])

        assert len(system.get_slack_buses()) == 1
        assert len(system.get_pv_buses()) == 1
        assert len(system.get_pq_buses()) == 2

    def test_system_total_generation(self):
        """Test total generation calculation."""
        gen1 = Generator("G1", bus_id="B1", p_gen=1.0, q_gen=0.3)
        gen2 = Generator("G2", bus_id="B2", p_gen=0.5, q_gen=0.2)
        gen_out = Generator("G3", bus_id="B3", p_gen=0.3, q_gen=0.1, status=0)

        system = System(generators=[gen1, gen2, gen_out])

        p, q = system.total_generation()
        assert p == pytest.approx(1.5)
        assert q == pytest.approx(0.5)

        # Including out-of-service
        p_all, q_all = system.total_generation(in_service_only=False)
        assert p_all == pytest.approx(1.8)
        assert q_all == pytest.approx(0.6)

    def test_system_total_load(self):
        """Test total load calculation."""
        load1 = Load("LD1", bus_id="B1", p_load=0.8, q_load=0.2)
        load2 = Load("LD2", bus_id="B2", p_load=0.4, q_load=0.1)

        system = System(loads=[load1, load2])

        p, q = system.total_load()
        assert p == pytest.approx(1.2)
        assert q == pytest.approx(0.3)

    def test_system_with_name(self):
        """Test System with a custom name."""
        system = System(name="IEEE 9-Bus System")
        assert system.name == "IEEE 9-Bus System"


class TestSystemIdentity:
    """Test cases for the unified identity API (get_element, used_ids, assign_ids)."""

    @pytest.fixture
    def identity_system(self) -> System:
        """A small system with one element of every type, using standard ids."""
        return System(
            buses=[Bus("B1", bus_type=3, number=1), Bus("B2", bus_type=1, number=2)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, circuit_id="1")],
            generators=[Generator("G1", bus_id="B1", p_gen=1.0, machine_id="1")],
            loads=[Load("LD1", bus_id="B2", p_load=0.8, load_id="1")],
            shunts=[Shunt("SH1", bus_id="B2", b_pu=0.1, shunt_id="1")],
            generator_costs=[
                GeneratorCost("GC1", generator_id="G1", model=2, coefficients=[0.04, 20.0, 100.0])
            ],
        )

    def test_get_element_finds_every_element_type(self, identity_system: System) -> None:
        """get_element() searches across all element types by a single id."""
        assert identity_system.get_element("B1") is identity_system.buses[0]
        assert identity_system.get_element("BR1") is identity_system.branches[0]
        assert identity_system.get_element("G1") is identity_system.generators[0]
        assert identity_system.get_element("LD1") is identity_system.loads[0]
        assert identity_system.get_element("SH1") is identity_system.shunts[0]
        assert identity_system.get_element("GC1") is identity_system.generator_costs[0]

    def test_get_element_returns_none_when_missing(self, identity_system: System) -> None:
        """An unknown id returns None rather than raising."""
        assert identity_system.get_element("X99") is None

    def test_used_ids_covers_all_element_types(self, identity_system: System) -> None:
        """used_ids() is the union of ids over every element type."""
        assert identity_system.used_ids() == {
            "B1",
            "B2",
            "BR1",
            "G1",
            "LD1",
            "SH1",
            "GC1",
        }

    def test_used_ids_excludes_system_id(self) -> None:
        """The System's own id is a case identifier, not an element id."""
        system = System(buses=[Bus("B1", bus_type=3)], id="case_1")
        assert system.used_ids() == {"B1"}

    def test_assign_ids_renames_by_standard_rules(self) -> None:
        """assign_ids() rewrites ids by the standard rules and updates all references.

        Buses become ``B{number}``; every other element type gets its type
        prefix plus 1-based position within that type (``BR1``, ``G1``,
        ``LD1``, ``SH1``, ``GC1``).
        """
        system = System(
            buses=[
                Bus("node_a", bus_type=3, number=1),
                Bus("node_b", bus_type=1, number=2),
            ],
            branches=[Branch("edge_1", "node_a", "node_b", r_pu=0.01, x_pu=0.1, circuit_id="1")],
            generators=[Generator("gen_x", bus_id="node_a", p_gen=1.0, machine_id="1")],
            loads=[Load("load_y", bus_id="node_b", p_load=0.8)],
            shunts=[Shunt("shunt_z", bus_id="node_b", b_pu=0.1)],
            generator_costs=[
                GeneratorCost("cost_1", generator_id="gen_x", model=2, coefficients=[0.0, 1.0])
            ],
            diagram_schematic=DiagramData(
                bus_positions={"node_a": BusPosition(x=100, y=200)},
                branch_routes={"edge_1": BranchRoute(waypoints=[(100, 200), (300, 400)])},
                labels=[DiagramLabel(element_type="bus", element_id="node_a", text_type="name")],
            ),
        )

        mapping = system.assign_ids()

        # Ids follow the standard deterministic rules
        assert system.buses[0].id == "B1"
        assert system.buses[1].id == "B2"
        assert system.branches[0].id == "BR1"
        assert system.generators[0].id == "G1"
        assert system.loads[0].id == "LD1"
        assert system.shunts[0].id == "SH1"
        assert system.generator_costs[0].id == "GC1"

        # References follow the renames
        assert system.branches[0].from_bus_id == "B1"
        assert system.branches[0].to_bus_id == "B2"
        assert system.generators[0].bus_id == "B1"
        assert system.loads[0].bus_id == "B2"
        assert system.shunts[0].bus_id == "B2"
        assert system.generator_costs[0].generator_id == "G1"

        # Diagram keys and labels follow the renames
        diagram = system.diagram_schematic
        assert diagram is not None
        assert set(diagram.bus_positions) == {"B1"}
        assert diagram.bus_positions["B1"].x == 100
        assert set(diagram.branch_routes) == {"BR1"}
        assert diagram.branch_routes["BR1"].waypoints == [(100, 200), (300, 400)]
        assert diagram.labels[0].element_id == "B1"

        # Mapping reports old -> new for every renamed element
        assert mapping["node_a"] == "B1"
        assert mapping["node_b"] == "B2"
        assert mapping["edge_1"] == "BR1"
        assert mapping["gen_x"] == "G1"
        assert mapping["load_y"] == "LD1"
        assert mapping["shunt_z"] == "SH1"
        assert mapping["cost_1"] == "GC1"

    def test_assign_ids_uses_per_type_sequence(self) -> None:
        """Non-bus elements are numbered by position within their own type."""
        system = System(
            buses=[Bus("B1", bus_type=3, number=1), Bus("B2", bus_type=1, number=2)],
            branches=[
                Branch("line_a", "B1", "B2", r_pu=0.01, x_pu=0.1),
                Branch("line_b", "B1", "B2", r_pu=0.02, x_pu=0.2),
            ],
            generators=[
                Generator("gen_a", bus_id="B1", p_gen=1.0),
                Generator("gen_b", bus_id="B2", p_gen=0.5),
            ],
        )
        mapping = system.assign_ids()
        assert [br.id for br in system.branches] == ["BR1", "BR2"]
        assert [g.id for g in system.generators] == ["G1", "G2"]
        assert mapping == {
            "line_a": "BR1",
            "line_b": "BR2",
            "gen_a": "G1",
            "gen_b": "G2",
        }

    def test_assign_ids_omits_identity_mappings(self, identity_system: System) -> None:
        """Elements already carrying their standard id are not reported as renamed."""
        mapping = identity_system.assign_ids()
        assert mapping == {}
        assert identity_system.buses[0].id == "B1"
        assert identity_system.branches[0].id == "BR1"

    def test_assign_ids_falls_back_to_list_position(self) -> None:
        """A bus without a format-provided number uses its 1-based list position."""
        system = System(
            buses=[Bus("alpha", bus_type=3), Bus("beta", bus_type=1)],
        )
        mapping = system.assign_ids()
        assert system.buses[0].id == "B1"
        assert system.buses[1].id == "B2"
        assert mapping == {"alpha": "B1", "beta": "B2"}
