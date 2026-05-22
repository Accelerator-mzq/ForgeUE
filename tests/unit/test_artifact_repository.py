"""F0-3 acceptance: ArtifactRepository write/read, lineage queries, variant siblings."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.artifact_store.repository import ArtifactMetadataIntegrityError
from framework.artifact_store.payload_backends import BlobBackend, PayloadBackendRegistry
from framework.artifact_store.payload_backends.blob_backend import InMemoryBlobClient
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

import framework.artifact_store.hashing as hashing  # noqa: E402
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


@pytest.mark.asyncio
async def test_ahash_path_equivalent_to_sync_hash_path(tmp_path):
    # async 变体只负责把同步 stream hash 挪到线程,输出契约必须完全一致。
    p = tmp_path / "async_blob.bin"
    p.write_bytes(b"forge-ue-async-hash" * 8192)

    async_hash = await hashing.ahash_path(p, chunk_size=1024)

    assert async_hash == hash_path(p, chunk_size=1024)
    assert async_hash == hash_payload(p.read_bytes())


@pytest.mark.asyncio
async def test_ahash_path_rejects_non_positive_chunk_size(tmp_path):
    # bad chunk_size 由 hash_path 原样校验,async wrapper 不吞异常。
    p = tmp_path / "async_nonempty.bin"
    p.write_bytes(b"some-content-that-must-be-hashed")

    with pytest.raises(ValueError, match="chunk_size must be positive"):
        await hashing.ahash_path(p, chunk_size=0)


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


def test_load_metadata_blob_kind_registers_when_payload_matches(repo, tmp_path):
    """FOR-11:BlobBackend MVP 实装后,blob kind 可随 run metadata 恢复。"""
    art = repo.put(
        artifact_id="aid_blob",
        value=b"blob-payload-for-resume",
        artifact_type=ArtifactType(modality="image", shape="raster", display_name="img"),
        role=ArtifactRole.intermediate,
        format="bin",
        mime_type="application/octet-stream",
        payload_kind=PayloadKind.blob,
        producer=ProducerRef(run_id="r_blob", step_id="s1", provider="t", model="m"),
        file_suffix=".bin",
    )
    run_dir = tmp_path / "run_dir_blob"
    repo.dump_run_metadata(run_id="r_blob", run_dir=run_dir)

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    fresh._artifacts.clear()
    import framework.artifact_store.repository as repo_mod
    real_hash_path = repo_mod.hash_path

    def _hash_path_only_for_metadata_integrity(path, *args, **kwargs):
        if Path(path).name == "_artifacts.json":
            return real_hash_path(path, *args, **kwargs)
        raise AssertionError("hash_path SHALL NOT be invoked on blob kind drift")

    with _patch_t6.object(
        repo_mod,
        "hash_path",
        side_effect=_hash_path_only_for_metadata_integrity,
    ):
        n = fresh.load_run_metadata(run_id="r_blob", run_dir=run_dir)

    assert n == 1
    assert "aid_blob" in fresh._artifacts
    assert fresh.get("aid_blob").hash == art.hash


def test_load_metadata_rejects_corrupted_blob_payload(tmp_path):
    """FOR-11:blob object bytes 漂移时,metadata entry 必须被跳过。"""
    client = InMemoryBlobClient()
    reg = PayloadBackendRegistry()
    reg.register(BlobBackend(bucket="bucket", client=client))
    repo = ArtifactRepository(backend_registry=reg)
    art = repo.put(
        artifact_id="aid_blob_corrupt",
        value=b"original-blob-payload",
        artifact_type=ArtifactType(modality="image", shape="raster", display_name="img"),
        role=ArtifactRole.intermediate,
        format="bin",
        mime_type="application/octet-stream",
        payload_kind=PayloadKind.blob,
        producer=ProducerRef(run_id="r_blob_corrupt", step_id="s1", provider="t", model="m"),
        file_suffix=".bin",
    )
    run_dir = tmp_path / "run_dir_blob_corrupt"
    repo.dump_run_metadata(run_id="r_blob_corrupt", run_dir=run_dir)
    client.upload_bytes(
        art.payload_ref.blob_key,
        b"tampered-blob-payload",
        metadata={"content_hash": "tampered", "source": "test"},
    )

    fresh = ArtifactRepository(backend_registry=reg)
    fresh._artifacts.clear()
    n = fresh.load_run_metadata(run_id="r_blob_corrupt", run_dir=run_dir)

    assert n == 0
    assert "aid_blob_corrupt" not in fresh._artifacts


def test_repo_put_blob_source_path_persists_payload(tmp_path):
    """FOR-11:repo.put 的 source_path 入口也允许 blob backend 使用。"""
    reg = PayloadBackendRegistry()
    reg.register(BlobBackend(bucket="bucket"))
    repo = ArtifactRepository(backend_registry=reg)
    src = tmp_path / "blob-source.bin"
    payload = b"blob-payload-from-repo-source-path"
    src.write_bytes(payload)

    art = repo.put(
        artifact_id="aid_blob_source",
        source_path=src,
        artifact_type=ArtifactType(modality="image", shape="raster", display_name="img"),
        role=ArtifactRole.intermediate,
        format="bin",
        mime_type="application/octet-stream",
        payload_kind=PayloadKind.blob,
        producer=ProducerRef(run_id="r_blob_source", step_id="s1", provider="t", model="m"),
        file_suffix=".bin",
    )

    assert art.payload_ref.kind == PayloadKind.blob
    assert art.payload_ref.blob_key == "bucket/r_blob_source/aid_blob_source.bin"
    assert repo.read_payload("aid_blob_source") == payload


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_dump_run_metadata_writes_integrity_file(repo: ArtifactRepository, tmp_path: Path):
    """FOR-14:dump _artifacts.json 后必须写伴生 integrity 文件。"""
    repo.put(
        artifact_id="aid_integrity_1",
        value={"x": 1},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_integrity", step_id="s1"),
    )
    repo.put(
        artifact_id="aid_integrity_2",
        value={"x": 2},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_integrity", step_id="s2"),
    )

    run_dir = tmp_path / "run_dir_integrity"
    dumped = repo.dump_run_metadata(run_id="r_integrity", run_dir=run_dir)

    artifacts_path = run_dir / "_artifacts.json"
    integrity_path = run_dir / "_artifacts.integrity.json"
    integrity = _read_json(integrity_path)

    assert dumped == 2
    assert artifacts_path.is_file()
    assert integrity_path.is_file()
    assert integrity == {
        "schema_version": "1.0",
        "artifacts_file": "_artifacts.json",
        "algorithm": "sha256",
        "artifacts_sha256": hash_path(artifacts_path),
        "artifact_count": 2,
        "artifact_ids": ["aid_integrity_1", "aid_integrity_2"],
    }


def test_load_run_metadata_fails_fast_when_inline_payload_metadata_changes(
    repo: ArtifactRepository,
    tmp_path: Path,
):
    """FOR-14:inline payload 属于 metadata 本身,被改后 resume 必须 fail-fast。"""
    repo.put(
        artifact_id="aid_inline_tamper",
        value={"x": 1},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_inline_tamper", step_id="s1"),
    )
    run_dir = tmp_path / "run_dir_inline_tamper"
    repo.dump_run_metadata(run_id="r_inline_tamper", run_dir=run_dir)

    artifacts_path = run_dir / "_artifacts.json"
    data = _read_json(artifacts_path)
    data[0]["payload_ref"]["inline_value"] = {"x": 2}
    data[0]["hash"] = hash_payload({"x": 2})
    _write_json(artifacts_path, data)

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    with pytest.raises(ArtifactMetadataIntegrityError, match="hash mismatch"):
        fresh.load_run_metadata(run_id="r_inline_tamper", run_dir=run_dir)
    assert not fresh.exists("aid_inline_tamper")


def test_load_run_metadata_fails_fast_when_artifact_id_changes(
    repo: ArtifactRepository,
    tmp_path: Path,
):
    """FOR-14:即使 integrity hash 被同步改写,artifact_id 摘要也要挡住改名。"""
    repo.put(
        artifact_id="aid_original",
        value={"x": 1},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_id_tamper", step_id="s1"),
    )
    run_dir = tmp_path / "run_dir_id_tamper"
    repo.dump_run_metadata(run_id="r_id_tamper", run_dir=run_dir)

    artifacts_path = run_dir / "_artifacts.json"
    integrity_path = run_dir / "_artifacts.integrity.json"
    data = _read_json(artifacts_path)
    data[0]["artifact_id"] = "aid_renamed"
    _write_json(artifacts_path, data)

    integrity = _read_json(integrity_path)
    integrity["artifacts_sha256"] = hash_path(artifacts_path)
    _write_json(integrity_path, integrity)

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    with pytest.raises(ArtifactMetadataIntegrityError, match="artifact id list mismatch"):
        fresh.load_run_metadata(run_id="r_id_tamper", run_dir=run_dir)
    assert not fresh.exists("aid_original")
    assert not fresh.exists("aid_renamed")


def test_load_run_metadata_fails_fast_when_integrity_json_is_invalid(
    repo: ArtifactRepository,
    tmp_path: Path,
):
    """FOR-14:integrity 文件坏掉时不得退回 legacy 路径。"""
    repo.put(
        artifact_id="aid_bad_integrity",
        value={"x": 1},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_bad_integrity", step_id="s1"),
    )
    run_dir = tmp_path / "run_dir_bad_integrity"
    repo.dump_run_metadata(run_id="r_bad_integrity", run_dir=run_dir)
    (run_dir / "_artifacts.integrity.json").write_text("{not json", encoding="utf-8")

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    with pytest.raises(ArtifactMetadataIntegrityError, match="invalid JSON"):
        fresh.load_run_metadata(run_id="r_bad_integrity", run_dir=run_dir)
    assert not fresh.exists("aid_bad_integrity")


def test_load_run_metadata_legacy_without_integrity_file_still_loads(
    repo: ArtifactRepository,
    tmp_path: Path,
):
    """FOR-14:旧 run 没有 integrity 文件时保持兼容,且 load 不 backfill。"""
    repo.put(
        artifact_id="aid_legacy",
        value={"x": 1},
        artifact_type=_text_type(),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="r_legacy", step_id="s1"),
    )
    run_dir = tmp_path / "run_dir_legacy"
    repo.dump_run_metadata(run_id="r_legacy", run_dir=run_dir)
    integrity_path = run_dir / "_artifacts.integrity.json"
    integrity_path.unlink()

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    loaded = fresh.load_run_metadata(run_id="r_legacy", run_dir=run_dir)

    assert loaded == 1
    assert fresh.exists("aid_legacy")
    assert not integrity_path.exists(), "resume load 不应为 legacy run 自动 backfill"
