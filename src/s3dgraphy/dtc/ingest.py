"""Ingestion, in bulk: a batch of files becomes ONE acquisition, and what came
out of what is **declared**, never guessed.

The four operations a tool needs the day somebody drags forty photographs into a
study. They are here, in the library, because more than one tool performs them —
EMStudio's Assets tab first, EMtools and a field ingest after — and a rule that
lives in a UI is a rule the next tool re-invents differently.

**Nothing new is introduced.** Every piece already existed:
:class:`~s3dgraphy.nodes.dtc_acquisition_node.DTCAcquisitionNode` (crmdig:D12) is
the event by which assets ENTER a study, ``ResourceNode`` is the file,
``dtc_had_output`` / ``dtc_had_input`` / ``dtc_derived_from`` are the chain, and
:mod:`s3dgraphy.rights` is how a licence gets said and signed. What was missing
was the *plural*: one event over N files, one attribution over the lot, and a
reader that can answer "where is this asset used?".

Four decisions this module encodes — E.D.'s, taken before the code:

1. **The serial node is the acquisition, not a new type.** A campaign of five
   hundred photographs is ONE node that groups them, not five hundred top-level
   things somebody has to scroll past. The resources still exist (they have
   digests, rights and bytes of their own); what the bucket gives them is a
   place to be.
2. **No document-node.** The "document" is a sub-graph — acquisition → process →
   output — and never a monolith that would have to be kept in step with the
   files it claims to contain.
3. **The derivation chain is DECLARED.** Nobody infers that an orthophoto came
   out of that flight because the timestamps line up: somebody says so, and the
   graph records who and with which tool. The tool is described **at the
   minimum** — its name — and enriched later; an empty parameter form would be a
   promise the data cannot keep.
4. **Attribution and provenance have different granularity, and must not be
   fused.** A licence belongs to the LOT (one campaign, one rights holder);
   how-it-was-made belongs to the single OUTPUT. So they are two calls, and a UI
   is free to offer them at two different moments.

Tombstones are skipped in reading *and* in writing, everywhere — a removed node
is not a member, not an input, and never a node to write onto.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..rights import normalise_digest

#: Deterministic ids for the ingestion chain, so the same act asked twice is the
#: same act. Its own namespace, distinct from promotion's: two different events
#: that happened to share inputs must not collide on an id.
_INGEST_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://w3id.org/em/ingest")

#: A batch dragged in from somebody's disk. The `acquisition` axis of the
#: data-driven `dtc_kinds` vocabulary (em_visual_rules.json) — `download` and
#: `ingest` are the other two, and which one a caller means is theirs to say.
DEFAULT_ACQUISITION_KIND = "local_import"

#: The `process` axis term for "this was made from that" — the same one
#: promotion uses. Not a new word for the same event.
DEFAULT_PROCESS_KIND = "transformation"

EDGE_HAD_INPUT = "dtc_had_input"
EDGE_HAD_OUTPUT = "dtc_had_output"
EDGE_DERIVED_FROM = "dtc_derived_from"

#: How a node can REFER to a resource, and what kind of reference it is. The
#: classification is the point of `resource_usages`: "an epoch cites this photo"
#: and "this photo is CC-BY" are both edges to the same node, and an inspector
#: that listed them together would bury the first under the second.
_USAGE_ROLES = {
    "has_linked_resource": "reference",
    "has_visual_reference": "reference",
    "is_on_resource": "annotation",
    "has_digital_object_part": "reference",
    "dtc_had_input": "chain",
    "dtc_had_output": "chain",
    "dtc_derived_from": "chain",
    "has_author": "rights",
    "has_license": "rights",
    "has_embargo": "rights",
}


# ── the small shared readers (dict-or-object, tombstone-aware) ───────────────

def _data(node: Any) -> Dict[str, Any]:
    d = getattr(node, "data", None)
    return d if isinstance(d, dict) else {}


def _alive(item: Any) -> bool:
    from ..crdt import is_removed
    payload = item if isinstance(item, dict) else getattr(item, "__dict__", {}) or {}
    try:
        return not is_removed(payload)
    except Exception:      # pragma: no cover — a shape crdt cannot read is alive
        return True


def _alive_nodes(graph: Any) -> List[Any]:
    return [n for n in getattr(graph, "nodes", []) or [] if _alive(n)]


def _alive_edges(graph: Any) -> List[Any]:
    return [e for e in getattr(graph, "edges", []) or [] if _alive(e)]


def _stable_id(key: str) -> str:
    return str(uuid.uuid5(_INGEST_NAMESPACE, key))


def _find(graph: Any, ref: str) -> Optional[Any]:
    """A node by id — or by DIGEST, because a caller that has just uploaded
    bytes holds their sha256 and not an id it never chose. Tombstones do not
    answer: writing onto a corpse is the mistake this ecosystem has already
    paid for twice."""
    if not ref:
        return None
    wanted = str(ref)
    for node in _alive_nodes(graph):
        if getattr(node, "node_id", None) == wanted:
            return node
    digest = normalise_digest(wanted)
    if not digest:
        return None
    for node in _alive_nodes(graph):
        if normalise_digest(_data(node).get("checksum")) == digest:
            return node
    return None


def _ensure_edge(graph: Any, source: str, target: str, edge_type: str,
                 warnings: List[str]) -> Optional[str]:
    """Create the edge unless it is already there. Returns its id, or None when
    the datamodel refused it (reported, never silently degraded to generic)."""
    for edge in _alive_edges(graph):
        if (getattr(edge, "edge_source", None) == source
                and getattr(edge, "edge_target", None) == target
                and getattr(edge, "edge_type", None) == edge_type):
            return getattr(edge, "edge_id", None)
    edge_id = _stable_id(f"edge|{source}|{edge_type}|{target}")
    before = len(getattr(graph, "warnings", []) or [])
    try:
        edge = graph.add_edge(edge_id, source, target, edge_type)
    except ValueError as exc:
        warnings.append(f"edge {edge_type} not created: {exc}")
        return None
    # `add_edge` DEGRADES a refused connection to `generic_connection` and puts a
    # sentence in graph.warnings. Silence here would let an unsupported pairing
    # look like a success and show up months later as a chain nobody can walk.
    if getattr(edge, "edge_type", edge_type) != edge_type:
        for extra in (getattr(graph, "warnings", []) or [])[before:]:
            warnings.append(str(extra))
    return getattr(edge, "edge_id", edge_id)


def _stamp(node: Any, *, author: Optional[str], at: Optional[str]) -> None:
    from ..editorial import stamp_created, stamp_modified
    stamp_created(node, by=author, at=at)
    stamp_modified(node, by=author, at=at)


# ── 1 · the bucket: N files, ONE acquisition ─────────────────────────────────

def bucket_acquisition(graph: Any, resources: Sequence[str], *,
                       acquisition_id: Optional[str] = None,
                       name: Optional[str] = None,
                       dtc_kind: Optional[str] = DEFAULT_ACQUISITION_KIND,
                       metadata: Optional[Dict[str, Any]] = None,
                       author: Optional[str] = None,
                       at: Optional[str] = None) -> Dict[str, Any]:
    """Group resources under ONE acquisition event (crmdig:D12).

    ``resources`` are node ids **or** digests — a caller fresh from an upload
    holds sha256s, a caller working on the graph holds ids, and both are the
    same question. A reference that matches nothing alive is *reported*, not
    invented: an acquisition claiming a member the graph does not have would be
    a lie a reader cannot detect.

    The membership IS the ``dtc_had_output`` edges (prov:generated — the event
    produced these files *in this study*). ``data.member_count`` is written
    beside them as a cached convenience for a list that wants a number without
    walking the graph; it is **recomputed on every call**, and the edges stay
    the authority. A count that disagrees with the edges is a stale cache, never
    a second truth to reconcile.

    ``metadata`` is merged into ``data`` verbatim: the representative facts of a
    lot (camera, lens, date, operator, folder) belong to the event, not repeated
    on four hundred files. Keys are never invented here — an absent camera stays
    absent.

    Idempotent. With no ``acquisition_id`` the id is derived: from the ``name``
    when there is one (so "Volo 2026-03" keeps meaning the same event and a
    second drop ADDS to it), otherwise from the sorted member keys (so the same
    batch converges instead of budding a second bucket). Naming a lot is
    therefore the way to keep adding to it — said here because the alternative
    surprises people.

    Returns ``{acquisition_id, created, members, added, missing, count,
    warnings}``. With **no live member at all** and no such acquisition yet,
    nothing is created and ``acquisition_id`` is ``None`` — an event that groups
    no file is not an event (see the guard below).
    """
    from ..nodes import DTCAcquisitionNode

    warnings: List[str] = []
    members: List[str] = []
    missing: List[str] = []
    for ref in resources or ():
        node = _find(graph, str(ref))
        if node is None:
            missing.append(str(ref))
            warnings.append(
                f"'{ref}' is not a live resource in this graph: not bucketed")
            continue
        if getattr(node, "node_type", None) != "resource":
            missing.append(str(ref))
            warnings.append(
                f"'{ref}' is a {getattr(node, 'node_type', '?')}, not a resource: "
                f"an acquisition groups FILES")
            continue
        if node.node_id not in members:
            members.append(node.node_id)

    if acquisition_id:
        acq_id = str(acquisition_id)
    elif name:
        acq_id = _stable_id(f"acquisition|{getattr(graph, 'graph_id', '')}|{name}")
    else:
        acq_id = _stable_id("acquisition|" + "|".join(sorted(members)))

    acq = _find(graph, acq_id)
    # An acquisition that groups NOTHING is not an acquisition. When every
    # reference is a ghost (a batch whose resources were never written, or were
    # tombstoned since), creating the event anyway leaves an EMPTY ROOT in the
    # corpus: a lot that claims to be where material entered the study while
    # naming no file at all. Measured on a synthetic corpus — an all-ghost lot
    # gave the DAG a fourth root nobody had documented.
    #
    # This refuses to CREATE, not to answer: an acquisition that already exists
    # keeps its identity (a second batch whose refs are all ghosts is a call that
    # added nothing to a real lot, and saying `acquisition_id: None` about a node
    # the caller can see would be the same kind of lie in the other direction).
    if not members and acq is None:
        warnings.append("no live resource to bucket — acquisition not created")
        return {"acquisition_id": None, "created": False, "members": [],
                "added": [], "missing": missing, "count": 0,
                "warnings": warnings}

    created = acq is None
    if acq is None:
        acq = DTCAcquisitionNode(
            acq_id,
            name=name or f"Acquisition of {len(members)} file(s)",
            description="",
            dtc_kind=dtc_kind)
        graph.add_node(acq)
    elif getattr(acq, "node_type", None) != "dtc_acquisition":
        raise ValueError(
            f"'{acq_id}' is a {getattr(acq, 'node_type', '?')}, not an "
            f"acquisition: refusing to turn somebody else's node into a bucket")
    elif name:
        acq.name = name

    data = _data(acq)
    if not isinstance(getattr(acq, "data", None), dict):
        acq.data = data
    if dtc_kind and not created:
        data.setdefault("dtc_kind", dtc_kind)
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        data[key] = value

    added: List[str] = []
    for member in members:
        already = any(
            getattr(e, "edge_source", None) == acq_id
            and getattr(e, "edge_target", None) == member
            and getattr(e, "edge_type", None) == EDGE_HAD_OUTPUT
            for e in _alive_edges(graph))
        edge_id = _ensure_edge(graph, acq_id, member, EDGE_HAD_OUTPUT, warnings)
        if edge_id and not already:
            added.append(member)

    live = acquisition_members(graph, acq_id)
    data["member_count"] = len(live)
    _stamp(acq, author=author, at=at)

    return {"acquisition_id": acq_id, "created": created, "members": live,
            "added": added, "missing": missing, "count": len(live),
            "warnings": warnings}


def acquisition_members(graph: Any, acquisition_id: str) -> List[str]:
    """The resources this acquisition brought in — read off the edges, live.

    The authority on membership. `data.member_count` is a cache of its length
    and this is what re-computes it; a tombstoned member drops out here first.
    """
    out: List[str] = []
    alive_ids = {n.node_id for n in _alive_nodes(graph)}
    for edge in _alive_edges(graph):
        if (getattr(edge, "edge_type", None) == EDGE_HAD_OUTPUT
                and getattr(edge, "edge_source", None) == acquisition_id):
            target = getattr(edge, "edge_target", None)
            if target in alive_ids and target not in out:
                out.append(target)
    return out


# ── 2 · the derivation, DECLARED ─────────────────────────────────────────────

def declare_derivation(graph: Any, output: str, inputs: Sequence[str], *,
                       tool: Optional[str] = None,
                       process_id: Optional[str] = None,
                       dtc_kind: Optional[str] = DEFAULT_PROCESS_KIND,
                       name: Optional[str] = None,
                       author: Optional[str] = None,
                       at: Optional[str] = None) -> Dict[str, Any]:
    """Say that this output came out of those inputs, with this tool.

    ``output`` is a ``ResourceNode`` (id or digest). Each entry of ``inputs`` is
    a resource **or a whole acquisition** — "the orthophoto comes from the March
    flight" is one input, not two hundred, and that is the reason the serial node
    exists at all.

    The event is a ``DTCProcessNode`` (crmdig:D7) wired
    ``process ─dtc_had_input→ input`` and ``process ─dtc_had_output→ output``.
    For a *resource* input the direct shortcut ``output ─dtc_derived_from→ input``
    is written too (as promotion does); for an *acquisition* input there is no
    shortcut to write — ``dtc_derived_from`` runs between files, and a batch is
    an event. Reported, not faked.

    **The tool is named and nothing else.** ``data.tool = {"name": …}`` is a
    dict on purpose: version, parameters and a container digest are the natural
    next keys, and a caller that adds them does not have to migrate a string.

    Idempotent: the process id is derived from (output, sorted inputs, tool), so
    declaring the same derivation twice converges on one event.

    Returns ``{process_id, created, output, inputs, missing, warnings}``.
    """
    from ..nodes import DTCProcessNode

    warnings: List[str] = []
    out_node = _find(graph, str(output))
    if out_node is None or getattr(out_node, "node_type", None) != "resource":
        raise LookupError(
            f"no live resource '{output}' in this graph: declare a derivation "
            f"after its output exists, not instead of it")

    resolved: List[Any] = []
    missing: List[str] = []
    for ref in inputs or ():
        node = _find(graph, str(ref))
        if node is None:
            missing.append(str(ref))
            warnings.append(f"'{ref}' is not in this graph: not recorded as input")
            continue
        if getattr(node, "node_type", None) not in ("resource", "dtc_acquisition"):
            missing.append(str(ref))
            warnings.append(
                f"'{ref}' is a {getattr(node, 'node_type', '?')}: an input is a "
                f"resource or an acquisition")
            continue
        if node.node_id == out_node.node_id:
            missing.append(str(ref))
            warnings.append(
                f"'{ref}' is the output itself: a file is not derived from itself")
            continue
        if all(node.node_id != n.node_id for n in resolved):
            resolved.append(node)

    key = "|".join([out_node.node_id, *sorted(n.node_id for n in resolved),
                    (tool or "")])
    pid = str(process_id) if process_id else _stable_id(f"derivation|{key}")

    proc = _find(graph, pid)
    created = proc is None
    if proc is None:
        proc = DTCProcessNode(
            pid,
            name=name or (tool.strip() if tool and tool.strip()
                          else f"derivation of {out_node.name}"),
            description="",
            dtc_kind=dtc_kind)
        graph.add_node(proc)
    elif getattr(proc, "node_type", None) != "dtc_process":
        raise ValueError(
            f"'{pid}' is a {getattr(proc, 'node_type', '?')}, not a DTC process")

    data = _data(proc)
    if not isinstance(getattr(proc, "data", None), dict):
        proc.data = data
    if tool and tool.strip():
        # the MINIMUM description of a tool: its name. A dict so that version,
        # parameters and a container digest are additions, not a migration.
        existing = data.get("tool")
        merged = dict(existing) if isinstance(existing, dict) else {}
        merged["name"] = tool.strip()
        data["tool"] = merged

    _ensure_edge(graph, pid, out_node.node_id, EDGE_HAD_OUTPUT, warnings)
    for node in resolved:
        _ensure_edge(graph, pid, node.node_id, EDGE_HAD_INPUT, warnings)
        if getattr(node, "node_type", None) == "resource":
            _ensure_edge(graph, out_node.node_id, node.node_id,
                         EDGE_DERIVED_FROM, warnings)
    _stamp(proc, author=author, at=at)

    return {"process_id": pid, "created": created, "output": out_node.node_id,
            "inputs": [n.node_id for n in resolved], "missing": missing,
            "warnings": warnings}


def derivation_chain(graph: Any, resource: str) -> Dict[str, Any]:
    """What made this file, and what it went on to make — one hop each way.

    Read-only, and deliberately shallow: an inspector shows the neighbourhood,
    and a full transitive walk is a different question (and a different screen).
    """
    node = _find(graph, str(resource))
    if node is None:
        return {"resource": None, "made_by": [], "used_by": []}
    rid = node.node_id
    made_by: List[Dict[str, Any]] = []
    used_by: List[Dict[str, Any]] = []
    for edge in _alive_edges(graph):
        etype = getattr(edge, "edge_type", None)
        source = getattr(edge, "edge_source", None)
        target = getattr(edge, "edge_target", None)
        if etype == EDGE_HAD_OUTPUT and target == rid:
            event = _find(graph, str(source))
            if event is not None:
                made_by.append(_event_card(graph, event))
        elif etype == EDGE_HAD_INPUT and target == rid:
            event = _find(graph, str(source))
            if event is not None:
                used_by.append(_event_card(graph, event))
    return {"resource": rid, "made_by": made_by, "used_by": used_by}


def _event_card(graph: Any, event: Any) -> Dict[str, Any]:
    data = _data(event)
    tool = data.get("tool")
    return {
        "id": event.node_id,
        "type": getattr(event, "node_type", ""),
        "name": str(getattr(event, "name", "") or ""),
        "dtc_kind": data.get("dtc_kind"),
        "tool": (tool or {}).get("name") if isinstance(tool, dict) else tool,
        "inputs": [getattr(e, "edge_target", None) for e in _alive_edges(graph)
                   if getattr(e, "edge_type", None) == EDGE_HAD_INPUT
                   and getattr(e, "edge_source", None) == event.node_id],
        "outputs": [getattr(e, "edge_target", None) for e in _alive_edges(graph)
                    if getattr(e, "edge_type", None) == EDGE_HAD_OUTPUT
                    and getattr(e, "edge_source", None) == event.node_id],
    }


# ── 3 · attribution, per LOT ─────────────────────────────────────────────────

def attribute_batch(graph: Any, acquisition_id: str, *,
                    attributor: Optional[str],
                    author: Any = None, author_name: Optional[str] = None,
                    license: Any = None, embargo: Any = None,
                    reason: Optional[str] = None, at: Optional[str] = None,
                    propagate: bool = False) -> Dict[str, Any]:
    """Declare licence / author / embargo for a whole acquisition, signed.

    One statement for the lot, hung on the EVENT — which is exactly how
    :func:`s3dgraphy.rights.rights_for_digest` already reads it: a file that says
    nothing about itself inherits from the chunk that brought it in, so four
    hundred photographs get one licence without four hundred copies of it.

    ``propagate=True`` also stamps every member individually
    (:func:`~s3dgraphy.rights.enrich_asset_dtc`). Off by default, and the choice
    is not cosmetic: stamped members keep their licence when they leave the
    campaign, but the lot then has four hundred statements to revise the day
    somebody changes their mind. Inheritance is one truth; propagation is a copy,
    and a copy is a thing that can disagree.

    Same tri-state as the single-asset act: omitted leaves alone, a value
    declares, ``""`` retracts. ``attributor`` is required for the same reason —
    an attribution nobody signs is a rumour.

    Returns ``{acquisition_id, changed, members, propagated, attributor, at,
    warnings}``.
    """
    from ..editorial import now_iso
    from ..rights import declare_statements, enrich_asset_dtc

    acq = _find(graph, str(acquisition_id))
    if acq is None or getattr(acq, "node_type", None) != "dtc_acquisition":
        raise LookupError(
            f"no live acquisition '{acquisition_id}' in this graph")
    if not attributor:
        raise ValueError(
            "attribute_batch needs an attributor: an attribution nobody signs "
            "is a rumour, and a batch of four hundred files is not the place to "
            "start")
    stamp = at or now_iso()

    changed = declare_statements(graph, acq.node_id, attributor=str(attributor),
                                 author=author, author_name=author_name,
                                 license=license, embargo=embargo,
                                 reason=reason, at=stamp)

    members = acquisition_members(graph, acq.node_id)
    propagated: List[str] = []
    warnings: List[str] = []
    if propagate:
        for member in members:
            node = _find(graph, member)
            digest = normalise_digest(_data(node).get("checksum")) if node else None
            if not digest:
                warnings.append(
                    f"'{member}' carries no checksum: the lot's rights are "
                    f"inherited, not stamped on it")
                continue
            enrich_asset_dtc(graph, digest, attributor=str(attributor),
                             author=author, author_name=author_name,
                             license=license, embargo=embargo, reason=reason,
                             at=stamp)
            propagated.append(member)

    return {"acquisition_id": acq.node_id, "changed": changed,
            "members": members, "propagated": propagated,
            "attributor": str(attributor), "at": stamp, "warnings": warnings}


# ── 4 · who uses this asset ──────────────────────────────────────────────────

def resource_usages(graph: Any, resource: str) -> List[Dict[str, Any]]:
    """Every live node that refers to this asset, classified by *how*.

    The question the inspector's "used by…" asks, and the one somebody must be
    able to answer before replacing a file: a photograph cited by three units, an
    epoch and a narrative is not a photograph you swap silently.

    ``resource`` is a node id or a digest. Each entry is
    ``{id, node_type, name, edge_type, role, direction}`` where *role* is
    ``reference`` (something points at the file), ``annotation`` (a region drawn
    on it), ``chain`` (the DTC event that made or consumed it), ``rights`` (its
    own licence/author/embargo statements — attached to it, not uses of it) or
    ``other``. Sorted by (role, node id) so two runs read the same.

    Tombstoned nodes and edges are absent: a usage somebody deleted is not a
    reason to keep a file.
    """
    node = _find(graph, str(resource))
    if node is None:
        return []
    rid = node.node_id
    by_id = {n.node_id: n for n in _alive_nodes(graph)}
    out: List[Dict[str, Any]] = []
    seen = set()
    for edge in _alive_edges(graph):
        etype = str(getattr(edge, "edge_type", "") or "")
        source = getattr(edge, "edge_source", None)
        target = getattr(edge, "edge_target", None)
        if source == rid:
            other, direction = target, "outgoing"
        elif target == rid:
            other, direction = source, "incoming"
        else:
            continue
        neighbour = by_id.get(other)
        if neighbour is None:
            continue
        key = (neighbour.node_id, etype, direction)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": neighbour.node_id,
            "node_type": getattr(neighbour, "node_type", ""),
            "name": str(getattr(neighbour, "name", "") or ""),
            "edge_type": etype,
            "role": _USAGE_ROLES.get(etype, "other"),
            "direction": direction,
        })
    out.sort(key=lambda r: (r["role"], r["id"]))
    return out


def unused_resources(graph: Any) -> List[Dict[str, Any]]:
    """Files nothing points at — a bucket's contents that no study text, unit or
    process has ever used. Not a fault (an archive is allowed to hold what nobody
    has cited yet); a list somebody may want to look at before a release."""
    out: List[Dict[str, Any]] = []
    for node in _alive_nodes(graph):
        if getattr(node, "node_type", None) != "resource":
            continue
        uses = [u for u in resource_usages(graph, node.node_id)
                if u["role"] in ("reference", "annotation")]
        if not uses:
            out.append({"id": node.node_id,
                        "name": str(getattr(node, "name", "") or ""),
                        "checksum": _data(node).get("checksum")})
    return out


def batch_summary(graph: Any, acquisition_id: str) -> Dict[str, Any]:
    """One acquisition, as a panel shows it: the event, its rights, its members
    with their own rights, and the count. Read-only."""
    from ..rights import rights_for_digest

    acq = _find(graph, str(acquisition_id))
    if acq is None:
        return {"acquisition_id": str(acquisition_id), "found": False,
                "members": [], "count": 0}
    members = []
    for member_id in acquisition_members(graph, acq.node_id):
        node = _find(graph, member_id)
        digest = normalise_digest(_data(node).get("checksum")) if node else None
        rights = rights_for_digest(graph, digest) if digest else None
        members.append({
            "id": member_id,
            "name": str(getattr(node, "name", "") or "") if node else "",
            "checksum": _data(node).get("checksum") if node else None,
            "residency": _data(node).get("residency") if node else None,
            "scope": _data(node).get("scope") if node else None,
            "license": (rights or {}).get("license"),
            "license_effective": (rights or {}).get("license_effective"),
            "via": (rights or {}).get("via"),
        })
    data = _data(acq)
    return {
        "acquisition_id": acq.node_id,
        "found": True,
        "name": str(getattr(acq, "name", "") or ""),
        "dtc_kind": data.get("dtc_kind"),
        "metadata": {k: v for k, v in data.items()
                     if k not in ("dtc_kind", "member_count")},
        "members": members,
        "count": len(members),
    }
