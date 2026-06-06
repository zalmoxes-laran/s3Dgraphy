Graph Merger and GraphML Patcher
================================

.. versionadded:: 0.1.33
.. versionchanged:: 1.5.0
   GraphMerger extended to the paradata layer (qualia, authors,
   documents, epochs, edge attribution); GraphMLPatcher dispatches
   AuthorNode / AuthorAINode / LicenseNode / EmbargoNode through the
   palette resources.

s3dgraphy ships two distinct *round-trip* primitives. They are
**complementary**, not interchangeable:

:class:`s3dgraphy.merge.graph_merger.GraphMerger`
    Compares an existing in-memory graph with an incoming graph (e.g.
    a re-imported xlsx) and produces a list of :class:`Conflict`
    instances that the host application (typically the Blender
    conflict-resolution UI) presents to the user. The user picks
    accept / reject per conflict; the merger then applies the chosen
    resolutions in place.

:class:`s3dgraphy.exporter.graphml.graphml_patcher.GraphMLPatcher`
    Patches an existing GraphML file *on disk* with the changes from
    an in-memory :class:`Graph`. It preserves visual state (positions,
    group folding, ImageNode resources) that a full re-export would
    lose. EMID validation and duplicate detection are enforced during
    the patch.

GraphMerger
-----------

Pipeline::

    merger = GraphMerger()                                   # no constructor args
    conflicts = merger.compare(existing_graph, incoming_graph)
    # The UI reviews each Conflict and sets two flags on it:
    #   conflict.resolved = True        # the user has made a decision
    #   conflict.accepted = True/False  # True = take incoming, False = keep current
    merger.apply_resolutions(existing_graph, conflicts, incoming=incoming_graph)

Conflict types (since 1.5)
~~~~~~~~~~~~~~~~~~~~~~~~~~

The merger surfaces conflicts under typed labels so the UI can group
and badge them appropriately:

============================================  =================================
``Conflict.conflict_type``                     Domain
============================================  =================================
``node_added``                                 StratigraphicNode present only
                                               in the incoming graph
``value_changed``                              A field (e.g. ``description``)
                                               differs on a matched unit
``edge_added`` / ``edge_removed``              A connecting edge is new in /
                                               missing from the incoming graph
``qualia_added``                               PropertyNode claim new to
                                               existing graph
``qualia_changed``                             Value drift on
                                               ``(unit_name, property_type)``
``qualia_attribution_added``                   New ExtractorNode / DocumentNode
                                               / AuthorNode behind an existing
                                               PropertyNode
``author_added`` / ``author_changed``          Authors catalog row matched by
                                               short code (``A.01``, ``AI.01``)
``document_added`` / ``document_changed``      Documents catalog row matched
                                               by short code (``D.01``)
``epoch_added`` / ``epoch_changed``            EpochNode matched by name;
                                               ``start_time`` / ``end_time`` /
                                               ``color`` reported each as a
                                               dedicated conflict with a
                                               ``subfield`` hint in
                                               ``Conflict.extra``
``edge_attribution_added`` /                   Diffs on the ``edge.attributes``
``edge_attribution_changed``                   dict (``authored_by_N``,
                                               ``authored_kind_N``,
                                               ``document_N``) of relation edges
============================================  =================================

The ``Conflict`` dataclass exposes:

============================  ========================================
Field                          Meaning
============================  ========================================
``node_name``                  Name of the host node (e.g. ``"USM01"``)
``field``                      Conflicting field — may be prefixed
                               (``edge:overlies``, ``qualia:material``,
                               ``author:…``, ``document:…``, ``epoch:…``,
                               ``edge_attr:…``)
``current_value``              Value on the existing graph
``incoming_value``             Value on the incoming graph
``conflict_type``              Typed label (see table above)
``resolved: bool``             Set ``True`` by the UI once the user
                               decides (default ``False``)
``accepted: bool``             ``True`` = take ``incoming_value``,
                               ``False`` = keep ``current_value``
``extra: Dict[str, Any]``      Per-conflict payload (subfield, target
                               endpoint, attribute key, …)
============================  ========================================

The ``extra`` field is *new in 1.5* and backward-compatible (defaults
to ``{}``). It carries everything a UI needs to render granular diffs
without re-walking the graphs. The read-only
:attr:`Conflict.display_field` and :attr:`Conflict.display_summary`
properties produce human-readable labels for list rendering.

apply_resolutions semantics
~~~~~~~~~~~~~~~~~~~~~~~~~~~

:meth:`GraphMerger.apply_resolutions` only acts on conflicts the UI
marked ``resolved=True`` **and** ``accepted=True``; everything else is
left untouched. Each accepted conflict type then has a *narrow*
application rule:

- **qualia_added / qualia_changed** — copy the full PropertyNode
  subtree (PN + provenance chain) from the incoming graph. Catalog
  nodes (Author / Document) are *reused* from the host to avoid
  duplication.
- **catalog (author / document / epoch) add / change** — apply
  directly.
- **edge_attribution** — write to ``edge.attributes`` without touching
  the graph topology.

This makes ``apply_resolutions`` *idempotent* and *side-effect
auditable* — the UI knows exactly what changed.

Locked in by ``tests/test_graph_merger.py`` (8 synthetic scenarios)
plus a real-data smoke test on the Templu Mare graphml
(export → modify → re-import → merge) covering author rename, author
addition, and new qualia row.

GraphMLPatcher
--------------

Patcher pipeline::

    patcher = GraphMLPatcher(existing_path, in_memory_graph)
    patcher.patch(output_path)        # volatile (default)
    patcher.patch(output_path, persist_auxiliary=True)   # bake

Operations the patcher handles
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Update existing nodes**
    Description, name, EMID, URI are patched in place. The original
    yEd geometry, group folding, and edge routing are preserved.

**Add new nodes**
    Nodes created in-memory (not present in the on-disk GraphML) are
    inserted with correct yEd realizers. Dispatch goes through
    :class:`s3dgraphy.exporter.graphml.paradata_image_generator.ParadataImageNodeGenerator`
    for the four paradata image classes (AuthorNode, AuthorAINode,
    LicenseNode, EmbargoNode) — the palette resources are injected
    from ``templates/em_palette_template.graphml`` when missing.

**Add new edges**
    With correct yEd line style (mapping in
    :data:`EDGE_TYPE_TO_LINE_STYLE`), preserving canonical direction.

**EMID validation**
    Patcher refuses to add a duplicate EMID — the host application
    must resolve the conflict via :class:`GraphMerger` before
    patching.

**ParadataNodeGroup / ActivityNodeGroup containment**
    Two-pass: first inserts new group containers (indexing their
    nested ``<graph>`` elements plus those of pre-existing groups via
    ``original_id``), then routes every other new node into the
    matching container based on ``is_in_paradata_nodegroup`` /
    ``is_in_activity`` edges. Result: US + PD + Extractors + Combiner
    + PropertyNode + Document instance are physically nested under the
    correct yEd group at save time, not dumped in the top-level graph.

**Extractor / Combiner positioning**
    NodeLabel positioned at Corner-NorthWest via
    ``modelName="corners"`` + ``modelPosition="nw"`` +
    ``borderDistance="0.0"`` + ``underlinedText="true"`` — matches the
    reference TempluMare graphml and the full-export
    ``node_generator.py``.

Volatile vs bake
~~~~~~~~~~~~~~~~

The ``persist_auxiliary`` flag works identically to
:meth:`GraphMLExporter.export` — see
:doc:`/internals/transforms`. Default is *volatile*: the patcher
applies the reversal policy and strips ``injected_by`` content before
emitting, so the on-disk GraphML reflects only the graph-native state.

Choosing between merger and patcher
-----------------------------------

============================================  ============================
You want…                                      Use…
============================================  ============================
to detect what changed between two graphs      :class:`GraphMerger`
to let a user resolve conflicts                :class:`GraphMerger`
to write changes to an existing yEd file       :class:`GraphMLPatcher`
to preserve visual state across edits          :class:`GraphMLPatcher`
to create a fresh GraphML from scratch         :class:`GraphMLExporter`
============================================  ============================

The typical Blender workflow combines all three:

#. ``UnifiedXLSXImporter.parse()`` — load the incoming xlsx in memory.
#. ``GraphMerger().compare(existing, incoming)`` — list what's new vs.
   drift.
#. UI loop: user sets ``resolved`` / ``accepted`` on each conflict.
#. ``GraphMerger().apply_resolutions(existing, conflicts, incoming=incoming)``
   — write the chosen changes into ``existing``.
#. ``GraphMLPatcher(existing_path, existing).patch(output_path)`` —
   serialise back to GraphML, preserving visual state.

See also
--------

- :doc:`/internals/transforms` — the auxiliary-lifecycle semantics
  shared between :class:`GraphMLExporter` and
  :class:`GraphMLPatcher` (the ``persist_auxiliary`` flag).
- :doc:`/importers/unified_xlsx_importer` — the typical source of an
  *incoming* graph in the merger pipeline.
- ``CHANGELOG.md`` [v0.1.33] and [Unreleased] for the per-feature
  detailed roadmap.

API Reference
-------------

.. automodule:: s3dgraphy.merge.graph_merger
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.exporter.graphml.graphml_patcher
   :members:
   :undoc-members:
   :show-inheritance:
