# s3Dgraphy — Phase 1 tasks (foundations & interoperability)

Live checklist for Claude Code, co-located with the code. Tick boxes as you go;
update the memory files at each handoff. Strategy context:
`EMStudio/.claude/wip/handoff-hdt-em-dtc-strategy.md` + `roadmap-interop-and-buildout.md`.
**Phase 1 = consolidate s3Dgraphy first; app features come in Phase 2.**
Funding tags: **[SG]** StratiGraph · **[ECHOES]** · **[OSS]** shared.

---

## ⭐ The golden summary — deployment tiers (keep this front & centre)

- **Solo / offline (the common case):** one installer = the **EMStudio desktop app**
  (Tauri, .dmg/.exe). It already bundles **`em-bridge` + s3Dgraphy** → editor + local
  modeling + **Turtle export**, zero config, no Python to install. Files live in local
  folders (like DosCo today) — **no MinIO at this tier.**
- **Small team / sync:** the local orchestrator is bundled into the same app (or a
  one-click add-on) → still ~one object, no endpoints to type.
- **Institutional / online:** `em-server` + MinIO + Keycloak are deployed **once by
  WP6/IT** with defaults; the archaeologist just **logs in**. **MinIO enters only
  here.**

Rule: complexity lives on the server, deployed once by admins; the end user gets one
app and defaults. Never ask an archaeologist to configure endpoints/realms/buckets.

**Architecture reminder:** the **library stays pure operations (no FastAPI)**;
`em-bridge` = local stdio transport; `em-server` = separate Dockerized FastAPI wrapper
(Phase 2 / when online). One-way dependency: em-server → s3dgraphy.

---

## P1-A — [SG] Split the generated registry (Option B) ✅ DONE (commits f3c4841, e9d7940)
- [x] Change `s3dgraphy.tools.sync_node_datamodel` to write the flat class registry to
      a **separate file** `JSON_config/node_registry.generated.json` (not the
      `node_types` block inside the datamodel).
- [x] Keep the hand-authored **categorized sections** (mappings) in
      `s3Dgraphy_node_datamodel.json` — that file becomes human-only.
      (node_types now holds only the base `Node` entry.)
- [x] Fix the **`SemanticShapeNode` drift** (was defined but never imported in
      `nodes/__init__.py` → undiscovered; imported it → registry 43→44 classes).
- [x] Update any Python reader if needed (`rdf_exporter` reads categorized entries by
      their `class` field — **verified** the CIDOC class-index is byte-identical
      before/after the datamodel cleanup).
- [x] Coordinate the **consumer** side in EMStudio (see its P1-J): `rules.ts` +
      `sync-datamodels.sh` now point at the new registry file.
- **DoD:** ✅ `sync_node_datamodel --check` clean (44); drift-guard test green;
  datamodel `node_types` = `{Node}` (hand-authored semantics only); full suite
  shows no new failures vs the pre-session baseline.

## P1-B — [SG] Domain-validate a few mappings ✅ DONE (commit d6f6b74)
- [x] Review `ContinuityNode → E64 End of Existence`, `WorkingUnit → E25`, and confirm
      `PropertyNode → E1` is the intended **qualia-refined fallback** (real CIDOC class
      comes from `em_qualia_types.json` `mappings.cidoc_crm`). All three confirmed.
- [x] Annotate decisions in the categorized sections (appended a dated domain-validation
      note to each `mapping.rationale`; no mapping changed).
- **DoD:** ✅ annotations committed; generated registry untouched (`--check` in sync, 44).

## P1-C — [SG] Additive HDTO coverage (S1)
- [ ] Audit HDTO **HC1–HC20 / HP1–HP26+** against existing EM node types → build a
      coverage table (already-mappable vs must-add).
- [ ] Add **only the missing/non-mappable** classes as new node types (the way
      `HDTNode → HC2` was seeded) with categorized `mapping` + `em_extension.uri`.
- [ ] Gate HC/HP behind the **HDTO view** so the EM palette is unchanged for
      stratigraphers.
- **DoD:** coverage table in the repo; author + project an HDT-aware graph to RDF;
  `rdf_exporter` emits the HDTO types (namespaces already declared).

## P1-D — [SG] Authority registry + resolver (S5)
- [ ] Create `authorities/` with offline **JSON-LD snapshots** + `provenance.json` +
      `LICENSE` per authority.
- [ ] Implement a **resolver** with an **ordered consumption list per facet** that
      attaches **all** hits (ranked): WHEN→ChronOntology/PeriodO first;
      WHAT/WHERE/WHO→Getty (AAT/TGN/ULAN) first, then GND, Wikidata, VIAF (hint-only).
- [ ] Add `authority_refs: [{uri, authority, rank}]` on nodes/qualia (redundant by
      design).
- [ ] First snapshots: **ChronOntology/PeriodO (epochs)** + **Getty AAT**.
- **DoD:** qualia + HDTO `E55/E53/E52/E39` resolve, redundant hits ranked; offline
  snapshot committed; never leaves an identifier empty.

## P1-E — [SG] Projection hardening → TTL round-trip ✅ DONE (commits 3773895, 7ac7b04)
- [x] Property graph → **intermediate TTL** (the verification checkpoint) via
      `rdf_exporter`; **drop Oxigraph** (removed the `rdf-embedded`/pyoxigraph extra;
      `rdf` extra keeps rdflib>=7.0). Hardened the qualia-IRI minting (slugify) so real
      graphs with free-text property types (e.g. "max level") emit valid Turtle.
- [x] Add a **lossless round-trip test** (em.json → TTL → reload) on `TempluMare`
      (`tests/test_ttl_roundtrip.py`; fixture vendored under `tests/fixtures/`).
- **DoD:** ✅ validated TTL out (206 nodes/527 edges, nodes_unmapped=0); round-trip
  test green (parse→serialize→parse isomorphic); no new failures vs baseline.

## P1-F — [SG] Define the access-API surface (pure ops, no web framework)
- [ ] Expose a clean, documented **operation surface** (functions + CLI):
      `open · validate · layout(call em-core) · map · project→TTL · authority`.
- [ ] **No FastAPI/uvicorn in the library.** This surface is the shared contract that
      `em-bridge` (local) and `em-server` (HTTP, later) both call.
- **DoD:** documented function/CLI surface; `pip install s3dgraphy` adds **no** web
  deps; `em-bridge` can drive every op.

---

### Not in Phase 1 (recorded so scope stays clean)
- `em-server` (FastAPI + WebSocket orchestrator + Keycloak/MinIO) — its own Dockerized
  repo, created when going online / adding realtime sync.
- DTC profile [ECHOES], HDTO lens, data plane, Workflow lens — Phase 2.
