"""Le piste, e la riga che non devono mai attraversare.

Una pista è «ho visto questo digest in questo posto, in questo momento»: un
registro mutevole, plurale e non autorevole, che sta **fuori** dal timbro perché
un record immutabile non può contenere un campo mutevole.

La prova che conta di più qui non è che il file si scriva: è che un percorso
assoluto — quello che porta il nome utente, la struttura delle cartelle e a volte
il nome di un committente — **non compaia in nulla che sia destinato a uscire**.
"""

from __future__ import annotations

import json
import os

import pytest

from s3dgraphy.graph import Graph
from s3dgraphy.nodes import ResourceNode
from s3dgraphy.publication import promote_resource
from s3dgraphy.stamp import (absorb_stamp_file, clean_stamp, emit_stamp,
                             file_digest, for_export, hints_filename,
                             new_hints, note_seen, private_locators,
                             read_hints, read_stamp, scan_directory,
                             stamp_filename, substance, write_hints,
                             write_public_hints, write_stamp)

SHA = "sha256:" + "aa" * 32
PRIVATO = "/Users/mrossi/lavori/Fondazione X/2015/nuvola.ply"
PUBBLICO = "s3://em-assets/res_91c2/nuvola.ply"


def _registro() -> dict:
    hints = new_hints(SHA)
    note_seen(hints, PUBBLICO, when="2026-09-14T09:12:00Z")
    note_seen(hints, PRIVATO, machine="mbp-ed", when="2026-09-14T18:40:11Z")
    return hints


# ── T4 · il file separato ────────────────────────────────────────────────────

def test_lo_scope_si_deduce_dal_locator_e_il_dubbio_va_verso_private():
    """Un URI di store è un indirizzo; **tutto il resto è privato per difetto**.

    Il verso del default è la decisione: sbagliare verso «privato» costa una
    pista che non viaggia, sbagliare verso «pubblico» costa il nome utente di
    qualcuno.
    """
    hints = _registro()
    per_locator = {e["locator"]: e for e in hints["seen"]}
    assert per_locator[PUBBLICO]["scope"] == "public"
    assert per_locator[PUBBLICO]["kind"] == "s3"
    assert per_locator[PRIVATO]["scope"] == "private"
    assert per_locator[PRIVATO]["kind"] == "local"

    ignoto = new_hints(SHA)
    note_seen(ignoto, "qualcosa-che-non-riconosco", when="2026-09-14T00:00:00Z")
    assert ignoto["seen"][0]["scope"] == "private"


def test_UNA_PISTA_PRIVATE_NON_COMPARE_IN_CIO_CHE_ESCE():
    """La prova di riservatezza, e non di pulizia.

    Misurata su **tutto il testo** di quello che esce, non sulle chiavi: un
    percorso può nascondersi in un campo che nessuno ha pensato di filtrare, e
    un'asserzione sulle chiavi non lo vedrebbe.
    """
    hints = _registro()
    che_esce = for_export(hints)
    testo = json.dumps(che_esce, ensure_ascii=False)

    assert PRIVATO not in testo
    assert "mrossi" not in testo
    assert "Fondazione X" not in testo
    assert PUBBLICO in testo
    assert [e["locator"] for e in che_esce["seen"]] == [PUBBLICO]
    # …e il registro di casa non è stato toccato: esce una copia
    assert private_locators(hints) == [PRIVATO]


def test_il_nome_della_macchina_non_esce_nemmeno_da_una_pista_pubblica():
    """Il nome del computer di una persona non è parte di un indirizzo."""
    hints = new_hints(SHA)
    note_seen(hints, PUBBLICO, machine="mbp-ed", when="2026-09-14T09:12:00Z")
    assert "mbp-ed" not in json.dumps(for_export(hints))


def test_la_porta_verso_lesterno_non_ha_un_interruttore(tmp_path):
    """`write_public_hints` non ha un parametro per disattivare il filtro.

    Una porta che si può aprire a metà è una porta che un giorno qualcuno apre a
    metà. Provato leggendo il file scritto, non la firma della funzione.
    """
    hints = _registro()
    fuori = tmp_path / hints_filename(SHA, asset="nuvola")
    write_public_hints(hints, str(fuori))
    assert PRIVATO not in fuori.read_text(encoding="utf-8")

    casa = tmp_path / "casa.hints.json"
    write_hints(hints, str(casa))
    # il file DI CASA invece le tiene tutte: è lì che servono
    assert PRIVATO in casa.read_text(encoding="utf-8")
    assert read_hints(str(casa))["seen"] == hints["seen"]


def test_LE_PISTE_NON_SONO_COPERTE_DA_NESSUN_DIGEST_DEL_TIMBRO():
    """Il timbro non nomina le piste, in nessun campo.

    È la ragione per cui i due file sono due: un record immutabile non può
    contenere un campo mutevole, perché riscriverlo ne cambierebbe il contenuto.
    Se un giorno un locator finisse nel timbro, questo test lo vedrebbe.
    """
    graph = Graph(graph_id="graph:x")
    graph.add_node(ResourceNode("res:nuvola", name="nuvola", checksum=SHA,
                                url=PRIVATO))
    promote_resource(graph, "res:mesh", url="s3://em-assets/mesh.glb",
                     sha256="sha256:" + "6e" * 32, source_id="res:nuvola",
                     name="mesh")
    testo = json.dumps(clean_stamp(emit_stamp(graph, "res:mesh")))
    assert PRIVATO not in testo
    assert "hints" not in testo
    assert "locator" not in testo


def test_i_due_file_hanno_due_nomi_e_nessuno_dei_due_e_em_json():
    """`<asset>.stamp.json` e `<asset>.hints.json`, in inglese.

    Non `em.json` (specie diversa: inviterebbe a fondere, editare, versionare un
    verbale) e non `dtc.json` (prometterebbe una catena e consegna un anello).
    """
    graph = Graph(graph_id="graph:x")
    graph.add_node(ResourceNode("res:mesh", name="mesh", checksum=SHA))
    stamp = emit_stamp(graph, "res:mesh")
    assert stamp_filename(stamp, asset="GT16-mesh") == "GT16-mesh.stamp.json"
    assert hints_filename(SHA, asset="GT16-mesh") == "GT16-mesh.hints.json"
    for nome in (stamp_filename(stamp), hints_filename(SHA)):
        assert not nome.endswith("em.json")
        assert "dtc.json" not in nome
    # un id con i due punti non diventa un percorso
    assert stamp_filename(stamp) == "res_mesh.stamp.json"


# ── T4 · l'aggiornamento è passivo ───────────────────────────────────────────

def test_riosservare_AGGIORNA_e_non_duplica():
    """Le piste non si cancellano, invecchiano — e non si moltiplicano.

    Lo stesso locator sulla stessa macchina è la stessa pista riosservata: le si
    rinfresca il `when`. Una riga per ogni sguardo farebbe crescere il file senza
    aggiungere un fatto.
    """
    hints = new_hints(SHA)
    note_seen(hints, PRIVATO, machine="mbp-ed", when="2026-09-14T09:00:00Z")
    note_seen(hints, PRIVATO, machine="mbp-ed", when="2026-09-20T09:00:00Z")
    assert len(hints["seen"]) == 1
    assert hints["seen"][0]["when"] == "2026-09-20T09:00:00Z"

    # …ma lo STESSO percorso su UN'ALTRA macchina è un'altra pista
    note_seen(hints, PRIVATO, machine="fisso", when="2026-09-20T10:00:00Z")
    assert len(hints["seen"]) == 2


def test_una_pista_vecchia_non_viene_rimossa_da_niente():
    """Non esiste nessuna funzione che chieda di sistemare un percorso.

    Provato come assenza di superficie: il modulo non espone né un `forget`, né
    un `prune`, né un `fix`. Un file spostato non è un errore da correggere, è un
    fatto da riosservare.
    """
    from s3dgraphy.stamp import hints as modulo

    proibiti = {"forget", "prune", "fix", "repair", "remove_hint",
                "cleanup", "validate_locators"}
    assert proibiti & set(dir(modulo)) == set()

    hints = _registro()
    prima = list(hints["seen"])
    note_seen(hints, "s3://em-assets/altro.ply", when="2026-09-21T00:00:00Z")
    assert hints["seen"][:2] == prima          # le vecchie sono ancora lì


def test_scansione_di_una_cartella(tmp_path):
    (tmp_path / "sotto").mkdir()
    uno = tmp_path / "a.ply"
    due = tmp_path / "sotto" / "b.ply"
    uno.write_bytes(b"punti")
    due.write_bytes(b"punti")               # **gli stessi byte**: un digest solo
    tre = tmp_path / "c.txt"
    tre.write_bytes(b"altro")

    esito = scan_directory(str(tmp_path), machine="prova",
                           when="2026-09-14T12:00:00Z", suffixes=(".ply",))
    trovati = esito["found"]
    assert esito["unreadable"] == []
    assert len(trovati) == 1, "due file con gli stessi byte sono un digest solo"
    digest = file_digest(str(uno))
    assert digest in trovati
    # due posti, due piste, tutte e due private perché sono percorsi su disco
    posti = {e["locator"] for e in trovati[digest]["seen"]}
    assert posti == {str(uno), str(due)}
    assert all(e["scope"] == "private" for e in trovati[digest]["seen"])
    # e il .txt non c'è: il filtro sui suffissi ha morso
    assert file_digest(str(tre)) not in trovati


def test_una_scansione_SI_AGGIUNGE_alle_osservazioni_di_prima(tmp_path):
    """Un file che oggi non c'è più non smette di essere stato visto ieri altrove."""
    (tmp_path / "a.ply").write_bytes(b"punti")
    digest = file_digest(str(tmp_path / "a.ply"))
    prima = {digest: new_hints(digest)}
    note_seen(prima[digest], PUBBLICO, when="2026-01-01T00:00:00Z")

    esito = scan_directory(str(tmp_path), machine="prova",
                           when="2026-09-14T12:00:00Z", into=prima)
    posti = {e["locator"] for e in esito["found"][digest]["seen"]}
    assert PUBBLICO in posti and str(tmp_path / "a.ply") in posti


def test_scandire_qualcosa_che_non_e_una_cartella_solleva(tmp_path):
    file = tmp_path / "non-sono-una-cartella.txt"
    file.write_bytes(b"x")
    with pytest.raises(NotADirectoryError):
        scan_directory(str(file))


def test_il_digest_di_un_file_porta_il_suo_algoritmo(tmp_path):
    file = tmp_path / "x.bin"
    file.write_bytes(b"ciao")
    import hashlib

    assert file_digest(str(file)) == \
        "sha256:" + hashlib.sha256(b"ciao").hexdigest()


def test_un_file_grande_si_legge_a_blocchi(tmp_path):
    """Un digest che muore sui file grandi fallisce sui dati che valeva la pena
    identificare. Provato con un blocco più piccolo del file."""
    import hashlib

    file = tmp_path / "grande.bin"
    contenuto = os.urandom(300_000)
    file.write_bytes(contenuto)
    assert file_digest(str(file), chunk=1024) == \
        "sha256:" + hashlib.sha256(contenuto).hexdigest()


# ── il giro completo, passando per il disco ──────────────────────────────────

def test_giro_completo_attraverso_i_file(tmp_path):
    """Grafo → file → grafo: la stessa prova di T3, con il filesystem in mezzo.

    Serve perché `write_stamp` toglie le note e `read_stamp` rivalida: due passi
    che l'emissione in memoria non attraversa mai.
    """
    graph = Graph(graph_id="graph:disco", name="Great Temple")
    graph.add_node(ResourceNode("res:nuvola", name="nuvola", checksum=SHA))
    promote_resource(graph, "res:mesh", url="s3://em-assets/mesh.glb",
                     sha256="sha256:" + "6e" * 32, source_id="res:nuvola",
                     author="0000-0002-5065-7970", at="2026-09-15T20:14:07Z",
                     name="mesh", packaging="file", size_bytes=99)

    andata = emit_stamp(graph, "res:mesh")
    percorso = tmp_path / stamp_filename(andata, asset="GT16-mesh")
    write_stamp(andata, str(percorso))
    # il file che esce NON porta le note di chi l'ha scritto
    assert "_notes" not in json.loads(percorso.read_text(encoding="utf-8"))

    arrivo = Graph(graph_id="graph:ricostruito")
    esito = absorb_stamp_file(arrivo, str(percorso))
    assert esito.applied, esito.as_dict()
    assert substance(clean_stamp(emit_stamp(arrivo, "res:mesh"))) == \
        substance(read_stamp(str(percorso)))
