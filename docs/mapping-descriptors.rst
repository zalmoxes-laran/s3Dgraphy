.. _mapping-descriptors:

Mapping descriptors: format and statute
=======================================

A **mapping descriptor** is a JSON document that says how one external source —
an archaeological database, a spreadsheet, an XML export — becomes nodes, edges
and properties in an Extended Matrix graph. It is not a script and it is not
executed: it is read, checked against the datamodels, and applied by the
importer.

This page covers two things that are easy to conflate: the **format**, which is
one and the same everywhere, and the **statute** — what a given descriptor *is*,
who owns it, and how it is versioned and cited — which is not.

The field-by-field reference lives at :doc:`importers/mapping_schema`. What
follows is what a reader of the deliverable needs: the shape, the checks, and the
two cases.

.. contents::
   :local:
   :depth: 2


.. note::

   The word "mapping" names two different things in this library and confusing
   them is the first mistake available. **This page is about source mappings**:
   how a table becomes a graph. The *ontology* mapping — how a graph becomes RDF
   — is a different layer, declared in the datamodels and described in
   :doc:`ontology-mapping-system`. A third, much smaller thing, the *acquisition*
   mapping, turns one repository's record into a shelf descriptor and is not
   discussed here.


The shape
---------

A descriptor has four parts.

**Identity** — ``name``, ``description``, ``version``, and the free ``_``-prefixed
comment keys, which the reader ignores and a human does not.

**Source settings** — ``source_settings`` (``table_settings`` is still read, for
descriptors written before the field was generalised), carrying a
``format_type`` from ``sqlite``, ``xlsx``, ``csv``, ``xml`` and ``fmpxml``, plus
whatever that format needs to be located: a table name, a sheet name and start
row, a record path for XML.

``fmpxml`` is its own format rather than a flavour of ``xml``, and the reason is
instructive: a FileMaker export has XML syntax but table shape, with field names
in a metadata block and values matched to them **by position**. The plain XML
reader does not fail on one — it produces rows whose columns all collide, which
looks like data.

**Column mappings** — one entry per field of the source. An entry says what the
field becomes: the record's identity (``is_id``, exactly one per descriptor), its
description, a property of a given name, or a node of a given type. It may also
name the **CIDOC class** the author chose rather than an EM node type, in which
case the library resolves which EM type implements it (see
:doc:`ontology-mapping-system`).

**Relations** — one entry per relationship the source encodes, naming the source
column, the target column, and either the EM edge type or the CIDOC property it
projects to.

.. code-block:: json

   {
     "name": "Template — EMdb-style XLSX sheet",
     "version": "1.6.0",
     "source_settings": { "format_type": "xlsx", "sheet_name": "Sheet1", "start_row": 1 },
     "column_mappings": {
       "Project":     { "is_filter": true, "filter_required": true },
       "ID":          { "is_id": true, "node_type": "US" },
       "Description": { "is_description": true },
       "Material":    { "node_type": "PropertyNode", "property_name": "Material" }
     },
     "relations": [],
     "_validated_against": {
       "s3dgraphy": "1.6.0.dev18", "schema_version": "1",
       "node_datamodel": "1.6.6", "connections_datamodel": "1.6.17",
       "on": "2026-09-21"
     }
   }

Two shipped templates, one per family of source, live in
``s3dgraphy/mappings/`` and are documented inline.


What is checked, and when
-------------------------

``api.mapping_validate`` returns ``{ok, errors, warnings}``, and the split is
deliberate: errors are what makes a descriptor unusable, warnings are what makes
it surprising. An editor must be able to save work in progress.

The checks are **structural and datamodel-checked**. Structural: a descriptor
with no columns maps nothing; a format that is not one of the five; zero or more
than one identity column; a relation pointing at a column that is not mapped.
Datamodel-checked, and this is the one that matters:

   A relation whose edge type the datamodel does not allow between the two
   resolved node types is an **error here**, rather than a failure at import
   time, long after the person who authored it left the screen.

That check is what makes CIDOC-first authoring safe. Resolving a property to an
edge type says nothing about whether that edge is legal between those two
endpoints; only the connections datamodel knows, and it is asked here.

.. important::

   ``mapping_validate`` runs **before** the import, not during it. That is the
   whole point of it: it is the only moment at which the person who wrote the
   descriptor is still present and can fix it.

The warnings catch the things that are not wrong but will surprise: a CIDOC class
no EM type implements (the descriptor may still target it, and what comes out is
a CIDOC-direct node, which exists for the RDF projection only); an XML column
with no source path; and one subtle case worth naming, because the damage it does
is invisible in the output — outside a known set of stratigraphic edges, the
importer *also* turns a relation's target column into a property, so the same
fact arrives twice, once as an edge and once as a literal. Declaring
``"is_relation": true`` on that column stops it.


The stamp
---------

``api.mapping_stamp`` validates and, on success, returns a copy carrying
``_validated_against``: the s3dgraphy version, the descriptor grammar version,
both datamodel versions, and the date.

A failing descriptor comes back **unstamped**. The stamp means "this passed", and
a stamp on a broken descriptor would be worse than no stamp at all.

The stamp exists because a descriptor travels. Partner mappings live in a project
share, not in this repository, and no test here will ever see them; the stamp is
the only record of which vocabulary a descriptor was checked against that
survives the trip. ``api.mapping_stamp_check`` reads it back and warns — never
refuses — when the stamp is absent or older than the current build. Our datamodel
advancing must not become the partner's problem; a surprise at import should have
an explanation waiting.


Two cases, one format
---------------------

The format above is invariant. What changes is what a descriptor **is** — and
therefore who owns it, how it is versioned, and how it is cited.

Case (a) — an internal database with no governing standard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An excavation's own database, a site archive, a project spreadsheet: a schema
that answers to no published norm, whose columns mean what this team decided they
mean.

Here the descriptor is an **interpretive act**. Saying that a column named
``rapporto`` holds a stratigraphic relation of a certain kind, or that a free-text
field is a material rather than a description, is a reading of that archive — one
a differently-minded archaeologist could make differently, and defend.

It follows that:

* the descriptor **belongs to the dataset**, not to the library and not to the
  standard;
* it is **versioned with the dataset**, and travels with it: an archive
  re-published with corrected data may need a corrected descriptor, and the pair
  moves together;
* it is **cited as part of the dataset**, under the dataset's own identifier;
* it carries an **author**, because an interpretation has one.

Case (b) — a national or institutional standard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A cataloguing norm with a published, stable schema. Here the descriptor does not
read one archive: it reads **the norm**, and therefore holds for every dataset
that answers to it.

It follows that:

* the descriptor **belongs to the norm**, as an alignment artefact of it, not to
  any one dataset that conforms;
* it is **valid for every conforming dataset**, which is exactly what makes it
  worth the effort of getting right;
* it is **versioned with the norm** — a new edition of the standard is what
  obliges a new edition of the descriptor, not a new excavation season;
* it is **cited as the norm is cited**, with its own identifier and its own
  version, independently of any dataset it is applied to.

Why the distinction has to be written down
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Because the file looks identical in the two cases, and the consequences of
treating one as the other run in both directions.

Treat case (a) as case (b) and an interpretation acquires an authority it never
earned: one team's reading of one archive is reused on a neighbouring archive
whose columns happen to share names, and the reading travels silently.

Treat case (b) as case (a) and the work is redone per dataset, divergently, with
no place to record a correction — the alignment to a national standard is
rebuilt, slightly differently, by everyone who needs it.

Nothing in the format enforces the distinction, and nothing should: the same
grammar has to serve both. What the distinction requires is that a descriptor
**declare which it is** — in its ``description``, in the identifier it is
published under, and in what it is versioned against. That declaration is
editorial, and it is the responsibility of whoever publishes the descriptor.


API summary
-----------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Call
     - What it answers
   * - ``api.mapping_validate(m)``
     - Is this descriptor coherent, structurally and against the datamodels?
   * - ``api.mapping_stamp(m)``
     - Validate and, on success, return a copy carrying ``_validated_against``.
   * - ``api.mapping_stamp_check(m)``
     - Is this descriptor's stamp absent, or older than this build? Warnings
       only, never a refusal.
   * - ``api.mapping_normalize(m)``
     - A copy with CIDOC choices resolved to EM node types, the unimplemented
       ones marked ``cidoc_direct``.
   * - ``api.mapping_apply(m, source, mode=...)``
     - Run it: ``volatile`` (an auxiliary in the graph, outside the saved
       document until a bake) or ``bake`` (written in).

See also :doc:`data-quality` for the validators that run on the resulting graph,
and :doc:`importers/mapping_schema` for every field.
