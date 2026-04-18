# s3dgraphy/resolvers/builtin_rules.py
"""Built-in PropagationRules registered at import time.

- ``chronology_start`` / ``chronology_end``: feed Layer B (TPQ/TAQ closure)
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


def _chronology_start_node(graph, node):
    return _node_temporal_property(graph, node, "absolute_start_date")


def _chronology_end_node(graph, node):
    return _node_temporal_property(graph, node, "absolute_end_date")


def _epoch_start(graph, epoch):
    val = getattr(epoch, "start_time", None)
    return float(val) if val is not None else None


def _epoch_end(graph, epoch):
    val = getattr(epoch, "end_time", None)
    return float(val) if val is not None else None


CHRONOLOGY_START_RULE = PropagationRule(
    id="chronology_start",
    label="Chronology — start",
    node_getter=_chronology_start_node,
    swimlane_getter=_epoch_start,
    swimlane_aggregate=min,   # earliest start across all connected epochs
    # No graph-level default for chronology today.
)


CHRONOLOGY_END_RULE = PropagationRule(
    id="chronology_end",
    label="Chronology — end",
    node_getter=_chronology_end_node,
    swimlane_getter=_epoch_end,
    swimlane_aggregate=max,   # latest end across all connected epochs
)


# ---------------------------------------------------------------------------
# Author — stub ready for DP-51. Node/swimlane getters are inert for now.
# ---------------------------------------------------------------------------

def _author_node_level(graph, node):
    # Will be wired to has_author edges / AuthorNode when DP-51 lands in yEd.
    # Until then, a node.attributes override is honored if present.
    return node.attributes.get("author") if hasattr(node, "attributes") else None


def _author_swimlane_level(graph, epoch):
    # Will read from the Swimlane Paradata Node Group (DP-19). For now, honor
    # an explicit attribute if an importer already puts one there.
    return getattr(epoch, "attributes", {}).get("author")


def _author_graph_level(graph):
    """Canvas-header author from DP-40.

    Composes ``author_name`` + ``author_surname`` when both are present,
    otherwise returns whichever is available. ``None`` if neither is set.
    """
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
# Register on import
# ---------------------------------------------------------------------------

for _r in (CHRONOLOGY_START_RULE, CHRONOLOGY_END_RULE, AUTHOR_RULE):
    register_rule(_r)
