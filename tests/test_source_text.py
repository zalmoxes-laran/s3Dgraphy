"""Reading the text out of a source document — StratiMiner's Path A input.

A model asked to canonise a folder of excavation sources must *see* the sources; a
filename is not a source. What these tests defend is the honesty of that reading,
because every failure here is silent by nature:

* **"not read" must not look like "says nothing".** A scanned PDF has no text
  layer. Returning ``""`` would present it to the model as an empty document, and
  the model would faithfully record that the source contains nothing.
* **a missing optional dependency is not an error.** Without the ``[pdf]`` extra,
  a PDF reports why it was not read and Path A degrades to filenames. That is a
  valid request this build cannot serve, and the caller has to be able to say so.
* **one bad file must not cost the folder.** Nothing here raises: a corrupt PDF, an
  unreadable file, an unknown format all come back as a note.

The PDF fixtures are BUILT here, in ~20 lines, rather than committed as binaries:
a PDF is text, so the fixture stays legible in a diff and cannot go missing.
"""

from __future__ import annotations

import importlib.util
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from s3dgraphy import api  # noqa: E402
from s3dgraphy.importer import source_text as st  # noqa: E402

pypdf_missing = pytest.mark.skipif(
    importlib.util.find_spec("pypdf") is None,
    reason="pypdf not installed (the [pdf] extra)")


def _make_pdf(text: str | None) -> bytes:
    """A minimal, valid one-page PDF. With ``text`` it has a text layer; with
    ``None`` it has a page and no text — which is what a scan looks like to an
    extractor."""
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    content = f"BT /F1 12 Tf 20 120 Td ({text}) Tj ET" if text else ""
    objects.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = io.StringIO()
    out.write("%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{index} 0 obj\n{body}\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n")
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n")
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
              f"startxref\n{xref}\n%%EOF\n")
    return out.getvalue().encode("latin-1")


def _hide_pypdf(monkeypatch):
    """Make pypdf unimportable, to exercise the build that has no extractor."""
    real = importlib.util.find_spec

    def find_spec(name, *args, **kwargs):
        if name == "pypdf":
            return None
        return real(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", find_spec)
    monkeypatch.setitem(sys.modules, "pypdf", None)


# ── plain text ────────────────────────────────────────────────────────────────

def test_plain_text_is_read(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("US 1 overlies US 2.", encoding="utf-8")
    out = api.source_text(str(path))
    assert out["kind"] == "text"
    assert out["text"] == "US 1 overlies US 2."
    assert out["note"] == ""


def test_truncation_is_reported_not_hidden(tmp_path):
    """A silently truncated source is a source the model read half of while
    believing it read all of."""
    path = tmp_path / "long.txt"
    path.write_text("x" * 500, encoding="utf-8")
    out = api.source_text(str(path), max_chars=100)
    assert len(out["text"]) == 100
    assert "truncated" in out["note"]


def test_an_unsupported_format_names_itself(tmp_path):
    path = tmp_path / "photo.tiff"
    path.write_bytes(b"II*\x00")
    out = api.source_text(str(path))
    assert out["text"] is None
    assert out["kind"] == "unsupported"
    assert ".tiff" in out["note"]


def test_a_missing_file_is_a_note_not_an_exception(tmp_path):
    """The caller is cataloguing a folder; a file that vanished between listing and
    reading must not abort the other nineteen."""
    out = api.source_text(str(tmp_path / "gone.txt"))
    assert out["text"] is None
    assert out["note"]


# ── PDF, with the extractor ───────────────────────────────────────────────────

@pypdf_missing
def test_a_pdf_text_layer_is_read(tmp_path):
    path = tmp_path / "report.pdf"
    path.write_bytes(_make_pdf("US 1 overlies US 2 - Roman phase"))
    out = api.source_text(str(path))
    assert out["kind"] == "pdf"
    assert "overlies" in out["text"]
    # The page number travels with the text: a claim extracted from a report is
    # worth more when the extractor can say which page it came from.
    assert "[p. 1]" in out["text"]


@pypdf_missing
def test_a_pdf_without_a_text_layer_says_scan_not_nothing(tmp_path):
    """The distinction this module exists for.

    An image-only PDF yields no characters. Returning ``""`` would hand the model
    an empty document and it would dutifully record that the source says nothing —
    an invented absence, which is exactly the error the whole reviewable-table
    design is meant to prevent.
    """
    path = tmp_path / "scan.pdf"
    path.write_bytes(_make_pdf(None))
    out = api.source_text(str(path))
    assert out["text"] is None
    assert "scan" in out["note"].lower()
    assert "ocr" in out["note"].lower()


@pypdf_missing
def test_a_corrupt_pdf_is_named_not_raised(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4\nthis is not a pdf body")
    out = api.source_text(str(path))
    assert out["text"] is None
    assert out["kind"] == "pdf"
    assert out["note"]


@pypdf_missing
def test_the_extractor_is_named_with_its_version():
    """Two extractors disagree about hyphenation and column order, so a table that
    came out oddly should be traceable to whatever read the page."""
    assert api.pdf_text_available() is True
    name = api.source_text_extractor()
    assert name and name.startswith("pypdf")


# ── PDF, without the extractor: the degradation ───────────────────────────────

def test_without_the_extractor_a_pdf_degrades_to_a_note(tmp_path, monkeypatch):
    """No exception, no empty string: a note naming the extra.

    This is the whole shape of the decision — pypdf is optional, PyMuPDF is not
    bundled, and a build without either still runs Path A on the filenames.
    """
    _hide_pypdf(monkeypatch)
    path = tmp_path / "report.pdf"
    path.write_bytes(_make_pdf("US 1 overlies US 2"))
    out = st.source_text(str(path))
    assert out["text"] is None
    assert out["kind"] == "pdf"
    assert "[pdf]" in out["note"] or "pdf]" in out["note"]
    assert "extractor" in out["note"]


def test_pdf_availability_is_askable_before_the_work(monkeypatch):
    """A caller must be able to warn ONCE, up front — "PDFs will be listed by name
    only" — rather than repeating itself per file."""
    _hide_pypdf(monkeypatch)
    assert st.pdf_text_available() is False
    assert st.extractor_name() is None


def test_plain_text_still_works_without_the_extractor(tmp_path, monkeypatch):
    """The extra is for PDFs alone: hiding it must not disturb the rest."""
    _hide_pypdf(monkeypatch)
    path = tmp_path / "notes.txt"
    path.write_text("US 1.", encoding="utf-8")
    assert st.source_text(str(path))["text"] == "US 1."


# ── the policy lives here, not in the callers ─────────────────────────────────

def test_the_suffix_policy_is_the_library_s(tmp_path):
    """em-bridge used to keep its own list of readable suffixes. Two lists become
    two policies, and the one nobody tests is the one that drifts."""
    assert ".md" in st.PLAIN_TEXT_SUFFIXES
    assert ".pdf" in st.PDF_SUFFIXES
    assert ".pdf" not in st.PLAIN_TEXT_SUFFIXES


def test_source_text_never_raises_on_anything_in_a_folder(tmp_path):
    """Swept over a hostile folder: a directory, an empty file, an unknown suffix,
    a broken symlink. The contract is that a catalogue always completes."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "empty.txt").write_text("", encoding="utf-8")
    (tmp_path / "odd.xyz").write_bytes(b"\x00\x01")
    os.symlink(tmp_path / "nowhere", tmp_path / "dangling.txt")
    for entry in sorted(os.listdir(tmp_path)):
        out = api.source_text(str(tmp_path / entry))
        assert set(out) == {"text", "kind", "note"}
