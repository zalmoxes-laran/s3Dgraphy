"""
Utility functions and classes for GraphML export.

This module provides ID management for nested node structures and helper functions
for coordinate calculation.
"""

import uuid
from typing import Dict, Optional, Tuple


class IDManager:
    """
    Manages mapping between UUIDs and nested GraphML IDs.

    yEd uses nested ID format (n0::n1::n2) for hierarchical node structures.
    This class maintains bidirectional mapping between original UUIDs and nested IDs.
    """

    def __init__(self):
        """Initialize ID manager with empty mappings."""
        self.uuid_to_nested: Dict[str, str] = {}  # {uuid: nested_id}
        self.nested_to_uuid: Dict[str, str] = {}  # {nested_id: uuid}
        self.nested_counter: int = 0
        self.group_counters: Dict[str, int] = {}  # {parent_id: counter}
        self.edge_counter: int = 0

    def get_nested_id(self, node_uuid: str, parent_id: Optional[str] = None) -> str:
        """
        Get or create nested ID for a node UUID.

        Args:
            node_uuid: Original UUID of the node
            parent_id: Nested ID of parent node (None for top-level nodes)

        Returns:
            Nested ID in format: n0, n0::n1, n0::n1::n0, etc.
        """
        # Return existing mapping if available
        if node_uuid in self.uuid_to_nested:
            return self.uuid_to_nested[node_uuid]

        # Generate new nested ID
        if parent_id:
            # Nested node inside a group
            if parent_id not in self.group_counters:
                self.group_counters[parent_id] = 0
            nested_id = f"{parent_id}::n{self.group_counters[parent_id]}"
            self.group_counters[parent_id] += 1
        else:
            # Top-level node
            nested_id = f"n{self.nested_counter}"
            self.nested_counter += 1

        # Store bidirectional mapping
        self.uuid_to_nested[node_uuid] = nested_id
        self.nested_to_uuid[nested_id] = node_uuid

        return nested_id

    def get_uuid(self, nested_id: str) -> Optional[str]:
        """
        Get original UUID for a nested ID.

        Args:
            nested_id: Nested ID (e.g., "n0::n1")

        Returns:
            Original UUID or None if not found
        """
        return self.nested_to_uuid.get(nested_id)

    def get_edge_id(self, prefix: str = None) -> str:
        """
        Generate unique edge ID.

        Args:
            prefix: Optional prefix for nested edges (e.g., "n0" → "n0::e0")

        Returns:
            Edge ID in format: e0, e1, e2, etc. (or n0::e0, n0::e1 with prefix)
        """
        if prefix:
            edge_id = f"{prefix}::e{self.edge_counter}"
        else:
            edge_id = f"e{self.edge_counter}"
        self.edge_counter += 1
        return edge_id

    def reset(self):
        """Reset all counters and mappings."""
        self.uuid_to_nested.clear()
        self.nested_to_uuid.clear()
        self.nested_counter = 0
        self.group_counters.clear()
        self.edge_counter = 0


def qname(namespace: str, tag: str) -> str:
    """
    Create a qualified XML name with namespace.

    Args:
        namespace: XML namespace URI
        tag: Element tag name

    Returns:
        Qualified name in format: {namespace}tag
    """
    return f"{{{namespace}}}{tag}"


def generate_uuid() -> str:
    """
    Generate UUID for EMID fields.

    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def calculate_node_width(label: str, base_width: float = 90.0, char_width: float = 7.0) -> float:
    """
    Calculate node width based on label length.

    Args:
        label: Node label text
        base_width: Minimum node width
        char_width: Approximate width per character

    Returns:
        Calculated width
    """
    label_width = len(label) * char_width + 20  # +20 for padding
    return max(base_width, label_width)


def parse_relation_string(rel_str: Optional[str]) -> list:
    """
    Parse comma-separated relation string.

    Args:
        rel_str: String like "USM01,USM02,USM03" or None

    Returns:
        List of relation IDs, empty if None or empty string
    """
    if not rel_str or not rel_str.strip():
        return []
    return [s.strip() for s in rel_str.split(',') if s.strip()]
