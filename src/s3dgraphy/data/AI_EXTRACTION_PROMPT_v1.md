# AI-Assisted Stratigraphic Data Extraction

## Overview

This document contains a ready-to-use prompt for extracting archaeological stratigraphic data from PDF reports, field notes, images, and other documentation using AI assistants (Claude, ChatGPT, Gemini, etc.).

The extraction produces **two standardized Excel files**:

1. **stratigraphy.xlsx** (sheet: "Stratigraphy") — Core stratigraphic data for generating the Extended Matrix GraphML
2. **em_paradata.xlsx** (sheet: "Paradata") — Per-property provenance data with full data lineage (extractor text → source document), baked into the GraphML as paradata chains

---

## Prompt — Part A: Core Stratigraphy Extraction

Copy and paste the prompt below into your AI assistant, followed by the document(s) to analyze.

---

### PROMPT START (Part A)

```
You are an archaeological stratigraphy specialist. Your task is to extract stratigraphic data from the provided document(s) and produce a structured table compatible with the Extended Matrix (EM) system.

## Output Format

Produce a markdown table with the following 24 columns. Use the EXACT column headers shown below. The table must be copy-pasteable into an Excel spreadsheet with sheet name "Stratigraphy".

## Column Schema

| Column | Required | Type | Description |
|--------|----------|------|-------------|
| ID | YES | text | Unique identifier for each stratigraphic unit (e.g., US001, USM01, SU3016). Preserve the original naming from the source. |
| TYPE | YES | enum | Node type. Valid values: US, USVs, USVn, SF, VSF, USD, serSU, serUSD, serUSVn, serUSVs, TSU, SE, BR |
| DESCRIPTION | YES | text | Detailed textual description of the unit. Use the language of the source document unless otherwise specified. |
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
| EXTRACTOR | YES | text | Who/what extracted this data. Use your model name (e.g., "Claude", "GPT-4o", "Gemini"). |
| DOCUMENT | YES | text | Source document filename or reference. |

## TYPE Classification Rules

- **US** (Stratigraphic Unit): Tangible physical units found in situ — walls, floors, deposits, fills, layers.
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

Stratigraphic relationships MUST be symmetric. If you write that US001 OVERLIES US002, then US002 must have US001 in its OVERLAIN_BY column. The symmetric pairs are:

- OVERLIES ↔ OVERLAIN_BY
- CUTS ↔ CUT_BY
- FILLS ↔ FILLED_BY
- ABUTS ↔ ABUTTED_BY
- BONDED_TO is bidirectional (if A bonded to B, then B bonded to A)
- EQUALS is bidirectional

## Language

Write descriptions in the same language as the source document, unless the user specifies otherwise.

## Important Notes

- Extract ALL stratigraphic units mentioned in the document, even if information is partial.
- If a unit is mentioned but details are scarce, create the row with ID and TYPE at minimum.
- Negative stratigraphic units (destructions, cuts, removals) should be typed as US with a description indicating the negative action, or as SE if they represent events.
- When chronological information is ambiguous, leave the date fields empty rather than guessing.
- Preserve the original unit numbering system from the source document.
```

### PROMPT END (Part A)

---

## Prompt — Part B: Paradata Extraction (em_paradata.xlsx)

After Part A is complete, use this prompt to extract per-property provenance data with full data lineage.

Unlike the stratigraphy table (one row per US, wide format), the paradata table uses a **long format**: one row per US+property pair. Each row records not just the property value, but the exact text extracted from a source document that supports that value.

---

### PROMPT START (Part B)

```
Now extract per-property provenance data for the same stratigraphic units. Produce a SECOND markdown table in LONG format (one row per property, not one row per unit). This table will be saved as `em_paradata.xlsx` (sheet: "Paradata") and imported into the Extended Matrix graph as data provenance chains.

## Column Schema

| Column | Required | Description |
|--------|----------|-------------|
| US_ID | YES | Same ID as in the stratigraphy table (must match exactly). |
| PROPERTY_TYPE | YES | Property type from the EM vocabulary (see list below). |
| VALUE | YES | The property value (e.g., "2.5m", "opus reticulatum", "Tufo giallo"). |
| COMBINER_REASONING | NO | If this value was derived from MULTIPLE source documents, write the reasoning that combines the evidence. Leave EMPTY for single-source properties. |
| EXTRACTOR_1 | YES | The specific text/observation extracted from the first source document that supports this property value. This is NOT the agent name — it is the actual extracted content. |
| DOCUMENT_1 | YES | Filename of the first source document (e.g., "excavation_report_2024.pdf"). |
| EXTRACTOR_2 | NO | Text extracted from a second source document (only for multi-source/combiner rows). |
| DOCUMENT_2 | NO | Filename of the second source document. |
| EXTRACTOR_N | NO | Additional extractor/document pairs can be added as needed (EXTRACTOR_3/DOCUMENT_3, etc.). |
| DOCUMENT_N | NO | There is no limit to the number of source pairs. |

## Provenance Chain Logic

Each row creates a provenance chain in the Extended Matrix graph:

**Single-source** (COMBINER_REASONING is empty):
```
PropertyNode → ExtractorNode → DocumentNode
```
Only EXTRACTOR_1 and DOCUMENT_1 are used. Other pairs are ignored.

**Multi-source / Combiner** (COMBINER_REASONING is filled):
```
PropertyNode → CombinerNode → ExtractorNode₁ → DocumentNode₁
                             → ExtractorNode₂ → DocumentNode₂
                             → ...
```
All EXTRACTOR_N/DOCUMENT_N pairs are scanned. Each source has its own distinct extractor text.

## CRITICAL Rules

### 1. One row per property
Each (US_ID, PROPERTY_TYPE) combination is ONE row. If USM01 has Height, Material, and Conservation State, that produces 3 rows.

### 2. EXTRACTOR is NOT the agent name
The EXTRACTOR column contains the specific text, measurement, or observation extracted from the source document — NOT the name of who extracted it (not "Claude", not "GPT-4", not "Manual").

CORRECT examples:
- "Layer of yellow tuff blocks with irregular mortar joints, thickness 15-20cm"
- "Measured from 3D model base to top: 2.50m ± 0.05m"
- "Observed wall fabric pattern with regular small blocks arranged in diamond pattern"

WRONG examples:
- "Claude"
- "GPT-4o"
- "Manual extraction"

### 3. DOCUMENT is a specific filename
Use the exact filename or bibliographic reference of the source.

CORRECT: "excavation_report_2024.pdf", "field_notes_day5.pdf", "Rossi2019_fig12.pdf"
WRONG: "Various sources", "Field documentation", "PDF reports"

### 4. When to use the Combiner
Use COMBINER_REASONING when a property value is the result of reasoning across MULTIPLE independent sources. Each source must have its OWN extractor text describing what was specifically found in THAT document.

Example: Material = "Tufo giallo napoletano" derived from two sources:
- Isotopic analysis report → specific finding about chemical signature
- Field notes → visual observation of color and texture

In this case, EXTRACTOR_1 and EXTRACTOR_2 each describe what was found in their respective document, and COMBINER_REASONING explains how these were combined.

### 5. Property Type Vocabulary

**Physical & Material:**
- Height, Width, Length, Thickness, Depth, Weight, Diameter
- Material, Origin Type, Surface Treatment, Granulometry
- Conservation State, Integrity
- Construction Technique

**Spatiotemporal:**
- Absolute Position, Orientation, Elevation, Arrangement
- Absolute Start Date, Absolute End Date, Dating Method

**Functional:**
- Primary Function, Secondary Functions, Structural Role

**Cultural & Interpretive:**
- Artistic Style, Stylistic Influences
- Definition, Interpretation

**Contextual:**
- Inventory Number, Legal Status

You may add property types not in this list if the document contains relevant data. Use descriptive English names in Title Case.

## Important Notes

- Extract ALL properties mentioned in the document for each stratigraphic unit.
- US_ID values MUST match exactly the IDs in the stratigraphy table (Part A).
- Use the same language as the source document for VALUE and EXTRACTOR text.
- If a property comes from a single source, leave COMBINER_REASONING empty and fill only EXTRACTOR_1/DOCUMENT_1.
- If a property comes from multiple sources, fill COMBINER_REASONING and provide each source as a separate EXTRACTOR_N/DOCUMENT_N pair.
```

### PROMPT END (Part B)

---

## Example Output

### Part A — Stratigraphy Table

| ID | TYPE | DESCRIPTION | PERIOD | PERIOD_START | PERIOD_END | PHASE | PHASE_START | PHASE_END | SUBPHASE | SUBPHASE_START | SUBPHASE_END | OVERLIES | OVERLAIN_BY | CUTS | CUT_BY | FILLS | FILLED_BY | ABUTS | ABUTTED_BY | BONDED_TO | EQUALS | EXTRACTOR | DOCUMENT |
|----|------|-------------|--------|--------------|------------|-------|-------------|-----------|----------|----------------|--------------|----------|-------------|------|--------|-------|-----------|-------|------------|-----------|--------|-----------|----------|
| USM01 | US | Foundation wall in opus incertum | Roman | -753 | 476 | Imperial | -27 | 476 | | | | | USM02,US03 | | | | | | | USM04 | | Claude | Report_2023.pdf |
| USM02 | US | Brick floor surface | Roman | -753 | 476 | Imperial | -27 | 476 | | | | USM01 | US03 | | | | | | | | | Claude | Report_2023.pdf |
| US03 | US | Destruction layer with rubble and mortar fragments | Roman | -753 | 476 | Imperial | -27 | 476 | | | | USM02 | | | | | | | | | | Claude | Report_2023.pdf |
| USM04 | US | Perimeter wall bonded to USM01 | Roman | -753 | 476 | Imperial | -27 | 476 | | | | | US03 | | | | | USM01 | | USM01 | | Claude | Report_2023.pdf |

### Part B — Paradata Table (em_paradata.xlsx)

**Single-source examples** (COMBINER_REASONING empty):

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|
| USM01 | Height | 1.80 m | | Measured from base course to top of preserved wall: 1.80m | Report_2023.pdf | | |
| USM01 | Construction Technique | opus incertum | | Wall fabric composed of irregularly shaped limestone blocks bonded with lime mortar, characteristic of opus incertum technique | Report_2023.pdf | | |
| USM01 | Conservation State | good | | Northern wall fully preserved to original height, no visible deterioration or structural damage | Report_2023.pdf | | |
| USM02 | Material | brick | | Floor composed of rectangular brick tiles (bessales) laid on a mortar bed | Report_2023.pdf | | |
| US03 | Thickness | 0.30-0.50 m | | Destruction layer thickness varies from 0.30m near walls to 0.50m at center of room | Report_2023.pdf | | |

**Multi-source / Combiner example** (COMBINER_REASONING filled):

| US_ID | PROPERTY_TYPE | VALUE | COMBINER_REASONING | EXTRACTOR_1 | DOCUMENT_1 | EXTRACTOR_2 | DOCUMENT_2 |
|-------|---------------|-------|--------------------|-------------|------------|-------------|------------|
| USM01 | Material | Tufo giallo napoletano | Isotopic signature matches Campi Flegrei yellow tuff. Visual confirmation of characteristic golden-yellow color and porous texture of blocks. | Isotopic analysis of block samples shows Campi Flegrei provenance signature with matching trace element ratios | isotopic_report_042.pdf | Visual inspection reveals characteristic golden-yellow color and porous vesicular texture consistent with Neapolitan yellow tuff | field_notes_day5.pdf |

---

## Usage with Existing GraphML

If you already have a GraphML file and want to enrich it with data extracted from new documents, add this instruction to the prompt:

```
I already have a GraphML with the following stratigraphic units: [list unit IDs].
Please check if any of the units you extract from this document match existing ones.
If they match, use the SAME ID. If they are new units not in the GraphML, mark them clearly.
For existing units, focus on extracting additional relationships and properties
that may be missing from the current graph.
```

---

## Import Workflow

1. Copy the Part A table output into Excel → save as `stratigraphy.xlsx` (sheet: "Stratigraphy")
2. Copy the Part B table output into Excel → save as `em_paradata.xlsx` (sheet: "Paradata")
3. Use s3Dgraphy's `MappedXLSXImporter` with mapping `excel_to_graphml_mapping` to import stratigraphy.xlsx → generates GraphML
4. Use EMtools (Blender) "XLSX → GraphML Converter" operator — optionally specify `em_paradata.xlsx` to enrich with provenance in a single step
5. Alternatively, import GraphML first, then use "Bake Paradata into GraphML" operator to add paradata to an existing GraphML file

---

## Customization

### Specifying Output Language

Add to the prompt: `Write all descriptions and properties in [language].`

### Processing Multiple Documents

For multi-document projects, process each document separately then merge the tables. Ensure ID consistency across documents. Use the "existing GraphML" instruction above to maintain coherence with previously extracted data.

### Adding Extra Extractor/Document Pairs

The em_paradata format supports unlimited EXTRACTOR_N/DOCUMENT_N column pairs. If a property derives from 3 or more sources, simply add EXTRACTOR_3/DOCUMENT_3, EXTRACTOR_4/DOCUMENT_4, etc. The QualiaImporter automatically detects all pairs via column name pattern matching.
