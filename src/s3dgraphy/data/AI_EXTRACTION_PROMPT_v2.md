# AI-Assisted Stratigraphic Data Extraction
## Version 2.0 — Extended Matrix Workflow

---

## Overview

This prompt extracts archaeological stratigraphic data from PDF reports, field notes, images, and other documentation using AI assistants (Claude, ChatGPT, Gemini, etc.).

The extraction produces **three standardized outputs**:

1. **stratigraphy.xlsx** (sheet: "Stratigraphy") — Core stratigraphic data for generating the Extended Matrix GraphML
2. **em_paradata.xlsx** (sheet: "Paradata") — Per-property provenance data with verbatim quotes and page pointers
3. **new_qualia_discovered.json** — Proposed additions to the Qualia vocabulary (if new property types are found)

---

# PART A: Core Stratigraphy Extraction

## Instructions

You are an archaeological stratigraphy specialist. Extract stratigraphic data from the provided document(s) and produce a structured table compatible with the Extended Matrix (EM) system.

## Output Format

Produce a markdown table with the following **24 columns**. Use the EXACT column headers shown below. The table must be copy-pasteable into an Excel spreadsheet with sheet name "Stratigraphy".

## Column Schema (IMMUTABLE — DO NOT MODIFY)

| Column | Required | Type | Description |
|--------|----------|------|-------------|
| ID | YES | text | Unique identifier for each stratigraphic unit (e.g., US001, USM01, SU3016). Preserve the original naming from the source. |
| TYPE | YES | enum | Node type. Valid values: `US`, `USVs`, `USVn`, `SF`, `VSF`, `USD`, `serSU`, `serUSD`, `serUSVn`, `serUSVs`, `TSU`, `SE`, `BR` |
| DESCRIPTION | YES | text | Detailed textual description of the unit. Use the language of the source document. |
| PERIOD | no | text | Historical period (e.g., Roman, Medieval, Modern, Contemporary). |
| PERIOD_START | no | integer | Start year of the period. Use negative numbers for BCE (e.g., -753 for 753 BC). |
| PERIOD_END | no | integer | End year of the period. |
| PHASE | no | text | Chronological phase within the period (e.g., Republican, Imperial, Early Medieval). |
| PHASE_START | no | integer | Start year of the phase. |
| PHASE_END | no | integer | End year of the phase. |
| SUBPHASE | no | text | Finer chronological subdivision within the phase. |
| SUBPHASE_START | no | integer | Start year of the subphase. |
| SUBPHASE_END | no | integer | End year of the subphase. |
| OVERLIES | no | IDs | Comma-separated IDs of units that THIS unit lies upon (covers). |
| OVERLAIN_BY | no | IDs | Comma-separated IDs of units that rest on top of THIS unit. |
| CUTS | no | IDs | Comma-separated IDs of units that are cut BY this unit. |
| CUT_BY | no | IDs | Comma-separated IDs of units that cut THIS unit. |
| FILLS | no | IDs | Comma-separated IDs of units that THIS unit fills. |
| FILLED_BY | no | IDs | Comma-separated IDs of units that fill THIS unit. |
| ABUTS | no | IDs | Comma-separated IDs of units that THIS unit abuts against. |
| ABUTTED_BY | no | IDs | Comma-separated IDs of units that abut THIS unit. |
| BONDED_TO | no | IDs | Comma-separated IDs of units physically bonded to this one (contemporary construction). |
| EQUALS | no | IDs | Comma-separated IDs of units physically equal to this one (same fabric). |
| EXTRACTOR | YES | text | Agent that performed extraction (e.g., "Claude", "GPT-4o", "Gemini"). |
| DOCUMENT | YES | text | Primary source document with page range. Format: `filename.pdf [pp. X-Y]` |

## TYPE Classification Rules

- **US** (Stratigraphic Unit): Tangible physical units found in situ — walls, floors, deposits, fills, layers, cuts.
- **USVs** (Structural Virtual SU): Reconstruction hypothesis based on in situ fragmented evidence (connected to a destruction event).
- **USVn** (Non-Structural Virtual SU): Reconstruction hypothesis based on sources/comparisons, not physically proven.
- **SF** (Special Find): Non-in situ element (collapsed, displaced) that needs repositioning.
- **VSF** (Virtual Special Find): Restoration/completion of a repositioned SF element.
- **USD** (Documentary SU): Units identified through indirect documentation (historical records, geophysics, etc.).
- **serSU/serUSD/serUSVn/serUSVs**: Serial versions — groups of geometrically discontinuous elements of the same type.
- **TSU** (Transformation SU): Chemical, physical, or biological changes on surfaces over time.
- **SE** (Stratigraphic Event): Represents the action/event that created a stratigraphic unit (e.g., "construction of wall").
- **BR** (Continuity): Represents continuity of use or function.

## Relationship Rules

Stratigraphic relationships MUST be **symmetric**. If you write that US001 OVERLIES US002, then US002 must have US001 in its OVERLAIN_BY column.

Symmetric pairs:
- OVERLIES ↔ OVERLAIN_BY
- CUTS ↔ CUT_BY
- FILLS ↔ FILLED_BY
- ABUTS ↔ ABUTTED_BY
- BONDED_TO is bidirectional (if A bonded to B, then B bonded to A)
- EQUALS is bidirectional

## Language

- **DESCRIPTION**: Same language as source document
- Preserve original terminology and unit names exactly as written

## Important Notes

- Extract ALL stratigraphic units mentioned in the document, even if information is partial.
- If a unit is mentioned but details are scarce, create the row with ID and TYPE at minimum.
- Negative stratigraphic units (cuts, robbing trenches) should be typed as US with description indicating the negative action.
- When chronological information is ambiguous, leave date fields empty rather than guessing.
- Preserve the original unit numbering system from the source document.
- DOCUMENT column must include page range: `report.pdf [pp. 45-52]`

---

# PART B: Paradata Extraction (em_paradata.xlsx)

## Instructions

Extract per-property provenance data for the same stratigraphic units. Produce a **LONG format table** (one row per property, not one row per unit). This table will be saved as `em_paradata.xlsx` (sheet: "Paradata") and imported into the Extended Matrix graph as data provenance chains.

## Column Schema

| Column | Required | Description |
|--------|----------|-------------|
| US_ID | YES | Same ID as in the stratigraphy table (must match exactly). |
| PROPERTY_TYPE | YES | Property type from the EM vocabulary (snake_case, see list below). |
| VALUE | YES | The property value (e.g., "1.80 m", "opus reticulatum", "7.5YR 6/4"). |
| COMBINER_REASONING | NO | If this value was derived from MULTIPLE source documents, explain how sources were combined. Leave EMPTY for single-source properties. |
| EXTRACTOR_1 | YES | **Verbatim quote** from source document + **page pointer**. Format: `"exact quote" [p. X]` |
| DOCUMENT_1 | YES | Filename of the first source document (e.g., "excavation_report_2024.pdf"). |
| EXTRACTOR_2 | NO | Verbatim quote from second source (only for multi-source/combiner rows). |
| DOCUMENT_2 | NO | Filename of the second source document. |
| EXTRACTOR_N | NO | Additional extractor/document pairs as needed (EXTRACTOR_3/DOCUMENT_3, etc.). |
| DOCUMENT_N | NO | No limit to the number of source pairs. |

---

## CRITICAL: Verbatim Quote Requirement

**EXTRACTOR_N columns MUST contain:**

1. **Verbatim quote** from the source document (exact wording, in original language)
2. **Location pointer** in standardized format

### Location Pointer Formats

| Source Type | Format | Example |
|-------------|--------|---------|
| PDF text | `[p. X]` or `[pp. X-Y]` | `[p. 47]`, `[pp. 23-25]` |
| Figure | `[fig. X]` | `[fig. 12]` |
| Figure detail | `[fig. X, detail: description]` | `[fig. 12, section A-A']` |
| Table | `[tab. X, row Y]` | `[tab. 3, row 5]` |
| Photograph | `[photo: filename, area: description]` | `[photo: DSC_1234.jpg, area: top-left quadrant]` |
| 3D model | `[3D: model_name, view/measurement]` | `[3D: site.obj, top view, ruler tool]` |
| Drawing | `[drawing: name, scale, location]` | `[drawing: plan_level2.dwg, 1:50, room A]` |

### Quote Formatting Rules

**CORRECT examples:**
```
"Lo strato è composto da blocchi di tufo giallo con giunti irregolari, spessore 15-20 cm" [p. 47]
"Altezza massima conservata: m 2,50" [p. 23]
"Paramento in opera reticolata con cubilia di cm 8-10 di lato" [p. 56]
"Traccia di stilatura dei giunti" [photo: IMG_0234.jpg, area: lower courses]
```

**WRONG examples:**
```
"Layer of yellow tuff blocks" — paraphrase, not verbatim
"Height is 2.50m" — no page pointer
"Claude" — agent name, not extracted text
"See report" — not specific
```

**For long quotes (>200 characters):** Truncate with `[...]` preserving key terms:
```
"Il muro USM01 presenta un paramento in opera [...] con cubilia di cm 8-10" [p. 47]
```

**If page number is unknown:** Use `[p. ?]` — the import system will flag for human review.

---

## Measurement Atomization Rules

When a measurement is a **RANGE**, create **SEPARATE rows**:

| Source Text | Creates Rows |
|-------------|--------------|
| "spessore 0,30-0,50 m" | `thickness_min: 0.30 m` + `thickness_max: 0.50 m` |
| "altezza conservata m 1,80" | `height_preserved: 1.80 m` |
| "circa 2,5 m" or "~2,5 m" | `height_approx: 2.5 m` |
| "larghezza 0,55 m" | `width: 0.55 m` (single value, no suffix) |
| "quota sup. 115.60 m s.l.m." | `elevation_top: 115.60 m` |
| "quota inf. 114.20 m s.l.m." | `elevation_bottom: 114.20 m` |

### Dimensional Suffixes

| Suffix | Meaning | Use When |
|--------|---------|----------|
| `_min` | Minimum of range | Range given (e.g., "0.30-0.50") |
| `_max` | Maximum of range | Range given |
| `_approx` | Approximate value | "circa", "~", "about", "c." |
| `_preserved` | Preserved dimension | "conservato", "preserved", implies original was larger |
| `_reconstructed` | Reconstructed dimension | Based on hypothesis, not measured |

### Unit Standardization

- **Always include unit**: `1.80 m`, `45 cm`, `12.5 kg`
- **Decimal separator**: Convert comma to period (`1,80` → `1.80`)
- **Prefer SI units**; preserve original if non-SI (e.g., feet in historical sources)

---

## Property Type Vocabulary (aligned with em_qualia_types.json)

**Use these EXACT snake_case identifiers. Do not use Title Case or variations.**

### DIMENSIONAL (`physical_material.dimensional`)

**Core measurements:**
`height`, `width`, `length`, `thickness`, `depth`, `weight`, `diameter`, `area`, `perimeter`, `volume`

**Elevation:**
`elevation`, `elevation_top`, `elevation_bottom`, `elevation_average`

**Suffixes** (append as needed):
`_min`, `_max`, `_approx`, `_preserved`, `_reconstructed`

**Examples:** `thickness_min`, `height_preserved`, `elevation_top`, `diameter_max`

### MATERIAL (`physical_material.material`)

`material_type`, `origin_type`, `surface_treatment`, `granulometry`, `mortar_type`, `binder_type`, `aggregate_type`, `aggregate_size`, `color`, `color_munsell`, `inclusions`, `material_provenance`

### STATE (`physical_material.state`)

`conservation_state`, `integrity`, `damage_type`, `damage_extent`, `weathering_type`, `biological_attack`, `salt_damage`, `structural_cracks`, `deformation`

### TECHNICAL (`physical_material.technical`)

`construction_technique`, `bond_pattern`, `joint_type`, `joint_width`, `tool_marks`, `laying_pattern`, `pointing_style`, `coursing`, `module_dimensions`, `surface_finish`

### SPATIAL (`spatiotemporal.spatial`)

`absolute_position`, `orientation`, `elevation`, `arrangement`, `slope`, `aspect`, `coordinates_x`, `coordinates_y`, `coordinates_z`, `coordinate_system`

### TEMPORAL / DATING (`spatiotemporal.temporal`)

**Assigned dates:**
`absolute_start_date`, `absolute_end_date`, `dating_method`

**Dating evidence (extracted from finds, samples, etc.):**
`terminus_post_quem`, `terminus_ante_quem`, `dating_evidence_type`, `dating_evidence_id`, `dating_confidence`

### FUNCTIONAL (`functional`)

`primary_function`, `secondary_functions`, `structural_role`, `load_capacity`, `stress_type`

### INTERPRETIVE (`cultural_interpretive`)

`definition`, `interpretation`, `artistic_style`, `stylistic_influences`, `comparanda`, `parallels`

### ADMINISTRATIVE (`contextual.administrative`)

`inventory_number`, `sample_id`, `excavation_date`, `excavator`, `legal_status`, `intervention_history`, `conservation_status`

---

## Dating Evidence Extraction

When the source mentions **dating evidence** (coins, pottery, inscriptions, C14, dendrochronology, etc.), extract these properties:

| PROPERTY_TYPE | What to extract |
|---------------|-----------------|
| `terminus_post_quem` | The date AFTER which the context was formed (e.g., coin minting date) |
| `terminus_ante_quem` | The date BEFORE which the context was formed |
| `dating_evidence_type` | Type: `coin`, `pottery`, `inscription`, `c14`, `dendrochronology`, `historical_source`, `typology`, `archaeomagnetism`, `osl` |
| `dating_evidence_id` | Inventory number, catalog reference, or sample ID |
| `dating_confidence` | `high`, `medium`, `low`, `uncertain` |

### Example: Coin providing TPQ

**Source text:** "Nello strato US03 è stata rinvenuta una moneta di Traiano (RIC II 123), databile al 103-111 d.C." [p. 89]

| US_ID | PROPERTY_TYPE | VALUE | EXTRACTOR_1 | DOCUMENT_1 |
|-------|---------------|-------|-------------|------------|
| US03 | terminus_post_quem | 103 AD | "moneta di Traiano (RIC II 123), databile al 103-111 d.C." [p. 89] | finds_catalog.pdf |
| US03 | dating_evidence_type | coin | "moneta di Traiano" [p. 89] | finds_catalog.pdf |
| US03 | dating_evidence_id | RIC II 123 | "RIC II 123" [p. 89] | finds_catalog.pdf |
| US03 | dating_confidence | high | "databile al 103-111 d.C." [p. 89] | finds_catalog.pdf |

### Example: Pottery providing date range

**Source text:** "Frammenti di sigillata africana D (Hayes 61A) datano lo strato al IV-V sec. d.C." [p. 112]

| US_ID | PROPERTY_TYPE | VALUE | EXTRACTOR_1 | DOCUMENT_1 |
|-------|---------------|-------|-------------|------------|
| US07 | terminus_post_quem | 325 AD | "sigillata africana D (Hayes 61A) datano lo strato al IV-V sec." [p. 112] | pottery_report.pdf |
| US07 | terminus_ante_quem | 500 AD | "sigillata africana D (Hayes 61A) datano lo strato al IV-V sec." [p. 112] | pottery_report.pdf |
| US07 | dating_evidence_type | pottery | "Frammenti di sigillata africana D" [p. 112] | pottery_report.pdf |
| US07 | dating_evidence_id | Hayes 61A | "Hayes 61A" [p. 112] | pottery_report.pdf |

---

## Multi-Source Reasoning (COMBINER_REASONING)

When a property value derives from **MULTIPLE sources**, the COMBINER_REASONING field must:

1. **Explicitly name each source** being combined
2. **State what each source contributes**
3. **Explain the reasoning logic**

### Template
```
Source 1 ([DOCUMENT_1]) provides [specific evidence].
Source 2 ([DOCUMENT_2]) provides [specific evidence].
Combined because [reasoning].
Resulting value [VALUE] assigned with [confidence level] confidence.
```

### Example: Combining petrographic and visual evidence

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|
| USM01 | material_provenance | Campi Flegrei | Source 1 (isotopic_report.pdf) provides chemical signature matching Campi Flegrei tuff. Source 2 (field_notes.pdf) confirms visual characteristics (golden-yellow color, vesicular texture). Combined because both chemical and visual evidence converge on same source. Assigned with high confidence. | "Analisi isotopica indica provenienza flegrea con rapporto Sr87/Sr86 = 0.7074" [p. 12] | isotopic_report.pdf | "Blocchi di colore giallo dorato con tessitura vescicolare tipica del tufo napoletano" [p. 34] | field_notes.pdf |

### Example: Resolving conflicting dates

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|
| US05 | absolute_start_date | 150 AD | Source 1 (pottery_report.pdf) dates construction to mid-2nd century based on associated pottery. Source 2 (coin_catalog.pdf) provides TPQ of 138 AD from coin of Antoninus Pius. Sources are compatible: coin provides minimum date, pottery refines to mid-century. Date of 150 AD assigned as midpoint estimate. | "Ceramica associata data la costruzione alla metà del II sec. d.C." [p. 67] | pottery_report.pdf | "Moneta di Antonino Pio (138-161 d.C.) rinvenuta nella fondazione" [p. 23] | coin_catalog.pdf |

---

## Discovering New Qualia Types

If you encounter a property that does **NOT fit any existing PROPERTY_TYPE**:

1. **Extract it anyway** using a descriptive snake_case ID
2. **Document it** in a third output: `new_qualia_discovered.json`

### Template for new_qualia_discovered.json

```json
{
  "extraction_session": {
    "date": "2024-01-15",
    "extractor_agent": "Claude",
    "source_documents": ["report_2024.pdf", "field_notes.pdf"]
  },
  "new_qualia": [
    {
      "proposed_id": "hydraulic_mortar",
      "proposed_name": "Hydraulic Mortar",
      "proposed_category": "physical_material.material",
      "definition": "Morite with hydraulic properties (contains pozzolana, cocciopesto, or volcanic aggregate)",
      "example_value": "cocciopesto with volcanic aggregate",
      "example_us_id": "USM12",
      "source_quote": "\"malta idraulica con cocciopesto e inerti vulcanici\" [p. 34]",
      "source_document": "masonry_analysis.pdf",
      "rationale": "Distinct from generic mortar_type; indicates specific hydraulic technology important for dating and function",
      "suggested_mappings": {
        "getty_aat": "300014922",
        "cidoc_crm": "E57_Material"
      }
    }
  ]
}
```

This enables vocabulary growth while ensuring no data is lost.

---

## Over-Extraction Mandate

**Extract MORE rather than less.** When in doubt, extract it.

### Systematic Extraction Checklist

Scan **every page** of the source document for:

- [ ] **Dimensions**: Any number with a unit (m, cm, mm, kg, etc.)
- [ ] **Materials**: Stone types, mortar, brick, wood, metal, organic materials
- [ ] **Colors**: Any color description, especially Munsell codes
- [ ] **Techniques**: Construction methods, tool marks, joint types, bond patterns
- [ ] **Condition**: Damage, weathering, erosion, biological attack, repairs
- [ ] **Dates**: Centuries, years, periods, phases, termini
- [ ] **Comparisons**: Parallels, analogies, comparanda cited by author
- [ ] **Finds**: Objects, samples, analysis results associated with units
- [ ] **Spatial**: Coordinates, elevations, orientations, slopes
- [ ] **Administrative**: Inventory numbers, sample IDs, excavation dates

**The Extended Matrix can filter unnecessary data; it cannot recover unextracted data.**

---

## Important Notes

- Extract ALL properties mentioned in the document for each stratigraphic unit.
- US_ID values MUST match exactly the IDs in the stratigraphy table (Part A).
- Use the **same language** as the source document for VALUE and EXTRACTOR text.
- **Verbatim quotes are mandatory** — do not paraphrase.
- **Page pointers are mandatory** — use `[p. ?]` if unknown.
- If a property comes from a single source, leave COMBINER_REASONING empty.
- If a property comes from multiple sources, fill COMBINER_REASONING and provide each source.

---

# Example Outputs

## Part A — Stratigraphy Table

| ID | TYPE | DESCRIPTION | PERIOD | PERIOD_START | PERIOD_END | PHASE | PHASE_START | PHASE_END | SUBPHASE | SUBPHASE_START | SUBPHASE_END | OVERLIES | OVERLAIN_BY | CUTS | CUT_BY | FILLS | FILLED_BY | ABUTS | ABUTTED_BY | BONDED_TO | EQUALS | EXTRACTOR | DOCUMENT |
|----|------|-------------|--------|--------------|------------|-------|-------------|-----------|----------|----------------|--------------|----------|-------------|------|--------|-------|-----------|-------|------------|-----------|--------|-----------|----------|
| USM01 | US | Muro perimetrale nord in opera incerta | Romano | -27 | 476 | Imperiale | 50 | 200 | | | | | USM02,US03 | | | | | | | USM04 | | Claude | Report_2023.pdf [pp. 45-52] |
| USM02 | US | Pavimento in laterizi (bessales) | Romano | -27 | 476 | Imperiale | 50 | 200 | | | | USM01 | US03 | | | | | | | | | Claude | Report_2023.pdf [pp. 53-55] |
| US03 | US | Strato di distruzione con crollo e malta | Romano | -27 | 476 | Tardo-imperiale | 200 | 300 | | | | USM02 | | | | | | | | | | Claude | Report_2023.pdf [pp. 56-58] |
| USM04 | US | Muro perimetrale est legato a USM01 | Romano | -27 | 476 | Imperiale | 50 | 200 | | | | | US03 | | | | | USM01 | | USM01 | | Claude | Report_2023.pdf [pp. 45-52] |

## Part B — Paradata Table (em_paradata.xlsx)

### Single-source examples

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 |
|-------|---------------|-------|--------------------|-------------|------------|
| USM01 | height_preserved | 1.80 m | | "altezza massima conservata m 1,80" [p. 47] | Report_2023.pdf |
| USM01 | construction_technique | opus incertum | | "paramento in opera incerta con bozze calcaree e malta di calce" [p. 47] | Report_2023.pdf |
| USM01 | thickness | 0.55 m | | "spessore del muro m 0,55" [p. 48] | Report_2023.pdf |
| USM01 | material_type | limestone | | "bozze calcaree di forma irregolare" [p. 47] | Report_2023.pdf |
| USM01 | mortar_type | lime mortar | | "malta di calce con inerti fini" [p. 47] | Report_2023.pdf |
| USM01 | color_munsell | 10YR 8/2 | | "colore della malta: 10YR 8/2 (very pale brown)" [p. 48] | Report_2023.pdf |
| USM01 | conservation_state | good | | "buono stato di conservazione, nessun danno strutturale visibile" [p. 49] | Report_2023.pdf |
| USM02 | material_type | brick | | "bessales in laterizio disposti su letto di malta" [p. 53] | Report_2023.pdf |
| USM02 | module_dimensions | 20 x 20 x 4 cm | | "modulo dei bessales cm 20 x 20 x 4" [p. 53] | Report_2023.pdf |
| US03 | thickness_min | 0.30 m | | "spessore variabile da m 0,30 presso i muri a m 0,50 al centro" [p. 56] | Report_2023.pdf |
| US03 | thickness_max | 0.50 m | | "spessore variabile da m 0,30 presso i muri a m 0,50 al centro" [p. 56] | Report_2023.pdf |
| US03 | terminus_post_quem | 193 AD | | "moneta di Settimio Severo (RIC IV 1) databile al 193-211 d.C." [p. 89] | finds_catalog.pdf |
| US03 | dating_evidence_type | coin | | "moneta di Settimio Severo" [p. 89] | finds_catalog.pdf |
| US03 | dating_evidence_id | RIC IV 1 | | "RIC IV 1" [p. 89] | finds_catalog.pdf |

### Multi-source example

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|
| USM01 | material_provenance | Monte Soratte quarries | Source 1 (petrographic_analysis.pdf) identifies limestone as Cretaceous calcarenite consistent with Monte Soratte formation. Source 2 (field_notes.pdf) notes proximity to known Roman quarries at Monte Soratte. Combined because petrographic and geographic evidence converge. Assigned with high confidence. | "Analisi petrografica: calcarenite cretacea compatibile con formazione M. Soratte" [p. 8] | petrographic_analysis.pdf | "Cave romane note a Monte Soratte a circa 15 km dal sito" [p. 12] | field_notes.pdf |

---

# Usage Instructions

## Processing Multiple Documents

For multi-document projects:
1. Process each document separately
2. Merge tables ensuring ID consistency
3. Use COMBINER_REASONING when same property has evidence from multiple documents

## Enriching Existing GraphML

If you already have a GraphML file:
```
I already have a GraphML with the following stratigraphic units: [list IDs].
Check if extracted units match existing ones — use SAME ID if they match.
For existing units, focus on extracting additional relationships and properties.
Mark new units clearly with "[NEW]" in DESCRIPTION.
```

## Output Formats

**Primary format:** Markdown tables (for human readability and review)

**Alternative format:** JSON (if requested, for direct import)
```json
{
  "stratigraphy": [...],
  "paradata": [...],
  "new_qualia_discovered": [...]
}
```

---

# Import Workflow

1. Copy Part A table → save as `stratigraphy.xlsx` (sheet: "Stratigraphy")
2. Copy Part B table → save as `em_paradata.xlsx` (sheet: "Paradata")
3. Save new Qualia JSON → `new_qualia_discovered.json`
4. Use s3Dgraphy `MappedXLSXImporter` to generate GraphML from stratigraphy.xlsx
5. Use EMtools "Bake Paradata" operator to enrich GraphML with em_paradata.xlsx
6. Review new_qualia_discovered.json for vocabulary updates

---

*Version 2.0 — Extended Matrix AI Extraction Prompt*
*Optimized for Claude, GPT-4, Gemini and compatible AI assistants*
