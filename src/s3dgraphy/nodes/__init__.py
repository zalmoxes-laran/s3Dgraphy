# s3Dgraphy/nodes/__init__.py

"""
Initialization for the s3Dgraphy nodes module.

This module provides classes for various node types, which are essential components 
of the s3Dgraphy graph structure, including stratigraphic, document, activity, 
property nodes, and more.
"""

from .base_node import Node
from .stratigraphic_node import (
    StratigraphicNode, WorkingUnit,
    StratigraphicUnit, NegativeStratigraphicUnit,
    TransformationStratigraphicUnit,
    StructuralVirtualStratigraphicUnit, NonStructuralVirtualStratigraphicUnit,
    SpecialFindUnit, VirtualSpecialFindUnit, ReusedSpecialFind,
    DocumentaryStratigraphicUnit,
    SeriesOfStratigraphicUnit, SeriesOfDocumentaryStratigraphicUnit,
    SeriesOfStructuralVirtualStratigraphicUnit,
    SeriesOfNonStructuralVirtualStratigraphicUnit,
    ContinuityNode, StratigraphicEventNode, UnknownNode,
)
from .epoch_node import EpochNode
from .property_node import PropertyNode
from .document_node import DocumentNode
from .combiner_node import CombinerNode
from .extractor_node import ExtractorNode
from .group_node import (
    GroupNode,
    ActivityNodeGroup,
    ParadataNodeGroup,
    TimeBranchNodeGroup,
    LocationNodeGroup,
)
from .paradata_node import ParadataNode
from .geo_position_node import GeoPositionNode
from .representation_node import (RepresentationModelNode,
                                  RepresentationModelDocNode,
                                  RepresentationModelSpecialFindNode)
from .author_node import AuthorNode, AuthorAINode
from .link_node import LinkNode
from .embargo_node import EmbargoNode
from .license_node import LicenseNode
from .graph_node import GraphNode
from .hdt_node import HDTNode
from .heritage_entity_node import HeritageEntityNode
from .study_node import StudyNode
from .project_node import ProjectNode
from .semantic_shape_node import SemanticShapeNode
# DTC substrate profile (ECHOES). Two event classes: DTCProcessNode (genesis /
# transformation, crmdig:D7) and DTCAcquisitionNode (acquisition / ingestion,
# crmdig:D12 ⊂ D7). Both the INPUT and the OUTPUT are Resources (LinkNode, E73/D1)
# — see dtc_had_input / dtc_had_output (target LinkNode). DTCInputNode/
# DTCOutputNode were retired.
from .dtc_node import DTCNode
from .dtc_process_node import DTCProcessNode
from .dtc_acquisition_node import DTCAcquisitionNode

# Define what is available for import when using 'from nodes import *'
__all__ = [
    "Node",
    "StratigraphicNode",
    "WorkingUnit",
    "StratigraphicUnit",
    "NegativeStratigraphicUnit",
    "TransformationStratigraphicUnit",
    "StructuralVirtualStratigraphicUnit",
    "NonStructuralVirtualStratigraphicUnit",
    "SpecialFindUnit",
    "VirtualSpecialFindUnit",
    "ReusedSpecialFind",
    "DocumentaryStratigraphicUnit",
    "SeriesOfStratigraphicUnit",
    "SeriesOfDocumentaryStratigraphicUnit",
    "SeriesOfStructuralVirtualStratigraphicUnit",
    "SeriesOfNonStructuralVirtualStratigraphicUnit",
    "ContinuityNode",
    "StratigraphicEventNode",
    "UnknownNode",
    "EpochNode",
    "PropertyNode",
    "DocumentNode",
    "CombinerNode",
    "ExtractorNode",
    "GroupNode",
    "ActivityNodeGroup",
    "ParadataNodeGroup",
    "TimeBranchNodeGroup",
    "LocationNodeGroup",
    "ParadataNode",
    "GeoPositionNode",
    "RepresentationModelNode",
    "RepresentationModelDocNode",
    "RepresentationModelSpecialFindNode",
    "AuthorNode",
    "AuthorAINode",
    "LinkNode",
    "EmbargoNode",
    "LicenseNode",
    "GraphNode",
    "HDTNode",
    "HeritageEntityNode",
    "StudyNode",
    "ProjectNode",
    "SemanticShapeNode",
    "DTCNode",
    "DTCProcessNode",
    "DTCAcquisitionNode",
]
