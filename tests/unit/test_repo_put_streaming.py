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


def test_null_inline_payload_survives_resume(repo, tmp_path):
    """D10 + R3 resume seam fence:value=None inline payload 在 dump+load 全 round-trip 后仍存活。

    InlineBackend.exists() 当前实装 `return ref.inline_value is not None`,
    value=None 时返回 False → load_run_metadata 的 payload_present guard 把该 artifact
    误判为"不存在"并静默丢弃。
    正确实装应用 model_fields_set 区分"显式 None"vs"未设字段"。
    """
    from framework.artifact_store import ArtifactRepository

    inline_type = ArtifactType(modality="text", shape="structured", display_name="null_payload")
    art = repo.put(
        artifact_id="aid_null_resume",
        value=None,
        artifact_type=inline_type,
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_kind=PayloadKind.inline,
        producer=_producer(),
    )
    assert art.payload_ref.inline_value is None

    run_dir = tmp_path / "run_dir_null"
    repo.dump_run_metadata(run_id="r1", run_dir=run_dir)

    fresh = ArtifactRepository(backend_registry=repo.backend_registry)
    fresh._artifacts.clear()
    n = fresh.load_run_metadata(run_id="r1", run_dir=run_dir)
    assert n == 1, (
        "null inline artifact 应在 resume 后存活,而非被 payload_present guard 静默丢弃"
    )
    assert "aid_null_resume" in fresh._artifacts
    assert fresh._artifacts["aid_null_resume"].payload_ref.inline_value is None


@pytest.mark.skipif(
    os.environ.get("FORGEUE_RUN_HEAVY_FENCE") != "1",
    reason="FORGEUE_RUN_HEAVY_FENCE not set — opt-in heavy RSS fence",
)
def test_zero_copy_rss_bounded_200mb(tmp_path):
    """200 MB zero-copy 路径 RSS peak delta < 32 MB(D-FenceOpt-in + R5-F2 peak sampling)。

    Opt-in via FORGEUE_RUN_HEAVY_FENCE=1 — 200MB 临时文件创建 / 拷贝 / hash
    在 CI 慢,默认 skip;开发者 / 验收手动跑过守门 zero-copy 实质行为。
    """
    import psutil
    process = psutil.Process()

    # 创建 200 MB 源文件(分块写,避免一次性 200 MB in-memory)
    src = tmp_path / "big.bin"
    chunk = b"\xA5" * (8 * 1024 * 1024)
    with src.open("wb") as f:
        for _ in range(25):  # 25 * 8MB = 200 MB
            f.write(chunk)

    # R5-F2 D-PeakRSSSampling:后台 thread 50ms 采样 RSS 取 max,捕获瞬时峰值
    import threading
    import time as _time
    rss_before = process.memory_info().rss
    rss_peak = rss_before
    stop_sampling = threading.Event()

    def _sample_peak():
        nonlocal rss_peak
        while not stop_sampling.is_set():
            try:
                rss_peak = max(rss_peak, process.memory_info().rss)
            except psutil.Error:
                break
            _time.sleep(0.05)  # 50ms

    sampler = threading.Thread(target=_sample_peak, daemon=True)
    sampler.start()
    try:
        reg = get_backend_registry(artifact_root=str(tmp_path / "store"))
        repo = ArtifactRepository(backend_registry=reg)
        art = repo.put(
            artifact_id="aid_big",
            source_path=src,
            artifact_type=_video_type(),
            role=ArtifactRole.intermediate,
            format="mp4",
            mime_type="video/mp4",
            payload_kind=PayloadKind.file,
            producer=_producer(),
            file_suffix=".mp4",
        )
    finally:
        stop_sampling.set()
        sampler.join(timeout=2.0)

    rss_after = process.memory_info().rss
    rss_delta_mb = (rss_after - rss_before) / (1024 * 1024)
    rss_peak_delta_mb = (rss_peak - rss_before) / (1024 * 1024)
    rss_before_mb = rss_before / (1024 * 1024)
    rss_after_mb = rss_after / (1024 * 1024)
    rss_peak_mb = rss_peak / (1024 * 1024)

    # R2-F4 + R5-F2:输出 peak RSS,evidence 捕获真实数值
    print(
        f"\n[heavy-fence] RSS peak delta: {rss_peak_delta_mb:.2f} MB "
        f"(threshold < 32 MB; rss_before={rss_before_mb:.1f} MB, "
        f"rss_peak={rss_peak_mb:.1f} MB, rss_after={rss_after_mb:.1f} MB, "
        f"end_delta={rss_delta_mb:.2f} MB, payload=200 MB)"
    )

    assert art.payload_ref.size_bytes == 200 * 1024 * 1024
    # R5-F2:核心断言基于 peak,end_delta 仅诊断
    assert rss_peak_delta_mb < 32, (
        f"zero-copy RSS peak delta {rss_peak_delta_mb:.2f} MB exceeds 32 MB fence "
        f"(rss_before={rss_before_mb:.1f} MB, rss_peak={rss_peak_mb:.1f} MB, "
        f"rss_after={rss_after_mb:.1f} MB)"
    )
