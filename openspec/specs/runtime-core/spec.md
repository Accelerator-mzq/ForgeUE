# runtime-core

## Purpose

Runtime-core owns the Run lifecycle: a Task becomes a Run, the Run is scheduled as a graph of Steps, each Step yields Artifacts and Checkpoints, Verdicts drive transitions, BudgetTracker accumulates cost, EventBus emits progress, and FailureModeMap classifies exceptions into recoverable Decisions. Everything else in ForgeUE sits on top of this spine.

## Source Documents

- `docs/requirements/SRS.md` §3.2 (FR-LC-001~008), §3.9 (FR-RUNTIME-001~012), §3.10 (FR-COST-001~009 cost wiring inside BudgetTracker), §3.11 (FR-OBS-001~006), §4.2 (NFR-REL-001~009), §4.5 (NFR-OBS-001~004), §4.8 ADR-006 / ADR-007
- `docs/design/HLD.md` §2 layered view, §3 subsystems, §5 collaboration (9-stage lifecycle)
- `docs/design/LLD.md` §5.7 failure-mode map (only invariants are lifted; field tables stay in LLD)
- `CHANGELOG.md` [Unreleased] TBD-007 mesh retry collapse (ADR-007)
- Source: `src/framework/runtime/orchestrator.py`, `scheduler.py`, `dry_run_pass.py`, `checkpoint_store.py`, `transition_engine.py`, `budget_tracker.py`, `failure_mode_map.py`, `executors/`
- Source: `src/framework/observability/` (EventBus, Compactor, Secrets, OTel tracing)
- Source: `src/framework/run.py:62-73` (adapter registration order)

## Current Behavior

Every Run passes through the nine pipeline stages: Task ingestion → Workflow resolution → DryRunPass → Scheduling plan → Step execution → Verdict dispatching → Validation gates → Export → Run finalize. DryRunPass is a zero-side-effect pre-flight — if it fails, the Run moves to `failed` and no executor runs. After each Step, Orchestrator first writes `cost_usd` into `exec_result.metrics` and then records a Checkpoint so a cross-process resume can replay the budget.

`TransitionEngine` converts every Verdict into the next Step; `cloned_for_run()` hands each `Orchestrator.arun()` entrypoint a private counter set (ADR-006). `BudgetTracker` accumulates cost per Step and synthesizes a `budget_exceeded` Verdict when the cap is hit. `FailureModeMap` classifies exceptions into eight failure modes, each mapping to a `Decision`; `unsupported_response` takes the `abort_or_fallback` path and never loops back to the same step with a new billable call.

`EventBus` is loop-aware (each Subscription captures its owning loop) and thread-safe (`_subs` is guarded by a `threading.Lock`); cross-thread publishes round-trip through `loop.call_soon_threadsafe`. The WebSocket progress server (`framework.server.ws_server`) binds to `127.0.0.1` by default and uses `asyncio.wait(FIRST_COMPLETED)` to watch both events and `receive_disconnect`.

## Requirements

### Requirement: 9-stage Run lifecycle is strict

The system SHALL execute every Run through the nine stages defined in SRS §3.2 in order.

#### Scenario: DryRunPass failure aborts the Run

- GIVEN a Task whose bundle has an unresolved `input_bindings.source`
- WHEN `Orchestrator.arun()` is called
- THEN DryRunPass flags the error, the Run status becomes `failed`, and no executor is invoked

### Requirement: Checkpoint persistence survives cross-process resume

The system SHALL dump artifact metadata to `<run_dir>/_artifacts.json` after each Step and SHALL reload it via `ArtifactRepository.load_run_metadata` on `--resume`; without this reload `find_hit` would miss and silently re-execute steps.

#### Scenario: Resume reloads artifact metadata and hits cache

- GIVEN a Run completed two Steps and was interrupted (process exited)
- WHEN the same `run_id` is resumed in a fresh process
- THEN `load_run_metadata` rebuilds the index, `find_hit` returns cached entries, and the Step is skipped

#### Scenario: Length mismatch forces a cache miss

- GIVEN a Checkpoint where `len(artifact_ids) != len(artifact_hashes)`
- WHEN `CheckpointStore.find_hit` is called
- THEN the method returns MISS (never a silent `zip()` truncation)

### Requirement: `load_run_metadata` performs three-stage filtering

The system SHALL skip already-known ids, SHALL skip entries whose backend `exists()` returns False, and SHALL skip entries whose on-disk byte hash does not match the recorded hash.

### Requirement: TransitionEngine is isolated per `arun`

The system SHALL call `cloned_for_run()` at the `Orchestrator.arun()` entrypoint so that sequential or concurrent Runs never share Transition counters; the clone MUST preserve subclass identity and instance attributes.

### Requirement: Cost is persisted before Checkpoint

The system SHALL write `cost_usd` into `exec_result.metrics` BEFORE `checkpoints.record(metrics=...)` so a cross-process resume recovers the budget from `cp.metrics["cost_usd"]`.

#### Scenario: Cache-hit replays cost into a fresh BudgetTracker

- GIVEN a Run resumed in a fresh process with `task.budget_policy` set
- WHEN `find_hit` returns a cached entry
- THEN the Orchestrator re-records `cp.metrics["cost_usd"]` into BudgetTracker, de-duplicated by `spend.by_step`

### Requirement: Unsupported-response short-circuit at three layers

The system SHALL exclude `*UnsupportedResponse` from `with_transient_retry_async.transient_check`, SHALL re-raise it in `CapabilityRouter` before the generic `except ProviderError` branch, and SHALL return False from the four executors' `_should_retry` first line — all three layers are required; missing any one produces an extra billable call.

### Requirement: Premium-API single-attempt contract

The system SHALL force `attempts = 1` for `capability_ref="mesh.generation"` inside `GenerateMeshExecutor` and SHALL NOT wrap `mesh_worker._apost` in `with_transient_retry_async`; on failure the CLI SHALL surface `job_id` on stderr so the user can query remote state before deciding to `--resume`.

### Requirement: Budget exceeded synthesizes a Verdict

The system SHALL, when `BudgetTracker.check()` trips the cost cap, synthesize a `budget_exceeded` Verdict and route it through TransitionEngine to terminate the Run; the Run MUST NOT silently exit.

### Requirement: EventBus is loop-aware and thread-safe

The system SHALL use a `threading.Lock` around `_subs` and SHALL publish cross-thread events via `loop.call_soon_threadsafe` so a subscription registered on one event loop never blocks on another thread's emission.

### Requirement: WebSocket idle-disconnect is leak-free

The system SHALL run each WS handler under `asyncio.wait(FIRST_COMPLETED)` covering both the event queue and `receive_disconnect`, and SHALL release the Subscription when the client disconnects.

## Invariants

- `LiteLLMAdapter` (wildcard) is registered LAST in the adapter chain (ADR-003); see `src/framework/run.py:62-73`.
- Every exception path maps to a `FailureMode` (NFR-REL-001); no bare/un-classified raise escapes to the user.
- `retry_same_step` in DAG mode must re-execute the step (`test_cascade_cancel::test_dag_retry_same_step_reexecutes` guards against the old `if next_id == current: break` silent-swallow bug).
- ChiefJudge always runs judges through `asyncio.gather`; no sequential fallback.
- WS server binds `127.0.0.1` by default (NFR-SEC-005); exposing to the public network is an explicit deployment decision.
- `disk_full` maps to `rollback → stop`; no further Artifact writes are allowed.
- ArtifactRepository snapshots (`list(...)`) are required inside `find_by_producer` during DAG fan-out (NFR-REL-009).

## Validation

- Unit: `tests/unit/test_transition_engine.py`, `test_failure_mode_map.py`, `test_checkpoint_store.py`, `test_dry_run_pass.py`, `test_budget_tracker.py`, `test_event_bus.py`, `test_cascade_cancel.py`, `test_cancellation.py`, `test_codex_audit_fixes.py`, `test_scheduler_risk_ordering.py`, `test_progress_passthrough.py`, `test_compactor.py`
- Integration: `tests/integration/test_p0_mock_linear.py`, `tests/integration/test_dag_concurrency.py`, `tests/integration/test_ws_progress.py`
- Offline smoke: `python -m framework.run --task examples/mock_linear.json --run-id demo --artifact-root ./artifacts`
- Test totals: see `python -m pytest -q` actual output (do not hardcode).

## Non-Goals

- Multi-tenant permission system (SRS §2.5); `project_id` stays logical-only.
- Bidirectional real-time control channel (WS is push-only).
- Rendering, animation, or physics simulation.
- Chat-style agent framework integration (SRS §2.5).
