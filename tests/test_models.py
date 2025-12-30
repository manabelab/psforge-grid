"""Tests for power system data models.

Tests the fundamental data classes: Bus, Branch, Generator, Load, and System.
"""

import pytest

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
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
        assert bus.p_load == 0.0
        assert bus.q_load == 0.0
        assert bus.p_gen == 0.0
        assert bus.q_gen == 0.0
        assert bus.base_kv == 1.0
        assert bus.name is None

    def test_bus_invalid_type(self):
        """Test that invalid bus_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid bus_type"):
            Bus(bus_id=1, bus_type=4)

        with pytest.raises(ValueError, match="Invalid bus_type"):
            Bus(bus_id=1, bus_type=0)

    def test_bus_types(self):
        """Test all valid bus types."""
        bus_pq = Bus(bus_id=1, bus_type=1)  # PQ bus
        bus_pv = Bus(bus_id=2, bus_type=2)  # PV bus
        bus_slack = Bus(bus_id=3, bus_type=3)  # Slack bus

        assert bus_pq.bus_type == 1
        assert bus_pv.bus_type == 2
        assert bus_slack.bus_type == 3


class TestBranch:
    """Test cases for Branch class."""

    def test_branch_creation(self):
        """Test that a Branch object can be created with valid parameters."""
        branch = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1, b_pu=0.02, rate_mva=100.0)
        assert branch.from_bus == 1
        assert branch.to_bus == 2
        assert branch.r_pu == 0.01
        assert branch.x_pu == 0.1
        assert branch.b_pu == 0.02
        assert branch.rate_mva == 100.0

    def test_branch_default_values(self):
        """Test that Branch uses correct default values."""
        branch = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1)
        assert branch.b_pu == 0.0
        assert branch.tap_ratio == 1.0
        assert branch.shift_angle == 0.0
        assert branch.rate_mva is None
        assert branch.name is None

    def test_branch_transformer(self):
        """Test transformer with non-unity tap ratio."""
        transformer = Branch(from_bus=1, to_bus=2, r_pu=0.001, x_pu=0.05, tap_ratio=1.05)
        assert transformer.tap_ratio == 1.05


class TestGenerator:
    """Test cases for Generator class."""

    def test_generator_creation(self):
        """Test that a Generator object can be created with valid parameters."""
        gen = Generator(bus_id=1, p_gen=100.0, v_setpoint=1.05, p_max=150.0, p_min=0.0)
        assert gen.bus_id == 1
        assert gen.p_gen == 100.0
        assert gen.v_setpoint == 1.05
        assert gen.p_max == 150.0
        assert gen.p_min == 0.0

    def test_generator_default_values(self):
        """Test that Generator uses correct default values."""
        gen = Generator(bus_id=1, p_gen=100.0)
        assert gen.q_gen == 0.0
        assert gen.v_setpoint == 1.0
        assert gen.p_max is None
        assert gen.p_min is None
        assert gen.q_max is None
        assert gen.q_min is None
        assert gen.name is None


class TestLoad:
    """Test cases for Load class."""

    def test_load_creation(self):
        """Test that a Load object can be created."""
        load = Load(bus_id=2, p_load=50.0, q_load=20.0, name="Load1")
        assert load.bus_id == 2
        assert load.p_load == 50.0
        assert load.q_load == 20.0
        assert load.name == "Load1"

    def test_load_default_values(self):
        """Test that Load uses correct default values."""
        load = Load(bus_id=2, p_load=50.0)
        assert load.q_load == 0.0
        assert load.name is None


class TestSystem:
    """Test cases for System class."""

    def test_system_creation(self):
        """Test that a System object can be created with components."""
        bus1 = Bus(bus_id=1, bus_type=3)
        bus2 = Bus(bus_id=2, bus_type=1)
        branch = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1)
        gen = Generator(bus_id=1, p_gen=100.0)

        system = System(buses=[bus1, bus2], branches=[branch], generators=[gen], base_mva=100.0)

        assert system.num_buses() == 2
        assert system.num_branches() == 1
        assert system.num_generators() == 1
        assert system.base_mva == 100.0

    def test_system_default_values(self):
        """Test that System uses correct default values."""
        system = System()
        assert system.num_buses() == 0
        assert system.num_branches() == 0
        assert system.num_generators() == 0
        assert system.base_mva == 100.0
        assert system.name == ""

    def test_system_empty_lists(self):
        """Test System with empty component lists."""
        system = System(buses=[], branches=[], generators=[])
        assert len(system.buses) == 0
        assert len(system.branches) == 0
        assert len(system.generators) == 0

    def test_system_with_name(self):
        """Test System with a custom name."""
        system = System(name="IEEE 9-Bus System")
        assert system.name == "IEEE 9-Bus System"
