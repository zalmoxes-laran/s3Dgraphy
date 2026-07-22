"""Generate the flat node-class registry from the Python class hierarchy.

The datamodel JSONs in ``JSON_config`` are the source of truth of the EM
language for every consumer (s3dgraphy itself, EM-blender-tools, EMStudio,
Heriverse, ...). Two concerns used to share one file and are now split
(Phase 1, P1-A — Option B):

* ``s3Dgraphy_node_datamodel.json`` — **hand-authored only**: the categorized
  family sections (``stratigraphic_nodes``, ``temporal_nodes``, ...) with the
  CIDOC ``mapping``/``class`` entries the ``rdf_exporter`` harvests, plus the
  base ``Node`` entry. The tool never writes here anymore.
* ``node_registry.generated.json`` — **fully generated** by this tool: one
  entry per Node subclass, keyed by class name, carrying ``parent``,
  ``node_type`` (the runtime type string) and a ``description`` seeded from
  the class docstring. This is the machine-readable class hierarchy that
  non-Python consumers (EMStudio ``rules.ts``) read for ancestry → socket
  validation, circles-of-detail and palette submenus.

Run after touching the node classes::

    python -m s3dgraphy.tools.sync_node_datamodel        # rewrites the registry
    python -m s3dgraphy.tools.sync_node_datamodel --check # CI guard, no write

``tests/test_node_datamodel_registry.py`` runs the ``--check`` mode so the
registry can never drift from the classes again.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_JSON_CONFIG = Path(__file__).resolve().parent.parent / "JSON_config"
# hand-authored semantics (read-only here — only the version is echoed)
DATAMODEL_PATH = _JSON_CONFIG / "s3Dgraphy_node_datamodel.json"
# generated flat class hierarchy (this tool owns this file)
REGISTRY_PATH = _JSON_CONFIG / "node_registry.generated.json"

_GENERATED_NOTE = (
    "by `python -m s3dgraphy.tools.sync_node_datamodel` — DO NOT hand-edit. "
    "The flat class hierarchy (parent/node_type/description) is derived from "
    "the Python Node subclasses; hand-authored semantics and CIDOC mappings "
    "live in s3Dgraphy_node_datamodel.json."
)


def _all_node_classes():
    from s3dgraphy.nodes.base_node import Node

    def subclasses(cls):
        out = set(cls.__subclasses__())
        for sub in list(out):
            out |= subclasses(sub)
        return out

    return sorted({Node} | subclasses(Node), key=lambda c: c.__name__)


def build_registry_entries() -> dict:
    """Class name -> {parent, node_type, description} from the live classes."""
    entries = {}
    for cls in _all_node_classes():
        parent = cls.__mro__[1].__name__ if cls.__mro__[1].__name__ != "object" else None
        # own attributes only: abstract classes must not inherit their
        # parent's node_type, nor its docstring
        node_type = cls.__dict__.get("node_type")
        doc = (cls.__dict__.get("__doc__") or "").strip().split("\n")[0].strip()
        entries[cls.__name__] = {
            "parent": parent,
            "node_type": node_type if isinstance(node_type, str) else None,
            "description": doc,
        }
    return entries


def build_registry_doc() -> dict:
    """The full generated document written to node_registry.generated.json."""
    version = None
    try:
        version = json.loads(DATAMODEL_PATH.read_text(encoding="utf-8")).get(
            "s3Dgraphy_data_model_version"
        )
    except (OSError, ValueError):
        pass
    return {
        "_generated": _GENERATED_NOTE,
        "s3Dgraphy_data_model_version": version,
        "node_types": build_registry_entries(),
    }


def sync(check_only: bool = False) -> int:
    doc = build_registry_doc()
    generated = doc["node_types"]

    if check_only:
        if not REGISTRY_PATH.exists():
            print(f"missing generated registry: {REGISTRY_PATH.name} "
                  "(run: python -m s3dgraphy.tools.sync_node_datamodel)")
            return 1
        current = json.loads(REGISTRY_PATH.read_text(encoding="utf-8")).get(
            "node_types", {}
        )
        missing = sorted(set(generated) - set(current))
        extra = sorted(set(current) - set(generated))
        changed = [
            (name, field, current[name].get(field), generated[name][field])
            for name in sorted(set(generated) & set(current))
            for field in ("parent", "node_type", "description")
            if current[name].get(field) != generated[name][field]
        ]
        if missing or extra or changed:
            print(f"{REGISTRY_PATH.name} out of sync with the Python classes:")
            for name in missing:
                print(f"  missing entry: {name}")
            for name in extra:
                print(f"  stale entry (class gone): {name}")
            for name, field, got, want in changed:
                print(f"  {name}.{field}: json={got!r} classes={want!r}")
            return 1
        print(f"node registry in sync ({len(generated)} classes).")
        return 0

    REGISTRY_PATH.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {REGISTRY_PATH.name}: {len(generated)} classes.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify only (exit 1 when out of sync); used by the test suite",
    )
    args = parser.parse_args()
    sys.exit(sync(check_only=args.check))


if __name__ == "__main__":
    main()
