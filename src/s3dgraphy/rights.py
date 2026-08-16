"""What may be done with ONE asset — read off the graph, never duplicated.

An asset is bytes in a store, addressed by its sha256. What those bytes are
*allowed to be* — who made them, under which licence, whether they are still
embargoed — is not a property of the store: it is said in the graph, on the
`ResourceNode` that points at them and on the DTC chain that produced them.

This module is the one place that knows how to walk from a **digest** to that
answer. The rule it exists to keep true:

    the asset store CONSULTS the graph; it does not keep a second copy of it.

A server that cached "this digest is embargoed until March" would be holding a
claim it cannot keep honest — the embargo lives in a document people edit, and
the copy would be wrong the first time somebody changed their mind.

**Two ways the rights attach, and both are read.** The simplest is directly on
the resource (`ResourceNode -has_license-> LicenseNode`), which is what an
authoring UI writes when somebody says "this photo is CC-BY". The other is
through the **DTC**: a process node that produced or consumed the resource
(`has_linked_resource`, `dtc_had_output`, `dtc_had_input`) carries the rights for
everything in that chain — which is how a whole acquisition campaign gets one
licence without stamping it on four hundred files. Direct wins when both are
present: the more specific statement is the one somebody made about *this*
object.

**Nothing is invented.** A resource with no licence reads as no licence
(`license: None`); the *default* is a separate question and it is answered where
a default belongs — `study.DEFAULT_LICENSE`, exposed beside the fact, never in
place of it. And an asset the graph has never heard of returns `None`: "I know
nothing about this digest" is not the same sentence as "this digest is free".
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from .crdt import is_removed
from .study import DEFAULT_LICENSE, embargo_active

#: How a resource reaches the DTC chunk that carries its rights. `has_linked_resource`
#: is the generic reference (P67); the two `dtc_*` edges are the chain's own
#: input/output. All three are followed in BOTH directions, because "the process
#: that produced this file" and "the file this process produced" are the same
#: fact written from two ends.
_CHAIN_EDGES = ("has_linked_resource", "dtc_had_output", "dtc_had_input")

#: The rights edges themselves. Their source may be a resource, a DTC node, or a
#: graph-self node — the datamodel deliberately leaves the source open, because
#: an embargo is a statement about *something*, at whatever scope it was made.
_RIGHTS_EDGES = {"has_license": "license",
                 "has_embargo": "embargo",
                 "has_author": "author"}


def normalise_digest(value: Any) -> Optional[str]:
    """`sha256:ab…` and `ab…` are the same digest. Answer in one spelling.

    Both forms are in the wild for a reason that is not going away: the graph
    stores `sha256:<hex>` (the algorithm travels with the value, as it should),
    and the IIIF identifier is the bare hex (Cantaloupe uses it as the object
    key). A lookup that understood only one of them would answer "unknown" for
    half the requests — measured, in the IIIF work.
    """
    if value in (None, ""):
        return None
    text = str(value).strip()
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    return text.lower() or None


def _sections(document: Any) -> List[Dict[str, Any]]:
    """Every graph in whatever was handed in — a container, a document, a Graph.

    Callers hold different things: em-server holds a raw container dict (and
    parsing it on every asset request would be a cost with no payer), a library
    caller holds a `Graph`. Both are walked here, in their own shape, rather
    than converted — a conversion would be the second reader this module exists
    to avoid.
    """
    if document is None:
        return []
    if isinstance(document, dict):
        graphs = document.get("graphs")
        if isinstance(graphs, dict):
            return [g for g in graphs.values() if isinstance(g, dict)]
        if "nodes" in document:
            return [document]
        return []
    # a Graph (or a Container) — duck-typed, so this module imports nothing
    graphs = getattr(document, "graphs", None)
    if isinstance(graphs, dict):
        out = []
        for graph in graphs.values():
            out.extend(_sections(graph))
        shelf = getattr(document, "shelf", None)
        if shelf is not None:
            out.extend(_sections(shelf))
        return out
    if hasattr(document, "nodes"):
        return [{"nodes": list(document.nodes), "edges": list(document.edges or [])}]
    return []


def _field(item: Any, *names: str) -> Any:
    """One reader for a node/edge that may be a dict or an object."""
    for name in names:
        if isinstance(item, dict):
            if name in item:
                return item[name]
        else:
            value = getattr(item, name, None)
            if value is not None:
                return value
    return None


def _data(node: Any) -> Dict[str, Any]:
    data = _field(node, "data")
    return data if isinstance(data, dict) else {}


def _alive(item: Any) -> bool:
    """Is this node/edge still standing, or is it a tombstone?

    A deletion in this ecosystem is a TOMBSTONE — the record stays in the
    document so a merge can see that somebody removed it. Which means a walk
    that reads the raw list keeps reading things nobody has any more. Measured
    live, and it was the worst possible one to get wrong: an embargo somebody
    had just lifted went on refusing the file, because the removed EmbargoNode
    was still sitting there being read.
    """
    payload = item if isinstance(item, dict) else getattr(item, "__dict__", {}) or {}
    try:
        return not is_removed(payload)
    except Exception:      # pragma: no cover — a shape crdt cannot read is alive
        return True


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        picked = value.get("default") or next(iter(value.values()), None)
        return str(picked) if picked not in (None, "") else None
    text = str(value).strip()
    return text or None


def _license_of(node: Any) -> Optional[str]:
    """The licence a `LicenseNode` states — its own field first, then its name.

    Two spellings again, and again both are real: the class keeps
    `data.license_type`, while the graph-scope migration (MIG1-A) writes the
    value as the node's NAME. Reading one of them would work perfectly on
    whichever half of the corpus the author happened to test with.
    """
    return _text(_data(node).get("license_type")) or _text(_field(node, "name"))


def _embargo_of(node: Any) -> Optional[str]:
    """The date an `EmbargoNode` runs until, or None for an open-ended one."""
    return _text(_data(node).get("embargo_end")) or _text(_field(node, "name"))


def _author_of(node: Any) -> Dict[str, Optional[str]]:
    return {"name": _text(_field(node, "name")),
            "orcid": _text(_data(node).get("orcid"))}


def rights_for_digest(document: Any, digest: Any, *,
                      today: Optional[datetime.date] = None
                      ) -> Optional[Dict[str, Any]]:
    """What the graph says about the asset with this digest, or `None`.

    `None` means the graph does not mention it — deliberately distinct from a
    resource that exists and carries no rights, which comes back with every
    field empty. A caller that conflated the two would treat an unknown file the
    same as a file somebody decided to publish.

    The answer:

    ``resource_id`` · which node points at these bytes
    ``license`` / ``license_effective`` / ``license_is_default`` — what was
    said, what a reader may act on, and which of the two this is
    ``embargo`` / ``embargo_active`` — the date, and the verdict TODAY (computed
    at call time and never stored: an embargo that expired this morning is over
    this morning, whatever an index remembers)
    ``authors`` — `[{name, orcid}]`
    ``via`` — ``"resource"`` or ``"dtc"``: where the rights were found, so a
    reader can tell a statement about this file from one inherited from the
    chain that produced it.
    """
    wanted = normalise_digest(digest)
    if not wanted:
        return None

    for section in _sections(document):
        nodes = section.get("nodes") if isinstance(section, dict) else None
        edges = section.get("edges") if isinstance(section, dict) else None
        # tombstones are NOT rights: a removed licence has stopped speaking
        nodes = [n for n in (nodes or []) if _alive(n)]
        edges = [e for e in (edges or []) if _alive(e)]
        by_id = {str(_field(n, "id", "node_id")): n for n in nodes}

        for node in nodes:
            if normalise_digest(_data(node).get("checksum")) != wanted:
                continue
            resource_id = str(_field(node, "id", "node_id"))
            found = _collect(resource_id, by_id, edges)
            via = "resource" if found else None
            if not found:
                # …then through the chain: whatever produced or consumed this
                # resource speaks for it when it says nothing itself
                for neighbour in _chain_neighbours(resource_id, edges):
                    found = _collect(neighbour, by_id, edges)
                    if found:
                        via = "dtc"
                        break
            license_value = found.get("license") if found else None
            embargo_value = found.get("embargo") if found else None
            return {
                "digest": wanted,
                "resource_id": resource_id,
                "license": license_value,
                "license_effective": license_value or DEFAULT_LICENSE,
                "license_is_default": license_value is None,
                "embargo": embargo_value,
                "embargo_active": embargo_active(embargo_value, today=today),
                "authors": (found or {}).get("authors") or [],
                "via": via,
            }
    return None


def _chain_neighbours(node_id: str, edges: List[Any]) -> List[str]:
    """The DTC chunks this resource is attached to, from either end."""
    out: List[str] = []
    for edge in edges:
        kind = _text(_field(edge, "edge_type", "type"))
        if kind not in _CHAIN_EDGES:
            continue
        source = str(_field(edge, "source", "edge_source") or "")
        target = str(_field(edge, "target", "edge_target") or "")
        other = target if source == node_id else (source if target == node_id else None)
        if other and other not in out:
            out.append(other)
    return out


def _collect(node_id: str, by_id: Dict[str, Any],
             edges: List[Any]) -> Dict[str, Any]:
    """The rights hanging off one node. Empty dict when there are none."""
    found: Dict[str, Any] = {}
    authors: List[Dict[str, Optional[str]]] = []
    for edge in edges:
        kind = _text(_field(edge, "edge_type", "type"))
        role = _RIGHTS_EDGES.get(kind or "")
        if not role:
            continue
        source = str(_field(edge, "source", "edge_source") or "")
        target = str(_field(edge, "target", "edge_target") or "")
        # the edge is written resource → statement; the reverse is read too,
        # because a graph written the other way round says the same thing
        other = target if source == node_id else (source if target == node_id else None)
        node = by_id.get(other or "")
        if node is None:
            continue
        if role == "license":
            found.setdefault("license", _license_of(node))
        elif role == "embargo":
            found.setdefault("embargo", _embargo_of(node))
        else:
            entry = _author_of(node)
            if entry.get("name") or entry.get("orcid"):
                if entry not in authors:
                    authors.append(entry)
    if authors:
        found["authors"] = authors
    return {k: v for k, v in found.items() if v not in (None, [], "")}
