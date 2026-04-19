"""F0-6 acceptance: checkpoint records persist, and cache hit requires hash match."""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, ProducerRef
from framework.core.enums import ArtifactRole, PayloadKind
from framework.runtime.checkpoint_store import CheckpointStore


@pytest.fixture
def env(tmp_path: Path):
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    store = CheckpointStore(artifact_root=tmp_path)
    return repo, store, tmp_path


def test_record_and_find_hit(env):
    repo, store, _ = env
    art = repo.put(
        artifact_id="a1", value={"x": 1},
        artifact_type=ArtifactType(modality="text", shape="structured", display_name="structured_answer"),
        role=ArtifactRole.final, format="json", mime_type="application/json",
        payload_kind=PayloadKind.inline, producer=ProducerRef(run_id="r1", step_id="s1"),
    )
    store.record(run_id="r1", step_id="s1", input_hash="h_in",
                 artifact_ids=["a1"], artifact_hashes=[art.hash])
    hit = store.find_hit(run_id="r1", step_id="s1", input_hash="h_in", repository=repo)
    assert hit is not None
    assert hit.artifact_ids == ["a1"]


def test_miss_on_different_input_hash(env):
    repo, store, _ = env
    art = repo.put(
        artifact_id="a1", value={"x": 1},
        artifact_type=ArtifactType(modality="text", shape="structured", display_name="structured_answer"),
        role=ArtifactRole.final, format="json", mime_type="application/json",
        payload_kind=PayloadKind.inline, producer=ProducerRef(run_id="r1", step_id="s1"),
    )
    store.record(run_id="r1", step_id="s1", input_hash="h_old",
                 artifact_ids=["a1"], artifact_hashes=[art.hash])
    assert store.find_hit(run_id="r1", step_id="s1", input_hash="h_new", repository=repo) is None


def test_miss_when_artifact_hash_drifts(env):
    repo, store, _ = env
    art = repo.put(
        artifact_id="a1", value={"x": 1},
        artifact_type=ArtifactType(modality="text", shape="structured", display_name="structured_answer"),
        role=ArtifactRole.final, format="json", mime_type="application/json",
        payload_kind=PayloadKind.inline, producer=ProducerRef(run_id="r1", step_id="s1"),
    )
    store.record(run_id="r1", step_id="s1", input_hash="h_in",
                 artifact_ids=["a1"], artifact_hashes=["tampered"])  # wrong hash
    assert store.find_hit(run_id="r1", step_id="s1", input_hash="h_in", repository=repo) is None


def test_miss_when_artifact_missing(env):
    repo, store, _ = env
    store.record(run_id="r1", step_id="s1", input_hash="h_in",
                 artifact_ids=["ghost"], artifact_hashes=["whatever"])
    assert store.find_hit(run_id="r1", step_id="s1", input_hash="h_in", repository=repo) is None


def test_persist_and_reload(env):
    repo, store, tmp = env
    store.record(run_id="r1", step_id="s1", input_hash="h",
                 artifact_ids=[], artifact_hashes=[])
    assert (tmp / "r1" / "_checkpoints.json").is_file()

    store2 = CheckpointStore(artifact_root=tmp)
    assert store2.all_for_run("r1") == []
    store2.load_from_disk("r1")
    loaded = store2.all_for_run("r1")
    assert len(loaded) == 1
    assert loaded[0].step_id == "s1"
