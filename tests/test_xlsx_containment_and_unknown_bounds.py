"""SM4 — what the table importer used to lose from StratiMiner v6.0-split.

Three rows of an ``em_data.xlsx`` that the importer handled wrongly and in
silence:

* a ``Claims`` row ``is_part_of`` (a hearth inside a layer) fell through to the
  qualia branch and became a PropertyNode with an empty VALUE — the containment
  vanished without a warning;
* an ``Epochs`` row with empty START/END became «year 0 – year 0»: a date the
  source never gave, which the chronology resolver then propagated to every unit
  of the lane (it skips None, but takes min/max over numbers);
* a ``nomenclature`` claim (the unit's code as a claim: whose code it is) must
  arrive as a PropertyNode with its attribution chain, like any other quale.

The workbook is written with openpyxl so the fixture reads in the diff.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from s3dgraphy import api  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.epoch_node import EpochNode  # noqa: E402
from s3dgraphy.nodes.property_node import PropertyNode  # noqa: E402


_HEADERS = {
    "Units": ("ID", "TYPE", "NAME"),
    "Epochs": ("ID", "NAME", "START", "END", "COLOR"),
    "Claims": ("TARGET_ID", "PROPERTY_TYPE", "VALUE", "TARGET2_ID",
               "UNITS", "EXTRACTOR_1", "DOCUMENT_1", "AUTHOR_1"),
    "Authors": ("ID", "KIND", "DISPLAY_NAME", "ORCID", "AFFILIATION"),
    "Documents": ("ID", "FILENAME", "TITLE", "YEAR", "AUTHOR_IDS",
                  "ROLE", "CONTENT_NATURE", "GEOMETRY"),
}

_FIXTURE = {
    "Units": [
        ("US1", "US", "Layer"),
        ("US2", "US", "Hearth"),
    ],
    "Epochs": [
        # Dated epoch, as control.
        ("E1", "Roman", -50, 100, "#aa5500"),
        # The source gives no bounds: they must stay unknown.
        ("E0", "Pre-Roman", None, None, "#556677"),
    ],
    "Claims": [
        ("US1", "has_first_epoch", "E0", "", "", "", "", ""),
        ("US2", "has_first_epoch", "E0", "", "", "", "", ""),
        # The hearth is inside the layer: child → container.
        ("US2", "is_part_of", "", "US1", "", "", "", ""),
        ("US1", "nomenclature", "US 1", "", "",
         "Unit code as given in the report", "D.01", "A.01"),
    ],
    "Authors": [
        ("A.01", "author", "Jane Roe", "", "ISPC-CNR"),
    ],
    "Documents": [
        ("D.01", "report.pdf", "Excavation Report", "2024", "A.01",
         "analytical", "2d_object", "observable"),
    ],
}


def _write_workbook(path):
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    for name, header in _HEADERS.items():
        ws = wb.create_sheet(name)
        ws.append(header)
        for row in _FIXTURE.get(name, []):
            ws.append(row)
    wb.save(str(path))
    return str(path)


@pytest.fixture
def imported(tmp_path):
    path = _write_workbook(tmp_path / "em_data.xlsx")
    graph, warnings, _stats = api.em_data_to_graph(path, graph_id="sm4")
    return graph, warnings, path


def _unit(graph, name):
    return next(n for n in graph.nodes if n.name == name
                and n.node_type not in ("EpochNode", "property"))


def _epoch(graph, name):
    return next(n for n in graph.nodes
                if isinstance(n, EpochNode) and n.name == name)


# ── containment ───────────────────────────────────────────────────────────────

def test_is_part_of_becomes_a_containment_edge_child_to_container(imported):
    graph, _w, _p = imported
    layer, hearth = _unit(graph, "US1"), _unit(graph, "US2")
    containment = [e for e in graph.edges
                   if e.edge_type == Graph.CONTAINMENT_EDGE]
    assert [(e.edge_source, e.edge_target) for e in containment] == [
        (hearth.node_id, layer.node_id)]
    # Same reading the GraphML importer's nesting gives.
    assert [n.node_id for n in graph.get_contained_nodes(layer.node_id)] == [
        hearth.node_id]
    assert graph.is_container(layer.node_id)


def test_is_part_of_is_not_swallowed_as_an_empty_quale(imported):
    graph, _w, _p = imported
    assert not [n for n in graph.nodes if isinstance(n, PropertyNode)
                and n.property_type == "is_part_of"]


def test_is_part_of_is_not_an_order_relation():
    from s3dgraphy import diagnostics
    for family in (Graph._SOURCE_IS_MORE_RECENT,
                   Graph._TARGET_IS_MORE_RECENT,
                   diagnostics._SOURCE_IS_MORE_RECENT,
                   diagnostics._TARGET_IS_MORE_RECENT):
        assert Graph.CONTAINMENT_EDGE not in family


def test_is_part_of_survives_the_table_round_trip(imported, tmp_path):
    graph, _w, _p = imported
    from s3dgraphy.exporter.unified_xlsx_exporter import UnifiedXLSXExporter
    out = tmp_path / "again.xlsx"
    UnifiedXLSXExporter(graph).write(str(out))
    again, _w2, _s2 = api.em_data_to_graph(str(out), graph_id="sm4")
    assert [e for e in again.edges if e.edge_type == "is_part_of"]


# ── unknown epoch bounds ──────────────────────────────────────────────────────

def test_epoch_without_bounds_stays_unknown(imported):
    graph, _w, _p = imported
    pre = _epoch(graph, "Pre-Roman")
    assert pre.start_time is None and pre.end_time is None
    roman = _epoch(graph, "Roman")
    assert (roman.start_time, roman.end_time) == (-50, 100)


def test_no_year_zero_reaches_the_units(imported):
    """0 was not only a wrong label: the resolver takes it as a real date."""
    graph, _w, _p = imported
    graph.calculate_chronology()
    for name in ("US1", "US2"):
        attrs = _unit(graph, name).attributes
        assert attrs.get("CALCUL_START_T") is None
        assert attrs.get("CALCUL_END_T") is None


def test_unknown_bounds_survive_em_json_save_and_load(imported):
    """The em.json exporter omits a None bound; reading it back must not
    refill it with 0."""
    _graph, _w, path = imported
    doc = api.import_em_data(path, graph_id="sm4")
    pre = next(n for n in doc["graph"]["nodes"] if n.get("name") == "Pre-Roman")
    assert "start_time" not in (pre.get("data") or {})
    assert "end_time" not in (pre.get("data") or {})

    from s3dgraphy.importer.emjson_importer import parse_emjson
    # Through a real JSON text, as a file on disk would be.
    reloaded, _warnings = parse_emjson(json.loads(json.dumps(doc)))
    back = _epoch(reloaded, "Pre-Roman")
    assert back.start_time is None and back.end_time is None
    assert (_epoch(reloaded, "Roman").start_time,
            _epoch(reloaded, "Roman").end_time) == (-50, 100)


# ── nomenclature as a claim ───────────────────────────────────────────────────

def test_nomenclature_is_a_property_with_its_attribution_chain(imported):
    graph, _w, _p = imported
    layer = _unit(graph, "US1")
    props = [n for n in graph.nodes if isinstance(n, PropertyNode)
             and n.property_type == "nomenclature"]
    assert len(props) == 1
    pn = props[0]
    assert pn.value == "US 1"
    assert any(e.edge_type == "has_property" and e.edge_source == layer.node_id
               and e.edge_target == pn.node_id for e in graph.edges)

    def out(node_id, edge_type):
        return [graph.find_node_by_id(e.edge_target) for e in graph.edges
                if e.edge_source == node_id and e.edge_type == edge_type]

    [extractor] = out(pn.node_id, "has_data_provenance")
    assert extractor.node_type == "extractor"
    [document] = out(extractor.node_id, "extracted_from")
    assert document.node_type == "document"
    assert [a.node_type for a in out(extractor.node_id, "has_author")] == [
        "author"]
