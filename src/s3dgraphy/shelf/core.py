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
# member). Heriverse ShelfGraph convention.
SHELF_COLLECTION = "shelf"
# conventional multigraph id for the per-study shelf (any id is accepted).
DEFAULT_SHELF_ID = "shelf"

_LINK_TYPE = "link"


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
