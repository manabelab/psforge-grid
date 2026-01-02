"""Main CLI application for psforge-grid.

This module defines the Typer application with all commands for inspecting
and validating power system data files.

Commands:
    info: Display system summary information
    show: Display detailed element information
    validate: Validate system data consistency

Example:
    $ psforge-grid info ieee14.raw
    $ psforge-grid info ieee14.raw --format json
    $ psforge-grid show ieee14.raw buses
    $ psforge-grid validate ieee14.raw --strict
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from psforge_grid.cli.formatters import (
    OutputFormat,
    create_system_summary,
    get_formatter,
)
from psforge_grid.models import System

# Create Typer app
app = typer.Typer(
    name="psforge-grid",
    help="Power system data inspection and validation CLI.",
    add_completion=False,
)

# Rich console for output
console = Console()
error_console = Console(stderr=True)


class ElementType(str, Enum):
    """Element types for the show command."""

    buses = "buses"
    branches = "branches"
    generators = "generators"
    loads = "loads"
    all = "all"


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        from importlib.metadata import version

        try:
            v = version("psforge-grid")
        except Exception:
            v = "0.1.0"
        console.print(f"psforge-grid version {v}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    """Power system data inspection and validation CLI.

    psforge-grid provides commands for inspecting PSS/E RAW files and other
    power system data formats. Designed with LLM affinity in mind, supporting
    multiple output formats including JSON and compact summaries.

    Examples:

        $ psforge-grid info ieee14.raw

        $ psforge-grid info ieee14.raw --format json

        $ psforge-grid show ieee14.raw buses

        $ psforge-grid validate ieee14.raw
    """


@app.command()
def info(
    raw_file: Annotated[
        Path,
        typer.Argument(
            help="Path to the PSS/E RAW file.",
            exists=True,
            readable=True,
        ),
    ],
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table, json, summary, or csv.",
        ),
    ] = "table",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path. If not specified, prints to stdout.",
        ),
    ] = None,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help="Increase verbosity. Use -v, -vv, or -vvv.",
        ),
    ] = 0,
) -> None:
    """Display summary information about a power system.

    Loads a PSS/E RAW file and displays summary statistics including
    bus counts, branch counts, power balance, and bus type distribution.

    Output formats:
      - table: Human-readable table (default)
      - json: Structured JSON for LLM/API processing
      - summary: Compact text for token-efficient LLM usage
      - csv: Comma-separated values for data analysis

    Examples:

        $ psforge-grid info ieee14.raw

        $ psforge-grid info ieee14.raw -f json

        $ psforge-grid info ieee14.raw -f summary

        $ psforge-grid info ieee14.raw -o output.json -f json
    """
    try:
        # Validate format
        try:
            output_format = OutputFormat(format.lower())
        except ValueError:
            error_console.print(
                f"[red]Error:[/red] Invalid format '{format}'. "
                f"Valid options: table, json, summary, csv"
            )
            raise typer.Exit(1) from None

        # Load system
        if verbose >= 1:
            console.print(f"[dim]Loading: {raw_file}[/dim]")

        system = System.from_raw(raw_file)

        if verbose >= 2:
            console.print(
                f"[dim]Parsed: {system.num_buses()} buses, {system.num_branches()} branches[/dim]"
            )

        # Create summary and format output
        summary = create_system_summary(system)
        formatter = get_formatter(output_format)
        result = formatter.format_system_info(summary)

        # Output
        if output:
            output.write_text(result)
            if verbose >= 1:
                console.print(f"[dim]Output written to: {output}[/dim]")
        else:
            console.print(result)

    except FileNotFoundError:
        error_console.print(f"[red]Error:[/red] File not found: {raw_file}")
        raise typer.Exit(1) from None
    except ValueError as e:
        error_console.print(f"[red]Error:[/red] Failed to parse file: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        if verbose >= 3:
            import traceback

            error_console.print(traceback.format_exc())
        raise typer.Exit(1) from None


@app.command()
def show(
    raw_file: Annotated[
        Path,
        typer.Argument(
            help="Path to the PSS/E RAW file.",
            exists=True,
            readable=True,
        ),
    ],
    element: Annotated[
        ElementType,
        typer.Argument(
            help="Element type to display: buses, branches, generators, loads, or all.",
        ),
    ],
    element_id: Annotated[  # noqa: ARG001 - placeholder for future filtering
        int | None,
        typer.Argument(
            help="Specific element ID to display. If not specified, shows all.",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table, json, summary, or csv.",
        ),
    ] = "table",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path. If not specified, prints to stdout.",
        ),
    ] = None,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help="Increase verbosity. Use -v, -vv, or -vvv.",
        ),
    ] = 0,
) -> None:
    """Display detailed information about specific elements.

    Shows detailed data for buses, branches, generators, or loads.
    Can filter by specific element ID or show all elements.

    Examples:

        $ psforge-grid show ieee14.raw buses

        $ psforge-grid show ieee14.raw buses 1

        $ psforge-grid show ieee14.raw branches -f json

        $ psforge-grid show ieee14.raw generators -f csv
    """
    try:
        # Validate format
        try:
            output_format = OutputFormat(format.lower())
        except ValueError:
            error_console.print(
                f"[red]Error:[/red] Invalid format '{format}'. "
                f"Valid options: table, json, summary, csv"
            )
            raise typer.Exit(1) from None

        # Load system
        if verbose >= 1:
            console.print(f"[dim]Loading: {raw_file}[/dim]")

        system = System.from_raw(raw_file)
        formatter = get_formatter(output_format)

        # Format based on element type
        if element == ElementType.buses:
            result = formatter.format_buses(system)
        elif element == ElementType.branches:
            result = formatter.format_branches(system)
        elif element == ElementType.generators:
            result = formatter.format_generators(system)
        elif element == ElementType.loads:
            # Loads formatting (similar to generators)
            result = _format_loads(system, output_format)
        else:  # all
            parts = [
                formatter.format_buses(system),
                "",
                formatter.format_branches(system),
                "",
                formatter.format_generators(system),
            ]
            result = "\n".join(parts)

        # Output
        if output:
            output.write_text(result)
            if verbose >= 1:
                console.print(f"[dim]Output written to: {output}[/dim]")
        else:
            console.print(result)

    except FileNotFoundError:
        error_console.print(f"[red]Error:[/red] File not found: {raw_file}")
        raise typer.Exit(1) from None
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        if verbose >= 3:
            import traceback

            error_console.print(traceback.format_exc())
        raise typer.Exit(1) from None


@app.command()
def validate(
    raw_file: Annotated[
        Path,
        typer.Argument(
            help="Path to the PSS/E RAW file.",
            exists=True,
            readable=True,
        ),
    ],
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Enable strict validation mode.",
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table, json, or summary.",
        ),
    ] = "table",
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help="Increase verbosity.",
        ),
    ] = 0,
) -> None:
    """Validate power system data for consistency.

    Checks for common issues such as:
    - Missing slack bus
    - Disconnected buses
    - Invalid voltage values
    - Missing generator at PV buses

    Examples:

        $ psforge-grid validate ieee14.raw

        $ psforge-grid validate ieee14.raw --strict

        $ psforge-grid validate ieee14.raw -f json
    """
    try:
        if verbose >= 1:
            console.print(f"[dim]Loading: {raw_file}[/dim]")

        system = System.from_raw(raw_file)

        # Run validation
        issues = _validate_system(system, strict=strict)

        # Format output
        if format.lower() == "json":
            import json

            result = json.dumps(
                {
                    "status": "PASSED" if not issues else "FAILED",
                    "num_errors": len([i for i in issues if i["level"] == "error"]),
                    "num_warnings": len([i for i in issues if i["level"] == "warning"]),
                    "issues": issues,
                },
                indent=2,
            )
            console.print(result)
        elif format.lower() == "summary":
            errors = [i for i in issues if i["level"] == "error"]
            warnings = [i for i in issues if i["level"] == "warning"]
            status = "PASSED" if not errors else "FAILED"
            console.print(
                f"Validation: {status} | Errors: {len(errors)}, Warnings: {len(warnings)}"
            )
            if issues:
                for issue in issues:
                    console.print(f"  [{issue['level'].upper()}] {issue['message']}")
        else:  # table
            from rich.table import Table

            table = Table(title="Validation Results")
            table.add_column("Level", style="cyan")
            table.add_column("Message")

            if not issues:
                console.print("[green]Validation PASSED[/green] - No issues found.")
            else:
                for issue in issues:
                    level_style = "red" if issue["level"] == "error" else "yellow"
                    table.add_row(
                        f"[{level_style}]{issue['level'].upper()}[/{level_style}]",
                        issue["message"],
                    )
                console.print(table)

                errors = [i for i in issues if i["level"] == "error"]
                if errors:
                    console.print(f"\n[red]Validation FAILED[/red] - {len(errors)} error(s) found.")
                    raise typer.Exit(1) from None
                else:
                    console.print("\n[yellow]Validation PASSED with warnings[/yellow]")

    except typer.Exit:
        raise
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        if verbose >= 3:
            import traceback

            error_console.print(traceback.format_exc())
        raise typer.Exit(1) from None


def _format_loads(system: System, output_format: OutputFormat) -> str:
    """Format load information."""
    import json

    if output_format == OutputFormat.JSON:
        loads = []
        for load in system.loads:
            loads.append(
                {
                    "bus_id": load.bus_id,
                    "load_id": load.load_id,
                    "p_pu": round(load.p_load, 4),
                    "q_pu": round(load.q_load, 4),
                    "in_service": load.is_in_service,
                }
            )
        return json.dumps({"loads": loads}, indent=2)
    elif output_format == OutputFormat.CSV:
        lines = ["bus_id,load_id,p_pu,q_pu,in_service"]
        for load in system.loads:
            in_service = 1 if load.is_in_service else 0
            load_id = load.load_id or ""
            lines.append(
                f"{load.bus_id},{load_id},{load.p_load:.4f},{load.q_load:.4f},{in_service}"
            )
        return "\n".join(lines)
    elif output_format == OutputFormat.SUMMARY:
        lines = [f"Loads ({len(system.loads)}):"]
        for load in system.loads:
            status = "ON" if load.is_in_service else "OFF"
            lines.append(
                f"  Bus {load.bus_id}: P={load.p_load:.3f}, Q={load.q_load:.3f} pu [{status}]"
            )
        return "\n".join(lines)
    else:  # TABLE
        from rich.console import Console
        from rich.table import Table

        console = Console(force_terminal=False, width=100)
        table = Table(title="Load Data")
        table.add_column("Bus", style="cyan", justify="right")
        table.add_column("ID", style="cyan")
        table.add_column("P [pu]", style="green", justify="right")
        table.add_column("Q [pu]", style="green", justify="right")
        table.add_column("Status", style="magenta")

        for load in system.loads:
            status = "In-Service" if load.is_in_service else "Out-of-Service"
            table.add_row(
                str(load.bus_id),
                load.load_id or "-",
                f"{load.p_load:.4f}",
                f"{load.q_load:.4f}",
                status,
            )

        with console.capture() as capture:
            console.print(table)
        return str(capture.get())


def _validate_system(system: System, strict: bool = False) -> list[dict]:
    """Run validation checks on the system.

    Args:
        system: System to validate
        strict: Enable strict validation mode

    Returns:
        List of issue dictionaries with 'level' and 'message' keys
    """
    issues = []

    # Check for slack bus
    slack_buses = system.get_slack_buses()
    if not slack_buses:
        issues.append({"level": "error", "message": "No slack (swing) bus found in system"})
    elif len(slack_buses) > 1:
        issues.append(
            {
                "level": "warning",
                "message": f"Multiple slack buses found: {[b.bus_id for b in slack_buses]}",
            }
        )

    # Check voltage magnitudes
    for bus in system.buses:
        if bus.v_magnitude < 0.8:
            issues.append(
                {
                    "level": "error" if strict else "warning",
                    "message": f"Bus {bus.bus_id}: Very low voltage {bus.v_magnitude:.3f} pu",
                }
            )
        elif bus.v_magnitude < 0.9:
            issues.append(
                {
                    "level": "warning",
                    "message": f"Bus {bus.bus_id}: Low voltage {bus.v_magnitude:.3f} pu",
                }
            )
        elif bus.v_magnitude > 1.1:
            issues.append(
                {
                    "level": "warning",
                    "message": f"Bus {bus.bus_id}: High voltage {bus.v_magnitude:.3f} pu",
                }
            )
        elif bus.v_magnitude > 1.2:
            issues.append(
                {
                    "level": "error" if strict else "warning",
                    "message": f"Bus {bus.bus_id}: Very high voltage {bus.v_magnitude:.3f} pu",
                }
            )

    # Check PV buses have generators
    pv_buses = system.get_pv_buses()
    for bus in pv_buses:
        gens = system.get_bus_generators(bus.bus_id)
        if not gens:
            issues.append(
                {
                    "level": "error",
                    "message": f"PV bus {bus.bus_id} has no generator",
                }
            )

    # Check for negative impedance (typically an error)
    for branch in system.branches:
        if branch.x_pu < 0:
            issues.append(
                {
                    "level": "error",
                    "message": f"Branch {branch.from_bus}-{branch.to_bus}: Negative reactance X={branch.x_pu:.4f}",
                }
            )
        if branch.r_pu < 0:
            issues.append(
                {
                    "level": "warning",
                    "message": f"Branch {branch.from_bus}-{branch.to_bus}: Negative resistance R={branch.r_pu:.4f}",
                }
            )

    # Strict mode additional checks
    if strict:
        # Check all buses are referenced
        bus_ids = set(system.get_bus_ids())
        referenced_buses = set()

        for branch in system.branches:
            referenced_buses.add(branch.from_bus)
            referenced_buses.add(branch.to_bus)
        for gen in system.generators:
            referenced_buses.add(gen.bus_id)
        for load in system.loads:
            referenced_buses.add(load.bus_id)

        isolated = bus_ids - referenced_buses
        for bus_id in isolated:
            found_bus = system.get_bus(bus_id)
            if found_bus and not found_bus.is_isolated:
                issues.append(
                    {
                        "level": "warning",
                        "message": f"Bus {bus_id}: Not referenced by any branch, generator, or load",
                    }
                )

    return issues


if __name__ == "__main__":
    app()
