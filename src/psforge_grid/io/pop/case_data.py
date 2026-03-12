"""Case data parser for .pop format (.pnsj file).

The .pnsj file contains the operating point (case) data:
    - DictN: Node operating data (voltage, P/Q dispatch, swing bus)
    - DictX: Transformer case data (tap settings)
    - DictT: Transmission line case data (circuit status)

All Dict keys in .pnsj are CodeNumber (user-visible bus/equipment numbers),
NOT ClusterIndex.

P/Q values in .pnsj are in per-unit on the system base MVA (Swva).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from psforge_grid.io.pop.xml_utils import get_bool, get_float, get_str


@dataclass
class NodeCaseData:
    """Operating point data for a single bus/node.

    Attributes:
        code_number: Bus number (CodeNumber).
        name: Bus name.
        voltage_pu: Voltage setpoint in per-unit.
        p_gen_pu: Generator active power output in p.u. on system base.
        q_gen_pu: Generator reactive power output in p.u. on system base.
        p_load_pu: Load active power in p.u. on system base.
        q_load_pu: Load reactive power in p.u. on system base.
        is_swing: True if this bus is the swing (slack) bus.
        is_active: True if this bus is in service.
        generator_name: Name of attached generator, or empty string.
    """

    code_number: int = 0
    name: str = ""
    voltage_pu: float = 1.0
    p_gen_pu: float = 0.0
    q_gen_pu: float = 0.0
    p_load_pu: float = 0.0
    q_load_pu: float = 0.0
    is_swing: bool = False
    is_active: bool = True
    generator_name: str = ""


@dataclass
class TransformerCaseData:
    """Operating point data for a transformer.

    Attributes:
        code_number: Transformer number (CodeNumber).
        name: Transformer name.
        tap: Tap ratio setting.
        is_active: True if in service.
    """

    code_number: int = 0
    name: str = ""
    tap: float = 1.0
    is_active: bool = True


@dataclass
class PopCaseData:
    """Complete case (operating point) data from a .pnsj file.

    Attributes:
        nodes: Node case data keyed by CodeNumber.
        transformers: Transformer case data keyed by CodeNumber.
        has_swing: True if a swing bus is designated.
        load_factor: Load scaling factor (100 = 100%).
        max_iterations: Maximum NR iterations.
        convergence_tolerance: Convergence tolerance (sigma).
    """

    nodes: dict[int, NodeCaseData] = field(default_factory=dict)
    transformers: dict[int, TransformerCaseData] = field(default_factory=dict)
    has_swing: bool = False
    load_factor: float = 100.0
    max_iterations: int = 20
    convergence_tolerance: float = 0.0001


def parse_case_data(pnsj_root: Element) -> PopCaseData:
    """Parse case data from a .pnsj XML root.

    Args:
        pnsj_root: Root element of the .pnsj XML file.

    Returns:
        PopCaseData with all operating point information.
    """
    result = PopCaseData()

    result.has_swing = get_bool(pnsj_root, "BStandard")
    result.load_factor = get_float(pnsj_root, "LoadFactor", 100.0)
    result.max_iterations = int(get_float(pnsj_root, "It", 20.0))
    result.convergence_tolerance = get_float(pnsj_root, "Sigma", 0.0001)

    # Parse DictN (node case data)
    dictn = pnsj_root.find("DictN")
    if dictn is not None:
        for item in dictn.findall("item"):
            snode = item.find(".//SNode")
            if snode is None:
                continue
            node = _parse_node_case(snode)
            result.nodes[node.code_number] = node

    # Parse DictX (transformer case data)
    dictx = pnsj_root.find("DictX")
    if dictx is not None:
        for item in dictx.findall("item"):
            strans = item.find(".//STransformer")
            if strans is None:
                continue
            xfmr = _parse_transformer_case(strans)
            result.transformers[xfmr.code_number] = xfmr

    return result


def _parse_node_case(snode: Element) -> NodeCaseData:
    """Parse a single SNode element.

    Args:
        snode: An <SNode> XML element from DictN.

    Returns:
        NodeCaseData with operating point values.
    """
    node = NodeCaseData()
    node.code_number = int(get_float(snode, "Number", 0))
    node.name = get_str(snode, "Name")
    node.voltage_pu = get_float(snode, "Vol", 1.0)
    node.p_gen_pu = get_float(snode, "Pgo", 0.0)
    node.q_gen_pu = get_float(snode, "Qgo", 0.0)
    node.p_load_pu = get_float(snode, "Plo", 0.0)
    node.q_load_pu = get_float(snode, "Qlo", 0.0)
    node.is_swing = get_bool(snode, "Standard")
    node.is_active = get_bool(snode, "BUse", True)
    node.generator_name = get_str(snode, "GeneratorName")
    return node


def _parse_transformer_case(strans: Element) -> TransformerCaseData:
    """Parse a single STransformer element.

    Args:
        strans: An <STransformer> XML element from DictX.

    Returns:
        TransformerCaseData with tap setting.
    """
    xfmr = TransformerCaseData()
    xfmr.code_number = int(get_float(strans, "Number", 0))
    xfmr.name = get_str(strans, "Name")
    xfmr.tap = get_float(strans, "Tap", 1.0)
    xfmr.is_active = get_bool(strans, "BUse", True)
    return xfmr
