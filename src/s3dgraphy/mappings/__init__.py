"""
Mapping system for s3dgraphy.
"""

from .registry import mapping_registry

__all__ = ['mapping_registry']

# Convenience functions for common operations
def add_custom_mapping_directory(mapping_type: str, directory: str, priority: str = 'high'):
    """Add a custom mapping directory. Wrapper for registry.add_mapping_directory."""
    mapping_registry.add_mapping_directory(mapping_type, directory, priority)

def get_available_mappings(mapping_type: str):
    """Get available mappings for a type. Wrapper for registry.list_available_mappings."""
    return mapping_registry.list_available_mappings(mapping_type)

def load_mapping_file(mapping_name: str, mapping_type: str):
    """Load a mapping file. Wrapper for registry.load_mapping."""
    return mapping_registry.load_mapping(mapping_name, mapping_type)