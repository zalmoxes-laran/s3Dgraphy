"""The figures a CLIENT rendered end up in all four exports — or degrade honestly.

The gap, measured on 20 Aug 2026: every visual embed exported as a **placeholder**
(in LaTeX, a commented `\\includegraphics` next to a real caption), so the PDF had
captions and no matrices, and the same hole was in the .docx, the HTML and the
notebook.

The reason it could not be fixed here is worth restating, because it decides the
shape of the seam: **a matrix is drawn by the layout engine, and the layout engine
lives in the client** (swimlanes + the `is_after` chain + inherited membership).
Re-implementing it in Python would be a second engine that drifts from the canvas
— exactly the bug the narrative embeds had. So the client renders and names its
pictures, and this library places them.

What is defended here:

* a supplied figure turns a placeholder block into a real **image** block, and
  every renderer places it: data-URI in HTML, `add_picture` in DocX, an inline
  markdown image in the notebook, `\\includegraphics{fig/…}` in LaTeX;
* the key is (view_type, ref), so the same epoch embedded twice is ONE figure;
* **no figure = the old placeholder**, per block: the export never breaks, and
  the empty space still says why;
* the LaTeX file name and the wire key agree, and are sanitised (a node id is
  free text; `\\includegraphics` chokes on spaces and braces).
"""

from __future__ import annotations

import base64
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from s3dgraphy import api as em                                    # noqa: E402
from s3dgraphy.exporter.latex_exporter import figure_file          # noqa: E402
from s3dgraphy.narrative.bake import bake_narrative, figure_key    # noqa: E402

def png(red: int, green: int, blue: int) -> bytes:
    """A real 1×1 PNG of one colour — the smallest thing that is unmistakably
    image bytes, built rather than pasted so two figures can DIFFER.

    They have to differ for the DocX check to mean anything: Word deduplicates
    identical media, so two copies of one image land as one part in the package
    and "two figures arrived" becomes unmeasurable (found by measuring)."""
    import struct
    import zlib

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)     # 1×1, truecolour
    raw = bytes([0, red, green, blue])                          # filter + pixel
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


#: two distinct figures, so "both arrived" is measurable
PNG = png(0x33, 0x99, 0xCC)
PNG2 = png(0xCC, 0x66, 0x00)


def study() -> dict:
    """Two epochs, units, and a narrative whose chapters embed the MATRIX of
    each epoch — the shape the scaffolder makes and the one E.D. exported."""
    return {
        "header": {"format": "em.json", "version": "1.0"},
        "graph": {
            "graph_id": "pm", "name": "Porta Marina",
            "nodes": [
                {"id": "EP1", "name": "Fase repubblicana", "node_type": "EpochNode",
                 "description": "", "data": {"start_time": -200, "end_time": -50}},
                {"id": "EP2", "name": "Fase imperiale", "node_type": "EpochNode",
                 "description": "", "data": {"start_time": -50, "end_time": 200}},
                {"id": "US1", "name": "US1", "node_type": "US", "description": "",
                 "data": {}},
                {"id": "US4", "name": "US4", "node_type": "US", "description": "",
                 "data": {}},
                {"id": "NARR", "name": "Porta Marina — la storia",
                 "node_type": "narrative", "description": "Bozza.",
                 "data": {"lang": "it", "chapters": [
                     {"title": "Fase repubblicana", "anchor": "EP1", "blocks": [
                         {"block_type": "prose", "text": "Il primo impianto."},
                         {"block_type": "embed", "ref": "EP1",
                          "view_type": "matrix"}]},
                     {"title": "Fase imperiale", "anchor": "EP2", "blocks": [
                         {"block_type": "embed", "ref": "EP2",
                          "view_type": "matrix"}]},
                 ]}},
            ],
            "edges": [
                {"id": "e1", "source": "US1", "target": "EP1",
                 "edge_type": "has_first_epoch"},
                {"id": "e2", "source": "US4", "target": "EP2",
                 "edge_type": "has_first_epoch"},
            ],
        },
    }


def graph_of(doc: dict):
    graph, _warnings = em.load_emjson(doc)
    return graph


def figures_for(*refs: str) -> dict:
    """One distinct image per ref (see `png`)."""
    palette = [PNG, PNG2]
    return {figure_key("matrix", ref): palette[i % len(palette)]
            for i, ref in enumerate(refs)}


# ── the key, and the file name derived from it ───────────────────────────────

def test_the_key_is_what_is_shown_and_what_it_shows():
    assert figure_key("matrix", "EP1") == "matrix:EP1"
    assert figure_key("matrix", "EP1") == figure_key(" matrix ", " EP1 "), \
        "trimmed, so a client that pads a value still names the same figure"
    assert figure_key("map", "EP1") != figure_key("matrix", "EP1"), \
        "the same node shown two ways is two figures"


def test_the_latex_file_name_is_sanitised_and_matches_the_key():
    assert figure_file("matrix", "EP1") == "fig/matrix-EP1.pdf"
    dirty = figure_file("matrix", "US 101 {beta}/x")
    assert " " not in dirty and "{" not in dirty and "}" not in dirty, dirty
    assert dirty.startswith("fig/") and dirty.endswith(".pdf")


# ── the bake: placeholder → image ───────────────────────────────────────────

def test_without_a_figure_the_block_is_still_a_placeholder():
    baked = bake_narrative(graph_of(study()), "NARR")
    kinds = [(b.kind, b.view_type) for c in baked.chapters for b in c.blocks]
    assert ("placeholder", "matrix") in kinds
    assert ("image", "matrix") not in kinds


def test_a_supplied_figure_becomes_a_REAL_image_block():
    baked = bake_narrative(graph_of(study()), "NARR",
                          figures=figures_for("EP1", "EP2"))
    images = [b for c in baked.chapters for b in c.blocks if b.kind == "image"]
    assert len(images) == 2
    assert sorted(b.image.data for b in images) == sorted([PNG, PNG2]), \
        "each embed gets ITS figure, not the first one twice"
    for block in images:
        assert block.image is not None and block.image.resolved
        assert block.view_type == "matrix"
        assert block.meta.get("rendered_by") == "client", \
            "who drew it travels with it: a reader of the bake can tell an " \
            "author's photograph from a snapshot of the canvas"


def test_one_figure_missing_degrades_only_THAT_block():
    baked = bake_narrative(graph_of(study()), "NARR", figures=figures_for("EP1"))
    kinds = [(b.kind, b.ref) for c in baked.chapters for b in c.blocks
             if b.kind in ("image", "placeholder")]
    assert ("image", "EP1") in kinds
    assert ("placeholder", "EP2") in kinds, \
        "the export never breaks over a figure that did not render"


# ── the four renderings ─────────────────────────────────────────────────────

def test_an_svg_figure_is_declared_as_svg_xml_or_no_browser_draws_it():
    """`image/svg` is not a media type. The data URI was there and the picture
    was not — measured the first time a client-rendered figure (SVG, because that
    is what a renderer produces) reached the HTML export."""
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"></svg>'
    html = em.export_narrative_html(
        graph_of(study()), "NARR",
        figures={figure_key("matrix", "EP1"): svg}, figure_suffix=".svg")
    assert "data:image/svg+xml;base64," in html
    assert "data:image/svg;base64," not in html


def test_html_inlines_the_figure_and_stays_one_file():
    html = em.export_narrative_html(graph_of(study()), "NARR",
                                    figures=figures_for("EP1", "EP2"))
    assert html.count("data:image/png;base64,") == 2
    for data in (PNG, PNG2):
        assert base64.b64encode(data).decode() in html
    assert "<img" in html
    # single file: nothing to fetch from beside it
    assert "src=\"fig/" not in html and "<link" not in html.split("</head>")[0].replace(
        "<link rel=\"icon\"", "")


def test_the_notebook_shows_the_figure_and_keeps_its_live_query():
    text = em.export_narrative_ipynb(graph_of(study()), "NARR",
                                     figures=figures_for("EP1", "EP2"))
    nb = json.loads(text)
    md = "\n".join("".join(c["source"]) for c in nb["cells"]
                   if c["cell_type"] == "markdown")
    code = "\n".join("".join(c["source"]) for c in nb["cells"]
                     if c["cell_type"] == "code")
    assert md.count("data:image/png;base64,") == 2, "the figures are inline"
    assert "istantanea al momento dell'export" in md, \
        "…and labelled as a snapshot, because this notebook's promise is that " \
        "its cells ask the study rather than quote it"
    assert "EP1" in code and "EP2" in code, "the live query is still there"
    # a valid notebook
    assert nb["nbformat"] >= 4 and all("id" in c for c in nb["cells"])


def test_latex_includes_the_figure_when_the_caller_writes_it():
    plain = em.export_narrative_latex(graph_of(study()), "NARR")["tex"]
    assert "% \\includegraphics" in plain, "no figures supplied: placeholder"

    with_figs = em.export_narrative_latex(
        graph_of(study()), "NARR", figures=figures_for("EP1", "EP2"))["tex"]
    assert with_figs.count("\\includegraphics[width=\\linewidth]{fig/") == 2
    assert "fig/matrix-EP1.pdf" in with_figs and "fig/matrix-EP2.pdf" in with_figs
    assert "% \\includegraphics" not in with_figs, \
        "a figure that IS there must not also be offered as a comment"
    # …and one missing degrades to the placeholder, in the same document
    half = em.export_narrative_latex(graph_of(study()), "NARR",
                                     figures=figures_for("EP1"))["tex"]
    assert half.count("\\includegraphics[width=\\linewidth]{fig/") == 1
    assert "% \\includegraphics" in half


def test_docx_embeds_the_figure_as_a_picture():
    pytest.importorskip("docx", reason="python-docx is an optional extra")
    blob = em.export_narrative_docx(graph_of(study()), "NARR",
                                    figures=figures_for("EP1", "EP2"))
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        media = [n for n in zf.namelist() if n.startswith("word/media/")]
        assert len(media) == 2, f"two figures, two media parts — got {media}"
        assert sorted(zf.read(m) for m in media) == sorted([PNG, PNG2])
        document = zf.read("word/document.xml").decode("utf-8")
        assert "<w:drawing>" in document or "graphicData" in document, \
            "the picture is IN the document body, not only in the package"


def test_every_renderer_survives_a_figure_dict_full_of_nothing():
    """A client that sent an empty map, or keys nobody asked for, must not break
    an export: the figures are an offer, not a contract."""
    graph = graph_of(study())
    noise = {"matrix:NOPE": PNG, "": PNG}
    assert em.export_narrative_html(graph, "NARR", figures=noise)
    assert em.export_narrative_ipynb(graph, "NARR", figures=noise)
    assert em.export_narrative_latex(graph, "NARR", figures=noise)["tex"]
    baked = bake_narrative(graph, "NARR", figures=noise)
    kinds = {b.kind for c in baked.chapters for b in c.blocks}
    assert "image" not in kinds, "…and an unmatched key shows nothing"
