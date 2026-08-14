"""Promotion: the working model becomes a published, referenced asset (DP-76).

What these tests hold to is not the mechanics — it is that the promotion says
something a reader can act on: WHERE the bytes are, HOW to check they are the
right ones, WHO published them and WHEN, and out of WHAT. And that saying it
twice does not make two of it.
"""

import pytest

from s3dgraphy import api
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import ResourceNode
from s3dgraphy.publication import promote_resource, promotion_delta

DIGEST = "b" * 64
URL = "https://em.example.org/v1/rooms/scavo/asset/sha256:" + DIGEST


def _graph_with_working_resource():
    graph = Graph(graph_id="promotion-test")
    node = ResourceNode("res-us101", name="US101 (mesh di lavoro)",
                        url="//models/US101.blend")
    node.set_residency("resident")
    graph.add_node(node)
    return graph


# ── the resource stops carrying the bytes and starts pointing at them ────────

def test_a_resident_resource_becomes_a_reference_with_url_and_checksum():
    graph = _graph_with_working_resource()
    promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                     media_type="model/gltf-binary", author="0000-0002-1825-0097")
    node = graph.find_node_by_id("res-us101")
    assert node.data["residency"] == "reference"
    assert node.data["url"] == URL
    assert node.data["checksum"] == f"sha256:{DIGEST}"


def test_the_checksum_carries_its_algorithm_even_when_the_caller_forgets():
    """A bare hex is unreadable in two years — the same rule as the shelf."""
    graph = _graph_with_working_resource()
    promote_resource(graph, "res-us101", url=URL, sha256=DIGEST)
    assert graph.find_node_by_id("res-us101").data["checksum"] == f"sha256:{DIGEST}"
    graph2 = _graph_with_working_resource()
    promote_resource(graph2, "res-us101", url=URL, sha256=f"sha256:{DIGEST}")
    assert graph2.find_node_by_id("res-us101").data["checksum"] == f"sha256:{DIGEST}"


def test_a_published_gltf_is_not_filed_as_a_web_page():
    graph = _graph_with_working_resource()
    promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                     media_type="model/gltf-binary")
    node = graph.find_node_by_id("res-us101")
    assert node.data["media_type"] == "model/gltf-binary"
    assert node.data["url_type"] == "3d_model"


def test_a_reference_without_a_url_or_a_checksum_is_refused():
    graph = _graph_with_working_resource()
    with pytest.raises(ValueError):
        promote_resource(graph, "res-us101", url="", sha256=DIGEST)
    with pytest.raises(ValueError):
        promote_resource(graph, "res-us101", url=URL, sha256="")
    # and nothing was half-done
    assert graph.find_node_by_id("res-us101").data["residency"] == "resident"


# ── the genesis is a DTC event, attributed and dated ─────────────────────────

def test_the_genesis_is_recorded_as_a_dtc_transformation_that_generated_it():
    graph = _graph_with_working_resource()
    result = promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                              author="0000-0002-1825-0097",
                              at="2026-08-14T10:00:00Z")
    process = graph.find_node_by_id(result.process_id)
    assert process is not None
    assert process.node_type == "dtc_process"          # crmdig:D7
    assert process.data["dtc_kind"] == "transformation"
    generated = [(e.edge_source, e.edge_target) for e in graph.edges
                 if e.edge_type == "dtc_had_output"]
    assert (result.process_id, "res-us101") in generated


def test_the_event_carries_the_hand_and_the_instant():
    graph = _graph_with_working_resource()
    result = promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                              author="0000-0002-1825-0097",
                              at="2026-08-14T10:00:00Z")
    stamps = graph.find_node_by_id(result.process_id).data
    assert stamps["created_by"] == "0000-0002-1825-0097"
    assert stamps["created_at"] == "2026-08-14T10:00:00Z"


def test_without_an_identity_the_event_is_still_dated_and_nobody_is_invented():
    graph = _graph_with_working_resource()
    result = promote_resource(graph, "res-us101", url=URL, sha256=DIGEST)
    stamps = graph.find_node_by_id(result.process_id).data
    assert stamps.get("created_at")
    assert "created_by" not in stamps


def test_the_source_is_named_when_it_is_in_the_graph():
    graph = _graph_with_working_resource()
    graph.add_node(ResourceNode("res-blend", name="progetto.blend",
                                url="//progetto.blend"))
    result = promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                              source_id="res-blend")
    triples = {(e.edge_source, e.edge_type, e.edge_target) for e in graph.edges}
    assert (result.process_id, "dtc_had_input", "res-blend") in triples
    assert ("res-us101", "dtc_derived_from", "res-blend") in triples


def test_an_absent_source_is_declared_not_invented():
    """The working file is usually a .blend nobody published. Making a node for
    it would put something unreachable in the graph."""
    graph = _graph_with_working_resource()
    result = promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                              source_id="res-nowhere")
    assert graph.find_node_by_id("res-nowhere") is None
    assert any("res-nowhere" in w for w in result.warnings)
    assert not [e for e in graph.edges if e.edge_type == "dtc_had_input"]


# ── the same promotion twice is the same promotion ───────────────────────────

def test_promoting_the_same_bytes_twice_converges():
    graph = _graph_with_working_resource()
    first = promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                             author="0000-0002-1825-0097")
    nodes, edges = len(list(graph.nodes)), len(list(graph.edges))
    second = promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                              author="0000-0002-1825-0097")
    assert second.process_id == first.process_id
    assert len(list(graph.nodes)) == nodes
    assert len(list(graph.edges)) == edges


def test_new_bytes_are_a_new_event_not_a_rewritten_one():
    """A second export is a second act: the first one still happened."""
    graph = _graph_with_working_resource()
    first = promote_resource(graph, "res-us101", url=URL, sha256=DIGEST)
    other = "c" * 64
    second = promote_resource(graph, "res-us101", url=URL.replace(DIGEST, other),
                              sha256=other)
    assert second.process_id != first.process_id
    assert graph.find_node_by_id(first.process_id) is not None
    assert graph.find_node_by_id("res-us101").data["checksum"] == f"sha256:{other}"


# ── no new vocabulary, and a delta a caller can send ─────────────────────────

def test_promotion_invents_no_node_type():
    graph = _graph_with_working_resource()
    before = {n.node_type for n in graph.nodes}
    promote_resource(graph, "res-us101", url=URL, sha256=DIGEST)
    after = {n.node_type for n in graph.nodes}
    # only the DTC process appears, and it is a type the datamodel already had
    assert after - before == {"dtc_process"}


def test_the_delta_is_em_json_and_carries_the_reference():
    graph = _graph_with_working_resource()
    result = promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                              media_type="model/gltf-binary")
    delta = promotion_delta(graph, result)
    ids = {n["id"] for n in delta["nodes"]}
    assert ids == {"res-us101", result.process_id}
    resource = next(n for n in delta["nodes"] if n["id"] == "res-us101")
    assert resource["data"]["residency"] == "reference"
    assert resource["data"]["checksum"] == f"sha256:{DIGEST}"
    assert len(delta["edges"]) == 1


def test_the_api_surface_returns_plain_dicts():
    """`api` is what another PROCESS calls (em-server, EMtools): what crosses
    that line has to be JSON, not a dataclass."""
    graph = _graph_with_working_resource()
    result = api.promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                                  author="0000-0002-1825-0097")
    assert isinstance(result, dict) and result["resource_id"] == "res-us101"
    delta = api.promotion_delta(graph, result)
    assert {n["id"] for n in delta["nodes"]} == {"res-us101", result["process_id"]}


def test_a_resource_the_graph_never_knew_is_created_rather_than_refused():
    graph = Graph(graph_id="promotion-test")
    result = promote_resource(graph, "res-new", url=URL, sha256=DIGEST,
                              name="US205 (glTF)")
    assert result.created
    node = graph.find_node_by_id("res-new")
    assert node.name == "US205 (glTF)"
    assert node.data["residency"] == "reference"


def test_the_published_asset_is_attached_to_what_it_depicts():
    """An asset nothing points at is a file in a bucket."""
    from s3dgraphy.nodes import StratigraphicUnit

    graph = Graph(graph_id="promotion-test")
    graph.add_node(StratigraphicUnit("US101", name="US101"))
    promote_resource(graph, "res-us101", url=URL, sha256=DIGEST,
                     name="US101 (glTF)", link_to="US101")
    triples = {(e.edge_source, e.edge_type, e.edge_target) for e in graph.edges}
    assert ("US101", "has_linked_resource", "res-us101") in triples
