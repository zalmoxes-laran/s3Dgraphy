Core Concepts
=============

This section introduces the fundamental concepts and architecture of s3dgraphy, 
the core Python library implementing the Extended Matrix formal language.

Graph Structure
---------------

s3dgraphy implements a **property graph model** specifically designed for archaeological 
stratigraphic documentation. Each graph represents an archaeological site or project 
and contains:

**Nodes (Vertices)**
   Represent archaeological entities such as stratigraphic units, documents, 
   interpretations, and metadata

**Edges (Relationships)**  
   Represent relationships between entities, including temporal sequences, 
   documentation links, and analytical connections

**Properties**
   Both nodes and edges can carry attributes and metadata specific to 
   archaeological documentation needs

Multigraph Architecture
-----------------------

s3dgraphy supports **multiple graphs** within a single project through the 
MultiGraphManager system:

.. code-block:: python

   from s3dgraphy import MultiGraphManager
   
   # Access the global manager
   manager = MultiGraphManager()
   
   # Create multiple site graphs
   site_a = manager.create_graph("SiteA_2024")
   site_b = manager.create_graph("SiteB_2024") 
   
   # Each graph is independent but can reference others
   print(f"Active graphs: {manager.get_all_graph_ids()}")

This allows for:

- **Multi-site projects** with separate but related documentation
- **Temporal phases** of the same site across different excavation seasons
- **Alternative hypotheses** represented as separate graph variants
- **Data organization** by research team or institutional affiliation

Node Type Hierarchy
--------------------

s3dgraphy implements a specialized node type system for archaeological documentation:

Core Node Types
~~~~~~~~~~~~~~~

**StratigraphicNode** - Base class for all archaeological units
   - ``US`` - Physical stratigraphic units (walls, floors, fills)
   - ``USV`` - Virtual reconstruction units (``USVs`` structural, ``USVn`` non-structural)
   - ``SF`` - Special finds (artifacts, samples)
   - ``VSF`` - Virtual special finds (reconstructed artifacts)
   - ``USD`` - Documentary units (based on historical sources)

**ParadataNode** - Documentation and analytical metadata
   - ``DocumentNode`` - Source materials (photos, drawings, reports)
   - ``ExtractorNode`` - Analytical processes and interpretations
   - ``AuthorNode`` - Persons responsible for documentation
   - ``ActivityNode`` - Methodological activities and processes

**RepresentationNode** - 3D and visual representations
   - ``RepresentationModelNode`` - 3D models for stratigraphic units
   - ``RepresentationModelDocNode`` - 3D models for documents
   - ``RepresentationModelSpecialFindNode`` - 3D models for special finds
   - ``SemanticShapeNode`` - Semantic annotations in 3D space

**AuxiliaryNode** - Supporting metadata
   - ``EpochNode`` - Temporal periods and chronological frameworks
   - ``GeoPositionNode`` - Spatial reference systems and coordinates

Example Usage
~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.nodes import StratigraphicNode, DocumentNode, ExtractorNode
   
   # Create stratigraphic unit
   wall = StratigraphicNode("US001", node_type="US")
   wall.set_attribute("material", "limestone")
   wall.set_attribute("technique", "opus_reticulatum")
   
   # Create documentation
   photo = DocumentNode("DOC001", "wall_photo.jpg")
   photo.set_attribute("author", "archaeologist@site.org")
   photo.set_attribute("date", "2024-03-15")
   
   # Create analysis
   analysis = ExtractorNode("EXT001")
   analysis.set_attribute("method", "visual_analysis") 
   analysis.set_attribute("result", "Roman period construction")

Edge Types and Relationships
-----------------------------

s3dgraphy defines specific edge types that correspond to archaeological relationships 
and CIDOC-CRM ontology mappings:

Temporal Relationships
~~~~~~~~~~~~~~~~~~~~~~

**line** - Sequential relationships
   Basic temporal sequences between stratigraphic units (before/after)

**dashed** - Provenance relationships  
   Links between data and its documentation sources

**dotted** - Temporal changes
   Represents modifications or evolution of entities over time

**double_line** - Contemporaneity
   Simultaneous existence or compositional relationships

Analytical Relationships
~~~~~~~~~~~~~~~~~~~~~~~~

**dashed_dotted** - Conflicting hypotheses
   Represents alternative interpretations or mutually exclusive properties

**TBD** - Undefined relationships
   Placeholder for relationships that need further classification

Example Usage
~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy import Graph
   
   graph = Graph("site_relationships")
   
   # Add temporal sequence: US003 is earlier than US002
   graph.add_edge("temp_1", "US003", "US002", "line")
   
   # Add documentation: photo documents the wall  
   graph.add_edge("doc_1", "US001", "DOC001", "dashed")
   
   # Add contemporaneity: floor and wall are contemporary
   graph.add_edge("contemp_1", "US001", "US004", "double_line")

Data Export and Interoperability
---------------------------------

s3dgraphy provides multiple export formats for data exchange and integration:

JSON Export Structure
~~~~~~~~~~~~~~~~~~~~~

The primary export format is structured JSON that preserves all graph information:

.. code-block:: json

   {
       "context": {},
       "multigraph": {
           "SiteA_2024": {
               "name@it": "Site A Excavation",
               "description@it": "2024 excavation campaign",
               "data": {
                   "geo_position": {
                       "epsg": 32633,
                       "shift_x": 500000.0,
                       "shift_y": 4500000.0,
                       "shift_z": 100.0
                   },
                   "epochs": {
                       "Roman": {
                           "start": -27,
                           "end": 476,
                           "color": "#CC6600"
                       }
                   }
               },
               "nodes": {},
               "edges": {}
           }
       }
   }

GraphML Export
~~~~~~~~~~~~~~

For compatibility with network analysis tools and graph databases:

.. code-block:: python

   # Export to GraphML format
   graph.export_graphml("site_analysis.graphml")
   
   # Import from existing GraphML
   from s3dgraphy.importers import GraphMLImporter
   importer = GraphMLImporter()
   imported_graph = importer.import_from_file("existing_data.graphml")

CIDOC-CRM Mapping
~~~~~~~~~~~~~~~~~

s3dgraphy maintains full compatibility with CIDOC-CRM ontology for heritage data:

.. list-table:: Edge Type Mappings
   :header-rows: 1
   :widths: 20 30 50

   * - **Edge Type**
     - **CIDOC-CRM Property**
     - **Archaeological Meaning**
   * - line
     - P4 has time-span
     - Chronological sequence of stratigraphic events
   * - dashed  
     - P22 has modifier
     - Provenance and documentation relationships
   * - dotted
     - P1 is identified by
     - Temporal changes or entity evolution
   * - double_line
     - P106 is composed of
     - Contemporary units or compositional relationships
   * - dashed_dotted
     - P2 has type
     - Alternative interpretations or conflicting properties

Integration with Extended Matrix Framework
------------------------------------------

s3dgraphy serves as the core library for the broader Extended Matrix ecosystem:

**EMtools for Blender**
   3D visualization and interactive annotation of stratigraphic units

**3D Survey Collection (3DSC)**
   High-quality 3D model preparation and metadata management

**ATON 3 Framework** 
   Web-based archaeological visualization and data sharing

**Heriverse Platform**
   Virtual heritage experiences and public engagement

The library's design ensures seamless data flow between these tools while maintaining 
scientific rigor and documentation standards.

Performance and Scalability
----------------------------

s3dgraphy is optimized for real-world archaeological projects:

**Graph Size Support**
   - **Small projects**: 100-500 nodes (single-season excavations)
   - **Medium projects**: 500-5,000 nodes (multi-season sites)  
   - **Large projects**: 5,000+ nodes (major archaeological sites)

**Memory Management**
   - Lazy loading for large datasets
   - Efficient node and edge storage
   - Configurable caching strategies

**Performance Optimization**
   - Indexed node and edge lookups
   - Optimized graph traversal algorithms
   - Batch operations for bulk data handling

.. code-block:: python

   # Performance example: bulk node creation
   graph = Graph("large_site")
   
   # Efficient batch addition
   nodes = []
   for i in range(1000):
       node = StratigraphicNode(f"US{i:03d}", node_type="US")
       nodes.append(node)
   
   graph.add_nodes_batch(nodes)  # Single operation vs. 1000 individual calls

Extensibility and Customization
--------------------------------

s3dgraphy is designed for extension and customization:

Custom Node Types
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.nodes import Node
   
   class CustomSampleNode(Node):
       """Custom node type for specialized sample analysis"""
       
       def __init__(self, node_id, sample_type):
           super().__init__(node_id, "custom_sample")
           self.set_attribute("sample_type", sample_type)
           
       def add_analysis_result(self, method, result):
           if "analyses" not in self.attributes:
               self.attributes["analyses"] = {}
           self.attributes["analyses"][method] = result

Custom Relationship Types
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Register custom edge types
   graph.register_edge_type("chemical_similarity", {
       "cidoc_mapping": "P130_shows_features_of",
       "description": "Chemical composition similarity"
   })
   
   # Use custom relationship
   graph.add_edge("chem_1", "SAMPLE001", "SAMPLE002", "chemical_similarity")

For more advanced customization examples, see the :doc:`examples/extension_development` guide.