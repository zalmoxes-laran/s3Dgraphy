"""Tests for the pyArchInit -> LocationNodeGroup mapping (sector as a node).

Covers ``_process_location_memberships`` in :class:`PyArchInitImporter`:
columns flagged ``node_type == 'LocationNodeGroup'`` (e.g. ``settore``,
``area``) must become ONE shared :class:`LocationNodeGroup` per distinct
value -- deduplicated across rows -- with every stratigraphic unit linked
to it by an ``is_in_location`` edge.

A sector/area is an identitary place (CIDOC E53 Place), not a per-row
string property: N US in the same sector -> 1 location node + N edges,
NOT N copies. See mappings/pyarchinit/pyarchinit_us_mapping_v2.json.

Same fixture pattern as test_composite_node_name.py.
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
    """Build the SQLite + mapping fixture, register the mapping dir.

    ``rows`` is a list of
    ``(us, sito, area, unita_tipo, settore, d_stratigrafica)`` tuples.
    Returns ``(db_path, mapping_name, mapping_dir)``.
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
            settore         TEXT,
            d_stratigrafica TEXT
        )
        """
    )
    cur.executemany(
        "INSERT INTO us_table "
        "(us, sito, area, unita_tipo, settore, d_stratigrafica) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
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


def _mapping(name):
    """Mapping that routes `settore` to a LocationNodeGroup (kind=study)."""
    return {
        "name": name,
        "description": "sector-as-LocationNodeGroup test mapping",
        "version": "1.6.0",
        "table_settings": {
            "format_type": "sqlite",
            "table_name": "us_table",
            "node_name_template": "{sito}.{settore}.{unita_tipo}.{us}",
        },
        "column_mappings": {
            "sito": {"is_filter": True, "filter_required": True},
            "area": {"is_filter": True, "filter_required": False},
            "unita_tipo": {"is_filter": True, "filter_required": False},
            "us": {"is_id": True, "node_type": "US"},
            "d_stratigrafica": {"is_description": True},
            "settore": {
                "node_type": "LocationNodeGroup",
                "location_kind": "study",
                "display_name": "Sector",
                "description": "Excavation sector",
            },
        },
        "relations": [],
    }


def _locations(graph):
    return [
        n for n in graph.nodes
        if getattr(n, "node_type", None) == "LocationNodeGroup"
    ]


def _is_in_location_edges(graph):
    return [
        e for e in graph.edges
        if getattr(e, "edge_type", None) == "is_in_location"
    ]


def test_shared_sector_is_a_single_node(tmp_path):
    """3 US in sector '1' -> exactly 1 LocationNodeGroup + 3 is_in_location edges."""
    rows = [
        (101, "GT16", "A", "USM", "1", "wall"),
        (102, "GT16", "A", "US", "1", "layer"),
        (103, "GT16", "A", "US", "1", "cut"),
    ]
    payload = _mapping("test_loc_shared")
    db, name, mdir = _write_fixture(tmp_path, rows, payload, "test_loc_shared")
    try:
        importer = PyArchInitImporter(filepath=db, mapping_name=name)
        graph = importer.parse()

        locs = _locations(graph)
        assert len(locs) == 1, f"expected 1 location node, got {len(locs)}"
        assert locs[0].name == "1"
        assert getattr(locs[0], "kind", None) == "study"

        edges = _is_in_location_edges(graph)
        assert len(edges) == 3, f"expected 3 is_in_location edges, got {len(edges)}"
        # every edge points at the single shared sector node
        assert {e.edge_target for e in edges} == {locs[0].node_id}
    finally:
        _cleanup_mapping_dir(mdir)


def test_distinct_sectors_are_distinct_nodes(tmp_path):
    """US in sectors '1' and '2' -> 2 LocationNodeGroup nodes, 2 edges."""
    rows = [
        (201, "GT16", "A", "US", "1", "layer"),
        (202, "GT16", "A", "US", "2", "layer"),
    ]
    payload = _mapping("test_loc_distinct")
    db, name, mdir = _write_fixture(tmp_path, rows, payload, "test_loc_distinct")
    try:
        importer = PyArchInitImporter(filepath=db, mapping_name=name)
        graph = importer.parse()
        assert sorted(n.name for n in _locations(graph)) == ["1", "2"]
        assert len(_is_in_location_edges(graph)) == 2
    finally:
        _cleanup_mapping_dir(mdir)


def test_empty_sector_creates_no_location(tmp_path):
    """Blank / None sector -> no LocationNodeGroup and no edge for that US."""
    rows = [
        (301, "GT16", "A", "US", "", "layer"),
        (302, "GT16", "A", "US", None, "layer"),
    ]
    payload = _mapping("test_loc_empty")
    db, name, mdir = _write_fixture(tmp_path, rows, payload, "test_loc_empty")
    try:
        importer = PyArchInitImporter(filepath=db, mapping_name=name)
        graph = importer.parse()
        assert _locations(graph) == []
        assert _is_in_location_edges(graph) == []
    finally:
        _cleanup_mapping_dir(mdir)
