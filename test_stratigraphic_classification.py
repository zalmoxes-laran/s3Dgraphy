"""Classification regression — the JSON datamodel is the single source
of truth for stratigraphic family / is_series metadata.

Validates invariants:

1. Every abbreviation in ``STRATIGRAPHIC_CLASS_MAP`` has a matching
   entry under ``stratigraphic_nodes.StratigraphicNode.subtypes`` in
   ``s3Dgraphy_node_datamodel.json`` — and vice versa. No orphans on
   either side.
2. Every JSON subtype declares ``family`` in
   ``{"real", "virtual", None}``.
3. ``is_series`` is True iff the abbreviation starts with ``ser`` —
   so the JSON cannot drift from the naming convention.
4. The ``classification.py`` accessors (``get_family``,
   ``is_real``, ``is_virtual``, ``is_series``) agree with the raw JSON.
5. :class:`NegativeStratigraphicUnit` exists, has ``node_type == 'USN'``,
   and is classified as ``family == 'real'`` / non-series.
6. The pre-computed sets
   (``REAL_US_TYPES``/``VIRTUAL_US_TYPES``/``SERIES_US_TYPES``/``ALL_US_TYPES``)
   are consistent with the per-node accessors.

Run with:  python3 test_stratigraphic_classification.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from s3dgraphy import (  # noqa: E402
    ALL_US_TYPES, REAL_US_TYPES, VIRTUAL_US_TYPES, SERIES_US_TYPES,
    get_family, is_real, is_virtual, is_series,
    get_subtype_info, iter_subtypes,
)
from s3dgraphy.utils.utils import STRATIGRAPHIC_CLASS_MAP  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import (  # noqa: E402
    NegativeStratigraphicUnit,
)


DATAMODEL_PATH = (
    REPO_ROOT
    / "src/s3dgraphy/JSON_config/s3Dgraphy_node_datamodel.json"
)


def _load_raw_subtypes() -> dict:
    with DATAMODEL_PATH.open() as f:
        d = json.load(f)
    return dict(
        d["stratigraphic_nodes"]["StratigraphicNode"]["subtypes"])


def test_python_and_json_agree_on_abbreviations():
    """Every ``node_type`` in STRATIGRAPHIC_CLASS_MAP exists as a JSON
    subtype abbreviation, and every JSON abbreviation has a Python
    class in the map. No drift permitted.
    """
    json_subs = _load_raw_subtypes()
    python_keys = set(STRATIGRAPHIC_CLASS_MAP.keys())
    json_keys = set(json_subs.keys())

    missing_in_json = python_keys - json_keys
    missing_in_python = json_keys - python_keys

    assert not missing_in_json, (
        f"Python-only abbreviations (add to JSON datamodel): "
        f"{sorted(missing_in_json)}")
    assert not missing_in_python, (
        f"JSON-only abbreviations (add Python class + map entry): "
        f"{sorted(missing_in_python)}")
    print(f"  ✓ {len(python_keys)} abbreviations aligned between "
          f"Python and JSON")


def test_family_values_are_well_formed():
    """Every JSON subtype must declare ``family`` in
    ``{real, virtual, None}``.
    """
    allowed = {"real", "virtual", None}
    for abbr, info in _load_raw_subtypes().items():
        assert "family" in info, (
            f"Subtype {abbr!r} missing 'family' field in datamodel")
        assert info["family"] in allowed, (
            f"Subtype {abbr!r} has invalid family "
            f"{info['family']!r} (allowed: {allowed})")
    print("  ✓ Every subtype declares a valid family")


def test_is_series_matches_naming_convention():
    """``is_series`` flag must equal ``abbr.startswith('ser')``. The
    convention prevents the JSON from silently contradicting the
    naming.
    """
    for abbr, info in _load_raw_subtypes().items():
        expected = abbr.startswith("ser")
        actual = bool(info.get("is_series", False))
        assert actual == expected, (
            f"Subtype {abbr!r}: is_series={actual!r}, expected="
            f"{expected!r} (convention: abbrev prefix 'ser' iff series)")
    print("  ✓ Every 'ser*' abbreviation has is_series=True, "
          "every other has is_series=False")


def test_classification_api_matches_json():
    """``classification.py`` accessors return exactly what the JSON
    says — ``get_family``, ``is_real``, ``is_virtual``, ``is_series``.
    """
    raw = _load_raw_subtypes()
    for abbr, info in raw.items():
        assert get_family(abbr) == info["family"], (
            f"get_family({abbr!r}) returned {get_family(abbr)!r}, "
            f"JSON says {info['family']!r}")
        assert is_real(abbr) == (info["family"] == "real"), (
            f"is_real({abbr!r}) disagrees with JSON")
        assert is_virtual(abbr) == (info["family"] == "virtual"), (
            f"is_virtual({abbr!r}) disagrees with JSON")
        assert is_series(abbr) == bool(info.get("is_series", False)), (
            f"is_series({abbr!r}) disagrees with JSON")
    print(f"  ✓ API agrees with JSON for {len(raw)} subtypes")


def test_usn_exists_and_is_real_non_series():
    """NegativeStratigraphicUnit must be registered with ``node_type
    == 'USN'``, family ``real``, and ``is_series`` False.
    """
    assert NegativeStratigraphicUnit.node_type == "USN", (
        f"NegativeStratigraphicUnit.node_type = "
        f"{NegativeStratigraphicUnit.node_type!r}, expected 'USN'")
    assert "USN" in STRATIGRAPHIC_CLASS_MAP, (
        "'USN' missing from STRATIGRAPHIC_CLASS_MAP")
    assert STRATIGRAPHIC_CLASS_MAP["USN"] is NegativeStratigraphicUnit, (
        "STRATIGRAPHIC_CLASS_MAP['USN'] is not NegativeStratigraphicUnit")
    info = get_subtype_info("USN")
    assert info is not None, "USN missing from JSON datamodel"
    assert info["family"] == "real", (
        f"USN family is {info['family']!r}, expected 'real'")
    assert info.get("is_series") is False, (
        f"USN is_series is {info.get('is_series')!r}, expected False")
    print("  ✓ USN registered everywhere, real + non-series")


def test_precomputed_sets_are_consistent():
    """The frozenset snapshots agree with the per-node accessors."""
    for abbr in ALL_US_TYPES:
        if abbr in REAL_US_TYPES:
            assert is_real(abbr)
        if abbr in VIRTUAL_US_TYPES:
            assert is_virtual(abbr)
        if abbr in SERIES_US_TYPES:
            assert is_series(abbr)
    # Disjointness
    assert not (REAL_US_TYPES & VIRTUAL_US_TYPES), (
        "real and virtual sets overlap")
    # Completeness for US-proper types (BR, SE may have family=None).
    classifiable = {a for a in ALL_US_TYPES
                    if get_family(a) is not None}
    assert classifiable == (REAL_US_TYPES | VIRTUAL_US_TYPES), (
        "Classifiable types don't match real ∪ virtual")
    print(f"  ✓ Sets consistent: {len(REAL_US_TYPES)} real, "
          f"{len(VIRTUAL_US_TYPES)} virtual, {len(SERIES_US_TYPES)} series")


def test_iter_subtypes_yields_all():
    """``iter_subtypes`` iterates over every subtype in JSON order."""
    iterated = list(iter_subtypes())
    assert len(iterated) == len(_load_raw_subtypes()), (
        f"iter_subtypes yielded {len(iterated)} items, "
        f"JSON has {len(_load_raw_subtypes())}")
    abbrs = [abbr for abbr, _ in iterated]
    assert len(abbrs) == len(set(abbrs)), "iter_subtypes had duplicates"
    print(f"  ✓ iter_subtypes yields {len(iterated)} unique entries")


def run():
    print("== Stratigraphic classification tests ==")
    test_python_and_json_agree_on_abbreviations()
    test_family_values_are_well_formed()
    test_is_series_matches_naming_convention()
    test_classification_api_matches_json()
    test_usn_exists_and_is_real_non_series()
    test_precomputed_sets_are_consistent()
    test_iter_subtypes_yields_all()
    print("== OK ==")


if __name__ == "__main__":
    run()
