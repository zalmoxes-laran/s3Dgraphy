Node Types
==========

This section documents every node type in s3dgraphy. All nodes inherit
from :class:`s3dgraphy.nodes.base_node.Node` (documented in
:doc:`/api/core`) and register their ``node_type`` string in the global
``Node.node_type_map`` on import.

.. note::

   The ``node_type`` *string* — not the Python class name — is what is
   stored on the node, written to GraphML/JSON, and matched by
   :meth:`Graph.get_nodes_by_type` and the connection-validation rules.
   The class hierarchy (``real`` vs ``virtual`` families, ``is_series``
   membership) is driven by ``JSON_config/s3Dgraphy_node_datamodel.json``;
   use the helpers in :doc:`/api/classification` rather than hard-coding
   these strings.

Node type reference
-------------------

.. list-table::
   :header-rows: 1
   :widths: 22 16 62

   * - Class
     - ``node_type``
     - Meaning
   * - ``StratigraphicNode``
     - ``StratigraphicNode``
     - Abstract base for all stratigraphic units.
   * - ``StratigraphicUnit``
     - ``US``
     - Stratigraphic Unit — positive matter layer/context.
   * - ``NegativeStratigraphicUnit``
     - ``USN``
     - Negative unit — a cut, lacuna or interface (absence of matter).
   * - ``StructuralVirtualStratigraphicUnit``
     - ``USVs``
     - Structural Virtual unit — reconstructed structural element.
   * - ``NonStructuralVirtualStratigraphicUnit``
     - ``USVn``
     - Non-structural Virtual unit — hypothetical non-structural element.
   * - ``SpecialFindUnit``
     - ``SF``
     - Special Find — a not-in-situ element needing repositioning.
   * - ``VirtualSpecialFindUnit``
     - ``VSF``
     - Hypothetical reconstruction of a fragmented Special Find.
   * - ``ReusedSpecialFind``
     - ``RSF``
     - Re-used architectural/decorative element (spolia).
   * - ``DocumentaryStratigraphicUnit``
     - ``USD``
     - Documentary unit — based on historical/archival evidence.
   * - ``TransformationStratigraphicUnit``
     - ``TSU``
     - Transformation unit — toolmarks/reworkings on a surface.
   * - ``WorkingUnit``
     - ``UL``
     - Working unit — labour-related traces or interventions.
   * - ``SeriesOfStratigraphicUnit``
     - ``serSU``
     - Series of Stratigraphic Units.
   * - ``SeriesOfDocumentaryStratigraphicUnit``
     - ``serUSD``
     - Series of Documentary Stratigraphic Units.
   * - ``SeriesOfStructuralVirtualStratigraphicUnit``
     - ``serUSVs``
     - Series of Structural Virtual units.
   * - ``SeriesOfNonStructuralVirtualStratigraphicUnit``
     - ``serUSVn``
     - Series of non-structural Virtual units.
   * - ``ContinuityNode``
     - ``BR``
     - End-of-life ("continuity"/break) marker for a US/USV.
   * - ``StratigraphicEventNode``
     - ``SE``
     - The process/event that formed or altered a unit.
   * - ``UnknownNode``
     - ``unknown``
     - Fallback for unrecognised types.
   * - ``ParadataNode``
     - ``ParadataNode``
     - Abstract base for interpretation/provenance nodes.
   * - ``PropertyNode``
     - ``property``
     - A qualia/attribute (``value``, ``property_type``, ``units``).
   * - ``DocumentNode``
     - ``document``
     - A source document (role / content_nature / geometry axes).
   * - ``ExtractorNode``
     - ``extractor``
     - An extraction of information from a single source.
   * - ``CombinerNode``
     - ``combiner``
     - A reasoning that combines several sources.
   * - ``GroupNode``
     - ``Group``
     - Abstract base for grouping nodes.
   * - ``ActivityNodeGroup``
     - ``ActivityNodeGroup``
     - Logical grouping of related actions/activities.
   * - ``ParadataNodeGroup``
     - ``ParadataNodeGroup``
     - Container for a unit's paradata (``[US]_PD``).
   * - ``TimeBranchNodeGroup``
     - ``TimeBranchNodeGroup``
     - Alternative temporal interpretation branch.
   * - ``LocationNodeGroup``
     - ``LocationNodeGroup``
     - Spatial/locational membership plane (``kind``: toponym/study/functional).
   * - ``EpochNode``
     - ``EpochNode``
     - A chronological period (``start_time`` / ``end_time`` / ``color``).
   * - ``AuthorNode``
     - ``author``
     - Human creator/contributor.
   * - ``AuthorAINode``
     - ``author_ai``
     - AI-assisted creator (``model`` / ``prompt_reference``).
   * - ``GeoPositionNode``
     - ``geo_position``
     - Identitary geographic position (``epsg`` + shifts).
   * - ``LinkNode``
     - ``link``
     - External resource link (auto-typed by extension).
   * - ``LicenseNode``
     - ``license``
     - Licence metadata.
   * - ``EmbargoNode``
     - ``embargo``
     - Time-bound access restriction.
   * - ``GraphNode``
     - ``graph``
     - Represents the graph itself (for graph-level authorship/licence).
   * - ``HDTNode``
     - ``hdt``
     - Heritage Digital Twin (HDT-O ``HC2``) aggregation node.
   * - ``SemanticShapeNode``
     - ``semantic_shape``
     - 3D proxy geometry (convex shapes / spheres).
   * - ``RepresentationModelNode``
     - ``representation_model``
     - 3D model / spatialised image for stratigraphic units.
   * - ``RepresentationModelDocNode``
     - ``representation_model_doc``
     - 3D model / spatialised image for documents & extractors.
   * - ``RepresentationModelSpecialFindNode``
     - ``representation_model_sf``
     - 3D model for special finds (anastylosis hypotheses).

Stratigraphic nodes
-------------------

The stratigraphic family carries the ``symbol`` / ``label`` /
``detailed_description`` class attributes used by the visual layer and
the JSON/GraphML exporters.

.. automodule:: s3dgraphy.nodes.stratigraphic_node
   :members:
   :undoc-members:
   :show-inheritance:

Epoch nodes
-----------

.. automodule:: s3dgraphy.nodes.epoch_node
   :members:
   :undoc-members:
   :show-inheritance:

Paradata nodes
--------------

The paradata family encodes the *interpretation chain*: a
:class:`PropertyNode` (a claim) is justified by an
:class:`ExtractorNode` (extraction from one source) or a
:class:`CombinerNode` (a reasoning over several sources), which in turn
references :class:`DocumentNode` sources.

.. automodule:: s3dgraphy.nodes.paradata_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.property_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.document_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.extractor_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.combiner_node
   :members:
   :undoc-members:
   :show-inheritance:

Grouping nodes
--------------

Group nodes organise other nodes along orthogonal planes: by activity,
by paradata container, by alternative time branch, or by spatial
location. In GraphML they are rendered as yEd group folders.

.. automodule:: s3dgraphy.nodes.group_node
   :members:
   :undoc-members:
   :show-inheritance:

Authorship nodes
----------------

.. automodule:: s3dgraphy.nodes.author_node
   :members:
   :undoc-members:
   :show-inheritance:

Representation & geometry nodes
-------------------------------

These nodes attach 3D geometry and spatial information to any node. A
:class:`GeoPositionNode` is *identitary* (where the object is on Earth)
and is distinct from the *geometric* representation models.

.. automodule:: s3dgraphy.nodes.representation_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.semantic_shape_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.geo_position_node
   :members:
   :undoc-members:
   :show-inheritance:

Reference, rights & link nodes
------------------------------

.. automodule:: s3dgraphy.nodes.link_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.license_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.embargo_node
   :members:
   :undoc-members:
   :show-inheritance:

Graph & Heritage Digital Twin nodes
-----------------------------------

.. automodule:: s3dgraphy.nodes.graph_node
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: s3dgraphy.nodes.hdt_node
   :members:
   :undoc-members:
   :show-inheritance:
