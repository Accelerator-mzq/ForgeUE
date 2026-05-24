"""Engine adapter registry tests."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from framework.artifact_store import ArtifactRepository, get_backend_registry
from framework.core.enums import RunMode, RunStatus, StepType, TaskType
from framework.core.task import Run, Step, Task
from framework.engine_bridge.core import EngineTarget
from framework.engine_bridge.registry import EngineAdapterRegistry
from framework.runtime.executors.base import ExecutorResult, StepContext
from framework.runtime.executors.export import ExportExecutor


class _DummyAdapter:
    engine = "godot4"


class _RecordingAdapter:
    def __init__(self, *, engine: str) -> None:
        self.engine = engine
        self.calls = []

    async def export(self, ctx: StepContext, *, target: EngineTarget) -> ExecutorResult:
        # 测试用 adapter 只记录 dispatcher 是否把目标透传过来。
        self.calls.append((ctx, target))
        return ExecutorResult(metrics={"engine": target.engine})


def test_engine_adapter_registry_resolves_registered_adapter():
    registry = EngineAdapterRegistry()
    adapter = _DummyAdapter()

    registry.register(adapter)

    assert registry.resolve("godot4") is adapter


def test_engine_adapter_registry_raises_for_missing_engine():
    registry = EngineAdapterRegistry()

    with pytest.raises(KeyError, match="No engine adapter"):
        registry.resolve("godot4")


async def test_export_executor_dispatches_to_engine_adapter(tmp_path: Path):
    adapter = _RecordingAdapter(engine="godot4")
    registry = EngineAdapterRegistry()
    registry.register(adapter)
    executor = ExportExecutor(adapter_registry=registry)

    task = Task(
        task_id="task_dispatch",
        task_type=TaskType.ue_export,
        run_mode=RunMode.production,
        title="dispatch",
        project_id="proj_dispatch",
        engine_target=EngineTarget(
            engine="godot4",
            project_name="G",
            project_root=str(tmp_path),
            import_mode="headless_import",
        ),
    )
    step = Step(
        step_id="step_export",
        type=StepType.export,
        name="export",
        capability_ref="engine.export",
    )
    run = Run(
        run_id="run_dispatch",
        task_id=task.task_id,
        project_id=task.project_id,
        status=RunStatus.running,
        started_at=datetime.now(timezone.utc),
        workflow_id="wf_dispatch",
        trace_id="trace_dispatch",
    )
    repo = ArtifactRepository(
        backend_registry=get_backend_registry(artifact_root=str(tmp_path / "_artifacts"))
    )

    ctx = StepContext(run=run, task=task, step=step, repository=repo)

    result = await executor.execute(ctx)

    assert adapter.calls == [(ctx, task.engine_target)]
    assert result.metrics["engine"] == "godot4"
