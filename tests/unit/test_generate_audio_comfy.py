"""GenerateAudioExecutor comfy/local-audio dispatch fences.

OpenSpec change comfy-agent-cli-audio-adoption Phase 2 — executor layer fences
(commit 4 of 13 per execution_plan)。

Per spec/probe-and-validation/spec.md + spec/provider-routing/spec.md named tests:
- _should_use_comfy_worker_path(F-Plan-R5-A round-5)
- _generate_via_comfy_worker(F2 round-1 三 except 块 + F-Plan-R7-B round-7 _should_retry honor retry_on)
- ComfyWorker → AudioWorker 异常 wrap(F2)
- AudioCandidate persistence(F-Plan-R6-A round-6 shape="waveform" + F-Plan-R7-A metadata single-source)
- ADR-007 边界(本地 audio non-premium → 内部 retry)

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
from framework.providers.workers.audio_worker import (
    AudioCandidate,
    AudioWorkerError,
    AudioWorkerTimeout,
    AudioWorkerUnsupportedResponse,
)
from framework.providers.workers.comfy_worker import (
    WorkerError as _ComfyWorkerError,
    WorkerTimeout as _ComfyWorkerTimeout,
    WorkerUnsupportedResponse as _ComfyWorkerUnsupportedResponse,
)
from framework.runtime.executors.base import StepContext
from framework.runtime.executors.generate_audio import (
    GenerateAudioExecutor,
    _should_retry,
)


# ---- Fixtures ---------------------------------------------------------------


def _make_audio_ctx(
    tmp_path: Path,
    run_id: str = "run_comfy_audio",
    *,
    num_candidates: int = 1,
    use_comfy_local_audio_route: bool = True,
    retry_policy: RetryPolicy | None = None,
) -> tuple[StepContext, ArtifactRepository]:
    """构造 comfy/local-audio 路由的 StepContext + repo。"""
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    routes: list[PreparedRoute] = []
    if use_comfy_local_audio_route:
        routes.append(PreparedRoute(
            model="comfy/local-audio", api_key_env=None, api_base=None,
            kind="audio", pricing=None,
        ))
    policy = ProviderPolicy(
        capability_required="audio.t2a",
        prepared_routes=routes,
    )
    step = Step(
        step_id="step_audio", type=StepType.generate, name="audio",
        risk_level=RiskLevel.medium, capability_ref="audio.t2a",
        config={
            "num_candidates": num_candidates,
            "seed": 42,
            "worker_timeout_s": 300,
            "spec": {
                "comfy_workflow": "Audio_Workflows/audio_stable_audio_example",
                "comfy_params": {"text": "uplifting electronic dance"},
                "comfy_lifecycle": "none",
            },
        },
        provider_policy=policy,
        retry_policy=retry_policy,
    )
    task = Task(
        task_id="t", task_type=TaskType.asset_generation,
        run_mode=RunMode.basic_llm, title="audio",
        input_payload={}, expected_output={}, project_id="proj_audio",
    )
    run = Run(
        run_id=run_id, task_id="t", project_id="proj_audio",
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


def _fake_audio_candidate(format_: str = "flac") -> AudioCandidate:
    """Construct a deterministic AudioCandidate for repo.put fences。"""
    if format_ == "flac":
        data = b"fLaC" + b"\x80\x00\x00\x22" + b"\x00" * 50
    elif format_ == "mp3":
        data = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 50
    elif format_ == "wav":
        data = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVE" + b"\x00" * 50
    else:
        data = b"\x00" * 64
    return AudioCandidate(
        data=data,
        format=format_,  # type: ignore[arg-type]
        metadata={
            "comfy_manifest": "Audio_Workflows/audio_stable_audio_example",
            "comfy_params_snapshot": {"text": "uplifting"},
            "comfy_capability": "audio",
            "comfy_original_filename": f"out.{format_}",
            "comfy_subprocess_run_metadata": {"exit_code": 0, "project_id": "proj_audio"},
        },
        duration_seconds=None,
        sample_rate=None,
    )


# ---- Executor dispatch ------------------------------------------------------


def test_should_use_comfy_worker_path_returns_true_for_comfy_local_audio_route(tmp_path):
    """F-Plan-R5-A round-5:detect `model == 'comfy/local-audio'` in prepared_routes。"""
    ctx, _ = _make_audio_ctx(tmp_path)
    executor = GenerateAudioExecutor()
    assert executor._should_use_comfy_worker_path(ctx) is True


def test_should_use_comfy_worker_path_returns_false_when_no_comfy_local_audio(tmp_path):
    """no comfy/local-audio in prepared_routes → returns False。"""
    ctx, _ = _make_audio_ctx(tmp_path, use_comfy_local_audio_route=False)
    executor = GenerateAudioExecutor()
    assert executor._should_use_comfy_worker_path(ctx) is False


async def test_executor_dispatches_comfy_local_audio_to_comfy_worker_branch(tmp_path, monkeypatch):
    """End-to-end:executor.execute → ComfyAgentWorker.generate_audio called。
    Mock at `subprocess.run` boundary(沿 mesh test 同款模式)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    fake = tmp_path / "out.flac"
    fake.write_bytes(b"fLaC" + b"\x80\x00\x00\x22" + b"\x00" * 50)
    ctx, _ = _make_audio_ctx(tmp_path)
    executor = GenerateAudioExecutor()
    import asyncio
    import json

    # TBD-010 Task 3: generate_audio 现在走 asyncio.create_subprocess_exec
    _stdout = json.dumps({
        "ok": True,
        "outputs": {"audio": [str(fake)], "images": [], "glb": [], "video": []},
    }).encode("utf-8")
    call_count = []

    class _FakeProc:
        returncode = 0
        async def communicate(self): return (_stdout, b"")
        async def wait(self): return 0
        def terminate(self): pass
        def kill(self): pass

    _orig = asyncio.create_subprocess_exec
    async def _fake_create(*a, **kw):
        call_count.append(1)
        return _FakeProc()
    asyncio.create_subprocess_exec = _fake_create  # type: ignore[assignment]
    try:
        # Task 5 RED: executor.execute 已转为 async def,需 await
        result = await executor.execute(ctx)
    finally:
        asyncio.create_subprocess_exec = _orig  # type: ignore[assignment]
    assert result.metrics["audio_count"] == 1
    assert result.metrics["model"] == "comfy/local-audio"
    assert len(call_count) == 1


async def test_executor_no_audio_worker_path_resolved_raises(tmp_path):
    """无 comfy/local-audio 路由 + 无 injected worker → raise AudioWorkerUnsupportedResponse。"""
    ctx, _ = _make_audio_ctx(tmp_path, use_comfy_local_audio_route=False)
    executor = GenerateAudioExecutor()  # no worker
    with pytest.raises(AudioWorkerUnsupportedResponse, match=r"no audio worker path"):
        await executor.execute(ctx)


# ---- F2 round-1 三 except 块 + F-Plan-R7-B round-7 _should_retry honor retry_on


async def test_generate_via_comfy_worker_wraps_worker_timeout_to_audio_worker_timeout_on_exhaustion(tmp_path, monkeypatch):
    """F2 round-1:ComfyWorkerTimeout → AudioWorkerTimeout (with `from exc`) on exhausted attempts。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    # retry_on 含 "timeout" + max_attempts=2 → 应 retry 一次后抛
    policy = RetryPolicy(max_attempts=2, retry_on=["timeout", "provider_error"])
    ctx, _ = _make_audio_ctx(tmp_path, retry_policy=policy)
    executor = GenerateAudioExecutor()
    with patch("framework.runtime.executors.generate_audio.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        # Task 5 RED: executor 转 async 后调 agenerate_audio,mock 需同步更新
        worker_inst.generate_audio.side_effect = _ComfyWorkerTimeout("subprocess hit 300s")
        cls_mock.return_value = worker_inst
        with pytest.raises(AudioWorkerTimeout) as exc_info:
            await executor.execute(ctx)
    # __cause__ chain should preserve original ComfyWorkerTimeout
    assert isinstance(exc_info.value.__cause__, _ComfyWorkerTimeout)
    # max_attempts=2 → 2 calls
    assert worker_inst.generate_audio.call_count == 2


async def test_generate_via_comfy_worker_wraps_worker_unsupported_to_audio_worker_unsupported_immediately(tmp_path, monkeypatch):
    """F2 round-1:ComfyWorkerUnsupportedResponse → AudioWorkerUnsupportedResponse 立即 raise(deterministic 不 retry)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    policy = RetryPolicy(max_attempts=3, retry_on=["timeout", "provider_error"])
    ctx, _ = _make_audio_ctx(tmp_path, retry_policy=policy)
    executor = GenerateAudioExecutor()
    with patch("framework.runtime.executors.generate_audio.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_audio.side_effect = _ComfyWorkerUnsupportedResponse("outputs.audio missing")
        cls_mock.return_value = worker_inst
        with pytest.raises(AudioWorkerUnsupportedResponse) as exc_info:
            await executor.execute(ctx)
    assert isinstance(exc_info.value.__cause__, _ComfyWorkerUnsupportedResponse)
    # Deterministic 不 retry — 1 call only
    assert worker_inst.generate_audio.call_count == 1


async def test_generate_via_comfy_worker_wraps_generic_worker_error_immediately(tmp_path, monkeypatch):
    """F2 round-1:ComfyWorkerError(generic)→ AudioWorkerError 立即 raise。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    policy = RetryPolicy(max_attempts=3, retry_on=["timeout", "provider_error"])
    ctx, _ = _make_audio_ctx(tmp_path, retry_policy=policy)
    executor = GenerateAudioExecutor()
    with patch("framework.runtime.executors.generate_audio.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_audio.side_effect = _ComfyWorkerError("subprocess crashed")
        cls_mock.return_value = worker_inst
        with pytest.raises(AudioWorkerError) as exc_info:
            await executor.execute(ctx)
    assert isinstance(exc_info.value.__cause__, _ComfyWorkerError)
    assert worker_inst.generate_audio.call_count == 1


async def test_local_comfy_audio_executor_retry_on_excludes_timeout_short_circuits_first_attempt(tmp_path, monkeypatch):
    """F-Plan-R7-B round-7:RetryPolicy.retry_on 不含 "timeout" → 即使 timeout exhaust 也 1 call。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    # retry_on=["provider_error"] 不含 "timeout" → _should_retry returns False
    policy = RetryPolicy(max_attempts=3, retry_on=["provider_error"])
    ctx, _ = _make_audio_ctx(tmp_path, retry_policy=policy)
    executor = GenerateAudioExecutor()
    with patch("framework.runtime.executors.generate_audio.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_audio.side_effect = _ComfyWorkerTimeout("first call timeout")
        cls_mock.return_value = worker_inst
        with pytest.raises(AudioWorkerTimeout):
            await executor.execute(ctx)
    # retry_on 不含 timeout → 1 call only(F-Plan-R7-B short-circuit)
    assert worker_inst.generate_audio.call_count == 1


# ---- Persistence(F-Plan-R6-A round-6 shape="waveform" + F-Plan-R7-A metadata)


async def test_executor_persists_audio_artifact_with_shape_waveform_and_format_aware_file_suffix(tmp_path, monkeypatch):
    """F-Plan-R6-A round-6 critical:Artifact.artifact_type.shape == "waveform"
    (与 UE bridge `_KIND_MAP[("audio", "waveform")] = "sound_wave"` 唯一映射对齐);
    file_suffix=`.{cand.format}` 反映真实 payload 编码。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    ctx, repo = _make_audio_ctx(tmp_path)
    executor = GenerateAudioExecutor()
    cand = _fake_audio_candidate(format_="flac")
    with patch("framework.runtime.executors.generate_audio.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_audio.return_value = [cand]
        cls_mock.return_value = worker_inst
        result = await executor.execute(ctx)
    assert len([a.artifact_id for a in result.artifacts]) == 1
    art = repo.get([a.artifact_id for a in result.artifacts][0])
    assert isinstance(art, Artifact)
    # F-Plan-R6-A:shape="waveform"(NOT "flac")
    assert art.artifact_type.modality == "audio"
    assert art.artifact_type.shape == "waveform"
    # PayloadRef.file_path extension = `.flac`(实际 payload bytes 格式)
    assert art.payload_ref.file_path is not None
    assert art.payload_ref.file_path.endswith(".flac")


async def test_executor_artifact_top_level_metadata_includes_format_duration_sample_rate(tmp_path, monkeypatch):
    """F-Plan-R7-A round-7 single-source + FR-STORE-004 audio metadata 三件套:
    Artifact.metadata.format=cand.format;duration_seconds/sample_rate=None always。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    ctx, repo = _make_audio_ctx(tmp_path)
    executor = GenerateAudioExecutor()
    cand = _fake_audio_candidate(format_="mp3")
    with patch("framework.runtime.executors.generate_audio.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        worker_inst.generate_audio.return_value = [cand]
        cls_mock.return_value = worker_inst
        result = await executor.execute(ctx)
    art = repo.get([a.artifact_id for a in result.artifacts][0])
    # FR-STORE-004 audio metadata triplet on Artifact.metadata
    assert art.metadata["format"] == "mp3"
    assert art.metadata["duration_seconds"] is None
    assert art.metadata["sample_rate"] is None
    # worker_metadata 5 个 comfy_* keys(F-Plan-R7-A single-source)
    wm = art.metadata["worker_metadata"]
    assert wm["comfy_manifest"] == "Audio_Workflows/audio_stable_audio_example"
    assert wm["comfy_capability"] == "audio"
    # worker_metadata 不重复 audio metadata 字段(F-Plan-R7-A守门)
    forbidden = {"duration_seconds", "sample_rate", "format", "format_detected"}
    leaked = forbidden & wm.keys()
    assert not leaked, f"worker_metadata leaked top-level audio fields: {leaked}"


# ---- ADR-007 边界(本地 audio non-premium → 内部 retry allowed)


async def test_local_comfy_audio_pricing_none_treated_as_non_premium(tmp_path, monkeypatch):
    """ADR-007 边界:`pricing=None` → `(None or {}).get("per_task_usd", 0) == 0` → non-premium
    → 内部 retry loop 用 `policy.max_attempts` 不受 ADR-007 strict-single-attempt 约束。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path / "scripts"))
    (tmp_path / "scripts" / "comfyui_api").mkdir(parents=True)
    policy = RetryPolicy(max_attempts=3, retry_on=["timeout"])
    ctx, _ = _make_audio_ctx(tmp_path, retry_policy=policy)
    # Confirm route pricing=None
    assert ctx.step.provider_policy.prepared_routes[0].pricing is None
    executor = GenerateAudioExecutor()
    with patch("framework.runtime.executors.generate_audio.ComfyAgentWorker") as cls_mock:
        worker_inst = MagicMock()
        # 第一次 timeout,第二次成功(retry budget 起作用)
        worker_inst.generate_audio.side_effect = [
            _ComfyWorkerTimeout("first call timeout"),
            [_fake_audio_candidate()],
        ]
        cls_mock.return_value = worker_inst
        result = await executor.execute(ctx)
    assert worker_inst.generate_audio.call_count == 2  # retry happened
    assert len([a.artifact_id for a in result.artifacts]) == 1


# ---- _should_retry helper ---------------------------------------------------


def test_should_retry_returns_true_for_audio_timeout_with_timeout_in_retry_on():
    """`_should_retry(policy, AudioWorkerTimeout)` returns True iff "timeout" ∈ retry_on。"""
    policy = RetryPolicy(max_attempts=2, retry_on=["timeout", "provider_error"])
    assert _should_retry(policy, AudioWorkerTimeout("x")) is True


def test_should_retry_returns_false_for_audio_timeout_when_timeout_not_in_retry_on():
    """`_should_retry(policy, AudioWorkerTimeout)` returns False when "timeout" ∉ retry_on。"""
    policy = RetryPolicy(max_attempts=2, retry_on=["provider_error"])
    assert _should_retry(policy, AudioWorkerTimeout("x")) is False


def test_should_retry_returns_false_for_audio_unsupported():
    """`_should_retry(policy, AudioWorkerUnsupportedResponse)` always returns False
    (deterministic 不 retry per F2 design)。"""
    policy = RetryPolicy(max_attempts=2, retry_on=["timeout", "provider_error", "schema_fail"])
    # _should_retry only handles AudioWorkerTimeout positively; unsupported / generic returns False
    assert _should_retry(policy, AudioWorkerUnsupportedResponse("x")) is False
