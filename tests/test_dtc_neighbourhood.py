"""The chain is walked, the context is not — the DTC neighbourhood of an asset.

The question is: standing on one file in the object store, show me its story —
what made it, what it went on to make, through which events. Not the whole
register: a neighbourhood.

The danger is the reason this file exists. From a photograph you reach the tool
that processed it, and from the tool **every other photograph that tool ever
touched**. A ceiling on a node's DEGREE would have been the wrong fix: degree
changes by itself as the data grows, so the same question would answer
differently in March and in July.

**The model already answered it, and the answer is about edges.** Only
`dtc_had_input` / `dtc_had_output` / `dtc_derived_from` are walked; anything
reached by a `has_*` is an ATTRIBUTE of the node you are standing on. Which is
sturdier than a list of forbidden types, and that is what the last test here
proves: a kind of context invented on the spot is non-traversable **by
construction**, with no policy updated and nothing remembered.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from s3dgraphy.dtc import (CHAIN_EDGES, DEFAULT_HOPS, neighbourhood,  # noqa: E402
                           neighbourhood_of_digest)
from s3dgraphy.edges import Edge                              # noqa: E402
from s3dgraphy.graph import Graph                             # noqa: E402
from s3dgraphy.nodes.author_node import AuthorNode            # noqa: E402
from s3dgraphy.nodes.dtc_process_node import DTCProcessNode   # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode        # noqa: E402

BRUNO = "0000-0001-5109-3700"


def digest(n: int) -> str:
    return "sha256:" + f"{n:02x}" * 32


def link(g: Graph, etype: str, source: str, target: str) -> None:
    g.add_edge(f"{etype}:{source}->{target}", source, target, etype)


def dig() -> Graph:
    """A small dig, with the trap in it.

    Two photographs go through ONE tool (`proc-align`, the shared instrument) and
    produce two meshes. `img0`'s mesh then goes through a second process into an
    orthophoto. And the tool carries an author, a licence, and a resource of its
    own — the context that must not become a corridor.

        img0 ─┐                  ┌─ mesh0 ── proc-ortho ── ortho0
              ├─ proc-align ─────┤
        img9 ─┘                  └─ mesh9

    Standing on `img0`, the answer must contain the alignment, `mesh0`,
    `proc-ortho` and `ortho0` — and must NOT contain `img9` or `mesh9`, which are
    only reachable THROUGH the tool's other chain… which is legitimate, so the
    test below is careful to say which reachability is meant.
    """
    g = Graph(graph_id="dig")
    for i in (0, 9):
        g.add_node(ResourceNode(f"img{i}", name=f"IMG_000{i}.jpg",
                                checksum=digest(i), residency="resident"))
        g.add_node(ResourceNode(f"mesh{i}", name=f"mesh{i}.ply",
                                checksum=digest(100 + i), residency="resident"))
    g.add_node(ResourceNode("ortho0", name="ortho0.tif",
                            checksum=digest(200), residency="resident"))
    # the REAL classes, not stand-ins: `add_edge` validates the pair against the
    # connections datamodel and DEGRADES a refused edge to `generic_connection`,
    # so a fixture built out of ad-hoc classes would quietly test a shape that
    # cannot exist. Measured — the first version of this file did exactly that
    # and the chain edges arrived as `generic_connection`.
    for pid, name in (("proc-align", "Alignment"), ("proc-ortho", "Orthophoto")):
        g.add_node(DTCProcessNode(pid, name=name, dtc_kind="transformation"))

    # one tool, two photographs, two meshes
    for i in (0, 9):
        link(g, "dtc_had_input", "proc-align", f"img{i}")
        link(g, "dtc_had_output", "proc-align", f"mesh{i}")
        link(g, "dtc_derived_from", f"mesh{i}", f"img{i}")
    # …and one of the meshes goes on
    link(g, "dtc_had_input", "proc-ortho", "mesh0")
    link(g, "dtc_had_output", "proc-ortho", "ortho0")
    link(g, "dtc_derived_from", "ortho0", "mesh0")

    # the CONTEXT that must stay context
    g.add_node(AuthorNode("author-bruno", name="Bruno", surname="B.",
                          orcid=BRUNO))
    link(g, "has_author", "proc-align", "author-bruno")
    link(g, "has_author", "img0", "author-bruno")
    return g


def ids(answer) -> set:
    return {card["id"] for card in answer["nodes"]}


def card_of(answer, node_id):
    return next(c for c in answer["nodes"] if c["id"] == node_id)


# ── 1 · the chain comes, and the neighbours of the tool do not ───────────────

def test_the_story_of_this_file_is_in_the_answer():
    answer = neighbourhood(dig(), "img0")
    assert answer["start"] == "img0"
    assert {"img0", "proc-align", "mesh0", "proc-ortho", "ortho0"} <= ids(answer)


def test_the_chain_edges_come_with_it_so_nobody_re_derives_the_shape():
    answer = neighbourhood(dig(), "img0")
    drawn = {(e["edge_type"], e["source"], e["target"]) for e in answer["edges"]}
    assert ("dtc_had_output", "proc-align", "mesh0") in drawn
    assert ("dtc_derived_from", "ortho0", "mesh0") in drawn
    # and ONLY chain edges: a `has_author` is context, not a line to draw
    assert all(e["edge_type"] in CHAIN_EDGES for e in answer["edges"])


def test_the_author_is_an_ATTRIBUTE_and_not_a_place_to_continue_from():
    """The whole rule, in one assertion: the author is ON the node, and is not a
    node the walk expanded."""
    answer = neighbourhood(dig(), "img0")
    assert "author-bruno" not in ids(answer)
    context = card_of(answer, "img0")["context"]
    assert [c["id"] for c in context] == ["author-bruno"]
    assert context[0]["edge_type"] == "has_author"
    assert context[0]["role"] == "rights"


def test_the_shared_tool_is_not_a_corridor_to_its_other_photographs():
    """`img9` and `mesh9` are reachable from `img0` — through the tool. They are
    NOT in the answer, because reaching them means walking the tool's OTHER
    chain, and the neighbourhood of a file is not the neighbourhood of the
    instrument that touched it."""
    answer = neighbourhood(dig(), "img0", hops=1)
    assert "img9" not in ids(answer)
    assert "mesh9" not in ids(answer)


# ── 2 · the ceiling bites, and says so ───────────────────────────────────────

def test_the_ceiling_stops_the_walk_and_reports_it():
    answer = neighbourhood(dig(), "img0", hops=1)
    assert answer["hops"] == 1
    assert answer["truncated"] is True, "a walk that stopped must say so"
    assert answer["frontier"], "…and which nodes it left unexpanded"
    # ONE hop from img0 is the alignment AND mesh0 — because `dtc_derived_from`
    # runs output → input directly, so the mesh is a neighbour of the photograph
    # and not two steps away through the event. Measured, and worth stating: a
    # reader who assumed «one hop = one event» would have set the ceiling wrong.
    assert ids(answer) == {"img0", "proc-align", "mesh0"}
    assert "proc-ortho" in answer["frontier"]


def test_a_walk_that_reached_the_end_does_not_claim_it_was_cut():
    answer = neighbourhood(dig(), "img0")
    assert answer["truncated"] is False
    assert answer["frontier"] == []


def test_the_default_ceiling_is_generous_because_it_is_a_safety_net():
    """With the context excluded the graph stays local by itself, so this only
    has to stop a pathological chain-of-chains."""
    assert DEFAULT_HOPS >= 4
    assert neighbourhood(dig(), "img0")["hops"] == DEFAULT_HOPS


def test_zero_hops_is_the_node_and_its_context():
    answer = neighbourhood(dig(), "img0", hops=0)
    assert ids(answer) == {"img0"}
    assert [c["id"] for c in card_of(answer, "img0")["context"]] == ["author-bruno"]
    assert answer["truncated"] is True


# ── 3 · what a reader gets ───────────────────────────────────────────────────

def test_each_node_says_how_far_it_is():
    answer = neighbourhood(dig(), "img0")
    assert card_of(answer, "img0")["hop"] == 0
    assert card_of(answer, "proc-align")["hop"] == 1
    assert card_of(answer, "mesh0")["hop"] == 1, "the derivation edge is direct"
    assert card_of(answer, "ortho0")["hop"] == 2


def test_the_kind_is_READ_and_never_written_down_here():
    answer = neighbourhood(dig(), "img0")
    assert card_of(answer, "proc-align")["dtc_kind"] == "transformation"
    source = (pathlib.Path(__file__).resolve().parent.parent
              / "src" / "s3dgraphy" / "dtc" / "neighbourhood.py").read_text()
    from s3dgraphy.utils.utils import get_dtc_kinds
    kinds = {k for axis in get_dtc_kinds().values() for k in axis}
    written = [k for k in kinds if f'"{k}"' in source]
    assert not written, f"a dtc_kind is hard-coded here: {written}"


def test_a_node_that_is_not_there_is_an_honest_nothing():
    answer = neighbourhood(dig(), "no-such-node")
    assert answer["start"] is None
    assert answer["nodes"] == [] and answer["edges"] == []
    assert answer["truncated"] is False


def test_a_removed_resource_is_not_part_of_the_story():
    from s3dgraphy.crdt import REMOVED_KEY

    g = dig()
    mesh = g.find_node_by_id("mesh0")
    # the shape the rest of the suite uses: a MARK with a time and a hand, not a
    # bare True — `is_removed` decides against the node's own later edits, so the
    # timestamp is part of the tombstone and not decoration.
    mesh.data[REMOVED_KEY] = {"ts": "2026-09-02T10:00:00Z", "by": BRUNO}
    answer = neighbourhood(g, "img0")
    assert "mesh0" not in ids(answer)
    # …and so is everything only reachable through it
    assert "ortho0" not in ids(answer)


# ── 4 · entered by digest, which is what a store-browser has ─────────────────

def test_the_neighbourhood_can_be_entered_by_an_asset_digest():
    answer = neighbourhood_of_digest(dig(), digest(0))
    assert answer["start"] == "img0"


def test_a_digest_nobody_has_is_an_honest_nothing():
    answer = neighbourhood_of_digest(dig(), "sha256:" + "ff" * 32)
    assert answer["start"] is None


# ── 5 · the property that makes the rule sturdier than a list ───────────────

def test_a_kind_of_context_NOBODY_CLASSIFIED_is_not_traversable():
    """This is the test the design argument rests on.

    `has_geoposition` is a REAL edge of the connections datamodel and appears
    nowhere in this traversal, nor in `ingest._USAGE_ROLES`. It must still be
    treated as context — because the rule names the three edges that ARE the
    chain, and everything else is, by construction, something hanging off a node.
    No list to update, and nothing to remember.

    (An earlier version of this test invented `has_funding_body`. It could not be
    written: `Edge.__init__` refuses a type the datamodel does not declare, so an
    unknown edge cannot exist in a graph at all. Which is a stronger guarantee
    than the test was reaching for, and worth knowing — the danger is not an
    unknown edge, it is a KNOWN edge nobody thought about.)
    """
    from s3dgraphy.nodes.geo_position_node import GeoPositionNode

    g = dig()
    g.add_node(GeoPositionNode("place", epsg=4326))
    link(g, "has_geoposition", "img0", "place")
    # …and the place has a chain of its own, which must stay out of the answer
    g.add_node(ResourceNode("elsewhere", name="other-project.ply",
                            checksum=digest(250), residency="resident"))
    link(g, "dtc_derived_from", "elsewhere", "place")

    answer = neighbourhood(g, "img0")
    assert "place" not in ids(answer), "an unclassified `has_*` was walked"
    assert "elsewhere" not in ids(answer), "…and it led into another story"
    context = card_of(answer, "img0")["context"]
    assert "place" in [c["id"] for c in context]
    assert next(c for c in context if c["id"] == "place")["role"] == "context", \
        "an edge nobody classified must default to context, never to chain"


# ── 6 · the classification lives in the datamodel, not in the code ──────────

def test_the_chain_edges_are_READ_from_the_datamodel():
    """Not a tuple in the source: the datamodel marks them `dtc_role: "chain"`,
    and both this walk and the client read that one place."""
    from s3dgraphy.edges import get_connections_datamodel

    marked = {name for name, definition
              in get_connections_datamodel()._canonical_edges.items()
              if isinstance(definition, dict)
              and definition.get("dtc_role") == "chain"}
    assert marked == set(CHAIN_EDGES)
    assert marked == {"dtc_had_input", "dtc_had_output", "dtc_derived_from"}


def test_a_dtc_edge_that_is_NOT_marked_is_not_traversed():
    """The whole point of the marker, and the failure it prevents.

    A `dtc_*` edge that is CONTEXT — an annotation, a note, a tool one day — must
    not be a corridor. A classification by PREFIX would have walked it; a
    classification by MARKER does not, and adding the edge is a JSON entry.
    """
    from s3dgraphy.dtc.neighbourhood import _chain_edges

    # the datamodel as it would be with a new, UNMARKED dtc_* edge in it
    edge_types = {
        "dtc_had_input": {"dtc_role": "chain"},
        "dtc_had_output": {"dtc_role": "chain"},
        "dtc_derived_from": {"dtc_role": "chain"},
        "dtc_annotated_by": {"label": "annotated by"},      # no dtc_role
    }
    marked = tuple(n for n, d in edge_types.items() if d.get("dtc_role") == "chain")
    assert "dtc_annotated_by" not in marked
    # …and the reader agrees with that arithmetic on the REAL datamodel
    assert "dtc_annotated_by" not in _chain_edges()


def test_the_fallback_is_the_historical_three_and_never_nothing(monkeypatch):
    """A vendored datamodel from before the marker must not make the walk
    traverse nothing: a walk that quietly returns one node is worse than one that
    answers the way it always did."""
    # `import s3dgraphy.dtc.neighbourhood as nb` does NOT give the module: the
    # package exports a FUNCTION with that name, and the `as` binding is a
    # getattr on the package. Worth ten minutes to somebody one day, so it is
    # written here rather than discovered again.
    from importlib import import_module

    nb = import_module("s3dgraphy.dtc.neighbourhood")

    class Empty:
        _canonical_edges = {"dtc_had_input": {}, "has_author": {}}

    monkeypatch.setattr("s3dgraphy.edges.get_connections_datamodel",
                        lambda *a, **k: Empty())
    assert nb._chain_edges() == ("dtc_had_input", "dtc_had_output",
                                 "dtc_derived_from")
