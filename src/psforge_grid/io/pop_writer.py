"""Writer for CPAT .pop format files (ZIP + XML).

This module provides functionality to export System objects to CPAT-GUI
native format (.pop). Symmetric counterpart of PopParser.

A .pop file is a ZIP archive containing three XML files:
    - data.pnsd: Electrical parameters (impedances, generator machine data)
    - psforge.pnsw: Topology (network connections)
    - psforge.pnsj: Operating point (voltage setpoints, P/Q dispatch)

Example:
    >>> from psforge_grid.io.pop_writer import write_pop
    >>> write_pop(system, tmp_path / "output.pop")
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element, SubElement, tostring

from psforge_grid.io.numbering import bus_number_map
from psforge_grid.io.protocols import IWriter

if TYPE_CHECKING:
    from psforge_grid.models.branch import Branch
    from psforge_grid.models.bus import Bus
    from psforge_grid.models.system import System

#: circuit_id pattern produced by PopParser for NL > 1 expansions
#: (e.g. "130_1", "130_2" for CPAT line CodeNumber 130 with NL=2).
_NL_CIRCUIT = re.compile(r"^(\d+)_(\d+)$")


class PopWriter(IWriter):
    """Writer for CPAT .pop format (ZIP + XML).

    Exports a System object to CPAT-GUI native .pop format.
    Generates three XML files and bundles them into a ZIP archive.

    Note:
        - ClusterIndex values are assigned sequentially during export:
          nodes start at 1000, transmission lines at 2000,
          transformers at 3000, generators at 4000
        - P/Q values are written in p.u. on system base MVA
        - Generator machine parameters are written on machine base (mbase)

    Round-trip fidelity (write → re-parse):
        - Element list order is preserved per type, so the sequential ids
          (``BR{n}``, ``G{n}``, ``LD{n}``) regenerate identically. The one
          format-imposed exception: .pop stores transmission lines and
          transformers in separate sections, so a branch list that
          interleaves them is re-read as "all lines, then all transformers".
        - Consecutive identical parallel lines whose ``circuit_id`` values
          follow the ``"{code}_1" .. "{code}_n"`` pattern (the PopParser
          NL > 1 expansion) are re-aggregated into a single cluster with
          ``NL=n``, so their ``circuit_id`` values round-trip exactly.
        - Other ``circuit_id`` values survive only if they are plain digits
          (CPAT CodeNumber is an integer field). A non-numeric
          ``circuit_id`` that does not match the NL pattern **cannot be
          represented** in .pop and is written as CodeNumber ``1``.
        - DictN (bus case data) is emitted with load-carrying buses first,
          in load occurrence order, so re-parsing regenerates the same
          ``LD{n}`` → bus assignment. DictN is a keyed dictionary in CPAT,
          so entry order carries no CPAT semantics.

    See Also:
        - PopParser: The symmetric read implementation
        - WriterFactory: Factory for creating writer instances
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return ["pop"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "CPAT Pop"

    def write(self, system: System, filepath: str | Path) -> None:
        """Write a System to a CPAT .pop file.

        Args:
            system: System object to export
            filepath: Output file path
        """
        # Integer bus numbers for CPAT (source-provided numbers kept as-is)
        num_map = bus_number_map(system)

        # Assign ClusterIndex values
        ci = _ClusterIndexAssigner(system)

        # Build XML trees
        pnsd_xml = _build_pnsd(system, ci)
        pnsw_xml = _build_pnsw(system, ci, num_map)
        pnsj_xml = _build_pnsj(system, ci, num_map)

        # Write ZIP archive
        path = Path(filepath)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("data.pnsd", _xml_to_str(pnsd_xml))
            zf.writestr("psforge.pnsw", _xml_to_str(pnsw_xml))
            zf.writestr("psforge.pnsj", _xml_to_str(pnsj_xml))


class _ClusterIndexAssigner:
    """Assigns ClusterIndex values and CodeNumbers to system components.

    Convention:
        - Nodes: 1000 + sequential index
        - Transmission line clusters: 2000 + sequential index
        - Transformers: 3000 + sequential index
        - Generators: 4000 + sequential index

    Transmission lines are grouped before assignment: consecutive
    identical parallel circuits (``circuit_id`` = ``"{code}_1"`` ..
    ``"{code}_n"``) become one cluster with ``NL=n``, mirroring the
    PopParser NL expansion. ``tline_groups`` holds branch-index groups;
    each group gets one ClusterIndex.

    Transformer CodeNumbers reuse a digit-only ``circuit_id`` when
    possible (so it round-trips); otherwise the lowest free positive
    integer is assigned.
    """

    def __init__(self, system: System) -> None:
        self.node_ci: dict[str, int] = {}  # Bus.id → ClusterIndex
        self.tline_groups: list[list[int]] = []  # groups of branch indices
        self.tline_group_ci: list[int] = []  # group index → ClusterIndex
        self.branch_group: dict[int, int] = {}  # branch index → group index
        self.xfmr_ci: dict[int, int] = {}  # branch index → ClusterIndex
        self.xfmr_code: dict[int, int] = {}  # branch index → CodeNumber
        self.gen_ci: dict[int, int] = {}  # generator index → ClusterIndex

        for idx, bus in enumerate(system.buses):
            self.node_ci[bus.id] = 1000 + idx

        self.tline_groups = _group_parallel_tlines(system)
        for g, group in enumerate(self.tline_groups):
            self.tline_group_ci.append(2000 + g)
            for i in group:
                self.branch_group[i] = g

        xf_idx = 0
        taken_codes: set[int] = set()
        fallback_pending: list[int] = []
        for i, br in enumerate(system.branches):
            if not br.is_transformer:
                continue
            self.xfmr_ci[i] = 3000 + xf_idx
            xf_idx += 1
            cid = br.circuit_id
            if cid is not None and cid.isdigit() and int(cid) > 0 and int(cid) not in taken_codes:
                self.xfmr_code[i] = int(cid)
                taken_codes.add(int(cid))
            else:
                fallback_pending.append(i)
        next_free = 1
        for i in fallback_pending:
            while next_free in taken_codes:
                next_free += 1
            self.xfmr_code[i] = next_free
            taken_codes.add(next_free)

        for i in range(len(system.generators)):
            self.gen_ci[i] = 4000 + i


def _group_parallel_tlines(system: System) -> list[list[int]]:
    """Group consecutive parallel transmission lines for NL re-aggregation.

    A group longer than one is formed only by the exact inverse of the
    PopParser NL > 1 expansion: consecutive non-transformer branches with
    ``circuit_id`` values ``"{code}_1"``, ``"{code}_2"``, ... sharing the
    same endpoints, electrical values and name.

    Args:
        system: System whose branches are being written.

    Returns:
        List of branch-index groups in branch list order. Every
        non-transformer branch appears in exactly one group.
    """
    branches = system.branches
    groups: list[list[int]] = []
    i = 0
    n = len(branches)
    while i < n:
        br = branches[i]
        if br.is_transformer:
            i += 1
            continue
        group = [i]
        m = _NL_CIRCUIT.match(br.circuit_id or "")
        if m is not None and m.group(2) == "1":
            prefix = m.group(1)
            k = 2
            j = i + 1
            while j < n:
                nxt = branches[j]
                if nxt.is_transformer or nxt.circuit_id != f"{prefix}_{k}":
                    break
                if not _same_parallel_circuit(br, nxt):
                    break
                group.append(j)
                k += 1
                j += 1
        groups.append(group)
        i = group[-1] + 1
    return groups


def _same_parallel_circuit(a: Branch, b: Branch) -> bool:
    """Check whether two branches are identical parallel circuits.

    Args:
        a: Representative branch of the candidate NL group.
        b: Branch considered for absorption into the group.

    Returns:
        True if ``b`` carries exactly the same endpoints and electrical
        values as ``a`` (so one NL cluster can represent both).
    """
    return (
        a.from_bus_id == b.from_bus_id
        and a.to_bus_id == b.to_bus_id
        and a.r_pu == b.r_pu
        and a.x_pu == b.x_pu
        and a.b_pu == b.b_pu
        and a.r0_pu == b.r0_pu
        and a.x0_pu == b.x0_pu
        and a.status == b.status
        and a.name == b.name
    )


def _tline_code_number(group: list[int], system: System) -> str:
    """Determine the CPAT CodeNumber text for a transmission line group.

    Args:
        group: Branch indices forming one cluster (see
            :func:`_group_parallel_tlines`).
        system: System whose branches are being written.

    Returns:
        The NL-pattern prefix for re-aggregated groups, the digit-only
        ``circuit_id`` for single circuits, or ``"1"`` when the
        ``circuit_id`` cannot be represented as a CPAT integer CodeNumber.
    """
    br = system.branches[group[0]]
    cid = br.circuit_id or ""
    if len(group) > 1:
        m = _NL_CIRCUIT.match(cid)
        assert m is not None  # guaranteed by _group_parallel_tlines
        return m.group(1)
    if cid.isdigit():
        return cid
    return "1"


def _xml_to_str(root: Element) -> str:
    """Convert an XML Element tree to a UTF-8 string with declaration."""
    return '<?xml version="1.0" encoding="utf-8"?>\n' + tostring(root, encoding="unicode")


def _add_text_elem(parent: Element, tag: str, text: str) -> Element:
    """Add a child element with text content."""
    elem = SubElement(parent, tag)
    elem.text = text
    return elem


# =============================================================================
# data.pnsd builder
# =============================================================================


def _build_pnsd(system: System, ci: _ClusterIndexAssigner) -> Element:
    """Build data.pnsd XML tree (electrical parameters).

    Contains:
        - ControlData: base MVA, frequency, header
        - VolDataSet: voltage class table
        - DictDataNodeValue: bus → voltage class mapping
        - DictDataTransmissionLine: line impedances
        - DictDataTransformer: transformer impedances
        - DictDataGenerator: generator machine parameters
    """
    root = Element("root")

    # ControlData
    cd = SubElement(root, "ControlData")
    _add_text_elem(cd, "Swva", str(system.base_mva))
    _add_text_elem(cd, "F", "60.0")
    _add_text_elem(cd, "Header", system.name or "psforge export")

    # VolDataSet: build unique voltage classes from bus base_kv
    kv_set = sorted({bus.base_kv for bus in system.buses})
    kv_to_idx: dict[float, int] = {kv: i for i, kv in enumerate(kv_set)}

    vds = SubElement(root, "VolDataSet")
    data_elem = SubElement(vds, "Data")
    for kv in kv_set:
        vd = SubElement(data_elem, "VolData")
        _add_text_elem(vd, "Vol", str(kv))

    # DictDataNodeValue: bus ClusterIndex → NumVol
    dnv = SubElement(root, "DictDataNodeValue")
    for bus in system.buses:
        item = SubElement(dnv, "item")
        key = SubElement(item, "key")
        _add_text_elem(key, "unsignedLong", str(ci.node_ci[bus.id]))
        val = SubElement(item, "value")
        dnvv = SubElement(val, "DataNodeValue")
        _add_text_elem(dnvv, "NumVol", str(kv_to_idx[bus.base_kv]))

    # DictDataTransmissionLine (one item per cluster; NL > 1 groups of
    # identical parallel circuits are written once with their NL count,
    # mirroring the PopParser expansion)
    dtl = SubElement(root, "DictDataTransmissionLine")
    for g, group in enumerate(ci.tline_groups):
        br = system.branches[group[0]]
        item = SubElement(dtl, "item")
        key = SubElement(item, "key")
        _add_text_elem(key, "unsignedLong", str(ci.tline_group_ci[g]))
        val = SubElement(item, "value")
        tld = SubElement(val, "DataTransmissionLine")
        _add_text_elem(tld, "Z1r", str(br.r_pu))
        _add_text_elem(tld, "Z1x", str(br.x_pu))
        # CPAT convention: Y1C = Y/2 (half of total charging).
        # Branch.b_pu stores total charging (PSS/E convention), so divide by 2.
        _add_text_elem(tld, "Y1c", str(br.b_pu / 2.0))
        if len(group) > 1:
            _add_text_elem(tld, "NL", str(len(group)))
        if br.r0_pu is not None:
            _add_text_elem(tld, "Zor", str(br.r0_pu))
        if br.x0_pu is not None:
            _add_text_elem(tld, "Zox", str(br.x0_pu))

    # DictDataTransformer
    dxt = SubElement(root, "DictDataTransformer")
    for i, br in enumerate(system.branches):
        if not br.is_transformer:
            continue
        item = SubElement(dxt, "item")
        key = SubElement(item, "key")
        _add_text_elem(key, "unsignedLong", str(ci.xfmr_ci[i]))
        val = SubElement(item, "value")
        xfd = SubElement(val, "DataTransformer")
        _add_text_elem(xfd, "Z1r", str(br.r_pu))
        _add_text_elem(xfd, "Z1x", str(br.x_pu))
        _add_text_elem(xfd, "Tapr", str(br.tap_ratio))
        _add_text_elem(xfd, "Tapi", str(br.shift_angle))

    # DictDataGenerator
    dg = SubElement(root, "DictDataGenerator")
    for i, gen in enumerate(system.generators):
        item = SubElement(dg, "item")
        key = SubElement(item, "key")
        _add_text_elem(key, "unsignedLong", str(ci.gen_ci[i]))
        val = SubElement(item, "value")
        gd = SubElement(val, "DataGenerator")
        _add_text_elem(gd, "Ngt", "1")
        _add_text_elem(gd, "Gmva", str(gen.mbase))
        gmw = (gen.p_max * system.base_mva) if gen.p_max is not None else 0.0
        _add_text_elem(gd, "Gmw", str(gmw))
        _add_text_elem(gd, "Xd", str(gen.xd_pu or 0.0))
        _add_text_elem(gd, "Xdd", str(gen.xdp_pu or 0.0))
        _add_text_elem(gd, "Xddd", str(gen.xdpp_pu or 0.0))
        _add_text_elem(gd, "Xqdd", str(gen.xqpp_pu or 0.0))
        _add_text_elem(gd, "X0_Saturation", str(gen.x0_pu or 0.0))
        _add_text_elem(gd, "X2_Saturation", str(gen.x2_pu or 0.0))
        _add_text_elem(gd, "Ta", str(gen.ta_s or 0.0))
        _add_text_elem(gd, "Ra", str(gen.ra_pu or 0.0))
        q_max = (gen.q_max * system.base_mva) if gen.q_max is not None else 0.0
        q_min = (gen.q_min * system.base_mva) if gen.q_min is not None else 0.0
        _add_text_elem(gd, "QgMax", str(q_max))
        _add_text_elem(gd, "QgMin", str(q_min))

    return root


# =============================================================================
# .pnsw builder (topology)
# =============================================================================

_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def _build_pnsw(system: System, ci: _ClusterIndexAssigner, num_map: dict[str, int]) -> Element:
    """Build .pnsw XML tree (topology).

    Creates Cluster elements for nodes, transmission lines,
    transformers, and generators with their connections.

    Bus CodeNumbers come from ``bus_number_map`` (source-provided
    ``Bus.number`` where available). The unified string ids are not
    written to the CPAT file.
    """
    root = Element("Clusters")
    root.set("xmlns:xsi", _XSI_NS)

    # Node clusters
    for bus in system.buses:
        bus_num = num_map[bus.id]
        cluster = SubElement(root, "Cluster")
        cluster.set("xsi:type", "GeneratingLine")
        _add_text_elem(cluster, "ClusterIndex", str(ci.node_ci[bus.id]))
        _add_text_elem(cluster, "CodeNumber", str(bus_num))
        _add_text_elem(cluster, "ClusterName", bus.name or f"BUS{bus_num}")

        # LinkBranchIndex: all branch clusters connected to this bus
        lbi = SubElement(cluster, "LinkBranchIndex")
        for g, group in enumerate(ci.tline_groups):
            br = system.branches[group[0]]
            if br.from_bus_id == bus.id or br.to_bus_id == bus.id:
                _add_text_elem(lbi, "unsignedLong", str(ci.tline_group_ci[g]))
        for i, br in enumerate(system.branches):
            if br.is_transformer and (br.from_bus_id == bus.id or br.to_bus_id == bus.id):
                _add_text_elem(lbi, "unsignedLong", str(ci.xfmr_ci[i]))
        # Also link generators
        for j, gen in enumerate(system.generators):
            if gen.bus_id == bus.id:
                _add_text_elem(lbi, "unsignedLong", str(ci.gen_ci[j]))

    # Transmission line clusters (one per NL group)
    for g, group in enumerate(ci.tline_groups):
        br = system.branches[group[0]]
        from_num = num_map[br.from_bus_id]
        to_num = num_map[br.to_bus_id]
        cluster = SubElement(root, "Cluster")
        cluster.set("xsi:type", "TransmissionLine")
        _add_text_elem(cluster, "ClusterIndex", str(ci.tline_group_ci[g]))
        _add_text_elem(cluster, "CodeNumber", _tline_code_number(group, system))
        _add_text_elem(cluster, "ClusterName", br.name or f"LINE{from_num}-{to_num}")
        lni = SubElement(cluster, "LinkNodeIndex")
        _add_text_elem(lni, "unsignedLong", str(ci.node_ci[br.from_bus_id]))
        _add_text_elem(lni, "unsignedLong", str(ci.node_ci[br.to_bus_id]))

    # Transformer clusters (CodeNumber reuses a digit-only circuit_id)
    for i, br in enumerate(system.branches):
        if not br.is_transformer:
            continue
        from_num = num_map[br.from_bus_id]
        to_num = num_map[br.to_bus_id]
        cluster = SubElement(root, "Cluster")
        cluster.set("xsi:type", "Transformer")
        _add_text_elem(cluster, "ClusterIndex", str(ci.xfmr_ci[i]))
        _add_text_elem(cluster, "CodeNumber", str(ci.xfmr_code[i]))
        _add_text_elem(cluster, "ClusterName", br.name or f"XFMR{from_num}-{to_num}")
        lni = SubElement(cluster, "LinkNodeIndex")
        _add_text_elem(lni, "unsignedLong", str(ci.node_ci[br.from_bus_id]))
        _add_text_elem(lni, "unsignedLong", str(ci.node_ci[br.to_bus_id]))

    # Generator clusters
    for j, gen in enumerate(system.generators):
        cluster = SubElement(root, "Cluster")
        cluster.set("xsi:type", "Generator")
        _add_text_elem(cluster, "ClusterIndex", str(ci.gen_ci[j]))
        _add_text_elem(cluster, "CodeNumber", gen.machine_id or "1")
        _add_text_elem(cluster, "ClusterName", gen.name or f"GEN{num_map[gen.bus_id]}")
        lni = SubElement(cluster, "LinkNodeIndex")
        _add_text_elem(lni, "unsignedLong", str(ci.node_ci[gen.bus_id]))

    return root


# =============================================================================
# .pnsj builder (case / operating point)
# =============================================================================


def _build_pnsj(system: System, ci: _ClusterIndexAssigner, num_map: dict[str, int]) -> Element:
    """Build .pnsj XML tree (operating point / case data).

    Contains DictN (node case data) and DictX (transformer case data).
    DictN keys are integer bus CodeNumbers from ``bus_number_map``.

    DictN entries are emitted with load-carrying buses first, ordered by
    load occurrence (``Load.order``, falling back to list position), so
    that re-parsing regenerates the same sequential ``LD{n}`` ids. DictN
    is a keyed dictionary, so this ordering carries no CPAT semantics.
    """
    root = Element("root")

    _add_text_elem(root, "BStandard", "true" if any(b.is_slack for b in system.buses) else "false")
    _add_text_elem(root, "LoadFactor", "100.0")
    _add_text_elem(root, "It", "20")
    _add_text_elem(root, "Sigma", "0.0001")

    # Aggregate P/Q per bus (keyed by Bus.id)
    gen_by_bus: dict[str, tuple[float, float, str]] = {}
    for gen in system.generators:
        if gen.status == 1:
            p, q, name = gen_by_bus.get(gen.bus_id, (0.0, 0.0, ""))
            gen_by_bus[gen.bus_id] = (p + gen.p_gen, q + gen.q_gen, gen.name or name)

    load_by_bus: dict[str, tuple[float, float]] = {}
    for load in system.loads:
        if load.status == 1:
            p, q = load_by_bus.get(load.bus_id, (0.0, 0.0))
            load_by_bus[load.bus_id] = (p + load.p_load, q + load.q_load)

    # DictN — load-carrying buses first, in load occurrence order, so the
    # re-parsed load sequence (and thus the LD{n} ids) matches this system.
    load_rank: dict[str, float] = {}
    for pos, load in enumerate(system.loads):
        if load.status != 1 or (load.p_load == 0.0 and load.q_load == 0.0):
            continue
        rank = load.order if load.order is not None else float(pos + 1)
        if load.bus_id not in load_rank or rank < load_rank[load.bus_id]:
            load_rank[load.bus_id] = rank

    def _dictn_key(bus: Bus) -> tuple[int, float]:
        if bus.id in load_rank:
            return (0, load_rank[bus.id])
        return (1, 0.0)  # stable sort keeps list order for no-load buses

    dictn = SubElement(root, "DictN")
    for bus in sorted(system.buses, key=_dictn_key):
        bus_num = num_map[bus.id]
        item = SubElement(dictn, "item")
        key = SubElement(item, "key")
        _add_text_elem(key, "int", str(bus_num))
        val = SubElement(item, "value")
        snode = SubElement(val, "SNode")
        _add_text_elem(snode, "Number", str(bus_num))
        _add_text_elem(snode, "Name", bus.name or f"BUS{bus_num}")
        _add_text_elem(snode, "Vol", str(bus.v_magnitude))

        p_gen, q_gen, gen_name = gen_by_bus.get(bus.id, (0.0, 0.0, ""))
        _add_text_elem(snode, "Pgo", str(p_gen))
        _add_text_elem(snode, "Qgo", str(q_gen))

        p_load, q_load = load_by_bus.get(bus.id, (0.0, 0.0))
        _add_text_elem(snode, "Plo", str(p_load))
        _add_text_elem(snode, "Qlo", str(q_load))

        _add_text_elem(snode, "Standard", "true" if bus.is_slack else "false")
        _add_text_elem(snode, "BUse", "true")
        _add_text_elem(snode, "GeneratorName", gen_name if gen_name else "（発電機データなし）")

    # DictX (transformer case data — keys must match CodeNumber in pnsw)
    dictx = SubElement(root, "DictX")
    for i, br in enumerate(system.branches):
        if not br.is_transformer:
            continue
        code = ci.xfmr_code[i]
        item = SubElement(dictx, "item")
        key = SubElement(item, "key")
        _add_text_elem(key, "int", str(code))
        val = SubElement(item, "value")
        strans = SubElement(val, "STransformer")
        _add_text_elem(strans, "Number", str(code))
        _add_text_elem(
            strans,
            "Name",
            br.name or f"XFMR{num_map[br.from_bus_id]}-{num_map[br.to_bus_id]}",
        )
        _add_text_elem(strans, "Tap", str(br.tap_ratio))
        _add_text_elem(strans, "BUse", "true" if br.status == 1 else "false")

    return root


def write_pop(system: System, filepath: str | Path) -> None:
    """Write a System to a CPAT .pop file (convenience function).

    Args:
        system: System object to export
        filepath: Output file path

    Example:
        >>> from psforge_grid.io.pop_writer import write_pop
        >>> write_pop(system, tmp_path / "output.pop")
    """
    writer = PopWriter()
    writer.write(system, filepath)
