"""The DOCUMENTATION member: a corpus is not a matrix.

What is defended:

* a corpus is a container member of its **own kind** (`em_collection:
  "DTCCorpus"`), recognised by its MARKER and kept out of `container.graphs` —
  the bug that would cause is a provenance forest rendered as a stratigraphic
  matrix, which is the whole reason this exists;
* it round-trips: written into `graphs` under its id, read back into
  `container.corpus`, and the study's graphs are untouched either way;
* the DTC ops write into it, and the forest **shares its leaves**: two
  acquisitions feeding one derived output is one output with two inputs, which is
  native here;
* **promotion carries the DTC**: a file that becomes an asset in the room's store
  gets its D7 event in the corpus and the asset mirrored there under its own id
  (the shared leaf) — the study graph keeps the resource, not the plumbing;
* the summary counts what a corpus is about, and says what is FOREIGN rather
  than pretending a unit in a corpus is normal;
* idempotence, and no tombstone speaking.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from s3dgraphy import api as em                                    # noqa: E402
from s3dgraphy.container import (Container, build_container,        # noqa: E402
                                 is_dtc_corpus_member, parse_container)
from s3dgraphy.crdt import REMOVED_KEY                             # noqa: E402
from s3dgraphy.dtc.corpus import (DTC_CORPUS_COLLECTION,           # noqa: E402
                                  corpus_of, mirror_resource, new_corpus)
from s3dgraphy.graph import Graph                                  # noqa: E402
from s3dgraphy.nodes.epoch_node import EpochNode                   # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode             # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit   # noqa: E402

ME = "0000-0002-1825-0097"


def study() -> Container:
    """A study with one graph, the way a project starts."""
    graph = Graph(graph_id="basilica")
    graph.add_node(EpochNode("ep1", name="Fase I", start_time=-100, end_time=0))
    graph.add_node(StratigraphicUnit("US1", name="US1"))
    return Container(graphs={"basilica": graph}, active_graph_id="basilica")


def digest(n: int) -> str:
    return "sha256:" + f"{n:02x}" * 32


# ── the member ───────────────────────────────────────────────────────────────

def test_a_corpus_is_a_member_of_its_own_kind():
    corpus = new_corpus()
    assert corpus.data["em_collection"] == DTC_CORPUS_COLLECTION
    assert em.is_dtc_corpus(corpus)
    assert not em.is_dtc_corpus(Graph(graph_id="plain"))


def test_it_is_found_by_its_marker_not_by_its_id():
    odd = new_corpus(graph_id="whatever-somebody-called-it")
    assert em.is_dtc_corpus(odd)
    # …and a member id that LOOKS like one, without the marker, is not one
    decoy = Graph(graph_id="dtc")
    assert not em.is_dtc_corpus(decoy)
    assert not is_dtc_corpus_member({"data": {"em_collection": "ShelfGraph"}})
    assert is_dtc_corpus_member({"data": {"em_collection": "DTCCorpus"}})


def test_the_corpus_stays_out_of_the_studys_graphs():
    container = study()
    corpus = em.dtc_corpus(container)
    assert container.corpus is corpus
    assert list(container.graphs) == ["basilica"], \
        "a caller iterating the study's graphs must not meet the corpus"
    assert container.active().graph_id == "basilica"


def test_it_round_trips_through_the_file():
    container = study()
    corpus = em.dtc_corpus(container)
    # a lot needs a FILE: an acquisition that groups nothing is not created
    # (dtc.ingest guards it), so the round trip is tested with a real member
    corpus.add_node(ResourceNode("img0", name="IMG_0000.jpg",
                                 checksum=digest(0), residency="resident"))
    em.bucket_acquisition(corpus, ["img0"], name="Volo 2026-03")

    doc = build_container(container)
    assert "dtc" in doc["graphs"], "written back into `graphs`, where a reader looks"
    assert doc["graphs"]["dtc"]["data"]["em_collection"] == DTC_CORPUS_COLLECTION

    back, warnings = parse_container(doc)
    assert back.corpus is not None
    assert list(back.graphs) == ["basilica"]
    # …and the acquisition is in it. (A member parse also materialises the
    # graph-scope node — the same thing happens to a shelf member; declared, not
    # asserted away.)
    assert "Volo 2026-03" in [n.name for n in back.corpus.nodes]
    assert [n.node_type for n in back.corpus.nodes].count("dtc_acquisition") == 1
    assert warnings == []


def test_asking_without_creating_does_not_invent_one():
    container = study()
    assert em.dtc_corpus(container, create=False) is None
    assert container.corpus is None
    em.dtc_corpus(container)                       # now there is one
    assert em.dtc_corpus(container, create=False) is not None


def test_a_container_of_corpus_only_is_readable_and_says_so():
    container = Container(graphs={})
    em.dtc_corpus(container)
    doc = build_container(container)
    back, warnings = parse_container(doc)
    assert back.corpus is not None
    assert any("no study graph" in w for w in warnings), \
        "readable, and the absence of a matrix is stated rather than crashed on"


# ── the forest, and its shared leaves ────────────────────────────────────────

def test_two_acquisitions_and_one_derived_output_share_a_leaf():
    container = study()
    corpus = em.dtc_corpus(container)
    for i in range(4):
        corpus.add_node(ResourceNode(f"img{i}", name=f"IMG_{i}.jpg",
                                     checksum=digest(i), residency="resident",
                                     url_type="image"))
    corpus.add_node(ResourceNode("ortho", name="ortho.tif", checksum=digest(9),
                                 residency="resident", url_type="image"))
    march = em.bucket_acquisition(corpus, ["img0", "img1"], name="Volo marzo")
    june = em.bucket_acquisition(corpus, ["img2", "img3"], name="Volo giugno")
    em.declare_derivation(corpus, "ortho",
                          [march["acquisition_id"], june["acquisition_id"]],
                          tool="Metashape")

    summary = em.dtc_corpus_summary(corpus)
    assert summary["counts"]["roots"] == 2, "two flights, two roots"
    assert summary["counts"]["transformations"] == 1
    # the members of a flight are outputs of an ACQUISITION; the orthophoto is
    # the output of a TRANSFORMATION — and the summary keeps them apart
    assert summary["derived"] == ["ortho"]
    assert summary["acquired"] == ["img0", "img1", "img2", "img3"]
    # the two acquisitions are the inputs of the ONE process
    assert sorted(summary["inputs"]) == sorted(
        [march["acquisition_id"], june["acquisition_id"]])
    assert summary["counts"]["foreign"] == 0


def test_a_leaf_two_events_consume_is_reported_as_shared():
    container = study()
    corpus = em.dtc_corpus(container)
    corpus.add_node(ResourceNode("photo", name="prospetto.jpg", checksum=digest(1),
                                 residency="resident", url_type="image"))
    for name in ("ortho", "mesh"):
        corpus.add_node(ResourceNode(name, name=f"{name}.tif",
                                     checksum=digest(hash(name) % 200),
                                     residency="resident", url_type="image"))
    em.declare_derivation(corpus, "ortho", ["photo"], tool="Metashape")
    em.declare_derivation(corpus, "mesh", ["photo"], tool="Blender")

    summary = em.dtc_corpus_summary(corpus)
    assert summary["shared"] == ["photo"], \
        "one photograph feeding two chains — the forest sharing a leaf"
    assert summary["counts"]["transformations"] == 2


def test_a_unit_in_a_corpus_is_reported_as_foreign():
    corpus = new_corpus()
    corpus.add_node(StratigraphicUnit("US1", name="US1"))
    corpus.add_node(EpochNode("ep1", name="Fase I", start_time=-1, end_time=0))
    summary = em.dtc_corpus_summary(corpus)
    assert set(summary["foreign"]) == {"US1", "ep1"}, \
        "a matrix written into the documentation is a mistake worth SEEING"
    assert summary["counts"]["roots"] == 0


def test_an_orphan_resource_is_listed_without_being_a_fault():
    corpus = new_corpus()
    corpus.add_node(ResourceNode("loose", name="loose.jpg", checksum=digest(3),
                                 residency="resident", url_type="image"))
    summary = em.dtc_corpus_summary(corpus)
    assert summary["orphans"] == ["loose"]
    assert summary["counts"]["transformations"] == 0


def test_a_tombstoned_event_is_not_in_the_summary():
    corpus = new_corpus()
    corpus.add_node(ResourceNode("img", name="a.jpg", checksum=digest(1),
                                 residency="resident", url_type="image"))
    lot = em.bucket_acquisition(corpus, ["img"], name="lot")
    # the mark must be LATER than the node's own editorial stamp, or the CRDT
    # reads it as resurrected — an edit after a deletion wins, by design
    corpus.find_node_by_id(lot["acquisition_id"]).data[REMOVED_KEY] = {
        "ts": "2099-01-01T00:00:00Z", "by": ME}
    assert em.dtc_corpus_summary(corpus)["counts"]["roots"] == 0


# ── promotion carries the DTC into the corpus ────────────────────────────────

def test_promoting_a_filesystem_resource_puts_its_dtc_in_the_corpus():
    container = study()
    graph = container.graphs["basilica"]
    corpus = em.dtc_corpus(container)
    # a file on somebody's disk, known to the study by its digest
    graph.add_node(ResourceNode("mesh", name="US1.glb",
                                url="/Users/somebody/US1.glb",
                                checksum=digest(7), residency="reference",
                                url_type="3d_model"))

    result = em.promote_resource(
        graph, "mesh",
        url="http://localhost:8000/v1/rooms/r/asset/" + digest(7),
        sha256=digest(7), media_type="model/gltf-binary",
        residency="resident", corpus=corpus, author=ME)

    # the study keeps the asset, and it is RESIDENT now
    resource = graph.find_node_by_id("mesh")
    assert resource.data["residency"] == "resident"
    assert resource.data["checksum"] == digest(7)
    # …and the plumbing is in the corpus, not in the matrix
    assert result["corpus_node_ids"], result
    assert result["process_id"] in result["corpus_node_ids"]
    assert graph.find_node_by_id(result["process_id"]) is None, \
        "the D7 event does not belong in the middle of a stratigraphic graph"
    process = corpus.find_node_by_id(result["process_id"])
    assert process is not None and process.node_type == "dtc_process"
    # the asset is mirrored under ITS OWN ID — the shared leaf
    mirrored = corpus.find_node_by_id("mesh")
    assert mirrored is not None and mirrored.node_type == "resource"
    assert mirrored.data["checksum"] == digest(7)
    summary = em.dtc_corpus_summary(corpus)
    assert summary["derived"] == ["mesh"]
    assert summary["counts"]["transformations"] == 1


def test_promoting_twice_does_not_duplicate_the_corpus_event():
    container = study()
    graph = container.graphs["basilica"]
    corpus = em.dtc_corpus(container)
    graph.add_node(ResourceNode("mesh", name="US1.glb", checksum=digest(7),
                                residency="reference", url_type="3d_model"))
    args = dict(url="http://localhost:8000/asset/" + digest(7), sha256=digest(7),
                residency="resident", corpus=corpus, author=ME)
    first = em.promote_resource(graph, "mesh", **args)
    nodes, edges = len(corpus.nodes), len(corpus.edges)
    second = em.promote_resource(graph, "mesh", **args)
    assert second["process_id"] == first["process_id"]
    assert (len(corpus.nodes), len(corpus.edges)) == (nodes, edges)


def test_without_a_corpus_promotion_behaves_exactly_as_before():
    graph = Graph(graph_id="basilica")
    graph.add_node(ResourceNode("mesh", name="US1.glb", checksum=digest(7)))
    result = em.promote_resource(graph, "mesh", url="http://x/asset", sha256=digest(7))
    assert graph.find_node_by_id(result["process_id"]) is not None, \
        "the old sentence still holds: no corpus, the event stays in the graph"
    assert result["corpus_node_ids"] == []
    assert graph.find_node_by_id("mesh").data["residency"] == "reference", \
        "…and the default residency is unchanged"


def test_mirroring_never_overwrites_a_richer_corpus_node():
    corpus = new_corpus()
    corpus.add_node(ResourceNode("mesh", name="already here",
                                 checksum=digest(7), residency="resident",
                                 url_type="3d_model"))
    corpus.find_node_by_id("mesh").data["media_type"] = "model/gltf-binary"
    thin = ResourceNode("mesh", name="thin", url="/tmp/x.glb")
    mirror_resource(corpus, thin)
    data = corpus.find_node_by_id("mesh").data
    assert data["media_type"] == "model/gltf-binary", "not clobbered by a thinner copy"
    assert data["url"] == "/tmp/x.glb", "…and an empty field IS filled in"


def test_corpus_of_adopts_a_corpus_that_was_filed_among_the_graphs():
    """A container written before the field existed keeps its corpus in `graphs`.
    Reading it must ADOPT it, not make a second one — otherwise the day the field
    arrived every project quietly grew an empty second corpus."""
    container = study()
    stray = new_corpus(graph_id="dtc")
    container.graphs["dtc"] = stray
    found = corpus_of(container)
    assert found is stray
    assert "dtc" not in container.graphs
    assert container.corpus is stray
