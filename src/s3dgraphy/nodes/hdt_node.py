"""
HDTNode — Heritage Digital Twin node (HDT-O HC2).

Represents an HC2 Heritage Digital Twin as defined in the Heritage Digital
Twin Ontology (HDT-O), ECHOES Deliverable D7.1 (May 2024).

An HDT is an aggregation of Heritage Proposition Sets (named graphs carrying
formal propositions) about a heritage entity (HC1). HDTs are hierarchically
composable — a city HDT contains district HDTs which contain monument HDTs.

Granularity connectors (declared in s3Dgraphy_connections_datamodel.json):
  * has_digital_twin              — Node → HDTNode  (HP1)
  * has_digital_twin_component    — HDTNode → HDTNode (HP3 inverse, transitive)
  * contains_proposition_set      — HDTNode → GraphNode (HP33)
  * has_digital_object_part       — HDTNode → RepresentationModel* / LinkNode (HP29)

Use case (the Colosseo example):
    colosseo_overall   = HDTNode("hdt_colosseo_overall", name="Colosseo HDT")
    colosseo_flavian   = HDTNode("hdt_colosseo_flavian", name="Colosseo Flavian phase")
    colosseo_medieval  = HDTNode("hdt_colosseo_medieval", name="Colosseo medieval fortress")
    graph.add_edge(..., source=colosseo_overall, target=colosseo_flavian,
                   edge_type="has_digital_twin_component")
    graph.add_edge(..., source=colosseo_overall, target=colosseo_medieval,
                   edge_type="has_digital_twin_component")
"""
from .base_node import Node


class HDTNode(Node):
    """
    HC2 Heritage Digital Twin (HDT-O / ECHOES D7.1).

    Attributes:
        heritage_entity_iri (str, optional): IRI of the linked HC1 Heritage
            Entity (the real-world heritage object). When provided, the
            RDF exporter emits hdto:HP1i_is_digital_twin_of triple linking
            this HDT to its HC1.
        valid_from (str, optional): ISO-8601 date when this HDT version
            became valid (used for temporal scoping per D7.1 — an HDT is
            valid for a specific timespan within a defining project).
        valid_until (str, optional): ISO-8601 date when this HDT version
            was superseded. None = currently valid.
    """
    node_type = "hdt"

    def __init__(self, node_id, name="Unnamed HDT", description="",
                 heritage_entity_iri=None, valid_from=None, valid_until=None):
        super().__init__(node_id=node_id, name=name, description=description)
        self.data = {
            "heritage_entity_iri": heritage_entity_iri,
            "valid_from": valid_from,
            "valid_until": valid_until,
        }

    def to_dict(self):
        return {
            "id": self.node_id,
            "type": self.node_type,
            "name": self.name,
            "description": self.description,
            "data": self.data,
        }


# Example usage (commented out — for documentation only):
"""
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import HDTNode, GraphNode

graph = Graph(graph_id="colosseo_research")

# Top-level Colosseo HDT
overall = HDTNode(
    node_id="hdt_colosseo_overall",
    name="Colosseo HDT — overall",
    description="Heritage Digital Twin of the Colosseum as a whole.",
    heritage_entity_iri="https://example.org/heritage/colosseo",
    valid_from="2024-01-01"
)

# Temporal slice: Flavian construction
flavian = HDTNode(
    node_id="hdt_colosseo_flavian",
    name="Colosseo HDT — Flavian period",
    description="HDT focused on the Flavian construction phase (AD 70-80).",
    heritage_entity_iri="https://example.org/heritage/colosseo",
    valid_from="2024-01-01"
)

# Interpretive aspect: medieval reuse
medieval = HDTNode(
    node_id="hdt_colosseo_medieval",
    name="Colosseo HDT — medieval fortress (Frangipane)",
    description="HDT focused on the Colosseum as Frangipane family fortress.",
    heritage_entity_iri="https://example.org/heritage/colosseo",
    valid_from="2024-01-01"
)

graph.add_node(overall)
graph.add_node(flavian)
graph.add_node(medieval)

# Hierarchical containment (HP3 inverse)
graph.add_edge(edge_id="hdt_e1", edge_source=overall.node_id,
               edge_target=flavian.node_id,
               edge_type="has_digital_twin_component")
graph.add_edge(edge_id="hdt_e2", edge_source=overall.node_id,
               edge_target=medieval.node_id,
               edge_type="has_digital_twin_component")
"""
