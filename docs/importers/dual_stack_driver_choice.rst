.. _dual-stack-driver-choice:

Driver Stack: stdlib (Read) + SQLAlchemy (Write)
================================================

.. versionadded:: 1.6
   PostgreSQL backend for :class:`~s3dgraphy.importer.pyarchinit_importer.PyArchInitImporter`
   (issue #9) and the new :mod:`s3dgraphy.sync` write pipeline (issue
   #10) land together. They use **different** database drivers — by
   design, not in transition.

s3dgraphy 1.6 ships two intentionally separate database stacks:

.. list-table::
   :header-rows: 1
   :widths: 24 38 38

   * - Path
     - Module
     - Driver
   * - **Read** (importer)
     - :mod:`s3dgraphy.importer.pyarchinit_importer`
     - Stdlib (``sqlite3`` + ``psycopg2``) via a small ``_qmark()`` dialect helper
   * - **Write** (sync / ingest)
     - :mod:`s3dgraphy.sync`
     - SQLAlchemy 2.x

This page documents **why** the split exists so that a future
contributor reading the code does not mistake it for legacy in
transition.

Why stdlib for the read path
----------------------------

The :class:`~s3dgraphy.importer.pyarchinit_importer.PyArchInitImporter`
issues a single parameterised ``SELECT`` (with an optional ``WHERE``
clause from the 1.6 ``filters=`` kwarg) per import. The dialect surface
is tiny:

- one placeholder character that differs between backends (``?`` for
  SQLite, ``%s`` for PostgreSQL) — handled by a single ``_qmark()``
  helper;
- one connection call dispatched on the URL scheme — ``sqlite3.connect``
  vs ``psycopg2.connect``;
- no transactions, no atomic updates, no schema management.

Pulling SQLAlchemy into this path would bind a heavy dependency to a
codepath that does not need it. EM-tools wheels in particular embed
s3dgraphy and want the SQLite-only consumer to stay free of any
extra runtime install.

The opt-in PostgreSQL support is therefore behind the ``[postgres]``
extra:

.. code-block:: bash

   pip install s3dgraphy[postgres]

If ``psycopg2`` is missing at the moment a PostgreSQL connection URL
is first opened, the importer raises a friendly ``ImportError``
pointing at this extra. SQLite consumers never pay the import cost.

Why SQLAlchemy for the write path
---------------------------------

:mod:`s3dgraphy.sync` (``GraphIngestor``, ``ConflictResolver``, the
``populate_list`` pipeline) writes back to the PyArchInit database. It
needs:

- transactional semantics (atomic ingest with rollback on conflict);
- per-row optimistic concurrency via ``node_uuid`` checks;
- portable DDL when applying the optional group-folder side-tables;
- a single code path that works for both SQLite and PostgreSQL without
  hand-rolling dialect logic for every statement.

These are exactly what SQLAlchemy gives for free. Rewriting them on top
of stdlib drivers would duplicate the transaction + dialect machinery
that already exists in SQLAlchemy, with no upside.

The write stack is opt-in behind the ``[sync]`` extra:

.. code-block:: bash

   pip install s3dgraphy[sync]            # SQLAlchemy 2.x
   pip install s3dgraphy[sync,postgres]   # + psycopg2-binary

Consumers that only import the read path do not need ``[sync]``.

Summary
-------

The two stacks compose: an importer using ``connection_url=`` (issue #9)
and ``GraphIngestor.populate_list()`` (issue #10) can run against the
same PostgreSQL fixture in the same process. The
``tests/sync/test_round_trip_pg.py`` test pins this composition.

The split is the right granularity of dependency for 1.6 and is not
expected to change. If a future caller needs SQLAlchemy on the read
side (e.g., for reflection or relationship traversal), it should be
added as an additional importer, not as a replacement of the stdlib
path that ``EM-tools`` and other lean consumers rely on.
