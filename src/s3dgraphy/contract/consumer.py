"""SERVING A CONSUMER — the contract's outgoing face.

Blender (reference #1) proved the connector that WRITES: it runs beside the
study, it materialises proxies and publishes models, and every write of its
passes :func:`~s3dgraphy.contract.connector.guard_write`. A **consumer** is the
other half of the same contract, and it is the half dissemination needs: a
Heriverse viewer, an ATON scene, a catalogue page. It reads a published study and
shows it. It writes nothing.

    a writing connector is GUARDED; a consumer is SERVED.

Those are two directions, not two contracts. The descriptor is the same, the
handshake is the same, the capability set is the same closed set, and the
refusals are worded once — this module reuses
:data:`~s3dgraphy.contract.connector.SEAM`'s *not declared* sentence rather than
writing a second one, because a consumer told "you did not declare that" in
different words from a writer would be a second contract wearing the first one's
name.

What the outgoing direction adds is the two questions a *serving* act has to
answer, and neither of them arises when somebody writes into their own study:

* **is this caller allowed to read it at all?** A study is `public` (published:
  anybody, with no token) or `restricted` (login *and* a grant). The rule is
  StratiGraph Server's `access.effective_visibility`, applied here so a library caller and
  the room's door cannot drift apart;
* **may these particular bytes go out?** An asset's licence and embargo are
  stated in the graph — :mod:`s3dgraphy.rights` — and an embargo is a refusal
  **with the date**, to a consumer exactly as to a browser. While it runs, the
  file is for the people working on the study (editor and above); the sentence is
  the one StratiGraph Server's asset gate already says, so a viewer refused through
  Heriverse and a viewer refused over HTTP are told the same thing.

**Read-only is enforced, not trusted.** A consumer that declared `write-graph`
is not refused at the door — a descriptor is a declaration, and refusing a peer
outright for being ambitious would take a viewer offline for a field nobody
reads. What happens instead is that the capability is *not granted*
(:func:`granted`), which is the same rule EMStudio's registry applies and the
same rule the room applies: a role decides, never a self-declaration. And
:func:`serve` refuses a writing capability outright, because serving is reading:
there is no path through this module that puts anything into a graph.

**What is published is not what is stored.** Two things are dropped on the way
out, and both would otherwise be a small scandal in a public scene:

* **tombstones** — a US the excavator deleted must be ABSENT, not greyed out
  (:mod:`s3dgraphy.dissemination` names `heriverse` a HIDE surface). The
  predicate is not re-implemented: :func:`s3dgraphy.crdt.live_nodes` /
  :func:`~s3dgraphy.crdt.live_edges` answer it, plus the edges those two leave
  dangling;
* **volatile proposals** — an ingest that arrived and has not been baked is not
  a fact about the study (:func:`~s3dgraphy.contract.connector.document_view`),
  and a viewer showing somebody's un-accepted folder as findings would publish a
  claim nobody made.

**What this module does NOT do.** It does not push: the transport is StratiGraph Server's
relay (P4.2/P4.3), which already speaks the wire. :class:`Subscription` is the
contract's side of a subscription — what a consumer is owed and what must never
reach it — and the socket that carries it is somebody else's job. It also does
not resolve an authority (`resolve-uri` is a capability a consumer may declare;
:mod:`s3dgraphy.resolvers` answers it) and it does not make thumbnails.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .connector import (CAPABILITY_LAYER, SEAM, WRITING_CAPABILITIES,
                        ConnectorDescriptor, document_view)
from .core import Result

# ── what a consumer may be ───────────────────────────────────────────────────
#
# A SUBSET of the one closed set, not a new one: `CONSUMER_CAPABILITIES` is
# filtered out of `CAPABILITY_LAYERS` below rather than typed, so a capability
# cannot be a consumer capability here and something else over there.

#: The capabilities :func:`serve` answers — reading, in the four senses a
#: dissemination client needs: the graph, the changes, the bytes, an identifier.
READ_CAPABILITIES: Tuple[str, ...] = ("read-graph", "subscribe",
                                     "resolve-asset", "resolve-preview",
                                     "resolve-uri")

#: Everything a consumer may declare: the reading capabilities plus the
#: ephemeral ones. A cursor and a roster are not reads of the document — they are
#: the radius of a person — which is why they are their own layer and why they
#: travel on the ephemeral channel rather than through anything here.
CONSUMER_CAPABILITIES: Tuple[str, ...] = READ_CAPABILITIES + (
    "link-selection", "presence")


def is_consumer(descriptor: ConnectorDescriptor) -> bool:
    """Does this connector only ever read?

    Declared, not inferred from a name: `heriverse` is a consumer because of what
    it asks for, and a viewer that grew an annotation write-back tomorrow stops
    being one the moment it says so.
    """
    return bool(descriptor.capabilities) and not any(
        c in WRITING_CAPABILITIES for c in descriptor.capabilities)


# ── who may read: the room's rule, one implementation ────────────────────────

#: The four roles, in order — the same order and the same names as StratiGraph Server's
#: `access.Role`, which RESOLVES them (from a token, an ACL, a group). Nothing
#: here resolves anything: it asks whether a role that was already resolved
#: carries a read or a write, and the answer is a comparison rather than a table
#: of cases.
ROLES: Tuple[str, ...] = ("viewer", "editor", "admin", "owner")

#: Visibility, as the header states it and the Catalog lists it.
VISIBILITIES: Tuple[str, ...] = ("public", "restricted")


def role_rank(role: Optional[str]) -> int:
    """-1 for "no role at all", which is a different thing from `viewer`.

    A viewer was GRANTED something. Somebody with no role was not, and in a
    restricted study those two must not come out the same — that distinction is
    the whole content of "a viewer is not one thing" (StratiGraph Server's `access`
    module says it at length).
    """
    try:
        return ROLES.index(str(role).strip().lower())
    except (ValueError, AttributeError):
        return -1


def role_can_write(role: Optional[str]) -> bool:
    """Editor and above. The predicate the embargo gate turns on."""
    return role_rank(role) >= ROLES.index("editor")


def may_read(visibility: Any, role: Optional[str] = None) -> bool:
    """May this caller read the study at all?

    `public` means published: anybody, including somebody with no token — that is
    what publishing IS, and a consumer serving a public study to anonymous
    visitors is the ordinary case, not an exception. `restricted` means login AND
    a grant.

    An embargo is *not* handled here even though it also gates reading: a study
    under embargo behaves as restricted whatever it says (StratiGraph Server's
    `effective_visibility`), and the caller passes the visibility that rule
    already produced — one place decides, and it is not two.
    """
    if str(visibility or "").strip().lower() == "public":
        return True
    return role_rank(role) >= 0


# ── the words of a serving refusal ───────────────────────────────────────────

@dataclass(frozen=True)
class ServeRefusals:
    """Parameterised for the same reason the core's are: a viewer shows this in a
    panel, a catalogue puts it in a body, and the refusals themselves are the
    contract while the sentences belong to whoever says them.

    `not_declared` is **the seam's own sentence**, not a copy: one wording for
    "you did not declare that", whichever direction the act was going.
    """

    not_declared: str = SEAM.not_declared
    read_only: str = ("«{name}» is a consumer: {capability} is not something a "
                      "read-only connector is served — it disseminates a study, "
                      "it does not write into one")
    no_grant: str = ("this study is {visibility} and this caller holds no role "
                     "in it — a consumer reads what it was granted, and nothing "
                     "was")
    #: The sentence StratiGraph Server's asset gate already says, on purpose: a viewer
    #: refused through a Heriverse scene and the same viewer refused over HTTP
    #: are told the same thing, including WHEN it opens.
    embargoed: str = ("this asset is under embargo until {until} — until then it "
                      "is readable by the people working on the study (editor "
                      "and above)")
    not_subscribed: str = ("«{name}» did not subscribe: there is nothing to push "
                           "to it")
    volatile: str = ("this change is a proposal nobody has accepted yet — it is "
                     "not published")


SERVE = ServeRefusals()


# ── the seam, in the outgoing direction ──────────────────────────────────────

def granted(descriptor: ConnectorDescriptor, role: Optional[str] = None,
            *, visibility: Any = "restricted") -> List[str]:
    """The capabilities this connector actually HAS here — declared ∩ allowed.

    The list a registry shows and a UI draws from, and the reason it is a
    function rather than the descriptor's own field: what a connector declared is
    a promise it made, what it may do is a decision somebody else took. A
    Heriverse that declared `write-graph` and arrived as a viewer is granted
    exactly the reads — no refusal, no drama, and no write.
    """
    if not may_read(visibility, role):
        return []
    writes = role_can_write(role)
    return [c for c in descriptor.capabilities
            if writes or c not in WRITING_CAPABILITIES]


def serve(descriptor: ConnectorDescriptor, capability: str, *,
          role: Optional[str] = None, visibility: Any = "restricted",
          phrases: ServeRefusals = SERVE) -> Result:
    """The seam every serving act passes: declared? a read? granted?

    Three refusals in that order, for the reason the write seam has three: they
    answer different questions, and the first one that fails is the one worth
    saying. Nothing is read here either — this returns a verdict, and the caller
    serves (:func:`serve_graph`, :func:`serve_asset`), which keeps a gate from
    half-answering.
    """
    if not descriptor.can(capability):
        return Result(ok=False,
                      message=phrases.not_declared.format(
                          name=descriptor.name, capability=capability),
                      data={"connector": descriptor.name,
                            "reason": "capability-not-declared",
                            "capability": capability})
    if capability in WRITING_CAPABILITIES:
        return Result(ok=False,
                      message=phrases.read_only.format(
                          name=descriptor.name, capability=capability),
                      data={"connector": descriptor.name, "reason": "read-only",
                            "capability": capability})
    if not may_read(visibility, role):
        return Result(ok=False,
                      message=phrases.no_grant.format(
                          visibility=str(visibility or "restricted")),
                      data={"connector": descriptor.name,
                            "reason": "role-not-granted",
                            "capability": capability,
                            "visibility": str(visibility or "restricted"),
                            "role": role})
    return Result(ok=True, message="",
                  data={"connector": descriptor.name, "capability": capability,
                        "layer": CAPABILITY_LAYER.get(capability),
                        "role": role, "visibility": str(visibility or "restricted")})


# ── the graph, as a consumer may have it ─────────────────────────────────────

@dataclass
class PublishedCount:
    """What :func:`published_view` left out. Numbers, because "the dead were
    filtered" is not a claim anybody can check."""

    removed_nodes: int = 0
    removed_edges: int = 0
    dangling: int = 0
    volatile_nodes: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {"removed_nodes": self.removed_nodes,
                "removed_edges": self.removed_edges,
                "dangling": self.dangling,
                "volatile_nodes": self.volatile_nodes}


def published_view(section: Dict[str, Any]
                   ) -> Tuple[Dict[str, Any], PublishedCount]:
    """The em.json section a consumer may have: no tombstones, no proposals.

    The section-level twin of :func:`s3dgraphy.dissemination.live_view` (which
    filters in-memory ``Graph`` objects for the exporters) — same policy, same
    predicate, a different shape of input, because the wire is em.json and
    parsing a document into a Graph to hide three nodes would be a cost with no
    payer.

    The third thing it drops is the reason this is a function and not two
    comprehensions: an edge left **dangling** by a hidden node does not hide the
    deletion, it publishes a broken graph.
    """
    from ..crdt import live_edges, live_nodes

    counted = PublishedCount()
    all_nodes = list(section.get("nodes") or [])
    all_edges = list(section.get("edges") or [])

    # 1 · proposals: not facts about the study (`document_view` is the same rule
    # a Save applies, so a consumer sees exactly what a saved file would carry)
    saved = document_view(section)
    counted.volatile_nodes = len(all_nodes) - len(saved.get("nodes") or [])

    # 2 · tombstones, by the one predicate
    nodes = live_nodes(saved)
    counted.removed_nodes = len(saved.get("nodes") or []) - len(nodes)
    edges = live_edges(saved)
    counted.removed_edges = len(saved.get("edges") or []) - len(edges)

    # 3 · and whatever the first two left pointing at a hole
    alive = {str(n.get("id")) for n in nodes}
    kept = [e for e in edges
            if str(e.get("source")) in alive and str(e.get("target")) in alive]
    counted.dangling = len(edges) - len(kept)

    out = dict(section)
    out["nodes"] = nodes
    out["edges"] = kept
    return out, counted


def serve_graph(section: Dict[str, Any], descriptor: ConnectorDescriptor, *,
                role: Optional[str] = None, visibility: Any = "restricted",
                phrases: ServeRefusals = SERVE) -> Result:
    """`read-graph`: the published view of one graph section, or a refusal."""
    verdict = serve(descriptor, "read-graph", role=role, visibility=visibility,
                    phrases=phrases)
    if not verdict.ok:
        return verdict
    view, counted = published_view(section)
    return Result(ok=True, message="",
                  data={"connector": descriptor.name, "capability": "read-graph",
                        "surface": "heriverse",
                        "nodes": view.get("nodes") or [],
                        "edges": view.get("edges") or [],
                        "hidden": counted.as_dict()})


# ── the bytes, and what the graph says about them ────────────────────────────

def serve_asset(document: Any, digest: Any, descriptor: ConnectorDescriptor, *,
                capability: str = "resolve-asset", role: Optional[str] = None,
                visibility: Any = "restricted",
                today: Optional[datetime.date] = None,
                phrases: ServeRefusals = SERVE) -> Result:
    """`resolve-asset` / `resolve-preview`: may these bytes go out, and under what.

    The store CONSULTS the graph; it does not keep a second copy of it
    (:mod:`s3dgraphy.rights`). So the answer is read from the document at call
    time, and the embargo verdict is computed against TODAY — an embargo that
    expired this morning is over this morning, whatever an index remembers.

    A **preview is not a loophole**: a thumbnail of an embargoed photograph is
    the photograph, and `resolve-preview` is gated identically. The two
    capabilities are separate because a viewer that may show a contact sheet
    without downloading originals is a real arrangement — the distinction is
    *what is served*, never *whether the embargo applies*.

    An asset the graph says nothing about is **served**, with `rights: None` —
    the same behaviour as StratiGraph Server's gate, and the honest one: "I know nothing
    about this digest" is not "this digest is embargoed", and refusing would make
    every unregistered byte in the store disappear. What is NOT done is inventing
    a licence for it: no rights means no `license_effective` either, because a
    default presented as a fact is worse than an absence.
    """
    from ..rights import normalise_digest, rights_for_digest

    verdict = serve(descriptor, capability, role=role, visibility=visibility,
                    phrases=phrases)
    if not verdict.ok:
        return verdict

    wanted = normalise_digest(digest)
    rights = rights_for_digest(document, wanted, today=today) if wanted else None
    base: Dict[str, Any] = {"connector": descriptor.name,
                            "capability": capability, "digest": wanted,
                            "rights": rights}

    if rights and rights.get("embargo_active") and not role_can_write(role):
        # Refused WITH THE DATE, and with the licence: a consumer that knows when
        # it opens can say so, and one that knows the terms can show them the day
        # it does. A bare 403 makes a viewer look broken.
        return Result(ok=False,
                      message=phrases.embargoed.format(until=rights.get("embargo")),
                      data={**base, "reason": "embargo-active",
                            "embargo": rights.get("embargo"),
                            "license": rights.get("license_effective")})

    # …and on the way out the licence TRAVELS. Not enforcement — a share-alike
    # cannot be imposed by a field — but nobody gets to say they were not told.
    # These are the same four facts StratiGraph Server puts in its `X-EM-*` headers.
    if rights:
        base["license"] = rights.get("license_effective")
        base["license_is_default"] = rights.get("license_is_default")
        base["authors"] = rights.get("authors") or []
        base["embargo"] = rights.get("embargo")
    return Result(ok=True, message="", data=base)


# ── the changes: what a subscription is owed ─────────────────────────────────

@dataclass
class Subscription:
    """One consumer's subscription — the contract's side of `subscribe`.

    Not a socket. The transport is StratiGraph Server's relay (P4.2/P4.3), which already
    speaks this wire and already fans out to whoever is in the room; what this
    holds is the part a relay must not decide on its own: *which changes a
    consumer is owed*.

    ``delivered`` is the log of what went out, so "the viewer got the rename" is
    a thing somebody can check rather than assert.
    """

    connector: str
    role: Optional[str] = None
    visibility: str = "restricted"
    delivered: List[Dict[str, Any]] = field(default_factory=list)
    withheld: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.delivered)


def subscribe(descriptor: ConnectorDescriptor, *, role: Optional[str] = None,
              visibility: Any = "restricted",
              phrases: ServeRefusals = SERVE) -> Result:
    """`subscribe`: a consumer asks to be told when the study changes."""
    verdict = serve(descriptor, "subscribe", role=role, visibility=visibility,
                    phrases=phrases)
    if not verdict.ok:
        return verdict
    subscription = Subscription(connector=descriptor.name, role=role,
                               visibility=str(visibility or "restricted"))
    return Result(ok=True, message="",
                  data={"connector": descriptor.name, "capability": "subscribe",
                        "subscription": subscription})


def _volatile_ids(section: Optional[Dict[str, Any]]) -> set:
    """The ids in this section that are proposals. Empty when no section is
    supplied — the caller then gets the payload check alone, which is stated in
    :func:`push` rather than silently assumed."""
    from .connector import VOLATILE_KEY
    if not isinstance(section, dict):
        return set()
    return {str(n.get("id")) for n in (section.get("nodes") or [])
            if (n.get("data") or {}).get(VOLATILE_KEY)}


def push(subscription: Subscription, op: Dict[str, Any], *,
         section: Optional[Dict[str, Any]] = None,
         phrases: ServeRefusals = SERVE) -> Result:
    """Hand one CRDT op to a subscribed consumer — or withhold it, and say why.

    The one thing withheld is a **volatile proposal**: an ingest nobody has baked
    is not published (same rule as :func:`published_view`, applied to the stream
    instead of to the document — a consumer that got the proposal live and the
    snapshot without it would show findings that vanish on reload).

    Two shapes of the same withholding, which is why ``section`` is worth
    passing: the op may CARRY the marker (an `add_node` for the proposal itself)
    or merely TOUCH something that has it (a `set_field` renaming a proposed
    node, an `add_edge` into one). Without the section only the first is
    detectable — a real limit, and a caller that has the graph should hand it
    over rather than let the second kind through.

    A **removal is delivered**, and as a removal. The tombstone rule is about a
    *document* — a merge has to see that something died — while a scene has to
    take the thing off the screen. Withholding it because "tombstones are hidden
    from Heriverse" would leave a deleted unit standing in the published scene,
    which is the exact failure the HIDE policy exists to prevent.
    """
    from .connector import VOLATILE_KEY

    node = op.get("node") if isinstance(op.get("node"), dict) else {}
    proposals = _volatile_ids(section)
    touched = [str(v) for v in (op.get("id"), node.get("id"),
                                op.get("source"), op.get("target"))
               if v not in (None, "")]
    if (node.get("data") or {}).get(VOLATILE_KEY) \
            or any(t in proposals for t in touched):
        subscription.withheld.append(dict(op))
        return Result(ok=False, message=phrases.volatile,
                      data={"connector": subscription.connector,
                            "reason": "volatile-proposal",
                            "op": op.get("op") or op.get("kind")})
    subscription.delivered.append(dict(op))
    return Result(ok=True, message="",
                  data={"connector": subscription.connector,
                        "capability": "subscribe",
                        "op": op.get("op") or op.get("kind"),
                        "delivered": subscription.count})
