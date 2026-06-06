"""GraphProjector multilingual unita_tipo recognition (issue #21).

A non-Italian host DB uses localized US/USM codes (English SU/WSU, German
SE/MSE, …). Before #21 the projector gated stratigraphic-row building on an
Italian-only tuple, so every localized US/USM row was skipped → no ``us``
attribute, no rapporti edges, no grouping. The fix routes the gating and the
node-class factory through ``rapporti.canonical_unita_tipo`` while keeping the
ORIGINAL code in ``attributes['unita_tipo']``.

Mirrors the real Al-Khutm data shape (unita_tipo SU/WSU, English rapporti).
"""
from __future__ import annotations
from pathlib import Path

import pandas  # noqa: F401
from lxml import etree as _etree  # noqa: F401

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DB = (PLUGIN_ROOT / "tests" / "sync" / "fixtures"
              / "mini_volterra.sqlite")


def test_projector_recognizes_localized_su_wsu(tmp_path):
    import shutil
    import sqlite3
    dst = tmp_path / "mv_en.sqlite"
    shutil.copy2(FIXTURE_DB, dst)
    con = sqlite3.connect(dst)
    con.execute("UPDATE us_table SET unita_tipo='SU'  WHERE unita_tipo='US'")
    con.execute("UPDATE us_table SET unita_tipo='WSU' WHERE unita_tipo='USM'")
    con.execute(
        "UPDATE us_table SET rapporti="
        "\"[['Covers', '2', '1', 'TestSite'], ['Covers', '3', '1', 'TestSite']]\""
        " WHERE us='1'")
    con.execute(
        "UPDATE us_table SET rapporti=\"[['Covers', '3', '1', 'TestSite']]\""
        " WHERE us='2'")
    con.commit()
    sito = con.execute("SELECT sito FROM us_table LIMIT 1").fetchone()[0]
    con.close()
    from tests.sync._uuid_backfill import add_columns, backfill_uuids
    add_columns(dst)
    backfill_uuids(dst)

    from s3dgraphy.sync import rapporti as R
    from s3dgraphy.sync.graph_projector import GraphProjector
    g = GraphProjector().populate_graph(dst, sito=sito)

    us_nodes = [n for n in g.nodes
                if (getattr(n, "attributes", {}) or {}).get("us")]
    assert len(us_nodes) >= 4, (
        f"SU/WSU rows must build stratigraphic nodes with a us attr, "
        f"got {len(us_nodes)}")
    strat = [e for e in g.edges
             if getattr(e, "edge_type", None) not in R.NON_RAPPORTI_EDGE_TYPES
             and getattr(e, "edge_type", None)]
    assert strat, "no stratigraphic edges created for English SU/WSU data"

    # Original code preserved on the node (round-trip safety).
    assert any((getattr(n, "attributes", {}) or {}).get("unita_tipo") == "SU"
               for n in us_nodes), "original SU code must survive on the node"

    labels = {e[0] for lst in R.serialize_rapporti_from_edges(g, sito).values()
              for e in lst}
    assert "Covers" in labels, f"expected localized 'Covers' in d13, got {labels}"
    assert "Copre" not in labels, f"d13 leaked Italian canonical: {labels}"
