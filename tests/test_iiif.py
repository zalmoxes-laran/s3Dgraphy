"""IIIF as a PROJECTION: image service, manifest, and the Web Annotation trip.

The two-tier rule is what these tests defend. The annotation is a node in the
em.json — that is the truth, versioned and attributable. IIIF and W3C Web
Annotation are a VIEW of it, and a view has to satisfy two things at once: any
viewer must be able to read it, and whatever comes back must be recognisably the
same region. A projection that cannot come home is an export, not
interoperability.
"""

import json

import pytest

from s3dgraphy import api, iiif
from s3dgraphy.graph import Graph
from s3dgraphy.nodes import DocumentNode, ResourceNode
from s3dgraphy.nodes.annotation_region_node import (AnnotationRegionError,
                                                    AnnotationRegionNode)

BASE = "https://em.example.org/iiif/3"
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _image(node_id="img-1", digest=DIGEST_A, *, width=None, height=None,
           media="image/jpeg", name="Foto del muro"):
    node = ResourceNode(node_id, name=name, url=f"https://em.example.org/asset/sha256:{digest}",
                        checksum=f"sha256:{digest}")
    node.data["media_type"] = media
    if width and height:
        node.data["width"], node.data["height"] = width, height
    return node


def _graph_with_image(**kwargs):
    graph = Graph(graph_id="iiif-test")
    image = _image(**kwargs)
    graph.add_node(image)
    return graph, image


def _region(graph, node_id, rect, resource_id="img-1", name=None):
    region = AnnotationRegionNode(node_id, name or node_id, "rect", rect=rect,
                                  resource_id=resource_id)
    graph.add_node(region)
    graph.add_edge(f"e-{node_id}", node_id, resource_id, "is_on_resource")
    return region


# ── the identifier: the asset's own digest ──────────────────────────────────

def test_the_iiif_identifier_is_the_assets_digest():
    """No registry of our own: the object store is content-addressed, so the key
    that identifies those exact pixels already exists."""
    image = _image()
    assert iiif.image_identifier(image) == DIGEST_A
    assert iiif.image_service(image, BASE) == {
        "id": f"{BASE}/{DIGEST_A}", "type": "ImageService3", "profile": "level2"}


def test_an_unhashed_image_has_no_service_rather_than_a_broken_one():
    image = ResourceNode("img-x", name="senza checksum", url="https://x/y.jpg")
    assert iiif.image_identifier(image) is None
    assert iiif.image_service(image, BASE) is None


def test_a_model_is_not_an_image():
    """A glTF has no Image API service. Offering one would produce a URL that
    404s, which is worse than the honest absence."""
    model = ResourceNode("res-model", name="US101 (glTF)", url="https://x/m",
                         checksum=f"sha256:{DIGEST_B}")
    model.data["media_type"] = "model/gltf-binary"
    assert iiif.is_image(model) is False
    assert iiif.image_service(model, BASE) is None


def test_nothing_is_written_into_the_graph():
    """The service is DERIVED. A hostname stored in a study is a dead address
    after the first migration."""
    image = _image()
    before = json.dumps(image.data, sort_keys=True)
    image.iiif_service(BASE)
    image.iiif_thumbnail(BASE)
    assert json.dumps(image.data, sort_keys=True) == before


# ── the requests: a thumbnail is a size, a crop is a region ─────────────────

def test_a_thumbnail_is_a_confining_size_request():
    """`!w,h`, not `w,`: measured against Cantaloupe, any size above the source
    is a 400 — so a box that a small image fits inside is the request that
    cannot fail, and "at most this big" is what a thumbnail means anyway."""
    assert iiif.thumbnail_url(_image(), BASE, 200) == \
        f"{BASE}/{DIGEST_A}/full/!200,200/0/default.jpg"


def test_the_size_says_max_and_not_full():
    """`full` as a SIZE is deprecated in Image API 3 and Cantaloupe answers 400
    to it — measured against a real server, not read in a spec."""
    assert iiif.image_url(_image(), BASE).endswith("/full/max/0/default.jpg")


def test_a_regions_crop_is_served_without_anybody_knowing_the_pixels():
    """Normalised coordinates map onto IIIF's percentage region — which is what
    makes an EM annotation instantly useful outside EM."""
    graph, image = _graph_with_image()
    region = _region(graph, "reg-1", [0.25, 0.25, 0.5, 0.5])
    url = iiif.region_url(image, region, BASE)
    assert url == (f"{BASE}/{DIGEST_A}/pct:25.000000,25.000000,50.000000,"
                   f"50.000000/max/0/default.jpg")


def test_a_polygons_crop_falls_back_to_its_bounding_box():
    graph, image = _graph_with_image()
    poly = AnnotationRegionNode("reg-p", "poligono", "polygon",
                                points=[[0.2, 0.2], [0.6, 0.3], [0.4, 0.8]],
                                resource_id="img-1")
    assert iiif.bounding_box(poly) == pytest.approx((0.2, 0.2, 0.4, 0.6))
    assert "pct:20.000000,20.000000,40.000000,60.000000" in \
        iiif.region_url(image, poly, BASE)


# ── the manifest ────────────────────────────────────────────────────────────

def test_a_document_with_two_regions_gives_one_canvas_and_two_annotations():
    graph, _ = _graph_with_image(width=800, height=600)
    _region(graph, "reg-1", [0.1, 0.1, 0.2, 0.2])
    _region(graph, "reg-2", [0.5, 0.5, 0.25, 0.25])
    manifest = api.iiif_manifest(graph, "img-1", image_base=BASE)

    assert manifest["type"] == "Manifest"
    assert manifest["@context"] == iiif.PRESENTATION_CONTEXT
    assert len(manifest["items"]) == 1
    canvas = manifest["items"][0]
    assert (canvas["width"], canvas["height"]) == (800, 600)
    assert len(canvas["annotations"][0]["items"]) == 2
    assert "em:warnings" not in manifest


def test_the_canvas_paints_the_image_through_its_service():
    graph, _ = _graph_with_image(width=800, height=600)
    canvas = api.iiif_manifest(graph, "img-1", image_base=BASE)["items"][0]
    painting = canvas["items"][0]["items"][0]
    assert painting["motivation"] == "painting"
    assert painting["body"]["service"][0]["id"] == f"{BASE}/{DIGEST_A}"
    assert canvas["thumbnail"][0]["id"].endswith("/full/!400,400/0/default.jpg")


def test_a_document_gathers_the_images_it_links():
    """One manifest per SOURCE, however many plates it has — no second concept."""
    graph = Graph(graph_id="iiif-test")
    graph.add_node(DocumentNode("doc-1", name="Rilievo 1978"))
    for node_id, digest in (("img-1", DIGEST_A), ("img-2", DIGEST_B)):
        graph.add_node(_image(node_id, digest, width=800, height=600))
        graph.add_edge(f"l-{node_id}", "doc-1", node_id, "has_linked_resource")
    manifest = api.iiif_manifest(graph, "doc-1", image_base=BASE)
    assert len(manifest["items"]) == 2
    assert manifest["label"]["none"] == ["Rilievo 1978"]


def test_an_unmeasured_image_is_declared_not_disguised():
    """No size recorded: the canvas still exists (hiding the image would be
    worse), the placeholder is stated, and its annotations use percentages —
    which stay correct whatever the real size turns out to be."""
    graph, _ = _graph_with_image()                     # no width/height
    _region(graph, "reg-1", [0.25, 0.25, 0.5, 0.5])
    manifest = api.iiif_manifest(graph, "img-1", image_base=BASE)
    assert len(manifest["items"]) == 1
    assert any("placeholder" in w for w in manifest["em:warnings"])
    selector = manifest["items"][0]["annotations"][0]["items"][0]["target"]["selector"]
    assert selector["value"].startswith("xywh=percent:")


def test_a_caller_that_read_info_json_can_say_the_size():
    """The library never fetches; the caller who has the answer hands it over."""
    graph, _ = _graph_with_image()
    manifest = api.iiif_manifest(graph, "img-1", image_base=BASE,
                                 sizes={"img-1": (1600, 900)})
    canvas = manifest["items"][0]
    assert (canvas["width"], canvas["height"]) == (1600, 900)
    assert "em:warnings" not in manifest


def test_the_manifest_is_stable_for_the_same_graph():
    """A projection that reorders itself cannot be diffed."""
    graph, _ = _graph_with_image(width=800, height=600)
    _region(graph, "reg-b", [0.5, 0.5, 0.1, 0.1])
    _region(graph, "reg-a", [0.1, 0.1, 0.1, 0.1])
    first = json.dumps(api.iiif_manifest(graph, "img-1", image_base=BASE))
    second = json.dumps(api.iiif_manifest(graph, "img-1", image_base=BASE))
    assert first == second
    ids = [a["id"] for a in
           json.loads(first)["items"][0]["annotations"][0]["items"]]
    assert ids == ["reg-a", "reg-b"]


def test_a_target_that_is_not_in_the_graph_is_refused():
    graph, _ = _graph_with_image()
    with pytest.raises(ValueError):
        api.iiif_manifest(graph, "nope", image_base=BASE)


# ── the round trip ──────────────────────────────────────────────────────────

def test_a_rectangle_comes_home_through_pixels():
    region = AnnotationRegionNode("reg-1", "muro", "rect",
                                  rect=[0.25, 0.25, 0.5, 0.5], resource_id="img-1")
    annotation = api.region_to_web_annotation(region, target="c1", size=(800, 600))
    assert annotation["target"]["selector"]["value"] == "xywh=200,150,400,300"
    back = api.web_annotation_to_region(annotation, size=(800, 600),
                                        resource_id="img-1")
    assert back.rect == pytest.approx(region.rect)
    assert back.node_id == region.node_id      # the id survives: that is the point


def test_a_rectangle_comes_home_through_percentages_with_no_size_at_all():
    region = AnnotationRegionNode("reg-1", "muro", "rect",
                                  rect=[0.1, 0.2, 0.3, 0.4])
    annotation = api.region_to_web_annotation(region, target="c1")
    assert annotation["target"]["selector"]["value"].startswith("xywh=percent:")
    back = api.web_annotation_to_region(annotation)
    assert back.rect == pytest.approx(region.rect)


def test_a_polygon_comes_home_through_svg():
    points = [[0.1, 0.1], [0.5, 0.2], [0.3, 0.6]]
    region = AnnotationRegionNode("reg-p", "poligono", "polygon", points=points)
    annotation = api.region_to_web_annotation(region, target="c1", size=(800, 600))
    assert annotation["target"]["selector"]["type"] == "SvgSelector"
    back = api.web_annotation_to_region(annotation, size=(800, 600))
    assert back.shape_kind == "polygon"
    for got, want in zip(back.points, points):
        assert got == pytest.approx(want, abs=1e-3)


def test_a_polygon_without_a_size_is_refused_rather_than_guessed():
    """An SvgSelector is in pixels and has no percentage form. Inventing a size
    would move the annotation."""
    region = AnnotationRegionNode("reg-p", "poligono", "polygon",
                                  points=[[0.1, 0.1], [0.5, 0.2], [0.3, 0.6]])
    with pytest.raises(ValueError):
        api.region_to_web_annotation(region, target="c1")


def test_a_foreign_annotation_without_a_selector_is_refused():
    with pytest.raises(AnnotationRegionError):
        api.web_annotation_to_region({"id": "x", "type": "Annotation",
                                      "target": "just-a-canvas"})


def test_a_foreign_svg_shape_is_refused_rather_than_approximated():
    annotation = {"id": "x", "type": "Annotation",
                  "target": {"type": "SpecificResource", "source": "c1",
                             "selector": {"type": "SvgSelector",
                                          "value": "<svg><circle r='5'/></svg>"}}}
    with pytest.raises(AnnotationRegionError):
        api.web_annotation_to_region(annotation, size=(800, 600))


def test_the_annotation_carries_the_label_not_the_claim():
    """The interpretation lives in the PropertyNode of the paradata chain. A body
    that pretended to carry it would be a second, weaker copy."""
    region = AnnotationRegionNode("reg-1", "muro in opus", "rect",
                                  rect=[0.1, 0.1, 0.2, 0.2])
    annotation = api.region_to_web_annotation(region, target="c1")
    assert annotation["body"]["value"] == "muro in opus"
    assert annotation["motivation"] == "identifying"


def test_a_region_on_a_later_page_keeps_its_page():
    region = AnnotationRegionNode("reg-1", "tavola 3", "rect",
                                  rect=[0.1, 0.1, 0.2, 0.2], page=2)
    annotation = api.region_to_web_annotation(region, target="c1")
    assert annotation["em:page"] == 2
    assert api.web_annotation_to_region(annotation).page == 2


# ── an independent implementation agrees ────────────────────────────────────

def test_the_manifest_parses_under_an_independent_iiif_implementation():
    """Our assertions above only prove we agree with ourselves.

    `iiif-prezi3` is somebody else's reading of the Presentation 3 spec, with its
    own models: if the manifest parses there, the shape is not just internally
    consistent. Skipped (not passed) when the library is absent.
    """
    prezi = pytest.importorskip("iiif_prezi3",
                                reason="iiif-prezi3 not installed "
                                       "(pip install iiif-prezi3)")
    graph, _ = _graph_with_image(width=800, height=600)
    _region(graph, "reg-1", [0.1, 0.1, 0.2, 0.2])
    _region(graph, "reg-2", [0.5, 0.5, 0.25, 0.25])
    manifest = api.iiif_manifest(
        graph, "img-1", image_base=BASE,
        manifest_id="https://em.example.org/manifest/img-1")
    # `@context` and our namespaced warnings are not part of the model's fields
    parsed = prezi.Manifest(**{k: v for k, v in manifest.items()
                               if not k.startswith("@") and not k.startswith("em:")})
    assert parsed.type == "Manifest"
    assert len(parsed.items) == 1
    assert len(parsed.items[0].annotations[0].items) == 2
