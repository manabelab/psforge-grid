"""PSS/E RAW file parser.

This module provides functionality to parse PSS/E RAW format files (v33)
and convert them to psforge System objects.
"""

from __future__ import annotations

import math
from pathlib import Path

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.system import System


def parse_raw(filepath: str | Path) -> System:
    """Parse PSS/E RAW file and return a System object.

    Reads a PSS/E RAW format file (version 33 preferred) and constructs
    a complete System object with buses, branches, and generators.

    Args:
        filepath: Path to .raw file

    Returns:
        System object containing parsed power system data

    Raises:
        FileNotFoundError: If the specified file does not exist
        ValueError: If the file format is invalid or cannot be parsed

    Note:
        - PSS/E RAW format varies by version; v33 is the primary target
        - Comments (lines starting with '@') are ignored
        - Empty lines and whitespace are handled automatically
        - Section markers ('0 /' or 'Q') denote end of data sections
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    system = System()

    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        raise ValueError(f"Failed to read file {filepath}: {e}") from e

    # Split file into sections
    sections = _split_sections(lines)

    # Parse CASE IDENTIFICATION section for base MVA
    if "CASE_ID" in sections:
        system.base_mva = _parse_case_id(sections["CASE_ID"])

    # Parse BUS DATA section
    if "BUS_DATA" in sections:
        system.buses = _parse_bus_data(sections["BUS_DATA"])

    # Parse BRANCH DATA section
    if "BRANCH_DATA" in sections:
        system.branches = _parse_branch_data(sections["BRANCH_DATA"])

    # Parse GENERATOR DATA section
    if "GENERATOR_DATA" in sections:
        system.generators = _parse_generator_data(sections["GENERATOR_DATA"])

    return system


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Split RAW file into sections.

    Identifies section boundaries and groups lines by section type.

    Args:
        lines: All lines from the RAW file

    Returns:
        Dictionary mapping section names to their content lines
    """
    sections = {}
    current_section = None
    current_lines = []

    # Track if we've seen the case ID (first 3 lines)
    case_id_lines = []
    line_count = 0

    for line in lines:
        line = line.strip()

        # Skip comments
        if line.startswith("@"):
            continue

        # Handle case identification (first 3 lines)
        if line_count < 3 and current_section is None:
            case_id_lines.append(line)
            line_count += 1
            if line_count == 3:
                sections["CASE_ID"] = case_id_lines
            continue

        # Section end markers
        if line.startswith("0 /") or line.startswith("Q") or line == "0":
            if current_section:
                sections[current_section] = current_lines
                current_lines = []
            current_section = None
            continue

        # Section start markers
        line_upper = line.upper()
        if "BUS DATA" in line_upper or "BEGIN BUS DATA" in line_upper:
            current_section = "BUS_DATA"
            continue
        elif "BRANCH DATA" in line_upper or "BEGIN BRANCH DATA" in line_upper:
            current_section = "BRANCH_DATA"
            continue
        elif "GENERATOR DATA" in line_upper or "BEGIN GENERATOR DATA" in line_upper:
            current_section = "GENERATOR_DATA"
            continue
        elif "LOAD DATA" in line_upper or "BEGIN LOAD DATA" in line_upper:
            current_section = "LOAD_DATA"
            continue

        # Add line to current section
        if current_section and line:
            current_lines.append(line)

    # Save last section if any
    if current_section and current_lines:
        sections[current_section] = current_lines

    return sections


def _parse_case_id(lines: list[str]) -> float:
    """Parse CASE ID section to extract base MVA.

    Args:
        lines: Lines from CASE_ID section (first 3 lines of RAW file)

    Returns:
        Base MVA value (default: 100.0 if not found)
    """
    if not lines:
        return 100.0

    try:
        # First line typically contains IC, SBASE, REV, etc.
        # Format: IC, SBASE, REV, XFRRAT, NXFRAT, BASFRQ
        first_line = lines[0].split(",")
        if len(first_line) >= 2:
            base_mva = float(first_line[1].strip())
            return base_mva
    except (IndexError, ValueError):
        pass

    return 100.0


def _parse_bus_data(lines: list[str]) -> list[Bus]:
    """Parse BUS DATA section.

    Args:
        lines: Lines from BUS_DATA section

    Returns:
        List of Bus objects
    """
    buses = []

    for line in lines:
        if not line or line.startswith("0"):
            continue

        try:
            fields = [f.strip().strip("'\"") for f in line.split(",")]

            # PSS/E v33 Bus Data Format:
            # I, 'NAME', BASKV, IDE, AREA, ZONE, OWNER, VM, VA, ...
            # I: Bus number
            # NAME: Bus name
            # BASKV: Base voltage (kV)
            # IDE: Bus type (1=PQ, 2=PV, 3=Slack, 4=Isolated)
            # VM: Voltage magnitude (p.u.)
            # VA: Voltage angle (degrees)

            bus_id = int(fields[0])
            name = fields[1] if len(fields) > 1 else None
            base_kv = float(fields[2]) if len(fields) > 2 else 1.0
            bus_type = int(fields[3]) if len(fields) > 3 else 1

            # Convert bus_type 4 (isolated) to 1 (PQ)
            if bus_type == 4:
                bus_type = 1

            # Initial voltage values (may be overwritten by power flow)
            v_magnitude = float(fields[7]) if len(fields) > 7 else 1.0
            v_angle_deg = float(fields[8]) if len(fields) > 8 else 0.0
            v_angle = v_angle_deg * math.pi / 180.0  # Convert to radians

            bus = Bus(
                bus_id=bus_id,
                bus_type=bus_type,
                base_kv=base_kv,
                v_magnitude=v_magnitude,
                v_angle=v_angle,
                name=name,
            )
            buses.append(bus)

        except (IndexError, ValueError):
            # Skip malformed lines
            continue

    return buses


def _parse_branch_data(lines: list[str]) -> list[Branch]:
    """Parse BRANCH DATA section.

    Args:
        lines: Lines from BRANCH_DATA section

    Returns:
        List of Branch objects
    """
    branches = []

    for line in lines:
        if not line or line.startswith("0"):
            continue

        try:
            fields = [f.strip().strip("'\"") for f in line.split(",")]

            # PSS/E v33 Branch Data Format:
            # I, J, CKT, R, X, B, RATEA, RATEB, RATEC, ...
            # I: From bus number
            # J: To bus number
            # CKT: Circuit ID
            # R: Resistance (p.u.)
            # X: Reactance (p.u.)
            # B: Total line charging susceptance (p.u.)

            from_bus = int(fields[0])
            to_bus = int(fields[1])
            # ckt = fields[2] if len(fields) > 2 else '1'
            r_pu = float(fields[3]) if len(fields) > 3 else 0.0
            x_pu = float(fields[4]) if len(fields) > 4 else 0.0
            b_pu = float(fields[5]) if len(fields) > 5 else 0.0

            # Rating (MVA)
            rate_mva = None
            if len(fields) > 6:
                rate_val = float(fields[6])
                if rate_val > 0:
                    rate_mva = rate_val

            branch = Branch(
                from_bus=from_bus, to_bus=to_bus, r_pu=r_pu, x_pu=x_pu, b_pu=b_pu, rate_mva=rate_mva
            )
            branches.append(branch)

        except (IndexError, ValueError):
            continue

    return branches


def _parse_generator_data(lines: list[str]) -> list[Generator]:
    """Parse GENERATOR DATA section.

    Args:
        lines: Lines from GENERATOR_DATA section

    Returns:
        List of Generator objects
    """
    generators = []

    for line in lines:
        if not line or line.startswith("0"):
            continue

        try:
            fields = [f.strip().strip("'\"") for f in line.split(",")]

            # PSS/E v33 Generator Data Format:
            # I, ID, PG, QG, QT, QB, VS, IREG, MBASE, ...
            # I: Bus number
            # ID: Generator ID
            # PG: Active power output (MW)
            # QG: Reactive power output (MVAr)
            # VS: Voltage setpoint (p.u.)
            # MBASE: Machine base MVA

            bus_id = int(fields[0])
            # gen_id = fields[1] if len(fields) > 1 else '1'
            p_gen = float(fields[2]) if len(fields) > 2 else 0.0
            q_gen = float(fields[3]) if len(fields) > 3 else 0.0
            # q_max = float(fields[4]) if len(fields) > 4 else None
            # q_min = float(fields[5]) if len(fields) > 5 else None
            v_setpoint = float(fields[6]) if len(fields) > 6 else 1.0

            # TODO: Verify if PG/QG values in RAW file are in MW/MVAr or p.u.
            # If MW/MVAr, conversion to p.u. is needed: p_gen = p_gen_mw / base_mva
            # This will be validated with IEEE test case data in Sprint 1 testing phase

            generator = Generator(bus_id=bus_id, p_gen=p_gen, q_gen=q_gen, v_setpoint=v_setpoint)
            generators.append(generator)

        except (IndexError, ValueError):
            continue

    return generators
