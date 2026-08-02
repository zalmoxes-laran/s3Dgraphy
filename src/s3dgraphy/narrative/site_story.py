"""The `site_story` template — the first one, derived from PortaMarina.

Structure (narrative-vision-spec §3):

    1. Presentazione        canonical   project prose + every source
    2. Dove si trova        canonical   the geographic placement
    3. one chapter per epoch            the units of that lane, each with
                                        "how I know it" beside it
    4. Il cantiere                      the activities: what was DONE, and the
                                        units it was done to

The chapters that carry the argument are 3 and 4. A chapter is a lane; inside
it, each unit sits next to its evidence chain — the paradata **in** the story,
not in an appendix. Reading the chapters in order is reading the site through
time, which is what makes multitemporal stratigraphy legible to someone who is
not holding the matrix in their head.

The template writes **no content**. Where prose belongs it leaves a bracketed
placeholder, because a sentence invented here would enter the record under the
author's name.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..nodes.narrative_node import NarrativeNode
from .registry import register_template

#: Placeholder prose. Bracketed so it is unmistakable on the page and greppable
#: in the file — an author must be able to find everything still unwritten.
PLACEHOLDER = "[da scrivere: {what}]"

#: The lane chapter shows a unit through its `us` view; where the unit has a
#: property justified by an evidence chain, a `paradata` embed goes beside it.
_EVIDENCE_EDGE = "has_data_provenance"
_PROPERTY_EDGE = "has_property"

#: What counts as "a source" in the presentation chapter. DocumentNode covers
#: its subclasses too, which is the point of matching on the class.
from ..nodes.document_node import DocumentNode as _SourceClass
from ..nodes.epoch_node import EpochNode as _EpochClass
from ..nodes.geo_position_node import GeoPositionNode as _GeoClass
from ..nodes.group_node import ActivityNodeGroup as _ActivityClass
from ..nodes.project_node import ProjectNode as _ProjectClass

#: Units belong to a lane through these edges (first-epoch attribution, and
#: survival into later epochs).
_EPOCH_EDGES = ("has_first_epoch", "survive_in_epoch")


def _nodes(graph, node_class) -> List[Any]:
    """Nodes of a class, not of a node_type STRING.

    The two are not interchangeable and the difference bites: `EpochNode` has
    node_type `"EpochNode"` while `DocumentNode` has `"document"`. Matching on
    the class also picks up subclasses, which is what "every source" or "every
    unit" means.
    """
    return [n for n in graph.nodes if isinstance(n, node_class)]


def _out(graph, node_id: str, edge_type: str) -> List[str]:
    return [e.edge_target for e in graph.edges
            if e.edge_source == node_id and e.edge_type == edge_type]


def _in(graph, node_id: str, edge_type: str) -> List[str]:
    return [e.edge_source for e in graph.edges
            if e.edge_target == node_id and e.edge_type == edge_type]


def _units_of_epoch(graph, epoch_id: str) -> List[Any]:
    """The stratigraphic units attributed to a lane, ordered by stratigraphy.

    `is_after` is the sequence: a unit that is after another comes later in the
    deposit, so the chapter reads oldest-first — the order in which the site was
    built, which is the order a story wants.
    """
    ids = set()
    for edge_type in _EPOCH_EDGES:
        ids.update(_in(graph, epoch_id, edge_type))
    units = [n for n in graph.nodes if n.node_id in ids and _is_stratigraphic(n)]
    return _topological_by_is_after(graph, units)


def _is_stratigraphic(node) -> bool:
    from ..nodes.stratigraphic_node import StratigraphicNode
    return isinstance(node, StratigraphicNode)


def _topological_by_is_after(graph, units: List[Any]) -> List[Any]:
    """Order units so that `A is_after B` puts B first — oldest at the top.

    A plain depth-first walk over `is_after`, tolerant of the cycles a real
    graph sometimes has: a unit already being visited is simply not recursed
    into, so a cyclic dataset still produces an order instead of an exception.
    Ties keep the graph's own order, which makes the output reproducible.
    """
    index = {u.node_id: u for u in units}
    ordered: List[Any] = []
    seen: set = set()
    visiting: set = set()

    def visit(uid: str) -> None:
        if uid in seen or uid in visiting:
            return
        visiting.add(uid)
        for older in _out(graph, uid, "is_after"):
            if older in index:
                visit(older)
        visiting.discard(uid)
        seen.add(uid)
        ordered.append(index[uid])

    for unit in units:
        visit(unit.node_id)
    return ordered


def _evidence_for(graph, unit_id: str) -> List[str]:
    """The property nodes of a unit that are backed by an evidence chain.

    Only those: a property nobody justified has no "how I know it" to show, and
    an embed pointing at nothing would be furniture.
    """
    out = []
    for prop_id in _out(graph, unit_id, _PROPERTY_EDGE):
        if _out(graph, prop_id, _EVIDENCE_EDGE):
            out.append(prop_id)
    return out


def _epoch_sort_key(epoch) -> tuple:
    """Chronological: oldest chapter first. An epoch with no start time sorts
    last rather than crashing the sort — a graph mid-authoring is normal."""
    start = getattr(epoch, "start_time", None)
    return (0, float(start)) if isinstance(start, (int, float)) \
        else (1, 0.0)


@register_template("site_story")
def build_site_story(graph, *, node_id: str = None, title: str = None,
                     lang: Optional[str] = None, **opts) -> NarrativeNode:
    """Lay out the story of a site as chapters over its lanes.

    Returns a fresh draft. To regenerate over an existing narrative without
    losing the author's work, go through
    :func:`~s3dgraphy.narrative.registry.build_narrative` with ``existing=``.
    """
    graph_name = _text(getattr(graph, "name", None)) or graph.graph_id
    narrative = NarrativeNode(
        node_id=node_id or f"narrative_{graph.graph_id}",
        name=title or f"{graph_name} — la storia del sito",
        description="Bozza generata dal template site_story; la prosa è da scrivere.",
        lang=lang,
        template_id="site_story",
    )

    _presentation_chapter(graph, narrative, graph_name)
    _geo_chapter(graph, narrative)
    _epoch_chapters(graph, narrative)
    _activity_chapter(graph, narrative)
    return narrative


# ── 1. Presentazione ─────────────────────────────────────────────────────────

def _presentation_chapter(graph, narrative, graph_name) -> None:
    chapter = narrative.add_chapter("Presentazione", canonical=True)
    projects = _nodes(graph, _ProjectClass)
    if projects:
        project = projects[0]
        desc = (getattr(project, "description", "") or "").strip()
        if desc:
            chapter.add_prose(desc)
        else:
            chapter.add_prose(PLACEHOLDER.format(
                what=f"presentazione del progetto «{project.name}»"))
    else:
        chapter.add_prose(PLACEHOLDER.format(
            what=f"presentazione di {graph_name}"))

    # One embed per source, not a table. A table would list them; an embed
    # SHOWS each one, with its criticism, which is what a reader of a
    # reconstruction needs — and it keeps every source individually
    # referenced, so "which narratives rest on this source" stays answerable.
    sources = _nodes(graph, _SourceClass)
    if sources:
        chapter.add_prose(PLACEHOLDER.format(
            what="come si legge questo racconto e su quali fonti si appoggia"))
        for source in sorted(sources, key=lambda n: str(n.name or n.node_id)):
            chapter.add_embed(source.node_id, "source")


# ── 2. Dove si trova ─────────────────────────────────────────────────────────

def _geo_chapter(graph, narrative) -> None:
    """Only if the graph actually has a position. Inventing coordinates for a
    site would be the worst kind of plausible."""
    geo = _nodes(graph, _GeoClass)
    placed = [g for g in geo if _has_coordinates(g)]
    if not placed:
        return
    chapter = narrative.add_chapter("Dove si trova", canonical=True)
    chapter.add_prose(PLACEHOLDER.format(what="il contesto geografico"))
    chapter.add_embed(placed[0].node_id, "map")


def _has_coordinates(geo) -> bool:
    data = getattr(geo, "data", {}) or {}
    x, y = data.get("shift_x"), data.get("shift_y")
    return bool(x or y)


# ── 3. Un capitolo per epoca ─────────────────────────────────────────────────

def _epoch_chapters(graph, narrative) -> None:
    for epoch in sorted(_nodes(graph, _EpochClass), key=_epoch_sort_key):
        units = _units_of_epoch(graph, epoch.node_id)
        if not units:
            continue  # an empty lane has no story yet
        chapter = narrative.add_chapter(str(epoch.name), anchor=epoch.node_id)
        chapter.add_prose(PLACEHOLDER.format(
            what=f"che cosa accade in «{epoch.name}»"))
        for unit in units:
            chapter.add_embed(unit.node_id, "us")
            # "come lo so": the evidence beside the claim, not in an appendix
            for prop_id in _evidence_for(graph, unit.node_id):
                chapter.add_embed(prop_id, "paradata")


# ── 4. Il cantiere ───────────────────────────────────────────────────────────

def _activity_chapter(graph, narrative) -> None:
    """The actions performed in antiquity — building, collapsing, robbing out.

    TODO (E.D.): EM has no node that says "this is an ACTION" as opposed to
    "this is a grouping". `ActivityNodeGroup` is the closest thing and is what
    this uses, but it is a container of intention, not a typed event: nothing
    distinguishes «costruzione della torre» from «materiale di scavo 2019».
    Until the language does, this chapter can only list the activities and let
    the author say which are actions — it does not classify them, and it does
    not invent an `action` type on the way past. If the multitemporal reading of
    §5 of the spec is to work properly, that distinction probably needs a DP of
    its own.
    """
    activities = _nodes(graph, _ActivityClass)
    if not activities:
        return
    chapter = narrative.add_chapter("Il cantiere", anchor=None)
    chapter.add_prose(PLACEHOLDER.format(
        what="le azioni compiute in antico, epoca per epoca"))
    for activity in activities:
        chapter.add_prose(PLACEHOLDER.format(what=f"l'attività «{activity.name}»"))
        for member in _in(graph, activity.node_id, "is_in_activity"):
            node = graph.find_node_by_id(member)
            if node is not None and _is_stratigraphic(node):
                chapter.add_embed(member, "us")


def _text(value) -> Optional[str]:
    if isinstance(value, dict):
        return value.get("default") or next(iter(value.values()), None)
    return value if isinstance(value, str) else None
