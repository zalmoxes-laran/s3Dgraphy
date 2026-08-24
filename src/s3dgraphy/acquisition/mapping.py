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
from typing import Any, Dict, Optional

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


#: How you get to a resource you did not copy. TWO modes, because the practical
#: question a colleague asks is binary: can I click this, or do I have to ask
#: for access?
#:
#: * ``open`` — the link is freely reachable;
#: * ``subscribe`` — you subscribe/register/are granted access first (an
#:   institutional repository, a shared drive, a IIIF endpoint behind a login).
#:
#: This is deliberately NOT a rights statement: `rights.license` says what you
#: may do with the object, `access.mode` says whether you can reach it at all.
#: A CC-BY image behind a login is both, and conflating them would make one of
#: the two unaskable.
ACCESS_MODES = ("open", "subscribe")


def uri_record(uri: str, *, protocol: Optional[str] = None,
               access: Optional[Any] = None, name: Optional[str] = None,
               media_type: Optional[str] = None,
               repo_id: Optional[str] = None) -> Dict[str, Any]:
    """Build a raw record for the ``uri`` mapping from a bare **URI**.

    The asset nobody downloads: somebody pastes a link and what enters the shelf
    is the URI plus the protocol it is reached through. **No bytes are copied**
    and no object store is touched — that is the point, and the difference from
    :func:`fs_record`.

    ``access`` is ``{"mode": "open"|"subscribe", "endpoint": …}``, or just the
    mode as a string (the common case). ``record_id`` is the URI itself, so
    re-acquiring the same link lands on the same stable Resource id and the shelf
    does not grow a second entry — the idempotence the fs record gets from the
    absolute path.

    Returns ``{uri, name, protocol, media_type, access, repo_id, record_id,
    record_url}``.
    """
    import mimetypes
    from urllib.parse import urlsplit

    text = (uri or "").strip()
    if not text:
        raise ValueError("a URI-only entry needs a URI")
    parts = urlsplit(text)
    scheme = (protocol or parts.scheme or "").lower() or "http"
    if isinstance(access, str):
        access = {"mode": access}
    access = dict(access or {})
    mode = str(access.get("mode") or "open").lower()
    if mode not in ACCESS_MODES:
        raise ValueError(f"access.mode must be one of {list(ACCESS_MODES)}, "
                         f"got {access.get('mode')!r}")
    access["mode"] = mode
    tail = parts.path.rstrip("/").rsplit("/", 1)[-1]
    guessed = media_type or (_FS_MEDIA_TYPES.get(tail.rsplit(".", 1)[-1].lower())
                             if "." in tail else None) \
        or (mimetypes.guess_type(tail)[0] if "." in tail else None) or ""
    return {
        "uri": text,
        # The host is the honest name when the tail is not a filename: a record
        # page ends in an id, and "12345" is not what anybody is looking for.
        "name": name or (tail if "." in tail else (parts.netloc or text)),
        "protocol": scheme,
        "media_type": guessed,
        "access": access,
        # …and the repo is the HOST unless told otherwise, so two links from the
        # same institution group together without anybody configuring a repo.
        "repo_id": repo_id or (parts.netloc or "uri"),
        "record_id": text,
        "record_url": text,
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
