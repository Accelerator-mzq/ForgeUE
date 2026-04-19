"""Scheduler: orders Steps within a Workflow (§C.4).

MVP rules:
- Build dependency map from Step.depends_on
- Linear + single-level branching supported
- Risk-level ordering used as tie-breaker when multiple Steps are runnable at once
"""
from __future__ import annotations

from dataclasses import dataclass

from framework.core.enums import RiskLevel
from framework.core.task import Step, Workflow

_RISK_ORDER = {RiskLevel.low: 0, RiskLevel.medium: 1, RiskLevel.high: 2}


@dataclass
class ScheduledSteps:
    entry_step_id: str
    step_by_id: dict[str, Step]


class Scheduler:
    def __init__(self) -> None:
        pass

    def prepare(self, *, workflow: Workflow, steps: list[Step]) -> ScheduledSteps:
        step_map = {s.step_id: s for s in steps}
        if workflow.entry_step_id not in step_map:
            raise ValueError(
                f"workflow entry_step_id={workflow.entry_step_id} not in provided steps"
            )
        for sid in workflow.step_ids:
            if sid not in step_map:
                raise ValueError(f"workflow references missing step: {sid}")
        return ScheduledSteps(entry_step_id=workflow.entry_step_id, step_by_id=step_map)

    def default_next(self, *, step: Step, workflow: Workflow) -> str | None:
        """Pick the next step by workflow ordering as a fallback for TransitionPolicy."""
        try:
            idx = workflow.step_ids.index(step.step_id)
        except ValueError:
            return None
        if idx + 1 >= len(workflow.step_ids):
            return None
        return workflow.step_ids[idx + 1]

    @staticmethod
    def risk_sort(steps: list[Step]) -> list[Step]:
        return sorted(steps, key=lambda s: _RISK_ORDER.get(s.risk_level, 99))

    def runnable_after(
        self,
        *,
        completed: set[str],
        steps: list[Step],
    ) -> list[Step]:
        """Return steps whose depends_on are satisfied by *completed*,
        risk-sorted ascending (low → high) per §C.4.

        Used by callers that need to pick an order when multiple steps become
        simultaneously runnable (branch merges, parallel forks). MVP orchestrator
        is single-threaded but still consults risk ordering as a tie-breaker.
        """
        runnable = [
            s for s in steps
            if s.step_id not in completed
            and all(dep in completed for dep in s.depends_on)
        ]
        return self.risk_sort(runnable)
