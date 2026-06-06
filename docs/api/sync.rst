Sync API — pyArchInit Bridge
============================

.. versionadded:: 1.6.0
   The ``sync`` subsystem was moved into s3dgraphy in 1.6.0 (previously
   it lived inside the pyArchInit plugin).

The :mod:`s3dgraphy.sync` package is a **backend-agnostic bridge**
between s3dgraphy graphs and `pyArchInit <https://github.com/pyarchinit/pyarchinit>`_
relational databases (SQLite **and** PostgreSQL). It lets an excavation
recorded in pyArchInit flow into the Extended Matrix workflow — projected
into a graph, edited, and written back — without leaving the database of
record.

.. note::

   The sync subsystem requires **SQLAlchemy** (and ``psycopg2`` for
   PostgreSQL). Install it with ``pip install s3dgraphy[postgres]`` or
   ``s3dgraphy[full]``. These libraries are *mocked* during the
   documentation build, so the signatures below are introspected without
   a live database driver installed.

Design principles
-----------------

* **Atomic ingestion.** A write is a single ``BEGIN``/``COMMIT``/``ROLLBACK``
  transaction; on any error the database is left untouched.
* **Idempotent.** Re-running an ingestion against the same input produces
  no further changes.
* **Non-destructive.** Only a small set of *mapped columns* round-trips;
  every other ``us_table`` column is preserved via selective ``UPDATE``.
* **Atomic file writes.** Paradata and group side-files are written with
  the ``.tmp`` + ``os.replace()`` pattern.

Architecture at a glance
------------------------

The package has four cooperating concerns plus a specialised yEd-raw
import path:

.. list-table::
   :header-rows: 1
   :widths: 26 20 54

   * - Concern
     - Entry point
     - Direction / role
   * - **Projection** (SQL → Graph)
     - :class:`~s3dgraphy.sync.graph_projector.GraphProjector`
     - Build a stratigraphic graph from a site's DB rows.
   * - **Ingestion** (Graph → SQL)
     - :class:`~s3dgraphy.sync.graph_ingestor.GraphIngestor`
     - Write a graph back to ``us_table`` atomically.
   * - **Paradata store**
     - :class:`~s3dgraphy.sync.paradata_store.ParadataStore`
     - CRUD for Author/License/Embargo/Document/… nodes that have no SQL
       column, persisted in ``paradata_<sito>.graphml``.
   * - **Group store**
     - :class:`~s3dgraphy.sync.group_store.GroupStore`
     - CRUD for user-authored ad-hoc groups in ``groups_<sito>.graphml``.
   * - **GraphML writer**
     - :func:`~s3dgraphy.sync.graphml_writer.export_graphml`
     - Project → (filter) → export a yEd GraphML with pyArchInit visuals.
   * - **yEd-raw import**
     - :func:`~s3dgraphy.sync.yed_import_pipeline.import_yed_raw`
     - Detect / classify / parse an externally-authored yEd file and
       ingest it.

Public API
----------

``from s3dgraphy.sync import …`` exposes:

* **Vocabulary** — ``VocabProviderCore``, ``EdgeType``, ``Family``,
  ``ParadataType``, ``UnitType``, ``VisualRule``, ``VocabularyVersion``
* **Database handle** — ``DbHandle``, ``DbHandleError``,
  ``PgConnectionError``, ``UnsupportedBackendError``
* **Ingestion** — ``GraphIngestor``, ``IngestResult``, ``ConflictRecord``,
  ``ConflictResolution``, ``ConflictResolver``
* **Projection** — ``GraphProjector``
* **yEd override hook** — ``YedOverrideResult``,
  ``register_yed_override_hook()``, ``clear_yed_override_hook()``
* **Errors** — ``GraphSyncError``, ``GraphIngestError``,
  ``CycleDetectedError``, ``SchemaMismatchError``,
  ``UnknownUnitaTipoError``, ``SiteMismatchError``, ``MissingEpochError``

Worked examples
---------------

**Project a site into a graph (SQL → Graph)**

.. code-block:: python

   from s3dgraphy.sync import GraphProjector

   projector = GraphProjector()
   graph = projector.populate_graph(
       db_path="excavation.sqlite",   # path | DbHandle | SQLAlchemy URL
       sito="Pompei",
       include_paradata=True,
   )

**Ingest a graph back into the database (Graph → SQL)**

.. code-block:: python

   from s3dgraphy.sync import GraphIngestor

   ingestor = GraphIngestor()
   result = ingestor.populate_list(
       graph=graph,                   # a Graph, or a path to a .graphml
       db_path="excavation.sqlite",
       sito="Pompei",
       dry_run=True,                  # roll back at the end (preview)
       create_missing_epochs=True,
   )
   print(result.inserted, result.updated, result.conflicts)

**Export a yEd GraphML straight from the database**

.. code-block:: python

   from s3dgraphy.sync import graphml_writer

   res = graphml_writer.export_graphml(
       db_path="excavation.sqlite",
       mapping="pyarchinit_us_mapping",
       output_path="pompei.graphml",
       site_filter="Pompei",
       language="it",
   )
   print(res.node_count, res.edge_count, res.tred_removed_edges)

API Reference
=============

Vocabulary
----------

.. automodule:: s3dgraphy.sync.vocab_types
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.vocab_provider_core
   :members:
   :undoc-members:
   :show-inheritance:

Database handle
---------------

.. automodule:: s3dgraphy.sync._db_handle
   :members:
   :undoc-members:
   :show-inheritance:

Projection (SQL → Graph)
------------------------

.. automodule:: s3dgraphy.sync.graph_projector
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.group_projector
   :members:
   :undoc-members:
   :show-inheritance:

Ingestion (Graph → SQL)
-----------------------

.. automodule:: s3dgraphy.sync.graph_ingestor
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.ingest_result
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.conflict_resolver
   :members:
   :undoc-members:
   :show-inheritance:

Site-scoped stores
------------------

.. automodule:: s3dgraphy.sync.paradata_store
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.group_store
   :members:
   :undoc-members:
   :show-inheritance:

GraphML writer
--------------

.. automodule:: s3dgraphy.sync.graphml_writer
   :members:
   :undoc-members:
   :show-inheritance:

yEd-raw import pipeline
-----------------------

The yEd-raw pipeline handles GraphML authored *directly* in yEd (no
pyArchInit data keys). It detects the flavour, classifies leaf nodes by
label prefix, extracts period swimlanes and folder hierarchy, resolves
folder-touching edges through a configurable policy, and writes the
result atomically.

.. automodule:: s3dgraphy.sync.yed_detector
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.yed_classifier
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.yed_table_parser
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.yed_group_walker
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.yed_rapporti_policy
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.yed_import_pipeline
   :members:
   :undoc-members:
   :show-inheritance:

Relation mapping & utilities
----------------------------

.. automodule:: s3dgraphy.sync.rapporti
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.edge_registry
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.uuid7
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.sync.pyarchinit_pg_importer
   :members:
   :undoc-members:
   :show-inheritance:
