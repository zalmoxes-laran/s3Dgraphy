"""
ProjectNode — Project node (HDT-O HC13).

Represents an HC13 Project (HDT-O, ECHOES D7.1): the coordinated activities of
institutions or research groups to produce heritage-related outcomes. A project
provides the organizational context under which studies are carried out and
under which HDTs are created, updated and curated (HC11 Digital Twin
Maintenance activities are "carried out under" a project, HP20).

Canonical framing used by s3Dgraphy:

    Project (HC13) ─includes(crm:P9)→ Study (HC9)

D7.1 defines no direct HC13→HC9 property, so the containment uses CIDOC-CRM
`crm:P9_consists_of` (activity/period composition) via the extension mechanism
— consistent with HP20 itself being declared a subproperty of `crm:P9i`.

HDT-O view: gated out of the stratigrapher palette; authored in HDT-aware
tooling and projected to RDF.
"""
from .base_node import Node


class ProjectNode(Node):
    """
    HC13 Project (HDT-O / ECHOES D7.1).

    Attributes:
        funding (str, optional): free label for the funding / programme context.
        timespan (str, optional): ISO-8601 range for the project's activity.
    """
    node_type = "project"

    def __init__(self, node_id, name="Unnamed Project", description="",
                 funding=None, timespan=None):
        super().__init__(node_id=node_id, name=name, description=description)
        self.data = {
            "funding": funding,
            "timespan": timespan,
        }

    def to_dict(self):
        return {
            "id": self.node_id,
            "type": self.node_type,
            "name": self.name,
            "description": self.description,
            "data": self.data,
        }
