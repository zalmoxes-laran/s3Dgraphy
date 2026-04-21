import re

from .paradata_node import ParadataNode
from ..utils.utils import get_document_vocabularies


# Canonical vocabularies for the two-axis Master-Document classification
# (EM 1.5.4+). Derived from ``em_visual_rules.json → document_variant_styles``
# so the JSON remains the single source of truth — add a variant there to
# extend constructor validation, dialog dropdowns, and renderer styling
# in one shot.
DOCUMENT_ROLES, DOCUMENT_SPATIAL_CONFIDENCES = get_document_vocabularies()


class DocumentNode(ParadataNode):
    """
    Represents a document or source attached to the graph.

    Two orthogonal axes classify a Master Document:

    1. ``role`` — is the document *about* this context (``analytical``)
       or does it provide external comparison material (``comparative``,
       e.g. the facade of another temple used as a reference model)?
    2. ``spatial_confidence`` — only meaningful for analytical documents,
       expresses how confident we are that the document can be placed in
       space relative to this context:

       - ``photogrammetric`` — camera-calibrated, metrically verifiable.
       - ``observable``      — positioned via landmarks internal to the
         document (manual but criterion-based; residual uncertainty).
       - ``asserted``        — operator-attributed; the document (e.g. a
         drawing) is not metrically correct, position is fluid.

    The renderer maps these to border colours (red / orange / yellow for
    analytical by descending certainty, green for comparative) via
    ``em_visual_rules.json``. The resolver does not consume them — they
    are metadata for humans and diagnostic UIs.

    Legacy convention (D.0-999 = analytical, D.1000+ = comparative) is
    honoured as a **fallback** by :meth:`effective_role` when neither
    attribute is set explicitly.

    Attributes:
        data (dict): Additional metadata. Canonical keys:

            - ``url`` / ``url_type`` — legacy
            - ``role`` ∈ :data:`DOCUMENT_ROLES` or None
            - ``spatial_confidence`` ∈ :data:`DOCUMENT_SPATIAL_CONFIDENCES`
              or None (must be None when role='comparative')
    """

    node_type = "document"

    _LEGACY_ID_RE = re.compile(r'^D\.(\d+)(?:\.|$)')
    _COMPARATIVE_ID_THRESHOLD = 1000

    def __init__(self, node_id, name, description="", url=None, data=None,
                 role=None, spatial_confidence=None):
        super().__init__(node_id, name, description=description, url=url)
        self.data = data if data is not None else {}
        if role is not None:
            if role not in DOCUMENT_ROLES:
                raise ValueError(
                    f"DocumentNode role must be one of {DOCUMENT_ROLES} "
                    f"or None, got {role!r}")
            self.data["role"] = role
        if spatial_confidence is not None:
            if spatial_confidence not in DOCUMENT_SPATIAL_CONFIDENCES:
                raise ValueError(
                    f"DocumentNode spatial_confidence must be one of "
                    f"{DOCUMENT_SPATIAL_CONFIDENCES} or None, got "
                    f"{spatial_confidence!r}")
            # Invariant: comparative documents do not carry a spatial
            # confidence — the document has its own geometry, the
            # "spatial placement" concept does not apply.
            if self.data.get("role") == "comparative":
                raise ValueError(
                    "DocumentNode with role='comparative' cannot carry a "
                    "spatial_confidence value")
            self.data["spatial_confidence"] = spatial_confidence

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

    def effective_spatial_confidence(self):
        """Return the canonical spatial_confidence, or ``None`` when
        comparative / unset. Applies the role invariant automatically.
        """
        if self.effective_role() == "comparative":
            return None
        v = self.data.get("spatial_confidence")
        return v if v in DOCUMENT_SPATIAL_CONFIDENCES else None

    def variant_style_key(self) -> str:
        """Return the lookup key for
        :func:`em_visual_rules.json → document_variant_styles`.

        Composite key ``"role.spatial_confidence"`` for analytical
        documents, just ``"comparative"`` for comparative, and
        ``"default"`` when neither axis resolves to a known value.
        """
        role = self.effective_role()
        if role == "comparative":
            return "comparative"
        sc = self.effective_spatial_confidence()
        if sc is None:
            return "default"
        return f"analytical.{sc}"
