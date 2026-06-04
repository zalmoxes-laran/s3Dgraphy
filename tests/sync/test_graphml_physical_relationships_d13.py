"""Tests for the per-node ``physical_relationships`` (d13) GraphML
channel — the EM 1.6 palette format that mirrors the pyArchInit
``us_table.rapporti`` column.

Two surfaces are pinned here:

* The exporter declares ``physical_relationships`` as a node-level key
  and emits a ``<data key="d13">`` element on stratigraphic nodes that
  participate in canonical physical relations. The payload is the
  Python-literal ``repr`` of the list-of-lists produced by
  :func:`s3dgraphy.sync.rapporti.serialize_rapporti_from_edges`.

* The importer prefers the richer graph-level
  ``_s3d_physical_relations`` JSON side channel when present. When
  that channel is *absent* (legacy / hand-authored EM 1.6 files), the
  per-node packed string fallback restores the canonical edges via
  :func:`s3dgraphy.sync.rapporti.parse_rapporti`.
"""

from __future__ import annotations

import ast
import os
import re
import tempfile

from s3dgraphy import Graph
from s3dgraphy.exporter.graphml.graphml_exporter import GraphMLExporter
from s3dgraphy.importer.import_graphml import GraphMLImporter
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_two_us_graph_with_overlies() -> Graph:
    """Tiny graph: ``US 12 -[overlies]-> US 6``."""
    g = Graph("TestSite")
    us1 = StratigraphicNode("uuid_us1", "US 12")
    us2 = StratigraphicNode("uuid_us2", "US 6")
    us1.attributes = {"us": "12", "unita_tipo": "US", "attivita": "1"}
    us2.attributes = {"us": "6", "unita_tipo": "US", "attivita": "1"}
    us1.node_type = "US"
    us2.node_type = "US"
    g.add_node(us1)
    g.add_node(us2)
    g.add_edge("e1", "uuid_us1", "uuid_us2", "overlies")
    return g


def _export_to_tempfile(graph: Graph, tmpdir: str) -> str:
    out = os.path.join(tmpdir, "out.graphml")
    GraphMLExporter(graph).export(out)
    return out


def _strip_json_side_channel(graphml_text: str) -> str:
    """Mutate exported GraphML to look like a legacy file: drop the
    ``_s3d_physical_relations`` key declaration AND the data payload
    so the importer falls back to the d13 channel.
    """
    text = re.sub(
        r"<data key=\"d_s3d_phys_rel\">.*?</data>",
        "", graphml_text, flags=re.DOTALL)
    text = re.sub(
        r"<key[^>]*attr\.name=\"_s3d_physical_relations\"[^/]*/>",
        "", text)
    return text


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


def test_exporter_declares_d13_key():
    g = _make_two_us_graph_with_overlies()
    with tempfile.TemporaryDirectory() as td:
        out = _export_to_tempfile(g, td)
        with open(out) as f:
            content = f.read()
    assert 'attr.name="physical_relationships"' in content
    assert 'id="d13"' in content


def test_exporter_emits_d13_data_on_source_node():
    g = _make_two_us_graph_with_overlies()
    with tempfile.TemporaryDirectory() as td:
        out = _export_to_tempfile(g, td)
        with open(out) as f:
            content = f.read()
    m = re.search(r'<data key="d13">(.*?)</data>', content)
    assert m is not None, "d13 data element not emitted"
    payload = ast.literal_eval(m.group(1))
    # Format: [[label, target_us, area, sito], …]. Italian verbose
    # label for canonical US-family unit types.
    assert payload == [["Copre", "6", "1", "TestSite"]]


def test_exporter_omits_d13_when_no_physical_relations():
    """A graph with only paradata / temporal edges should not emit d13
    on its US nodes — the dict from serialize_rapporti_from_edges is
    empty for those keys."""
    g = Graph("TestSite")
    us = StratigraphicNode("uuid_us", "US 42")
    us.attributes = {"us": "42", "unita_tipo": "US", "attivita": "1"}
    us.node_type = "US"
    g.add_node(us)
    with tempfile.TemporaryDirectory() as td:
        out = _export_to_tempfile(g, td)
        with open(out) as f:
            content = f.read()
    # Key declaration always present; the per-node data is not.
    assert 'attr.name="physical_relationships"' in content
    assert 'key="d13"' not in content


# ---------------------------------------------------------------------------
# Importer — JSON channel takes precedence
# ---------------------------------------------------------------------------


def test_full_round_trip_via_json_channel_restores_overlies():
    g = _make_two_us_graph_with_overlies()
    with tempfile.TemporaryDirectory() as td:
        out = _export_to_tempfile(g, td)
        g2 = Graph("imported")
        GraphMLImporter(out, g2).parse()
    overlies = [e for e in g2.edges if e.edge_type == "overlies"]
    assert len(overlies) == 1
    edge = overlies[0]
    assert edge.edge_source == "uuid_us1"
    assert edge.edge_target == "uuid_us2"


# ---------------------------------------------------------------------------
# Importer — d13 fallback when JSON channel is absent
# ---------------------------------------------------------------------------


def test_d13_fallback_restores_overlies_when_json_channel_stripped():
    g = _make_two_us_graph_with_overlies()
    with tempfile.TemporaryDirectory() as td:
        out = _export_to_tempfile(g, td)
        with open(out) as f:
            content = f.read()
        legacy = _strip_json_side_channel(content)
        out2 = os.path.join(td, "legacy.graphml")
        with open(out2, "w") as f:
            f.write(legacy)
        g2 = Graph("imported_d13")
        GraphMLImporter(out2, g2).parse()
    overlies = [e for e in g2.edges if e.edge_type == "overlies"]
    assert len(overlies) == 1, (
        "d13 fallback failed to restore the overlies edge "
        "after the JSON side channel was stripped")
    # The reduced ``is_after`` edge from parse_edges should have been
    # dropped — the per-node packed string is the canonical set, not
    # an addition to it.
    is_after = [e for e in g2.edges if e.edge_type == "is_after"]
    assert len(is_after) == 0


def test_d13_fallback_skipped_when_json_channel_present():
    """When BOTH channels are emitted (the s3dgraphy exporter does
    this in every output), the importer should consume the JSON
    channel and skip the d13 fallback — not double up the edges."""
    g = _make_two_us_graph_with_overlies()
    with tempfile.TemporaryDirectory() as td:
        out = _export_to_tempfile(g, td)
        g2 = Graph("imported")
        GraphMLImporter(out, g2).parse()
    overlies = [e for e in g2.edges if e.edge_type == "overlies"]
    assert len(overlies) == 1, "edges should not double up"
