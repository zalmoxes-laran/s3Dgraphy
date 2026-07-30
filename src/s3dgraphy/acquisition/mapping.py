"""Per-source acquisition mapping — the customizable seam (E.D. 2026-07-30).

Mirrors the xlsx-import mapping approach: a per-source JSON file (in
``JSON_config/acquisition_mappings/``) says how to translate ONE source's raw
records into an :class:`AcquisitionDescriptor`. A generic loader applies any of
them, so a new repo = a new mapping file, not code. Ercolano (Tier 0) ships as
the first mapping.

Mapping format::

    {
      "mapping_version": "0",
      "source": "ercolano",
      "descriptor_defaults": { ... constants for this source ... },
      "field_map": { "<dotted.descriptor.path>": "<raw record key>", ... }
    }

``apply_mapping(mapping, record)`` = deep-copy ``descriptor_defaults``, then for
each ``field_map`` entry set the dotted descriptor path from ``record[key]`` when
present (record value wins). Returns a descriptor dict.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

_MAPPINGS_DIR = (Path(__file__).resolve().parent.parent
                 / "JSON_config" / "acquisition_mappings")


def available_mappings() -> Dict[str, str]:
    """``{source_name: mapping_path}`` for every shipped per-source mapping."""
    out: Dict[str, str] = {}
    if _MAPPINGS_DIR.is_dir():
        for p in sorted(_MAPPINGS_DIR.glob("*.json")):
            out[p.stem] = str(p)
    return out


def load_mapping(source_or_path: str) -> Dict[str, Any]:
    """Load a mapping by source name (e.g. ``"ercolano"``) or by explicit path."""
    p = Path(source_or_path)
    if not p.is_file():
        p = _MAPPINGS_DIR / f"{source_or_path}.json"
    if not p.is_file():
        raise FileNotFoundError(f"acquisition mapping not found: {source_or_path!r}")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _set_path(d: Dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cur = d
    for key in parts[:-1]:
        nxt = cur.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[key] = nxt
        cur = nxt
    cur[parts[-1]] = value


def apply_mapping(mapping: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a raw source ``record`` into an AcquisitionDescriptor dict using
    ``mapping``. Defaults first, then field_map (record value wins when present)."""
    descriptor: Dict[str, Any] = copy.deepcopy(mapping.get("descriptor_defaults") or {})
    field_map = mapping.get("field_map") or {}
    for dotted, key in field_map.items():
        if key in record and record[key] not in (None, ""):
            _set_path(descriptor, dotted, record[key])
    return descriptor


# 3D media-type hints (extensions the browser/mimetypes stdlib does not know).
_FS_MEDIA_TYPES = {
    "glb": "model/gltf-binary", "gltf": "model/gltf+json", "obj": "model/obj",
    "fbx": "model/fbx", "ply": "model/ply", "stl": "model/stl",
    "3ds": "model/x-3ds", "dae": "model/vnd.collada+xml",
    "usd": "model/vnd.usd", "usdz": "model/vnd.usdz+zip",
}


def fs_record(path: str) -> Dict[str, Any]:
    """Build a raw FILE-SYSTEM record for the ``fs`` mapping from a local ``path``:
    ``{filename, path, record_id, record_url, size, ext, media_type}``. The local
    analog of a remote repo record (design §3). ``record_id`` = the absolute path,
    so re-scanning the same file re-uses the same stable Resource id (idempotent)."""
    import mimetypes
    import os
    ap = os.path.abspath(path)
    filename = os.path.basename(ap)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        size = os.path.getsize(ap)
    except OSError:
        size = 0
    media_type = _FS_MEDIA_TYPES.get(ext) or (mimetypes.guess_type(filename)[0] or "")
    return {
        "filename": filename,
        "path": ap,
        "record_id": ap,
        "record_url": "file://" + ap,
        "size": size,
        "ext": ext,
        "media_type": media_type,
    }
