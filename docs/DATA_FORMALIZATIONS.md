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

## The proxy as the qualia `geometry`

*Datamodel versions: nodes **1.6.3** · connections **1.6.10** · qualia **1.6.1**.*

### Why

A *proxy* is the geometry-without-material of a unit: the shape US101 has,
without asserting what it is made of. It used to be a `SemanticShapeNode`
hanging off the unit on its own — and **a lone node cannot say where it came
from**. "The proxy of US101" could not be traced to a measurement, a photograph
or a reprojection, because it had no paradata chain to be traced through.

Making it a property fixes exactly that, and buys one more thing: **one proxy can
be synthesised from several sources** — a photogrammetric mesh *and* a 1931
photograph — instead of one node per source with nothing to join them.

### How

```
US ──has_property──▶ PropertyNode(property_type="geometry")
                          │  has_semantic_shape
                          ▼
                     SemanticShapeNode   (convex hulls / spheres, or a .glb in url)

provenance, the ordinary chain:
    Extractor(s) ──combines──◀── Combiner ──◀── has_data_provenance ── the property
```

Nothing here is special-cased for geometry: the provenance uses the same
`extracted_from` / `combines` / `has_data_provenance` edges every other property
uses. A geometry property that needed its own provenance mechanism would be a
second paradata model to keep in step.

Two details worth knowing:

- the property's `value` is a **reference** to the shape, not the numbers.
  Copying them would be a second copy of the geometry, free to drift from the
  first;
- with **one** source no `CombinerNode` is created. An inference node between a
  single extractor and a property would assert a reasoning step nobody performed.

```python
from s3dgraphy import api

api.create_geometry_proxy(
    graph, "US101",
    {"convexshapes": [[0, 0, 0, 1, 0, 0, 1, 1, 0]]},
    extractor_sources=["D1", "D2"],      # mesh + historical photograph
)
```

`SemanticShapeNode` itself is unchanged — same fields, same CIDOC mapping. What
changed is **who points at it**; its `type='proxy'` option now names the *role of
the carrier*, not a standalone node kind.

### The invariant: annotating **is** extracting

The act of annotating is always an extraction — something is pulled out of a
source — and the region always lives on a document. That is the invariant. What
**varies** is *what* is being extracted, which is why the annotator must ask
before it records:

| You annotate to… | Chain | Extractor? |
|---|---|---|
| state the identity/extent of a unit | region → extractor → property → US | yes |
| measure (a scale on the image) | region → extractor → dimensional property | yes (a metric quale) |
| record two readings of one region | 1 region, 2 extractors, 2 properties | yes (1:N) |
| register 2D↔3D (an RMDoc pose) | region → extractor → correspondence → RMDoc | yes (target = the RMDoc) |
| photogrammetry (Aïoli) | region → 3D reprojection → SemanticShape | yes (photogrammetric provenance) |
| "look here" — a bare bookmark | — | **no**: it is a *note*, outside the paradata |

Consequences that the datamodel already carries:

- a region is a node of its own, **deduplicated by geometry** — the same
  rectangle traced twice is ONE region, referenced by `has_visual_reference` from
  *every* property that reads it. Two authors can point at the same brick and
  disagree;
- `create_annotation_paradata` does *get-or-create* on the region and adds **one
  extractor + one property per call**, rather than welding them to a single one;
- an `ExtractorNode` may cite an `AnnotationRegionNode` through `extracted_from`
  (CRMinf `J7_is_based_on_evidence_from` takes *evidence*, and a traced region is
  evidence — a more precise citation than the whole picture). This is a widened
  target rather than a new edge type: the relation "this extraction is based on
  that" already exists and already has a name.

### Promotion: a resource is not a source

`extracted_from` cites a **source** — a `DocumentNode`. The resource layer's file
node is not one: a source is something somebody authored and can be cited, a
resource is bytes on a disk. So annotating a `ResourceNode` **promotes** it
rather than converting it: a `DocumentNode` is minted beside it and linked with
`has_linked_resource` (P67).

```
Extractor        ──extracted_from──▶ Document ──has_linked_resource──▶ Resource
AnnotationRegion ──is_on_resource───────────────────────────────────▶ Resource
```

The extraction cites the document; the region lives on the pixels. The document's
id is a `uuid5` of the resource id, so annotating the same image twice reuses it.

### Open with CIDOC (declared, not settled)

The `geometry` qualia maps to **`crmgeo:SP5_Geometric_Place_Expression`** as a
*defensible default, not a final answer* — the vocabulary entry carries
`confirm_with: "Felicetti"`. The alternative under discussion is
`E36_Visual_Item`, which is the same choice open for `em:AnnotationRegion`; the
two should be decided together. Whichever wins changes the **projection of one
field**, not the modelling of the proxy as a property.

Also open, and untouched here: how the proxy-as-property and the spatialisation
chain attach to the **HDT-O** (Theodoridou).

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
