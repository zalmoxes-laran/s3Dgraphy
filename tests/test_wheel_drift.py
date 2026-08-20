"""A bundled wheel is checked by CONTENT, because a version string can lie.

The defect this defends against was measured on 17 Aug 2026: the wheel EMtools
bundles held code from days earlier **while declaring the same version**
(`1.6.0.dev14` on both sides), so the version-based check
(:mod:`s3dgraphy.tools.consumer_drift`) passed while EMtools ran the old library —
and the only symptom was an `ImportError` inside a button press.

What is defended here:

* the **fingerprint** is over path AND content, so a file that moved is a
  different code base and a file that changed is caught;
* a wheel with the SAME VERSION and older content is reported **stale**, with
  what changed spelled out (added / removed / different) rather than left as a
  hash mismatch;
* an identical wheel is **aligned**;
* the `.dist-info` is metadata and never part of the comparison — otherwise every
  rebuild would look like a change;
* `--check` fails for a bundle **we own** (the fix is one command) and a bundle
  that is not on this machine is **absent**, never a failure.
"""

from __future__ import annotations

import pathlib
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from s3dgraphy.tools import wheel_drift as wd                    # noqa: E402


def make_wheel(path: pathlib.Path, files: dict[str, bytes], *,
               version: str = "1.6.0.dev14") -> pathlib.Path:
    """A wheel that is only as much of one as this tool reads: the package tree
    plus a `.dist-info` (which must be ignored)."""
    wheel = path / f"s3dgraphy-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        for name, body in files.items():
            zf.writestr(name, body)
        zf.writestr(f"s3dgraphy-{version}.dist-info/METADATA",
                    f"Name: s3dgraphy\nVersion: {version}\n")
        zf.writestr(f"s3dgraphy-{version}.dist-info/RECORD", "")
    return wheel


# ── the fingerprint ─────────────────────────────────────────────────────────

def test_the_fingerprint_is_over_path_AND_content():
    a = {"s3dgraphy/api.py": b"x = 1"}
    same = {"s3dgraphy/api.py": b"x = 1"}
    moved = {"s3dgraphy/core/api.py": b"x = 1"}
    edited = {"s3dgraphy/api.py": b"x = 2"}

    assert wd.fingerprint(a) == wd.fingerprint(same)
    assert wd.fingerprint(a) != wd.fingerprint(moved), \
        "a file that MOVED is a different code base; a content-only hash would " \
        "have called it the same"
    assert wd.fingerprint(a) != wd.fingerprint(edited)
    assert wd.fingerprint({}) != wd.fingerprint(a)


def test_the_fingerprint_does_not_depend_on_insertion_order():
    one = {"s3dgraphy/a.py": b"1", "s3dgraphy/b.py": b"2"}
    other = {"s3dgraphy/b.py": b"2", "s3dgraphy/a.py": b"1"}
    assert wd.fingerprint(one) == wd.fingerprint(other)


# ── the comparison ──────────────────────────────────────────────────────────

def test_a_wheel_built_from_this_source_is_aligned(tmp_path):
    """The reference case: the same files, so the same fingerprint."""
    code = wd.source_files((".py",))
    data = wd.source_files((".json",))
    wheel = make_wheel(tmp_path, {**code, **data})

    verdict = wd.compare(wheel)
    assert verdict["aligned"] is True
    assert verdict["json_aligned"] is True
    assert verdict["missing"] == [] and verdict["extra"] == []
    assert verdict["changed"] == []
    assert verdict["files_wheel"] == verdict["files_source"] > 0


def test_the_dist_info_is_metadata_and_never_part_of_the_comparison(tmp_path):
    """Otherwise every rebuild would read as a change: `RECORD` holds hashes and
    `METADATA` a timestamp-ish header."""
    code = wd.source_files((".py",))
    plain_dir, noisy_dir = tmp_path / "plain", tmp_path / "noisy"
    plain_dir.mkdir()
    noisy_dir.mkdir()
    plain = make_wheel(plain_dir, dict(code))
    noisy = make_wheel(noisy_dir,
                       {**code, "s3dgraphy-1.6.0.dev14.dist-info/extra": b"x"})
    assert wd.compare(plain)["code_wheel"] == wd.compare(noisy)["code_wheel"]


def test_a_stale_wheel_with_the_SAME_VERSION_is_caught(tmp_path):
    """THE MEASURED CASE. Same version string, older code: the version check
    cannot see it, and this must."""
    code = dict(wd.source_files((".py",)))
    # a module added to the source since the wheel was built…
    added = sorted(code)[0]
    del code[added]
    # …one removed from the source since…
    code["s3dgraphy/nodes/link_node.py"] = b"# a module renamed away days ago\n"
    # …and one edited
    edited = sorted(code)[0]
    code[edited] = code[edited] + b"\n# not what the source says\n"

    wheel = make_wheel(tmp_path, code, version=wd.source_version() or "1.6.0.dev14")
    verdict = wd.compare(wheel)

    assert verdict["same_version"] is True, "the strings agree: that is the trap"
    assert verdict["aligned"] is False, "…and the content does not"
    assert added in verdict["missing"]
    assert "s3dgraphy/nodes/link_node.py" in verdict["extra"]
    assert edited in verdict["changed"]


def test_a_wheel_of_another_version_is_still_compared_by_content(tmp_path):
    """The version is REPORTED, never the verdict: a wheel that says 1.5 and
    holds this code is aligned, and one that says this version and holds other
    code is not."""
    code = wd.source_files((".py",))
    wheel = make_wheel(tmp_path, code, version="1.5.0")
    verdict = wd.compare(wheel)
    assert verdict["same_version"] is False
    assert verdict["aligned"] is True


# ── the report and its governance ───────────────────────────────────────────

def test_survey_of_one_wheel_says_STALE_or_aligned(tmp_path):
    code = dict(wd.source_files((".py",)))
    code.pop(sorted(code)[0])
    wheel = make_wheel(tmp_path, code)
    rows = wd.survey(wheel=str(wheel))["bundles"]
    assert [row["state"] for row in rows] == ["STALE"]

    good_dir = tmp_path / "ok"
    good_dir.mkdir()
    good = make_wheel(good_dir, wd.source_files((".py",)))
    rows = wd.survey(wheel=str(good))["bundles"]
    assert [row["state"] for row in rows] == ["aligned"]


def test_check_fails_for_a_stale_bundle_and_passes_for_an_aligned_one(tmp_path,
                                                                     capsys):
    code = dict(wd.source_files((".py",)))
    dropped = sorted(code)[0]
    code.pop(dropped)
    stale = make_wheel(tmp_path, code)

    assert wd.report(check=True, wheel=str(stale)) == 1
    out = capsys.readouterr().out
    assert "STALE" in out
    assert "THE VERSION STRING MATCHES AND THE CODE DOES NOT" in out, \
        "the report names the trap, or a reader learns nothing from it"
    assert dropped in out, "…and what is missing"

    fresh_dir = tmp_path / "fresh"
    fresh_dir.mkdir()
    fresh = make_wheel(fresh_dir, wd.source_files((".py",)))
    assert wd.report(check=True, wheel=str(fresh)) == 0


def test_a_bundle_that_is_not_on_this_machine_is_absent_not_a_failure(tmp_path,
                                                                     capsys):
    """A machine does not have to hold every repo — the same rule
    `consumer_drift` follows."""
    assert wd.report(root=str(tmp_path), check=True) == 0
    assert "not on this machine" in capsys.readouterr().out


def test_nothing_is_ever_written(tmp_path):
    """The tool reports. A tool that could fix a bundle would be a tool that
    could overwrite one."""
    wheel = make_wheel(tmp_path, wd.source_files((".py",)))
    before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    wd.report(check=True, wheel=str(wheel))
    after = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after
