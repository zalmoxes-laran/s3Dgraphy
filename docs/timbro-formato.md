---
orphan: true
---

# Il timbro — la specifica sta altrove

Il formato è specificato nella libreria che lo implementa: **`dtcstamp`**,
`stamp-format.md` ([il repo](https://github.com/), da pubblicare — per ora il
checkout accanto a questo).

Una specifica appartiene alla libreria che la implementa, e questa ha smesso di
stare qui il 15-09-2026, quando il formato è uscito di casa: leggere, scrivere,
validare, confrontare e risalire sono un modulo solo senza dipendenze, perché chi
scrive un addon per Blender o uno script per Metashape non installerà mai pandas
per scrivere due kilobyte di JSON.

Qui restano le due cose che hanno bisogno di un **grafo**: `s3dgraphy.stamp.emit`
(grafo → timbro) e `s3dgraphy.stamp.absorb` (timbro → grafo). Il protocollo
dell'**attribuzione** — chi dichiara che cosa, e la distinzione fra l'autore e
l'attributore — è invece di casa qui: `docs/asset-dtc-protocol.md`.
