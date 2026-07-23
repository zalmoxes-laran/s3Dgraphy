"""P1-C — HDT-O coverage: author an HDT-aware graph and project it to RDF.

Verifies the additive HDT-O layer end-to-end: the new HC1 HeritageEntityNode
completes the canonical HDT-O containment chain and the RDF exporter emits the
HDT-O types (namespaces were already declared in hdto_extension.ttl):

    HC1 HeritageEntityNode ─HP1 has_digital_twin→ HC2 HDTNode
        ─HP33 contains_proposition_set→ HC16 (em:EMGraph / GraphNode)
"""

import pytest

rdflib = pytest.importorskip("rdflib")  # projection needs the [rdf] extra

from s3dgraphy.graph import Graph
from s3dgraphy.nodes import (
    HeritageEntityNode, HDTNode, GraphNode, StudyNode, ProjectNode,
)
from s3dgraphy.exporter.rdf_exporter import RDFExporter

HDTO = "https://w3id.org/hdto/ontology#"
CRM = "http://www.cidoc-crm.org/cidoc-crm/"


def _hdt_aware_graph() -> Graph:
    g = Graph(graph_id="hdt_demo")
    g.add_node(HeritageEntityNode("he_colosseo", name="Colosseo",
                                  description="the monument", entity_kind="monument"))
    g.add_node(HDTNode("hdt_colosseo", name="Colosseo HDT"))
    g.add_node(GraphNode("emgraph_colosseo", name="Colosseo excavation EM graph"))
    g.add_edge(edge_id="e1", edge_source="he_colosseo", edge_target="hdt_colosseo",
               edge_type="has_digital_twin")
    g.add_edge(edge_id="e2", edge_source="hdt_colosseo", edge_target="emgraph_colosseo",
               edge_type="contains_proposition_set")
    return g


def test_hdt_aware_graph_projects_hdto_types(tmp_path):
    out = RDFExporter(str(tmp_path / "hdt.ttl"), format="turtle").export_single_graph(
        _hdt_aware_graph())

    g = rdflib.Graph()
    g.parse(out, format="turtle")  # valid Turtle

    types = {str(o) for o in g.objects(predicate=rdflib.RDF.type)}
    assert f"{HDTO}HC1_Heritage_Entity" in types, "HC1 (HeritageEntityNode) not projected"
    assert f"{HDTO}HC2_Heritage_Digital_Twin" in types, "HC2 (HDTNode) not projected"

    preds = {str(p) for p in g.predicates()}
    assert f"{HDTO}HP1_has_digital_twin" in preds, "HP1 has_digital_twin not projected"
    assert f"{HDTO}HP33_contains" in preds, "HP33 contains_proposition_set not projected"


def _project_study_graph() -> Graph:
    """Project ─includes→ Study ─about→ HC1 ─twin→ HC2 ─contains→ HC16,
    Study ─produced→ HC16."""
    g = Graph(graph_id="hdt_full")
    g.add_node(ProjectNode("prj", name="ECHOES pilot project"))
    g.add_node(StudyNode("std", name="Colosseo excavation study"))
    g.add_node(HeritageEntityNode("he", name="Colosseo"))
    g.add_node(HDTNode("hdt", name="Colosseo HDT"))
    g.add_node(GraphNode("emg", name="Colosseo EM graph"))
    for i, s, t, ty in [
        ("e1", "prj", "std", "includes_study"),
        ("e2", "std", "he", "study_about_heritage"),
        ("e3", "std", "emg", "study_produced_proposition_set"),
        ("e4", "he", "hdt", "has_digital_twin"),
        ("e5", "hdt", "emg", "contains_proposition_set"),
    ]:
        g.add_edge(edge_id=i, edge_source=s, edge_target=t, edge_type=ty)
    return g


def test_project_study_chain_projects_hdto(tmp_path):
    out = RDFExporter(str(tmp_path / "full.ttl"), format="turtle").export_single_graph(
        _project_study_graph())
    g = rdflib.Graph()
    g.parse(out, format="turtle")  # valid Turtle

    types = {str(o) for o in g.objects(predicate=rdflib.RDF.type)}
    for hc in ("HC9_Study", "HC13_Project", "HC1_Heritage_Entity",
               "HC2_Heritage_Digital_Twin"):
        assert f"{HDTO}{hc}" in types, f"{hc} not projected"

    preds = {str(p) for p in g.predicates()}
    assert f"{HDTO}HP23_was_about" in preds       # Study → HeritageEntity
    assert f"{HDTO}HP25_has_created" in preds      # Study → proposition set
    assert f"{CRM}P9_consists_of" in preds         # Project → Study (CRM fallback)
    assert f"{HDTO}HP1_has_digital_twin" in preds  # HC1 → HC2
    assert f"{HDTO}HP33_contains" in preds         # HC2 → HC16


def test_hdto_view_nodes_are_gated_from_the_palette():
    """HC1 is HDT-O-view only: registered as a class, but its node_type must
    NOT leak into the stratigrapher palette. The palette allowlist lives in
    EMStudio (palette-ui.ts); here we pin the datamodel side — the node lives
    in the dedicated `hdto_nodes` section, not a stratigraphic/paradata one."""
    import json
    from pathlib import Path
    dm = json.loads((Path(__file__).parents[1]
                     / "src/s3dgraphy/JSON_config/s3Dgraphy_node_datamodel.json"
                     ).read_text(encoding="utf-8"))
    for cls in ("HeritageEntityNode", "StudyNode", "ProjectNode"):
        assert cls in dm.get("hdto_nodes", {}), f"{cls} missing from hdto_nodes"
        # not smuggled into a palette-facing section
        for sec in ("stratigraphic_nodes", "paradata_nodes", "temporal_nodes"):
            assert cls not in dm.get(sec, {}), f"{cls} leaked into {sec}"
