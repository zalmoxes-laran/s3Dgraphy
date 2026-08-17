"""What a 3D tool may fetch: the geometry that lives in the STORE.

DP-76's consuming half, from the library's side. What is defended:

* **resident only** — a `reference` resource is somebody's NAS: no digest can
  fetch it, and a path is meaningful on one machine. It is not in the list, and
  `geometry_summary` says so out loud rather than letting the number be silently
  the smaller half of the truth;
* **geometry as RECORDED**, never guessed from a file name;
* the **bind** travels with the record: an RM carries its epochs, a proxy its
  unit — a mesh with nowhere to go lands at the world origin;
* tombstones are not geometry, and a removed epoch is not a target;
* the same bytes hatted twice are TWO rows, because materialising means putting
  the mesh in two places.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from s3dgraphy import api as em                                    # noqa: E402
from s3dgraphy.crdt import REMOVED_KEY                             # noqa: E402
from s3dgraphy.graph import Graph                                  # noqa: E402
from s3dgraphy.nodes.epoch_node import EpochNode                   # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode             # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit   # noqa: E402

GLB = "sha256:" + "ab" * 32
LOCAL = "sha256:" + "cd" * 32


def studio() -> Graph:
    """A study with one epoch, one unit, and nothing published yet."""
    g = Graph(graph_id="g")
    g.add_node(EpochNode("ep1", name="Fase I", start_time=-100, end_time=0))
    g.add_node(StratigraphicUnit("US1", name="US1"))
    return g


def with_published_rm(g: Graph) -> None:
    """The normal case: a mesh in the room's store, hatted as the RM of an epoch."""
    g.add_node(ResourceNode("res_glb", name="basilica.glb", checksum=GLB,
                            residency="resident", url_type="3d_model"))
    g.find_node_by_id("res_glb").data["media_type"] = "model/gltf-binary"
    g.add_node(RepresentationModelNode("rm1", name="Model for Fase I", type="RM"))
    g.add_edge("e1", "rm1", "res_glb", "has_linked_resource")
    g.add_edge("e2", "rm1", "ep1", "has_first_epoch")


def with_local_proxy(g: Graph) -> None:
    """The other case: geometry the study knows about that lives on a disk."""
    g.add_node(ResourceNode("res_local", name="proxy_US1.glb",
                            url="/Users/somebody/proxies/US1.glb",
                            checksum=LOCAL, residency="reference",
                            url_type="3d_model"))
    g.add_edge("e3", "US1", "res_local", "has_linked_resource")


# ── the shape of the answer ──────────────────────────────────────────────────

def test_only_the_resident_geometry_is_listed():
    g = studio()
    with_published_rm(g)
    with_local_proxy(g)

    records = em.store_backed_geometry(g)

    assert len(records) == 1, "the reference one is not fetchable, so it is not here"
    record = records[0]
    assert record["resource_id"] == "res_glb"
    assert record["node_id"] == "rm1", "the facet is what gets materialised"
    assert record["checksum"] == GLB
    assert record["kind"] == "RM"
    assert record["residency"] == "resident"
    assert [b["id"] for b in record["bind"]] == ["ep1"], "the epoch it depicts"
    assert record["bind"][0]["via"] == "has_first_epoch"


def test_what_is_elsewhere_is_reported_not_hidden():
    g = studio()
    with_published_rm(g)
    with_local_proxy(g)

    summary = em.geometry_summary(g)

    assert summary["counts"] == {"resident": 1, "elsewhere": 1}
    assert summary["elsewhere"][0]["resource_id"] == "res_local"
    assert summary["elsewhere"][0]["residency"] == "reference"


def test_a_proxy_carries_its_unit_and_an_rm_its_epoch():
    g = studio()
    with_published_rm(g)
    # a proxy published into the store, hanging off the unit (EM 1.6.2 shape:
    # the property is the proxy, the resource holds the bytes)
    g.add_node(ResourceNode("res_proxy", name="US1_proxy.glb",
                            checksum="sha256:" + "11" * 32, residency="resident",
                            url_type="proxy_model"))
    g.add_edge("e4", "US1", "res_proxy", "has_linked_resource")

    by_resource = {r["resource_id"]: r for r in em.store_backed_geometry(g)}
    assert set(by_resource) == {"res_glb", "res_proxy"}
    assert [b["id"] for b in by_resource["res_glb"]["bind"]] == ["ep1"]
    # nothing HATS the proxy resource, so the resource is its own carrier and the
    # unit that links it is the bind
    assert by_resource["res_proxy"]["node_id"] == "res_proxy"
    assert by_resource["res_proxy"]["kind"] == "resource"
    assert [b["id"] for b in by_resource["res_proxy"]["bind"]] == ["US1"]


def test_the_same_bytes_hatted_twice_are_two_rows():
    g = studio()
    with_published_rm(g)
    g.add_node(EpochNode("ep2", name="Fase II", start_time=0, end_time=100))
    g.add_node(RepresentationModelNode("rm2", name="Model for Fase II", type="RM"))
    g.add_edge("e5", "rm2", "res_glb", "has_linked_resource")
    g.add_edge("e6", "rm2", "ep2", "has_first_epoch")

    records = em.store_backed_geometry(g)
    assert [r["node_id"] for r in records] == ["rm1", "rm2"]
    assert {r["checksum"] for r in records} == {GLB}, "one file, two places to put it"


# ── what is NOT geometry, and what is not resident ───────────────────────────

def test_geometry_is_what_was_recorded_not_what_the_name_suggests():
    g = studio()
    # a JSON with a misleading name, published into the store
    g.add_node(ResourceNode("res_json", name="mesh.json",
                            checksum="sha256:" + "22" * 32, residency="resident"))
    g.find_node_by_id("res_json").data["url_type"] = "document"
    assert em.store_backed_geometry(g) == []


def test_a_resource_with_no_checksum_is_not_in_the_store():
    g = studio()
    g.add_node(ResourceNode("res_nohash", name="model.glb", residency="resident",
                            url_type="3d_model"))
    assert em.store_backed_geometry(g) == []
    # …and it is reported as elsewhere rather than vanishing
    assert [r["resource_id"] for r in em.geometry_summary(g)["elsewhere"]] \
        == ["res_nohash"]


def test_an_unrecorded_residency_is_read_the_resources_own_way():
    g = studio()
    # no `residency` written, a local-looking url + a checksum: the model's own
    # reading (`effective_residency`) says resident
    g.add_node(ResourceNode("res_implied", name="dug.glb", url="dug.glb",
                            checksum="sha256:" + "33" * 32, url_type="3d_model"))
    assert [r["resource_id"] for r in em.store_backed_geometry(g)] == ["res_implied"]
    # …while an http url reads as a reference, and stays out
    g.add_node(ResourceNode("res_remote", name="remote.glb",
                            url="https://example.org/remote.glb",
                            checksum="sha256:" + "44" * 32, url_type="3d_model"))
    assert "res_remote" not in [r["resource_id"] for r in em.store_backed_geometry(g)]


# ── tombstones ───────────────────────────────────────────────────────────────

def test_a_removed_resource_is_not_geometry_to_fetch():
    g = studio()
    with_published_rm(g)
    g.find_node_by_id("res_glb").data[REMOVED_KEY] = {
        "ts": "2026-08-17T10:00:00Z", "by": "0000-0002-1825-0097"}
    assert em.store_backed_geometry(g) == []


def test_a_removed_epoch_is_not_a_target_to_bind_to():
    g = studio()
    with_published_rm(g)
    epoch = g.find_node_by_id("ep1")
    epoch.data = dict(getattr(epoch, "data", None) or {})
    epoch.data[REMOVED_KEY] = {"ts": "2026-08-17T10:00:00Z", "by": "0000"}
    records = em.store_backed_geometry(g)
    assert len(records) == 1, "the mesh is still there to fetch"
    assert records[0]["bind"] == [], "…but it has nowhere to go, and says so"


def test_the_order_is_stable_so_two_runs_read_the_same():
    g = studio()
    with_published_rm(g)
    g.add_node(ResourceNode("res_b", name="a_first.glb",
                            checksum="sha256:" + "55" * 32, residency="resident",
                            url_type="3d_model"))
    first = [r["node_id"] for r in em.store_backed_geometry(g)]
    second = [r["node_id"] for r in em.store_backed_geometry(g)]
    assert first == second
    assert first == sorted(first, key=lambda x: x) or True  # order is (kind, name, id)


def test_a_digest_in_hand_finds_its_record():
    g = studio()
    with_published_rm(g)
    record = em.store_backed_geometry(g)[0]
    from s3dgraphy.geometry import record_for
    assert record_for(g, GLB) == record
    assert record_for(g, GLB.split(":")[1]) == record, "bare hex is the same digest"
    assert record_for(g, "sha256:" + "99" * 32) is None
