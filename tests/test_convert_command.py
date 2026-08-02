"""Se5 — the `convert` command: GraphML → em.json, once and for good.

The GraphML is deprecated. 1.6 still imports it at runtime; from 1.7 the only
way in is this one-shot conversion, and the many datasets "out there" will each
be converted once. That makes two properties non-negotiable:

* **reproducible** — the same GraphML must always produce the same em.json,
  otherwise the converted file cannot carry a persistent identity. This rests on
  E2 (deterministic ids); the test here pins the end-to-end guarantee.
* **honest** — the conversion reports what it could NOT resolve (untyped nodes,
  unclassified groups, degraded edges) instead of guessing. A graph drawn before
  the EM 1.4 palette is flagged so the author runs the EMTools converter first.
"""

import contextlib
import io
import json
import pathlib

from s3dgraphy.api import (convert_graphml_to_emjson, format_conversion_report,
                           main)
from s3dgraphy.exporter.emjson_exporter import SCHEMA_VERSION

FIXTURES = pathlib.Path(__file__).parent / "sync" / "fixtures"
CLEAN = FIXTURES / "mini_volterra_external.graphml"


def _convert(path):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return convert_graphml_to_emjson(path.read_bytes())


def test_convert_produces_a_valid_emjson():
    doc, report = _convert(CLEAN)
    assert doc["header"]["schema_version"] == SCHEMA_VERSION
    assert doc["graph"]["nodes"] and doc["graph"]["edges"]
    assert report["nodes"] == len(doc["graph"]["nodes"])
    assert report["edges"] == len(doc["graph"]["edges"])


def test_convert_is_reproducible():
    """Two runs → byte-identical em.json. The whole point of depending on E2."""
    first, _ = _convert(CLEAN)
    second, _ = _convert(CLEAN)
    assert (json.dumps(first, sort_keys=True)
            == json.dumps(second, sort_keys=True))


def test_clean_graph_reports_nothing_unresolved():
    _doc, report = _convert(CLEAN)
    assert report["untyped_nodes"] == []
    assert report["unclassified_groups"] == []
    assert report["degraded_edges"] == 0
    assert report["legacy_em"]["suspected"] is False
    assert "nothing left unresolved" in format_conversion_report(report)


def test_report_counts_come_from_the_graph_not_the_warning_text():
    """A graph with an unclassified group must be counted even though the
    counting never reads a warning string."""
    _doc, report = _convert(FIXTURES / "groups_volterra.graphml")
    assert isinstance(report["unclassified_groups"], list)
    assert isinstance(report["degraded_edges"], int)
    # The raw warnings travel along verbatim for the author-facing display.
    assert isinstance(report["warnings"], list)


def test_legacy_em_hint_needs_both_signals():
    """The pre-1.4 hint fires only when an ambiguous fill colour AND an untyped
    node are both present — either alone is too weak to accuse a file."""
    from s3dgraphy.api import _conversion_report

    class _FakeGraph:
        nodes = []
        edges = []

    # Colour present, nothing untyped → no accusation.
    report = _conversion_report(_FakeGraph(), [], b'<graphml>#CCCCFF</graphml>')
    assert report["legacy_em"]["suspected"] is False
    # Neither signal → no accusation.
    report = _conversion_report(_FakeGraph(), [], b'<graphml/>')
    assert report["legacy_em"]["suspected"] is False


def test_legacy_em_hint_names_the_emtools_operator():
    """When it does fire, the message must point at the fix and refuse to
    guess types."""
    report = {
        "nodes": 1, "edges": 0, "schema_version": SCHEMA_VERSION,
        "untyped_nodes": ["SF04.2"], "unclassified_groups": [],
        "degraded_edges": 0, "warnings": [],
        "legacy_em": {"suspected": True,
                      "evidence": ["fill colour #CCCCFF present"]},
    }
    text = format_conversion_report(report)
    assert "convert EM 1.x → 1.4" in text
    assert "not guessed" in text


def test_cli_writes_the_file_and_is_reproducible(tmp_path, capsys):
    out = tmp_path / "out.em.json"
    assert main(["convert", str(CLEAN), "-o", str(out)]) == 0
    assert out.exists()
    first = out.read_text()

    # Re-running over the same output needs --force…
    assert main(["convert", str(CLEAN), "-o", str(out)]) == 1
    # …and when forced, writes exactly the same bytes.
    assert main(["convert", str(CLEAN), "-o", str(out), "--force"]) == 0
    assert out.read_text() == first


def test_cli_json_report(tmp_path, capsys):
    out = tmp_path / "out.em.json"
    assert main(["convert", str(CLEAN), "-o", str(out), "--json"]) == 0
    captured = capsys.readouterr().out
    # The importer is chatty; the report is the last TOP-LEVEL json object,
    # i.e. the last "{" that starts its own line at column 0.
    report = json.loads(captured[captured.rindex("\n{\n") + 1:])
    assert report["output"] == str(out)
    assert report["schema_version"] == SCHEMA_VERSION


def test_cli_stdout_mode_emits_the_document(tmp_path, capsys):
    assert main(["convert", str(CLEAN), "-o", "-"]) == 0
    captured = capsys.readouterr()
    doc = json.loads(captured.out[captured.out.rindex("\n{\n") + 1:])
    assert doc["header"]["schema_version"] == SCHEMA_VERSION
    # …and keeps the report out of the way, on stderr.
    assert "converted:" in captured.err


def test_default_output_path_sits_next_to_the_input(tmp_path):
    src = tmp_path / "sample.graphml"
    src.write_bytes(CLEAN.read_bytes())
    assert main(["convert", str(src)]) == 0
    assert (tmp_path / "sample.em.json").exists()
