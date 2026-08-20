"""Shared identity validation for psforge-grid data models.

Every element in a :class:`~psforge_grid.models.system.System` (Bus, Branch,
Generator, Load, Shunt, GeneratorCost) carries a common identity layer:

- ``id``: unique string identifier (``^[A-Za-z0-9_]+$``, unique across the
  whole system, all element types combined)
- ``order``: optional float defining display/sort order
- ``name``: optional human-readable name (free text)
- ``tags``: list of attribute/grouping tags

This module holds the pieces of that contract that individual models can
enforce on their own: the identifier character set. Uniqueness can only be
checked where all elements are visible, so it lives in
:meth:`System.validate` and the ``System.add_*`` methods.

Tag convention:
    Hierarchies (region, voltage class, facility) are expressed as
    ``"key:value"`` tags until a dedicated field exists, e.g.
    ``["area:kansai", "voltage:500kV", "facility:shin_osaka"]``.
"""

from __future__ import annotations

import re

ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
"""Allowed identifier syntax: ASCII letters, digits and underscore, non-empty."""


def validate_id(id_: str, owner: str) -> None:
    """Validate an element identifier against the psforge-grid ID contract.

    Args:
        id_: Identifier to validate.
        owner: Class name of the element being validated, used in the
            error message (e.g. ``"Bus"``).

    Raises:
        ValueError: If ``id_`` is empty or contains characters outside
            ``[A-Za-z0-9_]``.

    Example:
        >>> from psforge_grid.models.identity import validate_id
        >>> validate_id("B1", "Bus")  # valid: silently returns
        >>> validate_id("B-1", "Bus")
        Traceback (most recent call last):
        ...
        ValueError: Invalid Bus id: 'B-1'. Identifiers must match [A-Za-z0-9_]+ (ASCII letters, digits, underscore; e.g. 'B1', 'BR1').
    """
    if not isinstance(id_, str) or not ID_PATTERN.match(id_):
        raise ValueError(
            f"Invalid {owner} id: {id_!r}. Identifiers must match [A-Za-z0-9_]+ "
            "(ASCII letters, digits, underscore; e.g. 'B1', 'BR1')."
        )


def sanitize_id(raw: str) -> str:
    """Map an arbitrary source-format key onto the identifier character set.

    Every character outside ``[A-Za-z0-9_]`` becomes an underscore, so the
    result is always a valid identifier fragment and the transformation is
    deterministic (same input, same output). Used by parsers and
    :meth:`System.assign_ids` when building ids from source keys such as
    PSS/E circuit IDs or OpenDSS names.

    Args:
        raw: Source-format key (may contain spaces, hyphens, etc.).

    Returns:
        Sanitized fragment; ``"_"`` if ``raw`` is empty.

    Example:
        >>> from psforge_grid.models.identity import sanitize_id
        >>> sanitize_id("Source Bus-1")
        'Source_Bus_1'
        >>> sanitize_id("")
        '_'
    """
    return re.sub(r"[^A-Za-z0-9_]", "_", raw) or "_"


def make_unique(id_: str, used: set[str]) -> str:
    """Resolve an id collision by appending a numeric suffix.

    Args:
        id_: Candidate id.
        used: Ids already taken. Not modified; the caller records the
            returned id.

    Returns:
        ``id_`` itself if free, otherwise the first free ``id__2``,
        ``id__3``, ... (suffix ``_2`` onward, matching "second occurrence").

    Example:
        >>> from psforge_grid.models.identity import make_unique
        >>> make_unique("B1", set())
        'B1'
        >>> make_unique("B1", {"B1"})
        'B1_2'
    """
    if id_ not in used:
        return id_
    n = 2
    while f"{id_}_{n}" in used:
        n += 1
    return f"{id_}_{n}"
