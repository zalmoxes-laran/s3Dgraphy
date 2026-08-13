"""The em.json CONTAINER — a project is one file holding one or more graphs.

The decision (E.D., 2026-08-13): **an em.json/emj is always a container**::

    {
      "header": {...},
      "graphs": {
        "<graph id>": { "nodes": [...], "edges": [...] },
        "shelf":      { ... em_collection: "ShelfGraph" }
      },
      "active_graph_id": "<graph id>"
    }

A study is one or more graphs plus its shelf; a single graph is a
**container-of-one**. This is the shape **Heriverse already reads**, so writing
it means Heriverse does not change — the format was not invented here, it was
adopted.

Why it matters beyond tidiness: the project becomes **one portable file**, and
"integrate later" becomes a local operation. You work offline on your own emj,
somebody else works on theirs, and afterwards one container takes in the other's
graphs — nodes shared between them merge **by UUID**, which s3Dgraphy has always
been able to do (`add_node(overwrite=True)`). No server, no session, no lock.

**P3 (2026-08-13) — the merge is now DATED and the conflicts are VISIBLE.**
Two divergent edits of the same node no longer resolve as "whoever arrived
last": the editorial stamps decide (`modified_at`, falling back to
`created_at`), the more recent version wins, and every contested node is
recorded in `MergeReport.conflicts` saying *who overwrote whom, and when*.
Deciding by date rather than by arrival makes the result **independent of the
order you merge in** — A into B and B into A land on the same project, which is
the least a collaboration tool owes you.

What this module deliberately does NOT do:

* **field-level fusion.** The unit of resolution is the NODE: if you changed a
  description and somebody else changed a date, the newer node wins whole and
  the other edit is in the conflict list, not merged in. Keeping both needs a
  common ancestor (three-way) or a version vector, which is P4 — and guessing
  at it here would produce nodes neither of you wrote.
* **real-time co-editing** of the same graph — that is the em-server hub
  (ADR-002 grows from selection-sync to operation-sync). P4.
* **manual conflict resolution UI**: this module produces the record; deciding
  what to do about it belongs upstream, where a person is.

Reading accepts BOTH shapes, always: the legacy single-graph document (which is
every file written before today) opens as a container-of-one, and nothing on
anybody's disk breaks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .graph import Graph

#: The key that makes a document a container.
GRAPHS_KEY = "graphs"

#: The conventional member id of the project shelf. Any id works — the marker
#: (`graph.data["em_collection"] == "ShelfGraph"`) is what identifies it — but
#: this is the one Heriverse uses, so writing it keeps the two aligned.
SHELF_MEMBER_ID = "shelf"


@dataclass
class Container:
    """One project: its graphs, its shelf, and which graph was in front.

    The shelf is kept OUT of `graphs` in memory and written back INTO it on
    save. Two reasons: a caller iterating the study's graphs should not have to
    remember to skip the shelf every time (the bug that would cause is a shelf
    rendered as a stratigraphic matrix), and "is there a shelf?" should be a
    field, not a search.
    """

    graphs: Dict[str, Graph] = field(default_factory=dict)
    shelf: Optional[Graph] = None
    active_graph_id: Optional[str] = None
    header: Dict[str, Any] = field(default_factory=dict)
    layout: Dict[str, Any] = field(default_factory=dict)

    def graph_ids(self) -> List[str]:
        return list(self.graphs.keys())

    def active(self) -> Optional[Graph]:
        if self.active_graph_id and self.active_graph_id in self.graphs:
            return self.graphs[self.active_graph_id]
        return next(iter(self.graphs.values()), None)

    def is_single(self) -> bool:
        """A container-of-one — the shape a legacy file opens as."""
        return len(self.graphs) == 1


def is_container(doc: Any) -> bool:
    """True when the document carries the `graphs` map.

    Structural, not heuristic: either the key is there with a dict in it, or the
    document is a legacy single-graph one. Nothing is guessed from content.
    """
    return isinstance(doc, dict) and isinstance(doc.get(GRAPHS_KEY), dict)


def is_shelf_member(graph_section: Any) -> bool:
    """Is this member the shelf? Read from the marker, never from the member id
    — an id is a name somebody chose, the marker is what the graph says it is."""
    data = (graph_section or {}).get("data") if isinstance(graph_section, dict) else None
    if isinstance(data, dict) and data.get("em_collection") == "ShelfGraph":
        return True
    # a Graph object rather than a section
    data = getattr(graph_section, "data", None)
    return isinstance(data, dict) and data.get("em_collection") == "ShelfGraph"


def parse_container(doc: Dict[str, Any]) -> Tuple[Container, List[str]]:
    """Read a container OR a legacy single-graph document.

    Returns ``(container, warnings)``. A legacy document becomes a
    container-of-one — the same object, so every caller downstream has one shape
    to handle instead of two.
    """
    from .importer.emjson_importer import EmJsonImportError, parse_emjson

    warnings: List[str] = []
    if not isinstance(doc, dict):
        raise EmJsonImportError("not an em.json document")

    header = dict(doc.get("header") or {})
    layout = dict(doc.get("layout") or {})

    if not is_container(doc):
        # LEGACY single-graph: read it with the reader that has always read it,
        # then wrap. No second parser, no drift between the two paths.
        graph, graph_warnings = parse_emjson(doc)
        container = Container(
            graphs={graph.graph_id: graph},
            active_graph_id=graph.graph_id,
            header=header,
            layout=layout,
        )
        return container, list(graph_warnings)

    container = Container(header=header, layout=layout)
    members = doc[GRAPHS_KEY]
    for member_id, section in members.items():
        if not isinstance(section, dict):
            warnings.append(f"container member '{member_id}' is not a graph; skipped")
            continue
        # Each member is parsed by the SAME single-graph reader, by handing it a
        # one-graph document. The alternative — a second parser for members —
        # would be a second place for the em.json semantics to live.
        member_doc = {
            "header": header or {"format": "em.json", "version": "1.0"},
            "graph": {**section, "graph_id": section.get("graph_id") or member_id},
        }
        try:
            graph, member_warnings = parse_emjson(member_doc)
        except Exception as exc:
            # One unreadable member must not lose the rest of the project.
            warnings.append(f"container member '{member_id}' not readable: {exc}")
            continue
        warnings.extend(member_warnings)
        if is_shelf_member(section):
            container.shelf = graph
        else:
            container.graphs[graph.graph_id] = graph

    active = doc.get("active_graph_id")
    if isinstance(active, str) and active in container.graphs:
        container.active_graph_id = active
    else:
        if isinstance(active, str) and active:
            warnings.append(
                f"active_graph_id '{active}' is not a member of this container; "
                f"falling back to the first graph")
        container.active_graph_id = next(iter(container.graphs), None)

    if not container.graphs and container.shelf is not None:
        warnings.append(
            "this container holds a shelf and no study graph — readable, but "
            "there is nothing to draw")
    return container, warnings


def _member_section(graph: Graph) -> Dict[str, Any]:
    """A graph as a container member: the `graph` section of the single-graph
    document, reusing the one builder there is."""
    from .exporter.emjson_exporter import build_emjson
    return build_emjson(graph)["graph"]


def build_container(container: Container) -> Dict[str, Any]:
    """Serialise a container. Always the `graphs` shape, even for one graph.

    The shelf goes back into `graphs` under its conventional id — that is where
    Heriverse looks for it, and keeping it elsewhere would make the file we write
    a dialect of the format we adopted.
    """
    from .exporter.emjson_exporter import build_emjson

    graphs: Dict[str, Any] = {}
    for graph_id, graph in container.graphs.items():
        graphs[graph_id] = _member_section(graph)
    if container.shelf is not None:
        shelf_id = container.shelf.graph_id or SHELF_MEMBER_ID
        graphs[shelf_id] = _member_section(container.shelf)

    # The header comes from the single-graph builder, so the format/version/
    # datamodel stamps are written in exactly ONE place.
    any_graph = container.active() or container.shelf or Graph(graph_id="empty")
    header = build_emjson(any_graph)["header"]
    doc: Dict[str, Any] = {"header": header, GRAPHS_KEY: graphs}
    active = container.active_graph_id or next(iter(container.graphs), None)
    if active:
        doc["active_graph_id"] = active
    if container.layout:
        doc["layout"] = container.layout
    return doc


def load_container_file(path: str) -> Tuple[Container, List[str]]:
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    return parse_container(doc)


def save_container_file(container: Container, path: str) -> str:
    doc = build_container(container)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return str(target)


def container_of(graph: Graph, *, shelf: Optional[Graph] = None) -> Container:
    """Wrap one graph as a container-of-one — the everyday case."""
    return Container(graphs={graph.graph_id: graph},
                     shelf=shelf,
                     active_graph_id=graph.graph_id)


# ── integrate later ─────────────────────────────────────────────────────────

# ── P3 · the dated merge and its record ──────────────────────────────────────

#: Which reason decided a contested node.
#:
#: ``newer``      — the stamps differ and the more recent version won.
#: ``tie``        — the two stamps are the same instant; a stable tie-break
#:                  decided (see `_pick_winner`), and the flag says so.
#: ``unstamped``  — at least one side carries no editorial stamp, so the DATE
#:                  DID NOT DECIDE. The incoming version is kept (the previous
#:                  behaviour), and this reason exists so nobody reads that as a
#:                  judgement: an absent stamp is unknown, not older.
CONFLICT_REASONS = ("newer", "tie", "unstamped")


@dataclass
class Conflict:
    """One node two people edited — with who won, who lost, and why.

    The whole point of P3. `merged_nodes` could already tell you *how many*
    nodes were touched twice; this says WHICH, and names the two hands, so the
    sentence a person reads is "B (11:30) overwrote A (10:00) on node X" instead
    of "3 nodes merged".
    """

    node_id: str
    reason: str
    winner: Dict[str, Any] = field(default_factory=dict)   # {"by":…, "at":…, "side":…}
    loser: Dict[str, Any] = field(default_factory=dict)
    #: which fields actually diverged (`name`, `description`, `data.value`, …) —
    #: not a diff, a pointer to where to look
    field_hint: List[str] = field(default_factory=list)
    #: the losing version, verbatim, so upstream can offer "keep A's version"
    #: without having to have kept the other file open
    loser_payload: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "node_id": self.node_id,
            "reason": self.reason,
            "winner": dict(self.winner),
            "loser": dict(self.loser),
        }
        if self.field_hint:
            out["field_hint"] = list(self.field_hint)
        if self.loser_payload is not None:
            out["loser_payload"] = self.loser_payload
        return out


@dataclass
class MergeReport:
    """What a merge did, in the terms somebody would want to check.

    Not a boolean: after taking in a colleague's file you want to know which
    graphs arrived, which were already yours, and how many nodes were the SAME
    node seen twice. A merge that only says "ok" is a merge you cannot audit.

    P3 · `merged_nodes` stays the COUNT of same-UUID encounters; `conflicts` is
    the list of the ones where the two versions actually diverged.
    """

    added_graphs: List[str] = field(default_factory=list)
    merged_graphs: List[str] = field(default_factory=list)
    merged_nodes: int = 0
    added_nodes: int = 0
    added_edges: int = 0
    shelf_added: int = 0
    shelf_merged: int = 0
    conflicts: List[Conflict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "added_graphs": list(self.added_graphs),
            "merged_graphs": list(self.merged_graphs),
            "merged_nodes": self.merged_nodes,
            "added_nodes": self.added_nodes,
            "added_edges": self.added_edges,
            "shelf_added": self.shelf_added,
            "shelf_merged": self.shelf_merged,
            "conflicts": [c.as_dict() for c in self.conflicts],
            "warnings": list(self.warnings),
        }


def _node_snapshot(node: Any) -> Dict[str, Any]:
    """The node as the em.json exporter writes it — one serializer, not two."""
    from .exporter.emjson_exporter import _node_payload
    return _node_payload(node)


def _content_of(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """The snapshot WITHOUT the editorial stamps.

    Two versions that differ only in when they were saved are not a conflict:
    nobody's work is at stake, and reporting one would train people to ignore
    the list. So divergence is judged on content, and the stamps are only how
    the winner is chosen.
    """
    from .editorial import FIELDS as EDITORIAL_FIELDS

    out = {k: v for k, v in snapshot.items() if k != "data"}
    data = snapshot.get("data")
    if isinstance(data, dict):
        stripped = {k: v for k, v in data.items() if k not in EDITORIAL_FIELDS}
        if stripped:
            out["data"] = stripped
    return out


def _diverging_fields(a: Dict[str, Any], b: Dict[str, Any]) -> List[str]:
    """Where the two versions differ, named for a human ("data.value")."""
    hints: List[str] = []
    for key in sorted(set(a) | set(b)):
        if key == "data":
            continue
        if a.get(key) != b.get(key):
            hints.append(key)
    da = a.get("data") if isinstance(a.get("data"), dict) else {}
    db = b.get("data") if isinstance(b.get("data"), dict) else {}
    for key in sorted(set(da) | set(db)):
        if da.get(key) != db.get(key):
            hints.append(f"data.{key}")
    return hints


def _stamp_of(node: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """``(instant, by, which)`` — the editorial stamp that dates a node.

    `modified_at` when there is one, else `created_at`: the last hand is what a
    merge is comparing, and a node nobody has edited since creation is dated by
    its creation. `which` says which of the two answered, because a report that
    compares a modification against a creation should be able to say so.
    """
    data = getattr(node, "data", None)
    if not isinstance(data, dict):
        return None, None, None
    if data.get("modified_at"):
        return str(data["modified_at"]), data.get("modified_by"), "modified_at"
    if data.get("created_at"):
        return str(data["created_at"]), data.get("created_by"), "created_at"
    return None, None, None


def _instant(text: Optional[str]):
    """An ISO-8601 stamp as a comparable, timezone-aware datetime, or None.

    Naive stamps are read as UTC rather than refused: they are the ordinary
    output of a tool that did not think about zones, and treating them as
    unstamped would throw away real ordering information.
    """
    if not text:
        return None
    from datetime import datetime, timezone
    try:
        parsed = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _pick_winner(mine: Any, theirs: Any) -> Tuple[str, str]:
    """Which version of a contested node survives, and why.

    Returns ``(side, reason)`` where side is ``"mine"`` or ``"theirs"``.

    By DATE, not by arrival — that is what makes the outcome the same whichever
    file you open first. When the two instants are identical the date cannot
    decide, so a stable tie-break does: the smaller editor iD wins, and failing
    that the smaller serialisation. It is arbitrary, and it is *declared*
    arbitrary by `reason="tie"` — what it must not be is random, or dependent on
    merge order, because then two people merging the same two files would end up
    with different projects and no way to tell.
    """
    mine_at, mine_by, _ = _stamp_of(mine)
    theirs_at, theirs_by, _ = _stamp_of(theirs)
    a, b = _instant(mine_at), _instant(theirs_at)
    if a is None or b is None:
        # the date did not decide: keep the historical behaviour (incoming wins)
        # and say that it was not a judgement
        return "theirs", "unstamped"
    if a > b:
        return "mine", "newer"
    if b > a:
        return "theirs", "newer"
    key_mine = str(mine_by or "")
    key_theirs = str(theirs_by or "")
    if key_mine != key_theirs:
        return ("mine", "tie") if key_mine < key_theirs else ("theirs", "tie")
    dump_mine = json.dumps(_node_snapshot(mine), sort_keys=True, ensure_ascii=False)
    dump_theirs = json.dumps(_node_snapshot(theirs), sort_keys=True, ensure_ascii=False)
    return ("mine", "tie") if dump_mine <= dump_theirs else ("theirs", "tie")


def _merge_graph_into(target: Graph, incoming: Graph, report: MergeReport) -> None:
    """Fold `incoming` into `target`, keyed by UUID, resolving by DATE.

    A node id IS the identity — that is what the UUID ids were for (offline
    merges were the stated reason in ADR-002). So a node already present is the
    same node; a node absent is added.

    P3 · when the same node exists on both sides with DIFFERENT content, the
    editorial stamps decide (`_pick_winner`) and the loser is recorded in
    `report.conflicts`. The winner keeps ITS OWN stamps — it is never re-stamped
    with the session running the merge, which is the same rule the audit applies
    to `applyRemoteOp`: somebody else's edit stays somebody else's edit.

    Edges are added when their (source, type, target) triple is not already
    there, which is the only definition of "the same edge" that survives two
    people minting edge ids independently.
    """
    existing_nodes = {n.node_id for n in target.nodes}
    for node in list(incoming.nodes):
        if node.node_id in existing_nodes:
            report.merged_nodes += 1
            mine = target.find_node_by_id(node.node_id)
            snap_mine = _node_snapshot(mine) if mine is not None else {}
            snap_theirs = _node_snapshot(node)
            if _content_of(snap_mine) == _content_of(snap_theirs):
                # the same node, said the same way. Keep the more recent stamps
                # so the project records the latest hand, and report nothing:
                # no work is at stake, and a conflict list that cries wolf is a
                # conflict list nobody reads.
                side, _ = _pick_winner(mine, node)
                if side == "theirs":
                    target.add_node(node, overwrite=True)
                continue
            side, reason = _pick_winner(mine, node)
            winner, loser = (mine, node) if side == "mine" else (node, mine)
            if side == "theirs":
                target.add_node(node, overwrite=True)
            w_at, w_by, w_which = _stamp_of(winner)
            l_at, l_by, l_which = _stamp_of(loser)
            report.conflicts.append(Conflict(
                node_id=node.node_id,
                reason=reason,
                winner={"by": w_by, "at": w_at, "stamp": w_which,
                        "side": "mine" if side == "mine" else "theirs"},
                loser={"by": l_by, "at": l_at, "stamp": l_which,
                       "side": "theirs" if side == "mine" else "mine"},
                field_hint=_diverging_fields(_content_of(snap_mine),
                                             _content_of(snap_theirs)),
                loser_payload=(snap_theirs if side == "mine" else snap_mine),
            ))
        else:
            target.add_node(node)
            existing_nodes.add(node.node_id)
            report.added_nodes += 1

    existing_edges = {
        (e.edge_source, e.edge_type, e.edge_target) for e in target.edges
    }
    existing_edge_ids = {getattr(e, "edge_id", None) for e in target.edges}
    for edge in list(incoming.edges):
        key = (edge.edge_source, edge.edge_type, edge.edge_target)
        if key in existing_edges:
            continue
        edge_id = getattr(edge, "edge_id", None)
        # two independent authors can mint the same edge id for different edges;
        # keep the relation and give it a free id rather than dropping it
        while edge_id in existing_edge_ids:
            edge_id = f"{edge_id}_merged"
        try:
            target.add_edge(edge_id, edge.edge_source, edge.edge_target, edge.edge_type)
        except ValueError as exc:
            report.warnings.append(f"edge {key} not merged: {exc}")
            continue
        existing_edges.add(key)
        existing_edge_ids.add(edge_id)
        report.added_edges += 1


def merge_into_container(container: Container, other: Container) -> MergeReport:
    """Take in another project's graphs — the offline "integrate later".

    ADDITIVE by design: a graph you do not have is added whole; a graph you both
    have is merged by UUID. The shelf merges into the project shelf the same way,
    so two people who collected the same photograph end up with one entry.

    P3 · contested nodes are resolved by DATE (the more recent editorial stamp
    wins) and every one of them is listed in `report.conflicts` with who
    overwrote whom. Declared limit: the unit is the NODE, not the field — two
    people who edited different parts of the same node do not get both edits,
    they get the newer node and a conflict entry naming the other. Field-level
    fusion needs a common ancestor and is P4.
    """
    report = MergeReport()
    for graph_id, incoming in other.graphs.items():
        if graph_id in container.graphs:
            _merge_graph_into(container.graphs[graph_id], incoming, report)
            report.merged_graphs.append(graph_id)
        else:
            container.graphs[graph_id] = incoming
            report.added_graphs.append(graph_id)
            report.added_nodes += len(list(incoming.nodes))
            report.added_edges += len(list(incoming.edges))

    if other.shelf is not None:
        if container.shelf is None:
            container.shelf = other.shelf
            report.shelf_added = len(list(other.shelf.nodes))
        else:
            before = len(list(container.shelf.nodes))
            shelf_report = MergeReport()
            _merge_graph_into(container.shelf, other.shelf, shelf_report)
            report.shelf_added = len(list(container.shelf.nodes)) - before
            report.shelf_merged = shelf_report.merged_nodes
            # a shelf entry two people described differently is contested like
            # any other node — the list is one list, or half the conflicts are
            # invisible for no reason a user could guess
            report.conflicts.extend(shelf_report.conflicts)
            report.warnings.extend(shelf_report.warnings)

    if container.active_graph_id not in container.graphs:
        container.active_graph_id = next(iter(container.graphs), None)
    return report
