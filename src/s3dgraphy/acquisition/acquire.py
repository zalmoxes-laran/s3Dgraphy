"""Tier-0 acquisition hook: descriptor → Resource + acquisition DTC event.

Consumes an :class:`AcquisitionDescriptor` (Tier 0 — opaque source, no inherited
payload) and, on a Shelf:

  * creates/reuses the **Resource** (LinkNode, R0 stable ID) for the asset, with
    ``origin`` = {repo, capabilities, scope} preserved for downstream tier badges
    (reuses the Session-A :func:`add_to_shelf`);
  * creates the **acquisition event** — a :class:`DTCAcquisitionNode`
    (crmdig:D12_Data_Transfer_Event), DISTINCT from a genesis process node — with
    the opaque source recorded as literals (repo/record/agent/retrieved_at/rights);
  * wires ``acquisition ─dtc_had_output→ Resource`` (prov:generated), the single
    ring of the Tier-0 chain (no genesis sub-graph).

Idempotent: the resource id is derived deterministically from (repo_id, record_id)
so re-acquiring the same record reuses the same Resource + event. Pure, no web.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Tuple

from .descriptor import AcquisitionDescriptor, AcquisitionError

# reuse the existing DTC output edge (prov:generated / crmdig:L11) — the acquired
# Resource is what the acquisition event produced. No new edge type needed.
_EDGE_HAD_OUTPUT = "dtc_had_output"
_ACQ_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://w3id.org/em/acquisition")


def _stable_resource_id(desc: AcquisitionDescriptor) -> str:
    """Deterministic id from (repo_id, record_id) for idempotent re-acquisition;
    else a fresh UUID."""
    repo = desc.source.get("repo_id")
    rec = desc.source.get("record_id")
    if repo and rec:
        return str(uuid.uuid5(_ACQ_NAMESPACE, f"{repo}:{rec}"))
    return str(uuid.uuid4())


def _resource_type(desc: AcquisitionDescriptor) -> str:
    from ..resources.fs_backend import classify_resource_type
    ref = desc.asset.get("ref", "") or ""
    rt = classify_resource_type(ref)
    if rt != "unknown":
        return rt
    mt = (desc.asset.get("media_type") or "").lower()
    top = mt.split("/", 1)[0] if "/" in mt else mt
    return {"image": "image", "model": "3d_model", "video": "video",
            "application": "document"}.get(top, "unknown")


def _acq_kind(desc: AcquisitionDescriptor) -> Optional[str]:
    """The acquisition method as a validated dtc_kind, or None (kept as literal)."""
    from ..utils.utils import get_dtc_kinds
    method = desc.acquisition.get("method")
    if method and method in get_dtc_kinds().get("acquisition", ()):
        return method
    return None


def _has_edge(graph: Any, s: str, t: str, et: str) -> bool:
    return any(e.edge_source == s and e.edge_target == t and e.edge_type == et
               for e in graph.edges)


def acquire_from_descriptor(descriptor: Any, shelf: Any = None
                            ) -> Tuple[Dict[str, Any], Any]:
    """Tier-0 acquisition: descriptor → (info, shelf).

    ``descriptor`` is an :class:`AcquisitionDescriptor` or a plain dict. ``shelf``
    is a shelf Graph (created via :func:`s3dgraphy.shelf.new_shelf` when ``None``).
    Returns ``(info, shelf)`` with ``info = {resource_id, acquisition_id, origin,
    entry, tier}``. Raises :class:`AcquisitionError` if the descriptor carries a
    payload_graph (that is Tier 1/2 — a later session)."""
    from ..shelf import add_to_shelf, new_shelf
    from ..nodes import DTCAcquisitionNode

    desc = (descriptor if isinstance(descriptor, AcquisitionDescriptor)
            else AcquisitionDescriptor.from_dict(descriptor))
    if not desc.is_tier0():
        raise AcquisitionError(
            "descriptor carries a payload_graph (Tier 1/2) — the Tier-0 hook only "
            "handles opaque sources; payload merge is a later session")

    if shelf is None:
        shelf = new_shelf()

    rid = _stable_resource_id(desc)
    ref = desc.asset.get("ref", "") or ""
    name = desc.asset.get("name") or (ref.rstrip("/").rsplit("/", 1)[-1] if ref else rid[:8])
    origin = desc.origin()

    # 1) Resource on the shelf (reuse-not-duplicate; origin preserved)
    entry = add_to_shelf(shelf, ref, resource_id=rid, name=name,
                         resource_type=_resource_type(desc), origin=origin)

    # 2) acquisition event — a distinct DTC event type (crmdig:D12), literals for
    #    the opaque upstream source (Tier 0: no genesis sub-graph)
    acq_id = str(uuid.uuid5(_ACQ_NAMESPACE, f"acq:{rid}"))
    acq = shelf.find_node_by_id(acq_id)
    if acq is None:
        acq = DTCAcquisitionNode(acq_id, name=f"Acquisition of {name}",
                                 dtc_kind=_acq_kind(desc))
        shelf.add_node(acq)
    lit = acq.data
    lit["repo_id"] = desc.source.get("repo_id")
    lit["record_id"] = desc.source.get("record_id")
    lit["record_url"] = desc.source.get("record_url")
    lit["retrieved_at"] = desc.acquisition.get("retrieved_at")
    lit["agent"] = desc.acquisition.get("agent")
    lit["method"] = desc.acquisition.get("method")
    # literal-first rights (design §7)
    lit["license"] = desc.rights.get("license")
    if desc.rights.get("holder"):
        lit["rights_holder"] = desc.rights.get("holder")
    if desc.rights.get("url"):
        lit["rights_url"] = desc.rights.get("url")

    # 3) acquisition ─dtc_had_output→ Resource (prov:generated) — the single ring
    if not _has_edge(shelf, acq_id, rid, _EDGE_HAD_OUTPUT):
        shelf.add_edge(f"{acq_id}__{_EDGE_HAD_OUTPUT}__{rid}", acq_id, rid,
                       _EDGE_HAD_OUTPUT)

    info = {
        "resource_id": rid,
        "acquisition_id": acq_id,
        "origin": origin,
        "entry": entry,
        "tier": 0,
    }
    return info, shelf
