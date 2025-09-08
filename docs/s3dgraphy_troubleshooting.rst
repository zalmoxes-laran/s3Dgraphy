Troubleshooting
===============

This section provides solutions to common issues encountered when using s3dgraphy 
for archaeological data management and graph operations.

Installation Issues
-------------------

Import Errors
~~~~~~~~~~~~~

**Problem**: ``ImportError: No module named 's3dgraphy'``

**Solutions**:

1. **Verify Installation**
   
   .. code-block:: bash
   
      pip list | grep s3dgraphy
      # Should show: s3dgraphy x.x.x

2. **Reinstall Package**
   
   .. code-block:: bash
   
      pip uninstall s3dgraphy
      pip install s3dgraphy

3. **Check Python Version**
   
   .. code-block:: bash
   
      python --version
      # s3dgraphy requires Python 3.8+

4. **Virtual Environment Issues**
   
   .. code-block:: bash
   
      # Activate correct environment
      source venv/bin/activate  # Linux/Mac
      venv\Scripts\activate     # Windows

Permission Errors
~~~~~~~~~~~~~~~~~

**Problem**: ``PermissionError: [Errno 13] Permission denied``

**Solutions**:

1. **User Installation**
   
   .. code-block:: bash
   
      pip install --user s3dgraphy

2. **Virtual Environment**
   
   .. code-block:: bash
   
      python -m venv s3d_env
      source s3d_env/bin/activate
      pip install s3dgraphy

3. **Administrator Rights** (Windows)
   
   Run command prompt as administrator

Network Issues
~~~~~~~~~~~~~~

**Problem**: ``ConnectionError`` or ``TimeoutError`` during installation

**Solutions**:

1. **Trusted Hosts**
   
   .. code-block:: bash
   
      pip install --trusted-host pypi.org --trusted-host pypi.python.org s3dgraphy

2. **Proxy Configuration**
   
   .. code-block:: bash
   
      pip install --proxy http://proxy.company.com:8080 s3dgraphy

3. **Offline Installation**
   
   Download wheel file manually and install locally:
   
   .. code-block:: bash
   
      pip install s3dgraphy-1.0.0-py3-none-any.whl

Graph Management Issues
-----------------------

Duplicate Nodes or Edges
~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem**: Nodes or edges are duplicated during import or creation

**Symptoms**:
   - Multiple nodes with same ID
   - Redundant relationships
   - Inconsistent graph state

**Solutions**:

1. **Check for Unique IDs**
   
   .. code-block:: python
   
      # Verify node ID uniqueness before adding
      if graph.find_node_by_id("US001") is None:
          graph.add_node(new_node)
      else:
          print(f"Node US001 already exists")

2. **Use Overwrite Parameter**
   
   .. code-block:: python
   
      # Overwrite existing nodes
      graph.add_node(node, overwrite=True)

3. **Validate Graph Integrity**
   
   .. code-block:: python
   
      from s3dgraphy.validators import GraphValidator
      
      validator = GraphValidator()
      issues = validator.find_duplicates(graph)
      
      for issue in issues:
          print(f"Duplicate found: {issue}")

4. **Clean Duplicates**
   
   .. code-block:: python
   
      # Remove duplicate nodes
      graph.remove_duplicate_nodes()
      
      # Remove duplicate edges  
      graph.remove_duplicate_edges()

Missing GeoPositionNode
~~~~~~~~~~~~~~~~~~~~~~~

**Problem**: Exported JSON lacks ``geo_position`` data

**Symptoms**:
   - Empty ``geo_position`` object in JSON export
   - Missing spatial reference information
   - Import/export warnings about missing geographic data

**Solutions**:

1. **Add GeoPositionNode During Import**
   
   .. code-block:: python
   
      from s3dgraphy.nodes import GeoPositionNode
      
      # Create geo position node if missing
      if not graph.has_geo_position():
          geo_node = GeoPositionNode("geo_" + graph.graph_id)
          geo_node.set_attribute("epsg", 32633)
          geo_node.set_attribute("shift_x", 0.0)
          geo_node.set_attribute("shift_y", 0.0) 
          geo_node.set_attribute("shift_z", 0.0)
          graph.add_node(geo_node)

2. **Verify Geographic Data**
   
   .. code-block:: python
   
      # Check if geographic data exists
      geo_nodes = graph.get_nodes_by_type("geo_position")
      
      if not geo_nodes:
          print("Warning: No geographic reference found")
          # Add default geographic data
          graph.add_default_geo_position()

3. **Import Geographic Data from External Source**
   
   .. code-block:: python
   
      # Import from GIS file
      from s3dgraphy.importers import GISImporter
      
      gis_importer = GISImporter()
      geo_data = gis_importer.extract_reference_system("site.shp")
      graph.set_geo_position(geo_data)

Incorrect Epoch Data
~~~~~~~~~~~~~~~~~~~~

**Problem**: Epochs have incorrect, missing, or inconsistent temporal data

**Symptoms**:
   - Epochs with inverted start/end dates
   - Missing temporal ranges
   - Inconsistent color schemes
   - Export validation failures

**Solutions**:

1. **Validate Temporal Data**
   
   .. code-block:: python
   
      # Check epoch consistency
      epochs = graph.get_epochs()
      
      for epoch_name, epoch_data in epochs.items():
          if epoch_data.get("start", 0) > epoch_data.get("end", 0):
              print(f"Warning: Epoch {epoch_name} has inverted dates")
              
          if "color" not in epoch_data:
              print(f"Warning: Epoch {epoch_name} missing color")

2. **Fix Temporal Ranges**
   
   .. code-block:: python
   
      # Correct epoch data
      graph.update_epoch("Roman", {
          "start": -27,   # 27 BCE
          "end": 476,     # 476 CE  
          "color": "#CC6600",
          "min": 1200.5,  # Relative height minimum
          "max": 1250.8   # Relative height maximum
      })

3. **Import Standard Chronologies**
   
   .. code-block:: python
   
      # Load standard archaeological periods
      from s3dgraphy.data import StandardChronologies
      
      chronology = StandardChronologies.get_mediterranean_periods()
      graph.import_epochs(chronology)

4. **Validate Against Known Sequences**
   
   .. code-block:: python
   
      # Cross-check with established chronologies
      validator = GraphValidator()
      temporal_issues = validator.validate_chronology(graph)
      
      for issue in temporal_issues:
          print(f"Chronological issue: {issue}")

Export and Import Issues
-------------------------

Export Failures
~~~~~~~~~~~~~~~~

**Problem**: JSON export process fails or generates invalid JSON

**Symptoms**:
   - Export operation crashes
   - Generated JSON is malformed
   - Missing data in exported files
   - Large file size issues

**Solutions**:

1. **Validate Before Export**
   
   .. code-block:: python
   
      from s3dgraphy.validators import ExportValidator
      
      validator = ExportValidator()
      result = validator.validate_graph_for_export(graph)
      
      if not result.is_valid:
          print("Export validation failed:")
          for error in result.errors:
              print(f"  - {error}")
          
          # Fix issues before export
          graph = validator.fix_common_issues(graph)

2. **Handle Large Graphs**
   
   .. code-block:: python
   
      # Use streaming export for large datasets
      from s3dgraphy.exporters import StreamingJSONExporter
      
      exporter = StreamingJSONExporter()
      exporter.export_large_graph(
          graph,
          "large_export.json",
          chunk_size=1000
      )

3. **Debug Export Process**
   
   .. code-block:: python
   
      # Enable debug logging
      import logging
      logging.basicConfig(level=logging.DEBUG)
      
      # Export with error handling
      try:
          exporter.export_graph(graph, "debug_export.json")
      except Exception as e:
          print(f"Export error: {e}")
          
          # Inspect problematic data
          problematic_nodes = exporter.get_problematic_nodes()
          for node in problematic_nodes:
              print(f"Issue with node: {node.node_id}")

4. **Partial Export Recovery**
   
   .. code-block:: python
   
      # Export valid portions only
      try:
          exporter.export_graph(graph, "full_export.json")
      except ExportError:
          # Fall back to partial export
          partial_graph = graph.extract_valid_subgraph()
          exporter.export_graph(partial_graph, "partial_export.json")

GraphML Import Issues
~~~~~~~~~~~~~~~~~~~~~

**Problem**: GraphML files fail to import or import with missing data

**Symptoms**:
   - Import operation fails with parsing errors
   - Missing nodes or edges after import
   - Incorrect node/edge attributes
   - Type information lost

**Solutions**:

1. **Validate GraphML Structure**
   
   .. code-block:: python
   
      from s3dgraphy.validators import GraphMLValidator
      
      validator = GraphMLValidator()
      validation_result = validator.validate_file("data.graphml")
      
      if not validation_result.is_valid:
          print("GraphML validation errors:")
          for error in validation_result.errors:
              print(f"  - {error}")

2. **Handle Encoding Issues**
   
   .. code-block:: python
   
      # Try different encodings
      encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
      
      for encoding in encodings:
          try:
              graph = importer.import_from_file(
                  "data.graphml", 
                  encoding=encoding
              )
              print(f"Successfully imported with {encoding} encoding")
              break
          except UnicodeDecodeError:
              continue

3. **Map Unknown Node Types**
   
   .. code-block:: python
   
      # Provide type mapping for unknown node types
      type_mapping = {
          "layer": "US",
          "feature": "US", 
          "artifact": "SF",
          "sample": "SF",
          "photo": "document",
          "drawing": "document"
      }
      
      graph = importer.import_from_file(
          "legacy_data.graphml",
          node_type_mapping=type_mapping
      )

4. **Handle Malformed GraphML**
   
   .. code-block:: python
   
      # Robust import with error recovery
      graph = importer.import_with_recovery(
          "problematic.graphml",
          skip_invalid_nodes=True,
          skip_invalid_edges=True,
          report_issues=True
      )

CIDOC-CRM Mapping Errors
~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem**: Graph elements do not correctly map to CIDOC-CRM concepts

**Symptoms**:
   - Export validation warnings about unmapped relationships
   - Incorrect semantic meaning in exported data
   - Integration issues with CIDOC-CRM compliant systems

**Solutions**:

1. **Review Standard Mappings**
   
   .. code-block:: python
   
      from s3dgraphy.mappings import CIDOCMapping
      
      # Check available mappings
      mapping = CIDOCMapping()
      available_types = mapping.get_supported_edge_types()
      
      print("Supported edge types:")
      for edge_type in available_types:
          cidoc_property = mapping.get_cidoc_property(edge_type)
          print(f"  {edge_type} -> {cidoc_property}")

2. **Extend Mappings for Custom Types**
   
   .. code-block:: python
   
      # Add custom CIDOC mappings
      mapping.register_custom_mapping(
          edge_type="sample_analysis",
          cidoc_property="P33_used_specific_technique",
          description="Analytical relationship between sample and method"
      )

3. **Validate Semantic Consistency**
   
   .. code-block:: python
   
      # Check for semantic inconsistencies
      semantic_validator = SemanticValidator()
      issues = semantic_validator.validate_cidoc_compliance(graph)
      
      for issue in issues:
          print(f"Semantic issue: {issue.description}")
          print(f"Suggested fix: {issue.suggestion}")

4. **Update to Standard Vocabularies**
   
   .. code-block:: python
   
      # Align with Getty AAT or other controlled vocabularies
      from s3dgraphy.vocabularies import GettyAAT
      
      getty = GettyAAT()
      
      # Update material terms
      for node in graph.get_nodes_by_type("US"):
          material = node.get_attribute("material")
          if material:
              aat_term = getty.find_preferred_term(material)
              if aat_term:
                  node.set_attribute("material_aat", aat_term.uri)

Performance Issues
------------------

Slow Graph Operations
~~~~~~~~~~~~~~~~~~~~~

**Problem**: Graph operations are slower than expected

**Symptoms**:
   - Long load times for large graphs
   - Slow search and query operations
   - Memory usage warnings
   - UI freezing during operations

**Solutions**:

1. **Enable Graph Indexing**
   
   .. code-block:: python
   
      # Create indexes for frequent searches
      graph.create_index("node_type")
      graph.create_index("attributes.material")
      graph.create_index("edge_type")

2. **Use Batch Operations**
   
   .. code-block:: python
   
      # Instead of individual additions
      for i in range(1000):
          graph.add_node(nodes[i])  # Slow
      
      # Use batch addition
      graph.add_nodes_batch(nodes)  # Fast

3. **Optimize Memory Usage**
   
   .. code-block:: python
   
      # Enable lazy loading
      graph.enable_lazy_loading()
      
      # Configure memory limits
      graph.set_memory_limit("2GB")
      
      # Use memory profiling
      from s3dgraphy.profiling import MemoryProfiler
      
      profiler = MemoryProfiler()
      with profiler.profile():
          # Your operations here
          graph.process_large_dataset()
      
      profiler.report()

4. **Database Backend for Large Graphs**
   
   .. code-block:: python
   
      # Switch to database backend for very large graphs
      from s3dgraphy.backends import PostgreSQLBackend
      
      backend = PostgreSQLBackend(
          host="localhost",
          database="archaeological_graphs"
      )
      
      graph = Graph("LargeSite", backend=backend)

Memory Issues
~~~~~~~~~~~~~

**Problem**: High memory usage or out-of-memory errors

**Solutions**:

1. **Monitor Memory Usage**
   
   .. code-block:: python
   
      import psutil
      
      def check_memory():
          process = psutil.Process()
          memory_mb = process.memory_info().rss / 1024 / 1024
          print(f"Memory usage: {memory_mb:.1f} MB")
      
      check_memory()
      # Perform operations
      check_memory()

2. **Use Memory-Efficient Data Structures**
   
   .. code-block:: python
   
      # Enable memory optimization
      graph.optimize_for_memory()
      
      # Use compressed attributes for large text fields
      node.set_attribute("description", "...", compress=True)

3. **Implement Garbage Collection**
   
   .. code-block:: python
   
      import gc
      
      # Force garbage collection after large operations
      graph.process_large_import()
      gc.collect()

Integration Issues
------------------

Blender Integration Problems
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem**: Issues with EMtools integration or 3D visualization

**Solutions**:

1. **Verify EMtools Installation**
   
   Check that EMtools extension is properly installed in Blender

2. **Check Data Compatibility**
   
   .. code-block:: python
   
      # Validate graph for Blender export
      from s3dgraphy.validators import BlenderValidator
      
      validator = BlenderValidator()
      compatibility = validator.check_blender_compatibility(graph)
      
      if not compatibility.is_compatible:
          print("Blender compatibility issues:")
          for issue in compatibility.issues:
              print(f"  - {issue}")

3. **Update Export Format**
   
   .. code-block:: python
   
      # Export in EMtools-compatible format
      from s3dgraphy.exporters import EMToolsExporter
      
      exporter = EMToolsExporter()
      exporter.export_for_emtools(graph, "blender_export.json")

Database Integration Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem**: Issues connecting to or synchronizing with external databases

**Solutions**:

1. **Test Database Connection**
   
   .. code-block:: python
   
      from s3dgraphy.database import DatabaseConnector
      
      connector = DatabaseConnector(
          type="postgresql",
          host="localhost",
          database="archaeology"
      )
      
      if connector.test_connection():
          print("Database connection successful")
      else:
          print("Connection failed - check credentials and network")

2. **Handle Schema Mismatches**
   
   .. code-block:: python
   
      # Map s3dgraphy schema to database schema
      schema_mapper = DatabaseSchemaMapper()
      schema_mapper.map_node_types({
          "US": "stratigraphic_units",
          "SF": "special_finds",
          "document": "documentation"
      })

Getting Help
------------

Community Support
~~~~~~~~~~~~~~~~~

* **GitHub Issues**: https://github.com/zalmoxes-laran/s3dgraphy/issues
* **Telegram Group**: https://t.me/UserGroupEM
* **Facebook Group**: https://www.facebook.com/groups/extendedmatrix

Documentation Resources
~~~~~~~~~~~~~~~~~~~~~~~

* **API Reference**: Complete function documentation
* **Examples Repository**: Real-world usage examples  
* **Video Tutorials**: Step-by-step video guides
* **FAQ**: Frequently asked questions

Professional Support
~~~~~~~~~~~~~~~~~~~~

For institutional or commercial support:

* **Email**: emanuel.demetrescu@cnr.it
* **Extended Matrix Website**: https://www.extendedmatrix.org
* **Consulting Services**: Available for large projects

Reporting Bugs
~~~~~~~~~~~~~~

When reporting issues, please include:

1. **Version Information**
   
   .. code-block:: python
   
      import s3dgraphy
      print(f"s3dgraphy version: {s3dgraphy.__version__}")
      print(f"Python version: {sys.version}")

2. **Minimal Reproduction Case**
   
   Provide the smallest possible code example that reproduces the issue

3. **Error Messages**
   
   Include complete error messages and stack traces

4. **System Information**
   
   Operating system, Python environment, and relevant dependencies

5. **Expected vs. Actual Behavior**
   
   Clear description of what should happen vs. what actually happens