"""L1 — a narrative projected to LaTeX, with its sources as a `.bib`.

**This is an exporter, not a renderer.** It emits two strings — a `.tex` body and
a `.bib` bibliography — and asks no LaTeX engine to exist. Nothing here typesets,
chooses a document class, or picks a font: those belong to whoever compiles.

The projection follows the same discipline as the RDF one: **project the value,
not the authoring**. A `Block` is not reified into anything — no environment named
after it, no marker recording that the text arrived in three pieces. Prose becomes
prose. An embed becomes what a printed page would put there: a figure with a
caption for something you look at, a citation for something you read. That
distinction is the whole mapping, and it is drawn from the embed's `view_type`.

Two rules kept the design honest:

* **Nothing is invented.** A source with no metadata becomes a minimal `@misc`
  with the title it has and nothing more — no guessed year, no fabricated author.
  A bibliography that invents a date is worse than one that admits it lacks one.
* **Keys come from ids.** A bib key is derived from the node id, deterministically,
  so `\\cite{}` in the `.tex` and the entry in the `.bib` cannot drift, and a
  re-export produces the same keys for the same graph.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

#: View types that a printed page CITES rather than shows. A source and a document
#: are things the reader could go and read; everything else in the vocabulary is
#: something they look at, and becomes a figure.
CITED_VIEW_TYPES = ("source", "document")

#: LaTeX's special characters, and what to write instead. Order matters:
#: the backslash must be replaced first, or it would escape the replacements.
_ESCAPES = (
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
)


def latex_escape(text: str) -> str:
    """Make `text` safe to place in a LaTeX document.

    Applied to everything that came from the graph — names, descriptions, prose.
    An archaeological record is full of `US_101`, `40%`, `Smith & Jones`: without
    this, the export produces a file that does not compile, which is a worse
    failure than an ugly one because it looks like the exporter's fault.
    """
    out = str(text or "")
    for char, replacement in _ESCAPES:
        out = out.replace(char, replacement)
    return out


def _markdown_to_latex(text: str) -> str:
    """The narrow markdown the narrative editor writes → LaTeX.

    `**bold**`, `*italic*`, `` `code` `` and blank-line paragraphs, which is
    exactly what the authoring UI offers. Escaping happens FIRST, so a literal
    asterisk in the prose cannot become emphasis and a brace cannot become a
    group; the markers are then re-read from the escaped text.
    """
    paragraphs = []
    for para in re.split(r"\n{2,}", str(text or "")):
        if not para.strip():
            continue
        body = latex_escape(para.strip())
        body = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", body)
        body = re.sub(r"\*([^*]+)\*", r"\\emph{\1}", body)
        body = re.sub(r"`([^`]+)`", r"\\texttt{\1}", body)
        body = body.replace("\n", " ")
        paragraphs.append(body)
    return "\n\n".join(paragraphs)


def bib_key(node_id: str) -> str:
    """A stable, deterministic BibTeX key for a node id.

    BibTeX keys may not contain spaces, commas, braces or the characters that
    delimit entries; EM ids are UUIDs or dotted names like `D.1`. The mapping is
    therefore: keep alphanumerics, turn every run of anything else into a single
    `-`, and prefix `em:` so a key is recognisable as ours and cannot collide with
    hand-written entries in a bibliography the author merges this into.

    Deterministic on purpose: the same graph exports the same keys, so a document
    that already `\\cite{}`s them keeps working after a re-export.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(node_id or "")).strip("-")
    return f"em:{slug or 'unknown'}"


def _label(prefix: str, node_id: str) -> str:
    """A `\\label` that is stable and unique, on the same principle as bib keys."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(node_id or "")).strip("-")
    return f"{prefix}:{slug or 'unknown'}"


def _node_data(node: Any) -> Dict[str, Any]:
    data = getattr(node, "data", None)
    return data if isinstance(data, dict) else {}


def _first(data: Dict[str, Any], *keys: str) -> Optional[str]:
    """The first key that carries something. Used to read metadata that different
    producers spell differently, without pretending a missing field is present."""
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return None


def _author_label(node: Any) -> str:
    """A person or model as a byline reads them: "Surname, Name" when the node
    carries both, else whatever name there is."""
    data = _node_data(node)
    name = _first(data, "name") or getattr(node, "name", "") or ""
    surname = _first(data, "surname")
    if surname and name:
        return f"{surname}, {name}"
    return str(surname or name or getattr(node, "node_id", ""))


def _person_key(label: str) -> str:
    """A spelling-insensitive identity for a person's name.

    Needed because a narrative carries the author BOTH as free text
    (``data.author``, e.g. "Emanuel Demetrescu") and as AuthorNodes reached
    through the blocks (→ "Demetrescu, Emanuel"). They are one person, and a
    by-line reading "A cura di Emanuel Demetrescu, Demetrescu, Emanuel" is the
    kind of small wrongness that makes a document look unproofread.

    Sorted, case-folded alphanumeric tokens: order and punctuation stop
    mattering, while two genuinely different people stay different.
    """
    tokens = re.findall(r"[A-Za-z0-9]+", str(label or "").lower())
    return " ".join(sorted(tokens))


# ── the bibliography ─────────────────────────────────────────────────────────

def _bib_entry(node: Any) -> Tuple[str, str]:
    """One BibTeX entry for a document/source node → `(key, text)`.

    The entry type is chosen from what the node actually knows, not from a guess:
    a node with a URL and no year is `@misc` with a `url`; one with author and
    year is `@book`-shaped only if it says so. In practice EM documents rarely
    carry structured bibliographic metadata, so `@misc` is the honest default —
    and `@misc` with a title is a valid, citable entry, whereas an `@article`
    missing journal and year is a broken one.
    """
    node_id = getattr(node, "node_id", "")
    data = _node_data(node)
    key = bib_key(node_id)

    title = _first(data, "title") or getattr(node, "name", "") or node_id
    fields: List[Tuple[str, str]] = [("title", latex_escape(title))]

    author = _first(data, "author", "authors", "creator")
    if author:
        fields.append(("author", latex_escape(author)))
    year = _first(data, "year", "date", "created")
    if year:
        fields.append(("year", latex_escape(year)))
    url = _first(data, "url", "locator") or getattr(node, "url", None)
    if url:
        # `url` goes in verbatim: escaping it would break the link, and BibTeX
        # styles expect the raw string. It is the one field that is not escaped.
        fields.append(("url", str(url)))
    note = getattr(node, "description", "") or ""
    if note:
        fields.append(("note", latex_escape(note)))
    # The EM id travels as `keywords` so a printed bibliography can be traced
    # back to the graph. Not decoration: it is how a reader of the PDF finds the
    # node the citation came from.
    fields.append(("keywords", latex_escape(f"EM:{node_id}")))

    body = ",\n  ".join(f"{name} = {{{value}}}" for name, value in fields)
    return key, f"@misc{{{key},\n  {body}\n}}"


# ── the document ─────────────────────────────────────────────────────────────

def _figure(node: Any, view_type: str, caption_extra: str = "") -> str:
    """An embed the reader LOOKS at → a figure placeholder with a caption.

    Deliberately a placeholder and not an `\\includegraphics`: this exporter does
    not know where the author will put the images, or whether the "image" is a 3D
    scene that has to be rendered first. A `\\missingfigure`-style box would need
    a package; a commented `\\includegraphics` line next to a real caption and
    label lets the author drop the file in and uncomment, and meanwhile the
    document compiles and the cross-reference works.
    """
    node_id = getattr(node, "node_id", "")
    name = getattr(node, "name", "") or node_id
    caption = latex_escape(name)
    if caption_extra:
        caption = f"{caption} — {latex_escape(caption_extra)}"
    return (
        "\\begin{figure}[htbp]\n"
        "  \\centering\n"
        f"  % {view_type}: {node_id} — drop the exported image in and uncomment\n"
        f"  % \\includegraphics[width=\\linewidth]{{{node_id}}}\n"
        f"  \\caption{{{caption}}}\n"
        f"  \\label{{{_label('fig', node_id)}}}\n"
        "\\end{figure}"
    )


def _unresolved(ref: str) -> str:
    """A reference the graph no longer answers. Stated in the output rather than
    dropped: a silent omission in a printed text is unrecoverable."""
    return (f"% unresolved reference: {ref} — the graph has no node with this id\n"
            f"\\textbf{{[riferimento non risolto: {latex_escape(ref)}]}}")


def export_narrative_latex(graph: Any, narrative_id: str) -> Dict[str, str]:
    """Project one NarrativeNode to `{"tex": ..., "bib": ...}`.

    `tex` is a BODY, not a whole document: chapters as `\\section`s, prose as
    prose, embeds as figures or `\\cite`s. It is meant to be `\\input{}` into the
    author's own preamble — an exporter that emitted `\\documentclass` would be
    choosing the layout of somebody else's book.

    `bib` holds one entry per cited source, keyed by :func:`bib_key`.

    Raises ``KeyError`` when `narrative_id` names no narrative in the graph:
    exporting nothing under a name the caller believes in would be worse.
    """
    node = graph.find_node_by_id(narrative_id)
    if node is None or getattr(node, "node_type", None) != "narrative":
        raise KeyError(f"no narrative node with id {narrative_id!r}")

    lookup = {getattr(n, "node_id", None): n for n in getattr(graph, "nodes", [])}
    lines: List[str] = []
    bib_entries: Dict[str, str] = {}     # key → entry, so a source cited twice
                                         # yields one entry (dict, not a list)
    cited_order: List[str] = []

    def cite(target: Any) -> str:
        key, entry = _bib_entry(target)
        if key not in bib_entries:
            bib_entries[key] = entry
            cited_order.append(key)
        return key

    title = getattr(node, "name", "") or narrative_id
    lines.append(f"% EM Narrative — {narrative_id}")
    lines.append(f"% generated by s3dgraphy.exporter.latex_exporter; "
                 f"\\input{{}} this into your own preamble")
    lines.append("")
    lines.append(f"\\section*{{{latex_escape(title)}}}")
    description = getattr(node, "description", "") or ""
    if description:
        lines.append("")
        lines.append(_markdown_to_latex(description))

    # ── the byline, and the honesty it carries (N8) ───────────────────────────
    # People who can be asked about a claim come first, as responsible; a model
    # that drafted text is stated as assistance, in a footnote rather than a
    # by-line, because it is not an author. And unendorsed AI text is FLAGGED:
    # a printed page cannot show a badge, so it says so in words.
    responsible: List[str] = []
    assisting: List[str] = []
    seen_people: set = set()
    for author_id in node.author_refs():
        author_node = lookup.get(author_id)
        label = _author_label(author_node) if author_node else author_id
        is_ai = getattr(author_node, "node_type", "") == "author_ai"
        target = assisting if is_ai else responsible
        key = _person_key(label)
        if key in seen_people:
            continue
        seen_people.add(key)
        target.append(label)
    # The narrative's own `data.author` is free text and usually names somebody
    # who is ALSO an AuthorNode, spelled the other way round: same person, two
    # spellings, one by-line.
    declared = _first(_node_data(node), "author")
    if declared and _person_key(declared) not in seen_people:
        seen_people.add(_person_key(declared))
        responsible.insert(0, declared)

    if responsible:
        lines.append("")
        lines.append("\\noindent\\textit{A cura di }"
                     + latex_escape(", ".join(responsible)) + ".")
    if assisting:
        lines.append("\\footnote{Con l'assistenza di "
                     + latex_escape(", ".join(assisting))
                     + ". Il testo generato è stato rivisto e avallato da una "
                       "persona, tranne dove indicato.}")
    pending = node.pending_validation()
    if pending:
        lines.append("")
        lines.append(f"% {len(pending)} AI block(s) are NOT endorsed by a person")
        lines.append("\\noindent\\textbf{Nota.} "
                     + f"{len(pending)} "
                     + ("paragrafo di questo testo è" if len(pending) == 1
                        else "paragrafi di questo testo sono")
                     + " una bozza generata automaticamente e non ancora "
                       "avallata; sono segnalati nel testo.")

    # The prompts behind generated text are DocumentNodes, and a prompt is a
    # source: it goes in the bibliography like any other, so "how did the machine
    # come to write this" is answerable from the printed page.
    for prompt_id in node.prompt_refs():
        prompt = lookup.get(prompt_id)
        if prompt is not None:
            cite(prompt)

    # ── chapters ─────────────────────────────────────────────────────────────
    for chapter in node.chapters:
        lines.append("")
        chapter_title = getattr(chapter, "title", "") or ""
        lines.append(f"\\subsection{{{latex_escape(chapter_title)}}}")
        anchor = getattr(chapter, "anchor", None)
        if anchor:
            # The lane a chapter narrates is structural information a reader of
            # the PDF cannot otherwise recover; as a label it also makes the
            # chapter referenceable.
            lines.append(f"\\label{{{_label('sec', anchor)}}}")
        for block in getattr(chapter, "blocks", []):
            block_type = getattr(block, "block_type", "")
            if block_type == "prose":
                text = getattr(block, "text", "") or ""
                if not text.strip():
                    continue
                body = _markdown_to_latex(text)
                if getattr(block, "ai_generated", False) \
                        and not getattr(block, "validated_by", None):
                    # Said in the text, not only in a comment: an unendorsed
                    # machine draft that looks identical to endorsed prose on
                    # paper would be the one thing this whole design refuses.
                    body = ("\\textit{[bozza generata, non avallata]} " + body)
                lines.append("")
                lines.append(body)
                continue

            ref = getattr(block, "ref", None)
            target = lookup.get(ref) if ref else None
            view_type = getattr(block, "view_type", "") or ""
            lines.append("")
            if target is None:
                lines.append(_unresolved(str(ref)))
            elif view_type in CITED_VIEW_TYPES:
                key = cite(target)
                name = getattr(target, "name", "") or ref
                lines.append(f"\\noindent {latex_escape(name)}~\\cite{{{key}}}.")
            else:
                options = getattr(block, "options", None) or {}
                extra = ""
                if view_type == "map":
                    data = _node_data(target)
                    epsg = data.get("epsg")
                    if epsg:
                        extra = f"EPSG:{epsg}"
                elif options.get("caption"):
                    extra = str(options["caption"])
                lines.append(_figure(target, view_type or "embed", extra))

    tex = "\n".join(lines).rstrip() + "\n"
    bib_header = ("% EM Narrative bibliography — generated by "
                  "s3dgraphy.exporter.latex_exporter\n"
                  "% keys are derived from EM node ids and are stable across "
                  "re-exports\n")
    bib = bib_header + "\n".join(bib_entries[k] for k in cited_order)
    if cited_order:
        bib += "\n"
    return {"tex": tex, "bib": bib}
