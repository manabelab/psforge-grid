"""PSS/E RAW file parser.

This module provides functionality to parse PSS/E RAW format files (v33/v34)
and convert them to psforge System objects.

Supported Formats:
    - PSS/E v33: Bus data starts immediately after 3-line case ID header
    - PSS/E v34: Uses explicit "BEGIN XXX DATA" section markers

Test Data Sources:
    - IEEE 9-bus (v34): https://github.com/todstewart1001/PSSE-24-Hour-Load-Dispatch-IEEE-9-Bus-System-
    - IEEE 14-bus (v33): https://github.com/ITI/models/blob/master/electric-grid/physical/reference/ieee-14bus/

References:
    - IEEE Test Systems: https://icseg.iti.illinois.edu/power-cases/
    - Texas A&M Repository: https://electricgrids.engr.tamu.edu/electric-grid-test-cases/
"""

from __future__ import annotations

import math
from pathlib import Path

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt
from psforge_grid.models.system import System


def parse_raw(filepath: str | Path) -> System:
    """Parse PSS/E RAW file and return a System object.

    Reads a PSS/E RAW format file (v33 or v34) and constructs a complete
    System object with buses, branches, generators, loads, and shunts.

    Args:
        filepath: Path to .raw file

    Returns:
        System object containing parsed power system data

    Raises:
        FileNotFoundError: If the specified file does not exist
        ValueError: If the file format is invalid or cannot be parsed

    Note:
        - Supports both v33 and v34 PSS/E RAW formats
        - v33: Bus data starts immediately after 3-line case ID
        - v34: Uses explicit "BEGIN XXX DATA" section markers
        - Comments (lines starting with '@') are ignored
        - Empty lines and whitespace are handled automatically
        - Section markers ('0 /' or 'Q') denote end of data sections
        - Power values (MW, MVAr) are converted to per-unit on system base MVA
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

    # Parse LOAD DATA section
    if "LOAD_DATA" in sections:
        system.loads = _parse_load_data(sections["LOAD_DATA"], system.base_mva)

    # Parse FIXED SHUNT DATA section
    if "FIXED_SHUNT_DATA" in sections:
        system.shunts = _parse_fixed_shunt_data(sections["FIXED_SHUNT_DATA"], system.base_mva)

    # Parse GENERATOR DATA section
    if "GENERATOR_DATA" in sections:
        system.generators = _parse_generator_data(sections["GENERATOR_DATA"], system.base_mva)

    # Parse BRANCH DATA section
    if "BRANCH_DATA" in sections:
        system.branches = _parse_branch_data(sections["BRANCH_DATA"])

    # Parse TRANSFORMER DATA section (v34 format)
    if "TRANSFORMER_DATA" in sections:
        transformer_branches = _parse_transformer_data(sections["TRANSFORMER_DATA"])
        system.branches.extend(transformer_branches)

    return system


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Split RAW file into sections.

    Identifies section boundaries and groups lines by section type.

    Args:
        lines: All lines from the RAW file

    Returns:
        Dictionary mapping section names to their content lines
    """
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    # Track if we've seen the case ID (first 3 lines)
    case_id_lines: list[str] = []
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
                # In v33 format, bus data starts immediately after case ID
                # (no explicit "BEGIN BUS DATA" marker)
                current_section = "BUS_DATA"
            continue

        # Section end markers (but check for next section on same line - v34 format)
        # v34 format: "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA"
        if line.startswith("0 /") or line.startswith("Q") or line == "0":
            if current_section:
                sections[current_section] = current_lines
                current_lines = []
            current_section = None
            # Don't continue - check if this line also contains a section start marker

        # Section start markers (check for various patterns)
        line_upper = line.upper()
        if "BEGIN BUS DATA" in line_upper:
            current_section = "BUS_DATA"
            continue
        elif "BEGIN LOAD DATA" in line_upper:
            current_section = "LOAD_DATA"
            continue
        elif "BEGIN FIXED SHUNT DATA" in line_upper:
            current_section = "FIXED_SHUNT_DATA"
            continue
        elif "BEGIN GENERATOR DATA" in line_upper:
            current_section = "GENERATOR_DATA"
            continue
        elif "BEGIN BRANCH DATA" in line_upper:
            current_section = "BRANCH_DATA"
            continue
        elif "BEGIN TRANSFORMER DATA" in line_upper:
            current_section = "TRANSFORMER_DATA"
            continue

        # If we hit an end marker without a new section start, skip the line
        if line.startswith("0 /") or line.startswith("Q") or line == "0":
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
            # I, 'NAME', BASKV, IDE, AREA, ZONE, OWNER, VM, VA, NVHI, NVLO, EVHI, EVLO
            # I: Bus number
            # NAME: Bus name
            # BASKV: Base voltage (kV)
            # IDE: Bus type (1=PQ, 2=PV, 3=Slack, 4=Isolated)
            # AREA: Area number
            # ZONE: Zone number
            # VM: Voltage magnitude (p.u.)
            # VA: Voltage angle (degrees)
            # NVHI, NVLO: Normal voltage limits
            # EVHI, EVLO: Emergency voltage limits

            bus_id = int(fields[0])
            name = fields[1] if len(fields) > 1 else None
            base_kv = float(fields[2]) if len(fields) > 2 else 1.0
            bus_type = int(fields[3]) if len(fields) > 3 else 1
            area = int(fields[4]) if len(fields) > 4 else 1
            zone = int(fields[5]) if len(fields) > 5 else 1

            # Initial voltage values (may be overwritten by power flow)
            v_magnitude = float(fields[7]) if len(fields) > 7 else 1.0
            v_angle_deg = float(fields[8]) if len(fields) > 8 else 0.0
            v_angle = v_angle_deg * math.pi / 180.0  # Convert to radians

            # Voltage limits (use normal limits if available)
            v_max = float(fields[9]) if len(fields) > 9 else 1.1
            v_min = float(fields[10]) if len(fields) > 10 else 0.9

            bus = Bus(
                bus_id=bus_id,
                bus_type=bus_type,
                base_kv=base_kv,
                v_magnitude=v_magnitude,
                v_angle=v_angle,
                area=area,
                zone=zone,
                v_max=v_max,
                v_min=v_min,
                name=name,
            )
            buses.append(bus)

        except (IndexError, ValueError):
            # Skip malformed lines
            continue

    return buses


def _parse_load_data(lines: list[str], base_mva: float) -> list[Load]:
    """Parse LOAD DATA section.

    Args:
        lines: Lines from LOAD_DATA section
        base_mva: System base MVA for per-unit conversion

    Returns:
        List of Load objects
    """
    loads = []

    for line in lines:
        if not line or line.startswith("0"):
            continue

        try:
            fields = [f.strip().strip("'\"") for f in line.split(",")]

            # PSS/E v33 Load Data Format:
            # I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER, SCALE, INTRPT
            # I: Bus number
            # ID: Load ID
            # STATUS: Status (1=in-service, 0=out-of-service)
            # PL: Active power (MW)
            # QL: Reactive power (MVAr)

            bus_id = int(fields[0])
            load_id = fields[1] if len(fields) > 1 else "1"
            status = int(fields[2]) if len(fields) > 2 else 1

            # Power values (in MW/MVAr, convert to p.u.)
            p_load_mw = float(fields[5]) if len(fields) > 5 else 0.0
            q_load_mvar = float(fields[6]) if len(fields) > 6 else 0.0

            p_load = p_load_mw / base_mva
            q_load = q_load_mvar / base_mva

            load = Load(
                bus_id=bus_id,
                p_load=p_load,
                q_load=q_load,
                status=status,
                load_id=load_id,
            )
            loads.append(load)

        except (IndexError, ValueError):
            continue

    return loads


def _parse_fixed_shunt_data(lines: list[str], base_mva: float) -> list[Shunt]:
    """Parse FIXED SHUNT DATA section.

    Args:
        lines: Lines from FIXED_SHUNT_DATA section
        base_mva: System base MVA for per-unit conversion

    Returns:
        List of Shunt objects
    """
    shunts = []

    for line in lines:
        if not line or line.startswith("0"):
            continue

        try:
            fields = [f.strip().strip("'\"") for f in line.split(",")]

            # PSS/E v33 Fixed Shunt Data Format:
            # I, ID, STATUS, GL, BL
            # I: Bus number
            # ID: Shunt ID
            # STATUS: Status (1=in-service, 0=out-of-service)
            # GL: Shunt conductance (MW at 1.0 p.u. voltage)
            # BL: Shunt susceptance (MVAr at 1.0 p.u. voltage)

            bus_id = int(fields[0])
            shunt_id = fields[1] if len(fields) > 1 else "1"
            status = int(fields[2]) if len(fields) > 2 else 1

            # G, B values (in MW/MVAr, convert to p.u.)
            g_mw = float(fields[3]) if len(fields) > 3 else 0.0
            b_mvar = float(fields[4]) if len(fields) > 4 else 0.0

            g_pu = g_mw / base_mva
            b_pu = b_mvar / base_mva

            shunt = Shunt(
                bus_id=bus_id,
                g_pu=g_pu,
                b_pu=b_pu,
                status=status,
                shunt_id=shunt_id,
            )
            shunts.append(shunt)

        except (IndexError, ValueError):
            continue

    return shunts


def _parse_generator_data(lines: list[str], base_mva: float) -> list[Generator]:
    """Parse GENERATOR DATA section.

    Args:
        lines: Lines from GENERATOR_DATA section
        base_mva: System base MVA for per-unit conversion

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
            # I, ID, PG, QG, QT, QB, VS, IREG, MBASE, ZR, ZX, RT, XT, GTAP, STAT, ...
            # I: Bus number
            # ID: Generator ID
            # PG: Active power output (MW)
            # QG: Reactive power output (MVAr)
            # QT: Maximum reactive power (MVAr)
            # QB: Minimum reactive power (MVAr)
            # VS: Voltage setpoint (p.u.)
            # MBASE: Machine base MVA
            # STAT: Status (1=in-service, 0=out-of-service)

            bus_id = int(fields[0])
            gen_id = fields[1] if len(fields) > 1 else "1"

            # Power values (in MW/MVAr, convert to p.u.)
            p_gen_mw = float(fields[2]) if len(fields) > 2 else 0.0
            q_gen_mvar = float(fields[3]) if len(fields) > 3 else 0.0
            q_max_mvar = float(fields[4]) if len(fields) > 4 else None
            q_min_mvar = float(fields[5]) if len(fields) > 5 else None

            p_gen = p_gen_mw / base_mva
            q_gen = q_gen_mvar / base_mva
            q_max = q_max_mvar / base_mva if q_max_mvar is not None else None
            q_min = q_min_mvar / base_mva if q_min_mvar is not None else None

            v_setpoint = float(fields[6]) if len(fields) > 6 else 1.0
            mbase = float(fields[8]) if len(fields) > 8 else base_mva

            # Status is at position 14 (0-indexed)
            status = int(fields[14]) if len(fields) > 14 else 1

            generator = Generator(
                bus_id=bus_id,
                p_gen=p_gen,
                q_gen=q_gen,
                v_setpoint=v_setpoint,
                q_max=q_max,
                q_min=q_min,
                mbase=mbase,
                status=status,
                gen_id=gen_id,
            )
            generators.append(generator)

        except (IndexError, ValueError):
            continue

    return generators


def _parse_branch_data(lines: list[str]) -> list[Branch]:
    """Parse BRANCH DATA section.

    Supports both v33 and v34 formats.

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

            # Common fields for both v33 and v34
            from_bus = int(fields[0])
            to_bus = int(fields[1])
            circuit_id = fields[2] if len(fields) > 2 else "1"
            r_pu = float(fields[3]) if len(fields) > 3 else 0.0
            x_pu = float(fields[4]) if len(fields) > 4 else 0.0
            b_pu = float(fields[5]) if len(fields) > 5 else 0.0

            # Detect v34 format: field[6] is NAME (string), not RATEA (number)
            # v34: I, J, CKT, R, X, B, NAME, RATE1-12, GI, BI, GJ, BJ, STAT, MET, LEN
            # v33: I, J, CKT, R, X, B, RATEA, RATEB, RATEC, GI, BI, GJ, BJ, ST, MET, LEN
            is_v34 = False
            if len(fields) > 6:
                try:
                    float(fields[6])
                except ValueError:
                    is_v34 = True

            rate_a = None
            rate_b = None
            rate_c = None
            status = 1

            if is_v34:
                # v34 format: RATE1 at field[7], RATE2 at field[8], RATE3 at field[9]
                # STAT at field[23]
                if len(fields) > 7:
                    rate_val = float(fields[7])
                    if rate_val > 0:
                        rate_a = rate_val
                if len(fields) > 8:
                    rate_val = float(fields[8])
                    if rate_val > 0:
                        rate_b = rate_val
                if len(fields) > 9:
                    rate_val = float(fields[9])
                    if rate_val > 0:
                        rate_c = rate_val
                if len(fields) > 23:
                    status = int(fields[23])
            else:
                # v33 format: RATEA at field[6], RATEB at field[7], RATEC at field[8]
                # ST at field[13]
                if len(fields) > 6:
                    rate_val = float(fields[6])
                    if rate_val > 0:
                        rate_a = rate_val
                if len(fields) > 7:
                    rate_val = float(fields[7])
                    if rate_val > 0:
                        rate_b = rate_val
                if len(fields) > 8:
                    rate_val = float(fields[8])
                    if rate_val > 0:
                        rate_c = rate_val
                if len(fields) > 13:
                    status = int(fields[13])

            branch = Branch(
                from_bus=from_bus,
                to_bus=to_bus,
                r_pu=r_pu,
                x_pu=x_pu,
                b_pu=b_pu,
                rate_a=rate_a,
                rate_b=rate_b,
                rate_c=rate_c,
                status=status,
                circuit_id=circuit_id,
            )
            branches.append(branch)

        except (IndexError, ValueError):
            continue

    return branches


def _parse_transformer_data(lines: list[str]) -> list[Branch]:
    """Parse TRANSFORMER DATA section (v34 format).

    In v34, transformer data spans multiple lines per transformer:
    - Line 1: I, J, K, CKT, CW, CZ, CM, MAG1, MAG2, NMETR, NAME, STAT, ...
    - Line 2: R1-2, X1-2, SBASE1-2, ... (impedance data)
    - Line 3: WINDV1, NOMV1, ANG1, RATE1-1, ... (winding 1 data)
    - Line 4: WINDV2, NOMV2, ... (winding 2 data for 2-winding)
    - (Optional Line 5: WINDV3, ... for 3-winding transformers)

    Args:
        lines: Lines from TRANSFORMER_DATA section

    Returns:
        List of Branch objects representing transformers
    """
    branches = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("@"):
            i += 1
            continue

        try:
            # Line 1: Header with I, J, K, CKT, ...
            fields1 = [f.strip().strip("'\"") for f in line.split(",")]

            from_bus = int(fields1[0])
            to_bus = int(fields1[1])
            k_bus = int(fields1[2])  # 0 for 2-winding, non-zero for 3-winding
            circuit_id = fields1[3] if len(fields1) > 3 else "1"

            # STAT is typically at position 11 in v34
            status = 1
            if len(fields1) > 11:
                try:
                    status = int(fields1[11])
                except ValueError:
                    pass

            # Determine number of windings
            is_three_winding = k_bus != 0
            num_data_lines = 5 if is_three_winding else 4

            # Check if we have enough lines
            if i + num_data_lines - 1 >= len(lines):
                break

            # Line 2: Impedance data (R1-2, X1-2, SBASE1-2, ...)
            i += 1
            line2 = lines[i].strip()
            if line2.startswith("@"):
                i += 1
                if i >= len(lines):
                    break
                line2 = lines[i].strip()

            fields2 = [f.strip() for f in line2.split(",")]
            r_pu = float(fields2[0]) if len(fields2) > 0 else 0.0
            x_pu = float(fields2[1]) if len(fields2) > 1 else 0.0

            # Line 3: Winding 1 data (WINDV1, NOMV1, ANG1, RATE1-1, ...)
            i += 1
            line3 = lines[i].strip()
            if line3.startswith("@"):
                i += 1
                if i >= len(lines):
                    break
                line3 = lines[i].strip()

            fields3 = [f.strip() for f in line3.split(",")]
            windv1 = float(fields3[0]) if len(fields3) > 0 else 1.0
            ang1_deg = float(fields3[2]) if len(fields3) > 2 else 0.0
            ang1_rad = ang1_deg * math.pi / 180.0

            # Rate from winding 1 data
            rate_a = None
            if len(fields3) > 3:
                rate_val = float(fields3[3])
                if rate_val > 0:
                    rate_a = rate_val

            # Line 4: Winding 2 data (WINDV2, NOMV2, ...)
            i += 1
            line4 = lines[i].strip()
            if line4.startswith("@"):
                i += 1
                if i >= len(lines):
                    break
                line4 = lines[i].strip()

            fields4 = [f.strip() for f in line4.split(",")]
            windv2 = float(fields4[0]) if len(fields4) > 0 else 1.0

            # Calculate effective tap ratio
            tap_ratio = windv1 / windv2 if windv2 != 0 else windv1

            # Skip winding 3 line for 3-winding transformers
            if is_three_winding:
                i += 1
                line5 = lines[i].strip()
                if line5.startswith("@"):
                    i += 1

            branch = Branch(
                from_bus=from_bus,
                to_bus=to_bus,
                r_pu=r_pu,
                x_pu=x_pu,
                b_pu=0.0,  # Transformers have no line charging
                tap_ratio=tap_ratio,
                shift_angle=ang1_rad,
                rate_a=rate_a,
                status=status,
                circuit_id=circuit_id,
            )
            branches.append(branch)

            i += 1

        except (IndexError, ValueError):
            i += 1
            continue

    return branches
