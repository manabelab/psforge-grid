"""System data model for power system analysis.

This module defines the System class as the central container for all power system components.

Factory Methods:
    The System class provides factory methods for creating instances from files:
    - from_raw(): Create from PSS/E RAW file
    - from_file(): Create from any supported format (auto-detect)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt


@dataclass
class System:
    """Power system container class.

    Central data structure containing all power system components including
    buses, branches, generators, loads, and shunts. Serves as the hub of the
    Hub & Spoke architecture for psforge ecosystem.

    Attributes:
        buses: List of Bus objects representing network nodes
        branches: List of Branch objects representing transmission lines/transformers
        generators: List of Generator objects representing generation units
        loads: List of Load objects representing electrical consumption
        shunts: List of Shunt objects representing capacitors/reactors
        base_mva: System base MVA for per-unit conversion (default: 100.0)
        name: System name (optional, default: empty string)
        description: Free-text description providing context about the system.
            For LLM-friendly output.

    Note:
        - All per-unit values in components are based on base_mva
        - This class serves as the primary interface between I/O parsers and analysis algorithms
        - Use helper methods to query components by bus ID

    Example:
        >>> from psforge_grid.models import System, Bus, Branch, Generator, Load
        >>> system = System(
        ...     buses=[Bus(1, bus_type=3), Bus(2, bus_type=1)],
        ...     branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)],
        ...     generators=[Generator(bus_id=1, p_gen=1.0)],
        ...     loads=[Load(bus_id=2, p_load=0.8, q_load=0.2)]
        ... )
    """

    buses: list[Bus] = field(default_factory=list)
    branches: list[Branch] = field(default_factory=list)
    generators: list[Generator] = field(default_factory=list)
    loads: list[Load] = field(default_factory=list)
    shunts: list[Shunt] = field(default_factory=list)
    base_mva: float = 100.0
    name: str = ""
    description: str | None = None

    # =========================================================================
    # Factory methods
    # =========================================================================

    @classmethod
    def from_raw(cls, filepath: str | Path) -> System:
        """Create a System from a PSS/E RAW file.

        Factory method for creating System instances from PSS/E RAW format
        files (v33/v34). This is the recommended way to load power system
        data from RAW files.

        Args:
            filepath: Path to the .raw file

        Returns:
            System object containing all parsed power system data

        Raises:
            FileNotFoundError: If the specified file does not exist
            ValueError: If the file format is invalid or cannot be parsed

        Example:
            >>> system = System.from_raw("ieee14.raw")
            >>> print(f"Loaded {system.num_buses()} buses")

        See Also:
            - from_file(): Auto-detect format from extension
            - parse_raw(): Standalone function alternative
        """
        # Lazy import to avoid circular dependency
        from psforge_grid.io.raw_parser import parse_raw

        return parse_raw(filepath)

    @classmethod
    def from_file(cls, filepath: str | Path) -> System:
        """Create a System from a power system data file.

        Factory method that auto-detects the file format based on extension
        and uses the appropriate parser. Supports PSS/E RAW and future formats.

        Args:
            filepath: Path to the data file (extension determines format)

        Returns:
            System object containing all parsed power system data

        Raises:
            FileNotFoundError: If the specified file does not exist
            ValueError: If the file format is not recognized or invalid

        Example:
            >>> system = System.from_file("ieee14.raw")  # PSS/E format
            >>> system = System.from_file("case9.m")    # MATPOWER (future)

        See Also:
            - from_raw(): Explicit PSS/E format loading
            - ParserFactory: Direct parser access
        """
        # Lazy import to avoid circular dependency
        from psforge_grid.io.factories import ParserFactory

        parser = ParserFactory.from_path(filepath)
        return parser.parse(filepath)

    # =========================================================================
    # Count methods
    # =========================================================================

    def num_buses(self) -> int:
        """Return the number of buses in the system."""
        return len(self.buses)

    def num_branches(self) -> int:
        """Return the number of branches in the system."""
        return len(self.branches)

    def num_generators(self) -> int:
        """Return the number of generators in the system."""
        return len(self.generators)

    def num_loads(self) -> int:
        """Return the number of loads in the system."""
        return len(self.loads)

    def num_shunts(self) -> int:
        """Return the number of shunts in the system."""
        return len(self.shunts)

    # =========================================================================
    # Bus lookup methods
    # =========================================================================

    def get_bus(self, bus_id: int) -> Bus | None:
        """Get a bus by its ID.

        Args:
            bus_id: Bus ID to search for

        Returns:
            Bus object if found, None otherwise
        """
        for bus in self.buses:
            if bus.bus_id == bus_id:
                return bus
        return None

    def get_bus_index(self, bus_id: int) -> int:
        """Get the index of a bus in the buses list.

        Args:
            bus_id: Bus ID to search for

        Returns:
            Index in buses list (0-based)

        Raises:
            ValueError: If bus_id is not found
        """
        for i, bus in enumerate(self.buses):
            if bus.bus_id == bus_id:
                return i
        raise ValueError(f"Bus {bus_id} not found in system")

    def get_bus_ids(self) -> list[int]:
        """Get all bus IDs in the system.

        Returns:
            List of bus IDs
        """
        return [bus.bus_id for bus in self.buses]

    # =========================================================================
    # Component lookup by bus
    # =========================================================================

    def get_bus_generators(self, bus_id: int, in_service_only: bool = True) -> list[Generator]:
        """Get all generators connected to a specific bus.

        Args:
            bus_id: Bus ID to search for
            in_service_only: If True, return only in-service generators

        Returns:
            List of Generator objects connected to the bus
        """
        gens = [g for g in self.generators if g.bus_id == bus_id]
        if in_service_only:
            gens = [g for g in gens if g.is_in_service]
        return gens

    def get_bus_loads(self, bus_id: int, in_service_only: bool = True) -> list[Load]:
        """Get all loads connected to a specific bus.

        Args:
            bus_id: Bus ID to search for
            in_service_only: If True, return only in-service loads

        Returns:
            List of Load objects connected to the bus
        """
        loads = [load for load in self.loads if load.bus_id == bus_id]
        if in_service_only:
            loads = [load for load in loads if load.is_in_service]
        return loads

    def get_bus_shunts(self, bus_id: int, in_service_only: bool = True) -> list[Shunt]:
        """Get all shunts connected to a specific bus.

        Args:
            bus_id: Bus ID to search for
            in_service_only: If True, return only in-service shunts

        Returns:
            List of Shunt objects connected to the bus
        """
        shunts = [s for s in self.shunts if s.bus_id == bus_id]
        if in_service_only:
            shunts = [s for s in shunts if s.status == 1]
        return shunts

    def get_branches_at_bus(self, bus_id: int, in_service_only: bool = True) -> list[Branch]:
        """Get all branches connected to a specific bus.

        Args:
            bus_id: Bus ID to search for
            in_service_only: If True, return only in-service branches

        Returns:
            List of Branch objects connected to the bus (either from_bus or to_bus)
        """
        branches = [b for b in self.branches if b.from_bus == bus_id or b.to_bus == bus_id]
        if in_service_only:
            branches = [b for b in branches if b.is_in_service]
        return branches

    # =========================================================================
    # Power injection calculations
    # =========================================================================

    def get_bus_p_injection(self, bus_id: int) -> float:
        """Calculate net active power injection at a bus [p.u.].

        P_injection = sum(P_gen) - sum(P_load)

        Args:
            bus_id: Bus ID

        Returns:
            Net active power injection (generation - load) [p.u.]
        """
        p_gen = sum(g.p_gen for g in self.get_bus_generators(bus_id))
        p_load = sum(load.p_load for load in self.get_bus_loads(bus_id))
        return p_gen - p_load

    def get_bus_q_injection(self, bus_id: int) -> float:
        """Calculate net reactive power injection at a bus [p.u.].

        Q_injection = sum(Q_gen) - sum(Q_load) + V^2 * sum(B_shunt)

        Note: Shunt contribution depends on voltage; this uses nominal V=1.0

        Args:
            bus_id: Bus ID

        Returns:
            Net reactive power injection [p.u.] (excluding voltage-dependent shunt)
        """
        q_gen = sum(g.q_gen for g in self.get_bus_generators(bus_id))
        q_load = sum(load.q_load for load in self.get_bus_loads(bus_id))
        return q_gen - q_load

    def get_bus_shunt_admittance(self, bus_id: int) -> tuple[float, float]:
        """Get total shunt admittance at a bus.

        Args:
            bus_id: Bus ID

        Returns:
            Tuple of (G_total, B_total) [p.u.]
        """
        g_total = sum(s.g_pu for s in self.get_bus_shunts(bus_id))
        b_total = sum(s.b_pu for s in self.get_bus_shunts(bus_id))
        return g_total, b_total

    # =========================================================================
    # System-wide queries
    # =========================================================================

    def get_slack_buses(self) -> list[Bus]:
        """Get all slack (swing) buses in the system.

        Returns:
            List of Bus objects with bus_type == 3
        """
        return [bus for bus in self.buses if bus.is_slack]

    def get_pv_buses(self) -> list[Bus]:
        """Get all PV (generator) buses in the system.

        Returns:
            List of Bus objects with bus_type == 2
        """
        return [bus for bus in self.buses if bus.is_pv]

    def get_pq_buses(self) -> list[Bus]:
        """Get all PQ (load) buses in the system.

        Returns:
            List of Bus objects with bus_type == 1
        """
        return [bus for bus in self.buses if bus.is_pq]

    def get_in_service_branches(self) -> list[Branch]:
        """Get all in-service branches.

        Returns:
            List of Branch objects with status == 1
        """
        return [b for b in self.branches if b.is_in_service]

    def total_generation(self, in_service_only: bool = True) -> tuple[float, float]:
        """Calculate total system generation.

        Args:
            in_service_only: If True, count only in-service generators

        Returns:
            Tuple of (total_P, total_Q) [p.u.]
        """
        gens = self.generators
        if in_service_only:
            gens = [g for g in gens if g.is_in_service]
        total_p = sum(g.p_gen for g in gens)
        total_q = sum(g.q_gen for g in gens)
        return total_p, total_q

    def total_load(self, in_service_only: bool = True) -> tuple[float, float]:
        """Calculate total system load.

        Args:
            in_service_only: If True, count only in-service loads

        Returns:
            Tuple of (total_P, total_Q) [p.u.]
        """
        loads = self.loads
        if in_service_only:
            loads = [load for load in loads if load.is_in_service]
        total_p = sum(load.p_load for load in loads)
        total_q = sum(load.q_load for load in loads)
        return total_p, total_q

    # =========================================================================
    # LLM-friendly output methods
    # =========================================================================

    def to_description(self) -> str:
        """Generate human/LLM-readable description of this system.

        Returns:
            Multi-line string describing the system for LLM context.

        Example:
            >>> system = System.from_raw("ieee14.raw")
            >>> print(system.to_description())
            Power System: IEEE 14-Bus Test System
              Base MVA: 100.0
              Components: 14 buses, 20 branches, 5 generators, 11 loads, 1 shunts
              Total Generation: 2.72 pu P, 0.00 pu Q
              Total Load: 2.59 pu P, 0.74 pu Q
        """
        name_str = self.name if self.name else "Unnamed System"
        p_gen, q_gen = self.total_generation()
        p_load, q_load = self.total_load()

        lines = [
            f"Power System: {name_str}",
            f"  Base MVA: {self.base_mva:.1f}",
            f"  Components: {self.num_buses()} buses, {self.num_branches()} branches, "
            f"{self.num_generators()} generators, {self.num_loads()} loads, "
            f"{self.num_shunts()} shunts",
            f"  Total Generation: {p_gen:.2f} pu P, {q_gen:.2f} pu Q",
            f"  Total Load: {p_load:.2f} pu P, {q_load:.2f} pu Q",
        ]

        if self.description:
            lines.append(f"  Note: {self.description}")

        return "\n".join(lines)

    def to_llm_context(
        self,
        max_buses: int = 20,  # noqa: ARG002
        max_branches: int = 20,  # noqa: ARG002
        include_components: bool = True,
        format: str = "markdown",
    ) -> str:
        """Generate context string optimized for LLM prompts.

        Creates a compact, token-efficient representation of the system
        suitable for embedding in LLM prompts.

        Args:
            max_buses: Maximum number of buses to include in detail
            max_branches: Maximum number of branches to include in detail
            include_components: Whether to include component lists
            format: Output format ("markdown" or "text")

        Returns:
            LLM-friendly context string

        Example:
            >>> context = system.to_llm_context(max_buses=10)
            >>> response = llm.ask(f"Analyze this system: {context}")
        """
        p_gen, q_gen = self.total_generation()
        p_load, q_load = self.total_load()

        if format == "markdown":
            lines = [
                f"## Power System: {self.name or 'Unnamed'}",
                "",
                "| Property | Value |",
                "|----------|-------|",
                f"| Base MVA | {self.base_mva:.1f} |",
                f"| Buses | {self.num_buses()} |",
                f"| Branches | {self.num_branches()} |",
                f"| Generators | {self.num_generators()} |",
                f"| Loads | {self.num_loads()} |",
                f"| Total Gen (P) | {p_gen * self.base_mva:.1f} MW |",
                f"| Total Load (P) | {p_load * self.base_mva:.1f} MW |",
            ]
        else:
            lines = [
                f"Power System: {self.name or 'Unnamed'}",
                f"Base MVA: {self.base_mva:.1f}",
                f"Buses: {self.num_buses()}, Branches: {self.num_branches()}",
                f"Generators: {self.num_generators()}, Loads: {self.num_loads()}",
                f"Total Gen: {p_gen * self.base_mva:.1f} MW, Load: {p_load * self.base_mva:.1f} MW",
            ]

        if self.description:
            lines.append("")
            lines.append(f"Description: {self.description}")

        if include_components:
            lines.append("")
            lines.append("### Bus Types:")
            slack = [b for b in self.buses if b.is_slack]
            pv = [b for b in self.buses if b.is_pv]
            pq = [b for b in self.buses if b.is_pq]
            lines.append(f"- Slack: {len(slack)} ({', '.join(str(b.bus_id) for b in slack)})")
            lines.append(f"- PV: {len(pv)}")
            lines.append(f"- PQ: {len(pq)}")

        return "\n".join(lines)

    def get_all_descriptions(self) -> str:
        """Get descriptions of all components with custom notes.

        Returns only components that have a description field set.

        Returns:
            Multi-line string with all component descriptions
        """
        lines = []

        if self.description:
            lines.append(f"System: {self.description}")

        for bus in self.buses:
            if bus.description:
                name = bus.name or f"Bus {bus.bus_id}"
                lines.append(f"Bus {bus.bus_id} ({name}): {bus.description}")

        for branch in self.branches:
            if branch.description:
                name = branch.name or f"{branch.from_bus}-{branch.to_bus}"
                lines.append(f"Branch {name}: {branch.description}")

        for gen in self.generators:
            if gen.description:
                name = gen.name or f"Gen {gen.gen_id} at Bus {gen.bus_id}"
                lines.append(f"Generator {name}: {gen.description}")

        for load in self.loads:
            if load.description:
                name = load.name or f"Load {load.load_id} at Bus {load.bus_id}"
                lines.append(f"Load {name}: {load.description}")

        for shunt in self.shunts:
            if shunt.description:
                name = shunt.name or f"Shunt {shunt.shunt_id} at Bus {shunt.bus_id}"
                lines.append(f"Shunt {name}: {shunt.description}")

        return "\n".join(lines) if lines else "No descriptions available."
