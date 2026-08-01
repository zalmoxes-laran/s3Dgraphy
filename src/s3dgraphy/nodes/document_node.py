import re

from .paradata_node import ParadataNode
from ..utils.utils import get_document_vocabularies


# Canonical vocabularies for the three-axis Master-Document classification
# (EM 1.6). Derived from ``em_visual_rules.json`` so the JSON remains the
# single source of truth — add or remove a value there to extend the
# constructor validation, dialog dropdowns, and renderer styling in one
# shot.
#
#   Axis 1 — role             (analytical / comparative)
#   Axis 2 — content_nature   (2d_object / 3d_object)
#   Axis 3 — geometry         (reality_based / observable / asserted
#                              / None when the document has no RM)
DOCUMENT_ROLES, DOCUMENT_CONTENT_NATURES, DOCUMENT_GEOMETRIES = \
    get_document_vocabularies()


#: Attribute keys carrying the canonical-document flag. The first two are
#: current, the last two are the pre-rename ("master") spelling: read for
#: backward compatibility, never written. See :meth:`DocumentNode.is_canonical`.
CANONICAL_FLAG = "is_canonical"
CANONICAL_DOCUMENT_FLAG = "em_canonical_document"
LEGACY_CANONICAL_FLAG = "is_master"
LEGACY_CANONICAL_DOCUMENT_FLAG = "em_master_document"

#: style key for a canonical document with no geometry classification
CANONICAL_UNKNOWN_STYLE = "canonical_unknown"


def normalise_canonical_attributes(attrs: dict) -> dict:
    """Rewrite the legacy ``master`` flags to their canonical spelling, in place.

    Applied when a document is read, so the in-memory graph speaks one language
    regardless of which version wrote the file. Nothing is lost: the legacy key
    is removed only after its value has been carried over."""
    if not isinstance(attrs, dict):
        return attrs
    for legacy, current in ((LEGACY_CANONICAL_FLAG, CANONICAL_FLAG),
                            (LEGACY_CANONICAL_DOCUMENT_FLAG, CANONICAL_DOCUMENT_FLAG)):
        if legacy in attrs:
            value = attrs.pop(legacy)
            attrs.setdefault(current, value)
    return attrs


class DocumentNode(ParadataNode):
    """Represents a document in the Extended Matrix.

    Every document is a *functional wrapper* — elevating an entity to
    document status makes it operationalizable for information extraction
    via Extractor nodes.

    A document is classified along three orthogonal axes:

    1. ``role`` — how this document participates in the reconstructive
       reasoning: ``analytical`` (primary source about this context)
       or ``comparative`` (external reference / analogy — e.g. the
       facade of another temple used as a model).

    2. ``content_nature`` — what the document is: ``2d_object``
       (image, drawing, photograph, text) or ``3d_object`` (mesh,
       laser scan, photogrammetric model).

    3. ``geometry`` — how the document's Representation Model (RM) is
       spatialized in the 3D scene:

       - ``reality_based``  — sensor / algorithmic positioning
         (photogrammetry, calibrated photo sequence, instrumentally
         surveyed find).
       - ``observable``     — reconstructed from rigorous archaeological
         documentation (plans, sections). Criterion-based, residual
         uncertainty.
       - ``asserted``       — compositional positioning asserted by the
         operator, without claim of restitution.
       - ``None``           — the document has no RM (e.g. a PDF
         article, a bibliography); the ``geometry`` node is simply
         absent from the graph.

    The renderer maps ``geometry`` to border colours (red / orange /
    yellow) via ``em_visual_rules.json``. ``role`` and
    ``content_nature`` are metadata only — they do not drive visuals.

    Legacy convention (``D.NNN`` with ``NNN >= 1000`` → comparative)
    is honoured as a **fallback** by :meth:`effective_role` when no
    explicit attribute is set.
    """

    node_type = "document"

    _LEGACY_ID_RE = re.compile(r'^D\.(\d+)(?:\.|$)')
    _COMPARATIVE_ID_THRESHOLD = 1000

    def __init__(self, node_id, name, description="", url=None, data=None,
                 role=None, content_nature=None, geometry=None):
        super().__init__(node_id, name, description=description, url=url)
        self.data = data if data is not None else {}
        if role is not None:
            if role not in DOCUMENT_ROLES:
                raise ValueError(
                    f"DocumentNode role must be one of {DOCUMENT_ROLES} "
                    f"or None, got {role!r}")
            self.data["role"] = role
        if content_nature is not None:
            if content_nature not in DOCUMENT_CONTENT_NATURES:
                raise ValueError(
                    f"DocumentNode content_nature must be one of "
                    f"{DOCUMENT_CONTENT_NATURES} or None, got "
                    f"{content_nature!r}")
            self.data["content_nature"] = content_nature
        if geometry is not None:
            if geometry not in DOCUMENT_GEOMETRIES:
                raise ValueError(
                    f"DocumentNode geometry must be one of "
                    f"{DOCUMENT_GEOMETRIES} or None, got {geometry!r}")
            self.data["geometry"] = geometry

    # ------------------------------------------------------------------
    # Effective classification (explicit attribute → fallback to legacy
    # numbering convention → analytical)
    # ------------------------------------------------------------------

    def effective_role(self) -> str:
        """Return the canonical role for this node.

        Explicit ``data['role']`` wins; otherwise the legacy numbering
        convention is applied (``D.NNN`` with ``NNN >= 1000`` →
        ``comparative``); final fallback is ``analytical``.
        """
        explicit = self.data.get("role")
        if explicit in DOCUMENT_ROLES:
            return explicit
        m = self._LEGACY_ID_RE.match(self.name or "")
        if m and int(m.group(1)) >= self._COMPARATIVE_ID_THRESHOLD:
            return "comparative"
        return "analytical"

    def effective_content_nature(self):
        """Return ``data['content_nature']`` when set, else ``None``.

        No legacy fallback — older graphs simply have no declared
        content nature.
        """
        v = self.data.get("content_nature")
        return v if v in DOCUMENT_CONTENT_NATURES else None

    def effective_geometry(self):
        """Return ``data['geometry']`` when set, else ``None``.

        A ``None`` return means the document has no Representation
        Model — the renderer omits the border-colour variant and any
        downstream RM viewport styling.
        """
        v = self.data.get("geometry")
        return v if v in DOCUMENT_GEOMETRIES else None

    def is_canonical(self) -> bool:
        """True when this node is the CANONICAL document rather than one of its
        use-instances.

        Naming (EM 1.6, renamed from "master" in schema 2): every digital
        document is a copy — there is no "original" among them — so "master" was
        misleading. What the flag actually distinguishes is the document node
        drawn at its own moment of creation, the **canonical** one, from the
        instances that re-use it in other contexts.

        Four attribute keys are honoured, and any of them being truthy is
        enough:

        - ``is_canonical``          — current key, set by the GraphML importer
          when the source node had a thick coloured border in yEd;
        - ``em_canonical_document`` — current key, set when a canonical document
          is authored from a tool (EM-blender-tools' helper), and the flag the
          GraphML patcher reads to decide whether to write a fresh DocumentNode;
        - ``is_master`` / ``em_master_document`` — **legacy**, the same two keys
          before the rename. Read, never written: a document saved by an older
          version keeps working, and is normalised on import.

        Both ``attributes`` and ``data`` are consulted, because the flag lands in
        either depending on where the node came from: the GraphML importer sets
        it as an attribute, while the em.json round-trip carries it in ``data``
        (the exporter lifts attributes into data, the importer reads them back
        there). Asking one and not the other would make a document canonical on
        one path and an instance on the other.
        """
        for store in (self.attributes, self.data):
            if not isinstance(store, dict):
                continue
            if any(store.get(k, False) for k in (CANONICAL_FLAG,
                                                 CANONICAL_DOCUMENT_FLAG,
                                                 LEGACY_CANONICAL_FLAG,
                                                 LEGACY_CANONICAL_DOCUMENT_FLAG)):
                return True
        return False

    def variant_style_key(self) -> str:
        """Return the lookup key for
        :func:`em_visual_rules.json → document_variant_styles`.

        Border *width* encodes the canonical/instance distinction; border
        *colour* encodes the geometry-axis sub-classification. The
        priorities here are:

        - ``geometry`` set (and recognised)   → that geometry key,
          which yields a *thick* coloured border (canonical).
        - canonical but no geometry           → ``"canonical_unknown"``,
          a thick *black* border that still reads as canonical in yEd
          and in :func:`_is_canonical_document` (width-based recognizer).
        - otherwise                           → ``"default"``, a thin
          black border (an instance / non-canonical document).
        """
        g = self.effective_geometry()
        if g is not None:
            return g
        return CANONICAL_UNKNOWN_STYLE if self.is_canonical() else "default"
