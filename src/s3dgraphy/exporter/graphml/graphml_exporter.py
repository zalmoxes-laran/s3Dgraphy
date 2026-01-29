"""
GraphML Exporter - Extended Matrix Compliant

Exports s3dgraphy Graph objects to Extended Matrix-compatible GraphML format
with proper TableNode swimlanes, ProxyAutoBoundsNode groups, and hierarchical nesting.

Based on reverse engineering of TempluMare_EM_converted_converted.graphml.
"""

from lxml import etree as ET
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from ...graph import Graph
from ...nodes.stratigraphic_node import StratigraphicNode
from ...nodes.epoch_node import EpochNode
from ...nodes.document_node import DocumentNode
from ...nodes.extractor_node import ExtractorNode
from ...nodes.property_node import PropertyNode
from ...edges import get_connections_datamodel

from .table_node_generator import TableNodeGenerator
from .group_node_generator import GroupNodeGenerator
from .paradata_node_generators import (
    PropertyNodeGenerator,
    DocumentNodeGenerator,
    ExtractorNodeGenerator
)
from .canvas_generator import CanvasGenerator
from .node_generator import NodeGenerator
from .edge_generator import EdgeGenerator


class GraphMLExporter:
    """
    Extended Matrix-compliant GraphML exporter.

    Generates GraphML with:
    - TableNode swimlanes for epochs
    - ProxyAutoBoundsNode for ParadataNodeGroups
    - Hierarchical nesting (n0::n3::n3::n0 pattern)
    - BPMN shapes for PropertyNode and DocumentNode
    - SVG shapes for ExtractorNode

    Usage:
        exporter = GraphMLExporter(graph)
        exporter.export("output.graphml", em_mode=True)
    """

    YFILES_NS = "http://www.yworks.com/xml/graphml"

    def __init__(self, graph: Graph):
        """
        Initialize the GraphML exporter.

        Args:
            graph: s3dgraphy Graph instance to export
        """
        self.graph = graph
        self.connections_dm = get_connections_datamodel()

        # Initialize generators
        self.canvas_gen = CanvasGenerator()
        self.table_gen = TableNodeGenerator()
        self.group_gen = GroupNodeGenerator()
        self.property_gen = PropertyNodeGenerator()
        self.doc_gen = DocumentNodeGenerator()
        self.extractor_gen = ExtractorNodeGenerator()
        self.node_gen = NodeGenerator()  # For stratigraphic nodes
        self.edge_gen = EdgeGenerator()

        # ID counters for nesting
        self.node_counters = defaultdict(int)

    def export(self, output_path: str, em_mode: bool = True):
        """
        Export the graph to GraphML file.

        Args:
            output_path: Output file path
            em_mode: If True, use EM hypergraph structure with swimlanes/groups.
                    If False, use flat structure (legacy mode).
        """
        if em_mode:
            self._export_em_structure(output_path)
        else:
            self._export_flat_structure(output_path)

    def _export_em_structure(self, output_path: str):
        """Export with Extended Matrix hypergraph structure."""

        # Generate root GraphML structure
        root = self.canvas_gen.generate_root(
            graph_id=self.graph.graph_id,
            include_svg_defs=True  # Include SVG definitions for ExtractorNode
        )

        # Get main <graph> element
        main_graph = self.canvas_gen.get_graph_element(root)

        # Extract epochs from graph
        epochs = [n for n in self.graph.nodes if isinstance(n, EpochNode)]

        if not epochs:
            print("⚠ No EpochNodes found. Falling back to flat structure.")
            self._export_flat_structure(output_path)
            return

        # Generate TableNode (swimlanes)
        site_metadata = {
            'id': self.graph.graph_id,
        }

        table_node = self.table_gen.generate_tablenode(
            site_id=self.graph.graph_id or "SITE",
            site_metadata=site_metadata,
            epochs=epochs
        )

        # Get the nested graph inside TableNode (where US nodes go)
        swimlane_graph = table_node.find('.//graph[@id="n0:"]')

        # Calculate epoch Y ranges for node positioning
        epoch_ranges = self.table_gen.calculate_epoch_y_ranges(epochs)

        # Group stratigraphic nodes by activity (if ActivityNodeGroup exists)
        # For now, we'll place all stratigraphic nodes directly in swimlane
        strat_nodes = [n for n in self.graph.nodes if isinstance(n, StratigraphicNode)]

        # Position stratigraphic nodes within epochs
        strat_positions = self._position_nodes_in_epochs(strat_nodes, epochs, epoch_ranges)

        # Generate stratigraphic nodes
        for node in strat_nodes:
            x, y = strat_positions.get(node.node_id, (150.0, 150.0))

            # Generate node with nested ID
            node_id = self._get_next_id("n0")
            node_xml = self.node_gen.generate_node(node, x, y, node_id=node_id)

            if node_xml is not None:
                swimlane_graph.append(node_xml)

        # Generate ParadataNodeGroups
        paradata_groups = self._generate_paradata_groups(strat_nodes, strat_positions)

        # Add paradata groups to swimlane
        for group_xml in paradata_groups:
            swimlane_graph.append(group_xml)

        # Generate edges (temporal and paradata connections)
        edges_xml = self._generate_all_edges(strat_nodes, paradata_groups)

        for edge_xml in edges_xml:
            swimlane_graph.append(edge_xml)

        # Add TableNode to main graph
        main_graph.append(table_node)

        # Write to file
        tree = ET.ElementTree(root)
        tree.write(
            output_path,
            encoding='UTF-8',
            xml_declaration=True,
            pretty_print=True
        )

        print(f"✓ Extended Matrix GraphML exported: {output_path}")
        print(f"  Epochs: {len(epochs)}")
        print(f"  Stratigraphic nodes: {len(strat_nodes)}")
        print(f"  Paradata groups: {len(paradata_groups)}")

    def _export_flat_structure(self, output_path: str):
        """Fallback to flat structure (legacy compatibility)."""
        # Import and use the old exporter logic
        from .graphml_exporter_flat import GraphMLExporter as FlatExporter

        flat_exporter = FlatExporter(self.graph)
        flat_exporter.export(output_path)

    def _position_nodes_in_epochs(
        self,
        nodes: List[StratigraphicNode],
        epochs: List[EpochNode],
        epoch_ranges: Dict[str, Tuple[float, float]]
    ) -> Dict[str, Tuple[float, float]]:
        """
        Position stratigraphic nodes within their corresponding epoch swimlanes.

        Args:
            nodes: List of StratigraphicNode objects
            epochs: List of EpochNode objects
            epoch_ranges: Dictionary mapping epoch IDs to (min_y, max_y)

        Returns:
            Dictionary mapping node IDs to (x, y) positions
        """
        positions = {}

        # Group nodes by epoch
        nodes_by_epoch = defaultdict(list)

        for node in nodes:
            # Determine which epoch this node belongs to
            # This should be based on node properties (period, phase, etc.)
            # For now, use a simple heuristic
            assigned_epoch = self._assign_node_to_epoch(node, epochs)

            if assigned_epoch:
                nodes_by_epoch[assigned_epoch.id].append(node)
            else:
                # Fallback to first epoch if no match
                nodes_by_epoch[epochs[0].id].append(node)

        # Position nodes within each epoch
        x_start = 150.0
        x_spacing = 150.0
        y_padding = 80.0

        for epoch in epochs:
            epoch_nodes = nodes_by_epoch.get(epoch.id, [])

            if not epoch_nodes:
                continue

            # Get Y range for this epoch
            min_y, max_y = epoch_ranges.get(epoch.id, (100.0, 200.0))

            # Calculate Y positions (evenly distributed or temporal order)
            available_height = max_y - min_y - (2 * y_padding)
            y_spacing = available_height / max(len(epoch_nodes), 1)

            for i, node in enumerate(epoch_nodes):
                x = x_start + (i % 5) * x_spacing  # 5 columns
                y = min_y + y_padding + (i // 5) * y_spacing

                positions[node.node_id] = (x, y)

        return positions

    def _assign_node_to_epoch(self, node: StratigraphicNode, epochs: List[EpochNode]) -> Optional[EpochNode]:
        """
        Assign a stratigraphic node to its corresponding epoch.

        Uses node properties (PERIOD, PHASE) to match with epoch names.

        Args:
            node: StratigraphicNode to assign
            epochs: List of available epochs

        Returns:
            Matching EpochNode or None
        """
        # Check node properties for period/phase information
        node_period = getattr(node, 'period', None)
        node_phase = getattr(node, 'phase', None)

        # Try to match with epoch names
        for epoch in epochs:
            epoch_name_lower = epoch.name.lower()

            if node_period and node_period.lower() in epoch_name_lower:
                return epoch
            if node_phase and node_phase.lower() in epoch_name_lower:
                return epoch

        # No match found
        return None

    def _generate_paradata_groups(
        self,
        strat_nodes: List[StratigraphicNode],
        strat_positions: Dict[str, Tuple[float, float]]
    ) -> List[ET.Element]:
        """
        Generate ParadataNodeGroup elements for stratigraphic nodes with provenance.

        Each group encapsulates: PropertyNode → ExtractorNode → DocumentNode

        Args:
            strat_nodes: List of stratigraphic nodes
            strat_positions: Positions of stratigraphic nodes

        Returns:
            List of ParadataNodeGroup XML elements
        """
        groups = []

        # Track unique extractors and documents for deduplication
        extractors_created = {}  # name -> (node_id, xml)
        documents_created = {}   # name -> (node_id, xml)

        for node in strat_nodes:
            # Check if node has extractor/document provenance
            extractor_name = getattr(node, 'extractor', None)
            document_name = getattr(node, 'document', None)

            if not (extractor_name and document_name):
                continue  # Skip if no provenance

            # Get stratigraphic node position
            us_x, us_y = strat_positions.get(node.node_id, (150.0, 150.0))

            # Position paradata group to the right of US node
            group_x = us_x + 250.0
            group_y = us_y - 50.0

            # Generate group ID
            group_id = self._get_next_id("n0")
            group_label = f"{node.node_id}_PD"

            # Create ParadataNodeGroup
            group_xml = self.group_gen.generate_group_node(
                node_id=group_id,
                group_type='ParadataNodeGroup',
                label=group_label,
                x=group_x,
                y=group_y,
                width=200.0,
                height=150.0,
                closed=False
            )

            # Get nested graph inside group
            group_graph = group_xml.find(f'.//graph[@id="{group_id}:"]')

            # Generate DocumentNode (inside group)
            if document_name not in documents_created:
                doc_id = self._get_next_id(group_id)
                doc_xml = self.doc_gen.generate_document_node(
                    node_id=doc_id,
                    document_name=document_name,
                    description=f"Document: {document_name}",
                    x=group_x + 30,
                    y=group_y + 100
                )
                documents_created[document_name] = (doc_id, doc_xml)
            else:
                doc_id, doc_xml = documents_created[document_name]

            # Generate ExtractorNode (inside group)
            if extractor_name not in extractors_created:
                ext_id = self._get_next_id(group_id)
                ext_xml = self.extractor_gen.generate_extractor_node(
                    node_id=ext_id,
                    extractor_name=extractor_name,
                    description=f"Extractor: {extractor_name}",
                    x=group_x + 90,
                    y=group_y + 70
                )
                extractors_created[extractor_name] = (ext_id, ext_xml)
            else:
                ext_id, ext_xml = extractors_created[extractor_name]

            # Generate PropertyNode (stratigraphic_definition)
            prop_id = self._get_next_id(group_id)
            prop_xml = self.property_gen.generate_property_node(
                node_id=prop_id,
                property_name="stratigraphic_definition",
                property_value=node.description or "",
                x=group_x + 50,
                y=group_y + 40
            )

            # Add nodes to group graph
            group_graph.append(doc_xml)
            group_graph.append(ext_xml)
            group_graph.append(prop_xml)

            # Store group for edge generation
            groups.append(group_xml)

        return groups

    def _generate_all_edges(
        self,
        strat_nodes: List[StratigraphicNode],
        paradata_groups: List[ET.Element]
    ) -> List[ET.Element]:
        """
        Generate all edges (temporal relations and paradata connections).

        Args:
            strat_nodes: List of stratigraphic nodes
            paradata_groups: List of paradata group XML elements

        Returns:
            List of edge XML elements
        """
        edges_xml = []

        # Generate temporal edges (is_after, etc.)
        for edge in self.graph.edges:
            edge_xml = self.edge_gen.generate_edge(edge, self.graph)
            edges_xml.append(edge_xml)

        # Generate paradata connection edges
        # US → ParadataNodeGroup (has_paradata_nodegroup)
        # This requires knowing which group corresponds to which US
        # For now, skip internal paradata edges as they're inside groups

        return edges_xml

    def _get_next_id(self, parent_id: str) -> str:
        """
        Generate next nested node ID.

        Args:
            parent_id: Parent node ID (e.g., "n0" or "n0::n3")

        Returns:
            Next available ID (e.g., "n0::n3" or "n0::n3::n5")
        """
        counter = self.node_counters[parent_id]
        self.node_counters[parent_id] += 1

        return f"{parent_id}::n{counter}"
