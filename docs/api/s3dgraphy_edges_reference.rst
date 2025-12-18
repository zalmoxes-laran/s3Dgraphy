s3dgraphy Edges Reference
=============================

This document provides comprehensive documentation for all edge types in s3dgraphy, including their semantic meanings, CIDOC-CRM mappings, and usage patterns.

Overview
--------

Edges in s3dgraphy represent relationships between nodes in the archaeological knowledge graph. Each edge type has specific semantic meaning and follows archaeological documentation standards.

Edge Types Classification
--------------------------

Temporal Relationships
~~~~~~~~~~~~~~~~~~~~~~

**is_before**
^^^^^^^^^^^^^

:Label: Chronological Sequence
:Description: Indicates a temporal sequence where one item occurs before another
:CIDOC-CRM: P120_occurs_before
:Visual Style: Solid line
:Usage: Primary stratigraphic relationships

.. code-block:: python

   # Stratigraphic sequence: US003 is earlier than US002
   graph.add_edge("rel001", "US003", "US002", "is_before")

**Allowed Connections:**
   - StratigraphicNode → StratigraphicNode
   - StratigraphicEventNode → StratigraphicEventNode
   - EpochNode → EpochNode

**has_same_time**
^^^^^^^^^^^^^^^^^

:Label: Contemporaneous Elements
:Description: Indicates that two elements are contemporaneous
:CIDOC-CRM: P114_is_equal_in_time_to
:Visual Style: Double line
:Usage: Contemporary archaeological features

.. code-block:: python

   # Contemporary features: wall and floor built at same time
   graph.add_edge("rel002", "US001_wall", "US002_floor", "has_same_time")

**Allowed Connections:**
   - StratigraphicNode → StratigraphicNode
   - SpecialFindUnit → SpecialFindUnit

**changed_from**
^^^^^^^^^^^^^^^^

:Label: Temporal Transformation
:Description: Represents an object that changes over time
:CIDOC-CRM: P123_resulted_from
:Visual Style: Dotted line
:Usage: Transformation processes, reconstruction phases

.. code-block:: python

   # Building transformation: medieval wall reuses Roman foundation
   graph.add_edge("trans001", "US005_medieval_wall", "US010_roman_foundation", "changed_from")

**Allowed Connections:**
   - StratigraphicNode → StratigraphicNode
   - TransformationStratigraphicUnit → StratigraphicNode

Documentation Relationships
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**has_data_provenance**
^^^^^^^^^^^^^^^^^^^^^^^

:Label: Data Provenance
:Description: Indicates the provenance of data, often linking to source nodes
:CIDOC-CRM: P70i_is_documented_in
:Visual Style: Dashed line
:Usage: Links interpretations to their sources

.. code-block:: python

   # Property supported by documentation
   graph.add_edge("prov001", "PROP001_material", "DOC001_analysis", "has_data_provenance")

**Allowed Connections:**
   - PropertyNode → DocumentNode
   - PropertyNode → ExtractorNode
   - CombinerNode → ExtractorNode

**extracted_from**
^^^^^^^^^^^^^^^^^^

:Label: Extracted From
:Description: Indicates that information is derived from a particular source
:CIDOC-CRM: P67_refers_to
:Visual Style: Dashed line
:Usage: Information extraction processes

.. code-block:: python

   # Information extracted from document
   graph.add_edge("ext001", "EXT001_typology", "DOC005_corpus", "extracted_from")

**Allowed Connections:**
   - ExtractorNode → DocumentNode
   - PropertyNode → DocumentNode
   - SpecialFindUnit → StratigraphicNode (findspot)

**combines**
^^^^^^^^^^^^

:Label: Combines
:Description: Indicates that a node combines information from various sources
:CIDOC-CRM: P16_used_specific_object
:Visual Style: Dashed line
:Usage: Information synthesis processes

.. code-block:: python

   # Combiner synthesizes multiple sources
   graph.add_edge("comb001", "COMB001_synthesis", "EXT001_dating", "combines")
   graph.add_edge("comb002", "COMB001_synthesis", "EXT002_material", "combines")

**Allowed Connections:**
   - CombinerNode → ExtractorNode
   - CombinerNode → PropertyNode

Property and Attribution Relationships
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**has_property**
^^^^^^^^^^^^^^^^

:Label: Has Property
:Description: Connects a node to one of its properties
:CIDOC-CRM: P2_has_type
:Visual Style: Solid line
:Usage: Attribute assignment

.. code-block:: python

   # Stratigraphic unit has material property
   graph.add_edge("prop001", "US001", "PROP001_material_stone", "has_property")

**Allowed Connections:**
   - StratigraphicNode → PropertyNode
   - SpecialFindUnit → PropertyNode
   - Any Node → PropertyNode

**contrasts_with**
^^^^^^^^^^^^^^^^^^

:Label: Contrasting Properties
:Description: Represents contrasting or mutually exclusive properties
:CIDOC-CRM: P69_has_association_with
:Visual Style: Dashed-dotted line
:Usage: Alternative interpretations, conflicting evidence

.. code-block:: python

   # Alternative dating interpretations
   graph.add_edge("contrast001", "PROP001_dating_early", "PROP002_dating_late", "contrasts_with")

**Allowed Connections:**
   - PropertyNode → PropertyNode
   - ExtractorNode → ExtractorNode
   - CombinerNode → CombinerNode

Temporal and Epochal Relationships
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**has_first_epoch**
^^^^^^^^^^^^^^^^^^^

:Label: Has First Epoch
:Description: Indicates the initial epoch associated with a node
:CIDOC-CRM: P82a_begin_of_the_begin
:Visual Style: Solid line
:Usage: Temporal assignment to periods

.. code-block:: python

   # Unit belongs to Roman period
   graph.add_edge("epoch001", "US001", "EPOCH_ROMAN", "has_first_epoch")

**Allowed Connections:**
   - StratigraphicNode → EpochNode
   - SpecialFindUnit → EpochNode

**survive_in_epoch**
^^^^^^^^^^^^^^^^^^^^

:Label: Survives In Epoch
:Description: Indicates that a node continues to exist in a given epoch
:CIDOC-CRM: P10_falls_within
:Visual Style: Solid line
:Usage: Long-duration features

.. code-block:: python

   # Wall continues through multiple periods
   graph.add_edge("surv001", "US001_wall", "EPOCH_MEDIEVAL", "survive_in_epoch")

**Allowed Connections:**
   - StratigraphicNode → EpochNode
   - ContinuityNode → EpochNode

Organizational Relationships
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**is_in_activity**
^^^^^^^^^^^^^^^^^^

:Label: Part of Activity
:Description: Indicates that a node is part of a specific activity
:CIDOC-CRM: P9_consists_of
:Visual Style: Solid line
:Usage: Activity-based grouping

.. code-block:: python

   # Units part of construction activity
   graph.add_edge("act001", "US001", "ACT001_construction", "is_in_activity")

**Allowed Connections:**
   - Any Node → ActivityNodeGroup

**has_timebranch** / **is_in_timebranch**
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Label: Connected to a Timebranch / Included in Timebranch
:Description: Indicates connection to alternative temporal interpretations
:CIDOC-CRM: P67_refers_to
:Visual Style: Solid line
:Usage: Alternative chronological hypotheses

.. code-block:: python

   # Alternative interpretation branch
   graph.add_edge("branch001", "US001", "BRANCH001_early_dating", "has_timebranch")

**Allowed Connections:**
   - Any Node → TimeBranchNodeGroup

**is_in_paradata_nodegroup** / **has_paradata_nodegroup**
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Label: Belongs to Paradata Group / Has Paradata Group
:Description: Organizational relationships for paradata management
:CIDOC-CRM: P106_is_composed_of
:Visual Style: Solid line
:Usage: Documentation organization

.. code-block:: python

   # Group paradata by excavation area
   graph.add_edge("para001", "DOC001", "PARAGROUP_AREA_A", "is_in_paradata_nodegroup")

**Allowed Connections:**
   - DocumentNode → ParadataNodeGroup
   - ExtractorNode → ParadataNodeGroup  
   - CombinerNode → ParadataNodeGroup
   - ParadataNodeGroup → ActivityNodeGroup

Specialized Relationships
~~~~~~~~~~~~~~~~~~~~~~~~~

**has_linked_resource**
^^^^^^^^^^^^^^^^^^^^^^^

:Label: Has Link
:Description: Connects a node to its linked resource(s)
:CIDOC-CRM: P67_refers_to
:Visual Style: Solid line
:Usage: External resource links

.. code-block:: python

   # Link to external resource
   graph.add_edge("link001", "US001", "LINK001_3d_model", "has_linked_resource")

**Allowed Connections:**
   - Any Node → LinkNode

**has_semantic_shape**
^^^^^^^^^^^^^^^^^^^^^^

:Label: Has Semantic Shape
:Description: Connects any node to its semantic shape representation in 3D space
:CIDOC-CRM: E36_Visual_Item
:Visual Style: Solid line
:Usage: 3D visualization links

.. code-block:: python

   # Link to 3D semantic representation
   graph.add_edge("shape001", "US001", "SHAPE001_wall_3d", "has_semantic_shape")

**Allowed Connections:**
   - Any Node → SemanticShapeNode

**has_representation_model**
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:Label: Has Representation Model
:Description: Connects any node to its representation model in 3D space
:CIDOC-CRM: E36_Visual_Item
:Visual Style: Solid line
:Usage: 3D model connections

.. code-block:: python

   # Link to 3D representation model
   graph.add_edge("model001", "US001", "MODEL001_wall", "has_representation_model")

**Allowed Connections:**
   - Any Node → RepresentationModelNode

Licensing and Legal Relationships
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**has_license**
^^^^^^^^^^^^^^^

:Label: Has License
:Description: Indicates that a resource is subject to a specific licence
:CIDOC-CRM: P104_is_subject_to
:Visual Style: Solid line
:Usage: Legal and copyright information

.. code-block:: python

   # Document has specific license
   graph.add_edge("lic001", "DOC001", "LICENSE_CC_BY", "has_license")

**has_embargo**
^^^^^^^^^^^^^^^

:Label: Has Embargo
:Description: Indicates that a licence has an associated time embargo
:CIDOC-CRM: P4_has_time-span
:Visual Style: Solid line
:Usage: Temporal access restrictions

.. code-block:: python

   # License has embargo period
   graph.add_edge("emb001", "LICENSE_CC_BY", "EMBARGO_2025", "has_embargo")

Generic Relationships
~~~~~~~~~~~~~~~~~~~~~

**generic_connection**
^^^^^^^^^^^^^^^^^^^^^^

:Label: Generic Connection
:Description: Represents a non-specific connection between two nodes
:CIDOC-CRM: P67_refers_to
:Visual Style: Solid line
:Usage: Placeholder for unspecified relationships

.. code-block:: python

   # Generic connection (should be enhanced to specific type)
   graph.add_edge("gen001", "NODE001", "NODE002", "generic_connection")

**Note:** Generic connections are often enhanced to more specific types during import processing.

Connection Validation Rules
---------------------------

Node Type Compatibility Matrix
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

s3dgraphy enforces strict validation rules for edge connections based on archaeological logic:

.. code-block:: python

   # Validation example
   source_node = graph.find_node_by_id("US001")
   target_node = graph.find_node_by_id("DOC001")
   
   if Graph.validate_connection(source_node.node_type, target_node.node_type, "has_data_provenance"):
       graph.add_edge("valid_edge", "US001", "DOC001", "has_data_provenance")
   else:
       print("Invalid connection type")

**Common Valid Patterns:**

Stratigraphic Relationships
^^^^^^^^^^^^^^^^^^^^^^^^^^^
   - US → US (is_before, has_same_time)
   - US → SF (extracted_from - findspot)
   - US → EpochNode (has_first_epoch, survive_in_epoch)

Documentation Chains
^^^^^^^^^^^^^^^^^^^^
   - DocumentNode → ExtractorNode (extracted_from)
   - ExtractorNode → CombinerNode (combines)
   - PropertyNode → DocumentNode (has_data_provenance)
   - US/SF → PropertyNode (has_property)

Organizational Structures
^^^^^^^^^^^^^^^^^^^^^^^^^
   - Any Node → ActivityNodeGroup (is_in_activity)
   - ParadataNode → ParadataNodeGroup (is_in_paradata_nodegroup)
   - Any Node → TimeBranchNodeGroup (has_timebranch)

Best Practices for Edge Usage
-----------------------------

Temporal Relationships
~~~~~~~~~~~~~~~~~~~~~~

1. **Use consistent direction**: Later units point to earlier units with "is_after" (canonical direction from recent to ancient)
2. **Document contemporaneity**: Use "has_same_time" for features built together
3. **Model transformations**: Use "changed_from" for reuse and modification

.. code-block:: python

   # Good: Consistent temporal direction (canonical "is_after")
   graph.add_edge("temp1", "US002_wall", "US003_foundation", "is_after")  # wall is more recent than foundation
   graph.add_edge("temp2", "US001_roof", "US002_wall", "is_after")  # roof is more recent than wall
   
   # Good: Contemporary features
   graph.add_edge("cont1", "US002_wall", "US004_floor", "has_same_time")

Documentation Chains
~~~~~~~~~~~~~~~~~~~~

1. **Complete paradata chains**: Link properties through extractors to documents
2. **Use specific edge types**: Avoid generic_connection when possible
3. **Document conflicting interpretations**: Use contrasts_with for alternatives

.. code-block:: python

   # Complete documentation chain
   graph.add_edge("prop1", "US001", "PROP001_material", "has_property")
   graph.add_edge("ext1", "EXT001_analysis", "DOC001_lab_report", "extracted_from") 
   graph.add_edge("prov1", "PROP001_material", "EXT001_analysis", "has_data_provenance")

Organizational Structure
~~~~~~~~~~~~~~~~~~~~~~~

1. **Group related elements**: Use node groups for logical organization
2. **Separate activity phases**: Use activity groups for excavation phases
3. **Model alternative interpretations**: Use time branches for competing hypotheses

.. code-block:: python

   # Organizational grouping
   graph.add_edge("org1", "US001", "ACT001_phase1", "is_in_activity")
   graph.add_edge("org2", "DOC001", "PARA001_area_a", "is_in_paradata_nodegroup")

Error Handling and Validation
-----------------------------

Common Edge Validation Errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Invalid Node Types**
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # This will fail validation
   try:
       graph.add_edge("invalid", "US001", "US002", "has_license")
   except ValueError as e:
       print(f"Invalid connection: {e}")
       # US nodes cannot have license relationships

**Missing Nodes**
^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Check nodes exist before creating edges
   if (graph.find_node_by_id("US001") and 
       graph.find_node_by_id("US002")):
       graph.add_edge("rel1", "US001", "US002", "is_before")
   else:
       graph.add_warning("Cannot create edge: missing nodes")

**Circular Dependencies**
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Detect circular temporal relationships
   def check_temporal_cycles(graph):
       temporal_edges = [e for e in graph.edges if e.edge_type == "is_before"]
       # Implementation of cycle detection algorithm
       return has_cycles

Edge Enhancement During Import
------------------------------

GraphML Import Processing
~~~~~~~~~~~~~~~~~~~~~~~~~

The GraphMLImporter automatically enhances edge types based on connected node types:

.. code-block:: python

   def enhance_edge_type(self, source_node, target_node, edge_type):
       """Enhance generic connections to specific types"""
       
       if edge_type == "generic_connection":
           # DocumentNode → ExtractorNode becomes "extracted_from"
           if (source_node.node_type == "document" and 
               target_node.node_type == "extractor"):
               return "extracted_from"
           
           # ExtractorNode → CombinerNode becomes "combines"  
           elif (source_node.node_type == "extractor" and
                 target_node.node_type == "combiner"):
               return "combines"
       
       return edge_type

Export Considerations
--------------------

GraphML Export
~~~~~~~~~~~~~~

Edge types are preserved with their semantic meaning and visual styling:

.. code-block:: python

   # Export preserves edge semantics
   exporter = GraphMLExporter()
   exporter.export_graph(graph, "output.graphml", 
                        preserve_edge_styles=True)

JSON Export
~~~~~~~~~~~

Edges include full metadata and CIDOC-CRM mappings:

.. code-block:: python

   # JSON export includes semantic information
   {
       "edge_id": "rel001",
       "source": "US001", 
       "target": "US002",
       "edge_type": "is_before",
       "label": "Chronological Sequence",
       "description": "Indicates a temporal sequence where one item occurs before another",
       "cidoc_mapping": "P120_occurs_before",
       "visual_style": "solid_line"
   }

This comprehensive edge reference provides the foundation for creating semantically rich archaeological graphs in s3dgraphy.
