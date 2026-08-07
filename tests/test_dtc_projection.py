"""DTC substrate profile (ECHOES) — author a chain and project it to CRMdig + PROV-O.

Model (post input+output Resource): BOTH the input and the output are RESOURCES
= LinkNodes (E73/D1); DTCProcessNode is the only DTC node. Chain: photo (INPUT
Resource) → transformation (DTCProcess) → mesh (OUTPUT Resource); the output is
derived from the input; a RepresentationModel references the output in scene
(has_linked_resource); Author reused via has_author.
"""

import pytest

rdflib = pytest.importorskip("rdflib")

from s3dgraphy.graph import Graph
from s3dgraphy.nodes import (
    DTCProcessNode, AuthorNode, ResourceNode, RepresentationModelNode,
)
from s3dgraphy.exporter.rdf_exporter import RDFExporter, DEFAULT_BASE_URI

CRMDIG = "http://www.cidoc-crm.org/extensions/crmdig/"
PROV = "http://www.w3.org/ns/prov#"
CRM = "http://www.cidoc-crm.org/cidoc-crm/"


def _resource(node_id, name, kind, url) -> ResourceNode:
    """A DTC Resource (input or output): a ResourceNode carrying dtc_kind + resource_type."""
    lk = ResourceNode(node_id, name=name, url=url)
    lk.data["dtc_kind"] = kind
    lk.data["resource_type"] = kind
    return lk


def _chain() -> Graph:
    g = Graph(graph_id="dtc_demo")
    g.add_node(_resource("in1", "Photo set", "photo", "https://assets.example/photos.zip"))
    g.add_node(DTCProcessNode("proc1", name="Photogrammetry", dtc_kind="transformation"))
    g.add_node(_resource("out1", "Site mesh", "mesh", "https://assets.example/mesh.obj"))
    g.add_node(AuthorNode("auth1", name="M. Rossi"))
    g.add_node(RepresentationModelNode("rm1", "Mesh in scene"))
    g.add_edge("e1", "proc1", "in1", "dtc_had_input")    # process → input RESOURCE
    g.add_edge("e2", "proc1", "out1", "dtc_had_output")  # process → output RESOURCE
    g.add_edge("e3", "out1", "in1", "dtc_derived_from")  # output → input RESOURCE
    g.add_edge("e4", "proc1", "auth1", "has_author")     # reused Author
    g.add_edge("e5", "rm1", "out1", "has_linked_resource")  # RM → the output resource (scene facet)
    return g


def _project(tmp_path):
    out = RDFExporter(str(tmp_path / "dtc.ttl"), format="turtle").export_single_graph(_chain())
    g = rdflib.Graph()
    g.parse(out, format="turtle")  # must be valid Turtle
    return g


def test_input_and_output_resource_types(tmp_path):
    """BOTH the input and output Resources (LinkNodes) are crmdig:D1 / prov:Entity
    (beyond E73), symmetric — the role is edge-borne."""
    g = _project(tmp_path)
    for node_id in ("in1", "out1"):
        res = rdflib.URIRef(f"{DEFAULT_BASE_URI}graph/dtc_demo/node/{node_id}")
        types = {str(o) for o in g.objects(subject=res, predicate=rdflib.RDF.type)}
        assert f"{CRMDIG}D1_Digital_Object" in types, node_id
        assert f"{PROV}Entity" in types, node_id
        assert any("E73" in t for t in types), node_id  # keeps its resource identity


def test_dtc_node_types(tmp_path):
    types = {str(o) for o in _project(tmp_path).objects(predicate=rdflib.RDF.type)}
    assert f"{CRMDIG}D1_Digital_Object" in types         # input + output resource
    assert f"{CRMDIG}D7_Digital_Machine_Event" in types  # process
    assert f"{PROV}Entity" in types
    assert f"{PROV}Activity" in types


def test_dtc_chain_predicates(tmp_path):
    preds = {str(p) for p in _project(tmp_path).predicates()}
    assert f"{CRMDIG}L10_had_input" in preds
    assert f"{CRMDIG}L11_had_output" in preds
    assert f"{CRMDIG}L21_used_as_derivation_source" in preds
    assert f"{PROV}used" in preds
    assert f"{PROV}generated" in preds
    assert f"{PROV}wasDerivedFrom" in preds


def test_dtc_commons_and_facets(tmp_path):
    g = _project(tmp_path)
    preds = {str(p) for p in g.predicates()}
    assert f"{PROV}wasAttributedTo" in preds   # has_author (Author reused)
    assert f"{CRM}P67_refers_to" in preds       # RM → resource (has_linked_resource)
    objs = {str(o) for o in g.objects()}
    assert "https://assets.example/mesh.obj" in objs  # the resource's real file


def test_dtc_kind_projected(tmp_path):
    vals = {str(o) for o in _project(tmp_path).objects(predicate=rdflib.URIRef(f"{CRM}P2_has_type"))}
    assert {"photo", "transformation", "mesh"} <= vals


def test_dtc_kind_validation_is_data_driven():
    # the surviving DTC node (Process) still validates its kind against dtc_kinds
    with pytest.raises(ValueError):
        DTCProcessNode("x", dtc_kind="not_a_real_kind")
    assert DTCProcessNode("y", dtc_kind="transformation").data["dtc_kind"] == "transformation"


def test_dtc_emjson_roundtrip():
    """DTC chunks + the output Resource's dtc_kind/resource_type + edges survive
    the em.json round-trip (build → parse)."""
    from s3dgraphy.exporter.emjson_exporter import build_emjson
    from s3dgraphy.importer.emjson_importer import parse_emjson
    doc = build_emjson(_chain())
    g2, _warnings = parse_emjson(doc)
    by = {n.node_id: n for n in g2.nodes}
    # input + output are both Resources (links) carrying dtc_kind + resource_type
    for nid, kind in (("in1", "photo"), ("out1", "mesh")):
        assert by[nid].node_type == "resource", nid
        assert (by[nid].data or {}).get("dtc_kind") == kind, nid
        assert (by[nid].data or {}).get("resource_type") == kind, nid
    assert (by["proc1"].data or {}).get("dtc_kind") == "transformation"
    ets = {e.edge_type for e in g2.edges}
    assert {"dtc_had_input", "dtc_had_output", "dtc_derived_from"} <= ets


def test_dtc_input_output_nodes_retired():
    """Both DTCInputNode and DTCOutputNode are gone (input+output are Resources).
    The DTC event classes are the genesis DTCProcessNode and (Session B) the
    acquisition DTCAcquisitionNode — both gated in dtc_nodes, none on the
    stratigrapher palette."""
    import json
    from pathlib import Path
    import s3dgraphy.nodes as nodes
    assert not hasattr(nodes, "DTCInputNode")
    assert not hasattr(nodes, "DTCOutputNode")
    cfg = Path(__file__).parents[1] / "src/s3dgraphy/JSON_config"
    dm = json.loads((cfg / "s3Dgraphy_node_datamodel.json").read_text(encoding="utf-8"))
    reg = json.loads((cfg / "node_registry.generated.json").read_text(encoding="utf-8"))
    dtc_classes = {c for c in dm.get("dtc_nodes", {}) if not c.startswith("_")}
    assert dtc_classes == {"DTCProcessNode", "DTCAcquisitionNode"}
    for cls in ("DTCInputNode", "DTCOutputNode"):
        assert cls not in reg["node_types"]
    # the DTC event nodes are gated out of the stratigrapher sections
    for sec in ("stratigraphic_nodes", "paradata_nodes", "temporal_nodes"):
        assert "DTCProcessNode" not in dm.get(sec, {})
        assert "DTCAcquisitionNode" not in dm.get(sec, {})
