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
    """First node connected via ``edge_type`` matching ``target_cls_name``
    (or any of its superclasses), or None.
    """
    for t in _all_connected_targets(graph, node, edge_type, target_cls_name):
        return t
    return None


def _all_connected_targets(graph, node, edge_type, target_cls_name):
    """All nodes connected via ``edge_type`` matching ``target_cls_name``
    (or any of its superclasses). Yields in stable edge order.
    """
    try:
        edges = graph.get_connected_edges(node.node_id)
    except Exception:
        return
    for edge in edges:
        if getattr(edge, "edge_type", None) != edge_type or edge.edge_source != node.node_id:
            continue
        target = graph.find_node_by_id(edge.edge_target)
        if target is None:
            continue
        for base in type(target).__mro__:
            if base.__name__ == target_cls_name:
                yield target
                break


# Users of the yEd palette (1.5 dev9+ convention) store a short code as the
# AuthorNode name (e.g. ``A.01``) and the full human data (name, surname,
# ORCID) in the description. Keeping the description as the display value
# matches what the user wants to see in every panel.

def _format_author(author_node):
    """Stable display string for an AuthorNode/AuthorAINode.

    Precedence:
      1. ``description`` — the human-readable content filled in yEd
         (e.g. ``Giulia Rossi, ORCID:0000-...``). This is the canonical
         display according to the 1.5 dev9 palette convention.
      2. ``data["name"] + data["surname"]`` — populated by the legacy
         AuthorNode constructor when explicit first/last names are set.
      3. ``node.name`` — the short code (``A.01``, ``AI.01``) as last
         resort, so at least the identifier appears in the UI.
    """
    if author_node is None:
        return None

    description = (getattr(author_node, "description", "") or "").strip()
    if description:
        return description

    data = getattr(author_node, "data", {}) or {}
    name = data.get("name")
    surname = data.get("surname")
    # Skip sentinel defaults from the legacy constructor
    if name and name != "noname" and surname and surname != "nosurname":
        return f"{name} {surname}".strip()
    if name and name != "noname":
        return name
    if surname and surname != "nosurname":
        return surname

    return getattr(author_node, "name", None)


_AUTHOR_SEPARATOR = " ; "


def _collect_authors(graph, origin, edge_type="has_author"):
    """Return the joined display string for all AuthorNodes reachable from
    ``origin`` through ``edge_type``. Returns None if there are none.

    Multi-author handling: authors are joined with ``_AUTHOR_SEPARATOR``.
    Duplicate display strings are deduplicated while preserving order.
    """
    seen = set()
    parts = []
    for target in _all_connected_targets(graph, origin, edge_type, "AuthorNode"):
        text = _format_author(target)
        if not text or text in seen:
            continue
        seen.add(text)
        parts.append(text)
    if not parts:
        return None
    return _AUTHOR_SEPARATOR.join(parts)


def _author_node_level(graph, node):
    """Follow has_author edges from the node; join multiple authors."""
    if hasattr(node, "attributes") and node.attributes.get("author"):
        return node.attributes["author"]
    return _collect_authors(graph, node)


def _author_swimlane_level(graph, epoch):
    """Follow has_author edges from the EpochNode; join multiple authors."""
    attrs = getattr(epoch, "attributes", {}) or {}
    if attrs.get("author"):
        return attrs["author"]
    return _collect_authors(graph, epoch)


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
