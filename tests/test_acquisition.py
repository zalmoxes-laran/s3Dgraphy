"""Shelf v2 core (Session B) — the Tier-0 acquisition hook.

Verifies: AcquisitionDescriptor v0 load/validate (Tier-0 = no payload_graph);
per-source mapping (Ercolano) raw record → descriptor; acquire → Resource on the
shelf (origin preserved) + a DTCAcquisitionNode event (crmdig:D12, distinct from
the genesis DTCProcessNode) wired acquisition ─dtc_had_output→ Resource;
idempotent re-acquisition; payload_graph → refused (Tier 1/2 later). Plus the new
node type registers + projects.
"""

import pytest

from s3dgraphy import api
from s3dgraphy.acquisition import (
    SCHEMA_VERSION,
    AcquisitionDescriptor,
    AcquisitionError,
)
from s3dgraphy.nodes import DTCAcquisitionNode, DTCProcessNode
from s3dgraphy.shelf import is_shelf


_ERCOLANO_RECORD = {
    "url": "https://ercolano.example/models/lamp.glb",
    "media_type": "model/gltf-binary",
    "title": "Roman lamp (Ercolano)",
    "record_id": "ERC-1234",
    "record_url": "https://ercolano.example/record/1234",
    "license": "CC-BY-4.0",
    "rights_holder": "Parco Archeologico di Ercolano",
    "retrieved_at": "2026-07-30T10:00:00Z",
    "method": "download",
}


# ── descriptor v0 ────────────────────────────────────────────────────────────
def test_descriptor_validate_and_tier0():
    d = AcquisitionDescriptor.from_dict({
        "schema_version": "0",
        "asset": {"ref": "/x.jpg", "media_type": "image/jpeg"},
        "source": {"repo_id": "ercolano", "capabilities": []},
    })
    assert d.is_tier0() and d.schema_version == SCHEMA_VERSION
    assert d.origin() == {"repo": "ercolano", "capabilities": [], "scope": None}


def test_descriptor_requires_asset_ref():
    with pytest.raises(AcquisitionError):
        AcquisitionDescriptor.from_dict({"schema_version": "0", "asset": {}})


def test_descriptor_rejects_unsupported_version():
    with pytest.raises(AcquisitionError):
        AcquisitionDescriptor.from_dict(
            {"schema_version": "9", "asset": {"ref": "/x"}})


def test_descriptor_not_tier0_when_payload():
    d = AcquisitionDescriptor.from_dict({
        "schema_version": "0", "asset": {"ref": "/x"},
        "payload_graph": {"scope": "genesis", "subgraph": {}},
    })
    assert d.is_tier0() is False


# ── per-source mapping (Ercolano) ────────────────────────────────────────────
def test_ercolano_mapping_builds_descriptor():
    desc = api.apply_acquisition_mapping("ercolano", _ERCOLANO_RECORD)
    d = AcquisitionDescriptor.from_dict(desc)
    assert d.source["repo_id"] == "ercolano" and d.source["capabilities"] == []
    assert d.asset["ref"] == _ERCOLANO_RECORD["url"]
    assert d.asset["name"] == "Roman lamp (Ercolano)"
    assert d.rights["license"] == "CC-BY-4.0"
    assert d.rights["holder"] == "Parco Archeologico di Ercolano"
    assert d.acquisition["method"] == "download"
    assert d.is_tier0()  # Ercolano is opaque Tier 0


def test_mapping_defaults_win_when_record_missing_keys():
    desc = api.apply_acquisition_mapping("ercolano", {"url": "/only/ref.obj"})
    # defaults supply repo_id/capabilities/method/license even with a sparse record
    assert desc["source"]["repo_id"] == "ercolano"
    assert desc["acquisition"]["method"] == "download"
    assert desc["rights"]["license"] == "unknown"


# ── acquire (Tier 0) ─────────────────────────────────────────────────────────
def test_acquire_creates_resource_event_and_edge():
    desc = api.apply_acquisition_mapping("ercolano", _ERCOLANO_RECORD)
    info, shelf = api.acquire_from_descriptor(desc)  # shelf auto-created
    assert is_shelf(shelf) and info["tier"] == 0

    rid, acq_id = info["resource_id"], info["acquisition_id"]
    res = shelf.find_node_by_id(rid)
    acq = shelf.find_node_by_id(acq_id)
    # the Resource (ResourceNode) carries the locator + origin (for tier badges)
    assert res.node_type == "resource" and res.data["url"] == _ERCOLANO_RECORD["url"]
    assert res.data["origin"] == {"repo": "ercolano", "capabilities": [], "scope": None}
    assert res.data.get("resource_type") == "proxy_model"  # .glb per ResourceNode vocab
    # the acquisition event is a DISTINCT DTC type (crmdig:D12), not a process node
    assert isinstance(acq, DTCAcquisitionNode) and acq.node_type == "dtc_acquisition"
    assert not isinstance(acq, DTCProcessNode)
    # opaque source captured as literals (no genesis sub-graph)
    assert acq.data["repo_id"] == "ercolano" and acq.data["record_id"] == "ERC-1234"
    assert acq.data["license"] == "CC-BY-4.0" and acq.data["method"] == "download"
    assert acq.data.get("dtc_kind") == "download"  # method validated into the kind vocab
    # single ring: acquisition ─dtc_had_output→ Resource
    outs = [(e.edge_source, e.edge_target, e.edge_type) for e in shelf.edges]
    assert (acq_id, rid, "dtc_had_output") in outs


def test_acquire_is_idempotent():
    desc = api.apply_acquisition_mapping("ercolano", _ERCOLANO_RECORD)
    info1, shelf = api.acquire_from_descriptor(desc)
    info2, shelf = api.acquire_from_descriptor(desc, shelf)  # same record again
    assert info1["resource_id"] == info2["resource_id"]
    assert info1["acquisition_id"] == info2["acquisition_id"]
    links = [n for n in shelf.nodes if n.node_type == "resource"]
    acqs = [n for n in shelf.nodes if n.node_type == "dtc_acquisition"]
    edges = [e for e in shelf.edges if e.edge_type == "dtc_had_output"]
    assert len(links) == 1 and len(acqs) == 1 and len(edges) == 1  # no duplicates


def test_acquire_refuses_payload_graph():
    with pytest.raises(AcquisitionError):
        api.acquire_from_descriptor({
            "schema_version": "0", "asset": {"ref": "/x.jpg"},
            "source": {"repo_id": "eccch", "capabilities": ["genesis"]},
            "payload_graph": {"scope": "genesis", "subgraph": {}},
        })


def test_acquired_resource_instantiates_into_a_study():
    from s3dgraphy.graph import Graph
    desc = api.apply_acquisition_mapping("ercolano", _ERCOLANO_RECORD)
    info, shelf = api.acquire_from_descriptor(desc)
    study = Graph(graph_id="study")
    node = api.instantiate_from_shelf(shelf, info["resource_id"], study)
    assert node.node_id == info["resource_id"]
    assert (node.data or {}).get("origin", {}).get("repo") == "ercolano"


# ── the new node type is registered + projects ──────────────────────────────
def test_acquisition_node_in_registry():
    import json
    from pathlib import Path
    reg = json.loads((Path(api.__file__).resolve().parent
                      / "JSON_config" / "node_registry.generated.json").read_text())
    assert reg["node_types"]["DTCAcquisitionNode"]["node_type"] == "dtc_acquisition"


def test_acquisition_projects_to_crmdig_d12():
    pytest.importorskip("rdflib")
    desc = api.apply_acquisition_mapping("ercolano", _ERCOLANO_RECORD)
    _info, shelf = api.acquire_from_descriptor(desc)
    ttl = api.project_ttl(shelf)
    assert "D12_Data_Transfer_Event" in ttl
