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
        p_gen: Active power output [p.u.] on system base
        q_gen: Reactive power output [p.u.] on system base (default: 0.0)
        v_setpoint: Voltage setpoint [p.u.] (default: 1.0)
            Used for PV buses to control voltage magnitude
        p_max: Maximum active power [p.u.] (default: None, unlimited)
        p_min: Minimum active power [p.u.] (default: None, unlimited)
        q_max: Maximum reactive power [p.u.] (default: None, unlimited)
        q_min: Minimum reactive power [p.u.] (default: None, unlimited)
        mbase: Machine base MVA (default: 100.0)
            Used for converting machine-specific parameters
        status: Operating status (1: in-service, 0: out-of-service)
        gen_id: Generator identifier for multiple generators on same bus
        name: Generator name (optional)

    Note:
        - All power values are in per-unit on system base MVA
        - v_setpoint is used for PV (generator) buses to control voltage magnitude
        - During power flow, if Q limits are violated, the bus may switch from PV to PQ
        - gen_id distinguishes multiple generators connected to the same bus
        - mbase is the machine's own MVA rating (for impedance conversion)

    Example:
        >>> # 100 MW generator with Q limits
        >>> gen = Generator(
        ...     bus_id=1,
        ...     p_gen=1.0,  # 100 MW on 100 MVA base
        ...     v_setpoint=1.02,
        ...     q_max=0.5,  # 50 MVAr
        ...     q_min=-0.3  # -30 MVAr
        ... )
    """

    bus_id: int
    p_gen: float
    q_gen: float = 0.0
    v_setpoint: float = 1.0
    p_max: float | None = None
    p_min: float | None = None
    q_max: float | None = None
    q_min: float | None = None
    mbase: float = 100.0
    status: int = 1
    gen_id: str = "1"
    name: str | None = None

    def __post_init__(self) -> None:
        """Validate generator data after initialization.

        Raises:
            ValueError: If status is not 0 or 1.
        """
        if self.status not in [0, 1]:
            raise ValueError(
                f"Invalid status: {self.status}. Must be 0 (out-of-service) or 1 (in-service)."
            )

    @property
    def is_in_service(self) -> bool:
        """Check if this generator is in service."""
        return self.status == 1

    def check_q_limits(self, q_value: float) -> tuple[bool, float]:
        """Check if reactive power is within limits.

        Args:
            q_value: Reactive power value to check [p.u.]

        Returns:
            Tuple of (within_limits, limited_value)
            - within_limits: True if q_value is within [q_min, q_max]
            - limited_value: q_value clamped to limits if necessary
        """
        limited = q_value
        within = True

        if self.q_max is not None and q_value > self.q_max:
            limited = self.q_max
            within = False
        elif self.q_min is not None and q_value < self.q_min:
            limited = self.q_min
            within = False

        return within, limited
