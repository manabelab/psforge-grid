"""Tests for System modification methods (add_bus, add_branch, etc.).

Tests the validated add methods for safe system modification,
supporting the grid access demo workflow, plus System.validate() under
the unified string-identifier scheme (system-wide unique ids, GeneratorCost
references, case_time format).
"""

import pytest

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.generator_cost import GeneratorCost
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
            Bus("B1", bus_type=3, v_magnitude=1.06, base_kv=138.0),
            Bus("B2", bus_type=1, v_magnitude=1.0, base_kv=138.0),
        ],
        branches=[
            Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1),
        ],
        generators=[
            Generator("G1", bus_id="B1", p_gen=1.0),
        ],
        loads=[
            Load("LD1", bus_id="B2", p_load=0.8, q_load=0.2),
        ],
    )


class TestAddBus:
    """Tests for System.add_bus()."""

    def test_add_bus_success(self, small_system: System) -> None:
        """New bus with unique id is added successfully."""
        original_count = small_system.num_buses
        new_bus = Bus("B3", bus_type=1, base_kv=33.0)
        small_system.add_bus(new_bus)
        assert small_system.num_buses == original_count + 1
        assert small_system.get_bus("B3") is new_bus

    def test_add_bus_duplicate_raises(self, small_system: System) -> None:
        """Duplicate bus id raises ValueError with informative message."""
        dup_bus = Bus("B1", bus_type=1)
        with pytest.raises(ValueError, match="already exists"):
            small_system.add_bus(dup_bus)

    def test_add_bus_rejects_id_used_by_other_element_type(self, small_system: System) -> None:
        """Uniqueness is system-wide: a bus cannot reuse a generator's id."""
        dup_bus = Bus("G1", bus_type=1)  # id already used by the generator
        with pytest.raises(ValueError, match="already exists"):
            small_system.add_bus(dup_bus)
        # The system is unchanged
        assert small_system.get_bus("G1") is None
        assert small_system.num_buses == 2

    def test_add_bus_ieee14(self, ieee14_system: System) -> None:
        """Add bus to IEEE 14-bus system."""
        original_count = ieee14_system.num_buses
        ieee14_system.add_bus(Bus("B15", bus_type=1, base_kv=33.0))
        assert ieee14_system.num_buses == original_count + 1


class TestAddBranch:
    """Tests for System.add_branch()."""

    def test_add_branch_success(self, small_system: System) -> None:
        """Branch with valid bus references is added."""
        small_system.add_bus(Bus("B3", bus_type=1))
        original_count = small_system.num_branches
        new_branch = Branch("BR2", "B2", "B3", r_pu=0.01, x_pu=0.05)
        small_system.add_branch(new_branch)
        assert small_system.num_branches == original_count + 1

    def test_add_branch_invalid_from_bus_raises(self, small_system: System) -> None:
        """from_bus_id not in system raises ValueError."""
        bad_branch = Branch("BR99", "B99", "B2", r_pu=0.01, x_pu=0.05)
        with pytest.raises(ValueError, match="from_bus_id 'B99' not found"):
            small_system.add_branch(bad_branch)

    def test_add_branch_invalid_to_bus_raises(self, small_system: System) -> None:
        """to_bus_id not in system raises ValueError."""
        bad_branch = Branch("BR99", "B1", "B99", r_pu=0.01, x_pu=0.05)
        with pytest.raises(ValueError, match="to_bus_id 'B99' not found"):
            small_system.add_branch(bad_branch)

    def test_add_branch_error_shows_available_ids(self, small_system: System) -> None:
        """Error message includes available bus ids."""
        bad_branch = Branch("BR99", "B1", "B99", r_pu=0.01, x_pu=0.05)
        with pytest.raises(ValueError, match="Available bus ids"):
            small_system.add_branch(bad_branch)

    def test_add_branch_duplicate_id_raises(self, small_system: System) -> None:
        """A branch id already used anywhere in the system is rejected."""
        dup_branch = Branch("BR1", "B1", "B2", r_pu=0.02, x_pu=0.2)
        with pytest.raises(ValueError, match="already exists"):
            small_system.add_branch(dup_branch)


class TestAddGenerator:
    """Tests for System.add_generator()."""

    def test_add_generator_success(self, small_system: System) -> None:
        """Generator with valid bus_id is added."""
        original_count = small_system.num_generators
        gen = Generator("G2", bus_id="B2", p_gen=0.5)
        small_system.add_generator(gen)
        assert small_system.num_generators == original_count + 1

    def test_add_generator_invalid_bus_raises(self, small_system: System) -> None:
        """Generator with non-existent bus_id raises ValueError."""
        gen = Generator("G99", bus_id="B99", p_gen=0.5)
        with pytest.raises(ValueError, match="Bus 'B99' not found"):
            small_system.add_generator(gen)

    def test_add_generator_error_suggests_add_bus(self, small_system: System) -> None:
        """Error message suggests using add_bus() first."""
        gen = Generator("G99", bus_id="B99", p_gen=0.5)
        with pytest.raises(ValueError, match="add_bus"):
            small_system.add_generator(gen)

    def test_add_generator_rejects_id_used_by_bus(self, small_system: System) -> None:
        """Uniqueness is system-wide: a generator cannot reuse a bus's id."""
        gen = Generator("B2", bus_id="B2", p_gen=0.5)  # id already used by bus B2
        with pytest.raises(ValueError, match="already exists"):
            small_system.add_generator(gen)
        assert small_system.num_generators == 1


class TestAddShunt:
    """Tests for System.add_shunt()."""

    def test_add_shunt_success(self, small_system: System) -> None:
        """Shunt with valid bus_id is added."""
        original_count = small_system.num_shunts
        shunt = Shunt("SH1", bus_id="B2", b_pu=0.05)
        small_system.add_shunt(shunt)
        assert small_system.num_shunts == original_count + 1

    def test_add_shunt_invalid_bus_raises(self, small_system: System) -> None:
        """Shunt with non-existent bus_id raises ValueError."""
        shunt = Shunt("SH99", bus_id="B99", b_pu=0.05)
        with pytest.raises(ValueError, match="Bus 'B99' not found"):
            small_system.add_shunt(shunt)


class TestAddLoad:
    """Tests for System.add_load()."""

    def test_add_load_success(self, small_system: System) -> None:
        """Load with valid bus_id is added."""
        original_count = small_system.num_loads
        load = Load("LD2", bus_id="B1", p_load=0.3, q_load=0.1)
        small_system.add_load(load)
        assert small_system.num_loads == original_count + 1

    def test_add_load_invalid_bus_raises(self, small_system: System) -> None:
        """Load with non-existent bus_id raises ValueError."""
        load = Load("LD99", bus_id="B99", p_load=0.3)
        with pytest.raises(ValueError, match="Bus 'B99' not found"):
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
        system = System(buses=[Bus("B1", bus_type=1)])
        errors = system.validate()
        assert any("slack" in e.lower() for e in errors)

    def test_validate_duplicate_bus(self, ieee14_system: System) -> None:
        """Duplicate bus id is detected."""
        ieee14_system.buses.append(Bus("B1", bus_type=1))
        errors = ieee14_system.validate()
        assert any("Duplicate id 'B1'" in e for e in errors)

    def test_validate_duplicate_id_across_element_types(self) -> None:
        """A Bus and a Generator sharing an id is detected (system-wide uniqueness)."""
        system = System(
            buses=[Bus("X", bus_type=3)],
            generators=[Generator("X", bus_id="X", p_gen=1.0)],
        )
        errors = system.validate()
        duplicate_errors = [e for e in errors if "Duplicate id 'X'" in e]
        assert len(duplicate_errors) == 1
        # The message names both element types involved
        assert "Bus" in duplicate_errors[0]
        assert "Generator" in duplicate_errors[0]

    def test_validate_invalid_id_syntax(self) -> None:
        """An id violating [A-Za-z0-9_]+ is caught by validate().

        Construction rejects such ids, so this simulates data loaded around
        __post_init__ (e.g. hand-edited JSON) by mutating the field afterward.
        """
        bus = Bus("B1", bus_type=3)
        bus.id = "B 1"  # bypass __post_init__, as hand-edited data would
        system = System(buses=[bus])
        errors = system.validate()
        assert any("Bus id 'B 1' is invalid" in e for e in errors)

    def test_validate_dangling_branch(self, ieee14_system: System) -> None:
        """Branch referencing non-existent bus is detected."""
        ieee14_system.branches.append(Branch("BR99", "B1", "B99", r_pu=0.01, x_pu=0.05))
        errors = ieee14_system.validate()
        assert any("to_bus_id 'B99' not in system" in e for e in errors)

    def test_validate_dangling_generator(self, ieee14_system: System) -> None:
        """Generator at non-existent bus is detected."""
        ieee14_system.generators.append(Generator("G99", bus_id="B99", p_gen=0.5))
        errors = ieee14_system.validate()
        assert any("bus_id 'B99' not in system" in e for e in errors)

    def test_validate_dangling_load(self, ieee14_system: System) -> None:
        """Load at non-existent bus is detected."""
        ieee14_system.loads.append(Load("LD99", bus_id="B99", p_load=0.3))
        errors = ieee14_system.validate()
        assert any("Load LD99" in e and "'B99'" in e for e in errors)

    def test_validate_dangling_shunt(self, ieee14_system: System) -> None:
        """Shunt at non-existent bus is detected."""
        ieee14_system.shunts.append(Shunt("SH99", bus_id="B99", b_pu=0.05))
        errors = ieee14_system.validate()
        assert any("Shunt SH99" in e and "'B99'" in e for e in errors)

    def test_validate_dangling_generator_cost(self) -> None:
        """GeneratorCost referencing a non-existent generator is detected."""
        system = System(
            buses=[Bus("B1", bus_type=3)],
            generators=[Generator("G1", bus_id="B1", p_gen=1.0)],
            generator_costs=[
                GeneratorCost("GC9", generator_id="G9", model=2, coefficients=[0.0, 1.0])
            ],
        )
        errors = system.validate()
        assert any(
            "GeneratorCost GC9" in e and "generator_id 'G9' not in system" in e for e in errors
        )

    def test_validate_generator_cost_reference_ok(self) -> None:
        """A GeneratorCost pointing at an existing generator raises no error."""
        system = System(
            buses=[Bus("B1", bus_type=3)],
            generators=[Generator("G1", bus_id="B1", p_gen=1.0)],
            generator_costs=[
                GeneratorCost("GC1", generator_id="G1", model=2, coefficients=[0.0, 1.0])
            ],
        )
        assert system.validate() == []

    def test_validate_case_time_bad_format_is_error(self) -> None:
        """A non-ISO-8601 case_time such as '2026/08' is an error."""
        system = System(buses=[Bus("B1", bus_type=3)], case_time="2026/08")
        errors = system.validate()
        assert any("case_time '2026/08'" in e and "ISO-8601" in e for e in errors)

    @pytest.mark.parametrize("case_time", ["2026", "2026-08", "2026-08-20T15:00"])
    def test_validate_case_time_partial_precision_ok(self, case_time: str) -> None:
        """ISO-8601 partial precision (year, month, minute) all pass."""
        system = System(buses=[Bus("B1", bus_type=3)], case_time=case_time)
        assert system.validate() == []

    def test_validate_modified_system_valid(self, ieee14_system: System) -> None:
        """System modified via add_* methods passes validation."""
        ieee14_system.add_bus(Bus("B15", bus_type=1, base_kv=33.0))
        ieee14_system.add_branch(Branch("BR21", "B14", "B15", r_pu=0.01, x_pu=0.05))
        ieee14_system.add_generator(Generator("G6", bus_id="B15", p_gen=0.5))
        errors = ieee14_system.validate()
        assert errors == []

    def test_validate_multiple_errors(self) -> None:
        """Multiple validation errors are all reported."""
        system = System(
            buses=[Bus("B1", bus_type=1)],  # no slack
            branches=[Branch("BR99", "B1", "B99", r_pu=0.01, x_pu=0.05)],  # dangling
            generators=[Generator("G88", bus_id="B88", p_gen=0.5)],  # dangling
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
                "B15",
                bus_type=1,
                v_magnitude=1.0,
                base_kv=33.0,
                name="Solar_POI",
            )
        )

        # Step 2: Add source line (connection point -> POI)
        ieee14_system.add_branch(
            Branch(
                "BR21",
                "B14",
                "B15",
                r_pu=0.01,
                x_pu=0.05,
                b_pu=0.02,
                rate_a=100.0,
            )
        )

        # Step 3: Add solar generator
        ieee14_system.add_generator(
            Generator(
                "G6",
                bus_id="B15",
                p_gen=0.5,
                q_gen=0.0,
                v_setpoint=1.0,
                machine_id="PV1",
            )
        )

        # Verify
        assert ieee14_system.num_buses == original_buses + 1
        assert ieee14_system.num_branches == original_branches + 1
        assert ieee14_system.num_generators == original_gens + 1

    def test_add_svc_to_poi(self, ieee14_system: System) -> None:
        """Simulate adding SVC at POI for voltage support."""
        ieee14_system.add_bus(Bus("B15", bus_type=1, base_kv=33.0))
        ieee14_system.add_shunt(
            Shunt(
                "SH2",
                bus_id="B15",
                g_pu=0.0,
                b_pu=0.05,
                shunt_id="SVC1",
            )
        )
        assert ieee14_system.get_bus_shunts("B15")[0].b_pu == 0.05

    def test_validation_order_matters(self, small_system: System) -> None:
        """Adding branch before bus raises, but bus-then-branch succeeds."""
        # Branch to non-existent bus B3 should fail
        with pytest.raises(ValueError):
            small_system.add_branch(Branch("BR2", "B2", "B3", r_pu=0.01, x_pu=0.05))

        # After adding bus B3, branch should succeed
        small_system.add_bus(Bus("B3", bus_type=1))
        small_system.add_branch(Branch("BR2", "B2", "B3", r_pu=0.01, x_pu=0.05))
        assert small_system.get_element("BR2") is small_system.branches[-1]


class TestDataCompleteness:
    """Tests for System.check_data_completeness() and the opt-in defaults."""

    def test_missing_ratings_are_reported(self) -> None:
        """A branch with no rate_a is reported, with its count."""
        system = System(
            buses=[Bus("B1", bus_type=3, base_kv=345.0), Bus("B2", bus_type=1, base_kv=345.0)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
        )
        issues = system.check_data_completeness()
        assert any("rate_a missing on 1/1" in i["message"] for i in issues)
        assert all(i["level"] == "warning" for i in issues)

    def test_missing_reactances_are_reported(self) -> None:
        """An in-service generator with no reactance is reported."""
        system = System(generators=[Generator("G1", bus_id="B1", p_gen=1.0)])
        issues = system.check_data_completeness()
        msg = next(i["message"] for i in issues if "reactance" in i["message"])
        assert "1/1 in-service generators" in msg
        # The direction of the error is the whole point: it reads as safe.
        assert "UNDERSTATES" in msg

    def test_out_of_service_generators_are_not_reported(self) -> None:
        """A generator that is out of service cannot understate fault current."""
        system = System(generators=[Generator("G1", bus_id="B1", p_gen=1.0, status=0)])
        assert not any("reactance" in i["message"] for i in system.check_data_completeness())

    def test_complete_system_reports_nothing(self) -> None:
        """Data that is present is not reported as missing."""
        system = System(
            buses=[Bus("B1", bus_type=3, base_kv=345.0), Bus("B2", bus_type=1, base_kv=345.0)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, rate_a=500.0)],
            generators=[Generator("G1", bus_id="B1", p_gen=1.0, xdpp_pu=0.2, xqpp_pu=0.2)],
        )
        assert system.check_data_completeness() == []

    def test_completeness_warnings_reach_validate_detailed(self) -> None:
        """validate_detailed() surfaces the same gaps."""
        system = System(
            buses=[Bus("B1", bus_type=3, base_kv=345.0), Bus("B2", bus_type=1, base_kv=345.0)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
        )
        assert any("rate_a missing" in i["message"] for i in system.validate_detailed())

    def test_missing_data_does_not_make_a_system_invalid(self) -> None:
        """Missing ratings are a warning, never an error: a power flow needs none."""
        system = System(
            buses=[Bus("B1", bus_type=3, base_kv=345.0), Bus("B2", bus_type=1, base_kv=345.0)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
        )
        assert system.validate() == []
        assert not [i for i in system.validate_detailed() if i["level"] == "error"]

    def test_assign_default_ratings_by_voltage_class(self) -> None:
        """Ratings follow the voltage class of the higher-voltage terminal."""
        system = System(
            buses=[Bus("B1", bus_type=3, base_kv=345.0), Bus("B2", bus_type=1, base_kv=138.0)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
        )
        assert system.assign_default_ratings() == 1
        assert system.branches[0].rate_a == 1200.0
        assert system.branches[0].rate_b == pytest.approx(1320.0)
        assert system.check_data_completeness() == []

    def test_assign_default_ratings_does_not_clobber_real_data(self) -> None:
        """Real ratings survive; only the missing one is filled."""
        system = System(
            buses=[Bus("B1", bus_type=3, base_kv=345.0), Bus("B2", bus_type=1, base_kv=345.0)],
            branches=[
                Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, rate_a=77.0),
                Branch("BR2", "B1", "B2", r_pu=0.01, x_pu=0.1),
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
            buses=[Bus("B1", bus_type=3, base_kv=0.6), Bus("B2", bus_type=1, base_kv=0.6)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
        )
        assert system.assign_default_ratings() == 1
        assert system.branches[0].rate_a == 50.0

    def test_assign_default_ratings_rejects_non_positive_voltage(self) -> None:
        """A base_kv of 0 has no voltage class and cannot be guessed."""
        system = System(
            buses=[Bus("B1", bus_type=3, base_kv=0.0), Bus("B2", bus_type=1, base_kv=345.0)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
        )
        with pytest.raises(ValueError, match="non-positive base_kv"):
            system.assign_default_ratings()

    def test_default_base_kv_is_flagged_as_unverified(self) -> None:
        """A bus left at the 1.0 default is rated but called out as unverified."""
        system = System(
            buses=[Bus("B1", bus_type=3), Bus("B2", bus_type=1)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
        )
        assert system.assign_default_ratings() == 1
        assert "unverified" in system.assumptions[0]

    def test_assign_default_reactances(self) -> None:
        """Machines without a reactance get the documented default."""
        system = System(
            generators=[
                Generator("G1", bus_id="B1", p_gen=1.0),
                Generator("G2", bus_id="B2", p_gen=1.0, xdpp_pu=0.15),
            ]
        )
        assert system.assign_default_reactances() == 1
        assert system.generators[0].xdpp_pu == 0.2
        assert system.generators[1].xdpp_pu == 0.15

    def test_assign_default_reactances_rejects_zero(self) -> None:
        """A zero reactance would make the machine an infinite source."""
        system = System(generators=[Generator("G1", bus_id="B1", p_gen=1.0)])
        with pytest.raises(ValueError, match="must be positive"):
            system.assign_default_reactances(xdpp_pu=0.0)

    def test_assumptions_are_declared_to_llm_context(self) -> None:
        """An LLM reading the context is told the inputs were invented."""
        system = System(
            buses=[Bus("B1", bus_type=3, base_kv=345.0), Bus("B2", bus_type=1, base_kv=345.0)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
        )
        assert "### Data Assumptions" not in system.to_llm_context()
        system.assign_default_ratings()
        ctx = system.to_llm_context()
        assert "### Data Assumptions" in ctx
        assert "rated by voltage class" in ctx

    def test_missing_data_is_declared_to_llm_context(self) -> None:
        """Gaps are surfaced even when no defaults were applied."""
        system = System(
            buses=[Bus("B1", bus_type=3, base_kv=345.0), Bus("B2", bus_type=1, base_kv=345.0)],
            branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
        )
        assert "### Missing Data" in system.to_llm_context()

    def test_assumptions_do_not_leak_between_systems(self) -> None:
        """The note is per-instance, not shared class state."""
        a = System(generators=[Generator("G1", bus_id="B1", p_gen=1.0)])
        b = System(generators=[Generator("G1", bus_id="B1", p_gen=1.0)])
        a.assign_default_reactances()
        assert len(a.assumptions) == 1
        assert b.assumptions == []
