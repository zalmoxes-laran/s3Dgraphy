"""AUX-COMPLETE (2026-08-06, DP-61) — the source_list mapping type is registered
and its built-in mapping is discoverable + loadable, coherent with the existing
mapping style (emdb / pyarchinit / generic).
"""

from s3dgraphy.mappings.registry import MappingRegistry


def test_source_list_is_a_registered_mapping_type():
    reg = MappingRegistry()
    dirs = reg.get_mapping_directories("source_list")
    assert dirs, "source_list must have a built-in mapping directory"


def test_source_list_mapping_is_discoverable():
    reg = MappingRegistry()
    names = [m[0] for m in reg.list_available_mappings("source_list")]
    assert "source_list_mapping" in names


def test_source_list_mapping_loads_and_targets_documents():
    reg = MappingRegistry()
    m = reg.load_mapping("source_list_mapping", "source_list")
    assert m is not None
    cols = m["column_mappings"]
    # the ID column is the DocumentNode; TITLE is carried as a property
    assert cols["ID"]["node_type"] == "DocumentNode"
    assert cols["ID"].get("is_id") is True
    assert cols["TITLE"]["node_type"] == "PropertyNode"
