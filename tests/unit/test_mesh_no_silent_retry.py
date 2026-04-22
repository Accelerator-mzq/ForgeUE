"""TBD-007 fences: mesh.generation 不允许任何静默重试 / 重发.

Background:
- 用户实测一次 a2_mesh live 跑(用户视角 1 个 mesh job)在腾讯云控制台扣
  16 调用 × 20 积分 = 320 积分。
- 三层 + 我漏的 1 层叠加重试:
  L1 transport `with_transient_retry_async(max_attempts=2)` 套 _apost  → ×2
  L2 executor 内部 for 循环 `policy.max_attempts` 调 worker.generate() → ×2(我漏的)
  L3 orchestrator `worker_timeout/error → retry_same_step/fallback_model` → ×2
  L4 download Range resume(只补缺字节,经济意义不同 — 不动)
- HYPOTHESIS 已 probe 验证(acceptance_report §6.6):客户端断开后 server 仍
  完成生成,blind retry 会双扣已完成 job。
- 修法:L1 + L2 + L3 全压。L1 是 test_transient_retry.py 里翻转的那条;
  本文件守 L2 + L3 三条 fence。
"""
from __future__ import annotations

import httpx
import pytest

from framework.providers.workers.mesh_worker import (
    HunyuanMeshWorker,
    MeshCandidate,
    MeshWorker,
    MeshWorkerError,
    MeshWorkerTimeout,
)
from framework.runtime.failure_mode_map import (
    DEFAULT_MAP,
    FailureMode,
    classify,
)
from framework.core.enums import Decision


# ---- L1 fence: _apost no transient retry (fast standalone version) -------


def _install_httpx_stub_minimal(monkeypatch, handler):
    """Lightweight transport patch — same shape as test_transient_retry.py
    helper but without the retry-helper sleep monkeypatch (we don't expect
    the sleep helper to fire any more)."""
    transport = httpx.MockTransport(handler)
    orig = httpx.AsyncClient

    class _Client(orig):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    from framework.providers.workers import mesh_worker as _mw
    monkeypatch.setattr(_mw.httpx, "AsyncClient", _Client)


def test_apost_no_transient_retry_on_connect_error(monkeypatch):
    """L1 fence: a single ConnectError on /submit must NOT trigger silent
    re-POST. Mirrors test_mesh_worker_does_NOT_retry_on_winerror_10060
    (test_transient_retry.py) but with simpler scaffolding so this fence
    can run even if the L1-helper module is later refactored."""
    attempts: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        attempts.append(str(req.url))
        raise httpx.ConnectError("All connection attempts failed")

    _install_httpx_stub_minimal(monkeypatch, handler)
    worker = HunyuanMeshWorker(api_key="sk-test", poll_interval_s=0.0)
    with pytest.raises(MeshWorkerError, match="connection attempts failed"):
        worker.generate(
            source_image_bytes=b"\x89PNG\r\n\x1a\nSRC",
            spec={"format": "glb"}, num_candidates=1,
        )
    assert len(attempts) == 1, (
        f"_apost must hit server EXACTLY ONCE per logical call; "
        f"silent transient retry would give 2+. Got {len(attempts)}: {attempts}"
    )


# ---- L2 fence: GenerateMeshExecutor no internal retry for mesh ----------


class _CountingMeshWorker(MeshWorker):
    """Records each call to generate() so we can assert exactly one was made."""
    name = "count_mesh"

    def __init__(self, *, raises: Exception) -> None:
        self.calls = 0
        self._raises = raises

    def generate(self, *, source_image_bytes, spec, num_candidates=1,
                 timeout_s=None):
        self.calls += 1
        raise self._raises


def _make_mesh_ctx(tmp_path, *, retry_max_attempts: int):
    """Mirror tests/unit/test_generate_mesh_cost.py::_make_ctx but inject a
    custom RetryPolicy.max_attempts so we can prove executor ignores it for
    mesh.generation."""
    from datetime import datetime, timezone
    from framework.artifact_store import ArtifactRepository, get_backend_registry
    from framework.core.artifact import ArtifactType, ProducerRef
    from framework.core.enums import (
        ArtifactRole, PayloadKind, RiskLevel, RunMode, RunStatus, StepType, TaskType,
    )
    from framework.core.policies import RetryPolicy
    from framework.core.task import Run, Step, Task
    from framework.runtime.executors.base import StepContext

    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    img_aid = "test_run_img"
    repo.put(
        artifact_id=img_aid,
        value=b"\x89PNG\r\n\x1a\nfake-png",
        artifact_type=ArtifactType(modality="image", shape="raster",
                                    display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id="test_run", step_id="upstream", provider="fab"),
        file_suffix=".png",
    )
    spec_aid = "test_run_spec"
    repo.put(
        artifact_id=spec_aid,
        value={"prompt_summary": "x", "format": "glb",
               "texture": False, "pbr": False},
        artifact_type=ArtifactType(modality="text", shape="structured",
                                    display_name="structured_answer"),
        role=ArtifactRole.intermediate, format="json",
        mime_type="application/json", payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id="test_run", step_id="spec", provider="fab"),
    )
    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        config={"num_candidates": 1},
        retry_policy=RetryPolicy(max_attempts=retry_max_attempts),
    )
    task = Task(
        task_id="t", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="m",
        input_payload={}, expected_output={}, project_id="p",
    )
    run = Run(
        run_id="test_run", task_id="t", project_id="p",
        status=RunStatus.running,
        started_at=datetime.now(timezone.utc),
        workflow_id="w", trace_id="tr",
    )
    return StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[spec_aid, img_aid],
    )


def test_executor_no_internal_retry_for_mesh_capability(tmp_path):
    """L2 fence: even with `retry_policy.max_attempts=5`, executor must call
    worker.generate() exactly ONCE for capability_ref='mesh.generation'.

    Pre-TBD-007 the executor had a `for attempt in range(attempts):` loop
    that would call .generate() multiple times silently — that's where the
    user's 16x billing amplification's "L2" came from (Codex independent
    review found this layer; my first pass missed it)."""
    from framework.runtime.executors.generate_mesh import GenerateMeshExecutor

    # Try with retry_policy.max_attempts = 5 — executor must STILL only call once
    ctx = _make_mesh_ctx(tmp_path, retry_max_attempts=5)
    worker = _CountingMeshWorker(
        raises=MeshWorkerTimeout("synthetic timeout"),
    )
    with pytest.raises(MeshWorkerTimeout):
        GenerateMeshExecutor(worker=worker).execute(ctx)

    assert worker.calls == 1, (
        f"TBD-007 fence: executor.execute() must call worker.generate() "
        f"EXACTLY ONCE for mesh.generation capability regardless of "
        f"retry_policy.max_attempts (was 5). Got {worker.calls} calls — "
        f"the executor-internal retry loop silently re-bills paid mesh jobs."
    )


# ---- L3 fence: failure_mode_map mesh-specific abort ----------------------


def test_failure_mode_map_routes_mesh_timeout_to_abort():
    """L3 fence: MeshWorkerTimeout must classify as `mesh_worker_timeout`
    (NOT generic `worker_timeout` which would route to retry_same_step) and
    map to `Decision.abort_or_fallback` which honours on_fallback if set
    or terminates cleanly — never silent re-step."""
    exc = MeshWorkerTimeout("tokenhub job 12345 exceeded 60s",
                             job_id="12345", worker="hunyuan_3d",
                             model="hy-3d-3.1")
    mode = classify(exc)
    assert mode == FailureMode.mesh_worker_timeout, (
        f"MeshWorkerTimeout must be classified as mesh_worker_timeout "
        f"(not generic worker_timeout — that maps to retry_same_step which "
        f"silently re-bills paid mesh jobs). Got {mode!r}."
    )
    entry = DEFAULT_MAP[mode]
    assert entry.decision == Decision.abort_or_fallback, (
        f"mesh_worker_timeout must map to abort_or_fallback (not "
        f"retry_same_step or fallback_model). Got {entry.decision!r}."
    )


def test_failure_mode_map_routes_mesh_error_to_abort():
    """L3 fence: MeshWorkerError must classify as `mesh_worker_error` (NOT
    generic `worker_error` which routes to fallback_model → degrades to
    retry_same_step when no fallback model exists, which is always true for
    mesh today since mesh doesn't go through CapabilityRouter)."""
    exc = MeshWorkerError("tokenhub 3d job 67890 failed: quota issue",
                          job_id="67890", worker="hunyuan_3d",
                          model="hy-3d-3.1")
    mode = classify(exc)
    assert mode == FailureMode.mesh_worker_error, (
        f"MeshWorkerError must be classified as mesh_worker_error. Got {mode!r}."
    )
    entry = DEFAULT_MAP[mode]
    assert entry.decision == Decision.abort_or_fallback, (
        f"mesh_worker_error must map to abort_or_fallback. Got {entry.decision!r}."
    )
