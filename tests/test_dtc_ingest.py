"""Ingestion in bulk: one event over N files, and a chain nobody guessed.

What is defended here, in the order the day happens:

* three files dragged in become **one** acquisition with three members — not
  three top-level nodes, and not three acquisitions;
* a derivation is **declared**: an output, its inputs (a whole acquisition
  counts as one), and a tool described by its name alone;
* the lot is attributed **once**, on the event, and the READER sees it on each
  member through the chain — inheritance, not four hundred copies;
* `resource_usages` answers "who uses this file", separating a citation from
  the file's own licence;
* everything is idempotent, and nothing reads or writes a tombstone.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from s3dgraphy import api as em                              # noqa: E402
from s3dgraphy.crdt import REMOVED_KEY                        # noqa: E402
from s3dgraphy.graph import Graph                            # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode       # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402

ME = "0000-0002-1825-0097"          # the cataloguer at the keyboard
BRUNO = "0000-0001-5109-3700"       # who took the photographs, in 1978


def digest(n: int) -> str:
    return "sha256:" + f"{n:02x}" * 32


def graph_with_files(count: int = 3) -> Graph:
    g = Graph(graph_id="g")
    for i in range(count):
        g.add_node(ResourceNode(f"img{i}", name=f"IMG_000{i}.jpg",
                                checksum=digest(i), residency="resident"))
    return g


def node_types(g: Graph, node_type: str):
    return [n for n in g.nodes if n.node_type == node_type]


# ── 1 · the bucket ───────────────────────────────────────────────────────────

def test_three_files_become_one_acquisition_with_three_members():
    g = graph_with_files(3)
    report = em.bucket_acquisition(g, ["img0", "img1", "img2"],
                                   name="Volo 2026-03",
                                   metadata={"camera": "DJI P4", "date": "2026-03-11"})

    assert report["count"] == 3
    assert len(node_types(g, "dtc_acquisition")) == 1, "one lot, one event"
    # the resources are still resources — the bucket groups them, it does not
    # absorb them
    assert len(node_types(g, "resource")) == 3
    acq = node_types(g, "dtc_acquisition")[0]
    assert acq.data["camera"] == "DJI P4"
    assert acq.data["member_count"] == 3
    assert em.acquisition_members(g, acq.node_id) == ["img0", "img1", "img2"]
    # the membership IS the edges (prov:generated), one per file
    assert sum(1 for e in g.edges if e.edge_type == "dtc_had_output") == 3


def test_the_bucket_takes_digests_too_because_an_uploader_has_no_ids():
    g = graph_with_files(2)
    report = em.bucket_acquisition(g, [digest(0), digest(1).split(":")[1]],
                                   name="lot")
    assert sorted(report["members"]) == ["img0", "img1"]


def test_a_named_lot_is_the_same_lot_the_second_time_and_grows():
    g = graph_with_files(3)
    first = em.bucket_acquisition(g, ["img0"], name="Volo 2026-03")
    second = em.bucket_acquisition(g, ["img1", "img2"], name="Volo 2026-03")
    assert second["acquisition_id"] == first["acquisition_id"]
    assert second["count"] == 3
    assert len(node_types(g, "dtc_acquisition")) == 1


def test_bucketing_the_same_batch_twice_adds_nothing():
    g = graph_with_files(3)
    em.bucket_acquisition(g, ["img0", "img1", "img2"], name="lot")
    edges = len(g.edges)
    again = em.bucket_acquisition(g, ["img0", "img1", "img2"], name="lot")
    assert again["added"] == []
    assert len(g.edges) == edges
    assert len(node_types(g, "dtc_acquisition")) == 1


def test_a_member_the_graph_does_not_have_is_reported_not_invented():
    g = graph_with_files(1)
    report = em.bucket_acquisition(g, ["img0", "img404"], name="lot")
    assert report["missing"] == ["img404"]
    assert report["count"] == 1
    assert any("img404" in w for w in report["warnings"])
    assert len(node_types(g, "resource")) == 1, "no node was conjured"


def test_a_tombstoned_member_is_not_a_member():
    g = graph_with_files(3)
    em.bucket_acquisition(g, ["img0", "img1", "img2"], name="lot")
    acq = node_types(g, "dtc_acquisition")[0]
    # img1 is deleted the way the synced document deletes: a tombstone
    g.find_node_by_id("img1").data[REMOVED_KEY] = {
        "ts": "2026-08-17T10:00:00Z", "by": ME}
    live = em.acquisition_members(g, acq.node_id)
    assert live == ["img0", "img2"]
    # …and the cached count catches up the next time somebody writes
    em.bucket_acquisition(g, [], acquisition_id=acq.node_id)
    assert acq.data["member_count"] == 2


def test_an_all_ghost_batch_creates_NO_acquisition():
    """The empty root. A lot whose every reference is a ghost used to be created
    anyway, and the corpus grew a root that grouped nothing — measured on a
    synthetic corpus, where it added a fourth root to a documentation that had
    three."""
    g = graph_with_files(1)
    before = len(node_types(g, "dtc_acquisition"))
    report = em.bucket_acquisition(g, ["ghost1", "ghost2"], name="Volo mai fatto")

    assert report["created"] is False
    assert report["acquisition_id"] is None, "no id, because there is no event"
    assert report["count"] == 0 and report["members"] == []
    assert report["missing"] == ["ghost1", "ghost2"], "the ghosts are reported"
    assert any("not created" in w for w in report["warnings"])
    assert len(node_types(g, "dtc_acquisition")) == before, "the corpus is untouched"


def test_a_partly_ghost_batch_still_makes_the_lot_of_what_is_there():
    """The guard is about NOTHING, not about something missing: one live file is
    a lot, and the ghost beside it is reported (unchanged behaviour)."""
    g = graph_with_files(2)
    report = em.bucket_acquisition(g, ["img0", "ghost", "img1"], name="Volo parziale")

    assert report["created"] is True
    assert report["acquisition_id"] is not None
    assert report["count"] == 2 and report["missing"] == ["ghost"]
    assert len(node_types(g, "dtc_acquisition")) == 1


def test_an_existing_lot_keeps_its_identity_when_a_later_batch_is_all_ghosts():
    """Refusing to CREATE is not refusing to answer: a second drop whose files
    are all ghosts added nothing to a REAL lot, and reporting `None` about a node
    the caller can see would be the same lie the other way round."""
    g = graph_with_files(1)
    first = em.bucket_acquisition(g, ["img0"], name="Volo marzo")
    again = em.bucket_acquisition(g, ["ghost"], name="Volo marzo")

    assert again["acquisition_id"] == first["acquisition_id"]
    assert again["created"] is False
    assert again["count"] == 1, "still the one live file"
    assert again["added"] == [] and again["missing"] == ["ghost"]
    assert len(node_types(g, "dtc_acquisition")) == 1


def test_a_batch_of_only_tombstones_creates_no_acquisition():
    """The same guard through the OTHER door: the files exist in the document but
    are deleted, so there is nothing alive to bucket."""
    g = graph_with_files(2)
    for nid in ("img0", "img1"):
        g.find_node_by_id(nid).data[REMOVED_KEY] = {
            "ts": "2026-08-17T10:00:00Z", "by": ME}
    report = em.bucket_acquisition(g, ["img0", "img1"], name="lot di fantasmi")

    assert report["acquisition_id"] is None and report["created"] is False
    assert node_types(g, "dtc_acquisition") == []


def test_a_bucket_groups_files_not_units():
    g = graph_with_files(1)
    g.add_node(StratigraphicUnit("US1", name="US1"))
    report = em.bucket_acquisition(g, ["img0", "US1"], name="lot")
    assert report["missing"] == ["US1"]
    assert any("resource" in w for w in report["warnings"])


# ── 2 · the declared chain ───────────────────────────────────────────────────

def test_an_output_is_declared_to_come_from_the_whole_acquisition():
    g = graph_with_files(3)
    lot = em.bucket_acquisition(g, ["img0", "img1", "img2"], name="Volo")
    g.add_node(ResourceNode("ortho", name="ortho.tif", checksum=digest(9),
                            residency="resident"))

    report = em.declare_derivation(g, "ortho", [lot["acquisition_id"]],
                                   tool="Metashape")

    assert report["inputs"] == [lot["acquisition_id"]]
    proc = g.find_node_by_id(report["process_id"])
    assert proc.node_type == "dtc_process"
    # the tool, at the minimum: its NAME, in a dict that can grow
    assert proc.data["tool"] == {"name": "Metashape"}
    kinds = {(e.edge_source, e.edge_type, e.edge_target) for e in g.edges}
    assert (proc.node_id, "dtc_had_output", "ortho") in kinds
    assert (proc.node_id, "dtc_had_input", lot["acquisition_id"]) in kinds
    # ONE input edge for the campaign, not one per photograph
    assert sum(1 for e in g.edges if e.edge_type == "dtc_had_input") == 1
    assert report["warnings"] == []


def test_a_resource_input_also_gets_the_derived_from_shortcut():
    g = graph_with_files(1)
    g.add_node(ResourceNode("mesh", name="mesh.glb", checksum=digest(9)))
    em.declare_derivation(g, "mesh", ["img0"], tool="Blender")
    kinds = {(e.edge_source, e.edge_type, e.edge_target) for e in g.edges}
    assert ("mesh", "dtc_derived_from", "img0") in kinds


def test_declaring_the_same_derivation_twice_converges():
    g = graph_with_files(1)
    g.add_node(ResourceNode("mesh", name="mesh.glb", checksum=digest(9)))
    a = em.declare_derivation(g, "mesh", ["img0"], tool="Blender")
    edges = len(g.edges)
    b = em.declare_derivation(g, "mesh", ["img0"], tool="Blender")
    assert a["process_id"] == b["process_id"]
    assert b["created"] is False
    assert len(g.edges) == edges
    assert len(node_types(g, "dtc_process")) == 1


def test_an_output_that_is_not_there_is_a_lookup_error_not_a_node():
    g = graph_with_files(1)
    with pytest.raises(LookupError):
        em.declare_derivation(g, "nowhere", ["img0"], tool="Blender")


def test_a_file_is_not_derived_from_itself():
    g = graph_with_files(1)
    report = em.declare_derivation(g, "img0", ["img0"], tool="cp")
    assert report["inputs"] == []
    assert any("itself" in w for w in report["warnings"])


def test_the_chain_reads_back_both_ways():
    g = graph_with_files(2)
    g.add_node(ResourceNode("mesh", name="mesh.glb", checksum=digest(9)))
    g.add_node(ResourceNode("proxy", name="proxy.glb", checksum=digest(8)))
    em.declare_derivation(g, "mesh", ["img0"], tool="Blender")
    em.declare_derivation(g, "proxy", ["mesh"], tool="gltfpack")
    chain = em.derivation_chain(g, "mesh")
    assert [c["tool"] for c in chain["made_by"]] == ["Blender"]
    assert [c["tool"] for c in chain["used_by"]] == ["gltfpack"]


def test_an_event_input_projects_as_was_informed_by_not_as_prov_used():
    """RDF: prov:used and L10_had_input range over digital OBJECTS.

    An acquisition is an event, so the edge that is legitimate in the property
    graph would be a false statement in the triples. It goes out as
    prov:wasInformedBy instead — checked, because a projection nobody looks at
    is where wrong classes live for years.
    """
    pytest.importorskip("rdflib")
    g = graph_with_files(2)
    lot = em.bucket_acquisition(g, ["img0", "img1"], name="Volo")
    g.add_node(ResourceNode("ortho", name="ortho.tif", checksum=digest(9)))
    em.declare_derivation(g, "ortho", [lot["acquisition_id"], "img0"],
                          tool="Metashape")
    ttl = em.project_ttl(g)
    assert "wasInformedBy" in ttl
    # the RESOURCE input is still the object-valued predicate
    assert "L10_had_input" in ttl or "prov:used" in ttl


# ── 3 · attribution, per lot ─────────────────────────────────────────────────

def test_the_lot_is_attributed_once_and_every_member_reads_it():
    g = graph_with_files(3)
    lot = em.bucket_acquisition(g, ["img0", "img1", "img2"], name="Volo")

    report = em.attribute_batch(g, lot["acquisition_id"], attributor=ME,
                                author=BRUNO, author_name="Bruno Rossi",
                                license="CC-BY-SA-4.0",
                                at="2026-08-17T09:00:00Z")

    assert report["changed"] == {"author": "declared", "license": "declared"}
    # ONE licence node for three files
    assert len(node_types(g, "license")) == 1
    for i in range(3):
        rights = em.asset_rights(g, digest(i))
        assert rights["license"] == "CC-BY-SA-4.0"
        assert rights["via"] == "dtc", "inherited from the event, not copied"
        assert rights["authors"] == [{"name": "Bruno Rossi", "orcid": BRUNO}]
    # the ACT is signed, and by the cataloguer — not by the author
    lic = node_types(g, "license")[0]
    assert lic.data["attributed_by"] == ME
    assert lic.data["attributed_at"] == "2026-08-17T09:00:00Z"


def test_propagation_is_a_copy_and_is_opt_in():
    g = graph_with_files(2)
    lot = em.bucket_acquisition(g, ["img0", "img1"], name="Volo")
    em.attribute_batch(g, lot["acquisition_id"], attributor=ME,
                       license="CC-BY-4.0", propagate=True)
    # one on the event + one per member
    assert len(node_types(g, "license")) == 3
    assert em.asset_rights(g, digest(0))["via"] == "resource"


def test_a_batch_attribution_is_signed_or_it_does_not_happen():
    g = graph_with_files(1)
    lot = em.bucket_acquisition(g, ["img0"], name="lot")
    with pytest.raises(ValueError):
        em.attribute_batch(g, lot["acquisition_id"], attributor=None,
                           license="CC-BY-4.0")


def test_the_lot_licence_can_be_retracted_and_the_members_stop_reading_it():
    g = graph_with_files(2)
    lot = em.bucket_acquisition(g, ["img0", "img1"], name="Volo")
    em.attribute_batch(g, lot["acquisition_id"], attributor=ME,
                       license="CC-BY-4.0")
    em.attribute_batch(g, lot["acquisition_id"], attributor=ME, license="")
    rights = em.asset_rights(g, digest(0))
    assert rights["license"] is None
    assert rights["license_is_default"] is True


def test_attributing_a_lot_that_is_not_an_acquisition_is_a_lookup_error():
    g = graph_with_files(1)
    with pytest.raises(LookupError):
        em.attribute_batch(g, "img0", attributor=ME, license="CC-BY-4.0")


# ── 4 · who uses this asset ──────────────────────────────────────────────────

def test_usages_separate_a_citation_from_the_files_own_licence():
    g = graph_with_files(1)
    g.add_node(StratigraphicUnit("US1", name="US1"))
    g.add_edge("e1", "US1", "img0", "has_linked_resource")
    em.enrich_asset_dtc(g, digest(0), attributor=ME, license="CC-BY-4.0")

    usages = em.resource_usages(g, digest(0))
    roles = {u["id"]: u["role"] for u in usages}
    assert roles["US1"] == "reference"
    assert set(roles.values()) == {"reference", "rights"}
    ref = next(u for u in usages if u["role"] == "reference")
    assert ref["edge_type"] == "has_linked_resource"
    assert ref["direction"] == "incoming"


def test_usages_see_the_chain_and_the_bucket():
    g = graph_with_files(1)
    lot = em.bucket_acquisition(g, ["img0"], name="Volo")
    usages = em.resource_usages(g, "img0")
    assert [(u["id"], u["role"]) for u in usages] == [
        (lot["acquisition_id"], "chain")]


def test_a_deleted_user_is_not_a_user():
    g = graph_with_files(1)
    g.add_node(StratigraphicUnit("US1", name="US1"))
    g.add_edge("e1", "US1", "img0", "has_linked_resource")
    unit = g.find_node_by_id("US1")
    unit.data = {REMOVED_KEY: {"ts": "2026-08-17T10:00:00Z", "by": ME}}
    assert em.resource_usages(g, "img0") == []


def test_unused_resources_lists_what_nothing_points_at():
    g = graph_with_files(2)
    g.add_node(StratigraphicUnit("US1", name="US1"))
    g.add_edge("e1", "US1", "img0", "has_linked_resource")
    em.bucket_acquisition(g, ["img0", "img1"], name="Volo")
    unused = [r["id"] for r in em.unused_resources(g)]
    assert unused == ["img1"], "being in a lot is not being used"


def test_the_batch_summary_is_what_a_panel_shows():
    g = graph_with_files(2)
    lot = em.bucket_acquisition(g, ["img0", "img1"], name="Volo 2026-03",
                                metadata={"camera": "DJI P4"})
    em.attribute_batch(g, lot["acquisition_id"], attributor=ME,
                       license="CC-BY-SA-4.0")
    card = em.batch_summary(g, lot["acquisition_id"])
    assert card["found"] and card["count"] == 2
    assert card["name"] == "Volo 2026-03"
    assert card["metadata"]["camera"] == "DJI P4"
    assert {m["license_effective"] for m in card["members"]} == {"CC-BY-SA-4.0"}
    assert {m["residency"] for m in card["members"]} == {"resident"}
