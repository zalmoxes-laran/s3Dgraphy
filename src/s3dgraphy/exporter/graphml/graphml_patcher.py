"""
GraphML Patcher for s3dgraphy.

Patches an existing GraphML file on disk with changes from an in-memory Graph.
Supports:
  - Updating existing nodes (description, name, EMID, URI)
  - Adding new nodes that were created in-memory
  - Adding new edges
  - EMID validation and duplicate detection

This is the "twin" of the importer: it uses the same dynamic key mapping
and the same conventions to write back what the importer can read.
"""

import xml.etree.ElementTree as ET
import uuid
import os
from typing import List, Dict, Optional, Tuple

from ...graph import Graph
from ...nodes.stratigraphic_node import StratigraphicNode
from ...nodes.property_node import PropertyNode
from ...nodes.document_node import DocumentNode
from ...nodes.extractor_node import ExtractorNode
from ...nodes.combiner_node import CombinerNode
from ...nodes.group_node import GroupNode, ParadataNodeGroup, ActivityNodeGroup, TimeBranchNodeGroup
from ...nodes.epoch_node import EpochNode
from ...nodes.base_node import Node
from ...edges.edge import Edge


# Namespace constants
NS_GRAPHML = 'http://graphml.graphdrawing.org/xmlns'
NS_Y = 'http://www.yworks.com/xml/graphml'

# Edge type to yEd line style mapping (inverse of importer's EM_extract_edge_type)
EDGE_TYPE_TO_LINE_STYLE = {
    'is_after': ('line', '1.0'),
    'is_before': ('line', '1.0'),
    'has_same_time': ('line', '1.0'),
    'changed_from': ('dotted', '2.0'),
    'changed_to': ('dotted', '2.0'),
    'has_data_provenance': ('dashed', '1.0'),
    'has_property': ('dashed', '1.0'),
    'extracted_from': ('dashed', '1.0'),
    'combines': ('dashed', '1.0'),
    'has_paradata_nodegroup': ('dashed', '1.0'),
    'is_in_paradata_nodegroup': ('dashed', '1.0'),
    'contrasts_with': ('dashed_dotted', '1.0'),
    'has_first_epoch': ('line', '1.0'),
    'overlies': ('line', '2.0'),
    'is_overlain_by': ('line', '2.0'),
    'cuts': ('line', '2.0'),
    'is_cut_by': ('line', '2.0'),
    'fills': ('line', '2.0'),
    'is_filled_by': ('line', '2.0'),
    'abuts': ('line', '2.0'),
    'is_abutted_by': ('line', '2.0'),
    'is_bonded_to': ('line', '2.0'),
    'is_physically_equal_to': ('line', '2.0'),
    'generic_connection': ('line', '1.0'),
}

# Structural/derived edge types: these should NOT be exported as <edge> elements.
# They are either represented by XML nesting, inferred during import,
# or are auxiliary data not part of the EM formal language in GraphML.
STRUCTURAL_EDGE_TYPES = {
    'is_in_paradata_nodegroup', 'is_in_activity', 'is_in_timebranch',
    'is_part_of', 'has_first_epoch', 'survive_in_epoch',
    'has_linked_resource',
    # Representation/scene-data edges — auxiliary, not formal EM in GraphML
    'has_representation_model', 'has_representation_model_doc',
    'has_representation_model_sf', 'has_semantic_shape',
    # Documentation edges — auxiliary, come from folder scanning not from GraphML
    'has_documentation', 'is_documentation_of',
}

# Node types that should not be exported to GraphML (internal to s3dgraphy)
INTERNAL_NODE_TYPES = {'geo_position', 'link', 'semantic_shape',
                       'representation_model', 'representation_model_doc',
                       'representation_model_special_find', 'author'}


class GraphMLPatcher:
    """
    Patches an existing GraphML file with changes from an in-memory Graph.

    Usage:
        patcher = GraphMLPatcher(filepath, graph)
        patcher.load()
        problems = patcher.validate_emids()
        patcher.update_existing_nodes()
        patcher.add_new_nodes()
        patcher.add_new_edges()
        patcher.ensure_svg_resources()
        patcher.save()
    """

    def __init__(self, filepath: str, graph: Graph):
        """
        Initialize patcher.

        Args:
            filepath: Path to the original GraphML file on disk
            graph: In-memory Graph with current state
        """
        self.filepath = filepath
        self.graph = graph
        self.tree: Optional[ET.ElementTree] = None
        self.root: Optional[ET.Element] = None
        self.key_map: Dict = {'node': {}, 'edge': {}}
        self._new_node_counter = 0
        self._new_edge_counter = 0
        # Maps node UUID -> original GraphML ID (for existing nodes)
        self._uuid_to_original_id: Dict[str, str] = {}
        # Maps node UUID -> generated GraphML ID (for new nodes)
        self._uuid_to_new_id: Dict[str, str] = {}
        # All node IDs in the XML (to avoid collisions)
        self._existing_xml_node_ids: set = set()
        self._existing_xml_edge_ids: set = set()
        # All EMIDs already present in the XML (safety check for add_new_nodes)
        self._existing_xml_emids: set = set()
        # Counter for new nodes added per epoch (for X spacing)
        self._new_nodes_per_epoch: Dict[str, int] = {}

    def load(self):
        """
        Parse the original GraphML file and build key mapping.

        Must be called before any other method.
        """
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"GraphML file not found: {self.filepath}")

        # Register namespaces to preserve them on write
        ET.register_namespace('', NS_GRAPHML)
        ET.register_namespace('y', NS_Y)
        ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        # yfiles java namespace (used in some key definitions)
        ET.register_namespace('java',
                              'http://www.yworks.com/xml/yfiles-common/1.0/java')

        self.tree = ET.parse(self.filepath)
        self.root = self.tree.getroot()

        # Build dynamic key mapping (same logic as importer)
        self.key_map = self._build_key_mapping()

        # Ensure EMID and URI keys exist
        self._ensure_custom_keys()

        # Collect existing node/edge IDs from XML
        self._collect_existing_ids()

        # Build uuid -> original_id mapping from graph nodes
        self._build_reverse_id_map()

        print(f"[GraphMLPatcher] Loaded {self.filepath}")
        print(f"  Node keys: {self.key_map['node']}")
        print(f"  Edge keys: {self.key_map['edge']}")
        print(f"  Existing XML nodes: {len(self._existing_xml_node_ids)}")
        print(f"  Existing XML edges: {len(self._existing_xml_edge_ids)}")
        print(f"  Existing XML EMIDs: {len(self._existing_xml_emids)}")

    def _build_key_mapping(self) -> Dict:
        """
        Build dynamic key mapping from GraphML key definitions.
        Same logic as GraphMLImporter.build_key_mapping().
        """
        key_map = {'node': {}, 'edge': {}}

        for key_elem in self.root.findall(f'.//{{{NS_GRAPHML}}}key'):
            key_id = key_elem.attrib.get('id')
            attr_name = key_elem.attrib.get('attr.name')
            yfiles_type = key_elem.attrib.get('yfiles.type')
            key_for = key_elem.attrib.get('for')

            if attr_name and key_id:
                if key_for == 'node':
                    key_map['node'][attr_name] = key_id
                elif key_for == 'edge':
                    key_map['edge'][attr_name] = key_id

            elif yfiles_type and key_id:
                if key_for == 'node' and yfiles_type == 'nodegraphics':
                    key_map['node']['nodegraphics'] = key_id
                elif key_for == 'edge' and yfiles_type == 'edgegraphics':
                    key_map['edge']['edgegraphics'] = key_id

        return key_map

    def _ensure_custom_keys(self):
        """
        Ensure EMID and URI keys exist in the GraphML.
        Adds them if missing (same logic as importer._ensure_custom_keys).
        """
        existing_keys = {}
        for key_elem in self.root.findall(f'{{{NS_GRAPHML}}}key'):
            attr_name = key_elem.attrib.get('attr.name')
            key_for = key_elem.attrib.get('for')
            if attr_name:
                existing_keys[(attr_name, key_for)] = key_elem

        # Find the max key ID to avoid collisions
        max_id = 0
        for key_elem in self.root.findall(f'{{{NS_GRAPHML}}}key'):
            key_id = key_elem.attrib.get('id', '')
            if key_id.startswith('d'):
                try:
                    max_id = max(max_id, int(key_id[1:]))
                except ValueError:
                    pass

        # Find insertion point (before the first <graph> element)
        graph_elem = self.root.find(f'{{{NS_GRAPHML}}}graph')
        insert_idx = list(self.root).index(graph_elem) if graph_elem is not None else len(list(self.root))

        # Add EMID key for nodes if missing
        if ('EMID', 'node') not in existing_keys:
            max_id += 1
            key = ET.Element(f'{{{NS_GRAPHML}}}key')
            key.set('attr.name', 'EMID')
            key.set('attr.type', 'string')
            key.set('for', 'node')
            key.set('id', f'd{max_id}')
            self.root.insert(insert_idx, key)
            self.key_map['node']['EMID'] = f'd{max_id}'

        # Add EMID key for edges if missing
        if ('EMID', 'edge') not in existing_keys:
            max_id += 1
            key = ET.Element(f'{{{NS_GRAPHML}}}key')
            key.set('attr.name', 'EMID')
            key.set('attr.type', 'string')
            key.set('for', 'edge')
            key.set('id', f'd{max_id}')
            self.root.insert(insert_idx, key)
            self.key_map['edge']['EMID'] = f'd{max_id}'

        # Add URI key for nodes if missing
        if ('URI', 'node') not in existing_keys:
            max_id += 1
            key = ET.Element(f'{{{NS_GRAPHML}}}key')
            key.set('attr.name', 'URI')
            key.set('attr.type', 'string')
            key.set('for', 'node')
            key.set('id', f'd{max_id}')
            self.root.insert(insert_idx, key)
            self.key_map['node']['URI'] = f'd{max_id}'

        # Add URI key for edges if missing
        if ('URI', 'edge') not in existing_keys:
            max_id += 1
            key = ET.Element(f'{{{NS_GRAPHML}}}key')
            key.set('attr.name', 'URI')
            key.set('attr.type', 'string')
            key.set('for', 'edge')
            key.set('id', f'd{max_id}')
            self.root.insert(insert_idx, key)
            self.key_map['edge']['URI'] = f'd{max_id}'

    def _collect_existing_ids(self):
        """Collect all existing node and edge IDs and EMIDs from the XML."""
        emid_key = self.key_map['node'].get('EMID')

        for node_elem in self.root.iter(f'{{{NS_GRAPHML}}}node'):
            nid = node_elem.attrib.get('id')
            if nid:
                self._existing_xml_node_ids.add(nid)
            # Collect existing EMIDs for safety check in add_new_nodes
            if emid_key:
                for data_elem in node_elem.findall(f'{{{NS_GRAPHML}}}data'):
                    if data_elem.attrib.get('key') == emid_key and data_elem.text:
                        self._existing_xml_emids.add(data_elem.text.strip())

        for edge_elem in self.root.iter(f'{{{NS_GRAPHML}}}edge'):
            eid = edge_elem.attrib.get('id')
            if eid:
                self._existing_xml_edge_ids.add(eid)

    def _build_reverse_id_map(self):
        """Build uuid -> original_id mapping from graph node attributes."""
        for node in self.graph.nodes:
            original_id = node.attributes.get('original_id')
            if original_id:
                self._uuid_to_original_id[node.node_id] = original_id

        # Also build for edges
        for edge in self.graph.edges:
            if hasattr(edge, 'attributes'):
                original_edge_id = edge.attributes.get('original_edge_id')
                if original_edge_id:
                    self._uuid_to_original_id[edge.edge_id] = original_edge_id

    def _find_xml_node_by_id(self, original_id: str) -> Optional[ET.Element]:
        """Find a <node> element in the XML by its id attribute."""
        for node_elem in self.root.iter(f'{{{NS_GRAPHML}}}node'):
            if node_elem.attrib.get('id') == original_id:
                return node_elem
        return None

    def _find_xml_edge_by_id(self, original_id: str) -> Optional[ET.Element]:
        """Find an <edge> element in the XML by its id attribute."""
        for edge_elem in self.root.iter(f'{{{NS_GRAPHML}}}edge'):
            if edge_elem.attrib.get('id') == original_id:
                return edge_elem
        return None

    def _get_data_element(self, parent: ET.Element, key_id: str) -> Optional[ET.Element]:
        """Find a <data key="..."> child element."""
        for data_elem in parent.findall(f'{{{NS_GRAPHML}}}data'):
            if data_elem.attrib.get('key') == key_id:
                return data_elem
        return None

    def _set_data_element(self, parent: ET.Element, key_id: str, value: str):
        """Set or create a <data key="..."> child element with given value."""
        data_elem = self._get_data_element(parent, key_id)
        if data_elem is None:
            data_elem = ET.SubElement(parent, f'{{{NS_GRAPHML}}}data')
            data_elem.set('key', key_id)
        data_elem.text = value

    def _generate_new_node_id(self) -> str:
        """Generate a unique new node ID that doesn't collide with existing ones."""
        while True:
            new_id = f"n_s3d_{self._new_node_counter}"
            self._new_node_counter += 1
            if new_id not in self._existing_xml_node_ids:
                self._existing_xml_node_ids.add(new_id)
                return new_id

    def _generate_new_edge_id(self) -> str:
        """Generate a unique new edge ID that doesn't collide with existing ones."""
        while True:
            new_id = f"e_s3d_{self._new_edge_counter}"
            self._new_edge_counter += 1
            if new_id not in self._existing_xml_edge_ids:
                self._existing_xml_edge_ids.add(new_id)
                return new_id

    def _resolve_node_xml_id(self, node_uuid: str) -> Optional[str]:
        """
        Resolve a node UUID to a GraphML XML ID.
        First checks original_id (existing nodes), then generated IDs (new nodes).
        """
        if node_uuid in self._uuid_to_original_id:
            return self._uuid_to_original_id[node_uuid]
        if node_uuid in self._uuid_to_new_id:
            return self._uuid_to_new_id[node_uuid]
        return None

    # -------------------------------------------------------------------------
    # Scenario 1: Update existing nodes
    # -------------------------------------------------------------------------

    def update_existing_nodes(self) -> int:
        """
        Update values of existing nodes in the GraphML XML.

        For each node in the graph that has an original_id:
        - Finds the corresponding <node> in the XML
        - Updates: description text, NodeLabel text, EMID, URI
        - Preserves: position, shape, colors, structure

        Returns:
            Number of nodes updated
        """
        updated = 0
        description_key = self.key_map['node'].get('description')
        emid_key = self.key_map['node'].get('EMID')
        uri_key = self.key_map['node'].get('URI')
        nodegraphics_key = self.key_map['node'].get('nodegraphics')

        for node in self.graph.nodes:
            original_id = node.attributes.get('original_id')
            if not original_id:
                continue

            node_elem = self._find_xml_node_by_id(original_id)
            if node_elem is None:
                continue

            changed = False

            # Update description field
            if description_key and hasattr(node, 'description') and node.description:
                self._set_data_element(node_elem, description_key, node.description)
                changed = True

            # Update EMID
            if emid_key:
                self._set_data_element(node_elem, emid_key, node.node_id)
                changed = True

            # Update URI
            if uri_key:
                uri_value = node.attributes.get('URI')
                if uri_value:
                    self._set_data_element(node_elem, uri_key, uri_value)
                    changed = True

            # Update NodeLabel text (node name) inside nodegraphics
            if nodegraphics_key and hasattr(node, 'name') and node.name:
                gfx_data = self._get_data_element(node_elem, nodegraphics_key)
                if gfx_data is not None:
                    for label_elem in gfx_data.iter(f'{{{NS_Y}}}NodeLabel'):
                        if label_elem.text != node.name:
                            label_elem.text = node.name
                            changed = True
                        break  # Only update the first NodeLabel

            if changed:
                updated += 1

        print(f"[GraphMLPatcher] Updated {updated} existing nodes")
        return updated

    # -------------------------------------------------------------------------
    # Scenario 2+4: Add new nodes
    # -------------------------------------------------------------------------

    def add_new_nodes(self) -> int:
        """
        Add new nodes (created in-memory, not from original GraphML) to the XML.

        For each node in the graph that does NOT have an original_id:
        - Generates a new GraphML node ID
        - Creates the XML element with correct yEd graphics for the node type
        - Appends to the first top-level <graph> element
        - Does NOT calculate layout positions (user will do that in yEd)

        Returns:
            Number of nodes added
        """
        added = 0
        graph_elem = self.root.find(f'{{{NS_GRAPHML}}}graph')
        if graph_elem is None:
            print("[GraphMLPatcher] WARNING: No <graph> element found in XML")
            return 0

        # Find the deepest graph to insert into (typically inside the swimlane)
        # For now, find any nested graph or use top-level
        target_graph = self._find_insertion_graph(graph_elem)

        for node in self.graph.nodes:
            # Skip nodes that already exist in the XML (have original_id from import)
            if node.attributes.get('original_id'):
                continue

            # Skip internal node types
            node_type = getattr(node, 'node_type', '')
            if node_type in INTERNAL_NODE_TYPES:
                continue

            # Skip DocumentNodes without original_id: they come from auxiliary
            # data (folder scanning, representation models) and are not part
            # of the EM formal language in GraphML
            if isinstance(node, DocumentNode):
                continue

            # Safety check: skip nodes whose EMID (node_id) already exists in the XML.
            # This catches nodes that were imported but lost their original_id
            # (e.g., deduplicated DocumentNodes, auxiliary imports).
            if node.node_id in self._existing_xml_emids:
                print(f"[GraphMLPatcher] Skipping node '{getattr(node, 'name', '?')}' "
                      f"(type={node_type}): EMID {node.node_id[:12]}... already in XML")
                continue

            print(f"[GraphMLPatcher] Adding new node: '{getattr(node, 'name', '?')}' "
                  f"(type={node_type}, id={node.node_id[:12]}...)")

            # Calculate position within the correct epoch lane
            x, y = self._calculate_node_position(node)

            # Generate XML for this node
            new_node_id = self._generate_new_node_id()
            self._uuid_to_new_id[node.node_id] = new_node_id

            node_xml = self._create_node_xml(node, new_node_id, x, y)
            if node_xml is not None:
                target_graph.append(node_xml)
                added += 1

        print(f"[GraphMLPatcher] Added {added} new nodes")
        return added

    def _calculate_node_position(self, node: Node) -> Tuple[float, float]:
        """
        Calculate (x, y) position for a new node based on its epoch assignment.

        Uses the has_first_epoch edge to find which epoch the node belongs to,
        then positions it within that epoch's Y range in the swimlane.

        Returns:
            (x, y) tuple. Falls back to (0.0, 0.0) if no epoch found.
        """
        from ...nodes.epoch_node import EpochNode

        # Find connected epochs via has_first_epoch
        epoch_node = None
        for edge in self.graph.edges:
            if edge.edge_source == node.node_id and edge.edge_type == 'has_first_epoch':
                target = self.graph.find_node_by_id(edge.edge_target)
                if isinstance(target, EpochNode):
                    epoch_node = target
                    break
            elif edge.edge_target == node.node_id and edge.edge_type == 'has_first_epoch':
                source = self.graph.find_node_by_id(edge.edge_source)
                if isinstance(source, EpochNode):
                    epoch_node = source
                    break

        if not epoch_node:
            # Try finding epoch through a connected stratigraphic node
            # (for paradata nodes connected to a US that has an epoch)
            parent_us = self._find_parent_stratigraphic_node(node)
            if parent_us:
                for edge in self.graph.edges:
                    if edge.edge_source == parent_us.node_id and edge.edge_type == 'has_first_epoch':
                        target = self.graph.find_node_by_id(edge.edge_target)
                        if isinstance(target, EpochNode):
                            epoch_node = target
                            break

        if not epoch_node or not hasattr(epoch_node, 'min_y') or not hasattr(epoch_node, 'max_y'):
            print(f"[GraphMLPatcher] No epoch found for node '{getattr(node, 'name', '?')}', "
                  f"using default position")
            return (0.0, 0.0)

        # Calculate Y: center within epoch band
        y = epoch_node.min_y + (epoch_node.max_y - epoch_node.min_y) / 2.0

        # Calculate X: spread new nodes horizontally within the epoch
        epoch_key = epoch_node.node_id
        col = self._new_nodes_per_epoch.get(epoch_key, 0)
        self._new_nodes_per_epoch[epoch_key] = col + 1
        x = 100.0 + (col % 8) * 150.0

        print(f"[GraphMLPatcher] Positioned '{getattr(node, 'name', '?')}' in epoch "
              f"'{epoch_node.name}' at ({x:.0f}, {y:.0f})")

        return (x, y)

    def _find_parent_stratigraphic_node(self, node: Node) -> Optional[StratigraphicNode]:
        """Find the stratigraphic node connected to this paradata node."""
        for edge in self.graph.edges:
            if edge.edge_target == node.node_id and edge.edge_type == 'has_property':
                source = self.graph.find_node_by_id(edge.edge_source)
                if isinstance(source, StratigraphicNode):
                    return source
            if edge.edge_source == node.node_id and edge.edge_type in (
                    'is_in_paradata_nodegroup', 'has_paradata_nodegroup'):
                # Node is in a PD group connected to a US
                group = self.graph.find_node_by_id(edge.edge_target)
                if group:
                    for e2 in self.graph.edges:
                        if e2.edge_target == group.node_id and \
                           e2.edge_type == 'has_paradata_nodegroup':
                            us = self.graph.find_node_by_id(e2.edge_source)
                            if isinstance(us, StratigraphicNode):
                                return us
        return None

    def _find_insertion_graph(self, top_graph: ET.Element) -> ET.Element:
        """
        Find the best <graph> element to insert new nodes into.

        Prefers the first nested graph inside a group/swimlane node (n0),
        as this is typically the main container in EM GraphML files.
        Falls back to the top-level graph.
        """
        # Look for a nested graph inside the first node (typical swimlane pattern)
        for node_elem in top_graph.findall(f'{{{NS_GRAPHML}}}node'):
            nested_graph = node_elem.find(f'{{{NS_GRAPHML}}}graph')
            if nested_graph is not None:
                return nested_graph

        return top_graph

    def _create_node_xml(self, node: Node, xml_id: str,
                          x: float = 0.0, y: float = 0.0) -> Optional[ET.Element]:
        """
        Create a GraphML <node> XML element for a given node.

        Dispatches to type-specific generators based on node_type.

        Args:
            node: The graph node to create XML for
            xml_id: The GraphML node ID to assign
            x: X coordinate within the swimlane
            y: Y coordinate within the swimlane (determines epoch lane)
        """
        node_type = getattr(node, 'node_type', '')

        if isinstance(node, StratigraphicNode):
            return self._create_stratigraphic_node_xml(node, xml_id, x, y)
        elif isinstance(node, PropertyNode):
            return self._create_property_node_xml(node, xml_id, x, y)
        elif isinstance(node, DocumentNode):
            return self._create_document_node_xml(node, xml_id, x, y)
        elif isinstance(node, ExtractorNode):
            return self._create_extractor_node_xml(node, xml_id, x, y)
        elif isinstance(node, CombinerNode):
            return self._create_combiner_node_xml(node, xml_id, x, y)
        elif isinstance(node, ParadataNodeGroup):
            return self._create_paradata_group_xml(node, xml_id, x, y)
        elif isinstance(node, EpochNode):
            # Epoch nodes are part of the swimlane structure, skip
            return None
        else:
            print(f"[GraphMLPatcher] Skipping unsupported node type: {node_type}")
            return None

    def _create_stratigraphic_node_xml(self, node: StratigraphicNode,
                                        xml_id: str,
                                        x: float = 0.0,
                                        y: float = 0.0) -> ET.Element:
        """Create ShapeNode XML for a stratigraphic node."""
        from .node_registry import NodeRegistry
        registry = NodeRegistry()

        node_elem = ET.Element(f'{{{NS_GRAPHML}}}node')
        node_elem.set('id', xml_id)

        # Description data
        description_key = self.key_map['node'].get('description')
        if description_key and node.description:
            self._set_data_element(node_elem, description_key, node.description)

        # EMID
        emid_key = self.key_map['node'].get('EMID')
        if emid_key:
            self._set_data_element(node_elem, emid_key, node.node_id)

        # URI
        uri_key = self.key_map['node'].get('URI')
        uri_value = node.attributes.get('URI')
        if uri_key and uri_value:
            self._set_data_element(node_elem, uri_key, uri_value)

        # Nodegraphics - ShapeNode
        gfx_key = self.key_map['node'].get('nodegraphics')
        if gfx_key:
            data_gfx = ET.SubElement(node_elem, f'{{{NS_GRAPHML}}}data')
            data_gfx.set('key', gfx_key)

            # Get visual properties from registry or stored attributes
            visual_props = registry.get_visual_properties(node.node_type)
            shape = node.attributes.get('shape',
                                         visual_props.shape if visual_props else 'rectangle')
            fill_color = node.attributes.get('fill_color',
                                              visual_props.fill_color if visual_props else '#FFFFFF')
            border_color = node.attributes.get('border_style',
                                                visual_props.border_color if visual_props else '#000000')
            border_type = visual_props.border_type if visual_props else 'line'
            border_width = str(visual_props.border_width) if visual_props else '4.0'
            text_color = visual_props.text_color if visual_props else '#000000'

            shape_node = ET.SubElement(data_gfx, f'{{{NS_Y}}}ShapeNode')

            # Geometry — positioned within the correct epoch lane
            geometry = ET.SubElement(shape_node, f'{{{NS_Y}}}Geometry')
            geometry.set('height', '30.0')
            label_text = node.name or node.node_type
            width = max(90.0, len(label_text) * 7.0 + 20)
            geometry.set('width', str(width))
            geometry.set('x', str(x))
            geometry.set('y', str(y))

            # Fill
            fill = ET.SubElement(shape_node, f'{{{NS_Y}}}Fill')
            fill.set('color', fill_color)
            fill.set('transparent', 'false')

            # BorderStyle
            border = ET.SubElement(shape_node, f'{{{NS_Y}}}BorderStyle')
            border.set('color', border_color)
            border.set('type', border_type)
            border.set('width', border_width)

            # NodeLabel
            label = ET.SubElement(shape_node, f'{{{NS_Y}}}NodeLabel')
            label.set('alignment', 'center')
            label.set('autoSizePolicy', 'content')
            label.set('fontFamily', 'Dialog')
            label.set('fontSize', '12')
            label.set('fontStyle', 'plain')
            label.set('hasBackgroundColor', 'false')
            label.set('hasLineColor', 'false')
            label.set('textColor', text_color)
            label.set('visible', 'true')
            label.text = label_text

            # Shape
            shape_elem = ET.SubElement(shape_node, f'{{{NS_Y}}}Shape')
            shape_elem.set('type', shape)

        return node_elem

    def _create_property_node_xml(self, node: PropertyNode,
                                   xml_id: str,
                                   x: float = 0.0,
                                   y: float = 0.0) -> ET.Element:
        """Create GenericNode BPMN Annotation XML for a PropertyNode."""
        node_elem = ET.Element(f'{{{NS_GRAPHML}}}node')
        node_elem.set('id', xml_id)

        # Description
        description_key = self.key_map['node'].get('description')
        if description_key and node.description:
            self._set_data_element(node_elem, description_key, node.description)

        # EMID
        emid_key = self.key_map['node'].get('EMID')
        if emid_key:
            self._set_data_element(node_elem, emid_key, node.node_id)

        # Nodegraphics
        gfx_key = self.key_map['node'].get('nodegraphics')
        if gfx_key:
            data_gfx = ET.SubElement(node_elem, f'{{{NS_GRAPHML}}}data')
            data_gfx.set('key', gfx_key)

            generic = ET.SubElement(data_gfx, f'{{{NS_Y}}}GenericNode')
            generic.set('configuration', 'com.yworks.bpmn.Artifact.withShadow')

            geometry = ET.SubElement(generic, f'{{{NS_Y}}}Geometry')
            label_text = node.name or 'property'
            width = max(62.75, len(label_text) * 6.0 + 20)
            geometry.set('height', '30.0')
            geometry.set('width', str(width))
            geometry.set('x', str(x))
            geometry.set('y', str(y))

            fill = ET.SubElement(generic, f'{{{NS_Y}}}Fill')
            fill.set('color', '#FFFFFFE6')
            fill.set('transparent', 'false')

            border = ET.SubElement(generic, f'{{{NS_Y}}}BorderStyle')
            border.set('color', '#000000')
            border.set('type', 'line')
            border.set('width', '1.0')

            label = ET.SubElement(generic, f'{{{NS_Y}}}NodeLabel')
            label.set('alignment', 'center')
            label.set('autoSizePolicy', 'content')
            label.set('fontFamily', 'Dialog')
            label.set('fontSize', '12')
            label.set('fontStyle', 'plain')
            label.set('hasBackgroundColor', 'false')
            label.set('hasLineColor', 'false')
            label.set('textColor', '#000000')
            label.set('visible', 'true')
            label.text = label_text

            # BPMN StyleProperties
            style_props = ET.SubElement(generic, f'{{{NS_Y}}}StyleProperties')
            self._add_bpmn_style_property(style_props, 'com.yworks.bpmn.icon.line.color',
                                           'java.awt.Color', '#000000')
            self._add_bpmn_style_property(style_props, 'com.yworks.bpmn.icon.fill2',
                                           'java.awt.Color', '#d4d4d4cc')
            self._add_bpmn_style_property(style_props, 'com.yworks.bpmn.icon.fill',
                                           'java.awt.Color', '#ffffffe6')
            self._add_bpmn_style_property(style_props, 'com.yworks.bpmn.type',
                                           'com.yworks.yfiles.bpmn.view.BPMNTypeEnum',
                                           'ARTIFACT_TYPE_ANNOTATION')

        return node_elem

    def _create_document_node_xml(self, node: DocumentNode,
                                   xml_id: str,
                                   x: float = 0.0,
                                   y: float = 0.0) -> ET.Element:
        """Create GenericNode BPMN Data Object XML for a DocumentNode."""
        node_elem = ET.Element(f'{{{NS_GRAPHML}}}node')
        node_elem.set('id', xml_id)

        description_key = self.key_map['node'].get('description')
        if description_key and node.description:
            self._set_data_element(node_elem, description_key, node.description)

        emid_key = self.key_map['node'].get('EMID')
        if emid_key:
            self._set_data_element(node_elem, emid_key, node.node_id)

        gfx_key = self.key_map['node'].get('nodegraphics')
        if gfx_key:
            data_gfx = ET.SubElement(node_elem, f'{{{NS_GRAPHML}}}data')
            data_gfx.set('key', gfx_key)

            generic = ET.SubElement(data_gfx, f'{{{NS_Y}}}GenericNode')
            generic.set('configuration', 'com.yworks.bpmn.Artifact.withShadow')

            geometry = ET.SubElement(generic, f'{{{NS_Y}}}Geometry')
            geometry.set('height', '63.79')
            geometry.set('width', '42.80')
            geometry.set('x', str(x))
            geometry.set('y', str(y))

            fill = ET.SubElement(generic, f'{{{NS_Y}}}Fill')
            fill.set('color', '#FFFFFFE6')
            fill.set('transparent', 'false')

            border = ET.SubElement(generic, f'{{{NS_Y}}}BorderStyle')
            border.set('color', '#000000')
            border.set('type', 'line')
            border.set('width', '1.0')

            label = ET.SubElement(generic, f'{{{NS_Y}}}NodeLabel')
            label.set('alignment', 'center')
            label.set('autoSizePolicy', 'content')
            label.set('fontFamily', 'Dialog')
            label.set('fontSize', '8')
            label.set('fontStyle', 'plain')
            label.set('hasBackgroundColor', 'false')
            label.set('hasLineColor', 'false')
            label.set('textColor', '#000000')
            label.set('visible', 'true')
            label.text = node.name or 'Document'

            style_props = ET.SubElement(generic, f'{{{NS_Y}}}StyleProperties')
            self._add_bpmn_style_property(style_props, 'com.yworks.bpmn.icon.line.color',
                                           'java.awt.Color', '#000000')
            self._add_bpmn_style_property(style_props, 'com.yworks.bpmn.icon.fill2',
                                           'java.awt.Color', '#d4d4d4cc')
            self._add_bpmn_style_property(style_props, 'com.yworks.bpmn.icon.fill',
                                           'java.awt.Color', '#ffffffe6')
            self._add_bpmn_style_property(style_props, 'com.yworks.bpmn.type',
                                           'com.yworks.yfiles.bpmn.view.BPMNTypeEnum',
                                           'ARTIFACT_TYPE_DATA_OBJECT')
            self._add_bpmn_style_property(style_props, 'com.yworks.bpmn.dataObjectType',
                                           'com.yworks.yfiles.bpmn.view.DataObjectTypeEnum',
                                           'DATA_OBJECT_TYPE_PLAIN')

        return node_elem

    def _create_extractor_node_xml(self, node: ExtractorNode,
                                    xml_id: str,
                                    x: float = 0.0,
                                    y: float = 0.0) -> ET.Element:
        """Create SVGNode XML for an ExtractorNode."""
        return self._create_svg_node_xml(node, xml_id, svg_refid='1', x=x, y=y)

    def _create_combiner_node_xml(self, node: CombinerNode,
                                   xml_id: str,
                                   x: float = 0.0,
                                   y: float = 0.0) -> ET.Element:
        """Create SVGNode XML for a CombinerNode."""
        return self._create_svg_node_xml(node, xml_id, svg_refid='2', x=x, y=y)

    def _create_svg_node_xml(self, node: Node, xml_id: str,
                              svg_refid: str,
                              x: float = 0.0,
                              y: float = 0.0) -> ET.Element:
        """Create SVGNode XML for ExtractorNode or CombinerNode."""
        node_elem = ET.Element(f'{{{NS_GRAPHML}}}node')
        node_elem.set('id', xml_id)

        description_key = self.key_map['node'].get('description')
        if description_key and node.description:
            self._set_data_element(node_elem, description_key, node.description)

        emid_key = self.key_map['node'].get('EMID')
        if emid_key:
            self._set_data_element(node_elem, emid_key, node.node_id)

        gfx_key = self.key_map['node'].get('nodegraphics')
        if gfx_key:
            data_gfx = ET.SubElement(node_elem, f'{{{NS_GRAPHML}}}data')
            data_gfx.set('key', gfx_key)

            svg_node = ET.SubElement(data_gfx, f'{{{NS_Y}}}SVGNode')

            geometry = ET.SubElement(svg_node, f'{{{NS_Y}}}Geometry')
            geometry.set('height', '25.0')
            geometry.set('width', '25.0')
            geometry.set('x', str(x))
            geometry.set('y', str(y))

            fill = ET.SubElement(svg_node, f'{{{NS_Y}}}Fill')
            fill.set('color', '#CCCCFF')
            fill.set('transparent', 'false')

            border = ET.SubElement(svg_node, f'{{{NS_Y}}}BorderStyle')
            border.set('color', '#000000')
            border.set('type', 'line')
            border.set('width', '1.0')

            label = ET.SubElement(svg_node, f'{{{NS_Y}}}NodeLabel')
            label.set('alignment', 'center')
            label.set('fontSize', '10')
            label.set('visible', 'true')
            label.text = node.name or ''

            svg_props = ET.SubElement(svg_node, f'{{{NS_Y}}}SVGNodeProperties')
            svg_props.set('usingVisualBounds', 'true')

            svg_model = ET.SubElement(svg_node, f'{{{NS_Y}}}SVGModel')
            svg_model.set('svgBoundsPolicy', '0')
            svg_content = ET.SubElement(svg_model, f'{{{NS_Y}}}SVGContent')
            svg_content.set('refid', svg_refid)

        return node_elem

    def _create_paradata_group_xml(self, node: ParadataNodeGroup,
                                    xml_id: str,
                                    x: float = 0.0,
                                    y: float = 0.0) -> ET.Element:
        """Create ProxyAutoBoundsNode XML for a ParadataNodeGroup."""
        node_elem = ET.Element(f'{{{NS_GRAPHML}}}node')
        node_elem.set('id', xml_id)
        node_elem.set('yfiles.foldertype', 'folder')

        emid_key = self.key_map['node'].get('EMID')
        if emid_key:
            self._set_data_element(node_elem, emid_key, node.node_id)

        gfx_key = self.key_map['node'].get('nodegraphics')
        if gfx_key:
            data_gfx = ET.SubElement(node_elem, f'{{{NS_GRAPHML}}}data')
            data_gfx.set('key', gfx_key)

            proxy = ET.SubElement(data_gfx, f'{{{NS_Y}}}ProxyAutoBoundsNode')
            realizers = ET.SubElement(proxy, f'{{{NS_Y}}}Realizers')
            realizers.set('active', '1')  # Closed by default

            # Open state
            self._add_group_realizer(realizers, node.name or 'PD', '#FFCC99',
                                      closed=False)
            # Closed state
            self._add_group_realizer(realizers, node.name or 'PD', '#FFCC99',
                                      closed=True)

        # Nested graph for group contents
        nested_graph = ET.SubElement(node_elem, f'{{{NS_GRAPHML}}}graph')
        nested_graph.set('edgedefault', 'directed')
        nested_graph.set('id', f'{xml_id}:')

        return node_elem

    def _add_group_realizer(self, realizers: ET.Element, label_text: str,
                             bg_color: str, closed: bool):
        """Add a GroupNode realizer (open or closed state)."""
        group_node = ET.SubElement(realizers, f'{{{NS_Y}}}GroupNode')

        geometry = ET.SubElement(group_node, f'{{{NS_Y}}}Geometry')
        geometry.set('height', '30.0' if closed else '120.0')
        geometry.set('width', '118.0' if closed else '376.0')
        # Group geometry is set by yEd auto-bounds; these are defaults
        geometry.set('x', '0.0')
        geometry.set('y', '0.0')

        fill = ET.SubElement(group_node, f'{{{NS_Y}}}Fill')
        fill.set('color', '#F5F5F5')
        fill.set('transparent', 'false')

        border = ET.SubElement(group_node, f'{{{NS_Y}}}BorderStyle')
        border.set('color', '#000000')
        border.set('type', 'dashed')
        border.set('width', '1.0')

        label = ET.SubElement(group_node, f'{{{NS_Y}}}NodeLabel')
        label.set('alignment', 'right')
        label.set('autoSizePolicy', 'node_width')
        label.set('backgroundColor', bg_color)
        label.set('fontSize', '15')
        label.set('fontStyle', 'plain')
        label.set('hasLineColor', 'false')
        label.set('modelName', 'internal')
        label.set('modelPosition', 't')
        label.set('textColor', '#000000')
        label.set('visible', 'true')
        label.text = label_text

        shape = ET.SubElement(group_node, f'{{{NS_Y}}}Shape')
        shape.set('type', 'roundrectangle')

        state = ET.SubElement(group_node, f'{{{NS_Y}}}State')
        state.set('closed', 'true' if closed else 'false')

    def _add_bpmn_style_property(self, style_props: ET.Element,
                                  name: str, cls: str, value: str):
        """Add a BPMN StyleProperty element."""
        prop = ET.SubElement(style_props, f'{{{NS_Y}}}Property')
        prop.set('class', cls)
        prop.set('name', name)
        prop.set('value', value)

    # -------------------------------------------------------------------------
    # Add new edges
    # -------------------------------------------------------------------------

    def add_new_edges(self) -> int:
        """
        Add new edges to the GraphML XML.

        For each edge in the graph that does NOT have an original_edge_id:
        - Generates a new edge ID
        - Creates <edge> XML with correct line style for the edge type
        - Resolves source/target using original_id or generated ID

        Skips:
        - Edges with original_edge_id (already in the XML)
        - Structural edges (represented by XML nesting, not <edge> elements)
        - Derived has_property edges where the target PropertyNode is inside
          a ParadataNodeGroup (these are shortcuts created by
          connect_paradatagroup_propertynode_to_stratigraphic, the real
          GraphML relationship is US → ParadataNodeGroup)

        Returns:
            Number of edges added
        """
        added = 0
        graph_elem = self.root.find(f'{{{NS_GRAPHML}}}graph')
        if graph_elem is None:
            return 0

        # Build set of PropertyNode IDs that are inside ParadataNodeGroups
        # These have is_in_paradata_nodegroup edges pointing to a PD group
        property_nodes_in_groups = set()
        for e in self.graph.edges:
            if e.edge_type == 'is_in_paradata_nodegroup':
                source_node = self.graph.find_node_by_id(e.edge_source)
                if source_node and isinstance(source_node, PropertyNode):
                    property_nodes_in_groups.add(e.edge_source)

        # Find the insertion graph (same as nodes — typically inside swimlane)
        target_graph = self._find_insertion_graph(graph_elem)

        for edge in self.graph.edges:
            # Skip edges that already exist in the XML
            if hasattr(edge, 'attributes') and edge.attributes.get('original_edge_id'):
                continue

            # Skip structural edges (represented by XML nesting)
            if edge.edge_type in STRUCTURAL_EDGE_TYPES:
                continue

            # Skip derived has_property edges to PropertyNodes inside PD groups
            # (the relationship is already represented by US → ParadataNodeGroup)
            if (edge.edge_type == 'has_property'
                    and edge.edge_target in property_nodes_in_groups):
                continue

            # Resolve source and target IDs
            source_xml_id = self._resolve_node_xml_id(edge.edge_source)
            target_xml_id = self._resolve_node_xml_id(edge.edge_target)

            if not source_xml_id or not target_xml_id:
                continue

            edge_xml = self._create_edge_xml(edge, source_xml_id, target_xml_id)
            if edge_xml is not None:
                target_graph.append(edge_xml)
                added += 1

        print(f"[GraphMLPatcher] Added {added} new edges")
        return added

    def _create_edge_xml(self, edge: Edge, source_id: str,
                          target_id: str) -> ET.Element:
        """Create an <edge> XML element."""
        edge_id = self._generate_new_edge_id()

        edge_elem = ET.Element(f'{{{NS_GRAPHML}}}edge')
        edge_elem.set('id', edge_id)
        edge_elem.set('source', source_id)
        edge_elem.set('target', target_id)

        # EMID
        emid_key = self.key_map['edge'].get('EMID')
        if emid_key:
            self._set_data_element(edge_elem, emid_key, edge.edge_id)

        # URI
        uri_key = self.key_map['edge'].get('URI')
        if uri_key and hasattr(edge, 'attributes'):
            uri_val = edge.attributes.get('URI')
            if uri_val:
                self._set_data_element(edge_elem, uri_key, uri_val)

        # Edge graphics
        gfx_key = self.key_map['edge'].get('edgegraphics')
        if gfx_key:
            data_gfx = ET.SubElement(edge_elem, f'{{{NS_GRAPHML}}}data')
            data_gfx.set('key', gfx_key)

            polyline = ET.SubElement(data_gfx, f'{{{NS_Y}}}PolyLineEdge')

            path = ET.SubElement(polyline, f'{{{NS_Y}}}Path')
            path.set('sx', '0.0')
            path.set('sy', '0.0')
            path.set('tx', '0.0')
            path.set('ty', '0.0')

            line_type, line_width = EDGE_TYPE_TO_LINE_STYLE.get(
                edge.edge_type, ('line', '1.0'))

            line_style = ET.SubElement(polyline, f'{{{NS_Y}}}LineStyle')
            line_style.set('color', '#000000')
            line_style.set('type', line_type)
            line_style.set('width', line_width)

            arrows = ET.SubElement(polyline, f'{{{NS_Y}}}Arrows')
            arrows.set('source', 'none')
            arrows.set('target', 'standard')

            bend = ET.SubElement(polyline, f'{{{NS_Y}}}BendStyle')
            bend.set('smoothed', 'false')

        return edge_elem

    # -------------------------------------------------------------------------
    # SVG Resources
    # -------------------------------------------------------------------------

    def ensure_svg_resources(self):
        """
        Ensure SVG resources section exists if ExtractorNode/CombinerNode/ContinuityNode
        are present in the graph.
        """
        has_svg_nodes = any(
            isinstance(n, (ExtractorNode, CombinerNode))
            or getattr(n, 'node_type', '') == 'BR'
            for n in self.graph.nodes
        )

        if not has_svg_nodes:
            return

        # Check if resources already exist
        resources_key = None
        for key_elem in self.root.findall(f'{{{NS_GRAPHML}}}key'):
            if key_elem.attrib.get('yfiles.type') == 'resources':
                resources_key = key_elem.attrib.get('id')
                break

        if resources_key is None:
            return  # No resources key definition found

        # Check if resources data already exists
        for data_elem in self.root.findall(f'{{{NS_GRAPHML}}}data'):
            if data_elem.attrib.get('key') == resources_key:
                return  # Resources already present

        # Add resources section using the canvas generator
        from .canvas_generator import CanvasGenerator
        canvas = CanvasGenerator()

        # We need to create the resources using lxml, then convert to xml.etree
        # Since the main exporter uses lxml but we use xml.etree, we need
        # to serialize and re-parse
        from lxml import etree as lxml_ET
        lxml_resources = canvas.generate_svg_resources()
        resources_str = lxml_ET.tostring(lxml_resources, encoding='unicode')

        # Re-parse with xml.etree
        resources_elem = ET.fromstring(resources_str)
        # Update the key reference to match our file's resources key
        resources_elem.set('key', resources_key)
        self.root.append(resources_elem)

        print(f"[GraphMLPatcher] Added SVG resources section")

    # -------------------------------------------------------------------------
    # EMID Validation
    # -------------------------------------------------------------------------

    def validate_emids(self) -> List[str]:
        """
        Validate EMID fields in the GraphML for duplicates.

        Checks both the in-memory graph and the XML file.

        Returns:
            List of warning messages about duplicate EMIDs
        """
        problems = []

        # Check in-memory graph for duplicate EMIDs
        emid_to_nodes: Dict[str, List[str]] = {}
        for node in self.graph.nodes:
            emid = node.node_id
            if emid not in emid_to_nodes:
                emid_to_nodes[emid] = []
            emid_to_nodes[emid].append(node.name if hasattr(node, 'name') else str(node.node_id))

        for emid, names in emid_to_nodes.items():
            if len(names) > 1:
                msg = (
                    f"Duplicate EMID detected: {emid[:20]}... "
                    f"is shared by nodes: {', '.join(names)}.\n"
                    f"This happens when you duplicate nodes in yEd using Ctrl+D. "
                    f"yEd copies the EMID field, creating duplicates.\n"
                    f"Always create new nodes from the EM palette template, "
                    f"not by duplicating existing nodes."
                )
                problems.append(msg)

        # Also check the XML file directly
        emid_key = self.key_map['node'].get('EMID')
        if emid_key:
            xml_emid_to_ids: Dict[str, List[str]] = {}
            for node_elem in self.root.iter(f'{{{NS_GRAPHML}}}node'):
                data_elem = self._get_data_element(node_elem, emid_key)
                if data_elem is not None and data_elem.text:
                    emid_val = data_elem.text.strip()
                    if emid_val:
                        node_id = node_elem.attrib.get('id', '?')
                        if emid_val not in xml_emid_to_ids:
                            xml_emid_to_ids[emid_val] = []
                        xml_emid_to_ids[emid_val].append(node_id)

            for emid_val, node_ids in xml_emid_to_ids.items():
                if len(node_ids) > 1:
                    msg = (
                        f"Duplicate EMID in GraphML file: {emid_val[:20]}... "
                        f"found in XML nodes: {', '.join(node_ids)}.\n"
                        f"This happens when duplicating nodes in yEd (Ctrl+D). "
                        f"Always use the EM palette template for new nodes."
                    )
                    problems.append(msg)

        if problems:
            print(f"[GraphMLPatcher] Found {len(problems)} EMID issues")
        else:
            print(f"[GraphMLPatcher] EMID validation passed - no duplicates found")

        return problems

    # -------------------------------------------------------------------------
    # Save
    # -------------------------------------------------------------------------

    def save(self, output_path: str = None):
        """
        Write the patched XML to disk.

        Args:
            output_path: Path to write to. If None, overwrites the original file.
        """
        if self.tree is None:
            raise RuntimeError("Call load() before save()")

        path = output_path or self.filepath
        self.tree.write(path, encoding='UTF-8', xml_declaration=True)
        print(f"[GraphMLPatcher] Saved to {path}")

    # -------------------------------------------------------------------------
    # Convenience: full patch pipeline
    # -------------------------------------------------------------------------

    def patch(self, output_path: str = None) -> Tuple[int, int, int, List[str]]:
        """
        Run the complete patch pipeline.

        Args:
            output_path: Optional output path (None = overwrite original)

        Returns:
            Tuple of (nodes_updated, nodes_added, edges_added, emid_problems)
        """
        self.load()
        problems = self.validate_emids()
        nodes_updated = self.update_existing_nodes()
        nodes_added = self.add_new_nodes()
        edges_added = self.add_new_edges()
        self.ensure_svg_resources()
        self.save(output_path)
        return nodes_updated, nodes_added, edges_added, problems
