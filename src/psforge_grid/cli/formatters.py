"""Output formatters for CLI with LLM Affinity support.

This module provides formatters for different output formats (JSON, Table, Summary, CSV).
Following the LLM Affinity Design Philosophy:
- Explicit over Implicit: Include units and clear labels
- Semantic Annotation: Add status indicators (NORMAL, LOW, HIGH)
- Compact Representation: Summary format for efficient token usage
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psforge_grid.models import System


class VoltageStatus(Enum):
    """Voltage status classification for LLM-friendly output."""

    CRITICAL_LOW = "CRITICAL_LOW"  # < 0.90 pu
    LOW = "LOW"  # 0.90 - 0.95 pu
    NORMAL = "NORMAL"  # 0.95 - 1.05 pu
    HIGH = "HIGH"  # 1.05 - 1.10 pu
    CRITICAL_HIGH = "CRITICAL_HIGH"  # > 1.10 pu

    @classmethod
    def from_voltage(cls, v_pu: float) -> VoltageStatus:
        """Determine voltage status from per-unit voltage magnitude.

        Args:
            v_pu: Voltage magnitude in per-unit

        Returns:
            VoltageStatus enum value
        """
        if v_pu < 0.90:
            return cls.CRITICAL_LOW
        elif v_pu < 0.95:
            return cls.LOW
        elif v_pu <= 1.05:
            return cls.NORMAL
        elif v_pu <= 1.10:
            return cls.HIGH
        else:
            return cls.CRITICAL_HIGH


class OutputFormat(Enum):
    """Supported output formats."""

    TABLE = "table"
    JSON = "json"
    SUMMARY = "summary"
    CSV = "csv"


@dataclass
class SystemSummary:
    """Summary data structure for system information.

    Designed for LLM-friendly structured output with explicit units and status.
    """

    base_mva: float
    num_buses: int
    num_branches: int
    num_generators: int
    num_loads: int
    num_shunts: int
    num_slack: int
    num_pv: int
    num_pq: int
    total_generation_mw: float
    total_generation_mvar: float
    total_load_mw: float
    total_load_mvar: float
    name: str = ""
    voltage_range: tuple[float, float] = field(default=(0.0, 0.0))
    voltage_stats: dict[str, int] = field(default_factory=dict)


class IFormatter(ABC):
    """Abstract base class for output formatters.

    Implementations should follow LLM Affinity principles:
    - Use explicit units in output
    - Include semantic annotations where applicable
    - Provide compact but complete information
    """

    @abstractmethod
    def format_system_info(self, summary: SystemSummary) -> str:
        """Format system summary information.

        Args:
            summary: SystemSummary dataclass

        Returns:
            Formatted string output
        """

    @abstractmethod
    def format_buses(self, system: System) -> str:
        """Format bus information.

        Args:
            system: System object containing buses

        Returns:
            Formatted string output
        """

    @abstractmethod
    def format_branches(self, system: System) -> str:
        """Format branch information.

        Args:
            system: System object containing branches

        Returns:
            Formatted string output
        """

    @abstractmethod
    def format_generators(self, system: System) -> str:
        """Format generator information.

        Args:
            system: System object containing generators

        Returns:
            Formatted string output
        """


class TableFormatter(IFormatter):
    """Human-readable table formatter using Rich library."""

    def format_system_info(self, summary: SystemSummary) -> str:
        """Format system info as a human-readable table."""
        from rich.console import Console
        from rich.table import Table

        console = Console(force_terminal=False, width=80)

        # System Overview Table
        overview = Table(title="System Overview", show_header=False)
        overview.add_column("Property", style="cyan")
        overview.add_column("Value", style="green")

        if summary.name:
            overview.add_row("Name", summary.name)
        overview.add_row("Base MVA", f"{summary.base_mva:.1f}")
        overview.add_row("Buses", str(summary.num_buses))
        overview.add_row("Branches", str(summary.num_branches))
        overview.add_row("Generators", str(summary.num_generators))
        overview.add_row("Loads", str(summary.num_loads))
        overview.add_row("Shunts", str(summary.num_shunts))

        # Bus Types Table
        bus_types = Table(title="Bus Types")
        bus_types.add_column("Type", style="cyan")
        bus_types.add_column("Count", style="green")

        bus_types.add_row("Slack (Type 3)", str(summary.num_slack))
        bus_types.add_row("PV (Type 2)", str(summary.num_pv))
        bus_types.add_row("PQ (Type 1)", str(summary.num_pq))

        # Power Balance Table
        power = Table(title="Power Balance [MW, Mvar]")
        power.add_column("", style="cyan")
        power.add_column("P (MW)", style="green", justify="right")
        power.add_column("Q (Mvar)", style="green", justify="right")

        power.add_row(
            "Total Generation",
            f"{summary.total_generation_mw:.2f}",
            f"{summary.total_generation_mvar:.2f}",
        )
        power.add_row(
            "Total Load",
            f"{summary.total_load_mw:.2f}",
            f"{summary.total_load_mvar:.2f}",
        )

        # Capture output
        with console.capture() as capture:
            console.print(overview)
            console.print()
            console.print(bus_types)
            console.print()
            console.print(power)

        return str(capture.get())

    def format_buses(self, system: System) -> str:
        """Format bus list as a table."""
        from rich.console import Console
        from rich.table import Table

        console = Console(force_terminal=False, width=100)

        table = Table(title="Bus Data")
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Name", style="white")
        table.add_column("Type", style="yellow")
        table.add_column("V [pu]", style="green", justify="right")
        table.add_column("Angle [deg]", style="green", justify="right")
        table.add_column("Base [kV]", style="blue", justify="right")
        table.add_column("Status", style="magenta")

        import math

        for bus in system.buses:
            type_name = {1: "PQ", 2: "PV", 3: "Slack", 4: "Isolated"}.get(bus.bus_type, "Unknown")
            status = VoltageStatus.from_voltage(bus.v_magnitude)
            angle_deg = math.degrees(bus.v_angle)

            table.add_row(
                str(bus.bus_id),
                bus.name or "-",
                type_name,
                f"{bus.v_magnitude:.4f}",
                f"{angle_deg:.2f}",
                f"{bus.base_kv:.1f}",
                status.value,
            )

        with console.capture() as capture:
            console.print(table)

        return str(capture.get())

    def format_branches(self, system: System) -> str:
        """Format branch list as a table."""
        from rich.console import Console
        from rich.table import Table

        console = Console(force_terminal=False, width=100)

        table = Table(title="Branch Data")
        table.add_column("From", style="cyan", justify="right")
        table.add_column("To", style="cyan", justify="right")
        table.add_column("R [pu]", style="green", justify="right")
        table.add_column("X [pu]", style="green", justify="right")
        table.add_column("B [pu]", style="green", justify="right")
        table.add_column("Rate A [MVA]", style="yellow", justify="right")
        table.add_column("Status", style="magenta")

        for branch in system.branches:
            status = "In-Service" if branch.is_in_service else "Out-of-Service"
            rate_str = (
                f"{branch.rate_a:.1f}" if branch.rate_a is not None and branch.rate_a > 0 else "-"
            )
            table.add_row(
                str(branch.from_bus),
                str(branch.to_bus),
                f"{branch.r_pu:.5f}",
                f"{branch.x_pu:.5f}",
                f"{branch.b_pu:.5f}",
                rate_str,
                status,
            )

        with console.capture() as capture:
            console.print(table)

        return str(capture.get())

    def format_generators(self, system: System) -> str:
        """Format generator list as a table."""
        from rich.console import Console
        from rich.table import Table

        console = Console(force_terminal=False, width=100)

        table = Table(title="Generator Data")
        table.add_column("Bus", style="cyan", justify="right")
        table.add_column("ID", style="cyan")
        table.add_column("P [pu]", style="green", justify="right")
        table.add_column("Q [pu]", style="green", justify="right")
        table.add_column("Pmax [pu]", style="yellow", justify="right")
        table.add_column("Pmin [pu]", style="yellow", justify="right")
        table.add_column("Status", style="magenta")

        for gen in system.generators:
            status = "In-Service" if gen.is_in_service else "Out-of-Service"
            p_max_str = f"{gen.p_max:.4f}" if gen.p_max is not None else "-"
            p_min_str = f"{gen.p_min:.4f}" if gen.p_min is not None else "-"
            table.add_row(
                str(gen.bus_id),
                gen.gen_id or "-",
                f"{gen.p_gen:.4f}",
                f"{gen.q_gen:.4f}",
                p_max_str,
                p_min_str,
                status,
            )

        with console.capture() as capture:
            console.print(table)

        return str(capture.get())


class JsonFormatter(IFormatter):
    """JSON formatter for machine-readable output and LLM processing."""

    def format_system_info(self, summary: SystemSummary) -> str:
        """Format system info as JSON."""
        data = {
            "system": {
                "name": summary.name,
                "base_mva": summary.base_mva,
            },
            "counts": {
                "buses": summary.num_buses,
                "branches": summary.num_branches,
                "generators": summary.num_generators,
                "loads": summary.num_loads,
                "shunts": summary.num_shunts,
            },
            "bus_types": {
                "slack": summary.num_slack,
                "pv": summary.num_pv,
                "pq": summary.num_pq,
            },
            "power_balance": {
                "generation": {
                    "p_mw": round(summary.total_generation_mw, 2),
                    "q_mvar": round(summary.total_generation_mvar, 2),
                },
                "load": {
                    "p_mw": round(summary.total_load_mw, 2),
                    "q_mvar": round(summary.total_load_mvar, 2),
                },
            },
        }
        return json.dumps(data, indent=2)

    def format_buses(self, system: System) -> str:
        """Format bus list as JSON."""
        import math

        buses = []
        for bus in system.buses:
            status = VoltageStatus.from_voltage(bus.v_magnitude)
            buses.append(
                {
                    "bus_id": bus.bus_id,
                    "name": bus.name,
                    "type": bus.bus_type,
                    "type_name": {1: "PQ", 2: "PV", 3: "Slack", 4: "Isolated"}.get(bus.bus_type),
                    "voltage_pu": round(bus.v_magnitude, 4),
                    "angle_deg": round(math.degrees(bus.v_angle), 2),
                    "base_kv": bus.base_kv,
                    "voltage_status": status.value,
                }
            )
        return json.dumps({"buses": buses}, indent=2)

    def format_branches(self, system: System) -> str:
        """Format branch list as JSON."""
        branches = []
        for branch in system.branches:
            branches.append(
                {
                    "from_bus": branch.from_bus,
                    "to_bus": branch.to_bus,
                    "r_pu": round(branch.r_pu, 6),
                    "x_pu": round(branch.x_pu, 6),
                    "b_pu": round(branch.b_pu, 6),
                    "rate_a_mva": branch.rate_a if branch.rate_a is not None else None,
                    "in_service": branch.is_in_service,
                }
            )
        return json.dumps({"branches": branches}, indent=2)

    def format_generators(self, system: System) -> str:
        """Format generator list as JSON."""
        generators = []
        for gen in system.generators:
            generators.append(
                {
                    "bus_id": gen.bus_id,
                    "gen_id": gen.gen_id,
                    "p_pu": round(gen.p_gen, 4),
                    "q_pu": round(gen.q_gen, 4),
                    "p_max_pu": round(gen.p_max, 4) if gen.p_max is not None else None,
                    "p_min_pu": round(gen.p_min, 4) if gen.p_min is not None else None,
                    "in_service": gen.is_in_service,
                }
            )
        return json.dumps({"generators": generators}, indent=2)


class SummaryFormatter(IFormatter):
    """Compact summary formatter optimized for LLM token efficiency.

    This formatter produces concise output with semantic annotations,
    ideal for LLM-based analysis where token usage matters.
    """

    def format_system_info(self, summary: SystemSummary) -> str:
        """Format system info as compact summary."""
        name_part = f" ({summary.name})" if summary.name else ""
        lines = [
            f"System{name_part}: {summary.num_buses} buses, {summary.num_branches} branches, "
            f"{summary.num_generators} generators | Base: {summary.base_mva:.0f} MVA",
            f"Types: {summary.num_slack} slack, {summary.num_pv} PV, {summary.num_pq} PQ | "
            f"Loads: {summary.num_loads}, Shunts: {summary.num_shunts}",
            f"Generation: P={summary.total_generation_mw:.1f} MW, "
            f"Q={summary.total_generation_mvar:.1f} Mvar",
            f"Load: P={summary.total_load_mw:.1f} MW, Q={summary.total_load_mvar:.1f} Mvar",
        ]
        return "\n".join(lines)

    def format_buses(self, system: System) -> str:
        """Format buses as compact list with status annotations."""
        import math

        lines = [f"Buses ({len(system.buses)}):"]
        for bus in system.buses:
            type_name = {1: "PQ", 2: "PV", 3: "Slack", 4: "Isolated"}[bus.bus_type]
            status = VoltageStatus.from_voltage(bus.v_magnitude)
            angle_deg = math.degrees(bus.v_angle)
            name_part = f" {bus.name}" if bus.name else ""
            lines.append(
                f"  {bus.bus_id}{name_part}: V={bus.v_magnitude:.3f}pu ({status.value}), "
                f"θ={angle_deg:.1f}°, {type_name}"
            )
        return "\n".join(lines)

    def format_branches(self, system: System) -> str:
        """Format branches as compact list."""
        lines = [f"Branches ({len(system.branches)}):"]
        for branch in system.branches:
            status = "ON" if branch.is_in_service else "OFF"
            lines.append(
                f"  {branch.from_bus}->{branch.to_bus}: "
                f"R={branch.r_pu:.4f}, X={branch.x_pu:.4f} pu [{status}]"
            )
        return "\n".join(lines)

    def format_generators(self, system: System) -> str:
        """Format generators as compact list."""
        lines = [f"Generators ({len(system.generators)}):"]
        for gen in system.generators:
            status = "ON" if gen.is_in_service else "OFF"
            lines.append(f"  Bus {gen.bus_id}: P={gen.p_gen:.3f}, Q={gen.q_gen:.3f} pu [{status}]")
        return "\n".join(lines)


class CsvFormatter(IFormatter):
    """CSV formatter for data analysis and export."""

    def format_system_info(self, summary: SystemSummary) -> str:
        """Format system info as CSV."""
        lines = [
            "property,value",
            f"name,{summary.name}",
            f"base_mva,{summary.base_mva}",
            f"num_buses,{summary.num_buses}",
            f"num_branches,{summary.num_branches}",
            f"num_generators,{summary.num_generators}",
            f"num_loads,{summary.num_loads}",
            f"num_shunts,{summary.num_shunts}",
            f"num_slack,{summary.num_slack}",
            f"num_pv,{summary.num_pv}",
            f"num_pq,{summary.num_pq}",
            f"total_generation_mw,{summary.total_generation_mw:.2f}",
            f"total_generation_mvar,{summary.total_generation_mvar:.2f}",
            f"total_load_mw,{summary.total_load_mw:.2f}",
            f"total_load_mvar,{summary.total_load_mvar:.2f}",
        ]
        return "\n".join(lines)

    def format_buses(self, system: System) -> str:
        """Format buses as CSV."""
        import math

        lines = ["bus_id,name,type,v_pu,angle_deg,base_kv,status"]
        for bus in system.buses:
            status = VoltageStatus.from_voltage(bus.v_magnitude)
            angle_deg = math.degrees(bus.v_angle)
            name = bus.name or ""
            lines.append(
                f"{bus.bus_id},{name},{bus.bus_type},"
                f"{bus.v_magnitude:.4f},{angle_deg:.2f},{bus.base_kv},{status.value}"
            )
        return "\n".join(lines)

    def format_branches(self, system: System) -> str:
        """Format branches as CSV."""
        lines = ["from_bus,to_bus,r_pu,x_pu,b_pu,rate_a,in_service"]
        for branch in system.branches:
            in_service = 1 if branch.is_in_service else 0
            lines.append(
                f"{branch.from_bus},{branch.to_bus},"
                f"{branch.r_pu:.6f},{branch.x_pu:.6f},{branch.b_pu:.6f},"
                f"{branch.rate_a},{in_service}"
            )
        return "\n".join(lines)

    def format_generators(self, system: System) -> str:
        """Format generators as CSV."""
        lines = ["bus_id,gen_id,p_pu,q_pu,p_max_pu,p_min_pu,in_service"]
        for gen in system.generators:
            in_service = 1 if gen.is_in_service else 0
            gen_id = gen.gen_id or ""
            p_max_str = f"{gen.p_max:.4f}" if gen.p_max is not None else ""
            p_min_str = f"{gen.p_min:.4f}" if gen.p_min is not None else ""
            lines.append(
                f"{gen.bus_id},{gen_id},"
                f"{gen.p_gen:.4f},{gen.q_gen:.4f},{p_max_str},{p_min_str},"
                f"{in_service}"
            )
        return "\n".join(lines)


def get_formatter(format_type: OutputFormat | str) -> IFormatter:
    """Factory function to get the appropriate formatter.

    Args:
        format_type: Output format (enum or string)

    Returns:
        Formatter instance

    Raises:
        ValueError: If format type is not recognized
    """
    if isinstance(format_type, str):
        format_type = OutputFormat(format_type.lower())

    formatters: dict[OutputFormat, type[IFormatter]] = {
        OutputFormat.TABLE: TableFormatter,
        OutputFormat.JSON: JsonFormatter,
        OutputFormat.SUMMARY: SummaryFormatter,
        OutputFormat.CSV: CsvFormatter,
    }

    formatter_class = formatters.get(format_type)
    if formatter_class is None:
        raise ValueError(f"Unknown format type: {format_type}")

    return formatter_class()


def create_system_summary(system: System) -> SystemSummary:
    """Create a SystemSummary from a System object.

    Args:
        system: System object to summarize

    Returns:
        SystemSummary dataclass with computed statistics
    """
    total_gen_p, total_gen_q = system.total_generation()
    total_load_p, total_load_q = system.total_load()

    # Voltage statistics
    voltages = [bus.v_magnitude for bus in system.buses]
    voltage_stats: dict[str, int] = {}
    for v in voltages:
        status = VoltageStatus.from_voltage(v).value
        voltage_stats[status] = voltage_stats.get(status, 0) + 1

    return SystemSummary(
        base_mva=system.base_mva,
        num_buses=system.num_buses(),
        num_branches=system.num_branches(),
        num_generators=system.num_generators(),
        num_loads=system.num_loads(),
        num_shunts=system.num_shunts(),
        num_slack=len(system.get_slack_buses()),
        num_pv=len(system.get_pv_buses()),
        num_pq=len(system.get_pq_buses()),
        total_generation_mw=total_gen_p * system.base_mva,
        total_generation_mvar=total_gen_q * system.base_mva,
        total_load_mw=total_load_p * system.base_mva,
        total_load_mvar=total_load_q * system.base_mva,
        name=system.name,
        voltage_range=(min(voltages) if voltages else 0, max(voltages) if voltages else 0),
        voltage_stats=voltage_stats,
    )
