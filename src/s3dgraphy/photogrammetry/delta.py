"""build_photogrammetry_delta — what a reconstruction MEANS, without an engine.

This is the semantic contract of the photogrammetric act, and it is deliberately
ignorant of how the act was performed. Give it what was true when the engine
stopped — these files went in, this model came out, it is placed like this, and
here is the control set if there was one — and it emits the DTC provenance:

1. **a model exists** — a ``ResourceNode`` with its URL and its digest, so
   anybody can check they got the same bytes;
2. **it came from somewhere** — a ``crmdig:D7`` process whose inputs are the
   photographs' acquisition (or the photographs), carrying whatever the caller
   knows about the tool;
3. **it is placed** — a ``RegistrationTransformNode`` the model points at and,
   in absolute mode, the ``GCPSetNode`` that transform was solved from.

**The two modes are two SHAPES, and that invariant lives here.**
``absolute`` = a transform with a CRS that ``has_gcp_set`` points at; ``local`` =
a transform with a scale and *no* CRS and no control set — scaled and oriented in
a site frame, honestly not georeferenced; no transform at all = nobody placed it.
Re-registering later is a NEW process producing a NEW transform: the old one
stays, because moving a model is provenance.

**Why the engine is not here.** s3Dgraphy is the semantic library — Extended
Matrix, the property graph, the CIDOC mapping. Driving a REST API, polling a task
queue and unzipping an archive are none of those things: they are node-side
plumbing, and they live in StratiGraph Server (``app/nodeodm_client.py``,
``app/photogrammetry.py``). A second engine — COLMAP, MicMac, Aïoli — is a second
driver calling this same function, which is the point of putting the meaning on
this side of the line. Nothing in this module imports a socket, and nothing in it
names an engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..contract.core import Delta, stable_id
from ..nodes.georeferencing_node import GCPSetNode, RegistrationTransformNode

#: the two shapes, named. `local` is the default because it is the one that is
#: always available: a phone with LiDAR, or a scale bar in frame, needs nobody to
#: have surveyed anything yet.
MODES = ("local", "absolute")

#: the edge a model points at its placement by
EDGE_HAS_TRANSFORM = "has_registration_transform"
#: the edge a placement points at the evidence it was solved from
EDGE_HAS_GCP_SET = "has_gcp_set"
#: the DTC edges — the core's, not re-declared
EDGE_HAD_INPUT = "dtc_had_input"
EDGE_HAD_OUTPUT = "dtc_had_output"
EDGE_DERIVED_FROM = "dtc_derived_from"
#: how a produced model is linked to what it is a model OF
EDGE_LINKED_RESOURCE = "has_linked_resource"

#: the process axis of the DTC vocabulary (em_visual_rules.json → dtc_kinds)
PROCESS_KIND = "photogrammetry"
#: the output axis, for the model resource
MODEL_KIND = "mesh"


@dataclass
class ProducedModel:
    """The model, as facts that are already true when this is called.

    ``checksum`` is the content reference (``sha256:…``) and it is required: a
    resource in a shared graph that points at bytes nobody can verify is the one
    thing the asset layer exists to prevent. ``url`` may be omitted, in which
    case the checksum is the locator — that is a resident asset, reached through
    the store that holds it.
    """

    checksum: str
    url: Optional[str] = None
    media_type: Optional[str] = None
    residency: str = "resident"
    name: Optional[str] = None
    #: normally derived from the digest, so the same bytes are the same node
    node_id: Optional[str] = None

    def identifier(self) -> str:
        if self.node_id:
            return str(self.node_id)
        return f"model.{self.checksum.split(':')[-1][:12]}"


@dataclass
class PhotogrammetryDelta:
    """The provenance to apply, or the reason there is none."""

    ok: bool
    message: str
    delta: Delta = field(default_factory=Delta)
    model_id: Optional[str] = None
    transform_id: Optional[str] = None
    gcp_set_id: Optional[str] = None
    process_id: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "message": self.message,
                "delta": self.delta.as_dict(), "model_id": self.model_id,
                "transform_id": self.transform_id, "gcp_set_id": self.gcp_set_id,
                "process_id": self.process_id, "warnings": list(self.warnings)}


def build_photogrammetry_delta(*,
                               input_resources: Sequence[str],
                               output_model: ProducedModel,
                               transform: Optional[RegistrationTransformNode] = None,
                               gcp_set: Optional[GCPSetNode] = None,
                               author: Optional[str] = None,
                               mode: str = "local",
                               acquisition: Optional[str] = None,
                               subject: Optional[str] = None,
                               tool: Optional[Dict[str, Any]] = None,
                               image_count: Optional[int] = None,
                               at: Optional[str] = None,
                               warnings: Optional[Sequence[str]] = None
                               ) -> PhotogrammetryDelta:
    """The DTC provenance of one reconstruction, as a delta somebody applies.

    ``input_resources`` are the photographs' resource ids. ``acquisition``, when
    given, is the ``crmdig:D12`` they arrived as: it becomes the process's single
    input, because "this model comes from the March cluster" is ONE input and not
    two hundred, and that is the reason the serial node exists at all. Without it
    each photograph is named individually AND gets the file-to-file
    ``dtc_derived_from`` shortcut — the shortcut runs between files, and a batch
    is an event.

    ``tool`` is whatever the caller knows about what performed the act
    (``{"name": …, "version": …, …}``). It is passed through verbatim and is the
    ONLY place an engine's name appears in the graph — this function does not
    know one.

    Refuses rather than writes a graph that would lie:

    * an unknown ``mode`` — the two shapes are the design, not a free string;
    * ``mode="absolute"`` with no control set, with one the bundle cannot solve
      (fewer than three observed points), or with one that names no CRS;
    * a control set in ``local`` mode — the graph would claim evidence for a
      registration that did not happen;
    * a ``transform`` whose CRS disagrees with the mode, which is the same lie
      arriving by a different door;
    * no inputs, or an output with no checksum.

    The author is NOT defaulted. A writing act without one is refused by
    :func:`s3dgraphy.contract.core.invoke`, and the delta carries whatever it was
    given so that refusal fires where it belongs.
    """
    notes: List[str] = list(warnings or [])

    if mode not in MODES:
        return PhotogrammetryDelta(
            ok=False, message=f"unknown mode {mode!r}: it is one of {MODES}")
    if mode == "absolute":
        if gcp_set is None:
            return PhotogrammetryDelta(
                ok=False,
                message="absolute mode needs ground control points: without "
                        "them there is nothing to register against, and a model "
                        "in an unnamed frame must not be labelled georeferenced")
        if not gcp_set.solvable:
            return PhotogrammetryDelta(
                ok=False,
                message=f"this control set has fewer than "
                        f"{GCPSetNode.MINIMUM_POINTS} observed points: a "
                        f"similarity is not determined by it")
        if gcp_set.crs is None:
            return PhotogrammetryDelta(
                ok=False,
                message="this control set names no CRS: absolute registration "
                        "into an unnamed frame is a local frame with extra steps")
    elif gcp_set is not None:
        return PhotogrammetryDelta(
            ok=False,
            message="control points were given but the mode is 'local': the "
                    "graph would record evidence that registered nothing. Say "
                    "mode='absolute'.")

    inputs = [str(r) for r in (input_resources or []) if str(r).strip()]
    if not inputs and not acquisition:
        return PhotogrammetryDelta(
            ok=False,
            message="no inputs: a reconstruction that came from nothing is not "
                    "provenance, it is an assertion")
    if not (output_model and str(output_model.checksum or "").strip()):
        return PhotogrammetryDelta(
            ok=False,
            message="the produced model has no checksum: a resource pointing at "
                    "bytes nobody can verify is what the asset layer exists to "
                    "prevent")

    # ── the model ────────────────────────────────────────────────────────────
    model_id = output_model.identifier()
    model = {
        "id": model_id, "node_type": "resource",
        "name": output_model.name or f"model {model_id}",
        "data": {"url": output_model.url or output_model.checksum,
                 "checksum": output_model.checksum,
                 "residency": output_model.residency or "resident",
                 "media_type": output_model.media_type,
                 "resource_type": "3d_model",
                 "dtc_kind": MODEL_KIND,
                 "created_by": author, "created_at": at},
    }
    nodes: List[Dict[str, Any]] = [model]
    edges: List[Dict[str, Any]] = []

    # ── the placement ────────────────────────────────────────────────────────
    expected_crs = gcp_set.crs if mode == "absolute" and gcp_set else None
    if transform is None:
        transform = RegistrationTransformNode(
            "registration",
            name=("Registration (absolute)" if expected_crs
                  else "Registration (site frame)"),
            crs=expected_crs,
            description=("solved from ground control points" if expected_crs
                         else "scaled and oriented in a site-local frame"))
    elif bool(transform.crs) != bool(expected_crs):
        # the invariant, enforced at the other door: a caller that solved its own
        # transform cannot smuggle a georeferenced one into local mode, nor an
        # unreferenced one into absolute
        return PhotogrammetryDelta(
            ok=False,
            message=(f"the transform names {'a CRS' if transform.crs else 'no CRS'} "
                     f"but the mode is {mode!r}: in absolute mode a transform "
                     f"lands the model in a NAMED frame, and in local mode it "
                     f"must not claim to"))

    transform_id = stable_id("registration", model_id, mode)
    transform.node_id = transform_id
    nodes.append(_payload(transform, author, at))
    edges.append(_edge(model_id, transform_id, EDGE_HAS_TRANSFORM))

    gcp_set_id = None
    if gcp_set is not None:
        gcp_set_id = gcp_set.node_id
        nodes.append(_payload(gcp_set, author, at))
        edges.append(_edge(transform_id, gcp_set_id, EDGE_HAS_GCP_SET))

    # ── the genesis ──────────────────────────────────────────────────────────
    # The id is derived from what the act IS, so a retry after a dropped
    # connection converges on one event instead of two.
    event_inputs = [acquisition] if acquisition else list(inputs)
    process_id = stable_id("photogrammetry", model_id, *sorted(event_inputs))
    count = image_count if image_count is not None else len(inputs)
    tool_card = dict(tool or {})
    process = {
        "id": process_id, "node_type": "dtc_process",
        "name": (f"{tool_card['name']} reconstruction" if tool_card.get("name")
                 else "photogrammetric reconstruction"),
        "description": f"{count} photographs → {model['name']}",
        "data": {"dtc_kind": PROCESS_KIND,
                 "tool": tool_card,
                 "mode": mode,
                 "image_count": count,
                 "created_by": author, "created_at": at},
    }
    edges.append(_edge(process_id, model_id, EDGE_HAD_OUTPUT))
    for ref in event_inputs:
        edges.append(_edge(process_id, ref, EDGE_HAD_INPUT))
    if not acquisition:
        for ref in inputs:
            edges.append(_edge(model_id, ref, EDGE_DERIVED_FROM))

    if subject:
        edges.append(_edge(subject, model_id, EDGE_LINKED_RESOURCE))

    if mode == "local":
        notes.append(
            "local mode: the model is scaled and oriented in a site frame and "
            "is NOT georeferenced — assembling it beside an absolute model needs "
            "a re-registration, which is a new act")

    return PhotogrammetryDelta(
        ok=True,
        message=(f"{count} photographs → a "
                 f"{'georeferenced' if transform.georeferenced else 'locally scaled'} "
                 f"model ({model_id})"),
        delta=Delta(nodes=nodes, edges=edges, author=author, process=process),
        model_id=model_id, transform_id=transform_id, gcp_set_id=gcp_set_id,
        process_id=process_id, warnings=notes)


# ── small helpers ────────────────────────────────────────────────────────────

def _payload(node: Any, author: Optional[str], at: Optional[str]) -> Dict[str, Any]:
    payload = node.to_dict()
    payload["node_type"] = payload.pop("type")
    data = dict(payload.get("data") or {})
    data.setdefault("created_by", author)
    data.setdefault("created_at", at)
    payload["data"] = data
    return payload


def _edge(source: str, target: str, edge_type: str) -> Dict[str, Any]:
    return {"id": f"{source}__{edge_type}__{target}", "source": source,
            "target": target, "edge_type": edge_type}
