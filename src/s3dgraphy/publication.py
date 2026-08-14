"""Promotion: a working model becomes a PUBLISHED asset, referenced.

The inverse of `import_geometry` (CMD1), and the activation of DP-76. Until now
a 3D model lived *inside* the .blend: the file was both the workshop and the
archive, which is why a .blend grows to gigabytes and why nobody but its author
can point at what is in it.

Promotion separates the two. The mesh is exported once, in the canonical format
(glTF, what Heriverse/ATON read), published into the room's asset store, and the
graph stops carrying it: the ResourceNode becomes a **reference** — a URL and a
checksum — to bytes that live where everybody can reach them. The .blend stays
the hi-res container you work in; the asset of record is the published one.

**Nothing here is a new node type.** The ResourceNode already had `url`,
`checksum` and `residency` (SHELF1), and the genesis of a digital object already
had a shape: a `DTCProcessNode` (crmdig:D7) with `dtc_had_input` /
`dtc_had_output`. Promotion is those pieces, arranged — an "export" concept
invented for the occasion would have been a second vocabulary for a thing the
DTC already says.

What the event records is the sentence a reader needs: *this published asset was
produced, by this hand, at this time, from that working model.*
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .graph import Graph
from .nodes import DTCProcessNode, ResourceNode

#: Deterministic ids for the promotion chain — the same promotion asked twice is
#: the same promotion, and re-sending it must not build a second event.
_PROMOTE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL,
                                "https://w3id.org/em/promotion")

#: The DTC `process` axis term for "this was made from that". Not a new word:
#: it is the one the DTC vocabulary already uses for a genesis event.
PROMOTION_KIND = "transformation"

#: A published asset arrives over http(s), and the ResourceNode's own url-sniffing
#: would then call a glTF model a "web_page" — true of the transport, useless to a
#: reader. When the uploader tells us the media type, we believe the media type.
_URL_TYPE_BY_MEDIA = {
    "model/gltf-binary": "3d_model",
    "model/gltf+json": "3d_model",
    "application/octet-stream": None,      # says nothing: leave the sniff alone
    "image/jpeg": "image",
    "image/png": "image",
    "application/pdf": "document",
}


def _stable_id(key: str) -> str:
    return str(uuid.uuid5(_PROMOTE_NAMESPACE, key))


@dataclass
class PromotionResult:
    """What the promotion produced, and what did not line up."""

    resource_id: str
    process_id: str
    source_id: Optional[str] = None
    node_ids: List[str] = field(default_factory=list)
    edge_ids: List[str] = field(default_factory=list)
    created: bool = False
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "process_id": self.process_id,
            "source_id": self.source_id,
            "node_ids": list(self.node_ids),
            "edge_ids": list(self.edge_ids),
            "created": self.created,
            "warnings": list(self.warnings),
        }


def _ensure_edge(graph: Graph, source: str, target: str, edge_type: str,
                 result: PromotionResult) -> None:
    edge_id = _stable_id(f"edge|{source}|{edge_type}|{target}")
    for edge in graph.edges:
        if (edge.edge_source, edge.edge_type, edge.edge_target) == (source, edge_type, target):
            result.edge_ids.append(getattr(edge, "edge_id", edge_id))
            return
    try:
        graph.add_edge(edge_id, source, target, edge_type)
        result.edge_ids.append(edge_id)
    except ValueError as exc:
        result.warnings.append(f"promotion: edge {edge_type} not created: {exc}")


def promote_resource(graph: Graph, resource_id: str, *, url: str, sha256: str,
                     media_type: Optional[str] = None,
                     author: Optional[str] = None,
                     at: Optional[str] = None,
                     source_id: Optional[str] = None,
                     link_to: Optional[str] = None,
                     name: Optional[str] = None) -> PromotionResult:
    """Publish a resource: `reference` residency, url + checksum, and a D7 event.

    Args:
        graph: the study graph.
        resource_id: the ResourceNode being published. Created if absent — a
            promotion of something the graph did not know about is still a fact
            about an asset, and refusing it would only push the caller into
            making the node itself, badly.
        url: where the published bytes are (the room's asset endpoint).
        sha256: their digest, `sha256:<hex>` or the bare hex. It is what makes
            the reference verifiable: a URL alone says where to look, not what
            you should find.
        media_type: recorded as `resource_type` when given.
        author / at: stamped on the event. The hand and the instant are the
            whole point of recording a genesis.
        source_id: the WORKING resource this was produced from, when there is
            one to name. Absent is honest — often the source is a .blend nobody
            has published, and inventing a node for it would put a thing in the
            graph that nobody can fetch.
        link_to: the node the published asset DEPICTS (typically the
            stratigraphic unit whose mesh was exported), attached with the
            existing `has_linked_resource` — the same hinge the shelf uses. An
            asset nothing points at is a file in a bucket.

    Returns:
        :class:`PromotionResult` — the ids of everything touched, so a caller can
        hand back a delta.

    Idempotent: the ids are derived from (resource, digest), so promoting the
    same bytes for the same resource twice converges instead of duplicating.
    """
    digest = str(sha256 or "").strip()
    if digest and not digest.startswith("sha256:"):
        # the algorithm travels with the value — a bare hex is unreadable later
        digest = f"sha256:{digest}"
    if not url:
        raise ValueError("promote_resource needs a url: a published asset that "
                         "nobody can fetch is not published")
    if not digest:
        raise ValueError("promote_resource needs a sha256: a reference without a "
                         "checksum is a promise, not a fact")

    process_id = _stable_id(f"promotion|{resource_id}|{digest}")
    result = PromotionResult(resource_id=resource_id, process_id=process_id,
                             source_id=source_id)

    # ── the resource becomes a REFERENCE ─────────────────────────────────────
    resource = graph.find_node_by_id(resource_id)
    if resource is None:
        resource = ResourceNode(resource_id, name=name or resource_id, url=url)
        graph.add_node(resource)
        result.created = True
    else:
        resource.url = url
        if name:
            resource.name = name
    data = getattr(resource, "data", None)
    if not isinstance(data, dict):
        data = {}
        resource.data = data
    data["url"] = url
    data["checksum"] = digest
    if media_type:
        data["media_type"] = media_type
        url_type = _URL_TYPE_BY_MEDIA.get(media_type)
        if url_type:
            data["url_type"] = url_type
    # `reference` and not `resident`: the bytes live in the store now, and the
    # study points at them. That IS the de-monolithisation (DP-76) — said in the
    # field the model already had, rather than in a new one.
    if hasattr(resource, "set_residency"):
        resource.set_residency("reference")
    else:                                      # pragma: no cover — older model
        data["residency"] = "reference"
    result.node_ids.append(resource_id)

    # ── the genesis: a DTC transformation, attributed and dated ──────────────
    process = graph.find_node_by_id(process_id)
    if process is None:
        process = DTCProcessNode(
            process_id,
            name=f"published {name or resource_id}",
            description="working model → published asset",
            dtc_kind=PROMOTION_KIND)
        graph.add_node(process)
        result.created = True
    _stamp(process, author=author, at=at)
    result.node_ids.append(process_id)

    _ensure_edge(graph, process_id, resource_id, "dtc_had_output", result)
    if source_id:
        if graph.find_node_by_id(source_id) is None:
            result.warnings.append(
                f"promotion: source '{source_id}' is not in the graph; the event "
                f"records the output only")
        else:
            _ensure_edge(graph, process_id, source_id, "dtc_had_input", result)
            _ensure_edge(graph, resource_id, source_id, "dtc_derived_from", result)

    if link_to:
        if graph.find_node_by_id(link_to) is None:
            result.warnings.append(
                f"promotion: '{link_to}' is not in the graph; the asset is "
                f"published but attached to nothing")
        else:
            _ensure_edge(graph, link_to, resource_id, "has_linked_resource", result)
            result.node_ids.append(link_to)

    return result


def _stamp(node: Any, *, author: Optional[str], at: Optional[str]) -> None:
    """Give the event its hand and its instant, through the editorial stamps.

    The same act as any other authored write (AUDIT1): `set_field`-style
    stamping, so the event carries who published and when — which is the only
    part of a promotion a reader cannot reconstruct from the bytes.
    """
    from .editorial import stamp_created, stamp_modified

    stamp_created(node, by=author, at=at)
    stamp_modified(node, by=author, at=at)


def promotion_delta(graph: Graph, result: PromotionResult) -> Dict[str, Any]:
    """The created/updated nodes and edges, in em.json shape — a delta to send.

    Serialised with the em.json exporter's own functions: a delta must be
    readable by exactly the same reader as a file, or the two drift and the drift
    shows up in somebody's project.
    """
    from .exporter.emjson_exporter import _edge_payload, _node_payload

    nodes = []
    for node_id in dict.fromkeys(result.node_ids):
        node = graph.find_node_by_id(node_id)
        if node is not None:
            nodes.append(_node_payload(node))
    by_id = {getattr(e, "edge_id", None): e for e in graph.edges}
    edges = []
    for edge_id in dict.fromkeys(result.edge_ids):
        edge = by_id.get(edge_id)
        if edge is not None:
            edges.append(_edge_payload(edge))
    return {"nodes": nodes, "edges": edges}
