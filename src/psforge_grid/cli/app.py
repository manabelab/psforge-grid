"""Main CLI application for psforge-grid.

This module defines the Typer application with all commands for inspecting,
validating, and converting power system data files.

Commands:
    info: Display system summary information
    show: Display detailed element information
    validate: Validate system data consistency
    convert: Convert between file formats

Supported input formats (auto-detected by extension):
    .raw: PSS/E RAW (v33/v34)
    .m: MATPOWER
    .pop: CPAT Pop (ZIP/XML)
    .dyna: CPAT Dyna (Fortran cards)
    .dss: OpenDSS
    .psfg.json: psforge JSON

Example:
    $ psforge-grid info ieee14.raw
    $ psforge-grid info case14.m --format json
    $ psforge-grid show WEST10peak.pop buses
    $ psforge-grid convert ieee14.raw output.psfg.json
"""

from __future__ import annotations

import copy
import operator
import re
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

if TYPE_CHECKING:
    from psforge_grid.models import Branch, Bus, Load

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
    """Power system data inspection, validation, and conversion CLI.

    Supports all psforge-grid formats: PSS/E RAW (.raw), MATPOWER (.m),
    CPAT (.pop/.dyna), OpenDSS (.dss), and psforge JSON (.psfg.json).
    Input format is auto-detected from file extension.

    Examples:

        $ psforge-grid info ieee14.raw

        $ psforge-grid info case14.m --format json

        $ psforge-grid show WEST10peak.pop buses

        $ psforge-grid convert ieee14.raw output.psfg.json
    """


@app.command()
def info(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to power system data file (.raw, .m, .pop, .dyna, .dss, .psfg.json).",
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

    Loads a power system data file (format auto-detected from extension)
    and displays summary statistics including bus counts, branch counts,
    power balance, and bus type distribution.

    Output formats:
      - table: Human-readable table (default)
      - json: Structured JSON for LLM/API processing
      - summary: Compact text for token-efficient LLM usage
      - csv: Comma-separated values for data analysis

    Examples:

        $ psforge-grid info ieee14.raw

        $ psforge-grid info case14.m -f json

        $ psforge-grid info WEST10peak.pop -f summary
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

        # Load system (auto-detect format from extension)
        if verbose >= 1:
            console.print(f"[dim]Loading: {input_file}[/dim]")

        system = System.from_file(input_file)

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
        error_console.print(f"[red]Error:[/red] File not found: {input_file}")
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
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to power system data file (.raw, .m, .pop, .dyna, .dss, .psfg.json).",
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
    element_id: Annotated[
        int | None,
        typer.Argument(
            help="Specific element ID to filter by. For buses/generators/loads: bus_id. For branches: list index.",
        ),
    ] = None,
    where: Annotated[
        str | None,
        typer.Option(
            "--where",
            "-w",
            help=(
                "Filter expression. Examples: 'v_magnitude<0.95', "
                "'bus_type==3', 'x_pu>0.1', 'status!=1'."
            ),
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
    Input format is auto-detected from file extension.

    Examples:

        $ psforge-grid show ieee14.raw buses

        $ psforge-grid show case14.m branches -f json

        $ psforge-grid show WEST10peak.pop generators -f csv
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

        # Load system (auto-detect format from extension)
        if verbose >= 1:
            console.print(f"[dim]Loading: {input_file}[/dim]")

        system = System.from_file(input_file)

        # Apply element_id filter first (before --where)
        if element_id is not None:
            system = _apply_element_id_filter(system, element, element_id)

        # Apply --where filter if specified
        if where:
            system = _apply_where_filter(system, element, where)

        formatter = get_formatter(output_format)

        # Format based on element type
        if element == ElementType.buses:
            result = formatter.format_buses(system)
        elif element == ElementType.branches:
            result = formatter.format_branches(system)
        elif element == ElementType.generators:
            result = formatter.format_generators(system)
        elif element == ElementType.loads:
            result = formatter.format_loads(system)
        else:  # all
            parts = [
                formatter.format_buses(system),
                "",
                formatter.format_branches(system),
                "",
                formatter.format_generators(system),
                "",
                formatter.format_loads(system),
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
        error_console.print(f"[red]Error:[/red] File not found: {input_file}")
        raise typer.Exit(1) from None
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        if verbose >= 3:
            import traceback

            error_console.print(traceback.format_exc())
        raise typer.Exit(1) from None


@app.command()
def validate(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to power system data file (.raw, .m, .pop, .dyna, .dss, .psfg.json).",
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

    Input format is auto-detected from file extension.

    Examples:

        $ psforge-grid validate ieee14.raw

        $ psforge-grid validate case14.m --strict

        $ psforge-grid validate ieee14.psfg.json -f json
    """
    try:
        if verbose >= 1:
            console.print(f"[dim]Loading: {input_file}[/dim]")

        system = System.from_file(input_file)

        # Run validation
        issues = system.validate_detailed(strict=strict)

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


@app.command()
def convert(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to input power system data file.",
            exists=True,
            readable=True,
        ),
    ],
    output_file: Annotated[
        Path,
        typer.Argument(
            help="Path to output file. Format is determined by extension.",
        ),
    ],
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
    """Convert a power system data file between formats.

    Input and output formats are auto-detected from file extensions.

    Supported formats: .raw, .m, .pop, .dyna, .dss, .psfg.json

    Examples:

        $ psforge-grid convert ieee14.raw ieee14.psfg.json

        $ psforge-grid convert ieee14.raw ieee14.m

        $ psforge-grid convert WEST10peak.pop west10.psfg.json
    """
    try:
        if verbose >= 1:
            console.print(f"[dim]Loading: {input_file}[/dim]")

        system = System.from_file(input_file)

        if verbose >= 1:
            console.print(
                f"[dim]Parsed: {system.num_buses()} buses, {system.num_branches()} branches[/dim]"
            )

        system.to_file(output_file)

        if verbose >= 1:
            console.print(f"[dim]Written: {output_file}[/dim]")
        else:
            console.print(
                f"Converted {input_file.name} → {output_file.name} "
                f"({system.num_buses()} buses, {system.num_branches()} branches)"
            )

    except FileNotFoundError:
        error_console.print(f"[red]Error:[/red] File not found: {input_file}")
        raise typer.Exit(1) from None
    except ValueError as e:
        error_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        if verbose >= 3:
            import traceback

            error_console.print(traceback.format_exc())
        raise typer.Exit(1) from None


@app.command()
def describe(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to power system data file.",
            exists=True,
            readable=True,
        ),
    ],
    detail: Annotated[
        str,
        typer.Option(
            "--detail",
            "-d",
            help="Detail level: brief, normal, or full.",
        ),
    ] = "normal",
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: text or markdown.",
        ),
    ] = "markdown",
) -> None:
    """Generate a natural language description of a power system.

    Produces LLM-ready context that can be directly embedded in prompts.
    Three detail levels control the amount of information included.

    Detail levels:
      - brief: System name, size, and power balance (minimal tokens)
      - normal: Add bus type breakdown and voltage range (default)
      - full: Add per-component details

    Examples:

        $ psforge-grid describe ieee14.raw

        $ psforge-grid describe case14.m --detail brief

        $ psforge-grid describe ieee14.psfg.json --detail full -f text
    """
    try:
        system = System.from_file(input_file)

        if detail == "brief":
            result = system.to_description()
        elif detail == "full":
            result = system.to_llm_context(
                include_components=True,
                format=format,
            )
            # Append voltage range and notable elements
            voltages = [b.v_magnitude for b in system.buses]
            result += "\n\n### Voltage Range\n"
            result += f"- Min: {min(voltages):.4f} pu (Bus {system.buses[voltages.index(min(voltages))].bus_id})\n"
            result += f"- Max: {max(voltages):.4f} pu (Bus {system.buses[voltages.index(max(voltages))].bus_id})\n"

            # Transformers
            xfmrs = [b for b in system.branches if b.is_transformer]
            lines = [b for b in system.branches if not b.is_transformer]
            result += "\n### Branch Breakdown\n"
            result += f"- Transmission lines: {len(lines)}\n"
            result += f"- Transformers: {len(xfmrs)}\n"
        else:  # normal
            result = system.to_llm_context(
                include_components=True,
                format=format,
            )

        console.print(result)

    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None


@app.command()
def diff(
    file_a: Annotated[
        Path,
        typer.Argument(
            help="Path to first (base) power system data file.",
            exists=True,
            readable=True,
        ),
    ],
    file_b: Annotated[
        Path,
        typer.Argument(
            help="Path to second (modified) power system data file.",
            exists=True,
            readable=True,
        ),
    ],
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: text or json.",
        ),
    ] = "text",
) -> None:
    """Compare two power system data files and show differences.

    Useful for N-1 analysis, scenario comparison, and change tracking.

    Examples:

        $ psforge-grid diff base.psfg.json modified.psfg.json

        $ psforge-grid diff ieee14.raw ieee14_modified.raw -f json
    """
    try:
        sys_a = System.from_file(file_a)
        sys_b = System.from_file(file_b)

        differences = _compute_diff(sys_a, sys_b, file_a.name, file_b.name)

        if format.lower() == "json":
            import json

            console.print(json.dumps(differences, indent=2))
        else:
            _print_diff_text(differences)

    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None


def _diff_buses(
    buses_a: list[Bus],
    buses_b: list[Bus],
) -> list[dict[str, Any]]:
    """Compute per-bus differences between two systems.

    Args:
        buses_a: Buses from the base system.
        buses_b: Buses from the modified system.

    Returns:
        List of change dicts with keys: type, id, action, and optionally fields.
    """
    changes: list[dict[str, Any]] = []
    map_a = {b.bus_id: b for b in buses_a}
    map_b = {b.bus_id: b for b in buses_b}

    for bus_id in sorted(set(map_a) | set(map_b)):
        if bus_id not in map_a:
            changes.append({"type": "bus", "id": bus_id, "action": "added"})
        elif bus_id not in map_b:
            changes.append({"type": "bus", "id": bus_id, "action": "removed"})
        else:
            ba, bb = map_a[bus_id], map_b[bus_id]
            field_changes: dict[str, Any] = {}
            if ba.bus_type != bb.bus_type:
                field_changes["bus_type"] = {"base": ba.bus_type, "modified": bb.bus_type}
            if abs(ba.v_magnitude - bb.v_magnitude) > 1e-6:
                field_changes["v_magnitude"] = {
                    "base": round(ba.v_magnitude, 6),
                    "modified": round(bb.v_magnitude, 6),
                }
            if field_changes:
                changes.append(
                    {"type": "bus", "id": bus_id, "action": "changed", "fields": field_changes}
                )

    return changes


def _diff_branches(
    branches_a: list[Branch],
    branches_b: list[Branch],
) -> list[dict[str, Any]]:
    """Compute per-branch differences between two systems.

    Args:
        branches_a: Branches from the base system.
        branches_b: Branches from the modified system.

    Returns:
        List of change dicts with keys: type, id, action, and optionally fields.
    """
    changes: list[dict[str, Any]] = []
    map_a = {(b.from_bus, b.to_bus, b.circuit_id): b for b in branches_a}
    map_b = {(b.from_bus, b.to_bus, b.circuit_id): b for b in branches_b}

    for br_key in sorted(set(map_a) | set(map_b)):
        label = f"{br_key[0]}-{br_key[1]}({br_key[2]})"
        if br_key not in map_a:
            changes.append({"type": "branch", "id": label, "action": "added"})
        elif br_key not in map_b:
            changes.append({"type": "branch", "id": label, "action": "removed"})
        else:
            br_a, br_b = map_a[br_key], map_b[br_key]
            field_changes: dict[str, Any] = {}
            if br_a.status != br_b.status:
                field_changes["status"] = {"base": br_a.status, "modified": br_b.status}
            if abs(br_a.r_pu - br_b.r_pu) > 1e-6:
                field_changes["r_pu"] = {
                    "base": round(br_a.r_pu, 6),
                    "modified": round(br_b.r_pu, 6),
                }
            if abs(br_a.x_pu - br_b.x_pu) > 1e-6:
                field_changes["x_pu"] = {
                    "base": round(br_a.x_pu, 6),
                    "modified": round(br_b.x_pu, 6),
                }
            if abs(br_a.tap_ratio - br_b.tap_ratio) > 1e-6:
                field_changes["tap_ratio"] = {
                    "base": round(br_a.tap_ratio, 6),
                    "modified": round(br_b.tap_ratio, 6),
                }
            if field_changes:
                changes.append(
                    {"type": "branch", "id": label, "action": "changed", "fields": field_changes}
                )

    return changes


def _diff_loads(
    loads_a: list[Load],
    loads_b: list[Load],
) -> list[dict[str, Any]]:
    """Compute per-load differences between two systems.

    Args:
        loads_a: Loads from the base system.
        loads_b: Loads from the modified system.

    Returns:
        List of change dicts with keys: type, id, action, and optionally fields.
    """
    changes: list[dict[str, Any]] = []
    map_a = {(ld.bus_id, ld.load_id): ld for ld in loads_a}
    map_b = {(ld.bus_id, ld.load_id): ld for ld in loads_b}

    for ld_key in sorted(set(map_a) | set(map_b)):
        label = f"Bus{ld_key[0]}({ld_key[1]})"
        if ld_key not in map_a:
            changes.append({"type": "load", "id": label, "action": "added"})
        elif ld_key not in map_b:
            changes.append({"type": "load", "id": label, "action": "removed"})
        else:
            ld_a, ld_b = map_a[ld_key], map_b[ld_key]
            field_changes: dict[str, Any] = {}
            if abs(ld_a.p_load - ld_b.p_load) > 1e-6:
                field_changes["p_load"] = {
                    "base": round(ld_a.p_load, 4),
                    "modified": round(ld_b.p_load, 4),
                }
            if abs(ld_a.q_load - ld_b.q_load) > 1e-6:
                field_changes["q_load"] = {
                    "base": round(ld_a.q_load, 4),
                    "modified": round(ld_b.q_load, 4),
                }
            if field_changes:
                changes.append(
                    {"type": "load", "id": label, "action": "changed", "fields": field_changes}
                )

    return changes


def _compute_diff(
    sys_a: System,
    sys_b: System,
    name_a: str,
    name_b: str,
) -> dict[str, Any]:
    """Compute differences between two systems.

    Orchestrates element-level diff helpers and aggregates results into
    a single diff dict with summary counts and per-element changes.
    """
    diff: dict[str, Any] = {
        "files": {"base": name_a, "modified": name_b},
        "summary": {},
        "changes": [],
    }

    # Component count differences
    counts = {
        "buses": (sys_a.num_buses(), sys_b.num_buses()),
        "branches": (sys_a.num_branches(), sys_b.num_branches()),
        "generators": (sys_a.num_generators(), sys_b.num_generators()),
        "loads": (sys_a.num_loads(), sys_b.num_loads()),
        "shunts": (sys_a.num_shunts(), sys_b.num_shunts()),
    }

    for comp, (count_a, count_b) in counts.items():
        if count_a != count_b:
            diff["summary"][comp] = {"base": count_a, "modified": count_b}

    p_gen_a, q_gen_a = sys_a.total_generation()
    p_gen_b, q_gen_b = sys_b.total_generation()
    p_load_a, q_load_a = sys_a.total_load()
    p_load_b, q_load_b = sys_b.total_load()

    if abs(p_gen_a - p_gen_b) > 1e-6 or abs(q_gen_a - q_gen_b) > 1e-6:
        diff["summary"]["generation"] = {
            "base_p_pu": round(p_gen_a, 4),
            "modified_p_pu": round(p_gen_b, 4),
            "base_q_pu": round(q_gen_a, 4),
            "modified_q_pu": round(q_gen_b, 4),
        }

    if abs(p_load_a - p_load_b) > 1e-6 or abs(q_load_a - q_load_b) > 1e-6:
        diff["summary"]["load"] = {
            "base_p_pu": round(p_load_a, 4),
            "modified_p_pu": round(p_load_b, 4),
            "base_q_pu": round(q_load_a, 4),
            "modified_q_pu": round(q_load_b, 4),
        }

    # Delegate element-level diffs to helpers
    diff["changes"].extend(_diff_buses(sys_a.buses, sys_b.buses))
    diff["changes"].extend(_diff_branches(sys_a.branches, sys_b.branches))
    diff["changes"].extend(_diff_loads(sys_a.loads, sys_b.loads))

    diff["summary"]["total_changes"] = len(diff["changes"])
    return diff


def _print_diff_text(differences: dict[str, Any]) -> None:
    """Print diff results in human-readable text format."""
    files = differences["files"]
    console.print(f"Comparing: {files['base']} vs {files['modified']}")
    console.print()

    summary = differences["summary"]
    total = summary.get("total_changes", 0)

    if total == 0:
        console.print("[green]No differences found.[/green]")
        return

    console.print(f"[bold]{total} change(s) detected:[/bold]")
    console.print()

    for change in differences["changes"]:
        action = change["action"]
        elem_type = change["type"]
        elem_id = change["id"]

        if action == "added":
            console.print(f"  [green]+ {elem_type} {elem_id}[/green]")
        elif action == "removed":
            console.print(f"  [red]- {elem_type} {elem_id}[/red]")
        else:
            fields = change.get("fields", {})
            field_strs = []
            for field_name, vals in fields.items():
                field_strs.append(f"{field_name}: {vals['base']} → {vals['modified']}")
            console.print(f"  [yellow]~ {elem_type} {elem_id}[/yellow]: {', '.join(field_strs)}")


_OPERATORS = {
    "<=": operator.le,
    ">=": operator.ge,
    "!=": operator.ne,
    "==": operator.eq,
    "<": operator.lt,
    ">": operator.gt,
}

_WHERE_PATTERN = re.compile(r"^(\w+)\s*(<=|>=|!=|==|<|>)\s*(.+)$")


def _parse_where(expr: str) -> tuple[str, str, str]:
    """Parse a where expression like 'v_magnitude<0.95'.

    Returns:
        Tuple of (field_name, operator_str, value_str)

    Raises:
        ValueError: If expression cannot be parsed
    """
    match = _WHERE_PATTERN.match(expr.strip())
    if not match:
        raise ValueError(
            f"Invalid filter expression: '{expr}'. "
            f"Expected format: 'field_name<operator>value' "
            f"(e.g., 'v_magnitude<0.95', 'bus_type==3', 'status!=1')"
        )
    return match.group(1), match.group(2), match.group(3)


def _matches_where(element: object, field: str, op_str: str, value_str: str) -> bool:
    """Check if an element matches a where condition."""
    if not hasattr(element, field):
        return False

    attr = getattr(element, field)
    if attr is None:
        return False

    # Try numeric comparison first
    try:
        num_value: float | int = float(value_str)
        if isinstance(attr, int) and "." not in value_str:
            num_value = int(value_str)
        return bool(_OPERATORS[op_str](attr, num_value))
    except (ValueError, TypeError):
        # Fall back to string comparison
        return bool(_OPERATORS[op_str](str(attr), value_str))


def _apply_element_id_filter(
    system: System,
    element: ElementType,
    element_id: int,
) -> System:
    """Filter a system by element ID, returning a filtered copy.

    For buses, generators, and loads: filters by bus_id.
    For branches: filters by list index (0-based position).

    Args:
        system: The power system to filter.
        element: Which element type to filter.
        element_id: The ID value to filter by.

    Returns:
        A deep copy of the system with only matching elements.
    """
    filtered = copy.deepcopy(system)

    if element == ElementType.buses or element == ElementType.all:
        filtered.buses = [b for b in system.buses if b.bus_id == element_id]
    if element == ElementType.branches or element == ElementType.all:
        if 0 <= element_id < len(system.branches):
            filtered.branches = [system.branches[element_id]]
        else:
            filtered.branches = []
    if element == ElementType.generators or element == ElementType.all:
        filtered.generators = [g for g in system.generators if g.bus_id == element_id]
    if element == ElementType.loads or element == ElementType.all:
        filtered.loads = [ld for ld in system.loads if ld.bus_id == element_id]

    return filtered


def _apply_where_filter(
    system: System,
    element: ElementType,
    where: str,
) -> System:
    """Apply a where filter to a system, returning a filtered copy.

    Only filters the specified element type. Other components are kept as-is.
    """
    field, op_str, value_str = _parse_where(where)

    filtered = copy.deepcopy(system)

    if element == ElementType.buses or element == ElementType.all:
        filtered.buses = [b for b in system.buses if _matches_where(b, field, op_str, value_str)]
    if element == ElementType.branches or element == ElementType.all:
        filtered.branches = [
            b for b in system.branches if _matches_where(b, field, op_str, value_str)
        ]
    if element == ElementType.generators or element == ElementType.all:
        filtered.generators = [
            g for g in system.generators if _matches_where(g, field, op_str, value_str)
        ]
    if element == ElementType.loads or element == ElementType.all:
        filtered.loads = [ld for ld in system.loads if _matches_where(ld, field, op_str, value_str)]

    return filtered


# =========================================================================
# Scenario subcommand
# =========================================================================

scenario_app = typer.Typer(
    name="scenario",
    help="Inspect scenario definition files.",
    add_completion=False,
)
app.add_typer(scenario_app, name="scenario")


class ScenarioFormat(str, Enum):
    """Output formats for scenario commands."""

    table = "table"
    json = "json"
    summary = "summary"


@scenario_app.command("list")
def scenario_list(
    filepath: Annotated[
        str,
        typer.Argument(help="Path to a scenario .psfg.json file"),
    ],
    format: Annotated[
        ScenarioFormat,
        typer.Option("-f", "--format", help="Output format"),
    ] = ScenarioFormat.table,
) -> None:
    """List scenarios defined in a scenario file."""
    import json as json_mod

    from psforge_grid.models.scenario import ScenarioSet

    path = Path(filepath)
    if not path.exists():
        error_console.print(f"[red]File not found: {filepath}[/red]")
        raise typer.Exit(code=1)

    try:
        scenario_set = ScenarioSet.from_json(path)
    except (ValueError, FileNotFoundError) as e:
        error_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from None

    if format == ScenarioFormat.json:
        data = {
            "file": str(path),
            "base_case": scenario_set.base_case_path,
            "base_summary": {
                "buses": len(scenario_set.base.buses),
                "branches": len(scenario_set.base.branches),
                "generators": len(scenario_set.base.generators),
                "loads": len(scenario_set.base.loads),
            },
            "num_scenarios": scenario_set.num_scenarios,
            "scenarios": [
                {
                    "name": s.name,
                    "description": s.description,
                    "num_modifications": len(s.modifications),
                }
                for s in scenario_set.scenarios
            ],
        }
        print(json_mod.dumps(data, indent=2, ensure_ascii=False))
        return

    if format == ScenarioFormat.summary:
        console.print(scenario_set.to_description())
        return

    # Table format (default)
    from rich.table import Table

    console.print(f"Scenario File: [bold]{path.name}[/bold]")
    base_info = (
        f"{scenario_set.base_case_path} "
        f"({len(scenario_set.base.buses)} buses, "
        f"{len(scenario_set.base.branches)} branches)"
    )
    console.print(f"Base Case: {base_info}")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Modifications", justify="right")

    for s in scenario_set.scenarios:
        table.add_row(
            s.name,
            s.description or "",
            str(len(s.modifications)),
        )

    console.print(table)
    console.print(f"\n{scenario_set.num_scenarios} scenarios defined")


if __name__ == "__main__":
    app()
