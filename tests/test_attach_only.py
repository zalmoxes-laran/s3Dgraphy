"""Attaching a table to a graph that is already right — and saying what missed.

There are two ways a legacy table becomes a graph, and until now only one of them
was reachable from `mapping_apply`.

* **the table brings the stratigraphy.** Relations in the columns, the graph born
  out of the dataset. One shot. This is what `apply_mapping` did, always;
* **the graph brings the stratigraphy and the table brings the rest.** Far more
  common: no relation columns anywhere, the sequence drawn by hand, and a
  spreadsheet that goes on being edited in QGIS or Excel and re-read. Here the
  graph is AUTHORITATIVE and the table may only enrich it.

In the second mode a row whose key is not in the graph used to **create a unit**,
in silence. Measured before this change: a host graph of 620 nodes, a csv with
one typo (`su = 99999`) → **624 nodes, `99999` in the graph, no warning**. A
mistyped cell invented an excavated unit.

So this file measures three things, and the third is the one that keeps the fix
honest:

1. with `enrich_only=False` — the old behaviour, **unchanged**: the unknown key
   creates its node, because that is what "the table brings the stratigraphy"
   means;
2. with `enrich_only=True` — no node is created, and the units that DID match are
   enriched, which is the whole point of attaching;
3. the skipped keys come back in the report as `unmatched`. Skipping in silence
   would only move the damage: from "a typo invents a unit" to "a typo loses a
   row", and the second is harder to see. The list is what lets a person tell a
   typo in the key column from a unit still to be drawn.
"""

from __future__ import annotations

import csv
import os
import tempfile

import pytest

from s3dgraphy import api
from s3dgraphy.graph import Graph

US = "A2 Stratigraphic Volume Unit"

#: The host: three units, with the covering between them. The stratigraphy.
HOST_ROWS = [
    ["us", "descrizione", "copre"],
    ["1", "Strato di crollo", "2"],
    ["2", "Piano pavimentale", "3"],
    ["3", "Muro perimetrale", ""],
]

#: The table attached afterwards: NO relation column at all, one property, and a
#: key that is not in the host — `99999`, the typo. The shape of every "case b"
#: descriptor: a join key and what it carries.
AUX_ROWS = [
    ["su", "interpretazione"],
    ["1", "Crollo del tetto"],
    ["2", "Pavimento della bottega"],
    ["99999", "Rifiuto: un refuso nella colonna chiave"],
]


def write_csv(path: str, rows) -> str:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle, delimiter=";").writerows(rows)
    return path


def host_mapping() -> dict:
    return {
        "name": "host",
        "source_settings": {"format_type": "csv"},
        "column_mappings": {
            "us": {"cidoc": US, "is_id": True},
            "descrizione": {"is_description": True, "target_id_column": "us"},
            "copre": {"cidoc": US, "is_relation": True},
        },
        "relations": [{"source_column": "us", "target_column": "copre",
                       "edge_type": "overlies"}],
    }


def aux_mapping() -> dict:
    """A "case b" descriptor: an id (the join key) and a property. No
    `relations`, no relation column — and that is NOT a degenerate mapping:
    `mapping_validate` accepts it, because the only thing a mapping is required
    to declare is its `is_id`."""
    return {
        "name": "aux",
        "source_settings": {"format_type": "csv"},
        "column_mappings": {
            "su": {"cidoc": US, "is_id": True},
            "interpretazione": {"property_name": "Interpretation"},
        },
    }


def host() -> Graph:
    with tempfile.TemporaryDirectory() as tmp:
        graph = Graph(graph_id="scavo")
        report = api.mapping_apply(host_mapping(),
                                   write_csv(os.path.join(tmp, "host.csv"),
                                             HOST_ROWS),
                                   graph=graph, mode="bake")
        assert report["ok"] is True, report["errors"]
    return graph


def names(graph: Graph, node_type: str = "US") -> set:
    return {n.name for n in graph.nodes if n.node_type == node_type}


def properties_of(graph: Graph, unit: str) -> dict:
    """The property nodes hanging off `unit`, as `{name: value}` — what
    "enriched" means, read from the graph rather than from a count."""
    node = next(n for n in graph.nodes if n.name == unit and n.node_type == "US")
    out = {}
    for edge in graph.edges:
        if edge.edge_source != node.node_id:
            continue
        target = graph.find_node_by_id(edge.edge_target)
        if target is not None and target.node_type == "property":
            out[target.name] = getattr(target, "description", "") or \
                getattr(target, "value", "")
    return out


# ── 1 · the default is untouched ────────────────────────────────────────────

def test_without_the_flag_an_unknown_key_still_creates_its_node():
    """The compatibility measure, and it is not a formality: this is the mode
    every mapping on disk runs in today. A table that brings the stratigraphy
    MUST go on creating what it names."""
    graph = host()
    with tempfile.TemporaryDirectory() as tmp:
        report = api.mapping_apply(aux_mapping(),
                                   write_csv(os.path.join(tmp, "aux.csv"),
                                             AUX_ROWS),
                                   graph=graph, mode="bake")
    assert report["ok"] is True, report["errors"]
    assert "99999" in names(graph), "the old behaviour, deliberately kept"
    assert report["unmatched"] == [], "nothing was skipped: nothing missed"
    assert report["unmatched_count"] == 0


# ── 2 · attached, the graph wins ────────────────────────────────────────────

def test_with_the_flag_the_typo_creates_nothing_and_is_reported():
    """The fix, in one assertion each way: the unit is NOT invented, and the key
    that invented it comes back by name."""
    graph = host()
    before = {n.node_id for n in graph.nodes}
    with tempfile.TemporaryDirectory() as tmp:
        report = api.mapping_apply(aux_mapping(),
                                   write_csv(os.path.join(tmp, "aux.csv"),
                                             AUX_ROWS),
                                   graph=graph, mode="bake", enrich_only=True)
    assert report["ok"] is True, report["errors"]
    assert "99999" not in names(graph), \
        "a typo in the key column must not excavate a unit"
    assert report["unmatched"] == ["99999"], \
        "…and must not vanish either — this list is the whole difference " \
        "between 'skipped' and 'lost'"
    assert report["unmatched_count"] == 1
    # the units that DID match are enriched — otherwise the mode would be a very
    # safe way of doing nothing.
    #
    # The property is named after the COLUMN (`_process_properties` reads
    # `display_name`, falling back to the column name, and does not look at
    # `property_name`). Asserted as measured rather than as expected: that
    # mismatch is real and predates this round, and a test written against the
    # name one would wish for would hide it.
    assert properties_of(graph, "1").get("interpretazione") == "Crollo del tetto"
    assert properties_of(graph, "2").get("interpretazione") == \
        "Pavimento della bottega"
    added = [n for n in graph.nodes if n.node_id not in before]
    assert {n.node_type for n in added} == {"property"}, \
        "only the paradata is new; no stratigraphic unit was added"
    assert report["nodes_added"] == len(added)


def test_a_mapping_with_no_relations_is_a_valid_mapping():
    """Stated because the whole second mode depends on it: a descriptor that
    declares no relation at all is not half a mapping. The schema asks for an
    `is_id` — the join key — and nothing else."""
    verdict = api.mapping_validate(aux_mapping())
    assert verdict["ok"] is True, verdict["errors"]
    assert "relations" not in aux_mapping()


# ── 3 · the same, through the table importers ───────────────────────────────

def test_the_table_importers_honour_it_too():
    """`enrich_only` is passed to all four importers or to none: the inline ones
    (csv, xml) take it in their constructor, the table ones (xlsx, sqlite) get
    `_use_existing_graph` set after construction. Measured on xlsx, because the
    line that used to force `False` there is the line this round changed."""
    pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    import json

    import pandas as pd

    from s3dgraphy.mappings import mapping_registry

    graph = host()
    with tempfile.TemporaryDirectory() as tmp:
        mapping = aux_mapping()
        mapping["source_settings"] = {"format_type": "xlsx", "sheet_name": 0}
        with open(os.path.join(tmp, "aux_mapping.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(mapping, handle)
        mapping_registry.add_mapping_directory("generic", tmp)
        path = os.path.join(tmp, "aux.xlsx")
        pd.DataFrame(AUX_ROWS[1:], columns=AUX_ROWS[0]).to_excel(path,
                                                                 index=False)
        report = api.mapping_apply(mapping, path, graph=graph, mode="bake",
                                   mapping_name="aux_mapping",
                                   enrich_only=True)
    assert report["ok"] is True, report["errors"]
    assert "99999" not in names(graph)
    assert report["unmatched"] == ["99999"]
