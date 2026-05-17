# Deprecations

This file tracks public-API symbols that are deprecated, the version in
which they were marked deprecated, and the canonical replacement.

Deprecated importers emit a `DeprecationWarning` at construction so
that downstream code surfaces the migration prompt without breaking.
Python suppresses `DeprecationWarning` by default; enable it explicitly
for migration audits:

```bash
PYTHONWARNINGS=default::DeprecationWarning python your_script.py
```

## Deprecated importers (1.6 → removed in 2.0)

| Symbol            | Deprecated in | Removed in | Replacement                                         |
| ----------------- | ------------- | ---------- | --------------------------------------------------- |
| `QualiaImporter`  | 1.6           | 2.0        | `UnifiedXLSXImporter` (single-file `em_data.xlsx`)  |

`QualiaImporter` consumed the long-format `em_paradata.xlsx` workbook
to enrich an already-imported stratigraphy graph with qualia, epoch
membership and provenance rows. That two-file pipeline
(`stratigraphy.xlsx` + `em_paradata.xlsx`) is fully superseded in 1.6
by `UnifiedXLSXImporter`, which reads a single `em_data.xlsx`
workbook with five typed sheets:

- `Units` — stratigraphic unit declarations (`ID`, `TYPE`, `NAME`).
- `Epochs` — temporal swimlanes (`ID`, `NAME`, `START`, `END`, `COLOR`).
- `Claims` — long-table, one row per claim (qualia, epoch membership,
  stratigraphic relation), each carrying its own
  `EXTRACTOR_n` / `DOCUMENT_n` / `AUTHOR_n` attribution.
- `Authors` — normalized catalog of human (`A.xx`) and AI (`AI.xx`)
  authors.
- `Documents` — normalized catalog of source PDFs / reports.

Build the importer like this:

```python
from s3dgraphy.importer.unified_xlsx_importer import UnifiedXLSXImporter
graph = UnifiedXLSXImporter("em_data.xlsx", graph_id="my_site").parse()
```

## Importers that are NOT deprecated

`MappedXLSXImporter`, `XLSXImporter` and `PyArchInitImporter` **remain
fully supported** in 1.6 and beyond. They are the canonical path for
ingesting tabular sources **external to `em_data.xlsx`** — for example
pyArchInit exports, EMdb extracts, or any generic `xlsx` / SQLite file
mapped via a JSON column-mapping descriptor. This flow is used heavily
by `em-tools` and is not going anywhere; only the legacy
`em_paradata.xlsx` long-format ingestion via `QualiaImporter` is
soppiantato by `em_data.xlsx` + `UnifiedXLSXImporter`.

## Migration recipe (em_paradata.xlsx → em_data.xlsx)

### Mapping concepts between legacy and 1.6

| Legacy                                              | 1.6 `em_data.xlsx` sheet & column                                |
| --------------------------------------------------- | ---------------------------------------------------------------- |
| Paradata sheet (QualiaImporter) `US_ID`             | `Claims.TARGET_ID`                                                |
| `PROPERTY_TYPE` + `VALUE`                            | `Claims.PROPERTY_TYPE` + `Claims.VALUE`                           |
| `EXTRACTOR_n` + `DOCUMENT_n` pair                   | `Claims.EXTRACTOR_n` + `Claims.DOCUMENT_n` + `Claims.AUTHOR_n`    |
| `COMBINER_REASONING` (multi-source rows)            | `Claims.COMBINER_REASONING`                                       |
| (implicit) belongs-to-epoch link                    | `Claims.PROPERTY_TYPE = "has_first_epoch"` + `TARGET2_ID` (epoch) |
| Stratigraphic relation row (`overlies`, `cuts`, …)  | `Claims.PROPERTY_TYPE = "<relation>"` + `TARGET2_ID` (other unit) |
| Author catalog (implicit, by column suffix)         | `Authors` sheet (`ID`, `KIND`, `DISPLAY_NAME`, `ORCID`, …)        |
| Document catalog (implicit, by reference)           | `Documents` sheet (`ID`, `FILENAME`, `TITLE`, `YEAR`, …)          |

### Migration steps

1. Export the existing `em_paradata.xlsx` (paradata long-format).
2. Create a new workbook `em_data.xlsx` with the five sheets above
   (Units / Epochs / Claims / Authors / Documents).
3. Populate `Units` from your stratigraphy source — keys stay the same.
4. For each paradata / qualia row, append one row to `Claims` keyed by
   `TARGET_ID = <unit id>`. Carry the `EXTRACTOR_n` / `DOCUMENT_n`
   columns over; add `AUTHOR_n` (matching an `Authors.ID`) so the
   provenance chain attaches to a named author or AI agent.
5. List every document referenced under `Documents` (with the new EM
   1.6 three-axis classification: `ROLE`, `CONTENT_NATURE`, `GEOMETRY`).
6. List every author referenced under `Authors` (`KIND` is `author` for
   humans, `extractor` for AI agents — the `AI.` prefix is conventional
   but not enforced).
7. Re-run your import:

   ```python
   from s3dgraphy.importer.unified_xlsx_importer import UnifiedXLSXImporter
   graph = UnifiedXLSXImporter("em_data.xlsx").parse()
   ```

Until 2.0 lands `QualiaImporter` still works; it just emits a
`DeprecationWarning` so that downstream tooling can flag pipelines
that have not yet migrated.
