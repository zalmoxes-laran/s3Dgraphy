"""NIGHT-RIM2/B1 — il locator «dentro un .blend».

Il quinto `LOCATION_KIND`, la forma che regge, e le due risposte di residenza.
"""

import json

import pytest

from s3dgraphy.graph import Graph
from s3dgraphy.nodes.resource_node import ResourceNode
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit
from s3dgraphy.resources import classify_locator
from s3dgraphy.resources.resolver import (
    BLEND_SCHEME,
    LOCATION_KINDS,
    make_blend_locator,
    parse_blend_locator,
)


#: I nomi che hanno deciso la forma. Misurati in Blender 5.1: un datablock
#: accetta QUALUNQUE carattere — `bpy.data.objects.new("misto # e / insieme")`
#: torna quel nome identico. Un parser che dividesse sul primo `#` o
#: sull'ultimo `/` sbaglierebbe in silenzio, restituendo un datablock diverso
#: o inesistente.
NOMI_CATTIVI = [
    "normale",
    "con spazio",
    "con#cancelletto",
    "con/slash",
    "misto # e / insieme",
    "à углы 漢",
    "finisce con spazio ",
]


def test_il_quinto_kind_esiste_ed_e_riconosciuto():
    assert "blend_datablock" in LOCATION_KINDS
    loc = make_blend_locator("rilievo2015.blend", "Object", "tile10")
    assert loc.startswith(BLEND_SCHEME)
    assert classify_locator(loc) == "blend_datablock"


def test_gli_altri_quattro_kind_non_sono_cambiati():
    """Il quinto si aggiunge, non sposta gli altri: `blend://` è l'ULTIMO
    controllo prima del ripiego, e un percorso che contenga la parola blend
    resta un `local_path`."""
    assert classify_locator("models/casa.gltf") == "local_path"
    assert classify_locator("https://x/y.gltf") == "http_url"
    assert classify_locator("s3://bucket/key") == "s3_uri"
    assert classify_locator("file:///tmp/a.blend") == "file_uri"
    #: un percorso che PARLA di blend senza esserne il locator
    assert classify_locator("/dati/rilievo2015.blend") == "local_path"
    assert classify_locator("") == "local_path"


@pytest.mark.parametrize("nome", NOMI_CATTIVI)
def test_il_round_trip_regge_sui_nomi_che_hanno_deciso_la_forma(nome):
    """È la prova per cui la forma è percent-encoded e non ingenua."""
    loc = make_blend_locator("/dati/scavo 2015/rilievo.blend", "Object", nome)
    assert classify_locator(loc) == "blend_datablock"
    #: esattamente un `#`, e un solo `/` dopo di esso: è ciò che rende il
    #: parsing non ambiguo
    corpo = loc[len(BLEND_SCHEME):]
    assert corpo.count("#") == 1
    assert corpo.split("#", 1)[1].count("/") == 1

    percorso, tipo, tornato = parse_blend_locator(loc)
    assert tornato == nome
    assert tipo == "Object"
    assert percorso == "/dati/scavo 2015/rilievo.blend"


def test_parse_torna_None_e_non_solleva_su_qualunque_altra_cosa():
    """Chi chiama sta classificando, non validando: un'eccezione qui
    diventerebbe un pannello che smette di disegnarsi a metà."""
    for brutto in ("", "models/x.gltf", "https://x/y", "blend://senza-frammento",
                   "blend://a.blend#SenzaSlash", "blend://#Object/x",
                   "blend://a.blend#Object/", None):
        assert parse_blend_locator(brutto) is None


def test_effective_residency_di_una_risorsa_blend_e_resident():
    """I byte stanno in un file .blend che ho: sono miei, non un riferimento
    a roba di qualcun altro."""
    dentro = ResourceNode(node_id="r1", name="r1",
                          url=make_blend_locator("a.blend", "Object", "x"))
    assert dentro.effective_residency() == "resident"

    remota = ResourceNode(node_id="r2", name="r2", url="https://x/y.gltf")
    assert remota.effective_residency() == "reference"

    #: e una residenza REGISTRATA vince comunque sul ripiego
    dichiarata = ResourceNode(node_id="r3", name="r3",
                              url=make_blend_locator("a.blend", "Object", "x"))
    dichiarata.data["residency"] = "reference"
    assert dichiarata.effective_residency() == "reference"


def test_la_residenza_dello_shelf_dice_disk():
    """`_residence` risponde nelle tre parole che usa una persona — disk ·
    minio · uri — e un datablock dentro un .blend è su disco.

    Una QUARTA parola sarebbe una scelta di modello, e la voce C delle
    questioni aperte la lascia a E.D.: qui c'è il minimo che non la
    pregiudica.
    """
    from s3dgraphy.shelf.core import _residence

    assert _residence(make_blend_locator("a.blend", "Object", "x"), {}) == "disk"
    assert _residence("s3://b/k", {}) == "minio"
    assert _residence("https://x/y", {}) == "uri"
    assert _residence("/dati/a.jpg", {}) == "disk"


def test_un_grafo_con_una_risorsa_blend_fa_round_trip_isomorfo(tmp_path):
    """B5 · scritto e riletto, il locator torna identico — compresi i
    caratteri codificati, che sono il punto."""
    from s3dgraphy.exporter.emjson_exporter import export_emjson
    from s3dgraphy.importer.emjson_importer import import_emjson

    nome_cattivo = "misto # e / insieme"
    loc = make_blend_locator("/dati/scavo 2015/rilievo.blend", "Object",
                             nome_cattivo)

    g = Graph(graph_id="prova_blend")
    g.add_node(StratigraphicUnit("US101", "US101"))
    r = ResourceNode(node_id="US101_res", name="risorsa interna", url=loc,
                     url_type="3d_model")
    g.add_node(r)
    g.add_edge("e1", "US101", "US101_res", "has_linked_resource")

    percorso = export_emjson(g, str(tmp_path / "g.em.json"))
    riletto, warnings = import_emjson(percorso)
    assert not warnings

    risorse = [n for n in riletto.nodes if getattr(n, "node_type", "") == "resource"]
    assert len(risorse) == 1
    assert risorse[0].node_id == "US101_res"
    assert risorse[0].data.get("url") == loc
    assert parse_blend_locator(risorse[0].data["url"])[2] == nome_cattivo

    #: e riscrivendolo il LOCATOR è byte per byte lo stesso — che è ciò che
    #: questa prova deve garantire
    di_nuovo = export_emjson(riletto, str(tmp_path / "g2.em.json"))
    primo = json.load(open(percorso, encoding="utf-8"))
    secondo = json.load(open(di_nuovo, encoding="utf-8"))

    def risorsa(doc):
        nodi = doc["graphs"]["prova_blend"]["nodes"]
        return next(n for n in nodi if n["id"] == "US101_res")

    assert risorsa(primo)["data"]["url"] == risorsa(secondo)["data"]["url"] == loc

    #: …e tutto il resto del documento è identico TRANNE la `description`
    #: della risorsa. NON è un difetto di questo giro: `ResourceNode.__init__`
    #: ha `description="No description"` come DEFAULT e poi scrive
    #: `description or f"Link to {name}"`, cioè un valore-sentinella finisce
    #: su disco come se fosse un dato. Al secondo giro quel valore non
    #: sopravvive e il ripiego produce «Link to risorsa interna».
    #:
    #: Lo asserisco invece di ignorarlo: così è documentato, e il giorno che
    #: qualcuno sistema il default questa prova diventa rossa e lo dice.
    def grafo_senza_descrizioni(doc):
        """Nodi e archi, che è ciò che «isomorfo» significa per un grafo.

        Non il documento intero: l'intestazione porta un'IMPRONTA sha256 del
        contenuto, quindi cambia a valle di qualunque differenza — e
        confrontarla direbbe solo che qualcosa è cambiato, non cosa.
        """
        import copy
        g = copy.deepcopy(doc["graphs"]["prova_blend"])
        for n in g.get("nodes", []):
            n.get("data", {}).pop("description", None)
        return {"nodes": sorted(g.get("nodes", []), key=lambda n: n["id"]),
                "edges": sorted(g.get("edges", []), key=lambda e: e["id"])}

    assert (json.dumps(grafo_senza_descrizioni(primo), sort_keys=True)
            == json.dumps(grafo_senza_descrizioni(secondo), sort_keys=True))
    assert risorsa(primo)["data"]["description"] == "No description"
    assert risorsa(secondo)["data"]["description"] == "Link to risorsa interna"
