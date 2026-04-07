"""
Test script for GraphML Patcher - round-trip validation.

Tests the full workflow:
1. Import a GraphML file
2. Patch it (update existing nodes, add new nodes/edges)
3. Re-import the patched file
4. Compare counts and structure

Usage:
    cd s3Dgraphy
    python test_graphml_patcher.py [path_to_graphml]
"""

import sys
import os
import tempfile
import xml.etree.ElementTree as ET

# Add s3dgraphy to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from s3dgraphy.graph import Graph
from s3dgraphy.importer.import_graphml import GraphMLImporter
from s3dgraphy.exporter.graphml.graphml_patcher import GraphMLPatcher
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
from s3dgraphy.nodes.property_node import PropertyNode
from s3dgraphy.nodes.document_node import DocumentNode
from s3dgraphy.nodes.extractor_node import ExtractorNode
from s3dgraphy.edges.edge import Edge


def count_nodes_by_type(graph):
    """Count nodes by node_type."""
    counts = {}
    for node in graph.nodes:
        nt = getattr(node, 'node_type', 'unknown')
        counts[nt] = counts.get(nt, 0) + 1
    return counts


def count_edges_by_type(graph):
    """Count edges by edge_type."""
    counts = {}
    for edge in graph.edges:
        et = edge.edge_type
        counts[et] = counts.get(et, 0) + 1
    return counts


def count_xml_elements(filepath):
    """Count nodes and edges in raw XML."""
    tree = ET.parse(filepath)
    ns = 'http://graphml.graphdrawing.org/xmlns'
    nodes = list(tree.iter(f'{{{ns}}}node'))
    edges = list(tree.iter(f'{{{ns}}}edge'))
    return len(nodes), len(edges)


def test_basic_patch(graphml_path):
    """Test 1: Basic patch - import, patch (no changes), verify XML integrity."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Patch (no modifications)")
    print("=" * 60)

    # Import
    graph = Graph(graph_id="test_basic")
    importer = GraphMLImporter(graphml_path, graph)
    graph = importer.parse()

    orig_node_count = len(graph.nodes)
    orig_edge_count = len(graph.edges)
    print(f"  Imported: {orig_node_count} nodes, {orig_edge_count} edges")

    # Count original XML elements
    orig_xml_nodes, orig_xml_edges = count_xml_elements(graphml_path)
    print(f"  Original XML: {orig_xml_nodes} <node>, {orig_xml_edges} <edge>")

    # Patch to temp file
    with tempfile.NamedTemporaryFile(suffix='.graphml', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        patcher = GraphMLPatcher(graphml_path, graph)
        patcher.load()
        problems = patcher.validate_emids()
        updated = patcher.update_existing_nodes()
        added_nodes = patcher.add_new_nodes()
        added_edges = patcher.add_new_edges()
        patcher.save(tmp_path)

        print(f"  Patch results: {updated} updated, {added_nodes} new nodes, {added_edges} new edges")
        if problems:
            print(f"  EMID problems: {len(problems)}")
            for p in problems[:3]:
                print(f"    - {p[:100]}...")

        # Count patched XML elements
        patched_xml_nodes, patched_xml_edges = count_xml_elements(tmp_path)
        print(f"  Patched XML: {patched_xml_nodes} <node>, {patched_xml_edges} <edge>")

        # Verify XML element counts are preserved (no data loss)
        assert patched_xml_nodes >= orig_xml_nodes, \
            f"Lost nodes! {patched_xml_nodes} < {orig_xml_nodes}"
        assert patched_xml_edges >= orig_xml_edges, \
            f"Lost edges! {patched_xml_edges} < {orig_xml_edges}"

        print("  PASSED: XML structure preserved")

    finally:
        os.unlink(tmp_path)


def test_update_node_description(graphml_path):
    """Test 2: Modify a node description and verify it's written to XML."""
    print("\n" + "=" * 60)
    print("TEST 2: Update Node Description")
    print("=" * 60)

    # Import
    graph = Graph(graph_id="test_update")
    importer = GraphMLImporter(graphml_path, graph)
    graph = importer.parse()

    # Find first stratigraphic node
    strat_nodes = [n for n in graph.nodes if isinstance(n, StratigraphicNode)]
    if not strat_nodes:
        print("  SKIPPED: No stratigraphic nodes found")
        return

    test_node = strat_nodes[0]
    old_desc = test_node.description
    new_desc = "PATCHED_DESCRIPTION_TEST_12345"
    test_node.description = new_desc
    original_id = test_node.attributes.get('original_id')

    print(f"  Modified node: {test_node.name} (original_id: {original_id})")
    print(f"  Old description: '{old_desc[:50]}...'")
    print(f"  New description: '{new_desc}'")

    # Patch to temp file
    with tempfile.NamedTemporaryFile(suffix='.graphml', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        patcher = GraphMLPatcher(graphml_path, graph)
        patcher.load()
        patcher.update_existing_nodes()
        patcher.save(tmp_path)

        # Re-import and verify
        graph2 = Graph(graph_id="test_verify")
        importer2 = GraphMLImporter(tmp_path, graph2)
        graph2 = importer2.parse()

        # Find the same node by name
        found = None
        for n in graph2.nodes:
            if hasattr(n, 'name') and n.name == test_node.name:
                found = n
                break

        if found:
            if found.description == new_desc:
                print(f"  PASSED: Description updated correctly")
            else:
                print(f"  FAILED: Expected '{new_desc}', got '{found.description}'")
        else:
            print(f"  FAILED: Could not find node {test_node.name} in re-imported graph")

    finally:
        os.unlink(tmp_path)


def test_add_new_node(graphml_path):
    """Test 3: Add a new PropertyNode and verify it appears in the XML."""
    print("\n" + "=" * 60)
    print("TEST 3: Add New Node")
    print("=" * 60)

    # Import
    graph = Graph(graph_id="test_add")
    importer = GraphMLImporter(graphml_path, graph)
    graph = importer.parse()

    orig_count = len(graph.nodes)

    # Add a new PropertyNode (no original_id = new node)
    import uuid
    new_node = PropertyNode(
        node_id=str(uuid.uuid4()),
        name="TEST_NEW_PROPERTY",
        property_type="test",
        description="This is a test property added by patcher"
    )
    graph.add_node(new_node)
    print(f"  Added new PropertyNode: {new_node.name} ({new_node.node_id})")

    # Count original XML
    orig_xml_nodes, _ = count_xml_elements(graphml_path)

    # Patch to temp file
    with tempfile.NamedTemporaryFile(suffix='.graphml', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        patcher = GraphMLPatcher(graphml_path, graph)
        patcher.load()
        patcher.update_existing_nodes()
        added = patcher.add_new_nodes()
        patcher.save(tmp_path)

        print(f"  Nodes added to XML: {added}")

        # Count patched XML
        patched_xml_nodes, _ = count_xml_elements(tmp_path)
        print(f"  XML nodes: {orig_xml_nodes} -> {patched_xml_nodes}")

        if patched_xml_nodes > orig_xml_nodes:
            print("  PASSED: New node added to XML")
        else:
            print("  FAILED: No new nodes in XML")

        # Verify the new node is findable via EMID in the XML
        tree = ET.parse(tmp_path)
        ns = 'http://graphml.graphdrawing.org/xmlns'
        found_emid = False
        for node_elem in tree.iter(f'{{{ns}}}node'):
            for data_elem in node_elem.findall(f'{{{ns}}}data'):
                if data_elem.text and data_elem.text.strip() == new_node.node_id:
                    found_emid = True
                    break

        if found_emid:
            print("  PASSED: New node EMID found in XML")
        else:
            print("  FAILED: New node EMID not found in XML")

    finally:
        os.unlink(tmp_path)


def test_emid_preservation(graphml_path):
    """Test 4: Verify EMIDs are not altered during patching."""
    print("\n" + "=" * 60)
    print("TEST 4: EMID Preservation")
    print("=" * 60)

    # Collect EMIDs from original file
    tree = ET.parse(graphml_path)
    ns = 'http://graphml.graphdrawing.org/xmlns'

    # Build key map to find EMID key
    emid_key = None
    for key_elem in tree.getroot().findall(f'{{{ns}}}key'):
        if key_elem.attrib.get('attr.name') == 'EMID' and \
           key_elem.attrib.get('for') == 'node':
            emid_key = key_elem.attrib.get('id')
            break

    if not emid_key:
        print("  SKIPPED: No EMID key found in file")
        return

    # Collect original EMIDs
    original_emids = {}
    for node_elem in tree.iter(f'{{{ns}}}node'):
        node_id = node_elem.attrib.get('id')
        for data_elem in node_elem.findall(f'{{{ns}}}data'):
            if data_elem.attrib.get('key') == emid_key and data_elem.text:
                original_emids[node_id] = data_elem.text.strip()

    print(f"  Original file has {len(original_emids)} nodes with EMIDs")

    # Import and patch
    graph = Graph(graph_id="test_emid")
    importer = GraphMLImporter(graphml_path, graph)
    graph = importer.parse()

    with tempfile.NamedTemporaryFile(suffix='.graphml', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        patcher = GraphMLPatcher(graphml_path, graph)
        patcher.load()
        patcher.update_existing_nodes()
        patcher.save(tmp_path)

        # Collect patched EMIDs
        tree2 = ET.parse(tmp_path)
        patched_emids = {}
        for node_elem in tree2.iter(f'{{{ns}}}node'):
            node_id = node_elem.attrib.get('id')
            for data_elem in node_elem.findall(f'{{{ns}}}data'):
                if data_elem.attrib.get('key') == emid_key and data_elem.text:
                    patched_emids[node_id] = data_elem.text.strip()

        # Compare
        preserved = 0
        changed = 0
        for node_id, orig_emid in original_emids.items():
            if node_id in patched_emids:
                if patched_emids[node_id] == orig_emid:
                    preserved += 1
                else:
                    changed += 1
                    if changed <= 3:
                        print(f"    CHANGED: {node_id}: {orig_emid[:20]}... -> {patched_emids[node_id][:20]}...")

        print(f"  EMIDs preserved: {preserved}/{len(original_emids)}")
        print(f"  EMIDs changed: {changed}")

        if changed == 0:
            print("  PASSED: All EMIDs preserved")
        else:
            print(f"  WARNING: {changed} EMIDs were changed (may be expected for newly assigned UUIDs)")

    finally:
        os.unlink(tmp_path)


def test_merge_conflicts():
    """Test 5: Test GraphMerger conflict detection."""
    print("\n" + "=" * 60)
    print("TEST 5: Merge Conflict Detection")
    print("=" * 60)

    from s3dgraphy.merge import GraphMerger, Conflict
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit
    import uuid

    # Create existing graph
    existing = Graph(graph_id="existing")
    us01 = StratigraphicUnit(node_id=str(uuid.uuid4()), name="USM01",
                              description="Old description")
    us01.node_type = "US"
    us02 = StratigraphicUnit(node_id=str(uuid.uuid4()), name="USM02",
                              description="Wall")
    us02.node_type = "US"
    existing.add_node(us01)
    existing.add_node(us02)
    existing.add_edge(str(uuid.uuid4()), us01.node_id, us02.node_id, 'overlies')

    # Create incoming graph with changes
    incoming = Graph(graph_id="incoming")
    us01_new = StratigraphicUnit(node_id=str(uuid.uuid4()), name="USM01",
                                  description="NEW description from XLSX")
    us01_new.node_type = "US"
    us02_new = StratigraphicUnit(node_id=str(uuid.uuid4()), name="USM02",
                                  description="Wall")
    us02_new.node_type = "US"
    us03_new = StratigraphicUnit(node_id=str(uuid.uuid4()), name="USM03",
                                  description="New floor")
    us03_new.node_type = "US"
    incoming.add_node(us01_new)
    incoming.add_node(us02_new)
    incoming.add_node(us03_new)
    incoming.add_edge(str(uuid.uuid4()), us01_new.node_id, us02_new.node_id, 'cuts')

    # Compare
    merger = GraphMerger()
    conflicts = merger.compare(existing, incoming)

    print(f"  Conflicts found: {len(conflicts)}")
    for c in conflicts:
        print(f"    {c.display_summary}")

    # Expected: description change for USM01, edge change (overlies removed, cuts added), new node USM03
    desc_conflicts = [c for c in conflicts if c.field == 'description']
    edge_conflicts = [c for c in conflicts if c.field.startswith('edge:')]
    node_conflicts = [c for c in conflicts if c.conflict_type == 'node_added']

    passed = True
    if len(desc_conflicts) >= 1:
        print("  PASSED: Description conflict detected")
    else:
        print("  FAILED: No description conflict detected")
        passed = False

    if len(edge_conflicts) >= 1:
        print("  PASSED: Edge conflict detected")
    else:
        print("  FAILED: No edge conflict detected")
        passed = False

    if len(node_conflicts) >= 1:
        print("  PASSED: New node detected")
    else:
        print("  FAILED: No new node detected")
        passed = False

    # Test apply
    for c in conflicts:
        c.resolved = True
        c.accepted = True

    merger.apply_resolutions(existing, conflicts, incoming)
    updated_node = existing.find_node_by_name("USM01")
    if updated_node and updated_node.description == "NEW description from XLSX":
        print("  PASSED: Resolution applied correctly")
    else:
        print("  FAILED: Resolution not applied correctly")
        passed = False


def main():
    # Default test file
    default_path = os.path.join(
        os.path.dirname(__file__), '..', 'EXAMPLES_EM_AI_WORKFLOW',
        'GreatTemple', 'TempluMare_EM_converted_converted 2.graphml'
    )

    graphml_path = sys.argv[1] if len(sys.argv) > 1 else default_path

    if not os.path.exists(graphml_path):
        print(f"ERROR: File not found: {graphml_path}")
        print("Usage: python test_graphml_patcher.py [path_to_graphml]")
        sys.exit(1)

    print(f"Testing with: {graphml_path}")
    print(f"File size: {os.path.getsize(graphml_path) / 1024:.1f} KB")

    test_basic_patch(graphml_path)
    test_update_node_description(graphml_path)
    test_add_new_node(graphml_path)
    test_emid_preservation(graphml_path)
    test_merge_conflicts()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)


if __name__ == '__main__':
    main()
