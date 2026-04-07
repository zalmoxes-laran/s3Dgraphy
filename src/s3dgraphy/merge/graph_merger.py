"""
Graph merger for s3dgraphy.

Compares an existing graph with incoming data (e.g., from XLSX)
and produces a list of conflicts that need user resolution.

Used by the Blender conflict resolution UI to let users decide
which changes to accept or reject when merging updated stratigraphy data.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from ..graph import Graph
from ..nodes.stratigraphic_node import StratigraphicNode
from ..nodes.epoch_node import EpochNode
from ..edges.edge import Edge


# Stratigraphic edge types that define relationships between units
STRATIGRAPHIC_EDGE_TYPES = {
    'overlies', 'is_overlain_by',
    'cuts', 'is_cut_by',
    'fills', 'is_filled_by',
    'abuts', 'is_abutted_by',
    'is_bonded_to', 'is_physically_equal_to',
}


@dataclass
class Conflict:
    """
    Represents a single conflict between existing and incoming data.

    Attributes:
        node_name: Name of the node involved (e.g., "USM01")
        field: Name of the conflicting field (e.g., "description", "edge:overlies")
        current_value: Value in the existing graph/GraphML
        incoming_value: Value from the incoming source (XLSX)
        conflict_type: Type of conflict:
            - "value_changed": a field value differs
            - "edge_added": new edge in incoming, not in existing
            - "edge_removed": edge in existing, not in incoming
            - "node_added": new node in incoming only (no conflict, auto-added)
        resolved: Whether the user has resolved this conflict
        accepted: True = use incoming value, False = keep current value
    """
    node_name: str
    field: str
    current_value: str
    incoming_value: str
    conflict_type: str
    resolved: bool = False
    accepted: bool = False

    @property
    def display_field(self) -> str:
        """Human-readable field name for UI display."""
        if self.field.startswith('edge:'):
            return f"Relationship: {self.field[5:]}"
        return self.field.replace('_', ' ').title()

    @property
    def display_summary(self) -> str:
        """One-line summary for conflict list."""
        if self.conflict_type == 'value_changed':
            return f"{self.node_name}: {self.display_field} changed"
        elif self.conflict_type == 'edge_added':
            return f"{self.node_name}: new {self.display_field}"
        elif self.conflict_type == 'edge_removed':
            return f"{self.node_name}: removed {self.display_field}"
        elif self.conflict_type == 'node_added':
            return f"{self.node_name}: new node"
        return f"{self.node_name}: {self.field}"


class GraphMerger:
    """
    Compares an existing graph with incoming data and generates conflicts.

    Usage:
        merger = GraphMerger()
        conflicts = merger.compare(existing_graph, incoming_graph)
        # ... user resolves conflicts via UI ...
        merger.apply_resolutions(existing_graph, conflicts)
    """

    def compare(self, existing: Graph, incoming: Graph) -> List[Conflict]:
        """
        Compare two graphs node-by-node and edge-by-edge.

        For nodes with the same name in both graphs:
        - Compares name, description
        - Compares stratigraphic edges (overlies, cuts, fills, etc.)
        - Creates Conflict entries for any differences

        Nodes only in incoming: marked as "node_added" (auto-accepted)
        Nodes only in existing: no action (preserved as-is)

        Args:
            existing: The current in-memory graph (from GraphML import)
            incoming: The new graph (from XLSX import)

        Returns:
            List of Conflict objects, sorted by node name
        """
        conflicts: List[Conflict] = []

        # Build name-based lookup maps
        existing_by_name = self._build_node_name_map(existing)
        incoming_by_name = self._build_node_name_map(incoming)

        # Build edge maps: {source_name: {edge_type: set(target_names)}}
        existing_edges = self._build_edge_map(existing)
        incoming_edges = self._build_edge_map(incoming)

        # Compare nodes present in both
        for name, incoming_node in incoming_by_name.items():
            if name in existing_by_name:
                existing_node = existing_by_name[name]

                # Compare description
                existing_desc = existing_node.description or ''
                incoming_desc = incoming_node.description or ''
                if existing_desc.strip() != incoming_desc.strip():
                    conflicts.append(Conflict(
                        node_name=name,
                        field='description',
                        current_value=existing_desc,
                        incoming_value=incoming_desc,
                        conflict_type='value_changed'
                    ))

                # Compare stratigraphic edges
                for edge_type in STRATIGRAPHIC_EDGE_TYPES:
                    existing_targets = existing_edges.get(name, {}).get(edge_type, set())
                    incoming_targets = incoming_edges.get(name, {}).get(edge_type, set())

                    # Edges added in incoming
                    for target in incoming_targets - existing_targets:
                        conflicts.append(Conflict(
                            node_name=name,
                            field=f'edge:{edge_type}',
                            current_value='',
                            incoming_value=target,
                            conflict_type='edge_added'
                        ))

                    # Edges removed (in existing but not in incoming)
                    for target in existing_targets - incoming_targets:
                        conflicts.append(Conflict(
                            node_name=name,
                            field=f'edge:{edge_type}',
                            current_value=target,
                            incoming_value='',
                            conflict_type='edge_removed'
                        ))

            else:
                # Node only in incoming: auto-add (not a conflict per se,
                # but tracked for completeness)
                conflicts.append(Conflict(
                    node_name=name,
                    field='node',
                    current_value='',
                    incoming_value=f'{getattr(incoming_node, "node_type", "US")}: {incoming_node.description or ""}',
                    conflict_type='node_added',
                    resolved=True,
                    accepted=True
                ))

        # Sort by node name for predictable navigation
        conflicts.sort(key=lambda c: (c.node_name, c.field))

        return conflicts

    def apply_resolutions(self, graph: Graph, conflicts: List[Conflict],
                           incoming: Graph = None):
        """
        Apply resolved conflicts to the graph.

        For each conflict that has been resolved:
        - If accepted: update the graph with the incoming value
        - If rejected: keep the existing value (no action needed)

        Args:
            graph: The graph to update (the existing/current graph)
            conflicts: List of conflicts with resolution decisions
            incoming: The incoming graph (needed for adding new nodes/edges)
        """
        incoming_by_name = self._build_node_name_map(incoming) if incoming else {}
        graph_by_name = self._build_node_name_map(graph)

        for conflict in conflicts:
            if not conflict.resolved:
                continue

            if not conflict.accepted:
                continue  # User chose to keep current value

            node_name = conflict.node_name

            if conflict.conflict_type == 'value_changed':
                node = graph_by_name.get(node_name)
                if node and conflict.field == 'description':
                    node.description = conflict.incoming_value

            elif conflict.conflict_type == 'edge_added':
                source_node = graph_by_name.get(node_name)
                target_name = conflict.incoming_value
                target_node = graph_by_name.get(target_name)
                edge_type = conflict.field.replace('edge:', '')

                if source_node and target_node:
                    import uuid
                    try:
                        graph.add_edge(
                            edge_id=str(uuid.uuid4()),
                            edge_source=source_node.node_id,
                            edge_target=target_node.node_id,
                            edge_type=edge_type
                        )
                    except ValueError:
                        pass  # Edge already exists or validation failed

            elif conflict.conflict_type == 'edge_removed':
                source_node = graph_by_name.get(node_name)
                target_name = conflict.current_value
                target_node = graph_by_name.get(target_name)
                edge_type = conflict.field.replace('edge:', '')

                if source_node and target_node:
                    # Find and remove the edge
                    edge_to_remove = None
                    for edge in graph.edges:
                        if (edge.edge_source == source_node.node_id
                                and edge.edge_target == target_node.node_id
                                and edge.edge_type == edge_type):
                            edge_to_remove = edge
                            break
                    if edge_to_remove:
                        graph.remove_edge(edge_to_remove.edge_id)

            elif conflict.conflict_type == 'node_added' and incoming:
                incoming_node = incoming_by_name.get(node_name)
                if incoming_node:
                    # Add the new node to the graph
                    graph.add_node(incoming_node)

                    # Also add any edges from incoming that involve this node
                    for edge in incoming.edges:
                        if edge.edge_source == incoming_node.node_id or \
                           edge.edge_target == incoming_node.node_id:
                            # Check if both endpoints exist in the graph
                            src = graph.find_node_by_id(edge.edge_source)
                            tgt = graph.find_node_by_id(edge.edge_target)
                            if src and tgt:
                                try:
                                    graph.add_edge(
                                        edge_id=edge.edge_id,
                                        edge_source=edge.edge_source,
                                        edge_target=edge.edge_target,
                                        edge_type=edge.edge_type
                                    )
                                except ValueError:
                                    pass

        print(f"[GraphMerger] Applied {sum(1 for c in conflicts if c.resolved and c.accepted)} accepted changes")

    def get_unresolved_conflicts(self, conflicts: List[Conflict]) -> List[Conflict]:
        """Get only conflicts that need user resolution (excluding auto-accepted)."""
        return [c for c in conflicts if not c.resolved]

    def get_statistics(self, conflicts: List[Conflict]) -> Dict:
        """Get summary statistics about conflicts."""
        total = len(conflicts)
        resolved = sum(1 for c in conflicts if c.resolved)
        accepted = sum(1 for c in conflicts if c.resolved and c.accepted)
        rejected = sum(1 for c in conflicts if c.resolved and not c.accepted)
        unresolved = total - resolved

        by_type = {}
        for c in conflicts:
            by_type[c.conflict_type] = by_type.get(c.conflict_type, 0) + 1

        return {
            'total': total,
            'resolved': resolved,
            'accepted': accepted,
            'rejected': rejected,
            'unresolved': unresolved,
            'by_type': by_type
        }

    def _build_node_name_map(self, graph: Graph) -> Dict[str, StratigraphicNode]:
        """Build a name -> node mapping for stratigraphic nodes."""
        result = {}
        for node in graph.nodes:
            if isinstance(node, StratigraphicNode) and hasattr(node, 'name'):
                result[node.name] = node
        return result

    def _build_edge_map(self, graph: Graph) -> Dict[str, Dict[str, Set[str]]]:
        """
        Build edge map: {source_name: {edge_type: set(target_names)}}.

        Only includes stratigraphic edge types.
        """
        # First build node_id -> name mapping
        id_to_name = {}
        for node in graph.nodes:
            if isinstance(node, StratigraphicNode) and hasattr(node, 'name'):
                id_to_name[node.node_id] = node.name

        result: Dict[str, Dict[str, Set[str]]] = {}
        for edge in graph.edges:
            if edge.edge_type not in STRATIGRAPHIC_EDGE_TYPES:
                continue

            source_name = id_to_name.get(edge.edge_source)
            target_name = id_to_name.get(edge.edge_target)

            if source_name and target_name:
                if source_name not in result:
                    result[source_name] = {}
                if edge.edge_type not in result[source_name]:
                    result[source_name][edge.edge_type] = set()
                result[source_name][edge.edge_type].add(target_name)

        return result
