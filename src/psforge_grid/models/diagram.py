"""Diagram data models for GUI/graphical layout representation.

This module defines data structures for storing single-line diagram layouts
(schematic) and geographic coordinates (geographic) alongside the electrical
power system data.

Coordinate Systems:
    - "schematic": Single-line diagram layout.
        X-axis: right is positive. Y-axis: up is positive (math convention).
        Units: integer (pixel-equivalent, Full HD-aligned).
        No coordinate range limits — canvas expands in all directions.
    - "geographic": Real-world geographic positions.
        X-axis: east is positive (longitude). Y-axis: north is positive (latitude).
        Units: degrees. CRS required (default: EPSG:4326 / WGS84).

Normalization (schematic only):
    When importing from external formats (CPAT .pop, OpenDSS, etc.), coordinates
    are normalized so that the short edge of the bounding box maps to
    ``normalization_ref`` (default: 1920, aligned with Full HD resolution).
    The long edge scales proportionally to preserve aspect ratio.
    Padding (default: 5%) is added on all sides.

    Once normalized, coordinates are stored as-is in psforge JSON format.
    No re-normalization is performed on load.

Example:
    >>> from psforge_grid.models.diagram import DiagramData, BusPosition
    >>> diagram = DiagramData(
    ...     coordinate_system="schematic",
    ...     bus_positions={"B1": BusPosition(x=960, y=540)},
    ... )
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BusPosition:
    """Position of a bus on the diagram.

    For schematic diagrams, x increases to the right and y increases upward.
    For geographic diagrams, x is longitude (east positive) and y is latitude
    (north positive).

    Attributes:
        x: X coordinate (right/east is positive).
        y: Y coordinate (up/north is positive).
        points: Optional list of (x, y) points for busbar rendering.
            Used when a bus is drawn as a line segment (e.g., CPAT .pop format).
            None means the bus is drawn as a single point at (x, y).
    """

    x: int
    y: int
    points: list[tuple[int, int]] | None = None


@dataclass
class BranchRoute:
    """Routing waypoints for a branch on the diagram.

    Defines the visual path of a transmission line or transformer on the
    diagram, including intermediate bend points.

    Attributes:
        waypoints: Ordered list of (x, y) points from the source bus to the
            destination bus. Includes the start and end points.
    """

    waypoints: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class DiagramLabel:
    """Text label associated with a diagram element.

    Represents a text annotation attached to a bus, branch, generator, or load.
    The label position is defined as an offset from the parent element.

    Note:
        Data class is defined in v0.7.0 but parser support is planned for
        a future release.

    Attributes:
        element_type: Type of the parent element
            ("bus", "branch", "generator", "load").
        element_id: ``id`` of the parent element (unified string identifier,
            e.g. ``"B1"`` for a bus, ``"BR1"`` for a branch).
        text_type: Kind of text displayed
            ("name", "code", "voltage", "result").
        offset_x: Horizontal offset from the parent element (right is positive).
        offset_y: Vertical offset from the parent element (up is positive).
        angle: Counter-clockwise rotation angle in degrees.
        visible: Whether the label is displayed.
    """

    element_type: str
    element_id: str
    text_type: str
    offset_x: int = 0
    offset_y: int = 0
    angle: float = 0.0
    visible: bool = True


@dataclass
class ImportMeta:
    """Metadata for reversing the normalization when exporting back.

    Stored during import from external formats. Used by writers to convert
    psforge schematic coordinates back to the original format's coordinate
    system.

    Attributes:
        source_format: Original file format ("pop", "dss", etc.).
        scale: Scale factor applied during normalization.
        offset_x: X offset applied during normalization.
        offset_y: Y offset applied during normalization.
        y_flipped: Whether the Y axis was inverted during import.
        source_bbox: Original bounding box (x_min, y_min, x_max, y_max).
    """

    source_format: str
    scale: float
    offset_x: float
    offset_y: float
    y_flipped: bool
    source_bbox: tuple[float, float, float, float]


@dataclass
class DiagramData:
    """Container for diagram layout data.

    Holds the graphical positions and routing for all elements in a power
    system diagram. A System can have up to two DiagramData instances:
    one for schematic layout (``diagram_schematic``) and one for geographic
    coordinates (``diagram_geographic``).

    Attributes:
        coordinate_system: Either "schematic" or "geographic".
        crs: Coordinate Reference System identifier.
            Required for geographic (e.g., "EPSG:4326").
            None for schematic.
        normalization_ref: Reference size for the short edge when normalizing
            schematic coordinates. Default is 1920 (Full HD aligned).
            Ignored for geographic.
        bus_positions: Mapping from ``Bus.id`` to its position.
        branch_routes: Mapping from ``Branch.id`` to its route.
        labels: List of text labels. Data class defined but parser support
            is planned for a future release.
        import_meta: Metadata for reversing normalization on export.
            Populated by parsers during import. None for data loaded from
            psforge JSON or created programmatically.
    """

    coordinate_system: str = "schematic"
    crs: str | None = None
    normalization_ref: int = 1920
    bus_positions: dict[str, BusPosition] = field(default_factory=dict)
    branch_routes: dict[str, BranchRoute] = field(default_factory=dict)
    labels: list[DiagramLabel] = field(default_factory=list)
    import_meta: ImportMeta | None = None


def normalize_coordinates(
    raw_points: list[tuple[float, float]],
    normalization_ref: int = 1920,
    padding_ratio: float = 0.05,
    y_flip: bool = False,
) -> tuple[list[tuple[int, int]], ImportMeta]:
    """Normalize raw coordinates to psforge schematic coordinate system.

    Scales coordinates so that the short edge of the bounding box maps to
    ``normalization_ref`` (default 1920). Preserves aspect ratio. Adds
    padding on all sides. Optionally flips the Y axis.

    Args:
        raw_points: List of (x, y) coordinates in the source format.
        normalization_ref: Target size for the short edge (default: 1920).
        padding_ratio: Fraction of normalization_ref reserved as padding
            on each side (default: 0.05 = 5%).
        y_flip: If True, invert the Y axis (for screen-coordinate formats
            where Y increases downward).

    Returns:
        Tuple of (normalized_points, import_meta).
        normalized_points: List of (x, y) integer coordinates.
        import_meta: Metadata for reversing the transformation.

    Raises:
        ValueError: If raw_points is empty or contains fewer than 2 distinct
            points (cannot determine bounding box).
    """
    if not raw_points:
        raise ValueError("raw_points must not be empty")

    xs = [p[0] for p in raw_points]
    ys = [p[1] for p in raw_points]

    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    bbox_width = x_max - x_min
    bbox_height = y_max - y_min

    # Handle degenerate cases (all points on a line or single point)
    if bbox_width == 0 and bbox_height == 0:
        # Single point: place at center of canvas
        padding_px = normalization_ref * padding_ratio
        center = round(normalization_ref / 2)
        normalized = [(center, center)] * len(raw_points)
        return normalized, ImportMeta(
            source_format="",
            scale=1.0,
            offset_x=x_min - center,
            offset_y=y_min - center,
            y_flipped=y_flip,
            source_bbox=(x_min, y_min, x_max, y_max),
        )

    if bbox_width == 0:
        bbox_width = bbox_height  # treat as square
    if bbox_height == 0:
        bbox_height = bbox_width  # treat as square

    short_range = min(bbox_width, bbox_height)
    usable = normalization_ref * (1 - 2 * padding_ratio)
    scale = usable / short_range
    padding_px = normalization_ref * padding_ratio

    normalized = []
    for x, y in raw_points:
        xn = round((x - x_min) * scale + padding_px)
        if y_flip:
            yn = round((y_max - y) * scale + padding_px)
        else:
            yn = round((y - y_min) * scale + padding_px)
        normalized.append((xn, yn))

    meta = ImportMeta(
        source_format="",
        scale=scale,
        offset_x=x_min,
        offset_y=y_min,
        y_flipped=y_flip,
        source_bbox=(x_min, y_min, x_max, y_max),
    )

    return normalized, meta
