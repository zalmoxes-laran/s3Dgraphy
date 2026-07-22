# HDT-O coverage in s3Dgraphy (P1-C)

Audit of HDT-O (ECHOES **D7.1**, May 2024) classes **HC1–HC20** and properties
**HP1–HP26+** against existing EM node/edge types. Scope of P1-C: *additive* —
add **only** the genuinely-missing, non-mappable classes as new node types (the
way `HDTNode → HC2` was seeded), gated out of the stratigrapher palette.

Namespaces already declared in `JSON_config/hdto_extension.ttl` (subset aligned
with D7.1); the RDF exporter emits a node's HDT-O type from its
`em_extension.uri` / `mapping.cidoc`.

Status legend: **mapped** = an existing EM node type already carries the class ·
**mappable** = an existing EM node covers it (annotate later, no new node) ·
**added** = new node type created in this session · **ontology-only** = RDF
superclass/infrastructure, no authoring node · **defer** = out of the core
authoring chain, add when a use-case needs it · **out-of-scope** = not an EM /
archaeology authoring concern.

## Classes (HC1–HC20)

| HC | Label | EM coverage | Status |
|----|-------|-------------|--------|
| HC1 | Heritage Entity | **`HeritageEntityNode`** (`hdto_nodes`, → `hdto:HC1` ⊂ `crm:E1`) | **added** |
| HC2 | Heritage Digital Twin | `HDTNode` (→ `hdto:HC2`) | mapped |
| HC3 | Tangible Aspect of an HC1 | specialization of HC1 | defer |
| HC4 | Intangible Heritage Entity | specialization of HC1 | defer |
| HC5 | Digital Representation | `RepresentationModelNode` family (`crmdig:D1`) | mappable |
| HC6 | Sensor | — | out-of-scope (IoT / SensorThings) |
| HC7 | Digital Audiovisual Object | `RepresentationModel*` covers 3D; AV n/a | defer |
| HC9 | Study | — | defer (research context) |
| HC10 | Heritage Valuation | — | defer |
| HC11 | Digital Twin Maintenance | — | defer (HDT lifecycle) |
| HC12 | Heritage Declaration Event | — | defer |
| HC13 | Project | — | defer (research-project context; candidate) |
| HC14 | Volatile Digital Object | superclass of HC2 (declared in `hdto_extension.ttl`; `HDTNode` `subclass_of` HC14) | ontology-only |
| HC15 | Persistent Digital Object | snapshot infrastructure (ttl) | defer / ontology-only |
| HC16 | Heritage Proposition Set | `GraphNode` = `em:EMGraph` (em.ttl declares `EMGraph ⊂ HC16`) | mapped |
| HC17 | Observation with Inference | `ParadataNode` (`crminf:I1_Argumentation`) — bridge noted in ttl | mappable |
| HC18 | Provenance Statement | `ExtractorNode`/`CombinerNode` (crminf provenance) | mappable / defer |
| HC19 | Provenance Assessment | — | defer |
| HC20 | Criminal Activity | — | out-of-scope |

> HC21–HC29 (SensorThings API module) are a separate D7.1 section, out of P1-C scope.

## Properties (HP1–HP26+) — mostly EDGES, not node types

The HDT granularity connectors already exist in
`s3Dgraphy_connections_datamodel.json` (no edge added this session — the HC1
chain works with them):

| HP | Label | EM edge | Status |
|----|-------|---------|--------|
| HP1 / HP1i | has digital twin / is digital twin of | `has_digital_twin` (Node → HDTNode) | present |
| HP3 / HP3i | (is/has) digital twin component of | `has_digital_twin_component` (HDTNode → HDTNode) | present |
| HP29 | has digital object part | `has_digital_object_part` (HDTNode → Representation*/Link) | present |
| HP33 / HP33i | contains / is proposition set of | `contains_proposition_set` (HDTNode → GraphNode) | present |
| HP9 / HP21 / HP22 | is visual repr. / is 3D repr. output of / represents | EM representation edges | mappable |
| HP2, HP4–HP8, HP10, HP12–HP20, HP23–HP26 | story / narration / manifestation / valuation / study | — | defer (domains/ranges are deferred classes) |
| HP28, HP30–HP32, HP34 | snapshot / added-deleted-replaced content | — | defer (HC11 maintenance / versioning; ttl-only) |

## What P1-C added (and why so little)

Only **HC1 `HeritageEntityNode`** was missing to complete and project the
canonical authoring chain **HC1 → (HP1) → HC2 → (HP33) → HC16**. Everything
else HC1–HC20 is either already mapped (HC2, HC16, HC14), mappable to an
existing EM node (HC5, HC17), or outside the archaeology authoring scope
(sensors, valuation, maintenance, provenance chains) — deferred to avoid scope
creep, to be added the same additive way when a concrete use-case needs them.

**Gating (HDT-O view):** HDT-O node types live in the datamodel and project to
RDF, but are **not** in the EMStudio palette allowlist (`palette-ui.ts`
`SECTIONS`), so the stratigrapher palette is unchanged. The dedicated
`hdto_nodes` datamodel section is the machine-readable HDT-O-view grouping;
`HDTNode`/`GraphNode` remain in `container_nodes` (pre-existing HDT-O members).

**Verification:** `tests/test_hdto_projection.py` authors an HC1→HC2→HC16 graph
and asserts the exporter emits `hdto:HC1_Heritage_Entity`, `HC2`, `HP1`, `HP33`
into valid Turtle.
