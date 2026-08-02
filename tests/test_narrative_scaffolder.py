"""N1 — the scaffolder: from a graph to a first draft.

Nobody starts from a blank page. The graph already knows the epochs, their
order, which units belong to each and which sources justify them; a template
reads that and lays out the chapters, so the author begins at "what do I want to
say" rather than "what is in here".

Two properties matter more than the layout itself:

* the template **writes no content** — where prose belongs it leaves a visible
  placeholder, because a sentence invented here would enter the record under the
  author's name;
* **regenerating never destroys writing** — otherwise the button is unusable:
  you would only dare press it once.
"""

import pathlib

import pytest

from s3dgraphy.api import load_emjson_file
from s3dgraphy.graph import Graph
from s3dgraphy.narrative import (build_narrative, get_template, list_templates,
                                 register_template)
from s3dgraphy.narrative.site_story import PLACEHOLDER
from s3dgraphy.nodes.document_node import DocumentNode
from s3dgraphy.nodes.epoch_node import EpochNode
from s3dgraphy.nodes.narrative_node import NarrativeNode
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "PortaMarina-lite.em.json"


@pytest.fixture
def portamarina():
    graph, _warnings = load_emjson_file(str(FIXTURE))
    return graph


def _embeds(chapter, view_type=None):
    return [b for b in chapter.blocks if b.block_type == "embed"
            and (view_type is None or b.view_type == view_type)]


# ── the registry ──────────────────────────────────────────────────────────────

def test_site_story_is_registered():
    assert "site_story" in list_templates()
    assert callable(get_template("site_story"))


def test_an_unknown_template_says_what_there_is():
    with pytest.raises(KeyError) as exc:
        get_template("diario_di_scavo")
    assert "site_story" in str(exc.value)


def test_a_template_is_just_a_registered_function():
    """Adding one must not mean touching the core — that is the whole point of
    the registry."""
    @register_template("_test_minimal")
    def _minimal(graph, **opts):
        n = NarrativeNode("n", "minimal")
        n.add_chapter("Uno")
        return n

    try:
        assert "_test_minimal" in list_templates()
        out = build_narrative(Graph(graph_id="g"), "_test_minimal")
        assert [c.title for c in out.chapters] == ["Uno"]
    finally:
        from s3dgraphy.narrative import registry
        registry._TEMPLATES.pop("_test_minimal", None)


# ── what site_story produces ──────────────────────────────────────────────────

def test_the_shape_is_the_one_the_spec_describes(portamarina):
    n = build_narrative(portamarina, "site_story")
    assert [c.title for c in n.chapters] == [
        "Presentazione", "Dove si trova", "Età imperiale", "Cantiere imperiale"]
    # intro and geo are settled by construction; the lane chapters are drafts
    assert [c.canonical for c in n.chapters] == [True, True, False, False]
    assert n.chapters[2].anchor == "EP.imperiale"     # an epoch lane
    assert n.chapters[3].anchor == "ACT.cantiere"     # an activity lane
    assert n.data["template_id"] == "site_story"


def test_every_source_gets_its_own_embed(portamarina):
    """A table would list the sources; an embed SHOWS each one with its
    criticism — and keeps each individually referenced, so 'which narratives
    rest on this source' stays answerable."""
    n = build_narrative(portamarina, "site_story")
    refs = [b.ref for b in _embeds(n.chapters[0], "source")]
    assert refs == ["D.1", "D.2"]


def test_a_prompt_is_not_listed_among_the_site_sources(portamarina):
    """A prompt is a source OF THE NARRATIVE, not of the reconstruction. Putting
    the machine's instructions next to Maiuri's survey would be a category
    error — and the list would grow with every generation."""
    n = build_narrative(portamarina, "site_story")
    refs = [b.ref for b in _embeds(n.chapters[0], "source")]
    assert "EXT.prompt.cantiere" not in refs


def test_the_units_are_ordered_by_stratigraphy(portamarina):
    """`US.101 is_after US.102` → US.102 is the older, so it is told first: the
    chapter reads in the order the site was built."""
    n = build_narrative(portamarina, "site_story")
    assert [b.ref for b in _embeds(n.chapters[2], "us")] == ["US.102", "US.101"]


def test_the_evidence_sits_beside_the_claim(portamarina):
    """'How I know it' belongs in the story, not in an appendix."""
    n = build_narrative(portamarina, "site_story")
    kinds = [(b.view_type, b.ref) for b in _embeds(n.chapters[2])]
    assert kinds == [("us", "US.102"), ("us", "US.101"),
                     ("paradata", "PR.101.material")]


def test_a_property_with_no_evidence_chain_gets_no_paradata_embed():
    """An embed pointing at nothing to show would be furniture."""
    from s3dgraphy.nodes.property_node import PropertyNode

    g = Graph(graph_id="g")
    g.add_node(EpochNode("EP.1", "Epoca", -100, 100))
    g.add_node(StratigraphicUnit("US.1", "US1"))
    g.add_node(PropertyNode("PR.1", "height", property_type="height", value="3"))
    g.add_edge("e1", "US.1", "EP.1", "has_first_epoch")
    g.add_edge("e2", "US.1", "PR.1", "has_property")   # no provenance chain
    n = build_narrative(g, "site_story")
    chapter = n.chapter_by_anchor("EP.1")
    assert not _embeds(chapter, "paradata")


def test_no_coordinates_no_geo_chapter():
    """Inventing coordinates for a site is the worst kind of plausible."""
    g = Graph(graph_id="g")
    g.add_node(EpochNode("EP.1", "Epoca", -100, 100))
    g.add_node(StratigraphicUnit("US.1", "US1"))
    g.add_edge("e1", "US.1", "EP.1", "has_first_epoch")
    n = build_narrative(g, "site_story")
    assert "Dove si trova" not in [c.title for c in n.chapters]


def test_an_empty_lane_gets_no_chapter():
    g = Graph(graph_id="g")
    g.add_node(EpochNode("EP.vuota", "Epoca vuota", -100, 100))
    n = build_narrative(g, "site_story")
    assert n.chapter_by_anchor("EP.vuota") is None


def test_epochs_are_told_oldest_first():
    g = Graph(graph_id="g")
    for eid, name, start in (("EP.b", "Tarda", 400), ("EP.a", "Antica", -200)):
        g.add_node(EpochNode(eid, name, start, start + 100))
        unit = StratigraphicUnit(f"US.{eid}", f"US {eid}")
        g.add_node(unit)
        g.add_edge(f"e_{eid}", unit.node_id, eid, "has_first_epoch")
    n = build_narrative(g, "site_story")
    assert [c.anchor for c in n.chapters if c.anchor] == ["EP.a", "EP.b"]


def test_all_prose_is_a_visible_placeholder(portamarina):
    """The template lays out structure. Everything it 'writes' must be
    recognisable as not-yet-written, and greppable."""
    n = build_narrative(portamarina, "site_story")
    prose = [b.text for c in n.chapters for b in c.blocks
             if b.block_type == "prose"]
    assert prose
    assert all(t.startswith("[da scrivere:") and t.endswith("]") for t in prose)


# ── regeneration must not destroy work ────────────────────────────────────────

def test_a_canonical_chapter_is_left_exactly_as_it_was(portamarina):
    n = build_narrative(portamarina, "site_story")
    intro = n.chapters[0]
    intro.blocks = [b for b in intro.blocks if b.block_type != "prose"]
    intro.add_prose("Porta Marina è l'accesso occidentale della città.")
    written = [b.to_dict() for b in intro.blocks]

    again = build_narrative(portamarina, "site_story", existing=n)
    assert [b.to_dict() for b in again.chapters[0].blocks] == written


def test_hand_written_prose_in_a_draft_chapter_survives(portamarina):
    """The lane chapters ARE regenerated — but prose is the part a human
    wrote, and regeneration only adds embeds."""
    n = build_narrative(portamarina, "site_story")
    lane = n.chapter_by_anchor("EP.imperiale")
    lane.blocks[0].text = "Nel I secolo la porta viene ricostruita."

    build_narrative(portamarina, "site_story", existing=n)
    lane = n.chapter_by_anchor("EP.imperiale")
    assert lane.blocks[0].text == "Nel I secolo la porta viene ricostruita."


def test_regeneration_is_idempotent(portamarina):
    """Pressing the button twice with an unchanged graph changes nothing."""
    n = build_narrative(portamarina, "site_story")
    before = [c.to_dict() for c in n.chapters]
    build_narrative(portamarina, "site_story", existing=n)
    build_narrative(portamarina, "site_story", existing=n)
    assert [c.to_dict() for c in n.chapters] == before


def test_new_material_in_the_graph_reaches_the_draft(portamarina):
    """The reason to regenerate at all."""
    n = build_narrative(portamarina, "site_story")
    assert [b.ref for b in _embeds(n.chapter_by_anchor("EP.imperiale"), "us")] \
        == ["US.102", "US.101"]

    unit = StratigraphicUnit("US.103", "US103")
    portamarina.add_node(unit)
    portamarina.add_edge("e_new", "US.103", "EP.imperiale", "has_first_epoch")

    build_narrative(portamarina, "site_story", existing=n)
    refs = [b.ref for b in _embeds(n.chapter_by_anchor("EP.imperiale"), "us")]
    assert "US.103" in refs


def test_a_chapter_whose_lane_disappeared_is_kept(portamarina):
    """Deleting an author's chapter because an epoch was renamed would be the
    tool destroying work in response to an edit elsewhere. It just stops being
    regenerated."""
    n = build_narrative(portamarina, "site_story")
    orphan = n.add_chapter("Un'epoca che non c'è più", anchor="EP.sparita")
    orphan.add_prose("Testo scritto a mano.")

    build_narrative(portamarina, "site_story", existing=n)
    kept = n.chapter_by_anchor("EP.sparita")
    assert kept is not None
    assert kept.blocks[0].text == "Testo scritto a mano."


def test_regeneration_does_not_duplicate_the_canonical_chapters(portamarina):
    """The intro and geo chapters have no anchor, so they are matched by title —
    without that they would be appended again on every run."""
    n = build_narrative(portamarina, "site_story")
    build_narrative(portamarina, "site_story", existing=n)
    titles = [c.title for c in n.chapters]
    assert titles.count("Presentazione") == 1
    assert titles.count("Dove si trova") == 1


# ── activities: the actions performed in antiquity ────────────────────────────

def test_each_activity_gets_its_own_anchored_chapter():
    """E.D., 2 Aug 2026: the ActivityNodeGroup IS the activity, and its actions
    are the units it contains. So an activity is a lane like an epoch is, and
    gets a chapter anchored to it — that is what makes the multitemporal reading
    work: epochs say WHEN, activities say WHAT WAS DONE."""
    from s3dgraphy.nodes.group_node import ActivityNodeGroup

    g = Graph(graph_id="g")
    g.add_node(EpochNode("EP.1", "Epoca", -100, 100))
    for uid in ("US.1", "US.2"):
        g.add_node(StratigraphicUnit(uid, uid))
        g.add_edge(f"e_{uid}", uid, "EP.1", "has_first_epoch")
    g.add_edge("seq", "US.1", "US.2", "is_after")
    g.add_node(ActivityNodeGroup("ACT.1", "Costruzione della torre"))
    g.add_edge("m1", "US.1", "ACT.1", "is_in_activity")
    g.add_edge("m2", "US.2", "ACT.1", "is_in_activity")

    n = build_narrative(g, "site_story")
    chapter = n.chapter_by_anchor("ACT.1")
    assert chapter is not None
    assert chapter.title == "Costruzione della torre"
    # the actions, in stratigraphic order — oldest first, as in an epoch chapter
    assert [b.ref for b in _embeds(chapter, "us")] == ["US.2", "US.1"]


def test_an_activity_with_a_narrative_account_uses_it():
    """`ActivityNodeGroup.narrative` is the prose the author wrote about what
    was done. When it exists, the chapter opens with it rather than with a
    placeholder — the template never overwrites writing."""
    from s3dgraphy.nodes.group_node import ActivityNodeGroup

    g = Graph(graph_id="g")
    g.add_node(ActivityNodeGroup("ACT.1", "Costruzione",
                                 narrative="Nel I secolo si alza la torre."))
    n = build_narrative(g, "site_story")
    chapter = n.chapter_by_anchor("ACT.1")
    assert chapter.blocks[0].text == "Nel I secolo si alza la torre."


def test_an_activity_without_an_account_gets_a_placeholder():
    from s3dgraphy.nodes.group_node import ActivityNodeGroup

    g = Graph(graph_id="g")
    g.add_node(ActivityNodeGroup("ACT.1", "Costruzione"))
    n = build_narrative(g, "site_story")
    text = n.chapter_by_anchor("ACT.1").blocks[0].text
    assert text.startswith("[da scrivere:") and "Costruzione" in text


def test_regenerating_preserves_an_edited_activity_chapter():
    """Activity chapters are lanes, so they merge by anchor like epoch ones:
    new actions appear, the prose the author wrote stays."""
    from s3dgraphy.nodes.group_node import ActivityNodeGroup

    g = Graph(graph_id="g")
    g.add_node(ActivityNodeGroup("ACT.1", "Costruzione"))
    g.add_node(StratigraphicUnit("US.1", "US1"))
    g.add_edge("m1", "US.1", "ACT.1", "is_in_activity")
    n = build_narrative(g, "site_story")
    n.chapter_by_anchor("ACT.1").blocks[0].text = "Scritto a mano."

    g.add_node(StratigraphicUnit("US.2", "US2"))
    g.add_edge("m2", "US.2", "ACT.1", "is_in_activity")
    build_narrative(g, "site_story", existing=n)

    chapter = n.chapter_by_anchor("ACT.1")
    assert chapter.blocks[0].text == "Scritto a mano."
    assert {b.ref for b in _embeds(chapter, "us")} == {"US.1", "US.2"}
