"""One-shot legacy migration: proxy-as-node → proxy-as-property.

Until EM 1.6.2 the proxy of a unit was a bare ``SemanticShapeNode`` hanging off
the unit::

    US ──has_semantic_shape──▶ SemanticShape        (legacy)

From 1.6.2 the proxy is a ``PropertyNode(geometry)`` that CARRIES the shape as
its payload, so it inherits the paradata chain (see :mod:`s3dgraphy.geometry`)::

    US ──has_property──▶ Property(geometry) ──has_semantic_shape──▶ SemanticShape

This module rewrites graphs written in the old shape into the new one. It is the
twin, for geometry, of ``importer.emjson_importer._migrate_legacy_graph_scope``
(DP-65), and follows the same three rules:

  · it REWIRES the existing SemanticShape, it does not mint a new one — the
    payload node keeps its id, so nothing that already points at it is orphaned;
  · ids are deterministic (``uuid5``), so running the migration twice is a
    no-op, not a second property;
  · a legacy proxy is exactly a ``has_semantic_shape`` edge whose SOURCE is a
    stratigraphic unit. The NEW edge (property → shape) is a ``has_semantic_shape``
    too, but its source is a PropertyNode, so it is never mistaken for legacy.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from ..graph import Graph
from ..nodes.property_node import PropertyNode
from ..nodes.stratigraphic_node import StratigraphicNode

# Same namespace family as geometry/proxy.py, so a proxy that is later re-created
# through create_geometry_proxy and one that is migrated here do not collide by
# accident: the migration keys carry the word "migrated".
_GEOM_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://w3id.org/em/geometry")

_EDGE_HAS_PROPERTY = "has_property"
_EDGE_HAS_SEMANTIC_SHAPE = "has_semantic_shape"
GEOMETRY_PROPERTY_TYPE = "geometry"


def _stable_id(key: str) -> str:
    return str(uuid.uuid5(_GEOM_NAMESPACE, key))


def _is_legacy_proxy_edge(graph: Graph, edge) -> bool:
    """A `has_semantic_shape` edge straight from a stratigraphic unit."""
    if getattr(edge, "edge_type", None) != _EDGE_HAS_SEMANTIC_SHAPE:
        return False
    source = graph.find_node_by_id(edge.edge_source)
    return isinstance(source, StratigraphicNode)


def migrate_legacy_proxies(graph: Graph) -> Dict[str, Any]:
    """Rewrite legacy proxies (US → SemanticShape) as geometry properties.

    Returns a small report: how many were migrated, the property ids created,
    and any warnings. Idempotent — a graph already in the new shape yields
    ``migrated == 0``.
    """
    report: Dict[str, Any] = {"migrated": 0, "property_ids": [], "warnings": []}

    # Snapshot: we mutate graph.edges (remove the legacy edge) inside the loop.
    legacy_edges = [e for e in list(graph.edges) if _is_legacy_proxy_edge(graph, e)]

    for edge in legacy_edges:
        unit_id = edge.edge_source
        shape_id = edge.edge_target
        shape = graph.find_node_by_id(shape_id)
        if shape is None:
            report["warnings"].append(
                f"legacy proxy on '{unit_id}': its SemanticShape '{shape_id}' is "
                f"missing; edge left as-is")
            continue

        property_id = _stable_id(f"migrated-geometry|{unit_id}|{shape_id}")

        # The property: identified by unit + shape, so re-running lands on the
        # same node instead of piling up copies.
        if graph.find_node_by_id(property_id) is None:
            prop = PropertyNode(
                node_id=property_id,
                name=GEOMETRY_PROPERTY_TYPE,
                # value is a REFERENCE to the payload, exactly as create_geometry_proxy
                # does — the numbers stay in the SemanticShape, never a second copy.
                value=shape_id,
                property_type=GEOMETRY_PROPERTY_TYPE,
            )
            # carry the author forward if the shape had one, so provenance is not lost
            author = (getattr(shape, "data", {}) or {}).get("author")
            if author:
                prop.data["author"] = author
            graph.add_node(prop)

        # US ──has_property──▶ Property
        hp_id = _stable_id(f"edge|{unit_id}|{_EDGE_HAS_PROPERTY}|{property_id}")
        if graph.find_edge_by_id(hp_id) is None:
            graph.add_edge(hp_id, unit_id, property_id, _EDGE_HAS_PROPERTY)

        # Property ──has_semantic_shape──▶ SemanticShape
        hss_id = _stable_id(f"edge|{property_id}|{_EDGE_HAS_SEMANTIC_SHAPE}|{shape_id}")
        if graph.find_edge_by_id(hss_id) is None:
            graph.add_edge(hss_id, property_id, shape_id, _EDGE_HAS_SEMANTIC_SHAPE)

        # Drop the legacy US → SemanticShape edge: the shape now hangs off the
        # property, and leaving both would assert the proxy twice.
        graph.remove_edge(edge.edge_id)

        report["migrated"] += 1
        report["property_ids"].append(property_id)

    return report
