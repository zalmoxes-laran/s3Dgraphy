# Changelog

All notable changes to **s3dgraphy** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased] — v1.6.0 (in development)

### Architectural game-changer

This release adopts the **RDF triplestore as the persistent source of truth**
for EM data. The in-memory property graph (Blender, s3dgraphy Python) is now
treated as an editing cache; the triplestore is where the data lives. This
unblocks: (a) SPARQL queries as a daily-workflow capability, (b) multi-tool
read/write to the same dataset (Blender + web viewers + analytics + AI
pipelines), (c) formal HDT-O integration (every EM graph is an HC16 Heritage
Proposition Set attached to one or more HC2 HDTs).

The TTL export shipping in v1.6.0 is the **first** of three pieces (export,
endpoint read, endpoint write) — see `docs/s3dgraphy_roadmap.rst` for the
v1.6.0 → v1.7.0 plan.

### Added — Ontology layer

- **`em.ttl`** (`JSON_config/em.ttl`) — first formal Extended Matrix
  ontology. 30+ classes, 13 object properties, 245 triples. Declares the
  `em:` namespace (https://w3id.org/em/ontology#) — placeholder until a
  resolvable IRI is published. Covers: authors (HumanAuthor, AIAuthor +
  abstract Author), virtual SUs (VirtualSU + structural/non-structural/
  documentary/special-find variants), real SUs (NegativeSU, ReusedSpecialFind,
  DisplacedSpecialFind), series (4 types), events (StratigraphicEvent,
  TransformationSU, WorkingUnit, ContinuityNode), TimeBranch, RepresentationModel
  (+ 3 specializations), SemanticShape, Rights (License, Embargo, EMGraph),
  Qualia (paradata shell), Paradata head (I1_Argumentation), AP11 subproperties
  (abuts, cuts, fills, overlies, bondedTo, physicallyEquals).
- **`hdto_extension.ttl`** — minimal HDT-O subset aligned with ECHOES
  Deliverable D7.1 ("The Digital Commons"). 67 triples, 5 classes (HC1, HC2,
  HC14, HC15, HC16), 7 properties (HP1 + HP1i, HP3 + HP3i, HP29, HP33 + HP33i)
  with scope notes citing D7.1 §4. Namespace placeholder
  `https://w3id.org/hdto/ontology#`. Companion to em.ttl for HDT-O containment
  expression.
- **HDTNode** — new node type representing an HC2 Heritage Digital Twin
  inside an EM graph. Python class `HDTNode` (node_type='hdt') with
  heritage_entity_iri + valid_from/until. Hierarchically composable via
  `has_digital_twin_component` (HP3 inverse, transitive). EMGraph → HDT
  attachment via `contains_proposition_set` (HP33).

### Added — Node datamodel (v1.6.0)

- **`em_extension` block** on 29 of 41 node classes — declarative single
  source of truth for class IRIs (uri, rdf_type, subclass_of, extension_status,
  rationale). Replaces the deprecated `cidoc_s3d` field of invented strings.
- **AuthorNode split** into `AuthorNode` (human, em:HumanAuthor) and existing
  `AuthorAINode` (AI, em:AIAuthor). Both exported from `nodes/__init__.py`.
  Connections datamodel `has_author` already referenced AuthorAINode — the
  declaration was missing.
- **GraphNode** properly exported. New `container_nodes` section in node
  datamodel. Multi-typed as em:EMGraph + crm:E73_Information_Object +
  prov:Bundle + hdto:HC16_Heritage_Proposition_Set.
- **HDTNode** added to node datamodel `container_nodes` section.
- **Virtual SUs** semantic fix — `StructuralVirtualStratigraphicUnit`,
  `NonStructuralVirtualStratigraphicUnit`, `VirtualSpecialFindUnit` now
  declared as `crminf:I4_Proposition_Set` (propositional) not `crmarchaeo:A2`
  (physical, wrong semantics).
- **NegativeStratigraphicUnit** mapped to `crmarchaeo:A3_Stratigraphic_Interface`
  (the correct CRM class for a removal interface) — was wrongly mapped to a
  non-existent "A8 (Negative)".
- **DocumentaryStratigraphicUnit** declared as `em:DocumentaryVirtualSU`
  (a virtual SU inferred from documents) — was wrongly mapped to E31 Document
  (confused the SU with its sources).
- **ParadataNode** primary mapped to `crminf:I1_Argumentation` (was E31
  Document — paradata is reasoning, not documentation).
- **ExtractorNode** mapped to `crminf:I7_Belief_Adoption` (more specific
  than the previous E7 Activity).
- **CombinerNode** mapped to `crminf:I5_Inference_Making`.
- **TimeBranchNodeGroup** mapped to `em:TimeBranch ⊂ crm:E4_Period` with
  `em:contrastsWith` (symmetric). Was mapped to I2_Belief which over-typed
  (everything in EM is propositional by design).
- **RepresentationModel** subclasses (Doc, SF) declared as proper subclasses
  of `em:RepresentationModel` ⊂ crmdig:D1, with structural P138 target
  type constraints (was flat).
- **SemanticShape** mapped to `crmgeo:SP5_Geometric_Place_Expression`
  (was E36 Visual Item — too generic).
- **PropertyNode** declared as `em:Qualia` shell — the specific CIDOC class
  is resolved at serialization time by the qualia type (see em_qualia_types
  v4.0).

### Added — Connections datamodel (v1.6.0)

- Bug fix: typo `ProperrtyNOde` → `PropertyNode` in
  `is_in_paradata_nodegroup.allowed_connections.source`.
- Semantic fix: `has_documentation.mapping.cidoc` changed from
  `P104_is_subject_to` (wrong — P104 means subject to a legal right) to
  `P70i_is_documented_in` (canonical "is documented by").
- `has_timebranch` marked **deprecated** with rationale: duplicate of
  `is_in_timebranch`. Verified usage: `is_in_timebranch` is canonical
  (import_graphml.py:1510, graphml_patcher.py:73); `has_timebranch` lives
  only in JSON config. Scheduled removal in 1.7.0.
- **+4 HDT-O containment edges**: `has_digital_twin` (HP1),
  `has_digital_twin_component` (HP3 inverse, transitive),
  `contains_proposition_set` (HP33), `has_digital_object_part` (HP29).
- Components list aligned with node datamodel (HDT-O, PROV-O added).

### Added — Qualia types (v4.0)

- Verified all existing v3.0 CIDOC-CRM mappings (all correct).
- **+50 new qualia** across categories: volume/area/circumference (dimensional);
  color, texture, finish, patina, hardness, porosity (material); damage_type,
  fragility, completeness (state); tool_marks, joining_technique (technical);
  bounding_box, footprint_area (spatial); duration, terminus_post_quem,
  terminus_ante_quem, relative_chronology (temporal); ceremonial/ritual/
  defensive/domestic/symbolic functions (telic); school, period_attribution
  (stylistic); provenance_history, exhibition_history, publication_history
  (administrative).
- **NEW SUBCATEGORIES**: iconographic (iconographic_subject, narrative_content,
  iconographic_program), semantic (aesthetic_value, religious_significance,
  monumental_status, attribution), ownership (current_custodian, ownership_chain).
- **NEW CATEGORY epistemic** — meta-qualia central to the EM paradata model:
  confidence_level (E54 percentage), certainty_level (E55 enum), uncertainty_factors,
  methodology_used (E29), validation_method, source_quality, primary_contributor
  (E39 ref), review_status, last_modified (E52).

### Added — Visual rules + palette

- Visual styles for `AUTH_AI` (cyan star), `LIC` (gold shield),
  `EMB` (red dashed octagon), `GRAPH` (gray dashed rounded rectangle).
- Palette label prefix `G.` for GraphNode (alongside existing AI./A./LI./EB.).

### Added — RDFExporter (exporter/rdf_exporter.py)

- First serialization pipeline from s3dgraphy Graph to RDF.
- Five formats: Turtle, N-Triples, N-Quads, TriG, JSON-LD, RDF/XML.
- Multi-typing emission from `em_extension.subclass_of`.
- **Conditional PropertyNode mapping** — qualia type drives the CIDOC class
  (height → E54_Dimension, aesthetic_value → crminf:I4_Proposition_Set, etc.).
- AP11 physical-relation discrimination: emits both the specific subproperty
  (em:abuts) AND the generic crmarchaeo:AP11 (so consumers without subproperty
  inference still see the relation).
- Deprecated edges skipped on write.
- Named-graph wrapping per s3dgraphy Graph (one named graph per Graph).
- Stats: graphs, nodes, edges_emitted, edges_skipped_deprecated, edges_unmapped,
  nodes_unmapped, parent_hdt_bindings.

### Added — v1.6.1: parent HDT binding

- `RDFExporter(parent_hdt_iri=...)` — every exported EMGraph emits
  `hdto:HP33i_is_proposition_set_of <parent>` + parent type triple.
- IRI validation: requires absolute http(s)/urn IRI, ValueError on malformed.
- EM-blender-tools `EXPORT_OT_rdf` operator wires the scene field through.

### Fixed — v1.6.0.dev5: RDF qualia lookup (exporter-only, importer unchanged)

Architectural note: this fix lives entirely in the RDF exporter. The
graphml importer is left intact — it preserves raw graphml data
(``name``, ``description``, raw ``value``, ``property_type``). Semantic
enrichment via the qualia vocabulary happens at serialization time,
where it belongs (separation of concerns: importer = data, exporter =
semantics).

- **`exporter/rdf_exporter.py::_Datamodel.get_qualia_crm_iri`** — 4-step
  graceful lookup so the RDF conditional mapping survives common yEd label
  conventions:
  1. exact match (`"height"` → E54_Dimension)
  2. dot-split last segment (`"Dimension.height"` → "height" → E54_Dimension)
  3. lowercase fallback (`"Height"` → "height" → E54_Dimension)
  4. lowercase + dot-split combined (`"Dimension.Height"` → E54)
- **`exporter/rdf_exporter.py::_compute_primary_iri`** — for PropertyNodes,
  resolves the lookup key in two steps:
  1. ``node.property_type`` if explicitly set (non-default — anything
     other than the constructor sentinel "string")
  2. ``node.name`` (the yEd NodeLabel — qualia identifier in EM convention)
  This means files exported with the structured ``_s3d_property_metadata``
  side channel (which populates ``property_type``) AND legacy / converted
  graphml (where only ``name`` is populated) both work transparently.
- **`exporter/rdf_exporter.py::_serialize_type_specific`** for property —
  value resolution falls back from ``node.value`` to ``node.description``
  when the former is empty/None. yEd ARTIFACT_TYPE_ANNOTATION nodes have
  no dedicated "value" socket, so the description field commonly carries
  the value text (e.g. ``description="2013"`` for an absolute_time_start
  PropertyNode). The legacy URL-as-value convention is also honoured via
  ``node.value`` (which the importer still populates from the URL).
- The same NodeLabel fallback feeds ``em:hasQualiaType`` so SPARQL queries
  by qualia type work even on legacy graphml without the side channel.

Verified on Templu Mare graphml labels (absolute_time_start →
E52_Time-Span, Dimension.height → E54_Dimension, aesthetic_value →
crminf:I4_Proposition_Set). Custom labels like "lenght_pipe" correctly
fall back to the generic PropertyNode default (em:Qualia +
crm:E1_CRM_Entity).

### Added — RSF (Reused Special Find)

- **`RSF` (Reused Special Find)** — new stratigraphic node type for re-used
  architectural / decorative elements (spolia). Octagon, red border
  (`#9B3333`), white fill — visually a sibling of `SF` (yellow border) and
  `VSF` (gold border), distinguished by colour. Originating Development
  Project: DP-26 (spolia project, last DP before the EM 1.5 cut). Wired
  through the full pipeline: Python class `ReusedSpecialFind` in
  `nodes/stratigraphic_node.py`, JSON datamodel entry under
  `stratigraphic_nodes.StratigraphicNode.subtypes` (family `real`,
  `is_series=false`), `em_visual_rules.json` style entry, and
  `STRATIGRAPHIC_CLASS_MAP` registration. Family classification
  (`real` / non-series) flows through the existing `classification.py`
  accessors (`is_real("RSF")` returns `True`) without code change.
- **`serUSD` export dispatch** — palette template `^USD\d+$` shape
  `ellipse` (border `#D86400`) now correctly dispatches to `serUSD` on
  export, mirroring the existing import logic in
  `utils/utils.py::convert_shape2type`. Closes the export-side asymmetry
  flagged in `PALETTE_AUDIT.md` § 4 — the `serUSD` *class*,
  *datamodel JSON*, *visual rules*, and *importer rule* all pre-existed,
  but the exporter was silently routing the ellipse stencil to its
  default fallback. Round-trip identity now holds for `serUSD` graphs.

### Changed
- `convert_shape2type` (importer) extended with the `RSF` recognition rule
  (`octagon` + `#9B3333`). `serSU` continues to use the same border colour
  but the shape qualifier (ellipse vs octagon) keeps the two unambiguous.
- `_PALETTE_DISPATCH_RULES` (exporter) extended with `RSF` (`^RSF\d+$` +
  octagon) and `serUSD` (`^USD\d+$` + ellipse) rules. Order preserves the
  first-match-wins contract: the new `serUSD` rule sits next to the
  existing `USD` roundrectangle rule, the new `RSF` rule next to `SF`/`VSF`.
- `_REQUIRED_PALETTE_TYPES` now includes `RSF` and `serUSD`, so a future
  palette template that drops either stencil triggers the existing
  `S3DgraphyPaletteWarning` plus default-visual-properties backfill rather
  than silently degrading.
- `NodeRegistry._default_visual_properties_dict()` ships fallback
  `NodeVisualProperties` for `RSF` and `serUSD` so the registry never
  returns `None` for these types even when the palette resource is
  unreachable.
- `s3Dgraphy_node_datamodel.json` bumped to internal version `1.5.4`
  (description annotated with the RSF addition). The package-level
  `__datamodel_version__` (`1.5.5`, connections datamodel) is intentionally
  unchanged — it is governed by a separate file.
- `em_visual_rules.json` bumped to internal version `1.5.2` with a
  changelog entry for the RSF style.

### Changed
- **GraphML export — semantic dispatch for stratigraphic node types**. The
  stratigraphic export pipeline (`exporter/graphml/node_registry.py`) now
  selects palette template elements by `<y:NodeLabel>` pattern matching
  (e.g. `USM\d+` rectangle → `US`, `USM\d+` ellipse → `serSU`,
  `USV\d+` parallelogram → `USVs`, `USV\d+` hexagon → `USVn`,
  `USV\d+` ellipse → `serUSVn`) instead of the GraphML-internal id
  (`n1..n9`). This aligns the export side with the existing semantic
  import logic (`utils/utils.py::convert_shape2type`), decouples the
  palette visual ordering from the writer, and removes the silent
  degradation that occurred when a node label could not be matched
  after the palette was reordered in yEd.

### Fixed
- Unrecognised palette labels in export no longer fall back silently to
  `US` with a white/red rectangle. The new dispatch emits an explicit
  `S3DgraphyPaletteWarning` (subclass of `UserWarning`) indicating the
  label and the chosen fallback, asking the caller to register the
  pattern in `node_registry._PALETTE_DISPATCH_RULES`.
- The registry also warns at load time if the palette template ships
  without one of the canonical stratigraphic stencils (`US`, `serSU`,
  `USD`, `USVs`, `USVn`, `serUSVn`, `SF`, `VSF`, `TSU`); missing types
  are backfilled from the hardcoded defaults so callers never get
  `None` for a known stratigraphic type.

### Migration notes
- No public API change. `NodeRegistry`, `get_visual_properties()`,
  `get_shape_for_type()`, `get_colors_for_type()` keep their
  signatures. Round-trip identity preserved for all existing GraphML
  fixtures shipped in this repository, including the live
  `templates/em_palette_template.graphml`.
- Tools generating palette templates with non-canonical labels (e.g.
  `MyCustomUS01`) should add their pattern to
  `_PALETTE_DISPATCH_RULES` in 0.1.42 to avoid the new
  `S3DgraphyPaletteWarning` and obtain correct visual rendering.
- The new public symbol `S3DgraphyPaletteWarning` (subclass of
  `UserWarning`) can be used by downstream code (Blender add-ons,
  CI gates) to filter or escalate palette mismatches via the standard
  `warnings` module.

### Tests
- New `test_palette_dispatch.py` covers: round-trip identity per
  stratigraphic type (US, USVs, USVn, SF, VSF, **RSF**, USD,
  **serUSD**, serSU, serUSVn, TSU), live-template backward
  compatibility, order independence (palette with shuffled `<node id>`
  still resolves to the right types), `S3DgraphyPaletteWarning`
  emission on unknown `node_type`, and missing-required-type detection
  with default backfill.
- Dedicated tests for the RSF / serUSD additions: class registration
  (`STRATIGRAPHIC_CLASS_MAP`), dispatch table content, USD-vs-serUSD
  shape disambiguation, `convert_shape2type` round-trip on the new
  rules, and `em_visual_rules.json` carrying the RSF and serUSD
  styles. All 47 palette-dispatch tests + 7 classification tests pass.

### Originating analysis
- Architectural audit `PALETTE_AUDIT.md` (May 2026, EM-blender-tools
  repo): identified the export-side positional dispatch as a
  silent-failure fragility for palette reordering at the 1.5 cut.
  Variante A applied; the related `serUSVs` synthesis (cloned from
  `serUSVn` with blue border) is preserved unchanged. The audit also
  surfaced the `serUSD` export-side asymmetry — closed in this
  release.
- DP-26 (spolia project, EM dev tracker): the typological framing of
  RSF as a re-used physical element with a stratigraphic identity of
  its own (real / non-series), distinct from `SF` (in-situ
  repositionable) and `VSF` (virtual reconstruction). Last
  Development Project before the EM 1.5 cut; formalised here as a
  first-class stratigraphic subtype.

## [0.1.41] — 2026-05-09

### Added — `LocationNodeGroup`: spatial / locational membership

A new group-node type closing the structural gap between activity-based and
location-based grouping in the EM formalism. Originating discussion:
[issue #5](https://github.com/zalmoxes-laran/s3Dgraphy/issues/5) by
[@enzococca](https://github.com/enzococca) — the PyArchInit integration
exposed cases (toponyms, study sectors, functional rooms — and walls between
two rooms) where activity grouping alone was not enough. Many thanks to Enzo
for the precise framing.

- **New class `LocationNodeGroup`** in `src/s3dgraphy/nodes/group_node.py`
  (subclass of `GroupNode`). Re-exported from `s3dgraphy.nodes` and listed
  in the package `__all__`.
  - Required field `kind ∈ {toponym, study, functional}` — the *epistemic
    plane* of the location. The three coexist on the same node and may
    compose. `ValueError` if the kind is not in the allowed set.
  - Field `propagation` defaulting to `"additive"` (memberships compose;
    none overrides) — distinct from `EpochNode`, which is substitutive
    (finest-grained wins).
  - Hierarchy: a `LocationNodeGroup` can itself be `is_in_location` of
    another `LocationNodeGroup` (Pompei → Sector 4 → Casa del Fauno →
    Room 12).
- **Datamodel JSON v1.5.3** (`JSON_config/s3Dgraphy_node_datamodel.json`):
  registers `LocationNodeGroup` under `group_nodes.GroupNode.subtypes`
  with abbreviation `LNG`, label `"Location Node Group"`, and the full
  `kind` / `propagation` field schema. CIDOC-core mapping: `E53 Place`,
  classified by `E55 Type` instances via `P2_has_type`. The `propagation`
  field is explicitly marked as schema-level metadata, *not* serialised to
  the triplestore (no per-instance triple).
- **Connections datamodel JSON v1.5.5**
  (`JSON_config/s3Dgraphy_connections_datamodel.json`): new `is_in_location`
  edge with `includes_location` reverse, full `allowed_connections.source`
  list (`StratigraphicNode`, `ParadataNode`, `ParadataNodeGroup`,
  `DocumentNode`, `ExtractorNode`, `CombinerNode`, `PropertyNode`,
  `LocationNodeGroup`) and `target = LocationNodeGroup`. Context-sensitive
  CIDOC mapping: `P53_has_former_or_current_location` for
  *node → location* and `P89_falls_within` for the recursive
  *location → location* hierarchy. Optional edge attribute
  `is_primary: bool` (default `false`) declared in the new `attributes`
  block on the edge definition; one `is_primary=true` edge per source is
  the rendering hint for em-graph yEd group-folder selection.
- **Visual rules v1.5.1** (`JSON_config/em_visual_rules.json`): new
  `LocationNodeGroup` entry — dashed round-rectangle, fill `#F5F5F5`,
  label at top, with per-`kind` border colour modifiers
  (toponym `#888888`, study `#3A5A8C`, functional `#000000`). New
  `is_in_location` edge style with a `primary_modifier` override
  (`width: 2`, `color: #444444`, solid line) applied when
  `is_primary=true`.

### Triplestore mapping discipline

Every new identifier carries either a CIDOC-core mapping (preferred) or a
proposed `s3d:` extension URI with an explicit `extension_status: proposed`
marker and a written `rationale` justifying why CIDOC-core (and the
existing extensions CRMarchaeo / CRMsci / CRMinf) do not already cover the
concept:

- `LocationNodeGroup` itself maps to vanilla `E53 Place`
  (no new s3d class).
- `kind` is expressed by `P2_has_type` to one of three reserved
  `E55 Type` instances: `s3d:KindToponym`, `s3d:KindStudy`,
  `s3d:KindFunctional`. CIDOC-native composition; no new property URI.
- `is_in_location` reuses CIDOC-core `P53` / `P89`. No s3d predicate.
- `is_primary` edge attribute is the only genuinely new RDF property —
  carried as `s3d:isPrimary` with rationale "no CIDOC equivalent —
  disambiguates UI rendering of m:n membership on yEd group folders".
- `propagation` is declared schema-level only and is not serialised to
  triples.

> **Stability disclaimer.** The `s3d:` namespace identifiers introduced in
> this release (`s3d:KindToponym`, `s3d:KindStudy`, `s3d:KindFunctional`,
> `s3d:isPrimary`) are *candidate primitives* for a forthcoming CIDOC-S3D
> extension (in the spirit of CRMarchaeo / CRMsci / CRMinf). Their
> stability is **proposed**, not final. Consumers should expect potential
> URI rename when the extension is formalised, and read the
> `extension_status: "proposed"` field in the JSON datamodel as a
> machine-readable marker of this commitment level.

### Documentation

The `extendedmatrix-doc` manual gains a new `Location` concept page (the
first to follow the *concept-first* template: overview → em graph → s3d
graph → em_data → CIDOC mapping → examples) and a new general `em_data`
section that the page cross-links to. The AI / StratiMiner section in
`knowledge_tree.rst` now points to `em_data` for the workbook conventions.

### Naming conventions

Going forward, single-axis sub-discrimination on nodes uses the field name `kind` (Python instance attribute and JSON datamodel field). The existing instance attributes `RepresentationNode.type` and `SemanticShapeNode.type` are preserved for backward compatibility; **new code should prefer `kind`** to avoid collision with the structurally reserved `node_type` (class identity, registered in `Node.node_type_map`) and with `rdf:type` / `P2_has_type` in the CIDOC mapping path.

Multi-axis classification (cf. `DocumentNode.role` / `content_nature` / `geometry`) continues to use semantically named axes — `kind` is reserved for single-axis cases.

A future release may unify `RepresentationNode.type` and `SemanticShapeNode.type` under `kind` with a deprecation cycle; this 0.1.41 makes no breaking changes.

### Added — Stratigraphic classification refactor (2026-04)

- **Datamodel JSON v1.5.2** (patch, additive)
  (`JSON_config/s3Dgraphy_node_datamodel.json`): every stratigraphic
  subtype now carries two additional fields — `family`
  (`"real"` / `"virtual"` / `null`) and `is_series` (bool). Bumped
  from v1.5.1 as a patch — these are additive metadata fields that
  existing consumers ignore, no breaking changes to the formalism
  (the EM formal language stays at 1.5). Lets downstream tools
  (GraphML importer BR-handling, EM-blender-tools pickers /
  filters / material maps) consume classification metadata without
  hardcoding type lists.
- **`s3dgraphy.classification` module**: JSON-driven API re-exported
  from the package root:
  - `get_family(node_type)` / `is_real(nt)` / `is_virtual(nt)` /
    `is_series(nt)` accessors reading the datamodel JSON.
  - `get_subtype_info(nt)` / `iter_subtypes()` for metadata walks.
  - Frozenset constants computed from the JSON:
    `REAL_US_TYPES`, `VIRTUAL_US_TYPES`, `SERIES_US_TYPES`,
    `ALL_US_TYPES`.
- **Negative Stratigraphic Unit**: new
  `NegativeStratigraphicUnit` class in
  `nodes/stratigraphic_node.py` with `node_type="USN"`,
  classified as `family="real"` / non-series. Surfaced in
  `em_visual_rules.json` with a dashed-rectangle variant so it
  renders distinct from a positive US in yEd. Replaces the ad-hoc
  `US_NEG` placeholder that lived only in EM-blender-tools.
- **Extended `STRATIGRAPHIC_CLASS_MAP`** (`utils/utils.py`): added
  `UL → WorkingUnit` (was silently missing from the map, causing
  downstream factories to fall back to the generic
  `StratigraphicNode`) and `USN → NegativeStratigraphicUnit`.
- **New qualia `proxy_geometry`** in
  `JSON_config/em_qualia_types_additions.json` under
  `physical_material.dimensional` (alongside `area` / `volume`) —
  canonical property name for the 7-point bounding box that the
  Proxy Box Creator (EM-blender-tools) writes as a PropertyNode.
- **Test `test_stratigraphic_classification.py`**: locks seven
  invariants between the Python map and the JSON datamodel:
  abbreviations aligned both ways, every subtype declares a valid
  `family`, `is_series` matches the `ser` prefix convention, the
  classification accessors agree with the JSON, USN registered
  correctly, pre-computed sets consistent with per-node
  accessors, and `iter_subtypes` yields every entry. Brings the
  suite to 20/20 green.

### Fixed — GraphMLPatcher paradata rendering (2026-04)

- **Extractor / Combiner NodeLabel** positioned at Corner-NorthWest
  via `modelName="corners"` + `modelPosition="nw"` +
  `borderDistance="0.0"` + `underlinedText="true"` — matches the
  reference TempluMare graphml and the full-export
  `node_generator.py`. Previously the patcher wrote neither
  attribute, so yEd defaulted to `Internal:Center` and the
  extractor id overlapped the SVG glyph.
- **ParadataNodeGroup positioning**: the `_add_group_realizer`
  Geometry was hardcoded to `(0, 0)`. The new
  `_seed_group_realizer_positions` rewrites the realizers'
  `x`/`y` with the epoch-derived position returned by
  `_calculate_node_position`, so PD groups are anchored in the
  right swimlane row instead of floating outside the Table.
- **ParadataNodeGroup / ActivityNodeGroup containment**:
  `add_new_nodes` now runs as a two-pass routine — first inserts
  new group containers (indexing their nested `<graph>` elements
  plus those of pre-existing groups discovered through
  `original_id`), then routes every other new node into the
  matching container based on `is_in_paradata_nodegroup` /
  `is_in_activity` edges. Result: US + PD + Extractors + Combiner
  + PropertyNode + Document-instance are physically nested under
  the correct yEd group at save time, not dumped in the top-level
  graph.
- **`_calculate_node_position` for ParadataNodeGroup**: special
  case that inherits the host US's epoch via
  `has_paradata_nodegroup` (reverse lookup) so the Y coordinate
  is the US's swimlane band, not `(0, 0)`.

### Added

- **Hybrid-C auxiliary lifecycle (Phase 1 + 3)**. New module
  ``s3dgraphy.transforms.aux_tracking`` providing the bookkeeping
  primitives that let the GraphML exporters distinguish **graph-
  native** content from **auxiliary-injected** content (DosCo, emdb,
  pyArchInit, sources-list, resource-folders):
  - ``mark_as_injected(obj, injector_id)`` / ``is_injected(obj)``
    — tag enrichment children (PropertyNodes, LinkNodes, etc.)
    added by an auxiliary.
  - ``record_attribute_override(node, attr, injector_id, original_value)``
    + ``freeze_aux_value(node, attr)`` — capture the pre-aux value
    when an auxiliary mutates a host-node attribute (e.g. DosCo
    setting ``DocumentNode.url``).
  - ``apply_override_reversal_policy(graph)`` — per-attribute
    policy used by the **volatile** save: if the current value
    still matches the aux value, revert to the pre-aux original;
    if the user re-edited the attribute afterwards, keep the
    user value and drop the override record.
  - ``strip_injected_content(graph)`` — remove every node/edge
    tagged ``injected_by`` (volatile save).
  - ``clear_aux_tags(graph)`` — drop all ``injected_by`` and
    ``_aux_overrides`` records (bake save, promotion to graph-
    native).
  - Orphan reporting: ``push_orphan`` / ``iter_orphans`` /
    ``clear_orphans`` — track aux rows whose key ID did not match
    any host in the graph (UI surfacing deferred to Phase 2).
- **``GraphMLExporter.export(path, persist_auxiliary=False)``** and
  **``GraphMLPatcher.patch(path, persist_auxiliary=False)``** new
  ``persist_auxiliary`` parameter:
  - ``False`` (default, **volatile**): apply the reversal policy
    and strip injected content before emitting. The on-disk
    GraphML reflects only graph-native state; on next reload the
    auxiliaries re-inject cleanly.
  - ``True`` (**bake**): emit everything verbatim and clear the
    ``injected_by`` / ``_aux_overrides`` bookkeeping. The
    enrichment layer becomes graph-native going forward.
- **User's Blender-native edits never lost**. The volatile save
  preserves new nodes the user adds in Blender (no ``injected_by``
  tag) and keeps attribute values the user manually re-edited
  after an auxiliary applied (detected by comparing current value
  to frozen aux value).
- Locked in by 7 unit scenarios in ``test_aux_tracking.py`` and 3
  end-to-end round-trips on the Great Temple GraphML
  (``test_aux_roundtrip_graphml.py``), covering scenarios α
  (volatile revert), β (user re-edit wins), γ (Blender-native
  additions survive) and bake-then-reload idempotence.
- **Phase 1b hookup plan** for the existing auxiliary importers
  (DosCo / emdb / pyArchInit / sources-list / resource-folders)
  documented in
  ``docs/dev-projects/HYBRID_C_PHASE_1B_IMPORTER_HOOKS.md``;
  code changes deferred to the next sprint.

### Changed

- **AI extraction prompt rewritten for the unified schema** (v5.0,
  breaking change). The StratiMiner prompt at
  ``s3dgraphy/data/AI_EXTRACTION_PROMPT_v4.md`` (filename kept for
  backward-compatible imports) now describes the single-file
  ``em_data.xlsx`` output with 5 sheets, explicit
  ``AUTHOR_KIND_N ∈ {author, extractor}`` distinguishing claims
  transcribed from the document author vs claims newly derived by the
  AI, and per-claim attribution on stratigraphic relations. Ships an
  updated validation script that checks cross-sheet referential
  integrity, duplicate triples, missing COMBINER_REASONING, and
  stratigraphic cycles. Also documents a **stratigraphy-only mode**
  for legacy archaeological databases where paradata attribution is
  not yet available (curator as sole author, no extractor chain).

### Added

- **GraphMerger extended for the paradata layer** (Phase B — xlsx ↔
  graphml merge). The existing ``s3dgraphy.merge.graph_merger.GraphMerger``
  now covers every node/edge class produced by the unified xlsx
  pipeline, not just stratigraphic units. New conflict types:
  - ``qualia_added``, ``qualia_changed``,
    ``qualia_attribution_added`` — PropertyNode claims (matched per
    ``(unit_name, property_type)``).
  - ``author_added`` / ``author_changed`` and ``document_added`` /
    ``document_changed`` — catalog entries matched by short code
    (``A.01``, ``D.01``). ``AuthorAINode`` vs ``AuthorNode`` kind drift
    is flagged but not auto-applied.
  - ``epoch_added`` / ``epoch_changed`` — Epoch matched by name;
    differences in ``start_time`` / ``end_time`` / color are each
    reported as a dedicated conflict with a ``subfield`` hint in
    ``Conflict.extra``.
  - ``edge_attribution_added`` / ``edge_attribution_changed`` — diffs
    on the ``edge.attributes`` dict (``authored_by_N``,
    ``authored_kind_N``, ``document_N``) of relation edges; lets the
    merger propagate per-claim relation attribution from an incoming
    xlsx into an existing graphml.
  - ``Conflict.extra: Dict[str, Any]`` — new field on the dataclass
    (default empty) that carries per-conflict payload (property type,
    target endpoint, attribute key, subfield, …). Backward-compatible
    for existing callers.
  - ``apply_resolutions`` handles all new types: qualia changes copy
    the full PropertyNode subtree (PN + provenance chain) from the
    incoming graph, with catalog nodes (Author / Document) reused
    from the host to avoid duplication. Catalog/epoch add-and-change
    apply directly; edge attribution writes to ``edge.attributes``.
  - Locked in by 8 synthetic scenarios (``test_graph_merger.py``)
    plus a real-data smoke test on the Templu Mare graphml
    (export → modify → re-import → merge) covering author rename,
    author addition, and new qualia row.
- **Unified xlsx writer** (Phase B — complete round-trip). New module
  ``s3dgraphy.exporter.unified_xlsx_exporter`` exporting a full graph
  back to an ``em_data.xlsx`` with the 5-sheet schema. It is the
  inverse of :class:`UnifiedXLSXImporter`: walks the in-memory graph
  and emits Units / Epochs / Authors / Documents catalogs plus a
  long-table Claims sheet that reconstructs the paradata chain
  (``PropertyNode → has_data_provenance → Extractor / Combiner →
  has_author``) as ``(EXTRACTOR_i, DOCUMENT_i, AUTHOR_i,
  AUTHOR_KIND_i)`` triples. Combiner rows get 2 triples plus
  ``COMBINER_REASONING``; stratigraphic relations read their
  attribution from the edge's ``attributes`` dict. Only the
  canonical direction of each relation pair is emitted (``overlies``
  but not ``is_overlain_by``) — the inverse is recovered at
  re-import. Disambiguates duplicate unit names with a short uuid
  suffix and logs a warning so round-trip fidelity is preserved even
  on legacy graphs with data-quality issues. Legacy GraphML sources
  whose PropertyNodes all carry the sentinel ``property_type =
  "string"`` are normalized: the actual qualia type comes from
  ``PN.name`` and the value from ``PN.description`` when
  ``PN.value`` is empty. Locked in by 4 round-trip scenarios in
  ``test_unified_xlsx_roundtrip.py`` covering the resolver
  fingerprint invariance, Combiner preservation, relation
  attribution preservation, and a real-data smoke test on the Great
  Temple graphml (102 units → export → re-import → 102 units).
- **Unified xlsx pipeline** (Phase B — DP-02 / DP-49). Single-file
  replacement for the legacy ``stratigraphy.xlsx`` + ``em_paradata.xlsx``
  two-step flow:
  - New template ``s3dgraphy/templates/em_data_template.xlsx`` with
    5 typed sheets: ``Units`` (skeleton), ``Epochs`` (swimlanes),
    ``Claims`` (long-table, one row per asserted fact), ``Authors``
    (normalized catalog with a ``KIND`` column distinguishing human
    authors from AI extractors), ``Documents`` (normalized catalog).
  - New importer ``s3dgraphy.importer.unified_xlsx_importer.UnifiedXLSXImporter``
    builds a complete graph from one xlsx in a single pass: author /
    document catalogs, epochs, stratigraphic units, and all claim
    rows (scalar qualia, temporal qualia, epoch membership via
    ``belongs_to_epoch``, and stratigraphic relations via
    ``is_after`` / ``overlies`` / ``cuts`` / ``fills`` / ``abuts`` /
    ``bonded_to`` / ``equals``). Each claim row carries its own
    attribution triple(s): ``EXTRACTOR_i`` / ``DOCUMENT_i`` /
    ``AUTHOR_i`` / ``AUTHOR_KIND_i``. Relational claims store the
    attribution on the edge's ``attributes`` dict; PropertyNode
    claims use the standard paradata chain.
  - Multi-source (Combiner) rows: when both
    ``EXTRACTOR_1`` / ``EXTRACTOR_2`` and ``COMBINER_REASONING`` are
    populated, a ``CombinerNode`` is inserted between the
    ``PropertyNode`` and the two ``ExtractorNode`` instances.
  - 6 synthetic test scenarios in ``test_unified_xlsx_importer.py``
    (catalog creation, relation attribution, SL_PD chronology
    override, author vs AI-extractor attribution, combiner structure,
    A.1 compaction invariance on xlsx-sourced graphs).
- **Diagnostics attribution now follows the ``has_data_provenance``
  chain** (xlsx pipeline). Previously ``attribute_property_node``
  walked only the ``is_in_paradata_nodegroup`` sibling-extractor
  path, which works for yEd-sourced graphs but misses the xlsx
  in-memory pattern (``PN → has_data_provenance → Extractor →
  has_author``, or through a ``CombinerNode``). The walk order is now:
  direct ``has_author`` → provenance chain (extractor / combiner) →
  paradata-group siblings. Unifies attribution coverage across import
  sources.
- **Chronology diagnostics with claim attribution** (DP-02 / DP-32
  Phase A.2). New module ``s3dgraphy.diagnostics`` providing:
  - ``attribute_property_node(graph, pn)`` and
    ``attribute_temporal_claim(graph, strat_node, temporal_type)`` —
    walk the paradata chain to find who made a specific claim. Resolution
    order: direct ``has_author`` on the PropertyNode → sibling
    ``ExtractorNode`` in the containing ParadataNodeGroup →
    ``has_author`` on that extractor. Returns ``(display_text, kind,
    author_uuid)`` where ``kind`` is ``"author"`` (transcribed from the
    PDF author; the claim is in the source) or ``"extractor"`` (derived
    by an AI tool like StratiMiner; the claim is new).
  - ``detect_stratigraphic_cycles(graph)`` — Tarjan SCC over the
    ``is_after`` / ``cuts`` / ``overlies`` / ``fills`` / ``is_before``
    edges, returning every loop (and self-loop) in the stratigraphic
    order. AI extractors occasionally close these loops; the BFS in
    ``_propagate_tpq_taq`` already survives them via a visited set but
    the user must be notified.
- **Paradox warnings now carry attribution**. The ``[chronology
  paradox]`` messages emitted by ``_propagate_tpq_taq`` include a
  trailing ``[attributed to <name> (<kind>)]`` suffix when the
  offending PropertyNode can be traced to an author or an extractor.
  This lets the user decide whether to audit the original document
  author or the AI extractor that produced the bad inference.
- **Stratigraphic cycle warnings emitted automatically**.
  ``Graph.calculate_chronology()`` now runs a cycle-detection pass
  before TPQ/TAQ propagation and appends one
  ``[stratigraphic cycle]`` warning per loop, with per-node
  attribution so the user can pinpoint the right extractor. Tests:
  9 scenarios in ``test_diagnostics.py`` covering human/AI
  attribution, sibling-extractor resolution, missing attribution,
  2- and 3-node cycles, linear chain (no false positives), end-to-end
  paradox warning with attribution.

- **Reverse-propagation compaction** (DP-32 / DP-49 Phase A.1). New module
  ``s3dgraphy.transforms.compact`` exposing three functions for pre-export
  metadata formalization:
  - ``prune_redundant_propagative_edges(graph)`` — removes per-node
    ``has_author`` / ``has_license`` / ``has_embargo`` edges and
    ``has_property`` edges to temporal PropertyNodes when the
    swimlane-level resolver returns the same value anyway.
  - ``hoist_propagative_metadata(graph)`` — when every stratigraphic
    unit whose primary swimlane is Epoch E declares the same single
    target for ``has_author`` / ``has_license`` / ``has_embargo``, promotes
    the declaration to an SL_PD anchored to E (created if missing) and
    removes the per-unit edges. Chronology is pruned but never hoisted
    (PropertyNode deduplication is out of scope).
  - ``compact_propagative_metadata(graph)`` — runs hoist then prune.
  Both passes preserve the resolver output for every node (lossless
  reformulation). Conservative rules: no hoist on partial overlap, no
  hoist on divergent targets, no hoist on multi-epoch nodes
  (``survive_in_epoch``). Locked in by 8 synthetic scenarios in
  ``test_compact_metadata.py`` including idempotence of
  ``compact_propagative_metadata``.
- **Dashed-connector reclassification** (DP-51). The yEd palette has no
  dedicated connector style for ``has_author`` / ``has_license`` /
  ``has_embargo``. The importer's ``enhance_edge_type`` now inspects the
  target class of a ``has_data_provenance`` edge (the dashed connector's
  default semantic): ``AuthorNode`` / ``AuthorAINode`` → ``has_author``,
  ``LicenseNode`` → ``has_license``, ``EmbargoNode`` → ``has_embargo``.
  Covers legacy EM graphs that connect strat units directly to paradata
  image nodes with a generic dashed edge.

### Refined

- **EpochNode queries report [swimlane], never [node]**. When the resolver
  is invoked directly on an EpochNode, node-level and swimlane-level
  collapse to the same lookup (the Epoch IS the swimlane). The generic
  resolver now skips the node-level call for Epoch inputs and always
  tags the result ``"swimlane"`` (or ``"graph"`` for canvas-header
  fallbacks). Matches the Epoch Manager UI mental model where values
  shown on an epoch come from the swimlane-level Paradata Node Group.
- **SL_PD auto-edge supports top-level layout** (DP-19). The paradata
  auto-edge inference previously required the SL_PD group to be XML-
  nested inside an EpochNode's swimlane column. Now also supported: an
  SL_PD that sits at the canvas top level and draws an explicit
  ``has_first_epoch`` edge to the target Epoch, with its children
  connected via ``is_in_paradata_nodegroup``. Resolution order for the
  containing group: immediate XML parent → ``is_in_paradata_nodegroup``
  edge. Resolution order for the anchor: first non-ParadataNodeGroup XML
  ancestor → ``has_first_epoch`` outgoing from the group. The pass is
  now scheduled **after** ``connect_nodes_to_epochs`` so that a
  Y-position-derived ``has_first_epoch`` from the SL_PD is available.
- **Swimlane chronology honours SL_PD PropertyNodes**. The
  ``absolute_time_start`` / ``absolute_time_end`` rules' swimlane
  getters (``_epoch_start`` / ``_epoch_end``) now prefer a PropertyNode
  attached to the Epoch (typically auto-edged from an SL_PD) over the
  header ``epoch.start_time`` / ``end_time`` declared in the yEd
  swimlane title. A stratigraphic unit in that epoch therefore inherits
  the refined window when a PropertyNode is declared in the
  swimlane-level paradata group. The ``[chronology mismatch]`` warning
  still surfaces header/PN disagreements so the user can reconcile yEd.

### Changed

- **Dropped legacy ``absolute_start_date`` / ``absolute_end_date``
  aliases** across the codebase. The canonical (and sole) pair of
  chronology qualia is now ``absolute_time_start`` /
  ``absolute_time_end``. Consumers updated: the EM-blender-tools
  PropertyGroup fields (``em_base_props.py``, ``document_manager/data.py``,
  ``document_manager/ui.py``, ``paradata_manager/ui.py``,
  ``populate_lists.py``), the s3dgraphy core-concepts and operators-guide
  docs, and the current AI extraction prompt (v4). Existing GraphML
  sources with the old names must be migrated manually. Archived AI
  prompts v2/v3 are left as-is.

### Refined

- **EpochNode resolves as its own swimlane** (DP-32 Priority 4). Passing an
  ``EpochNode`` directly to ``resolve`` / ``get_property`` now yields the
  expected swimlane-level value instead of ``None``. The swimlane iterator
  in ``resolvers.property_resolver`` short-circuits to ``[epoch]`` when the
  input is itself an EpochNode, so chronology (``absolute_time_start`` /
  ``absolute_time_end``), ``author``, ``license`` and ``embargo`` are all
  reachable on epochs without a dedicated code path in every consumer. The
  Epoch Manager UI's ``epoch.start_time``/``end_time`` workaround is no
  longer needed. Strat-unit resolution is unchanged. Locked in by a new
  scenario in ``test_chronology_resolver.py`` (10 scenarios total).
- **Multi-author resolution**. ``AUTHOR_RULE`` at node- and swimlane-
  level now follows *every* ``has_author`` edge, not just the first one,
  and joins the display values with ``" ; "``. Duplicate display strings
  are deduplicated while preserving edge order.
- **Author display uses the description field**. The 1.5 dev9 yEd
  palette convention is ``AuthorNode.name = "A.01"`` (short code) and
  ``AuthorNode.description = "Giulia Rossi, ORCID:…"`` (human content).
  ``_format_author`` now prefers the description; falls back to
  ``data["name"] + data["surname"]``; last resort is the code in
  ``node.name``.
- **Description marker stripped at import**. The ``_s3d_node_type:<X>``
  round-trip marker is scrubbed from the description when the importer
  creates Author/AuthorAI/License/Embargo nodes, so panels never leak
  the technical marker into the UI.
- **Import-time warning for epoch chronology mismatch**. After auto-
  edging the paradata groups, the importer checks every EpochNode for a
  conflict between the swimlane-header times (``epoch.start_time`` /
  ``epoch.end_time``) and a PropertyNode declared inside an SL_PD.
  When they disagree, a ``[chronology mismatch]`` warning is pushed to
  ``graph.warnings`` so the user can reconcile the source in yEd. The
  resolver already preferred the PropertyNode; this surfaces the
  inconsistency instead of silently hiding it.

### Added

- **GraphML export of paradata image nodes** (AuthorNode, AuthorAINode,
  LicenseNode, EmbargoNode).
  - New module ``exporter/graphml/palette_resources.py`` parses
    ``templates/em_palette_template.graphml`` once at import time and
    exposes, per paradata node class, the label prefix, the refid used in
    the palette, and the verbatim ``<y:Resource>`` payload. Changing an
    icon in yEd requires **no Python change** — just re-save the palette
    template.
  - New generator ``exporter/graphml/paradata_image_generator.py``
    (``ParadataImageNodeGenerator``) emits the four ``<node>`` XML
    elements with a correct ``<y:ImageNode>`` + label prefix + refid, and
    adds an explicit ``_s3d_node_type:<NodeType>`` marker in the node
    description for bulletproof round-trip.
  - ``GraphMLPatcher`` now dispatches AuthorNode / AuthorAINode /
    LicenseNode / EmbargoNode to the new generator when patching an
    existing file. If the destination file already contains an
    ImageNode whose label prefix matches, its refid is reused; otherwise
    the matching ``<y:Resource>`` is injected from the palette template
    into the file's ``<y:Resources>`` block under a fresh refid.
  - Round-trip smoke test ``test_paradata_image_roundtrip.py``:
    generates a minimal GraphML from scratch containing one of each of
    the 4 paradata image nodes (resources embedded from the palette),
    re-imports it, and verifies the 4 classes come back intact.

### Changed

- **Unified naming to ``absolute_time_start`` / ``absolute_time_end``**
  (EM qualia standard). The rename touches:
  - ``resolvers.builtin_rules``: the two temporal PropagationRules now
    carry ids ``absolute_time_start`` / ``absolute_time_end`` (previously
    ``chronology_start`` / ``chronology_end``). Consumer code that called
    ``Graph.get_property(node, "chronology_start")`` must use the new
    id. Internal attributes ``CALCUL_START_T`` / ``CALCUL_END_T`` on
    resolved nodes are unchanged.
  - Node-level seed detection: the temporal PropertyNode is now matched
    on name/type ``absolute_time_start`` / ``absolute_time_end``
    (previously ``absolute_start_date`` / ``absolute_end_date``).
  - ``JSON_config/em_qualia_types.json``: temporal qualia entries
    renamed to match.
  - Warnings emitted by the paradox detector and the companion test
    suite updated.

### Refined

- **Auto-edge inference is now scoped to FREE paradata groups** (those
  with no incoming ``has_paradata_nodegroup`` edge AND whose name
  starts with the ``SL_`` prefix by EM convention). This prevents the
  importer from double-wiring the DP-43 node-level paradata groups
  (``USV104_PD``, ``SU001_PD``, …) which are already handled by the
  pre-existing ``Graph.connect_paradatagroup_propertynode_to_stratigraphic``
  pathway.
- **Auto-edge now also covers PropertyNode** (``has_property``) in
  addition to the four paradata image nodes (Author / AuthorAI /
  License / Embargo). A PropertyNode called ``absolute_time_start``
  placed inside a swimlane-level SL_PD is therefore automatically
  connected to the enclosing EpochNode, which means the DP-32
  chronology resolver sees it as a node-level seed without the author
  having to draw the edge explicitly in yEd.
- **Hash-based paradata icon detection removed.** Palette PNGs may be
  redrawn or re-exported between versions (and each yEd save can
  perturb the base64 payload); the stable convention is the label
  prefix (same strategy already used for ``D.`` / ``C.``). Detection
  order is now: explicit ``_s3d_node_type:`` marker → ``<y:ImageNode>``
  + known label prefix. ``em_palette_icons.json`` shrinks to just the
  ``label_prefixes`` map.

### Added

- **Auto-inference of ``has_author`` / ``has_license`` / ``has_embargo``
  edges from ParadataNodeGroup membership** (DP-19 / DP-43 groundwork).
  After parsing a GraphML file, the importer runs a post-processing pass
  that, for every ``AuthorNode`` / ``AuthorAINode`` / ``LicenseNode`` /
  ``EmbargoNode`` found, walks the XML parent chain upward and emits the
  corresponding edge from the **nearest graph-visible non-
  ParadataNodeGroup ancestor**. Concretely:
  - An Author/License/Embargo node inside a swimlane-level
    ParadataNodeGroup (SL_PD) attached to a ``EpochNode`` → edge from
    the ``EpochNode`` (swimlane-level resolver now active).
  - An Author/License/Embargo node inside a node-level
    ParadataNodeGroup (DP-43 ``US_01_PD``, ``USV104_PD``, …) nested in
    a stratigraphic unit → edge from the stratigraphic unit
    (node-level resolver now active).
  - An Author/License/Embargo node inside a canvas-level group (parent
    is the top-level graph, not a node) → no edge created; the value
    is already reachable via the DP-40 canvas-header attributes on
    ``graph.attributes["author_name"|"license"|"embargo"]``.

  The inference never overwrites existing edges (duplicate-safe) and
  adds a ``[paradata auto-edge]`` warning summarizing how many edges
  were inferred.
- **Paradata image nodes wired into the GraphML importer** (DP-51
  groundwork). The importer now detects and instantiates the four
  palette-based paradata nodes:
  - ``AuthorNode`` — label prefix ``A.`` (human author)
  - ``AuthorAINode`` — label prefix ``AI.`` (AI-assisted author, new
    subclass of ``AuthorNode``)
  - ``LicenseNode`` — label prefix ``LI.``
  - ``EmbargoNode`` — label prefix ``EB.``

  Detection is **multi-signal** with a Hard > Medium > Weak priority
  chain, matching the pattern used for ``EM_check_node_continuity``:

  1. Explicit ``_s3d_node_type:<NodeType>`` marker in the node's
     description or URL field (round-trip aid).
  2. ``<y:ImageNode>`` + ``<y:Image refid="N"/>`` where the resource's
     SHA-256[:16] (post XML-entity-decoding, whitespace stripped) matches
     an entry in ``JSON_config/em_palette_icons.json``. This is robust
     to label renames and typos.
  3. ``<y:ImageNode>`` + label prefix match (``AI.``/``A.``/``LI.``/``EB.``
     checked longest-first to avoid ``AI.`` being shadowed by ``A.``).

  The dispatcher kicks in just before the generic fallback node path so
  existing stratigraphic / property / extractor / combiner / continuity
  detection is unchanged.
- **``em_palette_icons.json``** — new configuration file indexing the
  stable SHA-256[:16] of each palette icon to the node type it
  represents. Adding a new palette icon is a JSON edit, no Python change.
- **``AuthorAINode`` subclass** of ``AuthorNode`` (``node_type =
  "author_ai"``) with ``model`` and ``prompt_reference`` fields. Because
  it inherits from ``AuthorNode``, all consumer code that uses
  ``isinstance(n, AuthorNode)`` keeps working.
- **Two new built-in propagation rules** in
  ``resolvers.builtin_rules``:
  - ``LICENSE_RULE`` — follows ``has_license`` edges at node/swimlane
    levels, falls back to ``graph.attributes["license"]`` at canvas
    level.
  - ``EMBARGO_RULE`` — follows ``has_embargo`` edges; graph-level
    fallback to ``graph.attributes["embargo"]``.
  - ``AUTHOR_RULE`` node-level and swimlane-level getters are now
    active: they follow ``has_author`` edges to
    ``AuthorNode``/``AuthorAINode`` instances and format the returned
    value as ``"Name Surname"``. Canvas-header fallback via
    ``author_name`` / ``author_surname`` is unchanged.

### Changed

- ``has_author`` connections datamodel entry now lists
  ``AuthorAINode`` as an explicit target and adds ``EpochNode`` to the
  allowed source list so the swimlane-level resolver can attach an
  author directly to an epoch.
- ``has_embargo`` connections datamodel entry: source widened from
  ``["LicenseNode"]`` to ``["Node", "GraphNode", "LicenseNode"]``. Now
  mirrors ``has_license`` so an embargo can be attached to the canvas,
  a license, or any node directly. Also aligns with the declared
  intent: "si possono usare collegati ad ogni tipo di nodo".

### Tests

- Extended ``test_chronology_resolver.py`` with two new scenarios:
  - ``run_license_embargo_rule_test``: graph-level (canvas header)
    fallback for license and embargo via ``Graph.get_property(..., "license")``
    and ``get_property(..., "embargo")``.
  - ``run_author_via_has_author_edge_test``: a node with its own
    ``has_author`` → ``AuthorNode`` overrides the graph-level canvas
    header author.
- Ad-hoc round-trip smoke test against
  ``TempluMare_EM_converted_converted 2.graphml``: the four SL_PD
  paradata nodes are parsed to the correct classes via the hash signal
  (strongest), without relying on the label prefix fallback.
- New synthetic test ``run_paradata_auto_edge_test``: builds a minimal
  GraphML with a ParadataNodeGroup (``#FFCC99`` background) nested
  inside a stratigraphic unit, containing an AuthorNode tagged with
  the explicit ``_s3d_node_type:AuthorNode`` marker. Verifies that the
  importer (a) detects the AuthorNode, (b) auto-infers the
  ``has_author`` edge from the US to the AuthorNode, and (c) the
  resolver then returns the author when ``get_property`` is called on
  the US.

### Added (earlier in this release)

- **Generic propagative property resolver** (`s3dgraphy.resolvers`, DP-32
  Layer A). New subpackage that formalizes the 3-level hierarchical
  resolution **node > swimlane > graph** used across the Extended Matrix
  metadata system.
  - `PropagationRule` dataclass describing how to look up a property at each
    level (`node_getter`, `swimlane_getter`, `graph_getter`, optional
    `swimlane_aggregate`).
  - `resolve(graph, node, rule, default=None)` and
    `resolve_with_source(...)` — walk the three levels and return the first
    non-null value (or the value plus the level it came from).
  - Registry: `register_rule`, `unregister_rule`, `get_rule`, `list_rules`.
  - Built-in rules registered on import (`resolvers.builtin_rules`):
    - `chronology_start` and `chronology_end` — reproduce the previous
      hardcoded seed logic exactly (verified by regression test).
    - `author` — graph-level fallback already active (reads Canvas Header
      `author_name` / `author_surname` from DP-40). Node-level and
      swimlane-level getters are stubs for DP-51 (AuthorNode in yEd) and
      DP-19 (Swimlane Paradata Node Group); both honor an explicit
      `attributes["author"]` override if an importer sets one.
- **`Graph.get_property(node, rule_id, default=None)`** — one-line
  convenience wrapper for consumers that want to resolve a registered
  property by id.
- **Coherence / paradox detection in chronology closure** (DP-32 Layer B,
  Hard policy). When the TPQ/TAQ propagation would overwrite a
  user-declared `absolute_start_date` / `absolute_end_date` seed with a
  stratigraphically-inconsistent value, the propagation is blocked at the
  conflicting node, the declared value is preserved, and a descriptive
  warning is appended to `graph.warnings`. BFS does not traverse through
  the conflicting node (Hard policy). Seeds that merely tighten derived
  (swimlane-fallback) values remain silent as before — only true paradoxes
  are flagged.

### Changed

- **`Graph._calculate_base_chronology`** is now a thin wrapper around
  `resolve(...)` using the built-in `chronology_start` and `chronology_end`
  rules. External behavior is unchanged (locked by the regression test in
  `test_chronology_resolver.py`).

### Tests

- New synthetic regression suite in the repo root
  (`test_chronology_resolver.py`) covering:
  1. Baseline chronology (node PropertyNode seed, swimlane fallback,
     `survive_in_epoch` extension, simple TPQ across `is_after`).
  2. TAQ reverse propagation (recent node's `absolute_end_date` tightens
     older nodes).
  3. Overlapping constraints (chain with both a start seed and a later end
     seed split the population into three coherent sub-ranges).
  4. Paradox detection (conflicting node-level seeds preserved, warning
     raised).
  5. `AUTHOR_RULE` cascade (node override > swimlane attribute > graph
     canvas header).
