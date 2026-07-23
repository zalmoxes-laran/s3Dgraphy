"""
StudyNode — Study node (HDT-O HC9).

Represents an HC9 Study (HDT-O, ECHOES D7.1): a scholarly activity — research,
analysis or documentation, in any SSH / natural / exact-science domain — about
a Heritage Entity (HC1), explicating a disciplinary focus and the part of the
entity investigated. A study always results in documentary outputs that
contribute to the content of an HDT; in EM terms a study heads an EM
proposition set (HC16 / em:EMGraph).

Canonical HDT-O framing used by s3Dgraphy:

    Project (HC13) ─includes(crm:P9)→ Study (HC9)
    Study   (HC9)  ─was_about(HP23)→ HeritageEntity (HC1)
    Study   (HC9)  ─produced(HP25)→ GraphNode (HC16 / em:EMGraph)

HDT-O view: gated out of the stratigrapher palette (like HDTNode / GraphNode /
HeritageEntityNode); authored in HDT-aware tooling and projected to RDF.
"""
from .base_node import Node


class StudyNode(Node):
    """
    HC9 Study (HDT-O / ECHOES D7.1).

    Attributes:
        disciplinary_focus (str, optional): the disciplinary aspect under which
            the study investigated the entity (HDT-O HP24 → crm:E55 Type).
        project_iri (str, optional): IRI of the HC13 Project this study is part
            of, when authored standalone.
    """
    node_type = "study"

    def __init__(self, node_id, name="Unnamed Study", description="",
                 disciplinary_focus=None, project_iri=None):
        super().__init__(node_id=node_id, name=name, description=description)
        self.data = {
            "disciplinary_focus": disciplinary_focus,
            "project_iri": project_iri,
        }

    def to_dict(self):
        return {
            "id": self.node_id,
            "type": self.node_type,
            "name": self.name,
            "description": self.description,
            "data": self.data,
        }
