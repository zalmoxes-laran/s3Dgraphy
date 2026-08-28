"""P1-F — the access-API surface (s3dgraphy.api): pure ops, stable contract.

Covers the operations em-bridge / StratiGraph Server drive. Format-specific ops are
skipped if their optional dep is absent (rdflib for TTL, lxml for GraphML)."""

import json
from pathlib import Path

import pytest

from s3dgraphy import api

FIXTURE = Path(__file__).parent / "fixtures" / "TempluMare.em.json"


@pytest.fixture
def doc():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_no_web_framework_imported():
    # the library must stay web-dep-free (DoD): importing the surface must not
    # drag in FastAPI/uvicorn/starlette.
    import sys
    for mod in ("fastapi", "uvicorn", "starlette"):
        assert mod not in sys.modules


def test_load_emjson_and_validate(doc):
    graph, warnings = api.load_emjson(doc)
    assert graph.nodes and graph.edges
    rep = api.validate(graph)
    assert rep["ok"] is True
    assert rep["stats"]["nodes"] == len(graph.nodes)
    assert rep["stats"]["edges"] == len(graph.edges)
    assert rep["issues"] == []


def test_validate_flags_dangling_edge(doc):
    graph, _ = api.load_emjson(doc)
    graph.edges[0].edge_target = "does-not-exist"
    rep = api.validate(graph)
    assert rep["ok"] is False and rep["issues"]


def test_graph_to_emjson_roundtrips(doc):
    graph, _ = api.load_emjson(doc)
    out = api.graph_to_emjson(graph)
    assert out.get("header", {}).get("format") == "em.json"
    assert out["graph"]["graph_id"] == doc["graph"]["graph_id"]


def test_authority_ops():
    facets = api.authority_facets()
    assert set(facets) == {"WHEN", "WHAT", "WHERE", "WHO"}
    hits = api.resolve_authority("mosaic", "WHAT")
    assert hits and hits[0]["authority"] == "aat"
    assert api.resolve_authority("", "WHAT") == []


def test_missing_dependency_is_importerror():
    assert issubclass(api.MissingDependency, ImportError)


def test_project_ttl(doc):
    pytest.importorskip("rdflib")
    ttl = api.emjson_to_ttl(doc)
    assert "@prefix" in ttl and "hdto:" in ttl or "@prefix" in ttl


def test_graphml_roundtrip(doc):
    pytest.importorskip("lxml")
    graphml = api.emjson_to_graphml(doc)
    assert "<graphml" in graphml
    back = api.graphml_to_emjson(graphml)
    assert back["graph"]["nodes"], "re-imported graph should have nodes"
