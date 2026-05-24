Development Roadmap
===================

This document outlines the development roadmap for s3dgraphy, the core Python library
that implements the Extended Matrix formal language for archaeological documentation.

Architectural game-changer: triplestore as source of truth (v1.6.0+)
---------------------------------------------------------------------

Starting with v1.6.0, s3dgraphy adopts a fundamentally different architecture:
**the RDF triplestore becomes the persistent source of truth** for EM data, and
the in-memory property graph is treated as an editing cache.

Why this matters
~~~~~~~~~~~~~~~~

- Multiple tools (Blender, web viewers, analytics dashboards, AI pipelines)
  can read and write the **same** dataset concurrently
- SPARQL queries become a daily-workflow capability, not just an after-the-fact
  archival operation
- Heritage Digital Twin Ontology (HDT-O, ECHOES D7.1) integration is structural,
  not aspirational: every EM graph is formally an HC16 Heritage Proposition Set
  attached to one or more HC2 Heritage Digital Twins
- The HC14 Volatile vs HC15 Persistent distinction maps to versioning of
  proposition sets within an evolving HDT, not to "in-Blender vs exported"
  storage formats
- Conflict resolution and provenance become first-class concerns, supported
  by PROV-O timestamps + HC11 Digital Twin Maintenance activities

The full v1.6.0+ roadmap below operationalises this game-change.

Current development cycle: v1.6.0 (in dev)
-------------------------------------------

Completed in v1.6.0 (unreleased)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Datamodel & ontology
^^^^^^^^^^^^^^^^^^^^

- [x] Node datamodel v1.6.0 — systematic CIDOC-CRM mapping revision:
  legacy ``cidoc_s3d`` pseudo-class names replaced with formal ``em:`` IRIs;
  29 of 41 node classes carry ``em_extension`` blocks (uri, rdf_type,
  subclass_of, extension_status, rationale)
- [x] Connections datamodel v1.6.0 — typo fix (``ProperrtyNOde`` → ``PropertyNode``);
  ``has_documentation`` mapping corrected (P104 → P70i_is_documented_in);
  ``has_timebranch`` deprecated (use ``is_in_timebranch``); +4 HDT-O containment
  edges (has_digital_twin, has_digital_twin_component, contains_proposition_set,
  has_digital_object_part)
- [x] Qualia types v4.0 — expanded from ~30 to ~80 qualia, +4 subcategories
  (iconographic, semantic, ownership) and +1 new category **epistemic**
  (confidence_level, certainty_level, methodology_used, source_quality,
  primary_contributor, review_status, last_modified) — central to the EM
  paradata model
- [x] CRMinf promoted to primary mapping for ParadataNode (I1_Argumentation),
  ExtractorNode (I7_Belief_Adoption), CombinerNode (I5_Inference_Making)
- [x] AuthorNode split into ``AuthorNode`` (human, em:HumanAuthor) and
  ``AuthorAINode`` (AI, em:AIAuthor with model + prompt_reference)
- [x] **HDTNode** added (em:HC2_Heritage_Digital_Twin) for explicit HDT
  hierarchies inside an EM graph
- [x] **em.ttl** — first formal Extended Matrix ontology
  (30+ classes, 13 properties, 245 triples) — declares ``em:`` namespace
  classes/properties referenced by ``em_extension`` and the connections datamodel
- [x] **hdto_extension.ttl** — minimal HDT-O subset aligned with ECHOES D7.1
  (5 classes HC1/HC2/HC14/HC15/HC16, 7 properties HP1/HP3/HP29/HP33 + inverses,
  with scope notes citing D7.1 §4)
- [x] AP11_has_physical_relation discrimination via subproperties
  (em:abuts, em:cuts, em:fills, em:overlies, em:bondedTo, em:physicallyEquals)
  — SPARQL-friendly pattern, supersedes the ``type_tag`` workaround

Exporter
^^^^^^^^

- [x] **RDFExporter** — Turtle, N-Triples, JSON-LD, TriG, RDF/XML output
- [x] Multi-typing via em_extension.subclass_of (every node carries all
  declared CRM superclasses)
- [x] PropertyNode conditional mapping (qualia type drives CIDOC class:
  height → E54_Dimension, aesthetic_value → crminf:I4_Proposition_Set,
  color → E55_Type, etc.)
- [x] AP11 subproperty emission (both specific em:abuts and generic
  crmarchaeo:AP11 emitted for SPARQL fallback inference)
- [x] Deprecated edge skip (``has_timebranch`` not emitted)
- [x] Named-graph wrapping per s3dgraphy Graph
- [x] em:EMGraph multi-typed as crm:E73 + prov:Bundle + hdto:HC16
- [x] **v1.6.1: parent_hdt_iri parameter** — every exported EMGraph gets
  ``hdto:HP33i_is_proposition_set_of <parent>`` triple, with IRI validation
  and parent type emission

Visual rules / palette
^^^^^^^^^^^^^^^^^^^^^^

- [x] Visual styles added for AuthorAINode (AUTH_AI), LicenseNode (LIC),
  EmbargoNode (EMB), GraphNode (GRAPH)
- [x] Palette label prefix "G." added for GraphNode

EM-blender-tools integration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- [x] **RDF Export panel** in EM Bridge sidebar (provider pattern,
  ``EXPORT_OT_rdf`` operator) — format selector, base URI, parent HDT IRI,
  all-publishable toggle

v1.6.2 — RDF endpoint reader + timestamps (next)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- [ ] **Node lifecycle timestamps** added to ``Node`` base class:
  ``created_at`` (ISO-8601 UTC, ``prov:generatedAtTime``),
  ``modified_at`` (ISO-8601 UTC, ``dcterms:modified``),
  ``version`` (int, optimistic locking via ``em:version``).
  Required for v1.6.3+ writer concurrency and v1.7.0 conflict resolution.
- [ ] **RDFEndpointImporter** — SPARQL CONSTRUCT against an endpoint
  (Oxigraph local, Virtuoso remote, GraphDB, …) → reconstructs s3dgraphy
  Graph in memory. Filtering by named-graph IRI, HDT IRI, time range.
- [ ] EM-blender-tools UI "Load from endpoint" alongside the GraphML loader
- [ ] Backend abstraction: ``s3dgraphy.rdf.backend`` with ``InMemoryStore``,
  ``OxigraphEmbedded`` (via pyoxigraph), ``HTTPEndpoint`` implementations

v1.6.3 — RDF endpoint writer (daily save flow)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- [ ] **RDFEndpointWriter** — on save, computes delta and emits SPARQL
  UPDATE (``INSERT DATA { GRAPH <iri> { … } }`` + ``DELETE WHERE { … }``)
- [ ] Optimistic locking guard (uses ``em:version``)
- [ ] EM-blender-tools "Save to endpoint" — replaces TTL export as daily
  workflow; TTL export remains for snapshots/sharing

v1.6.4 — HC11 Digital Twin Maintenance lifecycle
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- [ ] Each save creates an ``hdto:HC11_Digital_Twin_Maintenance`` activity
  (PROV-O Activity) recording who/when/why
- [ ] Version chains via ``hdto:HP30_added_content`` / ``HP31_deleted_content``
  / ``HP32_replaced`` between successive HC16 Heritage Proposition Set instances
- [ ] SPARQL queries can "time-travel" via maintenance timestamps
- [ ] Snapshot publishing — promote a current HC16 (volatile in HDT) to a
  cited HC15 Persistent Digital Object with a permanent IRI

v1.7.0 — Conflict resolution + deployment topologies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- [ ] **Conflict detection** on write — optimistic lock failure surfaces a
  per-node diff between local and server versions
- [ ] **Conflict resolution UI** in EM-blender-tools — reuses the existing
  GraphMLMerger conflict-list pattern but for RDF/SPARQL
- [ ] **Sync layer** — ``s3dgraphy.sync.push(local, remote)`` and
  ``sync.pull(remote, local)`` for end-of-day field→office reconciliation
- [ ] **Documented deployment topologies**:

  - **A) Centralized office** — single remote Virtuoso/GraphDB, Blender
    talks SPARQL directly
  - **B) Hyperlocal field** — rover/laptop runs Oxigraph server, field
    Blenders → LAN endpoint, no internet required
  - **C) Solo offline** — pyoxigraph **embedded** in s3dgraphy, single
    user, zero servers
  - **D) Hybrid sync** — B in the field + push to A on return to office,
    conflict resolution via PROV-O timestamps + manual UI when needed

Pre-1.6.0 completed work (historical)
--------------------------------------

- [x] Core graph structure with indexing (``GraphIndices``)
- [x] Node type system with CIDOC-CRM mappings
- [x] Three core JSON configuration files (Visual Rules, CIDOC Mapping, Connection Rules)
- [x] Stratigraphic node subclasses (US, USV, SF, VSF, USD, TSU) and serial variants
- [x] Actor, Link, License, and Embargo nodes
- [x] Document, Extractor, Combiner, Property nodes (paradata chain)
- [x] Representation Model nodes (3D models for US, DOC, SF)
- [x] GraphML import with UUID slipback
- [x] GraphML export with container group support
- [x] Container group nodes (US, USD, VSF) with is_part_of edges
- [x] Instance chains via changed_from edges
- [x] Comment/note node skipping during import
- [x] XLSX import with JSON mapping system
- [x] SQLite/pyArchInit import with JSON mapping
- [x] JSON export for web platforms (Heriverse, ATON)
- [x] Multi-graph management (MultiGraphManager)
- [x] Integration with EM-tools for Blender
- [x] Tag parser for EM canvas integration
- [x] 3D model library (glTF) and 2D icons (PNG)
- [x] Modular architecture
- [x] PyPI package release
- [x] Canonical/reverse edge directionality (v1.5.3)
- [x] has_visual_reference edge type (v1.5.4)
- [x] **Chronology calculation** (``calculate_chronology``): BFS-based TPQ/TAQ propagation
- [x] **AI extraction capabilities** and prompt templates (v0.1.27-0.1.30)
- [x] **Qualia Importer** for importing from Qualia templates (v0.1.28)
- [x] **GraphML Patcher** for round-trip editing (v0.1.33)
- [x] **Graph Merger** with conflict resolution (v0.1.33)
- [x] **Master DocumentNode enrichment** (v0.1.33)
- [x] **Epoch/Relations second-pass processing** (v0.1.34)
- [x] **Import GraphML updates** (v0.1.35)

Future / longer term (post-1.7.0)
----------------------------------

- [ ] GeoJSON export for GIS integration
- [ ] Neo4j / KuzuDB export for property-graph database consumers
- [ ] Standalone CLI for headless export and validation
- [ ] Batch processing utilities
- [ ] HC17 Observation with Inference integration into the paradata chain
  (deeper CRMinf mapping)
- [ ] CRMarchaeo + CRMba native node coverage (currently only the most-used
  classes are native; long tail via ``CRMReferenceNode``)
- [ ] pyArchInit ↔ s3dgraphy ↔ RDF round-trip alignment audit
- [ ] Performance optimizations for very large graphs (100k+ nodes)
- [ ] Comprehensive unit test coverage
- [ ] Complete API documentation

Related Projects
----------------

- `EM-tools for Blender <https://github.com/zalmoxes-laran/EM-blender-tools>`_ - 3D visualization
- `Extended Matrix Documentation <https://github.com/zalmoxes-laran/ExtendedMatrix>`_ - Language reference
- `3D Survey Collection <https://docs.extendedmatrix.org/projects/3DSC/>`_ - 3D model preparation

Current Status
--------------

For the most current development status, see:

- `GitHub Issues <https://github.com/zalmoxes-laran/s3dgraphy/issues>`_
- `Project Milestones <https://github.com/zalmoxes-laran/s3dgraphy/milestones>`_
- `EM-tools Changelog <https://github.com/zalmoxes-laran/EM-blender-tools/blob/main/changelog.md>`_
