"""P3 — collaborazione async in sicurezza: merge DATATO, conflitti VISIBILI,
versioning leggero.

Il merge per-UUID esisteva già ma decideva per ORDINE D'ARRIVO ("vince
l'entrante"): due rami che toccano lo stesso nodo e il lavoro di uno spariva in
silenzio. Qui si verifica che ora decida la DATA, che il perdente venga
ELENCATO, e che il progetto sappia dire a che revisione è arrivato.

  P3A  il merge è datato: vince il più recente, e l'esito NON dipende
       dall'ordine in cui integri i due file
  P3B  ogni nodo conteso finisce in `conflicts` con chi/quando/perché
  P3C  senza timbri la data NON decide: si dichiara `unstamped`, non si inventa
       un ordine
  P3D  versioning leggero: bump solo se il contenuto cambia, `was_revision_of`,
       pin citabile, proiezione PROV
  P3E  la prova end-to-end: due settori, un muro di confine, ricuciti
"""

import json

import pytest

from s3dgraphy import api
from s3dgraphy.container import (
    Container,
    ProjectVersion,
    bump_version,
    build_container,
    container_of,
    content_digest,
    merge_into_container,
    parse_container,
    pin_version,
)
from s3dgraphy.editorial import stamp_created, stamp_modified
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import StratigraphicUnit

ANNA = "0000-0002-1825-0097"
BRUNO = "0000-0001-5109-3700"


def _unit(node_id, name=None, description="", *, by=None, at=None, created=None):
    node = StratigraphicUnit(node_id, name=name or node_id, description=description)
    stamp_created(node, by=by, at=created or at)
    if at:
        stamp_modified(node, by=by, at=at)
    return node


def _project(graph_id, *nodes) -> Container:
    g = Graph(graph_id=graph_id, name=graph_id)
    for n in nodes:
        g.add_node(n)
    return container_of(g)


# ── P3A · la data decide, e l'ordine no ─────────────────────────────────────

def test_p3a_the_more_recent_version_wins():
    mine = _project("scavo", _unit("US1", description="muro in opus",
                                   by=ANNA, at="2026-08-13T10:00:00Z"))
    theirs = _project("scavo", _unit("US1", description="muro in opus reticulatum",
                                     by=BRUNO, at="2026-08-13T11:30:00Z"))
    report = merge_into_container(mine, theirs)
    node = mine.graphs["scavo"].find_node_by_id("US1")
    assert node.description == "muro in opus reticulatum"
    # 2 e non 1: ogni Graph porta con sé il proprio GeoPositionNode, che è
    # identico dalle due parti — infatti NON è un conflitto
    assert report.merged_nodes == 2
    assert [c.reason for c in report.conflicts] == ["newer"]


def test_p3a_an_older_incoming_version_does_not_overwrite():
    """Il caso che prima si perdeva: integro un file più VECCHIO e il mio
    lavoro resta. Con "vince l'entrante" qui spariva."""
    mine = _project("scavo", _unit("US1", description="lettura aggiornata",
                                   by=ANNA, at="2026-08-13T12:00:00Z"))
    theirs = _project("scavo", _unit("US1", description="lettura di ieri",
                                     by=BRUNO, at="2026-08-12T09:00:00Z"))
    report = merge_into_container(mine, theirs)
    assert mine.graphs["scavo"].find_node_by_id("US1").description == "lettura aggiornata"
    # e il conflitto è comunque ELENCATO: "non ti ho sovrascritto" è
    # un'informazione tanto quanto il contrario
    assert len(report.conflicts) == 1
    conflict = report.conflicts[0]
    assert conflict.winner["by"] == ANNA and conflict.loser["by"] == BRUNO
    assert conflict.winner["side"] == "mine"


def test_p3a_the_result_does_not_depend_on_the_merge_order():
    """A dentro B e B dentro A devono dare lo stesso progetto. È il minimo che
    uno strumento di collaborazione deve: due persone che integrano gli stessi
    due file non possono ritrovarsi con due studi diversi."""
    def side_a():
        return _project("scavo", _unit("US1", description="A", by=ANNA,
                                       at="2026-08-13T10:00:00Z"))

    def side_b():
        return _project("scavo", _unit("US1", description="B", by=BRUNO,
                                       at="2026-08-13T11:30:00Z"))

    a_into_b = side_b()
    merge_into_container(a_into_b, side_a())
    b_into_a = side_a()
    merge_into_container(b_into_a, side_b())
    assert (a_into_b.graphs["scavo"].find_node_by_id("US1").description
            == b_into_a.graphs["scavo"].find_node_by_id("US1").description == "B")


def test_p3a_the_winner_keeps_its_own_stamps():
    """Il nodo vincente NON viene ri-timbrato con la sessione che fa il merge:
    la mano di Bruno resta di Bruno. Stessa regola di `applyRemoteOp`."""
    mine = _project("scavo", _unit("US1", description="mio", by=ANNA,
                                   at="2026-08-13T10:00:00Z"))
    theirs = _project("scavo", _unit("US1", description="suo", by=BRUNO,
                                     at="2026-08-13T11:30:00Z"))
    merge_into_container(mine, theirs)
    data = mine.graphs["scavo"].find_node_by_id("US1").data
    assert data["modified_by"] == BRUNO
    assert data["modified_at"] == "2026-08-13T11:30:00Z"


def test_p3a_identical_content_is_not_a_conflict():
    """Due copie dello stesso nodo salvate in momenti diversi non sono un
    conflitto: nessun lavoro è in gioco, e una lista che grida al lupo è una
    lista che nessuno legge."""
    mine = _project("scavo", _unit("US1", description="uguale", by=ANNA,
                                   at="2026-08-13T10:00:00Z"))
    theirs = _project("scavo", _unit("US1", description="uguale", by=BRUNO,
                                     at="2026-08-13T11:30:00Z"))
    report = merge_into_container(mine, theirs)
    assert report.merged_nodes == 2      # US1 + il geo_position del grafo
    assert report.conflicts == []


def test_p3a_exact_tie_is_broken_stably_and_declared():
    mine = _project("scavo", _unit("US1", description="A", by=ANNA,
                                   at="2026-08-13T10:00:00Z"))
    theirs = _project("scavo", _unit("US1", description="B", by=BRUNO,
                                     at="2026-08-13T10:00:00Z"))
    report = merge_into_container(mine, theirs)
    # P4.1 · il nome del motivo dice ANCHE che cosa ha deciso: `tie-author`
    assert [c.reason for c in report.conflicts] == ["tie-author"]
    # il tie-break è arbitrario ma DICHIARATO e stabile (iD minore): quello che
    # non deve essere è casuale o dipendente dall'ordine
    assert mine.graphs["scavo"].find_node_by_id("US1").description == "B"
    assert report.conflicts[0].winner["by"] == BRUNO


# ── P3B · il conflitto si legge ─────────────────────────────────────────────

def test_p3b_the_conflict_names_who_overwrote_whom_and_where():
    mine = _project("scavo", _unit("US1", name="US1", description="muro",
                                   by=ANNA, at="2026-08-13T10:00:00Z"))
    theirs = _project("scavo", _unit("US1", name="US1 (rivisto)",
                                     description="muro di fondazione",
                                     by=BRUNO, at="2026-08-13T11:30:00Z"))
    report = merge_into_container(mine, theirs)
    # P4.1 · UN esito PER CAMPO, non un verdetto sul nodo intero: qui i campi
    # contesi sono due (name e description), quindi due voci.
    assert {c.field for c in report.conflicts} == {"name", "description"}
    c = report.conflicts[0].as_dict()
    assert c["node_id"] == "US1"
    # P4.1b · `removed` dice se ciò che ha vinto era un valore o uno SVUOTAMENTO
    assert c["winner"] == {"by": BRUNO, "at": "2026-08-13T11:30:00Z",
                           "stamp": "modified_at", "side": "theirs",
                           "removed": False}
    assert c["loser"]["by"] == ANNA and c["loser"]["at"] == "2026-08-13T10:00:00Z"
    # dove guardare: il campo, non un diff
    assert c["field_hint"] == [c["field"]]
    # il VALORE perdente viaggia col conflitto (e la versione intera pure), così
    # "tieni quella di Anna" non richiede di avere ancora aperto l'altro file
    desc = next(x for x in report.conflicts if x.field == "description")
    assert desc.loser_value == "muro"
    assert c["loser_payload"]["description"] == "muro"


def test_p3b_the_report_serialises_for_a_ui():
    mine = _project("scavo", _unit("US1", description="A", by=ANNA,
                                   at="2026-08-13T10:00:00Z"))
    theirs = _project("scavo", _unit("US1", description="B", by=BRUNO,
                                     at="2026-08-13T11:30:00Z"))
    payload = merge_into_container(mine, theirs).as_dict()
    assert json.loads(json.dumps(payload))["conflicts"][0]["reason"] == "newer"


# ── P3C · senza timbri la data non decide ───────────────────────────────────

def test_p3c_an_unstamped_side_is_declared_not_guessed():
    """Un nodo legacy non ha timbri. Non è "più vecchio": è ignoto. Si tiene il
    comportamento storico (entra l'entrante) e lo si DICHIARA."""
    legacy = StratigraphicUnit("US1", name="US1", description="senza timbri")
    mine = _project("scavo", legacy)
    theirs = _project("scavo", _unit("US1", description="con timbri", by=BRUNO,
                                     at="2026-08-13T11:30:00Z"))
    report = merge_into_container(mine, theirs)
    assert [c.reason for c in report.conflicts] == ["unstamped"]
    assert mine.graphs["scavo"].find_node_by_id("US1").description == "con timbri"
    assert report.conflicts[0].loser["at"] is None


def test_p3c_creation_dates_a_node_nobody_edited():
    """`created_at` come ripiego: un nodo mai modificato è datato dalla sua
    creazione, e il report dice QUALE timbro ha risposto."""
    mine = _project("scavo", _unit("US1", description="creato tardi", by=ANNA,
                                   created="2026-08-13T12:00:00Z"))
    theirs = _project("scavo", _unit("US1", description="modificato prima",
                                     by=BRUNO, at="2026-08-13T09:00:00Z"))
    report = merge_into_container(mine, theirs)
    assert report.conflicts[0].reason == "newer"
    assert report.conflicts[0].winner["stamp"] == "created_at"
    assert mine.graphs["scavo"].find_node_by_id("US1").description == "creato tardi"


# ── P3D · versioning leggero ────────────────────────────────────────────────

def test_p3d_a_save_that_changes_content_bumps_the_version(tmp_path):
    container = _project("scavo", _unit("US1", by=ANNA, at="2026-08-13T10:00:00Z"))
    path = tmp_path / "progetto.em.json"
    api.save_container_file(container, str(path))
    assert container.version.number == 1
    first_id = container.version.id
    assert first_id.startswith("sha256:")
    assert container.version.was_revision_of is None

    # ri-salvare senza cambiare nulla NON è una revisione: un contatore che
    # misura quante volte hai premuto ⌘S non dice niente sul lavoro
    api.save_container_file(container, str(path))
    assert container.version.number == 1 and container.version.id == first_id

    container.graphs["scavo"].add_node(_unit("US2", by=ANNA,
                                             at="2026-08-13T11:00:00Z"))
    api.save_container_file(container, str(path))
    assert container.version.number == 2
    assert container.version.was_revision_of == first_id


def test_p3d_the_version_survives_the_round_trip(tmp_path):
    container = _project("scavo", _unit("US1", by=ANNA, at="2026-08-13T10:00:00Z"))
    path = tmp_path / "progetto.em.json"
    api.save_container_file(container, str(path))
    back, warnings = api.load_container_file(str(path))
    assert warnings == []
    assert back.version.number == container.version.number
    assert back.version.id == container.version.id


def test_p3d_a_merge_is_a_new_version():
    mine = _project("scavo", _unit("US1", by=ANNA, at="2026-08-13T10:00:00Z"))
    bump_version(mine, at="2026-08-13T10:00:00Z")
    before = mine.version.id
    theirs = _project("altro_settore", _unit("US9", by=BRUNO,
                                             at="2026-08-13T11:00:00Z"))
    merge_into_container(mine, theirs)
    assert mine.version.number == 2
    assert mine.version.was_revision_of == before


def test_p3d_the_digest_ignores_the_layout():
    """Spostare una scatola non è una nuova versione dello studio."""
    container = _project("scavo", _unit("US1", by=ANNA, at="2026-08-13T10:00:00Z"))
    doc = build_container(container)
    first = content_digest(doc)
    container.layout = {"positions": {"US1": {"x": 10, "y": 20, "w": 90, "h": 30}}}
    assert content_digest(build_container(container)) == first


def test_p3d_pin_is_immutable_and_round_trips():
    container = _project("scavo", _unit("US1", description="al momento del pin",
                                        by=ANNA, at="2026-08-13T10:00:00Z"))
    snapshot = pin_version(container, at="2026-08-13T12:00:00Z")
    assert snapshot["id"] == container.version.id
    assert snapshot["pinned_at"] == "2026-08-13T12:00:00Z"

    # il lavoro continua: lo snapshot NON deve muoversi con lui
    container.graphs["scavo"].find_node_by_id("US1").description = "cambiato dopo"
    frozen = next(n for n in snapshot["document"]["graphs"]["scavo"]["nodes"]
                  if n["id"] == "US1")
    assert frozen["description"] == "al momento del pin"

    back, warnings = parse_container(snapshot["document"])
    assert warnings == []
    assert back.graphs["scavo"].find_node_by_id("US1").description == "al momento del pin"


def test_p3d_pinning_the_same_content_twice_is_the_same_pin():
    container = _project("scavo", _unit("US1", by=ANNA, at="2026-08-13T10:00:00Z"))
    first = pin_version(container, at="2026-08-13T12:00:00Z")
    second = pin_version(container, at="2026-08-13T12:05:00Z")
    assert first["id"] == second["id"]
    assert container.version.number == 1     # nessuna revisione inventata


rdflib = pytest.importorskip("rdflib")


def test_p3d_the_version_projects_as_prov(tmp_path):
    container = _project("scavo", _unit("US1", by=ANNA, at="2026-08-13T10:00:00Z"))
    bump_version(container, at="2026-08-13T10:00:00Z")
    first = container.version.id
    container.graphs["scavo"].add_node(_unit("US2", by=ANNA, at="2026-08-13T11:00:00Z"))
    bump_version(container, at="2026-08-13T11:00:00Z")

    out = api.container_to_ttl(container, str(tmp_path / "prog.trig"), format="trig")
    store = rdflib.ConjunctiveGraph()
    store.parse(out, format="trig")
    PROV = rdflib.Namespace("http://www.w3.org/ns/prov#")
    DCT = rdflib.Namespace("http://purl.org/dc/terms/")
    revisions = list(store.objects(None, PROV.wasRevisionOf))
    assert revisions and str(revisions[0]).endswith(first.replace(":", "_"))
    assert {str(o) for o in store.objects(None, DCT.hasVersion)} == {"2"}


# ── P3E · la prova end-to-end: due settori, un muro di confine ──────────────

def test_p3e_two_sectors_stitched_into_one_project():
    """Il caso vero. Anna sul settore Porta, Bruno sul settore Nord, e un muro
    al confine che tocca a entrambi.

    Ciò che deve succedere: i due settori arrivano interi (nessun conflitto,
    sono grafi diversi), il muro condiviso si risolve per data, la lista dice
    chi ha vinto, e il progetto sale di versione.
    """
    porta = Graph(graph_id="settore_porta", name="Settore Porta")
    porta.add_node(_unit("US-porta-1", by=ANNA, at="2026-08-13T09:00:00Z"))
    porta.add_node(_unit("US-muro-confine", description="muro, letto da Anna",
                         by=ANNA, at="2026-08-13T10:00:00Z"))
    anna = container_of(porta)
    bump_version(anna, at="2026-08-13T10:00:00Z")
    v_before = anna.version.id

    nord = Graph(graph_id="settore_nord", name="Settore Nord")
    nord.add_node(_unit("US-nord-1", by=BRUNO, at="2026-08-13T09:30:00Z"))
    bruno = container_of(nord)
    # lo stesso muro, sul confine: Bruno l'ha rivisto DOPO
    bruno.graphs["settore_porta"] = Graph(graph_id="settore_porta")
    bruno.graphs["settore_porta"].add_node(
        _unit("US-muro-confine", description="muro di fondazione, letto da Bruno",
              by=BRUNO, at="2026-08-13T11:30:00Z"))

    report = merge_into_container(anna, bruno)

    # il settore che Anna non aveva arriva intero, senza conflitti
    assert report.added_graphs == ["settore_nord"]
    assert report.merged_graphs == ["settore_porta"]
    assert sorted(anna.graph_ids()) == ["settore_nord", "settore_porta"]
    # solo il nodo condiviso è conteso: gli altri due sono disgiunti
    assert report.merged_nodes == 2      # il muro + il geo_position del settore
    assert len(report.conflicts) == 1
    conflict = report.conflicts[0]
    assert conflict.node_id == "US-muro-confine"
    assert conflict.winner["by"] == BRUNO and conflict.loser["by"] == ANNA
    assert conflict.reason == "newer"
    # il muro porta la lettura più recente…
    muro = anna.graphs["settore_porta"].find_node_by_id("US-muro-confine")
    assert muro.description == "muro di fondazione, letto da Bruno"
    # …e la lettura di Anna non è persa nel silenzio: viaggia col conflitto
    assert conflict.loser_payload["description"] == "muro, letto da Anna"
    # il progetto è una nuova revisione di quella di prima
    assert anna.version.number == 2 and anna.version.was_revision_of == v_before
