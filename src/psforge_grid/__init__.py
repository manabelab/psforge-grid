"""psforge-grid: Core data models and I/O for the psforge power system analysis ecosystem.

This package provides:
- Power system data models (System, Bus, Branch, Generator, Load, Shunt)
- PSS/E RAW file parser (v33/v34)
- LLM-friendly output formats and CLI

Example:
    >>> from psforge_grid import System
    >>> system = System.from_raw("ieee14.raw")
    >>> print(system.to_summary())
"""

from psforge_grid.models import (
    Branch,
    Bus,
    BusType,
    ConvergenceStatus,
    Generator,
    LimitsConfig,
    Load,
    LoadingStatus,
    Severity,
    Shunt,
    System,
    SystemHealthStatus,
    VoltageStatus,
)

__version__ = "0.1.1"

__all__ = [
    # Version
    "__version__",
    # Data classes
    "System",
    "Bus",
    "Branch",
    "Generator",
    "Load",
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
