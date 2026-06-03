"""Shared pytest fixtures for tests/sync/.

The L1/L2 sync test suite was migrated from pyArchInit's
``tests/sync/`` in issue #10. The original conftest prepended
``ext_libs/`` to ``sys.path`` so it would test the vendored s3dgraphy
copy. That bootstrap is no longer needed here: s3dgraphy IS the
package under test, and we rely on the standard ``pip install -e .``
to put it on the path.

Fixtures preserved verbatim from the upstream conftest:
``node_datamodel_path``, ``connections_datamodel_path``,
``visual_rules_path``, ``vocab_dir``, ``overrides_dir``.
"""
from __future__ import annotations

from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def node_datamodel_path() -> Path:
    return FIXTURES / "node_datamodel_sample.json"


@pytest.fixture
def connections_datamodel_path() -> Path:
    return FIXTURES / "connections_datamodel_sample.json"


@pytest.fixture
def visual_rules_path() -> Path:
    return FIXTURES / "em_visual_rules_sample.json"


@pytest.fixture
def vocab_dir(tmp_path: Path,
              node_datamodel_path: Path,
              connections_datamodel_path: Path,
              visual_rules_path: Path) -> Path:
    """Create an isolated JSON_config/ directory holding sample fixtures."""
    out = tmp_path / "JSON_config"
    out.mkdir()
    (out / "s3Dgraphy_node_datamodel.json").write_bytes(node_datamodel_path.read_bytes())
    (out / "s3Dgraphy_connections_datamodel.json").write_bytes(connections_datamodel_path.read_bytes())
    (out / "em_visual_rules.json").write_bytes(visual_rules_path.read_bytes())
    return out


@pytest.fixture
def overrides_dir(tmp_path: Path) -> Path:
    out = tmp_path / "vocab_overrides"
    out.mkdir()
    return out
