"""Tests for psforge-grid CLI.

These tests verify the CLI commands work correctly with various inputs
and output formats.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from psforge_grid.cli.app import app

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_pattern.sub("", text)


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
IEEE14_RAW = FIXTURES_DIR / "ieee14.raw"
IEEE9_RAW = FIXTURES_DIR / "ieee9.raw"
IEEE14_MATPOWER = FIXTURES_DIR / "pglib_opf_case14_ieee.m"
IEEE14_JSON = FIXTURES_DIR / "ieee14.psfg.json"
WEST10_POP = FIXTURES_DIR / "WEST10peak.pop"


class TestInfoCommand:
    """Tests for the 'info' command."""

    def test_info_basic(self) -> None:
        """Test basic info command with table output."""
        result = runner.invoke(app, ["info", str(IEEE14_RAW)])
        assert result.exit_code == 0
        assert "System Overview" in result.stdout or "Buses" in result.stdout

    def test_info_json_format(self) -> None:
        """Test info command with JSON output."""
        result = runner.invoke(app, ["info", str(IEEE14_RAW), "-f", "json"])
        assert result.exit_code == 0

        # Verify valid JSON
        output = result.stdout.strip()
        data = json.loads(output)
        assert "system" in data
        assert "counts" in data
        assert "bus_types" in data
        assert "power_balance" in data

        # Check expected values for IEEE 14-bus
        assert data["counts"]["buses"] == 14

    def test_info_summary_format(self) -> None:
        """Test info command with summary output."""
        result = runner.invoke(app, ["info", str(IEEE14_RAW), "-f", "summary"])
        assert result.exit_code == 0
        assert "14 buses" in result.stdout
        assert "MVA" in result.stdout

    def test_info_csv_format(self) -> None:
        """Test info command with CSV output."""
        result = runner.invoke(app, ["info", str(IEEE14_RAW), "-f", "csv"])
        assert result.exit_code == 0
        assert "property,value" in result.stdout
        assert "num_buses,14" in result.stdout

    def test_info_verbose(self) -> None:
        """Test info command with verbose flag."""
        result = runner.invoke(app, ["info", str(IEEE14_RAW), "-v"])
        assert result.exit_code == 0
        assert "Loading:" in result.stdout

    def test_info_nonexistent_file(self) -> None:
        """Test info command with non-existent file."""
        result = runner.invoke(app, ["info", "nonexistent.raw"])
        assert result.exit_code != 0

    def test_info_invalid_format(self) -> None:
        """Test info command with invalid format."""
        result = runner.invoke(app, ["info", str(IEEE14_RAW), "-f", "invalid"])
        assert result.exit_code == 1
        # Error message may be in stdout or stderr depending on console configuration
        assert result.exit_code != 0  # Command should fail


class TestShowCommand:
    """Tests for the 'show' command."""

    def test_show_buses(self) -> None:
        """Test show buses command."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Bus" in output
        # Table lists buses by unified string id
        assert "B1" in output

    def test_show_buses_json(self) -> None:
        """Test show buses command with JSON output."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses", "-f", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "buses" in data
        assert len(data["buses"]) == 14
        assert data["buses"][0]["id"] == "B1"
        assert data["buses"][0]["number"] == 1

    def test_show_branches(self) -> None:
        """Test show branches command."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "branches"])
        assert result.exit_code == 0
        assert "From" in result.stdout or "from_bus" in result.stdout

    def test_show_branches_json(self) -> None:
        """Test show branches command with JSON output."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "branches", "-f", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "branches" in data
        assert len(data["branches"]) == 20
        first = data["branches"][0]
        assert first["id"] == "BR1"
        assert first["from_bus_id"] == "B1"
        assert first["to_bus_id"] == "B2"

    def test_show_generators(self) -> None:
        """Test show generators command."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "generators"])
        assert result.exit_code == 0

    def test_show_generators_json(self) -> None:
        """Test show generators command with JSON output."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "generators", "-f", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "generators" in data
        assert data["generators"][0]["id"] == "G1"
        assert data["generators"][0]["bus_id"] == "B1"

    def test_show_loads(self) -> None:
        """Test show loads command."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "loads"])
        assert result.exit_code == 0

    def test_show_all(self) -> None:
        """Test show all elements command."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "all"])
        assert result.exit_code == 0

    def test_show_csv_format(self) -> None:
        """Test show command with CSV output uses unified id header."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses", "-f", "csv"])
        assert result.exit_code == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0] == "id,number,name,type,v_pu,angle_deg,base_kv,status"
        assert lines[1].startswith("B1,1,")

    def test_show_csv_branches_header(self) -> None:
        """Branch CSV output uses id and string bus references."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "branches", "-f", "csv"])
        assert result.exit_code == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0] == "id,from_bus_id,to_bus_id,r_pu,x_pu,b_pu,rate_a,in_service"
        assert lines[1].startswith("BR1,B1,B2,")

    def test_show_element_id_bus(self) -> None:
        """The element_id argument selects a single bus by unified id."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses", "B1", "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["buses"]) == 1
        assert data["buses"][0]["id"] == "B1"

    def test_show_element_id_branch(self) -> None:
        """The element_id argument selects a single branch by unified id."""
        # BR2 is the second branch in ieee14.raw: line 1-5
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "branches", "BR2", "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["branches"]) == 1
        assert data["branches"][0]["from_bus_id"] == "B1"
        assert data["branches"][0]["to_bus_id"] == "B5"

    def test_show_element_id_generator_by_bus(self) -> None:
        """Generators also match on the id of their connected bus."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "generators", "B1", "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["generators"]) == 1
        assert data["generators"][0]["id"] == "G1"
        assert data["generators"][0]["bus_id"] == "B1"

    def test_show_summary_format(self) -> None:
        """Test show command with summary output."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses", "-f", "summary"])
        assert result.exit_code == 0
        assert "Buses" in result.stdout


class TestValidateCommand:
    """Tests for the 'validate' command."""

    def test_validate_basic(self) -> None:
        """Test basic validate command."""
        result = runner.invoke(app, ["validate", str(IEEE14_RAW)])
        # Should pass or give warnings (not errors) for valid files
        assert result.exit_code == 0 or "warning" in result.stdout.lower()

    def test_validate_json_format(self) -> None:
        """Test validate command with JSON output."""
        result = runner.invoke(app, ["validate", str(IEEE14_RAW), "-f", "json"])

        data = json.loads(result.stdout)
        assert "status" in data
        assert "issues" in data

    def test_validate_summary_format(self) -> None:
        """Test validate command with summary output."""
        result = runner.invoke(app, ["validate", str(IEEE14_RAW), "-f", "summary"])
        assert "Validation" in result.stdout

    def test_validate_strict_mode(self) -> None:
        """Test validate command with strict mode."""
        result = runner.invoke(app, ["validate", str(IEEE14_RAW), "--strict"])
        # Result depends on data quality - just check it doesn't crash
        assert result.exit_code in (0, 1)  # Either pass or fail based on data


class TestVersionAndHelp:
    """Tests for version and help commands."""

    def test_version(self) -> None:
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "psforge-grid" in result.stdout

    def test_help(self) -> None:
        """Test --help flag."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "info" in result.stdout
        assert "show" in result.stdout
        assert "validate" in result.stdout

    def test_info_help(self) -> None:
        """Test info --help."""
        result = runner.invoke(app, ["info", "--help"])
        assert result.exit_code == 0
        # Strip ANSI codes before checking (Typer adds color formatting)
        assert "--format" in strip_ansi(result.stdout)

    def test_show_help(self) -> None:
        """Test show --help."""
        result = runner.invoke(app, ["show", "--help"])
        assert result.exit_code == 0

    def test_validate_help(self) -> None:
        """Test validate --help."""
        result = runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        # Strip ANSI codes before checking (Typer adds color formatting)
        assert "--strict" in strip_ansi(result.stdout)


class TestLLMAffinityOutput:
    """Tests for LLM affinity features in output."""

    def test_json_has_explicit_units(self) -> None:
        """Test that JSON output includes explicit unit suffixes."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses", "-f", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        bus = data["buses"][0]

        # Check explicit unit naming
        assert "voltage_pu" in bus
        assert "angle_deg" in bus
        assert "base_kv" in bus

    def test_json_has_semantic_annotation(self) -> None:
        """Test that JSON output includes voltage status annotation."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses", "-f", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        bus = data["buses"][0]

        # Check semantic annotation
        assert "voltage_status" in bus
        assert bus["voltage_status"] in ["CRITICAL_LOW", "LOW", "NORMAL", "HIGH", "CRITICAL_HIGH"]

    def test_summary_is_compact(self) -> None:
        """Test that summary output is compact for token efficiency."""
        result = runner.invoke(app, ["info", str(IEEE14_RAW), "-f", "summary"])
        assert result.exit_code == 0

        lines = result.stdout.strip().split("\n")
        # Summary should be concise (typically 4-5 lines for system info)
        assert len(lines) <= 10

    def test_summary_has_semantic_annotation(self) -> None:
        """Test that summary output includes status annotations."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses", "-f", "summary"])
        assert result.exit_code == 0

        # Should include status annotations like (NORMAL)
        assert "NORMAL" in result.stdout or "LOW" in result.stdout or "HIGH" in result.stdout


class TestMultiFormatInput:
    """Tests for multi-format input support (auto-detection)."""

    def test_info_matpower(self) -> None:
        """Test info command with MATPOWER file."""
        result = runner.invoke(app, ["info", str(IEEE14_MATPOWER)])
        assert result.exit_code == 0

    def test_info_matpower_json(self) -> None:
        """Test info command with MATPOWER file and JSON output."""
        result = runner.invoke(app, ["info", str(IEEE14_MATPOWER), "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["counts"]["buses"] == 14

    def test_info_json_format(self) -> None:
        """Test info command with psforge JSON file."""
        result = runner.invoke(app, ["info", str(IEEE14_JSON)])
        assert result.exit_code == 0

    def test_info_pop_format(self) -> None:
        """Test info command with CPAT .pop file."""
        result = runner.invoke(app, ["info", str(WEST10_POP), "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["counts"]["buses"] == 27

    def test_show_matpower_buses(self) -> None:
        """Test show buses with MATPOWER file."""
        result = runner.invoke(app, ["show", str(IEEE14_MATPOWER), "buses", "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["buses"]) == 14

    def test_validate_matpower(self) -> None:
        """Test validate with MATPOWER file."""
        result = runner.invoke(app, ["validate", str(IEEE14_MATPOWER)])
        assert result.exit_code in (0, 1)

    def test_validate_json(self) -> None:
        """Test validate with psforge JSON file."""
        result = runner.invoke(app, ["validate", str(IEEE14_JSON)])
        assert result.exit_code in (0, 1)


class TestConvertCommand:
    """Tests for the 'convert' command."""

    def test_convert_raw_to_json(self, tmp_path: Path) -> None:
        """Test converting RAW to psforge JSON."""
        output = tmp_path / "ieee14.psfg.json"
        result = runner.invoke(app, ["convert", str(IEEE14_RAW), str(output)])
        assert result.exit_code == 0
        assert output.exists()
        assert "14 buses" in result.stdout

    def test_convert_raw_to_matpower(self, tmp_path: Path) -> None:
        """Test converting RAW to MATPOWER."""
        output = tmp_path / "ieee14.m"
        result = runner.invoke(app, ["convert", str(IEEE14_RAW), str(output)])
        assert result.exit_code == 0
        assert output.exists()

    def test_convert_matpower_to_json(self, tmp_path: Path) -> None:
        """Test converting MATPOWER to psforge JSON."""
        output = tmp_path / "case14.psfg.json"
        result = runner.invoke(app, ["convert", str(IEEE14_MATPOWER), str(output)])
        assert result.exit_code == 0
        assert output.exists()

    def test_convert_json_to_raw(self, tmp_path: Path) -> None:
        """Test converting psforge JSON to RAW."""
        output = tmp_path / "ieee14.raw"
        result = runner.invoke(app, ["convert", str(IEEE14_JSON), str(output)])
        assert result.exit_code == 0
        assert output.exists()

    def test_convert_pop_to_json(self, tmp_path: Path) -> None:
        """Test converting CPAT .pop to psforge JSON."""
        output = tmp_path / "west10.psfg.json"
        result = runner.invoke(app, ["convert", str(WEST10_POP), str(output)])
        assert result.exit_code == 0
        assert output.exists()

    def test_convert_verbose(self, tmp_path: Path) -> None:
        """Test convert command with verbose flag."""
        output = tmp_path / "ieee14.psfg.json"
        result = runner.invoke(app, ["convert", str(IEEE14_RAW), str(output), "-v"])
        assert result.exit_code == 0
        assert "Loading:" in result.stdout
        assert "Written:" in result.stdout

    def test_convert_nonexistent_input(self, tmp_path: Path) -> None:
        """Test convert with non-existent input file."""
        output = tmp_path / "out.psfg.json"
        result = runner.invoke(app, ["convert", "nonexistent.raw", str(output)])
        assert result.exit_code != 0

    def test_convert_unknown_output_extension(self, tmp_path: Path) -> None:
        """Test convert with unsupported output extension."""
        output = tmp_path / "output.xyz"
        result = runner.invoke(app, ["convert", str(IEEE14_RAW), str(output)])
        assert result.exit_code != 0


class TestDescribeCommand:
    """Tests for the 'describe' command."""

    def test_describe_normal(self) -> None:
        """Test describe with default (normal) detail level."""
        result = runner.invoke(app, ["describe", str(IEEE14_RAW)])
        assert result.exit_code == 0
        assert "Power System" in result.stdout
        assert "Buses" in result.stdout or "buses" in result.stdout.lower()

    def test_describe_brief(self) -> None:
        """Test describe with brief detail level."""
        result = runner.invoke(app, ["describe", str(IEEE14_RAW), "--detail", "brief"])
        assert result.exit_code == 0
        assert "Power System" in result.stdout
        # Brief should be shorter than normal
        brief_len = len(result.stdout)
        normal = runner.invoke(app, ["describe", str(IEEE14_RAW)])
        assert brief_len <= len(normal.stdout)

    def test_describe_full(self) -> None:
        """Test describe with full detail level."""
        result = runner.invoke(app, ["describe", str(IEEE14_RAW), "--detail", "full"])
        assert result.exit_code == 0
        assert "Voltage Range" in result.stdout
        assert "Branch Breakdown" in result.stdout

    def test_describe_matpower(self) -> None:
        """Test describe with MATPOWER file."""
        result = runner.invoke(app, ["describe", str(IEEE14_MATPOWER)])
        assert result.exit_code == 0

    def test_describe_json(self) -> None:
        """Test describe with psforge JSON file."""
        result = runner.invoke(app, ["describe", str(IEEE14_JSON)])
        assert result.exit_code == 0

    def test_describe_text_format(self) -> None:
        """Test describe with text format."""
        result = runner.invoke(app, ["describe", str(IEEE14_RAW), "-f", "text"])
        assert result.exit_code == 0
        assert "Power System" in result.stdout


class TestShowWhereFilter:
    """Tests for the show --where filter."""

    def test_filter_buses_by_type(self) -> None:
        """Filter buses by bus_type==3 (slack)."""
        result = runner.invoke(
            app, ["show", str(IEEE14_RAW), "buses", "-f", "json", "--where", "bus_type==3"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["buses"]) == 1
        # JSON formatter uses "type" key (integer value)
        assert data["buses"][0]["type"] == 3
        assert data["buses"][0]["id"] == "B1"

    def test_filter_buses_low_voltage(self) -> None:
        """Filter buses with v_magnitude < 1.0."""
        result = runner.invoke(
            app, ["show", str(IEEE14_RAW), "buses", "-f", "json", "--where", "v_magnitude<1.0"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        for bus in data["buses"]:
            assert bus["voltage_pu"] < 1.0

    def test_filter_branches_high_reactance(self) -> None:
        """Filter branches with x_pu > 0.2."""
        result = runner.invoke(
            app,
            ["show", str(IEEE14_RAW), "branches", "-f", "json", "--where", "x_pu>0.2"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["branches"]) > 0

    def test_filter_generators(self) -> None:
        """Filter generators by string bus_id reference."""
        result = runner.invoke(
            app,
            ["show", str(IEEE14_RAW), "generators", "-f", "json", "--where", "bus_id==B1"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["generators"]) == 1
        assert data["generators"][0]["bus_id"] == "B1"

    def test_filter_invalid_expression(self) -> None:
        """Invalid filter expression shows error."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses", "--where", "invalid"])
        assert result.exit_code != 0

    def test_filter_empty_result(self) -> None:
        """Filter that matches nothing returns empty."""
        result = runner.invoke(
            app,
            ["show", str(IEEE14_RAW), "buses", "-f", "json", "--where", "id==B999"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["buses"]) == 0


class TestDiffCommand:
    """Tests for the 'diff' command."""

    def test_diff_identical_files(self) -> None:
        """Comparing a file with itself shows no differences."""
        result = runner.invoke(app, ["diff", str(IEEE14_RAW), str(IEEE14_RAW)])
        assert result.exit_code == 0
        assert "No differences" in result.stdout

    def test_diff_different_formats(self) -> None:
        """Compare RAW and JSON versions of same system."""
        result = runner.invoke(app, ["diff", str(IEEE14_RAW), str(IEEE14_JSON)])
        assert result.exit_code == 0

    def test_diff_json_output(self) -> None:
        """Diff with JSON output format."""
        result = runner.invoke(app, ["diff", str(IEEE14_RAW), str(IEEE14_JSON), "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "files" in data
        assert "summary" in data
        assert "changes" in data

    def test_diff_with_scenario(self, tmp_path: Path) -> None:
        """Diff base vs scenario-modified system."""
        from psforge_grid.models.scenario import ScenarioSet

        scenarios = ScenarioSet.from_json(
            FIXTURES_DIR / "ieee14_contingencies_v2.psfg.json"
        ).resolve()
        n1_path = tmp_path / "n1.psfg.json"
        scenarios["N-1_Line_1-5"].to_json(n1_path)

        result = runner.invoke(app, ["diff", str(IEEE14_JSON), str(n1_path), "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # Should detect the branch status change
        branch_changes = [c for c in data["changes"] if c["type"] == "branch"]
        assert len(branch_changes) > 0

    def test_diff_different_systems(self) -> None:
        """Diff two different systems shows count differences."""
        result = runner.invoke(app, ["diff", str(IEEE14_RAW), str(IEEE9_RAW), "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["summary"]["total_changes"] > 0


# =========================================================================
# Scenario Command Tests
# =========================================================================

IEEE14_CONTINGENCIES = FIXTURES_DIR / "ieee14_contingencies_v2.psfg.json"


class TestScenarioCommand:
    """Tests for the 'scenario list' command."""

    def test_scenario_list_table(self) -> None:
        """Test scenario list with default table format."""
        result = runner.invoke(app, ["scenario", "list", str(IEEE14_CONTINGENCIES)])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "ieee14_contingencies_v2.psfg.json" in output
        assert "N-1_Line_1-5" in output
        assert "N-1_Line_2-3" in output
        assert "heavy_load_bus14" in output
        assert "3 scenarios defined" in output

    def test_scenario_list_json(self) -> None:
        """Test scenario list with JSON output."""
        result = runner.invoke(app, ["scenario", "list", str(IEEE14_CONTINGENCIES), "-f", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["num_scenarios"] == 3
        assert data["base_case"] == "ieee14.psfg.json"
        assert data["base_summary"]["buses"] == 14
        names = [s["name"] for s in data["scenarios"]]
        assert "N-1_Line_1-5" in names
        assert "heavy_load_bus14" in names

    def test_scenario_list_summary(self) -> None:
        """Test scenario list with summary output."""
        result = runner.invoke(
            app, ["scenario", "list", str(IEEE14_CONTINGENCIES), "-f", "summary"]
        )
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "14 buses" in output
        assert "N-1_Line_1-5" in output

    def test_scenario_list_nonexistent_file(self) -> None:
        """Test scenario list with non-existent file."""
        result = runner.invoke(app, ["scenario", "list", "nonexistent.psfg.json"])
        assert result.exit_code == 1

    def test_scenario_list_invalid_format(self) -> None:
        """Test scenario list with a non-scenario file."""
        result = runner.invoke(app, ["scenario", "list", str(IEEE14_JSON)])
        assert result.exit_code == 1
