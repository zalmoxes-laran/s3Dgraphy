"""A find inside a layer: P46 is not enough, and the inverse was going out too.

Two faults, one edge. `is_part_of` projected to `P46i_forms_part_of` — correct
but generic — while CRMarchaeo has a property for exactly this case: AP21
contains / AP21i is contained in, the declared shortcut for the path
E18 -AP18i- A7 Embedding -AP19- A2. A7's own scope note carries the
distinction that matters to an archaeologist: an embedding is normally stable
from the generation of the A2 around it, "but it may also be due to later
intrusion".

The second fault was quieter. The exporter emits the declared
`extension_mapping` with the SAME subject and object as the core predicate, and
the slot held `P46_is_composed_of` — the inverse. So every containment in the
corpus also asserted that the part is composed of the whole. Three edge types
carried it: is_part_of, is_in_functional_unit, is_in_representation_model_group.

AP21i ranges strictly over A2 Stratigraphic Volume Unit, and only US maps to A2
here (USD and the virtual units map to A8, VSF to E89/E19), so the refinement is
declared under a guard and the generic P46i still goes out for every
containment.
"""

from pathlib import Path

import pytest

rdflib = pytest.importorskip("rdflib")

from s3dgraphy.graph import Graph
from s3dgraphy.nodes import (StratigraphicUnit, SpecialFindUnit,
                             VirtualSpecialFindUnit, ReusedSpecialFind)
from s3dgraphy.exporter.rdf_exporter import RDFExporter, _Datamodel

CRM = "http://www.cidoc-crm.org/cidoc-crm/"
CRMARCHAEO = "http://www.cidoc-crm.org/extensions/crmarchaeo/"
P46I = CRM + "P46i_forms_part_of"
P46 = CRM + "P46_is_composed_of"
AP21I = CRMARCHAEO + "AP21i_is_contained_in"


def _contained_in(container_cls, containee_cls, tmp_path, name="a.ttl"):
    g = Graph(graph_id="g")
    g.add_node(containee_cls(node_id="X", name="X", description=""))
    g.add_node(container_cls(node_id="C", name="C", description=""))
    g.add_edge("e", "X", "C", "is_part_of")
    out = tmp_path / name
    RDFExporter(str(out), format="turtle").export_single_graph(g)
    parsed = rdflib.Graph()
    parsed.parse(str(out), format="turtle")
    return {str(p) for s, p, o in parsed
            if str(s).endswith("/X") and str(o).endswith("/C")}


def test_a_find_inside_a_layer_is_contained_in_it(tmp_path):
    preds = _contained_in(StratigraphicUnit, SpecialFindUnit, tmp_path)
    assert AP21I in preds, "the CRMarchaeo refinement is the point of this edge"
    assert P46I in preds, "the generic projection stays, for CRM-only readers"


def test_the_inverse_is_not_asserted_alongside_it(tmp_path):
    # P46_is_composed_of with X as subject would say the find is composed of
    # the layer. It went out on every containment until 2026-09-25.
    assert P46 not in _contained_in(StratigraphicUnit, SpecialFindUnit, tmp_path)


def test_no_edge_type_declares_the_inverse_of_its_own_predicate():
    """The fault, stated once for every edge rather than for the three found."""
    dm = _Datamodel()
    offenders = []
    for name, entry in (dm.connections_datamodel.get("edge_types") or {}).items():
        m = entry.get("mapping") or {}
        core = (m.get("cidoc") or "").strip()
        ext = (m.get("extension_mapping") or "").split("(")[0].strip()
        if not core or not ext:
            continue
        core_code = core.replace(" ", "_").split("_")[0]
        ext_code = ext.replace(" ", "_").split("_")[0]
        if core_code != ext_code and core_code.rstrip("i") == ext_code.rstrip("i"):
            offenders.append((name, core, ext))
    assert not offenders, offenders


def test_the_refinement_is_withheld_where_its_range_does_not_hold(tmp_path):
    # Fragments inside a reconstructed whole: the container is a VSF
    # (E89/E19), not an A2, so AP21i would be range-inconsistent.
    preds = _contained_in(VirtualSpecialFindUnit, SpecialFindUnit, tmp_path, "b.ttl")
    assert P46I in preds
    assert AP21I not in preds


def test_spolia_can_be_attached_to_its_host_masonry():
    """RSF was missing from is_part_of's source list.

    The manual says "the host SU acts as container for the RSF" and the edge's
    own description cites a Special Find reused inside a wall, but the datamodel
    refused the connection — while allowing it in is_in_functional_unit, which
    is what showed the omission to be an oversight.
    """
    g = Graph(graph_id="g")
    g.add_node(ReusedSpecialFind(node_id="RSF1", name="RSF1", description=""))
    g.add_node(StratigraphicUnit(node_id="USM1", name="USM1", description=""))
    edge = g.add_edge("e", "RSF1", "USM1", "is_part_of")
    assert edge.edge_type == "is_part_of", (
        "a refused connection is silently rewritten as generic_connection")
