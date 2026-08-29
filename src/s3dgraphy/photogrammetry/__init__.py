"""s3dgraphy.photogrammetry — what a reconstruction MEANS.

One module, and what is NOT in it is the point: no REST client, no task queue,
no zip. Driving an engine is node-side plumbing and lives in StratiGraph Server;
this side owns the semantics — the DTC genesis, the two modes as two shapes of
the graph, and the refusals that stop a graph from claiming a registration that
did not happen.

The types the delta is made of (``GCPSetNode``, ``RegistrationTransformNode``)
live where every other node class lives, in :mod:`s3dgraphy.nodes`.
"""

from .delta import (EDGE_DERIVED_FROM, EDGE_HAD_INPUT, EDGE_HAD_OUTPUT,
                    EDGE_HAS_GCP_SET, EDGE_HAS_TRANSFORM, MODEL_KIND, MODES,
                    PROCESS_KIND, PhotogrammetryDelta, ProducedModel,
                    build_photogrammetry_delta)

__all__ = [
    "build_photogrammetry_delta", "ProducedModel", "PhotogrammetryDelta",
    "MODES", "PROCESS_KIND", "MODEL_KIND",
    "EDGE_HAS_TRANSFORM", "EDGE_HAS_GCP_SET",
    "EDGE_HAD_INPUT", "EDGE_HAD_OUTPUT", "EDGE_DERIVED_FROM",
]
