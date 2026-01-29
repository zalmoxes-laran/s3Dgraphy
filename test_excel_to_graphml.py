"""
Test script for complete Excel → Graph → GraphML pipeline.

Tests the full workflow using MappedXLSXImporter + GraphMLExporter.
"""

from s3dgraphy.importer.mapped_xlsx_importer import MappedXLSXImporter
from s3dgraphy.exporter.graphml import GraphMLExporter
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode


def main():
    """Run the complete pipeline test."""
    print("="*70)
    print("Excel → Graph → GraphML Pipeline Test")
    print("="*70)

    # Step 1: Load Excel using MappedXLSXImporter
    print("\n1. Loading Excel file...")
    excel_path = "example_stratigraphy.xlsx"
    mapping_name = "excel_to_graphml_mapping"

    try:
        importer = MappedXLSXImporter(
            filepath=excel_path,
            mapping_name=mapping_name
        )
        print(f"   ✓ Importer initialized")
        print(f"     - Excel file: {excel_path}")
        print(f"     - Mapping: {mapping_name}")
    except Exception as e:
        print(f"   ✗ Error initializing importer: {e}")
        return

    # Step 2: Parse Excel → Graph
    print("\n2. Parsing Excel to Graph...")
    try:
        graph = importer.parse()
        print(f"   ✓ Graph created from Excel")
        print(f"     - Total nodes: {len(graph.nodes)}")
        print(f"     - Total edges: {len(graph.edges)}")

        # Count node types
        strat_nodes = [n for n in graph.nodes if isinstance(n, StratigraphicNode)]
        print(f"     - Stratigraphic nodes: {len(strat_nodes)}")

        # Show stratigraphic units
        if strat_nodes:
            print("\n   Stratigraphic units loaded:")
            for node in strat_nodes[:5]:  # Show first 5
                us_type = getattr(node, 'node_type', 'US')
                desc = node.description[:50] if hasattr(node, 'description') and node.description else "No description"
                extractor = getattr(node, 'extractor', None)
                document = getattr(node, 'document', None)
                print(f"     - {node.name} ({us_type}): {desc}...")
                if extractor or document:
                    print(f"       Provenance: Extractor={extractor}, Document={document}")

    except Exception as e:
        print(f"   ✗ Error parsing Excel: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 3: Export Graph → GraphML
    print("\n3. Exporting Graph to GraphML...")
    output_path = "/tmp/excel_pipeline_export.graphml"

    try:
        exporter = GraphMLExporter(graph)
        exporter.export(output_path)
        print(f"   ✓ GraphML export completed")
    except Exception as e:
        print(f"   ✗ Error exporting GraphML: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Validation
    print("\n4. Validating output...")
    try:
        import os
        file_size = os.path.getsize(output_path)
        print(f"   ✓ GraphML file created: {output_path}")
        print(f"     - File size: {file_size:,} bytes")

        # Check XML validity
        from lxml import etree as ET
        tree = ET.parse(output_path)
        root = tree.getroot()
        print(f"   ✓ XML is valid")
        print(f"     - Root element: {root.tag}")

        # Count nodes in GraphML
        nodes = root.findall(".//{http://graphml.graphdrawing.org/xmlns}node")
        edges = root.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")
        print(f"     - Nodes in GraphML: {len(nodes)}")
        print(f"     - Edges in GraphML: {len(edges)}")

    except Exception as e:
        print(f"   ✗ Error validating output: {e}")
        import traceback
        traceback.print_exc()
        return

    # Success!
    print("\n" + "="*70)
    print("SUCCESS!")
    print("="*70)
    print(f"\nComplete pipeline executed successfully:")
    print(f"  1. Excel loaded: {excel_path}")
    print(f"  2. Graph created with {len(strat_nodes)} stratigraphic units")
    print(f"  3. GraphML exported: {output_path}")
    print(f"  4. File is valid and ready for yEd")
    print("\nNext steps:")
    print("  - Open the GraphML file in yEd to visualize")
    print("  - Check paradata structure (US → Property → Extractor → Document)")
    print("  - Verify temporal relations are correct")
    print("="*70)


if __name__ == "__main__":
    main()
