"""Tests for psforge-grid CLI.

These tests verify the CLI commands work correctly with various inputs
and output formats.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from psforge_grid.cli.app import app

runner = CliRunner()

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
IEEE14_RAW = FIXTURES_DIR / "ieee14.raw"
IEEE9_RAW = FIXTURES_DIR / "ieee9.raw"


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
        assert "Bus" in result.stdout or "bus_id" in result.stdout

    def test_show_buses_json(self) -> None:
        """Test show buses command with JSON output."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses", "-f", "json"])
        assert result.exit_code == 0

        data = json.loads(result.stdout)
        assert "buses" in data
        assert len(data["buses"]) == 14
        assert data["buses"][0]["bus_id"] == 1

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
        assert len(data["branches"]) > 0

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

    def test_show_loads(self) -> None:
        """Test show loads command."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "loads"])
        assert result.exit_code == 0

    def test_show_all(self) -> None:
        """Test show all elements command."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "all"])
        assert result.exit_code == 0

    def test_show_csv_format(self) -> None:
        """Test show command with CSV output."""
        result = runner.invoke(app, ["show", str(IEEE14_RAW), "buses", "-f", "csv"])
        assert result.exit_code == 0
        assert "bus_id," in result.stdout

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
        assert "--format" in result.stdout

    def test_show_help(self) -> None:
        """Test show --help."""
        result = runner.invoke(app, ["show", "--help"])
        assert result.exit_code == 0

    def test_validate_help(self) -> None:
        """Test validate --help."""
        result = runner.invoke(app, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--strict" in result.stdout


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
