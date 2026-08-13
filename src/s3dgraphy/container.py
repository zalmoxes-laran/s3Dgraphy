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

What this module deliberately does NOT do:

* **conflict resolution.** Merging is ADDITIVE: a graph that is not there is
  added, and a node that is there already is overwritten by the incoming one.
  Two divergent edits of the same node are a real problem with a real answer
  (three-way merge, or a CRDT), and pretending to solve it with "last writer
  wins" would silently destroy somebody's work. Phase 2, declared.
* **real-time co-editing** of the same graph — that is the em-server hub
  (ADR-002 grows from selection-sync to operation-sync). Phase 4.

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

@dataclass
class MergeReport:
    """What a merge did, in the terms somebody would want to check.

    Not a boolean: after taking in a colleague's file you want to know which
    graphs arrived, which were already yours, and how many nodes were the SAME
    node seen twice. A merge that only says "ok" is a merge you cannot audit.
    """

    added_graphs: List[str] = field(default_factory=list)
    merged_graphs: List[str] = field(default_factory=list)
    merged_nodes: int = 0
    added_nodes: int = 0
    added_edges: int = 0
    shelf_added: int = 0
    shelf_merged: int = 0
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
            "warnings": list(self.warnings),
        }


def _merge_graph_into(target: Graph, incoming: Graph, report: MergeReport) -> None:
    """Fold `incoming` into `target`, keyed by UUID.

    A node id IS the identity — that is what the UUID ids were for (offline
    merges were the stated reason in ADR-002). So a node already present is the
    same node, and it is overwritten by the incoming one; a node absent is added.
    Edges are added when their (source, type, target) triple is not already
    there, which is the only definition of "the same edge" that survives two
    people minting edge ids independently.
    """
    existing_nodes = {n.node_id for n in target.nodes}
    for node in list(incoming.nodes):
        if node.node_id in existing_nodes:
            target.add_node(node, overwrite=True)
            report.merged_nodes += 1
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

    Declared limit: this is `add` + `merge-by-UUID`, NOT conflict resolution. If
    both of you edited the same node, the incoming version wins and yours is
    gone — which is why the report says how many nodes were merged: that number
    is exactly the set of nodes where a conflict COULD have happened, and it is
    the number a person should look at before trusting the result.
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
            report.warnings.extend(shelf_report.warnings)

    if container.active_graph_id not in container.graphs:
        container.active_graph_id = next(iter(container.graphs), None)
    return report
