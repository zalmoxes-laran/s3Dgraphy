"""
Epoch Swimlanes Generator for GraphML Export

Generates yEd TableNode structures to represent temporal epochs as horizontal swimlanes.
Matches the structure from the TempluMare reference GraphML (YED_TABLE_NODE configuration).
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
        self.NS_GRAPHML = "http://graphml.graphdrawing.org/xmlns"
        self.NS_YFILES = "http://www.yworks.com/xml/graphml"

    def generate_tablenode_xml(
        self,
        epoch_nodes: List[EpochNode],
        graph,
        swimlane_id: str = "n0",
        canvas_width: float = 2600.0,
        canvas_height: float = 2300.0,
        row_height: float = 150.0
    ) -> ET.Element:
        """
        Generate a TableNode XML element for epoch swimlanes.

        Matches the TempluMare reference structure with YED_TABLE_NODE configuration.

        Args:
            epoch_nodes: List of EpochNode instances
            graph: s3dgraphy Graph object (for context)
            swimlane_id: Node ID for the TableNode (default "n0")
            canvas_width: Total width of the canvas
            canvas_height: Total height of the canvas
            row_height: Default height of each epoch row

        Returns:
            ET.Element: TableNode XML element with nested graph
        """
        # Sort epochs by start time (most recent first)
        sorted_epochs = self._sort_epochs_by_time(epoch_nodes)

        # Calculate total height needed
        total_height = len(sorted_epochs) * row_height + 100  # +100 for padding
        if total_height > canvas_height:
            canvas_height = total_height

        # Create TableNode root element
        tablenode = ET.Element(
            qname(self.NS_GRAPHML, "node"),
            id=swimlane_id
        )
        tablenode.set("yfiles.foldertype", "group")

        # Add EMID (d7 for nodes)
        data_emid = ET.SubElement(tablenode, qname(self.NS_GRAPHML, "data"))
        data_emid.set("key", "d7")
        data_emid.text = generate_uuid()

        # Add description (d5)
        data_desc = ET.SubElement(tablenode, qname(self.NS_GRAPHML, "data"))
        data_desc.set("key", "d5")
        data_desc.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        data_desc.text = "Stratigrafia"

        # Add graphics data (d6) — TableNode structure
        data_graphics = ET.SubElement(tablenode, qname(self.NS_GRAPHML, "data"))
        data_graphics.set("key", "d6")

        y_tablenode = ET.SubElement(
            data_graphics,
            qname(self.NS_YFILES, "TableNode"),
            configuration="YED_TABLE_NODE"
        )

        # Geometry
        geometry = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "Geometry"))
        geometry.set("height", str(canvas_height))
        geometry.set("width", str(canvas_width))
        geometry.set("x", "-29.0")
        geometry.set("y", "-35.0")

        # Fill
        fill = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "Fill"))
        fill.set("color", "#ECF5FF")
        fill.set("color2", "#0042F440")
        fill.set("transparent", "false")

        # BorderStyle
        border = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "BorderStyle"))
        border.set("hasColor", "false")
        border.set("type", "line")
        border.set("width", "1.0")

        # Main title label (site/graph name)
        graph_name = graph.name.get("en", "Archaeological Site") if hasattr(graph, 'name') and isinstance(graph.name, dict) else "Archaeological Site"
        graph_id = graph.graph_id if hasattr(graph, 'graph_id') else "unknown"
        title_label = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "NodeLabel"))
        title_label.set("alignment", "center")
        title_label.set("autoSizePolicy", "content")
        title_label.set("fontFamily", "Dialog")
        title_label.set("fontSize", "15")
        title_label.set("fontStyle", "plain")
        title_label.set("hasBackgroundColor", "false")
        title_label.set("hasLineColor", "false")
        title_label.set("horizontalTextPosition", "center")
        title_label.set("iconTextGap", "4")
        title_label.set("modelName", "internal")
        title_label.set("modelPosition", "t")
        title_label.set("textColor", "#000000")
        title_label.set("verticalTextPosition", "bottom")
        title_label.set("visible", "true")
        title_label.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        title_label.text = f"{graph_name} [ID:{graph_id}]"

        # Epoch row labels (one per epoch, rotated 270°)
        for row_index, epoch in enumerate(sorted_epochs):
            row_label = self._generate_epoch_label(epoch, row_height, row_index)
            y_tablenode.append(row_label)

        # StyleProperties (yEd table painter styles)
        self._add_style_properties(y_tablenode)

        # State
        state = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "State"))
        state.set("autoResize", "true")
        state.set("closed", "false")
        state.set("closedHeight", "80.0")
        state.set("closedWidth", "100.0")

        # Insets
        insets = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "Insets"))
        insets.set("bottom", "0")
        insets.set("bottomF", "0.0")
        insets.set("left", "0")
        insets.set("leftF", "0.0")
        insets.set("right", "0")
        insets.set("rightF", "0.0")
        insets.set("top", "0")
        insets.set("topF", "0.0")

        # BorderInsets
        border_insets = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "BorderInsets"))
        border_insets.set("bottom", "15")
        border_insets.set("bottomF", "15.0")
        border_insets.set("left", "5")
        border_insets.set("leftF", "5.0")
        border_insets.set("right", "25")
        border_insets.set("rightF", "25.0")
        border_insets.set("top", "5")
        border_insets.set("topF", "5.0")

        # Table structure
        y_table = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "Table"))
        y_table.set("autoResizeTable", "true")
        y_table.set("defaultColumnWidth", "120.0")
        y_table.set("defaultMinimumColumnWidth", "80.0")
        y_table.set("defaultMinimumRowHeight", "50.0")
        y_table.set("defaultRowHeight", "80.0")

        # DefaultColumnInsets
        dc_insets = ET.SubElement(y_table, qname(self.NS_YFILES, "DefaultColumnInsets"))
        dc_insets.set("bottom", "0.0")
        dc_insets.set("left", "0.0")
        dc_insets.set("right", "0.0")
        dc_insets.set("top", "0.0")

        # DefaultRowInsets
        dr_insets = ET.SubElement(y_table, qname(self.NS_YFILES, "DefaultRowInsets"))
        dr_insets.set("bottom", "0.0")
        dr_insets.set("left", "24.0")
        dr_insets.set("right", "0.0")
        dr_insets.set("top", "0.0")

        # Table Insets
        t_insets = ET.SubElement(y_table, qname(self.NS_YFILES, "Insets"))
        t_insets.set("bottom", "0.0")
        t_insets.set("left", "0.0")
        t_insets.set("right", "0.0")
        t_insets.set("top", "30.0")

        # Columns (single column)
        columns = ET.SubElement(y_table, qname(self.NS_YFILES, "Columns"))
        column = ET.SubElement(columns, qname(self.NS_YFILES, "Column"))
        column.set("id", "column_0")
        column.set("minimumWidth", "80.0")
        column.set("width", str(canvas_width - 40.0))
        col_insets = ET.SubElement(column, qname(self.NS_YFILES, "Insets"))
        col_insets.set("bottom", "0.0")
        col_insets.set("left", "0.0")
        col_insets.set("right", "0.0")
        col_insets.set("top", "0.0")

        # Rows
        rows_elem = ET.SubElement(y_table, qname(self.NS_YFILES, "Rows"))
        for row_index, epoch in enumerate(sorted_epochs):
            row_elem = self._generate_epoch_row(epoch, row_height, row_index)
            rows_elem.append(row_elem)

        # Create nested graph element for nodes inside swimlane
        nested_graph = ET.SubElement(tablenode, qname(self.NS_GRAPHML, "graph"))
        nested_graph.set("edgedefault", "directed")
        nested_graph.set("id", f"{swimlane_id}:")

        return tablenode

    def _add_style_properties(self, y_tablenode: ET.Element):
        """Add yEd table painter style properties."""
        style_props = ET.SubElement(y_tablenode, qname(self.NS_YFILES, "StyleProperties"))

        props = [
            ("y.view.tabular.TableNodePainter.ALTERNATE_ROW_STYLE", None,
             {"fillColor": "#474A4340", "lineColor": "#000000", "lineType": "line", "lineWidth": "1.0"}),
            ("y.view.tabular.TableNodePainter.ALTERNATE_COLUMN_SELECTION_STYLE", None,
             {"fillColor": "#474A4380", "lineColor": "#000000", "lineType": "line", "lineWidth": "3.0"}),
            ("y.view.tabular.TableNodePainter.ALTERNATE_ROW_SELECTION_STYLE", None,
             {"fillColor": "#474A4380", "lineColor": "#000000", "lineType": "line", "lineWidth": "3.0"}),
            ("yed.table.section.color", "java.awt.Color", "#7192b2"),
            ("yed.table.header.height", "java.lang.Double", "24.0"),
            ("yed.table.header.font.size", "java.lang.Integer", "12"),
            ("yed.table.lane.color.main", "java.awt.Color", "#c4d7ed"),
            ("yed.table.lane.color.alternating", "java.awt.Color", "#abc8e2"),
            ("yed.table.header.color.alternating", "java.awt.Color", "#abc8e2"),
            ("yed.table.lane.style", "java.lang.String", "lane.style.rows"),
            ("y.view.tabular.TableNodePainter.ALTERNATE_COLUMN_STYLE", None,
             {"fillColor": "#474A4340", "lineColor": "#000000", "lineType": "line", "lineWidth": "1.0"}),
            ("yed.table.header.color.main", "java.awt.Color", "#c4d7ed"),
        ]

        for prop_data in props:
            prop = ET.SubElement(style_props, qname(self.NS_YFILES, "Property"))
            prop.set("name", prop_data[0])

            if prop_data[1] is not None:
                # Simple value property
                prop.set("class", prop_data[1])
                prop.set("value", prop_data[2])
            else:
                # SimpleStyle sub-element
                simple_style = ET.SubElement(prop, qname(self.NS_YFILES, "SimpleStyle"))
                for attr_name, attr_value in prop_data[2].items():
                    simple_style.set(attr_name, attr_value)

    def _sort_epochs_by_time(self, epoch_nodes: List[EpochNode]) -> List[EpochNode]:
        """
        Sort epoch nodes by start time (most recent first).

        Args:
            epoch_nodes: List of EpochNode instances

        Returns:
            Sorted list of EpochNode instances
        """
        def get_start_time(epoch: EpochNode) -> float:
            """Extract start time, handling None values."""
            if hasattr(epoch, 'start_time') and epoch.start_time is not None:
                return epoch.start_time
            return 0.0

        return sorted(epoch_nodes, key=get_start_time, reverse=True)

    def _generate_epoch_row(
        self,
        epoch: EpochNode,
        height: float,
        row_index: int
    ) -> ET.Element:
        """
        Generate a Row element for a single epoch.

        Args:
            epoch: EpochNode instance
            height: Row height
            row_index: Index of this row (0, 1, 2...)

        Returns:
            ET.Element: Row XML element
        """
        row = ET.Element(qname(self.NS_YFILES, "Row"))
        row.set("id", f"row_{row_index}")
        row.set("height", str(height))
        row.set("minimumHeight", "50.0")

        # Insets (left padding for label area)
        insets = ET.SubElement(row, qname(self.NS_YFILES, "Insets"))
        insets.set("bottom", "0.0")
        insets.set("left", "24.0")
        insets.set("right", "0.0")
        insets.set("top", "0.0")

        return row

    def _generate_epoch_label(
        self,
        epoch: EpochNode,
        row_height: float,
        row_index: int
    ) -> ET.Element:
        """
        Generate a NodeLabel for an epoch row with full yEd attributes.

        Matches the TempluMare reference format exactly:
        - rotationAngle="270.0" (vertical text)
        - RowNodeLabelModel with offset
        - RowNodeLabelModelParameter with row_X id

        Args:
            epoch: EpochNode instance
            row_height: Height of the row
            row_index: Index of this row (for row_0, row_1, etc.)

        Returns:
            ET.Element: NodeLabel XML element
        """
        label = ET.Element(qname(self.NS_YFILES, "NodeLabel"))

        # All attributes matching the reference
        label.set("alignment", "center")
        label.set("autoSizePolicy", "content")

        # Background color: use epoch color if set, else default green
        bg_color = epoch.color if hasattr(epoch, 'color') and epoch.color != "#FFFFFF" else "#CCFFCC"
        label.set("backgroundColor", bg_color)

        label.set("fontFamily", "Dialog")
        label.set("fontSize", "12")
        label.set("fontStyle", "plain")
        label.set("hasLineColor", "false")
        label.set("horizontalTextPosition", "center")
        label.set("iconTextGap", "4")
        label.set("modelName", "custom")
        label.set("rotationAngle", "270.0")  # CRITICAL: vertical text
        label.set("textColor", "#000000")
        label.set("verticalTextPosition", "bottom")
        label.set("visible", "true")
        label.set("x", "3.0")
        label.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

        # Label text: "EpochName [start:X;end:Y]"
        # Use start_time/end_time (NOT start/end which don't exist on EpochNode)
        start = epoch.start_time if epoch.start_time is not None else "?"
        end = epoch.end_time if epoch.end_time is not None else "?"

        # Format as integer if it's a float with no decimals
        if isinstance(start, float) and start == int(start):
            start = int(start)
        if isinstance(end, float) and end == int(end):
            end = int(end)

        label.text = f"{epoch.name} [start:{start};end:{end}]"

        # LabelModel (inside the label element)
        label_model_elem = ET.SubElement(label, qname(self.NS_YFILES, "LabelModel"))
        row_label_model = ET.SubElement(label_model_elem, qname(self.NS_YFILES, "RowNodeLabelModel"))
        row_label_model.set("offset", "3.0")

        # ModelParameter (inside the label element)
        model_param_elem = ET.SubElement(label, qname(self.NS_YFILES, "ModelParameter"))
        param = ET.SubElement(model_param_elem, qname(self.NS_YFILES, "RowNodeLabelModelParameter"))
        param.set("horizontalPosition", "0.0")
        param.set("id", f"row_{row_index}")
        param.set("inside", "true")

        return label

    def calculate_epoch_positions(
        self,
        nodes: List,
        epoch_nodes: List[EpochNode],
        temporal_edges: List[Tuple[str, str]],
        row_height: float = 150.0,
        start_x: float = 100.0,
        spacing_x: float = 150.0
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculate positions for stratigraphic nodes within epoch swimlanes.

        Positions nodes based on:
        1. Temporal epoch assignment (via has_first_epoch edges)
        2. Temporal ordering within epoch (using temporal_edges)

        The y-coordinate determines which row a node appears in.
        Rows are ordered top-to-bottom by most-recent-first.

        Args:
            nodes: List of stratigraphic nodes
            epoch_nodes: List of EpochNode instances
            temporal_edges: List of (source, target) temporal edges
            row_height: Height of each epoch row
            start_x: Starting X coordinate for nodes
            spacing_x: Horizontal spacing between nodes

        Returns:
            Dictionary mapping node_id to (x, y) coordinates
        """
        from ...nodes.stratigraphic_node import StratigraphicNode
        import networkx as nx

        positions = {}

        # Sort epochs by time (most recent first)
        sorted_epochs = self._sort_epochs_by_time(epoch_nodes)

        # Build temporal graph for ordering
        G = nx.DiGraph()
        G.add_edges_from(temporal_edges)

        # Assign nodes to epochs
        epoch_assignments = self._assign_nodes_to_epochs(nodes, sorted_epochs)

        # Position nodes within each epoch
        current_epoch_y = 50.0  # Start after header
        for epoch in sorted_epochs:
            epoch_nodes_list = epoch_assignments.get(epoch.node_id, [])

            if not epoch_nodes_list:
                current_epoch_y += row_height
                continue

            # Sort nodes within epoch by temporal order
            ordered_nodes = self._order_nodes_temporally(epoch_nodes_list, G)

            # Position nodes in grid within epoch row
            y_center = current_epoch_y + (row_height / 2.0)  # Center in row
            x_current = start_x + 30.0  # Left padding

            for i, node in enumerate(ordered_nodes):
                # Grid layout: wrap to new row after 8 nodes
                col = i % 8
                row = i // 8

                x = x_current + (col * spacing_x)
                y = y_center - 15.0 + (row * 50.0)  # -15 to center 30px nodes

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

        Uses the graph edges (has_first_epoch) to find which epoch each node belongs to.

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

            # Check if node has epoch_id attribute (set during import)
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
            id_to_node = {n.node_id: n for n in nodes}
            return [id_to_node[nid] for nid in ordered_ids if nid in id_to_node]
        except nx.NetworkXError:
            # If cycle or no edges, return as-is
            return nodes
