# DTC substrate profile in s3Dgraphy (ECHOES deliverable)

The **Digital Twin Chain (DTC)** profile captures the **digital provenance that
PRODUCES documents**: raw acquisitions → processing → produced digital objects.

> **Funding seam.** The DTC profile is the identifiable **ECHOES** deliverable.
> The substrate/engine it plugs into (s3Dgraphy, the EM language, the projection
> machinery) is **StratiGraph / OSS**. This document is the design + coverage note
> for the DTC profile specifically; adding it as a gated profile (like `hdto_nodes`)
> keeps the ECHOES contribution cleanly identifiable within the shared library.

DTC is **distinct from EM-paradata**: EM-paradata (Extractor/Combiner/PropertyNode,
CRMinf; and HDT-O HC17 Observation-with-Inference) is *interpretation ON a document*.
DTC is *how the digital objects themselves came to be*. The two meet at the document
(a DTC **output** may later be the same digital object an EM **DocumentNode** wraps —
that shared-UUID identity is a later slice; the model does not preclude it).

Naming (**Option A**): EM-native `...Node` classes; the CIDOC/CRMdig + PROV-O mapping
lives in `em_extension` (no D-numbers in the UI). **Chunk** = one node; **Chain** = the
assembled provenance. Gated OUT of the stratigrapher palette (like the HDT-O nodes) —
the dedicated `dtc_nodes` datamodel section is the machine-readable grouping.

## Node kinds (`dtc_nodes` section + Python classes)

| Kind | Class (`node_type`) | rdf:type (em_extension) | Role |
|------|---------------------|--------------------------|------|
| INPUT | `DTCInputNode` (`dtc_input`) | `crmdig:D1_Digital_Object` ⊂ `prov:Entity` | raw acquisition consumed by a process |
| PROCESS | `DTCProcessNode` (`dtc_process`) | `crmdig:D7_Digital_Machine_Event` ⊂ `prov:Activity` | the transformation/processing event |
| OUTPUT | `DTCOutputNode` (`dtc_output`) | `crmdig:D1_Digital_Object` ⊂ `prov:Entity` | produced digital object / document |

INPUT and OUTPUT share the same rdf:type (both are digital objects); their role is
carried by the **chain edges**, not the type — the correct CRMdig/PROV pattern. All
three subclass an abstract `DTCNode` (registry `node_type=None`) so tooling can group
them (`isinstance` / ancestry) — mirrors `StratigraphicNode`.

### Per-kind vocabulary — DATA-DRIVEN and EXPANDABLE

The **specific** kind (`data.dtc_kind`) is drawn from a vocabulary in
`em_visual_rules.json → dtc_kinds`, read via `utils.get_dtc_kinds()` and validated in
the node constructors — exactly mirroring the DocumentNode axis vocabularies
(`document_roles` / `document_content_natures`, DP-07). **Adding a kind (audio,
spectroscopy, …) is a JSON entry (+ a glyph), NOT a code change.**

Seeded from the 2017 DTC palette (each carries a `glyph` name for the later
visual-manager slice):

- **input**: `photo` (09_photos), `laserscanner` (10_laserscanner), `topographic` (01_topographicnetwork)
- **process**: `transformation` (00_transformation)
- **output**: `pointcloud` (02_pointcloud), `mesh` (03_mesh), `dem` (07_DEM),
  `orthophoto` (08_ortophoto), `points` (04_points), `lines` (05_lines), `polygons` (06_polygons)

`dtc_kind` projects as `crm:P2_has_type`.

## Chain edges (`s3Dgraphy_connections_datamodel.json`)

Each edge dual-projects a CRMdig predicate (`mapping.cidoc`) **and** a PROV-O predicate
(`mapping.extension_mapping`) — CRMdig for CRM readers, PROV-O for the provenance graph.

| Edge | Direction | CRMdig | PROV-O |
|------|-----------|--------|--------|
| `dtc_had_input` | Process → Input | `crmdig:L10_had_input` | `prov:used` |
| `dtc_had_output` | Process → Output | `crmdig:L11_had_output` | `prov:generated` |
| `dtc_derived_from` | Output → Input | `crmdig:L21_used_as_derivation_source` | `prov:wasDerivedFrom` |

## EM commons — REUSED, not duplicated

| Concern | Reused EM node + edge | Projection |
|---------|-----------------------|-----------|
| Agent | `AuthorNode` via `has_author` (source extended to the 3 DTC classes) | `prov:wasAttributedTo` |
| File pointer | `LinkNode` via `has_linked_resource` (source extended to `DTCOutputNode`/`DTCInputNode`) — the real file / future MinIO asset id | `crm:P67_refers_to` + `rdfs:seeAlso <url>` |
| Rights | `LicenseNode` via `has_license`; `EmbargoNode` via `has_embargo` (already allow source `Node`) | `crm:P104_is_subject_to` |

No new agent/license/embargo/file classes were introduced.

## Verification

`tests/test_dtc_projection.py` authors a chain **photos → transformation → mesh**
(+ Author, + LinkNode file, output derived from photos) and asserts the projected
Turtle carries `crmdig:D1/D7`, `prov:Entity/Activity`, `crmdig:L10/L11/L21`,
`prov:used/generated/wasDerivedFrom`, `crm:P2_has_type` kinds, and the reused commons
(`prov:wasAttributedTo`, `crm:P67_refers_to` + the file URL); plus data-driven kind
validation, an em.json round-trip, and the palette-gating check. `sync_node_datamodel
--check` clean (51 classes); full suite = baseline (no new failures).

## Deferred (next slices — recorded so scope stays clean)

- **DTC glyphs / visual manager** (the 2017 SVG set is already named per kind in
  `dtc_kinds.*.glyph`).
- **DTC lens + double-click seam** (like the HDT-O lens).
- **Output ↔ EM-document shared-UUID identity** (both are digital objects; not
  precluded by this model).
- **Provenance HC18/HC19 nodes** (GENESIS-side summary linking into this DTC chain).
- **Non-CH-seed kinds** beyond keeping the vocabulary expandable.
