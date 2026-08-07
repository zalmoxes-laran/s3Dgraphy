"""MIG1-A (DP-65) — graph-scope rights metadata become first-class nodes.

Legacy documents carried the graph-scope author / licence / embargo as
``graph.data['author_name' | 'license' | 'embargo']`` fields (BUGFIX-CANVAS-
IMPORT). EM 1.6 formalises them as MEMBER nodes of a graph-scope
ParadataNodeGroup owned by the graph-self node (GraphNode) via
``has_paradata_nodegroup`` ← ``is_in_paradata_nodegroup``. The emjson importer
migrates legacy fields to nodes on load (one-shot, idempotent) and the Data
Funnel canvas tier (builtin_rules graph getters) reads those nodes — the legacy
``graph.attributes`` read is gone (clean cut).
"""

from s3dgraphy.importer.emjson_importer import parse_emjson
from s3dgraphy.resolvers.property_resolver import get_rule, resolve_with_source
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode


def _doc(graph_data):
    """Minimal em.json document with the given graph.data payload."""
    return {
        "header": {"format": "em.json", "version": "1.0"},
        "graph": {
            "graph_id": "g_test",
            "name": "Test",
            "data": dict(graph_data),
            "nodes": [
                {"id": "US1", "node_type": "US", "name": "US1"},
            ],
            "edges": [],
        },
    }


def _members(graph):
    """node_type -> display name of the graph-scope PDG members."""
    roots = graph.get_nodes_by_type("graph")
    assert roots, "a graph-self GraphNode must exist after migration"
    root = roots[0]
    pdg_ids = [e.edge_target for e in graph.get_connected_edges(root.node_id)
               if e.edge_type == "has_paradata_nodegroup"
               and e.edge_source == root.node_id]
    assert pdg_ids, "the graph-self node must own a graph-scope PDG"
    out = {}
    for pdg_id in pdg_ids:
        for e in graph.get_connected_edges(pdg_id):
            if e.edge_type == "is_in_paradata_nodegroup" and e.edge_target == pdg_id:
                m = graph.find_node_by_id(e.edge_source)
                out[m.node_type] = m.name
    return out


def test_legacy_graph_data_migrates_to_nodes():
    graph, _ = parse_emjson(_doc({
        "author_name": "M. Rossi",
        "license": "CC-BY-NC",
        "embargo": "2025-12-31",
    }))
    members = _members(graph)
    assert members.get("author") == "M. Rossi"
    assert members.get("license") == "CC-BY-NC"
    assert members.get("embargo") == "2025-12-31"


def test_legacy_fields_are_dropped_after_migration():
    graph, _ = parse_emjson(_doc({
        "author_name": "M. Rossi", "license": "CC-BY-NC", "embargo": "12",
    }))
    for k in ("author_name", "license", "embargo"):
        assert k not in graph.data, f"legacy field {k!r} must be consumed"


def test_no_legacy_no_graphnode():
    """A document with no graph-scope rights metadata gains nothing (no phantom
    GraphNode / PDG)."""
    graph, _ = parse_emjson(_doc({}))
    assert graph.get_nodes_by_type("graph") == []


def test_migration_is_idempotent_no_duplicate_members():
    doc = _doc({"author_name": "M. Rossi", "license": "CC-BY-NC"})
    graph, _ = parse_emjson(doc)
    # re-run the migration explicitly (as a second load would): still one each
    from s3dgraphy.importer.emjson_importer import _migrate_legacy_graph_scope
    graph.data["author_name"] = "M. Rossi"  # simulate a stray re-appearance
    _migrate_legacy_graph_scope(graph)
    authors = [n for n in graph.nodes if n.node_type == "author"]
    assert len(authors) == 1


def test_resolver_reads_graph_scope_from_nodes():
    """The canvas tier of the Data Funnel resolves author / licence / embargo
    from the migrated graph-scope nodes, with source 'graph'."""
    graph, _ = parse_emjson(_doc({
        "author_name": "M. Rossi",
        "license": "CC-BY-NC",
        "embargo": "2025-12-31",
    }))
    us = graph.find_node_by_id("US1")
    assert isinstance(us, StratigraphicNode)
    for rule_id, expected in (("author", "M. Rossi"),
                              ("license", "CC-BY-NC"),
                              ("embargo", "2025-12-31")):
        value, source = resolve_with_source(graph, us, get_rule(rule_id))
        assert value == expected, f"{rule_id}: {value!r}"
        assert source == "graph", f"{rule_id} source {source!r}"


def test_resolver_ignores_legacy_graph_attributes():
    """Clean cut: a value only in graph.attributes (no node) does NOT resolve at
    the graph tier anymore."""
    graph, _ = parse_emjson(_doc({}))
    graph.attributes["author_name"] = "Ghost"
    graph.attributes["license"] = "CC-0"
    us_id = "US1"
    us = graph.find_node_by_id(us_id)
    for rule_id in ("author", "license", "embargo"):
        value, source = resolve_with_source(graph, us, get_rule(rule_id))
        assert value is None, f"{rule_id} should be unresolved, got {value!r}"
        assert source is None
