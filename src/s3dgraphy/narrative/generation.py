"""N5 — the seam between the graph and a language model, on the graph's side.

**s3Dgraphy stays pure.** No LLM SDK, no network, not even an import of one —
the same discipline that keeps it free of web frameworks and of the resource
layer's optional deps. What lives here is the two halves that touch the *graph*:

    build_narrative_generation_context(graph, …)  → a plain dict, ready to prompt
    write_ai_draft(graph, …)                      → the generated prose, attributed

The call in between happens in em-bridge, behind a provider interface. That
split is not bureaucratic: it means the context builder can be tested exactly
(it is a pure function of the graph), the write-back can be tested exactly, and
the only untestable part — a remote model — is isolated in one adapter.

What the context contains is deliberately narrow: the activity, its actions,
their epochs, and the evidence already recorded for them. It is a *briefing*,
not a dump of the graph. What is not in it cannot leak.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from ..nodes.document_node import DocumentNode
from ..nodes.epoch_node import EpochNode
from ..nodes.extractor_node import ExtractorNode
from ..nodes.group_node import ActivityNodeGroup
from ..nodes.narrative_node import (Block, Chapter, NarrativeError,
                                    NarrativeNode)
from ..nodes.stratigraphic_node import StratigraphicNode

#: The style contract handed to the model. Not decoration: these are the rules
#: that keep a generated paragraph admissible in an archaeological record, and
#: they are the same rules the template obeys — say what the graph says, and
#: nothing else.
GENERATION_CONSTRAINTS = [
    "Write only what the supplied context supports. Do not add dates, "
    "materials, functions or events that are not in it.",
    "Where the context records uncertainty, keep it: a virtual unit is a "
    "hypothesis, not a fact.",
    "Cite nothing that is not among the sources given.",
    "Write continuous prose for a reader who is not holding the matrix in "
    "their head. No bullet lists, no headings.",
    "If the context is too thin to say anything, say so plainly instead of "
    "filling the space.",
]


def _out(graph, node_id: str, edge_type: str) -> List[str]:
    return [e.edge_target for e in graph.edges
            if e.edge_source == node_id and e.edge_type == edge_type]


def _in(graph, node_id: str, edge_type: str) -> List[str]:
    return [e.edge_source for e in graph.edges
            if e.edge_target == node_id and e.edge_type == edge_type]


def _node_brief(node) -> Dict[str, Any]:
    return {
        "id": node.node_id,
        "name": str(getattr(node, "name", "") or ""),
        "type": getattr(node, "node_type", ""),
        "description": (getattr(node, "description", "") or ""),
    }


def _evidence_brief(graph, unit_id: str) -> List[Dict[str, Any]]:
    """The evidence chain behind a unit: property → extractor → source.

    This is the part that makes a generated sentence checkable. A model told
    "the wall is in opera incerta" can only repeat it; a model told "the wall is
    in opera incerta, read from Maiuri's survey by extractor D.1.1" can write a
    sentence an archaeologist can verify.
    """
    out = []
    for prop_id in _out(graph, unit_id, "has_property"):
        prop = graph.find_node_by_id(prop_id)
        if prop is None:
            continue
        chain = []
        for ext_id in _out(graph, prop_id, "has_data_provenance"):
            ext = graph.find_node_by_id(ext_id)
            if ext is None:
                continue
            sources = []
            for doc_id in _out(graph, ext_id, "extracted_from"):
                doc = graph.find_node_by_id(doc_id)
                if doc is not None:
                    sources.append(_node_brief(doc))
            chain.append({**_node_brief(ext), "sources": sources})
        if not chain:
            continue  # a property nobody justified proves nothing
        out.append({
            "property": _node_brief(prop),
            "value": str(getattr(prop, "value", "") or ""),
            "provenance": chain,
        })
    return out


def _epochs_of(graph, unit_id: str) -> List[Dict[str, Any]]:
    out = []
    for edge_type in ("has_first_epoch", "survive_in_epoch"):
        for ep_id in _out(graph, unit_id, edge_type):
            epoch = graph.find_node_by_id(ep_id)
            if isinstance(epoch, EpochNode):
                out.append({
                    "id": epoch.node_id,
                    "name": str(epoch.name),
                    "start": getattr(epoch, "start_time", None),
                    "end": getattr(epoch, "end_time", None),
                    "relation": edge_type,
                })
    return out


def build_narrative_generation_context(
    graph, activity_id: Optional[str] = None, *,
    chapter_ref: Optional[str] = None,
    template_id: str = "site_story",
) -> Dict[str, Any]:
    """Everything a model needs to write about one activity — and nothing else.

    Pure: reads the graph, returns a JSON-serialisable dict, touches no network.

    ``activity_id`` names an :class:`ActivityNodeGroup`; ``chapter_ref`` is
    accepted as an alias so a caller holding a chapter's ``anchor`` can pass it
    straight through, since an activity chapter is anchored to the activity.

    The shape:

    ``activity``     the thing that happened, with its own narrative if one exists
    ``actions``      the units it contains, in stratigraphic order, each with its
                     epochs and its evidence chain
    ``epochs``       the lanes those actions touch, oldest first
    ``sources``      the documents the evidence rests on, de-duplicated
    ``constraints``  the style contract (:data:`GENERATION_CONSTRAINTS`)

    Raises :class:`NarrativeError` when the target is not an activity — better
    than handing a model an empty briefing and letting it improvise.
    """
    target_id = activity_id or chapter_ref
    if not target_id:
        raise NarrativeError("build_narrative_generation_context needs an "
                             "activity_id (or chapter_ref)")
    activity = graph.find_node_by_id(target_id)
    if not isinstance(activity, ActivityNodeGroup):
        kind = type(activity).__name__ if activity is not None else "nothing"
        raise NarrativeError(
            f"'{target_id}' is {kind}, not an ActivityNodeGroup: generation is "
            f"anchored to an activity, which is where the actions are")

    members = [graph.find_node_by_id(mid)
               for mid in _in(graph, target_id, "is_in_activity")]
    units = [m for m in members
             if m is not None and isinstance(m, StratigraphicNode)]

    # stratigraphic order — the order in which it happened, which is the order
    # a story wants. Same walk the template uses.
    from .site_story import _topological_by_is_after
    units = _topological_by_is_after(graph, units)

    actions, sources, seen_sources = [], [], set()
    epochs, seen_epochs = [], set()
    for unit in units:
        evidence = _evidence_brief(graph, unit.node_id)
        unit_epochs = _epochs_of(graph, unit.node_id)
        actions.append({
            **_node_brief(unit),
            "epochs": unit_epochs,
            "evidence": evidence,
        })
        for ep in unit_epochs:
            if ep["id"] not in seen_epochs:
                seen_epochs.add(ep["id"])
                epochs.append(ep)
        for item in evidence:
            for prov in item["provenance"]:
                for src in prov["sources"]:
                    if src["id"] not in seen_sources:
                        seen_sources.add(src["id"])
                        sources.append(src)

    epochs.sort(key=lambda e: (e["start"] is None, e["start"] or 0))

    return {
        "graph_id": getattr(graph, "graph_id", ""),
        "template_id": template_id,
        "activity": {
            **_node_brief(activity),
            "narrative": getattr(activity, "narrative", "") or "",
        },
        "actions": actions,
        "epochs": epochs,
        "sources": sources,
        "constraints": list(GENERATION_CONSTRAINTS),
    }


def ensure_ai_author(graph, *, model: str, version: str = "",
                     node_id: Optional[str] = None):
    """Find-or-create the AuthorAINode for a model. One node per model, reused.

    A fresh author node per generation would scatter the same agent across the
    graph and make "what did this model write" unanswerable.
    """
    from ..nodes.author_node import AuthorAINode

    if not model:
        raise NarrativeError("an AI draft must name the model that wrote it")
    label = f"{model} {version}".strip()
    # Reuse is keyed on the MODEL, not on a guessed node id: the graph may
    # already know this model under a name somebody chose (`AI.claude`), and
    # minting `AI.claude-opus-5` beside it would split one agent in two.
    for node in graph.nodes:
        if isinstance(node, AuthorAINode) and \
                (node.data or {}).get("model") == model:
            return node
    author_id = node_id or f"AI.{model}"
    existing = graph.find_node_by_id(author_id)
    if isinstance(existing, AuthorAINode):
        return existing
    if existing is not None:
        raise NarrativeError(
            f"'{author_id}' already exists and is not an AI author")
    author = AuthorAINode(node_id=author_id, name=label or model, model=model)
    if version:
        author.data["version"] = version
    graph.add_node(author)
    return author


def register_prompt_extractor(graph, prompt: str, *,
                              node_id: Optional[str] = None,
                              name: Optional[str] = None,
                              sources: Optional[List[str]] = None,
                              based_on: str = ""):
    """Record a prompt as an **ExtractorNode**, wired to the sources it read.

    Not a DocumentNode. A document is a thing you consult; a prompt is an
    *operation* — applied to a context, it yields an assertion — and that is
    precisely what an Extractor is in EM. Filing it as a document was the least
    wrong box among the ones that existed, not a right one (E.D., 2026-08-02).

    Modelling it correctly is not tidiness. The extractor slots into the chain
    the language already has —

        PropertyNode --has_data_provenance--> ExtractorNode --extracted_from--> DocumentNode

    — so an AI paragraph is justified the same way a reading off a survey is,
    and the RDF projection follows for free: the exporter's `extractor` branch
    emits `crminf:J7_is_based_on_evidence_from` and the I7 Belief-Adoption
    skeleton. The machine's contribution becomes a belief adopted from stated
    evidence, which is exactly what it is.

    ``sources`` are the documents the briefing rested on; each becomes an
    `extracted_from` edge. Without them the extractor would be inert — an
    operation with nothing to operate on — which is the failing the DocumentNode
    had. Ids that are not documents are skipped rather than fabricated.

    The prompt TEXT lives in the description, so the record is self-contained: a
    reader sees what was asked, not merely that something was asked.
    """
    if not (prompt or "").strip():
        raise NarrativeError("an AI draft must record the prompt that produced it")
    # A CONTENT hash, not `hash()`: Python randomises string hashing per
    # process, so the same prompt would get a different node id after every
    # restart of the bridge — one operation silently forking into many.
    digest = hashlib.sha1(prompt.strip().encode("utf-8")).hexdigest()[:12]
    ext_id = node_id or f"EXT.prompt.{digest}"
    existing = graph.find_node_by_id(ext_id)
    if isinstance(existing, ExtractorNode):
        return existing
    if existing is not None:
        raise NarrativeError(
            f"'{ext_id}' already exists and is not an extractor")

    extractor = ExtractorNode(node_id=ext_id, name=name or "Prompt",
                              description=prompt,
                              source=based_on or None)
    graph.add_node(extractor)

    for doc_id in sources or []:
        doc = graph.find_node_by_id(doc_id)
        if not isinstance(doc, DocumentNode):
            continue          # never invent a source that is not one
        edge_id = f"{ext_id}_extracted_from_{doc_id}"
        if not graph.find_edge_by_id(edge_id):
            graph.add_edge(edge_id, ext_id, doc_id, "extracted_from")
    return extractor


#: The pre-N7 name. Kept so a caller written against N5 keeps working; it now
#: returns an ExtractorNode, which is the point of the change.
register_prompt_source = register_prompt_extractor


def write_ai_draft(graph, target: str, text: str, *, model: str,
                   version: str = "", date: Optional[str] = None,
                   prompt: str = "", narrative_id: Optional[str] = None,
                   chapter_title: Optional[str] = None,
                   sources: Optional[List[str]] = None) -> Dict[str, Any]:
    """Put generated prose into a narrative, attributed and unendorsed.

    ``target`` is the activity the prose is about; the block lands in the
    chapter anchored to it, creating the chapter if the narrative has none yet.

    Three things happen together, and none of them is optional:

    * the text is attributed to the **AI author** for that model;
    * the **prompt is registered as an Extractor** — wired to the documents the
      briefing rested on — and the block points at it;
    * the block is left **unendorsed** — `write_ai_draft` never validates
      anything, because validation is an act by a person and this is not one.

    Returns ``{narrative_id, chapter_title, author_id, prompt_id, status}``.
    """
    if not (text or "").strip():
        raise NarrativeError("nothing to write: the model returned no text")

    narratives = [n for n in graph.nodes if isinstance(n, NarrativeNode)]
    if narrative_id:
        narrative = graph.find_node_by_id(narrative_id)
        if not isinstance(narrative, NarrativeNode):
            raise NarrativeError(f"'{narrative_id}' is not a narrative")
    elif len(narratives) == 1:
        narrative = narratives[0]
    elif not narratives:
        raise NarrativeError(
            "this graph has no narrative yet: generate one with the site_story "
            "template first, or pass narrative_id")
    else:
        raise NarrativeError(
            f"this graph has {len(narratives)} narratives: pass narrative_id to "
            f"say which one")

    author = ensure_ai_author(graph, model=model, version=version)
    # The sources the briefing actually used. A caller that already built the
    # context (em-bridge does) passes them in; otherwise rebuild, because an
    # extractor with no `extracted_from` is an operation with nothing to
    # operate on — the very inertness that made the DocumentNode wrong.
    if prompt and sources is None:
        try:
            sources = [s["id"] for s in
                       build_narrative_generation_context(graph, target)["sources"]]
        except NarrativeError:
            sources = []      # not an activity: file the prompt anyway
    prompt_doc = register_prompt_extractor(
        graph, prompt, sources=sources, based_on=target) if prompt else None

    chapter = narrative.chapter_by_anchor(target)
    if chapter is None:
        activity = graph.find_node_by_id(target)
        title = chapter_title or str(getattr(activity, "name", "") or target)
        chapter = narrative.add_chapter(title, anchor=target)

    block = chapter.add_ai_prose(
        text.strip(), author_id=author.node_id,
        prompt_ref=prompt_doc.node_id if prompt_doc else None)
    if date:
        block.options["generated_at"] = date
    if version:
        block.options["model_version"] = version

    # the narrative as a whole is attributed to the model too, so
    # "what did this model write" is answerable from the edges
    edge_id = f"{narrative.node_id}_has_author_{author.node_id}"
    if not graph.find_edge_by_id(edge_id):
        graph.add_edge(edge_id, narrative.node_id, author.node_id, "has_author")

    return {
        "narrative_id": narrative.node_id,
        "chapter_title": chapter.title,
        "author_id": author.node_id,
        "prompt_id": prompt_doc.node_id if prompt_doc else None,
        "status": block.status,          # always "ai_draft" here, by design
        "pending_validation": len(narrative.pending_validation()),
    }
