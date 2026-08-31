"""The DTC neighbourhood of an asset — the chain is walked, the context is not.

`derivation_chain` (in :mod:`s3dgraphy.dtc.ingest`) answers one hop each way and
says in its own docstring that «a full transitive walk is a different question
(and a different screen)». This is that walk, and the screen is EMStudio's `dtc`
window: select a file in the store, see what made it, what it went on to make,
and through which events.

## The rule, and why it is not a limit on degree

The obvious danger: from a photograph you reach the tool that processed it, and
from the tool **every other photograph that tool ever touched** — half a dig.

A ceiling on a node's DEGREE would have been the wrong answer: degree changes by
itself as the data grows, so the same question would answer differently in March
and in July. A list of node types not to cross would be a policy to maintain by
hand.

**The DTC model already answers it, and the answer is about EDGES.** From
`nodes/dtc_node.py`: the chain is Resources connected by Process events, wired by
``dtc_had_input`` / ``dtc_had_output`` / ``dtc_derived_from``; Author, License,
Embargo and the Resource itself hang off it via ``has_author`` / ``has_license``
/ ``has_embargo`` / ``has_linked_resource``. So:

    only the chain's edges are walked; anything reached by a `has_*` is an
    ATTRIBUTE of the node you are standing on, not a place to continue from.

Which is sturdier than a list, and that is the whole reason to prefer it: a new
kind of context — a site, a campaign, a funding body — is born **non-traversable
by construction**, because it is not one of the three chain edges. No policy to
update, and nothing to forget.

## What this is not

* not a driver and not a network call: semantic-only, like everything here;
* not a place where a `dtc_kind` is written down. The kinds are data
  (`em_visual_rules.json`, via :func:`s3dgraphy.utils.get_dtc_kinds`) and this
  module never names one;
* not a census. It does not count the context neighbours it declined to expand:
  the number was the one expensive part and nobody asked for it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from .ingest import _USAGE_ROLES, _alive, _data, _find
from .residency import EDGE_DERIVED_FROM, EDGE_HAD_INPUT, EDGE_HAD_OUTPUT

#: The edges the chain is MADE of — READ from the connections datamodel, which
#: marks them ``"dtc_role": "chain"``.
#:
#: It used to be a tuple of three imported constants, and the client had a
#: `startsWith("dtc_")` beside it. Two rules with one name: the prefix presumed
#: every future ``dtc_*`` edge would be chain, so a ``dtc_annotated_by`` that was
#: CONTEXT would have been a corridor on one side and not on the other. Now the
#: datamodel says it once and both sides read it — the same discipline the
#: ``dtc_kinds`` vocabulary already follows.
#:
#: The constants stay where they are (`residency.py`) and keep their job: WRITING
#: an edge needs a name. Classifying needs a set, and a set is data.
def _chain_edges() -> tuple:
    """The marked edges, or the historical three when nothing is marked.

    The fallback is deliberate and it is not a second list: a vendored datamodel
    from before the marker (1.6.12 and earlier) would otherwise make this walk
    traverse NOTHING — and a walk that quietly returns one node is worse than a
    walk that answers the way it always did. When the marker exists the marker
    decides; the day it does not, the three names are the correct historical
    answer, and they are already imported for the writing side.
    """
    try:
        from ..edges import get_connections_datamodel

        edge_types = getattr(get_connections_datamodel(), "_canonical_edges", None)
        if isinstance(edge_types, dict):
            marked = tuple(
                name for name, definition in edge_types.items()
                if isinstance(definition, dict)
                and definition.get("dtc_role") == "chain"
            )
            if marked:
                return marked
    except Exception:                              # noqa: BLE001
        pass
    return (EDGE_HAD_INPUT, EDGE_HAD_OUTPUT, EDGE_DERIVED_FROM)


CHAIN_EDGES = _chain_edges()

#: How far the walk may go. A SAFETY NET and not a filter: with the context
#: already excluded the graph stays local by itself, so this only has to stop a
#: pathological chain-of-chains from becoming the whole register. An acquisition
#: → process → output → process → output is four hops; six leaves room for a
#: chain built on a chain and still answers in a blink.
DEFAULT_HOPS = 6


def _card(node: Any) -> Dict[str, Any]:
    """A node as a reader needs it: what it is, what it is called, which kind.

    `dtc_kind` is READ, never validated here — the vocabulary is data and this
    module is not the place that decides what a kind may be.
    """
    return {
        "id": getattr(node, "node_id", None),
        "type": getattr(node, "node_type", None),
        "name": getattr(node, "name", None),
        "dtc_kind": _data(node).get("dtc_kind"),
    }


def _role_of(edge_type: str) -> str:
    """What kind of edge this is, in the classification `ingest` already keeps.

    An edge nobody has classified comes back as ``"context"`` — and that is the
    safe direction: unknown means «hangs off this node», never «walk it».
    """
    if edge_type in CHAIN_EDGES:
        return "chain"
    return _USAGE_ROLES.get(edge_type, "context")


def neighbourhood(graph: Any, start: str, *,
                  hops: int = DEFAULT_HOPS) -> Dict[str, Any]:
    """The DTC neighbourhood of one node — the chain around it, and its context.

    Args:
        graph: any s3Dgraphy graph.
        start: the id of the node to stand on (a Resource, usually; a Process
            works too and is sometimes what a caller has).
        hops: how far to walk along the chain. See :data:`DEFAULT_HOPS`.

    Returns a dict with

    * ``start`` — the id actually found, or ``None`` when it was not;
    * ``nodes`` — one card per node reached, with ``hop`` (its distance from the
      start) and ``context``: the `has_*` neighbours that hang off THAT node;
    * ``edges`` — the chain edges inside the neighbourhood, so a caller can draw
      it without re-deriving the shape;
    * ``hops`` — the ceiling that was in force;
    * ``truncated`` and ``frontier`` — whether the ceiling bit, and which nodes
      were left unexpanded when it did. A walk that stopped and did not say so
      would be a walk whose answer looks complete.

    Read-only. Tombstoned nodes and edges are skipped, the way every reader in
    this package skips them: a removed resource is not part of the story.
    """
    node = _find(graph, str(start))
    if node is None:
        return {"start": None, "hops": int(hops), "nodes": [], "edges": [],
                "truncated": False, "frontier": []}

    ceiling = max(0, int(hops))
    seen: Dict[str, int] = {node.node_id: 0}
    cards: Dict[str, Dict[str, Any]] = {}
    chain: List[Dict[str, Any]] = []
    chain_seen: Set[tuple] = set()
    frontier: List[str] = []
    queue: List[Any] = [node]

    while queue:
        current = queue.pop(0)
        here = current.node_id
        depth = seen[here]
        card = _card(current)
        card["hop"] = depth
        card["context"] = []
        cards[here] = card

        # ONE pass over this node's edges, on top of `get_connected_edges` —
        # which is what the graph already offers. It is a linear scan of the edge
        # list, and the cost is bounded by the frontier staying small, which is
        # exactly what excluding the context buys. (If it ever stops being small,
        # the composite index behind `get_connected_nodes_by_edge_type` is the
        # faster road — and the shape of this loop would not change.)
        edges = graph.get_connected_edges(here)
        for edge in edges:
            if not _alive(edge):
                continue
            etype = str(getattr(edge, "edge_type", "") or "")
            source = getattr(edge, "edge_source", None)
            target = getattr(edge, "edge_target", None)
            other = target if source == here else source
            if other is None:
                continue
            neighbour = _find(graph, str(other))
            if neighbour is None or not _alive(neighbour):
                continue

            if _role_of(etype) != "chain":
                # CONTEXT. It belongs to this node and the walk stops here — an
                # author is a fact about this file, not a corridor to every other
                # file that author ever touched.
                entry = _card(neighbour)
                entry["edge_type"] = etype
                entry["role"] = _role_of(etype)
                card["context"].append(entry)
                continue

            # CHAIN. The edge is part of the story, so it is reported…
            key = (etype, source, target)
            if key not in chain_seen:
                chain_seen.add(key)
                chain.append({"edge_type": etype, "source": source,
                              "target": target})
            # …and the node it leads to is somewhere to continue from, unless the
            # ceiling says otherwise. Said, not silently dropped.
            if other in seen:
                continue
            if depth + 1 > ceiling:
                if other not in frontier:
                    frontier.append(str(other))
                continue
            seen[other] = depth + 1
            queue.append(neighbour)

    return {
        "start": node.node_id,
        "hops": ceiling,
        "nodes": sorted(cards.values(), key=lambda c: (c["hop"], str(c["id"]))),
        "edges": chain,
        "truncated": bool(frontier),
        "frontier": frontier,
    }


def neighbourhood_of_digest(graph: Any, digest: str, *,
                            hops: int = DEFAULT_HOPS) -> Dict[str, Any]:
    """The same, entered by an asset's DIGEST rather than by a node id.

    Which is how a caller who is looking at an object store arrives: what they
    have is a sha256, and the graph knows it as a Resource's `url`/`ref`. Kept
    here rather than in the service so the lookup rule lives with the traversal
    it feeds — one place that knows how an asset is named in a graph.
    """
    wanted = str(digest or "").strip().lower()
    if not wanted:
        return neighbourhood(graph, "", hops=hops)
    for candidate in getattr(graph, "nodes", []) or []:
        if not _alive(candidate):
            continue
        data = _data(candidate)
        for key in ("checksum", "sha256", "digest", "url", "ref", "path"):
            value = str(data.get(key) or "")
            if value and wanted in value.lower():
                return neighbourhood(graph, candidate.node_id, hops=hops)
    return {"start": None, "hops": max(0, int(hops)), "nodes": [], "edges": [],
            "truncated": False, "frontier": []}


__all__ = ["CHAIN_EDGES", "DEFAULT_HOPS", "neighbourhood",
           "neighbourhood_of_digest"]
