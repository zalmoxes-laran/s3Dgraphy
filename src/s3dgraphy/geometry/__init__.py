"""The PROXY, as a quale.

A proxy is the geometry-without-material of a unit: the shape US101 has, without
asserting what it is made of. Until EM 1.6.2 it was a `SemanticShapeNode` hanging
off the unit on its own — and a lone node cannot say where it came from. "The
proxy of US101" could not be traced to a measurement, a photograph or a
reprojection, because it had no paradata chain to be traced through.

So the proxy becomes a **`PropertyNode` of type `geometry`** whose payload is a
SemanticShape:

    US ──has_property──▶ Property(geometry) ──has_semantic_shape──▶ SemanticShape
                              ▲                                     (hulls | spheres | .glb)
                              │ has_data_provenance
                        Extractor(s) ──combines──◀── Combiner

Two things follow, and both are the point:

  · the proxy inherits the chain every other quale has, so it can say *how* it is
    known;
  · ONE proxy can be synthesised from SEVERAL sources — a photogrammetric mesh
    and a 1931 photograph — instead of one node per source with nothing to join
    them.

Nothing here is special-cased for geometry: the provenance is built with the
same `extracted_from` / `combines` / `has_data_provenance` edges every other
property uses. That is deliberate — a geometry property that needed its own
provenance mechanism would be a second paradata model to keep in step.
"""

from .proxy import GeometryProxyResult, create_geometry_proxy
from .migrate import migrate_legacy_proxies

__all__ = ["create_geometry_proxy", "GeometryProxyResult", "migrate_legacy_proxies"]
