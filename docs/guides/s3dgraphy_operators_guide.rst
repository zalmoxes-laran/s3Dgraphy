s3dgraphy Operators Guide
===========================

This document provides comprehensive guidance on s3dgraphy's operators, algorithms, and advanced graph manipulation methods.

Graph Operations
----------------

Node Operations
~~~~~~~~~~~~~~~

Adding and Managing Nodes
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Basic node addition
   node = StratigraphicUnit("US001")
   graph.add_node(node)

   # Batch node addition (recommended for performance)
   nodes = []
   for i in range(100):
       node = StratigraphicUnit(f"US{i:03d}")
       node.set_attribute("area", "Area_A")
       nodes.append(node)

   # Use batch operation for better performance
   graph.add_nodes_batch(nodes)  # More efficient than individual add_node calls

Node Queries and Filtering
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Find specific nodes
   node = graph.find_node_by_id("US001")
   if node:
       print(f"Found: {node.name}")

   # Get nodes by type (uses indexed lookup)
   stratigraphic_units = graph.get_nodes_by_type("US")
   special_finds = graph.get_nodes_by_type("SF")
   documents = graph.get_nodes_by_type("document")

   # Advanced filtering with attributes
   pottery_units = [node for node in stratigraphic_units 
                   if node.get_attribute("material") == "pottery"]

   # Filter by multiple criteria
   roman_pottery = [node for node in stratigraphic_units
                   if (node.get_attribute("material") == "pottery" and 
                       node.get_attribute("period") == "Roman")]

   # Use indices for efficient property-based queries
   material_index = graph.indices.properties_to_strat.get("material", {})
   pottery_nodes = material_index.get("pottery", [])

Node Attribute Management
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Set multiple attributes efficiently
   attributes = {
       "material": "limestone",
       "technique": "opus_reticulatum", 
       "dating": "1st century AD",
       "preservation": "good"
   }

   for key, value in attributes.items():
       node.set_attribute(key, value)

   # Batch attribute setting (custom method)
   def set_attributes_batch(node, attributes_dict):
       """Efficiently set multiple attributes"""
       node.attributes.update(attributes_dict)

   set_attributes_batch(node, attributes)

   # Conditional attribute updates
   def update_dating_if_empty(node, new_dating):
       """Update dating only if not already set"""
       if not node.get_attribute("dating"):
           node.set_attribute("dating", new_dating)
           return True
       return False

Edge Operations
~~~~~~~~~~~~~~~

Creating and Validating Relationships
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Basic edge creation with validation
   try:
       edge = graph.add_edge("rel001", "US002", "US001", "is_after")
       print(f"Added relationship: {edge}")
   except ValueError as e:
       print(f"Connection invalid: {e}")

   # Validate connection before creating
   source_node = graph.find_node_by_id("US002")
   target_node = graph.find_node_by_id("US001")

   if Graph.validate_connection(source_node.node_type, target_node.node_type, "is_after"):
       graph.add_edge("rel001", "US002", "US001", "is_after")
   else:
       print("Connection not allowed by schema rules")

   # Batch edge creation
   relationships = [
       ("rel001", "US001", "US002", "is_after"),
       ("rel002", "US002", "US003", "is_after"),
       ("rel003", "US003", "US004", "is_after"),
       ("rel004", "SF001", "US002", "extracted_from")
   ]

   for edge_id, source, target, edge_type in relationships:
       try:
           graph.add_edge(edge_id, source, target, edge_type)
       except ValueError as e:
           graph.add_warning(f"Failed to add edge {edge_id}: {e}")

Edge Queries and Analysis
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Get edges by type (uses indexed lookup)
   temporal_edges = graph.indices.edges_by_type.get("is_after", [])
   documentation_edges = graph.indices.edges_by_type.get("has_data_provenance", [])

   # Find all edges from a specific node
   source_edges = graph.indices.edges_by_source.get("US001", [])
   target_edges = graph.indices.edges_by_target.get("US001", [])

   # Find connected nodes
   def get_connected_nodes(graph, node_id, edge_type=None):
       """Get all nodes connected to a given node"""
       connected = []
       
       # Outgoing connections
       for edge in graph.indices.edges_by_source.get(node_id, []):
           if edge_type is None or edge.edge_type == edge_type:
               target = graph.find_node_by_id(edge.edge_target)
               if target:
                   connected.append(target)
       
       # Incoming connections  
       for edge in graph.indices.edges_by_target.get(node_id, []):
           if edge_type is None or edge.edge_type == edge_type:
               source = graph.find_node_by_id(edge.edge_source)
               if source:
                   connected.append(source)
       
       return connected

   # Usage examples
   all_connected = get_connected_nodes(graph, "US001")
   after_relations = get_connected_nodes(graph, "US001", "is_after")

Advanced Graph Analysis
-----------------------

Stratigraphic Sequence Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def build_stratigraphic_sequence(graph):
       """Build the complete stratigraphic sequence from temporal relationships"""

       # Get all temporal edges
       temporal_edges = graph.indices.edges_by_type.get("is_after", [])

       # Build adjacency list
       after_map = {}   # node -> nodes that come after it (more ancient)
       before_map = {}  # node -> nodes that come before it (more recent)

       for edge in temporal_edges:
           source = edge.edge_source  # More recent unit
           target = edge.edge_target  # More ancient unit

           if source not in after_map:
               after_map[source] = []
           before_map[target].append(source)
           
           if source not in after_map:
               after_map[source] = []
           after_map[source].append(target)
       
       # Find root nodes (no predecessors)
       all_nodes = set()
       for edge in temporal_edges:
           all_nodes.add(edge.edge_source)
           all_nodes.add(edge.edge_target)
       
       root_nodes = [node for node in all_nodes if node not in before_map]
       
       return {
           "before_map": before_map,
           "after_map": after_map, 
           "root_nodes": root_nodes,
           "all_nodes": list(all_nodes)
       }

   # Usage
   sequence = build_stratigraphic_sequence(graph)
   print(f"Found {len(sequence['root_nodes'])} earliest units")
   print(f"Total units in sequence: {len(sequence['all_nodes'])}")

Topological Sorting for Chronology
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def topological_sort_stratigraphy(graph):
       """
       Perform topological sort on stratigraphic relationships to get chronological order.
       """
       from collections import defaultdict, deque
       
       # Build graph of temporal relationships
       in_degree = defaultdict(int)
       adj_list = defaultdict(list)
       nodes = set()
       
       temporal_edges = graph.indices.edges_by_type.get("is_before", [])
       
       for edge in temporal_edges:
           source = edge.edge_source
           target = edge.edge_target
           
           adj_list[source].append(target)
           in_degree[target] += 1
           nodes.add(source)
           nodes.add(target)
       
       # Initialize all nodes with in_degree 0 if not already set
       for node in nodes:
           if node not in in_degree:
               in_degree[node] = 0
       
       # Find nodes with no dependencies (earliest)
       queue = deque([node for node in nodes if in_degree[node] == 0])
       result = []
       
       while queue:
           current = queue.popleft()
           result.append(current)
           
           # Reduce in_degree for adjacent nodes
           for neighbor in adj_list[current]:
               in_degree[neighbor] -= 1
               if in_degree[neighbor] == 0:
                   queue.append(neighbor)
       
       # Check for cycles
       if len(result) != len(nodes):
           remaining = [node for node in nodes if node not in result]
           return None, f"Circular dependency detected in nodes: {remaining}"
       
       return result, None

   # Usage
   chronological_order, error = topological_sort_stratigraphy(graph)
   if error:
       print(f"Error in chronology: {error}")
   else:
       print("Chronological sequence (earliest to latest):")
       for i, node_id in enumerate(chronological_order):
           node = graph.find_node_by_id(node_id)
           print(f"  {i+1}. {node_id}: {node.name if node else 'Unknown'}")

Paradata Chain Analysis
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def analyze_documentation_completeness(graph):
       """
       Analyze completeness of documentation chains for all stratigraphic nodes.
       """
       stratigraphic_nodes = graph.get_nodes_by_type("US")
       completeness_report = {}
       
       for node in stratigraphic_nodes:
           paradata = graph.get_complete_paradata_chain(node.node_id)
           
           completeness_report[node.node_id] = {
               "name": node.name,
               "properties_count": len(paradata["properties"]),
               "documents_count": len(paradata["documents"]),
               "extractors_count": len(paradata["extractors"]),
               "combiners_count": len(paradata["combiners"]),
               "has_material": any(p.name == "material" for p in paradata["properties"]),
               "has_dating": any(p.name == "dating" for p in paradata["properties"]),
               "has_documentation": len(paradata["documents"]) > 0,
               "completeness_score": 0
           }
           
           # Calculate completeness score
           report = completeness_report[node.node_id]
           score = 0
           if report["has_material"]: score += 25
           if report["has_dating"]: score += 25  
           if report["has_documentation"]: score += 25
           if report["properties_count"] >= 3: score += 25
           
           report["completeness_score"] = score
       
       return completeness_report

   # Usage and reporting
   completeness = analyze_documentation_completeness(graph)

   print("Documentation Completeness Report:")
   print("=" * 50)

   for node_id, report in sorted(completeness.items(), 
                                key=lambda x: x[1]["completeness_score"], 
                                reverse=True):
       print(f"\n{node_id}: {report['name']}")
       print(f"  Score: {report['completeness_score']}%")
       print(f"  Properties: {report['properties_count']}")
       print(f"  Documents: {report['documents_count']}")
       print(f"  Material: {'✓' if report['has_material'] else '✗'}")
       print(f"  Dating: {'✓' if report['has_dating'] else '✗'}")
       print(f"  Documentation: {'✓' if report['has_documentation'] else '✗'}")

   # Find nodes needing attention
   incomplete_nodes = [node_id for node_id, report in completeness.items() 
                      if report["completeness_score"] < 50]

   print(f"\nNodes needing documentation attention: {len(incomplete_nodes)}")
   for node_id in incomplete_nodes:
       print(f"  - {node_id}: {completeness[node_id]['name']}")

Graph Transformation Operations
-------------------------------

Node Type Conversion
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def convert_node_type(graph, node_id, new_type):
       """
       Convert a node from one type to another while preserving relationships.
       """
       node = graph.find_node_by_id(node_id)
       if not node:
           raise ValueError(f"Node {node_id} not found")
       
       # Store current attributes and relationships
       old_attributes = node.attributes.copy()
       old_name = node.name
       
       # Find all edges involving this node
       incoming_edges = [e for e in graph.edges if e.edge_target == node_id]
       outgoing_edges = [e for e in graph.edges if e.edge_source == node_id]
       
       # Remove old node
       graph.nodes.remove(node)
       
       # Create new node of different type
       if new_type == "US":
           new_node = StratigraphicUnit(node_id)
       elif new_type == "SF":
           new_node = SpecialFindUnit(node_id)
       elif new_type == "USV":
           new_node = StructuralVirtualStratigraphicUnit(node_id)
       else:
           raise ValueError(f"Unsupported conversion to type: {new_type}")
       
       # Restore attributes and name
       new_node.attributes = old_attributes
       new_node.name = old_name
       
       # Add new node
       graph.add_node(new_node)
       
       # Validate and restore relationships
       for edge in incoming_edges + outgoing_edges:
           source_node = graph.find_node_by_id(edge.edge_source)
           target_node = graph.find_node_by_id(edge.edge_target)
           
           if Graph.validate_connection(source_node.node_type, 
                                      target_node.node_type, 
                                      edge.edge_type):
               # Relationship is still valid, keep it
               continue
           else:
               # Relationship no longer valid, log warning
               graph.add_warning(f"Relationship {edge.edge_id} invalidated by type conversion")
               graph.edges.remove(edge)
       
       # Invalidate indices for rebuild
       graph._indices_dirty = True
       
       return new_node

   # Usage
   converted_node = convert_node_type(graph, "US001", "SF")
   print(f"Converted {converted_node.node_id} to type {converted_node.node_type}")

Graph Merging Operations
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def merge_graphs(target_graph, source_graph, prefix=""):
       """
       Merge one graph into another, optionally adding prefix to avoid ID conflicts.
       """
       id_mapping = {}
       
       # Add nodes with ID mapping
       for node in source_graph.nodes:
           new_id = f"{prefix}{node.node_id}" if prefix else node.node_id
           id_mapping[node.node_id] = new_id
           
           # Create new node of same type
           new_node = type(node)(new_id)
           new_node.name = node.name
           new_node.attributes = node.attributes.copy()
           
           # Check for ID conflicts
           if target_graph.find_node_by_id(new_id):
               target_graph.add_warning(f"ID conflict: {new_id} already exists")
               new_id = f"{new_id}_{len(target_graph.nodes)}"
               id_mapping[node.node_id] = new_id
               new_node.node_id = new_id
           
           target_graph.add_node(new_node)
       
       # Add edges with updated IDs
       for edge in source_graph.edges:
           new_source = id_mapping[edge.edge_source]
           new_target = id_mapping[edge.edge_target]
           new_edge_id = f"{prefix}{edge.edge_id}" if prefix else edge.edge_id
           
           try:
               target_graph.add_edge(new_edge_id, new_source, new_target, edge.edge_type)
           except ValueError as e:
               target_graph.add_warning(f"Failed to merge edge {new_edge_id}: {e}")
       
       # Merge metadata
       for key, value in source_graph.data.items():
           if key not in target_graph.data:
               target_graph.data[key] = value
       
       return id_mapping

   # Usage
   from s3dgraphy import MultiGraphManager

   manager = MultiGraphManager()
   main_graph = manager.get_graph("MainSite")
   area_graph = manager.get_graph("AreaB")

   id_mapping = merge_graphs(main_graph, area_graph, prefix="B_")
   print(f"Merged {len(area_graph.nodes)} nodes and {len(area_graph.edges)} edges")

Graph Filtering and Subgraph Extraction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def extract_subgraph(graph, node_filter=None, edge_filter=None):
       """
       Extract a subgraph based on node and edge filters.
       """
       from s3dgraphy import Graph
       
       # Create new graph for subgraph
       subgraph = Graph(f"{graph.graph_id}_filtered")
       
       # Filter nodes
       if node_filter:
           filtered_nodes = [node for node in graph.nodes if node_filter(node)]
       else:
           filtered_nodes = graph.nodes.copy()
       
       # Add filtered nodes
       node_ids = set()
       for node in filtered_nodes:
           subgraph.add_node(node)
           node_ids.add(node.node_id)
       
       # Filter edges (only between filtered nodes)
       for edge in graph.edges:
           if (edge.edge_source in node_ids and 
               edge.edge_target in node_ids):
               if not edge_filter or edge_filter(edge):
                   subgraph.add_edge(edge.edge_id, edge.edge_source, 
                                   edge.edge_target, edge.edge_type)
       
       return subgraph

   # Example filters
   def roman_period_filter(node):
       """Filter for Roman period stratigraphic units"""
       return (node.node_type in ["US", "SF"] and 
               "roman" in node.get_attribute("dating", "").lower())

   def temporal_edge_filter(edge):
       """Filter for temporal relationships only"""
       return edge.edge_type in ["is_before", "has_same_time", "changed_from"]

   # Usage
   roman_subgraph = extract_subgraph(
       graph, 
       node_filter=roman_period_filter,
       edge_filter=temporal_edge_filter
   )

   print(f"Roman period subgraph: {len(roman_subgraph.nodes)} nodes, {len(roman_subgraph.edges)} edges")

Performance Optimization Techniques
-----------------------------------

Efficient Bulk Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def bulk_attribute_update(graph, node_type, attribute_updates):
       """
       Efficiently update attributes for multiple nodes of the same type.
       """
       # Use indexed lookup for efficiency
       nodes = graph.get_nodes_by_type(node_type)
       
       updated_count = 0
       for node in nodes:
           # Apply conditional updates
           for attr_name, new_value in attribute_updates.items():
               if callable(new_value):
                   # Function-based update
                   if new_value(node):
                       updated_count += 1
               else:
                   # Direct value update
                   node.set_attribute(attr_name, new_value)
                   updated_count += 1
       
       # Invalidate indices once at the end
       graph._indices_dirty = True
       
       return updated_count

   # Usage examples
   def update_empty_dating(node):
       """Update dating for nodes without existing dating"""
       if not node.get_attribute("dating"):
           node.set_attribute("dating", "Unknown period")
           return True
       return False

   # Bulk update all US nodes
   updated = bulk_attribute_update(graph, "US", {
       "updated_date": "2024-01-15",
       "dating": update_empty_dating
   })

   print(f"Updated {updated} attributes")

Memory-Efficient Graph Traversal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def memory_efficient_dfs(graph, start_node_id, max_depth=5):
       """
       Memory-efficient depth-first search using generators.
       """
       visited = set()
       
       def dfs_generator(node_id, depth):
           if depth > max_depth or node_id in visited:
               return
           
           visited.add(node_id)
           node = graph.find_node_by_id(node_id)
           
           if node:
               yield (node, depth)
               
               # Get connected nodes using indices
               edges = graph.indices.edges_by_source.get(node_id, [])
               for edge in edges:
                   yield from dfs_generator(edge.edge_target, depth + 1)
       
       return dfs_generator(start_node_id, 0)

   # Usage - processes one node at a time, not loading all into memory
   for node, depth in memory_efficient_dfs(graph, "US001"):
       print("  " * depth + f"{node.node_id}: {node.name}")

Indexed Property Queries
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def create_property_search_index(graph):
       """
       Create optimized search indices for property-based queries.
       """
       property_index = {
           "material": {},
           "dating": {},
           "technique": {},
           "preservation": {}
       }
       
       # Build indices for common properties
       for node in graph.get_nodes_by_type("US"):
           for prop_name in property_index.keys():
               prop_value = node.get_attribute(prop_name)
               if prop_value:
                   if prop_value not in property_index[prop_name]:
                       property_index[prop_name][prop_value] = []
                   property_index[prop_name][prop_value].append(node.node_id)
       
       return property_index

   def fast_property_search(property_index, property_name, property_value):
       """
       Fast O(1) property-based search using pre-built index.
       """
       return property_index.get(property_name, {}).get(property_value, [])

   # Usage
   prop_index = create_property_search_index(graph)

   # Fast searches
   limestone_units = fast_property_search(prop_index, "material", "limestone")
   roman_units = fast_property_search(prop_index, "dating", "Roman")

   print(f"Found {len(limestone_units)} limestone units")
   print(f"Found {len(roman_units)} Roman units")

This comprehensive operators guide provides all the tools needed for advanced graph manipulation, analysis, and optimization in s3dgraphy.
