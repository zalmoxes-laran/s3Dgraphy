Diagnostics API
===============

The :mod:`s3dgraphy.diagnostics` module collects the *paradata-aware*
diagnostic walks introduced with the unified xlsx pipeline (DP-02 / DP-32).
These functions answer questions of the form *"who made this claim?"* and
*"is the stratigraphic order self-consistent?"* without imposing a fixed
schema on the calling code.

.. automodule:: s3dgraphy.diagnostics
   :members:
   :undoc-members:
   :show-inheritance:

See also
--------

- :doc:`/internals/propagation` — how property resolution walks the
  ``has_data_provenance`` / ``has_paradata_nodegroup`` chains.
- :doc:`/internals/temporal` — TPQ / TAQ propagation and the
  ``[chronology paradox]`` warnings that ``attribute_temporal_claim``
  annotates.
- :doc:`/internals/chronology` — the high-level chronology calculation
  pipeline and how diagnostics surface inside it.
