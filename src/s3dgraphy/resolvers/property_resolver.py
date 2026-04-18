# s3dgraphy/resolvers/property_resolver.py
"""Generic 3-level property resolver (DP-32 Layer A)."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


def _noop_node(graph, node):
    return None


def _noop_swimlane(graph, epoch_node):
    return None


def _noop_graph(graph):
    return None


@dataclass
class PropagationRule:
    """Declarative description of how to resolve a propagative property.

    The resolver walks three levels and returns the first non-null value:

    1. **node**: ``node_getter(graph, node)``
    2. **swimlane**: for every EpochNode connected via ``has_first_epoch`` or
       ``survive_in_epoch``, call ``swimlane_getter(graph, epoch)``; if
       ``swimlane_aggregate`` is provided, it is applied to the list of
       non-null values (e.g. ``min`` or ``max``). Otherwise the first
       non-null value wins.
    3. **graph**: ``graph_getter(graph)``

    Any getter that returns ``None`` signals "no value at this level" and
    delegates to the next one. A getter may raise to signal a hard error.
    """

    id: str
    #: Optional human-readable label (used in warnings and debug output).
    label: str = ""
    node_getter: Callable[[Any, Any], Any] = field(default=_noop_node)
    swimlane_getter: Callable[[Any, Any], Any] = field(default=_noop_swimlane)
    graph_getter: Callable[[Any], Any] = field(default=_noop_graph)
    #: If set, applied to the list of non-null swimlane values.
    #: Typical values: ``min`` for start dates, ``max`` for end dates,
    #: or a custom combiner. When ``None``, the first non-null value wins.
    swimlane_aggregate: Optional[Callable[[List[Any]], Any]] = None


# ---------------------------------------------------------------------------
# Core resolve() API
# ---------------------------------------------------------------------------

def _iter_connected_epochs(graph, node):
    """All EpochNodes a node belongs to (has_first_epoch + survive_in_epoch).

    Returns an empty list if the graph has no such edges or the node has no
    epoch associations.
    """
    epochs: List[Any] = []
    for edge_type in ("has_first_epoch", "survive_in_epoch"):
        try:
            epochs.extend(graph.get_connected_epoch_nodes_list_by_edge_type(node, edge_type))
        except Exception:
            # Defensive: a graph without epochs or an unexpected API shape
            # should not break the resolver.
            continue
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for e in epochs:
        eid = getattr(e, "node_id", id(e))
        if eid in seen:
            continue
        seen.add(eid)
        unique.append(e)
    return unique


def resolve(graph, node, rule: PropagationRule, default=None):
    """Return the resolved value for ``node`` following ``rule``.

    Falls back to ``default`` if no level yields a non-null value.
    """
    value, _source = resolve_with_source(graph, node, rule, default=default)
    return value


def resolve_with_source(graph, node, rule: PropagationRule,
                        default=None) -> Tuple[Any, Optional[str]]:
    """Like :func:`resolve`, but also returns the source level.

    Returns a ``(value, source)`` tuple where ``source`` is one of
    ``"node"``, ``"swimlane"``, ``"graph"`` or ``None`` (when the default was
    used).
    """
    # --- node level ---
    v = rule.node_getter(graph, node)
    if v is not None:
        return v, "node"

    # --- swimlane level ---
    epochs = _iter_connected_epochs(graph, node)
    if epochs:
        if rule.swimlane_aggregate is not None:
            collected = [rule.swimlane_getter(graph, e) for e in epochs]
            collected = [x for x in collected if x is not None]
            if collected:
                agg = rule.swimlane_aggregate(collected)
                if agg is not None:
                    return agg, "swimlane"
        else:
            for e in epochs:
                v = rule.swimlane_getter(graph, e)
                if v is not None:
                    return v, "swimlane"

    # --- graph level ---
    v = rule.graph_getter(graph)
    if v is not None:
        return v, "graph"

    return default, None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: Dict[str, PropagationRule] = {}


def register_rule(rule: PropagationRule) -> None:
    """Register a rule. Replaces any existing rule with the same id."""
    if not rule.id:
        raise ValueError("PropagationRule.id must be a non-empty string")
    _registry[rule.id] = rule


def unregister_rule(rule_id: str) -> None:
    """Remove a rule from the registry (silent if absent)."""
    _registry.pop(rule_id, None)


def get_rule(rule_id: str) -> PropagationRule:
    """Fetch a registered rule by id. Raises KeyError if not found."""
    try:
        return _registry[rule_id]
    except KeyError:
        raise KeyError(
            f"No PropagationRule registered with id='{rule_id}'. "
            f"Known: {sorted(_registry)}"
        )


def list_rules() -> List[str]:
    """Return the ids of all registered rules, sorted."""
    return sorted(_registry)
