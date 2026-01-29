"""
GroupNode Generator for Extended Matrix GraphML Export.

Generates yEd ProxyAutoBoundsNode elements for ParadataNodeGroup,
ActivityNodeGroup, and TimeBranchNodeGroup.

Based on reverse engineering of TempluMare_EM_converted_converted.graphml.
"""

from typing import List, Tuple, Optional
from lxml import etree as ET


class GroupNodeGenerator:
    """Generate yEd ProxyAutoBoundsNode for various group types."""

    # yFiles namespace
    YFILES_NS = "http://www.yworks.com/xml/graphml"

    # Group type color mappings (from importer analysis)
    GROUP_COLORS = {
        'ParadataNodeGroup': '#FFCC99',      # Orange
        'ActivityNodeGroup': '#CCFFFF',      # Cyan
        'TimeBranchNodeGroup': '#99CC00',    # Green
        'GroupNode': '#F5F5F5'               # Default gray
    }

    def __init__(self):
        """Initialize the GroupNode generator."""
        self.ns_map = {'y': self.YFILES_NS}

    def generate_group_node(
        self,
        node_id: str,
        group_type: str,
        label: str,
        x: float,
        y: float,
        width: float = 200.0,
        height: float = 150.0,
        closed: bool = False
    ) -> ET.Element:
        """
        Generate ProxyAutoBoundsNode XML element.

        Args:
            node_id: Node ID following nesting pattern (e.g., "n0::n3::n3")
            group_type: Type of group (ParadataNodeGroup, ActivityNodeGroup, etc.)
            label: Display label for the group
            x: X coordinate
            y: Y coordinate
            width: Group width (auto-calculated from content in yEd)
            height: Group height (auto-calculated from content in yEd)
            closed: Whether group starts in closed state

        Returns:
            lxml Element representing the GroupNode
        """
        # Create root node element
        node = ET.Element(
            'node',
            id=node_id,
            attrib={'{http://www.yworks.com/xml/graphml}foldertype': 'folder'}
        )

        # Create data element for d6 (node graphics)
        data = ET.SubElement(node, 'data', key='d6')

        # Create ProxyAutoBoundsNode
        proxy_node = ET.SubElement(
            data,
            '{%s}ProxyAutoBoundsNode' % self.YFILES_NS
        )

        # Realizers (dual state: open and closed)
        realizers = ET.SubElement(
            proxy_node,
            '{%s}Realizers' % self.YFILES_NS,
            active='1' if closed else '0'  # 0 = open, 1 = closed
        )

        # Open state realizer
        self._create_group_node_realizer(
            realizers,
            group_type,
            label,
            x, y, width, height,
            closed=False
        )

        # Closed state realizer (compact representation)
        closed_width = min(width, 118.6)
        closed_height = min(height, 87.5)
        self._create_group_node_realizer(
            realizers,
            group_type,
            label,
            x, y, closed_width, closed_height,
            closed=True
        )

        # Create nested graph for group contents
        graph = ET.SubElement(node, 'graph')
        graph.set('edgedefault', 'directed')
        graph.set('id', f"{node_id}:")

        return node

    def _create_group_node_realizer(
        self,
        parent: ET.Element,
        group_type: str,
        label: str,
        x: float,
        y: float,
        width: float,
        height: float,
        closed: bool
    ) -> ET.Element:
        """
        Create a single GroupNode realizer (open or closed state).

        Args:
            parent: Parent Realizers element
            group_type: Type of group
            label: Display label
            x, y, width, height: Geometry
            closed: Whether this is the closed state

        Returns:
            GroupNode element
        """
        group_node = ET.SubElement(parent, '{%s}GroupNode' % self.YFILES_NS)

        # Geometry
        geometry = ET.SubElement(group_node, '{%s}Geometry' % self.YFILES_NS)
        geometry.set('height', f"{height:.1f}")
        geometry.set('width', f"{width:.1f}")
        geometry.set('x', f"{x:.1f}")
        geometry.set('y', f"{y:.1f}")

        # Fill (background color based on group type)
        fill = ET.SubElement(group_node, '{%s}Fill' % self.YFILES_NS)
        fill.set('color', '#F5F5F5')  # Group background always light gray
        fill.set('transparent', 'false')

        # Border style
        border = ET.SubElement(group_node, '{%s}BorderStyle' % self.YFILES_NS)
        border.set('color', '#000000')
        border.set('type', 'dashed')
        border.set('width', '1.0')

        # Node label with color-coded background
        node_label = ET.SubElement(group_node, '{%s}NodeLabel' % self.YFILES_NS)
        node_label.set('alignment', 'right')
        node_label.set('autoSizePolicy', 'node_width')
        node_label.set('backgroundColor', self.GROUP_COLORS.get(group_type, '#F5F5F5'))
        node_label.set('borderDistance', '0.0')
        node_label.set('fontFamily', 'Dialog')
        node_label.set('fontSize', '15')
        node_label.set('fontStyle', 'plain')
        node_label.set('hasLineColor', 'false')
        node_label.set('height', '21.666015625')
        node_label.set('horizontalTextPosition', 'center')
        node_label.set('iconTextGap', '4')
        node_label.set('modelName', 'internal')
        node_label.set('modelPosition', 't')  # Top
        node_label.set('textColor', '#000000')
        node_label.set('verticalTextPosition', 'bottom')
        node_label.set('visible', 'true')
        node_label.set('width', f"{width:.1f}")
        node_label.set('x', '0.0')
        node_label.set('y', '0.0')
        node_label.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        node_label.text = label

        # Shape
        shape = ET.SubElement(group_node, '{%s}Shape' % self.YFILES_NS)
        shape.set('type', 'roundrectangle')

        # State
        state = ET.SubElement(group_node, '{%s}State' % self.YFILES_NS)
        state.set('closed', 'true' if closed else 'false')
        state.set('closedHeight', f"{height:.1f}")
        state.set('closedWidth', f"{width:.1f}")
        state.set('innerGraphDisplayEnabled', 'false')

        # Insets (padding)
        insets = ET.SubElement(group_node, '{%s}Insets' % self.YFILES_NS)
        if closed:
            # Closed state has smaller insets
            insets.set('bottom', '5')
            insets.set('bottomF', '5.0')
            insets.set('left', '5')
            insets.set('leftF', '5.0')
            insets.set('right', '5')
            insets.set('rightF', '5.0')
            insets.set('top', '5')
            insets.set('topF', '5.0')
        else:
            # Open state has larger insets
            insets.set('bottom', '15')
            insets.set('bottomF', '15.0')
            insets.set('left', '15')
            insets.set('leftF', '15.0')
            insets.set('right', '15')
            insets.set('rightF', '15.0')
            insets.set('top', '15')
            insets.set('topF', '15.0')

        # Border insets
        border_insets = ET.SubElement(group_node, '{%s}BorderInsets' % self.YFILES_NS)
        border_insets.set('bottom', '0')
        border_insets.set('bottomF', '0.0')
        border_insets.set('left', '0')
        border_insets.set('leftF', '0.0')
        border_insets.set('right', '0')
        border_insets.set('rightF', '0.0')
        border_insets.set('top', '0')
        border_insets.set('topF', '0.0')

        return group_node

    def calculate_group_bounds(
        self,
        member_nodes: List[Tuple[float, float, float, float]],
        padding: float = 20.0
    ) -> Tuple[float, float, float, float]:
        """
        Calculate bounding box for group based on member node positions.

        Args:
            member_nodes: List of (x, y, width, height) tuples for each member
            padding: Padding around member nodes

        Returns:
            Tuple of (x, y, width, height) for the group bounding box
        """
        if not member_nodes:
            # Default size if no members
            return (0.0, 0.0, 200.0, 150.0)

        # Find min/max coordinates
        min_x = min(node[0] for node in member_nodes)
        min_y = min(node[1] for node in member_nodes)
        max_x = max(node[0] + node[2] for node in member_nodes)
        max_y = max(node[1] + node[3] for node in member_nodes)

        # Calculate bounds with padding
        x = min_x - padding
        y = min_y - padding - 25.0  # Extra padding for header
        width = (max_x - min_x) + (2 * padding)
        height = (max_y - min_y) + (2 * padding) + 25.0

        return (x, y, width, height)

    @staticmethod
    def generate_node_id(parent_id: str, index: int) -> str:
        """
        Generate nested node ID following EM pattern.

        Args:
            parent_id: Parent node ID (e.g., "n0::n3")
            index: Child index

        Returns:
            Nested ID (e.g., "n0::n3::n5")
        """
        return f"{parent_id}::n{index}"

    @staticmethod
    def generate_graph_id(node_id: str) -> str:
        """
        Generate graph ID from node ID.

        Args:
            node_id: Node ID (e.g., "n0::n3::n3")

        Returns:
            Graph ID (e.g., "n0::n3::n3:")
        """
        return f"{node_id}:"
