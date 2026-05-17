# 3dgraphy/nodes/base_node.py

import json
import os
from importlib.resources import files

def load_json_mapping(filename):
    """
    Load JSON mapping data from a specified file.

    Args:
        filename (str): Name of the JSON file containing mapping data.

    Returns:
        dict: Mapping data loaded from the JSON file.
    """
    try:
        resource = files("s3dgraphy").joinpath("JSON_config", filename)
        with resource.open('r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, ModuleNotFoundError) as e:
        print(f"[s3dgraphy] load_json_mapping('{filename}') failed: {type(e).__name__}: {e}")
        return {}

class Node:
    """
    Base class to represent a node in the graph.

    Attributes:
        node_id (str): Unique identifier for the node.
        name (str): Name of the node.
        node_type (str): Type of the node.
        description (str): Description of the node.
        attributes (dict): Dictionary for additional attributes.
    """
    node_type = "Node"  # Attributo di classe
    node_type_map = {}  # Mappatura tra node_type e classi

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        node_type = getattr(cls, 'node_type', None)
        if node_type:
            Node.node_type_map[node_type] = cls

    def __init__(self, node_id, name, description=""):
        self.node_id = node_id
        self.name = name
        self.description = description
        self.node_type = self.__class__.node_type
        self.attributes = {}

    def add_attribute(self, key, value):
        self.attributes[key] = value
