"""TBD-012 repo.put streaming zero-copy 路径单元 fence。"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.artifact_store.hashing import hash_path, hash_payload
from framework.core.artifact import ArtifactType, ProducerRef
from framework.core.enums import ArtifactRole, PayloadKind


def _video_type() -> ArtifactType:
    return ArtifactType(modality="video", shape="mp4", display_name="video_asset")


def _producer() -> ProducerRef:
    return ProducerRef(run_id="r1", step_id="s1", provider="test", model="zero-copy")


@pytest.fixture
def repo(tmp_path: Path) -> ArtifactRepository:
    reg = get_backend_registry(artifact_root=str(tmp_path / "store"))
    return ArtifactRepository(backend_registry=reg)


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    src = tmp_path / "video.mp4"
    src.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\xA5" * (8 * 1024 * 1024 - 16))
    return src


def test_zero_copy_writes_byte_equal_and_hash_match(repo, source_file):
    art = repo.put(
        artifact_id="aid_video",
        source_path=source_file,
        artifact_type=_video_type(),
        role=ArtifactRole.intermediate,
        format="mp4",
        mime_type="video/mp4",
        payload_kind=PayloadKind.file,
        producer=_producer(),
        file_suffix=".mp4",
    )
    # D9 D-HashSource-vs-Dest invariant:hash / size_bytes 同源 dest 文件
    backend = repo.backend_registry.get(PayloadKind.file)
    dest_abs = backend.absolute_path(art.payload_ref)

    assert art.payload_ref.kind == PayloadKind.file
    assert art.payload_ref.size_bytes == dest_abs.stat().st_size
    assert art.hash == hash_path(dest_abs)
    # byte-equal scenario:source 与 dest hash 一致
    assert hash_path(dest_abs) == hash_path(source_file)
    written = dest_abs.read_bytes()
    assert written == source_file.read_bytes()


def test_value_and_source_path_mutually_exclusive(repo, source_file):
    with pytest.raises(ValueError, match="mutually exclusive"):
        repo.put(
            artifact_id="aid",
            value=b"x",
            source_path=source_file,
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.file,
            producer=_producer(),
        )


def test_neither_value_nor_source_path_raises(repo):
    with pytest.raises(ValueError, match="requires either value or source_path"):
        repo.put(
            artifact_id="aid",
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.file,
            producer=_producer(),
        )


def test_explicit_value_none_preserved_as_inline_null_payload(repo):
    """R2-F3 D10 D-NullValueAmbiguity fence:value=None 是合法 inline JSON null payload。"""
    inline_type = ArtifactType(
        modality="text", shape="structured", display_name="null_payload",
    )
    art = repo.put(
        artifact_id="aid_null",
        value=None,
        artifact_type=inline_type,
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=_producer(),
    )
    assert art.payload_ref.kind == PayloadKind.inline
    assert art.payload_ref.inline_value is None
    assert art.hash == hash_payload(None)


def test_source_path_requires_file_kind(repo, source_file):
    with pytest.raises(ValueError, match="payload_kind=file"):
        repo.put(
            artifact_id="aid",
            source_path=source_file,
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.inline,
            producer=_producer(),
        )


def test_zero_copy_uses_hash_path_not_hash_payload(repo, source_file):
    import framework.artifact_store.repository as repo_mod
    with patch.object(repo_mod, "hash_payload", side_effect=AssertionError(
        "hash_payload SHALL NOT be invoked on source_path branch"
    )):
        art = repo.put(
            artifact_id="aid_video2",
            source_path=source_file,
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.file,
            producer=_producer(),
            file_suffix=".mp4",
        )
    backend = repo.backend_registry.get(PayloadKind.file)
    dest_abs = backend.absolute_path(art.payload_ref)
    assert art.hash == hash_path(dest_abs)


def test_source_modified_between_stat_and_copy_hashes_dest_not_source(repo, tmp_path):
    """F1 codex finding fence:source 被并发改时,Artifact.hash / size_bytes 取 dest。"""
    src = tmp_path / "racing.bin"
    original = b"original-payload-A" * 1024  # 18 KB
    modified = b"modified-payload-B" * 768   # ~14 KB
    src.write_bytes(original)

    import shutil as _shutil
    real_copyfile = _shutil.copyfile

    def racing_copyfile(s, d, **kwargs):
        src.write_bytes(modified)
        return real_copyfile(s, d, **kwargs)

    import framework.artifact_store.payload_backends.file_backend as fb_mod
    with patch.object(fb_mod.shutil, "copyfile", side_effect=racing_copyfile):
        art = repo.put(
            artifact_id="aid_race",
            source_path=src,
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.file,
            producer=_producer(),
            file_suffix=".mp4",
        )

    backend = repo.backend_registry.get(PayloadKind.file)
    dest_abs = backend.absolute_path(art.payload_ref)
    assert dest_abs.read_bytes() == modified, "落盘 bytes 应是 copy 时刻的 source(modified)"
    assert art.hash == hash_path(dest_abs)
    assert art.payload_ref.size_bytes == dest_abs.stat().st_size
    assert art.hash != hash_payload(original), "hash 不应来自被替换前的 source 内容"
