# s3Dgraphy/importer/base_importer.py

from abc import ABC, abstractmethod
import json
import os
import logging
from typing import Dict, Any, Optional
from ..graph import Graph
from ..nodes.base_node import Node
from ..nodes.property_node import PropertyNode
from ..edges import Edge
from ..utils.utils import get_stratigraphic_node_class

# Configurazione logging opzionale per debug
logger = logging.getLogger(__name__)

class BaseImporter(ABC):
    """
    Abstract base class for all importers.
    Supports both mapped and automatic property creation modes.
    """
    def __init__(self, filepath: str, mapping_name: str = None, id_column: str = None, 
                 overwrite: bool = False, mode: str = "EM_ADVANCED"):
        """
        Initialize the importer.
        
        Args:
            filepath: Path to the file to import
            mapping_name: Name of the mapping configuration to use
            id_column: Name of the ID column when not using mapping
            overwrite: If True, overwrites existing property values
            mode: Either "3DGIS" or "EM_ADVANCED"
        """
        if mapping_name is None and id_column is None:
            raise ValueError("Either mapping_name or id_column must be provided")
        
        # ✅ FIX: Converti percorso relativo in assoluto
        import os
        try:
            # Se siamo in Blender, usa bpy.path.abspath
            import bpy
            self.filepath = bpy.path.abspath(filepath)
            logger.debug(f"Converted filepath using bpy.path.abspath: {filepath} -> {self.filepath}")
        except ImportError:
            # Se non siamo in Blender, usa os.path.abspath standard
            self.filepath = os.path.abspath(filepath)
            logger.debug(f"Converted filepath using os.path.abspath: {filepath} -> {self.filepath}")
        
        # Verifica che il file esista
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"File not found: {self.filepath} (original path: {filepath})")
            
        self.id_column = id_column
        self.mapping = self._load_mapping(mapping_name) if mapping_name else None
        self.overwrite = overwrite
        self.mode = mode

        # ✅ AGGIUNTA: Cache l'ID column una sola volta
        self._cached_id_column = None
        
        # Il grafo verrà inizializzato dalla classe figlia
        #self.graph = None
        self.warnings = []

    def _load_mapping(self, mapping_name: str) -> Dict[str, Any]:
        """Load the JSON mapping file using the mapping registry."""
        if mapping_name is None:
            return None
            
        logger.debug(f"Loading mapping: {mapping_name}")
        
        # Import registry
        from ..mappings import mapping_registry
        
        # Try different mapping types in order
        mapping_types = ['pyarchinit', 'emdb', 'generic']
        
        for mapping_type in mapping_types:
            logger.debug(f"Trying mapping type: {mapping_type}")
            mapping = mapping_registry.load_mapping(mapping_name, mapping_type)
            if mapping:
                logger.debug(f"Mapping loaded successfully from {mapping_type}")
                logger.debug(f"Keys in mapping: {list(mapping.keys())}")
                logger.debug(f"Column mappings: {list(mapping.get('column_mappings', {}).keys())}")
                return mapping
        
        raise FileNotFoundError(f"Mapping file {mapping_name} not found in any registered directories")

    @abstractmethod
    def parse(self) -> Graph:
        """Parse the input file and create nodes/edges in the graph."""
        pass

    def _get_id_column(self):
        """Get ID column from mapping or use provided id_column."""
        
        # ✅ AGGIUNTA: Usa cache per evitare ripetizioni
        if self._cached_id_column is not None:
            return self._cached_id_column
            
        logger.debug("Getting ID column")
        logger.debug(f"Mapping present: {self.mapping is not None}")
        
        if self.mapping:
            # 🔄 Nuovo formato: cerca in column_mappings per is_id: true
            for col_name, col_config in self.mapping.get('column_mappings', {}).items():
                if col_config.get('is_id', False):
                    logger.debug(f"Found ID column: {col_name}")
                    self._cached_id_column = col_name
                    return col_name
                    
        logger.debug(f"Using provided id_column: {self.id_column}")
        
        # ✅ AGGIUNTA: Salva in cache anche l'id_column fornito
        self._cached_id_column = self.id_column
        return self.id_column

    def _get_description_column(self) -> Optional[str]:
        """Get description column from mapping if available."""
        if self.mapping:
            # 🔄 Nuovo formato: cerca in column_mappings per is_description: true
            for col_name, col_config in self.mapping.get('column_mappings', {}).items():
                if col_config.get('is_description', False):
                    logger.debug(f"Found description column: {col_name}")
                    return col_name
        return None

    def _get_node_type_from_id_column(self) -> str:
        """Get node type from ID column configuration or use default."""
        if self.mapping:
            # Cerca il tipo nella configurazione della colonna ID
            id_column = self._get_id_column()
            if id_column:
                column_config = self.mapping.get('column_mappings', {}).get(id_column, {})
                node_type = column_config.get('node_type')
                if node_type:
                    logger.debug(f"Found node_type from ID column: {node_type}")
                    return node_type
            
            # Fallback: cerca stratigraphic_type globale (formato legacy)
            strat_type = self.mapping.get('stratigraphic_type')
            if strat_type:
                logger.debug(f"Using global stratigraphic_type: {strat_type}")
                return strat_type
        
        # Default
        logger.debug("Using default node type: US")
        return 'US'

    def _is_invalid_id(self, value) -> bool:
        """Check if an ID value is invalid (NaN, empty, etc.)"""
        import pandas as pd
        
        # Controlla NaN
        if pd.isna(value):
            return True
            
        # Controlla None
        if value is None:
            return True
            
        # Controlla stringhe vuote o solo spazi
        if isinstance(value, str) and value.strip() == '':
            return True
            
        # Controlla se è la stringa 'nan', 'null', 'none'
        if isinstance(value, str) and value.lower() in ['nan', 'null', 'none']:
            return True
            
        return False

    def process_row(self, row_data: Dict[str, Any]) -> Node:
        """Process a row using either mapping or automatic mode."""
        try:
            # ✅ AGGIUNTA: Filtra valori NaN PRIMA del processing
            id_column = self._get_id_column()
            if id_column not in row_data:
                raise KeyError(f"ID column '{id_column}' not found in data")
            
            # ✅ AGGIUNTA: Gestione valori NaN
            row_id = row_data[id_column]
            if self._is_invalid_id(row_id):
                raise ValueError(f"Invalid ID value: {row_id}")
            
            # Processo esistente
            if self.mapping:
                return self._process_row_mapped(row_data)
            else:
                return self._process_row_automatic(row_data)
                
        except Exception as e:
            logger.error(f"Error processing row: {e}")
            logger.error(f"Row data: {row_data}")
            raise

    def _process_row_mapped(self, row_data: Dict[str, Any]) -> Node:
        """Process a row with explicit mapping configuration."""
        
        # 🔧 FIX: Usa i metodi helper invece di accesso diretto alle chiavi
        id_column = self._get_id_column()
        description_column = self._get_description_column()
        
        # Get base attributes using helper methods
        base_attrs = {
            'node_id': str(row_data[id_column]),
            'name': str(row_data[id_column]),  # Usa ID come name se non specificato
            'description': str(row_data.get(description_column, '')) if description_column else ''
        }

        strat_type = self.mapping.get('stratigraphic_type', 'US')
        node_class = get_stratigraphic_node_class(strat_type)
        
        existing_node = self.graph.find_node_by_id(base_attrs['node_id'])
        
        if existing_node:
            if self.overwrite:
                existing_node.name = base_attrs['name']
                existing_node.description = base_attrs['description']
                self.warnings.append(f"Updated existing node: {base_attrs['node_id']}")
            strat_node = existing_node
        else:
            strat_node = node_class(
                node_id=base_attrs['node_id'],
                name=base_attrs['name'],
                description=base_attrs['description']
            )
            self.graph.add_node(strat_node)

        # Process properties
        self._process_properties(row_data, base_attrs['node_id'], strat_node)

        return strat_node

    def _process_row_automatic(self, row_data: Dict[str, Any]) -> Node:
        """Process a row creating properties for all non-ID columns."""
        
        id_column = self._get_id_column()
        node_id = str(row_data[id_column])
        
        # Create basic node
        base_attrs = {
            'node_id': node_id,
            'name': node_id,  # Use ID as name in automatic mode
            'description': f"Automatically imported node {node_id}"
        }
        
        # Use default stratigraphic node class
        node_class = get_stratigraphic_node_class('US')
        
        existing_node = self.graph.find_node_by_id(node_id)
        
        if existing_node:
            if self.overwrite:
                existing_node.name = base_attrs['name']
                existing_node.description = base_attrs['description']
                self.warnings.append(f"Updated existing node: {node_id}")
            strat_node = existing_node
        else:
            strat_node = node_class(
                node_id=node_id,
                name=base_attrs['name'],
                description=base_attrs['description']
            )
            self.graph.add_node(strat_node)
        
        # Create properties for all non-ID columns
        for col_name, col_value in row_data.items():
            if col_name != id_column and not self._is_invalid_id(col_value):
                self._create_property(node_id, col_name, col_value)
        
        return strat_node

    def _process_properties(self, row_data: Dict[str, Any], node_id: str, strat_node: Node):
        """Process properties based on mapping configuration."""
        
        # 🔄 Supporta sia nuovo che vecchio formato, ma in modo semplice
        if 'column_mappings' in self.mapping:
            # Formato nuovo: tutte le colonne che non sono speciali diventano proprietà
            id_column = self._get_id_column()
            description_column = self._get_description_column()
            
            for col_name, col_config in self.mapping.get('column_mappings', {}).items():
                # Skip colonne speciali
                if col_name in [id_column, description_column]:
                    continue
                if col_config.get('is_id', False) or col_config.get('is_description', False):
                    continue
                
                if col_name in row_data:
                    prop_value = row_data[col_name]
                    if not self._is_invalid_id(prop_value):
                        # Usa display_name se disponibile
                        prop_name = col_config.get('display_name', col_name)
                        self._create_property(node_id, prop_name, prop_value)
        
        elif 'property_columns' in self.mapping:
            # Formato legacy
            prop_columns = self.mapping.get('property_columns', {})
            for prop_name, col_name in prop_columns.items():
                if col_name in row_data:
                    prop_value = row_data[col_name]
                    if not self._is_invalid_id(prop_value):
                        self._create_property(node_id, prop_name, prop_value)

    def _create_property(self, node_id: str, prop_name: str, prop_value: Any):
        """Create a property node and connect it to the parent node."""
        
        # ✅ Skip se valore non valido
        if self._is_invalid_id(prop_value):
            logger.debug(f"Skipping property {prop_name} with invalid value: {prop_value}")
            return
            
        prop_id = f"{node_id}_{prop_name}"
        existing_prop = self.graph.find_node_by_id(prop_id)

        logger.debug(f"Creating property: {prop_name}")
        logger.debug(f"Property value: {prop_value}")
        
        if existing_prop:
            if self.overwrite:
                existing_prop.value = prop_value
                self.warnings.append(f"Updated existing property: {prop_id}")
        else:
            # Create new property
            prop_node = PropertyNode(
                node_id=prop_id,
                name=prop_name,
                description=str(prop_value),
                value=str(prop_value),
                property_type=prop_name,
                data={},
                url="",
            )
            
            self.graph.add_node(prop_node)

            # Create edge only if it doesn't exist
            edge_id = f"{node_id}_has_property_{prop_id}"
            if not self.graph.find_edge_by_id(edge_id):
                self.graph.add_edge(
                    edge_id=edge_id,
                    edge_source=node_id,
                    edge_target=prop_id,
                    edge_type="has_property"
                )

    def display_warnings(self):
        """Display all accumulated warnings."""
        if self.warnings:
            print("\nWarnings during import:")
            for warning in self.warnings:
                print(f"- {warning}")

    def validate_mapping(self):
        """Validate the mapping configuration if present."""
        if not self.mapping:
            return
            
        # Semplice validazione: deve avere almeno column_mappings
        if 'column_mappings' not in self.mapping:
            # Se non ha column_mappings, potrebbe essere formato legacy - accettalo
            return
        
        # Se ha column_mappings, deve avere almeno un ID
        id_columns = []
        for col_name, col_config in self.mapping.get('column_mappings', {}).items():
            if col_config.get('is_id', False):
                id_columns.append(col_name)
        
        if not id_columns:
            raise ValueError("No ID column found in mapping configuration")

    def get_statistics(self) -> Dict[str, Any]:
        """Get import statistics."""
        stats = {
            'total_nodes': len(self.graph.nodes) if hasattr(self, 'graph') and self.graph else 0,
            'total_edges': len(self.graph.edges) if hasattr(self, 'graph') and self.graph else 0,
            'warnings_count': len(self.warnings),
            'mode': self.mode,
            'mapping_used': self.mapping is not None,
            'id_column': self._get_id_column()
        }
        return stats