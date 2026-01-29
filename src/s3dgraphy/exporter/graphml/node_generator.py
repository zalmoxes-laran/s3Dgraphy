"""
Node Generator for GraphML Export

Generates yEd-compatible node XML elements for all s3dgraphy node types,
including stratigraphic nodes, documents, extractors, properties, and epochs.
"""

from lxml import etree as ET
from typing import Optional, Tuple
from ...nodes.stratigraphic_node import StratigraphicNode
from ...nodes.document_node import DocumentNode
from ...nodes.extractor_node import ExtractorNode
from ...nodes.property_node import PropertyNode
from ...nodes.epoch_node import EpochNode
from .utils import generate_uuid, qname, get_node_type_shape


class NodeGenerator:
    """
    Generates GraphML node elements for various s3dgraphy node types.

    Handles:
    - StratigraphicNode: Shape-based nodes (US, USVs, USVn, SF, etc.)
    - DocumentNode: BPMN data object shapes
    - ExtractorNode: BPMN data object shapes (prefixed with "D.")
    - PropertyNode: BPMN annotation shapes
    - EpochNode: Not generated directly (part of swimlanes)
    """

    # Namespace constants
    NS_GRAPHML = "http://graphml.graphdrawing.org/xmlns"
    NS_YFILES = "http://www.yworks.com/xml/graphml"

    # Default dimensions
    DEFAULT_NODE_WIDTH = 120.0
    DEFAULT_NODE_HEIGHT = 60.0
    DEFAULT_DOC_WIDTH = 60.0
    DEFAULT_DOC_HEIGHT = 80.0

    def __init__(self):
        """Initialize the node generator."""
        self.node_positions = {}  # Track node positions for layout

    def generate_node(
        self,
        node,
        x: float = 150.0,
        y: float = 150.0,
        node_id: Optional[str] = None
    ) -> Optional[ET.Element]:
        """
        Generate GraphML XML for a node based on its type.

        Args:
            node: s3dgraphy Node object
            x: X coordinate for node position
            y: Y coordinate for node position
            node_id: Optional custom node ID (for nested structures). If not provided, uses node.node_id

        Returns:
            ET.Element: GraphML <node> element, or None if node type not supported
        """
        # Use custom ID if provided, otherwise use node's ID
        final_node_id = node_id if node_id else node.node_id

        # Dispatch to appropriate generator based on node type
        if isinstance(node, StratigraphicNode):
            return self.generate_stratigraphic_node(node, x, y, node_id=final_node_id)
        elif isinstance(node, DocumentNode):
            return self.generate_document_node(node, x, y, node_id=final_node_id)
        elif isinstance(node, ExtractorNode):
            return self.generate_extractor_node(node, x, y, node_id=final_node_id)
        elif isinstance(node, PropertyNode):
            return self.generate_property_node(node, x, y, node_id=final_node_id)
        elif isinstance(node, EpochNode):
            # Epochs are handled by swimlane generator
            return None
        else:
            # Unknown node type - skip
            return None

    def generate_stratigraphic_node(
        self,
        node: StratigraphicNode,
        x: float,
        y: float,
        node_id: Optional[str] = None
    ) -> ET.Element:
        """
        Generate a stratigraphic node with appropriate shape and colors.

        Args:
            node: StratigraphicNode instance
            x: X coordinate
            y: Y coordinate

        Returns:
            ET.Element: <node> element with yEd ShapeNode
        """
        # Get node type from class name or attributes
        node_type = self._get_stratigraphic_type(node)

        # Get shape, fill color, and border color
        shape_type, fill_color, border_color = get_node_type_shape(node_type)

        # Create <node> element
        final_id = node_id if node_id else node.node_id
        node_elem = ET.Element(
            qname(self.NS_GRAPHML, "node"),
            id=final_id
        )

        # Add EMID data (key d11) - original node UUID
        emid_data = ET.SubElement(
            node_elem,
            qname(self.NS_GRAPHML, "data"),
            key="d11"
        )
        emid_data.text = node.node_id  # Original UUID from s3dgraphy

        # Add description data (key d5)
        if node.description:
            desc_data = ET.SubElement(
                node_elem,
                qname(self.NS_GRAPHML, "data"),
                key="d5"
            )
            desc_data.set(
                qname("http://www.w3.org/XML/1998/namespace", "space"),
                "preserve"
            )
            desc_data.text = node.description

        # Add node graphics data (key d6)
        graphics_data = ET.SubElement(
            node_elem,
            qname(self.NS_GRAPHML, "data"),
            key="d6"
        )

        # Create ShapeNode
        shape_node = ET.SubElement(
            graphics_data,
            qname(self.NS_YFILES, "ShapeNode")
        )

        # Geometry
        geometry = ET.SubElement(
            shape_node,
            qname(self.NS_YFILES, "Geometry"),
            height=str(self.DEFAULT_NODE_HEIGHT),
            width=str(self.DEFAULT_NODE_WIDTH),
            x=str(x),
            y=str(y)
        )

        # Fill color
        fill = ET.SubElement(
            shape_node,
            qname(self.NS_YFILES, "Fill"),
            color=fill_color,
            transparent="false"
        )

        # Border style
        border = ET.SubElement(
            shape_node,
            qname(self.NS_YFILES, "BorderStyle"),
            color=border_color,
            type="line",
            width="4.0"
        )

        # Node label (name)
        label = ET.SubElement(
            shape_node,
            qname(self.NS_YFILES, "NodeLabel"),
            alignment="center",
            autoSizePolicy="content",
            fontFamily="Dialog",
            fontSize="12",
            fontStyle="plain",
            hasBackgroundColor="false",
            hasLineColor="false",
            horizontalTextPosition="center",
            iconTextGap="4",
            modelName="custom",
            textColor=self._get_text_color(fill_color),
            verticalTextPosition="bottom",
            visible="true"
        )
        label.text = node.name

        # Label model (centered)
        label_model = ET.SubElement(
            label,
            qname(self.NS_YFILES, "LabelModel")
        )
        ET.SubElement(
            label_model,
            qname(self.NS_YFILES, "SmartNodeLabelModel"),
            distance="4.0"
        )

        # Model parameter
        model_param = ET.SubElement(
            label,
            qname(self.NS_YFILES, "ModelParameter")
        )
        ET.SubElement(
            model_param,
            qname(self.NS_YFILES, "SmartNodeLabelModelParameter"),
            labelRatioX="0.0",
            labelRatioY="0.0",
            nodeRatioX="0.0",
            nodeRatioY="0.0",
            offsetX="0.0",
            offsetY="0.0",
            upX="0.0",
            upY="-1.0"
        )

        # Shape type
        shape = ET.SubElement(
            shape_node,
            qname(self.NS_YFILES, "Shape"),
            type=shape_type
        )

        return node_elem

    def generate_document_node(
        self,
        node: DocumentNode,
        x: float,
        y: float,
        node_id: Optional[str] = None
    ) -> ET.Element:
        """
        Generate a document node with BPMN data object shape.

        Args:
            node: DocumentNode instance
            x: X coordinate
            y: Y coordinate

        Returns:
            ET.Element: <node> element with BPMN GenericNode
        """
        # Create <node> element
        final_id = node_id if node_id else node.node_id
        node_elem = ET.Element(
            qname(self.NS_GRAPHML, "node"),
            id=final_id
        )

        # Add graphics data (key d6)
        graphics_data = ET.SubElement(
            node_elem,
            qname(self.NS_GRAPHML, "data"),
            key="d6"
        )

        # Create GenericNode (BPMN)
        generic_node = ET.SubElement(
            graphics_data,
            qname(self.NS_YFILES, "GenericNode"),
            configuration="com.yworks.bpmn.Artifact.withShadow"
        )

        # Geometry
        geometry = ET.SubElement(
            generic_node,
            qname(self.NS_YFILES, "Geometry"),
            height=str(self.DEFAULT_DOC_HEIGHT),
            width=str(self.DEFAULT_DOC_WIDTH),
            x=str(x),
            y=str(y)
        )

        # Fill
        fill = ET.SubElement(
            generic_node,
            qname(self.NS_YFILES, "Fill"),
            color="#FFFFFFE6",
            transparent="false"
        )

        # Border
        border = ET.SubElement(
            generic_node,
            qname(self.NS_YFILES, "BorderStyle"),
            color="#000000",
            type="line",
            width="1.0"
        )

        # Node label
        label = ET.SubElement(
            generic_node,
            qname(self.NS_YFILES, "NodeLabel"),
            alignment="center",
            autoSizePolicy="content",
            fontFamily="Dialog",
            fontSize="8",
            fontStyle="plain",
            hasBackgroundColor="false",
            hasLineColor="false",
            modelName="internal",
            modelPosition="c",
            textColor="#000000",
            visible="true"
        )
        label.text = node.name

        # Style properties (BPMN data object)
        style_props = ET.SubElement(
            generic_node,
            qname(self.NS_YFILES, "StyleProperties")
        )

        # Icon line color
        prop1 = ET.SubElement(
            style_props,
            qname(self.NS_YFILES, "Property"),
            attrib={
                "class": "java.awt.Color",
                "name": "com.yworks.bpmn.icon.line.color",
                "value": "#000000"
            }
        )

        # Data object type
        prop2 = ET.SubElement(
            style_props,
            qname(self.NS_YFILES, "Property"),
            attrib={
                "class": "com.yworks.yfiles.bpmn.view.DataObjectTypeEnum",
                "name": "com.yworks.bpmn.dataObjectType",
                "value": "DATA_OBJECT_TYPE_PLAIN"
            }
        )

        # Icon fills
        prop3 = ET.SubElement(
            style_props,
            qname(self.NS_YFILES, "Property"),
            attrib={
                "class": "java.awt.Color",
                "name": "com.yworks.bpmn.icon.fill2",
                "value": "#d4d4d4cc"
            }
        )

        prop4 = ET.SubElement(
            style_props,
            qname(self.NS_YFILES, "Property"),
            attrib={
                "class": "java.awt.Color",
                "name": "com.yworks.bpmn.icon.fill",
                "value": "#ffffffe6"
            }
        )

        # BPMN type
        prop5 = ET.SubElement(
            style_props,
            qname(self.NS_YFILES, "Property"),
            attrib={
                "class": "com.yworks.yfiles.bpmn.view.BPMNTypeEnum",
                "name": "com.yworks.bpmn.type",
                "value": "ARTIFACT_TYPE_DATA_OBJECT"
            }
        )

        return node_elem

    def generate_extractor_node(
        self,
        node: ExtractorNode,
        x: float,
        y: float,
        node_id: Optional[str] = None
    ) -> ET.Element:
        """
        Generate an extractor node (similar to document, but for data extractors).

        ExtractorNode names are prefixed with "D." by convention (e.g., "D.GPT4").

        Args:
            node: ExtractorNode instance
            x: X coordinate
            y: Y coordinate

        Returns:
            ET.Element: <node> element with BPMN GenericNode
        """
        # Extractors use the same visual style as documents
        return self.generate_document_node(node, x, y)

    def generate_property_node(
        self,
        node: PropertyNode,
        x: float,
        y: float,
        node_id: Optional[str] = None
    ) -> ET.Element:
        """
        Generate a property node with BPMN annotation shape.

        Args:
            node: PropertyNode instance
            x: X coordinate
            y: Y coordinate

        Returns:
            ET.Element: <node> element with BPMN GenericNode (annotation)
        """
        # Property nodes use BPMN annotation style
        # For now, we'll use a simple rectangle shape
        # (Full BPMN annotation support can be added later)

        node_elem = ET.Element(
            qname(self.NS_GRAPHML, "node"),
            id=node.node_id
        )

        # Add graphics data
        graphics_data = ET.SubElement(
            node_elem,
            qname(self.NS_GRAPHML, "data"),
            key="d6"
        )

        # Create ShapeNode (simple rectangle for properties)
        shape_node = ET.SubElement(
            graphics_data,
            qname(self.NS_YFILES, "ShapeNode")
        )

        # Geometry (smaller than stratigraphic nodes)
        geometry = ET.SubElement(
            shape_node,
            qname(self.NS_YFILES, "Geometry"),
            height="40.0",
            width="100.0",
            x=str(x),
            y=str(y)
        )

        # Fill (light yellow)
        fill = ET.SubElement(
            shape_node,
            qname(self.NS_YFILES, "Fill"),
            color="#FFFFCC",
            transparent="false"
        )

        # Border (thin, gray)
        border = ET.SubElement(
            shape_node,
            qname(self.NS_YFILES, "BorderStyle"),
            color="#666666",
            type="line",
            width="1.0"
        )

        # Label
        label = ET.SubElement(
            shape_node,
            qname(self.NS_YFILES, "NodeLabel"),
            alignment="center",
            autoSizePolicy="content",
            fontFamily="Dialog",
            fontSize="10",
            fontStyle="plain",
            textColor="#000000",
            visible="true"
        )
        label.text = node.name if node.name else node.property_name

        # Shape
        shape = ET.SubElement(
            shape_node,
            qname(self.NS_YFILES, "Shape"),
            type="rectangle"
        )

        return node_elem

    def _get_stratigraphic_type(self, node: StratigraphicNode) -> str:
        """
        Extract the stratigraphic type code from a node.

        Tries to determine the type from:
        1. node.node_type attribute
        2. Class name (e.g., StructuralVirtualStratigraphicUnit -> USVs)

        Args:
            node: StratigraphicNode instance

        Returns:
            str: Type code (US, USVs, USVn, SF, etc.) or 'unknown'
        """
        # Try node_type attribute first
        if hasattr(node, 'node_type') and node.node_type:
            return node.node_type

        # Map class names to type codes
        class_name = node.__class__.__name__
        class_to_type = {
            'StratigraphicUnit': 'US',
            'StructuralVirtualStratigraphicUnit': 'USVs',
            'NonStructuralVirtualStratigraphicUnit': 'USVn',
            'SpecialFindUnit': 'SF',
            'VirtualSpecialFindUnit': 'VSF',
            'DocumentaryStratigraphicUnit': 'USD',
            'TransformationStratigraphicUnit': 'TSU',
            'StratigraphicEventNode': 'SE',
            'SeriesOfStratigraphicUnit': 'serSU',
            'SeriesOfStructuralVirtualStratigraphicUnit': 'serUSVs',
            'SeriesOfNonStructuralVirtualStratigraphicUnit': 'serUSVn',
            'ContinuityNode': 'BR',
        }

        return class_to_type.get(class_name, 'unknown')

    def _get_text_color(self, fill_color: str) -> str:
        """
        Determine text color (white or black) based on fill color.

        Dark fills use white text, light fills use black text.

        Args:
            fill_color: Hex color code (e.g., "#FFFFFF")

        Returns:
            str: "#FFFFFF" or "#000000"
        """
        # Black fills (#000000) should have white text
        if fill_color.upper() == "#000000":
            return "#FFFFFF"
        else:
            return "#000000"
