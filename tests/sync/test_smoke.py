"""L0 smoke tests for the freshly-moved s3dgraphy.sync package.

These don't exercise full ingestion or round-trip — they just prove
the package imports cleanly, the public surface is intact, and the
core constructors / hook API are wired up.

The full L1/L2 test migration from pyArchInit's
``tests/sync/`` follows in a separate commit on this same PR.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_public_surface_imports():
    """The 18 symbols promised by s3dgraphy.sync.__all__ are importable."""
    from s3dgraphy import sync

    expected = {
        # Vocabulary
        "VocabProviderCore",
        "EdgeType", "Family", "ParadataType", "UnitType",
        "VisualRule", "VocabularyVersion",
        # DB handle
        "DbHandle", "DbHandleError",
        "PgConnectionError", "UnsupportedBackendError",
        # Ingestion
        "GraphIngestor", "IngestResult",
        "ConflictRecord", "ConflictResolution", "ConflictResolver",
        # yEd override hook
        "YedOverrideResult",
        "register_yed_override_hook", "clear_yed_override_hook",
        # Projection
        "GraphProjector",
        # Errors
        "GraphSyncError", "GraphIngestError", "CycleDetectedError",
        "SchemaMismatchError", "UnknownUnitaTipoError",
        "SiteMismatchError", "MissingEpochError",
    }
    actual = set(sync.__all__)
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"Missing from __all__: {missing}"
    assert not extra, f"Unexpected in __all__: {extra}"

    # And each is actually accessible.
    for name in expected:
        assert hasattr(sync, name), f"{name} not accessible on package"


def test_graph_ingestor_constructs():
    """GraphIngestor() works with the default ConflictResolver."""
    from s3dgraphy.sync import GraphIngestor

    ingestor = GraphIngestor()
    assert ingestor is not None
    # The resolver attribute is internal but its presence is part of
    # the wired contract.
    assert hasattr(ingestor, "_resolver")


def test_db_handle_from_sqlite_path(tmp_path: Path):
    """DbHandle.from_path() wraps a SQLite file in a SQLAlchemy handle."""
    from s3dgraphy.sync import DbHandle

    db = tmp_path / "smoke.sqlite"
    handle = DbHandle.from_path(db)
    assert handle is not None
    assert handle.sqlite_path == db
    assert handle.is_postgres is False
    # The engine is lazily built but accessible on demand.
    assert handle.engine is not None


def test_yed_override_hook_register_clear_cycle():
    """register / clear yEd override hook is symmetric + idempotent."""
    from s3dgraphy.sync import (
        YedOverrideResult,
        clear_yed_override_hook,
        register_yed_override_hook,
    )
    from s3dgraphy.sync import graph_ingestor as gi_mod

    # Start clean.
    clear_yed_override_hook()
    assert gi_mod._yed_override_hook is None

    def _noop(*a, **kw):
        return YedOverrideResult()

    register_yed_override_hook(_noop)
    assert gi_mod._yed_override_hook is _noop

    clear_yed_override_hook()
    assert gi_mod._yed_override_hook is None

    # Double-clear must not raise.
    clear_yed_override_hook()
    assert gi_mod._yed_override_hook is None


def test_sync_module_has_no_qt_imports():
    """Belt-and-braces: no s3dgraphy.sync source file may import qgis
    or PyQt — this is the entire point of issue #10."""
    import s3dgraphy.sync as sync_pkg

    pkg_dir = Path(sync_pkg.__file__).parent
    for py in pkg_dir.glob("*.py"):
        text = py.read_text()
        # Catch both `from qgis...` and `import qgis...`, in any indent.
        for line in text.splitlines():
            stripped = line.lstrip()
            assert not stripped.startswith(("from qgis", "import qgis")), (
                f"{py.name}: qgis import on line: {line!r}"
            )
            assert not stripped.startswith(("from PyQt", "import PyQt")), (
                f"{py.name}: PyQt import on line: {line!r}"
            )
