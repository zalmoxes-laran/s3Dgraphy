"""REFERENCE DESCRIPTORS — the spec a partner implements against.

A descriptor is data, and the fastest way to de-risk somebody else's
implementation is to hand them the exact data their side has to produce. That is
what lives here: connectors whose ADAPTER belongs to another team, declared on
our side so that

* the shape is not negotiated over email — it is a value they can print, diff and
  assert against;
* our half is testable **before** their half exists (the tests in
  `tests/test_contract_consumer.py` run this descriptor through the handshake, the
  serving seam, the rights gate and a subscription);
* and the day their build announces itself, a mismatch is a diff against a
  reference rather than a debugging session.

**Whose file is whose.** Blender's descriptor lives in EMtools
(`EM-blender-tools/sync_manager/connector.py`) because that repository is ours to
write in. Heriverse's lives HERE because the viewer is 3DR's: we own the
contract, they own the adapter, and a reference on our side is the honest place
for a declaration we do not get to make on theirs. It is a reference, not a
stand-in for their build — nothing here connects to anything.

Only Heriverse today. Tropy, PyArchInit, Aioli and the FBK tools are candidates,
and each becomes ~40 lines of this plus a handler; none of them should require a
line of :mod:`s3dgraphy.contract.connector` to change.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .connector import ConnectorDescriptor, Versions, current_versions

#: What a Heriverse viewer does, and every one of them is a READ. There is no
#: `write-graph` and there is no `attach-asset`: Heriverse shows a study, it does
#: not add to one. When annotations write back (a candidate, not a plan) that
#: becomes a declared capability and a role that carries it — not a quiet
#: widening of this list.
#:
#:  * ``read-graph``       · the published graph (no tombstones, no proposals)
#:  * ``subscribe``        · the study evolves and the scene follows
#:  * ``resolve-asset``    · the bytes of a model, by sha256
#:  * ``resolve-preview``  · a thumbnail of the same bytes, for a card
#:  * ``resolve-uri``      · an authority identifier, for a label that is a link
#:  * ``link-selection``   · click a wall, EMStudio highlights the unit
#:  * ``presence``         · who else is looking at this scene
HERIVERSE_CAPABILITIES = ["read-graph", "subscribe", "resolve-asset",
                          "resolve-preview", "resolve-uri", "link-selection",
                          "presence"]

#: `cloud` first, and `lan` because a museum installation is a machine on a
#: network with no internet — the two ways a viewer actually reaches a study.
#: NOT `direct`: a browser scene is not a socket on this machine.
HERIVERSE_TRANSPORT = ["cloud", "lan"]


def heriverse(*, versions: Optional[Versions] = None,
              vendor: Optional[Dict[str, Any]] = None) -> ConnectorDescriptor:
    """The Heriverse viewer as a connector — reference #2, and a CONSUMER.

    ``writes=False`` is not a detail: it is the contract's own word for read-only,
    and it was there before this descriptor existed (:class:`Descriptor`). A
    consumer therefore needs no exemption from the no-author refusal — the
    refusal simply never applies, because nothing it does is a write.

    ``provenance="none"`` for the same reason. The field says how a connector
    attributes what it writes; a consumer writes nothing, and stating a
    provenance it will never use would be a promise about an act that does not
    happen.
    """
    return ConnectorDescriptor(
        name="heriverse",
        description="Heriverse · web viewer (3D-ResearchLab)",
        intents=["heriverse", "viewer", "aton"],
        service="app",
        host="app-side",                     # it runs inside another application
        transport=list(HERIVERSE_TRANSPORT),
        capabilities=list(HERIVERSE_CAPABILITIES),
        versions=versions or current_versions(),
        provenance="none",                   # a consumer attributes nothing
        writes=False,                        # …because it writes nothing
        output="published-graph",
        vendor=dict(vendor or {}))


def heriverse_wire(**kwargs: Any) -> Dict[str, Any]:
    """The same declaration as the JSON a partner actually sends.

    What 3DR's side has to produce, byte for byte: one serialisation
    (:meth:`ConnectorDescriptor.as_dict`), so EMStudio's registry reads a shape
    instead of guessing one.
    """
    return heriverse(**kwargs).as_dict()
