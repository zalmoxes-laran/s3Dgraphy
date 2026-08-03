"""Reading the TEXT out of a source document, for StratiMiner's Path A.

Path A asks a model to canonise a folder of excavation sources into
``em_data.xlsx``. For that the model has to *see* the sources — and a filename is
not a source. This module answers one question, for one file: **what does it say,
or why can we not tell?**

**Why it lives in s3Dgraphy and not in em-bridge.** The suffix policy and the
extraction are the same wherever StratiMiner runs — the bridge, EMtools, a script —
and a rule kept in the caller becomes three rules that disagree. It is also testable
here without an HTTP server.

**pypdf, and why not PyMuPDF** (E.D., 2026-08-03). PyMuPDF renders beautifully and
weighs **21 MB**; the frozen em-bridge sidecar would carry all of it to read some
paragraphs. pypdf is **~350 KB**, pure Python, no compiled extension and no
dependencies — which also means it installs next to Blender's interpreter without a
build. It extracts the text layer, which is exactly what is wanted; it does NOT do
OCR, so a scanned PDF has no text to give and says so rather than returning an
empty string that reads like an empty document.

**Optional and lazy**, declared as the ``[pdf]`` extra. Absent, this module still
works: PDFs report that their text was not read, and Path A degrades to the
filenames — which is what it did before, with the difference that now it says why.
That degradation is the point. A missing optional dependency must never be an
error: the request was valid, this build cannot serve it.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

#: Suffixes read straight off disk as text. Deliberately a list of formats whose
#: bytes ARE their content — a model reading raw HTML or CSV loses nothing that
#: matters for canonisation, and pretending to parse them would add failure modes
#: for no gain.
PLAIN_TEXT_SUFFIXES: Tuple[str, ...] = (
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".xml",
    ".html", ".htm", ".rst", ".yaml", ".yml", ".log",
)

#: Suffixes that need an extractor to yield text.
PDF_SUFFIXES: Tuple[str, ...] = (".pdf",)

#: Read at most this much per file unless the caller says otherwise. An
#: excavation report is not a corpus, and an unbounded read turns one folder into
#: an unbounded prompt.
DEFAULT_MAX_CHARS = 200_000


def pdf_text_available() -> bool:
    """True when this build can read a PDF's text.

    Exposed so a caller can warn ONCE, up front — "PDFs in this folder will be
    listed by name only" — instead of repeating itself per file. A single honest
    sentence before the work is worth more than twenty notes after it.
    """
    try:
        import pypdf  # noqa: F401
        return True
    except ImportError:
        return False


def extractor_name() -> Optional[str]:
    """Which extractor is in use, with its version, or ``None``.

    Named in the report because "the text was read" is not one fact: two
    extractors disagree about column order, ligatures and hyphenation, and a
    canonisation that came out differently should be traceable to the thing that
    read the page.
    """
    try:
        import pypdf
    except ImportError:
        return None
    return f"pypdf {getattr(pypdf, '__version__', '?')}"


def _pdf_text(path: str, max_chars: int) -> Dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return {
            "text": None,
            "kind": "pdf",
            "note": "PDF text not read — this build has no PDF extractor "
                    "(install the extra: pip install 's3dgraphy[pdf]')",
        }
    try:
        reader = PdfReader(path)
    except Exception as exc:
        # A corrupt or encrypted PDF is the user's file, not a bug here. Named
        # rather than raised: one bad document must not stop a folder.
        return {"text": None, "kind": "pdf",
                "note": f"PDF could not be opened: {exc}"}

    chunks = []
    total = 0
    truncated = False
    for index, page in enumerate(reader.pages):
        try:
            piece = page.extract_text() or ""
        except Exception:
            # Per PAGE, not per document: a single malformed page should cost
            # that page, not the whole report.
            continue
        if not piece.strip():
            continue
        remaining = max_chars - total
        if remaining <= 0:
            truncated = True
            break
        if len(piece) > remaining:
            piece = piece[:remaining]
            truncated = True
        chunks.append(f"[p. {index + 1}]\n{piece}")
        total += len(piece)
        if truncated:
            break

    if not chunks:
        # The distinction that matters: a PDF with no text layer is a SCAN, and
        # returning "" would read as "this document says nothing". It needs OCR,
        # which is a different tool and a different decision.
        return {
            "text": None,
            "kind": "pdf",
            "note": "no text layer — this looks like a scan; reading it would "
                    "need OCR, which this build does not do",
        }
    note = ""
    if truncated:
        note = f"truncated at {max_chars} characters"
    return {"text": "\n\n".join(chunks), "kind": "pdf", "note": note}


def source_text(path: str, *, max_chars: int = DEFAULT_MAX_CHARS
                ) -> Dict[str, Any]:
    """What a source file says, or why it cannot be read.

    Returns ``{"text": str | None, "kind": str, "note": str}`` where ``kind`` is
    ``text``, ``pdf`` or ``unsupported``. **Never raises** for a file it cannot
    read: the caller is assembling a catalogue of a whole folder, and one
    unreadable document must not cost the other twenty.

    ``text is None`` always comes with a ``note`` saying why — that note is what
    the prompt shows the model so it does not invent the contents of a file
    nobody read.
    """
    suffix = os.path.splitext(path)[1].lower()
    if suffix in PDF_SUFFIXES:
        return _pdf_text(path, max_chars)
    if suffix in PLAIN_TEXT_SUFFIXES:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read(max_chars + 1)
        except OSError as exc:
            return {"text": None, "kind": "text",
                    "note": f"could not be read: {exc}"}
        if len(text) > max_chars:
            return {"text": text[:max_chars], "kind": "text",
                    "note": f"truncated at {max_chars} characters"}
        return {"text": text, "kind": "text", "note": ""}
    return {
        "text": None,
        "kind": "unsupported",
        "note": f"{suffix or 'no extension'} is not a readable source format "
                f"(text: {', '.join(PLAIN_TEXT_SUFFIXES)}; plus PDF with the "
                f"[pdf] extra)",
    }
