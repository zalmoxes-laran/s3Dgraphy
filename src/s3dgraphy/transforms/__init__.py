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

__all__ = [
    "prune_redundant_propagative_edges",
    "hoist_propagative_metadata",
    "compact_propagative_metadata",
]
