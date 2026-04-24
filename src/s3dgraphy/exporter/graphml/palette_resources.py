"""Palette resource loader for the GraphML exporter.

Reads ``templates/em_palette_template.graphml`` once at import time and
exposes, per paradata image node type (AuthorNode, AuthorAINode,
LicenseNode, EmbargoNode):

- the label prefix (``A.`` / ``AI.`` / ``LI.`` / ``EB.``) — matches
  ``JSON_config/em_palette_icons.json``;
- the ``<y:Resource>`` payload (PNG/SVG base64) copied verbatim from the
  palette, indexed by the refid used inside the template;
- a sample ``<y:ImageNode>`` element that can be used as a layout stencil
  when a concrete geometry is not available.

Changing an icon in yEd therefore requires **no Python change**: just
re-save ``em_palette_template.graphml`` and the new payload flows through
to every exporter run.

This module intentionally avoids hashing or otherwise fingerprinting the
payload — label prefix remains the stable identity.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


_Y_NS = "http://www.yworks.com/xml/graphml"
_G_NS = "http://graphml.graphdrawing.org/xmlns"

_PALETTE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "templates",
    "em_palette_template.graphml",
)

# Label prefix → canonical s3Dgraphy node class name. Mirrors
# JSON_config/em_palette_icons.json at the exporter side so we do not have
# to load JSON twice.
_LABEL_PREFIX_TO_NODE_TYPE: Dict[str, str] = {
    "AI.": "AuthorAINode",
    "A.":  "AuthorNode",
    "LI.": "LicenseNode",
    "EB.": "EmbargoNode",
}


@dataclass(frozen=True)
class PaletteEntry:
    """One palette icon entry discovered in the template."""

    node_type: str              # e.g. "AuthorNode"
    label_prefix: str           # e.g. "A."
    template_refid: str         # the refid used INSIDE the palette template
    resource_xml: str           # serialized <y:Resource ...>...</y:Resource>
    sample_imagenode_xml: str   # serialized <y:ImageNode>...</y:ImageNode>


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------

def _serialize(elem: ET.Element) -> str:
    """Return an element serialized to the y:* default namespace."""
    return ET.tostring(elem, encoding="unicode")


def _iter_image_nodes(tree: ET.ElementTree):
    for node in tree.iter(f"{{{_Y_NS}}}ImageNode"):
        yield node


def _label_text(image_node: ET.Element) -> str:
    label = image_node.find(f"{{{_Y_NS}}}NodeLabel")
    return (label.text or "").strip() if label is not None else ""


def _image_refid(image_node: ET.Element) -> Optional[str]:
    image = image_node.find(f"{{{_Y_NS}}}Image")
    if image is None:
        return None
    return image.attrib.get("refid")


def _resources_map(tree: ET.ElementTree) -> Dict[str, ET.Element]:
    """{refid → <y:Resource> element}"""
    return {
        r.attrib.get("id"): r
        for r in tree.iter(f"{{{_Y_NS}}}Resource")
        if r.attrib.get("id")
    }


def _longest_prefix_first() -> List[str]:
    # "AI." before "A." so the lookup does not collapse.
    return sorted(_LABEL_PREFIX_TO_NODE_TYPE.keys(), key=len, reverse=True)


def _match_prefix(label: str) -> Optional[str]:
    for p in _longest_prefix_first():
        if label.startswith(p):
            return p
    return None


def _load_palette() -> Dict[str, PaletteEntry]:
    """Parse ``em_palette_template.graphml`` and build the entry map.

    Returns an empty dict if the template is missing — the exporter will
    still function for non-paradata node types; only the 4 new image
    nodes would be impossible to emit.
    """
    if not os.path.exists(_PALETTE_PATH):
        return {}

    tree = ET.parse(_PALETTE_PATH)
    resources = _resources_map(tree)

    entries: Dict[str, PaletteEntry] = {}
    for image_node in _iter_image_nodes(tree):
        label = _label_text(image_node)
        prefix = _match_prefix(label)
        if prefix is None:
            continue
        node_type = _LABEL_PREFIX_TO_NODE_TYPE[prefix]
        if node_type in entries:
            # First winner wins (palette usually has 1 sample per type).
            continue
        refid = _image_refid(image_node)
        if refid is None or refid not in resources:
            continue

        entries[node_type] = PaletteEntry(
            node_type=node_type,
            label_prefix=prefix,
            template_refid=refid,
            resource_xml=_serialize(resources[refid]),
            sample_imagenode_xml=_serialize(image_node),
        )
    return entries


# Loaded once at import time.
_PALETTE_ENTRIES: Dict[str, PaletteEntry] = _load_palette()


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def get_palette_entry(node_type: str) -> Optional[PaletteEntry]:
    """Return the PaletteEntry for a paradata node class name, or None."""
    return _PALETTE_ENTRIES.get(node_type)


def get_palette_entries() -> Dict[str, PaletteEntry]:
    return dict(_PALETTE_ENTRIES)


def has_palette() -> bool:
    return bool(_PALETTE_ENTRIES)


def label_prefix_for(node_type: str) -> Optional[str]:
    entry = _PALETTE_ENTRIES.get(node_type)
    return entry.label_prefix if entry else None


def all_paradata_node_types() -> Iterable[str]:
    return sorted(_PALETTE_ENTRIES.keys())


def resource_xml_for(node_type: str) -> Optional[str]:
    entry = _PALETTE_ENTRIES.get(node_type)
    return entry.resource_xml if entry else None


def template_refid_for(node_type: str) -> Optional[str]:
    entry = _PALETTE_ENTRIES.get(node_type)
    return entry.template_refid if entry else None


def palette_path() -> str:
    return _PALETTE_PATH


def reload_palette():
    """Re-read the palette template (for tests or hot-reloading)."""
    global _PALETTE_ENTRIES
    _PALETTE_ENTRIES = _load_palette()
