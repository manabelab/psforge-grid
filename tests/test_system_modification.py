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
def ieee14_system(fixtures_dir) -> System:
    """Load IEEE 14-bus system from RAW file.

    Note: Function-scoped (not module-scoped) because tests mutate the system.
    The ``fixtures_dir`` fixture comes from conftest.py.
    """
    return System.from_raw(fixtures_dir / "ieee14.raw")


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
        original_count = small_system.num_buses
        new_bus = Bus(bus_id=3, bus_type=1, base_kv=33.0)
        small_system.add_bus(new_bus)
        assert small_system.num_buses == original_count + 1
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
        original_count = ieee14_system.num_buses
        ieee14_system.add_bus(Bus(bus_id=15, bus_type=1, base_kv=33.0))
        assert ieee14_system.num_buses == original_count + 1


class TestAddBranch:
    """Tests for System.add_branch()."""

    def test_add_branch_success(self, small_system: System) -> None:
        """Branch with valid bus references is added."""
        small_system.add_bus(Bus(bus_id=3, bus_type=1))
        original_count = small_system.num_branches
        new_branch = Branch(from_bus=2, to_bus=3, r_pu=0.01, x_pu=0.05)
        small_system.add_branch(new_branch)
        assert small_system.num_branches == original_count + 1

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
        original_count = small_system.num_generators
        gen = Generator(bus_id=2, p_gen=0.5, gen_id="G2")
        small_system.add_generator(gen)
        assert small_system.num_generators == original_count + 1

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
        original_count = small_system.num_shunts
        shunt = Shunt(bus_id=2, b_pu=0.05)
        small_system.add_shunt(shunt)
        assert small_system.num_shunts == original_count + 1

    def test_add_shunt_invalid_bus_raises(self, small_system: System) -> None:
        """Shunt with non-existent bus_id raises ValueError."""
        shunt = Shunt(bus_id=99, b_pu=0.05)
        with pytest.raises(ValueError, match="Bus 99 not found"):
            small_system.add_shunt(shunt)


class TestAddLoad:
    """Tests for System.add_load()."""

    def test_add_load_success(self, small_system: System) -> None:
        """Load with valid bus_id is added."""
        original_count = small_system.num_loads
        load = Load(bus_id=1, p_load=0.3, q_load=0.1)
        small_system.add_load(load)
        assert small_system.num_loads == original_count + 1

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
        original_buses = ieee14_system.num_buses
        original_branches = ieee14_system.num_branches
        original_gens = ieee14_system.num_generators

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
        assert ieee14_system.num_buses == original_buses + 1
        assert ieee14_system.num_branches == original_branches + 1
        assert ieee14_system.num_generators == original_gens + 1

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
        assert ieee14_system.num_shunts > 0

    def test_validation_order_matters(self, small_system: System) -> None:
        """Adding branch before bus raises, but bus-then-branch succeeds."""
        # Branch to non-existent bus 3 should fail
        with pytest.raises(ValueError):
            small_system.add_branch(Branch(from_bus=2, to_bus=3, r_pu=0.01, x_pu=0.05))

        # After adding bus 3, branch should succeed
        small_system.add_bus(Bus(bus_id=3, bus_type=1))
        small_system.add_branch(Branch(from_bus=2, to_bus=3, r_pu=0.01, x_pu=0.05))


class TestDataCompleteness:
    """Tests for System.check_data_completeness() and the opt-in defaults."""

    def test_missing_ratings_are_reported(self) -> None:
        """A branch with no rate_a is reported, with its count."""
        system = System(
            buses=[Bus(1, bus_type=3, base_kv=345.0), Bus(2, bus_type=1, base_kv=345.0)],
            branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)],
        )
        issues = system.check_data_completeness()
        assert any("rate_a missing on 1/1" in i["message"] for i in issues)
        assert all(i["level"] == "warning" for i in issues)

    def test_missing_reactances_are_reported(self) -> None:
        """An in-service generator with no reactance is reported."""
        system = System(generators=[Generator(bus_id=1, p_gen=1.0)])
        issues = system.check_data_completeness()
        msg = next(i["message"] for i in issues if "reactance" in i["message"])
        assert "1/1 in-service generators" in msg
        # The direction of the error is the whole point: it reads as safe.
        assert "UNDERSTATES" in msg

    def test_out_of_service_generators_are_not_reported(self) -> None:
        """A generator that is out of service cannot understate fault current."""
        system = System(generators=[Generator(bus_id=1, p_gen=1.0, status=0)])
        assert not any("reactance" in i["message"] for i in system.check_data_completeness())

    def test_complete_system_reports_nothing(self) -> None:
        """Data that is present is not reported as missing."""
        system = System(
            buses=[Bus(1, bus_type=3, base_kv=345.0), Bus(2, bus_type=1, base_kv=345.0)],
            branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1, rate_a=500.0)],
            generators=[Generator(bus_id=1, p_gen=1.0, xdpp_pu=0.2, xqpp_pu=0.2)],
        )
        assert system.check_data_completeness() == []

    def test_completeness_warnings_reach_validate_detailed(self) -> None:
        """validate_detailed() surfaces the same gaps."""
        system = System(
            buses=[Bus(1, bus_type=3, base_kv=345.0), Bus(2, bus_type=1, base_kv=345.0)],
            branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)],
        )
        assert any("rate_a missing" in i["message"] for i in system.validate_detailed())

    def test_missing_data_does_not_make_a_system_invalid(self) -> None:
        """Missing ratings are a warning, never an error: a power flow needs none."""
        system = System(
            buses=[Bus(1, bus_type=3, base_kv=345.0), Bus(2, bus_type=1, base_kv=345.0)],
            branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)],
        )
        assert system.validate() == []
        assert not [i for i in system.validate_detailed() if i["level"] == "error"]

    def test_assign_default_ratings_by_voltage_class(self) -> None:
        """Ratings follow the voltage class of the higher-voltage terminal."""
        system = System(
            buses=[Bus(1, bus_type=3, base_kv=345.0), Bus(2, bus_type=1, base_kv=138.0)],
            branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)],
        )
        assert system.assign_default_ratings() == 1
        assert system.branches[0].rate_a == 1200.0
        assert system.branches[0].rate_b == pytest.approx(1320.0)
        assert system.check_data_completeness() == []

    def test_assign_default_ratings_does_not_clobber_real_data(self) -> None:
        """Real ratings survive; only the missing one is filled."""
        system = System(
            buses=[Bus(1, bus_type=3, base_kv=345.0), Bus(2, bus_type=1, base_kv=345.0)],
            branches=[
                Branch(1, 2, r_pu=0.01, x_pu=0.1, rate_a=77.0),
                Branch(1, 2, r_pu=0.01, x_pu=0.1),
            ],
        )
        assert system.assign_default_ratings() == 1
        assert system.branches[0].rate_a == 77.0
        assert system.branches[1].rate_a == 1200.0

    def test_assign_default_ratings_accepts_real_low_voltage_buses(self) -> None:
        """Regression: a genuine 0.6 kV bus is ratable, not an error.

        IEEE 300 has real 0.6 kV buses. An earlier guard rejected any base_kv
        at or below 1.0 as 'unset' and refused to rate the whole system.
        """
        system = System(
            buses=[Bus(1, bus_type=3, base_kv=0.6), Bus(2, bus_type=1, base_kv=0.6)],
            branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)],
        )
        assert system.assign_default_ratings() == 1
        assert system.branches[0].rate_a == 50.0

    def test_assign_default_ratings_rejects_non_positive_voltage(self) -> None:
        """A base_kv of 0 has no voltage class and cannot be guessed."""
        system = System(
            buses=[Bus(1, bus_type=3, base_kv=0.0), Bus(2, bus_type=1, base_kv=345.0)],
            branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)],
        )
        with pytest.raises(ValueError, match="non-positive base_kv"):
            system.assign_default_ratings()

    def test_default_base_kv_is_flagged_as_unverified(self) -> None:
        """A bus left at the 1.0 default is rated but called out as unverified."""
        system = System(
            buses=[Bus(1, bus_type=3), Bus(2, bus_type=1)],
            branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)],
        )
        assert system.assign_default_ratings() == 1
        assert "unverified" in system.assumptions[0]

    def test_assign_default_reactances(self) -> None:
        """Machines without a reactance get the documented default."""
        system = System(
            generators=[
                Generator(bus_id=1, p_gen=1.0),
                Generator(bus_id=2, p_gen=1.0, xdpp_pu=0.15),
            ]
        )
        assert system.assign_default_reactances() == 1
        assert system.generators[0].xdpp_pu == 0.2
        assert system.generators[1].xdpp_pu == 0.15

    def test_assign_default_reactances_rejects_zero(self) -> None:
        """A zero reactance would make the machine an infinite source."""
        system = System(generators=[Generator(bus_id=1, p_gen=1.0)])
        with pytest.raises(ValueError, match="must be positive"):
            system.assign_default_reactances(xdpp_pu=0.0)

    def test_assumptions_are_declared_to_llm_context(self) -> None:
        """An LLM reading the context is told the inputs were invented."""
        system = System(
            buses=[Bus(1, bus_type=3, base_kv=345.0), Bus(2, bus_type=1, base_kv=345.0)],
            branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)],
        )
        assert "### Data Assumptions" not in system.to_llm_context()
        system.assign_default_ratings()
        ctx = system.to_llm_context()
        assert "### Data Assumptions" in ctx
        assert "rated by voltage class" in ctx

    def test_missing_data_is_declared_to_llm_context(self) -> None:
        """Gaps are surfaced even when no defaults were applied."""
        system = System(
            buses=[Bus(1, bus_type=3, base_kv=345.0), Bus(2, bus_type=1, base_kv=345.0)],
            branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)],
        )
        assert "### Missing Data" in system.to_llm_context()

    def test_assumptions_do_not_leak_between_systems(self) -> None:
        """The note is per-instance, not shared class state."""
        a = System(generators=[Generator(bus_id=1, p_gen=1.0)])
        b = System(generators=[Generator(bus_id=1, p_gen=1.0)])
        a.assign_default_reactances()
        assert len(a.assumptions) == 1
        assert b.assumptions == []
