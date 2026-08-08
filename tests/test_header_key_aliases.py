"""IMPKEYS (2026-08-08) — header-key aliases at GraphML import.

Real files author the graph header with US/UK spellings and casing: Aiano uses
UK ``LICENCE`` and uppercase ``EMBARGO``; Templu Mare uses lowercase US
``license``/``embargo``. The importer normalises recognised VARIANTS to the
canonical keys in ONE place (`_normalize_header_vocab`) before the graph-scope
nodes are materialised (MIG1-A/IMP1), so a ``LICENCE`` header now yields a
LicenseNode instead of being silently dropped.
"""

import pathlib

from s3dgraphy.graph import Graph
from s3dgraphy.importer.import_graphml import (
    GraphMLImporter, _normalize_header_vocab)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "header_uk_variants.graphml"


def test_normalize_maps_uk_and_case_variants():
    v = _normalize_header_vocab({
        "LICENCE": "CC-BY-ND", "EMBARGO": "2099", "EM_ID": "UKSITE",
        "AUTHOR": "Giulia", "orcid": "0000-x",
    })
    assert v["license"] == "CC-BY-ND"
    assert v["embargo"] == "2099"
    assert v["ID"] == "UKSITE"
    assert v["author_name"] == "Giulia"
    assert v["ORCID"] == "0000-x"


def test_normalize_keeps_explicit_canonical_over_variant():
    # an explicit canonical key is never clobbered by a variant
    v = _normalize_header_vocab({"license": "CANONICAL", "LICENCE": "VARIANT"})
    assert v["license"] == "CANONICAL"


def test_normalize_passes_unknown_keys_through():
    v = _normalize_header_vocab({"weird_key": "x"})
    assert v["weird_key"] == "x"


def _members(graph):
    roots = graph.get_nodes_by_type("graph")
    assert roots
    root = roots[0]
    pdg_ids = [e.edge_target for e in graph.get_connected_edges(root.node_id)
               if e.edge_type == "has_paradata_nodegroup"
               and e.edge_source == root.node_id]
    out = {}
    for pdg_id in pdg_ids:
        for e in graph.get_connected_edges(pdg_id):
            if e.edge_type == "is_in_paradata_nodegroup" and e.edge_target == pdg_id:
                m = graph.find_node_by_id(e.edge_source)
                out[m.node_type] = m
    return out, root


def test_uk_header_materialises_license_from_LICENCE():
    """A header with UK `LICENCE`/`EMBARGO`/`EM_ID`/`AUTHOR` materialises the
    graph-scope nodes just like the US canonical spellings."""
    g = GraphMLImporter(str(FIXTURE), Graph(graph_id="g")).parse()
    members, root = _members(g)
    assert members.get("license") is not None, "LICENCE must yield a LicenseNode"
    assert members["license"].name == "CC-BY-ND"
    assert members.get("embargo") is not None and members["embargo"].name == "2099-01-01"
    assert members.get("author") is not None and members["author"].name == "Giulia Bianchi"
    assert (root.data or {}).get("em_id") == "UKSITE"
