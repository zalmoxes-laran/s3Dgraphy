"""The MAPPING EDITOR's foundation — schema, the CIDOC retro-map, XML, apply.

What is under test is the surface an authoring tool is built on, and the tests
are organised around the four ways it could quietly lie:

* **the schema drifts.** `source_settings` generalises `table_settings`, and every
  mapping on disk today says the old name. If the fallback broke, a user's
  pyarchinit mapping would stop working and nothing here would notice;
* **the retro-map is asserted instead of read.** The bridge CIDOC↔EM is the
  `mapping.cidoc` field the datamodels already declare, inverted. So the tests
  check REAL pairs (A2→US, E31→DocumentNode, P120_occurs_before→is_after) rather
  than that a dict has keys — the pairs are the contract with the ontology table;
* **a mapping validates and then fails at import.** An edge resolved from a CIDOC
  property says nothing about whether the datamodel allows it between those two
  types. That check is the difference between an editor that helps and one that
  hands you a file that breaks in a week;
* **an apply that reports success and writes nothing.** Measured, and it happened
  while this was written: passing a target graph set the importer's
  "enrich-only" flag, every record was skipped as "not found in existing graph",
  and the call returned ok with zero nodes.
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import tempfile

import pytest

from s3dgraphy import api
from s3dgraphy.contract.connector import VOLATILE_KEY
from s3dgraphy.graph import Graph
from s3dgraphy.mappings import authoring as A

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_XML = os.path.join(HERE, "fixtures", "mapping_editor_site.xml")


def xml_mapping(**extra):
    """The mapping the WP3 XML wants: a US per <us>, its description, its
    interpretation as a property, and <copre> as a stratigraphic edge."""
    mapping = {
        "name": "wp3-xml", "version": "1.0",
        "source_settings": {"format_type": "xml", "record_path": "/site/us"},
        "column_mappings": {
            "id": {"source_path": "@id", "cidoc": "A2 Stratigraphic Volume Unit",
                   "is_id": True},
            "descrizione": {"source_path": "descrizione", "is_description": True,
                            "target_id_column": "id"},
            "interpretazione": {"source_path": "interpretazione",
                                "node_type": "PropertyNode",
                                "property_name": "Interpretation",
                                "create_empty": True},
            "copre": {"source_path": "rapporti/copre", "is_relation": True,
                      "cidoc": "A2 Stratigraphic Volume Unit"},
        },
        "relations": [
            {"source_column": "id", "target_column": "interpretazione",
             "edge_type": "has_property"},
            {"source_column": "id", "target_column": "copre",
             "cidoc": "P120_occurs_before"},
        ],
    }
    mapping.update(extra)
    return mapping


# ── A1 · the schema, generalised without breaking what exists ───────────────

def test_a_mapping_that_says_table_settings_still_reads():
    """Every mapping on disk today says `table_settings`. A migration nobody
    asked for is not an improvement."""
    legacy = {"table_settings": {"format_type": "sqlite", "table_name": "us_table"},
              "column_mappings": {"us": {"node_type": "US", "is_id": True}}}
    settings = A.source_settings(legacy)
    assert settings["format_type"] == "sqlite"
    assert settings["table_name"] == "us_table"
    assert A.format_of(legacy) == "sqlite"


def test_source_settings_wins_when_both_are_there():
    both = {"table_settings": {"format_type": "sqlite"},
            "source_settings": {"format_type": "xml", "record_path": "/a/b"},
            "column_mappings": {}}
    assert A.format_of(both) == "xml"
    assert A.source_settings(both)["record_path"] == "/a/b"


def test_a_mapping_with_no_settings_at_all_defaults_to_the_old_assumption():
    """xlsx — what this library assumed before formats were a field. Guessing
    something new would silently change what an old mapping does."""
    assert A.format_of({"column_mappings": {}}) == "xlsx"


def test_the_formats_are_the_four_declared():
    assert api.mapping_formats() == ("sqlite", "xlsx", "csv", "xml")


# ── A2 · the CIDOC inverse index, on real pairs ─────────────────────────────

def test_the_inverse_index_is_read_from_the_datamodel_not_written_here():
    index = api.mapping_cidoc_index()
    classes, properties = index["classes"], index["properties"]
    # the pairs the ontology table cares about
    assert [c["em_type"] for c in classes["A2 Stratigraphic Volume Unit"]] == ["US"]
    assert "DocumentNode" in [c["em_type"] for c in classes["E31 Document"]]
    assert "AuthorNode" in [c["em_type"] for c in classes["E21 Person"]]
    assert {"SF", "RSF"} <= {c["em_type"] for c in classes["E19 Physical Object"]}
    assert [p["edge_type"] for p in properties["P120_occurs_before"]] == ["is_after"]
    assert [p["edge_type"] for p in properties["P123_resulted_from"]] \
        == ["changed_from"]


def test_one_cidoc_class_can_be_several_em_types_and_the_order_is_stable():
    """A8 is the CIDOC reading of eight EM types. The index returns candidates,
    in datamodel order — a set's whim would make the default target change
    between runs."""
    index = api.mapping_cidoc_index()
    a8 = [c["em_type"] for c in index["classes"]["A8 Stratigraphic Unit"]]
    assert len(a8) > 3
    assert a8 == [c["em_type"] for c in api.mapping_cidoc_index()
                  ["classes"]["A8 Stratigraphic Unit"]]
    assert a8[0] == "StratigraphicNode"


def test_the_em_type_is_one_a_resolver_can_actually_resolve():
    """The measured trap: preferring the datamodel's abbreviation everywhere made
    `E31 Document` resolve to **DOC**, which `base_importer` cannot turn into a
    class. Abbreviations for stratigraphic types (a resolver knows those), class
    names elsewhere."""
    from s3dgraphy.nodes.base_node import Node
    from s3dgraphy.utils.utils import get_stratigraphic_node_class

    index = api.mapping_cidoc_index()
    class_names = {c.__name__ for c in Node.node_type_map.values()}
    for candidates in index["classes"].values():
        for candidate in candidates:
            em = candidate["em_type"]
            resolvable = em in class_names
            if not resolvable:
                # then it must be a stratigraphic abbreviation
                assert get_stratigraphic_node_class(em) is not None, em


def test_an_edge_mapped_only_through_an_extension_is_reported_not_dropped():
    """`abuts` has no plain CIDOC property — it is CRMarchaeo's
    AP11 + a type tag. Saying "no CIDOC" about it would be wrong."""
    index = api.mapping_cidoc_index()
    assert "abuts" in index["properties_via_extension"]
    assert "cuts" in index["properties_via_extension"]
    assert "is_after" not in index["properties_via_extension"]


def test_the_catalog_sorts_the_way_a_person_looks_things_up():
    catalog = api.mapping_target_catalog()
    assert len(catalog) > 20
    codes = [c["cidoc"] for c in catalog]
    # E3 before E31 before E310 — by letter then NUMBER, not as strings
    e_numbers = [int(c[1:].split()[0]) for c in codes
                 if c[:1] == "E" and c[1:2].isdigit()]
    assert e_numbers == sorted(e_numbers)
    doc = next(c for c in catalog if c["cidoc"] == "E31 Document")
    assert doc["em_type"] == "DocumentNode"
    assert doc["cidoc_direct"] is False


# ── A3 · the fields of a source, with samples ──────────────────────────────

def test_xml_fields_are_paths_with_samples_and_a_record_candidate():
    out = api.mapping_source_fields(SITE_XML)
    assert out["format"] == "xml"
    # WHICH element is a record is not knowable — the repeated ones are offered,
    # most frequent first, and the first is the default
    assert out["record_path"] == "/site/us"
    assert out["record_paths"][0] == {"path": "/site/us", "count": 3}
    assert out["records"] == 3
    fields = {f["source_path"]: f for f in out["fields"]}
    assert set(fields) == {"@id", "@period", "descrizione", "interpretazione",
                           "rapporti/copre"}
    assert fields["@id"]["samples"] == ["1", "2", "3"]
    assert fields["interpretazione"]["samples"][0] == "Crollo del tetto"
    # a field present in one record out of three SAYS so
    assert fields["rapporti/copre"]["filled"] == 1


def test_a_chosen_record_path_changes_what_the_fields_are():
    out = api.mapping_source_fields(SITE_XML, record_path="/site")
    assert out["records"] == 1
    names = {f["source_path"] for f in out["fields"]}
    assert "@code" in names, "at /site the attributes are the site's"


def test_sqlite_fields_come_with_the_table_list_and_samples():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "scavo.sqlite")
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE us_table (us TEXT, d_stratigrafica TEXT, "
                         "d_interpretativa TEXT)")
            conn.executemany("INSERT INTO us_table VALUES (?,?,?)",
                             [("1", "crollo", "tetto"), ("2", "pavimento", "")])
            conn.execute("CREATE TABLE altra (x TEXT)")
        out = api.mapping_source_fields(path)
        assert out["format"] == "sqlite"
        assert out["tables"] == ["altra", "us_table"]
        assert out["table"] == "altra", "the first table, alphabetically — stated"
        out = api.mapping_source_fields(path, table="us_table")
        fields = {f["name"]: f for f in out["fields"]}
        assert set(fields) == {"us", "d_stratigrafica", "d_interpretativa"}
        assert fields["us"]["samples"] == ["1", "2"]
        assert fields["d_interpretativa"]["filled"] == 1


def test_csv_fields_sniff_the_delimiter():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "us.csv")
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(["us", "descrizione"])
            writer.writerow(["1", "crollo"])
        out = api.mapping_source_fields(path)
        assert out["format"] == "csv"
        assert out["delimiter"] == ";"
        assert [f["name"] for f in out["fields"]] == ["us", "descrizione"]


# ── A3 · the edges, from the datamodel ─────────────────────────────────────

def test_allowed_edges_are_the_datamodels_and_carry_their_cidoc():
    edges = {e["edge_type"]: e for e in api.mapping_allowed_edges("US", "US")}
    assert "is_after" in edges
    assert edges["is_after"]["cidoc"] == "P120_occurs_before"
    assert "has_property" not in edges, "a US does not have a property US"
    to_property = {e["edge_type"] for e in
                   api.mapping_allowed_edges("US", "PropertyNode")}
    assert "has_property" in to_property


def test_an_abbreviation_and_its_class_answer_the_same():
    """`US` is what a mapping carries; `StratigraphicUnit` is what the class is
    called. `allowed_connections` is written in neither — it says
    `StratigraphicNode`."""
    by_abbrev = {e["edge_type"] for e in api.mapping_allowed_edges("US", "US")}
    by_class = {e["edge_type"] for e in
                api.mapping_allowed_edges("StratigraphicUnit", "StratigraphicUnit")}
    assert by_abbrev == by_class
    assert "is_after" in by_abbrev


# ── A1/A3 · validation ─────────────────────────────────────────────────────

def test_a_good_mapping_validates_clean():
    assert api.mapping_validate(xml_mapping()) == {"ok": True, "errors": [],
                                                   "warnings": []}


def test_the_datamodel_refuses_an_edge_it_does_not_allow():
    """THE check that makes CIDOC-first safe: resolving a property to an edge says
    nothing about whether the edge is legal between those two types."""
    mapping = xml_mapping()
    mapping["relations"][0]["edge_type"] = "is_after"      # US → PropertyNode
    verdict = api.mapping_validate(mapping)
    assert verdict["ok"] is False
    assert any("does not allow 'is_after'" in e for e in verdict["errors"])
    assert any("has_property" in e for e in verdict["errors"]), \
        "…and it says what IS allowed"


def test_the_errors_name_the_field():
    empty = api.mapping_validate({"column_mappings": {}})
    assert not empty["ok"]
    assert any("column_mappings" in e for e in empty["errors"])
    no_id = api.mapping_validate({"column_mappings": {"a": {"node_type": "US"}}})
    assert any("is_id" in e for e in no_id["errors"])
    two_ids = api.mapping_validate({"column_mappings": {
        "a": {"node_type": "US", "is_id": True},
        "b": {"node_type": "US", "is_id": True}}})
    assert any("more than one is_id" in e for e in two_ids["errors"])
    dangling = api.mapping_validate({"column_mappings": {
        "a": {"node_type": "US", "is_id": True},
        "b": {"is_description": True, "target_id_column": "nope"}}})
    assert any("target_id_column" in e for e in dangling["errors"])


def test_an_xml_mapping_without_a_record_path_is_warned_not_refused():
    """An editor must be able to save work in progress: what makes a mapping
    surprising is a warning, what makes it unusable is an error."""
    mapping = xml_mapping()
    mapping["source_settings"].pop("record_path")
    verdict = api.mapping_validate(mapping)
    assert verdict["ok"] is True
    assert any("record_path" in w for w in verdict["warnings"])


def test_a_relation_target_that_would_double_as_a_property_is_warned():
    """The surprise worth naming: outside ten stratigraphic edges the importer
    ALSO makes a property of a relation's target column, so the same fact lands
    twice — once as an edge, once as "copre: 2"."""
    mapping = xml_mapping()
    mapping["column_mappings"]["copre"].pop("is_relation")
    verdict = api.mapping_validate(mapping)
    assert any("is_relation" in w for w in verdict["warnings"])


# ── A1 · normalisation: the CIDOC choice becomes an EM type ─────────────────

def test_normalising_resolves_the_cidoc_choice_and_says_where_it_came_from():
    normalized = api.mapping_normalize(xml_mapping())
    column = normalized["column_mappings"]["id"]
    assert column["node_type"] == "US"
    assert column["cidoc_resolved_from"] == "A2 Stratigraphic Volume Unit"
    relation = normalized["relations"][1]
    assert relation["edge_type"] == "is_after"
    assert relation["cidoc_resolved_from"] == "P120_occurs_before"
    # …and the original is untouched: normalising is a copy
    assert "node_type" not in xml_mapping()["column_mappings"]["id"]


def test_an_explicit_node_type_is_never_overwritten_by_a_cidoc_guess():
    mapping = xml_mapping()
    mapping["column_mappings"]["id"]["node_type"] = "USVs"
    assert api.mapping_normalize(mapping)["column_mappings"]["id"]["node_type"] \
        == "USVs"


def test_a_cidoc_class_no_em_type_implements_is_marked_not_dropped():
    mapping = xml_mapping()
    mapping["column_mappings"]["id"]["cidoc"] = "E999 Something Nobody Built"
    mapping["column_mappings"]["id"].pop("node_type", None)
    column = api.mapping_normalize(mapping)["column_mappings"]["id"]
    assert column.get("cidoc_direct") is True
    assert "node_type" not in column
    assert any("CIDOC-direct" in w for w in api.mapping_validate(mapping)["warnings"])


# ── A4 · the XML importer ──────────────────────────────────────────────────

def test_the_xml_importer_reads_the_tree_as_rows():
    from s3dgraphy.importer.xml_importer import XMLImporter

    importer = XMLImporter(SITE_XML, mapping=xml_mapping())
    records = importer.records()
    assert len(records) == 3
    assert records[0]["@id"] == "1"
    assert records[0]["rapporti/copre"] == "2"
    graph = importer.parse()
    assert importer.rows_read == 3
    us = [n for n in graph.nodes if n.node_type == "US"]
    assert sorted(n.name for n in us) == ["1", "2", "3"]
    assert [n for n in us if n.name == "1"][0].description \
        == "Strato di crollo con tegole"


def test_the_relation_in_the_xml_becomes_the_edge_the_datamodel_allows():
    from s3dgraphy.importer.xml_importer import XMLImporter

    graph = XMLImporter(SITE_XML, mapping=xml_mapping()).parse()
    names = {n.node_id: n.name for n in graph.nodes}
    edges = [(names.get(e.edge_source), e.edge_type, names.get(e.edge_target))
             for e in graph.edges]
    assert ("1", "is_after", "2") in edges, edges


def test_a_relation_to_a_record_that_is_not_here_is_a_warning_not_a_node():
    """A `<copre>99</copre>` must not invent a US 99 nobody described."""
    from s3dgraphy.importer.xml_importer import XMLImporter

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "one.xml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('<site><us id="1"><descrizione>x</descrizione>'
                         '<interpretazione>y</interpretazione>'
                         '<rapporti><copre>99</copre></rapporti></us></site>')
        importer = XMLImporter(path, mapping=xml_mapping())
        graph = importer.parse()
        assert sorted(n.name for n in graph.nodes if n.node_type == "US") == ["1"]
        assert any("99" in w and "not in the graph" in w
                   for w in importer.warnings), importer.warnings


def test_the_importer_needs_a_mapping_and_says_so():
    from s3dgraphy.importer.xml_importer import XMLImporter

    with pytest.raises(ValueError) as caught:
        XMLImporter(SITE_XML)
    assert "mapping" in str(caught.value)


# ── A5 · volatile, or baked ────────────────────────────────────────────────

def volatile_count(graph) -> int:
    return sum(1 for n in graph.nodes
               if isinstance(getattr(n, "data", None), dict)
               and n.data.get(VOLATILE_KEY))


def test_a_volatile_apply_marks_what_it_added_with_the_shared_key():
    """The same marker the connector seam and EMStudio use, so an existing bake
    promotes it — a second key would have needed a second bake."""
    graph = Graph(graph_id="scavo")
    report = api.mapping_apply(xml_mapping(), SITE_XML, graph=graph,
                               mode="volatile")
    assert report["ok"] is True
    assert report["rows"] == 3
    assert report["nodes_added"] == 6            # 3 US + 3 property
    assert report["edges_added"] == 4            # 3 has_property + 1 is_after
    assert report["volatile"] is True
    assert volatile_count(graph) == 6
    assert VOLATILE_KEY == "aux_volatile"


def test_a_baked_apply_marks_nothing():
    graph = Graph(graph_id="scavo")
    report = api.mapping_apply(xml_mapping(), SITE_XML, graph=graph, mode="bake")
    assert report["ok"] is True
    assert report["nodes_added"] == 6
    assert volatile_count(graph) == 0


def test_an_apply_into_a_graph_CREATES_rather_than_only_enriching():
    """The measured bug: passing a target graph set the importer's enrich-only
    flag, every record was skipped as "not found in existing graph", and the call
    returned ok with zero nodes. Success with nothing written is the worst kind."""
    graph = Graph(graph_id="scavo")
    report = api.mapping_apply(xml_mapping(), SITE_XML, graph=graph, mode="bake")
    assert report["nodes_added"] > 0
    assert not any("not found in existing graph" in w
                   for w in report["warnings"]), report["warnings"]


def test_applying_twice_does_not_double_the_edges():
    graph = Graph(graph_id="scavo")
    api.mapping_apply(xml_mapping(), SITE_XML, graph=graph, mode="bake")
    edges = len(graph.edges)
    second = api.mapping_apply(xml_mapping(), SITE_XML, graph=graph, mode="bake")
    assert second["edges_added"] == 0, "the same edge is one edge"
    assert len(graph.edges) == edges


def test_a_preview_needs_no_graph():
    report = api.mapping_apply(xml_mapping(), SITE_XML)
    assert report["ok"] is True
    assert report["graph"] is not None
    assert report["nodes_added"] == 6


def test_an_invalid_mapping_is_refused_before_anything_is_written():
    graph = Graph(graph_id="scavo")
    before = len(graph.nodes)
    mapping = xml_mapping()
    mapping["relations"][0]["edge_type"] = "is_after"       # illegal here
    report = api.mapping_apply(mapping, SITE_XML, graph=graph)
    assert report["ok"] is False
    assert report["errors"]
    assert len(graph.nodes) == before, "a refused mapping wrote nothing"


def test_an_unknown_mode_is_a_programming_error():
    with pytest.raises(ValueError):
        api.mapping_apply(xml_mapping(), SITE_XML, mode="maybe")


def test_csv_apply_is_no_longer_refused():
    """It WAS a declared limit ("csv apply is not implemented"), closed in the
    second round by a row-producer that adds no rules of its own — see
    `test_mapping_csv_and_relations.py` for the csv↔xlsx parity that proves it.
    Here only the dispatch: csv is a format `apply` knows."""
    from s3dgraphy.mappings.authoring import _IMPORTERS

    assert "csv" in _IMPORTERS
    mapping = xml_mapping()
    mapping["source_settings"] = {"format_type": "csv"}
    report = api.mapping_apply(mapping, "/nowhere/whatever.csv")
    # it fails because the FILE is not there, not because the format is refused
    assert report["ok"] is False
    assert not any("not implemented" in e for e in report["errors"])
    assert any("FileNotFoundError" in e or "No such file" in e
               for e in report["errors"]), report["errors"]


def test_a_table_apply_asks_for_the_registered_name():
    """The table importers load their mapping from the registry by name; an
    inline mapping has none yet, and the refusal says to save it first rather
    than failing inside pandas."""
    mapping = xml_mapping()
    mapping["source_settings"] = {"format_type": "xlsx", "sheet_name": 0}
    report = api.mapping_apply(mapping, "whatever.xlsx")
    assert report["ok"] is False
    assert any("mapping_name" in e for e in report["errors"])
