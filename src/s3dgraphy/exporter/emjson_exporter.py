"""
.em.json v1 exporter — the native Extended Matrix document format.

Frozen 2026-07-11 (format decision record in the EMStudio repository,
docs/emjson-v1-draft.md). Structure:

    header  — format name, semver, generator, datamodel_versions,
              ontology_versions (mirrors referenced_ontology_versions).
    graph   — FLAT canonical property graph: nodes[] (id, node_type, name,
              description, data{}) and edges[] (id, edge_type, source,
              target), plus graph-level metadata in data{}.
    layout  — optional, reconstructable (EMStudio's layout engine output);
              this exporter emits it only when passed in.

Design decision (v1 freeze): the graph section is FLAT, not bucketed.
The bucketed Heriverse payload (json_exporter.py) remains available as the
legacy transitional format for Heriverse 1.5.x; Heriverse 1.6 adopts
.em.json. Rationale: one canonical shape for editor, library and web
consumers; the bucket-enumeration family of bugs (node types silently
dropped when a bucket list lags behind the datamodel) is structurally
impossible on a flat list.

Determinism: keys are emitted sorted (sort_keys=True); node and edge order
follows graph insertion order. Same graph → same bytes (CI-diffable).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..graph import Graph

FORMAT_NAME = "em.json"
FORMAT_VERSION = "1.0"

# Node attributes lifted into data{} when present on the instance and not
# already carried by node.data. Keeps the flat format lossless for the
# type-specific fields the classes store as plain attributes.
_LIFTED_ATTRS = (
    "start_time", "end_time", "color",          # EpochNode
    "value", "property_type", "url",             # PropertyNode / LinkNode
    "source",                                     # ExtractorNode
    "symbol", "label",                            # class-level display metadata
)


def _to_text(value: Any) -> Optional[str]:
    """graph.name / node.name may be dict (multilang) or str."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("default") or next(iter(value.values()), None)
    if isinstance(value, str):
        return value
    return str(value)


def _json_safe(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


def _node_payload(node: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    node_data = getattr(node, "data", None)
    if isinstance(node_data, dict):
        data.update({k: v for k, v in node_data.items() if _json_safe(v)})
    # generic per-node attribute store (the GraphML importer writes Master/
    # Instance document metadata here: is_master, certainty_class,
    # border_color, instances) — lossless lift, node.data wins on clashes
    node_attrs = getattr(node, "attributes", None)
    if isinstance(node_attrs, dict):
        for k, v in node_attrs.items():
            if k not in data and v not in (None, "") and _json_safe(v):
                data[k] = v
    for attr in _LIFTED_ATTRS:
        if attr in data:
            continue
        val = getattr(node, attr, None)
        # skip class-level defaults that are not real content
        if val is None or val == "" or not _json_safe(val):
            continue
        data[attr] = val
    payload: Dict[str, Any] = {
        "id": node.node_id,
        "node_type": getattr(node, "node_type", type(node).__name__),
    }
    name = _to_text(getattr(node, "name", None))
    if name:
        payload["name"] = name
    desc = _to_text(getattr(node, "description", None))
    if desc:
        payload["description"] = desc
    if data:
        payload["data"] = data
    return payload


def _datamodel_versions() -> Dict[str, str]:
    from ..nodes.base_node import load_json_mapping
    out: Dict[str, str] = {}
    node_dm = load_json_mapping("s3Dgraphy_node_datamodel.json")
    if node_dm.get("s3Dgraphy_data_model_version"):
        out["nodes"] = node_dm["s3Dgraphy_data_model_version"]
    conn_dm = load_json_mapping("s3Dgraphy_connections_datamodel.json")
    if conn_dm.get("s3Dgraphy_connections_model_version"):
        out["connections"] = conn_dm["s3Dgraphy_connections_model_version"]
    qualia = load_json_mapping("em_qualia_types.json")
    meta = qualia.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("version"):
        out["qualia"] = meta["version"]
    return out


def _ontology_versions() -> Dict[str, str]:
    from ..nodes.base_node import load_json_mapping
    node_dm = load_json_mapping("s3Dgraphy_node_datamodel.json")
    refs = node_dm.get("referenced_ontology_versions") or {}
    return {
        k: v.get("version", "")
        for k, v in refs.items()
        if isinstance(v, dict) and not k.startswith("_")
    }


def build_emjson(graph: Graph, layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the .em.json v1 document for an in-memory graph."""
    try:
        from .. import __version__ as _s3d_version
    except Exception:  # pragma: no cover
        _s3d_version = "unknown"

    nodes: List[Dict[str, Any]] = [_node_payload(n) for n in graph.nodes]
    edges: List[Dict[str, Any]] = [
        {
            "id": e.edge_id,
            "edge_type": e.edge_type,
            "source": e.edge_source,
            "target": e.edge_target,
        }
        for e in graph.edges
    ]

    graph_section: Dict[str, Any] = {
        "graph_id": graph.graph_id,
        "nodes": nodes,
        "edges": edges,
    }
    gname = _to_text(getattr(graph, "name", None))
    if gname:
        graph_section["name"] = gname
    gdesc = _to_text(getattr(graph, "description", None))
    if gdesc:
        graph_section["description"] = gdesc
    gdata = getattr(graph, "data", None)
    if isinstance(gdata, dict) and gdata:
        graph_section["data"] = {k: v for k, v in gdata.items() if _json_safe(v)}

    doc: Dict[str, Any] = {
        "header": {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "generator": {"tool": "s3dgraphy", "version": str(_s3d_version)},
            "datamodel_versions": _datamodel_versions(),
            "ontology_versions": _ontology_versions(),
        },
        "graph": graph_section,
    }
    if layout:
        doc["layout"] = layout
    return doc


def export_emjson(graph: Graph, output_path: str,
                  layout: Optional[Dict[str, Any]] = None) -> str:
    """Serialize `graph` to `.em.json` at output_path. Returns the path."""
    doc = build_emjson(graph, layout=layout)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return str(path)
