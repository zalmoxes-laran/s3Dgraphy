"""Reverse edges in the RDF projection: the same fact, written either way.

The connections datamodel declares `reverse` on 49 of its 56 canonical edge
types, but keys `edge_types` by the canonical name alone. The exporter read
that dictionary raw, so a graph holding an `is_before` edge found no entry and
fell through to the generic fallback — and the fallback does not lose the
relation, it states a DIFFERENT one: `P130_shows_features_of`, a claim about
morphological similarity that nobody made.

RDF keeps no record of which way an author drew an arrow. `A is_after B` and
`B is_before A` are the same fact, so they must leave as the same triple.
"""

from pathlib import Path

import pytest

rdflib = pytest.importorskip("rdflib")

from s3dgraphy.graph import Graph
from s3dgraphy.nodes import StratigraphicUnit
from s3dgraphy.exporter.rdf_exporter import RDFExporter

CRM = "http://www.cidoc-crm.org/cidoc-crm/"


def _graph(graph_id, source, edge_type, target):
    g = Graph(graph_id=graph_id)
    for n in (source, target):
        g.add_node(StratigraphicUnit(node_id=n, name=n, description=""))
    g.add_edge("e", source, target, edge_type)
    return g


def _unit_triples(graph, path):
    RDFExporter(str(path), format="turtle").export_single_graph(graph)
    g = rdflib.Graph()
    g.parse(str(path), format="turtle")
    return {
        (str(s).rsplit("/", 1)[-1], str(p), str(o).rsplit("/", 1)[-1])
        for s, p, o in g
        if "/node/US" in str(s) and "/node/US" in str(o)
    }


def test_the_two_directions_produce_the_same_triple(tmp_path):
    # US1 is_after US2  ==  US2 is_before US1. One stratigraphic fact.
    canonical = _unit_triples(_graph("ga", "US1", "is_after", "US2"), tmp_path / "a.ttl")
    reverse = _unit_triples(_graph("gb", "US2", "is_before", "US1"), tmp_path / "b.ttl")
    assert canonical == reverse
    # subject and object are the canonical pair in both cases, whichever way
    # the edge was drawn
    assert {(s, o) for s, _, o in canonical} == {("US1", "US2")}
    assert CRM + "P120_occurs_before" in {p for _, p, _ in canonical}


def test_a_reverse_edge_no_longer_falls_through_to_the_generic_predicate(tmp_path):
    # the regression this file exists for: P130 is a claim about shared
    # features, and asserting it here would be an invention.
    triples = _unit_triples(_graph("gc", "US2", "is_before", "US1"), tmp_path / "c.ttl")
    assert not any(p.endswith("P130_shows_features_of") for _, p, _ in triples)


def test_the_fallback_still_catches_an_unrecognised_edge(tmp_path):
    # counterexample: the fallback must survive, or an edge we cannot map
    # would vanish silently instead of degrading visibly. Note that Graph
    # rewrites an unknown name to `generic_connection` on add_edge, so the
    # fallback is reached through that, not through a stray string.
    g = _graph("gd", "US1", "not_an_edge_type", "US2")
    assert g.edges[0].edge_type == "generic_connection"
    triples = _unit_triples(g, tmp_path / "d.ttl")
    assert CRM + "P130_shows_features_of" in {p for _, p, _ in triples}
    assert not any("P120" in p for _, p, _ in triples)


def test_direction_resolution_is_reported_and_bounded():
    from s3dgraphy.exporter.rdf_exporter import _Datamodel
    dm = _Datamodel()
    assert dm.resolve_edge_direction("is_before") == ("is_after", True)
    assert dm.resolve_edge_direction("is_after") == ("is_after", False)
    # an unknown name passes through untouched rather than guessing
    assert dm.resolve_edge_direction("not_an_edge_type") == ("not_an_edge_type", False)
    # every declared reverse is indexed, and none collides with a canonical
    canonicals = set(dm.connections_datamodel["edge_types"])
    assert len(dm._reverse_of) == 49
    assert not (set(dm._reverse_of) & canonicals)


# ── the extension predicates ─────────────────────────────────────────────────
# The exporter documents a "dual emission" pattern: the core CRM predicate for
# CRM-only readers, plus the specific extension subproperty for expressive
# SPARQL. It was firing for 21 of the 47 declared extension_mappings, because
# the code→namespace heuristic only knew the letters the extensions use for
# their CLASSES. CRMarchaeo properties are AP<n> (A<n> are classes); CRMdig
# properties are L<n> (D<n> are classes); CRMinf properties are J<n> (I<n> are
# classes). Checked against CRMarchaeo v2.1.1, CRMdig v5.0, CRMinf v1.0.

CRMARCHAEO_NS = "http://www.cidoc-crm.org/extensions/crmarchaeo/"
CRMDIG_NS = "http://www.cidoc-crm.org/extensions/crmdig/"
CRMINF_NS = "http://www.cidoc-crm.org/extensions/crminf/"


@pytest.mark.parametrize("code,expected_ns,", [
    ("AP28_occurs_before", CRMARCHAEO_NS),
    ("AP4_produced_surface", CRMARCHAEO_NS),
    ("AP22_is_equal_in_time_to", CRMARCHAEO_NS),
])
def test_extension_property_codes_resolve(code, expected_ns):
    from s3dgraphy.exporter.rdf_exporter import _resolve_prefixed
    iri = _resolve_prefixed(code)
    assert iri is not None, f"{code} did not resolve"
    assert str(iri) == expected_ns + code


def test_crmdig_and_crminf_property_codes_stay_unresolved():
    """Deliberate, and pinned so it is a decision rather than an oversight.

    L<n> and J<n> are the PROPERTY letters of CRMdig and CRMinf and they do
    exist, but J7 is already spoken for: the importer treats it as part of the
    CRMinf belief skeleton (ARTEFACT_PREDICATES). Resolving it here makes the
    exporter emit it as `extracted_from`'s signature, the importer discards it,
    and the edge does not survive the round trip. Which reading of J7 wins is a
    modelling decision, not a heuristic.
    """
    from s3dgraphy.exporter.rdf_exporter import _resolve_prefixed
    assert _resolve_prefixed("J7_is_based_on_evidence_from") is None
    assert _resolve_prefixed("L22_created_derivative") is None


def test_class_codes_still_resolve_to_their_own_namespaces():
    # counterexample: widening the heuristic must not steal the class letters.
    from s3dgraphy.exporter.rdf_exporter import _resolve_prefixed
    assert str(_resolve_prefixed("A8_Stratigraphic_Unit")).startswith(CRMARCHAEO_NS)
    assert str(_resolve_prefixed("D1_Digital_Object")).startswith(CRMDIG_NS)
    assert str(_resolve_prefixed("I4_Proposition_Set")).startswith(CRMINF_NS)
    assert "cidoc-crm/E" in str(_resolve_prefixed("E54_Dimension"))


def test_a_stratigraphic_edge_now_carries_its_crmarchaeo_predicate(tmp_path):
    # the point of the repair, end to end: AP28 travels beside P120.
    triples = _unit_triples(_graph("ge", "US1", "is_after", "US2"), tmp_path / "e.ttl")
    predicates = {p for _, p, _ in triples}
    assert CRM + "P120_occurs_before" in predicates
    assert CRMARCHAEO_NS + "AP28_occurs_before" in predicates
