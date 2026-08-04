# 3dgraphy/nodes/stratigraphic_node.py

from .base_node import Node

class StratigraphicNode(Node):
    """
    Base class for all stratigraphic units within the graph structure.
    Inherits from Node and provides additional functionality specific to stratigraphy.
    """
    node_type = "StratigraphicNode"

    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = None
        self.label = None
        self.detailed_description = None  # To avoid conflict with `description`


class StratigraphicUnit(StratigraphicNode):
    node_type = "US"

    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white rectangle"
        self.label = "US (or SU)"
        self.detailed_description = "Stratigraphic Unit (SU) or negative stratigraphic unit."

class VirtualStratigraphicUnit(StratigraphicNode):
    """Abstract parent of the virtual stratigraphic units (USV/s, USV/n).

    Introduced 2026-07-12 (datamodel curation, EMStudio ADR-001): the
    connections datamodel references ``VirtualStratigraphicUnit`` in
    ``allowed_connections`` but no such class existed — the concrete USV
    classes descended from ``StratigraphicNode`` directly, so class-based
    rule matching had to special-case the name. No ``node_type``: the class
    is abstract, only its subclasses are instantiated.
    """


class StructuralVirtualStratigraphicUnit(VirtualStratigraphicUnit):
    node_type = "USVs"

    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black parallelogram"
        self.label = "USV/s"
        self.detailed_description = "Structural Virtual Stratigraphic Unit (USV/s)."


class SeriesOfStratigraphicUnit(StratigraphicNode):
    node_type = "serSU"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white ellipse"
        self.label = "US series"
        self.detailed_description = "Series of Stratigraphic Units (SU)."


class SeriesOfNonStructuralVirtualStratigraphicUnit(StratigraphicNode):
    node_type = "serUSVn"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black ellipse green border"
        self.label = "USVn series"
        self.detailed_description = "Series of non-structural Virtual Stratigraphic Units."


class SeriesOfStructuralVirtualStratigraphicUnit(StratigraphicNode):
    node_type = "serUSVs"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black ellipse blue border"
        self.label = "USVs series"
        self.detailed_description = "Series of Structural Virtual Stratigraphic Units."


class SeriesOfDocumentaryStratigraphicUnit(StratigraphicNode):
    node_type = "serUSD"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white ellipse with orange border"
        self.label = "USD series"
        self.detailed_description = "Series of Documentary Stratigraphic Units (USD)."


class NonStructuralVirtualStratigraphicUnit(VirtualStratigraphicUnit):
    node_type = "USVn"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black hexagon"
        self.label = "USV/n"
        self.detailed_description = "Non-structural Virtual Stratigraphic Unit (USV/n)."


class SpecialFindUnit(StratigraphicNode):
    node_type = "SF"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white octagon"
        self.label = "Special Find"
        self.detailed_description = "Not in situ element that needs repositioning."


class VirtualSpecialFindUnit(StratigraphicNode):
    node_type= "VSF"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black octagon"
        self.label = "Virtual Special Find"
        self.detailed_description = "Hypothetical reconstruction of a fragmented Special Find."


class ReusedSpecialFind(StratigraphicNode):
    """Reused Special Find (RSF) — re-used architectural / decorative
    element (spolia) in archaeological reconstructions.

    Typological cousin of :class:`SpecialFindUnit` (SF) and
    :class:`VirtualSpecialFindUnit` (VSF): all three render as octagons.
    RSF is distinguished by its **red** border (``#9B3333``) and a white
    fill, marking the element as physically present *and* re-deployed
    out of its original construction context.

    Originating Development Project: DP-26 (spolia project, last DP
    before the EM 1.5 cut). Visual stencil shipped in the palette
    template at ``templates/em_palette_template.graphml``.
    """
    node_type = "RSF"

    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white octagon red border"
        self.label = "Reused Special Find"
        self.detailed_description = (
            "Re-used architectural or decorative element (spolia) in "
            "archaeological reconstructions. A physical find observed "
            "in situ but originally produced for a different context.")


class DocumentaryStratigraphicUnit(StratigraphicNode):
    node_type = "USD"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white round rectangle"
        self.label = "USD"
        self.detailed_description = "Documentary Stratigraphic Unit."


class TransformationStratigraphicUnit(StratigraphicNode):
    node_type = "TSU"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "dotted white rectangle"
        self.label = "TSU"
        self.detailed_description = "Transformation Unit."


class WorkingUnit(StratigraphicNode):
    node_type = "UL"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "white rectangle with orange border"
        self.label = "UL"
        self.detailed_description = "Working Unit. Traces of stone working, toolmarks, reworkings on architectural surfaces."


class NegativeStratigraphicUnit(StratigraphicNode):
    """Negative Stratigraphic Unit, displayed ``US-`` (US negativa).

    Describes a *lacuna* produced by a REMOVAL: a pit cut, an erosion
    surface, a demolition void. What defines it is the destructive act —
    matter that was there and is not any more — which is what separates
    it from :class:`NeutralStratigraphicUnit`, the void that was never
    filled because it was never meant to be.

    Equally observable on the ground as a positive unit, hence the
    ``real`` family alongside :class:`StratigraphicUnit` and
    :class:`DocumentaryStratigraphicUnit`.

    .. note:: ``node_type`` is ``USNeg`` since POL5 (2026-08-04). It used
       to be ``USN``, which E.D. reassigned to the NEUTRAL unit — the
       abbreviation reads "Unità Stratigrafica Neutra". The move was safe
       because nothing produced a ``USN`` node: ``convert_shape2type`` has
       no yEd shape mapping to it, so no imported graph carries one. An
       xlsx that typed ``USN`` meaning *negative* is the one case that
       changes meaning, and it is called out in the POL5 end-of.
    """
    node_type = "USNeg"

    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "grey rectangle, solid border"
        self.label = "US-"
        self.detailed_description = (
            "Negative Stratigraphic Unit (US-) — a lacuna left by a "
            "removal: a pit cut, an erosion surface, a demolition void.")


class NeutralStratigraphicUnit(StratigraphicNode):
    """Neutral Stratigraphic Unit (USN, Unità Stratigraphica Neutra).

    A void that is part of the design, not the product of a destruction:
    the *risparmi* of masonry — a window or door opening, the empty
    volume of a room. The wall was built around it, so nothing was ever
    removed and nothing is missing.

    This is the distinction E.D. asked for in POL5, and it is a real one
    on site: a demolition void (:class:`NegativeStratigraphicUnit`, shown
    ``US-``) is evidence of an ACT, while a *risparmio* is evidence of an
    INTENTION. Reading one as the other inverts the sequence — the void
    would be dated to a removal that never happened.

    ``real`` family: a risparmio is directly observable, and it is drawn
    with the outline at the four corners only (see ``em_visual_rules``),
    because the excavation observes its extent and not a surface.

    .. warning:: STRATIGRAPHIC RELATIONS (E.D.): a neutral unit takes
       ``is_after`` / ``is_before`` and **nothing else**. It is a void: it
       cannot cut, fill, abut or be bonded to anything. The rule is data,
       not code — ``s3Dgraphy_connections_datamodel.json`` →
       ``node_type_restrictions.USN``.

    .. todo:: CIDOC: mapping USN-neutra da definire — E.D. coordina con
       Achille Felicetti / CRMarchaeo. CRMarchaeo has A2 (Stratigraphic
       Volume Unit) and A3 (Stratigraphic Interface) but no term for a
       void left deliberately, so the datamodel entry carries a
       PROVISIONAL E24 placeholder rather than an invented A-class.
    """
    node_type = "USN"

    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "grey outline at the four corners only"
        self.label = "USN"
        self.detailed_description = (
            "Neutral Stratigraphic Unit (USN) — a void by design, not by "
            "removal: a window or door opening, the volume of a room. "
            "Only is_after/is_before relations.")


class ContinuityNode(StratigraphicNode):
    node_type = "BR"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "black rhombus"
        self.label = "continuity node"
        self.detailed_description = "End of life of a US/USV."


class StratigraphicEventNode(StratigraphicNode):
    node_type = "SE"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "to be defined"
        self.label = "stratigraphic event node"
        self.detailed_description = "A stratigraphic event is the process or event that leads to the formation or alteration of a stratigraphic unit. It is distinct from the unit itself, which represents the result or outcome of the event. The event can be thought of as a precursor and can be paired with its resulting unit to provide a more detailed temporal range. This allows for the documentation of both the initial moment of action (e.g., the start of construction, a collapse, or an incision) and the final state (the resulting unit that persists over time)."


class UnknownNode(StratigraphicNode):
    node_type = "unknown"
    def __init__(self, node_id, name, description=""):
        super().__init__(node_id, name, description)
        self.symbol = "question mark"
        self.label = "Unknown node"
        self.detailed_description = "Fallback node for unrecognized types."
