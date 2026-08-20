"""psforge-grid: Core data models and I/O for the psforge power system analysis ecosystem.

This package provides:
- Power system data models (System, Bus, Branch, Generator, Load, Shunt)
- PSS/E RAW file parser (v33/v34)
- LLM-friendly output formats and CLI

Example:
    >>> from psforge_grid import System
    >>> system = System.from_raw("ieee14.raw")  # doctest: +SKIP
    >>> print(f"{system.num_buses} buses, {system.num_branches} branches")
    2 buses, 1 branches
    >>> print(system.to_description())  # doctest: +SKIP
"""

from importlib import metadata as _metadata

from psforge_grid.models import (
    Branch,
    BranchRoute,
    Bus,
    BusPosition,
    BusType,
    ConvergenceStatus,
    DiagramData,
    DiagramLabel,
    Generator,
    GeneratorCost,
    ImportMeta,
    LimitsConfig,
    Load,
    LoadingStatus,
    Modification,
    ScenarioDefinition,
    ScenarioSet,
    Severity,
    Shunt,
    System,
    SystemHealthStatus,
    VoltageStatus,
)

try:
    # Read the version from installed package metadata so pyproject.toml stays
    # the single source of truth. Hardcoding it here let 0.7.0 ship reporting
    # "0.6.0": the bump touched pyproject.toml and nothing else, and nothing
    # cross-checks the two. psforge-flow shipped the same defect for the same
    # reason and fixed it the same way.
    __version__ = _metadata.version("psforge-grid")
except _metadata.PackageNotFoundError:  # pragma: no cover - source tree, not installed
    __version__ = "0.0.0+unknown"

__all__ = [
    # Version
    "__version__",
    # Data classes
    "System",
    "Bus",
    "BusPosition",
    "Branch",
    "BranchRoute",
    "DiagramData",
    "DiagramLabel",
    "Generator",
    "GeneratorCost",
    "ImportMeta",
    "Load",
    "Modification",
    "ScenarioDefinition",
    "ScenarioSet",
    "Shunt",
    # Enums
    "BusType",
    "ConvergenceStatus",
    "LoadingStatus",
    "Severity",
    "SystemHealthStatus",
    "VoltageStatus",
    # Configuration
    "LimitsConfig",
]
