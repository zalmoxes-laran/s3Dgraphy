Quick Start Guide
=================

This guide provides practical examples to get you started with s3dgraphy for 
archaeological stratigraphic documentation and analysis.

Basic Graph Creation
--------------------

Creating Your First Archaeological Graph
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy import Graph
   from s3dgraphy.nodes import StratigraphicNode, DocumentNode
   
   # Create a new archaeological site graph
   site = Graph("Pompeii_House_VII")
   
   # Add basic site information
   site.set_metadata("name@en", "House VII Excavation")
   site.set_metadata("description@en", "2024 excavation campaign")
   site.set_metadata("project_lead", "Dr. Maria Rossi")

Adding Stratigraphic Units
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Create stratigraphic units
   floor = StratigraphicNode("US001", node_type="US")
   floor.set_attribute("description", "Mosaic floor, main atrium")
   floor.set_attribute("material", "tesserae")
   floor.set_attribute("dating", "1st century CE")
   floor.set_attribute("preservation", "excellent")
   
   wall = StratigraphicNode("US002", node_type="US") 
   wall.set_attribute("description", "North wall, frescoed")
   wall.set_attribute("material", "tuff blocks")
   wall.set_attribute("technique", "opus_reticulatum")
   
   fill = StratigraphicNode("US003", node_type="US")
   fill.set_attribute("description", "Volcanic fill, 79 CE eruption")
   fill.set_attribute("material", "pumice and ash")
   fill.set_attribute("dating", "79 CE")
   
   # Add nodes to graph
   site.add_node(floor)
   site.add_node(wall)
   site.add_node(fill)

Creating Stratigraphic Relationships
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Create temporal relationships
   # Fill covers the floor (fill is later than floor)
   site.add_edge("rel_001", "US003", "US001", "line")
   
   # Wall and floor are contemporary (built together)
   site.add_edge("rel_002", "US002", "US001", "double_line")
   
   print(f"Site graph contains {len(site.nodes)} units and {len(site.edges)} relationships")

Working with Documentation
--------------------------

Adding Documentation Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.nodes import DocumentNode, ExtractorNode
   
   # Add photographic documentation
   photo1 = DocumentNode("DOC001", "floor_overview.jpg")
   photo1.set_attribute("type", "photograph")
   photo1.set_attribute("photographer", "L. Bianchi")
   photo1.set_attribute("date", "2024-06-15")
   photo1.set_attribute("resolution", "6000x4000")
   
   # Add technical drawing
   plan = DocumentNode("DOC002", "wall_elevation.dwg")
   plan.set_attribute("type", "technical_drawing")
   plan.set_attribute("scale", "1:50")
   plan.set_attribute("author", "M. Verdi")
   plan.set_attribute("software", "AutoCAD 2024")
   
   # Add 3D model
   model = DocumentNode("DOC003", "atrium_3d.gltf")
   model.set_attribute("type", "3d_model")
   model.set_attribute("vertices", 150000)
   model.set_attribute("method", "photogrammetry")
   model.set_attribute("software", "Metashape Professional")
   
   site.add_node(photo1)
   site.add_node(plan)
   site.add_node(model)

Linking Documentation to Stratigraphic Units
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Link photo to floor
   site.add_edge("doc_001", "US001", "DOC001", "dashed")
   
   # Link technical drawing to wall
   site.add_edge("doc_002", "US002", "DOC002", "dashed")
   
   # Link 3D model to overall context
   site.add_edge("doc_003", "US001", "DOC003", "dashed")
   site.add_edge("doc_004", "US002", "DOC003", "dashed")

Adding Analytical Processes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Create extractor nodes for analytical processes
   photogrammetry = ExtractorNode("EXT001")
   photogrammetry.set_attribute("process", "3D_reconstruction")
   photogrammetry.set_attribute("software", "Metashape Professional 2.0")
   photogrammetry.set_attribute("operator", "Dr. G. Neri")
   photogrammetry.set_attribute("date", "2024-06-20")
   
   material_analysis = ExtractorNode("EXT002")
   material_analysis.set_attribute("process", "petrographic_analysis")
   material_analysis.set_attribute("method", "thin_section_microscopy")
   material_analysis.set_attribute("laboratory", "CNR-ISPC Rome")
   
   site.add_node(photogrammetry)
   site.add_node(material_analysis)
   
   # Link processes to source materials and results
   site.add_edge("proc_001", "DOC001", "EXT001", "line")  # Photo input to 3D process
   site.add_edge("proc_002", "EXT001", "DOC003", "line")  # 3D process creates model
   site.add_edge("proc_003", "US002", "EXT002", "dashed") # Wall sample to analysis

Working with Special Finds
---------------------------

Creating Special Find Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.nodes import StratigraphicNode
   
   # Bronze coin found in fill
   coin = StratigraphicNode("SF001", node_type="SF")
   coin.set_attribute("description", "Bronze sestertius, Vespasian")
   coin.set_attribute("material", "bronze")
   coin.set_attribute("dating", "70-79 CE")
   coin.set_attribute("weight", "25.4g")
   coin.set_attribute("diameter", "34mm")
   coin.set_attribute("find_date", "2024-06-18")
   coin.set_attribute("finder", "Student excavation team")
   
   # Ceramic fragment
   pottery = StratigraphicNode("SF002", node_type="SF")
   pottery.set_attribute("description", "Terra sigillata rim fragment")
   pottery.set_attribute("material", "ceramic")
   pottery.set_attribute("dating", "1st century CE")
   pottery.set_attribute("fabric", "South Gaulish")
   pottery.set_attribute("form", "Dragendorff 37")
   
   site.add_node(coin)
   site.add_node(pottery)

Contextual Relationships
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Link finds to their stratigraphic contexts
   site.add_edge("ctx_001", "SF001", "US003", "dashed")  # Coin found in fill
   site.add_edge("ctx_002", "SF002", "US003", "dashed")  # Pottery in same fill
   
   # Add find documentation
   coin_photo = DocumentNode("DOC004", "coin_obverse.jpg")
   coin_photo.set_attribute("type", "artifact_photo")
   coin_photo.set_attribute("view", "obverse")
   coin_photo.set_attribute("scale", "1:1")
   
   site.add_node(coin_photo)
   site.add_edge("doc_005", "SF001", "DOC004", "dashed")

Virtual Reconstructions
-----------------------

Creating Virtual Stratigraphic Units
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Reconstruct missing roof structure
   roof = StratigraphicNode("USV001", node_type="USVs")
   roof.set_attribute("description", "Reconstructed roof structure")
   roof.set_attribute("reconstruction_method", "comparative_analysis")
   roof.set_attribute("certainty", "probable")
   roof.set_attribute("sources", ["Vitruvius De Architectura", "Pompeii parallels"])
   roof.set_attribute("material", "wood_and_tiles")
   
   # Virtual wall decoration
   fresco = StratigraphicNode("USV002", node_type="USVn")
   fresco.set_attribute("description", "Reconstructed Fourth Style frescoes")
   fresco.set_attribute("style", "Fourth Style Pompeian")
   fresco.set_attribute("reconstruction_method", "fragment_analysis")
   fresco.set_attribute("certainty", "possible")
   
   site.add_node(roof)
   site.add_node(fresco)

Reconstruction Relationships
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Connect virtual elements to physical evidence
   site.add_edge("rec_001", "USV001", "US002", "dotted")  # Roof supported by wall
   site.add_edge("rec_002", "USV002", "US002", "double_line")  # Fresco on wall
   
   # Document reconstruction process
   reconstruction_doc = DocumentNode("DOC005", "reconstruction_hypothesis.pdf")
   reconstruction_doc.set_attribute("type", "technical_report")
   reconstruction_doc.set_attribute("author", "Dr. A. Alberti")
   reconstruction_doc.set_attribute("date", "2024-07-01")
   
   site.add_node(reconstruction_doc)
   site.add_edge("doc_006", "USV001", "DOC005", "dashed")
   site.add_edge("doc_007", "USV002", "DOC005", "dashed")

Geographic and Temporal Context
-------------------------------

Adding Geographic Information
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.nodes import GeoPositionNode, EpochNode
   
   # Set geographic reference system
   geo_pos = GeoPositionNode("geo_" + site.graph_id)
   geo_pos.set_attribute("epsg", 32633)  # UTM Zone 33N
   geo_pos.set_attribute("shift_x", 450000.0)
   geo_pos.set_attribute("shift_y", 4515000.0)
   geo_pos.set_attribute("shift_z", 42.0)
   geo_pos.set_attribute("reference_point", "Site datum benchmark")
   
   site.add_node(geo_pos)

Defining Temporal Periods
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Define chronological periods
   epochs = {
       "Republican": {
           "start": -509,
           "end": -27,
           "color": "#996633",
           "description": "Roman Republican period"
       },
       "Imperial": {
           "start": -27,
           "end": 476,
           "color": "#CC6600", 
           "description": "Roman Imperial period"
       },
       "Vesuvian_Eruption": {
           "start": 79,
           "end": 79,
           "color": "#FF0000",
           "description": "79 CE Vesuvius eruption"
       }
   }
   
   # Add epochs to graph
   for epoch_name, epoch_data in epochs.items():
       epoch = EpochNode(f"epoch_{epoch_name}")
       for key, value in epoch_data.items():
           epoch.set_attribute(key, value)
       site.add_node(epoch)

Data Export and Analysis
------------------------

Exporting to JSON
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.exporters import JSONExporter
   
   # Export complete graph to JSON
   exporter = JSONExporter()
   site_data = exporter.export_graph(site.graph_id)
   
   # Save to file
   exporter.save_to_file(site_data, "pompeii_house_vii.json")
   
   print("Export completed: pompeii_house_vii.json")

Exporting to GraphML for Network Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.exporters import GraphMLExporter
   
   # Export for network analysis tools
   graphml_exporter = GraphMLExporter()
   graphml_exporter.export_graph(
       site.graph_id,
       "pompeii_network.graphml",
       include_attributes=True
   )

Basic Graph Analysis
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Analyze graph structure
   print(f"Total nodes: {len(site.nodes)}")
   print(f"Total edges: {len(site.edges)}")
   
   # Count by node type
   node_types = {}
   for node in site.nodes:
       node_type = node.node_type
       node_types[node_type] = node_types.get(node_type, 0) + 1
   
   print("\nNode type distribution:")
   for node_type, count in node_types.items():
       print(f"  {node_type}: {count}")
   
   # Find stratigraphic sequence
   us_nodes = [n for n in site.nodes if n.node_type == "US"]
   temporal_edges = [e for e in site.edges if e.edge_type == "line"]
   
   print(f"\nStratigraphic units: {len(us_nodes)}")
   print(f"Temporal relationships: {len(temporal_edges)}")

Multi-Graph Projects
--------------------

Working with Multiple Excavation Areas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy import MultiGraphManager
   
   # Get global graph manager
   manager = MultiGraphManager()
   
   # Create graphs for different excavation areas
   area_a = manager.create_graph("Pompeii_Area_A")
   area_b = manager.create_graph("Pompeii_Area_B")
   area_c = manager.create_graph("Pompeii_Area_C")
   
   # Set up Area A (residential quarter)
   area_a.set_metadata("name@en", "Residential Quarter A")
   area_a.set_metadata("supervisor", "Dr. Elena Rossi")
   area_a.set_metadata("excavation_method", "stratigraphic_excavation")
   
   # Set up Area B (commercial district)
   area_b.set_metadata("name@en", "Commercial District B")  
   area_b.set_metadata("supervisor", "Prof. Marco Bianchi")
   area_b.set_metadata("excavation_method", "area_excavation")

Cross-Area Relationships
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Add units to different areas
   house_wall = StratigraphicNode("A_US001", node_type="US")
   house_wall.set_attribute("description", "House wall, east side")
   area_a.add_node(house_wall)
   
   street_surface = StratigraphicNode("B_US001", node_type="US")
   street_surface.set_attribute("description", "Paved street surface")
   area_b.add_node(street_surface)
   
   # Create cross-area relationship
   # Note: This requires special handling for multi-graph relationships
   cross_ref = DocumentNode("CROSS_001", "area_relationship_analysis.pdf")
   cross_ref.set_attribute("type", "inter_area_analysis")
   cross_ref.set_attribute("relationship", "contemporary_construction")
   
   # Add to both graphs
   area_a.add_node(cross_ref)
   area_b.add_node(cross_ref)

Collaborative Workflows
-----------------------

Team-Based Documentation
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.nodes import AuthorNode
   
   # Define team members
   team_lead = AuthorNode("AUTH001")
   team_lead.set_attribute("name", "Dr. Maria Rossi")
   team_lead.set_attribute("role", "Project Director")
   team_lead.set_attribute("institution", "University of Rome")
   team_lead.set_attribute("email", "m.rossi@uniroma.it")
   
   field_supervisor = AuthorNode("AUTH002")
   field_supervisor.set_attribute("name", "Dr. Luca Verdi")
   field_supervisor.set_attribute("role", "Field Supervisor")
   field_supervisor.set_attribute("specialization", "Roman_archaeology")
   
   site.add_node(team_lead)
   site.add_node(field_supervisor)
   
   # Link team members to their work
   site.add_edge("auth_001", "AUTH001", "DOC005", "dashed")  # Director authored report
   site.add_edge("auth_002", "AUTH002", "US001", "dashed")   # Supervisor excavated unit

Version Control and Documentation History
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Track documentation versions
   initial_plan = DocumentNode("DOC006_v1", "site_plan_v1.dwg")
   initial_plan.set_attribute("version", "1.0")
   initial_plan.set_attribute("date", "2024-06-01")
   initial_plan.set_attribute("status", "preliminary")
   
   revised_plan = DocumentNode("DOC006_v2", "site_plan_v2.dwg")
   revised_plan.set_attribute("version", "2.0")
   revised_plan.set_attribute("date", "2024-07-15")
   revised_plan.set_attribute("status", "final")
   revised_plan.set_attribute("changes", "Added newly discovered rooms")
   
   site.add_node(initial_plan)
   site.add_node(revised_plan)
   
   # Link versions
   site.add_edge("ver_001", "DOC006_v1", "DOC006_v2", "dotted")

Integration with External Tools
-------------------------------

Preparing Data for Blender (EMtools)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.exporters import EMToolsExporter
   
   # Export for Blender EMtools integration
   emtools_exporter = EMToolsExporter()
   emtools_data = emtools_exporter.export_for_blender(
       site.graph_id,
       include_3d_models=True,
       include_spatial_data=True
   )
   
   emtools_exporter.save_to_file(emtools_data, "pompeii_for_blender.json")

Database Integration
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.exporters import DatabaseExporter
   
   # Export to PostgreSQL database
   db_exporter = DatabaseExporter(
       database_type="postgresql",
       host="localhost",
       database="archaeological_projects",
       username="archaeologist"
   )
   
   # Create tables and insert data
   db_exporter.export_graph(
       site.graph_id,
       schema="pompeii_2024",
       create_schema=True
   )

Best Practices Summary
---------------------

Naming Conventions
~~~~~~~~~~~~~~~~~

* **Use consistent ID formats**: ``US001``, ``SF001``, ``DOC001``
* **Include site/area prefixes**: ``POMP_A_US001`` for multi-site projects
* **Date-based versioning**: ``DOC001_20240615`` for document versions
* **Descriptive names**: Clear, concise descriptions for all entities

Documentation Standards
~~~~~~~~~~~~~~~~~~~~~~~

* **Complete attribution**: Always include author, date, and method
* **Standardized vocabularies**: Use controlled terms for materials and techniques
* **Multilingual support**: Include translations for international collaboration
* **Version control**: Track all document and interpretation changes

Quality Control
~~~~~~~~~~~~~~

* **Regular validation**: Use built-in validators before export
* **Backup procedures**: Regular exports to multiple formats
* **Peer review**: Team validation of interpretations and relationships
* **Standard compliance**: Maintain CIDOC-CRM compatibility

Next Steps
----------

After completing this quick start guide, explore:

* :doc:`examples/archaeological_workflow` - Complete excavation project example
* :doc:`examples/blender_integration` - 3D visualization workflows  
* :doc:`api/core` - Complete API reference
* :doc:`import_export` - Advanced data exchange techniques
* :doc:`troubleshooting` - Solutions to common issues

For more complex scenarios and advanced features, see the complete documentation 
and example projects in the s3dgraphy repository.