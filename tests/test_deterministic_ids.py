"""E2 — deterministic ids for GraphML elements without an EMID.

An element that carries an ``EMID`` keeps it: that is the authored identity.
Everything else used to receive a fresh ``uuid4()`` on every import, so the
SAME file produced DIFFERENT ids run after run. The re-import was therefore not
reproducible, and any ``layout.positions`` entry (or external reference) minted
against a previous run went orphan — in F2 the fixture ids had to be re-paired
by hand to make the test suite deterministic at all.

The importer now mints a ``uuid5`` over a key built from the file's own
content. These tests pin the two properties that matter:

1. **reproducibility** — importing the same GraphML twice yields exactly the
   same node ids, edge ids and graph id (and hence a byte-identical em.json);
2. **retro-compatibility** — an element WITH an EMID still gets that EMID.

Prerequisite of Se5 (the ``graphml → em.json`` command): a conversion that
returns different ids on every run cannot be used as a persistent identity.
"""

import io
import json
import pathlib

import contextlib

import pytest

from s3dgraphy.api import graphml_to_emjson
from s3dgraphy.graph import Graph
from s3dgraphy.importer.import_graphml import (DETERMINISTIC_ID_NAMESPACE,
                                               GraphMLImporter)

FIXTURES = pathlib.Path(__file__).parent / "sync" / "fixtures"

# Fixtures spanning the branches that mint ids: plain nodes, groups, the
# swimlane and its epoch rows, edges, and a legacy file.
GRAPHML_FIXTURES = [
    "em_demo_02_mini.graphml",
    "groups_volterra.graphml",
    "legacy_5_5_x.graphml",
    "mini_volterra_baseline_ai03.graphml",
    "mini_volterra_external.graphml",
    "mini_volterra_external_with_new_epoch.graphml",
    "paradata_volterra.graphml",
]


def _import(path):
    """Import ``path`` and return (node ids, edge ids, graph id).

    The importer is chatty on stdout; swallow it so the test output stays
    readable.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        graph = GraphMLImporter(str(path), Graph(graph_id="imported")).parse()
    return (sorted(n.node_id for n in graph.nodes),
            sorted(e.edge_id for e in graph.edges),
            graph.graph_id)


@pytest.mark.parametrize("name", GRAPHML_FIXTURES)
def test_import_twice_yields_identical_ids(name):
    """Same GraphML → same ids. This is the whole point of E2."""
    path = FIXTURES / name
    first = _import(path)
    second = _import(path)

    assert first[0] == second[0], f"{name}: node ids differ between imports"
    assert first[1] == second[1], f"{name}: edge ids differ between imports"
    assert first[2] == second[2], f"{name}: graph id differs between imports"


@pytest.mark.parametrize("name", GRAPHML_FIXTURES)
def test_ids_are_unique_within_one_import(name):
    """Determinism must not be bought with collisions: homonyms at the same
    coordinates are separated by their order of appearance."""
    node_ids, edge_ids, _ = _import(FIXTURES / name)
    assert len(node_ids) == len(set(node_ids)), f"{name}: duplicate node ids"
    assert len(edge_ids) == len(set(edge_ids)), f"{name}: duplicate edge ids"


def test_emjson_is_byte_identical_across_imports():
    """The Se5 contract: graphml → em.json is a pure function of the file."""
    text = (FIXTURES / "mini_volterra_external.graphml").read_text()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        first = graphml_to_emjson(text)
        second = graphml_to_emjson(text)
    assert (json.dumps(first, sort_keys=True)
            == json.dumps(second, sort_keys=True))


def test_no_orphan_positions():
    """Every ``layout.positions`` key must name a node that exists."""
    text = (FIXTURES / "mini_volterra_external.graphml").read_text()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        doc = graphml_to_emjson(text)
    node_ids = {n["id"] for n in doc["graph"]["nodes"]}
    positions = (doc.get("layout") or {}).get("positions") or {}
    orphans = [k for k in positions if k not in node_ids]
    assert not orphans, f"orphan position entries: {orphans[:5]}"


def test_emid_still_wins():
    """Retro-compatibility: a node WITH an EMID keeps it, untouched.

    Checked against ``id_mapping`` (original yEd id → final node id) rather
    than against the node set, so a node the importer deliberately skips
    (yellow comment/note box) simply does not appear and cannot mask a
    regression.
    """
    path = FIXTURES / "mini_volterra_external.graphml"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        importer = GraphMLImporter(str(path), Graph(graph_id="imported"))
        importer.parse()

    checked = 0
    for element in importer.graphml_tree.getroot().iter(
            "{http://graphml.graphdrawing.org/xmlns}node"):
        emid = importer.extract_custom_fields(element, "node").get("EMID")
        original_id = element.attrib.get("id")
        if not emid or original_id not in importer.id_mapping:
            continue
        assert importer.id_mapping[original_id] == emid, (
            f"node {original_id} carried EMID {emid} but was given "
            f"{importer.id_mapping[original_id]}")
        checked += 1

    assert checked, "fixture has no EMID — it cannot prove retro-compatibility"


def test_deterministic_id_is_stable_and_disambiguates():
    """Unit-level contract of the minting helper itself."""
    importer = GraphMLImporter(filepath="<none>", graph=Graph(graph_id="g"))
    a = importer._deterministic_id("node", "USV138_PD", "10.00", "20.00")
    b = importer._deterministic_id("node", "USV138_PD", "10.00", "20.00")
    # Second occurrence of the SAME key → different id, by document order.
    assert a != b
    # …but a fresh importer replays the same sequence exactly.
    other = GraphMLImporter(filepath="<none>", graph=Graph(graph_id="g"))
    assert other._deterministic_id("node", "USV138_PD", "10.00", "20.00") == a
    assert other._deterministic_id("node", "USV138_PD", "10.00", "20.00") == b
    # Different coordinates → different id without needing the counter.
    fresh = GraphMLImporter(filepath="<none>", graph=Graph(graph_id="g"))
    assert (fresh._deterministic_id("node", "USV138_PD", "99.00", "20.00")
            != a)


def test_namespace_is_frozen():
    """Changing the namespace would re-mint every id ever imported."""
    assert str(DETERMINISTIC_ID_NAMESPACE) == (
        "c6735a81-b2e2-5fbc-b972-a8a3f71d7a84")
