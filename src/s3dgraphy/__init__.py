__version__ = "0.1.12"

# s3Dgraphy/__init__.py

"""
Main initialization for the s3Dgraphy library.

s3Dgraphy is a Python library for creating and managing multitemporal, 3D knowledge graphs.
It includes functionality for graph creation, stratigraphic data management, edge definitions, 
node types, visual layout generation, and graph import/export operations.

Author: Emanuel Demetrescu, 2024
License: GNU-GPL 3.0
"""

# Importing the main classes and functions from each sub-module

# Graph-related imports
from .graph import Graph

# Node imports
from .nodes.base_node import Node
#from .nodes import (
#    Node, StratigraphicNode, GroupNode, ActivityNodeGroup,
#    ParadataNodeGroup, ParadataNode, DocumentNode, CombinerNode,
#    ExtractorNode, PropertyNode, EpochNode, GeoPositionNode, RepresentationModelNode, AuthorNode, LinkNode
#)

# Edge-related imports
from .edges import Edge

# MultiGraph Manager imports
from .multigraph import MultiGraphManager, load_graph_from_file, get_graph, get_all_graph_ids, remove_graph

# Importer for GraphML
from .importer import GraphMLImporter

# Utility imports
from .utils import convert_shape2type, manage_id_prefix, get_base_name, add_graph_prefix

from .indices import GraphIndices

# Mapping system imports (aggiungi questa riga)
from .mappings import mapping_registry, add_custom_mapping_directory, get_available_mappings, load_mapping_file

# Visual layout (optional import of networkx is handled in visual_layout)
#from .visual_layout import generate_layout

# Defining what is available for import when using 'from s3Dgraphy import *'
__all__ = [
    "Graph",
    "Node", 
    "StratigraphicNode", 
    "GroupNode", 
    "ActivityNodeGroup",
    "ParadataNodeGroup",
    "TimeBranchNodeGroup", 
    "ParadataNode", 
    "DocumentNode", 
    "CombinerNode",
    "ExtractorNode", 
    "PropertyNode", 
    "EpochNode", 
    "GeoPositionNode",
    "RepresentationModelNode", 
    "AuthorNode", 
    "LinkNode",
    "Edge",
    "MultiGraphManager", 
    "load_graph_from_file", 
    "get_graph", 
    "get_all_graph_ids",
    "remove_graph",
    "GraphMLImporter",
    "convert_shape2type",
    "GraphIndices",
    "mapping_registry",
    "add_custom_mapping_directory", 
    "get_available_mappings",
    "load_mapping_file",
    "manage_id_prefix",
    "get_base_name",
    "add_graph_prefix"
]
