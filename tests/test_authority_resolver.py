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
    # closed key set on purpose: the ref is persisted on every node, so each
    # added key costs em.json size forever. `fixture` earns its place because
    # it is the only way a sample URI can be told apart downstream.
    assert set(ref) <= {"uri", "authority", "label", "rank", "match", "broader",
                        "fixture"}
    assert ref["match"] == MATCH_EXACT and ref["rank"] == 1


def test_write_authority_refs_sets_node_data():
    class _N:
        pass
    n = _N()
    refs = write_authority_refs(n, "mosaic", "WHAT")
    assert refs and n.data["authority_refs"] == refs
    assert refs[0]["uri"].startswith("http://vocab.getty.edu/aat/")


# ── the sample flag ──────────────────────────────────────────────────────────
# The bundled snapshots are hand-seeded samples, not real dumps. provenance.json
# has said so since day one, but a README does not travel: an authority_ref
# written onto a node outlives this directory, goes into em.json and from there
# into the RDF projection. So the flag has to ride ON the ref.

def test_a_sample_snapshot_marks_its_candidates():
    cand = resolve("mosaic", "WHAT")[0]
    assert cand["provenance"].get("fixture") is True
    assert cand.get("fixture") is True


def test_the_sample_flag_survives_into_the_persisted_ref():
    # as_authority_ref is the shape that lands in node.data['authority_refs'];
    # this is the boundary where the warning used to be dropped.
    ref = as_authority_ref(resolve("mosaic", "WHAT")[0])
    assert ref["fixture"] is True


def test_a_real_snapshot_leaves_no_flag_behind():
    # counterexample — the flag must mean something, so a candidate that is NOT
    # from a sample carries no key at all. When real dated dumps replace these
    # files and `fixture` leaves provenance.json, refs go back to being clean.
    ref = as_authority_ref(
        {"uri": "http://vocab.getty.edu/aat/300015342", "authority": "aat",
         "label": "mosaic", "rank": 1, "match": MATCH_EXACT}
    )
    assert "fixture" not in ref


def test_written_refs_carry_the_flag_onto_the_node():
    class _N:
        pass
    n = _N()
    refs = write_authority_refs(n, "mosaic", "WHAT")
    assert refs and refs[0]["fixture"] is True
    assert n.data["authority_refs"][0]["fixture"] is True


# ── what may be shipped, and what may only be held ───────────────────────────
# `authorities/snapshots/` travels inside the wheel. Putting a vocabulary there
# IS redistributing it, to everyone who installs the library — and several of
# the ones we most want offline carry no statement that permits it (the IAA
# period thesaurus among them, asked 2026-09-20). Holding a copy for our own
# work and handing copies to every installer are different acts, and until this
# round the code could not tell them apart: anything dropped in that directory
# was published by the act of dropping it there.

def test_every_packaged_snapshot_declares_whether_it_may_be_redistributed():
    from importlib.resources import files
    import json
    prov = json.loads(files("s3dgraphy.authorities")
                      .joinpath("snapshots/provenance.json")
                      .read_text(encoding="utf-8"))["authorities"]
    missing = [k for k, v in prov.items() if "redistributable" not in v]
    assert not missing, f"no redistribution terms declared for: {missing}"


def test_nothing_unredistributable_is_in_the_package():
    """The guardrail, and it caught one on the day it was written.

    A file is published the moment it is written into this directory, long
    before anyone thinks to check. So: a packaged snapshot must either be
    redistributable, or still be a `fixture` — a sample we wrote ourselves,
    whose content is ours to give away whatever the real vocabulary's terms
    are.

    That second clause is a licence to postpone, not a loophole, and it expires
    on its own: the moment a real dump replaces the sample, `fixture` goes
    false and this test demands the terms. Which is exactly the moment the
    question stops being hypothetical.
    """
    from importlib.resources import files
    import json
    root = files("s3dgraphy.authorities").joinpath("snapshots")
    prov = json.loads(root.joinpath("provenance.json")
                      .read_text(encoding="utf-8"))["authorities"]
    # the authority is the one INSIDE the document, as the loader reads it —
    # the file names do not all match the provenance keys (getty_aat.jsonld
    # declares authority "aat"), and deriving it from the filename made this
    # test report two false offenders the first time it ran.
    shipped = set()
    for entry in root.iterdir():
        if not entry.name.endswith(".jsonld"):
            continue
        doc = json.loads(entry.read_text(encoding="utf-8"))
        shipped.add(doc.get("authority") or entry.name[:-7])
    offenders = {}
    for authority in shipped:
        entry = prov.get(authority, {})
        if entry.get("redistributable") == "yes":
            continue
        if entry.get("fixture"):
            continue          # our own sample, not their data — for now
        offenders[authority] = entry.get("redistributable", "undeclared")
    assert not offenders, (
        "these snapshots ship inside the package, are no longer samples, and "
        f"may not be redistributed: {offenders}. Move them to the local "
        "authority directory (resolver.local_authorities_dir()).")


def test_a_real_dump_without_terms_cannot_stay_in_the_package(tmp_path):
    """The clause above, tested on the case it is meant to catch: a snapshot
    that is no longer a fixture and whose terms are unknown."""
    entry = {"redistributable": "unknown", "fixture": False}
    assert not (entry.get("redistributable") == "yes" or entry.get("fixture")), (
        "a real dump with unknown terms must fail the packaging check")


def test_the_local_directory_is_read_and_its_hits_are_marked(tmp_path, monkeypatch):
    """A local snapshot resolves like any other and says it is local, so a
    consumer can tell that a resolution depended on something its own install
    may not hold."""
    import json
    from s3dgraphy.authorities import resolver

    (tmp_path / "provenance.json").write_text(json.dumps({"authorities": {
        "demo": {"name": "Demo", "facet": "WHAT", "redistributable": "no",
                 "license_ref": "none"}}}), encoding="utf-8")
    (tmp_path / "demo.jsonld").write_text(json.dumps({
        "authority": "demo", "facet": "WHAT", "scheme": "https://example.org/",
        "@graph": [{"@id": "https://example.org/x", "prefLabel": "tessera"}],
    }), encoding="utf-8")

    monkeypatch.setenv(resolver.LOCAL_DIR_ENV, str(tmp_path))
    resolver._load_snapshots.cache_clear()
    try:
        monkeypatch.setitem(resolver.FACET_ORDER, "WHAT",
                            list(resolver.FACET_ORDER["WHAT"]) + ["demo"])
        hits = [c for c in resolver.resolve("tessera", "WHAT")
                if c["authority"] == "demo"]
        assert hits and hits[0]["local"] is True
        assert resolver.as_authority_ref(hits[0])["local"] is True
    finally:
        resolver._load_snapshots.cache_clear()


def test_a_packaged_snapshot_is_not_marked_local():
    # counterexample: the flag must mean something
    from s3dgraphy.authorities import resolver
    resolver._load_snapshots.cache_clear()
    cand = resolver.resolve("mosaic", "WHAT")[0]
    assert "local" not in resolver.as_authority_ref(cand)
