"""
Utility functions for GraphML export.

Provides helper functions for UUID generation, coordinate calculation,
and other common operations.
"""

import uuid
from typing import List, Tuple, Dict
from lxml import etree as ET


def generate_uuid() -> str:
    """
    Generate a RFC 4122 compliant UUID.

    Returns:
        str: UUID string (e.g., "550e8400-e29b-41d4-a716-446655440000")
    """
    return str(uuid.uuid4())


def parse_relation_string(rel_str: str) -> List[str]:
    """
    Parse comma-separated relation string into list of IDs.

    Args:
        rel_str: Comma-separated string (e.g., "USM01, USM02, USM03")

    Returns:
        List[str]: List of trimmed IDs (e.g., ["USM01", "USM02", "USM03"])

    Examples:
        >>> parse_relation_string("USM01,USM02")
        ['USM01', 'USM02']
        >>> parse_relation_string(" US01 , US02 ")
        ['US01', 'US02']
        >>> parse_relation_string("")
        []
    """
    if not rel_str or not isinstance(rel_str, str):
        return []
    return [s.strip() for s in rel_str.split(',') if s.strip()]


def escape_xml_text(text: str) -> str:
    """
    Escape XML-unsafe characters in text.

    Note: lxml handles this automatically, but this function is provided
    for explicit escaping if needed.

    Args:
        text: Raw text that may contain XML-unsafe characters

    Returns:
        str: Escaped text safe for XML
    """
    if not text:
        return ""

    # lxml handles escaping, but we provide this for explicitness
    replacements = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&apos;'
    }

    for char, escape in replacements.items():
        text = text.replace(char, escape)

    return text


def qname(namespace: str, localname: str) -> str:
    """
    Create a qualified name (QName) for XML elements.

    Args:
        namespace: XML namespace URI
        localname: Local element name

    Returns:
        str: Qualified name in Clark notation {namespace}localname

    Example:
        >>> qname("http://www.yworks.com/xml/graphml", "ShapeNode")
        '{http://www.yworks.com/xml/graphml}ShapeNode'
    """
    return f"{{{namespace}}}{localname}"


def calculate_grid_positions(
    node_count: int,
    start_x: float = 100.0,
    start_y: float = 100.0,
    spacing_x: float = 150.0,
    spacing_y: float = 100.0,
    columns: int = 5
) -> List[Tuple[float, float]]:
    """
    Calculate grid positions for nodes.

    Args:
        node_count: Number of nodes to position
        start_x: Starting X coordinate
        start_y: Starting Y coordinate
        spacing_x: Horizontal spacing between nodes
        spacing_y: Vertical spacing between rows
        columns: Number of columns in grid

    Returns:
        List[Tuple[float, float]]: List of (x, y) coordinates

    Example:
        >>> calculate_grid_positions(3, columns=2)
        [(100.0, 100.0), (250.0, 100.0), (100.0, 200.0)]
    """
    positions = []
    for i in range(node_count):
        row = i // columns
        col = i % columns
        x = start_x + (col * spacing_x)
        y = start_y + (row * spacing_y)
        positions.append((x, y))
    return positions


def create_label_text(
    label: str,
    metadata: Dict[str, str] = None
) -> str:
    """
    Create Extended Matrix-style label text with metadata.

    Extended Matrix uses format: "Label [key1:value1;key2:value2]"

    Args:
        label: Main label text
        metadata: Optional dictionary of key-value pairs

    Returns:
        str: Formatted label with metadata

    Examples:
        >>> create_label_text("Roman Period", {"start": "-753", "end": "476"})
        'Roman Period [start:-753;end:476]'
        >>> create_label_text("USM01")
        'USM01'
    """
    if not metadata:
        return label

    # Format metadata as [key1:value1;key2:value2]
    meta_str = ";".join([f"{k}:{v}" for k, v in metadata.items()])
    return f"{label} [{meta_str}]"


def add_cdata_section(
    parent: ET.Element,
    text: str
) -> ET.Element:
    """
    Add a CDATA section to an XML element.

    Args:
        parent: Parent XML element
        text: Text content for CDATA

    Returns:
        ET.Element: The parent element (for chaining)
    """
    # In lxml, text content is automatically escaped unless explicitly set as CDATA
    # For description fields, we'll use xml:space="preserve"
    parent.text = text
    parent.set(f"{{http://www.w3.org/XML/1998/namespace}}space", "preserve")
    return parent


def get_node_type_shape(node_type: str) -> Tuple[str, str, str]:
    """
    Get yEd shape, fill color, and border color for a stratigraphic node type.

    Args:
        node_type: Stratigraphic node type code (US, USVs, USVn, SF, etc.)

    Returns:
        Tuple[str, str, str]: (shape_type, fill_color, border_color)

    Mapping based on Extended Matrix conventions:
    - US: rectangle, white fill, red border
    - USVs: parallelogram, black fill, blue border
    - USVn: hexagon, black fill, green border
    - SF: octagon, white fill, yellow border
    - VSF: octagon, black fill, beige border
    - USD: roundrectangle, white fill, black border
    - serSU: ellipse, white fill, red border
    - serUSVn: ellipse, black fill, green border
    - serUSVs: ellipse, black fill, blue border
    - TSU: rectangle, white fill, black border (dotted)
    - SE: diamond, yellow fill, black border
    - BR: trapezoid, gray fill, black border
    """
    TYPE_TO_SHAPE = {
        'US': ('rectangle', '#FFFFFF', '#9B3333'),
        'USVs': ('parallelogram', '#000000', '#248FE7'),
        'USVn': ('hexagon', '#000000', '#31792D'),
        'SF': ('octagon', '#FFFFFF', '#D8BD30'),
        'VSF': ('octagon', '#000000', '#B19F61'),
        'USD': ('roundrectangle', '#FFFFFF', '#000000'),
        'serSU': ('ellipse', '#FFFFFF', '#9B3333'),
        'serUSVn': ('ellipse', '#000000', '#31792D'),
        'serUSVs': ('ellipse', '#000000', '#248FE7'),
        'TSU': ('rectangle', '#FFFFFF', '#000000'),  # Should have dotted border
        'SE': ('diamond', '#FFFF00', '#000000'),
        'BR': ('trapezoid', '#808080', '#000000'),
        'unknown': ('rectangle', '#CCCCCC', '#666666')  # Fallback
    }

    return TYPE_TO_SHAPE.get(node_type, TYPE_TO_SHAPE['unknown'])


def get_edge_line_style(edge_type: str) -> str:
    """
    Get yEd line style for an edge type.

    Args:
        edge_type: Edge type from connections datamodel

    Returns:
        str: yEd line style ("line", "dotted", "dashed", etc.)

    Mapping:
    - is_after: solid line
    - changed_from: dotted
    - has_data_provenance: dashed
    - extracted_from: dashed
    - contrasts_with: dashed_dotted
    - default: solid line
    """
    EDGE_TYPE_TO_LINE_STYLE = {
        'is_after': 'line',
        'is_before': 'line',
        'has_same_time': 'line',  # yEd doesn't support double_line
        'changed_from': 'dotted',
        'changed_to': 'dotted',
        'has_data_provenance': 'dashed',
        'extracted_from': 'dashed',
        'contrasts_with': 'dashed_dotted',
        'has_property': 'line',
        'has_first_epoch': 'line',
        'survive_in_epoch': 'line',
        # Physical relations
        'cuts': 'line',
        'is_cut_by': 'line',
        'overlies': 'line',
        'is_overlain_by': 'line',
        'fills': 'line',
        'is_filled_by': 'line',
        'abuts': 'line',
        'is_abutted_by': 'line',
        'is_bonded_to': 'line',
        'is_physically_equal_to': 'line',
    }

    return EDGE_TYPE_TO_LINE_STYLE.get(edge_type, 'line')
