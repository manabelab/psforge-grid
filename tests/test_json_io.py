"""Tests for psforge-grid JSON format I/O and scenario loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from psforge_grid import Branch, Bus, Generator, GeneratorCost, Load, Shunt, System
from psforge_grid.io import (
    JsonParser,
    JsonWriter,
    ParserFactory,
    WriterFactory,
    load_scenarios,
    parse_json,
    write_json,
    write_scenario,
)
from psforge_grid.io.json_writer import FORMAT_NAME, FORMAT_VERSION

# =========================================================================
# Fixtures
# =========================================================================


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
            Branch(
                from_bus=2,
                to_bus=3,
                r_pu=0.0,
                x_pu=0.1,
                tap_ratio=1.05,
                is_xfmr=True,
                winding_connection="wye-wye",
                sbase_mva=50.0,
            ),
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
        generator_costs=[
            GeneratorCost(gen_index=0, model=2, coefficients=[0.04, 20.0, 0.0]),
        ],
        base_mva=100.0,
        frequency_hz=60.0,
        name="Test 3-Bus System",
        description="Simple test system for JSON I/O",
    )


@pytest.fixture
def json_output_path(tmp_path: Path) -> Path:
    """Provide a temporary output path."""
    return tmp_path / "output.psfg.json"


# =========================================================================
# JsonWriter Tests
# =========================================================================


class TestJsonWriter:
    """Tests for JsonWriter."""

    def test_write_creates_file(self, simple_system: System, json_output_path: Path) -> None:
        """Writer creates a valid JSON file."""
        write_json(simple_system, json_output_path)
        assert json_output_path.exists()

        data = json.loads(json_output_path.read_text(encoding="utf-8"))
        assert data["metadata"]["format"] == FORMAT_NAME
        assert data["metadata"]["version"] == FORMAT_VERSION

    def test_write_system_fields(self, simple_system: System, json_output_path: Path) -> None:
        """System-level fields are correctly written."""
        write_json(simple_system, json_output_path)
        data = json.loads(json_output_path.read_text(encoding="utf-8"))

        assert data["system"]["name"] == "Test 3-Bus System"
        assert data["system"]["base_mva"] == 100.0
        assert data["system"]["frequency_hz"] == 60.0
        assert data["system"]["description"] == "Simple test system for JSON I/O"

    def test_write_component_counts(self, simple_system: System, json_output_path: Path) -> None:
        """Correct number of components in output."""
        write_json(simple_system, json_output_path)
        data = json.loads(json_output_path.read_text(encoding="utf-8"))

        assert len(data["buses"]) == 3
        assert len(data["branches"]) == 2
        assert len(data["generators"]) == 2
        assert len(data["loads"]) == 1
        assert len(data["shunts"]) == 1
        assert len(data["generator_costs"]) == 1

    def test_write_omit_none(self, simple_system: System, json_output_path: Path) -> None:
        """None fields are omitted by default."""
        write_json(simple_system, json_output_path)
        data = json.loads(json_output_path.read_text(encoding="utf-8"))

        # Bus 1 has name set, but no description → description should be absent
        bus1 = data["buses"][0]
        assert bus1["name"] == "SLACK"
        assert "description" not in bus1

        # Line branch has no winding_connection → absent
        line = data["branches"][0]
        assert "winding_connection" not in line

        # Transformer branch has winding_connection → present
        xfmr = data["branches"][1]
        assert xfmr["winding_connection"] == "wye-wye"

    def test_write_include_none(self, simple_system: System, json_output_path: Path) -> None:
        """When omit_none=False, None fields appear as null."""
        write_json(simple_system, json_output_path, omit_none=False)
        data = json.loads(json_output_path.read_text(encoding="utf-8"))

        bus1 = data["buses"][0]
        assert bus1["description"] is None

    def test_writer_class(self, simple_system: System, json_output_path: Path) -> None:
        """JsonWriter class implements IWriter correctly."""
        writer = JsonWriter()
        assert "psfg.json" in writer.supported_extensions
        assert writer.format_name == "psforge-grid JSON"
        writer.write(simple_system, json_output_path)
        assert json_output_path.exists()


# =========================================================================
# JsonParser Tests
# =========================================================================


class TestJsonParser:
    """Tests for JsonParser."""

    def test_round_trip(self, simple_system: System, json_output_path: Path) -> None:
        """Write → read round-trip preserves data."""
        write_json(simple_system, json_output_path)
        loaded = parse_json(json_output_path)

        assert loaded.name == simple_system.name
        assert loaded.base_mva == simple_system.base_mva
        assert loaded.frequency_hz == simple_system.frequency_hz
        assert loaded.description == simple_system.description

        assert len(loaded.buses) == len(simple_system.buses)
        assert len(loaded.branches) == len(simple_system.branches)
        assert len(loaded.generators) == len(simple_system.generators)
        assert len(loaded.loads) == len(simple_system.loads)
        assert len(loaded.shunts) == len(simple_system.shunts)
        assert len(loaded.generator_costs) == len(simple_system.generator_costs)

    def test_round_trip_bus_values(self, simple_system: System, json_output_path: Path) -> None:
        """Bus field values are preserved in round-trip."""
        write_json(simple_system, json_output_path)
        loaded = parse_json(json_output_path)

        for orig, loaded_bus in zip(simple_system.buses, loaded.buses, strict=True):
            assert loaded_bus.bus_id == orig.bus_id
            assert loaded_bus.bus_type == orig.bus_type
            assert loaded_bus.v_magnitude == pytest.approx(orig.v_magnitude)
            assert loaded_bus.base_kv == pytest.approx(orig.base_kv)
            assert loaded_bus.name == orig.name

    def test_round_trip_branch_values(self, simple_system: System, json_output_path: Path) -> None:
        """Branch field values including Optional fields are preserved."""
        write_json(simple_system, json_output_path)
        loaded = parse_json(json_output_path)

        xfmr_orig = simple_system.branches[1]
        xfmr_loaded = loaded.branches[1]
        assert xfmr_loaded.is_xfmr is True
        assert xfmr_loaded.winding_connection == xfmr_orig.winding_connection
        assert xfmr_loaded.sbase_mva == pytest.approx(xfmr_orig.sbase_mva)

    def test_round_trip_generator_cost(self, simple_system: System, json_output_path: Path) -> None:
        """GeneratorCost data is preserved."""
        write_json(simple_system, json_output_path)
        loaded = parse_json(json_output_path)

        assert loaded.generator_costs[0].model == 2
        assert loaded.generator_costs[0].coefficients == pytest.approx([0.04, 20.0, 0.0])

    def test_reject_non_psforge_json(self, tmp_path: Path) -> None:
        """Parser rejects JSON files without psforge-grid format metadata."""
        pglib_file = tmp_path / "pglib.json"
        pglib_file.write_text(
            json.dumps({"generators": [], "buses": []}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Not a psforge-grid JSON file"):
            parse_json(pglib_file)

    def test_file_not_found(self) -> None:
        """Parser raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            parse_json("nonexistent.psfg.json")

    def test_parser_class(self, simple_system: System, json_output_path: Path) -> None:
        """JsonParser class implements IParser correctly."""
        write_json(simple_system, json_output_path)
        parser = JsonParser()
        assert "psfg.json" in parser.supported_extensions
        assert parser.format_name == "psforge-grid JSON"
        loaded = parser.parse(json_output_path)
        assert len(loaded.buses) == 3


# =========================================================================
# Factory Tests
# =========================================================================


class TestFactoryIntegration:
    """Tests for factory registration."""

    def test_parser_factory_create(self) -> None:
        """ParserFactory creates JsonParser for 'json' format."""
        parser = ParserFactory.create("json")
        assert isinstance(parser, JsonParser)

    def test_writer_factory_create(self) -> None:
        """WriterFactory creates JsonWriter for 'json' format."""
        writer = WriterFactory.create("json")
        assert isinstance(writer, JsonWriter)

    def test_parser_factory_from_path(self, simple_system: System, tmp_path: Path) -> None:
        """ParserFactory detects .psfg.json extension."""
        outpath = tmp_path / "test.psfg.json"
        write_json(simple_system, outpath)
        parser = ParserFactory.from_path(outpath)
        assert isinstance(parser, JsonParser)

    def test_writer_factory_from_path(self) -> None:
        """WriterFactory detects .psfg.json extension."""
        writer = WriterFactory.from_path("output.psfg.json")
        assert isinstance(writer, JsonWriter)

    def test_system_to_json(self, simple_system: System, json_output_path: Path) -> None:
        """System.to_json() facade method works."""
        simple_system.to_json(json_output_path)
        assert json_output_path.exists()
        loaded = System.from_json(json_output_path)
        assert len(loaded.buses) == 3

    def test_system_to_file_json(self, simple_system: System, tmp_path: Path) -> None:
        """System.to_file() auto-detects .psfg.json."""
        outpath = tmp_path / "test.psfg.json"
        simple_system.to_file(outpath)
        assert outpath.exists()


# =========================================================================
# Scenario Loader Tests
# =========================================================================


class TestScenarioLoader:
    """Tests for scenario loading with base case + modifications."""

    def test_load_scenarios(self, simple_system: System, tmp_path: Path) -> None:
        """Load scenarios from a scenario file."""
        # Write base case
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        # Write scenario file
        scenario_path = tmp_path / "scenarios.psfg.json"
        write_scenario(
            scenario_path,
            base_case="base.psfg.json",
            scenarios=[
                {
                    "name": "line_outage",
                    "description": "Take out line 1-2",
                    "modifications": [
                        {
                            "target": "branches",
                            "match": {"from_bus": 1, "to_bus": 2},
                            "set": {"status": 0},
                        }
                    ],
                },
                {
                    "name": "heavy_load",
                    "description": "Increase load at bus 3",
                    "modifications": [
                        {
                            "target": "loads",
                            "match": {"bus_id": 3},
                            "set": {"p_load": 3.0, "q_load": 0.6},
                        }
                    ],
                },
            ],
        )

        scenarios = load_scenarios(scenario_path)

        # Base case is included
        assert "base" in scenarios
        assert len(scenarios["base"].branches) == 2

        # Line outage scenario
        assert "line_outage" in scenarios
        outage = scenarios["line_outage"]
        line_12 = [b for b in outage.branches if b.from_bus == 1 and b.to_bus == 2][0]
        assert line_12.status == 0

        # Heavy load scenario
        assert "heavy_load" in scenarios
        heavy = scenarios["heavy_load"]
        load3 = [ld for ld in heavy.loads if ld.bus_id == 3][0]
        assert load3.p_load == pytest.approx(3.0)
        assert load3.q_load == pytest.approx(0.6)

    def test_scenarios_independent(self, simple_system: System, tmp_path: Path) -> None:
        """Each scenario is an independent deep copy."""
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        scenario_path = tmp_path / "scenarios.psfg.json"
        write_scenario(
            scenario_path,
            base_case="base.psfg.json",
            scenarios=[
                {
                    "name": "s1",
                    "modifications": [
                        {
                            "target": "branches",
                            "match": {"from_bus": 1, "to_bus": 2},
                            "set": {"status": 0},
                        }
                    ],
                },
            ],
        )

        scenarios = load_scenarios(scenario_path)

        # Modifying s1 should not affect base
        assert scenarios["base"].branches[0].status == 1
        assert scenarios["s1"].branches[0].status == 0

    def test_scenario_invalid_target(self, simple_system: System, tmp_path: Path) -> None:
        """Invalid target raises ValueError."""
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        scenario_path = tmp_path / "scenarios.psfg.json"
        write_scenario(
            scenario_path,
            base_case="base.psfg.json",
            scenarios=[
                {
                    "name": "bad",
                    "modifications": [
                        {
                            "target": "transformers",
                            "match": {},
                            "set": {"status": 0},
                        }
                    ],
                },
            ],
        )

        with pytest.raises(ValueError, match="Invalid modification target"):
            load_scenarios(scenario_path)

    def test_scenario_no_match(self, simple_system: System, tmp_path: Path) -> None:
        """Non-matching criteria raises ValueError."""
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        scenario_path = tmp_path / "scenarios.psfg.json"
        write_scenario(
            scenario_path,
            base_case="base.psfg.json",
            scenarios=[
                {
                    "name": "bad",
                    "modifications": [
                        {
                            "target": "buses",
                            "match": {"bus_id": 999},
                            "set": {"v_magnitude": 1.0},
                        }
                    ],
                },
            ],
        )

        with pytest.raises(ValueError, match="No buses matched"):
            load_scenarios(scenario_path)

    def test_scenario_invalid_field(self, simple_system: System, tmp_path: Path) -> None:
        """Invalid field name raises ValueError."""
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        scenario_path = tmp_path / "scenarios.psfg.json"
        write_scenario(
            scenario_path,
            base_case="base.psfg.json",
            scenarios=[
                {
                    "name": "bad",
                    "modifications": [
                        {
                            "target": "buses",
                            "match": {"bus_id": 1},
                            "set": {"nonexistent_field": 42},
                        }
                    ],
                },
            ],
        )

        with pytest.raises(ValueError, match="Invalid field"):
            load_scenarios(scenario_path)

    def test_scenario_file_not_found(self) -> None:
        """Missing scenario file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_scenarios("nonexistent.psfg.json")

    def test_scenario_base_not_found(self, tmp_path: Path) -> None:
        """Missing base case raises FileNotFoundError."""
        scenario_path = tmp_path / "scenarios.psfg.json"
        write_scenario(
            scenario_path,
            base_case="missing_base.psfg.json",
            scenarios=[],
        )

        with pytest.raises(FileNotFoundError, match="Base case file not found"):
            load_scenarios(scenario_path)

    def test_reject_non_scenario_format(self, tmp_path: Path) -> None:
        """Reject JSON with wrong format metadata."""
        bad_file = tmp_path / "bad.psfg.json"
        bad_file.write_text(
            json.dumps({"metadata": {"format": "psforge-grid"}}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Not a psforge-grid scenario file"):
            load_scenarios(bad_file)


# =========================================================================
# IEEE 14-bus Round-trip Test (integration)
# =========================================================================


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestFixtureJsonFiles:
    """Tests using pre-generated .psfg.json fixture files.

    These tests verify that the fixture JSON files can be loaded
    and match the original source data.
    """

    def test_ieee14_json_fixture_loads(self) -> None:
        """IEEE 14-bus .psfg.json fixture loads correctly."""
        system = parse_json(FIXTURE_DIR / "ieee14.psfg.json")
        assert len(system.buses) == 14
        assert len(system.branches) == 20
        assert len(system.generators) == 5
        assert len(system.loads) == 11
        assert len(system.shunts) == 1
        assert system.base_mva == pytest.approx(100.0)

    def test_ieee9_json_fixture_loads(self) -> None:
        """IEEE 9-bus .psfg.json fixture loads correctly."""
        system = parse_json(FIXTURE_DIR / "ieee9.psfg.json")
        assert len(system.buses) == 9
        assert len(system.branches) == 9
        assert len(system.generators) == 3
        assert len(system.loads) == 3

    def test_west10_json_fixture_loads(self) -> None:
        """WEST10peak .psfg.json fixture loads correctly."""
        system = parse_json(FIXTURE_DIR / "WEST10peak.psfg.json")
        assert len(system.buses) == 27
        assert len(system.generators) == 10
        assert len(system.loads) == 17
        assert system.base_mva == pytest.approx(1000.0)

    def test_ieee14_json_matches_raw(self) -> None:
        """IEEE 14-bus JSON matches original RAW data."""
        raw_system = System.from_raw(FIXTURE_DIR / "ieee14.raw")
        json_system = parse_json(FIXTURE_DIR / "ieee14.psfg.json")

        assert len(json_system.buses) == len(raw_system.buses)
        assert len(json_system.branches) == len(raw_system.branches)
        assert len(json_system.generators) == len(raw_system.generators)

        for raw_bus, json_bus in zip(raw_system.buses, json_system.buses, strict=True):
            assert json_bus.bus_id == raw_bus.bus_id
            assert json_bus.bus_type == raw_bus.bus_type
            assert json_bus.v_magnitude == pytest.approx(raw_bus.v_magnitude)
            assert json_bus.base_kv == pytest.approx(raw_bus.base_kv)

        for raw_br, json_br in zip(raw_system.branches, json_system.branches, strict=True):
            assert json_br.from_bus == raw_br.from_bus
            assert json_br.to_bus == raw_br.to_bus
            assert json_br.r_pu == pytest.approx(raw_br.r_pu)
            assert json_br.x_pu == pytest.approx(raw_br.x_pu)

    def test_ieee9_json_matches_raw(self) -> None:
        """IEEE 9-bus JSON matches original RAW data."""
        raw_system = System.from_raw(FIXTURE_DIR / "ieee9.raw")
        json_system = parse_json(FIXTURE_DIR / "ieee9.psfg.json")

        assert len(json_system.buses) == len(raw_system.buses)
        for raw_bus, json_bus in zip(raw_system.buses, json_system.buses, strict=True):
            assert json_bus.bus_id == raw_bus.bus_id
            assert json_bus.v_magnitude == pytest.approx(raw_bus.v_magnitude)

    def test_west10_json_matches_pop(self) -> None:
        """WEST10peak JSON matches original POP data."""
        pop_system = System.from_pop(FIXTURE_DIR / "WEST10peak.pop")
        json_system = parse_json(FIXTURE_DIR / "WEST10peak.psfg.json")

        assert len(json_system.buses) == len(pop_system.buses)
        assert len(json_system.generators) == len(pop_system.generators)
        for pop_gen, json_gen in zip(pop_system.generators, json_system.generators, strict=True):
            assert json_gen.bus_id == pop_gen.bus_id
            assert json_gen.p_gen == pytest.approx(pop_gen.p_gen)

    def test_ieee14_json_round_trip(self, tmp_path: Path) -> None:
        """JSON → System → JSON produces identical output."""
        original = parse_json(FIXTURE_DIR / "ieee14.psfg.json")
        round_trip_path = tmp_path / "ieee14_rt.psfg.json"
        write_json(original, round_trip_path)
        reloaded = parse_json(round_trip_path)

        assert len(reloaded.buses) == len(original.buses)
        assert len(reloaded.branches) == len(original.branches)
        for orig_bus, rt_bus in zip(original.buses, reloaded.buses, strict=True):
            assert rt_bus.bus_id == orig_bus.bus_id
            assert rt_bus.v_magnitude == pytest.approx(orig_bus.v_magnitude)

    def test_system_from_json_facade(self) -> None:
        """System.from_json() loads fixture correctly."""
        system = System.from_json(FIXTURE_DIR / "ieee14.psfg.json")
        assert len(system.buses) == 14

    def test_system_from_file_auto_detect(self) -> None:
        """System.from_file() auto-detects .psfg.json."""
        system = System.from_file(FIXTURE_DIR / "ieee14.psfg.json")
        assert len(system.buses) == 14


class TestFixtureScenario:
    """Tests using pre-generated scenario fixture file."""

    def test_contingency_fixture_loads(self) -> None:
        """N-1 contingency scenario file loads correctly."""
        scenarios = load_scenarios(FIXTURE_DIR / "ieee14_contingencies.psfg.json")
        assert "base" in scenarios
        assert "N-1_Line_1-5" in scenarios
        assert "N-1_Line_2-3" in scenarios
        assert "heavy_load_bus14" in scenarios

    def test_contingency_base_unchanged(self) -> None:
        """Base case in scenario has all branches in-service."""
        scenarios = load_scenarios(FIXTURE_DIR / "ieee14_contingencies.psfg.json")
        base = scenarios["base"]
        assert all(b.status == 1 for b in base.branches)

    def test_contingency_line_1_5_outage(self) -> None:
        """N-1 Line 1-5 scenario has branch 1-5 out of service."""
        scenarios = load_scenarios(FIXTURE_DIR / "ieee14_contingencies.psfg.json")
        n1 = scenarios["N-1_Line_1-5"]
        line_1_5 = [b for b in n1.branches if b.from_bus == 1 and b.to_bus == 5]
        assert len(line_1_5) == 1
        assert line_1_5[0].status == 0

        # Other branches remain in service
        other_branches = [b for b in n1.branches if not (b.from_bus == 1 and b.to_bus == 5)]
        assert all(b.status == 1 for b in other_branches)

    def test_contingency_heavy_load(self) -> None:
        """Heavy load scenario doubles load at bus 14."""
        scenarios = load_scenarios(FIXTURE_DIR / "ieee14_contingencies.psfg.json")
        heavy = scenarios["heavy_load_bus14"]
        load14 = [ld for ld in heavy.loads if ld.bus_id == 14]
        assert len(load14) == 1
        assert load14[0].p_load == pytest.approx(29.5)
        assert load14[0].q_load == pytest.approx(10.0)

    def test_scenarios_are_independent(self) -> None:
        """Modifications in one scenario do not affect others."""
        scenarios = load_scenarios(FIXTURE_DIR / "ieee14_contingencies.psfg.json")
        # Base has all lines in service
        base_line_1_5 = [b for b in scenarios["base"].branches if b.from_bus == 1 and b.to_bus == 5]
        assert base_line_1_5[0].status == 1

        # N-1 has line 1-5 out
        n1_line_1_5 = [
            b for b in scenarios["N-1_Line_1-5"].branches if b.from_bus == 1 and b.to_bus == 5
        ]
        assert n1_line_1_5[0].status == 0
