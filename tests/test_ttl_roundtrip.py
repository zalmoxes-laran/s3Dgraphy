"""P1-E — property-graph → intermediate TTL projection, verified on TempluMare.

TTL is the projection *verification checkpoint* (property graph → TTL now,
→ Virtuoso later). This test pins that the projection:

  1. exports valid Turtle from a real, complex graph (TempluMare, 206 nodes),
  2. covers every projected node (no node silently dropped),
  3. round-trips losslessly through rdflib (parse → serialize → parse is
     isomorphic) — i.e. the emitted TTL is stable and reloadable.

Regression guard for the qualia-IRI hardening: property types with spaces or
punctuation (e.g. "max level", "Shape; dimensions") must be slugified into
valid IRIs, otherwise Turtle serialization raised and TTL export was
impossible on any graph carrying such qualia.
"""

import json
from pathlib import Path

import pytest

rdflib = pytest.importorskip("rdflib")  # projection needs the [rdf] extra

from s3dgraphy.importer.emjson_importer import parse_emjson
from s3dgraphy.exporter.rdf_exporter import RDFExporter

FIXTURE = Path(__file__).parent / "fixtures" / "TempluMare.em.json"


def _load_graph():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    graph, _warnings = parse_emjson(doc)
    return graph


def test_templumare_projects_to_valid_ttl(tmp_path):
    graph = _load_graph()
    exporter = RDFExporter(str(tmp_path / "templumare.ttl"), format="turtle")
    out = exporter.export_single_graph(graph)

    # a real graph produced a non-trivial projection
    assert exporter.stats["nodes"] > 0
    assert exporter.stats["edges_emitted"] > 0
    assert exporter.stats["nodes_unmapped"] == 0  # every node type is mapped

    reloaded = rdflib.Graph()
    reloaded.parse(out, format="turtle")
    assert len(reloaded) > exporter.stats["nodes"]  # more than one triple/node


def test_ttl_covers_every_projected_node(tmp_path):
    graph = _load_graph()
    exporter = RDFExporter(str(tmp_path / "templumare.ttl"), format="turtle")
    out = exporter.export_single_graph(graph)

    reloaded = rdflib.Graph()
    reloaded.parse(out, format="turtle")
    subjects = set(reloaded.subjects())

    expected = {
        exporter._node_iri(graph.graph_id, n.node_id) for n in graph.nodes
    }
    missing = expected - subjects
    assert not missing, f"{len(missing)} nodes absent from the TTL: {sorted(map(str, missing))[:5]}"


def test_ttl_roundtrip_is_lossless(tmp_path):
    """em.json → TTL → reload → re-serialize → reload must be isomorphic."""
    graph = _load_graph()
    out = RDFExporter(str(tmp_path / "templumare.ttl"), format="turtle").export_single_graph(graph)

    g1 = rdflib.Graph()
    g1.parse(out, format="turtle")
    g2 = rdflib.Graph()
    g2.parse(data=g1.serialize(format="turtle"), format="turtle")

    assert g1.isomorphic(g2), "TTL projection is not a lossless RDF round-trip"
