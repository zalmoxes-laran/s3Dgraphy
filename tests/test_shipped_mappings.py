"""The mappings we ship must validate against the datamodel we ship with them.

A mapping file in this package is not documentation: a partner opens the one
nearest their data and edits it. On 2026-09-20 three of the eight did not
validate — twelve errors between them, all invisible until someone ran one.

The first test is the cheap structural one that would have caught every one of
them the day the datamodel moved. The rest measure what the generic mapping
actually carries into a graph, because validation only proves a mapping is
well-formed, not that the data arrives.
"""

import csv
import glob
import json
import os
from pathlib import Path

import pytest

from s3dgraphy import api

MAPPINGS_DIR = Path(__file__).parent.parent / "src" / "s3dgraphy" / "mappings"
GENERIC = MAPPINGS_DIR / "generic" / "excel_to_graphml_mapping.json"
FIXTURE = Path(__file__).parent / "fixtures" / "generic_stratigraphy.csv"


def _shipped():
    return sorted(glob.glob(str(MAPPINGS_DIR / "**" / "*.json"), recursive=True))


@pytest.mark.parametrize("path", _shipped(), ids=lambda p: os.path.basename(p))
def test_every_shipped_mapping_validates(path):
    mapping = json.loads(Path(path).read_text(encoding="utf-8"))
    report = api.mapping_validate(mapping)
    errors = report.get("errors") or []
    assert not errors, f"{os.path.basename(path)}:\n  " + "\n  ".join(errors)


def test_the_package_ships_at_least_one_mapping():
    # guards the parametrize above: an empty glob would make it vacuously green
    assert len(_shipped()) >= 5


def _import_fixture():
    mapping = json.loads(GENERIC.read_text(encoding="utf-8"))
    mapping["table_settings"]["format_type"] = "csv"
    mapping["table_settings"].pop("sheet_name", None)
    mapping["table_settings"]["start_row"] = 1
    return api.mapping_apply(mapping, str(FIXTURE), mode="volatile")


def test_the_generic_mapping_imports_without_complaint():
    res = _import_fixture()
    assert res["ok"], res.get("errors")
    assert res["rows"] == 3


def test_the_relation_columns_become_edges_and_not_properties():
    """`is_relation` is what stops an US name from being filed as a text value.

    Without it the column is read as a PropertyNode too, so US2 arrives both as
    the far end of an edge and as the string "US2" hanging off US1 — the same
    fact recorded twice, once wrongly.
    """
    g = _import_fixture()["graph"]
    names = {n.node_id: getattr(n, "name", n.node_id) for n in g.nodes}
    strat = {"overlies", "is_overlain_by", "cuts", "is_cut_by"}
    edges = {(names[e.edge_source], e.edge_type, names[e.edge_target])
             for e in g.edges if e.edge_type in strat}
    assert ("US1", "overlies", "US2") in edges
    assert ("US3", "cuts", "US2") in edges
    # and no property node is carrying an US name as its value
    values = {getattr(n, "value", None) for n in g.nodes
              if type(n).__name__ == "PropertyNode"}
    assert not (values & {"US1", "US2", "US3"})


def test_the_description_actually_arrives():
    """It did not, and nothing said so.

    `is_description` needs `target_id_column` to know which node the text
    belongs to. Without it the mapping validated, the import reported ok, three
    rows were read — and every description was dropped in silence. The column
    is the one thing an excavator is certain to have filled in.
    """
    g = _import_fixture()["graph"]
    got = {n.name: getattr(n, "description", "") for n in g.nodes
           if "Stratigraphic" in type(n).__name__}
    assert got == {"US1": "pavimento", "US2": "riempimento", "US3": "taglio"}


def test_the_unit_type_column_picks_the_subclass():
    # TYPE=USN must produce a negative unit, not a generic one — the failure
    # that once turned 2101 special finds into stratigraphic units.
    g = _import_fixture()["graph"]
    classes = {n.name: type(n).__name__ for n in g.nodes
               if "Stratigraphic" in type(n).__name__}
    assert classes["US3"] == "NegativeStratigraphicUnit"
    assert classes["US1"] == "StratigraphicUnit"


def test_the_epoch_carries_its_dates():
    g = _import_fixture()["graph"]
    epochs = [n for n in g.nodes if type(n).__name__ == "EpochNode"]
    assert len(epochs) == 1 and epochs[0].name == "Romano"
    assert (epochs[0].start_time, epochs[0].end_time) == (-100.0, 100.0)
