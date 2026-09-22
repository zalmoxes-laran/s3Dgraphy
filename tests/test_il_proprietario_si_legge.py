"""Il proprietario del repository si LEGGE, non si scrive.

════════════════════════════════════════════════════════════════════════════════
## PERCHÉ

Il 22 settembre 2026 s3Dgraphy è passato in `github.com/ExtendedMatrix` — la
casa della comunità Extended Matrix, che è più longeva del progetto che la
consuma. GitHub lascia un redirect, quindi tutto continuava a funzionare, e per
questo nessuno se ne accorgeva: quarantasei righe con il vecchio proprietario
sono sopravvissute al trasloco, fra cui `[project.urls]` — cioè quello che PyPI
mostra sulla pagina del pacchetto — e i due valori con cui Sphinx costruisce
l'«edit on GitHub» di ogni pagina della documentazione.

Un redirect è una cortesia, non un contratto: smette il giorno in cui qualcuno
riusa il nome vecchio, e da quel giorno «Source Code» e «edit on GitHub»
portano al repository di un altro senza che niente diventi rosso.

E c'è una ragione in più, specifica di questa libreria: con il Trusted
Publisher l'attestazione di provenance NOMINA il repository. Una wheel che dice
«nata in ExtendedMatrix/s3Dgraphy» e una pagina PyPI che rimanda altrove sono
due affermazioni sullo stesso fatto, e una delle due ha torto.

## COSA NON È VIETATO — ed è una misura, non una concessione

`zalmoxes-laran` è anche il profilo di una PERSONA, e due repository che NON si
sono spostati. Misurato con `curl` il 22 settembre 2026:

    zalmoxes-laran/s3Dgraphy         301 → ExtendedMatrix/s3Dgraphy
    zalmoxes-laran/EMStudio          301 → ExtendedMatrix/EMStudio
    zalmoxes-laran/EMStudio-doc      301 → ExtendedMatrix/EMStudio-doc
    zalmoxes-laran/EM-blender-tools  200   ← non si è spostato
    zalmoxes-laran/ExtendedMatrix    200   ← nemmeno (è la SPECIFICA del
                                             linguaggio, non l'organizzazione)

Quindi il divieto è su `<vecchio>/<repo-traslocato>`, non sulla stringa nuda.
Vietarla tutta renderebbe rossa una firma d'autore corretta, e un recinto che
ha torto una volta viene disattivato per sempre.

## LA MUTAZIONE

Rimetti il vecchio proprietario davanti a uno dei repository traslocati —
in un README, in `pyproject.toml`, in un commento — → rosso.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

RADICE = pathlib.Path(__file__).resolve().parent.parent

#: il soggetto della ricerca, scritto spezzato perché il recinto gira anche su
#: SÉ STESSO: `git ls-files` include questo file, e una regola che deve
#: esentarsi da sé è una regola con un buco della propria forma.
VECCHIO = "-".join(("zalmoxes", "laran"))

#: misurati traslocati (vedi la docstring)
TRASLOCATI = ("s3Dgraphy", "s3dgraphy", "EMStudio-doc", "EMStudio")

#: misurati fermi: nominarli col vecchio proprietario è CORRETTO, e il giorno
#: in cui si spostano questa lista è dove si guarda
RIMASTI = ("EM-blender-tools", "ExtendedMatrix")


def _tracciati() -> list[str]:
    """I file COMMITTATI. Ciò che non è committato non viaggia, e `.venv/`,
    `build/` e `.claude/` non sono cose che pubblichiamo."""
    out = subprocess.run(["git", "ls-files", "-z"], cwd=RADICE,
                         capture_output=True, text=True, check=True).stdout
    return [f for f in out.split("\0") if f and not f.startswith(".claude/")]


def _proprietario() -> str:
    """Chi siamo: dal remote. Nessun letterale — è la regola stessa."""
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=RADICE,
                             capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError:  # pragma: no cover
        pytest.skip("nessun remote: non so quale repository sia questo")
    m = re.search(r"github\.com[/:]([^/]+)/", url)
    assert m, f"remote non riconosciuto: {url}"
    return m.group(1)


def test_i_file_committati_non_nominano_il_vecchio_proprietario():
    colpevoli = []
    letti = 0
    for f in _tracciati():
        p = RADICE / f
        try:
            testo = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue          # binario, o sparito
        letti += 1
        for i, riga in enumerate(testo.splitlines(), 1):
            for repo in TRASLOCATI:
                #: il confine a destra serve: senza, `EMStudio` prenderebbe
                #: anche `EMStudio-doc` e il messaggio nominerebbe il
                #: repository sbagliato
                if re.search(rf"{VECCHIO}/{repo}(?![A-Za-z0-9_-])", riga):
                    colpevoli.append(f"{f}:{i}  →  …/{repo}")

    assert letti > 50, (
        f"ho letto solo {letti} file di testo: la ricerca è troppo stretta e "
        f"passerebbe comunque")
    assert not colpevoli, (
        "questi nominano un repository col proprietario che non ce l'ha più:\n  "
        + "\n  ".join(colpevoli)
        + "\n\nGli unici usi legittimi del nome vecchio sono il PROFILO della "
          f"persona e i repository non traslocati {RIMASTI}.")


def test_il_recinto_ha_qualcosa_su_cui_mordere():
    """Un controllo che passa perché non ha trovato niente passerebbe anche il
    giorno in cui la cosa che sorveglia scompare."""
    proprietario = _proprietario()
    tutto = "\n".join(
        (RADICE / f).read_text(encoding="utf-8", errors="ignore")
        for f in _tracciati())
    assert f"{proprietario}/s3Dgraphy" in tutto, (
        f"nessuno nomina {proprietario}/s3Dgraphy: o i link sono spariti, o la "
        f"ricerca dell'altra prova sta guardando nel posto sbagliato")


def test_le_urls_che_PyPI_mostra_puntano_al_repository_giusto():
    """`[project.urls]` è la vetrina del pacchetto, ed è anche ciò che
    l'attestazione di provenance dovrà confermare: due affermazioni sullo
    stesso fatto non possono divergere."""
    proprietario = _proprietario()
    testo = (RADICE / "pyproject.toml").read_text(encoding="utf-8")
    blocco = testo.split("[project.urls]", 1)
    assert len(blocco) == 2, "pyproject.toml non ha un blocco [project.urls]"
    corpo = blocco[1].split("\n[", 1)[0]
    github = re.findall(r'https://github\.com/([^/"\s]+)/([^/"\s]+)', corpo)
    assert github, "nessuna url GitHub in [project.urls]"
    sbagliate = [f"{o}/{r}" for o, r in github if o != proprietario]
    assert not sbagliate, (
        f"[project.urls] rimanda a {sbagliate}, ma questo repository è di "
        f"{proprietario}. È ciò che PyPI mostra sulla pagina del pacchetto.")


def test_sphinx_costruisce_edit_on_github_col_proprietario_giusto():
    """`html_context` è ciò con cui Sphinx fa il link «edit on GitHub» di OGNI
    pagina: sbagliato, manda a modificare il repository di un altro."""
    proprietario = _proprietario()
    conf = (RADICE / "docs" / "conf.py").read_text(encoding="utf-8")
    utente = re.search(r"'github_user':\s*'([^']+)'", conf)
    assert utente, "docs/conf.py non dichiara github_user"
    assert utente.group(1) == proprietario, (
        f"docs/conf.py dice github_user = {utente.group(1)}, ma questo "
        f"repository è di {proprietario}")
