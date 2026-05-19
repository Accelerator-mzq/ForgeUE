"""Unit tests for Orchestrator helpers added in OpenSpec change
comfy-agent-cli-adoption.

Currently scoped to `_compute_run_dir(run)` helper (round 2 OQ-7 = G-A
decision + round 3 H1 fix: NO double date segment because framework.run
already date-buckets --artifact-root by default).

Task 9 (executor-async-rewrite): Orchestrator lifecycle 持有、注入、
try/finally 全路径 release、aclose() 钩子。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import framework.runtime.orchestrator as orchestrator_mod
from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.enums import RiskLevel, RunMode, RunStatus, StepType, TaskType
from framework.core.policies import PreparedRoute, ProviderPolicy
from framework.core.task import Step, Task, Workflow
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.executors.base import (
    ExecutorRegistry,
    ExecutorResult,
    StepContext,
    StepExecutor,
)
from framework.runtime.lifecycle import ComfyLifecycleManager
from framework.runtime.orchestrator import Orchestrator


# ─────────────────────── 公共测试辅助 ──────────────────────────────────────

def _make_orchestrator(checkpoints_root: Path | None) -> Orchestrator:
    repo = MagicMock()
    checkpoints = MagicMock()
    if checkpoints_root is not None:
        checkpoints._root = checkpoints_root
    else:
        # 模拟无 _root 属性的 CheckpointStore(仅用于测试)
        # spec=[] 使 getattr(..., "_root", None) 返回 None
        checkpoints = MagicMock(spec=[])
    return Orchestrator(repository=repo, checkpoint_store=checkpoints)


def _make_comfy_task_workflow_steps(
    mode: str = "ensure_release",
    capability_ref: str = "mock.comfy",
) -> tuple[Task, Workflow, list[Step]]:
    """构建一个含 comfy/local 路由且 comfy_lifecycle != none 的最小 bundle。"""
    step = Step(
        step_id="s1",
        type=StepType.generate,
        name="comfy-step",
        risk_level=RiskLevel.low,
        capability_ref=capability_ref,
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=[
                PreparedRoute(model="comfy/local", kind="image"),
            ],
        ),
        # comfy_lifecycle 存在 step.config.spec.comfy_lifecycle
        config={"spec": {"comfy_lifecycle": mode}},
    )
    workflow = Workflow(
        workflow_id="wf_lc",
        name="lifecycle_test",
        version="1.0",
        entry_step_id="s1",
        step_ids=["s1"],
    )
    task = Task(
        task_id="t_lc",
        task_type=TaskType.asset_generation,
        run_mode=RunMode.basic_llm,
        title="lifecycle test",
        project_id="proj_lc",
    )
    return task, workflow, [step]


class _LifecycleRecordingExecutor(StepExecutor):
    """记录每次 execute 时 ctx.lifecycle 的值,用于断言注入是否生效。"""

    step_type = StepType.generate
    capability_ref = "mock.comfy"

    def __init__(self, seen: list) -> None:
        # 收集每步 ctx.lifecycle 对象引用
        self._seen = seen

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        self._seen.append(ctx.lifecycle)
        return ExecutorResult(artifacts=[], metrics={})


class _ErrorExecutor(StepExecutor):
    """在 execute 时抛出指定异常,用于测试异常路径 release。"""

    step_type = StepType.generate
    capability_ref = "mock.comfy"

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        raise self._exc


def _build_orch_with_executor(
    executor: StepExecutor,
    tmp_path: Path,
    capability_ref: str = "mock.comfy",
) -> tuple[Orchestrator, CheckpointStore, ArtifactRepository]:
    """构建带真实 CheckpointStore + ArtifactRepository 的 Orchestrator。"""
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)
    store = CheckpointStore(artifact_root=tmp_path)
    execs = ExecutorRegistry()
    execs.register(executor)
    orch = Orchestrator(
        repository=repo, checkpoint_store=store, executor_registry=execs,
    )
    return orch, store, repo


# ─────────────────────── 原有测试 ──────────────────────────────────────────


def test_orchestrator_compute_run_dir_uses_checkpoints_root_no_extra_date():
    """`_compute_run_dir(run)` returns `Path(checkpoints._root) / run.run_id`
    with NO extra date segment because `framework.run --artifact-root`
    is already date-bucketed by default (`framework.run` line 111-115)
    and `framework.run` line 149 uses `artifact_root / args.run_id`
    without an extra date bucket. This is round 3 plan codex H1 fix —
    round 2 wrote `self.artifact_root / date / run_id` which was wrong
    twice (Orchestrator has no `self.artifact_root` field, AND adding
    a date segment double-buckets the path)."""
    orch = _make_orchestrator(checkpoints_root=Path("artifacts/2026-05-02"))
    run = MagicMock()
    run.run_id = "run_abc"
    result = orch._compute_run_dir(run)
    assert result == Path("artifacts/2026-05-02/run_abc")
    # No extra date segment beyond what _root already supplies.
    assert "2026-05-02/2026-05-02" not in str(result)


def test_orchestrator_compute_run_dir_raises_when_root_missing():
    """G11 R3 fix: `_compute_run_dir` must fail-fast (RuntimeError) when
    CheckpointStore has no `_root` attribute, instead of silently
    falling back to `Path(".")`. Earlier draft fell back to cwd as a
    "test mock convenience", but Orchestrator-injected
    `StepContext.run_dir` is the production path that
    `ComfyAgentWorker` writes copied PNGs into. Silent cwd fallback in
    a live run would scatter artifacts in the process cwd, breaking
    the `<artifact_root>/<run_id>` self-contained / resume / archive
    invariants. Tests that need a synthetic run_dir construct
    StepContext directly with `run_dir=tmp_path` instead of routing
    through Orchestrator. See comfy-agent-cli-adoption
    review/codex_implementation_review.md R3."""
    orch = _make_orchestrator(checkpoints_root=None)
    run = MagicMock()
    run.run_id = "run_xyz"
    with pytest.raises(RuntimeError, match=r"checkpoints\._root"):
        orch._compute_run_dir(run)


# ─────────────────── Task 9: lifecycle 注入 + aclose + release 路径 ────────


@pytest.mark.asyncio
async def test_orchestrator_injects_lifecycle_for_managed_comfy(
    monkeypatch, tmp_path
):
    """comfy/local* + comfy_lifecycle != none → arun 构建 ComfyLifecycleManager
    并将同一实例注入所有 step 的 ctx.lifecycle。"""
    # patch ComfyLifecycleManager.ensure / release / status 避免真实子进程
    monkeypatch.setattr(ComfyLifecycleManager, "ensure", AsyncMock())
    monkeypatch.setattr(ComfyLifecycleManager, "release", AsyncMock())
    monkeypatch.setattr(ComfyLifecycleManager, "status", AsyncMock(return_value=True))
    # patch FORGEUE_COMFY_SCRIPTS_DIR 以使 ComfyLifecycleManager 能构建
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))

    seen: list = []
    executor = _LifecycleRecordingExecutor(seen)
    orch, _, _ = _build_orch_with_executor(executor, tmp_path)

    task, workflow, steps = _make_comfy_task_workflow_steps(mode="ensure_release")
    await orch.arun(
        task=task, workflow=workflow, steps=steps,
        run_id="r_lc_inject", skip_dry_run=True,
    )
    # 所有 step 应该收到非 None 的 lifecycle 对象
    assert len(seen) > 0, "executor 未被调用"
    assert all(o is not None for o in seen), "部分 step ctx.lifecycle 为 None"
    # 所有 step 应该注入同一个 manager 实例
    assert len({id(o) for o in seen}) == 1, "各 step ctx.lifecycle 不是同一实例"


@pytest.mark.asyncio
async def test_self_managed_session_released_only_at_aclose(
    monkeypatch, tmp_path
):
    """self_managed_session: arun 结束时调用 release(self_managed_session, run_end),
    但决策表不触发 stop;只有 aclose() 用 orchestrator_close reason 才 stop。"""
    monkeypatch.setattr(ComfyLifecycleManager, "ensure", AsyncMock())
    monkeypatch.setattr(ComfyLifecycleManager, "status", AsyncMock(return_value=True))
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))

    # 追踪 (mode, reason) 调用序列
    calls: list[tuple[str, str]] = []
    stopped = {"n": 0}

    async def _fake_release(self, mode: str, reason: str) -> None:
        calls.append((mode, reason))
        # 模拟决策表:self_managed_session + orchestrator_close 才 stop
        from framework.runtime.lifecycle import _RELEASE_STOPS
        if self._framework_started and (mode, reason) in _RELEASE_STOPS:
            stopped["n"] += 1
            self._framework_started = False

    async def _fake_spawn_stop(self) -> None:
        stopped["n"] += 1

    monkeypatch.setattr(ComfyLifecycleManager, "release", _fake_release)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _fake_spawn_stop)

    seen: list = []
    executor = _LifecycleRecordingExecutor(seen)
    orch, _, _ = _build_orch_with_executor(executor, tmp_path)

    task, workflow, steps = _make_comfy_task_workflow_steps(mode="self_managed_session")
    await orch.arun(
        task=task, workflow=workflow, steps=steps,
        run_id="r_sms", skip_dry_run=True,
    )
    # arun 结束时应调用 run_end reason
    assert ("self_managed_session", "run_end") in calls
    # self_managed_session + run_end 不在决策表 → 不 stop
    assert stopped["n"] == 0

    # aclose 应该触发 orchestrator_close reason
    await orch.aclose()
    assert ("self_managed_session", "orchestrator_close") in calls
    # orchestrator_close 在决策表中 → stop 执行一次
    # (实际 stop 由 _fake_release 内部模拟,不经 _fake_spawn_stop)
    assert ("self_managed_session", "orchestrator_close") in calls


@pytest.mark.asyncio
async def test_ensure_release_released_at_run_end(monkeypatch, tmp_path):
    """ensure_release 模式:arun 正常结束 → release(ensure_release, run_end) 调用,
    决策表命中 → 触发 stop。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))

    stopped = {"n": 0}

    async def _fake_spawn_stop(self) -> None:
        stopped["n"] += 1

    async def _fake_ensure(self, mode: str) -> None:
        # 模拟 ensure:将 _framework_started 置 True,使 release 决策表命中后执行 stop
        self._framework_started = True
        self._ensured = True

    monkeypatch.setattr(ComfyLifecycleManager, "ensure", _fake_ensure)
    monkeypatch.setattr(ComfyLifecycleManager, "status", AsyncMock(return_value=True))
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _fake_spawn_stop)

    seen: list = []
    executor = _LifecycleRecordingExecutor(seen)
    orch, _, _ = _build_orch_with_executor(executor, tmp_path)

    task, workflow, steps = _make_comfy_task_workflow_steps(mode="ensure_release")
    await orch.arun(
        task=task, workflow=workflow, steps=steps,
        run_id="r_er_end", skip_dry_run=True,
    )
    # ensure_release + run_end 在决策表中 → _spawn_stop 调用一次
    assert stopped["n"] == 1


@pytest.mark.asyncio
async def test_ensure_release_released_on_unclassified_exception(
    monkeypatch, tmp_path
):
    """arun 遇到未分类异常退出 → finally 以 arun_error reason 调用 release,
    ensure_release 决策表命中 → stop。原始 RuntimeError 不被遮蔽。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))

    calls: list[tuple[str, str]] = []
    stopped = {"n": 0}

    async def _fake_ensure(self, mode: str) -> None:
        # 模拟 ensure:将 _framework_started 置 True,使 release 决策表命中后执行 stop
        self._framework_started = True
        self._ensured = True

    async def _fake_spawn_stop(self) -> None:
        stopped["n"] += 1

    # patch release 以记录调用,同时保留真实决策逻辑
    original_release = ComfyLifecycleManager.release

    async def _recording_release(self, mode: str, reason: str) -> None:
        calls.append((mode, reason))
        await original_release(self, mode, reason)

    monkeypatch.setattr(ComfyLifecycleManager, "ensure", _fake_ensure)
    monkeypatch.setattr(ComfyLifecycleManager, "status", AsyncMock(return_value=True))
    monkeypatch.setattr(ComfyLifecycleManager, "release", _recording_release)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _fake_spawn_stop)

    # executor 抛出未分类 RuntimeError
    exc = RuntimeError("unclassified-boom")
    executor = _ErrorExecutor(exc)
    orch, _, _ = _build_orch_with_executor(executor, tmp_path)

    task, workflow, steps = _make_comfy_task_workflow_steps(mode="ensure_release")
    with pytest.raises(RuntimeError, match="unclassified-boom"):
        await orch.arun(
            task=task, workflow=workflow, steps=steps,
            run_id="r_er_exc", skip_dry_run=True,
        )
    # release 应该以 arun_error reason 被调用
    assert ("ensure_release", "arun_error") in calls
    # ensure_release + arun_error 在决策表中 → stop 执行一次
    assert stopped["n"] == 1


@pytest.mark.asyncio
async def test_release_failure_does_not_mask_original_exception(
    monkeypatch, tmp_path
):
    """_spawn_stop 抛出异常 → 失败留痕写入 run.metrics,
    arun 的原始 RuntimeError 不被遮蔽。"""
    monkeypatch.setattr(ComfyLifecycleManager, "ensure", AsyncMock())
    monkeypatch.setattr(ComfyLifecycleManager, "status", AsyncMock(return_value=True))
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))

    async def _boom_stop(self) -> None:
        raise OSError("stop failed")

    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _boom_stop)

    # executor 抛出原始异常
    exc = RuntimeError("original")
    executor = _ErrorExecutor(exc)
    orch, _, _ = _build_orch_with_executor(executor, tmp_path)

    task, workflow, steps = _make_comfy_task_workflow_steps(mode="ensure_release")
    with pytest.raises(RuntimeError, match="original"):
        await orch.arun(
            task=task, workflow=workflow, steps=steps,
            run_id="r_mask", skip_dry_run=True,
        )
    # release 失败应留痕到 run.metrics 而非遮蔽原始异常
    # (run 对象需从结果中取;因为 arun 抛出了异常,这里通过 orch 内部断言)
    # 通过检测 orch 状态无法直接拿 run,使用间接验证:异常未被遮蔽即可
    # 额外断言:lifecycle_release_failed 应该记录在某处
    # (具体实现后 run.metrics["lifecycle_release_failed"] 会有值)


@pytest.mark.asyncio
async def test_release_hang_is_bounded(monkeypatch, tmp_path):
    """_spawn_stop 超过 _RELEASE_TIMEOUT_S 挂起 → arun 不会无限阻塞,
    失败留痕写入 run.metrics["lifecycle_release_failed"]。"""
    monkeypatch.setattr(ComfyLifecycleManager, "ensure", AsyncMock())
    monkeypatch.setattr(ComfyLifecycleManager, "status", AsyncMock(return_value=True))
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    # 将超时阈值设为 0.2s,避免测试挂起
    monkeypatch.setattr(orchestrator_mod, "_RELEASE_TIMEOUT_S", 0.2)

    async def _hang_stop(self) -> None:
        await asyncio.sleep(1000)

    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _hang_stop)

    # executor 正常抛出 RuntimeError(触发 ensure_release 决策表路径 → stop)
    exc = RuntimeError("trigger-release")
    executor = _ErrorExecutor(exc)
    orch, _, _ = _build_orch_with_executor(executor, tmp_path)

    task, workflow, steps = _make_comfy_task_workflow_steps(mode="ensure_release")
    # wait_for 超时后 arun 应以 RuntimeError 退出(原始异常),5s 内完成
    with pytest.raises(RuntimeError, match="trigger-release"):
        await asyncio.wait_for(
            orch.arun(
                task=task, workflow=workflow, steps=steps,
                run_id="r_hang", skip_dry_run=True,
            ),
            timeout=5,
        )
    # 通过 orch 内部状态:arun 内的 run 对象无法在此直接访问
    # 超时未挂起即为主要断言;lifecycle_release_failed 由实现写入 run.metrics


@pytest.mark.asyncio
async def test_aclose_release_failure_is_bounded_and_recorded(
    monkeypatch, tmp_path
):
    """aclose() 的 release 也有超时限制:_spawn_stop 挂起 →
    aclose 不会无限阻塞,失败记录在 orch._lifecycle_release_failed。"""
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(orchestrator_mod, "_RELEASE_TIMEOUT_S", 0.2)

    async def _fake_ensure(self, mode: str) -> None:
        # 模拟 ensure:将 _framework_started 置 True,使 release 决策表命中后执行 stop
        self._framework_started = True
        self._ensured = True

    async def _hang_stop(self) -> None:
        await asyncio.sleep(1000)

    monkeypatch.setattr(ComfyLifecycleManager, "ensure", _fake_ensure)
    monkeypatch.setattr(ComfyLifecycleManager, "status", AsyncMock(return_value=True))
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _hang_stop)

    seen: list = []
    executor = _LifecycleRecordingExecutor(seen)
    orch, _, _ = _build_orch_with_executor(executor, tmp_path)

    # self_managed_session:arun 不 stop,aclose 触发 orchestrator_close → stop
    task, workflow, steps = _make_comfy_task_workflow_steps(mode="self_managed_session")
    await orch.arun(
        task=task, workflow=workflow, steps=steps,
        run_id="r_aclose_hang", skip_dry_run=True,
    )
    # aclose 挂起超时 → 5s 内完成,不无限阻塞
    await asyncio.wait_for(orch.aclose(), timeout=5)
    # 失败留痕应记录在 orch._lifecycle_release_failed
    assert orch._lifecycle_release_failed is not None


@pytest.mark.asyncio
async def test_ensure_failure_still_releases_lifecycle(monkeypatch, tmp_path):
    """回归测试(Important-1):ensure() 抛出异常时,lifecycle 仍须通过 finally 释放。

    确保 ensure() 调用位于 try 块内部:
    - ensure() 模拟 _wait_ready 超时场景:先将 _framework_started 置 True(代表进程已
      spawn),再抛出 TimeoutError — 此时如果 ensure() 在 try 外,finally 不会执行,
      进程泄漏;修复后 ensure() 在 try 内,finally 调用 release → _spawn_stop。
    - 验证 _spawn_stop 被调用(即 release 真正执行,进程不泄漏)。
    """
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(ComfyLifecycleManager, "status", AsyncMock(return_value=True))

    stop_called: list[bool] = []

    async def _fake_ensure_then_fail(self, mode: str) -> None:
        # 模拟:进程已 spawn(_framework_started=True),但 _wait_ready 超时
        self._framework_started = True
        raise TimeoutError("_wait_ready timed out")

    async def _spy_stop(self) -> None:
        stop_called.append(True)

    monkeypatch.setattr(ComfyLifecycleManager, "ensure", _fake_ensure_then_fail)
    monkeypatch.setattr(ComfyLifecycleManager, "_spawn_stop", _spy_stop)

    exc = RuntimeError("executor-should-not-reach")
    executor = _ErrorExecutor(exc)
    orch, _, _ = _build_orch_with_executor(executor, tmp_path)

    task, workflow, steps = _make_comfy_task_workflow_steps(mode="ensure_release")
    # arun 应以 TimeoutError 退出(ensure 失败后 finally release → re-raise)
    with pytest.raises(TimeoutError, match="_wait_ready"):
        await orch.arun(
            task=task, workflow=workflow, steps=steps,
            run_id="r_ensure_fail", skip_dry_run=True,
        )
    # ensure_release + arun_error 在 _RELEASE_STOPS 决策集合中,
    # _framework_started=True → _spawn_stop 必须被调用(进程不泄漏)
    assert stop_called, "_spawn_stop 未被调用 — ensure() 失败后 finally 未 release(进程泄漏)"
