"""G1 — coordinate reprojection (``api.reproject`` / ``api.reproject_many``).

Excavation coordinates are normally PROJECTED (a UTM zone, a national grid) with
the EPSG code recorded on the graph's GeoPositionNode; a web map wants WGS84.
This is the one place that conversion happens, and these tests pin the two things
that go wrong when it is improvised: **the axis order** (EPSG:4326 formally
declares lat before lon, and a swap is invisible until the marker is in the wrong
hemisphere) and **the silent failure** (PROJ answers with infinities outside a
frame's domain, and an ``inf`` would travel all the way to the map).

pyproj is an OPTIONAL extra ([geo]), so every test that needs a real
transformation skips without it — the point of a lazy dependency is that the
library, and its test suite, still work when it is absent. What does NOT skip is
the contract that holds either way: identity is dependency-free, and a missing
pyproj raises MissingDependency rather than crashing.
"""

import builtins

import pytest

from s3dgraphy import api


def _has_pyproj() -> bool:
    try:
        import pyproj  # noqa: F401
        return True
    except ImportError:
        return False


needs_pyproj = pytest.mark.skipif(
    not _has_pyproj(), reason="pyproj not installed (the [geo] extra)")


# ── the anchor: a case that can be checked without trusting the library ────────
#
# On UTM zone 33 the central meridian is 15°E and the false easting is 500 000 m.
# So easting EXACTLY 500 000 must come back as longitude EXACTLY 15 — that is the
# definition of the zone, not a value looked up somewhere — and 4 649 776.22 m of
# northing is the textbook distance from the equator to 42°N on WGS84.
UTM33N = 32633
WGS84 = 4326


@needs_pyproj
def test_utm33n_central_meridian_is_exactly_fifteen_degrees():
    lon, lat = api.reproject(500000.0, 4649776.22, UTM33N)
    assert lon == pytest.approx(15.0, abs=1e-9)
    assert lat == pytest.approx(42.0, abs=1e-6)


@needs_pyproj
def test_axis_order_is_lon_lat_not_lat_lon():
    """The Colosseum is at 41.89 N, 12.49 E: latitude is the BIGGER number here,
    so a swapped pair is unmistakable — and would land in the Indian Ocean."""
    lon, lat = api.reproject(291960.5, 4640631.8, UTM33N)
    assert 12.0 < lon < 13.0, f"first value must be longitude, got {lon}"
    assert 41.0 < lat < 42.0, f"second value must be latitude, got {lat}"


@needs_pyproj
def test_round_trip_returns_the_same_point():
    lon, lat = 12.492373, 41.890251
    east, north = api.reproject(lon, lat, WGS84, UTM33N)
    # A UTM easting/northing in metres: sanity, not just "some numbers".
    assert 200000 < east < 400000
    assert 4600000 < north < 4700000
    back_lon, back_lat = api.reproject(east, north, UTM33N, WGS84)
    assert back_lon == pytest.approx(lon, abs=1e-9)
    assert back_lat == pytest.approx(lat, abs=1e-9)


@needs_pyproj
def test_reproject_many_matches_reproject_one_by_one():
    pts = [(500000.0, 4649776.22), (600000.0, 4649776.22), (450000.0, 4500000.0)]
    batch = api.reproject_many(pts, UTM33N)
    one_by_one = [api.reproject(x, y, UTM33N) for x, y in pts]
    assert batch == one_by_one


@needs_pyproj
def test_a_point_outside_the_frame_raises_instead_of_returning_infinity():
    """PROJ signals "outside the domain" with a non-finite result. Returning it
    would put a marker at an absurd place and call it data."""
    with pytest.raises(ValueError):
        api.reproject(1e30, 1e30, UTM33N)


@needs_pyproj
def test_unknown_epsg_raises_value_error():
    with pytest.raises(ValueError):
        api.reproject(0.0, 0.0, 999999)


# ── contracts that hold WITHOUT the optional dependency ───────────────────────


def test_identity_needs_no_pyproj_and_changes_nothing():
    """A graph already in WGS84 must work in a build without the [geo] extra:
    same EPSG in and out is a short-circuit, not a transformation."""
    assert api.reproject(12.5, 41.9, WGS84, WGS84) == (12.5, 41.9)
    assert api.reproject_many([(1.0, 2.0)], 32633, 32633) == [(1.0, 2.0)]


def test_missing_pyproj_raises_missing_dependency(monkeypatch):
    """The lazy-dependency contract, verified by hiding the module: the op says
    what to install, and it is a MissingDependency (which the transports map to
    a 501), never an ImportError escaping from the middle of a call."""
    real_import = builtins.__import__

    def deny(name, *args, **kwargs):
        if name == "pyproj" or name.startswith("pyproj."):
            raise ImportError("no pyproj for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny)
    with pytest.raises(api.MissingDependency) as exc:
        api.reproject(500000.0, 4649776.22, UTM33N)
    assert "geo" in str(exc.value)  # the message names the extra to install


def test_non_integer_epsg_is_a_value_error():
    with pytest.raises(ValueError):
        api.reproject(0.0, 0.0, "EPSG:32633")  # the code, not the string form


# ── the graph-level georef anchor carries an azimuth (G1) ─────────────────────


def test_geo_position_node_carries_rotation_defaulting_to_north_up():
    from s3dgraphy.nodes.geo_position_node import GeoPositionNode

    node = GeoPositionNode(node_id="geo_test")
    assert node.data["rotation"] == 0.0, "0 = north up is the default"
    turned = GeoPositionNode(node_id="geo_turned", epsg=32633, shift_x=291960.0,
                             shift_y=4640631.0, rotation=27.5)
    assert turned.data["rotation"] == 27.5
    assert turned.to_dict()["data"]["rotation"] == 27.5


def test_rotation_survives_an_emjson_round_trip():
    """Additive means: it goes out and comes back. The importer feeds `data` keys
    to the constructor, so a new field only round-trips if it is a parameter."""
    from s3dgraphy.graph import Graph

    graph = Graph(graph_id="rot")
    geo = graph.find_node_by_id("geo_rot")
    geo.data.update({"epsg": 32633, "shift_x": 291960.0, "shift_y": 4640631.0,
                     "rotation": 27.5})
    doc = api.graph_to_emjson(graph)
    reloaded, _warnings = api.load_emjson(doc)
    back = reloaded.find_node_by_id("geo_rot")
    assert back.data["rotation"] == 27.5
    assert back.data["epsg"] == 32633


def test_a_graph_without_rotation_reads_as_north_up():
    """Backward tolerance: a 1.5-era document has no `rotation` at all."""
    from s3dgraphy.graph import Graph

    graph = Graph(graph_id="old")
    geo = graph.find_node_by_id("geo_old")
    geo.data.pop("rotation", None)
    doc = api.graph_to_emjson(graph)
    reloaded, _warnings = api.load_emjson(doc)
    back = reloaded.find_node_by_id("geo_old")
    assert back.data.get("rotation", 0.0) == 0.0
