"""
.em.json v1 importer — reads the native Extended Matrix document format
back into an s3dgraphy Graph. Counterpart of exporter/emjson_exporter.py.

Lives ALONGSIDE the GraphML importer (decision 2026-07-11): GraphML remains
the legacy one-way ingestion path until EMStudio replaces yEd; .em.json is
the native round-trip format.

Node instantiation strategy: `Node.node_type_map` (populated automatically
by `Node.__init_subclass__`) resolves node_type → class; constructors are
bound generically via `inspect.signature`, drawing extra required
parameters (e.g. EpochNode.start_time) from the node's data{} and falling
back to neutral defaults. Unknown node types degrade to the base Node with
a warning rather than failing the import (forward compatibility).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..graph import Graph
from ..nodes.base_node import Node
# Importing the nodes package populates Node.node_type_map via
# __init_subclass__ side effects.
from .. import nodes as _nodes_module  # noqa: F401

FORMAT_NAME = "em.json"
SUPPORTED_MAJOR = 1

_NEUTRAL_DEFAULTS: Dict[str, Any] = {"start_time": 0, "end_time": 0}


class EmJsonImportError(ValueError):
    pass


def _instantiate(node_type: str, payload: Dict[str, Any],
                 warnings: List[str]):
    cls = Node.node_type_map.get(node_type)
    if cls is None:
        warnings.append(
            f"unknown node_type '{node_type}' for node "
            f"'{payload.get('id')}': degraded to base Node"
        )
        cls = Node

    data = dict(payload.get("data") or {})
    kwargs: Dict[str, Any] = {}
    sig = inspect.signature(cls.__init__)
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        if pname == "node_id":
            kwargs[pname] = payload["id"]
        elif pname == "name":
            kwargs[pname] = payload.get("name", payload["id"])
        elif pname == "description":
            kwargs[pname] = payload.get("description", "")
        elif pname in data:
            kwargs[pname] = data[pname]
        elif param.default is not inspect.Parameter.empty:
            continue  # optional, leave default
        elif pname in _NEUTRAL_DEFAULTS:
            kwargs[pname] = _NEUTRAL_DEFAULTS[pname]
        else:
            kwargs[pname] = None
    try:
        node = cls(**kwargs)
    except Exception as exc:  # pragma: no cover — defensive
        warnings.append(
            f"constructor failed for '{payload.get('id')}' "
            f"({node_type}): {exc}; degraded to base Node"
        )
        node = Node(payload["id"], payload.get("name", payload["id"]),
                    payload.get("description", ""))

    # Aux-lifecycle bookkeeping keys live in node.attributes (where
    # is_injected / bake_injector / the volatile-save policy read them), not in
    # node.data. The emjson exporter lifts node.attributes into data{}, so on
    # import we must route these back to node.attributes — otherwise the
    # injected_by / _aux_overrides lifecycle does not survive an em.json
    # round-trip (e.g. the em-bridge inject-dtc → bake-dtc flow).
    _ATTR_KEYS = ("injected_by", "_aux_overrides")

    # Restore remaining data keys: known attributes as attributes, the rest
    # into node.data (creating it when the class has none).
    consumed = set(kwargs) | {"id", "name", "description"}
    leftover = {k: v for k, v in data.items() if k not in consumed}
    if leftover:
        if not isinstance(getattr(node, "data", None), dict):
            node.data = {}
        if not isinstance(getattr(node, "attributes", None), dict):
            node.attributes = {}
        for k, v in leftover.items():
            if k in _ATTR_KEYS:
                node.attributes[k] = v
            elif hasattr(node, k) and not isinstance(getattr(node, k), dict):
                try:
                    setattr(node, k, v)
                except Exception:
                    node.data[k] = v
            else:
                node.data[k] = v
    return node


def parse_emjson(doc: Dict[str, Any]) -> Tuple[Graph, List[str]]:
    """Parse an already-loaded .em.json dict into a Graph."""
    warnings: List[str] = []

    header = doc.get("header") or {}
    if header.get("format") != FORMAT_NAME:
        raise EmJsonImportError(
            f"not an em.json document (format={header.get('format')!r})")
    version = str(header.get("version", ""))
    major = version.split(".")[0]
    if not major.isdigit() or int(major) != SUPPORTED_MAJOR:
        raise EmJsonImportError(f"unsupported em.json version '{version}'")

    gsec = doc.get("graph") or {}
    if not gsec.get("graph_id"):
        raise EmJsonImportError("graph.graph_id is missing")

    graph = Graph(graph_id=gsec["graph_id"])
    if gsec.get("name"):
        graph.name = {"default": gsec["name"]}
    if gsec.get("description"):
        graph.description = {"default": gsec["description"]}
    if isinstance(gsec.get("data"), dict):
        graph.data.update(gsec["data"])

    # Graph.__init__ auto-creates a default geo_position node. When the
    # document carries its own geo_position node(s), drop the synthetic one
    # so the round-trip is count-stable (no phantom +1 node).
    incoming_types = {n.get("node_type") for n in gsec.get("nodes", [])}
    if "geo_position" in incoming_types:
        auto_geo_id = f"geo_{gsec['graph_id']}"
        incoming_ids = {n.get("id") for n in gsec.get("nodes", [])}
        if auto_geo_id not in incoming_ids:
            graph.nodes = [n for n in graph.nodes if n.node_id != auto_geo_id]

    for payload in gsec.get("nodes", []):
        if not payload.get("id") or not payload.get("node_type"):
            warnings.append(f"skipped node without id/node_type: {payload}")
            continue
        node = _instantiate(payload["node_type"], payload, warnings)
        graph.add_node(node)

    for e in gsec.get("edges", []):
        try:
            graph.add_edge(
                e.get("id") or f"{e['source']}__{e['edge_type']}__{e['target']}",
                e["source"], e["target"], e["edge_type"],
            )
        except Exception as exc:
            warnings.append(f"skipped edge {e.get('id')!r}: {exc}")

    return graph, warnings


def import_emjson(filepath: str) -> Tuple[Graph, List[str]]:
    """Load a .em.json file. Returns (graph, warnings)."""
    with open(Path(filepath), encoding="utf-8") as f:
        doc = json.load(f)
    return parse_emjson(doc)
