"""L'identità di un artefatto, e **quanto forte è** — che è una domanda a parte.

## Perché una funzione e non un `startswith`

La catena è forte all'estremità pubblicata e molle all'estremità autoriale. Un
file glTF in uno store ha byte canonici e il suo `sha256:` **dimostra che è lui**;
un datablock dentro un `.blend` non ha byte canonici — il file cambia per ragioni
che non c'entrano con quella mesh — e quello che si può calcolare è un'impronta
strutturale che basta ad **accorgersi che è cambiata**, non a verificare che è lei.

Il formato lo dichiara col prefisso: `emstruct1:` invece di `sha256:`. Ma un
consumatore che decidesse guardando dentro la stringa — `digest.startswith(...)`
sparso in cinque punti — è cinque posti dove la regola può divergere, e uno di
quei cinque prima o poi tratterà un'impronta strutturale come una prova. Quindi
una funzione sola, e questo modulo è quella funzione.

A valle governa **cosa un'interfaccia ha il diritto di affermare**: «verificato»
accanto a un `emstruct1:` è una bugia detta da un'icona.

## Tre risposte e non due, e la terza è la più importante

`verifiable` · `comparable` · `unknown`.

`unknown` esiste perché nel corpus reale i digest nudi ci sono: `promote_resource`
antepone `sha256:` a un esadecimale nudo *quando passa di lì*, ma un `checksum`
scritto a mano o arrivato da un importatore può essere sessantaquattro caratteri
e nient'altro. Chiamarlo `verifiable` sarebbe **indovinare l'algoritmo** e poi
affermarlo: si somiglia a uno sha256, quindi lo è. È esattamente il ragionamento
«ha un checksum, quindi è quello pubblicato» che `ResourceNode.TIERS` è nato per
togliere di mezzo, un piano più sotto.

Un'assenza invece non è `unknown`: è `None`. Non c'è nessuna identità di cui
misurare la forza, e restituire una parola dove non c'è una stringa farebbe
credere a chi legge che qualcosa sia stato detto.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

#: Impronte che **dimostrano**: c'è una sequenza di byte canonica e chiunque può
#: rifare il conto e ottenere lo stesso valore.
VERIFIABLE_SCHEMES = ("sha256",)

#: Impronte che **confrontano**: dicono se è cambiato, non se è lui. `emstruct1`
#: è l'impronta strutturale di un datablock (vertici, facce, bounding box, nomi
#: dei materiali, sulla mesh valutata) — il `1` è nel nome perché il giorno che
#: se ne calcola una diversa quella è `emstruct2`, e un vecchio timbro continua a
#: dire con che regola era stata presa la sua.
COMPARABLE_SCHEMES = ("emstruct1",)

VERIFIABLE = "verifiable"
COMPARABLE = "comparable"
UNKNOWN = "unknown"


def split_identity(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """`("sha256", "6e4a…")` — lo schema e il valore, o `(None, …)` se non c'è.

    Separata da :func:`identity_strength` perché chi scrive un timbro deve poter
    rimettere insieme i due pezzi, e ricomporli con un `:` a mano in due punti
    diversi è il modo in cui uno dei due un giorno perde il prefisso.
    """
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    if ":" not in text:
        return None, text
    scheme, _, rest = text.partition(":")
    scheme = scheme.strip().lower()
    rest = rest.strip()
    if not scheme or not rest:
        # `:abc` o `abc:` non sono uno schema e un valore: sono una stringa
        # malformata, e leggerla a metà sarebbe peggio che non leggerla.
        return None, text
    return scheme, rest


def identity_strength(value: Any) -> Optional[str]:
    """`verifiable`, `comparable`, `unknown` — oppure `None` se non c'è identità.

    La domanda è «dimostro che è lei» contro «mi accorgo se cambia», e va posta a
    questa funzione invece che alla stringa. Vedi il docstring del modulo per
    perché `unknown` non collassa su `verifiable`.
    """
    scheme, rest = split_identity(value)
    if rest is None:
        return None
    if scheme in VERIFIABLE_SCHEMES:
        return VERIFIABLE
    if scheme in COMPARABLE_SCHEMES:
        return COMPARABLE
    return UNKNOWN


def is_verifiable(value: Any) -> bool:
    """Se qualcuno può **rifare il conto** e dimostrare che sono quei byte.

    Falso per un'assenza e falso per un `unknown`: la domanda ha una sola
    risposta sicura, e in mancanza di quella la risposta è no.
    """
    return identity_strength(value) == VERIFIABLE


def is_comparable(value: Any) -> bool:
    """Se basta ad accorgersi che è cambiato — verificabile inclusa.

    **Una verificabile è anche confrontabile**, e questa riga è la ragione per
    cui la funzione esiste invece di essere `strength == "comparable"` scritto da
    chi chiama: chi vuole sapere «posso almeno accorgermi di una modifica?» deve
    ottenere `True` anche da uno sha256, e la domanda opposta si fa con
    :func:`is_verifiable`.
    """
    return identity_strength(value) in (VERIFIABLE, COMPARABLE)


def describe_identity(value: Any) -> Dict[str, Any]:
    """Quello che un'interfaccia ha il diritto di dire, in un dizionario.

    `claim` è la frase, e non è cortesia: il punto di tutto il modulo è che un
    pannello non scriva «verificato» accanto a un'impronta strutturale, e
    consegnargli la parola giusta è più efficace che sperare che la deduca.
    """
    scheme, rest = split_identity(value)
    strength = identity_strength(value)
    claim = {
        VERIFIABLE: "these are those bytes, and anyone can check",
        COMPARABLE: "this tells you if it changed, not that it is the same one",
        UNKNOWN: "an identity with no stated algorithm: not checkable",
        None: "no identity recorded",
    }[strength]
    return {"scheme": scheme, "value": rest, "strength": strength,
            "verifiable": strength == VERIFIABLE, "claim": claim}
