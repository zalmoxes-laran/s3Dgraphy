"""The resolver interface + the default passthrough backend (R0).

Pure Python, no web framework, no network. The resolver maps a **stable
resource ID** to a concrete :class:`Location`. Storage backends are pluggable
via :class:`ResolverRegistry`; R0 ships exactly one — :class:`PassthroughBackend`
— which classifies a resource's *current locator* (a ResourceNode ``url``) into a
Location without touching bytes. R1 (FS-index) and R2 (MinIO) will register
richer backends ahead of the passthrough fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# The location kinds a resolver can return. A locator (ResourceNode ``url``) is
# classified into exactly one of these; storage backends produce the same set.
LOCATION_KINDS = ("local_path", "file_uri", "s3_uri", "http_url")


@dataclass(frozen=True)
class Location:
    """The concrete, resolved location of a resource.

    ``kind`` is one of :data:`LOCATION_KINDS`; ``value`` is the resolved path or
    URI; ``exists`` is a best-effort local-existence check (``True``/``False``
    for ``local_path``/``file_uri``, ``None`` when existence can't be cheaply
    determined without I/O, e.g. remote ``http``/``s3``).
    """

    kind: str
    value: str
    exists: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "value": self.value, "exists": self.exists}


def stable_resource_id(node: Any) -> str:
    """The storage-agnostic stable ID of a resource = its node UUID.

    ADDITIVE: reuses the existing ``node_id``; the ResourceNode ``url`` is only the
    current locator, not the identity."""
    return getattr(node, "node_id")


def classify_locator(locator: str) -> str:
    """Classify a locator string into one of :data:`LOCATION_KINDS`.

    ``http://``/``https://`` → ``http_url``; ``s3://`` → ``s3_uri``;
    ``file://`` → ``file_uri``; anything else (a bare or relative path) →
    ``local_path``. An empty locator falls back to ``local_path`` (an empty
    path), so callers can still detect non-existence via :attr:`Location.exists`.
    """
    s = (locator or "").strip()
    low = s.lower()
    if low.startswith(("http://", "https://")):
        return "http_url"
    if low.startswith("s3://"):
        return "s3_uri"
    if low.startswith("file://"):
        return "file_uri"
    return "local_path"


def _local_exists(kind: str, value: str) -> Optional[bool]:
    """Best-effort existence check without importing heavy deps. Only local
    filesystem kinds are checked; remote kinds return ``None`` (unknown)."""
    if kind == "local_path":
        if not value:
            return False
        from pathlib import Path
        return Path(value).exists()
    if kind == "file_uri":
        from pathlib import Path
        from urllib.parse import urlparse, unquote
        path = unquote(urlparse(value).path)
        return Path(path).exists() if path else False
    return None


class ResourceBackend:
    """Interface for a storage backend.

    A backend inspects a resource's stable ID and its current locator and, if it
    owns/recognises the resource, returns a :class:`Location`; otherwise it
    returns ``None`` so the next backend (ultimately the passthrough fallback)
    gets a chance. Subclasses set :attr:`name` and override :meth:`resolve`.
    """

    name: str = "backend"

    def resolve(self, resource_id: str, locator: str,
                *, graph: Any = None) -> Optional[Location]:
        raise NotImplementedError


class PassthroughBackend(ResourceBackend):
    """The default R0 backend: resolve a resource to its stored locator as-is.

    It performs no ingest and moves no bytes — it classifies the ResourceNode
    ``url`` into a :class:`Location` so existing url/path-based graphs resolve
    unchanged. Always resolves (never returns ``None``), so it is the correct
    lowest-priority fallback."""

    name = "passthrough"

    def resolve(self, resource_id: str, locator: str,
                *, graph: Any = None) -> Optional[Location]:
        kind = classify_locator(locator)
        return Location(kind=kind, value=(locator or ""),
                        exists=_local_exists(kind, locator or ""))


class ResolverRegistry:
    """An ordered set of backends. :meth:`resolve` tries them by descending
    priority and returns the first non-``None`` :class:`Location`.

    R1/R2 register their backends at a HIGHER priority than the passthrough
    fallback (default priority ``0``); this is what lets them "plug in" and
    claim resources they own while everything else falls through to passthrough.
    """

    def __init__(self) -> None:
        # each entry: (priority, insertion_order, backend); higher priority and,
        # on ties, earlier registration win.
        self._backends: List[tuple] = []
        self._seq = 0

    def register(self, backend: ResourceBackend, *, priority: int = 0) -> None:
        self._backends.append((priority, self._seq, backend))
        self._seq += 1
        self._backends.sort(key=lambda t: (-t[0], t[1]))

    def backends(self) -> List[ResourceBackend]:
        """The registered backends in resolution order (highest priority first)."""
        return [b for _p, _s, b in self._backends]

    def resolve(self, resource_id: str, locator: str,
                *, graph: Any = None) -> Optional[Location]:
        for _p, _s, backend in self._backends:
            loc = backend.resolve(resource_id, locator, graph=graph)
            if loc is not None:
                return loc
        return None


def default_registry() -> ResolverRegistry:
    """A fresh registry with only the :class:`PassthroughBackend` (R0 default).

    Callers that want R1/R2 backends build on this and ``register(...)`` them at
    a priority above ``0``."""
    reg = ResolverRegistry()
    reg.register(PassthroughBackend(), priority=0)
    return reg
