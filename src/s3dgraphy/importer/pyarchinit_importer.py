# s3Dgraphy/importer/pyarchinit_importer.py

from typing import Dict, Any, Optional
from .base_importer import BaseImporter
import sqlite3
import os
from ..graph import Graph  
from ..nodes.base_node import Node
from ..nodes.property_node import PropertyNode
from ..nodes.stratigraphic_node import StratigraphicNode
from ..utils.utils import get_stratigraphic_node_class
from ..multigraph.multigraph import multi_graph_manager  

class PyArchInitImporter(BaseImporter):
    def __init__(self, filepath: str, mapping_name: str, overwrite: bool = False,
                existing_graph=None):
        """
        Initialize pyArchInit importer with mapping configuration.
        
        Args:
            filepath: Path to the SQLite database
            mapping_name: Name of the JSON mapping file to use
            overwrite: If True, overwrites existing nodes
            existing_graph: Existing graph instance to enrich. If None, creates new graph for 3DGIS.
        """
        super().__init__(
            filepath=filepath, 
            mapping_name=mapping_name,
            overwrite=overwrite
        )

        # Pattern come MappedXLSXImporter
        if existing_graph:
            # Use existing graph (EM_ADVANCED mode)
            self.graph = existing_graph
            self.graph_id = existing_graph.graph_id
            self._use_existing_graph = True
            print(f"PyArchInitImporter: Using existing graph {self.graph_id}")
        else:
            # Create new graph (3DGIS mode)
            self.graph_id = "3dgis_graph"
            self.graph = Graph(graph_id=self.graph_id)
            self._use_existing_graph = False
            print(f"PyArchInitImporter: Created new graph {self.graph_id}")
            
            # Registra il grafo nel MultiGraphManager solo se nuovo
            multi_graph_manager.graphs[self.graph_id] = self.graph
            print(f"PyArchInitImporter: Registered graph {self.graph_id}")
            print(f"Current registered graphs: {list(multi_graph_manager.graphs.keys())}")

        self.validate_mapping()

    def process_row(self, row_dict: Dict[str, Any]) -> Optional[Node]:
        """Process a row from pyArchInit database"""
        try:
            # 1️⃣ Get ID column and convert if numeric
            id_column = self._get_id_column()
            if isinstance(row_dict.get(id_column), (int, float)):
                row_dict[id_column] = str(row_dict[id_column])
                
            node_name = str(row_dict[id_column])  # Es: "1001"
            
            print(f"\n=== Processing pyArchInit row ===")
            print(f"Node name from DB: {node_name}")
            
            # 2️⃣ Check if we're enriching existing graph
            is_enriching_existing = self._use_existing_graph and len(self.graph.nodes) > 0
            print(f"Enriching existing graph: {is_enriching_existing}")
            
            # 3️⃣ Try to find existing node by NAME (not ID!)
            existing_node = self._find_node_by_name(node_name)
            
            if existing_node:
                # ✅ Node found in existing graph: only add properties
                print(f"✓ Found existing node: {existing_node.name} (ID: {existing_node.node_id})")
                print(f"  → Adding properties to existing node")
                
                # Get description from mapping
                desc_column = self._get_description_column()
                description = row_dict.get(desc_column) if desc_column else None
                
                # Update description if overwrite is enabled
                if self.overwrite and description:
                    existing_node.description = str(description)
                
                # Process properties for existing node
                self._process_pyarchinit_properties(row_dict, existing_node)
                return existing_node
                
            elif is_enriching_existing:
                # ❌ Enriching mode but node not found → SKIP this row
                warning_msg = f"Node '{node_name}' not found in existing graph - SKIPPED"
                self.warnings.append(warning_msg)
                print(f"⊘ {warning_msg}")
                return None
                
            else:
                # ✅ Creating new graph → create new stratigraphic node
                print(f"✓ Creating new stratigraphic node: {node_name}")
                
                # Get description from mapping
                desc_column = self._get_description_column()
                description = row_dict.get(desc_column) if desc_column else "pyarchinit element"
                
                # Get node type from id column mapping
                id_col_config = self.mapping['column_mappings'][id_column]
                strat_type = id_col_config.get('node_type', 'US')
                node_class = get_stratigraphic_node_class(strat_type)
                
                # Create new node with UUID
                import uuid
                new_node = node_class(
                    node_id=str(uuid.uuid4()),
                    name=node_name,
                    description=str(description)
                )
                
                self.graph.add_node(new_node)
                print(f"  → Node created with ID: {new_node.node_id}")
                
                # Process properties for new node
                self._process_pyarchinit_properties(row_dict, new_node)
                return new_node

        except KeyError as e:
            self.warnings.append(f"Missing required column: {str(e)}")
            raise

    def _process_pyarchinit_properties(self, row_dict: Dict[str, Any], strat_node: Node):
        """
        Process property columns for a stratigraphic node.
        Only creates properties if they have non-empty values.
        """
        print(f"\n  Processing properties for node: {strat_node.name}")
        
        for col_name, col_config in self.mapping.get('column_mappings', {}).items():
            # Skip ID and description columns
            if col_config.get('is_id', False) or col_config.get('is_description', False):
                continue
                
            if col_config.get('property_name'):
                value = row_dict.get(col_name, '')
                
                # ✅ IMPORTANTE: Crea proprietà SOLO se valore esiste e non è vuoto
                if value and str(value).strip():
                    property_id = f"{strat_node.node_id}_{col_config['property_name']}"
                    
                    # Check if property already exists
                    existing_prop = self.graph.find_node_by_id(property_id)
                    
                    if existing_prop:
                        # Update existing property if overwrite enabled
                        if self.overwrite:
                            existing_prop.value = str(value)
                            existing_prop.description = str(value)
                            print(f"    ↻ Updated property: {col_config['property_name']} = '{value}'")
                    else:
                        # Create new property node
                        property_node = PropertyNode(
                            node_id=property_id,
                            name=col_config['property_name'],
                            description=str(value),
                            value=str(value),
                            property_type=col_config['property_name']
                        )
                        self.graph.add_node(property_node)
                        print(f"    + Created property: {col_config['property_name']} = '{value}'")
                        
                        # Create edge between stratigraphic node and property
                        edge_id = f"{strat_node.node_id}_has_property_{property_id}"
                        if not self.graph.find_edge_by_id(edge_id):
                            self.graph.add_edge(
                                edge_id=edge_id,
                                edge_source=strat_node.node_id,
                                edge_target=property_id,
                                edge_type="has_property"
                            )
                else:
                    # Valore vuoto o mancante - non creare proprietà
                    print(f"    ⊘ Skipped property: {col_config['property_name']} (empty value)")

    def _get_description_column(self) -> Optional[str]:
        """Get description column from mapping"""
        for col_name, col_config in self.mapping.get('column_mappings', {}).items():
            if col_config.get('is_description', False):
                return col_name
        return None

    def parse(self) -> Graph:
        """Parse pyArchInit database using mapping configuration"""
        try:
            print("\n=== Starting PyArchInit Import ===")
            conn = sqlite3.connect(self.filepath)
            cursor = conn.cursor()
            
            # Debug del mapping
            print(f"\nMapping configuration:")
            print(f"Filepath: {self.filepath}")
            print(f"Table settings: {self.mapping.get('table_settings', {})}")
            print(f"Column mappings: {self.mapping.get('column_mappings', {})}")
            
            # Get table name from mapping
            table_settings = self.mapping.get('table_settings', {})
            table_name = table_settings.get('table_name')
            
            if not table_name:
                raise ValueError("Table name not specified in mapping configuration")
            
            print(f"\nReading from table: {table_name}")
            
            # Query all rows from table
            cursor.execute(f"SELECT * FROM {table_name}")
            columns = [description[0] for description in cursor.description]
            print(f"Columns found: {columns}")
            
            rows = cursor.fetchall()
            print(f"Total rows to process: {len(rows)}")
            
            successful_rows = 0
            skipped_rows = 0
            error_rows = 0
            
            # Process each row
            for idx, row in enumerate(rows, 1):
                try:
                    # Convert row to dictionary
                    row_dict = dict(zip(columns, row))
                    
                    # Process the row
                    result = self.process_row(row_dict)
                    
                    if result is not None:
                        successful_rows += 1
                        if (successful_rows % 10) == 0:
                            print(f"Processed {successful_rows} rows...")
                    else:
                        skipped_rows += 1
                        
                except Exception as e:
                    error_rows += 1
                    error_msg = f"Error processing row {idx}: {str(e)}"
                    self.warnings.append(error_msg)
                    print(f"❌ {error_msg}")
            
            conn.close()
            
            # Summary
            print(f"\n=== Import Summary ===")
            print(f"Total rows: {len(rows)}")
            print(f"✓ Successfully imported: {successful_rows}")
            print(f"⊘ Skipped: {skipped_rows}")
            print(f"✗ Errors: {error_rows}")
            print(f"Final graph size: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
            
            # Add to warnings for UI
            self.warnings.append(f"\nImport summary:")
            self.warnings.append(f"Successfully imported: {successful_rows}/{len(rows)}")
            if skipped_rows > 0:
                self.warnings.append(f"Skipped rows (not in graph): {skipped_rows}")
            if error_rows > 0:
                self.warnings.append(f"Errors: {error_rows}")
            
            return self.graph
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise ImportError(f"Error parsing pyArchInit database: {str(e)}")