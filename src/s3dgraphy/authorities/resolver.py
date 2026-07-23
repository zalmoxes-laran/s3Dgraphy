"""Offline-first authority resolver (P1-D).

Resolves a free-text term for a given facet (WHEN / WHAT / WHERE / WHO) against
OFFLINE JSON-LD snapshots bundled in ``authorities/snapshots/`` and returns a
RANKED list of candidates — **redundant by design**: every hit is attached, not
just the best one, ranked by an ordered consumption list per facet.

Design (decisions by E.D.):
  * Offline-first. Online enrichment is an optional hook, OFF by default
    (``online=True`` raises — not implemented in P1-D, no network here).
  * Strength-aware match: exact label hit → ``"exact"`` (→ skos:exactMatch on
    export); anything looser → ``"close"`` (→ skos:closeMatch, the default).
    The resolver NEVER emits an identity match — ``owl:sameAs`` is reserved for
    a human explicitly confirming identity (``match="sameAs"``), never for a
    ranked/uncertain candidate.
  * The registry is a DATA asset (JSON-LD snapshots), not code — like
    ``em_qualia_types.json``. em.json stays the single source of truth; the
    resolver just proposes ``authority_refs`` to write onto a node/qualia.

Public API:
  * :data:`FACET_ORDER` — the ordered consumption list per facet.
  * :func:`resolve` — ``(term, facet) -> [candidate dict]`` (rich, for the API).
  * :func:`as_authority_ref` — a candidate → the compact node/qualia ref shape.
  * :func:`write_authority_refs` — resolve + set ``node.data['authority_refs']``.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import Any, Dict, List, Optional

# ── facets & ordered consumption lists ───────────────────────────────────────
# Per facet, the authorities to consult IN ORDER. Only those with a bundled
# snapshot contribute offline; the rest are declared for ranking order and are
# hint-only until online enrichment / real dumps land (both out of P1-D scope).
FACET_ORDER: Dict[str, List[str]] = {
    "WHEN": ["chronontology", "periodo"],
    "WHAT": ["aat", "gnd", "wikidata"],
    "WHERE": ["tgn", "gnd", "wikidata"],
    "WHO": ["ulan", "gnd", "viaf", "wikidata"],
}

# match-strength vocabulary (the `match` field on an authority_ref)
MATCH_EXACT = "exact"
MATCH_CLOSE = "close"
MATCH_SAMEAS = "sameAs"  # identity — human-set only, never produced by resolve()

def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


@lru_cache(maxsize=1)
def _load_snapshots() -> Dict[str, Dict[str, Any]]:
    """Load every ``*.jsonld`` snapshot → {authority: {scheme, facet, concepts,
    provenance, license_ref}}. Cached (the snapshots are immutable data)."""
    root = files("s3dgraphy.authorities").joinpath("snapshots")
    provenance: Dict[str, Any] = {}
    try:
        provenance = json.loads(
            root.joinpath("provenance.json").read_text(encoding="utf-8")
        ).get("authorities", {})
    except FileNotFoundError:
        provenance = {}

    out: Dict[str, Dict[str, Any]] = {}
    for entry in root.iterdir():
        if not entry.name.endswith(".jsonld"):
            continue
        doc = json.loads(entry.read_text(encoding="utf-8"))
        authority = doc.get("authority") or entry.name[:-7]
        prov = provenance.get(authority, {})
        out[authority] = {
            "scheme": doc.get("scheme"),
            "facet": doc.get("facet"),
            "concepts": doc.get("@graph", []),
            "provenance": prov,
            "license_ref": prov.get("license_ref"),
        }
    return out


def _labels(concept: Dict[str, Any]) -> List[str]:
    """prefLabel + any altLabel(s), as a flat list of strings."""
    out: List[str] = []
    pref = concept.get("prefLabel")
    if pref:
        out.append(str(pref))
    alt = concept.get("altLabel")
    if isinstance(alt, list):
        out.extend(str(a) for a in alt)
    elif alt:
        out.append(str(alt))
    return out


def _match_strength(term_n: str, concept: Dict[str, Any]) -> Optional[str]:
    """MATCH_EXACT if the term equals any label (normalised), MATCH_CLOSE on a
    substring hit either direction, else None (no match)."""
    labels_n = [_norm(l) for l in _labels(concept)]
    if term_n in labels_n:
        return MATCH_EXACT
    for ln in labels_n:
        if ln and (term_n in ln or ln in term_n):
            return MATCH_CLOSE
    return None


def resolve(
    term: str,
    facet: str,
    *,
    online: bool = False,
) -> List[Dict[str, Any]]:
    """Resolve ``term`` for ``facet`` → RANKED candidate list (redundant by
    design: all hits attached). Offline-only unless ``online`` (not implemented
    in P1-D). Rank starts at 1, ordered by the facet's authority order, exact
    hits before close within each authority.

    Each candidate: ``{uri, authority, label, scheme, rank, match, provenance,
    license, broader?}``.
    """
    if online:
        raise NotImplementedError(
            "online authority enrichment is not implemented in P1-D "
            "(offline-first; enable a fetcher in a later phase)"
        )
    facet = (facet or "").upper()
    term_n = _norm(term)
    if not term_n or facet not in FACET_ORDER:
        return []

    snapshots = _load_snapshots()
    candidates: List[Dict[str, Any]] = []
    rank = 0
    for authority in FACET_ORDER[facet]:
        snap = snapshots.get(authority)
        if not snap:
            continue  # no offline snapshot for this authority (hint-only)
        # exact hits first, then close — stable within the authority
        for want in (MATCH_EXACT, MATCH_CLOSE):
            for concept in snap["concepts"]:
                if _match_strength(term_n, concept) != want:
                    continue
                rank += 1
                cand: Dict[str, Any] = {
                    "uri": concept.get("@id"),
                    "authority": authority,
                    "label": (concept.get("prefLabel") or term),
                    "scheme": snap.get("scheme"),
                    "rank": rank,
                    "match": want,
                    "provenance": snap.get("provenance", {}),
                    "license": snap.get("license_ref"),
                }
                broader = concept.get("broader")
                if broader:
                    cand["broader"] = broader
                candidates.append(cand)
    return candidates


def as_authority_ref(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """The compact ref shape persisted on a node/qualia (``authority_refs``):
    ``{uri, authority, label, rank, match}`` (+ ``broader`` when present)."""
    ref = {
        "uri": candidate.get("uri"),
        "authority": candidate.get("authority"),
        "label": candidate.get("label"),
        "rank": candidate.get("rank"),
        "match": candidate.get("match"),
    }
    if candidate.get("broader"):
        ref["broader"] = candidate["broader"]
    return ref


def write_authority_refs(node: Any, term: str, facet: str) -> List[Dict[str, Any]]:
    """Resolve ``term``/``facet`` and store the ranked compact refs on
    ``node.data['authority_refs']`` (em.json = single source of truth). Returns
    the refs written. Creates ``node.data`` if absent."""
    refs = [as_authority_ref(c) for c in resolve(term, facet)]
    data = getattr(node, "data", None)
    if not isinstance(data, dict):
        data = {}
        setattr(node, "data", data)
    data["authority_refs"] = refs
    return refs
