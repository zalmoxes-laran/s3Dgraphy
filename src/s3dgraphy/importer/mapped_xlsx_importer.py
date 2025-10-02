from .base_importer import BaseImporter
import pandas as pd
from ..graph import Graph
import os
import json
from pathlib import Path
#test
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
            self.graph = existing_graph
            self.graph_id = existing_graph.graph_id
            self._use_existing_graph = True
            print(f"MappedXLSXImporter: Using existing graph {self.graph_id}")
        else:
            self.graph_id = f"imported_{Path(filepath).stem}"
            self.graph = Graph(graph_id=self.graph_id)
            self._use_existing_graph = False
            print(f"MappedXLSXImporter: Created new graph {self.graph_id}")

    def parse(self) -> Graph:
        try:
            table_settings = self.mapping.get('table_settings', {})
            start_row = table_settings.get('start_row', 1)
            sheet_name = table_settings.get('sheet_name', 0)
            tutorial_row = table_settings.get('tutorial_row', None)
            
            # ✅ FIX: Calcola skiprows correttamente
            # header=0 usa SEMPRE la prima riga come header
            # skiprows salta le righe DOPO l'header ma PRIMA dei dati
            if tutorial_row is not None:
                # Se c'è tutorial_row, skippa le righe tra header e start_row
                skip_rows = list(range(1, start_row - 1)) if start_row > 1 else None
            else:
                # Altrimenti mantieni compatibilità vecchio formato
                skip_rows = start_row - 1 if start_row > 1 else None
            
            df = pd.read_excel(
                self.filepath,
                sheet_name=sheet_name,
                header=0,  # ✅ CRITICO: SEMPRE riga 0 come header
                skiprows=skip_rows,
                na_values=['', 'NA', 'N/A'],
                keep_default_na=True
            )
            
            # ✅ Normalizza nomi colonne
            df.columns = df.columns.str.strip()
            
            if df.empty:
                raise ValueError("Excel file is empty")
            
            column_maps = self.mapping.get('column_mappings', {})
            if not column_maps:
                raise ValueError("No column mappings found")
            
            total_rows = 0
            successful_rows = 0      
            skipped_rows = 0

            for _, row in df.iterrows():
                total_rows += 1
                try:
                    # STEP 1: Converti riga in dizionario
                    row_dict = row.to_dict()
                    
                    # STEP 2: Filtra solo colonne nel mapping
                    filtered_row = {k: v for k, v in row_dict.items() if k in column_maps}
                    
                    # STEP 3: Processa la riga
                    result_node = self.process_row(filtered_row)
                    
                    if result_node is not None:
                        successful_rows += 1
                    else:
                        skipped_rows += 1
                        
                except Exception as e:
                    self.warnings.append(f"Error processing row {total_rows}: {str(e)}")

            self.warnings.extend([
                f"\nImport summary:",
                f"Total rows processed: {total_rows}",
                f"Successfully imported: {successful_rows}",
                f"Skipped (not found in existing graph): {skipped_rows}",
                f"Failed/errors: {total_rows - successful_rows - skipped_rows}"
            ])
                
            return self.graph
            
        except Exception as e:
            raise ImportError(f"Error parsing mapped Excel file: {str(e)}")

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