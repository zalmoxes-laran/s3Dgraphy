"""
Epoch Swimlanes Generator for GraphML Export

Generates yEd TableNode structures to represent temporal epochs as horizontal swimlanes.
Supports hierarchical temporal periods (Period > Phase > Subphase).
"""

from typing import List, Dict, Tuple, Optional
from lxml import etree as ET
from ...nodes.epoch_node import EpochNode
from .utils import generate_uuid, qname


class EpochSwimlanesGenerator:
    """
    Generates TableNode structures for epoch-based swimlanes in yEd.

    Extended Matrix uses horizontal swimlanes to represent temporal periods,
    with stratigraphic units positioned within their corresponding epochs.
    """

    def __init__(self):
        """Initialize the epoch swimlanes generator."""
        # Namespace definitions
        self.NS_GRAPHML = "http://graphml.graphdrawing.org/xmlns"
        self.NS_YFILES = "http://www.yworks.com/xml/graphml"

    def generate_tablenode_xml(
        self,
        epoch_nodes: List[EpochNode],
        graph,
        canvas_width: float = 1200.0,
        canvas_height: float = 1000.0,
        row_height: float = 150.0
    ) -> ET.Element:
        """
        Generate a TableNode XML element for epoch swimlanes.

        Args:
            epoch_nodes: List of EpochNode instances
            graph: s3dgraphy Graph object (for context)
            canvas_width: Total width of the canvas
            canvas_height: Total height of the canvas
            row_height: Height of each epoch row

        Returns:
            ET.Element: TableNode XML element
        """
        # Sort epochs by start time (most recent first)
        sorted_epochs = self._sort_epochs_by_time(epoch_nodes)

        # Calculate total height needed
        total_height = len(sorted_epochs) * row_height
        if total_height > canvas_height:
            canvas_height = total_height

        # Create TableNode root
        tablenode_id = f"n0::swimlane"
        tablenode = ET.Element(
            qname(self.NS_GRAPHML, "node"),
            id=tablenode_id
        )
        tablenode.set("{http://www.yworks.com/xml/yfiles-common/2.0}foldertype", "group")

        # Add graphics data
        data_graphics = ET.SubElement(tablenode, qname(self.NS_GRAPHML, "data"), key="d6")
        y_tablenode = ET.SubElement(data_graphics, qname(self.NS_YFILES, "TableNode"))

        # Geometry
        geometry = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "Geometry"))
        geometry.set("height", str(canvas_height))
        geometry.set("width", str(canvas_width))
        geometry.set("x", "0")
        geometry.set("y", "0")

        # Main label (site/graph name)
        site_label = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "NodeLabel"))
        graph_name = graph.name.get("en", "Archaeological Site") if hasattr(graph, 'name') else "Archaeological Site"
        site_label.text = f"{graph_name} [ID:{graph.graph_id[:8]}]"

        # Table structure
        y_table = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "Table"))

        # Rows container
        y_rows = ET.SubElement(y_table, qname(self.NS_YFILES, "Rows"))

        # Generate row for each epoch
        current_y = 0.0
        for epoch in sorted_epochs:
            row_elem = self._generate_epoch_row(epoch, row_height, current_y)
            y_rows.append(row_elem)

            # Add row label to TableNode
            row_label = self._generate_epoch_label(epoch, row_height)
            y_tablenode.append(row_label)

            current_y += row_height

        # Create nested graph element for nodes inside swimlanes
        nested_graph = ET.SubElement(tablenode, qname(self.NS_GRAPHML, "graph"))
        nested_graph.set("edgedefault", "directed")
        nested_graph.set("id", f"{tablenode_id}:")

        return tablenode

    def _sort_epochs_by_time(self, epoch_nodes: List[EpochNode]) -> List[EpochNode]:
        """
        Sort epoch nodes by start time (most recent first).

        Args:
            epoch_nodes: List of EpochNode instances

        Returns:
            Sorted list of EpochNode instances
        """
        def get_start_time(epoch: EpochNode) -> int:
            """Extract start time, handling None values."""
            if hasattr(epoch, 'start') and epoch.start is not None:
                return epoch.start
            return 0  # Default for missing start times

        return sorted(epoch_nodes, key=get_start_time, reverse=True)

    def _generate_epoch_row(
        self,
        epoch: EpochNode,
        height: float,
        y_offset: float
    ) -> ET.Element:
        """
        Generate a Row element for a single epoch.

        Args:
            epoch: EpochNode instance
            height: Row height
            y_offset: Y offset from top

        Returns:
            ET.Element: Row XML element
        """
        row = ET.Element(qname(self.NS_YFILES, "Row"))
        row.set("id", f"epoch_{epoch.node_id}")
        row.set("height", str(height))

        # Insets (padding)
        insets = ET.SubElement(row, qname(self.NS_YFILES, "Insets"))
        insets.set("bottom", "0")
        insets.set("left", "0")
        insets.set("right", "0")
        insets.set("top", "0")

        return row

    def _generate_epoch_label(
        self,
        epoch: EpochNode,
        row_height: float
    ) -> ET.Element:
        """
        Generate a NodeLabel for an epoch row.

        Args:
            epoch: EpochNode instance
            row_height: Height of the row

        Returns:
            ET.Element: NodeLabel XML element
        """
        label = ET.Element(qname(self.NS_YFILES, "NodeLabel"))

        # Label text with epoch name and time range
        epoch_name = epoch.name if hasattr(epoch, 'name') else "Unknown Epoch"
        start_time = epoch.start if hasattr(epoch, 'start') and epoch.start is not None else "?"
        end_time = epoch.end if hasattr(epoch, 'end') and epoch.end is not None else "?"

        label.text = f"{epoch_name} [start:{start_time};end:{end_time}]"

        # Background color (gold/yellow for visibility)
        label.set("backgroundColor", "#FFD700")

        # Row label model parameter
        label_model = ET.SubElement(label, qname(self.NS_YFILES, "RowNodeLabelModelParameter"))
        label_model.set("id", f"epoch_{epoch.node_id}")

        return label

    def calculate_epoch_positions(
        self,
        nodes: List,
        epoch_nodes: List[EpochNode],
        temporal_edges: List[Tuple[str, str]],
        row_height: float = 150.0,
        start_x: float = 100.0,
        spacing_y: float = 80.0
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculate positions for stratigraphic nodes within epoch swimlanes.

        Positions nodes based on:
        1. Temporal epoch assignment
        2. Temporal ordering within epoch (using temporal_edges)

        Args:
            nodes: List of stratigraphic nodes
            epoch_nodes: List of EpochNode instances
            temporal_edges: List of (source, target) temporal edges
            row_height: Height of each epoch row
            start_x: Starting X coordinate for nodes
            spacing_y: Vertical spacing between nodes

        Returns:
            Dictionary mapping node_id to (x, y) coordinates
        """
        from ...nodes.stratigraphic_node import StratigraphicNode
        import networkx as nx

        positions = {}

        # Sort epochs by time
        sorted_epochs = self._sort_epochs_by_time(epoch_nodes)

        # Build temporal graph for ordering
        G = nx.DiGraph()
        G.add_edges_from(temporal_edges)

        # Assign nodes to epochs
        epoch_assignments = self._assign_nodes_to_epochs(nodes, sorted_epochs)

        # Position nodes within each epoch
        current_epoch_y = 0.0
        for epoch in sorted_epochs:
            epoch_nodes_list = epoch_assignments.get(epoch.node_id, [])

            if not epoch_nodes_list:
                current_epoch_y += row_height
                continue

            # Sort nodes within epoch by temporal order
            ordered_nodes = self._order_nodes_temporally(epoch_nodes_list, G)

            # Position nodes in grid within epoch row
            y_base = current_epoch_y + 20.0  # Top padding within row
            x_current = start_x

            for i, node in enumerate(ordered_nodes):
                # Grid layout: 5 columns
                col = i % 5
                row = i // 5

                x = x_current + (col * 150.0)
                y = y_base + (row * spacing_y)

                positions[node.node_id] = (x, y)

            current_epoch_y += row_height

        return positions

    def _assign_nodes_to_epochs(
        self,
        nodes: List,
        epochs: List[EpochNode]
    ) -> Dict[str, List]:
        """
        Assign stratigraphic nodes to their corresponding epochs.

        Args:
            nodes: List of stratigraphic nodes
            epochs: List of EpochNode instances (sorted)

        Returns:
            Dictionary mapping epoch_id to list of nodes
        """
        from ...nodes.stratigraphic_node import StratigraphicNode

        assignments = {epoch.node_id: [] for epoch in epochs}

        for node in nodes:
            if not isinstance(node, StratigraphicNode):
                continue

            # Find epoch for this node
            # Check if node has epoch_id attribute
            if hasattr(node, 'epoch_id') and node.epoch_id:
                if node.epoch_id in assignments:
                    assignments[node.epoch_id].append(node)
            else:
                # Assign to most recent epoch (default)
                if epochs:
                    assignments[epochs[0].node_id].append(node)

        return assignments

    def _order_nodes_temporally(
        self,
        nodes: List,
        temporal_graph: 'nx.DiGraph'
    ) -> List:
        """
        Order nodes by temporal precedence using topological sort.

        Args:
            nodes: List of nodes to order
            temporal_graph: NetworkX DiGraph of temporal relations

        Returns:
            List of nodes ordered from most recent to most ancient
        """
        import networkx as nx

        # Create subgraph with only these nodes
        node_ids = [n.node_id for n in nodes]
        subgraph = temporal_graph.subgraph(node_ids)

        # Topological sort (most recent first)
        try:
            ordered_ids = list(nx.topological_sort(subgraph))
            # Reorder nodes based on topological sort
            id_to_node = {n.node_id: n for n in nodes}
            return [id_to_node[nid] for nid in ordered_ids if nid in id_to_node]
        except nx.NetworkXError:
            # If cycle or no edges, return as-is
            return nodes
