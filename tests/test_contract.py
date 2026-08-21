"""The adapter contract, and the connector specialisation on top of it.

What is defended here is the FOUNDATION of the connector architecture, and each
test is one sentence of the decision (2026-08-21, with E.D.):

* one contract, **two consumers** — the field assistant's tools and the study's
  connectors. The four refusals, the descriptor and the DTC-attributed delta live
  in `s3dgraphy.contract.core`, and each consumer is a thin specialisation. The
  first test in this file is the one that keeps that true: the chatbot's wording
  is reproduced from the core with no new logic;
* a connector **declares** — host, transports, versions, capabilities from a
  closed set — because a capability is what a UI draws an affordance from;
* a version mismatch is a **refusal with a reason**, using the same comparison
  that reports which checked-out consumer is behind;
* a write passes the **EM language** at the seam (`allowed_connections`), so a
  peer speaking a slightly different EM cannot fill a study with
  `generic_connection`;
* an ingest **proposes**: volatile in the graph, absent from the document, until
  somebody bakes it.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from s3dgraphy.contract import (                                    # noqa: E402
    CAPABILITIES, CAPABILITY_LAYERS, ConnectorDescriptor, ConnectorRegistry,
    Delta, Descriptor, Refusals, Registry, Result, Slot, Versions,
    apply_delta, bake, current_versions, document_view, guard_write, handshake,
    invoke, validate_delta)


# ── the core, shared by two consumers ───────────────────────────────────────

def test_the_four_refusals_are_the_core_s_and_they_are_four():
    registry = Registry()
    registry.register(Descriptor(name="create_su", intents=["nuova unità"],
                                 input_schema=[Slot("number")],
                                 handler=lambda slots, author: Result(
                                     ok=True, message="ok",
                                     delta=Delta(nodes=[{"id": "US1"}]))))
    registry.register(Descriptor(name="declared_only", intents=["dichiarato"]))

    # 1 · unknown op: an answer, not an exception — and it says what exists
    unknown = invoke(registry.route("fai il caffè"), {}, "0000-0001",
                     registry=registry)
    assert unknown.ok is False
    assert unknown.data["reason"] == "unknown-op"
    assert "create_su" in unknown.message

    # 2 · declared but not wired: a real state during an integration
    nowire = invoke(registry.route("dichiarato"), {}, "0000-0001")
    assert (nowire.ok, nowire.data["reason"]) == (False, "no-handler")

    # 3 · a missing slot is NAMED, never defaulted
    missing = invoke(registry.route("nuova unità"), {}, "0000-0001")
    assert missing.data == {"op": "create_su", "reason": "missing-slots",
                            "missing": ["number"]}

    # 4 · a write with no author is refused — the whole reason ORCID is here
    unattributed = invoke(registry.route("create_su"), {"number": "101"}, None)
    assert (unattributed.ok, unattributed.data["reason"]) == (False, "no-author")

    # …and with an author it runs, and the author is stamped ON THE WAY OUT
    fine = invoke(registry.route("create_su"), {"number": "101"}, "0000-0001")
    assert fine.ok and fine.delta.author == "0000-0001"


def test_a_handler_that_raises_does_not_take_the_host_down():
    def boom(slots, author):
        raise RuntimeError("the endpoint is down")
    registry = Registry()
    registry.register(Descriptor(name="fragile", handler=boom))
    out = invoke(registry.route("fragile"), {}, "0000-0001")
    assert out.ok is False and out.data["reason"] == "handler-failed"
    assert "the endpoint is down" in out.message


def test_the_same_core_speaks_the_chatbot_s_words():
    """The proof that this is ONE contract and not two.

    The field assistant answers an archaeologist out loud, in Italian; a connector
    writes a line in a status bar, in English. Only the WORDS differ — so the
    chatbot's specialisation is its `Refusals` and nothing else, and this test
    reproduces its four sentences from the shared core with no new logic. (The
    chatbot repository still carries its own copy of the contract today;
    re-pointing it is the declared next step, and this is what it will point at.)
    """
    italian = Refusals(
        unknown="Non so fare questa cosa.",
        known_prefix=" So fare: ",
        no_handler="Lo strumento «{name}» è dichiarato ma non ancora collegato "
                   "a un servizio.",
        missing="Mi manca {slots}.",
        no_author="Non posso scrivere senza sapere chi sei: serve "
                 "un'identità verificata.",
        failed="«{name}» non è riuscito: {error}")

    registry = Registry()
    registry.register(Descriptor(name="create_su", intents=["nuova unità"],
                                 input_schema=[Slot("number")],
                                 handler=lambda s, a: Result(True, "fatto")))

    assert invoke(None, {}, None, registry=registry,
                  refusals=italian).message == \
        "Non so fare questa cosa. So fare: create_su."
    assert invoke(registry.route("nuova unità"), {}, "0000-0001",
                  refusals=italian).message == "Mi manca number."
    assert invoke(registry.route("create_su"), {"number": "1"}, None,
                  refusals=italian).message.startswith("Non posso scrivere")


def test_a_registry_refuses_to_shadow_a_name():
    registry = Registry()
    registry.register(Descriptor(name="twice"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(Descriptor(name="twice"))


def test_route_does_not_guess():
    registry = Registry()
    registry.register(Descriptor(name="create_su", intents=["nuova unità"]))
    assert registry.route("nuova unit") is None, "no nearest match, ever"
    assert registry.route("") is None
    assert registry.route("CREATE_SU") is not None, "the name itself routes"


# ── the connector specialisation ────────────────────────────────────────────

def blender(**over) -> ConnectorDescriptor:
    """The reference connector, as EMtools declares itself."""
    base = dict(
        name="blender", intents=["blender", "emtools"],
        description="Blender · EMtools", service="app", host="app-side",
        transport=["direct", "lan", "cloud"],
        capabilities=["read-graph", "write-graph", "subscribe",
                      "link-selection", "attach-asset", "materialize-3D",
                      "publish-3D"],
        versions=current_versions(), provenance="derivation")
    base.update(over)
    return ConnectorDescriptor(**base)


def test_a_descriptor_declares_where_it_runs_and_what_it_speaks():
    d = blender()
    assert d.host == "app-side" and "cloud" in d.transport
    assert d.can("materialize-3D") and not d.can("ingest-batch")
    # grouped by layer, which is what a registry shows and a reader needs: a
    # document capability and an ephemeral one are not the same kind of promise
    assert d.layers["document"] == ["read-graph", "write-graph", "subscribe"]
    assert d.layers["interaction"] == ["link-selection"]
    assert set(d.layers) == {"document", "interaction", "asset"}
    # the wire form: one serialisation, so the TypeScript side reads a shape
    wire = d.as_dict()
    assert wire["capabilities"] and wire["versions"]["datamodel"]
    assert wire["provenance"] == "derivation"


def test_the_capability_set_is_closed_and_the_layers_cover_it():
    with pytest.raises(ValueError, match="unknown capability"):
        blender(capabilities=["read-graph", "teleport"])
    with pytest.raises(ValueError, match="host must be one of"):
        blender(host="somewhere")
    with pytest.raises(ValueError, match="at least one transport"):
        blender(transport=[])
    # every capability belongs to exactly one layer — a capability in no layer
    # would be invisible in the registry that groups them
    flat = [c for caps in CAPABILITY_LAYERS.values() for c in caps]
    assert sorted(flat) == sorted(CAPABILITIES) == sorted(set(flat))
    # …and the ephemeral ones are declared as such, in their own layer: a
    # selection is not a fact about a study
    assert set(CAPABILITY_LAYERS["interaction"]) == {"link-selection", "presence"}


def test_a_writing_descriptor_cannot_opt_out_of_the_author_refusal():
    with pytest.raises(ValueError, match="writes=False"):
        blender(writes=False)


def test_the_registry_answers_who_can_do_this():
    registry = ConnectorRegistry()
    registry.register(blender())
    registry.register(ConnectorDescriptor(
        name="tropy", host="app-side", transport=["direct"],
        capabilities=["ingest-batch"], versions=current_versions()))
    assert [d.name for d in registry.providers("ingest-batch")] == ["tropy"]
    assert [d.name for d in registry.providers("write-graph")] == ["blender"]
    assert registry.capabilities()["subscribe"] == ["blender"]
    # and it holds connectors only: a plain Descriptor has nothing to route on
    with pytest.raises(TypeError, match="ConnectorDescriptors"):
        registry.register(Descriptor(name="plain"))


# ── the handshake ───────────────────────────────────────────────────────────

def test_a_stale_datamodel_is_refused_with_the_reason():
    ours = current_versions()
    stale = blender(versions=Versions(emjson=ours.emjson, datamodel="1.6.2",
                                      connector_api="1.0.0"))
    out = handshake(stale, current=ours)
    assert out.ok is False
    assert out.data["reason"] == "version-behind" and out.data["field"] == "datamodel"
    # the sentence a person can act on — both versions, and what to do
    assert "1.6.2" in out.message and str(ours.datamodel) in out.message
    assert "update" in out.message.lower()


def test_a_newer_peer_is_refused_too_and_told_which_side_to_update():
    ours = Versions(emjson="2", datamodel="1.6.11", connector_api="1.0.0")
    newer = blender(versions=Versions(emjson="2", datamodel="1.7.0",
                                      connector_api="1.0.0"))
    out = handshake(newer, current=ours)
    assert out.data["reason"] == "version-ahead"
    assert "update the study side" in out.message


def test_a_peer_that_will_not_say_is_refused():
    ours = current_versions()
    silent = blender(versions=Versions(emjson=ours.emjson, datamodel=None))
    out = handshake(silent, current=ours)
    assert out.data["reason"] == "version-undeclared"


def test_a_patch_difference_in_the_document_format_is_not_a_flag_day():
    """The tolerant half of the rule: the datamodel is strict because it IS the
    EM language, but refusing on every em.json patch would make each release a
    flag day for every partner. A MAJOR difference still refuses."""
    ours = Versions(emjson="2.3.1", datamodel="1.6.11", connector_api="1.0.0")
    minor = blender(versions=Versions(emjson="2.1.0", datamodel="1.6.11",
                                      connector_api="1.0.0"))
    assert handshake(minor, current=ours).ok is True
    major = blender(versions=Versions(emjson="1.9.0", datamodel="1.6.11",
                                      connector_api="1.0.0"))
    assert handshake(major, current=ours).ok is False


def test_the_handshake_compares_the_way_consumer_drift_does():
    """One comparison, not two: a connector arriving at run time is a consumer
    arriving late, and two implementations would eventually disagree."""
    from s3dgraphy.tools import consumer_drift
    assert consumer_drift.version_key("1.6.2") < consumer_drift.version_key("1.6.11")
    assert consumer_drift._key is consumer_drift.version_key, \
        "the private name still works for the report that used it first"


# ── the write seam ──────────────────────────────────────────────────────────

def test_a_capability_that_was_not_declared_is_refused():
    reader = blender(name="viewer", capabilities=["read-graph"])
    out = guard_write(reader, "write-graph",
                      Delta(nodes=[{"id": "US1"}], author="0000-0001"))
    assert out.data["reason"] == "capability-not-declared"
    assert "did not declare" in out.message


def test_nothing_enters_a_study_unattributed():
    out = guard_write(blender(), "write-graph", Delta(nodes=[{"id": "US1"}]))
    assert out.data["reason"] == "no-author"


def test_an_edge_the_em_language_forbids_is_refused_at_the_seam():
    """`allowed_connections` is read through the CORRECT resolver, so a
    connector's edge is held to the rule a report holds an import to."""
    # measured against the datamodel: `document → EpochNode` IS allowed (a
    # document is paradata), `resource → EpochNode` is not — a file does not
    # have a first epoch, an interpretation does
    bad = Delta(author="0000-0001",
                nodes=[{"id": "res-1", "node_type": "resource"},
                       {"id": "ep-1", "node_type": "EpochNode"}],
                edges=[{"id": "e1", "source": "res-1", "target": "ep-1",
                        "edge_type": "has_first_epoch"}])
    refused = validate_delta(bad)
    assert refused and refused[0]["edge_type"] == "has_first_epoch"
    out = guard_write(blender(), "write-graph", bad)
    assert out.ok is False and out.data["reason"] == "connection-not-allowed"
    assert "does not allow" in out.message

    # …and a legal one passes
    good = Delta(author="0000-0001",
                 nodes=[{"id": "us-1", "node_type": "US"},
                        {"id": "ep-1", "node_type": "EpochNode"}],
                 edges=[{"id": "e1", "source": "us-1", "target": "ep-1",
                         "edge_type": "has_first_epoch"}])
    assert validate_delta(good) == []
    assert guard_write(blender(), "write-graph", good).ok is True


def test_an_endpoint_this_function_cannot_see_is_not_refused():
    """An edge into a node that already lives in the graph: the type is unknown
    HERE, and refusing it would block a legitimate write on the strength of
    something this function cannot check."""
    delta = Delta(author="0000-0001",
                  edges=[{"id": "e1", "source": "already-there",
                          "target": "ep-1", "edge_type": "has_first_epoch"}])
    assert validate_delta(delta) == []
    assert validate_delta(delta, node_types={"already-there": "resource",
                                             "ep-1": "EpochNode"}), \
        "…but with the types supplied, the same edge is refused"


def test_a_refused_write_leaves_the_graph_untouched():
    section = {"nodes": [], "edges": []}
    # measured against the datamodel: `document → EpochNode` IS allowed (a
    # document is paradata), `resource → EpochNode` is not — a file does not
    # have a first epoch, an interpretation does
    bad = Delta(author="0000-0001",
                nodes=[{"id": "res-1", "node_type": "resource"},
                       {"id": "ep-1", "node_type": "EpochNode"}],
                edges=[{"id": "e1", "source": "res-1", "target": "ep-1",
                        "edge_type": "has_first_epoch"}])
    out = apply_delta(section, blender(), "write-graph", bad)
    assert out.ok is False
    assert section == {"nodes": [], "edges": []}, \
        "nothing applied: a validation must not half-write"


def test_a_write_lands_as_an_attributed_act():
    section = {"nodes": [], "edges": []}
    delta = Delta(author="0000-0002",
                  nodes=[{"id": "us-1", "node_type": "US", "name": "US 1"},
                         {"id": "ep-1", "node_type": "EpochNode", "name": "Phase"}],
                  edges=[{"id": "e1", "source": "us-1", "target": "ep-1",
                          "edge_type": "has_first_epoch"}])
    out = apply_delta(section, blender(), "write-graph", delta)
    assert out.ok and out.data["applied"] == {"nodes": 2, "edges": 1}
    # the author is on the record, not in a log: the CRDT stamps it
    stamped = [n for n in section["nodes"]
               if (n.get("data") or {}).get("created_by") == "0000-0002"]
    assert len(stamped) == 2, [n for n in section["nodes"]]
    # applying the same delta twice changes nothing (the CRDT's idempotence)
    again = apply_delta(section, blender(), "write-graph", delta)
    assert again.ok and len(section["nodes"]) == 2


# ── ingest: a proposal, not a fact ──────────────────────────────────────────

def tropy() -> ConnectorDescriptor:
    return ConnectorDescriptor(
        name="tropy", description="Tropy · photo archive", host="app-side",
        transport=["direct"], capabilities=["ingest-batch"],
        versions=current_versions(), provenance="acquisition")


def test_an_ingest_is_volatile_until_somebody_bakes_it():
    section = {"nodes": [], "edges": []}
    # what an `ingest-batch` proposes: an acquisition event and its files
    proposal = Delta(
        author="0000-0003", volatile=True,
        nodes=[{"id": "acq-1", "node_type": "dtc_acquisition",
                "name": "Tropy import 2026-08-21"},
               {"id": "res-1", "node_type": "resource", "name": "IMG_0001.jpg"}],
        edges=[{"id": "e1", "source": "acq-1", "target": "res-1",
                "edge_type": "dtc_had_output"}])
    out = apply_delta(section, tropy(), "ingest-batch", proposal)
    assert out.ok and out.data["volatile"] is True

    # it IS in the graph — a proposal you cannot see is not a proposal
    assert {n["id"] for n in section["nodes"]} == {"acq-1", "res-1"}
    # and it is NOT in the document a save would write
    saved = document_view(section)
    assert saved["nodes"] == [] and saved["edges"] == [], \
        "a folder that arrived is not yet a fact about the study"

    # a person accepts it…
    assert bake(section, "connector:tropy") == {"nodes": 2}
    kept = document_view(section)
    assert {n["id"] for n in kept["nodes"]} == {"acq-1", "res-1"}
    assert len(kept["edges"]) == 1
    # …and what landed is an acquisition attributed to them
    acq = next(n for n in kept["nodes"] if n["id"] == "acq-1")
    assert acq["node_type"] == "dtc_acquisition"
    assert (acq.get("data") or {}).get("created_by") == "0000-0003"


def test_baking_one_connector_does_not_bake_another_s_proposal():
    section = {"nodes": [], "edges": []}
    apply_delta(section, tropy(), "ingest-batch",
                Delta(author="0000-0003", volatile=True,
                      nodes=[{"id": "t-1", "node_type": "resource"}]))
    apply_delta(section, blender(), "write-graph",
                Delta(author="0000-0003", volatile=True,
                      nodes=[{"id": "b-1", "node_type": "resource"}]))
    assert bake(section, "connector:tropy") == {"nodes": 1}
    assert {n["id"] for n in document_view(section)["nodes"]} == {"t-1"}, \
        "two proposals in flight stay separable"


def test_a_write_graph_is_persistent_by_default():
    section = {"nodes": [], "edges": []}
    apply_delta(section, blender(), "write-graph",
                Delta(author="0000-0004",
                      nodes=[{"id": "us-9", "node_type": "US"}]))
    assert {n["id"] for n in document_view(section)["nodes"]} == {"us-9"}, \
        "recording an interpretation is not a proposal"
