"""IMP1 (2026-08-07) — the GraphML importer materialises the graph-scope
rights metadata as first-class NODES (MIG1-A / DP-65), not graph.data fields.

Header author / licence / embargo + EM-ID now become member nodes of a
graph-scope ParadataNodeGroup owned by the graph-self node (GraphNode):

    GraphNode ─has_paradata_nodegroup→ PDG ←is_in_paradata_nodegroup─ Author/License/Embargo

The value lives in each member's NAME (what funnel.ts / builtin_rules read); the
EM-ID (site key) is on GraphNode.data.em_id; the graph is named from the header.
This supersedes BUGFIX-CANVAS-IMPORT (which wrote graph.data['author_name'|…]):
the importer no longer writes those fields — the one-shot migration keeps reading
legacy em.json, but freshly imported GraphML carries the nodes directly.
"""

import pathlib

from s3dgraphy.graph import Graph
from s3dgraphy.importer.import_graphml import GraphMLImporter

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "canvas_metadata.graphml"


def _import():
    return GraphMLImporter(str(FIXTURE), Graph(graph_id="g")).parse()


def _graph_root(g):
    roots = g.get_nodes_by_type("graph")
    assert roots, "the importer must materialise a graph-self GraphNode"
    return roots[0]


def _members(g):
    """node_type -> the member node of the graph-scope PDG."""
    root = _graph_root(g)
    pdg_ids = [e.edge_target for e in g.get_connected_edges(root.node_id)
               if e.edge_type == "has_paradata_nodegroup"
               and e.edge_source == root.node_id]
    assert pdg_ids, "the GraphNode must own a graph-scope ParadataNodeGroup"
    out = {}
    for pdg_id in pdg_ids:
        for e in g.get_connected_edges(pdg_id):
            if e.edge_type == "is_in_paradata_nodegroup" and e.edge_target == pdg_id:
                m = g.find_node_by_id(e.edge_source)
                out[m.node_type] = m
    return out


def test_author_is_a_graph_scope_node():
    g = _import()
    author = _members(g).get("author")
    assert author is not None, "an AuthorNode must exist in the graph-scope PDG"
    # display value lives in the node name (composed name + surname)
    assert author.name == "Emanuel Demetrescu"


def test_author_keeps_orcid_on_data():
    g = _import()
    author = _members(g)["author"]
    assert (author.data or {}).get("orcid") == "0000-0002-1825-0097"


def test_license_is_a_graph_scope_node():
    g = _import()
    lic = _members(g).get("license")
    assert lic is not None and lic.name == "CC-BY-NC"


def test_embargo_is_a_graph_scope_node():
    g = _import()
    emb = _members(g).get("embargo")
    assert emb is not None and emb.name == "2025-12-31"


def test_em_id_is_the_site_key_on_graphnode():
    """The header ID (e.g. 'TestSite') is the human-readable EM-ID / site key,
    stored on GraphNode.data.em_id (IMP1)."""
    g = _import()
    root = _graph_root(g)
    assert (root.data or {}).get("em_id") == "TestSite"


def test_graph_named_from_header_not_file():
    """graph.name comes from the header label ('Archaeological Site'), not from
    the fixture file name."""
    g = _import()
    name = g.name.get("default") if isinstance(g.name, dict) else g.name
    assert name == "Archaeological Site"


def test_no_legacy_graph_data_fields_written():
    """Clean cut: the importer no longer writes graph.data['author_name'|
    'license'|'embargo'] — the nodes are the single truth."""
    g = _import()
    for k in ("author_name", "license", "embargo"):
        assert k not in (g.data or {}), f"graph.data must not carry {k!r} anymore"
