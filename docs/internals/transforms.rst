Transforms
==========

.. versionadded:: 1.5.0

.. module:: s3dgraphy.transforms

The :mod:`s3dgraphy.transforms` package collects **graph rewriting
passes** used by the GraphML exporter (and, in some cases, by hand
before export) to produce a *minimal, formally clean* GraphML without
losing resolver fidelity.

Three modules live here, each with a focused responsibility.

compact — reverse-propagation compaction
----------------------------------------

When stratigraphic units in the same swimlane repeat the same
``has_author`` / ``has_license`` / ``has_embargo`` declaration node by
node, the workbook is redundant: every unit re-states something already
true for the whole epoch. The compact transform *lifts* those
declarations to the swimlane-level Paradata Node Group (SL_PD) and
removes the per-unit copies. The resolver behaviour is **identical
before and after** — every node still returns the same value, but via
the swimlane-level lookup instead of a local edge.

Two passes:

:func:`s3dgraphy.transforms.compact.prune_redundant_propagative_edges`
    Removes per-node ``has_author`` / ``has_license`` / ``has_embargo``
    edges (and ``has_property`` edges to temporal PropertyNodes) when
    the swimlane-level resolver returns the same value anyway. Pure
    local pruning — no new nodes are created.

:func:`s3dgraphy.transforms.compact.hoist_propagative_metadata`
    Promotes a shared per-node declaration into an SL_PD when *every*
    stratigraphic unit whose primary swimlane is Epoch E declares the
    same single target. A new SL_PD is created only if no free SL_PD
    already covers the swimlane; otherwise the existing one is reused.

:func:`s3dgraphy.transforms.compact.compact_propagative_metadata`
    Convenience orchestrator that runs ``hoist`` then ``prune``.
    Idempotent: a second call is a no-op.

Conservative invariants:

- Only AUTHOR, LICENSE, EMBARGO are promoted. Chronology
  PropertyNodes are *pruned* when redundant but never *hoisted* —
  that would require PropertyNode deduplication, out of scope.
- Strat nodes associated with multiple epochs (``survive_in_epoch``
  in addition to ``has_first_epoch``) are skipped by hoist — their
  primary swimlane is ambiguous.
- Hoist requires **every** strat unit in a swimlane to declare the
  same target. Partial overlap never hoists, to avoid silently
  crediting units that had no declaration.

Locked in by ``tests/test_compact_metadata.py`` (8 synthetic scenarios
plus idempotence of the orchestrator).

materialize_continuity — diamond materialization on export
----------------------------------------------------------

The GraphML *importer* expands continuity diamonds (BRs) into
``has_first_epoch`` + ``survive_in_epoch`` edges on the strat node
they terminate. The Blender side then works with the edge chain and
never carries the diamond in memory.

On *export*, we have to re-create the diamond, otherwise the round-trip
breaks — the importer would assume default life rules and the user's
life-bound configuration would be lost on the next reload.

:func:`s3dgraphy.transforms.materialize_continuity.materialize_continuity`
    Family-aware rules using the single source of truth from
    :mod:`s3dgraphy.classification`:

    - **REAL** strat types (``REAL_US_TYPES``) live forever by default.
      A diamond is emitted iff the actual ``last_epoch`` is **not** the
      most recent epoch in the graph (the node has a bounded life).
    - **VIRTUAL** strat types (``VIRTUAL_US_TYPES``) live only in their
      birth epoch by default. A diamond is emitted iff the graph
      contains at least one ``survive_in_epoch`` edge on the node — its
      life has been extended beyond birth, which only a diamond can
      express in GraphML.

The synthetic diamond is wired to ``last_epoch`` via a synthetic
``has_first_epoch`` edge. The exporter's position calculator
(:class:`EpochSwimlanesGenerator`) uses it to decide which swimlane row
to place the diamond in. At re-import, the diamond's y-position sits
inside ``last_epoch``'s vertical range and the importer's gate
``epoch.max_y > continuity_y_pos`` correctly bounds
``survive_in_epoch`` to the right span.

All injected content is tagged ``injected_by="materialize_continuity"``
so it is treated as auxiliary (see ``aux_tracking`` below) and removed
by the volatile save.

aux_tracking — Hybrid-C auxiliary lifecycle
-------------------------------------------

The *auxiliary layer* in EM-tools / s3dgraphy covers DosCo documents,
emdb property tables, pyArchInit SQLite, sources-list xlsx and
configurable resource-folders. Auxiliary files **attach** to existing
host nodes via a stable key ID (``D.NN`` for documents, US / USV ids
for stratigraphic units). They never create new top-level entities by
themselves: they either

#. add **enrichment child nodes and edges** (e.g. ``PropertyNode``
   children added by emdb, ``LinkNode`` children added by DosCo), or
#. update **attributes on the host node** (e.g. DosCo setting
   :attr:`DocumentNode.url`, sources-list setting
   ``author / license / embargo``).

The :mod:`s3dgraphy.transforms.aux_tracking` module provides the
bookkeeping primitives so a later exporter pass can either keep the
auxiliary layer ephemeral (**volatile save**, default) or commit it
into the GraphML (**bake**).

Two complementary tracks:

**Tagging enrichment children**
    :func:`mark_as_injected(obj, injector_id)` /
    :func:`is_injected(obj)` — tag enrichment children with
    ``attributes['injected_by']``. ``injector_id`` is free-form,
    conventionally ``"<kind>:<source-path>"`` (e.g.
    ``"DosCo:/path/to/DosCo"``).

**Recording attribute overrides**
    :func:`record_attribute_override(node, attr, injector_id, original)`
    + :func:`freeze_aux_value(node, attr)` — capture the pre-aux value
    when an auxiliary mutates a host-node attribute. Used by the
    volatile save's reversal policy.

Volatile save policy:
    :func:`apply_override_reversal_policy(graph)` walks every host node
    with ``_aux_overrides`` and, for each attribute, *reverts* to the
    original value **only if** the current value is still the aux
    value; otherwise it *drops* the override record (the user
    re-edited the attribute manually after the auxiliary applied —
    user wins).

Bake save policy:
    :func:`clear_aux_tags(graph)` drops every ``injected_by`` tag and
    every ``_aux_overrides`` record. The enrichment layer becomes
    graph-native going forward.

Side-effect summary:

==================================  ==============================================
Function                              Side effect
==================================  ==============================================
``mark_as_injected``                  Writes ``obj.attributes['injected_by']``
``record_attribute_override``         Appends to ``node.attributes['_aux_overrides']``
``freeze_aux_value``                  Updates the override's current aux value
``apply_override_reversal_policy``    Mutates node attributes, drops override entries
``strip_injected_content``            Removes nodes/edges tagged ``injected_by``
``clear_aux_tags``                    Removes the two bookkeeping keys
==================================  ==============================================

The orphan-tracking helpers (``aux_overridden_attrs``, ``is_injected``,
``push_orphan`` / ``iter_orphans`` / ``clear_orphans``) report and manage
auxiliary rows that could not be attached to a host node.

Exporter dispatch
-----------------

:class:`GraphMLExporter` and :class:`GraphMLPatcher` take a
``persist_auxiliary`` flag::

    exporter.export("out.graphml")                          # volatile (default)
    exporter.export("out.graphml", persist_auxiliary=True)  # bake

- ``False`` (volatile): apply the reversal policy and strip injected
  content before emitting. The on-disk GraphML reflects only the
  graph-native state. On the next reload the auxiliaries re-inject
  cleanly.
- ``True`` (bake): emit everything verbatim and clear the
  ``injected_by`` / ``_aux_overrides`` bookkeeping. The enrichment
  layer is promoted to graph-native.

Idempotence:
    The bake then reload roundtrip is idempotent. The volatile save
    is idempotent in the absence of user edits between iterations
    (covered by ``tests/test_aux_roundtrip_graphml.py``).

When to run the transforms
--------------------------

The standard 1.5 export pipeline is:

#. Run any project-specific edits in memory.
#. Optional: ``compact_propagative_metadata(graph)`` for a smaller,
   formally cleaner GraphML.
#. ``GraphMLExporter.export(path)`` — implicitly calls
   ``materialize_continuity`` and the volatile save policy.

The compact pass is *not* run by the exporter automatically — it is a
conscious editorial decision (you might *want* per-unit declarations
for granular tracking).

See also
--------

- :doc:`/internals/propagation` — the resolver whose behaviour the
  transforms preserve.
- :doc:`/internals/temporal` — the temporal layer that
  ``compact`` defers to (chronology PropertyNodes are pruned but
  never hoisted).
- ``CHANGELOG.md`` root entry [Unreleased] / [1.5.x] for the
  detailed test matrix.

API Reference
-------------

.. automodule:: s3dgraphy.transforms.compact
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.transforms.materialize_continuity
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.transforms.aux_tracking
   :members:
   :undoc-members:
   :show-inheritance:
