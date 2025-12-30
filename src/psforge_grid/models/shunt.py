"""Shunt data model for power system analysis.

This module defines the Shunt class representing shunt devices such as
capacitors and reactors in a power system.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Shunt:
    """Shunt data class for capacitors and reactors.

    Represents shunt devices connected to a bus, including fixed shunts
    (capacitors, reactors) and switched shunts. Used for reactive power
    compensation and voltage control in power flow analysis.

    Attributes:
        bus_id: Bus ID where shunt is connected
        g_pu: Shunt conductance [p.u.] on system base (default: 0.0)
        b_pu: Shunt susceptance [p.u.] on system base (default: 0.0)
            Positive for capacitors, negative for reactors
        status: Operating status (1: in-service, 0: out-of-service)
        shunt_id: Shunt identifier for multiple shunts on same bus
        name: Shunt name (optional)

    Note:
        - Susceptance (B) convention: B > 0 for capacitors (leading VAr),
          B < 0 for reactors (lagging VAr)
        - Conductance (G) represents shunt losses (typically small)
        - All values are in per-unit on system base MVA
        - Shunt power injection: P + jQ = V^2 * (G + jB)

    Example:
        >>> # 50 MVAr capacitor on 100 MVA base
        >>> cap = Shunt(bus_id=1, b_pu=0.5)  # B = 50/100 = 0.5 p.u.
        >>> # 30 MVAr reactor on 100 MVA base
        >>> reactor = Shunt(bus_id=2, b_pu=-0.3)  # B = -30/100 = -0.3 p.u.
    """

    bus_id: int
    g_pu: float = 0.0
    b_pu: float = 0.0
    status: int = 1
    shunt_id: str = "1"
    name: str | None = None

    def __post_init__(self) -> None:
        """Validate shunt data after initialization.

        Raises:
            ValueError: If status is not 0 or 1.
        """
        if self.status not in [0, 1]:
            raise ValueError(
                f"Invalid status: {self.status}. Must be 0 (out-of-service) or 1 (in-service)."
            )
