"""DTCProcessNode — a DTC PROCESS chunk: the transformation/processing event that
turns inputs into produced digital objects.

Projection: crmdig:D7_Digital_Machine_Event (⊂ prov:Activity). Its inputs/outputs
are the chain edges dtc_had_input (prov:used) / dtc_had_output (prov:generated).
"""

from .dtc_node import DTCNode


class DTCProcessNode(DTCNode):
    """DTC processing step (ECHOES DTC profile). ``dtc_kind`` ∈ the ``process``
    vocabulary (transformation / …)."""

    node_type = "dtc_process"
    dtc_base = "process"

    def __init__(self, node_id, name="Unnamed DTC process", description="",
                 dtc_kind=None, data=None):
        super().__init__(node_id, name, description=description,
                         dtc_kind=dtc_kind, data=data)
