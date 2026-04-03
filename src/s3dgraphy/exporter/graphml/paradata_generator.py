"""
Paradata Structure Generator for GraphML Export

Generates the provenance chain structure:
StratigraphicNode → PropertyNode → ExtractorNode → DocumentNode

This ensures proper data lineage tracking in Extended Matrix format.
"""

from typing import Dict, List, Tuple, Optional, Set
from lxml import etree as ET
import uuid
from ...nodes.stratigraphic_node import StratigraphicNode
from ...nodes.property_node import PropertyNode
from ...nodes.extractor_node import ExtractorNode
from ...nodes.document_node import DocumentNode
from ...edges.edge import Edge
from .utils import generate_uuid


class ParadataGenerator:
    """
    Generates paradata (provenance) nodes and edges for stratigraphic units.

    Creates the standard Extended Matrix provenance structure:
    US → has_property → PropertyNode(stratigraphic_definition)
       → has_data_provenance → ExtractorNode
       → extracted_from → DocumentNode
    """

    def __init__(self):
        """Initialize the paradata generator."""
        # Track created paradata nodes to avoid duplicates
        self.extractor_nodes: Dict[str, ExtractorNode] = {}
        self.document_nodes: Dict[str, DocumentNode] = {}
        self.property_nodes: Dict[str, PropertyNode] = {}

        # Track created edges
        self.paradata_edges: List[Edge] = []

    def generate_paradata_structure(
        self,
        graph
    ) -> Tuple[List, List[Edge]]:
        """
        Generate complete paradata structure for all stratigraphic nodes.

        Args:
            graph: s3dgraphy Graph object containing nodes

        Returns:
            Tuple of (paradata_nodes, paradata_edges)
            - paradata_nodes: List of PropertyNode, ExtractorNode, DocumentNode instances
            - paradata_edges: List of Edge instances connecting the provenance chain
        """
        paradata_nodes = []

        # Process each stratigraphic node
        for node in graph.nodes:
            if not isinstance(node, StratigraphicNode):
                continue

            # Check if node has provenance information
            extractor_name = self._get_node_extractor(node)
            document_name = self._get_node_document(node)

            if not extractor_name and not document_name:
                continue  # No provenance for this node

            # Create/get paradata nodes for this US
            property_node, extractor_node, document_node = self._create_paradata_chain(
                us_node=node,
                extractor_name=extractor_name,
                document_name=document_name
            )

            # Add PropertyNode (always unique per US)
            if property_node:
                paradata_nodes.append(property_node)

            # Add ExtractorNode (deduplicated)
            if extractor_node and extractor_node.node_id not in [n.node_id for n in paradata_nodes]:
                paradata_nodes.append(extractor_node)

            # Add DocumentNode (deduplicated)
            if document_node and document_node.node_id not in [n.node_id for n in paradata_nodes]:
                paradata_nodes.append(document_node)

        return paradata_nodes, self.paradata_edges

    def _get_node_extractor(self, node: StratigraphicNode) -> Optional[str]:
        """
        Extract extractor name from node properties.

        Args:
            node: StratigraphicNode to check

        Returns:
            Extractor name string or None
        """
        # Check node properties for extractor information
        if hasattr(node, 'properties') and node.properties:
            for prop in node.properties:
                if hasattr(prop, 'name') and 'extractor' in prop.name.lower():
                    return getattr(prop, 'value', None)

        # Check direct attribute
        if hasattr(node, 'extractor'):
            return node.extractor

        return None

    def _get_node_document(self, node: StratigraphicNode) -> Optional[str]:
        """
        Extract document name from node properties.

        Args:
            node: StratigraphicNode to check

        Returns:
            Document name string or None
        """
        # Check node properties for document information
        if hasattr(node, 'properties') and node.properties:
            for prop in node.properties:
                if hasattr(prop, 'name') and 'document' in prop.name.lower():
                    return getattr(prop, 'value', None)

        # Check direct attribute
        if hasattr(node, 'document'):
            return node.document

        return None

    def _create_paradata_chain(
        self,
        us_node: StratigraphicNode,
        extractor_name: Optional[str],
        document_name: Optional[str]
    ) -> Tuple[Optional[PropertyNode], Optional[ExtractorNode], Optional[DocumentNode]]:
        """
        Create the complete paradata chain for a stratigraphic unit.

        Args:
            us_node: The stratigraphic node
            extractor_name: Name of the extractor (e.g., "GPT-4")
            document_name: Name of the source document (e.g., "Report_2023.pdf")

        Returns:
            Tuple of (PropertyNode, ExtractorNode, DocumentNode)
        """
        # Create PropertyNode for stratigraphic_definition
        property_node = PropertyNode(
            node_id=generate_uuid(),
            name="stratigraphic_definition",
            description=f"Stratigraphic definition for {us_node.name}",
            property_type="string"
        )

        # Create edge: US → PropertyNode
        edge_us_to_prop = Edge(
            edge_id=generate_uuid(),
            edge_source=us_node.node_id,
            edge_target=property_node.node_id,
            edge_type="has_property"
        )
        self.paradata_edges.append(edge_us_to_prop)

        # Get or create ExtractorNode
        extractor_node = None
        if extractor_name:
            extractor_node = self._get_or_create_extractor(extractor_name)

            # Create edge: PropertyNode → ExtractorNode
            edge_prop_to_ext = Edge(
                edge_id=generate_uuid(),
                edge_source=property_node.node_id,
                edge_target=extractor_node.node_id,
                edge_type="has_data_provenance"
            )
            self.paradata_edges.append(edge_prop_to_ext)

        # Get or create DocumentNode
        document_node = None
        if document_name and extractor_node:
            document_node = self._get_or_create_document(document_name)

            # Create edge: ExtractorNode → DocumentNode
            edge_ext_to_doc = Edge(
                edge_id=generate_uuid(),
                edge_source=extractor_node.node_id,
                edge_target=document_node.node_id,
                edge_type="extracted_from"
            )
            self.paradata_edges.append(edge_ext_to_doc)

        return property_node, extractor_node, document_node

    def _get_or_create_extractor(self, extractor_name: str) -> ExtractorNode:
        """
        Get existing or create new ExtractorNode.

        Args:
            extractor_name: Name of the extractor (e.g., "GPT-4", "Manual")

        Returns:
            ExtractorNode instance
        """
        # Normalize extractor name format: "D.{name}"
        if not extractor_name.startswith("D."):
            normalized_name = f"D.{extractor_name}"
        else:
            normalized_name = extractor_name

        # Check if already exists
        for node_id, node in self.extractor_nodes.items():
            if node.name == normalized_name:
                return node

        # Create new extractor node
        extractor_node = ExtractorNode(
            node_id=generate_uuid(),
            name=normalized_name,
            description=f"Data extractor: {extractor_name}"
        )

        self.extractor_nodes[extractor_node.node_id] = extractor_node
        return extractor_node

    def _get_or_create_document(self, document_name: str) -> DocumentNode:
        """
        Get existing or create new DocumentNode.

        Args:
            document_name: Name of the source document

        Returns:
            DocumentNode instance
        """
        # Check if already exists
        for node_id, node in self.document_nodes.items():
            if node.name == document_name:
                return node

        # Create new document node
        document_node = DocumentNode(
            node_id=generate_uuid(),
            name=document_name,
            description=f"Source document: {document_name}"
        )

        self.document_nodes[document_node.node_id] = document_node
        return document_node

    def calculate_paradata_positions(
        self,
        paradata_nodes: List,
        start_x: float = 800.0,
        start_y: float = 100.0
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculate positions for paradata nodes in a separate area.

        Args:
            paradata_nodes: List of paradata nodes (Property, Extractor, Document)
            start_x: Starting X coordinate for paradata area
            start_y: Starting Y coordinate

        Returns:
            Dictionary mapping node_id to (x, y) coordinates
        """
        positions = {}

        # Separate by type
        property_nodes = [n for n in paradata_nodes if isinstance(n, PropertyNode)]
        extractor_nodes = [n for n in paradata_nodes if isinstance(n, ExtractorNode)]
        document_nodes = [n for n in paradata_nodes if isinstance(n, DocumentNode)]

        # Layout property nodes (closest to stratigraphic area)
        y_offset = start_y
        for i, node in enumerate(property_nodes):
            positions[node.node_id] = (start_x, y_offset)
            y_offset += 80.0

        # Layout extractor nodes (middle column)
        y_offset = start_y
        for i, node in enumerate(extractor_nodes):
            positions[node.node_id] = (start_x + 200.0, y_offset)
            y_offset += 120.0

        # Layout document nodes (rightmost column)
        y_offset = start_y
        for i, node in enumerate(document_nodes):
            positions[node.node_id] = (start_x + 400.0, y_offset)
            y_offset += 120.0

        return positions
