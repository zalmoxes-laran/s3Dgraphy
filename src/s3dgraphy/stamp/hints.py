"""Le piste: «ho visto questo digest in questo posto, in questo momento».

## Perché sono un file a parte, e non un campo del timbro

Per necessità, non per ordine. **Un record immutabile non può contenere un campo
mutevole**: riscrivere la pista ne cambierebbe il contenuto e quindi — se il
timbro fosse coperto da un digest — la sua identità. Quindi `<asset>.hints.json`
accanto a `<asset>.stamp.json`, e **mai coperto da nessun digest**.

Il guadagno è il contrario di quello che sembra: **una pista sbagliata è
innocua.** La si segue, si ricalcola il digest, e o è la cosa giusta o ci si
accorge subito. Un sistema che punta per nome consegna *in silenzio* il file
sbagliato, che è il modo peggiore di sbagliare che esista.

## `scope`, che è riservatezza e non pulizia

`public` può viaggiare — un URI di uno store è indirizzo, non confidenza.
`private` **non esce mai**, e la ragione non è l'ordine: un percorso assoluto
pubblicato è inutile agli altri e indiscreto verso chi lo ha scritto, perché
porta il nome utente, la struttura delle cartelle e a volte il nome di un
committente. `/Users/mrossi/lavori/Fondazione X/2015/nuvola.ply` dice quattro
cose che nessuno aveva intenzione di dire.

Quindi :func:`for_export` esiste, ed è l'unica porta verso l'esterno. Non è un
filtro di cortesia da ricordarsi di chiamare: chi scrive su disco qualcosa che
esce passa da :func:`write_public_hints`, che non ha un parametro per disattivarlo.

## L'aggiornamento è passivo

**Le piste non si cancellano, invecchiano.** Nessuna manutenzione, e soprattutto
**niente che chieda a una persona di sistemare un percorso**: un file spostato
non è un errore da correggere, è un fatto da riosservare. Due modi di osservare, e
sono tutti e due opportunistici:

* :func:`note_seen` — ogni volta che uno strumento tocca un file ne calcola il
  digest e annota «visto qui, adesso»;
* :func:`scan_directory` — su richiesta, una cartella intera.

Non c'è nessuna terza funzione che dica «questa pista è rotta, sistemala».
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from typing import Any, Dict, Iterable, List, Optional

from ..editorial import now_iso

#: La versione del formato delle piste. Separata da quella del timbro perché
#: sono due file con due vite: uno non cambia mai, l'altro cambia sempre.
HINTS_VERSION = 1

#: Chi può viaggiare e chi no. **Due valori e non tre**: «forse» non è una
#: risposta a una domanda di riservatezza.
SCOPES = ("public", "private")

#: Come si raggiunge quel posto. Vocabolario aperto — un `kind` che non è qui
#: viene registrato lo stesso, perché una pista è un'osservazione e non una
#: dichiarazione di conformità — ma questi sono i quattro che si scrivono da soli.
KNOWN_KINDS = ("s3", "http", "local", "blend")

#: Quali `kind` sono pubblici quando nessuno lo dice. Un URI di store è un
#: indirizzo; **tutto il resto è privato per difetto**, e il verso di questo
#: default è la decisione: sbagliare verso «privato» costa una pista che non
#: viaggia, sbagliare verso «pubblico» costa il nome utente di qualcuno.
_PUBLIC_BY_DEFAULT = ("s3", "http")


def new_hints(digest: str) -> Dict[str, Any]:
    """Un registro vuoto per questo digest."""
    return {"hints": HINTS_VERSION, "digest": str(digest), "seen": []}


def scope_for(locator: str, kind: Optional[str] = None) -> str:
    """`public` o `private` quando nessuno l'ha detto.

    Il verso del dubbio è verso `private`, sempre. Vedi `_PUBLIC_BY_DEFAULT`.
    """
    guessed = kind or kind_for(locator)
    return "public" if guessed in _PUBLIC_BY_DEFAULT else "private"


def kind_for(locator: str) -> str:
    """Come si raggiunge quel posto, letto dalla forma del locator."""
    text = str(locator or "")
    if text.startswith("s3://"):
        return "s3"
    if text.startswith(("http://", "https://")):
        return "http"
    if text.startswith("blend://"):
        return "blend"
    return "local"


def note_seen(hints: Dict[str, Any], locator: str, *,
              kind: Optional[str] = None,
              scope: Optional[str] = None,
              machine: Optional[str] = None,
              when: Optional[str] = None) -> Dict[str, Any]:
    """Annota «visto qui, adesso». **Aggiorna, non duplica, non cancella.**

    Lo stesso locator sulla stessa macchina è **la stessa pista riosservata**: si
    aggiorna il suo `when` e resta al suo posto nella lista. Aggiungere una riga
    per ogni sguardo farebbe crescere il file senza aggiungere un fatto.

    `when` si può passare — e serve, perché una funzione che chiede l'ora non si
    può provare due volte con lo stesso esito. Assente, è adesso: qui l'orologio
    ci sta, perché **osservare è un atto che avviene in un momento**, al contrario
    dell'emissione di un timbro che è una lettura.
    """
    if scope is not None and scope not in SCOPES:
        raise ValueError(f"scope must be one of {list(SCOPES)}, got {scope!r}")
    seen = hints.setdefault("seen", [])
    resolved_kind = kind or kind_for(locator)
    entry = {
        "locator": str(locator),
        "kind": resolved_kind,
        "scope": scope or scope_for(locator, resolved_kind),
        "when": when or now_iso(),
    }
    if machine:
        entry["machine"] = machine
    for existing in seen:
        if existing.get("locator") == entry["locator"] \
                and existing.get("machine") == entry.get("machine"):
            existing.update(entry)
            return existing
    seen.append(entry)
    return entry


def for_export(hints: Dict[str, Any]) -> Dict[str, Any]:
    """Le piste che possono viaggiare: **solo `public`**.

    L'unica porta verso l'esterno. Restituisce sempre un registro ben formato,
    anche quando resta vuoto: un file di piste senza piste è una risposta onesta
    («di questo digest non so nessun posto pubblico»), mentre nessun file
    lascerebbe credere che il registro non esista.
    """
    out = {"hints": HINTS_VERSION, "digest": hints.get("digest"), "seen": []}
    for entry in hints.get("seen") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("scope") != "public":
            continue
        # `machine` non esce nemmeno da una pista pubblica: il nome del computer
        # di una persona non è parte dell'indirizzo, e in un file che viaggia è
        # solo un'altra cosa che si sa di lei.
        out["seen"].append({k: v for k, v in entry.items() if k != "machine"})
    return out


def private_locators(hints: Dict[str, Any]) -> List[str]:
    """I locator che non devono uscire. Per poterlo **provare**, non per usarli."""
    return [str(e.get("locator") or "") for e in hints.get("seen") or []
            if isinstance(e, dict) and e.get("scope") != "public"]


def hints_filename(digest: str, *, asset: Optional[str] = None) -> str:
    """`<asset>.hints.json`, accanto al timbro e con lo stesso criterio di nome."""
    base = str(asset or digest or "hints")
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in base)
    return f"{safe}.hints.json"


def write_hints(hints: Dict[str, Any], path: str) -> str:
    """Scrive il registro **intero**, piste private comprese: è il file di casa."""
    return _write(hints, path)


def write_public_hints(hints: Dict[str, Any], path: str) -> str:
    """Scrive **solo** quello che può viaggiare.

    Nessun parametro per disattivare il filtro, e non è un'omissione: una porta
    che si può aprire a metà è una porta che un giorno qualcuno apre a metà.
    """
    return _write(for_export(hints), path)


def _write(payload: Dict[str, Any], path: str) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    return path


def read_hints(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# ── osservare ────────────────────────────────────────────────────────────────

def file_digest(path: str, *, chunk: int = 1024 * 1024) -> str:
    """`sha256:<hex>` dei byte di un file, letto a blocchi.

    A blocchi perché una nuvola di punti non entra in memoria, e un digest che
    funziona sui file piccoli e muore su quelli grandi è peggio che nessun
    digest: fallisce esattamente sui dati che valeva la pena identificare.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def scan_directory(root: str, *, machine: Optional[str] = None,
                   when: Optional[str] = None,
                   suffixes: Optional[Iterable[str]] = None,
                   into: Optional[Dict[str, Dict[str, Any]]] = None
                   ) -> Dict[str, Any]:
    """Scandisce una cartella e annota dove ha visto che cosa.

    Torna `{"found": {digest: hints}, "unreadable": [...]}` — **due chiavi e non
    un dizionario solo**, perché un file che non si è potuto leggere non ha un
    digest sotto cui stare, e infilarlo nella stessa mappa con una chiave finta
    metterebbe una parola in mezzo agli indirizzi di chi itera.

    `into` permette di continuare un registro che c'era già, perché una scansione
    **si aggiunge** alle osservazioni precedenti invece di sostituirle: un file
    che oggi non c'è più non smette di essere stato visto ieri altrove.

    Il `scope` non si passa: un percorso su disco è `local`, e `local` è
    `private`. Farlo scegliere a chi chiama vorrebbe dire che un giorno qualcuno
    passa `public` a una scansione del proprio portatile.

    Un file illeggibile non ferma la scansione ed è riportato come tale: **non è
    un difetto di programmazione, è un fatto sul disco** (un permesso, un link
    rotto, un volume smontato), e fermarsi al primo lascerebbe non osservato tutto
    il resto della cartella.
    """
    base = pathlib.Path(root)
    if not base.is_dir():
        raise NotADirectoryError(f"{root} is not a directory to scan")
    found: Dict[str, Dict[str, Any]] = into if into is not None else {}
    unreadable: List[str] = []
    wanted = tuple(s.lower() for s in suffixes) if suffixes else None
    host = machine if machine is not None else _this_machine()
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if wanted and path.suffix.lower() not in wanted:
            continue
        try:
            digest = file_digest(str(path))
        except OSError as exc:
            # OSError e non Exception: un permesso negato o un link rotto sono
            # questo; qualunque altra cosa è un difetto e deve arrivare a chi
            # legge, non finire in un elenco di avvisi.
            unreadable.append(f"{path}: {exc}")
            continue
        register = found.setdefault(digest, new_hints(digest))
        note_seen(register, str(path), kind="local", scope="private",
                  machine=host, when=when)
    return {"found": found, "unreadable": unreadable}


def _this_machine() -> Optional[str]:
    """Il nome di questa macchina, quando il sistema lo dice.

    Sta in una pista `private` e non esce mai (:func:`for_export` lo toglie anche
    da una pubblica): serve a distinguere «l'ho visto sul portatile» da «l'ho
    visto sul fisso», che è la sola ragione per cui due piste allo stesso
    percorso sono due piste.
    """
    uname = getattr(os, "uname", None)
    return uname().nodename if callable(uname) else None
