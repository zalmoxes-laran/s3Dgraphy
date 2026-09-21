.. _data-quality:

Data quality, level one: checking a user's data
===============================================

There are two distinct kinds of quality assurance in this library, and the
documentation used not to distinguish them. Confusing them is easy, because both
are called "validation" and both produce a list of problems.

.. list-table::
   :header-rows: 1
   :widths: 14 43 43

   * -
     - **Level one — this page**
     - **Level two —** :doc:`development`
   * - Question
     - *Is this graph, this descriptor, sound?*
     - *Do the checks at level one still work?*
   * - Subject
     - The data of whoever is using the library
     - The library itself
   * - Run by
     - The user, or the application on their behalf, at any time
     - Developers and CI, on every change
   * - Called
     - ``api.validate``, ``api.mapping_validate``, ``api.graph_warnings``,
       ``api.connection_report``, ``api.diagnose_generic_connections``,
       ``api.resolve_edge_type``
     - ``pytest``
   * - Output
     - A report about a document
     - A pass or a failure about a build

A validator that has silently stopped working produces clean reports about dirty
data, which is worse than no validator at all. That is what level two exists to
prevent, and it is why the two are documented apart.

.. contents::
   :local:
   :depth: 2


Before the import: ``mapping_validate``
---------------------------------------

:func:`s3dgraphy.api.mapping_validate` checks a mapping descriptor — structurally,
and against the datamodels — and returns ``{ok, errors, warnings}``.

.. important::

   It runs **before** the import, not during it. That is its whole reason for
   existing. A relation the datamodel does not allow between two resolved node
   types is an error *here*, while the person who authored the descriptor is
   still at the screen, rather than a failure at import time, long after they
   left.

Errors are what makes a descriptor unusable; warnings are what makes it
surprising. The split exists so that an editor can save work in progress. The
full account, including the stamp a validated descriptor carries, is in
:doc:`mapping-descriptors`.


After the import: what is in this graph
---------------------------------------

``api.validate`` — the structural floor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A read-only structural check of a graph, returning
``{ok, stats, warnings, issues}``. It surfaces the graph's own accumulated
warnings and adds a cheap scan for dangling edges — an edge whose source or
target is not in the graph. Minimal, extensible, and with no side effects.

This is the floor, not the ceiling: ``ok`` here means the graph is structurally
coherent, not that its archaeology is right.

``api.graph_warnings`` — warnings as records
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The same warnings, but as ``{kind, node_id, message}`` records rather than
strings, so that an interface can act on them: ``node_id`` names the element to
reveal when the reader clicks the warning, and edge records also carry
``edge_id``, ``target_id`` and the ``candidates`` the datamodel would allow.

One design decision is worth stating because it explains the ``recompute``
argument. **Warnings are a function of the graph's state, not a log of how it was
loaded**, so the em.json format carries no warnings section and they are
recomputed at every load. Without that, a document opened from disk would be
silent about exactly the problems the GraphML path shouted about: the same graph,
two different stories. Pass ``recompute=True`` after mutating the graph and an
interface can refresh its warnings whenever it likes, with no import round trip.


Connection resolution: three read-only questions
------------------------------------------------

These three answer questions about the *typing of relations*, which is where most
of the real damage hides, and they are the ones most easily misunderstood as
repairs. They are not.

.. important::

   ``connection_report`` and ``diagnose_generic_connections`` are
   **non-destructive**. They compute what a stricter resolver *would* decide.
   Nothing is re-typed, no graph is mutated, and edge creation keeps behaving
   exactly as it does today.

The background, in one paragraph. The connections datamodel lists **class** names
as the permitted endpoints of an edge, while the runtime map of node types is
keyed by **node type**. The core's own connection check resolves the former
through the latter, so the lookup misses, falls back, and lets almost any
endpoint through — it is permissive by construction. A correct resolution exists
as a set of pure functions, and these three ops expose it *as measurement*, so
that the size of the problem can be known before anyone decides to make the core
strict.

``api.connection_report`` — what a strict resolver would decide
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Returns ``{total_edges, resolved, would_degrade, already_generic,
unknown_edge_type, dangling, delta, cases}``.

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Key
     - Meaning
   * - ``resolved``
     - The declared edge type is allowed between these endpoints: it survives.
   * - ``would_degrade``
     - Not allowed: under a strict resolver it would become
       ``generic_connection``.
   * - ``delta``
     - **The blast radius.** Edges that would degrade *and* are currently
       accepted by the permissive core — that is, exactly what would change if
       the core went strict.
   * - ``author_warning``
     - An endpoint has no EM type at all. The node is the problem, not the
       relation, so these are counted apart and cannot bury a real edge error.
   * - ``already_generic``
     - Edges already carrying ``generic_connection``.
   * - ``unknown_edge_type``
     - An edge type absent from the connections datamodel.
   * - ``dangling``
     - An endpoint is missing from the graph. Not judged.
   * - ``cases``
     - One row per distinct *(edge type, source type, target type)* that would
       degrade, with a count, whether it is currently accepted, one example edge
       id and the full lists of edge, source and target ids — so the offending
       edges can actually be found and fixed. Sorted by count.

``delta`` is the number to read first: it is the answer to "what does it cost us
to be correct".

``api.diagnose_generic_connections`` — how much is recoverable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The mirror question. Of the edges **already** typed ``generic_connection``, what
type would their endpoints allow? Returns ``{total_generic, recoverable,
ambiguous, no_candidate, dangling, cases}``:

* ``recoverable`` — exactly one edge type fits, so the lost type is unambiguously
  reconstructible;
* ``ambiguous`` — several fit; the endpoints alone cannot decide;
* ``no_candidate`` — none fits: the edge is genuinely outside the language.

``cases`` groups by *(source type, target type)* with the candidate list and an
example. Diagnostic only.

``api.resolve_edge_type`` — the single-edge question
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A pure function: the type an edge *would* carry under correct resolution — the
declared type when the datamodel allows it, ``generic_connection`` otherwise. It
touches no graph and changes nothing about how edges are actually created. It is
what the two reports above are built from, exposed on its own so that an
interface can ask about one relation a user is drawing.


A typical sequence
------------------

.. code-block:: python

   from s3dgraphy import api

   # 1. before anything: is the descriptor sound?
   report = api.mapping_validate(descriptor)
   if not report["ok"]:
       raise SystemExit("\n".join(report["errors"]))

   # 2. import, then the structural floor
   graph, warnings = api.load_emjson_file("site.em.json")
   print(api.validate(graph))

   # 3. warnings an interface can act on
   for record in api.graph_warnings(graph):
       print(record["kind"], record["node_id"], record["message"])

   # 4. how much relational typing is wrong, and how much is recoverable
   conn = api.connection_report(graph, max_cases=20,
                                diagnose_generic_edges=True)
   print("blast radius:", conn["delta"])
   print("recoverable:", conn["generic_diagnosis"]["recoverable"])

Nothing in this sequence writes to the graph.


What guarantees these
---------------------

Every function on this page is exercised by the regression suite — in particular
``tests/test_connection_resolver.py``, ``tests/test_api_surface.py``,
``tests/test_mapping_authoring.py``, ``tests/test_recompute_warnings.py`` and
``tests/test_stamp.py``. What that suite is, how to run it, and what its current
state actually is: :doc:`development`.
