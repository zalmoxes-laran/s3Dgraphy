"""DTCInputNode — a DTC INPUT chunk: a raw acquisition (photo set, laser scan,
topographic survey…) consumed by a processing step.

Projection: crmdig:D1_Digital_Object (⊂ prov:Entity). The specific acquisition
kind is ``data['dtc_kind']`` from the ``input`` axis of the DTC vocabulary.
"""

from .dtc_node import DTCNode


class DTCInputNode(DTCNode):
    """DTC input acquisition (ECHOES DTC profile). ``dtc_kind`` ∈ the ``input``
    vocabulary (photo / laserscanner / topographic / …)."""

    node_type = "dtc_input"
    dtc_base = "input"

    def __init__(self, node_id, name="Unnamed DTC input", description="",
                 dtc_kind=None, data=None):
        super().__init__(node_id, name, description=description,
                         dtc_kind=dtc_kind, data=data)
