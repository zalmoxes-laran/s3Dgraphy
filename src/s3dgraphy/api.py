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
    dd = sub.add_parser("detach-dtc", help="extract a DTC → standalone JSON record")
    dd.add_argument("path")
    dd.add_argument("process_id")
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
    elif args.op == "detach-dtc":
        with open(args.path, encoding="utf-8") as f:
            doc = json.load(f)
        graph, warnings = load_emjson(doc)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        print(json.dumps(detach_dtc(graph, args.process_id), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
