"""
Main GraphML Exporter.

Orchestrates the export of Graph objects to GraphML Extended Matrix format.
All stratigraphic nodes, ParadataNodeGroups, and edges are nested inside
a single TableNode swimlane (matching yEd reference structure).
"""

from lxml import etree as ET
from typing import List, Dict
from .canvas_generator import CanvasGenerator
from .node_registry import NodeRegistry
from .node_generator import NodeGenerator
from .group_node_generator import GroupNodeGenerator
from .edge_generator import EdgeGenerator
from .utils import IDManager


class GraphMLExporter:
    """Main orchestrator for GraphML export."""

    def __init__(self, graph):
        """
        Initialize exporter with Graph object.

        Args:
            graph: Graph object from s3dgraphy (loaded via MappedXLSXImporter or GraphML import)
        """
        self.graph = graph
        self.node_registry = NodeRegistry()
        self.id_manager = IDManager()

    def export(self, output_path: str):
        """
        Export Graph to GraphML Extended Matrix format.

        Architecture: ALL nodes and edges are nested inside a single TableNode
        (swimlane) that represents the stratigraphic matrix. This matches the
        TempluMare reference structure where the swimlane is the root container.

        Args:
            output_path: Path where to save the GraphML file
        """
        print(f"Starting GraphML export to {output_path}")

        # 1. Generate root XML with correct key definitions
        canvas = CanvasGenerator()
        root = canvas.generate_root()
        graph_elem = root.find('.//{http://graphml.graphdrawing.org/xmlns}graph')

        # 2. Initialize generators
        node_gen = NodeGenerator(self.node_registry, self.id_manager)
        group_gen = GroupNodeGenerator(self.node_registry, self.id_manager)
        edge_gen = EdgeGenerator(self.id_manager)

        # 3. TEMPORAL INFERENCE: derive minimal temporal edges from topological relations
        # Must be done BEFORE generating XML so we know positions and edges
        print("Deriving temporal edges from topological relations...")
        from ...temporal.inference_engine import TemporalInferenceEngine
        from ...nodes.epoch_node import EpochNode
        from ...nodes.stratigraphic_node import StratigraphicNode
        from ...edges.edge import Edge as EdgeObj

        engine = TemporalInferenceEngine()

        # 3a. Extract temporal relations from topological edges
        temporal_edges = engine.extract_temporal_from_graph(self.graph)

        # 3b. Transitive reduction → minimal set (Harris Matrix principle)
        minimal_edges = []
        if temporal_edges:
            try:
                minimal_edges = engine.transitive_reduction(temporal_edges)
            except ValueError as e:
                print(f"  ⚠️ Temporal cycle detected: {e}")
                minimal_edges = temporal_edges  # fallback: use unreduced

            engine.print_inference_report(temporal_edges, minimal_edges)

        # 3c. Get ambiguous relations (bonded_to, equals) → has_same_time edges
        ambiguous_edges = engine.get_ambiguous_relations(self.graph)

        # 3d. Build final edge list for export
        TOPOLOGICAL_EDGE_TYPES = {
            'overlies', 'is_overlain_by', 'cuts', 'is_cut_by',
            'fills', 'is_filled_by', 'abuts', 'is_abutted_by',
            'is_bonded_to', 'is_physically_equal_to'
        }

        # Filter out topological edges, keep non-topological ones (has_property, has_first_epoch, etc.)
        export_edges = [e for e in self.graph.edges if e.edge_type not in TOPOLOGICAL_EDGE_TYPES]

        # Add minimal temporal edges as is_after
        for source_id, target_id in minimal_edges:
            edge_id = f"{source_id}_is_after_{target_id}"
            temporal_edge = EdgeObj(edge_id, source_id, target_id, 'is_after')
            export_edges.append(temporal_edge)

        # Add has_same_time for ambiguous relations (bonded_to, equals)
        seen_pairs = set()
        for edge in ambiguous_edges:
            pair = tuple(sorted([edge.edge_source, edge.edge_target]))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                edge_id = f"{pair[0]}_has_same_time_{pair[1]}"
                same_time_edge = EdgeObj(edge_id, pair[0], pair[1], 'has_same_time')
                export_edges.append(same_time_edge)

        # 4. Get epoch nodes and calculate positions
        epoch_nodes = [n for n in self.graph.nodes if isinstance(n, EpochNode)]
        strat_nodes = [n for n in self.graph.nodes if isinstance(n, StratigraphicNode)]

        positions = {}
        if epoch_nodes:
            print(f"Generating epoch swimlanes ({len(epoch_nodes)} epochs)...")
            from .epoch_generator import EpochSwimlanesGenerator
            epoch_gen = EpochSwimlanesGenerator()

            # Calculate positions for nodes within swimlanes
            positions = epoch_gen.calculate_epoch_positions(
                strat_nodes, epoch_nodes, minimal_edges
            )

        # 5. Generate swimlane TableNode as CONTAINER for everything
        # Reserve "swimlane_container" UUID → gets nested_id "n0" (first top-level node)
        swimlane_uuid = "swimlane_container"
        swimlane_id = self.id_manager.get_nested_id(swimlane_uuid)  # → "n0"

        if epoch_nodes:
            swimlane_xml = epoch_gen.generate_tablenode_xml(
                epoch_nodes, self.graph,
                swimlane_id=swimlane_id
            )
        else:
            # Create a simple group node if no epochs
            swimlane_xml = self._create_simple_swimlane(swimlane_id)

        # Get the nested graph inside the swimlane
        swimlane_graph = swimlane_xml.find(
            './/{http://graphml.graphdrawing.org/xmlns}graph'
        )

        # 6. Generate stratigraphic nodes INSIDE the swimlane
        print(f"Generating {len(strat_nodes)} stratigraphic nodes inside swimlane...")
        stratigraphic_nodes = []
        for i, node in enumerate(strat_nodes):
            # Get position from epoch calculator, or use default grid layout
            if node.node_id in positions:
                x, y = positions[node.node_id]
            else:
                x = 100.0 + (i % 8) * 150
                y = 100.0 + (i // 8) * 80

            node_xml = node_gen.generate_stratigraphic_node(
                node, x, y, parent_id=swimlane_id
            )
            swimlane_graph.append(node_xml)
            stratigraphic_nodes.append(node)

        # 7. Build and generate ParadataNodeGroups INSIDE the swimlane
        print("Building ParadataNodeGroups...")
        paradata_groups = self._build_paradata_groups(stratigraphic_nodes)

        for group_data in paradata_groups:
            us_node = group_data['us_node']

            # Position PD group near its US node
            us_x = positions.get(us_node.node_id, (800.0, 100.0))[0]
            us_y = positions.get(us_node.node_id, (800.0, 100.0))[1]
            pd_x = us_x + 20.0
            pd_y = us_y + 60.0

            # Generate group container INSIDE the swimlane
            group_xml = group_gen.generate_paradata_group(
                group_data, x=pd_x, y=pd_y, parent_id=swimlane_id
            )
            swimlane_graph.append(group_xml)

            # Get nested graph element of the PD group
            group_nested_id = group_data['group_nested_id']
            nested_graph = group_xml.find(
                './/{http://graphml.graphdrawing.org/xmlns}graph'
            )

            # Add property nodes inside group
            y_offset = 50.0
            for prop_node in group_data.get('property_nodes', []):
                prop_xml = node_gen.generate_property_node(
                    prop_node, x=20.0, y=y_offset, parent_id=group_nested_id
                )
                nested_graph.append(prop_xml)
                y_offset += 50.0

            # Add extractor nodes
            for ext_node in group_data.get('extractor_nodes', []):
                ext_xml = node_gen.generate_extractor_node(
                    ext_node, x=150.0, y=y_offset, parent_id=group_nested_id
                )
                nested_graph.append(ext_xml)
                y_offset += 40.0

            # Add document nodes
            for doc_node in group_data.get('document_nodes', []):
                doc_xml = node_gen.generate_document_node(
                    doc_node, x=200.0, y=y_offset, parent_id=group_nested_id
                )
                nested_graph.append(doc_xml)
                y_offset += 70.0

        # 8. Generate US → ParadataNodeGroup dashed edges
        print("Generating US→ParadataNodeGroup edges...")
        for group_data in paradata_groups:
            us_node = group_data['us_node']
            group_uuid = group_data.get('group_uuid', '')

            if group_uuid:
                pd_edge_id = f"{us_node.node_id}_has_pd_{group_uuid}"
                pd_edge = EdgeObj(
                    pd_edge_id, us_node.node_id, group_uuid, 'has_paradata_nodegroup'
                )
                export_edges.append(pd_edge)

        # 9. Generate ALL edges inside the swimlane graph
        is_after_count = sum(1 for e in export_edges if e.edge_type == 'is_after')
        same_time_count = sum(1 for e in export_edges if e.edge_type == 'has_same_time')
        pd_count = sum(1 for e in export_edges if e.edge_type == 'has_paradata_nodegroup')
        print(f"Generating {len(export_edges)} edges ({is_after_count} is_after, "
              f"{same_time_count} has_same_time, {pd_count} has_paradata_nodegroup)...")

        for edge in export_edges:
            edge_xml = edge_gen.generate_edge(
                edge, edge_prefix=swimlane_id
            )
            if edge_xml is not None:
                swimlane_graph.append(edge_xml)

        # 10. Append the complete swimlane to the top-level graph
        graph_elem.append(swimlane_xml)

        # 11. Add SVG resources for ExtractorNode icons
        resources = canvas.generate_svg_resources()
        root.append(resources)

        # 12. Write file
        print(f"Writing GraphML to {output_path}...")
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding='UTF-8', xml_declaration=True, pretty_print=True)

        print(f"GraphML export completed successfully!")
        print(f"  - Stratigraphic nodes: {len(stratigraphic_nodes)}")
        print(f"  - Epoch nodes: {len(epoch_nodes)}")
        print(f"  - Temporal edges (is_after): {is_after_count}")
        print(f"  - Same-time edges: {same_time_count}")
        print(f"  - US→PD edges: {pd_count}")
        print(f"  - Total edges exported: {len(export_edges)}")
        print(f"  - ParadataGroups: {len(paradata_groups)}")

    def _create_simple_swimlane(self, swimlane_id: str) -> ET.Element:
        """
        Create a simple group node as swimlane when no epochs exist.

        Args:
            swimlane_id: Node ID for the swimlane

        Returns:
            ET.Element: Simple group node with nested graph
        """
        ns_graphml = "http://graphml.graphdrawing.org/xmlns"
        ns_y = "http://www.yworks.com/xml/graphml"

        node = ET.Element(f'{{{ns_graphml}}}node', id=swimlane_id)
        node.set('yfiles.foldertype', 'group')

        # EMID
        data_d7 = ET.SubElement(node, f'{{{ns_graphml}}}data')
        data_d7.set('key', 'd7')
        data_d7.text = "simple_swimlane"

        # Simple graphics
        data_d6 = ET.SubElement(node, f'{{{ns_graphml}}}data')
        data_d6.set('key', 'd6')
        group_node = ET.SubElement(data_d6, f'{{{ns_y}}}GroupNode')
        geom = ET.SubElement(group_node, f'{{{ns_y}}}Geometry')
        geom.set('height', '1000.0')
        geom.set('width', '2000.0')
        geom.set('x', '0')
        geom.set('y', '0')

        # Nested graph
        graph = ET.SubElement(node, f'{{{ns_graphml}}}graph')
        graph.set('edgedefault', 'directed')
        graph.set('id', f'{swimlane_id}:')

        return node

    def _build_paradata_groups(self, stratigraphic_nodes: List) -> List[Dict]:
        """
        Build ParadataNodeGroup structures from stratigraphic nodes.

        For each stratigraphic node with extractor/document attributes,
        create a ParadataNodeGroup containing:
        - PropertyNode (stratigraphic_definition)
        - ExtractorNode
        - DocumentNode

        Args:
            stratigraphic_nodes: List of StratigraphicNode instances

        Returns:
            List of dicts with group data
        """
        groups = []

        from ...nodes.property_node import PropertyNode
        from ...nodes.extractor_node import ExtractorNode
        from ...nodes.document_node import DocumentNode

        for us_node in stratigraphic_nodes:
            # Check if node has extractor/document attributes
            extractor = getattr(us_node, 'extractor', None)
            document = getattr(us_node, 'document', None)

            if extractor or document:
                # Create PropertyNode for stratigraphic_definition
                property_node = PropertyNode(
                    node_id=f"{us_node.node_id}_prop_strdef",
                    name="stratigraphic_definition",
                    property_type="stratigraphic_definition"
                )

                property_nodes = [property_node]
                extractor_nodes = []
                document_nodes = []

                # Create ExtractorNode if extractor exists
                if extractor:
                    ext_node = ExtractorNode(
                        node_id=f"{us_node.node_id}_ext",
                        name=f"D.{extractor}",
                        description=f"Extractor: {extractor}"
                    )
                    extractor_nodes.append(ext_node)

                # Create DocumentNode if document exists
                if document:
                    doc_node = DocumentNode(
                        node_id=f"{us_node.node_id}_doc",
                        name=document,
                        description=f"Source document: {document}"
                    )
                    document_nodes.append(doc_node)

                group_data = {
                    'us_node': us_node,
                    'property_nodes': property_nodes,
                    'extractor_nodes': extractor_nodes,
                    'document_nodes': document_nodes
                }

                groups.append(group_data)

        return groups
