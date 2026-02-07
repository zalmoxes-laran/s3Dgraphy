"""
Main GraphML Exporter.

Orchestrates the export of Graph objects to GraphML Extended Matrix format.
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
        
        # 3. Generate stratigraphic nodes
        print(f"Generating {len(self.graph.nodes)} nodes...")
        stratigraphic_nodes = []
        for i, node in enumerate(self.graph.nodes):
            node_type = type(node).__name__
            
            # Import node classes dynamically
            from ...nodes.stratigraphic_node import StratigraphicNode
            from ...nodes.property_node import PropertyNode
            
            if isinstance(node, StratigraphicNode):
                # Position: basic layout (will be improved with epochs later)
                x = 100.0 + (i % 5) * 150
                y = 100.0 + (i // 5) * 100
                
                node_xml = node_gen.generate_stratigraphic_node(node, x, y)
                graph_elem.append(node_xml)
                stratigraphic_nodes.append(node)
        
        # 4. Build and generate ParadataNodeGroups
        print("Building ParadataNodeGroups...")
        paradata_groups = self._build_paradata_groups(stratigraphic_nodes)
        
        for group_data in paradata_groups:
            # Generate group container
            group_xml = group_gen.generate_paradata_group(group_data, x=800.0, y=100.0)
            graph_elem.append(group_xml)
            
            # Get nested graph element
            group_nested_id = group_data['group_nested_id']
            nested_graph = group_xml.find('.//{http://graphml.graphdrawing.org/xmlns}graph')
            
            # Add property nodes inside group
            y_offset = 50.0
            for prop_node in group_data.get('property_nodes', []):
                prop_xml = node_gen.generate_property_node(prop_node, x=20.0, y=y_offset,
                                                          parent_id=group_nested_id)
                nested_graph.append(prop_xml)
                y_offset += 50.0
            
            # Add extractor nodes
            for ext_node in group_data.get('extractor_nodes', []):
                ext_xml = node_gen.generate_extractor_node(ext_node, x=150.0, y=y_offset,
                                                          parent_id=group_nested_id)
                nested_graph.append(ext_xml)
                y_offset += 40.0
            
            # Add document nodes
            for doc_node in group_data.get('document_nodes', []):
                doc_xml = node_gen.generate_document_node(doc_node, x=200.0, y=y_offset,
                                                         parent_id=group_nested_id)
                nested_graph.append(doc_xml)
                y_offset += 70.0
        
        # 5. Generate edges
        print(f"Generating {len(self.graph.edges)} edges...")
        for edge in self.graph.edges:
            edge_xml = edge_gen.generate_edge(edge)
            if edge_xml is not None:
                graph_elem.append(edge_xml)
        
        # 6. Add SVG resources for ExtractorNode icons
        resources = canvas.generate_svg_resources()
        root.append(resources)
        
        # 7. Write file
        print(f"Writing GraphML to {output_path}...")
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding='UTF-8', xml_declaration=True, pretty_print=True)
        
        print(f"GraphML export completed successfully!")
        print(f"  - Nodes: {len(self.graph.nodes)}")
        print(f"  - Edges: {len(self.graph.edges)}")
        print(f"  - ParadataGroups: {len(paradata_groups)}")

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
                    property_name="stratigraphic_definition"
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
