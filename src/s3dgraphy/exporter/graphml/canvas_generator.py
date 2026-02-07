"""
Canvas generator for GraphML export.

Generates root XML structure with correct namespaces and key definitions.
"""

from lxml import etree as ET
from typing import Dict


class CanvasGenerator:
    """Generates GraphML canvas with namespaces and key definitions."""

    # Namespace definitions
    NS = {
        None: 'http://graphml.graphdrawing.org/xmlns',  # Default namespace
        'y': 'http://www.yworks.com/xml/graphml',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    def __init__(self):
        """Initialize canvas generator."""
        pass

    def generate_root(self) -> ET.Element:
        """
        Generate root GraphML element with namespaces and key definitions.

        Returns:
            Root element with complete structure
        """
        # Create root element with namespaces
        root = ET.Element(
            '{http://graphml.graphdrawing.org/xmlns}graphml',
            nsmap=self.NS,
            attrib={
                '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation':
                'http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd'
            }
        )

        # Add key definitions for NODES (d4-d8)
        self._add_node_keys(root)

        # Add key definitions for EDGES (d10-d12)
        self._add_edge_keys(root)

        # Add resources key (for SVG content)
        self._add_resources_key(root)

        # Create main graph element
        graph = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}graph')
        graph.set('id', 'G')
        graph.set('edgedefault', 'directed')

        return root

    def _add_node_keys(self, root: ET.Element):
        """Add key definitions for nodes (d4-d8)."""
        # d4: url
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'url')
        key.set('attr.type', 'string')
        key.set('for', 'node')
        key.set('id', 'd4')

        # d5: description
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'description')
        key.set('attr.type', 'string')
        key.set('for', 'node')
        key.set('id', 'd5')

        # d6: nodegraphics (yfiles)
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('for', 'node')
        key.set('id', 'd6')
        key.set('{http://www.yworks.com/xml/yfiles-common/1.0/java}type', 'nodegraphics')
        key.set('yfiles.type', 'nodegraphics')

        # d7: EMID (UUID for nodes)
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'EMID')
        key.set('attr.type', 'string')
        key.set('for', 'node')
        key.set('id', 'd7')

        # d8: URI (for nodes)
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'URI')
        key.set('attr.type', 'string')
        key.set('for', 'node')
        key.set('id', 'd8')

    def _add_edge_keys(self, root: ET.Element):
        """Add key definitions for edges (d10-d12)."""
        # d10: edgegraphics (yfiles)
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('for', 'edge')
        key.set('id', 'd10')
        key.set('{http://www.yworks.com/xml/yfiles-common/1.0/java}type', 'edgegraphics')
        key.set('yfiles.type', 'edgegraphics')

        # d11: EMID (UUID for edges) - SEPARATE FROM NODES
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'EMID')
        key.set('attr.type', 'string')
        key.set('for', 'edge')
        key.set('id', 'd11')

        # d12: URI (for edges) - SEPARATE FROM NODES
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'URI')
        key.set('attr.type', 'string')
        key.set('for', 'edge')
        key.set('id', 'd12')

    def _add_resources_key(self, root: ET.Element):
        """Add resources key for SVG content."""
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('for', 'graphml')
        key.set('id', 'd9')
        key.set('yfiles.type', 'resources')

    def generate_svg_resources(self) -> ET.Element:
        """
        Generate SVG resources section for ExtractorNode icons.

        Returns:
            Resources data element with SVG content
        """
        data = ET.Element('{http://graphml.graphdrawing.org/xmlns}data')
        data.set('key', 'd9')

        resources = ET.SubElement(data, '{http://www.yworks.com/xml/graphml}Resources')

        # SVG Resource 1: Continuity node (BR)
        resource1 = ET.SubElement(resources, '{http://www.yworks.com/xml/graphml}Resource')
        resource1.set('id', '1')
        resource1.text = self._get_continuity_svg()

        # SVG Resource 2: Combiner node (C.)
        resource2 = ET.SubElement(resources, '{http://www.yworks.com/xml/graphml}Resource')
        resource2.set('id', '2')
        resource2.text = self._get_combiner_svg()

        # SVG Resource 3: Document node (D.)
        resource3 = ET.SubElement(resources, '{http://www.yworks.com/xml/graphml}Resource')
        resource3.set('id', '3')
        resource3.text = self._get_document_extractor_svg()

        return data

    def _get_continuity_svg(self) -> str:
        """SVG content for continuity node (BR)."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26.456684 26.456684">
  <circle cx="13.228342" cy="13.228342" r="10" fill="#CCCCFF" stroke="#000000" stroke-width="1"/>
  <line x1="13.228342" y1="3.228342" x2="13.228342" y2="23.228342" stroke="#000000" stroke-width="2"/>
</svg>'''

    def _get_combiner_svg(self) -> str:
        """SVG content for combiner node (C.)."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 25 25">
  <rect x="0" y="0" width="25" height="25" fill="#CCCCFF" stroke="#000000" stroke-width="1"/>
  <circle cx="12.5" cy="12.5" r="8" fill="none" stroke="#000000" stroke-width="1.5"/>
  <line x1="7" y1="12.5" x2="18" y2="12.5" stroke="#000000" stroke-width="1.5"/>
  <line x1="12.5" y1="7" x2="12.5" y2="18" stroke="#000000" stroke-width="1.5"/>
</svg>'''

    def _get_document_extractor_svg(self) -> str:
        """SVG content for document extractor node (D.)."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 25 25">
  <rect x="0" y="0" width="25" height="25" fill="#CCCCFF" stroke="#000000" stroke-width="1"/>
  <path d="M 8 6 L 8 19 L 17 19 L 17 10 L 13 6 Z" fill="white" stroke="#000000" stroke-width="1"/>
  <path d="M 13 6 L 13 10 L 17 10" fill="#E0E0E0" stroke="#000000" stroke-width="1"/>
</svg>'''
