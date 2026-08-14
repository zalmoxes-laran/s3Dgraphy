"""IIIF — the image layer as a PROJECTION of the graph.

The same two-tier arrangement as the RDF export, and it is the whole point of
adopting the standard rather than being adopted by it:

* **the authoring truth is the em.json** — an annotation is a node
  (`AnnotationRegionNode`), attached to the paradata chain that makes it a claim
  by somebody about something, versioned by the CRDT, queryable;
* **IIIF is the projection** — round-trippable, so anybody's viewer can read our
  images and our regions, and what they send back can come home.

What the standard gives us for free, and none of it is code we maintain:
**thumbnails** (a size request), **deep zoom** (tiles), **the crop of a region**
(a region request), and interoperability with every IIIF viewer there is. That is
why there is no thumbnail pipeline in this repository and there should never be
one.

**Nothing here is stored.** The image service is DERIVED from the asset — the
identifier is the asset's own sha256, because the object store is
content-addressed — and the manifest is built on demand. Writing the service URL
into the graph would pin a deployment's hostname into the authoring truth, and
the day the server moves, every study would carry a dead address.

This module is network-free on purpose: it computes URLs and documents. Fetching
`info.json` (the only way to learn an image's pixel size from outside) is the
caller's business — a library that made HTTP calls would be untestable and would
turn an offline project into a broken one.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .graph import Graph

#: The IIIF Image API version this projects to. 3 is what the manifests and the
#: current viewers speak; a server can keep 2 on for older clients without
#: anything here changing.
IMAGE_API_VERSION = 3
IMAGE_SERVICE_TYPE = "ImageService3"
IMAGE_SERVICE_PROFILE = "level2"

PRESENTATION_CONTEXT = "http://iiif.io/api/presentation/3/context.json"

#: Media types this layer treats as images. A model, a PDF or a point cloud has
#: no Image API service — asking for one would produce a URL that 404s, which is
#: worse than the honest absence of a service.
IMAGE_MEDIA_TYPES = ("image/jpeg", "image/png", "image/tiff", "image/jp2",
                     "image/gif", "image/webp", "image/x-tiff", "image/tif")

#: …and the resource-layer vocabulary that says the same thing without a media
#: type (SHELF1 resources predate `media_type`).
IMAGE_URL_TYPES = ("image", "Image")

#: The size, in pixels of the long edge, a card asks for. Small enough to be a
#: card, big enough for a retina screen — and it is a REQUEST, not a file we
#: generate and store.
THUMBNAIL_WIDTH = 400


# ── is this an image, and what is it called ─────────────────────────────────

def _data(node: Any) -> Dict[str, Any]:
    data = getattr(node, "data", None)
    return data if isinstance(data, dict) else {}


def is_image(resource: Any) -> bool:
    """Does this resource have pixels an Image API could serve?"""
    data = _data(resource)
    media = str(data.get("media_type") or "").lower()
    if media:
        return media in IMAGE_MEDIA_TYPES
    if str(data.get("url_type") or "") in IMAGE_URL_TYPES:
        return True
    url = str(data.get("url") or getattr(resource, "url", "") or "").lower()
    return url.rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "tif", "tiff", "jp2") \
        if "." in url else False


def image_identifier(resource: Any) -> Optional[str]:
    """The IIIF identifier of a resource: **its digest**, bare hex.

    Not a name we mint. The asset store is content-addressed, so the object's key
    already identifies exactly these pixels; reusing it means the image service
    needs no registry of its own, an identifier is verifiable, and two studies
    that reference the same photograph reference the same image.

    None when the resource carries no checksum — an image nobody hashed cannot be
    addressed by content, and inventing an id for it would produce a URL that
    resolves to nothing.
    """
    checksum = str(_data(resource).get("checksum") or "").strip()
    if not checksum:
        return None
    algorithm, _, digest = checksum.partition(":")
    if not digest:                      # a bare hex: legacy, still usable
        digest, algorithm = algorithm, "sha256"
    if algorithm.lower() != "sha256" or len(digest) != 64:
        return None
    return digest.lower()


def image_service(resource: Any, base: str) -> Optional[Dict[str, Any]]:
    """The Image API service block for a resource, or None.

    `base` is the Image API base of the deployment (`…/iiif/3`) — passed in,
    never stored: see the module docstring.
    """
    identifier = image_identifier(resource)
    if not identifier or not is_image(resource):
        return None
    return {"id": f"{base.rstrip('/')}/{identifier}",
            "type": IMAGE_SERVICE_TYPE,
            "profile": IMAGE_SERVICE_PROFILE}


def image_url(resource: Any, base: str, *, region: str = "full",
              size: str = "max", rotation: str = "0", quality: str = "default",
              fmt: str = "jpg") -> Optional[str]:
    """Any Image API request for this resource, spelled correctly.

    One function because the parameter ORDER is the part that gets written wrong
    by hand (`{region}/{size}/{rotation}/{quality}.{format}`), and because
    `full` as a SIZE is deprecated in Image API 3 — `max` is the spelling that
    works, and it is the default here rather than a thing to remember.
    """
    identifier = image_identifier(resource)
    if not identifier:
        return None
    return (f"{base.rstrip('/')}/{identifier}/{region}/{size}/{rotation}/"
            f"{quality}.{fmt}")


def thumbnail_url(resource: Any, base: str, width: int = THUMBNAIL_WIDTH
                  ) -> Optional[str]:
    """A thumbnail — which is a **size request**, not a file.

    `!w,h` (confine to a box) rather than `w,`: a thumbnail means "at most this
    big". Measured against Cantaloupe: any size ABOVE the source is a **400**,
    including the `^` upscale form — so `240,` on a 96-pixel image returns no
    picture at all, while `!240,240` returns the 96-pixel one, which is what a
    thumbnail wanted. The aspect ratio is kept either way.
    """
    box = int(width)
    return image_url(resource, base, size=f"!{box},{box}")


def region_url(resource: Any, region: Any, base: str, *, size: str = "max"
               ) -> Optional[str]:
    """The CROP of an annotated region, served by the image server.

    Normalised coordinates map straight onto IIIF's percentage region
    (`pct:x,y,w,h`) — so a region recorded in [0,1] can be delivered as an image
    **without anybody knowing the pixel dimensions**. That is the piece that
    makes an EM annotation instantly useful outside EM.

    A polygon has no IIIF region syntax; its bounding box is served instead, and
    the caller is not told a crop is a polygon — the shape stays in the graph.
    """
    box = bounding_box(region)
    if box is None:
        return None
    x, y, w, h = (v * 100 for v in box)
    return image_url(resource, base, size=size,
                     region=f"pct:{x:.6f},{y:.6f},{w:.6f},{h:.6f}")


def bounding_box(region: Any) -> Optional[Tuple[float, float, float, float]]:
    """`(x, y, w, h)` in [0,1] for a rect or a polygon, or None."""
    rect = getattr(region, "rect", None) or _data(region).get("rect")
    if rect and len(rect) == 4:
        return tuple(float(v) for v in rect)          # type: ignore[return-value]
    points = getattr(region, "points", None) or _data(region).get("points")
    if points:
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    return None


# ── pixel dimensions: known, or honestly absent ─────────────────────────────

def resource_size(resource: Any,
                  sizes: Optional[Dict[str, Sequence[int]]] = None
                  ) -> Optional[Tuple[int, int]]:
    """`(width, height)` in pixels, from the caller or from the graph.

    In that order: a caller that has just read `info.json` knows better than
    anything written down, and what is written down (`data.width`/`data.height`,
    recorded by the annotator when it loads an image) is what makes an offline
    manifest possible at all.

    None is a real answer and callers must handle it: **a size is not invented
    here**. A canvas with a made-up aspect ratio would stretch somebody's
    photograph and move every annotation on it.
    """
    node_id = getattr(resource, "node_id", None)
    if sizes and node_id in sizes:
        pair = sizes[node_id]
        return (int(pair[0]), int(pair[1]))
    data = _data(resource)
    width, height = data.get("width"), data.get("height")
    if isinstance(width, (int, float)) and isinstance(height, (int, float)) \
            and width > 0 and height > 0:
        return (int(width), int(height))
    return None


# ── W3C Web Annotation: the projection of a region, and its inverse ─────────
#
# The region in the graph is normalised [0,1]. The Web Annotation carries a
# SELECTOR, and which selector depends on what is known and what shape it is:
#
#   rect + pixel size known → FragmentSelector `xywh=<x>,<y>,<w>,<h>` (pixels),
#       because that is what every viewer implements;
#   rect + size unknown     → FragmentSelector `xywh=percent:…`, still standard
#       (Media Fragments), and exact — a manifest that cannot say the pixel size
#       can still say the region;
#   polygon                 → SvgSelector, the only standard way to express a
#       non-rectangle. Its coordinates are pixels, so it needs the size.
#
# The inverse reads all three back. Round-trip is pinned by a test, because a
# projection that cannot come home is an export, not an interoperability layer.

WEB_ANNOTATION_CONTEXT = "http://www.w3.org/ns/anno.jsonld"

#: How a region relates to what it points at. `identifying` is the honest term
#: for "this part of the picture is that thing" — the interpretation itself
#: lives in the PropertyNode the chain hangs off, not in the annotation body.
DEFAULT_MOTIVATION = "identifying"


def _fragment(box: Tuple[float, float, float, float],
              size: Optional[Tuple[int, int]]) -> str:
    x, y, w, h = box
    if size:
        width, height = size
        return (f"xywh={round(x * width)},{round(y * height)},"
                f"{round(w * width)},{round(h * height)}")
    return "xywh=percent:" + ",".join(f"{v * 100:.6f}" for v in (x, y, w, h))


def _svg_selector(points: Iterable[Sequence[float]],
                  size: Tuple[int, int]) -> Dict[str, str]:
    width, height = size
    coords = " ".join(f"{round(float(x) * width)},{round(float(y) * height)}"
                      for x, y in points)
    return {"type": "SvgSelector",
            "value": f'<svg xmlns="http://www.w3.org/2000/svg">'
                     f'<polygon points="{coords}"/></svg>'}


def region_to_web_annotation(region: Any, *, target: str,
                             size: Optional[Tuple[int, int]] = None,
                             annotation_id: Optional[str] = None,
                             body: Optional[Dict[str, Any]] = None,
                             motivation: str = DEFAULT_MOTIVATION
                             ) -> Dict[str, Any]:
    """One `AnnotationRegionNode` → one W3C Web Annotation.

    `target` is what the region is on — a IIIF canvas id in a manifest, or the
    image's own URL when the annotation travels alone.

    The annotation's **id is the region's node id**, unchanged. That is what
    makes the round trip meaningful and what lets somebody else's tool refer to
    our annotation and have us recognise it when it comes back.
    """
    node_id = str(annotation_id or getattr(region, "node_id", "") or "")
    shape_kind = getattr(region, "shape_kind", None) or _data(region).get("shape_kind")
    points = getattr(region, "points", None) or _data(region).get("points")

    if shape_kind == "polygon" and points:
        if not size:
            raise ValueError(
                f"the polygon region {node_id!r} cannot be projected without the "
                f"image's pixel size: an SvgSelector is in pixels, and there is "
                f"no percentage form of it to fall back on")
        selector: Dict[str, Any] = _svg_selector(points, size)
    else:
        box = bounding_box(region)
        if box is None:
            raise ValueError(f"the region {node_id!r} has no geometry to project")
        selector = {"type": "FragmentSelector",
                    "conformsTo": "http://www.w3.org/TR/media-frags/",
                    "value": _fragment(box, size)}

    annotation: Dict[str, Any] = {
        "@context": WEB_ANNOTATION_CONTEXT,
        "id": node_id,
        "type": "Annotation",
        "motivation": motivation,
        "target": {"type": "SpecificResource", "source": target,
                   "selector": selector},
    }
    label = getattr(region, "name", None)
    if body is not None:
        annotation["body"] = body
    elif label:
        # the label is what a viewer shows; the CLAIM stays in the graph, and a
        # body that pretended to carry it would be a second, weaker copy
        annotation["body"] = {"type": "TextualBody", "value": str(label),
                              "format": "text/plain"}
    page = getattr(region, "page", None)
    if isinstance(page, int) and page > 0:
        annotation["em:page"] = page
    return annotation


def web_annotation_to_region(annotation: Dict[str, Any], *,
                             size: Optional[Tuple[int, int]] = None,
                             resource_id: Optional[str] = None) -> Any:
    """A W3C Web Annotation → an `AnnotationRegionNode`. The inverse, exactly.

    Pixel selectors need the size to come back to [0,1]; a percentage selector
    does not, which is the second reason it is the fallback and not an
    afterthought.
    """
    from .nodes.annotation_region_node import (AnnotationRegionError,
                                               AnnotationRegionNode)

    target = annotation.get("target")
    selector = None
    if isinstance(target, dict):
        selector = target.get("selector")
    if not isinstance(selector, dict):
        raise AnnotationRegionError(
            "this annotation carries no selector: there is no region in it")

    node_id = str(annotation.get("id") or "")
    label = ""
    body = annotation.get("body")
    if isinstance(body, dict):
        label = str(body.get("value") or "")
    page = int(annotation.get("em:page") or 0)

    kind = selector.get("type")
    if kind == "FragmentSelector":
        value = str(selector.get("value") or "")
        if value.startswith("xywh=percent:"):
            parts = [float(v) / 100.0 for v in value[len("xywh=percent:"):].split(",")]
        elif value.startswith("xywh="):
            if not size:
                raise AnnotationRegionError(
                    f"the pixel selector {value!r} cannot be read without the "
                    f"image's size: pixels mean nothing on their own")
            width, height = size
            numbers = [float(v) for v in value[len("xywh="):].split(",")]
            parts = [numbers[0] / width, numbers[1] / height,
                     numbers[2] / width, numbers[3] / height]
        else:
            raise AnnotationRegionError(f"unsupported fragment {value!r}")
        if len(parts) != 4:
            raise AnnotationRegionError(f"malformed fragment {value!r}")
        return AnnotationRegionNode(node_id or "region", name=label or node_id,
                                    shape_kind="rect", rect=parts, page=page,
                                    resource_id=resource_id)

    if kind == "SvgSelector":
        if not size:
            raise AnnotationRegionError(
                "an SvgSelector is in pixels and cannot be read without the "
                "image's size")
        width, height = size
        value = str(selector.get("value") or "")
        start = value.find('points="')
        if start < 0:
            raise AnnotationRegionError(
                "only a <polygon points=…> SvgSelector is understood; a foreign "
                "SVG shape would have to be guessed at, and guessing invents "
                "geometry")
        raw = value[start + len('points="'):]
        raw = raw[:raw.find('"')]
        points = []
        for pair in raw.split():
            px, _, py = pair.partition(",")
            points.append([float(px) / width, float(py) / height])
        return AnnotationRegionNode(node_id or "region", name=label or node_id,
                                    shape_kind="polygon", points=points,
                                    page=page, resource_id=resource_id)

    raise AnnotationRegionError(f"unsupported selector type {kind!r}")


# ── the Presentation manifest: the graph, seen by any viewer ────────────────

def _regions_on(graph: Graph, resource_id: str) -> List[Any]:
    """Every annotation region on this image, in a stable order.

    Read from the EDGES (`is_on_resource`), which is the graph's statement, with
    the node's own `resource_id` as the fallback for a region that arrived
    without its edge. Sorted by node id so the same graph always produces the
    same manifest — a projection that reorders itself cannot be diffed.
    """
    found = {}
    for edge in graph.edges:
        if edge.edge_type == "is_on_resource" and edge.edge_target == resource_id:
            node = graph.find_node_by_id(edge.edge_source)
            if node is not None and getattr(node, "node_type", "") == "annotation_region":
                found[node.node_id] = node
    for node in graph.nodes:
        if getattr(node, "node_type", "") == "annotation_region" \
                and _data(node).get("resource_id") == resource_id:
            found.setdefault(node.node_id, node)
    return [found[k] for k in sorted(found)]


def _images_of(graph: Graph, target_id: str) -> List[Any]:
    """The image resources a manifest should show, for a resource OR a document.

    A ResourceNode is one image. A DocumentNode is however many images it links
    (`has_linked_resource`) — which is what makes "the manifest of this source"
    work for a multi-plate document without a second concept.
    """
    node = graph.find_node_by_id(target_id)
    if node is None:
        return []
    if getattr(node, "node_type", "") == "resource":
        return [node] if is_image(node) else []
    linked = []
    for edge in graph.edges:
        if edge.edge_type == "has_linked_resource" and edge.edge_source == target_id:
            resource = graph.find_node_by_id(edge.edge_target)
            if resource is not None and is_image(resource):
                linked.append(resource)
    return sorted(linked, key=lambda n: n.node_id)


def iiif_manifest(graph: Graph, target_id: str, *, image_base: str,
                  manifest_id: Optional[str] = None,
                  sizes: Optional[Dict[str, Sequence[int]]] = None,
                  label: Optional[str] = None) -> Dict[str, Any]:
    """A IIIF **Presentation 3** manifest for a resource or a document.

    One canvas per image, and on each canvas the annotations that the graph
    holds for it — projected, not stored. Hand this to Mirador, to the Universal
    Viewer, to a colleague's repository: they will show our photographs and our
    regions without knowing anything about the Extended Matrix.

    `sizes` maps resource id → `(width, height)` for callers who have read
    `info.json`. Where a size is unknown the canvas is still emitted — a manifest
    without its canvas would hide the image altogether — with a **declared
    placeholder** aspect and the fact recorded in `manifest["em:warnings"]`, so
    nobody mistakes a guess for a measurement. Annotations on such a canvas use
    PERCENTAGE selectors, which stay correct whatever the real size turns out to
    be.

    Returns the manifest as a plain dict; serialising it is the caller's job.
    """
    warnings: List[str] = []
    node = graph.find_node_by_id(target_id)
    if node is None:
        raise ValueError(f"nothing in this graph is called {target_id!r}")
    images = _images_of(graph, target_id)
    if not images:
        warnings.append(
            f"{target_id!r} has no image to show: a manifest of it would be an "
            f"empty book")

    base_id = (manifest_id or f"{image_base.rstrip('/')}/-/manifest/{target_id}")
    manifest: Dict[str, Any] = {
        "@context": PRESENTATION_CONTEXT,
        "id": base_id,
        "type": "Manifest",
        "label": {"none": [str(label or getattr(node, "name", None) or target_id)]},
        "items": [],
    }
    description = str(getattr(node, "description", "") or "")
    if description:
        manifest["summary"] = {"none": [description]}

    for index, resource in enumerate(images, start=1):
        identifier = image_identifier(resource)
        if not identifier:
            warnings.append(
                f"{resource.node_id!r} has no checksum, so it has no IIIF "
                f"identifier and cannot be put on a canvas")
            continue
        size = resource_size(resource, sizes)
        if size is None:
            # declared, never disguised: the canvas exists so the image shows,
            # and the number next to it says the size was not measured
            size = (1000, 1000)
            warnings.append(
                f"no pixel size recorded for {resource.node_id!r}: the canvas "
                f"uses a placeholder {size[0]}×{size[1]} and its annotations "
                f"use percentage selectors, which stay correct anyway")
            annotation_size = None
        else:
            annotation_size = size
        width, height = size

        canvas_id = f"{base_id}/canvas/{index}"
        service = image_service(resource, image_base)
        painting = {
            "id": f"{canvas_id}/annotation/1",
            "type": "Annotation",
            "motivation": "painting",
            "body": {
                "id": image_url(resource, image_base),
                "type": "Image",
                "format": "image/jpeg",
                "width": width,
                "height": height,
                **({"service": [service]} if service else {}),
            },
            "target": canvas_id,
        }
        canvas: Dict[str, Any] = {
            "id": canvas_id,
            "type": "Canvas",
            "label": {"none": [str(getattr(resource, "name", "") or resource.node_id)]},
            "width": width,
            "height": height,
            "thumbnail": [{"id": thumbnail_url(resource, image_base),
                           "type": "Image", "format": "image/jpeg"}],
            "items": [{"id": f"{canvas_id}/page/1", "type": "AnnotationPage",
                       "items": [painting]}],
        }

        regions = _regions_on(graph, resource.node_id)
        if regions:
            projected = []
            for region in regions:
                try:
                    projected.append(region_to_web_annotation(
                        region, target=canvas_id, size=annotation_size))
                except ValueError as exc:
                    warnings.append(str(exc))
            if projected:
                canvas["annotations"] = [{
                    "id": f"{canvas_id}/annotations/1",
                    "type": "AnnotationPage",
                    "items": projected,
                }]
        manifest["items"].append(canvas)

    if warnings:
        # in the document, in a namespaced key: a caller that ignores it gets a
        # valid manifest, and a caller that reads it learns what was assumed
        manifest["em:warnings"] = warnings
    return manifest
