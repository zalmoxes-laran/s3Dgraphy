"""
Node registry for GraphML export.

Hybrid approach: loads metadata from s3Dgraphy_node_datamodel.json and
visual properties from em_palette_template.graphml.
"""

import json
import os
from typing import Dict, Tuple, Optional
from lxml import etree as ET
from dataclasses import dataclass


@dataclass
class NodeVisualProperties:
    """Visual properties for a node type."""
    shape: str
    fill_color: str
    border_color: str
    border_type: str
    border_width: float
    text_color: str


class NodeRegistry:
    """
    Registry of node definitions with metadata and visual properties.
    
    Loads from:
    - s3Dgraphy_node_datamodel.json: metadata, class, description
    - em_palette_template.graphml: shapes, colors, border styles
    """

    def __init__(self):
        """Initialize node registry by loading datamodel and palette."""
        self.datamodel: Dict = {}
        self.visual_properties: Dict[str, NodeVisualProperties] = {}
        
        self._load_datamodel()
        self._load_palette_template()

    def _load_datamodel(self):
        """Load node datamodel from JSON."""
        json_path = os.path.join(
            os.path.dirname(__file__),
            '../../JSON_config/s3Dgraphy_node_datamodel.json'
        )
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.datamodel = data.get('nodes', {})
        except FileNotFoundError:
            print(f"Warning: Node datamodel not found at {json_path}")
            self.datamodel = {}

    def _load_palette_template(self):
        """Load visual properties from palette template GraphML."""
        template_path = os.path.join(
            os.path.dirname(__file__),
            '../../templates/em_palette_template.graphml'
        )
        
        try:
            tree = ET.parse(template_path)
            root = tree.getroot()
            
            # Parse nodes from palette
            ns = {'graphml': 'http://graphml.graphdrawing.org/xmlns',
                  'y': 'http://www.yworks.com/xml/graphml'}
            
            # Node mapping from palette (based on plan analysis)
            palette_mappings = {
                'n1': 'US',      # USM01 - rectangle white/red
                'n3': 'USD',     # USD10 - roundrectangle white/orange
                'n4': 'USVs',    # USV100 - parallelogram black/blue
                'n5': 'SF',      # SF01 - octagon white/yellow
                'n6': 'VSF',     # VSF01 - octagon black/beige
                'n7': 'USVn',    # USV102 - hexagon black/green
                'n8': 'serUSVn', # USV106 series - ellipse black/green
                'n9': 'TSU',     # TSU - roundrectangle white/red dashed
                'n2': 'serSU',   # USM02 series - ellipse white/red
            }
            
            for node_id, node_type in palette_mappings.items():
                node_elem = root.find(f'.//graphml:node[@id="{node_id}"]', ns)
                if node_elem is not None:
                    visual_props = self._extract_visual_properties(node_elem, ns)
                    if visual_props:
                        self.visual_properties[node_type] = visual_props
            
            # Add serUSVs (ellipse black/blue) - similar to serUSVn but different border
            if 'serUSVn' in self.visual_properties:
                self.visual_properties['serUSVs'] = NodeVisualProperties(
                    shape='ellipse',
                    fill_color='#000000',
                    border_color='#248FE7',  # Blue instead of green
                    border_type='line',
                    border_width=4.0,
                    text_color='#FFFFFF'
                )
            
        except FileNotFoundError:
            print(f"Warning: Palette template not found at {template_path}")
            self._load_default_visual_properties()
        except Exception as e:
            print(f"Warning: Error loading palette template: {e}")
            self._load_default_visual_properties()

    def _extract_visual_properties(self, node_elem: ET.Element, ns: Dict) -> Optional[NodeVisualProperties]:
        """Extract visual properties from a palette node element."""
        try:
            # Find ShapeNode
            shape_node = node_elem.find('.//y:ShapeNode', ns)
            if shape_node is None:
                return None
            
            # Extract shape
            shape_elem = shape_node.find('.//y:Shape', ns)
            shape = shape_elem.get('type', 'rectangle') if shape_elem is not None else 'rectangle'
            
            # Extract fill color
            fill_elem = shape_node.find('.//y:Fill', ns)
            fill_color = fill_elem.get('color', '#FFFFFF') if fill_elem is not None else '#FFFFFF'
            
            # Extract border
            border_elem = shape_node.find('.//y:BorderStyle', ns)
            border_color = '#000000'
            border_type = 'line'
            border_width = 4.0
            if border_elem is not None:
                border_color = border_elem.get('color', '#000000')
                border_type = border_elem.get('type', 'line')
                border_width = float(border_elem.get('width', '4.0'))
            
            # Extract text color
            label_elem = shape_node.find('.//y:NodeLabel', ns)
            text_color = '#000000'
            if label_elem is not None:
                text_color = label_elem.get('textColor', '#000000')
            
            return NodeVisualProperties(
                shape=shape,
                fill_color=fill_color,
                border_color=border_color,
                border_type=border_type,
                border_width=border_width,
                text_color=text_color
            )
        except Exception as e:
            print(f"Warning: Error extracting visual properties: {e}")
            return None

    def _load_default_visual_properties(self):
        """Load hardcoded default visual properties as fallback."""
        self.visual_properties = {
            'US': NodeVisualProperties('rectangle', '#FFFFFF', '#9B3333', 'line', 4.0, '#000000'),
            'USVs': NodeVisualProperties('parallelogram', '#000000', '#248FE7', 'line', 4.0, '#FFFFFF'),
            'USVn': NodeVisualProperties('hexagon', '#000000', '#31792D', 'line', 4.0, '#FFFFFF'),
            'SF': NodeVisualProperties('octagon', '#FFFFFF', '#D8BD30', 'line', 4.0, '#000000'),
            'VSF': NodeVisualProperties('octagon', '#000000', '#B19F61', 'line', 4.0, '#FFFFFF'),
            'USD': NodeVisualProperties('roundrectangle', '#FFFFFF', '#D86400', 'line', 4.0, '#000000'),
            'serSU': NodeVisualProperties('ellipse', '#FFFFFF', '#9B3333', 'line', 4.0, '#000000'),
            'serUSVn': NodeVisualProperties('ellipse', '#000000', '#31792D', 'line', 4.0, '#FFFFFF'),
            'serUSVs': NodeVisualProperties('ellipse', '#000000', '#248FE7', 'line', 4.0, '#FFFFFF'),
            'TSU': NodeVisualProperties('roundrectangle', '#FFFFFF', '#9B3333', 'dashed', 4.0, '#000000'),
        }

    def get_visual_properties(self, node_type: str) -> Optional[NodeVisualProperties]:
        """
        Get visual properties for a node type.
        
        Args:
            node_type: Type code (US, USVs, USVn, etc.)
            
        Returns:
            NodeVisualProperties or None if not found
        """
        return self.visual_properties.get(node_type)

    def get_node_metadata(self, node_type: str) -> Optional[Dict]:
        """
        Get metadata for a node type from datamodel.
        
        Args:
            node_type: Type code (US, USVs, USVn, etc.)
            
        Returns:
            Metadata dict or None if not found
        """
        return self.datamodel.get(node_type)

    def get_shape_for_type(self, node_type: str) -> str:
        """Get yEd shape for node type."""
        props = self.get_visual_properties(node_type)
        return props.shape if props else 'rectangle'

    def get_colors_for_type(self, node_type: str) -> Tuple[str, str, str]:
        """
        Get colors for node type.
        
        Returns:
            (fill_color, border_color, text_color)
        """
        props = self.get_visual_properties(node_type)
        if props:
            return (props.fill_color, props.border_color, props.text_color)
        return ('#FFFFFF', '#000000', '#000000')
