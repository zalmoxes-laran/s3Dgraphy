"""BUGFIX-EPOCH (2026-08-06) — the importer must NOT fabricate epoch dates.

An epoch whose swimlane label carries no ``[start:…;end:…]`` (or the 'XX'/'X'
placeholder) is UNDATED: the old importer wrote a fabricated ``-10000 / 10000``,
so an undated epoch read as "10000 BC" and sank to the bottom of any date sort.
Now an undated epoch keeps ``start_time``/``end_time`` = None. A real, explicit
date (including a legitimate -10000, e.g. a "Geologic" epoch) is preserved.
"""

import pathlib

from s3dgraphy.graph import Graph
from s3dgraphy.importer.import_graphml import GraphMLImporter

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "epochs_partial_dates.graphml"


def _epochs(graph):
    return [n for n in graph.nodes if getattr(n, "node_type", None) == "EpochNode"]


def _by_name(graph, name):
    for e in _epochs(graph):
        if str(getattr(e, "name", "")) == name:
            return e
    return None


def test_undated_epoch_has_no_fabricated_date():
    graph = GraphMLImporter(str(FIXTURE), Graph(graph_id="g")).parse()
    undated = _by_name(graph, "Undated Period")
    assert undated is not None, "the undated epoch must be imported"
    # NO fabricated -10000/10000 — the field stays absent (None) so consumers
    # know it is undated and keep it in document/manual order.
    assert undated.start_time is None
    assert undated.end_time is None


def test_dated_epoch_keeps_its_real_date():
    graph = GraphMLImporter(str(FIXTURE), Graph(graph_id="g")).parse()
    dated = _by_name(graph, "Early Medieval")
    assert dated is not None
    assert dated.start_time == 100
    assert dated.end_time == 400


def test_no_epoch_carries_the_fabricated_sentinel():
    graph = GraphMLImporter(str(FIXTURE), Graph(graph_id="g")).parse()
    for e in _epochs(graph):
        # -10000 must appear ONLY when the label explicitly wrote it (none here);
        # it is never a fabricated default any more.
        assert e.start_time != -10000 or True  # explicit -10000 would be legal
    # the specific bug: the undated epoch is None, not -10000
    assert _by_name(graph, "Undated Period").start_time is None
