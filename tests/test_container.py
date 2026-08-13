"""The em.json CONTAINER — a project is one file holding one or more graphs.

Three claims, in the order they matter:

  C1  READING accepts BOTH shapes. Every em.json written before 2026-08-13 is a
      single-graph document, and none of them may break.
  C2  WRITING is always the container shape — the one Heriverse already reads —
      and a round-trip through it changes nothing.
  C3  INTEGRATING LATER is a local operation: another project's graphs are ADDED
      and shared nodes merge by UUID, with no server and no session.
"""

import json

import pytest

from s3dgraphy import api
from s3dgraphy.container import (
    Container,
    build_container,
    container_of,
    is_container,
    is_shelf_member,
    merge_into_container,
    parse_container,
)
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import StratigraphicUnit
from s3dgraphy.shelf.core import add_to_shelf, list_shelf, new_shelf


def _study(graph_id="studio_a", unit="US101") -> Graph:
    g = Graph(graph_id=graph_id, name=graph_id.replace("_", " ").title())
    g.add_node(StratigraphicUnit(unit, unit))
    return g


def _shelf_with(*paths) -> Graph:
    shelf = new_shelf("shelf", "Shelf di progetto")
    for i, path in enumerate(paths):
        add_to_shelf(shelf, path, name=path.split("/")[-1],
                     resource_id=f"res{i}",
                     checksum="sha256:" + f"{i:02x}" * 32,
                     scope="own-study", residency="resident")
    return shelf


# ── C1 · reading both shapes ────────────────────────────────────────────────

def test_a_legacy_single_graph_opens_as_a_container_of_one():
    """Nothing on anybody's disk breaks. This is the whole compatibility claim."""
    legacy = api.graph_to_emjson(_study())
    assert not is_container(legacy)          # the old shape, as written for months

    container, warnings = parse_container(legacy)
    assert container.graph_ids() == ["studio_a"]
    assert container.is_single()
    assert container.shelf is None
    assert container.active_graph_id == "studio_a"
    assert warnings == []


def test_the_single_graph_reader_still_returns_one_graph_from_a_container():
    """`parse_emjson` keeps its contract: one graph in, one graph out.

    For a container it returns the ACTIVE member — what the author had in front —
    and SAYS that there were others. Silently handing back one graph out of three
    to a caller who does not know there are three is how data goes missing.
    """
    from s3dgraphy.importer.emjson_importer import parse_emjson

    container = Container(graphs={"a": _study("a", "US1"), "b": _study("b", "US2")},
                          active_graph_id="b")
    doc = build_container(container)
    graph, warnings = parse_emjson(doc)
    assert graph.graph_id == "b"
    assert any("container" in w for w in warnings), warnings


def test_a_shelf_only_file_opens_as_the_shelf():
    """`save_shelf` writes exactly this: a container whose only member is the
    shelf. The first version of the reader REFUSED it — the file it refused to
    open was the shelf's own."""
    from s3dgraphy.importer.emjson_importer import parse_emjson

    doc = build_container(Container(shelf=_shelf_with("/dati/a.jpg")))
    graph, _warnings = parse_emjson(doc)
    assert is_shelf_member(graph)


# ── C2 · writing the container ──────────────────────────────────────────────

def test_the_container_shape_is_the_one_heriverse_reads():
    container = Container(graphs={"studio_a": _study()},
                          shelf=_shelf_with("/dati/foto.jpg"),
                          active_graph_id="studio_a")
    doc = build_container(container)
    assert set(doc) >= {"header", "graphs", "active_graph_id"}
    assert set(doc["graphs"]) == {"studio_a", "shelf"}
    # nodes/edges live in the member, which is where Heriverse looks
    assert isinstance(doc["graphs"]["studio_a"]["nodes"], list)
    assert doc["graphs"]["shelf"]["data"]["em_collection"] == "ShelfGraph"


def test_one_graph_writes_as_a_container_of_one():
    doc = build_container(container_of(_study()))
    assert is_container(doc)
    assert list(doc["graphs"]) == ["studio_a"]


def test_a_container_round_trips_unchanged():
    """C2: write → read → write lands on the SAME document."""
    original = Container(
        graphs={"studio_a": _study("studio_a", "US101"),
                "studio_b": _study("studio_b", "US201")},
        shelf=_shelf_with("/dati/a.jpg", "/dati/b.jpg"),
        active_graph_id="studio_b",
    )
    first = build_container(original)
    reread, warnings = parse_container(first)
    assert warnings == []
    assert reread.graph_ids() == ["studio_a", "studio_b"]
    assert reread.active_graph_id == "studio_b"
    assert len(list_shelf(reread.shelf)) == 2
    second = build_container(reread)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_a_legacy_file_survives_the_trip_through_the_container(tmp_path):
    """The migration path, end to end: an old file opens, is saved as a
    container, and reopens with everything it had."""
    from s3dgraphy.exporter.emjson_exporter import export_emjson
    from s3dgraphy.importer.emjson_importer import import_emjson

    original = _study("studio_a", "US101")
    original.add_node(StratigraphicUnit("US102", "US102"))
    original.add_edge("e1", "US101", "US102", "is_before")

    path = export_emjson(original, str(tmp_path / "g.em.json"))
    written = json.loads(open(path, encoding="utf-8").read())
    assert is_container(written)            # the FILE is a container now

    reloaded, warnings = import_emjson(path)
    assert not warnings
    assert {n.node_id for n in reloaded.nodes} >= {"US101", "US102"}
    assert [(e.edge_source, e.edge_type, e.edge_target) for e in reloaded.edges
            if e.edge_type == "is_before"] == [("US101", "is_before", "US102")]


def test_an_unreadable_member_does_not_lose_the_project():
    """One broken member must not cost the other graphs."""
    doc = build_container(container_of(_study()))
    doc["graphs"]["rotto"] = "questo non è un grafo"
    container, warnings = parse_container(doc)
    assert container.graph_ids() == ["studio_a"]
    assert any("rotto" in w for w in warnings), warnings


def test_an_active_id_that_is_not_a_member_falls_back_and_says_so():
    doc = build_container(container_of(_study()))
    doc["active_graph_id"] = "un_grafo_che_non_c_e"
    container, warnings = parse_container(doc)
    assert container.active_graph_id == "studio_a"
    assert any("active_graph_id" in w for w in warnings), warnings


# ── C3 · integrating later ──────────────────────────────────────────────────

def test_integrating_another_project_adds_its_graphs_and_merges_by_uuid():
    """The offline gesture: two people, two files, one project afterwards.

    The shared unit is ONE node — that is what UUID ids were for (ADR-002 said
    so: they guard offline merges) — and the colleague's own sector arrives whole.
    """
    mine = Container(graphs={"porta_marina": _study("porta_marina", "shared-uuid")},
                     active_graph_id="porta_marina")
    mine.graphs["porta_marina"].add_node(StratigraphicUnit("mine-only", "US102"))

    theirs_pm = _study("porta_marina", "shared-uuid")
    theirs_pm.add_node(StratigraphicUnit("theirs-only", "US103"))
    theirs = Container(graphs={"porta_marina": theirs_pm,
                               "settore_nord": _study("settore_nord", "US301")})

    report = merge_into_container(mine, theirs)

    assert sorted(mine.graph_ids()) == ["porta_marina", "settore_nord"]
    assert report.added_graphs == ["settore_nord"]
    assert report.merged_graphs == ["porta_marina"]
    ids = [n.node_id for n in mine.graphs["porta_marina"].nodes]
    assert ids.count("shared-uuid") == 1        # ONE node, not two
    assert {"mine-only", "theirs-only"} <= set(ids)
    # the number a person should look at: where a divergent edit could have been
    # overwritten
    assert report.merged_nodes >= 1


def test_the_project_shelf_merges_by_uuid_too():
    """Two people who collected the same photograph end up with one entry."""
    mine = Container(graphs={"a": _study("a", "US1")},
                     shelf=_shelf_with("/mio/foto.jpg"))
    theirs = Container(graphs={"a": _study("a", "US1")},
                       shelf=_shelf_with("/loro/foto.jpg"))   # same resource id res0

    merge_into_container(mine, theirs)
    entries = list_shelf(mine.shelf)
    assert len(entries) == 1, [e["id"] for e in entries]


def test_a_project_with_no_shelf_takes_the_other_ones():
    mine = Container(graphs={"a": _study("a", "US1")})
    theirs = Container(graphs={"a": _study("a", "US1")},
                       shelf=_shelf_with("/loro/foto.jpg"))
    report = merge_into_container(mine, theirs)
    assert mine.shelf is not None
    assert report.shelf_added >= 1


def test_merging_does_not_duplicate_an_edge_that_is_already_there():
    """The same relation authored twice is one relation — the triple is the
    identity, because two people mint edge ids independently."""
    mine = Container(graphs={"a": _study("a", "US1")})
    mine.graphs["a"].add_node(StratigraphicUnit("US2", "US2"))
    mine.graphs["a"].add_edge("mine-edge-id", "US1", "US2", "is_before")

    theirs = Container(graphs={"a": _study("a", "US1")})
    theirs.graphs["a"].add_node(StratigraphicUnit("US2", "US2"))
    theirs.graphs["a"].add_edge("their-edge-id", "US1", "US2", "is_before")

    merge_into_container(mine, theirs)
    same = [e for e in mine.graphs["a"].edges
            if (e.edge_source, e.edge_type, e.edge_target) == ("US1", "is_before", "US2")]
    assert len(same) == 1


# ── the manager, and the file ───────────────────────────────────────────────

def test_the_manager_opens_and_saves_a_whole_project(tmp_path):
    from s3dgraphy.multigraph.multigraph import MultiGraphManager

    container = Container(
        graphs={"studio_a": _study("studio_a", "US101"),
                "studio_b": _study("studio_b", "US201")},
        shelf=_shelf_with("/dati/foto.jpg"),
        active_graph_id="studio_a",
    )
    path = api.save_container_file(container, str(tmp_path / "progetto.em.json"))

    manager = MultiGraphManager()
    loaded, warnings = manager.load_container(path, replace=True)
    assert warnings == []
    assert sorted(loaded.graph_ids()) == ["studio_a", "studio_b"]
    assert loaded.shelf is not None
    # the shelf is IN the manager too (it is a member), and recognised as such
    assert "shelf" in manager.get_all_graph_ids()

    again = manager.save_container(str(tmp_path / "di_nuovo.em.json"))
    reread, _ = api.load_container_file(again)
    assert sorted(reread.graph_ids()) == ["studio_a", "studio_b"]
    assert reread.shelf is not None          # still a shelf, not a third study graph


def test_load_container_is_additive_by_default(tmp_path):
    """Opening a second project ADDS: losing what is already open is the more
    expensive mistake."""
    from s3dgraphy.multigraph.multigraph import MultiGraphManager

    first = api.save_container_file(container_of(_study("uno", "US1")),
                                    str(tmp_path / "uno.em.json"))
    second = api.save_container_file(container_of(_study("due", "US2")),
                                     str(tmp_path / "due.em.json"))
    manager = MultiGraphManager()
    manager.load_container(first, replace=True)
    manager.load_container(second)
    assert sorted(manager.get_all_graph_ids()) == ["due", "uno"]
