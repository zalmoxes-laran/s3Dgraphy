# Template per generazione em_paradata.xlsx

Questo documento descrive il formato del file `em_paradata.xlsx` per agenti AI e operatori umani.

## Formato file
- File Excel (.xlsx)
- Foglio: "Paradata"
- Intestazione in riga 1, dati da riga 2

## Colonne

| Colonna | Tipo | Obbligatorio | Descrizione |
|---------|------|-------------|-------------|
| US_ID | string | SI | ID dell'unita stratigrafica (deve corrispondere a un ID in stratigraphy.xlsx) |
| PROPERTY_TYPE | string | SI | Tipo di proprieta dal vocabolario EM (vedi lista sotto) |
| VALUE | string | SI | Valore della proprieta |
| EXTRACTOR | string | SI | Testo specifico estratto dal documento sorgente. NON e' l'autore/agente. |
| DOCUMENT | string | SI* | Nome del documento sorgente. *Vuoto se si usa il combiner. |
| COMBINER_REASONING | string | NO | Se presente: il VALUE deriva da ragionamento combinato multi-fonte. |
| COMBINER_SOURCE_1 | string | NO | Prima fonte del ragionamento combinato |
| COMBINER_SOURCE_2 | string | NO | Seconda fonte del ragionamento combinato |

## Regole di compilazione

### 1. Una riga per proprieta
Ogni coppia (US, proprieta) e' una riga. Se USV101 ha 3 proprieta, ci sono 3 righe.

### 2. EXTRACTOR NON e' l'agente
L'extractor e' il testo/osservazione specifico estratto dalla fonte, non l'identita dell'agente AI o umano.

Corretto:
- "Layer of yellow tuff blocks with irregular mortar joints, thickness 15-20cm"
- "Measured from 3D model base to top: 2.50m +/- 0.05m"

Sbagliato:
- "Claude"
- "GPT-4"
- "Manual"

### 3. DOCUMENT e' una fonte specifica
Nome file o riferimento bibliografico preciso.

Corretto:
- "excavation_report_2024.pdf"
- "Rossi2019_fig12.pdf"
- "field_notes_day5.pdf"

Sbagliato:
- "Various sources"
- "Field documentation"
- "GraphML + PDF Documentation"

### 4. Combiner (multi-source)
Usare quando il valore della proprieta deriva dalla combinazione di piu' fonti.

Esempio: Material = "Tufo giallo napoletano" deriva da:
- Analisi isotopica (isotopic_analysis_042.pdf)
- Ispezione visiva sul campo (field_notes_day5.pdf)

Compilazione:
- VALUE: "Tufo giallo napoletano"
- EXTRACTOR: "Material identified by combining isotopic analysis results (Campi Flegrei signature) with visual inspection of block color and texture"
- DOCUMENT: (vuoto)
- COMBINER_REASONING: "Isotopic signature matches Campi Flegrei yellow tuff. Visual confirmation of characteristic golden-yellow color and porous texture of blocks."
- COMBINER_SOURCE_1: "isotopic_analysis_042.pdf"
- COMBINER_SOURCE_2: "field_notes_day5.pdf"

### 5. Vocabolario proprieta (da em_qualia_types.json)

**Physical & Material:**
- Height, Width, Length, Thickness, Depth, Weight, Diameter
- Material, Origin Type, Surface Treatment, Granulometry
- Conservation State, Integrity
- Construction Technique (= Building Technique)

**Spatiotemporal:**
- Absolute Position, Orientation, Elevation, Arrangement
- Absolute Start Date, Absolute End Date, Dating Method

**Functional:**
- Primary Function, Secondary Functions, Structural Role

**Cultural & Interpretive:**
- Artistic Style, Stylistic Influences

**Contextual:**
- Inventory Number, Legal Status

## Differenza tra em_paradata.xlsx e site_properties.xlsx

| | em_paradata.xlsx | site_properties.xlsx |
|---|---|---|
| Formato | Long (1 riga per proprieta) | Wide (1 riga per US, colonne per proprieta) |
| Provenance | Per-proprieta (extractor + document) | Globale (SOURCE_PDF, SOURCE_PAGE) |
| Nel GraphML | "Baked" come ParadataNodeGroup | Non incluso (dati volatili) |
| Combiner | Supportato | Non supportato |
| Uso tipico | Import AI con provenance | Compilazione manuale/GIS |
