"""DTC substrate profile (ECHOES) — author a chain and project it to CRMdig + PROV-O.

Chain: photos (DTCInput) → transformation (DTCProcess) → mesh (DTCOutput),
with the output derived from the photos, plus reused EM commons (Author via
has_author, LinkNode file pointer via has_linked_resource)."""

import pytest

rdflib = pytest.importorskip("rdflib")

from s3dgraphy.graph import Graph
from s3dgraphy.nodes import (
    DTCInputNode, DTCProcessNode, DTCOutputNode, AuthorNode, LinkNode,
)
from s3dgraphy.exporter.rdf_exporter import RDFExporter

CRMDIG = "http://www.cidoc-crm.org/extensions/crmdig/"
PROV = "http://www.w3.org/ns/prov#"
CRM = "http://www.cidoc-crm.org/cidoc-crm/"


def _chain() -> Graph:
    g = Graph(graph_id="dtc_demo")
    g.add_node(DTCInputNode("in1", name="Photo set", dtc_kind="photo"))
    g.add_node(DTCProcessNode("proc1", name="Photogrammetry", dtc_kind="transformation"))
    g.add_node(DTCOutputNode("out1", name="Site mesh", dtc_kind="mesh"))
    g.add_node(AuthorNode("auth1", name="M. Rossi"))
    lk = LinkNode("lk1", name="mesh.obj", url="https://assets.example/mesh.obj")
    g.add_node(lk)
    g.add_edge("e1", "proc1", "in1", "dtc_had_input")
    g.add_edge("e2", "proc1", "out1", "dtc_had_output")
    g.add_edge("e3", "out1", "in1", "dtc_derived_from")
    g.add_edge("e4", "proc1", "auth1", "has_author")
    g.add_edge("e5", "out1", "lk1", "has_linked_resource")
    return g


def _project(tmp_path):
    out = RDFExporter(str(tmp_path / "dtc.ttl"), format="turtle").export_single_graph(_chain())
    g = rdflib.Graph()
    g.parse(out, format="turtle")  # must be valid Turtle
    return g


def test_dtc_node_types(tmp_path):
    types = {str(o) for o in _project(tmp_path).objects(predicate=rdflib.RDF.type)}
    assert f"{CRMDIG}D1_Digital_Object" in types      # input + output
    assert f"{CRMDIG}D7_Digital_Machine_Event" in types  # process
    assert f"{PROV}Entity" in types
    assert f"{PROV}Activity" in types


def test_dtc_chain_predicates(tmp_path):
    preds = {str(p) for p in _project(tmp_path).predicates()}
    # CRMdig
    assert f"{CRMDIG}L10_had_input" in preds
    assert f"{CRMDIG}L11_had_output" in preds
    assert f"{CRMDIG}L21_used_as_derivation_source" in preds
    # PROV-O (dual-emitted)
    assert f"{PROV}used" in preds
    assert f"{PROV}generated" in preds
    assert f"{PROV}wasDerivedFrom" in preds


def test_dtc_commons_reused(tmp_path):
    g = _project(tmp_path)
    preds = {str(p) for p in g.predicates()}
    assert f"{PROV}wasAttributedTo" in preds       # has_author (Author reused)
    assert f"{CRM}P67_refers_to" in preds           # has_linked_resource (LinkNode reused)
    # the produced object's real file surfaces as rdfs:seeAlso on the LinkNode
    objs = {str(o) for o in g.objects()}
    assert "https://assets.example/mesh.obj" in objs


def test_dtc_kind_projected(tmp_path):
    vals = {str(o) for o in _project(tmp_path).objects(predicate=rdflib.URIRef(f"{CRM}P2_has_type"))}
    assert {"photo", "transformation", "mesh"} <= vals


def test_dtc_kind_validation_is_data_driven():
    # a kind outside the vocabulary is rejected; a seeded one is accepted
    with pytest.raises(ValueError):
        DTCOutputNode("x", dtc_kind="not_a_real_kind")
    assert DTCOutputNode("y", dtc_kind="orthophoto").data["dtc_kind"] == "orthophoto"


def test_dtc_emjson_roundtrip():
    """DTC chunks + their kind survive the em.json round-trip (build → parse)."""
    from s3dgraphy.exporter.emjson_exporter import build_emjson
    from s3dgraphy.importer.emjson_importer import parse_emjson
    doc = build_emjson(_chain())
    g2, _warnings = parse_emjson(doc)
    kinds = {n.node_id: (n.data or {}).get("dtc_kind")
             for n in g2.nodes if n.node_type in ("dtc_input", "dtc_process", "dtc_output")}
    assert kinds == {"in1": "photo", "proc1": "transformation", "out1": "mesh"}
    ets = {e.edge_type for e in g2.edges}
    assert {"dtc_had_input", "dtc_had_output", "dtc_derived_from"} <= ets


def test_dtc_gated_from_stratigrapher_palette():
    """DTC node types live in the dedicated `dtc_nodes` datamodel section, not a
    stratigraphic/paradata one (the EMStudio palette allowlist gates them out)."""
    import json
    from pathlib import Path
    dm = json.loads((Path(__file__).parents[1]
                     / "src/s3dgraphy/JSON_config/s3Dgraphy_node_datamodel.json"
                     ).read_text(encoding="utf-8"))
    for cls in ("DTCInputNode", "DTCProcessNode", "DTCOutputNode"):
        assert cls in dm.get("dtc_nodes", {})
        for sec in ("stratigraphic_nodes", "paradata_nodes", "temporal_nodes"):
            assert cls not in dm.get(sec, {})
