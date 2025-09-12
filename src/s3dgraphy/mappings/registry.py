"""
Mapping registry system for s3dgraphy.
Allows applications to register custom mapping directories.
"""

import os
import json
from typing import Dict, List, Optional, Any

class MappingRegistry:
    """Registry for managing mapping file directories and search paths."""
    
    def __init__(self):
        self._mapping_directories = {
            'pyarchinit': [],
            'emdb': [],
            'generic': []
        }
        self._initialize_builtin_paths()
    
    def _initialize_builtin_paths(self):
        """Initialize built-in mapping paths."""
        base_path = os.path.dirname(__file__)
        
        # Built-in paths (questi hanno priorità bassa)
        self._mapping_directories['pyarchinit'].append(
            os.path.join(base_path, 'pyarchinit')
        )
        self._mapping_directories['emdb'].append(
            os.path.join(base_path, 'emdb')
        )
        self._mapping_directories['generic'].append(
            os.path.join(base_path, 'generic')
        )
    
    def add_mapping_directory(self, mapping_type: str, directory: str, priority: str = 'high'):
        """
        Add a custom mapping directory.
        
        Args:
            mapping_type: Type of mapping ('pyarchinit', 'emdb', 'generic')
            directory: Path to the directory containing mapping files
            priority: 'high' = search first, 'low' = search after built-in
        """
        if mapping_type not in self._mapping_directories:
            self._mapping_directories[mapping_type] = []
        
        if not os.path.exists(directory):
            raise ValueError(f"Mapping directory does not exist: {directory}")
        
        if priority == 'high':
            # Insert at beginning (search first)
            self._mapping_directories[mapping_type].insert(0, directory)
        else:
            # Append at end (search last)
            self._mapping_directories[mapping_type].append(directory)
    
    def get_mapping_directories(self, mapping_type: str) -> List[str]:
        """Get all directories for a mapping type in search order."""
        return self._mapping_directories.get(mapping_type, [])
    
    def find_mapping_file(self, mapping_name: str, mapping_type: str) -> Optional[str]:
        """
        Find a mapping file by name and type.
        
        Args:
            mapping_name: Name of the mapping file (with or without .json)
            mapping_type: Type of mapping
            
        Returns:
            Full path to the mapping file, or None if not found
        """
        if not mapping_name.endswith('.json'):
            mapping_name = f"{mapping_name}.json"
        
        directories = self.get_mapping_directories(mapping_type)
        
        for directory in directories:
            file_path = os.path.join(directory, mapping_name)
            if os.path.exists(file_path):
                return file_path
        
        return None
    
    def load_mapping(self, mapping_name: str, mapping_type: str) -> Optional[Dict[str, Any]]:
        """
        Load a mapping file by name and type.
        
        Args:
            mapping_name: Name of the mapping file
            mapping_type: Type of mapping
            
        Returns:
            Mapping data as dictionary, or None if not found
        """
        file_path = self.find_mapping_file(mapping_name, mapping_type)
        
        if not file_path:
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading mapping {mapping_name}: {str(e)}")
            return None
    
    def list_available_mappings(self, mapping_type: str) -> List[tuple]:
        """
        List all available mappings for a type.
        
        Returns:
            List of tuples: (file_id, display_name, description)
        """
        mappings = []
        seen_files = set()  # Evita duplicati
        
        directories = self.get_mapping_directories(mapping_type)
        
        for directory in directories:
            if not os.path.exists(directory):
                continue
                
            try:
                for file in os.listdir(directory):
                    if file.endswith('.json') and file not in seen_files:
                        seen_files.add(file)
                        
                        file_path = os.path.join(directory, file)
                        file_id = os.path.splitext(file)[0]
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                display_name = data.get("name", file_id)
                                description = data.get("description", "")
                                mappings.append((file_id, display_name, description))
                        except Exception as e:
                            print(f"Error reading mapping {file}: {str(e)}")
                            # Fallback: usa il nome del file
                            mappings.append((file_id, file_id, ""))
                            
            except OSError as e:
                print(f"Error scanning directory {directory}: {str(e)}")
                continue
        
        return mappings

# Global instance
mapping_registry = MappingRegistry()