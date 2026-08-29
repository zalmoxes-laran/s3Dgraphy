"""What a reconstruction MEANS — measured without an engine, because there is
none to mock any more.

The driver moved to StratiGraph Server (`app/nodeodm_client.py`) and took its
tests with it. What is left here is the semantics, and it is the half that has to
be right no matter which engine performed the act: the two modes as two shapes of
the graph, the DTC genesis, the refusals that stop a graph from claiming a
registration that did not happen, and the control set that refuses to hold a lie.

Nothing in this file names an engine — which is the property `test_purity`
measures for the whole package.
"""

from __future__ import annotations

import pytest

from s3dgraphy.contract.core import Delta
from s3dgraphy.nodes.georeferencing_node import (GCPSetNode, GeoreferencingError,
                                                 RegistrationTransformNode)
from s3dgraphy.photogrammetry import (MODES, ProducedModel,
                                      build_photogrammetry_delta)

DIGEST = "sha256:" + "ab" * 32
AUTHOR = "0000-0001-5109-3700"

IMAGES = [f"res.IMG_{n:04d}.JPG" for n in range(1, 11)]


def _model(**kwargs) -> ProducedModel:
    base = dict(checksum=DIGEST, url=f"asset/{DIGEST}",
                media_type="model/gltf-binary", name="US12 model")
    base.update(kwargs)
    return ProducedModel(**base)


def _gcps(crs="EPSG:32633", points=3) -> GCPSetNode:
    return GCPSetNode(
        "gcp.site.01", crs=crs,
        points=[{"id": f"gcp{n:02d}",
                 "world": [100.0 + n, 200.0 + n, 30.0],
                 "observations": [{"image": IMAGES[n], "pixel": [10.0 * n, 20.0]},
                                  {"image": IMAGES[n + 1], "pixel": [11.0 * n, 21.0]}],
                 "uncertainty": 0.01}
                for n in range(points)])


def _build(**kwargs):
    base = dict(input_resources=IMAGES, output_model=_model(), author=AUTHOR)
    base.update(kwargs)
    return build_photogrammetry_delta(**base)


# ── 1 · the two modes are two SHAPES ─────────────────────────────────────────

def test_absolute_mode_writes_the_placement_and_the_evidence():
    run = _build(acquisition="acq.march", subject="US12",
                 gcp_set=_gcps(), mode="absolute",
                 tool={"name": "SomeEngine", "version": "1.2"},
                 at="2026-08-29T10:00:00Z")
    assert run.ok, run.message

    types = {n["id"]: n["node_type"] for n in run.delta.nodes}
    assert types[run.model_id] == "resource"
    assert types[run.transform_id] == "registration_transform"
    assert types[run.gcp_set_id] == "gcp_set"

    transform = next(n for n in run.delta.nodes if n["id"] == run.transform_id)
    assert transform["data"]["crs"] == "EPSG:32633"

    edges = {(e["source"], e["edge_type"], e["target"]) for e in run.delta.edges}
    assert (run.model_id, "has_registration_transform", run.transform_id) in edges
    assert (run.transform_id, "has_gcp_set", run.gcp_set_id) in edges
    assert ("US12", "has_linked_resource", run.model_id) in edges


def test_local_mode_has_no_crs_no_control_set_and_says_so():
    run = _build(acquisition="acq.march", mode="local")
    assert run.ok
    assert run.gcp_set_id is None
    transform = next(n for n in run.delta.nodes if n["id"] == run.transform_id)
    assert transform["data"]["crs"] is None
    assert not any(e["edge_type"] == "has_gcp_set" for e in run.delta.edges)
    assert any("NOT georeferenced" in w for w in run.warnings)
    assert "locally scaled" in run.message


def test_the_transform_object_knows_whether_it_georeferences():
    assert RegistrationTransformNode("t", crs="EPSG:4326").georeferenced
    assert not RegistrationTransformNode("t").georeferenced


def test_a_caller_supplied_transform_is_kept_with_its_measured_error():
    measured = RegistrationTransformNode("registration", crs="EPSG:32633",
                                         rms=0.021, scale=1.004)
    run = _build(gcp_set=_gcps(), mode="absolute", transform=measured)
    assert run.ok
    transform = next(n for n in run.delta.nodes if n["id"] == run.transform_id)
    assert transform["data"]["rms"] == pytest.approx(0.021)
    assert transform["data"]["scale"] == pytest.approx(1.004)


def test_a_transform_cannot_smuggle_a_crs_past_the_mode():
    """The invariant, at the other door: absolute/local is the SHAPE, and a
    caller that solved its own transform is held to it too."""
    georeferenced = RegistrationTransformNode("registration", crs="EPSG:32633")
    run = _build(mode="local", transform=georeferenced)
    assert not run.ok and "must not claim to" in run.message

    plain = RegistrationTransformNode("registration")
    run = _build(mode="absolute", gcp_set=_gcps(), transform=plain)
    assert not run.ok and "NAMED frame" in run.message


# ── 2 · the DTC genesis is the core's, not a second one ──────────────────────

def test_the_genesis_is_a_d7_with_the_acquisition_as_its_single_input():
    run = _build(acquisition="acq.march",
                 tool={"name": "SomeEngine", "task_uuid": "t-1"},
                 image_count=10)
    process = run.delta.process
    assert process["node_type"] == "dtc_process"
    assert process["data"]["dtc_kind"] == "photogrammetry"
    assert process["data"]["image_count"] == 10
    assert process["data"]["tool"] == {"name": "SomeEngine", "task_uuid": "t-1"}
    assert process["name"] == "SomeEngine reconstruction"

    edges = {(e["source"], e["edge_type"], e["target"]) for e in run.delta.edges}
    assert (run.process_id, "dtc_had_output", run.model_id) in edges
    assert (run.process_id, "dtc_had_input", "acq.march") in edges
    # a batch is an EVENT: there is no file-to-file shortcut to write
    assert not any(e["edge_type"] == "dtc_derived_from" for e in run.delta.edges)


def test_the_tool_is_the_only_place_an_engine_is_named_and_it_is_optional():
    run = _build(acquisition="acq.march")
    assert run.ok
    assert run.delta.process["data"]["tool"] == {}
    assert run.delta.process["name"] == "photogrammetric reconstruction"


def test_without_an_acquisition_each_photograph_is_named_and_shortcut():
    run = _build(input_resources=["res.a", "res.b"])
    edges = {(e["source"], e["edge_type"], e["target"]) for e in run.delta.edges}
    assert (run.process_id, "dtc_had_input", "res.a") in edges
    assert (run.model_id, "dtc_derived_from", "res.b") in edges


def test_the_model_carries_its_digest_and_the_output_kind():
    run = _build(acquisition="acq.march")
    model = next(n for n in run.delta.nodes if n["id"] == run.model_id)
    assert model["data"]["checksum"] == DIGEST
    assert model["data"]["url"] == f"asset/{DIGEST}"
    assert model["data"]["dtc_kind"] == "mesh"
    assert model["data"]["resource_type"] == "3d_model"
    # the id follows the bytes, so the same model is the same node
    assert run.model_id == f"model.{DIGEST.split(':')[1][:12]}"


def test_the_same_act_twice_is_the_same_event():
    first = _build(acquisition="acq.march")
    second = _build(acquisition="acq.march")
    assert first.process_id == second.process_id
    assert first.model_id == second.model_id
    assert first.transform_id == second.transform_id


# ── 3 · the refusals — a graph that would lie is not written ─────────────────

@pytest.mark.parametrize("kwargs, fragment", [
    ({"mode": "sideways"}, "unknown mode"),
    ({"mode": "absolute"}, "needs ground control points"),
])
def test_the_mode_refusals(kwargs, fragment):
    run = _build(**kwargs)
    assert not run.ok and fragment in run.message
    assert run.delta.nodes == [] and run.delta.edges == []


def test_absolute_with_too_few_observed_points_is_refused():
    run = _build(gcp_set=_gcps(points=2), mode="absolute")
    assert not run.ok and "fewer than 3 observed points" in run.message


def test_absolute_into_an_unnamed_frame_is_refused():
    run = _build(gcp_set=_gcps(crs=None), mode="absolute")
    assert not run.ok and "names no CRS" in run.message


def test_control_points_in_local_mode_are_refused_rather_than_ignored():
    run = _build(gcp_set=_gcps(), mode="local")
    assert not run.ok and "registered nothing" in run.message


def test_a_reconstruction_from_nothing_is_refused():
    run = _build(input_resources=[])
    assert not run.ok and "came from nothing" in run.message


def test_an_output_nobody_can_verify_is_refused():
    run = _build(output_model=ProducedModel(checksum=""))
    assert not run.ok and "no checksum" in run.message


def test_the_no_author_refusal_is_the_CORES_and_still_fires():
    """The reason a connector is DECLARED rather than written as an endpoint.

    The descriptor now lives with the driver, in StratiGraph Server — what is
    measured here is that the core's refusal is what fires, on any descriptor
    that declares a writing capability.
    """
    from s3dgraphy.contract.connector import ConnectorDescriptor
    from s3dgraphy.contract.core import Slot, invoke

    descriptor = ConnectorDescriptor(
        name="photogrammetry", writes=True,
        capabilities=["read-graph", "write-graph", "attach-asset"],
        input_schema=[Slot("cluster", "string", True, "the cluster")],
        handler=lambda slots, author: (_ for _ in ()).throw(
            AssertionError("the handler must not be reached")))
    result = invoke(descriptor, {"cluster": "acq.march"}, author=None)
    assert not result.ok
    assert result.data["reason"] == "no-author"
    assert not result.delta.writes


# ── 4 · the control set refuses to hold a lie ────────────────────────────────

@pytest.mark.parametrize("point, fragment", [
    ({"world": [1, 2, 3]}, "has no id"),
    ({"id": "a"}, "no world coordinate"),
    ({"id": "a", "world": [1, 2, 3], "observations": [{"pixel": [1, 2]}]},
     "names no image"),
    ({"id": "a", "world": [1, 2, 3], "observations": [{"image": "x.jpg"}]},
     "no [x, y] pixel"),
])
def test_a_control_point_that_controls_nothing_is_refused(point, fragment):
    with pytest.raises(GeoreferencingError) as exc:
        GCPSetNode("g", points=[point])
    assert fragment in str(exc.value)


def test_a_local_control_set_cannot_be_written_as_an_absolute_file():
    with pytest.raises(GeoreferencingError) as exc:
        _gcps(crs=None).gcp_list()
    assert "local grid" in str(exc.value)


def test_the_control_file_is_the_one_format_an_engine_reads():
    """`gcp_list.txt` stays in the library because it is a projection of the
    NODE, not a conversation with a server: the file an engine saw and the record
    a reader sees cannot drift."""
    text = _gcps().gcp_list()
    lines = text.strip().splitlines()
    assert lines[0] == "EPSG:32633"
    assert len(lines) == 1 + 3 * 2            # three points, two observations each
    assert lines[1].split()[5] in IMAGES


def test_a_negative_scale_is_refused():
    with pytest.raises(GeoreferencingError):
        RegistrationTransformNode("t", scale=0.0)


# ── 5 · the delta is the contract's, and it validates ────────────────────────

def test_the_delta_passes_the_seam_validator():
    from s3dgraphy.contract.connector import validate_delta

    run = _build(acquisition="acq.march", gcp_set=_gcps(), mode="absolute")
    assert isinstance(run.delta, Delta)
    # the validator answers with the edges the EM language does NOT allow —
    # an empty list is the verdict, measured against the connections datamodel
    assert validate_delta(run.delta) == []


def test_the_new_edges_are_in_the_connections_datamodel():
    from s3dgraphy.edges import get_connections_datamodel

    model = get_connections_datamodel()
    assert model.get_allowed_sources("has_registration_transform") == ["ResourceNode"]
    assert model.get_allowed_targets("has_registration_transform") == [
        "RegistrationTransformNode"]
    assert model.get_allowed_sources("has_gcp_set") == ["RegistrationTransformNode"]
    assert model.get_allowed_targets("has_gcp_set") == ["GCPSetNode"]
    assert model.get_reverse_name("has_registration_transform") == "places"
    assert model.get_reverse_name("has_gcp_set") == "controlled_registration"


def test_the_modes_are_exactly_two():
    assert MODES == ("local", "absolute")
