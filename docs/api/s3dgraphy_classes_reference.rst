s3dgraphy Classes Reference
============================

This document provides a comprehensive reference for all classes in the s3dgraphy library, including detailed descriptions of methods, attributes, and usage examples.

Core Classes
------------

Graph Class
~~~~~~~~~~~

The ``Graph`` class is the central component of s3dgraphy, managing nodes and edges in a knowledge graph structure.

Class Definition
^^^^^^^^^^^^^^^^

.. code-block:: python

   class Graph:
       """
       Class representing a graph containing nodes and edges.
       
       Attributes:
           graph_id (str): Unique identifier for the graph
           name (dict): Dictionary of graph name translations
           description (dict): Dictionary of graph description translations
           audio (dict): Dictionary of audio file lists by language
           video (dict): Dictionary of video file lists by language
           data (dict): Additional metadata like geographical position
           nodes (List[Node]): List of nodes in the graph
           edges (List[Edge]): List of edges in the graph
           warnings (List[str]): List of warning messages during operations
           attributes (dict): Additional graph attributes
       """

Initialization
^^^^^^^^^^^^^^

.. code-block:: python

   def __init__(self, graph_id, name=None, description=None, audio=None, video=None, data=None):
       """
       Initialize a new Graph instance.
       
       Args:
           graph_id (str): Unique identifier for the graph
           name (dict, optional): Multi-language name dictionary
           description (dict, optional): Multi-language description dictionary
           audio (dict, optional): Audio files by language
           video (dict, optional): Video files by language
           data (dict, optional): Additional metadata
       """

**Example:**

.. code-block:: python

   from s3dgraphy import Graph

   # Basic graph creation
   graph = Graph("MyExcavation_2024")

   # Graph with multilingual metadata
   graph = Graph(
       "Pompeii_Forum",
       name={"en": "Pompeii Forum", "it": "Foro di Pompei"},
       description={"en": "Forum excavation data", "it": "Dati scavo del foro"},
       data={"coordinates": [40.7497, 14.4919], "elevation": 15}
   )

Performance and Indexing
^^^^^^^^^^^^^^^^^^^^^^^^

The Graph class implements a sophisticated indexing system for optimal performance:

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
       # Automatically called when indices are dirty
       # Indexes nodes by type, properties, and edges

Core Methods
^^^^^^^^^^^^

Node Management
"""""""""""""""

.. code-block:: python

   def add_node(self, node: Node, overwrite=False) -> Node:
       """
       Adds a node to the graph.
       
       Args:
           node (Node): The node to add
           overwrite (bool): Whether to overwrite existing nodes
           
       Returns:
           Node: The added node (existing if not overwritten)
       """

   def find_node_by_id(self, node_id: str) -> Node:
       """
       Finds a node by its ID.
       
       Args:
           node_id (str): The node ID to search for
           
       Returns:
           Node: The found node or None
       """

   def get_nodes_by_type(self, node_type: str) -> List[Node]:
       """
       Gets all nodes of a specific type using indexed lookup.
       
       Args:
           node_type (str): The node type to filter by
           
       Returns:
           List[Node]: List of nodes of the specified type
       """

Edge Management
"""""""""""""""

.. code-block:: python

   def add_edge(self, edge_id: str, edge_source: str, edge_target: str, edge_type: str) -> Edge:
       """
       Adds an edge to the graph with connection validation.
       
       Args:
           edge_id (str): Unique ID of the edge
           edge_source (str): Source node ID
           edge_target (str): Target node ID
           edge_type (str): Type of edge (must be in EDGE_TYPES)
           
       Returns:
           Edge: The added edge
           
       Raises:
           ValueError: If nodes don't exist or edge type is invalid
       """

   @staticmethod
   def validate_connection(source_node_type, target_node_type, edge_type):
       """
       Validates if a connection type between two nodes is allowed.
       
       Args:
           source_node_type (str): Type of the source node
           target_node_type (str): Type of the target node
           edge_type (str): Type of edge connecting the nodes
           
       Returns:
           bool: True if connection is allowed, False otherwise
       """

Specialized Query Methods
"""""""""""""""""""""""""

.. code-block:: python

   def get_property_nodes_for_node(self, node_id: str) -> List[Node]:
       """
       Gets all property nodes connected to a node.
       
       Args:
           node_id (str): ID of the starting node
           
       Returns:
           list: List of connected property nodes
       """

   def get_complete_paradata_chain(self, strat_node_id: str) -> dict:
       """
       Gets the complete paradata chain for a stratigraphic node.
       
       Args:
           strat_node_id (str): ID of the stratigraphic node
           
       Returns:
           dict: Dictionary with structured paradata chains:
               - properties: List of property nodes
               - combiners: List of combiner nodes  
               - extractors: List of extractor nodes
               - documents: List of document nodes
       """

**Example Usage:**

.. code-block:: python

   # Get complete documentation chain for a stratigraphic unit
   paradata = graph.get_complete_paradata_chain("US001")
   print(f"Properties: {len(paradata['properties'])}")
   print(f"Documents: {len(paradata['documents'])}")

   # Find all pottery material properties
   pottery_props = [node for node in graph.get_nodes_by_type("property") 
                   if "pottery" in node.description.lower()]

Warning System
""""""""""""""

.. code-block:: python

   def add_warning(self, message: str):
       """
       Adds a warning message to the warnings list.
       
       Args:
           message (str): Warning message to add
       """

   # Access warnings
   print("Graph warnings:")
   for warning in graph.warnings:
       print(f"  - {warning}")

MultiGraphManager Class
~~~~~~~~~~~~~~~~~~~~~~~

The ``MultiGraphManager`` class handles multiple graph instances within a single project.

.. code-block:: python

   class MultiGraphManager:
       """
       Manager for handling multiple graph instances.
       
       Attributes:
           graphs (dict): Dictionary mapping graph IDs to Graph instances
       """
       
       def __init__(self):
           self.graphs = {}
       
       def load_graph(self, filepath: str, graph_id: str = None, overwrite: bool = False) -> str:
           """
           Loads a graph from a GraphML file.
           
           Args:
               filepath (str): Path to the GraphML file
               graph_id (str, optional): ID to assign to the graph
               overwrite (bool): Whether to overwrite existing graph
               
           Returns:
               str: The ID of the loaded graph
           """
       
       def get_graph(self, graph_id: str = None) -> Graph:
           """
           Gets a graph from the manager.
           
           Args:
               graph_id (str, optional): ID of graph to retrieve.
                   If None and only one graph exists, returns that graph.
                   If None and multiple graphs exist, returns None.
                   
           Returns:
               Graph: The requested graph instance, or None if not found
           """

**Example Usage:**

.. code-block:: python

   from s3dgraphy import MultiGraphManager

   # Create manager and load multiple graphs
   manager = MultiGraphManager()

   # Load graphs from different excavation areas
   area_a_id = manager.load_graph("area_a_data.graphml", "AreaA_2024")
   area_b_id = manager.load_graph("area_b_data.graphml", "AreaB_2024")

   # Work with specific graphs
   area_a = manager.get_graph("AreaA_2024")
   area_b = manager.get_graph("AreaB_2024")

GraphIndices Class
~~~~~~~~~~~~~~~~~~

The ``GraphIndices`` class provides high-performance indexing for graph queries.

.. code-block:: python

   class GraphIndices:
       """
       Indexing system for efficient graph queries.
       
       Attributes:
           nodes_by_type (dict): Index of nodes by type
           property_nodes_by_name (dict): Index of property nodes by name
           property_values_by_name (dict): Index of property values
           strat_to_properties (dict): Map stratigraphic nodes to properties
           properties_to_strat (dict): Map property values to stratigraphic nodes
           edges_by_type (dict): Index of edges by type
           edges_by_source (dict): Index of edges by source node
           edges_by_target (dict): Index of edges by target node
       """
       
       def clear(self):
           """Cleans all indexes"""
           
       def add_node_by_type(self, node_type: str, node: Node):
           """Adds a node to the index by type"""
           
       def add_property_node(self, prop_name: str, node: Node):
           """Adds a property node to the indexes"""
           
       def add_edge(self, edge: Edge):
           """Adds an edge to indices"""

**Performance Benefits:**

- O(1) lookup time for nodes by type
- O(1) lookup time for edges by source/target
- Automatic index invalidation and rebuilding
- Memory-efficient storage of index structures

Node Classes Hierarchy
-----------------------

Base Node Class
~~~~~~~~~~~~~~~

.. code-block:: python

   class Node:
       """
       Base class for all node types in the graph.
       
       Attributes:
           node_id (str): Unique identifier for the node
           node_type (str): Type classification of the node
           name (str): Human-readable name
           attributes (dict): Additional node attributes
       """
       
       def __init__(self, node_id: str, node_type: str):
           self.node_id = node_id
           self.node_type = node_type
           self.name = ""
           self.attributes = {}
       
       def set_attribute(self, key: str, value):
           """Sets an attribute value"""
           self.attributes[key] = value
       
       def get_attribute(self, key: str, default=None):
           """Gets an attribute value with optional default"""
           return self.attributes.get(key, default)

Stratigraphic Node Classes
~~~~~~~~~~~~~~~~~~~~~~~~~~

StratigraphicNode (Base)
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   class StratigraphicNode(Node):
       """
       Base class for all stratigraphic nodes.
       
       Specialized attributes:
           description (str): Detailed description
           area (str): Excavation area
           sector (str): Excavation sector
           shape (str): YED shape type
           y_pos (float): Y position for chronological ordering
           fill_color (str): Visual representation color
           border_style (str): Visual border style
       """
       
       def __init__(self, node_id: str, node_type: str):
           super().__init__(node_id, node_type)
           self.description = ""
           self.area = ""
           self.sector = ""
           # Visual and positional attributes set during import

StratigraphicUnit (US)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   class StratigraphicUnit(StratigraphicNode):
       """
       Represents a stratigraphic unit (US - Unità Stratigrafica).
       
       The basic unit of stratigraphic excavation.
       """
       
       def __init__(self, node_id: str):
           super().__init__(node_id, "US")

SpecialFindUnit (SF)
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   class SpecialFindUnit(StratigraphicNode):
       """
       Represents a special find unit (SF - Reperto Speciale).
       
       Used for individual artifacts or significant finds.
       """
       
       def __init__(self, node_id: str):
           super().__init__(node_id, "SF")

Virtual Units
^^^^^^^^^^^^^

.. code-block:: python

   class StructuralVirtualStratigraphicUnit(StratigraphicNode):
       """
       Virtual unit representing structural elements (USV).
       """
       
       def __init__(self, node_id: str):
           super().__init__(node_id, "USV")

   class NonStructuralVirtualStratigraphicUnit(StratigraphicNode):
       """
       Virtual unit for non-structural interpretive elements (USNV).
       """
       
       def __init__(self, node_id: str):
           super().__init__(node_id, "USNV")

Temporal and Analysis Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~

EpochNode
^^^^^^^^^

.. code-block:: python

   class EpochNode(Node):
       """
       Represents a temporal epoch or chronological period.
       
       Attributes:
           start_time (int): Start time of the epoch
           end_time (int): End time of the epoch  
           min_y (float): Minimum Y coordinate
           max_y (float): Maximum Y coordinate
       """
       
       def __init__(self, node_id: str, name: str, start_time: int, end_time: int):
           super().__init__(node_id, "EpochNode")
           self.name = name
           self.start_time = start_time
           self.end_time = end_time
           self.min_y = 0.0
           self.max_y = 0.0

Documentation and Paradata Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

DocumentNode
^^^^^^^^^^^^

.. code-block:: python

   class DocumentNode(Node):
       """
       Represents a document or source of information.
       
       Attributes:
           url (str): URL or file path to the document
           description (str): Description of the document content
       """
       
       def __init__(self, node_id: str, name: str = "", url: str = "", description: str = ""):
           super().__init__(node_id, "document")
           self.name = name
           self.url = url
           self.description = description

PropertyNode
^^^^^^^^^^^^

.. code-block:: python

   class PropertyNode(ParadataNode):
       """
       Represents a property or attribute of a stratigraphic element.
       
       Attributes:
           name (str): Property name (e.g., "material", "dating")
           description (str): Property value or description
       """
       
       def __init__(self, node_id: str, name: str = "", description: str = ""):
           super().__init__(node_id, "property")
           self.name = name
           self.description = description

Grouping and Organizational Nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

GroupNode (Base)
^^^^^^^^^^^^^^^^

.. code-block:: python

   class GroupNode(Node):
       """
       Base class for grouping nodes.
       
       Provides functionality for organizing related nodes.
       """
       
       def __init__(self, node_id: str, node_type: str):
           super().__init__(node_id, node_type)

ActivityNodeGroup
^^^^^^^^^^^^^^^^^

.. code-block:: python

   class ActivityNodeGroup(GroupNode):
       """
       Groups nodes related to a specific activity or process.
       
       Used to organize stratigraphic units by excavation activity.
       """
       
       def __init__(self, node_id: str, name: str = ""):
           super().__init__(node_id, "ActivityNodeGroup")
           self.name = name

Usage Examples
--------------

Complete Graph Creation Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from s3dgraphy import Graph
   from s3dgraphy.nodes import StratigraphicUnit, DocumentNode, PropertyNode

   # Create a new archaeological site graph
   site = Graph("Pompeii_House_VII")
   site.name = {"en": "House VII Excavation", "it": "Scavo Casa VII"}

   # Add stratigraphic units
   wall = StratigraphicUnit("US001")
   wall.name = "Eastern Wall"
   wall.description = "Stone wall with opus reticulatum technique"
   wall.set_attribute("material", "limestone")
   wall.set_attribute("technique", "opus_reticulatum")

   floor = StratigraphicUnit("US002") 
   floor.name = "Mosaic Floor"
   floor.description = "Geometric mosaic pavement"
   floor.set_attribute("material", "tesserae")
   floor.set_attribute("pattern", "geometric")

   site.add_node(wall)
   site.add_node(floor)

   # Add stratigraphic relationship
   site.add_edge("rel1", "US002", "US001", "is_before")

   # Add documentation
   doc = DocumentNode("DOC001", "Field Notes Day 15", "notes_day15.pdf")
   doc.description = "Excavation notes for eastern wall discovery"
   site.add_node(doc)

   # Add property with documentation chain
   material_prop = PropertyNode("PROP001", "material", "limestone")
   site.add_node(material_prop)

   # Connect property to stratigraphic unit
   site.add_edge("prop_rel1", "US001", "PROP001", "has_property")

   # Connect property to documentation
   site.add_edge("doc_rel1", "PROP001", "DOC001", "extracted_from")

   print(f"Created graph with {len(site.nodes)} nodes and {len(site.edges)} edges")

   # Query the complete paradata chain
   paradata = site.get_complete_paradata_chain("US001")
   print(f"US001 has {len(paradata['properties'])} properties and {len(paradata['documents'])} documents")

This comprehensive class reference provides all the tools needed to work effectively with s3dgraphy's rich node and graph system.
