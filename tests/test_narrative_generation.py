"""N5 (s3Dgraphy side) — the briefing, and the write-back.

s3Dgraphy stays **pure**: it builds what a model needs to know, and it files
what a model wrote. The call in between happens in em-bridge, behind a provider
interface. That split is what makes both halves testable exactly — there is no
network anywhere in this file, and there is none in the code it tests.

Two properties carry the weight:

* the briefing is a **briefing, not a dump** — what is not in it cannot leak;
* a written draft is **attributed and unendorsed** — generating is not vouching,
  and no code path here ever sets `validated_by`.
"""

import json
import pathlib

import pytest

from s3dgraphy.api import (build_narrative_generation_context, graph_to_emjson,
                           load_emjson, load_emjson_file, write_ai_draft)
from s3dgraphy.graph import Graph
from s3dgraphy.narrative.generation import (GENERATION_CONSTRAINTS,
                                            ensure_ai_author,
                                            register_prompt_extractor,
                                            register_prompt_source)
from s3dgraphy.nodes.author_node import AuthorAINode, AuthorNode
from s3dgraphy.nodes.document_node import DocumentNode
from s3dgraphy.nodes.epoch_node import EpochNode
from s3dgraphy.nodes.extractor_node import ExtractorNode
from s3dgraphy.nodes.group_node import ActivityNodeGroup
from s3dgraphy.nodes.narrative_node import (STATUS_AI_DRAFT, NarrativeError,
                                            NarrativeNode)
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "PortaMarina-lite.em.json"


@pytest.fixture
def portamarina():
    graph, _w = load_emjson_file(str(FIXTURE))
    return graph


def _narrative(graph):
    return next(n for n in graph.nodes if n.node_type == "narrative")


# ── the briefing ──────────────────────────────────────────────────────────────

def test_the_context_is_json_serialisable(portamarina):
    """It crosses a process boundary to em-bridge, so it must be plain data."""
    ctx = build_narrative_generation_context(portamarina, "ACT.cantiere")
    assert json.loads(json.dumps(ctx)) == ctx


def test_it_describes_the_activity_and_its_actions(portamarina):
    ctx = build_narrative_generation_context(portamarina, "ACT.cantiere")
    assert ctx["activity"]["id"] == "ACT.cantiere"
    assert ctx["activity"]["name"] == "Cantiere imperiale"
    # in stratigraphic order — the order in which it happened
    assert [a["name"] for a in ctx["actions"]] == ["US102", "US101"]


def test_the_actions_carry_their_evidence(portamarina):
    """A model told "the wall is in opera incerta" can only repeat it; one told
    where that reading comes from can write a sentence an archaeologist can
    check."""
    ctx = build_narrative_generation_context(portamarina, "ACT.cantiere")
    us101 = next(a for a in ctx["actions"] if a["name"] == "US101")
    (item,) = us101["evidence"]
    assert item["property"]["name"] == "material"
    assert item["value"] == "opera incerta"
    (prov,) = item["provenance"]
    assert prov["sources"][0]["id"] == "D.1"


def test_a_property_with_no_chain_is_not_offered_as_evidence():
    """An unjustified property proves nothing, and offering it would invite the
    model to lean on it."""
    from s3dgraphy.nodes.property_node import PropertyNode

    g = Graph(graph_id="g")
    g.add_node(ActivityNodeGroup("ACT.1", "Costruzione"))
    g.add_node(StratigraphicUnit("US.1", "US1"))
    g.add_node(PropertyNode("PR.1", "height", property_type="height", value="3"))
    g.add_edge("m", "US.1", "ACT.1", "is_in_activity")
    g.add_edge("p", "US.1", "PR.1", "has_property")
    ctx = build_narrative_generation_context(g, "ACT.1")
    assert ctx["actions"][0]["evidence"] == []


def test_the_epochs_come_oldest_first(portamarina):
    ctx = build_narrative_generation_context(portamarina, "ACT.cantiere")
    assert [e["name"] for e in ctx["epochs"]] == ["Età imperiale"]


def test_the_sources_are_deduplicated(portamarina):
    ctx = build_narrative_generation_context(portamarina, "ACT.cantiere")
    ids = [s["id"] for s in ctx["sources"]]
    assert ids == list(dict.fromkeys(ids))


def test_the_style_contract_travels_with_the_briefing(portamarina):
    """The rules that keep a generated paragraph admissible are part of what is
    sent, not something a caller can forget."""
    ctx = build_narrative_generation_context(portamarina, "ACT.cantiere")
    assert ctx["constraints"] == GENERATION_CONSTRAINTS
    assert any("Do not add" in c for c in ctx["constraints"])


def test_the_briefing_holds_only_the_named_activity(portamarina):
    """What is not in it cannot leak. The narrative's other chapters, the other
    epochs' units, the graph's file path: none of it is here."""
    ctx = build_narrative_generation_context(portamarina, "ACT.cantiere")
    blob = json.dumps(ctx)
    assert "Dove si trova" not in blob        # another chapter
    assert "geo_portamarina" not in blob      # a node outside the activity
    assert "PortaMarina-lite.em.json" not in blob


def test_a_target_that_is_not_an_activity_is_refused(portamarina):
    """Better than handing a model an empty briefing and letting it improvise."""
    with pytest.raises(NarrativeError) as exc:
        build_narrative_generation_context(portamarina, "EP.imperiale")
    assert "not an ActivityNodeGroup" in str(exc.value)


def test_chapter_ref_is_accepted_as_an_alias(portamarina):
    """An activity chapter is anchored to the activity, so a caller holding the
    anchor can pass it straight through."""
    a = build_narrative_generation_context(portamarina, "ACT.cantiere")
    b = build_narrative_generation_context(portamarina,
                                           chapter_ref="ACT.cantiere")
    assert a == b


# ── the write-back ────────────────────────────────────────────────────────────

def test_a_draft_is_attributed_and_unendorsed(portamarina):
    """The whole point: generating is not vouching."""
    out = write_ai_draft(portamarina, "ACT.cantiere", "Prosa generata.",
                         model="claude-opus-5", prompt="Racconta il cantiere.")
    assert out["status"] == STATUS_AI_DRAFT
    n = _narrative(portamarina)
    block = n.chapters[-1].blocks[-1]
    assert block.text == "Prosa generata."
    assert block.ai_generated is True
    assert block.validated_by is None
    assert block.authored_by == out["author_id"]


def test_the_prompt_is_filed_as_an_extractor(portamarina):
    """N7 — a prompt is an OPERATION, not a document you consult. Filing it as
    an Extractor puts it in the chain EM already has, so an AI paragraph is
    justified the same way a reading off a survey is."""
    out = write_ai_draft(portamarina, "ACT.cantiere", "Prosa.",
                         model="claude-opus-5", prompt="Racconta il cantiere.")
    ext = portamarina.find_node_by_id(out["prompt_id"])
    assert isinstance(ext, ExtractorNode)
    assert not isinstance(ext, DocumentNode)
    # the prompt TEXT is kept, not just the fact that there was one
    assert ext.description == "Racconta il cantiere."


def test_the_prompt_extractor_is_wired_to_the_sources_it_read(portamarina):
    """An extractor with no `extracted_from` is an operation with nothing to
    operate on — the inertness that made the DocumentNode wrong."""
    out = write_ai_draft(portamarina, "ACT.cantiere", "Prosa.",
                         model="m", prompt="Racconta.")
    read = {e.edge_target for e in portamarina.edges
            if e.edge_source == out["prompt_id"]
            and e.edge_type == "extracted_from"}
    assert read == {"D.1"}            # the source behind US101's evidence
    for doc_id in read:
        assert isinstance(portamarina.find_node_by_id(doc_id), DocumentNode)


def test_the_prompt_extractor_never_invents_a_source():
    """Ids that are not documents are skipped, not fabricated."""
    g = Graph(graph_id="g")
    g.add_node(StratigraphicUnit("US.1", "US1"))
    ext = register_prompt_extractor(g, "Racconta.", sources=["US.1", "nope"])
    assert not [e for e in g.edges if e.edge_source == ext.node_id]


def test_a_prompt_that_is_not_about_an_activity_is_still_filed():
    """Graceful degradation: no briefing to derive sources from is a reason to
    file the prompt bare, not a reason to lose it."""
    g = Graph(graph_id="g")
    g.add_node(EpochNode("EP.1", "Età", start_time=0, end_time=1))
    n = NarrativeNode("N1", "Storia")
    g.add_node(n)
    out = write_ai_draft(g, "EP.1", "Prosa.", model="m", prompt="Racconta.")
    assert isinstance(g.find_node_by_id(out["prompt_id"]), ExtractorNode)


def test_the_extractor_records_what_it_was_applied_to(portamarina):
    """`source` is what the RDF exporter projects as
    crminf:J7_is_based_on_evidence_from."""
    out = write_ai_draft(portamarina, "ACT.cantiere", "Prosa.",
                         model="m", prompt="Racconta.")
    assert portamarina.find_node_by_id(out["prompt_id"]).source == "ACT.cantiere"


def test_the_ai_author_is_created_once_and_reused(portamarina):
    """A fresh author per generation would scatter the same agent across the
    graph and make "what did this model write" unanswerable."""
    first = write_ai_draft(portamarina, "ACT.cantiere", "Uno.",
                           model="claude-opus-5", prompt="p")
    second = write_ai_draft(portamarina, "ACT.cantiere", "Due.",
                            model="claude-opus-5", prompt="p")
    assert first["author_id"] == second["author_id"]
    authors = [n for n in portamarina.nodes if isinstance(n, AuthorAINode)]
    assert len(authors) == 1


def test_the_draft_lands_in_the_chapter_anchored_to_the_activity(portamarina):
    write_ai_draft(portamarina, "ACT.cantiere", "Prosa.",
                   model="m", prompt="p")
    n = _narrative(portamarina)
    chapter = n.chapter_by_anchor("ACT.cantiere")
    assert chapter.blocks[-1].text == "Prosa."


def test_a_missing_chapter_is_created():
    g = Graph(graph_id="g")
    g.add_node(ActivityNodeGroup("ACT.1", "Costruzione"))
    n = NarrativeNode("N1", "Storia")
    g.add_node(n)
    write_ai_draft(g, "ACT.1", "Prosa.", model="m", prompt="p")
    chapter = n.chapter_by_anchor("ACT.1")
    assert chapter is not None and chapter.title == "Costruzione"


def test_the_narrative_gets_an_author_edge(portamarina):
    """So "what did this model write" is answerable from the edges, not only by
    walking the chapters."""
    out = write_ai_draft(portamarina, "ACT.cantiere", "Prosa.",
                         model="claude-opus-5", prompt="p")
    assert any(e.edge_type == "has_author"
               and e.edge_target == out["author_id"]
               for e in portamarina.edges)


def test_empty_text_is_refused(portamarina):
    with pytest.raises(NarrativeError):
        write_ai_draft(portamarina, "ACT.cantiere", "   ", model="m", prompt="p")


def test_a_draft_must_name_its_model():
    g = Graph(graph_id="g")
    g.add_node(ActivityNodeGroup("ACT.1", "A"))
    g.add_node(NarrativeNode("N1", "S"))
    with pytest.raises(NarrativeError):
        write_ai_draft(g, "ACT.1", "Prosa.", model="", prompt="p")


def test_an_ambiguous_graph_asks_which_narrative():
    g = Graph(graph_id="g")
    g.add_node(ActivityNodeGroup("ACT.1", "A"))
    g.add_node(NarrativeNode("N1", "Una"))
    g.add_node(NarrativeNode("N2", "Due"))
    with pytest.raises(NarrativeError) as exc:
        write_ai_draft(g, "ACT.1", "Prosa.", model="m", prompt="p")
    assert "pass narrative_id" in str(exc.value)


def test_a_graph_with_no_narrative_says_what_to_do():
    g = Graph(graph_id="g")
    g.add_node(ActivityNodeGroup("ACT.1", "A"))
    with pytest.raises(NarrativeError) as exc:
        write_ai_draft(g, "ACT.1", "Prosa.", model="m", prompt="p")
    assert "site_story" in str(exc.value)


def test_nothing_in_the_write_back_endorses_anything(portamarina):
    """Stated as a test because it is the invariant the paper rests on."""
    write_ai_draft(portamarina, "ACT.cantiere", "Prosa.", model="m", prompt="p")
    n = _narrative(portamarina)
    assert all(b.validated_by is None for b in n.ai_blocks()
               if b.text == "Prosa.")


def test_the_result_survives_em_json(portamarina):
    write_ai_draft(portamarina, "ACT.cantiere", "Prosa generata.",
                   model="claude-opus-5", version="2026-08", prompt="Racconta.")
    reloaded, _w = load_emjson(json.loads(json.dumps(
        graph_to_emjson(portamarina))))
    n = _narrative(reloaded)
    block = n.chapter_by_anchor("ACT.cantiere").blocks[-1]
    assert block.ai_generated and block.prompt_ref
    assert block.options["model_version"] == "2026-08"


# ── the helpers, on their own ─────────────────────────────────────────────────

def test_ensure_ai_author_refuses_to_shadow_a_human():
    g = Graph(graph_id="g")
    g.add_node(AuthorNode("AI.x", name="una persona"))
    with pytest.raises(NarrativeError):
        ensure_ai_author(g, model="x")


def test_a_prompt_must_not_be_empty():
    with pytest.raises(NarrativeError):
        register_prompt_source(Graph(graph_id="g"), "   ")


def test_the_same_prompt_is_registered_once():
    g = Graph(graph_id="g")
    a = register_prompt_extractor(g, "Racconta il cantiere.")
    b = register_prompt_extractor(g, "Racconta il cantiere.")
    assert a.node_id == b.node_id
    assert len([n for n in g.nodes if isinstance(n, ExtractorNode)]) == 1


def test_the_old_name_still_works_and_now_returns_an_extractor():
    """A caller written against N5 keeps working — and gets the better model."""
    g = Graph(graph_id="g")
    assert isinstance(register_prompt_source(g, "Racconta."), ExtractorNode)


def test_the_prompt_id_is_the_same_in_every_process():
    """`hash()` is randomised per process: using it would fork one prompt into
    a new source node after every restart of the bridge."""
    import subprocess
    import sys

    code = ("import sys; sys.path.insert(0, 'src');"
            "from s3dgraphy.graph import Graph;"
            "from s3dgraphy.narrative.generation import register_prompt_extractor;"
            "print(register_prompt_extractor(Graph(graph_id='g'), 'Racconta.').node_id)")
    runs = {subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, cwd=str(pathlib.Path(__file__).parent.parent)
                           ).stdout.strip() for _ in range(3)}
    assert len(runs) == 1, f"prompt id is not stable across processes: {runs}"


# ── purity ────────────────────────────────────────────────────────────────────

def test_s3dgraphy_imports_no_network_client():
    """The invariant: no LLM SDK, no HTTP client, anywhere in this package's
    narrative layer. The model call belongs to em-bridge."""
    import s3dgraphy.narrative.generation as gen

    source = pathlib.Path(gen.__file__).read_text()
    for forbidden in ("import requests", "import httpx", "urllib.request",
                      "anthropic", "openai"):
        assert forbidden not in source, f"{forbidden} must not appear here"


# ── the RDF projection of the AI chain (N7) ───────────────────────────────────

def test_the_ai_provenance_chain_projects_as_crminf(portamarina):
    """The reason to model a prompt as an Extractor rather than a Document.

    An extractor already projects as a CRMinf belief adoption: the exporter
    emits `J7_is_based_on_evidence_from` and the I2 belief skeleton. So the
    machine's contribution comes out as *a belief adopted from stated evidence*,
    which is what it is — where a DocumentNode came out as a thing somebody
    consulted, which it never was.
    """
    pytest.importorskip("rdflib")
    import rdflib

    from s3dgraphy.api import project_ttl

    out = write_ai_draft(portamarina, "ACT.cantiere", "Prosa.",
                         model="m", prompt="Racconta.")
    # the namespace from the exporter itself, not retyped here: a test that
    # hardcodes a URI passes or fails on the typo, not on the projection
    from s3dgraphy.exporter.rdf_exporter import CRMINF

    parsed = rdflib.Graph().parse(data=project_ttl(portamarina), format="turtle")

    iri = next(s for s in parsed.subjects()
               if str(s).endswith("/" + out["prompt_id"]))
    # applied to the activity…
    assert str(next(parsed.objects(iri, CRMINF.J7_is_based_on_evidence_from))) \
        == "ACT.cantiere"
    # …and it concluded something, like any argumentation node
    belief = next(parsed.objects(iri, CRMINF.J2_concluded_that))
    assert (belief, rdflib.RDF.type, CRMINF.I2_Belief) in parsed


def test_the_prompt_is_no_longer_projected_as_a_document(portamarina):
    pytest.importorskip("rdflib")
    import rdflib

    from s3dgraphy.api import project_ttl

    out = write_ai_draft(portamarina, "ACT.cantiere", "Prosa.",
                         model="m", prompt="Racconta.")
    from s3dgraphy.exporter.rdf_exporter import CRM

    parsed = rdflib.Graph().parse(data=project_ttl(portamarina), format="turtle")
    iri = next(s for s in parsed.subjects()
               if str(s).endswith("/" + out["prompt_id"]))
    types = set(parsed.objects(iri, rdflib.RDF.type))
    assert CRM.E31_Document not in types
