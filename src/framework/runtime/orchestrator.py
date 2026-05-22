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
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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
from framework.runtime.lifecycle import ComfyLifecycleManager
from framework.runtime.scheduler import Scheduler
from framework.runtime.transition_engine import TransitionEngine
from framework.providers.comfy_provider_config import (
    first_comfy_agent_route,
    resolve_comfy_agent_config,
)


# cascade-cancel drain 超时上限(秒)。
# 原生 async executor 的 CancelledError 通常在微秒内传播;
# 设为 30s 给含外部 I/O 清理的 executor(如 ComfyUI subprocess)足够时间。
# 超时视为清理卡死 → 显式失败,不静默丢弃。
_CASCADE_DRAIN_TIMEOUT_S: float = 30.0

# lifecycle release 超时上限(秒)。
# _spawn_stop 通过 factory_v3 stop 子命令停止 ComfyUI;
# 正常情况下几秒完成,设为 30s 给含外部进程通信足够时间。
# 超时后 _release_lifecycle_bounded 记录失败留痕,不遮蔽调用方原始异常。
_RELEASE_TIMEOUT_S: float = 30.0

class DryRunFailed(RuntimeError):
    def __init__(self, report: DryRunReport) -> None:
        super().__init__(f"dry-run failed: {report.errors}")
        self.report = report


@dataclass(frozen=True)
class _ComfyLifecycleSelection:
    """一次 lifecycle 选择结果:模式 + agent CLI 运行配置。"""

    mode: str
    scripts_dir: str | None
    python_exe: str | None


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
        # self_managed_session 模式下跨 arun 复用的 lifecycle manager 实例
        # 其他模式下为 None(per-arun manager 仅在 arun 局部变量中存在)
        self._lifecycle: ComfyLifecycleManager | None = None
        # aclose() 中 release 失败时的留痕记录(dict 或 None)
        self._lifecycle_release_failed: dict | None = None

    def _compute_run_dir(self, run: Run) -> Path:
        """Resolve the canonical artifact-tree directory for this run.

        Reads `getattr(self.checkpoints, "_root", None)` (same source
        `_post_step` line ~627 uses for `dump_run_metadata`) and joins
        with `run.run_id`. NO extra date segment because `framework.run`
        already date-buckets `--artifact-root` by default
        (`framework.run` line 111-115) and `framework.run` line 149 uses
        `artifact_root / args.run_id` without an extra date bucket.

        G11 R3 fix (codex implementation review):
        Raises RuntimeError when `_root is None` instead of silently
        returning `Path(".")`. Earlier draft fell back to cwd as a
        "test-mock convenience", but Orchestrator-injected
        `StepContext.run_dir` is also the production path that
        `ComfyAgentWorker` writes copied PNGs into. Silent cwd fallback
        meant any in-memory CheckpointStore live run would scatter
        artifacts in the process cwd, breaking the
        `<artifact_root>/<run_id>` self-contained / resume / archive
        invariants. Tests that need a synthetic run_dir construct
        StepContext directly with `run_dir=tmp_path` instead of going
        through Orchestrator. See comfy-agent-cli-adoption
        review/codex_implementation_review.md R3.
        """
        root = getattr(self.checkpoints, "_root", None)
        if root is None:
            raise RuntimeError(
                "Orchestrator._compute_run_dir requires checkpoints._root "
                "to be set so StepContext.run_dir can resolve to "
                "<artifact_root>/<run_id>; got None. Tests should "
                "construct StepContext directly with run_dir=tmp_path "
                "rather than route through Orchestrator."
            )
        return Path(root) / run.run_id

    # ---- lifecycle 辅助方法 -------------------------------------------------

    @staticmethod
    def _detect_comfy_lifecycle(steps: list[Step]) -> _ComfyLifecycleSelection | None:
        """扫描 provider metadata,检测是否需要 ComfyUI lifecycle 管理。

        若找到 ComfyUI subprocess route 且 lifecycle != "none",返回 mode 与
        agent CLI 配置;否则返回 None。按第一个命中的 ComfyUI route 为准。
        """
        for step in steps:
            pp = getattr(step, "provider_policy", None)
            if pp is None:
                continue
            route = first_comfy_agent_route(pp.prepared_routes or [])
            if route is None:
                continue
            # 从 step.config.spec 读取 lifecycle 覆盖值,再和 provider/env 配置合并。
            config_raw = step.config or {}
            spec_raw = (
                config_raw.get("spec", {}) if isinstance(config_raw, dict)
                else {}
            )
            spec = spec_raw if isinstance(spec_raw, dict) else {}
            config = resolve_comfy_agent_config(route=route, spec=spec)
            if config.default_lifecycle != "none":
                return _ComfyLifecycleSelection(
                    mode=config.default_lifecycle,
                    scripts_dir=config.scripts_dir,
                    python_exe=config.python_exe,
                )
        return None

    async def _release_lifecycle_bounded(
        self,
        manager: ComfyLifecycleManager,
        mode: str,
        reason: str,
        sink: Callable[[dict], None],
    ) -> None:
        """有界且非遮蔽的 lifecycle release。

        参数:
            manager: 待 release 的 ComfyLifecycleManager 实例
            mode:    lifecycle 模式(ensure_running / ensure_release / self_managed_session)
            reason:  释放原因(run_end / cascade / arun_cancel / arun_error / orchestrator_close)
            sink:    失败留痕回调;接收 dict,写入 run.metrics 或 self 属性

        使用 asyncio.shield 保护 release coroutine 不被外部 cancellation 中断,
        再用 asyncio.wait_for 设置超时上限:
        - 超时(TimeoutError)或其他异常 → 调用 sink 留痕 + 记录 warning 日志,不 re-raise
        - release 正常完成 → 无额外操作
        """
        try:
            await asyncio.wait_for(
                asyncio.shield(manager.release(mode, reason)),
                timeout=_RELEASE_TIMEOUT_S,
            )
        except BaseException as exc:
            payload = {"mode": mode, "reason": reason, "error": repr(exc)}
            sink(payload)
            logging.getLogger(__name__).warning(
                "lifecycle release failed: mode=%s reason=%s error=%r",
                mode, reason, exc,
            )
            # 不 re-raise:保留调用方原始异常 / cancellation 不被遮蔽

    async def aclose(self) -> None:
        """释放 Orchestrator 持有的 self_managed_session lifecycle manager。

        应在所有 arun 调用完成后调用(例如通过 async with 上下文管理器)。
        release 超时或失败时不抛出异常,失败留痕写入 self._lifecycle_release_failed。
        """
        if self._lifecycle is not None:
            manager = self._lifecycle
            # self_managed_session 的 mode 固定为 "self_managed_session"
            mode = "self_managed_session"
            await self._release_lifecycle_bounded(
                manager, mode, "orchestrator_close",
                sink=lambda d: setattr(self, "_lifecycle_release_failed", d),
            )

    async def __aenter__(self) -> "Orchestrator":
        """支持 async with 语法:返回 self。"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文时调用 aclose() 释放资源。不遮蔽原始异常。"""
        await self.aclose()

    # ---- 同步/异步入口 -------------------------------------------------------

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
        # Per-run TransitionEngine clone: counters (retry / revise) MUST NOT
        # leak across runs on the same Orchestrator instance, and concurrent
        # arun() calls must not share counter dicts. `cloned_for_run()`
        # preserves subclass identity and any caller-supplied instance
        # attributes — only TransitionCounters get reset.
        transitions = self.transitions.cloned_for_run()
        dr_report: DryRunReport | None = None
        if not skip_dry_run:
            with span("dry_run", {"run_id": run_id, "workflow_id": workflow.workflow_id}):
                # Step 6: DryRunPass.run 已改为 async def,必须 await
                dr_report = await self.dry_run.run(task=task, workflow=workflow, steps=steps)
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

        # ── lifecycle manager 检测与构建 ──────────────────────────────────
        # 扫描 provider metadata 寻找 ComfyUI subprocess 路由 + lifecycle mode != none
        lc_selection = self._detect_comfy_lifecycle(steps)
        lc_mode = lc_selection.mode if lc_selection is not None else None
        # per_arun_manager:仅对本次 arun 生命周期负责(非 self_managed_session 模式)
        per_arun_manager: ComfyLifecycleManager | None = None

        if lc_selection is not None:
            scripts_dir = lc_selection.scripts_dir
            python_exe = lc_selection.python_exe
            if lc_mode == "self_managed_session":
                # self_managed_session:跨 arun 复用同一个 manager 实例
                if self._lifecycle is None:
                    self._lifecycle = ComfyLifecycleManager(
                        scripts_dir=scripts_dir or ".",
                        python_exe=python_exe,
                    )
                active_manager: ComfyLifecycleManager | None = self._lifecycle
            else:
                # ensure_running / ensure_release:每次 arun 新建 manager
                per_arun_manager = ComfyLifecycleManager(
                    scripts_dir=scripts_dir or ".",
                    python_exe=python_exe,
                )
                active_manager = per_arun_manager
            # 注意:ensure() 调用移至 try 块内部(see Important-1 fix)
            # manager 构建(轻量,不失败)在 try 外;ensure() 可能抛出异常
            # 须由 finally 兜底 release,否则 _spawn_serve() 后泄漏进程
        else:
            active_manager = None
        # ──────────────────────────────────────────────────────────────────

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

        # release reason 变量:在各退出路径中设置,finally 统一读取
        # 可能取值:"run_end" / "cascade" / "arun_cancel" / "arun_error"
        release_reason: str = "run_end"
        try:
            # ensure() 在 try 内:失败时 except BaseException 设置 arun_error,
            # finally 统一调用 release(保证进程不泄漏)
            if active_manager is not None:
                assert lc_mode is not None
                await active_manager.ensure(lc_mode)
            while current is not None and not terminated:
                hops += 1
                if hops > self._max_loop:
                    run.status = RunStatus.failed
                    run.metrics["halt_reason"] = "max_loop_exceeded"
                    break

                # Linear fast path (also the default path when dag_mode is off).
                # Identical semantics to the pre-Plan-C sync orchestrator —
                # revise loops, checkpoint cache, budget termination all work the
                # same; executors are now native async coroutines awaited
                # directly on the event loop (no asyncio.to_thread wrapper).
                if not dag_mode:
                    outcome = await self._aexec_one(
                        step=step_map[current], task_obj=task, workflow=workflow,
                        run=run, run_id=run_id, result=result,
                        budget_tracker=budget_tracker,
                        produced_ids_per_step=produced_ids_per_step,
                        pending_revision_hints=pending_revision_hints,
                        transitions=transitions,
                        lifecycle_manager=active_manager,
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
                        transitions=transitions,
                        lifecycle_manager=active_manager,
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
                dag_tasks: dict[str, asyncio.Task] = {}
                for sid in ready_ids:
                    dag_tasks[sid] = asyncio.create_task(
                        self._aexec_one(
                            step=step_map[sid], task_obj=task, workflow=workflow,
                            run=run, run_id=run_id, result=result,
                            budget_tracker=budget_tracker,
                            produced_ids_per_step=produced_ids_per_step,
                            pending_revision_hints=pending_revision_hints,
                            transitions=transitions,
                            lifecycle_manager=active_manager,
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
                pending_tasks: set[asyncio.Task] = set(dag_tasks.values())
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
                            # 向所有仍在运行的兄弟任务发出取消信号。
                            for p in pending_tasks:
                                p.cancel()
                            # 原生 async 后 CancelledError 打穿到 executor/worker 真正
                            # 中断在飞工作。await 确认 sibling 真死;drain 超时是异常
                            # 兜底 → 显式失败,绝不静默丢弃未停的 task。
                            if pending_tasks:
                                done_drain, still_pending = await asyncio.wait(
                                    pending_tasks,
                                    timeout=_CASCADE_DRAIN_TIMEOUT_S,
                                )
                                if still_pending:
                                    # 清理卡死:记录卡住的 task 名称 + 标记失败。
                                    # 不再尝试二次 cancel — 由调用方或进程退出清理。
                                    stuck = sorted(t.get_name() for t in still_pending)
                                    for t in still_pending:
                                        t.cancel()
                                    run.metrics["cancel_drain_timeout"] = stuck
                                    run.status = RunStatus.failed
                            pending_tasks = set()
                            break
                except asyncio.CancelledError:
                    for t in dag_tasks.values():
                        if not t.done():
                            t.cancel()
                    raise

                # Commit whatever completed before the cascade.
                for sid, value in completed_outcomes.items():
                    step_outcomes[sid] = value
                    done.add(sid)

                if first_exc is not None:
                    # F1 Round 2 fix:span exit 已统一移至 finally(沿 sys.exc_info());
                    # 此处直接 raise,让 finally 路径关闭 span。
                    raise first_exc

                if cascade_terminate:
                    # cascade 终止:通知 lifecycle 以 cascade reason release
                    release_reason = "cascade"
                    terminated = True
                    current = None
                else:
                    current = spine_next

        except asyncio.CancelledError:
            # arun 被外部 cancel(如 asyncio.wait_for 超时)
            release_reason = "arun_cancel"
            raise
        except BaseException:
            # 未分类异常:设置 arun_error reason,finally 统一处理后 re-raise
            release_reason = "arun_error"
            raise
        finally:
            # ── 全路径 release:无论正常/cascade/cancel/异常都执行 ──────────
            if per_arun_manager is not None:
                # per-arun manager:本路径负责 release(恰好调用 1 次)
                await self._release_lifecycle_bounded(
                    per_arun_manager,
                    lc_mode or "ensure_release",
                    release_reason,
                    sink=lambda d: run.metrics.__setitem__("lifecycle_release_failed", d),
                )
            elif active_manager is not None and lc_mode == "self_managed_session":
                # self_managed_session:arun 内 release(run_end / cascade / cancel / error)
                # 不触发 stop(由决策表控制);aclose() 再以 orchestrator_close 触发 stop
                await self._release_lifecycle_bounded(
                    active_manager,
                    "self_managed_session",
                    release_reason,
                    sink=lambda d: run.metrics.__setitem__("lifecycle_release_failed", d),
                )
            # ──────────────────────────────────────────────────────────────

            # ── 全路径 span close(F1 Round 2 fix:OTel span 不漏)─────────
            # sys.exc_info() 在 finally 内拿当前 active exception(re-raise 中);
            # 正常退出为 (None, None, None)。覆盖三条出口:正常 / CancelledError /
            # 未分类异常 / DAG first_exc。原 L506-508 + L556 两处显式 __exit__ 已删,
            # 由本统一出口替代。
            exc_type, exc_val, exc_tb = sys.exc_info()
            run_span_ctx.__exit__(exc_type, exc_val, exc_tb)
            # ──────────────────────────────────────────────────────────────

        run.ended_at = datetime.now(timezone.utc)
        if run.status == RunStatus.running:
            run.status = RunStatus.succeeded
        if task.budget_policy is not None:
            result.budget_summary = budget_tracker.summary()
            run.metrics["budget_spent_usd"] = round(
                budget_tracker.spend.total_usd, 6
            )
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
        transitions: TransitionEngine,
        lifecycle_manager: "ComfyLifecycleManager | None" = None,
    ) -> "_StepOutcome":
        """Execute one step in-async. Mirrors v1 run()'s per-iteration body
        but returns a `_StepOutcome` for the caller to apply in aggregate."""
        # Bind (run_id, step_id) into a ContextVar so adapter-level progress
        # emitters (tokenhub poller, mesh poller) can tag their events with
        # the correct run_id/step_id. With native-async executors the
        # ContextVar is naturally task-local — no cross-thread propagation.
        _run_step_token = set_current_run_step(run_id, step.step_id)
        try:
            return await self._aexec_one_body(
                step=step, task_obj=task_obj, workflow=workflow,
                run=run, run_id=run_id, result=result,
                budget_tracker=budget_tracker,
                produced_ids_per_step=produced_ids_per_step,
                pending_revision_hints=pending_revision_hints,
                transitions=transitions,
                lifecycle_manager=lifecycle_manager,
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
        transitions: TransitionEngine,
        lifecycle_manager: "ComfyLifecycleManager | None" = None,
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
            # Fresh-process resume must replay the cached step's spend
            # into BudgetTracker — otherwise a run that was already
            # over-cap when persisted resumes "for free" on cache hits
            # and silently bypasses total_cost_cap_usd. We dedupe by
            # checking by_step (a counter we own per-tracker), so same-
            # process re-entries (revise loops) don't double-count.
            if task_obj.budget_policy is not None:
                cached_cost = (hit.metrics or {}).get("cost_usd") or 0.0
                already_recorded = budget_tracker.spend.by_step.get(
                    step.step_id, 0.0,
                )
                if cached_cost > 0 and already_recorded == 0:
                    budget_tracker.record(
                        step_id=step.step_id,
                        model=str((hit.metrics or {}).get("chosen_model")
                                   or (hit.metrics or {}).get("model")
                                   or "unknown"),
                        cost_usd=float(cached_cost),
                    )
                    if not budget_tracker.check():
                        run.metrics["termination_reason"] = (
                            f"budget_exceeded(cap={budget_tracker.cap_usd}, "
                            f"spent={budget_tracker.spend.total_usd:.4f})"
                        )
                        run.metrics["last_failure_mode"] = "budget_exceeded"
                        run.status = RunStatus.failed
                        return _StepOutcome(terminate=True, next_step_id=None)
            default_next = self.scheduler.default_next(step=step, workflow=workflow)
            cached_verdict = self._recover_verdict(hit.artifact_ids)
            if cached_verdict is not None:
                trans = transitions.on_verdict(
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
                trans = transitions.on_success(step=step, default_next=default_next)
            if trans.terminated:
                run.metrics["termination_reason"] = trans.reason
                return _StepOutcome(terminate=True, next_step_id=None)
            return _StepOutcome(terminate=False, next_step_id=trans.next_step_id)

        executor = self.executors.resolve(step)
        ctx = StepContext(
            run=run, task=task_obj, step=step,
            repository=self.repository,
            run_dir=self._compute_run_dir(run),
            inputs=resolved_inputs,
            upstream_artifact_ids=upstream_ids,
            # Task 9:将 lifecycle manager 注入 StepContext,executor 可感知 lifecycle 状态
            lifecycle=lifecycle_manager,
        )
        default_next = self.scheduler.default_next(step=step, workflow=workflow)
        try:
            with span(
                "step.execute",
                {"run_id": run_id, "step_id": step.step_id, "step_type": step.type.value,
                 "capability_ref": step.capability_ref, "risk_level": step.risk_level.value},
            ):
                # 全部 executor 已转 async def execute,直接 await
                exec_result = await executor.execute(ctx)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            mode = classify_failure(exc)
            if mode is None:
                raise
            synth = synth_failure_verdict(step_id=step.step_id, exc=exc, mode=mode)
            event: dict = {
                "step_id": step.step_id,
                "mode": mode.value,
                "decision": synth.decision.value,
            }
            # TBD-007: enrich with worker-side identifiers when the exception
            # carries them (MeshWorkerError / MeshWorkerTimeout do). CLI
            # surfaces these so users can `query` the remote job state before
            # blind-retrying — mesh jobs ~$0.20-1 each, blind retry can
            # double-bill jobs that completed server-side after local timeout.
            ctx_extras: dict = {}
            for attr in ("job_id", "worker", "model"):
                val = getattr(exc, attr, None)
                if val is not None:
                    ctx_extras[attr] = val
            if ctx_extras:
                event["context"] = ctx_extras
            result.failure_events.append(event)
            trans = transitions.on_verdict(
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

        # Estimate cost BEFORE recording the checkpoint so the per-step
        # cost lands in cp.metrics. Cross-process resume reads this value
        # back via the cache-hit replay path; without persistence,
        # generate_structured (whose executor only emits model + usage)
        # would resume "for free" and bypass total_cost_cap_usd.
        if task_obj.budget_policy is not None:
            cost_usd = exec_result.metrics.get("cost_usd")
            if cost_usd is None:
                usage = exec_result.metrics.get("usage")
                model = exec_result.metrics.get(
                    "model") or exec_result.metrics.get("chosen_model")
                if usage or model:
                    # 2026-04 pricing wiring: CapabilityRouter.astructured
                    # injects `_route_pricing` into the usage dict. Pull
                    # it through to `estimate_call_cost_usd` so text
                    # steps not on the review hot path (generate_
                    # structured, UE5 API assist, etc.) also benefit
                    # from yaml pricing when configured.
                    route_pricing = None
                    if isinstance(usage, dict):
                        route_pricing = usage.get("_route_pricing")
                    cost_usd = estimate_call_cost_usd(
                        model=str(model or "unknown"),
                        usage=usage,
                        route_pricing=route_pricing,
                    )
                    if cost_usd is not None:
                        exec_result.metrics["cost_usd"] = cost_usd

        cp = self.checkpoints.record(
            run_id=run_id, step_id=step.step_id, input_hash=input_hash,
            artifact_ids=new_ids, artifact_hashes=new_hashes,
            metrics=exec_result.metrics,
        )
        run.checkpoint_ids.append(cp.checkpoint_id)
        # Persist artifact metadata so a fresh CLI --resume can rebuild
        # the in-memory repository index. Without this, find_hit() always
        # misses on resume even though the checkpoint exists. Mirrors
        # `_checkpoints.json` writes done by CheckpointStore.record().
        self._dump_run_artifacts_if_possible(run_id=run_id)

        if task_obj.budget_policy is not None:
            cost_usd = exec_result.metrics.get("cost_usd")
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
            trans = transitions.on_verdict(
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
            trans = transitions.on_success(step=step, default_next=default_next)

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

    def _dump_run_artifacts_if_possible(self, *, run_id: str) -> None:
        """Persist Artifact metadata next to `_checkpoints.json` when the
        CheckpointStore has an artifact root configured. No-op when the
        store is in-memory only (tests / sub-flows without disk
        persistence) — matches CheckpointStore._persist's own no-op.

        Filesystem write errors propagate (mismatch with prior revisions
        that swallowed them silently): a failed dump means find_hit
        will miss on the next resume, and the user deserves to see the
        OSError rather than chase a phantom cache miss.
        Repository iteration is safe under DAG fan-out because
        find_by_producer snapshots `_artifacts` via list() before
        iterating, so a concurrent put() in a worker thread won't
        raise `dictionary changed size during iteration`.
        """
        root = getattr(self.checkpoints, "_root", None)
        if root is None:
            return
        self.repository.dump_run_metadata(
            run_id=run_id, run_dir=root / run_id,
        )

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
