# s3Dgraphy/importer/xlsx_importer.py

import pandas as pd
from typing import Dict, Any
from .base_importer import BaseImporter
from ..graph import Graph

class XLSXImporter(BaseImporter):
    """
    Importer for Excel (.xlsx) files.
    Supports both mapped and automatic property creation modes.
    """
    
    def __init__(self, filepath: str, mapping_name: str = None, id_column: str = None, overwrite: bool = False):
        """
        Initialize the XLSX importer.
        
        Args:
            filepath (str): Path to the XLSX file
            mapping_name (str, optional): Name of the mapping configuration to use
            id_column (str, optional): Name of the ID column when not using mapping
            overwrite (bool, optional): If True, overwrites existing values
        """
        super().__init__(filepath, mapping_name, id_column, overwrite)
        self._validate_settings()

    def _validate_settings(self):
        """
        Validate importer settings based on mode (mapped or automatic).
        
        Raises:
            ValueError: If required settings are missing or invalid
        """
        if self.mapping:
            self._validate_mapping()
        else:
            if not self.id_column:
                raise ValueError("id_column must be provided when not using mapping")

    def _validate_mapping(self):
        """
        Validate that the mapping configuration has all required fields.
        
        Raises:
            ValueError: If required fields are missing from mapping
        """
        required_fields = ['id_column', 'name_column']
        missing_fields = [field for field in required_fields if field not in self.mapping]
        
        if missing_fields:
            raise ValueError(f"Missing required fields in mapping: {', '.join(missing_fields)}")

    def _read_excel_file(self):
        """
        Read the Excel file using pandas.
        
        Returns:
            pd.DataFrame: The loaded DataFrame
            
        Raises:
            ImportError: If there's an error reading the file
        """
        try:
            # Determine sheet name or index
            sheet_name = self.mapping.get('sheet_name', 0) if self.mapping else 0
            
            # Read Excel with proper settings
            df = pd.read_excel(
                self.filepath,
                sheet_name=sheet_name,
                na_values=['', 'NA', 'N/A'],
                keep_default_na=True
            )
            
            # Basic validation
            if df.empty:
                raise ValueError("Excel file is empty")
                
            return df
            
        except Exception as e:
            raise ImportError(f"Error reading Excel file: {str(e)}")

    def _validate_dataframe(self, df: pd.DataFrame):
        """
        Validate the loaded DataFrame has required columns.
        
        Args:
            df (pd.DataFrame): The DataFrame to validate
            
        Raises:
            ValueError: If required columns are missing
        """
        # Check ID column exists
        id_column = self.mapping['id_column'] if self.mapping else self.id_column
        if id_column not in df.columns:
            raise ValueError(f"ID column '{id_column}' not found in Excel file")
            
        # If using mapping, check other required columns
        if self.mapping:
            required_columns = [self.mapping['id_column'], self.mapping['name_column']]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Required columns missing: {', '.join(missing_columns)}")

    def _clean_row_data(self, row: pd.Series) -> Dict[str, Any]:
        """
        Clean and prepare row data for processing.
        
        Args:
            row (pd.Series): The row from DataFrame
            
        Returns:
            dict: Cleaned row data
        """
        # Convert row to dictionary
        row_dict = row.to_dict()
        
        # Clean values
        cleaned_data = {}
        for key, value in row_dict.items():
            # Handle various types of null values
            if pd.isna(value):
                continue
                
            # Convert numbers to appropriate type
            if isinstance(value, (int, float)):
                cleaned_data[key] = value
            else:
                # Clean strings
                cleaned_value = str(value).strip()
                if cleaned_value:  # Only include non-empty strings
                    cleaned_data[key] = cleaned_value
                    
        return cleaned_data

    def parse(self) -> Graph:
        """Parse the Excel file and create nodes in the graph."""
        try:
            # ✅ Leggi configurazione tabella
            table_settings = self.mapping.get('table_settings', {})
            start_row = table_settings.get('start_row', 0)
            sheet_name = table_settings.get('sheet_name', 0)
            
            # ✅ Leggi Excel con pandas
            df = pd.read_excel(
                self.filepath,
                sheet_name=sheet_name,
                skiprows=start_row - 1 if start_row > 0 else 0,
                na_values=['', 'NA', 'N/A'],
                keep_default_na=True
            )
            
            if df.empty:
                raise ValueError("Excel file is empty")
            
            column_maps = self.mapping.get('column_mappings', {})
            if not column_maps:
                raise ValueError("No column mappings found")
            
            # ✅ Statistiche import
            total_rows = 0
            successful_rows = 0
            skipped_rows = 0
            
            # ✅ FIX PRINCIPALE: Usa i nomi delle colonne del DataFrame, non l'ordine del JSON
            for _, row in df.iterrows():
                total_rows += 1
                try:
                    # STEP 1: Converti la riga in dizionario usando i NOMI delle colonne del DataFrame
                    # Questo risolve il problema del disallineamento colonne
                    row_dict = row.to_dict()
                    
                    # STEP 2: Filtra solo le colonne presenti nel mapping
                    # Ignora colonne extra nell'Excel che non sono nel mapping
                    filtered_row = {k: v for k, v in row_dict.items() if k in column_maps}
                    
                    # STEP 3: Opzionale - pulisci i valori NaN esplicitamente PRIMA del processing
                    # Questo evita che NaN arrivino a _create_property
                    import pandas as pd
                    cleaned_row = {}
                    for k, v in filtered_row.items():
                        # Converti NaN in None per gestione consistente
                        if pd.isna(v):
                            cleaned_row[k] = None
                        else:
                            cleaned_row[k] = v
                    
                    # STEP 4: Processa la riga con i dati corretti
                    result_node = self.process_row(cleaned_row)
                    
                    if result_node is not None:
                        successful_rows += 1
                    else:
                        skipped_rows += 1
                        
                except Exception as e:
                    self.warnings.append(f"Error processing row {total_rows}: {str(e)}")
            
            # ✅ Aggiungi summary alle warnings
            self.warnings.extend([
                f"\nImport summary:",
                f"Total rows processed: {total_rows}",
                f"Successfully imported: {successful_rows}",
                f"Skipped rows: {skipped_rows}",
                f"Failed/errors: {total_rows - successful_rows - skipped_rows}"
            ])
            
            return self.graph
            
        except Exception as e:
            raise ImportError(f"Error parsing mapped Excel file: {str(e)}")

    def _get_sheet_names(self) -> list:
        """
        Get list of sheet names from Excel file.
        
        Returns:
            list: List of sheet names
        """
        try:
            return pd.ExcelFile(self.filepath).sheet_names
        except Exception as e:
            self.warnings.append(f"Error reading sheet names: {str(e)}")
            return []