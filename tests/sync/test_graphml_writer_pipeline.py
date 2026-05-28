"""Fixture-based pipeline tests for graphml_writer.

Each of the four tests pins one acceptance criterion from the AI03
spec §7.2 / dev-log limitations L1–L4. They run pure pytest (no
QGIS) against the committed mini_volterra.sqlite.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]

FIXTURE_DB = (PLUGIN_ROOT / "tests" / "sync" / "fixtures"
              / "mini_volterra.sqlite")


@pytest.fixture
def mini_volterra(tmp_path):
    """Copy the committed fixture to tmp_path so tests don't mutate it."""
    import shutil
    dst = tmp_path / "mini_volterra.sqlite"
    shutil.copy2(FIXTURE_DB, dst)
    return dst


def test_pipeline_produces_populated_graphml(mini_volterra, tmp_path):
    """L1 — the new pipeline must produce a non-empty .graphml.

    Closes the empty-on-grouping-flag bug from Phase 1.
    """
    from s3dgraphy.sync.graphml_writer import export_graphml
    out = tmp_path / "out.graphml"
    result = export_graphml(
        db_path=mini_volterra,
        mapping="pyarchinit_us_mapping",
        output_path=out,
    )
    assert out.exists()
    # Legacy bug produced 0-byte files; threshold of 1 KB is well above
    # the empty-document baseline of any GraphML header alone.
    assert out.stat().st_size > 1000
    assert result.node_count > 0
    assert result.edge_count > 0


def test_pipeline_emits_epoch_swimlanes(mini_volterra, tmp_path):
    """L2 — closes 'no period swimlanes' limitation.

    GraphMLExporter wraps strat nodes inside a TableNode swimlane;
    each EpochNode becomes a row inside the table. Look for a
    TableNode marker in the produced XML and assert epoch_count
    matches the fixture's two periods.
    """
    from s3dgraphy.sync.graphml_writer import export_graphml
    out = tmp_path / "out.graphml"
    result = export_graphml(
        db_path=mini_volterra, mapping="pyarchinit_us_mapping",
        output_path=out)
    xml = out.read_text(encoding="utf-8")
    assert ("TableNode" in xml or 'yfiles.foldertype="row"' in xml), (
        "no swimlane marker found in output")
    assert result.epoch_count >= 2, (
        f"expected >=2 epochs, got {result.epoch_count}")


def test_pipeline_diversifies_edge_styles(mini_volterra, tmp_path):
    """L3 — closes 'partial edge styling' limitation.

    The fixture rapporti span 4 distinct relation types (copre,
    coperto da, uguale a, riempie). After mapping into s3dgraphy
    edge types (is_after / is_after / has_same_time / fills) and
    rendering through GraphMLExporter, the produced XML must contain
    >=2 distinct yEd LineStyle.type values.
    """
    from s3dgraphy.sync.graphml_writer import export_graphml
    out = tmp_path / "out.graphml"
    export_graphml(
        db_path=mini_volterra, mapping="pyarchinit_us_mapping",
        output_path=out)
    xml = out.read_text(encoding="utf-8")
    line_styles = set(re.findall(
        r'<y:LineStyle[^>]+type="([^"]+)"', xml))
    assert len(line_styles) >= 2, (
        f"expected >=2 distinct LineStyle.type values, got {line_styles!r}")


def test_pipeline_applies_transitive_reduction(mini_volterra, tmp_path):
    """L4 — closes 'no transitive reduction' limitation.

    The fixture wires US1→US2→US3 plus a redundant US1→US3.
    GraphMLExporter must remove the redundant edge via
    TemporalInferenceEngine.transitive_reduction.
    """
    from s3dgraphy.sync.graphml_writer import export_graphml
    out = tmp_path / "out.graphml"
    result = export_graphml(
        db_path=mini_volterra, mapping="pyarchinit_us_mapping",
        output_path=out)
    assert result.tred_removed_edges >= 1, (
        f"expected >=1 redundant edge removed, got "
        f"{result.tred_removed_edges}; warnings={result.warnings!r}")
