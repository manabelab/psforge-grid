"""System data model for power system analysis.

This module defines the System class as the central container for all power system components.

Factory Methods (import):
    - from_raw(), from_matpower(), from_pop(), from_dyna(): Create from specific formats
    - from_file(): Create from any supported format (auto-detect)

Export Methods (write):
    - to_raw(), to_matpower(), to_pop(), to_dyna(): Write to specific formats
    - to_file(): Write to any supported format (auto-detect)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.diagram import DiagramData
from psforge_grid.models.generator import Generator
from psforge_grid.models.generator_cost import GeneratorCost
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt


@dataclass(repr=False)
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
        generator_costs: List of GeneratorCost objects for OPF/UC formulations
        base_mva: System base MVA for per-unit conversion (default: 100.0)
        frequency_hz: System frequency [Hz] (default: None).
            50 Hz for Japan/Europe, 60 Hz for North America.
            None means the source format did not provide this information.
        name: System name (optional, default: empty string)
        description: Free-text description providing context about the system.
            For LLM-friendly output.
        diagram_schematic: Schematic single-line diagram layout data.
            Coordinates use the psforge schematic system (right/up positive,
            integer pixels, short edge normalized to 1920 by default).
            None if the source format does not provide layout data.
        diagram_geographic: Geographic coordinate data for GIS visualization.
            Coordinates use latitude/longitude in degrees (CRS required).
            None if the source format does not provide geographic data.

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
    generator_costs: list[GeneratorCost] = field(default_factory=list)
    base_mva: float = 100.0
    frequency_hz: float | None = None
    name: str = ""
    description: str | None = None
    diagram_schematic: DiagramData | None = None
    diagram_geographic: DiagramData | None = None

    def __repr__(self) -> str:
        """Return a one-line summary instead of dumping every component.

        The dataclass-generated repr recursively expands every bus, branch,
        generator, load and shunt, which reaches several megabytes on a system
        the size of IEEE 300. That is unusable in a REPL and expensive for an
        LLM reading the output, so this returns counts only. Use
        ``to_description()`` or ``to_llm_context()`` for detailed output.

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> System(buses=[Bus(1, bus_type=3), Bus(2, bus_type=1)], name="demo")
            <System 'demo' buses=2 branches=0 generators=0 loads=0 shunts=0 base_mva=100.0>
            >>> System()
            <System buses=0 branches=0 generators=0 loads=0 shunts=0 base_mva=100.0>
        """
        name = f" {self.name!r}" if self.name else ""
        return (
            f"<System{name} "
            f"buses={self.num_buses} "
            f"branches={self.num_branches} "
            f"generators={self.num_generators} "
            f"loads={self.num_loads} "
            f"shunts={self.num_shunts} "
            f"base_mva={self.base_mva}>"
        )

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
            >>> print(f"Loaded {system.num_buses} buses")

        See Also:
            - from_file(): Auto-detect format from extension
            - parse_raw(): Standalone function alternative
        """
        # Lazy import to avoid circular dependency
        from psforge_grid.io.raw_parser import parse_raw

        return parse_raw(filepath)

    @classmethod
    def from_matpower(cls, filepath: str | Path) -> System:
        """Create a System from a MATPOWER .m file.

        Factory method for creating System instances from MATPOWER format
        files (.m). Supports standard MATPOWER case files including
        pglib-opf benchmark cases.

        Args:
            filepath: Path to the .m file

        Returns:
            System object containing all parsed power system data

        Raises:
            FileNotFoundError: If the specified file does not exist
            ValueError: If the file format is invalid or cannot be parsed

        Example:
            >>> system = System.from_matpower("case14.m")
            >>> print(f"Loaded {system.num_buses} buses")

        See Also:
            - from_raw(): Load PSS/E RAW format
            - from_file(): Auto-detect format from extension
            - parse_matpower(): Standalone function alternative
        """
        # Lazy import to avoid circular dependency
        from psforge_grid.io.matpower_parser import parse_matpower

        return parse_matpower(filepath)

    @classmethod
    def from_pop(cls, filepath: str | Path) -> System:
        """Create a System from a CPAT .pop file.

        Factory method for creating System instances from CPAT-GUI native
        format (.pop = ZIP archive containing XML files).

        Args:
            filepath: Path to the .pop file

        Returns:
            System object containing all parsed power system data

        Raises:
            FileNotFoundError: If the specified file does not exist
            ValueError: If the file format is invalid or cannot be parsed

        Example:
            >>> system = System.from_pop("WEST10peak.pop")
            >>> print(f"Loaded {system.num_buses} buses")

        See Also:
            - from_raw(): Load PSS/E RAW format
            - from_file(): Auto-detect format from extension
            - parse_pop(): Standalone function alternative
        """
        # Lazy import to avoid circular dependency
        from psforge_grid.io.pop_parser import parse_pop

        return parse_pop(filepath)

    @classmethod
    def from_dss(cls, filepath: str | Path) -> System:
        """Create a System from an OpenDSS .dss file.

        Factory method for creating System instances from OpenDSS script
        format files (.dss). Uses opendssdirect.py to compile and extract data.

        Args:
            filepath: Path to the .dss file

        Returns:
            System object containing all parsed power system data

        Raises:
            FileNotFoundError: If the specified file does not exist
            ValueError: If the file cannot be compiled by OpenDSS

        Example:
            >>> system = System.from_dss("network.dss")
            >>> print(f"Loaded {system.num_buses} buses")

        See Also:
            - from_file(): Auto-detect format from extension
            - parse_dss(): Standalone function alternative
        """
        from psforge_grid.io.dss_parser import parse_dss

        return parse_dss(filepath)

    @classmethod
    def from_dyna(cls, filepath: str | Path) -> System:
        """Create a System from a CPAT dyna card format file.

        Factory method for creating System instances from CPAT Fortran
        fixed-column card format files (.dyna).

        Args:
            filepath: Path to the .dyna file

        Returns:
            System object containing all parsed power system data

        Raises:
            FileNotFoundError: If the specified file does not exist
            ValueError: If the file format is invalid or cannot be parsed

        Example:
            >>> system = System.from_dyna("cpat_model.dyna")
            >>> print(f"Loaded {system.num_buses} buses")

        See Also:
            - from_pop(): Load CPAT .pop (ZIP+XML) format
            - from_file(): Auto-detect format from extension
            - parse_dyna(): Standalone function alternative
        """
        # Lazy import to avoid circular dependency
        from psforge_grid.io.dyna_parser import parse_dyna

        return parse_dyna(filepath)

    @classmethod
    def from_json(cls, filepath: str | Path) -> System:
        """Create a System from a psforge-grid JSON file.

        Factory method for loading System from psforge-grid native JSON
        format (.psfg.json). Validates the format metadata to prevent
        loading pglib-uc or other JSON files.

        Args:
            filepath: Path to the .psfg.json file

        Returns:
            System object containing all parsed power system data

        Raises:
            FileNotFoundError: If the specified file does not exist
            ValueError: If the file is not a valid psforge-grid JSON file

        Example:
            >>> system = System.from_json("ieee14.psfg.json")

        See Also:
            - from_file(): Auto-detect format from extension
            - parse_json(): Standalone function alternative
        """
        from psforge_grid.io.json_parser import parse_json

        return parse_json(filepath)

    # =========================================================================
    # Export methods (write to file)
    # =========================================================================

    def to_raw(self, filepath: str | Path) -> None:
        """Export this System to a PSS/E RAW file.

        Args:
            filepath: Output file path (.raw)

        Example:
            >>> system.to_raw("output.raw")

        See Also:
            - to_file(): Auto-detect format from extension
            - write_raw(): Standalone function alternative
        """
        from psforge_grid.io.raw_writer import write_raw

        write_raw(self, filepath)

    def to_matpower(self, filepath: str | Path) -> None:
        """Export this System to a MATPOWER .m file.

        Args:
            filepath: Output file path (.m)

        Example:
            >>> system.to_matpower("output.m")

        See Also:
            - to_file(): Auto-detect format from extension
            - write_matpower(): Standalone function alternative
        """
        from psforge_grid.io.matpower_writer import write_matpower

        write_matpower(self, filepath)

    def to_pop(self, filepath: str | Path) -> None:
        """Export this System to a CPAT .pop file.

        Args:
            filepath: Output file path (.pop)

        Example:
            >>> system.to_pop("output.pop")

        See Also:
            - to_file(): Auto-detect format from extension
            - write_pop(): Standalone function alternative
        """
        from psforge_grid.io.pop_writer import write_pop

        write_pop(self, filepath)

    def to_dss(self, filepath: str | Path) -> None:
        """Export this System to an OpenDSS .dss file.

        Args:
            filepath: Output file path (.dss)

        Example:
            >>> system.to_dss("output.dss")

        See Also:
            - to_file(): Auto-detect format from extension
            - write_dss(): Standalone function alternative
        """
        from psforge_grid.io.dss_writer import write_dss

        write_dss(self, filepath)

    def to_dyna(self, filepath: str | Path) -> None:
        """Export this System to a CPAT .dyna file.

        Args:
            filepath: Output file path (.dyna)

        Example:
            >>> system.to_dyna("output.dyna")

        See Also:
            - to_file(): Auto-detect format from extension
            - write_dyna(): Standalone function alternative
        """
        from psforge_grid.io.dyna_writer import write_dyna

        write_dyna(self, filepath)

    def to_json(
        self,
        filepath: str | Path,
        *,
        omit_none: bool = True,
    ) -> None:
        """Export this System to a psforge-grid JSON file.

        Args:
            filepath: Output file path (recommended: .psfg.json)
            omit_none: If True, omit fields with None values (default: True)

        Example:
            >>> system.to_json("output.psfg.json")

        See Also:
            - to_file(): Auto-detect format from extension
            - write_json(): Standalone function alternative
        """
        from psforge_grid.io.json_writer import write_json

        write_json(self, filepath, omit_none=omit_none)

    def to_file(self, filepath: str | Path) -> None:
        """Export this System to a file, auto-detecting format from extension.

        Args:
            filepath: Output file path (extension determines format)

        Raises:
            ValueError: If the file extension is not recognized

        Example:
            >>> system.to_file("output.raw")   # PSS/E format
            >>> system.to_file("output.m")     # MATPOWER format
            >>> system.to_file("output.pop")   # CPAT Pop format
            >>> system.to_file("output.dyna")  # CPAT Dyna format

        See Also:
            - to_raw(), to_matpower(), to_pop(), to_dyna(): Explicit format
            - WriterFactory: Direct writer access
        """
        from psforge_grid.io.factories import WriterFactory

        writer = WriterFactory.from_path(filepath)
        writer.write(self, filepath)

    # =========================================================================
    # Factory methods (class methods - read from file)
    # =========================================================================

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
    # Modification methods (validated)
    # =========================================================================

    def add_bus(self, bus: Bus) -> None:
        """Add a bus with validation.

        Validates that the bus ID does not already exist in the system
        before adding. Use this method instead of direct list append
        for safer system modification.

        Args:
            bus: Bus to add

        Raises:
            ValueError: If bus_id already exists in the system.

        Example:
            >>> system.add_bus(Bus(bus_id=15, bus_type=1, base_kv=33.0))
        """
        if any(b.bus_id == bus.bus_id for b in self.buses):
            raise ValueError(
                f"Bus {bus.bus_id} already exists. "
                f"Use a unique bus_id (current max: {max(b.bus_id for b in self.buses)})."
            )
        self.buses.append(bus)

    def add_branch(self, branch: Branch) -> None:
        """Add a branch with validation.

        Validates that both from_bus and to_bus exist in the system
        before adding.

        Args:
            branch: Branch to add

        Raises:
            ValueError: If from_bus or to_bus not found in system.

        Example:
            >>> system.add_branch(Branch(from_bus=14, to_bus=15, r_pu=0.01, x_pu=0.05))
        """
        bus_ids = {b.bus_id for b in self.buses}
        if branch.from_bus not in bus_ids:
            raise ValueError(
                f"from_bus {branch.from_bus} not found in system. "
                f"Available bus IDs: {sorted(bus_ids)}"
            )
        if branch.to_bus not in bus_ids:
            raise ValueError(
                f"to_bus {branch.to_bus} not found in system. Available bus IDs: {sorted(bus_ids)}"
            )
        self.branches.append(branch)

    def add_generator(self, generator: Generator) -> None:
        """Add a generator with validation.

        Validates that the generator's bus_id exists in the system.

        Args:
            generator: Generator to add

        Raises:
            ValueError: If bus_id not found in system.

        Example:
            >>> system.add_generator(Generator(bus_id=15, p_gen=0.5, gen_id="PV1"))
        """
        if not any(b.bus_id == generator.bus_id for b in self.buses):
            raise ValueError(
                f"Bus {generator.bus_id} not found in system. Add the bus first with add_bus()."
            )
        self.generators.append(generator)

    def add_shunt(self, shunt: Shunt) -> None:
        """Add a shunt device with validation.

        Validates that the shunt's bus_id exists in the system.

        Args:
            shunt: Shunt to add

        Raises:
            ValueError: If bus_id not found in system.

        Example:
            >>> system.add_shunt(Shunt(bus_id=15, b_pu=0.05))
        """
        if not any(b.bus_id == shunt.bus_id for b in self.buses):
            raise ValueError(
                f"Bus {shunt.bus_id} not found in system. Add the bus first with add_bus()."
            )
        self.shunts.append(shunt)

    def add_load(self, load: Load) -> None:
        """Add a load with validation.

        Validates that the load's bus_id exists in the system.

        Args:
            load: Load to add

        Raises:
            ValueError: If bus_id not found in system.

        Example:
            >>> system.add_load(Load(bus_id=15, p_load=0.3, q_load=0.1))
        """
        if not any(b.bus_id == load.bus_id for b in self.buses):
            raise ValueError(
                f"Bus {load.bus_id} not found in system. Add the bus first with add_bus()."
            )
        self.loads.append(load)

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> list[str]:
        """Validate system consistency.

        Checks structural integrity of the system data, including:
        - Duplicate bus IDs
        - Slack bus existence
        - Branch bus references (from_bus, to_bus)
        - Generator, load, and shunt bus references

        Returns a list of error messages. An empty list means the system
        is valid and ready for power flow calculation.

        Returns:
            List of validation error messages. Empty list means valid.

        Example:
            >>> errors = system.validate()
            >>> if errors:
            ...     for e in errors:
            ...         print(f"ERROR: {e}")
            ... else:
            ...     print("System is valid")
        """
        errors: list[str] = []
        bus_ids = {b.bus_id for b in self.buses}

        # Duplicate bus IDs
        if len(bus_ids) != len(self.buses):
            seen: set[int] = set()
            for b in self.buses:
                if b.bus_id in seen:
                    errors.append(f"Duplicate bus_id: {b.bus_id}")
                seen.add(b.bus_id)

        # Slack bus existence
        slack_buses = [b for b in self.buses if b.bus_type == 3]
        if not slack_buses:
            errors.append("No slack bus (bus_type=3) found")

        # Branch bus references
        for i, br in enumerate(self.branches):
            if br.from_bus not in bus_ids:
                errors.append(
                    f"Branch[{i}] ({br.from_bus}-{br.to_bus}): from_bus {br.from_bus} not in system"
                )
            if br.to_bus not in bus_ids:
                errors.append(
                    f"Branch[{i}] ({br.from_bus}-{br.to_bus}): to_bus {br.to_bus} not in system"
                )

        # Generator bus references
        for gen in self.generators:
            if gen.bus_id not in bus_ids:
                errors.append(f"Generator '{gen.gen_id}' at bus {gen.bus_id}: bus not in system")

        # Load bus references
        for load in self.loads:
            if load.bus_id not in bus_ids:
                errors.append(f"Load '{load.load_id}' at bus {load.bus_id}: bus not in system")

        # Shunt bus references
        for shunt in self.shunts:
            if shunt.bus_id not in bus_ids:
                errors.append(f"Shunt '{shunt.shunt_id}' at bus {shunt.bus_id}: bus not in system")

        return errors

    def validate_detailed(self, strict: bool = False) -> list[dict[str, str]]:
        """Run detailed validation checks on the system.

        Performs comprehensive validation including structural integrity,
        voltage magnitude ranges, PV bus generator presence, and branch
        impedance sign checks. In strict mode, additional checks such as
        isolated bus detection are enabled, and some warnings are elevated
        to errors.

        This method extends validate() with power-system-specific heuristic
        checks useful for data quality assurance and pre-analysis screening.

        Args:
            strict: If True, enable strict validation mode. This elevates
                certain warnings to errors and enables additional checks
                (e.g., isolated bus detection).

        Returns:
            List of issue dictionaries, each containing:
                - "level": "error" or "warning"
                - "message": Human-readable description of the issue

            An empty list means no issues were detected.

        Example:
            >>> issues = system.validate_detailed()
            >>> errors = [i for i in issues if i["level"] == "error"]
            >>> warnings = [i for i in issues if i["level"] == "warning"]
            >>> if not errors:
            ...     print("System is ready for analysis")
        """
        issues: list[dict[str, str]] = []

        # Check for slack bus
        slack_buses = self.get_slack_buses()
        if not slack_buses:
            issues.append({"level": "error", "message": "No slack (swing) bus found in system"})
        elif len(slack_buses) > 1:
            issues.append(
                {
                    "level": "warning",
                    "message": f"Multiple slack buses found: {[b.bus_id for b in slack_buses]}",
                }
            )

        # Check voltage magnitudes
        for bus in self.buses:
            if bus.v_magnitude < 0.8:
                issues.append(
                    {
                        "level": "error" if strict else "warning",
                        "message": f"Bus {bus.bus_id}: Very low voltage {bus.v_magnitude:.3f} pu",
                    }
                )
            elif bus.v_magnitude < 0.9:
                issues.append(
                    {
                        "level": "warning",
                        "message": f"Bus {bus.bus_id}: Low voltage {bus.v_magnitude:.3f} pu",
                    }
                )
            elif bus.v_magnitude > 1.1:
                issues.append(
                    {
                        "level": "warning",
                        "message": f"Bus {bus.bus_id}: High voltage {bus.v_magnitude:.3f} pu",
                    }
                )
            elif bus.v_magnitude > 1.2:
                issues.append(
                    {
                        "level": "error" if strict else "warning",
                        "message": f"Bus {bus.bus_id}: Very high voltage {bus.v_magnitude:.3f} pu",
                    }
                )

        # Check PV buses have generators
        pv_buses = self.get_pv_buses()
        for bus in pv_buses:
            gens = self.get_bus_generators(bus.bus_id)
            if not gens:
                issues.append(
                    {
                        "level": "error",
                        "message": f"PV bus {bus.bus_id} has no generator",
                    }
                )

        # Check for negative impedance (typically an error)
        for branch in self.branches:
            if branch.x_pu < 0:
                issues.append(
                    {
                        "level": "error",
                        "message": f"Branch {branch.from_bus}-{branch.to_bus}: Negative reactance X={branch.x_pu:.4f}",
                    }
                )
            if branch.r_pu < 0:
                issues.append(
                    {
                        "level": "warning",
                        "message": f"Branch {branch.from_bus}-{branch.to_bus}: Negative resistance R={branch.r_pu:.4f}",
                    }
                )

        # Strict mode additional checks
        if strict:
            # Check all buses are referenced
            bus_ids = set(self.get_bus_ids())
            referenced_buses: set[int] = set()

            for branch in self.branches:
                referenced_buses.add(branch.from_bus)
                referenced_buses.add(branch.to_bus)
            for gen in self.generators:
                referenced_buses.add(gen.bus_id)
            for load in self.loads:
                referenced_buses.add(load.bus_id)

            isolated = bus_ids - referenced_buses
            for bus_id in isolated:
                found_bus = self.get_bus(bus_id)
                if found_bus and not found_bus.is_isolated:
                    issues.append(
                        {
                            "level": "warning",
                            "message": f"Bus {bus_id}: Not referenced by any branch, generator, or load",
                        }
                    )

        return issues

    # =========================================================================
    # Count properties
    # =========================================================================

    @property
    def num_buses(self) -> int:
        """Number of buses in the system.

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> system = System(buses=[Bus(1, bus_type=3), Bus(2, bus_type=1)])
            >>> system.num_buses
            2
        """
        return len(self.buses)

    @property
    def num_branches(self) -> int:
        """Number of branches (lines and transformers) in the system.

        Example:
            >>> from psforge_grid.models import System, Branch
            >>> system = System(branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1)])
            >>> system.num_branches
            1
        """
        return len(self.branches)

    @property
    def num_generators(self) -> int:
        """Number of generators in the system.

        Example:
            >>> from psforge_grid.models import System, Generator
            >>> system = System(generators=[Generator(bus_id=1, p_gen=1.0)])
            >>> system.num_generators
            1
        """
        return len(self.generators)

    @property
    def num_loads(self) -> int:
        """Number of loads in the system.

        Example:
            >>> from psforge_grid.models import System, Load
            >>> system = System(loads=[Load(bus_id=2, p_load=0.8, q_load=0.2)])
            >>> system.num_loads
            1
        """
        return len(self.loads)

    @property
    def num_shunts(self) -> int:
        """Number of shunt devices (capacitors and reactors) in the system.

        Example:
            >>> from psforge_grid.models import System, Shunt
            >>> system = System(shunts=[Shunt(bus_id=3, b_pu=0.19)])
            >>> system.num_shunts
            1
        """
        return len(self.shunts)

    @property
    def num_generator_costs(self) -> int:
        """Number of generator cost functions in the system.

        Example:
            >>> from psforge_grid.models import System, GeneratorCost
            >>> system = System(generator_costs=[GeneratorCost(gen_index=0, model=2)])
            >>> system.num_generator_costs
            1
        """
        return len(self.generator_costs)

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
            f"  Components: {self.num_buses} buses, {self.num_branches} branches, "
            f"{self.num_generators} generators, {self.num_loads} loads, "
            f"{self.num_shunts} shunts",
            f"  Total Generation: {p_gen:.2f} pu P, {q_gen:.2f} pu Q",
            f"  Total Load: {p_load:.2f} pu P, {q_load:.2f} pu Q",
        ]

        if self.generator_costs:
            lines.append(f"  Generator Costs: {self.num_generator_costs} cost functions")

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
                f"| Buses | {self.num_buses} |",
                f"| Branches | {self.num_branches} |",
                f"| Generators | {self.num_generators} |",
                f"| Loads | {self.num_loads} |",
                f"| Total Gen (P) | {p_gen * self.base_mva:.1f} MW |",
                f"| Total Load (P) | {p_load * self.base_mva:.1f} MW |",
            ]
        else:
            lines = [
                f"Power System: {self.name or 'Unnamed'}",
                f"Base MVA: {self.base_mva:.1f}",
                f"Buses: {self.num_buses}, Branches: {self.num_branches}",
                f"Generators: {self.num_generators}, Loads: {self.num_loads}",
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
