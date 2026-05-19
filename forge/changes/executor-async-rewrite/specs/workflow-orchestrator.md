# Workflow Orchestrator — executor-async-rewrite delta

> 本文件是 `workflow-orchestrator` capability 在 `executor-async-rewrite`(TBD-010)
> change 引入的行为增量:orchestrator 原生 `await` executor 取代 `to_thread`、
> cascade-cancel 真停(含 drain 超时显式失败)、orchestrator 持有 ComfyUI lifecycle
> 所有权 + `aclose()` disposal 钩子。每条 Requirement 首行标注 ADDED。

## Requirement: Orchestrator awaits executors as native coroutines

**ADDED.** The system SHALL have `Orchestrator._aexec_one_body` execute a step via
`exec_result = await executor.execute(ctx)`. The previous mechanism —
`await asyncio.to_thread(executor.execute, ctx)` — SHALL be removed. Because the
executor now runs on the orchestrator's own event loop rather than in a detached
worker thread, the orchestrator's `except asyncio.CancelledError: raise` and the
`classify_failure` exclusion of `CancelledError` continue to hold and now genuinely
short-circuit in-flight work.

## Scenario: Step execution runs on the event loop with no worker thread

**Given** a step dispatched through `_aexec_one_body`
**When** the orchestrator runs the executor
**Then** it evaluates `await executor.execute(ctx)` directly with no `asyncio.to_thread` call
**And** the `set_current_run_step` ContextVar is naturally task-local with no cross-thread propagation needed

## Requirement: Cascade-cancel propagates real cancellation and fails explicitly on drain timeout

**ADDED.** When a DAG fan-out cascade is triggered (a sibling raises an exception OR a
sibling returns `_StepOutcome(terminate=True)`), the orchestrator SHALL `cancel()` the
still-pending sibling tasks AND SHALL `await asyncio.wait(pending, timeout=
_CASCADE_DRAIN_TIMEOUT_S)` so that cancellation actually unwinds the running executors
/ workers — terminating subprocesses and closing HTTP connections — before the run
proceeds to its terminal state. The orchestrator SHALL inspect the `(done,
still_pending)` result: if `still_pending` is non-empty (a cleanup hung past the
drain timeout) the orchestrator SHALL NOT silently discard those tasks — it SHALL
record the stuck step ids in `run.metrics["cancel_drain_timeout"]`, re-`cancel()`
them, and end the run with a failed status. This replaces the prior fire-and-forget
behavior where cancelled tasks were left to "finish in the background" because
`asyncio.to_thread` threads could not be interrupted.

## Scenario: A cascade-cancelled sibling's work actually stops

**Given** a DAG fan-out with two concurrent steps where step A raises a classified failure (or terminates) while step B is still awaiting a provider / worker call
**When** the orchestrator's cascade path runs
**Then** it cancels step B's task and awaits it within `_CASCADE_DRAIN_TIMEOUT_S`, and `CancelledError` propagates into step B's executor and into the provider / worker call, which aborts its in-flight work (HTTP connection closed; ComfyUI subprocess terminated AND its server-side prompt aborted via `comfyui_api cancel`)
**And** step B does not continue consuming external API calls or subprocess/GPU time after the run has been marked for termination
**And** `tests/unit/test_cascade_cancel.py` is extended with a probe (a counter that would keep incrementing if the cancelled work continued) asserting the cancelled sibling's work observably stopped

## Scenario: A cascade drain timeout is an explicit run failure, not a silent drop

**Given** a cascade-cancelled sibling whose cleanup hangs longer than `_CASCADE_DRAIN_TIMEOUT_S`
**When** `asyncio.wait` returns with that task still in `still_pending`
**Then** the orchestrator records the stuck step id(s) in `run.metrics["cancel_drain_timeout"]`, issues a second `cancel()`, and the run ends with `RunStatus.failed`
**And** the orchestrator does NOT execute `pending_tasks = set()` as the sole handling — an un-drained task is surfaced as a failure, never silently abandoned

## Requirement: Orchestrator owns the ComfyUI lifecycle and exposes a disposal hook

**ADDED.** When a bundle's `prepared_routes` reference a `comfy/local*` model AND the
resolved `comfy_lifecycle` (from `step.config.spec.comfy_lifecycle` or the
`FORGEUE_COMFY_LIFECYCLE` env default) is not `"none"`, the orchestrator SHALL obtain
a `ComfyLifecycleManager` and inject it into every step's `StepContext.lifecycle`.
For `self_managed_session` the manager SHALL be held at the orchestrator-instance
level (`self._lifecycle`) and reused across multiple `arun` calls; for
`ensure_running` / `ensure_release` it MAY be per-`arun`.

The orchestrator SHALL release the manager in a **mode-aware** way:

- `ensure_running` — never released by the framework (warm reuse).
- `ensure_release` — released at normal run-end, cascade-terminate, and the
  `except asyncio.CancelledError` handler.
- `self_managed_session` — NOT released at normal run-end; released at
  cascade-terminate, the `except asyncio.CancelledError` handler, and at
  `Orchestrator.aclose()`.

The system SHALL add `Orchestrator.aclose()` (`async def`) which releases the
orchestrator-instance-level `self_managed_session` manager, and the orchestrator
SHALL implement async context manager protocol (`__aenter__` / `__aexit__`, the
latter calling `aclose()`). The CLI (`framework.run`) SHALL call `await
orch.aclose()` before process exit. A `_released` flag SHALL ensure each manager is
released at most once per exit path.

## Scenario: ensure_release is released at run-end, self_managed_session is not

**Given** two runs — one with `comfy_lifecycle: "ensure_release"`, one with `comfy_lifecycle: "self_managed_session"` — each having constructed a `ComfyLifecycleManager` that the framework started
**When** each run ends normally
**Then** the `ensure_release` run calls `release("ensure_release")` and stops the ComfyUI process at run-end
**And** the `self_managed_session` run does NOT stop the ComfyUI process at run-end — it remains up for reuse by a subsequent `arun` on the same orchestrator instance

## Scenario: self_managed_session is released at Orchestrator.aclose

**Given** an orchestrator instance that ran one or more `self_managed_session` runs and started a ComfyUI process
**When** `await orchestrator.aclose()` is called (directly or via `async with`)
**Then** the orchestrator releases the orchestrator-instance-level manager and the framework-started ComfyUI process is stopped
**And** when `aclose()` is called on an orchestrator that never started a managed process, it is a no-op

## Scenario: No lifecycle manager for a lifecycle=none run

**Given** a run with no `comfy/local*` route, or a `comfy/local*` route with `comfy_lifecycle: "none"`
**When** `Orchestrator.arun` starts
**Then** no `ComfyLifecycleManager` is constructed and every `StepContext.lifecycle` is `None`
**And** there is no release call — behavior is identical to the pre-change path

## Non-Goals

- 不改 workflow 调度顺序、ready 判定、risk-ordered scheduling 或 DAG fan-out 的
  opt-in 语义(`parallel_dag`)—— 只换 executor 的执行机制与加 lifecycle 所有权。
- 不改 revise loop / checkpoint / budget 终止语义。
- lifecycle manager 不泛化成通用 `ManagedProcessRegistry`(SRS TBD-011 follow-on)。

## Validation

- Unit: `tests/unit/test_cascade_cancel.py`(扩 — 取消的 sibling 工作真停探针 +
  drain 超时显式失败)、`tests/unit/test_orchestrator.py`(扩 — lifecycle manager
  构造条件 + mode-aware release + `aclose()` disposal)。
- Integration: `tests/integration/test_dag_concurrency.py` 仍全绿。
- 测试总数不硬编码 —— 以 `python -m pytest -q` 实测为准。
