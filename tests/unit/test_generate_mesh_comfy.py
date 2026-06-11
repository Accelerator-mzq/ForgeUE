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
from unittest.mock import AsyncMock, MagicMock, patch

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


def _comfy_provider_config(tmp_path: Path) -> dict[str, str | None]:
    """构造测试用 ComfyUI provider_config，与 models.yaml 元数据形状对齐。"""
    return {
        "adapter": "comfy_agent_cli",
        "scripts_dir": str(tmp_path / "yaml_scripts"),
        "python_exe": None,
        "default_lifecycle": "none",
        "output_root": str(tmp_path),
    }


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
            provider_name="comfy_api",
            provider_kind="subprocess",
            provider_config=_comfy_provider_config(tmp_path),
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


def _fake_mesh_candidate(
    extra_meta: dict | None = None,
    *,
    data: bytes | None = None,
    source_path: str | None = None,
) -> MeshCandidate:
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
        data=data if data is not None else b"glTF\x02\x00\x00\x00" + b"\x00" * 16,
        format="glb", mime_type="model/gltf-binary",
        metadata=meta,
        source_path=source_path,
    )


# ---- _should_use_comfy_worker_path (R2-F1) ----------------------------------


def test_should_use_comfy_worker_path_reads_provider_policy_from_step_top_level(tmp_path, monkeypatch):
    """R2-F1 critical:`_should_use_comfy_worker_path` 必须读 ctx.step.provider_policy
    (Step 顶层)而非 ctx.step.config.provider_policy(后者不存在,会 AttributeError)。
    本 fence 用真实 Step 对象,断言 helper 不抛异常 + 返 True。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
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


async def test_generate_via_comfy_worker_writes_staging_png_under_run_dir_and_passes_abs_path(tmp_path, monkeypatch):
    """comfy-agent-api-v3-adaptation(2026-06-11):executor 写 source bytes 到
    in-tree staging 文件 <run_dir>/comfy/forgeue_<sha1>.png(idempotent via sha1),
    并以**绝对路径**传给 worker——上游 v3 起 `comfyui_api run` 对 input_image*
    本地路径自动 POST /upload/image(AGENT_API.md §1.3),原 round 5 D10 的
    FORGEUE_COMFY_INPUT_DIR 直写机制退役。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.delenv("FORGEUE_COMFY_INPUT_DIR", raising=False)
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    expected_sha1 = hashlib.sha1(src_bytes).hexdigest()[:16]
    expected_path = tmp_path / "comfy" / f"forgeue_{expected_sha1}.png"
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.agenerate_mesh = AsyncMock(return_value=[_fake_mesh_candidate()])
        await executor._generate_via_comfy_worker(
            ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
            source_image_bytes=src_bytes, num=1, seed=42, timeout_s=600,
        )
        call_kwargs = W.return_value.agenerate_mesh.call_args.kwargs
    # staging 文件落 in-tree run_dir(随 artifacts 生命周期管理,不再写 ComfyUI 自家目录)
    assert expected_path.exists()
    assert expected_path.read_bytes() == src_bytes
    # worker 收到的是绝对路径(上游 auto-upload 判定条件:含路径分隔符 + 文件存在)
    assert call_kwargs["source_image_filename"] == str(expected_path)


async def test_generate_via_comfy_worker_succeeds_without_input_dir_env(tmp_path, monkeypatch):
    """退役 fence:FORGEUE_COMFY_INPUT_DIR unset + provider_config 无 input_dir
    也必须成功(v3 auto-upload 后该配置链整体退役;原 round 5 D10 的 fail-fast
    守门随之删除)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.delenv("FORGEUE_COMFY_INPUT_DIR", raising=False)
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    route = ctx.step.provider_policy.prepared_routes[0]
    route.provider_config.pop("input_dir", None)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.agenerate_mesh = AsyncMock(return_value=[_fake_mesh_candidate()])
        results = await executor._generate_via_comfy_worker(
            ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
            source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
        )
    assert len(results) == 1


async def test_generate_via_comfy_worker_constructs_worker_with_model_id_comfy_local_mesh(tmp_path, monkeypatch):
    """D1:executor 构造 ComfyAgentWorker 时传 model_id='comfy/local-mesh'。
    Task 5 GREEN: _generate_via_comfy_worker 已转 async,测试改为 async def + await。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # Task 5 GREEN: agenerate_mesh 用 AsyncMock
        W.return_value.agenerate_mesh = AsyncMock(return_value=[_fake_mesh_candidate()])
        await executor._generate_via_comfy_worker(
            ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
            source_image_bytes=src_bytes, num=1, seed=None, timeout_s=600,
        )
    init_kwargs = W.call_args.kwargs
    assert init_kwargs["model_id"] == "comfy/local-mesh"
    assert init_kwargs["run_id"] == "run_comfy_mesh"
    assert init_kwargs["project_id"] == "p"


async def test_generate_via_comfy_worker_raises_when_env_unset(tmp_path, monkeypatch):
    """env unset → MeshWorkerUnsupportedResponse(不是 raw ComfyWorker exception;
    早 wrap 让 caller 看到 mesh-worker exception family)。
    Task 5 GREEN: _generate_via_comfy_worker 已转 async,测试改为 async def + await。"""
    monkeypatch.delenv("FORGEUE_COMFY_SCRIPTS_DIR", raising=False)
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    route = ctx.step.provider_policy.prepared_routes[0]
    route.provider_config["scripts_dir"] = None
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with pytest.raises(MeshWorkerUnsupportedResponse, match="FORGEUE_COMFY_SCRIPTS_DIR"):
        await executor._generate_via_comfy_worker(
            ctx=ctx, spec={}, source_image_bytes=src_bytes,
            num=1, seed=None, timeout_s=60,
        )


# ---- ComfyWorker → MeshWorker 异常 wrap (D9 + R2-F2) ------------------------


async def test_generate_via_comfy_worker_wraps_worker_timeout_to_mesh_worker_timeout(tmp_path, monkeypatch):
    """D9:WorkerTimeout → MeshWorkerTimeout(让 retry loop catch + FailureModeMap 路由)。
    Task 5 GREEN: _generate_via_comfy_worker 已转 async,测试改为 async def + await。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # Task 5 GREEN: agenerate_mesh 用 AsyncMock
        W.return_value.agenerate_mesh = AsyncMock(side_effect=_ComfyWorkerTimeout("subprocess exceeded"))
        with pytest.raises(MeshWorkerTimeout, match="subprocess exceeded") as ei:
            await executor._generate_via_comfy_worker(
                ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
            )
        # __cause__ 保留原 ComfyWorker exception
        assert isinstance(ei.value.__cause__, _ComfyWorkerTimeout)


async def test_generate_via_comfy_worker_wraps_worker_unsupported_response_to_mesh_worker_unsupported(tmp_path, monkeypatch):
    """D9:WorkerUnsupportedResponse → MeshWorkerUnsupportedResponse(不 retry)。
    Task 5 GREEN: _generate_via_comfy_worker 已转 async,测试改为 async def + await。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # Task 5 GREEN: agenerate_mesh 用 AsyncMock
        W.return_value.agenerate_mesh = AsyncMock(side_effect=_ComfyWorkerUnsupportedResponse("invalid param"))
        with pytest.raises(MeshWorkerUnsupportedResponse, match="invalid param") as ei:
            await executor._generate_via_comfy_worker(
                ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
            )
        assert isinstance(ei.value.__cause__, _ComfyWorkerUnsupportedResponse)
        # 不 retry → call_count == 1
        assert W.return_value.agenerate_mesh.call_count == 1


async def test_generate_via_comfy_worker_wraps_generic_worker_error_to_mesh_worker_error(tmp_path, monkeypatch):
    """D9:WorkerError → MeshWorkerError(不 retry)。
    Task 5 GREEN: _generate_via_comfy_worker 已转 async,测试改为 async def + await。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # Task 5 GREEN: agenerate_mesh 用 AsyncMock
        W.return_value.agenerate_mesh = AsyncMock(side_effect=_ComfyWorkerError("comfyui_api ok=false"))
        with pytest.raises(MeshWorkerError, match="comfyui_api ok=false") as ei:
            await executor._generate_via_comfy_worker(
                ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
            )
        assert isinstance(ei.value.__cause__, _ComfyWorkerError)


# ---- 本地 retry budget (R2-F2 + R4-F1) --------------------------------------


async def test_local_comfy_mesh_executor_calls_worker_max_attempts_times_on_timeout(tmp_path, monkeypatch):
    """R2-F2 critical:本地 mesh 走 standard retry,RetryPolicy 默认 max_attempts=2。
    第一次 timeout 后 retry,第二次成功 → call_count == 2。
    Task 5 GREEN: _generate_via_comfy_worker 已转 async,测试改为 async def + await。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    successful_cands = [_fake_mesh_candidate()]
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # 第一次 raise WorkerTimeout,第二次返候选
        # Task 5 GREEN: agenerate_mesh 用 AsyncMock + side_effect list
        W.return_value.agenerate_mesh = AsyncMock(side_effect=[
            _ComfyWorkerTimeout("first attempt timeout"),
            successful_cands,
        ])
        # 跳过 _backoff sleep 加快测试
        with patch("framework.runtime.executors.generate_mesh._backoff"):
            cands = await executor._generate_via_comfy_worker(
                ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
            )
    assert cands == successful_cands
    # max_attempts default 2 → 第一次 fail + 第二次 success = 2 次调用
    assert W.return_value.agenerate_mesh.call_count == 2


async def test_local_comfy_mesh_executor_does_not_retry_on_worker_unsupported_response(tmp_path, monkeypatch):
    """R2-F2:UnsupportedResponse 是 deterministic,不 retry。
    Task 5 GREEN: _generate_via_comfy_worker 已转 async,测试改为 async def + await。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # Task 5 GREEN: agenerate_mesh 用 AsyncMock
        W.return_value.agenerate_mesh = AsyncMock(side_effect=_ComfyWorkerUnsupportedResponse("bad param"))
        with pytest.raises(MeshWorkerUnsupportedResponse):
            await executor._generate_via_comfy_worker(
                ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
            )
        assert W.return_value.agenerate_mesh.call_count == 1


async def test_local_comfy_mesh_executor_raises_after_all_retries_exhausted(tmp_path, monkeypatch):
    """R2-F2 + R4-F1:max_attempts 全部 timeout → raise wrapped MeshWorkerTimeout
    (传给 FailureModeMap → mesh_worker_timeout → abort_or_fallback)。
    Task 5 GREEN: _generate_via_comfy_worker 已转 async,测试改为 async def + await。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # 两次都 timeout;Task 5 GREEN: agenerate_mesh 用 AsyncMock
        W.return_value.agenerate_mesh = AsyncMock(side_effect=_ComfyWorkerTimeout("persistent"))
        with patch("framework.runtime.executors.generate_mesh._backoff"):
            with pytest.raises(MeshWorkerTimeout, match="persistent"):
                await executor._generate_via_comfy_worker(
                    ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
                    source_image_bytes=src_bytes, num=1, seed=None, timeout_s=60,
                )
        assert W.return_value.agenerate_mesh.call_count == 2  # max_attempts


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


async def test_executor_execute_dispatches_comfy_local_mesh_via_internal_retry_branch(tmp_path, monkeypatch):
    """End-to-end:execute() 检测 comfy/local-mesh route → _generate_via_comfy_worker
    (NOT 现有 self._worker.generate)→ 持久化为 in-tree GLB Artifact。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    ctx, repo, src_bytes = _make_comfy_mesh_ctx(tmp_path, num_candidates=1)

    # injected worker:不应被调用(comfy 分支接管)
    injected_worker = MagicMock(spec=MeshWorker)
    injected_worker.name = "injected_test_worker"
    executor = GenerateMeshExecutor(worker=injected_worker)

    fake_cand = _fake_mesh_candidate()
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # Task 5 GREEN: agenerate_mesh 用 AsyncMock
        W.return_value.agenerate_mesh = AsyncMock(return_value=[fake_cand])
        result = await executor.execute(ctx)

    # injected worker 未被调用(comfy dispatch)
    injected_worker.generate.assert_not_called()
    # 1 个 mesh artifact 落 in-tree
    assert result.metrics["mesh_count"] == 1
    # cost = 0(comfy local pricing=None)
    assert result.metrics["cost_usd"] == 0.0


async def test_executor_persists_mesh_candidate_source_path_without_using_data(tmp_path, monkeypatch):
    """FOR-13:MeshCandidate.source_path 优先落盘,cand.data 只保留校验头/兼容信息。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    ctx, repo, _ = _make_comfy_mesh_ctx(tmp_path, num_candidates=1)
    source = tmp_path / "source_mesh.glb"
    source.write_bytes(b"glTF\x02\x00\x00\x00real-mesh-payload")
    fake_cand = _fake_mesh_candidate(data=b"glTF", source_path=str(source))
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())

    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.agenerate_mesh = AsyncMock(return_value=[fake_cand])
        result = await executor.execute(ctx)

    mesh_art = next(a for a in result.artifacts if a.artifact_type.modality == "mesh")
    assert repo.read_payload(mesh_art.artifact_id) == source.read_bytes()


async def test_executor_execute_remote_hunyuan_route_does_not_dispatch_to_comfy_branch(tmp_path):
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
        result = await executor.execute(ctx)
        # comfy worker 完全没被构造
        W.assert_not_called()
    assert result.metrics["mesh_count"] == 1
    assert result.metrics["cost_usd"] == pytest.approx(0.25)


# ---- G6-F3 follow-on: producer attribution for comfy/local-mesh path -------
# OpenSpec change `comfy-executor-producer-attribution-fix`(2026-05-04):
# fence 守门 comfy/local-mesh 分支活跃时,Artifact.producer.provider == "comfy_agent_cli"
# (NOT self._worker.name 注入的 fallback worker 名);metrics["worker"] 同样走 comfy_agent_cli。


async def test_executor_dispatches_comfy_local_mesh_records_provider_as_comfy_agent_cli(tmp_path, monkeypatch):
    """G6-F3 follow-on:comfy/local-mesh 路径活跃时,Artifact.producer.provider
    == "comfy_agent_cli",NOT injected worker name(框架 self._worker.name 注入的
    HunyuanMeshWorker / FakeMeshWorker 名会污染 audit / comparison report)。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    ctx, repo, src_bytes = _make_comfy_mesh_ctx(tmp_path, num_candidates=1)

    # injected worker:其 name 是 "injected_test_worker",但本 change 后该字段
    # 不应出现在 Artifact.producer 里
    injected_worker = MagicMock(spec=MeshWorker)
    injected_worker.name = "injected_test_worker"
    executor = GenerateMeshExecutor(worker=injected_worker)

    fake_cand = _fake_mesh_candidate()
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        # Task 5 GREEN: agenerate_mesh 用 AsyncMock
        W.return_value.agenerate_mesh = AsyncMock(return_value=[fake_cand])
        result = await executor.execute(ctx)

    assert len(result.artifacts) == 1
    art = result.artifacts[0]
    assert art.producer.provider == "comfy_agent_cli", (
        f"Expected provider='comfy_agent_cli' for comfy/local-mesh path, "
        f"got {art.producer.provider!r}; pre-fix would yield 'injected_test_worker'"
    )
    assert art.producer.model == "comfy/local-mesh", (
        f"Expected model='comfy/local-mesh' for comfy path, got {art.producer.model!r}"
    )
    # metrics["worker"] 同样应为 comfy_agent_cli(audit / comparison 走此字段)
    assert result.metrics["worker"] == "comfy_agent_cli", (
        f"Expected metrics.worker='comfy_agent_cli', got {result.metrics['worker']!r}"
    )


async def test_executor_remote_hunyuan_path_records_provider_as_worker_name(tmp_path):
    """regression:non-comfy 路径(远端 Hunyuan / Tripo)producer.provider == self._worker.name,
    保留原行为(本 change 只改 comfy 分支 attribution,不改远端 mesh 分支)。"""
    extra = [PreparedRoute(model="hunyuan/hy-3d-3.1", api_key_env="HUNYUAN_3D_KEY",
                           kind="mesh", pricing={"per_task_usd": 0.25})]
    ctx, _, _ = _make_comfy_mesh_ctx(tmp_path,
                                      use_comfy_local_mesh_route=False,
                                      extra_routes=extra,
                                      num_candidates=1)
    fake_worker = FakeMeshWorker()
    executor = GenerateMeshExecutor(worker=fake_worker)
    result = await executor.execute(ctx)
    assert len(result.artifacts) == 1
    art = result.artifacts[0]
    # FakeMeshWorker.name == "fake_mesh"
    assert art.producer.provider == fake_worker.name, (
        f"Expected provider='{fake_worker.name}' for remote/fake mesh path, "
        f"got {art.producer.provider!r}"
    )
    assert result.metrics["worker"] == fake_worker.name


async def test_generate_via_comfy_worker_resolves_relative_run_dir_to_absolute_path(tmp_path, monkeypatch):
    """L2 实测回归 fence(2026-06-11):framework.run 默认 --artifact-root 是相对路径
    (artifacts/<today>),ctx.run_dir 因此相对;CLI 子进程 cwd=scripts_dir,相对路径在
    CLI 侧 os.path.isfile() 判 False → auto-upload 不触发 → 原值透传 LoadImage →
    ComfyUI prompt 校验 HTTP 400(error_code=unknown → generic mesh_worker_error)。
    executor 必须把 staging 路径 resolve() 成绝对路径再传 worker。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    ctx, _, src_bytes = _make_comfy_mesh_ctx(tmp_path)
    # 模拟 orchestrator 注入相对 run_dir(默认 --artifact-root artifacts/<today>)
    rel_run_dir = Path("rel_artifacts") / "run_x"
    object.__setattr__(ctx, "run_dir", rel_run_dir) if hasattr(type(ctx), "__dataclass_fields__") else setattr(ctx, "run_dir", rel_run_dir)
    executor = GenerateMeshExecutor(worker=FakeMeshWorker())
    with patch("framework.runtime.executors.generate_mesh.ComfyAgentWorker") as W:
        W.return_value.agenerate_mesh = AsyncMock(return_value=[_fake_mesh_candidate()])
        await executor._generate_via_comfy_worker(
            ctx=ctx, spec={"comfy_workflow": "M/01", "comfy_params": {}},
            source_image_bytes=src_bytes, num=1, seed=42, timeout_s=600,
        )
        passed = Path(W.return_value.agenerate_mesh.call_args.kwargs["source_image_filename"])
    assert passed.is_absolute(), \
        f"staging 路径必须 resolve 成绝对路径(CLI cwd=scripts_dir,相对路径必坏): {passed}"
    assert passed.is_file()
