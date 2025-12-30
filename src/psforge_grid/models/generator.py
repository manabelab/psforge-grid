"""Generator data model for power system analysis.

This module defines the Generator class representing power generation units.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Generator:
    """Generator data class for power generation units.

    Represents power generation equipment connected to a bus, including
    output limits and voltage control capabilities.

    Attributes:
        bus_id: Bus ID where generator is connected
        p_gen: Active power output [p.u.]
        q_gen: Reactive power output [p.u.] (default: 0.0)
        v_setpoint: Voltage setpoint [p.u.] (default: 1.0, for PV buses)
        p_max: Maximum active power [p.u.] (default: None, unlimited)
        p_min: Minimum active power [p.u.] (default: None, unlimited)
        q_max: Maximum reactive power [p.u.] (default: None, unlimited)
        q_min: Minimum reactive power [p.u.] (default: None, unlimited)
        name: Generator name (optional)

    Note:
        - v_setpoint is used for PV (generator) buses to control voltage magnitude
        - Power limits (p_max, p_min, q_max, q_min) define operational constraints
        - All power values are in per-unit on system base MVA
    """

    bus_id: int
    p_gen: float
    q_gen: float = 0.0
    v_setpoint: float = 1.0
    p_max: float | None = None
    p_min: float | None = None
    q_max: float | None = None
    q_min: float | None = None
    name: str | None = None
