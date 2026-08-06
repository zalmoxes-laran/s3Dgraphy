"""BUGFIX-CANVAS-IMPORT (2026-08-06) — graphml canvas metadata land in the
CANONICAL fields the funnel / Canvas inspector read.

The canvas-scope author / license / embargo that EMStudio's CANVAS1 writes and
``funnel.ts::readScopeValue`` reads live at ``graph.data['author_name' |
'license' | 'embargo']`` (the em.json ``graph.data`` the exporter emits; the
funnel's canonical read key). The importer used to put license/embargo under a
DIFFERENT key (``embargo_until``) and the author only in an AuthorNode, so the
imported metadata never showed in the UI nor propagated through the funnel.
"""

import pathlib

from s3dgraphy.graph import Graph
from s3dgraphy.importer.import_graphml import GraphMLImporter

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "canvas_metadata.graphml"


def _import():
    return GraphMLImporter(str(FIXTURE), Graph(graph_id="g")).parse()


def test_author_lands_in_canonical_field():
    g = _import()
    # canonical canvas-tier author: graph.data['author_name'] (display name)
    assert g.data.get("author_name") == "Emanuel Demetrescu"


def test_license_lands_in_canonical_field():
    g = _import()
    assert g.data.get("license") == "CC-BY-NC"


def test_embargo_lands_in_canonical_key_not_legacy():
    g = _import()
    # canonical key is 'embargo' (what the funnel reads), NOT 'embargo_until'
    assert g.data.get("embargo") == "2025-12-31"


def test_header_metadata_also_in_graph_attributes_for_s3dgraphy():
    g = _import()
    # s3Dgraphy's OWN resolver (builtin_rules._author_graph_level) reads
    # graph.attributes; both stores are written so neither reader is stale (DP-40).
    assert g.attributes.get("author_name") == "Emanuel"
    assert g.attributes.get("license") == "CC-BY-NC"
    assert g.attributes.get("ORCID") == "0000-0002-1825-0097"
