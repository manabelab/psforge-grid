"""Branch data model for power system analysis.

This module defines the Branch class representing transmission lines and transformers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from psforge_grid.models.identity import validate_id


@dataclass
class Branch:
    """Branch data class for transmission lines and transformers.

    Represents electrical connections between buses, including transmission lines
    and transformers. Branch impedance parameters define the electrical characteristics
    using the pi-equivalent circuit model.

    Attributes:
        id: Unique string identifier (``[A-Za-z0-9_]+``). Unique across the
            whole system, all element types combined. Parsers generate it
            deterministically from the source data (e.g. ``BR1_2_1`` from
            bus numbers 1-2, circuit "1").
        from_bus_id: ``Bus.id`` of the sending end
        to_bus_id: ``Bus.id`` of the receiving end
        r_pu: Series resistance [p.u.] on system base (positive sequence)
        x_pu: Series reactance [p.u.] on system base (positive sequence)
        b_pu: Total line charging susceptance [p.u.] (default: 0.0)
            For pi-model, B/2 is placed at each end (positive sequence)
        tap_ratio: Off-nominal tap ratio (default: 1.0)
            For transformers: tap_ratio = V_from / V_to (typically)
        shift_angle: Phase shift angle [rad] (default: 0.0)
            For phase-shifting transformers
        rate_a: Continuous thermal rating [MVA] (default: None, unlimited)
        rate_b: Short-term thermal rating [MVA] (default: None)
        rate_c: Emergency thermal rating [MVA] (default: None)
        angmin: Minimum angle difference (theta_from - theta_to) [rad]
            (default: None, unlimited). Used in OPF constraints.
        angmax: Maximum angle difference (theta_from - theta_to) [rad]
            (default: None, unlimited). Used in OPF constraints.
        status: Operating status (1: in-service, 0: out-of-service)
        circuit_id: Circuit identifier for parallel branches in the source
            format (default: None). PSS/E RAW and CPAT provide this; None
            means the source format did not provide one. Kept for lossless
            round-trip; the branch itself is identified by ``id``.
        r0_pu: Zero-sequence series resistance [p.u.] (default: None)
            Used for unbalanced fault analysis (1LG, 2LG).
        x0_pu: Zero-sequence series reactance [p.u.] (default: None)
            Used for unbalanced fault analysis (1LG, 2LG).
        b0_pu: Zero-sequence total line charging susceptance [p.u.] (default: None)
            Used for unbalanced fault analysis (1LG, 2LG).
        winding_connection: Transformer winding connection type (default: None).
            Values: "wye-wye", "delta-wye", "wye-delta", "delta-delta".
            None means the source format did not provide this information.
            Writers may infer from shift_angle if None.
        nomv_from: From-side winding nominal voltage [kV] (default: None).
            None means the source format did not provide this information.
            Writers may infer from the from-side bus base_kv if None.
        nomv_to: To-side winding nominal voltage [kV] (default: None).
            None means the source format did not provide this information.
            Writers may infer from the to-side bus base_kv if None.
        sbase_mva: Transformer rated capacity [MVA] (default: None).
            None means the source format did not provide this information.
            Writers may use system base_mva if None.
        mag_g: Magnetizing conductance [p.u. on system base] (default: None).
            None means the source format did not provide this information.
        mag_b: Magnetizing susceptance [p.u. on system base] (default: None).
            None means the source format did not provide this information.
        is_xfmr: Explicit transformer flag from source format (default: None).
            True if the source format explicitly identified this branch as a
            transformer (e.g., parsed from PSS/E TRANSFORMER DATA section).
            None means the source format did not provide this information.
            Used by is_transformer property as a primary indicator.
        reg_control_mode: Voltage regulation control mode (default: None).
            "secondary" for secondary-side voltage control,
            "primary" for primary-side voltage control.
            None means the source format did not provide this information
            or the transformer does not regulate voltage.
        reg_target_voltage_pu: Target voltage for voltage regulation [p.u.]
            (default: None). None means the source format did not provide
            this information or regulation is not active.
        tap_max: Maximum tap ratio limit (default: None).
            None means the source format did not provide this information.
        tap_min: Minimum tap ratio limit (default: None).
            None means the source format did not provide this information.
        order: Sort/display order (default: None). Parsers assign the
            position within the source file (1.0, 2.0, ...).
        name: Branch name (optional, free text)
        tags: Attribute/grouping tags. Hierarchies use the ``"key:value"``
            convention, e.g. ``["voltage:500kV"]``.
        description: Free-text description providing context not captured
            in numerical parameters. For LLM-friendly output.

    Note:
        - All impedance values are in per-unit on system base MVA
        - For transmission lines: tap_ratio = 1.0, shift_angle = 0.0
        - For transformers: tap_ratio represents the turns ratio
        - Phase shifters: shift_angle is in radians (not degrees)
        - Ratings: rate_a (normal) < rate_b (short-term) < rate_c (emergency)

    Example:
        >>> # Transmission line: 0.01 + j0.1 p.u., B = 0.02 p.u.
        >>> line = Branch("BR1_2_1", "B1", "B2", r_pu=0.01, x_pu=0.1, b_pu=0.02)
        >>> # Transformer with 1.05 tap ratio
        >>> xfmr = Branch("BR1_3_1", "B1", "B3", r_pu=0.0, x_pu=0.05, tap_ratio=1.05)
    """

    id: str
    from_bus_id: str
    to_bus_id: str
    r_pu: float
    x_pu: float
    b_pu: float = 0.0
    tap_ratio: float = 1.0
    shift_angle: float = 0.0
    rate_a: float | None = None
    rate_b: float | None = None
    rate_c: float | None = None
    angmin: float | None = None
    angmax: float | None = None
    status: int = 1
    circuit_id: str | None = None
    r0_pu: float | None = None
    x0_pu: float | None = None
    b0_pu: float | None = None
    winding_connection: str | None = None
    nomv_from: float | None = None
    nomv_to: float | None = None
    sbase_mva: float | None = None
    mag_g: float | None = None
    mag_b: float | None = None
    is_xfmr: bool | None = None
    reg_control_mode: str | None = None
    reg_target_voltage_pu: float | None = None
    tap_max: float | None = None
    tap_min: float | None = None
    order: float | None = None
    name: str | None = None
    tags: list[str] = field(default_factory=list)
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate branch data after initialization.

        Raises:
            ValueError: If id violates the identifier character set, if
                status is not 0 or 1, or if tap_ratio is zero.
        """
        validate_id(self.id, "Branch")
        if self.status not in [0, 1]:
            raise ValueError(
                f"Invalid status: {self.status}. Must be 0 (out-of-service) or 1 (in-service)."
            )
        if self.tap_ratio == 0.0:
            raise ValueError("tap_ratio cannot be zero.")

    @property
    def is_transformer(self) -> bool:
        """Check if this branch is a transformer.

        A branch is identified as a transformer if any of:
        - is_xfmr is True (explicitly flagged by source format parser)
        - tap_ratio != 1.0 (off-nominal turns ratio)
        - shift_angle != 0.0 (phase-shifting transformer)

        Example:
            >>> from psforge_grid.models import Branch
            >>> Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1).is_transformer
            False
            >>> Branch("BR2", "B1", "B2", r_pu=0.0, x_pu=0.1, tap_ratio=1.05).is_transformer
            True
        """
        if self.is_xfmr is True:
            return True
        return self.tap_ratio != 1.0 or self.shift_angle != 0.0

    @property
    def is_in_service(self) -> bool:
        """Check if this branch is in service.

        Example:
            >>> from psforge_grid.models import Branch
            >>> Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1).is_in_service
            True
            >>> Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, status=0).is_in_service
            False
        """
        return self.status == 1

    @property
    def branch_type_name(self) -> str:
        """Get human-readable branch type name.

        Example:
            >>> from psforge_grid.models import Branch
            >>> Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1).branch_type_name
            'Transmission Line'
            >>> Branch("BR2", "B1", "B2", r_pu=0.0, x_pu=0.1, shift_angle=3.0).branch_type_name
            'Phase-Shifting Transformer'
        """
        if self.is_transformer:
            if self.shift_angle != 0.0:
                return "Phase-Shifting Transformer"
            return "Transformer"
        return "Transmission Line"

    @property
    def impedance_pu(self) -> complex:
        """Get positive-sequence series impedance as complex number [p.u.].

        Example:
            >>> from psforge_grid.models import Branch
            >>> Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1).impedance_pu
            (0.01+0.1j)
        """
        return complex(self.r_pu, self.x_pu)

    @property
    def zero_sequence_impedance_pu(self) -> complex | None:
        """Get zero-sequence series impedance as complex number [p.u.].

        Returns:
            Complex impedance if zero-sequence data is available, None otherwise.

        Example:
            >>> from psforge_grid.models import Branch
            >>> Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1,
            ...     r0_pu=0.03, x0_pu=0.3).zero_sequence_impedance_pu
            (0.03+0.3j)
            >>> Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1).zero_sequence_impedance_pu is None
            True
        """
        if self.r0_pu is not None and self.x0_pu is not None:
            return complex(self.r0_pu, self.x0_pu)
        return None

    @property
    def has_zero_sequence_data(self) -> bool:
        """Check if zero-sequence impedance data is available.

        Example:
            >>> from psforge_grid.models import Branch
            >>> Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1).has_zero_sequence_data
            False
            >>> Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1,
            ...     r0_pu=0.03, x0_pu=0.3).has_zero_sequence_data
            True
        """
        return self.r0_pu is not None and self.x0_pu is not None

    def to_description(self) -> str:
        """Generate human/LLM-readable description of this branch.

        Returns:
            Multi-line string describing the branch for LLM context.

        Example:
            >>> branch = Branch("BR1_2_1", "B1", "B2", r_pu=0.01, x_pu=0.1, rate_a=100)
            >>> print(branch.to_description())
            Branch BR1_2_1 (B1-B2): Transmission Line
              Impedance: 0.0100 + j0.1000 pu
              Rating: 100.0 MVA
              Status: In-service
        """
        name_str = f" ({self.name})" if self.name else ""
        status_str = "In-service" if self.is_in_service else "Out-of-service"

        lines = [
            f"Branch {self.id} ({self.from_bus_id}-{self.to_bus_id}){name_str}: "
            f"{self.branch_type_name}",
            f"  Impedance: {self.r_pu:.4f} + j{self.x_pu:.4f} pu",
        ]

        if self.b_pu != 0.0:
            lines.append(f"  Charging: B = {self.b_pu:.4f} pu")

        if self.is_transformer:
            shift_deg = self.shift_angle * 180.0 / math.pi
            lines.append(f"  Tap: {self.tap_ratio:.4f}, Shift: {shift_deg:.2f}°")

        if self.rate_a is not None:
            lines.append(f"  Rating: {self.rate_a:.1f} MVA")

        if self.angmin is not None or self.angmax is not None:
            angmin_deg = math.degrees(self.angmin) if self.angmin is not None else None
            angmax_deg = math.degrees(self.angmax) if self.angmax is not None else None
            min_str = f"{angmin_deg:.1f}°" if angmin_deg is not None else "-∞"
            max_str = f"{angmax_deg:.1f}°" if angmax_deg is not None else "+∞"
            lines.append(f"  Angle limits: [{min_str}, {max_str}]")

        lines.append(f"  Status: {status_str}")

        if self.tags:
            lines.append(f"  Tags: {', '.join(self.tags)}")

        if self.description:
            lines.append(f"  Note: {self.description}")

        return "\n".join(lines)
