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
from pathlib import Path

from psforge_grid.io.json_writer import FORMAT_NAME
from psforge_grid.io.protocols import IParser
from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.generator_cost import GeneratorCost
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

    # Parse system-level fields
    sys_data = data.get("system", {})

    # Parse components
    buses = [Bus(**b) for b in data.get("buses", [])]
    branches = [Branch(**b) for b in data.get("branches", [])]
    generators = [Generator(**g) for g in data.get("generators", [])]
    loads = [Load(**ld) for ld in data.get("loads", [])]
    shunts = [Shunt(**s) for s in data.get("shunts", [])]
    generator_costs = [GeneratorCost(**gc) for gc in data.get("generator_costs", [])]

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
        description=sys_data.get("description"),
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
        >>> system = parse_json("ieee14.psfg.json")
    """
    return _parse_json_impl(filepath)
