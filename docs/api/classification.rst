Classification API
==================

The :mod:`s3dgraphy.classification` module is the JSON-driven *single source
of truth* for stratigraphic family (``real`` / ``virtual``) and ``is_series``
membership. Consumers (EM-blender-tools pickers, GraphML importer
BR-handling, filter chains) should use these helpers instead of hardcoding
type lists.

Accessors
---------

.. automodule:: s3dgraphy.classification
   :members:
   :undoc-members:
   :show-inheritance:

Re-exported constants
---------------------

The following frozensets are also re-exported from the package root for
convenience (``from s3dgraphy import REAL_US_TYPES``):

.. autodata:: s3dgraphy.classification.REAL_US_TYPES
   :annotation:
   :no-index:

.. autodata:: s3dgraphy.classification.VIRTUAL_US_TYPES
   :annotation:
   :no-index:

.. autodata:: s3dgraphy.classification.SERIES_US_TYPES
   :annotation:
   :no-index:

.. autodata:: s3dgraphy.classification.ALL_US_TYPES
   :annotation:
   :no-index:

See :doc:`/internals/classification` for the conceptual overview and a
worked example of extending the JSON datamodel with a new subtype.
