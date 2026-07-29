"""s3dgraphy.acquisition — the acquisition seam (Shelf v2, Session B).

The versioned inbound-ingestion contract (design §4) + the **Tier-0 hook**: an
opaque source emits an :class:`AcquisitionDescriptor`; s3Dgraphy consumes it into
a Resource + a distinct **acquisition DTC event** (crmdig:D12_Data_Transfer_Event),
placed on the Shelf. Per-source **mapping files** (xlsx-import style) customize how
each repo's records become descriptors — Ercolano ships first.

Pure library: no UI, no network connectors, no OpenShelf/ECCCH. Tier 1/2 payload
merge (genesis / interpretation) is a later ECHOES track.
"""

from .descriptor import (
    SCHEMA_VERSION,
    AcquisitionDescriptor,
    AcquisitionError,
    schema,
)
from .mapping import apply_mapping, available_mappings, load_mapping
from .acquire import acquire_from_descriptor

__all__ = [
    "SCHEMA_VERSION",
    "AcquisitionDescriptor",
    "AcquisitionError",
    "schema",
    "load_mapping",
    "apply_mapping",
    "available_mappings",
    "acquire_from_descriptor",
]
