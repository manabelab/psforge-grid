"""Bus numbering helper for writers that require integer bus numbers.

PSS/E RAW, MATPOWER and the CPAT formats identify buses by integer number.
Since 0.10.0 the data model identifies elements by string ``id`` and keeps
the source number only as optional round-trip data (``Bus.number``), so a
hand-built system may have no numbers at all. Writers use this helper to
get a complete, collision-free mapping: source-provided numbers are kept
as-is, and buses without one are assigned the lowest unused positive
integers in list order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psforge_grid.models.system import System


def bus_number_map(system: System) -> dict[str, int]:
    """Map every ``Bus.id`` to an integer bus number for numeric formats.

    Buses with ``number`` set keep it. Buses without one are assigned the
    smallest positive integers not already taken, in list order, so the
    assignment is deterministic and never collides with real numbers.

    Args:
        system: System whose buses need numbering.

    Returns:
        Mapping from ``Bus.id`` to integer bus number.

    Raises:
        ValueError: If two buses carry the same source-provided ``number``
            (the mapping could not round-trip losslessly).

    Example:
        >>> from psforge_grid.models import Bus, System
        >>> system = System(buses=[
        ...     Bus("B5", bus_type=3, number=5),
        ...     Bus("Bnew", bus_type=1),  # no source number
        ... ])
        >>> bus_number_map(system)
        {'B5': 5, 'Bnew': 1}
    """
    taken: dict[int, str] = {}
    for bus in system.buses:
        if bus.number is None:
            continue
        if bus.number in taken:
            raise ValueError(
                f"Duplicate Bus.number {bus.number}: used by {taken[bus.number]!r} "
                f"and {bus.id!r}. Numeric formats cannot represent this."
            )
        taken[bus.number] = bus.id

    mapping: dict[str, int] = {}
    next_free = 1
    for bus in system.buses:
        if bus.number is not None:
            mapping[bus.id] = bus.number
        else:
            while next_free in taken:
                next_free += 1
            mapping[bus.id] = next_free
            taken[next_free] = bus.id
    return mapping
