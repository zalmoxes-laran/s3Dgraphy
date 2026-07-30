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
_ACQ_TYPE = "dtc_acquisition"
# RM edges (verified in the connections datamodel): RM ─has_linked_resource→
# LinkNode (P67_refers_to, the R0 hinge); entity ─has_representation_model→ RM
# (P138i_has_representation).
_EDGE_HAS_LINKED = "has_linked_resource"
_EDGE_HAS_RM = "has_representation_model"


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


# ── hatting: shelf resource → RepresentationModel (C2) ──────────────────────────
def _rm_referencing(graph: Any, resource_id: str):
    """An existing RepresentationModel that already references ``resource_id`` via
    has_linked_resource, or None."""
    for e in graph.edges:
        if e.edge_type == _EDGE_HAS_LINKED and e.edge_target == resource_id:
            n = graph.find_node_by_id(e.edge_source)
            if n is not None and getattr(n, "node_type", None) == _RM_TYPE:
                return n
    return None


def hat_as_representation_model(target_graph: Any, resource_id: str, *,
                                shelf: Any = None, rm_id: Optional[str] = None,
                                name: Optional[str] = None,
                                attach_to: Optional[str] = None) -> Dict[str, Any]:
    """Hat a shelf resource into ``target_graph`` as a **RepresentationModel**.

    Reference-by-stable-ID (R0 hinge): the Resource (LinkNode) is referenced into
    the target graph (from ``shelf`` if given, else it must already be present),
    and a RepresentationModelNode is created that references it via
    ``has_linked_resource`` (P67). Optionally the RM is attached to an entity
    (``attach_to``: an Epoch / Stratigraphic / Document node) via
    ``has_representation_model`` (P138i). Reuse-not-duplicate + idempotent: if an
    RM already references the resource it is reused. Returns
    ``{rm_id, resource_id, created, attached}``. No mesh import (that is EMTools)."""
    from ..nodes import RepresentationModelNode

    # 1) reference the Resource into the target graph
    if shelf is not None:
        res = instantiate_from_shelf(shelf, resource_id, target_graph)
    else:
        res = target_graph.find_node_by_id(resource_id)
        if res is None or getattr(res, "node_type", None) != _LINK_TYPE:
            raise ValueError(f"{resource_id!r} is not a resource in the target graph")

    # 2) reuse an existing RM (idempotent) or create one referencing the resource
    rm = _rm_referencing(target_graph, resource_id)
    created = False
    if rm is None:
        rid = rm_id or f"rm_{resource_id}"
        existing = target_graph.find_node_by_id(rid)
        if existing is not None and getattr(existing, "node_type", None) == _RM_TYPE:
            rm = existing
        else:
            rm = RepresentationModelNode(
                node_id=rid,
                name=name or f"RM of {str(getattr(res, 'name', '') or resource_id)}",
                type="RM")
            target_graph.add_node(rm)
        if not _has_edge(target_graph, rm.node_id, resource_id, _EDGE_HAS_LINKED):
            target_graph.add_edge(f"{rm.node_id}__{_EDGE_HAS_LINKED}__{resource_id}",
                                  rm.node_id, resource_id, _EDGE_HAS_LINKED)
        created = True

    # 3) optional: entity ─has_representation_model→ RM (P138i)
    attached = False
    if attach_to and target_graph.find_node_by_id(attach_to) is not None:
        if not _has_edge(target_graph, attach_to, rm.node_id, _EDGE_HAS_RM):
            target_graph.add_edge(f"{attach_to}__{_EDGE_HAS_RM}__{rm.node_id}",
                                  attach_to, rm.node_id, _EDGE_HAS_RM)
            attached = True

    return {"rm_id": rm.node_id, "resource_id": resource_id,
            "created": created, "attached": attached}


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
