"""P1-D — offline authority resolver: ranked, redundant, facet-ordered."""

import pytest

from s3dgraphy.authorities import (
    FACET_ORDER, MATCH_EXACT, MATCH_CLOSE, resolve, as_authority_ref,
    write_authority_refs,
)


def test_facet_order_contract():
    # ordered consumption lists exist for the four facets, Getty/period first
    assert FACET_ORDER["WHAT"][0] == "aat"
    assert FACET_ORDER["WHERE"][0] == "tgn"
    assert FACET_ORDER["WHO"][0] == "ulan"
    assert set(FACET_ORDER["WHEN"]) == {"chronontology", "periodo"}


def test_what_exact_hit_from_aat():
    cands = resolve("mosaic", "WHAT")
    assert cands, "expected an AAT hit for 'mosaic'"
    top = cands[0]
    assert top["authority"] == "aat"
    assert top["match"] == MATCH_EXACT
    assert top["uri"].startswith("http://vocab.getty.edu/aat/")
    assert top["rank"] == 1
    # provenance + license attached (redundant-by-design carries its terms)
    assert top["license"] == "getty"
    assert top["provenance"].get("name", "").startswith("Getty")


def test_when_is_ranked_and_redundant_across_authorities():
    # 'Roman' hits BOTH WHEN authorities → all attached, ranked, chronontology
    # (first in the consumption list) outranks periodo.
    cands = resolve("Roman", "WHEN")
    auths = [c["authority"] for c in cands]
    ranks = [c["rank"] for c in cands]
    assert "chronontology" in auths and "periodo" in auths
    assert ranks == sorted(ranks) and ranks[0] == 1  # contiguous, ranked
    assert auths.index("chronontology") < auths.index("periodo")
    # within an authority, an exact match precedes a close one
    ch = [c for c in cands if c["authority"] == "chronontology"]
    assert [c["match"] for c in ch][:2] == [MATCH_EXACT, MATCH_CLOSE]


def test_close_match_is_substring():
    # 'reticulatum' is a substring of the AAT prefLabel 'opus reticulatum'
    cands = resolve("reticulatum", "WHAT")
    assert cands and cands[0]["match"] == MATCH_CLOSE


def test_broader_is_surfaced_when_present():
    cands = resolve("brick", "WHAT")
    assert cands and cands[0]["match"] == MATCH_EXACT
    assert "broader" in cands[0]  # the AAT brick concept has a broader


def test_unknown_term_and_bad_facet_return_empty():
    assert resolve("no-such-thing", "WHAT") == []
    assert resolve("mosaic", "NOPE") == []
    assert resolve("", "WHAT") == []


def test_online_is_off_by_default_and_guarded():
    with pytest.raises(NotImplementedError):
        resolve("mosaic", "WHAT", online=True)


def test_as_authority_ref_is_compact():
    ref = as_authority_ref(resolve("mosaic", "WHAT")[0])
    assert set(ref) <= {"uri", "authority", "label", "rank", "match", "broader"}
    assert ref["match"] == MATCH_EXACT and ref["rank"] == 1


def test_write_authority_refs_sets_node_data():
    class _N:
        pass
    n = _N()
    refs = write_authority_refs(n, "mosaic", "WHAT")
    assert refs and n.data["authority_refs"] == refs
    assert refs[0]["uri"].startswith("http://vocab.getty.edu/aat/")
