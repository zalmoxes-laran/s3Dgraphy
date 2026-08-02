"""N0 — the narrative model: NarrativeNode, Chapter, Block.

A narrative is the story told OVER a graph — chapters anchored to its lanes,
each carrying prose and embeds. Two properties are load-bearing and are what
these tests defend:

* **an embed is a reference, never a copy** — it holds a stable id and nothing
  else, so a narrative always says what the graph currently says;
* **the round trip is lossless** — chapters survive em.json without a
  SCHEMA_VERSION bump, because to a reader that has never heard of narratives a
  NarrativeNode is just a node with an unfamiliar type and some data.
"""

import json
import pathlib

import pytest

from s3dgraphy.api import graph_to_emjson, load_emjson, load_emjson_file
from s3dgraphy.exporter.emjson_exporter import SCHEMA_VERSION
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import (BLOCK_EMBED, BLOCK_PROSE, NARRATIVE_VIEW_TYPES,
                             Block, Chapter, NarrativeError, NarrativeNode)
from s3dgraphy.nodes.base_node import Node
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "PortaMarina-lite.em.json"


def _narrative(graph):
    return next(n for n in graph.nodes if n.node_type == "narrative")


# ── the node ──────────────────────────────────────────────────────────────────

def test_it_is_a_registered_node_type():
    """First-class, so it can be queried and versioned like anything else."""
    assert Node.node_type_map["narrative"] is NarrativeNode


def test_metadata_is_written_only_when_given():
    """A narrative that declares no language differs from one declaring
    'unknown'; the model keeps the difference."""
    bare = NarrativeNode("n1", "Storia")
    assert "lang" not in bare.data
    tagged = NarrativeNode("n2", "Storia", lang="it", license="CC-BY")
    assert tagged.data["lang"] == "it"
    assert tagged.data["license"] == "CC-BY"


# ── blocks ────────────────────────────────────────────────────────────────────

def test_a_prose_block_owns_its_text():
    b = Block.prose("Porta Marina è l'accesso occidentale.")
    assert b.block_type == BLOCK_PROSE
    assert b.to_dict() == {"block_type": "prose",
                           "text": "Porta Marina è l'accesso occidentale."}


def test_an_embed_owns_nothing_but_the_reference():
    """No title, no thumbnail, no cached value: anything it cached could go
    stale, and staleness is exactly what referencing avoids."""
    b = Block.embed("US.101", "us")
    assert b.to_dict() == {"block_type": "embed", "ref": "US.101",
                           "view_type": "us"}


def test_an_embed_needs_a_ref():
    with pytest.raises(NarrativeError):
        Block(block_type=BLOCK_EMBED, view_type="us")


def test_the_view_type_must_be_one_the_model_knows():
    with pytest.raises(NarrativeError):
        Block.embed("US.101", "hologram")


@pytest.mark.parametrize("view_type", NARRATIVE_VIEW_TYPES)
def test_every_declared_view_type_is_accepted(view_type):
    assert Block.embed("X", view_type).view_type == view_type


def test_the_enum_matches_the_datamodel():
    """The tuple in code and the `valid_view_types` in the datamodel are the
    same vocabulary; if they drift, one of the two is lying."""
    from s3dgraphy.nodes.base_node import load_json_mapping
    dm = load_json_mapping("s3Dgraphy_node_datamodel.json")
    declared = dm["narrative_nodes"]["NarrativeNode"]["valid_view_types"]
    assert set(declared) == set(NARRATIVE_VIEW_TYPES)


# ── chapters ──────────────────────────────────────────────────────────────────

def test_chapters_keep_the_order_they_were_added_in():
    """The reason chapters are a list and not a set of nodes: order is the
    content, not metadata about it."""
    n = NarrativeNode("n1", "Storia")
    for title in ("Presentazione", "Dove si trova", "Età imperiale"):
        n.add_chapter(title)
    assert [c.title for c in n.chapters] == [
        "Presentazione", "Dove si trova", "Età imperiale"]


def test_a_chapter_is_found_by_the_lane_it_narrates():
    """One lane, one chapter — this is what the scaffolder merges on."""
    n = NarrativeNode("n1", "Storia")
    n.add_chapter("Età imperiale", anchor="EP.imperiale")
    assert n.chapter_by_anchor("EP.imperiale").title == "Età imperiale"
    assert n.chapter_by_anchor("EP.altro") is None
    assert n.chapter_by_anchor(None) is None


def test_an_anchorless_chapter_omits_the_key():
    assert "anchor" not in Chapter(title="Presentazione").to_dict()


# ── references ────────────────────────────────────────────────────────────────

def test_referenced_ids_are_in_order_and_unique():
    n = NarrativeNode("n1", "Storia")
    c = n.add_chapter("Cap")
    c.add_embed("D.1", "source")
    c.add_prose("del testo in mezzo")
    c.add_embed("US.101", "us")
    c.add_embed("D.1", "document")      # same resource, another view
    assert n.referenced_ids() == ["D.1", "US.101"]


def test_a_dangling_reference_is_named():
    """An embed can point at something that has left the graph. Saying which
    beats rendering a blank."""
    g = Graph(graph_id="g")
    g.add_node(StratigraphicUnit(node_id="US.101", name="US101"))
    n = NarrativeNode("n1", "Storia")
    c = n.add_chapter("Cap")
    c.add_embed("US.101", "us")
    c.add_embed("US.999", "us")
    g.add_node(n)
    assert n.unresolved_refs(g) == ["US.999"]


# ── em.json round trip ────────────────────────────────────────────────────────

def _round_trip(node):
    g = Graph(graph_id="g")
    g.add_node(node)
    doc = json.loads(json.dumps(graph_to_emjson(g)))
    reloaded, _warnings = load_emjson(doc)
    return _narrative(reloaded)


def test_a_narrative_survives_em_json_intact():
    n = NarrativeNode("n1", "Storia", lang="it", template_id="site_story")
    intro = n.add_chapter("Presentazione", canonical=True)
    intro.add_prose("Il sito…")
    intro.add_embed("D.1", "source")
    cap = n.add_chapter("Età imperiale", anchor="EP.1")
    cap.add_embed("US.101", "us", highlight=True)

    back = _round_trip(n)
    assert isinstance(back, NarrativeNode)
    assert back.data["lang"] == "it"
    assert back.data["template_id"] == "site_story"
    assert [c.title for c in back.chapters] == ["Presentazione", "Età imperiale"]
    assert back.chapters[0].canonical is True
    assert back.chapters[1].anchor == "EP.1"
    assert back.chapters[1].blocks[0].options == {"highlight": True}
    assert back.referenced_ids() == ["D.1", "US.101"]


def test_the_round_trip_is_byte_stable():
    """Export → import → export must give the same document, or an edit would
    show up as a diff nobody made."""
    n = NarrativeNode("n1", "Storia")
    c = n.add_chapter("Cap", anchor="EP.1")
    c.add_prose("testo")
    c.add_embed("D.1", "source")
    g = Graph(graph_id="g")
    g.add_node(n)
    once = json.dumps(graph_to_emjson(g), sort_keys=True)
    reloaded, _ = load_emjson(json.loads(once))
    twice = json.dumps(graph_to_emjson(reloaded), sort_keys=True)
    assert once == twice


def test_chapters_are_not_duplicated_between_data_and_attribute():
    """One copy: `chapters` is owned by the attribute and rendered into data{}
    on the way out. Two copies would drift."""
    n = NarrativeNode("n1", "Storia")
    n.add_chapter("Cap")
    assert "chapters" not in n.data
    assert len(n.to_data()["chapters"]) == 1


def test_no_schema_bump_was_needed():
    """A NarrativeNode is a node with an unfamiliar node_type and some data —
    precisely the forward-compatible degradation the format was built for, so
    nothing about the SCHEMA_VERSION contract changes."""
    assert SCHEMA_VERSION == 2


def test_an_older_reader_degrades_without_losing_the_content():
    """Simulate a build that has never heard of narratives: the node falls back
    to base Node, warns, and the chapters survive in data{} — recoverable."""
    n = NarrativeNode("n1", "Storia")
    n.add_chapter("Cap").add_embed("D.1", "source")
    g = Graph(graph_id="g")
    g.add_node(n)
    doc = json.loads(json.dumps(graph_to_emjson(g)))
    saved = Node.node_type_map.pop("narrative")
    try:
        reloaded, warnings = load_emjson(doc)
        node = next(x for x in reloaded.nodes if x.node_id == "n1")
        assert type(node) is Node
        assert any("unknown node_type 'narrative'" in w for w in warnings)
        assert node.data["chapters"][0]["blocks"][0]["ref"] == "D.1"
    finally:
        Node.node_type_map["narrative"] = saved


# ── the PortaMarina-lite fixture ──────────────────────────────────────────────

def test_the_fixture_loads_and_is_shaped_as_the_spec_describes():
    graph, _warnings = load_emjson_file(str(FIXTURE))
    n = _narrative(graph)
    titles = [c.title for c in n.chapters]
    assert titles == ["Presentazione", "Dove si trova", "Età imperiale"]
    # the two canonical chapters (intro + geo) and one epoch chapter
    assert [c.canonical for c in n.chapters] == [True, True, False]
    assert n.chapters[2].anchor == "EP.imperiale"
    kinds = [b.view_type for c in n.chapters for b in c.blocks
             if b.block_type == BLOCK_EMBED]
    assert kinds == ["source", "source", "map", "us", "us", "paradata"]


def test_every_reference_in_the_fixture_resolves():
    """It is the data N2 renders: a dangling ref there would be a bug in the
    fixture, not in the viewer."""
    graph, _warnings = load_emjson_file(str(FIXTURE))
    assert _narrative(graph).unresolved_refs(graph) == []


def test_the_fixture_re_exports_identically():
    graph, _warnings = load_emjson_file(str(FIXTURE))
    on_disk = json.loads(FIXTURE.read_text())
    assert (json.dumps(graph_to_emjson(graph), sort_keys=True)
            == json.dumps(on_disk, sort_keys=True))


# ── RDF projection (two-tier: authoring is the property graph above) ──────────

def test_the_projection_types_it_and_emits_its_references():
    """The RDF side restates what the property graph already says — it never
    originates anything. What it adds is queryability: the citations become
    P67_refers_to, so "which narratives cite this US" is one SPARQL line
    instead of a text search over prose.
    """
    rdflib = pytest.importorskip("rdflib")
    from s3dgraphy.api import project_ttl

    graph, _warnings = load_emjson_file(str(FIXTURE))
    ttl = project_ttl(graph)
    parsed = rdflib.Graph()
    parsed.parse(data=ttl, format="turtle")

    CRM = rdflib.Namespace("http://www.cidoc-crm.org/cidoc-crm/")
    EM = rdflib.Namespace("https://w3id.org/em/ontology#")
    narrative_iri = next(
        s for s in parsed.subjects(rdflib.RDF.type, EM.Narrative))

    # typed as a text, and as a text ABOUT something
    assert (narrative_iri, rdflib.RDF.type, CRM.E33_Linguistic_Object) in parsed
    # every embed became a reference, none was invented
    refs = set(parsed.objects(narrative_iri, CRM.P67_refers_to))
    assert len(refs) == len(_narrative(graph).referenced_ids())
    assert any(str(r).endswith("/US.101") for r in refs)
    # the language is carried through
    assert (narrative_iri, CRM.P72_has_language,
            rdflib.Literal("it")) in parsed


def test_the_chapters_are_not_reified_into_triples():
    """Order and nesting are an authoring concern. Reifying every block would
    put a document tree into a knowledge graph for a query nobody runs — and it
    is the sort of thing that quietly turns into triple-first authoring."""
    pytest.importorskip("rdflib")
    from s3dgraphy.api import project_ttl

    graph, _warnings = load_emjson_file(str(FIXTURE))
    ttl = project_ttl(graph)
    assert "Chapter" not in ttl
    assert "block_type" not in ttl
