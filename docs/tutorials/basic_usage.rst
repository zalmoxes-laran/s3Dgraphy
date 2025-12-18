Basic Usage Tutorial
===================

This tutorial will walk you through the basic usage of s3dgraphy, from creating your first graph to adding nodes and relationships.

Prerequisites
-------------

Make sure you have s3dgraphy installed:

.. code-block:: bash

   pip install s3dgraphy

Creating Your First Graph
--------------------------

Let's start by creating a simple stratigraphic graph for an archaeological site:

.. code-block:: python

   from s3dgraphy import Graph
   from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

   # Create a new graph
   site_graph = Graph("Pompeii_Forum")
   print(f"Created graph: {site_graph.name}")

Adding Stratigraphic Units
---------------------------

Now let's add some stratigraphic units representing different archaeological layers:

.. code-block:: python

   # Create stratigraphic units
   surface_layer = StratigraphicUnit(
       node_id="US001", 
       name="Surface layer", 
       node_type="US"
   )
   
   medieval_layer = StratigraphicUnit(
       node_id="US002", 
       name="Medieval occupation", 
       node_type="US"
   )
   
   roman_floor = StratigraphicUnit(
       node_id="US003", 
       name="Roman floor", 
       node_type="US"
   )

Adding Nodes to the Graph
--------------------------

Add the stratigraphic units to your graph:

.. code-block:: python

   # Add nodes to the graph
   site_graph.add_node(surface_layer)
   site_graph.add_node(medieval_layer)
   site_graph.add_node(roman_floor)

   print(f"Graph now has {len(site_graph.nodes)} nodes")

Defining Stratigraphic Relationships
------------------------------------

The core of stratigraphic analysis is understanding temporal relationships:

.. code-block:: python

   # Add temporal relationships (stratigraphic sequence)
   # "is_after" means the source is more recent than the target (canonical direction)

   site_graph.add_edge("rel1", "US001", "US002", "is_after")  # Surface after Medieval
   site_graph.add_edge("rel2", "US002", "US003", "is_after")  # Medieval after Roman

   print(f"Graph now has {len(site_graph.edges)} relationships")

Complete Example
----------------

Here's the complete code for this tutorial:

.. code-block:: python

   from s3dgraphy import Graph
   from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

   # Create graph
   site_graph = Graph("Pompeii_Forum")

   # Create and add stratigraphic units
   units = [
       StratigraphicUnit("US001", "Surface layer", "US"),
       StratigraphicUnit("US002", "Medieval occupation", "US"),
       StratigraphicUnit("US003", "Roman floor", "US")
   ]

   for unit in units:
       site_graph.add_node(unit)

   # Add stratigraphic relationships
   relationships = [
       ("rel1", "US001", "US002", "is_after"),
       ("rel2", "US002", "US003", "is_after")
   ]

   for rel_id, source, target, rel_type in relationships:
       site_graph.add_edge(rel_id, source, target, rel_type)

   # Print summary
   print(f"Created graph '{site_graph.name}' with:")
   print(f"  - {len(site_graph.nodes)} nodes")
   print(f"  - {len(site_graph.edges)} edges")

   # Export
   site_graph.export_graphml("pompeii_forum.graphml")

Next Steps
----------

Now that you understand the basics, you can explore:

- More complex node types and relationships
- Integration with Blender for 3D visualization
- CIDOC-CRM mappings for semantic interoperability
