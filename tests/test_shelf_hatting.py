"""Shelf v2 (Session C2) — hat-as-RepresentationModel + remove cleanup.

Verifies: hat a shelf resource into a study graph as an RM (reference-by-stable-ID,
RM ─has_linked_resource→ Resource / P67; optional entity ─has_representation_model→
RM / P138i); reuse-not-duplicate + idempotent; and remove_resource cleaning the
orphan acquisition event only when the resource is unreferenced.
"""

import pytest

from s3dgraphy import api
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import DTCAcquisitionNode, RepresentationModelNode


def _shelf_with_resource(rid="r1", url="/lib/lamp.glb", kind="proxy_model"):
    shelf = api.new_shelf()
    api.add_to_shelf(shelf, url, resource_id=rid, name="Lamp",
                     resource_type=kind,
                     origin={"repo": "filesystem", "capabilities": [], "scope": None})
    return shelf


# ── hat as RM ──────────────────────────────────────────────────────────────────
def test_hat_creates_rm_referencing_resource_by_id():
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    out = api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="lamp_model")
    assert out["created"] and out["rm_id"] == "lamp_model"
    # the Resource is referenced into the study by its SAME stable id (R0 hinge)
    res = study.find_node_by_id("r1")
    assert res is not None and res.node_type == "link"
    assert (res.data or {}).get("origin", {}).get("repo") == "filesystem"  # origin carried
    # the RM node references the resource via has_linked_resource (P67)
    rm = study.find_node_by_id("lamp_model")
    assert isinstance(rm, RepresentationModelNode) and rm.node_type == "representation_model"
    assert any(e.edge_source == "lamp_model" and e.edge_target == "r1"
               and e.edge_type == "has_linked_resource" for e in study.edges)


def test_hat_is_idempotent():
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    a = api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="lamp_model")
    b = api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="lamp_model")
    assert a["rm_id"] == b["rm_id"] and b["created"] is False
    rms = [n for n in study.nodes if n.node_type == "representation_model"]
    links = [n for n in study.nodes if n.node_type == "link"]
    edges = [e for e in study.edges if e.edge_type == "has_linked_resource"]
    assert len(rms) == 1 and len(links) == 1 and len(edges) == 1  # no duplicates


def test_hat_attach_to_entity_p138i():
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit
    shelf = _shelf_with_resource()
    study = Graph(graph_id="study")
    study.add_node(StratigraphicUnit(node_id="US1", name="US 1"))
    out = api.hat_as_representation_model(study, "r1", shelf=shelf, rm_id="lamp_model",
                                         attach_to="US1")
    assert out["attached"] is True
    # entity ─has_representation_model→ RM (P138i)
    assert any(e.edge_source == "US1" and e.edge_target == "lamp_model"
               and e.edge_type == "has_representation_model" for e in study.edges)


def test_hat_requires_resource_present_without_shelf():
    with pytest.raises(ValueError):
        api.hat_as_representation_model(Graph(graph_id="study"), "nope")


# ── remove cleanup ───────────────────────────────────────────────────────────
def test_remove_cleans_orphan_acquisition_event():
    # acquire (→ resource + acquisition event) on a shelf, then remove the resource
    desc = api.apply_acquisition_mapping("ercolano", {
        "url": "https://x/lamp.glb", "record_id": "E1", "title": "Lamp"})
    info, shelf = api.acquire_from_descriptor(desc)
    rid, acq = info["resource_id"], info["acquisition_id"]
    assert shelf.find_node_by_id(acq) is not None
    rep = api.remove_shelf_resource(shelf, rid)
    assert rep == {"removed": True, "referenced": False, "events_removed": 1}
    assert shelf.find_node_by_id(rid) is None
    assert shelf.find_node_by_id(acq) is None          # orphan event cleaned
    assert not any(n.node_type == "dtc_acquisition" for n in shelf.nodes)


def test_remove_keeps_event_when_resource_referenced():
    # if an RM references the resource (hatted into the SAME graph), keep everything
    desc = api.apply_acquisition_mapping("ercolano", {
        "url": "https://x/lamp.glb", "record_id": "E2", "title": "Lamp"})
    info, shelf = api.acquire_from_descriptor(desc)
    rid = info["resource_id"]
    api.hat_as_representation_model(shelf, rid, rm_id="lamp_model")  # RM in the shelf graph
    rep = api.remove_shelf_resource(shelf, rid)
    assert rep["removed"] is False and rep["referenced"] is True
    assert shelf.find_node_by_id(rid) is not None            # protected
    assert shelf.find_node_by_id(info["acquisition_id"]) is not None  # event kept


def test_remove_unknown_is_noop():
    shelf = api.new_shelf()
    assert api.remove_shelf_resource(shelf, "nope")["removed"] is False
