"""Orchestrator — drives a Run through a Workflow (§C.2, F0-4, Plan C Phase 7).

Flow (MVP):
  1. Dry-run Pass (unless caller pre-ran one)
  2. resolve entry step
  3. loop:
      a. resolve inputs for current step (or set of ready steps for DAG)
      b. compute input_hash; if CheckpointStore hit → reuse
      c. else invoke StepExecutor, persist Artifacts, record Checkpoint
      d. apply TransitionEngine to pick next step (or let DAG scheduler fan out)
  4. terminate when next_step_id is None, max-loop hit, or cascade-cancel triggered

Plan C Phase 7: `arun` is the async primary entry point; sync `run` is a thin
`asyncio.run(arun(...))` shim. When `scheduler.runnable_after(done)` returns
multiple steps at once (DAG fan-out), they're launched concurrently via
`asyncio.create_task` + `asyncio.wait(FIRST_COMPLETED)`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from framework.artifact_store import ArtifactRepository
from framework.artifact_store.hashing import hash_inputs
from framework.core.enums import RunStatus
from framework.core.task import InputBinding, Run, Step, Task, Workflow
from framework.observability.event_bus import (
    ProgressEvent,
    publish as publish_event,
    reset_current_run_step,
    set_current_run_step,
)
from framework.observability.tracing import span
from framework.runtime.checkpoint_store import CheckpointStore
from framework.runtime.dry_run_pass import DryRunPass, DryRunReport
from framework.runtime.executors.base import (
    ExecutorRegistry,
    StepContext,
    get_executor_registry,
)
from framework.runtime.budget_tracker import (
    BudgetTracker,
    estimate_call_cost_usd,
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
    cache_hits: list[str] = field(default_factory=list)
    dry_run: DryRunReport | None = None
    revise_events: list[dict] = field(default_factory=list)
    failure_events: list[dict] = field(default_factory=list)
    budget_summary: dict = field(default_factory=dict)


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
        return asyncio.run(self.arun(
            task=task, workflow=workflow, steps=steps,
            run_id=run_id, trace_id=trace_id, skip_dry_run=skip_dry_run,
        ))

    async def arun(
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
                raise DryRunFailed(dr_report)

        prepared = self.scheduler.prepare(workflow=workflow, steps=steps)
        step_map = prepared.step_by_id
        all_steps_list = list(steps)

        budget_tracker = BudgetTracker(policy=task.budget_policy)

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

        # State shared across step completions:
        produced_ids_per_step: dict[str, list[str]] = {}
        pending_revision_hints: dict[str, dict] = {}
        done: set[str] = set()
        step_outcomes: dict[str, _StepOutcome] = {}
        terminated = False

        # DAG fan-out is opt-in via workflow-level or task-level flag. For
        # the default linear behaviour every step is still executed one at a
        # time in spine order, identical to the pre-Plan-C orchestrator.
        # Turn on by setting `task.constraints["parallel_dag"] = True` or
        # `workflow.metadata.get("parallel_dag")` — both checked here.
        dag_mode = bool(
            (task.constraints or {}).get("parallel_dag")
            or (getattr(workflow, "metadata", None) or {}).get("parallel_dag")
        )

        current: str | None = prepared.entry_step_id
        hops = 0

        while current is not None and not terminated:
            hops += 1
            if hops > self._max_loop:
                run.status = RunStatus.failed
                run.metrics["halt_reason"] = "max_loop_exceeded"
                break

            # Linear fast path (also the default path when dag_mode is off).
            # Identical semantics to the pre-Plan-C sync orchestrator —
            # revise loops, checkpoint cache, budget termination all work the
            # same; difference is `await asyncio.to_thread(executor.execute)`
            # so the event loop stays free.
            if not dag_mode:
                outcome = await self._aexec_one(
                    step=step_map[current], task_obj=task, workflow=workflow,
                    run=run, run_id=run_id, result=result,
                    budget_tracker=budget_tracker,
                    produced_ids_per_step=produced_ids_per_step,
                    pending_revision_hints=pending_revision_hints,
                )
                if outcome.terminate:
                    terminated = True
                    current = None
                else:
                    current = outcome.next_step_id
                continue

            # DAG mode: track which steps are done so runnable_after works,
            # and skip spine-advancement through already-done steps.
            if current in pending_revision_hints and current in done:
                done.discard(current)       # revise target must re-execute
            if current in done:
                prev = step_outcomes.get(current)
                next_id = prev.next_step_id if prev else None
                if next_id == current:
                    # TransitionEngine emits `next_step_id == step_id` for
                    # Decision.retry_same_step (and for step/fallback exits
                    # without an explicit on_fallback). Linear mode honours
                    # this by re-entering the execute path with the same
                    # `current`; DAG mode must do the same — dropping from
                    # `done` forces re-execution. The outer hops counter
                    # (`max_loop`) still bounds total retries.
                    done.discard(current)
                else:
                    current = next_id
                    continue

            ready_ids: set[str] = {current}
            ready = self.scheduler.runnable_after(
                completed=done, steps=all_steps_list,
            )
            for s in ready:
                if s.step_id not in done and s.step_id not in ready_ids:
                    ready_ids.add(s.step_id)

            if len(ready_ids) == 1:
                outcome = await self._aexec_one(
                    step=step_map[current], task_obj=task, workflow=workflow,
                    run=run, run_id=run_id, result=result,
                    budget_tracker=budget_tracker,
                    produced_ids_per_step=produced_ids_per_step,
                    pending_revision_hints=pending_revision_hints,
                )
                done.add(current)
                step_outcomes[current] = outcome
                if outcome.terminate:
                    terminated = True
                    current = None
                else:
                    current = outcome.next_step_id
                continue

            # DAG fan-out — launch all ready concurrently.
            tasks: dict[str, asyncio.Task] = {}
            for sid in ready_ids:
                tasks[sid] = asyncio.create_task(
                    self._aexec_one(
                        step=step_map[sid], task_obj=task, workflow=workflow,
                        run=run, run_id=run_id, result=result,
                        budget_tracker=budget_tracker,
                        produced_ids_per_step=produced_ids_per_step,
                        pending_revision_hints=pending_revision_hints,
                    ),
                    name=sid,
                )

            # Drain concurrently-running tasks with FIRST_COMPLETED so we
            # cascade-cancel on EITHER a raised exception (classic) OR a
            # `_StepOutcome(terminate=True)` — the latter is how
            # `_aexec_one` reports budget-exceeded, classified provider
            # failures, and transition-terminated verdicts. FIRST_EXCEPTION
            # would only catch the first case and let siblings keep
            # burning external calls after a run was already marked failed.
            spine_next: str | None = None
            first_exc: BaseException | None = None
            cascade_terminate = False
            pending_tasks: set[asyncio.Task] = set(tasks.values())
            completed_outcomes: dict[str, _StepOutcome] = {}
            try:
                while pending_tasks:
                    done_set, pending_tasks = await asyncio.wait(
                        pending_tasks, return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in done_set:
                        sid = t.get_name()
                        exc = t.exception()
                        if exc is not None:
                            if first_exc is None:
                                first_exc = exc
                            continue
                        value = t.result()
                        completed_outcomes[sid] = value
                        if sid == current:
                            spine_next = value.next_step_id
                        if value.terminate:
                            cascade_terminate = True
                    if first_exc is not None or cascade_terminate:
                        # Cancel siblings still running. We do NOT await the
                        # cancelled tasks — sync executors in
                        # `asyncio.to_thread` can't be interrupted, and
                        # awaiting would block until the thread finishes
                        # naturally (defeats fail-fast). The cancelled
                        # futures finish in the background.
                        for p in pending_tasks:
                            p.cancel()
                        pending_tasks = set()
                        break
            except asyncio.CancelledError:
                for t in tasks.values():
                    if not t.done():
                        t.cancel()
                raise

            # Commit whatever completed before the cascade.
            for sid, value in completed_outcomes.items():
                step_outcomes[sid] = value
                done.add(sid)

            if first_exc is not None:
                run_span_ctx.__exit__(
                    type(first_exc), first_exc, first_exc.__traceback__,
                )
                raise first_exc

            if cascade_terminate:
                terminated = True
                current = None
            else:
                current = spine_next

        run.ended_at = datetime.now(timezone.utc)
        if run.status == RunStatus.running:
            run.status = RunStatus.succeeded
        if task.budget_policy is not None:
            result.budget_summary = budget_tracker.summary()
            run.metrics["budget_spent_usd"] = round(
                budget_tracker.spend.total_usd, 6
            )
        run_span_ctx.__exit__(None, None, None)
        return result

    # ---- single-step executor core --------------------------------------

    async def _aexec_one(
        self,
        *,
        step: Step,
        task_obj: Task,
        workflow: Workflow,
        run: Run,
        run_id: str,
        result: RunResult,
        budget_tracker: BudgetTracker,
        produced_ids_per_step: dict[str, list[str]],
        pending_revision_hints: dict[str, dict],
    ) -> "_StepOutcome":
        """Execute one step in-async. Mirrors v1 run()'s per-iteration body
        but returns a `_StepOutcome` for the caller to apply in aggregate."""
        # Bind (run_id, step_id) into a ContextVar so adapter-level progress
        # emitters (tokenhub poller, mesh poller) can tag their events with
        # the correct run_id/step_id. The ContextVar is propagated into the
        # worker thread by asyncio.to_thread.
        _run_step_token = set_current_run_step(run_id, step.step_id)
        try:
            return await self._aexec_one_body(
                step=step, task_obj=task_obj, workflow=workflow,
                run=run, run_id=run_id, result=result,
                budget_tracker=budget_tracker,
                produced_ids_per_step=produced_ids_per_step,
                pending_revision_hints=pending_revision_hints,
            )
        finally:
            reset_current_run_step(_run_step_token)

    async def _aexec_one_body(
        self,
        *,
        step: Step,
        task_obj: Task,
        workflow: Workflow,
        run: Run,
        run_id: str,
        result: RunResult,
        budget_tracker: BudgetTracker,
        produced_ids_per_step: dict[str, list[str]],
        pending_revision_hints: dict[str, dict],
    ) -> "_StepOutcome":
        run.current_step_id = step.step_id
        result.visited_step_ids.append(step.step_id)
        publish_event(ProgressEvent(
            run_id=run_id, step_id=step.step_id, phase="step_start",
            raw={"capability_ref": step.capability_ref,
                 "risk_level": step.risk_level.value},
        ))

        upstream_ids = self._resolve_upstream_ids(step, produced_ids_per_step)
        resolved_inputs = self._resolve_inputs(
            step=step, task=task_obj,
            upstream_ids=upstream_ids,
            produced_ids_per_step=produced_ids_per_step,
        )
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
                return _StepOutcome(terminate=True, next_step_id=None)
            return _StepOutcome(terminate=False, next_step_id=trans.next_step_id)

        executor = self.executors.resolve(step)
        ctx = StepContext(
            run=run, task=task_obj, step=step,
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
                # Run sync executor in a thread so the event loop stays free
                # (long image/mesh jobs don't block concurrent step tasks).
                exec_result = await asyncio.to_thread(executor.execute, ctx)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            mode = classify_failure(exc)
            if mode is None:
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
                return _StepOutcome(terminate=True, next_step_id=None)
            return _StepOutcome(terminate=False, next_step_id=trans.next_step_id)

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

        if task_obj.budget_policy is not None:
            cost_usd = exec_result.metrics.get("cost_usd")
            if cost_usd is None:
                usage = exec_result.metrics.get("usage")
                model = exec_result.metrics.get(
                    "model") or exec_result.metrics.get("chosen_model")
                if usage or model:
                    cost_usd = estimate_call_cost_usd(
                        model=str(model or "unknown"),
                        usage=usage,
                    )
            if cost_usd is not None and cost_usd > 0:
                budget_tracker.record(
                    step_id=step.step_id,
                    model=str(exec_result.metrics.get("chosen_model")
                               or exec_result.metrics.get("model")
                               or "unknown"),
                    cost_usd=float(cost_usd),
                )
            if not budget_tracker.check():
                run.metrics["termination_reason"] = (
                    f"budget_exceeded(cap={budget_tracker.cap_usd}, "
                    f"spent={budget_tracker.spend.total_usd:.4f})"
                )
                run.metrics["last_failure_mode"] = "budget_exceeded"
                result.failure_events.append({
                    "step_id": step.step_id,
                    "mode": "budget_exceeded",
                    "decision": "human_review_required",
                    "cap_usd": budget_tracker.cap_usd,
                    "spent_usd": round(budget_tracker.spend.total_usd, 6),
                })
                run.status = RunStatus.failed
                return _StepOutcome(terminate=True, next_step_id=None)

        if exec_result.verdict is not None:
            trans = self.transitions.on_verdict(
                step=step, verdict=exec_result.verdict, default_next=default_next,
            )
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
            publish_event(ProgressEvent(
                run_id=run_id, step_id=step.step_id, phase="step_done",
                raw={"terminated": True, "reason": trans.reason},
            ))
            return _StepOutcome(terminate=True, next_step_id=None)
        publish_event(ProgressEvent(
            run_id=run_id, step_id=step.step_id, phase="step_done",
            raw={"artifact_count": len(new_ids)},
        ))
        return _StepOutcome(terminate=False, next_step_id=trans.next_step_id)

    # ---- helpers --------------------------------------------------------

    def _recover_verdict(self, artifact_ids: list[str]):
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
        for b in step.input_bindings:
            if b.source.startswith("step:"):
                src_step = b.source.split(":", 1)[1].split(".", 1)[0]
                ids.extend(produced.get(src_step, []))
            elif b.source.startswith("artifact:"):
                ids.append(b.source.split(":", 1)[1])
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


@dataclass
class _StepOutcome:
    terminate: bool
    next_step_id: str | None
