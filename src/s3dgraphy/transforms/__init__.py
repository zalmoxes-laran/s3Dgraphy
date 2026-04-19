# s3dgraphy/transforms/__init__.py
"""Graph transformations: compaction, deduplication, and other
rewrites that take a graph in and produce a modified graph out.

These are typically useful as pre-export passes ("reverse propagation"
before writing GraphML, to reduce node count and formalize metadata
inheritance) or as post-import cleanup of legacy graphs.
"""

from .compact import (
    prune_redundant_propagative_edges,
    hoist_propagative_metadata,
    compact_propagative_metadata,
)

from .aux_tracking import (
    mark_as_injected,
    is_injected,
    record_attribute_override,
    freeze_aux_value,
    aux_overridden_attrs,
    strip_injected_content,
    apply_override_reversal_policy,
    clear_aux_tags,
    push_orphan,
    iter_orphans,
    clear_orphans,
    MISSING_SENTINEL,
)

__all__ = [
    "prune_redundant_propagative_edges",
    "hoist_propagative_metadata",
    "compact_propagative_metadata",
    "mark_as_injected",
    "is_injected",
    "record_attribute_override",
    "freeze_aux_value",
    "aux_overridden_attrs",
    "strip_injected_content",
    "apply_override_reversal_policy",
    "clear_aux_tags",
    "push_orphan",
    "iter_orphans",
    "clear_orphans",
    "MISSING_SENTINEL",
]
