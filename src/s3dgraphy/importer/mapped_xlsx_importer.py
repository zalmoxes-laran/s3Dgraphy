from .base_importer import BaseImporter
import pandas as pd
from ..graph import Graph
import os
import json
from pathlib import Path

class MappedXLSXImporter(BaseImporter):
    def __init__(self, filepath: str, mapping_name: str, overwrite: bool = False, 
                existing_graph=None):
        """
        Args:
            existing_graph: Existing graph instance to enrich. If None, creates new graph.
        """
        super().__init__(
            filepath=filepath, 
            mapping_name=mapping_name,
            overwrite=overwrite
        )
        
        if existing_graph:
            # Use existing graph
            self.graph = existing_graph
            self.graph_id = existing_graph.graph_id
            self._use_existing_graph = True
            print(f"MappedXLSXImporter: Using existing graph {self.graph_id}")
        else:
            # Create new graph 
            self.graph_id = f"imported_{Path(filepath).stem}"
            self.graph = Graph(graph_id=self.graph_id)
            self._use_existing_graph = False
            print(f"MappedXLSXImporter: Created new graph {self.graph_id}")

    def parse(self) -> Graph:
        """
        Parse Excel file with column name normalization.
        Handles differences between Excel column names (with spaces) and mapping names (with underscores).
        """
        try:
            # Get settings from mapping
            table_settings = self.mapping.get('table_settings', {})
            start_row = table_settings.get('start_row', 0)
            sheet_name = table_settings.get('sheet_name', 0)
            
            print(f"\n=== Starting Mapped XLSX Import ===")
            print(f"File: {self.filepath}")
            print(f"Sheet: {sheet_name}")
            print(f"Start row: {start_row}")
            print(f"Graph ID: {self.graph_id}")
            print(f"PIPPO")
            
            # Read Excel file
            df = pd.read_excel(
                self.filepath,
                sheet_name=sheet_name,
                skiprows=start_row - 1 if start_row > 0 else 0,
                na_values=['', 'NA', 'N/A'],
                keep_default_na=True
            )
            
            if df.empty:
                raise ValueError("Excel file is empty")
            
            # Get column mappings
            column_maps = self.mapping.get('column_mappings', {})
            if not column_maps:
                raise ValueError("No column mappings found in mapping configuration")
            
            # ✅ NORMALIZZAZIONE: Crea dizionario per mappare nomi Excel -> nomi JSON
            # Converte spazi in underscore e tutto in maiuscolo per matching case-insensitive
            excel_columns_normalized = {}
            for excel_col in df.columns:
                # Normalizza: rimuovi spazi extra, sostituisci spazi con underscore, uppercase
                normalized = excel_col.strip().replace(' ', '_').replace('-', '_').upper()
                excel_columns_normalized[normalized] = excel_col
            
            # Crea mapping inverso per JSON -> Excel column names
            json_to_excel_mapping = {}
            unmapped_json_cols = []
            
            for json_col in column_maps.keys():
                # Normalizza nome JSON allo stesso modo
                json_normalized = json_col.strip().replace(' ', '_').replace('-', '_').upper()
                
                if json_normalized in excel_columns_normalized:
                    # Trovata corrispondenza!
                    actual_excel_col = excel_columns_normalized[json_normalized]
                    json_to_excel_mapping[json_col] = actual_excel_col
                    print(f"✓ Matched: '{json_col}' (JSON) -> '{actual_excel_col}' (Excel)")
                else:
                    # Nessuna corrispondenza trovata
                    unmapped_json_cols.append(json_col)
            
            # Log risultati del matching
            print(f"\n=== Column Matching Results ===")
            print(f"Excel columns (original): {list(df.columns)}")
            print(f"Mapping columns (JSON): {list(column_maps.keys())}")
            print(f"\nSuccessfully matched: {len(json_to_excel_mapping)} columns")
            
            if unmapped_json_cols:
                print(f"\n⚠️ WARNING: {len(unmapped_json_cols)} columns from mapping NOT found in Excel:")
                for col in unmapped_json_cols:
                    print(f"  - {col}")
                    self.warnings.append(f"Column '{col}' not found in Excel (after normalization)")
            
            # Verifica che almeno alcune colonne siano state matchate
            if not json_to_excel_mapping:
                raise ValueError("No columns could be matched between mapping and Excel file!")
            
            # Trova la colonna ID
            id_column_json = None
            id_column_excel = None
            for col_name, col_config in column_maps.items():
                if col_config.get('is_id', False):
                    id_column_json = col_name
                    id_column_excel = json_to_excel_mapping.get(col_name)
                    break
            
            if not id_column_excel:
                raise ValueError(f"ID column not found in Excel after normalization")
            
            print(f"\nUsing ID column: '{id_column_json}' (JSON) -> '{id_column_excel}' (Excel)")
            
            # Process rows
            total_rows = 0
            successful_rows = 0
            skipped_rows = 0
            error_rows = 0
            
            print(f"\nProcessing {len(df)} rows...")
            
            for idx, row in df.iterrows():
                total_rows += 1
                
                try:
                    # ✅ IMPORTANTE: Costruisci row_dict usando i nomi JSON come chiavi
                    # ma prendi i valori dalle colonne Excel corrette
                    row_dict = {}
                    
                    for json_col, excel_col in json_to_excel_mapping.items():
                        value = row.get(excel_col)
                        # Solo aggiungi valori non-null
                        if pd.notna(value):
                            row_dict[json_col] = value
                    
                    # Skip righe senza dati
                    if not row_dict:
                        skipped_rows += 1
                        continue
                    
                    # Verifica che l'ID sia presente
                    if id_column_json not in row_dict:
                        skipped_rows += 1
                        print(f"  Row {idx+1}: Skipped (missing ID)")
                        continue
                    
                    # Debug per prime righe
                    if successful_rows < 3:
                        print(f"\n  Row {idx+1} sample data:")
                        for k, v in list(row_dict.items())[:5]:
                            print(f"    {k}: {v}")
                    
                    # Process the row
                    result_node = self.process_row(row_dict)
                    
                    if result_node is not None:
                        successful_rows += 1
                        if (successful_rows % 10) == 0:
                            print(f"  Processed {successful_rows} rows...")
                    else:
                        skipped_rows += 1
                        
                except Exception as e:
                    error_rows += 1
                    error_msg = f"Error processing row {idx+1}: {str(e)}"
                    self.warnings.append(error_msg)
                    print(f"  ❌ {error_msg}")
                    
                    # Debug info for errors
                    if error_rows <= 3:  # Show details for first 3 errors
                        print(f"    Row data sample: {list(row_dict.items())[:3]}")

            # Summary
            print(f"\n=== Import Summary ===")
            print(f"Total rows processed: {total_rows}")
            print(f"✓ Successfully imported: {successful_rows}")
            print(f"⊘ Skipped (no data/ID): {skipped_rows}")
            print(f"✗ Errors: {error_rows}")
            print(f"Columns matched: {len(json_to_excel_mapping)}/{len(column_maps)}")
            
            # Add to warnings for UI
            self.warnings.append(f"\nImport summary:")
            self.warnings.append(f"Rows: {successful_rows}/{total_rows} successful")
            self.warnings.append(f"Columns: {len(json_to_excel_mapping)}/{len(column_maps)} matched")
            
            if unmapped_json_cols:
                self.warnings.append(f"Unmatched columns: {', '.join(unmapped_json_cols[:5])}")
            
            if self.warnings:
                self.display_warnings()
            
            print(f"\nGraph now contains {len(self.graph.nodes)} nodes and {len(self.graph.edges)} edges")
            
            return self.graph
            
        except pd.errors.EmptyDataError:
            error_msg = f"Excel file '{self.filepath}' is empty or invalid"
            self.warnings.append(error_msg)
            raise ValueError(error_msg)
            
        except FileNotFoundError:
            error_msg = f"Excel file not found: {self.filepath}"
            self.warnings.append(error_msg)
            raise
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.warnings.append(error_msg)
            print(f"\n❌ {error_msg}")
            import traceback
            traceback.print_exc()
            raise

    def validate_mapping(self):

        if not self.mapping:
            raise ValueError("No mapping configuration provided")
            
        required_sections = ['table_settings', 'column_mappings']
        missing = [s for s in required_sections if s not in self.mapping]
        if missing:
            raise ValueError(f"Missing required sections in mapping: {', '.join(missing)}")
            
        table_settings = self.mapping.get('table_settings', {})
        if not table_settings.get('sheet_name'):
            raise ValueError("Sheet name not specified in mapping")
            
        column_maps = self.mapping.get('column_mappings', {})
        if not any(cm.get('is_id', False) for cm in column_maps.values()):
            raise ValueError("No ID column specified in mapping")
        
