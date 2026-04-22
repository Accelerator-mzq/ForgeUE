"""Dry-run Pass — zero-side-effect pre-flight check (§C.3).

Covers the MVP subset:
- all workflow step_ids resolve to provided Step objects
- entry_step exists
- every InputBinding can be resolved (task input or upstream step exists)
- output_schema is a dict (MVP: not fully JSONSchema-validated yet)
- UEOutputTarget.project_root is accessible (if declared)

Provider reachability / budget estimate / secrets checks are stubbed with
extension hooks so P1 can fill them without changing signatures.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from pydantic import BaseModel, Field

from framework.core.enums import RunMode, TaskType
from framework.core.task import Step, Task, Workflow


# capability_ref prefixes that consume paid provider credits. Steps outside
# this set (mock/schema/select/ue.export/validate) don't need a budget cap.
_PAID_CAPABILITY_PREFIXES = ("text.", "image.", "mesh.", "review.")


class DryRunReport(BaseModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)


class DryRunPass:
    """Pre-flight aggregator. Register additional checks via *register_check*."""

    def __init__(self) -> None:
        self._extra_checks: list[Callable[[Task, Workflow, list[Step]], tuple[str, bool, str | None]]] = []

    def register_check(
        self,
        check: Callable[[Task, Workflow, list[Step]], tuple[str, bool, str | None]],
    ) -> None:
        """Each check returns (check_name, passed, message)."""
        self._extra_checks.append(check)

    def run(self, *, task: Task, workflow: Workflow, steps: Iterable[Step]) -> DryRunReport:
        report = DryRunReport(passed=True)
        step_list = list(steps)
        step_map = {s.step_id: s for s in step_list}

        # 1. Manifest/workflow structural integrity
        self._record(report, "workflow.entry_exists", workflow.entry_step_id in step_map,
                     error=f"entry step {workflow.entry_step_id} missing" if workflow.entry_step_id not in step_map else None)

        missing = [sid for sid in workflow.step_ids if sid not in step_map]
        self._record(report, "workflow.steps_resolved", not missing,
                     error=f"missing steps: {missing}" if missing else None)

        # 2. Output schema sanity
        bad_schema = [s.step_id for s in step_list if not isinstance(s.output_schema, dict)]
        self._record(report, "step.output_schema.shape", not bad_schema,
                     error=f"bad output_schema on: {bad_schema}" if bad_schema else None)

        # 3. Input bindings resolvable
        unresolved: list[str] = []
        for s in step_list:
            for b in s.input_bindings:
                if not b.required:
                    continue
                if not self._input_resolves(b.source, task=task, step_map=step_map):
                    unresolved.append(f"{s.step_id}.{b.name}<={b.source}")
        self._record(report, "step.input_bindings_resolved", not unresolved,
                     error=f"unresolved bindings: {unresolved}" if unresolved else None)

        # 4. UEOutputTarget path accessibility (production/ue_export)
        if task.ue_target:
            root = Path(task.ue_target.project_root)
            exists = root.is_dir()
            self._record(
                report, "ue.project_root_exists", exists,
                error=None if exists else f"project_root does not exist: {root}",
                warning_only=True,
            )
            if not task.ue_target.asset_root.startswith("/Game/"):
                report.warnings.append(
                    f"ue.asset_root should start with /Game/: {task.ue_target.asset_root}"
                )

        # 5. Budget cap sanity (F1): production / ue_export runs that hit paid
        # providers should declare a cap. Not an error — UI may still accept
        # an open-ended run — but a warning so nobody burns spend silently.
        self._check_budget_cap(report, task=task, steps=step_list)

        # 6. Extra checks (providers / budget / secrets registered by outer code)
        for fn in self._extra_checks:
            try:
                name, ok, msg = fn(task, workflow, step_list)
            except Exception as exc:  # isolate extension failures
                report.warnings.append(f"dry_run extra check raised: {exc}")
                continue
            self._record(report, name, ok, error=msg if not ok else None)

        return report

    # ---- helpers ----

    def _check_budget_cap(
        self,
        report: DryRunReport,
        *,
        task: Task,
        steps: list[Step],
    ) -> None:
        is_paid_run = (
            task.run_mode == RunMode.production
            or task.task_type == TaskType.ue_export
        )
        if not is_paid_run:
            report.checks["budget.cap_declared"] = True
            return
        cap = task.budget_policy.total_cost_cap_usd if task.budget_policy else None
        has_paid_step = any(
            (s.capability_ref or "").startswith(_PAID_CAPABILITY_PREFIXES)
            for s in steps
        )
        ok = cap is not None or not has_paid_step
        report.checks["budget.cap_declared"] = ok
        if not ok:
            report.warnings.append(
                f"no total_cost_cap_usd on {task.run_mode.value} task with paid "
                f"steps — run may spend unboundedly"
            )

    def _record(
        self,
        report: DryRunReport,
        name: str,
        passed: bool,
        *,
        error: str | None = None,
        warning_only: bool = False,
    ) -> None:
        report.checks[name] = passed
        if not passed:
            if warning_only:
                report.warnings.append(error or name)
            else:
                report.errors.append(error or name)
                report.passed = False

    @staticmethod
    def _input_resolves(source: str, *, task: Task, step_map: dict[str, Step]) -> bool:
        # task.input_payload.<dotted>
        if source.startswith("task.input_payload."):
            path = source[len("task.input_payload."):].split(".")
            cur = task.input_payload
            for part in path:
                if not isinstance(cur, dict) or part not in cur:
                    return False
                cur = cur[part]
            return True
        # step:<step_id>.output  — only verify step exists
        if source.startswith("step:"):
            step_id = source.split(":", 1)[1].split(".", 1)[0]
            return step_id in step_map
        # artifact:<id> — can't verify before run; accept
        if source.startswith("artifact:"):
            return True
        # literal / const — treat as resolvable
        if source.startswith("const:") or source.startswith("literal:"):
            return True
        return False
