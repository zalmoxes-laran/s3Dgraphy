"""
Canvas generator for GraphML export.

Generates root XML structure with correct namespaces and key definitions.
"""

from lxml import etree as ET
from typing import Dict


class CanvasGenerator:
    """Generates GraphML canvas with namespaces and key definitions."""

    # Namespace definitions
    NS = {
        None: 'http://graphml.graphdrawing.org/xmlns',  # Default namespace
        'y': 'http://www.yworks.com/xml/graphml',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    def __init__(self):
        """Initialize canvas generator."""
        pass

    def generate_root(self) -> ET.Element:
        """
        Generate root GraphML element with namespaces and key definitions.

        Returns:
            Root element with complete structure
        """
        # Create root element with namespaces
        root = ET.Element(
            '{http://graphml.graphdrawing.org/xmlns}graphml',
            nsmap=self.NS,
            attrib={
                '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation':
                'http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd'
            }
        )

        # Add key definitions for NODES (d4-d8)
        self._add_node_keys(root)

        # Add key definitions for EDGES (d10-d12)
        self._add_edge_keys(root)

        # Add resources key (for SVG content)
        self._add_resources_key(root)

        # Add graph-level lossless key for the physical stratigraphic
        # relations side-channel (see graphml_exporter._write_physical_
        # relations for the rationale). yEd ignores unknown graph-level
        # keys and the round-trip parser preserves them opaquely, so
        # introducing this key has zero impact on the rendered matrix.
        self._add_physical_relations_key(root)

        # Add graph-level lossless key for the PropertyNode structured
        # metadata side-channel (value / property_type / units /
        # arbitrary attributes). Same yEd-ignored encoding pattern.
        self._add_property_metadata_key(root)

        # Create main graph element
        graph = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}graph')
        graph.set('id', 'G')
        graph.set('edgedefault', 'directed')

        return root

    def _add_node_keys(self, root: ET.Element):
        """Add key definitions for nodes (d4-d8, d13)."""
        # d4: url
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'url')
        key.set('attr.type', 'string')
        key.set('for', 'node')
        key.set('id', 'd4')

        # d5: description
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'description')
        key.set('attr.type', 'string')
        key.set('for', 'node')
        key.set('id', 'd5')

        # d6: nodegraphics (yfiles)
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('for', 'node')
        key.set('id', 'd6')
        key.set('{http://www.yworks.com/xml/yfiles-common/1.0/java}type', 'nodegraphics')
        key.set('yfiles.type', 'nodegraphics')

        # d7: EMID (UUID for nodes)
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'EMID')
        key.set('attr.type', 'string')
        key.set('for', 'node')
        key.set('id', 'd7')

        # d8: URI (for nodes)
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'URI')
        key.set('attr.type', 'string')
        key.set('for', 'node')
        key.set('id', 'd8')

        # d13: physical_relationships (EM 1.6 per-node packed string)
        #
        # Per-node serialisation of the canonical physical stratigraphic
        # edges, in the same list-of-lists Python-literal format used by
        # the pyArchInit ``us_table.rapporti`` column. yEd reserves edges
        # for the temporal Matrix layer, so the EM 1.6 palette surfaces
        # these relationships as a per-node attribute instead — visible
        # to humans editing the file in yEd, and byte-identical with the
        # pyArchInit column when the graph between them is unmutated.
        #
        # The exporter writes this attribute on every stratigraphic node
        # whose canonical edges include physical-stratigraphic types;
        # the importer reads it only when the richer graph-level JSON
        # side channel (``_s3d_physical_relations``) is absent. See
        # ``s3dgraphy.sync.rapporti`` for the canonical vocabulary.
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'physical_relationships')
        key.set('attr.type', 'string')
        key.set('for', 'node')
        key.set('id', 'd13')

    def _add_edge_keys(self, root: ET.Element):
        """Add key definitions for edges (d10-d12)."""
        # d10: edgegraphics (yfiles)
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('for', 'edge')
        key.set('id', 'd10')
        key.set('{http://www.yworks.com/xml/yfiles-common/1.0/java}type', 'edgegraphics')
        key.set('yfiles.type', 'edgegraphics')

        # d11: EMID (UUID for edges) - SEPARATE FROM NODES
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'EMID')
        key.set('attr.type', 'string')
        key.set('for', 'edge')
        key.set('id', 'd11')

        # d12: URI (for edges) - SEPARATE FROM NODES
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', 'URI')
        key.set('attr.type', 'string')
        key.set('for', 'edge')
        key.set('id', 'd12')

    def _add_resources_key(self, root: ET.Element):
        """Add resources key for SVG content."""
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('for', 'graphml')
        key.set('id', 'd9')
        key.set('yfiles.type', 'resources')

    # Stable ID used for the graph-level physical-relations key. Chosen
    # outside the d4..d12 range allocated to node/edge keys so the
    # existing GraphML id space stays untouched.
    PHYSICAL_RELATIONS_KEY_ID = "d_s3d_phys_rel"
    PHYSICAL_RELATIONS_ATTR_NAME = "_s3d_physical_relations"

    # Companion graph-level key for lossless storage of PropertyNode
    # metadata (value / property_type / units / arbitrary attributes).
    # yEd renders a PropertyNode's content from the description field
    # (d5), so without this side channel the unified-xlsx structured
    # qualia (value + units) get flattened into "value units" and
    # the structured form is lost on import. This key restores it.
    PROPERTY_METADATA_KEY_ID = "d_s3d_prop_meta"
    PROPERTY_METADATA_ATTR_NAME = "_s3d_property_metadata"

    def _add_physical_relations_key(self, root: ET.Element):
        """Declare the graph-level GraphML key for lossless storage of
        physical stratigraphic relations.

        The key is declared with ``for="graph"`` and a string-typed JSON
        payload, written next to the main ``<graph>`` element by
        :class:`GraphMLExporter`. The companion read side lives in
        ``importer/import_graphml.py``; legacy GraphML files without the
        key are handled gracefully (fall back to the Harris-minimal
        ``is_after`` set rendered in yEd).
        """
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', self.PHYSICAL_RELATIONS_ATTR_NAME)
        key.set('attr.type', 'string')
        key.set('for', 'graph')
        key.set('id', self.PHYSICAL_RELATIONS_KEY_ID)

    def _add_property_metadata_key(self, root: ET.Element):
        """Declare the graph-level GraphML key for lossless storage of
        PropertyNode structured metadata (value, property_type, units,
        and the per-node attributes dict).

        yEd encodes a PropertyNode's content via the description field
        only, which collapses ``value`` + ``attributes['units']`` into
        a single human-readable string and drops ``property_type``
        entirely. This side channel preserves the structured form so
        round-trips are lossless. Companion read side lives in
        ``importer/import_graphml.py``; legacy GraphML files without
        the key parse normally (PropertyNodes keep whatever the d5
        description carries).
        """
        key = ET.SubElement(root, '{http://graphml.graphdrawing.org/xmlns}key')
        key.set('attr.name', self.PROPERTY_METADATA_ATTR_NAME)
        key.set('attr.type', 'string')
        key.set('for', 'graph')
        key.set('id', self.PROPERTY_METADATA_KEY_ID)

    def generate_svg_resources(self) -> ET.Element:
        """
        Generate SVG resources section for paradata node icons.

        Resource IDs match the TempluMare reference:
        - id="1": Extractor node (D.XX.YY) — half-grey/half-white circle with square
        - id="2": Combiner node (C.XX) — white circle with grey arrows
        - id="3": Continuity node (_continuity) — small rotated square (diamond)

        Returns:
            Resources data element with SVG content
        """
        data = ET.Element('{http://graphml.graphdrawing.org/xmlns}data')
        data.set('key', 'd9')

        resources = ET.SubElement(data, '{http://www.yworks.com/xml/graphml}Resources')

        # SVG Resource 1: Extractor node (D.) — half-grey circle with square
        resource1 = ET.SubElement(resources, '{http://www.yworks.com/xml/graphml}Resource')
        resource1.set('id', '1')
        resource1.text = self._get_extractor_svg()

        # SVG Resource 2: Combiner node (C.) — white circle with arrows
        resource2 = ET.SubElement(resources, '{http://www.yworks.com/xml/graphml}Resource')
        resource2.set('id', '2')
        resource2.text = self._get_combiner_svg()

        # SVG Resource 3: Continuity node (BR) — rotated square (diamond)
        resource3 = ET.SubElement(resources, '{http://www.yworks.com/xml/graphml}Resource')
        resource3.set('id', '3')
        resource3.text = self._get_continuity_svg()

        return data

    def _get_extractor_svg(self) -> str:
        """SVG content for extractor node (D.) — from TempluMare reference id=1.

        Visual: Circle with left half grey (#7d7d7d), right half white,
        grey square in center. Created with Inkscape.
        """
        return '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!-- Created with Inkscape (http://www.inkscape.org/) -->

<svg
   xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmlns:cc="http://creativecommons.org/ns#"
   xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
   xmlns:svg="http://www.w3.org/2000/svg"
   xmlns="http://www.w3.org/2000/svg"
   xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
   width="48px"
   height="48px"
   id="svg4050"
   version="1.1"
   inkscape:version="0.48.4 r9939"
   sodipodi:docname="New document 13">
  <defs
     id="defs4052" />
  <sodipodi:namedview
     id="base"
     pagecolor="#ffffff"
     bordercolor="#666666"
     borderopacity="1.0"
     inkscape:pageopacity="0.0"
     inkscape:pageshadow="2"
     inkscape:zoom="9.8994949"
     inkscape:cx="18.095997"
     inkscape:cy="17.278115"
     inkscape:current-layer="layer1"
     showgrid="true"
     inkscape:grid-bbox="true"
     inkscape:document-units="px"
     inkscape:window-width="1920"
     inkscape:window-height="1025"
     inkscape:window-x="-2"
     inkscape:window-y="-3"
     inkscape:window-maximized="1" />
  <metadata
     id="metadata4055">
    <rdf:RDF>
      <cc:Work
         rdf:about="">
        <dc:format>image/svg+xml</dc:format>
        <dc:type
           rdf:resource="http://purl.org/dc/dcmitype/StillImage" />
        <dc:title></dc:title>
      </cc:Work>
    </rdf:RDF>
  </metadata>
  <g
     id="layer1"
     inkscape:label="Layer 1"
     inkscape:groupmode="layer">
    <g
       transform="matrix(0.41470954,0,0,0.41438764,-58.075087,96.197996)"
       id="g3932">
      <path
         transform="translate(-176.7767,-1080.8632)"
         d="m 430.32499,906.90021 c 0,30.68405 -24.87434,55.55839 -55.55839,55.55839 -30.68405,0 -55.55839,-24.87434 -55.55839,-55.55839 0,-30.68405 24.87434,-55.55839 55.55839,-55.55839 30.68405,0 55.55839,24.87434 55.55839,55.55839 z"
         sodipodi:ry="55.558392"
         sodipodi:rx="55.558392"
         sodipodi:cy="906.90021"
         sodipodi:cx="374.7666"
         id="path2996-3"
         style="fill:#ffffff;fill-opacity:1;stroke:#000000;stroke-width:4;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:4;stroke-opacity:1;stroke-dasharray:none;stroke-dashoffset:0"
         sodipodi:type="arc" />
      <path
         inkscape:connector-curvature="0"
         id="path3795"
         d="m 195.82737,-229.48049 c -29.75104,1.0602 -53.53125,25.52148 -53.53125,55.53125 0,30.00977 23.78021,54.4398 53.53125,55.5 l 0,-38.875 -18.1875,0 0,-32.8125 18.1875,0 0,-39.34375 z"
         style="fill:#7d7d7d;fill-opacity:1;stroke:#000000;stroke-width:4;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:4;stroke-opacity:1;stroke-dasharray:none;stroke-dashoffset:0" />
      <rect
         y="-187.49332"
         x="212.49696"
         height="27.142857"
         width="26.071428"
         id="rect3805"
         style="fill:#7d7d7d;fill-opacity:1;stroke:#000000;stroke-width:4;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:4;stroke-opacity:1;stroke-dasharray:none;stroke-dashoffset:0" />
      <path
         inkscape:connector-curvature="0"
         id="path3807"
         d="m 180.35416,-173.20759 c 29.28571,0 29.28571,0 29.28571,0"
         style="fill:none;stroke:#000000;stroke-width:1px;stroke-linecap:butt;stroke-linejoin:miter;stroke-opacity:1" />
    </g>
  </g>
</svg>'''

    def _get_combiner_svg(self) -> str:
        """SVG content for combiner node (C.) — from TempluMare reference id=2.

        Visual: White circle with two grey arrows pointing inward.
        Created with Inkscape.
        """
        return '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!-- Created with Inkscape (http://www.inkscape.org/) -->

<svg
   xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmlns:cc="http://creativecommons.org/ns#"
   xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
   xmlns:svg="http://www.w3.org/2000/svg"
   xmlns="http://www.w3.org/2000/svg"
   xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
   width="48px"
   height="48px"
   id="svg4192"
   version="1.1"
   inkscape:version="0.48.4 r9939"
   sodipodi:docname="New document 20">
  <defs
     id="defs4194" />
  <sodipodi:namedview
     id="base"
     pagecolor="#ffffff"
     bordercolor="#666666"
     borderopacity="1.0"
     inkscape:pageopacity="0.0"
     inkscape:pageshadow="2"
     inkscape:zoom="14"
     inkscape:cx="24.612064"
     inkscape:cy="28.768962"
     inkscape:current-layer="layer1"
     showgrid="true"
     inkscape:grid-bbox="true"
     inkscape:document-units="px"
     inkscape:window-width="1920"
     inkscape:window-height="1025"
     inkscape:window-x="-2"
     inkscape:window-y="-3"
     inkscape:window-maximized="1" />
  <metadata
     id="metadata4197">
    <rdf:RDF>
      <cc:Work
         rdf:about="">
        <dc:format>image/svg+xml</dc:format>
        <dc:type
           rdf:resource="http://purl.org/dc/dcmitype/StillImage" />
        <dc:title></dc:title>
      </cc:Work>
    </rdf:RDF>
  </metadata>
  <g
     id="layer1"
     inkscape:label="Layer 1"
     inkscape:groupmode="layer">
    <g
       transform="matrix(0.40828104,0,0,0.41346794,-201.56174,97.998396)"
       id="g3922">
      <path
         sodipodi:type="arc"
         style="fill:#ffffff;fill-opacity:1;stroke:#000000;stroke-width:4;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:4;stroke-opacity:1;stroke-dasharray:none;stroke-dashoffset:0"
         id="path3912"
         sodipodi:cx="374.7666"
         sodipodi:cy="906.90021"
         sodipodi:rx="55.558392"
         sodipodi:ry="55.558392"
         d="m 430.32499,906.90021 c 0,30.68405 -24.87434,55.55839 -55.55839,55.55839 -30.68405,0 -55.55839,-24.87434 -55.55839,-55.55839 0,-30.68405 24.87434,-55.55839 55.55839,-55.55839 30.68405,0 55.55839,24.87434 55.55839,55.55839 z"
         transform="translate(177.55723,-1085.7479)" />
      <path
         sodipodi:nodetypes="ccsccc"
         inkscape:connector-curvature="0"
         id="path3914"
         d="m 543.53146,-169.98986 63.36579,-17.50001 c 0,0 0.71429,3.97312 0.71429,11.68875 0,7.71563 -2.93748,15.70661 -2.93748,15.70661 l -61.1426,17.05358 z"
         style="fill:#7b7b7b;fill-opacity:1;stroke:#000000;stroke-width:4;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:4;stroke-opacity:1;stroke-dasharray:none;stroke-dashoffset:0" />
      <path
         sodipodi:nodetypes="ccccsc"
         inkscape:connector-curvature="0"
         id="path3916"
         d="m 501.52478,-201.54471 54.88091,-14.27148 0,26.94893 -59.23348,15.97426 c 0,0 -0.15898,-6.266 0.10274,-12.48413 0.34368,-8.16509 4.24983,-16.16758 4.24983,-16.16758 z"
         style="fill:#7b7b7b;fill-opacity:1;stroke:#000000;stroke-width:4;stroke-linecap:round;stroke-linejoin:round;stroke-miterlimit:4;stroke-opacity:1;stroke-dasharray:none;stroke-dashoffset:0" />
    </g>
  </g>
</svg>'''

    def _get_continuity_svg(self) -> str:
        """SVG content for continuity node (BR) — from TempluMare reference id=3.

        Visual: Small square rotated 45 degrees (diamond shape).
        Created with Inkscape.
        """
        return '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!-- Created with Inkscape (http://www.inkscape.org/) -->

<svg
   xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmlns:cc="http://creativecommons.org/ns#"
   xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
   xmlns:svg="http://www.w3.org/2000/svg"
   xmlns="http://www.w3.org/2000/svg"
   xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
   width="7mm"
   height="7mm"
   viewBox="0 0 7 7"
   version="1.1"
   id="svg8"
   inkscape:version="0.92.2 5c3e80d, 2017-08-06"
   sodipodi:docname="continuity.svg">
  <defs
     id="defs2" />
  <sodipodi:namedview
     id="base"
     pagecolor="#ffffff"
     bordercolor="#666666"
     borderopacity="1.0"
     inkscape:pageopacity="0.0"
     inkscape:pageshadow="2"
     inkscape:zoom="1.8181416"
     inkscape:cx="-10.002405"
     inkscape:cy="-64.860066"
     inkscape:document-units="mm"
     inkscape:current-layer="layer1"
     showgrid="false"
     fit-margin-top="0"
     fit-margin-left="0"
     fit-margin-right="0"
     fit-margin-bottom="0"
     inkscape:window-width="1440"
     inkscape:window-height="800"
     inkscape:window-x="0"
     inkscape:window-y="1"
     inkscape:window-maximized="1" />
  <metadata
     id="metadata5">
    <rdf:RDF>
      <cc:Work
         rdf:about="">
        <dc:format>image/svg+xml</dc:format>
        <dc:type
           rdf:resource="http://purl.org/dc/dcmitype/StillImage" />
        <dc:title></dc:title>
      </cc:Work>
    </rdf:RDF>
  </metadata>
  <g
     inkscape:label="Livello 1"
     inkscape:groupmode="layer"
     id="layer1"
     transform="translate(-82.089519,-139.87478)">
    <rect
       id="rect12"
       width="4.9497476"
       height="4.9497476"
       x="159.42734"
       y="38.385479"
       style="stroke-width:0.01220008"
       transform="rotate(45)" />
  </g>
</svg>'''
