"""EM Narrative — the scaffolders that turn a graph into a first draft (N1).

Nobody starts writing from a blank page. The graph already knows which epochs
there are, in what order, which units belong to each, and which sources justify
them: a template reads that and lays out the chapters, so the author's work
starts at "what do I want to say about this epoch" rather than at "what is in
here".

What a template does NOT do is write the content. It produces structure —
chapters, anchors, embeds — and, where prose belongs, a visible placeholder. A
machine-written sentence about an archaeological site would be a guess wearing
the author's name.
"""

from .registry import (NarrativeTemplate, build_narrative, get_template,
                       list_templates, register_template)
from .site_story import build_site_story

__all__ = [
    "NarrativeTemplate",
    "build_narrative",
    "get_template",
    "list_templates",
    "register_template",
    "build_site_story",
]
