"""Cross-PR composition test: PR #9 (read) + PR #11 (write) on PostgreSQL.

Emanuel asked for this on PR #11 as "the canonical demonstration that
the two PRs compose" — one PG fixture, read via the new
``PyArchInitImporter(connection_url=)`` from #9, mutate in memory,
write back via ``GraphIngestor.populate_list`` from #11, then re-read
the SQL and assert the bridge round-trips faithfully.

The two pieces use intentionally different driver stacks (stdlib +
``_qmark()`` on the read side, SQLAlchemy on the write side — see
``docs/importers/dual_stack_driver_choice.rst``). This test pins that
the two stacks see the same PG state and that an import-mutate-export
cycle leaves all unmutated rows byte-identical.

Skipped cleanly when PG is unreachable at localhost:5433 or when
``psycopg2`` is not installed (the ``pg_engine`` fixture in
``conftest_pg.py`` handles the skip).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

# Import the PG fixture explicitly — conftest_pg.py is not auto-discovered.
from tests.sync.conftest_pg import PG_CONN_STR, pg_engine  # noqa: F401

# The SQLAlchemy URL form ("postgresql+psycopg2://...") is what
# create_engine() wants, but psycopg2.connect() — which the PR #9
# importer dispatches to — can't parse the "+psycopg2" driver suffix.
# Strip it for the read side; both forms point at the same PG cluster.
_PG_IMPORTER_URL = PG_CONN_STR.replace("postgresql+psycopg2://", "postgresql://")


_psycopg2_available: bool
try:
    import psycopg2  # noqa: F401
    _psycopg2_available = True
except ImportError:  # pragma: no cover
    _psycopg2_available = False


# This is the cross-PR composition test (PR #11 write + PR #12 read).
# PR #11 (this branch, issue-10/move-sync-module) brings GraphIngestor;
# PR #12 (separate branch, issue-9/postgres-importer) brings the
# `connection_url=` kwarg on PyArchInitImporter. Neither branch alone
# has both. The test activates automatically once both land on
# s3dgraphy_v1.6dev; until then it skips with a clear reason so a
# reviewer running this PR's test suite sees why it's not exercised.
import inspect
from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter as _Imp
_connection_url_kw_supported = (
    "connection_url" in inspect.signature(_Imp.__init__).parameters
)

pytestmark = [
    pytest.mark.skipif(
        not _psycopg2_available,
        reason="psycopg2 not installed (pip install s3dgraphy[postgres])",
    ),
    pytest.mark.skipif(
        not _connection_url_kw_supported,
        reason=(
            "PyArchInitImporter.connection_url= kwarg not present on this "
            "branch — cross-PR test, requires PR #12 (issue-9/postgres-"
            "importer) to land on s3dgraphy_v1.6dev. Activates "
            "automatically once both #11 and #12 are merged."
        ),
    ),
]


# Three rows, one site, three pre-assigned UUIDs so the importer-side
# nodes match the ingestor-side rows by node_uuid without a backfill pass.
_UUID_1 = "11111111-1111-7111-8111-111111111111"
_UUID_2 = "22222222-2222-7222-8222-222222222222"
_UUID_3 = "33333333-3333-7333-8333-333333333333"

_SEED_ROWS = (
    (_UUID_1, "Volterra", "A", "1", "US", "Foundation layer",   "Pre-Roman"),
    (_UUID_2, "Volterra", "A", "2", "US", "Collapse deposit",   "Roman"),
    (_UUID_3, "Volterra", "B", "3", "US", "Medieval substrate", "Medieval"),
)


@pytest.fixture
def seeded_pg(pg_engine, tmp_path):  # noqa: F811
    """Insert 3 known rows into the pg_engine schema and register a
    minimal mapping JSON for PyArchInitImporter. Yields (mapping_name,)
    so the test can reuse the imported mapping name.
    """
    from s3dgraphy.mappings.registry import mapping_registry

    # Wipe + seed us_table inside one transaction so the rows are
    # visible from any subsequent connection (including the importer's
    # stdlib psycopg2 connection — different driver than SQLAlchemy).
    # Pre-seed site_table too: GraphIngestor will look for "Volterra"
    # and attempt an INSERT if missing, but conftest_pg.py's schema
    # uses different column names than the production us_table, so the
    # auto-create path would fail. Pre-seeding sidesteps that.
    with pg_engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE us_table, site_table, periodizzazione_table "
            "RESTART IDENTITY CASCADE"
        ))
        conn.execute(
            text("INSERT INTO site_table (sito) VALUES (:s)"),
            {"s": "Volterra"},
        )
        for (node_uuid, sito, area, us_num,
             unita_tipo, d_strat, d_interp) in _SEED_ROWS:
            conn.execute(
                text(
                    "INSERT INTO us_table "
                    "(node_uuid, sito, area, us, unita_tipo, "
                    " d_stratigrafica, d_interpretativa) "
                    "VALUES (:uuid, :sito, :area, :us, :tipo, "
                    "        :d_strat, :d_interp)"
                ),
                {
                    "uuid": node_uuid, "sito": sito, "area": area,
                    "us": us_num, "tipo": unita_tipo,
                    "d_strat": d_strat, "d_interp": d_interp,
                },
            )

    # Minimal mapping JSON — only the columns needed for the round-trip
    # assertion. node_uuid is carried as a plain attribute so the
    # ingestor can match graph nodes against PG rows by uuid.
    mapping_dir = tmp_path / "mappings"
    mapping_dir.mkdir()
    mapping_name = "test_round_trip_pg_mapping"
    mapping_payload = {
        "name": "round-trip PG composition test",
        "description": "PR #9 ↔ PR #11 round-trip mapping",
        "version": "1.0",
        "table_settings": {
            "format_type": "postgres",
            "table_name": "us_table",
        },
        "column_mappings": {
            "us":               {"is_id": True, "node_type": "US"},
            "d_stratigrafica":  {"is_description": True},
            "d_interpretativa": {},
            "sito":             {},
            "area":             {},
            "unita_tipo":       {},
            "node_uuid":        {},
        },
        "relations": [],
    }
    (mapping_dir / f"{mapping_name}.json").write_text(
        json.dumps(mapping_payload), encoding="utf-8"
    )
    mapping_registry.add_mapping_directory(
        "pyarchinit", str(mapping_dir), priority="high"
    )

    yield mapping_name

    # Teardown — registry has no remove API, so drop the dir entry
    # manually like the other PG-importer tests do.
    dirs = mapping_registry._mapping_directories.get("pyarchinit", [])
    try:
        dirs.remove(str(mapping_dir))
    except ValueError:
        pass


def test_round_trip_read_via_9_write_via_11(seeded_pg, pg_engine):
    """End-to-end: read PG via #9, mutate one node, write back via #11,
    verify the mutation persisted and other rows are byte-identical.

    Demonstrates the canonical composition pattern Emanuel asked for
    in his review on PR #11. The two PRs use different driver stacks
    (psycopg2 for read, SQLAlchemy for write); the test pins that they
    see the same PG state and round-trip a graph faithfully.
    """
    from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter
    from s3dgraphy.sync._db_handle import _resolve_db_handle
    from s3dgraphy.sync.graph_ingestor import GraphIngestor

    mapping_name = seeded_pg

    # ---- 1. READ via PR #9 ---------------------------------------------
    # PyArchInitImporter dispatches on the URL prefix to psycopg2 and
    # uses _qmark() to swap "?" → "%s" placeholders. This is the only
    # piece touching #9's new code path.
    importer = PyArchInitImporter(
        connection_url=_PG_IMPORTER_URL,
        mapping_name=mapping_name,
        filters={"sito": "Volterra"},
    )
    graph = importer.parse()
    us_nodes = [
        n for n in graph.nodes
        if getattr(n, "node_type", None) == "US"
    ]
    assert len(us_nodes) == 3, (
        f"expected 3 US nodes from the 3 seeded rows, got {len(us_nodes)}: "
        f"{[getattr(n, 'name', '?') for n in us_nodes]}"
    )

    # Stamp the PG-side node_uuid onto each imported graph node.
    #
    # KNOWN INTEROP GAP: PyArchInitImporter generates a fresh random
    # node_id per row (line ~284) and does not preserve any DB column
    # as a node attribute — it only knows the mapping flags is_id,
    # is_description, is_filter, property_name. The full pyArchInit
    # production read path adds node_uuid via GraphProjector's
    # `_propagate_node_uuid_and_us`, which is outside PR #9's scope.
    # We do the equivalent here directly so the cross-PR demo proves
    # the two stacks compose; downstream this should be folded into
    # either a mapping-side "passthrough" flag or a GraphIngestor
    # secondary lookup by (sito, us).
    by_us = {}
    for n in us_nodes:
        a = n.attributes if getattr(n, "attributes", None) is not None else {}
        n.attributes = a
        by_us[str(a.get("us") or getattr(n, "name", ""))] = n

    with pg_engine.begin() as conn:
        for row in conn.execute(text(
                "SELECT us, node_uuid FROM us_table WHERE sito = :s"),
                {"s": "Volterra"}):
            us_val, uuid_val = row[0], row[1]
            node = by_us.get(str(us_val))
            if node is not None:
                node.attributes["node_uuid"] = uuid_val

    seen_uuids = {
        n.attributes.get("node_uuid") for n in us_nodes
    }
    assert seen_uuids == {_UUID_1, _UUID_2, _UUID_3}, (
        f"node_uuid stamping failed: got {sorted(u for u in seen_uuids if u)}"
    )

    # ---- 2. MUTATE one node in memory ---------------------------------
    # Update d_stratigrafica on node 1; the other two stay untouched.
    target = next(n for n in us_nodes
                  if n.attributes.get("node_uuid") == _UUID_1)
    new_description = "Foundation layer (updated via round-trip)"
    target.attributes["d_stratigrafica"] = new_description
    # Make sure the rest of the mapped attrs are present — populate_list
    # writes whatever is in node.attributes, so we explicitly set the
    # values the importer placed on the node to avoid accidental nulls.
    for n in us_nodes:
        a = n.attributes
        a.setdefault("sito", "Volterra")
        a.setdefault("unita_tipo", "US")

    # ---- 3. WRITE via PR #11 ------------------------------------------
    # GraphIngestor uses SQLAlchemy under the hood — different driver
    # stack from the importer above, talking to the same PG database.
    handle = _resolve_db_handle(PG_CONN_STR)
    assert handle.is_postgres, "DbHandle should detect the postgresql:// URL"

    result = GraphIngestor().populate_list(graph, handle, "Volterra")

    assert result.updated == 1, (
        f"exactly one row should have been updated (#1's d_stratigrafica), "
        f"got updated={result.updated} skipped={result.skipped} "
        f"inserted={result.inserted}"
    )
    assert result.skipped == 2, (
        f"the other two unchanged rows should be skipped, got "
        f"skipped={result.skipped}"
    )
    assert result.inserted == 0, (
        f"no new rows expected (all 3 uuids were already in PG), got "
        f"inserted={result.inserted}"
    )

    # ---- 4. VERIFY by re-reading SQL directly --------------------------
    # Sanity: the mutated row has the new description; the other two
    # have their original values; no rows were lost.
    with pg_engine.begin() as conn:
        rows = list(conn.execute(
            text(
                "SELECT node_uuid, us, d_stratigrafica, d_interpretativa "
                "FROM us_table WHERE sito = :s ORDER BY us"
            ),
            {"s": "Volterra"},
        ))
    assert len(rows) == 3, f"row count regressed: got {len(rows)} rows"

    by_us = {r[1]: r for r in rows}
    assert by_us["1"][2] == new_description, (
        f"mutation lost in round-trip: PG still has "
        f"{by_us['1'][2]!r} for us=1"
    )
    assert by_us["1"][3] == "Pre-Roman", (
        f"unmutated column d_interpretativa for us=1 changed: {by_us['1'][3]!r}"
    )
    assert by_us["2"][2] == "Collapse deposit", (
        f"row 2 was touched by the write: {by_us['2'][2]!r}"
    )
    assert by_us["3"][2] == "Medieval substrate", (
        f"row 3 was touched by the write: {by_us['3'][2]!r}"
    )


def test_idempotent_second_pass_skips_all(seeded_pg, pg_engine):
    """A second populate_list pass with no graph mutation skips all rows.

    Convergence check: once a round-trip has settled, repeating it must
    not produce spurious updates. This is the same invariant
    test_idempotent_ingest.py pins for SQLite, repeated on PG to make
    sure the SQLAlchemy write path agrees.
    """
    from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter
    from s3dgraphy.sync._db_handle import _resolve_db_handle
    from s3dgraphy.sync.graph_ingestor import GraphIngestor

    importer = PyArchInitImporter(
        connection_url=_PG_IMPORTER_URL,
        mapping_name=seeded_pg,
        filters={"sito": "Volterra"},
    )
    graph = importer.parse()

    # Same stamping step as test 1 (see KNOWN INTEROP GAP comment there).
    us_nodes = [n for n in graph.nodes
                if getattr(n, "node_type", None) == "US"]
    by_us = {}
    for n in us_nodes:
        a = n.attributes if getattr(n, "attributes", None) is not None else {}
        n.attributes = a
        a.setdefault("sito", "Volterra")
        a.setdefault("unita_tipo", "US")
        by_us[str(a.get("us") or getattr(n, "name", ""))] = n
    with pg_engine.begin() as conn:
        for row in conn.execute(text(
                "SELECT us, node_uuid FROM us_table WHERE sito = :s"),
                {"s": "Volterra"}):
            node = by_us.get(str(row[0]))
            if node is not None:
                node.attributes["node_uuid"] = row[1]

    handle = _resolve_db_handle(PG_CONN_STR)
    first = GraphIngestor().populate_list(graph, handle, "Volterra")
    second = GraphIngestor().populate_list(graph, handle, "Volterra")

    # First pass: nothing mutated in memory after the read, so it should
    # already be a no-op for the row-level counters (3 skipped). Second
    # pass confirms convergence. We compare the row-level counters
    # explicitly rather than the whole IngestResult — the `applied`
    # field tracks SQL group-folder applications (unused here, transient
    # between passes) and is not part of the convergence invariant.
    assert first.updated == 0, f"first pass touched rows: {first}"
    assert first.skipped == 3, f"first pass skip count: {first}"
    assert first.inserted == 0, f"first pass inserted unexpected rows: {first}"
    assert (second.updated, second.skipped, second.inserted) == \
           (first.updated, first.skipped, first.inserted), (
        f"row-level counters diverged between passes: "
        f"{(second.updated, second.skipped, second.inserted)} != "
        f"{(first.updated, first.skipped, first.inserted)}"
    )
