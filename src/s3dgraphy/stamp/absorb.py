"""Riassorbire il timbro: un verbale torna a essere grafo.

Un timbro è un frammento di em.json scritto in miniatura, quindi riattaccarlo è
**un merge per UUID** — e quello la libreria lo sa già fare. Qui non se ne scrive
un secondo: si costruisce il frammento come `Graph` e lo si piega dentro con
`container.merge_graph_into`, che è l'algebra CRDT di P4.1 (OR-Set per la
presenza, LWW-per-campo per il contenuto, i timbri editoriali come orologi).

## La regola che vale più di tutte le altre

**Due timbri per lo stesso digest che si contraddicono nella sostanza — genitori
diversi, processo diverso — non sono un errore: sono una scoperta.**

Quindi qui non c'è nessuna politica di risoluzione e **non si sceglie un
vincitore**. Quando i due contenuti non vanno d'accordo il grafo **non viene
toccato** e il risultato consegna i due timbri interi a chi legge — quello che il
grafo dice adesso e quello che è arrivato — con l'elenco dei punti in cui
divergono. Chi decide è una persona, e non stanotte.

È anche il motivo per cui il confronto non è «i due file sono uguali byte per
byte»: il timbro **non ha identità di contenuto propria** (è chiavato dal digest
della sua uscita), quindi due implementazioni possono serializzare gli stessi
fatti in modi diversi. Si confrontano i **fatti**, e si confrontano generando dal
grafo il timbro che quel grafo emetterebbe — cioè con la funzione di T1, nella
stessa lingua.

## Cosa è sostanza e cosa no

Non è sostanza l'**istante** (`by.at`, `declared.as_of`): due timbri che
differiscono solo lì sono lo stesso fatto registrato due volte, e si
deduplicano. Non lo è il `registry`, che il formato dichiara «un indizio per
ritrovare, non un'autorità»: lo stesso artefatto può stare in due stanze. Non lo
sono le `label`, «cortesia per un umano, non identità».

**Tutto il resto lo è.** Genitori, processo, tecnica, parametri, software,
operatore, misure. Anche il software: lo stesso algoritmo in due versioni non
produce gli stessi byte, quindi due versioni per lo stesso digest sono due
affermazioni che non possono essere entrambe vere.

## E il silenzio non è un disaccordo

Un campo che una parte dice e l'altra tace non è una contraddizione: è
un'aggiunta, e il merge la assorbe. Serve che **entrambe** parlino e dicano cose
diverse. Senza questa regola un timbro ricco non potrebbe mai atterrare su un
grafo povero — che è il caso normale.

Con una eccezione misurata, ed è il punto più sottile del formato: `"from": []`
**è** una dichiarazione («nato qui») quando c'è un `how` che la firma, e **non è
niente** quando il `how` manca — lì significa solo «di questo artefatto non so
come è stato fatto». Trattare i due casi allo stesso modo farebbe gridare al
disaccordo ogni volta che un timbro con genitori arriva su una risorsa nuda.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from dtcstamp import (BadStamp, Disagreement, STAMP_VERSION, clean_stamp,
                      compare_stamps, read_stamp, substance, validate_stamp)

from .emit import (EDGE_HAD_INPUT, EDGE_HAD_OUTPUT, SIZE_KEY, emit_stamp,
                   find_resource)

#: L'arco diretto uscita → ingresso, la scorciatoia che il substrato scrive
#: accanto alla coppia input/output. Stesso nome di `dtc.residency`.
EDGE_DERIVED_FROM = "dtc_derived_from"

#: Il genere di processo da usare quando il timbro non ne porta uno. Lo stesso
#: che `publication.promote_resource` scrive: un timbro che non dichiara l'asse
#: non deve far nascere un nodo senza `dtc_kind`, perché quel campo è validato.
DEFAULT_PROCESS_KIND = "transformation"

#: I percorsi che **non** fanno sostanza. Vedi il docstring del modulo.
IGNORED_PATHS = ("by.at", "declared.as_of", "registry", "_notes")


# ── quello che il FORMATO sa fare, e che non sta più qui ─────────────────────
#
# `BadStamp`, `validate_stamp`, `read_stamp`, `substance`, `compare_stamps` e
# `Disagreement` sono importati da `dtcstamp` e **ri-esportati con questi nomi**:
# non hanno mai avuto bisogno di un grafo — leggono e confrontano JSON — e chi
# scrive un addon per Blender non deve installare pandas per confrontare due
# verbali. I nomi restano raggiungibili da qui perché `from
# s3dgraphy.stamp.absorb import BadStamp` è un import che qualcuno ha scritto.
#
# Quello che resta in questo modulo ha bisogno di un grafo, ed è la ragione per
# cui il modulo esiste ancora: costruire il frammento e fonderlo.

@dataclass
class AbsorbResult:
    """Cosa è successo, detto in modo che si possa controllare.

    `applied` è falso in due casi diversi e il chiamante deve poterli
    distinguere: **deduplicato** (lo stesso fatto già registrato: non c'era
    niente da fare) e **in disaccordo** (c'era qualcosa da fare e non tocca a noi
    decidere cosa). Un booleano solo li avrebbe confusi, e sono l'opposto l'uno
    dell'altro.
    """

    digest: Optional[str] = None
    resource_id: Optional[str] = None
    applied: bool = False
    deduplicated: bool = False
    disagreements: List[Disagreement] = field(default_factory=list)
    #: I due contenuti interi, quando c'è un disaccordo: chi legge deve avere in
    #: mano tutti e due, non un elenco di differenze da cui ricostruirli.
    mine: Optional[Dict[str, Any]] = None
    theirs: Optional[Dict[str, Any]] = None
    added_nodes: int = 0
    merged_nodes: int = 0
    added_edges: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def in_disagreement(self) -> bool:
        return bool(self.disagreements)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "digest": self.digest,
            "resource_id": self.resource_id,
            "applied": self.applied,
            "deduplicated": self.deduplicated,
            "in_disagreement": self.in_disagreement,
            "disagreements": [d.as_dict() for d in self.disagreements],
            "mine": self.mine,
            "theirs": self.theirs,
            "added_nodes": self.added_nodes,
            "merged_nodes": self.merged_nodes,
            "added_edges": self.added_edges,
            "warnings": list(self.warnings),
        }


# ── costruire il frammento ───────────────────────────────────────────────────

def stamp_to_graph(stamp: Dict[str, Any], *, graph_id: Optional[str] = None):
    """Il timbro come `Graph` — il frammento di em.json che è sempre stato.

    Nessun tipo di nodo nuovo: una `ResourceNode` per l'uscita, una per ogni
    ingresso che sia un file, un `DTCAcquisitionNode` per un ingresso che sia una
    campagna, un `DTCProcessNode` per il passo. Gli archi sono i tre che il
    substrato già usa, con la stessa disciplina di `declare_derivation`: la
    scorciatoia `dtc_derived_from` si scrive **solo** fra file, perché fra un file
    e una campagna non c'è una derivazione da scrivere — c'è un evento.
    """
    from ..graph import Graph
    from ..nodes import DTCAcquisitionNode, DTCProcessNode, ResourceNode

    validate_stamp(stamp)
    itself = dict(stamp.get("self") or {})
    resource_id = str(itself["resource_id"])
    fragment = Graph(graph_id=graph_id or f"stamp:{resource_id}")
    _strip_born_with(fragment)

    output = ResourceNode(resource_id, name=resource_id)
    _apply_self(output, itself)
    fragment.add_node(output)

    how = dict(stamp.get("how") or {})
    parents = [p for p in (stamp.get("from") or []) if isinstance(p, dict)]
    if not how and not parents:
        # Il passo vuoto SENZA how: c'è solo l'artefatto e ciò che dichiara.
        # Un processo inventato qui sarebbe un evento che nessuno ha compiuto.
        _apply_declared(output, stamp)
        return fragment

    process_id = str(how.get("process_id") or "").strip() \
        or f"{resource_id}::step"
    process = DTCProcessNode(
        process_id,
        name=str(how.get("technique") or "step"),
        description="",
        dtc_kind=_process_kind(how))
    _apply_how(process, how)
    _apply_by(process, stamp.get("by") or {})
    _apply_declared(process, stamp)
    fragment.add_node(process)
    fragment.add_edge(f"{process_id}->{resource_id}", process_id, resource_id,
                      EDGE_HAD_OUTPUT)

    for parent in parents:
        pid = str(parent.get("resource_id") or "").strip()
        if not pid:
            continue
        if str(parent.get("kind") or "") == "acquisition":
            node = DTCAcquisitionNode(pid, name=str(parent.get("label") or pid))
            fragment.add_node(node)
            fragment.add_edge(f"{process_id}->{pid}", process_id, pid,
                              EDGE_HAD_INPUT)
            continue
        node = ResourceNode(pid, name=str(parent.get("label") or pid))
        digest = str(parent.get("digest") or "").strip()
        if digest:
            node.data["checksum"] = digest
        fragment.add_node(node)
        fragment.add_edge(f"{process_id}->{pid}", process_id, pid,
                          EDGE_HAD_INPUT)
        fragment.add_edge(f"{resource_id}~>{pid}", resource_id, pid,
                          EDGE_DERIVED_FROM)
    return fragment


def _strip_born_with(fragment: Any) -> None:
    """Toglie dal frammento quello che `Graph.__init__` gli mette addosso da solo.

    **Misurato, e non è un dettaglio.** Ogni `Graph` nasce con un
    `GeoPositionNode` di nome `geo_<graph_id>` (`graph.py:64`), perché un grafo di
    studio ha un posto sulla terra. Un frammento di timbro **non è un grafo di
    studio**: è un anello di catena. Senza questa riga, riassorbire un timbro
    piegava dentro al grafo di chi lo riceve un nodo `geo_stamp:res:mesh` — una
    posizione geografica **vuota e altrui**, arrivata per posta insieme a un
    verbale che non parlava di geografia.

    Non si cancella niente al ricevente: si toglie dal frammento, prima che parta.
    """
    for node in list(getattr(fragment, "nodes", []) or []):
        if getattr(node, "node_type", None) == "geo_position":
            fragment.remove_node(node.node_id)


def _process_kind(how: Dict[str, Any]) -> str:
    """L'asse controllato, e il ripiego quando il timbro non lo porta.

    `dtc_kind` è **validato** contro il vocabolario dei dati, quindi un valore
    che non c'è farebbe sollevare il costruttore e il timbro non atterrerebbe
    affatto. Un timbro che porta una `technique` fine ma non l'asse coarse cade
    sul genere di default — lo stesso che scrive `promote_resource` — e la
    `technique` resta scritta per intero in `data`: niente si perde, e nessun
    vocabolario si allarga per sbaglio a partire da un file arrivato da fuori.
    """
    from ..nodes.dtc_node import DTC_KINDS

    stated = str(how.get("dtc_kind") or "").strip()
    allowed = DTC_KINDS.get("process", ())
    return stated if stated in allowed else DEFAULT_PROCESS_KIND


def _apply_self(node: Any, itself: Dict[str, Any]) -> None:
    data = node.data
    for key in ("digest_covers", "media_type", "format", "packaging", "tier"):
        value = itself.get(key)
        if value not in (None, ""):
            data[key] = value
    digest = itself.get("digest")
    if digest:
        data["checksum"] = digest
    measures = itself.get("measures")
    if isinstance(measures, dict):
        # La chiave riservata torna al suo campo, tutto il resto ai `primitives`:
        # è l'inverso esatto dell'appiattimento che l'emissione fa, e per questo
        # il giro torna senza un secondo campo nel formato.
        primitives = {k: v for k, v in measures.items() if k != SIZE_KEY}
        if measures.get(SIZE_KEY) is not None:
            data[SIZE_KEY] = measures[SIZE_KEY]
        if primitives:
            data["primitives"] = primitives


def _apply_how(node: Any, how: Dict[str, Any]) -> None:
    data = node.data
    for key in ("technique", "parameters"):
        value = how.get(key)
        if value not in (None, "", {}):
            data[key] = value
    software = how.get("software")
    if isinstance(software, list) and software:
        data["software"] = software
        # `tool` resta scritto accanto perché `dtc.ingest._event_card` e le
        # schede che già esistono lo leggono: un riassorbimento che lasciasse
        # quel campo vuoto renderebbe muta un'interfaccia che funzionava.
        first = software[0]
        if isinstance(first, dict) and first.get("name"):
            data["tool"] = dict(first)


def _apply_by(node: Any, by: Dict[str, Any]) -> None:
    """Chi e quando, **senza inventare un autore**.

    L'ORCID va nel timbro editoriale, che è il posto dove questo ecosistema
    registra la mano che ha scritto. L'operatore intero resta accanto in
    `data.operator` perché l'etichetta — il nome della persona — nel timbro
    editoriale non ci sta: quello tiene un'identità, non un nome.

    **Non si crea un `AuthorNode`.** Sarebbe il modo del substrato per un agente
    con un nome, ma il suo costruttore ha dei valori-sentinella (`noorcid`,
    `nosurname`) e farne nascere uno da un timbro vorrebbe dire scrivere quelle
    parole nel grafo di qualcuno. E `has_author` è responsabilità
    **interpretativa**: chi ha decimato una mesh non è chi risponde della lettura
    archeologica, e confondere le due è esattamente ciò contro cui `editorial.py`
    mette in guardia in testa.
    """
    from ..editorial import normalize_instant, normalize_orcid

    operator = by.get("operator")
    if isinstance(operator, dict) and operator:
        node.data["operator"] = dict(operator)
        orcid = normalize_orcid(operator.get("id"))
        if orcid:
            node.data["created_by"] = orcid
    at = normalize_instant(by.get("at"))
    if at:
        node.data["created_at"] = at


def _apply_declared(node: Any, stamp: Dict[str, Any]) -> None:
    """`declared` si registra, **non si applica**.

    Il formato è esplicito: è storia con il suo `as_of`, non una regola. Farne un
    `LicenseNode` collegato con `has_license` vorrebbe dire trasformare «allora
    diceva CC-BY-NC» in «adesso la licenza è CC-BY-NC» — cioè far decidere il
    cancello vivo a un file arrivato per posta.

    Resta scritto sul nodo del passo (o sull'artefatto, quando passo non ce n'è),
    dove un lettore lo trova insieme al resto del verbale e dove l'emissione lo
    ritrova se il grafo non ha niente di più fresco da dire. È anche ciò che
    chiude il giro completo senza toccare i diritti vivi.
    """
    declared = stamp.get("declared")
    if isinstance(declared, dict) and declared:
        node.data["declared"] = dict(declared)


# ── il riassorbimento ────────────────────────────────────────────────────────

def absorb_stamp(graph: Any, stamp: Dict[str, Any], *,
                 dry_run: bool = False) -> AbsorbResult:
    """Riattacca un timbro a un grafo, o dice perché non l'ha fatto.

    Tre esiti, e sono diversi fra loro:

    * **applicato** — il frammento è stato piegato dentro con il merge per UUID;
    * **deduplicato** — il grafo diceva già questo, a meno dell'istante: lo stesso
      fatto registrato due volte, niente da fare;
    * **in disaccordo** — il grafo dice un'altra cosa nella sostanza. Il grafo
      **non viene toccato**, e il risultato porta i due timbri interi più
      l'elenco dei punti in cui divergono. **Non si sceglie un vincitore**:
      questa funzione non ha una politica di risoluzione perché la decisione non
      è sua.

    `dry_run` risponde senza scrivere — serve a un'interfaccia che voglia
    chiedere «che cosa succederebbe» prima di proporlo a una persona.
    """
    from ..container import merge_graph_into

    validate_stamp(stamp)
    itself = dict(stamp.get("self") or {})
    result = AbsorbResult(digest=itself.get("digest"),
                          resource_id=str(itself.get("resource_id")))

    existing = find_resource(graph, result.resource_id)
    if existing is None and result.digest:
        existing = find_resource(graph, result.digest)
    if existing is not None:
        mine = clean_stamp(emit_stamp(graph, existing.node_id))
        theirs = clean_stamp(stamp)
        differences = compare_stamps(mine, theirs)
        if differences:
            result.disagreements = differences
            result.mine = mine
            result.theirs = theirs
            return result
        # Nessun disaccordo. Resta una domanda sola: l'entrante porta qualcosa
        # che il grafo tace? Se no è lo stesso fatto registrato due volte.
        if _says_as_much(mine, theirs):
            result.deduplicated = True
            result.mine = mine
            result.theirs = theirs
            mine_at = (mine.get("by") or {}).get("at")
            theirs_at = (theirs.get("by") or {}).get("at")
            if mine_at != theirs_at:
                result.warnings.append(
                    "the same fact recorded twice at different instants "
                    f"({mine_at!r} and {theirs_at!r}): deduplicated, and the "
                    "graph keeps the instant it had")
            return result

    if dry_run:
        result.warnings.append("dry run: nothing was written")
        return result

    fragment = stamp_to_graph(stamp)
    report = merge_graph_into(graph, fragment)
    result.applied = True
    result.added_nodes = report.added_nodes
    result.merged_nodes = report.merged_nodes
    result.added_edges = report.added_edges
    result.warnings.extend(report.warnings)
    return result


def _says_as_much(mine: Dict[str, Any], theirs: Dict[str, Any]) -> bool:
    """Il grafo dice già **almeno quanto** il timbro entrante.

    La sostanza confrontabile può coincidere mentre l'entrante porta qualcosa che
    il grafo tace — un `how` su una risorsa che non ne aveva. Quello non è un
    duplicato: è un'aggiunta, e va assorbita. Senza questa riga un timbro con un
    processo atterrato su una risorsa nuda verrebbe scartato come «già visto».
    """
    said = substance(mine)
    for key, value in substance(theirs).items():
        if value in (None, "", {}, []):
            continue
        if said.get(key) in (None, "", {}, []):
            return False
    return True


def absorb_stamp_file(graph: Any, path: str, **kwargs: Any) -> AbsorbResult:
    """Come :func:`absorb_stamp`, partendo dal file."""
    return absorb_stamp(graph, read_stamp(path), **kwargs)
