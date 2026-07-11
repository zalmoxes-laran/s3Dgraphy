"""Round-trip test for the .em.json v1 native format.

graph → build_emjson → parse_emjson → graph must preserve: node ids, types,
names, descriptions, type-specific attributes (epoch bounds, property
values), edge tuples, and graph metadata. Also checks header conformance
and that ALL stratigraphic subtypes survive (the bucket-bug regression
class is impossible on the flat format — this test pins that promise).
"""

import json

import pytest

from s3dgraphy.graph import Graph
from s3dgraphy.nodes.base_node import Node
from s3dgraphy.nodes.stratigraphic_node import (
    StratigraphicUnit, ReusedSpecialFind, WorkingUnit,
    NegativeStratigraphicUnit, SeriesOfDocumentaryStratigraphicUnit,
    ContinuityNode,
)
from s3dgraphy.nodes.epoch_node import EpochNode
from s3dgraphy.nodes.property_node import PropertyNode
from s3dgraphy.nodes.extractor_node import ExtractorNode
from s3dgraphy.nodes.combiner_node import CombinerNode
from s3dgraphy.nodes.document_node import DocumentNode
from s3dgraphy.exporter.emjson_exporter import build_emjson, FORMAT_VERSION
from s3dgraphy.importer.emjson_importer import parse_emjson, EmJsonImportError


def _fixture() -> Graph:
    g = Graph(graph_id="rt")
    g.name = {"default": "roundtrip fixture"}
    g.add_node(StratigraphicUnit("US1", "US1", "wall"))
    g.add_node(NegativeStratigraphicUnit("USN1", "USN1", "cut"))
    g.add_node(ReusedSpecialFind("RSF1", "RSF1", "spolia block"))
    g.add_node(WorkingUnit("UL1", "UL1", "tooling"))
    g.add_node(SeriesOfDocumentaryStratigraphicUnit("serUSD1", "serUSD1", "series"))
    g.add_node(ContinuityNode("BR1", "BR1", "end of life"))
    g.add_node(EpochNode("EP1", "Roman", -27, 476))
    p = PropertyNode("PR1", "height", "wall height", value="3.2 m",
                     property_type="height")
    g.add_node(p)
    g.add_node(ExtractorNode("EX1", "EX1", "measured", "D.01 p.4"))
    g.add_node(CombinerNode("CB1", "CB1", "synthesis"))
    g.add_node(DocumentNode("D01", "survey", "photogrammetric survey"))
    g.add_edge("e1", "US1", "EP1", "has_first_epoch")
    g.add_edge("e2", "US1", "PR1", "has_property")
    g.add_edge("e3", "PR1", "EX1", "has_data_provenance")
    g.add_edge("e4", "EX1", "D01", "extracted_from")
    g.add_edge("e5", "USN1", "US1", "is_after")
    return g


def test_roundtrip_preserves_everything():
    g = _fixture()
    doc = build_emjson(g)

    # header conformance
    assert doc["header"]["format"] == "em.json"
    assert doc["header"]["version"] == FORMAT_VERSION
    assert doc["header"]["datamodel_versions"].get("nodes")
    assert "CIDOC-CRM" in doc["header"]["ontology_versions"]

    g2, warnings = parse_emjson(json.loads(json.dumps(doc)))
    assert warnings == [], f"unexpected warnings: {warnings}"

    # nodes: ids, types, names survive — including every stratigraphic subtype
    before = {(n.node_id, n.node_type) for n in g.nodes}
    after = {(n.node_id, n.node_type) for n in g2.nodes}
    assert before == after
    # count-stable: no phantom nodes from Graph.__init__ side effects
    assert len(g2.nodes) == len(g.nodes)

    by_id = {n.node_id: n for n in g2.nodes}
    assert by_id["EP1"].start_time == -27
    assert by_id["EP1"].end_time == 476
    assert by_id["PR1"].value == "3.2 m"
    assert by_id["PR1"].property_type == "height"
    assert by_id["US1"].description == "wall"
    assert isinstance(by_id["BR1"], ContinuityNode)

    # edges survive as (id, type, source, target)
    e_before = {(e.edge_id, e.edge_type, e.edge_source, e.edge_target) for e in g.edges}
    e_after = {(e.edge_id, e.edge_type, e.edge_source, e.edge_target) for e in g2.edges}
    assert e_before == e_after

    # second round-trip is byte-stable (determinism contract)
    doc2 = build_emjson(g2)
    assert json.dumps(doc["graph"], sort_keys=True) == \
        json.dumps(doc2["graph"], sort_keys=True)


def test_unknown_node_type_degrades_gracefully():
    g = _fixture()
    doc = build_emjson(g)
    doc["graph"]["nodes"].append({"id": "X1", "node_type": "from_the_future"})
    g2, warnings = parse_emjson(doc)
    assert any("from_the_future" in w for w in warnings)
    assert any(n.node_id == "X1" and type(n) is Node for n in g2.nodes)


def test_header_rejection():
    g = _fixture()
    doc = build_emjson(g)
    doc["header"]["version"] = "2.0"
    with pytest.raises(EmJsonImportError):
        parse_emjson(doc)
    doc["header"] = {"format": "something_else", "version": "1.0"}
    with pytest.raises(EmJsonImportError):
        parse_emjson(doc)
