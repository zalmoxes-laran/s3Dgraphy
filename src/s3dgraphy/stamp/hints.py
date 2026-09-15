"""Le piste — **ora in `dtcstamp`**.

«Ho visto questo digest in questo posto, in questo momento»: un registro
mutevole, plurale e non autorevole, in un file separato e mai coperto da nessun
digest. Non ha mai avuto bisogno di un grafo — leggeva soltanto `now_iso` da
`editorial`, due righe di `datetime` — e quindi è traslocato per intero nella
libreria del formato insieme a quella funzione.

Il nome resta qui perché `from s3dgraphy.stamp import hints` è un import che
esiste, e una prova di questo repo interroga proprio **questo modulo** per
verificare un'assenza di superficie: che non esponga né un `forget`, né un
`prune`, né un `fix`. Le piste non si cancellano, invecchiano — e la prova
continua a misurarlo qui, perché è qui che qualcuno andrebbe ad aggiungerlo.

`scope_for` e `kind_for` non erano nell'elenco pubblico del pacchetto e restano
raggiungibili da questo modulo, come prima.
"""

from dtcstamp import (HINTS_SUFFIX, HINTS_VERSION, KNOWN_KINDS, SCOPES,
                      file_digest, for_export, hints_filename, kind_for,
                      new_hints, note_seen, private_locators, read_hints,
                      scan_directory, scope_for, write_hints,
                      write_public_hints)

__all__ = [
    "HINTS_SUFFIX", "HINTS_VERSION", "KNOWN_KINDS", "SCOPES", "file_digest",
    "for_export", "hints_filename", "kind_for", "new_hints", "note_seen",
    "private_locators", "read_hints", "scan_directory", "scope_for",
    "write_hints", "write_public_hints",
]
