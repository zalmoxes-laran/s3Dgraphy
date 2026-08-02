"""C1 — the explicit ``_s3d_node_type:`` marker, honoured beyond image nodes.

Extractors and combiners could only ever be recognised by their label prefix
(``D.`` / ``C.``). That prefix is a naming convention, not a type: an old EM
graph whose author named an extractor after the unit it reads from — ``SF04.2``
— drew a perfectly unambiguous extractor icon and still imported as an untyped
node, dragging every edge that touched it down to ``generic_connection``.

The marker already existed as a concept (the GraphML exporter writes it, and
the paradata-image path read it). C1 lets the extractor, combiner and
continuity paths read it too, so the EMTools converter can state outright what
the icon says. The marker is consulted ONLY after the existing heuristics have
failed, so nothing that used to resolve can change.
"""

import io
import contextlib

import pytest

from s3dgraphy.graph import Graph
from s3dgraphy.importer.import_graphml import GraphMLImporter

G = "http://graphml.graphdrawing.org/xmlns"
Y = "http://www.yworks.com/xml/graphml"

_TEMPLATE = """<?xml version='1.0' encoding='UTF-8'?>
<graphml xmlns="{g}" xmlns:y="{y}">
  <key for="node" attr.name="url" attr.type="string" id="d4"/>
  <key for="node" attr.name="description" attr.type="string" id="d5"/>
  <key for="node" id="d6" yfiles.type="nodegraphics"/>
  <graph edgedefault="directed" id="G">
{nodes}
  </graph>
</graphml>
"""

_NODE = """    <node id="{nid}">
      <data key="d5">{desc}</data>
      <data key="d6">
        <y:SVGNode>
          <y:Geometry height="25.0" width="25.0" x="{x}" y="10.0"/>
          <y:Fill color="#CCCCFF" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel>{label}</y:NodeLabel>
          <y:SVGModel svgBoundsPolicy="0"><y:SVGContent refid="2"/></y:SVGModel>
        </y:SVGNode>
      </data>
    </node>"""


def graphml(*nodes):
    body = "\n".join(
        _NODE.format(nid=f"n{i}", label=label, desc=desc, x=i * 100)
        for i, (label, desc) in enumerate(nodes)
    )
    return _TEMPLATE.format(g=G, y=Y, nodes=body)


def parse(text, tmp_path):
    path = tmp_path / "t.graphml"
    path.write_text(text, encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return GraphMLImporter(str(path), Graph(graph_id="g")).parse()


def only_node(graph):
    # the importer auto-creates a geo_position node; ignore it
    nodes = [n for n in graph.nodes if n.node_type != "geo_position"]
    assert len(nodes) == 1, [(n.name, type(n).__name__) for n in nodes]
    return nodes[0]


# ── the gap C1 closes ─────────────────────────────────────────────────────────

def test_without_the_marker_a_misnamed_extractor_stays_untyped(tmp_path):
    """The state of the world before C1 — kept as a test so the gap is on
    record and the fix below is demonstrably a fix."""
    graph = parse(graphml(("SF04.2", "colore dell'intonaco")), tmp_path)
    assert type(only_node(graph)).__name__ == "Node"


@pytest.mark.parametrize("declared,expected", [
    ("ExtractorNode", "ExtractorNode"),
    ("CombinerNode", "CombinerNode"),
    ("ContinuityNode", "ContinuityNode"),
])
def test_the_marker_types_a_node_the_label_cannot(tmp_path, declared, expected):
    text = graphml(("SF04.2", f"colore dell'intonaco _s3d_node_type:{declared}"))
    node = only_node(parse(text, tmp_path))
    assert type(node).__name__ == expected


def test_the_authors_name_is_kept(tmp_path):
    """Typing the node must not rename it: `SF04.2` is what the author called
    this extractor, and that is data."""
    text = graphml(("SF04.2", "colore _s3d_node_type:ExtractorNode"))
    assert only_node(parse(text, tmp_path)).name == "SF04.2"


def test_the_marker_does_not_leak_into_the_description(tmp_path):
    """It is machinery, not prose — the author must never read it in a UI."""
    text = graphml(("SF04.2", "colore dell'intonaco _s3d_node_type:ExtractorNode"))
    node = only_node(parse(text, tmp_path))
    assert "_s3d_node_type" not in (node.description or "")
    assert node.description == "colore dell'intonaco"


def test_a_marker_only_description_leaves_an_empty_description(tmp_path):
    text = graphml(("", "_s3d_node_type:ExtractorNode"))
    node = only_node(parse(text, tmp_path))
    assert type(node).__name__ == "ExtractorNode"
    assert not node.description


# ── it must not disturb what already worked ───────────────────────────────────

def test_the_label_convention_still_wins_on_its_own(tmp_path):
    graph = parse(graphml(("D.01.2", "impasto e colore")), tmp_path)
    assert type(only_node(graph)).__name__ == "ExtractorNode"


def test_an_unmarked_unconventional_node_is_still_reported(tmp_path):
    """No marker, no convention → untyped, with the warning that tells the
    author to classify it. C1 must not silently start guessing."""
    graph = parse(graphml(("USR2170.1", "una descrizione")), tmp_path)
    assert type(only_node(graph)).__name__ == "Node"
    assert any("no recognised EM type" in w for w in graph.warnings)
