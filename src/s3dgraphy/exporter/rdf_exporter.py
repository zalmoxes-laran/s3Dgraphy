"""
RDF Exporter for s3Dgraphy graphs.

Serializes s3Dgraphy graphs to RDF (Turtle, N-Triples, JSON-LD, RDF/XML)
using the CIDOC-CRM + HDT-O + EM ontology declared in companion files:

  * em.ttl              — Extended Matrix ontology (em: classes & properties)
  * hdto_extension.ttl  — HDT-O containment / granularity properties

Three driving datamodels are read at construction time as the single
source of truth — no class/edge/qualia type is hard-coded here:

  * s3Dgraphy_node_datamodel.json
      → class → IRI mapping via em_extension.uri (preferred) or mapping.cidoc.
        Multi-typing via em_extension.subclass_of (emitted as additional
        rdf:type triples so a CRM-only reader still sees the CRM superclasses).

  * s3Dgraphy_connections_datamodel.json
      → edge_type → predicate IRI.
        AP11_has_physical_relation discrimination via type_tag → em:abuts /
        em:cuts / em:fills / em:overlies / em:bondedTo / em:physicallyEquals
        subproperties (SPARQL-friendly: queries can be specific or fall
        back to AP11 via subproperty inference).
        Deprecated edges (deprecated: true) are skipped on write — see
        has_timebranch which is canonicalised to is_in_timebranch.

  * em_qualia_types.json
      → PropertyNode conditional mapping: a property's CIDOC class is
        looked up by property_type (height → E54_Dimension, color → E55_Type,
        aesthetic_value → crminf:I4_Proposition_Set, etc.).

Named-graph wrapping:
  Each s3Dgraphy Graph is serialized into its own named graph IRI of the
  form <base>/graph/<graph_id>, anchored by an em:EMGraph triple plus the
  graph-level metadata (default author, license).

Author:  Emanuele Demetrescu
Version: 1.6.0 — initial RDF export pipeline
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from rdflib import ConjunctiveGraph, Literal, Namespace, URIRef
    from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, XSD
except ImportError as _e:  # pragma: no cover
    raise ImportError(
        "RDFExporter requires rdflib. Install with: pip install rdflib"
    ) from _e

from ..graph import Graph as S3DGraph
from ..multigraph.multigraph import get_all_graph_ids, get_graph


# ─────────────────────────────────────────────────────────────────────────────
# Namespaces
# ─────────────────────────────────────────────────────────────────────────────

EM         = Namespace("https://w3id.org/em/ontology#")
S3D        = Namespace("https://w3id.org/em/s3dgraphy#")
CRM        = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
CRMINF     = Namespace("http://www.cidoc-crm.org/extensions/crminf/")
CRMARCHAEO = Namespace("http://www.cidoc-crm.org/extensions/crmarchaeo/")
CRMDIG     = Namespace("http://www.cidoc-crm.org/extensions/crmdig/")
CRMGEO     = Namespace("http://www.cidoc-crm.org/extensions/crmgeo/")
HDTO       = Namespace("https://w3id.org/hdto/ontology#")

DEFAULT_BASE_URI = "https://example.org/em/"

PREFIX_MAP: Dict[str, Namespace] = {
    "em":         EM,
    "s3d":        S3D,
    "crm":        CRM,
    "crminf":     CRMINF,
    "crmarchaeo": CRMARCHAEO,
    "crmdig":     CRMDIG,
    "crmgeo":     CRMGEO,
    "hdto":       HDTO,
    "prov":       PROV,
    "dcterms":    DCTERMS,
    "rdfs":       Namespace(str(RDFS)),
    "owl":        Namespace(str(OWL)),
    "xsd":        Namespace(str(XSD)),
}


# ─────────────────────────────────────────────────────────────────────────────
# IRI resolution helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_prefixed(name: Optional[str]) -> Optional[URIRef]:
    """
    Resolve 'prefix:LocalName' or a bare CRM code (e.g. 'A2_Stratigraphic_Volume_Unit',
    'P67_refers_to') to a URIRef using PREFIX_MAP.

    Heuristics for un-prefixed codes (legacy datamodel fields):
        A<digit> → crmarchaeo;   I<digit> → crminf;   D<digit> → crmdig;
        SP / Q / OA prefixes → crmgeo;
        E<digit> / P<digit>   → crm core.

    Returns None for empty, non-string or unrecognised input.
    """
    if not name or not isinstance(name, str):
        return None
    name = name.strip()
    if not name:
        return None

    # Explicit prefix
    if ":" in name and not name.startswith(("http://", "https://")):
        prefix, local = name.split(":", 1)
        ns = PREFIX_MAP.get(prefix)
        return ns[local] if ns else None

    # Absolute URI passthrough
    if name.startswith(("http://", "https://")):
        return URIRef(name)

    # Datamodel uses human strings like "A2 Stratigraphic Volume Unit" —
    # the canonical CRM URI joins the code and the label with underscores
    # ("crmarchaeo:A2_Stratigraphic_Volume_Unit"). Normalise spaces so both
    # "E54 Dimension" and "E54_Dimension" resolve identically.
    full = name.replace(" ", "_")
    code = full.split("_")[0]

    head = code[:2]
    if len(head) >= 2 and head[1].isdigit():
        first = head[0]
        if first == "A":
            return CRMARCHAEO[full]
        if first == "I":
            return CRMINF[full]
        if first == "D":
            return CRMDIG[full]
        if first in ("E", "P"):
            return CRM[full]
    if code[:2] in ("SP", "OA") or code[:1] == "Q":
        return CRMGEO[full]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# AP11 type_tag → em: subproperty (CRMarchaeo physical relation discrimination)
# ─────────────────────────────────────────────────────────────────────────────

AP11_SUBPROPS: Dict[str, URIRef] = {
    "abuts":        EM.abuts,
    "cuts":         EM.cuts,
    "fills":        EM.fills,
    "overlies":     EM.overlies,
    "bonded to":    EM.bondedTo,
    "is bonded to": EM.bondedTo,
    "equals":       EM.physicallyEquals,
}


# ─────────────────────────────────────────────────────────────────────────────
# Datamodel loader (caches the three JSON datamodels)
# ─────────────────────────────────────────────────────────────────────────────

class _Datamodel:
    """Reads and indexes the three JSON datamodels once per exporter instance."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "JSON_config"
        self.config_dir = Path(config_dir)

        self.node_datamodel        = self._load_json("s3Dgraphy_node_datamodel.json")
        self.connections_datamodel = self._load_json("s3Dgraphy_connections_datamodel.json")
        self.qualia_types          = self._load_json("em_qualia_types.json")

        self._node_class_index: Dict[str, Dict[str, Any]] = {}
        self._build_node_class_index(self.node_datamodel)

        self._qualia_class_index: Dict[str, str] = {}
        self._build_qualia_index(self.qualia_types)

    def _load_json(self, name: str) -> Dict[str, Any]:
        path = self.config_dir / name
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _build_node_class_index(self, node: Any) -> None:
        """Recursive descent collecting every entry with a 'class' field."""
        if isinstance(node, dict):
            cls = node.get("class")
            if isinstance(cls, str):
                self._node_class_index[cls] = node
            for v in node.values():
                self._build_node_class_index(v)
        elif isinstance(node, list):
            for item in node:
                self._build_node_class_index(item)

    def _build_qualia_index(self, qualia_doc: Dict[str, Any]) -> None:
        for cat in qualia_doc.get("qualia_categories", []):
            for sub in (cat.get("subcategories") or {}).values():
                for q in sub.get("qualia", []) or []:
                    qid = q.get("id")
                    mappings = q.get("mappings") or {}
                    crm_class = mappings.get("cidoc_crm")
                    if qid and crm_class:
                        self._qualia_class_index[qid] = crm_class

    # ─── public lookups ─────────────────────────────────────────────────────

    def get_node_primary_iri(self, class_name: str) -> Optional[URIRef]:
        """em_extension.uri preferred; falls back to mapping.cidoc."""
        entry = self._node_class_index.get(class_name)
        if not entry:
            return None
        ext = entry.get("em_extension") or {}
        uri = ext.get("uri")
        if uri:
            resolved = _resolve_prefixed(uri)
            if resolved:
                return resolved
        mapping = entry.get("mapping") or {}
        return _resolve_prefixed(mapping.get("cidoc"))

    def get_node_superclasses(self, class_name: str) -> List[URIRef]:
        """All em_extension.subclass_of IRIs (multi-typing)."""
        entry = self._node_class_index.get(class_name)
        if not entry:
            return []
        ext = entry.get("em_extension") or {}
        result: List[URIRef] = []
        for sc in ext.get("subclass_of", []) or []:
            iri = _resolve_prefixed(sc)
            if iri is not None:
                result.append(iri)
        return result

    def get_edge_mapping(self, edge_type: str) -> Tuple[Optional[URIRef], Optional[str], bool]:
        """
        Returns (predicate_iri, type_tag, deprecated).

        type_tag is set for the AP11 family — caller resolves the specific
        subproperty via AP11_SUBPROPS. deprecated edges should be skipped on
        write (already canonicalised aliases like has_timebranch).
        """
        edges = self.connections_datamodel.get("edge_types", {})
        entry = edges.get(edge_type) or {}
        if not entry:
            return None, None, False
        deprecated = bool(entry.get("deprecated"))
        mapping = entry.get("mapping") or {}
        type_tag = mapping.get("type_tag")
        cidoc = mapping.get("cidoc")
        # AP11 family: prefer the generic AP11 predicate; caller adds subproperty.
        if type_tag:
            return CRMARCHAEO.AP11_has_physical_relation, type_tag, deprecated
        return _resolve_prefixed(cidoc), None, deprecated

    def get_qualia_crm_iri(self, property_type: Optional[str]) -> Optional[URIRef]:
        """Resolve a property_type string to its CIDOC class IRI.

        Lookup strategy (graceful, three steps):
          1. Exact match against em_qualia_types.json `id` (e.g.
             "absolute_time_start", "height", "color").
          2. Last segment after dot — handles EM yEd convention where
             properties are labelled with a category prefix
             (e.g. "Dimension.height" → "height", "Spatial.elevation" →
             "elevation").
          3. Lowercase match — handles minor case mismatches between
             graphml labels and qualia ids (e.g. "Height" → "height").

        Returns None if no strategy matches; the caller (typically
        ``_compute_primary_iri``) falls back to the generic PropertyNode
        default mapping.
        """
        if not property_type:
            return None
        # 1) Exact match
        crm = self._qualia_class_index.get(property_type)
        if crm:
            return _resolve_prefixed(crm)
        # 2) Last segment after dot (yEd category prefix convention)
        if "." in property_type:
            tail = property_type.rsplit(".", 1)[-1]
            crm = self._qualia_class_index.get(tail)
            if crm:
                return _resolve_prefixed(crm)
        # 3) Lowercase fallback
        crm = self._qualia_class_index.get(property_type.lower())
        if crm:
            return _resolve_prefixed(crm)
        # 4) Combined: lowercase last segment
        if "." in property_type:
            tail_lower = property_type.rsplit(".", 1)[-1].lower()
            crm = self._qualia_class_index.get(tail_lower)
            if crm:
                return _resolve_prefixed(crm)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Main exporter
# ─────────────────────────────────────────────────────────────────────────────

class RDFExporter:
    """
    Export s3Dgraphy graphs to RDF formats.

    Usage:
        exporter = RDFExporter("out.ttl", format="turtle")
        exporter.export_graphs()                  # all graphs
        exporter.export_graphs(["my_site"])       # specific ones
    """

    SUPPORTED_FORMATS: Dict[str, Tuple[str, str]] = {
        # alias        : (filename_extension, rdflib_format)
        "turtle":      ("ttl",    "turtle"),
        "ttl":         ("ttl",    "turtle"),
        "n-triples":   ("nt",     "nt"),
        "ntriples":    ("nt",     "nt"),
        "nt":          ("nt",     "nt"),
        "n-quads":     ("nq",     "nquads"),
        "nquads":      ("nq",     "nquads"),
        "trig":        ("trig",   "trig"),
        "json-ld":     ("jsonld", "json-ld"),
        "jsonld":      ("jsonld", "json-ld"),
        "rdf-xml":     ("rdf",    "xml"),
        "xml":         ("rdf",    "xml"),
    }

    def __init__(self,
                 output_path: str,
                 format: str = "turtle",
                 base_uri: str = DEFAULT_BASE_URI,
                 parent_hdt_iri: Optional[str] = None,
                 config_dir: Optional[Path] = None):
        """
        Args:
            output_path: target file path (extension auto-fixed by format).
            format: 'turtle' (default), 'n-triples', 'json-ld', 'trig', 'xml'.
            base_uri: base URI for minted node IRIs.
            parent_hdt_iri: if set, every exported EMGraph (HC16) gets a
                triple `<emgraph> hdto:HP33i_is_proposition_set_of <parent>`
                binding it as a proposition set of the given HC2 Heritage
                Digital Twin. The parent HDT IRI is also declared as
                rdf:type hdto:HC2_Heritage_Digital_Twin so a SPARQL query
                can discover the parent without a separate type assertion.
            config_dir: override location of JSON_config/ (default: alongside exporter).
        """
        fmt = (format or "turtle").lower()
        if fmt not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported RDF format '{format}'. Supported: "
                f"{sorted(set(self.SUPPORTED_FORMATS.keys()))}"
            )
        self.format_key = fmt
        self.ext, self.rdflib_format = self.SUPPORTED_FORMATS[fmt]
        self.output_path = self._adjust_extension(output_path)
        self.base_uri = base_uri.rstrip("/") + "/"
        self.parent_hdt_iri = self._normalize_iri(parent_hdt_iri)
        self.datamodel = _Datamodel(config_dir=config_dir)

        # Stats for the caller (verbose logging, eval)
        self.stats: Dict[str, int] = {
            "graphs": 0, "nodes": 0, "edges_emitted": 0,
            "edges_skipped_deprecated": 0, "edges_unmapped": 0,
            "nodes_unmapped": 0,
            "parent_hdt_bindings": 0,
        }

    @staticmethod
    def _normalize_iri(value: Optional[str]) -> Optional[str]:
        """Trim and lightly validate an IRI for the parent HDT binding.

        Accepts absolute http(s) URIs and urn: identifiers. Returns None for
        empty/whitespace inputs (treated as 'no binding requested'). Raises
        ValueError on clearly malformed input so the caller fails loudly
        rather than emitting a broken triple.
        """
        if value is None:
            return None
        v = value.strip()
        if not v:
            return None
        if not (v.startswith("http://") or v.startswith("https://") or v.startswith("urn:")):
            raise ValueError(
                f"parent_hdt_iri must be an absolute IRI (http://, https:// or urn:); got: {v!r}"
            )
        return v

    # ── public entry points ─────────────────────────────────────────────────

    def export_graphs(self, graph_ids: Optional[List[str]] = None) -> str:
        """Serialize specified (or all) graphs into one RDF document. Returns output path."""
        if graph_ids is None:
            graph_ids = get_all_graph_ids()

        store = ConjunctiveGraph()
        self._bind_namespaces(store)

        for gid in graph_ids:
            g = get_graph(gid)
            if g is None:
                continue
            ctx = store.get_context(self._graph_iri(g))
            self._serialize_graph(g, ctx)
            self.stats["graphs"] += 1

        store.serialize(destination=self.output_path, format=self.rdflib_format)
        return self.output_path

    def export_single_graph(self, graph: S3DGraph) -> str:
        """Serialize an in-memory graph directly (no MultiGraphManager lookup)."""
        store = ConjunctiveGraph()
        self._bind_namespaces(store)
        ctx = store.get_context(self._graph_iri(graph))
        self._serialize_graph(graph, ctx)
        self.stats["graphs"] += 1
        store.serialize(destination=self.output_path, format=self.rdflib_format)
        return self.output_path

    # ── path/format helpers ─────────────────────────────────────────────────

    def _adjust_extension(self, path: str) -> str:
        """Ensure the file path ends with the format-correct extension.

        Defensive against the leading-dot trap: a basename like ".ttl" is
        treated by pathlib.Path as a hidden-file name (no suffix), so
        ``with_suffix(".ttl")`` would produce ".ttl.ttl". We detect that case
        and leave the path untouched if its name IS already the wanted ext.
        """
        p = Path(path)

        # Leading-dot trap: basename equals "." + wanted ext (e.g. ".ttl")
        # → treat as already correct, don't double-append.
        if p.name.startswith('.') and p.name.lower().lstrip('.') == self.ext.lower():
            return str(p)

        current_ext = p.suffix.lstrip(".").lower()
        if current_ext != self.ext.lower():
            return str(p.with_suffix("." + self.ext))
        return str(p)

    def _bind_namespaces(self, g: ConjunctiveGraph) -> None:
        for prefix, ns in PREFIX_MAP.items():
            g.bind(prefix, ns)

    # ── IRI minting ─────────────────────────────────────────────────────────

    def _graph_iri(self, g: S3DGraph) -> URIRef:
        return URIRef(f"{self.base_uri}graph/{g.graph_id}")

    def _node_iri(self, graph_id: str, node_id: str) -> URIRef:
        # rdflib URIRef does not URL-encode by default — keep node_id safe.
        safe = str(node_id).replace(" ", "_")
        return URIRef(f"{self.base_uri}graph/{graph_id}/node/{safe}")

    # ── value extraction (graph.name / .description can be dict or str) ─────

    @staticmethod
    def _to_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, dict):
            return value.get("default") or next(iter(value.values()), None)
        if isinstance(value, str):
            return value
        return str(value)

    # ── graph-level serialization ───────────────────────────────────────────

    def _serialize_graph(self, g: S3DGraph, ctx) -> None:
        graph_iri = self._graph_iri(g)

        ctx.add((graph_iri, RDF.type, EM.EMGraph))
        ctx.add((graph_iri, RDF.type, CRM.E73_Information_Object))
        ctx.add((graph_iri, RDF.type, PROV.Bundle))
        # em:EMGraph rdfs:subClassOf hdto:HC16 is declared in em.ttl, but we
        # also emit the HC16 type explicitly so HDT-O-aware consumers that
        # don't run an OWL reasoner can find the proposition set directly.
        ctx.add((graph_iri, RDF.type, HDTO.HC16_Heritage_Proposition_Set))

        # Parent HDT binding (HP33i is_proposition_set_of) — when configured,
        # every exported EMGraph is declared as a proposition set of the
        # given HC2 HDT. We also emit a type triple for the parent so its
        # role is discoverable via SPARQL without external coordination.
        if self.parent_hdt_iri:
            parent_iri = URIRef(self.parent_hdt_iri)
            ctx.add((graph_iri, HDTO.HP33i_is_proposition_set_of, parent_iri))
            ctx.add((parent_iri, RDF.type, HDTO.HC2_Heritage_Digital_Twin))
            self.stats["parent_hdt_bindings"] += 1

        gname = self._to_text(getattr(g, "name", None))
        if gname:
            ctx.add((graph_iri, RDFS.label, Literal(gname)))
        gdesc = self._to_text(getattr(g, "description", None))
        if gdesc:
            ctx.add((graph_iri, DCTERMS.description, Literal(gdesc)))

        data = getattr(g, "data", {}) or {}
        for aid in data.get("authors", []) or []:
            ctx.add((graph_iri, CRM.P94_has_created,
                     self._node_iri(g.graph_id, aid)))
        license_val = data.get("license")
        if license_val:
            ctx.add((graph_iri, CRM.P104_is_subject_to, Literal(license_val)))
        embargo_until = data.get("embargo_until")
        if embargo_until:
            ctx.add((graph_iri, EM.embargoUntil, Literal(embargo_until)))

        # Nodes
        for node in g.nodes:
            self._serialize_node(g, node, ctx)

        # Edges
        for edge in g.edges:
            self._serialize_edge(g, edge, ctx)

    # ── node serialization ──────────────────────────────────────────────────

    def _serialize_node(self, g: S3DGraph, node: Any, ctx) -> None:
        node_iri = self._node_iri(g.graph_id, node.node_id)
        cls_name = type(node).__name__
        node_type = getattr(node, "node_type", None)

        # Primary class — conditional for PropertyNode (qualia takes precedence).
        primary_iri = self._compute_primary_iri(node, cls_name, node_type)
        if primary_iri is not None:
            ctx.add((node_iri, RDF.type, primary_iri))
        else:
            self.stats["nodes_unmapped"] += 1

        # Multi-type via subclass_of
        for sc in self.datamodel.get_node_superclasses(cls_name):
            ctx.add((node_iri, RDF.type, sc))

        # Base triples — label, description, identifier
        name = self._to_text(getattr(node, "name", None))
        if name:
            ctx.add((node_iri, RDFS.label, Literal(name)))
        desc = self._to_text(getattr(node, "description", None))
        if desc:
            ctx.add((node_iri, DCTERMS.description, Literal(desc)))
        ctx.add((node_iri, DCTERMS.identifier, Literal(node.node_id)))

        # Type-specific (node_type already computed above for primary IRI logic)
        self._serialize_type_specific(node, node_type, node_iri, ctx)

        self.stats["nodes"] += 1

    def _compute_primary_iri(self, node: Any, cls_name: str,
                             node_type: Optional[str]) -> Optional[URIRef]:
        """
        Resolve the rdf:type primary IRI for a node, applying conditional rules.

        Conditional rule for PropertyNode:
            The qualia-type-specific class (looked up in em_qualia_types.json)
            takes precedence over the generic PropertyNode default class
            (typically crm:E54_Dimension). Without this, an aesthetic_value
            property would be typed as BOTH crm:E54_Dimension (PropertyNode
            default) and crminf:I4_Proposition_Set (qualia-specific), which is
            semantically misleading: aesthetic value is NOT a dimension.

        Lookup key resolution (PropertyNode):
            The s3dgraphy graphml importer preserves raw graphml data
            (``node.name`` carries the NodeLabel, ``node.property_type`` is
            the default "string" unless populated by the
            ``_s3d_property_metadata`` side channel). To enrich at export
            time without burdening the importer with vocabulary knowledge,
            we try the lookup key in this order:
              1. ``node.property_type`` if explicitly set (not "string")
              2. ``node.name`` if available (the yEd NodeLabel — qualia
                 identifier in EM convention)
            Either string is resolved through the multi-step graceful
            matcher in ``_Datamodel.get_qualia_crm_iri`` (exact / dot-split
            / lowercase). Falls back to the generic node datamodel mapping
            when no qualia term matches (e.g. custom labels like
            "lenght_pipe" stay as em:Qualia + crm:E1_CRM_Entity).
        """
        if node_type == "property":
            ptype = getattr(node, "property_type", None)
            # Treat the default "string" sentinel as "unset" — the importer
            # leaves it on the PropertyNode constructor default when no
            # side-channel metadata is present.
            if ptype and ptype.lower() != "string":
                qualia_iri = self.datamodel.get_qualia_crm_iri(ptype)
                if qualia_iri is not None:
                    return qualia_iri
            # Fall back to NodeLabel (em yEd convention: label IS the qualia id)
            name = getattr(node, "name", None)
            if name:
                qualia_iri = self.datamodel.get_qualia_crm_iri(name)
                if qualia_iri is not None:
                    return qualia_iri
        return self.datamodel.get_node_primary_iri(cls_name)

    def _serialize_type_specific(self, node: Any, node_type: Optional[str],
                                 node_iri: URIRef, ctx) -> None:
        data = getattr(node, "data", {}) or {}

        if node_type == "property":
            # rdf:type already emitted by _compute_primary_iri (qualia-specific
            # class takes precedence over PropertyNode default).
            #
            # Value resolution: prefer node.value when set & non-empty;
            # fall back to node.description for legacy graphml where the
            # description data field encodes the value (yEd has no separate
            # "value" socket on annotation-style PropertyNodes).
            raw_value = getattr(node, "value", None)
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                raw_value = getattr(node, "description", None)
            if raw_value is not None and (not isinstance(raw_value, str) or raw_value.strip()):
                ctx.add((node_iri, CRM.P90_has_value, Literal(raw_value)))

            # Qualia type identifier — same key resolution as _compute_primary_iri:
            # property_type if non-default, otherwise the NodeLabel (name).
            ptype = getattr(node, "property_type", None)
            if not ptype or ptype.lower() == "string":
                ptype = getattr(node, "name", None)
            if ptype:
                ctx.add((node_iri, EM.hasQualiaType, Literal(ptype)))

        elif node_type == "epoch":
            start = getattr(node, "start_time", None)
            end = getattr(node, "end_time", None)
            color = getattr(node, "color", None)
            if start is not None:
                ctx.add((node_iri, CRM["P82a_begin_of_the_begin"], Literal(start)))
            if end is not None:
                ctx.add((node_iri, CRM["P82b_end_of_the_end"], Literal(end)))
            if color:
                ctx.add((node_iri, CRM.P90_has_value, Literal(color)))

        elif node_type == "author":
            orcid = data.get("orcid")
            if orcid and orcid != "noorcid":
                ctx.add((node_iri, CRM.P48_has_preferred_identifier, Literal(orcid)))
            surname = data.get("surname")
            if surname and surname != "nosurname":
                ctx.add((node_iri, CRM.P131_is_identified_by, Literal(surname)))

        elif node_type == "author_ai":
            orcid = data.get("orcid")
            if orcid and orcid != "noorcid":
                ctx.add((node_iri, CRM.P48_has_preferred_identifier, Literal(orcid)))
            model = data.get("model")
            if model:
                ctx.add((node_iri, EM.modelIdentifier, Literal(model)))
            prompt = data.get("prompt_reference")
            if prompt:
                ctx.add((node_iri, EM.promptReference, Literal(prompt)))

        elif node_type == "license":
            ltype = data.get("license_type")
            if ltype:
                ctx.add((node_iri, CRM.P2_has_type, Literal(ltype)))
            url = data.get("url")
            if url:
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    ctx.add((node_iri, RDFS.seeAlso, URIRef(url)))
                else:
                    ctx.add((node_iri, RDFS.seeAlso, Literal(url)))

        elif node_type == "embargo":
            start = data.get("embargo_start")
            end = data.get("embargo_end")
            if start:
                ctx.add((node_iri, CRM["P82a_begin_of_the_begin"], Literal(start)))
            if end:
                ctx.add((node_iri, CRM["P82b_end_of_the_end"], Literal(end)))
            reason = data.get("reason")
            if reason:
                ctx.add((node_iri, RDFS.comment, Literal(reason)))

        elif node_type == "link":
            url = data.get("url")
            url_type = data.get("url_type")
            if url:
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    ctx.add((node_iri, RDFS.seeAlso, URIRef(url)))
                else:
                    ctx.add((node_iri, RDFS.seeAlso, Literal(url)))
            if url_type:
                ctx.add((node_iri, CRM.P2_has_type, Literal(url_type)))

        elif node_type == "geo_position":
            epsg = data.get("epsg")
            if epsg:
                ctx.add((node_iri, CRM.P2_has_type, Literal(f"EPSG:{epsg}")))
            for axis in ("shift_x", "shift_y", "shift_z"):
                v = data.get(axis)
                if v is not None:
                    ctx.add((node_iri, EM[axis], Literal(v)))

        elif node_type == "extractor":
            source = getattr(node, "source", None)
            if source:
                ctx.add((node_iri, CRMINF.J7_is_based_on_evidence_from, Literal(source)))

    # ── edge serialization ──────────────────────────────────────────────────

    def _serialize_edge(self, g: S3DGraph, edge: Any, ctx) -> None:
        edge_type = edge.edge_type
        predicate, type_tag, deprecated = self.datamodel.get_edge_mapping(edge_type)

        if deprecated:
            self.stats["edges_skipped_deprecated"] += 1
            return

        source_iri = self._node_iri(g.graph_id, edge.edge_source)
        target_iri = self._node_iri(g.graph_id, edge.edge_target)

        if type_tag and type_tag in AP11_SUBPROPS:
            specific = AP11_SUBPROPS[type_tag]
            ctx.add((source_iri, specific, target_iri))
            # Also assert the generic AP11 (so SPARQL on AP11 still works
            # for readers that don't know our subproperties).
            ctx.add((source_iri, CRMARCHAEO.AP11_has_physical_relation, target_iri))
            self.stats["edges_emitted"] += 1
            return

        if predicate is not None:
            ctx.add((source_iri, predicate, target_iri))
            self.stats["edges_emitted"] += 1
        else:
            # Fallback: emit as generic P130_shows_features_of so the
            # connection survives the round-trip even if unmapped.
            ctx.add((source_iri, CRM.P130_shows_features_of, target_iri))
            self.stats["edges_unmapped"] += 1


# ─────────────────────────────────────────────────────────────────────────────
# Convenience helpers
# ─────────────────────────────────────────────────────────────────────────────

def export_to_rdf(output_path: str,
                  format: str = "turtle",
                  graph_ids: Optional[List[str]] = None,
                  base_uri: str = DEFAULT_BASE_URI,
                  parent_hdt_iri: Optional[str] = None) -> str:
    """One-call helper: export all (or specified) graphs to RDF.

    If parent_hdt_iri is set, every exported EMGraph is bound to it via
    hdto:HP33i_is_proposition_set_of.
    """
    exporter = RDFExporter(output_path, format=format, base_uri=base_uri,
                           parent_hdt_iri=parent_hdt_iri)
    return exporter.export_graphs(graph_ids)


def export_single_graph_to_rdf(graph: S3DGraph,
                               output_path: str,
                               format: str = "turtle",
                               base_uri: str = DEFAULT_BASE_URI,
                               parent_hdt_iri: Optional[str] = None) -> str:
    """One-call helper for an in-memory graph."""
    exporter = RDFExporter(output_path, format=format, base_uri=base_uri,
                           parent_hdt_iri=parent_hdt_iri)
    return exporter.export_single_graph(graph)
