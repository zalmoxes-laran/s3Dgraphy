"""L'ora zero: dare una data senza inventare un autore, e senza fare danno.

════════════════════════════════════════════════════════════════════════════════
## COSA È STATO MISURATO PRIMA DI SCRIVERE UNA RIGA

Sul corpus vero di `stratigraph-server` (70 documenti, letti e mai scritti):

    senza NESSUN orologio     7 documenti   ·   interamente timbrati  63
    da timbrare               2931 nodi  ·  8514 archi

E due cose che il prompt del 4 ottobre dava per assodate e **non lo erano**:

* «nei documenti legacy `attributes` non esiste, va creato» — **metà ce l'ha**
  (4907 archi su 9755), con dentro `original_edge_id` e compagnia: va
  integrato, non sostituito. Questo file lo prova nei due sensi.
* `created_at` e `created_by` **viaggiano sempre insieme**: 3662 nodi su 3662,
  1241 archi su 1241. Una data senza autore non esiste in natura in questi
  documenti — ed è quello che la rende la firma di un'importazione.
"""

from __future__ import annotations

import copy
import json

import pytest

from s3dgraphy import zero_hour as oz
from s3dgraphy.crdt import Clock, compare_clocks, node_stamp

T0 = "2026-08-31T00:00:00Z"
VIVO = "2026-09-04T10:00:00Z"
ANNA = "0000-0002-1825-0097"


def _legacy():
    """La forma vera di un documento importato, verificata sul corpus: nessun
    orologio, e `attributes` che a volte c'è e a volte no."""
    return {
        "header": {"format": "em.json", "version": "1.0",
                   "title": "Sarmizegetusa · Foro"},
        "graphs": {"g": {"graph_id": "g", "name": "g", "nodes": [
            {"id": "US1", "node_type": "US", "name": "US1",
             "data": {"original_id": "n0", "graph_id": "g"}},
            {"id": "US2", "node_type": "US", "name": "US2",
             "data": {"original_id": "n1"}},
            # …e uno SENZA `data` del tutto: 27 nodi del corpus sono così
            {"id": "US3", "node_type": "US", "name": "US3"},
        ], "edges": [
            # con `attributes` già presente — metà del corpus
            {"id": "e1", "edge_type": "is_before", "source": "US1",
             "target": "US2", "attributes": {"original_edge_id": "e0"}},
            # …e senza — l'altra metà
            {"id": "e2", "edge_type": "is_before", "source": "US2",
             "target": "US3"},
        ]}},
        "active_graph_id": "g",
    }


# ═══ 1 · la forma, verificata ════════════════════════════════════════════════

def test_cosa_e_senza_orologio():
    doc = _legacy()
    nodi, archi = oz.unstamped(doc)
    assert nodi == ["US1", "US2", "US3"]
    assert archi == ["e1", "e2"]


def test_ATTRIBUTES_SI_INTEGRA_e_non_si_sostituisce():
    """Il prompt diceva «non esiste, va creato». Metà del corpus ce l'ha, e
    dentro c'è la tracciabilità dell'importazione: sostituirlo la butterebbe."""
    doc = _legacy()
    oz.give_a_date(doc, T0)
    archi = {e["id"]: e for e in doc["graphs"]["g"]["edges"]}
    assert archi["e1"]["attributes"]["original_edge_id"] == "e0", "conservato"
    assert archi["e1"]["attributes"]["created_at"] == T0, "…e integrato"
    assert archi["e2"]["attributes"] == {"created_at": T0}, "…e creato dove non c'era"


def test_UN_NODO_SENZA_data_ne_riceve_uno():
    doc = _legacy()
    oz.give_a_date(doc, T0)
    us3 = [n for n in doc["graphs"]["g"]["nodes"] if n["id"] == "US3"][0]
    assert us3["data"] == {"created_at": T0}


def test_QUELLO_CHE_UN_OROLOGIO_CE_LHA_NON_SI_TOCCA():
    doc = _legacy()
    doc["graphs"]["g"]["nodes"][0]["data"]["created_at"] = VIVO
    doc["graphs"]["g"]["nodes"][0]["data"]["created_by"] = ANNA
    tocco = oz.give_a_date(doc, T0)
    assert "US1" not in tocco.nodes
    assert doc["graphs"]["g"]["nodes"][0]["data"]["created_at"] == VIVO
    assert doc["graphs"]["g"]["nodes"][0]["data"]["created_by"] == ANNA


def test_GLI_OROLOGI_DI_CAMPO_NON_SI_TOCCANO():
    """Un nodo legacy ha il timbro di nascita e nessun orologio di campo, ed è
    la verità: inventarne uno per campo direbbe che ogni campo è stato scritto
    in quell'istante, che è una bugia più grande di quella che si evita."""
    doc = _legacy()
    oz.give_a_date(doc, T0)
    for nodo in doc["graphs"]["g"]["nodes"]:
        assert oz.FIELD_CLOCKS_KEY not in (nodo.get("data") or {})


# ═══ 2 · nessun autore inventato ═════════════════════════════════════════════

def test_IL_TIMBRO_NON_PORTA_UN_AUTORE():
    """Misurato sul cruscotto vero: con un `by` d'importazione il buco
    «senza il nome di nessuno» va da 1845 a 0 su `sarmizegetusa`, e il
    cruscotto direbbe «0 senza autore» mentre nessuno di quei nodi ha ancora un
    autore umano.

    E non serve: `Clock.stamped` è `bool(ts)`."""
    doc = _legacy()
    oz.give_a_date(doc, T0)
    for nodo in doc["graphs"]["g"]["nodes"]:
        assert nodo["data"]["created_at"] == T0
        assert oz.CREATED_BY not in nodo["data"], (
            "il timbro ha inventato un autore: il buco dell'autorialità "
            "sparirebbe invece di restare")
    for arco in doc["graphs"]["g"]["edges"]:
        assert oz.CREATED_BY not in arco["attributes"]


def test_UNA_DATA_SENZA_AUTORE_BASTA_al_CRDT():
    """La ragione per cui l'autore non serve, misurata sul modello."""
    doc = _legacy()
    oz.give_a_date(doc, T0)
    nodo = doc["graphs"]["g"]["nodes"][0]
    assert node_stamp(nodo).stamped is True
    assert node_stamp(nodo).by is None


def test_CHI_VUOLE_UN_AUTORE_PUO_AVERLO_e_sa_cosa_compra():
    doc = _legacy()
    oz.give_a_date(doc, T0, by="import:EM_CaseStudies")
    assert doc["graphs"]["g"]["nodes"][0]["data"][oz.CREATED_BY] == \
        "import:EM_CaseStudies"


# ═══ 3 · IL CANCELLO — T0 mai dopo la prima scrittura vera ═══════════════════

def test_IL_CANCELLO_rifiuta_una_data_troppo_TARDA():
    """L'unico modo in cui questa operazione può fare danno: un legacy che
    batte il lavoro di una persona, in silenzio."""
    doc = _legacy()
    with pytest.raises(oz.RefusedDate) as rifiuto:
        oz.give_a_date(doc, "2026-09-05T23:29:14Z",
                       not_after="2026-09-05T19:28:23.734Z",
                       where="basilica-demo")
    detto = str(rifiuto.value)
    assert "basilica-demo" in detto
    assert "19:28:23.734Z" in detto
    assert "mtime" in detto, "…e dice perché la fonte ovvia è quella sbagliata"
    # …e NIENTE è stato toccato
    assert oz.unstamped(doc) == (["US1", "US2", "US3"], ["e1", "e2"])


def test_E_SENZA_IL_CANCELLO_il_legacy_batte_il_lavoro_delle_persone():
    """La gemella della rottura, e misura **l'effetto** invece della
    sostituzione: si timbra con una data più tarda e si guarda chi vince."""
    vivo = Clock(VIVO, ANNA)
    # prima: il legacy non sa, e perde perché un istante noto batte uno ignoto
    verso, ragione = compare_clocks(vivo, Clock())
    assert (verso, ragione) == (1, "unstamped")

    # …e con una data più tarda del lavoro vero, il legacy VINCE
    tardi = Clock("2026-09-05T23:29:14Z")
    verso, ragione = compare_clocks(tardi, vivo)
    assert (verso, ragione) == (1, "newer"), (
        "ed ecco il danno: un valore importato batte una scrittura di una "
        "persona, e la ragione dice «più recente»")


def test_QUANDO_NON_SI_SA_NIENTE_nessuna_data_e_troppo_tarda():
    oz.check_date("2030-01-01T00:00:00Z", not_after=None)


def test_LA_PRIMA_SCRITTURA_VERA_si_cerca_in_tre_posti():
    doc = _legacy()
    doc["graphs"]["g"]["nodes"][0]["data"]["created_at"] = "2026-09-10T00:00:00Z"
    assert oz.earliest_real_write(doc) == "2026-09-10T00:00:00Z"
    assert oz.earliest_real_write(
        doc, [{"op": "add_node", "ts": "2026-09-02T00:00:00Z"}]
    ) == "2026-09-02T00:00:00Z"
    assert oz.earliest_real_write(
        doc, room_created_at="2026-08-01T00:00:00Z"
    ) == "2026-08-01T00:00:00Z"
    assert oz.earliest_real_write({"graphs": {}}) is None


# ═══ 4 · reversibile, byte a byte ════════════════════════════════════════════

def test_LA_REVERSIBILITA_BYTE_A_BYTE():
    """Timbrato → ri-spogliato → **identico all'originale**, serializzato.

    Non «gli stessi campi»: gli stessi byte. Un `attributes` creato dove non
    c'era, e un `data` creato dove non c'era, devono tornare a non esserci —
    e un conteggio non basta a saperlo, per questo `Touched` porta gli id.
    """
    originale = _legacy()
    prima = json.dumps(originale, ensure_ascii=False, sort_keys=True)

    doc = copy.deepcopy(originale)
    tocco = oz.give_a_date(doc, T0)
    assert tocco.total == 5, "tre nodi e due archi"
    assert json.dumps(doc, ensure_ascii=False, sort_keys=True) != prima

    tolti = oz.take_the_date_back(doc, tocco)
    assert tolti == 5
    assert json.dumps(doc, ensure_ascii=False, sort_keys=True) == prima


def test_LA_REVERSIBILITA_non_tocca_quello_che_non_ha_messo():
    """Un documento misto: quello che c'era prima resta, anche al ritorno."""
    originale = _legacy()
    originale["graphs"]["g"]["nodes"][0]["data"]["created_at"] = VIVO
    originale["graphs"]["g"]["nodes"][0]["data"]["created_by"] = ANNA
    prima = json.dumps(originale, ensure_ascii=False, sort_keys=True)

    doc = copy.deepcopy(originale)
    tocco = oz.give_a_date(doc, T0)
    oz.take_the_date_back(doc, tocco)
    assert json.dumps(doc, ensure_ascii=False, sort_keys=True) == prima


def test_dated_lavora_su_una_COPIA():
    originale = _legacy()
    prima = json.dumps(originale, sort_keys=True)
    copia, tocco = oz.dated(originale, T0)
    assert json.dumps(originale, sort_keys=True) == prima, "l'originale è intatto"
    assert tocco.total == 5


# ═══ 5 · la fusione non cambia, e il pareggio ════════════════════════════════

def test_LA_FUSIONE_INVARIATA_una_scrittura_viva_vince_PRIMA_e_DOPO():
    """Il cancello di §3 del prompt, dall'altro lato: una scrittura viva batte
    il legacy prima e dopo la timbratura, **per ragioni diverse**.

    Prima: perché un istante noto batte uno ignoto (`unstamped`).
    Dopo:  perché è più tarda (`newer`).
    """
    vivo = Clock(VIVO, ANNA)
    prima = compare_clocks(vivo, Clock())
    dopo = compare_clocks(vivo, Clock(T0))
    assert prima == (1, "unstamped")
    assert dopo == (1, "newer")
    assert prima[0] == dopo[0] == 1, "vince tutte e due le volte"


def test_IL_PAREGGIO_DOPO_LA_TIMBRATURA_resta_un_pareggio():
    """§8 — e questa è la ragione per cui l'autore non si mette.

    Due valori legacy dello STESSO documento, timbrati con lo stesso T0 e senza
    autore, pareggiano: nessuno vince, niente si muove, e il «non lo so»
    sopravvive esattamente dove è vero — dentro un documento non sappiamo
    davvero l'ordine.
    """
    verso, ragione = compare_clocks(Clock(T0), Clock(T0))
    assert verso == 0
    assert ragione == "tie-author"


def test_E_CON_UN_AUTORE_DIMPORTAZIONE_il_pareggio_resta_un_pareggio():
    """Anche mettendo il `by`, due valori dello stesso import pareggiano: è lo
    stesso nome da tutte e due le parti.

    Quindi `tie-author` fra due battezzati **è accettabile**, e non serve un
    terzo esito: il caso che preoccupava — «vince il nome più piccolo in ordine
    alfabetico» — si presenta solo fra due importazioni DIVERSE allo stesso
    istante, e T0 è per importazione. **Non l'ho costruito**, ed è un
    cambiamento a `compare_clocks`, cioè al cuore."""
    stesso = "import:EM_CaseStudies"
    assert compare_clocks(Clock(T0, stesso), Clock(T0, stesso)) == (0, "tie-author")
    # due importazioni diverse allo stesso istante: qui vincerebbe l'alfabeto
    verso, ragione = compare_clocks(Clock(T0, "import:A"), Clock(T0, "import:B"))
    assert (verso, ragione) == (1, "tie-author")


def test_DUE_IMPORTAZIONI_IN_GIORNI_DIVERSI_si_ordinano():
    """Il guadagno vero: T0 per importazione e non globale."""
    verso, ragione = compare_clocks(Clock("2026-09-01T00:00:00Z"),
                                    Clock("2026-08-31T00:00:00Z"))
    assert (verso, ragione) == (1, "newer")


# ════════════════════════════════════════════════════════════════════════════
# 5 OTTOBRE — da dove viene T0, e cosa NON è una data di registrazione
#
# Il 4 ottobre il corpus non fu timbrato perché nessuna fonte reggeva il
# cancello. La fonte che regge non descrive il file e non descrive la stanza:
# descrive il **programma** che ha prodotto il documento. Misurata sul corpus,
# regge 7 volte su 7 dove la mtime ne reggeva 4.
# ════════════════════════════════════════════════════════════════════════════


def _con_generatore(version="1.6.0.dev16"):
    """La forma vera dell'header dei quattro documenti EM_CaseStudies."""
    doc = _legacy()
    doc["header"]["generator"] = {"tool": "s3dgraphy", "version": version}
    return doc


def test_IL_DOCUMENTO_DICE_DA_QUALE_PROGRAMMA_VIENE():
    assert oz.declared_generator(_con_generatore()) == (
        "s3dgraphy", "1.6.0.dev16")


def test_E_QUANDO_NON_LO_DICE_non_si_indovina():
    #: le tre forme che il corpus contiene davvero: header senza `generator`
    #: (le tre stanze seminate), e le due mezze forme che un file rotto darebbe
    assert oz.declared_generator(_legacy()) is None
    mezzo = _legacy()
    mezzo["header"]["generator"] = {"tool": "s3dgraphy"}
    assert oz.declared_generator(mezzo) is None
    storto = _legacy()
    storto["header"]["generator"] = "s3dgraphy 1.6.0.dev16"
    assert oz.declared_generator(storto) is None


def test_LA_NASCITA_DEL_PROGRAMMA_PRECEDE_TUTTO_e_il_cancello_la_accetta():
    """T0 = quando è nata `1.6.0.dev16`, misurato in git: 2026-08-24T20:50:37Z.

    Il documento è stato salvato una settimana dopo (mtime 2026-08-31) e la
    stanza dichiara di essere nata il 2026-09-04. La nascita del programma sta
    prima di tutte e due — è più antica del vero, cioè modesta.
    """
    nascita_del_programma = "2026-08-24T20:50:37Z"
    doc = _con_generatore()
    doc["graphs"]["g"]["nodes"][0]["data"][oz.CREATED_AT] = VIVO
    doc["graphs"]["g"]["nodes"][0]["data"][oz.CREATED_BY] = ANNA

    #: il limite è la nascita DICHIARATA della stanza, che qui viene prima
    #: della scrittura viva: `earliest_real_write` prende il minimo, ed è la
    #: cosa giusta perché nessuna scrittura può precedere la stanza.
    limite = oz.earliest_real_write(doc, room_created_at="2026-09-04T00:00:00Z")
    assert limite == "2026-09-04T00:00:00Z"
    copia, tocco = oz.dated(doc, nascita_del_programma, not_after=limite,
                            where="sarmizegetusa")
    assert tocco.total == 4                      # i due nodi e i due archi
    assert oz.unstamped(copia) == ([], [])

    #: e la mtime dello stesso documento, al suo posto, sarebbe passata anche
    #: lei qui — la differenza non è che il cancello la ferma, è che la nascita
    #: del programma è vera anche quando il file viene ricopiato.
    assert nascita_del_programma < "2026-08-31T21:06:41Z" < limite


# ── e ciò che NON è una data di registrazione ───────────────────────────────


def _con_una_epoca(start, end, nome):
    """Una `EpochNode` come quelle del corpus: dice quando è esistita la cosa."""
    doc = _legacy()
    doc["graphs"]["g"]["nodes"].append(
        {"id": "ep1", "node_type": "EpochNode", "name": nome,
         "data": {"start_time": start, "end_time": end}})
    return doc


def test_UNA_DATAZIONE_ARCHEOLOGICA_NON_ENTRA_nel_limite():
    """`portamarina` ha «IV d.C.» da 300 a 399. Non è una scrittura."""
    doc = _con_una_epoca(300, 399, "IV d.C.")
    assert oz.earliest_real_write(doc) is None
    #: e nemmeno quando nel documento una scrittura vera c'è: il limite è
    #: quella, non l'anno 300
    doc["graphs"]["g"]["nodes"][0]["data"][oz.CREATED_AT] = VIVO
    assert oz.earliest_real_write(doc) == VIVO


def test_E_IL_DANNO_SE_QUALCUNO_LA_USASSE_il_cancello_NON_lo_vede():
    """La prova che l'esclusione deve stare a monte: qui il cancello tace.

    `portamarina` ha davvero una `EpochNode` chiamata «y2018» che va da 1950 a
    2018 — una datazione che a un essere umano sembra una data di registrazione
    plausibile. Timbrare con quella passa il cancello (2018 è *prima* di ogni
    scrittura vera) e da quel momento il legacy batte tutto, per sempre.
    """
    doc = _con_una_epoca(1950, 2018, "y2018")
    doc["graphs"]["g"]["nodes"][0]["data"][oz.CREATED_AT] = VIVO
    doc["graphs"]["g"]["nodes"][0]["data"][oz.CREATED_BY] = ANNA
    limite = oz.earliest_real_write(doc)

    dallanno = "2018-01-01T00:00:00Z"
    oz.check_date(dallanno, not_after=limite, where="portamarina")   # …tace.

    #: ed ecco cosa avrebbe lasciato passare: un valore vivo contro un legacy
    #: timbrato nel 2018 vince ancora — ma un legacy timbrato nel 300 no.
    dal_quarto_secolo = "0300-01-01T00:00:00Z"
    oz.check_date(dal_quarto_secolo, not_after=limite)               # …tace anche qui.
    assert compare_clocks(Clock(ts=VIVO, by=ANNA),
                          Clock(ts=dal_quarto_secolo))[0] == 1

    #: Il danno non è nell'ordinamento: è nella frase. Il grafo direbbe che quel
    #: nodo è stato registrato nel IV secolo, e nessun cancello può accorgersene
    #: perché la data è, tecnicamente, sicura. L'unica difesa è a monte, ed è
    #: comportamentale: il limite guarda `created_at` e nient'altro — provato
    #: qui sopra e nel test precedente, non cercando parole nel sorgente.
    assert oz.earliest_real_write(doc) == VIVO
