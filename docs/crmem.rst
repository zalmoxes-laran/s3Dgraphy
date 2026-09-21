.. _crmem:

CRMem — the Extended Matrix extension
=====================================

CRMem is the companion ontology of the Extended Matrix: the terms s3dgraphy
coins because the CIDOC CRM family has no way to say what the Extended Matrix
asserts. Its prefix is ``em:`` and its file is ``em.ttl``, shipped inside the
package at ``s3dgraphy/JSON_config/em.ttl``.

This page states what CRMem contains, what it deliberately does not contain, and
where its boundary with CRMinf runs. It is written for a reader who knows CIDOC
CRM and does not know the Extended Matrix.

.. contents::
   :local:
   :depth: 2


The criterion of extension
--------------------------

A class or a property enters CRMem only when it is needed to say **what the
Extended Matrix asserts about the non-observed, and on what basis**.

The virtual stratigraphic units — structural, non-structural, documentary — and
the virtual special find exist because no ontology in the family has a class for
*the entity that is not there and is argued to have been there*. A systematic
search of the official declarations of CIDOC CRM 7.1.3, CRMarchaeo 2.1.1,
CRMinf 1.2.1, CRMsci 3.2, CRMdig 5.0 and CRMgeo returns no term on "virtual",
"reconstruct" or "restoration"; the nearest, CRMsci's
``S8_Categorical_Hypothesis_Building``, names the *act* of forming a hypothesis,
not the hypothesised entity.

Two things follow from the same criterion, and both keep terms **out**.

*Descriptive scales are vocabularies, not extensions.* Taphonomic alteration
stages, masonry texture classes, functional typologies: CIDOC provides for these
explicitly, the scope note of ``E55_Type`` describing the class as "an interface
to domain specific ontologies and thesauri" and ``P2_has_type`` as the mechanism
of terminological specialisation. A term is coined in a SKOS module and attached
with ``P2_has_type``, without touching the ontology.

*A usage profile is not an extension.* The Data Transformation Chain projects
entirely onto CRMdig with a parallel PROV-O projection and introduces not one
term of its own. See :doc:`dtc-profile`.


Four properties, not seven
--------------------------

Until September 2026 the connections datamodel declared an extension prefix
``CIDOC-S3D:`` on ten edges, carrying seven distinct property names. **None of
the seven existed** — not in ``em.ttl``, not in ``hdto_extension.ttl`` — and the
prefix itself was not registered in the exporter's prefix table, so every one of
them resolved to nothing and was never emitted. They were desiderata written in a
mapping field.

A case-by-case review against the official declarations reduced seven to four.
That is a better result than seven: an extension of four terms, each with a
nameable gap behind it, is defensible; one of seven, half of which duplicate
CIDOC, is not.

The three that fell — our faults, not CIDOC's gaps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the part worth stating without softening, because it is the part a
reviewer will test. Three of the seven were not gaps in CIDOC at all. They were a
co-typing we had not done, a class we had got wrong, and a direction we had
emitted backwards — each of which looked like a missing predicate from the
inside.

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Desideratum
     - What CIDOC already offers
     - What was actually wrong
   * - ``has3DRepresentation``
     - ``crm:P138i_has_representation``
     - **A co-typing we had not done.** "3D" belongs in the ``rdf:type`` of the
       target, not in the predicate. Co-typing the model as
       ``E36_Visual_Item`` says it — ``D1`` and ``E36`` are both under ``E73``
       and are not disjoint, and the same remedy was already in use for
       ``has_visual_reference``.
   * - ``isPartOfParadataGroup``
     - ``crm:P106i_forms_part_of``
     - **A wrong class, and a reversed direction.** The group had been typed
       ``E78 Collection`` — a class CIDOC 7.1 renamed, and whose successor
       ``E78_Curated_Holding`` is a subclass of ``E24 Physical Human-Made
       Thing``, which a set of nodes is not. Re-typed, the membership predicate
       exists; emitted through the inverse, it reads the right way round.
   * - ``hasParadataDocumentation``
     - ``crm:P129i_is_subject_of``
     - **A distinction already carried elsewhere.** "The paradata container"
       versus "everything that mentions this unit" is a difference in the *type
       of the target*, not a difference of predicate.

The four that survive
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Term
     - Ceiling
     - The gap it names
   * - ``em:isInActivity``
     - **none, deliberately**
     - Classification of an arbitrary entity under an activity-shaped grouping.
       See below.
   * - ``em:contrastsWith``
     - none available
     - Mutual exclusivity between two alternative reconstructions of the same
       interval. ``P15_was_influenced_by`` has ``E7 Activity`` as its domain and
       a time branch is an ``E4 Period``, so there is no honest superproperty.
   * - ``em:belongsToAlternative``
     - ``rdfs:subPropertyOf crminf:J28i_is_referred_to_in``
     - Membership of an entity in an alternative scenario. CRMinf does cover
       this, so the extension *narrows* here rather than widening: the term
       exists to name the EM-specific reading, under a CRMinf ceiling.
   * - ``em:hasSemanticShape``
     - none available
     - The proximity geometry of a unit — *where it is held to be*, not how it
       looks. ``P156`` / ``P161`` do not reach, because since the
       proxy-as-property change the source of this relation includes a
       ``PropertyNode``, and a quale does not occupy a place.

.. note::

   **Implementation state, measured on the working tree, September 2026.**
   Of the four, ``em:isInActivity`` is declared in ``em.ttl`` *and* wired in the
   connections datamodel. ``em:contrastsWith`` is declared in ``em.ttl`` —
   as an ``owl:SymmetricProperty`` with domain and range ``em:TimeBranch`` — but
   is **not yet wired**: the ``contrasts_with`` edge still carries the dead
   ``CIDOC-S3D:incompatibleWith``. ``em:belongsToAlternative`` and
   ``em:hasSemanticShape`` are decided but **not yet declared**. Six distinct
   dead ``CIDOC-S3D:`` names remain on nine edge types, one of which
   (``has_timebranch``) is deprecated and never serialised. Connecting them is a
   string change in the datamodel plus, for two of them, an axiom in ``em.ttl``
   — the work item described in :doc:`mapping-update-procedure`.


``em:isInActivity`` in full
---------------------------

This is the first CRMem term to be implemented, and it carries the argument for
the others, so it is given in full.

.. code-block:: turtle

   em:isInActivity
       a owl:ObjectProperty ;
       rdfs:label "is in activity"@en ;
       rdfs:domain crm:E1_CRM_Entity ;
       rdfs:range  crm:E7_Activity .

**No class is introduced.** ``crm:E7_Activity`` is CIDOC core — a subclass of
``E5_Event``, declared in CRM 7.1.3 — and the EM activity group stays mapped to
it. Only the property is ours.

The scope note
~~~~~~~~~~~~~~

CIDOC can say that an actor **participated in** an event (``P11i``), that a thing
**was present at** one (``P12i``), that an object **was used for** one
(``P16i``). It cannot say that an arbitrary entity — a stratigraphic unit, a
quale, a document, an extractor, a whole paradata group — is **classified under**
an activity-shaped grouping.

That is the axis of **intention** in the Extended Matrix, orthogonal to space
(``is_in_location``) and to time (the epoch relations), and it is a curatorial
grouping rather than an event anyone attended.

Why there is no superproperty
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each candidate was checked and each fails for a stateable reason:

* ``P11i_participated_in`` requires an ``E39 Actor`` in the subject; the sources
  here are not actors.
* ``P12i_was_present_at`` would pass the type check — ``E28 Conceptual Object``
  reaches ``E77`` through ``E71``/``E70`` — but it would be **false**. A property
  node attended nothing.
* ``P9i_forms_part_of`` requires an ``E4 Period`` in the subject; none of the
  sources is a period.
* ``P129i_is_subject_of`` requires an ``E89 Propositional Object`` in the object;
  ``E7 Activity`` has ancestors ``E5``/``E4``/``E2``/``E1``/``E92`` and is not
  one.
* CRMarchaeo 2.1.1 offers no alternative: it has specific archaeological
  activities (``A9_Archaeological_Excavation``, ``A1_Excavation_Processing_Unit``,
  ``A6_Group_Declaration_Event``) but **no generic activity class**, and none of
  its 32 ``AP`` properties expresses membership in one. Verified against the
  full parsed release.

Declaring the absence of a superproperty is itself a claim, and it is made
explicitly rather than by omission.

Why the name
~~~~~~~~~~~~

The term replaces a dead desideratum called ``participatedInActivity``. It is
**not** called that, because participation is a claim this model does not make,
and the imprecision is the kind a reviewer notices at first sight.

How it is emitted
~~~~~~~~~~~~~~~~~

The edge's ``mapping.cidoc`` is left **empty on purpose** — a declaration that no
CIDOC predicate holds, not a gap — and the serializer was changed so that a
*declared-absent* edge is emitted on its extension predicate alone rather than
staying silent. Silence was correct only while there was nothing true to say. A
CRM-only reader still sees nothing on this relation, which is correct, instead of
seeing something false.


The boundary with CRMinf
------------------------

CRMinf is asked two different questions and gives two different answers, and the
distinction is the first objection a reviewer will raise.

**CRMinf covers membership.** An entity's belonging to a set of propositions is
expressed by ``J28``/``J28i``, and since 1.2 by the ``I17`` pattern with
``J30``/``J31``/``J32``. So ``em:belongsToAlternative`` hangs beneath CRMinf and
the extension narrows there rather than widening.

**CRMinf does not cover incompatibility.** Its 52 ``J`` properties speak of
premises, conclusions, adoption, provenance and meaning; none states that two
beliefs exclude one another. This is not an oversight: CRMinf models *how one
arrives at* a belief, not the logical relations *between* beliefs. That sentence
belongs in the scope note of ``em:contrastsWith``, because it is the objection
that will arrive.

**CRMinf must be declared a formal dependency of CRMem.** It is listed among the
components of the datamodels, but no CRMinf IRI is currently emitted from the
connections datamodel, so the dependency is asserted and not yet exercised.
Typing ``em:TimeBranch`` also as ``crminf:I4_Proposition_Set`` is the open
modelling decision attached to it: what is incompatible are propositions, not
periods.


Namespace
---------

The prefix is ``em:``. CRMem follows the family's naming convention — CRMarchaeo,
CRMsci, CRMdig, CRMgeo, CRMinf — and replaces two earlier names that pointed at
nothing anyone could look up: ``CIDOC-S3D`` (a prefix on ten edges, never
registered) and ``CRMs3D`` (a metadata label).

.. warning::

   The canonical namespace is being moved to ``w3id.org/extendedmatrix``. At the
   time of writing ``w3id.org/extendedmatrix/`` and ``/vocab/`` resolve, while
   ``/extendedmatrix/ontology`` does not yet serve content, and ``w3id.org/em``
   — which is what the shipped RDF currently emits — is not yet registered. The
   IRIs in delivered RDF are therefore stable as identifiers but not yet
   dereferenceable. This is a deployment item outside this repository.


A lesson worth carrying
-----------------------

One finding from the verification generalises beyond this ontology and is
recorded here because it cost real time.

**A URL containing a version number does not prove the version.** CRMgeo is the
only extension in the family without a stable release on the institutional
namespace: the only stable RDFS serialization lives on the FORTH-ICS namespace,
while what is served under a path containing the version number is a preparatory
draft that says of itself, in its own ``owl:versionInfo``, that it may be used
only as a draft — and that has removed roughly a dozen classes and properties
relative to the stable version. Read ``owl:versionInfo``, always.
