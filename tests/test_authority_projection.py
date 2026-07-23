"""P1-D — projection of authority_refs with strength-aware predicates, and the
minted base_uri. Generalised to ANY node carrying authority_refs (not just HC1).
"""

import tempfile
from pathlib import Path

import pytest

rdflib = pytest.importorskip("rdflib")

from s3dgraphy.graph import Graph
from s3dgraphy.nodes import StratigraphicUnit, HeritageEntityNode
from s3dgraphy.exporter.rdf_exporter import RDFExporter, DEFAULT_BASE_URI

SKOS = "http://www.w3.org/2004/02/skos/core#"
OWL = "http://www.w3.org/2002/07/owl#"


def _project(graph, tmp_path, **kw):
    out = RDFExporter(str(tmp_path / "o.ttl"), format="turtle", **kw
                      ).export_single_graph(graph)
    g = rdflib.Graph()
    g.parse(out, format="turtle")
    return g


def _us_with_refs():
    g = Graph(graph_id="auth")
    us = StratigraphicUnit("us1", name="US 1")
    us.data = {
        "authority_refs": [
            {"uri": "http://vocab.getty.edu/aat/300015342", "authority": "aat",
             "label": "mosaic", "rank": 1, "match": "exact"},
            {"uri": "http://n2t.net/ark:/99152/p0qhb66hrvw", "authority": "periodo",
             "label": "Roman period", "rank": 2, "match": "close"},
            {"uri": "http://www.wikidata.org/entity/Q10285", "authority": "wikidata",
             "label": "Colosseum", "rank": 3, "match": "sameAs"},
            # no `match` → default skos:closeMatch
            {"uri": "http://example.org/x", "authority": "x", "label": "x", "rank": 4},
            # non-http → skipped
            {"uri": "not-a-uri", "authority": "x", "label": "x", "rank": 5, "match": "exact"},
        ]
    }
    g.add_node(us)
    return g, us


def test_match_strength_predicates(tmp_path):
    g, _ = _us_with_refs()
    gg = _project(g, tmp_path)
    preds = [str(p) for p in gg.predicates()]
    assert preds.count(f"{SKOS}exactMatch") == 1
    assert preds.count(f"{SKOS}closeMatch") == 2   # the close ref + the default
    assert preds.count(f"{OWL}sameAs") == 1
    # the non-http ref was skipped (no extra alignment triple)
    aligns = sum(preds.count(f"{SKOS}{m}") for m in
                 ("exactMatch", "closeMatch", "broadMatch")) + preds.count(f"{OWL}sameAs")
    assert aligns == 4


def test_generalised_to_non_heritage_node(tmp_path):
    """authority_refs project from a StratigraphicUnit — not only HC1."""
    g, us = _us_with_refs()
    gg = _project(g, tmp_path)
    node_iri = f"{DEFAULT_BASE_URI}graph/auth/node/us1"
    objs = {str(o) for o in gg.objects(subject=rdflib.URIRef(node_iri))}
    assert "http://vocab.getty.edu/aat/300015342" in objs


def test_base_uri_default_is_w3id(tmp_path):
    g, _ = _us_with_refs()
    gg = _project(g, tmp_path)
    assert DEFAULT_BASE_URI == "https://w3id.org/em/id/"
    subs = {str(s) for s in gg.subjects()}
    assert any(s.startswith("https://w3id.org/em/id/graph/auth/") for s in subs)


def test_base_uri_is_configurable(tmp_path):
    g, _ = _us_with_refs()
    gg = _project(g, tmp_path, base_uri="https://example.test/x/")
    subs = {str(s) for s in gg.subjects()}
    assert any(s.startswith("https://example.test/x/graph/auth/") for s in subs)


def test_heritage_entity_still_projects_its_refs(tmp_path):
    """The generalisation replaced the interim HC1-only rdfs:seeAlso; HC1 refs
    still project — now as skos:closeMatch (default)."""
    g = Graph(graph_id="he")
    he = HeritageEntityNode("he1", name="Colosseo")
    he.data["authority_refs"] = [
        {"uri": "http://vocab.getty.edu/tgn/7000874", "authority": "tgn",
         "label": "Roma", "rank": 1}
    ]
    g.add_node(he)
    gg = _project(g, tmp_path)
    preds = {str(p) for p in gg.predicates()}
    assert f"{SKOS}closeMatch" in preds
    assert f"http://www.w3.org/2000/01/rdf-schema#seeAlso" not in preds
