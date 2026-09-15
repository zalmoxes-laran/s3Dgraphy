"""Emettere il timbro: da un grafo e da un id, il verbale di **un** passo.

## Cosa è un timbro, in una riga

Il verbale immutabile di un passo: un agente, con un processo e dei parametri,
consuma uno o più ingressi e produce **un** artefatto. Non è un formato nuovo — i
nodi che cita esistono già tutti — ed è **un frammento di em.json scritto in
miniatura**, per stare da solo fuori dal perimetro.

Quindi qui non nasce nessun tipo di nodo. Questo modulo **legge** ciò che
`publication.promote_resource` e `dtc.ingest.declare_derivation` hanno scritto,
e lo ridice nella forma del file.

## Le tre regole che governano questo modulo

**1 · Gli ingressi si nominano e non si aprono.** Di ogni genitore escono tre
campi — `resource_id`, `digest`, `label` — e nient'altro: nessun percorso,
nessuno stato, nessuna espansione ricorsiva. È tutta lì la differenza fra il
passo e la catena: un timbro che aprisse i suoi genitori sarebbe la catena
intera in ogni anello, e il primo grafo un po' profondo la farebbe esplodere.

**2 · Niente letture, solo dichiarazioni.** `ResourceNode` offre
`effective_tier()`, `effective_packaging()`, `effective_scope()` — ripieghi
onesti che un *consumatore* può fare. Qui **non si usano**, e la ragione si vede
solo facendo il giro completo: emettere un ripiego e poi riassorbirlo lo
**scriverebbe** nel grafo, trasformando una lettura in un'affermazione. Il timbro
direbbe «packaging: file» di una risorsa di cui nessuno l'aveva mai detto, e al
secondo giro quella frase sarebbe indistinguibile da una che qualcuno ha scritto.
Il campo assente è la sola risposta che sopravvive a un round-trip.

**3 · Nessun orologio.** `emit_stamp` è una funzione pura: prende un grafo e un
id, torna un dizionario, non tocca il filesystem e **non chiede l'ora**. Gli
istanti che compaiono vengono dai timbri editoriali dei nodi. Chi scrive su disco
è :func:`write_stamp`, che è un'altra funzione — così l'emissione si prova senza
un filesystem e due emissioni dello stesso grafo sono identiche.

## Il passo vuoto

Una risorsa senza genitori — un proxy modellato a mano, una foto di campo —
emette `"from": []`. È una **dichiarazione completa**: nato qui, da questa
persona, in questo momento. In un progetto archeologico metà degli asset sono
origini, e trattare l'assenza di genitori come un errore trasforma metà del
progetto in rumore.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from .identity import identity_strength, is_verifiable

#: La versione del formato. Un intero e non una stringa semver: il timbro è un
#: verbale, non una libreria, e l'unica domanda che un lettore gli fa è «so
#: leggere questa forma?».
STAMP_VERSION = 1

#: Gli archi della catena, con i nomi che il substrato usa già. Importati e non
#: riscritti: sono l'unica definizione di «questo processo ha prodotto quello».
EDGE_HAD_INPUT = "dtc_had_input"
EDGE_HAD_OUTPUT = "dtc_had_output"

#: `measures` nel formato è **piatto** — `{"size_bytes": …, "faces": …}` — mentre
#: il nodo tiene il peso separato dai conteggi (`size_bytes` e `primitives`).
#: Questa è l'unica chiave riservata, e tutto il resto di `measures` torna nei
#: `primitives`: è ciò che rende il giro reversibile senza un secondo campo.
SIZE_KEY = "size_bytes"

#: Cosa il digest copre. `artifact` = i byte come usciti dal processo;
#: `payload` = il contenuto al netto del timbro, per quando il timbro vive dentro
#: il vascello e scriverlo cambierebbe i byte.
DIGEST_COVERS = ("artifact", "payload")


class NotAnArtifact(LookupError):
    """L'id dato non è una risorsa viva di questo grafo."""


# ── letture minime sul grafo ─────────────────────────────────────────────────

def _data(node: Any) -> Dict[str, Any]:
    data = getattr(node, "data", None)
    return data if isinstance(data, dict) else {}


def _alive(item: Any) -> bool:
    """Un nodo o un arco che una tombstone ha spento non parla più.

    Lo decide `crdt.is_removed` e non un `"removed" in data`: una tombstone più
    vecchia di una modifica sullo stesso nodo **non è più** una cancellazione, e
    quella regola sta in un posto solo.
    """
    from ..crdt import is_removed

    payload = _data(item)
    attrs = getattr(item, "attributes", None)
    if is_removed(payload):
        return False
    return not (isinstance(attrs, dict) and is_removed(attrs))


def _nodes(graph: Any) -> List[Any]:
    return [n for n in getattr(graph, "nodes", []) or [] if _alive(n)]


def _edges(graph: Any) -> List[Any]:
    return [e for e in getattr(graph, "edges", []) or [] if _alive(e)]


def _text(value: Any) -> Optional[str]:
    """`name` può essere una stringa o un dizionario multilingua."""
    if value is None:
        return None
    if isinstance(value, dict):
        picked = value.get("default") or next(iter(value.values()), None)
        return str(picked).strip() or None if picked is not None else None
    text = str(value).strip()
    return text or None


def _courtesy(label: Any, *identifiers: Any) -> Optional[str]:
    """Un'etichetta che RIPETE l'identificatore non è un'etichetta: si omette.

    `label` è cortesia per un umano — un nome che dice qualcosa a chi legge — e
    quando quel nome È l'identificatore la cortesia diventa rumore che si finge
    informazione. Misurato su timbri veri: `by.operator.label` diceva
    «0000-0002-5065-7970», cioè l'ORCID una seconda volta; e togliendo il nome al
    nodo autore diventava «author:0000-0002-…», cioè l'identificatore una terza.

    Il confronto guarda anche **l'ultimo segmento**, perché è lì che i due si
    incontrano: `https://orcid.org/0000-…` e `author:0000-…` sono due vestiti
    della stessa stringa, e un confronto per uguaglianza secca li avrebbe
    lasciati passare tutti e due.

    Vale per OGNI etichetta del timbro e non solo per l'operatore: un ingresso
    chiamato come il suo `resource_id` e un grafo chiamato come il suo
    `graph_id` sono lo stesso difetto in due posti diversi.
    """
    text = _text(label)
    if not text:
        return None
    seen = {text.lower(), _tail(text)}
    for identifier in identifiers:
        other = _text(identifier)
        if not other:
            continue
        if other.lower() in seen or _tail(other) in seen:
            return None
    return text


def _tail(value: str) -> str:
    """L'ultimo segmento di un identificatore, dopo `/` o `:`.

    Serve solo al confronto qui sopra, e per questo non normalizza altro: non è
    una funzione di identità — quella è `identity.split_identity`, e mescolare le
    due farebbe decidere a una cortesia una cosa che riguarda le impronte.
    """
    return value.rsplit("/", 1)[-1].rsplit(":", 1)[-1].strip().lower()


def _size_of(node: Any) -> Optional[int]:
    """La dimensione dichiarata di una risorsa, o None — e **None è una
    risposta**, non un difetto.

    Una campagna di acquisizione non ha byte da pesare; una risorsa scritta
    prima che `size_bytes` esistesse non lo dichiara; e un valore che non è un
    intero non ancorato a zero non è una dimensione. In tutti e tre i casi la
    voce `from` esce senza il campo, che è esattamente ciò che «additivo»
    significa: chi legge lo tratta come facoltativo.
    """
    raw = _data(node).get("size_bytes")
    if isinstance(raw, bool) or not isinstance(raw, int):
        # `bool` è sottotipo di `int` in Python e `True` passerebbe per 1: una
        # dimensione non è mai un booleano, e lasciarlo passare metterebbe
        # «1 byte» in un timbro perché qualcuno ha scritto un flag nel campo
        # sbagliato.
        return None
    return raw if raw >= 0 else None


def _put(target: Dict[str, Any], key: str, value: Any) -> None:
    """Scrive solo quello che c'è.

    **Assente vuol dire non detto**, e un `null` in un file che esce dal
    perimetro è peggio di un campo mancante: un lettore ragionevole lo prende per
    una negazione esplicita.
    """
    if value is None or value == "" or value == {} or value == []:
        return
    target[key] = value


def find_resource(graph: Any, ref: str) -> Optional[Any]:
    """La risorsa viva con questo id — **o con questo digest**.

    Le due chiavi perché è così che le si nomina nella pratica: un tool interno
    ha l'id del nodo, chi arriva da uno store ha solo l'impronta. Stessa doppia
    porta di `dtc.ingest._find`, e per la stessa ragione.
    """
    wanted = str(ref or "").strip()
    if not wanted:
        return None
    for node in _nodes(graph):
        if node.node_id == wanted:
            return node
    lowered = wanted.lower()
    _, bare = _split(lowered)
    for node in _nodes(graph):
        if getattr(node, "node_type", None) != "resource":
            continue
        _, mine = _split(str(_data(node).get("checksum") or "").lower())
        if mine and mine == bare:
            return node
    return None


def _split(value: str):
    from .identity import split_identity

    return split_identity(value)


def producing_process(graph: Any, resource_id: str) -> Optional[Any]:
    """Il processo che ha **prodotto** questa risorsa, o None.

    `dtc_had_output` puntato a lei. Se ce n'è più d'uno il primo vince e il
    chiamante lo scopre da `warnings`: due eventi che dichiarano di aver prodotto
    gli stessi byte sono già un disaccordo, e questo modulo lo segnala invece di
    sceglierne uno in silenzio (T2 fa lo stesso un piano più su).
    """
    found = [e for e in _edges(graph)
             if getattr(e, "edge_type", None) == EDGE_HAD_OUTPUT
             and getattr(e, "edge_target", None) == resource_id]
    if not found:
        return None
    by_id = {n.node_id: n for n in _nodes(graph)}
    for edge in found:
        node = by_id.get(str(getattr(edge, "edge_source", "") or ""))
        if node is not None:
            return node
    return None


def _producers(graph: Any, resource_id: str) -> List[str]:
    return [str(getattr(e, "edge_source", "") or "") for e in _edges(graph)
            if getattr(e, "edge_type", None) == EDGE_HAD_OUTPUT
            and getattr(e, "edge_target", None) == resource_id]


def _inputs_of(graph: Any, process_id: str) -> List[Any]:
    by_id = {n.node_id: n for n in _nodes(graph)}
    out: List[Any] = []
    for edge in _edges(graph):
        if getattr(edge, "edge_type", None) != EDGE_HAD_INPUT:
            continue
        if getattr(edge, "edge_source", None) != process_id:
            continue
        node = by_id.get(str(getattr(edge, "edge_target", "") or ""))
        if node is not None and all(node.node_id != n.node_id for n in out):
            out.append(node)
    return out


# ── i cinque blocchi ─────────────────────────────────────────────────────────

def _self_block(resource: Any, warnings: List[str]) -> Dict[str, Any]:
    data = _data(resource)
    block: Dict[str, Any] = {"resource_id": resource.node_id}
    digest = _text(data.get("checksum"))
    _put(block, "digest", digest)
    if digest is None:
        warnings.append(
            "the artifact carries no identity: this stamp names a step but "
            "nothing that can be looked up or checked")
    elif identity_strength(digest) == "unknown":
        warnings.append(
            f"the identity '{digest}' states no algorithm: it reads as neither "
            f"verifiable nor comparable (see stamp.identity)")

    covers = _text(data.get("digest_covers")) or "artifact"
    if covers not in DIGEST_COVERS:
        warnings.append(
            f"digest_covers '{covers}' is not one of {list(DIGEST_COVERS)}; "
            f"recorded as given")
    block["digest_covers"] = covers

    _put(block, "media_type", _text(data.get("media_type")))
    _put(block, "format", _text(data.get("format")))
    # DICHIARATI, mai i ripieghi `effective_*` — vedi la regola 2 in testa.
    _put(block, "packaging", _text(data.get("packaging")))
    _put(block, "tier", _text(data.get("tier")))

    measures: Dict[str, Any] = {}
    if data.get(SIZE_KEY) is not None:
        measures[SIZE_KEY] = data.get(SIZE_KEY)
    primitives = data.get("primitives")
    if isinstance(primitives, dict):
        for what, how_many in primitives.items():
            if str(what) == SIZE_KEY:
                # `primitives: {"size_bytes": …}` collide con la chiave riservata
                # e il giro non tornerebbe: si dice invece di perderlo in silenzio
                warnings.append(
                    "a primitive named 'size_bytes' collides with the reserved "
                    "measures key and was not emitted")
                continue
            measures[str(what)] = how_many
    _put(block, "measures", measures)
    return block


def _from_block(inputs: Sequence[Any], warnings: List[str]) -> List[Dict[str, Any]]:
    """I genitori: **si nominano e non si aprono**.

    Identità, dimensione ed etichetta — e nient'altro. Nessuna ricorsione,
    nessun percorso, nessuno stato: è la regola che ferma la catena all'anello.

    **`size_bytes` non è ridondanza, è l'indice del recupero.** Riconoscere un
    file costa poco perché il suo timbro dichiara la dimensione e il filtro
    scarta i candidati impossibili senza leggere un byte; senza la stessa cifra
    qui, cercare un genitore smarrito costerebbe hashare tutto — e l'asimmetria
    rendeva la ricerca di un genitore la strada cara, che è l'opposto di quello
    che serve quando qualcuno ha riordinato nel Finder.

    Non può contraddire l'identità (stesso digest ⇒ stessa dimensione), quindi è
    un derivato che non invecchia. **Additivo**: i timbri emessi prima restano
    validi e chi legge lo tratta come facoltativo — per questo un genitore di cui
    non si conosce la dimensione non è un errore ed esce senza il campo.
    """
    out: List[Dict[str, Any]] = []
    for node in inputs:
        entry: Dict[str, Any] = {"resource_id": node.node_id}
        digest = _text(_data(node).get("checksum"))
        _put(entry, "digest", digest)
        _put(entry, "size_bytes", _size_of(node))
        _put(entry, "label", _courtesy(getattr(node, "name", None),
                                       node.node_id, digest))
        if digest is None and getattr(node, "node_type", None) == "resource":
            warnings.append(
                f"the input '{node.node_id}' has no digest: it can be named but "
                f"not looked up")
        if getattr(node, "node_type", None) == "dtc_acquisition":
            # Un'acquisizione È un ingresso legittimo («l'ortofoto viene dal volo
            # di marzo» è UN ingresso, non duecento) e non ha byte da hashare.
            # Detto, non finto.
            entry["kind"] = "acquisition"
        out.append(entry)
    return out


def _how_block(process: Optional[Any], warnings: List[str]) -> Dict[str, Any]:
    if process is None:
        return {}
    data = _data(process)
    block: Dict[str, Any] = {"process_id": process.node_id}

    # `technique` e `dtc_kind` NON sono lo stesso campo, ed è la scoperta di
    # questa notte. Il vocabolario `dtc_kinds` ha due voci sull'asse `process` —
    # `photogrammetry` e `transformation` — mentre l'esempio del formato dice
    # `"technique": "decimation"`, che lì dentro non c'è e non ci deve entrare:
    # sono due granularità (l'asse controllato e l'operazione specifica), non due
    # nomi della stessa cosa. Il formato nominava solo la seconda: senza la prima
    # il giro completo perderebbe un campo che il nodo valida.
    _put(block, "technique", _text(data.get("technique")))
    _put(block, "dtc_kind", _text(data.get("dtc_kind")))
    if not block.get("technique") and block.get("dtc_kind"):
        warnings.append(
            "no technique stated: the stamp carries the controlled dtc_kind "
            "only, which says the axis but not the operation")

    parameters = data.get("parameters")
    if isinstance(parameters, dict):
        _put(block, "parameters", dict(parameters))
    elif parameters is not None:
        warnings.append("parameters is not a dict and was not emitted")

    _put(block, "acquisition", _acquisition_block(process, data))

    _put(block, "software", _software_of(data))
    return block


#: I campi che il nodo-evento porta per RAGIONI SUE e che non sono fatti
#: dell'atto di acquisizione: quelli che il timbro emette già altrove, quelli
#: del registro editoriale e quelli della presenza CRDT, più la conta dei membri
#: — che è una cache di un numero, non una circostanza del rilievo.
#:
#: Composti dalle costanti che vivono dove quei campi sono definiti, e non
#: riscritti a mano: un elenco copiato qui invecchierebbe in silenzio il giorno
#: che `editorial` o `crdt` ne aggiungono uno.
def _structural_keys() -> frozenset:
    from ..crdt import FIELD_CLOCKS_KEY, REMOVED_KEY
    from ..editorial import FIELDS as EDITORIAL_FIELDS

    return frozenset({
        "dtc_kind", "technique", "parameters", "software", "tool",
        "declared", "operator", "member_count", "acquisition",
        *EDITORIAL_FIELDS, FIELD_CLOCKS_KEY, REMOVED_KEY,
    })


def _acquisition_block(process: Any, data: Dict[str, Any]) -> Dict[str, Any]:
    """I fatti dell'ATTO DI ACQUISIZIONE — apparecchio, obiettivo, campagna.

    **Non vanno in `parameters`**, e non è pedanteria: `parameters` vuol dire
    «come la tecnica è stata applicata», mentre l'apparecchio e le circostanze
    sono un'altra cosa — la distinzione che CRM3D fa fra `L12 happened on device`
    e `L13 used parameters`. Per un rilievo fotogrammetrico è metà di quello che
    serve sapere fra vent'anni, e finché non aveva una casa ripiegava su
    `parameters`, cioè si travestiva da parametro.

    **Blocco aperto**, perché ciò che conta cambia col tipo di strumento: una
    fotocamera ha un obiettivo, uno scanner ha una risoluzione angolare, un
    georadar ha una frequenza. Un elenco chiuso avrebbe scartato in silenzio il
    campo che serve al terzo strumento.

    Due strade per leggerlo, e la seconda è per ciò che esiste già:

    * `data["acquisition"]`, quando chi ha scritto l'evento l'ha detto
      esplicitamente — non ambiguo, e da preferire;
    * per un nodo `dtc_acquisition`, **ciò che resta** del suo `data` una volta
      tolti i campi strutturali. È la strada che fa funzionare
      `bucket_acquisition` così com'è: quella funzione fonde `metadata` nel
      `data` alla lettera — «i fatti rappresentativi del lotto appartengono
      all'evento, non ripetuti su quattrocento file», dice il suo docstring — e
      il posto in cui li mette è giusto; mancava solo la porta per uscirne.

    Una volta sola: se il blocco esce di qui, non esce anche da `parameters`,
    perché `bucket_acquisition` non scrive mai `parameters`.
    """
    explicit = data.get("acquisition")
    if isinstance(explicit, dict) and explicit:
        return {k: v for k, v in explicit.items() if v not in (None, "")}
    if getattr(process, "node_type", None) != "dtc_acquisition":
        return {}
    skip = _structural_keys()
    return {k: v for k, v in data.items()
            if k not in skip and not str(k).startswith("_")
            and v not in (None, "")}


def _software_of(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """La lista del software, da `data.software` o dal vecchio `data.tool`.

    `declare_derivation` scrive `data.tool = {"name": …}` — **uno** strumento —
    e il suo docstring dice che il dizionario esiste perché «version, parameters
    and a container digest are the natural next keys». Il formato ne vuole
    **una lista**, perché una catena vera ne nomina due (EM Tools *e* s3dgraphy) e
    lo stesso algoritmo in due versioni non produce gli stessi byte.

    Quindi si legge la lista quando c'è e si promuove il vecchio `tool` a lista
    di uno quando c'è solo lui: un timbro emesso da un grafo scritto prima di
    stanotte dice comunque con che cosa è stato fatto.
    """
    software = data.get("software")
    if isinstance(software, list):
        out = []
        for item in software:
            if isinstance(item, dict):
                entry = {k: v for k, v in item.items() if v not in (None, "")}
                if entry:
                    out.append(entry)
            elif str(item or "").strip():
                out.append({"name": str(item).strip()})
        return out
    tool = data.get("tool")
    if isinstance(tool, dict):
        entry = {k: v for k, v in tool.items() if v not in (None, "")}
        return [entry] if entry else []
    if str(tool or "").strip():
        return [{"name": str(tool).strip()}]
    return []


def _by_block(graph: Any, process: Optional[Any],
              resource: Any) -> Dict[str, Any]:
    """Chi e quando.

    **`operator` può mancare, e non è un buco**: quando manca l'agente è il
    software nominato in `how`. Una regola sola, nessuna ridondanza — è il caso
    del bake in batch, del servizio, del chatbot che produce risorse. Non si
    scrive nessun «unknown» al suo posto: sarebbe un agente inventato.

    Due sorgenti per l'operatore, nell'ordine in cui dicono di più: un
    `has_author` verso un `AuthorNode` (id **e** nome), poi il timbro editoriale
    `created_by` (solo l'ORCID, che è già un'identità). Il secondo è il caso
    reale — `promote_resource` timbra e non crea archi d'autore.
    """
    anchor = process if process is not None else resource
    block: Dict[str, Any] = {}
    operator = _author_of(graph, anchor) or _author_of(graph, resource)
    if operator is None:
        data = _data(anchor)
        orcid = _text(data.get("created_by")) or _text(_data(resource).get("created_by"))
        if orcid:
            operator = {"id": f"https://orcid.org/{orcid}"}
    _put(block, "operator", operator)
    _put(block, "at", _instant_of(anchor) or _instant_of(resource))
    return block


def _author_of(graph: Any, node: Any) -> Optional[Dict[str, Any]]:
    if node is None:
        return None
    by_id = {n.node_id: n for n in _nodes(graph)}
    for edge in _edges(graph):
        if getattr(edge, "edge_type", None) != "has_author":
            continue
        source = str(getattr(edge, "edge_source", "") or "")
        target = str(getattr(edge, "edge_target", "") or "")
        other = target if source == node.node_id else (
            source if target == node.node_id else None)
        author = by_id.get(other or "")
        if author is None or getattr(author, "node_type", None) not in (
                "author", "author_ai"):
            continue
        orcid = _text(_data(author).get("orcid"))
        entry: Dict[str, Any] = {}
        _put(entry, "id", f"https://orcid.org/{orcid}" if orcid else None)
        _put(entry, "label", _courtesy(getattr(author, "name", None),
                                       orcid, author.node_id))
        if entry:
            return entry
    return None


def _instant_of(node: Any) -> Optional[str]:
    """L'istante del passo: `created_at`, mai `modified_at`.

    Il timbro è il verbale della **genesi**, e `modified_at` cambia ogni volta
    che qualcuno rinomina il nodo. Usarlo farebbe scivolare in avanti la data di
    un fatto già avvenuto.
    """
    if node is None:
        return None
    return _text(_data(node).get("created_at"))


def _declared_block(graph: Any, resource: Any,
                    at: Optional[str]) -> Dict[str, Any]:
    """Licenza ed embargo **come dichiarati allora**, con il loro `as_of`.

    È storia, non una regola da applicare: il cancello vivo sta altrove
    (`rights.rights_for_digest`, che ricalcola la scadenza al momento della
    domanda). Qui si registra che cosa diceva il grafo, e quando lo diceva.

    La lettura passa da `rights_for_digest` — la stessa che usa il gate degli
    asset — invece di essere riscritta qui: due algoritmi per «che licenza ha
    questo file» divergerebbero, e il giorno in cui divergono uno dei due è su un
    server che serve byte.

    **Il `Graph` gli si passa nudo**, e la prima versione di questa riga lo
    serializzava prima con `build_emjson`. Misurato: `rights_for_digest` cerca
    `graphs` (plurale) o un `nodes` in cima, mentre `build_emjson` scrive
    `{"header": …, "graph": …}` al singolare — quindi rispondeva `None`, cioè
    «di questo digest non so niente», su un grafo che dichiarava una licenza.
    `rights._sections` sa già leggere un `Graph` per conto suo: passarglielo è
    più corretto **e** costa una passata invece di una serializzazione intera.

    `as_of` è l'istante della genesi e **non l'ora corrente**: chiedere l'ora qui
    renderebbe l'emissione impura e due emissioni dello stesso grafo diverse.

    Quando il grafo vivo non dice niente si ripiega su ciò che il verbale aveva
    già registrato (`data.declared`, scritto dal riassorbimento): è quello che
    chiude il giro completo senza che `declared` diventi mai un diritto vivo.
    """
    digest = _text(_data(resource).get("checksum"))
    if not digest:
        return {}
    from ..rights import rights_for_digest

    found = rights_for_digest(graph, digest) or {}
    block: Dict[str, Any] = {}
    # `license` e non `license_effective`: un default non è una dichiarazione, e
    # scriverlo qui lo trasformerebbe in una.
    _put(block, "license", found.get("license"))
    _put(block, "embargo_until", found.get("embargo"))
    if block:
        _put(block, "as_of", at)
        return block
    return _recorded_declaration(graph, resource)


def _recorded_declaration(graph: Any, resource: Any) -> Dict[str, Any]:
    """Il `declared` che un riassorbimento aveva messo da parte.

    Sta su `data.declared` del nodo del passo (o dell'artefatto, quando passo non
    ce n'è) perché **`declared` è storia e non una regola**: materializzarlo come
    `LicenseNode` collegato con `has_license` avrebbe trasformato «allora diceva
    CC-BY-NC» in «adesso la licenza è CC-BY-NC», cioè avrebbe fatto decidere il
    cancello vivo a un file arrivato per posta.

    Letto **dopo** il grafo vivo e mai al posto suo: se qualcuno ha dichiarato
    qualcosa qui, quello che conta è quello.
    """
    process = producing_process(graph, resource.node_id)
    for node in (process, resource):
        recorded = _data(node).get("declared") if node is not None else None
        if isinstance(recorded, dict) and recorded:
            return dict(recorded)
    return {}


def _registry_block(graph: Any, revision: Optional[int],
                    room: Optional[str]) -> Dict[str, Any]:
    """Un **indizio per ritrovare, non un'autorità**.

    `graph_id` e l'etichetta li sa il grafo; `revision` e `room` no — sono fatti
    del posto da cui il timbro esce, e chi emette li passa. Assenti quando
    nessuno li ha detti: un `revision` inventato renderebbe citabile una cosa che
    non lo è, che è il contrario del motivo per cui quel campo esiste.
    """
    block: Dict[str, Any] = {}
    _put(block, "graph_id", _text(getattr(graph, "graph_id", None)))
    _put(block, "label", _courtesy(getattr(graph, "name", None),
                                   getattr(graph, "graph_id", None)))
    if revision is not None:
        block["revision"] = revision
    _put(block, "room", _text(room))
    return block


# ── l'emissione ──────────────────────────────────────────────────────────────

def emit_stamp(graph: Any, resource_ref: str, *,
               revision: Optional[int] = None,
               room: Optional[str] = None) -> Dict[str, Any]:
    """Il timbro del passo che ha prodotto questa risorsa.

    **Pura**: nessun filesystem, nessun orologio, nessuna scrittura sul grafo.
    Prende un grafo e un id (o un digest) e torna un dizionario. Chi scrive su
    disco è :func:`write_stamp`.

    `resource_ref` è l'**uscita**, perché un timbro descrive un passo dal lato di
    ciò che ne è venuto fuori: un processo può avere N ingressi, ma il timbro
    verbalizza **un** artefatto, ed è quello a dargli identità.

    Il risultato porta `warnings` sotto `_notes`: sono osservazioni sul DATO —
    un ingresso senza digest, un'identità senza algoritmo — non difetti di
    programmazione, e stanno nel timbro perché chi lo riceve possa vederle senza
    aver assistito all'emissione. La chiave ha l'underscore perché non fa parte
    del formato che esce: :func:`clean_stamp` la toglie.

    Raises:
        NotAnArtifact: se l'id non è una risorsa viva di questo grafo. Non un
            timbro vuoto: un verbale di un passo che non esiste sarebbe una
            dichiarazione falsa, e restituirlo la renderebbe archiviabile.
    """
    resource = find_resource(graph, resource_ref)
    if resource is None or getattr(resource, "node_type", None) != "resource":
        raise NotAnArtifact(
            f"'{resource_ref}' is not a live resource in this graph: a stamp is "
            f"the record of a step that produced something, and there is nothing "
            f"here to have produced")

    warnings: List[str] = []
    producers = _producers(graph, resource.node_id)
    if len(producers) > 1:
        warnings.append(
            f"{len(producers)} processes claim to have produced this artifact "
            f"({', '.join(sorted(producers))}); the stamp records the first and "
            f"the disagreement is reported rather than resolved")
    process = producing_process(graph, resource.node_id)
    inputs = _inputs_of(graph, process.node_id) if process is not None else []

    stamp: Dict[str, Any] = {"stamp": STAMP_VERSION}
    stamp["self"] = _self_block(resource, warnings)
    #: SEMPRE presente, anche vuoto — ed è il caso che deve funzionare al primo
    #: colpo. `"from": []` è una dichiarazione COMPLETA: nato qui. Metà degli
    #: asset di un progetto archeologico sono origini, e `_put` (che tace sulle
    #: liste vuote) qui NON si usa apposta: l'assenza del campo direbbe «non lo
    #: so», la lista vuota dice «nessuno».
    stamp["from"] = _from_block(inputs, warnings)
    _put(stamp, "how", _how_block(process, warnings))
    by = _by_block(graph, process, resource)
    _put(stamp, "by", by)
    if not by.get("operator"):
        warnings.append(
            "no operator: by the format's own rule the agent is the software "
            "named in `how`")
    _put(stamp, "declared", _declared_block(graph, resource, by.get("at")))
    _put(stamp, "registry", _registry_block(graph, revision, room))
    if process is None:
        warnings.append(
            "no process produced this artifact: the stamp records the artifact "
            "and its declarations, and says nothing about how it was made")
    if warnings:
        stamp["_notes"] = warnings
    return stamp


def clean_stamp(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """Il timbro **senza le note**, che è quello che esce.

    Le note sono per chi emette. Un file che lascia il perimetro non deve
    portarsi dietro i dubbi di chi l'ha scritto travestiti da contenuto.
    """
    return {k: v for k, v in stamp.items() if not str(k).startswith("_")}


def stamp_filename(stamp: Dict[str, Any], *, asset: Optional[str] = None) -> str:
    """`<asset>.stamp.json`.

    Il nome dell'asset quando c'è, altrimenti l'id della risorsa: mai `em.json`
    (specie diversa — inviterebbe a fondere, editare e versionare un verbale) e
    mai `dtc.json` (prometterebbe una catena e consegna un anello).
    """
    base = str(asset or (stamp.get("self") or {}).get("resource_id") or "stamp")
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in base)
    return f"{safe}.stamp.json"


def write_stamp(stamp: Dict[str, Any], path: str) -> str:
    """Scrive il timbro su disco. **L'unica funzione di questo modulo che tocca
    un filesystem**, e sta separata perché l'emissione si possa provare senza.

    `indent=1` e `ensure_ascii=False` come l'esportatore em.json: un timbro si
    legge a occhio e si guarda in un diff.
    """
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(clean_stamp(stamp), handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    return path


def stamp_identity(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """Quanto è forte l'identità di questo timbro — vedi :mod:`.identity`.

    Sta qui, e non lasciato a chi legge, perché è la domanda che un'interfaccia
    deve fare **prima** di scrivere «verificato» accanto a una riga.
    """
    from .identity import describe_identity

    return describe_identity((stamp.get("self") or {}).get("digest"))


def is_verifiable_stamp(stamp: Dict[str, Any]) -> bool:
    return is_verifiable((stamp.get("self") or {}).get("digest"))
