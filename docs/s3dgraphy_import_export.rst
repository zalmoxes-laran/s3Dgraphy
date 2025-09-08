Import and Export
=================

s3dgraphy provides comprehensive import and export capabilities for archaeological 
data exchange and integration with external tools.

JSON Export Format
------------------

The primary export format is structured JSON that preserves all graph information 
while maintaining compatibility with web applications and databases.

Overall Structure
~~~~~~~~~~~~~~~~~

The exported JSON follows a hierarchical structure with two main sections:

.. code-block:: json

   {
       "context": {},
       "multigraph": {
           "graph_id_1": { /* graph details */ },
           "graph_id_2": { /* graph details */ }
       }
   }

Context Section
~~~~~~~~~~~~~~~

Reserved for global metadata and export parameters. Currently empty but extensible 
for future requirements:

.. code-block:: json

   "context": {
       "export_date": "2024-03-15T10:30:00Z",
       "s3dgraphy_version": "1.0.0",
       "export_format_version": "1.0"
   }

Multigraph Section
~~~~~~~~~~~~~~~~~~

Contains all loaded graphs, each identified by its unique graph ID:

.. code-block:: json

   "multigraph": {
       "AcropoliSite": { /* complete graph data */ },
       "ForumExcavation": { /* complete graph data */ }
   }

Individual Graph Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~

Each graph contains comprehensive metadata, geographic information, temporal data, 
nodes, and relationships:

.. code-block:: json

   "AcropoliSite": {
       "name@it": "Acropoli di Segni",
       "description@it": "Scavo 2024 - Area monumentale",
       "audio@it": ["intro.mp3", "findings.mp3"],
       "video@it": ["overview.mp4"],
       "image@it": ["site_plan.jpg", "aerial_view.jpg"],
       "data": {
           "geo_position": {
               "epsg": 32633,
               "shift_x": 300000.0,
               "shift_y": 4600000.0,
               "shift_z": 150.0
           },
           "epochs": {
               "Roman_Imperial": {
                   "min": 1200.5,
                   "max": 1250.8,
                   "start": 27,
                   "end": 476,
                   "color": "#CC6600"
               },
               "Medieval": {
                   "min": 1250.8,
                   "max": 1300.2,
                   "start": 500,
                   "end": 1500,
                   "color": "#806040"
               }
           }
       },
       "nodes": { /* all graph nodes */ },
       "edges": { /* all graph relationships */ }
   }

Metadata Fields
^^^^^^^^^^^^^^^

**Multilingual Support**
   Field names with language codes (e.g., ``@it``, ``@en``) support 
   internationalization

**Media References**
   Arrays of file paths for associated audio, video, and image content

**Temporal Framework**
   Epoch definitions with both relative (min/max) and absolute (start/end) dating

Geographic Data
^^^^^^^^^^^^^^^

**Coordinate Reference System**
   EPSG codes for precise spatial positioning

**Spatial Transformations**
   X, Y, Z shifts for local coordinate system alignment

**Integration Support**
   Compatible with GIS systems and 3D modeling software

Nodes Section
~~~~~~~~~~~~~

Contains all nodes within the graph, organized by unique identifiers:

.. code-block:: json

   "nodes": {
       "US001": {
           "type": "US",
           "name": "Stone wall foundation",
           "data": {
               "material": "limestone",
               "technique": "opus_reticulatum",
               "preservation": "good",
               "dating": "1st century CE",
               "dimensions": {
                   "length": 15.6,
                   "width": 0.8,
                   "height": 1.2
               }
           }
       },
       "DOC001": {
           "type": "document",
           "name": "Wall documentation photo",
           "data": {
               "file_path": "photos/US001_north.jpg",
               "author": "M. Rossi",
               "date": "2024-03-10",
               "resolution": "6000x4000",
               "equipment": "Canon EOS R5"
           }
       },
       "EXT001": {
           "type": "extractor",
           "name": "Photogrammetric analysis",
           "data": {
               "software": "Metashape Professional",
               "processing_date": "2024-03-12",
               "point_cloud_density": "high",
               "accuracy": "sub-centimetric"
           }
       }
   }

Node Type Examples
^^^^^^^^^^^^^^^^^^

**Stratigraphic Units**

.. code-block:: json

   "US105": {
       "type": "USVs",
       "name": "Reconstructed column capital",
       "data": {
           "reconstruction_hypothesis": "Corinthian order",
           "certainty_level": "high",
           "source_fragments": ["SF023", "SF024", "SF031"],
           "reconstruction_method": "comparative_analysis"
       }
   }

**Special Finds**

.. code-block:: json

   "SF023": {
       "type": "SF", 
       "name": "Marble column fragment",
       "data": {
           "material": "Carrara marble",
           "find_date": "2024-03-08",
           "context": "US105 fill",
           "dimensions": {"length": 45.2, "width": 38.1, "thickness": 12.8},
           "weight": 15.6,
           "condition": "fragment"
       }
   }

**Documentation**

.. code-block:: json

   "DOC042": {
       "type": "document",
       "name": "Stratigraphic section drawing",
       "data": {
           "document_type": "technical_drawing",
           "scale": "1:20",
           "format": "DWG",
           "creation_software": "AutoCAD 2024",
           "author": "L. Bianchi",
           "approval_date": "2024-03-14"
       }
   }

Edges Section
~~~~~~~~~~~~~

Relationships are categorized by type, with each category containing arrays of 
connections:

.. code-block:: json

   "edges": {
       "line": [
           {
               "from": "US002",
               "to": "US001",
               "properties": {
                   "relationship": "covers",
                   "confidence": "certain",
                   "evidence": "direct_superimposition"
               }
           }
       ],
       "dashed": [
           {
               "from": "US001", 
               "to": "DOC001",
               "properties": {
                   "documentation_type": "photographic",
                   "completeness": "partial",
                   "quality": "high"
               }
           }
       ],
       "dotted": [
           {
               "from": "US105.construction",
               "to": "US105.destruction", 
               "properties": {
                   "temporal_span": "ca. 300 years",
                   "transformation_type": "gradual_decay"
               }
           }
       ]
   }

Edge Type Categories
^^^^^^^^^^^^^^^^^^^^

**Temporal Relationships (line)**
   Stratigraphic sequences, chronological ordering

**Documentation Links (dashed)**  
   Connections between units and their documentation

**Temporal Changes (dotted)**
   Evolution or transformation of entities over time

**Compositional Relations (double_line)**
   Part-whole relationships, contemporary assemblages

**Alternative Hypotheses (dashed_dotted)**
   Conflicting interpretations or uncertain relationships

**Undefined Relations (TBD)**
   Placeholder relationships requiring further analysis

Export API Usage
~~~~~~~~~~~~~~~~

**Basic Export**

.. code-block:: python

   from s3dgraphy.exporters import JSONExporter
   
   # Export single graph
   exporter = JSONExporter()
   graph_data = exporter.export_graph(graph_id="MySite2024")
   
   # Save to file
   exporter.save_to_file(graph_data, "site_export.json")

**Multi-graph Export**

.. code-block:: python

   # Export all loaded graphs
   all_data = exporter.export_all_graphs()
   exporter.save_to_file(all_data, "complete_project.json")

**Custom Export Options**

.. code-block:: python

   # Export with filtering options
   filtered_data = exporter.export_graph(
       graph_id="MySite2024",
       include_nodes=["US", "USV"],  # Only stratigraphic units
       include_edges=["line", "dashed"],  # Only temporal and documentation
       date_range=("2024-01-01", "2024-12-31")  # Time-filtered content
   )

GraphML Import/Export
---------------------

GraphML format provides compatibility with network analysis tools and graph databases.

GraphML Export
~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.exporters import GraphMLExporter
   
   exporter = GraphMLExporter()
   
   # Basic export
   exporter.export_graph("MySite2024", "site_analysis.graphml")
   
   # Export with custom attributes
   exporter.export_graph(
       "MySite2024", 
       "enhanced_export.graphml",
       include_attributes=["material", "dating", "technique"],
       include_metadata=True
   )

GraphML Import
~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.importers import GraphMLImporter
   
   importer = GraphMLImporter()
   
   # Import from existing GraphML file
   imported_graph = importer.import_from_file("existing_data.graphml")
   
   # Import with node type mapping
   imported_graph = importer.import_from_file(
       "legacy_data.graphml",
       node_type_mapping={
           "layer": "US",
           "artifact": "SF", 
           "photo": "document"
       }
   )

Advanced GraphML Features
~~~~~~~~~~~~~~~~~~~~~~~~~

**Attribute Preservation**
   All node and edge attributes are preserved during export/import

**Type Information**
   Node and edge types are maintained using GraphML's type system

**Metadata Support**
   Graph-level metadata is stored in GraphML header information

**Validation**
   Automatic validation against GraphML schema during import

CSV Import
----------

For legacy data migration and bulk data entry:

.. code-block:: python

   from s3dgraphy.importers import CSVImporter
   
   importer = CSVImporter()
   
   # Import nodes from CSV
   graph = importer.import_nodes_from_csv(
       "stratigraphic_units.csv",
       node_id_column="US_ID",
       node_type_column="TYPE", 
       name_column="DESCRIPTION"
   )
   
   # Import relationships from CSV
   importer.import_edges_from_csv(
       graph,
       "relationships.csv",
       source_column="FROM_US",
       target_column="TO_US",
       relationship_column="RELATION_TYPE"
   )

CSV Format Requirements
~~~~~~~~~~~~~~~~~~~~~~~

**Nodes CSV Format**

.. csv-table:: stratigraphic_units.csv
   :header: "US_ID", "TYPE", "DESCRIPTION", "MATERIAL", "DATING"
   :widths: 15, 10, 30, 20, 25

   "US001", "US", "Stone wall foundation", "limestone", "1st century CE"
   "US002", "US", "Floor preparation", "mortar", "1st century CE" 
   "SF001", "SF", "Bronze coin", "bronze", "Antonine period"

**Relationships CSV Format**

.. csv-table:: relationships.csv
   :header: "FROM_US", "TO_US", "RELATION_TYPE", "CONFIDENCE"
   :widths: 15, 15, 20, 20

   "US002", "US001", "line", "certain"
   "US001", "DOC001", "dashed", "high"
   "SF001", "US002", "dashed", "certain"

Integration with External Tools
-------------------------------

Database Export
~~~~~~~~~~~~~~~

**PostgreSQL with PostGIS**

.. code-block:: python

   from s3dgraphy.exporters import PostgreSQLExporter
   
   exporter = PostgreSQLExporter(
       host="localhost",
       database="archaeological_db",
       user="archaeologist"
   )
   
   # Export to normalized tables
   exporter.export_graph("MySite2024", schema="site_data")

**Neo4j Graph Database**

.. code-block:: python

   from s3dgraphy.exporters import Neo4jExporter
   
   exporter = Neo4jExporter(uri="bolt://localhost:7687")
   exporter.export_graph("MySite2024", preserve_relationships=True)

Visualization Tools
~~~~~~~~~~~~~~~~~~~

**Gephi Network Analysis**

.. code-block:: python

   # Export for Gephi visualization
   exporter = GraphMLExporter()
   exporter.export_for_gephi(
       "MySite2024",
       "network_analysis.graphml",
       layout_algorithm="force_atlas2"
   )

**Cytoscape Biological Networks**

.. code-block:: python

   # Export with Cytoscape-compatible attributes
   exporter.export_for_cytoscape(
       "MySite2024",
       "archaeological_network.graphml",
       node_size_attribute="importance",
       edge_width_attribute="confidence"
   )

Validation and Quality Control
------------------------------

Export Validation
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.validators import ExportValidator
   
   validator = ExportValidator()
   
   # Validate before export
   validation_result = validator.validate_graph("MySite2024")
   
   if validation_result.is_valid:
       exporter.export_graph("MySite2024", "validated_export.json")
   else:
       print("Validation errors:")
       for error in validation_result.errors:
           print(f"  - {error}")

Common Validation Checks
~~~~~~~~~~~~~~~~~~~~~~~~~

**Graph Integrity**
   - Orphaned nodes detection
   - Circular relationship validation  
   - Edge endpoint verification

**Data Completeness**
   - Required attribute verification
   - Missing metadata detection
   - Reference integrity checking

**Format Compliance**
   - JSON schema validation
   - GraphML DTD compliance
   - CSV format verification

Performance Optimization
-------------------------

Large Dataset Handling
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Streaming export for large graphs
   exporter = JSONExporter(streaming=True)
   
   with exporter.stream_export("LargeSite2024") as stream:
       stream.write_to_file("large_export.json")

**Memory Management**
   - Chunked processing for large node sets
   - Lazy loading of graph components
   - Configurable buffer sizes

**Parallel Processing**
   - Multi-threaded export operations
   - Concurrent validation processes
   - Parallel format conversion

Batch Operations
~~~~~~~~~~~~~~~~

.. code-block:: python

   # Batch export multiple graphs
   graphs_to_export = ["Site1", "Site2", "Site3"]
   
   for graph_id in graphs_to_export:
       exporter.export_graph(
           graph_id, 
           f"exports/{graph_id}_export.json",
           compress=True
       )

Error Handling and Recovery
---------------------------

Export Error Management
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   try:
       exporter.export_graph("MySite2024", "export.json")
   except GraphExportError as e:
       print(f"Export failed: {e.message}")
       
       # Attempt partial export
       partial_data = exporter.export_partial(
           "MySite2024",
           exclude_problematic_nodes=True
       )
       
   except ValidationError as e:
       print(f"Validation failed: {e.details}")
       
       # Export with warnings
       exporter.export_with_warnings("MySite2024", "export_with_issues.json")

Recovery Strategies
~~~~~~~~~~~~~~~~~~~

**Partial Export Recovery**
   Extract valid portions of corrupted graphs

**Format Fallback**
   Automatic fallback to alternative export formats

**Incremental Export**
   Export only modified components since last successful export

**Backup Integration**
   Automatic backup creation before destructive operations

For more advanced export scenarios and custom format development, 
see :doc:`examples/custom_exporters`.