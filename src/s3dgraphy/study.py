"""What a study says about ITSELF — the card a catalogue derives from a container.

The Catalog's founding decision (StratiGraph_Catalog_SPEC_per_3DR §1–2, and the
runner that made it executable): **the unit of the catalogue is the STUDY, and a
study is one em.json container**. The container is the truth; the catalogue's
index is a **projection** of it, rebuildable by re-reading the containers. This
module is the seam that makes that sentence true rather than aspirational —
without it, an indexer would have to know where a licence lives, and the day it
guessed wrong the index would be a second, disagreeing truth.

**Nothing here is a new node type, and nothing is invented.** Authorship,
licence and embargo already live as **graph-scope nodes** (DP-65 / MIG1-A: a
`GraphNode` owning a `ParadataNodeGroup` whose members are `AuthorNode` /
`LicenseNode` / `EmbargoNode`); the HDT view already has its vocabulary
(HDT-O: `HeritageEntityNode` = HC1, `HDTNode` = HC2, `StudyNode` = HC9); the
version already travels beside the header (P3 `ProjectVersion`) and the site
position already sits on the graph-self node (GEO1). This function READS those
and puts them in one shape. The spec says it in one line — the Catalog *exposes
and indexes* them, it does not reinvent them.

**A missing field is missing.** Every key of the card is always present (an
index needs a stable schema) and its value is `None` / `[]` when the container
does not say. Nothing is defaulted into existence: a study without a licence
must READ as a study without a licence, because "CC-BY" invented by a reader is
a licence nobody granted.

The one thing that IS computed: `checksum`, the container's content digest
(`container.content_digest`) — the same oracle P3 uses to decide whether a save
is a new version. It is what lets a catalogue answer "is the copy I indexed
still the copy you have".

Precedence, stated once because a reader of an index deserves to know where a
value came from:

* **title** — `header.title`, else the active graph's name, else its id;
* **authors / license / embargo** — the graph-scope NODES (DP-65) of every
  member graph, in member order; the legacy `graph.data` spellings
  (`authors`, `license`, `embargo_until`) are read only as a fallback, so a
  container written before MIG1-A still catalogues;
* **visibility** — `header.visibility`, normalised, defaulting to
  **restricted**: a study served too openly cannot be un-served;
* **version** — the container's `ProjectVersion` (top level, NOT the header:
  the header describes the FORMAT, the version describes the WORK);
* **hc1 / hc2** — the HDT-O nodes, if the study carries them;
* **spatial** — `GraphNode.data.site_position` (GEO1), which is the SITE, not
  the georeferencing shift.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .container import Container, content_digest, parse_container

#: What `header.visibility` may say, and what it means here. The spec writes
#: `public|private`; the rooms of em-server write `public|restricted`. One
#: concept, two spellings in the wild — read both, answer in one, never invent a
#: third. Anything unknown reads as restricted, which is the safe direction:
#: the failure modes are not symmetric.
VISIBILITY_PUBLIC = "public"
VISIBILITY_RESTRICTED = "restricted"
_PUBLIC_SPELLINGS = {"public", "published", "open"}


def normalise_visibility(raw: Any) -> str:
    """`public` only when the document says so; everything else is restricted."""
    if isinstance(raw, str) and raw.strip().lower() in _PUBLIC_SPELLINGS:
        return VISIBILITY_PUBLIC
    return VISIBILITY_RESTRICTED


def _text(value: Any) -> Optional[str]:
    """graph.name / node.name may be a multilang dict or a plain string."""
    if value is None:
        return None
    if isinstance(value, dict):
        picked = value.get("default") or next(iter(value.values()), None)
        return str(picked) if picked not in (None, "") else None
    text = str(value).strip()
    return text or None


def _graph_scope_members(graph: Any) -> Dict[str, List[Any]]:
    """The DP-65 graph-scope paradata of one graph, by node type.

    Walks the structure rather than guessing ids: graph-self node
    → `has_paradata_nodegroup` → the group → `is_in_paradata_nodegroup`. A
    container whose author node was minted with a different id still resolves,
    which is the whole reason the walk exists.
    """
    out: Dict[str, List[Any]] = {}
    roots = [n for n in graph.nodes if getattr(n, "node_type", "") == "graph"]
    if not roots:
        return out
    by_id = {n.node_id: n for n in graph.nodes}
    group_ids = {e.edge_target for e in graph.edges
                 if e.edge_type == "has_paradata_nodegroup"
                 and e.edge_source in {r.node_id for r in roots}}
    if not group_ids:
        return out
    for edge in graph.edges:
        if edge.edge_type != "is_in_paradata_nodegroup":
            continue
        if edge.edge_target not in group_ids:
            continue
        member = by_id.get(edge.edge_source)
        if member is None:
            continue
        out.setdefault(getattr(member, "node_type", ""), []).append(member)
    return out


def _authors_of(graph: Any) -> List[Dict[str, Optional[str]]]:
    """`[{name, orcid}]` — the display value is the node NAME (DP-65), and the
    ORCID rides on its data when somebody claimed one."""
    people: List[Dict[str, Optional[str]]] = []
    members = _graph_scope_members(graph)
    for kind in ("author", "author_ai"):
        for node in members.get(kind, []):
            name = _text(getattr(node, "name", None))
            data = getattr(node, "data", None)
            orcid = data.get("orcid") if isinstance(data, dict) else None
            entry = {"name": name, "orcid": _text(orcid)}
            if kind == "author_ai":
                entry["kind"] = "ai"
            if entry not in people:
                people.append(entry)
    if people:
        return people
    # LEGACY (pre-MIG1-A): a bare list on graph.data. Read, never written back.
    data = getattr(graph, "data", None)
    if isinstance(data, dict):
        for raw in data.get("authors") or []:
            entry = {"name": _text(raw), "orcid": None}
            if entry["name"] and entry not in people:
                people.append(entry)
    return people


def _member_value(graph: Any, node_type: str, *legacy_keys: str) -> Optional[str]:
    """One graph-scope value by node type, with the legacy `graph.data` spelling
    behind it. Returns the NAME, which is where DP-65 keeps the display value."""
    for node in _graph_scope_members(graph).get(node_type, []):
        value = _text(getattr(node, "name", None))
        if value:
            return value
    data = getattr(graph, "data", None)
    if isinstance(data, dict):
        for key in legacy_keys:
            value = _text(data.get(key))
            if value:
                return value
    return None


def _hdt_of(graph: Any) -> Dict[str, Optional[Dict[str, Optional[str]]]]:
    """The HDT-O pair, when the study carries it: HC2 (the digital twin) and HC1
    (the heritage entity it is a twin OF).

    HC1 is taken from the entity node when there is one, and otherwise from the
    HDT's own `heritage_entity_iri` — the same fact recorded two ways, and a
    catalogue that only understood one of them would group half the studies.
    """
    hc2 = hc1 = None
    for node in graph.nodes:
        kind = getattr(node, "node_type", "")
        data = getattr(node, "data", None) or {}
        if kind == "hdt" and hc2 is None:
            hc2 = {"id": node.node_id, "name": _text(getattr(node, "name", None)),
                   "iri": _text(data.get("heritage_entity_iri"))}
        elif kind == "heritage_entity" and hc1 is None:
            hc1 = {"id": node.node_id, "name": _text(getattr(node, "name", None)),
                   "kind": _text(data.get("entity_kind"))}
    if hc1 is None and hc2 is not None and hc2.get("iri"):
        hc1 = {"id": None, "name": None, "kind": None, "iri": hc2["iri"]}
    return {"hc1": hc1, "hc2": hc2}


def _spatial_of(graph: Any) -> Optional[Dict[str, Any]]:
    """The SITE position (GEO1), which is a place on Earth — not the
    georeferencing shift, which is an offset in a 3D scene. Conflating them is
    how a catalogue puts a study in the Gulf of Guinea."""
    for node in graph.nodes:
        if getattr(node, "node_type", "") != "graph":
            continue
        data = getattr(node, "data", None)
        site = data.get("site_position") if isinstance(data, dict) else None
        if isinstance(site, dict) and site.get("lat") is not None \
                and site.get("lon") is not None:
            try:
                return {"lat": float(site["lat"]), "lon": float(site["lon"]),
                        "crs": _text(site.get("crs")) or "EPSG:4326"}
            except (TypeError, ValueError):
                return None
    return None


def _em_id_of(graph: Any) -> Optional[str]:
    for node in graph.nodes:
        if getattr(node, "node_type", "") == "graph":
            data = getattr(node, "data", None)
            if isinstance(data, dict):
                return _text(data.get("em_id"))
    return None


def study_metadata(container: Any, *, study_id: Optional[str] = None
                   ) -> Dict[str, Any]:
    """The catalogue card of one study, derived from its container.

    Accepts a :class:`~s3dgraphy.container.Container` or the raw em.json
    document (a dict) — a catalogue holds documents, and making it parse first
    just to call this would be a seam in the wrong place.

    `study_id` is the identity the CALLER owns: a catalogue mints and keeps it,
    a library does not get to invent one. When it is not given the card carries
    the container's own `em_id` if there is one, and otherwise `None` — an
    honest gap rather than a random uuid that would change on every read.
    """
    doc: Optional[Dict[str, Any]] = None
    if isinstance(container, dict):
        doc = container
        container, _warnings = parse_container(doc)
    if not isinstance(container, Container):
        raise TypeError("study_metadata wants a Container or an em.json document")

    header = container.header or {}
    graphs = [container.graphs[gid] for gid in container.graph_ids()]
    active = container.active()
    ordered = ([active] + [g for g in graphs if g is not active]) if active else graphs

    authors: List[Dict[str, Optional[str]]] = []
    for graph in ordered:
        for entry in _authors_of(graph):
            if entry not in authors:
                authors.append(entry)

    license_value = embargo_value = None
    hdt: Dict[str, Optional[Dict[str, Optional[str]]]] = {"hc1": None, "hc2": None}
    spatial = None
    em_id = None
    for graph in ordered:
        license_value = license_value or _member_value(
            graph, "license", "license", "licence")
        embargo_value = embargo_value or _member_value(
            graph, "embargo", "embargo", "embargo_until")
        found = _hdt_of(graph)
        hdt["hc1"] = hdt["hc1"] or found["hc1"]
        hdt["hc2"] = hdt["hc2"] or found["hc2"]
        spatial = spatial or _spatial_of(graph)
        em_id = em_id or _em_id_of(graph)

    title = _text(header.get("title"))
    if not title and active is not None:
        title = _text(getattr(active, "name", None)) or _text(active.graph_id)

    description = _text(header.get("description"))
    if not description and active is not None:
        description = _text(getattr(active, "description", None))

    version = container.version.as_dict() if container.version else None

    if doc is None:
        # a Container was handed in: rebuild the document shape the digest is
        # defined over, so the same study always hashes the same way
        from .exporter.emjson_exporter import build_emjson
        doc = {"graphs": {gid: build_emjson(graph)["graph"]
                          for gid, graph in container.graphs.items()},
               "active_graph_id": container.active_graph_id}

    return {
        "id": study_id or em_id,
        "em_id": em_id,
        "title": title,
        "description": description,
        "authors": authors,
        "license": license_value,
        "embargo": embargo_value,
        "visibility": normalise_visibility(header.get("visibility")),
        "version": version,
        "hc1": hdt["hc1"],
        "hc2": hdt["hc2"],
        "spatial": spatial,
        "graph_ids": list(container.graph_ids()),
        "has_shelf": container.shelf is not None,
        "checksum": content_digest(doc),
    }
