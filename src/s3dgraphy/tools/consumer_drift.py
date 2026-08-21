"""Which consumers are behind on the connections datamodel — reported, not managed.

The datamodel JSONs in ``JSON_config`` are the source of truth of the EM
language, and s3Dgraphy already propagates them: EMStudio re-vendors with
``frontend/scripts/sync-datamodels.sh``, the Python consumers install the
package, and the node registry has its own ``--check``
(:mod:`s3dgraphy.tools.sync_node_datamodel`). **This tool adds no distribution
mechanism** — it only makes an existing drift VISIBLE, because a consumer that
falls behind does so silently and nobody notices until a viewer stops drawing
something.

The distinction it keeps, and the reason it is not simply a CI failure:

* a consumer **we** own and track in git (EMStudio) being behind is a task —
  run the sync script, review the diff, commit. ``--check`` exits 1 for it;
* a consumer **somebody else** owns (Heriverse, 3DR) being behind is *news to
  send*, not a build break: we do not control their release cycle, and failing
  our own build over their vendored copy would be theatre. Reported, exit 0;
* an **untracked local** copy (a `.venv` install, a gitignored `ext_libs`) is an
  environment, not a repo state. Reported as such, never a failure — some of
  them are pinned on purpose.

Run from anywhere; the repos root is found by walking up from this checkout, or
given explicitly::

    python -m s3dgraphy.tools.consumer_drift                 # the table
    python -m s3dgraphy.tools.consumer_drift --check         # exit 1 if OURS is behind
    python -m s3dgraphy.tools.consumer_drift --root ~/repos  # another checkout root

**Nothing is ever written.** Not to our consumers, and above all not to somebody
else's repository or to a gitignored `ext_libs` — the first is theirs to change,
the second is a local install that a write would silently diverge from its
package.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_JSON_CONFIG = Path(__file__).resolve().parent.parent / "JSON_config"
CONNECTIONS_PATH = _JSON_CONFIG / "s3Dgraphy_connections_datamodel.json"
VERSION_KEY = "s3Dgraphy_connections_model_version"

#: The consumers we know about, and WHO owns each one. `ours` decides whether a
#: drift is a task or a piece of news; `tracked` decides whether it is a repo
#: state at all. Paths are relative to the repos root (the parent of this
#: checkout). A consumer that is not there is simply absent — this machine does
#: not have to hold every repo.
CONSUMERS: List[Dict[str, object]] = [
    {
        "name": "EMStudio",
        "path": "EMStudio/frontend/src/assets/s3Dgraphy_connections_datamodel.json",
        "ours": True,
        "tracked": True,
        "how": "frontend/scripts/sync-datamodels.sh ../../s3Dgraphy",
    },
    {
        "name": "Heriverse",
        "path": "Heriverse/src/3dgraphy_config_files/s3Dgraphy_connections_datamodel.json",
        "ours": False,
        "tracked": True,
        "how": "3DR's repository — send the diff, do not write here",
    },
    {
        "name": "EM-blender-tools (.venv)",
        "path": "EM-blender-tools/.venv/lib/python3.11/site-packages/s3dgraphy/"
                "JSON_config/s3Dgraphy_connections_datamodel.json",
        "ours": True,
        "tracked": False,
        "how": "pip install -U s3dgraphy in that venv (a local install, often pinned)",
    },
    {
        "name": "pyarchinit_stratigraph (ext_libs)",
        "path": "pyarchinit_stratigraph/ext_libs/s3dgraphy/JSON_config/"
                "s3Dgraphy_connections_datamodel.json",
        "ours": True,
        "tracked": False,
        "how": "re-vendor into ext_libs (gitignored on purpose)",
    },
]


def _version(path: Path) -> Optional[str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get(VERSION_KEY)
    except (OSError, ValueError):
        return None


def version_key(version: Optional[str]) -> Tuple[int, ...]:
    """A comparable tuple, tolerant of anything that is not `a.b.c`.

    An unparseable version sorts LOWEST rather than raising: a consumer whose
    file says something unexpected is behind until somebody looks, which is the
    safe direction for a report nobody is watching closely.

    Public because the CONNECTOR HANDSHAKE compares the same way
    (:mod:`s3dgraphy.contract.connector`): a connector that declares a datamodel
    version is a consumer arriving at run time instead of sitting in a checkout,
    and answering "behind / aligned / ahead" twice, with two comparisons, is how
    the two answers start disagreeing.
    """
    parts: List[int] = []
    for chunk in str(version or "").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


#: the name this module used before the handshake needed it too
_key = version_key


def find_root(explicit: Optional[str] = None) -> Path:
    """The directory the sibling repos live in.

    From `<root>/s3Dgraphy/src/s3dgraphy/tools/…` that is four levels up. Given
    explicitly it is taken as-is — a checkout can be anywhere, and guessing
    twice is worse than being told once.
    """
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[4]


def survey(root: Optional[str] = None) -> Dict[str, object]:
    """The state of every known consumer, as data. No printing, no exit codes."""
    ours = _version(CONNECTIONS_PATH)
    base = find_root(root)
    rows = []
    for entry in CONSUMERS:
        path = base / str(entry["path"])
        found = _version(path) if path.exists() else None
        if not path.exists():
            state = "absent"
        elif found == ours:
            state = "aligned"
        elif _key(found) < _key(ours):
            state = "behind"
        else:
            state = "ahead"
        rows.append({**entry, "version": found, "state": state,
                     "full_path": str(path)})
    return {"source": ours, "root": str(base), "consumers": rows}


def report(root: Optional[str] = None, *, check: bool = False) -> int:
    survey_result = survey(root)
    ours = survey_result["source"]
    print(f"connections datamodel {ours}  (source: {CONNECTIONS_PATH.name})")
    print(f"repos root: {survey_result['root']}")
    todo = 0
    for row in survey_result["consumers"]:  # type: ignore[union-attr]
        version = row["version"] or "—"
        owner = "ours" if row["ours"] else "third-party"
        where = "tracked" if row["tracked"] else "local"
        mark = {"aligned": "✓", "behind": "→", "ahead": "?", "absent": "·"}[str(row["state"])]
        print(f"  {mark} {str(row['name']):34} {str(version):>8}  "
              f"{str(row['state']):8} ({owner}, {where})")
        if row["state"] == "behind":
            print(f"      {row['how']}")
            if row["ours"] and row["tracked"]:
                todo += 1
    if check and todo:
        print(f"\n{todo} consumer(s) we own and track are behind — see the line "
              f"under each. Third-party and local copies are reported, never "
              f"failed on: their release cycle is not ours to fail over.")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="the directory the sibling repos live in")
    parser.add_argument(
        "--check", action="store_true",
        help="exit 1 when a consumer we own AND track is behind (third-party "
             "and local copies are reported only)")
    args = parser.parse_args()
    sys.exit(report(args.root, check=args.check))


if __name__ == "__main__":
    main()
