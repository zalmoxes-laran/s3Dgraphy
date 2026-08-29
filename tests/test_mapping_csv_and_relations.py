"""Second round: the csv row-producer, and `is_relation` in the TABLES.

Three limits from the first round, and the tests are shaped around what each one
could still get wrong:

* **the csv becomes a fourth place the rules live.** It must not: a csv importer
  turns a delimited file into ROWS and `base_importer` does the rest, exactly as
  the XML one does. The way to check that is not to read the code — it is to map
  the SAME data as a csv and as an xlsx and demand the same graph;
* **`is_relation` changes what existing mappings produce.** It must not. It is
  opt-in, and nothing on disk declares it — so the test is a mapping WITHOUT the
  flag, whose output must be identical to what it was, and then the same mapping
  WITH it;
* **"edge-only" quietly means "gone".** Skipping the property is half the job: if
  the edge is not created either, the flag becomes a way to lose a column. So the
  flag-on case checks the node count went DOWN by one and the edge is THERE.
"""

from __future__ import annotations

import csv
import os
import tempfile

import pytest

from s3dgraphy import api
from s3dgraphy.graph import Graph

ROWS = [
    ["us", "descrizione", "interpretazione", "copre"],
    ["1", "Strato di crollo con tegole", "Crollo del tetto", "2"],
    ["2", "Piano pavimentale in cocciopesto", "Pavimento della bottega", ""],
    ["3", "Muro in opera reticolata", "Muro perimetrale", ""],
]


def mapping(*, fmt: str, is_relation: bool, edge: str = "P120_occurs_before"):
    """The same mapping in two formats and two flag states — one function, so a
    difference in the result cannot come from a difference in the mapping."""
    settings = {"format_type": fmt}
    if fmt == "xlsx":
        settings["sheet_name"] = 0
    copre = {"cidoc": "A2 Stratigraphic Volume Unit"}
    if is_relation:
        copre["is_relation"] = True
    return {
        "name": f"round2-{fmt}",
        "source_settings": settings,
        "column_mappings": {
            "us": {"cidoc": "A2 Stratigraphic Volume Unit", "is_id": True},
            "descrizione": {"is_description": True, "target_id_column": "us"},
            "interpretazione": {"property_name": "Interpretation"},
            "copre": copre,
        },
        "relations": [{"source_column": "us", "target_column": "copre",
                       "cidoc": edge}],
    }


def write_csv(path: str, delimiter: str = ";", bom: bool = False) -> str:
    encoding = "utf-8-sig" if bom else "utf-8"
    with open(path, "w", newline="", encoding=encoding) as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        for row in ROWS:
            writer.writerow(row)
    return path


def write_xlsx(path: str) -> str:
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    frame = pd.DataFrame(ROWS[1:], columns=ROWS[0])
    frame.to_excel(path, index=False)
    return path


def shape(graph) -> dict:
    """What a graph IS, in the terms these tests compare: how many of each node
    type, and which edges between which names. Ids are uuids and would make two
    identical imports look different."""
    names = {n.node_id: n.name for n in graph.nodes}
    return {
        "types": sorted(f"{n.node_type}:{n.name}" for n in graph.nodes
                        if n.node_type != "geo_position"),
        "edges": sorted(f"{names.get(e.edge_source)}-{e.edge_type}->"
                        f"{names.get(e.edge_target)}" for e in graph.edges),
    }


# ── C1 · the csv is a row producer, not a second set of rules ───────────────

def test_a_csv_and_an_xlsx_of_the_same_data_make_the_same_graph():
    """The parity that proves the csv importer added no rules of its own: two
    formats, one mapping shape, one graph."""
    with tempfile.TemporaryDirectory() as tmp:
        csv_graph = Graph(graph_id="scavo")
        api.mapping_apply(mapping(fmt="csv", is_relation=True),
                          write_csv(os.path.join(tmp, "us.csv")),
                          graph=csv_graph, mode="bake")
        # the xlsx path loads its mapping BY NAME from the registry — which is
        # the real flow ("save it, then apply"), so the test files it the way the
        # editor's Save does instead of skipping the measure
        import json

        from s3dgraphy.mappings import mapping_registry

        xlsx_mapping = mapping(fmt="xlsx", is_relation=True)
        with open(os.path.join(tmp, "round2xlsx_mapping.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(xlsx_mapping, handle)
        mapping_registry.add_mapping_directory("generic", tmp)

        xlsx_graph = Graph(graph_id="scavo")
        report = api.mapping_apply(xlsx_mapping,
                                   write_xlsx(os.path.join(tmp, "us.xlsx")),
                                   graph=xlsx_graph, mode="bake",
                                   mapping_name="round2xlsx_mapping")
        assert report["ok"] is True, report["errors"]
        assert shape(csv_graph) == shape(xlsx_graph)
        assert report["rows"] == 3


def test_the_csv_sniffs_its_delimiter_and_eats_the_bom():
    """Two facts about the FORMAT and nothing else. A comma-only reader turns an
    Italian export into one column; a BOM left in place makes the first column
    `\\ufeffus`, which matches no mapping and reads as a wrong mapping."""
    from s3dgraphy.importer.csv_importer import CSVImporter

    with tempfile.TemporaryDirectory() as tmp:
        for delimiter in (";", ",", "\t", "|"):
            path = write_csv(os.path.join(tmp, "x.csv"), delimiter=delimiter)
            importer = CSVImporter(path, mapping=mapping(fmt="csv",
                                                         is_relation=True))
            records = importer.records()
            assert importer.delimiter == delimiter or len(records[0]) == 4
            assert list(records[0]) == ROWS[0], f"delimiter {delimiter!r}"
        withbom = write_csv(os.path.join(tmp, "bom.csv"), bom=True)
        first = CSVImporter(withbom,
                            mapping=mapping(fmt="csv", is_relation=True)
                            ).records()[0]
        assert list(first)[0] == "us", "the BOM is not part of the column name"


def test_the_csv_needs_a_mapping_and_says_so():
    from s3dgraphy.importer.csv_importer import CSVImporter

    with pytest.raises(ValueError) as caught:
        CSVImporter("whatever.csv")
    assert "mapping" in str(caught.value)


def test_csv_is_no_longer_refused_by_apply():
    """It used to answer «csv apply is not implemented» — a declared limit that
    this round closes."""
    with tempfile.TemporaryDirectory() as tmp:
        report = api.mapping_apply(mapping(fmt="csv", is_relation=True),
                                   write_csv(os.path.join(tmp, "us.csv")))
        assert report["ok"] is True
        assert report["rows"] == 3
        assert report["nodes_added"] == 6            # 3 US + 3 property
        assert report["edges_added"] == 4            # 3 has_property + 1 is_after


def test_a_csv_mapping_is_not_asked_for_a_sheet_name():
    """A csv is one table in one file: warning about the name of it was a warning
    nobody could act on."""
    verdict = api.mapping_validate(mapping(fmt="csv", is_relation=True))
    assert verdict["ok"] is True
    assert not any("table/sheet" in w for w in verdict["warnings"]), \
        verdict["warnings"]


# ── C2 · is_relation in the tables: opt-in, and it means EDGE-ONLY ──────────

def apply_csv(is_relation: bool, edge: str = "P120_occurs_before"):
    with tempfile.TemporaryDirectory() as tmp:
        graph = Graph(graph_id="scavo")
        report = api.mapping_apply(mapping(fmt="csv", is_relation=is_relation,
                                           edge=edge),
                                   write_csv(os.path.join(tmp, "us.csv")),
                                   graph=graph, mode="bake")
        return graph, report


def test_without_the_flag_nothing_changes():
    """THE compatibility test. No mapping on disk declares `is_relation`, so the
    default path has to produce what it has always produced: the relation column
    ALSO becomes a property (that is the surprise the validator warns about, not
    a behaviour this round removes)."""
    graph, report = apply_csv(is_relation=False)
    properties = sorted(n.name for n in graph.nodes if n.node_type == "property")
    assert properties.count("copre") == 1, properties
    assert report["nodes_added"] == 7               # 3 US + 3 interp + 1 copre
    # …and the edge is NOT created for a non-stratigraphic type without the flag
    assert not any(e.edge_type == "is_after" for e in graph.edges)


def test_with_the_flag_the_column_is_edge_only():
    """One node fewer, and the edge is THERE. Skipping the property alone would
    have made the flag a way to lose a column."""
    graph, report = apply_csv(is_relation=True)
    properties = sorted(n.name for n in graph.nodes if n.node_type == "property")
    assert "copre" not in properties, properties
    assert report["nodes_added"] == 6               # one fewer than above
    names = {n.node_id: n.name for n in graph.nodes}
    edges = [(names.get(e.edge_source), e.edge_type, names.get(e.edge_target))
             for e in graph.edges]
    assert ("1", "is_after", "2") in edges, edges


def test_the_ten_stratigraphic_edges_still_work_without_any_flag():
    """The path that existed before this round: an `overlies` target column has
    always been edge-only, flag or no flag."""
    graph, _report = apply_csv(is_relation=False, edge="")
    # …with no CIDOC to resolve, name the edge outright
    with tempfile.TemporaryDirectory() as tmp:
        m = mapping(fmt="csv", is_relation=False)
        m["relations"] = [{"source_column": "us", "target_column": "copre",
                           "edge_type": "overlies"}]
        graph = Graph(graph_id="scavo")
        api.mapping_apply(m, write_csv(os.path.join(tmp, "us.csv")),
                          graph=graph, mode="bake")
    properties = sorted(n.name for n in graph.nodes if n.node_type == "property")
    assert "copre" not in properties, "an overlies target was never a property"
    assert any(e.edge_type == "overlies" for e in graph.edges)


def test_the_skip_list_lives_in_one_place():
    """It used to be a literal set written twice in `base_importer` and mirrored
    a third time in `authoring`. Three copies of a rule are three rules."""
    from s3dgraphy.importer.base_importer import STRATIGRAPHIC_EDGE_TYPES
    from s3dgraphy.mappings.authoring import _importer_skips_property

    assert _importer_skips_property() == frozenset(STRATIGRAPHIC_EDGE_TYPES)
    assert len(STRATIGRAPHIC_EDGE_TYPES) == 10
    source = open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "src", "s3dgraphy", "importer", "base_importer.py"),
        encoding="utf-8").read()
    assert source.count("'overlies'") + source.count('"overlies"') == 1, \
        "the set is written once"


# ── C3 · the CIDOC catalogue, grouped BY ONTOLOGY, from the datamodel ───────

def test_the_catalogue_groups_by_the_ontology_the_datamodel_names():
    """A curated subset of CIDOC by construction: what the datamodel declares and
    not one class more. The counts are the datamodel's own, so this test moves
    when E.D. refines the mapping — which is the point, and why it asserts the
    SHAPE plus a few real members rather than a frozen total."""
    groups = {g["ontology"]: g for g in api.mapping_target_groups()}
    assert "CIDOC-CRM" in groups and "CRMarchaeo" in groups
    assert sum(g["count"] for g in groups.values()) \
        == len(api.mapping_target_catalog())
    # the trunk comes first — a picker whose groups move is a picker you re-read
    assert api.mapping_target_groups()[0]["ontology"] == "CIDOC-CRM"
    crmarchaeo = {t["cidoc"] for t in groups["CRMarchaeo"]["targets"]}
    assert "A2 Stratigraphic Volume Unit" in crmarchaeo
    assert "A8 Stratigraphic Unit" in crmarchaeo
    crm = {t["cidoc"] for t in groups["CIDOC-CRM"]["targets"]}
    assert "E31 Document" in crm and "E21 Person" in crm
    assert "HC" not in "".join(crm), "an HDT-O class is not in the CRM trunk"


def test_every_group_carries_the_version_the_datamodel_declares():
    versions = api.mapping_ontologies()
    for group in api.mapping_target_groups():
        if group["ontology"] in versions:
            assert group["version"] == versions[group["ontology"]]["version"], \
                group["ontology"]
    assert versions["CIDOC-CRM"]["version"] == "7.1.3"
    assert versions["HDT-O"]["version"] == "1.0"


def test_the_edges_group_with_the_datamodels_real_counts():
    """These numbers ARE the datamodel's: 32 CIDOC-CRM · 8 CRMarchaeo ·
    4 CRMdig · 6 HDT-O · 2 PROV-O, plus the 2 mapped only through an extension
    property (`heritage_part_of`, `includes_study`).

    Grew by two on 2026-08-29 with the georeferencing edges of the photogrammetry
    connector: `has_registration_transform` (CIDOC-CRM P67i) and `has_gcp_set`
    (CRMdig L21). Updating this number is the point of the test — a datamodel
    that grows without anybody noticing is how a consumer starts reading an edge
    nobody documented."""
    groups = {g["ontology"]: g["count"] for g in api.mapping_edge_groups()}
    assert groups == {"CIDOC-CRM": 32, "CRMarchaeo": 8, "CRMdig": 4,
                      "HDT-O": 6, "PROV-O": 2, "unmapped": 2}, groups
    filtered = {g["ontology"]: [e["edge_type"] for e in g["edges"]]
                for g in api.mapping_edge_groups("US", "US")}
    assert "is_after" in filtered["CIDOC-CRM"]
    assert "cuts" in filtered["CRMarchaeo"]


def test_a_node_class_gets_its_ontology_from_the_identifier_and_says_so():
    """The node datamodel does not (yet) declare `cidoc_extension` on its
    entries, so theirs is read off the identifier — `A8` is CRMarchaeo,
    `crmdig:D12` is CRMdig. Marked `extension_inferred`, so the day an entry
    declares one, that wins and this stops being used."""
    index = api.mapping_cidoc_index()
    a8 = index["classes"]["A8 Stratigraphic Unit"][0]
    assert a8["extension"] == "CRMarchaeo"
    assert a8["extension_inferred"] is True
    dig = index["classes"]["crmdig:D12_Data_Transfer_Event"][0]
    assert dig["extension"] == "CRMdig"
    # …while an EDGE declares it, so nothing is inferred there
    edge = index["properties"]["P120_occurs_before"][0]
    assert edge["extension"] == "CIDOC-CRM"


def test_no_owl_file_is_ever_opened():
    """The decision, asserted: the catalogue is fed by the DATAMODEL, not by the
    ontologies on disk. No OWL parsing, no dependency on a checkout."""
    source = open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "src", "s3dgraphy", "mappings", "authoring.py"), encoding="utf-8").read()
    code = "\n".join(line for line in source.splitlines()
                     if not line.strip().startswith("#"))
    for forbidden in (".owl", ".ttl", "rdflib", "GitHub/CIDOC", "CIDOC/"):
        assert forbidden not in code, f"{forbidden} appears in the catalogue code"
