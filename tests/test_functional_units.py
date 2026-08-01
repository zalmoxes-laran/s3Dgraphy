"""DP-72 — Functional Units: the typed componential aggregation node.

A Functional Unit groups the stratigraphic units that make up one recognisable
architectural component (the column made of its US). Membership is a TAG axis,
`is_in_functional_unit` (m:n, additive) — NOT the nesting axis `is_part_of`,
even though both project to the same mereological P46i: a Functional Unit
legitimately spans epochs, and the nesting axis is what draws a box and assigns
a lane. It is distinct from an ActivityNodeGroup (actions), from a generic
container (a US that contains things is still a US) and from a LocationNodeGroup
of kind `functional` (a named place).
"""

import json
from pathlib import Path

import pytest

from s3dgraphy.graph import Graph
from s3dgraphy.nodes import FunctionalUnitNodeGroup
from s3dgraphy.nodes.base_node import Node
from s3dgraphy.nodes.group_node import (ActivityNodeGroup, GroupNode,
                                        LocationNodeGroup)
from s3dgraphy.nodes.stratigraphic_node import (SpecialFindUnit,
                                                StratigraphicUnit)

_JSON_CONFIG = Path(__file__).resolve().parents[1] / "src" / "s3dgraphy" / "JSON_config"


def _column_graph():
    """A column made of three US, plus an SF reused in one of them."""
    g = Graph(graph_id="site")
    g.add_node(FunctionalUnitNodeGroup(node_id="FU1", name="Column 1",
                                       geometry_type_ref="aat:300047102"))
    for nid, name in (("US1", "base"), ("US2", "shaft"), ("US3", "capital")):
        g.add_node(StratigraphicUnit(node_id=nid, name=name))
        g.add_edge(f"{nid}_in_FU1", nid, "FU1", "is_in_functional_unit")
    g.add_node(SpecialFindUnit(node_id="SF1", name="reused block"))
    g.add_edge("SF1_is_part_of_US1", "SF1", "US1", "is_part_of")
    return g


# ── the node type itself ──────────────────────────────────────────────────────
def test_functional_unit_is_a_group_node():
    fu = FunctionalUnitNodeGroup(node_id="FU1", name="Column 1")
    assert isinstance(fu, GroupNode)
    assert fu.node_type == "FunctionalUnitNodeGroup"
    assert Node.node_type_map["FunctionalUnitNodeGroup"] is FunctionalUnitNodeGroup


def test_geometry_type_is_carried_by_reference_only():
    """DP-72: the geometry type points at an EXTERNAL taxonomy; nothing is
    internalized, so nothing is validated and the attribute stays absent when
    the caller says nothing."""
    assert "geometry_type_ref" not in FunctionalUnitNodeGroup("FU1", "c").attributes
    fu = FunctionalUnitNodeGroup("FU2", "c", geometry_type_ref="bsdd:column")
    assert fu.attributes["geometry_type_ref"] == "bsdd:column"


# ── membership is a TAG axis, distinct from DP-36 nesting ─────────────────────
def _edge_def(name):
    cm = json.loads((_JSON_CONFIG / "s3Dgraphy_connections_datamodel.json").read_text())

    def find(o):
        if isinstance(o, dict):
            if name in o and isinstance(o[name], dict) and "allowed_connections" in o[name]:
                return o[name]
            for v in o.values():
                got = find(v)
                if got:
                    return got
        return None

    return find(cm)


def test_units_join_via_is_in_functional_unit():
    g = _column_graph()
    members = {n.node_id for n in g.get_functional_unit_members("FU1")}
    assert members == {"US1", "US2", "US3"}
    assert not any(e.edge_type == "generic_connection" for e in g.edges)
    # the tag axis does NOT make the FU a nesting container
    assert g.get_contained_nodes("FU1") == []
    assert not g.is_container("FU1")


def test_membership_edge_is_the_tag_axis_not_the_nesting_one():
    """The datamodel — not this test — is the authority. Asserted on the JSON:
    `Graph.validate_connection` cannot decide it, because it resolves the allowed
    CLASS names through the node_type-keyed map and lets anything pass when the
    name is not also a node_type (e.g. `StratigraphicNode`)."""
    membership = _edge_def("is_in_functional_unit")["allowed_connections"]
    # the stratigraphic family, one concrete class at a time (see the _note:
    # the base name 'StratigraphicNode' is the node_type of a single subclass)
    assert {"StratigraphicUnit", "DocumentaryStratigraphicUnit",
            "VirtualStratigraphicUnit", "SpecialFindUnit"} <= set(membership["source"])
    assert "StratigraphicNode" not in membership["source"]
    assert "FunctionalUnitNodeGroup" in membership["source"]  # FU ∈ FU (nesting)
    assert membership["target"] == ["FunctionalUnitNodeGroup"]

    nesting = _edge_def("is_part_of")["allowed_connections"]
    # a Functional Unit is NOT a nesting container...
    assert "FunctionalUnitNodeGroup" not in nesting["target"]
    # ...but a whole component CAN be physically embedded in a US
    assert "FunctionalUnitNodeGroup" in nesting["source"]


def test_both_axes_project_to_the_same_cidoc_property():
    """Distinct in the EM language, one relation in RDF."""
    assert (_edge_def("is_in_functional_unit")["mapping"]["cidoc"]
            == _edge_def("is_part_of")["mapping"]["cidoc"] == "P46i_forms_part_of")


def test_functional_units_nest():
    g = _column_graph()
    g.add_node(FunctionalUnitNodeGroup(node_id="FU0", name="Portico"))
    g.add_edge("FU1_in_FU0", "FU1", "FU0", "is_in_functional_unit")
    assert [n.node_id for n in g.get_functional_units_of("FU1")] == ["FU0"]
    assert [n.node_id for n in g.get_functional_unit_members("FU0")] == ["FU1"]


def test_a_functional_unit_can_be_embedded_in_a_stratigraphic_unit():
    """E.D. 2026-08-01: the column engaged in a later wall — that one IS
    containment, and keeps using `is_part_of`."""
    g = _column_graph()
    g.add_node(StratigraphicUnit(node_id="US9", name="later wall"))
    g.add_edge("FU1_is_part_of_US9", "FU1", "US9", "is_part_of")
    assert [n.node_id for n in g.get_containers_of("FU1")] == ["US9"]
    assert g.is_container("US9")


def test_dp36_containers_are_untouched():
    g = _column_graph()
    assert [n.node_id for n in g.get_contained_nodes("US1")] == ["SF1"]
    assert g.is_container("US1") and not g.is_container("US2")


def test_members_stay_stratigraphic_and_membership_is_m_to_n():
    """The units keep their own axes; a US may be nested in a container AND tagged
    into more than one Functional Unit."""
    g = _column_graph()
    g.add_node(FunctionalUnitNodeGroup(node_id="FU2", name="Roof support"))
    g.add_edge("US1_in_FU2", "US1", "FU2", "is_in_functional_unit")
    g.add_edge("US1_is_part_of_US2", "US1", "US2", "is_part_of")
    assert {n.node_id for n in g.get_functional_units_of("US1")} == {"FU1", "FU2"}
    assert [n.node_id for n in g.get_containers_of("US1")] == ["US2"]  # nesting: one
    assert g.find_node_by_id("US1").node_type == "US"   # unchanged by the aggregation


def test_get_functional_units():
    g = _column_graph()
    g.add_node(ActivityNodeGroup(node_id="A1", name="Erection of columns"))
    g.add_node(LocationNodeGroup(node_id="L1", name="Room 12", kind="functional"))
    assert [n.node_id for n in g.get_functional_units()] == ["FU1"]


# ── datamodel + registry ──────────────────────────────────────────────────────
def test_declared_in_the_categorized_section_with_its_mapping():
    dm = json.loads((_JSON_CONFIG / "s3Dgraphy_node_datamodel.json").read_text())
    entry = dm["group_nodes"]["GroupNode"]["subtypes"]["FunctionalUnitNodeGroup"]
    assert entry["parent"] == "GroupNode"
    # NOT the E78 Collection its GroupNode parent defaults to: a component is a
    # whole made of parts, not a curated set.
    assert entry["mapping"]["cidoc"] == "E24 Physical Human-Made Thing"
    assert "P46" in entry["mapping"]["alternative"]
    assert entry["em_extension"]["uri"] == "em:FunctionalUnit"
    assert entry["em_extension"]["subclass_of"] == ["crm:E24_Physical_Human-Made_Thing"]
    # the scope note states what it is NOT (the three neighbours)
    desc = entry["description"]
    for neighbour in ("ActivityNodeGroup", "container", "LocationNodeGroup"):
        assert neighbour in desc


def test_registry_regenerated_not_hand_edited():
    reg = json.loads((_JSON_CONFIG / "node_registry.generated.json").read_text())
    entry = reg["node_types"]["FunctionalUnitNodeGroup"]
    assert entry["parent"] == "GroupNode"
    assert entry["node_type"] == "FunctionalUnitNodeGroup"


# ── em.json round-trip (generic by node_type — nothing to special-case) ───────
def test_emjson_round_trip(tmp_path):
    from s3dgraphy.exporter.emjson_exporter import export_emjson
    from s3dgraphy.importer.emjson_importer import import_emjson
    path = export_emjson(_column_graph(), str(tmp_path / "site.em.json"))
    g2, warnings = import_emjson(path)
    assert not [w for w in warnings if "FunctionalUnit" in w]
    fu = g2.find_node_by_id("FU1")
    assert isinstance(fu, FunctionalUnitNodeGroup)
    assert fu.attributes.get("geometry_type_ref") == "aat:300047102"
    assert {n.node_id for n in g2.get_functional_unit_members("FU1")} == {"US1", "US2",
                                                                          "US3"}


# ── the case that forced the tag axis: a component spanning epochs ────────────
def test_a_functional_unit_spans_the_epochs_of_its_members():
    """E.D. 2026-08-01: a wall made of elements from four stratified epochs still
    holds the roof as one body. The FU has NO epoch of its own — its temporal
    extent is derived — and it may cover several."""
    from s3dgraphy.nodes.epoch_node import EpochNode
    g = _column_graph()
    for i, nid in enumerate(("US1", "US2", "US3")):
        ep = f"ep{i}"
        g.add_node(EpochNode(node_id=ep, name=f"phase {i}",
                             start_time=i * 100, end_time=(i + 1) * 100))
        g.add_edge(f"{nid}_hfe_{ep}", nid, ep, "has_first_epoch")
    spanned = [n.node_id for n in g.get_functional_unit_epochs("FU1")]
    assert spanned == ["ep0", "ep1", "ep2"]
    # no epoch edge of its own
    assert not any(e.edge_source == "FU1"
                   and e.edge_type in ("has_first_epoch", "survive_in_epoch")
                   for e in g.edges)


@pytest.mark.parametrize("edge_type", ["is_in_activity", "is_in_location"])
def test_the_other_aggregation_axes_do_not_accept_it(edge_type):
    """An Activity clusters actions and a Location is a place — neither takes a
    Functional Unit as target."""
    assert Graph.validate_connection("US", "FunctionalUnitNodeGroup",
                                     edge_type) is False


def test_a_stratigraphic_member_is_accepted_without_degrading():
    """End-to-end guard on `add_edge`: the whole point of listing the concrete
    classes is that the membership edge survives instead of silently becoming a
    `generic_connection`."""
    g = _column_graph()
    assert g.warnings == []
    assert {e.edge_type for e in g.edges} == {"is_in_functional_unit", "is_part_of"}
