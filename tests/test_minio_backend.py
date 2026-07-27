"""R2 — the MinIO / S3 resource backend (object-storage tier).

Verifies (R2 DoD): ingest → object_key + stable ID + manifest entry; resolve →
s3_uri Location (no network); presign → http_url Location; registers above
passthrough (same interface + stable-ID space as R1); MissingDependency when the
SDK is absent. The S3 client is MOCKED — no running MinIO required.
"""

import sys

import pytest

from s3dgraphy import api
from s3dgraphy.resources import (
    MinioBackend,
    MinioConfig,
    default_registry,
)


class _FakeMinioClient:
    """A stand-in for minio.Minio — records calls, needs no server."""

    def __init__(self):
        self.buckets = set()
        self.put = []            # (bucket, key, path)
        self.presigned = []      # (bucket, key)

    def bucket_exists(self, bucket):
        return bucket in self.buckets

    def make_bucket(self, bucket):
        self.buckets.add(bucket)

    def fput_object(self, bucket, key, path):
        self.put.append((bucket, key, path))

    def presigned_get_object(self, bucket, key, expires=None):
        self.presigned.append((bucket, key))
        return f"http://localhost:9000/{bucket}/{key}?X-Amz-Signature=deadbeef"


def _mk(tmp_path, name="scan.obj", content="x"):
    f = tmp_path / name
    f.write_text(content)
    return str(f)


# ── ingest ────────────────────────────────────────────────────────────────────
def test_ingest_uploads_and_records_stable_id(tmp_path):
    client = _FakeMinioClient()
    be = MinioBackend(MinioConfig(bucket="em-resources"), client=client)
    path = _mk(tmp_path, "site.obj")
    rid, key = be.ingest(path)
    assert rid and key == f"{rid}/site.obj"          # id-legible object key
    assert client.buckets == {"em-resources"}         # bucket auto-created
    assert client.put == [("em-resources", key, path)]  # object uploaded
    entry = be.entries()[0]
    assert entry.resource_id == rid and entry.object_key == key
    assert entry.resource_type == "3d_model"          # classified via LinkNode vocab


def test_ingest_is_idempotent_by_source_path(tmp_path):
    client = _FakeMinioClient()
    be = MinioBackend(client=client)
    path = _mk(tmp_path, "a.pdf")
    rid1, _ = be.ingest(path)
    rid2, _ = be.ingest(path)     # same file again → same stable ID
    assert rid1 == rid2 and len(be.entries()) == 1


def test_ingest_honours_explicit_id(tmp_path):
    be = MinioBackend(client=_FakeMinioClient())
    rid, key = be.ingest(_mk(tmp_path), resource_id="fixed-id")
    assert rid == "fixed-id" and key.startswith("fixed-id/")


# ── resolve (no network) ───────────────────────────────────────────────────────
def test_resolve_returns_s3_uri_without_network(tmp_path):
    client = _FakeMinioClient()
    be = MinioBackend(MinioConfig(bucket="assets"), client=client)
    rid, key = be.ingest(_mk(tmp_path, "m.glb"))
    loc = be.resolve(rid, "")
    assert loc.kind == "s3_uri" and loc.value == f"s3://assets/{key}"
    assert loc.exists is None                 # remote — unknown without a HEAD
    assert client.presigned == []             # resolve did NOT touch the network


def test_resolve_unknown_id_falls_through():
    be = MinioBackend(client=_FakeMinioClient())
    assert be.resolve("no-such-id", "") is None


# ── presign (explicit network) ─────────────────────────────────────────────────
def test_presign_returns_http_url(tmp_path):
    client = _FakeMinioClient()
    be = MinioBackend(MinioConfig(bucket="assets"), client=client)
    rid, key = be.ingest(_mk(tmp_path, "photo.jpg"))
    loc = be.presign(rid, expires_seconds=120)
    assert loc.kind == "http_url" and loc.value.startswith("http://localhost:9000/assets/")
    assert client.presigned == [("assets", key)]   # presign DID call the client


# ── registry integration (same interface + stable-ID space as R1) ──────────────
def test_registers_above_passthrough(tmp_path):
    client = _FakeMinioClient()
    be = MinioBackend(MinioConfig(bucket="assets"), client=client)
    rid, key = be.ingest(_mk(tmp_path, "x.obj"))

    reg = default_registry()             # passthrough only
    reg.register(be, priority=20)        # MinIO on top
    assert [b.name for b in reg.backends()] == ["minio", "passthrough"]

    owned = reg.resolve(rid, "ignored-locator")
    assert owned.kind == "s3_uri" and owned.value == f"s3://assets/{key}"
    # a url-only resource the MinIO backend doesn't own → passthrough
    other = reg.resolve("some-linknode-uuid", "https://zenodo.org/record/1")
    assert other.kind == "http_url" and other.value == "https://zenodo.org/record/1"


# ── manifest round-trip (parallel to R1) ────────────────────────────────────────
def test_manifest_roundtrip_preserves_ids(tmp_path):
    be = MinioBackend(MinioConfig(bucket="assets"), client=_FakeMinioClient())
    rid, key = be.ingest(_mk(tmp_path, "y.obj"))
    manifest = be.to_manifest()
    assert "access_key" not in str(manifest)   # credentials never serialised
    rebuilt = MinioBackend.from_manifest(manifest, client=_FakeMinioClient())
    assert rebuilt.resolve(rid, "").value == f"s3://assets/{key}"
    assert rebuilt.config.bucket == "assets"


# ── optional dependency → MissingDependency ─────────────────────────────────────
def test_missing_sdk_raises_missing_dependency(tmp_path, monkeypatch):
    # Simulate the 'minio' SDK being absent: `from minio import Minio` → ImportError.
    monkeypatch.setitem(sys.modules, "minio", None)
    be = MinioBackend()  # no injected client → will try to import the SDK
    with pytest.raises(api.MissingDependency):
        be.ingest(_mk(tmp_path))


def test_missing_dependency_is_importerror():
    # transports map it to a 501 (same contract as rdflib for TTL)
    assert issubclass(api.MissingDependency, ImportError)


# ── shared config from Heriverse S3_* env (connective tissue) ──────────────────
def test_config_from_env_aligns_to_heriverse():
    env = {
        "S3_ENDPOINT": "http://localhost:9000",
        "S3_BUCKET": "heriverse",
        "S3_PREFIX": "heriverse",
        "S3_FORCE_PATH_STYLE": "true",
        "S3_ACCESS_KEY_ID": "admin",
        "S3_SECRET_ACCESS_KEY": "password",
        "S3_REGION": "eu-west-1",
    }
    c = MinioConfig.from_env(env)
    assert c.endpoint == "localhost:9000" and c.secure is False   # scheme stripped
    assert c.bucket == "heriverse" and c.prefix == "heriverse"
    assert c.access_key == "admin" and c.secret_key == "password"
    assert c.region == "eu-west-1" and c.force_path_style is True


def test_config_from_env_https_is_secure():
    c = MinioConfig.from_env({"S3_ENDPOINT": "https://minio.example.org"})
    assert c.endpoint == "minio.example.org" and c.secure is True


def test_config_from_env_defaults_to_heriverse_convention():
    c = MinioConfig.from_env({})   # nothing set → shared defaults
    assert c.endpoint == "localhost:9000" and c.bucket == "heriverse"
    assert c.force_path_style is True


def test_prefix_namespaces_object_key(tmp_path):
    client = _FakeMinioClient()
    be = MinioBackend(MinioConfig(bucket="heriverse", prefix="heriverse"), client=client)
    rid, key = be.ingest(_mk(tmp_path, "m.glb"))
    assert key == f"heriverse/{rid}/m.glb"
    assert be.resolve(rid, "").value == f"s3://heriverse/heriverse/{rid}/m.glb"


def test_presign_key_is_stateless(tmp_path):
    client = _FakeMinioClient()
    be = MinioBackend(MinioConfig(bucket="assets"), client=client)
    loc = be.presign_key("some/known/key.obj", expires_seconds=60)
    assert loc.kind == "http_url"
    assert client.presigned == [("assets", "some/known/key.obj")]


# ── the seam stays S3-dep-free ──────────────────────────────────────────────────
def test_construction_pulls_no_s3_dep(monkeypatch):
    # Force `from minio import Minio` to fail; constructing the backend (and any
    # dep-free op) must still work — the SDK is only touched on a network op.
    monkeypatch.setitem(sys.modules, "minio", None)
    from s3dgraphy.resources import MinioBackend, MinioConfig
    be = MinioBackend(MinioConfig())
    assert be.name == "minio"
    assert be.resolve("unknown", "") is None   # dep-free lookup still works
