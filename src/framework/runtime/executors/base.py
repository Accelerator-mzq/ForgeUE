"""Executor protocol for Steps (§C.2, F0-4)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from framework.artifact_store import ArtifactRepository
from framework.core.artifact import Artifact
from framework.core.enums import StepType
from framework.core.review import Verdict
from framework.core.task import Run, Step, Task

# 使用 TYPE_CHECKING 守门避免运行时循环导入:
# lifecycle.py 不依赖 base.py,但 base.py 若直接 import lifecycle 会形成
# base → lifecycle → (无依赖) 的单向链,理论上无循环。
# 为防未来 lifecycle 引入其他 runtime 组件造成循环,保留 TYPE_CHECKING 守门。
if TYPE_CHECKING:
    from framework.runtime.lifecycle import ExternalProcessLifecycle


@dataclass
class StepContext:
    """Everything a Step executor sees when it runs.

    `run_dir` is the canonical artifact-tree directory for this run
    (`<artifact_root>/<run_id>/`). Workers needing in-tree file placement
    (e.g. ComfyAgentWorker copying ComfyUI outputs from external dir)
    SHALL read this field directly. Orchestrator injects via
    `_compute_run_dir(run)` helper at construction time. The default
    `Path('.')` is a test-mock convenience — production code path
    via Orchestrator always injects the real path.
    See OpenSpec change comfy-agent-cli-adoption: design.md D8 +
    runtime-core/spec.md "StepContext exposes run_dir for in-tree
    artifact placement" Requirement.

    `lifecycle` 由 Orchestrator 在 arun 开始时构建并注入
    (Task 9 executor-async-rewrite):comfy/local* + comfy_lifecycle != none 时
    为 ComfyLifecycleManager 实例;其余情况为 None。
    executor 通过此字段感知 lifecycle 模式,无需直接操作 manager。
    (Task 10 将解锁 ComfyAgentWorker 侧的 lifecycle gate)
    """

    run: Run
    task: Task
    step: Step
    repository: ArtifactRepository
    run_dir: Path = field(default_factory=lambda: Path("."))
    inputs: dict[str, Any] = field(default_factory=dict)
    upstream_artifact_ids: list[str] = field(default_factory=list)
    # Task 9:由 Orchestrator 注入的 lifecycle manager 实例;None 表示 lifecycle="none"
    lifecycle: "ExternalProcessLifecycle | None" = None


@dataclass
class ExecutorResult:
    """Output of a Step run."""

    artifacts: list[Artifact] = field(default_factory=list)
    verdict: Verdict | None = None           # only for review-type steps
    metrics: dict = field(default_factory=dict)


class StepExecutor(ABC):
    """Binds one (step_type, capability_ref) combination to concrete behavior.

    A registry entry of `(StepType, None)` is a wildcard capability match.
    """

    step_type: StepType
    capability_ref: str | None = None        # None = wildcard

    @abstractmethod
    async def execute(self, ctx: StepContext) -> ExecutorResult: ...


class ExecutorRegistry:
    def __init__(self) -> None:
        self._exact: dict[tuple[StepType, str], StepExecutor] = {}
        self._wildcard: dict[StepType, StepExecutor] = {}

    def register(self, executor: StepExecutor) -> None:
        if executor.capability_ref is None:
            self._wildcard[executor.step_type] = executor
        else:
            self._exact[(executor.step_type, executor.capability_ref)] = executor

    def resolve(self, step: Step) -> StepExecutor:
        key = (step.type, step.capability_ref)
        if key in self._exact:
            return self._exact[key]
        if step.type in self._wildcard:
            return self._wildcard[step.type]
        raise KeyError(
            f"No executor for step_type={step.type} capability_ref={step.capability_ref}"
        )


_default_registry: ExecutorRegistry | None = None


def get_executor_registry() -> ExecutorRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ExecutorRegistry()
    return _default_registry
