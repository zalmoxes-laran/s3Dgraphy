"""
HeritageEntityNode — Heritage Entity node (HDT-O HC1).

Represents an HC1 Heritage Entity as defined in the Heritage Digital Twin
Ontology (HDT-O), ECHOES Deliverable D7.1 (May 2024): any real-world entity
socially recognized as having cultural, historical or scientific value
(heritage status is an attributed ROLE, context-dependent and dynamic).

It is the real-world referent that an HC2 Heritage Digital Twin (HDTNode) is
a digital twin OF. It completes the canonical HDT-O containment chain that
s3Dgraphy expresses:

    HC1 (HeritageEntityNode) ─HP1 has_digital_twin→ HC2 (HDTNode)
        ─HP33 contains_proposition_set→ HC16 (em:EMGraph / GraphNode)

Granularity connector (declared in s3Dgraphy_connections_datamodel.json):

* has_digital_twin  — Node → HDTNode  (HP1)  ← a HeritageEntityNode is a
  valid source (it is a Node subclass), so no new edge type is needed.

HDT-O view: this class is part of the HDT-O layer, not the stratigrapher
palette (like HDTNode / GraphNode) — it is authored in HDT-aware tooling and
projected to RDF, but does not appear in the default EM node palette.
"""
from .base_node import Node


class HeritageEntityNode(Node):
    """
    HC1 Heritage Entity (HDT-O / ECHOES D7.1).

    Attributes:
        entity_kind (str, optional): free label for the kind of heritage
            entity (e.g. "monument", "site", "landscape"). HC3 Tangible /
            HC4 Intangible specializations are deferred; this general HC1
            node covers the common case.
        authority_refs (list, optional): external authority identifiers for
            the entity (Getty TGN, Wikidata, …) — populated by the P1-D
            authority resolver when available.
    """
    node_type = "heritage_entity"

    def __init__(self, node_id, name="Unnamed Heritage Entity", description="",
                 entity_kind=None, authority_refs=None):
        super().__init__(node_id=node_id, name=name, description=description)
        self.data = {
            "entity_kind": entity_kind,
            "authority_refs": authority_refs or [],
        }

    def to_dict(self):
        return {
            "id": self.node_id,
            "type": self.node_type,
            "name": self.name,
            "description": self.description,
            "data": self.data,
        }
