# GraphML Export - AI Stratigraphic Data Collection

Complete GraphML Writer implementation for s3dgraphy, enabling AI-powered stratigraphic data extraction workflows.

## ✅ ALL FEATURES COMPLETED

### 1. Core GraphML Export System ✓
- Canvas Generator: Root XML with yEd namespaces
- Node Generator: All Extended Matrix node types with shapes/colors
- Edge Generator: Edges with correct line styles
- Main Exporter: Orchestrates layout and generation

### 2. Paradata Structure Generator ✓
Automatic provenance chains:
- US → PropertyNode → ExtractorNode → DocumentNode
- Deduplication of Extractor/Document nodes

### 3. Temporal Inference Engine ✓
- Topological → Temporal conversion (cuts/overlies/fills → is_after)
- Transitive reduction with networkx
- Cycle detection

### 4. Epoch Swimlanes Generator ✓
- yEd TableNode structures for temporal periods
- Hierarchical epoch support

### 5. Excel → Graph → GraphML Pipeline ✓
- Complete end-to-end workflow tested
- Example template included

### 6. Blender Integration ✓
- Operator: XLSX → GraphML in EMsetup Quick Utils
- File browser, mapping selection, output naming

## Quick Start

### From Blender
1. EM panel > EMsetup > Utilities & Settings
2. Click "XLSX → GraphML"
3. Select Excel file
4. GraphML created in same directory

### Programmatic
```python
from s3dgraphy.importer.mapped_xlsx_importer import MappedXLSXImporter
from s3dgraphy.exporter.graphml import GraphMLExporter

importer = MappedXLSXImporter(
    filepath="data.xlsx",
    mapping_name="excel_to_graphml_mapping"
)
graph = importer.parse()

exporter = GraphMLExporter(graph)
exporter.export("output.graphml")
```

## Files Created

**s3Dgraphy**:
- `src/s3dgraphy/exporter/graphml/` - All export modules
- `src/s3dgraphy/temporal/inference_engine.py` - Temporal logic
- `src/s3dgraphy/mappings/generic/excel_to_graphml_mapping.json` - Excel mapping
- `example_stratigraphy.xlsx` - Sample data
- `test_graphml_export.py` - Basic test
- `test_excel_to_graphml.py` - Pipeline test

**EM-blender-tools**:
- `operators/xlsx_to_graphml.py` - Blender operator
- `operators/__init__.py` - Updated registration
- `em_setup/ui.py` - Button added

## Status: Production Ready ✅

All tasks completed and tested successfully!
