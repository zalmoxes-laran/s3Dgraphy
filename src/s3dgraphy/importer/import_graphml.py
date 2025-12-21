# s3Dgraphy/import_graphml.py

import xml.etree.ElementTree as ET
from ..graph import Graph
from ..nodes.stratigraphic_node import (
    Node, StratigraphicNode, ContinuityNode)
from ..nodes.paradata_node import ParadataNode
from ..nodes.document_node import DocumentNode
from ..nodes.combiner_node import CombinerNode
from ..nodes.extractor_node import ExtractorNode
from ..nodes.property_node import PropertyNode
from ..nodes.epoch_node import EpochNode
from ..nodes.group_node import GroupNode, ParadataNodeGroup, ActivityNodeGroup, TimeBranchNodeGroup
from ..nodes.link_node import *
from ..edges.edge import Edge, EDGE_TYPES
from ..edges import get_connections_datamodel
from ..utils.utils import convert_shape2type, get_stratigraphic_node_class
import re
import uuid

class GraphMLImporter:
    """
    Classe per importare grafi da file GraphML.

    Attributes:
        filepath (str): Percorso del file GraphML da importare.
        graph (Graph): Istanza della classe Graph in cui verrà caricato il grafo.
    """

    def __init__(self, filepath, graph=None):
        self.filepath = filepath
        self.graph = graph if graph is not None else Graph(graph_id="imported_graph")
        # Dizionario per la deduplicazione dei nodi documento
        self.document_nodes_map = {}  # nome documento -> node_id
        self.duplicate_id_map = {}    # id originale -> id deduplicated
        self.id_mapping = {}          # id originale -> uuid
        # Get connections datamodel for edge validation
        self._connections_datamodel = get_connections_datamodel()
        # Key mapping for dynamic GraphML parsing
        self.key_map = {'node': {}, 'edge': {}}  # Mappa attr_name -> key_id
        # Track if we need to update the GraphML file with generated UUIDs
        self.graphml_tree = None  # Will store the parsed XML tree for slipback

    def build_key_mapping(self, tree):
        """
        Costruisce una mappa dinamica delle chiavi GraphML.
        Questo permette di gestire file GraphML con campi custom (EMID, URI)
        senza hardcodare i key ID (d4, d5, d6...).

        Args:
            tree: XML ElementTree del file GraphML

        Returns:
            dict: Mappa con struttura {'node': {attr_name: key_id}, 'edge': {attr_name: key_id}}
        """
        key_map = {
            'node': {},  # Per nodi
            'edge': {}   # Per edge
        }

        # Scansiona tutti gli elementi <key> nel GraphML
        for key_elem in tree.findall('.//{http://graphml.graphdrawing.org/xmlns}key'):
            key_id = key_elem.attrib.get('id')
            attr_name = key_elem.attrib.get('attr.name')
            key_for = key_elem.attrib.get('for')

            if attr_name and key_id:
                if key_for == 'node':
                    key_map['node'][attr_name] = key_id
                elif key_for == 'edge':
                    key_map['edge'][attr_name] = key_id

        print(f"[GraphML Parser] Built key mapping:")
        print(f"  Node keys: {key_map['node']}")
        print(f"  Edge keys: {key_map['edge']}")

        return key_map

    def extract_custom_fields(self, element, entity_type='node'):
        """
        Estrae i campi custom EMID e URI se presenti nel GraphML.

        Args:
            element: Elemento XML (node o edge)
            entity_type: 'node' o 'edge'

        Returns:
            dict: {'EMID': valore, 'URI': valore} se presenti, altrimenti {}
        """
        custom_fields = {}
        ns = 'http://graphml.graphdrawing.org/xmlns'

        # Estrai EMID
        if 'EMID' in self.key_map[entity_type]:
            emid_key = self.key_map[entity_type]['EMID']
            emid_elem = element.find(f'./{{{ns}}}data[@key="{emid_key}"]')
            if emid_elem is not None and emid_elem.text:
                custom_fields['EMID'] = emid_elem.text.strip()

        # Estrai URI
        if 'URI' in self.key_map[entity_type]:
            uri_key = self.key_map[entity_type]['URI']
            uri_elem = element.find(f'./{{{ns}}}data[@key="{uri_key}"]')
            if uri_elem is not None and uri_elem.text:
                custom_fields['URI'] = uri_elem.text.strip()

        return custom_fields

    def extract_graph_id_and_code(self, tree):
        """
        Extracts the ID and code of the graph from the GraphML file.
        
        Args:
            tree: XML ElementTree of the GraphML file
            
        Returns:
            tuple: (graph_id, graph_code) where graph_id is the actual ID and graph_code is the
                human-readable code (e.g. VDL16). Both could be None if not found.
        """
        import uuid

        graph_id = None
        graph_code = None
        
        # Look for NodeLabel to find the graph header
        for nodelabel in tree.findall('.//{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
            RowNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
            ColumnNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}ColumnNodeLabelModelParameter')
            
            if RowNodeLabelModelParameter is None and ColumnNodeLabelModelParameter is None:
                try:
                    stringa_pulita, vocabolario = self.estrai_stringa_e_vocabolario(nodelabel.text)
                    
                    # Extract ID if present in vocabulary
                    if 'ID' in vocabolario:
                        graph_code = vocabolario['ID']
                        #print(f"Found graph code from vocabulary: {graph_code}")
                    
                    # If there's a specific ID in the vocabulary, use it
                    if 'graph_id' in vocabolario:
                        graph_id = vocabolario['graph_id']
                        #print(f"Found specific graph ID: {graph_id}")
                    
                    break
                except Exception as e:
                    print(f"Error extracting graph ID from node label: {e}")
        
        # If we didn't find a graph_code, use MISSINGCODE
        if not graph_code or graph_code == "site_id":
            graph_code = "MISSINGCODE"
            #print(f"Using fallback graph code: {graph_code}")
        
        # If we don't have a graph_id, generate a UUID
        if not graph_id:
            graph_id = str(uuid.uuid4())
            #print(f"Generated graph ID from UUID: {graph_id}")
        
        return graph_id, graph_code

    def parse(self):
        """
        Esegue il parsing del file GraphML e popola l'istanza di Graph.

        Returns:
            Graph: Istanza di Graph popolata con nodi e archi dal file GraphML.
        """
        import uuid

        tree = ET.parse(self.filepath)

        # Salva il tree per lo slipback
        self.graphml_tree = tree

        # Costruisci la mappa dinamica delle chiavi GraphML
        self.key_map = self.build_key_mapping(tree)

        # Prima estrai il codice del grafo
        graph_id, graph_code = self.extract_graph_id_and_code(tree)
        
        # Se abbiamo trovato un codice, aggiungilo come attributo al grafo
        if graph_code:
            self.graph.attributes['graph_code'] = graph_code
            
        # Genera un ID univoco per il grafo se non esiste
        if not graph_id:
            graph_id = str(uuid.uuid4())
        
        # Imposta l'ID univoco nel grafo
        self.graph.graph_id = graph_id
        
        # Memorizza gli ID originali per la mappatura
        self.id_mapping = {}  # {original_id: uuid_id}
        
        # Prosegui con il parsing normale
        self.parse_nodes(tree)
        self.parse_edges(tree)

        # Aggiungi qui la nuova funzionalità per collegare PropertyNode dai ParadataNodeGroup
        # Impostare verbose=True per avere output dettagliati durante il debug
        stats = self.graph.connect_paradatagroup_propertynode_to_stratigraphic(verbose=False)
        if stats["connections_created"] > 0:
            pass


        self.connect_nodes_to_epochs()

        br_nodes = [n for n in self.graph.nodes if hasattr(n, 'node_type') and n.node_type == "BR"]
        #print(f"\nTotal BR nodes included in the graph: {len(br_nodes)}")
        for node in br_nodes:
            pass

        # Verifica se i nodi BR esistono nel grafo
        if len(br_nodes) == 0:
            print("\nWARNING: No BR (continuity) nodes found in the graph!")
            # print("Looking for nodes with _continuity in description...")

            for node in self.graph.nodes:
                if hasattr(node, 'description') and '_continuity' in node.description:
                    pass

        # FASE 2: Slipback immediato - scrivi UUID nel GraphML
        print("\n[GraphML Parser] Performing slipback - writing UUIDs to GraphML...")
        self.slipback_uuids_to_graphml()

        return self.graph

    def slipback_uuids_to_graphml(self):
        """
        FASE 2: Slipback immediato - Aggiorna il file GraphML con gli UUID generati/riutilizzati.
        Popola i campi EMID con gli UUID di nodi ed edge creati da s3Dgraphy.
        """
        if not self.graphml_tree:
            print("[GraphML Slipback] ERROR: No GraphML tree available for slipback")
            return

        # Namespace GraphML
        ns = {'gml': 'http://graphml.graphdrawing.org/xmlns'}

        # Assicurati che esistano le chiavi EMID e URI nel GraphML
        root = self.graphml_tree.getroot()
        self._ensure_custom_keys(root)

        # Conta aggiornamenti
        nodes_updated = 0
        edges_updated = 0

        # Aggiorna nodi
        for node_elem in self.graphml_tree.findall('.//gml:node', ns):
            original_id = node_elem.attrib.get('id')
            if original_id in self.id_mapping:
                uuid_val = self.id_mapping[original_id]
                # Cerca il nodo nel grafo per ottenere URI
                graph_node = self.graph.find_node_by_id(uuid_val)
                node_uri = graph_node.attributes.get('URI') if graph_node and hasattr(graph_node, 'attributes') else None

                # Aggiorna EMID e URI nel GraphML
                if self._update_node_custom_fields(node_elem, uuid_val, node_uri):
                    nodes_updated += 1

        # Aggiorna edge
        for edge_elem in self.graphml_tree.findall('.//gml:edge', ns):
            original_edge_id = edge_elem.attrib.get('id')
            # Trova l'edge nel grafo
            for edge in self.graph.edges:
                if hasattr(edge, 'attributes') and edge.attributes.get('original_edge_id') == original_edge_id:
                    edge_uuid = edge.edge_id
                    edge_uri = edge.attributes.get('URI')

                    # Aggiorna EMID e URI nel GraphML
                    if self._update_edge_custom_fields(edge_elem, edge_uuid, edge_uri):
                        edges_updated += 1
                    break

        # Salva il GraphML aggiornato
        output_path = self.filepath  # Sovrascrive il file originale
        try:
            self.graphml_tree.write(output_path, encoding='UTF-8', xml_declaration=True)
            print(f"[GraphML Slipback] SUCCESS: Updated {nodes_updated} nodes and {edges_updated} edges")
            print(f"[GraphML Slipback] Saved to: {output_path}")
        except Exception as e:
            print(f"[GraphML Slipback] ERROR saving file: {e}")

    def _ensure_custom_keys(self, root):
        """Assicura che le chiavi EMID e URI esistano nel GraphML."""
        ns = {'gml': 'http://graphml.graphdrawing.org/xmlns'}

        # Controlla se EMID e URI keys esistono già
        existing_keys = {}
        for key_elem in root.findall('.//gml:key', ns):
            attr_name = key_elem.attrib.get('attr.name')
            if attr_name:
                existing_keys[attr_name] = key_elem

        # Trova il prossimo ID disponibile
        all_keys = root.findall('.//gml:key', ns)
        max_id = 0
        for key_elem in all_keys:
            key_id = key_elem.attrib.get('id', '')
            if key_id.startswith('d'):
                try:
                    num = int(key_id[1:])
                    max_id = max(max_id, num)
                except ValueError:
                    pass

        # Crea EMID key se non esiste
        if 'EMID' not in existing_keys:
            emid_key_id = f"d{max_id + 1}"
            max_id += 1

            # Crea key per nodi
            emid_node_key = ET.Element('{http://graphml.graphdrawing.org/xmlns}key')
            emid_node_key.attrib['attr.name'] = 'EMID'
            emid_node_key.attrib['attr.type'] = 'string'
            emid_node_key.attrib['for'] = 'node'
            emid_node_key.attrib['id'] = emid_key_id
            default_elem = ET.SubElement(emid_node_key, '{http://graphml.graphdrawing.org/xmlns}default')
            default_elem.attrib['{http://www.w3.org/XML/1998/namespace}space'] = 'preserve'
            root.insert(list(root).index(root.find('.//gml:graph', ns)), emid_node_key)

            # Crea key per edge
            emid_edge_key = ET.Element('{http://graphml.graphdrawing.org/xmlns}key')
            emid_edge_key.attrib['attr.name'] = 'EMID'
            emid_edge_key.attrib['attr.type'] = 'string'
            emid_edge_key.attrib['for'] = 'edge'
            emid_edge_key.attrib['id'] = f"d{max_id + 1}"
            max_id += 1
            default_elem = ET.SubElement(emid_edge_key, '{http://graphml.graphdrawing.org/xmlns}default')
            default_elem.attrib['{http://www.w3.org/XML/1998/namespace}space'] = 'preserve'
            root.insert(list(root).index(root.find('.//gml:graph', ns)), emid_edge_key)

            print(f"[GraphML Slipback] Created EMID keys")

        # Crea URI key se non esiste (stessa logica)
        if 'URI' not in existing_keys:
            uri_node_key = ET.Element('{http://graphml.graphdrawing.org/xmlns}key')
            uri_node_key.attrib['attr.name'] = 'URI'
            uri_node_key.attrib['attr.type'] = 'string'
            uri_node_key.attrib['for'] = 'node'
            uri_node_key.attrib['id'] = f"d{max_id + 1}"
            max_id += 1
            default_elem = ET.SubElement(uri_node_key, '{http://graphml.graphdrawing.org/xmlns}default')
            default_elem.attrib['{http://www.w3.org/XML/1998/namespace}space'] = 'preserve'
            root.insert(list(root).index(root.find('.//gml:graph', ns)), uri_node_key)

            uri_edge_key = ET.Element('{http://graphml.graphdrawing.org/xmlns}key')
            uri_edge_key.attrib['attr.name'] = 'URI'
            uri_edge_key.attrib['attr.type'] = 'string'
            uri_edge_key.attrib['for'] = 'edge'
            uri_edge_key.attrib['id'] = f"d{max_id + 1}"
            max_id += 1
            default_elem = ET.SubElement(uri_edge_key, '{http://graphml.graphdrawing.org/xmlns}default')
            default_elem.attrib['{http://www.w3.org/XML/1998/namespace}space'] = 'preserve'
            root.insert(list(root).index(root.find('.//gml:graph', ns)), uri_edge_key)

            print(f"[GraphML Slipback] Created URI keys")

    def _update_node_custom_fields(self, node_elem, uuid_val, uri_val=None):
        """Aggiorna i campi EMID e URI di un nodo nel GraphML."""
        ns = 'http://graphml.graphdrawing.org/xmlns'

        # Trova le chiavi per EMID e URI
        emid_key = self.key_map['node'].get('EMID')
        uri_key = self.key_map['node'].get('URI')

        updated = False

        # Aggiorna EMID
        if emid_key:
            emid_data = node_elem.find(f'.//{{{ns}}}data[@key="{emid_key}"]')
            if emid_data is None:
                # Crea nuovo elemento data
                emid_data = ET.Element(f'{{{ns}}}data')
                emid_data.attrib['key'] = emid_key
                node_elem.insert(0, emid_data)  # Inserisci all'inizio
            emid_data.text = uuid_val
            updated = True

        # Aggiorna URI se presente
        if uri_val and uri_key:
            uri_data = node_elem.find(f'.//{{{ns}}}data[@key="{uri_key}"]')
            if uri_data is None:
                uri_data = ET.Element(f'{{{ns}}}data')
                uri_data.attrib['key'] = uri_key
                node_elem.insert(1 if emid_key else 0, uri_data)
            uri_data.text = uri_val
            updated = True

        return updated

    def _update_edge_custom_fields(self, edge_elem, uuid_val, uri_val=None):
        """Aggiorna i campi EMID e URI di un edge nel GraphML."""
        ns = 'http://graphml.graphdrawing.org/xmlns'

        # Trova le chiavi per EMID e URI
        emid_key = self.key_map['edge'].get('EMID')
        uri_key = self.key_map['edge'].get('URI')

        updated = False

        # Aggiorna EMID
        if emid_key:
            emid_data = edge_elem.find(f'.//{{{ns}}}data[@key="{emid_key}"]')
            if emid_data is None:
                emid_data = ET.Element(f'{{{ns}}}data')
                emid_data.attrib['key'] = emid_key
                edge_elem.insert(0, emid_data)
            emid_data.text = uuid_val
            updated = True

        # Aggiorna URI se presente
        if uri_val and uri_key:
            uri_data = edge_elem.find(f'.//{{{ns}}}data[@key="{uri_key}"]')
            if uri_data is None:
                uri_data = ET.Element(f'{{{ns}}}data')
                uri_data.attrib['key'] = uri_key
                edge_elem.insert(1 if emid_key else 0, uri_data)
            uri_data.text = uri_val
            updated = True

        return updated

    def parse_nodes(self, tree):
        """
        Esegue il parsing dei nodi dal file GraphML.
        """
        # Prima raccogli tutti gli ID dei nodi per identificare potenziali duplicati
        all_node_ids = {}  # {node_id: count}
        
        for node_element in tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node'):
            node_id = self.getnode_id(node_element)
            all_node_ids[node_id] = all_node_ids.get(node_id, 0) + 1
        
        # Registra i nodi con più occorrenze
        duplicate_ids = {node_id for node_id, count in all_node_ids.items() if count > 1}
        if duplicate_ids:
            #print(f"Attenzione: rilevati {len(duplicate_ids)} ID di nodi duplicati nel file GraphML:")
            for node_id in duplicate_ids:
                pass
        
        # Ora processa i nodi normalmente
        for node_element in tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node'):
            node_type = self._check_node_type(node_element)
            if node_type == 'node_simple':
                self.process_node_element(node_element)
            elif node_type == 'node_swimlane':
                self.extract_epochs(node_element, self.graph)
            elif node_type == 'node_group':
                self.handle_group_node(node_element)

    def parse_edges(self, tree):
        """
        Esegue il parsing degli archi dal file GraphML.
        """
        alledges = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}edge')
        #print(f"Found {len(alledges)} edges in GraphML")
        
        # Prima traccia tutti gli ID originali e le loro relazioni
        edge_original_mappings = []
        
        for edge in alledges:
            original_edge_id = str(edge.attrib['id'])
            original_source_id = str(edge.attrib['source'])
            original_target_id = str(edge.attrib['target'])
            edge_type = self.EM_extract_edge_type(edge)

            # Estrai campi custom EMID e URI per l'edge
            edge_custom_fields = self.extract_custom_fields(edge, 'edge')

            # Gestisci gli ID duplicati
            if original_source_id in self.duplicate_id_map:
                #print(f"Remapping source: {original_source_id} -> {self.duplicate_id_map[original_source_id]}")
                original_source_id = self.duplicate_id_map[original_source_id]
            if original_target_id in self.duplicate_id_map:
                #print(f"Remapping target: {original_target_id} -> {self.duplicate_id_map[original_target_id]}")
                original_target_id = self.duplicate_id_map[original_target_id]

            # Salva le mappature originali (source/target mantengono la direzione del GraphML)
            # GraphML ha già source=recent, target=ancient, che corrisponde a "is_after"
            edge_original_mappings.append({
                'original_edge_id': original_edge_id,
                'original_source_id': original_source_id,
                'original_target_id': original_target_id,
                'edge_type': edge_type,
                'custom_fields': edge_custom_fields
            })
        
        # Ora crea gli archi usando gli UUID
        for mapping in edge_original_mappings:
            original_edge_id = mapping['original_edge_id']
            original_source_id = mapping['original_source_id']
            original_target_id = mapping['original_target_id']
            base_edge_type = mapping['edge_type']
            edge_custom_fields = mapping.get('custom_fields', {})

            # Ottieni gli UUID corrispondenti
            source_uuid = self.id_mapping.get(original_source_id)
            target_uuid = self.id_mapping.get(original_target_id)

            if source_uuid is not None and target_uuid is not None:
                try:
                    # FASE 3: Se esiste EMID per l'edge, riutilizzalo come UUID, altrimenti generane uno nuovo
                    if 'EMID' in edge_custom_fields and edge_custom_fields['EMID']:
                        edge_uuid = edge_custom_fields['EMID']
                        print(f"[GraphML Parser] Reusing existing EMID as edge ID: {edge_uuid} for edge {original_edge_id}")
                    else:
                        # Genera un nuovo UUID per l'edge
                        edge_uuid = str(uuid.uuid4())

                    # Get the source and target nodes for edge type enhancement
                    source_node = self.graph.find_node_by_id(source_uuid)
                    target_node = self.graph.find_node_by_id(target_uuid)

                    # Enhance the edge type based on node types
                    enhanced_edge_type = self.enhance_edge_type(base_edge_type, source_node, target_node)

                    # Crea l'arco con il tipo avanzato
                    edge = self.graph.add_edge(edge_uuid, source_uuid, target_uuid, enhanced_edge_type)

                    # Aggiungi attributi di tracciamento
                    edge.attributes = edge.attributes if hasattr(edge, 'attributes') else {}
                    edge.attributes['original_edge_id'] = original_edge_id
                    edge.attributes['original_source_id'] = original_source_id
                    edge.attributes['original_target_id'] = original_target_id

                    # Aggiungi URI se presente
                    if 'URI' in edge_custom_fields and edge_custom_fields['URI']:
                        edge.attributes['URI'] = edge_custom_fields['URI']
                    
                except Exception as e:
                    print(f"Error adding edge {original_edge_id} ({edge_type}): {e}")
            else:
                # Report specifico sulla mappatura mancante
                if source_uuid is None:
                    print(f"Missing source UUID for edge {original_edge_id}: {original_source_id}")
                if target_uuid is None:
                    print(f"Missing target UUID for edge {original_edge_id}: {original_target_id}")
                
                print(f"Warning: Could not create edge {original_edge_id} - Source: {original_source_id} -> Target: {original_target_id}")
                
    def process_node_element(self, node_element):
        """
        Processa un elemento nodo dal file GraphML e lo aggiunge al grafo.

        Args:
            node_element (Element): Elemento nodo XML dal file GraphML.
        """

        node_counter = getattr(self, '_node_counter', 0)
        self._node_counter = node_counter + 1

        # Estrai l'ID originale
        original_id = self.getnode_id(node_element)

        # Se abbiamo già mappato questo ID originale, non creare un nuovo nodo
        if original_id in self.id_mapping:
            #print(f"Skipping already processed node with original ID: {original_id}")
            return

        # Estrai campi custom EMID e URI
        custom_fields = self.extract_custom_fields(node_element, 'node')

        # FASE 3: Se esiste EMID, riutilizzalo come UUID, altrimenti generane uno nuovo
        if 'EMID' in custom_fields and custom_fields['EMID']:
            uuid_id = custom_fields['EMID']
            print(f"[GraphML Parser] Reusing existing EMID as node ID: {uuid_id} for node {original_id}")
        else:
            # Genera un nuovo UUID per questo nodo
            uuid_id = str(uuid.uuid4())
            print(f"[GraphML Parser] Generated new UUID: {uuid_id} for node {original_id}")

        # Memorizza la mappatura per uso futuro
        self.id_mapping[original_id] = uuid_id

        # Estrai URI se presente
        node_uri = custom_fields.get('URI', None)

        if self.EM_check_node_us(node_element):
            # Creazione del nodo stratigrafico e aggiunta al grafo
            nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor, borderstyle = self.EM_extract_node_name(node_element)
            
            stratigraphic_type = convert_shape2type(nodeshape, borderstyle)[0]
            node_class = get_stratigraphic_node_class(stratigraphic_type)  # Ottieni la classe usando la funzione
            stratigraphic_node = node_class(
                node_id=uuid_id,
                name=nodename,
                description=nodedescription
            )

            # Aggiungi attributi di tracciamento
            stratigraphic_node.attributes['original_id'] = original_id
            stratigraphic_node.attributes['graph_id'] = self.graph.graph_id

            # Aggiunta di runtime properties
            stratigraphic_node.attributes['shape'] = nodeshape
            stratigraphic_node.attributes['y_pos'] = float(node_y_pos)
            stratigraphic_node.attributes['fill_color'] = fillcolor
            stratigraphic_node.attributes['border_style'] = borderstyle

            # Aggiungi URI se presente
            if node_uri:
                stratigraphic_node.attributes['URI'] = node_uri

            #print(f"Node {self._node_counter}: {stratigraphic_node.node_id} (Original ID: {original_id}, Type: {stratigraphic_node.node_type})")

            self.graph.add_node(stratigraphic_node)

        elif self.EM_check_node_document(node_element):
            # Creazione del nodo documento e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_document_node(node_element)
            # Controlla se esiste già un documento con lo stesso nome

            if nodename in self.document_nodes_map:
                # Ottieni UUID del documento esistente
                existing_uuid = self.document_nodes_map[nodename]
                
                # Cerca il nodo documento esistente
                existing_doc = self.graph.find_node_by_id(existing_uuid)
                
                if existing_doc and hasattr(existing_doc, 'attributes'):
                    # Ottieni l'ID originale del documento esistente
                    existing_original_id = existing_doc.attributes.get('original_id')
                    
                    if existing_original_id:
                        # Mappa l'ID originale del nuovo documento all'ID originale del documento esistente
                        self.duplicate_id_map[original_id] = existing_original_id
                        pass
                    else:
                        # Non è stato possibile ottenere l'ID originale, usa l'UUID direttamente
                        self.duplicate_id_map[original_id] = existing_uuid
                        pass
                else:
                    # Non è stato possibile trovare il documento esistente, usa l'UUID direttamente
                    self.duplicate_id_map[original_id] = existing_uuid
                    pass
            else:
                # Crea nuovo documento
                document_node = DocumentNode(
                    node_id=uuid_id,
                    name=nodename,
                    description=nodedescription,
                    url=nodeurl
                )
                
                # Aggiungi attributi di tracciamento
                document_node.attributes['original_id'] = original_id
                document_node.attributes['graph_id'] = self.graph.graph_id

                # Aggiungi URI se presente
                if node_uri:
                    document_node.attributes['URI'] = node_uri

                # Aggiungi al grafo e memorizza UUID
                self.graph.add_node(document_node)
                self.document_nodes_map[nodename] = uuid_id
                # Se c'è un URL valido, crea un nodo Link
                if nodeurl and nodeurl.strip() != 'Empty':
                    link_node = self._create_link_node(document_node, nodeurl)

        elif self.EM_check_node_property(node_element):
            # Creazione del nodo proprietà e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_property_node(node_element)
            property_node = PropertyNode(
                node_id=uuid_id,
                name=nodename,
                description=nodedescription,
                value=nodeurl,
                data={},  # Popola 'data' se necessario
                url=nodeurl
            )

            # Per PropertyNode
            property_node.attributes['original_id'] = original_id
            property_node.attributes['graph_id'] = self.graph.graph_id

            # Aggiungi URI se presente
            if node_uri:
                property_node.attributes['URI'] = node_uri

            self.graph.add_node(property_node)

        elif self.EM_check_node_extractor(node_element):
            # Creazione del nodo extractor e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_extractor_node(node_element)
            extractor_node = ExtractorNode(
                node_id=uuid_id,
                name=nodename,
                description=nodedescription,
                source=nodeurl
            )
            # Per extractor_node
            extractor_node.attributes['original_id'] = original_id
            extractor_node.attributes['graph_id'] = self.graph.graph_id

            # Aggiungi URI se presente
            if node_uri:
                extractor_node.attributes['URI'] = node_uri

            self.graph.add_node(extractor_node)

            # Se c'è un URL valido, crea un nodo Link
            if nodeurl and nodeurl.strip() != 'Empty':
                link_node = self._create_link_node(extractor_node, nodeurl)


        elif self.EM_check_node_combiner(node_element):
            # Creazione del nodo combiner e aggiunta al grafo
            nodename, node_id, nodedescription, nodeurl, _ = self.EM_extract_combiner_node(node_element)
            combiner_node = CombinerNode(
                node_id=uuid_id,
                name=nodename,
                description=nodedescription,
                sources=[nodeurl]
            )

            # Per combiner_node
            combiner_node.attributes['original_id'] = original_id
            combiner_node.attributes['graph_id'] = self.graph.graph_id

            # Aggiungi URI se presente
            if node_uri:
                combiner_node.attributes['URI'] = node_uri

            self.graph.add_node(combiner_node)

        elif self.EM_check_node_continuity(node_element):
            # Creazione del nodo continuity e aggiunta al grafo
            nodedescription, node_y_pos, node_id = self.EM_extract_continuity(node_element)
            continuity_node = ContinuityNode(
                node_id=uuid_id,
                name="continuity_node",
                description=nodedescription
            )
            
            # Aggiungi attributi di tracciamento
            continuity_node.attributes['original_id'] = original_id
            continuity_node.attributes['graph_id'] = self.graph.graph_id
            continuity_node.attributes['y_pos'] = float(node_y_pos)

            # Aggiungi URI se presente
            if node_uri:
                continuity_node.attributes['URI'] = node_uri

            #print(f"Adding continuity node to graph: {continuity_node.node_id} (Original ID: {original_id})")
            self.graph.add_node(continuity_node)

        else:
            # Creazione di un nodo generico
            node_id = self.getnode_id(node_element)
            node_name = self.EM_extract_generic_node_name(node_element)
            generic_node = Node(
                node_id=uuid_id,
                name=node_name,
                #node_type="Generic",
                description=""
            )
            self.graph.add_node(generic_node)



    def _create_link_node(self, source_node, url):
        """
        Creates a Link node for a resource.

        Args:
            source_node (Node): The source node with which the link is associated
            url (str): The URL or path of the resource

        Returns:
            LinkNode: The Link node created
        """
        from ..nodes.link_node import LinkNode
        
        link_node_id = f"{source_node.node_id}_link"
        
        # Verifica se il nodo Link esiste già
        existing_link_node = self.graph.find_node_by_id(link_node_id)
        if existing_link_node:
            return existing_link_node
        
        # Se non esiste, crealo
        link_node = LinkNode(
            node_id=link_node_id,
            name=f"Link to {source_node.name}",
            description=f"Link to {source_node.description}" if source_node.description else "",
            url=url
        )
        
        self.graph.add_node(link_node)
        
        # Crea l'edge solo se non esiste già
        edge_id = f"{source_node.node_id}_has_linked_resource_{link_node_id}"
        if not self.graph.find_edge_by_id(edge_id):
            self.graph.add_edge(
                edge_id=edge_id,
                edge_source=source_node.node_id,
                edge_target=link_node.node_id,
                edge_type="has_linked_resource"
            )
        
        return link_node
        
    def handle_group_node(self, node_element):
        """
        Gestisce un nodo di tipo gruppo dal file GraphML.

        Args:
            node_element (Element): Elemento nodo XML dal file GraphML.
        """

        # Estrarre l'ID originale, il nome e la descrizione del gruppo
        original_id = self.getnode_id(node_element)

        # Estrai campi custom EMID e URI
        custom_fields = self.extract_custom_fields(node_element, 'node')

        # FASE 3: Se esiste EMID, riutilizzalo come UUID, altrimenti generane uno nuovo
        if 'EMID' in custom_fields and custom_fields['EMID']:
            uuid_id = custom_fields['EMID']
            print(f"[GraphML Parser] Reusing existing EMID as group node ID: {uuid_id} for node {original_id}")
        else:
            uuid_id = str(uuid.uuid4())
            print(f"[GraphML Parser] Generated new UUID for group node: {uuid_id} for node {original_id}")

        self.id_mapping[original_id] = uuid_id

        # Estrai URI se presente
        node_uri = custom_fields.get('URI', None)        
        
        # Estrarre l'ID, il nome e la descrizione del gruppo
        group_name = self.EM_extract_group_node_name(node_element)
        group_description = self.EM_extract_group_node_description(node_element)
        group_background_color = self.EM_extract_group_node_background_color(node_element)
        group_y_pos = self.EM_extract_group_node_y_pos(node_element)

        # Determinare il tipo di nodo gruppo basandoci sul background color
        group_node_type = self.determine_group_node_type_by_color(group_background_color)

        if group_node_type == 'ActivityNodeGroup':
            group_node = ActivityNodeGroup(
                node_id=uuid_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )
        elif group_node_type == 'ParadataNodeGroup':
            group_node = ParadataNodeGroup(
                node_id=uuid_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )
        elif group_node_type == 'TimeBranchNodeGroup':
            group_node = TimeBranchNodeGroup(
                node_id=uuid_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )
        else:
            group_node = GroupNode(
                node_id=uuid_id,
                name=group_name,
                description=group_description,
                y_pos=group_y_pos
            )

        # Aggiungi attributi di tracciamento
        group_node.attributes['original_id'] = original_id
        group_node.attributes['graph_id'] = self.graph.graph_id

        # Aggiungi URI se presente
        if node_uri:
            group_node.attributes['URI'] = node_uri

        # Aggiungere il nodo gruppo al grafo
        self.graph.add_node(group_node)

        # Processare i nodi contenuti nel gruppo
        subgraph = node_element.find('{http://graphml.graphdrawing.org/xmlns}graph')
        if subgraph is not None:
            subnodes = subgraph.findall('{http://graphml.graphdrawing.org/xmlns}node')
            for subnode in subnodes:
                subnode_original_id = self.getnode_id(subnode)
                subnode_type = self._check_node_type(subnode)
                if subnode_type == 'node_simple':
                    # Processare e aggiungere il nodo al grafo
                    self.process_node_element(subnode)
                elif subnode_type == 'node_group':
                    # Gestire ricorsivamente il sottogruppo
                    self.handle_group_node(subnode)
                elif subnode_type == 'node_swimlane':
                    # Gestire i nodi EpochNode se necessario
                    self.extract_epochs(subnode, self.graph)

                # Qui devi usare la mappatura UUID per creare l'arco
                if subnode_original_id in self.id_mapping:
                    subnode_uuid = self.id_mapping[subnode_original_id]
                    
                    # Creare l'arco appropriato in base al tipo di gruppo
                    edge_type = "generic_connection"  # Fallback sicuro
                    
                    if group_node_type == "ActivityNodeGroup":
                        edge_type = "is_in_activity"
                        edge_id_prefix = "is_in_activity"
                    elif group_node_type == "ParadataNodeGroup":
                        edge_type = "is_in_paradata_nodegroup"
                        edge_id_prefix = "is_in_paradata_nodegroup"
                    elif group_node_type == "TimeBranchNodeGroup":
                        edge_type = "is_in_timebranch"
                        edge_id_prefix = "is_in_timebranch"
                    else:
                        # Per altri tipi di gruppo non specificati
                        edge_id_prefix = "grouped_in"
                    
                    # Crea l'edge con gli UUID
                    edge_id = f"{subnode_uuid}_{edge_id_prefix}_{uuid_id}"
                    try:
                        self.graph.add_edge(
                            edge_id=edge_id,
                            edge_source=subnode_uuid,  # Usa UUID
                            edge_target=uuid_id,      # Usa UUID
                            edge_type=edge_type
                        )
                    except Exception as e:
                        print(f"Error creating edge from {subnode_uuid} to {uuid_id}: {e}")

    def extract_epochs(self, node_element, graph):
        """
        Estrae gli EpochNode dal nodo swimlane nel file GraphML.
        """
        # Mappa per tenere traccia delle righe per ID
        row_id_to_index = {}
        epoch_nodes = []
        
        geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
        y_start = float(geometry.attrib['y'])

        y_min = y_start
        y_max = y_start

        # Crea prima tutti i nodi epoca
        # print(f"Creazione nodi epoca iniziali...")
        rows = node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}Table/{http://www.yworks.com/xml/graphml}Rows/{http://www.yworks.com/xml/graphml}Row')
        for i, row in enumerate(rows):
            original_id = row.attrib['id']
            uuid_id = str(uuid.uuid4())
            self.id_mapping[original_id] = uuid_id
            row_id_to_index[original_id] = i
            
            h_row = float(row.attrib['height'])
            y_min = y_max
            y_max += h_row

            epoch_node = EpochNode(
                node_id=uuid_id,
                name=f"temp_{i}",  # Nome temporaneo con indice per debug
                start_time=-10000,
                end_time=10000
            )
        
            epoch_node.attributes['original_id'] = original_id
            epoch_node.min_y = y_min
            epoch_node.max_y = y_max
            self.graph.add_node(epoch_node)
            epoch_nodes.append(epoch_node)
            #print(f"Creato nodo epoca {i}: ID orig: {original_id}, UUID: {uuid_id}")

        # Aggiorna i nomi e i colori delle epoche
        # print(f"Aggiornamento nomi epoche...")
        for nodelabel in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
            try:
                row_param = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
                if row_param is not None:
                    label_text = nodelabel.text
                    original_id = str(row_param.attrib['id'])
                    
                    # Ottieni il colore se presente
                    e_color = nodelabel.attrib.get('backgroundColor', "#BCBCBC")
                    
                    #print(f"Processando etichetta con ID orig: {original_id}")
                    
                    # Cerca l'UUID corrispondente
                    uuid_id = self.id_mapping.get(original_id)
                    if not uuid_id:
                        print(f"WARNING: UUID non trovato per ID originale {original_id}")
                        continue
                    
                    # Cerca il nodo epoca usando l'UUID
                    epoch_node = self.graph.find_node_by_id(uuid_id)
                    if not epoch_node:
                        # Fallback: cerca usando l'indice se disponibile
                        row_index = row_id_to_index.get(original_id)
                        if row_index is not None and row_index < len(epoch_nodes):
                            epoch_node = epoch_nodes[row_index]
                            pass
                        else:
                            print(f"WARNING: Nodo epoca non trovato per UUID {uuid_id} o indice {row_index}")
                            continue
                    
                    # Aggiorna le proprietà del nodo epoca
                    try:
                        stringa_pulita, vocabolario = self.estrai_stringa_e_vocabolario(label_text)
                        epoch_node.set_name(stringa_pulita)
                        
                        # Gestisci i valori 'XX' per start_time
                        start_value = vocabolario.get('start', -10000)
                        if isinstance(start_value, str) and start_value.lower() in ['xx', 'x']:
                            start_value = 10000
                            pass
                        
                        # Gestisci i valori 'XX' per end_time
                        end_value = vocabolario.get('end', 10000)
                        if isinstance(end_value, str) and end_value.lower() in ['xx', 'x']:
                            end_value = 10000
                            pass
                        
                        epoch_node.set_start_time(start_value)
                        epoch_node.set_end_time(end_value)
                        #print(f"Aggiornato nodo epoca: '{stringa_pulita}' (start={start_value}, end={end_value})")
                    except Exception as e:
                        epoch_node.set_name(label_text)
                        # print(f"Fallback al nome completo: {label_text}: {str(e)}")                    
                    epoch_node.set_color(e_color)
                    #print(f"Impostato colore: {e_color}")
            except Exception as e:
                print(f"ERROR durante l'elaborazione dell'etichetta: {e}")

    def process_general_data(self, nodelabel, graph):
        """
        Processa i dati generali dal nodelabel e li aggiunge al grafo.
        """
        # print(f"\nProcessing general data from GraphML header:")
        # print(f"Raw nodelabel text: '{nodelabel.text}'")
        
        stringa_pulita, vocabolario = self.estrai_stringa_e_vocabolario(nodelabel.text)
        # print(f"Stringa pulita: '{stringa_pulita}'")
        # print(f"Vocabolario estratto: {vocabolario}")
        
        try:
            # Imposta il nome e l'ID del grafo
            if 'ID' in vocabolario:
                graph.graph_id = vocabolario['ID']
            else:
                # Fallback al nome del file
                import os
                graph.graph_id = os.path.splitext(os.path.basename(self.filepath))[0]

            graph.name = {'default': stringa_pulita}
                
            # Crea il nodo grafo stesso
            from ..nodes.base_node import Node
            graph_node = Node(
                node_id=graph.graph_id,
                name=stringa_pulita
            )
            graph.add_node(graph_node)
                
            # Crea e connetti il nodo autore se presente un ORCID
            if 'ORCID' in vocabolario:
                # print(f"Found ORCID: {vocabolario['ORCID']}")
                from ..nodes.author_node import AuthorNode
                
                # Componi il nome completo per il display
                author_name = vocabolario.get('author_name', '')
                author_surname = vocabolario.get('author_surname', '')
                display_name = f"{author_name} {author_surname}".strip()
                
                # Crea l'ID dell'autore
                author_id = f"author_{vocabolario['ORCID']}"
                
                # Crea il nodo autore usando solo i parametri accettati dal costruttore
                author_node = AuthorNode(
                    node_id=author_id,
                    orcid=vocabolario['ORCID'],
                    name=author_name,
                    surname=author_surname
                )
                
                # Aggiungi il nodo al grafo
                graph.add_node(author_node)
                
                # Aggiungi l'autore alla lista degli autori nei dati del grafo
                if 'authors' not in graph.data:
                    graph.data['authors'] = []
                if author_id not in graph.data['authors']:
                    graph.data['authors'].append(author_id)
                
                # Crea l'edge tra autore e grafo
                edge_id = f"authorship_{author_id}"
                graph.add_edge(
                    edge_id=edge_id,
                    edge_source=author_id,
                    edge_target=graph.graph_id,
                    edge_type="has_author"
                )
                    
            # Aggiorna la descrizione del grafo
            if 'description' in vocabolario:
                graph.description = {'default': vocabolario['description']}
                    
            # Gestisce la data di embargo se presente
            if 'embargo' in vocabolario:
                graph.data['embargo_until'] = vocabolario['embargo']
                    
            # Gestisce la licenza se presente
            if 'license' in vocabolario:
                graph.data['license'] = vocabolario['license']

            # print(f"\nGraph data after processing:")
            # print(f"ID: {graph.graph_id}")
            # print(f"Name: {graph.name}")
            # print(f"Description: {graph.description}")
            # print(f"Data: {graph.data}")
            # print(f"Authors: {graph.data.get('authors', [])}")
            
        except Exception as e:
            print(f"Error processing general data: {e}")
            import traceback
            traceback.print_exc()




    def connect_nodes_to_epochs(self):
        """
        Assegna le epoche ai nodi nel grafo in base alla posizione Y e gestisce i nodi continuity.
        """
        # print("\n=== Connecting nodes to epochs ===")
        
        # Verifica se ci sono nodi BR (continuity)
        br_nodes = [n for n in self.graph.nodes if hasattr(n, 'node_type') and n.node_type == "BR"]
        # print(f"Found {len(br_nodes)} BR (continuity) nodes for connection process")
        
        # Esegui una ricerca manuale nelle classi dei nodi per verificare che ContinuityNode esista e sia correttamente definito
        
        # print(f"ContinuityNode class node_type: {ContinuityNode.node_type}")

        # Definisce i tipi di nodi stratigrafici fisici che possono estendersi fino all'ultima epoca
        list_of_physical_stratigraphic_nodes = ["US", "serSU"]

        # Crea indici per accesso rapido
        epochs = [n for n in self.graph.nodes if hasattr(n, 'node_type') and n.node_type == "EpochNode"]

        # print(f"Numero totale di epoche trovate: {len(epochs)}")
        if len(epochs) == 0:
            print("AVVISO: Nessuna epoca trovata nel grafo")
            return

        # Crea un dizionario inverso per mappare UUID a ID originali
        reverse_mapping = {}
        for orig_id, uuid in self.id_mapping.items():
            reverse_mapping[uuid] = orig_id

        # print(f"Numero totale di epoche trovate: {len(epochs)}")
        if len(epochs) == 0:
            print("AVVISO: Nessuna epoca trovata nel grafo")
            return

        # Debug info
        # print(f"Connect nodes to epochs: {len(self.graph.nodes)} nodes, {len(epochs)} epochs")
        
        # Usa una mappatura diretta per trovare i nodi continuity collegati a nodi stratigrafici
        continuity_connections = {}  # node_id -> continuity_node

        # Prima identifica le connessioni continuity dagli archi
        for edge in self.graph.edges:
            # Usa direttamente source e target degli edge
            source_id = edge.edge_source
            target_id = edge.edge_target
            
            # Verifica se il source è un nodo continuity
            source_node = self.graph.find_node_by_id(source_id)
            if source_node and hasattr(source_node, 'node_type') and source_node.node_type == "BR":
                continuity_connections[target_id] = source_node
                # print(f"Found continuity connection: {source_node.node_id} -> {target_id}")
        
        # Per ogni nodo stratigrafico
        for node in self.graph.nodes:
            if not hasattr(node, 'attributes') or not 'y_pos' in node.attributes:
                continue
                
            connected_continuity_node = None

            # Cerca il nodo continuity collegato direttamente con l'UUID
            connected_continuity_node = continuity_connections.get(node.node_id)
            
            if connected_continuity_node:
                pass
            
            # Connetti alle epoche appropriate
            for epoch in epochs:
                if epoch.min_y < node.attributes['y_pos'] < epoch.max_y:
                    edge_id = f"{node.node_id}_{epoch.node_id}_first_epoch"
                    try:
                        self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "has_first_epoch")
                        #print(f"Connected node {node.name} to epoch {epoch.name} (first)")
                    except Exception as e:
                        print(f"Error connecting node {node.name} to epoch {epoch.name} (first): {e}")
                    
                elif connected_continuity_node and hasattr(connected_continuity_node, 'attributes') and 'y_pos' in connected_continuity_node.attributes:
                    y_pos = node.attributes['y_pos']
                    continuity_y_pos = connected_continuity_node.attributes['y_pos']
                    # print(f"Node {node.name} (y_pos: {y_pos}) connected to continuity node {connected_continuity_node.node_id} (y_pos: {continuity_y_pos})")

                    if epoch.max_y < y_pos and epoch.max_y > continuity_y_pos:
                        try:
                            edge_id = f"{node.node_id}_{epoch.node_id}_survive"
                            self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "survive_in_epoch")
                            #print(f"Connected node {node.name} to epoch {epoch.name} yeee (survive with continuity)")
                        except Exception as e:
                            print(f"Error connecting node {node.name} to epoch {epoch.name} (survive): {e}")
                    
                elif hasattr(node, 'node_type') and node.node_type in list_of_physical_stratigraphic_nodes:
                    # L'epoca è più recente del nodo (cioè il max_y dell'epoca è più basso del y_pos del nodo)
                    if epoch.max_y < node.attributes['y_pos']:
                        edge_id = f"{node.node_id}_{epoch.node_id}_survive"
                        try:
                            self.graph.add_edge(edge_id, node.node_id, epoch.node_id, "survive_in_epoch")
                            #print(f"Connected node {node.name} to epoch {epoch.name} (physical)")
                        except Exception as e:
                            print(f"Error connecting node {node.name} to epoch {epoch.name} (physical): {e}")

    # Funzioni di supporto per l'estrazione dei dati dai nodi

    def EM_extract_generic_node_name(self, node_element):
        node_name = ''
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            node_label = data_d6.find('.//{http://www.yworks.com/xml/graphml}NodeLabel')
            if node_label is not None:
                node_name = self._check_if_empty(node_label.text)
        return node_name

    def EM_extract_group_node_name(self, node_element):
        group_name = ''
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            node_label = data_d6.find('.//{http://www.yworks.com/xml/graphml}NodeLabel')
            if node_label is not None:
                group_name = self._check_if_empty(node_label.text)
        return group_name

    def EM_extract_group_node_description(self, node_element):
        group_description = ''
        description_key = self.key_map['node'].get('description')
        ns = 'http://graphml.graphdrawing.org/xmlns'
        if description_key:
            data_desc = node_element.find(f'./{{{ns}}}data[@key="{description_key}"]')
            if data_desc is not None and data_desc.text is not None:
                group_description = self.clean_comments(data_desc.text)
        return group_description

    def EM_extract_group_node_background_color(self, node_element):
        background_color = None
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            node_label = data_d6.find('.//{http://www.yworks.com/xml/graphml}NodeLabel')
            if node_label is not None:
                background_color = node_label.attrib.get('backgroundColor')
        return background_color

    def EM_extract_group_node_y_pos(self, node_element):
        y_pos = 0.0
        data_d6 = node_element.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d6"]')
        if data_d6 is not None:
            geometry = data_d6.find('.//{http://www.yworks.com/xml/graphml}Geometry')
            if geometry is not None:
                y_pos = float(geometry.attrib.get('y', 0.0))
        return y_pos

    def determine_group_node_type_by_color(self, background_color):
        if background_color == '#CCFFFF':
            return 'ActivityNodeGroup'
        elif background_color == '#FFCC99':
            return 'ParadataNodeGroup'
        elif background_color == '#99CC00':
            return 'TimeBranchNodeGroup'
        else:
            return 'GroupNode'

    # Funzioni per estrarre e verificare i vari tipi di nodi

    def EM_check_node_us(self, node_element):
        US_nodes_list = ['rectangle', 'parallelogram', 'ellipse', 'hexagon', 'octagon', 'roundrectangle']
        nodename, _, _, nodeshape, _, _, _ = self.EM_extract_node_name(node_element)
        return nodeshape in US_nodes_list

    def EM_extract_node_name(self, node_element):
        node_y_pos = None
        nodeshape = None
        nodeurl = ''
        nodedescription = ''
        nodename = None
        fillcolor = None
        borderstyle = None

        # Usa key_map dinamico per trovare le chiavi corrette
        url_key = self.key_map['node'].get('url')
        description_key = self.key_map['node'].get('description')

        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib = subnode.attrib
            key = attrib.get('key')

            # Estrai URL usando la chiave dinamica
            if url_key and key == url_key:
                nodeurl = subnode.text if subnode.text else ''

            # Estrai description usando la chiave dinamica
            if description_key and key == description_key:
                if not subnode.text:
                    nodedescription = ''
                else:
                    nodedescription = self.clean_comments(subnode.text)

            # yfiles.type="nodegraphics" non ha attr.name, quindi cerchiamo per yfiles.type
            # Cerca tra tutte le chiavi yfiles per nodegraphics
            if 'yfiles.type' in ' '.join(str(v) for v in attrib.values()) or 'nodegraphics' in str(key):
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = self._check_if_empty(USname.text)
                for fill_color in subnode.findall('.//{http://www.yworks.com/xml/graphml}Fill'):
                    fillcolor = fill_color.attrib['color']
                for border_style in subnode.findall('.//{http://www.yworks.com/xml/graphml}BorderStyle'):
                    borderstyle = border_style.attrib['color']
                for USshape in subnode.findall('.//{http://www.yworks.com/xml/graphml}Shape'):
                    nodeshape = USshape.attrib['type']
                for geometry in subnode.findall('.//{http://www.yworks.com/xml/graphml}Geometry'):
                    node_y_pos = geometry.attrib['y']

        return nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor, borderstyle

    def EM_check_node_document(self, node_element):
        try:
            _, _, _, _, subnode_is_document = self.EM_extract_document_node(node_element)
        except TypeError:
            subnode_is_document = False
        return subnode_is_document

    def EM_extract_document_node(self, node_element):
        node_id = node_element.attrib['id']
        nodename = ""
        node_description = ""
        nodeurl = ""
        subnode_is_document = False

        # Usa key_map dinamico
        url_key = self.key_map['node'].get('url')
        description_key = self.key_map['node'].get('description')

        # Prima verifica se è un document node cercando le proprietà yfiles
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            # Cerca nodegraphics (la chiave varia, usiamo yfiles.type)
            if 'yfiles.type' in ' '.join(str(v) for v in subnode.attrib.values()) or 'nodegraphics' in str(subnode.attrib.get('key', '')):
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = USname.text
                for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}Property'):
                    if nodetype.attrib.get('name') == 'com.yworks.bpmn.dataObjectType' and nodetype.attrib.get('value') == 'DATA_OBJECT_TYPE_PLAIN':
                        subnode_is_document = True

        if subnode_is_document:
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                key = subnode.attrib.get('key')
                if url_key and key == url_key:
                    if subnode.text is not None:
                        nodeurl = subnode.text
                if description_key and key == description_key:
                    node_description = self.clean_comments(subnode.text) if subnode.text else ''

        return nodename, node_id, node_description, nodeurl, subnode_is_document

    def EM_check_node_property(self, node_element):
        try:
            _, _, _, _, subnode_is_property = self.EM_extract_property_node(node_element)
        except UnboundLocalError:
            subnode_is_property = False
        return subnode_is_property

    def EM_extract_property_node(self, node_element):
        node_id = node_element.attrib['id']
        subnode_is_property = False
        nodeurl = ""
        nodename = ""
        node_description = ""

        # Usa key_map dinamico
        url_key = self.key_map['node'].get('url')
        description_key = self.key_map['node'].get('description')

        # Prima verifica se è un property node
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if 'yfiles.type' in ' '.join(str(v) for v in subnode.attrib.values()) or 'nodegraphics' in str(subnode.attrib.get('key', '')):
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = self._check_if_empty(USname.text)
                for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}Property'):
                    if nodetype.attrib.get('name') == 'com.yworks.bpmn.type' and nodetype.attrib.get('value') == 'ARTIFACT_TYPE_ANNOTATION':
                        subnode_is_property = True

        if subnode_is_property:
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                key = subnode.attrib.get('key')
                if url_key and key == url_key:
                    if subnode.text is not None:
                        nodeurl = subnode.text
                if description_key and key == description_key:
                    node_description = self.clean_comments(subnode.text) if subnode.text else ''

        return nodename, node_id, node_description, nodeurl, subnode_is_property

    def EM_check_node_extractor(self, node_element):
        try:
            _, _, _, _, subnode_is_extractor = self.EM_extract_extractor_node(node_element)
        except TypeError:
            subnode_is_extractor = False
        return subnode_is_extractor

    def EM_extract_extractor_node(self, node_element):
        node_id = node_element.attrib['id']
        subnode_is_extractor = False
        nodeurl = ""
        nodename = ""
        node_description = ""

        # Usa key_map dinamico
        url_key = self.key_map['node'].get('url')
        description_key = self.key_map['node'].get('description')

        # Prima verifica se è un extractor node (nome inizia con "D.")
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if 'yfiles.type' in ' '.join(str(v) for v in subnode.attrib.values()) or 'nodegraphics' in str(subnode.attrib.get('key', '')):
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = self._check_if_empty(USname.text)
                if nodename.startswith("D.") and not self.graph.find_node_by_name(nodename):
                    subnode_is_extractor = True

        if subnode_is_extractor:
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                key = subnode.attrib.get('key')
                if url_key and key == url_key:
                    if subnode.text is not None:
                        nodeurl = self._check_if_empty(subnode.text)
                if description_key and key == description_key:
                    node_description = self.clean_comments(self._check_if_empty(subnode.text)) if subnode.text else ''

        return nodename, node_id, node_description, nodeurl, subnode_is_extractor

    def EM_check_node_combiner(self, node_element):
        try:
            _, _, _, _, subnode_is_combiner = self.EM_extract_combiner_node(node_element)
        except TypeError:
            subnode_is_combiner = False
        return subnode_is_combiner

    def EM_extract_combiner_node(self, node_element):
        node_id = node_element.attrib['id']
        subnode_is_combiner = False
        nodeurl = ""
        nodename = ""
        node_description = ""

        # Usa key_map dinamico
        url_key = self.key_map['node'].get('url')
        description_key = self.key_map['node'].get('description')

        # Prima verifica se è un combiner node (nome inizia con "C.")
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if 'yfiles.type' in ' '.join(str(v) for v in subnode.attrib.values()) or 'nodegraphics' in str(subnode.attrib.get('key', '')):
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = self._check_if_empty(USname.text)
                if nodename.startswith("C."):
                    subnode_is_combiner = True

        if subnode_is_combiner:
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                key = subnode.attrib.get('key')
                if url_key and key == url_key:
                    if subnode.text is not None:
                        nodeurl = self._check_if_empty(subnode.text)
                if description_key and key == description_key:
                    node_description = self.clean_comments(self._check_if_empty(subnode.text)) if subnode.text else ''

        return nodename, node_id, node_description, nodeurl, subnode_is_combiner

    def EM_check_node_continuity(self, node_element):
        """
        Verifica se un nodo è un nodo di continuità (BR).
        
        Args:
            node_element: Elemento XML del nodo
            
        Returns:
            bool: True se il nodo è di tipo continuity
        """
        # Cerca nei dati del nodo
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if subnode.attrib.get('key') == 'd5':
                # Verifica se il testo è "_continuity"
                if subnode.text and "_continuity" in subnode.text:
                    # print(f"Found continuity node: {node_element.attrib['id']}")
                    return True
                    
        # Verifica se è un SVGNode (alternativa)
        svg_node = node_element.find('.//{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}SVGNode')
        if svg_node is not None:
            # Cerca di nuovo nei dati per confermare se è un nodo continuity
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                if subnode.attrib.get('key') == 'd5' and subnode.text:
                    if "_continuity" in subnode.text:
                        # print(f"Found SVG continuity node: {node_element.attrib['id']}")
                        return True
                        
        return False

    def EM_extract_continuity(self, node_element):
        """
        Estrae informazioni da un nodo continuity.
        
        Args:
            node_element: Elemento XML del nodo
            
        Returns:
            tuple: (descrizione, posizione y, id)
        """
        is_d5 = False
        node_y_pos = 0.0
        nodedescription = None
        node_id = node_element.attrib['id']

        # Estrai descrizione dal campo d5
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            if subnode.attrib.get('key') == 'd5':
                is_d5 = True
                nodedescription = subnode.text
            
            # Per SVGNode, estrai la posizione y
                geometry = subnode.find('.//{http://www.yworks.com/xml/graphml}SVGNode/{http://www.yworks.com/xml/graphml}Geometry')
                if geometry is not None:
                    y_str = geometry.attrib.get('y', '0.0')
                    try:
                        node_y_pos = float(y_str)
                        # print(f"Extracted y position from SVGNode: {node_y_pos}")
                    except (ValueError, TypeError):
                        print(f"Error converting y position to float: {y_str}")
                        node_y_pos = 0.0
            
            # Fallback per i nodi non SVG
            if subnode.attrib.get('key') == 'd6':
                geometry = subnode.find('.//{http://www.yworks.com/xml/graphml}Geometry')
                if geometry is not None:
                    y_str = geometry.attrib.get('y', '0.0')
                    try:
                        node_y_pos = float(y_str)
                    except (ValueError, TypeError):
                        node_y_pos = 0.0
        
        if not is_d5:
            nodedescription = ''
            
        if nodedescription == "_continuity":
            #print(f"Extracting continuity node: ID={node_id}, y_pos={node_y_pos}")
            pass
            
        return nodedescription, node_y_pos, node_id

    def enhance_edge_type(self, edge_type, source_node, target_node):
        """
        Enhances the edge type based on the types of the connected nodes.
        
        Args:
            edge_type (str): The basic edge type from GraphML style.
            source_node (Node): The source node.
            target_node (Node): The target node.
            
        Returns:
            str: The enhanced edge type.
        """
        if not source_node or not target_node:
            return edge_type
            
        # Definizione dei tipi stratigrafici
        stratigraphic_types = ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 
                            'serUSVn', 'serUSVs', 'TSU', 'SE', 'BR', 'unknown']

        source_type = source_node.node_type if hasattr(source_node, 'node_type') else ""
        target_type = target_node.node_type if hasattr(target_node, 'node_type') else ""
        
        # print(f"Enhancing edge type {edge_type}: {source_type} -> {target_type}")

        # Logica per has_data_provenance
        if edge_type == "has_data_provenance":
            # Se il source è un nodo stratigrafico e il target è una property
            if source_type in stratigraphic_types and target_type == "property":
                edge_type = "has_property"
                # print(f"Enhanced to has_property: {source_type} -> PropertyNode")

            # Unità stratigrafica collegata a ParadataNodeGroup
            elif source_type in stratigraphic_types and target_type == "ParadataNodeGroup":
                edge_type = "has_paradata_nodegroup"
                # print(f"Enhanced to has_paradata_nodegroup: {source_type} -> ParadataNodeGroup")
            
            # ParadataNodeGroup collegato a unità stratigrafica (direzione invertita)
            elif source_type == "ParadataNodeGroup" and target_type in stratigraphic_types:
                edge_type = "has_paradata_nodegroup"
                # print(f"Enhanced to has_paradata_nodegroup (direzione invertita): ParadataNodeGroup -> {target_type}")

            # ExtractorNode -> DocumentNode
            elif (isinstance(source_node, ExtractorNode) and 
                isinstance(target_node, DocumentNode)):
                edge_type = "extracted_from"
                # print(f"Enhanced to extracted_from: ExtractorNode -> DocumentNode")
                
            # CombinerNode -> ExtractorNode
            elif (isinstance(source_node, CombinerNode) and
                isinstance(target_node, ExtractorNode)):
                edge_type = "combines"
                # print(f"Enhanced to combines: CombinerNode -> ExtractorNode")

            # ✅ v1.5.3: StratigraphicNode -> DocumentNode = has_documentation
            elif (source_type in stratigraphic_types and
                isinstance(target_node, DocumentNode)):
                edge_type = "has_documentation"
                # print(f"Enhanced to has_documentation: {source_type} -> DocumentNode")

            # ✅ v1.5.3: DocumentNode -> StratigraphicNode = is_documentation_of (reverse)
            elif (isinstance(source_node, DocumentNode) and
                  target_type in stratigraphic_types):
                edge_type = "is_documentation_of"
                # print(f"Enhanced to is_documentation_of: DocumentNode -> {target_type}")

        # Post-processing per generic_connection
        elif edge_type == "generic_connection":
            # ✅ v1.5.3: StratigraphicNode -> DocumentNode = has_documentation
            if (source_type in stratigraphic_types and
                isinstance(target_node, DocumentNode)):
                edge_type = "has_documentation"
                # print(f"Enhanced to has_documentation: {source_type} -> DocumentNode")

            # ✅ v1.5.3: DocumentNode -> StratigraphicNode = is_documentation_of (reverse)
            elif (isinstance(source_node, DocumentNode) and
                  target_type in stratigraphic_types):
                edge_type = "is_documentation_of"
                # print(f"Enhanced to is_documentation_of: DocumentNode -> {target_type}")

            # Nodi ParadataNode (e sottoclassi) collegati a ParadataNodeGroup
            elif (isinstance(source_node, (DocumentNode, ExtractorNode, CombinerNode, ParadataNode)) and
                target_type == "ParadataNodeGroup"):
                edge_type = "is_in_paradata_nodegroup"
                # print(f"Enhanced to is_in_paradata_nodegroup: {source_type} -> ParadataNodeGroup")

            # ParadataNodeGroup collegato a ActivityNodeGroup
            elif source_type == "ParadataNodeGroup" and target_type == "ActivityNodeGroup":
                edge_type = "has_paradata_nodegroup"
                # print(f"Enhanced to has_paradata_nodegroup: ParadataNodeGroup -> ActivityNodeGroup")

            # Puoi aggiungere altre regole specifiche qui

        return edge_type

    def EM_extract_edge_type(self, edge):
        """
        Extracts the basic semantic type of the edge from the GraphML line style.

        Note: For stratigraphic relations, "is_after" is now used as the canonical direction.
        In v1.5.3+, "is_after" (source more recent than target) is canonical,
        while "is_before" (source older than target) is the reverse direction.

        GraphML convention in Extended Matrix has arrows pointing from recent to ancient:
        - Source node = more recent unit (positioned higher in the matrix)
        - Target node = more ancient unit (positioned lower in the matrix)
        - Visual arrow = points downward (from recent to ancient)

        This matches perfectly with "is_after" canonical direction, so no reversal is needed.

        Args:
            edge_element (Element): XML element for the edge.

        Returns:
            str: The edge type representing the semantic relationship.
        """
        edge_type = "generic_connection"  # Default edge type

        data_element = edge.find('./{http://graphml.graphdrawing.org/xmlns}data[@key="d10"]')

        if data_element is not None:
            # Extract graphical line style and map it to a semantic relationship
            line_style = data_element.find('.//{http://www.yworks.com/xml/graphml}LineStyle')
            if line_style is not None:
                style_type = line_style.attrib.get("type")
                # Map each graphical style to its semantic meaning
                if style_type == "line":
                    # v1.5.3: Use canonical "is_after" direction (recent → ancient)
                    # GraphML already has source=recent, target=ancient (arrow points down)
                    # This matches the canonical direction perfectly, no reversal needed
                    edge_type = "is_after"
                elif style_type == "double_line":
                    edge_type = "has_same_time"
                elif style_type == "dotted":
                    edge_type = "changed_from"
                elif style_type == "dashed":
                    edge_type = "has_data_provenance"
                elif style_type == "dashed_dotted":
                    edge_type = "contrasts_with"
                else:
                    edge_type = "generic_connection"

        return edge_type


    # Funzioni di utilità

    def _check_node_type(self, node_element):
        id_node = str(node_element.attrib)
        if "yfiles.foldertype" in id_node:
            tablenode = node_element.find('.//{http://www.yworks.com/xml/graphml}TableNode')
            if tablenode is not None:
                return 'node_swimlane'
            else:
                return 'node_group'
        else:
            return 'node_simple'

    def estrai_stringa_e_vocabolario(self, s):
        match = re.search(r'\[(.*?)\]', s)
        vocabolario = {}
        if match:
            contenuto = match.group(1)
            coppie = contenuto.split(';')
            for coppia in coppie:
                coppia = coppia.strip()
                if not coppia:
                    continue
                if ':' in coppia:
                    parti = coppia.split(':', 1)
                    if len(parti) != 2 or not parti[0] or not parti[1]:
                        raise ValueError(f"Coppia chiave:valore malformata: '{coppia}'")
                    chiave, valore = parti
                    chiave = chiave.strip()
                    valore = valore.strip()
                    try:
                        valore = int(valore)
                    except ValueError:
                        pass
                    vocabolario[chiave] = valore
                else:
                    raise ValueError(f"Coppia senza separatore ':': '{coppia}'")
            stringa_pulita = re.sub(r'\[.*?\]', '', s).strip()
        else:
            stringa_pulita = s.strip()
        return stringa_pulita, vocabolario

    def clean_comments(self, multiline_str):
        newstring = ""
        for line in multiline_str.splitlines():
            if line.startswith("«") or line.startswith("#"):
                pass
            else:
                newstring += line + " "
        return newstring.strip()

    def getnode_id(self, node_element):
        return str(node_element.attrib['id'])

    def _check_if_empty(self, name):
        return name if name is not None else ""

    # Aggiungi ulteriori metodi di supporto se necessario
