# AI-Assisted Stratigraphic Data Extraction

## Overview

This document contains a ready-to-use prompt for extracting archaeological stratigraphic data from PDF reports, field notes, images, and other documentation using AI assistants (Claude, ChatGPT, Gemini, etc.).

The extraction produces **two standardized Excel files**:

1. **stratigraphy.xlsx** (sheet: "Stratigraphy") — Core stratigraphic data for generating the Extended Matrix GraphML
2. **site_properties.xlsx** (sheet: "Properties") — Site-specific properties imported as auxiliary data to enrich the graph

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

## Prompt — Part B: Site Properties Extraction

After Part A is complete, use this prompt to extract additional site-specific properties.

---

### PROMPT START (Part B)

```
Now extract site-specific properties for the same stratigraphic units. Produce a SECOND markdown table with the following columns. This table will be imported as an auxiliary file (sheet name "Properties") to enrich the graph with detailed attributes.

## Column Schema

| Column | Required | Type | Description |
|--------|----------|------|-------------|
| ID | YES | text | Same ID as in the stratigraphy table (must match exactly). |
| DEFINITION | no | text | Synthetic definition (e.g., "Wall", "Floor", "Fill", "Cut", "Deposit", "Threshold"). |
| INTERPRETATION | no | text | Functional interpretation in context (e.g., "Perimeter wall of room G", "Furnace for iron smithing"). |
| BUILDING_TECHNIQUE | no | text | Construction technique (e.g., "opus reticulatum", "dry stone", "brick masonry with lime mortar"). |
| INORGANIC_COMPONENTS | no | text | Inorganic materials (e.g., "limestone blocks, lime mortar, brick fragments"). |
| ORGANIC_COMPONENTS | no | text | Organic materials (e.g., "charcoal inclusions, wood fragments"). |
| MEASURES | no | text | Dimensions, free format (e.g., "2.30 x 0.55 x 1.20 m", "thickness: 0.15 m"). |
| MATERIAL | no | text | Primary material (e.g., "stone", "brick", "clay", "morite"). |
| COLOR | no | text | Color description (Munsell notation or descriptive, e.g., "10YR 5/3", "dark brown"). |
| CONSERVATION_STATE | no | text | State of conservation (e.g., "good", "partially collapsed", "heavily eroded"). |
| SITE | no | text | Name of the archaeological site. |
| AREA | no | text | Excavation area, sector, room, or functional unit identifier. |
| SOURCE_PDF | no | text | Source PDF filename. |
| SOURCE_PAGE | no | text | Page number(s) in the source PDF. |
| NOTES | no | text | Any additional notes or observations. |

## Important Notes

- Only include rows for units that have at least one property to report beyond the ID.
- The ID column MUST match exactly the IDs used in the stratigraphy table (Part A).
- You may add extra columns if the document contains relevant property types not listed above. If you do, describe the added columns.
- Use the same language as the source document for property values.
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

### Part B — Site Properties Table

| ID | DEFINITION | INTERPRETATION | BUILDING_TECHNIQUE | INORGANIC_COMPONENTS | ORGANIC_COMPONENTS | MEASURES | MATERIAL | COLOR | CONSERVATION_STATE | SITE | AREA | SOURCE_PDF | SOURCE_PAGE | NOTES |
|----|------------|----------------|--------------------|-----------------------|--------------------|----------|----------|-------|--------------------|------|------|------------|-------------|-------|
| USM01 | Wall | Northern perimeter wall of room A | opus incertum | limestone, lime mortar | | 3.20 x 0.60 x 1.80 m | stone | | good | Villa Romana | Room A | Report_2023.pdf | 12-14 | |
| USM02 | Floor | Main floor of room A | | brick tiles, mortar bed | | 4.50 x 3.20 m, thickness 0.08 m | brick | 10YR 6/4 | partially preserved | Villa Romana | Room A | Report_2023.pdf | 15 | |
| US03 | Destruction layer | Collapse event of upper structures | | limestone fragments, mortar, brick | charcoal | thickness 0.30-0.50 m | mixed | dark brown | | Villa Romana | Room A | Report_2023.pdf | 16-17 | Contains pottery fragments |
| USM04 | Wall | Eastern perimeter wall of room A | opus incertum | limestone, lime mortar | | 2.80 x 0.55 x 1.60 m | stone | | partially collapsed | Villa Romana | Room A | Report_2023.pdf | 14 | Bonded to USM01 |

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
2. Copy the Part B table output into Excel → save as `site_properties.xlsx` (sheet: "Properties")
3. Use s3Dgraphy's `MappedXLSXImporter` with mapping `excel_to_graphml_mapping` to import stratigraphy.xlsx → generates GraphML
4. Import the GraphML into EMtools (Blender)
5. Add `site_properties.xlsx` as an auxiliary file in EMtools (mapping: `site_properties_mapping`) → enriches nodes with detailed properties

---

## Customization

### Adding Project-Specific Columns (Part B)

The site properties template is intentionally flexible. For specialized projects, the AI may suggest additional columns based on the document content. For example, the Montebelluna metallurgical project added:

- METALLURGICAL_EVIDENCE
- SLAG_IDS
- POSITIVE_NEGATIVE
- ROOM_OR_FUNCTIONAL_UNIT

When adding custom columns, you will need a corresponding custom mapping JSON. The AI can generate one following the format in `s3dgraphy/mappings/emdb/site_properties_mapping.json`.

### Specifying Output Language

Add to the prompt: `Write all descriptions and properties in [language].`

### Processing Multiple Documents

For multi-document projects, process each document separately then merge the tables. Ensure ID consistency across documents. Use the "existing GraphML" instruction above to maintain coherence with previously extracted data.
