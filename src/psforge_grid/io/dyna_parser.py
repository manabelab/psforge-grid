"""CPAT dyna card format parser.

Parses CPAT Fortran fixed-column card format files (.dyna) into
psforge-grid System objects.

CPAT card format uses 80-character lines with fields at fixed column positions.
Data is organized in sections separated by terminators (TEND, XEND, NEND, GEND).

Supported cards:
    - DATA: System name, base MVA, frequency
    - T: Transmission line (positive + zero-sequence impedance)
    - X: Transformer (impedance, tap ratio, phase shift)
    - N: Node (voltage, generation, load, shunt)
    - G1-G5: Generator (ratings, D/Q-axis constants, sequence reactances)

Example:
    >>> from psforge_grid.io.dyna_parser import parse_dyna
    >>> system = parse_dyna("cpat_model.dyna")
    >>> print(f"Loaded {system.num_buses} buses")

See Also:
    - DynaParser: Class implementing IParser for .dyna format
    - ParserFactory: io/factories.py
"""

from __future__ import annotations

import logging
from pathlib import Path

from psforge_grid.io.dyna.card_parsers import (
    DynaGenerator,
    DynaNode,
    DynaParsedData,
    DynaTransformer,
    DynaTransmissionLine,
    parse_all_cards,
)
from psforge_grid.io.protocols import IParser
from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
from psforge_grid.models.system import System

logger = logging.getLogger(__name__)


class DynaParser(IParser):
    """CPAT dyna card format parser.

    Parses CPAT Fortran fixed-column format files into System objects.
    Supports the standard CPAT card format used for T-method and L-method analysis.

    See Also:
        - IParser: io/protocols.py
        - PopParser: io/pop_parser.py (CPAT .pop XML format)
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return ["dyna"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "CPAT Dyna"

    def parse(self, filepath: str | Path) -> System:
        """Parse a .dyna file and return a System object.

        Args:
            filepath: Path to the .dyna file.

        Returns:
            System object with buses, branches, generators, and loads.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is invalid.
        """
        return _parse_dyna_impl(filepath)


def parse_dyna(filepath: str | Path) -> System:
    """Parse a CPAT dyna card format file and return a System object.

    Convenience function wrapping DynaParser.parse().

    Args:
        filepath: Path to the .dyna file.

    Returns:
        System object containing all parsed power system data.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is invalid.

    Example:
        >>> system = parse_dyna("cpat_model.dyna")
        >>> print(f"{system.num_buses} buses, {system.num_branches} branches")
    """
    return _parse_dyna_impl(filepath)


def _parse_dyna_impl(filepath: str | Path) -> System:
    """Internal implementation of .dyna file parsing.

    Data flow:
        1. Read file lines
        2. Parse all cards (DATA, T, X, N, G1-G5) into intermediate data
        3. Build buses from N cards
        4. Build branches from T and X cards
        5. Build generators from G cards + N card P/Q
        6. Build loads from N card P_load/Q_load
        7. Determine bus types (swing detection from N card data)

    Args:
        filepath: Path to the .dyna file.

    Returns:
        Fully populated System object.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    parsed = parse_all_cards(lines)

    buses = _build_buses(parsed)
    branches = _build_branches(parsed)
    generators = _build_generators(parsed)
    loads = _build_loads(parsed)

    system = System(
        buses=buses,
        branches=branches,
        generators=generators,
        loads=loads,
        base_mva=parsed.control.base_mva,
        name=parsed.control.system_name,
    )

    logger.info(
        "Parsed .dyna file: %d buses, %d branches, %d generators, %d loads (base_mva=%.1f)",
        system.num_buses,
        system.num_branches,
        system.num_generators,
        system.num_loads,
        system.base_mva,
    )

    return system


def _build_buses(parsed: DynaParsedData) -> list[Bus]:
    """Build Bus objects from parsed N cards.

    Bus type determination:
        - bus_type=3 (Slack): N card has both P_gen and voltage setpoint,
          or name contains "SWING"
        - bus_type=2 (PV): N card has P_gen > 0 (generator bus)
        - bus_type=1 (PQ): all other buses

    Args:
        parsed: Parsed dyna data.

    Returns:
        List of Bus objects sorted by bus_id.
    """
    # Collect generator bus nodes for PV/Slack detection
    gen_nodes = {g.node_no for g in parsed.generators}

    buses: list[Bus] = []
    for node in parsed.nodes:
        if node.node_no <= 0:
            continue

        bus_type = _determine_bus_type(node, gen_nodes)

        # Voltage magnitude: prefer v0 if set, else 1.0
        v_mag = node.v0 if node.v0 > 0 else 1.0

        bus = Bus(
            bus_id=node.node_no,
            bus_type=bus_type,
            v_magnitude=v_mag,
            v_angle=0.0,
            name=node.name,
        )
        buses.append(bus)

    buses.sort(key=lambda b: b.bus_id)
    return buses


def _determine_bus_type(node: DynaNode, gen_nodes: set[int]) -> int:
    """Determine bus type from N card data.

    Detection logic:
        1. If name contains "SWING" → Slack (type 3)
        2. If has both Q_load < 0 and P_gen → Slack (CPAT convention:
           negative Q_load on a generator bus indicates swing)
        3. If has P_gen > 0 or is in gen_nodes → PV (type 2)
        4. Otherwise → PQ (type 1)

    Args:
        node: Parsed node data.
        gen_nodes: Set of node numbers with generator data.

    Returns:
        Bus type: 1 (PQ), 2 (PV), or 3 (Slack).
    """
    # Check name for swing indicator
    if node.name and "SWING" in node.name.upper():
        return 3

    # Generator bus detection
    is_gen_bus = node.p_gen > 0 or node.node_no in gen_nodes

    # CPAT swing bus convention: generator bus with Q_gen specified
    # and voltage setpoint (v0) set indicates controlled bus
    if is_gen_bus and node.q_load != 0 and node.p_gen > 0:
        # In the CPAT example, SWING bus has p_gen=1.0, p_load=4.0, q_load=-0.5
        # This is the only bus with both generation and load
        return 3

    if is_gen_bus:
        return 2

    return 1


def _build_branches(parsed: DynaParsedData) -> list[Branch]:
    """Build Branch objects from parsed T and X cards.

    Args:
        parsed: Parsed dyna data.

    Returns:
        List of Branch objects.
    """
    branches: list[Branch] = []

    # Transmission lines
    for tl in parsed.transmission_lines:
        branch = _tline_to_branch(tl)
        branches.append(branch)

    # Transformers
    for xfmr in parsed.transformers:
        branch = _xfmr_to_branch(xfmr)
        branches.append(branch)

    return branches


def _tline_to_branch(tl: DynaTransmissionLine) -> Branch:
    """Convert a parsed transmission line to a Branch.

    Note:
        Y1C in CPAT is half the total charging susceptance (Y/2).
        Branch.b_pu expects total charging susceptance, so we store
        the value as-is (b_pu = Y1C, which is the half-value per CPAT convention).

    Args:
        tl: Parsed transmission line data.

    Returns:
        Branch object.
    """
    branch = Branch(
        from_bus=tl.from_node,
        to_bus=tl.to_node,
        r_pu=tl.z1r,
        x_pu=tl.z1x,
        b_pu=tl.y1c,
        name=tl.name,
        circuit_id=str(tl.branch_no),
    )
    if tl.z0r != 0.0:
        branch.r0_pu = tl.z0r
    if tl.z0x != 0.0:
        branch.x0_pu = tl.z0x
    return branch


def _xfmr_to_branch(xfmr: DynaTransformer) -> Branch:
    """Convert a parsed transformer to a Branch.

    Args:
        xfmr: Parsed transformer data.

    Returns:
        Branch object with tap_ratio and shift_angle set.
    """
    return Branch(
        from_bus=xfmr.from_node,
        to_bus=xfmr.to_node,
        r_pu=xfmr.z1r,
        x_pu=xfmr.z1x,
        tap_ratio=xfmr.tap_ratio if xfmr.tap_ratio != 0.0 else 1.0,
        shift_angle=xfmr.shift_angle,
        name=xfmr.name,
        circuit_id=str(xfmr.branch_no),
    )


def _build_generators(parsed: DynaParsedData) -> list[Generator]:
    """Build Generator objects from parsed G cards and N card data.

    Generator P/Q comes from N cards (PGO/QGO fields).
    Machine parameters come from G3-G5 cards (on machine base GMVA).

    Args:
        parsed: Parsed dyna data.

    Returns:
        List of Generator objects.
    """
    # Build node lookup for P/Q and voltage setpoint
    node_map = {n.node_no: n for n in parsed.nodes}

    generators: list[Generator] = []
    for dg in parsed.generators:
        gen = _dyna_gen_to_generator(dg, node_map, parsed.control.base_mva)
        generators.append(gen)

    return generators


def _dyna_gen_to_generator(
    dg: DynaGenerator,
    node_map: dict[int, DynaNode],
    base_mva: float,
) -> Generator:
    """Convert a parsed DynaGenerator to a Generator.

    Args:
        dg: Parsed generator data.
        node_map: Node number to DynaNode mapping.
        base_mva: System base MVA.

    Returns:
        Generator object with machine parameters on machine base.
    """
    node = node_map.get(dg.node_no)

    # P/Q from N card (already in p.u. on system base)
    p_gen = node.p_gen if node else 0.0
    v_setpoint = node.v0 if node and node.v0 > 0 else 1.0

    # Machine parameters (on machine base GMVA)
    xd = dg.xd if dg.xd > 0 else None
    xdp = dg.xdd if dg.xdd > 0 else None
    xdpp = dg.xddd if dg.xddd > 0 else None
    xqpp = dg.xqdd if dg.xqdd > 0 else None
    x0 = dg.x0 if dg.x0 > 0 else None
    x2 = dg.x2 if dg.x2 > 0 else None

    # Armature: R or Ta based on ra_type
    ra = None
    ta = None
    if dg.ta > 0:
        if dg.ra_type == "R":
            ra = dg.ta  # Direct resistance value
        else:
            ta = dg.ta  # Time constant

    # Operating limits
    p_max = dg.gmw / base_mva if base_mva > 0 else None

    return Generator(
        bus_id=dg.node_no,
        p_gen=p_gen,
        q_gen=0.0,
        v_setpoint=v_setpoint,
        mbase=dg.gmva if dg.gmva > 0 else base_mva,
        p_max=p_max,
        xd_pu=xd,
        xdp_pu=xdp,
        xdpp_pu=xdpp,
        xqpp_pu=xqpp,
        x0_pu=x0,
        x2_pu=x2,
        ra_pu=ra,
        ta_s=ta,
        gen_id=dg.name or "1",
        name=dg.name,
    )


def _build_loads(parsed: DynaParsedData) -> list[Load]:
    """Build Load objects from N card P_load/Q_load data.

    Only buses with nonzero load are included.

    Args:
        parsed: Parsed dyna data.

    Returns:
        List of Load objects sorted by bus_id.
    """
    loads: list[Load] = []

    for node in parsed.nodes:
        if node.p_load == 0.0 and node.q_load == 0.0:
            continue
        load = Load(
            bus_id=node.node_no,
            p_load=node.p_load,
            q_load=node.q_load,
        )
        loads.append(load)

    loads.sort(key=lambda ld: ld.bus_id)
    return loads
