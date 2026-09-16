"""Parser for psforge-grid JSON format (.psfg.json).

Imports System objects from psforge-grid JSON format files.
Validates the ``"format": "psforge-grid"`` metadata field to prevent
accidental loading of pglib-uc or other JSON files.

Example:
    >>> from psforge_grid.io.json_parser import parse_json
    >>> system = parse_json("ieee14.psfg.json")
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from psforge_grid.io.errors import FileFormatError, MalformedRecordError
from psforge_grid.io.json_writer import FORMAT_NAME
from psforge_grid.io.parse_report import ParseReportBuilder
from psforge_grid.io.protocols import IParser
from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.diagram import (
    BranchRoute,
    BusPosition,
    DiagramData,
    DiagramLabel,
    ImportMeta,
)
from psforge_grid.models.generator import Generator
from psforge_grid.models.generator_cost import GeneratorCost
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt
from psforge_grid.models.system import System


def _parse_json_impl(filepath: str | Path, *, strict: bool = False) -> System:
    """Parse a psforge-grid JSON file into a System object.

    Elements whose fields do not match the current data model are skipped and
    listed in :attr:`~psforge_grid.models.system.System.parse_report` rather
    than raising from the middle of building the system. JSON carries no line
    numbers, so each skip is identified by its position in the array, e.g.
    ``buses[7]``.

    Args:
        filepath: Path to the .psfg.json file
        strict: Raise instead of skipping when any element cannot be read.

    Returns:
        System object containing all parsed data

    Raises:
        FileNotFoundError: If the file does not exist
        FileFormatError: If the file is not valid JSON, or not a psforge-grid
            JSON file
        MalformedRecordError: If ``strict`` is set and an element was skipped
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    builder = ParseReportBuilder(format="json")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FileFormatError(
            f"the file is not valid JSON: {exc.msg}", filepath=str(path), line_no=exc.lineno
        ) from exc
    except UnicodeDecodeError as exc:
        raise FileFormatError(f"the file is not valid UTF-8: {exc}", filepath=str(path)) from exc

    if not isinstance(data, dict):
        raise FileFormatError(
            f"the top level of the file is {type(data).__name__}, expected an object",
            filepath=str(path),
        )

    # Validate format metadata
    metadata = data.get("metadata", {})
    file_format = metadata.get("format", "") if isinstance(metadata, dict) else ""
    if file_format != FORMAT_NAME:
        raise FileFormatError(
            f"Not a psforge-grid JSON file: format={file_format!r}, expected {FORMAT_NAME!r}. "
            "This may be a pglib-uc or other JSON file.",
            filepath=str(path),
        )

    # Parse system-level fields
    sys_data = data.get("system", {})
    if not isinstance(sys_data, dict):
        raise FileFormatError(
            f'"system" is {type(sys_data).__name__}, expected an object', filepath=str(path)
        )

    def build_all(key: str, factory: Callable[..., Any]) -> list[Any]:
        """Build every element of one array, recording the ones that fail."""
        built = []
        for index, item in enumerate(data.get(key, []) or []):
            try:
                built.append(factory(**item))
            except (TypeError, ValueError) as exc:
                builder.skip(0, f"{key}[{index}]", str(exc), repr(item))
            else:
                builder.record_read()
        return built

    buses = build_all("buses", Bus)
    branches = build_all("branches", Branch)
    generators = build_all("generators", Generator)
    loads = build_all("loads", Load)
    shunts = build_all("shunts", Shunt)
    generator_costs = build_all("generator_costs", GeneratorCost)

    # Parse diagram data (no re-normalization)
    diagram_schematic = _parse_diagram_dict(data.get("diagram_schematic"))
    diagram_geographic = _parse_diagram_dict(data.get("diagram_geographic"))

    report = builder.build()

    system = System(
        buses=buses,
        branches=branches,
        generators=generators,
        loads=loads,
        shunts=shunts,
        generator_costs=generator_costs,
        base_mva=sys_data.get("base_mva", 100.0),
        frequency_hz=sys_data.get("frequency_hz"),
        name=sys_data.get("name", ""),
        description=sys_data.get("description"),
        diagram_schematic=diagram_schematic,
        diagram_geographic=diagram_geographic,
        parse_report=report,
    )

    if strict and report.skipped:
        first = report.skipped[0]
        raise MalformedRecordError(
            f"{report.skipped_count} element(s) could not be read; "
            f"first: {first.section}: {first.reason}",
            filepath=str(path),
        )

    return system


def _parse_diagram_dict(d: dict[str, Any] | None) -> DiagramData | None:
    """Parse a diagram dictionary from JSON into DiagramData.

    No re-normalization is performed — coordinates are already in psforge
    schematic or geographic system.
    """
    if d is None:
        return None

    # Bus positions
    bus_positions: dict[int, BusPosition] = {}
    for bus_id_str, pos_data in d.get("bus_positions", {}).items():
        points = None
        if "points" in pos_data:
            points = [tuple(p) for p in pos_data["points"]]
        bus_positions[int(bus_id_str)] = BusPosition(
            x=pos_data["x"],
            y=pos_data["y"],
            points=points,
        )

    # Branch routes
    branch_routes: dict[tuple[int, int, str], BranchRoute] = {}
    for key_str, route_data in d.get("branch_routes", {}).items():
        parts = key_str.rsplit("_", 1)
        from_to = parts[0].rsplit("_", 1)
        from_bus, to_bus, ckt = int(from_to[0]), int(from_to[1]), parts[1]
        waypoints = [tuple(p) for p in route_data.get("waypoints", [])]
        branch_routes[(from_bus, to_bus, ckt)] = BranchRoute(waypoints=waypoints)

    # Labels
    labels: list[DiagramLabel] = []
    for lbl_data in d.get("labels", []):
        element_id = lbl_data["element_id"]
        if isinstance(element_id, list):
            element_id = tuple(element_id)
        labels.append(
            DiagramLabel(
                element_type=lbl_data["element_type"],
                element_id=element_id,
                text_type=lbl_data["text_type"],
                offset_x=lbl_data.get("offset_x", 0),
                offset_y=lbl_data.get("offset_y", 0),
                angle=lbl_data.get("angle", 0.0),
                visible=lbl_data.get("visible", True),
            )
        )

    # ImportMeta
    import_meta = None
    meta_data = d.get("import_meta")
    if meta_data is not None:
        import_meta = ImportMeta(
            source_format=meta_data["source_format"],
            scale=meta_data["scale"],
            offset_x=meta_data["offset_x"],
            offset_y=meta_data["offset_y"],
            y_flipped=meta_data["y_flipped"],
            source_bbox=tuple(meta_data["source_bbox"]),
        )

    return DiagramData(
        coordinate_system=d.get("coordinate_system", "schematic"),
        crs=d.get("crs"),
        normalization_ref=d.get("normalization_ref", 1920),
        bus_positions=bus_positions,
        branch_routes=branch_routes,
        labels=labels,
        import_meta=import_meta,
    )


class JsonParser(IParser):
    """Parser for psforge-grid JSON format.

    Parses ``.psfg.json`` files into System objects.
    Validates format metadata to prevent loading non-psforge JSON files.

    Example:
        >>> parser = JsonParser()
        >>> system = parser.parse("ieee14.psfg.json")
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return ["psfg.json", "json"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "psforge-grid JSON"

    def parse(self, filepath: str | Path, *, strict: bool = False) -> System:
        """Parse a psforge-grid JSON file.

        Args:
            filepath: Path to the .psfg.json file

        Returns:
            System object containing all parsed data

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file is not a valid psforge-grid JSON file
        """
        return _parse_json_impl(filepath, strict=strict)


def parse_json(filepath: str | Path, *, strict: bool = False) -> System:
    """Parse a psforge-grid JSON file.

    Convenience function wrapping JsonParser.

    Args:
        filepath: Path to the .psfg.json file

    Returns:
        System object containing all parsed data

    Example:
        >>> system = parse_json("ieee14.psfg.json")
    """
    return _parse_json_impl(filepath, strict=strict)
