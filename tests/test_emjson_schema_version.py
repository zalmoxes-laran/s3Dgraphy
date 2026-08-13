"""S2a — em.json schema versioning and per-edge attributes.

Both additions are ADDITIVE: a document that carries neither field is still a
valid em.json and reads without complaint, and a consumer that knows nothing
about them simply ignores them.

`schema_version` answers a different question from `header.version`: the latter
is the frozen SHAPE of the document (and its major gates whether the file is
readable at all), the former is an integer that moves when the CONTENT of that
shape evolves — so a future migration has something to key off.
"""

import json

import pytest

from s3dgraphy import api
from s3dgraphy.exporter.emjson_exporter import (FORMAT_VERSION, SCHEMA_VERSION,
                                                build_emjson, export_emjson)
from s3dgraphy.graph import Graph
from s3dgraphy.importer.emjson_importer import (LEGACY_SCHEMA_VERSION,
                                                import_emjson, parse_emjson,
                                                schema_version_of)
from s3dgraphy.nodes.group_node import ParadataNodeGroup
from s3dgraphy.nodes.property_node import PropertyNode
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit


def _paradata_graph():
    """A US whose paradata group holds one property — the shape that makes the
    propagation materialise a `has_property` edge and mark it derived."""
    g = Graph(graph_id="g")
    g.add_node(StratigraphicUnit("US1", "wall"))
    g.add_node(ParadataNodeGroup("PD1", "US1_PD"))
    g.add_node(PropertyNode("P1", "height", property_type="dimension", value="3"))
    g.add_edge("p_in", "P1", "PD1", "is_in_paradata_nodegroup")
    g.add_edge("us_pd", "US1", "PD1", "has_paradata_nodegroup")
    return g


# ── schema_version ────────────────────────────────────────────────────────────
def test_the_exporter_stamps_the_schema_version():
    doc = build_emjson(Graph(graph_id="g"))
    assert doc["header"]["schema_version"] == SCHEMA_VERSION
    # the format version is a different field with a different job
    assert doc["header"]["version"] == FORMAT_VERSION


def test_the_reader_reads_it_back():
    doc = build_emjson(_paradata_graph())
    assert schema_version_of(doc) == SCHEMA_VERSION
    graph, warnings = parse_emjson(doc)
    assert graph.attributes["emjson_schema_version"] == SCHEMA_VERSION
    assert graph.attributes["emjson_format_version"] == FORMAT_VERSION
    assert not warnings


def test_a_legacy_document_without_the_field_reads_as_zero():
    """Every file written before S2a. It is not an error — those documents are
    perfectly readable, they just predate any schema evolution."""
    doc = build_emjson(_paradata_graph())
    del doc["header"]["schema_version"]
    assert schema_version_of(doc) == LEGACY_SCHEMA_VERSION == 0
    graph, warnings = parse_emjson(doc)
    assert graph.attributes["emjson_schema_version"] == 0
    assert not warnings          # legacy is normal, not worth a complaint
    assert len(graph.nodes) == len(doc["graph"]["nodes"])


@pytest.mark.parametrize("bogus", ["", "abc", None, {}])
def test_an_unreadable_version_field_degrades_to_legacy(bogus):
    doc = build_emjson(Graph(graph_id="g"))
    doc["header"]["schema_version"] = bogus
    assert schema_version_of(doc) == LEGACY_SCHEMA_VERSION


def test_a_document_from_the_future_is_read_with_a_warning():
    """The format is additive, so a newer file is still readable — but silently
    dropping content the writer meant to carry would be worse than saying so."""
    doc = build_emjson(_paradata_graph())
    doc["header"]["schema_version"] = SCHEMA_VERSION + 5
    graph, warnings = parse_emjson(doc)
    assert graph.nodes                                   # read, not refused
    assert any("newer than this s3dgraphy" in w for w in warnings)


def test_the_fixture_still_loads():
    from pathlib import Path
    fixture = Path(__file__).with_name("fixtures") / "TempluMare.em.json"
    if not fixture.exists():
        pytest.skip("TempluMare fixture absent")
    graph, warnings = import_emjson(str(fixture))
    assert len(graph.nodes) == 206
    assert not [w for w in warnings if "schema" in w]


# ── per-edge attributes ───────────────────────────────────────────────────────
def test_edges_without_attributes_serialize_exactly_as_before():
    """Additive means additive: the field appears only when there is something
    to put in it, so existing documents keep their bytes."""
    doc = build_emjson(_paradata_graph())
    assert all("attributes" not in e for e in doc["graph"]["edges"])


def test_derived_marks_survive_a_round_trip(tmp_path):
    """Se4 marks the materialised `has_property` edges with the paradata group
    that justified them. Before S2a those marks lived only in memory."""
    g = _paradata_graph()
    g.connect_paradatagroup_propertynode_to_stratigraphic(verbose=False)
    edge = next(e for e in g.edges if e.edge_type == "has_property")
    assert edge.attributes == {"derived": True, "derived_from": "PD1"}

    path = export_emjson(g, str(tmp_path / "g.em.json"))
    payload = json.loads(open(path, encoding="utf-8").read())
    # container-of-one: the edges are in the member (see container.py)
    member = next(iter(payload["graphs"].values()))
    written = next(e for e in member["edges"]
                   if e["edge_type"] == "has_property")
    assert written["attributes"] == {"derived": True, "derived_from": "PD1"}

    reloaded, warnings = import_emjson(path)
    assert not warnings
    back = next(e for e in reloaded.edges if e.edge_type == "has_property")
    assert back.attributes["derived"] is True
    assert back.attributes["derived_from"] == "PD1"      # which group, preserved


def test_a_derived_edge_stays_distinguishable_from_an_authored_one(tmp_path):
    g = _paradata_graph()
    g.connect_paradatagroup_propertynode_to_stratigraphic(verbose=False)
    g.add_node(PropertyNode("P2", "width", property_type="dimension", value="1"))
    g.add_edge("authored", "US1", "P2", "has_property")   # by hand, not derived
    reloaded, _ = import_emjson(export_emjson(g, str(tmp_path / "g.em.json")))
    marks = {e.edge_id: e.attributes.get("derived", False)
             for e in reloaded.edges if e.edge_type == "has_property"}
    assert marks["authored"] is False
    assert any(v is True for k, v in marks.items() if k != "authored")


def test_unserialisable_attributes_are_dropped_not_fatal(tmp_path):
    g = _paradata_graph()
    edge = g.find_edge_by_id("p_in")
    edge.attributes["ok"] = "yes"
    edge.attributes["bad"] = object()          # not JSON
    reloaded, _ = import_emjson(export_emjson(g, str(tmp_path / "g.em.json")))
    back = reloaded.find_edge_by_id("p_in")
    assert back.attributes == {"ok": "yes"}


def test_the_api_round_trip_carries_them_too():
    g = _paradata_graph()
    g.connect_paradatagroup_propertynode_to_stratigraphic(verbose=False)
    doc = api.graph_to_emjson(g)
    reloaded, _ = api.load_emjson(doc)
    back = next(e for e in reloaded.edges if e.edge_type == "has_property")
    assert back.attributes["derived_from"] == "PD1"
