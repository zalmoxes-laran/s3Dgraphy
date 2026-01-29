# GraphML Export - Extended Matrix Specification

## Problema Identificato

L'attuale implementazione del GraphML exporter genera una rappresentazione "flat" del grafo s3dgraphy che **non rispetta le convenzioni visive e strutturali di Extended Matrix**.

## Analisi Reverse Engineering dall'Importer

### 1. Struttura Gerarchica EM

Extended Matrix usa una struttura gerarchica con 3 livelli principali:

```
GraphML Root
├── TableNode (Swimlanes per Epoche)
│   ├── Row 1 → Epoch "Romano" (background: #colore)
│   ├── Row 2 → Epoch "Medievale"
│   └── Nested Graph
│       ├── US nodes (posizionati in base a y_pos dell'epoca)
│       └── GroupNodes
│           ├── ParadataNodeGroup (#FFCC99 arancione)
│           │   ├── PropertyNode
│           │   ├── ExtractorNode
│           │   └── DocumentNode
│           ├── ActivityNodeGroup (#CCFFFF cyan)
│           └── TimeBranchNodeGroup (#99CC00 verde)
```

### 2. Componenti EM da Implementare

#### A. TableNode (Swimlanes Epoche)
```xml
<node id="n0::swimlane">
  <data key="d6">
    <y:TableNode>
      <y:Geometry height="1000" width="1200" x="0" y="0"/>
      <y:NodeLabel>Site Name [ID:uuid]</y:NodeLabel>
      <y:Table>
        <y:Rows>
          <y:Row id="epoch_1" height="200">
            <y:Insets bottom="0" left="0" right="0" top="0"/>
          </y:Row>
        </y:Rows>
      </y:Table>
      <y:NodeLabel backgroundColor="#BCBCBC">
        <y:RowNodeLabelModelParameter id="epoch_1"/>
        Epoch Name [start:X;end:Y]
      </y:NodeLabel>
    </y:TableNode>
  </data>
  <graph edgedefault="directed" id="n0::swimlane:">
    <!-- Nested nodes here -->
  </graph>
</node>
```

**Caratteristiche**:
- ID speciale: `n0::swimlane`
- Contiene `<y:Table>` con `<y:Rows>`
- Ogni Row ha un ID che corrisponde a un Epoch
- `<y:RowNodeLabelModelParameter>` lega il label alla row
- Background color identifica l'epoca visualmente
- Nested `<graph>` contiene i nodi US

#### B. ProxyAutoBoundsNode (GroupNode)
```xml
<node id="group_paradata_1">
  <data key="d6">
    <y:ProxyAutoBoundsNode>
      <y:Realizers active="0">
        <y:GroupNode>
          <y:Geometry height="150" width="200" x="800" y="300"/>
          <y:Fill color="#FFCC99" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel>Paradata Group</y:NodeLabel>
          <y:State closed="false"/>
        </y:GroupNode>
      </y:Realizers>
    </y:ProxyAutoBoundsNode>
  </data>
  <graph edgedefault="directed" id="group_paradata_1:">
    <node id="prop1"><!-- PropertyNode --></node>
    <node id="ext1"><!-- ExtractorNode --></node>
    <node id="doc1"><!-- DocumentNode --></node>
  </graph>
</node>
```

**Caratteristiche**:
- `<y:ProxyAutoBoundsNode>` con `<y:Realizers>`
- Background color identifica il tipo:
  - `#FFCC99` → ParadataNodeGroup
  - `#CCFFFF` → ActivityNodeGroup
  - `#99CC00` → TimeBranchNodeGroup
- `<y:State closed="false"/>` per rendere il gruppo visibile
- Nested `<graph>` contiene i member nodes
- Dimensioni auto-calcolate dai contenuti

### 3. Regole di Posizionamento EM

#### Positioning Logic
```python
# US positioning within epochs
for us_node in stratigraphic_nodes:
    epoch = find_epoch_for_node(us_node)
    y_base = epoch.min_y + 20  # Top padding
    y_position = y_base + calculate_temporal_order(us_node)
    x_position = calculate_column(us_node)
```

#### Epoch Assignment
- Leggere proprietà `PERIOD`, `PHASE` dal nodo
- Creare EpochNode con `start`/`end` times
- Assegnare US a epoch in base al temporal range
- Ordinare US dentro epoch per precedenza temporale

### 4. Edge Connection Rules

#### Paradata Structure
```
US → has_property → PropertyNode (dentro ParadataNodeGroup)
PropertyNode → has_data_provenance → ExtractorNode
ExtractorNode → extracted_from → DocumentNode
```

**IMPORTANTE**: Il ParadataNodeGroup si collega alla US tramite:
- Edge: US → ParadataNodeGroup con type `has_paradata_nodegroup`
- I nodi dentro il gruppo sono collegati tra loro internamente

#### Stratigraphic Relations
```
US_recent → is_after → US_ancient (freccia verso il basso)
US → cuts → USVs (relazione topologica)
US → overlies → US (relazione topologica)
```

### 5. Shape Mappings (da mantenere)

Le shape attuali sono **corrette** per i nodi singoli:
- US: rectangle, border #9B3333, fill #FFFFFF
- USVs: parallelogram, border #248FE7
- USVn: hexagon, border #31792D
- SF: rectangle, border #9B3333, fill #FFFF99
- PropertyNode: rectangle, fill #FFFFCC
- ExtractorNode: BPMN Artifact
- DocumentNode: BPMN Artifact

### 6. Piano di Implementazione

#### Phase 1: TableNode Generator (PRIORITÀ ALTA)
- [ ] Creare `TableNodeGenerator` class
- [ ] Generare XML `<y:TableNode>` con rows per epochs
- [ ] Calcolare geometrie (height somma delle rows)
- [ ] Generare `<y:NodeLabel>` con `<y:RowNodeLabelModelParameter>`
- [ ] Nested graph con id corretto (`n0::swimlane:`)

#### Phase 2: GroupNode Generator (PRIORITÀ ALTA)
- [ ] Creare `GroupNodeGenerator` class
- [ ] Generare XML `<y:ProxyAutoBoundsNode>` con `<y:Realizers>`
- [ ] Calcolare background color in base al tipo
- [ ] Generare nested graph per member nodes
- [ ] Calcolare bounding box dai contenuti

#### Phase 3: Layout Engine Refactor (PRIORITÀ MEDIA)
- [ ] Implementare `EpochAwareLayoutEngine`
- [ ] Assegnare nodi US a epochs in base a proprietà temporali
- [ ] Calcolare posizioni Y in base a epoch.min_y/max_y
- [ ] Ordinare US per precedenza temporale dentro epoch
- [ ] Posizionare gruppi paradata accanto alle US

#### Phase 4: Paradata Grouping (PRIORITÀ ALTA)
- [ ] Modificare `ParadataGenerator` per creare `ParadataNodeGroup`
- [ ] Raggruppare Property+Extractor+Document in GroupNode
- [ ] Collegare GroupNode alla US con edge `has_paradata_nodegroup`
- [ ] Non creare più edge singoli US→Property

#### Phase 5: Integration & Testing
- [ ] Integrare tutti i generator nel `GraphMLExporter`
- [ ] Test con file EM esistenti (round-trip import→export→import)
- [ ] Validare visualmente in yEd
- [ ] Verificare compatibilità con EM-blender-tools

### 7. Riferimenti Codice Esistente

**Da studiare nell'importer**:
- `extract_epochs()` → come vengono letti i TableNode
- `handle_group_node()` → come vengono processati i GroupNode
- `determine_group_node_type_by_color()` → mapping colori→tipi
- `EM_extract_group_node_*()` → estrazione metadati gruppi

**File chiave**:
- `/src/s3dgraphy/importer/import_graphml.py` (linee 860-960, 964-1050)
- Existing GraphML files in EM projects (come riferimento visivo)

### 8. Backward Compatibility

**Mantenere**:
- Export "flat" come opzione `flat_mode=True`
- Shape mappings attuali per nodi singoli
- Edge styles e line types

**Aggiungere**:
- Parameter `em_mode=True` per export EM-compliant
- Auto-detection delle epoche da nodi EpochNode esistenti
- Fallback a flat se mancano epoche

---

## 9. XML Templates Estratti da TempluMare_EM_converted_converted.graphml

### Template TableNode (Swimlanes)
```xml
<node id="n0" yfiles.foldertype="group">
  <data key="d6">
    <y:TableNode configuration="YED_TABLE_NODE">
      <y:Geometry height="2284.4" width="2584.1" x="-29.0" y="-35.0"/>
      <y:NodeLabel>Temple [ID:GT16; ORCID:0000-0002-1825-0097]</y:NodeLabel>
      <y:Table>
        <y:Rows>
          <y:Row height="66.0" id="row_2" minimumHeight="50.0"/>
          <y:Row height="66.0" id="row_0" minimumHeight="50.0"/>
          <y:Row height="2122.4" id="row_1" minimumHeight="50.0"/>
        </y:Rows>
      </y:Table>
      <y:NodeLabel backgroundColor="#CCFFCC">
        <y:RowNodeLabelModelParameter id="row_0"/>
        Post antiquity [start:200;end:1800]
      </y:NodeLabel>
      <!-- More epoch labels -->
    </y:TableNode>
  </data>
  <graph edgedefault="directed" id="n0:">
    <!-- US nodes and groups here -->
  </graph>
</node>
```

### Template ProxyAutoBoundsNode (ParadataNodeGroup)
```xml
<node id="n0::n3::n3" yfiles.foldertype="folder">
  <data key="d6">
    <y:ProxyAutoBoundsNode>
      <y:Realizers active="1">
        <y:GroupNode>
          <y:Geometry height="427.7" width="376.4" x="891.6" y="948.0"/>
          <y:Fill color="#F5F5F5" transparent="false"/>
          <y:BorderStyle color="#000000" type="dashed" width="1.0"/>
          <y:NodeLabel alignment="right" autoSizePolicy="node_width"
                       backgroundColor="#FFCC99" borderDistance="0.0"
                       fontFamily="Dialog" fontSize="15" fontStyle="plain"
                       hasLineColor="false" height="21.7"
                       horizontalTextPosition="center" iconTextGap="4"
                       modelName="internal" modelPosition="t"
                       textColor="#000000" verticalTextPosition="bottom"
                       visible="true" width="376.4" x="0.0"
                       xml:space="preserve" y="0.0">USV106_PD</y:NodeLabel>
          <y:Shape type="roundrectangle"/>
          <y:State closed="false" closedHeight="50.0" closedWidth="50.0"
                   innerGraphDisplayEnabled="false"/>
          <y:Insets bottom="15" bottomF="15.0" left="15" leftF="15.0"
                    right="15" rightF="15.0" top="15" topF="15.0"/>
          <y:BorderInsets bottom="0" bottomF="0.0" left="0" leftF="0.0"
                          right="0" rightF="0.0" top="0" topF="0.0"/>
        </y:GroupNode>
        <y:GroupNode>
          <!-- Closed state representation -->
          <y:Geometry height="87.5" width="118.6" x="1261.5" y="995.1"/>
          <y:Fill color="#F5F5F5" transparent="false"/>
          <y:BorderStyle color="#000000" type="dashed" width="1.0"/>
          <y:NodeLabel alignment="right" autoSizePolicy="node_width"
                       backgroundColor="#FFCC99" borderDistance="0.0"
                       fontFamily="Dialog" fontSize="15" fontStyle="plain"
                       hasLineColor="false" height="21.7"
                       horizontalTextPosition="center" iconTextGap="4"
                       modelName="internal" modelPosition="t"
                       textColor="#000000" verticalTextPosition="bottom"
                       visible="true" width="118.6" x="0.0"
                       xml:space="preserve" y="0.0">USV106_PD</y:NodeLabel>
          <y:Shape type="roundrectangle"/>
          <y:State closed="true" closedHeight="87.5" closedWidth="118.6"
                   innerGraphDisplayEnabled="false"/>
          <y:Insets bottom="5" bottomF="5.0" left="5" leftF="5.0"
                    right="5" rightF="5.0" top="5" topF="5.0"/>
          <y:BorderInsets bottom="0" bottomF="0.0" left="0" leftF="0.0"
                          right="0" rightF="0.0" top="0" topF="0.0"/>
        </y:GroupNode>
      </y:Realizers>
    </y:ProxyAutoBoundsNode>
  </data>
  <graph edgedefault="directed" id="n0::n3::n3:">
    <!-- PropertyNode, ExtractorNode, DocumentNode here -->
    <node id="n0::n3::n3::n0"><!-- DocumentNode BPMN --></node>
    <node id="n0::n3::n3::n1"><!-- ExtractorNode SVG --></node>
    <node id="n0::n3::n3::n2"><!-- PropertyNode BPMN Annotation --></node>
    <!-- More property nodes -->
  </graph>
</node>
```

**OSSERVAZIONE CRITICA**: La ParadataNodeGroup ha **2 Realizers**:
- `active="0"`: Stato APERTO (gruppo espanso con contenuti visibili)
- `active="1"`: Stato CHIUSO (gruppo collassato, visualizzazione compatta)

Il `active` attribute indica quale realizer è attualmente attivo in yEd.

### Template PropertyNode (BPMN Annotation)
```xml
<node id="n0::n3::n3::n2">
  <data key="d5" xml:space="preserve"><![CDATA[Height 5.14 / 4 = 1.285]]></data>
  <data key="d6">
    <y:GenericNode configuration="com.yworks.bpmn.Artifact.withShadow">
      <y:Geometry height="30.0" width="107.9" x="1030.4" y="985.4"/>
      <y:Fill color="#FFFFFFE6" transparent="false"/>
      <y:BorderStyle color="#000000" type="line" width="1.0"/>
      <y:NodeLabel alignment="center" autoSizePolicy="content"
                   fontFamily="Dialog" fontSize="12" fontStyle="plain"
                   hasBackgroundColor="false" hasLineColor="false"
                   height="18.1" horizontalTextPosition="center"
                   iconTextGap="4" modelName="custom" textColor="#000000"
                   verticalTextPosition="bottom" visible="true"
                   width="107.0" x="0.4" xml:space="preserve" y="5.9">Dimension.height
        <y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel>
        <y:ModelParameter>
          <y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0"
                                          nodeRatioX="0.0" nodeRatioY="0.0"
                                          offsetX="0.0" offsetY="0.0"
                                          upX="0.0" upY="-1.0"/>
        </y:ModelParameter>
      </y:NodeLabel>
      <y:StyleProperties>
        <y:Property class="java.awt.Color" name="com.yworks.bpmn.icon.line.color" value="#000000"/>
        <y:Property class="java.awt.Color" name="com.yworks.bpmn.icon.fill2" value="#d4d4d4cc"/>
        <y:Property class="java.awt.Color" name="com.yworks.bpmn.icon.fill" value="#ffffffe6"/>
        <y:Property class="com.yworks.yfiles.bpmn.view.BPMNTypeEnum" name="com.yworks.bpmn.type" value="ARTIFACT_TYPE_ANNOTATION"/>
      </y:StyleProperties>
    </y:GenericNode>
  </data>
</node>
```

### Template DocumentNode (BPMN Data Object)
```xml
<node id="n0::n3::n3::n0">
  <data key="d5" xml:space="preserve"><![CDATA[Lintel = 1/4 or 1/5 of the whole column]]></data>
  <data key="d6">
    <y:GenericNode configuration="com.yworks.bpmn.Artifact.withShadow">
      <y:Geometry height="63.8" width="42.8" x="1038.7" y="1149.6"/>
      <y:Fill color="#FFFFFFE6" transparent="false"/>
      <y:BorderStyle color="#000000" type="line" width="1.0"/>
      <y:NodeLabel alignment="center" autoSizePolicy="content"
                   fontFamily="Dialog" fontSize="8" fontStyle="plain"
                   hasBackgroundColor="false" hasLineColor="false"
                   height="13.4" horizontalTextPosition="center"
                   iconTextGap="4" modelName="internal" modelPosition="c"
                   textColor="#000000" verticalTextPosition="bottom"
                   visible="true" width="22.6" x="10.1"
                   xml:space="preserve" y="25.2">D.05</y:NodeLabel>
      <y:StyleProperties>
        <y:Property class="java.awt.Color" name="com.yworks.bpmn.icon.line.color" value="#000000"/>
        <y:Property class="com.yworks.yfiles.bpmn.view.DataObjectTypeEnum" name="com.yworks.bpmn.dataObjectType" value="DATA_OBJECT_TYPE_PLAIN"/>
        <y:Property class="java.awt.Color" name="com.yworks.bpmn.icon.fill2" value="#d4d4d4cc"/>
        <y:Property class="java.awt.Color" name="com.yworks.bpmn.icon.fill" value="#ffffffe6"/>
        <y:Property class="com.yworks.yfiles.bpmn.view.BPMNTypeEnum" name="com.yworks.bpmn.type" value="ARTIFACT_TYPE_DATA_OBJECT"/>
      </y:StyleProperties>
    </y:GenericNode>
  </data>
</node>
```

### Template ExtractorNode (SVG Node)
```xml
<node id="n0::n3::n3::n1">
  <data key="d5" xml:space="preserve"><![CDATA[Lintel = 1/4 of whole column]]></data>
  <data key="d6">
    <y:SVGNode>
      <y:Geometry height="25.0" width="25.0" x="1071.8" y="1091.1"/>
      <y:Fill color="#CCCCFF" transparent="false"/>
      <y:BorderStyle color="#000000" type="line" width="1.0"/>
      <y:NodeLabel alignment="center" autoSizePolicy="content"
                   borderDistance="0.0" fontFamily="Dialog" fontSize="10"
                   fontStyle="plain" hasBackgroundColor="false"
                   hasLineColor="false" height="15.8"
                   horizontalTextPosition="center" iconTextGap="4"
                   modelName="corners" modelPosition="nw"
                   textColor="#000000" underlinedText="true"
                   verticalTextPosition="bottom" visible="true"
                   width="43.1" x="-43.1" xml:space="preserve" y="-15.8">D.05.02</y:NodeLabel>
      <y:SVGNodeProperties usingVisualBounds="true"/>
      <y:SVGModel svgBoundsPolicy="0">
        <y:SVGContent refid="1"/>
      </y:SVGModel>
    </y:SVGNode>
  </data>
</node>
```

**NOTA SVG**: L'SVGContent ha `refid="1"` che riferisce a una definizione SVG nel header del GraphML (non estratta qui, ma presente nel file completo).

### Template ActivityNodeGroup (#CCFFFF cyan)
```xml
<node id="n0::n3" yfiles.foldertype="group">
  <data key="d6">
    <y:ProxyAutoBoundsNode>
      <y:Realizers active="0">
        <y:GroupNode>
          <y:Geometry height="449.7" width="273.3" x="1205.6" y="647.9"/>
          <y:Fill color="#F5F5F5" transparent="false"/>
          <y:BorderStyle color="#000000" type="dashed" width="1.0"/>
          <y:NodeLabel alignment="right" autoSizePolicy="node_width"
                       backgroundColor="#CCFFFF" borderDistance="0.0"
                       fontFamily="Dialog" fontSize="15" fontStyle="plain"
                       hasLineColor="false" height="21.7"
                       horizontalTextPosition="center" iconTextGap="4"
                       modelName="internal" modelPosition="t"
                       textColor="#000000" verticalTextPosition="bottom"
                       visible="true" width="273.3" x="0.0"
                       xml:space="preserve" y="0.0">VAct.03 Lintel of the columnade</y:NodeLabel>
          <y:Shape type="roundrectangle"/>
          <y:State closed="false" closedHeight="50.0" closedWidth="50.0"
                   innerGraphDisplayEnabled="false"/>
          <y:Insets bottom="15" bottomF="15.0" left="15" leftF="15.0"
                    right="15" rightF="15.0" top="15" topF="15.0"/>
          <y:BorderInsets bottom="0" bottomF="0.0" left="2" leftF="1.5"
                          right="0" rightF="0.0" top="0" topF="0.0"/>
        </y:GroupNode>
        <!-- Closed state GroupNode -->
      </y:Realizers>
    </y:ProxyAutoBoundsNode>
  </data>
  <graph edgedefault="directed" id="n0::n3:">
    <!-- USV nodes and nested ParadataNodeGroup here -->
    <node id="n0::n3::n0"><!-- USV106 hexagon --></node>
    <node id="n0::n3::n1"><!-- USV105 hexagon --></node>
    <node id="n0::n3::n2"><!-- USV149 hexagon --></node>
    <node id="n0::n3::n3" yfiles.foldertype="folder">
      <!-- ParadataNodeGroup nested here -->
    </node>
  </graph>
</node>
```

## 10. Gerarchia di Nesting Completa

```
TableNode (n0) - Swimlanes Epoche
├── graph id="n0:"
    ├── ActivityNodeGroup (n0::n3) - #CCFFFF
    │   ├── graph id="n0::n3:"
    │       ├── StratigraphicNode (n0::n3::n0) - USV106
    │       ├── StratigraphicNode (n0::n3::n1) - USV105
    │       ├── StratigraphicNode (n0::n3::n2) - USV149
    │       └── ParadataNodeGroup (n0::n3::n3) - #FFCC99
    │           ├── graph id="n0::n3::n3:"
    │               ├── DocumentNode (n0::n3::n3::n0) - BPMN Data Object
    │               ├── ExtractorNode (n0::n3::n3::n1) - SVG Node
    │               ├── PropertyNode (n0::n3::n3::n2) - BPMN Annotation
    │               ├── PropertyNode (n0::n3::n3::n3) - BPMN Annotation
    │               └── PropertyNode (n0::n3::n3::n4) - BPMN Annotation
```

**PATTERN ID NESTING**:
- Swimlane root: `n0`
- Child nel swimlane: `n0::nX` (dove X = index)
- Child nel gruppo: `n0::nX::nY`
- Child nel gruppo nested: `n0::nX::nY::nZ`

**PATTERN GRAPH ID**:
- Graph del swimlane: `n0:`
- Graph del gruppo livello 1: `n0::n3:`
- Graph del gruppo livello 2: `n0::n3::n3:`

**REGOLA**: Graph ID = Node ID + `:` (colon finale)

## Next Steps

1. Implementare `TableNodeGenerator` con template completo (2-3 ore)
2. Implementare `GroupNodeGenerator` con ProxyAutoBoundsNode e dual Realizers (2-3 ore)
3. Implementare generators per PropertyNode, DocumentNode, ExtractorNode con BPMN/SVG shapes (2 ore)
4. Refactorare `ParadataGenerator` per creare ParadataNodeGroup container (1 ora)
5. Implementare ID nesting logic (n0::n3::n3::n0 pattern) (1 ora)
6. Integrare nel main `GraphMLExporter` (1 ora)
7. Test & validation con round-trip (1 ora)

**Stima totale**: 10-12 ore di sviluppo
