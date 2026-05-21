Changelog
=========

All notable changes to s3dgraphy will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

[1.5.1] - 2026
---------------

This release marks the formal cut to the Extended Matrix 1.5 line. It
absorbs every change accumulated since the [0.1.32] release; the full
per-commit ledger lives in the root ``CHANGELOG.md``.

Added
^^^^^
- **``RSF`` (Reused Special Find)** stratigraphic subtype for spolia /
  re-used architectural elements (octagon, red border ``#9B3333``,
  white fill). Wired through the full pipeline: Python class
  ``ReusedSpecialFind`` in ``nodes/stratigraphic_node.py``, datamodel
  JSON entry (family ``real``, ``is_series=false``), visual rules entry,
  ``STRATIGRAPHIC_CLASS_MAP`` registration. Family classification flows
  through ``classification.py`` (``is_real("RSF")`` → ``True``).
- **``serUSD`` export dispatch** — palette template ``^USD\d+$`` shape
  ``ellipse`` (border ``#D86400``) now correctly dispatches to ``serUSD``
  on export. Round-trip identity holds for ``serUSD`` graphs.
- **Palette dispatch semantic** — ``exporter/graphml/node_registry.py``
  selects palette template elements by ``<y:NodeLabel>`` pattern matching
  instead of internal id (``n1..n9``). New
  ``S3DgraphyPaletteWarning`` subclass of ``UserWarning`` lets downstream
  code (Blender add-ons, CI gates) filter or escalate palette mismatches.

Changed
^^^^^^^
- ``convert_shape2type`` (importer) extended with RSF recognition rule
  (``octagon`` + ``#9B3333``); ``serSU`` keeps the same border colour
  but the shape qualifier (ellipse vs octagon) keeps the two
  unambiguous.
- ``_PALETTE_DISPATCH_RULES`` (exporter) extended with RSF and
  ``serUSD`` rules; first-match-wins contract preserved.
- ``_REQUIRED_PALETTE_TYPES`` now includes RSF and ``serUSD``.
- ``s3Dgraphy_node_datamodel.json`` bumped to internal version 1.5.4
  (RSF addition documented); ``em_visual_rules.json`` bumped to 1.5.2.
- ``__datamodel_version__`` (connections datamodel) is 1.5.5
  (governed by a separate file).

Fixed
^^^^^
- Unrecognised palette labels in export no longer fall back silently to
  ``US`` with a white/red rectangle.
- Registry warns at load time if the palette template ships without one
  of the canonical stratigraphic stencils.

[0.1.41] - 2026-05-09
----------------------

Added
^^^^^
- **``LocationNodeGroup``** — spatial / locational membership node
  (subclass of ``GroupNode``). Required field
  ``kind ∈ {toponym, study, functional}``; ``propagation`` defaulting to
  ``"additive"`` (memberships compose; none overrides). A
  ``LocationNodeGroup`` can itself be ``is_in_location`` of another
  ``LocationNodeGroup`` (Pompei → Sector 4 → Casa del Fauno → Room 12).
- **Datamodel JSON v1.5.3** — registers ``LocationNodeGroup`` under
  ``group_nodes.GroupNode.subtypes`` with abbreviation ``LNG``. CIDOC
  mapping: ``E53 Place``, classified by ``E55 Type`` via ``P2_has_type``.
- **Connections datamodel v1.5.5** — new ``is_in_location`` edge with
  ``includes_location`` reverse. Context-sensitive CIDOC mapping:
  ``P53_has_former_or_current_location`` (node→location) and
  ``P89_falls_within`` (recursive location→location). Optional edge
  attribute ``is_primary: bool`` (default ``false``).
- **Visual rules v1.5.1** — ``LocationNodeGroup`` dashed
  round-rectangle, fill ``#F5F5F5``, per-``kind`` border colour
  modifiers (toponym ``#888888``, study ``#3A5A8C``,
  functional ``#000000``). ``is_in_location`` edge style with
  ``primary_modifier`` override on ``is_primary=true``.

Added — Stratigraphic classification refactor (2026-04)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
- **Datamodel JSON v1.5.2** — every stratigraphic subtype carries
  ``family`` (``"real"``/``"virtual"``/``null``) and ``is_series``
  (bool). Additive patch.
- **``s3dgraphy.classification`` module** — JSON-driven API re-exported
  from the package root: ``get_family``, ``is_real``, ``is_virtual``,
  ``is_series``, ``get_subtype_info``, ``iter_subtypes``, plus frozenset
  constants ``REAL_US_TYPES``, ``VIRTUAL_US_TYPES``, ``SERIES_US_TYPES``,
  ``ALL_US_TYPES``.
- **NegativeStratigraphicUnit** — new ``USN`` class (family ``real``,
  non-series).
- **Extended ``STRATIGRAPHIC_CLASS_MAP``** — added ``UL → WorkingUnit``
  and ``USN → NegativeStratigraphicUnit``.

Added — Unified xlsx pipeline (DP-02 / DP-49)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
- **``em_data.xlsx`` 5-sheet schema** — single-file replacement for the
  legacy ``stratigraphy.xlsx`` + ``em_paradata.xlsx`` two-step flow.
  Sheets: ``Units``, ``Epochs``, ``Claims``, ``Authors``, ``Documents``.
  Template at ``s3dgraphy/templates/em_data_template.xlsx``.
- **``UnifiedXLSXImporter``** — single-pass importer for the unified
  schema. Each claim row carries its own attribution triple(s):
  ``EXTRACTOR_i`` / ``DOCUMENT_i`` / ``AUTHOR_i`` / ``AUTHOR_KIND_i``.
  Combiner rows insert a ``CombinerNode`` between the ``PropertyNode``
  and the two ``ExtractorNode`` instances.
- **``UnifiedXLSXExporter``** — inverse round-trip. Walks the in-memory
  graph and emits the 5-sheet workbook with only the canonical
  direction of each relation pair.

Added — Hybrid-C auxiliary lifecycle (Phase 1 + 3)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
- **``s3dgraphy.transforms.aux_tracking``** — bookkeeping primitives
  to distinguish *graph-native* content from *auxiliary-injected*
  content (DosCo, emdb, pyArchInit, sources-list, resource-folders).
- **``GraphMLExporter.export(path, persist_auxiliary=False)``** and
  **``GraphMLPatcher.patch(path, persist_auxiliary=False)``** —
  *volatile* (default) reverts and strips injected content;
  *bake* (``True``) emits everything verbatim and clears the
  bookkeeping (the enrichment layer becomes graph-native).

Added — Diagnostics & chronology
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
- **``s3dgraphy.diagnostics``** — ``attribute_property_node``,
  ``attribute_temporal_claim``, ``detect_stratigraphic_cycles`` (Tarjan
  SCC). Paradox warnings carry attribution; cycle warnings auto-emitted
  by ``Graph.calculate_chronology()``.
- **Reverse-propagation compaction** —
  ``s3dgraphy.transforms.compact`` exposes
  ``prune_redundant_propagative_edges``,
  ``hoist_propagative_metadata`` and the orchestrator
  ``compact_propagative_metadata`` (hoist then prune). Lossless
  reformulation: resolver output preserved per node.
- **Materialize-continuity diamonds** on GraphML export.

Added — Resolvers / propagation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
- **``s3dgraphy.resolvers``** — property resolver with node-level /
  swimlane-level / graph-level fallback (``builtin_rules``).
  ``absolute_time_start`` / ``absolute_time_end`` PropagationRules
  (renamed from ``chronology_start`` / ``chronology_end``).

Added — GraphML round-trip
^^^^^^^^^^^^^^^^^^^^^^^^^^
- **GraphML export of paradata image nodes** (AuthorNode, AuthorAINode,
  LicenseNode, EmbargoNode). Changing an icon in yEd requires
  **no Python change** — just re-save the palette template.

Added — Earlier releases absorbed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
- **[v0.1.33]** ``GraphMLPatcher`` (round-trip editing, EMID
  validation), ``GraphMerger`` (conflict resolution),
  Master DocumentNode enrichment.
- **[v0.1.34]** Epoch / Relations second-pass GraphML handling.
- **[v0.1.35]** Import GraphML updates.

Changed
^^^^^^^
- **Dropped legacy ``absolute_start_date`` / ``absolute_end_date``
  aliases** across the codebase. Canonical pair is
  ``absolute_time_start`` / ``absolute_time_end``.
- **AI extraction prompt rewritten for the unified schema** (v5.0,
  breaking change). The StratiMiner prompt at
  ``s3dgraphy/data/StratiMiner_Extraction_Prompt.md`` now describes the
  single-file ``em_data.xlsx`` output with 5 sheets, explicit
  ``AUTHOR_KIND_N ∈ {author, extractor}`` distinguishing claims
  transcribed from the document author vs claims newly derived by the
  AI, and per-claim attribution on stratigraphic relations.

Migration
^^^^^^^^^
- No public API change in the palette dispatch refactor.
  ``NodeRegistry``, ``get_visual_properties()``,
  ``get_shape_for_type()``, ``get_colors_for_type()`` keep their
  signatures.
- Tools generating palette templates with non-canonical labels should
  add their pattern to ``_PALETTE_DISPATCH_RULES`` to avoid
  ``S3DgraphyPaletteWarning``.

[0.1.32] - 2026
----------------

Added
^^^^^
- **Chronology calculation engine** (``calculate_chronology``): BFS-based temporal
  inference that propagates absolute dates (TPQ/TAQ) through stratigraphic relations,
  storing computed ``CALCUL_START_T`` and ``CALCUL_END_T`` attributes on each node
- **Temporal property detection**: ``_find_temporal_property`` resolves
  ``absolute_start_date`` / ``absolute_end_date`` PropertyNodes by matching on
  ``property_type`` or ``name``, with fallback to ``description`` as value source

Changed
^^^^^^^
- ``calculate_chronology`` now collects stratigraphic nodes by their actual
  ``node_type`` values (US, USVs, USVn, VSF, SF, USD, serSU, serUSD, serUSVn,
  serUSVs, USM) instead of the former class-name lookup ``"StratigraphicNode"``

Fixed
^^^^^
- PropertyNode value resolution when the GraphML importer stores the numeric value
  in ``description`` rather than ``value``
- Node type lookup in chronology calculation returning 0 nodes due to mismatch
  between class name and ``node_type`` attribute

[0.1.31] - 2025
----------------

Added
^^^^^
- **GraphML export** with full round-trip support (``GraphMLExporter``)
- **Container group nodes**: US (``#9B3333``), USD (``#D86400``), VSF (``#B19F61``) as group nodes in GraphML, converted to regular nodes with ``is_part_of`` edges on import
- **VirtualSpecialFindUnit as container**: VSF can now contain SF elements via ``is_part_of``
- **Instance chains**: ``changed_from`` edges link the same object across epochs; BFS traversal identifies connected components
- **Comment node skipping**: yEd annotation nodes with yellow fill (``#FFCC00``, ``#FFFF00``, ``#FFFF99``) are skipped during import
- **has_visual_reference** edge type (connections datamodel v1.5.4)
- Canonical/reverse edge directionality pattern (connections datamodel v1.5.3)
- GraphML export of container group nodes with correct background colours
- GraphML export of epoch swimlanes, activity groups, and paradata groups

Changed
^^^^^^^
- Connections datamodel updated to v1.5.4
- ``is_part_of`` allowed targets now include ``VirtualSpecialFindUnit``
- Improved duplicate EMID detection during GraphML import

[0.1.13] - 2024
----------------

Added
^^^^^
- XLSX import with JSON mapping system (``MappedXLSXImporter``)
- SQLite/pyArchInit import with JSON mapping
- Graph indexing system (``GraphIndices``) for O(1) lookups
- UUID slipback mechanism for GraphML round-trip editing
- Multi-graph management (``MultiGraphManager``)
- Three core JSON configuration files (Visual Rules, CIDOC Mapping, Connection Rules)
- Stratigraphic node subclasses (US, USV, SF, VSF, USD)
- Paradata chain nodes (DOC, EXT, COMB, PROP)
- Representation Model nodes
- Actor, Link, License, Embargo nodes
- Tag parser for EM canvas integration
- 3D model library (glTF) and 2D icons (PNG)

Changed
^^^^^^^
- Modular architecture revision from EM-tools codebase
- Node type hierarchy restructured for extensibility

[0.1.0] - Initial Development
------------------------------

Added
^^^^^
- Basic graph structure implementation
- Node and edge management system
- JSON export functionality
- Integration hooks for Blender (via EM-tools)
- Core stratigraphic modeling capabilities
- Document and paradata node support
- Python package structure
- Documentation structure with Sphinx

Version History Context
-----------------------

s3dgraphy represents the core graph library that powers the Extended Matrix Framework.
It evolved from the graph management components of EM-tools and is developed
as a standalone Python library to enable Extended Matrix functionality across
multiple platforms and applications.

Links
-----

| [1.5.1]: https://github.com/zalmoxes-laran/s3dgraphy/compare/v0.1.41...v1.5.1
| [0.1.41]: https://github.com/zalmoxes-laran/s3dgraphy/compare/v0.1.32...v0.1.41
| [0.1.32]: https://github.com/zalmoxes-laran/s3dgraphy/compare/v0.1.31...v0.1.32
| [0.1.31]: https://github.com/zalmoxes-laran/s3dgraphy/compare/v0.1.13...v0.1.31
| [0.1.13]: https://github.com/zalmoxes-laran/s3dgraphy/compare/v0.1.0...v0.1.13
| [0.1.0]: https://github.com/zalmoxes-laran/s3dgraphy/releases/tag/v0.1.0
