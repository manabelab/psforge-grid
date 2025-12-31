"""Load data model for power system analysis.

This module defines the Load class representing electrical loads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Load:
    """Load data class for electrical consumption.

    Represents electrical load connected to a bus. Each load is modeled as
    constant power (P, Q) consumption at the connected bus.

    Attributes:
        bus_id: Bus ID where load is connected
        p_load: Active power demand [p.u.] on system base
        q_load: Reactive power demand [p.u.] on system base (default: 0.0)
        status: Operating status (1: in-service, 0: out-of-service)
        load_id: Load identifier for multiple loads on same bus
        name: Load name (optional)
        description: Free-text description providing context not captured
            in numerical parameters. For LLM-friendly output.

    Note:
        - All power values are in per-unit on system base MVA
        - Positive values indicate power consumption (load)
        - Multiple loads can be connected to the same bus (identified by load_id)
        - Future versions may support ZIP load models (constant Z, I, P components)

    Example:
        >>> # 50 MW + j20 MVAr load on 100 MVA base
        >>> load = Load(bus_id=2, p_load=0.5, q_load=0.2)
        >>> # Multiple loads on same bus
        >>> load_a = Load(bus_id=3, p_load=0.3, load_id="A")
        >>> load_b = Load(bus_id=3, p_load=0.2, load_id="B")
    """

    bus_id: int
    p_load: float
    q_load: float = 0.0
    status: int = 1
    load_id: str = "1"
    name: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate load data after initialization.

        Raises:
            ValueError: If status is not 0 or 1.
        """
        if self.status not in [0, 1]:
            raise ValueError(
                f"Invalid status: {self.status}. Must be 0 (out-of-service) or 1 (in-service)."
            )

    @property
    def is_in_service(self) -> bool:
        """Check if this load is in service."""
        return self.status == 1

    @property
    def apparent_power(self) -> float:
        """Calculate apparent power magnitude [p.u.].

        Returns:
            |S| = sqrt(P^2 + Q^2)
        """
        return math.sqrt(self.p_load**2 + self.q_load**2)

    @property
    def power_factor(self) -> float:
        """Calculate power factor.

        Returns:
            Power factor = P / |S|. Returns 1.0 if S = 0.
        """
        s = self.apparent_power
        if s == 0.0:
            return 1.0
        return self.p_load / s

    def to_description(self) -> str:
        """Generate human/LLM-readable description of this load.

        Returns:
            Multi-line string describing the load for LLM context.

        Example:
            >>> load = Load(bus_id=2, p_load=0.5, q_load=0.2, name="Industrial")
            >>> print(load.to_description())
            Load Industrial at Bus 2
              Demand: P = 0.5000 pu, Q = 0.2000 pu
              Apparent power: 0.5385 pu
              Power factor: 0.93
              Status: In-service
        """
        name_str = f"{self.name}" if self.name else f"L{self.load_id}"
        status_str = "In-service" if self.is_in_service else "Out-of-service"

        lines = [
            f"Load {name_str} at Bus {self.bus_id}",
            f"  Demand: P = {self.p_load:.4f} pu, Q = {self.q_load:.4f} pu",
            f"  Apparent power: {self.apparent_power:.4f} pu",
            f"  Power factor: {self.power_factor:.2f}",
            f"  Status: {status_str}",
        ]

        if self.description:
            lines.append(f"  Note: {self.description}")

        return "\n".join(lines)
