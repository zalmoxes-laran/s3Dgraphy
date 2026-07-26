"""DTCNode — abstract base for the DTC substrate profile (ECHOES deliverable).

The **Digital Twin Chain (DTC)** captures the DIGITAL PROVENANCE that *produces*
documents: input **Resources** (raw acquisitions) → a **Process** event →
output **Resources** (produced files: mesh/orthophoto/table…). It is distinct
from EM-paradata (interpretation *on* a document = CRMinf / HDT-O HC17): DTC is
about how the digital objects came to be.

Both the INPUT and the OUTPUT are **Resources** (the EM ``LinkNode``, E73/D1 —
the shared hinge a RepresentationModel and/or a Document may reference), NOT
dedicated node classes: so :class:`DTCProcessNode` is the ONLY DTC node class.
The DTC graph = Resources connected by Process events: the process links to its
input/output Resources via the ``dtc_had_input`` / ``dtc_had_output`` edges (target
LinkNode); an output Resource ``dtc_derived_from`` an input Resource. (An earlier
form had DTCInputNode/DTCOutputNode classes — both retired.)

Naming (Option A): EM-native ``...Node`` class; the CIDOC/CRMdig + PROV-O mapping
lives in ``em_extension`` (no D-numbers in the UI). Gated out of the stratigrapher
palette (like the HDT-O nodes). One node = a **Chunk**; the assembled provenance
= a **Chain**.

The process (and each participating Resource) carries a ``dtc_kind`` — a specific
kind drawn from a DATA-DRIVEN, expandable vocabulary (``dtc_kinds`` in
``em_visual_rules.json``, read via :func:`s3dgraphy.utils.get_dtc_kinds`): adding a
new kind (audio, spectroscopy…) is a JSON entry (+ a glyph), NOT a code change.

EM commons are REUSED, never duplicated: Author (agent), License, Embargo, and
LinkNode (the Resource itself) attach to the chain via the existing
``has_author`` / ``has_license`` / ``has_embargo`` / ``has_linked_resource`` edges.
"""

from .base_node import Node
from ..utils.utils import get_dtc_kinds

# {"input": (...), "process": (...), "output": (...)} — the single source of
# truth for per-kind validation; extend it in em_visual_rules.json, not here.
DTC_KINDS = get_dtc_kinds()


class DTCNode(Node):
    """Abstract base for a DTC chain chunk. Concrete subclasses set ``node_type``
    and ``dtc_base`` (which vocabulary axis in ``dtc_kinds`` validates ``dtc_kind``).
    Not instantiated directly and not in the stratigrapher palette."""

    node_type = None  # abstract — concrete subclasses define it
    dtc_base = None    # "input" | "process" | "output"

    def __init__(self, node_id, name, description="", dtc_kind=None, data=None):
        super().__init__(node_id=node_id, name=name, description=description)
        self.data = data if data is not None else {}
        if dtc_kind is not None:
            allowed = DTC_KINDS.get(self.dtc_base, ())
            if dtc_kind not in allowed:
                raise ValueError(
                    f"{type(self).__name__} dtc_kind must be one of {allowed} "
                    f"or None, got {dtc_kind!r}")
            self.data["dtc_kind"] = dtc_kind

    def to_dict(self):
        return {
            "id": self.node_id,
            "type": self.node_type,
            "name": self.name,
            "description": self.description,
            "data": self.data,
        }
