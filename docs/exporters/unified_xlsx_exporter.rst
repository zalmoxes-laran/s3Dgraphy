Unified XLSX Exporter
=====================

.. versionadded:: 1.5.0

The :class:`~s3dgraphy.exporter.unified_xlsx_exporter.UnifiedXLSXExporter`
walks an in-memory :class:`~s3dgraphy.graph.Graph` and emits a single
``em_data.xlsx`` workbook with the same 5-sheet schema consumed by
:class:`UnifiedXLSXImporter`. It is the **inverse round-trip** of the
unified importer and is the recommended XLSX export path for
s3dgraphy 1.5.

.. seealso::

   :doc:`/importers/unified_xlsx_importer` for the schema reference,
   sheet semantics, and Combiner row pattern.

Round-trip symmetry
-------------------

The exporter is *deliberately conservative*: it emits only what the
graph actually contains, and is **canonical-edges-only**.

For each directed relation pair (e.g. ``overlies`` / ``is_overlain_by``,
``cuts`` / ``is_cut_by``), only the **primary direction** is written.
The reverse is recovered automatically at re-import time via
:meth:`Edge.get_reverse_name`. This keeps the workbook deduplicated and
avoids inadvertently emitting twice the rows from a graph that the
importer auto-completed with reverse edges. See
:ref:`canonical-reverse-edges` for the underlying schema convention.

Concretely, the canonical set emitted by the exporter is:

.. code-block:: text

   _CANONICAL_RELATIONS = {
       "overlies", "cuts", "fills", "abuts",
       "bonded_to", "equals",
       "is_after", "is_before",
       "has_same_time", "contrasts_with", "changed_from",
   }

while reverses (``is_overlain_by``, ``is_cut_by``, ``is_filled_by``,
``is_abutted_by``) are skipped on emission.

What the exporter walks
-----------------------

For each of the 5 sheets, the exporter performs the following walk:

**Units**
    Iterate every :class:`StratigraphicNode` in the graph (subclasses
    included) and write one row ``(ID, TYPE, NAME)`` per node, using
    ``node.node_type`` for ``TYPE``.

**Epochs**
    Iterate :class:`EpochNode` instances, emitting
    ``(ID, NAME, START, END, COLOR)``.

**Authors**
    Iterate :class:`AuthorNode` and :class:`AuthorAINode` instances.
    Parse the ``description`` field (set by the importer as
    ``"display | ORCID:XXXX | affiliation"``) back into its three
    structured columns ``DISPLAY_NAME`` / ``ORCID`` / ``AFFILIATION``.
    ``KIND`` is derived from the concrete class:

    - :class:`AuthorNode` → ``"human"``
    - :class:`AuthorAINode` → ``"ai"``

**Documents**
    Iterate :class:`DocumentNode` instances and rebuild
    ``(ID, FILENAME, TITLE, YEAR, AUTHOR_IDS)``.

**Claims** (the long table)
    For every :class:`PropertyNode`, walk the
    ``has_data_provenance`` chain to recover the attribution triple(s):

    .. code-block:: text

        PropertyNode  --has_data_provenance-->  ExtractorNode
                                                       |
                                          extracted_from
                                                       v
                                                DocumentNode
                                                       |
                                              has_author
                                                       v
                                                 AuthorNode

    or, for Combiner-mediated synthesis::

        PropertyNode --has_data_provenance--> CombinerNode
                                                |
                                  combines / combines
                                  /                \\
                       ExtractorNode_1        ExtractorNode_2

    Combiner rows produce **two attribution triples** plus
    ``COMBINER_REASONING`` (copied verbatim from
    :attr:`CombinerNode.description`).

    Stratigraphic relations read their attribution from the edge's
    ``attributes`` dict (``authored_by_id``, ``authored_by_kind``,
    ``document_id``) — no PropertyNode involved.

Legacy graph quirks
~~~~~~~~~~~~~~~~~~~

The exporter normalises a few legacy GraphML quirks observed in
pre-unified projects:

- ``PropertyNode.property_type == "string"`` (the legacy sentinel)
  is replaced with the actual qualia type recovered from
  :attr:`PropertyNode.name`; the value is read from
  :attr:`PropertyNode.description` when :attr:`PropertyNode.value` is
  empty.
- Duplicate unit names are disambiguated with a short uuid suffix and
  a warning is logged so that round-trip fidelity is preserved on
  legacy graphs with data-quality issues.

Workflow
--------

.. code-block:: python

   from s3dgraphy.exporter.unified_xlsx_exporter import UnifiedXLSXExporter

   exporter = UnifiedXLSXExporter(graph)
   stats = exporter.export("output/em_data.xlsx")
   print(stats)  # { 'units': N, 'epochs': M, 'claims': K, ... }

A module-level convenience wrapper :func:`write_unified_xlsx` is also
available for one-shot use::

   from s3dgraphy.exporter.unified_xlsx_exporter import write_unified_xlsx
   write_unified_xlsx(graph, "output/em_data.xlsx")

Round-trip locking
------------------

Round-trip identity is locked in by the test
``tests/test_unified_xlsx_roundtrip.py``, which covers:

#. **Resolver fingerprint invariance** — the property resolver returns
   the same value for every node before and after an
   export-then-reimport cycle.
#. **Combiner preservation** — Combiner structure (the two extractor
   provenance triples + ``COMBINER_REASONING``) survives the trip.
#. **Relation attribution preservation** — per-edge ``authored_by_id``
   / ``authored_by_kind`` / ``document_id`` survive the trip on
   stratigraphic relations.
#. **Real-data smoke test** — the Great Temple GraphML (102 units,
   ≈600 edges) exports and re-imports with the same unit count and
   no resolver drift.

When to use UnifiedXLSXExporter vs GraphMLExporter
--------------------------------------------------

**Use UnifiedXLSXExporter when**
    - You need an editable, human-readable representation
      (spreadsheet workflows, archival storage, AI re-extraction
      loops).
    - You want a *normalised* view (Authors and Documents in
      separate sheets rather than node-by-node duplication).
    - You're handing the data off to StratiMiner or a non-Python
      consumer.

**Use GraphMLExporter when**
    - You're round-tripping through yEd or em-graph (visual editing).
    - You need *visual* state (positions, group folding, swimlanes).
    - You want UUID slipback for stable edit-import cycles.

The two exporters are designed to coexist on the same graph; nothing
forces a choice between them.

API Reference
-------------

.. automodule:: s3dgraphy.exporter.unified_xlsx_exporter
   :members:
   :undoc-members:
   :show-inheritance:
