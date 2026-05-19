# Workflow Orchestrator — executor-async-rewrite delta

> 本文件是 `workflow-orchestrator` capability 在 `executor-async-rewrite`(TBD-010)
> change 引入的行为增量:orchestrator 原生 `await` executor 取代 `to_thread`、
> cascade-cancel 真停、orchestrator 持有 ComfyUI lifecycle 所有权。每条 Requirement
> 首行标注 ADDED。

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

## Requirement: Cascade-cancel propagates real cancellation into running siblings

**ADDED.** When a DAG fan-out cascade is triggered (a sibling raises an exception OR a
sibling returns `_StepOutcome(terminate=True)`), the orchestrator SHALL `cancel()` the
still-pending sibling tasks AND SHALL `await` them under a bounded timeout so that
cancellation actually unwinds the running executors / workers — terminating
subprocesses and closing HTTP connections — before the run proceeds to its terminal
state. This replaces the prior fire-and-forget behavior where cancelled tasks were
left to "finish in the background" because `asyncio.to_thread` threads could not be
interrupted.

## Scenario: A cascade-cancelled sibling's work actually stops

**Given** a DAG fan-out with two concurrent steps where step A raises a classified failure (or terminates) while step B is still awaiting a provider / worker call
**When** the orchestrator's cascade path runs
**Then** it cancels step B's task and awaits it within a bounded timeout, and `CancelledError` propagates into step B's executor and into the provider / worker call, which aborts its in-flight work
**And** step B does not continue consuming external API calls or subprocess time after the run has been marked for termination
**And** `tests/unit/test_cascade_cancel.py` is extended with a probe (a counter that would keep incrementing if the cancelled work continued) asserting the cancelled sibling's work observably stopped

## Requirement: Orchestrator owns the ComfyUI lifecycle for the run session

**ADDED.** When a bundle's `prepared_routes` reference a `comfy/local*` model AND the
resolved `comfy_lifecycle` (from `step.config.spec.comfy_lifecycle` or the
`FORGEUE_COMFY_LIFECYCLE` env default) is not `"none"`, the orchestrator SHALL
construct a single `ComfyLifecycleManager` at `arun` start, inject it into every
step's `StepContext.lifecycle`, and SHALL invoke `release(mode)` on it along all
three run-exit paths: normal run-end, cascade-terminate, and the
`except asyncio.CancelledError` handler. When no comfy-managed-lifecycle route is
present, no manager is constructed and `StepContext.lifecycle` stays `None`.

## Scenario: Lifecycle manager is released on every run-exit path

**Given** a run that constructed a `ComfyLifecycleManager` (a `comfy/local*` route with `comfy_lifecycle != "none"`)
**When** the run ends normally, OR a cascade-terminate fires, OR the `arun` task itself is cancelled
**Then** the orchestrator calls `await manager.release(mode)` on that exit path exactly once
**And** an `ensure_release` / `self_managed_session` ComfyUI process started by the framework is torn down rather than orphaned

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

- Unit: `tests/unit/test_cascade_cancel.py`(扩 — 取消的 sibling 工作真停探针)、
  `tests/unit/test_orchestrator.py`(扩 — lifecycle manager 构造条件 + 三路径
  release)。
- Integration: `tests/integration/test_dag_concurrency.py` 仍全绿。
- 测试总数不硬编码 —— 以 `python -m pytest -q` 实测为准。
