"""
Canvas Generator for GraphML Export

Generates the root GraphML XML structure with proper namespaces and key definitions
compatible with yEd and Extended Matrix.
"""

from lxml import etree as ET


class CanvasGenerator:
    """
    Generates the root canvas structure for GraphML files.

    Creates the <graphml> root element with:
    - Proper XML namespaces (graphml, yfiles, xsi)
    - Key definitions for node/edge attributes
    - Root <graph> element
    """

    # XML Namespaces
    NS_GRAPHML = "http://graphml.graphdrawing.org/xmlns"
    NS_YFILES = "http://www.yworks.com/xml/graphml"
    NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
    NS_YED = "http://www.yworks.com/xml/yed/3"
    NS_JAVA = "http://www.yworks.com/xml/yfiles-common/1.0/java"
    NS_SYS = "http://www.yworks.com/xml/yfiles-common/markup/primitives/2.0"
    NS_X = "http://www.yworks.com/xml/yfiles-common/markup/2.0"

    # Namespace map for lxml
    NSMAP = {
        None: NS_GRAPHML,  # Default namespace
        'y': NS_YFILES,
        'xsi': NS_XSI,
        'yed': NS_YED,
        'java': NS_JAVA,
        'sys': NS_SYS,
        'x': NS_X
    }

    def __init__(self):
        """Initialize the canvas generator."""
        pass

    def generate_root(self, graph_id="G", include_svg_defs=False) -> ET.Element:
        """
        Generate the root <graphml> element with all key definitions.

        Args:
            graph_id: ID for the root graph element (default: "G")
            include_svg_defs: If True, include SVG resource definitions for ExtractorNode

        Returns:
            lxml.etree.Element: Root <graphml> element with keys and empty graph
        """
        # Create root <graphml> element with namespaces
        root = ET.Element(
            f"{{{self.NS_GRAPHML}}}graphml",
            nsmap=self.NSMAP,
            attrib={
                f"{{{self.NS_XSI}}}schemaLocation":
                    "http://graphml.graphdrawing.org/xmlns "
                    "http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd"
            }
        )

        # Add key definitions
        self._add_key_definitions(root)

        # Add SVG resource definitions if requested
        if include_svg_defs:
            self._add_svg_resources(root)

        # Create root <graph> element
        graph = ET.SubElement(
            root,
            f"{{{self.NS_GRAPHML}}}graph",
            edgedefault="directed",
            id=graph_id
        )

        # Add graph description (can be populated later)
        data_desc = ET.SubElement(
            graph,
            f"{{{self.NS_GRAPHML}}}data",
            key="d0"
        )
        data_desc.set(f"{{{self.NS_GRAPHML}}}space", "preserve")

        return root

    def _add_key_definitions(self, root: ET.Element):
        """
        Add all <key> definitions to the root element.

        These keys define the attributes that can be attached to nodes and edges,
        following the Extended Matrix / yEd conventions.

        Args:
            root: The root <graphml> element
        """
        keys = [
            # Graph description
            {
                "id": "d0",
                "for": "graph",
                "attr.name": "Description",
                "attr.type": "string"
            },
            # Port keys (for yEd)
            {
                "id": "d1",
                "for": "port",
                "yfiles.type": "portgraphics"
            },
            {
                "id": "d2",
                "for": "port",
                "yfiles.type": "portgeometry"
            },
            {
                "id": "d3",
                "for": "port",
                "yfiles.type": "portuserdata"
            },
            # Node attributes
            {
                "id": "d4",
                "for": "node",
                "attr.name": "url",
                "attr.type": "string"
            },
            {
                "id": "d5",
                "for": "node",
                "attr.name": "description",
                "attr.type": "string"
            },
            {
                "id": "d6",
                "for": "node",
                "yfiles.type": "nodegraphics"
            },
            # Resources (yEd)
            {
                "id": "d7",
                "for": "graphml",
                "yfiles.type": "resources"
            },
            # Edge attributes
            {
                "id": "d8",
                "for": "edge",
                "attr.name": "url",
                "attr.type": "string"
            },
            {
                "id": "d9",
                "for": "edge",
                "attr.name": "description",
                "attr.type": "string"
            },
            {
                "id": "d10",
                "for": "edge",
                "yfiles.type": "edgegraphics"
            },
            # Extended Matrix custom fields
            {
                "id": "d11",
                "for": "node",
                "attr.name": "EMID",
                "attr.type": "string"
            },
            {
                "id": "d12",
                "for": "edge",
                "attr.name": "EMID",
                "attr.type": "string"
            },
            {
                "id": "d13",
                "for": "node",
                "attr.name": "URI",
                "attr.type": "string"
            },
            {
                "id": "d14",
                "for": "edge",
                "attr.name": "URI",
                "attr.type": "string"
            }
        ]

        for key_def in keys:
            key_elem = ET.SubElement(
                root,
                f"{{{self.NS_GRAPHML}}}key"
            )

            # Set attributes
            for attr_name, attr_value in key_def.items():
                key_elem.set(attr_name, attr_value)

    def _add_svg_resources(self, root: ET.Element):
        """
        Add SVG resource definitions for ExtractorNode icons.

        These are referenced by SVGNode elements via refid attribute.

        Args:
            root: The root <graphml> element
        """
        # Create data element for resources (d7)
        data_resources = ET.SubElement(root, f"{{{self.NS_GRAPHML}}}data", key="d7")

        # Create y:Resources
        resources = ET.SubElement(data_resources, f"{{{self.NS_YFILES}}}Resources")

        # SVG Content definition (refid="1" for ExtractorNode)
        # This is a simple person icon SVG
        svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 25 25">
  <circle cx="12.5" cy="7.5" r="3.5" fill="#CCCCFF" stroke="#000" stroke-width="1"/>
  <path d="M 5 20 Q 5 15, 12.5 15 Q 20 15, 20 20" fill="#CCCCFF" stroke="#000" stroke-width="1"/>
</svg>'''

        resource = ET.SubElement(
            resources,
            f"{{{self.NS_YFILES}}}Resource",
            id="1",
            type="java.lang.String"
        )
        resource.text = svg_content.strip()

    def get_graph_element(self, root: ET.Element) -> ET.Element:
        """
        Get the <graph> element from the root.

        Args:
            root: The root <graphml> element

        Returns:
            The <graph> element, or None if not found
        """
        return root.find(f"{{{self.NS_GRAPHML}}}graph")
