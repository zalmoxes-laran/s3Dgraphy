"""AnnotationRegionNode — a region in IMAGE space (2D annotator, semantics first).

Why a new node and not a `SemanticShapeNode`
--------------------------------------------
`SemanticShapeNode` is a proxy geometry in the **3D space of the scene**: convex
hulls and spheres in scene coordinates, projected as
`crmgeo:SP5_Geometric_Place_Expression` because it expresses WHERE a thing is.

An annotation region is a different kind of thing: it is a portion of a
**specific image** (a photograph, a plan, one page of a PDF), in the coordinate
system of that image. It says nothing about where anything is in the world — it
says "this part of this picture". Its CIDOC home is therefore
`crm:E36_Visual_Item`: a region of a visual item IS a visual item.

Putting both in one class would have meant one field set with two meanings and a
`kind` flag to tell them apart — and every reader would have to know which
meaning it was holding before it could do anything with the numbers.

Coordinates are NORMALISED to [0,1]
-----------------------------------
A region recorded in pixels is only readable next to the resolution it was drawn
at, and the same photograph is routinely re-exported at another size (a web
derivative, a thumbnail, a re-scan). Normalised coordinates survive that: they
are a statement about the picture, not about a file. It also makes the region
directly expressible as a W3C Media Fragment (`xywh=percent:…`), which is the
selector the RDF projection emits.
"""

from typing import Any, Dict, List, Optional

from .base_node import Node


class AnnotationRegionError(ValueError):
    """A region whose geometry cannot be read as a region."""


def _norm_pair(pair: Any, where: str) -> List[float]:
    """One [x, y] in [0,1], or raise. Clamping silently would move somebody's
    annotation without telling them; a bad region is a caller's bug."""
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        raise AnnotationRegionError(f"{where}: expected a [x, y] pair, got {pair!r}")
    out = []
    for value in pair:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AnnotationRegionError(f"{where}: {value!r} is not a number")
        if not (0.0 <= float(value) <= 1.0):
            raise AnnotationRegionError(
                f"{where}: {value} is outside [0,1] — image-space coordinates are "
                f"normalised, so a pixel value is a unit error, not a big region")
        out.append(float(value))
    return out


class AnnotationRegionNode(Node):
    """A region of one image (or one page), in normalised image coordinates.

    Attributes:
        node_type (str): ``"annotation_region"``.
        shape_kind (str): ``"rect"`` or ``"polygon"``. ``"mask"`` is phase 2 —
            declared in the datamodel, refused here, so nothing half-supports it.
        rect (list): ``[x, y, w, h]`` in [0,1] when ``shape_kind == "rect"``.
        points (list): ``[[x, y], …]`` in [0,1] when ``shape_kind == "polygon"``.
        page (int): page/frame index inside a multi-page or multi-image resource,
            0 for a plain single image. The collection abstraction the annotator
            iterates is 0-based, and so is this.
        resource_id (str): the image this region is on. The EDGE
            (``is_on_resource``) is the graph's statement; this field is the
            node's own copy of it, so a region is readable on its own — the same
            belt-and-braces the other nodes use for their anchors.
    """

    node_type = "annotation_region"

    SHAPE_KINDS = ("rect", "polygon")
    #: Declared, not implemented: a raster mask needs a payload (a PNG, an RLE)
    #: and a place to keep it, which is the resource layer's problem and a
    #: decision of its own. Refusing it is honest; accepting it and storing
    #: nothing would not be.
    FUTURE_SHAPE_KINDS = ("mask",)

    def __init__(self,
                 node_id: str,
                 name: str,
                 shape_kind: str = "rect",
                 rect: Optional[List[float]] = None,
                 points: Optional[List[List[float]]] = None,
                 page: int = 0,
                 resource_id: Optional[str] = None,
                 description: str = ""):
        super().__init__(node_id=node_id, name=name, description=description)

        if shape_kind in self.FUTURE_SHAPE_KINDS:
            raise AnnotationRegionError(
                f"shape_kind '{shape_kind}' is declared in the datamodel but not "
                f"implemented (phase 2); use one of {list(self.SHAPE_KINDS)}")
        if shape_kind not in self.SHAPE_KINDS:
            raise AnnotationRegionError(
                f"shape_kind must be one of {list(self.SHAPE_KINDS)}, got {shape_kind!r}")

        self.shape_kind = shape_kind
        self.rect: List[float] = []
        self.points: List[List[float]] = []

        if shape_kind == "rect":
            if rect is None:
                raise AnnotationRegionError("a rect region needs rect=[x, y, w, h]")
            if not isinstance(rect, (list, tuple)) or len(rect) != 4:
                raise AnnotationRegionError(
                    f"rect must be [x, y, w, h] in [0,1], got {rect!r}")
            x, y = _norm_pair([rect[0], rect[1]], "rect origin")
            w, h = _norm_pair([rect[2], rect[3]], "rect size")
            if w <= 0 or h <= 0:
                raise AnnotationRegionError(
                    "a rect region needs a positive width and height")
            if x + w > 1.0000001 or y + h > 1.0000001:
                raise AnnotationRegionError(
                    f"rect [{x}, {y}, {w}, {h}] runs off the image")
            self.rect = [x, y, w, h]
        else:
            if not points or not isinstance(points, (list, tuple)):
                raise AnnotationRegionError(
                    "a polygon region needs points=[[x, y], …]")
            if len(points) < 3:
                raise AnnotationRegionError(
                    f"a polygon needs at least 3 points, got {len(points)}")
            self.points = [_norm_pair(p, f"point {i}") for i, p in enumerate(points)]

        if isinstance(page, bool) or not isinstance(page, int) or page < 0:
            raise AnnotationRegionError(f"page must be a non-negative int, got {page!r}")
        self.page = page
        self.resource_id = resource_id

        self.data: Dict[str, Any] = {
            "shape_kind": self.shape_kind,
            "page": self.page,
        }
        if self.rect:
            self.data["rect"] = self.rect
        if self.points:
            self.data["points"] = self.points
        if self.resource_id:
            self.data["resource_id"] = self.resource_id

    # ── the selector: one geometry, one string, both ways ────────────────────
    #
    # The RDF projection carries the geometry as a SELECTOR, the way the W3C Web
    # Annotation model does — a Media Fragment for a rectangle, an SVG-style
    # point list for a polygon. One string, parseable, and standard enough that
    # a consumer outside EM can act on it without reading our datamodel.
    #
    # It is DERIVED, never stored twice: `selector()` writes it and
    # `from_selector()` reads it, so there is no second copy of the geometry to
    # drift from the first.

    def selector(self) -> str:
        """The geometry as a selector string (percent units, 6 decimals).

        Fixed precision on purpose: this string is what the round-trip compares,
        and `repr(float)` differences would show up as a projection that is not
        isomorphic with itself.
        """
        if self.shape_kind == "rect":
            x, y, w, h = self.rect
            return "xywh=percent:" + ",".join(f"{v * 100:.6f}" for v in (x, y, w, h))
        pts = " ".join(f"{x * 100:.6f},{y * 100:.6f}" for x, y in self.points)
        return f"polygon(percent:{pts})"

    @classmethod
    def parse_selector(cls, selector: str) -> Dict[str, Any]:
        """Selector string → ``{shape_kind, rect|points}``, or raise.

        The exact inverse of :meth:`selector`; anything else is not a region we
        wrote, and guessing at a foreign syntax would invent geometry.
        """
        text = (selector or "").strip()
        if text.startswith("xywh=percent:"):
            parts = text[len("xywh=percent:"):].split(",")
            if len(parts) != 4:
                raise AnnotationRegionError(f"malformed rect selector: {selector!r}")
            return {"shape_kind": "rect",
                    "rect": [float(p) / 100.0 for p in parts]}
        if text.startswith("polygon(percent:") and text.endswith(")"):
            body = text[len("polygon(percent:"):-1].strip()
            points = []
            for chunk in body.split():
                xy = chunk.split(",")
                if len(xy) != 2:
                    raise AnnotationRegionError(
                        f"malformed polygon point {chunk!r} in {selector!r}")
                points.append([float(xy[0]) / 100.0, float(xy[1]) / 100.0])
            if len(points) < 3:
                raise AnnotationRegionError(
                    f"polygon selector with {len(points)} points: {selector!r}")
            return {"shape_kind": "polygon", "points": points}
        raise AnnotationRegionError(f"unrecognised region selector: {selector!r}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            self.node_id: {
                "name": self.name,
                "type": self.node_type,
                "description": self.description,
                "data": self.data,
            }
        }
