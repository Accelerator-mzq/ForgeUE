"""Executor protocol for Steps (§C.2, F0-4)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from framework.artifact_store import ArtifactRepository
from framework.core.artifact import Artifact
from framework.core.enums import StepType
from framework.core.review import Verdict
from framework.core.task import Run, Step, Task


@dataclass
class StepContext:
    """Everything a Step executor sees when it runs."""

    run: Run
    task: Task
    step: Step
    repository: ArtifactRepository
    inputs: dict[str, Any] = field(default_factory=dict)
    upstream_artifact_ids: list[str] = field(default_factory=list)


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
    def execute(self, ctx: StepContext) -> ExecutorResult: ...


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
