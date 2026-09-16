"""DTCDeviceNode — the APPARATUS an acquisition happened on (crmdig:D8).

Until today the camera was a **string** inside `how.acquisition`, and a string
cannot be asked anything. «What did this machine produce», «which surveys used
that scanner», «that lens turned out to be distorted — which models are
affected» are three questions that do not exist while the answer is prose.

## It hangs off the EVENT, and that is the whole shape

The three axes of ``dtc_kinds`` are the **flow**: what went in, what happened,
what came out. A device is none of those — it is **what it happened on**. CRMdig
says it in one property, ``L12_happened_on_device`` (D7 → D8), and it is
deliberately not ``L10_had_input``: the photographs are the input, the camera is
not. Flatten the two and «which files did this body take» stops being askable,
which is the only reason the node exists.

So: ``dtc_happened_on_device``, from the event to the device, and it is
**context and not chain** — a provenance walk does not traverse it. That is
recorded where the datamodel records such things: the edge carries no
``dtc_role``, and `_dtc_role_note` says an edge without one is context by
construction.

## One type, and the genus from the data

Camera, sensor, drone, computer, scanner, total station, GNSS: one class, a
``dtc_kind`` from the ``device`` axis of the data-driven vocabulary. Adding an
apparatus stays **a JSON entry plus a sign**, which is the rule
:mod:`.dtc_node` already states for the flow axes and which this one reuses
rather than re-inventing.

## The identity is stable ACROSS graphs, or the node is worth nothing

If «Nikon D850» became a different node in every study, the three questions
above would stop working and the only thing gained would be complexity. So the
id is **derived from a descriptor**, exactly the way ``bucket_acquisition``
derives an acquisition's id from the campaign name — the same mechanism, not a
new one.

**With one deliberate difference, and it is the point.** The acquisition's key
carries the ``graph_id``: a campaign is an event of THIS study, and two studies
that both ran «Aiano 2015» ran two campaigns. A device's key does NOT: the same
camera in two studies is one camera, and mixing the graph into the key would
produce precisely the per-study duplicates this node exists to prevent. Same
mechanism, opposite decision about scope, and the difference is the design.

## What is lost, said out loud

**Without a serial number two identical bodies are one node.** Two Nikon D850s
in the same department, both described as make + model, derive the same id and
merge — and the day somebody asks «which body took this» the graph cannot
answer, because it was never told.

This is not hidden and it is not an accident. A *declared* merge is better than
an invented distinction: the alternative is to salt the id with something that
is not about the device (a graph, a timestamp, a counter), which would make two
records of the same camera look like two cameras — and that failure is silent,
while this one is visible the moment anybody looks at the node. Pass the serial
when it is known; :func:`s3dgraphy.dtc.devices.device_identity` reports which of
the two happened, so a caller can say so rather than guess.
"""

from .base_node import Node
from ..utils.utils import get_dtc_kinds

#: The same single source of truth the flow axes use. The `device` axis lives
#: beside `input` / `process` / `output` / `acquisition` in
#: `em_visual_rules.json`; adding an apparatus is an entry there, never here.
DTC_KINDS = get_dtc_kinds()


class DTCDeviceNode(Node):
    """The apparatus an acquisition or a processing step happened on.

    NOT a :class:`DTCNode`. A DTC node is a **step** — an event in the chain —
    and a device is a thing in the world that steps happen on: it has no inputs,
    no outputs, and a provenance walk has no business entering it. Making it a
    subclass would have put it in the chain by inheritance and made
    ``dtc_role`` argue with the class hierarchy.

    Gated out of the stratigrapher palette, like every DTC and HDT-O node.
    """

    node_type = "dtc_device"

    #: which axis of `dtc_kinds` validates `dtc_kind` — the same contract
    #: `DTCNode.dtc_base` states for the flow classes
    dtc_base = "device"

    def __init__(self, node_id, name="Device", description="",
                 dtc_kind=None, data=None):
        super().__init__(node_id=node_id, name=name, description=description)
        self.data = data if data is not None else {}
        if dtc_kind is not None:
            allowed = DTC_KINDS.get(self.dtc_base, ())
            if dtc_kind not in allowed:
                raise ValueError(
                    f"{type(self).__name__} dtc_kind must be one of {allowed} "
                    f"or None, got {dtc_kind!r}")
            self.data["dtc_kind"] = dtc_kind

    def to_dict(self):
        return {
            "id": self.node_id,
            "type": self.node_type,
            "name": self.name,
            "description": self.description,
            "data": self.data,
        }
