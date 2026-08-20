"""Load data model for power system analysis.

This module defines the Load class representing electrical loads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from psforge_grid.models.identity import validate_id


@dataclass
class Load:
    """Load data class for electrical consumption.

    Represents electrical load connected to a bus. Each load is modeled as
    constant power (P, Q) consumption at the connected bus.

    Attributes:
        id: Unique string identifier (``[A-Za-z0-9_]+``). Unique across the
            whole system, all element types combined. Parsers generate it
            deterministically from the source data (e.g. ``LD2_1`` from bus
            number 2, load ID "1").
        bus_id: ``Bus.id`` of the bus where the load is connected
        p_load: Active power demand [p.u.] on system base
        q_load: Reactive power demand [p.u.] on system base (default: 0.0)
        status: Operating status (1: in-service, 0: out-of-service)
        load_id: Load identifier in the source format (default: None).
            PSS/E RAW provides this (e.g. "1"); None means the source format
            did not provide one. Kept for lossless round-trip; the load
            itself is identified by ``id``.
        kv: Rated voltage [kV] (default: None).
            None means the source format did not provide this information.
            Writers may infer from the connected bus base_kv if None.
        connection: Winding connection type (default: None).
            Values: "wye" or "delta".
            None means the source format did not provide this information.
        model_type: Load model type (default: None).
            OpenDSS convention: 1=constant PQ, 2=constant Z, 5=ZIP, etc.
            None means the source format did not provide this information.
        order: Sort/display order (default: None). Parsers assign the
            position within the source file (1.0, 2.0, ...).
        name: Load name (optional, free text)
        tags: Attribute/grouping tags. Hierarchies use the ``"key:value"``
            convention, e.g. ``["area:kansai"]``.
        description: Free-text description providing context not captured
            in numerical parameters. For LLM-friendly output.

    Note:
        - All power values are in per-unit on system base MVA
        - Positive values indicate power consumption (load)
        - Multiple loads can be connected to the same bus
        - Future versions may support ZIP load models (constant Z, I, P components)

    Example:
        >>> # 50 MW + j20 MVAr load on 100 MVA base
        >>> load = Load("LD2_1", bus_id="B2", p_load=0.5, q_load=0.2)
        >>> # Multiple loads on same bus
        >>> load_a = Load("LD3_A", bus_id="B3", p_load=0.3)
        >>> load_b = Load("LD3_B", bus_id="B3", p_load=0.2)
    """

    id: str
    bus_id: str
    p_load: float
    q_load: float = 0.0
    status: int = 1
    load_id: str | None = None
    kv: float | None = None
    connection: str | None = None
    model_type: int | None = None
    order: float | None = None
    name: str | None = None
    tags: list[str] = field(default_factory=list)
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate load data after initialization.

        Raises:
            ValueError: If id violates the identifier character set, or if
                status is not 0 or 1.
        """
        validate_id(self.id, "Load")
        if self.status not in [0, 1]:
            raise ValueError(
                f"Invalid status: {self.status}. Must be 0 (out-of-service) or 1 (in-service)."
            )

    @property
    def is_in_service(self) -> bool:
        """Check if this load is in service.

        Example:
            >>> from psforge_grid.models import Load
            >>> Load("LD1", bus_id="B2", p_load=0.8).is_in_service
            True
            >>> Load("LD1", bus_id="B2", p_load=0.8, status=0).is_in_service
            False
        """
        return self.status == 1

    @property
    def apparent_power(self) -> float:
        """Calculate apparent power magnitude [p.u.].

        Returns:
            |S| = sqrt(P^2 + Q^2)

        Example:
            >>> from psforge_grid.models import Load
            >>> Load("LD1", bus_id="B2", p_load=0.8, q_load=0.6).apparent_power
            1.0
        """
        return math.sqrt(self.p_load**2 + self.q_load**2)

    @property
    def power_factor(self) -> float:
        """Calculate power factor.

        Returns:
            Power factor = P / |S|. Returns 1.0 if S = 0.

        Example:
            >>> from psforge_grid.models import Load
            >>> Load("LD1", bus_id="B2", p_load=0.8, q_load=0.6).power_factor
            0.8
            >>> Load("LD1", bus_id="B2", p_load=0.0, q_load=0.0).power_factor  # S = 0
            1.0
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
            >>> load = Load("LD2_1", bus_id="B2", p_load=0.5, q_load=0.2, name="Industrial")
            >>> print(load.to_description())
            Load LD2_1 (Industrial) at Bus B2
              Demand: P = 0.5000 pu, Q = 0.2000 pu
              Apparent power: 0.5385 pu
              Power factor: 0.93
              Status: In-service
        """
        name_str = f" ({self.name})" if self.name else ""
        status_str = "In-service" if self.is_in_service else "Out-of-service"

        lines = [
            f"Load {self.id}{name_str} at Bus {self.bus_id}",
            f"  Demand: P = {self.p_load:.4f} pu, Q = {self.q_load:.4f} pu",
            f"  Apparent power: {self.apparent_power:.4f} pu",
            f"  Power factor: {self.power_factor:.2f}",
            f"  Status: {status_str}",
        ]

        if self.tags:
            lines.append(f"  Tags: {', '.join(self.tags)}")

        if self.description:
            lines.append(f"  Note: {self.description}")

        return "\n".join(lines)
