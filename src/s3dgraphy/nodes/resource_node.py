from .base_node import Node

class ResourceNode(Node):
    """
    A RESOURCE node — the resource-layer hinge to an external file/URL (image,
    document, 3D model, point cloud, web page…). Renamed from ``ResourceNode`` in
    MIG1 (2026-08-06); ``node_type`` is now ``"resource"`` (was ``"link"``).

    Attributi:
        url (str): URL del collegamento.
        url_type (str): Tipo di URL (es. "External link", "Image").
        description (str): Descrizione del collegamento.
    """
    node_type="resource"

    # Valid resource types
    RESOURCE_TYPES = {
        "3d_model": ["gltf", "obj", "fbx", "3ds", "blend"],
        "proxy_model": ["glb"],  # Typically GLB for proxies
        "image": ["jpg", "jpeg", "png", "tif", "tiff", "bmp"],
        "document": ["pdf", "doc", "docx", "txt"],
        "web_page": ["http", "https"],
        "video": ["mp4", "avi", "mov"],
        "point_cloud": ["e57", "pts", "las", "laz"]
    }

    def __init__(self, node_id, name="Unnamed Link", url="", url_type="External link", description="No description"):
        """
        Inizializza una nuova istanza di ResourceNode.

        Args:
            node_id (str): Identificatore univoco del nodo.
            name (str, opzionale): Nome del collegamento. Defaults to "Unnamed Link".
            url (str, opzionale): URL del collegamento. Defaults to "".
            url_type (str, opzionale): Tipo di URL. Defaults to "External link".
            description (str, opzionale): Descrizione del collegamento. Defaults to "No description".
        """
        super().__init__(node_id=node_id, name=name)

        # Dati del collegamento
        self.data = {
            "url": url,
            "url_type": url_type or self._determine_url_type(url),
            "description": description or f"Link to {name}"
        }

    @property
    def url(self):
        """Property for convenient access to URL from data dict"""
        return self.data.get("url", "")

    @url.setter
    def url(self, value):
        """Property setter for URL"""
        self.data["url"] = value


    def _determine_url_type(self, url):
        """
        Automatically determine the resource type from the URL/path
        """
        # Check if it's a web URL
        if url.startswith(("http://", "https://")):
            return "web_page"
            
        # Get extension
        ext = url.lower().split('.')[-1] if '.' in url else ''
        
        # Check extension against known types
        for res_type, extensions in self.RESOURCE_TYPES.items():
            if ext in extensions:
                return res_type
                
        # Special case for proxies
        if ext == "glb" and "proxy" in url.lower():
            return "proxy_model"
            
        return "unknown"

    def to_dict(self):
        """
        Converte l'istanza di ResourceNode in un dizionario.

        Returns:
            dict: Rappresentazione del ResourceNode come dizionario.
        """
        return {
            "id": self.node_id,
            "type": self.node_type,
            "name": self.name,
            "description": self.data.get("description", ""),
            "data": {
                "url": self.data.get("url", ""),
                "url_type": self.data.get("url_type", "unknown")
            }
        }




'''
# Creazione di un ResourceNode per un URL Zenodo
resource_node_zenodo = ResourceNode(
    node_id="USM04.zenodo",
    name="ZENODO URL",
    url="https://zenodo.org/record/28917",
    url_type="External link",
    description="Zenodo repository entry"
)

# Creazione di un ResourceNode per un’immagine a risoluzione completa
resource_node_image = ResourceNode(
    node_id="D.01.image",
    name="FullRES Image",
    url="http://aton.ispc.it/image.jpeg",
    url_type="Image",
    description="Full resolution image"
)

# Aggiunta dei nodi al grafo e connessione (esempio con edge tipo "generic")
graph = Graph(graph_id="example_graph")
graph.add_node(resource_node_zenodo)
graph.add_node(resource_node_image)
graph.add_edge(edge_id="link_edge_1", edge_source=resource_node_zenodo.node_id, edge_target="some_target_node", edge_type="generic")
graph.add_edge(edge_id="link_edge_2", edge_source=resource_node_image.node_id, edge_target="some_target_node", edge_type="generic")

'''