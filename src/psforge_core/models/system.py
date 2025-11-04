"""System data model for power system analysis.

This module defines the System class as the central container for all power system components.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

from psforge_core.models.bus import Bus
from psforge_core.models.branch import Branch
from psforge_core.models.generator import Generator


@dataclass
class System:
    """Power system container class.

    Central data structure containing all power system components including
    buses, branches, and generators. Serves as the hub of the Hub & Spoke
    architecture for psforge ecosystem.

    Attributes:
        buses: List of Bus objects representing network nodes
        branches: List of Branch objects representing transmission lines/transformers
        generators: List of Generator objects representing generation units
        base_mva: System base MVA for per-unit conversion (default: 100.0)
        name: System name (optional, default: empty string)

    Note:
        - All per-unit values in components are based on base_mva
        - This class should be treated as immutable for data integrity
        - Modifying buses/branches/generators after construction is discouraged
        - Used as the primary interface between I/O parsers and analysis algorithms
    """

    buses: List[Bus] = field(default_factory=list)
    branches: List[Branch] = field(default_factory=list)
    generators: List[Generator] = field(default_factory=list)
    base_mva: float = 100.0
    name: str = ""

    def num_buses(self) -> int:
        """Return the number of buses in the system.

        Returns:
            Number of buses.
        """
        return len(self.buses)

    def num_branches(self) -> int:
        """Return the number of branches in the system.

        Returns:
            Number of branches.
        """
        return len(self.branches)

    def num_generators(self) -> int:
        """Return the number of generators in the system.

        Returns:
            Number of generators.
        """
        return len(self.generators)
