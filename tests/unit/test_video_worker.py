"""VideoWorker baseline fence(L4 / unit)。

OpenSpec change `comfy-agent-cli-video-adoption` Phase 3 commit 2 — VideoWorker ABC +
VideoCandidate dataclass + 异常树 + FakeVideoWorker。

Round-2 F2 + round-3 PF3 sweep:`format: Literal["mp4"]` mp4-only。
Round-3 PF4 修订:Python `@dataclass` 不在 runtime enforce Literal,实际 mp4-only
enforcement 在 worker 层 `_run_once_video` 扩展名检查 + BMFF strict header validation
(沿 audio Phase 2 `tests/unit/test_audio_worker.py::test_audio_candidate_format_whitelist`
同款分层 enforcement 模式)。
"""
from __future__ import annotations

import pytest

from framework.providers.workers import (
    FakeVideoWorker,
    VideoCandidate,
    VideoWorker,
    VideoWorkerError,
    VideoWorkerTimeout,
    VideoWorkerUnsupportedResponse,
)


# ----------------------------------------------------------------------------
# VideoWorker ABC contract
# ----------------------------------------------------------------------------


def test_video_worker_abc_requires_generate_video() -> None:
    """`VideoWorker` 是 ABC,具体子类 omit `generate_video` 实现 → TypeError on
    instantiation(Python ABC 强制检查)。
    """

    class IncompleteWorker(VideoWorker):
        pass  # 故意不实现 generate_video

    with pytest.raises(TypeError, match="generate_video"):
        IncompleteWorker()  # type: ignore[abstract]


def test_video_candidate_format_mp4_accepted_dataclass_does_not_runtime_enforce_literal() -> None:
    """`VideoCandidate.format` Literal["mp4"] mp4-only(round-2 F2 + round-3 PF3 sweep)。

    Round-3 PF4 修订关键(沿 audio Phase 2 同款行为):
    - Python `@dataclass` 不在 runtime 强制 `Literal` 类型注解(只是 type hint)
    - dataclass accepts `format="mp4"` AND non-Literal strings (`"webm"` / `"mov"`)
      at construction WITHOUT raising
    - 实际 mp4-only enforcement 在 worker 层 `_run_once_video` 扩展名检查 + BMFF strict
      header validation(`tests/unit/test_comfy_subprocess.py::test_generate_video_unsupported_extension_mov_raises_unsupported_response`
      + `..._webm_extension_rejected_pending_follow_on` 守门 worker 层行为)
    - 沿 audio Phase 2 `tests/unit/test_audio_worker.py::test_audio_candidate_format_whitelist`
      已显式记录的同款分层 enforcement 模式
    """
    # mp4 (valid Literal value) accepted
    cand_mp4 = VideoCandidate(data=b"fake bytes", format="mp4")
    assert cand_mp4.format == "mp4"
    assert cand_mp4.duration_seconds is None
    assert cand_mp4.frame_count is None
    assert cand_mp4.width is None
    assert cand_mp4.height is None
    assert cand_mp4.fps is None

    # webm / mov (NOT in Literal["mp4"]) — dataclass 仍 accept(Python 不 enforce
    # Literal at runtime);worker 层 enforcement 在 _run_once_video 扩展名检查
    cand_webm = VideoCandidate(data=b"fake bytes", format="webm")  # type: ignore[arg-type]
    assert cand_webm.format == "webm"  # dataclass accepts whatever string
    cand_mov = VideoCandidate(data=b"fake bytes", format="mov")  # type: ignore[arg-type]
    assert cand_mov.format == "mov"


def test_video_worker_exception_tree_inheritance() -> None:
    """`VideoWorkerTimeout` / `VideoWorkerUnsupportedResponse` 都 subclass
    `VideoWorkerError`(D14 priority 守门依赖此继承 — FailureModeMap.from_exception
    isinstance check `VideoWorkerError` catches both)。
    """
    assert issubclass(VideoWorkerTimeout, VideoWorkerError)
    assert issubclass(VideoWorkerUnsupportedResponse, VideoWorkerError)
    # And both are RuntimeError subclasses
    assert issubclass(VideoWorkerError, RuntimeError)
    assert issubclass(VideoWorkerTimeout, RuntimeError)
    assert issubclass(VideoWorkerUnsupportedResponse, RuntimeError)


# ----------------------------------------------------------------------------
# FakeVideoWorker 行为
# ----------------------------------------------------------------------------


def test_fake_video_worker_returns_minimal_valid_mp4_bytes() -> None:
    """FakeVideoWorker 默认输出 minimal valid BMFF mp4 bytes,通过 round-2 F4 +
    round-3 PF2 BMFF strict 5-tuple 校验:

    1. `len(data) >= 16`(实际 32 bytes)
    2. `data[4:8] == b"ftyp"`
    3. `box_size in [8, len(data)]`(box_size = 32 = len(data),不 == 1)
    4. `data[8:12]` major_brand 非空非全 0 / 全 space(实际 = `b"isom"`)
    """
    worker = FakeVideoWorker()
    candidates = worker.generate_video(spec={}, num_candidates=1)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.format == "mp4"

    # BMFF strict 5-tuple 校验(沿 round-2 F4 + round-3 PF2 实施 BMFF strict)
    assert len(cand.data) >= 16, f"too short: {len(cand.data)} bytes"
    assert cand.data[4:8] == b"ftyp", f"ftyp mismatch: {cand.data[4:8]!r}"
    box_size = int.from_bytes(cand.data[0:4], "big")
    assert box_size != 1, "box_size==1 (largesize) deferred to follow-on"
    assert 8 <= box_size <= len(cand.data), f"box_size {box_size} out of range"
    major_brand = cand.data[8:12]
    assert major_brand != b"\x00\x00\x00\x00", "major_brand is all-zero"
    assert major_brand != b"    ", "major_brand is all-spaces"
    assert major_brand == b"isom", f"expected isom brand, got {major_brand!r}"


def test_fake_video_worker_respects_num_candidates_parameter() -> None:
    """`num_candidates=N` → 返回 list of length N,每个 candidate 都是 valid
    minimal mp4(沿 audio Phase 2 同款 per-candidate loop 行为)。
    """
    worker = FakeVideoWorker()
    for n in (1, 2, 3):
        candidates = worker.generate_video(spec={}, num_candidates=n)
        assert len(candidates) == n, f"num_candidates={n} → got {len(candidates)}"
        for i, cand in enumerate(candidates):
            assert cand.format == "mp4"
            assert cand.metadata.get("is_fake") is True
            assert cand.metadata.get("fake_index") == i


def test_fake_video_worker_program_returns_preset_candidates() -> None:
    """`program(candidates=...)` 注入预设 candidates;sweep-mirror of audio
    `FakeAudioWorker.program` 模式。
    """
    worker = FakeVideoWorker()
    preset = [VideoCandidate(data=b"preset", format="mp4", metadata={"injected": True})]
    worker.program(candidates=preset)
    result = worker.generate_video(spec={"some_key": "some_value"}, num_candidates=5)
    # Returns preset (NOT 5 minimal mp4s)
    assert result == preset
    # Call recorded
    assert len(worker.calls) == 1
    assert worker.calls[0]["spec"] == {"some_key": "some_value"}
    assert worker.calls[0]["num_candidates"] == 5


def test_fake_video_worker_program_raises_preset_error() -> None:
    """`program(raise_error=...)` 注入预设异常;Mock executor retry policy fence
    依赖此模式(类比 `FakeAudioWorker.program(raise_error=...)`)。
    """
    worker = FakeVideoWorker()
    worker.program(raise_error=VideoWorkerTimeout("simulated subprocess timeout"))
    with pytest.raises(VideoWorkerTimeout, match="simulated"):
        worker.generate_video(spec={}, num_candidates=1)
