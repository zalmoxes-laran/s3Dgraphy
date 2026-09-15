"""DTCNode — abstract base for the DTC substrate profile (ECHOES deliverable).

The **Data Transformation Chain (DTC)** captures the DIGITAL PROVENANCE that *produces*
documents: input **Resources** (raw acquisitions) → a **Process** event →
output **Resources** (produced files: mesh/orthophoto/table…). It is distinct
from EM-paradata (interpretation *on* a document = CRMinf / HDT-O HC17): DTC is
about how the digital objects came to be.

Both the INPUT and the OUTPUT are **Resources** (the EM ``ResourceNode``, E73/D1 —
the shared hinge a RepresentationModel and/or a Document may reference) and NOT
dedicated node classes — that is what DTCInputNode and DTCOutputNode were, and
both are retired. The DTC graph = Resources connected by EVENTS: the event links
to its input/output Resources via the ``dtc_had_input`` / ``dtc_had_output``
edges (target ResourceNode); an output Resource ``dtc_derived_from`` an input
Resource.

**The concrete event classes are TWO**, and this line used to say one:
:class:`DTCProcessNode` (crmdig:D7, a transformation) and
:class:`DTCAcquisitionNode` (crmdig:D12, the moment material enters a study).
The sentence was true the day it was written — it was recording the retirement
of the two Resource classes above — and then the acquisition arrived and nobody
came back to it. **It has already produced a wrong specification**: a reader
building on «the only DTC node class» treats an acquisition as a file without a
digest, and the ``from`` entry's ``kind: "acquisition"`` exists precisely because
it is not one. Count the subclasses of :class:`DTCNode` rather than trusting a
sentence — including this one.

Naming (Option A): EM-native ``...Node`` class; the CIDOC/CRMdig + PROV-O mapping
lives in ``em_extension`` (no D-numbers in the UI). Gated out of the stratigrapher
palette (like the HDT-O nodes). **Three referents, three words**: the **chain**
is the whole, a **step** is the single transformation, and a **stamp** is the file
that records one — *a stamp attests one step of a chain*. One node here is one
**step**. («Chunk» was the word before, and it named the same thing; it is gone
because a reader needed a glossary to know that a chunk and a step were not two
different things.)

The process (and each participating Resource) carries a ``dtc_kind`` — a specific
kind drawn from a DATA-DRIVEN, expandable vocabulary (``dtc_kinds`` in
``em_visual_rules.json``, read via :func:`s3dgraphy.utils.get_dtc_kinds`): adding a
new kind (audio, spectroscopy…) is a JSON entry (+ a glyph), NOT a code change.

EM commons are REUSED, never duplicated: Author (agent), License, Embargo, and
ResourceNode (the Resource itself) attach to the chain via the existing
``has_author`` / ``has_license`` / ``has_embargo`` / ``has_linked_resource`` edges.
"""

from .base_node import Node
from ..utils.utils import get_dtc_kinds

# {"input": (...), "process": (...), "output": (...)} — the single source of
# truth for per-kind validation; extend it in em_visual_rules.json, not here.
DTC_KINDS = get_dtc_kinds()


class DTCNode(Node):
    """Abstract base for one STEP of a DTC chain. Concrete subclasses set ``node_type``
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
