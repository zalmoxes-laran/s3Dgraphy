"""Public API for pyArchInit ``rapporti`` ↔ canonical s3dgraphy edges.

This module is the single home for the bidirectional mapping between
pyArchInit's stratigraphic ``rapporti`` packed string format and the
canonical edge types in the s3dgraphy property graph.

Architectural baseline (decided 2026-06-04 with the EM project lead):

* **In s3dgraphy in memory**, physical/topological stratigraphic
  relationships (``copre`` / ``coperto da`` / ``taglia`` / …) are
  **first-class edges** between US-type nodes — ``overlies`` /
  ``is_overlain_by`` / ``cuts`` / etc., the canonical edge types
  declared in ``s3Dgraphy_connections_datamodel.json`` and already
  recognised by the GraphML exporter, the unified XLSX importer and
  the JSON exporter. The property graph carries the single source of
  truth.

* **In pyArchInit's `us_table.rapporti` column**, the same
  relationships are serialised as a list-of-lists Python literal
  (e.g. ``[["Copre", "12", "1", "Pompei"], …]``). pyArchInit's
  vocabulary mixes Italian and English terms; the GraphML world has
  used both depending on the file's provenance, so we accept both
  on parse and emit canonical Italian on serialise.

* **In yEd GraphML (EM 1.6 palette onwards)**, the same
  relationships are serialised again, this time as a packed string
  attribute ``physical_relationships`` on each US node — because yEd
  edges are reserved for the temporal Matrix dimension and cannot
  visually carry physical relations without polluting the layout.
  The packed format is the **same pyArchInit-native list-of-lists**
  so the GraphML ↔ pyArchInit transit is byte-identical when the
  graph between them is unmutated.

This module exposes the constants the parsers / serialisers /
dispatchers consume. The parse/serialise *functions* land in a later
commit; today's commit is purely the constants extraction from
``graphml_writer.py`` and ``graph_ingestor.py`` so the canonical
vocabulary lives in one place.

The legacy private names (``_RAPPORTI_TO_EDGE_TYPE`` etc.) remain
importable from their original modules — see the re-export shims at
the bottom of ``graphml_writer.py`` and ``graph_ingestor.py``.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Forward: pyArchInit-native label → canonical s3dgraphy edge type
# ---------------------------------------------------------------------------
#: pyArchInit ``rapporti`` labels (Italian + English) mapped to canonical
#: s3dgraphy edge types declared in
#: ``s3Dgraphy_connections_datamodel.json``.
#:
#: Used by:
#:
#: * ``s3dgraphy.sync.graph_projector`` when reading the
#:   ``us_table.rapporti`` column out of a pyArchInit DB and turning
#:   each entry into a graph edge.
#: * ``s3dgraphy.sync.graphml_writer`` for the same translation step
#:   when an external pipeline feeds ``rapporti``-style strings into
#:   the writer's pre-export enrichment.
#:
#: pyArchInit's vocabulary is loose — older sites have Italian terms,
#: newer ones with English UIs have English. Both are accepted on
#: import. On serialise we emit the verbose Italian form (or shorthand
#: tokens for non-canonical unit types — see ``RAPPORTI_SHORTHAND``).
RAPPORTI_TO_EDGE_TYPE: dict[str, str] = {
    # Italian
    "copre": "overlies",
    "coperto da": "is_overlain_by",
    "taglia": "cuts",
    "tagliato da": "is_cut_by",
    "riempie": "fills",
    "riempito da": "is_filled_by",
    "uguale a": "is_physically_equal_to",
    "si lega a": "is_bonded_to",
    "si appoggia a": "abuts",
    "gli si appoggia": "is_abutted_by",
    # English
    "covers": "overlies",
    "covered by": "is_overlain_by",
    "cuts": "cuts",
    "cut by": "is_cut_by",
    "fills": "fills",
    "filled by": "is_filled_by",
    "same as": "is_physically_equal_to",
    "bonds with": "is_bonded_to",
    "abuts": "abuts",
}


# ---------------------------------------------------------------------------
# Inverse: canonical edge type → verbose Italian rapporti label
# ---------------------------------------------------------------------------
#: Inverse of ``RAPPORTI_TO_EDGE_TYPE`` for the verbose-Italian dispatch
#: (the form pyArchInit's Scheda US shows). Used when serialising
#: canonical edges back into the ``us_table.rapporti`` column for the
#: subset of edges whose endpoints are both canonical Harris units
#: (US / USM ↔ US / USM). For other unit-type combinations the
#: serialiser falls back to ``RAPPORTI_SHORTHAND`` instead (see
#: convention notes below).
#:
#: ``is_after`` falls back to ``Copre`` because that's the
#: stratigraphic-precedence default pyArchInit's UI assumes when no
#: more-specific physical relation is declared.
#: ``generic_connection`` falls back to ``Connesso a`` (used for
#: paradata data-flow shorthand ``>>`` / ``<<`` that travels through
#: pyArchInit as a free-text term).
EDGE_TYPE_TO_RAPPORTI_IT: dict[str, str] = {
    "overlies": "Copre",
    "is_overlain_by": "Coperto da",
    "cuts": "Taglia",
    "is_cut_by": "Tagliato da",
    "fills": "Riempie",
    "is_filled_by": "Riempito da",
    "is_physically_equal_to": "Uguale a",
    "is_bonded_to": "Si lega a",
    "abuts": "Si appoggia a",
    "is_abutted_by": "Gli si appoggia",
    "is_after": "Copre",       # default fallback for temporal precedence
    "generic_connection": "Connesso a",
}


# ---------------------------------------------------------------------------
# Shorthand tokens for relations between non-Harris unit types
# ---------------------------------------------------------------------------
#: Shorthand ``rapporti`` tokens for relations between non-US/USM units
#: (USVs / USVn / SF / CON / Combinar / Extractor / property / DOC).
#: Per pyArchInit author convention (May 2026):
#:
#: * single arrow ``>`` / ``<`` carries simple temporal precedence
#:   (used for Continuity units, ``CON``);
#: * double arrow ``>>`` / ``<<`` carries paradata-style data flow
#:   (Extractor / Combiner / property / DOC chains, expressed as
#:   ``generic_connection`` edges so the GraphML writer's paradata
#:   filter handles them correctly).
#:
#: Each value is ``(edge_type, swap)``:
#:
#: * ``swap=False`` means emit the edge with source / target as the
#:   user wrote them (``A > B`` → ``A is_after B``);
#: * ``swap=True`` means swap source / target (``A < B`` →
#:   ``B is_after A``).
#:
#: Mirrored in ``EDGE_TYPE_DIRECTION_FORWARD`` for the
#: serialise direction.
RAPPORTI_SHORTHAND: dict[str, tuple[str, bool]] = {
    ">":  ("is_after", False),            # A > B  ⇒  A is_after B
    "<":  ("is_after", True),             # A < B  ⇒  B is_after A
    ">>": ("generic_connection", False),  # A >> B ⇒  A → B
    "<<": ("generic_connection", True),   # A << B ⇒  B → A
}


# ---------------------------------------------------------------------------
# Edge-type direction for shorthand serialise
# ---------------------------------------------------------------------------
#: Per-edge-type direction. ``True`` means the rapporti token reads as
#: ``>`` / ``>>`` (source covers target); ``False`` means ``<`` / ``<<``
#: (source is covered by target).
#:
#: Used by the serialiser when the dispatch logic falls back to
#: shorthand for non-canonical unit-type endpoints.
EDGE_TYPE_DIRECTION_FORWARD: dict[str, bool] = {
    "overlies": True,
    "is_overlain_by": False,
    "cuts": True,
    "is_cut_by": False,
    "fills": True,
    "is_filled_by": False,
    "is_physically_equal_to": True,   # equality conventionally `>`
    "is_bonded_to": True,
    "abuts": True,
    "is_abutted_by": False,
    "is_after": True,
    "is_before": False,
    "generic_connection": True,
    "extracted_from": True,
    "combines": True,
    "has_property": True,
}


# ---------------------------------------------------------------------------
# Unit-type frozensets driving the verbose-vs-shorthand dispatch
# ---------------------------------------------------------------------------
#: Unit types where both endpoints get the verbose Italian dispatch
#: ("Copre", "Coperto da", ...). Stratigraphic Harris atoms only.
CANONICAL_UNIT_TYPES: frozenset[str] = frozenset({"US", "USM"})


#: Continuity unit type. Single-arrow shorthand ``>`` / ``<`` is
#: reserved for relations where at least one endpoint is a CON.
CONTINUITY_UNIT_TYPES: frozenset[str] = frozenset({"CON"})


__all__ = [
    "RAPPORTI_TO_EDGE_TYPE",
    "EDGE_TYPE_TO_RAPPORTI_IT",
    "RAPPORTI_SHORTHAND",
    "EDGE_TYPE_DIRECTION_FORWARD",
    "CANONICAL_UNIT_TYPES",
    "CONTINUITY_UNIT_TYPES",
]

# NOTE — the Python class-name → pyArchInit `unita_tipo` lookup
# (currently `_S3DGRAPHY_TYPE_TO_UNITA_TIPO` in graph_ingestor.py)
# is intentionally NOT moved into this module in this commit. The
# canonical copy carries more entries (paradata classes, continuity
# nodes, yEd-import-pipeline synthetic types) than belong in a
# pyArchInit-rapporti-focused vocabulary file. It moves in a later
# refactor commit alongside the verbose-vs-shorthand dispatch
# function `_select_rapporti_label`.

