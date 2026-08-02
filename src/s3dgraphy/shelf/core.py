"""Shelf substrate ops (pure; no UI, no connectors).

A shelf is a :class:`~s3dgraphy.graph.Graph` whose nodes are LinkNode resources
(R0 stable IDs). It self-identifies via ``graph.data["em_collection"] == "shelf"``
so a standalone shelf file and a multigraph member are the same thing. Reuses the
resource layer (LinkNode = stable ID) and the em.json I/O.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

# graph.data marker so a shelf self-identifies (standalone file AND multigraph
# member) — the Heriverse **ShelfGraph** convention (E.D. 2026-07-30).
SHELF_COLLECTION = "ShelfGraph"
# conventional multigraph id for the per-study shelf (any id is accepted).
DEFAULT_SHELF_ID = "shelf"

_LINK_TYPE = "link"
_RM_TYPE = "representation_model"
_RMSF_TYPE = "representation_model_sf"
_RMDOC_TYPE = "representation_model_doc"
_DOC_TYPE = "document"
_ACQ_TYPE = "dtc_acquisition"

# Facet edges — ALL verified in the connections datamodel.
#
# The P67 hinge is invariant across every facet:
#   facet ─has_linked_resource→ LinkNode        (P67_refers_to, the R0 hinge)
# What changes per facet is the edge towards *what it represents / documents*:
#   RM       ─has_first_epoch→ EpochNode         (P10_falls_within, first epoch)
#   RM       ─survive_in_epoch→ EpochNode        (P132, the further epochs)
#   SF       ─has_representation_model_sf→ RMSF  (P138i_has_representation)
#   Document ─has_representation_model_doc→ RMDoc (P138i_has_representation)
#   Extractor ─extracted_from→ Document          (P67 / J7 — the paradata entry)
#   strat    ─has_documentation→ Document        (P70i_is_documented_in)
#   paradata ─has_visual_reference→ Document     (P138i)
_EDGE_HAS_LINKED = "has_linked_resource"
_EDGE_HAS_RM_SF = "has_representation_model_sf"
_EDGE_HAS_RM_DOC = "has_representation_model_doc"
_EDGE_HAS_FIRST_EPOCH = "has_first_epoch"
_EDGE_SURVIVE_IN_EPOCH = "survive_in_epoch"
_EDGE_EXTRACTED_FROM = "extracted_from"
_EDGE_HAS_DOCUMENTATION = "has_documentation"
_EDGE_HAS_VISUAL_REF = "has_visual_reference"

# Attach-edge candidates for the Document facet, most specific first. The
# datamodel decides which one applies (validate_connection): an Extractor target
# takes ``extracted_from`` (the paradata chain), a stratigraphic node takes
# ``has_documentation``, any other paradata node takes ``has_visual_reference``.
_DOC_ATTACH_EDGES = (_EDGE_EXTRACTED_FROM, _EDGE_HAS_DOCUMENTATION,
                     _EDGE_HAS_VISUAL_REF)


def _has_edge(graph: Any, src: str, tgt: str, edge_type: str) -> bool:
    return any(e.edge_source == src and e.edge_target == tgt
               and e.edge_type == edge_type for e in graph.edges)


def new_shelf(graph_id: str = DEFAULT_SHELF_ID, name: Optional[str] = None):
    """Create an empty shelf-graph tagged as a shelf collection."""
    from ..graph import Graph
    g = Graph(graph_id=graph_id, name=name or "Shelf")
    if not isinstance(getattr(g, "data", None), dict):
        g.data = {}
    g.data["em_collection"] = SHELF_COLLECTION
    return g


def is_shelf(graph: Any) -> bool:
    """True if ``graph`` is tagged as a shelf collection."""
    d = getattr(graph, "data", None) or {}
    return d.get("em_collection") == SHELF_COLLECTION


def _data(node: Any) -> Dict[str, Any]:
    d = getattr(node, "data", None)
    if not isinstance(d, dict):
        d = {}
        setattr(node, "data", d)
    return d


def _entry(node: Any) -> Dict[str, Any]:
    """One shelf entry — aligned with ``api.list_resources`` / ``shelf_resources``
    (id/name/locator/kind) PLUS the preserved capability/origin + resource_type."""
    from ..resources import classify_locator, stable_resource_id
    d = _data(node)
    url = d.get("url", "") or getattr(node, "url", "") or ""
    return {
        "id": stable_resource_id(node),
        "name": str(getattr(node, "name", "") or ""),
        "locator": url,
        "kind": classify_locator(url),
        "resource_type": d.get("resource_type", ""),
        "origin": d.get("origin"),  # capability/origin — never stripped
    }


def add_to_shelf(shelf: Any, locator: str, *, resource_id: Optional[str] = None,
                 name: Optional[str] = None, url_type: Optional[str] = None,
                 description: Optional[str] = None,
                 resource_type: Optional[str] = None,
                 origin: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Add a resource to the shelf and return its entry.

    Reuse-not-duplicate: if ``resource_id`` is already present, the existing
    LinkNode is updated (locator/origin), not duplicated. ``origin`` is the
    capability/origin envelope (``repo``, ``capabilities``, ``scope``, …) preserved
    for downstream tier badges."""
    from ..nodes.link_node import LinkNode
    rid = resource_id or str(uuid.uuid4())
    node = shelf.find_node_by_id(rid)
    if node is None or getattr(node, "node_type", None) != _LINK_TYPE:
        node = LinkNode(node_id=rid, name=name or "Unnamed Resource",
                        url=locator or "", url_type=url_type or "",
                        description=description or "")
        shelf.add_node(node)
    else:
        if locator:
            _data(node)["url"] = locator
        if name:
            node.name = name
    d = _data(node)
    if resource_type is not None:
        d["resource_type"] = resource_type
    if origin is not None:
        d["origin"] = origin
    return _entry(node)


def list_shelf(shelf: Any) -> List[Dict[str, Any]]:
    """List the shelf's resources (LinkNodes) with their capability/origin. Pure
    read; aligned to the resource-entry shape used across the api."""
    return [_entry(n) for n in getattr(shelf, "nodes", []) or []
            if getattr(n, "node_type", None) == _LINK_TYPE]


def remove_from_shelf(shelf: Any, resource_id: str) -> bool:
    """Remove a resource from the shelf. Returns True if it was present."""
    node = shelf.find_node_by_id(resource_id)
    if node is None or getattr(node, "node_type", None) != _LINK_TYPE:
        return False
    shelf.remove_node(resource_id)
    return True


def save_shelf(shelf: Any, path: str) -> str:
    """Persist the shelf as a STANDALONE em.json file (reusable in any study).
    Returns the written path."""
    from ..exporter.emjson_exporter import export_emjson
    return export_emjson(shelf, path)


def load_shelf(path: str):
    """Load a standalone shelf em.json file → ``(graph, warnings)``. The graph is
    a normal Graph; check :func:`is_shelf` to confirm the collection tag."""
    from ..importer.emjson_importer import import_emjson
    return import_emjson(path)


def instantiate_from_shelf(shelf: Any, resource_id: str, target_graph: Any):
    """Reference a shelf resource into ``target_graph`` by its **stable ID**
    (HAT / reuse-not-duplicate). The same resource is referenced — never cloned
    under a new ID — and its capability/origin is preserved. If ``target_graph``
    already references the ID, that existing node is returned (no duplicate). The
    resource STAYS on the shelf (the library keeps it). Returns the target node."""
    from ..nodes.link_node import LinkNode
    src = shelf.find_node_by_id(resource_id)
    if src is None or getattr(src, "node_type", None) != _LINK_TYPE:
        raise ValueError(f"{resource_id!r} is not a resource in the shelf")
    existing = target_graph.find_node_by_id(resource_id)
    if existing is not None:
        return existing  # already referenced — reuse, do not duplicate
    sd = _data(src)
    node = LinkNode(node_id=resource_id,  # SAME stable ID = the reference
                    name=str(getattr(src, "name", "") or resource_id),
                    url=sd.get("url", "") or "",
                    url_type=sd.get("url_type", "") or "",
                    description=str(getattr(src, "description", "") or ""))
    # carry the capability/origin (+ resource_type / dtc_kind) — do not strip
    d = _data(node)
    for k in ("resource_type", "origin", "dtc_kind"):
        if k in sd:
            d[k] = sd[k]
    target_graph.add_node(node)
    return node


# ── hatting: shelf resource → a FACET node (C2 = RM; C3 = RMSF/RMDoc/Document) ──
#
# The ROLE determines the facet, and the facets are NOT exclusive: the same
# Resource may carry several at once (a photogrammetric model is typically an RM
# of the epoch it depicts AND, when it is used as evidence in a reasoning chain,
# a Document). Each facet is a distinct node TYPE, so they never collide: the
# reuse lookup is per node type.
def _facet_referencing(graph: Any, resource_id: str, node_type: str):
    """An existing node of ``node_type`` that already references ``resource_id``
    via has_linked_resource (the facet is already hatted), or None."""
    for e in graph.edges:
        if e.edge_type == _EDGE_HAS_LINKED and e.edge_target == resource_id:
            n = graph.find_node_by_id(e.edge_source)
            if n is not None and getattr(n, "node_type", None) == node_type:
                return n
    return None


def _rm_referencing(graph: Any, resource_id: str):
    """The RepresentationModel facet of ``resource_id`` (C2 name, kept)."""
    return _facet_referencing(graph, resource_id, _RM_TYPE)


def _reference_resource(target_graph: Any, resource_id: str, shelf: Any):
    """Reference the Resource (LinkNode) into ``target_graph`` by stable ID — from
    ``shelf`` when given, else it must already be present. The R0 hinge."""
    if shelf is not None:
        return instantiate_from_shelf(shelf, resource_id, target_graph)
    res = target_graph.find_node_by_id(resource_id)
    if res is None or getattr(res, "node_type", None) != _LINK_TYPE:
        raise ValueError(f"{resource_id!r} is not a resource in the target graph")
    return res


# Correct resolution of the datamodel's allowed_connections. Written here for C3,
# now shared: the canonical implementation lives in `edges.connection_resolver`
# (S1) so the report-only pass in the core and these facet ops cannot drift.
# Stricter than `Graph.validate_connection`, which resolves the allowed CLASS
# names through the node_type-keyed map and therefore lets any endpoint pass
# whenever the name is not also a node_type.
from ..edges.connection_resolver import (  # noqa: E402
    allowed_endpoints as _allowed_endpoints,
    connection_allowed as _connection_allowed,
    endpoint_matches as _endpoint_ok,
    resolve_node_class as _resolve_node_class,
)


def _attach(target_graph: Any, src_id: str, tgt_id: str, edge_type: str) -> bool:
    """Attach ``src ─edge_type→ tgt`` ONLY when the datamodel allows it.

    Returns True when the edge is (now) present, False when either endpoint is
    missing or the connection is not allowed for these node types — so a wrong
    target is REFUSED rather than degraded to a ``generic_connection`` by
    ``add_edge``."""
    src = target_graph.find_node_by_id(src_id)
    tgt = target_graph.find_node_by_id(tgt_id)
    if src is None or tgt is None:
        return False
    if not _connection_allowed(src, tgt, edge_type):
        return False
    if _has_edge(target_graph, src_id, tgt_id, edge_type):
        return True
    target_graph.add_edge(f"{src_id}__{edge_type}__{tgt_id}", src_id, tgt_id, edge_type)
    return True


def _hat_facet(target_graph: Any, resource_id: str, *, shelf: Any, node_type: str,
               factory, default_prefix: str, node_id: Optional[str]):
    """Shared facet body: reference the Resource, then reuse-or-create the facet
    node and wire the P67 hinge. Returns ``(facet_node, created, resource_node)``.
    ``factory(node_id, resource_node)`` builds the node when one is needed."""
    res = _reference_resource(target_graph, resource_id, shelf)
    node = _facet_referencing(target_graph, resource_id, node_type)
    if node is not None:
        return node, False, res  # idempotent: this facet already exists
    nid = node_id or f"{default_prefix}{resource_id}"
    existing = target_graph.find_node_by_id(nid)
    if existing is not None and getattr(existing, "node_type", None) == node_type:
        node = existing  # reuse a node the caller already created (one shape)
    else:
        node = factory(nid, res)
        target_graph.add_node(node)
    if not _has_edge(target_graph, node.node_id, resource_id, _EDGE_HAS_LINKED):
        target_graph.add_edge(f"{node.node_id}__{_EDGE_HAS_LINKED}__{resource_id}",
                              node.node_id, resource_id, _EDGE_HAS_LINKED)
    return node, True, res


def _res_name(res: Any, resource_id: str) -> str:
    return str(getattr(res, "name", "") or resource_id)


# The four facets, and the attach edge(s) each one may use. Keys are the public
# facet names a UI shows the user; the edge list is ordered most-specific-first.
FACETS = ("rm", "rmsf", "rmdoc", "document")
_FACET_ATTACH_EDGES = {
    "rm": (_EDGE_HAS_FIRST_EPOCH,),   # RM ──→ Epoch  (the facet is the SOURCE)
    "rmsf": (_EDGE_HAS_RM_SF,),       # SF ──→ RMSF   (the facet is the TARGET)
    "rmdoc": (_EDGE_HAS_RM_DOC,),     # Document ──→ RMDoc
    "document": _DOC_ATTACH_EDGES,    # Extractor / strat / paradata ──→ Document
}
_FACET_NODE_TYPE = {"rm": _RM_TYPE, "rmsf": _RMSF_TYPE, "rmdoc": _RMDOC_TYPE,
                    "document": _DOC_TYPE}


def _facet_class(facet: str):
    from ..nodes.base_node import Node
    return Node.node_type_map[_FACET_NODE_TYPE[facet]]


def attach_candidates(facet: str, graph: Any) -> List[Dict[str, Any]]:
    """The nodes of ``graph`` that may be the attach target of ``facet``, as
    ``[{id, name, node_type, edge}]``.

    Computed FROM THE DATAMODEL (allowed_connections), so a picker never
    hardcodes a type list: ``rm`` yields the EpochNodes the RM can point at
    (ordered by ``start_time`` — the caller keeps that order, first =
    ``has_first_epoch``); ``rmsf`` yields Special Finds, ``rmdoc`` the nodes a
    RMDoc can be instantiated from (Document / Extractor / Combiner), and
    ``document`` the nodes that can point at a Document (Extractor → the
    paradata chain, stratigraphic → documentation, other paradata → visual
    reference)."""
    facet = (facet or "").lower()
    if facet not in _FACET_ATTACH_EDGES:
        raise ValueError(f"unknown facet {facet!r} (expected one of {FACETS})")
    probe = _facet_class(facet)
    out: List[Dict[str, Any]] = []
    for node in getattr(graph, "nodes", []) or []:
        for edge_type in _FACET_ATTACH_EDGES[facet]:
            ends = _allowed_endpoints(edge_type)
            if ends is None:
                continue
            if facet == "rm":  # the facet is the edge SOURCE, the node the target
                ok = _endpoint_ok(probe, ends[0]) and _endpoint_ok(node, ends[1])
            else:              # the node is the edge SOURCE, the facet the target
                ok = _endpoint_ok(node, ends[0]) and _endpoint_ok(probe, ends[1])
            if ok:
                out.append({"id": node.node_id,
                            "name": str(getattr(node, "name", "") or node.node_id),
                            "node_type": getattr(node, "node_type", ""),
                            "edge": edge_type})
                break
    if facet == "rm":  # chronological: the oldest epoch is the RM's first epoch
        order = {n.node_id: i for i, n in enumerate(getattr(graph, "nodes", []) or [])}
        out.sort(key=lambda c: (
            _start_time(graph.find_node_by_id(c["id"])), order.get(c["id"], 0)))
    return out


def _start_time(node: Any) -> float:
    v = getattr(node, "start_time", None)
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("inf")


def hat_as_representation_model(target_graph: Any, resource_id: str, *,
                                shelf: Any = None, rm_id: Optional[str] = None,
                                name: Optional[str] = None,
                                epochs: Optional[List[str]] = None,
                                attach_to: Optional[str] = None) -> Dict[str, Any]:
    """Hat a shelf resource into ``target_graph`` as a **RepresentationModel**.

    An RM represents a real or reconstructed STATE, so it binds to one or more
    **EpochNodes** — a photogrammetric model of the current state is the RM of
    the epoch it depicts. Following the RM Manager convention (and the
    datamodel), the first epoch gets ``has_first_epoch`` and the remaining ones
    ``survive_in_epoch``; ``epochs`` is an ORDERED list (the caller sorts, e.g.
    by ``start_time``). A target that is not an EpochNode is REFUSED and returned
    in ``skipped`` — an RM does not bind to a US (that was the C2.1 off-target
    attach; a US binds to a Document instead, see :func:`hat_as_document`).

    ``attach_to`` is the deprecated single-target alias of ``epochs`` (kept so
    the C2 signature does not break) — it means "this RM's epoch".

    Reference-by-stable-ID (R0 hinge) + reuse-not-duplicate + idempotent.
    Returns ``{rm_id, resource_id, created, epochs, skipped, attached}``.
    No mesh import (that is EMTools)."""
    from ..nodes import RepresentationModelNode

    rm, created, res = _hat_facet(
        target_graph, resource_id, shelf=shelf, node_type=_RM_TYPE,
        default_prefix="rm_", node_id=rm_id,
        factory=lambda nid, r: RepresentationModelNode(
            node_id=nid, name=name or f"Model for {_res_name(r, resource_id)}",
            type="RM"))

    # epochs: first → has_first_epoch, the rest → survive_in_epoch (RM Manager)
    targets: List[str] = [e for e in (epochs or []) if e]
    if attach_to and attach_to not in targets:
        targets.append(attach_to)
    attached_epochs: List[str] = []
    skipped: List[str] = []
    bound = {e.edge_target for e in target_graph.edges
             if e.edge_source == rm.node_id
             and e.edge_type in (_EDGE_HAS_FIRST_EPOCH, _EDGE_SURVIVE_IN_EPOCH)}
    has_first = any(e.edge_type == _EDGE_HAS_FIRST_EPOCH
                    and e.edge_source == rm.node_id for e in target_graph.edges)
    for tid in targets:
        if tid in bound:  # already this RM's epoch — never bind it twice
            attached_epochs.append(tid)
            continue
        edge_type = _EDGE_SURVIVE_IN_EPOCH if has_first else _EDGE_HAS_FIRST_EPOCH
        if _attach(target_graph, rm.node_id, tid, edge_type):
            attached_epochs.append(tid)
            bound.add(tid)
            has_first = True
        else:
            skipped.append(tid)

    return {"rm_id": rm.node_id, "resource_id": resource_id, "created": created,
            "epochs": attached_epochs, "skipped": skipped,
            "attached": bool(attached_epochs)}


def hat_as_rmsf(target_graph: Any, resource_id: str, *, shelf: Any = None,
                rmsf_id: Optional[str] = None, name: Optional[str] = None,
                attach_to: Optional[str] = None) -> Dict[str, Any]:
    """Hat a shelf resource as a **RepresentationModelSpecialFind** (RMSF).

    An RMSF is the 3D representation of a **Special Find** — e.g. a scanned
    capital repositioned by an anastylosis hypothesis. ``attach_to`` is the SF
    node: ``SF ─has_representation_model_sf→ RMSF`` (P138i, the datamodel's
    purpose-built edge). Non-SF targets are refused (``attached`` stays False).
    Reuse-not-duplicate + idempotent. Returns
    ``{rmsf_id, resource_id, created, attached}``."""
    from ..nodes.representation_node import RepresentationModelSpecialFindNode

    rmsf, created, res = _hat_facet(
        target_graph, resource_id, shelf=shelf, node_type=_RMSF_TYPE,
        default_prefix="rmsf_", node_id=rmsf_id,
        factory=lambda nid, r: RepresentationModelSpecialFindNode(
            node_id=nid, name=name or f"RMSF for {_res_name(r, resource_id)}",
            type="RM"))

    attached = bool(attach_to) and _attach(target_graph, attach_to, rmsf.node_id,
                                           _EDGE_HAS_RM_SF)
    return {"rmsf_id": rmsf.node_id, "resource_id": resource_id,
            "created": created, "attached": attached}


def hat_as_rmdoc(target_graph: Any, resource_id: str, *, shelf: Any = None,
                 rmdoc_id: Optional[str] = None, name: Optional[str] = None,
                 attach_to: Optional[str] = None,
                 geometry: Optional[str] = None) -> Dict[str, Any]:
    """Hat a shelf resource as a **RepresentationModelDoc** (RMDoc).

    An RMDoc instantiates a **Document** (or an Extractor / Combiner) in the 3D
    scene — the canonical case being a historical photo placed where it was
    taken. ``attach_to`` is the Document node:
    ``Document ─has_representation_model_doc→ RMDoc`` (P138i).

    Unlike an RM, an RMDoc is NOT bound to an epoch or to a stratigraphic unit.
    What grades it is ``geometry`` — the **metric authority of its placement**
    (Q-C), on the RMDoc because the RMDoc *is* the spatial instance:
    ``reality_based → observable → asserted → symbolic``, with ``em_based``
    outside the ladder as a provenance statement. ``None`` leaves the placement
    unclassified rather than asserting a grade.

    This replaces the C3 ``data["placement"] = "manual"|"anchored"`` literal,
    which stated a workflow fact instead of a qualia and had no vocabulary
    behind it. Reuse-not-duplicate + idempotent. Returns
    ``{rmdoc_id, resource_id, created, attached, geometry}``."""
    from ..nodes.document_node import DOCUMENT_GEOMETRIES
    from ..nodes.representation_node import RepresentationModelDocNode

    if geometry is not None and geometry not in DOCUMENT_GEOMETRIES:
        raise ValueError(
            f"RMDoc geometry must be one of {DOCUMENT_GEOMETRIES} or None, "
            f"got {geometry!r}")

    rmdoc, created, res = _hat_facet(
        target_graph, resource_id, shelf=shelf, node_type=_RMDOC_TYPE,
        default_prefix="rmdoc_", node_id=rmdoc_id,
        factory=lambda nid, r: RepresentationModelDocNode(
            node_id=nid, name=name or f"RM Doc for {_res_name(r, resource_id)}",
            type="RM"))
    if geometry is not None:
        _data(rmdoc)["geometry"] = geometry

    attached = bool(attach_to) and _attach(target_graph, attach_to, rmdoc.node_id,
                                           _EDGE_HAS_RM_DOC)
    return {"rmdoc_id": rmdoc.node_id, "resource_id": resource_id,
            "created": created, "attached": attached,
            "geometry": _data(rmdoc).get("geometry")}


def hat_as_document(target_graph: Any, resource_id: str, *, shelf: Any = None,
                    doc_id: Optional[str] = None, name: Optional[str] = None,
                    description: str = "", role: Optional[str] = None,
                    content_nature: Optional[str] = None,
                    geometry: Optional[str] = None, mark_as_canonical: bool = True,
                    attach_to: Optional[str] = None) -> Dict[str, Any]:
    """Hat a shelf resource as a **Document** (E31) — a SOURCE, no placement.

    This is the paradata entry point: the resource is used as EVIDENCE in a
    source-criticism chain, so an ExtractorNode can later read from it
    (``Extractor ─extracted_from→ Document``). A photogrammetric model becomes a
    Document only when it is used this way — which does not stop it from ALSO
    being an RM of its epoch (the facets are not exclusive).

    Nothing is spatialized here: the Document only references the Resource via
    ``has_linked_resource`` (P67). ``role`` / ``content_nature`` / ``geometry``
    are the three EM 1.6 classification axes, passed through to
    :class:`DocumentNode` (which validates them against ``em_visual_rules``);
    ``mark_as_canonical`` sets ``attributes['em_canonical_document']``, the flag
    EMTools' Document Manager / GraphML patcher already use.

    ``doc_id`` naming an EXISTING DocumentNode reuses it — that is how EMTools
    keeps ONE document shape (``create_master_document_node`` builds the node,
    this op wires the hinge). ``attach_to`` picks its edge from the datamodel:
    an Extractor gets ``extracted_from``, a stratigraphic node
    ``has_documentation`` (P70i), another paradata node
    ``has_visual_reference``. Reuse-not-duplicate + idempotent. Returns
    ``{doc_id, resource_id, created, attached, attach_edge}``."""
    from ..nodes.document_node import DocumentNode

    def _factory(nid: str, r: Any) -> Any:
        node = DocumentNode(node_id=nid,
                            name=name or _res_name(r, resource_id),
                            description=description, role=role,
                            content_nature=content_nature, geometry=geometry)
        if mark_as_canonical:
            if getattr(node, "attributes", None) is None:
                node.attributes = {}
            node.attributes["em_canonical_document"] = True
        return node

    doc, created, res = _hat_facet(
        target_graph, resource_id, shelf=shelf, node_type=_DOC_TYPE,
        default_prefix="doc_", node_id=doc_id, factory=_factory)

    attached, attach_edge = False, ""
    if attach_to:
        for edge_type in _DOC_ATTACH_EDGES:
            if _attach(target_graph, attach_to, doc.node_id, edge_type):
                attached, attach_edge = True, edge_type
                break

    return {"doc_id": doc.node_id, "resource_id": resource_id, "created": created,
            "attached": attached, "attach_edge": attach_edge}


# ── remove with acquisition-event cleanup (C2) ──────────────────────────────────
def remove_resource(graph: Any, resource_id: str) -> Dict[str, Any]:
    """Remove a shelf resource and clean up its now-orphan acquisition event.

    If the resource is still referenced by a NON-acquisition node in ``graph``
    (e.g. an RM ``has_linked_resource`` to it — i.e. hatted into this graph),
    nothing is removed (``removed=False, referenced=True``) — the reference-check.
    Otherwise the resource is removed (cascading its edges) and any
    ``dtc_acquisition`` event left with no remaining ``dtc_had_output`` is removed
    too. Returns ``{removed, referenced, events_removed}``."""
    node = graph.find_node_by_id(resource_id)
    if node is None or getattr(node, "node_type", None) != _LINK_TYPE:
        return {"removed": False, "referenced": False, "events_removed": 0}
    # referenced by a non-acquisition node? → keep it (and its event)
    for e in graph.edges:
        if e.edge_target == resource_id:
            src = graph.find_node_by_id(e.edge_source)
            if src is not None and getattr(src, "node_type", None) != _ACQ_TYPE:
                return {"removed": False, "referenced": True, "events_removed": 0}
    # acquisition events that output this resource
    acq_ids = {e.edge_source for e in graph.edges
               if e.edge_type == "dtc_had_output" and e.edge_target == resource_id}
    remove_from_shelf(graph, resource_id)  # removes resource + cascades its edges
    events_removed = 0
    for aid in acq_ids:
        acq = graph.find_node_by_id(aid)
        if acq is None or getattr(acq, "node_type", None) != _ACQ_TYPE:
            continue
        still = any(e.edge_type == "dtc_had_output" and e.edge_source == aid
                    for e in graph.edges)
        if not still:
            graph.remove_node(aid)
            events_removed += 1
    return {"removed": True, "referenced": False, "events_removed": events_removed}
