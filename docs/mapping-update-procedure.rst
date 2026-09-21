.. _mapping-update-procedure:

Updating the mapping: a proposed procedure
==========================================

.. admonition:: Status of this page
   :class: important

   **This is a proposal, not a record of established practice.** It is written
   down at the point where the project has enough experience to say what the
   procedure should be, and before it has been followed enough times to call it
   custom. Steps 4, 8 and 9 are not yet automated and are performed by hand;
   where a step describes something the repository does not yet enforce, it says
   so.

   It is published rather than kept internal because a mapping that partners
   depend on needs a visible change procedure more than it needs a tidy one.

.. contents::
   :local:
   :depth: 1


Why a procedure at all
----------------------

The September 2026 verification pass found seven IRIs, cited in 429 places, that
did not exist in any official release. They had been introduced by ordinary,
careful changes. The reason they survived is the property that makes this whole
class of fault dangerous:

   An IRI that does not exist raises no error anywhere. It serialises, it round
   trips, it looks exactly like a good one, and it produces a triple no reasoner
   can place and no query can reach.

From which the operative lesson: **moving the reference version of an ontology
cannot be an edit to a metadata line.** It has to be a procedure that re-validates
every identifier. What follows is that procedure, generalised to any change to
the alignment.


The steward
-----------

The procedure names one role. The **mapping steward** is a single person — not a
committee, and not "the team" — who is answerable for two things and no others:

* **the register decision** (step 3): whether a given change is a correction, a
  vocabulary term, or an extension. This is the decision that cannot be made
  correctly by whoever happens to be writing the code, because it is a judgement
  about what the model commits to, not about what makes the tests pass.
* **the sign-off** (step 9): that the change has been propagated, and that what
  the documentation now says is what the code now does.

The steward is deliberately **not** a gatekeeper on the measuring, the editing or
the testing. Anyone may open a case, measure it, propose a patch and run the
suite. Concentrating approval on the two judgement steps is what keeps the role
answerable rather than merely busy.


The nine steps
--------------

1. Open the case, and say which of three things it is
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

State in one sentence what is wrong or missing, and classify it:

* **a projection that does not hold** — wrong predicate, wrong domain or range,
  reversed direction;
* **a term the standard has moved** — renamed, deprecated, migrated to another
  extension;
* **something the family cannot say** — a candidate for coining.

The third is the expensive one and the most often claimed. Three of the seven
extension terms reviewed in 2026 were claimed as gaps in CIDOC and were in fact a
co-typing we had not done, a class we had got wrong, and a direction we were
emitting backwards. **Assume category three is category one until the measuring
says otherwise.**

2. Measure the current state on the code, never on the documentation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the resolution the exporter runs and look at what actually comes out. A
mapping field is a claim; what the exporter emits is a fact, and the two have
been known to disagree for two minor versions at a stretch.

Record the measurement in the case. If the documentation and the code disagree,
the code is right about the facts — but **the divergence is reported, not
silently corrected**: two times in three it is a bug nobody had noticed.

3. Decide the register — *steward*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Four registers, in increasing order of commitment. Choose the lowest that works.

.. list-table::
   :header-rows: 1
   :widths: 22 44 34

   * - Register
     - Use when
     - Cost
   * - **Mapping**
     - An official term exists and says it. Most changes are this.
     - A JSON edit.
   * - **Vocabulary**
     - It is a descriptive scale — alteration stages, texture classes,
       functional typologies. CIDOC provides for this through ``E55 Type`` and
       ``P2_has_type``.
     - A SKOS entry. **Not** an ontology change.
   * - **Extension**
     - Nothing in the family can say it, and the gap can be *named* — not merely
       felt.
     - A JSON edit **plus** an axiom, plus a scope note, plus a permanent
       obligation.
   * - **Prefix**
     - A whole namespace is being introduced.
     - The one case that needs a **code** change: an unregistered prefix
       resolves to nothing, silently. See :doc:`ontology-mapping-system`.

The test for the extension register is whether the gap can be stated as a
sentence about what CIDOC *can* say and what it cannot. If that sentence cannot
be written, the term is not ready to be coined.

4. Verify against the official releases
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rebuild the term index from the official RDFS/OWL serializations and check every
IRI the datamodels cite — not only the ones being touched.

.. code-block:: bash

   python .claude/wip/verify_cidoc_iris.py .

Two rules learned the hard way, both of which belong at this step:

* **A URL containing a version number does not prove the version.** Read
  ``owl:versionInfo`` in the document itself. One extension in the family serves
  a preparatory draft under a versioned path, and that draft has fewer terms than
  the stable release it appears to be.
* **Check the whole citation set, not the diff.** The seven dead IRIs were not
  introduced together; they accumulated.

.. note::

   **Not yet automated.** This verifier is run by hand and lives outside the
   package, in a working directory. Wiring it into the test suite is the single
   highest-value automation this procedure is missing, because it is the only
   step that catches the silent fault class.

5. Change the data (and, for a coined term, the axiom)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Edit the datamodel entry. Where the change is a correction, leave the previous
reading in the entry's comment field rather than deleting it: the record of what
was wrong is what stops it being reintroduced.

Where a term is coined, the axiom in ``em.ttl`` carries, without exception:

* ``rdfs:domain`` and ``rdfs:range``;
* a superproperty **or the explicit statement that there is none**, with the
  candidates considered and why each fails. An absent superproperty asserted by
  silence is indistinguishable from one nobody looked for;
* a scope note naming the gap — what the family *can* say and what it cannot;
* the name, chosen to claim no more than the model asserts.

6. Re-run, and compare like with like
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the suite before and after, on the same environment, and compare the **sets**
of failures rather than the counts. The suite carries a standing baseline of
known failures (see :doc:`development`); a count that stays the same while the
set changes is a regression hidden by an accidental repair.

Run the RDF round trip over a real fixture and count what survives the
projection. The measurement that closed ``em:isInActivity`` was that 76 of 76
edges in one fixture, and 2 of 2 in another, projected *and returned*, where
previously none had.

7. Version the datamodel, and say why in the datamodel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bump the version of every datamodel touched, and record the reason in that
datamodel's own ``description`` field, dated and attributed. The datamodels
already carry their change history inline, and that is the right place for it:
the file that travels is the file that should explain itself.

State explicitly what was **not** done and why. The most useful sentences in that
history are the ones naming decisions deferred.

8. Update the documentation and regenerate the tables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Regenerate :doc:`generated-report`, which derives every count, version and
  per-ontology total from the datamodels. **No count is written by hand.**
* Update the supported-versions table at
  :ref:`development-supported-versions` if a reference version moved.
* Update the affected prose page — :doc:`ontology-mapping-system`,
  :doc:`crmem`, :doc:`dtc-profile`, :doc:`mapping-descriptors` — in the same
  commit as the change, not afterwards.
* A page that can no longer be verified gets a marker, not a deletion.

Pages are not moved or renamed; if one must be, the old address keeps a redirect.

9. Propagate, notify, sign off — *steward*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A datamodel change is not finished when it is committed here. It is finished when
the people reading the old one know.

.. code-block:: bash

   python -m s3dgraphy.tools.sync_node_datamodel        # regenerate the registry
   python -m s3dgraphy.tools.consumer_drift             # who is behind
   python -m s3dgraphy.tools.wheel_drift                # is a bundled copy stale

The distinction these tools keep is deliberate: a consumer *this project owns*
being behind is a task, and its check fails the build; a consumer *somebody else*
owns being behind is **news to send**, not a build break — failing our own build
over a third party's vendored copy would be theatre.

Partner mapping descriptors live outside this repository and no test here will
ever see them. They carry a validation stamp naming the datamodel versions they
were last checked against, and a stale stamp produces a warning and never a
refusal: our datamodel advancing must not become the partner's problem. Where a
change would alter what an existing descriptor means, the notification is a
message to a person, not a warning in a log.

The steward signs off that the propagation happened and that the documentation
now describes the code.


Summary
-------

.. list-table::
   :header-rows: 1
   :widths: 6 40 24 30

   * - #
     - Step
     - Who
     - Automated?
   * - 1
     - Open the case and classify it
     - anyone
     - no (judgement)
   * - 2
     - Measure on the code
     - anyone
     - partly
   * - 3
     - Decide the register
     - **steward**
     - no (judgement)
   * - 4
     - Verify against the official releases
     - anyone
     - script, **not wired in**
   * - 5
     - Change the data, and the axiom if any
     - anyone
     - no
   * - 6
     - Re-run and compare sets
     - anyone
     - yes (``pytest``)
   * - 7
     - Version the datamodel, record the reason
     - anyone
     - no
   * - 8
     - Regenerate tables, update the pages
     - anyone
     - generator, run by hand
   * - 9
     - Propagate, notify, sign off
     - **steward**
     - drift tools, run by hand
