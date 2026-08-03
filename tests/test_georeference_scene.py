"""G3 — placing a whole scene on the ground (``api.georeference_scene``).

G1 answered "where is this point". This answers what a reader actually asks of a
map: **where the scene is AND which way it faces**. The transform is
``rotate → shift → reproject`` and the tests pin the two things that make it
either right or silently wrong:

* **north up is the identity.** With ``rotation = 0`` the local frame must come
  out unchanged apart from the shift. If that drifts, every unrotated scene — the
  overwhelming majority — is quietly misplaced.
* **the rotation turns the right way.** Clockwise from north, so a scene rotated
  +90° has its local +Y pointing EAST. A sign error here mirrors the building and
  nothing in the picture says so.

The order matters as much as the maths: rotating AFTER translating would swing
the scene around the grid origin instead of around itself, and with a shift a few
hundred metres away that puts it in the next field. There is a test for that too.
"""

import math

import pytest

from s3dgraphy import api
from s3dgraphy.graph import Graph
from s3dgraphy.nodes.semantic_shape_node import SemanticShapeNode


def _has_pyproj() -> bool:
    try:
        import pyproj  # noqa: F401
        return True
    except ImportError:
        return False


needs_pyproj = pytest.mark.skipif(
    not _has_pyproj(), reason="pyproj not installed (the [geo] extra)")

UTM33N = 32633


def _graph(*, epsg=UTM33N, shift=(291960.0, 4640631.0, 0.0), rotation=0.0):
    g = Graph(graph_id="scene")
    geo = g.find_node_by_id("geo_scene")
    geo.data.update({"epsg": epsg, "shift_x": shift[0], "shift_y": shift[1],
                     "shift_z": shift[2], "rotation": rotation})
    return g


# ── the pose, in the anchor's own frame (no reprojection involved) ─────────────
# Asking for the anchor's own EPSG as the target isolates rotate+shift from PROJ:
# these run without pyproj, and a failure here is a maths failure, not a datum one.

def test_north_up_is_the_identity():
    g = _graph(rotation=0.0)
    out = api.georeference_scene(g, [(10.0, 20.0)], epsg_target=UTM33N)
    x, y = out["points"][0]
    assert x == pytest.approx(291970.0)   # 291960 + 10
    assert y == pytest.approx(4640651.0)  # 4640631 + 20
    assert out["reprojected"] is False


def test_a_quarter_turn_clockwise_sends_local_north_to_the_east():
    """+90° clockwise: the local +Y axis (10 m "up" in the scene) must come out as
    +10 m of EASTING and no northing."""
    g = _graph(shift=(0.0, 0.0, 0.0), rotation=90.0)
    out = api.georeference_scene(g, [(0.0, 10.0)], epsg_target=UTM33N)
    x, y = out["points"][0]
    assert x == pytest.approx(10.0, abs=1e-9)
    assert y == pytest.approx(0.0, abs=1e-9)


def test_a_quarter_turn_clockwise_sends_local_east_to_the_south():
    g = _graph(shift=(0.0, 0.0, 0.0), rotation=90.0)
    out = api.georeference_scene(g, [(10.0, 0.0)], epsg_target=UTM33N)
    x, y = out["points"][0]
    assert x == pytest.approx(0.0, abs=1e-9)
    assert y == pytest.approx(-10.0, abs=1e-9)


def test_rotation_is_about_the_scene_origin_not_the_grid_origin():
    """The order rotate→shift, stated as a test: a point at the scene origin must
    land exactly on the shift whatever the azimuth. Translating first would send
    it swinging around the grid origin, hundreds of metres away."""
    for angle in (0.0, 27.5, 90.0, 180.0, 351.25):
        g = _graph(rotation=angle)
        out = api.georeference_scene(g, [(0.0, 0.0)], epsg_target=UTM33N)
        x, y = out["points"][0]
        assert x == pytest.approx(291960.0, abs=1e-9), f"azimuth {angle}"
        assert y == pytest.approx(4640631.0, abs=1e-9), f"azimuth {angle}"


def test_rotation_preserves_distances():
    """A rotation is rigid: the diagonal of a square is the same after it. Catches
    a stray scale factor, which a picture would never reveal."""
    g = _graph(shift=(0.0, 0.0, 0.0), rotation=33.7)
    out = api.georeference_scene(g, [(0.0, 0.0), (10.0, 10.0)],
                                 epsg_target=UTM33N)
    (x0, y0), (x1, y1) = out["points"]
    assert math.hypot(x1 - x0, y1 - y0) == pytest.approx(math.hypot(10, 10),
                                                         abs=1e-9)


def test_the_anchor_travels_with_the_answer():
    g = _graph(rotation=27.5)
    out = api.georeference_scene(g, [(0.0, 0.0)], epsg_target=UTM33N)
    assert out["rotation"] == 27.5
    assert out["shift"] == [291960.0, 4640631.0, 0.0]
    assert out["epsg_source"] == UTM33N


def test_no_points_no_geometry():
    """Nothing is invented: an empty request is an empty answer, not a default
    box somewhere."""
    out = api.georeference_scene(_graph(), [], epsg_target=UTM33N)
    assert out["points"] == []


# ── metres and degrees do not mix ─────────────────────────────────────────────

def test_a_degrees_anchor_refuses_a_metric_extent():
    """Found by looking at the map: with an anchor in EPSG:4326 the shift is in
    DEGREES, and adding a 30 m scene extent to it would read 30 as 30° — a
    footprint spanning a continent, drawn confidently. This is a category error,
    not an inaccuracy, so it raises instead of producing a picture."""
    g = _graph(epsg=4326, shift=(12.4923, 41.8902, 0.0))
    with pytest.raises(ValueError) as exc:
        api.georeference_scene(g, [(-30.0, -20.0), (30.0, 20.0)])
    msg = str(exc.value)
    assert "degrees" in msg and "projected" in msg  # it says what to change


def test_a_degrees_anchor_still_places_the_origin():
    """The origin involves no metres at all, so it stays legal: a graph anchored
    in WGS84 can still say where it is, it just cannot carry a metric footprint."""
    g = _graph(epsg=4326, shift=(12.4923, 41.8902, 0.0))
    out = api.georeference_scene(g, [(0.0, 0.0)])
    assert out["points"][0] == pytest.approx([12.4923, 41.8902])
    assert out["reprojected"] is False


# ── the whole chain, degrees out (needs PROJ) ──────────────────────────────────

@needs_pyproj
def test_a_square_becomes_a_quadrilateral_around_the_right_place():
    g = _graph(rotation=0.0)
    corners = [(-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0)]
    out = api.georeference_scene(g, corners)
    assert out["reprojected"] is True
    lons = [p[0] for p in out["points"]]
    lats = [p[1] for p in out["points"]]
    # Around the Colosseum, and small: 20 m is a fraction of a thousandth of a
    # degree, so a unit slip (metres read as degrees) would be unmistakable.
    assert all(12.4 < lon < 12.6 for lon in lons), lons
    assert all(41.8 < lat < 42.0 for lat in lats), lats
    assert max(lons) - min(lons) < 0.001
    assert max(lats) - min(lats) < 0.001


@needs_pyproj
def test_with_north_up_the_footprint_still_faces_the_right_way():
    """Azimuth 0 keeps south to the south and east to the east — but NOT exactly
    on a parallel, and that is correct rather than sloppy: see the next test."""
    g = _graph(rotation=0.0)
    sw, se, ne, nw = api.georeference_scene(
        g, [(-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0)])["points"]
    assert sw[1] < nw[1]      # south is south
    assert sw[0] < se[0]      # east is east
    assert sw[1] == pytest.approx(se[1], abs=1e-4)   # nearly a parallel…
    assert sw[1] != pytest.approx(se[1], abs=1e-7)   # …but not exactly one


@needs_pyproj
def test_azimuth_zero_means_GRID_north_up_not_true_north_up():
    """The fact this pins is a property of projections, not of this code, and it
    is the one that would otherwise be discovered as "the footprint looks a bit
    crooked": a UTM grid is only aligned with true north ON its central meridian.
    At 12.49°E in zone 33 (CM 15°E) the convergence is about -1.67°, which over a
    20 m east–west edge is ~0.6 m of latitude — visible on a map at z19, and
    absolutely not something to "fix" by forcing the box straight.

    Consequence for a renderer: the footprint must be drawn from the REPROJECTED
    corners (where the convergence is already baked in), and a north arrow on a
    Web-Mercator map points straight up because that map is true-north-up. Drawing
    the box from the local frame and rotating it by the azimuth would be wrong by
    exactly this angle.
    """
    g = _graph(rotation=0.0)
    p0, p1 = api.georeference_scene(g, [(0.0, 0.0), (0.0, 1000.0)])["points"]
    dlon = (p1[0] - p0[0]) * math.cos(math.radians(p0[1]))
    convergence = math.degrees(math.atan2(dlon, p1[1] - p0[1]))
    assert -3.0 < convergence < -0.5, (
        f"grid north should lean ~1.7° west of true north here, got {convergence}")


@needs_pyproj
def test_a_rotated_footprint_is_not_axis_aligned():
    g = _graph(rotation=30.0)
    sw, se, ne, nw = api.georeference_scene(
        g, [(-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0)])["points"]
    assert sw[1] != pytest.approx(se[1], abs=1e-7), \
        "a rotated box cannot have a horizontal south edge"


# ── the extent: derived from data, or absent ───────────────────────────────────

def test_no_geometry_means_no_extent():
    assert api.scene_extent(_graph()) is None


def test_the_extent_comes_from_the_semantic_shapes():
    g = _graph()
    shape = SemanticShapeNode(node_id="ss.1", name="proxy US.1")
    shape.add_convex_shape([0.0, 0.0, 0.0, 4.0, 0.0, 0.0, 4.0, 6.0, 0.0])
    g.add_node(shape)
    extent = api.scene_extent(g)
    assert extent["min_x"] == 0.0 and extent["max_x"] == 4.0
    assert extent["min_y"] == 0.0 and extent["max_y"] == 6.0
    assert extent["centroid"] == [2.0, 3.0]
    # SW, SE, NE, NW — a fixed winding, so a consumer can close the ring.
    assert extent["corners"] == [[0.0, 0.0], [4.0, 0.0], [4.0, 6.0], [0.0, 6.0]]
    assert extent["source"] == "semantic_shape"


def test_spheres_contribute_their_radius():
    g = _graph()
    shape = SemanticShapeNode(node_id="ss.2", name="proxy US.2")
    shape.add_sphere(10.0, 10.0, 0.0, 2.5)
    g.add_node(shape)
    extent = api.scene_extent(g)
    assert extent["min_x"] == 7.5 and extent["max_x"] == 12.5
    assert extent["centroid"] == [10.0, 10.0]


def test_the_extent_spans_every_shape_in_the_scene():
    g = _graph()
    a = SemanticShapeNode(node_id="ss.a", name="a")
    a.add_convex_shape([0.0, 0.0, 0.0, 1.0, 1.0, 0.0])
    b = SemanticShapeNode(node_id="ss.b", name="b")
    b.add_sphere(20.0, -5.0, 0.0, 1.0)
    g.add_node(a)
    g.add_node(b)
    extent = api.scene_extent(g)
    assert (extent["min_x"], extent["max_x"]) == (0.0, 21.0)
    assert (extent["min_y"], extent["max_y"]) == (-6.0, 1.0)


@needs_pyproj
def test_extent_and_georeference_compose_into_a_placed_footprint():
    """The two ops together are the whole G3 story: derive the box from the
    graph's own proxies, then put it on the ground."""
    g = _graph(rotation=0.0)
    shape = SemanticShapeNode(node_id="ss.3", name="proxy")
    shape.add_convex_shape([-5.0, -5.0, 0.0, 5.0, 5.0, 0.0])
    g.add_node(shape)
    extent = api.scene_extent(g)
    out = api.georeference_scene(g, [tuple(c) for c in extent["corners"]]
                                + [tuple(extent["centroid"])])
    assert len(out["points"]) == 5
    centroid = out["points"][-1]
    assert 12.4 < centroid[0] < 12.6 and 41.8 < centroid[1] < 42.0
