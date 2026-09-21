"""Generate the factual tables a deliverable or the documentation needs.

The point of this script is that the tables are DERIVED, never typed. Two modes:

    python -m s3dgraphy.tools.deliverable_report            # markdown, to stdout
    python -m s3dgraphy.tools.deliverable_report --freeze   # + provenance header

``--freeze`` stamps the output with the date, the package version and the exact
command that produced it, which is what a dated deliverable annex needs; without
it the same tables are the living version for the library documentation.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "JSON_config"


def _load(name):
    with open(CONFIG / name, encoding="utf-8") as fh:
        return json.load(fh)


def _walk_mappings(obj, out):
    """Collect every ``mapping`` block declared anywhere in a datamodel."""
    if isinstance(obj, dict):
        if "mapping" in obj and isinstance(obj["mapping"], dict):
            out.append(obj["mapping"])
        for value in obj.values():
            _walk_mappings(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _walk_mappings(value, out)
    return out


def _prefix(term):
    """The ontology a declared term belongs to, as the datamodel spells it."""
    if not term or not isinstance(term, str):
        return None
    term = term.strip()
    if ":" in term:
        return term.split(":", 1)[0]
    head = term.split()[0] if term.split() else ""
    if head[:1] in {"A"} and head[1:2].isdigit():
        return "crmarchaeo"
    if head[:1] in {"D", "L"} and head[1:2].isdigit():
        return "crmdig"
    if head[:2] in {"SP"} or (head[:1] == "S" and head[1:2].isdigit()):
        return "crmgeo/crmsci"
    if head[:1] in {"E", "P"} and head[1:2].isdigit():
        return "crm"
    return "(unqualified)"


def collect():
    nodes = _load("s3Dgraphy_node_datamodel.json")
    conns = _load("s3Dgraphy_connections_datamodel.json")
    qualia = _load("em_qualia_types.json")
    try:
        from s3dgraphy import __version__ as lib_version
    except Exception:
        lib_version = "(not importable)"

    node_maps = _walk_mappings(nodes, [])
    edges = conns.get("edge_types", {})
    edge_maps = [e.get("mapping", {}) for e in edges.values()] if isinstance(edges, dict) else []

    node_by_onto, edge_by_onto = {}, {}
    for m in node_maps:
        key = _prefix(m.get("cidoc"))
        node_by_onto[key] = node_by_onto.get(key, 0) + 1
    for m in edge_maps:
        key = m.get("cidoc_extension") or _prefix(m.get("cidoc"))
        edge_by_onto[key] = edge_by_onto.get(key, 0) + 1

    api_count = None
    try:
        import s3dgraphy.api as api
        api_count = len([n for n in dir(api) if not n.startswith("_") and callable(getattr(api, n))])
    except Exception:
        pass

    tests = HERE.parent.parent.parent / "tests"
    test_modules = len(list(tests.glob("test_*.py"))) if tests.is_dir() else None

    return {
        "library": lib_version,
        "datamodels": {
            "nodes": nodes.get("s3Dgraphy_data_model_version"),
            "connections": conns.get("s3Dgraphy_connections_model_version"),
            "qualia": qualia.get("metadata", {}).get("version"),
        },
        "ontologies": nodes.get("referenced_ontology_versions", {}),
        "counts": {
            "node mappings declared": len(node_maps),
            "edge types declared": len(edges),
            "public API callables": api_count,
            "test modules": test_modules,
        },
        "node_by_ontology": node_by_onto,
        "edge_by_ontology": edge_by_onto,
    }


def _table(rows, head):
    out = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def render(data, freeze=False):
    lines = []
    if freeze:
        lines += [
            "<!-- GENERATED, do not edit by hand -->",
            f"Generated {datetime.date.today().isoformat()} from s3dgraphy {data['library']} "
            "by `python -m s3dgraphy.tools.deliverable_report --freeze`.",
            "",
        ]
    lines += ["## Declared coherence horizon", ""]
    rows = [("s3dgraphy (library)", data["library"])]
    rows += [(f"{k} datamodel", v) for k, v in data["datamodels"].items()]
    for name, block in (data["ontologies"] or {}).items():
        if name.startswith("_"):
            continue
        ver = block.get("version") if isinstance(block, dict) else block
        rows.append((name, ver))
    lines += [_table(rows, ["Component", "Version"]), ""]

    lines += ["## Declared counts", ""]
    lines += [_table([(k, v) for k, v in data["counts"].items() if v is not None],
                     ["What", "Count"]), ""]

    lines += ["## Alignment by ontology", "", "Node types, by the ontology of the primary declared class:", ""]
    lines += [_table(sorted(data["node_by_ontology"].items(), key=lambda kv: -kv[1]),
                     ["Ontology", "Node types"]), ""]
    lines += ["Edge types, by the extension the datamodel declares:", ""]
    lines += [_table(sorted(data["edge_by_ontology"].items(), key=lambda kv: -kv[1]),
                     ["Ontology", "Edge types"]), ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--freeze", action="store_true",
                    help="stamp the output with date, version and command")
    ap.add_argument("-o", "--out", help="write to this file instead of stdout")
    args = ap.parse_args(argv)
    text = render(collect(), freeze=args.freeze)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"written: {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
