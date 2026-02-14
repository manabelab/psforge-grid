"""Tests for System modification methods (add_bus, add_branch, etc.).

Tests the validated add methods for safe system modification,
supporting the grid access demo workflow.
"""

import pytest

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt
from psforge_grid.models.system import System


@pytest.fixture
def ieee14_system() -> System:
    """Load IEEE 14-bus system from RAW file."""
    return System.from_raw("tests/fixtures/ieee14.raw")


@pytest.fixture
def small_system() -> System:
    """Create a minimal 2-bus system for unit tests."""
    return System(
        buses=[
            Bus(bus_id=1, bus_type=3, v_magnitude=1.06, base_kv=138.0),
            Bus(bus_id=2, bus_type=1, v_magnitude=1.0, base_kv=138.0),
        ],
        branches=[
            Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1),
        ],
        generators=[
            Generator(bus_id=1, p_gen=1.0),
        ],
        loads=[
            Load(bus_id=2, p_load=0.8, q_load=0.2),
        ],
    )


class TestAddBus:
    """Tests for System.add_bus()."""

    def test_add_bus_success(self, small_system: System) -> None:
        """New bus with unique ID is added successfully."""
        original_count = small_system.num_buses()
        new_bus = Bus(bus_id=3, bus_type=1, base_kv=33.0)
        small_system.add_bus(new_bus)
        assert small_system.num_buses() == original_count + 1
        assert small_system.get_bus(3) is new_bus

    def test_add_bus_duplicate_raises(self, small_system: System) -> None:
        """Duplicate bus_id raises ValueError with informative message."""
        dup_bus = Bus(bus_id=1, bus_type=1)
        with pytest.raises(ValueError, match="already exists"):
            small_system.add_bus(dup_bus)

    def test_add_bus_duplicate_error_shows_max_id(self, small_system: System) -> None:
        """Error message includes current max bus_id."""
        dup_bus = Bus(bus_id=2, bus_type=1)
        with pytest.raises(ValueError, match="current max: 2"):
            small_system.add_bus(dup_bus)

    def test_add_bus_ieee14(self, ieee14_system: System) -> None:
        """Add bus to IEEE 14-bus system."""
        original_count = ieee14_system.num_buses()
        ieee14_system.add_bus(Bus(bus_id=15, bus_type=1, base_kv=33.0))
        assert ieee14_system.num_buses() == original_count + 1


class TestAddBranch:
    """Tests for System.add_branch()."""

    def test_add_branch_success(self, small_system: System) -> None:
        """Branch with valid bus references is added."""
        small_system.add_bus(Bus(bus_id=3, bus_type=1))
        original_count = small_system.num_branches()
        new_branch = Branch(from_bus=2, to_bus=3, r_pu=0.01, x_pu=0.05)
        small_system.add_branch(new_branch)
        assert small_system.num_branches() == original_count + 1

    def test_add_branch_invalid_from_bus_raises(self, small_system: System) -> None:
        """from_bus not in system raises ValueError."""
        bad_branch = Branch(from_bus=99, to_bus=2, r_pu=0.01, x_pu=0.05)
        with pytest.raises(ValueError, match="from_bus 99 not found"):
            small_system.add_branch(bad_branch)

    def test_add_branch_invalid_to_bus_raises(self, small_system: System) -> None:
        """to_bus not in system raises ValueError."""
        bad_branch = Branch(from_bus=1, to_bus=99, r_pu=0.01, x_pu=0.05)
        with pytest.raises(ValueError, match="to_bus 99 not found"):
            small_system.add_branch(bad_branch)

    def test_add_branch_error_shows_available_ids(self, small_system: System) -> None:
        """Error message includes available bus IDs."""
        bad_branch = Branch(from_bus=1, to_bus=99, r_pu=0.01, x_pu=0.05)
        with pytest.raises(ValueError, match="Available bus IDs"):
            small_system.add_branch(bad_branch)


class TestAddGenerator:
    """Tests for System.add_generator()."""

    def test_add_generator_success(self, small_system: System) -> None:
        """Generator with valid bus_id is added."""
        original_count = small_system.num_generators()
        gen = Generator(bus_id=2, p_gen=0.5, gen_id="G2")
        small_system.add_generator(gen)
        assert small_system.num_generators() == original_count + 1

    def test_add_generator_invalid_bus_raises(self, small_system: System) -> None:
        """Generator with non-existent bus_id raises ValueError."""
        gen = Generator(bus_id=99, p_gen=0.5)
        with pytest.raises(ValueError, match="Bus 99 not found"):
            small_system.add_generator(gen)

    def test_add_generator_error_suggests_add_bus(self, small_system: System) -> None:
        """Error message suggests using add_bus() first."""
        gen = Generator(bus_id=99, p_gen=0.5)
        with pytest.raises(ValueError, match="add_bus"):
            small_system.add_generator(gen)


class TestAddShunt:
    """Tests for System.add_shunt()."""

    def test_add_shunt_success(self, small_system: System) -> None:
        """Shunt with valid bus_id is added."""
        original_count = small_system.num_shunts()
        shunt = Shunt(bus_id=2, b_pu=0.05)
        small_system.add_shunt(shunt)
        assert small_system.num_shunts() == original_count + 1

    def test_add_shunt_invalid_bus_raises(self, small_system: System) -> None:
        """Shunt with non-existent bus_id raises ValueError."""
        shunt = Shunt(bus_id=99, b_pu=0.05)
        with pytest.raises(ValueError, match="Bus 99 not found"):
            small_system.add_shunt(shunt)


class TestAddLoad:
    """Tests for System.add_load()."""

    def test_add_load_success(self, small_system: System) -> None:
        """Load with valid bus_id is added."""
        original_count = small_system.num_loads()
        load = Load(bus_id=1, p_load=0.3, q_load=0.1)
        small_system.add_load(load)
        assert small_system.num_loads() == original_count + 1

    def test_add_load_invalid_bus_raises(self, small_system: System) -> None:
        """Load with non-existent bus_id raises ValueError."""
        load = Load(bus_id=99, p_load=0.3)
        with pytest.raises(ValueError, match="Bus 99 not found"):
            small_system.add_load(load)


class TestSystemValidation:
    """Tests for System.validate()."""

    def test_validate_valid_system(self, ieee14_system: System) -> None:
        """IEEE 14-bus system passes validation."""
        errors = ieee14_system.validate()
        assert errors == []

    def test_validate_small_system(self, small_system: System) -> None:
        """Small valid system passes validation."""
        errors = small_system.validate()
        assert errors == []

    def test_validate_missing_slack(self) -> None:
        """System without slack bus is detected."""
        system = System(buses=[Bus(bus_id=1, bus_type=1)])
        errors = system.validate()
        assert any("slack" in e.lower() for e in errors)

    def test_validate_duplicate_bus(self, ieee14_system: System) -> None:
        """Duplicate bus_id is detected."""
        ieee14_system.buses.append(Bus(bus_id=1, bus_type=1))
        errors = ieee14_system.validate()
        assert any("Duplicate" in e for e in errors)

    def test_validate_dangling_branch(self, ieee14_system: System) -> None:
        """Branch referencing non-existent bus is detected."""
        ieee14_system.branches.append(Branch(from_bus=1, to_bus=99, r_pu=0.01, x_pu=0.05))
        errors = ieee14_system.validate()
        assert any("99" in e for e in errors)

    def test_validate_dangling_generator(self, ieee14_system: System) -> None:
        """Generator at non-existent bus is detected."""
        ieee14_system.generators.append(Generator(bus_id=99, p_gen=0.5))
        errors = ieee14_system.validate()
        assert any("99" in e for e in errors)

    def test_validate_dangling_load(self, ieee14_system: System) -> None:
        """Load at non-existent bus is detected."""
        ieee14_system.loads.append(Load(bus_id=99, p_load=0.3))
        errors = ieee14_system.validate()
        assert any("99" in e for e in errors)

    def test_validate_dangling_shunt(self, ieee14_system: System) -> None:
        """Shunt at non-existent bus is detected."""
        ieee14_system.shunts.append(Shunt(bus_id=99, b_pu=0.05))
        errors = ieee14_system.validate()
        assert any("99" in e for e in errors)

    def test_validate_modified_system_valid(self, ieee14_system: System) -> None:
        """System modified via add_* methods passes validation."""
        ieee14_system.add_bus(Bus(bus_id=15, bus_type=1, base_kv=33.0))
        ieee14_system.add_branch(Branch(from_bus=14, to_bus=15, r_pu=0.01, x_pu=0.05))
        ieee14_system.add_generator(Generator(bus_id=15, p_gen=0.5, gen_id="PV1"))
        errors = ieee14_system.validate()
        assert errors == []

    def test_validate_multiple_errors(self) -> None:
        """Multiple validation errors are all reported."""
        system = System(
            buses=[Bus(bus_id=1, bus_type=1)],  # no slack
            branches=[Branch(from_bus=1, to_bus=99, r_pu=0.01, x_pu=0.05)],  # dangling
            generators=[Generator(bus_id=88, p_gen=0.5)],  # dangling
        )
        errors = system.validate()
        assert len(errors) >= 3  # slack + branch to_bus + generator bus


class TestGridAccessWorkflow:
    """Integration tests simulating the grid access demo workflow."""

    def test_add_solar_plant_to_ieee14(self, ieee14_system: System) -> None:
        """Simulate adding a solar plant with POI substation to IEEE 14-bus."""
        original_buses = ieee14_system.num_buses()
        original_branches = ieee14_system.num_branches()
        original_gens = ieee14_system.num_generators()

        # Step 1: Add POI substation bus
        ieee14_system.add_bus(
            Bus(
                bus_id=15,
                bus_type=1,
                v_magnitude=1.0,
                base_kv=33.0,
                name="Solar_POI",
            )
        )

        # Step 2: Add source line (connection point -> POI)
        ieee14_system.add_branch(
            Branch(
                from_bus=14,
                to_bus=15,
                r_pu=0.01,
                x_pu=0.05,
                b_pu=0.02,
                rate_a=100.0,
            )
        )

        # Step 3: Add solar generator
        ieee14_system.add_generator(
            Generator(
                bus_id=15,
                p_gen=0.5,
                q_gen=0.0,
                v_setpoint=1.0,
                gen_id="PV1",
            )
        )

        # Verify
        assert ieee14_system.num_buses() == original_buses + 1
        assert ieee14_system.num_branches() == original_branches + 1
        assert ieee14_system.num_generators() == original_gens + 1

    def test_add_svc_to_poi(self, ieee14_system: System) -> None:
        """Simulate adding SVC at POI for voltage support."""
        ieee14_system.add_bus(Bus(bus_id=15, bus_type=1, base_kv=33.0))
        ieee14_system.add_shunt(
            Shunt(
                bus_id=15,
                g_pu=0.0,
                b_pu=0.05,
                shunt_id="SVC1",
            )
        )
        assert ieee14_system.num_shunts() > 0

    def test_validation_order_matters(self, small_system: System) -> None:
        """Adding branch before bus raises, but bus-then-branch succeeds."""
        # Branch to non-existent bus 3 should fail
        with pytest.raises(ValueError):
            small_system.add_branch(Branch(from_bus=2, to_bus=3, r_pu=0.01, x_pu=0.05))

        # After adding bus 3, branch should succeed
        small_system.add_bus(Bus(bus_id=3, bus_type=1))
        small_system.add_branch(Branch(from_bus=2, to_bus=3, r_pu=0.01, x_pu=0.05))
