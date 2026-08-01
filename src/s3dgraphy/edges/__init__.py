# s3Dgraphy/edges/__init__.py

"""
Initialization for the s3Dgraphy edges module.

This module contains classes and definitions related to edges,
which define the relationships and connections between nodes in the s3Dgraphy graphs.
"""

from .edge import Edge, EDGE_TYPES
from .connections_loader import (
    ConnectionsDatamodel,
    get_connections_datamodel,
    reload_connections_datamodel
)
from .connection_resolver import (
    GENERIC_CONNECTION,
    allowed_endpoints,
    candidate_edge_types,
    connection_allowed,
    connection_report,
    diagnose_generic,
    endpoint_matches,
    format_connection_report,
    resolve_edge_type,
    resolve_node_class,
)

# Define what is available for import when using 'from edges import *'
__all__ = [
    "Edge",
    "EDGE_TYPES",
    "ConnectionsDatamodel",
    "get_connections_datamodel",
    "reload_connections_datamodel",
    # correct connection resolution — REPORT-ONLY, changes no behaviour
    "GENERIC_CONNECTION",
    "resolve_node_class",
    "endpoint_matches",
    "allowed_endpoints",
    "connection_allowed",
    "resolve_edge_type",
    "connection_report",
    "candidate_edge_types",
    "diagnose_generic",
    "format_connection_report",
]
