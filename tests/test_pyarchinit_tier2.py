"""Tier-2 importer handlers for :class:`PyArchInitImporter`.

Covers the memberships added on top of Tier-1 (identity + location):

* **EpochNode** via ``epoch_mappings`` — ``has_first_epoch`` (initial
  period/phase) and ``survive_in_epoch`` (final period/phase), with the
  time span resolved against a ``periodizzazione_table`` join.
* **AuthorNode** via ``has_author`` — one shared node per person.
* **DocumentNode** via ``has_documentation`` — the pyArchInit
  ``documentazione`` presence checklist (one per-US doc per affirmative
  entry) and a single file reference (one shared doc, deduped by path).

The fixture deliberately mirrors a pyArchInit quirk that bit the first
implementation: ``periodizzazione_table.fase`` is declared ``STRING``,
which carries SQLite **NUMERIC** affinity, so ``'2'`` round-trips as
``int 2`` and the sub-phase ``'2.1'`` as ``float 2.1`` — while us_table
keeps them as text. The code-distinction test below guards that ``2`` and
``2.1`` stay separate epochs and never collapse onto each other.

Same fixture pattern as ``test_composite_node_name.py``.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter  # noqa: E402
from s3dgraphy.mappings.registry import mapping_registry  # noqa: E402


# --------------------------------------------------------------------------
# _norm_code unit coverage — the period/phase canonicalizer
# --------------------------------------------------------------------------
@pytest.mark.parametrize("value, expected", [
    (2, "2"),            # INTEGER from periodizzazione
    ("2", "2"),          # VARCHAR from us_table
    (2.0, "2"),          # integer-valued float collapses
    ("2.0", "2"),
    ("02", "2"),         # zero-padded
    (2.1, "2.1"),        # REAL sub-phase (NUMERIC affinity) — MUST NOT -> "2"
    ("2.1", "2.1"),      # text sub-phase
    ("2.10", "2.1"),     # trailing-zero text == float 2.1
    ("A", "A"),          # non-numeric code preserved
    ("II", "II"),
    (None, ""),
    ("", ""),
    ("  3 ", "3"),       # stripped
])
def test_norm_code(value, expected):
    assert PyArchInitImporter._norm_code(value) == expected


def test_norm_code_keeps_subphase_distinct_from_period():
    """The regression that motivated this test: 2 and 2.1 must differ."""
    assert (PyArchInitImporter._norm_code(2)
            != PyArchInitImporter._norm_code(2.1))
    assert (PyArchInitImporter._norm_code("2")
            != PyArchInitImporter._norm_code("2.1"))


# --------------------------------------------------------------------------
# Fixture
# --------------------------------------------------------------------------
def _write_fixture(tmp_path):
    """Build a SQLite DB (us_table + periodizzazione_table) and a Tier-2
    mapping. Returns ``(db_path, mapping_name, mapping_dir)``."""
    db_path = tmp_path / "tier2.sqlite"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE us_table (
            us               INTEGER PRIMARY KEY,
            sito             TEXT NOT NULL,
            area             TEXT,
            settore          TEXT,
            unita_tipo       TEXT,
            d_stratigrafica  TEXT,
            periodo_iniziale VARCHAR(4),
            fase_iniziale    VARCHAR(4),
            periodo_finale   VARCHAR(4),
            fase_finale      VARCHAR(4),
            schedatore       TEXT,
            direttore_us     TEXT,
            documentazione   TEXT,
            doc_usv          TEXT,
            node_uuid        TEXT
        )
        """
    )
    # fase declared STRING on purpose -> NUMERIC affinity (see module docstring).
    cur.execute(
        """
        CREATE TABLE periodizzazione_table (
            id_perfas     INTEGER PRIMARY KEY,
            sito          TEXT,
            periodo       INTEGER,
            fase          STRING,
            cron_iniziale INTEGER,
            cron_finale   INTEGER,
            descrizione   TEXT
        )
        """
    )
    periods = [
        (1, "S", 2, "2",   1500, 1549, "First half 16th c."),
        (2, "S", 2, "2.1", 1451, 1499, "15th c. recent"),
        (3, "S", 1, "1",   1800, 2022, "Contemporary"),
    ]
    cur.executemany(
        "INSERT INTO periodizzazione_table "
        "(id_perfas, sito, periodo, fase, cron_iniziale, cron_finale, descrizione) "
        "VALUES (?,?,?,?,?,?,?)", periods)

    # US1: phase 2 ; US2: sub-phase 2.1 ; US3: phase 2 + survives into 1.1.
    checklist = "[['Fotografie', 'Si'], ['Sezioni', 'No']]"
    # node_uuid = canonical UUID v7 identity (added by the pyArchInit
    # node_uuid backfill migration); carried into node_id via is_passthrough.
    rows = [
        (1, "S", "1", "A", "US", "layer 1", "2", "2", "", "",
         "Luca Mandolesi", "", checklist, "", "uuid-us-1"),
        (2, "S", "1", "A", "US", "layer 2", "2", "2.1", "", "",
         "Luca Mandolesi", "", "[]", r"DosCo\plan.dxf", "uuid-us-2"),
        (3, "S", "1", "A", "US", "layer 3", "2", "2", "1", "1",
         "Anna Rossi", "Luca Mandolesi", "[['Planimetrie', 'Si']]",
         r"DosCo\plan.dxf", "uuid-us-3"),
    ]
    cur.executemany(
        "INSERT INTO us_table VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    join = {
        "table": "periodizzazione_table", "site_column": "sito",
        "period_column": "periodo", "phase_column": "fase",
        "start_column": "cron_iniziale", "end_column": "cron_finale",
        "name_column": "descrizione",
    }
    mapping = {
        "name": "tier2_test", "description": "Tier-2 test mapping",
        "version": "1.6.2",
        "table_settings": {
            "format_type": "sqlite", "table_name": "us_table",
            "node_name_template": "{area}.{unita_tipo}{us}",
        },
        "column_mappings": {
            "sito": {"is_filter": True, "filter_required": True},
            "area": {"node_type": "LocationNodeGroup", "location_kind": "study"},
            "settore": {"node_type": "LocationNodeGroup", "location_kind": "study"},
            "unita_tipo": {"display_name": "type"},
            "us": {"is_id": True, "node_type": "US"},
            "node_uuid": {"is_passthrough": True},
            "d_stratigrafica": {"is_description": True},
            "schedatore": {"node_type": "AuthorNode", "author_role": "compiler"},
            "direttore_us": {"node_type": "AuthorNode", "author_role": "director"},
            "documentazione": {
                "node_type": "DocumentNode",
                "doc_format": "pyarchinit_checklist",
                "doc_content_nature_default": "2d_object"},
            "doc_usv": {"node_type": "DocumentNode", "doc_format": "path"},
        },
        "relations": [],
        "epoch_mappings": [
            {"edge_type": "has_first_epoch", "period_column": "periodo_iniziale",
             "phase_column": "fase_iniziale", "site_column": "sito", "join": join},
            {"edge_type": "survive_in_epoch", "period_column": "periodo_finale",
             "phase_column": "fase_finale", "site_column": "sito", "join": join},
        ],
    }
    mapping_dir = tmp_path / "mappings"
    mapping_dir.mkdir()
    (mapping_dir / "tier2_test.json").write_text(
        json.dumps(mapping), encoding="utf-8")
    mapping_registry.add_mapping_directory(
        "pyarchinit", str(mapping_dir), priority="high")
    return str(db_path), "tier2_test", str(mapping_dir)


def _cleanup(mapping_dir):
    dirs = mapping_registry._mapping_directories.get("pyarchinit", [])
    try:
        dirs.remove(mapping_dir)
    except ValueError:
        pass


@pytest.fixture
def graph(tmp_path):
    db, name, mdir = _write_fixture(tmp_path)
    try:
        importer = PyArchInitImporter(
            filepath=db, mapping_name=name, filters={"sito": "S"})
        g = importer.parse()
        g._importer = importer  # expose for warning assertions
        yield g
    finally:
        _cleanup(mdir)


def _by_type(g):
    return Counter(getattr(n, "node_type", "?") for n in g.nodes)


def _edge_types(g):
    return Counter(getattr(e, "edge_type", "?") for e in g.edges)


def _node(g, node_id):
    return next((n for n in g.nodes if n.node_id == node_id), None)


# --------------------------------------------------------------------------
# Epoch
# --------------------------------------------------------------------------
def test_subphase_epochs_are_distinct(graph):
    """2 and 2.1 must resolve to separate EpochNodes with their own spans."""
    e_2 = _node(graph, "epoch::S::2::2")
    e_21 = _node(graph, "epoch::S::2::2.1")
    assert e_2 is not None and e_21 is not None
    assert (e_2.start_time, e_2.end_time) == (1500, 1549)
    assert (e_21.start_time, e_21.end_time) == (1451, 1499)
    assert e_2.name == "First half 16th c."
    assert e_21.name == "15th c. recent"


def test_has_first_epoch_edges(graph):
    et = _edge_types(graph)
    assert et["has_first_epoch"] == 3   # every US has an initial period
    assert et["survive_in_epoch"] == 1  # only US3 has a final period


def test_epoch_shared_across_rows(graph):
    """US1 and US3 both sit in phase 2 -> one shared epoch, two edges."""
    edges = [e for e in graph.edges
             if e.edge_type == "has_first_epoch"
             and e.edge_target == "epoch::S::2::2"]
    assert len(edges) == 2


def test_missing_periodization_row_skips_epoch(tmp_path):
    """A period/phase with no periodizzazione match yields a warning, no edge."""
    db, name, mdir = _write_fixture(tmp_path)
    # Point a US at a non-existent phase by editing the DB.
    conn = sqlite3.connect(db)
    conn.execute("UPDATE us_table SET fase_iniziale='9' WHERE us=1")
    conn.commit()
    conn.close()
    try:
        importer = PyArchInitImporter(
            filepath=db, mapping_name=name, filters={"sito": "S"})
        g = importer.parse()
        assert _node(g, "epoch::S::2::9") is None
        assert any("No periodization row" in w for w in importer.warnings)
    finally:
        _cleanup(mdir)


# --------------------------------------------------------------------------
# Author
# --------------------------------------------------------------------------
def test_author_shared_and_deduped(graph):
    """Luca Mandolesi appears as schedatore (US1,2,3) and direttore (US3):
    one shared AuthorNode, and US3's two roles collapse to one edge."""
    authors = [n for n in graph.nodes if n.node_type == "author"]
    names = sorted(a.name for a in authors)
    assert names == ["Anna Rossi", "Luca Mandolesi"]
    luca = next(a for a in authors if a.name == "Luca Mandolesi")
    luca_edges = [e for e in graph.edges
                  if e.edge_type == "has_author"
                  and e.edge_target == luca.node_id]
    # US1, US2, US3 each link once to Luca (US3's compiler+director collapse).
    assert len(luca_edges) == 3
    assert len({e.edge_source for e in luca_edges}) == 3


# --------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------
def test_checklist_documents_per_us(graph):
    """Only affirmative ('Si') checklist entries become per-US docs."""
    docs = [n for n in graph.nodes if n.node_type == "document"]
    us1 = _node(graph, _us_id(graph, "1.US1"))
    # US1: Fotografie=Si (doc), Sezioni=No (skipped).
    foto = _node(graph, f"{us1.node_id}_doc_fotografie")
    assert foto is not None and foto.name == "Fotografie"
    assert foto.data.get("content_nature") == "2d_object"
    assert _node(graph, f"{us1.node_id}_doc_sezioni") is None


def test_path_document_shared(graph):
    """US2 and US3 reference the same file -> one shared DocumentNode."""
    doc = _node(graph, r"doc::path::DosCo\plan.dxf")
    assert doc is not None
    assert doc.name == "plan.dxf"
    assert getattr(doc, "url", None) == r"DosCo\plan.dxf"
    edges = [e for e in graph.edges
             if e.edge_type == "has_documentation" and e.edge_target == doc.node_id]
    assert len(edges) == 2


# --------------------------------------------------------------------------
# Edge validity + idempotency
# --------------------------------------------------------------------------
def test_passthrough_uses_node_uuid(graph):
    """The canonical node_uuid (UUID v7) is carried into the US node_id
    (is_passthrough), so re-import is idempotent on a migrated DB."""
    us_ids = {n.node_id for n in graph.nodes if n.node_type == "US"}
    assert us_ids == {"uuid-us-1", "uuid-us-2", "uuid-us-3"}


def test_no_generic_connection_downgrades(graph):
    assert not any("not allowed" in w for w in graph.warnings)


def test_reimport_is_idempotent(tmp_path):
    """Re-importing into the same graph adds no duplicate nodes or edges."""
    db, name, mdir = _write_fixture(tmp_path)
    try:
        g = PyArchInitImporter(
            filepath=db, mapping_name=name, filters={"sito": "S"}).parse()
        n0, e0 = len(g.nodes), len(g.edges)
        imp2 = PyArchInitImporter(
            filepath=db, mapping_name=name, filters={"sito": "S"},
            existing_graph=g)
        imp2.parse()
        assert (len(g.nodes), len(g.edges)) == (n0, e0)
        assert imp2.orphans == []   # all rows matched the enriching branch
    finally:
        _cleanup(mdir)


def _us_id(g, name):
    return next(n.node_id for n in g.nodes
               if getattr(n, "node_type", None) == "US" and n.name == name)


# --------------------------------------------------------------------------
# Shipped-file consistency: quota property_names must be real qualia ids
# --------------------------------------------------------------------------
def test_shipped_quota_property_names_are_qualia_ids():
    """Guard against drift between the shipped pyArchInit mapping and
    em_qualia_types.json: every quota_* column maps to a property_name that
    exists as a qualia `id` (exact-match resolution in rdf_exporter)."""
    import json
    cfg = _REPO_ROOT / "src" / "s3dgraphy"
    mapping = json.loads(
        (cfg / "mappings" / "pyarchinit" / "pyarchinit_us_mapping.json")
        .read_text(encoding="utf-8"))
    qualia = json.loads(
        (cfg / "JSON_config" / "em_qualia_types.json").read_text(encoding="utf-8"))
    qids = {q["id"]
            for cat in qualia.get("qualia_categories", [])
            for sub in (cat.get("subcategories") or {}).values()
            for q in (sub.get("qualia") or [])
            if q.get("id") and (q.get("mappings") or {}).get("cidoc_crm")}
    quota_pnames = {
        col: c["property_name"]
        for col, c in mapping["column_mappings"].items()
        if col.startswith("quota_") and c.get("property_name")}
    assert quota_pnames, "expected quota_* columns in the shipped mapping"
    missing = {col: pn for col, pn in quota_pnames.items() if pn not in qids}
    assert not missing, f"quota property_names not found as qualia ids: {missing}"
