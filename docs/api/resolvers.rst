Resolvers API
=============

The :mod:`s3dgraphy.resolvers` package implements *property propagation*:
given a node and a property name, the resolver walks the graph and returns
the value (and the source level it came from — ``node``, ``swimlane``,
``graph``) without forcing the caller to know which edges to traverse.

Property resolver
-----------------

.. automodule:: s3dgraphy.resolvers.property_resolver
   :members:
   :undoc-members:
   :show-inheritance:

Builtin rules
-------------

.. automodule:: s3dgraphy.resolvers.builtin_rules
   :members:
   :undoc-members:
   :show-inheritance:

See :doc:`/internals/propagation` for the conceptual model (node-level →
swimlane-level → graph-level fallback) and the list of canonical
:class:`PropagationRule` instances shipped with 1.5.
