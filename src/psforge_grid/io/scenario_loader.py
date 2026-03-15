"""Scenario loader for base case + modifications pattern.

Loads a base case from a psforge-grid JSON file and applies differential
modifications to generate multiple System variants with minimal data.

Scenario File Format (.psfg.json):
    {
        "format": "psforge-grid-scenario",
        "version": "1.0",
        "base_case": "ieee14.psfg.json",
        "scenarios": [
            {
                "name": "N-1_Line_1-2",
                "description": "Line 1-2 outage",
                "modifications": [
                    {
                        "target": "branches",
                        "match": {"from_bus": 1, "to_bus": 2, "circuit_id": "1"},
                        "set": {"status": 0}
                    }
                ]
            }
        ]
    }

Supported modification targets: buses, branches, generators, loads, shunts

Example:
    >>> from psforge_grid.io.scenario_loader import load_scenarios
    >>> scenarios = load_scenarios("contingencies.psfg.json")
    >>> for name, system in scenarios.items():
    ...     print(f"{name}: {len(system.branches)} branches")
"""

from __future__ import annotations

import copy
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from psforge_grid.models.system import System

SCENARIO_FORMAT_NAME = "psforge-grid-scenario"


def _match_element(element: Any, match_criteria: dict[str, Any]) -> bool:
    """Check if a dataclass element matches all given criteria.

    Args:
        element: Dataclass instance (Bus, Branch, Generator, etc.)
        match_criteria: Dictionary of field_name → expected_value

    Returns:
        True if all criteria match
    """
    for key, value in match_criteria.items():
        if not hasattr(element, key):
            return False
        if getattr(element, key) != value:
            return False
    return True


def _apply_modifications(
    system: System,
    modifications: list[dict[str, Any]],
) -> System:
    """Apply a list of modifications to a System (deep copy).

    Args:
        system: Base system to modify (not mutated)
        modifications: List of modification dicts with target, match, set

    Returns:
        New System with modifications applied

    Raises:
        ValueError: If target is invalid or no elements match
    """
    modified = copy.deepcopy(system)

    target_map: dict[str, list[Any]] = {
        "buses": modified.buses,
        "branches": modified.branches,
        "generators": modified.generators,
        "loads": modified.loads,
        "shunts": modified.shunts,
    }

    for mod in modifications:
        target = mod.get("target")
        if target not in target_map:
            valid = list(target_map.keys())
            raise ValueError(f"Invalid modification target: '{target}'. Valid targets: {valid}")

        match_criteria = mod.get("match", {})
        set_values = mod.get("set", {})

        if not set_values:
            continue

        elements = target_map[target]
        matched = False

        for element in elements:
            if _match_element(element, match_criteria):
                matched = True
                # Validate field names
                valid_fields = {f.name for f in fields(element)}
                for key, value in set_values.items():
                    if key not in valid_fields:
                        raise ValueError(
                            f"Invalid field '{key}' for {target}. "
                            f"Valid fields: {sorted(valid_fields)}"
                        )
                    setattr(element, key, value)

        if not matched and match_criteria:
            raise ValueError(f"No {target} matched criteria: {match_criteria}")

    return modified


def load_scenarios(
    filepath: str | Path,
) -> dict[str, System]:
    """Load scenarios from a psforge-grid scenario file.

    Reads the base case, then applies each scenario's modifications
    to produce independent System objects.

    Args:
        filepath: Path to the scenario .psfg.json file

    Returns:
        Dictionary mapping scenario name to modified System.
        Also includes the key ``"base"`` for the unmodified base case.

    Raises:
        FileNotFoundError: If the scenario or base case file is not found
        ValueError: If the file format is invalid

    Example:
        >>> scenarios = load_scenarios("contingencies.psfg.json")
        >>> base = scenarios["base"]
        >>> n1 = scenarios["N-1_Line_1-2"]
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    # Validate format
    metadata = data.get("metadata", data)
    file_format = metadata.get("format", "")
    if file_format != SCENARIO_FORMAT_NAME:
        raise ValueError(
            f"Not a psforge-grid scenario file: format='{file_format}', "
            f"expected='{SCENARIO_FORMAT_NAME}'"
        )

    # Resolve base case path (relative to scenario file)
    base_case_ref = data.get("base_case")
    if not base_case_ref:
        raise ValueError("Scenario file must specify 'base_case' field")

    base_case_path = path.parent / base_case_ref
    if not base_case_path.exists():
        raise FileNotFoundError(
            f"Base case file not found: {base_case_path} (referenced from {path})"
        )

    # Load base case
    from psforge_grid.io.json_parser import parse_json

    base_system = parse_json(base_case_path)

    # Build scenarios
    result: dict[str, System] = {"base": base_system}

    for scenario_data in data.get("scenarios", []):
        name = scenario_data.get("name", f"scenario_{len(result)}")
        modifications = scenario_data.get("modifications", [])
        result[name] = _apply_modifications(base_system, modifications)

    return result


def write_scenario(
    filepath: str | Path,
    base_case: str,
    scenarios: list[dict[str, Any]],
    *,
    indent: int = 2,
) -> None:
    """Write a scenario definition file.

    Args:
        filepath: Output file path
        base_case: Relative path to the base case .psfg.json file
        scenarios: List of scenario definitions, each containing:
            - name: Scenario name
            - description: Optional description
            - modifications: List of {target, match, set} dicts
        indent: JSON indentation level (default: 2)

    Example:
        >>> write_scenario(
        ...     "contingencies.psfg.json",
        ...     base_case="ieee14.psfg.json",
        ...     scenarios=[
        ...         {
        ...             "name": "N-1_Line_1-2",
        ...             "description": "Line 1-2 outage",
        ...             "modifications": [
        ...                 {
        ...                     "target": "branches",
        ...                     "match": {"from_bus": 1, "to_bus": 2},
        ...                     "set": {"status": 0},
        ...                 }
        ...             ],
        ...         }
        ...     ],
        ... )
    """
    data = {
        "metadata": {
            "format": SCENARIO_FORMAT_NAME,
            "version": "1.0",
        },
        "base_case": base_case,
        "scenarios": scenarios,
    }

    path = Path(filepath)
    path.write_text(
        json.dumps(data, indent=indent, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
