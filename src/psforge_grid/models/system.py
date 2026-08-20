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

import re
from dataclasses import dataclass, field
from pathlib import Path

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.diagram import DiagramData
from psforge_grid.models.generator import Generator
from psforge_grid.models.generator_cost import GeneratorCost
from psforge_grid.models.identity import ID_PATTERN
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt

CASE_TIME_PATTERN = re.compile(r"^\d{4}(-\d{2}(-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?)?)?$")
"""ISO-8601 with partial precision: "2026", "2026-08", "2026-08-20", "2026-08-20T15:00"."""


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
        id: Case identifier (default: None). Same character set as element
            ids (``[A-Za-z0-9_]+``); a natural primary key when systems are
            stored in a database. Never auto-generated — case identity is
            the user's decision.
        order: Sort order within a collection of cases (default: None).
        tags: Attribute/grouping tags. Hierarchies use the ``"key:value"``
            convention, e.g. ``["area:west", "study:2030peak"]``.
        case_time: Point in time this network data represents (default: None).
            ISO-8601 with partial precision allowed: ``"2026"``, ``"2026-08"``,
            ``"2026-08-20"``, or ``"2026-08-20T15:00"``. A string rather than
            a datetime because "the August 2026 snapshot" has no meaningful
            day or hour; lexicographic order still matches chronological order.
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
        - Every element carries a unified ``id`` (unique string across the
          whole system); use helper methods to query components by id

    Example:
        >>> from psforge_grid.models import System, Bus, Branch, Generator, Load
        >>> system = System(
        ...     buses=[Bus("B1", bus_type=3), Bus("B2", bus_type=1)],
        ...     branches=[Branch("BR1_2_1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
        ...     generators=[Generator("G1_1", bus_id="B1", p_gen=1.0)],
        ...     loads=[Load("LD2_1", bus_id="B2", p_load=0.8, q_load=0.2)],
        ...     case_time="2026-08",
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
    id: str | None = None
    order: float | None = None
    tags: list[str] = field(default_factory=list)
    case_time: str | None = None
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
            >>> System(buses=[Bus("B1", bus_type=3), Bus("B2", bus_type=1)], name="demo")
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

    def _check_new_id(self, id_: str) -> None:
        """Reject an element id that is already used anywhere in this system.

        Ids are unique across the whole system, all element types combined,
        so a Bus and a Generator can never share an id either.
        """
        if id_ in self.used_ids():
            raise ValueError(
                f"Element id {id_!r} already exists in this system. "
                "Ids are unique across all element types; choose another id."
            )

    def add_bus(self, bus: Bus) -> None:
        """Add a bus with validation.

        Validates that the bus id is not already used anywhere in the
        system before adding. Use this method instead of direct list append
        for safer system modification.

        Args:
            bus: Bus to add

        Raises:
            ValueError: If the id already exists in the system.

        Example:
            >>> system.add_bus(Bus("B15", bus_type=1, base_kv=33.0))
        """
        self._check_new_id(bus.id)
        self.buses.append(bus)

    def add_branch(self, branch: Branch) -> None:
        """Add a branch with validation.

        Validates that the branch id is unused and that both terminal buses
        exist in the system before adding.

        Args:
            branch: Branch to add

        Raises:
            ValueError: If the id already exists, or if from_bus_id or
                to_bus_id is not found in the system.

        Example:
            >>> system.add_branch(Branch("BR14_15_1", "B14", "B15", r_pu=0.01, x_pu=0.05))
        """
        self._check_new_id(branch.id)
        bus_ids = {b.id for b in self.buses}
        if branch.from_bus_id not in bus_ids:
            raise ValueError(
                f"from_bus_id {branch.from_bus_id!r} not found in system. "
                f"Available bus ids: {sorted(bus_ids)}"
            )
        if branch.to_bus_id not in bus_ids:
            raise ValueError(
                f"to_bus_id {branch.to_bus_id!r} not found in system. "
                f"Available bus ids: {sorted(bus_ids)}"
            )
        self.branches.append(branch)

    def add_generator(self, generator: Generator) -> None:
        """Add a generator with validation.

        Validates that the generator id is unused and that its bus exists
        in the system.

        Args:
            generator: Generator to add

        Raises:
            ValueError: If the id already exists, or if bus_id is not
                found in the system.

        Example:
            >>> system.add_generator(Generator("G15_PV1", bus_id="B15", p_gen=0.5))
        """
        self._check_new_id(generator.id)
        if not any(b.id == generator.bus_id for b in self.buses):
            raise ValueError(
                f"Bus {generator.bus_id!r} not found in system. Add the bus first with add_bus()."
            )
        self.generators.append(generator)

    def add_shunt(self, shunt: Shunt) -> None:
        """Add a shunt device with validation.

        Validates that the shunt id is unused and that its bus exists in
        the system.

        Args:
            shunt: Shunt to add

        Raises:
            ValueError: If the id already exists, or if bus_id is not
                found in the system.

        Example:
            >>> system.add_shunt(Shunt("SH15_1", bus_id="B15", b_pu=0.05))
        """
        self._check_new_id(shunt.id)
        if not any(b.id == shunt.bus_id for b in self.buses):
            raise ValueError(
                f"Bus {shunt.bus_id!r} not found in system. Add the bus first with add_bus()."
            )
        self.shunts.append(shunt)

    def add_load(self, load: Load) -> None:
        """Add a load with validation.

        Validates that the load id is unused and that its bus exists in
        the system.

        Args:
            load: Load to add

        Raises:
            ValueError: If the id already exists, or if bus_id is not
                found in the system.

        Example:
            >>> system.add_load(Load("LD15_1", bus_id="B15", p_load=0.3, q_load=0.1))
        """
        self._check_new_id(load.id)
        if not any(b.id == load.bus_id for b in self.buses):
            raise ValueError(
                f"Bus {load.bus_id!r} not found in system. Add the bus first with add_bus()."
            )
        self.loads.append(load)

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> list[str]:
        """Validate system consistency.

        Checks structural integrity of the system data, including:
        - Element id syntax ([A-Za-z0-9_]+; catches data loaded around
          __post_init__, e.g. hand-edited JSON)
        - Duplicate ids across ALL element types (system-wide uniqueness)
        - Slack bus existence
        - Branch bus references (from_bus_id, to_bus_id)
        - Generator, load, and shunt bus references
        - GeneratorCost generator references (generator_id)
        - case_time format (ISO-8601, partial precision allowed)

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
        bus_ids = {b.id for b in self.buses}

        # Id syntax and system-wide duplicates (all element types combined)
        all_elements: list[tuple[str, str]] = [
            *(("Bus", b.id) for b in self.buses),
            *(("Branch", br.id) for br in self.branches),
            *(("Generator", g.id) for g in self.generators),
            *(("Load", ld.id) for ld in self.loads),
            *(("Shunt", s.id) for s in self.shunts),
            *(("GeneratorCost", c.id) for c in self.generator_costs),
        ]
        seen: dict[str, str] = {}
        for kind, id_ in all_elements:
            if not ID_PATTERN.match(id_):
                errors.append(f"{kind} id {id_!r} is invalid: ids must match [A-Za-z0-9_]+")
            if id_ in seen:
                errors.append(f"Duplicate id {id_!r}: used by {seen[id_]} and {kind}")
            else:
                seen[id_] = kind
        if self.id is not None and not ID_PATTERN.match(self.id):
            errors.append(f"System id {self.id!r} is invalid: ids must match [A-Za-z0-9_]+")

        # Slack bus existence
        slack_buses = [b for b in self.buses if b.bus_type == 3]
        if not slack_buses:
            errors.append("No slack bus (bus_type=3) found")

        # Branch bus references
        for br in self.branches:
            if br.from_bus_id not in bus_ids:
                errors.append(f"Branch {br.id}: from_bus_id {br.from_bus_id!r} not in system")
            if br.to_bus_id not in bus_ids:
                errors.append(f"Branch {br.id}: to_bus_id {br.to_bus_id!r} not in system")

        # Generator bus references
        for gen in self.generators:
            if gen.bus_id not in bus_ids:
                errors.append(f"Generator {gen.id}: bus_id {gen.bus_id!r} not in system")

        # Load bus references
        for load in self.loads:
            if load.bus_id not in bus_ids:
                errors.append(f"Load {load.id}: bus_id {load.bus_id!r} not in system")

        # Shunt bus references
        for shunt in self.shunts:
            if shunt.bus_id not in bus_ids:
                errors.append(f"Shunt {shunt.id}: bus_id {shunt.bus_id!r} not in system")

        # GeneratorCost generator references
        generator_ids = {g.id for g in self.generators}
        for cost in self.generator_costs:
            if cost.generator_id not in generator_ids:
                errors.append(
                    f"GeneratorCost {cost.id}: generator_id {cost.generator_id!r} not in system"
                )

        # case_time format
        if self.case_time is not None and not CASE_TIME_PATTERN.match(self.case_time):
            errors.append(
                f"case_time {self.case_time!r} is not ISO-8601 "
                "(expected e.g. '2026', '2026-08', '2026-08-20', '2026-08-20T15:00')"
            )

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
                    "message": f"Multiple slack buses found: {[b.id for b in slack_buses]}",
                }
            )

        # Check voltage magnitudes
        for bus in self.buses:
            if bus.v_magnitude < 0.8:
                issues.append(
                    {
                        "level": "error" if strict else "warning",
                        "message": f"Bus {bus.id}: Very low voltage {bus.v_magnitude:.3f} pu",
                    }
                )
            elif bus.v_magnitude < 0.9:
                issues.append(
                    {
                        "level": "warning",
                        "message": f"Bus {bus.id}: Low voltage {bus.v_magnitude:.3f} pu",
                    }
                )
            elif bus.v_magnitude > 1.1:
                issues.append(
                    {
                        "level": "warning",
                        "message": f"Bus {bus.id}: High voltage {bus.v_magnitude:.3f} pu",
                    }
                )
            elif bus.v_magnitude > 1.2:
                issues.append(
                    {
                        "level": "error" if strict else "warning",
                        "message": f"Bus {bus.id}: Very high voltage {bus.v_magnitude:.3f} pu",
                    }
                )

        # Check PV buses have generators
        pv_buses = self.get_pv_buses()
        for bus in pv_buses:
            gens = self.get_bus_generators(bus.id)
            if not gens:
                issues.append(
                    {
                        "level": "error",
                        "message": f"PV bus {bus.id} has no generator",
                    }
                )

        # Check for negative impedance (typically an error)
        for branch in self.branches:
            if branch.x_pu < 0:
                issues.append(
                    {
                        "level": "error",
                        "message": f"Branch {branch.id}: Negative reactance X={branch.x_pu:.4f}",
                    }
                )
            if branch.r_pu < 0:
                issues.append(
                    {
                        "level": "warning",
                        "message": f"Branch {branch.id}: Negative resistance R={branch.r_pu:.4f}",
                    }
                )

        # Strict mode additional checks
        if strict:
            # Check all buses are referenced
            bus_ids = set(self.get_bus_ids())
            referenced_buses: set[str] = set()

            for branch in self.branches:
                referenced_buses.add(branch.from_bus_id)
                referenced_buses.add(branch.to_bus_id)
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

        issues.extend(self.check_data_completeness())

        return issues

    def check_data_completeness(self) -> list[dict[str, str]]:
        """Report inputs that downstream analyses need but this system lacks.

        RAW and MATPOWER files routinely arrive without branch ratings or
        machine reactances. Nothing rejects such a system: a thermal screening
        simply has no limit to compare against, and a fault study silently
        treats a generator with no reactance as absent, which understates fault
        current instead of failing. This surfaces the gap so the omission is a
        decision rather than an accident.

        Returns:
            List of dicts with 'level' and 'message', matching
            validate_detailed(). Always 'warning': missing data is not an
            error, since a power flow needs none of it.

        Example:
            >>> from psforge_grid.models import System, Branch
            >>> system = System(branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)])
            >>> for issue in system.check_data_completeness():
            ...     print(issue["message"])
            Branch ratings: rate_a missing on 1/1 branches. Thermal loading cannot be assessed; loading status will be NOT_CLASSIFIED. Use assign_default_ratings() to apply documented defaults.

        See Also:
            - assign_default_ratings(): opt-in defaults for missing ratings
            - assign_default_reactances(): opt-in defaults for missing reactances
        """
        issues: list[dict[str, str]] = []

        if self.branches:
            missing = sum(1 for b in self.branches if b.rate_a is None)
            if missing:
                issues.append(
                    {
                        "level": "warning",
                        "message": (
                            f"Branch ratings: rate_a missing on {missing}/{len(self.branches)} "
                            "branches. Thermal loading cannot be assessed; loading status will "
                            "be NOT_CLASSIFIED. Use assign_default_ratings() to apply "
                            "documented defaults."
                        ),
                    }
                )

        in_service = [g for g in self.generators if g.is_in_service]
        if in_service:
            missing = sum(1 for g in in_service if g.get_fault_reactance() is None)
            if missing:
                issues.append(
                    {
                        "level": "warning",
                        "message": (
                            f"Machine reactances: sub-transient reactance missing on "
                            f"{missing}/{len(in_service)} in-service generators. A fault study "
                            "treats these machines as absent, which UNDERSTATES fault current. "
                            "Use assign_default_reactances() to apply documented defaults."
                        ),
                    }
                )

        return issues

    # =========================================================================
    # Opt-in defaults for missing data
    # =========================================================================

    def assign_default_ratings(
        self,
        rule: dict[float, float] | None = None,
        overwrite: bool = False,
    ) -> int:
        """Assign branch thermal ratings by voltage class. Opt-in.

        This invents data. It is deliberately not automatic: the package's
        stated position is that unspecified limits yield NOT_CLASSIFIED rather
        than an arbitrary default (see VoltageStatus/LoadingStatus). Calling
        this is you choosing an assumption, and the choice is recorded so
        to_llm_context() can declare it alongside the results.

        Ratings are set from the higher-voltage terminal of each branch. Note
        this is a crude rule: a real rating depends on conductor, ambient
        conditions and the circuit's actual duty, none of which are in a RAW
        file. Prefer real ratings whenever you have them.

        Args:
            rule: Mapping of minimum base_kv to rating [MVA], applied as
                'highest floor at or below the branch voltage wins'. Defaults
                to a transmission-scale table (500kV:2000, 300kV:1200,
                200kV:800, 100kV:400, 50kV:150, 0kV:50).
            overwrite: If True, replace ratings that are already set. Defaults
                to False, so real data is never clobbered.

        Returns:
            Number of branches whose rate_a was assigned.

        Raises:
            ValueError: If a branch terminal has a non-positive base_kv, which
                cannot be classified at all.

        Note:
            Bus.base_kv defaults to 1.0, so a bus left at exactly 1.0 may be an
            unset voltage rather than a real 1 kV bus. Those branches are still
            rated, but the count is called out in the recorded assumption, since
            their voltage class is unverified. Genuine low voltages are fine:
            IEEE 300 has real 0.6 kV buses.

        Example:
            >>> from psforge_grid.models import System, Bus, Branch
            >>> system = System(
            ...     buses=[
            ...         Bus("B1", bus_type=3, base_kv=345.0),
            ...         Bus("B2", bus_type=1, base_kv=345.0),
            ...     ],
            ...     branches=[Branch("BR1_2_1", "B1", "B2", r_pu=0.01, x_pu=0.1)],
            ... )
            >>> system.assign_default_ratings()
            1
            >>> system.branches[0].rate_a
            1200.0
        """
        table = (
            rule
            if rule is not None
            else {
                500.0: 2000.0,
                300.0: 1200.0,
                200.0: 800.0,
                100.0: 400.0,
                50.0: 150.0,
                0.0: 50.0,
            }
        )
        floors = sorted(table.keys(), reverse=True)
        kv = {bus.id: bus.base_kv for bus in self.buses}

        targets = [b for b in self.branches if overwrite or b.rate_a is None]
        invalid = {
            bus_id
            for b in targets
            for bus_id in (b.from_bus_id, b.to_bus_id)
            if kv.get(bus_id, 1.0) <= 0.0
        }
        if invalid:
            raise ValueError(
                f"Cannot assign ratings: {len(invalid)} bus(es) have a non-positive base_kv, "
                f"which has no voltage class: {sorted(invalid)[:10]}. Set Bus.base_kv on these "
                f"buses first."
            )

        assigned = 0
        unverified = 0
        for branch in targets:
            v = max(kv[branch.from_bus_id], kv[branch.to_bus_id])
            # 1.0 is the field's default, so it may mean 'nobody set this'.
            # Rate it anyway, but say so rather than let it pass as known.
            if kv[branch.from_bus_id] == 1.0 or kv[branch.to_bus_id] == 1.0:
                unverified += 1
            rate = next(table[f] for f in floors if v >= f)
            branch.rate_a = rate
            branch.rate_b = rate * 1.1
            branch.rate_c = rate * 1.2
            assigned += 1

        if assigned:
            note = (
                f"Branch ratings: {assigned} branch(es) rated by voltage class, "
                f"not from real equipment data. Thermal results depend on this assumption."
            )
            if unverified:
                note += (
                    f" {unverified} of them touch a bus left at the 1.0 kV default, so their "
                    f"voltage class is unverified."
                )
            self._record_assumption(note)
        return assigned

    def assign_default_reactances(self, xdpp_pu: float = 0.2, overwrite: bool = False) -> int:
        """Assign a sub-transient reactance to machines that lack one. Opt-in.

        Like assign_default_ratings(), this invents data and is not automatic.
        It exists because the alternative is worse: a fault study silently drops
        a machine with no reactance, so the network loses a source and the
        computed fault level comes out too LOW. An understated fault level is
        the dangerous direction — it is the one that reads as safe.

        Args:
            xdpp_pu: Sub-transient reactance [pu on the machine's own mbase].
                Defaults to 0.2, a conventional round figure for synchronous
                machines. Real values vary widely with machine design.
            overwrite: If True, replace reactances that are already set.
                Defaults to False, so real data is never clobbered.

        Returns:
            Number of generators whose xdpp_pu was assigned.

        Example:
            >>> from psforge_grid.models import System, Generator
            >>> system = System(generators=[Generator("G1", bus_id="B1", p_gen=1.0)])
            >>> system.assign_default_reactances()
            1
            >>> system.generators[0].xdpp_pu
            0.2
        """
        if xdpp_pu <= 0:
            raise ValueError(
                f"xdpp_pu must be positive, got {xdpp_pu}. A zero or negative "
                "reactance makes the machine an infinite source."
            )

        assigned = 0
        for gen in self.generators:
            if overwrite or gen.xdpp_pu is None:
                gen.xdpp_pu = xdpp_pu
                assigned += 1

        if assigned:
            self._record_assumption(
                f"Machine reactances: {assigned} generator(s) assigned Xd''={xdpp_pu} pu, "
                f"not from real machine data. Fault levels depend on this assumption."
            )
        return assigned

    def _record_assumption(self, note: str) -> None:
        """Remember an invented-data decision for to_llm_context()/to_description().

        Kept off the dataclass fields on purpose: the JSON writer serialises
        fields(), so a new field would change the on-disk schema and the
        round-trip. Assumptions describe an in-memory analysis session, not the
        network, so they are intentionally not persisted. Writing this system to
        a file bakes the invented values in and drops this note with it.
        """
        if not hasattr(self, "_assumptions"):
            self._assumptions: list[str] = []
        self._assumptions.append(note)

    @property
    def assumptions(self) -> list[str]:
        """Invented-data decisions applied to this system, newest last.

        Empty unless assign_default_ratings() or assign_default_reactances()
        was called. Not persisted by the writers.

        Example:
            >>> from psforge_grid.models import System, Generator
            >>> system = System(generators=[Generator("G1", bus_id="B1", p_gen=1.0)])
            >>> system.assumptions
            []
            >>> _ = system.assign_default_reactances()
            >>> len(system.assumptions)
            1
        """
        return list(getattr(self, "_assumptions", []))

    # =========================================================================
    # Count properties
    # =========================================================================

    @property
    def num_buses(self) -> int:
        """Number of buses in the system.

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> system = System(buses=[Bus("B1", bus_type=3), Bus("B2", bus_type=1)])
            >>> system.num_buses
            2
        """
        return len(self.buses)

    @property
    def num_branches(self) -> int:
        """Number of branches (lines and transformers) in the system.

        Example:
            >>> from psforge_grid.models import System, Branch
            >>> system = System(branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1)])
            >>> system.num_branches
            1
        """
        return len(self.branches)

    @property
    def num_generators(self) -> int:
        """Number of generators in the system.

        Example:
            >>> from psforge_grid.models import System, Generator
            >>> system = System(generators=[Generator("G1", bus_id="B1", p_gen=1.0)])
            >>> system.num_generators
            1
        """
        return len(self.generators)

    @property
    def num_loads(self) -> int:
        """Number of loads in the system.

        Example:
            >>> from psforge_grid.models import System, Load
            >>> system = System(loads=[Load("LD1", bus_id="B2", p_load=0.8, q_load=0.2)])
            >>> system.num_loads
            1
        """
        return len(self.loads)

    @property
    def num_shunts(self) -> int:
        """Number of shunt devices (capacitors and reactors) in the system.

        Example:
            >>> from psforge_grid.models import System, Shunt
            >>> system = System(shunts=[Shunt("SH1", bus_id="B3", b_pu=0.19)])
            >>> system.num_shunts
            1
        """
        return len(self.shunts)

    @property
    def num_generator_costs(self) -> int:
        """Number of generator cost functions in the system.

        Example:
            >>> from psforge_grid.models import System, GeneratorCost
            >>> system = System(generator_costs=[GeneratorCost("GC1", generator_id="G1", model=2)])
            >>> system.num_generator_costs
            1
        """
        return len(self.generator_costs)

    # =========================================================================
    # Bus lookup methods
    # =========================================================================

    def get_bus(self, bus_id: str) -> Bus | None:
        """Get a bus by its id.

        Args:
            bus_id: ``Bus.id`` to search for

        Returns:
            Bus object if found, None otherwise

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> system = System(buses=[Bus("B1", bus_type=3), Bus("B2", bus_type=1, base_kv=230.0)])
            >>> system.get_bus("B2").base_kv
            230.0
            >>> system.get_bus("B99") is None  # missing bus returns None
            True
        """
        for bus in self.buses:
            if bus.id == bus_id:
                return bus
        return None

    def get_bus_index(self, bus_id: str) -> int:
        """Get the index of a bus in the buses list.

        Args:
            bus_id: ``Bus.id`` to search for

        Returns:
            Index in buses list (0-based)

        Raises:
            ValueError: If the bus id is not found

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> system = System(buses=[Bus("B1", bus_type=3), Bus("B2", bus_type=1)])
            >>> system.get_bus_index("B2")  # bus "B2" is at list index 1
            1
        """
        for i, bus in enumerate(self.buses):
            if bus.id == bus_id:
                return i
        raise ValueError(f"Bus {bus_id!r} not found in system")

    def get_bus_ids(self) -> list[str]:
        """Get all bus ids in the system.

        Returns:
            List of bus ids

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> system = System(buses=[Bus("B1", bus_type=3), Bus("B4", bus_type=1)])
            >>> system.get_bus_ids()
            ['B1', 'B4']
        """
        return [bus.id for bus in self.buses]

    def used_ids(self) -> set[str]:
        """Get every element id used in this system, all element types combined.

        The unified identity contract makes ids unique across the whole
        system; this is the set the uniqueness checks and id generators
        test against.

        Returns:
            Set of all element ids (buses, branches, generators, loads,
            shunts, generator costs). The System's own ``id`` is a case
            identifier, not an element id, and is not included.

        Example:
            >>> from psforge_grid.models import System, Bus, Generator
            >>> system = System(
            ...     buses=[Bus("B1", bus_type=3)],
            ...     generators=[Generator("G1_1", bus_id="B1", p_gen=1.0)],
            ... )
            >>> sorted(system.used_ids())
            ['B1', 'G1_1']
        """
        ids: set[str] = set()
        for group in (
            self.buses,
            self.branches,
            self.generators,
            self.loads,
            self.shunts,
            self.generator_costs,
        ):
            ids.update(e.id for e in group)
        return ids

    def get_element(
        self, element_id: str
    ) -> Bus | Branch | Generator | Load | Shunt | GeneratorCost | None:
        """Get any element by its id, searching across all element types.

        Because ids are unique system-wide, an id alone identifies the
        element without knowing its type.

        Args:
            element_id: Element id to search for

        Returns:
            The matching element, or None if no element has this id.

        Example:
            >>> from psforge_grid.models import System, Bus, Generator
            >>> system = System(
            ...     buses=[Bus("B1", bus_type=3)],
            ...     generators=[Generator("G1_1", bus_id="B1", p_gen=1.0)],
            ... )
            >>> system.get_element("G1_1").p_gen
            1.0
            >>> system.get_element("X99") is None
            True
        """
        for group in (
            self.buses,
            self.branches,
            self.generators,
            self.loads,
            self.shunts,
            self.generator_costs,
        ):
            for element in group:
                if element.id == element_id:
                    return element
        return None

    def assign_ids(self) -> dict[str, str]:
        """Regenerate every element id using the standard deterministic rules.

        Rewrites all element ids from format-provided keys (``Bus.number``,
        ``circuit_id``, ``machine_id``, ...) with the same rules the parsers
        use (``B1``, ``BR1_2_1``, ``G1_1``, ...), and updates every reference
        (``from_bus_id``/``to_bus_id``/``bus_id``/``generator_id`` and
        diagram keys) consistently. Opt-in, like assign_default_ratings():
        renaming identifiers is a decision, not a side effect.

        Elements without a format-provided key fall back to their 1-based
        list position.

        Returns:
            Mapping from old id to new id for every renamed element
            (identity mappings are omitted).

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> system = System(buses=[Bus("node_a", bus_type=3, number=1)])
            >>> system.assign_ids()
            {'node_a': 'B1'}
            >>> system.buses[0].id
            'B1'
        """
        from psforge_grid.models.identity import make_unique, sanitize_id

        mapping: dict[str, str] = {}
        used: set[str] = set()

        def rename(old: str, candidate: str) -> str:
            new = make_unique(candidate, used)
            used.add(new)
            if new != old:
                mapping[old] = new
            return new

        # Buses first: everything else references them.
        bus_key: dict[str, str] = {}  # old bus id -> key used in dependent ids
        for i, bus in enumerate(self.buses):
            key = str(bus.number) if bus.number is not None else str(i + 1)
            bus_key[bus.id] = key
            bus.id = rename(bus.id, f"B{key}")

        per_bus_count: dict[tuple[str, str], int] = {}

        def seq(kind: str, old_bus_id: str) -> str:
            per_bus_count[(kind, old_bus_id)] = per_bus_count.get((kind, old_bus_id), 0) + 1
            return str(per_bus_count[(kind, old_bus_id)])

        for branch in self.branches:
            fk = bus_key.get(branch.from_bus_id, branch.from_bus_id)
            tk = bus_key.get(branch.to_bus_id, branch.to_bus_id)
            ckt = sanitize_id(branch.circuit_id) if branch.circuit_id is not None else "1"
            branch.id = rename(branch.id, f"BR{fk}_{tk}_{ckt}")

        gen_new_id: dict[str, str] = {}  # old generator id -> new id
        for gen in self.generators:
            bk = bus_key.get(gen.bus_id, gen.bus_id)
            sub = (
                sanitize_id(gen.machine_id)
                if gen.machine_id is not None
                else seq("gen", gen.bus_id)
            )
            old = gen.id
            gen.id = rename(old, f"G{bk}_{sub}")
            gen_new_id[old] = gen.id

        for load in self.loads:
            bk = bus_key.get(load.bus_id, load.bus_id)
            sub = (
                sanitize_id(load.load_id) if load.load_id is not None else seq("load", load.bus_id)
            )
            load.id = rename(load.id, f"LD{bk}_{sub}")

        for shunt in self.shunts:
            bk = bus_key.get(shunt.bus_id, shunt.bus_id)
            sub = (
                sanitize_id(shunt.shunt_id)
                if shunt.shunt_id is not None
                else seq("shunt", shunt.bus_id)
            )
            shunt.id = rename(shunt.id, f"SH{bk}_{sub}")

        for cost in self.generator_costs:
            new_gen = gen_new_id.get(cost.generator_id, cost.generator_id)
            cost.id = rename(cost.id, f"GC_{new_gen}")

        # Rewrite references and diagram keys.
        for branch in self.branches:
            branch.from_bus_id = mapping.get(branch.from_bus_id, branch.from_bus_id)
            branch.to_bus_id = mapping.get(branch.to_bus_id, branch.to_bus_id)
        for gen in self.generators:
            gen.bus_id = mapping.get(gen.bus_id, gen.bus_id)
        for load in self.loads:
            load.bus_id = mapping.get(load.bus_id, load.bus_id)
        for shunt in self.shunts:
            shunt.bus_id = mapping.get(shunt.bus_id, shunt.bus_id)
        for cost in self.generator_costs:
            cost.generator_id = mapping.get(cost.generator_id, cost.generator_id)
        for diagram in (self.diagram_schematic, self.diagram_geographic):
            if diagram is None:
                continue
            diagram.bus_positions = {mapping.get(k, k): v for k, v in diagram.bus_positions.items()}
            diagram.branch_routes = {mapping.get(k, k): v for k, v in diagram.branch_routes.items()}
            for label in diagram.labels:
                label.element_id = mapping.get(label.element_id, label.element_id)

        return mapping

    # =========================================================================
    # Component lookup by bus
    # =========================================================================

    def get_bus_generators(self, bus_id: str, in_service_only: bool = True) -> list[Generator]:
        """Get all generators connected to a specific bus.

        Args:
            bus_id: ``Bus.id`` to search for
            in_service_only: If True, return only in-service generators

        Returns:
            List of Generator objects connected to the bus

        Example:
            >>> from psforge_grid.models import System, Generator
            >>> system = System(generators=[
            ...     Generator("G1_1", bus_id="B1", p_gen=1.0),
            ...     Generator("G1_2", bus_id="B1", p_gen=0.5, status=0),  # out of service
            ... ])
            >>> len(system.get_bus_generators("B1"))
            1
            >>> len(system.get_bus_generators("B1", in_service_only=False))
            2
        """
        gens = [g for g in self.generators if g.bus_id == bus_id]
        if in_service_only:
            gens = [g for g in gens if g.is_in_service]
        return gens

    def get_bus_loads(self, bus_id: str, in_service_only: bool = True) -> list[Load]:
        """Get all loads connected to a specific bus.

        Args:
            bus_id: ``Bus.id`` to search for
            in_service_only: If True, return only in-service loads

        Returns:
            List of Load objects connected to the bus

        Example:
            >>> from psforge_grid.models import System, Load
            >>> system = System(loads=[Load("LD2_1", bus_id="B2", p_load=0.8, q_load=0.2)])
            >>> system.get_bus_loads("B2")[0].p_load
            0.8
            >>> system.get_bus_loads("B3")  # no loads at bus B3
            []
        """
        loads = [load for load in self.loads if load.bus_id == bus_id]
        if in_service_only:
            loads = [load for load in loads if load.is_in_service]
        return loads

    def get_bus_shunts(self, bus_id: str, in_service_only: bool = True) -> list[Shunt]:
        """Get all shunts connected to a specific bus.

        Args:
            bus_id: ``Bus.id`` to search for
            in_service_only: If True, return only in-service shunts

        Returns:
            List of Shunt objects connected to the bus

        Example:
            >>> from psforge_grid.models import System, Shunt
            >>> system = System(shunts=[
            ...     Shunt("SH3_1", bus_id="B3", b_pu=0.19),
            ...     Shunt("SH3_2", bus_id="B3", b_pu=-0.2, status=0),  # out of service
            ... ])
            >>> len(system.get_bus_shunts("B3"))
            1
            >>> len(system.get_bus_shunts("B3", in_service_only=False))
            2
        """
        shunts = [s for s in self.shunts if s.bus_id == bus_id]
        if in_service_only:
            shunts = [s for s in shunts if s.status == 1]
        return shunts

    def get_branches_at_bus(self, bus_id: str, in_service_only: bool = True) -> list[Branch]:
        """Get all branches connected to a specific bus.

        Args:
            bus_id: ``Bus.id`` to search for
            in_service_only: If True, return only in-service branches

        Returns:
            List of Branch objects connected to the bus (either terminal)

        Example:
            >>> from psforge_grid.models import System, Branch
            >>> system = System(branches=[
            ...     Branch("BR1_2_1", "B1", "B2", r_pu=0.01, x_pu=0.1),
            ...     Branch("BR2_3_1", "B2", "B3", r_pu=0.02, x_pu=0.2),
            ... ])
            >>> len(system.get_branches_at_bus("B2"))  # matches either terminal
            2
            >>> len(system.get_branches_at_bus("B1"))
            1
        """
        branches = [b for b in self.branches if bus_id in (b.from_bus_id, b.to_bus_id)]
        if in_service_only:
            branches = [b for b in branches if b.is_in_service]
        return branches

    # =========================================================================
    # Power injection calculations
    # =========================================================================

    def get_bus_p_injection(self, bus_id: str) -> float:
        """Calculate net active power injection at a bus [p.u.].

        P_injection = sum(P_gen) - sum(P_load)

        Args:
            bus_id: ``Bus.id``

        Returns:
            Net active power injection (generation - load) [p.u.]

        Example:
            >>> from psforge_grid.models import System, Generator, Load
            >>> system = System(
            ...     generators=[Generator("G1", bus_id="B1", p_gen=1.0)],
            ...     loads=[Load("LD1", bus_id="B1", p_load=0.25)],
            ... )
            >>> system.get_bus_p_injection("B1")  # 1.0 generated - 0.25 consumed
            0.75
        """
        p_gen = sum(g.p_gen for g in self.get_bus_generators(bus_id))
        p_load = sum(load.p_load for load in self.get_bus_loads(bus_id))
        return p_gen - p_load

    def get_bus_q_injection(self, bus_id: str) -> float:
        """Calculate net reactive power injection at a bus [p.u.].

        Q_injection = sum(Q_gen) - sum(Q_load)

        Note:
            Shunts are NOT included. Their contribution is voltage-dependent
            (V^2 * B_shunt) and this method has no voltage solution to apply,
            so it would have to assume a nominal V = 1.0. Use
            get_bus_shunt_admittance() and combine it with a solved voltage if
            you need the shunt term.

        Args:
            bus_id: ``Bus.id``

        Returns:
            Net reactive power injection [p.u.], excluding shunts

        Example:
            >>> from psforge_grid.models import System, Generator, Load
            >>> system = System(
            ...     generators=[Generator("G1", bus_id="B1", p_gen=1.0, q_gen=0.5)],
            ...     loads=[Load("LD1", bus_id="B1", p_load=0.25, q_load=0.25)],
            ... )
            >>> system.get_bus_q_injection("B1")  # 0.5 generated - 0.25 consumed
            0.25
        """
        q_gen = sum(g.q_gen for g in self.get_bus_generators(bus_id))
        q_load = sum(load.q_load for load in self.get_bus_loads(bus_id))
        return q_gen - q_load

    def get_bus_shunt_admittance(self, bus_id: str) -> tuple[float, float]:
        """Get total shunt admittance at a bus.

        Args:
            bus_id: ``Bus.id``

        Returns:
            Tuple of (G_total, B_total) [p.u.]

        Example:
            >>> from psforge_grid.models import System, Shunt
            >>> system = System(shunts=[
            ...     Shunt("SH3_1", bus_id="B3", g_pu=0.5, b_pu=0.25),
            ...     Shunt("SH3_2", bus_id="B3", b_pu=0.25),
            ... ])
            >>> system.get_bus_shunt_admittance("B3")  # summed over both shunts
            (0.5, 0.5)
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

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> system = System(
            ...     buses=[Bus("B1", bus_type=3), Bus("B2", bus_type=2), Bus("B3", bus_type=1)]
            ... )
            >>> [bus.id for bus in system.get_slack_buses()]
            ['B1']
        """
        return [bus for bus in self.buses if bus.is_slack]

    def get_pv_buses(self) -> list[Bus]:
        """Get all PV (generator) buses in the system.

        Returns:
            List of Bus objects with bus_type == 2

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> system = System(
            ...     buses=[Bus("B1", bus_type=3), Bus("B2", bus_type=2), Bus("B3", bus_type=1)]
            ... )
            >>> [bus.id for bus in system.get_pv_buses()]
            ['B2']
        """
        return [bus for bus in self.buses if bus.is_pv]

    def get_pq_buses(self) -> list[Bus]:
        """Get all PQ (load) buses in the system.

        Returns:
            List of Bus objects with bus_type == 1

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> system = System(
            ...     buses=[Bus("B1", bus_type=3), Bus("B2", bus_type=2), Bus("B3", bus_type=1)]
            ... )
            >>> [bus.id for bus in system.get_pq_buses()]
            ['B3']
        """
        return [bus for bus in self.buses if bus.is_pq]

    def get_in_service_branches(self) -> list[Branch]:
        """Get all in-service branches.

        Returns:
            List of Branch objects with status == 1

        Example:
            >>> from psforge_grid.models import System, Branch
            >>> system = System(branches=[
            ...     Branch("BR1_2_1", "B1", "B2", r_pu=0.01, x_pu=0.1),
            ...     Branch("BR2_3_1", "B2", "B3", r_pu=0.02, x_pu=0.2, status=0),  # out of service
            ... ])
            >>> len(system.get_in_service_branches())
            1
        """
        return [b for b in self.branches if b.is_in_service]

    def total_generation(self, in_service_only: bool = True) -> tuple[float, float]:
        """Calculate total system generation.

        Args:
            in_service_only: If True, count only in-service generators

        Returns:
            Tuple of (total_P, total_Q) [p.u.]

        Example:
            >>> from psforge_grid.models import System, Generator
            >>> system = System(generators=[
            ...     Generator("G1", bus_id="B1", p_gen=1.0, q_gen=0.25),
            ...     Generator("G2", bus_id="B2", p_gen=0.5, q_gen=0.25, status=0),  # out of service
            ... ])
            >>> system.total_generation()
            (1.0, 0.25)
            >>> system.total_generation(in_service_only=False)
            (1.5, 0.5)
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

        Example:
            >>> from psforge_grid.models import System, Load
            >>> system = System(loads=[
            ...     Load("LD2", bus_id="B2", p_load=0.8, q_load=0.25),
            ...     Load("LD3", bus_id="B3", p_load=0.5, q_load=0.25, status=0),  # out of service
            ... ])
            >>> system.total_load()
            (0.8, 0.25)
            >>> system.total_load(in_service_only=False)
            (1.3, 0.5)
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
        ]

        if self.case_time:
            lines.append(f"  Case time: {self.case_time}")

        lines += [
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

        for note in self.assumptions:
            lines.append(f"  ASSUMPTION: {note}")

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
            lines.append(f"- Slack: {len(slack)} ({', '.join(b.id for b in slack)})")
            lines.append(f"- PV: {len(pv)}")
            lines.append(f"- PQ: {len(pq)}")

        # Anything reading this context to interpret results has to be told when
        # the inputs were invented, otherwise it will report assumed numbers as
        # measured ones.
        if self.assumptions:
            lines.append("")
            lines.append("### Data Assumptions:")
            lines.append("Some inputs were not in the source data and were assigned defaults.")
            lines.append("Results that depend on them are only as good as these assumptions.")
            for note in self.assumptions:
                lines.append(f"- {note}")

        missing = self.check_data_completeness()
        if missing:
            lines.append("")
            lines.append("### Missing Data:")
            for issue in missing:
                lines.append(f"- {issue['message']}")

        return "\n".join(lines)

    def get_all_descriptions(self) -> str:
        """Get descriptions of all components with custom notes.

        Returns only components that have a description field set.

        Returns:
            Multi-line string with all component descriptions

        Example:
            >>> from psforge_grid.models import System, Bus
            >>> system = System(buses=[
            ...     Bus("B1", bus_type=3, name="Main", description="Utility interconnection"),
            ...     Bus("B2", bus_type=1),  # no description -> omitted
            ... ])
            >>> print(system.get_all_descriptions())
            Bus B1 (Main): Utility interconnection
        """
        lines = []

        if self.description:
            lines.append(f"System: {self.description}")

        for bus in self.buses:
            if bus.description:
                name = bus.name or f"Bus {bus.id}"
                lines.append(f"Bus {bus.id} ({name}): {bus.description}")

        for branch in self.branches:
            if branch.description:
                name = branch.name or f"{branch.from_bus_id}-{branch.to_bus_id}"
                lines.append(f"Branch {branch.id} ({name}): {branch.description}")

        for gen in self.generators:
            if gen.description:
                name = gen.name or f"at Bus {gen.bus_id}"
                lines.append(f"Generator {gen.id} ({name}): {gen.description}")

        for load in self.loads:
            if load.description:
                name = load.name or f"at Bus {load.bus_id}"
                lines.append(f"Load {load.id} ({name}): {load.description}")

        for shunt in self.shunts:
            if shunt.description:
                name = shunt.name or f"at Bus {shunt.bus_id}"
                lines.append(f"Shunt {shunt.id} ({name}): {shunt.description}")

        return "\n".join(lines) if lines else "No descriptions available."
