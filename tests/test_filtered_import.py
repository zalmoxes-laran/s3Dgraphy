"""Round-trip tests for the 1.6 row-filtering feature.

Covers:

1. ``filters=None`` — no filter, all 6 rows imported.
2. ``filters={"sito": "Pompei"}`` — single filter, 2 rows imported.
3. ``filters={"sito": "Pompei", "area": "A"}`` — AND of two filters,
   1 row imported.
4. ``get_filter_columns()`` — discovery API returns the columns flagged
   as ``is_filter: true`` in the mapping.
5. ``get_distinct_values("sito")`` — returns the sorted list of
   distinct site names in the SQLite fixture.

The fixture builds an in-tempdir SQLite database with a ``us_table``
holding two rows for each of three Italian sites (Pompei, Ercolano,
Stabia). The mapping JSON is also written to a temp directory and
registered with ``mapping_registry`` so the importer can find it
without polluting the packaged mappings.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Make the in-repo src/ importable without requiring an editable install.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter  # noqa: E402
from s3dgraphy.mappings.registry import mapping_registry  # noqa: E402


# Site → list of (us_number, area, description) rows
_FIXTURE_ROWS = {
    "Pompei":   [(1001, "A", "Pompei foundation layer"),
                 (1002, "B", "Pompei collapse layer")],
    "Ercolano": [(2001, "A", "Ercolano floor surface"),
                 (2002, "B", "Ercolano destruction deposit")],
    "Stabia":   [(3001, "A", "Stabia mosaic substrate"),
                 (3002, "B", "Stabia drainage fill")],
}


@pytest.fixture
def filtered_setup(tmp_path):
    """Build a SQLite fixture + mapping JSON in a temp dir.

    Returns:
        (db_path, mapping_name): both strings. The mapping is
        registered under the 'pyarchinit' type with high priority so
        the importer's mapping loader finds it.
    """
    # --- 1. SQLite database -----------------------------------------
    db_path = tmp_path / "fixture.sqlite"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE us_table (
            us           INTEGER PRIMARY KEY,
            sito         TEXT NOT NULL,
            area         TEXT NOT NULL,
            d_stratigrafica TEXT
        )
        """
    )
    for site, rows in _FIXTURE_ROWS.items():
        for us_num, area, desc in rows:
            cur.execute(
                "INSERT INTO us_table (us, sito, area, d_stratigrafica) "
                "VALUES (?, ?, ?, ?)",
                (us_num, site, area, desc),
            )
    conn.commit()
    conn.close()

    # --- 2. Mapping JSON --------------------------------------------
    mapping_dir = tmp_path / "mappings"
    mapping_dir.mkdir()
    mapping_name = "test_filter_mapping"
    mapping_payload = {
        "name": "Filter test mapping",
        "description": "Mapping used by tests/test_filtered_import.py",
        "version": "1.0",
        "table_settings": {
            "format_type": "sqlite",
            "table_name": "us_table",
        },
        "column_mappings": {
            "sito": {
                "is_filter": True,
                "filter_required": True,
                "display_name": "Site",
                "description": "Site name",
            },
            "area": {
                "is_filter": True,
                "filter_required": False,
                "display_name": "Area",
                "description": "Excavation area",
            },
            "us": {
                "is_id": True,
                "node_type": "US",
            },
            "d_stratigrafica": {
                "is_description": True,
            },
        },
        "relations": [],
    }
    (mapping_dir / f"{mapping_name}.json").write_text(
        json.dumps(mapping_payload), encoding="utf-8"
    )

    # Register with high priority so the importer's mapping loader finds it
    # before any packaged mapping with the same name (there's none, but be
    # explicit).
    mapping_registry.add_mapping_directory(
        "pyarchinit", str(mapping_dir), priority="high"
    )

    yield str(db_path), mapping_name

    # Cleanup: drop the temp directory from the registry. The registry
    # has no removal API; we reach into the private store and pop the
    # entry to avoid pollution between test runs.
    dirs = mapping_registry._mapping_directories.get("pyarchinit", [])
    try:
        dirs.remove(str(mapping_dir))
    except ValueError:
        pass


def test_no_filters_imports_all_rows(filtered_setup):
    """filters=None → all 6 rows imported."""
    db_path, mapping_name = filtered_setup
    importer = PyArchInitImporter(
        filepath=db_path, mapping_name=mapping_name, filters=None
    )
    graph = importer.parse()
    # 6 stratigraphic nodes (one per row), no other US nodes expected.
    us_nodes = [n for n in graph.nodes if getattr(n, "node_type", None) == "US"]
    assert len(us_nodes) == 6, (
        f"expected 6 US nodes with filters=None, got {len(us_nodes)}: "
        f"{[n.name for n in us_nodes]}"
    )


def test_single_filter(filtered_setup):
    """filters={'sito': 'Pompei'} → only the 2 Pompei rows imported."""
    db_path, mapping_name = filtered_setup
    importer = PyArchInitImporter(
        filepath=db_path,
        mapping_name=mapping_name,
        filters={"sito": "Pompei"},
    )
    graph = importer.parse()
    us_nodes = [n for n in graph.nodes if getattr(n, "node_type", None) == "US"]
    names = sorted(n.name for n in us_nodes)
    assert names == ["1001", "1002"], (
        f"expected only Pompei rows (1001, 1002), got {names}"
    )


def test_and_filter(filtered_setup):
    """filters={'sito': 'Pompei', 'area': 'A'} → 1 row (us=1001)."""
    db_path, mapping_name = filtered_setup
    importer = PyArchInitImporter(
        filepath=db_path,
        mapping_name=mapping_name,
        filters={"sito": "Pompei", "area": "A"},
    )
    graph = importer.parse()
    us_nodes = [n for n in graph.nodes if getattr(n, "node_type", None) == "US"]
    names = sorted(n.name for n in us_nodes)
    assert names == ["1001"], (
        f"expected only us=1001 (Pompei + area A), got {names}"
    )


def test_get_filter_columns(filtered_setup):
    """get_filter_columns() returns the is_filter:true entries."""
    db_path, mapping_name = filtered_setup
    importer = PyArchInitImporter(
        filepath=db_path, mapping_name=mapping_name
    )
    cols = importer.get_filter_columns()
    by_name = {c["column"]: c for c in cols}
    assert set(by_name.keys()) == {"sito", "area"}, (
        f"expected ['sito', 'area'] as filter columns, got {sorted(by_name.keys())}"
    )
    assert by_name["sito"]["filter_required"] is True
    assert by_name["area"]["filter_required"] is False
    assert by_name["sito"]["display_name"] == "Site"


def test_get_distinct_values(filtered_setup):
    """get_distinct_values('sito') returns sorted distinct site names."""
    db_path, mapping_name = filtered_setup
    importer = PyArchInitImporter(
        filepath=db_path, mapping_name=mapping_name
    )
    values = importer.get_distinct_values("sito")
    assert values == ["Ercolano", "Pompei", "Stabia"], (
        f"expected sorted sites, got {values}"
    )


def test_filter_column_whitelist(filtered_setup):
    """A filter column not in the mapping is rejected.

    PyArchInitImporter.parse() wraps any unhandled exception in an
    ImportError, so the underlying ValueError surfaces as ImportError
    whose message contains the original whitelist failure. We assert on
    the message so the test stays meaningful either way.
    """
    db_path, mapping_name = filtered_setup
    importer = PyArchInitImporter(
        filepath=db_path,
        mapping_name=mapping_name,
        filters={"definitely_not_in_mapping": "x"},
    )
    with pytest.raises((ValueError, ImportError),
                       match="not declared in column_mappings"):
        importer.parse()
