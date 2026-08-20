"""Is the s3dgraphy BUNDLED IN A CONSUMER the code this checkout holds? By content.

## Why a second drift tool, and why it is not the first one

:mod:`s3dgraphy.tools.consumer_drift` compares **version strings** of the
datamodel JSONs. That is the right question for a vendored config, and the wrong
one for a bundled **wheel** — because a version string is a claim, and a claim can
be false:

EM-blender-tools ships s3dgraphy as a wheel (a copy). On 17 Aug 2026 that copy was
older than this source **while declaring the same version** (`1.6.0.dev14` on both
sides), so EMtools ran code from days earlier and the only symptom was an
`ImportError` inside a click — `materialise.LibraryTooOld` catches that symptom,
and a symptom caught at runtime is not a defect fixed. The version-based check
passed the whole time. It had to: it was comparing two identical strings.

So this asks the only question that cannot be answered wrongly: **do the bytes of
the code match?**

## What it compares

A **fingerprint**: sha256 over `path → sha256(bytes)` for every `.py` under
`s3dgraphy/`, sorted. Two fingerprints are equal exactly when the code is the
same file-for-file. The datamodel JSONs get their own fingerprint, reported
separately, because `consumer_drift` already watches their versions and mixing the
two would make one number answer two questions.

What a difference tells you is spelled out rather than left as a hash mismatch:
files **missing** from the wheel (added to the source since it was built), files
**only** in the wheel (removed or renamed since), and files whose **content**
differs. That is the difference between "stale" and "stale, and here is what
changed".

## Governance — the same as `consumer_drift`, one line different

**Nothing is ever written.** A stale wheel is reported with the command that
rebuilds it (`EM-blender-tools/scripts/rebundle_s3dgraphy.py`). `--check` exits 1
for a bundle **we own**, because unlike a third party's vendored config this one is
one command away from being right — and shipping a wheel that lies about its
version is the defect this exists to stop.

    python -m s3dgraphy.tools.wheel_drift                 # the table
    python -m s3dgraphy.tools.wheel_drift --check         # exit 1 if ours is stale
    python -m s3dgraphy.tools.wheel_drift --root ~/repos  # another checkout root
    python -m s3dgraphy.tools.wheel_drift --wheel path/to/x.whl   # just this one
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional

#: The package root of THIS checkout — the code a bundle is compared against.
SOURCE_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = SOURCE_ROOT.name          # "s3dgraphy"

#: Where the bundled wheels live, per consumer. Globs, because the file name
#: carries a version and pinning it here would make this tool need editing every
#: time the thing it watches changes.
BUNDLES: List[Dict[str, object]] = [
    {
        "name": "EM-blender-tools (cp311)",
        "glob": "EM-blender-tools/wheels/cp311/s3dgraphy-*.whl",
        "ours": True,
        "how": "python EM-blender-tools/scripts/rebundle_s3dgraphy.py --python 3.11",
    },
    {
        "name": "EM-blender-tools (cp313)",
        "glob": "EM-blender-tools/wheels/cp313/s3dgraphy-*.whl",
        "ours": True,
        "how": "python EM-blender-tools/scripts/rebundle_s3dgraphy.py --python 3.13",
    },
]


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(files: Dict[str, bytes]) -> str:
    """One hash for a set of files: `sha256` over `path\\0sha256(content)` lines.

    Path-and-content, not content alone: a file MOVED is a different code base,
    and a fingerprint that ignored names would call it the same.
    """
    lines = "\n".join(f"{name}\0{_digest(body)}" for name, body in sorted(files.items()))
    return "sha256:" + _digest(lines.encode("utf-8"))


def _keep(name: str, suffixes: Iterable[str]) -> bool:
    return (name.startswith(f"{PACKAGE}/")
            and any(name.endswith(s) for s in suffixes)
            and "__pycache__" not in name)


def source_files(suffixes: Iterable[str] = (".py",)) -> Dict[str, bytes]:
    """The code of THIS checkout, keyed the way a wheel keys it."""
    out: Dict[str, bytes] = {}
    for path in SOURCE_ROOT.rglob("*"):
        if not path.is_file():
            continue
        name = f"{PACKAGE}/{path.relative_to(SOURCE_ROOT).as_posix()}"
        if _keep(name, suffixes):
            out[name] = path.read_bytes()
    return out


def wheel_files(wheel: Path,
                suffixes: Iterable[str] = (".py",)) -> Dict[str, bytes]:
    """The code inside a bundled wheel. The `.dist-info` is metadata, not code."""
    out: Dict[str, bytes] = {}
    with zipfile.ZipFile(wheel) as zf:
        for name in zf.namelist():
            if _keep(name, suffixes):
                out[name] = zf.read(name)
    return out


def wheel_version(wheel: Path) -> Optional[str]:
    """The version the FILE NAME claims — which is the claim this tool distrusts."""
    stem = wheel.name
    parts = stem.split("-")
    return parts[1] if len(parts) > 2 else None


def source_version() -> Optional[str]:
    """The version this checkout declares (`s3dgraphy.__version__`)."""
    init = SOURCE_ROOT / "__init__.py"
    try:
        for line in init.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__"):
                return line.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        return None
    return None


def compare(wheel: Path) -> Dict[str, object]:
    """One wheel against this source. Data only — no printing, no exit code."""
    code_src = source_files((".py",))
    code_whl = wheel_files(wheel, (".py",))
    json_src = source_files((".json",))
    json_whl = wheel_files(wheel, (".json",))

    missing = sorted(set(code_src) - set(code_whl))        # added since it was built
    extra = sorted(set(code_whl) - set(code_src))          # removed/renamed since
    changed = sorted(name for name in set(code_src) & set(code_whl)
                     if code_src[name] != code_whl[name])

    code_here, code_there = fingerprint(code_src), fingerprint(code_whl)
    return {
        "wheel": str(wheel),
        "wheel_version": wheel_version(wheel),
        "source_version": source_version(),
        "same_version": wheel_version(wheel) == source_version(),
        "code_source": code_here,
        "code_wheel": code_there,
        "aligned": code_here == code_there,
        "json_source": fingerprint(json_src),
        "json_wheel": fingerprint(json_whl),
        "json_aligned": fingerprint(json_src) == fingerprint(json_whl),
        "missing": missing, "extra": extra, "changed": changed,
        "files_source": len(code_src), "files_wheel": len(code_whl),
    }


def find_root(explicit: Optional[str] = None) -> Path:
    """The directory the sibling repos live in — same rule as `consumer_drift`."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[4]


def survey(root: Optional[str] = None,
           wheel: Optional[str] = None) -> Dict[str, object]:
    base = find_root(root)
    rows: List[Dict[str, object]] = []
    if wheel:
        path = Path(wheel).expanduser().resolve()
        rows.append({"name": path.name, "ours": True, "how": "—",
                     **(compare(path) if path.is_file() else {"state": "absent"})})
    else:
        for entry in BUNDLES:
            found = sorted(base.glob(str(entry["glob"])))
            if not found:
                rows.append({**entry, "state": "absent"})
                continue
            for path in found:
                rows.append({**entry, **compare(path)})
    for row in rows:
        if "state" not in row:
            row["state"] = "aligned" if row.get("aligned") else "STALE"
    return {"source_version": source_version(), "root": str(base),
            "bundles": rows}


def report(root: Optional[str] = None, *, check: bool = False,
           wheel: Optional[str] = None) -> int:
    result = survey(root, wheel)
    print(f"s3dgraphy source {result['source_version']}  ({SOURCE_ROOT})")
    print(f"repos root: {result['root']}")
    todo = 0
    for row in result["bundles"]:  # type: ignore[union-attr]
        state = str(row["state"])
        mark = {"aligned": "✓", "STALE": "✗", "absent": "·"}[state]
        name = str(row["name"])
        if state == "absent":
            print(f"  {mark} {name:28} — not on this machine")
            continue
        version = str(row.get("wheel_version") or "?")
        print(f"  {mark} {name:28} {version:>14}  {state}")
        if state == "aligned":
            continue
        if row.get("same_version"):
            print("      THE VERSION STRING MATCHES AND THE CODE DOES NOT — this is "
                  "the case a version check cannot see")
        for label, key in (("missing from the wheel (added since)", "missing"),
                           ("only in the wheel (removed/renamed since)", "extra"),
                           ("different content", "changed")):
            items = list(row.get(key) or [])
            if not items:
                continue
            shown = ", ".join(items[:4]) + (f" … +{len(items) - 4}" if len(items) > 4 else "")
            print(f"      {label}: {shown}")
        if not row.get("json_aligned"):
            print("      the bundled JSON_config differs too (versions: see "
                  "consumer_drift)")
        print(f"      {row['how']}")
        if row.get("ours"):
            todo += 1
    if check and todo:
        print(f"\n{todo} bundle(s) we own are STALE. A wheel is a copy, and a copy "
              f"that declares the source's version while holding older code fails "
              f"inside a click rather than in a build — rebuild it with the command "
              f"under each.")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="the directory the sibling repos live in")
    parser.add_argument("--wheel", help="check ONE wheel by path")
    parser.add_argument(
        "--check", action="store_true",
        help="exit 1 when a bundle we own is stale (the fix is one command)")
    args = parser.parse_args()
    sys.exit(report(args.root, check=args.check, wheel=args.wheel))


if __name__ == "__main__":
    main()
