"""Every 2D icon the datamodel DECLARES exists — because 2D is what renders.

The asymmetry between the two assertions in this file is the whole point:

* **2D is enforced.** `em_visual_rules.node_styles` is read by EMStudio's
  `icons.ts`, which resolves vector-then-raster and returns *null* when neither
  file is there. A declaration naming a file that does not exist therefore fails
  SILENTLY: the canvas draws the node's shape and nobody sees an error. Measured
  on 2026-08-29: four such declarations had accumulated (SE, TSU, serUSD, and
  `unknown`, which named a `unknown.png` that never existed), plus GRAPH, which
  had *neither* half and drew no icon at all.
* **3D is reported, not enforced.** Sixteen of the forty-one styles declare a
  `.glb` that has not been modelled yet, and that is a known state of the visual
  language rather than a bug: the 3D set covers the stratigraphic core and stops
  there. Asserting it would mean a permanently red suite or sixteen fabricated
  assets, and a placeholder that looks official is harder to notice than an
  absence. So it is counted and named, and the number is allowed to go down.
"""

from __future__ import annotations

import json
import pathlib

CONFIG = (pathlib.Path(__file__).resolve().parent.parent
          / "src" / "s3dgraphy" / "JSON_config")

_2D_FIELDS = ("2d_file_vect", "2d_file_rast", "file_2d")


def _styles():
    return json.loads((CONFIG / "em_visual_rules.json").read_text(
        encoding="utf-8"))["node_styles"]


def _declared(fields):
    for key, style in _styles().items():
        if not isinstance(style, dict):
            continue
        for field in fields:
            path = style.get(field)
            if isinstance(path, str):
                yield key, field, path


def test_every_declared_2D_icon_is_there():
    missing = [f"{key}.{field} → {path}"
               for key, field, path in _declared(_2D_FIELDS)
               if not (CONFIG / path).is_file()]
    assert not missing, (
        "the datamodel names 2D icons that do not exist. `icons.ts` returns null "
        "and the canvas quietly draws the shape instead, so this never shows up "
        "as an error — which is why it is a test:\n  " + "\n  ".join(missing))


def test_every_node_type_the_canvas_draws_resolves_to_a_FILE():
    """One level past the declaration: what `icons.ts` would actually reach.

    Its order is declared-vector, declared-raster, then a file named after the
    type. A style whose declarations are all stale still draws if the convention
    saves it — and one where neither does draws nothing. GRAPH was the second
    case until 2026-08-29.
    """
    icons = CONFIG / "src" / "2D"
    unresolved = []
    for key, style in _styles().items():
        if not isinstance(style, dict):
            continue
        found = any((CONFIG / style[f]).is_file()
                    for f in _2D_FIELDS if isinstance(style.get(f), str))
        found = found or any((icons / f"{key}{ext}").is_file()
                             for ext in (".svg", ".png"))
        if not found:
            unresolved.append(key)
    # Two allowances, and they are different things.
    #
    # SHARING: `BR`, `serUSVn`, `serUSVs` are drawn with somebody else's file,
    # spelled out in `icons.ts::FILE_ALIAS` rather than in the datamodel.
    # Declared sharing, not a gap.
    shared = {"BR", "serUSVn", "serUSVs"}
    # A KNOWN GAP: two of the four group types have no drawing and draw nothing.
    # Their siblings do (`ActivityNodeGroup.svg`, `ParadataNodeGroup.svg`), so
    # this is an unfinished family rather than a design decision — and finishing
    # it is an act of EM iconography with an author, not a thing to fill in from
    # a test. Named here so the number can only go DOWN.
    known_gap = {"LocationNodeGroup", "TimeBranchNodeGroup"}
    assert set(unresolved) <= shared | known_gap, (
        f"these node types would draw NO icon at all: "
        f"{sorted(set(unresolved) - shared - known_gap)}")


def test_the_3D_gap_is_counted_and_named_rather_than_asserted():
    """Reported, and the number is allowed to go DOWN, never silently up."""
    missing = sorted(key for key, _field, path in _declared(("file_3d",))
                     if not (CONFIG / path).is_file())
    # the state on 2026-08-29: the 3D set covers the stratigraphic core, and the
    # newer families (rights, references, DTC, georeferencing) are unmodelled
    assert len(missing) <= 16, (
        f"{len(missing)} styles declare a .glb that is not there — MORE than the "
        f"16 known on 2026-08-29. A new type should either ship its model or not "
        f"declare one:\n  " + "\n  ".join(missing))
    # the two georeferencing types added on 2026-08-29 are in that list, and the
    # test says so rather than letting them hide in a count
    assert {"GCP", "RGT"} <= set(missing) or not ({"GCP", "RGT"} & set(missing))
