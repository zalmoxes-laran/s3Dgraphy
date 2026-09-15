"""L'identità di un artefatto e quanto è forte — **ora in `dtcstamp`**.

Questo modulo non contiene più la regola: la **importa**. Il contenuto è
traslocato nella libreria del formato, che è un file solo senza dipendenze,
perché chi scrive un addon per Blender o uno script per Metashape non installerà
mai s3Dgraphy per sapere se un digest dimostra o confronta.

Il nome resta qui, e non è cortesia verso il passato: `from s3dgraphy.stamp
import identity` è un import che qualcuno ha scritto, e romperlo per spostare un
file sarebbe far pagare a chi chiama una riorganizzazione che non lo riguarda.

**La regola sta in un posto solo.** Se un giorno una di queste funzioni venisse
riscritta qui invece che là, sarebbe due fonti per un fatto solo — ed è
esattamente il difetto che l'estrazione esiste per togliere di mezzo.
"""

from dtcstamp import (COMPARABLE, COMPARABLE_SCHEMES, UNKNOWN, VERIFIABLE,
                      VERIFIABLE_SCHEMES, describe_identity, identity_strength,
                      is_comparable, is_verifiable, split_identity)

__all__ = [
    "COMPARABLE", "COMPARABLE_SCHEMES", "UNKNOWN", "VERIFIABLE",
    "VERIFIABLE_SCHEMES", "describe_identity", "identity_strength",
    "is_comparable", "is_verifiable", "split_identity",
]
