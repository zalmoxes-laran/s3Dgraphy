"""Public API for the s3dgraphy ↔ host-application SQL sync layer.

This package was moved from pyArchInit (issue #10) and provides a
backend-agnostic (SQLite + PostgreSQL via SQLAlchemy) bridge between
s3dgraphy Graph objects and the host application's relational tables.

Originally lived inside pyArchInit at
``modules/s3dgraphy/sync/``. Moved into the s3dgraphy package proper
in 1.6.0 after a Qt/QGIS decoupling pass — see
zalmoxes-laran/s3Dgraphy#10 for the design discussion.

Public surface
==============

Vocabulary (Phase 1):
    VocabProviderCore, vocab dataclasses (EdgeType, Family,
    ParadataType, UnitType, VisualRule, VocabularyVersion)

DB handle (PG-Compat Foundation):
    DbHandle + exception hierarchy

Ingestion (GraphIngestor, the s3dgraphy ↔ SQL writer):
    GraphIngestor, IngestResult, ConflictRecord, ConflictResolution
    ConflictResolver
    YedOverrideResult, register_yed_override_hook,
    clear_yed_override_hook (Qt/GUI hook — host registers, library
    never imports Qt itself)

Projection (Graph ← SQL):
    GraphProjector, GroupProjector

Errors:
    GraphSyncError, GraphIngestError, CycleDetectedError,
    SchemaMismatchError, UnknownUnitaTipoError, SiteMismatchError,
    MissingEpochError

Dependency note
---------------
This subpackage requires SQLAlchemy 2.x. Install via the [sync]
extras::

    pip install s3dgraphy[sync]              # SQLite-only ingestion
    pip install s3dgraphy[sync,postgres]     # + Postgres backend

A friendly ``ImportError`` is raised on first use if SQLAlchemy is
missing.
"""
from __future__ import annotations

# Lazy SQLAlchemy probe with a friendly error — happens on package
# import; users who don't touch s3dgraphy.sync pay nothing.
try:
    import sqlalchemy as _sa  # noqa: F401
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "s3dgraphy.sync requires SQLAlchemy. Install via:\n"
        "    pip install s3dgraphy[sync]\n"
        "(add [postgres] extra for the PostgreSQL backend)"
    ) from _e

from ._db_handle import (
    DbHandle,
    DbHandleError,
    PgConnectionError,
    UnsupportedBackendError,
)
from .conflict_resolver import ConflictResolver
from .graph_ingestor import (
    CycleDetectedError,
    GraphIngestError,
    GraphIngestor,
    GraphSyncError,
    MissingEpochError,
    SchemaMismatchError,
    SiteMismatchError,
    UnknownUnitaTipoError,
    YedOverrideResult,
    clear_yed_override_hook,
    register_yed_override_hook,
)
from .graph_projector import GraphProjector
from .ingest_result import ConflictRecord, ConflictResolution, IngestResult
from .vocab_provider_core import VocabProviderCore
from .vocab_types import (
    EdgeType,
    Family,
    ParadataType,
    UnitType,
    VisualRule,
    VocabularyVersion,
)

__all__ = [
    # Vocabulary
    "VocabProviderCore",
    "EdgeType",
    "Family",
    "ParadataType",
    "UnitType",
    "VisualRule",
    "VocabularyVersion",
    # DB handle
    "DbHandle",
    "DbHandleError",
    "PgConnectionError",
    "UnsupportedBackendError",
    # Ingestion
    "GraphIngestor",
    "IngestResult",
    "ConflictRecord",
    "ConflictResolution",
    "ConflictResolver",
    # yEd override hook
    "YedOverrideResult",
    "register_yed_override_hook",
    "clear_yed_override_hook",
    # Projection
    "GraphProjector",
    # Errors
    "GraphSyncError",
    "GraphIngestError",
    "CycleDetectedError",
    "SchemaMismatchError",
    "UnknownUnitaTipoError",
    "SiteMismatchError",
    "MissingEpochError",
]
