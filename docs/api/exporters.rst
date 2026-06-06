Exporters API
=============

s3dgraphy can serialise an in-memory :class:`~s3dgraphy.graph.Graph` (or
all graphs held by the :class:`~s3dgraphy.multigraph.multigraph.MultiGraphManager`)
to four target formats. Each exporter targets a different consumer.

.. list-table::
   :header-rows: 1
   :widths: 24 22 18 36

   * - Class
     - Output
     - Entry method
     - Target / use
   * - ``JSONExporter``
     - JSON (lossless v1.6)
     - ``export_graphs()``
     - Web viewers (Heriverse, ATON).
   * - ``RDFExporter``
     - Turtle / N-Triples / JSON-LD / TriG / …
     - ``export_graphs()`` / ``export_single_graph()``
     - Semantic web / SPARQL; CIDOC-CRM + HDT-O + EM ontology.
   * - ``UnifiedXLSXExporter``
     - ``em_data.xlsx`` (5 sheets)
     - ``write(path)``
     - Round-trip & graph→spreadsheet refactoring (inverse of the unified importer).
   * - ``GraphMLExporter``
     - yEd GraphML
     - ``export(path)``
     - Round-trip editing in yEd; temporal inference + transitive reduction.

JSON exporter
-------------

The JSON exporter writes the **lossless 1.6 schema**: every node and edge
carries its ``attributes`` dict, PropertyNode ``value`` / ``property_type``
/ ``units`` are lifted to the top level, and nodes are organised into
semantic buckets (stratigraphic, epochs, properties, documents,
authors, …) for direct consumption by WebGL viewers.

.. automodule:: s3dgraphy.exporter.json_exporter
   :members:
   :undoc-members:
   :show-inheritance:

RDF exporter
------------

The RDF exporter maps each graph to a named graph anchored by
``em:EMGraph`` (also typed as ``hdto:HC16_Heritage_Proposition_Set``).
Node and edge types are resolved from the datamodel to CIDOC-CRM /
CRMarchaeo classes, the ``AP11_has_physical_relation`` family is emitted
with EM subproperties, and an optional ``parent_hdt_iri`` binds every
graph to a Heritage Digital Twin.

.. note::

   RDF export requires the optional ``rdflib`` dependency
   (``pip install s3dgraphy[rdf]`` or ``[full]``). It is mocked at
   documentation-build time, so signatures below are introspected
   without ``rdflib`` installed.

.. automodule:: s3dgraphy.exporter.rdf_exporter
   :members:
   :undoc-members:
   :show-inheritance:

Unified XLSX exporter
---------------------

The inverse of :class:`~s3dgraphy.importer.unified_xlsx_importer.UnifiedXLSXImporter`:
it walks the graph and writes the five typed sheets (Units, Epochs,
Claims, Authors, Documents), reconstructing the attribution chain and
emitting only canonical edge directions. See
:doc:`/exporters/unified_xlsx_exporter` for the column reference.

.. automodule:: s3dgraphy.exporter.unified_xlsx_exporter
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

GraphML exporter
----------------

Builds a yEd-compatible GraphML document from scratch. The exporter
orchestrates a set of node/edge/group/epoch generators, materialises
continuity diamonds, runs temporal inference + transitive reduction to a
minimal ``is_after`` set, and applies the Hybrid-C auxiliary-lifecycle
policy controlled by ``persist_auxiliary`` (volatile vs bake). See the
design note :doc:`/GRAPHML_EXPORT` and :doc:`/internals/transforms`.

.. automodule:: s3dgraphy.exporter.graphml.graphml_exporter
   :members:
   :undoc-members:
   :show-inheritance:

.. seealso::

   The in-place GraphML patcher
   (:class:`s3dgraphy.exporter.graphml.graphml_patcher.GraphMLPatcher`),
   which updates an existing yEd file while preserving visual state, is
   documented in :doc:`/internals/merge_patcher`.
