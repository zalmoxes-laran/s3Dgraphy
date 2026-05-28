"""PostgreSQL-backend round-trip tests for PyArchInitImporter (#9).

Gated by the ``PYTEST_PG_DSN`` env var: when unset, the entire module
is skipped, so the default test run stays SQLite-only (matching how
the s3dgraphy core dependencies stay minimal).

To opt in locally::

    docker compose -f tests/fixtures/postgres/docker-compose.yml up -d
    export PYTEST_PG_DSN="postgresql://s3dgraphy@127.0.0.1:55432/s3dgraphy_test"
    pip install s3dgraphy[postgres]
    pytest tests/test_pg_importer.py -v

The 6 tests below mirror tests/test_filtered_import.py — same data,
same expectations — but build the fixture in PostgreSQL via psycopg2
and run the importer through the ``connection_url=`` kwarg. This pins
that the dialect-switch helpers (``_qmark``, ``_connect``) and the
WHERE-clause placeholder rewrite produce identical results on both
backends.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Make the in-repo src/ importable without requiring an editable install.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

# PG availability gate. The round-trip tests need both:
#   1. PYTEST_PG_DSN env var pointing to a writable PG (see
#      tests/fixtures/postgres/docker-compose.yml for a local one).
#   2. psycopg2 installed (via the [postgres] extra).
# The API-guard tests (mutual exclusion, neither, unsupported scheme)
# don't need PG and run unconditionally.
_PG_DSN = os.environ.get("PYTEST_PG_DSN")
try:
    import psycopg2  # noqa: F401
    _PSYCOPG2_OK = True
except ImportError:  # pragma: no cover
    _PSYCOPG2_OK = False

pg_required = pytest.mark.skipif(
    not (_PG_DSN and _PSYCOPG2_OK),
    reason=("PG round-trip tests need PYTEST_PG_DSN + psycopg2. "
            "Install via: pip install s3dgraphy[postgres]"),
)

from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter  # noqa: E402
from s3dgraphy.mappings.registry import mapping_registry  # noqa: E402


# Same data shape as tests/test_filtered_import.py.
_FIXTURE_ROWS = {
    "Pompei":   [(1001, "A", "Pompei foundation layer"),
                 (1002, "B", "Pompei collapse layer")],
    "Ercolano": [(2001, "A", "Ercolano floor surface"),
                 (2002, "B", "Ercolano destruction deposit")],
    "Stabia":   [(3001, "A", "Stabia mosaic substrate"),
                 (3002, "B", "Stabia drainage fill")],
}


@pytest.fixture
def pg_filtered_setup(tmp_path):
    """Create a us_table in the configured PG, populate it, register a
    mapping JSON, and yield (connection_url, mapping_name). The table
    is dropped on teardown so consecutive runs stay clean.
    """
    import psycopg2  # gated above
    conn = psycopg2.connect(_PG_DSN)
    conn.autocommit = True
    cur = conn.cursor()
    # Use a fresh schema-less table; DROP CASCADE keeps teardown
    # robust even if a previous run aborted.
    cur.execute("DROP TABLE IF EXISTS us_table CASCADE")
    cur.execute(
        """
        CREATE TABLE us_table (
            us              INTEGER PRIMARY KEY,
            sito            TEXT NOT NULL,
            area            TEXT NOT NULL,
            d_stratigrafica TEXT
        )
        """
    )
    for site, rows in _FIXTURE_ROWS.items():
        for us_num, area, desc in rows:
            cur.execute(
                "INSERT INTO us_table (us, sito, area, d_stratigrafica) "
                "VALUES (%s, %s, %s, %s)",
                (us_num, site, area, desc),
            )
    cur.close()
    conn.close()

    # Mapping JSON — identical to the SQLite test, just renamed so the
    # two test suites can't collide if registered concurrently.
    mapping_dir = tmp_path / "mappings"
    mapping_dir.mkdir()
    mapping_name = "test_pg_filter_mapping"
    mapping_payload = {
        "name": "PG filter test mapping",
        "description": "Mapping used by tests/test_pg_importer.py",
        "version": "1.0",
        "table_settings": {
            # format_type is informational; the dialect is derived
            # from the connection URL at runtime.
            "format_type": "postgres",
            "table_name": "us_table",
        },
        "column_mappings": {
            "sito": {"is_filter": True, "filter_required": True,
                     "display_name": "Site", "description": "Site name"},
            "area": {"is_filter": True, "filter_required": False,
                     "display_name": "Area",
                     "description": "Excavation area"},
            "us":   {"is_id": True, "node_type": "US"},
            "d_stratigrafica": {"is_description": True},
        },
        "relations": [],
    }
    (mapping_dir / f"{mapping_name}.json").write_text(
        json.dumps(mapping_payload), encoding="utf-8"
    )
    mapping_registry.add_mapping_directory(
        "pyarchinit", str(mapping_dir), priority="high"
    )

    yield _PG_DSN, mapping_name

    # Teardown.
    dirs = mapping_registry._mapping_directories.get("pyarchinit", [])
    try:
        dirs.remove(str(mapping_dir))
    except ValueError:
        pass
    conn = psycopg2.connect(_PG_DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS us_table CASCADE")
    cur.close()
    conn.close()


# ---------------------------------------------------------------------------
# Round-trip tests (mirror the SQLite-side test_filtered_import.py)
# ---------------------------------------------------------------------------

@pg_required
def test_pg_no_filters_imports_all_rows(pg_filtered_setup):
    dsn, mapping_name = pg_filtered_setup
    importer = PyArchInitImporter(
        connection_url=dsn, mapping_name=mapping_name, filters=None,
    )
    graph = importer.parse()
    us_nodes = [n for n in graph.nodes
                if getattr(n, "node_type", None) == "US"]
    assert len(us_nodes) == 6


@pg_required
def test_pg_single_filter(pg_filtered_setup):
    dsn, mapping_name = pg_filtered_setup
    importer = PyArchInitImporter(
        connection_url=dsn,
        mapping_name=mapping_name,
        filters={"sito": "Pompei"},
    )
    graph = importer.parse()
    us_nodes = [n for n in graph.nodes
                if getattr(n, "node_type", None) == "US"]
    names = sorted(n.name for n in us_nodes)
    assert names == ["1001", "1002"]


@pg_required
def test_pg_and_filter(pg_filtered_setup):
    dsn, mapping_name = pg_filtered_setup
    importer = PyArchInitImporter(
        connection_url=dsn,
        mapping_name=mapping_name,
        filters={"sito": "Pompei", "area": "A"},
    )
    graph = importer.parse()
    us_nodes = [n for n in graph.nodes
                if getattr(n, "node_type", None) == "US"]
    names = sorted(n.name for n in us_nodes)
    assert names == ["1001"]


@pg_required
def test_pg_get_distinct_values(pg_filtered_setup):
    dsn, mapping_name = pg_filtered_setup
    importer = PyArchInitImporter(
        connection_url=dsn, mapping_name=mapping_name,
    )
    values = importer.get_distinct_values("sito")
    # PG ORDER BY uses the default collation; the alphabetic ordering
    # of these three names is stable across both backends.
    assert values == ["Ercolano", "Pompei", "Stabia"]


@pg_required
def test_pg_filter_column_whitelist(pg_filtered_setup):
    dsn, mapping_name = pg_filtered_setup
    importer = PyArchInitImporter(
        connection_url=dsn,
        mapping_name=mapping_name,
        filters={"definitely_not_in_mapping": "x"},
    )
    with pytest.raises((ValueError, ImportError),
                       match="not declared in column_mappings"):
        importer.parse()


# ---------------------------------------------------------------------------
# API guards (don't need PG to run, but live here for cohesion — they're
# also gated by the module-level skip so they'll only fire when PG mode
# is intentionally enabled).
# ---------------------------------------------------------------------------

def test_filepath_and_connection_url_are_mutually_exclusive(tmp_path):
    """Passing both raises ValueError before any connection is opened."""
    fake_sqlite = tmp_path / "x.sqlite"
    fake_sqlite.touch()
    with pytest.raises(ValueError, match="not both"):
        PyArchInitImporter(
            filepath=str(fake_sqlite),
            connection_url="postgresql://u:p@h/db",
            mapping_name="ignored",
        )


def test_neither_filepath_nor_connection_url_raises():
    """Calling with neither raises a friendly ValueError."""
    with pytest.raises(ValueError, match="required"):
        PyArchInitImporter(mapping_name="ignored")


def test_unsupported_url_scheme_raises():
    """Schemes outside sqlite/postgres are rejected up front."""
    with pytest.raises(ValueError, match="Unsupported connection_url"):
        PyArchInitImporter(
            connection_url="mysql://u:p@h/db", mapping_name="ignored",
        )
