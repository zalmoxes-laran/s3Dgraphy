Property Propagation
====================

.. versionadded:: 1.5.0

.. module:: s3dgraphy.resolvers

The :mod:`s3dgraphy.resolvers` package implements the **3-level property
resolver** introduced in s3dgraphy 1.5 (DP-32 Layer A). Given a node and
a property name, the resolver walks the graph and returns the value plus
the source level it came from, so callers no longer need to know which
edges to traverse.

Conceptually
------------

For every *propagative* property — ``author``, ``license``, ``embargo``,
``absolute_time_start``, ``absolute_time_end`` — the resolver tries
three lookups in order and returns the first non-null result:

#. **Node-level**
   :func:`PropagationRule.node_getter` reads a value attached directly
   to the input node (typically a :class:`PropertyNode` reachable via
   ``has_property`` or an :class:`AuthorNode` reachable via
   ``has_author``).

#. **Swimlane-level**
   For every :class:`EpochNode` connected to the input node via
   ``has_first_epoch`` or ``survive_in_epoch``, the resolver calls
   :func:`PropagationRule.swimlane_getter`. If
   :attr:`PropagationRule.swimlane_aggregate` is provided (``min`` for
   start dates, ``max`` for end dates), it is applied to the non-null
   values; otherwise the first non-null value wins.

#. **Graph-level**
   :func:`PropagationRule.graph_getter` reads a value from the canvas
   header (``graph.attributes['author_name'|'license'|'embargo']``,
   populated by the DP-40 Canvas Header loader).

When the input itself is an :class:`EpochNode`, the resolver
short-circuits to the swimlane-level lookup — for an epoch, "node level"
and "swimlane level" are the same thing.

PropagationRule
---------------

Every propagative property is declared once as a
:class:`PropagationRule`::

    from s3dgraphy.resolvers import PropagationRule, register_rule

    AUTHOR_RULE = PropagationRule(
        id="author",
        label="Author",
        node_getter=_author_node_level,
        swimlane_getter=_author_swimlane_level,
        graph_getter=_author_graph_level,
    )
    register_rule(AUTHOR_RULE)

The four ship-standard rules are registered at module-import time in
:mod:`s3dgraphy.resolvers.builtin_rules`:

================================  ============================  ==========
Rule id                            What it returns                Aggregate
================================  ============================  ==========
``absolute_time_start``            TPQ — earliest year             ``min``
``absolute_time_end``              TAQ — latest year               ``max``
``author``                         joined display string           none
``license``                        license string                  none
``embargo``                        embargo end date                none
================================  ============================  ==========

The author rule follows **every** ``has_author`` edge (not just the
first one) and joins the display values with ``" ; "``. Duplicates are
de-duplicated while preserving edge order.

The author display string is read from
:attr:`AuthorNode.description` (1.5 dev9 yEd palette convention:
``AuthorNode.name = "A.01"``,
``AuthorNode.description = "Giulia Rossi | ORCID:… | affiliation"``),
falling back to ``data["name"] + data["surname"]`` and lastly to the
short code in :attr:`AuthorNode.name`.

resolve() / resolve_with_source()
---------------------------------

Two entry points::

    from s3dgraphy.resolvers import resolve, resolve_with_source

    val = resolve(graph, node, AUTHOR_RULE)                  # → "Giulia Rossi ; AI Tool"
    val, src = resolve_with_source(graph, node, AUTHOR_RULE) # → ("Giulia Rossi", "swimlane")

``src`` is one of ``"node"`` / ``"swimlane"`` / ``"graph"`` /
``"none"``. Use it to tag UI labels (em-graph paints node-level values
black, swimlane-level grey, graph-level grey-italic).

Worked example — author resolution
----------------------------------

.. code-block:: text

   US001  --has_author-->  AuthorNode  (A.01, "Giulia Rossi")
   US001  --has_first_epoch-->  EP_ROMAN

   EP_ROMAN  <--has_first_epoch--  SL_PD_ROMAN  (paradata group)
   SL_PD_ROMAN  --has_author-->  AuthorNode  (A.02, "Marco Bianchi")

For ``resolve(graph, US001, AUTHOR_RULE)``:

#. Node-level: US001 has a direct ``has_author`` edge → ``"Giulia Rossi"``.
   First non-null value wins, ``src = "node"``.

For ``resolve(graph, US002, AUTHOR_RULE)`` (a unit with no direct
``has_author``):

#. Node-level: nothing → ``None``.
#. Swimlane-level: US002's epoch is ``EP_ROMAN``, which has the SL_PD
   author A.02. Resolver returns ``"Marco Bianchi"``, ``src = "swimlane"``.

For an isolated unit US003 with no edges:

#. Node-level: nothing.
#. Swimlane-level: nothing.
#. Graph-level: ``graph.attributes["author_name"]`` from the DP-40
   canvas header → ``"Project lead"``.

Custom rules
------------

Add a project-specific propagative property without touching s3dgraphy
core::

    MATERIAL_RULE = PropagationRule(
        id="material",
        label="Material",
        node_getter=lambda g, n: _read_prop(g, n, "material_type"),
        swimlane_getter=lambda g, e: _read_prop(g, e, "material_type"),
        graph_getter=lambda g: g.attributes.get("project_material"),
    )
    register_rule(MATERIAL_RULE)

    val = resolve(graph, node, MATERIAL_RULE)

Use :func:`register_rule` / :func:`unregister_rule` / :func:`get_rule` /
:func:`list_rules` from :mod:`s3dgraphy.resolvers` to manage the
registry.

See also
--------

- :doc:`/internals/temporal` — the Temporal Inference Engine (Layer B)
  that uses the temporal rules registered here to seed TPQ/TAQ closure
  through stratigraphic relations.
- :doc:`/internals/transforms` — the ``compact`` transform that
  *promotes* per-node declarations to swimlane-level once the resolver
  reports they are redundant.
- :doc:`/api/diagnostics` — ``attribute_property_node`` /
  ``attribute_temporal_claim`` walk the same provenance chain to
  attribute a value to *who* asserted it.

API Reference
-------------

.. autodata:: s3dgraphy.resolvers.PropagationRule
   :annotation:

See :doc:`/api/resolvers` for the full autodoc of
:mod:`s3dgraphy.resolvers.property_resolver` and
:mod:`s3dgraphy.resolvers.builtin_rules`.
