"""DTCOutputNode — a DTC OUTPUT chunk: a produced digital object / document
(point cloud, mesh, DEM, orthophoto, vector features…).

Projection: crmdig:D1_Digital_Object (⊂ prov:Entity). Reuses the EM LinkNode
(via has_linked_resource / crm:P67) to point at its real file — future: a MinIO
asset id. The model does NOT preclude a later shared-UUID identity with the EM
DocumentNode (both are digital objects); that seam is a later slice.
"""

from .dtc_node import DTCNode


class DTCOutputNode(DTCNode):
    """DTC produced digital object (ECHOES DTC profile). ``dtc_kind`` ∈ the
    ``output`` vocabulary (pointcloud / mesh / dem / orthophoto / points /
    lines / polygons / …)."""

    node_type = "dtc_output"
    dtc_base = "output"

    def __init__(self, node_id, name="Unnamed DTC output", description="",
                 dtc_kind=None, data=None):
        super().__init__(node_id, name, description=description,
                         dtc_kind=dtc_kind, data=data)
