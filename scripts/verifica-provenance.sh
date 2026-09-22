#!/usr/bin/env bash
# verifica-provenance · la wheel appena pubblicata porta la sua attestazione
#
#   ./scripts/verifica-provenance.sh 1.6.0.dev19
#
# ── LA DOMANDA ───────────────────────────────────────────────────────────────
#
# Un publish riuscito senza provenance è un publish che ha fatto metà del
# lavoro e lo dichiara riuscito. Non è un'ipotesi: è lo stato in cui questa
# libreria si trova oggi. Misurato il 22 settembre 2026 —
#
#   s3dgraphy 1.6.0.dev18, caricata il 16 settembre
#   /integrity/…/provenance → 404 {"message":"No provenance available"}
#
# — e nessuno se n'era accorto perché nessuno l'aveva chiesto all'indice. Tre
# servizi installano questa wheel e finisce dentro le immagini che consegniamo
# a un partner: chi le specchia può risalire al Dockerfile, al commit, al tag,
# e poi arriva alla wheel e la catena si interrompe.
#
# ── COSA CONTROLLA, E COSA NO ────────────────────────────────────────────────
#
# Controlla che PyPI SERVA un'attestazione per ciascun file di quella versione,
# e che quell'attestazione nomini QUESTO repository. Non verifica la firma
# crittograficamente: quello lo fa PyPI quando la accetta, e rifarlo qui
# vorrebbe dire portarsi dietro sigstore per ridire una cosa già detta.
#
# ROSSO se: la versione non esiste, un file non ha provenance, o l'attestazione
# nomina un repository diverso da quello che ha lanciato il job.
set -euo pipefail

VERSIONE="${1:-}"
PACCHETTO="${PACCHETTO:-s3dgraphy}"
#: dentro Actions è il contesto; fuori è il remote. Nessun letterale: è la
#: lezione di `check-owner.mjs` in EMStudio, e vale qui per lo stesso motivo.
ATTESO="${GITHUB_REPOSITORY:-}"
if [ -z "$ATTESO" ]; then
  remote="$(git remote get-url origin 2>/dev/null || true)"
  ATTESO="$(printf '%s' "$remote" | sed -n 's#.*github\.com[/:]\([^/]*\)/\([^/]*\)#\1/\2#p' | sed 's/\.git$//')"
fi

if [ -z "$VERSIONE" ]; then
  echo "uso: $0 <versione>   (es. 1.6.0.dev19)" >&2
  exit 2
fi

echo "▶ provenance di $PACCHETTO $VERSIONE"
[ -n "$ATTESO" ] && echo "  repository atteso nell'attestazione: $ATTESO"

files="$(curl -fsS -m 30 "https://pypi.org/pypi/$PACCHETTO/$VERSIONE/json" \
         | python3 -c 'import sys,json; d=json.load(sys.stdin); print("\n".join(u["filename"] for u in d["urls"]))' \
         2>/dev/null || true)"

if [ -z "$files" ]; then
  echo "  ✗ $PACCHETTO $VERSIONE non risulta su PyPI (o l'indice non risponde)."
  exit 1
fi

rosse=0
assenti=0
altrove=0
n=0
for f in $files; do
  n=$((n + 1))
  url="https://pypi.org/integrity/$PACCHETTO/$VERSIONE/$f/provenance"
  corpo="$(curl -sS -m 30 -w '\n%{http_code}' "$url" || true)"
  stato="$(printf '%s' "$corpo" | tail -1)"
  json="$(printf '%s' "$corpo" | sed '$d')"

  if [ "$stato" != "200" ]; then
    echo "  ✗ $f — nessuna provenance (HTTP $stato)"
    rosse=$((rosse + 1)); assenti=$((assenti + 1))
    continue
  fi

  #: e non basta che risponda: l'attestazione deve nominare QUESTO repository.
  #: Una provenance che dice «nata altrove» è peggio di nessuna provenance,
  #: perché sembra una garanzia.
  dove="$(printf '%s' "$json" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print(""); raise SystemExit
visti = set()
def cerca(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("repository", "sourceRepositoryURI", "source_repository_uri") \
               and isinstance(v, str):
                visti.add(v.rstrip("/").split("github.com/")[-1])
            cerca(v)
    elif isinstance(o, list):
        for v in o:
            cerca(v)
cerca(d)
print(" ".join(sorted(visti)))
' 2>/dev/null || true)"

  if [ -n "$ATTESO" ] && [ -n "$dove" ] && ! printf '%s' " $dove " | grep -q " $ATTESO "; then
    echo "  ✗ $f — l'attestazione nomina «$dove», non «$ATTESO»"
    rosse=$((rosse + 1)); altrove=$((altrove + 1))
    continue
  fi
  echo "  ✓ $f — provenance presente${dove:+ ($dove)}"
done

echo
if [ "$rosse" -ne 0 ]; then
  echo "── $((n - rosse)) su $n con provenance · $rosse ROSSE ──"
  echo
  #: due guasti diversi meritano due consigli diversi. Una frase sola per
  #: entrambi manderebbe a configurare PyPI chi ha invece l'attestazione di un
  #: altro repository — che è un problema più grosso e di segno opposto.
  if [ "$assenti" -gt 0 ]; then
    echo "MANCA l'attestazione ($assenti file). Se il publish è appena riuscito,"
    echo "la causa quasi certa è che PyPI non conosce ancora questo Trusted"
    echo "Publisher, o che il publish è passato da un token: con un token"
    echo "l'indice accetta la wheel e non firma niente. I campi da mettere su"
    echo "PyPI sono nel README, «Pubblicare su PyPI»."
  fi
  if [ "$altrove" -gt 0 ]; then
    echo "L'attestazione c'è ma nomina un ALTRO repository ($altrove file), e"
    echo "questo è più grave della sua assenza: una provenance che dice «nata"
    echo "altrove» sembra una garanzia. O il Trusted Publisher su PyPI punta al"
    echo "repository sbagliato, o questa versione l'ha pubblicata qualcun altro."
  fi
  exit 1
fi
echo "── $n file su $n con provenance ──"
