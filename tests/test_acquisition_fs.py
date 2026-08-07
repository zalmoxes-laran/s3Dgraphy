"""Shelf v2 (Session C1) — the file-system Tier-0 acquisition mapping.

Verifies the `fs` mapping + `fs_record` helper: a local file → record → descriptor
→ acquire onto a shelf, the same pipeline the EMTools 3D-first Shelf search drives
in-process.
"""

from s3dgraphy import api
from s3dgraphy.acquisition import AcquisitionDescriptor, available_mappings


def _mk(tmp_path, name="lamp.glb", content="x"):
    f = tmp_path / name
    f.write_text(content)
    return str(f)


def test_fs_mapping_is_available():
    assert "fs" in available_mappings()
    assert "ercolano" in available_mappings()  # B still there


def test_fs_record_fields(tmp_path):
    path = _mk(tmp_path, "site.gltf", "xyz")
    rec = api.fs_acquisition_record(path)
    assert rec["filename"] == "site.gltf" and rec["path"].endswith("site.gltf")
    assert rec["ext"] == "gltf" and rec["media_type"] == "model/gltf+json"
    assert rec["size"] == 3 and rec["record_id"] == rec["path"]
    assert rec["record_url"].startswith("file://")


def test_fs_record_to_descriptor(tmp_path):
    path = _mk(tmp_path, "mesh.obj")
    desc = api.apply_acquisition_mapping("fs", api.fs_acquisition_record(path))
    d = AcquisitionDescriptor.from_dict(desc)
    assert d.is_tier0()                                   # opaque local FS
    assert d.source["repo_id"] == "filesystem" and d.source["capabilities"] == []
    assert d.asset["ref"] == path and d.asset["name"] == "mesh.obj"
    assert d.asset["media_type"] == "model/obj"
    assert d.asset.get("size") == 1                       # peso in byte (mapping field)
    assert d.acquisition["method"] == "local_import"


def test_fs_acquire_onto_shelf(tmp_path):
    path = _mk(tmp_path, "lamp.glb")
    desc = api.apply_acquisition_mapping("fs", api.fs_acquisition_record(path))
    info, shelf = api.acquire_from_descriptor(desc)
    res = shelf.find_node_by_id(info["resource_id"])
    assert res.node_type == "resource" and res.data["url"] == path
    assert res.data["origin"] == {"repo": "filesystem", "capabilities": [], "scope": None}
    acq = shelf.find_node_by_id(info["acquisition_id"])
    assert acq.node_type == "dtc_acquisition" and acq.data.get("dtc_kind") == "local_import"


def test_fs_acquire_idempotent_by_path(tmp_path):
    path = _mk(tmp_path, "a.ply")
    desc = api.apply_acquisition_mapping("fs", api.fs_acquisition_record(path))
    i1, shelf = api.acquire_from_descriptor(desc)
    i2, shelf = api.acquire_from_descriptor(desc, shelf)   # re-scan same file
    assert i1["resource_id"] == i2["resource_id"]
    links = [n for n in shelf.nodes if n.node_type == "resource"]
    assert len(links) == 1
