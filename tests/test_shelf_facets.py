"""Shelf v2 (Session C3) — hatting FACETS: RM / RMSF / RMDoc / Document.

The role determines the facet, and the facets are NOT exclusive: the same
Resource may be an RM (of the epoch it depicts) AND a Document (a source in a
paradata chain). Every facet keeps the P67 hinge
(facet ─has_linked_resource→ LinkNode); what changes is the edge towards what it
represents / documents:

  RM       ─has_first_epoch / survive_in_epoch→ EpochNode(s)
  SF       ─has_representation_model_sf→ RMSF
  Document ─has_representation_model_doc→ RMDoc      (free / manual placement)
  Extractor ─extracted_from→ Document                (the paradata entry)
  strat    ─has_documentation→ Document

Every attach is validated against the datamodel (``Graph.validate_connection``),
so a wrong target is refused instead of degrading to a ``generic_connection``.
"""

import pytest

from s3dgraphy import api
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import (DocumentNode, RepresentationModelDocNode,
                             RepresentationModelSpecialFindNode)
from s3dgraphy.nodes.epoch_node import EpochNode
from s3dgraphy.nodes.extractor_node import ExtractorNode
from s3dgraphy.nodes.stratigraphic_node import SpecialFindUnit, StratigraphicUnit


def _shelf_with_resource(rid="r1", url="/lib/photogrammetry.glb"):
    shelf = api.new_shelf()
    api.add_to_shelf(shelf, url, resource_id=rid, name="Photogrammetric model",
                     resource_type="proxy_model",
                     origin={"repo": "filesystem", "capabilities": [], "scope": None})
    return shelf


def _study_with_epochs():
    study = Graph(graph_id="study")
    study.add_node(EpochNode(node_id="ep20", name="XX century",
                             start_time=1900, end_time=2000))
    study.add_node(EpochNode(node_id="ep21", name="XXI century",
                             start_time=2000, end_time=2100))
    return study


def _has(graph, src, tgt, edge_type):
    return any(e.edge_source == src and e.edge_target == tgt
               and e.edge_type == edge_type for e in graph.edges)


def _p67(graph, facet_id, resource_id):
    return _has(graph, facet_id, resource_id, "has_linked_resource")


# ── RM: binds to one or more EPOCHS (C3 correction of C2.1) ────────────────────
def test_rm_binds_to_epochs_first_then_survive():
    shelf, study = _shelf_with_resource(), _study_with_epochs()
    out = api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="m_model",
                                          epochs=["ep20", "ep21"])
    assert out["epochs"] == ["ep20", "ep21"] and out["skipped"] == []
    assert out["attached"] is True
    assert _p67(study, "m_model", "r1")                       # the R0 hinge
    assert _has(study, "m_model", "ep20", "has_first_epoch")  # first epoch
    assert _has(study, "m_model", "ep21", "survive_in_epoch")  # the further ones


def test_rm_epoch_attach_is_idempotent():
    shelf, study = _shelf_with_resource(), _study_with_epochs()
    api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="m_model",
                                    epochs=["ep20"])
    out = api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="m_model",
                                          epochs=["ep20"])
    assert out["created"] is False and out["epochs"] == ["ep20"]
    assert len([e for e in study.edges if e.edge_type == "has_first_epoch"]) == 1
    assert len([n for n in study.nodes if n.node_type == "representation_model"]) == 1
    # an epoch the RM is already bound to is NEVER re-bound as survive_in_epoch
    assert not any(e.edge_type == "survive_in_epoch" for e in study.edges)


def test_rm_second_call_adds_further_epoch_as_survive():
    shelf, study = _shelf_with_resource(), _study_with_epochs()
    api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="m_model",
                                    epochs=["ep20"])
    out = api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="m_model",
                                          epochs=["ep21"])
    assert out["epochs"] == ["ep21"]
    assert _has(study, "m_model", "ep21", "survive_in_epoch")  # first is taken


def test_rm_attach_to_is_the_single_epoch_alias():
    shelf, study = _shelf_with_resource(), _study_with_epochs()
    out = api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="m_model",
                                          attach_to="ep20")
    assert out["epochs"] == ["ep20"]
    assert _has(study, "m_model", "ep20", "has_first_epoch")


# ── RMSF: binds to a Special Find ─────────────────────────────────────────────
def test_rmsf_binds_to_special_find():
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    study.add_node(SpecialFindUnit(node_id="SF1", name="Capital"))
    out = api.hat_as_rmsf(study, "r1", shelf=shelf, rmsf_id="cap_rmsf",
                          attach_to="SF1")
    assert out["created"] and out["attached"] is True
    rmsf = study.find_node_by_id("cap_rmsf")
    assert isinstance(rmsf, RepresentationModelSpecialFindNode)
    assert _p67(study, "cap_rmsf", "r1")
    assert _has(study, "SF1", "cap_rmsf", "has_representation_model_sf")


def test_rmsf_refuses_a_non_sf_target():
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    study.add_node(StratigraphicUnit(node_id="US1", name="US 1"))
    out = api.hat_as_rmsf(study, "r1", shelf=shelf, rmsf_id="cap_rmsf",
                          attach_to="US1")
    assert out["attached"] is False
    assert not any(e.edge_type == "generic_connection" for e in study.edges)


# ── RMDoc: binds to a Document; graded by the geometry axis (Q-C) ─────────────
def test_rmdoc_binds_to_document_and_is_not_anchored():
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    study.add_node(DocumentNode(node_id="D1", name="D.1"))
    out = api.hat_as_rmdoc(study, "r1", shelf=shelf, rmdoc_id="D1_rm_doc",
                           attach_to="D1")
    assert out["attached"] is True
    rmdoc = study.find_node_by_id("D1_rm_doc")
    assert isinstance(rmdoc, RepresentationModelDocNode)
    assert _p67(study, "D1_rm_doc", "r1")
    assert _has(study, "D1", "D1_rm_doc", "has_representation_model_doc")
    # An RMDoc is NOT anchored to an epoch or a stratigraphic unit.
    assert not any(e.edge_source == "D1_rm_doc"
                   and e.edge_type in ("has_first_epoch", "survive_in_epoch")
                   for e in study.edges)
    # No geometry asked for → none asserted. Silence is not a grade.
    assert out["geometry"] is None
    assert "geometry" not in rmdoc.data


def test_rmdoc_records_the_placement_qualia_on_the_geometry_axis():
    """Q-C: the metric authority of the placement lives on the RMDoc — the
    spatial instance — not on the Document."""
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    study.add_node(DocumentNode(node_id="D1", name="D.1"))
    out = api.hat_as_rmdoc(study, "r1", shelf=shelf, rmdoc_id="D1_rm_doc",
                           attach_to="D1", geometry="symbolic")
    assert out["geometry"] == "symbolic"
    assert study.find_node_by_id("D1_rm_doc").data["geometry"] == "symbolic"
    # …and the Document is left alone: it carries no position.
    assert "geometry" not in study.find_node_by_id("D1").data


def test_rmdoc_geometry_is_validated_against_the_datamodel():
    """The vocabulary comes from em_visual_rules.json, not from a literal."""
    from s3dgraphy.nodes.document_node import DOCUMENT_GEOMETRIES

    assert "symbolic" in DOCUMENT_GEOMETRIES
    # The full metric-authority ladder, in order, ahead of em_based.
    ladder = ("reality_based", "observable", "asserted", "symbolic")
    assert DOCUMENT_GEOMETRIES[:4] == ladder
    assert DOCUMENT_GEOMETRIES.index("em_based") > DOCUMENT_GEOMETRIES.index("symbolic")

    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    study.add_node(DocumentNode(node_id="D1", name="D.1"))
    with pytest.raises(ValueError):
        api.hat_as_rmdoc(study, "r1", shelf=shelf, attach_to="D1",
                         geometry="manual")   # the retired C3 literal


# ── Document: a SOURCE, no placement — the paradata entry ─────────────────────
def test_document_references_resource_without_placement():
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    out = api.hat_as_document(study, "r1", shelf=shelf, doc_id="D.7",
                              name="D.7", content_nature="3d_object",
                              geometry="reality_based")
    assert out["created"] and out["doc_id"] == "D.7"
    doc = study.find_node_by_id("D.7")
    assert isinstance(doc, DocumentNode) and doc.node_type == "document"
    assert doc.data.get("content_nature") == "3d_object"      # facets passed through
    assert doc.data.get("geometry") == "reality_based"
    assert doc.is_canonical() is True          # the canonical-document flag
    assert _p67(study, "D.7", "r1")
    # a Document is NOT spatialized: no representation node was created
    assert not any(n.node_type.startswith("representation") for n in study.nodes)


def test_document_attaches_to_extractor_as_paradata_entry():
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    study.add_node(ExtractorNode(node_id="EX1", name="measure extraction"))
    out = api.hat_as_document(study, "r1", shelf=shelf, doc_id="D.7",
                              attach_to="EX1")
    assert out["attached"] is True and out["attach_edge"] == "extracted_from"
    assert _has(study, "EX1", "D.7", "extracted_from")


def test_document_attaches_to_stratigraphic_unit_as_documentation():
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    study.add_node(StratigraphicUnit(node_id="US1", name="US 1"))
    out = api.hat_as_document(study, "r1", shelf=shelf, doc_id="D.7",
                              attach_to="US1")
    assert out["attached"] is True and out["attach_edge"] == "has_documentation"
    assert _has(study, "US1", "D.7", "has_documentation")


def test_document_reuses_a_node_the_caller_created():
    """EMTools builds the DocumentNode with create_master_document_node and passes
    its id — ONE document shape, the op only wires the P67 hinge."""
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    study.add_node(DocumentNode(node_id="D.9", name="D.9", description="mine"))
    out = api.hat_as_document(study, "r1", shelf=shelf, doc_id="D.9", name="ignored")
    assert out["doc_id"] == "D.9"
    doc = study.find_node_by_id("D.9")
    assert doc.name == "D.9" and doc.description == "mine"    # untouched
    assert len([n for n in study.nodes if n.node_type == "document"]) == 1
    assert _p67(study, "D.9", "r1")


def test_document_is_idempotent():
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    a = api.hat_as_document(study, "r1", shelf=shelf, doc_id="D.7")
    b = api.hat_as_document(study, "r1", shelf=shelf, doc_id="D.7")
    assert a["doc_id"] == b["doc_id"] and b["created"] is False
    assert len([n for n in study.nodes if n.node_type == "document"]) == 1
    assert len([e for e in study.edges if e.edge_type == "has_linked_resource"]) == 1


# ── facets are NOT exclusive ──────────────────────────────────────────────────
def test_same_resource_can_be_rm_and_document():
    """The photogrammetry case: an RM of the epoch it depicts AND a source in a
    reasoning chain. ONE Resource (stable ID), two facets, one P67 hinge each."""
    shelf, study = _shelf_with_resource(), _study_with_epochs()
    study.add_node(ExtractorNode(node_id="EX1", name="measure extraction"))
    rm = api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="m_model",
                                         epochs=["ep20"])
    doc = api.hat_as_document(study, "r1", shelf=shelf, doc_id="D.7", attach_to="EX1")
    assert rm["created"] and doc["created"]
    assert len([n for n in study.nodes if n.node_type == "link"]) == 1  # one Resource
    assert _p67(study, "m_model", "r1") and _p67(study, "D.7", "r1")
    assert _has(study, "m_model", "ep20", "has_first_epoch")
    assert _has(study, "EX1", "D.7", "extracted_from")


def test_resource_stays_on_the_shelf_across_facets():
    shelf, study = _shelf_with_resource(), _study_with_epochs()
    api.hat_as_representation_model(study, "r1", shelf=shelf, epochs=["ep20"])
    api.hat_as_document(study, "r1", shelf=shelf)
    assert [e["id"] for e in api.list_shelf(shelf)] == ["r1"]  # the library keeps it


@pytest.mark.parametrize("op", ["hat_as_rmsf", "hat_as_rmdoc", "hat_as_document"])
def test_facets_require_the_resource_without_a_shelf(op):
    with pytest.raises(ValueError):
        getattr(api, op)(Graph(graph_id="study"), "nope")


# ── attach_candidates: the picker is driven by the datamodel ──────────────────
def _mixed_study():
    study = _study_with_epochs()
    study.add_node(StratigraphicUnit(node_id="US1", name="US 1"))
    study.add_node(SpecialFindUnit(node_id="SF1", name="Capital"))
    study.add_node(DocumentNode(node_id="D1", name="D.1"))
    study.add_node(ExtractorNode(node_id="EX1", name="measures"))
    return study


def test_attach_candidates_rm_are_epochs_in_chronological_order():
    got = api.attach_candidates("rm", _mixed_study())
    assert [c["id"] for c in got] == ["ep20", "ep21"]        # oldest first
    assert all(c["edge"] == "has_first_epoch" for c in got)


def test_attach_candidates_rmsf_are_special_finds_only():
    got = api.attach_candidates("rmsf", _mixed_study())
    assert [c["id"] for c in got] == ["SF1"]
    assert got[0]["edge"] == "has_representation_model_sf"


def test_attach_candidates_rmdoc_are_document_side_nodes():
    got = {c["id"] for c in api.attach_candidates("rmdoc", _mixed_study())}
    assert got == {"D1", "EX1"}          # Document / Extractor / Combiner


def test_attach_candidates_document_carry_their_edge():
    got = {c["id"]: c["edge"] for c in api.attach_candidates("document", _mixed_study())}
    assert got["EX1"] == "extracted_from"        # the paradata chain
    assert got["US1"] == "has_documentation"     # P70i
    assert "ep20" not in got                     # an epoch documents nothing


def test_attach_candidates_rejects_an_unknown_facet():
    with pytest.raises(ValueError):
        api.attach_candidates("nope", Graph(graph_id="study"))
