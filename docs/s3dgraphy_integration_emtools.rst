Integration with EM-tools for Blender
======================================

s3dgraphy is the core graph library that powers EM-tools, a Blender extension for archaeological documentation and 3D reconstruction using the Extended Matrix methodology.

This document explains how s3dgraphy integrates with EM-tools and provides real-world usage examples.

Overview
--------

EM-tools for Blender uses s3dgraphy to:

1. **Import archaeological data** from GraphML, XLSX, and SQLite databases
2. **Manage graph structures** representing stratigraphic relationships
3. **Link 3D models** to graph nodes (US, USV, DOC, etc.)
4. **Sync data** between Blender scene and graph
5. **Export complete projects** to web platforms (Heriverse, ATON)

Architecture
------------

.. code-block:: text

   ┌─────────────────────────────────────────────────┐
   │           Blender UI (EM-tools)                 │
   │  - Setup Panel                                  │
   │  - US/USV Manager                               │
   │  - Epoch Manager                                │
   │  - Paradata Manager                             │
   │  - Export Manager                               │
   └─────────────────┬───────────────────────────────┘
                     │
                     │ Uses
                     ↓
   ┌─────────────────────────────────────────────────┐
   │            s3dgraphy Library                    │
   │  - Graph management                             │
   │  - Node/Edge structures                         │
   │  - Import/Export                                │
   │  - CIDOC-CRM mappings                           │
   └─────────────────┬───────────────────────────────┘
                     │
                     │ Manages
                     ↓
   ┌─────────────────────────────────────────────────┐
   │         Archaeological Graph Data               │
   │  - Stratigraphic relationships                  │
   │  - Temporal sequences (epochs)                  │
   │  - Documentation chains (paradata)              │
   │  - 3D model links                               │
   └─────────────────────────────────────────────────┘

Installation
------------

s3dgraphy is automatically installed as a dependency when you install EM-tools:

.. code-block:: bash

   # EM-tools automatically installs s3dgraphy from PyPI
   # As a wheel dependency in the Blender extension

Or install manually:

.. code-block:: bash

   pip install s3dgraphy

Key Integration Points
----------------------

1. Graph Loading and Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

EM-tools uses s3dgraphy's multi-graph system to manage multiple GraphML files:

.. code-block:: python

   # From EM-tools import_operators/importer_graphml.py
   
   from s3dgraphy.importer import GraphMLImporter
   from s3dgraphy import Graph
   from s3dgraphy.multigraph.multigraph import multi_graph_manager
   
   def import_graphml_file(filepath, graph_name):
       """Import GraphML and register in multi-graph manager"""
       
       # Create graph
       graph = Graph(graph_name)
       
       # Import GraphML
       importer = GraphMLImporter(filepath)
       graph = importer.parse()
       
       # Register in manager
       multi_graph_manager.graphs[graph_name] = graph
       
       print(f"Loaded graph '{graph_name}' with {len(graph.nodes)} nodes")
       
       return graph

2. Scene Synchronization
~~~~~~~~~~~~~~~~~~~~~~~~~

EM-tools synchronizes Blender objects with graph nodes:

.. code-block:: python

   # From EM-tools graph_updaters.py
   
   from s3dgraphy import get_graph
   from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
   
   def update_graph_with_scene_data(graph_id, context):
       """Sync Blender scene changes back to graph"""
       
       graph = get_graph(graph_id)
       if not graph:
           return
       
       # Update nodes from Blender objects
       for obj in context.scene.objects:
           if not hasattr(obj, 'EM_ep_belong_ob'):
               continue
           
           # Find corresponding node
           node = graph.find_node_by_id(obj.name)
           if node and isinstance(node, StratigraphicNode):
               # Sync properties
               if hasattr(obj, 'EM_description'):
                   node.description = obj.EM_description
               
               # Sync epochs
               epochs = [ep.epoch for ep in obj.EM_ep_belong_ob]
               node.epochs = epochs
       
       print(f"Synced {len(context.scene.objects)} objects to graph")

3. Property Management
~~~~~~~~~~~~~~~~~~~~~~

Properties from the graph are made available in Blender:

.. code-block:: python

   # From EM-tools populate_lists.py
   
   def populate_properties_list(context, graph):
       """Populate Blender property list from graph"""
       
       scene = context.scene
       scene.em_properties_list.clear()
       
       # Get all property nodes
       property_nodes = graph.get_nodes_by_type("property")
       
       for prop_node in property_nodes:
           item = scene.em_properties_list.add()
           item.name = prop_node.name
           item.id_node = prop_node.node_id
           item.description = prop_node.description
           
           # Get property value
           if hasattr(prop_node, 'value'):
               item.value = str(prop_node.value)

Real-World Example: Heriverse Exporter
---------------------------------------

The Heriverse exporter is an excellent example of s3dgraphy integration. It exports complete archaeological projects for web visualization.

Complete Export Workflow
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # From EM-tools export_operators/exporter_heriverse.py
   
   import bpy
   import os
   from s3dgraphy.exporter.json_exporter import JSONExporter
   from s3dgraphy import get_graph, get_all_graph_ids
   
   class EXPORT_OT_heriverse(bpy.types.Operator):
       """Export complete Heriverse project"""
       bl_idname = "export.heriverse"
       bl_label = "Export Heriverse Project"
       
       def execute(self, context):
           scene = context.scene
           export_vars = context.window_manager.export_vars
           
           # Get export path
           project_path = scene.heriverse_export_path
           project_name = scene.heriverse_project_name
           
           print(f"\n=== Starting Heriverse Export ===")
           print(f"Project: {project_name}")
           print(f"Path: {project_path}")
           
           # STEP 1: Export 3D models
           if export_vars.heriverse_export_rm:
               models_path = os.path.join(project_path, "models")
               os.makedirs(models_path, exist_ok=True)
               self.export_rm_models(context, models_path)
           
           # STEP 2: Export proxy models  
           if export_vars.heriverse_export_proxies:
               proxies_path = os.path.join(project_path, "proxies")
               os.makedirs(proxies_path, exist_ok=True)
               self.export_proxies(context, proxies_path)
           
           # STEP 3: Export documentation files
           if export_vars.heriverse_export_dosco:
               dosco_path = os.path.join(project_path, "dosco")
               self.export_dosco(context, dosco_path)
           
           # STEP 4: Sync graph with current scene state
           self.sync_graphs_before_export(context)
           
           # STEP 5: Export graph data to JSON using s3dgraphy
           if export_vars.heriverse_overwrite_json:
               json_path = os.path.join(project_path, "project.json")
               self.export_json_with_s3dgraphy(json_path)
           
           # STEP 6: Create ZIP if requested
           if export_vars.heriverse_create_zip:
               self.create_project_zip(project_path)
           
           print("✓ Heriverse export completed")
           return {'FINISHED'}

Syncing Graphs Before Export
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def sync_graphs_before_export(self, context):
       """Ensure all graph data is up to date before export"""
       
       from ..graph_updaters import update_graph_with_scene_data
       
       em_tools = context.scene.em_tools
       
       # Check if we have multiple graphs
       has_multiple_graphs = len(em_tools.graphml_files) > 1
       
       if has_multiple_graphs:
           # Update all publishable graphs
           print("Updating all publishable graphs...")
           update_graph_with_scene_data(
               update_all_graphs=True, 
               context=context
           )
       else:
           # Update single active graph
           if em_tools.active_file_index >= 0:
               graphml = em_tools.graphml_files[em_tools.active_file_index]
               print(f"Updating graph: {graphml.name}")
               update_graph_with_scene_data(graphml.name, context=context)

JSON Export Using s3dgraphy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def export_json_with_s3dgraphy(self, json_path):
       """Export graph data to JSON using s3dgraphy's JSONExporter"""
       
       print(f"\n--- Exporting JSON ---")
       print(f"Output path: {json_path}")
       
       # Create JSONExporter
       from s3dgraphy.exporter.json_exporter import JSONExporter
       exporter = JSONExporter(json_path)
       
       # Export all graphs (or only publishable ones)
       # The exporter will automatically get all registered graphs
       exporter.export_graphs()
       
       print("✓ JSON export completed")
       
       # Verify file was created
       if os.path.exists(json_path):
           file_size = os.path.getsize(json_path)
           print(f"  File size: {file_size / 1024:.2f} KB")
       else:
           raise Exception("JSON file was not created!")

Simplified JSON Export Operator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

EM-tools also provides a standalone JSON export operator:

.. code-block:: python

   # From export_operators/exporter_heriverse.py
   
   class JSON_OT_exportEMformat(bpy.types.Operator):
       """Export project data in Heriverse JSON format"""
       bl_idname = "export.heriversejson"
       bl_label = "Export Heriverse JSON"
       
       filename_ext = ".json"
       
       filepath: bpy.props.StringProperty(
           name="File Path",
           description="Path to save the JSON file"
       )
       
       def execute(self, context):
           print("\n=== Starting Heriverse JSON Export ===")
           
           try:
               # Import s3dgraphy exporter
               from s3dgraphy.exporter.json_exporter import JSONExporter
               
               # Create exporter with filepath
               exporter = JSONExporter(self.filepath)
               
               print(f"Created JSONExporter for path: {self.filepath}")
               
               # Export all graphs
               exporter.export_graphs()
               print("Graphs exported successfully")
               
               self.report(
                   {'INFO'}, 
                   f"Heriverse data successfully exported to {self.filepath}"
               )
               return {'FINISHED'}
               
           except Exception as e:
               print(f"Error during JSON export: {str(e)}")
               import traceback
               traceback.print_exc()
               self.report({'ERROR'}, f"Error during export: {str(e)}")
               return {'CANCELLED'}

Exported JSON Structure
~~~~~~~~~~~~~~~~~~~~~~~

The exported JSON has this structure (used by Heriverse web platform):

.. code-block:: json

   {
       "version": "1.5",
       "graphs": {
           "pompeii_house_vii": {
               "name": "House VII Excavation",
               "description": "2024 excavation campaign",
               "defaults": {
                   "license": "CC-BY-NC-ND",
                   "authors": ["AUTH.001"],
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
                               "dating": "1st century CE",
                               "model_path": "models/US001.glb"
                           }
                       }
                   ],
                   "EP": [
                       {
                           "type": "EP",
                           "name": "EP01",
                           "description": "Roman Imperial Period",
                           "data": {
                               "start_date": -27,
                               "end_date": 476
                           }
                       }
                   ]
               },
               "edges": {
                   "is_before": [
                       {"id": "e1", "from": "US002", "to": "US001"}
                   ],
                   "has_first_epoch": [
                       {"id": "e2", "from": "US001", "to": "EP01"}
                   ]
               }
           }
       }
   }

Using the Exported Project
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The exported Heriverse project contains:

.. code-block:: text

   project_name/
   ├── project.json          # Graph data from s3dgraphy
   ├── models/               # 3D models (glTF)
   │   ├── US001.glb
   │   ├── US002.glb
   │   └── ...
   ├── proxies/              # Proxy models
   │   ├── US001_proxy.glb
   │   └── ...
   ├── dosco/                # Documentation
   │   ├── photos/
   │   ├── drawings/
   │   └── ...
   └── tilesets/             # Cesium 3D Tiles (optional)
       └── ...

The Heriverse web platform reads ``project.json`` to:

1. Display graph structure and relationships
2. Link 3D models to their nodes
3. Show temporal evolution through epochs
4. Display documentation (paradata)
5. Enable navigation through stratigraphic sequences

Other Integration Examples
---------------------------

XLSX Import in EM-tools
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # From import_operators/import_EMdb.py
   
   from s3dgraphy.importer import MappedXLSXImporter
   from s3dgraphy import Graph
   
   def import_xlsx_to_graph(filepath, mapping_name, graph):
       """Import XLSX data using s3dgraphy mapping system"""
       
       # Create importer
       importer = MappedXLSXImporter(
           filepath=filepath,
           mapping_name=mapping_name,
           graph=graph
       )
       
       # Parse and import
       graph = importer.parse()
       
       # Display warnings
       importer.display_warnings()
       
       return graph

PyArchInit Import in EM-tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # From import_operators/import_EMdb.py
   
   from s3dgraphy.importer import PyArchInitImporter
   
   def import_pyarchinit_to_graph(db_path, mapping_name, graph):
       """Import pyArchInit database using s3dgraphy"""
       
       importer = PyArchInitImporter(
           filepath=db_path,
           mapping_name=mapping_name,
           graph=graph
       )
       
       graph = importer.parse()
       importer.display_warnings()
       
       return graph

Landscape System Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

EM-tools includes a "Landscape" mode for managing multiple sites:

.. code-block:: python

   # From landscape_system/populate_functions.py
   
   from s3dgraphy import get_graph, get_all_graph_ids
   
   def load_all_graphs_for_landscape(context):
       """Load all graphs for landscape multi-site view"""
       
       em_tools = context.scene.em_tools
       loaded_graphs = {}
       
       # Iterate through all GraphML files
       for graph_file in em_tools.graphml_files:
           try:
               # Get graph from multi-graph manager
               graph = get_graph(graph_file.name)
               
               if graph and len(graph.nodes) > 0:
                   graph_code = graph.attributes.get('graph_code', 'UNKNOWN')
                   loaded_graphs[graph_code] = graph
                   
           except Exception as e:
               print(f"Error loading graph {graph_file.name}: {e}")
       
       return loaded_graphs
   
   def populate_stratigraphy_list_landscape(context, all_graphs):
       """Populate UI list with nodes from all graphs"""
       
       scene = context.scene
       
       for graph_code, graph in all_graphs.items():
           # Find stratigraphic nodes
           strat_nodes = [
               n for n in graph.nodes 
               if n.node_type in ['US', 'USVs', 'USVn', 'SF', 'VSF']
           ]
           
           for node in strat_nodes:
               # Create list item with graph prefix
               item = scene.em_list.add()
               item.name = f"[{graph_code}] {node.name}"
               item.id_node = node.node_id
               item.node_type = node.node_type
               item.description = node.description

Visual Manager Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Visual Manager uses property values from s3dgraphy to colorize 3D models:

.. code-block:: python

   # From visual_manager/utils.py
   
   from s3dgraphy import get_graph
   from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
   
   def create_property_mapping(graph, property_name):
       """Create mapping of objects to property values"""
       
       mapping = {}
       
       # Use graph indices for efficient lookup
       property_nodes = [
           n for n in graph.nodes
           if n.node_type == "property" and n.name == property_name
       ]
       
       # Track which stratigraphic nodes have this property
       for prop_node in property_nodes:
           value = prop_node.description
           
           # Find connected stratigraphic nodes
           for edge in graph.edges:
               if (edge.edge_type == "has_property" and 
                   edge.edge_target == prop_node.node_id):
                   
                   strat_node = graph.find_node_by_id(edge.edge_source)
                   if strat_node and isinstance(strat_node, StratigraphicNode):
                       mapping[strat_node.name] = value
       
       return mapping

Best Practices for Integration
-------------------------------

1. Use Multi-Graph Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Always use the multi-graph manager for graph lifecycle:

.. code-block:: python

   from s3dgraphy.multigraph.multigraph import multi_graph_manager
   from s3dgraphy import get_graph, get_all_graph_ids
   
   # Register graph
   multi_graph_manager.graphs[graph_id] = graph
   
   # Retrieve graph
   graph = get_graph(graph_id)
   
   # Get all graph IDs
   all_ids = get_all_graph_ids()

2. Sync Before Export
~~~~~~~~~~~~~~~~~~~~~

Always sync scene data to graph before exporting:

.. code-block:: python

   # Update graph with current scene state
   update_graph_with_scene_data(graph_id, context)
   
   # Then export
   exporter.export_graphs()

3. Handle Warnings
~~~~~~~~~~~~~~~~~~

Always check and display importer warnings:

.. code-block:: python

   graph = importer.parse()
   
   if graph.warnings:
       for warning in graph.warnings:
           print(f"⚠ {warning}")
   
   importer.display_warnings()

4. Use Indices for Performance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For large graphs, use the indexing system:

.. code-block:: python

   # Efficient node type lookup
   us_nodes = graph.get_nodes_by_type("US")
   
   # The indices property rebuilds automatically if dirty
   # O(1) lookup instead of O(n)

5. Validate Connections
~~~~~~~~~~~~~~~~~~~~~~~~

Let s3dgraphy validate edge connections:

.. code-block:: python

   try:
       graph.add_edge("e1", "US001", "DOC001", "has_documentation")
   except ValueError as e:
       print(f"Invalid connection: {e}")

Development and Debugging
--------------------------

Enable Debug Output
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # s3dgraphy prints debug info to console
   import s3dgraphy
   
   # Importers show detailed progress
   importer = GraphMLImporter("file.graphml")
   graph = importer.parse()
   # Prints: "Imported 150 nodes", "Imported 200 edges", etc.

Inspect Graph Structure
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy import get_graph
   
   graph = get_graph("my_graph")
   
   print(f"Graph: {graph.graph_id}")
   print(f"Nodes: {len(graph.nodes)}")
   print(f"Edges: {len(graph.edges)}")
   
   # Count by type
   from collections import Counter
   node_types = Counter(n.node_type for n in graph.nodes)
   print(f"Node types: {node_types}")

Test Import/Export
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Test round-trip
   def test_import_export():
       # Import
       importer = GraphMLImporter("test.graphml")
       graph = importer.parse()
       
       # Export
       from s3dgraphy.exporter import JSONExporter
       exporter = JSONExporter("test.json")
       exporter.export_graphs([graph.graph_id])
       
       # Verify
       import json
       with open("test.json") as f:
           data = json.load(f)
           
       print(f"Exported {len(data['graphs'])} graphs")

See Also
--------

- :doc:`s3dgraphy_import_export` - Import/Export documentation
- :doc:`s3dgraphy_json_config` - JSON configuration files
- :doc:`api/s3dgraphy_classes_reference` - Complete API reference
- `EM-tools Repository <https://github.com/zalmoxes-laran/EM-blender-tools>`_
- `s3dgraphy Repository <https://github.com/zalmoxes-laran/s3dgraphy>`_
