# Provider Routing — executor-async-rewrite delta

> 本文件是 `provider-routing` capability 在 `executor-async-rewrite`(TBD-010)change
> 引入的行为增量:ComfyAgentWorker async-subprocess、comfy-submission 串行锁、cancel
> 时 server-side `/interrupt`、`comfy_lifecycle` 三模式解锁、`ExternalProcessLifecycle`
> (`release(mode, reason)`)+ `ComfyLifecycleManager`,以及 framework-managed ComfyUI
> lifecycle 相关 Invariant / Non-Goal 的 MODIFIED / REMOVED。每条 Requirement 首行
> 标注 ADDED / MODIFIED / REMOVED。

## Requirement: ComfyAgentWorker invokes the agent CLI via an async subprocess under a process-wide submission lock

**ADDED.** The system SHALL invoke the `comfyui_api` agent CLI via
`asyncio.create_subprocess_exec` (NOT the blocking `subprocess.run`), and SHALL await
completion via `asyncio.wait_for(proc.communicate(), timeout=<s>)`. The four
capability entry points SHALL expose async primaries `agenerate` / `agenerate_mesh` /
`agenerate_audio` / `agenerate_video`; the historical sync names `generate` /
`generate_mesh` / `generate_audio` / `generate_video` SHALL be retained as thin
`asyncio.run(...)` shims so probe scripts that call the worker outside an event loop
keep working. `FakeComfyWorker` SHALL expose the same async surface.

The submit→poll critical section of each `agenerate*` call SHALL be wrapped in a
process-wide `asyncio.Lock` (`_comfy_submit_lock`), so that ForgeUE has at most one
ComfyUI prompt in flight on the ComfyUI server at any time. This is REQUIRED for
correct cancellation: `comfyui_api cancel` issues a global `POST /interrupt` that the
ComfyUI server applies to whichever prompt is currently running, irrespective of
which worker submitted it. Without the lock, a `parallel_dag` fan-out of two comfy
steps could have a cancel of one step interrupt a healthy sibling's prompt. The lock
imposes no real throughput cost — a single local ComfyUI GPU already executes prompts
serially.

## Scenario: Concurrent agenerate calls are serialized so only one comfy prompt is in flight

**Given** two comfy workers whose `agenerate` calls run concurrently (a `parallel_dag` fan-out of two comfy steps)
**When** both call `agenerate` at the same time
**Then** the `_comfy_submit_lock` serializes them — at most one `comfyui_api` subprocess is in flight at any instant; the second waits for the first to finish
**And** the sync shim `ComfyAgentWorker.generate(...)` still returns `list[ImageCandidate]` when called from a probe script with no running event loop

## Requirement: ComfyAgentWorker cancel terminates the subprocess and aborts the server-side prompt

**ADDED.** The system SHALL propagate `asyncio.CancelledError` into
`ComfyAgentWorker.agenerate*` at the `await proc.communicate()` point. On cancellation
(or `wait_for` timeout), the worker's `finally` block — still inside the
`_comfy_submit_lock` critical section — SHALL, in order: (1) issue a best-effort
server-side abort `comfyui_api cancel` (`POST http://127.0.0.1:8188/interrupt`),
which because the submission lock is still held is guaranteed to interrupt THIS
worker's prompt and not a sibling's; (2) `proc.terminate()` the `comfyui_api` CLI
subprocess, then `proc.kill()` after a bounded grace period if it has not exited.
The server-side abort SHALL be best-effort: a failure of the abort step SHALL be
logged as a warning and SHALL NOT mask the `CancelledError`. The worker SHALL NOT
leak the CLI subprocess after the awaiting task is cancelled.

## Scenario: Cancel during ComfyAgentWorker run aborts this worker's server prompt and terminates the CLI subprocess

**Given** a step awaiting `ComfyAgentWorker.agenerate` with a `comfyui_api` subprocess in flight, holding `_comfy_submit_lock`
**And** a sibling DAG step raising an exception that triggers `cascade_terminate`
**When** the orchestrator cancels the in-flight image step's task
**Then** `CancelledError` is raised inside `agenerate` at the `await proc.communicate()` point
**And** the `finally` block (lock still held) first runs `comfyui_api cancel` (server-side `POST /interrupt`) so the ComfyUI GPU job for this prompt is aborted, then calls `proc.terminate()` and `proc.kill()` if needed
**And** neither the `comfyui_api` CLI subprocess survives as an orphan nor the server-side prompt continues consuming GPU time, and `CancelledError` re-raises out of the worker

## Requirement: comfy_lifecycle supports ensure_running, ensure_release, and self_managed_session

**ADDED.** The system SHALL accept `step.config.spec.comfy_lifecycle` (and the
`FORGEUE_COMFY_LIFECYCLE` env default) as one of four values:

- `"none"` — assume a user-owned ComfyUI is already running (unchanged behavior).
- `"ensure_running"` — start ComfyUI if not already up, then leave it running (warm
  reuse; never released by the framework).
- `"ensure_release"` — `ensure_running` semantics, plus stop the instance at every
  run-exit path (run-end / cascade / cancel) if and only if this framework started it.
- `"self_managed_session"` — the framework owns one ComfyUI process held at the
  orchestrator-instance level, reused across multiple `arun` calls, released only at
  `Orchestrator.aclose()` (the `orchestrator_close` reason) — NOT at run-end, cascade,
  or `arun` cancel, since those are run-level events that do not end the session.

Any value outside this four-element set SHALL be rejected with
`WorkerUnsupportedResponse`. The lifecycle for the three non-`none` modes SHALL be
carried out by an `ExternalProcessLifecycle` handle, NOT by `ComfyAgentWorker` itself
(per-step workers are constructed inline and cannot own a session-scoped process).

## Scenario: A bundle requesting ensure_running starts ComfyUI when it is down

**Given** a step config with `comfy_lifecycle: "ensure_running"` and `FORGEUE_COMFY_LIFECYCLE=ensure_running`
**And** ComfyUI not currently running
**When** the run reaches the comfy-backed step
**Then** `ComfyLifecycleManager.ensure("ensure_running")` probes `comfyui_api status`, finds it down, spawns `python -m factory_v3 serve` detached, polls status until ready within a bounded timeout, and records the "framework started it" flag
**And** the step proceeds and the ComfyUI process is left running after the run completes

## Scenario: An unknown comfy_lifecycle value is rejected

**Given** a step config with `comfy_lifecycle: "warp_drive"` (not in the four-element set)
**When** the executor or worker resolves the spec
**Then** `WorkerUnsupportedResponse` is raised naming the unsupported value and listing the four accepted values
**And** no subprocess is spawned

## Requirement: ExternalProcessLifecycle abstracts a framework-managed external process with a reason-aware release contract

**ADDED.** The system SHALL define an abstract `ExternalProcessLifecycle` base class
in `src/framework/runtime/lifecycle.py` with three async methods — `ensure(mode)`,
`release(mode, reason)`, and `status()`. The `release` method SHALL take a `reason`
argument (`run_end` / `cascade` / `arun_cancel` / `orchestrator_close`) so that the
ENTIRE teardown contract — including `self_managed_session` teardown at
`orchestrator_close` — lives in the ABC; there SHALL be no concrete-only teardown
method that the orchestrator must downcast to reach. `ComfyLifecycleManager` SHALL be
the sole concrete implementation in this change, managing a ComfyUI process via the
`comfyui_api status` probe and the `python -m factory_v3 serve` / `stop` sister CLI.

`ComfyLifecycleManager.ensure` / `release` SHALL serialize their full state machine
under an `asyncio.Lock` — under DAG fan-out the same manager is injected into every
step, so two concurrent comfy steps may call `ensure` simultaneously; without the
lock both observe `_ensured == False` and race. `ensure` SHALL be idempotent. The
`_framework_started` ownership flag SHALL be set immediately after `_spawn_serve()`
returns, BEFORE `_wait_ready()` — so that a cancellation during the cold-start
readiness poll still leaves the manager able to stop the framework-started process
(setting it only after `_wait_ready()` would leak the process on cold-start cancel).

The abstraction exists so a second managed-subprocess provider (SRS TBD-011
follow-on) can be added as a second implementation conforming to the same
`release(mode, reason)` contract without changing the orchestrator-side wiring.

## Scenario: Concurrent ensure() calls start ComfyUI exactly once

**Given** a `ComfyLifecycleManager` whose `status()` first reports ComfyUI down
**When** two `ensure("ensure_release")` calls run concurrently (via `asyncio.gather`)
**Then** `_spawn_serve` is invoked exactly once, `_framework_started` ends up consistent, and a later `release` stops the process exactly once

## Scenario: Cancel during cold start still leaves the process releasable

**Given** a `ComfyLifecycleManager.ensure` that has spawned `factory_v3 serve` and is awaiting `_wait_ready()`
**When** the awaiting task is cancelled before readiness completes
**Then** `_framework_started` is already `True` (set right after `_spawn_serve`), so a subsequent `release(mode, reason)` on a stopping `(mode, reason)` still stops the framework-started ComfyUI process — it is not leaked

## Scenario: release(mode, reason) follows the decision table

**Given** a `ComfyLifecycleManager` that the framework itself started
**When** `release(mode, reason)` is called
**Then** it stops the process (`factory_v3 stop`) exactly for these `(mode, reason)` pairs: `(ensure_release, run_end)`, `(ensure_release, cascade)`, `(ensure_release, arun_cancel)`, `(ensure_release, orchestrator_close)`, `(self_managed_session, orchestrator_close)` — and for every other pair (`ensure_running` any reason; `self_managed_session` with `run_end` / `cascade` / `arun_cancel`) it is a no-op
**And** for a manager whose `ensure` found ComfyUI already running (user-owned), no `(mode, reason)` ever stops it

## Requirement: ComfyUI bundle spec uses manifest workflow + JSON params

**MODIFIED.** The system SHALL accept `step.config.spec.comfy_workflow` (string,
manifest name as listed by `python -m comfyui_api list`), `step.config.spec.comfy_params`
(dict, passed to `--params`), and optional `step.config.spec.comfy_lifecycle` (string;
one of `"none"` / `"ensure_running"` / `"ensure_release"` / `"self_managed_session"`;
defaults to `"none"`). The system SHALL reject the legacy
`step.config.spec.workflow_graph` field with `WorkerUnsupportedResponse` so a
partially migrated bundle fails fast. The system SHALL reject any `comfy_lifecycle`
value outside the four-element set with `WorkerUnsupportedResponse`. (This MODIFIES
the prior requirement of the same name: the `comfy-agent-cli-adoption` D6 constraint
that `comfy_lifecycle` MUST be `"none"`, and its scenario "Bundle requesting a
non-none comfy_lifecycle is rejected", are lifted by this change — TBD-010 — now that
the orchestrator awaits worker calls natively and cancellation reaches the subprocess.)

## Scenario: Bundle declaring comfy_workflow + comfy_params resolves through ComfyAgentWorker via worker dispatch

**Given** a step config `{"spec": {"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {"text": "oak barrel", "seed": 42}, "comfy_lifecycle": "none"}, "num_candidates": 1, "worker_timeout_s": 300}` whose `provider_policy.models_ref` resolves to a `prepared_routes` containing `ResolvedRoute(model="comfy/local", ...)`
**When** the `generate_image` executor's `_resolve_spec` reads the config and the worker-dispatch detector finds the `comfy/local` model id
**Then** the executor takes the worker-dispatch branch and `await`s the async ABC method `worker.agenerate(spec=..., num_candidates=1, seed=..., timeout_s=300)` returning `list[ImageCandidate]`
**And** the executor MUST NOT route through `router.image_generation(...)` for `comfy/local`-bearing routes, and MUST NOT read or accept any `workflow_graph` field

## Scenario: Bundle still carrying legacy workflow_graph fails fast

**Given** a step config still containing `step.config.spec.workflow_graph` (a leftover from the v1 inline-workflow bundle path captured at commit 292420a)
**When** the executor or worker resolves the spec
**Then** `WorkerUnsupportedResponse` is raised with a message naming the deprecated field and pointing at the new contract
**And** no subprocess is spawned, no HTTP call is made, and `FailureModeMap` routes the failure to `unsupported_response` → `Decision.abort_or_fallback`

## Requirement: ComfyAgentWorker cancel is best-effort under orchestrator to_thread wrapping

**REMOVED.** Reason: this change (TBD-010) makes `StepExecutor.execute` a native
async coroutine, so the orchestrator `await`s worker calls directly instead of
wrapping the synchronous executor in `asyncio.to_thread`. The premise of the prior
requirement — "`CancelledError` propagation does NOT reach `ComfyAgentWorker.generate`
while the synchronous executor is wrapped by `asyncio.to_thread`" — no longer holds.
Migration: replaced by the ADDED requirement "ComfyAgentWorker cancel terminates the
subprocess and aborts the server-side prompt" above; the obsolete scenario "Cancel
during ComfyAgentWorker run does not produce orphan processes" (which asserted the
subprocess "continues to run in the worker thread until ComfyUI finishes the request
naturally") is removed with it.

## Invariants

- **MODIFIED**: ComfyUI integration MAY run against a user-owned local ComfyUI
  (`comfy_lifecycle: "none"`, unchanged default) OR against a framework-managed
  ComfyUI process when the bundle / `FORGEUE_COMFY_LIFECYCLE` selects
  `ensure_running` / `ensure_release` / `self_managed_session`. (Supersedes the prior
  invariant "ComfyUI integration requires a user-owned local ComfyUI at
  `http://127.0.0.1:8188` (no framework-managed lifecycle)".)

## Non-Goals

- **REMOVED Non-Goal**: "Framework-managed ComfyUI process lifecycle (users own their
  ComfyUI)" — now an in-scope capability via `ComfyLifecycleManager` and the three
  non-`none` lifecycle modes.
- 不引入 image-to-video / video-to-video / standalone text-to-mesh 等新 capability
  路径 —— 本 change 只改执行机制与 lifecycle。
- 不改远端 `HunyuanTokenHubWorker` / Tripo3D mesh worker 的内部实现(已 async-native)。
- 不把 ComfyUI worker 配置从 `FORGEUE_COMFY_*` env 迁进 `config/models.yaml`
  (SRS TBD-011 follow-on)。
- 不做 prompt-scoped 的 ComfyUI cancel(捕获 prompt_id 精确取消)—— 那需改
  `D:/AI/ComfyUI/scripts/comfyui_api/` 用户自管共享目录;本 change 用进程级
  comfy-submission 串行锁达成等价的取消正确性。

## Validation

- Unit: `tests/unit/test_comfy_subprocess.py`(扩 — async-subprocess spawn /
  comfy-submission 锁串行 / cancel terminate + server-side `/interrupt` abort /
  sync-shim 兼容)、`tests/unit/test_comfy_lifecycle.py`(新 — `ComfyLifecycleManager`
  三模式 + 并发 `ensure` 单飞 + 冷启动 cancel 不泄漏 + `release(mode, reason)` 决策
  表 + "framework started it" 标志)。
- Integration: `tests/integration/test_example_bundles_smoke.py`(comfy bundle 仍
  loadable)。
- Level 2 live evidence:`python -m framework.run --task examples/comfy_local_smoke.json
  --live-llm --run-id <id>`,bundle `comfy_lifecycle: "ensure_running"`,验证框架自动
  拉起 ComfyUI;evidence note 落 `forge/changes/executor-async-rewrite/notes/`。
- 测试总数不硬编码 —— 以 `python -m pytest -q` 实测为准。
