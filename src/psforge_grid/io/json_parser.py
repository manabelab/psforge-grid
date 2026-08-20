"""Parser for psforge-grid JSON format (.psfg.json).

Imports System objects from psforge-grid JSON format files.
Validates the ``"format": "psforge-grid"`` metadata field to prevent
accidental loading of pglib-uc or other JSON files.

Format versions:
    - 2.0 (current): elements carry the unified identity layer
      (``id``/``order``/``name``/``tags``), references are string ids
      (``from_bus_id``, ``bus_id``, ``generator_id``), and diagram data is
      keyed by element id.
    - 1.x (legacy, read-only): elements identified by integer ``bus_id`` and
      composite keys. Loading a 1.x file migrates it in memory: ids are
      generated with the standard deterministic rules (``B1``, ``BR1``,
      ``G1``, ...), the old keys are kept as round-trip data
      (``Bus.number``, ``circuit_id``, ``machine_id``, ...), and writing the
      System back produces a 2.0 file.

Example:
    >>> from psforge_grid.io.json_parser import parse_json
    >>> system = parse_json("ieee14.psfg.json")  # doctest: +SKIP
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psforge_grid.io.json_writer import FORMAT_NAME
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
from psforge_grid.models.identity import make_unique, sanitize_id
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt
from psforge_grid.models.system import System


def _parse_json_impl(filepath: str | Path) -> System:
    """Parse a psforge-grid JSON file into a System object.

    Args:
        filepath: Path to the .psfg.json file

    Returns:
        System object containing all parsed data

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file is not a valid psforge-grid JSON file
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    # Validate format metadata
    metadata = data.get("metadata", {})
    file_format = metadata.get("format", "")
    if file_format != FORMAT_NAME:
        raise ValueError(
            f"Not a psforge-grid JSON file: format='{file_format}', "
            f"expected='{FORMAT_NAME}'. "
            f"This may be a pglib-uc or other JSON file."
        )

    version = str(metadata.get("version", "1.0"))
    if version.startswith("1"):
        data = _migrate_v1(data)

    # Parse system-level fields
    sys_data = data.get("system", {})

    # Parse components
    buses = [Bus(**b) for b in data.get("buses", [])]
    branches = [Branch(**b) for b in data.get("branches", [])]
    generators = [Generator(**g) for g in data.get("generators", [])]
    loads = [Load(**ld) for ld in data.get("loads", [])]
    shunts = [Shunt(**s) for s in data.get("shunts", [])]
    generator_costs = [GeneratorCost(**gc) for gc in data.get("generator_costs", [])]

    # Parse diagram data (no re-normalization)
    diagram_schematic = _parse_diagram_dict(data.get("diagram_schematic"))
    diagram_geographic = _parse_diagram_dict(data.get("diagram_geographic"))

    return System(
        buses=buses,
        branches=branches,
        generators=generators,
        loads=loads,
        shunts=shunts,
        generator_costs=generator_costs,
        base_mva=sys_data.get("base_mva", 100.0),
        frequency_hz=sys_data.get("frequency_hz"),
        name=sys_data.get("name", ""),
        id=sys_data.get("id"),
        order=sys_data.get("order"),
        tags=sys_data.get("tags", []),
        case_time=sys_data.get("case_time"),
        description=sys_data.get("description"),
        diagram_schematic=diagram_schematic,
        diagram_geographic=diagram_geographic,
    )


def _migrate_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate a version 1.x document to the 2.0 element schema, in place.

    v1 identified elements by integer ``bus_id`` and composite keys. This
    generates unified ids with the standard deterministic rules and demotes
    the old keys to round-trip data. The mapping is:

    - bus: ``bus_id`` -> ``id="B{n}"`` + ``number=n``
    - branch/generator/load/shunt/generator_cost: type prefix + 1-based
      file position (``BR1``, ``G1``, ``LD1``, ``SH1``, ``GC1``); the old
      keys become ``circuit_id``/``machine_id``/``load_id``/``shunt_id``
      and ``gen_index`` (a list position) becomes ``generator_id``
    - diagram keys: bus numbers / "f_t_ckt" strings -> element ids

    Every id goes through make_unique against all ids generated so far, so
    even a v1 file with duplicate keys loads into a valid v2 System.
    """
    used: set[str] = set()

    def take(candidate: str) -> str:
        new = make_unique(candidate, used)
        used.add(new)
        return new

    def clean(source_id: str | None) -> str:
        # v1 files serialized RAW-era identifier columns as-is, including
        # their fixed-width padding ('1 '). Strip it so the stored
        # round-trip key matches what the RAW parser produces today.
        return (source_id or "").strip() or "1"

    bus_id_map: dict[int, str] = {}  # v1 bus number -> v2 Bus.id
    for i, b in enumerate(data.get("buses", [])):
        number = b.pop("bus_id")
        b["id"] = take(f"B{number}")
        b["number"] = number
        b.setdefault("order", float(i + 1))
        bus_id_map[number] = b["id"]

    def bus_ref(number: int) -> str:
        # A dangling v1 reference has no bus to map to; keep it visibly
        # broken ("B{n}") so System.validate() reports it instead of KeyError.
        return bus_id_map.get(number, f"B{number}")

    branch_key_map: dict[str, str] = {}  # v1 "f_t_ckt" -> v2 Branch.id
    for i, br in enumerate(data.get("branches", [])):
        from_num = br.pop("from_bus")
        to_num = br.pop("to_bus")
        raw_ckt = br.get("circuit_id", "1")
        br["circuit_id"] = clean(raw_ckt)
        br["id"] = take(f"BR{i + 1}")
        br["from_bus_id"] = bus_ref(from_num)
        br["to_bus_id"] = bus_ref(to_num)
        br.setdefault("order", float(i + 1))
        branch_key_map[f"{from_num}_{to_num}_{raw_ckt}"] = br["id"]

    for i, g in enumerate(data.get("generators", [])):
        bus_num = g.pop("bus_id")
        machine_id = clean(g.pop("gen_id", "1"))
        g["id"] = take(f"G{i + 1}")
        g["bus_id"] = bus_ref(bus_num)
        g["machine_id"] = machine_id
        g.setdefault("order", float(i + 1))

    for i, ld in enumerate(data.get("loads", [])):
        bus_num = ld.pop("bus_id")
        ld["load_id"] = clean(ld.get("load_id", "1"))
        ld["id"] = take(f"LD{i + 1}")
        ld["bus_id"] = bus_ref(bus_num)
        ld.setdefault("order", float(i + 1))

    for i, s in enumerate(data.get("shunts", [])):
        bus_num = s.pop("bus_id")
        s["shunt_id"] = clean(s.get("shunt_id", "1"))
        s["id"] = take(f"SH{i + 1}")
        s["bus_id"] = bus_ref(bus_num)
        s.setdefault("order", float(i + 1))

    generators = data.get("generators", [])
    for i, gc in enumerate(data.get("generator_costs", [])):
        gen_index = gc.pop("gen_index")
        if 0 <= gen_index < len(generators):
            gc["generator_id"] = generators[gen_index]["id"]
        else:
            raise ValueError(
                f"generator_costs[{i}]: gen_index {gen_index} is out of range "
                f"({len(generators)} generators in file)"
            )
        gc["id"] = take(f"GC{i + 1}")
        gc.setdefault("order", float(i + 1))

    for key in ("diagram_schematic", "diagram_geographic"):
        diagram = data.get(key)
        if diagram is None:
            continue
        if "bus_positions" in diagram:
            diagram["bus_positions"] = {
                bus_ref(int(k)): v for k, v in diagram["bus_positions"].items()
            }
        if "branch_routes" in diagram:
            diagram["branch_routes"] = {
                branch_key_map.get(k, k): v for k, v in diagram["branch_routes"].items()
            }
        for lbl in diagram.get("labels", []):
            eid = lbl.get("element_id")
            # Best effort: v1 stored a bus number (int) or a branch key
            # tuple. Label parser support never shipped, so this only has
            # to produce a valid string, not recover exact semantics.
            if isinstance(eid, list):
                key = f"{eid[0]}_{eid[1]}_{eid[2]}"
                lbl["element_id"] = branch_key_map.get(key, sanitize_id(f"BR_{key}"))
            elif isinstance(eid, int):
                lbl["element_id"] = bus_ref(eid)

    return data


def _parse_diagram_dict(d: dict[str, Any] | None) -> DiagramData | None:
    """Parse a diagram dictionary from JSON into DiagramData.

    No re-normalization is performed — coordinates are already in psforge
    schematic or geographic system.
    """
    if d is None:
        return None

    # Bus positions (keyed by Bus.id)
    bus_positions: dict[str, BusPosition] = {}
    for bus_id, pos_data in d.get("bus_positions", {}).items():
        points = None
        if "points" in pos_data:
            points = [tuple(p) for p in pos_data["points"]]
        bus_positions[bus_id] = BusPosition(
            x=pos_data["x"],
            y=pos_data["y"],
            points=points,
        )

    # Branch routes (keyed by Branch.id)
    branch_routes: dict[str, BranchRoute] = {}
    for branch_id, route_data in d.get("branch_routes", {}).items():
        waypoints = [tuple(p) for p in route_data.get("waypoints", [])]
        branch_routes[branch_id] = BranchRoute(waypoints=waypoints)

    # Labels
    labels: list[DiagramLabel] = []
    for lbl_data in d.get("labels", []):
        labels.append(
            DiagramLabel(
                element_type=lbl_data["element_type"],
                element_id=lbl_data["element_id"],
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
    Reads both 2.0 (current) and 1.x (legacy) documents; 1.x elements are
    migrated to the unified identity schema on load.

    Example:
        >>> parser = JsonParser()
        >>> system = parser.parse("ieee14.psfg.json")  # doctest: +SKIP
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return ["psfg.json", "json"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "psforge-grid JSON"

    def parse(self, filepath: str | Path) -> System:
        """Parse a psforge-grid JSON file.

        Args:
            filepath: Path to the .psfg.json file

        Returns:
            System object containing all parsed data

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file is not a valid psforge-grid JSON file
        """
        return _parse_json_impl(filepath)


def parse_json(filepath: str | Path) -> System:
    """Parse a psforge-grid JSON file.

    Convenience function wrapping JsonParser.

    Args:
        filepath: Path to the .psfg.json file

    Returns:
        System object containing all parsed data

    Example:
        >>> system = parse_json("ieee14.psfg.json")  # doctest: +SKIP
    """
    return _parse_json_impl(filepath)
