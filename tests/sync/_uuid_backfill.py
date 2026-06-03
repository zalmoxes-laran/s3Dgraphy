"""Test-only helper: node_uuid backfill (ported from pyArchInit).

In pyArchInit the equivalent lives in
``scripts/migrations/_2026_05_node_uuid_backfill_lib.py`` and is a
production migration utility. The s3dgraphy sync package only needs
the same logic during tests, so we keep a focused copy here rather
than promoting the whole migration to the library.

Both ``add_columns`` and ``backfill_uuids`` are idempotent and work
across SQLite and PostgreSQL via the ``DbHandle`` shim.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

from sqlalchemy import inspect, text

from s3dgraphy.sync._db_handle import (
    DbHandle, _columns_of, _resolve_db_handle,
)
from s3dgraphy.sync.uuid7 import uuid7


#: Tables that need a stable node identity for the s3dgraphy bridge.
TABLES: tuple[str, ...] = (
    "us_table",
    "inventario_materiali_table",
    "periodizzazione_table",
)

#: Canonical primary key column per target table; used by ``backfill_uuids``
#: to auto-add a missing PRIMARY KEY on legacy PG dumps.
_CANONICAL_PK: dict[str, str] = {
    "us_table": "id_us",
    "inventario_materiali_table": "id_invmat",
    "periodizzazione_table": "id_perfas",
}

DbInput = Union[DbHandle, Path]


def add_columns(db: DbInput) -> None:
    """Add ``node_uuid TEXT`` + partial unique index on each target table.

    Idempotent. Atomic on PG (DDL transactional); on SQLite a crash
    mid-loop may leave some columns added.
    """
    handle = _resolve_db_handle(db)
    with handle.engine.begin() as conn:
        for table in TABLES:
            cols = _columns_of(handle.engine, table)
            if "node_uuid" not in cols:
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN node_uuid TEXT")
                )
            conn.execute(text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS "
                f"ix_{table}_node_uuid ON {table}(node_uuid) "
                f"WHERE node_uuid IS NOT NULL"
            ))


def backfill_uuids(db: DbInput) -> dict[str, int]:
    """Assign ``uuid7()`` to every NULL ``node_uuid``; return per-table counts.

    Idempotent: second invocation returns ``{table: 0, ...}``. Atomic via
    SQLAlchemy ``engine.begin()``.
    """
    handle = _resolve_db_handle(db)
    counts: dict[str, int] = {}
    inspector = inspect(handle.engine)
    with handle.engine.begin() as conn:
        for table in TABLES:
            pks = inspector.get_pk_constraint(table)["constrained_columns"]
            if pks:
                pk_col = pks[0]
            elif handle.is_postgres:
                pk_col = _CANONICAL_PK.get(table)
                if pk_col is None or pk_col not in _columns_of(
                        handle.engine, table):
                    raise RuntimeError(
                        f"{table}: no primary key declared on PostgreSQL "
                        f"and no canonical id column found — cannot "
                        f"backfill safely"
                    )
                dupes = conn.execute(
                    text(f"SELECT {pk_col} FROM {table} "
                         f"GROUP BY {pk_col} HAVING COUNT(*) > 1 "
                         f"ORDER BY {pk_col} LIMIT 5")
                ).fetchall()
                if dupes:
                    sample = ", ".join(str(r[0]) for r in dupes)
                    raise RuntimeError(
                        f"{table}: column {pk_col} has duplicate values "
                        f"(sample: {sample}) — cannot auto-add PRIMARY "
                        f"KEY. Resolve duplicates manually then re-run."
                    )
                conn.execute(text(
                    f"ALTER TABLE {table} ADD CONSTRAINT "
                    f"{table}_pkey PRIMARY KEY ({pk_col})"
                ))
            else:
                pk_col = "rowid"
            rows = conn.execute(
                text(f"SELECT {pk_col} FROM {table} WHERE node_uuid IS NULL")
            ).fetchall()
            for (row_id,) in rows:
                conn.execute(
                    text(f"UPDATE {table} SET node_uuid = :uuid "
                         f"WHERE {pk_col} = :id"),
                    {"uuid": str(uuid7()), "id": row_id},
                )
            counts[table] = len(rows)
    return counts
