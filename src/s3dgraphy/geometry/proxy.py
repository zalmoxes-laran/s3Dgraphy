"""`create_geometry_proxy` — one proxy, as a property with its provenance.

Same discipline as `annotation/paradata.py`, and for the same reasons:
deterministic `uuid5` ids so a re-send converges instead of duplicating, and an
edge guard that refuses to write a relation nobody can name rather than letting
`add_edge` degrade one to `generic_connection`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..graph import Graph
from ..nodes.combiner_node import CombinerNode
from ..nodes.extractor_node import ExtractorNode
from ..nodes.property_node import PropertyNode
from ..nodes.semantic_shape_node import SemanticShapeNode
from ..nodes.stratigraphic_node import StratigraphicNode

#: Frozen namespace for this module's deterministic ids.
_GEOM_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://w3id.org/em/geometry")

#: The qualia type. Registered in em_qualia_types.json (spatial), which is where
#: its CIDOC mapping lives — not here.
GEOMETRY_PROPERTY_TYPE = "geometry"

_EDGE_HAS_PROPERTY = "has_property"
_EDGE_HAS_SEMANTIC_SHAPE = "has_semantic_shape"
_EDGE_HAS_DATA_PROVENANCE = "has_data_provenance"
_EDGE_EXTRACTED_FROM = "extracted_from"
_EDGE_COMBINES = "combines"


@dataclass
class GeometryProxyResult:
    """The ids of the proxy chain, and what did not line up."""

    property_id: str
    shape_id: str
    unit_id: str
    extractor_ids: List[str] = field(default_factory=list)
    combiner_id: Optional[str] = None
    edge_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "property_id": self.property_id,
            "shape_id": self.shape_id,
            "unit_id": self.unit_id,
            "extractor_ids": list(self.extractor_ids),
            "combiner_id": self.combiner_id,
            "edge_ids": list(self.edge_ids),
            "warnings": list(self.warnings),
            "created": self.created,
        }


def _stable_id(key: str) -> str:
    return str(uuid.uuid5(_GEOM_NAMESPACE, key))


def _shape_key(shape: Dict[str, Any]) -> str:
    """The identity of a PAYLOAD: what geometry it carries.

    A `.glb` is identified by its url; inline numbers by the numbers. Two calls
    with the same hulls therefore land on the same SemanticShape instead of
    piling up copies of the same volume.
    """
    url = (shape.get("url") or "").strip()
    if url:
        return f"url|{url}"
    convex = shape.get("convexshapes") or []
    spheres = shape.get("spheres") or []
    return "inline|" + repr([[round(float(v), 6) for v in part] for part in convex]) \
           + "|" + repr([[round(float(v), 6) for v in s] for s in spheres])


def _ensure_edge(graph: Graph, source_id: str, target_id: str, edge_type: str,
                 result: GeometryProxyResult) -> None:
    """One edge, or a warning — never a `generic_connection`. See the twin of
    this function in `annotation/paradata.py` for the reasoning."""
    source = graph.find_node_by_id(source_id)
    target = graph.find_node_by_id(target_id)
    if source is None or target is None:
        result.warnings.append(
            f"geometry proxy: cannot create '{edge_type}' — an endpoint is missing")
        return
    if not graph.validate_connection(source.node_type, target.node_type, edge_type):
        result.warnings.append(
            f"geometry proxy: '{edge_type}' is not allowed from "
            f"{type(source).__name__} to {type(target).__name__}; the edge was "
            f"NOT created")
        return
    edge_id = _stable_id(f"edge|{source_id}|{edge_type}|{target_id}")
    result.edge_ids.append(edge_id)
    if graph.find_edge_by_id(edge_id) is not None:
        return
    graph.add_edge(edge_id, source_id, target_id, edge_type)
    result.created = True


def create_geometry_proxy(
    graph: Graph,
    unit_id: str,
    shape: Dict[str, Any],
    extractor_sources: Optional[Sequence[str]] = None,
    author: Optional[str] = None,
    name: Optional[str] = None,
) -> GeometryProxyResult:
    """Build the geometry proxy of a unit: a property, its payload, its sources.

    Args:
        graph: the graph to write into.
        unit_id: the US/USV the geometry belongs to.
        shape: the payload — ``{"url": "...glb"}`` or
            ``{"convexshapes": [[x,y,z, …], …], "spheres": [[x,y,z,r], …]}``.
        extractor_sources: the ids this geometry was read FROM — a Document, or
            an AnnotationRegion (a 2D annotation, once spatialised, is geometric
            evidence). One source → one extractor; several → several extractors
            joined by a combiner, which is what "synthesised from two sources"
            means in EM and needs no new mechanism.
        author: recorded as `data.author` on the created nodes.
        name: the property's label; defaults to "geometry".

    Returns:
        :class:`GeometryProxyResult`.

    Raises:
        ValueError: if `shape` carries no geometry at all. A proxy with no
            payload is not a proxy — and writing an empty SemanticShape would put
            a shape in the graph that claims a volume nobody described.
    """
    if not isinstance(shape, dict):
        raise ValueError(f"shape must be a dict, got {type(shape).__name__}")
    if not (shape.get("url") or shape.get("convexshapes") or shape.get("spheres")):
        raise ValueError(
            "a geometry proxy needs a payload: a url (.glb) or convexshapes/spheres")

    shape_id = _stable_id(f"shape|{_shape_key(shape)}")
    # The PROPERTY is identified by the unit it belongs to and the payload it
    # carries: re-sending the same geometry for the same unit is the same
    # property, while a different hull is a different assertion about the unit.
    property_id = _stable_id(f"geometry|{unit_id}|{shape_id}")

    result = GeometryProxyResult(property_id=property_id, shape_id=shape_id,
                                 unit_id=unit_id)

    unit = graph.find_node_by_id(unit_id)
    if unit is None:
        result.warnings.append(
            f"geometry proxy: unit '{unit_id}' is not in the graph; the property "
            f"and its payload are created but not attached to a unit")
    elif not isinstance(unit, StratigraphicNode):
        result.warnings.append(
            f"geometry proxy: '{unit_id}' is a {type(unit).__name__}, not a "
            f"stratigraphic unit; a geometry belongs to a unit, so has_property "
            f"was not created")

    # ── the payload ──────────────────────────────────────────────────────────
    if graph.find_node_by_id(shape_id) is None:
        node = SemanticShapeNode(
            node_id=shape_id,
            name=name or f"{unit_id} geometry",
            # `type` is SemanticShape's own enum, and 'proxy' is exactly what
            # this payload is — the word now names the ROLE of the carrier, not
            # a standalone node kind (see the datamodel's re-read of the field).
            type="proxy",
            url=str(shape.get("url") or ""),
            convexshapes=[list(part) for part in (shape.get("convexshapes") or [])],
            spheres=[list(s) for s in (shape.get("spheres") or [])],
        )
        if author:
            node.data["author"] = author
        graph.add_node(node)
        result.created = True

    # ── the property ─────────────────────────────────────────────────────────
    if graph.find_node_by_id(property_id) is None:
        prop = PropertyNode(
            node_id=property_id,
            name=name or GEOMETRY_PROPERTY_TYPE,
            # The value is a REFERENCE, not the numbers: the payload lives in the
            # SemanticShape, and copying it into the value would be a second copy
            # of the geometry free to drift from the first.
            value=shape_id,
            property_type=GEOMETRY_PROPERTY_TYPE,
        )
        if author:
            prop.data["author"] = author
        graph.add_node(prop)
        result.created = True

    _ensure_edge(graph, property_id, shape_id, _EDGE_HAS_SEMANTIC_SHAPE, result)
    if unit is not None and isinstance(unit, StratigraphicNode):
        _ensure_edge(graph, unit_id, property_id, _EDGE_HAS_PROPERTY, result)

    # ── the provenance: the ordinary chain, not a special case ───────────────
    sources = [s for s in (extractor_sources or []) if s]
    for source_id in sources:
        if graph.find_node_by_id(source_id) is None:
            result.warnings.append(
                f"geometry proxy: source '{source_id}' is not in the graph; no "
                f"extractor was created for it")
            continue
        extractor_id = _stable_id(f"extractor|{property_id}|{source_id}")
        if graph.find_node_by_id(extractor_id) is None:
            extractor = ExtractorNode(
                node_id=extractor_id,
                name=f"geometry from {getattr(graph.find_node_by_id(source_id), 'name', source_id)}",
                description="geometric evidence read from a source",
            )
            if author:
                extractor.data["author"] = author
            graph.add_node(extractor)
            result.created = True
        _ensure_edge(graph, extractor_id, source_id, _EDGE_EXTRACTED_FROM, result)
        result.extractor_ids.append(extractor_id)

    if len(result.extractor_ids) > 1:
        # More than one source means somebody decided how they combine — that
        # decision is the CombinerNode, and the property hangs off it. With a
        # single source there is nothing to combine, so no combiner is minted:
        # an inference node standing between one extractor and one property
        # would assert a reasoning step nobody performed.
        combiner_id = _stable_id(f"combiner|{property_id}")
        if graph.find_node_by_id(combiner_id) is None:
            combiner = CombinerNode(
                node_id=combiner_id,
                name=f"{name or 'geometry'} synthesis",
                description="synthesis of several geometric readings",
            )
            if author:
                combiner.data["author"] = author
            graph.add_node(combiner)
            result.created = True
        result.combiner_id = combiner_id
        for extractor_id in result.extractor_ids:
            _ensure_edge(graph, combiner_id, extractor_id, _EDGE_COMBINES, result)
        _ensure_edge(graph, property_id, combiner_id, _EDGE_HAS_DATA_PROVENANCE,
                     result)
    elif result.extractor_ids:
        _ensure_edge(graph, property_id, result.extractor_ids[0],
                     _EDGE_HAS_DATA_PROVENANCE, result)

    return result
