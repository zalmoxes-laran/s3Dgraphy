"""Il timbro: emissione, riassorbimento, e il giro completo.

Le prove sono costruite sul substrato **vero** — `promote_resource` e
`declare_derivation`, le stesse funzioni che scrivono i grafi di tutti i giorni —
e non su grafi montati a mano campo per campo. La differenza conta: un grafo
montato a mano assomiglia a quello che chi scrive il test si aspetta, e un timbro
che legge quel grafo dimostra solo che le due aspettative coincidono.
"""

from __future__ import annotations

import json

import pytest

from s3dgraphy.dtc.ingest import declare_derivation
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import ResourceNode
from s3dgraphy.publication import promote_resource
from s3dgraphy.stamp import (absorb_stamp, clean_stamp, compare_stamps,
                             emit_stamp, identity_strength, is_verifiable,
                             stamp_to_graph, substance, validate_stamp)
from s3dgraphy.stamp.absorb import BadStamp
from s3dgraphy.stamp.emit import NotAnArtifact

SHA_OUT = "sha256:" + "6e" * 32
SHA_IN = "sha256:" + "a1" * 32
SHA_IN2 = "sha256:" + "b2" * 32
ORCID = "0000-0002-5065-7970"


# ── i tre grafi su cui si misura ─────────────────────────────────────────────

def _grafo_con_un_ingresso() -> Graph:
    """Un passo con UN ingresso: la mesh che esce dalla nuvola."""
    graph = Graph(graph_id="graph:uno", name="Great Temple")
    graph.add_node(ResourceNode("res:nuvola", name="GT16 · rilievo 2015, nuvola",
                                url="s3://em-assets/nuvola.ply",
                                checksum=SHA_IN))
    promote_resource(graph, "res:mesh", url="s3://em-assets/mesh.glb",
                     sha256=SHA_OUT, media_type="model/gltf-binary",
                     source_id="res:nuvola", author=ORCID,
                     at="2026-09-15T20:14:07Z", name="GT16 · mesh decimata",
                     packaging="file", size_bytes=1234567,
                     primitives={"faces": 48210})
    return graph


def _grafo_con_n_ingressi() -> Graph:
    """Il tileset che esce da N mesh: la derivazione N:1 che il DTC porta nativa."""
    graph = Graph(graph_id="graph:enne", name="Great Temple")
    for i, digest in enumerate((SHA_IN, SHA_IN2), start=1):
        graph.add_node(ResourceNode(f"res:mesh{i}", name=f"mesh {i}",
                                    url=f"s3://em-assets/mesh{i}.glb",
                                    checksum=digest))
    promote_resource(graph, "res:tileset", url="s3://em-assets/tileset.zip",
                     sha256=SHA_OUT, media_type="application/octet-stream",
                     source_ids=["res:mesh1", "res:mesh2"], author=ORCID,
                     at="2026-09-15T21:00:00Z", name="tileset",
                     packaging="archive", primitives={"tiles": 812})
    return graph


def _grafo_passo_vuoto() -> Graph:
    """Una risorsa senza genitori — un proxy modellato a mano, una foto di campo.

    Il passo c'è (qualcuno l'ha pubblicata, in un momento, con una mano) e i
    genitori non ci sono. È **metà del mondo reale**.
    """
    graph = Graph(graph_id="graph:vuoto", name="Aiano")
    promote_resource(graph, "res:proxy", url="s3://em-assets/proxy.glb",
                     sha256=SHA_OUT, media_type="model/gltf-binary",
                     author=ORCID, at="2026-09-15T22:00:00Z",
                     name="proxy modellato a mano", packaging="file")
    return graph


CASI = {
    "un ingresso": (_grafo_con_un_ingresso, "res:mesh"),
    "N ingressi": (_grafo_con_n_ingressi, "res:tileset"),
    "passo vuoto": (_grafo_passo_vuoto, "res:proxy"),
}


# ── T1 · emettere ────────────────────────────────────────────────────────────

def test_emissione_nomina_lartefatto_e_il_passo():
    stamp = emit_stamp(_grafo_con_un_ingresso(), "res:mesh")
    assert stamp["stamp"] == 1
    assert stamp["self"]["resource_id"] == "res:mesh"
    assert stamp["self"]["digest"] == SHA_OUT
    assert stamp["self"]["digest_covers"] == "artifact"
    assert stamp["self"]["media_type"] == "model/gltf-binary"
    assert stamp["self"]["packaging"] == "file"
    assert stamp["self"]["tier"] == "distribution"
    # `measures` è PIATTO nel formato: il peso e i conteggi nello stesso posto
    assert stamp["self"]["measures"] == {"size_bytes": 1234567, "faces": 48210}
    assert stamp["how"]["process_id"]
    assert stamp["by"]["at"] == "2026-09-15T20:14:07Z"
    assert stamp["by"]["operator"]["id"] == f"https://orcid.org/{ORCID}"


def test_gli_ingressi_si_nominano_e_NON_si_aprono():
    """La regola che ferma la ricorsione: tre campi, e nient'altro.

    Provata come tale — non «il digest c'è», ma **l'insieme delle chiavi è
    esattamente quello**. Un campo in più aggiunto per comodità fra sei mesi
    (l'url, «tanto ce l'ho») sarebbe la catena intera in ogni anello, e questo
    test è la cosa che lo impedisce.
    """
    graph = _grafo_con_un_ingresso()
    # la risorsa di ingresso ha un url, un url_type, una descrizione: roba che
    # il timbro DEVE tacere
    ingresso = graph.find_node_by_id("res:nuvola")
    assert ingresso.data.get("url")

    stamp = emit_stamp(graph, "res:mesh")
    assert len(stamp["from"]) == 1
    parent = stamp["from"][0]
    assert set(parent) == {"resource_id", "digest", "label"}
    assert parent["resource_id"] == "res:nuvola"
    assert parent["digest"] == SHA_IN
    # e nessuna espansione ricorsiva: nel timbro non compare da nessuna parte
    # ciò che sta a monte dell'ingresso
    testo = json.dumps(clean_stamp(stamp))
    assert "s3://em-assets/nuvola.ply" not in testo


def test_n_ingressi_sono_n_righe_e_nessuna_apre():
    stamp = emit_stamp(_grafo_con_n_ingressi(), "res:tileset")
    assert [p["resource_id"] for p in stamp["from"]] == ["res:mesh1", "res:mesh2"]
    for parent in stamp["from"]:
        assert set(parent) <= {"resource_id", "digest", "label", "kind"}


def test_PASSO_VUOTO_from_vuoto_e_una_dichiarazione_completa():
    """`"from": []` non è un errore: è «nato qui, da questa persona, adesso».

    La chiave deve **esserci** ed essere una lista vuota. Un timbro che
    omettesse il campo direbbe «non so da cosa viene», che è l'opposto.
    """
    stamp = emit_stamp(_grafo_passo_vuoto(), "res:proxy")
    assert "from" in stamp
    assert stamp["from"] == []
    # …e il resto della dichiarazione c'è tutta: chi, quando, con che processo
    assert stamp["how"]["process_id"]
    assert stamp["by"]["at"] == "2026-09-15T22:00:00Z"
    assert stamp["by"]["operator"]["id"].endswith(ORCID)
    assert stamp["self"]["digest"] == SHA_OUT


def test_senza_operatore_lagente_e_il_software_in_how():
    """`by.operator` può mancare — bake in batch, servizio, chatbot.

    Quando manca non si scrive nessun «unknown»: si tace, e la regola del
    formato dice che l'agente è il software nominato in `how`. Il timbro lo
    annota fra le note perché chi lo riceve non debba conoscere la regola a
    memoria.
    """
    graph = Graph(graph_id="graph:batch")
    promote_resource(graph, "res:out", url="s3://em-assets/out.glb",
                     sha256=SHA_OUT, name="out")
    processo = [n for n in graph.nodes if n.node_type == "dtc_process"][0]
    processo.data["software"] = [
        {"name": "EM Tools", "version": "1.6.0-dev.8", "commit": "9555447"},
        {"name": "s3dgraphy", "version": "1.6.0.dev17", "commit": "afe62e3"},
    ]

    stamp = emit_stamp(graph, "res:out")
    assert "operator" not in (stamp.get("by") or {})
    assert stamp["how"]["software"][0]["name"] == "EM Tools"
    assert any("the agent is the software" in n for n in stamp["_notes"])


def test_il_vecchio_tool_diventa_una_lista_di_uno():
    """Un grafo scritto prima di stanotte dice comunque con che cosa è stato fatto.

    `declare_derivation` scrive `data.tool = {"name": …}` — **uno** strumento —
    mentre il formato ne vuole una lista. Il ponte sta nell'emissione, così
    nessun grafo esistente va migrato per poter essere timbrato.
    """
    graph = Graph(graph_id="graph:vecchio")
    graph.add_node(ResourceNode("res:in", name="in", checksum=SHA_IN))
    graph.add_node(ResourceNode("res:out", name="out", checksum=SHA_OUT))
    declare_derivation(graph, "res:out", ["res:in"], tool="MeshLab")
    stamp = emit_stamp(graph, "res:out")
    assert stamp["how"]["software"] == [{"name": "MeshLab"}]


def test_emissione_NON_scrive_i_ripieghi_del_consumatore():
    """`effective_tier()` e compagni sono letture, e una lettura non si timbra.

    Una risorsa che non dichiara né `tier` né `packaging` emette un timbro che
    tace su tutti e due. Se il timbro scrivesse il ripiego, riassorbirlo lo
    trasformerebbe in un'affermazione — e al secondo giro nessuno saprebbe più
    distinguere una cosa dichiarata da una dedotta.
    """
    graph = Graph(graph_id="graph:muto")
    graph.add_node(ResourceNode("res:muta", name="muta",
                                url="s3://em-assets/x.bin", checksum=SHA_OUT))
    nodo = graph.find_node_by_id("res:muta")
    # il ripiego ESISTE e direbbe qualcosa…
    assert nodo.effective_tier() == "distribution"
    assert nodo.effective_packaging() == "file"
    # …ma il timbro tace
    stamp = emit_stamp(graph, "res:muta")
    assert "tier" not in stamp["self"]
    assert "packaging" not in stamp["self"]


def test_emissione_e_pura_e_ripetibile():
    """Nessun orologio, nessun filesystem: due emissioni sono identiche.

    È la proprietà che rende il timbro provabile e i suoi disaccordi
    significativi: se l'emissione chiedesse l'ora, due timbri dello stesso grafo
    differirebbero e ogni confronto sarebbe rumore.
    """
    graph = _grafo_con_un_ingresso()
    assert emit_stamp(graph, "res:mesh") == emit_stamp(graph, "res:mesh")


def test_si_puo_timbrare_partendo_dal_digest():
    stamp = emit_stamp(_grafo_con_un_ingresso(), SHA_OUT)
    assert stamp["self"]["resource_id"] == "res:mesh"


def test_un_artefatto_che_non_ce_non_produce_un_timbro_vuoto():
    with pytest.raises(NotAnArtifact):
        emit_stamp(_grafo_con_un_ingresso(), "res:inesistente")


def test_il_registry_non_inventa_una_revisione():
    """«Un indizio per ritrovare, non un'autorità»: quello che nessuno ha detto
    non compare. Una `revision` inventata renderebbe citabile ciò che non lo è."""
    stamp = emit_stamp(_grafo_con_un_ingresso(), "res:mesh")
    assert stamp["registry"]["graph_id"] == "graph:uno"
    assert "revision" not in stamp["registry"]
    assert "room" not in stamp["registry"]

    con_posto = emit_stamp(_grafo_con_un_ingresso(), "res:mesh",
                           revision=47, room="em.localhost/aiano")
    assert con_posto["registry"]["revision"] == 47
    assert con_posto["registry"]["room"] == "em.localhost/aiano"


# ── T3 · il giro completo ────────────────────────────────────────────────────

@pytest.mark.parametrize("caso", list(CASI))
def test_GIRO_COMPLETO_grafo_timbro_grafo(caso):
    """**La prova che conta più di tutte le altre messe insieme.**

    Grafo → timbro → grafo, e i due grafi dicono la stessa cosa sul chunk
    emesso. Misurata confrontando i due TIMBRI e non i due grafi: il grafo di
    partenza porta anche altro (il nodo di ingresso ha un url, il grafo ha un
    nome), e il timbro è per definizione ciò che di quel grafo riguarda il passo.
    """
    costruisci, ref = CASI[caso]
    partenza = costruisci()
    timbro = clean_stamp(emit_stamp(partenza, ref))

    arrivo = Graph(graph_id="graph:ricostruito")
    esito = absorb_stamp(arrivo, timbro)
    assert esito.applied, esito.as_dict()

    ritimbro = clean_stamp(emit_stamp(arrivo, ref))
    assert substance(ritimbro) == substance(timbro), (
        f"{caso}: il giro non chiude\n"
        f"andata:  {json.dumps(substance(timbro), indent=1, sort_keys=True)}\n"
        f"ritorno: {json.dumps(substance(ritimbro), indent=1, sort_keys=True)}")


@pytest.mark.parametrize("caso", list(CASI))
def test_il_giro_riporta_anche_il_chi_e_il_quando(caso):
    costruisci, ref = CASI[caso]
    timbro = clean_stamp(emit_stamp(costruisci(), ref))
    arrivo = Graph(graph_id="graph:ricostruito")
    absorb_stamp(arrivo, timbro)
    ritimbro = clean_stamp(emit_stamp(arrivo, ref))
    assert ritimbro.get("by") == timbro.get("by")


def test_il_giro_chiude_anche_sul_dichiarato():
    """`declared` sopravvive al giro **senza diventare una regola viva**.

    Il grafo di partenza ha una licenza dichiarata con `has_license`; il grafo
    d'arrivo non la ha come statuto vivo — e non deve averla, perché `declared` è
    storia — ma il timbro che ne esce dice ancora che allora era quella.
    """
    from s3dgraphy.nodes.license_node import LicenseNode

    graph = _grafo_con_un_ingresso()
    graph.add_node(LicenseNode("lic:1", name="CC-BY-NC", license_type="CC-BY-NC"))
    graph.add_edge("e:lic", "res:mesh", "lic:1", "has_license")
    timbro = clean_stamp(emit_stamp(graph, "res:mesh"))
    assert timbro["declared"]["license"] == "CC-BY-NC"
    assert timbro["declared"]["as_of"] == "2026-09-15T20:14:07Z"

    arrivo = Graph(graph_id="graph:ricostruito")
    absorb_stamp(arrivo, timbro)
    # NON è diventata una licenza viva: nessun LicenseNode, nessun has_license
    assert not [n for n in arrivo.nodes if n.node_type == "license"]
    assert not [e for e in arrivo.edges if e.edge_type == "has_license"]
    # …ma il verbale la ricorda
    assert clean_stamp(emit_stamp(arrivo, "res:mesh"))["declared"] == \
        timbro["declared"]


def test_il_riassorbimento_non_introduce_tipi_di_nodo_nuovi():
    """Nessun tipo nuovo: solo `resource` e `dtc_process` (più `dtc_acquisition`
    quando un ingresso è una campagna). Se un giorno ne comparisse un quarto,
    vorrebbe dire che il formato chiede qualcosa che il substrato non ha."""
    ammessi = {"resource", "dtc_process", "dtc_acquisition"}
    for costruisci, ref in CASI.values():
        timbro = clean_stamp(emit_stamp(costruisci(), ref))
        fragment = stamp_to_graph(timbro)
        assert {n.node_type for n in fragment.nodes} <= ammessi


# ── T2 · riassorbire ─────────────────────────────────────────────────────────

def test_due_timbri_che_differiscono_SOLO_nellistante_si_deduplicano():
    graph = _grafo_con_un_ingresso()
    timbro = clean_stamp(emit_stamp(graph, "res:mesh"))
    di_nuovo = json.loads(json.dumps(timbro))
    di_nuovo["by"]["at"] = "2026-10-01T08:00:00Z"

    esito = absorb_stamp(graph, di_nuovo)
    assert esito.deduplicated is True
    assert esito.applied is False
    assert esito.in_disagreement is False
    assert any("the same fact recorded twice" in w for w in esito.warnings)
    # e il grafo tiene l'istante che aveva: non si sovrascrive un fatto con sé
    assert graph.find_node_by_id(
        timbro["how"]["process_id"]).data["created_at"] == "2026-09-15T20:14:07Z"


def test_due_timbri_con_GENITORI_DIVERSI_sono_una_scoperta_non_un_errore():
    """Il cuore di T2. Nessuna eccezione, nessun vincitore, il grafo intatto."""
    graph = _grafo_con_un_ingresso()
    mio = clean_stamp(emit_stamp(graph, "res:mesh"))
    prima = json.loads(json.dumps(
        {n.node_id: n.data for n in graph.nodes}, sort_keys=True))

    altrui = json.loads(json.dumps(mio))
    altrui["from"] = [{"resource_id": "res:altra", "digest": SHA_IN2,
                       "label": "un'altra nuvola"}]

    esito = absorb_stamp(graph, altrui)
    assert esito.in_disagreement is True
    assert esito.applied is False
    assert esito.deduplicated is False
    assert [d.path for d in esito.disagreements] == ["from"]
    # I DUE CONTENUTI IN MANO A CHI LEGGE, interi e non un diff da ricomporre
    assert esito.mine == mio
    assert esito.theirs == altrui
    # …e il grafo non è stato toccato: non si sceglie un vincitore
    dopo = json.loads(json.dumps(
        {n.node_id: n.data for n in graph.nodes}, sort_keys=True))
    assert dopo == prima
    assert graph.find_node_by_id("res:altra") is None


def test_due_timbri_con_PROCESSO_DIVERSO_sono_una_scoperta():
    """Serve che parlino TUTTI E DUE: è la regola del silenzio, misurata al rovescio.

    Un grafo che non dice con che tecnica ha fatto una cosa non contraddice
    nessuno — e infatti la prima versione di questo test falliva proprio lì, con
    il grafo muto e il timbro loquace, ed era il test a sbagliare premessa. Qui
    il grafo dichiara la sua tecnica, e allora due tecniche diverse per lo stesso
    digest sono due affermazioni che non possono essere entrambe vere.
    """
    graph = _grafo_con_un_ingresso()
    mio_id = clean_stamp(emit_stamp(graph, "res:mesh"))["how"]["process_id"]
    processo = graph.find_node_by_id(mio_id)
    processo.data["technique"] = "decimation"
    processo.data["parameters"] = {"target_faces": 50000}
    mio = clean_stamp(emit_stamp(graph, "res:mesh"))

    altrui = json.loads(json.dumps(mio))
    altrui["how"]["technique"] = "remeshing"
    altrui["how"]["parameters"] = {"voxel": 0.01}

    esito = absorb_stamp(graph, altrui)
    assert esito.in_disagreement is True
    assert esito.applied is False
    assert {d.path for d in esito.disagreements} == {"how.technique",
                                                     "how.parameters"}
    disaccordo = next(d for d in esito.disagreements if d.path == "how.technique")
    assert (disaccordo.mine, disaccordo.theirs) == ("decimation", "remeshing")


def test_una_tecnica_su_un_processo_muto_e_unaggiunta_non_un_conflitto():
    """L'altra metà della stessa regola, e il caso normale nella pratica."""
    graph = _grafo_con_un_ingresso()
    mio = clean_stamp(emit_stamp(graph, "res:mesh"))
    assert "technique" not in mio["how"]
    altrui = json.loads(json.dumps(mio))
    altrui["how"]["technique"] = "decimation"

    esito = absorb_stamp(graph, altrui)
    assert esito.applied is True
    assert esito.in_disagreement is False
    assert graph.find_node_by_id(mio["how"]["process_id"]).data["technique"] \
        == "decimation"


def test_il_software_in_due_versioni_e_un_disaccordo():
    """«Lo stesso algoritmo in due versioni non produce gli stessi byte»: due
    versioni per lo stesso digest sono due affermazioni non entrambe vere."""
    graph = _grafo_con_un_ingresso()
    processo = graph.find_node_by_id(
        clean_stamp(emit_stamp(graph, "res:mesh"))["how"]["process_id"])
    processo.data["software"] = [{"name": "EM Tools", "version": "1.6.0-dev.8"}]
    mio = clean_stamp(emit_stamp(graph, "res:mesh"))

    altrui = json.loads(json.dumps(mio))
    altrui["how"]["software"] = [{"name": "EM Tools", "version": "1.6.0-dev.9"}]
    esito = absorb_stamp(graph, altrui)
    assert [d.path for d in esito.disagreements] == ["how.software"]


def test_il_SILENZIO_non_e_un_disaccordo():
    """Un timbro ricco deve poter atterrare su un grafo povero — è il caso normale.

    Il grafo conosce la risorsa e non sa come è stata fatta; il timbro porta il
    passo. Non è una contraddizione: è un'aggiunta, e viene assorbita.
    """
    povero = Graph(graph_id="graph:povero")
    povero.add_node(ResourceNode("res:mesh", name="mesh", checksum=SHA_OUT))
    timbro = clean_stamp(emit_stamp(_grafo_con_un_ingresso(), "res:mesh"))

    esito = absorb_stamp(povero, timbro)
    assert esito.applied is True
    assert esito.in_disagreement is False
    assert povero.find_node_by_id("res:nuvola") is not None


def test_from_vuoto_parla_solo_se_un_how_lo_firma():
    """Il punto più sottile del formato, misurato nei due versi.

    Un artefatto che NESSUN processo ha prodotto emette `"from": []` perché non
    si sa come sia stato fatto; un passo vuoto emette `"from": []` per dire «nato
    qui». Sono due frasi diverse scritte uguali, e solo il `how` le distingue.
    """
    nudo = Graph(graph_id="graph:nudo")
    nudo.add_node(ResourceNode("res:mesh", name="mesh", checksum=SHA_OUT))
    muto = clean_stamp(emit_stamp(nudo, "res:mesh"))
    assert muto["from"] == [] and "how" not in muto

    con_genitori = clean_stamp(emit_stamp(_grafo_con_un_ingresso(), "res:mesh"))
    # il silenzio del grafo nudo non contraddice i genitori dell'altro
    assert compare_stamps(muto, con_genitori) == []

    # …ma due PASSI che dichiarano genitori diversi sì
    vuoto_firmato = clean_stamp(emit_stamp(_grafo_passo_vuoto(), "res:proxy"))
    vuoto_firmato["self"] = dict(con_genitori["self"])
    assert "from" in [d.path for d in compare_stamps(vuoto_firmato, con_genitori)]


def test_riassorbire_due_volte_lo_stesso_timbro_converge():
    arrivo = Graph(graph_id="graph:due-volte")
    timbro = clean_stamp(emit_stamp(_grafo_con_un_ingresso(), "res:mesh"))
    primo = absorb_stamp(arrivo, timbro)
    nodi = len(list(arrivo.nodes))
    secondo = absorb_stamp(arrivo, timbro)
    assert primo.applied and secondo.deduplicated
    assert len(list(arrivo.nodes)) == nodi


def test_dry_run_non_scrive():
    arrivo = Graph(graph_id="graph:prova")
    timbro = clean_stamp(emit_stamp(_grafo_con_un_ingresso(), "res:mesh"))
    esito = absorb_stamp(arrivo, timbro, dry_run=True)
    assert esito.applied is False
    # `== []` non si può scrivere: un `Graph` NASCE con il suo `geo_position`
    # (graph.py:64). Si contano i nodi che il timbro avrebbe portato.
    assert [n for n in arrivo.nodes if n.node_type != "geo_position"] == []


def test_un_em_json_non_e_un_timbro():
    """Le due specie non si confondono, e la frase lo dice."""
    with pytest.raises(BadStamp) as errore:
        validate_stamp({"graphs": {"g": {"nodes": [], "edges": []}}})
    assert "different species" in str(errore.value)


def test_un_timbro_di_una_versione_che_non_conosco_viene_rifiutato():
    with pytest.raises(BadStamp):
        validate_stamp({"stamp": 99, "self": {"resource_id": "res:x"}})


def test_un_timbro_senza_artefatto_viene_rifiutato():
    with pytest.raises(BadStamp):
        validate_stamp({"stamp": 1, "self": {}})


# ── T5 · verificabile contro confrontabile ───────────────────────────────────

@pytest.mark.parametrize("valore,atteso", [
    ("sha256:" + "6e" * 32, "verifiable"),
    ("emstruct1:abcdef", "comparable"),
    ("SHA256:" + "6e" * 32, "verifiable"),          # lo schema è insensibile
    ("6e" * 32, "unknown"),                          # nudo: nessun algoritmo detto
    ("md5:abc", "unknown"),
    ("", None),
    (None, None),
])
def test_la_forza_di_unidentita_si_chiede_a_una_funzione(valore, atteso):
    assert identity_strength(valore) == atteso


def test_un_master_blend_non_e_verificabile_e_lo_dichiara():
    """«Fino al bake ricorda, dal bake in poi dimostra».

    Un datablock dentro un .blend non ha byte canonici: la sua impronta basta ad
    accorgersi che è cambiata, non a verificare che è lei. Un'interfaccia che
    scrivesse «verificato» accanto a quella riga direbbe una bugia, e questa è la
    funzione che glielo impedisce.
    """
    graph = Graph(graph_id="graph:blend")
    graph.add_node(ResourceNode("res:master", name="mesh di lavoro",
                                url="blend://Scene/US01",
                                checksum="emstruct1:0f1e2d3c"))
    stamp = emit_stamp(graph, "res:master")
    from s3dgraphy.stamp import stamp_identity

    assert is_verifiable(stamp["self"]["digest"]) is False
    detto = stamp_identity(stamp)
    assert detto["strength"] == "comparable"
    assert detto["scheme"] == "emstruct1"
    assert "not that it is the same one" in detto["claim"]


def test_un_digest_nudo_non_viene_promosso_a_verificabile():
    """Somigliare a uno sha256 non è esserlo: `unknown` e non `verifiable`.

    È lo stesso ragionamento che `ResourceNode.TIERS` è nato per togliere di
    mezzo un piano più sotto («ha un checksum, quindi è quello pubblicato»).
    """
    graph = Graph(graph_id="graph:nudo")
    graph.add_node(ResourceNode("res:x", name="x", checksum="6e" * 32))
    stamp = emit_stamp(graph, "res:x")
    assert is_verifiable(stamp["self"]["digest"]) is False
    assert any("states no algorithm" in n for n in stamp["_notes"])


# ── T6 · quello che non doveva cambiare ──────────────────────────────────────

def test_le_tre_porte_sulla_superficie_api():
    """`emit_stamp` / `absorb_stamp` / `stamp_identity` si chiamano da `api`.

    Sono lì per la stessa ragione per cui ci sono `promote_resource` e
    `declare_derivation`: quella superficie è ciò che il bake di EMtools e
    StratiGraph Server guidano, e un'operazione raggiungibile solo importando un
    pacchetto è un'operazione che il prossimo strumento si riscrive.
    """
    from s3dgraphy import api

    graph = _grafo_con_un_ingresso()
    timbro = api.emit_stamp(graph, "res:mesh", revision=47, room="em.localhost/x")
    assert timbro["registry"]["revision"] == 47
    assert api.stamp_identity(timbro)["strength"] == "verifiable"

    arrivo = Graph(graph_id="graph:via-api")
    esito = api.absorb_stamp(arrivo, clean_stamp(timbro))
    # un dizionario e non una dataclass: la superficie parla in JSON
    assert isinstance(esito, dict) and esito["applied"] is True


def test_promote_resource_ha_ancora_la_sua_firma():
    """Il timbro **legge** ciò che quella scrive, non la sostituisce."""
    import inspect

    from s3dgraphy.publication import promote_resource as vera

    firma = inspect.signature(vera)
    assert list(firma.parameters)[:2] == ["graph", "resource_id"]
    for atteso in ("url", "sha256", "media_type", "author", "at", "source_id",
                   "source_ids", "link_to", "name", "residency", "tier",
                   "packaging", "size_bytes", "primitives", "corpus"):
        assert atteso in firma.parameters, f"manca {atteso}"


def test_un_genere_nuovo_resta_una_voce_JSON_e_non_una_modifica_di_codice():
    """`dtc_kinds` resta dato dai dati, anche per il riassorbimento.

    Provato mettendo un genere che oggi non esiste NEL VOCABOLARIO (non nel
    codice) e verificando che un timbro che lo dichiara atterri con quel genere.
    Senza la voce, lo stesso timbro cade sul genere di default invece di far
    sollevare il costruttore o — peggio — di allargare il vocabolario da solo a
    partire da un file arrivato da fuori.
    """
    from s3dgraphy.nodes.dtc_node import DTC_KINDS

    timbro = clean_stamp(emit_stamp(_grafo_con_un_ingresso(), "res:mesh"))
    timbro["how"]["dtc_kind"] = "fotogrammetria_aerea"

    senza_la_voce = stamp_to_graph(timbro)
    processo = senza_la_voce.find_node_by_id(timbro["how"]["process_id"])
    assert processo.data["dtc_kind"] == "transformation"

    DTC_KINDS["process"] = list(DTC_KINDS["process"]) + ["fotogrammetria_aerea"]
    try:
        con_la_voce = stamp_to_graph(timbro)
        processo = con_la_voce.find_node_by_id(timbro["how"]["process_id"])
        assert processo.data["dtc_kind"] == "fotogrammetria_aerea"
    finally:
        DTC_KINDS["process"] = [k for k in DTC_KINDS["process"]
                                if k != "fotogrammetria_aerea"]


def test_il_merge_per_UUID_e_QUELLO_e_non_un_secondo():
    """Il riassorbimento passa da `container.merge_graph_into`, che è
    `_merge_graph_into` con un nome pubblico: stesso corpo, stessa algebra CRDT.

    Un secondo algoritmo per «lo stesso nodo visto due volte» è la malattia che i
    tombstone sono costati per curare una volta sola.
    """
    from s3dgraphy.container import _merge_graph_into, merge_graph_into

    assert merge_graph_into.__module__ == _merge_graph_into.__module__
    arrivo = Graph(graph_id="graph:merge")
    arrivo.add_node(ResourceNode("res:mesh", name="il mio nome", checksum=SHA_OUT))
    timbro = clean_stamp(emit_stamp(_grafo_con_un_ingresso(), "res:mesh"))
    esito = absorb_stamp(arrivo, timbro)
    assert esito.applied and esito.merged_nodes >= 1


def test_il_frammento_non_porta_in_dote_una_posizione_geografica():
    """Ogni `Graph` nasce con un `geo_position` (graph.py:64). Un frammento di
    timbro non è un grafo di studio: senza toglierlo, riassorbire un timbro
    piegava dentro al grafo di chi lo riceve una posizione geografica VUOTA e
    ALTRUI, arrivata per posta con un verbale che non parlava di geografia."""
    timbro = clean_stamp(emit_stamp(_grafo_con_un_ingresso(), "res:mesh"))
    fragment = stamp_to_graph(timbro)
    assert not [n for n in fragment.nodes if n.node_type == "geo_position"]

    arrivo = Graph(graph_id="graph:mio")
    suoi = {n.node_id for n in arrivo.nodes if n.node_type == "geo_position"}
    absorb_stamp(arrivo, timbro)
    dopo = {n.node_id for n in arrivo.nodes if n.node_type == "geo_position"}
    assert dopo == suoi, "è arrivata una posizione geografica di qualcun altro"


# ── TIMBRO2 · chiudere la distanza fra il formato dichiarato e quello emesso ──

def test_S1_la_voce_from_porta_la_DIMENSIONE():
    """`size_bytes` sulla voce `from`: **l'indice del recupero**.

    Riconoscere un file costa poco perché il suo timbro dichiara la dimensione e
    il filtro scarta senza leggere un byte. Senza la stessa cifra qui, cercare un
    genitore smarrito costerebbe hashare tutto — e l'asimmetria rendeva la
    ricerca di un genitore la strada cara, cioè esattamente quella che serve
    quando qualcuno ha riordinato nel Finder.
    """
    graph = _grafo_con_un_ingresso()
    graph.find_node_by_id("res:nuvola").data["size_bytes"] = 84213760
    parent = clean_stamp(emit_stamp(graph, "res:mesh"))["from"][0]
    assert parent["size_bytes"] == 84213760
    assert set(parent) == {"resource_id", "digest", "size_bytes", "label"}


def test_S1_un_genitore_SENZA_dimensione_nota_non_e_un_errore():
    """Additivo vuol dire questo: il campo manca e il timbro è valido lo stesso.

    Tre modi di non avere una dimensione, e nessuno dei tre è un difetto: la
    risorsa non la dichiara (scritta prima che il campo esistesse), è una
    campagna che non ha byte da pesare, o qualcuno ha messo nel campo una cosa
    che una dimensione non è.
    """
    graph = _grafo_con_un_ingresso()
    assert "size_bytes" not in graph.find_node_by_id("res:nuvola").data
    parent = clean_stamp(emit_stamp(graph, "res:mesh"))["from"][0]
    assert "size_bytes" not in parent
    assert parent["digest"] == SHA_IN, "…e il resto della voce è intatto"

    # un booleano NON è una dimensione: `True` passerebbe per 1 in Python, e
    # «1 byte» in un timbro perché qualcuno ha scritto un flag nel campo
    # sbagliato è peggio del campo assente
    for storto in (True, -5, "84213760", None, 3.5):
        graph.find_node_by_id("res:nuvola").data["size_bytes"] = storto
        parent = clean_stamp(emit_stamp(graph, "res:mesh"))["from"][0]
        assert "size_bytes" not in parent, f"{storto!r} non è una dimensione"

    graph.find_node_by_id("res:nuvola").data["size_bytes"] = 0
    parent = clean_stamp(emit_stamp(graph, "res:mesh"))["from"][0]
    assert parent["size_bytes"] == 0, "zero È una misura, e va detta"


def test_S2_i_fatti_del_lotto_arrivano_in_how_acquisition():
    """Da un `bucket_acquisition` VERO, e una volta sola.

    L'apparecchio e le circostanze non sono `parameters` — quello vuol dire
    «come la tecnica è stata applicata» — ed è la distinzione che CRM3D fa fra
    `L12 happened on device` e `L13 used parameters`. Finché non avevano una
    casa ripiegavano su `parameters`, cioè si travestivano da parametro.
    """
    from s3dgraphy.dtc.ingest import bucket_acquisition

    graph = Graph(graph_id="graph:volo", name="Aiano")
    for i in range(3):
        graph.add_node(ResourceNode(f"res:s{i}", name=f"IMG_{i}.JPG",
                                    checksum="sha256:" + f"{i:02x}" * 32,
                                    size_bytes=180000 + i))
    bucket_acquisition(graph, [f"res:s{i}" for i in range(3)],
                       name="Volo 2026-03", dtc_kind="local_import",
                       metadata={"camera": "DJI Mavic 3E", "lens": "24mm",
                                 "folder": "volo_marzo"},
                       author=ORCID, at="2026-03-14T09:00:00Z")
    how = clean_stamp(emit_stamp(graph, "res:s0"))["how"]

    assert how["acquisition"] == {"camera": "DJI Mavic 3E", "lens": "24mm",
                                  "folder": "volo_marzo"}
    # UNA VOLTA SOLA: non anche in `parameters`
    assert "parameters" not in how
    # …e la conta dei membri NON è un fatto del rilievo: è una cache di un numero
    assert "member_count" not in how["acquisition"]
    # …né i timbri editoriali, né l'asse controllato
    for fuori in ("created_by", "created_at", "dtc_kind"):
        assert fuori not in how["acquisition"], fuori


def test_S2_il_blocco_e_APERTO_e_un_processo_normale_non_lo_porta():
    """Ciò che conta cambia col tipo di strumento: uno scanner non ha un
    obiettivo e un georadar ha una frequenza. Un elenco chiuso avrebbe scartato
    in silenzio il campo che serve al terzo strumento.

    E un passo che non è un'acquisizione non si inventa il blocco.
    """
    graph = Graph(graph_id="graph:gpr")
    graph.add_node(ResourceNode("res:out", name="out", checksum=SHA_OUT))
    graph.add_node(ResourceNode("res:in", name="in", checksum=SHA_IN))
    from s3dgraphy.dtc.ingest import bucket_acquisition
    bucket_acquisition(graph, ["res:out"], name="GPR 2026",
                       dtc_kind="local_import",
                       metadata={"frequenza_mhz": 400, "antenna": "shielded"},
                       at="2026-01-01T00:00:00Z")
    how = clean_stamp(emit_stamp(graph, "res:out"))["how"]
    assert how["acquisition"] == {"frequenza_mhz": 400, "antenna": "shielded"}

    # un passo derivato NON porta un blocco acquisition
    graph2 = _grafo_con_un_ingresso()
    assert "acquisition" not in clean_stamp(emit_stamp(graph2, "res:mesh"))["how"]


def test_S3_unetichetta_che_ripete_lidentificatore_e_omessa():
    """Vale per OGNI label del timbro, non solo per l'operatore."""
    from s3dgraphy.nodes.author_node import AuthorNode

    graph = Graph(graph_id="graph:uuid-che-nessuno-legge")
    # il GRAFO si chiama come il suo id
    graph.name = "graph:uuid-che-nessuno-legge"
    # l'INGRESSO si chiama come il suo id
    graph.add_node(ResourceNode("res:nuvola", name="res:nuvola", checksum=SHA_IN))
    promote_resource(graph, "res:mesh", url="s3://b/m.glb", sha256=SHA_OUT,
                     source_id="res:nuvola", name="mesh", at="2026-01-01T00:00:00Z")
    # l'AUTORE si chiama come il suo ORCID
    graph.add_node(AuthorNode("author:x", name=ORCID, orcid=ORCID))
    processo = [n for n in graph.nodes if n.node_type == "dtc_process"][0]
    graph.add_edge("e:a", processo.node_id, "author:x", "has_author")

    stamp = clean_stamp(emit_stamp(graph, "res:mesh"))
    assert "label" not in stamp["from"][0], "l'ingresso ridiceva il resource_id"
    assert "label" not in stamp["by"]["operator"], "l'operatore ridiceva l'ORCID"
    assert "label" not in stamp["registry"], "il grafo ridiceva il graph_id"
    # …e l'identificatore c'è comunque: si omette la cortesia, mai l'identità
    assert stamp["from"][0]["resource_id"] == "res:nuvola"
    assert stamp["by"]["operator"]["id"].endswith(ORCID)


def test_S3_IL_CONTROESEMPIO_un_nome_vero_sopravvive():
    """Una guardia che togliesse ogni label sarebbe indistinguibile da questa
    finché nessuno prova il caso opposto. Qui il nome c'è e deve restare."""
    from s3dgraphy.nodes.author_node import AuthorNode

    graph = _grafo_con_un_ingresso()
    graph.add_node(AuthorNode("author:x", name="Emanuel Demetrescu", orcid=ORCID))
    processo = [n for n in graph.nodes if n.node_type == "dtc_process"][0]
    graph.add_edge("e:a", processo.node_id, "author:x", "has_author")
    stamp = clean_stamp(emit_stamp(graph, "res:mesh"))
    assert stamp["by"]["operator"]["label"] == "Emanuel Demetrescu"
    assert stamp["from"][0]["label"] == "GT16 · rilievo 2015, nuvola"
    assert stamp["registry"]["label"] == "Great Temple"


def test_S3_anche_le_vesti_diverse_dello_stesso_id_sono_una_ripetizione():
    """`https://orcid.org/0000-…` e `author:0000-…` sono due vestiti della stessa
    stringa: un confronto per uguaglianza secca li avrebbe lasciati passare
    tutti e due, ed è così che l'etichetta arrivò a dire `author:0000-…`."""
    from s3dgraphy.nodes.author_node import AuthorNode

    graph = _grafo_con_un_ingresso()
    graph.add_node(AuthorNode("author:x", name=f"author:{ORCID}", orcid=ORCID))
    processo = [n for n in graph.nodes if n.node_type == "dtc_process"][0]
    graph.add_edge("e:a", processo.node_id, "author:x", "has_author")
    assert "label" not in clean_stamp(emit_stamp(graph, "res:mesh"))["by"]["operator"]


def test_S4_declare_derivation_inoltra_cio_che_il_passo_dichiara():
    """La cucitura chiusa: nessun chiamante deve più scrivere sul nodo a mano."""
    from s3dgraphy import api

    graph = Graph(graph_id="graph:cucitura")
    graph.add_node(ResourceNode("res:in", name="in", checksum=SHA_IN))
    graph.add_node(ResourceNode("res:out", name="out", checksum=SHA_OUT))
    api.declare_derivation(
        graph, "res:out", ["res:in"], process_id="proc:1",
        dtc_kind="photogrammetry", technique="decimation",
        parameters={"target_faces": 50000},
        software=[{"name": "EM Tools", "version": "1.6.0-dev.8",
                   "commit": "9555447"}],
        at="2026-01-01T00:00:00Z")
    how = clean_stamp(emit_stamp(graph, "res:out"))["how"]
    assert how["dtc_kind"] == "photogrammetry"
    assert how["technique"] == "decimation"
    assert how["parameters"] == {"target_faces": 50000}
    assert how["software"][0]["commit"] == "9555447"
    # …e `tool` resta compilata, perché le schede che esistono la leggono
    assert graph.find_node_by_id("proc:1").data["tool"]["name"] == "EM Tools"


def test_S4_un_tool_passato_a_mano_NON_viene_soppiantato_dal_software():
    """Una scelta di chi chiama non si sovrascrive con un derivato."""
    from s3dgraphy import api

    graph = Graph(graph_id="graph:tool")
    graph.add_node(ResourceNode("res:in", name="in", checksum=SHA_IN))
    graph.add_node(ResourceNode("res:out", name="out", checksum=SHA_OUT))
    api.declare_derivation(graph, "res:out", ["res:in"], process_id="proc:1",
                           tool="MeshLab",
                           software=[{"name": "EM Tools", "version": "1.6"}],
                           at="2026-01-01T00:00:00Z")
    assert graph.find_node_by_id("proc:1").data["tool"]["name"] == "MeshLab"


def test_S4_un_dtc_kind_SCONOSCIUTO_non_entra_nel_vocabolario():
    """Chiudere una cucitura non deve allargare un recinto.

    Due comportamenti diversi e tutti e due voluti: chi **scrive** un evento con
    un genere che non esiste sbaglia e lo sente subito (il costruttore solleva);
    un **timbro arrivato da fuori** con un genere sconosciuto cade sul default,
    perché un file di qualcun altro non allarga il nostro vocabolario.
    """
    from s3dgraphy import api
    from s3dgraphy.nodes.dtc_node import DTC_KINDS
    from s3dgraphy.stamp import stamp_to_graph

    prima = list(DTC_KINDS["process"])
    graph = Graph(graph_id="graph:vocab")
    graph.add_node(ResourceNode("res:in", name="in", checksum=SHA_IN))
    graph.add_node(ResourceNode("res:out", name="out", checksum=SHA_OUT))
    with pytest.raises(ValueError):
        api.declare_derivation(graph, "res:out", ["res:in"],
                               dtc_kind="inventato_stanotte",
                               at="2026-01-01T00:00:00Z")
    assert list(DTC_KINDS["process"]) == prima, "il vocabolario non si è allargato"

    # …e dal lato del riassorbimento: cade sul default, non entra
    timbro = {"stamp": 1, "self": {"resource_id": "res:x", "digest": SHA_OUT},
              "from": [], "how": {"process_id": "p", "dtc_kind": "inventato_stanotte"}}
    frammento = stamp_to_graph(timbro)
    assert frammento.find_node_by_id("p").data["dtc_kind"] == "transformation"
    assert list(DTC_KINDS["process"]) == prima


def test_S6_un_em_json_a_grafo_singolo_non_legge_piu_zero_sezioni():
    """IL CANCELLO. Un embargo scritto nel grafo e serializzato usciva.

    `rights._sections` cercava `graphs` (plurale) mentre `build_emjson` scrive
    `graph` (singolare): su un em.json a grafo singolo trovava ZERO sezioni e
    rispondeva `None`. E `None` non è inerte — i due chiamanti che decidono se
    trattenere scrivono `if rights and rights.get("embargo_active")`, quindi su
    `None` **non trattengono**.
    """
    from s3dgraphy import api, rights as R
    from s3dgraphy.exporter.emjson_exporter import build_emjson
    from s3dgraphy.nodes.embargo_node import EmbargoNode

    graph = Graph(graph_id="graph:embargo")
    graph.add_node(ResourceNode("res:foto", name="foto.jpg", checksum=SHA_OUT))
    graph.add_node(EmbargoNode("emb:1", name="2099-12-31",
                               embargo_end="2099-12-31"))
    graph.add_edge("e", "res:foto", "emb:1", "has_embargo")
    documento = build_emjson(graph)
    assert "graph" in documento and "graphs" not in documento

    assert len(R._sections(documento)) == 1, "zero sezioni = nessun diritto visto"
    letto = api.asset_rights(documento, SHA_OUT)
    assert letto is not None, "«non so niente» su un embargo che c'è"
    assert letto["embargo_active"] is True
    # e la forma container continua a funzionare
    assert len(R._sections({"graphs": {"a": {"nodes": [], "edges": []}}})) == 1


def test_S6_IL_CONTROESEMPIO_il_cancello_si_apriva_davvero():
    """Il difetto riprodotto, con la riga di codice dei chiamanti.

    Non «il lettore rispondeva None», che è un dettaglio: **che cosa ne facevano
    i chiamanti**. `iiif.iiif_manifest` e `contract.consumer` scrivono tutti e
    due `if rights and rights.get("embargo_active")`. Con `None` quella
    condizione è falsa, e un'immagine sotto embargo entra nel manifesto.
    """
    def come_decidono(rights):
        # la riga vera dei due chiamanti, copiata
        return bool(rights and rights.get("embargo_active"))

    assert come_decidono({"embargo_active": True}) is True
    assert come_decidono(None) is False, (
        "è questo: su None NON si trattiene, quindi un lettore che non vede "
        "l'embargo è un cancello che si apre")


# ── EXTRACT1 · `declared.by`, l'attributore ─────────────────────────────────
#
# L'autore è chi HA FATTO il dato; l'attributore è chi LO DICE, adesso, e i due
# sono frequentemente persone diverse — una catalogatrice dichiara la licenza di
# una fotografia scattata nel 1978 da un collega in pensione. `rights.py` fa
# questa distinzione da sempre e la firma su ogni dichiarazione; fino a stanotte
# la firma si fermava al grafo, e un timbro che affermava «CC-BY-NC al 15
# settembre» non diceva da chi — cioè non era contestabile.

def _grafo_con_un_asset(digest):
    from s3dgraphy import api

    doc = {"header": {"format": "em.json", "version": "1.0"},
           "graph": {"graph_id": "g", "nodes": [
               {"id": "res:a", "node_type": "resource", "name": "x.jpg",
                "data": {"checksum": digest}}], "edges": []}}
    grafo, _ = api.load_emjson(doc)
    api.bucket_acquisition(grafo, ["res:a"], name="dep", dtc_kind="ingest",
                           at="2026-09-15T10:00:00Z")
    return grafo


def test_E1_declared_porta_chi_ha_dichiarato():
    from s3dgraphy import api

    digest = "sha256:" + "a" * 64
    grafo = _grafo_con_un_asset(digest)
    api.enrich_asset_dtc(grafo, digest, attributor="0000-0002-1825-0097",
                         license="CC-BY-4.0", at="2026-09-15T10:00:00Z")
    declared = api.emit_stamp(grafo, "res:a")["declared"]
    assert declared["license"] == "CC-BY-4.0"
    assert declared["by"] == {"id": "https://orcid.org/0000-0002-1825-0097"}
    # NESSUNA label: il nome non si sa, e l'id del nodo (`author:0000-…`) è
    # l'identificatore un'altra volta. Vale la regola delle etichette.
    assert "label" not in declared["by"]


def test_E1_la_label_compare_solo_quando_c_e_un_nome_vero():
    from s3dgraphy import api
    from s3dgraphy.nodes.author_node import AuthorNode

    digest = "sha256:" + "b" * 64
    grafo = _grafo_con_un_asset(digest)
    grafo.add_node(AuthorNode(node_id="author:0000-0002-1825-0097",
                              name="Dev Utente", orcid="0000-0002-1825-0097"))
    api.enrich_asset_dtc(grafo, digest, attributor="0000-0002-1825-0097",
                         license="CC-BY-4.0", at="2026-09-15T10:00:00Z")
    declared = api.emit_stamp(grafo, "res:a")["declared"]
    assert declared["by"]["label"] == "Dev Utente"


def test_E1_IL_CONTROESEMPIO_con_DUE_firmatari_non_se_ne_sceglie_uno():
    """Licenza ed embargo firmati da due persone: `by` **non si scrive**.

    È il controesempio che deve far fallire l'asserzione comoda («c'è sempre un
    attributore»): scrivere uno dei due nomi accanto a un `declared` che tiene
    insieme le due affermazioni direbbe una cosa falsa su metà di esse. E il
    grafo, che le firme le ha tutte e due, resta il posto dove guardare.
    """
    from s3dgraphy import api
    from s3dgraphy.rights import rights_for_digest

    digest = "sha256:" + "c" * 64
    grafo = _grafo_con_un_asset(digest)
    api.enrich_asset_dtc(grafo, digest, attributor="0000-0002-1825-0097",
                         license="CC-BY-4.0", at="2026-09-15T10:00:00Z")
    api.enrich_asset_dtc(grafo, digest, attributor="0000-0002-5065-7970",
                         embargo="2099-12-31", at="2026-09-15T11:00:00Z")
    declared = api.emit_stamp(grafo, "res:a")["declared"]
    assert declared["license"] == "CC-BY-4.0"
    assert declared["embargo_until"] == "2099-12-31"
    assert "by" not in declared, "con due firmatari non si sceglie"

    firme = rights_for_digest(grafo, digest)["attributed_by"]
    assert sorted(f["orcid"] for f in firme) == ["0000-0002-1825-0097",
                                                 "0000-0002-5065-7970"]


def test_E1_l_attributore_sopravvive_al_giro_completo():
    """Riassorbito e riemesso, `declared.by` è ancora lì.

    Senza questo il campo sarebbe utile una volta sola: il timbro che arriva da
    fuori porta la firma, la si assorbe, e il timbro che si riemette da quel
    grafo l'avrebbe persa — cioè la contestabilità si consumerebbe al primo
    passaggio di mano.
    """
    from s3dgraphy import api

    digest = "sha256:" + "d" * 64
    grafo = _grafo_con_un_asset(digest)
    api.enrich_asset_dtc(grafo, digest, attributor="0000-0002-1825-0097",
                         license="CC-BY-4.0", at="2026-09-15T10:00:00Z")
    timbro = {k: v for k, v in api.emit_stamp(grafo, "res:a").items()
              if not k.startswith("_")}

    altro, _ = api.load_emjson({"header": {"format": "em.json", "version": "1.0"},
                                "graph": {"graph_id": "h", "nodes": [],
                                          "edges": []}})
    api.absorb_stamp(altro, timbro)
    assert api.emit_stamp(altro, "res:a")["declared"]["by"] == {
        "id": "https://orcid.org/0000-0002-1825-0097"}


def test_E1_un_asset_senza_dichiarazioni_non_inventa_un_firmatario():
    from s3dgraphy import api

    digest = "sha256:" + "e" * 64
    grafo = _grafo_con_un_asset(digest)
    timbro = api.emit_stamp(grafo, "res:a")
    # nessun `declared`, quindi a maggior ragione nessun `by`: un attributore
    # senza una dichiarazione da firmare non è una firma, è un nome messo lì
    assert "by" not in (timbro.get("declared") or {})
