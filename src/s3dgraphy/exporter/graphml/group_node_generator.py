"""
Group node generator for GraphML export.

Generates ProxyAutoBoundsNode for ParadataNodeGroup and ActivityNodeGroup.
"""

from lxml import etree as ET
from typing import List, Optional, Dict
from .node_registry import NodeRegistry
from .utils import IDManager, generate_uuid


# Group background colors (reverse engineered from import_graphml.py lines 1323-1331)
GROUP_COLORS = {
    'ParadataNodeGroup': '#FFCC99',      # Correct color for paradata
    'ActivityNodeGroup': '#CCFFFF',
    'TimeBranchNodeGroup': '#99CC00',
    'USContainer': '#9B3333',            # US group (stratigraphic container)
    'USDContainer': '#D86400'            # USD group (documentary container)
}


class GroupNodeGenerator:
    """Generates ProxyAutoBoundsNode for group nodes."""

    def __init__(self, registry: NodeRegistry, id_manager: IDManager):
        """
        Initialize group node generator.
        
        Args:
            registry: Node registry
            id_manager: ID manager for nested IDs
        """
        self.registry = registry
        self.id_manager = id_manager
        self.ns_y = 'http://www.yworks.com/xml/graphml'

    def generate_paradata_group(self, group_data: Dict, x: float = 800.0, y: float = 100.0,
                               parent_id: str = None) -> ET.Element:
        """
        Generate ProxyAutoBoundsNode for ParadataNodeGroup.

        Args:
            group_data: Dict with 'us_node', 'property_nodes', 'extractor_nodes', 'document_nodes'
            x, y: Position coordinates
            parent_id: Parent nested ID (e.g., "n0" when inside swimlane)

        Returns:
            node XML element with nested graph
        """
        us_node = group_data['us_node']
        property_nodes = group_data.get('property_nodes', [])
        extractor_nodes = group_data.get('extractor_nodes', [])
        document_nodes = group_data.get('document_nodes', [])

        # Generate group UUID and nested ID
        group_uuid = generate_uuid()
        group_nested_id = self.id_manager.get_nested_id(group_uuid, parent_id=parent_id)
        
        # Create node element
        node_elem = ET.Element('{http://graphml.graphdrawing.org/xmlns}node')
        node_elem.set('id', group_nested_id)
        node_elem.set('yfiles.foldertype', 'folder')  # "folder" for PD groups (ref: TempluMare)
        
        # Add EMID (d7)
        data_d7 = ET.SubElement(node_elem, '{http://graphml.graphdrawing.org/xmlns}data')
        data_d7.set('key', 'd7')
        data_d7.text = group_uuid
        
        # Add nodegraphics (d6) - ProxyAutoBoundsNode
        data_d6 = ET.SubElement(node_elem, '{http://graphml.graphdrawing.org/xmlns}data')
        data_d6.set('key', 'd6')
        
        proxy_node = ET.SubElement(data_d6, f'{{{self.ns_y}}}ProxyAutoBoundsNode')
        
        realizers = ET.SubElement(proxy_node, f'{{{self.ns_y}}}Realizers')
        realizers.set('active', '1')  # Closed by default (ref: TempluMare PD groups)
        
        # Realizer 0: Open state
        self._add_group_realizer(realizers, us_node, x, y, closed=False,
                                width=376.0, height=120.0)

        # Realizer 1: Closed state (same position as open, compact height)
        self._add_group_realizer(realizers, us_node, x, y, closed=True,
                                width=118.0, height=30.0)
        
        # Create nested graph for group content
        graph_elem = ET.SubElement(node_elem, '{http://graphml.graphdrawing.org/xmlns}graph')
        graph_elem.set('edgedefault', 'directed')
        graph_elem.set('id', f'{group_nested_id}:')
        
        # Add nested nodes (will be populated by main exporter)
        # Store group identifiers in group_data for later use
        group_data['group_nested_id'] = group_nested_id
        group_data['group_uuid'] = group_uuid
        
        return node_elem

    def _add_group_realizer(self, realizers: ET.Element, us_node, x: float, y: float,
                           closed: bool, width: float, height: float):
        """Add a GroupNode realizer (open or closed state)."""
        group_node = ET.SubElement(realizers, f'{{{self.ns_y}}}GroupNode')
        
        # Geometry
        geometry = ET.SubElement(group_node, f'{{{self.ns_y}}}Geometry')
        geometry.set('height', str(height))
        geometry.set('width', str(width))
        geometry.set('x', str(x))
        geometry.set('y', str(y))
        
        # Fill
        fill = ET.SubElement(group_node, f'{{{self.ns_y}}}Fill')
        fill.set('color', '#F5F5F5')
        fill.set('transparent', 'false')
        
        # BorderStyle - DASHED for ParadataNodeGroup
        border = ET.SubElement(group_node, f'{{{self.ns_y}}}BorderStyle')
        border.set('color', '#000000')
        border.set('type', 'dashed')  # Dashed border
        border.set('width', '1.0')
        
        # NodeLabel with CORRECT background color #FFCC99
        us_name = getattr(us_node, 'name', 'US')
        label_text = f'{us_name}_PD'
        
        label = ET.SubElement(group_node, f'{{{self.ns_y}}}NodeLabel')
        label.set('alignment', 'right')
        label.set('autoSizePolicy', 'node_width')
        label.set('backgroundColor', GROUP_COLORS['ParadataNodeGroup'])  # #FFCC99
        label.set('borderDistance', '0.0')
        label.set('fontSize', '15')
        label.set('fontStyle', 'plain')
        label.set('hasLineColor', 'false')
        label.set('horizontalTextPosition', 'center')
        label.set('iconTextGap', '4')
        label.set('modelName', 'internal')
        label.set('modelPosition', 't')
        label.set('textColor', '#000000')
        label.set('verticalTextPosition', 'bottom')
        label.set('visible', 'true')
        label.text = label_text
        
        # Shape
        shape = ET.SubElement(group_node, f'{{{self.ns_y}}}Shape')
        shape.set('type', 'roundrectangle')
        
        # State
        state = ET.SubElement(group_node, f'{{{self.ns_y}}}State')
        state.set('closed', 'true' if closed else 'false')
        if closed:
            state.set('closedHeight', str(height))
            state.set('closedWidth', str(width))
        
        # Insets
        insets = ET.SubElement(group_node, f'{{{self.ns_y}}}Insets')
        if closed:
            insets.set('bottom', '5')
            insets.set('left', '5')
            insets.set('right', '5')
            insets.set('top', '5')
        else:
            insets.set('bottom', '15')
            insets.set('left', '15')
            insets.set('right', '15')
            insets.set('top', '15')

    def generate_activity_group(self, group_data: Dict, x: float = 100.0, y: float = 100.0) -> ET.Element:
        """
        Generate ProxyAutoBoundsNode for ActivityNodeGroup.

        Similar to ParadataNodeGroup but with different background color (#CCFFFF).

        Args:
            group_data: Dict with group information
            x, y: Position coordinates

        Returns:
            node XML element
        """
        # Similar structure to paradata group but with ActivityNodeGroup color
        # Implementation would be similar to generate_paradata_group but with #CCFFFF
        pass

    def generate_us_container_group(self, container_node, child_nodes: List,
                                     x: float = 100.0, y: float = 100.0,
                                     parent_id: str = None) -> ET.Element:
        """
        Generate ProxyAutoBoundsNode for a US/USD container.

        A US/USD container is a regular StratigraphicUnit or DocumentaryStratigraphicUnit
        that has has_part edges. In GraphML, it is rendered as a yEd group node with the
        appropriate background color (#9B3333 for US, #D86400 for USD).

        Args:
            container_node: The US or USD node that acts as container
            child_nodes: List of child nodes contained in the container
            x, y: Position coordinates
            parent_id: Parent nested ID (e.g., "n0" when inside swimlane)

        Returns:
            node XML element with nested graph
        """
        # Determine container type from node_type
        node_type = getattr(container_node, 'node_type', 'US')
        if node_type == 'USD':
            bg_color = GROUP_COLORS['USDContainer']
        else:
            bg_color = GROUP_COLORS['USContainer']

        container_uuid = container_node.node_id
        group_nested_id = self.id_manager.get_nested_id(container_uuid, parent_id=parent_id)

        # Create node element
        node_elem = ET.Element('{http://graphml.graphdrawing.org/xmlns}node')
        node_elem.set('id', group_nested_id)
        node_elem.set('yfiles.foldertype', 'group')

        # Add EMID
        data_emid = ET.SubElement(node_elem, '{http://graphml.graphdrawing.org/xmlns}data')
        data_emid.set('key', 'd7')
        data_emid.text = container_uuid

        # Add nodegraphics - ProxyAutoBoundsNode
        data_gfx = ET.SubElement(node_elem, '{http://graphml.graphdrawing.org/xmlns}data')
        data_gfx.set('key', 'd6')

        proxy_node = ET.SubElement(data_gfx, f'{{{self.ns_y}}}ProxyAutoBoundsNode')
        realizers = ET.SubElement(proxy_node, f'{{{self.ns_y}}}Realizers')
        realizers.set('active', '0')  # Open by default

        # Realizer 0: Open state
        self._add_container_realizer(
            realizers, container_node.name, bg_color, x, y,
            closed=False, width=224.0, height=222.0
        )
        # Realizer 1: Closed state
        self._add_container_realizer(
            realizers, container_node.name, bg_color, x, y,
            closed=True, width=105.0, height=70.0
        )

        # Create nested graph for child nodes
        graph_elem = ET.SubElement(node_elem, '{http://graphml.graphdrawing.org/xmlns}graph')
        graph_elem.set('edgedefault', 'directed')
        graph_elem.set('id', f'{group_nested_id}:')

        return node_elem

    def _add_container_realizer(self, realizers: ET.Element, label_text: str,
                                 bg_color: str, x: float, y: float,
                                 closed: bool, width: float, height: float):
        """Add a GroupNode realizer for US/USD container (open or closed state)."""
        group_node = ET.SubElement(realizers, f'{{{self.ns_y}}}GroupNode')

        geometry = ET.SubElement(group_node, f'{{{self.ns_y}}}Geometry')
        geometry.set('height', str(height))
        geometry.set('width', str(width))
        geometry.set('x', str(x))
        geometry.set('y', str(y))

        fill = ET.SubElement(group_node, f'{{{self.ns_y}}}Fill')
        fill.set('color', '#F5F5F5')
        fill.set('transparent', 'false')

        border = ET.SubElement(group_node, f'{{{self.ns_y}}}BorderStyle')
        border.set('color', '#000000')
        border.set('type', 'dashed')
        border.set('width', '1.0')

        label = ET.SubElement(group_node, f'{{{self.ns_y}}}NodeLabel')
        label.set('alignment', 'right')
        label.set('autoSizePolicy', 'node_width')
        label.set('backgroundColor', bg_color)
        label.set('borderDistance', '0.0')
        label.set('fontSize', '15')
        label.set('fontStyle', 'plain')
        label.set('hasLineColor', 'false')
        label.set('horizontalTextPosition', 'center')
        label.set('iconTextGap', '4')
        label.set('modelName', 'internal')
        label.set('modelPosition', 't')
        label.set('textColor', '#FFFFFF' if not closed else '#000000')
        label.set('verticalTextPosition', 'bottom')
        label.set('visible', 'true')
        label.text = label_text

        shape = ET.SubElement(group_node, f'{{{self.ns_y}}}Shape')
        shape.set('type', 'roundrectangle')

        state = ET.SubElement(group_node, f'{{{self.ns_y}}}State')
        state.set('closed', 'true' if closed else 'false')
        if closed:
            state.set('closedHeight', str(height))
            state.set('closedWidth', str(width))

        insets = ET.SubElement(group_node, f'{{{self.ns_y}}}Insets')
        if closed:
            insets.set('bottom', '5')
            insets.set('left', '5')
            insets.set('right', '5')
            insets.set('top', '5')
        else:
            insets.set('bottom', '15')
            insets.set('left', '15')
            insets.set('right', '15')
            insets.set('top', '15')
