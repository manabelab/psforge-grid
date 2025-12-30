"""Branch data model for power system analysis.

This module defines the Branch class representing transmission lines and transformers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Branch:
    """Branch data class for transmission lines and transformers.

    Represents electrical connections between buses, including transmission lines
    and transformers. Branch impedance parameters define the electrical characteristics
    using the pi-equivalent circuit model.

    Attributes:
        from_bus: From-bus ID (sending end)
        to_bus: To-bus ID (receiving end)
        r_pu: Series resistance [p.u.] on system base
        x_pu: Series reactance [p.u.] on system base
        b_pu: Total line charging susceptance [p.u.] (default: 0.0)
            For pi-model, B/2 is placed at each end
        tap_ratio: Off-nominal tap ratio (default: 1.0)
            For transformers: tap_ratio = V_from / V_to (typically)
        shift_angle: Phase shift angle [rad] (default: 0.0)
            For phase-shifting transformers
        rate_a: Continuous thermal rating [MVA] (default: None, unlimited)
        rate_b: Short-term thermal rating [MVA] (default: None)
        rate_c: Emergency thermal rating [MVA] (default: None)
        status: Operating status (1: in-service, 0: out-of-service)
        circuit_id: Circuit identifier for parallel branches (default: "1")
        name: Branch name (optional)

    Note:
        - All impedance values are in per-unit on system base MVA
        - For transmission lines: tap_ratio = 1.0, shift_angle = 0.0
        - For transformers: tap_ratio represents the turns ratio
        - Phase shifters: shift_angle is in radians (not degrees)
        - Ratings: rate_a (normal) < rate_b (short-term) < rate_c (emergency)
        - circuit_id distinguishes parallel lines between same buses

    Example:
        >>> # Transmission line: 0.01 + j0.1 p.u., B = 0.02 p.u.
        >>> line = Branch(from_bus=1, to_bus=2, r_pu=0.01, x_pu=0.1, b_pu=0.02)
        >>> # Transformer with 1.05 tap ratio
        >>> xfmr = Branch(from_bus=1, to_bus=3, r_pu=0.0, x_pu=0.05, tap_ratio=1.05)
    """

    from_bus: int
    to_bus: int
    r_pu: float
    x_pu: float
    b_pu: float = 0.0
    tap_ratio: float = 1.0
    shift_angle: float = 0.0
    rate_a: float | None = None
    rate_b: float | None = None
    rate_c: float | None = None
    status: int = 1
    circuit_id: str = "1"
    name: str | None = None

    def __post_init__(self) -> None:
        """Validate branch data after initialization.

        Raises:
            ValueError: If status is not 0 or 1, or if tap_ratio is zero.
        """
        if self.status not in [0, 1]:
            raise ValueError(
                f"Invalid status: {self.status}. Must be 0 (out-of-service) or 1 (in-service)."
            )
        if self.tap_ratio == 0.0:
            raise ValueError("tap_ratio cannot be zero.")

    @property
    def is_transformer(self) -> bool:
        """Check if this branch is a transformer (tap_ratio != 1.0 or shift_angle != 0.0)."""
        return self.tap_ratio != 1.0 or self.shift_angle != 0.0

    @property
    def is_in_service(self) -> bool:
        """Check if this branch is in service."""
        return self.status == 1
