"""L'ora zero — dare una data a ciò che non ne ha, senza inventare un autore.

════════════════════════════════════════════════════════════════════════════════
## IL BUCO, CON IL SUO NUMERO

Il cruscotto di stanza, su un documento vero del corpus di sviluppo:

    sarmizegetusa:  1845 nodi  ·  1845 senza il nome di nessuno

Quei documenti vengono da conversioni GraphML e non portano né orologi né
autori. Misurato sul corpus intero (70 documenti):

    senza NESSUN orologio            7 documenti
    interamente timbrati            63 documenti   (nati in una stanza)
    parzialmente timbrati            0

    da timbrare:  2931 nodi  ·  8514 archi  ·  11 445 in tutto

**Non è una lacuna del modello: è una lacuna delle importazioni.** `crdt.py`
timbra un arco che nasce con un clock (`{"created_at": …, "created_by": …}`), e
un arco rimosso porta un tombstone che è un clock vero.

════════════════════════════════════════════════════════════════════════════════
## LA TRAPPOLA, E LE TRE REGOLE CHE LA EVITANO

Oggi due valori legacy che si incontrano danno `0, "unstamped"`: nessuno vince,
niente si muove, **e la ragione dice che non lo sappiamo**. `crdt.py:136` è
scrupoloso: *«a known instant beats an unknown one, and calling that "newer"
would claim we know something we do not»*.

Timbrare tutto con **un solo** T0 renderebbe quei valori simultanei, e a parità
di istante `compare_clocks` cade sul pareggio d'autore — *«an author that exists
beats one that does not»*, ragione `tie-author`. Si sarebbe convertito un onesto
«non lo so» in un arbitrario «vince il nome più piccolo in ordine alfabetico».

### 1 · T0 per IMPORTAZIONE, non globale

Due documenti importati in giorni diversi si ordinano correttamente fra loro.
Dentro un documento restano simultanei — e va bene, perché dentro un documento
non sappiamo davvero l'ordine.

### 2 · Il timbro NON porta un autore. Misurato, non scelto per gusto

Il prompt del 4 ottobre proponeva un `by` che nominasse l'importazione. **Non si
fa, e la ragione è un numero**: `roomview.statistics` conta «senza il nome di
nessuno» come *nodi senza `created_by`*, e con un `by` d'importazione

    sarmizegetusa   1845 → 0        il buco SPARISCE
    aiano            454 → 0

Il cruscotto direbbe «0 senza autore» mentre nessuno di quei nodi ha ancora un
autore **umano**: avremmo insegnato al cruscotto a tacere su un lavoro che resta
da fare. Un timbro d'importazione risolve la **sincronizzazione**, non
l'**autorialità**.

E non serve: `Clock.stamped` è `bool(self.ts)`. L'autore entra solo nel pareggio
a parità di istante, dove **due valori legacy senza autore pareggiano** — cioè
il «non lo so» sopravvive esattamente dove è vero.

Costa anche meno: sullo stesso documento, +14,3% di peso invece di +26,6%.

### 3 · Un timbro importato resta distinguibile da uno scritto

E lo è **per la sua forma**, senza vocabolario nuovo: misurato sul corpus,
`created_at` e `created_by` viaggiano sempre insieme — 3662 nodi su 3662, 1241
archi su 1241. Una data **senza** autore non esiste in natura in questi
documenti, quindi è la firma dell'importazione.

**È una firma implicita, e una firma implicita è una cosa che si rompe in
silenzio.** Se serve esplicita è una decisione di vocabolario, cioè di E.D.

════════════════════════════════════════════════════════════════════════════════
## IL CANCELLO CHE CONTA PIÙ DI TUTTI

> **T0 non deve MAI essere più tardo della prima scrittura vera in quella
> stanza.**

Se lo fosse, la timbratura farebbe **vincere il legacy sul lavoro delle
persone**, in silenzio, su tutto il corpus. È l'unico modo in cui questa
operazione può fare danno, e per questo `check_date` **alza** invece di
avvisare: un cancello che si può ignorare non è un cancello.

E la fonte che veniva prima in mente — la **mtime del file** — è
sistematicamente la peggiore possibile, misurato:

    basilica-demo   mtime 2026-09-05T23:29:14Z
                    operazione più VECCHIA nel registro  19:28:23.734Z
                    operazione più NUOVA                 23:29:14.389Z

La mtime di uno snapshot è **quando la stanza è stata salvata l'ultima volta**,
cioè l'istante dell'ultima scrittura. Per una stanza che qualcuno ha toccato è
per costruzione **più tarda di ogni scrittura vera che contiene**.

════════════════════════════════════════════════════════════════════════════════
## E ALLORA DA DOVE VIENE T0 — LA NASCITA DEL PROGRAMMA

La fonte che regge non descrive il file e non descrive la stanza: descrive il
**programma che ha prodotto il documento**. Nessun documento può essere più
vecchio del programma che lo ha scritto, quindi

> **T0 = l'istante in cui è nata la versione che compare in `header.generator`.**

è ≤ di ogni cosa che il documento contiene **per costruzione**, non per fortuna.
È una data più antica del vero — modesta — ed è **provabile in due pezzi**: la
versione sta dentro il documento, e la data di quella versione sta nella storia
del repo che l'ha rilasciata.

Misurato sul corpus, la candidata regge dove le altre no:

    fonte                    regge su   che cosa afferma
    ──────────────────────────────────────────────────────────────────────────
    generator + storia git      7 / 7   «prodotto da un programma che prima di
                                         questo istante non esisteva»
    sidecar più vecchio         5 / 7   «di questa stanza esisteva già un file»
    room.created_at             6 / 7   una DICHIARAZIONE, e nel corpus è un
                                        letterale a mezzanotte in tutti e 6
    prima operazione            1 / 7   è la prima scrittura, non la precede
    mtime del documento         4 / 7   l'ultimo salvataggio: la peggiore

`declared_generator` legge la prima metà — la versione — e **si ferma lì**.
Datare una versione vuole la storia di un repo, che questo modulo non ha e non
deve avere: la seconda metà la mette chi chiama.

════════════════════════════════════════════════════════════════════════════════
## CIÒ CHE NON È UNA DATA DI REGISTRAZIONE

Un documento EM è pieno di date, e quasi nessuna serve qui. Una `EpochNode`
porta `start_time` / `end_time`, e dicono **quando è esistita la cosa**, non
quando qualcuno l'ha scritta. Nel corpus:

    portamarina    EpochNode «IV d.C.»    start_time  300
    aiano          EpochNode «periodo 1 Fase 1»       350
    (minimo del corpus)                              -100

Usarne una come T0 metterebbe un timbro dell'anno 300 su un record del 2026 e
farebbe vincere il legacy su ogni scrittura futura, per sempre. Il cancello non
lo vedrebbe: 300 è ben *prima* di ogni scrittura vera, quindi `check_date`
tacerebbe.

**Il pericolo peggiore è quello che sembra plausibile**: `portamarina` ha una
`EpochNode` chiamata «y2018» che va da **1950 a 2018**. Un T0 di «2018» supera
qualunque controllo di buon senso di un essere umano — ed è la datazione di un
muro. Per questo `earliest_real_write` guarda **solo** `created_at`, e nessuna
euristica su «campi che sembrano date» entra in questo modulo.

*(La stessa trappola, dal vivo: il censimento con cui ho cercato le candidate
segnalava 28 «anni» in `aiano`. Erano `y_pos = 1982.62744140625`, la coordinata
verticale di un nodo sulla tela.)*
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: Dove sta il timbro di un nodo e dove quello di un arco. Due posti, e non uno.
NODE_DATA = "data"
EDGE_ATTRS = "attributes"
CREATED_AT = "created_at"
CREATED_BY = "created_by"

#: Gli orologi di campo, che **non si toccano**. Un nodo legacy ha il timbro di
#: nascita e nessun orologio di campo: inventarne uno per campo direbbe che ogni
#: campo è stato scritto in quell'istante, che è una bugia più grande di quella
#: che si sta evitando.
FIELD_CLOCKS_KEY = "field_clocks"


class RefusedDate(ValueError):
    """La data scelta cade dopo una scrittura vera. Si alza, non si avvisa."""


@dataclass
class Touched:
    """Esattamente cosa è stato toccato, per poterlo disfare.

    Non «quanti»: **quali**, e con quale forma. Un arco che non aveva
    `attributes` va riportato a non averlo, e un conteggio non basta a saperlo.
    """

    nodes: List[str] = field(default_factory=list)
    edges: List[str] = field(default_factory=list)
    #: gli archi a cui `attributes` è stato CREATO (metà dei legacy ce l'ha già,
    #: con dentro `original_edge_id` e compagnia: va integrato, non sostituito)
    edges_given_attributes: List[str] = field(default_factory=list)
    #: …e i nodi a cui è stato creato `data`
    nodes_given_data: List[str] = field(default_factory=list)
    at: Optional[str] = None
    by: Optional[str] = None

    @property
    def total(self) -> int:
        return len(self.nodes) + len(self.edges)


def _sections(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list((document.get("graphs") or {}).values())


def _edge_id(edge: Dict[str, Any]) -> str:
    return str(edge.get("id") or
               f"{edge.get('source')}__{edge.get('edge_type')}__{edge.get('target')}")


# ── guardare, prima di toccare ──────────────────────────────────────────────


def unstamped(document: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Gli id di quello che non porta un orologio: nodi e archi."""
    nodi, archi = [], []
    for section in _sections(document):
        for node in section.get("nodes") or []:
            data = node.get(NODE_DATA)
            if not (isinstance(data, dict) and data.get(CREATED_AT)):
                nodi.append(str(node.get("id")))
        for edge in section.get("edges") or []:
            attrs = edge.get(EDGE_ATTRS)
            if not (isinstance(attrs, dict) and attrs.get(CREATED_AT)):
                archi.append(_edge_id(edge))
    return nodi, archi


def declared_generator(document: Dict[str, Any]
                       ) -> Optional[Tuple[str, str]]:
    """Il programma che il documento dichiara di avere per padre: `(tool, versione)`.

    La metà di T0 che sta **dentro** il documento. L'altra metà — quando quella
    versione è nata — sta nella storia del repo che l'ha rilasciata, e non è
    affare di questo modulo: qui non si aprono repo.

    `None` quando il documento non lo dichiara, che nel corpus è il caso delle
    stanze generate da uno script di semina: lì la paternità si prova
    altrimenti (rigenerando il documento e confrontandolo), e resta più debole
    perché non è il documento a dirla.
    """
    header = document.get("header")
    if not isinstance(header, dict):
        return None
    generator = header.get("generator")
    if not isinstance(generator, dict):
        return None
    tool, version = generator.get("tool"), generator.get("version")
    if not tool or not version:
        return None
    return str(tool), str(version)


def earliest_real_write(document: Dict[str, Any],
                        operations: Optional[List[Dict[str, Any]]] = None,
                        *, room_created_at: Optional[str] = None
                        ) -> Optional[str]:
    """Il primo istante che qualcuno ha davvero scritto in questa stanza.

    Da tutte le fonti che lo sanno, e la più vecchia vince: il registro delle
    operazioni, i timbri che il documento porta già, e la nascita della stanza —
    che non è una scrittura ma la **limita**, perché nessuna scrittura può
    esserle precedente.

    `None` quando non si sa niente: e allora nessuna data può essere «troppo
    tarda», perché non c'è niente che possa perdere.
    """
    candidati: List[str] = []
    for op in operations or []:
        if isinstance(op, dict) and op.get("ts"):
            candidati.append(str(op["ts"]))
    for section in _sections(document):
        for node in section.get("nodes") or []:
            data = node.get(NODE_DATA)
            if isinstance(data, dict) and data.get(CREATED_AT):
                candidati.append(str(data[CREATED_AT]))
        for edge in section.get("edges") or []:
            attrs = edge.get(EDGE_ATTRS)
            if isinstance(attrs, dict) and attrs.get(CREATED_AT):
                candidati.append(str(attrs[CREATED_AT]))
    if room_created_at:
        candidati.append(str(room_created_at))
    return min(candidati) if candidati else None


def check_date(at: str, *, not_after: Optional[str], where: str = "") -> None:
    """Il cancello di §3. Alza `RefusedDate` se `at` cade dopo `not_after`.

    Alza e non avvisa, perché il danno che impedisce è silenzioso: un legacy che
    batte il lavoro di una persona non fa rumore, cambia solo cosa dice il
    grafo.
    """
    if not not_after:
        return
    if str(at) > str(not_after):
        raise RefusedDate(
            f"la data scelta ({at}) cade DOPO la prima scrittura vera "
            f"({not_after})"
            + (f" nella stanza «{where}»" if where else "")
            + ". Timbrare qui farebbe vincere il legacy sul lavoro delle "
              "persone, in silenzio. La fonte della data va scelta prima "
              "di quell'istante — la mtime di uno snapshot non va bene: è "
              "l'ora dell'ULTIMO salvataggio, quindi è più tarda di ogni "
              "scrittura che il documento contiene.")


# ── timbrare, e disfare ─────────────────────────────────────────────────────


def give_a_date(document: Dict[str, Any], at: str, *,
                by: Optional[str] = None,
                not_after: Optional[str] = None,
                where: str = "") -> Touched:
    """Metti `at` su tutto quello che non ha un orologio. **Modifica in luogo.**

    `by` è `None` di default, e la ragione è misurata nella testa del modulo: un
    autore d'importazione fa sparire il buco dell'autorialità invece di
    rinominarlo. Si può passare, e chi lo passa sa cosa sta comprando.

    Gli **orologi di campo non si toccano**: un nodo legacy ha un timbro di
    nascita e nessun orologio di campo, ed è la verità — inventarne uno per
    campo direbbe che ogni campo è stato scritto in quell'istante.
    """
    check_date(at, not_after=not_after, where=where)
    touched = Touched(at=at, by=by)
    for section in _sections(document):
        for node in section.get("nodes") or []:
            data = node.get(NODE_DATA)
            if not isinstance(data, dict):
                data = node[NODE_DATA] = {}
                touched.nodes_given_data.append(str(node.get("id")))
            if data.get(CREATED_AT):
                continue
            data[CREATED_AT] = at
            if by:
                data[CREATED_BY] = by
            touched.nodes.append(str(node.get("id")))
        for edge in section.get("edges") or []:
            attrs = edge.get(EDGE_ATTRS)
            if not isinstance(attrs, dict):
                attrs = edge[EDGE_ATTRS] = {}
                touched.edges_given_attributes.append(_edge_id(edge))
            if attrs.get(CREATED_AT):
                continue
            attrs[CREATED_AT] = at
            if by:
                attrs[CREATED_BY] = by
            touched.edges.append(_edge_id(edge))
    return touched


def take_the_date_back(document: Dict[str, Any], touched: Touched) -> int:
    """L'inverso esatto: togli **solo** quello che `give_a_date` ha messo.

    Ogni passo reversibile, e la reversibilità si dimostra byte a byte —
    timbrato, ri-spogliato, identico all'originale. Per riuscirci non basta
    «togli `created_at` dove vale T0»: metà degli archi legacy hanno già un
    `attributes` (con `original_edge_id` dentro) e metà no, e quelli a cui è
    stato creato vanno riportati a non averlo.
    """
    nodi = set(touched.nodes)
    archi = set(touched.edges)
    creati_data = set(touched.nodes_given_data)
    creati_attr = set(touched.edges_given_attributes)
    tolti = 0
    for section in _sections(document):
        for node in section.get("nodes") or []:
            ident = str(node.get("id"))
            data = node.get(NODE_DATA)
            if not isinstance(data, dict):
                continue
            if ident in nodi and data.get(CREATED_AT) == touched.at:
                data.pop(CREATED_AT, None)
                if touched.by and data.get(CREATED_BY) == touched.by:
                    data.pop(CREATED_BY, None)
                tolti += 1
            if ident in creati_data and not data:
                node.pop(NODE_DATA, None)
        for edge in section.get("edges") or []:
            ident = _edge_id(edge)
            attrs = edge.get(EDGE_ATTRS)
            if not isinstance(attrs, dict):
                continue
            if ident in archi and attrs.get(CREATED_AT) == touched.at:
                attrs.pop(CREATED_AT, None)
                if touched.by and attrs.get(CREATED_BY) == touched.by:
                    attrs.pop(CREATED_BY, None)
                tolti += 1
            if ident in creati_attr and not attrs:
                edge.pop(EDGE_ATTRS, None)
    return tolti


def dated(document: Dict[str, Any], at: str, **kwargs: Any
          ) -> Tuple[Dict[str, Any], Touched]:
    """`give_a_date` su una COPIA, per chi non vuole modificare in luogo.

    Il corpus si migra su copia, mai in luogo: questa è la forma che lo rende
    la strada facile invece di quella disciplinata.
    """
    copia = copy.deepcopy(document)
    return copia, give_a_date(copia, at, **kwargs)
