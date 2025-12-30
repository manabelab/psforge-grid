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
