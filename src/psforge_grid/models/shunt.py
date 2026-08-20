"""Shunt data model for power system analysis.

This module defines the Shunt class representing shunt devices such as
capacitors and reactors in a power system.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from psforge_grid.models.identity import validate_id


@dataclass
class Shunt:
    """Shunt data class for capacitors and reactors.

    Represents shunt devices connected to a bus, including fixed shunts
    (capacitors, reactors) and switched shunts. Used for reactive power
    compensation and voltage control in power flow analysis.

    Attributes:
        id: Unique string identifier (``[A-Za-z0-9_]+``). Unique across the
            whole system, all element types combined. Parsers generate it
            deterministically from the source data (e.g. ``SH3_1`` from bus
            number 3, shunt ID "1").
        bus_id: ``Bus.id`` of the bus where the shunt is connected
        g_pu: Shunt conductance [p.u.] on system base (default: 0.0)
        b_pu: Shunt susceptance [p.u.] on system base (default: 0.0)
            Positive for capacitors, negative for reactors
        status: Operating status (1: in-service, 0: out-of-service)
        shunt_id: Shunt identifier in the source format (default: None).
            PSS/E RAW provides this (e.g. "1"); None means the source format
            did not provide one. Kept for lossless round-trip; the shunt
            itself is identified by ``id``.
        kv: Rated voltage [kV] (default: None).
            None means the source format did not provide this information.
            Writers may infer from the connected bus base_kv if None.
        connection: Winding connection type (default: None).
            Values: "wye" or "delta".
            None means the source format did not provide this information.
        num_steps: Number of switchable steps (default: None).
            None means the source format did not provide this information
            or the shunt is a fixed (non-switched) device.
        order: Sort/display order (default: None). Parsers assign the
            position within the source file (1.0, 2.0, ...).
        name: Shunt name (optional, free text)
        tags: Attribute/grouping tags. Hierarchies use the ``"key:value"``
            convention, e.g. ``["voltage:275kV"]``.
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
        >>> cap = Shunt("SH1_1", bus_id="B1", b_pu=0.5)  # B = 50/100 = 0.5 p.u.
        >>> # 30 MVAr reactor on 100 MVA base
        >>> reactor = Shunt("SH2_1", bus_id="B2", b_pu=-0.3)  # B = -30/100 = -0.3 p.u.
    """

    id: str
    bus_id: str
    g_pu: float = 0.0
    b_pu: float = 0.0
    status: int = 1
    shunt_id: str | None = None
    kv: float | None = None
    connection: str | None = None
    num_steps: int | None = None
    order: float | None = None
    name: str | None = None
    tags: list[str] = field(default_factory=list)
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate shunt data after initialization.

        Raises:
            ValueError: If id violates the identifier character set, or if
                status is not 0 or 1.
        """
        validate_id(self.id, "Shunt")
        if self.status not in [0, 1]:
            raise ValueError(
                f"Invalid status: {self.status}. Must be 0 (out-of-service) or 1 (in-service)."
            )

    @property
    def is_in_service(self) -> bool:
        """Check if this shunt is in service.

        Example:
            >>> from psforge_grid.models import Shunt
            >>> Shunt("SH1", bus_id="B3", b_pu=0.19).is_in_service
            True
            >>> Shunt("SH1", bus_id="B3", b_pu=0.19, status=0).is_in_service
            False
        """
        return self.status == 1

    @property
    def is_capacitor(self) -> bool:
        """Check if this shunt is a capacitor (B > 0).

        Example:
            >>> from psforge_grid.models import Shunt
            >>> Shunt("SH1", bus_id="B3", b_pu=0.19).is_capacitor
            True
            >>> Shunt("SH1", bus_id="B3", b_pu=-0.2).is_capacitor
            False
        """
        return self.b_pu > 0

    @property
    def is_reactor(self) -> bool:
        """Check if this shunt is a reactor (B < 0).

        Example:
            >>> from psforge_grid.models import Shunt
            >>> Shunt("SH1", bus_id="B3", b_pu=-0.2).is_reactor
            True
            >>> Shunt("SH1", bus_id="B3", b_pu=0.19).is_reactor
            False
        """
        return self.b_pu < 0

    @property
    def shunt_type_name(self) -> str:
        """Get human-readable shunt type name.

        Example:
            >>> from psforge_grid.models import Shunt
            >>> Shunt("SH1", bus_id="B3", b_pu=0.19).shunt_type_name
            'Capacitor'
            >>> Shunt("SH1", bus_id="B3", b_pu=-0.2).shunt_type_name
            'Reactor'
        """
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
            >>> cap = Shunt("SH1_1", bus_id="B1", b_pu=0.5, name="Cap1")
            >>> print(cap.to_description())
            Shunt SH1_1 (Cap1) at Bus B1: Capacitor
              Admittance: G = 0.0000 pu, B = 0.5000 pu
              Status: In-service
        """
        name_str = f" ({self.name})" if self.name else ""
        status_str = "In-service" if self.is_in_service else "Out-of-service"

        lines = [
            f"Shunt {self.id}{name_str} at Bus {self.bus_id}: {self.shunt_type_name}",
            f"  Admittance: G = {self.g_pu:.4f} pu, B = {self.b_pu:.4f} pu",
            f"  Status: {status_str}",
        ]

        if self.tags:
            lines.append(f"  Tags: {', '.join(self.tags)}")

        if self.description:
            lines.append(f"  Note: {self.description}")

        return "\n".join(lines)
