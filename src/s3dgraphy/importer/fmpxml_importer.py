"""FileMaker `FMPXMLRESULT` → graph, through the same mapping as any table.

## Why this is not just XML

FileMaker's export has an XML syntax and a TABLE shape, and the two disagree in
the way that matters: the field NAMES are declared once, up front, in a
`METADATA` block, and the values come later in `RESULTSET/ROW/COL/DATA` with no
names at all — associated to their field by POSITION.

    <METADATA><FIELD NAME="d_locus_no" …/><FIELD NAME="d_description" …/></METADATA>
    <RESULTSET FOUND="173">
      <ROW><COL><DATA>35001</DATA></COL><COL><DATA>pit fill</DATA></COL></ROW>

`XMLImporter` reads a tree where every field has a path of its own, so pointed
at this it finds `/FMPXMLRESULT/RESULTSET/ROW/COL/DATA` repeated N times per
record and cannot tell one field from another. It does not fail: it produces
rows in which every column collides. That is the failure worth naming, because
it is silent.

So this class changes ONE thing — how a record becomes a dict — and inherits
the rest. Column names come from `METADATA`, values from each `ROW` by index,
and from there on a FileMaker source is an ordinary table: the same
`column_mappings`, the same relations, the same importer underneath.

## Why a format and not a converter

The alternative was a script writing CSVs beside the source. It would work, and
it would leave a second copy of every dataset on disk — which for an excavation
database under a partner's licence is the wrong default. A mapping that reads
the export where it lies copies nothing.

Declared as `source_settings.format_type: "fmpxml"`. A mapping that says `xml`
over a FileMaker export is also accepted, with a warning: saying "this is XML"
about this file is true and useless, and the alternative to accepting it is 173
rows of collided columns that look like data.

A multi-table export is one file per table (`loci.xml`, `stratigraphy.xml`), so
there is nothing to select inside a file: `table_name` and `record_path` are
not read, and `FOUND` on `RESULTSET` is what the source itself says it holds.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from .xml_importer import XMLImporter

#: FileMaker's namespace. Stripped like any other — a namespace is a fact about
#: the file, not about a field somebody mapped.
FMP_NS = "http://www.filemaker.com/fmpxmlresult"

#: The root element that identifies one of these exports.
FMP_ROOT = "FMPXMLRESULT"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in str(tag) else str(tag)


def looks_like_fmpxml(path: str) -> bool:
    """Is this file a FileMaker export? Read cheaply, by its root element.

    Used to catch a mapping that declares plain `xml` over one of these, which
    would otherwise import silently and wrongly.
    """
    try:
        for _event, element in ET.iterparse(path, events=("start",)):
            return _local(element.tag) == FMP_ROOT
    except (ET.ParseError, OSError):
        return False
    return False


def field_names(path: str) -> List[str]:
    """The column names a FileMaker export declares, in order."""
    root = ET.parse(path).getroot()
    metadata = root.find(f"{{{FMP_NS}}}METADATA")
    if metadata is None:                      # an export without a namespace
        metadata = root.find("METADATA")
    if metadata is None:
        return []
    return [f.get("NAME") or "" for f in metadata]


def declared_row_count(path: str) -> Optional[int]:
    """What the export says it holds (`RESULTSET/@FOUND`), or None.

    Worth having beside the rows actually read: a mismatch means the file was
    truncated, and a truncated import that reports success is the kind of thing
    nobody notices until much later.
    """
    root = ET.parse(path).getroot()
    rs = root.find(f"{{{FMP_NS}}}RESULTSET") or root.find("RESULTSET")
    if rs is None:
        return None
    try:
        return int(rs.get("FOUND"))
    except (TypeError, ValueError):
        return None


class FMPXMLImporter(XMLImporter):
    """A FileMaker export, read as the table it is."""

    def records(self) -> List[Dict[str, Any]]:
        """Every row as `{field_name: value}`, names taken from METADATA."""
        root = ET.parse(self.filepath).getroot()
        if _local(root.tag) != FMP_ROOT:
            raise ValueError(
                f"{self.filepath}: root is <{_local(root.tag)}>, not "
                f"<{FMP_ROOT}> — this is not a FileMaker export. Use "
                f'format_type "xml".')

        names = [_ for _ in field_names(self.filepath)]
        resultset = (root.find(f"{{{FMP_NS}}}RESULTSET")
                     or root.find("RESULTSET"))
        rows: List[Dict[str, Any]] = []
        if resultset is None:
            return rows

        for row in resultset:
            values: List[Optional[str]] = []
            for col in row:
                data = col.find(f"{{{FMP_NS}}}DATA")
                if data is None:
                    data = col.find("DATA")
                values.append(data.text if data is not None else None)
            # zip() would drop the tail of whichever side is shorter and say
            # nothing. A row with fewer COLs than METADATA declares is a real
            # export (FileMaker omits nothing, but a hand-trimmed file might),
            # and the honest reading is that the missing fields are empty.
            record = {name: (values[i] if i < len(values) else None)
                      for i, name in enumerate(names)}
            rows.append(record)
        return rows

    def _row_for_mapping(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Already keyed by column name — no path translation to do.

        `source_path` is still honoured when a mapping sets one, so a
        descriptor written against the XML shape keeps working.
        """
        row: Dict[str, Any] = {}
        for name, column in (self.mapping.get("column_mappings") or {}).items():
            if (column or {}).get("is_relation"):
                continue      # an edge, not a fact about this record
            key = str((column or {}).get("source_path") or name)
            row[name] = record.get(key, record.get(name, ""))
        return row
