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
        description: Free-text description providing context not captured
            in numerical parameters. For LLM-friendly output.

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
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate shunt data after initialization.

        Raises:
            ValueError: If status is not 0 or 1.
        """
        if self.status not in [0, 1]:
            raise ValueError(
                f"Invalid status: {self.status}. Must be 0 (out-of-service) or 1 (in-service)."
            )

    @property
    def is_in_service(self) -> bool:
        """Check if this shunt is in service."""
        return self.status == 1

    @property
    def is_capacitor(self) -> bool:
        """Check if this shunt is a capacitor (B > 0)."""
        return self.b_pu > 0

    @property
    def is_reactor(self) -> bool:
        """Check if this shunt is a reactor (B < 0)."""
        return self.b_pu < 0

    @property
    def shunt_type_name(self) -> str:
        """Get human-readable shunt type name."""
        if self.b_pu > 0:
            return "Capacitor"
        elif self.b_pu < 0:
            return "Reactor"
        else:
            return "Neutral Shunt"

    def to_description(self) -> str:
        """Generate human/LLM-readable description of this shunt.

        Returns:
            Multi-line string describing the shunt for LLM context.

        Example:
            >>> cap = Shunt(bus_id=1, b_pu=0.5, name="Cap1")
            >>> print(cap.to_description())
            Shunt Cap1 at Bus 1: Capacitor
              Admittance: G = 0.0000 pu, B = 0.5000 pu
              Status: In-service
        """
        name_str = f"{self.name}" if self.name else f"S{self.shunt_id}"
        status_str = "In-service" if self.is_in_service else "Out-of-service"

        lines = [
            f"Shunt {name_str} at Bus {self.bus_id}: {self.shunt_type_name}",
            f"  Admittance: G = {self.g_pu:.4f} pu, B = {self.b_pu:.4f} pu",
            f"  Status: {status_str}",
        ]

        if self.description:
            lines.append(f"  Note: {self.description}")

        return "\n".join(lines)
