"""Generate the factual tables a deliverable or the documentation needs.

The point of this script is that the tables are DERIVED, never typed. Two modes::

    python -m s3dgraphy.tools.deliverable_report            # markdown, to stdout
    python -m s3dgraphy.tools.deliverable_report --freeze   # + provenance header

``--freeze`` stamps the output with the date, the package version and the exact
command that produced it, which is what a dated deliverable annex needs; without
it the same tables are the living version for the library documentation.

``-o PATH`` writes to a file. The Sphinx build calls this on ``builder-inited``
to refresh ``docs/generated-report.md`` before reading it, so the published page
can never be older than the datamodels it describes.

## On counting node types

There is no single true count, and pretending otherwise is how two documents end
up disagreeing. Three populations exist and this report names all three:

* **node types declared in the node datamodel** — the entries that carry a CIDOC
  projection. This is the population the ontology alignment is about, and the one
  to quote when the subject is the mapping. A few of them are *abstract family
  bases* (the root, and the parents of the stratigraphic, group and paradata
  families): they declare a mapping, they inherit to their subtypes, and nothing
  is ever authored directly as one. They are counted, and counted apart.
* **field-level mapping blocks** — a handful of individual FIELDS inside a node
  type also declare a projection (``P2_has_type → E55 Type`` and the like). They
  are mapping blocks but they are not node types, and an earlier version of this
  script counted them as if they were.
* **Python node classes** — what ``node_registry.generated.json`` holds. It
  differs from the datamodel population in both directions and the differences
  are listed, because each one is either a deliberate arrangement or a defect,
  and the report should not hide which.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "JSON_config"
REPO = HERE.parent.parent.parent

#: datamodel sections that declare node types (everything else is metadata)
_NODE_SECTIONS_SUFFIX = "_nodes"
_ROOT_SECTION = "node_types"


def _load(name):
    with open(CONFIG / name, encoding="utf-8") as fh:
        return json.load(fh)


# ── walking the node datamodel ────────────────────────────────────────────────

def _node_entries(doc):
    """[(path, name, entry, is_base)] for every NODE TYPE in the datamodel.

    ``is_base`` marks an entry that has subtypes, plus the root: an abstract
    family parent that declares a mapping without being something anyone authors.
    """
    out = []
    sections = [k for k in doc
                if k == _ROOT_SECTION or k.endswith(_NODE_SECTIONS_SUFFIX)]
    for section in sections:
        entries = doc.get(section) or {}
        if not isinstance(entries, dict):
            continue
        for name, entry in entries.items():
            if name.startswith("_") or not isinstance(entry, dict):
                continue
            subtypes = entry.get("subtypes") or {}
            out.append((f"{section}/{name}", name, entry,
                        bool(subtypes) or section == _ROOT_SECTION))
            for sub_name, sub in subtypes.items():
                if sub_name.startswith("_") or not isinstance(sub, dict):
                    continue
                out.append((f"{section}/{name}/{sub_name}", sub_name, sub, False))
    return out


def _field_mappings(doc):
    """Mapping blocks that sit on a FIELD or a PROPERTY, not on a node type."""
    found = []

    def walk(obj, path):
        if isinstance(obj, dict):
            if ("mapping" in obj and isinstance(obj["mapping"], dict)
                    and ("/fields/" in path or "/properties/" in path)):
                found.append((path, obj["mapping"]))
            for key, value in obj.items():
                walk(value, f"{path}/{key}")
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                walk(value, f"{path}[{i}]")

    walk(doc, "")
    return found


def _prefix(term):
    """The ontology a declared term belongs to, as the datamodel spells it."""
    if not term or not isinstance(term, str):
        return "(none declared)"
    term = term.strip()
    if not term:
        return "(none declared)"
    if ":" in term:
        return term.split(":", 1)[0]
    head = term.split()[0] if term.split() else ""
    if head[:1] == "A" and head[1:2].isdigit():
        return "crmarchaeo"
    if head[:1] in {"D", "L"} and head[1:2].isdigit():
        return "crmdig"
    if head[:2] == "SP" or (head[:1] == "S" and head[1:2].isdigit()):
        return "crmgeo/crmsci"
    if head[:1] in {"E", "P"} and head[1:2].isdigit():
        return "crm"
    return "(unqualified)"


# ── collection ────────────────────────────────────────────────────────────────

def collect():
    nodes = _load("s3Dgraphy_node_datamodel.json")
    conns = _load("s3Dgraphy_connections_datamodel.json")
    qualia = _load("em_qualia_types.json")
    try:
        registry = _load("node_registry.generated.json")
    except OSError:
        registry = {}

    try:
        from s3dgraphy import __version__ as lib_version
    except Exception:                                      # noqa: BLE001
        lib_version = "(not importable)"

    entries = _node_entries(nodes)
    bases = [e for e in entries if e[3]]
    authorable = [e for e in entries if not e[3]]
    fields = _field_mappings(nodes)
    no_mapping = [name for _p, name, entry, _b in entries
                  if not isinstance(entry.get("mapping"), dict)]

    edges = conns.get("edge_types") or {}
    live_edges = {n: e for n, e in edges.items() if not e.get("deprecated")}
    with_reverse = [n for n, e in edges.items() if e.get("reverse")]

    node_by_onto, edge_by_onto, ext_by_onto = {}, {}, {}
    own_class, reused_class = 0, 0
    for _path, _name, entry, _base in entries:
        mapping = entry.get("mapping") or {}
        node_by_onto_key = _prefix(mapping.get("cidoc"))
        node_by_onto[node_by_onto_key] = node_by_onto.get(node_by_onto_key, 0) + 1
        if str((entry.get("em_extension") or {}).get("uri") or "").startswith("em:"):
            own_class += 1
        else:
            reused_class += 1
    for _n, entry in edges.items():
        mapping = entry.get("mapping") or {}
        edge_by_onto_key = _prefix(mapping.get("cidoc"))
        edge_by_onto[edge_by_onto_key] = edge_by_onto.get(edge_by_onto_key, 0) + 1
        ext = mapping.get("extension_mapping")
        if ext:
            ext_key = _prefix(ext) if ":" in str(ext) else (
                mapping.get("extension_name") or _prefix(ext))
            ext_by_onto[ext_key] = ext_by_onto.get(ext_key, 0) + 1

    # the Python class registry, and how it differs from the datamodel
    reg_types = (registry.get("node_types") or {})
    reg_abstract = [k for k, v in reg_types.items() if not v.get("node_type")]
    dm_names = {name for _p, name, _e, _b in entries}
    # the datamodel keys stratigraphic subtypes by abbreviation, the registry by
    # class name; match those through the registry's own node_type field
    reg_node_types = {v.get("node_type") for v in reg_types.values()}
    only_in_registry = sorted(
        k for k, v in reg_types.items()
        if k not in dm_names and (v.get("node_type") or k) not in dm_names)

    # which extension prefixes the exporter can actually resolve. A prefix the
    # table does not contain resolves to nothing and the predicate is silently
    # never emitted — the exact failure that kept ten edges inert for two minor
    # versions. Checked here so that it shows up in a table rather than in a
    # post-mortem.
    known_prefixes = None
    try:
        from ..exporter.rdf_exporter import PREFIX_MAP
        known_prefixes = set(PREFIX_MAP)
    except Exception:                                      # noqa: BLE001
        pass
    unresolvable = {}
    if known_prefixes is not None:
        for name, entry in edges.items():
            ext = (entry.get("mapping") or {}).get("extension_mapping")
            if not ext or ":" not in str(ext):
                continue
            prefix = str(ext).split(":", 1)[0]
            if prefix not in known_prefixes:
                unresolvable.setdefault(prefix, []).append(name)

    api_count = None
    try:
        import s3dgraphy.api as api
        api_count = len([n for n in dir(api)
                         if not n.startswith("_") and callable(getattr(api, n))])
    except Exception:                                      # noqa: BLE001
        pass

    tests = REPO / "tests"
    test_top = len(list(tests.glob("test_*.py"))) if tests.is_dir() else None
    test_nested = (len(list(tests.glob("*/test_*.py")))
                   if tests.is_dir() else None)

    return {
        "library": lib_version,
        "datamodels": {
            "nodes": nodes.get("s3Dgraphy_data_model_version"),
            "connections": conns.get("s3Dgraphy_connections_model_version"),
            "qualia": (qualia.get("metadata") or {}).get("version"),
        },
        "registry_declares": registry.get("s3Dgraphy_data_model_version"),
        "ontologies": nodes.get("referenced_ontology_versions") or {},
        "nodes": {
            "declared in the node datamodel": len(entries),
            "— of which authorable types": len(authorable),
            "— of which abstract family bases": len(bases),
            "field-level mapping blocks (not node types)": len(fields),
            "entries with no mapping block": len(no_mapping),
        },
        "edges": {
            "declared in the connections datamodel": len(edges),
            "— of which live (not deprecated)": len(live_edges),
            "— declaring a named reverse direction": len(with_reverse),
        },
        "classes": {
            "Python node classes in the generated registry": len(reg_types),
            "— of which abstract (no own node_type)": len(reg_abstract),
            "present in the registry, absent from the datamodel":
                len(only_in_registry),
        },
        "other": {
            "public API callables": api_count,
            "test modules in tests/": test_top,
            "test modules in tests/*/": test_nested,
        },
        "base_names": sorted(name for _p, name, _e, b in entries if b),
        "registry_abstract": sorted(reg_abstract),
        "registry_only": only_in_registry,
        "own_extension_class": own_class,
        "reused_class": reused_class,
        "unresolvable_prefixes": unresolvable,
        "prefix_check_ran": known_prefixes is not None,
        "node_by_ontology": node_by_onto,
        "edge_by_ontology": edge_by_onto,
        "extension_by_ontology": ext_by_onto,
    }


# ── rendering ─────────────────────────────────────────────────────────────────

def _table(rows, head):
    out = ["| " + " | ".join(head) + " |",
           "| " + " | ".join("---" for _ in head) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def _counts(block):
    return _table([(k, v) for k, v in block.items() if v is not None],
                  ["What", "Count"])


def render(data, freeze=False):
    lines = ["(generated-report)=", "", "# Generated figures", ""]
    if freeze:
        lines += [
            "<!-- GENERATED, do not edit by hand -->",
            f"Generated {datetime.date.today().isoformat()} from s3dgraphy "
            f"{data['library']} by "
            "`python -m s3dgraphy.tools.deliverable_report --freeze`.",
            "",
        ]
    else:
        lines += [
            "<!-- GENERATED, do not edit by hand. Regenerated on every "
            "documentation build; see docs/conf.py. -->",
            "",
            "Every figure on this page is read off the datamodels and the "
            "installed package at build time. **No count in this documentation "
            "is written by hand**; where another page needs one, it links here.",
            "",
        ]

    lines += ["## Declared coherence horizon", ""]
    rows = [("s3dgraphy (library)", data["library"])]
    rows += [(f"{k} datamodel", v) for k, v in data["datamodels"].items()]
    for name, block in (data["ontologies"] or {}).items():
        if name.startswith("_"):
            continue
        rows.append((name, block.get("version")
                     if isinstance(block, dict) else block))
    lines += [_table(rows, ["Component", "Version"]), ""]

    if data.get("registry_declares") and \
            data["registry_declares"] != data["datamodels"]["nodes"]:
        lines += [
            f"> ⚠ The generated node registry declares node datamodel version "
            f"`{data['registry_declares']}` while the node datamodel itself is "
            f"at `{data['datamodels']['nodes']}`. The registry's `--check` mode "
            f"compares class entries only, so a version drift like this one "
            f"passes unnoticed. Regenerate with "
            f"`python -m s3dgraphy.tools.sync_node_datamodel`.",
            "",
        ]

    lines += ["## Node types", "",
              "The three populations, named apart — see this module's docstring "
              "for why there is no single number.", "",
              _counts(data["nodes"]), ""]
    if data["base_names"]:
        lines += ["Abstract family bases: "
                  + ", ".join(f"`{n}`" for n in data["base_names"]) + ".", ""]

    lines += ["## Edge types", "", _counts(data["edges"]), ""]

    lines += ["## Python classes", "", _counts(data["classes"]), ""]
    if data["registry_abstract"]:
        lines += ["Abstract classes (no own `node_type`): "
                  + ", ".join(f"`{n}`" for n in data["registry_abstract"]) + ".",
                  ""]
    if data["registry_only"]:
        lines += ["Classes present in the registry with no entry in the node "
                  "datamodel, and therefore with no declared CIDOC projection: "
                  + ", ".join(f"`{n}`" for n in data["registry_only"]) + ".", ""]

    lines += ["## Other surfaces", "", _counts(data["other"]), ""]

    lines += ["## Alignment by ontology", "",
              f"Of the {data['nodes']['declared in the node datamodel']} node "
              f"types declared, **{data['reused_class']} reuse a class from an "
              f"existing ontology unchanged** and "
              f"**{data['own_extension_class']} declare a class in the "
              f"Extended Matrix namespace**. Every one of the latter keeps a "
              f"CIDOC anchor, so the table below covers all of them.", "",
              "Node types, by the ontology of the CIDOC class they are "
              "anchored to:", "",
              _table(sorted(data["node_by_ontology"].items(),
                            key=lambda kv: (-kv[1], kv[0])),
                     ["Ontology", "Node types"]), "",
              "Edge types, by the ontology of the CIDOC predicate they emit. "
              "An edge with no CIDOC predicate is a *declared absence*: the "
              "family has no term for that relation and the edge is emitted on "
              "its extension predicate alone.", "",
              _table(sorted(data["edge_by_ontology"].items(),
                            key=lambda kv: (-kv[1], kv[0])),
                     ["Ontology", "Edge types"]), "",
              "Edge types carrying a second, extension predicate beside (or "
              "instead of) the CIDOC one:", "",
              _table(sorted(data["extension_by_ontology"].items(),
                            key=lambda kv: (-kv[1], kv[0])),
                     ["Ontology", "Edge types"]), ""]

    if data["prefix_check_ran"]:
        if data["unresolvable_prefixes"]:
            lines += ["> ⚠ **Extension prefixes the RDF exporter cannot "
                      "resolve.** A predicate declared under a prefix that is "
                      "not in the exporter's prefix table resolves to nothing "
                      "and is never emitted — no error is raised anywhere. "
                      "These declarations are inert:", ""]
            for prefix, names in sorted(data["unresolvable_prefixes"].items()):
                lines += [f"> * `{prefix}:` — on {len(names)} edge type"
                          f"{'s' if len(names) != 1 else ''}: "
                          + ", ".join(f"`{n}`" for n in sorted(names))]
            lines += [""]
        else:
            lines += ["Every extension prefix declared above resolves in the "
                      "RDF exporter's prefix table.", ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
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
