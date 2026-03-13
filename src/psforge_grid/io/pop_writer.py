"""Writer for CPAT .pop format files (ZIP + XML).

This module provides functionality to export System objects to CPAT-GUI
native format (.pop). Symmetric counterpart of PopParser.

A .pop file is a ZIP archive containing three XML files:
    - data.pnsd: Electrical parameters (impedances, generator machine data)
    - psforge.pnsw: Topology (network connections)
    - psforge.pnsj: Operating point (voltage setpoints, P/Q dispatch)

Example:
    >>> from psforge_grid.io.pop_writer import write_pop
    >>> write_pop(system, "output.pop")
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element, SubElement, tostring

from psforge_grid.io.protocols import IWriter

if TYPE_CHECKING:
    from psforge_grid.models.system import System


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
        # Assign ClusterIndex values
        ci = _ClusterIndexAssigner(system)

        # Build XML trees
        pnsd_xml = _build_pnsd(system, ci)
        pnsw_xml = _build_pnsw(system, ci)
        pnsj_xml = _build_pnsj(system)

        # Write ZIP archive
        path = Path(filepath)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("data.pnsd", _xml_to_str(pnsd_xml))
            zf.writestr("psforge.pnsw", _xml_to_str(pnsw_xml))
            zf.writestr("psforge.pnsj", _xml_to_str(pnsj_xml))


class _ClusterIndexAssigner:
    """Assigns sequential ClusterIndex values to system components.

    Convention:
        - Nodes: 1000 + sequential index
        - Transmission lines: 2000 + sequential index
        - Transformers: 3000 + sequential index
        - Generators: 4000 + sequential index
    """

    def __init__(self, system: System) -> None:
        self.node_ci: dict[int, int] = {}  # bus_id → ClusterIndex
        self.tline_ci: dict[int, int] = {}  # branch index → ClusterIndex
        self.xfmr_ci: dict[int, int] = {}  # branch index → ClusterIndex
        self.gen_ci: dict[int, int] = {}  # generator index → ClusterIndex

        for idx, bus in enumerate(system.buses):
            self.node_ci[bus.bus_id] = 1000 + idx

        tl_idx = 0
        xf_idx = 0
        for i, br in enumerate(system.branches):
            if br.is_transformer:
                self.xfmr_ci[i] = 3000 + xf_idx
                xf_idx += 1
            else:
                self.tline_ci[i] = 2000 + tl_idx
                tl_idx += 1

        for i in range(len(system.generators)):
            self.gen_ci[i] = 4000 + i


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
        _add_text_elem(key, "unsignedLong", str(ci.node_ci[bus.bus_id]))
        val = SubElement(item, "value")
        dnvv = SubElement(val, "DataNodeValue")
        _add_text_elem(dnvv, "NumVol", str(kv_to_idx[bus.base_kv]))

    # DictDataTransmissionLine
    dtl = SubElement(root, "DictDataTransmissionLine")
    for i, br in enumerate(system.branches):
        if br.is_transformer:
            continue
        item = SubElement(dtl, "item")
        key = SubElement(item, "key")
        _add_text_elem(key, "unsignedLong", str(ci.tline_ci[i]))
        val = SubElement(item, "value")
        tld = SubElement(val, "DataTransmissionLine")
        _add_text_elem(tld, "Z1r", str(br.r_pu))
        _add_text_elem(tld, "Z1x", str(br.x_pu))
        _add_text_elem(tld, "Y1c", str(br.b_pu))
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


def _build_pnsw(system: System, ci: _ClusterIndexAssigner) -> Element:
    """Build .pnsw XML tree (topology).

    Creates Cluster elements for nodes, transmission lines,
    transformers, and generators with their connections.
    """
    root = Element("Clusters")
    root.set("xmlns:xsi", _XSI_NS)

    # Node clusters
    for bus in system.buses:
        cluster = SubElement(root, "Cluster")
        cluster.set("xsi:type", "GeneratingLine")
        _add_text_elem(cluster, "ClusterIndex", str(ci.node_ci[bus.bus_id]))
        _add_text_elem(cluster, "CodeNumber", str(bus.bus_id))
        _add_text_elem(cluster, "ClusterName", bus.name or f"BUS{bus.bus_id}")

        # LinkBranchIndex: all branches connected to this bus
        lbi = SubElement(cluster, "LinkBranchIndex")
        for i, br in enumerate(system.branches):
            if br.from_bus == bus.bus_id or br.to_bus == bus.bus_id:
                branch_ci = ci.tline_ci.get(i) or ci.xfmr_ci.get(i)
                if branch_ci is not None:
                    _add_text_elem(lbi, "unsignedLong", str(branch_ci))
        # Also link generators
        for j, gen in enumerate(system.generators):
            if gen.bus_id == bus.bus_id:
                _add_text_elem(lbi, "unsignedLong", str(ci.gen_ci[j]))

    # Transmission line clusters
    for i, br in enumerate(system.branches):
        if br.is_transformer:
            continue
        cluster = SubElement(root, "Cluster")
        cluster.set("xsi:type", "TransmissionLine")
        _add_text_elem(cluster, "ClusterIndex", str(ci.tline_ci[i]))
        _add_text_elem(cluster, "CodeNumber", br.circuit_id)
        _add_text_elem(cluster, "ClusterName", br.name or f"LINE{br.from_bus}-{br.to_bus}")
        lni = SubElement(cluster, "LinkNodeIndex")
        _add_text_elem(lni, "unsignedLong", str(ci.node_ci[br.from_bus]))
        _add_text_elem(lni, "unsignedLong", str(ci.node_ci[br.to_bus]))

    # Transformer clusters
    for i, br in enumerate(system.branches):
        if not br.is_transformer:
            continue
        cluster = SubElement(root, "Cluster")
        cluster.set("xsi:type", "Transformer")
        _add_text_elem(cluster, "ClusterIndex", str(ci.xfmr_ci[i]))
        _add_text_elem(cluster, "CodeNumber", br.circuit_id)
        _add_text_elem(cluster, "ClusterName", br.name or f"XFMR{br.from_bus}-{br.to_bus}")
        lni = SubElement(cluster, "LinkNodeIndex")
        _add_text_elem(lni, "unsignedLong", str(ci.node_ci[br.from_bus]))
        _add_text_elem(lni, "unsignedLong", str(ci.node_ci[br.to_bus]))

    # Generator clusters
    for j, gen in enumerate(system.generators):
        cluster = SubElement(root, "Cluster")
        cluster.set("xsi:type", "Generator")
        _add_text_elem(cluster, "ClusterIndex", str(ci.gen_ci[j]))
        _add_text_elem(cluster, "CodeNumber", gen.gen_id)
        _add_text_elem(cluster, "ClusterName", gen.name or f"GEN{gen.bus_id}")
        lni = SubElement(cluster, "LinkNodeIndex")
        _add_text_elem(lni, "unsignedLong", str(ci.node_ci[gen.bus_id]))

    return root


# =============================================================================
# .pnsj builder (case / operating point)
# =============================================================================


def _build_pnsj(system: System) -> Element:
    """Build .pnsj XML tree (operating point / case data).

    Contains DictN (node case data) and DictX (transformer case data).
    """
    root = Element("root")

    _add_text_elem(root, "BStandard", "true" if any(b.is_slack for b in system.buses) else "false")
    _add_text_elem(root, "LoadFactor", "100.0")
    _add_text_elem(root, "It", "20")
    _add_text_elem(root, "Sigma", "0.0001")

    # Aggregate P/Q per bus
    gen_by_bus: dict[int, tuple[float, float, str]] = {}
    for gen in system.generators:
        if gen.status == 1:
            p, q, name = gen_by_bus.get(gen.bus_id, (0.0, 0.0, ""))
            gen_by_bus[gen.bus_id] = (p + gen.p_gen, q + gen.q_gen, gen.name or name)

    load_by_bus: dict[int, tuple[float, float]] = {}
    for load in system.loads:
        if load.status == 1:
            p, q = load_by_bus.get(load.bus_id, (0.0, 0.0))
            load_by_bus[load.bus_id] = (p + load.p_load, q + load.q_load)

    # DictN
    dictn = SubElement(root, "DictN")
    for bus in system.buses:
        item = SubElement(dictn, "item")
        key = SubElement(item, "key")
        _add_text_elem(key, "int", str(bus.bus_id))
        val = SubElement(item, "value")
        snode = SubElement(val, "SNode")
        _add_text_elem(snode, "Number", str(bus.bus_id))
        _add_text_elem(snode, "Name", bus.name or f"BUS{bus.bus_id}")
        _add_text_elem(snode, "Vol", str(bus.v_magnitude))

        p_gen, q_gen, gen_name = gen_by_bus.get(bus.bus_id, (0.0, 0.0, ""))
        _add_text_elem(snode, "Pgo", str(p_gen))
        _add_text_elem(snode, "Qgo", str(q_gen))

        p_load, q_load = load_by_bus.get(bus.bus_id, (0.0, 0.0))
        _add_text_elem(snode, "Plo", str(p_load))
        _add_text_elem(snode, "Qlo", str(q_load))

        _add_text_elem(snode, "Standard", "true" if bus.is_slack else "false")
        _add_text_elem(snode, "BUse", "true")
        _add_text_elem(snode, "GeneratorName", gen_name if gen_name else "（発電機データなし）")

    # DictX (transformer case data)
    dictx = SubElement(root, "DictX")
    for i, br in enumerate(system.branches):
        if not br.is_transformer:
            continue
        item = SubElement(dictx, "item")
        key = SubElement(item, "key")
        code = int(br.circuit_id) if br.circuit_id.isdigit() else i
        _add_text_elem(key, "int", str(code))
        val = SubElement(item, "value")
        strans = SubElement(val, "STransformer")
        _add_text_elem(strans, "Number", str(code))
        _add_text_elem(strans, "Name", br.name or f"XFMR{br.from_bus}-{br.to_bus}")
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
        >>> write_pop(system, "output.pop")
    """
    writer = PopWriter()
    writer.write(system, filepath)
