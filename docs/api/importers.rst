Importers API
=============

s3dgraphy reads external data through a family of importers. They fall
into two groups:

* **Mapping-driven importers** subclass
  :class:`~s3dgraphy.importer.base_importer.BaseImporter` and read tabular
  sources (Excel, SQLite/PostgreSQL) according to a JSON *mapping*. They
  share a two-pass pipeline (units first, then epochs and relations), the
  1.6 *row-filter* API, and an *enrichment* mode that augments an existing
  graph.
* **Fixed-format importers** parse a self-describing source and do not need
  a mapping: :class:`~s3dgraphy.importer.import_graphml.GraphMLImporter`
  (yEd GraphML) and
  :class:`~s3dgraphy.importer.unified_xlsx_importer.UnifiedXLSXImporter`
  (the single-file ``em_data.xlsx``).

Every importer exposes a single :meth:`parse` method that returns a
populated :class:`~s3dgraphy.graph.Graph`.

Choosing an importer
--------------------

.. list-table::
   :header-rows: 1
   :widths: 26 20 18 36

   * - Class
     - Source
     - Mapping?
     - When to use
   * - ``GraphMLImporter``
     - yEd ``.graphml``
     - no
     - Round-trip editing in yEd; UUID slipback; comment-node skipping.
   * - ``UnifiedXLSXImporter``
     - ``em_data.xlsx`` (5 sheets)
     - no
     - StratiMiner output / single-file authoring of the full graph.
   * - ``MappedXLSXImporter``
     - ``.xlsx``
     - required
     - EMdb-style spreadsheets; column-name normalisation; enrichment.
   * - ``XLSXImporter``
     - ``.xlsx``
     - required
     - Simple mapped Excel import (no column normalisation).
   * - ``PyArchInitImporter``
     - SQLite **or** PostgreSQL
     - required
     - Pulling pyArchInit records (``filepath`` or ``connection_url``).
   * - ``QualiaImporter``
     - ``em_paradata.xlsx``
     - no
     - **Deprecated** — superseded by ``UnifiedXLSXImporter``.

The row-filter API (1.6)
------------------------

Every :class:`BaseImporter` subclass accepts a ``filters={column: value}``
keyword (AND semantics, exact case-sensitive match). ``filters`` defaults
to ``None`` so existing code is unaffected. Two helpers let a consumer
build a filter UI *before* importing:

* :meth:`~s3dgraphy.importer.base_importer.BaseImporter.get_filter_columns`
  — returns the columns the mapping marked ``is_filter: true`` (with their
  ``display_name`` and ``filter_required`` flags).
* :meth:`~s3dgraphy.importer.base_importer.BaseImporter.get_distinct_values`
  — returns the sorted distinct values of a column, to populate a dropdown.

.. code-block:: python

   from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter

   probe = PyArchInitImporter(filepath="dig.sqlite",
                              mapping_name="pyarchinit_us_mapping")
   for spec in probe.get_filter_columns():
       print(spec["display_name"], probe.get_distinct_values(spec["column"]))

   importer = PyArchInitImporter(filepath="dig.sqlite",
                                 mapping_name="pyarchinit_us_mapping",
                                 filters={"sito": "Pompei", "area": "A"})
   graph = importer.parse()

See :doc:`/importers/mapping_schema` for the full mapping JSON schema and
:doc:`/s3dgraphy_mapping_system` for the mapping registry.

Base importer
-------------

.. automodule:: s3dgraphy.importer.base_importer
   :members:
   :undoc-members:
   :show-inheritance:

GraphML importer
----------------

The GraphML importer reuses any ``EMID`` stored on a yEd node as the
node's UUID (*UUID slipback*), so a node keeps its identity across
export/edit/re-import cycles. It also skips yEd comment/note nodes
(yellow fills), restores the physical stratigraphic relations and
structured PropertyNode metadata from the GraphML side-channels, and
enhances placeholder edge types to their semantic form.

.. automodule:: s3dgraphy.importer.import_graphml
   :members:
   :undoc-members:
   :show-inheritance:

Mapped XLSX importer
--------------------

.. automodule:: s3dgraphy.importer.mapped_xlsx_importer
   :members:
   :undoc-members:
   :show-inheritance:

XLSX importer
-------------

.. automodule:: s3dgraphy.importer.xlsx_importer
   :members:
   :undoc-members:
   :show-inheritance:

Unified XLSX importer
---------------------

The single-file ``em_data.xlsx`` importer. See the dedicated guide
:doc:`/importers/unified_xlsx_importer` for the sheet schema and the
claim/attribution model.

.. automodule:: s3dgraphy.importer.unified_xlsx_importer
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

pyArchInit importer (SQLite / PostgreSQL)
-----------------------------------------

Reads pyArchInit ``us_table`` records. Pass either a ``filepath`` (SQLite
file) or the keyword-only ``connection_url`` (a SQLAlchemy-style
``postgresql://…`` URL). Supports node-name templating via the mapping's
``node_name_template`` and the same filter API as the other mapped
importers.

.. automodule:: s3dgraphy.importer.pyarchinit_importer
   :members:
   :undoc-members:
   :show-inheritance:

Qualia importer (deprecated)
----------------------------

.. deprecated:: 1.6
   Use :class:`~s3dgraphy.importer.unified_xlsx_importer.UnifiedXLSXImporter`
   (single-file ``em_data.xlsx``) instead. See :doc:`/deprecations`.

.. automodule:: s3dgraphy.importer.qualia_importer
   :members:
   :undoc-members:
   :show-inheritance:
