"""RDF round-trip: property graph → TTL → property graph → TTL.

The exporter alone makes the triplestore a place you can only write to. These
tests pin the return leg: that what ``RDFExporter`` projects, ``RDFImporter``
reads back, and that projecting the result again lands on the SAME RDF graph
(rdflib isomorphism, not string equality — the serializer is free to reorder).

Three claims, in the order they matter:

  RT1  export → import → export is **isomorphic**. If it is not, something in
       the projection cannot be read back, and the store is not a source.
  RT2  the rebuilt property graph has the same **structure** — ids, node
       classes, edge types — and the DTC substrate survives with its CRMdig +
       PROV typing.
  RT3  two named graphs in a TriG come back as two Graphs with their own ids.
"""

import json
from pathlib import Path

import pytest

rdflib = pytest.importorskip("rdflib")
from rdflib.compare import isomorphic, to_isomorphic  # noqa: E402

from s3dgraphy.graph import Graph
from s3dgraphy.nodes import (
    DTCProcessNode, AuthorNode, ResourceNode, RepresentationModelNode,
    EpochNode, StratigraphicUnit, PropertyNode, DocumentNode, ExtractorNode,
)
from s3dgraphy.exporter.rdf_exporter import RDFExporter, DEFAULT_BASE_URI
from s3dgraphy.importer.rdf_importer import RDFImporter, import_rdf

CRMDIG = "http://www.cidoc-crm.org/extensions/crmdig/"
PROV = "http://www.w3.org/ns/prov#"
FIXTURE = Path(__file__).parent / "fixtures" / "TempluMare.em.json"


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: the DTC chain (same shape as test_dtc_projection) plus EM content
# ─────────────────────────────────────────────────────────────────────────────

def _resource(node_id, name, kind, url) -> ResourceNode:
    lk = ResourceNode(node_id, name=name, url=url)
    lk.data["dtc_kind"] = kind
    lk.data["resource_type"] = kind
    return lk


def _dtc_chain(graph_id="dtc_demo") -> Graph:
    """The DTC chain of tests/test_dtc_projection.py, plus a stratigraphic
    core (epoch, unit, property, document, extractor) so the round-trip is
    exercised on the EM classes too and not only on the digital-twin ones."""
    g = Graph(graph_id=graph_id)
    g.add_node(_resource("in1", "Photo set", "photo", "https://assets.example/photos.zip"))
    g.add_node(DTCProcessNode("proc1", name="Photogrammetry", dtc_kind="transformation"))
    g.add_node(_resource("out1", "Site mesh", "mesh", "https://assets.example/mesh.obj"))
    g.add_node(AuthorNode("auth1", name="M. Rossi"))
    g.add_node(RepresentationModelNode("rm1", "Mesh in scene"))
    g.add_edge("e1", "proc1", "in1", "dtc_had_input")
    g.add_edge("e2", "proc1", "out1", "dtc_had_output")
    g.add_edge("e3", "out1", "in1", "dtc_derived_from")
    g.add_edge("e4", "proc1", "auth1", "has_author")
    g.add_edge("e5", "rm1", "out1", "has_linked_resource")

    # EM core: an epoch, a unit in it, a measured property, its source
    g.add_node(EpochNode("ep1", name="II A.D.", start_time=100, end_time=199))
    g.add_node(StratigraphicUnit("US1", name="US1", description="Wall face"))
    prop = PropertyNode("p1", name="height", description="", value="3.2",
                        property_type="height")
    g.add_node(prop)
    g.add_node(DocumentNode("D1", name="D.1 Survey"))
    g.add_node(ExtractorNode("ext1", name="Extractor 1", source="D.1 p.12"))
    g.add_edge("e6", "US1", "ep1", "has_first_epoch")
    g.add_edge("e7", "US1", "p1", "has_property")
    g.add_edge("e8", "p1", "ext1", "has_data_provenance")
    g.add_edge("e9", "ext1", "D1", "extracted_from")
    return g


def _export(graph: Graph, path: Path) -> str:
    return RDFExporter(str(path), format="turtle").export_single_graph(graph)


def _rdf(path: str) -> "rdflib.Graph":
    g = rdflib.Graph()
    g.parse(path, format="turtle")
    return g


# ─────────────────────────────────────────────────────────────────────────────
# RT1 — idempotence under isomorphism
# ─────────────────────────────────────────────────────────────────────────────

def test_rt1_export_import_export_is_isomorphic(tmp_path):
    """The second projection is the SAME RDF graph as the first.

    Isomorphism and not text equality: rdflib may order triples and mint blank
    node labels differently, and neither is a difference in what was said.
    """
    original = _dtc_chain()
    ttl1 = _export(original, tmp_path / "a.ttl")

    importer = RDFImporter()
    rebuilt = importer.parse(ttl1)
    assert len(rebuilt) == 1, importer.warnings

    ttl2 = _export(rebuilt[0], tmp_path / "b.ttl")

    g1, g2 = _rdf(ttl1), _rdf(ttl2)
    assert isomorphic(g1, g2), (
        "second projection differs from the first\n"
        f"only in first : {sorted(set(g1) - set(g2))[:8]}\n"
        f"only in second: {sorted(set(g2) - set(g1))[:8]}"
    )
    # a non-trivial graph, and the same size on both sides
    assert len(g1) == len(g2) > 60, (len(g1), len(g2))


def test_rt1_isomorphic_via_to_isomorphic(tmp_path):
    """Same claim through the canonicalising API, as a second opinion."""
    original = _dtc_chain()
    ttl1 = _export(original, tmp_path / "a.ttl")
    rebuilt = RDFImporter().parse(ttl1)
    ttl2 = _export(rebuilt[0], tmp_path / "b.ttl")
    assert to_isomorphic(_rdf(ttl1)) == to_isomorphic(_rdf(ttl2))


# ─────────────────────────────────────────────────────────────────────────────
# RT2 — the property graph's structure survives
# ─────────────────────────────────────────────────────────────────────────────

def test_rt2_structure_preserved(tmp_path):
    original = _dtc_chain()
    ttl = _export(original, tmp_path / "a.ttl")
    importer = RDFImporter()
    rebuilt = importer.parse(ttl)[0]

    assert rebuilt.graph_id == original.graph_id

    ids_before = {n.node_id for n in original.nodes}
    ids_after = {n.node_id for n in rebuilt.nodes}
    assert ids_after == ids_before, (
        f"missing: {ids_before - ids_after}, extra: {ids_after - ids_before}")

    classes_before = {n.node_id: type(n).__name__ for n in original.nodes}
    classes_after = {n.node_id: type(n).__name__ for n in rebuilt.nodes}
    assert classes_after == classes_before, {
        k: (classes_before[k], classes_after.get(k))
        for k in classes_before if classes_before[k] != classes_after.get(k)
    }

    edges_before = {(e.edge_source, e.edge_target, e.edge_type)
                    for e in original.edges}
    edges_after = {(e.edge_source, e.edge_target, e.edge_type)
                   for e in rebuilt.edges}
    assert edges_after == edges_before, (
        f"missing: {edges_before - edges_after}, extra: {edges_after - edges_before}")


def test_rt2_property_node_keeps_its_qualia_type(tmp_path):
    """A PropertyNode comes back as a PropertyNode with its property_type.

    The class inverse cannot do this — 27 qualia share E54_Dimension — so the
    importer reads em:hasQualiaType, which the exporter states explicitly.
    """
    ttl = _export(_dtc_chain(), tmp_path / "a.ttl")
    rebuilt = RDFImporter().parse(ttl)[0]
    prop = next(n for n in rebuilt.nodes if n.node_id == "p1")
    assert type(prop).__name__ == "PropertyNode"
    assert prop.property_type == "height"
    assert str(prop.value) == "3.2"


def test_rt2_epoch_bounds_are_numbers(tmp_path):
    """Epoch bounds went out as numbers and come back as numbers — a start
    read as the string "100" would break every chronological comparison."""
    ttl = _export(_dtc_chain(), tmp_path / "a.ttl")
    rebuilt = RDFImporter().parse(ttl)[0]
    ep = next(n for n in rebuilt.nodes if n.node_id == "ep1")
    assert ep.start_time == 100 and isinstance(ep.start_time, int)
    assert ep.end_time == 199 and isinstance(ep.end_time, int)


def test_rt2_dtc_survives_the_round_trip(tmp_path):
    """The DTC substrate is still there after import → re-export:
    DTCProcessNode → crmdig:D7, the Resources → crmdig:D1, and the PROV
    input/output chain with its kinds."""
    ttl1 = _export(_dtc_chain(), tmp_path / "a.ttl")
    rebuilt = RDFImporter().parse(ttl1)[0]

    # property-graph side
    proc = next(n for n in rebuilt.nodes if n.node_id == "proc1")
    assert type(proc).__name__ == "DTCProcessNode"
    assert proc.data.get("dtc_kind") == "transformation"
    for node_id, kind in (("in1", "photo"), ("out1", "mesh")):
        res = next(n for n in rebuilt.nodes if n.node_id == node_id)
        assert type(res).__name__ == "ResourceNode"
        assert res.data.get("dtc_kind") == kind

    # RDF side, after re-export
    g = _rdf(_export(rebuilt, tmp_path / "b.ttl"))
    types = {str(o) for o in g.objects(predicate=rdflib.RDF.type)}
    assert f"{CRMDIG}D7_Digital_Machine_Event" in types
    assert f"{CRMDIG}D1_Digital_Object" in types
    assert f"{PROV}Activity" in types
    assert f"{PROV}Entity" in types
    for node_id in ("in1", "out1"):
        ref = rdflib.URIRef(f"{DEFAULT_BASE_URI}graph/dtc_demo/node/{node_id}")
        node_types = {str(o) for o in g.objects(ref, rdflib.RDF.type)}
        assert f"{CRMDIG}D1_Digital_Object" in node_types, node_id


def test_rt2_graph_scope_metadata_and_hdt_anchor(tmp_path):
    """Graph name, default author/license/embargo and the HDT anchor return."""
    g = _dtc_chain()
    g.name = {"default": "DTC demo site"}
    g.description = {"default": "A chain for the round-trip test"}
    g.data["authors"] = ["auth1"]
    g.data["license"] = "CC-BY-4.0"
    g.data["embargo"] = "2030-01-01"
    out = RDFExporter(str(tmp_path / "a.ttl"), format="turtle",
                      parent_hdt_iri="https://example.org/hdt/site1"
                      ).export_single_graph(g)

    rebuilt = RDFImporter().parse(out)[0]
    name = rebuilt.name.get("default") if isinstance(rebuilt.name, dict) else rebuilt.name
    assert name == "DTC demo site"
    assert rebuilt.data.get("license") == "CC-BY-4.0"
    assert rebuilt.data.get("embargo") == "2030-01-01"
    assert rebuilt.data.get("authors") == ["auth1"]
    assert rebuilt.data.get("parent_hdt_iri") == "https://example.org/hdt/site1"


def test_rt2_no_duplicate_edges_from_dual_emission(tmp_path):
    """The exporter emits a specific AND a generic predicate for many edges;
    the importer must produce ONE edge, not two."""
    original = _dtc_chain()
    ttl = _export(original, tmp_path / "a.ttl")
    rebuilt = RDFImporter().parse(ttl)[0]
    assert len(rebuilt.edges) == len(original.edges), (
        f"{len(rebuilt.edges)} edges rebuilt from {len(original.edges)}")


def test_rt2_ap11_physical_relation_keeps_its_type_tag(tmp_path):
    """A physical relation projects to an em: subproperty and comes back as the
    right edge type — the AP11 family is the one place where the type_tag, not
    the predicate, carries the meaning."""
    g = Graph(graph_id="phys")
    g.add_node(StratigraphicUnit("A", name="A"))
    g.add_node(StratigraphicUnit("B", name="B"))
    g.add_edge("x1", "A", "B", "cuts")
    ttl = _export(g, tmp_path / "phys.ttl")
    rebuilt = RDFImporter().parse(ttl)[0]
    assert {(e.edge_source, e.edge_target, e.edge_type) for e in rebuilt.edges} == {
        ("A", "B", "cuts")}


# ─────────────────────────────────────────────────────────────────────────────
# RT3 — multigraph through a TriG
# ─────────────────────────────────────────────────────────────────────────────

def test_rt3_two_named_graphs_become_two_graphs(tmp_path):
    """Two named graphs in one TriG → two Graphs with the right ids."""
    from s3dgraphy.multigraph.multigraph import multi_graph_manager

    a, b = _dtc_chain("site_a"), _dtc_chain("site_b")
    multi_graph_manager.graphs["site_a"] = a
    multi_graph_manager.graphs["site_b"] = b
    try:
        out = RDFExporter(str(tmp_path / "two.trig"), format="trig"
                          ).export_graphs(["site_a", "site_b"])
    finally:
        multi_graph_manager.graphs.pop("site_a", None)
        multi_graph_manager.graphs.pop("site_b", None)

    importer = RDFImporter()
    graphs = importer.parse(out, fmt="trig")
    assert {g.graph_id for g in graphs} == {"site_a", "site_b"}, importer.warnings
    # `Graph.__init__` mints a `geo_<graph_id>` node, so that one id differs by
    # construction between two graphs; everything else must match.
    def _content(graph):
        return {n.node_id for n in graph.nodes
                if n.node_id != f"geo_{graph.graph_id}"}
    for g in graphs:
        assert _content(g) == _content(a)
        assert len(g.edges) == len(a.edges)


def test_rt3_multigraph_registration(tmp_path):
    """`multigraph=` registers the rebuilt graphs where the manager can find them."""
    from s3dgraphy.multigraph.multigraph import MultiGraphManager

    ttl = _export(_dtc_chain("solo"), tmp_path / "a.ttl")
    mgr = MultiGraphManager()
    RDFImporter().parse(ttl, multigraph=mgr)
    assert "solo" in mgr.graphs


# ─────────────────────────────────────────────────────────────────────────────
# API surface / format handling
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_accepts_a_turtle_string(tmp_path):
    ttl_path = _export(_dtc_chain(), tmp_path / "a.ttl")
    text = Path(ttl_path).read_text(encoding="utf-8")
    graphs = RDFImporter().parse(text, fmt="turtle")
    assert len(graphs) == 1 and graphs[0].graph_id == "dtc_demo"


def test_parse_autodetects_jsonld(tmp_path):
    out = RDFExporter(str(tmp_path / "a.jsonld"), format="json-ld"
                      ).export_single_graph(_dtc_chain())
    graphs = RDFImporter().parse(out)
    assert len(graphs) == 1 and {n.node_id for n in graphs[0].nodes}


def test_into_graph_imports_into_an_existing_graph(tmp_path):
    ttl = _export(_dtc_chain(), tmp_path / "a.ttl")
    target = Graph(graph_id="existing")
    target.add_node(StratigraphicUnit("keep_me", name="Kept"))
    result = RDFImporter().parse(ttl, into_graph=target)
    assert result == [target]
    assert target.graph_id == "existing"          # keeps its own identity
    ids = {n.node_id for n in target.nodes}
    assert "keep_me" in ids and "proc1" in ids    # merged, not replaced


def test_rdf_without_emgraph_warns_and_returns_nothing():
    graphs, warnings = import_rdf(
        "<http://example.org/a> <http://example.org/b> <http://example.org/c> .",
        fmt="nt")
    assert graphs == []
    assert any("em:EMGraph" in w for w in warnings)


def test_unknown_predicate_warns_without_crashing(tmp_path):
    """A predicate outside the datamodel is reported, not fatal."""
    ttl_path = _export(_dtc_chain(), tmp_path / "a.ttl")
    text = Path(ttl_path).read_text(encoding="utf-8")
    base = f"{DEFAULT_BASE_URI}graph/dtc_demo/node/"
    text += (f'\n<{base}US1> <http://example.org/unknownPredicate> '
             f'<{base}D1> .\n')
    importer = RDFImporter()
    graphs = importer.parse(text, fmt="turtle")
    assert len(graphs) == 1
    assert any("unknownPredicate" in w for w in importer.warnings)


# ─────────────────────────────────────────────────────────────────────────────
# A real graph: TempluMare (measured, limits declared)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not FIXTURE.exists(), reason="TempluMare fixture absent")
def test_templumare_round_trip_keeps_every_node(tmp_path):
    """On a real 200+ node graph every node comes back, with its class.

    Edges are asserted as a SUPERSET check rather than an equality: the
    projection is deliberately lossy in two declared places (see the end-of
    report) — a narrative's citations live in its chapters, not in edges, and
    two spellings of the same physical relation share one em: subproperty.
    """
    from s3dgraphy.importer.emjson_importer import parse_emjson

    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    original, _w = parse_emjson(doc)

    ttl = _export(original, tmp_path / "tm.ttl")
    importer = RDFImporter()
    rebuilt = importer.parse(ttl)[0]

    ids_before = {n.node_id for n in original.nodes}
    ids_after = {n.node_id for n in rebuilt.nodes}
    assert ids_after == ids_before, (
        f"lost: {sorted(ids_before - ids_after)[:10]}")

    classes_before = {n.node_id: type(n).__name__ for n in original.nodes}
    classes_after = {n.node_id: type(n).__name__ for n in rebuilt.nodes}
    drifted = {k: (classes_before[k], classes_after[k])
               for k in classes_before if classes_before[k] != classes_after[k]}
    assert not drifted, drifted

    # every edge survives, and none is invented
    edges_before = {(e.edge_source, e.edge_target, e.edge_type)
                    for e in original.edges}
    edges_after = {(e.edge_source, e.edge_target, e.edge_type)
                   for e in rebuilt.edges}
    assert not edges_after - edges_before, sorted(edges_after - edges_before)[:10]
    assert not edges_before - edges_after, sorted(edges_before - edges_after)[:10]

    # ONE declared difference in the counts: this graph carries a DUPLICATE
    # `is_after` edge (the same source, target and type twice). RDF is a set of
    # triples, so a duplicate cannot survive a projection — 527 authored edges,
    # 526 distinct ones. Stated here rather than absorbed into a >= assertion.
    assert len(original.edges) - len(rebuilt.edges) == 1
    assert len(rebuilt.edges) == len(edges_after)


@pytest.mark.skipif(not FIXTURE.exists(), reason="TempluMare fixture absent")
def test_templumare_round_trip_is_isomorphic(tmp_path):
    """RT1 on a real 206-node graph: the second projection IS the first.

    This is the strongest statement the pair can make, and it only became true
    once two exporter bugs the round-trip exposed were fixed — epoch bounds that
    were never emitted, and an order-dependent J30_has_domain. See the end-of.
    """
    from s3dgraphy.importer.emjson_importer import parse_emjson

    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    original, _w = parse_emjson(doc)

    ttl1 = _export(original, tmp_path / "tm1.ttl")
    rebuilt = RDFImporter().parse(ttl1)[0]
    ttl2 = _export(rebuilt, tmp_path / "tm2.ttl")

    g1, g2 = _rdf(ttl1), _rdf(ttl2)
    assert len(g1) == len(g2) > 1800, (len(g1), len(g2))
    assert isomorphic(g1, g2), (
        f"only in first : {sorted(set(g1) - set(g2), key=str)[:5]}\n"
        f"only in second: {sorted(set(g2) - set(g1), key=str)[:5]}")


@pytest.mark.skipif(not FIXTURE.exists(), reason="TempluMare fixture absent")
def test_projection_is_order_independent(tmp_path):
    """The projection must not depend on the ORDER of the edges.

    Regression guard for the J30_has_domain bug: a property with several
    `has_property` parents used to be attributed to whichever edge came last, so
    reordering the edges changed the RDF — and nothing that reorders can then be
    idempotent.
    """
    from s3dgraphy.importer.emjson_importer import parse_emjson

    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    a, _ = parse_emjson(doc)
    b, _ = parse_emjson(doc)
    b.edges = list(reversed(b.edges))

    assert isomorphic(_rdf(_export(a, tmp_path / "a.ttl")),
                      _rdf(_export(b, tmp_path / "b.ttl")))


# ─────────────────────────────────────────────────────────────────────────────
# SPARQL seam (stretch) — query construction only; see the docstring
# ─────────────────────────────────────────────────────────────────────────────

def test_sparql_construct_targets_one_named_graph():
    """The CONSTRUCT asks for exactly one named graph's own triples.

    A CONSTRUCT and not a DESCRIBE: DESCRIBE is implementation-defined — each
    store decides how much of the neighbourhood to hand back — and this needs
    the graph, no more and no less.
    """
    q = RDFImporter().sparql_query("https://w3id.org/em/id/graph/site_a")
    assert "CONSTRUCT" in q and "GRAPH <https://w3id.org/em/id/graph/site_a>" in q
    assert "DESCRIBE" not in q


def test_sparql_construct_without_a_graph_iri_takes_everything():
    q = RDFImporter().sparql_query()
    assert "CONSTRUCT" in q and "GRAPH" not in q


def test_sparql_result_goes_through_the_same_parse(tmp_path, monkeypatch):
    """`from_sparql` adds no second reconstruction path: whatever the endpoint
    returns is handed to `parse`. Verified by faking the HTTP leg — the live
    conversation with a real store is a declared untested seam."""
    ttl = Path(_export(_dtc_chain("from_store"), tmp_path / "a.ttl")).read_bytes()

    class _Response:
        def read(self):
            return ttl
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: _Response())

    graphs = RDFImporter().from_sparql("https://example.org/sparql",
                                       graph_iri="https://w3id.org/em/id/graph/from_store")
    assert [g.graph_id for g in graphs] == ["from_store"]
    assert {n.node_id for n in graphs[0].nodes} >= {"proc1", "in1", "out1"}
