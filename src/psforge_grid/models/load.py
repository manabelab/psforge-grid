"""Load data model for power system analysis.

This module defines the Load class representing electrical loads.
Note: In the current implementation, load data is integrated into the Bus class.
This module is provided for future extensibility.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Load:
    """Load data class for electrical consumption.

    Represents electrical load connected to a bus. Currently, loads are
    typically represented directly in the Bus class (p_load, q_load).
    This class is provided for future extensibility and compatibility.

    Attributes:
        bus_id: Bus ID where load is connected
        p_load: Active power demand [p.u.]
        q_load: Reactive power demand [p.u.] (default: 0.0)
        name: Load name (optional)

    Note:
        - All power values are in per-unit on system base MVA
        - In most cases, load data is stored directly in Bus objects
        - This class allows for more detailed load modeling in future versions
    """

    bus_id: int
    p_load: float
    q_load: float = 0.0
    name: str | None = None
