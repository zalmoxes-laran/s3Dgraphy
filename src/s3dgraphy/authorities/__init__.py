"""Authority layer (P1-D): offline-first, redundant, ranked cross-references.

Resolves free-text terms against bundled OFFLINE JSON-LD snapshots
(``snapshots/``) into ranked ``authority_refs`` for nodes/qualia. em.json stays
the single source of truth; this package is a DATA asset + a pure resolver, no
web framework, no network by default.

See :mod:`s3dgraphy.authorities.resolver`.
"""

from .resolver import (
    FACET_ORDER,
    MATCH_CLOSE,
    MATCH_EXACT,
    MATCH_SAMEAS,
    as_authority_ref,
    resolve,
    write_authority_refs,
)

__all__ = [
    "FACET_ORDER",
    "MATCH_EXACT",
    "MATCH_CLOSE",
    "MATCH_SAMEAS",
    "resolve",
    "as_authority_ref",
    "write_authority_refs",
]
