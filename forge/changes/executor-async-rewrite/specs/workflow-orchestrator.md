# Workflow Orchestrator — executor-async-rewrite delta

> 本文件是 `workflow-orchestrator` capability 在 `executor-async-rewrite`(TBD-010)
> change 引入的行为增量:orchestrator 原生 `await` executor 取代 `to_thread`、
> cascade-cancel 真停(含 drain 超时显式失败)、orchestrator 持有 ComfyUI lifecycle
> 并以 `release(mode, reason)` 四路径释放 + `aclose()` disposal 钩子。每条
> Requirement 首行标注 ADDED。

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
/ workers before the run proceeds to its terminal state. The orchestrator SHALL
inspect the `(done, still_pending)` result: if `still_pending` is non-empty (a
cleanup hung past the drain timeout) the orchestrator SHALL NOT silently discard
those tasks — it SHALL record the stuck step ids in
`run.metrics["cancel_drain_timeout"]`, re-`cancel()` them, and end the run with a
failed status. This replaces the prior fire-and-forget behavior where cancelled tasks
were left to "finish in the background" because `asyncio.to_thread` threads could not
be interrupted.

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

## Requirement: Orchestrator owns the ComfyUI lifecycle and releases it with a reason

**ADDED.** When a bundle's `prepared_routes` reference a `comfy/local*` model AND the
resolved `comfy_lifecycle` (from `step.config.spec.comfy_lifecycle` or the
`FORGEUE_COMFY_LIFECYCLE` env default) is not `"none"`, the orchestrator SHALL obtain
a `ComfyLifecycleManager` and inject it into every step's `StepContext.lifecycle`.
For `self_managed_session` the manager SHALL be held at the orchestrator-instance
level (`self._lifecycle`) and reused across multiple `arun` calls; for
`ensure_running` / `ensure_release` it MAY be per-`arun`.

The orchestrator SHALL release a per-`arun` manager via a `try ... finally` around
the `arun` body so that `await manager.release(mode, reason)` runs exactly once on
EVERY exit path — including the unclassified-exception re-raise path (`classify_failure`
returning `None`, which in linear mode propagates straight out of `arun` without going
through the cascade branch). The orchestrator SHALL pass the matching `reason` and
SHALL NOT itself decide whether the process stops — that is the manager's
`(mode, reason)` decision:

| `arun` 退出方式 | `reason` |
|---|---|
| normal run-end | `run_end` |
| cascade-terminate (`run.status=failed`, normal return) | `cascade` |
| `asyncio.CancelledError` (re-raised) | `arun_cancel` |
| other unclassified `BaseException` (re-raised) | `arun_error` |

`Orchestrator.aclose()` releases the orchestrator-instance-level manager with the
separate `orchestrator_close` reason. Releasing on the `arun_error` path is REQUIRED
so an `ensure_release` ComfyUI process started by the framework is not leaked when an
executor bug / artifact-dump IO error / unclassified exception ends the run.

The release call in the `try/finally` AND in `aclose()` SHALL go through ONE shared
**bounded and non-masking** helper (`_release_lifecycle_bounded`): it SHALL run as
`await asyncio.wait_for(asyncio.shield(manager.release(mode, reason)),
timeout=_RELEASE_TIMEOUT_S)` wrapped in a `try/except BaseException`. A release that
fails, times out, or is itself cancelled (e.g. a second `cancel()` arriving during
the `finally`, or `factory_v3 stop` raising / hanging) SHALL be recorded and logged,
and SHALL NOT be re-raised — so the release failure neither hangs the caller
indefinitely nor masks the original exception / cancellation being propagated. The
failure-telemetry sink differs by caller: the `arun` `try/finally` records into
`run.metrics["lifecycle_release_failed"]`; `aclose()` (which has no `run`) records
into the orchestrator-instance attribute `self._lifecycle_release_failed`. `aclose()`
MUST NOT use a raw `await manager.release(...)`.

The system SHALL add `Orchestrator.aclose()` (`async def`) which calls
`release(mode, "orchestrator_close")` on the orchestrator-instance-level manager, and
the orchestrator SHALL implement async context manager protocol (`__aenter__` /
`__aexit__`, the latter calling `aclose()`). The CLI (`framework.run`) SHALL call
`await orch.aclose()` before process exit. A `_released` flag SHALL ensure each
manager is released at most once per exit path.

## Scenario: Orchestrator passes the matching reason on each exit path

**Given** a run with a `comfy_lifecycle != "none"` route that constructed a `ComfyLifecycleManager`
**When** the run ends normally / a cascade fires / the `arun` task is cancelled / an unclassified exception re-raises out of `arun` / `aclose()` is called
**Then** the `try/finally` around the `arun` body calls `release(mode, "run_end")` / `release(mode, "cascade")` / `release(mode, "arun_cancel")` / `release(mode, "arun_error")` respectively, and `aclose()` calls `release(mode, "orchestrator_close")`
**And** whether the ComfyUI process actually stops is decided by the manager's `(mode, reason)` table — the orchestrator only reports the correct reason for the path

## Scenario: ensure_release is released even when an unclassified exception ends the run

**Given** an `ensure_release` run whose `ComfyLifecycleManager` has already started a ComfyUI process
**When** an executor raises an unclassified exception (`classify_failure` returns `None`) that re-raises out of `arun`
**Then** the `arun` `try/finally` still calls `release(mode, "arun_error")`, the manager runs `factory_v3 stop`, and the framework-started ComfyUI process is not leaked

## Scenario: A failing or hanging release does not mask the original exception or hang the run

**Given** an `arun` propagating an original exception (or a `CancelledError`) whose `finally`-block release call has `_spawn_stop()` raise an error, hang past `_RELEASE_TIMEOUT_S`, or be hit by a second `cancel()`
**When** the bounded `_release_lifecycle_bounded` helper's `await asyncio.wait_for(asyncio.shield(manager.release(...)), timeout=_RELEASE_TIMEOUT_S)` fails / times out / is cancelled
**Then** the orchestrator records `run.metrics["lifecycle_release_failed"]` (mode / reason / error) and logs a warning, does NOT re-raise the release failure, and the original exception or cancellation that `arun` was propagating is preserved unmasked
**And** `arun` is not hung indefinitely by a stuck `factory_v3 stop`

## Scenario: aclose() release is bounded and non-masking through the same helper

**Given** an `Orchestrator.aclose()` whose `self_managed_session` manager's `_spawn_stop()` raises, hangs past `_RELEASE_TIMEOUT_S`, or is hit by a cancel
**When** `aclose()` releases the manager via the shared `_release_lifecycle_bounded` helper (NOT a raw `await manager.release(...)`)
**Then** `aclose()` is not hung indefinitely, the failure is recorded in the orchestrator-instance attribute `self._lifecycle_release_failed` and logged, and the failure is not re-raised so it does not mask any exception propagating through `__aexit__`

## Scenario: ensure_release stops at run-end, self_managed_session stops only at aclose

**Given** two runs — one `comfy_lifecycle: "ensure_release"`, one `self_managed_session` — each having started a ComfyUI process
**When** each run ends normally
**Then** the `ensure_release` run's `release(mode, "run_end")` stops the process; the `self_managed_session` run's `release(mode, "run_end")` is a no-op and the process remains up for reuse by a subsequent `arun`
**And** when `await orchestrator.aclose()` is later called, `release("self_managed_session", "orchestrator_close")` stops the process; `aclose()` on an orchestrator that never started a managed process is a no-op

## Scenario: No lifecycle manager for a lifecycle=none run

**Given** a run with no `comfy/local*` route, or a `comfy/local*` route with `comfy_lifecycle: "none"`
**When** `Orchestrator.arun` starts
**Then** no `ComfyLifecycleManager` is constructed and every `StepContext.lifecycle` is `None`
**And** there is no release call — behavior is identical to the pre-change path

## Non-Goals

- 不改 workflow 调度顺序、ready 判定、risk-ordered scheduling 或 DAG fan-out 的
  opt-in 语义(`parallel_dag`)—— 只换 executor 的执行机制与加 lifecycle 所有权。
  (comfy-submission 串行锁是 worker 级锁,不改调度。)
- 不改 revise loop / checkpoint / budget 终止语义。
- lifecycle manager 不泛化成通用 `ManagedProcessRegistry`(SRS TBD-011 follow-on)。

## Validation

- Unit: `tests/unit/test_cascade_cancel.py`(扩 — 取消的 sibling 工作真停探针 +
  drain 超时显式失败)、`tests/unit/test_orchestrator.py`(扩 — lifecycle manager
  构造条件 + 四路径 `release(mode, reason)` + `aclose()` disposal)。
- Integration: `tests/integration/test_dag_concurrency.py` 仍全绿。
- 测试总数不硬编码 —— 以 `python -m pytest -q` 实测为准。
