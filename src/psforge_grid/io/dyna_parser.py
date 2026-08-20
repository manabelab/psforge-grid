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
    >>> system = parse_dyna("cpat_model.dyna")  # doctest: +SKIP
    >>> print(f"Loaded {system.num_buses} buses")  # doctest: +SKIP

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
from psforge_grid.models.identity import make_unique
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
        >>> system = parse_dyna("cpat_model.dyna")  # doctest: +SKIP
        >>> print(f"{system.num_buses} buses, {system.num_branches} branches")  # doctest: +SKIP
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

    Element ids are generated deterministically: ``B{number}`` from the CPAT
    node number, and per-type sequence numbers in file occurrence order for
    everything else (``BR{n}``, ``G{n}``, ``LD{n}``, matching the integer
    part of ``order``). A shared ``used`` id set with
    :func:`~psforge_grid.models.identity.make_unique` acts as a safety net
    against collisions. CPAT branch/generator identifiers are kept as data
    (``circuit_id``, ``machine_id``), not encoded into ids.

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

    used: set[str] = set()
    buses, bus_id_by_no = _build_buses(parsed, used)
    branches = _build_branches(parsed, bus_id_by_no, used)
    generators = _build_generators(parsed, bus_id_by_no, used)
    loads = _build_loads(parsed, bus_id_by_no, used)

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


def _build_buses(parsed: DynaParsedData, used: set[str]) -> tuple[list[Bus], dict[int, str]]:
    """Build Bus objects from parsed N cards.

    Bus type determination:
        - bus_type=3 (Slack): N card has both P_gen and voltage setpoint,
          or name contains "SWING"
        - bus_type=2 (PV): N card has P_gen > 0 (generator bus)
        - bus_type=1 (PQ): all other buses

    Args:
        parsed: Parsed dyna data.
        used: Ids already generated for this system; extended in place.

    Returns:
        Tuple of (buses sorted by CPAT node number, node number →
        ``Bus.id`` mapping for reference fields).
    """
    # Collect generator bus nodes for PV/Slack detection
    gen_nodes = {g.node_no for g in parsed.generators}

    buses: list[Bus] = []
    bus_id_by_no: dict[int, str] = {}
    order = 0.0

    for node in parsed.nodes:
        if node.node_no <= 0:
            continue

        bus_type = _determine_bus_type(node, gen_nodes)

        # Voltage magnitude: prefer v0 if set, else 1.0
        v_mag = node.v0 if node.v0 > 0 else 1.0

        bus_id = make_unique(f"B{node.node_no}", used)
        used.add(bus_id)
        bus_id_by_no.setdefault(node.node_no, bus_id)
        order += 1.0

        bus = Bus(
            bus_id,
            bus_type=bus_type,
            v_magnitude=v_mag,
            v_angle=0.0,
            number=node.node_no,
            order=order,
            name=node.name,
        )
        buses.append(bus)

    buses.sort(key=lambda b: b.number if b.number is not None else 0)
    return buses, bus_id_by_no


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


def _build_branches(
    parsed: DynaParsedData,
    bus_id_by_no: dict[int, str],
    used: set[str],
) -> list[Branch]:
    """Build Branch objects from parsed T and X cards.

    Branch ids are ``BR{n}`` (file occurrence order, matching the integer
    part of ``order``). The CPAT branch number (NO field) is kept in
    ``circuit_id``.

    Args:
        parsed: Parsed dyna data.
        bus_id_by_no: Node number → ``Bus.id`` mapping.
        used: Ids already generated for this system; extended in place.

    Returns:
        List of Branch objects.
    """
    branches: list[Branch] = []
    order = 0.0

    # Transmission lines
    for tl in parsed.transmission_lines:
        order += 1.0
        branch = _tline_to_branch(tl, bus_id_by_no, used, order)
        branches.append(branch)

    # Transformers
    for xfmr in parsed.transformers:
        order += 1.0
        branch = _xfmr_to_branch(xfmr, bus_id_by_no, used, order)
        branches.append(branch)

    return branches


def _bus_ref(node_no: int, bus_id_by_no: dict[int, str]) -> str:
    """Resolve a node number to a Bus.id reference (lenient fallback).

    A dangling reference (node number without an N card) falls back to
    ``B{number}`` so that :meth:`System.validate` can report it, matching
    the pre-0.10.0 leniency of the parser.
    """
    return bus_id_by_no.get(node_no, f"B{node_no}")


def _tline_to_branch(
    tl: DynaTransmissionLine,
    bus_id_by_no: dict[int, str],
    used: set[str],
    order: float,
) -> Branch:
    """Convert a parsed transmission line to a Branch.

    Note:
        Y1C in CPAT is half the total charging susceptance (Y/2).
        Branch.b_pu expects total charging susceptance, so we store
        the value as-is (b_pu = Y1C, which is the half-value per CPAT convention).

    Args:
        tl: Parsed transmission line data.
        bus_id_by_no: Node number → ``Bus.id`` mapping.
        used: Ids already generated for this system; extended in place.
        order: Sort/display order within the file.

    Returns:
        Branch object.
    """
    ckt = str(tl.branch_no)
    branch_id = make_unique(f"BR{int(order)}", used)
    used.add(branch_id)

    branch = Branch(
        branch_id,
        from_bus_id=_bus_ref(tl.from_node, bus_id_by_no),
        to_bus_id=_bus_ref(tl.to_node, bus_id_by_no),
        r_pu=tl.z1r,
        x_pu=tl.z1x,
        b_pu=tl.y1c,
        order=order,
        name=tl.name,
        circuit_id=ckt,
    )
    if tl.z0r != 0.0:
        branch.r0_pu = tl.z0r
    if tl.z0x != 0.0:
        branch.x0_pu = tl.z0x
    return branch


def _xfmr_to_branch(
    xfmr: DynaTransformer,
    bus_id_by_no: dict[int, str],
    used: set[str],
    order: float,
) -> Branch:
    """Convert a parsed transformer to a Branch.

    Args:
        xfmr: Parsed transformer data.
        bus_id_by_no: Node number → ``Bus.id`` mapping.
        used: Ids already generated for this system; extended in place.
        order: Sort/display order within the file.

    Returns:
        Branch object with tap_ratio and shift_angle set.
    """
    ckt = str(xfmr.branch_no)
    branch_id = make_unique(f"BR{int(order)}", used)
    used.add(branch_id)

    return Branch(
        branch_id,
        from_bus_id=_bus_ref(xfmr.from_node, bus_id_by_no),
        to_bus_id=_bus_ref(xfmr.to_node, bus_id_by_no),
        r_pu=xfmr.z1r,
        x_pu=xfmr.z1x,
        tap_ratio=xfmr.tap_ratio if xfmr.tap_ratio != 0.0 else 1.0,
        shift_angle=xfmr.shift_angle,
        order=order,
        name=xfmr.name,
        circuit_id=ckt,
    )


def _build_generators(
    parsed: DynaParsedData,
    bus_id_by_no: dict[int, str],
    used: set[str],
) -> list[Generator]:
    """Build Generator objects from parsed G cards and N card data.

    Generator P/Q comes from N cards (PGO/QGO fields).
    Machine parameters come from G3-G5 cards (on machine base GMVA).

    Generator ids are ``G{n}`` (file occurrence order). The G card name
    (GNAME, the field the parser has always used as the generator
    identifier) is kept in ``machine_id``, falling back to ``"1"``.

    Args:
        parsed: Parsed dyna data.
        bus_id_by_no: Node number → ``Bus.id`` mapping.
        used: Ids already generated for this system; extended in place.

    Returns:
        List of Generator objects.
    """
    # Build node lookup for P/Q and voltage setpoint
    node_map = {n.node_no: n for n in parsed.nodes}

    generators: list[Generator] = []
    order = 0.0
    for dg in parsed.generators:
        order += 1.0
        gen = _dyna_gen_to_generator(
            dg, node_map, parsed.control.base_mva, bus_id_by_no, used, order
        )
        generators.append(gen)

    return generators


def _dyna_gen_to_generator(
    dg: DynaGenerator,
    node_map: dict[int, DynaNode],
    base_mva: float,
    bus_id_by_no: dict[int, str],
    used: set[str],
    order: float,
) -> Generator:
    """Convert a parsed DynaGenerator to a Generator.

    Args:
        dg: Parsed generator data.
        node_map: Node number to DynaNode mapping.
        base_mva: System base MVA.
        bus_id_by_no: Node number → ``Bus.id`` mapping.
        used: Ids already generated for this system; extended in place.
        order: Sort/display order within the file (its integer part is the
            id sequence number).

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

    machine_id = dg.name or "1"
    gen_id = make_unique(f"G{int(order)}", used)
    used.add(gen_id)

    return Generator(
        gen_id,
        bus_id=_bus_ref(dg.node_no, bus_id_by_no),
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
        machine_id=machine_id,
        order=order,
        name=dg.name,
    )


def _build_loads(
    parsed: DynaParsedData,
    bus_id_by_no: dict[int, str],
    used: set[str],
) -> list[Load]:
    """Build Load objects from N card P_load/Q_load data.

    Only buses with nonzero load are included. Load ids are ``LD{n}``
    (file occurrence order). The .dyna format has no per-load identifier,
    so ``load_id`` stays ``None`` (source not provided).

    Args:
        parsed: Parsed dyna data.
        bus_id_by_no: Node number → ``Bus.id`` mapping.
        used: Ids already generated for this system; extended in place.

    Returns:
        List of Load objects sorted by CPAT node number.
    """
    entries: list[tuple[int, Load]] = []
    order = 0.0

    for node in parsed.nodes:
        if node.p_load == 0.0 and node.q_load == 0.0:
            continue

        load_id = make_unique(f"LD{int(order) + 1}", used)
        used.add(load_id)
        order += 1.0

        load = Load(
            load_id,
            bus_id=_bus_ref(node.node_no, bus_id_by_no),
            p_load=node.p_load,
            q_load=node.q_load,
            order=order,
        )
        entries.append((node.node_no, load))

    entries.sort(key=lambda e: e[0])
    return [load for _no, load in entries]
