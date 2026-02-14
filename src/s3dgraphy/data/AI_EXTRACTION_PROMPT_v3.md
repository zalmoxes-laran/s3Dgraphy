# AI-Assisted Stratigraphic Data Extraction
## Version 3.0 — Extended Matrix Workflow

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

## Column Schema (up to 5 source pairs)

The table has a **fixed set of columns**. Every row MUST have columns up to DOCUMENT_5, even if most are empty. This ensures a consistent, rectangular table suitable for spreadsheet import.

| Column | Required | Description |
|--------|----------|-------------|
| US_ID | YES | Same ID as in the stratigraphy table (must match exactly). |
| PROPERTY_TYPE | YES | Property type from the EM vocabulary (snake_case, see list below). |
| VALUE | YES | The property value (e.g., "1.80 m", "opus reticulatum", "7.5YR 6/4"). |
| COMBINER_REASONING | **YES if ≥2 sources** | Reasoning that explains HOW and WHY multiple sources were combined. MUST be populated whenever EXTRACTOR_2 is not empty. Leave EMPTY only for single-source properties. |
| EXTRACTOR_1 | YES | **Verbatim quote** from source document + **page pointer**. Format: `"exact quote" [p. X]` |
| DOCUMENT_1 | YES | Filename + author attribution. Format: `source_file [Author]` |
| EXTRACTOR_2 | NO | Verbatim quote from second source (only for multi-source rows). |
| DOCUMENT_2 | NO | Filename + author attribution of the second source. |
| EXTRACTOR_3 | NO | Verbatim quote from third source. |
| DOCUMENT_3 | NO | Filename + author attribution of the third source. |
| EXTRACTOR_4 | NO | Verbatim quote from fourth source. |
| DOCUMENT_4 | NO | Filename + author attribution of the fourth source. |
| EXTRACTOR_5 | NO | Verbatim quote from fifth source. |
| DOCUMENT_5 | NO | Filename + author attribution of the fifth source. Maximum 5 source pairs per row. |

### Column Count Rule

The table ALWAYS has exactly **14 columns** (US_ID through DOCUMENT_5). Unused EXTRACTOR/DOCUMENT pairs are left empty. This ensures consistent import into spreadsheets and databases.

If a property requires more than 5 sources, split it into two rows with a cross-reference in the COMBINER_REASONING field.

---

## CRITICAL: Combiner Reasoning Rules (v3 — NEW)

### The Iron Rule

**COMBINER_REASONING is MANDATORY whenever EXTRACTOR_2 is populated.** A row with two or more extractors and an empty combiner is an ERROR.

### What the Combiner Does

The COMBINER_REASONING field is the **intellectual core** of the paradata. It explains the reasoning that connects multiple independent sources into a single property value. It answers: *"Why do these sources, taken together, justify this value?"*

### Common Combiner Patterns

#### Pattern 1: Local observation + Bibliographic rule
The most common pattern in virtual reconstruction: a measurement or observation on the archaeological remains (Source 1) is combined with a proportional rule or typological classification from the literature (Source 2).

```
Source 1 (thesis_chapter5.tex [Demetrescu]) provides measured module from special
finds T12 and T15 (0.514 m at imoscapo).
Source 2 (Wilson Jones, Principles of Roman architecture, 2000) documents the 10:1
height-to-module ratio as standard for orthodox Corinthian columns.
Combined because the locally measured module (0.514 m × 10 = 5.14 m) produces the
total height, validated by the comparative proportional rule.
```

#### Pattern 2: Archaeological negative evidence + Textual source
An absence of materials at the site (Source 1) is explained by a textual recommendation or known practice (Source 2).

```
Source 1 (thesis_chapter5.tex [Demetrescu]) observes absence of stone lintel blocks
during excavation.
Source 2 (Vitruvius, De Architectura III, 2) recommends wooden lintels for diastil
intercolumnia due to fragility of stone over such spans.
Combined because the archaeological negative evidence (no stone blocks found) is
consistent with the Vitruvian recommendation for this module type.
```

#### Pattern 3: Converging evidence from different disciplines
Multiple independent analyses (petrographic, visual, geographic) point to the same conclusion.

```
Source 1 (isotopic_report.pdf) provides chemical signature matching Campi Flegrei tuff.
Source 2 (field_notes.pdf) confirms visual characteristics (golden-yellow color,
vesicular texture).
Combined because both chemical and visual evidence independently converge on the same
provenance. Assigned with high confidence.
```

#### Pattern 4: Resolving ambiguity with comparative evidence
A textual ambiguity (Source 1) is resolved by comparative measurements from real buildings (Source 2+).

```
Source 1 (Gros 1990; Gros 1997) discusses the ambiguity in Vitruvius' text regarding
where to measure the imoscapo (base or flare of shaft).
Source 2 (Wilson Jones 2000, pp. 147-149) provides comparative measurements from
multiple Roman buildings showing the flare as the correct measurement point.
Combined because the comparative evidence from real buildings resolves the textual
ambiguity in favor of the lower flare.
```

#### Pattern 5: Three or more sources converging
When three or more sources contribute, ALL must be listed in the combiner and each must have its own EXTRACTOR_N/DOCUMENT_N pair.

```
Source 1 (thesis_chapter5.tex [Demetrescu]) classifies the column as orthodox Corinthian
based on proportions.
Source 2 (Heilmeyer 1970, pp. 25-51) documents the canonization of the Corinthian order
at Rome.
Source 3 (Wilson Jones 2000, pp. 136-143) provides the proportional framework (10:1
ratio, 5/6 shaft, 7/6 capital).
Source 4 (Gros 1976, pp. 197-234) traces the stylistic evolution from Augustan to
imperial age.
Combined because the proportional measurements from local fragments match the canonical
system documented across three independent scholarly frameworks.
```

### Combiner Template

```
Source 1 ([DOCUMENT_1]) provides [specific evidence / observation].
Source 2 ([DOCUMENT_2]) provides [specific evidence / rule / comparison].
[Source 3 ([DOCUMENT_3]) provides [additional evidence].]
[Source 4 ([DOCUMENT_4]) provides [additional evidence].]
[Source 5 ([DOCUMENT_5]) provides [additional evidence].]
Combined because [explicit reasoning connecting the sources].
Resulting value "[VALUE]" assigned with [high/medium/low] confidence.
```

### Combiner Validation Checklist

Before finalizing each multi-source row, verify:

- [ ] **COMBINER_REASONING is not empty** (mandatory if EXTRACTOR_2 exists)
- [ ] **Every source mentioned in the combiner** has a corresponding EXTRACTOR_N / DOCUMENT_N pair
- [ ] **The number of EXTRACTOR_N columns** matches the number of sources described in the combiner
- [ ] **The reasoning is explicit** — a reader should understand WHY these sources together justify the VALUE without needing to read the original documents
- [ ] **Confidence level is stated** (high / medium / low)

---

## Author Attribution in DOCUMENT_N

Each DOCUMENT_N column should indicate **who made the interpretation** using this format:

```
source_filename [Author_surname]
```

**Examples:**
- `thesis_chapter5.tex [Demetrescu]` — the author's own interpretation
- `Wilson Jones, Principles of Roman architecture, 2000` — extracted from another scholar's work
- `Vitruvius, De Architectura` — classical source
- `excavation_report_2024.pdf [Rossi]` — from another archaeologist's report

**Rules:**
- Use `[Author_surname]` in square brackets when the interpretation is by a specific person
- For published works, the author is implicit in the bibliographic reference
- When extracting from one's own work, always mark it: `my_thesis.pdf [Demetrescu]`

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
| LaTeX section | `[sec. Section Name]` | `[sec. Virtual Activity 2]` |
| LaTeX table | `[Tab. label]` | `[Tab. VAct2]` |
| Footnote | `[footnote N]` | `[footnote 12]` |

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

**IMPORTANT (v3): Prefer specific property types over generic ones.** If the standard vocabulary does not capture the specific meaning of a property, create a new descriptive snake_case identifier and document it in `new_qualia_discovered.json`. A column shaft height is `shaft_height`, not `height`. An intercolumnium is `intercolumnium`, not `width`. Generic types like `interpretation` should only be used when no more specific type applies.

### DIMENSIONAL (`physical_material.dimensional`)

**Core measurements:**
`height`, `width`, `length`, `thickness`, `depth`, `weight`, `diameter`, `area`, `perimeter`, `volume`

**Elevation:**
`elevation`, `elevation_top`, `elevation_bottom`, `elevation_average`, `elevation_difference`

**Architectural-specific measurements:**
`base_height`, `shaft_height`, `capital_height`, `module_column`, `intercolumnium`, `step_dimensions`, `column_grid`, `corridor_width`, `portico_length`, `portico_width`

**Suffixes** (append as needed):
`_min`, `_max`, `_approx`, `_preserved`, `_reconstructed`

**Examples:** `thickness_min`, `height_preserved`, `elevation_top`, `diameter_max`

### MATERIAL (`physical_material.material`)

`material_type`, `origin_type`, `surface_treatment`, `granulometry`, `mortar_type`, `binder_type`, `aggregate_type`, `aggregate_size`, `color`, `color_munsell`, `inclusions`, `material_provenance`

### STATE (`physical_material.state`)

`conservation_state`, `integrity`, `damage_type`, `damage_extent`, `weathering_type`, `biological_attack`, `salt_damage`, `structural_cracks`, `deformation`, `construction_error`, `spoliation_evidence`

### TECHNICAL (`physical_material.technical`)

`construction_technique`, `bond_pattern`, `joint_type`, `joint_width`, `tool_marks`, `laying_pattern`, `pointing_style`, `coursing`, `module_dimensions`, `surface_finish`, `proportional_system`, `imoscapo_position`, `capital_proportion_note`, `lintel_alternative`

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

`definition`, `interpretation`, `interpretation_alternative`, `artistic_style`, `stylistic_influences`, `comparanda`, `parallels`, `building_type`, `cult_attribution`, `inauguratio_evidence`

### ADMINISTRATIVE (`contextual.administrative`)

`inventory_number`, `sample_id`, `excavation_date`, `excavator`, `legal_status`, `intervention_history`, `conservation_status`, `survey_precision`, `restoration_note`, `repositioning_note`, `dimensions_note`

---

## Avoiding Duplicate Property Types

**Do NOT use the same PROPERTY_TYPE twice for the same US_ID with different meanings.** When the same US_ID has multiple values that might seem like the same property, use more specific types:

| WRONG (duplicate) | CORRECT (specific) |
|---|---|
| USV125 / `height` / 5.14 m | USV125 / `height` / 5.14 m (total column height) |
| USV125 / `height` / 0.25 m | USV125 / `base_height` / 0.25 m |
| USV125 / `height` / 4.28 m | USV125 / `shaft_height` / 4.28 m |
| USV125 / `height` / 0.59 m | USV125 / `capital_height` / 0.59 m |
| USV104 / `width` / 15 feet | USV104 / `corridor_width` / 15 roman feet |
| USV104 / `width` / 34 m | USV104 / `portico_width` / 34 m |
| USV104 / `interpretation` / diastil | USV104 / `intercolumnium` / 1.542 m (diastil) |
| USV104 / `interpretation` / aerostil | USV104 / `interpretation_alternative` / aerostil |

**Exception:** `comparanda` MAY be repeated for the same US_ID, since a unit can have multiple distinct architectural parallels (each is a separate comparison with a different building).

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

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 |
|-------|---------------|-------|--------------------|-------------|------------|
| US03 | terminus_post_quem | 103 AD | | "moneta di Traiano (RIC II 123), databile al 103-111 d.C." [p. 89] | finds_catalog.pdf |
| US03 | dating_evidence_type | coin | | "moneta di Traiano" [p. 89] | finds_catalog.pdf |
| US03 | dating_evidence_id | RIC II 123 | | "RIC II 123" [p. 89] | finds_catalog.pdf |
| US03 | dating_confidence | high | | "databile al 103-111 d.C." [p. 89] | finds_catalog.pdf |

### Example: Pottery providing date range

**Source text:** "Frammenti di sigillata africana D (Hayes 61A) datano lo strato al IV-V sec. d.C." [p. 112]

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 |
|-------|---------------|-------|--------------------|-------------|------------|
| US07 | terminus_post_quem | 325 AD | | "sigillata africana D (Hayes 61A) datano lo strato al IV-V sec." [p. 112] | pottery_report.pdf |
| US07 | terminus_ante_quem | 500 AD | | "sigillata africana D (Hayes 61A) datano lo strato al IV-V sec." [p. 112] | pottery_report.pdf |
| US07 | dating_evidence_type | pottery | | "Frammenti di sigillata africana D" [p. 112] | pottery_report.pdf |
| US07 | dating_evidence_id | Hayes 61A | | "Hayes 61A" [p. 112] | pottery_report.pdf |

---

## Multi-Source Reasoning (COMBINER_REASONING) — EXPANDED IN V3

When a property value derives from **MULTIPLE sources**, the COMBINER_REASONING field must:

1. **Explicitly name each source** being combined (matching the DOCUMENT_N columns)
2. **State what each source contributes** (observation, rule, measurement, comparison)
3. **Explain the reasoning logic** that connects them
4. **State a confidence level** (high / medium / low)

### CRITICAL: Number of EXTRACTOR/DOCUMENT pairs must match

Every source mentioned in COMBINER_REASONING **MUST** have a corresponding EXTRACTOR_N / DOCUMENT_N column pair. Conversely, every populated EXTRACTOR_N **MUST** be referenced in the COMBINER_REASONING.

| Sources in combiner | Columns needed |
|---------------------|----------------|
| 1 source | EXTRACTOR_1 + DOCUMENT_1 only. **COMBINER_REASONING is empty.** |
| 2 sources | EXTRACTOR_1/DOCUMENT_1 + EXTRACTOR_2/DOCUMENT_2. **COMBINER_REASONING is mandatory.** |
| 3 sources | EXTRACTOR_1–3 / DOCUMENT_1–3. **COMBINER_REASONING is mandatory.** |
| 4 sources | EXTRACTOR_1–4 / DOCUMENT_1–4. **COMBINER_REASONING is mandatory.** |
| 5 sources | EXTRACTOR_1–5 / DOCUMENT_1–5. **COMBINER_REASONING is mandatory.** |
| >5 sources | Split into two rows with cross-reference in COMBINER_REASONING. |

### Example: 2-source combiner (local observation + bibliographic rule)

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|
| USV125 | height | 5.14 m | Source 1 (thesis_cap5.tex [Demetrescu]) provides measured module from special finds T12 and T15 (0.514 m at imoscapo). Source 2 (Wilson Jones 2000) documents the 10:1 height-to-module ratio as standard for orthodox Corinthian columns. Combined because the locally measured module (0.514 m × 10) produces the total height, validated by the comparative rule. Assigned with high confidence. | "In the case of the colonnade the diameter at imoscapo (module D) is recognizable in special find T12, T15 and it is 0.514 m" [sec. Column's dimensions] | thesis_cap5.tex [Demetrescu] | "See pp. 148-149 and fig. 7.26" [pp. 148-149] | Wilson Jones, Principles of Roman architecture, 2000 |

### Example: 2-source combiner (negative evidence + textual recommendation)

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|
| USV106 | material_type | Wood and stuccoes | Source 1 (thesis_cap5.tex [Demetrescu]) observes absence of stone lintel blocks during excavation. Source 2 (Vitruvius DeArch III, 2) recommends wooden lintels for diastil intercolumnia. Combined because archaeological negative evidence (no stone blocks found) is consistent with the Vitruvian recommendation. Assigned with high confidence. | "The lack of stone blocks during the recent excavations of the lintel suggests however that it could be a wooden one" [sec. Virtual Activity 3] | thesis_cap5.tex [Demetrescu] | "According to Vitruvius (Vitr III,2), the diastil module manner is fragile [...] he suggests, for this kind of module, a wooden lintel (with stuccoes for the decoration)" [III, 2] | Vitruvius, De Architectura |

### Example: 3-source combiner (measurement ambiguity resolved by comparison)

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 | EXTRACTOR_3 | DOCUMENT_3 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|-------------|------------|
| USV125 | imoscapo_position | Lower flare of the shaft | Source 1 (thesis_cap5.tex [Demetrescu]) applies the lower flare position for module measurement. Source 2 (Gros 1990, 1997) discusses the ambiguity in Vitruvius' text about where to measure the imoscapo. Source 3 (Wilson Jones 2000, pp. 147-149) provides comparative measurements from multiple Roman buildings confirming the flare. Combined because the comparative evidence resolves the textual ambiguity. Assigned with high confidence. | "In this reconstruction the flare of the shaft is used as the reference measure" [sec. Virtual Activity 2] | thesis_cap5.tex [Demetrescu] | "About this topic see Gros 1990 p. 102 and Gros 1997 pp. 299-300, footnote 88" [p. 102; pp. 299-300] | Gros, Vitruve: De l'architecture, 1990; Gros, Vitruvio. De architectura, 1997 | "See Wilson Jones 2000 pp. 147-149" [pp. 147-149] | Wilson Jones, Principles of Roman architecture, 2000 |

### Example: 4-source combiner (stylistic classification)

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 | EXTRACTOR_3 | DOCUMENT_3 | EXTRACTOR_4 | DOCUMENT_4 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|-------------|------------|-------------|------------|
| USV125 | artistic_style | Orthodox Corinthian-Roman order | Source 1 (thesis_cap5.tex [Demetrescu]) classifies the column as orthodox Corinthian based on measured proportions. Source 2 (Heilmeyer 1970) documents the canonization of the Corinthian order. Source 3 (Wilson Jones 2000) provides the proportional framework. Source 4 (Gros 1976) traces the stylistic evolution. Combined because the measured proportions match the canonical system documented across three independent scholarly frameworks. Assigned with high confidence. | "in several examples of orthodox corinthian-roman columns" [sec. Column's dimensions] | thesis_cap5.tex [Demetrescu] | "See Heilmeyer 1970 pp. 25-51" [pp. 25-51] | Heilmeyer, Korinthische Normalkapitelle, 1970 | "See Wilson Jones 2000 pp. 136-143" [pp. 136-143] | Wilson Jones, Principles of Roman architecture, 2000 | "See Gros 1976 pp. 197-234" [pp. 197-234] | Gros, Aurea templa, 1976 |

### Example: Resolving conflicting dates (2-source combiner)

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|
| US05 | absolute_start_date | 150 AD | Source 1 (pottery_report.pdf) dates construction to mid-2nd century based on associated pottery. Source 2 (coin_catalog.pdf) provides TPQ of 138 AD from coin of Antoninus Pius. Sources are compatible: coin provides minimum date, pottery refines to mid-century. Date of 150 AD assigned as midpoint estimate. Assigned with medium confidence. | "Ceramica associata data la costruzione alla metà del II sec. d.C." [p. 67] | pottery_report.pdf | "Moneta di Antonino Pio (138-161 d.C.) rinvenuta nella fondazione" [p. 23] | coin_catalog.pdf |

---

## Discovering New Qualia Types

If you encounter a property that does **NOT fit any existing PROPERTY_TYPE**:

1. **Extract it anyway** using a descriptive snake_case ID
2. **Use it immediately** in the paradata table — do not wait for approval
3. **Document it** in a third output: `new_qualia_discovered.json`

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
      "definition": "Mortar with hydraulic properties (contains pozzolana, cocciopesto, or volcanic aggregate)",
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
- [ ] **Proportional systems**: Module ratios, Vitruvian rules, canonical proportions
- [ ] **Construction errors**: Misalignments, lack of perpendicularity
- [ ] **Negative evidence**: Absence of expected materials (spoliation, robbing)
- [ ] **Restoration history**: Modern interventions, repositioned elements

**The Extended Matrix can filter unnecessary data; it cannot recover unextracted data.**

---

## Important Notes

- Extract ALL properties mentioned in the document for each stratigraphic unit.
- US_ID values MUST match exactly the IDs in the stratigraphy table (Part A).
- Use the **same language** as the source document for VALUE and EXTRACTOR text.
- **Verbatim quotes are mandatory** — do not paraphrase.
- **Page pointers are mandatory** — use `[p. ?]` if unknown.
- If a property comes from a single source, leave COMBINER_REASONING empty.
- If a property comes from multiple sources, fill COMBINER_REASONING and provide ALL sources as EXTRACTOR_N / DOCUMENT_N pairs.
- **Do not use generic property types when a specific one exists** (see "Avoiding Duplicate Property Types" section).
- **COMBINER_REASONING is mandatory whenever EXTRACTOR_2 is not empty** — this is the v3 iron rule.

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

### Single-source examples (COMBINER_REASONING is empty)

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 | EXTRACTOR_3 | DOCUMENT_3 | EXTRACTOR_4 | DOCUMENT_4 | EXTRACTOR_5 | DOCUMENT_5 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|-------------|------------|-------------|------------|-------------|------------|
| USM01 | height_preserved | 1.80 m | | "altezza massima conservata m 1,80" [p. 47] | Report_2023.pdf [Rossi] | | | | | | | | |
| USM01 | construction_technique | opus incertum | | "paramento in opera incerta con bozze calcaree e malta di calce" [p. 47] | Report_2023.pdf [Rossi] | | | | | | | | |
| USM01 | thickness | 0.55 m | | "spessore del muro m 0,55" [p. 48] | Report_2023.pdf [Rossi] | | | | | | | | |

### 2-source example (COMBINER_REASONING is mandatory)

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 | EXTRACTOR_3 | DOCUMENT_3 | EXTRACTOR_4 | DOCUMENT_4 | EXTRACTOR_5 | DOCUMENT_5 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|-------------|------------|-------------|------------|-------------|------------|
| USM01 | material_provenance | Monte Soratte quarries | Source 1 (petrographic_analysis.pdf) identifies limestone as Cretaceous calcarenite consistent with Monte Soratte formation. Source 2 (field_notes.pdf) notes proximity to known Roman quarries at Monte Soratte. Combined because petrographic and geographic evidence converge. Assigned with high confidence. | "Analisi petrografica: calcarenite cretacea compatibile con formazione M. Soratte" [p. 8] | petrographic_analysis.pdf | "Cave romane note a Monte Soratte a circa 15 km dal sito" [p. 12] | field_notes.pdf [Bianchi] | | | | | | |

### 3-source example (COMBINER_REASONING is mandatory)

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 | EXTRACTOR_3 | DOCUMENT_3 | EXTRACTOR_4 | DOCUMENT_4 | EXTRACTOR_5 | DOCUMENT_5 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|-------------|------------|-------------|------------|-------------|------------|
| USV125 | imoscapo_position | Lower flare of the shaft | Source 1 (thesis_cap5.tex [Demetrescu]) applies the lower flare for module measurement. Source 2 (Gros 1990; Gros 1997) discusses the Vitruvian ambiguity. Source 3 (Wilson Jones 2000) confirms with comparative data from Roman buildings. Combined because comparative evidence resolves textual ambiguity. Assigned with high confidence. | "In this reconstruction the flare of the shaft is used as the reference measure" [sec. Virtual Activity 2] | thesis_cap5.tex [Demetrescu] | "About this topic see Gros 1990 p. 102 and Gros 1997 pp. 299-300" [p. 102; pp. 299-300] | Gros, Vitruve: De l'architecture, 1990; Gros, Vitruvio. De architectura, 1997 | "See pp. 147-149" [pp. 147-149] | Wilson Jones, Principles of Roman architecture, 2000 | | | | |

---

# Usage Instructions

## Processing Multiple Documents

For multi-document projects:
1. Process each document separately
2. Merge tables ensuring ID consistency
3. Use COMBINER_REASONING when same property has evidence from multiple documents
4. Ensure every source in the combiner has its own EXTRACTOR_N / DOCUMENT_N pair (up to 5)

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
2. Copy Part B table → save as `em_paradata.xlsx` (sheet: "Paradata") — **must have exactly 14 columns**
3. Save new Qualia JSON → `new_qualia_discovered.json`
4. Use s3Dgraphy `MappedXLSXImporter` to generate GraphML from stratigraphy.xlsx
5. Use EMtools "Bake Paradata" operator to enrich GraphML with em_paradata.xlsx
6. Review new_qualia_discovered.json for vocabulary updates

---

# Changelog

## v3.0 (2026-02-14)
- **COMBINER_REASONING is now mandatory** whenever EXTRACTOR_2 is populated (the "iron rule")
- **Fixed column schema**: exactly 14 columns (up to EXTRACTOR_5/DOCUMENT_5), explicitly enumerated
- **Added combiner patterns**: 5 documented patterns (local+bibliographic, negative evidence+text, converging disciplines, ambiguity resolution, 3+ sources)
- **Added combiner validation checklist**
- **Added author attribution** in DOCUMENT_N columns (`source_file [Author]`)
- **Expanded property vocabulary**: added architectural-specific types (`base_height`, `shaft_height`, `capital_height`, `module_column`, `intercolumnium`, `column_grid`, `corridor_width`, `portico_length`, `portico_width`, `step_dimensions`, `elevation_difference`)
- **Added state types**: `construction_error`, `spoliation_evidence`
- **Added technical types**: `proportional_system`, `imoscapo_position`, `capital_proportion_note`, `lintel_alternative`
- **Added interpretive types**: `interpretation_alternative`, `building_type`, `cult_attribution`, `inauguratio_evidence`
- **Added administrative types**: `survey_precision`, `restoration_note`, `repositioning_note`, `dimensions_note`
- **Added "Avoiding Duplicate Property Types" section** with specific-vs-generic examples
- **Added LaTeX-specific location pointers** (`[sec.]`, `[Tab.]`, `[footnote]`)
- **Expanded extraction checklist**: added proportional systems, construction errors, negative evidence, restoration history

## v2.0
- Initial structured extraction with Part A (stratigraphy) and Part B (paradata)
- Introduced COMBINER_REASONING for multi-source properties
- Introduced new_qualia_discovered.json for vocabulary growth

---

*Version 3.0 — Extended Matrix AI Extraction Prompt*
*Optimized for Claude, GPT-4, Gemini and compatible AI assistants*
