"""CPAT .pop format parser.

Parses CPAT-GUI native format (.pop) files into psforge-grid System objects.

A .pop file is a ZIP archive containing XML files:
    - data.pnsd: Electrical parameters (impedances, generator machine data)
    - *.pnsw: Topology (network connections between equipment)
    - *.pnsj: Operating point (voltage setpoints, P/Q dispatch, swing bus)

Data integration requires cross-referencing three XML files:
    - data.pnsd keys: ClusterIndex (internal unique ID)
    - *.pnsw: maps ClusterIndex to CodeNumber (user-visible bus number)
    - *.pnsj keys: CodeNumber (user-visible bus number)

Example:
    >>> from psforge_grid.io.pop_parser import parse_pop
    >>> system = parse_pop("WEST10peak.pop")
    >>> print(f"Loaded {system.num_buses()} buses")

See Also:
    - PopParser: Class implementing IParser for .pop format
    - ParserFactory: io/factories.py
"""

from __future__ import annotations

import logging
from pathlib import Path
from xml.etree.ElementTree import Element

from psforge_grid.io.pop.archive import PopArchive
from psforge_grid.io.pop.case_data import PopCaseData, parse_case_data
from psforge_grid.io.pop.control_data import PopControlData, parse_control_data
from psforge_grid.io.pop.topology import PopTopology, parse_topology
from psforge_grid.io.pop.xml_utils import get_float, get_int
from psforge_grid.io.protocols import IParser
from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
from psforge_grid.models.system import System

logger = logging.getLogger(__name__)


class PopParser(IParser):
    """CPAT .pop format parser.

    Parses CPAT-GUI native .pop files (ZIP + XML) into System objects.
    Supports the IEEJ standard model format used by CPAT-GUI.

    See Also:
        - IParser: io/protocols.py
        - RawParser: io/raw_parser.py (similar pattern)
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return ["pop"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "CPAT Pop"

    def parse(self, filepath: str | Path) -> System:
        """Parse a .pop file and return a System object.

        Args:
            filepath: Path to the .pop file.

        Returns:
            System object with buses, branches, generators, and loads.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is invalid.
        """
        return _parse_pop_impl(filepath)


def parse_pop(filepath: str | Path) -> System:
    """Parse a CPAT .pop file and return a System object.

    Convenience function wrapping PopParser.parse().

    Args:
        filepath: Path to the .pop file.

    Returns:
        System object containing all parsed power system data.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is invalid.

    Example:
        >>> system = parse_pop("WEST10peak.pop")
        >>> print(f"{system.num_buses()} buses, {system.num_branches()} branches")
    """
    return _parse_pop_impl(filepath)


def _parse_pop_impl(filepath: str | Path) -> System:
    """Internal implementation of .pop file parsing.

    Data flow:
        1. Extract ZIP archive → 3 XML trees (pnsd, pnsw, pnsj)
        2. Parse control data (base MVA, voltage classes)
        3. Parse topology (equipment connections)
        4. Parse case data (operating point, swing bus)
        5. Build buses from topology nodes + case data + pnsd NumVol
        6. Build branches from topology + pnsd impedance data
        7. Build generators from topology + pnsd machine data + case dispatch
        8. Build loads from case data P/Q values

    Args:
        filepath: Path to the .pop file.

    Returns:
        Fully populated System object.
    """
    archive = PopArchive(filepath)

    control = parse_control_data(archive.pnsd_root)
    topology = parse_topology(archive.pnsw_root)
    case = parse_case_data(archive.pnsj_root)

    buses = _build_buses(topology, control, case, archive.pnsd_root)
    branches = _build_branches(topology, archive, control, case)
    generators = _build_generators(topology, archive, control, case)
    loads = _build_loads(case)

    system = System(
        buses=buses,
        branches=branches,
        generators=generators,
        loads=loads,
        base_mva=control.base_mva,
        name=control.header,
    )

    logger.info(
        "Parsed .pop file: %d buses, %d branches, %d generators, %d loads (base_mva=%.1f)",
        system.num_buses(),
        system.num_branches(),
        system.num_generators(),
        system.num_loads(),
        system.base_mva,
    )

    return system


def _build_buses(
    topology: PopTopology,
    control: PopControlData,
    case: PopCaseData,
    pnsd_root: Element,
) -> list[Bus]:
    """Build Bus objects from topology nodes, case data, and pnsd NumVol.

    Bus type determination:
        - bus_type=3 (Slack): pnsj Standard=true
        - bus_type=2 (PV): has generator with voltage setpoint
        - bus_type=1 (PQ): load bus or no generator

    Args:
        topology: Parsed topology from .pnsw.
        control: Control data with voltage class table.
        case: Case data with operating point.
        pnsd_root: Root element of data.pnsd for NumVol lookup.

    Returns:
        List of Bus objects sorted by bus_id.
    """
    # Build ClusterIndex → NumVol mapping from data.pnsd
    numvol_map = _build_numvol_map(pnsd_root)

    buses: list[Bus] = []

    for cluster_idx, node in topology.nodes.items():
        code = node.code_number
        if code <= 0:
            continue

        node_case = case.nodes.get(code)

        # Determine base_kv from voltage class index
        numvol = numvol_map.get(cluster_idx, 9)
        base_kv = control.voltage_classes.get(numvol, 1.0)

        # Voltage setpoint from case data
        v_mag = 1.0
        if node_case is not None and node_case.voltage_pu > 0:
            v_mag = node_case.voltage_pu

        # Bus type
        bus_type = 1  # PQ default
        if node_case is not None:
            if node_case.is_swing:
                bus_type = 3  # Slack
            elif node_case.generator_name and node_case.generator_name != "（発電機データなし）":
                bus_type = 2  # PV

        bus = Bus(
            bus_id=code,
            bus_type=bus_type,
            v_magnitude=v_mag,
            v_angle=0.0,
            base_kv=base_kv,
            v_max=1.1,
            v_min=0.9,
            name=node.name,
        )
        buses.append(bus)

    buses.sort(key=lambda b: b.bus_id)
    return buses


def _build_numvol_map(pnsd_root: Element) -> dict[int, int]:
    """Build ClusterIndex → NumVol mapping from DictDataNodeValue.

    Args:
        pnsd_root: Root element of data.pnsd XML.

    Returns:
        Dictionary mapping node ClusterIndex to voltage class index.
    """
    result: dict[int, int] = {}
    nodes_dict = pnsd_root.find("DictDataNodeValue")
    if nodes_dict is None:
        return result

    for item in nodes_dict.findall("item"):
        key_el = item.find(".//unsignedLong")
        val = item.find(".//DataNodeValue")
        if key_el is not None and key_el.text and val is not None:
            ci = int(key_el.text)
            result[ci] = get_int(val, "NumVol", 9)

    return result


def _build_branches(
    topology: PopTopology,
    archive: PopArchive,
    _control: PopControlData,
    case: PopCaseData,
) -> list[Branch]:
    """Build Branch objects from topology and data.pnsd impedance data.

    Transmission lines and transformers are both mapped to Branch objects.

    Args:
        topology: Parsed topology from .pnsw.
        archive: Parsed .pop archive with XML roots.
        _control: Control data (reserved for future base conversion).
        case: Case data with transformer tap settings.

    Returns:
        List of Branch objects.
    """
    branches: list[Branch] = []

    # Transmission lines
    tline_dict = _build_pnsd_dict(
        archive.pnsd_root, "DictDataTransmissionLine", "DataTransmissionLine"
    )
    for ci, cluster in topology.transmission_lines.items():
        tline_data = tline_dict.get(ci)
        if tline_data is None:
            continue

        try:
            from_bus, to_bus = topology.get_branch_from_to(cluster)
        except (ValueError, KeyError):
            logger.warning("Cannot resolve from/to for TransmissionLine ClusterIndex=%d", ci)
            continue

        r_pu = get_float(tline_data, "Z1r", 0.0)
        x_pu = get_float(tline_data, "Z1x", 0.0)
        b_pu = get_float(tline_data, "Y1c", 0.0)

        # Zero-sequence data
        r0 = get_float(tline_data, "Zor", 0.0)
        x0 = get_float(tline_data, "Zox", 0.0)

        # Number of parallel circuits (NL).  When NL > 1 the stored
        # impedance/admittance values are per-circuit values.  We
        # create NL identical branches so the Y-bus gets the correct
        # combined admittance (Y_total = NL * Y_per_circuit).
        nl = get_int(tline_data, "NL", 1)
        if nl < 1:
            nl = 1

        for cct in range(1, nl + 1):
            branch = Branch(
                from_bus=from_bus,
                to_bus=to_bus,
                r_pu=r_pu,
                x_pu=x_pu,
                b_pu=b_pu,
                name=cluster.name,
                circuit_id=f"{cluster.code_number}_{cct}" if nl > 1 else str(cluster.code_number),
            )
            if r0 != 0.0:
                branch.r0_pu = r0
            if x0 != 0.0:
                branch.x0_pu = x0

            branches.append(branch)

    # Transformers
    xfmr_dict = _build_pnsd_dict(archive.pnsd_root, "DictDataTransformer", "DataTransformer")
    for ci, cluster in topology.transformers.items():
        xfmr_data = xfmr_dict.get(ci)
        if xfmr_data is None:
            continue

        try:
            from_bus, to_bus = topology.get_branch_from_to(cluster)
        except (ValueError, KeyError):
            logger.warning("Cannot resolve from/to for Transformer ClusterIndex=%d", ci)
            continue

        r_pu = get_float(xfmr_data, "Z1r", 0.0)
        x_pu = get_float(xfmr_data, "Z1x", 0.0)

        # Tap ratio: prefer case data over static data
        tap = get_float(xfmr_data, "Tapr", 1.0)
        xfmr_case = case.transformers.get(cluster.code_number)
        if xfmr_case is not None and xfmr_case.tap != 0.0:
            tap = xfmr_case.tap

        shift_angle = get_float(xfmr_data, "Tapi", 0.0)

        # Zero-sequence data
        r0 = get_float(xfmr_data, "Zor", 0.0)
        x0 = get_float(xfmr_data, "Zox", 0.0)

        branch = Branch(
            from_bus=from_bus,
            to_bus=to_bus,
            r_pu=r_pu,
            x_pu=x_pu,
            tap_ratio=tap if tap != 0.0 else 1.0,
            shift_angle=shift_angle,
            name=cluster.name,
            circuit_id=str(cluster.code_number),
        )
        if r0 != 0.0:
            branch.r0_pu = r0
        if x0 != 0.0:
            branch.x0_pu = x0

        branches.append(branch)

    return branches


def _build_generators(
    topology: PopTopology,
    archive: PopArchive,
    control: PopControlData,
    case: PopCaseData,
) -> list[Generator]:
    """Build Generator objects from topology, data.pnsd, and case data.

    Generator data comes from three sources:
        - Topology (pnsw): which bus the generator is connected to
        - data.pnsd (DictDataGenerator, Ngt=1): machine parameters
        - Case data (pnsj): P dispatch and voltage setpoint

    Generators with Ngt=0 in data.pnsd are transient model variants
    and are skipped for power flow purposes.

    Machine parameters (Xd, Xdd, etc.) are on machine base (Gmva).

    Args:
        topology: Parsed topology from .pnsw.
        archive: Parsed .pop archive with XML roots.
        control: Control data with base MVA.
        case: Case data with P/Q dispatch.

    Returns:
        List of Generator objects.
    """
    generators: list[Generator] = []

    gen_dict = _build_pnsd_dict(archive.pnsd_root, "DictDataGenerator", "DataGenerator")

    for ci, cluster in topology.generators.items():
        gen_data = gen_dict.get(ci)
        if gen_data is None:
            continue

        # Skip transient-only entries (Ngt=0)
        ngt = get_int(gen_data, "Ngt", 0)
        if ngt == 0:
            continue

        # Find parent bus CodeNumber
        bus_code = _find_generator_bus(ci, topology)
        if bus_code is None:
            logger.warning("Cannot find parent bus for Generator ClusterIndex=%d", ci)
            continue

        # Machine base MVA
        gmva = get_float(gen_data, "Gmva", control.base_mva)

        # P/Q dispatch and voltage setpoint from case data
        node_case = case.nodes.get(bus_code)
        p_gen_pu = 0.0
        v_setpoint = 1.0
        if node_case is not None:
            p_gen_pu = node_case.p_gen_pu
            if node_case.voltage_pu > 0:
                v_setpoint = node_case.voltage_pu

        # Machine parameters (on machine base)
        xd = get_float(gen_data, "Xd") or None
        xdp = get_float(gen_data, "Xdd") or None
        xdpp = get_float(gen_data, "Xddd") or None
        xqpp = get_float(gen_data, "Xqdd") or None
        x0 = get_float(gen_data, "X0") or None
        x2 = get_float(gen_data, "X2") or None
        ta = get_float(gen_data, "Ta") or None
        ra = get_float(gen_data, "Ra") or None

        # Operating limits
        gmw = get_float(gen_data, "Gmw", 0.0)
        p_max = gmw / control.base_mva if control.base_mva > 0 else None
        q_max = get_float(gen_data, "QgMax") or None
        q_min = get_float(gen_data, "QgMin") or None

        gen = Generator(
            bus_id=bus_code,
            p_gen=p_gen_pu,
            q_gen=0.0,
            v_setpoint=v_setpoint,
            mbase=gmva,
            p_max=p_max,
            q_max=q_max,
            q_min=q_min,
            xd_pu=xd,
            xdp_pu=xdp,
            xdpp_pu=xdpp,
            xqpp_pu=xqpp,
            x0_pu=x0,
            x2_pu=x2,
            ta_s=ta,
            ra_pu=ra,
            gen_id=cluster.name or "1",
            name=cluster.name,
        )
        generators.append(gen)

    return generators


def _find_generator_bus(
    gen_cluster_index: int,
    topology: PopTopology,
) -> int | None:
    """Find the bus CodeNumber that a generator is connected to.

    Generator clusters are referenced by node clusters' LinkBranchIndex.
    We search all nodes to find which one lists this generator's
    ClusterIndex in its branch connections.

    Args:
        gen_cluster_index: Generator's ClusterIndex.
        topology: Parsed topology.

    Returns:
        Bus CodeNumber, or None if not found.
    """
    for node in topology.nodes.values():
        if gen_cluster_index in node.link_branch_indices:
            return node.code_number
    return None


def _build_loads(case: PopCaseData) -> list[Load]:
    """Build Load objects from case data P/Q values.

    Load P/Q is stored per-bus in the .pnsj file (Plo, Qlo fields).
    Only buses with nonzero load are included.

    Args:
        case: Case data with per-bus P/Q.

    Returns:
        List of Load objects sorted by bus_id.
    """
    loads: list[Load] = []

    for code, node_case in case.nodes.items():
        if node_case.p_load_pu == 0.0 and node_case.q_load_pu == 0.0:
            continue
        if not node_case.is_active:
            continue

        load = Load(
            bus_id=code,
            p_load=node_case.p_load_pu,
            q_load=node_case.q_load_pu,
        )
        loads.append(load)

    loads.sort(key=lambda ld: ld.bus_id)
    return loads


def _build_pnsd_dict(
    pnsd_root: Element,
    section_tag: str,
    data_tag: str,
) -> dict[int, Element]:
    """Build a ClusterIndex → XML Element mapping for a data.pnsd Dict section.

    Args:
        pnsd_root: Root element of data.pnsd XML.
        section_tag: Name of the Dict section (e.g., "DictDataTransmissionLine").
        data_tag: Name of the data element within each item.

    Returns:
        Dictionary mapping ClusterIndex (int) to the data XML Element.
    """
    section = pnsd_root.find(section_tag)
    if section is None:
        return {}

    result: dict[int, Element] = {}
    for item in section.findall("item"):
        key_el = item.find(".//unsignedLong")
        val = item.find(f".//{data_tag}")
        if key_el is not None and key_el.text and val is not None:
            result[int(key_el.text)] = val

    return result
