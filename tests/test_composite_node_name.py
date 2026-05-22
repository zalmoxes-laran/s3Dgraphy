"""Round-trip tests for the 1.6 composite-node-name feature.

Covers ``table_settings.node_name_template`` resolution in
:class:`PyArchInitImporter`:

1. All three columns present → ``A.US.101``.
2. ``unita_tipo`` empty → ``A.101`` (empty component dropped, dots collapsed).
3. ``area`` empty + ``unita_tipo`` empty → ``101`` (both dropped).
4. Template absent (legacy mapping) → fallback to bare ``us`` value.

Each test builds a small SQLite fixture in a temp dir and a mapping
JSON that points at it, then asserts on the resulting
``StratigraphicNode.name`` values. This is the same pattern as
``test_filtered_import.py``.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# Make the in-repo src/ importable without requiring an editable install.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter  # noqa: E402
from s3dgraphy.mappings.registry import mapping_registry  # noqa: E402


def _write_fixture(tmp_path, rows, mapping_payload, mapping_name):
    """Build the SQLite + mapping fixture, register mapping_dir.

    ``rows`` is a list of (us, sito, area, unita_tipo, d_stratigrafica)
    tuples. Returns ``(db_path, mapping_name, mapping_dir)``.
    """
    db_path = tmp_path / "fixture.sqlite"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE us_table (
            us              INTEGER PRIMARY KEY,
            sito            TEXT NOT NULL,
            area            TEXT,
            unita_tipo      TEXT,
            d_stratigrafica TEXT
        )
        """
    )
    for row in rows:
        cur.execute(
            "INSERT INTO us_table "
            "(us, sito, area, unita_tipo, d_stratigrafica) "
            "VALUES (?, ?, ?, ?, ?)",
            row,
        )
    conn.commit()
    conn.close()

    mapping_dir = tmp_path / "mappings"
    mapping_dir.mkdir()
    (mapping_dir / f"{mapping_name}.json").write_text(
        json.dumps(mapping_payload), encoding="utf-8"
    )
    mapping_registry.add_mapping_directory(
        "pyarchinit", str(mapping_dir), priority="high"
    )
    return str(db_path), mapping_name, str(mapping_dir)


def _cleanup_mapping_dir(mapping_dir):
    dirs = mapping_registry._mapping_directories.get("pyarchinit", [])
    try:
        dirs.remove(mapping_dir)
    except ValueError:
        pass


def _base_mapping(name: str, with_template: bool):
    """Build a mapping payload for the composite-name tests."""
    payload = {
        "name": name,
        "description": "Composite node-name test mapping",
        "version": "1.6.0",
        "table_settings": {
            "format_type": "sqlite",
            "table_name": "us_table",
        },
        "column_mappings": {
            "sito": {
                "is_filter": True,
                "filter_required": True,
                "display_name": "Site",
            },
            "area": {
                "is_filter": True,
                "filter_required": False,
                "display_name": "Area",
            },
            "unita_tipo": {
                "is_filter": True,
                "filter_required": False,
                "display_name": "Stratigraphic Unit Type",
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
    if with_template:
        payload["table_settings"]["node_name_template"] = (
            "{area}.{unita_tipo}.{us}"
        )
    return payload


def _us_node_names(graph):
    return sorted(
        n.name for n in graph.nodes
        if getattr(n, "node_type", None) == "US"
    )


def test_composite_name_all_components(tmp_path):
    """All three placeholders populated → ``A.US.101``."""
    rows = [(101, "Pompei", "A", "US", "layer one")]
    payload = _base_mapping("test_composite_all", with_template=True)
    db, name, mdir = _write_fixture(tmp_path, rows, payload, "test_composite_all")
    try:
        importer = PyArchInitImporter(filepath=db, mapping_name=name)
        graph = importer.parse()
        assert _us_node_names(graph) == ["A.US.101"], (
            f"expected ['A.US.101'], got {_us_node_names(graph)}"
        )
    finally:
        _cleanup_mapping_dir(mdir)


def test_composite_name_empty_unita_tipo(tmp_path):
    """``unita_tipo=''`` → component dropped, dots collapsed: ``A.101``."""
    rows = [(101, "Pompei", "A", "", "layer one")]
    payload = _base_mapping("test_composite_empty_tipo", with_template=True)
    db, name, mdir = _write_fixture(
        tmp_path, rows, payload, "test_composite_empty_tipo"
    )
    try:
        importer = PyArchInitImporter(filepath=db, mapping_name=name)
        graph = importer.parse()
        assert _us_node_names(graph) == ["A.101"], (
            f"expected ['A.101'], got {_us_node_names(graph)}"
        )
    finally:
        _cleanup_mapping_dir(mdir)


def test_composite_name_empty_area_and_tipo(tmp_path):
    """Both ``area`` and ``unita_tipo`` empty → ``101``."""
    # Use None for area to also exercise the None branch alongside "".
    rows = [(101, "Pompei", None, "", "layer one")]
    payload = _base_mapping(
        "test_composite_empty_area_tipo", with_template=True
    )
    db, name, mdir = _write_fixture(
        tmp_path, rows, payload, "test_composite_empty_area_tipo"
    )
    try:
        importer = PyArchInitImporter(filepath=db, mapping_name=name)
        graph = importer.parse()
        assert _us_node_names(graph) == ["101"], (
            f"expected ['101'], got {_us_node_names(graph)}"
        )
    finally:
        _cleanup_mapping_dir(mdir)


def test_legacy_mapping_no_template_falls_back_to_bare_us(tmp_path):
    """No ``node_name_template`` in mapping → name is the bare ``us`` value."""
    rows = [(101, "Pompei", "A", "US", "layer one")]
    payload = _base_mapping(
        "test_composite_legacy", with_template=False
    )
    db, name, mdir = _write_fixture(
        tmp_path, rows, payload, "test_composite_legacy"
    )
    try:
        importer = PyArchInitImporter(filepath=db, mapping_name=name)
        graph = importer.parse()
        assert _us_node_names(graph) == ["101"], (
            f"expected ['101'] (bare us value), got {_us_node_names(graph)}"
        )
    finally:
        _cleanup_mapping_dir(mdir)


def test_composite_name_unit_resolver_directly():
    """Exercise the resolver helper without touching the DB.

    Guards the regex-based substitution against accidental regressions
    in placeholder syntax handling.
    """
    # Build a minimal importer-shaped object by monkey-patching the
    # mapping attribute on a constructed instance. We can't call
    # __init__ because it touches the filesystem; the resolver only
    # reads self.mapping, so we bind the bare class method to a
    # SimpleNamespace.
    from types import SimpleNamespace

    ns = SimpleNamespace(
        mapping={
            "table_settings": {
                "node_name_template": "{area}.{unita_tipo}.{us}"
            }
        }
    )
    resolve = PyArchInitImporter._resolve_node_name.__get__(ns)

    # All populated.
    assert resolve({"area": "A", "unita_tipo": "USM", "us": "12"}, "us") == "A.USM.12"
    # unita_tipo empty.
    assert resolve({"area": "A", "unita_tipo": "", "us": "12"}, "us") == "A.12"
    # area None, unita_tipo "".
    assert resolve({"area": None, "unita_tipo": "", "us": "12"}, "us") == "12"
    # All empty → fallback to bare id.
    assert resolve({"area": "", "unita_tipo": "", "us": "12"}, "us") == "12"
