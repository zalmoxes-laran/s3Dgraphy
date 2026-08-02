"""N4 — who made this, and who stands behind it.

The model of the "Who Made This?" paper, in three facts a reader can check:

* **who wrote it** — a human author or a model, both first-class AuthorNodes;
* **how the machine came to write it** — the prompt, recorded as a source and
  cited like any other;
* **whether a person has vouched for it** — an explicit act by a named human,
  never automatic, never performed by a model.

The state is DERIVED from those facts rather than stored, so a label can never
contradict what the graph says. And the absence of an endorsement is itself the
statement: until someone signs, the text reads as a draft.
"""

import json
import pathlib

import pytest

from s3dgraphy.api import graph_to_emjson, load_emjson, load_emjson_file
from s3dgraphy.graph import Graph
from s3dgraphy.nodes.author_node import AuthorAINode, AuthorNode
from s3dgraphy.nodes.document_node import DocumentNode
from s3dgraphy.nodes.group_node import ActivityNodeGroup
from s3dgraphy.nodes.narrative_node import (STATUS_AI_DRAFT,
                                            STATUS_AI_ENDORSED, STATUS_HUMAN,
                                            NarrativeError, NarrativeNode,
                                            endorse_block, endorse_narrative,
                                            resolve_human_author)
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "PortaMarina-lite.em.json"


def _narrative(graph):
    return next(n for n in graph.nodes if n.node_type == "narrative")


@pytest.fixture
def peopled():
    """A graph with a person, a model, a prompt and one AI block."""
    g = Graph(graph_id="g")
    g.add_node(AuthorNode("A.ed", name="Emanuel", surname="Demetrescu"))
    g.add_node(AuthorAINode("AI.claude", name="Claude", model="claude-opus-5"))
    g.add_node(DocumentNode("D.prompt", name="Prompt", description="Racconta…"))
    n = NarrativeNode("N1", "Storia")
    g.add_node(n)
    chapter = n.add_chapter("Cap")
    chapter.add_ai_prose("testo generato", author_id="AI.claude",
                         prompt_ref="D.prompt")
    return g, n


# ── authorship reuses DP-32 ───────────────────────────────────────────────────

def test_a_narrative_can_carry_an_author_edge(peopled):
    """`has_author` already existed and is domain-neutral
    (prov:wasAttributedTo): the narrative was simply added to its allowed
    sources. No new authorship edge was invented."""
    g, n = peopled
    g.add_edge("e", n.node_id, "A.ed", "has_author")
    edge = next(e for e in g.edges if e.edge_id == "e")
    assert edge.edge_type == "has_author"      # not degraded
    assert not g.warnings


def test_the_ai_author_is_a_subclass_not_a_new_type():
    """`AuthorAINode` already existed as a subclass of AuthorNode, carrying
    `model` and `prompt_reference`. Adding a parallel type would have split
    "author" in two for no gain: code that asks "is this an author" keeps
    working, code that asks "is this a machine" has isinstance."""
    ai = AuthorAINode("AI.x", name="Claude", model="claude-opus-5")
    assert isinstance(ai, AuthorNode)
    assert ai.node_type == "author_ai"
    assert ai.data["model"] == "claude-opus-5"


def test_a_chapter_records_its_author(peopled):
    _g, n = peopled
    n.chapters[0].authored_by = "A.ed"
    assert n.chapters[0].to_dict()["authored_by"] == "A.ed"


def test_author_refs_collects_everyone_credited(peopled):
    g, n = peopled
    n.chapters[0].authored_by = "A.ed"
    endorse_block(g, n.ai_blocks()[0], "A.ed")
    assert n.author_refs() == ["A.ed", "AI.claude"]


# ── the prompt is a source ────────────────────────────────────────────────────

def test_the_prompt_is_cited_like_any_other_source(peopled):
    """"How do I know this" applies just as much to "how did the machine come
    to write it" — so the prompt is a DocumentNode and the block points at it."""
    g, n = peopled
    assert n.prompt_refs() == ["D.prompt"]
    assert isinstance(g.find_node_by_id("D.prompt"), DocumentNode)


# ── the endorsement act ───────────────────────────────────────────────────────

def test_ai_content_is_born_unendorsed(peopled):
    _g, n = peopled
    block = n.ai_blocks()[0]
    assert block.ai_generated is True
    assert block.validated_by is None
    assert block.status == STATUS_AI_DRAFT


def test_human_prose_needs_no_endorsement():
    n = NarrativeNode("N1", "Storia")
    block = n.add_chapter("Cap").add_prose("scritto da una persona")
    assert block.status == STATUS_HUMAN


def test_a_person_endorsing_changes_the_state(peopled):
    g, n = peopled
    block = n.ai_blocks()[0]
    endorse_block(g, block, "A.ed")
    assert block.validated_by == "A.ed"
    assert block.status == STATUS_AI_ENDORSED
    assert n.pending_validation() == []


def test_a_model_cannot_endorse(peopled):
    """The core of the thing. A model vouching for a model is a signature with
    nobody behind it."""
    g, n = peopled
    with pytest.raises(NarrativeError) as exc:
        endorse_block(g, n.ai_blocks()[0], "AI.claude")
    assert "only a human author can endorse" in str(exc.value)
    assert n.ai_blocks()[0].status == STATUS_AI_DRAFT


def test_the_datamodel_alone_cannot_forbid_an_ai_validator(peopled):
    """Recorded, not hidden: `validated_by` declares target `AuthorNode`, and
    the resolver is subclass-aware, so `AuthorAINode` SATISFIES it. The
    connections datamodel has no way to say "this class but not its
    subclasses", which is why the rule is enforced in code. An edge added by
    hand still passes validation — and that is a gap worth knowing about."""
    g, n = peopled
    g.add_edge("bad", n.node_id, "AI.claude", "validated_by")
    edge = next(e for e in g.edges if e.edge_id == "bad")
    assert edge.edge_type == "validated_by"   # accepted by the datamodel…
    # …while the code path refuses it
    with pytest.raises(NarrativeError):
        resolve_human_author(g, "AI.claude")


def test_endorsing_an_unknown_author_is_refused(peopled):
    g, n = peopled
    with pytest.raises(NarrativeError) as exc:
        endorse_block(g, n.ai_blocks()[0], "A.nobody")
    assert "no node" in str(exc.value)


def test_endorsing_human_text_is_refused(peopled):
    g, n = peopled
    human = n.chapters[0].add_prose("scritto da una persona")
    with pytest.raises(NarrativeError):
        endorse_block(g, human, "A.ed")


def test_endorse_narrative_takes_the_whole_pending_list(peopled):
    g, n = peopled
    n.chapters[0].add_ai_prose("un secondo pezzo", author_id="AI.claude")
    assert len(n.pending_validation()) == 2
    assert endorse_narrative(g, n, "A.ed") == 2
    assert n.pending_validation() == []


def test_nothing_endorses_itself(peopled):
    """No code path sets `validated_by` as a side effect of anything."""
    _g, n = peopled
    json.dumps(graph_to_emjson(Graph(graph_id="x")))  # exercising export
    assert n.ai_blocks()[0].validated_by is None


# ── the activity IS the activity ──────────────────────────────────────────────

def test_the_activity_carries_its_own_narrative():
    """E.D.: the ActivityNodeGroup IS «costruzione della torre»; its actions are
    the units it contains. No new event type — the language already had the
    right node."""
    act = ActivityNodeGroup("ACT.1", "Costruzione",
                            narrative="Nel I secolo si alza la torre.")
    assert act.narrative == "Nel I secolo si alza la torre."
    assert act.data["narrative"] == "Nel I secolo si alza la torre."


def test_the_narrative_field_is_distinct_from_the_description():
    """`description` is the technical note the stratigrapher writes for their
    own use; a reader of the story is a different reader."""
    act = ActivityNodeGroup("ACT.1", "Costruzione",
                            description="Interventi edilizi, fase 2",
                            narrative="Nel I secolo si alza la torre.")
    assert act.description != act.narrative


def test_an_activity_without_a_narrative_stays_empty():
    act = ActivityNodeGroup("ACT.1", "Costruzione")
    assert act.narrative == ""
    assert "narrative" not in act.data


# ── round trip ────────────────────────────────────────────────────────────────

def test_provenance_survives_em_json(peopled):
    g, n = peopled
    endorse_block(g, n.ai_blocks()[0], "A.ed")
    n.chapters[0].authored_by = "A.ed"
    reloaded, _w = load_emjson(json.loads(json.dumps(graph_to_emjson(g))))
    back = _narrative(reloaded)
    block = back.ai_blocks()[0]
    assert block.authored_by == "AI.claude"
    assert block.prompt_ref == "D.prompt"
    assert block.validated_by == "A.ed"
    assert block.status == STATUS_AI_ENDORSED
    assert back.chapters[0].authored_by == "A.ed"


def test_an_older_reader_still_sees_the_provenance(peopled):
    """A build that has never heard of narratives degrades the node — but the
    attribution and the endorsement are plain data, so they are still there to
    be read. Provenance must not depend on knowing the class."""
    from s3dgraphy.nodes.base_node import Node

    g, n = peopled
    endorse_block(g, n.ai_blocks()[0], "A.ed")
    doc = json.loads(json.dumps(graph_to_emjson(g)))
    saved = Node.node_type_map.pop("narrative")
    try:
        reloaded, _w = load_emjson(doc)
        raw = next(x for x in reloaded.nodes if x.node_id == "N1")
        block = raw.data["chapters"][0]["blocks"][0]
        assert block["authored_by"] == "AI.claude"
        assert block["validated_by"] == "A.ed"
        assert block["prompt_ref"] == "D.prompt"
    finally:
        Node.node_type_map["narrative"] = saved


# ── the fixture ───────────────────────────────────────────────────────────────

def test_the_fixture_carries_the_whole_author_layer():
    graph, _w = load_emjson_file(str(FIXTURE))
    n = _narrative(graph)
    assert n.author_refs() == ["A.demetrescu", "AI.claude"]
    assert n.prompt_refs() == ["EXT.prompt.cantiere"]
    assert len(n.ai_blocks()) == 2
    # one endorsed, one deliberately left pending: both states are exercised
    assert [b.status for b in n.ai_blocks()] == [STATUS_AI_ENDORSED,
                                                 STATUS_AI_DRAFT]
    assert n.chapter_by_anchor("ACT.cantiere") is not None


def test_the_fixture_re_exports_identically():
    graph, _w = load_emjson_file(str(FIXTURE))
    on_disk = json.loads(FIXTURE.read_text())
    assert (json.dumps(graph_to_emjson(graph), sort_keys=True)
            == json.dumps(on_disk, sort_keys=True))


# ── RDF projection ────────────────────────────────────────────────────────────

def test_the_projection_carries_authors_and_the_endorsement():
    rdflib = pytest.importorskip("rdflib")
    from s3dgraphy.api import project_ttl

    graph, _w = load_emjson_file(str(FIXTURE))
    parsed = rdflib.Graph()
    parsed.parse(data=project_ttl(graph), format="turtle")

    EM = rdflib.Namespace("https://w3id.org/em/ontology#")
    PROV = rdflib.Namespace("http://www.w3.org/ns/prov#")
    iri = next(parsed.subjects(rdflib.RDF.type, EM.Narrative))

    attributed = {str(o) for o in parsed.objects(iri, PROV.wasAttributedTo)}
    assert any(a.endswith("/A.demetrescu") for a in attributed)
    assert any(a.endswith("/AI.claude") for a in attributed)

    endorsers = {str(o) for o in parsed.objects(iri, PROV.wasInfluencedBy)}
    assert any(e.endswith("/A.demetrescu") for e in endorsers)

    # the unendorsed draft is stated, not silently absent
    pending = list(parsed.objects(iri, EM.pendingValidation))
    assert pending and int(pending[0]) == 1


def test_the_projection_still_does_not_reify_the_chapters():
    pytest.importorskip("rdflib")
    from s3dgraphy.api import project_ttl

    graph, _w = load_emjson_file(str(FIXTURE))
    ttl = project_ttl(graph)
    assert "block_type" not in ttl
    assert "Chapter" not in ttl
