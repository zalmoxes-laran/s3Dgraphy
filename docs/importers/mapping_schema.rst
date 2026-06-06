.. _mapping-schema:

Mapping JSON Schema Reference
=============================

.. versionadded:: 1.6
   ``is_filter`` / ``filter_required`` flags and the importer
   ``get_filter_columns()`` / ``get_distinct_values()`` / ``filters=``
   API introduced in this release. The ``node_name_template`` field on
   ``table_settings`` (composite node names) is also new in 1.6.

s3dgraphy imports from tabular sources (SQLite tables, XLSX sheets,
generic CSVs) by reading a JSON mapping file that describes how each
column relates to the graph: which one identifies a row, which become
node attributes or :class:`~s3dgraphy.nodes.property_node.PropertyNode`
instances, which encode relations to other rows, and (from 1.6 onward)
which can be exposed as user-selectable filters to a consumer
application.

This page is the **complete reference** for the schema. It is intended
to be read in parallel with the two annotated template files that ship
with the library:

- ``src/s3dgraphy/mappings/template_pyarchinit_mapping.json`` —
  SQLite tables (PyArchInit-style).
- ``src/s3dgraphy/mappings/template_emdb_mapping.json`` —
  XLSX sheets (EMdb-style).

Both templates carry inline ``_comment`` fields next to every key, so
they double as worked examples. Neither file is auto-loaded by the
:class:`~s3dgraphy.mappings.registry.MappingRegistry` — they live at
the root of the ``mappings/`` folder and exist only as reference.

.. seealso::

   - :doc:`/s3dgraphy_mapping_system` — narrative guide and tutorial.
   - :doc:`/s3dgraphy_import_export` — end-to-end import/export overview.
   - :doc:`/api/s3dgraphy_edges_reference` — edge-type catalogue used
     in the ``relations`` array.

Schema overview
---------------

A mapping JSON file is a single object with the following top-level
keys:

==========================  ==========  ==========================================
Key                         Required    Purpose
==========================  ==========  ==========================================
``name``                    optional    Human-readable label.
``description``             optional    Free-text description of what the mapping
                                        targets (table layout, project, etc.).
``version``                 optional    Author-defined version string. Not
                                        validated by the importer.
``table_settings``          required    Source-format settings: format type,
                                        table or sheet name, header offsets, ...
``column_mappings``         required    Dict, keyed by source-column name, whose
                                        values declare per-column behaviour.
``relations``               optional    Array of edge specs that turn cell values
                                        into graph edges.
==========================  ==========  ==========================================

Minimal skeleton:

.. code-block:: json

   {
     "name": "My mapping",
     "description": "...",
     "version": "1.0",
     "table_settings": { "format_type": "sqlite", "table_name": "us_table" },
     "column_mappings": {
       "us":  { "is_id": true, "node_type": "US" },
       "txt": { "is_description": true }
     },
     "relations": []
   }

table_settings
--------------

The ``table_settings`` object selects the source format and provides
format-specific addressing.

SQLite (``format_type: "sqlite"``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Used by :class:`~s3dgraphy.importer.pyarchinit_importer.PyArchInitImporter`.

.. list-table::
   :header-rows: 1
   :widths: 20 12 68

   * - Key
     - Required
     - Meaning
   * - ``format_type``
     - yes
     - Must be the literal string ``"sqlite"``.
   * - ``table_name``
     - yes
     - Name of the table to read with ``SELECT * FROM <table_name>``. Guarded
       against a ``[A-Za-z_][A-Za-z0-9_]*`` whitelist to prevent SQL injection.

.. code-block:: json

   "table_settings": {
     "format_type": "sqlite",
     "table_name": "us_table"
   }

XLSX (``format_type: "xlsx"``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Used by :class:`~s3dgraphy.importer.xlsx_importer.MappedXLSXImporter`
and :class:`~s3dgraphy.importer.xlsx_importer.XLSXImporter`.

.. list-table::
   :header-rows: 1
   :widths: 18 12 70

   * - Key
     - Required
     - Meaning
   * - ``format_type``
     - yes
     - Must be the literal string ``"xlsx"``.
   * - ``sheet_name``
     - yes
     - Worksheet to read. String name or 0-based index.
   * - ``start_row``
     - optional
     - 1-indexed row of the first **data** row. Row 1 always holds column
       headers; ``start_row=1`` means data starts on row 2. Defaults vary by
       importer.
   * - ``header_row``
     - optional
     - 0-indexed row index passed to pandas as the column header. Mutually
       exclusive with ``start_row`` in practice — pick the one your importer
       reads.

.. code-block:: json

   "table_settings": {
     "format_type": "xlsx",
     "sheet_name": "Sheet1",
     "start_row": 1
   }

column_mappings
---------------

A dict whose **keys are the source column names** as they appear in the
SQLite table or the XLSX header row. Each value is a *column spec*: a
small dict of flags describing what the column means.

Role flags — pick one per column
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following flags are **mutually exclusive**. A column plays exactly
one role in the graph:

``is_id`` (bool, default ``false``)
   Marks the row identifier. The cell value becomes the **name** of a
   :class:`~s3dgraphy.nodes.base_node.Node` in the graph (and the node
   id, for the automatic / non-mapped mode). **Exactly one** column in
   ``column_mappings`` must be flagged ``is_id: true``; the importer
   raises ``ValueError`` if zero or more than one are found. Pair with
   ``node_type`` to choose the stratigraphic subclass (``US``, ``USV``,
   ``USD``, ``SF``, ``TSU``, ``RSF``, ``USN``, ``USVs``, ``USVn``,
   ``VSF``, ``serSU``, ``serUSD``, ``serUSVn`` — see
   :func:`s3dgraphy.utils.utils.get_stratigraphic_node_class`).

``is_description`` (bool, default ``false``)
   The cell value becomes the
   :attr:`~s3dgraphy.nodes.base_node.Node.description` of the row's
   stratigraphic node. At most one column should carry this flag.

``is_attribute`` (bool, default ``false``)
   The cell value is stored **as an attribute on the stratigraphic node
   itself**, not as a separate :class:`PropertyNode`. The attribute name
   defaults to the column name, but can be overridden with
   ``property_name``. Use this for fields that downstream consumers
   (e.g. GraphML exporters) read directly off the node — for example
   ``EXTRACTOR`` and ``DOCUMENT`` columns consumed by the
   ``ParadataNodeGroup`` writer. Multiple ``is_attribute`` columns are
   allowed on the same row.

PropertyNode columns (default behaviour)
   A column that carries **none** of the role flags above is treated
   as a regular property column: the importer creates one
   :class:`PropertyNode` per row, named with the column's
   ``display_name`` (or the column name if no display name is given),
   and links it to the row's stratigraphic node with a
   ``has_property`` edge. The ``property_name`` key, when present, is
   stored on the resulting PropertyNode.

EpochNode columns
   When a column declares ``"node_type": "EpochNode"``, the importer
   instead creates one
   :class:`~s3dgraphy.nodes.epoch_node.EpochNode` per distinct value
   and links the stratigraphic node to it with a ``has_first_epoch``
   edge. The importer also recognises companion columns
   ``<col>_START`` / ``<col>_END`` (or any column whose
   ``property_name`` ends in ``Start`` / ``End``) and uses them to
   populate the epoch's
   :attr:`~s3dgraphy.nodes.epoch_node.EpochNode.start_time` /
   :attr:`~s3dgraphy.nodes.epoch_node.EpochNode.end_time`.

Decorative keys
~~~~~~~~~~~~~~~

Keys that apply to several role flags:

==================  =============================================================
Key                 Meaning
==================  =============================================================
``display_name``    Human-readable label. For PropertyNode columns it is also
                    used as the property name. Surfaced by
                    ``get_filter_columns()`` for filter columns.
``description``     Free-text description of the column, returned to consumers
                    that introspect the mapping.
``property_name``   Override the attribute / property name written into the
                    graph. Used by both ``is_attribute`` and EpochNode columns.
``node_type``       For ``is_id`` columns: the stratigraphic subclass. For
                    other columns: ``"PropertyNode"`` (default) or
                    ``"EpochNode"``.
==================  =============================================================

Filter columns (1.6+)
~~~~~~~~~~~~~~~~~~~~~

The ``is_filter`` / ``filter_required`` flags are **orthogonal** to the
role flags above. A single column can be both ``is_filter: true`` and
``is_attribute: true`` (or ``is_description: true``), but the
combination ``is_filter + is_id`` does not make sense and should be
avoided — a filter restricts which rows are imported, while the id
column distinguishes one row from another within that subset.

``is_filter`` (bool, default ``false``)
   Marks the column as a *filter candidate*. The consumer application
   (CLI, GUI, web form, ...) can discover these columns at import time
   via :meth:`BaseImporter.get_filter_columns` and present them to the
   user as dropdowns. The library itself does not render any UI.

``filter_required`` (bool, default ``false``)
   When ``true``, the consumer is expected to force the user to pick a
   value before triggering the import (no "All values" option). When
   ``false``, the filter is optional and may be skipped. Validation is
   the consumer's responsibility; the importer accepts an empty
   ``filters`` dict regardless.

``display_name`` (string, default = column name)
   Label surfaced by ``get_filter_columns()`` for display in the
   consumer UI.

JSON example:

.. code-block:: json

   "column_mappings": {
     "sito": {
       "is_filter": true,
       "filter_required": true,
       "display_name": "Site",
       "description": "Archaeological site name."
     },
     "area": {
       "is_filter": true,
       "filter_required": false,
       "display_name": "Excavation Area"
     },
     "us": { "is_id": true, "node_type": "US" },
     "d_stratigrafica": { "is_description": true }
   }

Consumer-side flow:

.. code-block:: python

   from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter

   # 1) Instantiate once to discover available filters and values.
   probe = PyArchInitImporter(
       filepath="excavation.sqlite",
       mapping_name="pyarchinit_us_mapping",
   )
   for spec in probe.get_filter_columns():
       column = spec["column"]
       label = spec["display_name"]
       required = spec["filter_required"]
       values = probe.get_distinct_values(column)
       print(f"{label} ({'required' if required else 'optional'}): {values}")

   # 2) Re-instantiate with the values the user picked.
   importer = PyArchInitImporter(
       filepath="excavation.sqlite",
       mapping_name="pyarchinit_us_mapping",
       filters={"sito": "Pompei", "area": "A"},
   )
   graph = importer.parse()

Filter semantics
^^^^^^^^^^^^^^^^

- **AND combination.** Multiple entries in the ``filters`` dict are
  combined with logical AND. ``{"sito": "Pompei", "area": "A"}``
  imports only the rows where *both* conditions hold.
- **Exact match, single value.** Each filter compares ``column == value``
  with no wildcards, ranges, or lists. To allow several values for the
  same column, instantiate the importer once per value and merge the
  resulting graphs, or extend the importer.
- **Case-sensitive.** Comparison is exact at the database / pandas
  level.
- **Empty / ``None`` disables filtering.** Passing ``filters=None`` or
  ``filters={}`` imports every row.
- **Column validation.** SQL backends route filter column names through
  :meth:`BaseImporter._validate_filter_column`, which checks they appear
  in ``column_mappings`` before interpolating into the SQL string. The
  filter *value* is always parameter-bound (``?`` placeholder), so it
  cannot inject SQL.

Filter discovery API
~~~~~~~~~~~~~~~~~~~~

.. method:: BaseImporter.get_filter_columns()
   :noindex:

   Return a list of column specs flagged as ``is_filter: true`` in the
   mapping. Each entry is a shallow copy of the column spec with an
   extra ``"column"`` key added, holding the original column name.
   Defaults for ``filter_required`` (``False``) and ``display_name``
   (the column name) are surfaced explicitly so callers do not need
   ``.get()``.

   :rtype: list[dict]

.. method:: BaseImporter.get_distinct_values(column)
   :noindex:

   Return the sorted list of distinct, non-null values present in
   ``column`` in the source data. Implementation is format-specific:

   - SQLite: ``SELECT DISTINCT col FROM table WHERE col IS NOT NULL
     ORDER BY col``.
   - XLSX: pandas ``Series.unique`` over the loaded sheet, sorted.

   :param column: Column name to enumerate. Should usually come from
       a ``"column"`` key of ``get_filter_columns()``.
   :rtype: list

.. note::

   :class:`~s3dgraphy.importer.unified_xlsx_importer.UnifiedXLSXImporter`
   is intentionally **not** part of the filter API: its
   ``em_data.xlsx`` workbook has its own 5-sheet semantic schema
   (Units / Epochs / Claims / Authors / Documents) where "filter one
   site out of many" is not a meaningful operation.

Composite node names (1.6+)
---------------------------

.. versionadded:: 1.6

By default, the **name** of each imported stratigraphic node is the
bare cell value of the ``is_id`` column — for a pyArchInit ``us_table``
that is just the US number (``"101"``, ``"1002"``, ...). Plain numeric
labels collide easily across sites/areas and don't match the dotted
labelling convention that yEd-curated EMdb graphs commonly use
(``"A.US.101"``).

The optional ``node_name_template`` field, set on ``table_settings``,
lets a mapping declare a **composite name** built from several columns
of the row. The id column's role is unchanged — it still identifies
the row's primary key for cross-row relations — but the
:attr:`~s3dgraphy.nodes.base_node.Node.name` written to the graph is
now the rendered template.

Syntax
~~~~~~

The template is a Python ``str.format``-style string with
``{column_name}`` placeholders. Each placeholder is the literal name
of a column in the source table; it does **not** need to be the
``is_id`` column or even appear in ``column_mappings`` (but listing it
there is recommended for documentation and so the registered importer
can validate it).

.. code-block:: json

   "table_settings": {
     "format_type": "sqlite",
     "table_name": "us_table",
     "node_name_template": "{area}.{unita_tipo}.{us}"
   }

For a row with ``area="A"``, ``unita_tipo="US"``, ``us="101"``, the
resulting node name is ``"A.US.101"``.

NULL / empty handling
~~~~~~~~~~~~~~~~~~~~~

Components whose cell value is ``None`` or an empty string are
**omitted** from the composite. After substitution the importer
collapses runs of separator dots to a single dot and strips
leading/trailing dots, so:

- ``area="A"``, ``unita_tipo=""``, ``us="101"`` → ``"A.101"`` (not
  ``"A..101"``).
- ``area=None``, ``unita_tipo=""``, ``us="101"`` → ``"101"``.

If *every* component resolves to an empty string, the importer falls
back to ``str(row[is_id column])`` — a defensive fallback to avoid
silently colliding multiple empty-named nodes.

Fallback when the template is absent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If ``node_name_template`` is not declared, the importer uses the
pre-1.6 behaviour: ``node_name = str(row[is_id column])``. The feature
is fully opt-in for custom mappings.

.. warning::

   **Breaking change for the default pyArchInit mapping.**

   Starting in 1.6 the shipped
   ``mappings/pyarchinit/pyarchinit_us_mapping.json`` declares
   ``"node_name_template": "{area}.{unita_tipo}.{us}"``. Users
   re-importing into existing graphs whose nodes were created with the
   pre-1.6 bare-US-number convention (``"101"``, ``"1002"``, ...) will
   see every row reported as an orphan in enrich mode, because
   ``_find_node_by_name`` will look for ``"A.US.101"`` and miss
   ``"101"``. To migrate, either (a) update the labels in the existing
   graph to the composite form, or (b) override the mapping with a
   local copy that removes ``node_name_template``.

Enrich-mode lookups
~~~~~~~~~~~~~~~~~~~

In auxiliary-mode imports (``existing_graph=...``), the importer
attaches PyArchInit properties to nodes it finds in the host graph by
**name**. Composite names mean that the host graph's node labels must
match the convention encoded in the template, otherwise every row will
be recorded as an orphan in ``PyArchInitImporter.orphans``. yEd-curated
graphs that will be enriched via a 1.6+ PyArchInit import should have
their US node labels written in the composite form.

JSON example (pyArchInit default mapping)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   {
     "name": "pyArchInit US Table",
     "version": "1.6.0",
     "table_settings": {
       "format_type": "sqlite",
       "table_name": "us_table",
       "node_name_template": "{area}.{unita_tipo}.{us}"
     },
     "column_mappings": {
       "sito":       { "is_filter": true, "filter_required": true },
       "area":       { "is_filter": true, "filter_required": false },
       "unita_tipo": { "is_filter": true, "filter_required": false },
       "us":         { "is_id": true, "node_type": "US" }
     }
   }

relations
---------

The ``relations`` array declares **cell-derived edges**. Each entry is
an object:

==================  =============================================================
Key                 Meaning
==================  =============================================================
``source_column``   Column whose row's stratigraphic node is the edge source.
                    Typically the ``is_id`` column.
``target_column``   Column whose cell value is the **name** of the edge target.
                    The importer resolves this name to an existing node in the
                    graph; missing targets are logged as warnings.
``edge_type``       Edge type label. See
                    :doc:`/api/s3dgraphy_edges_reference` for the full catalogue.
==================  =============================================================

Two flavours, with very different semantics:

``has_property`` edges
   ``edge_type: "has_property"`` does **not** create a cross-row edge.
   It declares that ``target_column`` is a regular property column
   that hangs off the row's main node. The importer creates one
   PropertyNode per row and links it to the row's stratigraphic node.
   See the PropertyNode discussion under
   :ref:`column_mappings <mapping-schema>` above.

Stratigraphic / topological edges
   Edge types in the set

   - ``overlies`` / ``is_overlain_by``
   - ``cuts`` / ``is_cut_by``
   - ``fills`` / ``is_filled_by``
   - ``abuts`` / ``is_abutted_by``
   - ``is_bonded_to``
   - ``is_physically_equal_to``

   are **cross-row edges**. The ``target_column`` cell value is parsed
   as a comma-separated list of row identifiers (matched against
   ``is_id`` column values across the whole table). One edge is created
   per resolved target. Edges are built in a *second pass*, after every
   stratigraphic node has been created, so forward references work.

   These topological edges are also **intermediate**: the GraphML
   exporter feeds them into
   :class:`~s3dgraphy.utils.temporal_inference.TemporalInferenceEngine`
   to derive minimal ``is_after`` chains for export. They are not
   written out verbatim.

Example:

.. code-block:: json

   "relations": [
     {
       "source_column": "us",
       "target_column": "interpretation",
       "edge_type": "has_property"
     },
     {
       "source_column": "us",
       "target_column": "overlies_us",
       "edge_type": "overlies"
     }
   ]

Validation rules
----------------

The importer enforces a small set of structural rules. These are
checked at parse time and raise ``ValueError`` (or ``FileNotFoundError``
for missing mappings) on failure.

- **Exactly one id column.** ``column_mappings`` must contain exactly
  one entry with ``is_id: true``. Zero raises an error during mapping
  validation; multiple are silently first-wins but should be avoided.

- **Known node types.** When ``node_type`` is set on an id column, it
  must resolve via
  :func:`s3dgraphy.utils.utils.get_stratigraphic_node_class`. Unknown
  types fall back to ``US`` with a warning.

- **Filter columns must exist in the table.** When ``filters=`` is
  passed, SQL backends route each key through
  ``_validate_filter_column``, which checks the column appears in
  ``column_mappings``. Unknown columns raise ``ValueError`` before any
  query is issued. Pandas backends pass the column name through
  ``df[col] == value`` directly; an unknown column raises ``KeyError``.

- **Table / sheet identifiers.** SQLite table names are matched
  against the regex ``[A-Za-z_][A-Za-z0-9_]*``. XLSX sheet names are
  not validated by the importer — pandas raises if the sheet is
  missing.

- **Backward compatibility.** Mappings without ``is_filter``,
  ``filter_required``, ``is_attribute``, or ``relations`` continue to
  work unchanged. ``filters=None`` (the default) imports every row,
  matching pre-1.6 behaviour exactly.

Worked examples
---------------

See the two annotated templates in the source tree. They are the
canonical companions to this reference page:

- `template_pyarchinit_mapping.json
  <https://github.com/zalmoxes-laran/s3dgraphy/blob/main/src/s3dgraphy/mappings/template_pyarchinit_mapping.json>`_
- `template_emdb_mapping.json
  <https://github.com/zalmoxes-laran/s3dgraphy/blob/main/src/s3dgraphy/mappings/template_emdb_mapping.json>`_

For a runnable end-to-end example, see
``tests/test_filtered_import.py`` in the repository, which builds a
SQLite fixture and exercises the full
``get_filter_columns()`` → ``get_distinct_values()`` → ``filters=`` →
``parse()`` round-trip.
