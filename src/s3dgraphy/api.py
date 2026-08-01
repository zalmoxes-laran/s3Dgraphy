"""s3dgraphy.api — the formal access-API surface (P1-F).

A single, documented set of **pure operations** over the Extended Matrix graph:
load/parse, validate, project → TTL/RDF, GraphML/XLSX interop, authority
resolution. This is the stable contract that the local **em-bridge** sidecar and
the future **em-server** (HTTP) both drive — the library itself stays pure:

  * NO web framework here (no FastAPI/uvicorn/HTTP). Transports wrap this surface.
  * Heavy/optional deps (lxml for GraphML, pandas for XLSX, rdflib for RDF) are
    imported LAZILY inside each function, so ``import s3dgraphy.api`` is cheap and
    ``pip install s3dgraphy`` pulls no web/format deps until an op needs them.
  * em.json is the single source of truth; ``dict`` = an em.json document,
    ``str``/``bytes`` = a serialized GraphML/Turtle payload, ``Graph`` = the
    in-memory model. HTTP callers work in docs/strings; in-process callers may
    use the Graph-level ops directly.

Layout is intentionally absent: it lives in em-core (Rust/WASM), not the Python
library (ADR-001 invariant 2).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Type-only alias; avoid importing submodules at module load (keeps this import
# cheap and cycle-free). Real classes are imported lazily inside the ops.
Graph = Any
EmJson = Dict[str, Any]


class MissingDependency(ImportError):
    """An optional dependency for an op is not installed (e.g. rdflib for TTL).
    Transports may map this to a 501-style 'not available' response."""


# ── load / parse ──────────────────────────────────────────────────────────────
def load_emjson(doc: EmJson) -> Tuple[Graph, List[str]]:
    """Parse an in-memory .em.json v1 document into a Graph.

    Returns ``(graph, warnings)``; unknown node types degrade to base nodes with
    a warning (forward-compatible) rather than failing."""
    from .importer.emjson_importer import parse_emjson
    return parse_emjson(doc)


def load_emjson_file(path: str) -> Tuple[Graph, List[str]]:
    """Load a .em.json v1 file. Returns ``(graph, warnings)``."""
    from .importer.emjson_importer import import_emjson
    return import_emjson(path)


def graph_to_emjson(graph: Graph, layout: Optional[Dict[str, Any]] = None) -> EmJson:
    """Serialize a Graph to an .em.json v1 document (dict). Optional ``layout``
    is embedded as-is (the caller owns layout; em-core computes it)."""
    from .exporter.emjson_exporter import build_emjson
    return build_emjson(graph, layout=layout)


# ── validate ────────────────────────────────────────────────────────────────
def validate(graph: Graph) -> Dict[str, Any]:
    """Read-only structural check of a Graph. Returns
    ``{ok, stats, warnings, issues}`` — surfaces the graph's own accumulated
    warnings plus a cheap dangling-edge scan. Minimal and extensible; adds no
    side effects."""
    nodes = list(getattr(graph, "nodes", []) or [])
    edges = list(getattr(graph, "edges", []) or [])
    ids = {n.node_id for n in nodes}
    issues: List[str] = []
    for e in edges:
        if e.edge_source not in ids:
            issues.append(f"edge '{getattr(e, 'edge_id', '?')}' has missing source '{e.edge_source}'")
        if e.edge_target not in ids:
            issues.append(f"edge '{getattr(e, 'edge_id', '?')}' has missing target '{e.edge_target}'")
    warnings = list(getattr(graph, "warnings", []) or [])
    return {
        "ok": not issues,
        "stats": {"nodes": len(nodes), "edges": len(edges)},
        "warnings": warnings,
        "issues": issues,
    }


# ── project → TTL / RDF ────────────────────────────────────────────────────────
def project_ttl(graph: Graph, *, base_uri: Optional[str] = None,
                fmt: str = "turtle") -> str:
    """Project a Graph to RDF and return it as a string (default Turtle).

    Raises :class:`MissingDependency` if rdflib is not installed."""
    try:
        from .exporter.rdf_exporter import (
            export_single_graph_to_rdf, DEFAULT_BASE_URI,
        )
    except ImportError as exc:  # rdflib missing
        raise MissingDependency(f"RDF projection needs rdflib ({exc})") from exc
    with tempfile.NamedTemporaryFile(suffix=".ttl", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        export_single_graph_to_rdf(
            graph, str(tmp_path), format=fmt,
            base_uri=base_uri or DEFAULT_BASE_URI)
        return tmp_path.read_text(encoding="utf-8")
    finally:
        tmp_path.unlink(missing_ok=True)


def emjson_to_ttl(doc: EmJson, *, base_uri: Optional[str] = None) -> str:
    """Convenience: load an em.json doc and project it to Turtle."""
    graph, _warnings = load_emjson(doc)
    return project_ttl(graph, base_uri=base_uri)


# ── GraphML interop ────────────────────────────────────────────────────────────
def graph_to_graphml(graph: Graph, *, persist_auxiliary: bool = False) -> str:
    """Serialize a Graph to yEd GraphML (XML string)."""
    from .exporter.graphml.graphml_exporter import GraphMLExporter
    with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        GraphMLExporter(graph).export(str(tmp_path), persist_auxiliary=persist_auxiliary)
        return tmp_path.read_text(encoding="utf-8")
    finally:
        tmp_path.unlink(missing_ok=True)


def graphml_to_graph(graphml: "str | bytes", *, graph_id: str = "imported_graph"
                     ) -> Tuple[Graph, List[str]]:
    """Parse yEd GraphML into a Graph. Returns ``(graph, warnings)``."""
    from .graph import Graph as _Graph
    from .importer.import_graphml import GraphMLImporter
    data = graphml.encode("utf-8") if isinstance(graphml, str) else graphml
    with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        g = _Graph(graph_id=graph_id)
        graph = GraphMLImporter(str(tmp_path), g).parse()
        return graph, list(getattr(graph, "warnings", []) or [])
    finally:
        tmp_path.unlink(missing_ok=True)


def emjson_to_graphml(doc: EmJson) -> str:
    """Convenience: load an em.json doc and serialize it to GraphML."""
    graph, _warnings = load_emjson(doc)
    return graph_to_graphml(graph)


def graphml_to_emjson(graphml: "str | bytes") -> EmJson:
    """Convenience: parse GraphML → em.json document (layout=None; the client
    re-lays-out via em-core)."""
    graph, _warnings = graphml_to_graph(graphml)
    return graph_to_emjson(graph)


# ── XLSX mapping ──────────────────────────────────────────────────────────────
def xlsx_to_graph(path: str, *, mapping_name: Optional[str] = None,
                  id_column: Optional[str] = None, graph_id: str = "imported_graph"
                  ) -> Tuple[Graph, List[str]]:
    """Map an Excel workbook into a Graph via the XLSX importer. Returns
    ``(graph, warnings)``. Needs pandas/openpyxl (imported lazily by the
    importer)."""
    from .graph import Graph as _Graph
    from .importer.xlsx_importer import XLSXImporter
    importer = XLSXImporter(path, mapping_name=mapping_name, id_column=id_column)
    # BaseImporter subclasses attach to a Graph they hold; use the importer's own.
    graph = importer.parse()
    if getattr(graph, "graph_id", None) in (None, ""):
        graph.graph_id = graph_id
    return graph, list(getattr(graph, "warnings", []) or [])


def xlsx_to_emjson(path: str, **kwargs) -> EmJson:
    """Convenience: map an Excel workbook → em.json document."""
    graph, _warnings = xlsx_to_graph(path, **kwargs)
    return graph_to_emjson(graph)


# ── authority resolution ────────────────────────────────────────────────────
def resolve_authority(term: str, facet: str) -> List[Dict[str, Any]]:
    """Ranked offline authority candidates for a term/facet (P1-D). Returns [] on
    empty term or when the resolver/snapshots are unavailable."""
    try:
        from .authorities import resolve
        return list(resolve(term, facet))
    except Exception:
        return []


def authority_facets() -> List[str]:
    """The valid authority facet identifiers (WHEN/WHAT/WHERE/WHO)."""
    try:
        from .authorities import FACET_ORDER
        return list(FACET_ORDER)
    except Exception:
        return []


# ── resource layer (R0: stable-ID resolver seam) ──────────────────────────────
# Resources are LinkNodes (E73). Their stable, storage-agnostic ID is the node
# UUID; the ``url`` is the *current locator*, not the identity. A pluggable
# resolver maps ID → a concrete Location. See :mod:`s3dgraphy.resources`.
def _resource_locator(node: Any) -> str:
    """The current locator of a resource node (LinkNode ``url``)."""
    url = getattr(node, "url", None)
    if url is None:
        url = (getattr(node, "data", {}) or {}).get("url", "")
    return url or ""


def list_resources(graph: Graph) -> List[Dict[str, Any]]:
    """List the resources in a graph. Resources = LinkNodes (E73). Returns, per
    resource, its stable ``id`` (node UUID), ``name``, current ``locator`` and
    the classified location ``kind`` — a pure read, no I/O on the locator."""
    from .resources import classify_locator, stable_resource_id
    out: List[Dict[str, Any]] = []
    for node in getattr(graph, "nodes", []) or []:
        if getattr(node, "node_type", None) != "link":
            continue
        locator = _resource_locator(node)
        out.append({
            "id": stable_resource_id(node),
            "name": getattr(node, "name", ""),
            "locator": locator,
            "kind": classify_locator(locator),
        })
    return out


def shelf_resources(doc: Optional[EmJson], folder: str, *,
                    graph_code: Optional[str] = None) -> List[Dict[str, Any]]:
    """The **Shelf** for a library/DosCo ``folder`` given the current em.json
    ``doc``: the un-hatted resources (orphans) with their stable IDs.

    Scans ``folder`` with the FS-index backend (R1), then returns the orphans —
    files with no matching graph node (DosCo EM-id convention filters applied) —
    additionally excluding any whose FS stable ID is already a node in ``doc``
    (ID-adoption aware, so a hatted resource leaves the Shelf). ``doc`` may be
    ``None`` (empty graph → every on-convention Document-id file is on the Shelf).
    Returns dicts ``{resource_id, key_id, filename, rel_path}``.

    Manifest-backed: reuses a ``.em_resources_manifest.json`` persisted IN the
    folder (same filename EMTools R4 uses) so stable IDs survive across scans and
    across tools — one ID space per folder, the "single connector". A hatted
    resource therefore keeps the same ID that was adopted as its node_id."""
    import json as _json
    import os as _os
    from .resources import FSIndexBackend
    manifest_name = ".em_resources_manifest.json"
    mpath = _os.path.join(folder, manifest_name)
    backend = None
    if _os.path.isfile(mpath):
        try:
            with open(mpath, encoding="utf-8") as fh:
                backend = FSIndexBackend.from_manifest(_json.load(fh))
            backend.folder = _os.path.abspath(folder)
        except Exception:
            backend = None
    if backend is None:
        backend = FSIndexBackend(folder)
    backend.rescan()
    if _os.path.isdir(folder):
        try:
            with open(mpath, "w", encoding="utf-8") as fh:
                _json.dump(backend.to_manifest(), fh, indent=2)
        except Exception:
            pass

    # The Shelf needs only each node's id/name/node_type — read them straight
    # from the em.json dict rather than a full ``load_emjson`` parse, so the
    # Shelf stays robust to header/version quirks (e.g. a freshly-created empty
    # doc) and stays decoupled from the importer. A tiny shim gives
    # ``FSIndexBackend.orphans`` the node view it expects (name-convention
    # exclusion); the id-adoption exclusion uses the same ids.
    class _ShimNode:
        __slots__ = ("node_id", "name", "node_type")

        def __init__(self, nid, name, ntype):
            self.node_id, self.name, self.node_type = nid, name, ntype

    class _ShimGraph:
        def __init__(self, nodes):
            self.nodes = nodes

    graph = None
    node_ids: set = set()
    if doc is not None:
        raw_nodes = ((doc.get("graph") or {}).get("nodes")) or []
        shim = [_ShimNode(n.get("id"), n.get("name", ""), n.get("node_type") or n.get("type"))
                for n in raw_nodes if isinstance(n, dict)]
        graph = _ShimGraph(shim)
        node_ids = {n.node_id for n in shim if n.node_id}
    out: List[Dict[str, Any]] = []
    for orphan in backend.orphans(graph, graph_code=graph_code):
        if orphan.resource_id in node_ids:
            continue  # already hatted (ID adopted) — off the Shelf
        out.append({
            "resource_id": orphan.resource_id,
            "key_id": orphan.key_id,
            "filename": orphan.filename,
            "rel_path": orphan.rel_path,
        })
    return out


def resolve_resource(graph: Graph, resource_id: str, *, registry: Any = None
                     ) -> Optional[Dict[str, Any]]:
    """Resolve a resource's stable ID to a Location dict via the resolver.

    Looks up the LinkNode by its ``node_id`` (the stable ID), reads its current
    locator, and asks the resolver registry (default: passthrough) to map it to
    a :class:`~s3dgraphy.resources.Location`. Returns the Location as a dict
    ``{kind, value, exists}``, or ``None`` if no such resource exists."""
    from .resources import default_registry
    node = graph.find_node_by_id(resource_id)
    if node is None or getattr(node, "node_type", None) != "link":
        return None
    locator = _resource_locator(node)
    reg = registry if registry is not None else default_registry()
    loc = reg.resolve(resource_id, locator, graph=graph)
    return loc.to_dict() if loc is not None else None


def register_resource(graph: Graph, locator: str, *, name: Optional[str] = None,
                      resource_id: Optional[str] = None,
                      url_type: Optional[str] = None,
                      description: Optional[str] = None) -> Dict[str, Any]:
    """Register a resource: assign a stable ID and store a locator (R0 STUB).

    Creates a LinkNode carrying a new stable ID (a UUID unless ``resource_id`` is
    given) and the ``locator`` as its current ``url``, and adds it to the graph.
    This is the *identity + locator* half only — real ingest (copying bytes into
    an FS-index or MinIO store) is R1/R2, which will resolve the same ID through
    their backends. Returns ``{id, locator, kind}``."""
    import uuid
    from .nodes.link_node import LinkNode
    from .resources import classify_locator

    rid = resource_id or str(uuid.uuid4())
    node = LinkNode(
        node_id=rid,
        name=name or "Unnamed Resource",
        url=locator or "",
        url_type=url_type or "",
        description=description or "",
    )
    graph.add_node(node)
    return {"id": rid, "locator": locator or "", "kind": classify_locator(locator or "")}


def scan_fs_resources(folder: str) -> List[Dict[str, Any]]:
    """Scan a folder with the FS-index backend (R1) and return its manifest
    entries as dicts (id, rel_path, name, resource_type, mtime, present).

    Pure/offline: files are indexed in place (Tropy-like) and minted stable IDs;
    it moves no bytes and touches no graph. Callers that want resolution build a
    registry and ``register`` the returned backend above passthrough."""
    from .resources import FSIndexBackend
    backend = FSIndexBackend(folder)
    backend.scan()
    return [e.to_dict() for e in backend.entries()]


def ingest_minio_resource(path: str, *, resource_id: Optional[str] = None,
                          config: Any = None) -> Dict[str, Any]:
    """Ingest a file into the SHARED MinIO/S3 store (R2) and return
    ``{id, object_key, s3_uri}``.

    ``resource_id`` (optional): reuse an EXISTING stable ID instead of minting a
    fresh one — this is how "promote to MinIO" keeps a resource's identity (the
    SAME id whether it lives on the file system or in MinIO — one ID space).

    By default the connection is read from the ``S3_*`` environment (the SAME
    vars Heriverse-Server uses → one shared object store); pass an explicit
    :class:`~s3dgraphy.resources.MinioConfig` to override. Needs the optional
    ``minio`` SDK (``pip install s3dgraphy[minio]``) AND a reachable server —
    raises :class:`MissingDependency` if the SDK is absent."""
    from .resources import MinioBackend, MinioConfig
    cfg = config or MinioConfig.from_env()
    backend = MinioBackend(cfg)
    rid, key = backend.ingest(path, resource_id=resource_id)
    return {"id": rid, "object_key": key, "s3_uri": f"s3://{cfg.bucket}/{key}"}


def presign_minio_resource(object_key: str, *, config: Any = None,
                           expires_seconds: int = 3600) -> Dict[str, Any]:
    """Presign a shared-MinIO ``object_key`` (as returned by
    :func:`ingest_minio_resource`) into a short-lived fetchable
    ``{object_key, http_url}``. Stateless (presign by key, no manifest). Connection
    from the ``S3_*`` env by default. Raises :class:`MissingDependency` without the
    ``minio`` SDK."""
    from .resources import MinioBackend, MinioConfig
    cfg = config or MinioConfig.from_env()
    loc = MinioBackend(cfg).presign_key(object_key, expires_seconds=expires_seconds)
    return {"object_key": object_key, "http_url": loc.value}


# ── DTC residency (R3: detach ↔ inject ↔ bake) ─────────────────────────────────
# A DTC can live WITH the asset store (a standalone record) rather than baked into
# em.json, and be baked back on demand. Resources are referenced by stable ID.
def detach_dtc(graph: Graph, process_id: str) -> Dict[str, Any]:
    """Extract the DTC anchored on ``process_id`` into a standalone JSON record
    (resources keyed by stable ID). Read-only — the graph is not mutated."""
    from .dtc import detach_dtc as _detach
    return _detach(graph, process_id)


def inject_dtc(graph: Graph, record: Dict[str, Any], *,
               injector_id: Optional[str] = None) -> Dict[str, Any]:
    """Re-create a DTC from a :func:`detach_dtc` record into ``graph``. Created
    nodes/edges are tagged ``injected_by`` (temporary); resources already present
    (by stable ID) are reused. Returns
    ``{injector_id, process_id, resource_ids, created}``."""
    from .dtc import inject_dtc as _inject
    return _inject(graph, record, injector_id=injector_id)


def bake_dtc(graph: Graph, injector_id: str) -> Dict[str, int]:
    """Promote an injected DTC to persistent (drop ``injected_by``) — the
    ``bake → em.json`` export. Returns ``{nodes, edges, overrides_cleared}``."""
    from .dtc import bake_dtc as _bake
    return _bake(graph, injector_id)


# ── Shelf substrate (Shelf v2 core: a collection of un-hatted resources) ───────
# A shelf-graph is a Graph of LinkNode resources (R0 stable IDs), representable as
# a multigraph member OR a standalone reusable em.json. Each entry preserves its
# capability/origin for downstream tier badges. See :mod:`s3dgraphy.shelf`.
def new_shelf(graph_id: str = "shelf", name: Optional[str] = None) -> Graph:
    """Create an empty shelf-graph (tagged as a shelf collection)."""
    from .shelf import new_shelf as _n
    return _n(graph_id=graph_id, name=name)


def add_to_shelf(shelf: Graph, locator: str, *, resource_id: Optional[str] = None,
                 name: Optional[str] = None, url_type: Optional[str] = None,
                 description: Optional[str] = None,
                 resource_type: Optional[str] = None,
                 origin: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Add a resource to the shelf (reuse-not-duplicate by ``resource_id``);
    ``origin`` = the capability/origin envelope, preserved. Returns the entry."""
    from .shelf import add_to_shelf as _a
    return _a(shelf, locator, resource_id=resource_id, name=name,
              url_type=url_type, description=description,
              resource_type=resource_type, origin=origin)


def list_shelf(shelf: Graph) -> List[Dict[str, Any]]:
    """List the shelf's resources — id/name/locator/kind + resource_type/origin
    (aligned with :func:`list_resources` / :func:`shelf_resources`)."""
    from .shelf import list_shelf as _l
    return _l(shelf)


def remove_from_shelf(shelf: Graph, resource_id: str) -> bool:
    """Remove a resource from the shelf. Returns True if it was present."""
    from .shelf import remove_from_shelf as _r
    return _r(shelf, resource_id)


def save_shelf(shelf: Graph, path: str) -> str:
    """Persist the shelf as a STANDALONE em.json file. Returns the path."""
    from .shelf import save_shelf as _s
    return _s(shelf, path)


def load_shelf(path: str) -> Tuple[Graph, List[str]]:
    """Load a standalone shelf em.json file → ``(graph, warnings)``."""
    from .shelf import load_shelf as _l
    return _l(path)


def instantiate_from_shelf(shelf: Graph, resource_id: str,
                           target_graph: Graph) -> Any:
    """Reference a shelf resource into ``target_graph`` by its stable ID
    (reuse-not-duplicate; capability/origin preserved). Returns the target node."""
    from .shelf import instantiate_from_shelf as _i
    return _i(shelf, resource_id, target_graph)


# Hatting facets. The ROLE picks the facet, and facets are NOT exclusive — the
# same Resource can be an RM of an epoch AND a Document in a paradata chain. Every
# facet keeps the P67 hinge (facet ─has_linked_resource→ LinkNode); what differs is
# the edge towards what it represents / documents.
def hat_facets() -> Tuple[str, ...]:
    """The hatting facet names: ``("rm", "rmsf", "rmdoc", "document")``."""
    from .shelf import FACETS
    return FACETS


def attach_candidates(facet: str, graph: Graph) -> List[Dict[str, Any]]:
    """The nodes of ``graph`` a ``facet`` may attach to, as
    ``[{id, name, node_type, edge}]`` — derived from the datamodel's
    ``allowed_connections``, so a UI picker never hardcodes a type list. ``rm``
    yields the epochs in chronological order (first = ``has_first_epoch``)."""
    from .shelf import attach_candidates as _c
    return _c(facet, graph)
def hat_as_representation_model(target_graph: Graph, resource_id: str, *,
                                shelf: Optional[Graph] = None,
                                rm_id: Optional[str] = None,
                                name: Optional[str] = None,
                                epochs: Optional[List[str]] = None,
                                attach_to: Optional[str] = None) -> Dict[str, Any]:
    """Hat a shelf resource into ``target_graph`` as a RepresentationModel: the
    Resource is referenced by stable ID (R0 hinge) and an RM node references it via
    ``has_linked_resource`` (P67). An RM represents a STATE, so it binds to one or
    more **EpochNodes** (``epochs``, ordered: first → ``has_first_epoch``, rest →
    ``survive_in_epoch``); non-epoch targets are refused and returned in
    ``skipped``. ``attach_to`` is the deprecated single-epoch alias.
    Reuse-not-duplicate + idempotent. Returns
    ``{rm_id, resource_id, created, epochs, skipped, attached}``. No mesh import
    (EMTools does that)."""
    from .shelf import hat_as_representation_model as _h
    return _h(target_graph, resource_id, shelf=shelf, rm_id=rm_id, name=name,
              epochs=epochs, attach_to=attach_to)


def hat_as_rmsf(target_graph: Graph, resource_id: str, *,
                shelf: Optional[Graph] = None, rmsf_id: Optional[str] = None,
                name: Optional[str] = None,
                attach_to: Optional[str] = None) -> Dict[str, Any]:
    """Hat a shelf resource as a RepresentationModelSpecialFind: RMSF ─P67→ Resource
    plus ``SF ─has_representation_model_sf→ RMSF`` (P138i) when ``attach_to`` names a
    Special Find. Returns ``{rmsf_id, resource_id, created, attached}``."""
    from .shelf import hat_as_rmsf as _h
    return _h(target_graph, resource_id, shelf=shelf, rmsf_id=rmsf_id, name=name,
              attach_to=attach_to)


def hat_as_rmdoc(target_graph: Graph, resource_id: str, *,
                 shelf: Optional[Graph] = None, rmdoc_id: Optional[str] = None,
                 name: Optional[str] = None, attach_to: Optional[str] = None,
                 free_placement: bool = True) -> Dict[str, Any]:
    """Hat a shelf resource as a RepresentationModelDoc — a Document instantiated in
    the 3D scene (e.g. a historical photo in place). RMDoc ─P67→ Resource plus
    ``Document ─has_representation_model_doc→ RMDoc`` (P138i) when ``attach_to``
    names a Document. Placement is free/manual (no epoch, no stratigraphy).
    Returns ``{rmdoc_id, resource_id, created, attached, placement}``."""
    from .shelf import hat_as_rmdoc as _h
    return _h(target_graph, resource_id, shelf=shelf, rmdoc_id=rmdoc_id, name=name,
              attach_to=attach_to, free_placement=free_placement)


def hat_as_document(target_graph: Graph, resource_id: str, *,
                    shelf: Optional[Graph] = None, doc_id: Optional[str] = None,
                    name: Optional[str] = None, description: str = "",
                    role: Optional[str] = None,
                    content_nature: Optional[str] = None,
                    geometry: Optional[str] = None, mark_as_master: bool = True,
                    attach_to: Optional[str] = None) -> Dict[str, Any]:
    """Hat a shelf resource as a Document (E31) — a SOURCE, with no placement: the
    paradata entry point an ExtractorNode can later read from (``extracted_from``).
    Document ─P67→ Resource; ``attach_to`` picks its edge from the datamodel
    (Extractor → ``extracted_from``, stratigraphic → ``has_documentation``, other
    paradata → ``has_visual_reference``). ``doc_id`` naming an existing DocumentNode
    reuses it (one document shape with EMTools' ``create_master_document_node``).
    Returns ``{doc_id, resource_id, created, attached, attach_edge}``."""
    from .shelf import hat_as_document as _h
    return _h(target_graph, resource_id, shelf=shelf, doc_id=doc_id, name=name,
              description=description, role=role, content_nature=content_nature,
              geometry=geometry, mark_as_master=mark_as_master, attach_to=attach_to)


def remove_shelf_resource(graph: Graph, resource_id: str) -> Dict[str, Any]:
    """Remove a shelf resource + clean up its now-orphan acquisition event (kept
    if the resource is still referenced, e.g. hatted). Returns
    ``{removed, referenced, events_removed}``."""
    from .shelf import remove_resource as _r
    return _r(graph, resource_id)


# ── Acquisition seam (Shelf v2 Session B: Tier-0 hook) ─────────────────────────
# An opaque source emits an AcquisitionDescriptor (versioned, canonical schema in
# JSON_config); s3Dgraphy consumes it into a Resource + a distinct acquisition DTC
# event (crmdig:D12) on the Shelf. Per-source JSON mappings (xlsx-import style)
# customize each repo's records. See :mod:`s3dgraphy.acquisition`.
def acquire_from_descriptor(descriptor: Any, shelf: Optional[Graph] = None
                            ) -> Tuple[Dict[str, Any], Graph]:
    """Tier-0 acquisition: descriptor (dict or AcquisitionDescriptor) → ``(info,
    shelf)``. Creates/reuses the Resource + its acquisition event on ``shelf``
    (a new shelf when ``None``). Raises if the descriptor carries a payload_graph
    (Tier 1/2 — later)."""
    from .acquisition import acquire_from_descriptor as _a
    return _a(descriptor, shelf)


def apply_acquisition_mapping(source_or_path: str,
                              record: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a raw source ``record`` into an AcquisitionDescriptor dict using
    the per-source mapping (``source`` name or explicit path). Ercolano + fs ship."""
    from .acquisition import apply_mapping, load_mapping
    return apply_mapping(load_mapping(source_or_path), record)


def fs_acquisition_record(path: str) -> Dict[str, Any]:
    """Build a raw file-system record (filename/path/size/ext/media_type/…) for the
    ``fs`` mapping from a local ``path`` — the local project-folder acquisition source."""
    from .acquisition import fs_record
    return fs_record(path)


def acquisition_schema() -> Dict[str, Any]:
    """The canonical AcquisitionDescriptor JSON Schema (versioned)."""
    from .acquisition import schema
    return schema()


# ── connection resolution: REPORT-ONLY (S1) ───────────────────────────────────
# `Graph.validate_connection` is permissive by construction (it resolves the
# datamodel's CLASS names through the node_type-keyed map). These two ops measure
# what a CORRECT resolver would decide, changing nothing: no graph is mutated and
# `add_edge` keeps degrading exactly as it does today.
def connection_report(graph: Graph, *, max_cases: int = 0,
                      diagnose_generic_edges: bool = False) -> Dict[str, Any]:
    """What a correct resolver would decide about ``graph``'s edges. Returns
    ``{total_edges, resolved, would_degrade, already_generic, unknown_edge_type,
    dangling, delta, cases}`` — ``delta`` is the blast radius: edges that would
    degrade to ``generic_connection`` but are accepted by the current permissive
    core, i.e. exactly what a strict switch would change. With
    ``diagnose_generic_edges`` it also adds ``generic_diagnosis`` (see
    :func:`diagnose_generic_connections`). Read-only."""
    from .edges.connection_resolver import connection_report as _r
    return _r(graph, max_cases=max_cases,
              diagnose_generic_edges=diagnose_generic_edges)


def diagnose_generic_connections(graph: Graph, *, max_cases: int = 0) -> Dict[str, Any]:
    """Of the edges ALREADY typed ``generic_connection``, what type would their
    endpoints allow? Returns ``{total_generic, recoverable, ambiguous,
    no_candidate, dangling, cases}`` — ``recoverable`` = exactly one edge type
    fits, so the lost type is unambiguously reconstructible. **Diagnostic only**:
    nothing is re-typed and no graph is mutated."""
    from .edges.connection_resolver import diagnose_generic as _d
    return _d(graph, max_cases=max_cases)


def resolve_edge_type(source_node: Any, target_node: Any, declared_type: str) -> str:
    """The type an edge WOULD carry under correct resolution — the declared type
    when the datamodel allows it, else ``generic_connection``. Pure; does not
    touch any graph and does not change how edges are actually created."""
    from .edges.connection_resolver import resolve_edge_type as _r
    return _r(source_node, target_node, declared_type)


# ── thin CLI (part of the surface; no web deps) ────────────────────────────────
def main(argv: Optional[List[str]] = None) -> int:
    """`python -m s3dgraphy.api <op> ...` — a thin CLI over the ops above."""
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(prog="s3dgraphy.api", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="op", required=True)
    sub.add_parser("open", help="parse an .em.json file, print stats").add_argument("path")
    sub.add_parser("validate", help="validate an .em.json file").add_argument("path")
    sub.add_parser("project-ttl", help=".em.json → Turtle (stdout)").add_argument("path")
    sub.add_parser("graphml", help=".em.json → GraphML (stdout)").add_argument("path")
    sub.add_parser("import-graphml", help="GraphML → .em.json (stdout)").add_argument("path")
    r = sub.add_parser("resolve", help="resolve an authority term")
    r.add_argument("term")
    r.add_argument("facet")
    sub.add_parser("list-resources", help="list a graph's resources (LinkNodes)").add_argument("path")
    rr = sub.add_parser("resolve-resource", help="resolve a resource ID → Location")
    rr.add_argument("path")
    rr.add_argument("resource_id")
    sub.add_parser("scan-resources", help="FS-index scan a folder → manifest").add_argument("folder")
    cr = sub.add_parser("connection-report",
                        help="REPORT-ONLY: what a correct connection resolver "
                             "would decide about an .em.json (changes nothing)")
    cr.add_argument("path")
    cr.add_argument("--json", action="store_true", help="machine-readable output")
    cr.add_argument("--max-cases", type=int, default=0,
                    help="truncate the case list (0 = all)")
    cr.add_argument("--diagnose-generic", action="store_true",
                    help="also ask what type the already-generic edges would "
                         "take, judging by their endpoints (diagnostic only)")
    dd = sub.add_parser("detach-dtc", help="extract a DTC → standalone JSON record")
    dd.add_argument("path")
    dd.add_argument("process_id")
    # ── Shelf substrate (all operate on a standalone shelf em.json file) ──────
    sn = sub.add_parser("shelf-new", help="create an empty standalone shelf em.json")
    sn.add_argument("path")
    sn.add_argument("--graph-id", default="shelf")
    sn.add_argument("--name", default=None)
    sub.add_parser("shelf-list", help="list a shelf's resources").add_argument("path")
    sa = sub.add_parser("shelf-add", help="add a resource to a shelf (saved back)")
    sa.add_argument("path")
    sa.add_argument("locator")
    sa.add_argument("--resource-id", default=None)
    sa.add_argument("--name", default=None)
    sa.add_argument("--resource-type", default=None)
    sa.add_argument("--origin-repo", default=None, help="source repo id (origin)")
    sa.add_argument("--capabilities", default=None,
                    help="comma-separated source capabilities, e.g. genesis,interpretation")
    sa.add_argument("--scope", default=None, help="payload scope (origin)")
    srm = sub.add_parser("shelf-remove", help="remove a resource from a shelf (saved back)")
    srm.add_argument("path")
    srm.add_argument("resource_id")
    si = sub.add_parser("shelf-instantiate",
                        help="reference a shelf resource into a target em.json (saved back)")
    si.add_argument("path")
    si.add_argument("resource_id")
    si.add_argument("target")
    # ── Acquisition (Tier 0): descriptor / mapped record → Resource + event on a shelf ──
    aq = sub.add_parser("acquire", help="Tier-0 acquire a descriptor onto a shelf")
    aq.add_argument("descriptor", help="path to an AcquisitionDescriptor .json")
    aq.add_argument("--shelf", required=True, help="shelf em.json (created if missing)")
    am = sub.add_parser("acquire-map",
                        help="map a raw source record → descriptor, then acquire onto a shelf")
    am.add_argument("source", help="per-source mapping name (e.g. ercolano) or path")
    am.add_argument("record", help="path to a raw source record .json")
    am.add_argument("--shelf", required=True, help="shelf em.json (created if missing)")
    args = ap.parse_args(argv)

    if args.op in ("open", "validate", "project-ttl", "graphml"):
        with open(args.path, encoding="utf-8") as f:
            doc = json.load(f)
        graph, warnings = load_emjson(doc)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        if args.op == "open":
            print(json.dumps(validate(graph)["stats"]))
        elif args.op == "validate":
            print(json.dumps(validate(graph), indent=2))
        elif args.op == "project-ttl":
            print(project_ttl(graph))
        elif args.op == "graphml":
            print(graph_to_graphml(graph))
    elif args.op == "import-graphml":
        print(json.dumps(graphml_to_emjson(Path(args.path).read_bytes())))
    elif args.op == "resolve":
        print(json.dumps(resolve_authority(args.term, args.facet), indent=2))
    elif args.op in ("list-resources", "resolve-resource"):
        with open(args.path, encoding="utf-8") as f:
            doc = json.load(f)
        graph, warnings = load_emjson(doc)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        if args.op == "list-resources":
            print(json.dumps(list_resources(graph), indent=2))
        else:
            print(json.dumps(resolve_resource(graph, args.resource_id), indent=2))
    elif args.op == "scan-resources":
        print(json.dumps(scan_fs_resources(args.folder), indent=2))
    elif args.op == "connection-report":
        with open(args.path, encoding="utf-8") as f:
            doc = json.load(f)
        graph, warnings = load_emjson(doc)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        rep = connection_report(graph, max_cases=args.max_cases,
                                diagnose_generic_edges=args.diagnose_generic)
        if args.json:
            print(json.dumps(rep, indent=2))
        else:
            from .edges.connection_resolver import format_connection_report
            print(format_connection_report(rep))
    elif args.op == "detach-dtc":
        with open(args.path, encoding="utf-8") as f:
            doc = json.load(f)
        graph, warnings = load_emjson(doc)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        print(json.dumps(detach_dtc(graph, args.process_id), indent=2))
    elif args.op == "shelf-new":
        shelf = new_shelf(graph_id=args.graph_id, name=args.name)
        save_shelf(shelf, args.path)
        print(json.dumps({"ok": True, "path": args.path, "graph_id": args.graph_id}))
    elif args.op == "shelf-list":
        shelf, warnings = load_shelf(args.path)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        print(json.dumps(list_shelf(shelf), indent=2))
    elif args.op == "shelf-add":
        shelf, warnings = load_shelf(args.path)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        origin = None
        if args.origin_repo or args.capabilities or args.scope:
            origin = {}
            if args.origin_repo:
                origin["repo"] = args.origin_repo
            if args.capabilities:
                origin["capabilities"] = [c.strip() for c in args.capabilities.split(",") if c.strip()]
            if args.scope:
                origin["scope"] = args.scope
        entry = add_to_shelf(shelf, args.locator, resource_id=args.resource_id,
                             name=args.name, resource_type=args.resource_type,
                             origin=origin)
        save_shelf(shelf, args.path)
        print(json.dumps(entry, indent=2))
    elif args.op == "shelf-remove":
        shelf, warnings = load_shelf(args.path)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        removed = remove_from_shelf(shelf, args.resource_id)
        save_shelf(shelf, args.path)
        print(json.dumps({"ok": True, "removed": removed}))
    elif args.op == "shelf-instantiate":
        shelf, sw = load_shelf(args.path)
        for w in sw:
            print(f"warning: {w}", file=sys.stderr)
        target, tw = load_emjson_file(args.target)
        for w in tw:
            print(f"warning: {w}", file=sys.stderr)
        node = instantiate_from_shelf(shelf, args.resource_id, target)
        from .exporter.emjson_exporter import export_emjson
        export_emjson(target, args.target)
        print(json.dumps({"ok": True, "resource_id": node.node_id,
                          "target": args.target}))
    elif args.op in ("acquire", "acquire-map"):
        import os as _os
        if args.op == "acquire":
            with open(args.descriptor, encoding="utf-8") as f:
                descriptor = json.load(f)
        else:  # acquire-map
            with open(args.record, encoding="utf-8") as f:
                record = json.load(f)
            descriptor = apply_acquisition_mapping(args.source, record)
        # load-or-create the shelf
        if _os.path.isfile(args.shelf):
            shelf, sw = load_shelf(args.shelf)
            for w in sw:
                print(f"warning: {w}", file=sys.stderr)
        else:
            shelf = new_shelf()
        info, shelf = acquire_from_descriptor(descriptor, shelf)
        save_shelf(shelf, args.shelf)
        out = {"ok": True, "shelf": args.shelf, **info}
        if args.op == "acquire-map":
            out["descriptor"] = descriptor
        print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
