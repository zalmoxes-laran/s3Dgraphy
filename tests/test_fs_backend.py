"""R1 — the FS-index resource backend (Tropy-like), generalising DosCo.

Verifies (R1 DoD): scan a folder → stable IDs + manifest; resolve(id) →
local_path Location (exists=True); add/delete + rescan reflected (new / missing);
D.NN name-match still resolves to the right document; orphan detection lists
unmatched files; registers above passthrough; non-breaking.
"""

from s3dgraphy import api
from s3dgraphy.graph import Graph
from s3dgraphy.nodes.link_node import LinkNode
from s3dgraphy.resources import (
    FSIndexBackend,
    PassthroughBackend,
    ResolverRegistry,
    classify_resource_type,
    default_registry,
)


def _mk(tmp_path, name, content="x"):
    f = tmp_path / name
    f.write_text(content)
    return f


# ── scan → stable IDs + manifest ───────────────────────────────────────────────
def test_scan_indexes_files_with_stable_ids(tmp_path):
    _mk(tmp_path, "D.01 photo.jpg")
    _mk(tmp_path, "D.02.pdf")
    be = FSIndexBackend(str(tmp_path))
    result = be.scan()
    assert len(result.added) == 2 and not result.missing
    entries = be.entries()
    assert {e.rel_path for e in entries} == {"D.01 photo.jpg", "D.02.pdf"}
    # every entry carries a stable, unique id + classified type
    ids = {e.resource_id for e in entries}
    assert len(ids) == 2 and all(ids)
    types = {e.name: e.resource_type for e in entries}
    assert types["D.01 photo"] == "image" and types["D.02"] == "document"


def test_dotfiles_are_skipped(tmp_path):
    _mk(tmp_path, ".DS_Store")
    _mk(tmp_path, "D.03.png")
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    assert [e.name for e in be.entries()] == ["D.03"]


def test_rescan_keeps_stable_ids(tmp_path):
    _mk(tmp_path, "D.01.jpg")
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    first_id = be.entries()[0].resource_id
    _mk(tmp_path, "D.02.pdf")
    result = be.rescan()
    # the pre-existing file keeps its id; only the new one is "added"
    assert first_id in result.present and len(result.added) == 1
    assert be.entries()[0].resource_id == first_id  # sorted by rel_path → D.01 first


# ── resolve ────────────────────────────────────────────────────────────────────
def test_resolve_returns_local_path_location(tmp_path):
    f = _mk(tmp_path, "D.05.obj")
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    rid = be.entries()[0].resource_id
    loc = be.resolve(rid, "")
    assert loc.kind == "local_path" and loc.exists is True
    assert loc.value == str(f)


def test_resolve_unknown_id_falls_through(tmp_path):
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    assert be.resolve("no-such-id", "") is None


# ── add / delete + rescan reflected ─────────────────────────────────────────────
def test_delete_file_then_rescan_flags_missing(tmp_path):
    f = _mk(tmp_path, "D.09.txt")
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    rid = be.entries()[0].resource_id
    f.unlink()
    result = be.rescan()
    assert rid in result.missing
    # a missing resource no longer resolves (falls through to the next backend)
    assert be.resolve(rid, "") is None
    assert be.entries(present_only=True) == []


def test_add_file_then_rescan_is_new(tmp_path):
    _mk(tmp_path, "D.01.jpg")
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    _mk(tmp_path, "unfiled_photo.png")
    result = be.rescan()
    assert len(result.added) == 1


# ── D.NN name-match (optional convenience) ─────────────────────────────────────
def test_name_match_resolves_to_right_document(tmp_path):
    _mk(tmp_path, "D.02 field notes.jpg")
    _mk(tmp_path, "D.02.01.png")   # an extractor output — must NOT match D.02
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    hit = be.match_name("D.02")
    assert hit is not None and hit.rel_path == "D.02 field notes.jpg"
    # the match yields the STABLE id, not a name — identity is the id
    assert be.resolve(hit.resource_id, "").value.endswith("D.02 field notes.jpg")
    # the extractor file is reachable only by its own id/name
    assert be.match_name("D.02.01").rel_path == "D.02.01.png"


def test_name_match_prefers_priority_extension(tmp_path):
    _mk(tmp_path, "D.07.txt")
    _mk(tmp_path, "D.07.jpg")   # jpg outranks txt
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    assert be.match_name("D.07").rel_path == "D.07.jpg"


def test_name_match_none_when_absent(tmp_path):
    _mk(tmp_path, "D.01.jpg")
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    assert be.match_name("D.99") is None


# ── orphan detection ────────────────────────────────────────────────────────────
def _doc(node_id, name):
    from s3dgraphy.nodes.document_node import DocumentNode
    return DocumentNode(node_id=node_id, name=name)


def test_orphans_lists_files_without_a_node(tmp_path):
    _mk(tmp_path, "D.01.jpg")   # has a node → not an orphan
    _mk(tmp_path, "D.42.pdf")   # no node → orphan
    _mk(tmp_path, "notes.txt")  # off-convention → ignored (not an orphan)
    _mk(tmp_path, "D.05.03.png")  # extractor-like, no node → ignored
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    g = Graph(graph_id="g")
    g.add_node(_doc("d1", "D.01"))
    orphans = be.orphans(g)
    assert [o.key_id for o in orphans] == ["D.42"]
    o = orphans[0]
    assert o.filename == "D.42.pdf" and o.resource_id  # carries the stable id


def test_orphans_honour_graph_code_prefix(tmp_path):
    _mk(tmp_path, "D.11.pdf")
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    g = Graph(graph_id="g")
    g.add_node(_doc("d1", "GT26.D.11"))  # prefixed node matches unprefixed file
    assert be.orphans(g, graph_code="GT26") == []


# ── registry integration (plugs in above passthrough) ──────────────────────────
def test_fs_backend_registers_above_passthrough(tmp_path):
    f = _mk(tmp_path, "D.01.jpg")
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    rid = be.entries()[0].resource_id

    reg = default_registry()               # passthrough only
    reg.register(be, priority=10)          # FS backend on top
    assert [b.name for b in reg.backends()] == ["fs_index", "passthrough"]

    # an FS-owned id resolves to the real local path via the FS backend...
    owned = reg.resolve(rid, "ignored-locator")
    assert owned.kind == "local_path" and owned.value == str(f)
    # ...a url-only resource (not in the index) still falls through to passthrough
    other = reg.resolve("some-linknode-uuid", "https://zenodo.org/record/1")
    assert other.kind == "http_url" and other.value == "https://zenodo.org/record/1"


# ── manifest round-trip (Tropy-like persistence) ────────────────────────────────
def test_manifest_roundtrip_preserves_ids(tmp_path):
    _mk(tmp_path, "D.01.jpg")
    _mk(tmp_path, "D.02.pdf")
    be = FSIndexBackend(str(tmp_path))
    be.scan()
    ids_before = {e.resource_id for e in be.entries()}
    rebuilt = FSIndexBackend.from_manifest(be.to_manifest())
    assert {e.resource_id for e in rebuilt.entries()} == ids_before
    rid = next(iter(ids_before))
    assert rebuilt.resolve(rid, "").kind == "local_path"


# ── non-breaking + helpers ──────────────────────────────────────────────────────
def test_classify_resource_type_uses_linknode_vocab():
    assert classify_resource_type("x.glb") == "proxy_model"
    assert classify_resource_type("x.e57") == "point_cloud"
    assert classify_resource_type("x.zzz") == "unknown"


def test_api_scan_fs_resources(tmp_path):
    _mk(tmp_path, "D.01.jpg")
    out = api.scan_fs_resources(str(tmp_path))
    assert len(out) == 1 and out[0]["resource_type"] == "image"
    assert out[0]["id"] and out[0]["rel_path"] == "D.01.jpg"


def test_default_registry_unchanged_by_r1():
    # R0 contract intact: the default registry is passthrough-only.
    reg = default_registry()
    assert [b.name for b in reg.backends()] == ["passthrough"]
    assert isinstance(reg.backends()[0], PassthroughBackend)
