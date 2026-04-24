"""Generator for paradata image nodes (Author / AuthorAI / License / Embargo).

Produces ``<node>`` elements that yEd renders as image-tagged paradata
nodes. Each generated node carries:

- a ``<y:ImageNode>`` with the label prefix from the palette
  (``A.``/``AI.``/``LI.``/``EB.``) and a ``<y:Image refid="N"/>`` where
  ``N`` is the refid the *host file* uses for the icon resource;
- a ``_s3d_node_type:<NodeType>`` marker in the description so the
  importer can round-trip the node even if the palette is stripped.

The caller is responsible for making sure the referenced ``<y:Resource>``
is present in the file's ``<y:Resources>`` section. The companion helper
:func:`ensure_resources_in_file` (in :mod:`palette_resources` / exporter
flow) handles that upstream.
"""

from __future__ import annotations

from typing import Optional
from lxml import etree as ET

from . import palette_resources


_Y_NS = "http://www.yworks.com/xml/graphml"
_GFX_KEY_FOR = {  # data keys for node graphics/description — aligned with existing generators
    "nodegraphics": "d6",
    "description":  "d5",
    "emid":         "d11",
}


class ParadataImageNodeGenerator:
    """Generate <node> XML for AuthorNode / AuthorAINode / LicenseNode /
    EmbargoNode.
    """

    YFILES_NS = _Y_NS

    # ------------------------------------------------------------------
    # Individual generators (one per class), all delegating to _build()
    # ------------------------------------------------------------------

    def generate_author_node(self, node_id: str, display_name: str,
                             description: Optional[str] = None,
                             x: float = 0.0, y: float = 0.0,
                             refid: Optional[str] = None,
                             emid: Optional[str] = None) -> ET.Element:
        return self._build("AuthorNode", node_id, display_name,
                           description, x, y, refid, emid)

    def generate_author_ai_node(self, node_id: str, display_name: str,
                                description: Optional[str] = None,
                                x: float = 0.0, y: float = 0.0,
                                refid: Optional[str] = None,
                                emid: Optional[str] = None) -> ET.Element:
        return self._build("AuthorAINode", node_id, display_name,
                           description, x, y, refid, emid)

    def generate_license_node(self, node_id: str, display_name: str,
                              description: Optional[str] = None,
                              x: float = 0.0, y: float = 0.0,
                              refid: Optional[str] = None,
                              emid: Optional[str] = None) -> ET.Element:
        return self._build("LicenseNode", node_id, display_name,
                           description, x, y, refid, emid)

    def generate_embargo_node(self, node_id: str, display_name: str,
                              description: Optional[str] = None,
                              x: float = 0.0, y: float = 0.0,
                              refid: Optional[str] = None,
                              emid: Optional[str] = None) -> ET.Element:
        return self._build("EmbargoNode", node_id, display_name,
                           description, x, y, refid, emid)

    # ------------------------------------------------------------------
    # Dispatch helper (callers can use this directly)
    # ------------------------------------------------------------------

    def generate_from_node(self, s3d_node, node_id_override: Optional[str] = None,
                           x: float = 0.0, y: float = 0.0,
                           refid: Optional[str] = None) -> Optional[ET.Element]:
        """Dispatch by the s3Dgraphy node class. Returns None for
        unsupported types.
        """
        cls = s3d_node.__class__.__name__
        node_id = node_id_override or s3d_node.node_id
        name = getattr(s3d_node, "name", None) or cls
        description = getattr(s3d_node, "description", "") or ""
        emid = None  # Callers can override via node.attributes if they need

        fn = {
            "AuthorNode":   self.generate_author_node,
            "AuthorAINode": self.generate_author_ai_node,
            "LicenseNode":  self.generate_license_node,
            "EmbargoNode":  self.generate_embargo_node,
        }.get(cls)
        if fn is None:
            return None
        return fn(node_id=node_id, display_name=name,
                  description=description, x=x, y=y, refid=refid,
                  emid=emid)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build(self, node_type: str, node_id: str, display_name: str,
               description: Optional[str], x: float, y: float,
               refid: Optional[str], emid: Optional[str]) -> ET.Element:
        entry = palette_resources.get_palette_entry(node_type)
        if entry is None:
            raise RuntimeError(
                f"No palette entry for {node_type}. Ensure "
                f"em_palette_template.graphml is present and contains an "
                f"ImageNode labelled with the expected prefix."
            )

        # Use the template refid as default — caller should override to
        # the refid that the *destination* file actually uses.
        effective_refid = str(refid) if refid is not None else str(entry.template_refid)

        label_text = self._compose_label(entry.label_prefix, display_name)
        description_with_marker = self._compose_description(node_type, description)

        node = ET.Element("node", id=node_id)

        # EMID (optional — aligns with existing generators' convention).
        if emid:
            emid_data = ET.SubElement(node, "data", key=_GFX_KEY_FOR["emid"])
            emid_data.text = emid

        # Description (d5) — carries the round-trip marker.
        desc_data = ET.SubElement(node, "data", key=_GFX_KEY_FOR["description"])
        desc_data.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        desc_data.text = description_with_marker

        # Graphics (d6) — an ImageNode with the label prefix + image refid.
        gfx_data = ET.SubElement(node, "data", key=_GFX_KEY_FOR["nodegraphics"])
        image_node = ET.SubElement(gfx_data, "{%s}ImageNode" % self.YFILES_NS)

        geometry = ET.SubElement(image_node, "{%s}Geometry" % self.YFILES_NS)
        geometry.set("height", "25.0")
        geometry.set("width", "25.0")
        geometry.set("x", str(x))
        geometry.set("y", str(y))

        fill = ET.SubElement(image_node, "{%s}Fill" % self.YFILES_NS)
        fill.set("color", "#CCCCFF")
        fill.set("transparent", "false")

        border = ET.SubElement(image_node, "{%s}BorderStyle" % self.YFILES_NS)
        border.set("color", "#000000")
        border.set("type", "line")
        border.set("width", "1.0")

        label = ET.SubElement(image_node, "{%s}NodeLabel" % self.YFILES_NS)
        for k, v in (
            ("alignment", "center"),
            ("autoSizePolicy", "content"),
            ("borderDistance", "0.0"),
            ("fontFamily", "Dialog"),
            ("fontSize", "12"),
            ("fontStyle", "plain"),
            ("hasBackgroundColor", "false"),
            ("hasLineColor", "false"),
            ("height", "18.1328125"),
            ("horizontalTextPosition", "center"),
            ("iconTextGap", "4"),
            ("modelName", "corners"),
            ("modelPosition", "nw"),
            ("textColor", "#000000"),
            ("underlinedText", "true" if node_type != "AuthorNode" else "false"),
            ("verticalTextPosition", "bottom"),
            ("visible", "true"),
            ("x", "-25.0"),
            ("y", "-18.1328125"),
        ):
            label.set(k, v)
        label.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        label.text = label_text

        image = ET.SubElement(image_node, "{%s}Image" % self.YFILES_NS)
        image.set("refid", effective_refid)

        return node

    @staticmethod
    def _compose_label(prefix: str, display_name: str) -> str:
        display_name = (display_name or "").strip()
        if not display_name:
            return prefix
        if display_name.startswith(prefix):
            # avoid "A. A. Name" when name was already prefixed
            return display_name
        return f"{prefix} {display_name}"

    @staticmethod
    def _compose_description(node_type: str, description: Optional[str]) -> str:
        marker = f"_s3d_node_type:{node_type}"
        if not description:
            return marker
        if marker in description:
            return description
        # Keep user text first, marker on its own line at the end.
        return f"{description}\n{marker}"
