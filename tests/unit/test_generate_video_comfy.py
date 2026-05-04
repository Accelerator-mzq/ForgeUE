"""GenerateVideoExecutor comfy/local-video dispatch fences.

OpenSpec change comfy-agent-cli-video-adoption Phase 3 — executor layer fences
(commit 5 of 16 per execution_plan)。

Per spec/probe-and-validation/spec.md + spec/provider-routing/spec.md named tests:
- _should_use_comfy_worker_path(沿 audio F-Plan-R5-A round-5 模式)
- _generate_via_comfy_worker(沿 audio F2 round-1 三 except 块 + F-Plan-R7-B round-7
  _should_retry honor retry_on)
- ComfyWorker → VideoWorker 异常 wrap(沿 audio F2)
- VideoCandidate persistence(D1 + D8:shape="mp4" UE bridge dispatch + 5 metadata None)
- ADR-007 边界(本地 video non-premium → 内部 retry)

14 fences covering executor dispatch + retry/wrap + persistence + UE bridge integration。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import Artifact, ArtifactType
from framework.core.enums import RiskLevel, RunMode, RunStatus, StepType, TaskType
from framework.core.policies import PreparedRoute, ProviderPolicy, RetryPolicy
from framework.core.task import Run, Step, Task
from framework.providers.workers.comfy_worker import (
    WorkerError as _ComfyWorkerError,
    WorkerTimeout as _ComfyWorkerTimeout,
    WorkerUnsupportedResponse as _ComfyWorkerUnsupportedResponse,
)
from framework.providers.workers.video_worker import (
    VideoCandidate,
    VideoWorkerError,
    VideoWorkerTimeout,
    VideoWorkerUnsupportedResponse,
)
from framework.runtime.executors.base import StepContext
from framework.runtime.executors.generate_video import (
    GenerateVideoExecutor,
    _should_retry,
)


# ---- Fixtures ---------------------------------------------------------------


def _make_video_ctx(
    tmp_path: Path,
    run_id: str = "run_comfy_video",
    *,
    num_candidates: int = 1,
    use_comfy_local_video_route: bool = True,
    retry_policy: RetryPolicy | None = None,
) -> tuple[StepContext, ArtifactRepository]:
    """构造 comfy/local-video 路由的 StepContext + repo(沿 audio _make_audio_ctx 模板)。"""
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    routes: list[PreparedRoute] = []
    if use_comfy_local_video_route:
        routes.append(PreparedRoute(
            model="comfy/local-video", api_key_env=None, api_base=None,
            kind="video", pricing=None,
        ))
    policy = ProviderPolicy(
        capability_required="video.t2v",
        prepared_routes=routes,
    )
    step = Step(
        step_id="step_video", type=StepType.generate, name="video",
        risk_level=RiskLevel.medium, capability_ref="video.t2v",
        config={
            "num_candidates": num_candidates,
            "seed": 5042,
            "worker_timeout_s": 600,  # D3 Wan T2V 7-min
            "spec": {
                "comfy_workflow": "Vedio/Wan2.1-T2V-1.3B_native_5sec",  # D5 上游拼写照实跟
                "comfy_params": {"positive_prompt": "uplifting space scene"},
                "comfy_lifecycle": "none",
            },
        },
        provider_policy=policy,
        retry_policy=retry_policy,
    )
    task = Task(
        task_id="t", task_type=TaskType.asset_generation,
        run_mode=RunMode.basic_llm, title="video",
        input_payload={}, expected_output={}, project_id="proj_video",
    )
    run = Run(
        run_id=run_id, task_id="t", project_id="proj_video",
        status=RunStatus.running,
        started_at=datetime.now(timezone.utc),
        workflow_id="w", trace_id="tr",
    )
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[],
        run_dir=tmp_path,
    )
    return ctx, repo


def _fake_video_candidate() -> VideoCandidate:
    """Construct a deterministic VideoCandidate for repo.put fences。

    Minimal valid BMFF mp4 bytes (32 bytes) — 通过 round-2 F4 + round-3 PF2 strict
    5-tuple,但 fence 不依赖 worker 层 BMFF 校验(executor fence 走 mock worker
    返回 candidate,不经过 _run_once_video)。
    """
    data = (
        b"\x00\x00\x00\x20" + b"ftyp" + b"isom" + b"\x00\x00\x02\x00"
        + b"isom" + b"iso2" + b"mp41" + b"mp42"
    )
    return VideoCandidate(
        data=data,
        format="mp4",
        metadata={
            "comfy_manifest": "Vedio/Wan2.1-T2V-1.3B_native_5sec",
            "comfy_params_snapshot": {"positive_prompt": "uplifting space scene"},
            "comfy_capability": "video",
            "comfy_original_filename": "wan21_test.mp4",
            "comfy_subprocess_run_metadata": {"exit_code": 0, "project_id": "proj_video"},
        },
        duration_seconds=None,
        frame_count=None,
        width=None,
        height=None,
        fps=None,
    )


# ---- Executor dispatch ------------------------------------------------------


def test_should_use_comfy_worker_path_returns_true_for_comfy_local_video_route(tmp_path):
    """D6:detect `model == 'comfy/local-video'` in prepared_routes。"""
    ctx, _ = _make_video_ctx(tmp_path)
    executor = GenerateVideoExecutor()
    assert executor._should_use_comfy_worker_path(ctx) is True


def test_should_use_comfy_worker_path_returns_false_when_no_comfy_local_video(tmp_path):
    """no comfy/local-video in prepared_routes → returns False。"""
    ctx, _ = _make_video_ctx(tmp_path, use_comfy_local_video_route=False)
    executor = GenerateVideoExecutor()
    assert executor._should_use_comfy_worker_path(ctx) is False


def test_executor_dispatches_comfy_local_video_to_comfy_worker_branch(tmp_path, monkeypatch):
    """End-to-end:executor.execute → ComfyAgentWorker.generate_video called。
    Mock at `subprocess.run` boundary(沿 audio test 同款模式)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    fake = tmp_path / "out.mp4"
    fake.write_bytes(
        b"\x00\x00\x00\x20" + b"ftyp" + b"isom" + b"\x00\x00\x02\x00"
        + b"isom" + b"iso2" + b"mp41" + b"mp42"
    )
    ctx, _ = _make_video_ctx(tmp_path)
    executor = GenerateVideoExecutor()
    import json
    import subprocess
    with patch("subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["mocked"], returncode=0,
            stdout=json.dumps({
                "ok": True,
                "outputs": {"images": [], "audio": [], "glb": [], "video": [str(fake)]},
            }),
            stderr="",
        )
        result = executor.execute(ctx)
    assert result.metrics["video_count"] == 1
    assert result.metrics["model"] == "comfy/local-video"
    assert run_mock.call_count == 1


def test_executor_no_video_worker_path_resolved_raises(tmp_path):
    """无 comfy/local-video 路由 + 无 injected worker → raise VideoWorkerUnsupportedResponse。"""
    ctx, _ = _make_video_ctx(tmp_path, use_comfy_local_video_route=False)
    executor = GenerateVideoExecutor()  # no worker
    with pytest.raises(VideoWorkerUnsupportedResponse, match=r"no video worker path"):
        executor.execute(ctx)


# ---- F2 round-1 三 except 块 + F-Plan-R7-B round-7 _should_retry honor retry_on


def test_generate_via_comfy_worker_wraps_worker_timeout_to_video_worker_timeout_on_exhaustion(tmp_path, monkeypatch):
    """沿 audio F2 round-1:ComfyWorkerTimeout → VideoWorkerTimeout (with `from exc`)
    on exhausted attempts。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    # retry_on 含 "timeout" + max_attempts=2 → 应 retry 一次后抛
    policy = RetryPolicy(max_attempts=2, retry_on=["timeout", "provider_error"])
    ctx, _ = _make_video_ctx(tmp_path, retry_policy=policy)
    executor = GenerateVideoExecutor()
    with patch("framework.runtime.executors.generate_video.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_video.side_effect = _ComfyWorkerTimeout("subprocess hit 600s")
        cls_mock.return_value = worker_inst
        with pytest.raises(VideoWorkerTimeout) as exc_info:
            executor.execute(ctx)
    # __cause__ chain should preserve original ComfyWorkerTimeout
    assert isinstance(exc_info.value.__cause__, _ComfyWorkerTimeout)
    # max_attempts=2 → 2 calls
    assert worker_inst.generate_video.call_count == 2


def test_generate_via_comfy_worker_wraps_worker_unsupported_to_video_worker_unsupported_immediately(tmp_path, monkeypatch):
    """沿 audio F2 round-1:ComfyWorkerUnsupportedResponse → VideoWorkerUnsupportedResponse
    立即 raise(deterministic 不 retry)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    policy = RetryPolicy(max_attempts=3, retry_on=["timeout", "provider_error"])
    ctx, _ = _make_video_ctx(tmp_path, retry_policy=policy)
    executor = GenerateVideoExecutor()
    with patch("framework.runtime.executors.generate_video.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_video.side_effect = _ComfyWorkerUnsupportedResponse("outputs.video missing")
        cls_mock.return_value = worker_inst
        with pytest.raises(VideoWorkerUnsupportedResponse) as exc_info:
            executor.execute(ctx)
    assert isinstance(exc_info.value.__cause__, _ComfyWorkerUnsupportedResponse)
    # Deterministic 不 retry — 1 call only
    assert worker_inst.generate_video.call_count == 1


def test_generate_via_comfy_worker_wraps_generic_worker_error_immediately(tmp_path, monkeypatch):
    """沿 audio F2 round-1:ComfyWorkerError(generic)→ VideoWorkerError 立即 raise。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    policy = RetryPolicy(max_attempts=3, retry_on=["timeout", "provider_error"])
    ctx, _ = _make_video_ctx(tmp_path, retry_policy=policy)
    executor = GenerateVideoExecutor()
    with patch("framework.runtime.executors.generate_video.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_video.side_effect = _ComfyWorkerError("subprocess crashed")
        cls_mock.return_value = worker_inst
        with pytest.raises(VideoWorkerError) as exc_info:
            executor.execute(ctx)
    assert isinstance(exc_info.value.__cause__, _ComfyWorkerError)
    assert worker_inst.generate_video.call_count == 1


def test_local_comfy_video_executor_retry_on_excludes_timeout_short_circuits_first_attempt(tmp_path, monkeypatch):
    """沿 audio F-Plan-R7-B round-7:RetryPolicy.retry_on 不含 "timeout" → 即使 timeout
    exhaust 也 1 call。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    # retry_on=["provider_error"] 不含 "timeout" → _should_retry returns False
    policy = RetryPolicy(max_attempts=3, retry_on=["provider_error"])
    ctx, _ = _make_video_ctx(tmp_path, retry_policy=policy)
    executor = GenerateVideoExecutor()
    with patch("framework.runtime.executors.generate_video.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_video.side_effect = _ComfyWorkerTimeout("first call timeout")
        cls_mock.return_value = worker_inst
        with pytest.raises(VideoWorkerTimeout):
            executor.execute(ctx)
    # retry_on 不含 timeout → 1 call only(F-Plan-R7-B short-circuit)
    assert worker_inst.generate_video.call_count == 1


# ---- Persistence(D1 + D8 shape="mp4" UE bridge + 5 metadata None)----------


def test_executor_persists_video_artifact_with_shape_mp4_and_format_aware_file_suffix(tmp_path, monkeypatch):
    """D1 + D8 critical:Artifact.artifact_type.shape == "mp4"(与 UE bridge
    `_KIND_MAP[("video", "mp4")] = "file_media_source"` 唯一映射对齐);
    file_suffix=`.{cand.format}` 反映真实 payload 编码(post-F2 sweep mp4-only =`.mp4`)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    ctx, repo = _make_video_ctx(tmp_path)
    executor = GenerateVideoExecutor()
    cand = _fake_video_candidate()
    with patch("framework.runtime.executors.generate_video.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_video.return_value = [cand]
        cls_mock.return_value = worker_inst
        result = executor.execute(ctx)
    assert len([a.artifact_id for a in result.artifacts]) == 1
    art = repo.get([a.artifact_id for a in result.artifacts][0])
    assert isinstance(art, Artifact)
    # D1 + D8:shape="mp4"(NOT "waveform" / "raster" / "gltf")
    assert art.artifact_type.modality == "video"
    assert art.artifact_type.shape == "mp4"
    # PayloadRef.file_path extension = `.mp4`(实际 payload bytes 格式)
    assert art.payload_ref.file_path is not None
    assert art.payload_ref.file_path.endswith(".mp4")


def test_executor_artifact_top_level_metadata_includes_format_5_video_metadata_fields(tmp_path, monkeypatch):
    """D8 single-source + FR-STORE-004 video metadata 6 件套(format + 5 video fields):
    Artifact.metadata.format=cand.format("mp4");5 video metadata 顶层全 None always
    (本 change scope ComfyUI agent CLI 不暴露 video metadata,follow-on `video-metadata-parser` 加 ffprobe / mutagen 解析)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    ctx, repo = _make_video_ctx(tmp_path)
    executor = GenerateVideoExecutor()
    cand = _fake_video_candidate()
    with patch("framework.runtime.executors.generate_video.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_video.return_value = [cand]
        cls_mock.return_value = worker_inst
        result = executor.execute(ctx)
    art = repo.get([a.artifact_id for a in result.artifacts][0])
    # FR-STORE-004 video metadata 6 件套 on Artifact.metadata
    assert art.metadata["format"] == "mp4"
    assert art.metadata["duration_seconds"] is None
    assert art.metadata["frame_count"] is None
    assert art.metadata["width"] is None
    assert art.metadata["height"] is None
    assert art.metadata["fps"] is None
    # worker_metadata 5 个 comfy_* keys(D8 single-source)
    wm = art.metadata["worker_metadata"]
    assert wm["comfy_manifest"] == "Vedio/Wan2.1-T2V-1.3B_native_5sec"
    assert wm["comfy_capability"] == "video"
    # worker_metadata 不重复 video metadata 字段(D8 守门)
    forbidden = {"duration_seconds", "frame_count", "width", "height", "fps", "format", "format_detected"}
    leaked = forbidden & wm.keys()
    assert not leaked, f"worker_metadata leaked top-level video fields: {leaked}"


# ---- ADR-007 边界(本地 video non-premium → 内部 retry allowed)


def test_local_comfy_video_pricing_none_treated_as_non_premium(tmp_path, monkeypatch):
    """ADR-007 边界:`pricing=None` → `(None or {}).get("per_task_usd", 0) == 0` → non-premium
    → 内部 retry loop 用 `policy.max_attempts` 不受 ADR-007 strict-single-attempt 约束。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    policy = RetryPolicy(max_attempts=3, retry_on=["timeout"])
    ctx, _ = _make_video_ctx(tmp_path, retry_policy=policy)
    # Confirm route pricing=None
    assert ctx.step.provider_policy.prepared_routes[0].pricing is None
    executor = GenerateVideoExecutor()
    with patch("framework.runtime.executors.generate_video.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        # 第一次 timeout,第二次成功(retry budget 起作用)
        worker_inst.generate_video.side_effect = [
            _ComfyWorkerTimeout("first call timeout"),
            [_fake_video_candidate()],
        ]
        cls_mock.return_value = worker_inst
        result = executor.execute(ctx)
    assert worker_inst.generate_video.call_count == 2  # retry happened
    assert len([a.artifact_id for a in result.artifacts]) == 1


# ---- _should_retry helper ---------------------------------------------------


def test_should_retry_returns_true_for_video_timeout_with_timeout_in_retry_on():
    """`_should_retry(policy, VideoWorkerTimeout)` returns True iff "timeout" ∈ retry_on
    (沿 audio _should_retry 同款逻辑)。"""
    policy = RetryPolicy(max_attempts=2, retry_on=["timeout", "provider_error"])
    assert _should_retry(policy, VideoWorkerTimeout("x")) is True


def test_should_retry_returns_false_for_video_timeout_when_timeout_not_in_retry_on():
    """`_should_retry(policy, VideoWorkerTimeout)` returns False when "timeout" ∉ retry_on。"""
    policy = RetryPolicy(max_attempts=2, retry_on=["provider_error"])
    assert _should_retry(policy, VideoWorkerTimeout("x")) is False


def test_should_retry_returns_false_for_video_unsupported():
    """`_should_retry(policy, VideoWorkerUnsupportedResponse)` always returns False
    (deterministic 不 retry per F2 design;沿 audio same)。"""
    policy = RetryPolicy(max_attempts=2, retry_on=["timeout", "provider_error", "schema_fail"])
    assert _should_retry(policy, VideoWorkerUnsupportedResponse("x")) is False
