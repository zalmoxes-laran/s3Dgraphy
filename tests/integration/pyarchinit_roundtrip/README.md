# pyarchinit ↔ s3dgraphy round-trip integration tests

End-to-end smoke for the AI07 LocationNodeGroup migration shipped in
**pyarchinit 5.6.0-alpha** (tag `phase2-ai07-locationnodegroup-5.6.0-alpha`,
2026-05-10), which resolves [issue #5](https://github.com/zalmoxes-laran/s3Dgraphy/issues/5)
on the consumer side.

## What this tests

```
pyarchinit SQLite (toponym_volterra fixture)
    ↓ GraphProjector.populate_graph
    ↓ graphml_writer.export_graphml         ← writes GraphML
    ↓ GraphIngestor.populate_list           ← reads GraphML back
    ↓ us_table identity check               (before == after)
```

Round-trip invariants verified:

1. `us_table` rows for the requested `sito` survive the export+import
   without mutation (no-op re-import preserves all structural columns).
2. `site_table` rows survive too — the projector and ingestor must
   never write to `site_table` on a structural round-trip.
3. The export emits `LocationNodeGroup` folders for the 6 spatial
   dimensions (`area`, `struttura`, `settore`, `ambient`, `saggio`,
   `quad_par`) per the AI07 dispatch table. `attivita` stays as
   `ActivityNodeGroup` (Q1 in issue #5).
4. `site_table.{nazione,regione,provincia,comune}` is auto-emitted as
   a recursive `LocationNodeGroup(kind="toponym")` chain when populated.

## How to run

This test **requires `pyarchinit` to be importable**. Two ways:

### Option A — pyarchinit checked out alongside

```bash
cd /path/to/your/workspace
git clone https://github.com/pyarchinit/pyarchinit.git
git clone https://github.com/zalmoxes-laran/s3Dgraphy.git

cd s3Dgraphy
pip install -e .

PYTHONPATH="../pyarchinit:$PWD/src" \
  python -m pytest tests/integration/pyarchinit_roundtrip/ -v
```

### Option B — pyarchinit installed via QGIS plugin path

```bash
PYTHONPATH="$HOME/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/pyarchinit" \
  python -m pytest tests/integration/pyarchinit_roundtrip/ -v
```

### Option C — CI without pyarchinit

If pyarchinit is not on `sys.path`, every test in this directory
**skips cleanly** (no failure). This is the intended behavior in
generic s3dgraphy CI runs that don't bundle a pyarchinit checkout.

## Fixture provenance

`fixtures/toponym_volterra.sqlite` is a derivative of the pyarchinit
`mini_volterra.sqlite` test fixture, extended in pyarchinit Group D
(commit `5e93d091`) with three sites:

| sito | nazione | regione | provincia | comune |
|---|---|---|---|---|
| Volterra | Italia | Toscana | Pisa | Volterra |
| Volterra2 | Italia | Toscana | Pisa | Volterra |
| Pompei_test | Italia | Campania | (empty) | Pompei |

The stratigraphic data (50 US rows) lives under `sito='TestSite'` —
the fixture exercises both single-site and cross-site dedupe paths
(Volterra + Volterra2 share `comune='Volterra'`) plus the skip-empty
path (Pompei_test has empty `provincia`).

`node_uuid` Phase 1 migration is pre-applied so the projector's
strict-schema mode passes.

## Cross-references

- Pyarchinit AI07 spec: `docs/superpowers/specs/2026-05-09-ai07-locationnodegroup-design.md`
  in `pyarchinit/pyarchinit:Stratigraph_00001`.
- Pyarchinit AI07 release tag: `phase2-ai07-locationnodegroup-5.6.0-alpha`.
- s3dgraphy 0.1.41 ship: tag `v0.1.41` on `s3DgraphyBeta4`, datamodel 1.5.5.
- Issue: [zalmoxes-laran/s3Dgraphy#5](https://github.com/zalmoxes-laran/s3Dgraphy/issues/5).

## Maintenance

If pyarchinit's API surface changes (`GraphProjector`, `export_graphml`,
`GraphIngestor.populate_list` signatures), this test will break. Update
the imports in `test_pyarchinit_roundtrip.py` and the assertions
correspondingly. Pyarchinit maintainers should keep this directory in
sync as part of their release dance.
