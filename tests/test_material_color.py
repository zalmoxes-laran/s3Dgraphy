"""The material colour: one key, and everything that declares one gets one.

History in two lines, because it explains what these tests are guarding.
`em_visual_rules.json` used to say the same thing two ways — `material.color`
on the thirteen stratigraphic types, `material.rgba_color` on the rest — and
the lookup read only the first, so twenty-one types that declare a colour came
back as None. Nothing crashed; the colour was simply absent, which is the kind
of failure that survives for months. **S1** made the read defensive over both
spellings; **S8** unified the file on `rgba_color` and left `color` as
tolerance for older files.

The tests walk `em_visual_rules.json` itself rather than a hardcoded list, so a
type added tomorrow is covered without touching this file.
"""

import json
import pathlib

import pytest

from s3dgraphy.utils.utils import (_MATERIAL_COLOR_KEYS, _material_rgba,
                                   get_material_color)

RULES = (pathlib.Path(__file__).parent.parent / "src" / "s3dgraphy"
         / "JSON_config" / "em_visual_rules.json")


def _styles():
    return json.loads(RULES.read_text())["node_styles"]


def _material(entry):
    return ((entry.get("style") or {}).get("material")) or {}


# ── the property that matters ────────────────────────────────────────────────

def test_every_type_that_declares_a_colour_gets_one():
    """The whole point. Stated over the datamodel, not over a list of names, so
    it keeps holding as the datamodel grows."""
    missing = [name for name, entry in _styles().items()
               if _material(entry) and get_material_color(name) is None]
    assert missing == []


def test_the_authoritative_key_serves_every_entry_that_uses_it():
    """Since S8 the datamodel speaks `rgba_color` only, so this is the whole
    population. (Its ancestor asserted that BOTH spellings had users — a true
    statement about the two-key world that S8 made obsolete; what survives is
    the part that still means something.)"""
    styles = _styles()
    users = [n for n, e in styles.items() if "rgba_color" in _material(e)]
    assert users, "no entry uses rgba_color — this test has gone stale"
    for name in users:
        assert get_material_color(name) is not None, name


def test_the_values_are_the_declared_ones():
    """Reading both keys must not mean inventing a colour."""
    styles = _styles()
    for name, entry in styles.items():
        material = _material(entry)
        if not material:
            continue
        declared = next(material[k] for k in _MATERIAL_COLOR_KEYS
                        if k in material)
        r, g, b, a = get_material_color(name)
        assert (r, g, b) == (declared["r"], declared["g"], declared["b"])
        assert a == declared.get("a", 1.0)


# ── what must still return None ──────────────────────────────────────────────

def test_a_node_with_no_material_still_has_no_colour():
    """The four group containers are drawn as boxes, not materials. Handing
    them a colour would be a regression dressed as a fix."""
    without = [name for name, entry in _styles().items()
               if not _material(entry)]
    assert without, "the datamodel no longer has a material-less entry"
    for name in without:
        assert get_material_color(name) is None


def test_an_unknown_type_has_no_colour():
    assert get_material_color("definitely-not-a-node-type") is None


# ── the helper, on malformed input ───────────────────────────────────────────

@pytest.mark.parametrize("style", [
    {},
    {"material": None},
    {"material": "red"},                       # not a mapping
    {"material": {"color": "red"}},            # not a mapping either
    {"material": {"color": {"r": 1.0}}},       # incomplete triple
    {"material": {"tint": {"r": 1, "g": 1, "b": 1}}},   # unknown spelling
])
def test_malformed_material_returns_none_rather_than_raising(style):
    """A datamodel typo should leave a node uncoloured, not take down the
    caller — this runs inside Blender's material setup."""
    assert _material_rgba(style) is None


def test_alpha_defaults_to_opaque():
    assert _material_rgba(
        {"material": {"color": {"r": 0.1, "g": 0.2, "b": 0.3}}}) \
        == (0.1, 0.2, 0.3, 1.0)


# ── precedence ───────────────────────────────────────────────────────────────

def test_material_key_precedence_is_pinned():
    """`rgba_color` is authoritative since S8; `color` is read only as
    tolerance for a file written before the rename. No entry carries both, so
    precedence changes nothing today — it is pinned so that the day one does,
    the winner is a decision and not whichever key the loop saw first."""
    assert _MATERIAL_COLOR_KEYS == ("rgba_color", "color")
    both = {"material": {
        "color": {"r": 1.0, "g": 0.0, "b": 0.0},
        "rgba_color": {"r": 0.0, "g": 1.0, "b": 0.0},
    }}
    assert _material_rgba(both) == (0.0, 1.0, 0.0, 1.0)


def test_the_datamodel_speaks_one_key_now():
    """S8: the file is unified on `rgba_color`. The legacy `color` must not
    reappear — a new entry copy-pasted from an old one would resurrect the very
    split that made 21 types colourless."""
    legacy = [name for name, entry in _styles().items()
              if "color" in _material(entry)]
    assert legacy == [], f"still on the legacy key: {legacy}"


def test_the_legacy_key_is_still_tolerated():
    """An em_visual_rules written before S8 must keep working."""
    assert _material_rgba({"material": {"color": {"r": 0.5, "g": 0.5, "b": 0.5}}}) \
        == (0.5, 0.5, 0.5, 1.0)


def test_no_datamodel_entry_carries_both_keys():
    """If this fails the datamodel has grown an ambiguity, and the TODO in
    utils.py about normalising on one key stopped being optional."""
    ambiguous = [name for name, entry in _styles().items()
                 if set(_MATERIAL_COLOR_KEYS) <= set(_material(entry))]
    assert ambiguous == []
