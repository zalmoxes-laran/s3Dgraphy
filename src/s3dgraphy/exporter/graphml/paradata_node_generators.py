"""
Paradata Node Generators for Extended Matrix GraphML Export.

Generates PropertyNode, DocumentNode, and ExtractorNode with correct
BPMN and SVG shapes as seen in TempluMare_EM_converted_converted.graphml.
"""

from typing import Optional
from lxml import etree as ET


class PropertyNodeGenerator:
    """Generate PropertyNode as BPMN Annotation."""

    YFILES_NS = "http://www.yworks.com/xml/graphml"

    def generate_property_node(
        self,
        node_id: str,
        property_name: str,
        property_value: str,
        x: float,
        y: float,
        width: float = 107.9,
        height: float = 30.0,
        emid: Optional[str] = None
    ) -> ET.Element:
        """
        Generate PropertyNode as BPMN Annotation.

        Args:
            node_id: Node ID (e.g., "n0::n3::n3::n2")
            property_name: Property name (e.g., "Dimension.height")
            property_value: Property value/description
            x, y: Coordinates
            width, height: Dimensions
            emid: Optional EMID (original UUID) for the node

        Returns:
            lxml Element representing the PropertyNode
        """
        node = ET.Element('node', id=node_id)

        # EMID data (d11) - if provided
        if emid:
            emid_data = ET.SubElement(node, 'data', key='d11')
            emid_data.text = emid

        # Description data (d5)
        desc_data = ET.SubElement(node, 'data', key='d5')
        desc_data.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        desc_data.text = property_value

        # Graphics data (d6)
        gfx_data = ET.SubElement(node, 'data', key='d6')

        # GenericNode with BPMN configuration
        generic_node = ET.SubElement(
            gfx_data,
            '{%s}GenericNode' % self.YFILES_NS,
            configuration='com.yworks.bpmn.Artifact.withShadow'
        )

        # Geometry
        geometry = ET.SubElement(generic_node, '{%s}Geometry' % self.YFILES_NS)
        geometry.set('height', str(height))
        geometry.set('width', str(width))
        geometry.set('x', str(x))
        geometry.set('y', str(y))

        # Fill
        fill = ET.SubElement(generic_node, '{%s}Fill' % self.YFILES_NS)
        fill.set('color', '#FFFFFFE6')
        fill.set('transparent', 'false')

        # Border
        border = ET.SubElement(generic_node, '{%s}BorderStyle' % self.YFILES_NS)
        border.set('color', '#000000')
        border.set('type', 'line')
        border.set('width', '1.0')

        # Label
        label = ET.SubElement(generic_node, '{%s}NodeLabel' % self.YFILES_NS)
        label.set('alignment', 'center')
        label.set('autoSizePolicy', 'content')
        label.set('fontFamily', 'Dialog')
        label.set('fontSize', '12')
        label.set('fontStyle', 'plain')
        label.set('hasBackgroundColor', 'false')
        label.set('hasLineColor', 'false')
        label.set('height', '18.1328125')
        label.set('horizontalTextPosition', 'center')
        label.set('iconTextGap', '4')
        label.set('modelName', 'custom')
        label.set('textColor', '#000000')
        label.set('verticalTextPosition', 'bottom')
        label.set('visible', 'true')
        label.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        label.text = property_name

        # Label model
        label_model = ET.SubElement(label, '{%s}LabelModel' % self.YFILES_NS)
        ET.SubElement(
            label_model,
            '{%s}SmartNodeLabelModel' % self.YFILES_NS,
            distance='4.0'
        )

        # Model parameter
        model_param = ET.SubElement(label, '{%s}ModelParameter' % self.YFILES_NS)
        smart_param = ET.SubElement(
            model_param,
            '{%s}SmartNodeLabelModelParameter' % self.YFILES_NS
        )
        smart_param.set('labelRatioX', '0.0')
        smart_param.set('labelRatioY', '0.0')
        smart_param.set('nodeRatioX', '0.0')
        smart_param.set('nodeRatioY', '0.0')
        smart_param.set('offsetX', '0.0')
        smart_param.set('offsetY', '0.0')
        smart_param.set('upX', '0.0')
        smart_param.set('upY', '-1.0')

        # Style properties (BPMN)
        style_props = ET.SubElement(generic_node, '{%s}StyleProperties' % self.YFILES_NS)

        # Icon line color
        prop1 = ET.SubElement(style_props, '{%s}Property' % self.YFILES_NS)
        prop1.set('class', 'java.awt.Color')
        prop1.set('name', 'com.yworks.bpmn.icon.line.color')
        prop1.set('value', '#000000')

        # Icon fill 2
        prop2 = ET.SubElement(style_props, '{%s}Property' % self.YFILES_NS)
        prop2.set('class', 'java.awt.Color')
        prop2.set('name', 'com.yworks.bpmn.icon.fill2')
        prop2.set('value', '#d4d4d4cc')

        # Icon fill
        prop3 = ET.SubElement(style_props, '{%s}Property' % self.YFILES_NS)
        prop3.set('class', 'java.awt.Color')
        prop3.set('name', 'com.yworks.bpmn.icon.fill')
        prop3.set('value', '#ffffffe6')

        # BPMN type - ANNOTATION
        prop4 = ET.SubElement(style_props, '{%s}Property' % self.YFILES_NS)
        prop4.set('class', 'com.yworks.yfiles.bpmn.view.BPMNTypeEnum')
        prop4.set('name', 'com.yworks.bpmn.type')
        prop4.set('value', 'ARTIFACT_TYPE_ANNOTATION')

        return node


class DocumentNodeGenerator:
    """Generate DocumentNode as BPMN Data Object."""

    YFILES_NS = "http://www.yworks.com/xml/graphml"

    def generate_document_node(
        self,
        node_id: str,
        document_name: str,
        description: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 42.8,
        height: float = 63.8,
        emid: Optional[str] = None
    ) -> ET.Element:
        """
        Generate DocumentNode as BPMN Data Object.

        Args:
            node_id: Node ID (e.g., "n0::n3::n3::n0")
            document_name: Document identifier (e.g., "D.05")
            description: Optional description
            x, y: Coordinates
            width, height: Dimensions
            emid: Optional EMID (original UUID) for the node

        Returns:
            lxml Element representing the DocumentNode
        """
        node = ET.Element('node', id=node_id)

        # EMID data (d11) - if provided
        if emid:
            emid_data = ET.SubElement(node, 'data', key='d11')
            emid_data.text = emid

        # Description data (d5)
        desc_data = ET.SubElement(node, 'data', key='d5')
        desc_data.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        desc_data.text = description or document_name

        # Graphics data (d6)
        gfx_data = ET.SubElement(node, 'data', key='d6')

        # GenericNode with BPMN configuration
        generic_node = ET.SubElement(
            gfx_data,
            '{%s}GenericNode' % self.YFILES_NS,
            configuration='com.yworks.bpmn.Artifact.withShadow'
        )

        # Geometry
        geometry = ET.SubElement(generic_node, '{%s}Geometry' % self.YFILES_NS)
        geometry.set('height', str(height))
        geometry.set('width', str(width))
        geometry.set('x', str(x))
        geometry.set('y', str(y))

        # Fill
        fill = ET.SubElement(generic_node, '{%s}Fill' % self.YFILES_NS)
        fill.set('color', '#FFFFFFE6')
        fill.set('transparent', 'false')

        # Border
        border = ET.SubElement(generic_node, '{%s}BorderStyle' % self.YFILES_NS)
        border.set('color', '#000000')
        border.set('type', 'line')
        border.set('width', '1.0')

        # Label
        label = ET.SubElement(generic_node, '{%s}NodeLabel' % self.YFILES_NS)
        label.set('alignment', 'center')
        label.set('autoSizePolicy', 'content')
        label.set('fontFamily', 'Dialog')
        label.set('fontSize', '8')
        label.set('fontStyle', 'plain')
        label.set('hasBackgroundColor', 'false')
        label.set('hasLineColor', 'false')
        label.set('height', '13.421875')
        label.set('horizontalTextPosition', 'center')
        label.set('iconTextGap', '4')
        label.set('modelName', 'internal')
        label.set('modelPosition', 'c')  # Center
        label.set('textColor', '#000000')
        label.set('verticalTextPosition', 'bottom')
        label.set('visible', 'true')
        label.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        label.text = document_name

        # Style properties (BPMN)
        style_props = ET.SubElement(generic_node, '{%s}StyleProperties' % self.YFILES_NS)

        # Icon line color
        prop1 = ET.SubElement(style_props, '{%s}Property' % self.YFILES_NS)
        prop1.set('class', 'java.awt.Color')
        prop1.set('name', 'com.yworks.bpmn.icon.line.color')
        prop1.set('value', '#000000')

        # Data object type
        prop2 = ET.SubElement(style_props, '{%s}Property' % self.YFILES_NS)
        prop2.set('class', 'com.yworks.yfiles.bpmn.view.DataObjectTypeEnum')
        prop2.set('name', 'com.yworks.bpmn.dataObjectType')
        prop2.set('value', 'DATA_OBJECT_TYPE_PLAIN')

        # Icon fill 2
        prop3 = ET.SubElement(style_props, '{%s}Property' % self.YFILES_NS)
        prop3.set('class', 'java.awt.Color')
        prop3.set('name', 'com.yworks.bpmn.icon.fill2')
        prop3.set('value', '#d4d4d4cc')

        # Icon fill
        prop4 = ET.SubElement(style_props, '{%s}Property' % self.YFILES_NS)
        prop4.set('class', 'java.awt.Color')
        prop4.set('name', 'com.yworks.bpmn.icon.fill')
        prop4.set('value', '#ffffffe6')

        # BPMN type - DATA_OBJECT
        prop5 = ET.SubElement(style_props, '{%s}Property' % self.YFILES_NS)
        prop5.set('class', 'com.yworks.yfiles.bpmn.view.BPMNTypeEnum')
        prop5.set('name', 'com.yworks.bpmn.type')
        prop5.set('value', 'ARTIFACT_TYPE_DATA_OBJECT')

        return node


class ExtractorNodeGenerator:
    """Generate ExtractorNode as SVG Node."""

    YFILES_NS = "http://www.yworks.com/xml/graphml"

    def generate_extractor_node(
        self,
        node_id: str,
        extractor_name: str,
        description: Optional[str] = None,
        x: float = 0.0,
        y: float = 0.0,
        width: float = 25.0,
        height: float = 25.0,
        svg_refid: int = 1,
        emid: Optional[str] = None
    ) -> ET.Element:
        """
        Generate ExtractorNode as SVG Node.

        Args:
            node_id: Node ID (e.g., "n0::n3::n3::n1")
            extractor_name: Extractor identifier (e.g., "D.05.02")
            description: Optional description
            x, y: Coordinates
            width, height: Dimensions
            svg_refid: SVG reference ID (must match SVG definition in header)
            emid: Optional EMID (original UUID) for the node

        Returns:
            lxml Element representing the ExtractorNode
        """
        node = ET.Element('node', id=node_id)

        # EMID data (d11) - if provided
        if emid:
            emid_data = ET.SubElement(node, 'data', key='d11')
            emid_data.text = emid

        # Description data (d5)
        desc_data = ET.SubElement(node, 'data', key='d5')
        desc_data.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        desc_data.text = description or extractor_name

        # Graphics data (d6)
        gfx_data = ET.SubElement(node, 'data', key='d6')

        # SVGNode
        svg_node = ET.SubElement(gfx_data, '{%s}SVGNode' % self.YFILES_NS)

        # Geometry
        geometry = ET.SubElement(svg_node, '{%s}Geometry' % self.YFILES_NS)
        geometry.set('height', str(height))
        geometry.set('width', str(width))
        geometry.set('x', str(x))
        geometry.set('y', str(y))

        # Fill
        fill = ET.SubElement(svg_node, '{%s}Fill' % self.YFILES_NS)
        fill.set('color', '#CCCCFF')
        fill.set('transparent', 'false')

        # Border
        border = ET.SubElement(svg_node, '{%s}BorderStyle' % self.YFILES_NS)
        border.set('color', '#000000')
        border.set('type', 'line')
        border.set('width', '1.0')

        # Label (positioned at top-left corner, underlined)
        label = ET.SubElement(svg_node, '{%s}NodeLabel' % self.YFILES_NS)
        label.set('alignment', 'center')
        label.set('autoSizePolicy', 'content')
        label.set('borderDistance', '0.0')
        label.set('fontFamily', 'Dialog')
        label.set('fontSize', '10')
        label.set('fontStyle', 'plain')
        label.set('hasBackgroundColor', 'false')
        label.set('hasLineColor', 'false')
        label.set('height', '15.77734375')
        label.set('horizontalTextPosition', 'center')
        label.set('iconTextGap', '4')
        label.set('modelName', 'corners')
        label.set('modelPosition', 'nw')  # North-west (top-left)
        label.set('textColor', '#000000')
        label.set('underlinedText', 'true')
        label.set('verticalTextPosition', 'bottom')
        label.set('visible', 'true')
        label.set('x', f"-{width + 18}")  # Offset to left
        label.set('y', f"-{height - 9}")  # Offset above
        label.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        label.text = extractor_name

        # SVG properties
        svg_props = ET.SubElement(svg_node, '{%s}SVGNodeProperties' % self.YFILES_NS)
        svg_props.set('usingVisualBounds', 'true')

        # SVG model with reference
        svg_model = ET.SubElement(svg_node, '{%s}SVGModel' % self.YFILES_NS)
        svg_model.set('svgBoundsPolicy', '0')

        svg_content = ET.SubElement(svg_model, '{%s}SVGContent' % self.YFILES_NS)
        svg_content.set('refid', str(svg_refid))

        return node
