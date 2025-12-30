"""Bus data model for power system analysis.

This module defines the Bus class representing electrical buses in a power system.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Bus:
    """Bus data class for power system analysis.

    Represents an electrical bus with voltage, power, and type information.
    Used as the fundamental node component in power system network analysis.

    Attributes:
        bus_id: Bus ID (integer starting from 1)
        bus_type: Bus type (1: PQ, 2: PV, 3: Slack/Swing)
        v_magnitude: Voltage magnitude [p.u.] (default: 1.0)
        v_angle: Voltage angle [rad] (default: 0.0)
        p_load: Active power load [p.u.] (default: 0.0)
        q_load: Reactive power load [p.u.] (default: 0.0)
        p_gen: Active power generation [p.u.] (default: 0.0)
        q_gen: Reactive power generation [p.u.] (default: 0.0)
        base_kv: Base voltage [kV] (default: 1.0)
        name: Bus name (optional)

    Note:
        - Bus types: 1 (PQ/Load bus), 2 (PV/Generator bus), 3 (Slack/Swing bus)
        - Per-unit (p.u.) values are normalized by system base MVA
        - Voltage angle is in radians, not degrees
    """

    bus_id: int
    bus_type: int  # 1: PQ, 2: PV, 3: Slack
    v_magnitude: float = 1.0
    v_angle: float = 0.0
    p_load: float = 0.0
    q_load: float = 0.0
    p_gen: float = 0.0
    q_gen: float = 0.0
    base_kv: float = 1.0
    name: str | None = None

    def __post_init__(self) -> None:
        """Validate bus data after initialization.

        Raises:
            ValueError: If bus_type is not 1, 2, or 3.
        """
        if self.bus_type not in [1, 2, 3]:
            raise ValueError(
                f"Invalid bus_type: {self.bus_type}. Must be 1 (PQ), 2 (PV), or 3 (Slack)."
            )
