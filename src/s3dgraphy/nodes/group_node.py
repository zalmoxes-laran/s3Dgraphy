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


class FunctionalUnitNodeGroup(GroupNode):
    """Typed aggregation of the stratigraphic units that make up one
    recognisable functional / architectural component — the *column* made
    of its US, the *wall* made of its US (DP-72).

    Scope note
    ----------
    A Functional Unit answers *what a set of stratigraphic units is, as a
    building component*. It is built **bottom-up** from the stratigraphic
    reading: the units it aggregates stay intact and fully stratigraphic
    underneath, each keeping its own epochs, paradata and provenance. The
    Functional Unit adds a handle for the component as a whole — to name
    it, filter by it, and project it to architectural-component
    vocabularies.

    Membership is a **tag**, not a nesting: a member carries an
    ``is_in_functional_unit`` edge towards the Functional Unit. The relation
    is the same mereological P46i that ``is_part_of`` projects to — what
    differs is the ROLE in the EM language. ``is_part_of`` is the nesting
    axis (one primary drawing parent, a box around its members, propagates
    the epoch lane); a Functional Unit legitimately **spans epochs** — a
    wall built across four of them still carries the roof as one body — and
    a swimlane box cannot. So membership stays m:n and additive, does not
    claim the member's primary parent, and every view opts into drawing it:
    the functional reading lives beside pure stratigraphy without either
    constraining the other.

    What it is NOT
    --------------
    - Not an **ActivityNodeGroup** (DP-43), which clusters *actions /
      processes* ("construction of the portico"). A Functional Unit is
      what the units *are*, not what was done to them or when.
    - Not a generic **container** (DP-36). A US / USD / VSF acting as a
      container is still a stratigraphic unit, with its own formation
      event and its own place in the sequence; a Functional Unit is a
      typed aggregation with no formation event of its own.
    - Not a **LocationNodeGroup** of kind ``functional``, which is a named
      *place* ("Room 12") and answers *where*. A Functional Unit is a
      *component* and answers *what*.
    - Not a geometric construction grammar. The component's geometry type
      travels **by reference** to an external taxonomy
      (``geometry_type_ref`` — bSDD / Getty AAT / an HBIM shape-grammar
      vocabulary); nothing of that vocabulary is internalized or
      validated here.

    Attach rules
    ------------
    - members: ``StratigraphicNode ─is_in_functional_unit→ FunctionalUnit``
    - nesting: a Functional Unit may itself be
      ``is_in_functional_unit`` another one (the capital inside the column).
    - ``FunctionalUnit ─is_part_of→ US`` stays legal and means something
      else: the whole component **physically embedded** in a stratigraphic
      unit (a column engaged in a later wall). That one IS containment.
    - the orthogonal axes stay orthogonal: a member keeps its own
      ``has_first_epoch`` (time), ``is_in_activity`` (intention) and
      ``is_in_location`` (place); the Functional Unit does not override
      them and has no epoch of its own — its temporal extent is DERIVED
      from its members, and may cover several epochs.

    EM manual: *Stratigraphic Nodes* → "SU / USD / VSF as Container" and
    *Connectors* → ``is_part_of`` ("Containment is a relationship (edge),
    not a change in node type").
    """

    node_type = "FunctionalUnitNodeGroup"

    def __init__(self, node_id, name, description="", y_pos=0.0,
                 geometry_type_ref=None):
        super().__init__(node_id, name, description=description, y_pos=y_pos)
        # Geometry type BY REFERENCE only (DP-72): an opaque pointer into an
        # external taxonomy (bSDD / Getty AAT / HBIM shape grammar). Free-form
        # on purpose — no vocabulary is internalized or validated here, and the
        # binding to a target ontology (CRMvr V5) is separate work.
        if geometry_type_ref is not None:
            self.attributes['geometry_type_ref'] = geometry_type_ref