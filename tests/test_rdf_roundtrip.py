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


# ─────────────────────────────────────────────────────────────────────────────
# STEP A — the RDF is self-describing: IRI → class is bijective
# ─────────────────────────────────────────────────────────────────────────────

def _structural_graph() -> Graph:
    """The six classes that used to share three CIDOC classes, in one graph."""
    from s3dgraphy.nodes import (
        GeoPositionNode, LocationNodeGroup, ParadataNodeGroup, GroupNode,
        UnknownNode,
    )
    g = Graph(graph_id="structural")
    g.add_node(LocationNodeGroup("loc1", "Pompei", "toponym"))
    g.add_node(ParadataNodeGroup("pd1", "US1_PD"))
    g.add_node(GroupNode("grp1", "Generic group"))
    g.add_node(UnknownNode("unk1", "?"))
    return g


def test_iri_to_class_is_bijective():
    """50 classes, 50 distinct primary IRIs, zero collisions.

    Before the distinct URIs of 2026-08-11 three CIDOC classes were shared by two
    s3Dgraphy classes each, and the projection could not say which had been
    written. This is the property that makes the RDF self-describing.
    """
    from s3dgraphy.importer.rdf_importer import _InverseDatamodel

    inv = _InverseDatamodel()
    collisions = {iri: names for iri, names in inv.classes_by_iri.items()
                  if len(names) > 1}
    assert not collisions, collisions
    assert len(inv.classes_by_iri) == len(inv.dm._node_class_index)


def test_the_three_former_collisions_resolve_without_evidence(tmp_path):
    """Each of the six comes back as itself, from its rdf:type alone."""
    original = _structural_graph()
    ttl = _export(original, tmp_path / "s.ttl")
    importer = RDFImporter()
    rebuilt = importer.parse(ttl)[0]

    classes = {n.node_id: type(n).__name__ for n in rebuilt.nodes}
    assert classes["loc1"] == "LocationNodeGroup"
    assert classes["pd1"] == "ParadataNodeGroup"
    assert classes["grp1"] == "GroupNode"
    assert classes["unk1"] == "UnknownNode"
    assert not importer.warnings, importer.warnings


def test_geoposition_without_a_transform_still_reads_as_a_geoposition(tmp_path):
    """The case the evidence heuristic could NOT read.

    A GeoPositionNode with no shift and no rotation emits no `em:shift_*`, so
    the old tie-break had nothing to look at and fell through to
    LocationNodeGroup — the two shared crm:E53_Place. With a distinct
    `em:GeoPositionNode` in the datamodel the question is answered by the type
    itself, whatever the node happens to carry.
    """
    from s3dgraphy.nodes import GeoPositionNode

    g = Graph(graph_id="bare_geo")
    geo = GeoPositionNode("geo_bare")
    geo.data = {}                       # no epsg, no shift, no rotation
    g.add_node(geo, overwrite=True)

    ttl = _export(g, tmp_path / "bare.ttl")
    # the evidence the old heuristic relied on is genuinely absent FROM THIS NODE
    # (the graph auto-creates a geo node of its own, which does carry shifts)
    rdf = _rdf(ttl)
    bare = rdflib.URIRef(f"{DEFAULT_BASE_URI}graph/bare_geo/node/geo_bare")
    preds = {str(p) for p in rdf.predicates(bare, None)}
    assert not any("shift" in p or "rotation" in p for p in preds), sorted(preds)

    importer = RDFImporter()
    rebuilt = importer.parse(ttl)[0]
    geo_back = next(n for n in rebuilt.nodes if n.node_id == "geo_bare")
    assert type(geo_back).__name__ == "GeoPositionNode"
    assert not importer.warnings, importer.warnings


def test_crm_superclasses_are_still_emitted_for_crm_only_readers(tmp_path):
    """Nothing was taken away: the E1/E78/E53 statements are still there.

    The new em: classes are declared `rdfs:subClassOf` their former CIDOC class
    and the exporter emits both, so a consumer that knows only CIDOC reads the
    same graph it read before.
    """
    ttl = _export(_structural_graph(), tmp_path / "s.ttl")
    g = _rdf(ttl)
    CRM_NS = "http://www.cidoc-crm.org/cidoc-crm/"
    base = f"{DEFAULT_BASE_URI}graph/structural/node/"
    expected = {
        "loc1": (f"{CRM_NS}E53_Place", "LocationNodeGroup"),
        "pd1": (f"{CRM_NS}E78_Collection", "ParadataNodeGroup"),
        "grp1": (f"{CRM_NS}E78_Collection", "NodeGroup"),
        "unk1": (f"{CRM_NS}E1_CRM_Entity", "UnknownNode"),
    }
    for node_id, (crm_class, em_local) in expected.items():
        types = {str(o) for o in g.objects(rdflib.URIRef(base + node_id),
                                           rdflib.RDF.type)}
        assert crm_class in types, (node_id, sorted(types))
        assert f"https://w3id.org/em/ontology#{em_local}" in types, (
            node_id, sorted(types))


def test_structural_graph_round_trips_isomorphically(tmp_path):
    ttl1 = _export(_structural_graph(), tmp_path / "a.ttl")
    rebuilt = RDFImporter().parse(ttl1)[0]
    ttl2 = _export(rebuilt, tmp_path / "b.ttl")
    assert isomorphic(_rdf(ttl1), _rdf(ttl2))


def test_legacy_ttl_without_the_new_uris_still_reads(tmp_path):
    """Back-compatibility: TTL written BEFORE the distinct URIs.

    Such a document types a GeoPosition as a bare crm:E53_Place, which is also
    what a Location was. The evidence tie-break is kept for exactly this, and
    the shift triples are what it reads.
    """
    legacy = f"""
@prefix crm: <http://www.cidoc-crm.org/cidoc-crm/> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix em: <https://w3id.org/em/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<{DEFAULT_BASE_URI}graph/legacy> a em:EMGraph .

<{DEFAULT_BASE_URI}graph/legacy/node/geo_legacy> a crm:E53_Place ;
    rdfs:label "geo_position" ;
    dcterms:identifier "geo_legacy" ;
    crm:P2_has_type "EPSG:4326" ;
    em:shift_x 1.5 ;
    em:shift_y 2.5 ;
    em:shift_z 0.0 ;
    em:rotation 0.0 .
"""
    importer = RDFImporter()
    rebuilt = importer.parse(legacy, fmt="turtle")[0]
    geo = next(n for n in rebuilt.nodes if n.node_id == "geo_legacy")
    assert type(geo).__name__ == "GeoPositionNode"
    assert geo.data.get("shift_x") == 1.5


# ─────────────────────────────────────────────────────────────────────────────
# STEP B — one I17 per (property, unit) pair: the projection is not lossy
# ─────────────────────────────────────────────────────────────────────────────

CRMINF_NS = "http://www.cidoc-crm.org/extensions/crminf/"


def _shared_property_graph() -> Graph:
    """Three units claiming ONE property — the shape that used to lose two of
    the three attributions on the way into RDF."""
    from s3dgraphy.nodes import ExtractorNode

    g = Graph(graph_id="shared_prop")
    for uid in ("US_a", "US_b", "US_c"):
        g.add_node(StratigraphicUnit(uid, name=uid))
    g.add_node(PropertyNode("p_shared", name="height", description="",
                            value="2.4", property_type="height"))
    g.add_node(ExtractorNode("ext1", name="Extractor", source="D.1"))
    for i, uid in enumerate(("US_a", "US_b", "US_c")):
        g.add_edge(f"hp{i}", uid, "p_shared", "has_property")
    g.add_edge("prov", "p_shared", "ext1", "has_data_provenance")
    return g


def test_one_i17_per_property_unit_pair(tmp_path):
    """Three units, three propositions — each naming its own subject."""
    g = _rdf(_export(_shared_property_graph(), tmp_path / "s.ttl"))
    i17s = list(g.subjects(rdflib.RDF.type,
                           rdflib.URIRef(CRMINF_NS + "I17_One-Proposition_Set")))
    assert len(i17s) == 3, sorted(str(s) for s in i17s)

    domains = {str(o).rsplit("/node/", 1)[-1]
               for s in i17s
               for o in g.objects(s, rdflib.URIRef(CRMINF_NS + "J30_has_domain"))}
    assert domains == {"US_a", "US_b", "US_c"}, domains


def test_i17_iris_name_the_pair_and_are_deterministic(tmp_path):
    """The IRI carries the pair, which is what makes the set re-readable and the
    export order-independent — a stable name derived from the two things the
    proposition relates."""
    g = _rdf(_export(_shared_property_graph(), tmp_path / "s.ttl"))
    i17s = {str(s) for s in g.subjects(
        rdflib.RDF.type, rdflib.URIRef(CRMINF_NS + "I17_One-Proposition_Set"))}
    base = f"{DEFAULT_BASE_URI}graph/shared_prop/node/p_shared/proposition/"
    assert i17s == {base + "US_a", base + "US_b", base + "US_c"}, sorted(i17s)


def test_all_three_has_property_edges_come_back(tmp_path):
    """The point of the whole step: nothing is lost on the way in OR out."""
    original = _shared_property_graph()
    ttl = _export(original, tmp_path / "s.ttl")
    importer = RDFImporter()
    rebuilt = importer.parse(ttl)[0]

    parents = sorted(e.edge_source for e in rebuilt.edges
                     if e.edge_type == "has_property"
                     and e.edge_target == "p_shared")
    assert parents == ["US_a", "US_b", "US_c"], parents

    edges_before = {(e.edge_source, e.edge_target, e.edge_type)
                    for e in original.edges}
    edges_after = {(e.edge_source, e.edge_target, e.edge_type)
                   for e in rebuilt.edges}
    assert edges_after == edges_before


def test_shared_property_round_trips_isomorphically(tmp_path):
    ttl1 = _export(_shared_property_graph(), tmp_path / "a.ttl")
    rebuilt = RDFImporter().parse(ttl1)[0]
    ttl2 = _export(rebuilt, tmp_path / "b.ttl")
    assert isomorphic(_rdf(ttl1), _rdf(ttl2))


def test_single_parent_property_still_gets_exactly_one_i17(tmp_path):
    """The ordinary case is unchanged in count — one parent, one proposition."""
    g = _rdf(_export(_dtc_chain(), tmp_path / "a.ttl"))
    i17s = list(g.subjects(rdflib.RDF.type,
                           rdflib.URIRef(CRMINF_NS + "I17_One-Proposition_Set")))
    assert len(i17s) == 1
    assert str(i17s[0]).endswith("/node/p1/proposition/US1")


@pytest.mark.skipif(not FIXTURE.exists(), reason="TempluMare fixture absent")
def test_templumare_three_parent_property_keeps_all_three(tmp_path):
    """The real case that motivated the change: TempluMare carries one property
    claimed by three units. Before, two of those attributions were absent from
    the RDF; nothing downstream could recover what was never written."""
    from s3dgraphy.importer.emjson_importer import parse_emjson

    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    original, _w = parse_emjson(doc)

    parents_of = {}
    for e in original.edges:
        if e.edge_type == "has_property":
            parents_of.setdefault(e.edge_target, []).append(e.edge_source)
    multi = {p: sorted(u) for p, u in parents_of.items() if len(u) > 1}
    assert len(multi) == 1, multi          # exactly one such property
    prop_id, expected_parents = next(iter(multi.items()))
    assert len(expected_parents) == 3

    ttl = _export(original, tmp_path / "tm.ttl")
    rebuilt = RDFImporter().parse(ttl)[0]
    got = sorted(e.edge_source for e in rebuilt.edges
                 if e.edge_type == "has_property" and e.edge_target == prop_id)
    assert got == expected_parents, (got, expected_parents)


# ─────────────────────────────────────────────────────────────────────────────
# STEP A (2026-08-11 combo) — symmetric relations: canonicalising is not a loss
# ─────────────────────────────────────────────────────────────────────────────

def _symmetric_graph() -> Graph:
    """Both directional spellings of both symmetric physical relations."""
    g = Graph(graph_id="symmetric")
    for uid in ("A", "B", "C", "D"):
        g.add_node(StratigraphicUnit(uid, name=uid))
    g.add_edge("s1", "A", "B", "is_bonded_to")
    g.add_edge("s2", "C", "D", "is_physically_equal_to")
    return g


def test_symmetric_properties_are_declared_symmetric_in_em_ttl():
    """`em:bondedTo` and `em:physicallyEquals` are owl:SymmetricProperty.

    They must be: the datamodel declares all four edge spellings symmetric, so
    the ontology has to say the relation has no direction — otherwise a reasoner
    would treat `A bondedTo B` and `B bondedTo A` as different facts.
    """
    from pathlib import Path as _Path
    import s3dgraphy

    ttl = _Path(s3dgraphy.__file__).parent / "JSON_config" / "em.ttl"
    onto = rdflib.Graph()
    onto.parse(str(ttl), format="turtle")
    OWL = rdflib.namespace.OWL
    EM_NS = "https://w3id.org/em/ontology#"
    for local in ("bondedTo", "physicallyEquals"):
        types = set(onto.objects(rdflib.URIRef(EM_NS + local), rdflib.RDF.type))
        assert OWL.SymmetricProperty in types, (local, types)
        assert OWL.ObjectProperty in types, (local, types)


def test_symmetric_spellings_canonicalise_without_a_warning(tmp_path):
    """The heart of the step: no warning, because there is no problem.

    Two names for a directionless relation collapse onto one predicate BY
    DESIGN. Reporting that as an ambiguity was reporting a non-problem.
    """
    importer = RDFImporter()
    rebuilt = importer.parse(_export(_symmetric_graph(), tmp_path / "s.ttl"))[0]

    assert importer.warnings == [], importer.warnings
    types = {(e.edge_source, e.edge_target, e.edge_type) for e in rebuilt.edges}
    assert types == {("A", "B", "bonded_to"), ("C", "D", "equals")}, types


def test_symmetric_round_trip_is_isomorphic(tmp_path):
    """Canonicalising does not change the RDF: `is_bonded_to` and `bonded_to`
    were always the same triple, which is why the projection is stable."""
    ttl1 = _export(_symmetric_graph(), tmp_path / "a.ttl")
    rebuilt = RDFImporter().parse(ttl1)[0]
    ttl2 = _export(rebuilt, tmp_path / "b.ttl")
    assert isomorphic(_rdf(ttl1), _rdf(ttl2))


def test_the_canonical_spelling_projects_identically(tmp_path):
    """`is_bonded_to` and `bonded_to` produce the SAME RDF — which is the
    evidence that collapsing them loses nothing."""
    a = Graph(graph_id="sym")
    a.add_node(StratigraphicUnit("A", name="A"))
    a.add_node(StratigraphicUnit("B", name="B"))
    a.add_edge("e", "A", "B", "is_bonded_to")

    b = Graph(graph_id="sym")
    b.add_node(StratigraphicUnit("A", name="A"))
    b.add_node(StratigraphicUnit("B", name="B"))
    b.add_edge("e", "A", "B", "bonded_to")

    assert isomorphic(_rdf(_export(a, tmp_path / "a.ttl")),
                      _rdf(_export(b, tmp_path / "b.ttl")))


def test_other_ambiguities_still_warn():
    """The silence is narrow: only the symmetric spellings stop warning.

    Checked on the rule itself rather than by constructing a graph, because the
    endpoints resolve nearly everything else — the point is that the test is
    structural (one em: subproperty, AP11 family) and not a blanket exemption.
    """
    from s3dgraphy.importer.rdf_importer import _InverseDatamodel

    inv = _InverseDatamodel()
    assert inv.symmetric_spellings(["is_bonded_to", "bonded_to"]) == "bonded_to"
    assert inv.symmetric_spellings(
        ["equals", "is_physically_equal_to"]) == "equals"
    # different relations of the same family → NOT a spelling pair
    assert inv.symmetric_spellings(["cuts", "fills"]) is None
    # outside the physical family → never silent
    assert inv.symmetric_spellings(["has_license", "has_embargo"]) is None
    assert inv.symmetric_spellings(["is_part_of", "is_in_functional_unit"]) is None


def test_symmetric_orientation_is_stable_across_the_round_trip(tmp_path):
    """The exporter keeps the AUTHORED direction, and the importer gives it back.

    Declared, because it is a choice: for a symmetric relation `A→B` and `B→A`
    say the same thing, so the projection COULD normalise the subject to the
    smaller id. It does not — it keeps what the author wrote, which is what makes
    the property-graph round-trip exact (the rebuilt edge has the same source and
    target as the original). Two graphs that authored the same bond in opposite
    directions therefore project to different triples; that is a semantic
    equivalence an OWL reasoner resolves via owl:SymmetricProperty, not a
    difference in what was said.
    """
    g = Graph(graph_id="orient")
    g.add_node(StratigraphicUnit("Z", name="Z"))
    g.add_node(StratigraphicUnit("A", name="A"))
    g.add_edge("e", "Z", "A", "bonded_to")        # authored high → low

    rebuilt = RDFImporter().parse(_export(g, tmp_path / "a.ttl"))[0]
    edge = next(e for e in rebuilt.edges if e.edge_type == "bonded_to")
    assert (edge.edge_source, edge.edge_target) == ("Z", "A")

    # and it is stable: exporting the rebuilt graph gives the same triples
    ttl1 = _export(g, tmp_path / "b.ttl")
    ttl2 = _export(rebuilt, tmp_path / "c.ttl")
    assert isomorphic(_rdf(ttl1), _rdf(ttl2))


# ─────────────────────────────────────────────────────────────────────────────
# 2D ANNOTATOR — the semantics, before any canvas
#
# An annotation is not a coloured box on a photograph: it is a claim, and the
# chain is what makes it readable by somebody else. These tests pin the chain
# (four nodes, four edges), the region's geometry, and the fact that all of it
# survives the projection — because a store that cannot give the region back
# cannot be the place the annotator reads from.
# ─────────────────────────────────────────────────────────────────────────────

def _annotated_graph(graph_id="annot") -> Graph:
    """One image, one unit, two annotations — a rect and a polygon, one of them
    on page 3 (so the page is exercised as something other than the default)."""
    from s3dgraphy.annotation import create_annotation_paradata

    g = Graph(graph_id=graph_id)
    g.add_node(DocumentNode("img1", name="Foto Maiuri 1931", url="maiuri.jpg"))
    g.add_node(StratigraphicUnit("US101", name="US101"))
    create_annotation_paradata(
        g, "img1", {"shape_kind": "rect", "rect": [0.12, 0.30, 0.25, 0.18], "page": 3},
        interpretation="laterizio con malta di calce",
        property_type="material", target_unit_id="US101")
    create_annotation_paradata(
        g, "img1",
        {"shape_kind": "polygon",
         "points": [[0.5, 0.5], [0.7, 0.52], [0.65, 0.8], [0.48, 0.72]]},
        interpretation="lacuna di intonaco",
        property_type="conservation_state", target_unit_id="US101")
    return g


def test_annotation_chain_is_four_nodes_and_four_edges():
    """The chain, asserted as a chain: every link named, none of them generic."""
    from s3dgraphy.annotation import create_annotation_paradata

    g = Graph(graph_id="chain")
    g.add_node(DocumentNode("img1", name="Foto", url="f.jpg"))
    g.add_node(StratigraphicUnit("US101", name="US101"))
    result = create_annotation_paradata(
        g, "img1", {"shape_kind": "rect", "rect": [0.1, 0.1, 0.2, 0.2]},
        interpretation="laterizio", property_type="material",
        target_unit_id="US101")

    assert result.warnings == [], result.warnings
    kinds = {type(n).__name__ for n in g.nodes}
    assert {"AnnotationRegionNode", "ExtractorNode", "PropertyNode",
            "DocumentNode", "StratigraphicUnit"} <= kinds

    edges = {(e.edge_type, e.edge_source, e.edge_target) for e in g.edges}
    assert ("extracted_from", result.extractor_id, "img1") in edges
    assert ("is_on_resource", result.region_id, "img1") in edges
    assert ("has_visual_reference", result.property_id, result.region_id) in edges
    assert ("has_property", "US101", result.property_id) in edges
    # the whole point of the guard in `_ensure_edge`
    assert not [e for e in g.edges if e.edge_type == "generic_connection"]


def test_annotation_is_idempotent():
    """A canvas that re-sends on every mouse-up must converge, not accumulate."""
    from s3dgraphy.annotation import create_annotation_paradata

    g = _annotated_graph()
    nodes_before = len(g.nodes)
    edges_before = len(g.edges)

    again = create_annotation_paradata(
        g, "img1", {"shape_kind": "rect", "rect": [0.12, 0.30, 0.25, 0.18], "page": 3},
        interpretation="laterizio con malta di calce",
        property_type="material", target_unit_id="US101")

    assert again.created is False
    assert len(g.nodes) == nodes_before
    assert len(g.edges) == edges_before


def test_the_same_region_read_twice_is_one_region_with_two_properties():
    """Two authors point at the same brick and disagree: ONE region, two qualia.

    This is what keeps the region's identity geometric and not interpretive — the
    alternative (a region per reading) would duplicate the geometry and lose the
    fact that they are talking about the same thing.
    """
    from s3dgraphy.annotation import create_annotation_paradata

    g = Graph(graph_id="disagree")
    g.add_node(DocumentNode("img1", name="Foto", url="f.jpg"))
    g.add_node(StratigraphicUnit("US101", name="US101"))
    rect = {"shape_kind": "rect", "rect": [0.2, 0.2, 0.3, 0.3]}
    a = create_annotation_paradata(g, "img1", rect, "laterizio", "material", "US101")
    b = create_annotation_paradata(g, "img1", rect, "tufo", "material", "US101")

    assert a.region_id == b.region_id
    assert a.property_id != b.property_id
    regions = [n for n in g.nodes if type(n).__name__ == "AnnotationRegionNode"]
    assert len(regions) == 1
    refs = [e for e in g.edges if e.edge_type == "has_visual_reference"]
    assert {e.edge_source for e in refs} == {a.property_id, b.property_id}


def test_annotating_a_resource_promotes_it_to_a_source():
    """A resource FILE is not a source — so one is minted beside it.

    `extracted_from` cites a SOURCE (a DocumentNode). Annotating a bare
    `ResourceNode` used to leave the chain without its extraction link. It is now
    PROMOTED, not converted: a Document is minted next to the resource and linked
    with `has_linked_resource`, so both statements exist and stay distinct —
    the extraction cites the document, the region lives on the resource.
    """
    from s3dgraphy.annotation import create_annotation_paradata

    g = Graph(graph_id="resource_image")
    g.add_node(ResourceNode("res1", name="foto.jpg", url="foto.jpg"))
    g.add_node(StratigraphicUnit("US101", name="US101"))
    result = create_annotation_paradata(
        g, "res1", {"shape_kind": "rect", "rect": [0.1, 0.1, 0.2, 0.2]},
        interpretation="laterizio", property_type="material",
        target_unit_id="US101")

    assert result.warnings == [], result.warnings
    assert not [e for e in g.edges if e.edge_type == "generic_connection"]
    doc_id = result.source_document_id
    assert doc_id and doc_id != "res1"

    edges = {(e.edge_type, e.edge_source, e.edge_target) for e in g.edges}
    assert ("has_linked_resource", doc_id, "res1") in edges   # the promotion
    assert ("extracted_from", result.extractor_id, doc_id) in edges
    assert ("is_on_resource", result.region_id, "res1") in edges  # the pixels
    # the resource is still a resource: promotion is not conversion
    assert type(g.find_node_by_id("res1")).__name__ == "ResourceNode"


def test_the_promoted_document_is_minted_once():
    """Annotating the same image twice reuses its document."""
    from s3dgraphy.annotation import create_annotation_paradata

    g = Graph(graph_id="promo")
    g.add_node(ResourceNode("res1", name="foto.jpg", url="foto.jpg"))
    g.add_node(StratigraphicUnit("US101", name="US101"))
    a = create_annotation_paradata(
        g, "res1", {"shape_kind": "rect", "rect": [0.1, 0.1, 0.2, 0.2]},
        "laterizio", "material", "US101")
    b = create_annotation_paradata(
        g, "res1", {"shape_kind": "rect", "rect": [0.5, 0.5, 0.2, 0.2]},
        "malta", "material", "US101")

    assert a.source_document_id == b.source_document_id
    docs = [n for n in g.nodes if type(n).__name__ == "DocumentNode"]
    assert len(docs) == 1
    assert docs[0].data.get("promoted_from_resource") == "res1"


def test_annotating_something_that_is_no_source_at_all_warns():
    """The guard is still there for what cannot be promoted.

    A US is neither a document nor a resource: there is nothing to cite, and the
    chain is made without an extraction link rather than with an unnameable one.
    """
    from s3dgraphy.annotation import create_annotation_paradata

    g = Graph(graph_id="odd")
    g.add_node(StratigraphicUnit("US101", name="US101"))
    result = create_annotation_paradata(
        g, "US101", {"shape_kind": "rect", "rect": [0.1, 0.1, 0.2, 0.2]},
        "laterizio", "material")

    assert not [e for e in g.edges if e.edge_type == "generic_connection"]
    assert not [e for e in g.edges if e.edge_type == "extracted_from"]
    assert any("nothing to cite" in w for w in result.warnings), result.warnings


def test_annotation_region_geometry_survives_the_round_trip(tmp_path):
    """Export → import: the region comes back as a REGION, not as a string.

    The geometry travels as one selector literal and is parsed back, so this test
    is what pins those two functions as actual inverses.
    """
    original = _annotated_graph()
    importer = RDFImporter()
    rebuilt = importer.parse(_export(original, tmp_path / "a.ttl"))[0]
    assert not importer.warnings, importer.warnings

    regions = {n.node_id: n for n in rebuilt.nodes
               if type(n).__name__ == "AnnotationRegionNode"}
    assert len(regions) == 2

    by_kind = {r.shape_kind: r for r in regions.values()}
    rect = by_kind["rect"]
    assert [round(v, 6) for v in rect.rect] == [0.12, 0.30, 0.25, 0.18]
    assert rect.page == 3
    assert rect.data.get("resource_id") == "img1"   # the node's own copy

    poly = by_kind["polygon"]
    assert [[round(x, 6), round(y, 6)] for x, y in poly.points] == [
        [0.5, 0.5], [0.7, 0.52], [0.65, 0.8], [0.48, 0.72]]
    assert poly.page == 0

    # the four edges of each chain come back with their names
    types = [e.edge_type for e in rebuilt.edges]
    assert types.count("is_on_resource") == 2
    assert types.count("has_visual_reference") == 2
    assert types.count("has_property") == 2
    assert types.count("extracted_from") == 2
    assert "generic_connection" not in types


def test_annotation_paradata_roundtrip(tmp_path):
    """RT1 for the annotation chain: export → import → export is isomorphic."""
    original = _annotated_graph()
    ttl1 = _export(original, tmp_path / "1.ttl")
    rebuilt = RDFImporter().parse(ttl1)[0]
    ttl2 = _export(rebuilt, tmp_path / "2.ttl")

    g1, g2 = _rdf(ttl1), _rdf(ttl2)
    assert isomorphic(g1, g2), (
        f"annotation projection is not stable: {len(g1)} vs {len(g2)} triples")
    # declared, so a change in the projection is visible in the diff
    assert len(g1) == len(g2)


def test_annotation_region_has_its_own_class_in_the_projection(tmp_path):
    """em:AnnotationRegion, not "some E36": the region must be distinguishable
    from the picture it is on, or the round-trip cannot tell them apart."""
    from rdflib import Namespace, RDF as RDF_

    EM = Namespace("https://w3id.org/em/ontology#")
    CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
    store = _rdf(_export(_annotated_graph(), tmp_path / "a.ttl"))

    regions = set(store.subjects(RDF_.type, EM.AnnotationRegion))
    assert len(regions) == 2
    for r in regions:
        assert (r, RDF_.type, CRM.E36_Visual_Item) in store   # the CRM reading
        assert next(store.objects(r, EM.hasSelector), None) is not None
        assert next(store.objects(r, EM.isOnResource), None) is not None
        assert (r, CRM.P106i_forms_part_of, None) in store    # the core predicate

    # and the region is NOT confusable with the image it is on. A DocumentNode
    # projects as crm:E31_Document (it has no em: class of its own — it needs
    # none, E31 is not shared), so THAT is what must stay disjoint from the
    # regions: the picture and a region of the picture are two subjects.
    images = set(store.subjects(RDF_.type, CRM.E31_Document))
    assert images and not (images & regions)


def test_em_ttl_declares_the_annotation_region():
    """The rule of this batch: nothing is used before it is defined."""
    from rdflib import Namespace, RDF as RDF_, RDFS as RDFS_

    ttl = Path(__file__).resolve().parents[1] / (
        "src/s3dgraphy/JSON_config/em.ttl")
    onto = rdflib.Graph()
    onto.parse(str(ttl), format="turtle")
    EM = Namespace("https://w3id.org/em/ontology#")
    CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
    OWL_ = Namespace("http://www.w3.org/2002/07/owl#")

    assert (EM.AnnotationRegion, RDFS_.subClassOf, CRM.E36_Visual_Item) in onto
    assert (EM.isOnResource, RDFS_.subPropertyOf, CRM.P106i_forms_part_of) in onto
    assert (EM.hasSelector, RDF_.type, OWL_.DatatypeProperty) in onto
    assert (EM.onPage, RDF_.type, OWL_.DatatypeProperty) in onto


def test_annotation_region_does_not_collide_with_the_semantic_shape(tmp_path):
    """The two geometries are two classes, and the projection says which is which.

    A region in image space and a proxy hull in scene space would be
    indistinguishable if they shared a class — and then a reader could not know
    whether the numbers it holds are pixels of a photograph or metres of a site.
    """
    from s3dgraphy.nodes import SemanticShapeNode
    from rdflib import Namespace, RDF as RDF_

    EM = Namespace("https://w3id.org/em/ontology#")
    g = _annotated_graph("both")
    shape = SemanticShapeNode("shape1", "US101 proxy", type="proxy")
    shape.add_convex_shape([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0])
    g.add_node(shape)

    store = _rdf(_export(g, tmp_path / "a.ttl"))
    assert len(set(store.subjects(RDF_.type, EM.AnnotationRegion))) == 2
    assert len(set(store.subjects(RDF_.type, EM.SemanticShape))) == 1
    assert not (set(store.subjects(RDF_.type, EM.AnnotationRegion))
                & set(store.subjects(RDF_.type, EM.SemanticShape)))


def test_the_annotation_iris_enter_the_inverse_without_colliding():
    """The return leg is datamodel-driven, so the new class and edge must be
    findable there — and findable UNAMBIGUOUSLY, by either route.

    Two routes, because a projection can be written by two kinds of producer:
      · the SIGNATURE (the em: subproperty we emit) — unique by construction;
      · the CORE CRM predicate, which P106i and P138i share with others, and
        which is disambiguated by the endpoints.
    A CRM-only writer that emits only `P106i` is therefore still read as
    `is_on_resource`, and only as that.
    """
    from s3dgraphy.importer.rdf_importer import _InverseDatamodel

    inv = _InverseDatamodel()
    CRM_ = "http://www.cidoc-crm.org/cidoc-crm/"
    EM_ = "https://w3id.org/em/ontology#"

    # the CLASS: its own IRI, nobody else's
    assert inv.classes_by_iri[EM_ + "AnnotationRegion"] == ["AnnotationRegionNode"]
    assert not {i: n for i, n in inv.classes_by_iri.items() if len(n) > 1}

    # the EDGE, by signature
    assert inv.candidates_for_predicate(EM_ + "isOnResource") == ["is_on_resource"]
    # and by core predicate + endpoints
    assert inv.narrow_by_endpoints(
        inv.core_candidates_for_predicate(CRM_ + "P106i_forms_part_of"),
        "AnnotationRegionNode", "DocumentNode") == ["is_on_resource"]
    # P138i is shared by five edge types; the region as a target picks exactly one
    assert inv.narrow_by_endpoints(
        inv.core_candidates_for_predicate(CRM_ + "P138i_has_representation"),
        "PropertyNode", "AnnotationRegionNode") == ["has_visual_reference"]


# ─────────────────────────────────────────────────────────────────────────────
# PROXY-AS-PROPERTY — the geometry of a unit, with its provenance
#
# The proxy used to be a SemanticShapeNode hanging off the unit on its own, and a
# lone node cannot say where it came from. As a property it inherits the paradata
# chain, and one proxy can be synthesised from several sources. These tests pin
# the chain, the payload, and the fact that the payload survives the projection —
# which it did NOT before this batch: a proxy came back from the store as an
# empty shape with a label.
# ─────────────────────────────────────────────────────────────────────────────

def _proxy_graph(graph_id="proxy") -> Graph:
    """A unit whose geometry is known from two sources, one of them a region
    traced on a photograph — plus an RMDoc that declares how it was posed."""
    from s3dgraphy.annotation import create_annotation_paradata
    from s3dgraphy.geometry import create_geometry_proxy
    from s3dgraphy.nodes import RepresentationModelDocNode

    g = Graph(graph_id=graph_id)
    g.add_node(StratigraphicUnit("US101", name="US101"))
    g.add_node(DocumentNode("D1", name="Foto Maiuri 1931", url="maiuri.jpg"))
    g.add_node(DocumentNode("D2", name="Mesh fotogrammetrica 2024"))

    # the 2D annotation: an interpretation traced on the photograph
    annot = create_annotation_paradata(
        g, "D1", {"shape_kind": "polygon",
                  "points": [[0.2, 0.2], [0.6, 0.25], [0.55, 0.7], [0.18, 0.62]]},
        interpretation="estensione del paramento", property_type="material",
        target_unit_id="US101")

    # the proxy: read from the traced region AND from the mesh
    create_geometry_proxy(
        g, "US101",
        {"convexshapes": [[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]],
         "spheres": [[0.5, 0.5, 0.5, 0.25]]},
        extractor_sources=[annot.region_id, "D2"])

    # the spatialisation of the photograph, with a property of its own
    g.add_node(RepresentationModelDocNode("rmd1", "Foto Maiuri, posata"))
    g.add_node(PropertyNode("pose1", name="methodology_used",
                            value="feature matching su 8 punti noti",
                            property_type="methodology_used"))
    g.add_edge("e_rmd_prop", "rmd1", "pose1", "has_property")
    g.add_edge("e_doc_rmd", "D1", "rmd1", "has_representation_model_doc")
    return g


def test_geometry_proxy_is_a_property_that_carries_its_payload():
    from s3dgraphy.geometry import create_geometry_proxy

    g = Graph(graph_id="one_source")
    g.add_node(StratigraphicUnit("US101", name="US101"))
    g.add_node(DocumentNode("D1", name="Mesh"))
    result = create_geometry_proxy(
        g, "US101", {"convexshapes": [[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]]},
        extractor_sources=["D1"])

    assert result.warnings == [], result.warnings
    prop = g.find_node_by_id(result.property_id)
    assert type(prop).__name__ == "PropertyNode"
    assert prop.property_type == "geometry"
    shape = g.find_node_by_id(result.shape_id)
    assert type(shape).__name__ == "SemanticShapeNode"
    assert shape.convexshapes == [[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]]

    edges = {(e.edge_type, e.edge_source, e.edge_target) for e in g.edges}
    assert ("has_property", "US101", result.property_id) in edges
    assert ("has_semantic_shape", result.property_id, result.shape_id) in edges
    assert ("has_data_provenance", result.property_id, result.extractor_ids[0]) in edges
    assert ("extracted_from", result.extractor_ids[0], "D1") in edges
    # ONE source: no combiner is invented
    assert result.combiner_id is None
    assert not [n for n in g.nodes if type(n).__name__ == "CombinerNode"]
    assert not [e for e in g.edges if e.edge_type == "generic_connection"]


def test_two_sources_are_joined_by_a_combiner():
    """"Synthesised from two readings" is the ordinary paradata chain, not a
    mechanism of its own."""
    from s3dgraphy.geometry import create_geometry_proxy

    g = Graph(graph_id="two_sources")
    g.add_node(StratigraphicUnit("US101", name="US101"))
    g.add_node(DocumentNode("D1", name="Mesh"))
    g.add_node(DocumentNode("D2", name="Foto 1931"))
    result = create_geometry_proxy(g, "US101", {"url": "US101_proxy.glb"},
                                   extractor_sources=["D1", "D2"])

    assert result.combiner_id is not None
    assert len(result.extractor_ids) == 2
    edges = {(e.edge_type, e.edge_source, e.edge_target) for e in g.edges}
    for extractor_id in result.extractor_ids:
        assert ("combines", result.combiner_id, extractor_id) in edges
    # the property hangs off the COMBINER: it is the conclusion of the chain
    assert ("has_data_provenance", result.property_id, result.combiner_id) in edges
    assert not [e for e in g.edges
                if e.edge_type == "has_data_provenance"
                and e.edge_target in result.extractor_ids]


def test_geometry_proxy_is_idempotent():
    from s3dgraphy.geometry import create_geometry_proxy

    g = _proxy_graph()
    nodes_before, edges_before = len(g.nodes), len(g.edges)
    again = create_geometry_proxy(
        g, "US101",
        {"convexshapes": [[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]],
         "spheres": [[0.5, 0.5, 0.5, 0.25]]},
        extractor_sources=[n.node_id for n in g.nodes
                           if type(n).__name__ == "AnnotationRegionNode"] + ["D2"])
    assert again.created is False
    assert (len(g.nodes), len(g.edges)) == (nodes_before, edges_before)


def test_a_proxy_with_no_payload_is_refused():
    """A shape claiming a volume nobody described is worse than an error."""
    from s3dgraphy.geometry import create_geometry_proxy

    g = Graph(graph_id="empty")
    g.add_node(StratigraphicUnit("US101", name="US101"))
    with pytest.raises(ValueError):
        create_geometry_proxy(g, "US101", {})


def test_an_extractor_can_cite_an_annotation_region():
    """A traced region is evidence — a more precise citation than the whole
    picture, and it reaches its own source through is_on_resource."""
    g = _proxy_graph()
    region = next(n for n in g.nodes if type(n).__name__ == "AnnotationRegionNode")
    citing = [e for e in g.edges
              if e.edge_type == "extracted_from" and e.edge_target == region.node_id]
    assert len(citing) == 1
    # and from there the source is still reachable
    onto_image = [e for e in g.edges
                  if e.edge_type == "is_on_resource" and e.edge_source == region.node_id]
    assert [e.edge_target for e in onto_image] == ["D1"]
    assert not [e for e in g.edges if e.edge_type == "generic_connection"]


def test_an_rmdoc_can_declare_how_it_was_posed():
    """STEP C: the structural permission, and only that.

    A spatialisation is a reconstruction, so it must be able to say how it is
    known. The mathematics of the pose is not modelled here — a property and its
    chain are."""
    g = _proxy_graph()
    edges = {(e.edge_type, e.edge_source, e.edge_target) for e in g.edges}
    assert ("has_property", "rmd1", "pose1") in edges
    assert not [e for e in g.edges if e.edge_type == "generic_connection"]

    # a plain RepresentationModel is NOT a source of has_property
    assert not Graph.validate_connection("representation_model", "property",
                                         "has_property")
    assert Graph.validate_connection("representation_model_doc", "property",
                                     "has_property")


def test_the_semantic_shape_payload_survives_the_round_trip(tmp_path):
    """It did not, before this batch: the numbers were never projected."""
    original = _proxy_graph()
    importer = RDFImporter()
    rebuilt = importer.parse(_export(original, tmp_path / "a.ttl"))[0]
    assert not importer.warnings, importer.warnings

    shape = next(n for n in rebuilt.nodes
                 if type(n).__name__ == "SemanticShapeNode")
    assert shape.convexshapes == [[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]]
    assert shape.spheres == [[0.5, 0.5, 0.5, 0.25]]
    assert shape.type == "proxy"

    prop = next(n for n in rebuilt.nodes
                if type(n).__name__ == "PropertyNode"
                and getattr(n, "property_type", None) == "geometry")
    edges = {(e.edge_type, e.edge_source, e.edge_target) for e in rebuilt.edges}
    assert ("has_semantic_shape", prop.node_id, shape.node_id) in edges
    assert ("has_property", "US101", prop.node_id) in edges


def test_geometry_proxy_roundtrip(tmp_path):
    """RT1 for the whole picture: proxy + provenance + annotation + RMDoc."""
    original = _proxy_graph()
    ttl1 = _export(original, tmp_path / "1.ttl")
    rebuilt = RDFImporter().parse(ttl1)[0]
    ttl2 = _export(rebuilt, tmp_path / "2.ttl")

    g1, g2 = _rdf(ttl1), _rdf(ttl2)
    assert isomorphic(g1, g2), (
        f"proxy projection is not stable: {len(g1)} vs {len(g2)} triples\n"
        f"only in first : {sorted(set(g1) - set(g2))[:6]}\n"
        f"only in second: {sorted(set(g2) - set(g1))[:6]}")
    assert len(g1) == len(g2)

    # every edge type of the chain came back with its name
    types = [e.edge_type for e in rebuilt.edges]
    for expected in ("has_property", "has_semantic_shape", "has_data_provenance",
                     "combines", "extracted_from", "is_on_resource",
                     "has_visual_reference", "has_representation_model_doc"):
        assert expected in types, (expected, sorted(set(types)))
    assert "generic_connection" not in types


def test_the_geometry_qualia_projects_as_its_own_class(tmp_path):
    """`geometry` is a registered qualia type, so the property carries the CIDOC
    class the vocabulary gives it — not the generic E54_Dimension."""
    from rdflib import Namespace, RDF as RDF_

    CRMGEO = Namespace("http://www.cidoc-crm.org/extensions/crmgeo/")
    CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
    EM = Namespace("https://w3id.org/em/ontology#")
    store = _rdf(_export(_proxy_graph(), tmp_path / "a.ttl"))

    geometry_props = set(store.subjects(EM.hasQualiaType, rdflib.Literal("geometry")))
    assert len(geometry_props) == 1
    prop = next(iter(geometry_props))
    assert (prop, RDF_.type, CRMGEO.SP5_Geometric_Place_Expression) in store
    assert (prop, RDF_.type, CRM.E54_Dimension) not in store


def test_em_ttl_declares_the_payload_properties():
    """Nothing is emitted before it is defined."""
    from rdflib import Namespace, RDF as RDF_

    ttl = Path(__file__).resolve().parents[1] / (
        "src/s3dgraphy/JSON_config/em.ttl")
    onto = rdflib.Graph()
    onto.parse(str(ttl), format="turtle")
    EM = Namespace("https://w3id.org/em/ontology#")
    OWL_ = Namespace("http://www.w3.org/2002/07/owl#")
    assert (EM.convexShape, RDF_.type, OWL_.DatatypeProperty) in onto
    assert (EM.sphere, RDF_.type, OWL_.DatatypeProperty) in onto


# ─────────────────────────────────────────────────────────────────────────────
# IDENTITY — the ORCID iD is the identity; `verified` says whether it was checked
#
# Claim now, verify later. Someone on a dig with no network declares their iD
# and starts working: the authorship is real from the first node. What waits for
# a connection is PUBLISHING AS that person — so `verified` must survive the
# projection, and "not verified" must never be mistaken for a claim of falsity.
# ─────────────────────────────────────────────────────────────────────────────

EM_NS = "https://w3id.org/em/ontology#"


def _identity_graph(graph_id="ident") -> Graph:
    from s3dgraphy.nodes import AuthorAINode

    g = Graph(graph_id=graph_id)
    g.add_node(AuthorNode("a1", name="Emanuel", surname="Demetrescu",
                          orcid="0000-0002-1825-0097", verified=True))
    g.add_node(AuthorNode("a2", name="Sul campo", surname="Rossi",
                          orcid="0000-0001-5109-3700", verified=False))
    g.add_node(AuthorAINode("ai1", name="Claude", model="claude-opus-5"))
    g.add_node(StratigraphicUnit("US101", name="US101"))
    g.add_edge("e1", "US101", "a1", "has_author")
    return g


def test_author_verified_defaults_to_claimed():
    """Every author authored before this field existed reads as CLAIMED — which
    is what they are: nobody checked them."""
    a = AuthorNode("a", name="X", orcid="0000-0002-1825-0097")
    assert a.data["verified"] is False


def test_only_the_boolean_true_verifies():
    """An identity must not be promoted by a string that happens to be truthy.

    `bool("false")` is True, and this value decides whether a publication may
    claim to be by this person — so the coercion is `is True`, not `bool()`.
    """
    for value in (True,):
        assert AuthorNode("a", verified=value).data["verified"] is True
    for value in ("false", "true", "yes", 1, 0, None, [], object()):
        assert AuthorNode("a", verified=value).data["verified"] is False, value


def test_verified_survives_the_round_trip(tmp_path):
    original = _identity_graph()
    importer = RDFImporter()
    rebuilt = importer.parse(_export(original, tmp_path / "a.ttl"))[0]
    assert not importer.warnings, importer.warnings

    by_id = {n.node_id: n for n in rebuilt.nodes}
    assert by_id["a1"].data["verified"] is True
    assert by_id["a1"].data["orcid"] == "0000-0002-1825-0097"
    assert by_id["a2"].data["verified"] is False
    assert by_id["a2"].data["orcid"] == "0000-0001-5109-3700"
    assert by_id["ai1"].data["verified"] is False


def test_unverified_authors_say_nothing_rather_than_saying_false(tmp_path):
    """Absence, not a negative assertion.

    "Nobody has checked yet" is what an empty graph already says. Writing
    `verified false` into a store would turn that silence into a claim that
    travels — and a reader downstream cannot tell a claim of falsity from a
    check that has not happened.
    """
    from rdflib import Namespace

    EM_ = Namespace(EM_NS)
    store = _rdf(_export(_identity_graph(), tmp_path / "a.ttl"))
    triples = list(store.triples((None, EM_.orcidVerified, None)))
    assert len(triples) == 1                      # the verified author, and only him
    assert bool(triples[0][2].toPython()) is True  # never a `false` literal


def test_identity_projection_is_isomorphic(tmp_path):
    """RT1 for the identity layer: the second projection is the same graph."""
    original = _identity_graph()
    ttl1 = _export(original, tmp_path / "1.ttl")
    rebuilt = RDFImporter().parse(ttl1)[0]
    ttl2 = _export(rebuilt, tmp_path / "2.ttl")
    g1, g2 = _rdf(ttl1), _rdf(ttl2)
    assert isomorphic(g1, g2), f"{len(g1)} vs {len(g2)} triples"
    assert len(g1) == len(g2)


def test_em_ttl_declares_orcid_verified():
    from rdflib import Namespace, RDF as RDF_, RDFS as RDFS_

    ttl = Path(__file__).resolve().parents[1] / "src/s3dgraphy/JSON_config/em.ttl"
    onto = rdflib.Graph()
    onto.parse(str(ttl), format="turtle")
    EM_ = Namespace(EM_NS)
    OWL_ = Namespace("http://www.w3.org/2002/07/owl#")
    XSD_ = Namespace("http://www.w3.org/2001/XMLSchema#")
    assert (EM_.orcidVerified, RDF_.type, OWL_.DatatypeProperty) in onto
    assert (EM_.orcidVerified, RDFS_.domain, EM_.Author) in onto
    assert (EM_.orcidVerified, RDFS_.range, XSD_.boolean) in onto
