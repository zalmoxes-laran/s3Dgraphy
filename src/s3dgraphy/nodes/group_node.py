#s3Dgraphy/nodes/group_node.py
from .base_node import Node

# GroupNode Class
class GroupNode(Node):
    """
    Nodo che rappresenta un gruppo di nodi. Tali gruppi possono essere di vari tipi: vedi sottoclassi di seguito.

    Attributes:
        y_pos (float): Posizione verticale del nodo.
    """
    node_type = "Group"
    def __init__(self, node_id, name, description="", y_pos=0.0):
        super().__init__(node_id, name, description=description)
        self.attributes['y_pos'] = y_pos

class ActivityNodeGroup(GroupNode):
    """
    Nodo gruppo per attività. Una attività è un gruppo logico di azioni che vengono tenute insieme per un fine narrativo e di ordine delle informazioni (es: costruzione di una stanza di un edificio nell'anno x, attività di restauro di varie parti di quella stanza 20 anni dopo)

    """
    node_type = "ActivityNodeGroup"
    def __init__(self, node_id, name, description="", y_pos=0.0):
        super().__init__(node_id, name, description=description, y_pos=y_pos)
        #self.node_type = "ActivityNodeGroup"

class ParadataNodeGroup(GroupNode):
    """
    Nodo gruppo per paradata. Questo gruppo tiene insieme tutti i paradati relativi ad una unità stratigrafica: normalmente si chiama "[nome_US]_PD" (ParaData)

    """

    node_type = "ParadataNodeGroup"

    def __init__(self, node_id, name, description="", y_pos=0.0):
        super().__init__(node_id, name, description=description, y_pos=y_pos)
        #self.node_type = "ParadataNodeGroup"


class TimeBranchNodeGroup(GroupNode):
    """
    Group node to aggregate all elements belonging to a time branch. Two TB can be connected by a "contrasts_with" edge.

    """
    node_type = "TimeBranchNodeGroup"
    def __init__(self, node_id, name, description="", y_pos=0.0):
        super().__init__(node_id, name, description=description, y_pos=y_pos)
        #self.node_type = "TimeBranchNodeGroup"


class LocationNodeGroup(GroupNode):
    """
    Group node for spatial / locational membership of stratigraphic units
    and paradata. Orthogonal to ``ActivityNodeGroup`` (intention) and
    ``EpochNode`` (time): a Location answers the question *what (named)
    place is this in?*.

    Three required *kinds* coexist on the same axis and may compose on
    the same node:

    - ``toponym``    — external / administrative identity
                       (Pompei, Lazio, Italia)
    - ``study``      — operational / procedural identity
                       (saggio, settore, quadrato, sondage)
    - ``functional`` — interpretive / semantic identity
                       (basilica, room A, courtyard)

    Propagation is **additive**: multiple memberships compose, none
    overrides — distinct from ``EpochNode`` which is substitutive
    (finest-grained wins).

    Membership is **m:n** via multiple ``is_in_location`` edges. A wall
    between two rooms belongs to both. The optional ``is_primary: True``
    attribute on one of the edges marks the membership that should be
    rendered as a yEd group folder in em-graph (yEd cannot draw
    overlapping group folders).

    Locations are **hierarchical**: a ``LocationNodeGroup`` can itself
    be ``is_in_location`` of another ``LocationNodeGroup``
    (Pompei → Sector 4 → Casa del Fauno → Room 12).

    A Location is **identitary**, not geometric. For coordinates / EPSG
    / shifts use the dedicated ``GeoPositionNode``. The two concepts are
    linked at the CIDOC level via P161 has spatial projection
    (E53 Place → E94 Space Primitive).

    CIDOC-CRM mapping:
      - the ``LocationNodeGroup`` itself        →  E53 Place
      - the ``kind`` attribute classifies it    →  E55 Type
      - ``is_in_location`` (node → location)    →  P53 has former or current location
      - ``is_in_location`` (location → location, recursive)
                                                →  P89 falls within
      - non-CIDOC fields (``is_primary``,
        ``propagation``, ``kind`` enum value)   →  ``s3d:`` extension URIs

    Originating discussion:
        https://github.com/zalmoxes-laran/s3Dgraphy/issues/5
    """

    node_type = "LocationNodeGroup"

    VALID_KINDS = ("toponym", "study", "functional")
    VALID_PROPAGATIONS = ("additive", "substitutive")

    def __init__(self, node_id, name, kind, description="",
                 propagation="additive", y_pos=0.0):
        if kind not in self.VALID_KINDS:
            raise ValueError(
                "LocationNodeGroup.kind must be one of "
                f"{self.VALID_KINDS}, got {kind!r}"
            )
        if propagation not in self.VALID_PROPAGATIONS:
            raise ValueError(
                "LocationNodeGroup.propagation must be one of "
                f"{self.VALID_PROPAGATIONS}, got {propagation!r}"
            )
        super().__init__(node_id, name, description=description, y_pos=y_pos)
        # Required spatial-plane discriminator. Stored both as a Python
        # attribute (ergonomic access) and inside the .attributes dict
        # (for serialisers / round-trip with the JSON datamodel).
        self.kind = kind
        self.attributes['kind'] = kind
        # Declarative propagation flag. Location is additive by default
        # (memberships compose). Kept declarative so that future engines
        # can switch behaviour per-instance without touching this class.
        self.propagation = propagation
        self.attributes['propagation'] = propagation