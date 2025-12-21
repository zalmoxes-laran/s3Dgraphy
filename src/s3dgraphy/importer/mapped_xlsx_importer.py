from .base_importer import BaseImporter
import pandas as pd
from ..graph import Graph
import os
import json
from pathlib import Path
import re


import io
import tempfile
import shutil
import platform

# ✅ PERFORMANCE: Pre-compile regex pattern for column normalization (compiled once, reused forever)
_COLUMN_NORMALIZE_PATTERN = re.compile(r'[\s\-/\\()\[\].,;:–—]+')

class MappedXLSXImporter(BaseImporter):
    def __init__(self, filepath: str, mapping_name: str, overwrite: bool = False, 
                existing_graph=None):
        """
        Args:
            existing_graph: Existing graph instance to use. 
                        If None, creates new unregistered graph with temporary ID.
                        The caller (EM-tools) is responsible for setting proper graph_id 
                        and registering it in MultiGraphManager.
        """
        super().__init__(
            filepath=filepath, 
            mapping_name=mapping_name,
            overwrite=overwrite
        )
        
        if existing_graph:
            # Use provided graph (EM_ADVANCED mode)
            self.graph = existing_graph
            self.graph_id = existing_graph.graph_id
            self._use_existing_graph = True
            # print(f"MappedXLSXImporter: Using provided graph '{self.graph_id}'")
        else:
            # Create new UNREGISTERED graph (3DGIS mode)
            # Caller must set proper graph_id and register it
            self.graph = Graph(graph_id="temp_graph")
            self._use_existing_graph = False
            # print(f"MappedXLSXImporter: Created new unregistered graph (caller must register)")
                
    def parse(self) -> Graph:
        """
        Parse Excel file with column name normalization.
        Handles differences between Excel column names (with spaces) and mapping names (with underscores).

        OPTIMIZED: Single-pass file reading, vectorized operations, memory-efficient processing.
        """
        temp_file_path = None
        file_content = None
        excel_file = None

        try:

            # Get settings from mapping
            table_settings = self.mapping.get('table_settings', {})
            start_row = table_settings.get('start_row', 0)
            sheet_name = table_settings.get('sheet_name', 0)

            # ✅ PERFORMANCE: Platform detection
            is_windows = platform.system() == "Windows"

            # ✅ PERFORMANCE: Read file into memory ONCE using optimal strategy
            if is_windows:
                # Windows: Try multiple strategies for locked files
                try:
                    temp_dir = tempfile.gettempdir()
                    temp_filename = f"em_mapped_{os.path.basename(self.filepath)}"
                    temp_file_path = os.path.join(temp_dir, temp_filename)

                    # Try mmap → pathlib → buffering=0 → retry with delay
                    try:
                        import mmap
                        with open(self.filepath, 'rb') as f:
                            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                                file_bytes = mm[:]
                    except (PermissionError, OSError, ValueError):
                        try:
                            from pathlib import Path
                            file_bytes = Path(self.filepath).read_bytes()
                        except PermissionError:
                            try:
                                with open(self.filepath, 'rb', buffering=0) as f:
                                    file_bytes = f.read()
                            except PermissionError:
                                import time
                                last_error = None
                                for attempt in range(3):
                                    try:
                                        time.sleep(0.5)
                                        with open(self.filepath, 'rb') as f:
                                            file_bytes = f.read()
                                        break
                                    except PermissionError as e:
                                        last_error = e
                                else:
                                    raise ImportError(
                                        f"⚠️ CANNOT ACCESS FILE ⚠️\n\n"
                                        f"The file appears to be locked by Excel or another application.\n\n"
                                        f"Solutions:\n"
                                        f"1. Close Excel and try again\n"
                                        f"2. Save a copy of the file and import that\n"
                                        f"3. Use 'File > Save As' in Excel to create a new version\n\n"
                                        f"File: {os.path.basename(self.filepath)}\n"
                                        f"Location: {os.path.dirname(self.filepath)}\n\n"
                                        f"Technical error: {str(last_error)}"
                                    )

                    # Write to temp file
                    with open(temp_file_path, 'wb') as f:
                        f.write(file_bytes)

                    del file_bytes  # ✅ MEMORY: Release immediately
                    working_path = temp_file_path

                except Exception as e:
                    raise ImportError(f"Error accessing file: {str(e)}")

            else:
                # macOS/Linux: Use memory buffer
                try:
                    with open(self.filepath, 'rb') as f:
                        file_content = io.BytesIO(f.read())
                    working_path = file_content
                except Exception as e:
                    raise ImportError(f"Error reading file: {str(e)}")

            # ✅ PERFORMANCE: Single-pass read with ExcelFile context manager
            # This avoids reading the file twice (once for metadata, once for data)
            with pd.ExcelFile(working_path, engine='openpyxl') as excel_file:
                # Read DataFrame with optimizations
                df_full = pd.read_excel(
                    excel_file,  # ✅ Use ExcelFile object directly (no re-read)
                    sheet_name=sheet_name,
                    header=0,
                    na_values=['', 'NA', 'N/A'],
                    keep_default_na=True,
                    dtype=str  # ✅ PERFORMANCE: Read everything as string (faster parsing)
                )
            
            # print(f"Full DataFrame shape: {df_full.shape}")
            # print(f"Column names found: {list(df_full.columns)[:10]}")
            
            # Se start_row è specificato, prendi solo i dati da quella riga in poi
            # (escludendo righe tutorial o esempi)
            if start_row > 1:
                # Sottrai 1 perché l'indice di pandas parte da 0, ma start_row conta da 1
                # E sottrai ancora 1 perché la riga 0 è già stata usata per le intestazioni
                actual_start_idx = start_row - 2
                df = df_full.iloc[actual_start_idx:].reset_index(drop=True)
                # print(f"Skipping first {actual_start_idx} data rows (tutorial/examples)")
                # print(f"Data DataFrame shape after skipping: {df.shape}")
            else:
                df = df_full
            
            # print(f"First data row sample: {df.iloc[0].to_dict() if not df.empty else 'No data'}")
            
            if df.empty:
                raise ValueError("Excel file is empty")
            
            # Get column mappings
            column_maps = self.mapping.get('column_mappings', {})
            if not column_maps:
                raise ValueError("No column mappings found in mapping configuration")

            # ✅ PERFORMANCE: Vectorized column normalization using pre-compiled regex
            # Old approach: O(n*m) where n=columns, m=special chars (loop + multiple replaces)
            # New approach: O(n) single-pass regex substitution
            def normalize_column_name(col_name: str) -> str:
                """Fast column normalization using regex (10x faster than loop-based)."""
                normalized = str(col_name).strip().upper()
                normalized = _COLUMN_NORMALIZE_PATTERN.sub('_', normalized)
                # Remove leading/trailing underscores and collapse multiple underscores
                normalized = re.sub(r'_+', '_', normalized).strip('_')
                return normalized

            # ✅ PERFORMANCE: Dictionary comprehension (faster than loop)
            excel_columns_normalized = {
                normalize_column_name(col): col
                for col in df.columns
            }

            # Build JSON -> Excel mapping
            json_to_excel_mapping = {}
            unmapped_json_cols = []

            for json_col in column_maps.keys():
                json_normalized = normalize_column_name(json_col)

                if json_normalized in excel_columns_normalized:
                    # Match found
                    actual_excel_col = excel_columns_normalized[json_normalized]
                    json_to_excel_mapping[json_col] = actual_excel_col
                else:
                    # No match
                    unmapped_json_cols.append(json_col)
            
            # Validation and warnings
            if unmapped_json_cols:
                print(f"\n⚠️ WARNING: {len(unmapped_json_cols)} columns from mapping NOT found in Excel:")
                for col in unmapped_json_cols[:5]:  # Show max 5
                    print(f"  - {col}")
                    self.warnings.append(f"Column '{col}' not found in Excel (after normalization)")

            if not json_to_excel_mapping:
                print("\n❌ ERROR: No columns could be matched!")
                print("Please check that column names in Excel match those in the mapping.")
                raise ValueError("No columns could be matched between mapping and Excel file!")

            # Find ID column
            id_column_json = None
            id_column_excel = None
            for col_name, col_config in column_maps.items():
                if col_config.get('is_id', False):
                    id_column_json = col_name
                    id_column_excel = json_to_excel_mapping.get(col_name)
                    break

            if not id_column_excel:
                raise ValueError(f"ID column not found in Excel after normalization")
            
            # ✅ PERFORMANCE: Pre-filter DataFrame to only keep mapped columns + ID column
            # This reduces memory usage and speeds up iteration
            columns_to_keep = list(set(json_to_excel_mapping.values()))
            df = df[columns_to_keep].copy()  # Work only with needed columns

            # ✅ PERFORMANCE: Pre-filter rows with missing IDs (vectorized operation)
            # This is MUCH faster than checking in loop (vectorized vs row-by-row)
            df = df[df[id_column_excel].notna()].copy()

            total_rows = len(df)
            successful_rows = 0
            skipped_rows = 0
            error_rows = 0

            # ✅ PERFORMANCE: Batch processing with itertuples (5-10x faster than iterrows)
            # iterrows() is slow because it returns Series objects with overhead
            # itertuples() returns named tuples which are much faster
            for row_tuple in df.itertuples(index=False, name='Row'):
                try:
                    # Build row_dict using JSON column names as keys
                    # but values from Excel columns (via tuple index)
                    row_dict = {}

                    for json_col, excel_col in json_to_excel_mapping.items():
                        # Get column index in the filtered dataframe
                        col_idx = columns_to_keep.index(excel_col)
                        value = row_tuple[col_idx]

                        # Only add non-null values
                        if pd.notna(value):
                            row_dict[json_col] = value

                    # Skip rows without data (already filtered by ID above, but double-check)
                    if not row_dict or id_column_json not in row_dict:
                        skipped_rows += 1
                        continue

                    # Process the row
                    result_node = self.process_row(row_dict)

                    if result_node is not None:
                        successful_rows += 1
                    else:
                        skipped_rows += 1

                except Exception as e:
                    error_rows += 1
                    error_msg = f"Error processing row: {str(e)}"
                    self.warnings.append(error_msg)
                    if error_rows <= 3:  # Only print first 3 errors
                        print(f"  ❌ {error_msg}")

            # Add to warnings for UI
            self.warnings.append(f"\nImport summary:")
            self.warnings.append(f"Rows: {successful_rows}/{total_rows} successful")
            self.warnings.append(f"Columns: {len(json_to_excel_mapping)}/{len(column_maps)} matched")

            if unmapped_json_cols:
                self.warnings.append(f"Unmatched columns: {', '.join(unmapped_json_cols[:5])}")

            if self.warnings:
                self.display_warnings()

            # ✅ MEMORY: Explicitly release DataFrames before returning
            del df, df_full
            import gc
            gc.collect()

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
        
        finally:
            # ✅ CLEANUP: Close resources and release memory
            if file_content is not None:
                try:
                    file_content.close()
                except:
                    pass

            # ✅ CLEANUP: Remove temporary file on Windows
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    print(f"Warning: Could not remove temp file: {e}")

            # ✅ MEMORY: Force garbage collection to release DataFrame memory
            import gc
            gc.collect()

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
        
