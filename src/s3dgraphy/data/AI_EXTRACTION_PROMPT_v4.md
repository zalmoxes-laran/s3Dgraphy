# EM Extraction Prompt — v4.1
**Extended Matrix (EM) — Tempio Grande, Sarmizegetusa Regia**
*Version: 4.1 | Date: 2026-02-26 | Author: Emanuel Demetrescu*

---

<!-- SECTION: PREAMBLE -->
## PREAMBLE

**Lingua di lavoro:** `[LINGUA]`
Tutto il testo estratto (VALUE, COMBINER_REASONING, citazioni verbatim) deve essere scritto nella lingua del documento sorgente (romeno, italiano, francese, latino). I valori di PROPERTY_TYPE restano in inglese.

**Contesto tecnico:** Questo prompt è progettato per essere usato con la libreria `openpyxl` in Python 3. Le righe di output sono costruite come liste di lunghezza fissa e aggiunte al foglio attivo. Le righe Paradata devono avere esattamente 14 colonne; le righe Stratigrafia esattamente 24 colonne.

**Doppio controllo obbligatorio prima del salvataggio:**
1. Ogni riga Paradata ha esattamente 14 colonne; ogni riga Stratigrafia esattamente 24 colonne.
2. I campi EXTRACTOR_N e DOCUMENT_N sono sempre accoppiati.
3. Se è presente più di un EXTRACTOR, COMBINER_REASONING (col 4) è **obbligatorio**.
4. Ogni VALUE e ogni citazione EXTRACTOR è tratta da un passo reale della fonte; nessuna parafrasi, nessuna invenzione.
5. Per la stessa coppia (US_ID, PROPERTY_TYPE) esiste **una sola riga** nel foglio Paradata.

---

<!-- SECTION: PART_A -->
## PARTE A — ESTRAZIONE STRATIGRAFIA

### A.1 — File di output: `stratigraphy.xlsx` (foglio: `Stratigraphy`)

#### Schema delle colonne (24 colonne, 1-based)

| # | Colonna | Note |
|---|---------|------|
| 1 | ID | Identificatore univoco, es. `C01`, `TM_USM01` |
| 2 | TYPE | Uno tra: US, USVs, USVn, SF, VSF, USD, serSU, serUSD, serUSVn, serUSVs, TSU, SE, BR |
| 3 | DESCRIPTION | Descrizione breve in lingua del sito |
| 4 | PERIOD | Etichetta descrittiva (es. "Roman Imperial"). **Non usata per il layout della matrice.** |
| 5 | PERIOD_START | Anno numerico (negativo = a.C.) |
| 6 | PERIOD_END | Anno numerico |
| 7 | **PHASE** | **Usata per il layout swimlane della matrice.** Deve essere uno dei cinque codici di fase (§A.2). Obbligatoria per ogni US. |
| 8 | PHASE_START | Anno iniziale della fase |
| 9 | PHASE_END | Anno finale della fase |
| 10 | SUBPHASE | Sottofase, opzionale |
| 11 | SUBPHASE_START | Opzionale |
| 12 | SUBPHASE_END | Opzionale |
| 13 | OVERLIES | ID separati da virgola |
| 14 | OVERLAIN_BY | ID separati da virgola |
| 15 | CUTS | ID separati da virgola |
| 16 | CUT_BY | ID separati da virgola |
| 17 | FILLS | ID separati da virgola |
| 18 | FILLED_BY | ID separati da virgola |
| 19 | ABUTS | ID separati da virgola |
| 20 | ABUTTED_BY | ID separati da virgola |
| 21 | BONDED_TO | ID separati da virgola (bidirezionale) |
| 22 | EQUALS | ID separati da virgola (bidirezionale). Vedere §A.5. |
| 23 | EXTRACTOR | **Citazione verbatim + puntatore di pagina/figura** dal passo sorgente che giustifica la definizione dell'unità (vedere regola sotto). |
| 24 | DOCUMENT | Codice del documento sorgente + autore abbreviato, es. `D.05 Diaconescu 2013` |

**Regola per il campo EXTRACTOR (col 23):** Deve contenere una citazione verbatim nella lingua della fonte, seguita da un puntatore in parentesi quadre, es. `"Groapă de dimensiuni mici, care taie C02" [p. 5]`. Per le unità virtuali (§A.6), la stringa termina con `[ID virtuale EM AAAA-MM-GG]`. Il campo non deve mai contenere solo il nome di un ricercatore o del sistema di estrazione.

---

### A.2 — Fasi non sovrapposte (PHASE)

Il campo PHASE guida il layout swimlane della matrice. **Tutte le fasi devono essere non sovrapposte.** Usare esclusivamente i seguenti cinque codici:

| Codice | Etichetta | PHASE_START | PHASE_END | Unità incluse (esempi) |
|--------|-----------|-------------|-----------|------------------------|
| PH0 | PH0 – Pre-Roman | -100 | 107 | C05, C12 |
| PH1 | PH1 – Early Roman / ante-temple | 108 | 149 | TM_S1, C02, C03, C04 |
| PH2 | PH2 – Temple construction and use | 150 | 270 | TM_USM01–08, C01, C06, TM_SF01, TM_SF02, TM_CANALE_FASE2, TM_SE_DESTRUCTION170, TM_VESTIBULUM, TM_PRONAOS, TM_NAOS, TM_CUBICULA |
| PH3 | PH3 – Post-Roman disturbance | 271 | 1974 | C07, C08, C09, TM_US08 |
| PH4 | PH4 – Modern archaeological documentation | 1975 | 2015 | C10, C11 |

Per aggiungere nuove fasi è necessario prima documentarle nel foglio `ParadataEpochs` (§C).

---

### A.3 — Regole di simmetria dei rapporti

| Rapporto | Direzione | Inverso richiesto |
|---|---|---|
| OVERLIES | A → B | B.OVERLAIN_BY deve contenere A |
| CUTS | A → B | B.CUT_BY deve contenere A |
| FILLS | A → B | B.FILLED_BY deve contenere A |
| ABUTS | A → B | B.ABUTTED_BY deve contenere A |
| BONDED_TO | bidirezionale | B.BONDED_TO deve contenere A |
| EQUALS | bidirezionale | B.EQUALS deve contenere A |

---

### A.4 — Validazione finale dei rapporti stratigrafici

<!-- FLAG: VALIDAZIONE_FINALE -->
Eseguire questo script Python prima del salvataggio. Correggere ogni problema segnalato. I risultati vengono scritti nel foglio `StratValidation` di `stratigraphy.xlsx`.

```python
from openpyxl import load_workbook

COL_IDX = {
    'ID': 0, 'PHASE': 6,
    'OVERLIES': 12, 'OVERLAIN_BY': 13, 'CUTS': 14, 'CUT_BY': 15,
    'FILLS': 16, 'FILLED_BY': 17, 'ABUTS': 18, 'ABUTTED_BY': 19,
    'BONDED_TO': 20, 'EQUALS': 21,
}

wb = load_workbook('stratigraphy.xlsx')
ws = wb['Stratigraphy']

rows_by_id = {}
for row in ws.iter_rows(min_row=2):
    if row[COL_IDX['ID']].value:
        rows_by_id[row[COL_IDX['ID']].value] = row

def get_rel(us_id, rel):
    row = rows_by_id.get(us_id)
    if not row: return []
    val = row[COL_IDX[rel]].value
    return [v.strip() for v in str(val).split(',')] if val else []

symmetric_pairs = [
    ('OVERLIES','OVERLAIN_BY'), ('CUTS','CUT_BY'),
    ('FILLS','FILLED_BY'),      ('ABUTS','ABUTTED_BY'),
]
bidirectional = ['BONDED_TO', 'EQUALS']
issues = []

for us_id in rows_by_id:
    if not rows_by_id[us_id][COL_IDX['PHASE']].value:
        issues.append(f'MISSING_PHASE: {us_id}')
    for t in get_rel(us_id, 'OVERLIES'):
        if us_id in get_rel(t, 'OVERLIES'):
            issues.append(f'CIRCULAR: {us_id} ↔ {t}')
    for fwd, inv in symmetric_pairs:
        for t in get_rel(us_id, fwd):
            if t not in rows_by_id:
                issues.append(f'BROKEN_REF: {us_id}.{fwd} → {t}')
            elif us_id not in get_rel(t, inv):
                issues.append(f'ASYMMETRIC: {us_id}.{fwd}={t} ma {t}.{inv} manca {us_id}')
    for rel in bidirectional:
        for t in get_rel(us_id, rel):
            if us_id not in get_rel(t, rel):
                issues.append(f'ASYMMETRIC_BIDI: {us_id}.{rel}={t} ma {t}.{rel} manca {us_id}')

if issues:
    print(f"VALIDAZIONE FALLITA — {len(issues)} problema/i:")
    for i in issues: print(' ', i)
else:
    print("Validazione OK — zero errori.")
```
<!-- /FLAG: VALIDAZIONE_FINALE -->

---

### A.5 — Protocollo EQUALS

EQUALS collega due US distinte che rappresentano la **stessa entità fisica** documentata indipendentemente da campagne di scavo o ricercatori diversi.

**Quando usare EQUALS:**
- Due campagne hanno assegnato codici diversi alla stessa deposito, muro o struttura.
- Una ricerca archivistica successiva conferma l'identità (non solo la somiglianza) di due unità separate.

**Quando NON usare EQUALS:**
- Due descrizioni della stessa unità in due fonti diverse (quelle vanno in righe multi-sorgente nella Paradata).
- Unità spazialmente vicine o funzionalmente simili ma non dimostratamente identiche.
- Identificazioni speculative non documentate in almeno una fonte.

**Obbligo di documentazione:** Ogni relazione EQUALS deve avere almeno una riga `stratigraphic_note` nel foglio Paradata che ne spiega l'identificazione, con citazione verbatim o riferimento incrociato esplicito. Se l'identificazione è un'inferenza editoriale, aggiungere una riga `unit_id_note`.

---

### A.6 — Politica degli ID virtuali

Alcuni ID US di questo dataset sono **identificatori virtuali** assegnati dalla sessione di documentazione EM, non usati nei rapporti di scavo originali (es. TM_USM01–08, TM_VESTIBULUM, TM_PRONAOS, TM_NAOS, TM_CUBICULA, TM_CANALE_FASE2, TM_SE_DESTRUCTION170, TM_SF01, TM_SF02).

Questa situazione emerge quando i documenti storici descrivono strutture reali senza assegnare loro una numerazione sistematica delle unità stratigrafiche.

**Obblighi per le unità virtuali:**
1. Il campo EXTRACTOR (col 23) deve includere il passo verbatim che meglio supporta la definizione dell'unità, seguito da `[ID virtuale EM AAAA-MM-GG]`.
2. Il foglio Paradata deve contenere una riga `unit_id_note` che spiega il ragionamento identificativo e precisa che gli autori originali non usano questo ID.
3. L'unità stratigrafica fisica è reale; solo il codice identificativo è nostro.
4. Se una campagna successiva ha documentato la stessa struttura con un codice diverso, aggiungere una relazione EQUALS con la riga `stratigraphic_note` di supporto.

**Naming convention per unità non numerate:**
- Usare il prefisso della campagna + tipo + numero progressivo nella serie: `TM_USM08`, `TM_US09`, ecc.
- Non inventare suffissi di fase nel nome dell'ID (es. evitare `TM_USM05_FASE2`): ogni fase di un elemento è una US propria con il suo ID nella serie.

---

<!-- /SECTION: PART_A -->

<!-- SECTION: PART_B -->
## PARTE B — ESTRAZIONE PARADATA

### B.1 — File di output: `em_paradata.xlsx` (foglio: `Paradata`)

#### Schema delle colonne (14 colonne, fisse)

| # | Colonna | Note |
|---|---------|------|
| 1 | US_ID | Deve corrispondere a un ID nel foglio Stratigraphy |
| 2 | PROPERTY_TYPE | Vocabolario controllato (§B.2) |
| 3 | VALUE | Il valore estratto |
| 4 | COMBINER_REASONING | **Obbligatorio** se EXTRACTOR_2 è popolato |
| 5 | EXTRACTOR_1 | Citazione verbatim + puntatore pagina/figura dalla fonte 1 |
| 6 | DOCUMENT_1 | Codice documento + autore abbreviato |
| 7–14 | EXTRACTOR_2–5 / DOCUMENT_2–5 | Fonti aggiuntive se pertinenti |

### B.2 — Vocabolario controllato PROPERTY_TYPE

**Geometria / dimensioni:** `length`, `width`, `height`, `thickness_min`, `thickness_max`, `area`, `depth_from_surface`, `foundation_offset`

**Materiale / tecnica:** `material_type`, `construction_technique`, `mortar_type`, `color`, `texture`, `surface_treatment`

**Cronologia:** `absolute_time_start`, `absolute_time_end`, `terminus_post_quem`, `terminus_ante_quem`, `period_interpretation`

**Interpretazione:** `function_interpretation`, `primary_function`, `cult_interpretation`, `phase_interpretation`, `construction_phase`

**Flag editoriali:**
- `ocr_error_note` — errore OCR identificato e corretto in un'altra riga
- `unit_id_note` — documenta che l'ID è virtuale (assegnato dalla sessione EM, non dagli scavatori originali)
- `stratigraphic_note` — documenta un'identificazione EQUALS o un ragionamento stratigrafico complesso

### B.3 — Regola anti-duplicati

Per ogni coppia (US_ID, PROPERTY_TYPE) deve esistere **esattamente una riga** nel foglio Paradata.

Quando una seconda fonte fornisce lo stesso dato per la stessa unità: non aggiungere una nuova riga. Aggiornare la riga esistente aggiungendo EXTRACTOR_2 / DOCUMENT_2 e compilando COMBINER_REASONING.

Se i valori di due fonti riflettono due fasi costruttive distinte della stessa struttura fisica, queste appartengono a **due US separate** (ciascuna con il suo ID e le sue proprietà), non a due righe della stessa US.

### B.4 — Regola multi-sorgente

Quando EXTRACTOR_2 è popolato: DOCUMENT_2 deve essere popolato; COMBINER_REASONING è obbligatorio (indica se le fonti concordano, divergono parzialmente, o si contraddicono; quale valore è stato scelto come canonico e perché).

### B.5 — Protocollo errori OCR

1. Usare il valore corretto in VALUE.
2. Aggiungere una riga separata: `PROPERTY_TYPE = ocr_error_note`, `VALUE = <testo OCR errato>`.
3. Riferimento incrociato tra le due righe in COMBINER_REASONING.

<!-- /SECTION: PART_B -->

<!-- SECTION: PART_C -->
## PARTE C — PARADATA DELLE EPOCHE

### C.1 — File di output: `em_paradata.xlsx` (foglio: `ParadataEpochs`)

Stesso schema a 14 colonne del foglio `Paradata`, ma la prima colonna è **`epoch_ID`** (non `US_ID`). Ogni epoca deve avere righe per:

| PROPERTY_TYPE | Contenuto |
|---|---|
| `epoch_label` | Etichetta leggibile |
| `epoch_start` | Anno iniziale come stringa, es. `150 d.C.` |
| `epoch_end` | Anno finale come stringa |
| `epoch_start_rationale` | Giustificazione con citazione verbatim |
| `epoch_end_rationale` | Giustificazione con citazione verbatim |
| `epoch_internal_event` | (opzionale) Evento interno notevole con fonte |
| `epoch_campaign_N` | (opzionale) Campagne di documentazione nell'epoca |

Ogni nuova epoca deve essere giustificata qui **prima** di poter essere assegnata a una US.

<!-- /SECTION: PART_C -->

<!-- SECTION: PART_D -->
## PARTE D — LISTA DELLE FONTI

### D.1 — File di output: `GreatTemple_sources_list.xlsx`

| # | Colonna | Note |
|---|---------|------|
| 1 | Name | Codice, es. `D.01` |
| 2 | Description | Titolo / descrizione breve |
| 3 | Url | Riferimento bibliografico completo o DOI; percorso file per documenti inediti |
| 4 | Property that can validate | Elenco libero dei PROPERTY_TYPE che questa fonte può supportare |
| 5 | original id. | Identificatore originale del documento, se applicabile |
| 6 | Type | Uno tra: 3D, PDF, PDF (scanned), PDF (unpublished), Image, Text |
| 7 | Preview | Percorso o URL del thumbnail (opzionale) |

I codici D.01–D.09 sono riservati al corpus originale; D.10+ per fonti aggiuntive.

<!-- /SECTION: PART_D -->

<!-- SECTION: CHECKLIST -->
## PARTE E — CHECKLIST DI FINE SESSIONE

**Stratigrafia**
- [ ] Ogni US ha PHASE non nullo, scelto tra PH0–PH4.
- [ ] Ogni unità virtuale ha una riga `unit_id_note` in Paradata e un campo EXTRACTOR con citazione verbatim + `[ID virtuale EM AAAA-MM-GG]`.
- [ ] Il campo EXTRACTOR (col 23) contiene citazione verbatim + puntatore per ogni US; mai solo `"Claude"` o un nome di ricercatore.
- [ ] Il campo DOCUMENT (col 24) contiene il codice documento sorgente; mai `"Claude"`.
- [ ] Ogni relazione EQUALS ha una riga `stratigraphic_note` o `unit_id_note` di supporto in Paradata.

<!-- FLAG: VALIDAZIONE_FINALE -->
- [ ] Lo script di validazione (§A.4) riporta zero errori; foglio `StratValidation` rigenerato.
<!-- /FLAG: VALIDAZIONE_FINALE -->

**Paradata**
- [ ] Nessuna coppia duplicata (US_ID, PROPERTY_TYPE) nel foglio Paradata.
- [ ] Tutte le righe multi-sorgente hanno COMBINER_REASONING compilato.
- [ ] Ogni campo EXTRACTOR_N contiene citazione verbatim + puntatore.
- [ ] Gli errori OCR sono documentati con righe `ocr_error_note`.
- [ ] Le righe Paradata hanno esattamente 14 colonne.

<!-- SECTION: PART_C -->
**Epoche**
- [ ] Ogni nuova epoca è documentata in `ParadataEpochs` prima dell'uso.
<!-- /SECTION: PART_C -->

<!-- SECTION: PART_D -->
**Fonti**
- [ ] Le nuove fonti sono aggiunte a `GreatTemple_sources_list.xlsx` con dati bibliografici completi.
<!-- /SECTION: PART_D -->

<!-- /SECTION: CHECKLIST -->

---

*Fine del prompt di estrazione EM v4.1*
