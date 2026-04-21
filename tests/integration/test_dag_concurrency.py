"""Plan C Phase 7 — DAG-mode Orchestrator runs independent branches concurrently.

Layout:
    root (fast)
     ├── branch_a (0.2s)
     ├── branch_b (0.2s)
     └── branch_c (0.2s)

All three branches declare `depends_on=[root]` but no deps on each other. With
`task.constraints["parallel_dag"]=True` the orchestrator should launch all
three concurrently — total elapsed ≈ 0.2s + scheduling, not 0.6s.

Without the flag, behaviour falls back to linear (serial) for strict
back-compat with P0-P4 integration tests.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.artifact_store.hashing import hash_inputs  # noqa: F401
from framework.core.enums import RiskLevel, RunMode, RunStatus, StepType, TaskType
from framework.core.task import Run, Step, Task, Workflow
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.executors.base import (
    ExecutorRegistry,
    StepContext,
    StepExecutor,
    ExecutorResult,
)
from framework.runtime.orchestrator import Orchestrator


class _SlowMockExecutor(StepExecutor):
    """Executor that sleeps `delay_s` before producing one text artifact."""

    step_type = StepType.generate
    capability_ref = "mock.slow"

    def __init__(self, delay_s: float) -> None:
        self._delay_s = delay_s

    def execute(self, ctx: StepContext) -> ExecutorResult:
        from framework.core.artifact import ArtifactType, Lineage, ProducerRef
        from framework.core.enums import ArtifactRole, PayloadKind
        time.sleep(self._delay_s)       # sync sleep — arun wraps in to_thread
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
                provider="mock", model="mock-slow",
            ),
            lineage=Lineage(
                source_artifact_ids=list(ctx.upstream_artifact_ids),
                source_step_ids=[ctx.step.step_id],
            ),
        )
        return ExecutorResult(artifacts=[art], metrics={})


def _make_workflow(*, dag_parallel: bool, tmp_path):
    steps = [
        Step(step_id="root", type=StepType.generate, name="root",
             capability_ref="mock.slow", risk_level=RiskLevel.low),
        Step(step_id="leaf_a", type=StepType.generate, name="a",
             capability_ref="mock.slow", risk_level=RiskLevel.low,
             depends_on=["root"]),
        Step(step_id="leaf_b", type=StepType.generate, name="b",
             capability_ref="mock.slow", risk_level=RiskLevel.low,
             depends_on=["root"]),
        Step(step_id="leaf_c", type=StepType.generate, name="c",
             capability_ref="mock.slow", risk_level=RiskLevel.low,
             depends_on=["root"]),
    ]
    workflow = Workflow(
        workflow_id="wf_dag", name="fan_out", version="1",
        entry_step_id="root",
        step_ids=["root", "leaf_a", "leaf_b", "leaf_c"],
    )
    constraints = {"parallel_dag": True} if dag_parallel else {}
    task = Task(
        task_id="t_dag", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="t",
        input_payload={}, expected_output={},
        project_id="p_dag", constraints=constraints,
    )
    registry = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=registry)
    store = CheckpointStore(artifact_root=tmp_path)
    execs = ExecutorRegistry()
    execs.register(_SlowMockExecutor(delay_s=0.2))
    orch = Orchestrator(
        repository=repo, checkpoint_store=store, executor_registry=execs,
    )
    return orch, task, workflow, steps


def test_dag_fans_out_leaves_concurrently(tmp_path):
    orch, task, workflow, steps = _make_workflow(
        dag_parallel=True, tmp_path=tmp_path,
    )
    start = time.monotonic()
    result = orch.run(task=task, workflow=workflow, steps=steps, run_id="r_dag")
    elapsed = time.monotonic() - start
    assert result.run.status == RunStatus.succeeded
    # root 0.2s serial + leaves 0.2s parallel = ~0.4s total; allow slack.
    # Serial would be 0.8s.
    assert elapsed < 0.6, f"leaves not parallelized: elapsed={elapsed:.3f}s"
    assert set(result.visited_step_ids) == {"root", "leaf_a", "leaf_b", "leaf_c"}


def test_workflow_metadata_parallel_dag_activates_fanout(tmp_path):
    """Codex P2 #5 regression — the orchestrator documents two ways to
    enable DAG mode (`task.constraints["parallel_dag"]` OR
    `workflow.metadata["parallel_dag"]`). Previously `Workflow` had no
    `metadata` field at all so the second toggle was silently dead code.
    Workflow now carries `metadata: dict` and this test locks in that
    enabling via metadata produces the same parallel timing as enabling
    via task.constraints."""
    steps = [
        Step(step_id="root", type=StepType.generate, name="root",
             capability_ref="mock.slow", risk_level=RiskLevel.low),
        Step(step_id="leaf_a", type=StepType.generate, name="a",
             capability_ref="mock.slow", risk_level=RiskLevel.low,
             depends_on=["root"]),
        Step(step_id="leaf_b", type=StepType.generate, name="b",
             capability_ref="mock.slow", risk_level=RiskLevel.low,
             depends_on=["root"]),
    ]
    workflow = Workflow(
        workflow_id="wf_dag_meta", name="fan_out_via_metadata", version="1",
        entry_step_id="root",
        step_ids=["root", "leaf_a", "leaf_b"],
        metadata={"parallel_dag": True},
    )
    # No task-level flag — DAG mode must come from workflow.metadata only.
    task = Task(
        task_id="t_dag_meta", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="t",
        input_payload={}, expected_output={},
        project_id="p_dag_meta", constraints={},
    )
    registry = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=registry)
    store = CheckpointStore(artifact_root=tmp_path)
    execs = ExecutorRegistry()
    execs.register(_SlowMockExecutor(delay_s=0.2))
    orch = Orchestrator(
        repository=repo, checkpoint_store=store, executor_registry=execs,
    )

    start = time.monotonic()
    result = orch.run(
        task=task, workflow=workflow, steps=steps, run_id="r_dag_meta",
    )
    elapsed = time.monotonic() - start

    assert result.run.status == RunStatus.succeeded
    # root 0.2s + parallel leaves 0.2s = ~0.4s. Serial would be ~0.6s.
    # If workflow.metadata toggle was ignored, we'd fall back to linear
    # and this assertion would fail.
    assert elapsed < 0.55, f"workflow.metadata did not enable DAG mode: elapsed={elapsed:.3f}s"


def test_linear_mode_still_sequential(tmp_path):
    """Without the flag, behaviour is unchanged — linear sequence ~0.8s."""
    orch, task, workflow, steps = _make_workflow(
        dag_parallel=False, tmp_path=tmp_path,
    )
    start = time.monotonic()
    result = orch.run(task=task, workflow=workflow, steps=steps, run_id="r_lin")
    elapsed = time.monotonic() - start
    assert result.run.status == RunStatus.succeeded
    # 4 steps × 0.2s = 0.8s; accept a wide band (0.7–1.5) for CI variance
    assert elapsed > 0.7, f"expected serial timing: elapsed={elapsed:.3f}s"
    assert result.visited_step_ids == ["root", "leaf_a", "leaf_b", "leaf_c"]
