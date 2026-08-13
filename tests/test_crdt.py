"""P4.1 — l'algebra CRDT, provata su un tavolo (niente rete, niente server).

Sette prove, quelle che il design chiede prima di scrivere un relay:

  1  COMMUTATIVITÀ  applicare L1∘L2 e L2∘L1 → stesso digest canonico
  2  IDEMPOTENZA    applicare due volte la stessa op → niente si muove
  3  DELETE-vs-EDIT tombstone@T2 batte edit@T1; edit@T3 RESUSCITA (e lo dice)
  4  FIELD-LEVEL    A cambia `description`, B cambia `data.value` → ENTRAMBI
  5  STESSO CAMPO   concorrenti → vince (ts, author), in modo deterministico
  6  PARITÀ Py↔JS   fixture condivisa → stesso digest canonico dai due lati
  7  NIENTE REGRESSIONI  la suite invariante resta al suo baseline

La 6 è la ragione per cui questo file scrive anche una fixture su disco: il
controllo JS (`frontend/scripts/check-crdt.mjs`) legge la STESSA fixture e deve
arrivare allo stesso digest. Due implementazioni che non si vedono mai devono
poter essere confrontate su qualcosa.
"""

import json
import pathlib

from s3dgraphy import api, crdt
from s3dgraphy.container import (
    build_container,
    container_of,
    content_digest,
    merge_into_container,
)
from s3dgraphy.editorial import stamp_created, stamp_modified
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import StratigraphicUnit

ANNA = "0000-0002-1825-0097"
BRUNO = "0000-0001-5109-3700"

T1 = "2026-08-13T10:00:00Z"
T2 = "2026-08-13T11:00:00Z"
T3 = "2026-08-13T12:00:00Z"

#: la fixture condivisa col controllo JS — scritta qui, letta da entrambi
FIXTURE = (pathlib.Path(__file__).parent / "fixtures" / "crdt-parity.json")


def _section(*nodes, graph_id="scavo"):
    return {"graph_id": graph_id, "name": "Scavo",
            "nodes": [dict(n) for n in nodes], "edges": []}


def _node(node_id="US1", **data):
    payload = {"id": node_id, "node_type": "US", "name": node_id}
    if data:
        payload["data"] = dict(data)
    return payload


def _digest(section):
    return content_digest({"graphs": {section["graph_id"]: section},
                           "active_graph_id": section["graph_id"]})


# ── 1 · commutatività / convergenza ─────────────────────────────────────────

def test_1_two_op_logs_converge_whatever_the_order():
    """La proprietà su cui poggia tutto il disegno: l'ordine di arrivo non
    cambia lo stato finale. Senza questa, un relay dovrebbe ORDINARE, e allora
    servirebbe un coordinatore — cioè un'altra architettura."""
    base = _node("US1", created_at=T1, created_by=ANNA)
    l1 = [
        crdt.make_op("update_field", node_id="US1", field="description",
                     value="muro in opus", ts=T2, author=ANNA),
        crdt.make_op("update_field", node_id="US1", field="data.value",
                     value="1.20", ts=T2, author=ANNA),
    ]
    l2 = [
        crdt.make_op("update_field", node_id="US1", field="description",
                     value="muro di fondazione", ts=T3, author=BRUNO),
        crdt.make_op("add_node", node=_node("US2"), ts=T2, author=BRUNO),
    ]

    a = _section(base)
    crdt.apply_ops_to_section(a, l1 + l2)
    b = _section(base)
    crdt.apply_ops_to_section(b, l2 + l1)

    assert _digest(a) == _digest(b), "L1∘L2 e L2∘L1 devono convergere"
    # e non è convergenza per vuoto: il contenuto è quello atteso
    us1 = next(n for n in a["nodes"] if n["id"] == "US1")
    assert us1["description"] == "muro di fondazione"      # T3 batte T2
    assert us1["data"]["value"] == "1.20"                   # campo diverso, tenuto
    assert any(n["id"] == "US2" for n in a["nodes"])


def test_1b_interleavings_converge_too():
    """Non solo i due blocchi: anche mescolando le op una a una."""
    base = _node("US1", created_at=T1, created_by=ANNA)
    ops = [
        crdt.make_op("update_field", node_id="US1", field="name",
                     value="US1 (Anna)", ts=T2, author=ANNA),
        crdt.make_op("update_field", node_id="US1", field="name",
                     value="US1 (Bruno)", ts=T3, author=BRUNO),
        crdt.make_op("update_field", node_id="US1", field="description",
                     value="strato", ts=T2, author=BRUNO),
    ]
    digests = set()
    for order in ([0, 1, 2], [2, 1, 0], [1, 0, 2], [1, 2, 0]):
        section = _section(base)
        crdt.apply_ops_to_section(section, [ops[i] for i in order])
        digests.add(_digest(section))
    assert len(digests) == 1, f"quattro ordini, {len(digests)} stati diversi"


# ── 2 · idempotenza ─────────────────────────────────────────────────────────

def test_2_applying_the_same_op_twice_changes_nothing():
    section = _section(_node("US1", created_at=T1, created_by=ANNA))
    op = crdt.make_op("update_field", node_id="US1", field="description",
                      value="muro", ts=T2, author=ANNA)
    first = crdt.apply_op_to_section(section, op)
    after_one = _digest(section)
    second = crdt.apply_op_to_section(section, op)
    assert first.applied and not second.applied
    assert second.reason == "idempotent"
    assert _digest(section) == after_one


def test_2b_add_node_twice_is_one_node():
    section = _section()
    op = crdt.make_op("add_node", node=_node("US9"), ts=T1, author=ANNA)
    crdt.apply_op_to_section(section, op)
    before = _digest(section)
    crdt.apply_op_to_section(section, op)
    assert [n["id"] for n in section["nodes"]] == ["US9"]
    assert _digest(section) == before


def test_2c_a_stale_op_is_refused_and_says_so():
    """Un'op in ritardo non è un errore: è il CRDT che le impedisce di essere
    una regressione. Dirlo è ciò che distingue "converso" da "perso"."""
    section = _section(_node("US1", created_at=T1))
    crdt.apply_op_to_section(section, crdt.make_op(
        "update_field", node_id="US1", field="description", value="nuovo",
        ts=T3, author=BRUNO))
    late = crdt.apply_op_to_section(section, crdt.make_op(
        "update_field", node_id="US1", field="description", value="vecchio",
        ts=T2, author=ANNA))
    assert not late.applied and late.reason == "stale"
    assert next(n for n in section["nodes"] if n["id"] == "US1")["description"] == "nuovo"


# ── 3 · delete vs edit ──────────────────────────────────────────────────────

def test_3_a_deletion_later_than_the_edit_wins():
    section = _section(_node("US1", created_at=T1, created_by=ANNA))
    crdt.apply_op_to_section(section, crdt.make_op(
        "update_field", node_id="US1", field="description", value="edit",
        ts=T1, author=ANNA))
    crdt.apply_op_to_section(section, crdt.make_op(
        "remove_node", id="US1", ts=T2, author=BRUNO))
    node = next(n for n in section["nodes"] if n["id"] == "US1")
    assert crdt.is_removed(node)
    # il nodo NON sparisce dal record: è la vista che lo nasconde
    assert [n["id"] for n in section["nodes"]] == ["US1"]
    assert crdt.live_nodes(section) == []


def test_3b_an_edit_later_than_the_deletion_resurrects_it():
    """Deliberato e tracciato: senza tombstone questa risurrezione avverrebbe
    in silenzio ogni volta che qualcuno non aveva ancora visto la cancellazione."""
    section = _section(_node("US1", created_at=T1, created_by=ANNA))
    crdt.apply_op_to_section(section, crdt.make_op(
        "remove_node", id="US1", ts=T2, author=BRUNO))
    crdt.apply_op_to_section(section, crdt.make_op(
        "update_field", node_id="US1", field="description", value="ci ripenso",
        ts=T3, author=ANNA))
    node = next(n for n in section["nodes"] if n["id"] == "US1")
    assert not crdt.is_removed(node)
    assert len(crdt.live_nodes(section)) == 1


def test_3c_delete_vs_edit_converges_in_both_orders():
    base = _node("US1", created_at=T1, created_by=ANNA)
    delete = crdt.make_op("remove_node", id="US1", ts=T2, author=BRUNO)
    edit = crdt.make_op("update_field", node_id="US1", field="description",
                        value="tardi", ts=T3, author=ANNA)
    a, b = _section(base), _section(base)
    crdt.apply_ops_to_section(a, [delete, edit])
    crdt.apply_ops_to_section(b, [edit, delete])
    assert _digest(a) == _digest(b)


def test_3d_a_merge_reports_the_resurrection():
    """Il merge di due container: uno ha cancellato, l'altro ha scritto dopo."""
    def side(desc, at, by, removed=None):
        node = StratigraphicUnit("US1", name="US1", description=desc)
        stamp_created(node, by=by, at=T1)
        stamp_modified(node, by=by, at=at)
        if removed:
            node.data[crdt.REMOVED_KEY] = {"ts": removed[0], "by": removed[1]}
        g = Graph(graph_id="scavo")
        g.add_node(node)
        return container_of(g)

    deleted = side("com'era", T1, BRUNO, removed=(T2, BRUNO))
    edited = side("ci ripenso", T3, ANNA)
    report = merge_into_container(deleted, edited)
    node = deleted.graphs["scavo"].find_node_by_id("US1")
    assert not crdt.is_removed(crdt_payload(node))
    assert report.resurrected_nodes == 1
    assert any(c.reason == "resurrected" for c in report.conflicts)


def crdt_payload(node):
    from s3dgraphy.container import _node_snapshot
    return _node_snapshot(node)


# ── 4 · field-level: il regalo a P3 ─────────────────────────────────────────

def test_4_two_people_two_fields_both_kept():
    """Il limite dichiarato di P3, chiuso — a una condizione precisa.

    La fusione per campo funziona quando i campi portano il PROPRIO clock: è
    quello che producono le `update_field` (la strada del real-time) e quello che
    un editor scrive quando tocca un campo. Col solo timbro di nodo la
    granularità non esiste, e infatti il test qui sotto la misura.
    """
    def side(field_name, value, at, by):
        node = StratigraphicUnit("US1", name="US1", description="base")
        stamp_created(node, by=ANNA, at=T1)          # crea anche node.data
        if field_name == "description":
            node.description = value
        else:
            node.data["dating"] = value
        stamp_modified(node, by=by, at=at)
        api.stamp_field(node, field_name if field_name == "description"
                        else f"data.{field_name}", by=by, at=at)
        g = Graph(graph_id="scavo")
        g.add_node(node)
        return container_of(g)

    anna = side("description", "muro in opus", T2, ANNA)
    bruno = side("dating", "II sec. d.C.", T3, BRUNO)
    report = merge_into_container(anna, bruno)

    node = anna.graphs["scavo"].find_node_by_id("US1")
    assert node.description == "muro in opus"          # il campo di Anna, tenuto
    assert node.data["dating"] == "II sec. d.C."       # e quello di Bruno
    assert [c.field for c in report.conflicts] == []   # niente è stato perso


def test_4b_the_same_two_edits_converge_in_both_directions():
    def anna_side():
        node = StratigraphicUnit("US1", name="US1", description="muro in opus")
        stamp_created(node, by=ANNA, at=T1)
        stamp_modified(node, by=ANNA, at=T2)
        api.stamp_field(node, "description", by=ANNA, at=T2)
        g = Graph(graph_id="scavo")
        g.add_node(node)
        return container_of(g)

    def bruno_side():
        node = StratigraphicUnit("US1", name="US1", description="base")
        stamp_created(node, by=ANNA, at=T1)          # crea anche node.data
        node.data["dating"] = "II sec. d.C."
        stamp_modified(node, by=BRUNO, at=T3)
        api.stamp_field(node, "data.dating", by=BRUNO, at=T3)
        g = Graph(graph_id="scavo")
        g.add_node(node)
        return container_of(g)

    a = anna_side()
    merge_into_container(a, bruno_side())
    b = bruno_side()
    merge_into_container(b, anna_side())
    assert content_digest(build_container(a)) == content_digest(build_container(b))


def test_4c_without_field_clocks_the_node_stamp_decides_every_field():
    """IL LIMITE, misurato invece che dichiarato a parole.

    Senza clock per-campo l'unico orologio è quello del nodo, che parla per
    TUTTI i campi — compresi quelli che chi ha salvato per ultimo non ha
    toccato. Non è un difetto dell'algebra: senza un antenato comune non
    esiste modo di sapere CHI ha cambiato COSA, e indovinarlo produrrebbe nodi
    che non ha scritto nessuno dei due. La granularità la porta chi edita,
    scrivendo il clock del campo (`api.stamp_field`, o una `update_field`).
    """
    anna = _node("US1", created_at=T1, modified_at=T2, modified_by=ANNA)
    anna["description"] = "muro in opus"
    bruno = _node("US1", created_at=T1, modified_at=T3, modified_by=BRUNO)
    bruno["description"] = "base"
    bruno.setdefault("data", {})["dating"] = "II sec. d.C."

    outcome = crdt.merge_payloads(anna, bruno)
    assert outcome.payload["description"] == "base"        # il nodo più recente
    assert outcome.payload["data"]["dating"] == "II sec. d.C."
    # e la perdita NON è silenziosa: è un esito riportato, col valore perduto
    lost = [f for f in outcome.fields if f.field == "description"]
    assert lost and lost[0].loser_value == "muro in opus"


def test_4d_a_field_clock_beats_a_newer_node_stamp():
    """La granularità vince sul grossolano: il campo che porta il suo clock non
    viene travolto dal timbro di nodo dell'altro lato."""
    anna = _node("US1", created_at=T1, modified_at=T2, modified_by=ANNA)
    anna["description"] = "muro in opus"
    anna["data"][crdt.FIELD_CLOCKS_KEY] = {"description": {"ts": T3, "by": ANNA}}
    bruno = _node("US1", created_at=T1, modified_at=T2, modified_by=BRUNO)
    bruno["description"] = "base"

    outcome = crdt.merge_payloads(anna, bruno)
    assert outcome.payload["description"] == "muro in opus"


# ── 5 · stesso campo, concorrenti ───────────────────────────────────────────

def test_5_same_field_is_decided_by_clock_then_author():
    section = _section(_node("US1", created_at=T1))
    crdt.apply_op_to_section(section, crdt.make_op(
        "update_field", node_id="US1", field="description", value="di Anna",
        ts=T2, author=ANNA))
    crdt.apply_op_to_section(section, crdt.make_op(
        "update_field", node_id="US1", field="description", value="di Bruno",
        ts=T2, author=BRUNO))
    node = next(n for n in section["nodes"] if n["id"] == "US1")
    # stesso istante → decide l'iD minore, e BRUNO (…0001) < ANNA (…0002)
    assert node["description"] == "di Bruno"
    assert node["data"][crdt.FIELD_CLOCKS_KEY]["description"]["by"] == BRUNO


def test_5b_the_loser_is_reported_with_its_value():
    a = _node("US1", created_at=T1, modified_at=T2, modified_by=ANNA)
    a["description"] = "di Anna"
    b = _node("US1", created_at=T1, modified_at=T3, modified_by=BRUNO)
    b["description"] = "di Bruno"
    outcome = crdt.merge_payloads(a, b)
    assert outcome.payload["description"] == "di Bruno"
    assert len(outcome.fields) == 1
    lost = outcome.fields[0]
    assert lost.field == "description" and lost.reason == "newer"
    assert lost.loser_value == "di Anna"
    assert lost.winner["by"] == BRUNO and lost.loser["by"] == ANNA


def test_5c_merging_is_symmetric():
    a = _node("US1", created_at=T1, modified_at=T2, modified_by=ANNA)
    a["description"] = "di Anna"
    b = _node("US1", created_at=T1, modified_at=T3, modified_by=BRUNO)
    b["description"] = "di Bruno"
    assert (crdt.canonical(crdt.merge_payloads(a, b).payload)
            == crdt.canonical(crdt.merge_payloads(b, a).payload))


# ── 6 · parità Py ↔ JS ──────────────────────────────────────────────────────

def test_6_parity_fixture_digest_is_stable():
    """La fixture che il controllo JS legge, e il digest che deve ottenere.

    Non è un test di se stesso: il valore è PINNATO qui e ri-verificato in
    `frontend/scripts/check-crdt.mjs`. Se una delle due implementazioni cambia
    idea su un tie-break, questo numero si muove e il confronto lo dice.
    """
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    section = payload["section"]
    ops = payload["ops"]
    crdt.apply_ops_to_section(section, ops)
    digest = _digest(section)
    assert digest == payload["expected_digest"], (
        f"il digest Python è {digest}, la fixture dice {payload['expected_digest']}")
    # e l'ordine inverso arriva allo stesso posto
    section2 = json.loads(FIXTURE.read_text(encoding="utf-8"))["section"]
    crdt.apply_ops_to_section(section2, list(reversed(ops)))
    assert _digest(section2) == digest


# ── 7 · niente regressioni: nel file della suite, non qui ───────────────────
#
# La prova 7 è il `diff` dei FAILED contro il baseline noto (25) — si misura
# lanciando la suite, non asserendo su se stessa. Il numero è nel report.


# ═══════════════════════════════════════════════════════════════════════════
# P4.1b — la timbratura è l'atto di scrittura, e svuotare ha il suo tombstone
# ═══════════════════════════════════════════════════════════════════════════
#
# P4.1 aveva reso il field-level vero nell'algebra e DORMIENTE nell'uso: finché
# chi edita scriveva campi col solo timbro di nodo, due persone sullo stesso
# nodo si risolvevano ancora al nodo (test_4c). Qui si accende.


# ── D1 · nessuna scrittura non timbrata ─────────────────────────────────────

def test_d1_writing_a_field_always_stamps_it():
    """Non è disciplina, è che non c'è un altro modo: `set_field` fa le due cose
    in un atto solo, quindi un valore senza clock non si può produrre."""
    node = StratigraphicUnit("US1", name="US1", description="base")
    api.set_field(node, "description", "muro in opus", author=ANNA, at=T2)
    api.set_field(node, "data.dating", "II sec. d.C.", author=BRUNO, at=T3)

    clocks = node.data[crdt.FIELD_CLOCKS_KEY]
    assert clocks["description"] == {"ts": T2, "by": ANNA}
    assert clocks["data.dating"] == {"ts": T3, "by": BRUNO}
    assert node.description == "muro in opus" and node.data["dating"] == "II sec. d.C."
    # e la guardia non ha niente da dire su ciò che è passato di qui
    assert "description" not in api.unstamped_fields(node)
    assert "data.dating" not in api.unstamped_fields(node)


def test_d1b_an_update_field_op_stamps_too():
    """La stessa cosa dall'altra porta: un'operazione è l'altro modo di scrivere
    un campo, e passa per lo stesso atto."""
    section = _section(_node("US1", created_at=T1))
    crdt.apply_op_to_section(section, crdt.make_op(
        "update_field", node_id="US1", field="description", value="muro",
        ts=T2, author=ANNA))
    node = section["nodes"][0]
    assert node["data"][crdt.FIELD_CLOCKS_KEY]["description"] == {"ts": T2, "by": ANNA}
    # `name` resta senza clock: l'ha messo il costruttore, non un edit — ed è il
    # limite dichiarato della diagnostica (vede uno stato, non un gesto)
    assert "description" not in crdt.unstamped_fields(node)


def test_d1c_the_guard_sees_a_write_that_bypassed_the_act():
    """La diagnostica: un campo scritto a mano su un nodo che timbra viene
    datato alla CREAZIONE da chi legge — che è giusto per un valore del
    costruttore e sbagliato per una modifica. Qui si vede."""
    node = StratigraphicUnit("US1", name="US1", description="base")
    api.set_field(node, "description", "muro", author=ANNA, at=T2)
    node.data["dating"] = "scritto di nascosto"      # il bug: nessun clock
    assert "data.dating" in api.unstamped_fields(node)


# ── D2 · tombstone di CAMPO ─────────────────────────────────────────────────

def test_d2_a_field_removal_later_than_the_edit_wins():
    a = _node("US1", created_at=T1)
    a["description"] = "muro"
    crdt.write_field(a, "description", "muro", crdt.Clock(T1, ANNA))
    b = json.loads(json.dumps(a))
    crdt.clear_field(b, "description", crdt.Clock(T2, BRUNO))

    out = crdt.merge_payloads(a, b)
    assert out.payload.get("description") is None
    assert crdt.field_tombstone(out.payload, "description") is not None
    assert [f.reason for f in out.fields] == ["newer"]
    assert out.fields[0].winner["removed"] is True


def test_d2b_an_edit_later_than_the_removal_resurrects_the_field():
    a = _node("US1", created_at=T1)
    crdt.clear_field(a, "description", crdt.Clock(T2, BRUNO))
    b = json.loads(json.dumps(a))
    crdt.write_field(b, "description", "ci ripenso", crdt.Clock(T3, ANNA))

    out = crdt.merge_payloads(a, b)
    assert out.payload["description"] == "ci ripenso"
    assert crdt.field_tombstone(out.payload, "description") is None
    assert [f.reason for f in out.fields] == ["resurrected"]


def test_d2c_a_field_removal_converges_in_both_orders():
    base = _node("US1", created_at=T1)
    crdt.write_field(base, "description", "muro", crdt.Clock(T1, ANNA))
    a = json.loads(json.dumps(base))
    crdt.clear_field(a, "description", crdt.Clock(T2, BRUNO))
    b = json.loads(json.dumps(base))
    crdt.write_field(b, "data.dating", "II sec.", crdt.Clock(T3, ANNA))
    assert (crdt.canonical(crdt.merge_payloads(a, b).payload)
            == crdt.canonical(crdt.merge_payloads(b, a).payload))


# ── D3 · svuotare ≠ non aver mai avuto ──────────────────────────────────────

def test_d3_an_emptied_field_does_not_come_back_from_an_absence():
    """I due casi convivono, ed è il punto delicato di tutto il mattone:

    * P4.1 · un campo che l'altro **non ha mai avuto** NON viene cancellato
      (assenza ≠ cancellazione);
    * P4.1b · un campo che l'altro ha **svuotato di proposito** resta vuoto.

    Sono distinguibili solo perché lo svuotamento lascia un marcatore.
    """
    emptied = _node("US1", created_at=T1)
    crdt.write_field(emptied, "description", "c'era", crdt.Clock(T1, ANNA))
    crdt.clear_field(emptied, "description", crdt.Clock(T2, ANNA))
    never_had = _node("US1", created_at=T1)      # nessuna descrizione, nessun clock

    out = crdt.merge_payloads(emptied, never_had)
    assert out.payload.get("description") is None, "lo svuotamento resta"
    assert crdt.field_tombstone(out.payload, "description") is not None

    # …e il caso di P4.1, che NON deve essere cambiato da questo mattone
    has_it = _node("US1", created_at=T1)
    crdt.write_field(has_it, "data.nota", "una nota", crdt.Clock(T1, ANNA))
    plain = _node("US1", created_at=T2)
    assert crdt.merge_payloads(has_it, plain).payload["data"]["nota"] == "una nota"


# ── D4 · il field-level è VIVO ──────────────────────────────────────────────

def test_d4_the_dormant_case_wakes_up_when_the_edit_path_stamps():
    """Il gemello di `test_4c`, con la SOLA differenza che conta: qui si scrive
    dall'edit-path. Stessa situazione, esito opposto — ed è la misura di che
    cosa fa la timbratura."""
    def side(field_name, value, at, by):
        node = StratigraphicUnit("US1", name="US1", description="base")
        stamp_created(node, by=ANNA, at=T1)
        api.set_field(node, field_name, value, author=by, at=at)
        stamp_modified(node, by=by, at=at)
        g = Graph(graph_id="scavo")
        g.add_node(node)
        return container_of(g)

    anna = side("description", "muro in opus", T2, ANNA)
    bruno = side("data.dating", "II sec. d.C.", T3, BRUNO)
    report = merge_into_container(anna, bruno)

    node = anna.graphs["scavo"].find_node_by_id("US1")
    assert node.description == "muro in opus"       # in P4.1 qui usciva "base"
    assert node.data["dating"] == "II sec. d.C."
    assert [c.field for c in report.conflicts] == []


# ── D5 · parità Py↔JS della NUOVA fixture ───────────────────────────────────

FIXTURE_B = (pathlib.Path(__file__).parent / "fixtures" / "crdt-parity-fields.json")


def test_d5_field_clocks_and_field_tombstones_have_the_same_digest():
    payload = json.loads(FIXTURE_B.read_text(encoding="utf-8"))
    section = payload["section"]
    crdt.apply_ops_to_section(section, payload["ops"])
    digest = _digest(section)
    assert digest == payload["expected_digest"], (
        f"il digest Python è {digest}, la fixture dice {payload['expected_digest']}")
    section2 = json.loads(FIXTURE_B.read_text(encoding="utf-8"))["section"]
    crdt.apply_ops_to_section(section2, list(reversed(payload["ops"])))
    assert _digest(section2) == digest, "e l'ordine inverso arriva allo stesso posto"
