"""Audio worker baseline fences(commit 1 of comfy-agent-cli-audio-adoption).

Fences per `tasks.md` §2.6 + `specs/probe-and-validation/spec.md`
"AudioWorker ABC contract (test_audio_worker.py, NEW file)" Requirement:
- `test_audio_worker_abc_requires_generate_audio`
- `test_audio_candidate_format_whitelist`
- `test_audio_worker_exception_tree_inheritance`
- `test_fake_audio_worker_returns_minimal_valid_flac_bytes`
- `test_fake_audio_worker_respects_num_candidates_parameter`

F-Plan-R7-A round-7 plan 修订:加 1 fence 守 single-source metadata
(`test_audio_candidate_metadata_does_not_duplicate_top_level_audio_fields`)。
"""
from __future__ import annotations

import pytest

from framework.providers.workers.audio_worker import (
    AudioCandidate,
    AudioWorker,
    AudioWorkerError,
    AudioWorkerTimeout,
    AudioWorkerUnsupportedResponse,
    FakeAudioWorker,
)


def test_audio_worker_abc_requires_generate_audio() -> None:
    """Concrete subclass missing `generate_audio` cannot be instantiated."""

    class IncompleteAudioWorker(AudioWorker):
        # Intentionally omits generate_audio
        pass

    with pytest.raises(TypeError, match="generate_audio"):
        IncompleteAudioWorker()  # type: ignore[abstract]


def test_audio_candidate_format_whitelist() -> None:
    """`AudioCandidate.format` SHALL be one of {"flac", "mp3", "wav"}.

    Note:dataclass with `Literal` annotation 不在 runtime 强制校验(Python 不检查
    Literal 类型),实际守门由 ComfyAgentWorker.generate_audio 在 read_bytes 后
    raise WorkerUnsupportedResponse 完成(test_comfy_subprocess.py
    test_generate_audio_unsupported_extension_ogg_raises_unsupported_response 守门)。
    本 fence 验证 dataclass 接受 3 个 valid format 字符串构造成功 — runtime 守门
    在 `ComfyAgentWorker.generate_audio` 层。
    """
    for fmt in ("flac", "mp3", "wav"):
        cand = AudioCandidate(data=b"fake bytes", format=fmt)  # type: ignore[arg-type]
        assert cand.format == fmt
        assert cand.duration_seconds is None
        assert cand.sample_rate is None


def test_audio_worker_exception_tree_inheritance() -> None:
    """`AudioWorkerTimeout` / `AudioWorkerUnsupportedResponse` 都 subclass `AudioWorkerError`。"""
    assert issubclass(AudioWorkerTimeout, AudioWorkerError)
    assert issubclass(AudioWorkerUnsupportedResponse, AudioWorkerError)
    # And both are RuntimeError subclasses (per dataclass)
    assert issubclass(AudioWorkerError, RuntimeError)
    assert issubclass(AudioWorkerTimeout, RuntimeError)
    assert issubclass(AudioWorkerUnsupportedResponse, RuntimeError)


def test_fake_audio_worker_returns_minimal_valid_flac_bytes() -> None:
    """`FakeAudioWorker.generate_audio` 默认产 minimal valid FLAC bytes(magic `fLaC`)。"""
    worker = FakeAudioWorker()
    cands = worker.generate_audio(
        spec={"comfy_workflow": "test", "comfy_params": {"text": "hello"}},
        num_candidates=1,
        seed=42,
        timeout_s=30.0,
    )
    assert len(cands) == 1
    cand = cands[0]
    assert cand.format == "flac"
    # FLAC magic bytes per RFC 9639
    assert cand.data[:4] == b"fLaC", f"FakeAudioWorker should produce FLAC magic, got {cand.data[:8]!r}"
    # STREAMINFO METADATA_BLOCK header(last-block flag + type 0 + length 34)
    assert cand.data[4:8] == b"\x80\x00\x00\x22", "Expected STREAMINFO METADATA_BLOCK header"
    # Must be non-empty + reasonable size(magic 4 + header 4 + STREAMINFO 34 + frame ≤ 10)
    assert 40 < len(cand.data) < 200, f"Expected ~40-200 bytes, got {len(cand.data)}"
    # Provenance metadata 标 fake
    assert cand.metadata.get("is_fake") is True
    assert cand.duration_seconds is None
    assert cand.sample_rate is None


def test_fake_audio_worker_respects_num_candidates_parameter() -> None:
    """`FakeAudioWorker.generate_audio(num_candidates=N)` 返回 N 个 candidates,seed 递增。"""
    worker = FakeAudioWorker()
    cands = worker.generate_audio(
        spec={"comfy_workflow": "test", "comfy_params": {"text": "hello"}},
        num_candidates=3,
        seed=100,
        timeout_s=30.0,
    )
    assert len(cands) == 3
    # Each candidate has fake_seed = base + i
    seeds = [c.metadata["fake_seed"] for c in cands]
    assert seeds == [100, 101, 102], f"Expected [100,101,102], got {seeds}"
    # Each candidate has FLAC magic
    for c in cands:
        assert c.data[:4] == b"fLaC"
        assert c.format == "flac"


def test_audio_candidate_metadata_does_not_duplicate_top_level_audio_fields() -> None:
    """F-Plan-R7-A round-7 single-source守门:`AudioCandidate.metadata` SHALL NOT
    contain keys `duration_seconds` / `sample_rate` / `format` / `format_detected`;
    those values live on top-level dataclass fields. This prevents double-source bugs
    where executor `repo.put` would not know whether to read `cand.duration_seconds`
    or `cand.metadata['duration_seconds']`."""

    # 1. FakeAudioWorker default candidates 不放这些 keys 进 metadata
    worker = FakeAudioWorker()
    cands = worker.generate_audio(
        spec={"comfy_workflow": "test", "comfy_params": {}},
        num_candidates=2,
    )
    forbidden_keys = {"duration_seconds", "sample_rate", "format", "format_detected"}
    for cand in cands:
        leaked = forbidden_keys & cand.metadata.keys()
        assert not leaked, (
            f"AudioCandidate.metadata MUST NOT contain top-level audio field keys "
            f"(F-Plan-R7-A single-source); leaked: {leaked}"
        )

    # 2. 直接构造的 AudioCandidate metadata 字典也不应有(by convention; 由 worker 写,
    #    但此 fence 守门 ComfyAgentWorker.generate_audio 实装时不能往 metadata 塞 audio
    #    metadata fields — 真实校验在 commit 3 ComfyAgentWorker.generate_audio fence)
    cand = AudioCandidate(
        data=b"fLaC\x80\x00\x00\x22" + b"\x00" * 50,
        format="flac",
        metadata={
            "comfy_manifest": "test",
            "comfy_params_snapshot": {},
            "comfy_capability": "audio",
            "comfy_original_filename": "ComfyUI_00001_.flac",
            "comfy_subprocess_run_metadata": {},
        },
        duration_seconds=None,
        sample_rate=None,
    )
    leaked = forbidden_keys & cand.metadata.keys()
    assert not leaked, f"Reference AudioCandidate construction leaked: {leaked}"
