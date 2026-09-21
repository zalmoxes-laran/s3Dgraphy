.. _ontology-mapping-system:

The ontology mapping system
===========================

This page describes how s3dgraphy declares the projection of its property graph
onto CIDOC CRM and its extensions, and who reads those declarations. It is
written for a reader who does not know the Extended Matrix: everything specific
to EM is introduced where it is first needed.

The short version is one sentence. **Adding or correcting an alignment is a
change to data plus, where a new term is coined, an axiom in an ontology file —
it is not a change to software.** The rest of this page is the evidence for that
sentence, and the one exception to it.

.. contents::
   :local:
   :depth: 2


Two forms of the same knowledge
-------------------------------

s3dgraphy holds archaeological stratigraphy and the reasoning built on it as a
**typed property graph**: nodes of declared types, edges of declared types, each
carrying attributes. That is the form in which the knowledge is authored — drawn
in a graph editor, queried, corrected, argued over.

RDF is the form in which it is **delivered**. The two forms do not coincide and
are not meant to. An editor needs oriented edges and connection constraints so
that it can refuse an illegal relation while someone is drawing it; a triple
store needs triples a reasoner can use without knowing anything about the
Extended Matrix.

The bridge between the two is not code. It is a declaration carried by every node
type and every edge type, in the datamodels.


The three datamodels are the single source of truth
---------------------------------------------------

Three JSON documents in ``s3dgraphy/JSON_config/`` carry the whole alignment:

``s3Dgraphy_node_datamodel.json``
   Every node type, grouped into families (stratigraphic, temporal, group,
   paradata, reference, visualization, rights, container, HDT-O, DTC,
   georeferencing, narrative, fallback). Each entry declares the CIDOC class it
   projects to, and — where the Extended Matrix coins a class of its own — the
   extension IRI and its superclasses.

``s3Dgraphy_connections_datamodel.json``
   Every edge type: the CIDOC predicate, an optional extension predicate, the
   direction in which the triple is emitted, and the node classes admitted at
   each end.

``em_qualia_types.json``
   The catalogue of property types (*qualia*) an EM ``PropertyNode`` can carry,
   each with the CIDOC class that a property of that kind resolves to.

The RDF exporter (:mod:`s3dgraphy.exporter.rdf_exporter`) reads all three at
construction time. Its own docstring states the contract, and the code keeps it:
**no class, edge or qualia type is hard-coded in the exporter.** A node type the
exporter has never heard of projects correctly, provided the datamodel says how.

How a node type declares its projection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   "USD": {
     "mapping":      { "cidoc": "A8 Stratigraphic Unit" },
     "em_extension": { "uri": "em:DocumentaryVirtualSU",
                       "subclass_of": ["em:VirtualSU"] }
   }

``em_extension.uri`` is preferred and ``mapping.cidoc`` is the fallback; every
entry in ``em_extension.subclass_of`` is emitted as an additional ``rdf:type``,
so a consumer that reads only CIDOC still sees a class it knows, while a consumer
that reads the EM ontology sees the specific one.

How an edge type declares its projection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   "has_property": {
     "allowed_connections": { "source": [...], "target": ["PropertyNode"] },
     "mapping": { "cidoc":             "P43_has_dimension",
                  "extension_mapping": "em:hasQualia",
                  "extension_name":    "EM",
                  "rdf_subject":       "target" }
   }

``rdf_subject`` exists because a graph edge and an RDF triple do not always run
the same way round. An edge drawn from A to B whose correct predicate reads
"B ... A" is declared with ``rdf_subject: "target"`` rather than reversed in the
graph, where the drawing convention is what archaeologists expect. Where CIDOC
declares an inverse property, the inverse is preferred to ``rdf_subject``,
because it is one indirection less.

An edge may declare an empty ``cidoc`` deliberately. That is not an omission: it
is the statement that the CIDOC family has no predicate for this relation, and
the edge is then emitted on its extension predicate alone. ``is_in_activity`` is
the worked example — see :doc:`crmem`.

How a property resolves its class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An EM ``PropertyNode`` is a structural shell: what CIDOC class it becomes depends
on *which* property it expresses. A height is an ``E54 Dimension``, a colour an
``E55 Type``, a material an ``E57 Material``, an interpretive judgement a
``crminf:I4 Proposition Set``. The exporter resolves this at serialization time
from ``em_qualia_types.json``, not from a branch in the code, which is why a new
qualia type is a JSON entry.


The registries built from the official releases
-----------------------------------------------

An IRI that does not exist raises no error anywhere. It serialises, it
round-trips, it looks exactly like a good one — and it produces a triple no
reasoner can place and no query can reach. It is a silent fault, and for that
reason a dangerous one.

The only way to know whether a cited term exists is to ask the standard. The
repository therefore builds a **term index from the official releases** —
downloading the RDFS/OWL serializations and parsing them — and checks every IRI
the datamodels cite against it. On the current working tree:

.. code-block:: text

   official terms parsed: crm=425, crmarchaeo=70, crmdig=58,
                          crmgeo=76, crminf=67, crmsci=106
   distinct IRIs cited by the repo: 85 (in 431 citations)
   NOT DECLARED IN ANY OFFICIAL RELEASE: 0

A second generated registry, ``node_registry.generated.json``, is derived from
the Python node classes rather than from the ontologies: it is the flat class
hierarchy (``parent`` / ``node_type`` / ``description``) that non-Python
consumers read for ancestry checks and palette construction. It is produced by
``python -m s3dgraphy.tools.sync_node_datamodel`` and guarded by a
``--check`` mode that the test suite runs, so it cannot drift from the classes.

The two registries answer different questions and neither replaces the other: one
asks *does the term exist in the standard*, the other asks *does the shipped
class hierarchy match the code*.

.. warning::

   The IRI verifier currently lives at ``.claude/wip/verify_cidoc_iris.py`` and
   is **not** invoked by the test suite or by CI: it is run by hand. Until it is
   wired in, "zero undeclared IRIs" is a measurement of a moment and not an
   invariant the build enforces. See :doc:`mapping-update-procedure`, step 4.

Counts, versions and per-ontology alignment totals are not written by hand
anywhere in this documentation. They are generated — see :doc:`generated-report`.


The authoring surface
---------------------

Alignment declarations are not only read by the exporter. They are also read
*backwards*, by the surface a mapping editor is built on
(:mod:`s3dgraphy.mappings.authoring`), so that someone mapping an external
database chooses a **CIDOC class** — the vocabulary the ontology table speaks —
and the library resolves which EM node type implements it.

The bridge in that direction is the same ``mapping.cidoc`` field, read in
reverse. No second table exists, and nothing is translated by hand. Two
consequences follow, and both are declared rather than hidden:

* the inverse is **many-to-one**. ``A8 Stratigraphic Unit`` is the CIDOC class of
  several EM types, so the index returns candidates in datamodel order and a
  mapping that wants one of them says which;
* some CIDOC classes have **no EM type at all**. A mapping may still target them;
  what comes out is a generic node that exists for the RDF projection. These are
  marked ``cidoc_direct`` — a declared half-measure, not a silent one.

The surface answers four questions and performs one act — what is in this source,
what may it map to, how may two things connect, is this mapping coherent, and
then: run it. See :doc:`mapping-descriptors`.


What this buys, and the one exception
-------------------------------------

Because the alignment lives in data:

* correcting a wrong predicate is a JSON edit;
* following an ontology release that renamed a term is a JSON edit;
* adding a node type's projection is a JSON edit;
* coining a new EM term is a JSON edit **plus** an axiom in ``em.ttl`` — domain,
  range, superproperty or the explicit absence of one, and a scope note saying
  what gap it names;
* none of the above requires touching the exporter, the importers, or any
  consumer that reads the datamodels.

The exception is worth stating plainly, because it is exactly how the previous
generation of extension declarations failed. The exporter resolves a prefixed
term through a **prefix table** (``PREFIX_MAP`` in the RDF exporter). A datamodel
may declare an extension predicate under a prefix that table does not contain;
nothing refuses it, and the term simply resolves to nothing and is never emitted.
That is what happened to the ``CIDOC-S3D:`` declarations documented in
:doc:`crmem`: they sat in the datamodels for two minor versions, looking like
mappings, resolving to ``None`` every time.

**Registering a new prefix is therefore the one alignment change that does
require a code change**, and it is a single line. The procedure in
:doc:`mapping-update-procedure` puts it at step 3 for that reason.


Where to go next
----------------

* :doc:`crmem` — the Extended Matrix extension: what it contains, and what it
  deliberately does not.
* :doc:`dtc-profile` — a usage profile of CRMdig that introduces no terms at all.
* :doc:`mapping-descriptors` — the descriptor that maps an external source into
  the graph, and the two statutes such a descriptor can have.
* :doc:`data-quality` — the validators that run on a user's own data.
* :doc:`mapping-update-procedure` — the proposed procedure for changing any of
  the above.
* :doc:`generated-report` — the counts and versions, derived from the
  datamodels at build time.
