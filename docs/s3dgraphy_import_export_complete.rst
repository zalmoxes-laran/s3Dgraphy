Import and Export
=================

This document describes the import and export capabilities of s3dgraphy, the core Python library for managing Extended Matrix graphs.

.. note::
   s3dgraphy version 0.1.13 currently supports:
   
   - **Import**: GraphML, XLSX (with JSON mapping), SQLite/pyArchInit (with JSON mapping)
   - **Export**: JSON
   - **Planned**: GraphML export (future release)

Import System
-------------

s3dgraphy provides a flexible import system that can read data from multiple formats and convert them into the Extended Matrix graph structure.

GraphML Import
~~~~~~~~~~~~~~

GraphML is the primary interchange format for Extended Matrix graphs. The GraphML importer reads graph structure, nodes, edges, and attributes.

Basic GraphML Import
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from s3dgraphy.importer import GraphMLImporter
   from s3dgraphy import Graph
   
   # Create a new graph
   graph = Graph("pompeii_excavation")
   
   # Create importer and parse GraphML file
   importer = GraphMLImporter("excavation_data.graphml")
   graph = importer.parse()
   
   # Check import results
   print(f"Imported {len(graph.nodes)} nodes")
   print(f"Imported {len(graph.edges)} edges")
   
   # Check for warnings
   if graph.warnings:
       print("\nImport warnings:")
       for warning in graph.warnings:
           print(f"  - {warning}")

GraphML Import Features
^^^^^^^^^^^^^^^^^^^^^^^

The GraphML importer includes:

- **Automatic node type detection** from GraphML attributes
- **Edge type mapping** to Extended Matrix connection types
- **Attribute preservation** for all node and edge properties
- **Warning system** for incomplete or malformed data
- **Support for multilingual content** (name, description fields)
- **Placeholder date detection** (XX values) with warnings

.. code-block:: python

   # Import with detailed validation
   importer = GraphMLImporter("site_data.graphml")
   graph = importer.parse()
   
   # Validate imported data
   print("\n=== Import Summary ===")
   print(f"Total nodes: {len(graph.nodes)}")
   print(f"Total edges: {len(graph.edges)}")
   
   # Count nodes by type
   from collections import Counter
   node_types = Counter(node.node_type for node in graph.nodes)
   print("\nNodes by type:")
   for node_type, count in node_types.items():
       print(f"  {node_type}: {count}")
   
   # Count edges by type  
   edge_types = Counter(edge.edge_type for edge in graph.edges)
   print("\nEdges by type:")
   for edge_type, count in edge_types.items():
       print(f"  {edge_type}: {count}")

XLSX Import with JSON Mapping
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

s3dgraphy can import data from Excel files using JSON mapping configurations. This is useful for importing structured archaeological data from spreadsheets.

Mapped XLSX Import
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from s3dgraphy.importer import MappedXLSXImporter
   from s3dgraphy import Graph
   
   # Create graph
   graph = Graph("xlsx_import")
   
   # Create importer with mapping file
   importer = MappedXLSXImporter(
       filepath="stratigraphic_units.xlsx",
       mapping_name="emdb_basic",  # Name of mapping in registry
       graph=graph
   )
   
   # Parse and import
   graph = importer.parse()
   
   print(f"Imported {len(graph.nodes)} nodes from XLSX")
   
   # Display any warnings
   importer.display_warnings()

Mapping System
^^^^^^^^^^^^^^

The mapping system uses JSON configuration files to define how Excel columns map to graph node attributes.

**Mapping file structure:**

.. code-block:: json

   {
       "mapping_name": "emdb_basic",
       "description": "Basic EMdb format for stratigraphic units",
       "version": "1.0",
       "format_type": "xlsx",
       "table_settings": {
           "sheet_name": "US",
           "header_row": 0
       },
       "column_mappings": {
           "US": {
               "is_id": true,
               "required": true,
               "node_attribute": "node_id"
           },
           "Definition": {
               "node_attribute": "description"
           },
           "Chronology": {
               "node_attribute": "dating"
           },
           "Material": {
               "node_attribute": "material"
           }
       },
       "node_settings": {
           "default_node_type": "US"
       }
   }

**How column matching works:**

1. Column names are normalized (uppercase, underscores replace spaces/dashes)
2. JSON mapping columns are matched to Excel columns after normalization
3. Unmatched columns generate warnings but don't stop import
4. At minimum, the ID column must be found

.. code-block:: python

   # Example: Excel has columns "US Number", "Description", "Date"
   # Mapping has "US", "Definition", "Chronology"
   # After normalization: "US_NUMBER", "DESCRIPTION", "DATE"
   # Matches: "US" -> "US_NUMBER" ✓, "Definition" -> "DESCRIPTION" ✓
   # No match: "Chronology" (generates warning)

Custom Mapping Creation
^^^^^^^^^^^^^^^^^^^^^^^

You can create custom mapping files for your specific data formats:

.. code-block:: python

   # Custom mapping for site-specific format
   custom_mapping = {
       "mapping_name": "mysite_format",
       "description": "Custom format for My Excavation Site",
       "version": "1.0",
       "format_type": "xlsx",
       "table_settings": {
           "sheet_name": "Stratigraphic Units",
           "header_row": 0
       },
       "column_mappings": {
           "Unit_ID": {
               "is_id": true,
               "required": true,
               "node_attribute": "node_id"
           },
           "Unit_Type": {
               "node_attribute": "node_type",
               "required": true
           },
           "Description_English": {
               "node_attribute": "description"
           },
           "Excavation_Area": {
               "node_attribute": "area"
           },
           "Excavator_Name": {
               "node_attribute": "excavator"
           }
       },
       "node_settings": {
           "default_node_type": "US",
           "create_properties": true
       }
   }
   
   # Save to JSON file
   import json
   with open('mappings/mysite_format.json', 'w') as f:
       json.dump(custom_mapping, f, indent=2)
   
   # Register and use
   from s3dgraphy.mappings import mapping_registry
   mapping_registry.register_mapping('mysite_format', custom_mapping)

SQLite/pyArchInit Import
~~~~~~~~~~~~~~~~~~~~~~~~~

s3dgraphy can import data from SQLite databases, with specialized support for pyArchInit database format.

PyArchInit Database Import
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from s3dgraphy.importer import PyArchInitImporter
   from s3dgraphy import Graph
   
   # Create graph
   graph = Graph("pyarchinit_import")
   
   # Create importer with mapping
   importer = PyArchInitImporter(
       filepath="excavation.db",
       mapping_name="pyarchinit_us_table",  # Predefined mapping
       graph=graph
   )
   
   # Parse database
   graph = importer.parse()
   
   print(f"Imported {len(graph.nodes)} nodes from database")
   importer.display_warnings()

PyArchInit mapping example:

.. code-block:: json

   {
       "mapping_name": "pyarchinit_us_table",
       "description": "PyArchInit US table mapping",
       "version": "1.0",
       "format_type": "sqlite",
       "table_settings": {
           "table_name": "us_table",
           "id_column": "sito||'_'||area||'_'||us"
       },
       "column_mappings": {
           "sito": {
               "node_attribute": "site"
           },
           "area": {
               "node_attribute": "area"
           },
           "us": {
               "is_id": true,
               "node_attribute": "node_id"
           },
           "d_stratigrafica": {
               "node_attribute": "description"
           },
           "interpretazione": {
               "node_attribute": "interpretation"
           }
       },
       "node_settings": {
           "default_node_type": "US",
           "id_format": "{site}_{area}_{us}"
       }
   }

Import Factory Function
~~~~~~~~~~~~~~~~~~~~~~~~

The ``create_importer`` factory function provides a unified interface for all import formats:

.. code-block:: python

   from s3dgraphy.importer import create_importer
   from s3dgraphy import Graph
   
   # GraphML import
   importer = create_importer(
       filepath='data.graphml',
       format_type='graphml'
   )
   
   # XLSX import with mapping
   importer = create_importer(
       filepath='data.xlsx',
       format_type='xlsx',
       mapping_name='emdb_basic'
   )
   
   # SQLite import
   importer = create_importer(
       filepath='excavation.db',
       format_type='sqlite',
       mapping_name='pyarchinit_us_table'
   )
   
   # Parse with any importer
   graph = importer.parse()

Export System
-------------

JSON Export
~~~~~~~~~~~

s3dgraphy exports graphs to JSON format, which is used for web visualization platforms like Heriverse and ATON.

Basic JSON Export
^^^^^^^^^^^^^^^^^

.. code-block:: python

   from s3dgraphy.exporter import JSONExporter
   from s3dgraphy import get_graph
   
   # Get graph to export
   graph = get_graph("pompeii_excavation")
   
   # Create exporter
   exporter = JSONExporter("output/project.json")
   
   # Export single graph
   exporter.export_graphs([graph.graph_id])
   
   print(f"Exported graph to project.json")

Export All Graphs
^^^^^^^^^^^^^^^^^

.. code-block:: python

   from s3dgraphy.exporter import JSONExporter
   from s3dgraphy import get_all_graph_ids
   
   # Export all loaded graphs
   exporter = JSONExporter("output/all_graphs.json")
   exporter.export_graphs()  # No arguments = export all
   
   # Or specify multiple graphs
   graph_ids = get_all_graph_ids()
   exporter.export_graphs(graph_ids)

JSON Export Structure
^^^^^^^^^^^^^^^^^^^^^

The exported JSON has this structure:

.. code-block:: json

   {
       "version": "1.5",
       "graphs": {
           "pompeii_house_vii": {
               "name": "House VII Excavation",
               "description": "2024 excavation campaign",
               "defaults": {
                   "license": "CC-BY-NC-ND",
                   "authors": ["AUTH.001", "AUTH.002"],
                   "embargo_until": null,
                   "panorama": "panorama/defsky.jpg"
               },
               "nodes": {
                   "US": [
                       {
                           "type": "US",
                           "name": "US001",
                           "description": "Mosaic floor",
                           "data": {
                               "material": "tesserae",
                               "dating": "1st century CE"
                           }
                       }
                   ],
                   "DOC": [
                       {
                           "type": "DOC",
                           "name": "DOC001",
                           "description": "Floor photograph",
                           "data": {}
                       }
                   ]
               },
               "edges": {
                   "is_before": [
                       {
                           "id": "edge_001",
                           "from": "US002",
                           "to": "US001"
                       }
                   ],
                   "has_documentation": [
                       {
                           "id": "edge_002",
                           "from": "US001",
                           "to": "DOC001"
                       }
                   ]
               }
           }
       }
   }

Convenience Export Function
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from s3dgraphy.exporter import export_to_json
   
   # Simple one-line export
   export_to_json("output/graphs.json")  # Exports all graphs
   
   # Export specific graphs
   export_to_json("output/subset.json", ["graph_1", "graph_2"])

Usage in EM-tools Heriverse Exporter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is a real-world example of how s3dgraphy's JSONExporter is used in EM-tools for Blender to export projects to Heriverse format:

.. code-block:: python

   # From EM-tools exporter_heriverse.py
   
   from s3dgraphy.exporter.json_exporter import JSONExporter
   from s3dgraphy import get_graph, get_all_graph_ids
   
   def export_heriverse_project(context):
       """Export complete Heriverse project with 3D models and graph data"""
       
       # Step 1: Update graph with current Blender scene data
       # This syncs any changes made in Blender back to the graph
       update_graph_with_scene_data(update_all_graphs=True, context=context)
       
       # Step 2: Export JSON using JSONExporter
       json_path = os.path.join(project_path, "project.json")
       print(f"Exporting JSON to: {json_path}")
       
       # Create exporter
       exporter = JSONExporter(json_path)
       
       # Export all graphs (or only publishable ones)
       exporter.export_graphs()
       
       print("JSON export completed successfully")
       
       # The exported JSON is then used by Heriverse web platform
       # to display the 3D models with their graph relationships

**Complete Heriverse export workflow:**

1. User works in Blender with 3D models and EM graph
2. Models are linked to graph nodes (US, USV, DOC, etc.)
3. Export operator exports:
   
   - 3D models (glTF format) to ``/models`` folder
   - Proxy models to ``/proxies`` folder
   - Documentation files to ``/dosco`` folder
   - **Graph data via JSONExporter** to ``project.json``

4. Heriverse platform reads ``project.json`` to:
   
   - Display graph structure
   - Link 3D models to nodes
   - Show temporal relationships (epochs)
   - Display paradata chains
   - Manage documentation

Import/Export Best Practices
-----------------------------

Data Validation
~~~~~~~~~~~~~~~

Always validate imported data:

.. code-block:: python

   def validate_import(graph):
       """Validate imported graph data"""
       issues = []
       
       # Check for orphaned nodes
       node_ids = {n.node_id for n in graph.nodes}
       for edge in graph.edges:
           if edge.edge_source not in node_ids:
               issues.append(f"Edge {edge.edge_id} references missing source {edge.edge_source}")
           if edge.edge_target not in node_ids:
               issues.append(f"Edge {edge.edge_id} references missing target {edge.edge_target}")
       
       # Check required attributes
       for node in graph.nodes:
           if not hasattr(node, 'name') or not node.name:
               issues.append(f"Node {node.node_id} missing name")
       
       # Report issues
       if issues:
           print("Validation issues found:")
           for issue in issues:
               print(f"  - {issue}")
       else:
           print("✓ Graph validation passed")
       
       return len(issues) == 0

Error Handling
~~~~~~~~~~~~~~

Wrap import/export operations in proper error handling:

.. code-block:: python

   def safe_import(filepath, format_type, **kwargs):
       """Import with comprehensive error handling"""
       try:
           importer = create_importer(
               filepath=filepath,
               format_type=format_type,
               **kwargs
           )
           
           graph = importer.parse()
           
           # Check warnings
           if graph.warnings:
               print(f"Import completed with {len(graph.warnings)} warnings")
               for warning in graph.warnings:
                   print(f"  ⚠ {warning}")
           
           # Validate
           if validate_import(graph):
               print("✓ Import successful and validated")
               return graph
           else:
               print("✗ Import completed but validation failed")
               return graph  # Return anyway, let user decide
               
       except FileNotFoundError:
           print(f"✗ Error: File not found: {filepath}")
           return None
       except Exception as e:
           print(f"✗ Import failed: {str(e)}")
           import traceback
           traceback.print_exc()
           return None

Performance Considerations
~~~~~~~~~~~~~~~~~~~~~~~~~~

For large datasets:

.. code-block:: python

   # Use graph indices for efficient queries
   graph = importer.parse()
   
   # Indices are automatically built
   # Access via graph.indices for O(1) lookups
   
   # Get all US nodes efficiently
   us_nodes = graph.get_nodes_by_type("US")
   
   # Find edges by source efficiently  
   edges_from_us001 = [
       e for e in graph.edges 
       if e.edge_source == "US001"
   ]

Future Import/Export Features
------------------------------

Planned for future releases:

GraphML Export
~~~~~~~~~~~~~~

GraphML export functionality is planned for a future release:

.. code-block:: python

   # PLANNED - Not yet implemented
   from s3dgraphy.exporter import GraphMLExporter
   
   exporter = GraphMLExporter("output.graphml")
   exporter.export_graph(graph.graph_id)

Additional Export Formats
~~~~~~~~~~~~~~~~~~~~~~~~~~

Under consideration:

- **GeoJSON export** for GIS integration
- **RDF/TTL export** for semantic web (CIDOC-CRM compliance)
- **Neo4j export** for graph database integration

See Also
--------

- :doc:`s3dgraphy_json_config` - JSON configuration files documentation
- :doc:`s3dgraphy_mapping_system` - Detailed mapping system guide
- :doc:`s3dgraphy_integration_emtools` - Integration with EM-tools for Blender
- :doc:`api/s3dgraphy_classes_reference` - Complete API reference
