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
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from rdflib import ConjunctiveGraph, Literal, Namespace, URIRef
    from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD
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

DEFAULT_BASE_URI = "https://w3id.org/em/id/"

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
    "skos":       Namespace(str(SKOS)),
    "rdfs":       Namespace(str(RDFS)),
    "owl":        Namespace(str(OWL)),
    "xsd":        Namespace(str(XSD)),
}

# authority_ref `match` strength → RDF predicate (E.D.: concept alignment via
# SKOS; owl:sameAs ONLY for a human-confirmed identity, NEVER for a ranked or
# uncertain candidate; unqualified default = skos:closeMatch).
AUTHORITY_MATCH_PREDICATE: Dict[str, URIRef] = {
    "exact":    SKOS.exactMatch,
    "close":    SKOS.closeMatch,
    "broad":    SKOS.broadMatch,
    "narrow":   SKOS.narrowMatch,
    "related":  SKOS.relatedMatch,
    "sameAs":   OWL.sameAs,
    "identity": OWL.sameAs,
}
DEFAULT_AUTHORITY_PREDICATE: URIRef = SKOS.closeMatch


# ─────────────────────────────────────────────────────────────────────────────
# IRI resolution helpers
# ─────────────────────────────────────────────────────────────────────────────

def _iri_local(text: str) -> str:
    """Slugify a free-text label into a safe IRI local part.

    Property/qualia types are user text (e.g. ``"max level"``,
    ``"Shape; dimensions"``); minted verbatim they yield IRIs with spaces or
    ``;`` that rdflib refuses to serialize as Turtle. Keep [A-Za-z0-9_.-],
    collapse every other run to a single ``_``, and trim. Deterministic, so
    equal inputs still mint the same IRI (intra-graph joins hold).
    """
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")
    return slug or "unknown"


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

    def get_edge_mapping(self, edge_type: str) -> Tuple[Optional[URIRef], Optional[URIRef], Optional[str], bool]:
        """
        Returns (predicate_iri, extension_iri, type_tag, deprecated).

        predicate_iri  — the core predicate from mapping.cidoc.
        extension_iri  — the resolved mapping.extension_mapping predicate
                         (e.g. em:hasVisualReference, em:survivesInEpoch),
                         or None when absent/unresolvable. The caller emits
                         BOTH, generalising the AP11 dual-emission pattern:
                         specific em: subproperty for expressive SPARQL,
                         generic CRM predicate for CRM-only readers.
        type_tag is set for the AP11 family — caller resolves the specific
        subproperty via AP11_SUBPROPS. deprecated edges should be skipped on
        write (already canonicalised aliases like has_timebranch).
        """
        edges = self.connections_datamodel.get("edge_types", {})
        entry = edges.get(edge_type) or {}
        if not entry:
            return None, None, None, False
        deprecated = bool(entry.get("deprecated"))
        mapping = entry.get("mapping") or {}
        type_tag = mapping.get("type_tag")
        cidoc = mapping.get("cidoc")
        # extension_mapping may carry a legacy parenthesised reverse label,
        # e.g. "AP13_has_stratigraphic_relation (is_stratigraphic_relation_of)"
        # — strip it before resolution.
        ext_raw = mapping.get("extension_mapping")
        if isinstance(ext_raw, str) and "(" in ext_raw:
            ext_raw = ext_raw.split("(", 1)[0].strip()
        ext_iri = _resolve_prefixed(ext_raw)
        # AP11 family: prefer the generic AP11 predicate; caller adds subproperty.
        if type_tag:
            return CRMARCHAEO.AP11_has_physical_relation, None, type_tag, deprecated
        return _resolve_prefixed(cidoc), ext_iri, None, deprecated

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


def _narrative_authors_from_data(data: Dict[str, Any]) -> List[str]:
    """Author ids read out of a serialised narrative payload (chapters and
    blocks), for the case where the node degraded to a base ``Node``."""
    seen, out = set(), []
    for chapter in data.get("chapters") or []:
        for key in ("authored_by",):
            value = (chapter or {}).get(key)
            if value and value not in seen:
                seen.add(value)
                out.append(value)
        for block in (chapter or {}).get("blocks") or []:
            for key in ("authored_by", "validated_by"):
                value = (block or {}).get(key)
                if value and value not in seen:
                    seen.add(value)
                    out.append(value)
    return out


def _narrative_validators(node: Any, data: Dict[str, Any]) -> List[str]:
    """The humans who have endorsed content in this narrative."""
    seen, out = set(), []
    blocks = ([b for _c, b in node.blocks_iter()]
              if hasattr(node, "blocks_iter") else [])
    if blocks:
        values = [getattr(b, "validated_by", None) for b in blocks]
    else:
        values = [(b or {}).get("validated_by")
                  for c in (data.get("chapters") or [])
                  for b in ((c or {}).get("blocks") or [])]
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _narrative_refs_from_data(data: Dict[str, Any]) -> List[str]:
    """Referenced ids read straight out of a serialised narrative payload.

    Used when the node arrives as a plain ``Node`` — a reader older than the
    NarrativeNode class still carries the chapters in ``data``, and the
    projection should not lose the references just because the class was not
    recognised.
    """
    seen, out = set(), []
    for chapter in data.get("chapters") or []:
        for block in (chapter or {}).get("blocks") or []:
            ref = (block or {}).get("ref")
            if ref and ref not in seen:
                seen.add(ref)
                out.append(ref)
    return out


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
        # BUGFIX-CANVAS-IMPORT (2026-08-06): the canonical canvas-scope key is
        # `embargo` (what CANVAS1 writes and the funnel reads); `embargo_until` is
        # the legacy key. Read the canonical first, fall back to legacy so old
        # em.json still exports. ONE read, one meaning.
        embargo = data.get("embargo") or data.get("embargo_until")
        if embargo:
            ctx.add((graph_iri, EM.embargoUntil, Literal(embargo)))

        # Nodes
        for node in g.nodes:
            self._serialize_node(g, node, ctx)

        # Edges
        for edge in g.edges:
            self._serialize_edge(g, edge, ctx)

        # CRMinf belief propositions (J4 → I17) — needs the full edge
        # topology, so it runs as a post-pass after nodes and edges.
        self._emit_belief_propositions(g, ctx)

    def _emit_belief_propositions(self, g: S3DGraph, ctx) -> None:
        """J4 linking: connect each argumentation belief to its proposition.

        Design (WP3 coverage analysis, Appendix D.3, approved E.D.
        2026-07-11). The belief skeleton (<arg> J2_concluded_that
        <arg>/belief, typed I2) is emitted per argumentation node by
        ``_emit_belief_skeleton``. This post-pass adds WHAT each belief
        concludes, derived from the existing graph topology — the user
        never authors beliefs:

        * Property claim ("US12 has height 3.2 m"): for every chain
          unit --has_property--> property --has_data_provenance--> arg,
          emit an I17 One-Proposition Set at <property>/proposition:
              <i17> a crminf:I17_One-Proposition_Set ;
                    crminf:J30_has_domain <unit> ;
                    crminf:J32_has_property_type <s3d:qualia_TYPE> ;
                    crminf:J31_has_range "VALUE" .
              <arg>/belief crminf:J4_that <i17> .
          The J32 target is a placeholder E55 IRI in the s3d: namespace
          until the SKOS vocabulary layer (Appendix E) provides
          dereferenceable concept URIs.

        * Reconstruction claim ("there was a colonnade here"): when the
          justified property is the existence of a virtual-family unit
          (qualia id 'existence'), the proposition IS the unit itself —
          em:VirtualSU is declared subclass of crminf:I4 in em.ttl — so
          the belief links J4 directly to the unit and no I17 is minted.

        * J5 holds to be: when the same argumentation node also
          justifies a confidence_level property (typed I6_Belief_Value
          via the qualia catalogue), the belief links J5 to it.
        """
        VIRTUAL_TYPES = {"USVs", "USVn", "USD", "VSF",
                         "serUSVs", "serUSVn", "serUSD"}
        ARG_TYPES = {"extractor", "combiner"}

        node_by_id = {n.node_id: n for n in g.nodes}

        # property_id → [unit_id] — ALL the units that claim this property.
        # It was a single id, which meant a property with several parents lost
        # every attribution but one. See the I17-per-pair emission below.
        prop_units: Dict[str, List[str]] = {}
        # arg_id → [property_id] (has_data_provenance: property → arg)
        arg_props: Dict[str, List[str]] = {}

        for edge in g.edges:
            if edge.edge_type == "has_property":
                # Every parent is kept. This was first a plain assignment (so the
                # LAST edge won and the projection depended on edge ORDER — found
                # by the round-trip), then a deterministic min(). Both named ONE
                # unit, and a property claimed by three units then said so about
                # one: the other two attributions were simply absent from the
                # RDF. Now all of them are collected and each becomes its own
                # I17 below. Sorted, so the emission is order-independent.
                prop_units.setdefault(edge.edge_target, []).append(edge.edge_source)
            elif edge.edge_type == "has_data_provenance":
                tgt = node_by_id.get(edge.edge_target)
                if tgt is not None and getattr(tgt, "node_type", None) in ARG_TYPES:
                    arg_props.setdefault(edge.edge_target, []).append(edge.edge_source)

        for arg_id, prop_ids in arg_props.items():
            belief_iri = URIRef(str(self._node_iri(g.graph_id, arg_id)) + "/belief")
            for prop_id in prop_ids:
                prop_node = node_by_id.get(prop_id)
                if prop_node is None:
                    continue
                ptype = getattr(prop_node, "property_type", None)
                if not ptype or (isinstance(ptype, str) and ptype.lower() == "string"):
                    ptype = getattr(prop_node, "name", None) or "unknown"
                unit_ids = sorted(set(prop_units.get(prop_id, [])))

                # J5: confidence qualia → I6 Belief Value
                if str(ptype).lower().endswith("confidence_level"):
                    ctx.add((belief_iri, CRMINF.J5_holds_to_be,
                             self._node_iri(g.graph_id, prop_id)))
                    continue

                # Reconstruction claim: belief J4 → the virtual unit (⊂ I4).
                # Unchanged in meaning; it just runs per parent now, since a
                # property may be claimed by more than one.
                virtual_units = [
                    uid for uid in unit_ids
                    if getattr(node_by_id.get(uid), "node_type", None) in VIRTUAL_TYPES
                ]
                if virtual_units and str(ptype).lower().endswith("existence"):
                    for uid in virtual_units:
                        ctx.add((belief_iri, CRMINF.J4_that,
                                 self._node_iri(g.graph_id, uid)))
                        self.stats["belief_propositions"] = self.stats.get("belief_propositions", 0) + 1
                    continue

                # Property claim: ONE I17 One-Proposition Set PER (property, unit)
                # PAIR. A proposition is "THIS unit has THIS value for THIS
                # property" — so a property claimed by three units is three
                # propositions, not one with a chosen subject. Naming one and
                # dropping the others made the RDF quietly lossy, and no importer
                # could have recovered what was never written.
                #
                # The IRI carries the pair (`…/proposition/<unit_id>`), which is
                # what makes the set deterministic and re-readable: each I17 has
                # a stable name derived from the two things it relates, so
                # re-exporting the same graph mints the same IRIs whatever the
                # order of the edges. A property with no parent at all still gets
                # its bare `…/proposition` — the claim exists, its subject is
                # simply not stated.
                prop_iri = self._node_iri(g.graph_id, prop_id)
                qualia_iri = S3D["qualia_" + _iri_local(str(ptype).rsplit(".", 1)[-1])]
                raw_value = getattr(prop_node, "value", None)
                if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                    raw_value = getattr(prop_node, "description", None)
                has_value = raw_value is not None and (
                    not isinstance(raw_value, str) or raw_value.strip())

                for uid in (unit_ids or [None]):
                    i17_iri = URIRef(
                        f"{prop_iri}/proposition/{_iri_local(uid)}" if uid
                        else f"{prop_iri}/proposition")
                    ctx.add((i17_iri, RDF.type, CRMINF["I17_One-Proposition_Set"]))
                    if uid:
                        ctx.add((i17_iri, CRMINF.J30_has_domain,
                                 self._node_iri(g.graph_id, uid)))
                    ctx.add((i17_iri, CRMINF.J32_has_property_type, qualia_iri))
                    ctx.add((qualia_iri, RDF.type, CRM.E55_Type))
                    if has_value:
                        ctx.add((i17_iri, CRMINF.J31_has_range, Literal(raw_value)))
                    ctx.add((belief_iri, CRMINF.J4_that, i17_iri))
                    self.stats["belief_propositions"] = self.stats.get("belief_propositions", 0) + 1

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

        # Authority cross-references (P1-D) — GENERALISED to any node carrying
        # `data.authority_refs` (nodes AND qualia). Redundant by design: every
        # ranked ref is emitted, with the strength-aware predicate.
        self._serialize_authority_refs(node, node_iri, ctx)

        # Type-specific (node_type already computed above for primary IRI logic)
        self._serialize_type_specific(node, node_type, node_iri, ctx,
                                      graph_id=g.graph_id)

        self.stats["nodes"] += 1

    def _serialize_authority_refs(self, node: Any, node_iri: URIRef, ctx) -> None:
        """Emit `data.authority_refs` as SKOS/OWL alignment triples.

        Each ref ``{uri, authority, label, rank, match}`` becomes
        ``<node> <predicate(match)> <uri>`` where the predicate is chosen by
        match strength (default skos:closeMatch). Non-http URIs are skipped
        (an authority ref must be a resolvable IRI)."""
        data = getattr(node, "data", {}) or {}
        refs = data.get("authority_refs")
        if not isinstance(refs, list):
            return
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            uri = ref.get("uri")
            if not uri or not (isinstance(uri, str)
                               and uri.startswith(("http://", "https://"))):
                continue
            pred = AUTHORITY_MATCH_PREDICATE.get(
                ref.get("match"), DEFAULT_AUTHORITY_PREDICATE)
            ctx.add((node_iri, pred, URIRef(uri)))
            self.stats["authority_refs"] = self.stats.get("authority_refs", 0) + 1

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
                                 node_iri: URIRef, ctx,
                                 graph_id: Optional[str] = None) -> None:
        data = getattr(node, "data", {}) or {}

        if node_type == "narrative":
            # EM Narrative (DP-79) — the PROJECTION side of the two-tier model.
            # Authoring happens on the property graph; here we only restate what
            # it already says, in RDF terms.
            #
            # The chapters are NOT projected as a structure: their order and
            # nesting are an authoring concern, and reifying every block as a
            # resource would put a document tree into a knowledge graph for no
            # query anyone wants to run. What IS projected is the thing worth
            # asking about — WHICH resources this narrative cites — as
            # P67_refers_to, the same reference hinge used everywhere else in
            # EM. That makes "which narratives cite this US" a one-line SPARQL
            # query instead of a text search.
            lang = data.get("lang")
            if lang:
                ctx.add((node_iri, CRM.P72_has_language, Literal(lang)))
            for key, prop in (("version", CRM.P3_has_note),):
                value = data.get(key)
                if value:
                    ctx.add((node_iri, prop, Literal(f"{key}: {value}")))
            # Authorship and endorsement (N4). Both are projected because both
            # are claims ABOUT the text that a reader is entitled to check:
            # who wrote it, and whether a person has vouched for it. The
            # per-block state is not reified — a block is not a resource — but
            # the agents are, so "which narratives has this person endorsed"
            # and "what did this model write" are answerable.
            for author_id in (node.author_refs()
                              if hasattr(node, "author_refs")
                              else _narrative_authors_from_data(data)):
                if graph_id is None:
                    break
                ctx.add((node_iri, PROV.wasAttributedTo,
                         self._node_iri(graph_id, author_id)))
            for validator_id in (_narrative_validators(node, data)):
                if graph_id is None:
                    break
                ctx.add((node_iri, PROV.wasInfluencedBy,
                         self._node_iri(graph_id, validator_id)))
                self.stats["narrative_endorsements"] = self.stats.get(
                    "narrative_endorsements", 0) + 1
            # An unendorsed AI draft says so, in the graph as on the page: the
            # absence of a validator is the state, and stating it means a
            # consumer cannot mistake a draft for something someone stands
            # behind.
            pending = (len(node.pending_validation())
                       if hasattr(node, "pending_validation")
                       else 0)
            if pending:
                ctx.add((node_iri, EM.pendingValidation, Literal(pending)))

            refs = node.referenced_ids() if hasattr(node, "referenced_ids") \
                else _narrative_refs_from_data(data)
            for ref in refs:
                if graph_id is None:
                    break
                ctx.add((node_iri, CRM.P67_refers_to,
                         self._node_iri(graph_id, ref)))
                self.stats["narrative_references"] = self.stats.get(
                    "narrative_references", 0) + 1
            return

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

        # BUGFIX (2026-08-11, found by the RDF round-trip): the branch tested for
        # "epoch", but EpochNode.node_type is "EpochNode" — so it NEVER fired and
        # no epoch ever carried its bounds or its colour into RDF. A projection of
        # an EM graph without its chronology is missing the thing EM is about, and
        # nothing downstream could have restored it. Both spellings are accepted
        # now; the fix only ADDS triples.
        elif node_type in ("EpochNode", "epoch"):
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
                self._emit_orcid_verification(node_iri, data, ctx)
            surname = data.get("surname")
            if surname and surname != "nosurname":
                ctx.add((node_iri, CRM.P131_is_identified_by, Literal(surname)))

        elif node_type == "author_ai":
            orcid = data.get("orcid")
            if orcid and orcid != "noorcid":
                ctx.add((node_iri, CRM.P48_has_preferred_identifier, Literal(orcid)))
                self._emit_orcid_verification(node_iri, data, ctx)
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

        elif node_type == "resource":
            url = data.get("url")
            url_type = data.get("url_type")
            if url:
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    ctx.add((node_iri, RDFS.seeAlso, URIRef(url)))
                else:
                    ctx.add((node_iri, RDFS.seeAlso, Literal(url)))
            if url_type:
                ctx.add((node_iri, CRM.P2_has_type, Literal(url_type)))
            # DTC OUTPUT (slice b): a ResourceNode that is a DTC output — carries
            # data.dtc_kind — is the produced digital object (Resource). Beyond
            # its E73/url it is a crmdig:D1_Digital_Object / prov:Entity (the
            # process prov:generated it via dtc_had_output) and its kind projects
            # as crm:P2_has_type. RM/Document referencing it keep their own types.
            dtc_kind = data.get("dtc_kind")
            if dtc_kind:
                ctx.add((node_iri, RDF.type, CRMDIG.D1_Digital_Object))
                ctx.add((node_iri, RDF.type, PROV.Entity))
                ctx.add((node_iri, CRM.P2_has_type, Literal(dtc_kind)))

        elif node_type == "LocationNodeGroup":
            # The kind (toponym / study / functional) is the discriminator of the
            # spatial plane and is REQUIRED by the constructor — a Location
            # without it cannot be rebuilt. It was not projected at all, so a
            # Location came back as a bare Node. The datamodel already declared
            # how ("E53 Place + E55 Type (kind classifier via P2_has_type)"); this
            # emits what that mapping says.
            kind = getattr(node, "kind", None) or data.get("kind")
            if kind:
                ctx.add((node_iri, CRM.P2_has_type, Literal(kind)))
            # propagation is real data too (additive vs substitutive changes what
            # the membership MEANS), and only stated when it is not the default —
            # a triple per node saying "the usual" is noise.
            propagation = getattr(node, "propagation", None) or data.get("propagation")
            if propagation and propagation != "additive":
                ctx.add((node_iri, EM.propagation, Literal(propagation)))

        elif node_type == "geo_position":
            epsg = data.get("epsg")
            if epsg:
                ctx.add((node_iri, CRM.P2_has_type, Literal(f"EPSG:{epsg}")))
            # The shift is the anchor of the scene-local frame, and `rotation`
            # (G1) is its azimuth — clockwise degrees from north, 0 = north up.
            # Projecting the shift without the rotation would describe an
            # orientation the scene does not have, so it travels with it.
            for axis in ("shift_x", "shift_y", "shift_z", "rotation"):
                v = data.get(axis)
                if v is not None:
                    ctx.add((node_iri, EM[axis], Literal(v)))

        elif node_type == "semantic_shape":
            # PROXY-AS-PROPERTY (v1.6.3): the SemanticShape is the PAYLOAD of a
            # geometry property, so the numbers are the whole point of the node
            # and the projection dropped them — a proxy came back from the store
            # as an empty shape with a label. Now they travel.
            #
            # One literal per hull and per sphere rather than one blob: they are
            # separate objects, and a consumer reading "the third hull" should
            # not have to parse a container to get at it. Coordinates are
            # space-separated with fixed precision, for the same reason the 2D
            # selector has fixed precision — this string is what the round-trip
            # compares.
            for part in (getattr(node, "convexshapes", None) or []):
                ctx.add((node_iri, EM.convexShape,
                         Literal(" ".join(f"{float(v):.6f}" for v in part))))
            for sphere in (getattr(node, "spheres", None) or []):
                ctx.add((node_iri, EM.sphere,
                         Literal(" ".join(f"{float(v):.6f}" for v in sphere))))
            shape_type = getattr(node, "type", None)
            if shape_type:
                ctx.add((node_iri, CRM.P2_has_type, Literal(shape_type)))
            # The .glb form of the same payload: same predicate a ResourceNode
            # uses for its file, so "where the bytes are" reads the same way
            # everywhere.
            url = getattr(node, "url", None) or (data.get("url") if data else None)
            if url:
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    ctx.add((node_iri, RDFS.seeAlso, URIRef(url)))
                else:
                    ctx.add((node_iri, RDFS.seeAlso, Literal(url)))

        elif node_type == "annotation_region":
            # The geometry travels as ONE selector literal (Media Fragment for a
            # rect, SVG-style point list for a polygon), not as a bag of numbers:
            # a consumer outside EM can resolve `xywh=percent:…` against the
            # image without knowing anything about this datamodel, and the string
            # is derived from the node's own fields rather than stored twice.
            selector = getattr(node, "selector", None)
            if callable(selector):
                ctx.add((node_iri, EM.hasSelector, Literal(selector())))
            shape_kind = getattr(node, "shape_kind", None)
            if shape_kind:
                ctx.add((node_iri, CRM.P2_has_type, Literal(shape_kind)))
            # Page 0 is emitted as NOTHING. A plain image has no page, and
            # asserting `onPage 0` for every region would put a fact in the store
            # that nobody stated — and the importer defaults to 0 anyway, so the
            # round-trip is exact either way.
            page = getattr(node, "page", 0)
            if page:
                ctx.add((node_iri, EM.onPage,
                         Literal(int(page), datatype=XSD.nonNegativeInteger)))

        elif node_type == "extractor":
            source = getattr(node, "source", None)
            if source:
                ctx.add((node_iri, CRMINF.J7_is_based_on_evidence_from, Literal(source)))
            self._emit_belief_skeleton(node_iri, ctx)

        elif node_type == "combiner":
            self._emit_belief_skeleton(node_iri, ctx)

        # Same family of gap: DTCAcquisitionNode (crmdig:D12 ⊂ D7) carries the
        # same `dtc_kind` fact and had no branch, so an acquisition's kind was
        # dropped while a process's was kept.
        elif node_type in ("dtc_process", "dtc_acquisition"):
            # DTC substrate profile (ECHOES): the process kind (e.g.
            # transformation) projects as crm:P2_has_type. The rdf:type
            # (crmdig:D7 + prov:Activity) is emitted from em_extension by the
            # generic pass. INPUT and OUTPUT kinds are handled in the `link`
            # branch (both are Resources/LinkNodes).
            kind = data.get("dtc_kind")
            if kind:
                ctx.add((node_iri, CRM.P2_has_type, Literal(kind)))

    def _emit_orcid_verification(self, node_iri: URIRef, data: Dict[str, Any],
                                 ctx) -> None:
        """Say whether the declared ORCID iD was CONFIRMED, and only then.

        Emitted **only for a verified author**, and that asymmetry is the point.
        "Verified" is a positive fact somebody established; "not verified" is the
        absence of one, and absence is what an empty graph already says. Writing
        `verified false` into a store would turn "nobody has checked yet" into an
        assertion that travels — and a reader downstream cannot tell a claim of
        falsity from a silence.

        The predicate is `em:orcidVerified`. A CIDOC-native alternative would be
        an E13 Attribute Assignment reifying the check (who verified, when,
        against which authority), which is the *right* shape once the flow
        records those facts — it does not yet, and reifying an event with no
        actor and no date would be inventing provenance. Flagged
        `confirm_with: Felicetti` in em.ttl.
        """
        if data.get("verified") is True:
            ctx.add((node_iri, EM.orcidVerified,
                     Literal(True, datatype=XSD.boolean)))

    def _emit_belief_skeleton(self, node_iri: URIRef, ctx) -> None:
        """CRMinf belief expansion (I2) for argumentation nodes.

        EM deliberately collapses the CRMinf belief layer: the conclusion of
        an Extractor (I7 Belief Adoption) or Combiner (I5 Inference Making)
        is implicit in the existence of the node it justifies. To make the
        chain CRMinf-complete on export WITHOUT asking users to author
        beliefs explicitly, each argumentation node deterministically emits
        its concluded belief:

            <node> J2_concluded_that <node>/belief .
            <node>/belief a I2_Belief .

        J2 has domain I1_Argumentation — valid for both I5 and I7.

        J4_that and J5_holds_to_be are emitted by the graph-level post-pass
        ``_emit_belief_propositions`` (design approved E.D. 2026-07-11):
        property claims get a minted I17 One-Proposition_Set, reconstruction
        claims link J4 directly to the virtual unit (⊂ I4), confidence_level
        qualia are linked via J5 as I6 Belief Values.
        """
        belief_iri = URIRef(str(node_iri) + "/belief")
        ctx.add((node_iri, CRMINF.J2_concluded_that, belief_iri))
        ctx.add((belief_iri, RDF.type, CRMINF.I2_Belief))

    # ── edge serialization ──────────────────────────────────────────────────

    def _serialize_edge(self, g: S3DGraph, edge: Any, ctx) -> None:
        edge_type = edge.edge_type
        predicate, ext_iri, type_tag, deprecated = self.datamodel.get_edge_mapping(edge_type)

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

        # has_visual_reference co-typing: the target is asserted to be an
        # E36 Visual Item — required for the P138i_has_representation mapping
        # to be range-consistent. Since BUGFIX-CONN2 (2026-08-05) the target
        # is the resource-layer image node (ResourceNode, E73 Information Object)
        # rather than the former E31 Document; E36 is a subclass of E73, so
        # co-typing a ResourceNode as E36 is now clean (it was strained for E31).
        # The co-typing is target-agnostic, so no logic change was needed —
        # only the semantics of what the target IS. See Appendix B.1 of the
        # WP3 coverage analysis and the CIDOC note for Felicetti (confirm E36
        # as the target class, as for USNt).
        if edge_type == "has_visual_reference":
            ctx.add((target_iri, RDF.type, CRM.E36_Visual_Item))

        if predicate is not None:
            ctx.add((source_iri, predicate, target_iri))
            # Dual emission (generalised AP11 pattern): also assert the
            # specific em:/extension subproperty when one is declared and
            # resolvable, so expressive SPARQL works without inference
            # while CRM-only readers still see the core predicate.
            if ext_iri is not None and ext_iri != predicate:
                ctx.add((source_iri, ext_iri, target_iri))
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
