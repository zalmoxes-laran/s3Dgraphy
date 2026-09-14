"""Il **timbro**: il verbale immutabile di un passo, scritto per stare da solo.

Un agente, con un processo e dei parametri, consuma uno o più ingressi e produce
**un** artefatto. Non è un formato nuovo e non introduce nessun tipo di nodo: i
nodi che cita — risorsa, processo con parametri, agente, licenza, embargo — sono
già tipi di s3Dgraphy, e il substrato DTC (`nodes/dtc_node.py`) dice da sempre che
«one node = a Chunk; the assembled provenance = a Chain». **Il timbro è quel
chunk, scritto per uscire dal perimetro.**

Tre moduli e una divisione che è un contratto:

* :mod:`.emit` — grafo → timbro. Funzione **pura**: niente filesystem, niente
  orologio. Chi scrive su disco è un'altra funzione.
* :mod:`.absorb` — timbro → grafo, come **merge per UUID** (quello che la
  libreria già fa, `container.merge_graph_into`). Due timbri che si
  contraddicono nella sostanza non sono un errore: sono una scoperta, e qui
  **non si sceglie un vincitore**.
* :mod:`.hints` — le piste, che sono un'altra cosa: un registro mutevole, plurale
  e non autorevole, in un file separato e **mai coperto da nessun digest**. Una
  pista `private` non esce mai.
* :mod:`.identity` — quanto è forte un'identità: `sha256:` **dimostra**,
  `emstruct1:` **confronta**. La differenza fra «è lei» e «è cambiata», chiesta a
  una funzione invece che a un `startswith`.

I nomi dei file sono `<asset>.stamp.json` e `<asset>.hints.json`, in inglese
perché escono da casa nostra. Non `em.json` (specie diversa: inviterebbe a
fondere, editare, versionare un verbale) e non `dtc.json` (prometterebbe una
catena e consegna un anello).
"""

from .absorb import (AbsorbResult, BadStamp, Disagreement, absorb_stamp,
                     absorb_stamp_file, compare_stamps, read_stamp,
                     stamp_to_graph, substance, validate_stamp)
from .emit import (NotAnArtifact, STAMP_VERSION, clean_stamp, emit_stamp,
                   is_verifiable_stamp, stamp_filename, stamp_identity,
                   write_stamp)
from .hints import (HINTS_VERSION, file_digest, for_export, hints_filename,
                    new_hints, note_seen, private_locators, read_hints,
                    scan_directory, write_hints, write_public_hints)
from .identity import (COMPARABLE, UNKNOWN, VERIFIABLE, describe_identity,
                       identity_strength, is_comparable, is_verifiable,
                       split_identity)

__all__ = [
    "AbsorbResult", "BadStamp", "COMPARABLE", "Disagreement", "HINTS_VERSION",
    "NotAnArtifact", "STAMP_VERSION", "UNKNOWN", "VERIFIABLE", "absorb_stamp",
    "absorb_stamp_file", "clean_stamp", "compare_stamps", "describe_identity",
    "emit_stamp", "file_digest", "for_export", "hints_filename",
    "identity_strength", "is_comparable", "is_verifiable",
    "is_verifiable_stamp", "new_hints", "note_seen", "private_locators",
    "read_hints", "read_stamp", "scan_directory", "split_identity",
    "stamp_filename", "stamp_identity", "stamp_to_graph", "substance",
    "validate_stamp", "write_hints", "write_public_hints", "write_stamp",
]
