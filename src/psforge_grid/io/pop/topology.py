"""Topology parser for .pop format (.pnsw file).

The .pnsw file contains a flat list of Cluster elements representing
all equipment in the single-line diagram. Each Cluster has:
    - ClusterIndex: unique internal ID (used as key in data.pnsd dicts)
    - CodeNumber: user-visible number (bus number for nodes)
    - ClusterName: human-readable name
    - xsi:type: equipment type (GeneratingLine, TransmissionLine, etc.)

Topology connections are expressed through:
    - LinkNodeIndex: for branches, lists [from_node, to_node] ClusterIndex
    - LinkBranchIndex: for nodes, lists connected branch ClusterIndex values
    - LinkGeneratorIndex: for generators, links to related generator data
"""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from psforge_grid.io.pop.xml_utils import get_int, get_str

# xsi:type attribute namespace
_XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"


@dataclass
class ClusterInfo:
    """Parsed information for a single Cluster element.

    Attributes:
        cluster_index: Internal unique ID (key for data.pnsd dicts).
        cluster_type: Equipment type string from xsi:type attribute.
        code_number: User-visible number (bus number for nodes, line number
            for branches, transformer number for transformers).
        name: Human-readable name (e.g., "NODE1", "G1", "LINE20-1").
        link_node_indices: Connected node ClusterIndex values.
            For branches: [from_node, to_node].
            For generators/loads: [parent_node].
        link_branch_indices: Connected branch ClusterIndex values (for nodes).
        link_generator_indices: Related generator ClusterIndex values.
    """

    cluster_index: int = 0
    cluster_type: str = ""
    code_number: int = 0
    name: str = ""
    link_node_indices: list[int] = field(default_factory=list)
    link_branch_indices: list[int] = field(default_factory=list)
    link_generator_indices: list[int] = field(default_factory=list)


@dataclass
class PopTopology:
    """Complete topology extracted from a .pnsw file.

    Provides lookup tables for resolving ClusterIndex → equipment
    and CodeNumber → ClusterIndex mappings.

    Attributes:
        nodes: Node (bus) clusters, keyed by ClusterIndex.
        transmission_lines: Transmission line clusters, keyed by ClusterIndex.
        transformers: Transformer clusters, keyed by ClusterIndex.
        generators: Generator clusters, keyed by ClusterIndex.
        loads: Load clusters, keyed by ClusterIndex.
        code_to_cluster: Mapping of CodeNumber → ClusterIndex for nodes.
        cluster_to_code: Mapping of ClusterIndex → CodeNumber for nodes.
    """

    nodes: dict[int, ClusterInfo] = field(default_factory=dict)
    transmission_lines: dict[int, ClusterInfo] = field(default_factory=dict)
    transformers: dict[int, ClusterInfo] = field(default_factory=dict)
    generators: dict[int, ClusterInfo] = field(default_factory=dict)
    loads: dict[int, ClusterInfo] = field(default_factory=dict)
    code_to_cluster: dict[int, int] = field(default_factory=dict)
    cluster_to_code: dict[int, int] = field(default_factory=dict)

    def get_bus_id(self, cluster_index: int) -> int:
        """Get bus CodeNumber from a node ClusterIndex.

        Args:
            cluster_index: Node ClusterIndex.

        Returns:
            Bus CodeNumber (user-visible bus number).

        Raises:
            KeyError: If cluster_index is not a known node.
        """
        return self.cluster_to_code[cluster_index]

    def get_branch_from_to(self, cluster_info: ClusterInfo) -> tuple[int, int]:
        """Get from/to bus CodeNumbers for a branch Cluster.

        Args:
            cluster_info: Branch cluster (transmission line or transformer).

        Returns:
            Tuple of (from_bus_code, to_bus_code) as CodeNumbers.

        Raises:
            ValueError: If the branch has fewer than 2 linked nodes.
        """
        if len(cluster_info.link_node_indices) < 2:
            raise ValueError(
                f"Branch ClusterIndex={cluster_info.cluster_index} "
                f"has {len(cluster_info.link_node_indices)} linked nodes, expected 2"
            )
        from_cluster = cluster_info.link_node_indices[0]
        to_cluster = cluster_info.link_node_indices[1]
        return self.get_bus_id(from_cluster), self.get_bus_id(to_cluster)


def parse_topology(pnsw_root: Element) -> PopTopology:
    """Parse topology from a .pnsw XML root.

    Args:
        pnsw_root: Root element of the .pnsw XML file.

    Returns:
        PopTopology with all clusters categorized by type.
    """
    topo = PopTopology()

    for cluster in pnsw_root.iter("Cluster"):
        info = _parse_cluster(cluster)
        ctype = info.cluster_type

        if ctype == "GeneratingLine":
            topo.nodes[info.cluster_index] = info
            if info.code_number > 0:
                topo.code_to_cluster[info.code_number] = info.cluster_index
                topo.cluster_to_code[info.cluster_index] = info.code_number
        elif ctype == "TransmissionLine":
            topo.transmission_lines[info.cluster_index] = info
        elif ctype == "Transformer":
            topo.transformers[info.cluster_index] = info
        elif ctype == "Generator":
            topo.generators[info.cluster_index] = info
        elif ctype == "Load":
            topo.loads[info.cluster_index] = info
        # Skip other types (TransformerPs, TransformerThree, etc.)

    return topo


def _parse_cluster(cluster: Element) -> ClusterInfo:
    """Parse a single Cluster element into ClusterInfo.

    Args:
        cluster: A <Cluster> XML element with xsi:type attribute.

    Returns:
        ClusterInfo with all fields populated.
    """
    info = ClusterInfo()
    info.cluster_index = get_int(cluster, "ClusterIndex")
    info.cluster_type = cluster.get(_XSI_TYPE, "")
    info.code_number = get_int(cluster, "CodeNumber")
    info.name = get_str(cluster, "ClusterName")

    # LinkNodeIndex: list of connected node ClusterIndex values
    link_nodes = cluster.find("LinkNodeIndex")
    if link_nodes is not None:
        for ul in link_nodes.findall("unsignedLong"):
            if ul.text:
                info.link_node_indices.append(int(ul.text))

    # LinkBranchIndex: list of connected branch ClusterIndex values
    link_branches = cluster.find("LinkBranchIndex")
    if link_branches is not None:
        for ul in link_branches.findall("unsignedLong"):
            if ul.text:
                info.link_branch_indices.append(int(ul.text))

    # LinkGeneratorIndex: list of related generator ClusterIndex values
    link_gens = cluster.find("LinkGeneratorIndex")
    if link_gens is not None:
        for ul in link_gens.findall("unsignedLong"):
            if ul.text:
                info.link_generator_indices.append(int(ul.text))

    return info
