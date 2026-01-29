"""
Edge Generator for GraphML Export

Generates yEd-compatible edge XML elements with appropriate line styles
based on edge types from the s3dgraphy connections datamodel.
"""

from lxml import etree as ET
from typing import Optional
from ...edges.edge import Edge
from .utils import generate_uuid, qname, get_edge_line_style


class EdgeGenerator:
    """
    Generates GraphML edge elements for s3dgraphy Edge objects.

    Handles:
    - Temporal edges (is_after, changed_from)
    - Physical stratigraphic relations (cuts, overlies, fills, abuts)
    - Provenance edges (has_data_provenance, extracted_from)
    - Property edges (has_property)
    - Epoch edges (has_first_epoch, survive_in_epoch)
    """

    # Namespace constants
    NS_GRAPHML = "http://graphml.graphdrawing.org/xmlns"
    NS_YFILES = "http://www.yworks.com/xml/graphml"

    def __init__(self):
        """Initialize the edge generator."""
        pass

    def generate_edge(
        self,
        edge: Edge,
        graph=None
    ) -> ET.Element:
        """
        Generate GraphML XML for an edge.

        Args:
            edge: s3dgraphy Edge object
            graph: Optional Graph object (for additional context)

        Returns:
            ET.Element: GraphML <edge> element with yEd PolyLineEdge
        """
        # Create <edge> element
        edge_elem = ET.Element(
            qname(self.NS_GRAPHML, "edge"),
            id=edge.edge_id,
            source=edge.edge_source,
            target=edge.edge_target
        )

        # Add edge description if present
        if edge.description:
            desc_data = ET.SubElement(
                edge_elem,
                qname(self.NS_GRAPHML, "data"),
                key="d9"
            )
            desc_data.text = edge.description

        # Add edge graphics data (key d10)
        graphics_data = ET.SubElement(
            edge_elem,
            qname(self.NS_GRAPHML, "data"),
            key="d10"
        )

        # Create PolyLineEdge
        polyline = ET.SubElement(
            graphics_data,
            qname(self.NS_YFILES, "PolyLineEdge")
        )

        # Path (simple straight line)
        path = ET.SubElement(
            polyline,
            qname(self.NS_YFILES, "Path"),
            sx="0",
            sy="0",
            tx="0",
            ty="0"
        )

        # Line style based on edge type
        line_style = get_edge_line_style(edge.edge_type)
        line_elem = ET.SubElement(
            polyline,
            qname(self.NS_YFILES, "LineStyle"),
            color="#000000",
            type=line_style,
            width="2.0"
        )

        # Arrows
        # For temporal edges (is_after), arrow points from recent to ancient
        # For most edges, arrow points from source to target
        arrow_source, arrow_target = self._get_arrow_directions(edge.edge_type)

        arrows = ET.SubElement(
            polyline,
            qname(self.NS_YFILES, "Arrows"),
            source=arrow_source,
            target=arrow_target
        )

        # Bend style (straight lines, no curves)
        bend = ET.SubElement(
            polyline,
            qname(self.NS_YFILES, "BendStyle"),
            smoothed="false"
        )

        return edge_elem

    def _get_arrow_directions(self, edge_type: str) -> tuple:
        """
        Determine arrow directions for an edge type.

        Args:
            edge_type: Edge type from connections datamodel

        Returns:
            tuple: (source_arrow, target_arrow)
                   Each can be: "none", "standard", "white_delta", etc.

        Arrow conventions:
        - Temporal edges (is_after): arrow at target (pointing to ancient)
        - Directed edges: arrow at target
        - Symmetric edges: no arrows
        """
        # Symmetric relations (no arrows)
        SYMMETRIC_EDGES = {
            'has_same_time',
            'is_bonded_to',
            'is_physically_equal_to',
            'contrasts_with'
        }

        if edge_type in SYMMETRIC_EDGES:
            return ("none", "none")

        # Most edges have arrow pointing to target
        # (source → target)
        return ("none", "standard")
