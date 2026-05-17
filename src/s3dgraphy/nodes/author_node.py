from .base_node import Node

class AuthorNode(Node):
    """
    Human author node.

    Represents a human creator/contributor attached to a graph, a swimlane or
    a specific node via the ``has_author`` edge type. In the yEd palette it
    appears as an ImageNode with label prefix ``A.``.

    Attributes:
        orcid (str): ORCID identifier (optional).
        name (str): First name (optional).
        surname (str): Family name (optional).
    """
    node_type = "author"

    def __init__(self, node_id, name="author", description="",
                 orcid="noorcid", surname="nosurname",
                 first_name=None):
        """Initialize a new AuthorNode.

        ``name`` here is the node's display name (kept backwards-compatible
        with existing code that instantiates ``AuthorNode(node_id, name=...)``
        as a generic Node label). The author's given name can also be passed
        explicitly via ``first_name``; when omitted, ``name`` is used as the
        author's given name.
        """
        super().__init__(node_id=node_id, name=name, description=description)

        # Dati dell'autore con valori di fallback
        self.data = {
            "orcid": orcid,
            "name": first_name if first_name is not None else name,
            "surname": surname,
        }

    def to_dict(self):
        return {
            "type": self.node_type,
            "name": self.name,
            "data": self.data,
        }


class AuthorAINode(AuthorNode):
    """
    AI-generated author node (subclass of :class:`AuthorNode`).

    Represents an AI-assisted creator (e.g. LLM, image generator) used while
    authoring parts of the reconstruction. In the yEd palette it appears as
    an ImageNode with label prefix ``AI.``.

    Adds two fields in ``data``:
        model (str): identifier of the AI model or service (e.g. ``gpt-5``,
            ``stable-diffusion-xl``, ``custom-comfyui``).
        prompt_reference (str): optional reference to the prompt / workflow
            used; can be a URL, a DocumentNode id or free text.

    The node_type is ``author_ai`` to keep it distinguishable at the graph
    layer while still resolving as "an author" via
    ``isinstance(n, AuthorNode)`` checks in consumer code.
    """
    node_type = "author_ai"

    def __init__(self, node_id, name="author_ai", description="",
                 orcid="noorcid", surname="nosurname", first_name=None,
                 model="", prompt_reference=""):
        super().__init__(
            node_id=node_id, name=name, description=description,
            orcid=orcid, surname=surname, first_name=first_name,
        )
        self.data["model"] = model
        self.data["prompt_reference"] = prompt_reference

'''
# Esempio di utilizzo per connettere AuthorNode al GraphNode e a nodi specifici
author_node = AuthorNode(node_id="author_1", orcid="noorcid", name="John", surname="Doe")
graph = Graph(graph_id="my_graph")

# Aggiunge l'AuthorNode al grafo
graph.add_node(author_node)

# Connetti l'AuthorNode al GraphNode con edge "generic"
graph.add_edge(edge_id="authorship_1", edge_source=author_node.node_id, edge_target=graph.graph_id, edge_type="generic")

# Connetti l'AuthorNode a un nodo specifico (es. StratigraphicNode) con edge "generic"
stratigraphic_node = StratigraphicNode(node_id="strat_1", name="Stratification A", stratigraphic_type="Layer")
graph.add_node(stratigraphic_node)
graph.add_edge(edge_id="contribution_1", edge_source=author_node.node_id, edge_target=stratigraphic_node.node_id, edge_type="generic")

'''