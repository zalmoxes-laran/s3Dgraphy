# s3Dgraphy/utils/utils.py
import os
import json

"""
Utilities for the s3Dgraphy library.

This module includes helper functions for node type conversion based on YED node shapes and border styles.
"""

from ..nodes.stratigraphic_node import (
    StratigraphicNode,
    StratigraphicUnit,
    SeriesOfStratigraphicUnit,
    SeriesOfNonStructuralVirtualStratigraphicUnit,
    SeriesOfStructuralVirtualStratigraphicUnit,
    SeriesOfDocumentaryStratigraphicUnit,
    NonStructuralVirtualStratigraphicUnit,
    StructuralVirtualStratigraphicUnit,
    SpecialFindUnit,
    VirtualSpecialFindUnit,
    DocumentaryStratigraphicUnit,
    TransformationStratigraphicUnit,
    StratigraphicEventNode,
    ContinuityNode
)


def debug_graph_structure(graph, node_id=None, max_depth=5, current_depth=0):
    """
    Stampa informazioni dettagliate sulla struttura del grafo.
    Se node_id è specificato, si concentra sulle relazioni di quel nodo.
    
    Args:
        graph: Il grafo da analizzare
        node_id: ID del nodo su cui concentrarsi (opzionale)
        max_depth: Profondità massima di ricorsione
        current_depth: Profondità corrente di ricorsione
    """
    # Prevent infinite recursion
    if current_depth >= max_depth:
        # print(f"Limite di profondità ricorsiva ({max_depth}) raggiunto.")
        return
        
    
    
    if node_id:
        node = graph.find_node_by_id(node_id)
        if node:
            
            out_edges = [e for e in graph.edges if e.edge_source == node_id]
            in_edges = [e for e in graph.edges if e.edge_target == node_id]
            
            for e in out_edges:
                target = graph.find_node_by_id(e.edge_target)
                target_type = target.node_type if target else "Unknown"
            
            for e in in_edges:
                source = graph.find_node_by_id(e.edge_source)
                source_type = source.node_type if source else "Unknown"
            
    else:
        node_types = {}
        for node in graph.nodes:
            if node.node_type not in node_types:
                node_types[node.node_type] = []
            node_types[node.node_type].append(node)
        
        for ntype, nodes in node_types.items():
            pass
        
        edge_types = {}
        for edge in graph.edges:
            if edge.edge_type not in edge_types:
                edge_types[edge.edge_type] = 0
            edge_types[edge.edge_type] += 1
        
        for etype, count in edge_types.items():
            pass

def convert_shape2type(yedtype, border_style):
    """
    Converts YED node shape and border style to a specific stratigraphic node type.

    Args:
        yedtype (str): The shape type of the node in YED.
        border_style (str): The border color of the node.

    Returns:
        tuple: A tuple with a short code for the node type and an extended description.
    """
    if yedtype == "rectangle":
        nodetype = ("US", "Stratigraphic Unit")
    elif yedtype == "parallelogram":
        nodetype = ("USVs", "Structural Virtual Stratigraphic Units")
    elif yedtype == "ellipse" and border_style == "#D86400":
        nodetype = ("serUSD", "Series of USD")
    elif yedtype == "ellipse" and border_style == "#31792D":
        nodetype = ("serUSVn", "Series of USVn")
    elif yedtype == "ellipse" and border_style == "#248FE7":
        nodetype = ("serUSVs", "Series of USVs")
    elif yedtype == "ellipse" and border_style == "#9B3333":
        nodetype = ("serSU", "Series of SU")
    elif yedtype == "hexagon":
        nodetype = ("USVn", "Non-Structural Virtual Stratigraphic Units")
    elif yedtype == "octagon" and border_style == "#D8BD30":
        nodetype = ("SF", "Special Find")
    elif yedtype == "octagon" and border_style == "#B19F61":
        nodetype = ("VSF", "Virtual Special Find")
    elif yedtype == "roundrectangle":
        nodetype = ("USD", "Documentary Stratigraphic Unit")
    else:
        print(f"Unrecognized node type and style: yedtype='{yedtype}', border_style='{border_style}'")
        nodetype = ("unknown", "Unrecognized node")
        
    return nodetype


# Mappa dei tipi stratigrafici alle rispettive classi
STRATIGRAPHIC_CLASS_MAP = {
    "US": StratigraphicUnit,
    "USVs": StructuralVirtualStratigraphicUnit,
    "serSU": SeriesOfStratigraphicUnit,
    "serUSVn": SeriesOfNonStructuralVirtualStratigraphicUnit,
    "serUSVs": SeriesOfStructuralVirtualStratigraphicUnit,
    "serUSD": SeriesOfDocumentaryStratigraphicUnit,
    "USVn": NonStructuralVirtualStratigraphicUnit,
    "SF": SpecialFindUnit,
    "VSF": VirtualSpecialFindUnit,
    "USD": DocumentaryStratigraphicUnit,
    "TSU": TransformationStratigraphicUnit,
    "SE": StratigraphicEventNode,
    "BR": ContinuityNode,
    # Aggiungi ulteriori tipi e classi se necessario
}

def get_stratigraphic_node_class(stratigraphic_type):
    """
    Returns the stratigraphic node class corresponding to the specified type.

    Args:
        stratigraphic_type (str): The type of stratigraphic unit.

    Returns:
        class: The corresponding stratigraphic node class.
    """
    # Usa StratigraphicUnit come fallback se il tipo non è nella mappa
    return STRATIGRAPHIC_CLASS_MAP.get(stratigraphic_type, StratigraphicNode)

def get_material_color(matname, rules_path=None):
    """
    Ottiene i valori RGB per un dato tipo di materiale dal file di configurazione.
    
    Args:
        matname (str): Nome del materiale/tipo di unità stratigrafica
        rules_path (str, optional): Percorso al file JSON delle regole. Se None,
            usa il path di default.
            
    Returns:
        tuple: (R, G, B, A) con valori tra 0 e 1 o None se il nodo non prevede
        un materiale
    """
    if rules_path is None:
        rules_path = os.path.join(os.path.dirname(__file__), 
                                "../JSON_config/em_visual_rules.json")
    
    try:
        with open(rules_path, 'r') as f:
            rules = json.load(f)
            node_style = rules["node_styles"].get(matname, {})
            style = node_style.get("style", {})
            
            # Se non c'è la sezione material, restituisce None
            if "material" not in style:
                return None
                
            color = style["material"]["color"]
            return (color["r"], color["g"], color["b"], color.get("a", 1.0))
            
    except (KeyError, FileNotFoundError, json.JSONDecodeError):
        # Fallback solo per i nodi che dovrebbero avere un materiale
        if matname in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD']:
            return (0.5, 0.5, 0.5, 1.0)
        return None
    
def get_original_node_id(node):
    """
    Recupera l'ID originale di un nodo.
    
    Args:
        node: Il nodo da cui estrarre l'ID originale
        
    Returns:
        str: L'ID originale o l'ID corrente se non disponibile
    """
    return node.attributes.get('original_id', node.node_id)

def get_original_node_name(node):
    """
    Recupera il nome originale di un nodo (senza prefisso del grafo).
    
    Args:
        node: Il nodo da cui estrarre il nome originale
        
    Returns:
        str: Il nome originale o il nome corrente se non disponibile
    """
    return node.attributes.get('original_name', node.name)

def get_graph_code_from_node(node):
    """
    Estrae il codice del grafo da un nodo.
    
    Args:
        node: Il nodo da cui estrarre il codice
        
    Returns:
        str: Il codice del grafo o None se non disponibile
    """
    # Se il nome è prefissato (contiene _)
    if '_' in node.name:
        return node.name.split('_', 1)[0]
    
    # Altrimenti, cerca negli attributi
    return node.attributes.get('graph_code')

def manage_id_prefix(name: str, graph_code: str = None, action: str = 'add', separator: str = '.') -> str:
    """
    Add or remove graph code prefix from element names.
    
    This utility is useful for managing unique names when working with multiple graphs,
    especially when mapping to external systems with unique name constraints
    (e.g., 3D object names in Blender, database primary keys, file systems).
    
    The function handles edge cases gracefully:
    - Adding a prefix when one already exists (replaces old prefix)
    - Removing prefix when none exists (returns name unchanged)
    - Handling empty or None values
    
    Args:
        name (str): The name to modify
        graph_code (str, optional): The graph code to use as prefix. 
                                   If None and action='remove', removes any existing prefix.
                                   Defaults to None.
        action (str): Operation to perform: 'add' or 'remove'. Defaults to 'add'.
        separator (str): Character(s) between prefix and name. Defaults to '.'.
    
    Returns:
        str: The modified name
        
    Raises:
        ValueError: If action is not 'add' or 'remove'
        
    Examples:
        >>> manage_id_prefix('US001', 'VDL16', 'add')
        'VDL16.US001'
        
        >>> manage_id_prefix('VDL16.US001', 'VDL16', 'remove')
        'US001'
        
        >>> manage_id_prefix('GT15.US001', None, 'remove')
        'US001'
        
        >>> manage_id_prefix('GT15.US001', 'VDL16', 'add')
        'VDL16.US001'
        
        >>> manage_id_prefix('US001', None, 'add')
        'US001'
        
        >>> manage_id_prefix('', 'VDL16', 'add')
        ''
    """
    # Validate action parameter
    if action not in ['add', 'remove']:
        raise ValueError(f"Invalid action '{action}'. Must be 'add' or 'remove'.")
    
    # Handle empty or None names
    if not name or name.strip() == '':
        return name
    
    # Remove action
    if action == 'remove':
        # If the name contains the separator, split and return the part after first separator
        if separator in name:
            parts = name.split(separator, 1)  # Split only on first occurrence
            return parts[1] if len(parts) > 1 else name
        # No separator found, return name as-is
        return name
    
    # Add action
    if action == 'add':
        # If no graph_code provided, return name unchanged
        if not graph_code or graph_code.strip() == '':
            return name
        
        # Check if name already has a prefix
        if separator in name:
            # Remove existing prefix first
            base_name = manage_id_prefix(name, None, 'remove', separator)
            # Add new prefix
            return f"{graph_code}{separator}{base_name}"
        else:
            # No existing prefix, just add it
            return f"{graph_code}{separator}{name}"
    
    # Should never reach here due to validation above
    return name


def get_base_name(name: str, separator: str = '.') -> str:
    """
    Convenience function to extract base name without prefix.
    
    This is a wrapper around manage_id_prefix with action='remove'.
    
    Args:
        name (str): The name potentially containing a prefix
        separator (str): Character(s) between prefix and name. Defaults to '.'.
    
    Returns:
        str: The base name without prefix
        
    Examples:
        >>> get_base_name('VDL16.US001')
        'US001'
        
        >>> get_base_name('US001')
        'US001'
    """
    return manage_id_prefix(name, None, 'remove', separator)


def add_graph_prefix(name: str, graph_code: str, separator: str = '.') -> str:
    """
    Convenience function to add graph code prefix to a name.
    
    This is a wrapper around manage_id_prefix with action='add'.
    
    Args:
        name (str): The name to add prefix to
        graph_code (str): The graph code to use as prefix
        separator (str): Character(s) between prefix and name. Defaults to '.'.
    
    Returns:
        str: The name with prefix added
        
    Examples:
        >>> add_graph_prefix('US001', 'VDL16')
        'VDL16.US001'
    """
    return manage_id_prefix(name, graph_code, 'add', separator)


def get_ai_prompt(language: str = None) -> str:
    """
    Build and return the AI extraction prompt for stratigraphic data.

    Reads the AI_EXTRACTION_PROMPT.md bundled inside the s3dgraphy package,
    extracts Part A (stratigraphy) and Part B (paradata), and prepends a
    language instruction.

    Args:
        language: Target language for AI-generated descriptions.
            If None, empty, or equal to "the same as the original document",
            the prompt instructs the AI to use the source document's language.
            Otherwise, the specified language is used (e.g., "Italian", "English").

    Returns:
        str: The composed prompt text ready to paste into an AI assistant.

    Raises:
        FileNotFoundError: If the bundled prompt file cannot be located.
        ValueError: If the prompt file cannot be parsed (fewer than 2 code blocks).

    Example:
        >>> prompt = get_ai_prompt("Italian")
        >>> print(prompt[:60])
        IMPORTANT: Write all descriptions and properties in Italian.
    """
    # Locate the bundled prompt file inside the package
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    prompt_path = os.path.join(data_dir, 'AI_EXTRACTION_PROMPT.md')

    if not os.path.exists(prompt_path):
        raise FileNotFoundError(
            f"AI extraction prompt not found at: {prompt_path}. "
            "Ensure s3dgraphy is installed correctly."
        )

    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract code blocks (text between ``` delimiters)
    blocks = []
    current_block = []
    in_block = False
    for line in content.splitlines():
        if line.strip() == '```':
            if in_block:
                blocks.append('\n'.join(current_block))
                current_block = []
            in_block = not in_block
        elif in_block:
            current_block.append(line)

    if len(blocks) < 2:
        raise ValueError(
            "Could not parse prompt blocks from AI_EXTRACTION_PROMPT.md. "
            f"Expected at least 2 code blocks, found {len(blocks)}."
        )

    part_a = blocks[0]
    part_b = blocks[1]

    # Build language instruction
    default_lang = "the same as the original document"
    if not language or language.strip().lower() == default_lang.lower():
        lang_instruction = (
            "IMPORTANT: Write all descriptions and properties in the same "
            "language as the original document."
        )
    else:
        lang_instruction = (
            f"IMPORTANT: Write all descriptions and properties in {language.strip()}."
        )

    # Compose final prompt
    full_prompt = (
        f"{lang_instruction}\n\n"
        f"--- PART A: STRATIGRAPHY EXTRACTION ---\n\n"
        f"{part_a}\n\n"
        f"--- PART B: PARADATA EXTRACTION ---\n\n"
        f"{part_b}"
    )

    return full_prompt
