"""Tests for psforge-grid JSON format I/O and scenario loading.

Covers the 2.0 element schema (unified string ids, ``number``/``order``/
``tags``/``case_time``) and the read-only migration of 1.x legacy documents.
"""

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
    parse_json,
    write_json,
)
from psforge_grid.io.json_writer import FORMAT_NAME, FORMAT_VERSION
from psforge_grid.models.scenario import Modification, ScenarioSet

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def simple_system() -> System:
    """Create a simple 3-bus system for testing."""
    return System(
        buses=[
            Bus("B1", bus_type=3, v_magnitude=1.06, base_kv=69.0, number=1, name="SLACK"),
            Bus("B2", bus_type=2, v_magnitude=1.04, base_kv=69.0, number=2, name="GEN2"),
            Bus("B3", bus_type=1, v_magnitude=1.00, base_kv=13.8, number=3, name="LOAD3"),
        ],
        branches=[
            Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.05, b_pu=0.02, circuit_id="1"),
            Branch(
                "BR2",
                "B2",
                "B3",
                r_pu=0.0,
                x_pu=0.1,
                tap_ratio=1.05,
                circuit_id="1",
                is_xfmr=True,
                winding_connection="wye-wye",
                sbase_mva=50.0,
            ),
        ],
        generators=[
            Generator(
                "G1",
                bus_id="B1",
                p_gen=1.0,
                q_gen=0.5,
                v_setpoint=1.06,
                p_max=2.0,
                machine_id="1",
            ),
            Generator("G2", bus_id="B2", p_gen=0.8, q_gen=0.2, v_setpoint=1.04, machine_id="1"),
        ],
        loads=[
            Load("LD1", bus_id="B3", p_load=1.5, q_load=0.3, load_id="1"),
        ],
        shunts=[
            Shunt("SH1", bus_id="B3", g_pu=0.0, b_pu=0.05, shunt_id="1"),
        ],
        generator_costs=[
            GeneratorCost("GC1", generator_id="G1", model=2, coefficients=[0.04, 20.0, 0.0]),
        ],
        base_mva=100.0,
        frequency_hz=60.0,
        name="Test 3-Bus System",
        id="SYS3",
        tags=["purpose:testing", "size:small"],
        case_time="2026-08-20T12:00",
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
        """Writer creates a valid JSON file with 2.0 format metadata."""
        write_json(simple_system, json_output_path)
        assert json_output_path.exists()

        data = json.loads(json_output_path.read_text(encoding="utf-8"))
        assert data["metadata"]["format"] == FORMAT_NAME
        assert data["metadata"]["version"] == "2.0"
        assert data["metadata"]["version"] == FORMAT_VERSION

    def test_write_system_fields(self, simple_system: System, json_output_path: Path) -> None:
        """System-level fields including identity fields are correctly written."""
        write_json(simple_system, json_output_path)
        data = json.loads(json_output_path.read_text(encoding="utf-8"))

        assert data["system"]["name"] == "Test 3-Bus System"
        assert data["system"]["base_mva"] == 100.0
        assert data["system"]["frequency_hz"] == 60.0
        assert data["system"]["description"] == "Simple test system for JSON I/O"
        assert data["system"]["id"] == "SYS3"
        assert data["system"]["tags"] == ["purpose:testing", "size:small"]
        assert data["system"]["case_time"] == "2026-08-20T12:00"

    def test_write_element_ids(self, simple_system: System, json_output_path: Path) -> None:
        """Elements are written with unified string ids and string references."""
        write_json(simple_system, json_output_path)
        data = json.loads(json_output_path.read_text(encoding="utf-8"))

        assert data["buses"][0]["id"] == "B1"
        assert data["buses"][0]["number"] == 1
        assert data["branches"][0]["id"] == "BR1"
        assert data["branches"][0]["from_bus_id"] == "B1"
        assert data["branches"][0]["to_bus_id"] == "B2"
        assert data["generators"][0]["id"] == "G1"
        assert data["generators"][0]["bus_id"] == "B1"
        assert data["generators"][0]["machine_id"] == "1"
        assert data["loads"][0]["id"] == "LD1"
        assert data["loads"][0]["bus_id"] == "B3"
        assert data["generator_costs"][0]["id"] == "GC1"
        assert data["generator_costs"][0]["generator_id"] == "G1"

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
        """None fields and empty tags lists are omitted by default."""
        write_json(simple_system, json_output_path)
        data = json.loads(json_output_path.read_text(encoding="utf-8"))

        # Bus 1 has name set, but no description → description should be absent
        bus1 = data["buses"][0]
        assert bus1["name"] == "SLACK"
        assert "description" not in bus1
        # Empty tags list carries no information → omitted
        assert "tags" not in bus1
        # order was never assigned (system built in memory) → omitted
        assert "order" not in bus1

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
        assert bus1["order"] is None

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

    def test_round_trip_system_identity(
        self, simple_system: System, json_output_path: Path
    ) -> None:
        """System-level id, tags, and case_time survive the round-trip."""
        write_json(simple_system, json_output_path)
        loaded = parse_json(json_output_path)

        assert loaded.id == "SYS3"
        assert loaded.tags == ["purpose:testing", "size:small"]
        assert loaded.case_time == "2026-08-20T12:00"

    def test_round_trip_bus_values(self, simple_system: System, json_output_path: Path) -> None:
        """Bus field values are preserved in round-trip."""
        write_json(simple_system, json_output_path)
        loaded = parse_json(json_output_path)

        for orig, loaded_bus in zip(simple_system.buses, loaded.buses, strict=True):
            assert loaded_bus.id == orig.id
            assert loaded_bus.number == orig.number
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
        assert xfmr_loaded.id == "BR2"
        assert xfmr_loaded.from_bus_id == "B2"
        assert xfmr_loaded.to_bus_id == "B3"
        assert xfmr_loaded.circuit_id == "1"
        assert xfmr_loaded.is_xfmr is True
        assert xfmr_loaded.winding_connection == xfmr_orig.winding_connection
        assert xfmr_loaded.sbase_mva == pytest.approx(xfmr_orig.sbase_mva)

    def test_round_trip_generator_cost(self, simple_system: System, json_output_path: Path) -> None:
        """GeneratorCost data is preserved."""
        write_json(simple_system, json_output_path)
        loaded = parse_json(json_output_path)

        assert loaded.generator_costs[0].id == "GC1"
        assert loaded.generator_costs[0].generator_id == "G1"
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
# v1 (legacy) → v2 Migration Tests
# =========================================================================


def _v1_document() -> dict:
    """Build a small version-1.x psforge-grid JSON document.

    v1 identified buses by integer ``bus_id``, branches by
    ``from_bus``/``to_bus``/``circuit_id``, generators by ``bus_id``/``gen_id``,
    and generator costs by ``gen_index`` (list position). The identifier
    columns carry RAW-era fixed-width padding (``"1 "``) on purpose: the
    migration must strip it before storing the round-trip keys.
    """
    return {
        "metadata": {"format": "psforge-grid", "version": "1.0"},
        "system": {"name": "V1 Legacy System", "base_mva": 100.0},
        "buses": [
            {"bus_id": 1, "bus_type": 3, "v_magnitude": 1.06, "base_kv": 69.0, "name": "SLACK"},
            {"bus_id": 2, "bus_type": 1, "v_magnitude": 1.00, "base_kv": 69.0, "name": "LOAD2"},
        ],
        "branches": [
            {"from_bus": 1, "to_bus": 2, "circuit_id": "1 ", "r_pu": 0.01, "x_pu": 0.05},
        ],
        "generators": [
            {"bus_id": 1, "gen_id": "1 ", "p_gen": 1.0, "q_gen": 0.5},
        ],
        "loads": [
            {"bus_id": 2, "load_id": "1 ", "p_load": 0.9, "q_load": 0.3},
        ],
        "shunts": [
            {"bus_id": 2, "shunt_id": "1 ", "b_pu": 0.05},
        ],
        "generator_costs": [
            {"gen_index": 0, "model": 2, "coefficients": [0.04, 20.0, 0.0]},
        ],
    }


class TestV1Migration:
    """Tests for reading legacy 1.x documents (auto-migration to v2 schema)."""

    @pytest.fixture
    def v1_path(self, tmp_path: Path) -> Path:
        """Write the inline v1 document to a temporary file."""
        path = tmp_path / "legacy.psfg.json"
        path.write_text(json.dumps(_v1_document(), indent=2), encoding="utf-8")
        return path

    def test_v1_bus_migration(self, v1_path: Path) -> None:
        """v1 ``bus_id`` becomes ``id="B{n}"`` plus ``number=n``."""
        system = parse_json(v1_path)

        bus1, bus2 = system.buses
        assert bus1.id == "B1"
        assert bus1.number == 1
        assert bus1.name == "SLACK"
        assert bus2.id == "B2"
        assert bus2.number == 2

    def test_v1_branch_migration(self, v1_path: Path) -> None:
        """v1 ``from_bus``/``to_bus`` become string references; id is ``BR{n}``."""
        system = parse_json(v1_path)

        branch = system.branches[0]
        assert branch.id == "BR1"
        assert branch.from_bus_id == "B1"
        assert branch.to_bus_id == "B2"
        # The padded v1 column '1 ' is stripped before being stored
        assert branch.circuit_id == "1"
        assert branch.r_pu == pytest.approx(0.01)
        assert branch.x_pu == pytest.approx(0.05)

    def test_v1_generator_migration(self, v1_path: Path) -> None:
        """v1 ``gen_id`` is demoted to ``machine_id``; ``bus_id`` becomes a string ref."""
        system = parse_json(v1_path)

        gen = system.generators[0]
        assert gen.id == "G1"
        assert gen.bus_id == "B1"
        # The padded v1 gen_id '1 ' is stripped before being stored
        assert gen.machine_id == "1"
        assert gen.p_gen == pytest.approx(1.0)

    def test_v1_load_shunt_migration(self, v1_path: Path) -> None:
        """v1 loads/shunts get sequential ids and string bus references."""
        system = parse_json(v1_path)

        load = system.loads[0]
        assert load.id == "LD1"
        assert load.bus_id == "B2"
        # The padded v1 load_id '1 ' is stripped before being stored
        assert load.load_id == "1"

        shunt = system.shunts[0]
        assert shunt.id == "SH1"
        assert shunt.bus_id == "B2"
        # The padded v1 shunt_id '1 ' is stripped before being stored
        assert shunt.shunt_id == "1"

    def test_v1_generator_cost_migration(self, v1_path: Path) -> None:
        """v1 ``gen_index`` (list position) is resolved to ``generator_id``."""
        system = parse_json(v1_path)

        gc = system.generator_costs[0]
        assert gc.id == "GC1"
        assert gc.generator_id == "G1"
        assert gc.model == 2
        assert gc.coefficients == pytest.approx([0.04, 20.0, 0.0])

    def test_v1_order_assigned_from_file_position(self, v1_path: Path) -> None:
        """Migration assigns ``order`` from the position within the v1 file."""
        system = parse_json(v1_path)

        assert system.buses[0].order == pytest.approx(1.0)
        assert system.buses[1].order == pytest.approx(2.0)
        assert system.branches[0].order == pytest.approx(1.0)
        assert system.generators[0].order == pytest.approx(1.0)
        assert system.loads[0].order == pytest.approx(1.0)
        assert system.shunts[0].order == pytest.approx(1.0)
        assert system.generator_costs[0].order == pytest.approx(1.0)

    def test_v1_round_trip_writes_v2(self, v1_path: Path, tmp_path: Path) -> None:
        """A System read from v1 writes back as version 2.0 with equal elements."""
        original = parse_json(v1_path)

        out_path = tmp_path / "migrated.psfg.json"
        write_json(original, out_path)

        raw = json.loads(out_path.read_text(encoding="utf-8"))
        assert raw["metadata"]["version"] == "2.0"

        reloaded = parse_json(out_path)
        assert reloaded.buses == original.buses
        assert reloaded.branches == original.branches
        assert reloaded.generators == original.generators
        assert reloaded.loads == original.loads
        assert reloaded.shunts == original.shunts
        assert reloaded.generator_costs == original.generator_costs

    def test_v1_fixture_west10_loads_and_validates(self) -> None:
        """The v1 WEST10peak fixture migrates cleanly and passes validate()."""
        system = parse_json(FIXTURE_DIR / "WEST10peak.psfg.json")

        assert system.validate() == []
        assert system.buses[0].id == "B1"
        assert system.buses[0].number == 1
        assert len(system.buses) == 27
        assert len(system.generators) == 10


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
    """Tests for scenario loading with ScenarioSet API."""

    def _write_scenario_file(
        self,
        filepath: Path,
        base_case: str,
        scenarios: list[dict],
    ) -> None:
        """Helper to write a scenario JSON file."""
        data = {
            "metadata": {"format": "psforge-grid-scenario", "version": "1.0"},
            "base_case": base_case,
            "scenarios": scenarios,
        }
        filepath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def test_load_scenarios(self, simple_system: System, tmp_path: Path) -> None:
        """Load scenarios from a scenario file."""
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        scenario_path = tmp_path / "scenarios.psfg.json"
        self._write_scenario_file(
            scenario_path,
            base_case="base.psfg.json",
            scenarios=[
                {
                    "name": "line_outage",
                    "description": "Take out line 1-2",
                    "modifications": [
                        {
                            "target": "branches",
                            "match": {"from_bus_id": "B1", "to_bus_id": "B2"},
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
                            "match": {"bus_id": "B3"},
                            "set": {"p_load": 3.0, "q_load": 0.6},
                        }
                    ],
                },
            ],
        )

        scenario_set = ScenarioSet.from_json(scenario_path)
        scenarios = scenario_set.resolve()

        # Base case is included
        assert "base" in scenarios
        assert len(scenarios["base"].branches) == 2

        # Line outage scenario
        assert "line_outage" in scenarios
        outage = scenarios["line_outage"]
        line_12 = [b for b in outage.branches if b.id == "BR1"][0]
        assert line_12.status == 0

        # Heavy load scenario
        assert "heavy_load" in scenarios
        heavy = scenarios["heavy_load"]
        load3 = [ld for ld in heavy.loads if ld.bus_id == "B3"][0]
        assert load3.p_load == pytest.approx(3.0)
        assert load3.q_load == pytest.approx(0.6)

    def test_scenarios_independent(self, simple_system: System, tmp_path: Path) -> None:
        """Each scenario is an independent deep copy."""
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        scenario_path = tmp_path / "scenarios.psfg.json"
        self._write_scenario_file(
            scenario_path,
            base_case="base.psfg.json",
            scenarios=[
                {
                    "name": "s1",
                    "modifications": [
                        {
                            "target": "branches",
                            "match": {"id": "BR1"},
                            "set": {"status": 0},
                        }
                    ],
                },
            ],
        )

        scenarios = ScenarioSet.from_json(scenario_path).resolve()

        # Modifying s1 should not affect base
        assert scenarios["base"].branches[0].status == 1
        assert scenarios["s1"].branches[0].status == 0

    def test_scenario_invalid_target(self) -> None:
        """Invalid target raises ValueError at Modification construction."""
        with pytest.raises(ValueError, match="Invalid modification target"):
            Modification(target="transformers", match={}, set_values={"status": 0})

    def test_scenario_no_match(self, simple_system: System, tmp_path: Path) -> None:
        """Non-matching criteria raises ValueError."""
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        scenario_path = tmp_path / "scenarios.psfg.json"
        self._write_scenario_file(
            scenario_path,
            base_case="base.psfg.json",
            scenarios=[
                {
                    "name": "bad",
                    "modifications": [
                        {
                            "target": "buses",
                            "match": {"id": "B999"},
                            "set": {"v_magnitude": 1.0},
                        }
                    ],
                },
            ],
        )

        with pytest.raises(ValueError, match="No buses matched"):
            ScenarioSet.from_json(scenario_path).resolve()

    def test_scenario_invalid_field(self, simple_system: System, tmp_path: Path) -> None:
        """Invalid field name raises ValueError."""
        base_path = tmp_path / "base.psfg.json"
        write_json(simple_system, base_path)

        scenario_path = tmp_path / "scenarios.psfg.json"
        self._write_scenario_file(
            scenario_path,
            base_case="base.psfg.json",
            scenarios=[
                {
                    "name": "bad",
                    "modifications": [
                        {
                            "target": "buses",
                            "match": {"id": "B1"},
                            "set": {"nonexistent_field": 42},
                        }
                    ],
                },
            ],
        )

        with pytest.raises(ValueError, match="Invalid field"):
            ScenarioSet.from_json(scenario_path).resolve()

    def test_scenario_file_not_found(self) -> None:
        """Missing scenario file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ScenarioSet.from_json("nonexistent.psfg.json")

    def test_scenario_base_not_found(self, tmp_path: Path) -> None:
        """Missing base case raises FileNotFoundError."""
        scenario_path = tmp_path / "scenarios.psfg.json"
        self._write_scenario_file(
            scenario_path,
            base_case="missing_base.psfg.json",
            scenarios=[],
        )

        with pytest.raises(FileNotFoundError, match="Base case file not found"):
            ScenarioSet.from_json(scenario_path)

    def test_reject_non_scenario_format(self, tmp_path: Path) -> None:
        """Reject JSON with wrong format metadata."""
        bad_file = tmp_path / "bad.psfg.json"
        bad_file.write_text(
            json.dumps({"metadata": {"format": "psforge-grid"}}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Not a psforge-grid scenario file"):
            ScenarioSet.from_json(bad_file)


# =========================================================================
# IEEE 14-bus Round-trip Test (integration)
# =========================================================================


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestFixtureJsonFiles:
    """Tests using pre-generated .psfg.json fixture files.

    These fixtures are v1 (legacy) documents kept deliberately: loading them
    exercises the v1 → v2 migration path on real systems.
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
            assert json_bus.id == raw_bus.id
            assert json_bus.number == raw_bus.number
            assert json_bus.bus_type == raw_bus.bus_type
            assert json_bus.v_magnitude == pytest.approx(raw_bus.v_magnitude)
            assert json_bus.base_kv == pytest.approx(raw_bus.base_kv)

        for raw_br, json_br in zip(raw_system.branches, json_system.branches, strict=True):
            # Sequential ids (BR{n}) are generated identically by the RAW
            # parser and the v1 JSON migration, so ids match exactly.
            assert json_br.id == raw_br.id
            assert json_br.from_bus_id == raw_br.from_bus_id
            assert json_br.to_bus_id == raw_br.to_bus_id
            assert json_br.r_pu == pytest.approx(raw_br.r_pu)
            assert json_br.x_pu == pytest.approx(raw_br.x_pu)

        for raw_gen, json_gen in zip(raw_system.generators, json_system.generators, strict=True):
            assert json_gen.id == raw_gen.id
            assert json_gen.bus_id == raw_gen.bus_id
            assert json_gen.machine_id == raw_gen.machine_id

    def test_ieee9_json_matches_raw(self) -> None:
        """IEEE 9-bus JSON matches original RAW data."""
        raw_system = System.from_raw(FIXTURE_DIR / "ieee9.raw")
        json_system = parse_json(FIXTURE_DIR / "ieee9.psfg.json")

        assert len(json_system.buses) == len(raw_system.buses)
        for raw_bus, json_bus in zip(raw_system.buses, json_system.buses, strict=True):
            assert json_bus.id == raw_bus.id
            assert json_bus.number == raw_bus.number
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
            assert rt_bus.id == orig_bus.id
            assert rt_bus.number == orig_bus.number
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
    """Tests using the pre-generated scenario fixture file.

    ``ieee14_contingencies_v2.psfg.json`` matches elements with the unified
    (v2) field names — ``from_bus_id``/``to_bus_id``/``bus_id`` as string
    references — against a v1 base case migrated on load.
    """

    SCENARIO_FIXTURE = FIXTURE_DIR / "ieee14_contingencies_v2.psfg.json"

    def test_contingency_fixture_loads(self) -> None:
        """N-1 contingency scenario file loads correctly."""
        scenario_set = ScenarioSet.from_json(self.SCENARIO_FIXTURE)
        scenarios = scenario_set.resolve()
        assert "base" in scenarios
        assert "N-1_Line_1-5" in scenarios
        assert "N-1_Line_2-3" in scenarios
        assert "heavy_load_bus14" in scenarios

    def test_contingency_base_unchanged(self) -> None:
        """Base case in scenario has all branches in-service."""
        scenarios = ScenarioSet.from_json(self.SCENARIO_FIXTURE).resolve()
        base = scenarios["base"]
        assert all(b.status == 1 for b in base.branches)

    def test_contingency_line_1_5_outage(self) -> None:
        """N-1 Line 1-5 scenario has branch B1-B5 out of service."""
        scenarios = ScenarioSet.from_json(self.SCENARIO_FIXTURE).resolve()
        n1 = scenarios["N-1_Line_1-5"]
        line_1_5 = [b for b in n1.branches if b.from_bus_id == "B1" and b.to_bus_id == "B5"]
        assert len(line_1_5) == 1
        assert line_1_5[0].status == 0

        # Other branches remain in service
        other_branches = [
            b for b in n1.branches if not (b.from_bus_id == "B1" and b.to_bus_id == "B5")
        ]
        assert all(b.status == 1 for b in other_branches)

    def test_contingency_heavy_load(self) -> None:
        """Heavy load scenario doubles load at bus B14."""
        scenarios = ScenarioSet.from_json(self.SCENARIO_FIXTURE).resolve()
        heavy = scenarios["heavy_load_bus14"]
        load14 = [ld for ld in heavy.loads if ld.bus_id == "B14"]
        assert len(load14) == 1
        assert load14[0].p_load == pytest.approx(0.298)
        assert load14[0].q_load == pytest.approx(0.1)

    def test_scenarios_are_independent(self) -> None:
        """Modifications in one scenario do not affect others."""
        scenarios = ScenarioSet.from_json(self.SCENARIO_FIXTURE).resolve()
        # Base has all lines in service
        base_line_1_5 = [
            b for b in scenarios["base"].branches if b.from_bus_id == "B1" and b.to_bus_id == "B5"
        ]
        assert base_line_1_5[0].status == 1

        # N-1 has line 1-5 out
        n1_line_1_5 = [
            b
            for b in scenarios["N-1_Line_1-5"].branches
            if b.from_bus_id == "B1" and b.to_bus_id == "B5"
        ]
        assert n1_line_1_5[0].status == 0
