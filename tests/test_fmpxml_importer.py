"""FileMaker FMPXMLRESULT: XML syntax, table shape.

The reason this is a format of its own and not a flavour of `xml` is the one
test below that measures what the plain XML reader does with one of these
files. It does not fail. It produces rows whose columns collide — which is
indistinguishable from data until someone checks a value by hand.
"""

import json
from pathlib import Path

import pytest

from s3dgraphy import api
from s3dgraphy.importer.fmpxml_importer import (
    FMPXMLImporter, looks_like_fmpxml, field_names, declared_row_count)
from s3dgraphy.mappings.authoring import detect_format, sniff_format

FIXTURES = Path(__file__).parent / "fixtures"
FM = FIXTURES / "filemaker_export.xml"
PLAIN = FIXTURES / "plain_tree.xml"


def _reader(path):
    r = FMPXMLImporter.__new__(FMPXMLImporter)
    r.filepath = str(path)
    return r


# ── recognising one ──────────────────────────────────────────────────────────

def test_a_filemaker_export_is_recognised_by_its_root():
    assert looks_like_fmpxml(str(FM)) is True
    assert looks_like_fmpxml(str(PLAIN)) is False


def test_the_extension_alone_cannot_tell_them_apart():
    """Both are `.xml`, so detect_format says `xml` for both — correctly, since
    it never opens a file. sniff_format is the one that reads."""
    assert detect_format(str(FM)) == "xml"
    assert detect_format(str(PLAIN)) == "xml"
    assert sniff_format(str(FM)) == "fmpxml"
    assert sniff_format(str(PLAIN)) == "xml"


def test_a_missing_file_does_not_raise_from_sniffing():
    assert looks_like_fmpxml(str(FIXTURES / "nope.xml")) is False


# ── reading one ──────────────────────────────────────────────────────────────

def test_the_names_come_from_metadata_and_the_values_by_position():
    assert field_names(str(FM)) == ["locus_no", "description", "material"]
    rows = _reader(FM).records()
    assert rows[0] == {"locus_no": "W100", "description": "muro perimetrale",
                       "material": "calcare"}
    assert rows[2]["locus_no"] == "#102"


def test_the_declared_count_is_reported_beside_what_was_read():
    """A truncated file is the failure that reports success."""
    assert declared_row_count(str(FM)) == 3
    assert len(_reader(FM).records()) == 3
    fields = api.mapping_source_fields(str(FM), format_type="fmpxml")
    assert fields["declared_rows"] == 3 and fields["read_rows"] == 3


def test_an_empty_cell_is_empty_and_not_a_shifted_value():
    """The trap of a positional format: one missed empty COL and every
    following field in that row holds its neighbour's value."""
    rows = _reader(FM).records()
    assert rows[1] == {"locus_no": "101", "description": "riempimento",
                       "material": None}


def test_reading_a_plain_tree_as_filemaker_says_so():
    with pytest.raises(ValueError, match="not a FileMaker export"):
        _reader(PLAIN).records()


# ── why it is not a flavour of `xml` ─────────────────────────────────────────

def test_the_plain_xml_reader_collides_the_columns_instead_of_failing():
    """THE measurement this format exists for.

    Pointed at a FileMaker export, XMLImporter finds
    `…/RESULTSET/ROW/COL/DATA` three times in one record and cannot tell the
    fields apart. It raises nothing. What comes back is one value where three
    were expected — a row that looks like a row.
    """
    from s3dgraphy.importer.xml_importer import XMLImporter
    reader = XMLImporter.__new__(XMLImporter)
    reader.filepath = str(FM)
    reader.mapping = {"source_settings": {"record_path": "/FMPXMLRESULT/RESULTSET/ROW"}}
    rows = reader.records()
    assert rows, "the plain reader produced nothing at all — then it would be safe"
    keys = set().union(*(r.keys() for r in rows))
    assert not ({"locus_no", "description", "material"} & keys), (
        "if the plain reader now recovers the field names, this format's reason "
        "to exist has changed and the docs need revisiting")


# ── through the mapping layer ────────────────────────────────────────────────

def _mapping():
    return {
        "name": "fixture",
        "source_settings": {"format_type": "fmpxml"},
        "column_mappings": {
            "locus_no": {"node_type": "StratigraphicNode", "is_id": True},
            "description": {"node_type": "StratigraphicNode",
                            "is_description": True,
                            "target_id_column": "locus_no"},
            "material": {"node_type": "PropertyNode", "property_name": "material"},
        },
        "relations": [],
    }


def test_the_format_is_declarable_and_validates():
    assert "fmpxml" in api.mapping_formats()
    assert api.mapping_validate(_mapping())["ok"]


def test_record_path_on_a_filemaker_source_is_a_warning():
    mapping = _mapping()
    mapping["source_settings"]["record_path"] = "/FMPXMLRESULT/RESULTSET/ROW"
    report = api.mapping_validate(mapping)
    assert report["ok"]                      # it still runs
    assert any("one table per file" in w for w in report["warnings"])


def test_an_export_imports_as_an_ordinary_table():
    res = api.mapping_apply(_mapping(), str(FM), mode="volatile")
    assert res["ok"] and res["rows"] == 3
    graph = res["graph"]
    units = {n.name: getattr(n, "description", "")
             for n in graph.nodes if "Stratigraphic" in type(n).__name__}
    assert units == {"W100": "muro perimetrale", "101": "riempimento",
                     "#102": "taglio"}
