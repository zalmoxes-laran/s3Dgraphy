"""
Hybrid-C auxiliary-lifecycle tracking (Phase 1 of
``HYBRID_C_AUXILIARY_LIFECYCLE.md``).

The "auxiliary" layer in EMtools/s3Dgraphy covers DosCo documents,
emdb property tables, pyArchInit SQLite, sources-list xlsx and
configurable resource-folders. Auxiliary files **attach** to existing
host nodes via a stable key ID (``D.NN`` for documents, US / USV ids
for stratigraphic units). They never create new top-level entities
by themselves: they only

1. add **enrichment child nodes and edges** (e.g. ``PropertyNode``
   children added by emdb, ``LinkNode`` children added by DosCo),
2. update **attributes on the host node** (e.g. DosCo setting
   ``DocumentNode.url``, sources-list setting
   ``author / license / embargo``).

This module provides the bookkeeping primitives so a later exporter
pass can either keep the auxiliary layer ephemeral (**volatile save**,
default) or commit it into the GraphML (**bake**).

Two complementary tracks:

* ``mark_as_injected(obj, injector_id)`` / ``is_injected(obj)`` —
  tag enrichment children with ``attributes['injected_by']``.
* ``record_attribute_override(node, attr, injector_id, original)`` /
  ``aux_overridden_attrs(node)`` — record each auxiliary-induced
  attribute change so the volatile save can revert it (or keep the
  current value if the user re-edited it manually afterwards).

Additional helpers:

* ``strip_injected_content(graph, keep_ids=None)`` — remove every
  node and edge tagged ``injected_by`` from a graph in-place.
  Returns the number of items removed.
* ``apply_override_reversal_policy(graph)`` — walk every host node
  with ``_aux_overrides`` and, for each attribute, revert to the
  original value **only if** the current value is still the aux
  value; otherwise drop the override record (the user re-edited).
* ``clear_aux_tags(graph)`` — clear both ``injected_by`` tags and
  ``_aux_overrides`` across the whole graph. Used by the **bake**
  path to promote the enrichment layer to graph-native.

All functions are side-effect-free unless documented otherwise.
"""

from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# Sentinel used to mark a missing original value in ``_aux_overrides``
# entries (i.e. the attribute did not exist before the auxiliary
# injected it). We use a string so the per-attribute dict remains
# JSON-serialisable, and we document it here.
_MISSING = "<MISSING>"


# ---------------------------------------------------------------------------
# Tagging: enrichment children
# ---------------------------------------------------------------------------

def mark_as_injected(obj, injector_id: str) -> None:
    """Tag an enrichment node or edge as coming from an auxiliary.

    ``injector_id`` is a free-form string, conventionally in the form
    ``"<kind>:<source-path>"``: ``"DosCo:/path/to/DosCo"``,
    ``"emdb:/path/x.xlsx"``, ``"pyarchinit:/path/x.sqlite"``,
    ``"sources_list:/path/sources.xlsx"``,
    ``"resource_folder:/path/resources"``.

    The tag lives on the object's ``attributes`` dict under the key
    ``"injected_by"``. Nodes and edges both expose an ``attributes``
    dict in s3Dgraphy.
    """
    if obj is None:
        return
    attrs = getattr(obj, "attributes", None)
    if attrs is None:
        # Defensive: some node classes build attributes lazily. Only
        # assign when there's a way to store it.
        try:
            obj.attributes = {}
        except Exception:
            return
        attrs = obj.attributes
    attrs["injected_by"] = injector_id


def is_injected(obj) -> Optional[str]:
    """Return the injector id stamped on ``obj``, or ``None`` if
    the object is graph-native (no ``injected_by`` tag).
    """
    if obj is None:
        return None
    attrs = getattr(obj, "attributes", None) or {}
    val = attrs.get("injected_by")
    return val if val else None


# ---------------------------------------------------------------------------
# Tagging: host-node attribute overrides
# ---------------------------------------------------------------------------

def record_attribute_override(node, attr_name: str, injector_id: str,
                                original_value: Any) -> None:
    """Record that an auxiliary touched ``node.<attr_name>`` and that
    its pre-auxiliary value was ``original_value``.

    Call this **before** applying the auxiliary change so the
    ``original_value`` you pass is the real pre-aux value. If the
    attribute did not exist prior to the aux, pass
    :data:`MISSING_SENTINEL` (or the module-level ``_MISSING``).

    The override is stored on the node's attributes dict under the
    special key ``"_aux_overrides"`` as a dict:

    ``{attr_name: {"injector": injector_id, "aux_value": <set by
    apply_override_reversal_policy>, "original": original_value}}``

    The ``aux_value`` slot is filled by
    :func:`freeze_aux_values` just after the injector finishes its
    pass, so that ``apply_override_reversal_policy`` can later
    compare the current value against the aux value (to detect user
    edits) without requiring the injector to track it by itself.
    """
    if node is None or not attr_name:
        return
    attrs = getattr(node, "attributes", None)
    if attrs is None:
        try:
            node.attributes = {}
        except Exception:
            return
        attrs = node.attributes
    overrides = attrs.setdefault("_aux_overrides", {})
    # If the auxiliary applies twice (re-register after aux source
    # file change) we keep the FIRST original — that is the true
    # pre-aux value.
    if attr_name not in overrides:
        overrides[attr_name] = {
            "injector": injector_id,
            "original": original_value,
            # aux_value left undefined until freeze_aux_values runs
        }


def freeze_aux_value(node, attr_name: str) -> None:
    """Called by the injector AFTER it has written the new value to
    ``node.<attr_name>``. Copies the freshly-written value into the
    override record so the reversal policy can later compare against
    it.

    If no override record exists (injector didn't call
    ``record_attribute_override`` first), this is a no-op — the
    attribute is treated as graph-native.
    """
    if node is None:
        return
    attrs = getattr(node, "attributes", None) or {}
    overrides = attrs.get("_aux_overrides")
    if not overrides or attr_name not in overrides:
        return
    overrides[attr_name]["aux_value"] = _read_attr(node, attr_name)


def aux_overridden_attrs(node) -> Dict[str, Dict[str, Any]]:
    """Return the ``_aux_overrides`` dict for ``node`` (empty dict if
    none). Keys are attribute names; values are ``{"injector", "original",
    "aux_value"}`` triples.
    """
    if node is None:
        return {}
    attrs = getattr(node, "attributes", None) or {}
    return dict(attrs.get("_aux_overrides") or {})


# ---------------------------------------------------------------------------
# Bulk operations used by the exporters
# ---------------------------------------------------------------------------

def strip_injected_content(graph) -> Dict[str, int]:
    """Remove every node and edge whose ``attributes['injected_by']``
    is set. Returns ``{"nodes": N, "edges": M}``.

    Edges are removed first (to avoid dangling endpoints), then the
    nodes are removed. Any edge that becomes dangling because its
    endpoint was removed is also dropped.

    This mutates ``graph`` in place.
    """
    removed_edges = 0
    removed_nodes = 0

    # First pass: collect injected node ids.
    injected_node_ids: Set[str] = set()
    for n in graph.nodes:
        if is_injected(n):
            injected_node_ids.add(n.node_id)

    # Remove edges injected OR touching an injected node.
    keep_edges = []
    for e in graph.edges:
        if is_injected(e):
            removed_edges += 1
            continue
        if e.edge_source in injected_node_ids or e.edge_target in injected_node_ids:
            removed_edges += 1
            continue
        keep_edges.append(e)
    graph.edges = keep_edges

    # Remove injected nodes
    keep_nodes = []
    for n in graph.nodes:
        if n.node_id in injected_node_ids:
            removed_nodes += 1
            continue
        keep_nodes.append(n)
    graph.nodes = keep_nodes

    # Mark indices dirty if the graph maintains any
    if hasattr(graph, "_indices_dirty"):
        graph._indices_dirty = True

    return {"nodes": removed_nodes, "edges": removed_edges}


def apply_override_reversal_policy(graph) -> Dict[str, int]:
    """Walk every node with ``_aux_overrides`` and apply the Hybrid-C
    volatile-save policy per-attribute:

    * If ``current value == aux_value`` → restore ``original`` value
      (the user never re-edited this attribute after the aux applied).
    * If ``current value != aux_value`` → keep the current value
      (the user re-edited manually after the aux) and drop the
      override entry; the attribute becomes graph-native going
      forward.

    Returns ``{"reverted": R, "kept": K, "unseen": U}`` where
    ``R`` is the number of attributes rolled back to their pre-aux
    value, ``K`` is the number kept because the user re-edited,
    ``U`` is the number of entries whose ``aux_value`` was never
    frozen (injector didn't call :func:`freeze_aux_value`); for
    those we conservatively **keep the current value**.

    This mutates ``graph`` in place (removes ``_aux_overrides`` on
    each node after processing, since the policy is applied once
    per save).
    """
    reverted = 0
    kept = 0
    unseen = 0
    for n in graph.nodes:
        attrs = getattr(n, "attributes", None) or {}
        overrides = attrs.get("_aux_overrides")
        if not overrides:
            continue
        for attr_name, record in list(overrides.items()):
            if "aux_value" not in record:
                # Injector didn't freeze → assume current value is
                # user-owned. Keep current, drop the entry.
                unseen += 1
                continue
            current = _read_attr(n, attr_name)
            if current == record["aux_value"]:
                # Policy: revert to pre-aux value
                _write_attr(n, attr_name, record["original"])
                reverted += 1
            else:
                # User edited after aux → keep current
                kept += 1
        # Clear the whole _aux_overrides for this node (the policy
        # has been applied; on re-inject the auxiliary will record
        # new overrides).
        del attrs["_aux_overrides"]
    return {"reverted": reverted, "kept": kept, "unseen": unseen}


def clear_aux_tags(graph) -> Dict[str, int]:
    """Drop all ``injected_by`` tags and ``_aux_overrides`` from
    every node and edge in ``graph``. Used by the **bake** path to
    promote the enrichment layer to graph-native.

    Returns ``{"injected_cleared": N, "overrides_cleared": M}``.
    """
    injected_cleared = 0
    overrides_cleared = 0

    for n in graph.nodes:
        attrs = getattr(n, "attributes", None)
        if not attrs:
            continue
        if attrs.pop("injected_by", None) is not None:
            injected_cleared += 1
        if attrs.pop("_aux_overrides", None) is not None:
            overrides_cleared += 1

    for e in graph.edges:
        attrs = getattr(e, "attributes", None)
        if not attrs:
            continue
        if attrs.pop("injected_by", None) is not None:
            injected_cleared += 1

    return {"injected_cleared": injected_cleared,
            "overrides_cleared": overrides_cleared}


# ---------------------------------------------------------------------------
# Orphan reporting helper
# ---------------------------------------------------------------------------

def push_orphan(graph, injector_id: str, key_id: str, payload: dict) -> None:
    """Record that an auxiliary row with key ``key_id`` could not be
    attached to any host node in the graph. Orphans live under
    ``graph.attributes['aux_orphans']`` as a list of dicts
    ``{"injector", "key_id", "payload"}``.

    The UI layer (EMtools) can render these per-auxiliary and offer a
    "create host node" action.
    """
    attrs = getattr(graph, "attributes", None)
    if attrs is None:
        return
    orphans = attrs.setdefault("aux_orphans", [])
    orphans.append({
        "injector": injector_id,
        "key_id": key_id,
        "payload": dict(payload or {}),
    })


def iter_orphans(graph, injector_id: Optional[str] = None) -> Iterable[dict]:
    """Yield orphan entries in ``graph.attributes['aux_orphans']``.
    When ``injector_id`` is provided, only entries matching that
    injector are yielded.
    """
    attrs = getattr(graph, "attributes", None) or {}
    for entry in attrs.get("aux_orphans", []) or []:
        if injector_id is not None and entry.get("injector") != injector_id:
            continue
        yield entry


def clear_orphans(graph, injector_id: Optional[str] = None) -> int:
    """Drop orphan entries. Returns how many were removed.

    With ``injector_id``: only entries for that injector (used when
    an auxiliary is unregistered). Without: clears the whole list
    (used by the bake path).
    """
    attrs = getattr(graph, "attributes", None)
    if attrs is None or not attrs.get("aux_orphans"):
        return 0
    if injector_id is None:
        n = len(attrs["aux_orphans"])
        attrs["aux_orphans"] = []
        return n
    kept = [e for e in attrs["aux_orphans"] if e.get("injector") != injector_id]
    removed = len(attrs["aux_orphans"]) - len(kept)
    attrs["aux_orphans"] = kept
    return removed


# ---------------------------------------------------------------------------
# Attribute accessor utilities
# ---------------------------------------------------------------------------
#
# Host-node attributes live in two places in s3Dgraphy: as direct
# Python attributes on the node object (``node.description``,
# ``node.name``, ``node.url`` …) and as entries in the
# ``node.attributes`` dict (``node.attributes['author_name']`` …).
# The ``record_attribute_override`` / ``apply_override_reversal_policy``
# pair must handle both. These helpers normalise access: if the
# attribute name is a top-level Python attribute on the node we
# read/write via getattr/setattr; otherwise we fall back to the
# attributes dict.

def _read_attr(node, name: str) -> Any:
    if name in ("_aux_overrides", "injected_by"):
        return None  # bookkeeping keys are never targets
    # Prefer a direct Python attribute when the node exposes it.
    if hasattr(node, name) and name not in ("attributes",):
        return getattr(node, name)
    attrs = getattr(node, "attributes", None) or {}
    return attrs.get(name)


def _write_attr(node, name: str, value: Any) -> None:
    if name in ("_aux_overrides", "injected_by"):
        return
    if hasattr(node, name) and name not in ("attributes",):
        try:
            setattr(node, name, value)
            return
        except Exception:
            pass
    attrs = getattr(node, "attributes", None)
    if attrs is None:
        try:
            node.attributes = {}
        except Exception:
            return
        attrs = node.attributes
    attrs[name] = value


# Public sentinel
MISSING_SENTINEL = _MISSING
