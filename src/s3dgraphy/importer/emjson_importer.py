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
#: schema version written by files that predate the field (S2a)
LEGACY_SCHEMA_VERSION = 0

_NEUTRAL_DEFAULTS: Dict[str, Any] = {"start_time": 0, "end_time": 0}


class EmJsonImportError(ValueError):
    pass


def schema_version_of(doc: Dict[str, Any]) -> int:
    """The em.json SCHEMA version of a document, tolerantly.

    A file written before the field existed reports ``LEGACY_SCHEMA_VERSION``
    (0) — that is the honest answer, not an error: those documents are perfectly
    readable, they simply predate any schema evolution. Anything unparseable is
    read as legacy too, on the same principle: the reader never refuses a
    document over a version field it cannot make sense of. See
    ``exporter.emjson_exporter.SCHEMA_VERSION`` for the current value and its
    history."""
    header = doc.get("header") or {}
    raw = header.get("schema_version", LEGACY_SCHEMA_VERSION)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return LEGACY_SCHEMA_VERSION


def _instantiate(node_type: str, payload: Dict[str, Any],
                 warnings: List[str]):
    cls = Node.node_type_map.get(node_type)
    if cls is None:
        # ``Node`` is not in the map because it is the base class, not a type:
        # a node serialised with it is one the source could not type, which is
        # a real problem but NOT an unknown-type one — calling it "unknown"
        # was factually wrong, and it double-reported what `recompute_warnings`
        # now states properly as an untyped node (F). A genuinely unrecognised
        # type still warns: that is a version gap and the reader must say so.
        if node_type != "Node":
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

    # Schema version: read, never refused. A file from the future is read anyway
    # — the format is additive, so unknown fields are simply ignored — but the
    # reader says so, because silently dropping content the writer meant to
    # carry is worse than a warning.
    from ..exporter.emjson_exporter import SCHEMA_VERSION as _CURRENT_SCHEMA
    schema_version = schema_version_of(doc)
    if schema_version > _CURRENT_SCHEMA:
        warnings.append(
            f"em.json schema_version {schema_version} is newer than this "
            f"s3dgraphy knows ({_CURRENT_SCHEMA}): reading it anyway, fields "
            f"introduced after {_CURRENT_SCHEMA} are ignored")

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
    # recorded so a consumer (and the S6 version banner) can tell what it read
    graph.attributes["emjson_schema_version"] = schema_version
    graph.attributes["emjson_format_version"] = version

    # Graph.__init__ auto-creates a default geo_position node. When the
    # document carries its own geo_position node(s), drop the synthetic one
    # so the round-trip is count-stable (no phantom +1 node).
    #
    # Dropped UNCONDITIONALLY, and that is a fix (G1). The previous version kept
    # the synthetic node whenever the document's own geo node had the SAME id —
    # `geo_<graph_id>`, which is exactly the id the exporter and EMTools write, so
    # the normal case. `add_node` without `overwrite` returns the existing node
    # and discards the incoming one, so the document's epsg/shift were silently
    # replaced by the defaults (4326, 0, 0, 0) on every load: the georeferencing
    # anchor did not survive a round trip at all. Verified before and after.
    incoming_types = {n.get("node_type") for n in gsec.get("nodes", [])}
    if "geo_position" in incoming_types:
        auto_geo_id = f"geo_{gsec['graph_id']}"
        graph.nodes = [n for n in graph.nodes if n.node_id != auto_geo_id]

    for payload in gsec.get("nodes", []):
        if not payload.get("id") or not payload.get("node_type"):
            warnings.append(f"skipped node without id/node_type: {payload}")
            continue
        node = _instantiate(payload["node_type"], payload, warnings)
        # schema <2 spelled the canonical-document flags "master": carry them
        # over so the in-memory graph speaks one language whatever wrote the file
        from ..nodes.document_node import normalise_canonical_attributes
        normalise_canonical_attributes(getattr(node, "attributes", None))
        normalise_canonical_attributes(getattr(node, "data", None))
        graph.add_node(node)

    for e in gsec.get("edges", []):
        try:
            edge = graph.add_edge(
                e.get("id") or f"{e['source']}__{e['edge_type']}__{e['target']}",
                e["source"], e["target"], e["edge_type"],
            )
        except Exception as exc:
            warnings.append(f"skipped edge {e.get('id')!r}: {exc}")
            continue
        # schema 1+: per-edge attributes (e.g. the paradata propagation's
        # derived / derived_from). Absent on legacy files, which is fine.
        attrs = e.get("attributes")
        if isinstance(attrs, dict) and attrs and edge is not None:
            edge.attributes.update(attrs)

    return graph, warnings


def import_emjson(filepath: str) -> Tuple[Graph, List[str]]:
    """Load a .em.json file. Returns (graph, warnings)."""
    with open(Path(filepath), encoding="utf-8") as f:
        doc = json.load(f)
    return parse_emjson(doc)
