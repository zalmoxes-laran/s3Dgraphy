"""DTCAcquisitionNode — a DTC ACQUISITION chunk: the digital event by which an
asset ENTERS this study from an (opaque, Tier-0) external source.

Distinct from :class:`DTCProcessNode` (genesis/transformation, crmdig:D7): an
acquisition is a **data-transfer / ingestion** event —
``crmdig:D12_Data_Transfer_Event`` (⊂ D7 ⊂ prov:Activity), "events that transfer a
digital object from one digital carrier to another; normally the digital object
remains the same" — i.e. the object arrives opaque, no genesis is asserted. This
keeps *genesis ≠ acquisition* as distinct TYPES inside the one DTC substrate
(design decision §2/§3).

Tier 0: the chain has a single ring — the acquisition event ─dtc_had_output→ the
acquired Resource (ResourceNode). The upstream root is an opaque external entity,
recorded as literals on ``data`` (repo/record/agent/retrieved_at/rights), not as a
genesis sub-graph. ``dtc_kind`` ∈ the ``acquisition`` axis of ``dtc_kinds``.
"""

from .dtc_node import DTCNode


class DTCAcquisitionNode(DTCNode):
    """DTC acquisition/ingestion event (ECHOES DTC profile, acquisition seam).
    ``dtc_kind`` ∈ the ``acquisition`` vocabulary (download / ingest / local_import)."""

    node_type = "dtc_acquisition"
    dtc_base = "acquisition"

    def __init__(self, node_id, name="Acquisition", description="",
                 dtc_kind=None, data=None):
        super().__init__(node_id, name, description=description,
                         dtc_kind=dtc_kind, data=data)
