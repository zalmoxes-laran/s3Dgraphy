"""The template registry: a narrative template is just a function.

``build(graph, **opts) -> NarrativeNode``. Registering one is a decorator call;
the core never learns about individual templates, so "site story", "excavation
diary" and "hypothesis comparison" are peers rather than special cases.

The registry also owns the one rule that is easy to get wrong: **regenerating a
narrative must not destroy what the author wrote**. See :func:`merge_narrative`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from ..nodes.narrative_node import Chapter, NarrativeNode

#: A template: given a graph (and options), return a fresh NarrativeNode draft.
NarrativeTemplate = Callable[..., NarrativeNode]

_TEMPLATES: Dict[str, NarrativeTemplate] = {}


def register_template(template_id: str) -> Callable[[NarrativeTemplate],
                                                    NarrativeTemplate]:
    """Decorator: register ``fn`` under ``template_id``."""
    def _wrap(fn: NarrativeTemplate) -> NarrativeTemplate:
        if template_id in _TEMPLATES:
            raise ValueError(f"template '{template_id}' is already registered")
        _TEMPLATES[template_id] = fn
        return fn
    return _wrap


def get_template(template_id: str) -> NarrativeTemplate:
    try:
        return _TEMPLATES[template_id]
    except KeyError:
        raise KeyError(
            f"unknown narrative template '{template_id}'; "
            f"registered: {sorted(_TEMPLATES)}") from None


def list_templates() -> List[str]:
    return sorted(_TEMPLATES)


def build_narrative(graph: Any, template_id: str = "site_story", *,
                    existing: NarrativeNode = None, **opts) -> NarrativeNode:
    """Build a narrative draft from ``graph``.

    With ``existing``, this is a REGENERATION: the fresh draft is merged onto
    what is already there under the rules in :func:`merge_narrative`, so running
    it again after the graph has grown adds the new material without touching
    the writing.
    """
    draft = get_template(template_id)(graph, **opts)
    if existing is None:
        return draft
    return merge_narrative(existing, draft)


def merge_narrative(existing: NarrativeNode,
                    draft: NarrativeNode) -> NarrativeNode:
    """Fold a freshly generated ``draft`` into an ``existing`` narrative.

    The rule, and why it is this one:

    * **A canonical chapter is never touched.** ``canonical`` is precisely the
      author's way of saying "this one is settled" — the introduction they
      rewrote, the geographic chapter they captioned. Regeneration that
      overwrote those would make the button unusable: you would only ever dare
      press it once.
    * **A non-canonical chapter is matched by ``anchor``** — one lane, one
      chapter — and is *extended*, not replaced: embeds the draft has and the
      chapter lacks are appended, and **every prose block the author wrote
      survives**. New material shows up; sentences do not vanish.
    * **A chapter whose lane has disappeared stays.** Deleting an author's
      chapter because an epoch was renamed would be the tool destroying work in
      response to an edit elsewhere. It simply stops being regenerated.
    * **Order**: existing chapters keep their order; genuinely new chapters are
      appended.

    The narrative is modified in place and returned.
    """
    by_anchor = {c.anchor: c for c in existing.chapters if c.anchor}
    titles = {c.title for c in existing.chapters}

    for fresh in draft.chapters:
        current = by_anchor.get(fresh.anchor) if fresh.anchor else None
        if current is None and not fresh.anchor:
            # anchorless chapters (intro, geo) are matched by title — they have
            # no lane to key on
            current = next((c for c in existing.chapters
                            if c.anchor is None and c.title == fresh.title),
                           None)
        if current is None:
            if fresh.title in titles and not fresh.anchor:
                continue
            existing.chapters.append(fresh)
            titles.add(fresh.title)
            if fresh.anchor:
                by_anchor[fresh.anchor] = fresh
            continue
        if current.canonical:
            continue  # settled by the author — leave it exactly as it is
        _extend_chapter(current, fresh)

    # the draft records which template produced it; a regeneration keeps that
    if draft.data.get("template_id"):
        existing.data["template_id"] = draft.data["template_id"]
    return existing


def _extend_chapter(current: Chapter, fresh: Chapter) -> None:
    """Append the embeds ``fresh`` has and ``current`` lacks. Prose is never
    added, removed or reordered: it is the part a human wrote."""
    have = {(b.ref, b.view_type) for b in current.blocks
            if b.block_type == "embed"}
    for block in fresh.blocks:
        if block.block_type != "embed":
            continue
        if (block.ref, block.view_type) in have:
            continue
        current.blocks.append(block)
        have.add((block.ref, block.view_type))
