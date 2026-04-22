"""TBD-007 integration fence: when an executor raises an exception with
job_id/worker/model attrs (as MeshWorkerError/Timeout do post-TBD-007),
the orchestrator persists those into failure_events.context AND the CLI
stderr hint surfaces them for the user.

Why this matters: HYPOTHESIS verification (acceptance_report §6.6) showed
that abandoned mesh jobs DO continue running on Hunyuan tokenhub server-side
after local timeout. Without this fence, framework errors strip job_id
from the user's view → user blind-retries → double-bills a job that may
have already completed (~$0.20-1 each).

Test strategy: use a synthetic generate(text) step with a custom executor
that raises MeshWorkerTimeout(job_id=...). This exercises the orchestrator's
failure_event-enrichment path WITHOUT needing the full upstream-image
machinery that GenerateMeshExecutor requires. The enrichment code is
generic — it copies job_id/worker/model attrs from any exception."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.enums import (
    RiskLevel, RunMode, RunStatus, StepType, TaskType,
)
from framework.core.task import Run, Step, Task, Workflow
from framework.providers.workers.mesh_worker import MeshWorkerTimeout
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.executors.base import (
    ExecutorRegistry, ExecutorResult, StepContext, StepExecutor,
)
from framework.runtime.orchestrator import Orchestrator


class _AlwaysRaisingMeshExecutor(StepExecutor):
    """Synthetic executor that always raises MeshWorkerTimeout with job_id —
    avoids GenerateMeshExecutor's upstream-image / spec-resolution coupling.
    The orchestrator path under test (failure_event context enrichment) is
    generic — it copies job_id/worker/model attrs off any exception."""
    step_type = StepType.generate
    capability_ref = "mesh.generation"

    def execute(self, ctx: StepContext) -> ExecutorResult:
        raise MeshWorkerTimeout(
            "tokenhub 3d job 9999_test_job exceeded 300s",
            job_id="9999_test_job",
            worker="hunyuan_3d",
            model="hy-3d-3.1",
        )


def test_mesh_failure_event_includes_job_id_and_stderr_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture
):
    """End-to-end: executor raises MeshWorkerTimeout with job_id → orchestrator
    failure_event.context carries it → CLI stderr hint shows it with concrete
    probe command. Two assertions in one fence (orchestrator + CLI) so the
    invariant is covered top-to-bottom."""
    reg = get_backend_registry(artifact_root=str(tmp_path))
    repo = ArtifactRepository(backend_registry=reg)

    step = Step(
        step_id="step_mesh", type=StepType.generate, name="mesh",
        risk_level=RiskLevel.high, capability_ref="mesh.generation",
        depends_on=[],
        config={"num_candidates": 1},
    )
    task = Task(
        task_id="t", task_type=TaskType.asset_generation,
        run_mode=RunMode.production, title="m",
        input_payload={}, expected_output={}, project_id="p",
    )
    workflow = Workflow(workflow_id="w_mesh_fail", name="w_mesh_fail",
                         version="1", entry_step_id="step_mesh",
                         step_ids=["step_mesh"])

    store = CheckpointStore(artifact_root=tmp_path)
    execs = ExecutorRegistry()
    execs.register(_AlwaysRaisingMeshExecutor())
    orch = Orchestrator(repository=repo, checkpoint_store=store,
                        executor_registry=execs)

    result = orch.run(
        task=task, workflow=workflow, steps=[step],
        run_id="stub_run",
    )

    # ---- assertion 1: failure_event has context.job_id ----
    assert result.run.status == RunStatus.failed
    assert len(result.failure_events) >= 1, (
        f"expected at least 1 failure_event, got {result.failure_events}"
    )
    fe = result.failure_events[0]
    assert fe["mode"] == "mesh_worker_timeout", (
        f"TBD-007 fence: MeshWorkerTimeout must classify as mesh_worker_timeout "
        f"(not generic worker_timeout). Got {fe['mode']!r}."
    )
    assert "context" in fe, (
        f"TBD-007 fence: failure_event must carry context dict when exc has "
        f"job_id. Event keys: {list(fe)}"
    )
    ctx_dict = fe["context"]
    assert ctx_dict.get("job_id") == "9999_test_job", (
        f"failure_event.context.job_id must propagate from MeshWorkerTimeout. "
        f"Got {ctx_dict!r}."
    )
    assert ctx_dict.get("worker") == "hunyuan_3d"
    assert ctx_dict.get("model") == "hy-3d-3.1"

    # ---- assertion 2: stderr hint contains job_id + probe command ----
    # Build the same summary dict shape that framework/run.py writes,
    # then call _print_mesh_failure_hint directly.
    from framework.run import _print_mesh_failure_hint
    summary = {
        "run_id": "stub_run",
        "status": "failed",
        "failure_events": result.failure_events,
    }
    run_dir = tmp_path / "stub_run"
    run_dir.mkdir(exist_ok=True)
    _print_mesh_failure_hint(summary, run_dir)
    captured = capsys.readouterr()

    assert "9999_test_job" in captured.err, (
        f"stderr hint must surface job_id. Got stderr: {captured.err[:500]!r}"
    )
    assert "probe_hunyuan_3d_query" in captured.err, (
        f"stderr hint must point to query probe so user verifies job state "
        f"BEFORE blind-retry (avoids double-bill of paid mesh job). "
        f"Got: {captured.err[:500]!r}"
    )
    assert "--resume" in captured.err, (
        f"stderr hint must show --resume command for legitimate retry. "
        f"Got: {captured.err[:500]!r}"
    )
