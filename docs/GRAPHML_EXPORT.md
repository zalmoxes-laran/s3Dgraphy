# GraphML Export for Extended Matrix

This document explains the GraphML export functionality for converting s3dgraphy graphs to Extended Matrix GraphML format.

## Overview

The GraphML exporter transforms s3dgraphy graph data into Extended Matrix GraphML format compatible with yEd. It implements all Extended Matrix specifications including:

- ✅ Correct key definitions (d7/d8 for nodes, d11/d12 for edges)
- ✅ ParadataNodeGroup with correct background color (#FFCC99)
- ✅ ExtractorNode (SVG icon, paradata family)
- ✅ DocumentNode (BPMN Data Object, paradata family)
- ✅ Nested ID format (n0::n1::n2) for yEd compatibility
- ✅ Visual properties from palette template
- ✅ Dashed edges for paradata connections

## Quick Start

```python
from s3dgraphy.importer.mapped_xlsx_importer import MappedXLSXImporter
from s3dgraphy.exporter.graphml import GraphMLExporter

# 1. Import Excel data to s3dgraphy Graph
importer = MappedXLSXImporter(
    filepath="stratigraphy.xlsx",
    mapping_name="excel_to_graphml_mapping"
)
graph = importer.parse()

# 2. Export to GraphML
exporter = GraphMLExporter(graph)
exporter.export("output.graphml")

# 3. Open in yEd to visualize
```

## Architecture

### Module Structure

```
src/s3dgraphy/exporter/graphml/
├── graphml_exporter.py         # Main orchestrator
├── canvas_generator.py         # Root XML + key definitions
├── node_registry.py            # Hybrid: datamodel JSON + palette template
├── node_generator.py           # StratigraphicNode, PropertyNode, ExtractorNode, DocumentNode
├── group_node_generator.py    # ParadataNodeGroup with correct colors
├── edge_generator.py           # Edges with line styles
└── utils.py                    # ID management, coordinate calculation
```

### Key Components

#### 1. Canvas Generator

Generates root XML with correct namespaces and key definitions:

```xml
<!-- Node keys -->
<key attr.name="EMID" attr.type="string" for="node" id="d7"/>
<key attr.name="URI" attr.type="string" for="node" id="d8"/>

<!-- Edge keys (SEPARATE) -->
<key attr.name="EMID" attr.type="string" for="edge" id="d11"/>
<key attr.name="URI" attr.type="string" for="edge" id="d12"/>
```

#### 2. Node Registry

Loads node definitions from two sources:
- **s3Dgraphy_node_datamodel.json**: Metadata (class, description, abbreviation)
- **em_palette_template.graphml**: Visual properties (shape, colors, borders)

```python
registry = NodeRegistry()
visual = registry.get_visual_properties('US')
# Returns: NodeVisualProperties(
#   shape='rectangle',
#   fill_color='#FFFFFF',
#   border_color='#9B3333',
#   border_type='line',
#   border_width=4.0,
#   text_color='#000000'
# )
```

#### 3. Node Generators

Generates XML for different node types:

**StratigraphicNode** → ShapeNode (rectangle, hexagon, etc.)
```xml
<y:ShapeNode>
  <y:Fill color="#FFFFFF"/>
  <y:BorderStyle color="#9B3333" type="line" width="4.0"/>
  <y:Shape type="rectangle"/>
</y:ShapeNode>
```

**PropertyNode** → BPMN Annotation
```xml
<y:GenericNode configuration="com.yworks.bpmn.Artifact.withShadow">
  <y:StyleProperties>
    <y:Property name="com.yworks.bpmn.type" value="ARTIFACT_TYPE_ANNOTATION"/>
  </y:StyleProperties>
</y:GenericNode>
```

**ExtractorNode** → SVG Node (paradata family)
```xml
<y:SVGNode>
  <y:NodeLabel>D.</y:NodeLabel>
  <y:SVGModel svgBoundsPolicy="0">
    <y:SVGContent refid="3"/>
  </y:SVGModel>
</y:SVGNode>
```

**DocumentNode** → BPMN Data Object (paradata family)
```xml
<y:GenericNode configuration="com.yworks.bpmn.Artifact.withShadow">
  <y:StyleProperties>
    <y:Property name="com.yworks.bpmn.type" value="ARTIFACT_TYPE_DATA_OBJECT"/>
    <y:Property name="com.yworks.bpmn.dataObjectType" value="DATA_OBJECT_TYPE_PLAIN"/>
  </y:StyleProperties>
</y:GenericNode>
```

#### 4. ParadataNodeGroup Generator

Creates ProxyAutoBoundsNode with correct background color:

```xml
<y:ProxyAutoBoundsNode>
  <y:Realizers active="0">
    <y:GroupNode>
      <y:BorderStyle color="#000000" type="dashed" width="1.0"/>
      <y:NodeLabel backgroundColor="#FFCC99">USM01_PD</y:NodeLabel>
      <y:State closed="false"/>
    </y:GroupNode>
    <!-- Second realizer for closed state -->
  </y:Realizers>
</y:ProxyAutoBoundsNode>
```

**Key Features**:
- Background color: `#FFCC99` (reverse engineered from import_graphml.py)
- Border: dashed
- Two realizers (open/closed states)
- Nested graph for contained nodes

#### 5. Edge Generator

Generates edges with correct EMID placement:

```xml
<edge id="e0" source="n0" target="n1">
  <data key="d11">uuid-edge-1234</data>  <!-- EMID in d11, NOT d7 -->
  <y:PolyLineEdge>
    <y:LineStyle type="line" width="2.0"/>
    <y:Arrows source="none" target="standard"/>
  </y:PolyLineEdge>
</edge>
```

**Line Style Mapping**:
- `is_after`: solid line (temporal)
- `has_data_provenance`: dashed (provenance)
- `has_paradata_nodegroup`: dashed (US → ParadataGroup)
- `changed_from`: dotted (transformation)

#### 6. ID Management

Maps UUIDs to nested IDs for yEd compatibility:

```python
id_manager = IDManager()

# Top-level nodes
id_manager.get_nested_id(uuid1)  # → "n0"
id_manager.get_nested_id(uuid2)  # → "n1"

# Nested nodes inside group
id_manager.get_nested_id(uuid3, parent_id="n1")  # → "n1::n0"
id_manager.get_nested_id(uuid4, parent_id="n1")  # → "n1::n1"
```

## Paradata Structure Transformation

### In s3dgraphy (Graph)

```python
StratigraphicNode(
    node_id="uuid-1234",
    name="USM01",
    extractor="GPT-4",        # Attribute
    document="Report_2023.pdf" # Attribute
)
```

### In GraphML (Extended Matrix)

```
StratigraphicNode (USM01)                    [n0]
    ↓ has_paradata_nodegroup (dashed edge)
ParadataNodeGroup (USM01_PD)                 [n1]  backgroundColor="#FFCC99"
    ├─ PropertyNode (stratigraphic_definition) [n1::n0] BPMN Annotation
    │   ↓ has_data_provenance
    │   ExtractorNode (D.GPT4)                 [n1::n1] SVG node
    │       ↓ extracted_from
    │       DocumentNode (Report_2023.pdf)     [n1::n2] BPMN Data Object
    │
    └─ PropertyNode (description)              [n1::n3] BPMN Annotation
```

**Transformation handled by** `_build_paradata_groups()` in `graphml_exporter.py`.

## Implementation Details

### Correct Key Definitions

**CRITICAL**: Nodes and edges have separate EMID/URI keys.

```python
# Node keys
d7 = "EMID" (for nodes)
d8 = "URI" (for nodes)

# Edge keys (SEPARATE!)
d11 = "EMID" (for edges)
d12 = "URI" (for edges)
```

### ParadataNodeGroup Colors

Colors reverse engineered from `import_graphml.py` (lines 1323-1331):

```python
GROUP_COLORS = {
    'ParadataNodeGroup': '#FFCC99',      # ✓ Correct
    'ActivityNodeGroup': '#CCFFFF',
    'TimeBranchNodeGroup': '#99CC00'
}
```

### Node Visual Properties

Loaded from **hybrid approach**:
1. Metadata from `s3Dgraphy_node_datamodel.json`
2. Visual properties from `em_palette_template.graphml`

Example mapping:
- US → rectangle, white fill (#FFFFFF), red border (#9B3333)
- USVs → parallelogram, black fill (#000000), blue border (#248FE7)
- USVn → hexagon, black fill (#000000), green border (#31792D)

## Testing

```bash
python3 test_excel_to_graphml.py
```

**Expected output**:
- ✅ 5 stratigraphic nodes exported
- ✅ Nested IDs (n0-n4)
- ✅ Correct shapes and colors
- ✅ SVG resources included
- ✅ Valid GraphML file

## Files Generated

Example structure of exported GraphML:

```xml
<?xml version='1.0' encoding='UTF-8'?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" ...>
  <!-- Key definitions -->
  <key for="node" id="d7" attr.name="EMID"/>
  <key for="edge" id="d11" attr.name="EMID"/>
  
  <graph id="G" edgedefault="directed">
    <!-- StratigraphicNode with nested ID -->
    <node id="n0">
      <data key="d7">uuid-1234</data>
      <data key="d6">
        <y:ShapeNode>
          <y:Fill color="#FFFFFF"/>
          <y:BorderStyle color="#9B3333" type="line" width="4.0"/>
          <y:Shape type="rectangle"/>
        </y:ShapeNode>
      </data>
    </node>
    
    <!-- ParadataNodeGroup (if extractor/document present) -->
    <node id="n1" yfiles.foldertype="group">
      <data key="d7">uuid-5678</data>
      <data key="d6">
        <y:ProxyAutoBoundsNode>
          <y:GroupNode>
            <y:NodeLabel backgroundColor="#FFCC99">USM01_PD</y:NodeLabel>
            ...
          </y:GroupNode>
        </y:ProxyAutoBoundsNode>
      </data>
      <graph id="n1:">
        <!-- Nested PropertyNode, ExtractorNode, DocumentNode -->
      </graph>
    </node>
    
    <!-- Edge with EMID in d11 -->
    <edge id="e0" source="n0" target="n1">
      <data key="d11">uuid-edge-9012</data>
      <y:PolyLineEdge>
        <y:LineStyle type="dashed" width="2.0"/>
      </y:PolyLineEdge>
    </edge>
  </graph>
  
  <!-- SVG Resources for ExtractorNode icons -->
  <data key="d9">
    <y:Resources>
      <y:Resource id="3"><!-- SVG content --></y:Resource>
    </y:Resources>
  </data>
</graphml>
```

## See Also

- [Data Formalizations](DATA_FORMALIZATIONS.md) - Explains Excel → s3dgraphy → GraphML workflow
- [Extended Matrix Specification](https://www.extendedmatrix.org/) - Official EM documentation
- [yEd Manual](https://yed.yworks.com/support/manual/) - yEd graph editor documentation

## References

- Implementation plan: `/Users/emanueldemetrescu/.claude/plans/inherited-shimmying-flask.md`
- Palette template: `src/s3dgraphy/templates/em_palette_template.graphml`
- Node datamodel: `src/s3dgraphy/JSON_config/s3Dgraphy_node_datamodel.json`
- Import reference: `src/s3dgraphy/importer/import_graphml.py` (reverse engineering source)
