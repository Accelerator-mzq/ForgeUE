"""Orchestrator — drives a Run through a Workflow (§C.2, F0-4).

Flow (MVP):
  1. Dry-run Pass (unless caller pre-ran one)
  2. resolve entry step
  3. loop:
      a. resolve inputs for current step
      b. compute input_hash; if CheckpointStore hit → reuse
      c. else invoke StepExecutor, persist Artifacts, record Checkpoint
      d. apply TransitionEngine to pick next step
  4. terminate when next_step_id is None or max-loop hit
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from framework.artifact_store import ArtifactRepository
from framework.artifact_store.hashing import hash_inputs
from framework.core.enums import RunStatus
from framework.core.task import InputBinding, Run, Step, Task, Workflow
from framework.observability.tracing import span
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.dry_run_pass import DryRunPass, DryRunReport
from framework.runtime.executors.base import (
    ExecutorRegistry,
    StepContext,
    get_executor_registry,
)
from framework.runtime.failure_mode_map import classify as classify_failure
from framework.runtime.failure_mode_map import synthesise_verdict as synth_failure_verdict
from framework.runtime.scheduler import Scheduler
from framework.runtime.transition_engine import TransitionEngine


class DryRunFailed(RuntimeError):
    def __init__(self, report: DryRunReport) -> None:
        super().__init__(f"dry-run failed: {report.errors}")
        self.report = report


@dataclass
class RunResult:
    run: Run
    visited_step_ids: list[str] = field(default_factory=list)
    cache_hits: list[str] = field(default_factory=list)          # step ids that hit checkpoint
    dry_run: DryRunReport | None = None
    revise_events: list[dict] = field(default_factory=list)      # {"step_id","target","hint_keys"}
    failure_events: list[dict] = field(default_factory=list)     # {"step_id","mode","decision"}


class Orchestrator:
    def __init__(
        self,
        *,
        repository: ArtifactRepository,
        checkpoint_store: CheckpointStore,
        executor_registry: ExecutorRegistry | None = None,
        scheduler: Scheduler | None = None,
        transition_engine: TransitionEngine | None = None,
        dry_run_pass: DryRunPass | None = None,
        max_loop: int = 64,
    ) -> None:
        self.repository = repository
        self.checkpoints = checkpoint_store
        self.executors = executor_registry or get_executor_registry()
        self.scheduler = scheduler or Scheduler()
        self.transitions = transition_engine or TransitionEngine()
        self.dry_run = dry_run_pass or DryRunPass()
        self._max_loop = max_loop

    def run(
        self,
        *,
        task: Task,
        workflow: Workflow,
        steps: list[Step],
        run_id: str,
        trace_id: str | None = None,
        skip_dry_run: bool = False,
    ) -> RunResult:
        dr_report: DryRunReport | None = None
        if not skip_dry_run:
            with span("dry_run", {"run_id": run_id, "workflow_id": workflow.workflow_id}):
                dr_report = self.dry_run.run(task=task, workflow=workflow, steps=steps)
            if not dr_report.passed:
                run = Run(
                    run_id=run_id, task_id=task.task_id, project_id=task.project_id,
                    status=RunStatus.failed, started_at=datetime.now(timezone.utc),
                    workflow_id=workflow.workflow_id, trace_id=trace_id or f"trace_{run_id}",
                )
                raise DryRunFailed(dr_report)

        prepared = self.scheduler.prepare(workflow=workflow, steps=steps)
        step_map = prepared.step_by_id

        run = Run(
            run_id=run_id, task_id=task.task_id, project_id=task.project_id,
            status=RunStatus.running, started_at=datetime.now(timezone.utc),
            workflow_id=workflow.workflow_id,
            current_step_id=prepared.entry_step_id,
            trace_id=trace_id or f"trace_{run_id}",
        )
        result = RunResult(run=run, dry_run=dr_report)

        run_span_ctx = span("run", {"run_id": run_id, "workflow_id": workflow.workflow_id,
                                      "task_id": task.task_id, "run_mode": task.run_mode.value})
        run_span_ctx.__enter__()
        current: str | None = prepared.entry_step_id
        produced_ids_per_step: dict[str, list[str]] = {}
        pending_revision_hints: dict[str, dict] = {}
        hops = 0
        while current is not None:
            hops += 1
            if hops > self._max_loop:
                run.status = RunStatus.failed
                run.metrics["halt_reason"] = "max_loop_exceeded"
                break

            step = step_map[current]
            run.current_step_id = step.step_id
            result.visited_step_ids.append(step.step_id)

            upstream_ids = self._resolve_upstream_ids(step, produced_ids_per_step)
            resolved_inputs = self._resolve_inputs(
                step=step, task=task,
                upstream_ids=upstream_ids,
                produced_ids_per_step=produced_ids_per_step,
            )
            # Thread any pending revision_hint targeting this step (§F3-4).
            if step.step_id in pending_revision_hints:
                resolved_inputs["revision_hint"] = pending_revision_hints.pop(step.step_id)
            input_hash = hash_inputs(
                step.step_id, step.capability_ref, step.config, resolved_inputs, upstream_ids,
            )

            # Checkpoint hit?
            hit = self.checkpoints.find_hit(
                run_id=run_id, step_id=step.step_id,
                input_hash=input_hash, repository=self.repository,
            )
            if hit is not None:
                result.cache_hits.append(step.step_id)
                produced_ids_per_step[step.step_id] = list(hit.artifact_ids)
                run.artifact_ids.extend(hit.artifact_ids)
                default_next = self.scheduler.default_next(step=step, workflow=workflow)
                # If the cached step was a review (or any producer of a Verdict),
                # replay the verdict through the TransitionEngine so revise/reject
                # decisions are honoured — otherwise we'd incorrectly fall through
                # to on_success on resume or revise loops.
                cached_verdict = self._recover_verdict(hit.artifact_ids)
                if cached_verdict is not None:
                    trans = self.transitions.on_verdict(
                        step=step, verdict=cached_verdict, default_next=default_next,
                    )
                    hint = cached_verdict.revision_hint
                    if hint and trans.next_step_id and not trans.terminated:
                        pending_revision_hints[trans.next_step_id] = dict(hint)
                        result.revise_events.append({
                            "step_id": step.step_id,
                            "target": trans.next_step_id,
                            "hint_keys": sorted(hint.keys()),
                            "from_cache": True,
                        })
                else:
                    trans = self.transitions.on_success(step=step, default_next=default_next)
                if trans.terminated:
                    run.metrics["termination_reason"] = trans.reason
                    current = None
                else:
                    current = trans.next_step_id
                continue

            # Real execution — failure-mode map (§C.6) catches classifiable errors.
            executor = self.executors.resolve(step)
            ctx = StepContext(
                run=run, task=task, step=step,
                repository=self.repository,
                inputs=resolved_inputs,
                upstream_artifact_ids=upstream_ids,
            )
            default_next = self.scheduler.default_next(step=step, workflow=workflow)
            try:
                with span(
                    "step.execute",
                    {"run_id": run_id, "step_id": step.step_id, "step_type": step.type.value,
                     "capability_ref": step.capability_ref, "risk_level": step.risk_level.value},
                ):
                    exec_result = executor.execute(ctx)
            except BaseException as exc:
                mode = classify_failure(exc)
                if mode is None:
                    run_span_ctx.__exit__(type(exc), exc, exc.__traceback__)
                    raise
                synth = synth_failure_verdict(step_id=step.step_id, exc=exc, mode=mode)
                result.failure_events.append({
                    "step_id": step.step_id,
                    "mode": mode.value,
                    "decision": synth.decision.value,
                })
                trans = self.transitions.on_verdict(
                    step=step, verdict=synth, default_next=default_next,
                )
                if trans.terminated:
                    run.status = RunStatus.failed
                    run.metrics["halt_reason"] = trans.reason or f"failure_mode:{mode.value}"
                    run.metrics["last_failure_mode"] = mode.value
                    current = None
                else:
                    current = trans.next_step_id
                continue

            new_ids = [a.artifact_id for a in exec_result.artifacts]
            new_hashes = [a.hash for a in exec_result.artifacts]
            produced_ids_per_step[step.step_id] = new_ids
            run.artifact_ids.extend(new_ids)

            cp = self.checkpoints.record(
                run_id=run_id, step_id=step.step_id, input_hash=input_hash,
                artifact_ids=new_ids, artifact_hashes=new_hashes,
                metrics=exec_result.metrics,
            )
            run.checkpoint_ids.append(cp.checkpoint_id)

            if exec_result.verdict is not None:
                trans = self.transitions.on_verdict(
                    step=step, verdict=exec_result.verdict, default_next=default_next,
                )
                # Carry a revision_hint forward to whichever step runs next.
                hint = exec_result.verdict.revision_hint
                if hint and trans.next_step_id and not trans.terminated:
                    pending_revision_hints[trans.next_step_id] = dict(hint)
                    result.revise_events.append({
                        "step_id": step.step_id,
                        "target": trans.next_step_id,
                        "hint_keys": sorted(hint.keys()),
                    })
            else:
                trans = self.transitions.on_success(step=step, default_next=default_next)

            if trans.terminated:
                run.metrics["termination_reason"] = trans.reason
                current = None
            else:
                current = trans.next_step_id

        run.ended_at = datetime.now(timezone.utc)
        if run.status == RunStatus.running:
            run.status = RunStatus.succeeded
        run_span_ctx.__exit__(None, None, None)
        return result

    # ---- helpers ----

    def _recover_verdict(self, artifact_ids: list[str]):
        """Return a Verdict parsed from the first verdict-shaped artifact in *artifact_ids*."""
        from framework.core.review import Verdict
        for aid in artifact_ids:
            if not self.repository.exists(aid):
                continue
            art = self.repository.get(aid)
            if art.artifact_type.modality == "report" and art.artifact_type.shape == "verdict":
                try:
                    return Verdict.model_validate(self.repository.read_payload(aid))
                except Exception:
                    return None
        return None

    @staticmethod
    def _resolve_upstream_ids(
        step: Step, produced: dict[str, list[str]]
    ) -> list[str]:
        ids: list[str] = []
        for dep in step.depends_on:
            ids.extend(produced.get(dep, []))
        # Also pick up ids from input bindings of form step:<id>.output
        for b in step.input_bindings:
            if b.source.startswith("step:"):
                src_step = b.source.split(":", 1)[1].split(".", 1)[0]
                ids.extend(produced.get(src_step, []))
            elif b.source.startswith("artifact:"):
                ids.append(b.source.split(":", 1)[1])
        # de-dup while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for i in ids:
            if i in seen:
                continue
            seen.add(i)
            out.append(i)
        return out

    @staticmethod
    def _resolve_inputs(
        *,
        step: Step,
        task: Task,
        upstream_ids: list[str],
        produced_ids_per_step: dict[str, list[str]],
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for b in step.input_bindings:
            resolved[b.name] = Orchestrator._lookup(
                b, task=task, produced_ids_per_step=produced_ids_per_step,
            )
        return resolved

    @staticmethod
    def _lookup(
        b: InputBinding,
        *,
        task: Task,
        produced_ids_per_step: dict[str, list[str]],
    ) -> Any:
        src = b.source
        if src.startswith("task.input_payload."):
            path = src[len("task.input_payload."):].split(".")
            cur: Any = task.input_payload
            for part in path:
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return b.default
            return cur
        if src.startswith("step:"):
            sid = src.split(":", 1)[1].split(".", 1)[0]
            return list(produced_ids_per_step.get(sid, []))
        if src.startswith("artifact:"):
            return src.split(":", 1)[1]
        if src.startswith("const:") or src.startswith("literal:"):
            return src.split(":", 1)[1]
        return b.default
