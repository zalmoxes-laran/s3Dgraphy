"""
UnifiedXLSXImporter — single-file xlsx importer for the Extended Matrix.

Reads a ``em_data.xlsx`` file produced by StratiMiner (DP-02) and builds a
complete s3dgraphy Graph in memory: stratigraphic units, epochs, qualia,
relations, and the full paradata chain (PropertyNode → ExtractorNode →
DocumentNode, with AuthorNode / AuthorAINode attached to the extractor or
directly to the PropertyNode).

Unlike the legacy two-file pipeline (MappedXLSXImporter + QualiaImporter),
this importer consumes a single workbook with five typed sheets:

  1. ``Units``     — stratigraphic unit declarations (ID, TYPE, NAME).
  2. ``Epochs``    — swimlane declarations (ID, NAME, START, END, COLOR).
  3. ``Claims``    — long-table, one row per claim about a unit/epoch:
                      qualia values, epoch assignment, stratigraphic
                      relations, each with its own attribution.
  4. ``Authors``   — normalized catalog of claim authors (human A.xx or
                      AI AI.xx).
  5. ``Documents`` — normalized catalog of source PDFs/reports.

The schema and semantics are described in the template
``s3dgraphy/templates/em_data_template.xlsx``.

Claim row semantics
-------------------

Each Claims row is one of:

* **Scalar qualia** (``PROPERTY_TYPE`` ∈ {definition, material_type,
  length, width, height, shape, conservation_state, comparanda,
  interpretation, ...}):
  creates a ``PropertyNode`` attached to ``TARGET_ID`` via
  ``has_property``. ``VALUE`` is the qualia content.

* **Temporal qualia** (``PROPERTY_TYPE`` ∈ {``absolute_time_start``,
  ``absolute_time_end``}):
  same as scalar, but the PropertyNode's ``property_type`` is set so
  the DP-32 resolver and A.1 compaction pick it up.

* **Epoch membership** (``PROPERTY_TYPE`` = ``has_first_epoch``,
  or the deprecated alias ``belongs_to_epoch`` — kept for backward
  compat with prompt ≤ v5.2): creates a ``has_first_epoch`` edge
  from ``TARGET_ID`` (unit) to
  the Epochs row identified by ``VALUE`` or ``TARGET2_ID``.

* **Stratigraphic relation** (``PROPERTY_TYPE`` ∈ ``_RELATION_TYPES``):
  creates a directed edge from ``TARGET_ID`` to ``TARGET2_ID`` with
  that edge_type.

Attribution
-----------

For every claim row, one or two attribution triples
``(EXTRACTOR_i, DOCUMENT_i, AUTHOR_i)`` may be present:

* If ``EXTRACTOR_i`` populated: create an ExtractorNode with that text,
  link ``ExtractorNode → extracted_from → DocumentNode`` and
  ``PropertyNode → has_data_provenance → ExtractorNode``. If
  ``AUTHOR_i`` is also populated, link
  ``ExtractorNode → has_author → AuthorNode/AuthorAINode`` (subclass
  chosen from ``AUTHOR_KIND_i`` and the Authors sheet).
* If ``EXTRACTOR_i`` is empty but ``AUTHOR_i`` is populated: attach
  ``has_author`` directly to the PropertyNode (claim stated without
  an AI extraction step — e.g. the user declared it themselves).
* If both extractor_1 and extractor_2 populated AND
  ``COMBINER_REASONING`` present: create a ``CombinerNode`` between
  the PropertyNode and the two extractors (``PropertyNode →
  has_data_provenance → CombinerNode``, ``CombinerNode → combines →
  ExtractorNode_i``).

For relational claims the extractor chain hangs off the edge's
``attributes`` dict (``authored_by_id`` / ``authored_by_kind`` /
``document_id``) rather than creating nodes — edges are the natural
subject of a relational claim's attribution.
"""

import os
import uuid
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..graph import Graph
from ..nodes.stratigraphic_node import StratigraphicUnit
from ..nodes.epoch_node import EpochNode
from ..nodes.author_node import AuthorNode, AuthorAINode
from ..nodes.document_node import DocumentNode
from ..nodes.extractor_node import ExtractorNode
from ..nodes.combiner_node import CombinerNode
from ..nodes.property_node import PropertyNode
from ..utils.utils import get_stratigraphic_node_class


# Stratigraphic edge types that a Claims row may declare as a relation.
# Kept in sync with Graph._SOURCE_IS_MORE_RECENT / _TARGET_IS_MORE_RECENT
# and the yEd palette conventions.
_RELATION_TYPES = frozenset({
    "is_after", "is_before",
    "overlies", "is_overlain_by",
    "cuts", "is_cut_by",
    "fills", "is_filled_by",
    "abuts", "is_abutted_by",
    "bonded_to", "equals",
    "has_same_time", "contrasts_with", "changed_from",
})

# Property types that mean "temporal seed for chronology resolver"
_TEMPORAL_PROPERTIES = frozenset({"absolute_time_start", "absolute_time_end"})


class UnifiedXLSXImporter:
    """Import a unified ``em_data.xlsx`` file into a fresh s3dgraphy Graph.

    Usage::

        importer = UnifiedXLSXImporter("em_data.xlsx", graph_id="great_temple")
        graph = importer.parse()

    After ``parse()``:

    * ``importer.graph`` is the populated Graph (also returned).
    * ``importer.warnings`` collects non-fatal issues (unknown references,
      duplicate declarations, ...). They are also appended to
      ``graph.warnings``.
    * ``importer.stats`` reports how many rows of each sheet were read
      and how many nodes/edges were created.
    """

    # Expected sheet names. The importer fails fast if any is missing.
    _SHEETS = ("Units", "Epochs", "Claims", "Authors", "Documents")

    def __init__(self, filepath: str, graph_id: Optional[str] = None):
        self.filepath = filepath
        self.graph_id = graph_id or os.path.splitext(
            os.path.basename(filepath))[0]
        self.graph = Graph(graph_id=self.graph_id)
        self.warnings: List[str] = []
        self.stats: Dict[str, int] = {}

        # Lookup maps populated during parse.
        self._author_by_id: Dict[str, object] = {}
        self._document_by_id: Dict[str, DocumentNode] = {}
        self._epoch_by_id: Dict[str, EpochNode] = {}
        self._unit_by_id: Dict[str, object] = {}

        # Counters for generating paradata serials on the fly (for
        # extractor / combiner short codes).
        self._extractor_counters: Dict[str, int] = {}
        self._combiner_counter = 0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def parse(self) -> Graph:
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Unified xlsx not found: {self.filepath}")

        sheets = self._load_sheets()
        self.stats["rows_units"] = len(sheets["Units"])
        self.stats["rows_epochs"] = len(sheets["Epochs"])
        self.stats["rows_claims"] = len(sheets["Claims"])
        self.stats["rows_authors"] = len(sheets["Authors"])
        self.stats["rows_documents"] = len(sheets["Documents"])

        # Order matters: catalogs first, then skeleton, then claims.
        self._parse_authors(sheets["Authors"])
        self._parse_documents(sheets["Documents"])
        self._parse_epochs(sheets["Epochs"])
        self._parse_units(sheets["Units"])
        self._parse_claims(sheets["Claims"])

        self.stats["nodes_total"] = len(self.graph.nodes)
        self.stats["edges_total"] = len(self.graph.edges)

        # Merge local warnings into the graph so downstream consumers
        # (diagnostics, UI) see them uniformly.
        for w in self.warnings:
            self.graph.warnings.append(w)

        return self.graph

    # ------------------------------------------------------------------
    # Sheet loading
    # ------------------------------------------------------------------

    # Per-sheet column aliases. AI agents (and legacy xlsx files) drift
    # toward variant spellings like ``UNIT_ID`` instead of ``ID``,
    # ``DOC_ID_1`` instead of ``DOCUMENT_1`` or a surplus ``CLAIM_ID``
    # first column. Normalising on load means every parser downstream
    # can read canonical names without worrying about drift.
    _COLUMN_ALIASES: Dict[str, Dict[str, str]] = {
        "Units": {
            "UNIT_ID": "ID",
            "UNITS_ID": "ID",
            "UNIT_TYPE": "TYPE",
        },
        "Epochs": {
            "EPOCH_ID": "ID",
            "EPOCHS_ID": "ID",
        },
        "Authors": {
            "AUTHOR_ID": "ID",
            "AUTHORS_ID": "ID",
            "AUTHOR_KIND": "KIND",
        },
        "Documents": {
            "DOC_ID": "ID",
            "DOCUMENT_ID": "ID",
            "DOCUMENTS_ID": "ID",
        },
        "Claims": {
            # Per-triple document / author variants.
            "DOC_ID_1": "DOCUMENT_1",
            "DOCUMENT_ID_1": "DOCUMENT_1",
            "DOC_1": "DOCUMENT_1",
            "DOC_ID_2": "DOCUMENT_2",
            "DOCUMENT_ID_2": "DOCUMENT_2",
            "DOC_2": "DOCUMENT_2",
            "AUTHOR_ID_1": "AUTHOR_1",
            "AUTHOR_ID_2": "AUTHOR_2",
            # Surplus first column some AIs add for row-level keys; harmless,
            # rename to a reserved slot so it does not collide.
            "CLAIM_ID": "_CLAIM_ID",
        },
    }

    def _load_sheets(self) -> Dict[str, pd.DataFrame]:
        sheets = pd.read_excel(
            self.filepath,
            sheet_name=None,
            engine="openpyxl",
            keep_default_na=True,
        )
        missing = [s for s in self._SHEETS if s not in sheets]
        if missing:
            raise ValueError(
                f"Missing required sheets in {self.filepath}: "
                f"{', '.join(missing)}. Expected: {', '.join(self._SHEETS)}."
            )
        for sheet_name, aliases in self._COLUMN_ALIASES.items():
            df = sheets[sheet_name]
            rename = {col: aliases[col] for col in df.columns
                      if col in aliases and aliases[col] not in df.columns}
            if rename:
                df.rename(columns=rename, inplace=True)
                for src, dst in rename.items():
                    self.warnings.append(
                        f"{sheet_name}: column '{src}' normalised to '{dst}' "
                        f"(accepted alias)."
                    )
        return sheets

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _parse_authors(self, df: pd.DataFrame) -> None:
        for _, row in df.iterrows():
            aid = _str(row.get("ID"))
            if not aid:
                continue
            kind = (_str(row.get("KIND")) or "").lower()
            display = _str(row.get("DISPLAY_NAME"))
            orcid = _str(row.get("ORCID"))
            affil = _str(row.get("AFFILIATION"))

            # The KIND column is authoritative; the ID prefix (A./AI.) is
            # a convention check but not enforced.
            if kind == "extractor":
                cls = AuthorAINode
            elif kind == "author":
                cls = AuthorNode
            else:
                # Fall back to ID prefix, then default to human author.
                cls = AuthorAINode if aid.upper().startswith("AI.") else AuthorNode
                self.warnings.append(
                    f"Author '{aid}' has missing/unknown KIND '{row.get('KIND')!r}'; "
                    f"defaulted to {cls.__name__} based on ID prefix."
                )

            # Compose a description with the extra metadata.
            desc_parts = []
            if display:
                desc_parts.append(display)
            if orcid:
                desc_parts.append(f"ORCID:{orcid}")
            if affil:
                desc_parts.append(affil)
            description = " | ".join(desc_parts) if desc_parts else ""

            node = cls(node_id=str(uuid.uuid4()), name=aid,
                       description=description)
            self.graph.add_node(node)
            self._author_by_id[aid] = node

    def _parse_documents(self, df: pd.DataFrame) -> None:
        for _, row in df.iterrows():
            did = _str(row.get("ID"))
            if not did:
                continue
            filename = _str(row.get("FILENAME"))
            title = _str(row.get("TITLE"))
            year = _str(row.get("YEAR"))
            author_ids = _str(row.get("AUTHOR_IDS"))

            desc_parts = [p for p in (filename, title, year) if p]
            doc = DocumentNode(node_id=str(uuid.uuid4()), name=did,
                               description=" | ".join(desc_parts))
            self.graph.add_node(doc)
            self._document_by_id[did] = doc

            # Link document to its author(s) — one has_author edge each.
            if author_ids:
                for aid in _split_ids(author_ids):
                    author = self._author_by_id.get(aid)
                    if author is None:
                        self.warnings.append(
                            f"Document '{did}' references unknown author '{aid}'"
                        )
                        continue
                    self.graph.add_edge(
                        edge_id=f"{doc.node_id}_has_author_{author.node_id}",
                        edge_source=doc.node_id,
                        edge_target=author.node_id,
                        edge_type="has_author",
                    )

    def _parse_epochs(self, df: pd.DataFrame) -> None:
        for _, row in df.iterrows():
            eid = _str(row.get("ID"))
            if not eid:
                continue
            name = _str(row.get("NAME")) or eid
            start = _num(row.get("START"))
            end = _num(row.get("END"))
            color = _str(row.get("COLOR"))

            epoch = EpochNode(
                node_id=str(uuid.uuid4()),
                name=name,
                start_time=start if start is not None else 0,
                end_time=end if end is not None else 0,
            )
            if color:
                if hasattr(epoch, "color"):
                    epoch.color = color
                if hasattr(epoch, "attributes"):
                    epoch.attributes["fill_color"] = color
            self.graph.add_node(epoch)
            self._epoch_by_id[eid] = epoch

    def _parse_units(self, df: pd.DataFrame) -> None:
        for _, row in df.iterrows():
            uid = _str(row.get("ID"))
            if not uid:
                continue
            type_str = _str(row.get("TYPE")) or "US"
            name = _str(row.get("NAME")) or uid

            cls = get_stratigraphic_node_class(type_str)
            # Robust instantiation: try with (node_id, name, description)
            try:
                node = cls(node_id=str(uuid.uuid4()), name=uid,
                           description=name if name != uid else "")
            except TypeError:
                node = cls(node_id=str(uuid.uuid4()), name=uid)
            self.graph.add_node(node)
            self._unit_by_id[uid] = node

    def _parse_claims(self, df: pd.DataFrame) -> None:
        for idx, row in df.iterrows():
            target_id = _str(row.get("TARGET_ID"))
            if not target_id:
                continue
            prop_type = _str(row.get("PROPERTY_TYPE"))
            if not prop_type:
                self.warnings.append(
                    f"Row {idx + 2}: target '{target_id}' has no PROPERTY_TYPE; skipping."
                )
                continue

            target_node = (self._unit_by_id.get(target_id)
                           or self._epoch_by_id.get(target_id))
            if target_node is None:
                self.warnings.append(
                    f"Row {idx + 2}: TARGET_ID '{target_id}' not declared in "
                    f"Units or Epochs; skipping."
                )
                continue

            value = row.get("VALUE")
            value_str = _str(value)
            target2 = _str(row.get("TARGET2_ID"))

            # Dispatch by semantic class of PROPERTY_TYPE.
            # ``has_first_epoch`` is the canonical name (matches the graph
            # edge type); ``belongs_to_epoch`` is kept as a deprecated alias
            # for xlsx files written against prompt v5.2 and earlier.
            if prop_type in ("has_first_epoch", "belongs_to_epoch"):
                if prop_type == "belongs_to_epoch":
                    self.warnings.append(
                        f"Row {idx + 2}: PROPERTY_TYPE 'belongs_to_epoch' is "
                        f"deprecated — use 'has_first_epoch' instead "
                        f"(accepted for backward compat)."
                    )
                self._handle_belongs_to_epoch(
                    target_node, target2 or value_str, row, idx + 2)
            elif prop_type in _RELATION_TYPES:
                self._handle_relation(
                    target_node, target2, prop_type, row, idx + 2)
            else:
                # Scalar or temporal qualia.
                self._handle_qualia(
                    target_node, prop_type, value, row, idx + 2)

    # ------------------------------------------------------------------
    # Claim handlers
    # ------------------------------------------------------------------

    def _handle_belongs_to_epoch(self, unit_node, epoch_ref, row, line):
        if not epoch_ref:
            self.warnings.append(
                f"Row {line}: belongs_to_epoch row for '{unit_node.name}' "
                f"has no VALUE or TARGET2_ID pointing to an Epochs.ID; skipping."
            )
            return
        epoch = self._epoch_by_id.get(epoch_ref)
        if epoch is None:
            self.warnings.append(
                f"Row {line}: unknown epoch '{epoch_ref}' referenced by "
                f"'{unit_node.name}' — skipping has_first_epoch edge."
            )
            return
        edge_id = f"{unit_node.node_id}_first_{epoch.node_id}"
        self.graph.add_edge(
            edge_id=edge_id,
            edge_source=unit_node.node_id,
            edge_target=epoch.node_id,
            edge_type="has_first_epoch",
        )

    def _handle_relation(self, source_node, target_id, rel_type, row, line):
        if not target_id:
            self.warnings.append(
                f"Row {line}: relational claim '{rel_type}' on '{source_node.name}' "
                f"is missing TARGET2_ID; skipping."
            )
            return
        target_node = (self._unit_by_id.get(target_id)
                       or self._epoch_by_id.get(target_id))
        if target_node is None:
            self.warnings.append(
                f"Row {line}: TARGET2_ID '{target_id}' not declared; "
                f"cannot create '{rel_type}' edge."
            )
            return
        edge_id = str(uuid.uuid4())
        self.graph.add_edge(
            edge_id=edge_id,
            edge_source=source_node.node_id,
            edge_target=target_node.node_id,
            edge_type=rel_type,
        )
        # Attach attribution as edge metadata (no graph nodes created).
        edge = next(e for e in self.graph.edges if e.edge_id == edge_id)
        self._annotate_edge_attribution(edge, row)

    def _handle_qualia(self, target_node, prop_type, value, row, line):
        value_str = _str(value)
        units = _str(row.get("UNITS"))
        # PropertyNode stores the value; units (if any) go into a
        # dedicated attribute so consumers can render "14.5 m" or just
        # "14.5" depending on context.
        pn = PropertyNode(
            node_id=str(uuid.uuid4()),
            name=prop_type,
            property_type=prop_type,
            value=value_str or "",
            description="",
        )
        if units:
            pn.attributes["units"] = units
        self.graph.add_node(pn)
        # has_property edge from the target to the property
        self.graph.add_edge(
            edge_id=f"{target_node.node_id}_has_prop_{pn.node_id}",
            edge_source=target_node.node_id,
            edge_target=pn.node_id,
            edge_type="has_property",
        )
        self._attach_attribution_chain(pn, row, line)

    # ------------------------------------------------------------------
    # Attribution machinery
    # ------------------------------------------------------------------

    def _attach_attribution_chain(self, property_node, row, line):
        """Build the ExtractorNode / DocumentNode / AuthorNode chain
        around ``property_node`` using the two optional triples
        (EXTRACTOR_i, DOCUMENT_i, AUTHOR_i) in the Claims row.
        """
        triples = list(self._iter_attribution_triples(row, line))

        if not triples:
            return

        # Case A: 1 triple → single-source chain.
        # Case B: 2 triples + COMBINER_REASONING → combiner chain.
        combiner_text = _str(row.get("COMBINER_REASONING"))

        if len(triples) == 1 or not combiner_text:
            for triple in triples:
                self._build_single_source(property_node, triple)
            return

        # Combiner: one CombinerNode fronting the two extractors.
        self._combiner_counter += 1
        comb = CombinerNode(
            node_id=str(uuid.uuid4()),
            name=f"C.{self._combiner_counter:02d}",
            description=combiner_text,
        )
        self.graph.add_node(comb)
        self.graph.add_edge(
            edge_id=f"{property_node.node_id}_prov_{comb.node_id}",
            edge_source=property_node.node_id,
            edge_target=comb.node_id,
            edge_type="has_data_provenance",
        )
        for triple in triples:
            ext = self._create_extractor(triple, parent_origin=comb)
            self.graph.add_edge(
                edge_id=f"{comb.node_id}_combines_{ext.node_id}",
                edge_source=comb.node_id,
                edge_target=ext.node_id,
                edge_type="combines",
            )
            self._attach_author_to_origin(ext, triple)

    def _iter_attribution_triples(self, row, line):
        for suffix in ("_1", "_2"):
            ext_text = _str(row.get(f"EXTRACTOR{suffix}"))
            doc_id = _str(row.get(f"DOCUMENT{suffix}"))
            author_id = _str(row.get(f"AUTHOR{suffix}"))
            kind = (_str(row.get(f"AUTHOR_KIND{suffix}")) or "").lower()
            if not (ext_text or author_id):
                continue
            yield {
                "extractor_text": ext_text,
                "document_id": doc_id,
                "author_id": author_id,
                "author_kind": kind,
                "line": line,
            }

    def _build_single_source(self, property_node, triple):
        """Create the ExtractorNode / DocumentNode / has_author chain
        for a single-source row, or attach has_author directly to the
        PropertyNode when no extractor text is provided.
        """
        if not triple["extractor_text"]:
            # Author-only declaration: skip the extractor node, attach
            # has_author directly to the PropertyNode.
            self._attach_author_to_origin(property_node, triple)
            return

        ext = self._create_extractor(triple, parent_origin=property_node)
        self.graph.add_edge(
            edge_id=f"{property_node.node_id}_prov_{ext.node_id}",
            edge_source=property_node.node_id,
            edge_target=ext.node_id,
            edge_type="has_data_provenance",
        )
        self._attach_author_to_origin(ext, triple)

    def _create_extractor(self, triple, parent_origin):
        """Create an ExtractorNode with a ``D.XX.YY`` short code (XX
        tracking the document's global serial, YY the per-document
        sequence). When DOCUMENT_i is missing, uses the generic
        prefix ``D.00``.
        """
        doc_node = None
        doc_short = "D.00"
        if triple["document_id"]:
            doc_node = self._document_by_id.get(triple["document_id"])
            if doc_node is None:
                self.warnings.append(
                    f"Row {triple['line']}: unknown DOCUMENT '{triple['document_id']}'; "
                    f"extractor will be orphaned from its document."
                )
            else:
                doc_short = doc_node.name

        counter = self._extractor_counters.get(doc_short, 0) + 1
        self._extractor_counters[doc_short] = counter
        ext_short = f"{doc_short}.{counter:02d}"

        ext = ExtractorNode(
            node_id=str(uuid.uuid4()),
            name=ext_short,
            description=triple["extractor_text"],
        )
        self.graph.add_node(ext)

        if doc_node is not None:
            self.graph.add_edge(
                edge_id=f"{ext.node_id}_from_{doc_node.node_id}",
                edge_source=ext.node_id,
                edge_target=doc_node.node_id,
                edge_type="extracted_from",
            )
        return ext

    def _attach_author_to_origin(self, origin_node, triple):
        """Attach a has_author edge from ``origin_node`` (ExtractorNode
        or PropertyNode) to the AuthorNode/AuthorAINode identified by
        ``AUTHOR_i``. Warns if the author id is unknown.
        """
        author_id = triple["author_id"]
        if not author_id:
            return
        author = self._author_by_id.get(author_id)
        if author is None:
            self.warnings.append(
                f"Row {triple['line']}: unknown AUTHOR '{author_id}'; "
                f"skipping has_author edge."
            )
            return
        # Sanity-check kind against the node class.
        kind = triple.get("author_kind")
        expected_kind = (
            "extractor" if isinstance(author, AuthorAINode) else "author"
        )
        if kind and kind != expected_kind:
            self.warnings.append(
                f"Row {triple['line']}: AUTHOR_KIND='{kind}' for '{author_id}' "
                f"disagrees with the author's declared kind '{expected_kind}' "
                f"in the Authors sheet; using the Authors sheet as truth."
            )
        self.graph.add_edge(
            edge_id=f"{origin_node.node_id}_has_author_{author.node_id}",
            edge_source=origin_node.node_id,
            edge_target=author.node_id,
            edge_type="has_author",
        )

    def _annotate_edge_attribution(self, edge, row):
        """Relational claims don't get a PropertyNode; instead, we store
        the attribution on the edge's ``attributes`` dict so downstream
        consumers (diagnostics, UI) can still trace who asserted the
        relation.
        """
        for suffix in ("_1", "_2"):
            author_id = _str(row.get(f"AUTHOR{suffix}"))
            if not author_id:
                continue
            key_author = f"authored_by{suffix}"
            key_kind = f"authored_kind{suffix}"
            key_doc = f"document{suffix}"
            edge.attributes[key_author] = author_id
            kind = (_str(row.get(f"AUTHOR_KIND{suffix}")) or "").lower()
            if kind:
                edge.attributes[key_kind] = kind
            doc = _str(row.get(f"DOCUMENT{suffix}"))
            if doc:
                edge.attributes[key_doc] = doc


# ---------------------------------------------------------------------------
# Tiny helpers (string coercion without pandas NaN surprises)
# ---------------------------------------------------------------------------

def _str(v) -> str:
    """Return a trimmed string form of ``v``, treating NaN / None / empty
    as an empty string.
    """
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none") else s


def _num(v) -> Optional[float]:
    """Return a float for numeric inputs; None for empties / NaN / garbage."""
    s = _str(v)
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _split_ids(s: str) -> List[str]:
    """Split a comma/semicolon-separated id string."""
    out = []
    for part in s.replace(";", ",").split(","):
        part = part.strip()
        if part:
            out.append(part)
    return out
