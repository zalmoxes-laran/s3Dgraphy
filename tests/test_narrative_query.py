"""DP-79 P4 — the four questions the narrative layer makes answerable.

Authoring a study on the graph buys one thing: the interpretation and the
evidence are the same data, so questions that cross them have answers. These
tests are that claim, measured.

Two fixtures, and the second is the point: a study where a source has been
**retracted** and a reconstruction has never been written about. A query surface
that only works on a tidy graph answers nothing anybody needs.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from s3dgraphy import api                                       # noqa: E402
from s3dgraphy.graph import Graph                               # noqa: E402
from s3dgraphy.nodes import StratigraphicUnit                   # noqa: E402
from s3dgraphy.nodes.document_node import DocumentNode          # noqa: E402
from s3dgraphy.nodes.epoch_node import EpochNode                # noqa: E402
from s3dgraphy.nodes.group_node import ActivityNodeGroup        # noqa: E402
from s3dgraphy.nodes.narrative_node import NarrativeNode        # noqa: E402
from s3dgraphy.nodes.representation_node import (               # noqa: E402
    RepresentationModelNode)


def _narrative(node_id, name, chapters):
    """Built through `from_payload` — the node's own reader of the serialised
    shape, which is the shape a document holds. Assembling it block by block
    would test the builder; this tests what a loaded study looks like."""
    return NarrativeNode.from_payload(node_id, name, data={"chapters": chapters})


def _study():
    """Two epochs, three units, an activity, a source, a narrative — and the
    two problems a reviewer looks for."""
    graph = Graph(graph_id="portico")

    early = EpochNode(node_id="ep-1", name="Fase 1", start_time=1200, end_time=1450)
    late = EpochNode(node_id="ep-2", name="Fase 2", start_time=1450, end_time=1520)
    silent = EpochNode(node_id="ep-3", name="Fase 3", start_time=1520, end_time=1600)
    for epoch in (early, late, silent):
        graph.add_node(epoch)

    for uid, label, epoch in (("us1", "US 1", early), ("us2", "US 2", early),
                              ("us3", "US 3", silent)):
        graph.add_node(StratigraphicUnit(uid, name=label))
        graph.add_edge(f"{uid}_ep", uid, epoch.node_id, "has_first_epoch")

    activity = ActivityNodeGroup(node_id="act-1", name="Cantiere")
    graph.add_node(activity)
    for uid in ("us1", "us2"):
        graph.add_edge(f"{uid}_act", uid, "act-1", "is_in_activity")

    # a source that has since been withdrawn, and one that has not
    graph.add_node(DocumentNode("doc-ok", name="Rossi 1987"))
    withdrawn = DocumentNode("doc-bad", name="Bianchi 1972")
    withdrawn.data = dict(getattr(withdrawn, "data", None) or {})
    withdrawn.data["retracted"] = True
    graph.add_node(withdrawn)

    # a reconstruction with a scene that nobody has written about
    model = RepresentationModelNode("rm-1", name="Colonnato restituito")
    # the scene lives in `data`, which is where the node keeps what it points at
    model.data = dict(getattr(model, "data", None) or {})
    model.data["url"] = "https://scenes.example/colonnato.gltf"
    graph.add_node(model)
    graph.add_edge("rm_of", "rm-1", "us3", "is_representation_model_of")

    graph.add_node(_narrative("narr-1", "Il portico", [
        {"title": "Le fasi", "blocks": [
            {"block_type": "prose", "text": "Il muro."},
            {"block_type": "embed", "ref": "us1", "view_type": "us"},
            {"block_type": "embed", "ref": "doc-ok", "view_type": "source"},
            {"block_type": "embed", "ref": "doc-bad", "view_type": "source"},
        ]},
        {"title": "Il restauro", "blocks": [
            {"block_type": "embed", "ref": "ep-2", "view_type": "matrix"},
            {"block_type": "embed", "ref": "us1", "view_type": "paradata"},
            {"block_type": "embed", "ref": "ghost", "view_type": "us"},
        ]},
    ]))
    return graph


@pytest.fixture()
def study():
    return _study()


# ── the spine ────────────────────────────────────────────────────────────────

def test_citations_are_flattened_with_their_position(study):
    rows = api.narrative_citations(study)
    assert len(rows) == 6, "one row per embed, prose excluded"
    first = rows[0]
    assert (first["chapter"], first["block"], first["ref"]) == (0, 1, "us1")
    assert first["chapter_title"] == "Le fasi"
    assert first["narrative_name"] == "Il portico"


# ── 1 · which narratives cite this unit, IN ORDER ───────────────────────────

def test_where_a_unit_is_cited_in_reading_order(study):
    """The ordered answer the RDF projection cannot give: chapters are
    deliberately not reified there."""
    hits = api.narratives_citing(study, "us1")
    assert [(h["chapter"], h["block"], h["view_type"]) for h in hits] == [
        (0, 1, "us"), (1, 1, "paradata")]
    assert all(h["narrative_id"] == "narr-1" for h in hits)
    assert api.narratives_citing(study, "us2") == [], \
        "a unit nobody cited has no citations — not an error"


def test_the_ordering_is_the_authors_and_not_the_dicts(study):
    """Sorted by (narrative, chapter, block), so the sequence is the one that
    was written rather than the one the loader happened to produce."""
    rows = api.narratives_citing(study, "us1")
    assert rows == sorted(rows, key=lambda r: (r["narrative_id"], r["chapter"],
                                               r["block"]))


# ── 2 · citations that no longer stand ──────────────────────────────────────

def test_a_retracted_source_and_a_missing_one_are_both_reported_and_told_apart(
        study):
    """Two failures, two kinds of work: one sentence has to be reread, the other
    cannot even say what it leaned on."""
    broken = api.narratives_on_retracted_sources(study)
    by_ref = {b["ref"]: b for b in broken}
    assert set(by_ref) == {"doc-bad", "ghost"}
    assert by_ref["doc-bad"]["reason"] == "retracted"
    assert by_ref["doc-bad"]["source_name"] == "Bianchi 1972"
    assert by_ref["ghost"]["reason"] == "missing"
    # and it says WHERE, so somebody can go and fix the sentence
    assert (by_ref["doc-bad"]["chapter"], by_ref["doc-bad"]["block"]) == (0, 3)


def test_a_healthy_citation_is_not_reported(study):
    refs = {b["ref"] for b in api.narratives_on_retracted_sources(study)}
    assert "doc-ok" not in refs


def test_retraction_is_read_off_the_source_itself(study):
    """No separate register: a source is retracted in the study that holds it."""
    from s3dgraphy.narrative.query import is_retracted
    index = {n.node_id: n for n in study.nodes}
    assert is_retracted(index["doc-bad"]) is True
    assert is_retracted(index["doc-ok"]) is False


# ── 3 · interpretive coverage ───────────────────────────────────────────────

def test_coverage_counts_a_member_citation_as_covering_its_epoch(study):
    """An author who wrote about a unit HAS written about its phase. A query
    that only counted direct citations would report the phase as untouched."""
    rows = {r["name"]: r for r in api.interpretive_coverage(study)}
    assert rows["Fase 1"]["narratives"] == 1
    assert rows["Fase 1"]["direct_citations"] == 0, "reached through us1"
    assert rows["Fase 2"]["narratives"] == 1
    assert rows["Fase 2"]["direct_citations"] == 1, "cited by the matrix embed"


def test_the_row_people_are_looking_for_is_the_zero(study):
    """`narratives: 0` is the question — what has nobody explained yet."""
    rows = api.interpretive_coverage(study)
    assert rows[0]["narratives"] == 0, "the uncovered come first"
    assert rows[0]["name"] == "Fase 3"
    assert [r["name"] for r in rows if not r["narratives"]] == ["Fase 3"]


def test_coverage_answers_for_activities_too(study):
    rows = api.interpretive_coverage(study, kind="activity")
    assert [(r["name"], r["narratives"], r["members"]) for r in rows] == [
        ("Cantiere", 1, 2)]
    with pytest.raises(ValueError):
        api.interpretive_coverage(study, kind="nonsense")


# ── 4 · a model nobody explained ────────────────────────────────────────────

def test_a_reconstruction_with_a_scene_and_no_text_is_listed(study):
    rows = api.unexplained_reconstructions(study)
    assert [r["id"] for r in rows] == ["rm-1"]
    assert rows[0]["represents"] == ["us3"]


def test_writing_about_the_unit_explains_its_model(study):
    """A reconstruction is explained when the unit it stands for is — an author
    does not have to name the file."""
    narrative = next(n for n in study.nodes if n.node_type == "narrative")
    chapter = narrative.add_chapter("La fase 3")
    chapter.add_embed("us3", "us")
    assert api.unexplained_reconstructions(study) == []


# ── all four, deterministically ─────────────────────────────────────────────

def test_the_report_is_deterministic_and_complete(study):
    first = api.narrative_report(study)
    second = api.narrative_report(_study())
    assert first == second, "same graph, same answer"
    assert first["citations"] == 6
    assert first["uncovered_epochs"] == ["Fase 3"]
    assert len(first["broken_citations"]) == 2
    assert [r["id"] for r in first["unexplained_reconstructions"]] == ["rm-1"]


def test_a_graph_with_no_narrative_answers_empty_rather_than_failing():
    """An ordinary graph is not an error. Every query has to survive one."""
    graph = Graph(graph_id="quiet")
    graph.add_node(StratigraphicUnit("us1", name="US 1"))
    assert api.narrative_citations(graph) == []
    assert api.narratives_citing(graph, "us1") == []
    assert api.narratives_on_retracted_sources(graph) == []
    assert api.unexplained_reconstructions(graph) == []
    report = api.narrative_report(graph)
    assert report["narratives"] == [] and report["citations"] == 0
