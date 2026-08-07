"""R3 — DTC resident-with-data: detach ↔ inject ↔ bake.

A DTC can live outside em.json (a standalone record referencing resources by
stable ID) and be re-injected (temporary, ``injected_by``) then baked to
persistent on demand — reusing the aux-lifecycle convention. Verifies the
round-trip, the tagging, the bake, stable-ID reference, non-interference with a
DTC already in em.json, and that TTL (CRMdig/PROV) projection holds after inject
and after bake.
"""

import pytest

from s3dgraphy import api
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import DTCProcessNode, ResourceNode
from s3dgraphy.dtc import (
    EDGE_DERIVED_FROM, EDGE_HAD_INPUT, EDGE_HAD_OUTPUT, dtc_injector_id,
)
from s3dgraphy.resources import stable_resource_id
from s3dgraphy.transforms import is_injected


def _resource(node_id, name, kind, url):
    lk = ResourceNode(node_id, name=name, url=url)
    lk.data["dtc_kind"] = kind
    lk.data["resource_type"] = kind
    return lk


def _chain(graph_id="dtc_demo") -> Graph:
    g = Graph(graph_id=graph_id)
    g.add_node(_resource("in1", "Photo set", "photo", "https://assets.example/photos.zip"))
    g.add_node(DTCProcessNode("proc1", name="Photogrammetry", dtc_kind="transformation"))
    g.add_node(_resource("out1", "Site mesh", "mesh", "https://assets.example/mesh.obj"))
    g.add_edge("e1", "proc1", "in1", EDGE_HAD_INPUT)
    g.add_edge("e2", "proc1", "out1", EDGE_HAD_OUTPUT)
    g.add_edge("e3", "out1", "in1", EDGE_DERIVED_FROM)
    return g


# ── detach ───────────────────────────────────────────────────────────────────
def test_detach_record_shape_and_stable_ids():
    g = _chain()
    rec = api.detach_dtc(g, "proc1")
    assert rec["dtc_record_version"] == 1
    assert rec["process"]["id"] == "proc1" and rec["process"]["dtc_kind"] == "transformation"
    # resources referenced by STABLE ID (= the ResourceNode UUID) + kind
    res = {r["id"]: r for r in rec["resources"]}
    assert set(res) == {"in1", "out1"}
    assert res["in1"]["role"] == "input" and res["in1"]["dtc_kind"] == "photo"
    assert res["out1"]["role"] == "output" and res["out1"]["dtc_kind"] == "mesh"
    for rid in ("in1", "out1"):
        assert res[rid]["id"] == stable_resource_id(g.find_node_by_id(rid))
    ets = {(e["source"], e["target"], e["type"]) for e in rec["edges"]}
    assert ("proc1", "in1", EDGE_HAD_INPUT) in ets
    assert ("proc1", "out1", EDGE_HAD_OUTPUT) in ets
    assert ("out1", "in1", EDGE_DERIVED_FROM) in ets


def test_detach_is_read_only():
    g = _chain()
    before = (len(g.nodes), len(g.edges))
    api.detach_dtc(g, "proc1")
    assert (len(g.nodes), len(g.edges)) == before  # a DTC in em.json is untouched


def test_detach_rejects_non_process():
    g = _chain()
    with pytest.raises(ValueError):
        api.detach_dtc(g, "in1")


# ── inject (round-trip) ─────────────────────────────────────────────────────────
def test_detach_inject_roundtrip_same_ids_and_kinds():
    src = _chain()
    rec = api.detach_dtc(src, "proc1")

    dst = Graph(graph_id="target")
    out = api.inject_dtc(dst, rec)
    assert out["process_id"] == "proc1"
    assert set(out["resource_ids"]) == {"in1", "out1"}
    by = {n.node_id: n for n in dst.nodes}
    assert by["proc1"].node_type == "dtc_process"
    assert (by["proc1"].data or {}).get("dtc_kind") == "transformation"
    for rid, kind in (("in1", "photo"), ("out1", "mesh")):
        assert by[rid].node_type == "resource"
        assert (by[rid].data or {}).get("dtc_kind") == kind
        assert (by[rid].data or {}).get("resource_type") == kind
    ets = {e.edge_type for e in dst.edges}
    assert {EDGE_HAD_INPUT, EDGE_HAD_OUTPUT, EDGE_DERIVED_FROM} <= ets


def test_injected_dtc_is_tagged_temporary():
    rec = api.detach_dtc(_chain(), "proc1")
    dst = Graph(graph_id="target")
    out = api.inject_dtc(dst, rec)
    inj = out["injector_id"]
    assert inj == dtc_injector_id("proc1")
    # every created node + every chain edge carries the injected_by tag
    for nid in ("proc1", "in1", "out1"):
        assert is_injected(dst.find_node_by_id(nid)) == inj
    chain_edges = [e for e in dst.edges
                   if e.edge_type in (EDGE_HAD_INPUT, EDGE_HAD_OUTPUT, EDGE_DERIVED_FROM)]
    assert chain_edges and all(is_injected(e) == inj for e in chain_edges)


def test_inject_reuses_existing_resources_by_stable_id():
    rec = api.detach_dtc(_chain(), "proc1")
    # a target graph that ALREADY owns the resources (asset store) — inject must
    # reference them by stable ID, not duplicate them.
    dst = Graph(graph_id="target")
    dst.add_node(_resource("in1", "Photo set", "photo", "https://assets.example/photos.zip"))
    dst.add_node(_resource("out1", "Site mesh", "mesh", "https://assets.example/mesh.obj"))
    n_before = len(dst.nodes)
    out = api.inject_dtc(dst, rec)
    assert out["created"] == ["proc1"]            # only the process was created
    assert len(dst.nodes) == n_before + 1
    # pre-existing resources stay graph-native (not tagged as injected)
    assert is_injected(dst.find_node_by_id("in1")) is None
    assert is_injected(dst.find_node_by_id("out1")) is None


# ── bake ─────────────────────────────────────────────────────────────────────
def test_bake_promotes_injected_to_persistent():
    rec = api.detach_dtc(_chain(), "proc1")
    dst = Graph(graph_id="target")
    inj = api.inject_dtc(dst, rec)["injector_id"]
    report = api.bake_dtc(dst, inj)
    assert report["nodes"] == 3 and report["edges"] == 3
    # after bake nothing is tagged temporary — it is graph-native
    for nid in ("proc1", "in1", "out1"):
        assert is_injected(dst.find_node_by_id(nid)) is None
    assert all(is_injected(e) is None for e in dst.edges)


def test_bake_is_scoped_to_the_injector():
    # two independent DTCs injected; baking one leaves the other temporary.
    dst = Graph(graph_id="target")
    inj_a = api.inject_dtc(dst, api.detach_dtc(_chain("a"), "proc1"),
                           injector_id="DTC:A")["injector_id"]
    # a second DTC with distinct ids
    src_b = Graph(graph_id="b")
    src_b.add_node(_resource("in2", "Scan", "point_cloud", "s3://b/scan.e57"))
    src_b.add_node(DTCProcessNode("proc2", name="Meshing", dtc_kind="transformation"))
    src_b.add_node(_resource("out2", "Mesh2", "mesh", "s3://b/mesh2.obj"))
    src_b.add_edge("b1", "proc2", "in2", EDGE_HAD_INPUT)
    src_b.add_edge("b2", "proc2", "out2", EDGE_HAD_OUTPUT)
    inj_b = api.inject_dtc(dst, api.detach_dtc(src_b, "proc2"),
                           injector_id="DTC:B")["injector_id"]

    api.bake_dtc(dst, inj_a)
    assert is_injected(dst.find_node_by_id("proc1")) is None       # A baked
    assert is_injected(dst.find_node_by_id("proc2")) == inj_b       # B still temporary


# ── TTL projection holds after inject and after bake ────────────────────────────
def _project_ok(graph) -> bool:
    ttl = api.project_ttl(graph)
    return ("crmdig" in ttl or "D7_Digital_Machine_Event" in ttl) and "prov" in ttl


def test_ttl_projection_after_inject_and_bake():
    pytest.importorskip("rdflib")
    rec = api.detach_dtc(_chain(), "proc1")
    dst = Graph(graph_id="target")
    inj = api.inject_dtc(dst, rec)["injector_id"]

    # the DTC predicates project (CRMdig L10/L11/L21 + PROV used/generated/derived)
    ttl_injected = api.project_ttl(dst)
    for tok in ("L10_had_input", "L11_had_output", "used", "generated"):
        assert tok in ttl_injected
    assert _project_ok(dst)

    api.bake_dtc(dst, inj)
    ttl_baked = api.project_ttl(dst)
    for tok in ("L10_had_input", "L11_had_output", "used", "generated"):
        assert tok in ttl_baked  # projection unchanged by baking
    assert _project_ok(dst)
