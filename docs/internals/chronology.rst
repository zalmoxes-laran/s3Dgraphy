Chronology
==========

.. versionadded:: 0.1.32
.. versionchanged:: 1.5.0
   Per-claim attribution on paradox warnings; auto-cycle detection;
   resolver-backed swimlane lookup.

Chronology in s3dgraphy is **emergent**: there is no single
``chronology`` table. The library assembles a temporal picture from
five layered sources, each contributing what it knows, and the
:meth:`Graph.calculate_chronology` entry point ties them together.

The five sources
----------------

#. **EpochNode header** — ``start_time`` / ``end_time`` declared in the
   yEd swimlane title. The cheapest, coarsest constraint.

#. **EpochNode swimlane PropertyNode** — a PropertyNode named
   ``absolute_time_start`` / ``absolute_time_end`` attached to the
   epoch (typically inside an SL_PD free paradata group, auto-edged by
   the importer). **Overrides** the header when both are present;
   import-time check emits a ``[chronology mismatch]`` warning.

#. **Unit-level PropertyNode seeds** — PropertyNodes attached to a
   stratigraphic unit via ``has_property``, named
   ``absolute_time_start`` / ``absolute_time_end``. These are the
   TPQ/TAQ seeds that bypass the swimlane.

#. **Topological relations** —
   ``cuts`` / ``overlies`` / ``fills`` edges. Mapped to temporal
   direction by the
   :class:`s3dgraphy.temporal.inference_engine.TemporalInferenceEngine`
   (see :doc:`/internals/temporal`).

#. **Direct ``is_after`` / ``is_before`` edges** — explicit user
   declaration of temporal order, absorbed into the DAG without
   re-derivation.

Epochs as their own swimlane
----------------------------

Since 1.5 (DP-32 Priority 4) passing an :class:`EpochNode` directly to
the resolver yields the swimlane-level value instead of ``None``. The
swimlane iterator in :mod:`s3dgraphy.resolvers.property_resolver`
short-circuits to ``[epoch]`` when the input is itself an EpochNode,
so chronology, author, license and embargo are all reachable on epochs
without a dedicated code path in every consumer. The Epoch Manager
UI's ``epoch.start_time``/``end_time`` workaround is no longer needed.

calculate_chronology pipeline
-----------------------------

Pseudo-code::

    def calculate_chronology(graph):
        # Layer A — seed
        for node in graph.stratigraphic_nodes():
            node.CALCUL_START_T = resolve(node, ABSOLUTE_TIME_START_RULE)
            node.CALCUL_END_T   = resolve(node, ABSOLUTE_TIME_END_RULE)

        # Detect cycles first — paradox warnings get clean attribution
        for loop in detect_stratigraphic_cycles(graph):
            graph.warnings.append(f"[stratigraphic cycle] {loop}")

        # Layer B — TPQ/TAQ closure
        _propagate_tpq_taq(graph.stratigraphic_nodes())

        # Layer C — paradox surfacing
        for node in graph.stratigraphic_nodes():
            if node.CALCUL_END_T < node.CALCUL_START_T:
                attr = attribute_temporal_claim(graph, node, "absolute_time_start")
                graph.warnings.append(
                    f"[chronology paradox] {node.name} "
                    f"[attributed to {attr.display} ({attr.kind})]")

Each step is documented in detail in :doc:`/internals/temporal` (the
inference engine) and :doc:`/api/diagnostics` (cycle detection and
attribution).

Stored on the node
~~~~~~~~~~~~~~~~~~

After ``calculate_chronology`` runs:

- ``node.attributes["CALCUL_START_T"]`` — earliest plausible year
- ``node.attributes["CALCUL_END_T"]`` — latest plausible year
- ``node.attributes["CALCUL_START_T_source"]`` — one of ``"node"`` /
  ``"swimlane"`` / ``"graph"`` / ``"propagated"``

The ``_source`` tag lets em-graph and Blender colour cells by
provenance (node-level black, swimlane-level grey, propagated italic)
without re-querying the resolver.

Worked example
--------------

.. code-block:: text

   EP_HELLENISTIC: start=-300, end=-100
   EP_ROMAN:       start=-100, end=+300

   US001: --has_first_epoch--> EP_HELLENISTIC
   US001: --has_property--> PN(absolute_time_end = -120)

   US005: --cuts--> US001                  # foundation trench
   US005: --has_property--> PN(absolute_time_start = -80)

   US010: --overlies--> US005
   US010: --has_first_epoch--> EP_ROMAN

For ``graph.calculate_chronology()``:

1. **Seeds**

   - US001 TPQ = −300 (EP_HELLENISTIC), TAQ = −120 (own PN; tighter
     than EP_HELLENISTIC.end = −100, so PN wins).
   - US005 TPQ = −80 (own PN), TAQ = none (will inherit).
   - US010 TPQ = −100 (EP_ROMAN), TAQ = +300 (EP_ROMAN).

2. **Topological mapping**

   ``cuts`` → US005 more recent than US001;
   ``overlies`` → US010 more recent than US005.

3. **BFS closure**

   - US005 inherits TPQ ≥ US001's TPQ (−300) — but its own PN
     constrains TPQ ≥ −80. Final TPQ = −80.
   - US005 inherits TAQ ≤ US010's TAQ (+300). Final TAQ = +300.
   - US001 inherits TAQ ≤ US005's TAQ (+300) — own PN
     constrains TAQ ≤ −120. Final TAQ = −120.

4. **Paradox check**: US001's window is ``[-300, -120]`` — consistent.
   US005's window is ``[-80, +300]`` — consistent.

If a sixth unit US015 cuts US005 *and* has TAQ = −150 (older than
US005), the BFS forces US005's window to invert and a
``[chronology paradox]`` warning is emitted with attribution.

The Master DocumentNode
-----------------------

DP-33 introduced the **Master DocumentNode** enrichment: the GraphML
importer rolls per-document chronology hints into a single epoch-level
PropertyNode so the resolver finds them at swimlane scope. The
mechanism is described in the [v0.1.33] changelog entry; for the
chronology pipeline it is transparent — the resolver sees a regular
PropertyNode attached to the epoch and uses it like any other
swimlane-level seed.

See also
--------

- :doc:`/internals/temporal` — TemporalInferenceEngine details and
  topology-to-temporal mapping.
- :doc:`/internals/propagation` — the 3-level resolver used to seed
  the chronology calculation.
- :doc:`/api/diagnostics` — cycle detection and paradox attribution.
