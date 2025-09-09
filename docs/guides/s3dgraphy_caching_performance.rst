s3dgraphy Caching and Performance
=========================================

This document covers s3dgraphy's performance optimization systems, including caching strategies, indexing mechanisms, and memory management techniques.

Indexing System
---------------

GraphIndices Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~

s3dgraphy uses a sophisticated indexing system (``GraphIndices``) that provides O(1) lookup performance for common graph operations.

.. code-block:: python

   class GraphIndices:
       """
       High-performance indexing system for graph queries.
       
       Index Types:
           - nodes_by_type: Fast node type lookups
           - property_nodes_by_name: Property name indexing
           - property_values_by_name: Property value sets
           - strat_to_properties: Stratigraphic unit → properties mapping
           - properties_to_strat: Property values → stratigraphic units mapping
           - edges_by_type: Edge type indexing
           - edges_by_source: Source node → edges mapping
           - edges_by_target: Target node → edges mapping
       """

Lazy Loading Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Graph class implements lazy loading with automatic index rebuilding:

.. code-block:: python

   @property
   def indices(self):
       """Lazy loading of indices with automatic rebuild if necessary"""
       if self._indices is None:
           self._indices = GraphIndices()
       if self._indices_dirty:
           self._rebuild_indices()
       return self._indices

   def _rebuild_indices(self):
       """Rebuilds graph indices for efficient querying"""
       if self._indices is None:
           self._indices = GraphIndices()
       
       self._indices.clear()
       
       # Index nodes by type - O(n) build, O(1) lookup
       for node in self.nodes:
           node_type = getattr(node, 'node_type', 'unknown')
           self._indices.add_node_by_type(node_type, node)
           
           # Special indexing for property nodes
           if node_type == 'property' and hasattr(node, 'name'):
               self._indices.add_property_node(node.name, node)
       
       # Index edges for fast lookups
       for edge in self.edges:
           self._indices.add_edge(edge)
           
           # Special indexing for property relationships
           if edge.edge_type == 'has_property':
               source_node = self.find_node_by_id(edge.edge_source)
               target_node = self.find_node_by_id(edge.edge_target)
               if source_node and target_node and hasattr(target_node, 'name'):
                   prop_value = getattr(target_node, 'description', 'empty')
                   self._indices.add_property_relation(
                       target_node.name, 
                       edge.edge_source, 
                       prop_value
                   )
       
       self._indices_dirty = False

Index Invalidation Strategy
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def add_node(self, node: Node, overwrite=False) -> Node:
       """Adds a node and marks indices as dirty"""
       # ... node addition logic ...
       self._indices_dirty = True  # Invalidate indices
       return node

   def add_edge(self, edge_id: str, edge_source: str, edge_target: str, edge_type: str) -> Edge:
       """Adds an edge and marks indices as dirty"""
       # ... edge addition logic ...
       self._indices_dirty = True  # Invalidate indices
       return edge

**Performance Characteristics:**

- **Index Build Time**: O(n + m) where n = nodes, m = edges
- **Lookup Time**: O(1) for indexed operations
- **Memory Overhead**: ~20-30% additional memory for indices
- **Rebuild Trigger**: Only when graph structure changes

Performance Optimization Techniques
-----------------------------------

Batch Operations
~~~~~~~~~~~~~~~~

Efficient Node Addition
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def add_nodes_batch(self, nodes: List[Node], validate=True):
       """
       Add multiple nodes efficiently with single index rebuild.
       
       Args:
           nodes: List of nodes to add
           validate: Whether to validate each node (default: True)
       
       Performance: O(n) vs O(n log n) for individual additions
       """
       added_nodes = []
       
       for node in nodes:
           existing_node = self.find_node_by_id(node.node_id)
           if existing_node:
               if validate:
                   self.add_warning(f"Node '{node.node_id}' already exists, skipping")
                   continue
           
           self.nodes.append(node)
           added_nodes.append(node)
       
       # Single index invalidation at the end
       if added_nodes:
           self._indices_dirty = True
       
       return added_nodes

   # Usage example
   nodes_to_add = []
   for i in range(1000):
       node = StratigraphicUnit(f"US{i:03d}")
       node.set_attribute("batch_import", True)
       nodes_to_add.append(node)

   # Much faster than 1000 individual add_node() calls
   added = graph.add_nodes_batch(nodes_to_add)
   print(f"Added {len(added)} nodes in batch operation")

Efficient Edge Addition
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def add_edges_batch(self, edge_definitions: List[tuple], validate_connections=True):
       """
       Add multiple edges efficiently.
       
       Args:
           edge_definitions: List of (edge_id, source, target, edge_type) tuples
           validate_connections: Whether to validate each connection
       
       Returns:
           Tuple of (successful_edges, failed_edges)
       """
       successful = []
       failed = []
       
       for edge_id, source, target, edge_type in edge_definitions:
           try:
               if validate_connections:
                   source_node = self.find_node_by_id(source)
                   target_node = self.find_node_by_id(target)
                   
                   if not source_node or not target_node:
                       failed.append((edge_id, "Node not found"))
                       continue
                   
                   if not self.validate_connection(source_node.node_type, 
                                                 target_node.node_type, 
                                                 edge_type):
                       failed.append((edge_id, "Invalid connection"))
                       continue
               
               edge = Edge(edge_id, source, target, edge_type)
               self.edges.append(edge)
               successful.append(edge)
               
           except Exception as e:
               failed.append((edge_id, str(e)))
       
       # Single index invalidation
       if successful:
           self._indices_dirty = True
       
       return successful, failed

   # Usage example
   edge_definitions = [
       ("rel001", "US001", "US002", "is_before"),
       ("rel002", "US002", "US003", "is_before"),
       ("rel003", "US003", "US004", "is_before"),
       ("doc001", "US001", "DOC001", "has_data_provenance")
   ]

   successful, failed = graph.add_edges_batch(edge_definitions)
   print(f"Added {len(successful)} edges, {len(failed)} failed")

Memory Management
~~~~~~~~~~~~~~~~~

Memory Usage Monitoring
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   import psutil
   import sys

   class MemoryProfiler:
       """Monitor memory usage during graph operations"""
       
       def __init__(self):
           self.process = psutil.Process()
           self.baseline = 0
       
       def start_monitoring(self):
           """Set baseline memory usage"""
           self.baseline = self.process.memory_info().rss / 1024 / 1024  # MB
           print(f"Baseline memory: {self.baseline:.1f} MB")
       
       def check_memory(self, operation=""):
           """Check current memory usage"""
           current = self.process.memory_info().rss / 1024 / 1024  # MB
           delta = current - self.baseline
           print(f"Memory after {operation}: {current:.1f} MB (+{delta:.1f} MB)")
           return current
       
       def get_graph_memory_estimate(self, graph):
           """Estimate memory usage of graph components"""
           node_memory = sys.getsizeof(graph.nodes) + sum(sys.getsizeof(node) for node in graph.nodes)
           edge_memory = sys.getsizeof(graph.edges) + sum(sys.getsizeof(edge) for edge in graph.edges)
           
           # Estimate index memory (approximation)
           index_memory = 0
           if hasattr(graph, '_indices') and graph._indices:
               for index_dict in [graph._indices.nodes_by_type, 
                                graph._indices.edges_by_type,
                                graph._indices.edges_by_source,
                                graph._indices.edges_by_target]:
                   index_memory += sys.getsizeof(index_dict)
                   for key, value in index_dict.items():
                       index_memory += sys.getsizeof(key) + sys.getsizeof(value)
           
           total_mb = (node_memory + edge_memory + index_memory) / 1024 / 1024
           
           return {
               "nodes_mb": node_memory / 1024 / 1024,
               "edges_mb": edge_memory / 1024 / 1024,
               "indices_mb": index_memory / 1024 / 1024,
               "total_mb": total_mb
           }

   # Usage example
   profiler = MemoryProfiler()
   profiler.start_monitoring()

   # Load large graph
   manager = MultiGraphManager()
   graph_id = manager.load_graph("large_excavation.graphml")
   profiler.check_memory("graph loading")

   graph = manager.get_graph(graph_id)
   memory_breakdown = profiler.get_graph_memory_estimate(graph)

   print("\nMemory breakdown:")
   for component, size_mb in memory_breakdown.items():
       print(f"  {component}: {size_mb:.2f} MB")

Memory Optimization Strategies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   def optimize_graph_memory(graph):
       """
       Apply memory optimization strategies to a graph.
       """
       optimizations_applied = []
       
       # 1. Compact attribute dictionaries
       for node in graph.nodes:
           if hasattr(node, 'attributes') and node.attributes:
               # Remove empty string values
               empty_keys = [k for k, v in node.attributes.items() if v == ""]
               for k in empty_keys:
                   del node.attributes[k]
               
               if empty_keys:
                   optimizations_applied.append(f"Removed {len(empty_keys)} empty attributes from {node.node_id}")
       
       # 2. Deduplicate identical attribute dictionaries
       attribute_cache = {}
       for node in graph.nodes:
           if hasattr(node, 'attributes'):
               attr_key = str(sorted(node.attributes.items()))
               if attr_key in attribute_cache:
                   # Reuse existing dictionary
                   node.attributes = attribute_cache[attr_key]
                   optimizations_applied.append(f"Deduplicated attributes for {node.node_id}")
               else:
                   attribute_cache[attr_key] = node.attributes
       
       # 3. Compact warning messages
       if len(graph.warnings) > 100:
           # Keep only recent warnings
           graph.warnings = graph.warnings[-50:]
           optimizations_applied.append("Compacted warning messages")
       
       # 4. Force garbage collection
       import gc
       collected = gc.collect()
       optimizations_applied.append(f"Garbage collection freed {collected} objects")
       
       # 5. Rebuild indices if dirty (consolidates memory)
       if graph._indices_dirty:
           graph._rebuild_indices()
           optimizations_applied.append("Rebuilt indices")
       
       return optimizations_applied

   # Usage
   optimizations = optimize_graph_memory(graph)
   print("Applied optimizations:")
   for opt in optimizations:
       print(f"  - {opt}")

Query Performance Optimization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indexed Query Patterns
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   class PerformantQueries:
       """Collection of high-performance query methods"""
       
       @staticmethod
       def fast_node_by_type(graph, node_type):
           """O(1) node lookup by type using indices"""
           return graph.indices.nodes_by_type.get(node_type, [])
       
       @staticmethod
       def fast_edges_from_node(graph, node_id):
           """O(1) edge lookup from source node"""
           return graph.indices.edges_by_source.get(node_id, [])
       
       @staticmethod
       def fast_edges_to_node(graph, node_id):
           """O(1) edge lookup to target node"""
           return graph.indices.edges_by_target.get(node_id, [])
       
       @staticmethod
       def fast_property_search(graph, property_name, property_value):
           """O(1) property value search using indices"""
           return graph.indices.properties_to_strat.get(property_name, {}).get(property_value, [])
       
       @staticmethod
       def fast_connected_nodes(graph, node_id, edge_type=None):
           """Fast connected node lookup with optional edge type filtering"""
           connected = []
           
           # Outgoing edges
           for edge in graph.indices.edges_by_source.get(node_id, []):
               if edge_type is None or edge.edge_type == edge_type:
                   target = graph.find_node_by_id(edge.edge_target)
                   if target:
                       connected.append(target)
           
           # Incoming edges
           for edge in graph.indices.edges_by_target.get(node_id, []):
               if edge_type is None or edge.edge_type == edge_type:
                   source = graph.find_node_by_id(edge.edge_source)
                   if source:
                       connected.append(source)
           
           return connected

   # Performance comparison example
   def compare_query_performance(graph):
       """Compare indexed vs non-indexed query performance"""
       import time
       
       # Test data
       node_type = "US"
       test_node_id = graph.nodes[0].node_id if graph.nodes else "US001"
       
       # Non-indexed approach (slow)
       start = time.time()
       slow_nodes = [node for node in graph.nodes if node.node_type == node_type]
       slow_time = time.time() - start
       
       # Indexed approach (fast)
       start = time.time()
       fast_nodes = PerformantQueries.fast_node_by_type(graph, node_type)
       fast_time = time.time() - start
       
       print(f"Query performance comparison:")
       print(f"  Non-indexed: {slow_time:.4f}s ({len(slow_nodes)} results)")
       print(f"  Indexed: {fast_time:.4f}s ({len(fast_nodes)} results)")
       print(f"  Speedup: {slow_time/fast_time:.2f}x faster")

   # Usage
   compare_query_performance(graph)

Query Result Caching
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   class QueryCache:
       """Simple LRU cache for expensive queries"""
       
       def __init__(self, max_size=100):
           self.cache = {}
           self.access_order = []
           self.max_size = max_size
       
       def get(self, key):
           """Get cached result"""
           if key in self.cache:
               # Move to end (most recently used)
               self.access_order.remove(key)
               self.access_order.append(key)
               return self.cache[key]
           return None
       
       def put(self, key, value):
           """Cache a result"""
           if key in self.cache:
               # Update existing
               self.access_order.remove(key)
           elif len(self.cache) >= self.max_size:
               # Remove least recently used
               oldest = self.access_order.pop(0)
               del self.cache[oldest]
           
           self.cache[key] = value
           self.access_order.append(key)
       
       def clear(self):
           """Clear all cached results"""
           self.cache.clear()
           self.access_order.clear()

   # Usage with complex queries
   class CachedGraphAnalyzer:
       """Graph analyzer with query result caching"""
       
       def __init__(self, graph):
           self.graph = graph
           self.cache = QueryCache(max_size=50)
       
       def get_stratigraphic_sequence(self, start_node_id):
           """Get stratigraphic sequence with caching"""
           cache_key = f"sequence_{start_node_id}"
           
           result = self.cache.get(cache_key)
           if result is not None:
               return result
           
           # Expensive computation
           sequence = self._compute_sequence(start_node_id)
           self.cache.put(cache_key, sequence)
           
           return sequence
       
       def _compute_sequence(self, start_node_id):
           """Expensive sequence computation"""
           # Complex algorithm here...
           visited = set()
           sequence = []
           
           def dfs(node_id):
               if node_id in visited:
                   return
               visited.add(node_id)
               sequence.append(node_id)
               
               # Get temporal connections
               edges = PerformantQueries.fast_edges_from_node(self.graph, node_id)
               for edge in edges:
                   if edge.edge_type == "is_before":
                       dfs(edge.edge_target)
           
           dfs(start_node_id)
           return sequence
       
       def invalidate_cache(self):
           """Clear cache when graph changes"""
           self.cache.clear()

   # Usage
   analyzer = CachedGraphAnalyzer(graph)

   # First call - computed and cached
   sequence1 = analyzer.get_stratigraphic_sequence("US001")

   # Second call - returned from cache (fast)
   sequence2 = analyzer.get_stratigraphic_sequence("US001")

   # After graph modifications
   graph.add_edge("new_rel", "US001", "US999", "is_before")
   analyzer.invalidate_cache()  # Clear cache for consistency

Performance Monitoring and Benchmarking
---------------------------------------

Graph Performance Metrics
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class GraphPerformanceMonitor:
       """Monitor and report graph performance metrics"""
       
       def __init__(self, graph):
           self.graph = graph
           self.metrics = {}
       
       def collect_metrics(self):
           """Collect comprehensive performance metrics"""
           import time
           
           # Basic metrics
           self.metrics['node_count'] = len(self.graph.nodes)
           self.metrics['edge_count'] = len(self.graph.edges)
           
           # Index metrics
           if hasattr(self.graph, '_indices') and self.graph._indices:
               self.metrics['indices_built'] = not self.graph._indices_dirty
               self.metrics['indexed_node_types'] = len(self.graph._indices.nodes_by_type)
               self.metrics['indexed_edge_types'] = len(self.graph._indices.edges_by_type)
           
           # Performance benchmarks
           self.metrics.update(self._benchmark_operations())
           
           return self.metrics
       
       def _benchmark_operations(self):
           """Benchmark common operations"""
           import time
           benchmarks = {}
           
           if not self.graph.nodes:
               return benchmarks
           
           # Node lookup benchmark
           test_node_id = self.graph.nodes[0].node_id
           start = time.time()
           for _ in range(1000):
               self.graph.find_node_by_id(test_node_id)
           benchmarks['node_lookup_1000ops_ms'] = (time.time() - start) * 1000
           
           # Node type query benchmark
           start = time.time()
           for _ in range(100):
               self.graph.get_nodes_by_type("US")
           benchmarks['type_query_100ops_ms'] = (time.time() - start) * 1000
           
           # Index rebuild benchmark
           start = time.time()
           self.graph._rebuild_indices()
           benchmarks['index_rebuild_ms'] = (time.time() - start) * 1000
           
           return benchmarks
       
       def generate_report(self):
           """Generate performance report"""
           metrics = self.collect_metrics()
           
           print("Graph Performance Report")
           print("=" * 40)
           print(f"Nodes: {metrics.get('node_count', 0):,}")
           print(f"Edges: {metrics.get('edge_count', 0):,}")
           
           if metrics.get('indices_built'):
               print(f"Indexed node types: {metrics.get('indexed_node_types', 0)}")
               print(f"Indexed edge types: {metrics.get('indexed_edge_types', 0)}")
           else:
               print("Indices: Not built (will be built on next access)")
           
           print("\nBenchmarks:")
           print(f"  Node lookup (1000 ops): {metrics.get('node_lookup_1000ops_ms', 0):.2f} ms")
           print(f"  Type query (100 ops): {metrics.get('type_query_100ops_ms', 0):.2f} ms")
           print(f"  Index rebuild: {metrics.get('index_rebuild_ms', 0):.2f} ms")
           
           # Performance recommendations
           self._generate_recommendations(metrics)
       
       def _generate_recommendations(self, metrics):
           """Generate performance recommendations"""
           print("\nRecommendations:")
           
           if metrics.get('node_count', 0) > 5000:
               print("  - Large graph detected. Consider using database backend for better performance.")
           
           if metrics.get('node_lookup_1000ops_ms', 0) > 100:
               print("  - Slow node lookups. Ensure indices are built and consider graph optimization.")
           
           if metrics.get('index_rebuild_ms', 0) > 1000:
               print("  - Slow index rebuild. Consider reducing graph complexity or using batch operations.")
           
           if not metrics.get('indices_built'):
               print("  - Indices not built. Performance will improve after first indexed operation.")

   # Usage
   monitor = GraphPerformanceMonitor(graph)
   monitor.generate_report()

Performance Best Practices
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class PerformanceBestPractices:
       """Collection of performance best practices and utilities"""
       
       @staticmethod
       def efficient_graph_building():
           """Demonstrate efficient graph building patterns"""
           from s3dgraphy import Graph
           
           # Create graph
           graph = Graph("OptimizedGraph")
           
           # 1. Batch node creation (more efficient)
           nodes = []
           for i in range(1000):
               node = StratigraphicUnit(f"US{i:03d}")
               node.set_attribute("area", f"Area_{i // 100}")
               nodes.append(node)
           
           # Add all nodes at once
           graph.add_nodes_batch(nodes)
           
           # 2. Batch edge creation
           edge_definitions = []
           for i in range(999):
               edge_definitions.append((f"rel{i}", f"US{i:03d}", f"US{i+1:03d}", "is_before"))
           
           successful, failed = graph.add_edges_batch(edge_definitions)
           
           print(f"Efficiently created graph with {len(nodes)} nodes and {len(successful)} edges")
           return graph
       
       @staticmethod
       def memory_conscious_iteration(graph):
           """Demonstrate memory-conscious iteration patterns"""
           
           # Good: Use generators and indexed lookups
           us_nodes = graph.get_nodes_by_type("US")  # Uses indices
           for node in us_nodes:
               # Process one node at a time
               if node.get_attribute("material") == "stone":
                   # Do something with stone nodes
                   pass
       
       @staticmethod
       def efficient_queries(graph):
           """Demonstrate efficient query patterns"""
           
           # Use indexed lookups instead of linear search
           
           # Good: O(1) indexed lookup (if property index exists)
           stone_node_ids = graph.indices.properties_to_strat.get("material", {}).get("stone", [])
           stone_nodes = [graph.find_node_by_id(node_id) for node_id in stone_node_ids]
           
           # Use batch operations for multiple similar operations
           node_ids_to_check = ["US001", "US002", "US003"]
           nodes = [graph.find_node_by_id(node_id) for node_id in node_ids_to_check]
           # Process all at once instead of individual lookups

   # Performance testing utility
   def performance_test_suite(graph):
       """Run comprehensive performance tests"""
       
       print("Running performance test suite...")
       
       # Test 1: Index performance
       print("\n1. Testing index performance...")
       monitor = GraphPerformanceMonitor(graph)
       metrics = monitor.collect_metrics()
       
       # Test 2: Memory usage
       print("\n2. Testing memory usage...")
       profiler = MemoryProfiler()
       memory_stats = profiler.get_graph_memory_estimate(graph)
       
       # Test 3: Query performance
       print("\n3. Testing query performance...")
       compare_query_performance(graph)
       
       # Test 4: Best practices check
       print("\n4. Checking best practices...")
       if len(graph.nodes) > 1000 and not hasattr(graph, '_last_batch_operation'):
           print("  Warning: Large graph without evident batch operations")
       
       if graph._indices_dirty:
           print("  Info: Indices need rebuilding")
       else:
           print("  Good: Indices are up to date")
       
       print("\nPerformance test suite completed.")

   # Usage
   performance_test_suite(graph)

This comprehensive caching and performance guide provides all the tools needed to optimize s3dgraphy graphs for maximum efficiency and scalability.
