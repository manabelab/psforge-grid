"""Writer for psforge-grid JSON format (.psfg.json).

Exports System objects to a human/LLM-friendly JSON format with:
- Explicit metadata (format, version, source)
- Snake_case field names with unit suffixes (_pu, _mw, etc.)
- None fields omitted by default for compact output
- Indented output for readability

The format is distinct from pglib-uc and other power system JSON formats
through its ``"format": "psforge-grid"`` metadata field and ``.psfg.json``
file extension.

Example:
    >>> from psforge_grid.io.json_writer import write_json
    >>> write_json(system, tmp_path / "demo.psfg.json")
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psforge_grid.io.protocols import IWriter
from psforge_grid.models.system import System

# Format metadata constants
FORMAT_NAME = "psforge-grid"
FORMAT_VERSION = "2.0"


def _dataclass_to_dict(obj: Any, *, omit_none: bool = True) -> dict[str, Any]:
    """Convert a dataclass instance to a dict, optionally omitting None values.

    Empty ``tags`` lists are omitted alongside None values: they carry no
    information and would add a line to every element (compact
    representation, LLM affinity principle #2).

    Args:
        obj: Dataclass instance to convert
        omit_none: If True, omit fields with None values (default: True)

    Returns:
        Dictionary representation of the dataclass
    """
    result: dict[str, Any] = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if omit_none and value is None:
            continue
        if omit_none and f.name == "tags" and value == []:
            continue
        result[f.name] = value
    return result


def _diagram_to_dict(diagram: Any) -> dict[str, Any]:
    """Convert a DiagramData to a JSON-serializable dictionary."""
    from psforge_grid.models.diagram import DiagramData

    if not isinstance(diagram, DiagramData):
        return {}

    result: dict[str, Any] = {
        "coordinate_system": diagram.coordinate_system,
        "normalization_ref": diagram.normalization_ref,
    }
    if diagram.crs is not None:
        result["crs"] = diagram.crs

    # Bus positions: {Bus.id: {x, y, points?}}
    if diagram.bus_positions:
        bp_dict: dict[str, Any] = {}
        for bus_id, pos in diagram.bus_positions.items():
            entry: dict[str, Any] = {"x": pos.x, "y": pos.y}
            if pos.points is not None:
                entry["points"] = [list(p) for p in pos.points]
            bp_dict[bus_id] = entry
        result["bus_positions"] = bp_dict

    # Branch routes: {Branch.id: {waypoints: [[x,y], ...]}}
    if diagram.branch_routes:
        br_dict: dict[str, Any] = {}
        for branch_id, route in diagram.branch_routes.items():
            br_dict[branch_id] = {"waypoints": [list(p) for p in route.waypoints]}
        result["branch_routes"] = br_dict

    # Labels (stored as list of dicts)
    if diagram.labels:
        result["labels"] = [
            {
                "element_type": lbl.element_type,
                "element_id": lbl.element_id,
                "text_type": lbl.text_type,
                "offset_x": lbl.offset_x,
                "offset_y": lbl.offset_y,
                "angle": lbl.angle,
                "visible": lbl.visible,
            }
            for lbl in diagram.labels
        ]

    # ImportMeta (stored for round-trip fidelity)
    if diagram.import_meta is not None:
        m = diagram.import_meta
        result["import_meta"] = {
            "source_format": m.source_format,
            "scale": m.scale,
            "offset_x": m.offset_x,
            "offset_y": m.offset_y,
            "y_flipped": m.y_flipped,
            "source_bbox": list(m.source_bbox),
        }

    return result


def _system_to_dict(
    system: System,
    *,
    omit_none: bool = True,
    source_file: str | None = None,
) -> dict[str, Any]:
    """Convert a System to a JSON-serializable dictionary.

    Args:
        system: Power system data to serialize
        omit_none: If True, omit fields with None values
        source_file: Optional source file path for metadata

    Returns:
        JSON-serializable dictionary
    """
    metadata: dict[str, Any] = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    if source_file:
        metadata["source_file"] = source_file

    data: dict[str, Any] = {
        "metadata": metadata,
        "system": {
            "name": system.name,
            "base_mva": system.base_mva,
        },
        "buses": [_dataclass_to_dict(b, omit_none=omit_none) for b in system.buses],
        "branches": [_dataclass_to_dict(b, omit_none=omit_none) for b in system.branches],
        "generators": [_dataclass_to_dict(g, omit_none=omit_none) for g in system.generators],
        "loads": [_dataclass_to_dict(ld, omit_none=omit_none) for ld in system.loads],
        "shunts": [_dataclass_to_dict(s, omit_none=omit_none) for s in system.shunts],
    }

    # Optional fields on System
    if system.frequency_hz is not None:
        data["system"]["frequency_hz"] = system.frequency_hz
    if system.description is not None:
        data["system"]["description"] = system.description
    if system.id is not None:
        data["system"]["id"] = system.id
    if system.order is not None:
        data["system"]["order"] = system.order
    if system.tags:
        data["system"]["tags"] = system.tags
    if system.case_time is not None:
        data["system"]["case_time"] = system.case_time

    # Generator costs (only if present)
    if system.generator_costs:
        data["generator_costs"] = [
            _dataclass_to_dict(gc, omit_none=omit_none) for gc in system.generator_costs
        ]

    # Diagram data (only if present)
    if system.diagram_schematic is not None:
        data["diagram_schematic"] = _diagram_to_dict(system.diagram_schematic)
    if system.diagram_geographic is not None:
        data["diagram_geographic"] = _diagram_to_dict(system.diagram_geographic)

    return data


class JsonWriter(IWriter):
    """Writer for psforge-grid JSON format.

    Exports System objects to ``.psfg.json`` files with metadata,
    compact representation (None fields omitted), and indented output.

    Args:
        omit_none: If True, omit fields with None values (default: True)
        indent: JSON indentation level (default: 2)

    Example:
        >>> writer = JsonWriter()
        >>> writer.write(system, tmp_path / "output.psfg.json")
        >>> # Include all fields (with null values)
        >>> writer = JsonWriter(omit_none=False)
        >>> writer.write(system, tmp_path / "output.psfg.json")
    """

    def __init__(
        self,
        *,
        omit_none: bool = True,
        indent: int = 2,
    ) -> None:
        self._omit_none = omit_none
        self._indent = indent

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return ["psfg.json", "json"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "psforge-grid JSON"

    def write(self, system: System, filepath: str | Path) -> None:
        """Write a System to a psforge-grid JSON file.

        Args:
            system: Power system data to export
            filepath: Output file path (recommended: .psfg.json)
        """
        data = _system_to_dict(system, omit_none=self._omit_none)
        path = Path(filepath)
        path.write_text(
            json.dumps(data, indent=self._indent, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def write_json(
    system: System,
    filepath: str | Path,
    *,
    omit_none: bool = True,
    indent: int = 2,
) -> None:
    """Write a System to a psforge-grid JSON file.

    Convenience function wrapping JsonWriter.

    Args:
        system: Power system data to export
        filepath: Output file path (recommended: .psfg.json)
        omit_none: If True, omit fields with None values (default: True)
        indent: JSON indentation level (default: 2)

    Example:
        >>> write_json(system, tmp_path / "ieee14.psfg.json")
    """
    writer = JsonWriter(omit_none=omit_none, indent=indent)
    writer.write(system, filepath)
