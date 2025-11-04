"""Branch data model for power system analysis.

This module defines the Branch class representing transmission lines and transformers.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Branch:
    """Branch data class for transmission lines and transformers.

    Represents electrical connections between buses, including transmission lines
    and transformers. Branch impedance parameters define the electrical characteristics.

    Attributes:
        from_bus: From-bus ID (sending end)
        to_bus: To-bus ID (receiving end)
        r_pu: Resistance [p.u.]
        x_pu: Reactance [p.u.]
        b_pu: Susceptance [p.u.] (default: 0.0, line charging)
        tap_ratio: Tap ratio (default: 1.0, for transformers)
        shift_angle: Phase shift angle [rad] (default: 0.0, for phase shifters)
        rate_mva: Thermal capacity [MVA] (default: None, unlimited)
        name: Branch name (optional)

    Note:
        - Impedance values (r_pu, x_pu) are in per-unit on system base MVA
        - tap_ratio = 1.0 means no tap change (normal transmission line)
        - shift_angle is used for phase-shifting transformers
        - b_pu represents total line charging susceptance
    """

    from_bus: int
    to_bus: int
    r_pu: float
    x_pu: float
    b_pu: float = 0.0
    tap_ratio: float = 1.0
    shift_angle: float = 0.0
    rate_mva: Optional[float] = None
    name: Optional[str] = None
