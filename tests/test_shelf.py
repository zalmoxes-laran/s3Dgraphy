"""Shelf v2 core (Session A) — the shelf-graph substrate.

A shelf is a Graph of un-hatted ResourceNode resources, representable as a multigraph
member AND a standalone reusable em.json. Verifies: new/is_shelf; add (reuse-not-
duplicate); list (with capability/origin); remove; save/load standalone round-trip
(origin invariant preserved); instantiate-by-stable-ID into a study graph (reuse-
not-duplicate); a shelf loads as a plain em.json too.
"""

from s3dgraphy import api
from s3dgraphy.graph import Graph
from s3dgraphy.shelf import DEFAULT_SHELF_ID, SHELF_COLLECTION, is_shelf


_ORIGIN = {"repo": "sketchfab", "capabilities": ["genesis"], "scope": "genesis"}


# ── new / is_shelf ──────────────────────────────────────────────────────────────
def test_new_shelf_is_tagged():
    s = api.new_shelf()
    assert s.graph_id == DEFAULT_SHELF_ID
    assert is_shelf(s) and s.data.get("em_collection") == SHELF_COLLECTION
    # a plain graph is NOT a shelf
    assert not is_shelf(Graph(graph_id="study"))


# ── add / list (+ origin preserved) ─────────────────────────────────────────────
def test_add_and_list_with_origin():
    s = api.new_shelf()
    e = api.add_to_shelf(s, "/lib/photo.jpg", resource_id="r1", name="Photo",
                         resource_type="image", origin=_ORIGIN)
    assert e["id"] == "r1" and e["kind"] == "local_path"
    assert e["resource_type"] == "image" and e["origin"] == _ORIGIN
    rows = api.list_shelf(s)
    assert [r["id"] for r in rows] == ["r1"]
    assert rows[0]["origin"] == _ORIGIN  # capability/origin not stripped


def test_add_is_reuse_not_duplicate():
    s = api.new_shelf()
    api.add_to_shelf(s, "/lib/a.obj", resource_id="dup")
    api.add_to_shelf(s, "/lib/a-v2.obj", resource_id="dup", origin=_ORIGIN)  # same id
    rows = api.list_shelf(s)
    assert len(rows) == 1                       # not duplicated
    assert rows[0]["locator"] == "/lib/a-v2.obj"  # locator updated
    assert rows[0]["origin"] == _ORIGIN           # origin updated


def test_add_mints_id_when_absent():
    s = api.new_shelf()
    e = api.add_to_shelf(s, "https://zenodo.org/1")
    assert e["id"] and e["kind"] == "http_url"


# ── remove ────────────────────────────────────────────────────────────────────
def test_remove_from_shelf():
    s = api.new_shelf()
    api.add_to_shelf(s, "/lib/x.pdf", resource_id="rx")
    assert api.remove_from_shelf(s, "rx") is True
    assert api.list_shelf(s) == []
    assert api.remove_from_shelf(s, "rx") is False  # already gone


# ── save / load standalone (round-trip; origin invariant) ───────────────────────
def test_save_load_standalone_roundtrip(tmp_path):
    s = api.new_shelf(name="My Library")
    api.add_to_shelf(s, "/lib/photo.jpg", resource_id="r1", name="Photo",
                     resource_type="image", origin=_ORIGIN)
    api.add_to_shelf(s, "s3://bucket/mesh.obj", resource_id="r2",
                     resource_type="3d_model", origin={"repo": "stratigraph"})
    path = str(tmp_path / "shelf.em.json")
    api.save_shelf(s, path)

    back, warnings = api.load_shelf(path)
    assert is_shelf(back)                       # collection tag survives
    rows = {r["id"]: r for r in api.list_shelf(back)}
    assert set(rows) == {"r1", "r2"}
    assert rows["r1"]["origin"] == _ORIGIN       # capability/origin round-trips
    assert rows["r1"]["kind"] == "local_path" and rows["r2"]["kind"] == "s3_uri"
    assert rows["r2"]["origin"] == {"repo": "stratigraph"}


def test_shelf_file_is_plain_emjson(tmp_path):
    # a standalone shelf is ALSO a normal em.json (loadable by the generic loader)
    s = api.new_shelf()
    api.add_to_shelf(s, "/lib/a.jpg", resource_id="r1")
    path = str(tmp_path / "shelf.em.json")
    api.save_shelf(s, path)
    graph, _w = api.load_emjson_file(path)
    assert graph.find_node_by_id("r1") is not None


# ── instantiate (reuse-not-duplicate, by stable ID, origin preserved) ───────────
def test_instantiate_references_by_stable_id():
    s = api.new_shelf()
    api.add_to_shelf(s, "/lib/photo.jpg", resource_id="r1", name="Photo",
                     resource_type="image", origin=_ORIGIN)
    study = Graph(graph_id="study")
    node = api.instantiate_from_shelf(s, "r1", study)
    # same stable ID = the reference (not a clone under a new id)
    assert node.node_id == "r1" and node.node_type == "resource"
    assert study.find_node_by_id("r1") is not None
    # capability/origin carried into the study
    assert (node.data or {}).get("origin") == _ORIGIN
    # the resource STAYS on the shelf (library keeps it)
    assert [r["id"] for r in api.list_shelf(s)] == ["r1"]


def test_instantiate_is_idempotent():
    s = api.new_shelf()
    api.add_to_shelf(s, "/lib/a.obj", resource_id="r1")
    study = Graph(graph_id="study")
    n1 = api.instantiate_from_shelf(s, "r1", study)
    n2 = api.instantiate_from_shelf(s, "r1", study)  # already referenced
    assert n1 is n2
    links = [n for n in study.nodes if n.node_type == "resource"]
    assert len(links) == 1  # no duplicate


def test_instantiate_unknown_raises():
    import pytest
    s = api.new_shelf()
    with pytest.raises(ValueError):
        api.instantiate_from_shelf(s, "nope", Graph(graph_id="study"))


# ── shelf as a multigraph member (a plain Graph, any id) ────────────────────────
def test_shelf_can_use_any_graph_id():
    s = api.new_shelf(graph_id="templu_mare_shelf", name="Templu Mare shelf")
    assert s.graph_id == "templu_mare_shelf" and is_shelf(s)
