# Data Formalizations in s3dgraphy

This document explains the three different data formalizations used in the stratigraphic data workflow and how they transform from one to another.

## Overview

The stratigraphic data workflow involves three distinct formalizations:

```
Excel (Tabular) → s3dgraphy (Graph) → Extended Matrix (Hypergraph)
     ↓                    ↓                        ↓
  Data Entry      In-Memory Model         GraphML Export
```

Each formalization serves a specific purpose and has its own structure.

---

## 1. Excel Formalization (Tabular)

**Purpose**: Data entry and AI-powered data extraction

**Structure**: Tabular spreadsheet with columns and rows

**Characteristics**:
- Human-readable and editable
- Suitable for AI extraction from PDF/documents
- Supports comma-separated relationships (e.g., "USM01,USM02")
- Attributes stored as simple column values

**Example**:
```
| ID    | TYPE | DESCRIPTION          | EXTRACTOR | DOCUMENT         | OVERLIES |
|-------|------|----------------------|-----------|------------------|----------|
| USM01 | US   | Strato terra compatta| GPT-4     | Report_2023.pdf  | USM02    |
| USM02 | US   | Muro in mattoni      | Claude    | Report_2023.pdf  |          |
```

**Key Columns**:
- `ID`: Stratigraphic unit identifier
- `TYPE`: Node type (US, USVs, USVn, SF, etc.)
- `EXTRACTOR`: Who/what extracted the data (attribute)
- `DOCUMENT`: Source document (attribute)
- Topological relations: `OVERLIES`, `CUTS`, `FILLS`, etc.

---

## 2. s3dgraphy Formalization (Graph)

**Purpose**: In-memory representation with support for 3D elements

**Structure**: Property graph with typed nodes and edges

**Characteristics**:
- Extended version of Extended Matrix
- Includes 3D representation nodes (not in pure EM)
- Paradata stored as **attributes** on nodes (not separate nodes)
- Groups are "dissolved" into individual nodes

**Node Types**:
- `StratigraphicNode`: US, USVs, USVn, SF, VSF, USD, etc.
- `PropertyNode`: Properties of stratigraphic units
- `EpochNode`: Temporal periods/phases
- `RepresentationNode`: 3D models (s3dgraphy extension)
- `SemanticShapeNode`: 3D geometry (s3dgraphy extension)

**Example Structure**:
```python
StratigraphicNode(
    node_id="uuid-1234",
    name="USM01",
    node_type="US",
    description="Strato terra compatta",
    extractor="GPT-4",        # Attribute (not separate node)
    document="Report_2023.pdf" # Attribute (not separate node)
)
```

**Important**: `extractor` and `document` are **attributes**, not separate nodes in s3dgraphy. They will be transformed into Extended Matrix paradata structure during export.

---

## 3. Extended Matrix GraphML (Hypergraph)

**Purpose**: Standardized archaeological stratigraphy visualization in yEd

**Structure**: Hypergraph with groups (ProxyAutoBoundsNode)

**Characteristics**:
- Pure Extended Matrix formalism
- Paradata organized in **ParadataNodeGroup** (collapsible groups)
- ExtractorNode and DocumentNode as **separate nodes** (paradata family)
- No 3D elements (pure stratigraphic representation)
- Nested ID hierarchy (n0::n1::n2) for yEd compatibility

**Node Structure in GraphML**:
```
StratigraphicNode (USM01)                    [n0]
    ↓ has_paradata_nodegroup (dashed edge)
ParadataNodeGroup (USM01_PD)                 [n1]  ← backgroundColor="#FFCC99"
    ├─ PropertyNode (stratigraphic_definition) [n1::n0]
    │   ↓ has_data_provenance
    │   ExtractorNode (D.GPT4)                 [n1::n1]  ← SVG node, paradata family
    │       ↓ extracted_from
    │       DocumentNode (Report_2023.pdf)     [n1::n2]  ← BPMN Data Object, paradata family
    │
    └─ PropertyNode (description)              [n1::n3]
```

**Key Differences from s3dgraphy**:
- Extractor/Document become **separate nodes** (ExtractorNode, DocumentNode)
- Paradata organized in **ParadataNodeGroup** with specific background color (#FFCC99)
- Each node has both UUID (EMID) and nested ID for yEd
- Visual properties: shapes, colors, icons (defined in palette template)

---

## Transformation Workflow

### Excel → s3dgraphy (via MappedXLSXImporter)

**Handled by**: `MappedXLSXImporter` + `excel_to_graphml_mapping.json`

**Process**:
1. Read Excel columns according to mapping
2. Create StratigraphicNode for each row (ID column)
3. Create PropertyNode/EpochNode for properties
4. Store EXTRACTOR/DOCUMENT as **attributes** on StratigraphicNode
5. Create edges for topological relations

**Mapping Configuration**:
```json
"EXTRACTOR": {
    "node_type": "StratigraphicNode",
    "property_name": "extractor",
    "is_attribute": true  // ← Stored as attribute, not separate node
}
```

### s3dgraphy → Extended Matrix GraphML (via GraphMLExporter)

**Handled by**: `GraphMLExporter`

**Process**:
1. Generate StratigraphicNode as ShapeNode with correct visual properties
2. For each StratigraphicNode with `extractor`/`document` attributes:
   - Create ParadataNodeGroup (ProxyAutoBoundsNode, backgroundColor="#FFCC99")
   - Create PropertyNode (stratigraphic_definition) inside group
   - Create ExtractorNode (SVG node, paradata family) inside group
   - Create DocumentNode (BPMN Data Object, paradata family) inside group
   - Create edge US → ParadataNodeGroup (dashed)
3. Map UUIDs to nested IDs (n0, n0::n1, etc.)
4. Generate edges with correct line styles (solid, dashed, dotted)

**Key Code** (`graphml_exporter.py`, lines 148-191):
```python
def _build_paradata_groups(self, stratigraphic_nodes):
    for us_node in stratigraphic_nodes:
        # Read attributes from s3dgraphy node
        extractor = getattr(us_node, 'extractor', None)
        document = getattr(us_node, 'document', None)
        
        if extractor or document:
            # Create Extended Matrix paradata structure
            property_node = PropertyNode(...)
            extractor_node = ExtractorNode(...) if extractor else None
            document_node = DocumentNode(...) if document else None
            # ... create ParadataNodeGroup containing these nodes
```

---

## Why Three Formalizations?

1. **Excel**: Optimized for **human data entry** and **AI extraction**
   - Easy to edit in spreadsheet tools
   - Natural format for AI models (GPT-4, Claude) to populate
   - Simple comma-separated lists for relationships

2. **s3dgraphy**: Optimized for **in-memory processing** and **3D integration**
   - Rich object model with methods and behavior
   - Supports 3D representation nodes
   - Flexible attribute storage
   - Easy to query and manipulate programmatically

3. **Extended Matrix GraphML**: Optimized for **visualization** and **standardization**
   - Standard format readable by yEd
   - Visual properties (colors, shapes, icons)
   - Collapsible groups for paradata
   - Nested hierarchy for complex structures

---

## File Locations

- **Excel Mapping**: `src/s3dgraphy/mappings/generic/excel_to_graphml_mapping.json`
- **Importer**: `src/s3dgraphy/importer/mapped_xlsx_importer.py`
- **Exporter**: `src/s3dgraphy/exporter/graphml/graphml_exporter.py`
- **Node Definitions**: `src/s3dgraphy/JSON_config/s3Dgraphy_node_datamodel.json`
- **Visual Palette**: `src/s3dgraphy/templates/em_palette_template.graphml`

---

## Common Mistakes to Avoid

❌ **Wrong**: Treating EXTRACTOR/DOCUMENT as separate nodes in s3dgraphy
```python
# WRONG! Don't do this
ExtractorNode(name="GPT-4")  # in s3dgraphy Graph
```

✅ **Correct**: Store as attributes, let GraphMLExporter create paradata structure
```python
# CORRECT!
StratigraphicNode(
    name="USM01",
    extractor="GPT-4",  # attribute
    document="Report_2023.pdf"  # attribute
)
# GraphMLExporter will create ExtractorNode/DocumentNode during export
```

---

❌ **Wrong**: Expecting ParadataNodeGroup in s3dgraphy Graph
```python
# WRONG! ParadataNodeGroup doesn't exist in s3dgraphy
graph.nodes  # Contains only StratigraphicNode, PropertyNode, etc.
```

✅ **Correct**: ParadataNodeGroup is created during GraphML export
```python
# CORRECT!
# s3dgraphy has: StratigraphicNode with attributes
# GraphML will have: ParadataNodeGroup with nested ExtractorNode/DocumentNode
```

---

## Summary

| Aspect | Excel | s3dgraphy | Extended Matrix GraphML |
|--------|-------|-----------|-------------------------|
| **Format** | Tabular | Graph | Hypergraph |
| **Purpose** | Data entry | Processing | Visualization |
| **Extractor** | Column value | Node attribute | ExtractorNode (paradata) |
| **Document** | Column value | Node attribute | DocumentNode (paradata) |
| **Groups** | N/A | Dissolved | ParadataNodeGroup |
| **3D** | No | Yes | No |
| **IDs** | Simple (USM01) | UUID | UUID + Nested (n0::n1) |

Each formalization is optimized for its specific use case. The transformation between them is handled automatically by the importer and exporter, ensuring data integrity while adapting to each format's strengths.
