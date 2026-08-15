"""The catalogue card, derived from a container — and never invented.

`study_metadata` is the seam that lets a catalogue keep its index as a
PROJECTION: every field comes from the container, so re-reading the containers
rebuilds the index. Two properties matter more than the field list, and both are
asserted here:

* **derived** — the same container always yields the same card, and a card built
  from a Container equals the one built from its document;
* **honest** — a container that does not say something produces `None`, not a
  plausible default. An invented licence is a licence nobody granted.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from s3dgraphy import api                                        # noqa: E402
from s3dgraphy.container import container_of, save_container_file  # noqa: E402
from s3dgraphy.graph import Graph                                # noqa: E402
from s3dgraphy.importer.emjson_importer import (                 # noqa: E402
    materialize_graph_scope)
from s3dgraphy.nodes import StratigraphicUnit                    # noqa: E402
from s3dgraphy.nodes.hdt_node import HDTNode                     # noqa: E402
from s3dgraphy.nodes.heritage_entity_node import (               # noqa: E402
    HeritageEntityNode)
from s3dgraphy.study import normalise_visibility                 # noqa: E402


def _study(**header):
    graph = Graph(graph_id="sarmizegetusa-2026")
    graph.name = {"default": "Sarmizegetusa · campagna 2026"}
    graph.add_node(StratigraphicUnit("US1", name="US 1"))
    root = materialize_graph_scope(
        graph, author="Emanuel Demetrescu", license="CC-BY-4.0",
        em_id="SARM26", orcid="0000-0002-1825-0097")
    root.data["site_position"] = {"lat": 45.62, "lon": 23.31, "crs": "EPSG:4326"}
    graph.add_node(HDTNode("hdt_sarm", name="Sarmizegetusa HDT",
                           heritage_entity_iri="https://example.org/h/sarm"))
    graph.add_node(HeritageEntityNode("hc1_sarm", name="Sarmizegetusa Regia",
                                      entity_kind="site"))
    container = container_of(graph)
    container.header = {"format": "em.json", "version": "1.0", **header}
    return container


def _bare():
    """A study that says nothing about itself beyond its graph."""
    graph = Graph(graph_id="scavo-anonimo")
    graph.add_node(StratigraphicUnit("US1", name="US 1"))
    container = container_of(graph)
    container.header = {"format": "em.json", "version": "1.0"}
    return container


# ── what it reads, and from where ────────────────────────────────────────────

def test_the_card_is_read_from_the_graph_scope_nodes():
    """DP-65 is where authorship and licence live. The catalogue EXPOSES them."""
    card = api.study_metadata(_study(title="Sarmizegetusa 2026"),
                              study_id="study:abc")
    assert card["authors"] == [{"name": "Emanuel Demetrescu",
                                "orcid": "0000-0002-1825-0097"}]
    assert card["license"] == "CC-BY-4.0"
    assert card["em_id"] == "SARM26"
    assert card["title"] == "Sarmizegetusa 2026"


def test_the_hdt_pair_is_the_hdt_o_vocabulary():
    """HC2 groups the studies of one heritage object over time; HC1 is the
    object. Both come from the nodes HDT-O already defines."""
    card = api.study_metadata(_study())
    assert card["hc2"]["id"] == "hdt_sarm"
    assert card["hc2"]["iri"] == "https://example.org/h/sarm"
    assert card["hc1"]["id"] == "hc1_sarm"
    assert card["hc1"]["kind"] == "site"


def test_hc1_falls_back_to_the_iri_the_twin_carries():
    """The same fact recorded two ways. A catalogue that understood only the
    node would fail to group half the studies."""
    graph = Graph(graph_id="solo-hdt")
    graph.add_node(HDTNode("hdt_x", name="X HDT",
                           heritage_entity_iri="https://example.org/h/x"))
    card = api.study_metadata(container_of(graph))
    assert card["hc2"]["id"] == "hdt_x"
    assert card["hc1"]["iri"] == "https://example.org/h/x"


def test_spatial_is_the_site_not_the_shift():
    """`site_position` is a place on Earth; the georeferencing shift is an offset
    in a scene. Confusing them puts a study in the Gulf of Guinea."""
    card = api.study_metadata(_study())
    assert card["spatial"] == {"lat": 45.62, "lon": 23.31, "crs": "EPSG:4326"}


def test_the_title_falls_back_to_the_active_graph_never_to_a_placeholder():
    card = api.study_metadata(_study())
    assert card["title"] == "Sarmizegetusa · campagna 2026"


# ── what it refuses to invent ────────────────────────────────────────────────

def test_a_container_that_says_nothing_produces_honest_gaps():
    card = api.study_metadata(_bare())
    assert card["authors"] == []
    assert card["license"] is None
    assert card["embargo"] is None
    assert card["hc1"] is None and card["hc2"] is None
    assert card["spatial"] is None
    assert card["id"] is None, "a library does not mint identities"
    # …and the schema is still complete: an index needs stable keys
    for key in ("id", "title", "authors", "license", "visibility", "version",
                "hc1", "hc2", "spatial", "graph_ids", "checksum"):
        assert key in card


def test_visibility_defaults_to_restricted_and_reads_both_spellings():
    """The spec writes `public|private`, the rooms write `public|restricted`.
    One concept, two spellings — and anything unknown is restricted, because a
    study served too openly cannot be un-served."""
    assert api.study_metadata(_bare())["visibility"] == "restricted"
    assert api.study_metadata(_study(visibility="public"))["visibility"] == "public"
    assert api.study_metadata(_study(visibility="private"))["visibility"] == "restricted"
    assert normalise_visibility("PUBLIC") == "public"
    assert normalise_visibility("yes-please") == "restricted"
    assert normalise_visibility(None) == "restricted"


# ── derived, therefore stable ────────────────────────────────────────────────

def test_the_same_container_always_gives_the_same_card():
    a = api.study_metadata(_study(title="T"), study_id="study:abc")
    b = api.study_metadata(_study(title="T"), study_id="study:abc")
    assert a == b
    assert a["checksum"].startswith("sha256:")


def test_the_document_and_the_container_agree(tmp_path):
    """A catalogue holds DOCUMENTS. If the two paths disagreed, the index would
    depend on which one the indexer happened to take."""
    container = _study(title="T", visibility="public")
    path = tmp_path / "study.em.json"
    save_container_file(container, str(path))
    doc = json.loads(path.read_text(encoding="utf-8"))

    from_doc = api.study_metadata(doc, study_id="study:abc")
    from_container = api.study_metadata(container, study_id="study:abc")
    assert from_doc["checksum"] == from_container["checksum"]
    for key in ("authors", "license", "hc1", "hc2", "spatial", "graph_ids",
                "visibility", "em_id"):
        assert from_doc[key] == from_container[key], key


def test_the_checksum_moves_when_the_content_moves():
    """It is the oracle a catalogue uses to answer "is the copy I indexed still
    the copy you have" — so it has to be a function of the content."""
    before = api.study_metadata(_study())["checksum"]
    container = _study()
    container.graphs["sarmizegetusa-2026"].add_node(
        StratigraphicUnit("US2", name="US 2"))
    assert api.study_metadata(container)["checksum"] != before


def test_legacy_containers_still_catalogue():
    """Written before MIG1-A: authorship and licence as bare `graph.data`. Read
    as a fallback, never written back."""
    graph = Graph(graph_id="vecchio")
    graph.data["authors"] = ["Tizio"]
    graph.data["license"] = "CC-BY-NC"
    card = api.study_metadata(container_of(graph))
    assert card["authors"] == [{"name": "Tizio", "orcid": None}]
    assert card["license"] == "CC-BY-NC"


def test_it_refuses_something_that_is_not_a_container():
    with pytest.raises(TypeError):
        api.study_metadata(object())
