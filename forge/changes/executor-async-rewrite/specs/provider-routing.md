# Provider Routing — executor-async-rewrite delta

> 本文件是 `provider-routing` capability 在 `executor-async-rewrite`(TBD-010)change
> 引入的行为增量:ComfyAgentWorker async-subprocess、cancel 时 server-side
> `/interrupt`、`comfy_lifecycle` 三模式解锁、`ExternalProcessLifecycle` +
> `ComfyLifecycleManager`,以及 framework-managed ComfyUI lifecycle 相关 Invariant /
> Non-Goal 的 MODIFIED / REMOVED。每条 Requirement 首行标注 ADDED / MODIFIED /
> REMOVED。

## Requirement: ComfyAgentWorker invokes the agent CLI via an async subprocess

**ADDED.** The system SHALL invoke the `comfyui_api` agent CLI via
`asyncio.create_subprocess_exec` (NOT the blocking `subprocess.run`), and SHALL await
completion via `asyncio.wait_for(proc.communicate(), timeout=<s>)`. The four
capability entry points SHALL expose async primaries `agenerate` / `agenerate_mesh` /
`agenerate_audio` / `agenerate_video`; the historical sync names `generate` /
`generate_mesh` / `generate_audio` / `generate_video` SHALL be retained as thin
`asyncio.run(...)` shims so probe scripts that call the worker outside an event loop
keep working (mirrors the `mesh_worker.py` async-primary + sync-shim pattern).
`FakeComfyWorker` SHALL expose the same async surface.

## Scenario: ComfyAgentWorker spawns the agent CLI through create_subprocess_exec and awaits it

**Given** a resolved route `ResolvedRoute(model="comfy/local", kind="image", pricing=None)` and `FORGEUE_COMFY_SCRIPTS_DIR` set
**When** `GenerateImageExecutor.execute` awaits `ComfyAgentWorker.agenerate(spec=..., num_candidates=1, seed=..., timeout_s=300)`
**Then** the worker spawns `python -m comfyui_api run ...` via `asyncio.create_subprocess_exec`, awaits `asyncio.wait_for(proc.communicate(), timeout=300+buffer)`, and parses the stdout JSON envelope
**And** no `subprocess.run` call and no nested `asyncio.run` occur on the orchestrator's event loop
**And** the sync shim `ComfyAgentWorker.generate(...)` still returns `list[ImageCandidate]` when called from a probe script with no running event loop

## Requirement: ComfyAgentWorker cancel terminates the subprocess and aborts the server-side prompt

**ADDED.** The system SHALL propagate `asyncio.CancelledError` into
`ComfyAgentWorker.agenerate*` at the `await proc.communicate()` point. On cancellation
(or `wait_for` timeout), the worker's `finally` block SHALL, in order: (1) issue a
best-effort server-side abort — `comfyui_api cancel` (`POST
http://127.0.0.1:8188/interrupt`, which interrupts the running ComfyUI prompt and
does NOT require a `prompt_id`) — so the server-side GPU job stops rather than
running to completion; (2) `proc.terminate()` the `comfyui_api` CLI subprocess, then
`proc.kill()` after a bounded grace period if it has not exited. The server-side
abort SHALL be best-effort: a failure of the abort step SHALL be logged as a warning
and SHALL NOT mask the `CancelledError`. The worker SHALL NOT leak the CLI subprocess
after the awaiting task is cancelled.

## Scenario: Cancel during ComfyAgentWorker run aborts the server prompt and terminates the CLI subprocess

**Given** a step awaiting `ComfyAgentWorker.agenerate` with a `comfyui_api` subprocess in flight
**And** a sibling DAG step raising an exception that triggers `cascade_terminate`
**When** the orchestrator cancels the in-flight image step's task
**Then** `CancelledError` is raised inside `agenerate` at the `await proc.communicate()` point
**And** the `finally` block first runs `comfyui_api cancel` (server-side `POST /interrupt`) so the ComfyUI GPU job is aborted, then calls `proc.terminate()` and `proc.kill()` if needed
**And** neither the `comfyui_api` CLI subprocess survives as an orphan nor the server-side prompt continues consuming GPU time, and `CancelledError` re-raises out of the worker

## Requirement: comfy_lifecycle supports ensure_running, ensure_release, and self_managed_session

**ADDED.** The system SHALL accept `step.config.spec.comfy_lifecycle` (and the
`FORGEUE_COMFY_LIFECYCLE` env default) as one of four values:

- `"none"` — assume a user-owned ComfyUI is already running (unchanged behavior).
- `"ensure_running"` — start ComfyUI if not already up, then leave it running (warm
  reuse; never released by the framework).
- `"ensure_release"` — `ensure_running` semantics, plus stop the instance at run end
  / cascade / cancel if and only if this framework started it.
- `"self_managed_session"` — the framework owns one ComfyUI process held at the
  orchestrator-instance level, reused across multiple `arun` calls, NOT released at
  normal run-end; released only at cascade / cancel or `Orchestrator.aclose()`.

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

## Requirement: ExternalProcessLifecycle abstracts a framework-managed external process with concurrency-safe state

**ADDED.** The system SHALL define an abstract `ExternalProcessLifecycle` base class
in `src/framework/runtime/lifecycle.py` with three async methods — `ensure(mode)`
(bring the process up as required by the mode), `release(mode)` (tear it down per the
mode), and `status()` (report whether the process is up). `ComfyLifecycleManager`
SHALL be the sole concrete implementation in this change, managing a ComfyUI process
via the `comfyui_api status` probe and the `python -m factory_v3 serve` / `stop`
sister CLI.

`ComfyLifecycleManager.ensure` / `release` SHALL serialize their full state machine
under an `asyncio.Lock`: under DAG fan-out the same manager instance is injected into
every step's `StepContext.lifecycle`, so two concurrent comfy steps may call `ensure`
simultaneously. Without the lock both would observe `_ensured == False` and race to
`status()` / `_spawn_serve()` / write `_framework_started`, causing duplicate startup
or a wrong / missed stop. The `ensure` call SHALL be idempotent (a manager started
once is not started again).

The abstraction exists so a second managed-subprocess provider (SRS TBD-011
follow-on) can be added as a second implementation without changing the
orchestrator-side wiring.

## Scenario: Concurrent ensure() calls start ComfyUI exactly once

**Given** a `ComfyLifecycleManager` whose `status()` first reports ComfyUI down
**When** two `ensure("ensure_release")` calls run concurrently (via `asyncio.gather`), as happens when a DAG fans out two comfy steps
**Then** `_spawn_serve` is invoked exactly once, `_framework_started` ends up consistent, and a later `release` stops the process exactly once
**And** `tests/unit/test_comfy_lifecycle.py` fences this concurrent-ensure single-flight behavior

## Scenario: ComfyLifecycleManager release is mode-aware

**Given** a `ComfyLifecycleManager` that the framework itself started
**When** `release(mode)` runs at normal run-end
**Then** for `ensure_release` the manager runs `python -m factory_v3 stop`; for `ensure_running` and `self_managed_session` the manager does NOT stop the process at run-end
**And** for a manager whose `ensure` found ComfyUI already running (user-owned), no mode ever stops it
**And** `self_managed_session` teardown happens via `Orchestrator.aclose()` / cancel path, not at run-end

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

## Validation

- Unit: `tests/unit/test_comfy_subprocess.py`(扩 — async-subprocess spawn / cancel
  terminate + server-side `/interrupt` abort / sync-shim 兼容)、
  `tests/unit/test_comfy_lifecycle.py`(新 — `ComfyLifecycleManager` 三模式 +
  并发 `ensure` 单飞 + mode-aware release + "framework started it" 标志)。
- Integration: `tests/integration/test_example_bundles_smoke.py`(comfy bundle 仍
  loadable)。
- Level 2 live evidence:`python -m framework.run --task examples/comfy_local_smoke.json
  --live-llm --run-id <id>`,bundle `comfy_lifecycle: "ensure_running"`,验证框架自动
  拉起 ComfyUI;evidence note 落 `forge/changes/executor-async-rewrite/notes/`。
- 测试总数不硬编码 —— 以 `python -m pytest -q` 实测为准。
