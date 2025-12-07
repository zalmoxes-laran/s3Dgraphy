# Import the connections datamodel loader
from .connections_loader import get_connections_datamodel

# Get the global datamodel instance
_connections_datamodel = get_connections_datamodel()

# Legacy EDGE_TYPES dictionary for backward compatibility
# This is now dynamically generated from the connections datamodel
def _build_legacy_edge_types():
    """Build a legacy EDGE_TYPES dict for backward compatibility."""
    edge_types = {}
    for edge_name in _connections_datamodel.get_all_edge_names(canonical_only=False):
        edge_types[edge_name] = {
            "label": _connections_datamodel.get_label(edge_name),
            "description": _connections_datamodel.get_description(edge_name)
        }
    return edge_types

EDGE_TYPES = _build_legacy_edge_types()

class Edge:
    """
    Represents an edge in the graph, connecting two nodes with a specific relationship type.
    
    Attributes:
        edge_id (str): Unique identifier for the edge.
        edge_source (str): ID of the source node.
        edge_target (str): ID of the target node.
        edge_type (str): Semantic type of the relationship.
        label (str): A descriptive label for the relationship type.
        description (str): A detailed description of the relationship type.
    """

    def __init__(self, edge_id, edge_source, edge_target, edge_type):
        if edge_type not in EDGE_TYPES:
            raise ValueError(f"Edge type '{edge_type}' is not a recognized relationship type.")
        
        self.edge_id = edge_id
        self.edge_source = edge_source
        self.edge_target = edge_target
        self.edge_type = edge_type
        self.label = EDGE_TYPES[edge_type]["label"]
        self.description = EDGE_TYPES[edge_type]["description"]

        self.attributes = {}


    def to_dict(self):
        """
        Converts the Edge instance to a dictionary format.

        Returns:
            dict: A dictionary representation of the edge, including its attributes.
        """
        return {
            "edge_id": self.edge_id,
            "source": self.edge_source,
            "target": self.edge_target,
            "type": self.edge_type,
            "label": self.label,
            "description": self.description
        }

    def __repr__(self):
        """
        Returns a string representation of the Edge instance.

        Returns:
            str: A string representation of the edge, showing its source, target, and type.
        """
        return f"Edge({self.edge_id}, {self.edge_source} -> {self.edge_target}, {self.edge_type})"

    def is_symmetric(self):
        """Check if this edge is symmetric (bidirectional)."""
        return _connections_datamodel.is_symmetric(self.edge_type)

    def is_canonical(self):
        """Check if this edge uses the canonical direction."""
        return _connections_datamodel.is_canonical(self.edge_type)

    def get_reverse_name(self):
        """Get the reverse edge name if this edge has directionality."""
        return _connections_datamodel.get_reverse_name(self.edge_type)

    @staticmethod
    def get_datamodel():
        """Get the global connections datamodel instance."""
        return _connections_datamodel
