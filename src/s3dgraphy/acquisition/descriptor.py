"""AcquisitionDescriptor v0 — the versioned acquisition seam (design §4).

A stable, versioned JSON contract an acquisition front-end EMITS and s3Dgraphy
CONSUMES. Canonical schema: ``JSON_config/acquisition_descriptor.schema.json``.
This is a thin typed loader/validator over the descriptor dict — pure, no web.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Contract major version. Bump on a breaking change to the descriptor shape.
SCHEMA_VERSION = "0"

_SCHEMA_PATH = (Path(__file__).resolve().parent.parent
                / "JSON_config" / "acquisition_descriptor.schema.json")


class AcquisitionError(ValueError):
    """Raised when a descriptor is malformed or of an unsupported version."""


def schema() -> Dict[str, Any]:
    """The canonical JSON Schema (from JSON_config)."""
    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class AcquisitionDescriptor:
    """Typed view over an acquisition descriptor dict (v0)."""

    asset: Dict[str, Any] = field(default_factory=dict)
    source: Dict[str, Any] = field(default_factory=dict)
    rights: Dict[str, Any] = field(default_factory=dict)
    acquisition: Dict[str, Any] = field(default_factory=dict)
    attribution: Optional[Dict[str, Any]] = None
    payload_graph: Optional[Dict[str, Any]] = None
    schema_version: str = SCHEMA_VERSION

    # ── load / validate ─────────────────────────────────────────────────────────
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AcquisitionDescriptor":
        d = cls(
            asset=dict(data.get("asset") or {}),
            source=dict(data.get("source") or {}),
            rights=dict(data.get("rights") or {}),
            acquisition=dict(data.get("acquisition") or {}),
            attribution=data.get("attribution"),
            payload_graph=data.get("payload_graph"),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        )
        d.validate()
        return d

    @classmethod
    def from_file(cls, path: str) -> "AcquisitionDescriptor":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "asset": self.asset,
            "source": self.source,
            "rights": self.rights,
            "acquisition": self.acquisition,
        }
        if self.attribution is not None:
            out["attribution"] = self.attribution
        if self.payload_graph is not None:
            out["payload_graph"] = self.payload_graph
        return out

    def validate(self) -> None:
        """Structural validation (no external jsonschema dep): version major must
        match, and an asset locator must be present."""
        major = self.schema_version.split(".")[0]
        if major != SCHEMA_VERSION:
            raise AcquisitionError(
                f"unsupported acquisition schema_version {self.schema_version!r} "
                f"(consumer supports v{SCHEMA_VERSION})")
        if not (self.asset.get("ref")):
            raise AcquisitionError("descriptor.asset.ref (a locator) is required")

    # ── tier helpers ─────────────────────────────────────────────────────────────
    def is_tier0(self) -> bool:
        """Tier 0 = opaque source: no inherited payload_graph."""
        return not self.payload_graph

    def capabilities(self) -> List[str]:
        caps = self.source.get("capabilities") or []
        return list(caps) if isinstance(caps, (list, tuple)) else []

    def origin(self) -> Dict[str, Any]:
        """The capability/origin envelope carried onto the shelf entry (for
        downstream tier badges): repo + capabilities + scope, and — when the
        asset says so — how it is REACHED.

        ``access`` rides in the origin rather than in a channel of its own
        because that is exactly what it is: a fact about where this resource came
        from and how to get back to it. A URI-only entry has no bytes here, so
        its origin is the only place that can answer "and how do I open it?".
        """
        out: Dict[str, Any] = {
            "repo": self.source.get("repo_id"),
            "capabilities": self.capabilities(),
            "scope": (self.payload_graph or {}).get("scope"),  # None in Tier 0
        }
        access = self.asset.get("access")
        if access:
            out["access"] = (dict(access) if isinstance(access, dict)
                             else {"mode": str(access)})
        if self.asset.get("protocol"):
            out["protocol"] = self.asset.get("protocol")
        return out

    def access(self) -> Optional[Dict[str, Any]]:
        """``{mode, endpoint?}`` when the asset declared how it is reached."""
        return self.origin().get("access")
