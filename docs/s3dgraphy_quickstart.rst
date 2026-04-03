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

   from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

   # Create stratigraphic units
   floor = StratigraphicUnit("US001", name="US001", description="Mosaic floor, main atrium")

   wall = StratigraphicUnit("US002", name="US002", description="North wall, frescoed")

   fill = StratigraphicUnit("US003", name="US003", description="Volcanic fill, 79 CE eruption")

   # Add nodes to graph
   site.add_node(floor)
   site.add_node(wall)
   site.add_node(fill)

Creating Stratigraphic Relationships
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Create temporal relationships
   # Fill covers the floor (fill is later than floor)
   site.add_edge("rel_001", "US003", "US001", "is_after")

   # Wall and floor are contemporary (built together)
   site.add_edge("rel_002", "US002", "US001", "has_same_time")

   print(f"Site graph contains {len(site.nodes)} units and {len(site.edges)} relationships")

Working with Documentation
--------------------------

Adding Documentation Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.nodes import DocumentNode, ExtractorNode

   # Add photographic documentation
   photo1 = DocumentNode("DOC001", name="floor_overview.jpg", description="Floor overview photograph")

   # Add technical drawing
   plan = DocumentNode("DOC002", name="wall_elevation.dwg", description="Wall elevation drawing")

   # Add 3D model
   model = DocumentNode("DOC003", name="atrium_3d.gltf", description="3D photogrammetric model")

   site.add_node(photo1)
   site.add_node(plan)
   site.add_node(model)

Linking Documentation to Stratigraphic Units
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Link photo to floor
   site.add_edge("doc_001", "US001", "DOC001", "has_data_provenance")

   # Link technical drawing to wall
   site.add_edge("doc_002", "US002", "DOC002", "has_data_provenance")

   # Link 3D model to overall context
   site.add_edge("doc_003", "US001", "DOC003", "has_data_provenance")
   site.add_edge("doc_004", "US002", "DOC003", "has_data_provenance")

Adding Analytical Processes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Create extractor nodes for analytical processes
   photogrammetry = ExtractorNode("EXT001", name="EXT001", description="3D reconstruction process")

   material_analysis = ExtractorNode("EXT002", name="EXT002", description="Petrographic analysis")

   site.add_node(photogrammetry)
   site.add_node(material_analysis)

   # Link processes to source materials and results
   site.add_edge("proc_001", "EXT001", "DOC001", "extracted_from")
   site.add_edge("proc_002", "EXT001", "DOC003", "extracted_from")
   site.add_edge("proc_003", "EXT002", "US002", "has_data_provenance")

Working with Special Finds
---------------------------

Creating Special Find Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.nodes.stratigraphic_node import SpecialFindUnit

   # Bronze coin found in fill
   coin = SpecialFindUnit("SF001", name="SF001", description="Bronze sestertius, Vespasian")

   # Ceramic fragment
   pottery = SpecialFindUnit("SF002", name="SF002", description="Terra sigillata rim fragment")

   site.add_node(coin)
   site.add_node(pottery)

Contextual Relationships
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Link finds to their stratigraphic contexts
   site.add_edge("ctx_001", "SF001", "US003", "extracted_from")
   site.add_edge("ctx_002", "SF002", "US003", "extracted_from")

   # Add find documentation
   coin_photo = DocumentNode("DOC004", name="coin_obverse.jpg", description="Coin obverse photograph")

   site.add_node(coin_photo)
   site.add_edge("doc_005", "SF001", "DOC004", "has_data_provenance")

Virtual Reconstructions
-----------------------

Creating Virtual Stratigraphic Units
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.nodes.stratigraphic_node import StructuralVirtualStratigraphicUnit, NonStructuralVirtualStratigraphicUnit

   # Reconstruct missing roof structure (structural, based on physical evidence)
   roof = StructuralVirtualStratigraphicUnit("USV001", name="USV001", description="Reconstructed roof structure")

   # Virtual wall decoration (non-structural, based on comparisons)
   fresco = NonStructuralVirtualStratigraphicUnit("USV002", name="USV002", description="Reconstructed Fourth Style frescoes")

   site.add_node(roof)
   site.add_node(fresco)

Reconstruction Relationships
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Connect virtual elements to physical evidence
   site.add_edge("rec_001", "USV001", "US002", "changed_from")
   site.add_edge("rec_002", "USV002", "US002", "has_same_time")

   # Document reconstruction process
   reconstruction_doc = DocumentNode("DOC005", name="reconstruction_hypothesis.pdf", description="Reconstruction technical report")

   site.add_node(reconstruction_doc)
   site.add_edge("doc_006", "USV001", "DOC005", "has_data_provenance")
   site.add_edge("doc_007", "USV002", "DOC005", "has_data_provenance")

Geographic and Temporal Context
-------------------------------

Adding Geographic Information
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.nodes import GeoPositionNode, EpochNode

   # Set geographic reference system
   geo_pos = GeoPositionNode(
       "geo_" + site.graph_id,
       epsg=32633,
       shift_x=450000.0,
       shift_y=4515000.0,
       shift_z=42.0
   )

   site.add_node(geo_pos)

Defining Temporal Periods
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Define chronological periods
   epoch_republican = EpochNode("epoch_Republican", name="Republican", start_time=-509, end_time=-27, color="#996633")
   epoch_imperial = EpochNode("epoch_Imperial", name="Imperial", start_time=-27, end_time=476, color="#CC6600")
   epoch_eruption = EpochNode("epoch_Vesuvian", name="Vesuvian Eruption", start_time=79, end_time=79, color="#FF0000")

   site.add_node(epoch_republican)
   site.add_node(epoch_imperial)
   site.add_node(epoch_eruption)

Data Export and Analysis
------------------------

Exporting to JSON
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.exporter.json_exporter import JSONExporter

   # Export complete graph to JSON
   exporter = JSONExporter("pompeii_house_vii.json")
   exporter.export_graphs()

   print("Export completed: pompeii_house_vii.json")

Exporting to GraphML for Network Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy.exporter.graphml import GraphMLExporter

   # Export for network analysis tools
   exporter = GraphMLExporter(site)
   exporter.export("pompeii_network.graphml")

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
   temporal_edges = [e for e in site.edges if e.edge_type == "is_after"]
   
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
   house_wall = StratigraphicUnit("A_US001", name="A_US001", description="House wall, east side")
   area_a.add_node(house_wall)

   street_surface = StratigraphicUnit("B_US001", name="B_US001", description="Paved street surface")
   area_b.add_node(street_surface)

   # Create cross-area relationship
   cross_ref = DocumentNode("CROSS_001", name="area_relationship_analysis.pdf", description="Inter-area analysis")

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
   team_lead = AuthorNode("AUTH001", name="Maria", surname="Rossi", orcid="0000-0001-2345-6789")

   field_supervisor = AuthorNode("AUTH002", name="Luca", surname="Verdi")

   site.add_node(team_lead)
   site.add_node(field_supervisor)

   # Link team members to their work
   site.add_edge("auth_001", "AUTH001", "DOC005", "has_author")
   site.add_edge("auth_002", "AUTH002", "US001", "has_author")

Version Control and Documentation History
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Track documentation versions
   initial_plan = DocumentNode("DOC006_v1", name="site_plan_v1.dwg", description="Preliminary site plan")

   revised_plan = DocumentNode("DOC006_v2", name="site_plan_v2.dwg", description="Final site plan with newly discovered rooms")

   site.add_node(initial_plan)
   site.add_node(revised_plan)

   # Link versions
   site.add_edge("ver_001", "DOC006_v1", "DOC006_v2", "changed_from")

Integration with External Tools
-------------------------------

Preparing Data for Web Platforms
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Export graph to JSON for Heriverse/ATON web platforms
   from s3dgraphy.exporter.json_exporter import JSONExporter

   exporter = JSONExporter("pompeii_for_heriverse.json")
   exporter.export_graphs()

Database Integration
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # s3dgraphy graphs can be exported to JSON and then loaded into external databases
   # Direct database export is planned for future releases
   # For now, export to JSON and use database-specific import tools

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

* :doc:`examples/s3dgraphy_workflow_examples` - Complete excavation project example
* :doc:`api/s3dgraphy_classes_reference` - Complete API reference
* :doc:`s3dgraphy_import_export` - Advanced data exchange techniques
* :doc:`s3dgraphy_troubleshooting` - Solutions to common issues

For more complex scenarios and advanced features, see the complete documentation 
and example projects in the s3dgraphy repository.