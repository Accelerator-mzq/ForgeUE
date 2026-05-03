"""GenerateMeshExecutor comfy/local-mesh dispatch fences.

OpenSpec change comfy-agent-cli-mesh-audio-video-adoption Phase 1 mesh
adoption — executor layer fences (commit 4 of 7 per execution_plan).

Per spec/probe-and-validation/spec.md + spec/provider-routing/spec.md
named tests for:
- _should_use_comfy_worker_path (R2-F1: provider_policy 在 Step 顶层)
- _generate_via_comfy_worker (B2 + D7: in-tree source bytes + image_path injection)
- ComfyWorker → MeshWorker 异常 wrap (D9 + R2-F2)
- 本地 retry budget vs 远端 attempts=1 (D4 + R4-F1)
- FailureModeMap 路由 wrapped MeshWorkerTimeout (R4-F1: → abort_or_fallback)
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.artifact import ArtifactType, ProducerRef
from framework.core.enums import (
    ArtifactRole, Decision, PayloadKind, RiskLevel, RunMode, RunStatus,
    StepType, TaskType,
)
from framework.core.policies import PreparedRoute, ProviderPolicy
from framework.core.task import Run, Step, Task
from framework.providers.workers.comfy_worker import (
    WorkerError as _ComfyWorkerError,
    WorkerTimeout as _ComfyWorkerTimeout,
    WorkerUnsupportedResponse as _ComfyWorkerUnsupportedResponse,
)
from framework.providers.workers.mesh_worker import (
    FakeMeshWorker, MeshCandidate, MeshWorker, MeshWorkerError,
    MeshWorkerTimeout, MeshWorkerUnsupportedResponse,
)
from framework.runtime.executors.base import StepContext
from framework.runtime.executors.generate_mesh import GenerateMeshExecutor
from framework.runtime.failure_mode_map import DEFAULT_MAP, classify


# ---- Fixtures ---------------------------------------------------------------


def _seed_image(repo: ArtifactRepository, run_id: str) -> tuple[str, bytes]:
    aid = f"{run_id}_img"
    src_bytes = b"\x89PNG\r\n\x1a\nfake-png-payload-for-comfy-mesh-test"
    repo.put(
        artifact_id=aid,
        value=src_bytes,
        artifact_type=ArtifactType(modality="image", shape="raster",
                                    display_name="concept_image"),
        role=ArtifactRole.intermediate, format="png", mime_type="image/png",
        payload_kind=PayloadKind.file,
        producer=ProducerRef(run_id=run_id, step_id="upstream", provider="fab"),
        file_suffix=".png",
    )
    return aid, src_bytes


def _seed_spec(repo: ArtifactRepository, run_id: str) -> str:
    aid = f"{run_id}_spec"
    # _resolve_spec 要求 'prompt_summary' 字段(text.structured artifact 模式);
    # 同时塞 comfy_workflow / comfy_params 让 spec 适配 mesh executor。
    repo.put(
        artifact_id=aid,
        value={
            "prompt_summary": "a textured 3d asset",
            "comfy_workflow": "Mesh/02_mini_textured_3d_hunyuan",
            "comfy_params": {"texture_quality": "high"},
            "comfy_lifecycle": "none",
        },
        artifact_type=ArtifactType(modality="text", shape="structured",
                                    display_name="structured_answer"),
        role=ArtifactRole.intermediate, format="json",
        mime_type="application/json", payload_kind=PayloadKind.inline,
        producer=ProducerRef(run_id=run_id, step_id="spec", provider="fab"),
    )
    return aid


def _make_comfy_mesh_ctx(
    tmp_path: Path, run_id: str = "run_comfy_mesh", *,
    num_candidates: int = 1,
    use_comfy_local_mesh_route: bool = True,
    extra_routes: list[PreparedRoute] | None = None,
) -> tuple[StepContext, ArtifactRepository, bytes]:
    """构造 comfy/local-mesh 路由的 StepContext + repo + source bytes。"""
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    img_aid, src_bytes = _seed_image(repo, run_id)
    spec_aid = _seed_spec(repo, run_id)
    routes: list[PreparedRoute] = []
    if use_comfy_local_mesh_route:
        routes.append(PreparedRoute(
            model="comfy/local-mesh", api_key_env=None, api_base=None,
            kind="mesh", pricing=None,
        ))
    if extra_routes:
        routes.extend(extra_routes)
    policy = ProviderPolicy(
        capability_required="mesh.generation",
        prepared_routes=routes,
    )
    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        config={"num_candidates": num_candidates},
        provider_policy=policy,
    )
    task = Task(
        task_id="t", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="m",
        input_payload={}, expected_output={}, project_id="p",
    )
    run = Run(
        run_id=run_id, task_id="t", project_id="p",
        status=RunStatus.running,
        started_at=datetime.now(timezone.utc),
        workflow_id="w", trace_id="tr",
    )
    # 显式设 run_dir = tmp_path,避免 _generate_via_comfy_worker 把 source bytes
    # 写到项目根(ctx.run_dir 默认 Path(".") 会污染 working tree)
    ctx = StepContext(
        run=run, task=task, step=step, repository=repo,
        upstream_artifact_ids=[spec_aid, img_aid],
        run_dir=tmp_path,
    )
    return ctx, repo, src_bytes


def _fake_mesh_candidate(extra_meta: dict | None = None) -> MeshCandidate:
    meta = {
        "comfy_manifest": "Mesh/01",
        "comfy_params_snapshot": {"image_path": "x"},
        "comfy_capability": "mesh",
        "comfy_original_filename": "asset.glb",
        "comfy_source_image_path": "x",
    }
    if extra_meta:
        meta.update(extra_meta)
    return MeshCandidate(
        data=b"glTF\x02\x00\x00\x00" + b"\x00" * 16,
        format="glb", mime_type="model/gltf-binary",
        metadata=meta,
    )


# ---- _should_use_comfy_worker_path (R2-F1) ----------------------------------


def test_should_use_comfy_worker_path_reads_provider_policy_from_step_top_level(tmp_path, monkeypatch):
    """R2-F1 critical:`_should_use_comfy_worker_path` 必须读 ctx.step.provider_policy
    (Step 顶层)而非 ctx.step.config.provider_policy(后者不存在,会 AttributeError)。
    本 fence 用真实 Step 对象,断言 helper 不抛异常 + 返 True。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(tmp_path / "comfy_input"))  # round 5 D10
    ctx, _, _ = _make_comfy_mesh_ctx(tmp_path, use_comfy_local_mesh_route=True)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    # 直接调 helper:必须返 True 且不抛 AttributeError
    assert executor._should_use_comfy_worker_path(ctx) is True


def test_should_use_comfy_worker_path_returns_false_for_remote_hunyuan_route(tmp_path):
    """remote hunyuan/hy-3d-3.1 route 不触发 comfy 分支。"""
    extra = [PreparedRoute(model="hunyuan/hy-3d-3.1", api_key_env="HUNYUAN_3D_KEY",
                           kind="mesh", pricing={"per_task_usd": 0.25})]
    ctx, _, _ = _make_comfy_mesh_ctx(tmp_path,
                                      use_comfy_local_mesh_route=False,
                                      extra_routes=extra)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    assert executor._should_use_comfy_worker_path(ctx) is False


def test_should_use_comfy_worker_path_returns_false_when_no_provider_policy(tmp_path):
    """provider_policy is None → 返 False(不 raise)。"""
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    img, _ = _seed_image(repo, "run_x")
    spec = _seed_spec(repo, "run_x")
    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        config={}, provider_policy=None,
    )
    task = Task(task_id="t", task_type=TaskType.asset_generation,
                run_mode=RunMode.production, title="m",
                input_payload={}, expected_output={}, project_id="p")
    run = Run(run_id="run_x", task_id="t", project_id="p",
              status=RunStatus.running,
              started_at=datetime.now(timezone.utc),
              workflow_id="w", trace_id="tr")
    ctx = StepContext(run=run, task=task, step=step, repository=repo,
                      upstream_artifact_ids=[spec, img])
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    assert executor._should_use_comfy_worker_path(ctx) is False


# ---- _generate_via_comfy_worker (B2 + D7) -----------------------------------


def test_generate_via_comfy_worker_writes_source_bytes_to_comfyui_input_dir_with_forgeue_prefix(tmp_path, monkeypatch):
    """Round 5 D10 修订:executor 写 source bytes 到 ComfyUI 自家 input/ 目录
    (via FORGEUE_COMFY_INPUT_DIR env),filename `forgeue_<sha1>.png`(prefix 防与
    ComfyUI 自家 input 文件冲突);round 1-4 写到 <run_dir>/comfy/input 是错的
    (LoadImage 节点不接绝对路径)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    comfy_input_dir = tmp_path / "comfy_input"
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(comfy_input_dir))
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    expected_sha1 = hashlib.sha1(src_bytes).hexdigest()[:16]
    expected_path = comfy_input_dir / f"forgeue_{expected_sha1}.png"
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.generate_mesh.return_value = [_fake_mesh_candidate()]
        executor._generate_via_comfy_worker(
            ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
            source_image_bytes=src_bytes, num=1, seed=42, timeout_s=600,
        )
    assert expected_path.exists()
    assert expected_path.read_bytes() == src_bytes


def test_generate_via_comfy_worker_passes_source_image_filename_to_worker_generate_mesh(tmp_path, monkeypatch):
    """Round 5 D10:filename only(不是 absolute path)传给 worker.generate_mesh。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(tmp_path / "comfy_input"))
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.generate_mesh.return_value = [_fake_mesh_candidate()]
        executor._generate_via_comfy_worker(
            ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
            source_image_bytes=src_bytes, num=1, seed=42, timeout_s=600,
        )
        call_kwargs = W.return_value.generate_mesh.call_args.kwargs
        sha1_hex = hashlib.sha1(src_bytes).hexdigest()[:16]
        # round 5 D10:source_image_filename(filename only)而非 source_image_path(绝对路径)
        assert call_kwargs["source_image_filename"] == f"forgeue_{sha1_hex}.png"


def test_generate_via_comfy_worker_raises_when_FORGEUE_COMFY_INPUT_DIR_unset(tmp_path, monkeypatch):
    """Round 5 D10:FORGEUE_COMFY_INPUT_DIR env unset 时立即 raise
    MeshWorkerUnsupportedResponse(fail-fast,不静默落 source bytes 到错位置)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.delenv("FORGEUE_COMFY_INPUT_DIR", raising=False)
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with pytest.raises(MeshWorkerUnsupportedResponse, match="FORGEUE_COMFY_INPUT_DIR"):
        executor._generate_via_comfy_worker(
            ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
            source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
        )


def test_generate_via_comfy_worker_constructs_worker_with_model_id_comfy_local_mesh(tmp_path, monkeypatch):
    """D1:executor 构造 ComfyAgentWorker 时传 model_id='comfy/local-mesh'。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(tmp_path / "comfy_input"))  # round 5 D10
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.generate_mesh.return_value = [_fake_mesh_candidate()]
        executor._generate_via_comfy_worker(
            ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
            source_image_bytes=src_bytes, num=1, seed=None, timeout_s=600,
        )
    init_kwargs = W.call_args.kwargs
    assert init_kwargs["model_id"] == "comfy/local-mesh"
    assert init_kwargs["run_id"] == "run_comfy_mesh"
    assert init_kwargs["project_id"] == "p"


def test_generate_via_comfy_worker_raises_when_env_unset(tmp_path, monkeypatch):
    """env unset → MeshWorkerUnsupportedResponse(不是 raw ComfyWorker exception;
    早 wrap 让 caller 看到 mesh-worker exception family)。"""
    monkeypatch.delenv("FORGEUE_COMFY_SCRIPTS_DIR", raising=False)
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with pytest.raises(MeshWorkerUnsupportedResponse, match="FORGEUE_COMFY_SCRIPTS_DIR"):
        executor._generate_via_comfy_worker(
            ctx=ctx, spec={}, source_image_bytes=src_bytes,
            num=1, seed=None, timeout_s=60,
        )


# ---- ComfyWorker → MeshWorker 异常 wrap (D9 + R2-F2) ------------------------


def test_generate_via_comfy_worker_wraps_worker_timeout_to_mesh_worker_timeout(tmp_path, monkeypatch):
    """D9:WorkerTimeout → MeshWorkerTimeout(让 retry loop catch + FailureModeMap 路由)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(tmp_path / "comfy_input"))  # round 5 D10
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.generate_mesh.side_effect = _ComfyWorkerTimeout("subprocess exceeded")
        with pytest.raises(MeshWorkerTimeout, match="subprocess exceeded") as ei:
            executor._generate_via_comfy_worker(
                ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
            )
        # __cause__ 保留原 ComfyWorker exception
        assert isinstance(ei.value.__cause__, _ComfyWorkerTimeout)


def test_generate_via_comfy_worker_wraps_worker_unsupported_response_to_mesh_worker_unsupported(tmp_path, monkeypatch):
    """D9:WorkerUnsupportedResponse → MeshWorkerUnsupportedResponse(不 retry)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(tmp_path / "comfy_input"))  # round 5 D10
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.generate_mesh.side_effect = _ComfyWorkerUnsupportedResponse("invalid param")
        with pytest.raises(MeshWorkerUnsupportedResponse, match="invalid param") as ei:
            executor._generate_via_comfy_worker(
                ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
            )
        assert isinstance(ei.value.__cause__, _ComfyWorkerUnsupportedResponse)
        # 不 retry → call_count == 1
        assert W.return_value.generate_mesh.call_count == 1


def test_generate_via_comfy_worker_wraps_generic_worker_error_to_mesh_worker_error(tmp_path, monkeypatch):
    """D9:WorkerError → MeshWorkerError(不 retry)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(tmp_path / "comfy_input"))  # round 5 D10
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.generate_mesh.side_effect = _ComfyWorkerError("comfyui_api ok=false")
        with pytest.raises(MeshWorkerError, match="comfyui_api ok=false") as ei:
            executor._generate_via_comfy_worker(
                ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
            )
        assert isinstance(ei.value.__cause__, _ComfyWorkerError)


# ---- 本地 retry budget (R2-F2 + R4-F1) --------------------------------------


def test_local_comfy_mesh_executor_calls_worker_max_attempts_times_on_timeout(tmp_path, monkeypatch):
    """R2-F2 critical:本地 mesh 走 standard retry,RetryPolicy 默认 max_attempts=2。
    第一次 timeout 后 retry,第二次成功 → call_count == 2。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(tmp_path / "comfy_input"))  # round 5 D10
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    successful_cands = [_fake_mesh_candidate()]
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # 第一次 raise WorkerTimeout,第二次返候选
        W.return_value.generate_mesh.side_effect = [
            _ComfyWorkerTimeout("first attempt timeout"),
            successful_cands,
        ]
        # 跳过 _backoff sleep 加快测试
        with patch("framework.runtime.executors.generate_mesh._backoff"):
            cands = executor._generate_via_comfy_worker(
                ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
            )
    assert cands == successful_cands
    # max_attempts default 2 → 第一次 fail + 第二次 success = 2 次调用
    assert W.return_value.generate_mesh.call_count == 2


def test_local_comfy_mesh_executor_does_not_retry_on_worker_unsupported_response(tmp_path, monkeypatch):
    """R2-F2:UnsupportedResponse 是 deterministic,不 retry。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(tmp_path / "comfy_input"))  # round 5 D10
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.generate_mesh.side_effect = _ComfyWorkerUnsupportedResponse("bad param")
        with pytest.raises(MeshWorkerUnsupportedResponse):
            executor._generate_via_comfy_worker(
                ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
            )
        assert W.return_value.generate_mesh.call_count == 1


def test_local_comfy_mesh_executor_raises_after_all_retries_exhausted(tmp_path, monkeypatch):
    """R2-F2 + R4-F1:max_attempts 全部 timeout → raise wrapped MeshWorkerTimeout
    (传给 FailureModeMap → mesh_worker_timeout → abort_or_fallback)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(tmp_path / "comfy_input"))  # round 5 D10
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # 两次都 timeout
        W.return_value.generate_mesh.side_effect = _ComfyWorkerTimeout("persistent")
        with patch("framework.runtime.executors.generate_mesh._backoff"):
            with pytest.raises(MeshWorkerTimeout, match="persistent"):
                executor._generate_via_comfy_worker(
                    ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                    source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
                )
        assert W.return_value.generate_mesh.call_count == 2  # max_attempts


# ---- FailureModeMap 路由 (R4-F1) --------------------------------------------


def test_failure_mode_map_routes_wrapped_local_comfy_mesh_timeout_to_abort_or_fallback_after_internal_retries_exhausted(tmp_path):
    """R4-F1 critical:wrapped MeshWorkerTimeout 经 FailureModeMap 走
    mesh_worker_timeout mode → Decision.abort_or_fallback(NOT retry_same_step;
    与远端 mesh 终态一致;本地 standard retry 已在内部 loop 完成)。"""
    wrapped = MeshWorkerTimeout("internal retry exhausted")
    mode = classify(wrapped)
    decision = DEFAULT_MAP[mode].decision
    assert decision == Decision.abort_or_fallback


def test_failure_mode_map_routes_wrapped_mesh_worker_unsupported_to_abort_or_fallback(tmp_path):
    """wrapped MeshWorkerUnsupportedResponse 走 unsupported_response → abort_or_fallback。"""
    wrapped = MeshWorkerUnsupportedResponse("invalid param")
    mode = classify(wrapped)
    decision = DEFAULT_MAP[mode].decision
    # MeshWorkerUnsupportedResponse 是 MeshWorkerError 的子类,但实际 classify
    # 优先匹配 unsupported_response(comfy_worker.WorkerUnsupportedResponse 同理)
    assert decision == Decision.abort_or_fallback


# ---- End-to-end execute() with comfy/local-mesh route -----------------------


def test_executor_execute_dispatches_comfy_local_mesh_via_internal_retry_branch(tmp_path, monkeypatch):
    """End-to-end:execute() 检测 comfy/local-mesh route → _generate_via_comfy_worker
    (NOT 现有 self._worker.generate)→ 持久化为 in-tree GLB Artifact。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setenv("FORGEUE_COMFY_INPUT_DIR", str(tmp_path / "comfy_input"))  # round 5 D10
    ctx, repo, src_bytes = _make_comfy_mesh_ctx(tmp_path, num_candidates=1)

    # injected worker:不应被调用(comfy 分支接管)
    injected_worker = MagicMock(spec=MeshWorker)
    injected_worker.name = "injected_test_worker"
    executor = GenerateMeshExecutor(worker=injected_worker)

    fake_cand = _fake_mesh_candidate()
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.generate_mesh.return_value = [fake_cand]
        result = executor.execute(ctx)

    # injected worker 未被调用(comfy dispatch)
    injected_worker.generate.assert_not_called()
    # 1 个 mesh artifact 落 in-tree
    assert result.metrics["mesh_count"] == 1
    # cost = 0(comfy local pricing=None)
    assert result.metrics["cost_usd"] == 0.0


def test_executor_execute_remote_hunyuan_route_does_not_dispatch_to_comfy_branch(tmp_path):
    """regression:no comfy/local-mesh route → 走原 self._worker.generate 路径
    (远端 mesh attempts=1 enforcement 不受本 change 影响)。"""
    extra = [PreparedRoute(model="hunyuan/hy-3d-3.1", api_key_env="HUNYUAN_3D_KEY",
                           kind="mesh", pricing={"per_task_usd": 0.25})]
    ctx, _, _ = _make_comfy_mesh_ctx(tmp_path,
                                      use_comfy_local_mesh_route=False,
                                      extra_routes=extra,
                                      num_candidates=1)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        result = executor.execute(ctx)
        # comfy worker 完全没被构造
        W.assert_not_called()
    assert result.metrics["mesh_count"] == 1
    assert result.metrics["cost_usd"] == pytest.approx(0.25)
