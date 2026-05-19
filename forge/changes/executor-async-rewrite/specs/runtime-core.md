# Runtime Core — executor-async-rewrite delta

> 本文件是 `runtime-core` capability 在 `executor-async-rewrite`(TBD-010)change 引入
> 的行为增量:`StepExecutor.execute` ABC 由 sync 改原生 async,`StepContext` 新增可选
> `lifecycle` 字段。每条 Requirement 首行标注 ADDED / MODIFIED。

## Requirement: StepExecutor.execute is a native async coroutine

**ADDED.** The system SHALL define `StepExecutor.execute` (the abstract method in
`src/framework/runtime/executors/base.py`) as `async def execute(self, ctx:
StepContext) -> ExecutorResult`. Every concrete executor — `generate_image`,
`generate_image_edit`, `generate_mesh`, `generate_audio`, `generate_video`,
`generate_structured`, `review`, `select`, `validate`, `export`, and the mock
executors — SHALL implement `execute` as an `async def`. The orchestrator SHALL
`await executor.execute(ctx)` directly; it SHALL NOT wrap the executor in
`asyncio.to_thread`. There is no synchronous `execute` compatibility shim — the
contract is async-only.

I/O-bound executors SHALL reach the provider layer through its async surface
(`await router.aimage_generation` / `astructured_with_usage` / `worker.agenerate*`);
they SHALL NOT call the synchronous provider shims (which internally do `asyncio.run`
and would nest event loops). An executor whose body is pure CPU / local-filesystem
work MAY be an `async def` with no `await`; if such a body does genuinely heavy
blocking work it MAY wrap that inner section in `await asyncio.to_thread(...)`, but
the executor's own `execute` entry point is always `async def`.

## Scenario: Orchestrator awaits an async executor without to_thread

**Given** a registered concrete executor whose `execute` is declared `async def`
**When** the orchestrator's `_aexec_one_body` runs the step
**Then** it evaluates `exec_result = await executor.execute(ctx)` on the running event loop with no `asyncio.to_thread` wrapper and no nested `asyncio.run`
**And** the executor's `await` points on router / worker calls run as ordinary awaits on the same loop

## Scenario: A cancelled step propagates CancelledError out of the executor

**Given** an async executor awaiting a provider / worker call when its orchestrator task is cancelled
**When** `asyncio.CancelledError` is raised into the executor at the `await` point
**Then** the executor does not swallow `CancelledError` — it is excluded from `classify_failure` and the orchestrator's `except asyncio.CancelledError: raise` continues to hold
**And** the cancellation propagates to the provider / worker, which aborts its in-flight work (HTTP request closed, subprocess terminated) rather than running to completion in a detached thread

## Requirement: StepContext exposes an optional lifecycle handle

**ADDED.** The system SHALL add an optional `lifecycle: ExternalProcessLifecycle |
None = None` field to `StepContext` (`src/framework/runtime/executors/base.py`). When
a run uses a non-`none` ComfyUI lifecycle mode, the orchestrator SHALL inject the
run-session's `ComfyLifecycleManager` into this field; otherwise it stays `None`.
Executors and workers needing to ensure an external process is up SHALL read
`ctx.lifecycle` rather than constructing their own lifecycle manager (per-step workers
cannot own a session-scoped process). The default `None` keeps existing test mocks
and `lifecycle="none"` runs unchanged.

## Scenario: StepContext.lifecycle is None for a lifecycle=none run

**Given** a run whose bundle uses `comfy_lifecycle: "none"`, or a run with no comfy step at all
**When** the orchestrator constructs `StepContext` for each step
**Then** `ctx.lifecycle is None` and no `ComfyLifecycleManager` is constructed
**And** behavior is identical to the pre-change path

## Scenario: StepContext.lifecycle carries the session manager for a managed-lifecycle run

**Given** a run whose bundle resolves a `comfy/local*` route and selects `comfy_lifecycle: "ensure_running"`
**When** the orchestrator constructs `StepContext` for each step
**Then** `ctx.lifecycle` is the single run-session `ComfyLifecycleManager` instance
**And** it is the same object for every step in the run

## Non-Goals

- 不改 `StepExecutor` / `ExecutorResult` / `ExecutorRegistry` 的其他契约 —— 只把
  `execute` 由 sync 改 async,registry resolve 语义不变。
- 不改 `StepContext.run_dir` 的语义(沿 `comfy-agent-cli-adoption` 既有 Requirement)。
- 不引入第三方 async 框架;只用 stdlib asyncio。

## Validation

- Unit: `tests/unit/test_step_context.py`(扩 — `lifecycle` 字段默认 None + 注入)、
  既有 executor 单测全部转 `pytest.mark.asyncio`。
- Integration: `tests/integration/test_p{0,1,2,3,4}_*.py` 仍全绿(执行机制改变对
  端到端行为透明)。
- 测试总数不硬编码 —— 以 `python -m pytest -q` 实测为准。
