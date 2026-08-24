"""MAPPING AUTHORING — the pure surface a mapping EDITOR is built on.

## What this is, and which of the two mapping layers it belongs to

There are two things called "mapping" in this library and confusing them is the
first mistake available:

* **acquisition mappings** (`s3dgraphy/acquisition/mapping.py` +
  `JSON_config/acquisition_mappings/*.json`) — a flat `field_map` that turns one
  repository's record into an `AcquisitionDescriptor` for the shelf. Not this.
* **rich source mappings** (`s3dgraphy/mappings/` + the importers that read
  `column_mappings` / `relations`) — how a TABLE or an XML becomes nodes, edges
  and paradata in a graph. **This is the one an editor authors**, and this module
  is everything such an editor needs that is not a user interface.

Nothing here draws or asks. It answers four questions, and each one is a question
a UI must not answer for itself:

1. *what is in this source?* — `source_fields()`: columns or XML paths, with
   sample values, so a person maps what they can see;
2. *what can I map it TO?* — `target_catalog()`: the CIDOC classes on offer, each
   already resolved to the EM node type that implements it (or marked
   `cidoc_direct` when no EM type does);
3. *how may these two connect?* — `allowed_edges()`, straight from the
   connections datamodel's `allowed_connections`, the same source the canvas's
   edge picker uses;
4. *is this mapping coherent?* — `validate_mapping()`.

…plus one act: `apply_mapping()`, which runs a mapping over a source either as a
**volatile** auxiliary (in the graph, out of the saved document until a bake) or
as a **bake** straight into it.

## CIDOC-first, with the retro-map (E.D. 2026-08-24)

The picker offers CIDOC classes, not EM types, because that is the vocabulary the
ontology table speaks. The bridge between the two is not a new table: it is the
`mapping.cidoc` field the datamodels ALREADY declare for every node type and
every edge type, read backwards. So a mapping serves both faces — the property
graph natively, the triplestore by projection — and neither is translated into
the other by hand.

Two honest consequences, both measured rather than assumed:

* the inverse is **many-to-one**: `A8 Stratigraphic Unit` is the CIDOC class of
  eight EM types (USVs, USVn, serSU, …). So the index returns candidates, in
  datamodel order, and a mapping that wants one of them says which;
* some CIDOC classes have **no EM type at all** (nothing in the datamodel claims
  them). Those are the `cidoc_direct` candidates: a mapping may still target them,
  and what comes out is a generic node that exists for the RDF projection. That is
  a declared half-measure, not a silent one.

## The schema, generalised (retro-compatible)

`table_settings` becomes `source_settings` with `format_type ∈ {sqlite, xlsx,
csv, xml}`; a column entry may carry `source_path` (for XML) and `cidoc` (the
class the author picked) beside `node_type`. **A mapping written before this
still reads**: `source_settings()` falls back to `table_settings`, and a mapping
with no `cidoc` anywhere behaves exactly as it did.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from importlib.resources import files
from typing import Any, Dict, List, Optional, Tuple

#: The mapping schema this module reads and writes. Bumped on a breaking change
#: to the shape, never on an addition — `source_path` and `cidoc` are additions.
SCHEMA_VERSION = "1"

#: The sources a mapping can describe. `xml` is the new one and it is why
#: `table_settings` had to become `source_settings`: an XML has no table.
FORMATS = ("sqlite", "xlsx", "csv", "xml")

#: How many example values a field carries. Three is enough to recognise a column
#: and few enough that a 200-column source stays one screen.
SAMPLE_COUNT = 3

_NODE_DATAMODEL = "s3Dgraphy_node_datamodel.json"
_CONNECTIONS_DATAMODEL = "s3Dgraphy_connections_datamodel.json"

#: The datamodel sections that declare node classes. Listed rather than
#: discovered because a section that appears tomorrow should show up in a diff,
#: not silently change what a picker offers.
_NODE_SECTIONS = (
    "node_types", "stratigraphic_nodes", "temporal_nodes", "group_nodes",
    "paradata_nodes", "reference_nodes", "visualization_nodes", "rights_nodes",
    "container_nodes", "hdto_nodes", "dtc_nodes", "narrative_nodes",
    "fallback_nodes",
)


def _load(filename: str) -> Dict[str, Any]:
    resource = files("s3dgraphy").joinpath("JSON_config", filename)
    with resource.open("r", encoding="utf-8") as handle:
        return json.load(handle)


# ── the schema, generalised ──────────────────────────────────────────────────

def source_settings(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """The source block of a mapping — `source_settings`, or `table_settings`.

    Retro-compatibility is the whole reason this is a function: every mapping on
    disk today says `table_settings`, and rewriting them would be a migration
    nobody asked for. New mappings say `source_settings`; both read.
    """
    settings = mapping.get("source_settings")
    if isinstance(settings, dict) and settings:
        out = dict(settings)
    else:
        out = dict(mapping.get("table_settings") or {})
    out.setdefault("format_type", "xlsx")
    return out


def format_of(mapping: Dict[str, Any]) -> str:
    return str(source_settings(mapping).get("format_type") or "xlsx").lower()


def normalize_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """A mapping with its CIDOC choices RESOLVED — a copy, never in place.

    For every column that names a `cidoc` class and no `node_type`, the EM type
    that implements it is filled in from the inverse index. When nothing does, the
    column is marked `cidoc_direct: true` and left without a node type: the
    importers will make a generic node for it, and the RDF projection is where it
    means something. Marking it is the point — a column that silently got no type
    would look like a mapping mistake for ever.
    """
    out = json.loads(json.dumps(mapping))          # deep copy, JSON-safe by construction
    out["source_settings"] = source_settings(mapping)
    index = cidoc_index()
    for name, column in (out.get("column_mappings") or {}).items():
        if not isinstance(column, dict):
            continue
        # A column that names a PROPERTY is a PropertyNode — and that string is
        # resolved from the datamodel here rather than typed in whatever tool is
        # authoring the mapping. An editor should not have to know the name of a
        # class to say "this field is a property of the record", and a literal in
        # a UI is a literal that outlives the datamodel that justified it.
        if column.get("property_name") and not column.get("node_type"):
            column["node_type"] = property_node_type()
        cidoc = str(column.get("cidoc") or "").strip()
        if not cidoc:
            continue
        if column.get("node_type"):
            continue                                # the author was explicit; leave it
        candidates = index["classes"].get(cidoc) or []
        if candidates:
            column["node_type"] = candidates[0]["em_type"]
            column["cidoc_resolved_from"] = cidoc
        else:
            column["cidoc_direct"] = True
    for relation in (out.get("relations") or []):
        if not isinstance(relation, dict):
            continue
        cidoc = str(relation.get("cidoc") or "").strip()
        if cidoc and not relation.get("edge_type"):
            props = index["properties"].get(cidoc) or []
            if props:
                relation["edge_type"] = props[0]["edge_type"]
                relation["cidoc_resolved_from"] = cidoc
    return out


@lru_cache(maxsize=1)
def property_node_type() -> str:
    """The node type a PROPERTY column produces, from the datamodel.

    Read rather than written down, so the one place the name lives is the file
    that defines it. Falls back to the literal only if the datamodel cannot be
    read at all — a mapping is more useful than a purity.
    """
    node_dm = _load(_NODE_DATAMODEL)
    for section in _NODE_SECTIONS:
        for _path, key, entry in _node_entries(node_dm.get(section) or {}):
            if str(entry.get("class") or key) == "PropertyNode":
                return str(entry.get("class") or key)
    return "PropertyNode"


def validate_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """`{ok, errors, warnings}` — structural, and it names the field.

    Errors are the things that make a mapping unusable (no columns, no id, an
    unknown format, a relation pointing at a column that is not mapped). Warnings
    are the things that make it *surprising*: an XML mapping with no
    `record_path`, a CIDOC class nothing in EM implements. The split matters
    because an editor should be able to save work in progress.
    """
    errors: List[str] = []
    warnings: List[str] = []
    columns = mapping.get("column_mappings")
    if not isinstance(columns, dict) or not columns:
        errors.append("column_mappings is missing or empty: a mapping with no "
                      "columns maps nothing")
        columns = {}
    settings = source_settings(mapping)
    fmt = str(settings.get("format_type") or "").lower()
    if fmt not in FORMATS:
        errors.append(f"source_settings.format_type {fmt!r} is not one of "
                      f"{list(FORMATS)}")
    if fmt in ("sqlite", "xlsx", "csv") and not (
            settings.get("table_name") or settings.get("sheet_name") is not None):
        warnings.append(f"a {fmt} source usually names its table/sheet "
                        f"(source_settings.table_name / sheet_name)")
    if fmt == "xml" and not settings.get("record_path"):
        warnings.append("an XML source needs source_settings.record_path — the "
                        "element that is one RECORD; without it every field would "
                        "have to be absolute and there would be no rows")

    ids = [name for name, c in columns.items()
           if isinstance(c, dict) and c.get("is_id")]
    if not ids:
        errors.append("no column carries is_id: the importer would not know what "
                      "identifies a record")
    elif len(ids) > 1:
        errors.append(f"more than one is_id column ({', '.join(sorted(ids))}): a "
                      f"record has one identity")

    index = cidoc_index()
    for name, column in columns.items():
        if not isinstance(column, dict):
            errors.append(f"column {name!r} is not an object")
            continue
        cidoc = str(column.get("cidoc") or "").strip()
        if cidoc and cidoc not in index["classes"] and not column.get("node_type"):
            warnings.append(f"column {name!r}: no EM node type implements "
                            f"{cidoc!r} — it will be a CIDOC-direct node "
                            f"(RDF projection only)")
        if fmt == "xml" and not column.get("source_path"):
            warnings.append(f"column {name!r}: an XML field needs source_path")
        target = column.get("target_id_column")
        if target and target not in columns:
            errors.append(f"column {name!r}: target_id_column {target!r} is not "
                          f"a mapped column")
    for i, relation in enumerate(mapping.get("relations") or []):
        if not isinstance(relation, dict):
            errors.append(f"relations[{i}] is not an object")
            continue
        for side in ("source_column", "target_column"):
            col = relation.get(side)
            if not col:
                errors.append(f"relations[{i}]: {side} is missing")
            elif col not in columns:
                errors.append(f"relations[{i}]: {side} {col!r} is not a mapped "
                              f"column")
        if not relation.get("edge_type") and not relation.get("cidoc"):
            errors.append(f"relations[{i}]: neither edge_type nor cidoc given")
            continue
        # …and the DATAMODEL decides whether that edge may run between those two
        # types. This is the check that makes CIDOC-first safe: resolving a
        # property to an edge type says nothing about whether the edge is legal
        # here, and a mapping that produced an edge the graph refuses would fail
        # at import time — long after the person who authored it left the screen.
        src = columns.get(relation.get("source_column")) or {}
        tgt = columns.get(relation.get("target_column")) or {}
        edge_type = relation.get("edge_type")
        if not edge_type and relation.get("cidoc"):
            resolved = index["properties"].get(str(relation["cidoc"])) or []
            edge_type = resolved[0]["edge_type"] if resolved else None
            if not edge_type:
                warnings.append(f"relations[{i}]: no EM edge implements "
                                f"{relation['cidoc']!r}")
        src_type = _resolved_type(src, index)
        tgt_type = _resolved_type(tgt, index)
        # …and the thing that surprises an author: outside a known set of
        # stratigraphic edges, `base_importer` ALSO turns a relation's target
        # column into a PropertyNode — so the same fact arrives twice, once as an
        # edge and once as "copre: 2". Declaring `is_relation: true` stops that
        # (honoured by the XML importer); saying so here is what makes it
        # findable, because the duplicate is not visibly wrong in the output.
        tgt_column = columns.get(relation.get("target_column")) or {}
        if (edge_type and edge_type not in _IMPORTER_SKIPS_PROPERTY
                and not tgt_column.get("property_name")
                and not tgt_column.get("is_relation")
                and not tgt_column.get("is_id")):
            warnings.append(
                f"relations[{i}]: column {relation.get('target_column')!r} will "
                f"ALSO become a property (the importer only skips "
                f"{len(_IMPORTER_SKIPS_PROPERTY)} stratigraphic edges) — add "
                f"\"is_relation\": true to that column to keep it edge-only")
        if edge_type and src_type and tgt_type:
            legal = {e["edge_type"] for e in allowed_edges(src_type, tgt_type)}
            if edge_type not in legal:
                errors.append(
                    f"relations[{i}]: the datamodel does not allow "
                    f"{edge_type!r} from {src_type} to {tgt_type} "
                    f"(allowed: {', '.join(sorted(legal)) or 'none'})")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


#: The edges whose target column `base_importer._process_properties` already
#: leaves alone. Mirrored, not imported, because it is a literal set inside a
#: method there — and mirrored rather than widened, because widening it would
#: change what every mapping on disk produces, which is E.D.'s call and not a
#: night's.
_IMPORTER_SKIPS_PROPERTY = frozenset({
    "overlies", "is_overlain_by", "cuts", "is_cut_by", "fills", "is_filled_by",
    "abuts", "is_abutted_by", "is_bonded_to", "is_physically_equal_to",
})


def _resolved_type(column: Dict[str, Any], index: Dict[str, Any]
                   ) -> Optional[str]:
    """The EM node type a column will produce — stated, or resolved from CIDOC."""
    if column.get("node_type"):
        return str(column["node_type"])
    cidoc = str(column.get("cidoc") or "").strip()
    candidates = index["classes"].get(cidoc) or []
    return candidates[0]["em_type"] if candidates else None


# ── the CIDOC inverse index ──────────────────────────────────────────────────

def _node_entries(section: Dict[str, Any], path: Tuple[str, ...] = ()
                  ) -> List[Tuple[Tuple[str, ...], str, Dict[str, Any]]]:
    """Every entry in a datamodel section that declares a class, subtypes
    included. Recursive because the stratigraphic types live one level down."""
    out: List[Tuple[Tuple[str, ...], str, Dict[str, Any]]] = []
    for key, value in (section or {}).items():
        if key.startswith("_") or not isinstance(value, dict):
            continue
        if "class" in value or "mapping" in value:
            out.append((path, key, value))
        subtypes = value.get("subtypes")
        if isinstance(subtypes, dict):
            out.extend(_node_entries(subtypes, path + (key,)))
    return out


@lru_cache(maxsize=1)
def _registry() -> Dict[str, Any]:
    """class name → `{parent, node_type}`, from the generated registry (the file
    `sync_node_datamodel --check` keeps honest)."""
    try:
        return _load("node_registry.generated.json").get("node_types") or {}
    except Exception:                              # noqa: BLE001 — a missing registry
        return {}


def _em_type_for(section: str, key: str, entry: Dict[str, Any]) -> str:
    """The string a MAPPING can carry for this datamodel entry.

    And it is not one thing, because the existing schema is not one thing: the
    importers read `"node_type": "US"` (a stratigraphic ABBREVIATION, resolved by
    `get_stratigraphic_node_class`) and `"node_type": "PropertyNode"` (a CLASS
    name, resolved through `Node.node_type_map`).

    So the rule follows the resolver, not the datamodel's convenience: the
    abbreviation ONLY for stratigraphic types (the one family whose abbreviations
    a resolver understands), the class name everywhere else. Measured before it
    was written this way — preferring the abbreviation everywhere resolved
    `E31 Document` to **DOC**, which `base_importer` cannot turn into a class, so
    the mapping would have produced an untyped node and looked like the author's
    mistake.
    """
    if section == "stratigraphic_nodes" and entry.get("abbreviation"):
        return str(entry["abbreviation"])
    return str(entry.get("class") or key)


@lru_cache(maxsize=1)
def cidoc_index() -> Dict[str, Any]:
    """The inverse of the datamodels' `mapping.cidoc` fields.

    Returns::

        {"classes":    {cidoc_class    → [ {em_type, class, cidoc, extension,
                                            section, label} … ]},
         "properties": {cidoc_property → [ {edge_type, cidoc, extension, label} … ]},
         "classes_without_em":    [ … ],      # declared, never silently dropped
         "properties_without_em": [ … ]}

    Many-to-one on purpose (see the module docstring): one CIDOC class can be the
    reading of several EM types, and the candidates keep the datamodel's order so
    the first is the one the datamodel presents first — a stable answer rather
    than a set's whim.
    """
    node_dm = _load(_NODE_DATAMODEL)
    conn_dm = _load(_CONNECTIONS_DATAMODEL)
    classes: Dict[str, List[Dict[str, Any]]] = {}
    for section in _NODE_SECTIONS:
        for path, key, entry in _node_entries(node_dm.get(section) or {}):
            mapping = entry.get("mapping") or {}
            cidoc = str(mapping.get("cidoc") or "").strip()
            if not cidoc:
                continue
            classes.setdefault(cidoc, []).append({
                "em_type": _em_type_for(section, key, entry),
                "class": str(entry.get("class") or key),
                "cidoc": cidoc,
                "extension": str(mapping.get("cidoc_extension")
                                 or mapping.get("extension_name") or "CIDOC-CRM"),
                "section": section,
                "path": "/".join(path + (key,)),
                "label": str(entry.get("label") or entry.get("class") or key),
            })
    properties: Dict[str, List[Dict[str, Any]]] = {}
    for name, entry in (conn_dm.get("edge_types") or {}).items():
        mapping = entry.get("mapping") or {}
        cidoc = str(mapping.get("cidoc") or "").strip()
        if not cidoc:
            continue
        properties.setdefault(cidoc, []).append({
            "edge_type": name,
            "cidoc": cidoc,
            "extension": str(mapping.get("cidoc_extension") or "CIDOC-CRM"),
            "label": str(entry.get("label") or name),
        })
    return {
        "classes": classes,
        "properties": properties,
        # An edge whose `mapping.cidoc` is empty is NOT unmapped: it is mapped
        # through an extension property (`extension_mapping`, e.g. CRMarchaeo's
        # AP11_has_physical_relation with a type tag). Saying "no CIDOC" about it
        # would be wrong, so it is reported as its own list.
        "properties_via_extension": sorted(
            name for name, entry in (conn_dm.get("edge_types") or {}).items()
            if not str((entry.get("mapping") or {}).get("cidoc") or "").strip()),
        "classes_without_em": [],
        "properties_without_em": [],
    }


def target_catalog(*, include_direct: bool = True) -> List[Dict[str, Any]]:
    """The classes a field may be mapped TO, as a picker wants them.

    One entry per CIDOC class, with the EM types that implement it (the first is
    the default) — or `cidoc_direct: true` when none does. Sorted by the CIDOC
    identifier, because a person looking for `E31` should find it where E-numbers
    live and not wherever the datamodel happened to declare it.
    """
    index = cidoc_index()
    out: List[Dict[str, Any]] = []
    for cidoc, candidates in index["classes"].items():
        out.append({
            "cidoc": cidoc,
            "em_type": candidates[0]["em_type"],
            "em_candidates": [c["em_type"] for c in candidates],
            "extension": candidates[0]["extension"],
            "label": candidates[0]["label"],
            "cidoc_direct": False,
        })
    if include_direct:
        for cidoc in index["classes_without_em"]:
            out.append({"cidoc": cidoc, "em_type": None, "em_candidates": [],
                        "extension": "CIDOC-CRM", "label": cidoc,
                        "cidoc_direct": True})
    return sorted(out, key=lambda e: _cidoc_sort_key(e["cidoc"]))


def _cidoc_sort_key(cidoc: str) -> Tuple[str, int, str]:
    """`E31 Document` sorts under E, at 31 — not as the string "E31" beside
    "E3" and "E310"."""
    text = str(cidoc).strip()
    letter = text[:1].upper() if text else "Z"
    digits = ""
    for char in text[1:]:
        if char.isdigit():
            digits += char
        else:
            break
    return (letter, int(digits) if digits else 0, text)


def allowed_edges(source_type: Optional[str] = None,
                  target_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """The edges the datamodel allows between two node types.

    THE SAME source the canvas's edge picker reads (`allowed_connections`), so a
    relation authored in a mapping cannot be one the graph would refuse. With one
    or both types omitted, every edge whose other side matches is returned — an
    editor filters as the author fills the row in.

    Class names AND stratigraphic abbreviations are accepted, because that is
    what the mapping schema carries: `US` is matched against
    `StratigraphicNode` through the class hierarchy, exactly as the graph's own
    validation resolves it.
    """
    conn_dm = _load(_CONNECTIONS_DATAMODEL)
    src_family = _family_of(source_type)
    tgt_family = _family_of(target_type)
    out: List[Dict[str, Any]] = []
    for name, entry in (conn_dm.get("edge_types") or {}).items():
        allowed = entry.get("allowed_connections") or {}
        sources = [str(s) for s in (allowed.get("source") or [])]
        targets = [str(t) for t in (allowed.get("target") or [])]
        if source_type and not _matches(src_family, sources):
            continue
        if target_type and not _matches(tgt_family, targets):
            continue
        mapping = entry.get("mapping") or {}
        out.append({
            "edge_type": name,
            "label": str(entry.get("label") or name),
            "cidoc": str(mapping.get("cidoc") or ""),
            "cidoc_extension": str(mapping.get("cidoc_extension") or ""),
            "extension_mapping": str(mapping.get("extension_mapping") or ""),
            "source": sources,
            "target": targets,
        })
    return sorted(out, key=lambda e: e["edge_type"])


def _family_of(node_type: Optional[str]) -> List[str]:
    """A node type plus every ancestor class the datamodel gives it — the names
    `allowed_connections` is written in. `US` becomes
    `[US, StratigraphicUnit, StratigraphicNode, Node]`."""
    if not node_type:
        return []
    registry = _registry()
    names = [str(node_type)]
    # a stratigraphic abbreviation → its class (the registry is keyed by class)
    for cls, info in registry.items():
        if str(info.get("node_type")) == str(node_type):
            names.append(cls)
    current = names[-1]
    seen = set(names)
    while current in registry:
        parent = registry[current].get("parent")
        if not parent or parent in seen:
            break
        names.append(parent)
        seen.add(parent)
        current = parent
    return names


def _matches(family: List[str], allowed: List[str]) -> bool:
    if not allowed:
        return False
    if "Node" in allowed or "*" in allowed:
        return True
    return any(name in allowed for name in family)


# ── what is in this source ───────────────────────────────────────────────────
#
# A person maps what they can SEE. A list of column names is not enough: half the
# columns in an archaeological table are called `d_interpretativa` or `stato_cons`
# and the only way to know what they hold is to look at three values. So every
# field carries samples, and that is the whole reason this function exists rather
# than a `SELECT name FROM pragma_table_info`.

#: extension → format. DATA, and exported, because it is not only this module's
#: business: a file PICKER (a native dialog's filter, a file browser's greying)
#: has to know which files are mappable, and a picker with its own list would be
#: a second answer to "can this be a source?" — the same rule as the node types.
SOURCE_EXTENSIONS = {
    "db": "sqlite", "sqlite": "sqlite", "sqlite3": "sqlite",
    "xlsx": "xlsx", "xlsm": "xlsx",
    "csv": "csv", "tsv": "csv",
    "xml": "xml", "rdf": "xml", "xsd": "xml",
}


def detect_format(path: str) -> str:
    """The format of a source, from its extension. Honest fallback: `xlsx`, the
    one this library has always assumed."""
    ext = str(path).rsplit(".", 1)[-1].lower() if "." in str(path) else ""
    return SOURCE_EXTENSIONS.get(ext, "xlsx")


def source_extensions() -> Dict[str, str]:
    """`{extension: format}` — what a picker may offer, from one place."""
    return dict(SOURCE_EXTENSIONS)


def source_fields(path: str, *, format_type: Optional[str] = None,
                  table: Optional[str] = None, record_path: Optional[str] = None,
                  samples: int = SAMPLE_COUNT) -> Dict[str, Any]:
    """The fields of a source, with example values.

    Returns ``{format, source, table?, tables?, record_path?, record_paths?,
    fields: [{name, source_path?, samples: [...], filled: n}]}``.

    `filled` is how many of the sampled records actually had a value — a column
    that is empty in every row it was asked about is a column an author should
    think twice about mapping, and saying "0 of 3" is more useful than an empty
    sample list.
    """
    fmt = (format_type or detect_format(path)).lower()
    if fmt == "sqlite":
        return _fields_sqlite(path, table, samples)
    if fmt == "csv":
        return _fields_csv(path, samples)
    if fmt == "xml":
        return _fields_xml(path, record_path, samples)
    return _fields_xlsx(path, table, samples)


def _field(name: str, values: List[Any], *, source_path: Optional[str] = None
           ) -> Dict[str, Any]:
    clean = ["" if v is None else str(v) for v in values]
    out: Dict[str, Any] = {
        "name": name,
        "samples": [v for v in clean][:SAMPLE_COUNT],
        "filled": sum(1 for v in clean if v.strip()),
        "seen": len(clean),
    }
    if source_path:
        out["source_path"] = source_path
    return out


def _fields_sqlite(path: str, table: Optional[str], samples: int) -> Dict[str, Any]:
    import sqlite3

    with sqlite3.connect(f"file:{os.path.abspath(path)}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        chosen = table or (tables[0] if tables else None)
        fields: List[Dict[str, Any]] = []
        if chosen:
            # the table name cannot be a bound parameter, so it is quoted — and
            # it comes from sqlite_master, not from a caller's string
            rows = [dict(r) for r in conn.execute(
                f'SELECT * FROM "{chosen}" LIMIT ?', (samples,))]
            columns = [d[0] for d in conn.execute(
                f'SELECT * FROM "{chosen}" LIMIT 0').description]
            for column in columns:
                fields.append(_field(column, [r.get(column) for r in rows]))
    return {"format": "sqlite", "source": path, "table": chosen,
            "tables": tables, "fields": fields}


def _fields_csv(path: str, samples: int) -> Dict[str, Any]:
    import csv

    with open(path, newline="", encoding="utf-8-sig") as handle:
        sniffed = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sniffed, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel                    # a one-column file is still a file
        reader = csv.DictReader(handle, dialect=dialect)
        rows = []
        for row in reader:
            rows.append(row)
            if len(rows) >= samples:
                break
        columns = list(reader.fieldnames or [])
    return {"format": "csv", "source": path,
            "delimiter": getattr(dialect, "delimiter", ","),
            "fields": [_field(c, [r.get(c) for r in rows]) for c in columns]}


def _fields_xlsx(path: str, sheet: Optional[str], samples: int) -> Dict[str, Any]:
    import pandas as pd                            # lazy: the xlsx extra

    book = pd.ExcelFile(path)
    sheets = list(book.sheet_names)
    chosen = sheet if sheet in sheets else (sheets[0] if sheets else None)
    fields: List[Dict[str, Any]] = []
    if chosen is not None:
        frame = book.parse(chosen, nrows=samples)
        for column in frame.columns:
            fields.append(_field(str(column), list(frame[column].values)))
    return {"format": "xlsx", "source": path, "table": chosen,
            "tables": sheets, "fields": fields}


def _fields_xml(path: str, record_path: Optional[str], samples: int
                ) -> Dict[str, Any]:
    """XML fields are PATHS, and the path that matters first is the record's.

    Which element is one record is not something a reader can know: `/site/us` and
    `/site/finds/find` are both plausible and only a person can say. So this
    reports the repeated elements it found — the candidates, most frequent first —
    and, once one is chosen, the fields RELATIVE to it (child elements and
    `@attributes`), which is what `source_path` means in a mapping.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(path)
    root = tree.getroot()
    counts: Dict[str, int] = {}

    def walk(element, path: str) -> None:
        for child in element:
            tag = _local(child.tag)
            here = f"{path}/{tag}"
            counts[here] = counts.get(here, 0) + 1
            walk(child, here)

    root_path = "/" + _local(root.tag)
    counts[root_path] = 1
    walk(root, root_path)
    # a RECORD is an element that repeats: one <site> is a container, twenty <us>
    # are the rows. Sorted by count so the answer is the same on every run.
    candidates = sorted(((p, n) for p, n in counts.items() if n > 1),
                        key=lambda pn: (-pn[1], pn[0]))
    chosen = record_path or (candidates[0][0] if candidates else root_path)
    records = _xml_records(root, root_path, chosen)
    fields: Dict[str, List[Any]] = {}
    for record in records[:max(samples, 1)]:
        for name, value in _xml_leaves(record).items():
            fields.setdefault(name, []).append(value)
    return {
        "format": "xml", "source": path,
        "record_path": chosen,
        "record_paths": [{"path": p, "count": n} for p, n in candidates],
        "records": len(records),
        "fields": [_field(name, values, source_path=name)
                   for name, values in sorted(fields.items())],
    }


def _local(tag: str) -> str:
    """`{http://ns}us` → `us`. Namespaces are a fact about the file, not about the
    field somebody is mapping, and carrying them into every path would make the
    editor unusable on any real XML."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _xml_records(root, root_path: str, record_path: str) -> List[Any]:
    """Every element at `record_path` (an absolute `/a/b/c` path)."""
    parts = [p for p in str(record_path).split("/") if p]
    if not parts:
        return [root]
    if parts[0] != _local(root.tag):
        return []
    if len(parts) == 1:
        return [root]
    out = [root]
    for step in parts[1:]:
        nxt: List[Any] = []
        for element in out:
            nxt.extend(child for child in element if _local(child.tag) == step)
        out = nxt
    return out


def _xml_leaves(record, prefix: str = "") -> Dict[str, str]:
    """One record flattened to `{relative_path: value}`.

    Attributes become `@name`, nested elements `child/grandchild` — the same
    shape a mapping's `source_path` uses, so what the editor shows is what the
    importer will read. Repeated siblings keep the FIRST value and are not
    silently joined: a mapping that needs the others needs a decision, and
    inventing a separator here would hide it.
    """
    out: Dict[str, str] = {}
    for name, value in (record.attrib or {}).items():
        out[f"{prefix}@{_local(name)}"] = value
    text = (record.text or "").strip()
    if text and prefix:
        out[prefix.rstrip("/")] = text
    for child in record:
        tag = _local(child.tag)
        here = f"{prefix}{tag}"
        child_text = (child.text or "").strip()
        if child_text and here not in out:
            out[here] = child_text
        for name, value in (child.attrib or {}).items():
            out.setdefault(f"{here}/@{_local(name)}", value)
        for key, value in _xml_leaves(child, f"{here}/").items():
            out.setdefault(key, value)
    return out


# ── applying: a proposal, or a fact ──────────────────────────────────────────
#
# Two modes, and they are not two implementations. The mapping runs the same way
# in both; what differs is one marker.
#
#   volatile → the nodes are IN the graph (visible on a canvas, listed in a
#              table) and OUT of the saved document until somebody bakes them.
#              The marker is `data.aux_volatile` — THE SAME KEY the connector
#              seam and EMStudio already use (`contract/connector.VOLATILE_KEY`,
#              `frontend/src/volatile.ts`), so an existing bake promotes them and
#              nothing needed a second concept.
#   bake     → written straight in, like any import.
#
# Reusing the key rather than inventing a "mapping_volatile" is the whole point:
# a mapped auxiliary and an ingest proposal are the same STATE, and two markers
# would need two bakes.

#: format → the importer that reads it. Data, so an unsupported format is a
#: sentence naming what IS supported instead of an AttributeError.
_IMPORTERS = {
    "xml": ("..importer.xml_importer", "XMLImporter"),
    "xlsx": ("..importer.mapped_xlsx_importer", "MappedXLSXImporter"),
    "sqlite": ("..importer.pyarchinit_importer", "PyArchInitImporter"),
}


def apply_mapping(mapping: Dict[str, Any], source: str, *,
                  graph: Any = None, mode: str = "volatile",
                  mapping_name: Optional[str] = None,
                  injector: Optional[str] = None) -> Dict[str, Any]:
    """Run a mapping over a source. `mode` is ``"volatile"`` or ``"bake"``.

    Returns ``{ok, mode, format, rows, nodes_added, edges_added, volatile,
    injector, warnings, errors}`` — counts of what THIS call added, not of what
    the graph now holds, because "did my mapping do anything?" is the question an
    editor's Apply button has to answer.

    The graph is optional: without one a fresh graph is made and returned in
    `graph`, which is what a preview wants.
    """
    if mode not in ("volatile", "bake"):
        raise ValueError(f"mode must be 'volatile' or 'bake', got {mode!r}")
    verdict = validate_mapping(mapping)
    if not verdict["ok"]:
        return {"ok": False, "mode": mode, "errors": verdict["errors"],
                "warnings": verdict["warnings"], "rows": 0,
                "nodes_added": 0, "edges_added": 0}
    normalized = normalize_mapping(mapping)
    fmt = format_of(normalized)
    if fmt == "csv":
        # DECLARED: there is no csv importer in this library, and writing a
        # fourth one tonight would be a fourth place the mapping rules live.
        # A csv is read as a table by the xlsx path only when a caller converts
        # it; until then the refusal says so instead of half-working.
        return {"ok": False, "mode": mode, "rows": 0, "nodes_added": 0,
                "edges_added": 0, "warnings": verdict["warnings"],
                "errors": ["csv apply is not implemented: this library has no csv "
                           "importer yet (the fields/authoring side does work). "
                           "Save the sheet as .xlsx, or map the sqlite/xml source."]}
    if fmt not in _IMPORTERS:
        return {"ok": False, "mode": mode, "rows": 0, "nodes_added": 0,
                "edges_added": 0, "warnings": verdict["warnings"],
                "errors": [f"no importer for format {fmt!r} "
                           f"(have: {', '.join(sorted(_IMPORTERS))})"]}

    from ..graph import Graph

    target = graph if graph is not None else Graph(graph_id="mapping_preview")
    before_nodes = {n.node_id for n in target.nodes}
    before_edges = {e.edge_id for e in target.edges}

    module_name, class_name = _IMPORTERS[fmt]
    import importlib

    module = importlib.import_module(module_name, package=__package__)
    importer_class = getattr(module, class_name)
    warnings: List[str] = list(verdict["warnings"])
    try:
        if fmt == "xml":
            importer = importer_class(source, mapping=normalized,
                                      existing_graph=target)
        else:
            # the table importers load their mapping BY NAME from the registry;
            # an inline mapping is set on the instance after construction, which
            # is the seam they already have (`self.mapping`)
            if not mapping_name:
                return {"ok": False, "mode": mode, "rows": 0, "nodes_added": 0,
                        "edges_added": 0, "warnings": warnings,
                        "errors": [f"a {fmt} source needs mapping_name (the "
                                   f"table importers load their mapping from the "
                                   f"registry) — save the mapping first, then apply"]}
            importer = importer_class(source, mapping_name,
                                      existing_graph=target)
            importer.mapping = normalized
        importer.parse()
        warnings.extend(getattr(importer, "warnings", []) or [])
    except Exception as exc:                       # noqa: BLE001 — surfaced, not raised
        return {"ok": False, "mode": mode, "rows": 0, "nodes_added": 0,
                "edges_added": 0, "warnings": warnings,
                "errors": [f"{type(exc).__name__}: {exc}"]}

    added_nodes = [n for n in target.nodes if n.node_id not in before_nodes]
    added_edges = [e for e in target.edges if e.edge_id not in before_edges]
    stamp = injector or f"mapping:{mapping_name or 'inline'}"
    if mode == "volatile":
        from ..contract.connector import VOLATILE_KEY

        for node in added_nodes:
            data = getattr(node, "data", None)
            if not isinstance(data, dict):
                data = {}
                setattr(node, "data", data)
            data[VOLATILE_KEY] = stamp
    return {
        "ok": True, "mode": mode, "format": fmt,
        "rows": int(getattr(importer, "rows_read", 0) or 0),
        "nodes_added": len(added_nodes),
        "edges_added": len(added_edges),
        "volatile": mode == "volatile",
        "injector": stamp if mode == "volatile" else None,
        "graph": target,
        "warnings": warnings,
        "errors": [],
    }
