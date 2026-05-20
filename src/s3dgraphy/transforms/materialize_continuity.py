"""Export-time inverse of the importer's continuity-diamond expansion.

The GraphML importer (``import_graphml.py:1601+``) reads a continuity
diamond (BR) and derives ``has_first_epoch`` + ``survive_in_epoch``
edges on the strat node it terminates. The Blender side then works
with the edge chain and never carries the diamond in memory: a node
lives in Epoch_N (``has_first_epoch``) and survives into Epoch_M
(``survive_in_epoch``), and that is all the in-memory graph knows.

When exporting back to GraphML, we have to RE-CREATE the diamond,
otherwise the round-trip semantics break — the importer would assume
default life rules and the user's life-bound configuration would be
lost on the next load.

Family-aware rules (single source of truth:
:mod:`s3dgraphy.classification`):

* **REAL** strat types (``REAL_US_TYPES``) live forever by default.
  When no terminator is present the importer adds
  ``survive_in_epoch`` for every epoch more recent than the birth
  epoch. We must emit a diamond iff the actual ``last_epoch`` is NOT
  the most recent epoch in the graph (the node has a bounded life).

* **VIRTUAL** strat types (``VIRTUAL_US_TYPES``) live ONLY in their
  birth epoch by default. Without a terminator the importer adds no
  ``survive_in_epoch``. We must emit a diamond iff the in-memory
  graph has at least one ``survive_in_epoch`` edge on the node — its
  life has been extended beyond birth, which only a diamond can
  express in GraphML.

Placement: the synthetic diamond is wired to ``last_epoch`` via a
synthetic ``has_first_epoch`` edge. That's how the exporter's
position calculator (:class:`EpochSwimlanesGenerator`) decides which
swimlane row a node falls into. At re-import, the diamond's y_pos
sits inside ``last_epoch``'s vertical range and the importer's gate
``epoch.max_y > continuity_y_pos`` correctly bounds
``survive_in_epoch`` to the right span.

All injected content is tagged ``injected_by="materialize_continuity"``
so :func:`s3dgraphy.transforms.aux_tracking.revert_injector` (re-exposed
here as :func:`dematerialize_continuity`) can drop it at the end of
the export, leaving the in-memory graph identical to its pre-export
state.

Idempotent: a strat node that already has an incoming edge from a BR
(user-authored diamond in the graph) is skipped — we never duplicate
an existing terminator.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Set

from ..classification import REAL_US_TYPES, VIRTUAL_US_TYPES
from ..edges.edge import Edge
from ..nodes.epoch_node import EpochNode
from ..nodes.stratigraphic_node import ContinuityNode, StratigraphicNode
from .aux_tracking import mark_as_injected, revert_injector


INJECTOR_ID = "materialize_continuity"


def _epoch_start_time(epoch: EpochNode) -> float:
    """Same convention used by :class:`EpochSwimlanesGenerator`:
    epochs with a higher ``start_time`` are MORE RECENT.
    Missing values map to 0.0 (treated as oldest).
    """
    st = getattr(epoch, "start_time", None)
    return st if st is not None else 0.0


def materialize_continuity(graph) -> Dict[str, int]:
    """Inject synthetic ContinuityNode diamonds + edges so a re-import
    of the exported GraphML reproduces the in-memory life chain.

    Self-healing: any leftover synthetic content from a previous
    failed run (tagged ``injected_by=INJECTOR_ID``) is swept first.

    Idempotent vs user-authored continuity: strat nodes that already
    have an incoming edge from a BR are left untouched.

    Returns ``{"nodes", "edges", "skipped_user_authored", "swept"}``.
    """
    # Reset state — drop any synthetic content left behind by a
    # previous run that didn't reach the cleanup step.
    swept_report = revert_injector(graph, INJECTOR_ID)
    swept = swept_report.get("nodes", 0) + swept_report.get("edges", 0)

    epoch_nodes = [n for n in graph.nodes if isinstance(n, EpochNode)]
    if not epoch_nodes:
        return {"nodes": 0, "edges": 0,
                "skipped_user_authored": 0, "swept": swept}

    sorted_epochs = sorted(epoch_nodes, key=_epoch_start_time, reverse=True)
    latest_epoch_id = sorted_epochs[0].node_id  # highest start_time
    epoch_id_to_obj = {e.node_id: e for e in epoch_nodes}

    # Single pass over edges to gather, per strat node:
    #   - first_epoch (via has_first_epoch outgoing edge)
    #   - the set of surviving epoch ids (has_first_epoch ∪ survive_in_epoch)
    #   - whether the node already has an incoming edge from a BR
    first_epoch_of: Dict[str, EpochNode] = {}
    survives_in: Dict[str, Set[str]] = {}
    has_user_br: Set[str] = set()

    for edge in graph.edges:
        if edge.edge_type == "has_first_epoch":
            tgt_epoch = epoch_id_to_obj.get(edge.edge_target)
            if tgt_epoch is not None:
                first_epoch_of[edge.edge_source] = tgt_epoch
                survives_in.setdefault(
                    edge.edge_source, set()).add(edge.edge_target)
        elif edge.edge_type == "survive_in_epoch":
            if edge.edge_target in epoch_id_to_obj:
                survives_in.setdefault(
                    edge.edge_source, set()).add(edge.edge_target)
        else:
            # Any edge whose source is a BR terminates the target node's
            # life. The edge type is unconstrained — the importer only
            # checks source.node_type == "BR" at
            # ``import_graphml.py:1632``.
            src = graph.find_node_by_id(edge.edge_source)
            if src is not None and getattr(src, "node_type", "") == "BR":
                has_user_br.add(edge.edge_target)

    nodes_added = 0
    edges_added = 0
    skipped = 0

    # Snapshot the node list — we mutate ``graph.nodes`` inside the loop.
    for node in list(graph.nodes):
        if not isinstance(node, StratigraphicNode):
            continue
        ntype = getattr(node, "node_type", None)
        if ntype in (None, "BR", "SE"):
            # BR / SE are not life-bearing strat units; skip.
            continue

        first_epoch = first_epoch_of.get(node.node_id)
        if first_epoch is None:
            # No birth epoch on this node → no life to terminate.
            continue

        if node.node_id in has_user_br:
            # User already wired a continuity diamond — don't double up.
            skipped += 1
            continue

        survival_ids = survives_in.get(node.node_id, set())
        survival_epochs = [
            epoch_id_to_obj[eid]
            for eid in survival_ids
            if eid in epoch_id_to_obj
        ]
        if not survival_epochs:
            # has_first_epoch pointed at an unknown epoch id.
            continue

        last_epoch = max(survival_epochs, key=_epoch_start_time)

        # Family-aware decision: when does the round-trip NEED a
        # diamond to reproduce this exact life chain?
        if ntype in REAL_US_TYPES:
            # Default "lives forever". Diamond needed iff bounded.
            need_br = last_epoch.node_id != latest_epoch_id
        elif ntype in VIRTUAL_US_TYPES:
            # Default "lives only at birth". Diamond needed iff the
            # graph carries any survival edge on this node — i.e. the
            # life extends beyond first_epoch.
            survives_beyond_birth = survival_ids - {first_epoch.node_id}
            need_br = bool(survives_beyond_birth)
        else:
            # Unknown family (helper / not classified). Be
            # conservative: do not synthesize.
            need_br = False

        if not need_br:
            continue

        # Synthesize the diamond. The y_pos is set by the exporter's
        # epoch position calculator from the BR's has_first_epoch
        # target (last_epoch).
        br_id = str(uuid.uuid4())
        node_label = getattr(node, "name", None) or node.node_id
        br = ContinuityNode(
            node_id=br_id,
            name=f"_synth_BR_{node_label}",
            description="",
        )
        br.attributes["original_id"] = br_id
        br.attributes["graph_id"] = getattr(graph, "graph_id", "")
        mark_as_injected(br, INJECTOR_ID)
        graph.add_node(br)
        nodes_added += 1

        # has_first_epoch → last_epoch so the position calculator
        # drops the BR inside the correct swimlane row.
        hf_edge_id = f"{br_id}__has_first_epoch__{last_epoch.node_id}"
        try:
            hf_edge = graph.add_edge(
                hf_edge_id, br_id, last_epoch.node_id, "has_first_epoch")
        except ValueError:
            # Should not happen: BR is a StratigraphicNode subclass
            # and has_first_epoch accepts that as source.
            continue
        mark_as_injected(hf_edge, INJECTOR_ID)
        edges_added += 1

        # Terminator: BR → N. Direction matches the GraphML
        # convention (source = more recent = the BR, target = more
        # ancient = the strat node being terminated). ``is_after`` is
        # the canonical StratigraphicNode → StratigraphicNode edge.
        term_edge_id = f"{br_id}__is_after__{node.node_id}"
        try:
            term_edge = graph.add_edge(
                term_edge_id, br_id, node.node_id, "is_after")
        except ValueError:
            # Defensive: still safer to leave the orphan BR than to
            # crash the export. revert_injector will remove it at
            # cleanup time.
            continue
        mark_as_injected(term_edge, INJECTOR_ID)
        edges_added += 1

    return {
        "nodes": nodes_added,
        "edges": edges_added,
        "skipped_user_authored": skipped,
        "swept": swept,
    }


def dematerialize_continuity(graph) -> Dict[str, int]:
    """Remove every node and edge tagged
    ``injected_by="materialize_continuity"``, plus any dangling
    edges that would result.

    Thin pinned wrapper over
    :func:`s3dgraphy.transforms.aux_tracking.revert_injector` so
    callers don't have to remember the injector id.

    Returns ``{"nodes", "edges"}``.
    """
    report = revert_injector(graph, INJECTOR_ID)
    return {
        "nodes": report.get("nodes", 0),
        "edges": report.get("edges", 0),
    }
