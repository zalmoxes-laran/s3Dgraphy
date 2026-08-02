"""EM Narrative — the narrative node and the structures it carries (N0).

A narrative tells the story of a site as **chapters**: the lanes of the graph
(epochs, activities) become the sections of a text, and beside each thing that
happened in antiquity stands *how we know it* — the sources, the paradata chain.

Two decisions shape this module, both worth stating because they are the ones
that could reasonably have gone the other way.

**Chapters and blocks are DATA, not nodes.** Every other composite in EM —
a paradata group, an activity — models membership with edges, and that is right
for membership. But a narrative is *ordered*, and EM has no ordered-edge
primitive: expressing "chapter 3 comes after chapter 2" would mean minting an
integer attribute per node and sorting on it, which is a list wearing a costume.
A chapter also has no existence apart from its narrative — nobody will ever ask
"which graphs contain this chapter". So chapters and blocks are plain
dataclasses serialised into ``node.data``, where a list is a list, and the
NarrativeNode itself is the first-class, queryable, versionable thing the spec
asks for.

**An embed is a reference, never a copy.** ``Block.ref`` holds the stable id of
an EM resource and nothing else: no title, no thumbnail, no cached value. The
moment a US is renamed or a source is withdrawn, every narrative that cites it
says the new thing. That is the whole reason for authoring on the property graph
instead of pasting text — and it is why :meth:`NarrativeNode.referenced_ids`
exists rather than a `referenced_names`.

Two-tier invariant: this is the **authoring** layer (property graph, em.json).
RDF is a projection of it, emitted by the exporter — never the other way round.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base_node import Node

#: The ways an embedded resource can be rendered. The name says WHAT to show,
#: not how: a viewer that cannot yet draw one of these shows a placeholder and
#: says so, which is honest and lets the enum lead the implementations rather
#: than trail them (spec §4).
NARRATIVE_VIEW_TYPES = (
    "matrix",     # the matrix, or a slice of one epoch
    "epoch3d",    # the 3D scene of an epoch (Heriverse / ATON)
    "us",         # a stratigraphic unit with its certainty qualia
    "rm",         # a representation model (RM / RMDoc)
    "document",   # a document or image (Shelf / IIIF)
    "source",     # a source together with its criticism
    "paradata",   # the evidence chain: source → extractor → property
    "map",        # geographic placement (OSM)
    "timeline",
    "table",      # a query over the em.json
    "un_scene",   # a composable scene (DP-29)
)

#: The two kinds of block. `prose` carries text the author wrote; `embed`
#: carries a reference to something the graph already knows.
BLOCK_PROSE = "prose"
BLOCK_EMBED = "embed"
NARRATIVE_BLOCK_TYPES = (BLOCK_PROSE, BLOCK_EMBED)


class NarrativeError(ValueError):
    """A narrative structure was given something the model does not admit."""


@dataclass
class Block:
    """One unit of a chapter: either prose, or a reference to a resource.

    A `prose` block owns its ``text``. An `embed` block owns nothing — only the
    ``ref`` of the resource, the ``view_type`` saying how to show it, and free
    ``options`` for the renderer. Anything an embed could cache is something
    that would go stale.
    """

    block_type: str
    text: str = ""
    ref: Optional[str] = None
    view_type: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.block_type not in NARRATIVE_BLOCK_TYPES:
            raise NarrativeError(
                f"block_type must be one of {NARRATIVE_BLOCK_TYPES}, "
                f"got {self.block_type!r}")
        if self.block_type == BLOCK_EMBED:
            if not self.ref:
                raise NarrativeError("an embed block needs a ref")
            if self.view_type not in NARRATIVE_VIEW_TYPES:
                raise NarrativeError(
                    f"view_type must be one of {NARRATIVE_VIEW_TYPES}, "
                    f"got {self.view_type!r}")

    # — helpers ————————————————————————————————————————————————————————
    @classmethod
    def prose(cls, text: str) -> "Block":
        return cls(block_type=BLOCK_PROSE, text=text)

    @classmethod
    def embed(cls, ref: str, view_type: str, **options: Any) -> "Block":
        return cls(block_type=BLOCK_EMBED, ref=ref, view_type=view_type,
                   options=dict(options))

    def to_dict(self) -> Dict[str, Any]:
        """Only what this block actually carries — an absent key is smaller and
        clearer than a null one, and the reader fills the defaults."""
        out: Dict[str, Any] = {"block_type": self.block_type}
        if self.block_type == BLOCK_PROSE:
            out["text"] = self.text
        else:
            out["ref"] = self.ref
            out["view_type"] = self.view_type
            if self.options:
                out["options"] = self.options
        return out

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Block":
        return cls(
            block_type=payload.get("block_type", BLOCK_PROSE),
            text=payload.get("text", "") or "",
            ref=payload.get("ref"),
            view_type=payload.get("view_type"),
            options=dict(payload.get("options") or {}),
        )


@dataclass
class Chapter:
    """A section of the story, usually anchored to one lane of the graph.

    ``anchor`` is the id of an epoch, an activity/group, or an area label —
    whatever lane this chapter narrates — or ``None`` for a chapter that stands
    outside the stratigraphy (the introduction, the geographic placement).

    ``canonical`` marks a chapter the author has settled: the scaffolder (N1)
    regenerates the rest from the graph, and must leave these alone. It is the
    difference between a draft the machine keeps refreshing and a text somebody
    has decided.
    """

    title: str
    anchor: Optional[str] = None
    canonical: bool = False
    blocks: List[Block] = field(default_factory=list)

    def add_prose(self, text: str) -> Block:
        block = Block.prose(text)
        self.blocks.append(block)
        return block

    def add_embed(self, ref: str, view_type: str, **options: Any) -> Block:
        block = Block.embed(ref, view_type, **options)
        self.blocks.append(block)
        return block

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"title": self.title, "canonical": self.canonical,
                               "blocks": [b.to_dict() for b in self.blocks]}
        if self.anchor:
            out["anchor"] = self.anchor
        return out

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Chapter":
        return cls(
            title=payload.get("title", "") or "",
            anchor=payload.get("anchor"),
            canonical=bool(payload.get("canonical", False)),
            blocks=[Block.from_dict(b) for b in (payload.get("blocks") or [])],
        )


class NarrativeNode(Node):
    """A story told over the graph — a first-class node, not a document beside it.

    Being a node is the point: a narrative can be asked about ("which narratives
    cite this US", "which rest on a withdrawn source", "how much of epoch 3 has
    anyone actually written about"), versioned, and carried through the DTC like
    any other EM entity. A text file next to the graph could do none of that.

    Metadata follows the conventions already in the language: ``author`` /
    ``license`` / ``embargo`` are the rights triple (DP-32), ``lang`` the
    language tag (DP-63), ``template_id`` the scaffolder that produced the first
    draft (N1) — recorded so a regeneration knows what it is regenerating.
    """

    node_type = "narrative"

    def __init__(self, node_id, name, description="", *, author=None,
                 license=None, embargo=None, lang=None, version=None,
                 template_id=None, chapters=None, data=None):
        super().__init__(node_id=node_id, name=name, description=description)
        self.data = dict(data or {})
        # Tolerant on purpose: the em.json importer matches constructor
        # parameters against the serialised `data{}`, so `chapters` arrives here
        # as a list of plain dicts. Parsing them at the door means the round
        # trip needs no special case in the importer.
        self.chapters: List[Chapter] = [
            c if isinstance(c, Chapter) else Chapter.from_dict(c)
            for c in (chapters or [])
        ]
        # `chapters` is owned by the attribute, not by data{} — keep one copy.
        self.data.pop("chapters", None)
        # Written only when set: a narrative that declares no language is
        # different from one that declares "unknown", and the difference is
        # worth keeping.
        for key, value in (("author", author), ("license", license),
                           ("embargo", embargo), ("lang", lang),
                           ("version", version), ("template_id", template_id)):
            if value is not None:
                self.data[key] = value

    # — chapters ————————————————————————————————————————————————————————

    def add_chapter(self, title, anchor=None, canonical=False) -> Chapter:
        chapter = Chapter(title=title, anchor=anchor, canonical=canonical)
        self.chapters.append(chapter)
        return chapter

    def chapter_by_anchor(self, anchor) -> Optional[Chapter]:
        """The chapter narrating a given lane, or None. The scaffolder merges on
        this: one lane, one chapter."""
        if not anchor:
            return None
        return next((c for c in self.chapters if c.anchor == anchor), None)

    # — references ————————————————————————————————————————————————————————

    def referenced_ids(self) -> List[str]:
        """Every resource this narrative points at, in order of appearance,
        without repetitions.

        This is what makes "which narratives cite this US" answerable without
        parsing prose, and what the RDF projection turns into reference
        predicates.
        """
        seen, out = set(), []
        for chapter in self.chapters:
            for block in chapter.blocks:
                if block.block_type == BLOCK_EMBED and block.ref \
                        and block.ref not in seen:
                    seen.add(block.ref)
                    out.append(block.ref)
        return out

    def unresolved_refs(self, graph) -> List[str]:
        """The referenced ids that no node in ``graph`` answers to.

        An embed is a reference, so it can dangle — a source removed from the
        graph leaves the narrative pointing at nothing. Saying which, instead of
        rendering a blank, is the same principle as the state warnings.
        """
        return [ref for ref in self.referenced_ids()
                if graph.find_node_by_id(ref) is None]

    # — serialisation ——————————————————————————————————————————————————————
    #
    # `chapters` lives inside `node.data`, which the em.json exporter already
    # copies verbatim for every node when it is JSON-safe. So the round-trip
    # costs no exporter change and no SCHEMA_VERSION bump: to a reader that has
    # never heard of narratives, a NarrativeNode is a node with an unfamiliar
    # node_type and some data — exactly the forward-compatible degradation the
    # format was built for.

    def to_data(self) -> Dict[str, Any]:
        """The `data` payload, chapters included."""
        out = dict(self.data)
        out["chapters"] = [c.to_dict() for c in self.chapters]
        return out

    @classmethod
    def from_payload(cls, node_id, name, description="", data=None
                     ) -> "NarrativeNode":
        payload = dict(data or {})
        chapters = [Chapter.from_dict(c) for c in (payload.pop("chapters", None)
                                                   or [])]
        node = cls(node_id=node_id, name=name, description=description,
                   data=payload)
        node.chapters = chapters
        return node
