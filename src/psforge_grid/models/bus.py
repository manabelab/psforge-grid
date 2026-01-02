"""Bus data model for power system analysis.

This module defines the Bus class representing electrical buses in a power system.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Bus:
    """Bus data class for power system analysis.

    Represents an electrical bus (node) with voltage and type information.
    Used as the fundamental node component in power system network analysis.

    Attributes:
        bus_id: Bus ID (integer starting from 1)
        bus_type: Bus type code:
            - 1: PQ bus (load bus) - P and Q are specified
            - 2: PV bus (generator bus) - P and V magnitude are specified
            - 3: Slack/Swing bus - V magnitude and angle are specified
            - 4: Isolated bus - disconnected from the network
        v_magnitude: Voltage magnitude [p.u.] (default: 1.0)
        v_angle: Voltage angle [rad] (default: 0.0)
        base_kv: Base voltage [kV] (default: 1.0)
        area: Area number for interchange control (default: 1)
        zone: Zone number for administrative grouping (default: 1)
        v_max: Maximum voltage limit [p.u.] (default: 1.1)
        v_min: Minimum voltage limit [p.u.] (default: 0.9)
        name: Bus name (optional)
        description: Free-text description providing context not captured
            in numerical parameters. For LLM-friendly output.

    Note:
        - Per-unit (p.u.) values are normalized by system base MVA
        - Voltage angle is in radians, not degrees
        - Load and generation data are stored separately in Load and Generator objects
        - Voltage limits (v_max, v_min) are used for OPF and voltage control studies

    Example:
        >>> # Create a PV (generator) bus at 230 kV
        >>> gen_bus = Bus(bus_id=1, bus_type=2, base_kv=230.0, v_magnitude=1.02)
        >>> # Create a PQ (load) bus
        >>> load_bus = Bus(bus_id=2, bus_type=1, base_kv=230.0)
    """

    bus_id: int
    bus_type: int  # 1: PQ, 2: PV, 3: Slack, 4: Isolated
    v_magnitude: float = 1.0
    v_angle: float = 0.0
    base_kv: float = 1.0
    area: int = 1
    zone: int = 1
    v_max: float = 1.1
    v_min: float = 0.9
    name: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate bus data after initialization.

        Raises:
            ValueError: If bus_type is not 1, 2, 3, or 4.
        """
        if self.bus_type not in [1, 2, 3, 4]:
            raise ValueError(
                f"Invalid bus_type: {self.bus_type}. "
                "Must be 1 (PQ), 2 (PV), 3 (Slack), or 4 (Isolated)."
            )

    @property
    def is_pq(self) -> bool:
        """Check if this is a PQ (load) bus."""
        return self.bus_type == 1

    @property
    def is_pv(self) -> bool:
        """Check if this is a PV (generator) bus."""
        return self.bus_type == 2

    @property
    def is_slack(self) -> bool:
        """Check if this is a slack (swing) bus."""
        return self.bus_type == 3

    @property
    def is_isolated(self) -> bool:
        """Check if this is an isolated bus."""
        return self.bus_type == 4

    @property
    def bus_type_name(self) -> str:
        """Get human-readable bus type name."""
        type_names = {1: "PQ (Load)", 2: "PV (Generator)", 3: "Slack", 4: "Isolated"}
        return type_names.get(self.bus_type, f"Unknown ({self.bus_type})")

    def to_description(self) -> str:
        """Generate human/LLM-readable description of this bus.

        Returns:
            Multi-line string describing the bus for LLM context.

        Example:
            >>> bus = Bus(bus_id=1, bus_type=3, base_kv=500.0, name="Main")
            >>> print(bus.to_description())
            Bus 1 (Main): Slack bus at 500.0 kV
              Voltage: 1.0000 pu @ 0.00°
              Limits: 0.90 - 1.10 pu
        """
        name_str = f" ({self.name})" if self.name else ""
        v_angle_deg = self.v_angle * 180.0 / 3.14159265359

        lines = [
            f"Bus {self.bus_id}{name_str}: {self.bus_type_name} at {self.base_kv:.1f} kV",
            f"  Voltage: {self.v_magnitude:.4f} pu @ {v_angle_deg:.2f}°",
            f"  Limits: {self.v_min:.2f} - {self.v_max:.2f} pu",
        ]

        if self.description:
            lines.append(f"  Note: {self.description}")

        return "\n".join(lines)
