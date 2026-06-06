Core Classes
============

This section documents the core classes of s3dgraphy that form the
foundation of the library: the :class:`~s3dgraphy.graph.Graph` container,
the base :class:`~s3dgraphy.nodes.base_node.Node`, the in-memory
:class:`~s3dgraphy.indices.GraphIndices`, and the
:class:`~s3dgraphy.multigraph.multigraph.MultiGraphManager` that holds
several graphs in a single session.

.. note::

   Edge objects and the canonical edge-type catalog are documented on
   their own page — see :doc:`/api/edges` and the in-depth
   :doc:`/api/s3dgraphy_edges_reference`.

Graph
-----

The ``Graph`` is the central container. It owns the ``nodes`` and
``edges`` lists, validates every connection against the connections
datamodel at write time, maintains lazily-rebuilt
:class:`~s3dgraphy.indices.GraphIndices` for O(1) lookups, and exposes
the chronology engine (:meth:`~s3dgraphy.graph.Graph.calculate_chronology`)
and the paradata-chain walkers.

.. autoclass:: s3dgraphy.graph.Graph
   :members:
   :undoc-members:
   :show-inheritance:

Base Node
---------

Every node type inherits from ``Node``. The base class implements the
``node_type_map`` registry: each subclass auto-registers its
``node_type`` string via ``__init_subclass__``, which is what powers
:meth:`Graph.validate_connection` and the importers' type dispatch.

.. automodule:: s3dgraphy.nodes.base_node
   :members:
   :undoc-members:
   :show-inheritance:

Graph Indices
-------------

``GraphIndices`` is the performance layer behind the ``Graph``. It is
rebuilt lazily (the ``Graph`` flips an internal *dirty* flag on every
mutation) and provides constant-time lookups by id, by type, by
property name/value and by edge source/target/type.

.. automodule:: s3dgraphy.indices
   :members:
   :undoc-members:
   :show-inheritance:

Multi-Graph Manager
-------------------

``MultiGraphManager`` keeps several named graphs in one session (for
example one graph per excavation area) and provides the module-level
convenience functions used across the library and by EM-tools
(``load_graph_from_file``, ``get_graph``, ``get_all_graph_ids``,
``remove_graph``).

.. automodule:: s3dgraphy.multigraph.multigraph
   :members:
   :undoc-members:
   :show-inheritance:
