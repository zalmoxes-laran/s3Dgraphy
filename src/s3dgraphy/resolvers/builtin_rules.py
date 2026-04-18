# s3dgraphy/resolvers/builtin_rules.py
"""Built-in PropagationRules registered at import time.

- ``absolute_time_start`` / ``absolute_time_end``: feed Layer B (TPQ/TAQ closure)
  and reproduce the behavior of the previous hardcoded
  ``Graph._calculate_base_chronology``.
- ``author``: declaration of the authorship property. Node-level and
  swimlane-level getters return ``None`` until DP-51 formalizes AuthorNode
  and has_author edges in yEd. Graph-level already works today: the Canvas
  Header loader (DP-40) populates ``graph.attributes['author_name' | ...]``.
"""

from .property_resolver import PropagationRule, register_rule


# ---------------------------------------------------------------------------
# Chronology — Layer A seed getters
# ---------------------------------------------------------------------------

def _node_temporal_property(graph, node, property_type):
    """Find a PropertyNode of the given type attached to ``node``.

    Mirrors Graph._find_temporal_property: matches by ``property_type`` OR by
    node name, and falls back to ``description`` when ``value`` is empty
    (GraphML imports sometimes put the numeric value in description).
    """
    from ..nodes.property_node import PropertyNode  # local import breaks cycle

    try:
        edges = graph.get_connected_edges(node.node_id)
    except Exception:
        return None

    for edge in edges:
        if edge.edge_type != "has_property" or edge.edge_source != node.node_id:
            continue
        prop = graph.find_node_by_id(edge.edge_target)
        if not isinstance(prop, PropertyNode):
            continue
        if prop.property_type != property_type and prop.name != property_type:
            continue

        raw = prop.value
        if (raw is None or raw == "") and prop.description:
            # GraphML-style storage in description
            try:
                float(prop.description)
                raw = prop.description
            except (ValueError, TypeError):
                raw = None

        if raw is None or raw == "":
            continue
        try:
            return float(raw)
        except (ValueError, TypeError):
            continue
    return None


def _absolute_time_start_node(graph, node):
    return _node_temporal_property(graph, node, "absolute_time_start")


def _absolute_time_end_node(graph, node):
    return _node_temporal_property(graph, node, "absolute_time_end")


def _epoch_start(graph, epoch):
    val = getattr(epoch, "start_time", None)
    return float(val) if val is not None else None


def _epoch_end(graph, epoch):
    val = getattr(epoch, "end_time", None)
    return float(val) if val is not None else None


CHRONOLOGY_START_RULE = PropagationRule(
    id="absolute_time_start",
    label="Chronology — start",
    node_getter=_absolute_time_start_node,
    swimlane_getter=_epoch_start,
    swimlane_aggregate=min,   # earliest start across all connected epochs
    # No graph-level default for chronology today.
)


CHRONOLOGY_END_RULE = PropagationRule(
    id="absolute_time_end",
    label="Chronology — end",
    node_getter=_absolute_time_end_node,
    swimlane_getter=_epoch_end,
    swimlane_aggregate=max,   # latest end across all connected epochs
)


# ---------------------------------------------------------------------------
# Author — stub ready for DP-51. Node/swimlane getters are inert for now.
# ---------------------------------------------------------------------------

def _first_connected_target(graph, node, edge_type, target_cls_name):
    """Return the first node connected via ``edge_type`` whose class name
    (or node_type) matches ``target_cls_name``, or None. Tolerates missing
    get_connected_edges.
    """
    try:
        edges = graph.get_connected_edges(node.node_id)
    except Exception:
        return None
    for edge in edges:
        if getattr(edge, "edge_type", None) != edge_type or edge.edge_source != node.node_id:
            continue
        target = graph.find_node_by_id(edge.edge_target)
        if target is None:
            continue
        if target.__class__.__name__ == target_cls_name:
            return target
        # Accept subclasses (AuthorAINode inherits from AuthorNode)
        for base in type(target).__mro__:
            if base.__name__ == target_cls_name:
                return target
    return None


def _format_author(author_node):
    """Stable display string for an AuthorNode/AuthorAINode."""
    if author_node is None:
        return None
    data = getattr(author_node, "data", {}) or {}
    name = data.get("name")
    surname = data.get("surname")
    # Skip sentinel defaults (noname/nosurname) inherited from pre-existing code
    if name and name != "noname" and surname and surname != "nosurname":
        return f"{name} {surname}".strip()
    if name and name != "noname":
        return name
    if surname and surname != "nosurname":
        return surname
    # Fallback to node display name
    return getattr(author_node, "name", None)


def _author_node_level(graph, node):
    """Follow a has_author edge from the node. Honors any node.attributes
    override if importers already populated it (legacy).
    """
    if hasattr(node, "attributes") and node.attributes.get("author"):
        return node.attributes["author"]
    author = _first_connected_target(graph, node, "has_author", "AuthorNode")
    return _format_author(author)


def _author_swimlane_level(graph, epoch):
    """Follow a has_author edge from the EpochNode (swimlane-level). DP-19
    will emit these edges when a Swimlane Paradata Node Group contains an
    AuthorNode.
    """
    attrs = getattr(epoch, "attributes", {}) or {}
    if attrs.get("author"):
        return attrs["author"]
    author = _first_connected_target(graph, epoch, "has_author", "AuthorNode")
    return _format_author(author)


def _author_graph_level(graph):
    """Canvas-header author from DP-40. Composes author_name+surname."""
    attrs = getattr(graph, "attributes", {}) or {}
    name = attrs.get("author_name")
    surname = attrs.get("author_surname")
    if name and surname:
        return f"{name} {surname}".strip()
    return name or surname or None


AUTHOR_RULE = PropagationRule(
    id="author",
    label="Author",
    node_getter=_author_node_level,
    swimlane_getter=_author_swimlane_level,
    graph_getter=_author_graph_level,
)


# ---------------------------------------------------------------------------
# License — node-level via has_license, graph-level legacy via canvas header
# ---------------------------------------------------------------------------

def _format_license(license_node):
    if license_node is None:
        return None
    data = getattr(license_node, "data", {}) or {}
    t = data.get("license_type")
    url = data.get("url")
    if t and url:
        return f"{t} ({url})"
    return t or url or getattr(license_node, "name", None)


def _license_node_level(graph, node):
    if hasattr(node, "attributes") and node.attributes.get("license"):
        return node.attributes["license"]
    return _format_license(_first_connected_target(graph, node, "has_license", "LicenseNode"))


def _license_swimlane_level(graph, epoch):
    attrs = getattr(epoch, "attributes", {}) or {}
    if attrs.get("license"):
        return attrs["license"]
    return _format_license(_first_connected_target(graph, epoch, "has_license", "LicenseNode"))


def _license_graph_level(graph):
    attrs = getattr(graph, "attributes", {}) or {}
    return attrs.get("license") or None


LICENSE_RULE = PropagationRule(
    id="license",
    label="License",
    node_getter=_license_node_level,
    swimlane_getter=_license_swimlane_level,
    graph_getter=_license_graph_level,
)


# ---------------------------------------------------------------------------
# Embargo — node-level via has_embargo (can be direct or chained via license)
# ---------------------------------------------------------------------------

def _format_embargo(embargo_node):
    if embargo_node is None:
        return None
    data = getattr(embargo_node, "data", {}) or {}
    start = data.get("embargo_start") or getattr(embargo_node, "embargo_start", None)
    end = data.get("embargo_end") or getattr(embargo_node, "embargo_end", None)
    reason = data.get("reason") or getattr(embargo_node, "reason", "")
    if start and end:
        return f"{start}..{end}" + (f" ({reason})" if reason else "")
    if start:
        return f"from {start}" + (f" ({reason})" if reason else "")
    return getattr(embargo_node, "name", None)


def _embargo_node_level(graph, node):
    if hasattr(node, "attributes") and node.attributes.get("embargo"):
        return node.attributes["embargo"]
    return _format_embargo(_first_connected_target(graph, node, "has_embargo", "EmbargoNode"))


def _embargo_swimlane_level(graph, epoch):
    attrs = getattr(epoch, "attributes", {}) or {}
    if attrs.get("embargo"):
        return attrs["embargo"]
    return _format_embargo(_first_connected_target(graph, epoch, "has_embargo", "EmbargoNode"))


def _embargo_graph_level(graph):
    attrs = getattr(graph, "attributes", {}) or {}
    return attrs.get("embargo") or None


EMBARGO_RULE = PropagationRule(
    id="embargo",
    label="Embargo",
    node_getter=_embargo_node_level,
    swimlane_getter=_embargo_swimlane_level,
    graph_getter=_embargo_graph_level,
)


# ---------------------------------------------------------------------------
# Register on import
# ---------------------------------------------------------------------------

for _r in (CHRONOLOGY_START_RULE, CHRONOLOGY_END_RULE,
           AUTHOR_RULE, LICENSE_RULE, EMBARGO_RULE):
    register_rule(_r)
