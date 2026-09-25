"""Guard: no class may occupy another class's slot in ``Node.node_type_map``.

``__init_subclass__`` reads ``cls.__dict__`` rather than ``getattr`` precisely
so that an abstract intermediate class — one that declares no ``node_type`` of
its own — does not register itself under the name it inherits and silently
replace its parent in the map. ``VirtualStratigraphicUnit`` did exactly that
until 2026-09-25: every node serialised as ``StratigraphicNode`` came back as a
virtual unit, whose class name the node datamodel does not know, so the RDF
exporter found no mapping and emitted the node with NO ``rdf:type`` at all.
Nothing in the suite noticed, which is why this file exists.

The second test is the consequence, stated where a reader will see it: every
name in the map must resolve to a class the node datamodel declares, or the
RDF projection of that node type is empty.
"""
import json
from pathlib import Path

from s3dgraphy.nodes.base_node import Node
import s3dgraphy.nodes  # noqa: F401  — registers every subclass

CONFIG = Path(s3dgraphy.nodes.__file__).resolve().parent.parent / "JSON_config"


def test_every_registered_class_declares_its_own_node_type():
    wrong = {
        name: cls.__name__
        for name, cls in Node.node_type_map.items()
        if "node_type" not in cls.__dict__
    }
    assert not wrong, (
        "these classes registered under a node_type they only INHERIT, "
        "shadowing the class that declares it: " + repr(wrong)
    )


def test_every_registered_class_is_known_to_the_node_datamodel():
    with open(CONFIG / "s3Dgraphy_node_datamodel.json", encoding="utf-8") as fh:
        doc = json.load(fh)

    declared = set()

    def walk(entries):
        for key, entry in entries.items():
            if key.startswith("_") or not isinstance(entry, dict):
                continue
            if isinstance(entry.get("class"), str):
                declared.add(entry["class"])
            if isinstance(entry.get("subtypes"), dict):
                walk(entry["subtypes"])

    for section in doc.values():
        if isinstance(section, dict):
            walk(section)

    missing = sorted(
        cls.__name__ for cls in Node.node_type_map.values()
        if cls.__name__ not in declared
    )
    assert not missing, (
        "authorable node classes the node datamodel does not declare — the RDF "
        "exporter has no mapping for them and emits no rdf:type: "
        + repr(missing)
    )
