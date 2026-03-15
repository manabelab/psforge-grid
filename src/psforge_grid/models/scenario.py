"""Scenario data models for base case + modifications pattern.

This module defines typed dataclasses for representing power system scenarios:
modifications to a base case that produce variant System objects.

The scenario file format (.psfg.json) stores a reference to a base case file
and a list of named scenarios, each with targeted modifications to specific
power system elements (buses, branches, generators, loads, shunts).

Example:
    >>> from psforge_grid.models.scenario import ScenarioSet
    >>> scenario_set = ScenarioSet.from_json("contingencies.psfg.json")
    >>> systems = scenario_set.resolve()
    >>> for name, system in systems.items():
    ...     print(f"{name}: {len(system.branches)} branches")
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar

from psforge_grid.models.system import System

SCENARIO_FORMAT_NAME = "psforge-grid-scenario"
SCENARIO_FORMAT_VERSION = "1.0"


@dataclass
class Modification:
    """A single modification to apply to power system elements.

    Identifies elements by matching criteria, then applies new values
    to the matched elements.

    Attributes:
        target: Element collection to modify.
            One of: "buses", "branches", "generators", "loads", "shunts".
        match: Criteria to identify target elements.
            Dictionary of field_name -> expected_value pairs.
            All criteria must match (AND logic).
        set_values: Values to apply to matched elements.
            Dictionary of field_name -> new_value pairs.
            In JSON format, this field is serialized as "set".
        description: Optional human-readable description of this modification.

    Example:
        >>> mod = Modification(
        ...     target="branches",
        ...     match={"from_bus": 1, "to_bus": 5},
        ...     set_values={"status": 0},
        ...     description="Take line 1-5 out of service",
        ... )
    """

    target: str
    match: dict[str, Any]
    set_values: dict[str, Any]
    description: str | None = None

    VALID_TARGETS: ClassVar[list[str]] = [
        "buses",
        "branches",
        "generators",
        "loads",
        "shunts",
    ]

    def __post_init__(self) -> None:
        """Validate that target is a supported element collection."""
        if self.target not in self.VALID_TARGETS:
            raise ValueError(
                f"Invalid modification target: '{self.target}'. Valid targets: {self.VALID_TARGETS}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON output.

        Maps ``set_values`` to ``"set"`` key for JSON format compatibility.

        Returns:
            Dictionary representation with "set" key instead of "set_values".
        """
        result: dict[str, Any] = {
            "target": self.target,
            "match": self.match,
            "set": self.set_values,
        }
        if self.description is not None:
            result["description"] = self.description
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Modification:
        """Create a Modification from a dictionary.

        Maps ``"set"`` key from JSON to ``set_values`` parameter.

        Args:
            data: Dictionary with "target", "match", "set" keys.

        Returns:
            New Modification instance.
        """
        return cls(
            target=data["target"],
            match=data.get("match", {}),
            set_values=data.get("set", {}),
            description=data.get("description"),
        )

    def to_description(self) -> str:
        """Generate a human/LLM-readable description of this modification.

        Returns:
            Single-line description string.
        """
        if self.description:
            return self.description

        match_str = ", ".join(f"{k}={v}" for k, v in self.match.items())
        set_str = ", ".join(f"{k}={v}" for k, v in self.set_values.items())
        return f"Modify {self.target} where [{match_str}]: set [{set_str}]"


@dataclass
class ScenarioDefinition:
    """A named scenario with a list of modifications.

    Represents one variant of the base case, identified by name
    and described by a sequence of modifications.

    Attributes:
        name: Unique name for this scenario (used as dictionary key).
        modifications: Ordered list of modifications to apply.
        description: Optional human-readable description of the scenario.

    Example:
        >>> scenario = ScenarioDefinition(
        ...     name="N-1_Line_1-5",
        ...     description="Line 1-5 outage contingency",
        ...     modifications=[
        ...         Modification(target="branches", match={"from_bus": 1, "to_bus": 5},
        ...                      set_values={"status": 0}),
        ...     ],
        ... )
    """

    name: str
    modifications: list[Modification] = field(default_factory=list)
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON output.

        Returns:
            Dictionary representation compatible with scenario file format.
        """
        result: dict[str, Any] = {"name": self.name}
        if self.description is not None:
            result["description"] = self.description
        result["modifications"] = [m.to_dict() for m in self.modifications]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioDefinition:
        """Create a ScenarioDefinition from a dictionary.

        Args:
            data: Dictionary with "name", optional "description",
                  and "modifications" keys.

        Returns:
            New ScenarioDefinition instance.
        """
        return cls(
            name=data["name"],
            description=data.get("description"),
            modifications=[Modification.from_dict(m) for m in data.get("modifications", [])],
        )

    def to_description(self) -> str:
        """Generate a human/LLM-readable description.

        Returns:
            Multi-line description string.
        """
        parts = [f"Scenario: {self.name}"]
        if self.description:
            parts.append(f"  {self.description}")
        parts.append(f"  {len(self.modifications)} modification(s)")
        for i, mod in enumerate(self.modifications, 1):
            parts.append(f"    {i}. {mod.to_description()}")
        return "\n".join(parts)


@dataclass
class ScenarioSet:
    """A collection of scenarios built from a common base case.

    ScenarioSet holds a base System and a list of scenario definitions.
    Calling ``resolve()`` produces independent System objects for each
    scenario by deep-copying the base and applying modifications.

    Attributes:
        base: The base case System that all scenarios modify.
        scenarios: List of scenario definitions.
        base_case_path: Original file path of the base case (for JSON round-trip).
        name: Optional name for this scenario set.
        description: Optional description.

    Example:
        >>> scenario_set = ScenarioSet.from_json("contingencies.psfg.json")
        >>> systems = scenario_set.resolve()
        >>> base = systems["base"]
        >>> n1 = systems["N-1_Line_1-5"]
    """

    base: System
    scenarios: list[ScenarioDefinition] = field(default_factory=list)
    base_case_path: str | None = None
    name: str = ""
    description: str | None = None

    @property
    def scenario_names(self) -> list[str]:
        """List of scenario names (excluding base case).

        Returns:
            List of scenario name strings.
        """
        return [s.name for s in self.scenarios]

    @property
    def num_scenarios(self) -> int:
        """Number of scenarios (excluding base case).

        Returns:
            Count of scenario definitions.
        """
        return len(self.scenarios)

    def resolve(self) -> dict[str, System]:
        """Resolve all scenarios into independent System objects.

        Creates a deep copy of the base System for each scenario and
        applies the scenario's modifications. The result includes a
        ``"base"`` key for the unmodified base case.

        Returns:
            Dictionary mapping scenario name to modified System.
            Includes ``"base"`` for the unmodified base case.

        Raises:
            ValueError: If a modification has an invalid target or field,
                or if no elements match the criteria.
        """
        result: dict[str, System] = {"base": copy.deepcopy(self.base)}

        for scenario_def in self.scenarios:
            modified = copy.deepcopy(self.base)
            _apply_modifications(modified, scenario_def.modifications)
            result[scenario_def.name] = modified

        return result

    def to_description(self) -> str:
        """Generate a human/LLM-readable description.

        Returns:
            Multi-line description of this scenario set.
        """
        parts = []
        if self.name:
            parts.append(f"ScenarioSet: {self.name}")
        if self.description:
            parts.append(f"  {self.description}")
        parts.append(f"Base case: {len(self.base.buses)} buses, {len(self.base.branches)} branches")
        if self.base_case_path:
            parts.append(f"Base file: {self.base_case_path}")
        parts.append(f"{self.num_scenarios} scenario(s):")
        for s in self.scenarios:
            desc = s.description or f"{len(s.modifications)} modification(s)"
            parts.append(f"  - {s.name}: {desc}")
        return "\n".join(parts)

    @classmethod
    def from_json(cls, filepath: str | Path) -> ScenarioSet:
        """Load a ScenarioSet from a psforge-grid scenario JSON file.

        Reads the scenario file, loads the referenced base case, and
        constructs a fully populated ScenarioSet.

        Args:
            filepath: Path to the scenario .psfg.json file.

        Returns:
            ScenarioSet with base System and scenario definitions.

        Raises:
            FileNotFoundError: If the scenario or base case file is not found.
            ValueError: If the file format is invalid.

        Example:
            >>> scenario_set = ScenarioSet.from_json("contingencies.psfg.json")
            >>> print(scenario_set.num_scenarios)
            3
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

        # Parse scenario definitions
        scenario_defs = [ScenarioDefinition.from_dict(s) for s in data.get("scenarios", [])]

        return cls(
            base=base_system,
            scenarios=scenario_defs,
            base_case_path=base_case_ref,
        )

    def to_json(
        self,
        filepath: str | Path,
        *,
        base_case_path: str | None = None,
        indent: int = 2,
    ) -> None:
        """Write this ScenarioSet to a scenario JSON file.

        Writes the scenario definitions (not the base System data).
        The base case is referenced by path.

        Args:
            filepath: Output file path.
            base_case_path: Path to write as base_case reference.
                If None, uses ``self.base_case_path``.
                At least one must be set.
            indent: JSON indentation level (default: 2).

        Raises:
            ValueError: If no base_case_path is available.

        Example:
            >>> scenario_set.to_json("output.psfg.json", base_case_path="ieee14.psfg.json")
        """
        ref = base_case_path or self.base_case_path
        if not ref:
            raise ValueError(
                "base_case_path must be provided either as argument "
                "or set on the ScenarioSet instance"
            )

        data = {
            "metadata": {
                "format": SCENARIO_FORMAT_NAME,
                "version": SCENARIO_FORMAT_VERSION,
            },
            "base_case": ref,
            "scenarios": [s.to_dict() for s in self.scenarios],
        }

        path = Path(filepath)
        path.write_text(
            json.dumps(data, indent=indent, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _match_element(element: Any, match_criteria: dict[str, Any]) -> bool:
    """Check if a dataclass element matches all given criteria.

    Args:
        element: Dataclass instance (Bus, Branch, Generator, etc.)
        match_criteria: Dictionary of field_name -> expected_value.

    Returns:
        True if all criteria match.
    """
    for key, value in match_criteria.items():
        if not hasattr(element, key):
            return False
        if getattr(element, key) != value:
            return False
    return True


def _apply_modifications(
    system: System,
    modifications: list[Modification],
) -> None:
    """Apply a list of Modification objects to a System in-place.

    Args:
        system: System to modify (mutated in place).
        modifications: List of Modification objects to apply.

    Raises:
        ValueError: If target is invalid or no elements match.
    """
    target_map: dict[str, list[Any]] = {
        "buses": system.buses,
        "branches": system.branches,
        "generators": system.generators,
        "loads": system.loads,
        "shunts": system.shunts,
    }

    for mod in modifications:
        elements = target_map[mod.target]
        matched = False

        for element in elements:
            if _match_element(element, mod.match):
                matched = True
                valid_fields = {f.name for f in fields(element)}
                for key, value in mod.set_values.items():
                    if key not in valid_fields:
                        raise ValueError(
                            f"Invalid field '{key}' for {mod.target}. "
                            f"Valid fields: {sorted(valid_fields)}"
                        )
                    setattr(element, key, value)

        if not matched and mod.match:
            raise ValueError(f"No {mod.target} matched criteria: {mod.match}")
