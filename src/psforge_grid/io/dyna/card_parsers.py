"""CPAT card format parsers for individual card types.

Each card type (DATA, T, X, N, G1-G5) has a dedicated parser function
that extracts fields from fixed-column Fortran format lines.

Card format reference: R07CPATFree版(データ入出力様式).pdf
    - DATA card: p.85
    - T card (3-1, 3-2): p.86-90  (transmission line)
    - X card (4-1, 4-2, 4-3): p.91-98  (transformer)
    - N card (5-1): p.100  (node)
    - G1-G5 cards (9-1 to 9-5): p.163-167  (generator)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from psforge_grid.io.dyna.format_utils import read_float, read_int, read_str

# =============================================================================
# Parsed data containers
# =============================================================================


@dataclass
class DynaControlData:
    """Parsed DATA card contents."""

    system_name: str = ""
    base_mva: float = 1000.0
    frequency_hz: float = 60.0


@dataclass
class DynaTransmissionLine:
    """Parsed T card (positive + zero-sequence) contents."""

    branch_no: int = 0
    from_node: int = 0
    to_node: int = 0
    has_zero_seq: bool = False
    num_circuits: int = 1
    z1r: float = 0.0
    z1x: float = 0.0
    y1c: float = 0.0
    z0r: float = 0.0
    z0x: float = 0.0
    y0c: float = 0.0
    name: str = ""


@dataclass
class DynaTransformer:
    """Parsed X card (positive + zero-sequence + voltage control) contents."""

    branch_no: int = 0
    from_node: int = 0
    to_node: int = 0
    has_zero_seq: bool = False
    z1r: float = 0.0
    z1x: float = 0.0
    tap_ratio: float = 1.0
    shift_angle: float = 0.0
    z0r: float = 0.0
    z0x: float = 0.0
    name: str = ""


@dataclass
class DynaNode:
    """Parsed N card contents."""

    node_no: int = 0
    v0: float = 0.0
    p_gen: float = 0.0
    q_gen: float = 0.0
    p_load: float = 0.0
    q_load: float = 0.0
    shunt_b: float = 0.0
    v_setpoint: float = 0.0
    name: str = ""


@dataclass
class DynaGenerator:
    """Parsed G1-G5 card set contents."""

    node_no: int = 0
    ngt: int = 0
    lgt: int = 0
    gmva: float = 0.0
    gmw: float = 0.0
    mg: float = 0.0
    plm: float = 0.0
    dg: float = 0.0
    name: str = ""
    # G3 - D-axis constants
    xd: float = 0.0
    xdd: float = 0.0
    xddd: float = 0.0
    tdd: float = 0.0
    tddd: float = 0.0
    tdod: float = 0.0
    tdodd: float = 0.0
    # G4 - Q-axis constants
    xq: float = 0.0
    xqd: float = 0.0
    xqdd: float = 0.0
    tqd: float = 0.0
    tqdd: float = 0.0
    tqod: float = 0.0
    tqodd: float = 0.0
    # G5 - leakage, armature, sequence
    xl: float = 0.0
    ta: float = 0.0
    x0: float = 0.0
    x2: float = 0.0
    ra_type: str = ""  # 'R' = resistance, "'" = time constant


@dataclass
class DynaParsedData:
    """Container for all parsed dyna card data."""

    control: DynaControlData = field(default_factory=DynaControlData)
    transmission_lines: list[DynaTransmissionLine] = field(default_factory=list)
    transformers: list[DynaTransformer] = field(default_factory=list)
    nodes: list[DynaNode] = field(default_factory=list)
    generators: list[DynaGenerator] = field(default_factory=list)


# =============================================================================
# Section terminators
# =============================================================================

_TERMINATORS = {"TEND", "XEND", "NEND", "GEND", "GCON", "GSAT", "DEND", "STOP"}


def is_terminator(line: str) -> str | None:
    """Check if a line is a section terminator.

    Args:
        line: Input line.

    Returns:
        Terminator keyword if found, None otherwise.
    """
    token = line.strip().split()[0].upper() if line.strip() else ""
    if token in _TERMINATORS:
        return token
    return None


# =============================================================================
# DATA card parser
# =============================================================================


def parse_data_card(line: str) -> DynaControlData:
    """Parse DATA card (system name, base MVA, frequency).

    Format (p.85):
        Col 3-10: KEITO (A8) - system name
        Col 11-20: SWVA (F10) - base MVA
        Col 21-30: F (F10) - frequency Hz
        Col 41-80: HEADR (10A4) - header text

    Args:
        line: The DATA card content line (line after 'DATA' keyword).

    Returns:
        Parsed control data.
    """
    ctrl = DynaControlData()
    ctrl.system_name = read_str(line, 3, 10)
    ctrl.base_mva = read_float(line, 11, 20, 1000.0)
    ctrl.frequency_hz = read_float(line, 21, 30, 60.0)
    header = read_str(line, 41, 80)
    if header:
        ctrl.system_name = f"{ctrl.system_name} {header}".strip()
    return ctrl


# =============================================================================
# T card parser (transmission line)
# =============================================================================


def parse_t_card_primary(line: str) -> DynaTransmissionLine:
    """Parse T card primary line (3-1: positive-sequence data).

    Format (p.86):
        Col 1: 'T'
        Col 4-10: NO (I7) - branch number
        Col 12: Z (A1) - zero-sequence flag ('Z' = has zero-seq)
        Col 14-20: NFO (I7) - from node
        Col 24-30: NTO (I7) - to node
        Col 33: L (I1) - number of circuits
        Col 36-45: Z1R (F10) - positive-sequence resistance
        Col 46-55: Z1X (F10) - positive-sequence reactance
        Col 56-65: Y1C (F10) - charging susceptance (Y/2)
        Col 69-80: TNAME (A12) - line name

    Args:
        line: T card primary line.

    Returns:
        Partially populated DynaTransmissionLine.
    """
    tl = DynaTransmissionLine()
    tl.branch_no = read_int(line, 4, 10)
    tl.has_zero_seq = read_str(line, 12, 12) == "Z"
    tl.from_node = read_int(line, 14, 20)
    tl.to_node = read_int(line, 24, 30)
    tl.num_circuits = read_int(line, 33, 33, 1)
    tl.z1r = read_float(line, 36, 45)
    tl.z1x = read_float(line, 46, 55)
    tl.y1c = read_float(line, 56, 65)
    tl.name = read_str(line, 69, 80)
    return tl


def parse_t_card_zero_seq(line: str, tl: DynaTransmissionLine) -> None:
    """Parse T card zero-sequence line (3-2).

    Format (p.87):
        Col 4-10: NMO (I7) - mutual coupling branch (0 = none)
        Col 16-25: ZOR (F10) - zero-sequence resistance
        Col 26-35: ZOX (F10) - zero-sequence reactance
        Col 56-65: YOC (F10) - zero-sequence charging susceptance

    Args:
        line: T card zero-sequence line.
        tl: DynaTransmissionLine to update in place.
    """
    tl.z0r = read_float(line, 16, 25)
    tl.z0x = read_float(line, 26, 35)
    tl.y0c = read_float(line, 56, 65)


# =============================================================================
# X card parser (transformer)
# =============================================================================


def parse_x_card_primary(line: str) -> DynaTransformer:
    """Parse X card primary line (4-1: positive-sequence data).

    Format (p.91):
        Col 1: 'X'
        Col 2: R (A1) - transformer type flag
        Col 4-10: NO (I7) - branch number
        Col 12: Z (A1) - zero-sequence flag
        Col 14-20: NFO (I7) - from node (HV side)
        Col 24-30: NTO (I7) - to node (LV side)
        Col 33: L (I1) - number of windings
        Col 36-45: Z1X (F10) - positive-sequence reactance
        Col 46-55: TAPR (F10) - tap ratio
        Col 56-65: TAPI (F10) - phase shift angle
        Col 69-80: XNAME (A12) - transformer name

    Args:
        line: X card primary line.

    Returns:
        Partially populated DynaTransformer.
    """
    xfmr = DynaTransformer()
    xfmr.branch_no = read_int(line, 4, 10)
    xfmr.has_zero_seq = read_str(line, 12, 12) == "Z"
    xfmr.from_node = read_int(line, 14, 20)
    xfmr.to_node = read_int(line, 24, 30)
    xfmr.z1x = read_float(line, 36, 45)
    xfmr.tap_ratio = read_float(line, 46, 55, 1.0)
    xfmr.shift_angle = read_float(line, 56, 65, 0.0)
    xfmr.name = read_str(line, 69, 80)
    return xfmr


def parse_x_card_zero_seq(line: str, xfmr: DynaTransformer) -> None:
    """Parse X card zero-sequence line (4-2).

    Format (p.93):
        Col 2: Y (A1) - winding type flag
        Col 16-25: ZOR (F10) - zero-sequence reactance (from side)
        Col 26-35: ZOX (F10) - zero-sequence reactance (to side)

    Args:
        line: X card zero-sequence line.
        xfmr: DynaTransformer to update in place.
    """
    xfmr.z0r = read_float(line, 16, 25)
    xfmr.z0x = read_float(line, 26, 35)


# =============================================================================
# N card parser (node)
# =============================================================================


def parse_n_card(line: str) -> DynaNode:
    """Parse N card (5-1: node data).

    Format (p.100):
        Col 1: 'N'
        Col 2: Z (A1) - zone flag
        Col 4-10: NO (I7) - node number
        Col 11-20: VO (F10) - initial voltage magnitude [p.u.]
        Col 21-30: PGO (F10) - generator active power [p.u.]
        Col 31-40: QGO (F10) - generator reactive power [p.u.]
        Col 41-50: PLO (F10) - load active power [p.u.]
        Col 51-60: QLO (F10) - load reactive power [p.u.]
        Col 61-68: YCO (F8) - shunt susceptance [p.u.]
        Col 69-72: VRT (F4) - voltage setpoint [p.u.]
        Col 69-80: NNAME (A12) - node name (shares cols with VRT)

    Note:
        NNAME and VRT share columns 69-80. If the field contains
        non-numeric text, it is treated as NNAME. Otherwise VRT.

    Args:
        line: N card line.

    Returns:
        Parsed DynaNode.
    """
    node = DynaNode()
    node.node_no = read_int(line, 4, 10)
    node.v0 = read_float(line, 11, 20, 0.0)
    node.p_gen = read_float(line, 21, 30)
    node.q_gen = read_float(line, 31, 40)
    node.p_load = read_float(line, 41, 50)
    node.q_load = read_float(line, 51, 60)
    node.shunt_b = read_float(line, 61, 68)
    # Col 69-80: could be VRT (numeric) or NNAME (text)
    name_or_vrt = read_str(line, 69, 80)
    if name_or_vrt:
        try:
            node.v_setpoint = float(name_or_vrt)
        except ValueError:
            node.name = name_or_vrt
    return node


# =============================================================================
# G card parser (generator)
# =============================================================================


def parse_g1_card(line: str) -> DynaGenerator:
    """Parse G1 card (9-1: generator ratings).

    Format (p.163):
        Col 1-2: 'G1'
        Col 4-10: NFG (I7) - generator bus node number
        Col 13-15: LGT (I3) - generator representation type
        Col 18-20: NGT (I3) - generator constant type
        Col 21-30: GMVA (F10) - rated capacity [MVA]
        Col 31-40: GMW (F10) - active power output [MW]
        Col 41-45: MG (F5) - inertia constant [sec, MVA base = 2H]
        Col 46-50: PLM (F5) - governor margin [MW base %]
        Col 51-55: DG (F5) - damping coefficient [p.u. on mbase]
        Col 56-60: QKGT (F5) - cross-compound Q allocation
        Col 61-72: GNAME (A12) - generator name

    Args:
        line: G1 card line.

    Returns:
        Partially populated DynaGenerator.
    """
    gen = DynaGenerator()
    gen.node_no = read_int(line, 4, 10)
    gen.lgt = read_int(line, 13, 15)
    gen.ngt = read_int(line, 18, 20)
    gen.gmva = read_float(line, 21, 30)
    gen.gmw = read_float(line, 31, 40)
    gen.mg = read_float(line, 41, 45)
    gen.plm = read_float(line, 46, 50)
    gen.dg = read_float(line, 51, 55)
    gen.name = read_str(line, 61, 72)
    return gen


def parse_g3_card(line: str, gen: DynaGenerator) -> None:
    """Parse G3 card (9-3: D-axis constants).

    Format (p.165):
        Col 1-2: 'G3'
        Col 4-10: blank
        Col 11-20: XD (F10) - synchronous reactance Xd [p.u.]
        Col 21-30: XDD (F10) - transient reactance Xd' [p.u.]
        Col 31-40: XDDD (F10) - sub-transient reactance Xd'' [p.u.]
        Col 41-50: TDD (F10) - transient time constant Td' [sec]
        Col 51-60: TDDD (F10) - sub-transient time constant Td'' [sec]
        Col 61-70: TDOD (F10) - open-circuit transient Tdo' [sec]
        Col 71-80: TDODD (F10) - open-circuit sub-transient Tdo'' [sec]

    Args:
        line: G3 card line.
        gen: DynaGenerator to update in place.
    """
    gen.xd = read_float(line, 11, 20)
    gen.xdd = read_float(line, 21, 30)
    gen.xddd = read_float(line, 31, 40)
    gen.tdd = read_float(line, 41, 50)
    gen.tddd = read_float(line, 51, 60)
    gen.tdod = read_float(line, 61, 70)
    gen.tdodd = read_float(line, 71, 80)


def parse_g4_card(line: str, gen: DynaGenerator) -> None:
    """Parse G4 card (9-4: Q-axis constants).

    Format (p.166):
        Col 1-2: 'G4'
        Col 11-20: XQ (F10) - synchronous reactance Xq [p.u.]
        Col 21-30: XQD (F10) - transient reactance Xq' [p.u.]
        Col 31-40: XQDD (F10) - sub-transient reactance Xq'' [p.u.]
        Col 41-50: TQD (F10) - transient time constant Tq' [sec]
        Col 51-60: TQDD (F10) - sub-transient time constant Tq'' [sec]
        Col 61-70: TQOD (F10) - open-circuit transient Tqo' [sec]
        Col 71-80: TQODD (F10) - open-circuit sub-transient Tqo'' [sec]

    Args:
        line: G4 card line.
        gen: DynaGenerator to update in place.
    """
    gen.xq = read_float(line, 11, 20)
    gen.xqd = read_float(line, 21, 30)
    gen.xqdd = read_float(line, 31, 40)
    gen.tqd = read_float(line, 41, 50)
    gen.tqdd = read_float(line, 51, 60)
    gen.tqod = read_float(line, 61, 70)
    gen.tqodd = read_float(line, 71, 80)


def parse_g5_card(line: str, gen: DynaGenerator) -> None:
    """Parse G5 card (9-5: leakage reactance, armature, sequence).

    Format (p.167):
        Col 1-2: 'G5'
        Col 3: R (A1) - 'R' = resistance, "'" = time constant
        Col 11-20: XL (F10) - leakage reactance [p.u.]
        Col 21-30: TA (F10) - armature time constant [sec] or resistance [p.u.]
        Col 31-40: X0 (F10) - zero-sequence reactance [p.u.]
        Col 41-50: X2 (F10) - negative-sequence reactance [p.u.]

    Args:
        line: G5 card line.
        gen: DynaGenerator to update in place.
    """
    gen.ra_type = read_str(line, 3, 3)
    gen.xl = read_float(line, 11, 20)
    gen.ta = read_float(line, 21, 30)
    gen.x0 = read_float(line, 31, 40)
    gen.x2 = read_float(line, 41, 50)


# =============================================================================
# Main section parsers
# =============================================================================


def parse_all_cards(lines: list[str]) -> DynaParsedData:
    """Parse all cards from a list of lines.

    Reads the file top-to-bottom, dispatching each line to the
    appropriate card parser based on the current section.

    Section transitions:
        DATA → T section → TEND → X section → XEND → N section → NEND
        → G section → GEND → STOP

    Args:
        lines: List of lines from a .dyna file.

    Returns:
        Fully populated DynaParsedData.
    """
    data = DynaParsedData()

    section = "INIT"
    i = 0
    current_tline: DynaTransmissionLine | None = None
    current_xfmr: DynaTransformer | None = None
    current_gen: DynaGenerator | None = None

    while i < len(lines):
        line = lines[i]

        # Skip comments and blank lines
        if not line.strip() or (len(line) > 0 and line[0] == "*"):
            i += 1
            continue

        # Check for terminators
        term = is_terminator(line)
        if term:
            # Flush pending objects
            if term == "TEND" and current_tline is not None:
                data.transmission_lines.append(current_tline)
                current_tline = None
            elif term == "XEND" and current_xfmr is not None:
                data.transformers.append(current_xfmr)
                current_xfmr = None
            elif term == "NEND":
                pass
            elif term in ("GEND", "GCON", "GSAT") and current_gen is not None:
                data.generators.append(current_gen)
                current_gen = None
            elif term == "STOP":
                break

            # Update section
            if term == "TEND":
                section = "POST_T"
            elif term == "XEND":
                section = "POST_X"
            elif term == "NEND":
                section = "POST_N"
            elif term in ("GEND", "GCON", "GSAT"):
                section = "POST_G"

            i += 1
            continue

        # Parse by section/card type
        card_id = line[0:2].rstrip() if len(line) >= 2 else line[0:1]

        if section == "INIT" and card_id == "DA":
            # DATA keyword line - next line has the actual data
            section = "DATA"
            i += 1
            continue

        if section == "DATA":
            data.control = parse_data_card(line)
            section = "POST_DATA"
            i += 1
            continue

        # T card section
        if card_id == "T" and section in ("POST_DATA", "T_SECTION"):
            section = "T_SECTION"
            # Check if this is a primary or continuation line
            branch_no = read_int(line, 4, 10)
            if branch_no > 0:
                # New primary T card - flush previous
                if current_tline is not None:
                    data.transmission_lines.append(current_tline)
                current_tline = parse_t_card_primary(line)
            elif current_tline is not None:
                # Zero-sequence continuation
                parse_t_card_zero_seq(line, current_tline)
            i += 1
            continue

        # X card section
        if card_id == "X" and section in ("POST_T", "X_SECTION"):
            section = "X_SECTION"
            branch_no = read_int(line, 4, 10)
            if branch_no > 0:
                if current_xfmr is not None:
                    data.transformers.append(current_xfmr)
                current_xfmr = parse_x_card_primary(line)
            elif current_xfmr is not None:
                # Zero-sequence or voltage control continuation
                vn = read_str(line, 2, 3)
                if vn and vn[0].isalpha() and vn[0] not in ("Y", "N"):
                    # Voltage control line (4-3) - skip for now
                    pass
                else:
                    parse_x_card_zero_seq(line, current_xfmr)
            i += 1
            continue

        # N card section
        if card_id == "N" and section in ("POST_X", "N_SECTION"):
            section = "N_SECTION"
            node = parse_n_card(line)
            if node.node_no > 0:
                data.nodes.append(node)
            i += 1
            continue

        # G card section
        if card_id in ("G1", "G2", "G3", "G4", "G5") and section in (
            "POST_N",
            "G_SECTION",
        ):
            section = "G_SECTION"

            if card_id == "G1":
                if current_gen is not None:
                    data.generators.append(current_gen)
                current_gen = parse_g1_card(line)
            elif card_id == "G2":
                # G2 card (AVR/governor) - skip for power flow
                pass
            elif card_id == "G3" and current_gen is not None:
                parse_g3_card(line, current_gen)
            elif card_id == "G4" and current_gen is not None:
                parse_g4_card(line, current_gen)
            elif card_id == "G5" and current_gen is not None:
                parse_g5_card(line, current_gen)

            i += 1
            continue

        # Unknown line - skip
        i += 1

    # Flush any remaining objects
    if current_tline is not None:
        data.transmission_lines.append(current_tline)
    if current_xfmr is not None:
        data.transformers.append(current_xfmr)
    if current_gen is not None:
        data.generators.append(current_gen)

    return data
