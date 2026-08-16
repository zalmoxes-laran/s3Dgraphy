"""The asset enrichment protocol: attribution is an ACT, and somebody signs it.

`docs/asset-dtc-protocol.md` is the contract; this is the contract executed.
What is defended:

* the **author** (who made the data) and the **attributor** (who says so) are
  two people, and the model must not flatten them — the normal case for anything
  catalogued after the fact is that they differ, and posthumous is legal;
* the three states of a field: untouched / declared / **retracted**, because
  "not declared" and "declared to be nothing" are different sentences;
* idempotence per (checksum, field), so a re-run leaves one statement;
* **tombstones are never reused** — the seam that bit twice in one night;
* and the reader (`asset_rights`) sees what the writer wrote: enrichment the
  reader cannot see is enrichment that changed nothing.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from s3dgraphy import api as em                              # noqa: E402
from s3dgraphy.graph import Graph                            # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode       # noqa: E402

ATTRIBUTOR = "0000-0002-1825-0097"     # the cataloguer, at the keyboard
AUTHOR = "0000-0001-5109-3700"         # who took the photograph, in 1978
DIGEST = "sha256:" + "ab" * 32


def graph_with_asset() -> Graph:
    g = Graph(graph_id="g")
    g.add_node(ResourceNode("img", name="Prospetto nord", checksum=DIGEST,
                            residency="resident"))
    return g


def as_document(g: Graph) -> dict:
    return {"graphs": {"g": {
        "nodes": [{"id": n.node_id, "node_type": n.node_type, "name": n.name,
                   "data": n.data} for n in g.nodes],
        "edges": [{"id": e.edge_id, "source": e.edge_source,
                   "target": e.edge_target, "edge_type": e.edge_type}
                  for e in g.edges]}}}


def kind(g: Graph, node_type: str):
    return [n for n in g.nodes if n.node_type == node_type]


def test_the_author_is_not_the_attributor_and_the_act_is_signed():
    g = graph_with_asset()
    report = em.enrich_asset_dtc(g, DIGEST, attributor=ATTRIBUTOR, author=AUTHOR,
                                 author_name="Bruno Rossi", license="CC-BY-4.0",
                                 at="2026-08-16T20:00:00Z")
    assert report["changed"] == {"author": "declared", "license": "declared"}

    author = kind(g, "author")[0]
    assert author.data["orcid"] == AUTHOR, "who MADE it"
    assert author.name == "Bruno Rossi", "…shown as a person, not as an iD"
    assert author.data["attributed_by"] == ATTRIBUTOR, "who SAYS so"
    assert author.data["attributed_at"] == "2026-08-16T20:00:00Z"
    # the licence carries the same signature: it is the same act
    assert kind(g, "license")[0].data["attributed_by"] == ATTRIBUTOR

    # …and the edges are the datamodel's own, from the resource
    assert {(e.edge_source, e.edge_type) for e in g.edges} == {
        ("img", "has_author"), ("img", "has_license")}


def test_the_reader_sees_what_the_writer_wrote():
    """Enrichment the one reader cannot see is enrichment that changed nothing —
    and that reader is what em-server consults before serving bytes."""
    g = graph_with_asset()
    em.enrich_asset_dtc(g, DIGEST, attributor=ATTRIBUTOR, author=AUTHOR,
                        author_name="Bruno Rossi", license="CC-BY-4.0",
                        embargo="2099-01-01")
    rights = em.asset_rights(as_document(g), DIGEST)
    assert rights["license"] == "CC-BY-4.0"
    assert rights["embargo_active"] is True
    assert rights["authors"] == [{"name": "Bruno Rossi", "orcid": AUTHOR}]


def test_a_field_nobody_mentioned_is_left_alone():
    """Declaring a licence must not silently clear an embargo somebody set."""
    g = graph_with_asset()
    em.enrich_asset_dtc(g, DIGEST, attributor=ATTRIBUTOR, embargo="2099-01-01")
    em.enrich_asset_dtc(g, DIGEST, attributor=ATTRIBUTOR, license="CC-BY-4.0")
    assert len(kind(g, "embargo")) == 1 and len(kind(g, "license")) == 1


def test_the_empty_string_retracts_and_none_does_not():
    g = graph_with_asset()
    em.enrich_asset_dtc(g, DIGEST, attributor=ATTRIBUTOR, license="CC-BY-4.0")
    em.enrich_asset_dtc(g, DIGEST, attributor=ATTRIBUTOR, license="")
    assert kind(g, "license") == []
    # and nothing is left pointing at it
    assert not [e for e in g.edges if e.edge_type == "has_license"]
    # …while the reader goes back to "not declared", with the default beside it
    rights = em.asset_rights(as_document(g), DIGEST)
    assert rights["license"] is None
    assert rights["license_effective"] == "CC-BY-SA-4.0"
    assert rights["license_is_default"] is True


def test_running_it_twice_leaves_one_statement():
    g = graph_with_asset()
    for _ in range(3):
        em.enrich_asset_dtc(g, DIGEST, attributor=ATTRIBUTOR, license="CC-BY-4.0")
    assert len(kind(g, "license")) == 1
    assert len([e for e in g.edges if e.edge_type == "has_license"]) == 1


def test_a_revision_re_signs_the_statement():
    """An attribution somebody edited is theirs now, not still the first
    person's."""
    g = graph_with_asset()
    em.enrich_asset_dtc(g, DIGEST, attributor=ATTRIBUTOR, license="CC-BY-4.0",
                        at="2026-01-01T00:00:00Z")
    em.enrich_asset_dtc(g, DIGEST, attributor=AUTHOR, license="CC-BY-SA-4.0",
                        at="2026-08-16T00:00:00Z")
    licence = kind(g, "license")[0]
    assert licence.data["license_type"] == "CC-BY-SA-4.0"
    assert licence.data["attributed_by"] == AUTHOR
    assert licence.data["attributed_at"] == "2026-08-16T00:00:00Z"


def test_a_tombstoned_statement_is_not_reused():
    """The seam that bit twice: a removed node is not a node to write the next
    statement onto."""
    from s3dgraphy.crdt import REMOVED_KEY

    g = graph_with_asset()
    em.enrich_asset_dtc(g, DIGEST, attributor=ATTRIBUTOR, license="CC-BY-4.0")
    dead = kind(g, "license")[0]
    dead.data[REMOVED_KEY] = {"ts": "2026-08-16T10:00:00Z", "by": ATTRIBUTOR}

    em.enrich_asset_dtc(g, DIGEST, attributor=ATTRIBUTOR, license="CC-BY-SA-4.0")
    alive = [n for n in kind(g, "license") if REMOVED_KEY not in (n.data or {})]
    assert len(alive) == 1 and alive[0].node_id != dead.node_id
    assert em.asset_rights(as_document(g), DIGEST)["license"] == "CC-BY-SA-4.0"


def test_an_attribution_nobody_signs_is_refused():
    g = graph_with_asset()
    with pytest.raises(ValueError, match="attributor"):
        em.enrich_asset_dtc(g, DIGEST, attributor=None, license="CC-BY-4.0")


def test_a_digest_nothing_points_at_is_a_lookup_error_not_a_new_node():
    """It enriches an asset; it does not invent one. A node conjured to hold a
    licence would be a resource nobody uploaded."""
    g = graph_with_asset()
    with pytest.raises(LookupError):
        em.enrich_asset_dtc(g, "sha256:" + "cd" * 32, attributor=ATTRIBUTOR,
                            license="CC-BY-4.0")
    assert kind(g, "license") == []


# ── the ROOT of the "half data" bug, on the Python side ──────────────────────

def test_a_multi_field_data_update_arrives_whole():
    """The bug, generalised: a change to two `data` fields must arrive as two
    field operations, and a partial update must not leave a stale sibling.

    It was found on a licence (the name changed, `data.license_type` did not),
    but the question is not about licences: it is whether the field-level CRDT
    carries the whole `data` map. Asked here of an ordinary resource, with no
    rights in sight, so the answer cannot be accidentally about one field."""
    section = {"graph_id": "g", "nodes": [
        {"id": "R1", "node_type": "resource", "name": "foto",
         "data": {"checksum": "sha256:aa", "media_type": "image/png",
                  "size": 10}}], "edges": []}

    for field, value in (("data.media_type", "image/tiff"), ("data.size", 42),
                         ("name", "prospetto")):
        result = em.apply_op(section, {"op": "update_field", "node_id": "R1",
                                       "field": field, "value": value,
                                       "ts": "2026-08-16T20:00:00Z",
                                       "author": ATTRIBUTOR})
        assert result["applied"] is True, (field, result)

    node = section["nodes"][0]
    assert node["name"] == "prospetto"
    assert node["data"]["media_type"] == "image/tiff"
    assert node["data"]["size"] == 42, "the SECOND field is the half that was lost"
    assert node["data"]["checksum"] == "sha256:aa", "…and the untouched sibling stays"


def test_an_older_write_does_not_resurrect_a_stale_sibling():
    """Field-level means per-field clocks: a late operation on one field must
    not drag the others back to what they were when it was made."""
    section = {"graph_id": "g", "nodes": [
        {"id": "R1", "node_type": "resource", "name": "foto",
         "data": {"media_type": "image/png", "size": 10}}], "edges": []}
    em.apply_op(section, {"op": "update_field", "node_id": "R1",
                          "field": "data.size", "value": 42,
                          "ts": "2026-08-16T20:00:00Z", "author": ATTRIBUTOR})
    stale = em.apply_op(section, {"op": "update_field", "node_id": "R1",
                                  "field": "data.size", "value": 7,
                                  "ts": "2026-08-16T10:00:00Z",
                                  "author": AUTHOR})
    assert stale["applied"] is False, "an older write loses"
    assert section["nodes"][0]["data"]["size"] == 42
    assert section["nodes"][0]["data"]["media_type"] == "image/png"
