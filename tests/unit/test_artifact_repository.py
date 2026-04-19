"""F0-3 acceptance: ArtifactRepository write/read, lineage queries, variant siblings."""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, Lineage, ProducerRef
from framework.core.enums import ArtifactRole, PayloadKind


@pytest.fixture
def repo(tmp_path: Path) -> ArtifactRepository:
    reg = get_backend_registry(artifact_root=str(tmp_path))
    return ArtifactRepository(backend_registry=reg)


def _text_type() -> ArtifactType:
    return ArtifactType(modality="text", shape="structured", display_name="structured_answer")


def _image_type() -> ArtifactType:
    return ArtifactType(modality="image", shape="raster", display_name="concept_image")


def test_put_and_get_inline(repo: ArtifactRepository):
    art = repo.put(
        artifact_id="a1", value={"x": 1}, artifact_type=_text_type(),
        role=ArtifactRole.final, format="json", mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r1", step_id="s1"),
    )
    assert repo.exists("a1")
    assert repo.read_payload("a1") == {"x": 1}
    assert art.hash == repo.get("a1").hash


def test_put_file_persisted_on_disk(repo: ArtifactRepository, tmp_path: Path):
    art = repo.put(
        artifact_id="img_1", value=b"\x89PNG\r\n", artifact_type=_image_type(),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="run_a", step_id="gen"),
        file_suffix=".png",
    )
    assert art.payload_ref.file_path == "run_a/img_1.png"
    assert (tmp_path / "run_a" / "img_1.png").is_file()
    assert repo.read_payload("img_1") == b"\x89PNG\r\n"


def test_same_value_same_hash(repo: ArtifactRepository):
    repo.put(artifact_id="a1", value={"k": 1}, artifact_type=_text_type(),
             role=ArtifactRole.final, format="json", mime_type="application/json",
             payload_kind=PayloadKind.inline, producer=ProducerRef(run_id="r1", step_id="s1"))
    repo.put(artifact_id="a2", value={"k": 1}, artifact_type=_text_type(),
             role=ArtifactRole.final, format="json", mime_type="application/json",
             payload_kind=PayloadKind.inline, producer=ProducerRef(run_id="r2", step_id="s1"))
    assert repo.get("a1").hash == repo.get("a2").hash


def test_get_missing_raises(repo: ArtifactRepository):
    with pytest.raises(KeyError):
        repo.get("nope")


def test_lineage_parents_children_and_ancestors(repo: ArtifactRepository):
    prod = ProducerRef(run_id="r1", step_id="s1")
    repo.put(artifact_id="a1", value={"n": 1}, artifact_type=_text_type(),
             role=ArtifactRole.intermediate, format="json", mime_type="application/json",
             payload_kind=PayloadKind.inline, producer=prod)
    repo.put(artifact_id="a2", value={"n": 2}, artifact_type=_text_type(),
             role=ArtifactRole.intermediate, format="json", mime_type="application/json",
             payload_kind=PayloadKind.inline, producer=prod,
             lineage=Lineage(source_artifact_ids=["a1"]))
    repo.put(artifact_id="a3", value={"n": 3}, artifact_type=_text_type(),
             role=ArtifactRole.final, format="json", mime_type="application/json",
             payload_kind=PayloadKind.inline, producer=prod,
             lineage=Lineage(source_artifact_ids=["a2"]))
    assert [a.artifact_id for a in repo.parents_of("a3")] == ["a2"]
    assert [a.artifact_id for a in repo.children_of("a1")] == ["a2"]
    ancestors = {a.artifact_id for a in repo.ancestors_of("a3")}
    assert ancestors == {"a1", "a2"}


def test_variant_siblings(repo: ArtifactRepository):
    prod = ProducerRef(run_id="r1", step_id="s1")
    repo.put(artifact_id="v_original", value=b"o", artifact_type=_image_type(),
             role=ArtifactRole.intermediate, format="png", mime_type="image/png",
             payload_kind=PayloadKind.file, producer=prod, file_suffix=".png",
             lineage=Lineage(variant_group_id="g1", variant_kind="original"))
    repo.put(artifact_id="v_lod0", value=b"l0", artifact_type=_image_type(),
             role=ArtifactRole.intermediate, format="png", mime_type="image/png",
             payload_kind=PayloadKind.file, producer=prod, file_suffix=".png",
             lineage=Lineage(variant_group_id="g1", variant_kind="lod_0"))
    repo.put(artifact_id="v_compressed", value=b"c", artifact_type=_image_type(),
             role=ArtifactRole.intermediate, format="png", mime_type="image/png",
             payload_kind=PayloadKind.file, producer=prod, file_suffix=".png",
             lineage=Lineage(variant_group_id="g1", variant_kind="compressed"))
    siblings = {a.artifact_id for a in repo.siblings_of("v_original")}
    assert siblings == {"v_lod0", "v_compressed"}


def test_find_by_tag_and_producer(repo: ArtifactRepository):
    repo.put(artifact_id="a1", value={"k": 1}, artifact_type=_text_type(),
             role=ArtifactRole.final, format="json", mime_type="application/json",
             payload_kind=PayloadKind.inline,
             producer=ProducerRef(run_id="r1", step_id="s1"), tags=["ue", "tavern"])
    repo.put(artifact_id="a2", value={"k": 2}, artifact_type=_text_type(),
             role=ArtifactRole.final, format="json", mime_type="application/json",
             payload_kind=PayloadKind.inline,
             producer=ProducerRef(run_id="r2", step_id="s2"), tags=["ue"])
    assert {a.artifact_id for a in repo.find_by_tag("tavern")} == {"a1"}
    assert {a.artifact_id for a in repo.find_by_producer(run_id="r1")} == {"a1"}
    assert {a.artifact_id for a in repo.find_by_producer(step_id="s2")} == {"a2"}
