"""BUGFIX-XLSXIMPORTER (2026-08-06) — XLSXImporter.parse() completes.

`base_importer.__init__` left `self.graph` commented out ("initialised by the
child class") and the XLSX importer never did, so `parse()` — which calls
`self.graph.add_node/find_node_by_id` — raised `'XLSXImporter' object has no
attribute 'graph'`. self.graph is now initialised in the base __init__ (accepting
an optional graph, else a fresh one), exactly like import_graphml. And the ID
column's declared node_type is honoured, so a source_list maps ID → DocumentNode.

These cases exercise XLSXImporter.parse() end-to-end, which used to crash.
"""

import openpyxl

from s3dgraphy import api


def _source_list_xlsx(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sources"
    ws.append(["ID", "TITLE"])
    ws.append(["D.01", "Scavo 2020"])
    ws.append(["D.02", "Rilievo 2021"])
    wb.save(str(path))
    return str(path)


def test_xlsx_importer_parse_no_longer_crashes(tmp_path):
    path = _source_list_xlsx(tmp_path / "sources.xlsx")
    # This is the exact call the bridge /import-em-data (mapping) makes. Before
    # the fix it raised ImportError("...no attribute 'graph'").
    graph, warnings = api.xlsx_to_graph(
        path, mapping_name="source_list_mapping", graph_id="Src")
    assert graph is not None
    assert graph.nodes  # rows became nodes


def test_source_list_rows_become_document_nodes(tmp_path):
    path = _source_list_xlsx(tmp_path / "sources.xlsx")
    graph, _ = api.xlsx_to_graph(
        path, mapping_name="source_list_mapping", graph_id="Src")
    docs = [n for n in graph.nodes if n.node_type == "document"]
    assert sorted(n.name for n in docs) == ["D.01", "D.02"]
    # TITLE is carried as a property, wired with has_property
    titles = [n for n in graph.nodes if n.node_type == "property"]
    assert len(titles) == 2
    assert sum(1 for e in graph.edges if e.edge_type == "has_property") == 2
