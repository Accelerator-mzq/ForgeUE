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


# ---------------------------------------------------------------------------
# TBD-012 Task 1: hash_path stream SHA-256 helper
# ---------------------------------------------------------------------------

import pytest  # noqa: E402 — 追加在文件末尾,import 跟随测试块

from framework.artifact_store.hashing import hash_path, hash_payload  # noqa: E402


@pytest.mark.parametrize("size", [1, 64 * 1024, 1 * 1024 * 1024, 50 * 1024 * 1024])
def test_hash_path_equivalent_to_hash_payload(tmp_path, size):
    # 跨多个 size grade 验证 stream / value 哈希等价
    p = tmp_path / f"blob_{size}.bin"
    data = (b"\xA5" * size) if size <= 1024 * 1024 else (b"\xA5" * (size // 16)) * 16
    p.write_bytes(data)
    assert hash_path(p) == hash_payload(p.read_bytes())


def test_hash_path_chunk_size_does_not_affect_output(tmp_path):
    # 不同 chunk_size 输出 SHALL 完全一致
    p = tmp_path / "blob_chunked.bin"
    p.write_bytes(b"forge-ue-test-pattern" * 12345)  # ~258 KB
    h1 = hash_path(p, chunk_size=1024)
    h2 = hash_path(p, chunk_size=8 * 1024 * 1024)
    h3 = hash_payload(p.read_bytes())
    assert h1 == h2 == h3


@pytest.mark.parametrize("bad_chunk_size", [0, -1, -8 * 1024])
def test_hash_path_rejects_non_positive_chunk_size(tmp_path, bad_chunk_size):
    """R4-F4 fence:chunk_size <= 0 必须 raise ValueError;否则 f.read(0) 静默返
    回空 bytes,非空文件会得到 empty hash(silent corruption)。"""
    p = tmp_path / "nonempty.bin"
    p.write_bytes(b"some-content-that-must-be-hashed")
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        hash_path(p, chunk_size=bad_chunk_size)


# ---------------------------------------------------------------------------
# TBD-012 Task 6: load_run_metadata file-kind drift uses hash_path (stream)
# ---------------------------------------------------------------------------

from unittest.mock import patch as _patch_t6  # noqa: E402


def test_load_metadata_uses_stream_hash_for_file_kind(repo, tmp_path):
    """File kind drift 校验应走 hash_path 不走 hash_payload(spy 守门)。"""
    src = tmp_path / "raw.bin"
    src.write_bytes(b"forge-drift-test" * 4096)  # 64 KB
    art = repo.put(
        artifact_id="aid_drift",
        source_path=src,
        artifact_type=ArtifactType(modality="image", shape="raster", display_name="img"),
        role=ArtifactRole.intermediate,
        format="bin",
        mime_type="application/octet-stream",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r_drift", step_id="s1", provider="t", model="m"),
        file_suffix=".bin",
    )
    run_dir = tmp_path / "run_dir"
    repo.dump_run_metadata(run_id="r_drift", run_dir=run_dir)

    # 另起 repo 跑 load(同一 store 让 backend exists 返回 True)
    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    fresh._artifacts.clear()

    import framework.artifact_store.repository as repo_mod
    with _patch_t6.object(
        repo_mod, "hash_payload",
        side_effect=AssertionError("hash_payload SHALL NOT be invoked on file kind drift check"),
    ):
        n = fresh.load_run_metadata(run_id="r_drift", run_dir=run_dir)
    assert n == 1
    assert "aid_drift" in fresh._artifacts


def test_load_metadata_rejects_corrupted_file_stream(repo, tmp_path):
    """落盘 bytes 被改后 stream drift 应检出 → entry skipped。"""
    src = tmp_path / "good.bin"
    src.write_bytes(b"good-original-data" * 1024)
    art = repo.put(
        artifact_id="aid_corrupt",
        source_path=src,
        artifact_type=ArtifactType(modality="image", shape="raster", display_name="img"),
        role=ArtifactRole.intermediate,
        format="bin",
        mime_type="application/octet-stream",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="r_corrupt", step_id="s1", provider="t", model="m"),
        file_suffix=".bin",
    )
    run_dir = tmp_path / "run_dir_corrupt"
    repo.dump_run_metadata(run_id="r_corrupt", run_dir=run_dir)

    backend = repo.backend_registry.get(PayloadKind.file)
    on_disk = backend.absolute_path(art.payload_ref)
    on_disk.write_bytes(b"TAMPERED")

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    fresh._artifacts.clear()
    n = fresh.load_run_metadata(run_id="r_corrupt", run_dir=run_dir)
    assert n == 0
    assert "aid_corrupt" not in fresh._artifacts


def test_load_metadata_blob_kind_preserves_legacy_behavior(repo, tmp_path):
    """R3-F4 D-DriftScope:blob kind 保旧行为(不走 hash_path),走 read+hash_payload。

    BlobBackend.exists() stub 抛 NotImplementedError;
    BlobBackend.read() stub 抛 NotImplementedError。
    测试 patch exists() → True 让流程进入 drift 块,然后 read() 抛 NotImplementedError
    被 `except Exception: continue` 兜住。关键断言:hash_path spy 未触发(D-DriftScope)。
    """
    import json
    from unittest.mock import MagicMock
    run_dir = tmp_path / "run_dir_blob"
    run_dir.mkdir(parents=True, exist_ok=True)
    blob_art_dict = {
        "artifact_id": "aid_blob",
        "artifact_type": {"modality": "image", "shape": "raster", "display_name": "x"},
        "role": "intermediate",
        "format": "bin",
        "mime_type": "application/octet-stream",
        "payload_ref": {"kind": "blob", "blob_key": "s3://stub/key", "size_bytes": 0},
        "schema_version": "1.0.0",
        "hash": "0" * 64,
        "producer": {"run_id": "r_blob", "step_id": "s1", "provider": "t", "model": "m"},
        "lineage": {},
        "metadata": {},
        "validation": {"status": "pending"},
        "tags": [],
        "created_at": "2026-05-21T10:00:00+00:00",
    }
    (run_dir / "_artifacts.json").write_text(
        json.dumps([blob_art_dict], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    fresh._artifacts.clear()
    import framework.artifact_store.repository as repo_mod

    # patch exists() → True 让流程越过 payload_present 守门进入 drift 块;
    # read() 保持原 stub 行为(抛 NotImplementedError)→ except Exception: continue 兜
    with _patch_t6.object(repo_mod, "hash_path",
                          side_effect=AssertionError("hash_path SHALL NOT be invoked on blob kind drift")):
        with _patch_t6.object(fresh._registry, "exists", return_value=True):
            n = fresh.load_run_metadata(run_id="r_blob", run_dir=run_dir)
    # BlobBackend.read() 抛 NotImplementedError → except Exception: continue → n=0
    # 关键不是 n 值,是 hash_path spy 没被触发(D-DriftScope)
    assert n == 0
    assert "aid_blob" not in fresh._artifacts
