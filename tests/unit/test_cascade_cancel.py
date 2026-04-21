"""Plan C Phase 7 — DAG fan-out failure semantics.

When one leaf raises an un-classifiable exception, the orchestrator's
`asyncio.wait(FIRST_EXCEPTION)` returns immediately, pending siblings
are cancelled, and the original exception re-raises through `run`.

Caveat: sync executors that run via `asyncio.to_thread` can't actually
be interrupted mid-sleep (Python has no way to cancel a running thread's
`time.sleep`). For true cancellation responsiveness we'd need the
executor to be async-native and await `asyncio.sleep`. Here we use a
very short-running OK executor so test completes quickly even though
cancellation isn't strictly observable.
"""
from __future__ import annotations

import time

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

    def execute(self, ctx: StepContext) -> ExecutorResult:
        from framework.core.artifact import ArtifactType, Lineage, ProducerRef
        from framework.core.enums import ArtifactRole, PayloadKind
        time.sleep(0.05)        # short — sync threads can't be interrupted
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

    def execute(self, ctx: StepContext) -> ExecutorResult:
        # Non-classifiable exception (not a provider/worker/schema error) so
        # orchestrator re-raises rather than synthesising a failure Verdict.
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

    def execute(self, ctx: StepContext) -> ExecutorResult:
        from framework.core.artifact import ArtifactType, Lineage, ProducerRef
        from framework.core.enums import ArtifactRole, PayloadKind
        time.sleep(0.02)
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

    def execute(self, ctx: StepContext) -> ExecutorResult:
        from framework.core.artifact import ArtifactType, Lineage, ProducerRef
        from framework.core.enums import ArtifactRole, PayloadKind
        time.sleep(0.5)
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

    def execute(self, ctx: StepContext) -> ExecutorResult:
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
