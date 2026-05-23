from .json_exporter import JSONExporter, export_to_json

try:
    from .rdf_exporter import (
        RDFExporter,
        export_to_rdf,
        export_single_graph_to_rdf,
    )
    _RDF_AVAILABLE = True
except ImportError:
    # rdflib is an optional dependency. The exporter package still loads,
    # but RDF export is unavailable. Install rdflib to enable.
    _RDF_AVAILABLE = False

__all__ = [
    "JSONExporter",
    "export_to_json",
]

if _RDF_AVAILABLE:
    __all__ += ["RDFExporter", "export_to_rdf", "export_single_graph_to_rdf"]