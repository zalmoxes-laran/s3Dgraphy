"""Synchronise the node datamodel JSON with the Python class registry.

The datamodel JSONs in ``JSON_config`` are the source of truth of the EM
language for every consumer (s3dgraphy itself, EM-blender-tools, EMStudio,
Heriverse, ...). The *class hierarchy* however was historically only
expressed in the Python classes: ``s3Dgraphy_node_datamodel.json`` shipped a
single ``Node`` entry, so non-Python consumers had to introspect or mine it.

This tool closes the gap **in the datamodel itself** (decision of
2026-07-12, E. Demetrescu / EMStudio ADR-001): it adds one entry per node
class to ``node_types`` — keyed by class name, carrying ``parent``,
``node_type`` (the runtime type string) and a ``description`` seeded from
the class docstring. Existing entries and hand-curated fields (mappings,
properties, descriptions) are never overwritten: the tool only *adds*
missing entries and missing ``parent``/``node_type`` fields.

Run after touching the node classes::

    python -m s3dgraphy.tools.sync_node_datamodel        # rewrites JSON
    python -m s3dgraphy.tools.sync_node_datamodel --check  # CI guard, no write

``tests/test_node_datamodel_registry.py`` runs the ``--check`` mode so the
JSON can never drift from the classes again.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

JSON_PATH = (
    Path(__file__).resolve().parent.parent / "JSON_config" / "s3Dgraphy_node_datamodel.json"
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


def sync(check_only: bool = False) -> int:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    node_types = data.setdefault("node_types", {})
    generated = build_registry_entries()

    # NOTE: generated entries deliberately carry NO "class" field — the key
    # already is the class name, and rdf_exporter indexes every dict that has
    # a "class" string field (recursive descent): bare registry entries must
    # stay invisible to that index so curated family-section entries keep
    # answering the CIDOC lookups.
    missing_entries = []
    missing_fields = []
    for name, gen in generated.items():
        entry = node_types.get(name)
        if entry is None:
            missing_entries.append(name)
            if not check_only:
                node_types[name] = {
                    "parent": gen["parent"],
                    "node_type": gen["node_type"],
                    "description": gen["description"],
                    "_generated": "sync_node_datamodel (curate freely; only "
                    "'parent'/'node_type' are kept in sync with the classes)",
                }
            continue
        for field in ("parent", "node_type"):
            if entry.get(field) != gen[field]:
                missing_fields.append((name, field, entry.get(field), gen[field]))
                if not check_only:
                    entry[field] = gen[field]

    if check_only:
        if missing_entries or missing_fields:
            print("node datamodel out of sync with the Python classes:")
            for name in missing_entries:
                print(f"  missing entry: {name}")
            for name, field, got, want in missing_fields:
                print(f"  {name}.{field}: json={got!r} classes={want!r}")
            return 1
        print(f"node datamodel in sync ({len(generated)} classes).")
        return 0

    JSON_PATH.write_text(
        json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"updated {JSON_PATH.name}: +{len(missing_entries)} entries, "
        f"{len(missing_fields)} fields corrected, {len(generated)} classes total."
    )
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
