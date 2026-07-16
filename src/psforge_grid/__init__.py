"""psforge-grid: Core data models and I/O for the psforge power system analysis ecosystem.

This package provides:
- Power system data models (System, Bus, Branch, Generator, Load, Shunt)
- PSS/E RAW file parser (v33/v34)
- LLM-friendly output formats and CLI

Example:
    >>> from psforge_grid import System
    >>> system = System.from_raw("ieee14.raw")
    >>> print(f"{system.num_buses} buses, {system.num_branches} branches")
    >>> print(system.to_description())
"""

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

__version__ = "0.8.0"

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
