"""The apparatus: a stable identity, and an edge from the step to it.

The node is :class:`s3dgraphy.nodes.DTCDeviceNode` and the reason it exists is in
its docstring. This module is the two things a caller needs: **how its id is
derived**, and **how it is attached**.

## The id, and why it is derived rather than chosen

If «Nikon D850» were a different node in every study, «what did this machine
produce» would return one study's answer and «which surveys used that scanner»
would return nothing. The node would have bought complexity and sold nothing.

So the id comes from a **descriptor**, by the mechanism this package already
uses: `uuid5` over a namespace, exactly as `bucket_acquisition` derives an
acquisition's id from the campaign name so that a second drop joins the event
instead of budding a new one. Same mechanism; **not a new one**.

**With one difference that is the design.** The acquisition's key carries the
``graph_id`` — a campaign is an event of THIS study, and two studies that each
ran «Aiano 2015» ran two campaigns. The device's key does not. The same camera in
two studies is one camera, and salting the key with the graph would manufacture
exactly the per-study duplicates the node exists to prevent.

## And what that costs, said rather than hidden

**Without a serial number, two identical bodies are one node.** Two Nikon D850s
in the same department, each described as make + model, derive the same id and
merge; the day somebody asks «which body took this» the graph cannot answer,
because nobody ever told it.

The alternative would be to salt the id with something that is not about the
device — a graph, a timestamp, a counter — and that fails the other way: two
records of the SAME camera become two cameras, silently, and the very questions
this node was added for start returning half an answer. A declared merge is
better than an invented distinction. :func:`device_identity` reports which of the
two happened (``distinguishes: "serial" | "make+model"``) so a caller can say so
instead of guessing, and so an interface can show it.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

#: Its own namespace, beside ingestion's. Two different species of thing that
#: happen to share a descriptor string must not collide on an id.
_DEVICE_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://w3id.org/em/device")

#: The edge from the step to the apparatus it happened on. Context, never chain:
#: it carries no `dtc_role`, and the datamodel says an edge without one is not
#: traversable by a provenance walk.
EDGE_HAPPENED_ON_DEVICE = "dtc_happened_on_device"

DEVICE_TYPE = "dtc_device"


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def device_identity(*, make: Any = None, model: Any = None,
                    serial: Any = None) -> Optional[Dict[str, Any]]:
    """The id of an apparatus, plus what that id can and cannot tell apart.

    Returns ``None`` when there is nothing to identify: an apparatus with no
    make, no model and no serial is not an apparatus anybody can point at, and
    minting an id for it would create a node that merges every unnamed device in
    the corpus into one.

    ``distinguishes`` is the honest half:

    * ``"serial"`` — this id names **one body**;
    * ``"make+model"`` — this id names **a model**, and two identical bodies
      share it. Declared, not hidden: see the module docstring.

    The key is normalised (lower-cased, whitespace collapsed) so that «Nikon
    D850», «nikon  d850» and «NIKON D850» are one camera. That is the same
    decision as the id itself: a difference that is only typing is not a
    difference between machines.
    """
    parts = [_text(make), _text(model), _text(serial)]
    if not any(parts):
        return None
    make_t, model_t, serial_t = parts
    key = "device|" + "|".join(" ".join((p or "").lower().split())
                               for p in parts)
    label = " ".join(p for p in (make_t, model_t) if p) or serial_t
    out: Dict[str, Any] = {
        "id": f"dev:{uuid.uuid5(_DEVICE_NAMESPACE, key)}",
        "label": label,
        "distinguishes": "serial" if serial_t else "make+model",
    }
    for name, value in (("make", make_t), ("model", model_t),
                        ("serial", serial_t)):
        if value:
            out[name] = value
    return out


def device_facts(node: Any) -> Dict[str, Any]:
    """The descriptor a device node carries, read back off it.

    Used by the emitter, so that what travels in a stamp is what the graph
    says rather than a second spelling of it.
    """
    data = getattr(node, "data", None)
    data = data if isinstance(data, dict) else {}
    out: Dict[str, Any] = {}
    for key in ("make", "model", "serial", "dtc_kind", "distinguishes"):
        value = _text(data.get(key))
        if value:
            out[key] = value
    return out


def attach_device(graph: Any, step_id: str, *, make: Any = None,
                  model: Any = None, serial: Any = None,
                  dtc_kind: Any = None, name: Any = None) -> Dict[str, Any]:
    """Declare the apparatus a step happened on, and return what it did.

    Idempotent by construction, and not by a flag: the id is derived, so calling
    this twice for the same camera finds the node that is already there and adds
    no second edge. That is the property that makes it safe to call from an
    importer that runs over a folder twice.

    The node is created only if it is missing; an existing one is **not
    overwritten**. A device that arrived with a serial and a genus from one study
    must not lose either because a second study knew only its model — the poorer
    description is not a correction.
    """
    from ..nodes.dtc_device_node import DTCDeviceNode

    identity = device_identity(make=make, model=model, serial=serial)
    if identity is None:
        raise ValueError(
            "a device needs at least one of make / model / serial: an apparatus "
            "nobody can name is not one, and minting an id for it would merge "
            "every unnamed device in the corpus into a single node")
    step = graph.find_node_by_id(step_id)
    if step is None:
        raise LookupError(f"no node {step_id!r} to attach a device to")

    warnings = []
    node = graph.find_node_by_id(identity["id"])
    created = node is None
    if created:
        data = {k: v for k, v in identity.items() if k in ("make", "model",
                                                           "serial")}
        data["distinguishes"] = identity["distinguishes"]
        node = DTCDeviceNode(identity["id"],
                             name=_text(name) or identity["label"],
                             dtc_kind=_text(dtc_kind), data=data)
        graph.add_node(node)
    elif getattr(node, "node_type", None) != DEVICE_TYPE:
        raise ValueError(
            f"{identity['id']!r} is a {getattr(node, 'node_type', '?')}, not a "
            f"device: refusing to turn somebody else's node into an apparatus")

    edge_id = f"edge:device:{step_id}:{identity['id']}"
    already = any(
        getattr(e, "edge_source", None) == step_id
        and getattr(e, "edge_target", None) == identity["id"]
        and getattr(e, "edge_type", None) == EDGE_HAPPENED_ON_DEVICE
        for e in (getattr(graph, "edges", None) or []))
    if not already:
        # NO `try` HERE, and the reason was measured rather than assumed. The
        # first version wrapped this and blamed «the datamodel», which would have
        # been a lie: `Graph.add_edge` does NOT enforce `allowed_connections` —
        # it only refuses when an endpoint is missing, and the connection rules
        # are read by the consumers that declare they read them (the connector
        # contract's guard_write, the RDF importer). So the only failure this
        # call can raise is a missing node, which the check above has already
        # ruled out for the step, and which for the device cannot happen because
        # it was just created. Catching here would have hidden a real defect
        # behind a sentence about a rule that never ran.
        graph.add_edge(edge_id, step_id, identity["id"],
                       EDGE_HAPPENED_ON_DEVICE)

    return {"device_id": identity["id"], "created": created,
            "attached": not already,
            "distinguishes": identity["distinguishes"],
            "warnings": warnings}
