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

    merger = GraphMerger(existing_graph, incoming_graph)
    conflicts = merger.detect_conflicts()
    # UI picks resolutions: e.g. resolutions = {"q.US001.material": "accept_incoming"}
    merger.apply_resolutions(resolutions)

Conflict types (since 1.5)
~~~~~~~~~~~~~~~~~~~~~~~~~~

The merger surfaces conflicts under typed labels so the UI can group
and badge them appropriately:

============================================  =================================
``Conflict.conflict_type``                     Domain
============================================  =================================
``unit_added`` / ``unit_changed``              StratigraphicNode existence /
                                               description / connecting edges
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
``conflict_type``              Typed label (see above)
``target_id``                  ID of the host node / edge
``field``                      Attribute / property name in conflict
``existing_value``             Value on the host graph
``incoming_value``             Value on the incoming graph
``extra: Dict[str, Any]``      Per-conflict payload (subfield, target
                               endpoint, attribute key, …)
============================  ========================================

The ``extra`` field is *new in 1.5* and backward-compatible (defaults
to ``{}``). It carries everything a UI needs to render granular diffs
without re-walking the graphs.

apply_resolutions semantics
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each conflict type has a *narrow* application rule:

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
#. ``GraphMerger(existing, incoming).detect_conflicts()`` — list
   what's new vs. drift.
#. UI loop: user picks resolutions.
#. ``GraphMerger.apply_resolutions(...)`` — write the chosen changes
   into ``existing``.
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
