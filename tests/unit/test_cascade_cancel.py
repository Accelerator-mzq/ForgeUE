"""Plan C Phase 7 — DAG fan-out failure semantics.

当某一叶节点抛出非可分类异常时,orchestrator 的 asyncio.wait(FIRST_COMPLETED)
立即检测到,取消其余兄弟任务,并将原始异常透传到 run()。

executor-async-rewrite Task 6 后,所有 executor 均为原生 async def execute;
CancelledError 可直接打入 awaiting executor coroutine,取消立即生效。

Task 7:cascade-cancel 从"开火即忘"升级为"真停":
  cancel() 后 await asyncio.wait(pending, timeout=_CASCADE_DRAIN_TIMEOUT_S)
  确认 sibling 工作真正中断;drain 超时(清理卡死)时显式失败,不静默丢弃。
"""
from __future__ import annotations

import asyncio
import unittest.mock

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.enums import RiskLevel, RunMode, RunStatus, StepType, TaskType
from framework.core.task import Step, Task, Workflow
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.executors.base import (
    ExecutorRegistry,
    ExecutorResult,
    StepContext,
    StepExecutor,
)
from framework.runtime.orchestrator import Orchestrator


class _OkExecutor(StepExecutor):
    step_type = StepType.generate
    capability_ref = "mock.ok"

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        import asyncio
        from framework.core.artifact import ArtifactType, Lineage, ProducerRef
        from framework.core.enums import ArtifactRole, PayloadKind
        # 原生 async 等待,短延迟确保并发可见
        await asyncio.sleep(0.05)
        art = ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_out",
            value={"done": ctx.step.step_id},
            artifact_type=ArtifactType(
                modality="text", shape="structured", display_name="mock_text",
            ),
            role=ArtifactRole.intermediate,
            format="json", mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider="mock", model="m",
            ),
            lineage=Lineage(
                source_artifact_ids=[], source_step_ids=[ctx.step.step_id],
            ),
        )
        return ExecutorResult(artifacts=[art], metrics={})


class _FailExecutor(StepExecutor):
    step_type = StepType.generate
    capability_ref = "mock.fail"

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        # 非可分类异常 — orchestrator 将直接 re-raise 而非合成 Verdict
        raise KeyError(f"boom from {ctx.step.step_id}")


def test_dag_failure_cancels_sibling(tmp_path):
    steps = [
        Step(step_id="leaf_ok", type=StepType.generate, name="ok",
             capability_ref="mock.ok", risk_level=RiskLevel.low),
        Step(step_id="leaf_fail", type=StepType.generate, name="fail",
             capability_ref="mock.fail", risk_level=RiskLevel.low),
    ]
    workflow = Workflow(
        workflow_id="wf_cc", name="cascade_cancel", version="1",
        entry_step_id="leaf_ok",
        step_ids=["leaf_ok", "leaf_fail"],
    )
    task = Task(
        task_id="t_cc", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="t",
        input_payload={}, expected_output={},
        project_id="p_cc", constraints={"parallel_dag": True},
    )
    registry = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=registry)
    store = CheckpointStore(artifact_root=tmp_path)
    execs = ExecutorRegistry()
    execs.register(_OkExecutor())
    execs.register(_FailExecutor())
    orch = Orchestrator(
        repository=repo, checkpoint_store=store, executor_registry=execs,
    )

    with pytest.raises(KeyError, match="boom"):
        orch.run(task=task, workflow=workflow, steps=steps, run_id="r_cc")


class _CostlyExecutor(StepExecutor):
    """Produces one artifact + metrics[cost_usd] large enough to blow the
    budget cap. Orchestrator sees cost_usd > cap after this step and
    returns _StepOutcome(terminate=True) — a NORMAL return, not a raised
    exception. The previous implementation waited for siblings via
    FIRST_EXCEPTION and therefore didn't cascade-cancel on this path.
    """

    step_type = StepType.generate
    capability_ref = "mock.costly"

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        import asyncio
        from framework.core.artifact import ArtifactType, Lineage, ProducerRef
        from framework.core.enums import ArtifactRole, PayloadKind
        # 短延迟以确保并发调度可见
        await asyncio.sleep(0.02)
        art = ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_out",
            value={"x": 1},
            artifact_type=ArtifactType(
                modality="text", shape="structured", display_name="x",
            ),
            role=ArtifactRole.intermediate,
            format="json", mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider="mock", model="m",
            ),
            lineage=Lineage(
                source_artifact_ids=[], source_step_ids=[ctx.step.step_id],
            ),
        )
        return ExecutorResult(artifacts=[art], metrics={"cost_usd": 10.0})


class _SlowSiblingExecutor(StepExecutor):
    """Takes longer than the costly step. If cascade-cancel works, the
    orchestrator task wrapping this executor is cancelled at the
    `await asyncio.to_thread(...)` boundary before the post-exec
    `run.artifact_ids.extend(...)` commit runs, so this step's artifact
    id never appears in `run.artifact_ids`. (The underlying thread itself
    is uninterruptible and does still finish.)
    """

    step_type = StepType.generate
    capability_ref = "mock.slow_sibling"

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        import asyncio
        from framework.core.artifact import ArtifactType, Lineage, ProducerRef
        from framework.core.enums import ArtifactRole, PayloadKind
        # 长延迟模拟慢速兄弟步骤;原生 async 允许 CancelledError 打入
        await asyncio.sleep(0.5)
        art = ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_out",
            value={"y": 1},
            artifact_type=ArtifactType(
                modality="text", shape="structured", display_name="y",
            ),
            role=ArtifactRole.intermediate,
            format="json", mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider="mock", model="m",
            ),
            lineage=Lineage(
                source_artifact_ids=[], source_step_ids=[ctx.step.step_id],
            ),
        )
        return ExecutorResult(artifacts=[art], metrics={})


class _FlakyThenOkExecutor(StepExecutor):
    """First call raises a classifiable ProviderTimeout (→ Decision.retry_same_step);
    subsequent calls produce one artifact. Used to verify DAG-mode retry semantics."""

    step_type = StepType.generate
    capability_ref = "mock.flaky"

    def __init__(self) -> None:
        self.call_count = 0

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        from framework.core.artifact import ArtifactType, Lineage, ProducerRef
        from framework.core.enums import ArtifactRole, PayloadKind
        from framework.providers.base import ProviderTimeout

        self.call_count += 1
        if self.call_count < 2:
            raise ProviderTimeout("simulated first-call timeout")
        art = ctx.repository.put(
            artifact_id=f"{ctx.run.run_id}_{ctx.step.step_id}_out",
            value={"attempts": self.call_count},
            artifact_type=ArtifactType(
                modality="text", shape="structured", display_name="flaky",
            ),
            role=ArtifactRole.intermediate,
            format="json", mime_type="application/json",
            payload_kind=PayloadKind.inline,
            producer=ProducerRef(
                run_id=ctx.run.run_id, step_id=ctx.step.step_id,
                provider="mock", model="m",
            ),
            lineage=Lineage(
                source_artifact_ids=[], source_step_ids=[ctx.step.step_id],
            ),
        )
        return ExecutorResult(artifacts=[art], metrics={})


def test_dag_retry_same_step_reexecutes(tmp_path):
    """Codex P1 #1: when a DAG branch's outcome carries
    `next_step_id == step.step_id` (the TransitionEngine's signal for
    `Decision.retry_same_step`), the orchestrator must re-run that step
    instead of breaking out of the outer loop. The previous code's
    `if next_id == current: break` defeated every classifiable-failure
    retry in DAG mode (provider_timeout, schema_validation_fail,
    worker_timeout)."""
    flaky = _FlakyThenOkExecutor()
    steps = [
        Step(step_id="flaky_leaf", type=StepType.generate, name="flaky",
             capability_ref="mock.flaky", risk_level=RiskLevel.low),
    ]
    workflow = Workflow(
        workflow_id="wf_retry", name="dag_retry", version="1",
        entry_step_id="flaky_leaf",
        step_ids=["flaky_leaf"],
    )
    task = Task(
        task_id="t_retry", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="t",
        input_payload={}, expected_output={},
        project_id="p_retry", constraints={"parallel_dag": True},
    )
    registry = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=registry)
    store = CheckpointStore(artifact_root=tmp_path)
    execs = ExecutorRegistry()
    execs.register(flaky)
    orch = Orchestrator(
        repository=repo, checkpoint_store=store, executor_registry=execs,
    )

    result = orch.run(
        task=task, workflow=workflow, steps=steps, run_id="r_retry",
    )

    assert result.run.status == RunStatus.succeeded
    # Executor must have been called at least twice (first raised, second succeeded).
    assert flaky.call_count >= 2, f"retry did not re-execute: {flaky.call_count}"
    # Final artifact committed.
    assert any("flaky_leaf" in aid for aid in result.run.artifact_ids)


def test_dag_terminate_true_cancels_sibling(tmp_path):
    """Codex P1 #2: `_StepOutcome(terminate=True)` must cascade-cancel
    sibling DAG branches. Previously FIRST_EXCEPTION only caught raised
    exceptions, so budget-exceeded / transition-terminate branches let
    siblings run to completion (wasting external calls)."""
    from framework.core.policies import BudgetPolicy

    steps = [
        Step(step_id="costly", type=StepType.generate, name="costly",
             capability_ref="mock.costly", risk_level=RiskLevel.low),
        Step(step_id="slow", type=StepType.generate, name="slow",
             capability_ref="mock.slow_sibling", risk_level=RiskLevel.low),
    ]
    workflow = Workflow(
        workflow_id="wf_ct", name="cascade_terminate", version="1",
        entry_step_id="costly",
        step_ids=["costly", "slow"],
    )
    task = Task(
        task_id="t_ct", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="t",
        input_payload={}, expected_output={},
        project_id="p_ct", constraints={"parallel_dag": True},
        budget_policy=BudgetPolicy(total_cost_cap_usd=1.0),
    )
    registry = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=registry)
    store = CheckpointStore(artifact_root=tmp_path)
    execs = ExecutorRegistry()
    execs.register(_CostlyExecutor())
    execs.register(_SlowSiblingExecutor())
    orch = Orchestrator(
        repository=repo, checkpoint_store=store, executor_registry=execs,
    )

    result = orch.run(
        task=task, workflow=workflow, steps=steps, run_id="r_ct",
    )

    # Budget termination reason recorded.
    assert result.run.metrics.get("termination_reason", "").startswith(
        "budget_exceeded"
    )
    # Costly step's artifact committed.
    assert any("costly" in aid for aid in result.run.artifact_ids)
    # Slow sibling MUST NOT have its artifact id committed — the await on
    # asyncio.to_thread was cancelled before the commit line ran.
    assert not any("slow" in aid for aid in result.run.artifact_ids), (
        f"sibling was not cascade-cancelled: {result.run.artifact_ids}"
    )


# ---------------------------------------------------------------------------
# Task 7 新测试:cascade-cancel 真停 + drain 超时显式失败
# ---------------------------------------------------------------------------

def _make_two_step_dag_fixture(tmp_path, fail_executor, slow_executor):
    """构建两步 DAG fan-out:leaf_fail + leaf_slow 并发执行。
    返回 (orch, task, workflow, steps) 供调用方直接 run。
    """
    steps = [
        Step(
            step_id="leaf_fail",
            type=StepType.generate,
            name="fail",
            capability_ref=fail_executor.capability_ref,
            risk_level=RiskLevel.low,
        ),
        Step(
            step_id="leaf_slow",
            type=StepType.generate,
            name="slow",
            capability_ref=slow_executor.capability_ref,
            risk_level=RiskLevel.low,
        ),
    ]
    workflow = Workflow(
        workflow_id="wf_t7",
        name="task7_dag",
        version="1",
        entry_step_id="leaf_fail",
        step_ids=["leaf_fail", "leaf_slow"],
    )
    task = Task(
        task_id="t_t7",
        task_type=TaskType.asset_generation,
        run_mode=RunMode.production,
        title="t7",
        input_payload={},
        expected_output={},
        project_id="p_t7",
        constraints={"parallel_dag": True},
    )
    registry = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=registry)
    store = CheckpointStore(artifact_root=tmp_path)
    execs = ExecutorRegistry()
    execs.register(fail_executor)
    execs.register(slow_executor)
    orch = Orchestrator(
        repository=repo,
        checkpoint_store=store,
        executor_registry=execs,
    )
    return orch, task, workflow, steps


class _ImmediateFailExecutor(StepExecutor):
    """立即抛出非可分类异常,触发 cascade-cancel。"""

    step_type = StepType.generate
    capability_ref = "mock.t7_fail"

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        # 短暂让步确保 slow sibling 已开始循环
        await asyncio.sleep(0.02)
        raise KeyError("t7 immediate fail")


class _SlowTickingExecutor(StepExecutor):
    """持续自增计数器直到被取消。
    用于验证 cancel 后工作真正停止:若取消生效则计数器冻结。
    """

    step_type = StepType.generate
    capability_ref = "mock.t7_slow_tick"

    def __init__(self, ticks: dict) -> None:
        # ticks 为可变字典 {"n": 0},供外部读取
        self._ticks = ticks

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        for _ in range(1000):
            self._ticks["n"] += 1
            await asyncio.sleep(0.01)
        return ExecutorResult()


class _UncleanableExecutor(StepExecutor):
    """被 cancel 后在 except CancelledError 块内再次长时间 sleep,
    模拟清理卡死(不能在 drain timeout 内退出)。
    用于验证 drain 超时路径。
    """

    step_type = StepType.generate
    capability_ref = "mock.t7_uncleanable"

    async def execute(self, ctx: StepContext) -> ExecutorResult:
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            # 模拟清理卡死:再次 sleep 远超 drain timeout
            await asyncio.sleep(100)
            raise


@pytest.mark.asyncio
async def test_cascade_cancelled_sibling_work_actually_stops(tmp_path):
    """被取消的 sibling 工作真停 — 自增探针计数器反证。

    Task 7 修复前:cascade 发出 cancel() 但不 await 确认,sibling coroutine
    在事件循环空转期间仍能继续执行若干 tick。
    Task 7 修复后:cancel() + await asyncio.wait(pending, timeout=...) 确保
    sibling 真正停止;等待后计数器不再增长。
    """
    ticks: dict = {"n": 0}
    fail_exec = _ImmediateFailExecutor()
    slow_exec = _SlowTickingExecutor(ticks)

    orch, task, workflow, steps = _make_two_step_dag_fixture(tmp_path, fail_exec, slow_exec)

    # leaf_fail 抛出非可分类 KeyError,orchestrator re-raise
    with pytest.raises(KeyError, match="t7 immediate fail"):
        await orch.arun(
            task=task, workflow=workflow, steps=steps, run_id="r_t7_stop",
        )

    # 记录 cancel 发出后的计数器值
    n_at_cancel = ticks["n"]

    # 等待一段时间;若 cancel 真正生效,计数器应冻结
    await asyncio.sleep(0.2)

    # 取消后 sibling coroutine 必须已停止,不再自增
    assert ticks["n"] == n_at_cancel, (
        f"sibling 在 cancel 后仍运行:{n_at_cancel} -> {ticks['n']}"
    )


@pytest.mark.asyncio
async def test_cascade_drain_timeout_is_explicit_failure(tmp_path):
    """sibling cancel 后清理卡死 > drain timeout → 显式失败,不静默吞。

    Task 7:drain 超时时须在 run.metrics 中记录 "cancel_drain_timeout",
    并将 run.status 置为 RunStatus.failed。静默丢弃 still_pending task
    是不可接受的:用户必须能从 metrics 感知清理异常。
    """
    import framework.runtime.orchestrator as _orch_mod

    fail_exec = _ImmediateFailExecutor()
    unclean_exec = _UncleanableExecutor()

    orch, task, workflow, steps = _make_two_step_dag_fixture(
        tmp_path, fail_exec, unclean_exec,
    )

    # 把 drain timeout 压到 0.2s,避免测试等待 30s
    with unittest.mock.patch.object(_orch_mod, "_CASCADE_DRAIN_TIMEOUT_S", 0.2):
        # leaf_fail 抛出 KeyError → cascade-cancel → uncleanable 卡死 → drain timeout
        # drain timeout 后 orchestrator 应记录 metrics 再 re-raise first_exc
        with pytest.raises(KeyError, match="t7 immediate fail"):
            await orch.arun(
                task=task, workflow=workflow, steps=steps, run_id="r_t7_drain",
            )

    # first_exc re-raise 路径下 run 对象不通过 RunResult 暴露,无法直接断言;
    # 改用 spy:下方 _CapturingOrch 在 raise 前捕获 run 引用,
    # 再断言 run.metrics["cancel_drain_timeout"] + run.status == failed。
    captured_run = {}

    class _CapturingOrch(Orchestrator):
        async def arun(self, **kwargs):
            # 注入 spy 以捕获 run 对象(在 raise 前已修改)
            try:
                return await super().arun(**kwargs)
            except BaseException:
                # run 对象在 super().arun 内部创建,无法从外部直接访问;
                # 改为在 raise 后检查 captured_run(由下方 monkeypatch 填充)
                raise

    # 更简单策略:monkeypatch run_span_ctx.__exit__ 无法轻易捕获 run。
    # 使用正确方式:patch _aexec_one_body 来捕获 run 参数引用。
    real_body = Orchestrator._aexec_one_body

    async def _spy_body(self_orch, *, run, **kwargs):
        captured_run["ref"] = run
        return await real_body(self_orch, run=run, **kwargs)

    fail_exec2 = _ImmediateFailExecutor()
    unclean_exec2 = _UncleanableExecutor()
    orch2, task2, workflow2, steps2 = _make_two_step_dag_fixture(
        tmp_path, fail_exec2, unclean_exec2,
    )

    with unittest.mock.patch.object(Orchestrator, "_aexec_one_body", _spy_body):
        with unittest.mock.patch.object(_orch_mod, "_CASCADE_DRAIN_TIMEOUT_S", 0.2):
            with pytest.raises(KeyError, match="t7 immediate fail"):
                await orch2.arun(
                    task=task2, workflow=workflow2, steps=steps2,
                    run_id="r_t7_drain2",
                )

    # drain 超时必须被记录
    assert "ref" in captured_run, "spy が run を捕获できなかった"
    run = captured_run["ref"]
    assert "cancel_drain_timeout" in run.metrics, (
        f"drain timeout 未被记录在 run.metrics 中: {run.metrics}"
    )
    assert run.status == RunStatus.failed, (
        f"drain timeout 后 run.status 应为 failed,实际: {run.status}"
    )
