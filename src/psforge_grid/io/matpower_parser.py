"""MATPOWER case file (.m) parser.

This module provides functionality to parse MATPOWER format files (.m)
and convert them to psforge System objects. Supports standard MATPOWER
case files including pglib-opf benchmark cases.

Supported Data Sections:
    - mpc.baseMVA: System base MVA
    - mpc.bus: Bus data (also extracts loads and shunts)
    - mpc.gen: Generator data
    - mpc.branch: Branch data (lines and transformers)
    - mpc.gencost: Generator cost functions

Architecture:
    The module provides two interfaces:
    - MatpowerParser class: Implements IParser interface for factory pattern
    - parse_matpower function: Convenience function for quick usage

    Both use the same parsing logic internally.

References:
    - MATPOWER Manual: https://matpower.org/docs/MATPOWER-manual.pdf
    - pglib-opf: https://github.com/power-grid-lib/pglib-opf

IDE Navigation Tips:
    - Press F12 on MatpowerParser to see this implementation
    - Press Ctrl+F12 (Mac: Cmd+F12) on IParser to see other implementations
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path

from psforge_grid.io.errors import FileFormatError, MalformedRecordError
from psforge_grid.io.parse_report import ParseReportBuilder
from psforge_grid.io.protocols import IParser
from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.generator_cost import GeneratorCost
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt
from psforge_grid.models.system import System


class MatpowerParser(IParser):
    """MATPOWER format parser.

    Parses MATPOWER .m files and constructs System objects.
    This class implements the IParser interface for use with ParserFactory.

    Supported Features:
        - Standard MATPOWER case format (mpc struct)
        - Bus, generator, branch, and gencost sections
        - Automatic extraction of loads and shunts from bus data
        - Per-unit conversion using system base MVA

    See IParser.parse() for full documentation of the parse method.

    Example:
        >>> from psforge_grid.io.matpower_parser import MatpowerParser
        >>> parser = MatpowerParser()
        >>> system = parser.parse("case14.m")
        >>>
        >>> # Or use the convenience function:
        >>> from psforge_grid.io import parse_matpower
        >>> system = parse_matpower("case14.m")
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return ["m"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "MATPOWER"

    def parse(self, filepath: str | Path, *, strict: bool = False) -> System:
        """Parse MATPOWER .m file and return a System object.

        See IParser.parse() for full documentation.
        """
        return _parse_matpower_impl(filepath, strict=strict)


def parse_matpower(filepath: str | Path, *, strict: bool = False) -> System:
    """Parse MATPOWER .m file and return a System object.

    Convenience function for parsing MATPOWER format files. For factory
    pattern usage, see MatpowerParser class or ParserFactory.

    Reads a MATPOWER format file (.m) and constructs a complete System object
    with buses, branches, generators, loads, shunts, and generator costs.

    Args:
        filepath: Path to .m file

    Returns:
        System object containing parsed power system data

    Raises:
        FileNotFoundError: If the specified file does not exist
        ValueError: If the file format is invalid or cannot be parsed

    Note:
        - Load data (Pd, Qd) and shunt data (Gs, Bs) are extracted from bus rows
        - Only non-zero loads and shunts are created as separate objects
        - Power values (MW, MVAr) are converted to per-unit on system base MVA
        - Voltage angles are converted from degrees to radians
        - MATPOWER ratio=0.0 is converted to tap_ratio=1.0 (transmission line)

    See Also:
        - MatpowerParser: Class implementing IParser interface
        - ParserFactory: Factory for creating parsers
        - System.from_matpower(): Alternative factory method
    """
    return _parse_matpower_impl(filepath, strict=strict)


def _parse_matpower_impl(filepath: str | Path, *, strict: bool = False) -> System:
    """Internal implementation of MATPOWER file parsing.

    Args:
        filepath: Path to the .m file.
        strict: Raise instead of skipping when any row cannot be read.

    Returns:
        The parsed System, carrying a ParseReport of anything skipped.

    Raises:
        FileNotFoundError: If the file does not exist.
        FileFormatError: If no bus rows could be read at all.
        MalformedRecordError: If ``strict`` is set and a row was skipped.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    builder = ParseReportBuilder(format="matpower")

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise FileFormatError(f"could not read the file: {e}", filepath=str(filepath)) from e
    if "\ufffd" in content:
        builder.warn("file is not valid UTF-8; undecodable bytes were replaced")

    # Extract base MVA
    base_mva = _extract_base_mva(content)

    # Extract case name
    case_name = _extract_case_name(content)

    # Extract data sections
    sections = _extract_sections(content)

    # Parse bus section (also produces loads and shunts)
    buses: list[Bus] = []
    loads: list[Load] = []
    shunts: list[Shunt] = []
    if "bus" in sections:
        buses, loads, shunts = _parse_bus_section(sections["bus"], base_mva, builder)

    # Parse generator section
    generators: list[Generator] = []
    if "gen" in sections:
        generators = _parse_gen_section(sections["gen"], base_mva, builder)

    # Parse branch section
    branches: list[Branch] = []
    if "branch" in sections:
        branches = _parse_branch_section(sections["branch"], builder)

    # Parse generator cost section
    generator_costs: list[GeneratorCost] = []
    if "gencost" in sections:
        generator_costs = _parse_gencost_section(sections["gencost"], builder)

    builder.record_read(len(buses) + len(generators) + len(branches) + len(generator_costs))
    report = builder.build()

    system = System(
        buses=buses,
        branches=branches,
        generators=generators,
        loads=loads,
        shunts=shunts,
        generator_costs=generator_costs,
        base_mva=base_mva,
        name=case_name or filepath.name,
        parse_report=report,
    )

    if not buses:
        raise FileFormatError(
            f"no bus rows could be read; the file does not look like a MATPOWER case "
            f"({report.records_read} rows read, {report.skipped_count} skipped)",
            filepath=str(filepath),
        )

    if strict and report.skipped:
        first = report.skipped[0]
        raise MalformedRecordError(
            f"{report.skipped_count} row(s) could not be read; first: {first.reason}",
            filepath=str(filepath),
            line_no=first.line_no,
        )

    return system


def _extract_base_mva(content: str) -> float:
    """Extract system base MVA from MATPOWER file content.

    Args:
        content: Full file content as string

    Returns:
        Base MVA value (default: 100.0 if not found)
    """
    match = re.search(r"mpc\.baseMVA\s*=\s*([0-9.]+)", content)
    if match:
        return float(match.group(1))
    return 100.0


def _extract_case_name(content: str) -> str:
    """Extract case name from MATPOWER function declaration.

    Args:
        content: Full file content as string

    Returns:
        Case name string (empty if not found)
    """
    match = re.search(r"function\s+mpc\s*=\s*(\w+)", content)
    if match:
        return match.group(1)
    return ""


def _non_numeric_column(row: list[str], count: int) -> str | None:
    """Return a reason string if any of the first ``count`` columns is not a number.

    MATPOWER data sections are numeric tables, so a column that does not read as
    a number means the row is not the record it claims to be. Checking up front
    keeps the row out of the model instead of letting a conversion raise from
    the middle of building one.

    Args:
        row: Whitespace-separated fields of one row.
        count: How many leading columns must be numeric.

    Returns:
        A reason to skip the row, or ``None`` when every column reads.
    """
    for index, value in enumerate(row[:count]):
        try:
            float(value)
        except ValueError:
            return f"column {index + 1} is not a number: {value!r}"
    return None


def _extract_sections(content: str) -> dict[str, list[tuple[int, list[str]]]]:
    """Extract data sections from MATPOWER file content.

    Finds all `mpc.SECTION = [ ... ];` blocks and extracts the data rows.
    Each row is split into string fields and paired with its 1-based line
    number in the file, so a row that cannot be read can be reported against
    its place in the source.

    Args:
        content: Full file content as string

    Returns:
        Dictionary mapping section names to lists of ``(line_no, fields)``.
    """
    sections: dict[str, list[tuple[int, list[str]]]] = {}

    # Pattern: mpc.section_name = [ ... ];
    # Uses non-greedy matching to find the content between [ and ];
    pattern = re.compile(
        r"mpc\.(\w+)\s*=\s*\[(.*?)\];",
        re.DOTALL,
    )

    for match in pattern.finditer(content):
        section_name = match.group(1)
        block = match.group(2)
        block_first_line = content.count("\n", 0, match.start(2)) + 1

        rows: list[tuple[int, list[str]]] = []
        for offset, line in enumerate(block.split("\n")):
            # Remove comments (% to end of line)
            line = re.sub(r"%.*$", "", line).strip()
            # Remove trailing semicolons within the block
            line = line.rstrip(";").strip()
            if not line:
                continue

            # Split by whitespace or tabs
            fields = line.split()
            if fields:
                rows.append((block_first_line + offset, fields))

        if rows:
            sections[section_name] = rows

    return sections


def _parse_bus_section(
    rows: list[tuple[int, list[str]]], base_mva: float, builder: ParseReportBuilder
) -> tuple[list[Bus], list[Load], list[Shunt]]:
    """Parse MATPOWER bus data section.

    MATPOWER bus format columns (1-indexed):
        1: bus_i    - bus number
        2: type     - bus type (1=PQ, 2=PV, 3=Ref, 4=Isolated)
        3: Pd       - real power demand [MW]
        4: Qd       - reactive power demand [MVAr]
        5: Gs       - shunt conductance [MW at V=1.0 pu]
        6: Bs       - shunt susceptance [MVAr at V=1.0 pu]
        7: area     - area number
        8: Vm       - voltage magnitude [pu]
        9: Va       - voltage angle [degrees]
        10: baseKV  - base voltage [kV]
        11: zone    - loss zone
        12: Vmax    - maximum voltage magnitude [pu]
        13: Vmin    - minimum voltage magnitude [pu]

    Args:
        rows: ``(line_no, fields)`` for each row of the bus section
        base_mva: System base MVA for per-unit conversion
        builder: Report being filled for this parse run

    Returns:
        Tuple of (buses, loads, shunts)
    """
    buses: list[Bus] = []
    loads: list[Load] = []
    shunts: list[Shunt] = []

    for line_no, row in rows:
        if len(row) < 13:
            builder.skip(line_no, "bus", f"expected 13 columns, got {len(row)}", " ".join(row))
            continue
        reason = _non_numeric_column(row, 13)
        if reason is not None:
            builder.skip(line_no, "bus", reason, " ".join(row))
            continue

        bus_id = int(row[0])
        bus_type = int(row[1])
        pd_mw = float(row[2])
        qd_mvar = float(row[3])
        gs_mw = float(row[4])
        bs_mvar = float(row[5])
        area = int(row[6])
        vm = float(row[7])
        va_deg = float(row[8])
        base_kv = float(row[9])
        zone = int(row[10])
        v_max = float(row[11])
        v_min = float(row[12])

        bus = Bus(
            bus_id=bus_id,
            bus_type=bus_type,
            v_magnitude=vm,
            v_angle=math.radians(va_deg),
            base_kv=base_kv,
            area=area,
            zone=zone,
            v_max=v_max,
            v_min=v_min,
        )
        buses.append(bus)

        # Create Load if Pd or Qd is non-zero
        if pd_mw != 0.0 or qd_mvar != 0.0:
            load = Load(
                bus_id=bus_id,
                p_load=pd_mw / base_mva,
                q_load=qd_mvar / base_mva,
            )
            loads.append(load)

        # Create Shunt if Gs or Bs is non-zero
        if gs_mw != 0.0 or bs_mvar != 0.0:
            shunt = Shunt(
                bus_id=bus_id,
                g_pu=gs_mw / base_mva,
                b_pu=bs_mvar / base_mva,
            )
            shunts.append(shunt)

    return buses, loads, shunts


def _parse_gen_section(
    rows: list[tuple[int, list[str]]], base_mva: float, builder: ParseReportBuilder
) -> list[Generator]:
    """Parse MATPOWER generator data section.

    MATPOWER gen format columns (1-indexed):
        1: bus      - bus number
        2: Pg       - real power output [MW]
        3: Qg       - reactive power output [MVAr]
        4: Qmax     - maximum reactive power output [MVAr]
        5: Qmin     - minimum reactive power output [MVAr]
        6: Vg       - voltage magnitude setpoint [pu]
        7: mBase    - total MVA base of machine
        8: status   - machine status (>0 = in-service, <=0 = out-of-service)
        9: Pmax     - maximum real power output [MW]
        10: Pmin    - minimum real power output [MW]

    Args:
        rows: List of field lists from gen section
        base_mva: System base MVA for per-unit conversion

    Returns:
        List of Generator objects
    """
    generators: list[Generator] = []

    # Track gen_id per bus for multiple generators on same bus
    bus_gen_count: dict[int, int] = defaultdict(int)

    for line_no, row in rows:
        if len(row) < 10:
            builder.skip(line_no, "gen", f"expected 10 columns, got {len(row)}", " ".join(row))
            continue
        reason = _non_numeric_column(row, 10)
        if reason is not None:
            builder.skip(line_no, "gen", reason, " ".join(row))
            continue

        bus_id = int(row[0])
        pg_mw = float(row[1])
        qg_mvar = float(row[2])
        qmax_mvar = float(row[3])
        qmin_mvar = float(row[4])
        vg = float(row[5])
        mbase = float(row[6])
        status_raw = int(row[7])
        pmax_mw = float(row[8])
        pmin_mw = float(row[9])

        # MATPOWER status: >0 = in-service, <=0 = out-of-service
        status = 1 if status_raw > 0 else 0

        # Assign gen_id for multiple generators on same bus
        bus_gen_count[bus_id] += 1
        gen_id = str(bus_gen_count[bus_id])

        generator = Generator(
            bus_id=bus_id,
            p_gen=pg_mw / base_mva,
            q_gen=qg_mvar / base_mva,
            v_setpoint=vg,
            p_max=pmax_mw / base_mva,
            p_min=pmin_mw / base_mva,
            q_max=qmax_mvar / base_mva,
            q_min=qmin_mvar / base_mva,
            mbase=mbase,
            status=status,
            gen_id=gen_id,
        )
        generators.append(generator)

    return generators


def _parse_branch_section(
    rows: list[tuple[int, list[str]]], builder: ParseReportBuilder
) -> list[Branch]:
    """Parse MATPOWER branch data section.

    MATPOWER branch format columns (1-indexed):
        1: fbus     - from bus number
        2: tbus     - to bus number
        3: r        - resistance [pu]
        4: x        - reactance [pu]
        5: b        - total line charging susceptance [pu]
        6: rateA    - MVA rating A (long term) [MVA], 0 = unlimited
        7: rateB    - MVA rating B (short term) [MVA], 0 = unlimited
        8: rateC    - MVA rating C (emergency) [MVA], 0 = unlimited
        9: ratio    - transformer off nominal turns ratio, 0 = transmission line
        10: angle   - transformer phase shift angle [degrees]
        11: status  - branch status (1 = in-service, 0 = out-of-service)
        12: angmin  - minimum angle difference [degrees]
        13: angmax  - maximum angle difference [degrees]

    Args:
        rows: List of field lists from branch section

    Returns:
        List of Branch objects
    """
    branches: list[Branch] = []

    for line_no, row in rows:
        if len(row) < 13:
            builder.skip(line_no, "branch", f"expected 13 columns, got {len(row)}", " ".join(row))
            continue
        reason = _non_numeric_column(row, 13)
        if reason is not None:
            builder.skip(line_no, "branch", reason, " ".join(row))
            continue

        from_bus = int(row[0])
        to_bus = int(row[1])
        r_pu = float(row[2])
        x_pu = float(row[3])
        b_pu = float(row[4])
        rate_a_mva = float(row[5])
        rate_b_mva = float(row[6])
        rate_c_mva = float(row[7])
        ratio = float(row[8])
        angle_deg = float(row[9])
        status = int(row[10])
        angmin_deg = float(row[11])
        angmax_deg = float(row[12])

        # MATPOWER convention: ratio=0 means transmission line (tap=1.0)
        tap_ratio = ratio if ratio != 0.0 else 1.0

        # Convert angle from degrees to radians
        shift_angle = math.radians(angle_deg)

        # Convert rates: 0 = unlimited → None
        rate_a = rate_a_mva if rate_a_mva > 0 else None
        rate_b = rate_b_mva if rate_b_mva > 0 else None
        rate_c = rate_c_mva if rate_c_mva > 0 else None

        # Convert angle limits from degrees to radians
        angmin = math.radians(angmin_deg)
        angmax = math.radians(angmax_deg)

        branch = Branch(
            from_bus=from_bus,
            to_bus=to_bus,
            r_pu=r_pu,
            x_pu=x_pu,
            b_pu=b_pu,
            tap_ratio=tap_ratio,
            shift_angle=shift_angle,
            rate_a=rate_a,
            rate_b=rate_b,
            rate_c=rate_c,
            angmin=angmin,
            angmax=angmax,
            status=status,
        )
        branches.append(branch)

    return branches


def _parse_gencost_section(
    rows: list[tuple[int, list[str]]], builder: ParseReportBuilder
) -> list[GeneratorCost]:
    """Parse MATPOWER generator cost data section.

    MATPOWER gencost format columns (1-indexed):
        1: model    - cost model (1=piecewise linear, 2=polynomial)
        2: startup  - startup cost [$]
        3: shutdown - shutdown cost [$]
        4: ncost    - number of cost coefficients/points
        5+: cost    - cost data (model-dependent)

    For polynomial (model=2): c_n, c_{n-1}, ..., c_1, c_0
    For piecewise linear (model=1): x_1, f_1, x_2, f_2, ...

    Args:
        rows: List of field lists from gencost section

    Returns:
        List of GeneratorCost objects (one per generator, indexed by row order)
    """
    costs: list[GeneratorCost] = []

    for gen_index, (line_no, row) in enumerate(rows):
        if len(row) < 4:
            builder.skip(line_no, "gencost", f"expected 4 columns, got {len(row)}", " ".join(row))
            continue
        reason = _non_numeric_column(row, 4)
        if reason is not None:
            builder.skip(line_no, "gencost", reason, " ".join(row))
            continue

        model = int(row[0])
        startup = float(row[1])
        shutdown = float(row[2])
        ncost = int(row[3])

        # Extract cost coefficients/points
        coefficients = [float(x) for x in row[4 : 4 + ncost]]

        cost = GeneratorCost(
            gen_index=gen_index,
            model=model,
            startup=startup,
            shutdown=shutdown,
            coefficients=coefficients,
        )
        costs.append(cost)

    return costs
