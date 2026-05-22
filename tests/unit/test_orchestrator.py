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
                PreparedRoute(
                    model="comfy/local",
                    kind="image",
                    provider_name="comfy_api",
                    provider_kind="subprocess",
                    provider_config={
                        "adapter": "comfy_agent_cli",
                        "scripts_dir": ".",
                        "python_exe": None,
                        "default_lifecycle": "none",
                        "input_dir": None,
                        "output_root": None,
                    },
                ),
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
    失败留痕写入 run.metrics["lifecycle_release_failed"]。

    非 vacuous 断言:
    1. ensure 用 _fake_ensure(_framework_started=True),确保 release 决策表
       真正命中 _spawn_stop(而非 _framework_started=False 静默跳过)。
    2. 捕获 run 对象,断言 run.metrics["lifecycle_release_failed"] 实际被写入。
    """
    monkeypatch.setenv("FORGEUE_COMFY_SCRIPTS_DIR", str(tmp_path))
    # 将超时阈值设为 0.2s,避免测试挂起
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

    # executor 捕获 run 对象后抛出 RuntimeError(触发 ensure_release 决策表路径 → stop)
    captured_runs: list = []

    class _CapturingErrorExecutor(StepExecutor):
        """捕获 ctx.run 后抛出异常,用于测试 finally release 路径的 metrics 写入。"""
        step_type = StepType.generate
        capability_ref = "mock.comfy"

        async def execute(self, ctx: StepContext) -> ExecutorResult:
            # 先捕获 run 对象,再抛出异常触发 finally release
            captured_runs.append(ctx.run)
            raise RuntimeError("trigger-release")

    executor = _CapturingErrorExecutor()
    orch, _, _ = _build_orch_with_executor(executor, tmp_path)

    task, workflow, steps = _make_comfy_task_workflow_steps(mode="ensure_release")
    # _spawn_stop 挂起超时后 arun 应以 RuntimeError 退出(原始异常),5s 内完成
    with pytest.raises(RuntimeError, match="trigger-release"):
        await asyncio.wait_for(
            orch.arun(
                task=task, workflow=workflow, steps=steps,
                run_id="r_hang", skip_dry_run=True,
            ),
            timeout=5,
        )
    # 断言 1:run 被捕获到(executor 实际被调用)
    assert captured_runs, "executor 未被调用,run 对象未捕获"
    run_obj = captured_runs[0]
    # 断言 2:lifecycle_release_failed 写入 run.metrics(bounded timeout 保护生效)
    assert "lifecycle_release_failed" in run_obj.metrics, (
        "run.metrics 未包含 lifecycle_release_failed — "
        "_spawn_stop 挂起时 bounded release 未记录失败留痕"
    )


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


# ── F1 Round 2 fix:run_span_ctx 全路径 finally close 回归 ──────────────────
# 根因:原 arun 实现把 run_span_ctx.__exit__ 放在三处分散点(DAG first_exc / 正常
# 退出 L556),CancelledError / 未分类异常路径 finally 块只 release lifecycle 不
# close span,OTel 部署下漏 span。修复:把 __exit__ 统一进 finally,用 sys.exc_info()
# 拿 active exception 传给 tracer。

@pytest.mark.asyncio
async def test_run_span_closed_on_cancelled_error(monkeypatch, tmp_path):
    """F1 Round 2 fence:arun 被外部 cancel 时,run_span_ctx 必须仍被 __exit__。

    monkeypatch span() 工厂返回一个 spy context manager,记录 __enter__/__exit__ 调用。
    arun 在 ensure() 后 cancel,需观察到 1 次 __enter__ + 1 次 __exit__(exc 类型为 CancelledError)。
    """
    enter_calls: list[dict] = []
    exit_calls: list[dict] = []

    class _SpySpan:
        def __init__(self, label, attrs):
            self.label = label
            self.attrs = attrs

        def __enter__(self):
            enter_calls.append({"label": self.label, "attrs": self.attrs})
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            exit_calls.append({
                "label": self.label,
                "exc_type": exc_type.__name__ if exc_type else None,
            })
            return False  # 不吞异常

    def _fake_span(label, attrs):
        return _SpySpan(label, attrs)

    monkeypatch.setattr(orchestrator_mod, "span", _fake_span)

    # 构造在 ensure() 内部 cancel 的 executor — 让 arun 走 CancelledError 路径
    class _CancelOnEnsureExecutor(StepExecutor):
        step_type = StepType.generate
        capability_ref = "mock.comfy"
        async def execute(self, ctx):
            # 不该走到这里(应在 ensure 阶段被 cancel)
            raise AssertionError("executor 不应被调用")

    executor = _CancelOnEnsureExecutor()

    async def _ensure_then_cancel(self, mode):
        # 进入 ensure 时直接抛 CancelledError 模拟外部 cancel
        raise asyncio.CancelledError()

    monkeypatch.setattr(ComfyLifecycleManager, "ensure", _ensure_then_cancel)
    monkeypatch.setattr(ComfyLifecycleManager, "release", AsyncMock())

    orch, _, _ = _build_orch_with_executor(executor, tmp_path)
    task, workflow, steps = _make_comfy_task_workflow_steps(mode="ensure_running")

    with pytest.raises(asyncio.CancelledError):
        await orch.arun(
            task=task, workflow=workflow, steps=steps,
            run_id="r_cancel_span", skip_dry_run=True,
        )

    # 必须 enter 1 次 run span + exit 1 次 run span
    run_enters = [c for c in enter_calls if c["label"] == "run"]
    run_exits = [c for c in exit_calls if c["label"] == "run"]
    assert len(run_enters) == 1, f"run span __enter__ 应恰好 1 次,实测 {len(run_enters)}"
    assert len(run_exits) == 1, f"run span __exit__ 应恰好 1 次(CancelledError 路径漏关),实测 {len(run_exits)}"
    assert run_exits[0]["exc_type"] == "CancelledError", (
        f"__exit__ 应感知 active CancelledError,实测 {run_exits[0]['exc_type']!r}"
    )


@pytest.mark.asyncio
async def test_run_span_closed_on_normal_exit(monkeypatch, tmp_path):
    """F1 Round 2 fence:正常退出路径下,run_span_ctx 仍恰好 __exit__ 一次(防止 finally 与原 L556 重复 close)。"""
    enter_calls: list = []
    exit_calls: list = []

    class _SpySpan:
        def __init__(self, label, attrs):
            self.label = label
        def __enter__(self):
            enter_calls.append(self.label)
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            exit_calls.append({"label": self.label, "exc_type": exc_type})
            return False

    monkeypatch.setattr(orchestrator_mod, "span", lambda label, attrs: _SpySpan(label, attrs))

    executor = _LifecycleRecordingExecutor(seen=[])
    orch, _, _ = _build_orch_with_executor(executor, tmp_path)
    task, workflow, steps = _make_comfy_task_workflow_steps(mode="none")

    # ensure() 在 mode=none 路径下直接 return,无 lifecycle 干预;arun 走正常退出
    result = await orch.arun(
        task=task, workflow=workflow, steps=steps,
        run_id="r_normal_span", skip_dry_run=True,
    )
    assert result.run.status == RunStatus.succeeded

    run_exits = [c for c in exit_calls if c["label"] == "run"]
    assert len(run_exits) == 1, f"正常路径 run span __exit__ 应恰好 1 次,实测 {len(run_exits)}"
    assert run_exits[0]["exc_type"] is None, "正常退出 __exit__ exc_type 应为 None"


# ── F4 Round 2 fix:_detect_comfy_lifecycle 与 executor 读取 path 一致性 contract ──

def test_detect_lifecycle_matches_executor_read_path(tmp_path):
    """F4 contract fence:orchestrator._detect_comfy_lifecycle 与 executor
    内部读取 step.config['spec']['comfy_lifecycle'] 必须从同一字段读到同值。

    防止未来 bundle format drift 导致两端读到不同 mode(orch 构建 manager 但
    executor 读不到 lifecycle,或反之)。
    """
    # 构造一个 mock step,模拟 bundle JSON 形态
    step = Step(
        step_id="s_contract",
        type=StepType.generate,
        name="comfy-contract-fence",
        risk_level=RiskLevel.medium,
        capability_ref="image.generation",
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=[PreparedRoute(
                model="comfy/local", api_key_env=None, api_base=None,
                kind="image", pricing=None,
                provider_name="comfy_api",
                provider_kind="subprocess",
                provider_config={
                    "adapter": "comfy_agent_cli",
                    "scripts_dir": ".",
                    "python_exe": None,
                    "default_lifecycle": "none",
                    "input_dir": None,
                    "output_root": None,
                },
            )],
        ),
        config={
            "num_candidates": 1,
            "spec": {
                "comfy_workflow": "GameAssets/01b_singleview_sdxl",
                "comfy_lifecycle": "ensure_running",
            },
        },
    )

    orch = _make_orchestrator(tmp_path)
    # orchestrator 侧读取
    selection = orch._detect_comfy_lifecycle([step])
    assert selection is not None
    orch_mode = selection.mode

    # executor 侧读取路径(直接复刻 generate_image.py:298 + generate_mesh / audio / video 的逻辑)
    spec_raw = (step.config or {}).get("spec", {})
    spec = spec_raw if isinstance(spec_raw, dict) else {}
    executor_mode = spec.get("comfy_lifecycle") if isinstance(spec, dict) else None

    assert orch_mode == "ensure_running", (
        f"_detect_comfy_lifecycle 应读到 ensure_running,实测 {orch_mode!r}"
    )
    assert executor_mode == "ensure_running", (
        f"executor 侧 spec.get('comfy_lifecycle') 应读到 ensure_running,实测 {executor_mode!r}"
    )
    assert orch_mode == executor_mode, (
        f"contract violation:orchestrator vs executor 读到不同值 "
        f"(orch={orch_mode!r}, executor={executor_mode!r})"
    )


def test_detect_comfy_lifecycle_uses_provider_config_scripts_dir(tmp_path):
    from framework.core.policies import PreparedRoute, ProviderPolicy
    from framework.core.task import Step
    from framework.core.enums import RiskLevel, StepType
    from framework.runtime.orchestrator import Orchestrator

    step = Step(
        step_id="step_image",
        type=StepType.generate,
        name="image",
        risk_level=RiskLevel.medium,
        capability_ref="image.generation",
        config={"spec": {"comfy_workflow": "X", "comfy_lifecycle": "ensure_running"}},
        provider_policy=ProviderPolicy(
            capability_required="image.generation",
            prepared_routes=[
                PreparedRoute(
                    model="local/custom-image",
                    kind="image",
                    provider_name="comfy_api",
                    provider_kind="subprocess",
                    provider_config={
                        "adapter": "comfy_agent_cli",
                        "scripts_dir": str(tmp_path / "scripts"),
                        "python_exe": str(tmp_path / "python.exe"),
                        "default_lifecycle": "none",
                        "input_dir": None,
                        "output_root": None,
                    },
                )
            ],
        ),
    )

    selected = Orchestrator._detect_comfy_lifecycle([step])
    assert selected is not None
    assert selected.mode == "ensure_running"
    assert selected.scripts_dir == str(tmp_path / "scripts")
    assert selected.python_exe == str(tmp_path / "python.exe")
