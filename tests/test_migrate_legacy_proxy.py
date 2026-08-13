"""One-shot legacy migration: proxy-as-node → proxy-as-property."""

import uuid

from s3dgraphy.graph import Graph
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
from s3dgraphy.nodes.semantic_shape_node import SemanticShapeNode
from s3dgraphy.nodes.property_node import PropertyNode
from s3dgraphy.geometry.migrate import migrate_legacy_proxies


def _legacy_graph():
    """US101 with a proxy in the OLD shape: US ──has_semantic_shape──▶ SS."""
    g = Graph(graph_id="legacy")
    us = StratigraphicNode(node_id="US101", name="US101")
    ss = SemanticShapeNode(node_id="SS1", name="US101 proxy", type="proxy",
                           convexshapes=[[0, 0, 0, 1, 1, 1]])
    ss.data["author"] = "E. Demetrescu"
    g.add_node(us)
    g.add_node(ss)
    g.add_edge("e-legacy", "US101", "SS1", "has_semantic_shape")
    return g


def test_migrates_legacy_proxy_to_property():
    g = _legacy_graph()
    report = migrate_legacy_proxies(g)

    assert report["migrated"] == 1
    prop_id = report["property_ids"][0]

    # the property exists, is a geometry quale, and points at the SAME shape node
    prop = g.find_node_by_id(prop_id)
    assert isinstance(prop, PropertyNode)
    assert prop.property_type == "geometry"
    assert prop.value == "SS1"
    # author carried forward
    assert prop.data.get("author") == "E. Demetrescu"

    # the SemanticShape node was REWIRED, not replaced
    assert g.find_node_by_id("SS1") is not None

    # new chain US ──has_property──▶ Property ──has_semantic_shape──▶ SS
    types = {(e.edge_source, e.edge_type, e.edge_target) for e in g.edges}
    assert ("US101", "has_property", prop_id) in types
    assert (prop_id, "has_semantic_shape", "SS1") in types
    # the legacy direct edge is gone
    assert ("US101", "has_semantic_shape", "SS1") not in types


def test_migration_is_idempotent():
    g = _legacy_graph()
    migrate_legacy_proxies(g)
    edges_after_first = {(e.edge_source, e.edge_type, e.edge_target) for e in g.edges}
    nodes_after_first = {n.node_id for n in g.nodes}

    second = migrate_legacy_proxies(g)
    assert second["migrated"] == 0
    assert {(e.edge_source, e.edge_type, e.edge_target) for e in g.edges} == edges_after_first
    assert {n.node_id for n in g.nodes} == nodes_after_first


def test_new_shape_graph_is_untouched():
    """A graph already in the new shape has nothing to migrate."""
    g = Graph(graph_id="new")
    us = StratigraphicNode(node_id="US1", name="US1")
    ss = SemanticShapeNode(node_id="S", name="p", type="proxy", spheres=[[0, 0, 0, 1]])
    prop = PropertyNode(node_id="P", name="geometry", value="S", property_type="geometry")
    g.add_node(us)
    g.add_node(prop)
    g.add_node(ss)
    g.add_edge("a", "US1", "P", "has_property")
    g.add_edge("b", "P", "S", "has_semantic_shape")

    report = migrate_legacy_proxies(g)
    assert report["migrated"] == 0
