"""S2b — the canonical document, renamed from "master".

"Master" read as *original vs copies*, which is wrong: every digital document is
a copy, there is no original among them. What the flag actually marks is the
document node drawn at its own moment of creation — the **canonical** one —
against the instances that re-use it in other contexts.

The rename is clean in the new schema (2) and the old spelling is **read, never
written**: a file saved by an older version keeps working and is normalised on
import, so the in-memory graph speaks one language whatever wrote it.
"""

import json

import pytest

from s3dgraphy import api
from s3dgraphy.exporter.emjson_exporter import SCHEMA_VERSION, export_emjson
from s3dgraphy.graph import Graph
from s3dgraphy.importer.emjson_importer import import_emjson, parse_emjson
from s3dgraphy.nodes.document_node import (CANONICAL_DOCUMENT_FLAG,
                                           CANONICAL_FLAG,
                                           CANONICAL_UNKNOWN_STYLE,
                                           DocumentNode,
                                           LEGACY_CANONICAL_DOCUMENT_FLAG,
                                           LEGACY_CANONICAL_FLAG,
                                           normalise_canonical_attributes)


def _doc(**attrs):
    d = DocumentNode(node_id="D.1", name="D.1")
    d.attributes.update(attrs)
    return d


# ── the rename itself ─────────────────────────────────────────────────────────
def test_the_schema_version_records_the_rename():
    assert SCHEMA_VERSION >= 2


def test_the_key_names_are_the_canonical_ones():
    assert CANONICAL_FLAG == "is_canonical"
    assert CANONICAL_DOCUMENT_FLAG == "em_canonical_document"
    assert CANONICAL_UNKNOWN_STYLE == "canonical_unknown"
    # the legacy spelling is still known — for reading
    assert LEGACY_CANONICAL_FLAG == "is_master"
    assert LEGACY_CANONICAL_DOCUMENT_FLAG == "em_master_document"


def test_the_style_key_follows_the_new_name():
    assert _doc(is_canonical=True).variant_style_key() == "canonical_unknown"
    assert _doc().variant_style_key() == "default"
    # geometry still wins over the canonical fallback
    d = _doc(is_canonical=True)
    d.data["geometry"] = "reality_based"
    assert d.variant_style_key() == "reality_based"


def test_the_visual_rules_declare_the_new_style_key():
    from s3dgraphy.nodes.base_node import load_json_mapping
    styles = load_json_mapping("em_visual_rules.json")["document_variant_styles"]
    assert "canonical_unknown" in styles
    assert "master_unknown" not in styles


@pytest.mark.parametrize("flag", ["is_canonical", "em_canonical_document"])
def test_either_current_flag_marks_it_canonical(flag):
    assert _doc(**{flag: True}).is_canonical() is True


@pytest.mark.parametrize("flag", ["is_master", "em_master_document"])
def test_either_legacy_flag_is_still_honoured(flag):
    """A graph built by an older version, in memory, must not silently lose its
    canonical documents."""
    assert _doc(**{flag: True}).is_canonical() is True


def test_a_document_without_any_flag_is_an_instance():
    assert _doc().is_canonical() is False
    assert _doc(is_canonical=False).is_canonical() is False


# ── legacy normalisation ──────────────────────────────────────────────────────
def test_normalisation_carries_the_value_over_and_drops_the_old_key():
    attrs = {"is_master": True, "em_master_document": True, "other": 1}
    normalise_canonical_attributes(attrs)
    assert attrs == {"is_canonical": True, "em_canonical_document": True, "other": 1}


def test_normalisation_does_not_overwrite_an_explicit_new_key():
    attrs = {"is_master": True, "is_canonical": False}
    normalise_canonical_attributes(attrs)
    assert attrs["is_canonical"] is False      # the current key wins
    assert "is_master" not in attrs


def test_normalisation_tolerates_anything():
    assert normalise_canonical_attributes(None) is None
    assert normalise_canonical_attributes({}) == {}


# ── round-trip: new writes canonical, legacy reads and normalises ─────────────
def _graph_with_canonical_doc():
    g = Graph(graph_id="g")
    d = DocumentNode(node_id="D.1", name="D.1")
    d.attributes["em_canonical_document"] = True
    g.add_node(d)
    return g


def test_a_new_document_round_trips_with_the_canonical_key(tmp_path):
    path = export_emjson(_graph_with_canonical_doc(), str(tmp_path / "g.em.json"))
    payload = json.loads(open(path, encoding="utf-8").read())
    assert payload["header"]["schema_version"] == SCHEMA_VERSION
    # An em.json FILE is a container since 2026-08-13: one graph is a
    # container-of-one, so the nodes live in the member rather than in a
    # top-level `graph` section.
    member = next(iter(payload["graphs"].values()))
    doc_node = next(n for n in member["nodes"] if n["id"] == "D.1")
    data = doc_node.get("data") or {}
    assert data.get("em_canonical_document") is True
    assert "em_master_document" not in data     # the old spelling is never written

    reloaded, warnings = import_emjson(path)
    assert not warnings
    assert reloaded.find_node_by_id("D.1").is_canonical() is True


@pytest.mark.parametrize("legacy_key", ["is_master", "em_master_document"])
def test_a_legacy_emjson_loads_and_is_normalised(legacy_key):
    """A file written before the rename: schema 1 (or none) and the old key."""
    doc = api.graph_to_emjson(Graph(graph_id="g"))
    doc["header"]["schema_version"] = 1
    doc["graph"]["nodes"].append({
        "id": "D.1", "node_type": "document", "name": "D.1",
        "data": {legacy_key: True},
    })
    graph, warnings = parse_emjson(doc)
    assert not warnings
    node = graph.find_node_by_id("D.1")
    assert node.is_canonical() is True                     # nothing lost
    merged = {**(node.attributes or {}), **(node.data or {})}
    assert legacy_key not in merged                        # …and normalised
    assert merged.get("is_canonical") or merged.get("em_canonical_document")


def test_a_legacy_document_still_styles_as_canonical():
    doc = api.graph_to_emjson(Graph(graph_id="g"))
    doc["graph"]["nodes"].append({
        "id": "D.1", "node_type": "document", "data": {"is_master": True}})
    graph, _ = parse_emjson(doc)
    assert graph.find_node_by_id("D.1").variant_style_key() == "canonical_unknown"


def test_the_shelf_hat_marks_the_document_canonical():
    shelf = api.new_shelf()
    api.add_to_shelf(shelf, "/lib/model.glb", resource_id="r1", name="model")
    study = Graph(graph_id="study")
    api.hat_as_document(study, "r1", shelf=shelf, doc_id="D.7")
    assert study.find_node_by_id("D.7").is_canonical() is True


def test_the_old_keyword_argument_is_gone():
    """Clean rename: `mark_as_master` no longer exists. Callers move to
    `mark_as_canonical` (listed in the report as a consumer follow-up)."""
    shelf = api.new_shelf()
    api.add_to_shelf(shelf, "/lib/model.glb", resource_id="r1", name="model")
    with pytest.raises(TypeError):
        api.hat_as_document(Graph(graph_id="s"), "r1", shelf=shelf,
                            mark_as_master=False)
    study = Graph(graph_id="s")
    api.hat_as_document(study, "r1", shelf=shelf, doc_id="D.9",
                        mark_as_canonical=False)
    assert study.find_node_by_id("D.9").is_canonical() is False


# ── E: canonical_unknown is a STYLE, never a geometry ─────────────────────────

def test_canonical_unknown_is_not_a_geometry_value():
    """``canonical_unknown`` describes a BORDER (thick black: canonical, not yet
    classified), not a degree of metric authority. It used to leak into
    ``DOCUMENT_GEOMETRIES`` because the filter only excluded ``default`` — which
    would have let a document declare, as its geometry, that it has no geometry.
    """
    from s3dgraphy.nodes.document_node import DOCUMENT_GEOMETRIES

    assert "canonical_unknown" not in DOCUMENT_GEOMETRIES
    assert "default" not in DOCUMENT_GEOMETRIES
    # the real axis, unaffected
    assert DOCUMENT_GEOMETRIES == ("reality_based", "observable", "asserted",
                                   "symbolic", "em_based")


def test_it_is_refused_as_a_geometry():
    from s3dgraphy.nodes.document_node import DocumentNode

    with pytest.raises(ValueError):
        DocumentNode(node_id="D.1", name="D.1", geometry="canonical_unknown")


def test_it_still_works_as_a_style_key():
    """Removing it from the vocabulary must not remove it from the palette: the
    thick black border is how a canonical-but-unclassified document is drawn."""
    from s3dgraphy.utils.utils import get_document_variant_style

    style = get_document_variant_style("canonical_unknown")
    assert style["border_color"] == "#000000"
    assert style["border_width"] >= 3.0          # thick = canonical
    assert get_document_variant_style("default")["border_width"] < 3.0


def test_a_canonical_document_without_geometry_still_styles_as_unknown():
    assert _doc(is_canonical=True).variant_style_key() == "canonical_unknown"
