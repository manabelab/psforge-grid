"""Tests for power system data models.

Tests the fundamental data classes: Bus, Branch, Generator, Load, Shunt, and System.
"""

import pytest

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt
from psforge_grid.models.system import System


class TestBus:
    """Test cases for Bus class."""

    def test_bus_creation(self):
        """Test that a Bus object can be created with valid parameters."""
        bus = Bus(bus_id=1, bus_type=3, v_magnitude=1.05, base_kv=138.0, name="Bus1")
        assert bus.bus_id == 1
        assert bus.bus_type == 3
        assert bus.v_magnitude == 1.05
        assert bus.base_kv == 138.0
        assert bus.name == "Bus1"

    def test_bus_default_values(self):
        """Test that Bus uses correct default values."""
        bus = Bus(bus_id=1, bus_type=1)
        assert bus.v_magnitude == 1.0
        assert bus.v_angle == 0.0
        assert bus.base_kv == 1.0
        assert bus.area == 1
        assert bus.zone == 1
        assert bus.v_max == 1.1
        assert bus.v_min == 0.9
        assert bus.name is None

    def test_bus_invalid_type(self):
        """Test that invalid bus_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid bus_type"):
            Bus(bus_id=1, bus_type=5)

        with pytest.raises(ValueError, match="Invalid bus_type"):
            Bus(bus_id=1, bus_type=0)

    def test_bus_types(self):
        """Test all valid bus types."""
        bus_pq = Bus(bus_id=1, bus_type=1)  # PQ bus
        bus_pv = Bus(bus_id=2, bus_type=2)  # PV bus
        bus_slack = Bus(bus_id=3, bus_type=3)  # Slack bus
        bus_isolated = Bus(bus_id=4, bus_type=4)  # Isolated bus

        assert bus_pq.bus_type == 1
        assert bus_pv.bus_type == 2
        assert bus_slack.bus_type == 3
        assert bus_isolated.bus_type == 4

    def test_bus_type_properties(self):
        """Test bus type convenience properties."""
        bus_pq = Bus(bus_id=1, bus_type=1)
        bus_pv = Bus(bus_id=2, bus_type=2)
        bus_slack = Bus(bus_id=3, bus_type=3)
        bus_isolated = Bus(bus_id=4, bus_type=4)

        assert bus_pq.is_pq is True
        assert bus_pq.is_pv is False
        assert bus_pv.is_pv is True
        assert bus_slack.is_slack is True
        assert bus_isolated.is_isolated is True

    def test_bus_with_area_zone(self):
        """Test bus with area and zone."""
        bus = Bus(bus_id=1, bus_type=1, area=2, zone=3)
        assert bus.area == 2
        assert bus.zone == 3


class TestBranch:
    """Test cases for Branch class."""

    def test_branch_creation(self):
        """Test that a Branch object can be created with valid parameters."""
        branch = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1, b_pu=0.02, rate_a=100.0)
        assert branch.from_bus == 1
        assert branch.to_bus == 2
        assert branch.r_pu == 0.01
        assert branch.x_pu == 0.1
        assert branch.b_pu == 0.02
        assert branch.rate_a == 100.0

    def test_branch_default_values(self):
        """Test that Branch uses correct default values."""
        branch = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1)
        assert branch.b_pu == 0.0
        assert branch.tap_ratio == 1.0
        assert branch.shift_angle == 0.0
        assert branch.rate_a is None
        assert branch.rate_b is None
        assert branch.rate_c is None
        assert branch.status == 1
        assert branch.circuit_id == "1"
        assert branch.name is None

    def test_branch_transformer(self):
        """Test transformer with non-unity tap ratio."""
        transformer = Branch(from_bus=1, to_bus=2, r_pu=0.001, x_pu=0.05, tap_ratio=1.05)
        assert transformer.tap_ratio == 1.05
        assert transformer.is_transformer is True

    def test_branch_is_transformer_property(self):
        """Test is_transformer property."""
        line = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1)
        xfmr_tap = Branch(from_bus=1, to_bus=2, r_pu=0.0, x_pu=0.05, tap_ratio=1.02)
        xfmr_shift = Branch(from_bus=1, to_bus=2, r_pu=0.0, x_pu=0.05, shift_angle=0.1)

        assert line.is_transformer is False
        assert xfmr_tap.is_transformer is True
        assert xfmr_shift.is_transformer is True

    def test_branch_status(self):
        """Test branch status."""
        branch_in = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1, status=1)
        branch_out = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1, status=0)

        assert branch_in.is_in_service is True
        assert branch_out.is_in_service is False

    def test_branch_invalid_status(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1, status=2)

    def test_branch_zero_tap_ratio(self):
        """Test that zero tap_ratio raises ValueError."""
        with pytest.raises(ValueError, match="tap_ratio cannot be zero"):
            Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1, tap_ratio=0.0)


class TestGenerator:
    """Test cases for Generator class."""

    def test_generator_creation(self):
        """Test that a Generator object can be created with valid parameters."""
        gen = Generator(bus_id=1, p_gen=1.0, v_setpoint=1.05, p_max=1.5, p_min=0.0)
        assert gen.bus_id == 1
        assert gen.p_gen == 1.0
        assert gen.v_setpoint == 1.05
        assert gen.p_max == 1.5
        assert gen.p_min == 0.0

    def test_generator_default_values(self):
        """Test that Generator uses correct default values."""
        gen = Generator(bus_id=1, p_gen=1.0)
        assert gen.q_gen == 0.0
        assert gen.v_setpoint == 1.0
        assert gen.p_max is None
        assert gen.p_min is None
        assert gen.q_max is None
        assert gen.q_min is None
        assert gen.mbase == 100.0
        assert gen.status == 1
        assert gen.gen_id == "1"
        assert gen.name is None

    def test_generator_status(self):
        """Test generator status."""
        gen_in = Generator(bus_id=1, p_gen=1.0, status=1)
        gen_out = Generator(bus_id=1, p_gen=1.0, status=0)

        assert gen_in.is_in_service is True
        assert gen_out.is_in_service is False

    def test_generator_invalid_status(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            Generator(bus_id=1, p_gen=1.0, status=2)

    def test_generator_q_limits(self):
        """Test Q limit checking."""
        gen = Generator(bus_id=1, p_gen=1.0, q_max=0.5, q_min=-0.3)

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
        load = Load(bus_id=2, p_load=0.5, q_load=0.2, name="Load1")
        assert load.bus_id == 2
        assert load.p_load == 0.5
        assert load.q_load == 0.2
        assert load.name == "Load1"

    def test_load_default_values(self):
        """Test that Load uses correct default values."""
        load = Load(bus_id=2, p_load=0.5)
        assert load.q_load == 0.0
        assert load.status == 1
        assert load.load_id == "1"
        assert load.name is None

    def test_load_status(self):
        """Test load status."""
        load_in = Load(bus_id=2, p_load=0.5, status=1)
        load_out = Load(bus_id=2, p_load=0.5, status=0)

        assert load_in.is_in_service is True
        assert load_out.is_in_service is False

    def test_load_invalid_status(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            Load(bus_id=2, p_load=0.5, status=2)

    def test_load_apparent_power(self):
        """Test apparent power calculation."""
        load = Load(bus_id=2, p_load=0.3, q_load=0.4)
        assert load.apparent_power == pytest.approx(0.5)

    def test_load_power_factor(self):
        """Test power factor calculation."""
        load = Load(bus_id=2, p_load=0.8, q_load=0.6)
        assert load.power_factor == pytest.approx(0.8)

        # Zero load
        zero_load = Load(bus_id=2, p_load=0.0, q_load=0.0)
        assert zero_load.power_factor == 1.0


class TestShunt:
    """Test cases for Shunt class."""

    def test_shunt_creation(self):
        """Test that a Shunt object can be created."""
        shunt = Shunt(bus_id=1, g_pu=0.01, b_pu=0.5, name="Cap1")
        assert shunt.bus_id == 1
        assert shunt.g_pu == 0.01
        assert shunt.b_pu == 0.5
        assert shunt.name == "Cap1"

    def test_shunt_default_values(self):
        """Test that Shunt uses correct default values."""
        shunt = Shunt(bus_id=1)
        assert shunt.g_pu == 0.0
        assert shunt.b_pu == 0.0
        assert shunt.status == 1
        assert shunt.shunt_id == "1"
        assert shunt.name is None

    def test_shunt_capacitor(self):
        """Test capacitor (positive B)."""
        cap = Shunt(bus_id=1, b_pu=0.5)
        assert cap.b_pu > 0  # Capacitor: positive susceptance

    def test_shunt_reactor(self):
        """Test reactor (negative B)."""
        reactor = Shunt(bus_id=1, b_pu=-0.3)
        assert reactor.b_pu < 0  # Reactor: negative susceptance

    def test_shunt_invalid_status(self):
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            Shunt(bus_id=1, status=2)


class TestSystem:
    """Test cases for System class."""

    def test_system_creation(self):
        """Test that a System object can be created with components."""
        bus1 = Bus(bus_id=1, bus_type=3)
        bus2 = Bus(bus_id=2, bus_type=1)
        branch = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1)
        gen = Generator(bus_id=1, p_gen=1.0)
        load = Load(bus_id=2, p_load=0.8)
        shunt = Shunt(bus_id=2, b_pu=0.1)

        system = System(
            buses=[bus1, bus2],
            branches=[branch],
            generators=[gen],
            loads=[load],
            shunts=[shunt],
            base_mva=100.0,
        )

        assert system.num_buses() == 2
        assert system.num_branches() == 1
        assert system.num_generators() == 1
        assert system.num_loads() == 1
        assert system.num_shunts() == 1
        assert system.base_mva == 100.0

    def test_system_default_values(self):
        """Test that System uses correct default values."""
        system = System()
        assert system.num_buses() == 0
        assert system.num_branches() == 0
        assert system.num_generators() == 0
        assert system.num_loads() == 0
        assert system.num_shunts() == 0
        assert system.base_mva == 100.0
        assert system.name == ""

    def test_system_get_bus(self):
        """Test get_bus method."""
        bus1 = Bus(bus_id=1, bus_type=3)
        bus2 = Bus(bus_id=2, bus_type=1)
        system = System(buses=[bus1, bus2])

        assert system.get_bus(1) == bus1
        assert system.get_bus(2) == bus2
        assert system.get_bus(3) is None

    def test_system_get_bus_index(self):
        """Test get_bus_index method."""
        bus1 = Bus(bus_id=1, bus_type=3)
        bus2 = Bus(bus_id=2, bus_type=1)
        system = System(buses=[bus1, bus2])

        assert system.get_bus_index(1) == 0
        assert system.get_bus_index(2) == 1

        with pytest.raises(ValueError, match="Bus 3 not found"):
            system.get_bus_index(3)

    def test_system_get_bus_ids(self):
        """Test get_bus_ids method."""
        bus1 = Bus(bus_id=1, bus_type=3)
        bus2 = Bus(bus_id=5, bus_type=1)
        system = System(buses=[bus1, bus2])

        assert system.get_bus_ids() == [1, 5]

    def test_system_get_bus_generators(self):
        """Test get_bus_generators method."""
        gen1 = Generator(bus_id=1, p_gen=1.0, gen_id="1")
        gen2 = Generator(bus_id=1, p_gen=0.5, gen_id="2")
        gen3 = Generator(bus_id=2, p_gen=0.8)
        gen_out = Generator(bus_id=1, p_gen=0.3, gen_id="3", status=0)

        system = System(generators=[gen1, gen2, gen3, gen_out])

        # In-service only (default)
        gens = system.get_bus_generators(1)
        assert len(gens) == 2
        assert gen1 in gens
        assert gen2 in gens
        assert gen_out not in gens

        # Including out-of-service
        gens_all = system.get_bus_generators(1, in_service_only=False)
        assert len(gens_all) == 3

    def test_system_get_bus_loads(self):
        """Test get_bus_loads method."""
        load1 = Load(bus_id=2, p_load=0.5, load_id="A")
        load2 = Load(bus_id=2, p_load=0.3, load_id="B")
        load_out = Load(bus_id=2, p_load=0.1, load_id="C", status=0)

        system = System(loads=[load1, load2, load_out])

        loads = system.get_bus_loads(2)
        assert len(loads) == 2
        assert load_out not in loads

    def test_system_get_bus_shunts(self):
        """Test get_bus_shunts method."""
        shunt1 = Shunt(bus_id=3, b_pu=0.5, shunt_id="1")
        shunt2 = Shunt(bus_id=3, b_pu=-0.2, shunt_id="2")

        system = System(shunts=[shunt1, shunt2])

        shunts = system.get_bus_shunts(3)
        assert len(shunts) == 2

    def test_system_get_branches_at_bus(self):
        """Test get_branches_at_bus method."""
        b1 = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1)
        b2 = Branch(from_bus=2, to_bus=3, r_pu=0.02, x_pu=0.2)
        b3 = Branch(from_bus=1, to_bus=3, r_pu=0.03, x_pu=0.3)

        system = System(branches=[b1, b2, b3])

        # Branches at bus 1
        branches1 = system.get_branches_at_bus(1)
        assert len(branches1) == 2
        assert b1 in branches1
        assert b3 in branches1

        # Branches at bus 2
        branches2 = system.get_branches_at_bus(2)
        assert len(branches2) == 2
        assert b1 in branches2
        assert b2 in branches2

    def test_system_power_injection(self):
        """Test power injection calculations."""
        gen1 = Generator(bus_id=1, p_gen=2.0, q_gen=0.5)
        load1 = Load(bus_id=1, p_load=0.8, q_load=0.2)

        system = System(generators=[gen1], loads=[load1])

        p_inj = system.get_bus_p_injection(1)
        q_inj = system.get_bus_q_injection(1)

        assert p_inj == pytest.approx(1.2)  # 2.0 - 0.8
        assert q_inj == pytest.approx(0.3)  # 0.5 - 0.2

    def test_system_shunt_admittance(self):
        """Test shunt admittance calculation."""
        shunt1 = Shunt(bus_id=1, g_pu=0.01, b_pu=0.5)
        shunt2 = Shunt(bus_id=1, g_pu=0.02, b_pu=-0.2)

        system = System(shunts=[shunt1, shunt2])

        g, b = system.get_bus_shunt_admittance(1)
        assert g == pytest.approx(0.03)
        assert b == pytest.approx(0.3)

    def test_system_get_buses_by_type(self):
        """Test getting buses by type."""
        bus1 = Bus(bus_id=1, bus_type=3)  # Slack
        bus2 = Bus(bus_id=2, bus_type=2)  # PV
        bus3 = Bus(bus_id=3, bus_type=1)  # PQ
        bus4 = Bus(bus_id=4, bus_type=1)  # PQ

        system = System(buses=[bus1, bus2, bus3, bus4])

        assert len(system.get_slack_buses()) == 1
        assert len(system.get_pv_buses()) == 1
        assert len(system.get_pq_buses()) == 2

    def test_system_total_generation(self):
        """Test total generation calculation."""
        gen1 = Generator(bus_id=1, p_gen=1.0, q_gen=0.3)
        gen2 = Generator(bus_id=2, p_gen=0.5, q_gen=0.2)
        gen_out = Generator(bus_id=3, p_gen=0.3, q_gen=0.1, status=0)

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
        load1 = Load(bus_id=1, p_load=0.8, q_load=0.2)
        load2 = Load(bus_id=2, p_load=0.4, q_load=0.1)

        system = System(loads=[load1, load2])

        p, q = system.total_load()
        assert p == pytest.approx(1.2)
        assert q == pytest.approx(0.3)

    def test_system_with_name(self):
        """Test System with a custom name."""
        system = System(name="IEEE 9-Bus System")
        assert system.name == "IEEE 9-Bus System"
