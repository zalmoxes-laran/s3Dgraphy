"""s3dgraphy.dtc — DTC (Digital Twin Chain) residency ops (ECHOES, R3).

Provenance is a property of the DATA: a DTC can live WITH the asset store
(referenced by the knowledge graph) rather than baked into em.json, and be baked
back on demand. This package provides the pure detach / inject / bake ops that
realise that "residency" axis, reusing the existing ``injected_by`` + bake
convention (:mod:`s3dgraphy.transforms.aux_tracking`) — no parallel mechanism.

The DTC references its resources by **stable ID** (the Resource layer,
:func:`s3dgraphy.resources.stable_resource_id` = the ResourceNode UUID), so a DTC is
reusable across graphs: the same resources → the same provenance.
"""

from .residency import (
    DTC_RECORD_VERSION,
    EDGE_DERIVED_FROM,
    EDGE_HAD_INPUT,
    EDGE_HAD_OUTPUT,
    bake_dtc,
    detach_dtc,
    dtc_injector_id,
    inject_dtc,
)
# Ingestion in bulk (2026-08-17): the plural of the acquisition seam — one event
# over N files, one attribution over the lot, a DECLARED derivation, and the
# reader that answers "where is this asset used?".
from .ingest import (
    DEFAULT_ACQUISITION_KIND,
    DEFAULT_PROCESS_KIND,
    acquisition_members,
    attribute_batch,
    batch_summary,
    bucket_acquisition,
    declare_derivation,
    derivation_chain,
    resource_usages,
    unused_resources,
)

__all__ = [
    "DTC_RECORD_VERSION",
    "EDGE_HAD_INPUT",
    "EDGE_HAD_OUTPUT",
    "EDGE_DERIVED_FROM",
    "detach_dtc",
    "inject_dtc",
    "bake_dtc",
    "dtc_injector_id",
    "DEFAULT_ACQUISITION_KIND",
    "DEFAULT_PROCESS_KIND",
    "bucket_acquisition",
    "acquisition_members",
    "declare_derivation",
    "derivation_chain",
    "attribute_batch",
    "resource_usages",
    "unused_resources",
    "batch_summary",
]
