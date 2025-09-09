s3dgraphy Import/Export Complete Guide
=============================================

This document provides comprehensive coverage of s3dgraphy's import and export capabilities, including GraphML, JSON, CSV formats, advanced configurations, and integration examples.

GraphML Import System
---------------------

GraphMLImporter Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``GraphMLImporter`` class provides sophisticated parsing capabilities for complex GraphML files created by yEd or other graph editing tools.

.. code-block:: python

   class GraphMLImporter:
       """
       Advanced GraphML importer with support for:
       - YED node shapes and styling
       - Table nodes (swimlanes) for epochs
       - Document deduplication
       - ID mapping and collision handling
       - Paradata chain reconstruction
       """
       
       def __init__(self, filepath, graph=None):
           self.filepath = filepath
           self.graph = graph if graph is not None else Graph(graph_id="imported_graph")
           
           # Deduplication and mapping systems
           self.document_nodes_map = {}  # name -> node_id mapping
           self.duplicate_id_map = {}    # original_id -> deduplicated_id
           self.id_mapping = {}          # original_id -> uuid mapping

Basic GraphML Import
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.importer import GraphMLImporter
   from s3dgraphy import Graph

   # Basic import
   importer = GraphMLImporter("excavation_data.graphml")
   graph = importer.parse()

   print(f"Imported graph: {graph.graph_id}")
   print(f"Nodes: {len(graph.nodes)}")
   print(f"Edges: {len(graph.edges)}")

   # Import into existing graph
   existing_graph = Graph("MyProject")
   importer = GraphMLImporter("additional_data.graphml", existing_graph)
   updated_graph = importer.parse()

   # Check for import warnings
   if graph.warnings:
       print("Import warnings:")
       for warning in graph.warnings:
           print(f"  - {warning}")

Advanced GraphML Features
~~~~~~~~~~~~~~~~~~~~~~~~~

Node Type Recognition
^^^^^^^^^^^^^^^^^^^^^

The importer automatically recognizes node types based on yEd shapes and styling:

.. code-block:: python

   def convert_shape2type(yedtype, border_style):
       """
       Maps yEd node shapes to s3dgraphy node types.
       
       Shape Mappings:
           - ellipse: US (Stratigraphic Unit)
           - rectangle: SF (Special Find)
           - hexagon: USV (Virtual Stratigraphic Unit)
           - diamond: DOC (Documentary Unit)
           - parallelogram: Continuity Node
           - trapezoid: Series of units
       
       Border Style Modifiers:
           - dashed: Virtual variants
           - dotted: Transformation units
           - thick: Structural elements
       """

**Example of automatic node type detection:**

.. code-block:: python

   # The importer automatically creates appropriate node types
   # Based on GraphML shape and style information:

   # ellipse + solid border → StratigraphicUnit
   # ellipse + dashed border → NonStructuralVirtualStratigraphicUnit
   # rectangle + solid border → SpecialFindUnit
   # hexagon + thick border → StructuralVirtualStratigraphicUnit
   # diamond → DocumentNode

Epoch Node Handling
^^^^^^^^^^^^^^^^^^^

GraphML table nodes (swimlanes) are converted to temporal epochs:

.. code-block:: python

   def EM_extract_epoch_nodes(self, node_element):
       """
       Extracts epoch information from yEd table nodes.
       
       Features:
           - Automatic Y-coordinate calculation for temporal ordering
           - Row-based epoch creation with proper spacing
           - Name and dating extraction from table content
           - Color scheme preservation for visualization
       """
       
       # Extract geometry for Y positioning
       geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
       y_start = float(geometry.attrib['y'])
       
       # Process each table row as an epoch
       rows = node_element.findall('.//Row')
       epoch_nodes = []
       
       y_min = y_start
       for i, row in enumerate(rows):
           h_row = float(row.attrib['height'])
           y_max = y_min + h_row
           
           # Create epoch with calculated coordinates
           epoch_node = EpochNode(
               node_id=str(uuid.uuid4()),
               name=f"Epoch_{i}",
               start_time=-10000,  # Will be updated from data
               end_time=10000
           )
           
           epoch_node.min_y = y_min
           epoch_node.max_y = y_max
           epoch_nodes.append(epoch_node)
           
           y_min = y_max
       
       return epoch_nodes

Document Deduplication
^^^^^^^^^^^^^^^^^^^^^^

The importer intelligently handles duplicate documents:

.. code-block:: python

   def handle_document_deduplication(self, nodename, original_id):
       """
       Sophisticated document deduplication system.
       
       Process:
           1. Check if document with same name already exists
           2. If exists, map new references to existing document
           3. Update duplicate_id_map for edge creation
           4. Log deduplication actions for transparency
       """
       
       if nodename in self.document_nodes_map:
           # Document already exists
           existing_uuid = self.document_nodes_map[nodename]
           existing_doc = self.graph.find_node_by_id(existing_uuid)
           
           if existing_doc and hasattr(existing_doc, 'attributes'):
               existing_original_id = existing_doc.attributes.get('original_id')
               
               if existing_original_id:
                   self.duplicate_id_map[original_id] = existing_original_id
                   print(f"Deduplicating document: {nodename} ({original_id} -> {existing_original_id})")
               else:
                   self.duplicate_id_map[original_id] = existing_uuid
                   print(f"Deduplicating document: {nodename} ({original_id} -> UUID: {existing_uuid})")
       else:
           # New document, add to map
           self.document_nodes_map[nodename] = new_document_uuid

Edge Type Enhancement
^^^^^^^^^^^^^^^^^^^^^

The importer enhances basic edge types based on connected node types:

.. code-block:: python

   def enhance_edge_type(self, source_node, target_node, edge_type):
       """
       Enhance edge types based on semantic context.
       
       Enhancement Rules:
           - DocumentNode -> ExtractorNode: becomes "extracted_from"
           - ExtractorNode -> CombinerNode: becomes "combines"
           - PropertyNode -> DocumentNode: becomes "has_data_provenance"
           - ParadataNode -> ParadataNodeGroup: becomes "is_in_paradata_nodegroup"
       """
       
       source_type = source_node.node_type if source_node else "unknown"
       target_type = target_node.node_type if target_node else "unknown"
       
       # Apply enhancement rules
       if edge_type == "generic_connection":
           if source_type == "document" and target_type == "extractor":
               return "extracted_from"
           elif source_type == "extractor" and target_type == "combiner":
               return "combines"
           elif source_type == "property" and target_type == "document":
               return "has_data_provenance"
           elif (isinstance(source_node, (DocumentNode, ExtractorNode, CombinerNode)) and 
                 target_type == "ParadataNodeGroup"):
               return "is_in_paradata_nodegroup"
       
       return edge_type

Graph Metadata Extraction
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def extract_graph_metadata(self, tree):
       """
       Extract comprehensive graph metadata from GraphML.
       
       Extracted Information:
           - Graph ID and human-readable code
           - Multilingual names and descriptions
           - Author information with automatic node creation
           - Licensing and embargo information
           - Geographical coordinates and positioning
       """
       
       # Extract from graph attributes
       graph_element = tree.find('.//{http://graphml.graphdrawing.org/xmlns}graph')
       graph_id = graph_element.attrib.get('id', 'default_graph')
       
       # Extract vocabulary from description
       description = graph_element.attrib.get('description', '')
       clean_description, vocabulary = self.estrai_stringa_e_vocabolario(description)
       
       # Process vocabulary information
       if 'id' in vocabulary:
           self.graph.graph_id = vocabulary['id']
       
       if 'name' in vocabulary:
           self.graph.name = {'default': vocabulary['name']}
       
       if 'description' in vocabulary:
           self.graph.description = {'default': vocabulary['description']}
       
       # Handle author information
       if 'author' in vocabulary:
           author_name = vocabulary['author']
           author_id = f"author_{author_name.replace(' ', '_').lower()}"
           
           author_node = AuthorNode(author_id, author_name)
           self.graph.add_node(author_node)
           
           # Connect to graph
           self.graph.add_edge(
               f"auth_{author_id}",
               self.graph.graph_id,
               author_id,
               edge_type="has_author"
           )
       
       # Handle licensing and embargo
       if 'license' in vocabulary:
           self.graph.data['license'] = vocabulary['license']
       
       if 'embargo' in vocabulary:
           self.graph.data['embargo_until'] = vocabulary['embargo']

Complete Import Example
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def comprehensive_graphml_import():
       """Complete example of GraphML import with all features"""
       
       # Import with full error handling
       try:
           importer = GraphMLImporter("complex_excavation.graphml")
           graph = importer.parse()
           
           # Post-import processing
           print(f"Successfully imported: {graph.graph_id}")
           print(f"Name: {graph.name}")
           print(f"Description: {graph.description}")
           
           # Analyze imported content
           node_types = {}
           for node in graph.nodes:
               node_type = node.node_type
               if node_type not in node_types:
                   node_types[node_type] = 0
               node_types[node_type] += 1
           
           print("\nImported node types:")
           for node_type, count in node_types.items():
               print(f"  {node_type}: {count}")
           
           # Check edge types
           edge_types = {}
           for edge in graph.edges:
               edge_type = edge.edge_type
               if edge_type not in edge_types:
                   edge_types[edge_type] = 0
               edge_types[edge_type] += 1
           
           print("\nImported edge types:")
           for edge_type, count in edge_types.items():
               print(f"  {edge_type}: {count}")
           
           # Validate paradata chains
           print("\nValidating paradata chains...")
           stratigraphic_nodes = graph.get_nodes_by_type("US")
           complete_chains = 0
           
           for node in stratigraphic_nodes[:5]:  # Check first 5
               paradata = graph.get_complete_paradata_chain(node.node_id)
               if (len(paradata['properties']) > 0 and 
                   len(paradata['documents']) > 0):
                   complete_chains += 1
               
               print(f"  {node.node_id}: {len(paradata['properties'])} props, "
                     f"{len(paradata['documents'])} docs")
           
           print(f"\nNodes with complete paradata: {complete_chains}/{len(stratigraphic_nodes[:5])}")
           
           # Check for import issues
           if graph.warnings:
               print(f"\nImport warnings ({len(graph.warnings)}):")
               for warning in graph.warnings:
                   print(f"  - {warning}")
           
           return graph
           
       except Exception as e:
           print(f"Import failed: {e}")
           import traceback
           traceback.print_exc()
           return None

   # Usage
   imported_graph = comprehensive_graphml_import()

JSON Export System
------------------

Standard JSON Export
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.exporters import JSONExporter

   def export_to_json(graph, filename):
       """
       Export graph to comprehensive JSON format.
       
       JSON Structure:
           - metadata: Graph information, authors, licensing
           - nodes: Complete node definitions with attributes
           - edges: All relationships with CIDOC-CRM mappings
           - indices: Performance optimization data
           - paradata_chains: Complete documentation lineages
       """
       
       exporter = JSONExporter()
       
       # Basic export
       graph_data = exporter.export_graph(graph.graph_id)
       
       # Enhanced export with additional data
       enhanced_data = {
           "metadata": {
               "graph_id": graph.graph_id,
               "name": graph.name,
               "description": graph.description,
               "export_timestamp": "2024-01-15T10:30:00Z",
               "exporter_version": "s3dgraphy-1.0.0"
           },
           "nodes": [],
           "edges": [],
           "paradata_chains": {},
           "validation_info": {}
       }
       
       # Export nodes with full attribute preservation
       for node in graph.nodes:
           node_data = {
               "node_id": node.node_id,
               "node_type": node.node_type,
               "name": getattr(node, 'name', ''),
               "attributes": getattr(node, 'attributes', {}),
               "cidoc_mapping": get_cidoc_mapping(node.node_type)
           }
           
           # Add type-specific data
           if hasattr(node, 'description'):
               node_data["description"] = node.description
           
           if hasattr(node, 'start_time'):  # EpochNode
               node_data["temporal_data"] = {
                   "start_time": node.start_time,
                   "end_time": node.end_time,
                   "min_y": getattr(node, 'min_y', 0),
                   "max_y": getattr(node, 'max_y', 0)
               }
           
           enhanced_data["nodes"].append(node_data)
       
       # Export edges with relationship semantics
       for edge in graph.edges:
           edge_data = {
               "edge_id": edge.edge_id,
               "source": edge.edge_source,
               "target": edge.edge_target,
               "edge_type": edge.edge_type,
               "label": edge.label,
               "description": edge.description,
               "cidoc_mapping": get_cidoc_mapping_for_edge(edge.edge_type)
           }
           enhanced_data["edges"].append(edge_data)
       
       # Export paradata chains for documentation
       stratigraphic_nodes = graph.get_nodes_by_type("US")
       for node in stratigraphic_nodes:
           paradata = graph.get_complete_paradata_chain(node.node_id)
           enhanced_data["paradata_chains"][node.node_id] = {
               "properties": [p.node_id for p in paradata["properties"]],
               "combiners": [c.node_id for c in paradata["combiners"]],
               "extractors": [e.node_id for e in paradata["extractors"]],
               "documents": [d.node_id for d in paradata["documents"]]
           }
       
       # Validation information
       enhanced_data["validation_info"] = {
           "node_count": len(graph.nodes),
           "edge_count": len(graph.edges),
           "orphaned_nodes": find_orphaned_nodes(graph),
           "circular_dependencies": check_circular_dependencies(graph)
       }
       
       # Save to file
       import json
       with open(filename, 'w', encoding='utf-8') as f:
           json.dump(enhanced_data, f, indent=2, ensure_ascii=False)
       
       print(f"Exported to {filename}")
       return enhanced_data

   def get_cidoc_mapping(node_type):
       """Get CIDOC-CRM mapping for node type"""
       mappings = {
           "US": "E18_Physical_Thing",
           "SF": "E22_Man-Made_Object", 
           "document": "E31_Document",
           "property": "E55_Type",
           "epoch": "E52_Time-Span"
       }
       return mappings.get(node_type, "E1_CRM_Entity")

   def get_cidoc_mapping_for_edge(edge_type):
       """Get CIDOC-CRM property mapping for edge type"""
       mappings = {
           "is_before": "P120_occurs_before",
           "has_same_time": "P114_is_equal_in_time_to",
           "has_property": "P2_has_type",
           "extracted_from": "P67_refers_to"
       }
       return mappings.get(edge_type, "P67_refers_to")

   # Usage
   export_data = export_to_json(graph, "comprehensive_export.json")

Selective Export Options
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def selective_export(graph, **options):
       """
       Export with filtering and selection options.
       
       Options:
           - node_types: List of node types to include
           - edge_types: List of edge types to include
           - include_metadata: Whether to include graph metadata
           - include_paradata: Whether to include paradata chains
           - date_range: Tuple of (start_date, end_date) for temporal filtering
           - area_filter: Specific excavation area to export
       """
       
       # Filter nodes by type
       if 'node_types' in options:
           filtered_nodes = [node for node in graph.nodes 
                            if node.node_type in options['node_types']]
       else:
           filtered_nodes = graph.nodes
       
       # Filter by excavation area
       if 'area_filter' in options:
           area = options['area_filter']
           filtered_nodes = [node for node in filtered_nodes
                            if getattr(node, 'area', '') == area]
       
       # Filter by date range (for nodes with temporal attributes)
       if 'date_range' in options:
           start_date, end_date = options['date_range']
           filtered_nodes = [node for node in filtered_nodes
                            if is_in_date_range(node, start_date, end_date)]
       
       # Create filtered graph
       filtered_graph = Graph(f"{graph.graph_id}_filtered")
       
       # Add filtered nodes
       node_ids = set()
       for node in filtered_nodes:
           filtered_graph.add_node(node)
           node_ids.add(node.node_id)
       
       # Add edges between filtered nodes
       edge_type_filter = options.get('edge_types', None)
       for edge in graph.edges:
           if (edge.edge_source in node_ids and 
               edge.edge_target in node_ids):
               if not edge_type_filter or edge.edge_type in edge_type_filter:
                   filtered_graph.add_edge(
                       edge.edge_id, edge.edge_source, 
                       edge.edge_target, edge.edge_type
                   )
       
       # Export filtered graph
       return export_to_json(filtered_graph, options.get('filename', 'filtered_export.json'))

   # Usage examples
   # Export only stratigraphic units and temporal relationships
   selective_export(graph,
       node_types=["US", "USV"],
       edge_types=["is_before", "has_same_time"],
       filename="stratigraphy_only.json"
   )

   # Export specific excavation area
   selective_export(graph,
       area_filter="Area_A",
       include_paradata=True,
       filename="area_a_export.json"
   )

   # Export Roman period data
   selective_export(graph,
       date_range=("50 BCE", "476 CE"),
       filename="roman_period.json"
   )

CSV Import/Export
-----------------

CSV Import with Mapping
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.importer import CSVImporter

   class AdvancedCSVImporter:
       """Advanced CSV importer with field mapping and validation"""
       
       def __init__(self, csv_file, mapping_file=None):
           self.csv_file = csv_file
           self.mapping = self.load_mapping(mapping_file) if mapping_file else None
           self.graph = None
       
       def load_mapping(self, mapping_file):
           """Load column mapping configuration"""
           import json
           with open(mapping_file, 'r') as f:
               return json.load(f)
       
       def import_stratigraphic_units(self, graph):
           """Import stratigraphic units from CSV"""
           import csv
           
           with open(self.csv_file, 'r', encoding='utf-8') as f:
               reader = csv.DictReader(f)
               
               for row in reader:
                   # Extract node data using mapping
                   node_id = self.get_mapped_value(row, 'id_column', 'US_ID')
                   name = self.get_mapped_value(row, 'name_column', 'Name')
                   description = self.get_mapped_value(row, 'description_column', 'Description')
                   
                   # Create node
                   node = StratigraphicUnit(node_id)
                   node.name = name
                   node.description = description
                   
                   # Map additional attributes
                   for field, column in self.get_attribute_mappings().items():
                       if column in row and row[column]:
                           node.set_attribute(field, row[column])
                   
                   graph.add_node(node)
           
           return graph
       
       def get_mapped_value(self, row, mapping_key, default_column):
           """Get value using mapping or default column"""
           if self.mapping:
               column = self.mapping.get('column_mappings', {}).get(mapping_key, default_column)
           else:
               column = default_column
           
           return row.get(column, '')
       
       def get_attribute_mappings(self):
           """Get attribute column mappings"""
           if self.mapping:
               return self.mapping.get('attribute_mappings', {})
           
           # Default mappings
           return {
               'material': 'Material',
               'dating': 'Dating',
               'technique': 'Technique',
               'preservation': 'Preservation',
               'area': 'Area',
               'sector': 'Sector'
           }

   # CSV mapping configuration example
   csv_mapping = {
       "column_mappings": {
           "id_column": "USN",
           "name_column": "US_Name", 
           "description_column": "US_Description"
       },
       "attribute_mappings": {
           "material": "Material_Type",
           "dating": "Chronology",
           "technique": "Construction_Technique",
           "preservation": "Preservation_State",
           "area": "Excavation_Area",
           "sector": "Grid_Square"
       },
       "validation_rules": {
           "required_fields": ["USN", "US_Name"],
           "data_types": {
               "USN": "string",
               "Dating_Start": "integer",
               "Dating_End": "integer"
           }
       }
   }

   # Usage
   import json
   with open('us_mapping.json', 'w') as f:
       json.dump(csv_mapping, f, indent=2)

   importer = AdvancedCSVImporter('stratigraphic_units.csv', 'us_mapping.json')
   graph = Graph("CSV_Import_Test")
   importer.import_stratigraphic_units(graph)

   print(f"Imported {len(graph.nodes)} nodes from CSV")

CSV Export
~~~~~~~~~~

.. code-block:: python

   def export_to_csv(graph, output_dir="exports"):
       """
       Export graph components to multiple CSV files.
       
       Exports:
           - nodes.csv: All nodes with attributes
           - edges.csv: All relationships
           - stratigraphic_units.csv: US nodes with specialized fields
           - special_finds.csv: SF nodes with artifact data
           - documents.csv: Documentation references
       """
       import csv
       import os
       
       os.makedirs(output_dir, exist_ok=True)
       
       # Export all nodes
       with open(f"{output_dir}/nodes.csv", 'w', newline='', encoding='utf-8') as f:
           writer = csv.writer(f)
           
           # Header
           writer.writerow(['node_id', 'node_type', 'name', 'description', 'attributes_json'])
           
           # Data
           for node in graph.nodes:
               import json
               attributes_json = json.dumps(getattr(node, 'attributes', {}))
               
               writer.writerow([
                   node.node_id,
                   node.node_type,
                   getattr(node, 'name', ''),
                   getattr(node, 'description', ''),
                   attributes_json
               ])
       
       # Export stratigraphic units with specialized fields
       stratigraphic_nodes = graph.get_nodes_by_type("US")
       if stratigraphic_nodes:
           with open(f"{output_dir}/stratigraphic_units.csv", 'w', newline='', encoding='utf-8') as f:
               writer = csv.writer(f)
               
               # Collect all possible attributes
               all_attributes = set()
               for node in stratigraphic_nodes:
                   all_attributes.update(getattr(node, 'attributes', {}).keys())
               
               # Header
               header = ['us_id', 'name', 'description', 'area', 'sector'] + sorted(all_attributes)
               writer.writerow(header)
               
               # Data
               for node in stratigraphic_nodes:
                   row = [
                       node.node_id,
                       getattr(node, 'name', ''),
                       getattr(node, 'description', ''),
                       getattr(node, 'area', ''),
                       getattr(node, 'sector', '')
                   ]
                   
                   # Add attribute values
                   for attr in sorted(all_attributes):
                       value = node.get_attribute(attr, '')
                       row.append(value)
                   
                   writer.writerow(row)
       
       # Export edges
       with open(f"{output_dir}/edges.csv", 'w', newline='', encoding='utf-8') as f:
           writer = csv.writer(f)
           
           # Header
           writer.writerow(['edge_id', 'source', 'target', 'edge_type', 'label', 'description'])
           
           # Data
           for edge in graph.edges:
               writer.writerow([
                   edge.edge_id,
                   edge.edge_source,
                   edge.edge_target,
                   edge.edge_type,
                   getattr(edge, 'label', ''),
                   getattr(edge, 'description', '')
               ])
       
       # Export documents
       documents = graph.get_nodes_by_type("document")
       if documents:
           with open(f"{output_dir}/documents.csv", 'w', newline='', encoding='utf-8') as f:
               writer = csv.writer(f)
               
               # Header
               writer.writerow(['document_id', 'name', 'description', 'url', 'type'])
               
               # Data
               for doc in documents:
                   writer.writerow([
                       doc.node_id,
                       getattr(doc, 'name', ''),
                       getattr(doc, 'description', ''),
                       getattr(doc, 'url', ''),
                       doc.get_attribute('document_type', '')
                   ])
       
       print(f"Exported graph to CSV files in {output_dir}/")
       
       # Generate export summary
       summary = {
           'total_nodes': len(graph.nodes),
           'total_edges': len(graph.edges),
           'stratigraphic_units': len(stratigraphic_nodes),
           'documents': len(documents),
           'export_files': [
               'nodes.csv',
               'edges.csv',
               'stratigraphic_units.csv',
               'documents.csv'
           ]
       }
       
       with open(f"{output_dir}/export_summary.json", 'w') as f:
           json.dump(summary, f, indent=2)
       
       return summary

   # Usage
   export_summary = export_to_csv(graph, "pompeii_export")
   print(f"Exported {export_summary['total_nodes']} nodes and {export_summary['total_edges']} edges")

Database Integration
--------------------

PostgreSQL Backend Export
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def export_to_postgresql(graph, connection_params):
       """
       Export graph to PostgreSQL database for advanced querying.
       
       Creates tables:
           - nodes: All node information
           - edges: All relationships
           - node_attributes: Flexible attribute storage
           - paradata_chains: Documentation lineages
       """
       import psycopg2
       import json
       
       # Connect to database
       conn = psycopg2.connect(**connection_params)
       cur = conn.cursor()
       
       # Create tables
       cur.execute("""
           CREATE TABLE IF NOT EXISTS nodes (
               node_id VARCHAR(255) PRIMARY KEY,
               node_type VARCHAR(100) NOT NULL,
               name TEXT,
               description TEXT,
               attributes JSONB,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )
       """)
       
       cur.execute("""
           CREATE TABLE IF NOT EXISTS edges (
               edge_id VARCHAR(255) PRIMARY KEY,
               source_id VARCHAR(255) REFERENCES nodes(node_id),
               target_id VARCHAR(255) REFERENCES nodes(node_id),
               edge_type VARCHAR(100) NOT NULL,
               label TEXT,
               description TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )
       """)
       
       cur.execute("""
           CREATE TABLE IF NOT EXISTS paradata_chains (
               stratigraphic_node_id VARCHAR(255) REFERENCES nodes(node_id),
               property_nodes JSONB,
               combiner_nodes JSONB,
               extractor_nodes JSONB,
               document_nodes JSONB,
               chain_completeness_score INTEGER,
               updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )
       """)
       
       # Insert nodes
       for node in graph.nodes:
           attributes_json = json.dumps(getattr(node, 'attributes', {}))
           
           cur.execute("""
               INSERT INTO nodes (node_id, node_type, name, description, attributes)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (node_id) DO UPDATE SET
                   node_type = EXCLUDED.node_type,
                   name = EXCLUDED.name,
                   description = EXCLUDED.description,
                   attributes = EXCLUDED.attributes
           """, (
               node.node_id,
               node.node_type,
               getattr(node, 'name', ''),
               getattr(node, 'description', ''),
               attributes_json
           ))
       
       # Insert edges
       for edge in graph.edges:
           cur.execute("""
               INSERT INTO edges (edge_id, source_id, target_id, edge_type, label, description)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (edge_id) DO UPDATE SET
                   source_id = EXCLUDED.source_id,
                   target_id = EXCLUDED.target_id,
                   edge_type = EXCLUDED.edge_type,
                   label = EXCLUDED.label,
                   description = EXCLUDED.description
           """, (
               edge.edge_id,
               edge.edge_source,
               edge.edge_target,
               edge.edge_type,
               getattr(edge, 'label', ''),
               getattr(edge, 'description', '')
           ))
       
       # Insert paradata chains
       stratigraphic_nodes = graph.get_nodes_by_type("US")
       for node in stratigraphic_nodes:
           paradata = graph.get_complete_paradata_chain(node.node_id)
           
           # Calculate completeness score
           score = 0
           if len(paradata['properties']) > 0: score += 25
           if len(paradata['documents']) > 0: score += 25
           if len(paradata['extractors']) > 0: score += 25
           if len(paradata['combiners']) > 0: score += 25
           
           cur.execute("""
               INSERT INTO paradata_chains 
               (stratigraphic_node_id, property_nodes, combiner_nodes, extractor_nodes, document_nodes, chain_completeness_score)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (stratigraphic_node_id) DO UPDATE SET
                   property_nodes = EXCLUDED.property_nodes,
                   combiner_nodes = EXCLUDED.combiner_nodes,
                   extractor_nodes = EXCLUDED.extractor_nodes,
                   document_nodes = EXCLUDED.document_nodes,
                   chain_completeness_score = EXCLUDED.chain_completeness_score,
                   updated_at = CURRENT_TIMESTAMP
           """, (
               node.node_id,
               json.dumps([p.node_id for p in paradata['properties']]),
               json.dumps([c.node_id for c in paradata['combiners']]),
               json.dumps([e.node_id for e in paradata['extractors']]),
               json.dumps([d.node_id for d in paradata['documents']]),
               score
           ))
       
       # Create useful indexes
       cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type)")
       cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type)")
       cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id)")
       cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id)")
       cur.execute("CREATE INDEX IF NOT EXISTS idx_paradata_completeness ON paradata_chains(chain_completeness_score)")
       
       conn.commit()
       cur.close()
       conn.close()
       
       print(f"Exported to PostgreSQL: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

   # Usage
   db_params = {
       'host': 'localhost',
       'database': 'archaeology_db',
       'user': 'archaeologist',
       'password': 'password'
   }

   export_to_postgresql(graph, db_params)

This comprehensive import/export guide provides all the tools needed for data interchange and integration with external systems in s3dgraphy.
