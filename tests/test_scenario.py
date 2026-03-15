"""Tests for ScenarioSet dataclass API.

Tests Modification, ScenarioDefinition, and ScenarioSet data models
including serialization, deserialization, and resolution.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from psforge_grid import Branch, Bus, Generator, Load, Shunt, System
from psforge_grid.io import write_json
from psforge_grid.models.scenario import (
    Modification,
    ScenarioDefinition,
    ScenarioSet,
)

# =========================================================================
# Fixtures
# =========================================================================

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def simple_system() -> System:
    """Create a simple 3-bus system for testing."""
    return System(
        buses=[
            Bus(bus_id=1, bus_type=3, v_magnitude=1.06, base_kv=69.0, name="SLACK"),
            Bus(bus_id=2, bus_type=2, v_magnitude=1.04, base_kv=69.0, name="GEN2"),
            Bus(bus_id=3, bus_type=1, v_magnitude=1.00, base_kv=13.8, name="LOAD3"),
        ],
        branches=[
            Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.05, b_pu=0.02),
            Branch(from_bus=2, to_bus=3, r_pu=0.0, x_pu=0.1, tap_ratio=1.05, is_xfmr=True),
        ],
        generators=[
            Generator(bus_id=1, p_gen=1.0, q_gen=0.5, v_setpoint=1.06, p_max=2.0),
            Generator(bus_id=2, p_gen=0.8, q_gen=0.2, v_setpoint=1.04),
        ],
        loads=[
            Load(bus_id=3, p_load=1.5, q_load=0.3),
        ],
        shunts=[
            Shunt(bus_id=3, g_pu=0.0, b_pu=0.05),
        ],
        base_mva=100.0,
        name="Test 3-Bus System",
    )


# =========================================================================
# Modification Tests
# =========================================================================


class TestModification:
    """Tests for the Modification dataclass."""

    def test_valid_targets(self) -> None:
        """All 5 valid targets are accepted."""
        for target in ["buses", "branches", "generators", "loads", "shunts"]:
            mod = Modification(target=target, match={}, set_values={})
            assert mod.target == target

    def test_invalid_target_raises(self) -> None:
        """Invalid target raises ValueError in __post_init__."""
        with pytest.raises(ValueError, match="Invalid modification target"):
            Modification(target="transformers", match={}, set_values={})

    def test_to_dict_maps_set_values_to_set(self) -> None:
        """to_dict() maps set_values to 'set' key."""
        mod = Modification(
            target="branches",
            match={"from_bus": 1, "to_bus": 5},
            set_values={"status": 0},
        )
        d = mod.to_dict()
        assert d["target"] == "branches"
        assert d["match"] == {"from_bus": 1, "to_bus": 5}
        assert d["set"] == {"status": 0}
        assert "set_values" not in d

    def test_to_dict_includes_description(self) -> None:
        """to_dict() includes description when set."""
        mod = Modification(
            target="loads",
            match={"bus_id": 3},
            set_values={"p_load": 3.0},
            description="Increase load",
        )
        d = mod.to_dict()
        assert d["description"] == "Increase load"

    def test_to_dict_omits_none_description(self) -> None:
        """to_dict() omits description when None."""
        mod = Modification(target="loads", match={"bus_id": 3}, set_values={"p_load": 3.0})
        d = mod.to_dict()
        assert "description" not in d

    def test_from_dict_maps_set_to_set_values(self) -> None:
        """from_dict() maps 'set' key to set_values."""
        data = {
            "target": "branches",
            "match": {"from_bus": 1, "to_bus": 5},
            "set": {"status": 0},
        }
        mod = Modification.from_dict(data)
        assert mod.target == "branches"
        assert mod.match == {"from_bus": 1, "to_bus": 5}
        assert mod.set_values == {"status": 0}

    def test_to_description(self) -> None:
        """to_description() returns readable string."""
        mod = Modification(
            target="branches",
            match={"from_bus": 1, "to_bus": 5},
            set_values={"status": 0},
            description="Take line 1-5 out of service",
        )
        assert mod.to_description() == "Take line 1-5 out of service"

    def test_to_description_auto_generated(self) -> None:
        """to_description() auto-generates when no description set."""
        mod = Modification(
            target="branches",
            match={"from_bus": 1},
            set_values={"status": 0},
        )
        desc = mod.to_description()
        assert "branches" in desc
        assert "from_bus=1" in desc
        assert "status=0" in desc


# =========================================================================
# ScenarioDefinition Tests
# =========================================================================


class TestScenarioDefinition:
    """Tests for the ScenarioDefinition dataclass."""

    def test_create_with_modifications(self) -> None:
        """Create a ScenarioDefinition with modifications."""
        mods = [
            Modification(target="branches", match={"from_bus": 1}, set_values={"status": 0}),
            Modification(target="loads", match={"bus_id": 3}, set_values={"p_load": 3.0}),
        ]
        sd = ScenarioDefinition(name="test", modifications=mods, description="Test scenario")
        assert sd.name == "test"
        assert len(sd.modifications) == 2
        assert sd.description == "Test scenario"

    def test_to_dict_round_trip(self) -> None:
        """to_dict → from_dict preserves data."""
        mods = [
            Modification(
                target="branches",
                match={"from_bus": 1, "to_bus": 5},
                set_values={"status": 0},
                description="Line outage",
            ),
        ]
        original = ScenarioDefinition(name="N-1", modifications=mods, description="Contingency")
        d = original.to_dict()
        restored = ScenarioDefinition.from_dict(d)

        assert restored.name == original.name
        assert restored.description == original.description
        assert len(restored.modifications) == len(original.modifications)
        assert restored.modifications[0].target == "branches"
        assert restored.modifications[0].set_values == {"status": 0}

    def test_to_description(self) -> None:
        """to_description() returns multi-line readable string."""
        sd = ScenarioDefinition(
            name="N-1_Line_1-5",
            description="Line 1-5 outage",
            modifications=[
                Modification(
                    target="branches",
                    match={"from_bus": 1, "to_bus": 5},
                    set_values={"status": 0},
                ),
            ],
        )
        desc = sd.to_description()
        assert "N-1_Line_1-5" in desc
        assert "Line 1-5 outage" in desc
        assert "1 modification" in desc


# =========================================================================
# ScenarioSet Tests
# =========================================================================


class TestScenarioSet:
    """Tests for the ScenarioSet dataclass."""

    def test_resolve_includes_base(self, simple_system: System) -> None:
        """resolve() includes 'base' key."""
        ss = ScenarioSet(base=simple_system)
        result = ss.resolve()
        assert "base" in result
        assert len(result["base"].buses) == 3

    def test_resolve_applies_modifications(self, simple_system: System) -> None:
        """resolve() applies modifications to produce modified Systems."""
        ss = ScenarioSet(
            base=simple_system,
            scenarios=[
                ScenarioDefinition(
                    name="line_outage",
                    modifications=[
                        Modification(
                            target="branches",
                            match={"from_bus": 1, "to_bus": 2},
                            set_values={"status": 0},
                        ),
                    ],
                ),
            ],
        )
        result = ss.resolve()
        assert "line_outage" in result
        line_12 = [b for b in result["line_outage"].branches if b.from_bus == 1 and b.to_bus == 2]
        assert line_12[0].status == 0

    def test_resolve_independent_deep_copies(self, simple_system: System) -> None:
        """resolve() returns independent deep copies for each scenario."""
        ss = ScenarioSet(
            base=simple_system,
            scenarios=[
                ScenarioDefinition(
                    name="s1",
                    modifications=[
                        Modification(
                            target="branches",
                            match={"from_bus": 1, "to_bus": 2},
                            set_values={"status": 0},
                        ),
                    ],
                ),
            ],
        )
        result = ss.resolve()

        # Base unchanged
        assert result["base"].branches[0].status == 1
        # s1 modified
        assert result["s1"].branches[0].status == 0
        # Mutating result doesn't affect original
        result["base"].branches[0].status = 99
        assert simple_system.branches[0].status == 1

    def test_scenario_names_property(self, simple_system: System) -> None:
        """scenario_names returns list of scenario names."""
        ss = ScenarioSet(
            base=simple_system,
            scenarios=[
                ScenarioDefinition(name="a"),
                ScenarioDefinition(name="b"),
                ScenarioDefinition(name="c"),
            ],
        )
        assert ss.scenario_names == ["a", "b", "c"]

    def test_num_scenarios_property(self, simple_system: System) -> None:
        """num_scenarios returns correct count."""
        ss = ScenarioSet(
            base=simple_system,
            scenarios=[
                ScenarioDefinition(name="a"),
                ScenarioDefinition(name="b"),
            ],
        )
        assert ss.num_scenarios == 2

    def test_to_description(self, simple_system: System) -> None:
        """to_description() returns readable multi-line string."""
        ss = ScenarioSet(
            base=simple_system,
            scenarios=[
                ScenarioDefinition(name="N-1", description="Line outage"),
            ],
            base_case_path="test.psfg.json",
            name="Test Scenarios",
        )
        desc = ss.to_description()
        assert "Test Scenarios" in desc
        assert "3 buses" in desc
        assert "N-1" in desc
        assert "Line outage" in desc


# =========================================================================
# ScenarioSet JSON Tests
# =========================================================================


class TestScenarioSetJson:
    """Tests for ScenarioSet JSON I/O."""

    def test_from_json_loads_fixture(self) -> None:
        """from_json() loads the ieee14_contingencies fixture."""
        ss = ScenarioSet.from_json(FIXTURE_DIR / "ieee14_contingencies.psfg.json")
        assert ss.num_scenarios == 3
        assert ss.scenario_names == ["N-1_Line_1-5", "N-1_Line_2-3", "heavy_load_bus14"]
        assert ss.base_case_path == "ieee14.psfg.json"
        assert len(ss.base.buses) == 14

    def test_to_json_writes_valid_file(self, simple_system: System, tmp_path: Path) -> None:
        """to_json() writes a valid scenario file."""
        # Write base case
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        ss = ScenarioSet(
            base=simple_system,
            scenarios=[
                ScenarioDefinition(
                    name="test",
                    description="Test scenario",
                    modifications=[
                        Modification(
                            target="branches",
                            match={"from_bus": 1, "to_bus": 2},
                            set_values={"status": 0},
                        ),
                    ],
                ),
            ],
            base_case_path="base.psfg.json",
        )

        out_path = tmp_path / "scenarios.psfg.json"
        ss.to_json(out_path)

        # Validate written file structure
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["metadata"]["format"] == "psforge-grid-scenario"
        assert data["base_case"] == "base.psfg.json"
        assert len(data["scenarios"]) == 1
        assert data["scenarios"][0]["name"] == "test"
        assert data["scenarios"][0]["modifications"][0]["set"] == {"status": 0}

    def test_round_trip(self, simple_system: System, tmp_path: Path) -> None:
        """Write → read round-trip preserves scenario definitions."""
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        original = ScenarioSet(
            base=simple_system,
            scenarios=[
                ScenarioDefinition(
                    name="outage",
                    description="Line outage",
                    modifications=[
                        Modification(
                            target="branches",
                            match={"from_bus": 1, "to_bus": 2},
                            set_values={"status": 0},
                        ),
                    ],
                ),
                ScenarioDefinition(
                    name="heavy",
                    modifications=[
                        Modification(
                            target="loads",
                            match={"bus_id": 3},
                            set_values={"p_load": 3.0, "q_load": 0.6},
                        ),
                    ],
                ),
            ],
            base_case_path="base.psfg.json",
        )

        out_path = tmp_path / "scenarios.psfg.json"
        original.to_json(out_path)

        reloaded = ScenarioSet.from_json(out_path)
        assert reloaded.num_scenarios == 2
        assert reloaded.scenario_names == ["outage", "heavy"]
        assert reloaded.scenarios[0].description == "Line outage"
        assert reloaded.scenarios[0].modifications[0].set_values == {"status": 0}

        # Resolve and verify results match
        orig_systems = original.resolve()
        reload_systems = reloaded.resolve()
        assert (
            orig_systems["outage"].branches[0].status == reload_systems["outage"].branches[0].status
        )

    def test_to_json_requires_base_case_path(self, simple_system: System, tmp_path: Path) -> None:
        """to_json() raises ValueError if no base_case_path."""
        ss = ScenarioSet(base=simple_system)
        with pytest.raises(ValueError, match="base_case_path must be provided"):
            ss.to_json(tmp_path / "out.psfg.json")

    def test_to_json_accepts_base_case_path_argument(
        self, simple_system: System, tmp_path: Path
    ) -> None:
        """to_json() accepts base_case_path as argument."""
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        ss = ScenarioSet(base=simple_system)
        out_path = tmp_path / "scenarios.psfg.json"
        ss.to_json(out_path, base_case_path="base.psfg.json")

        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["base_case"] == "base.psfg.json"
