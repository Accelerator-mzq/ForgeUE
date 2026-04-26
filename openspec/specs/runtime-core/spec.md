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

#### Scenario: load_run_metadata skips entries already in the index and entries whose backend payload is missing

- GIVEN an `<run_dir>/_artifacts.json` dump containing N artifact records, some of which are already registered in `ArtifactRepository._artifacts` (same `artifact_id`) and some of which point to payload refs whose backing file is no longer on disk (e.g. partial-write corruption / external cleanup)
- WHEN `ArtifactRepository.load_run_metadata(run_id=<id>, run_dir=<run_dir>)` runs (`src/framework/artifact_store/repository.py`)
- THEN the loader iterates the dump and `continue`s past any record whose `art.artifact_id` already lives in `self._artifacts` (no double-registration), and `continue`s past any record whose `self._registry.exists(art.payload_ref)` returns False (or raises `KeyError`); only the surviving records reach `register_existing(art)` and increment the returned count `n`. `tests/unit/test_codex_audit_fixes.py::test_repository_metadata_dump_and_load_roundtrip` (line 639) and `::test_load_run_metadata_skips_missing_payload` (line 666) fence the dedup and missing-payload sides of this contract

#### Scenario: load_run_metadata skips file-backed entry whose on-disk hash drifted from the recorded hash

- GIVEN a dump entry whose `payload_ref.kind` is `file` or `blob` (i.e. external bytes), where the bytes on disk have drifted from the recorded `art.hash` since the last write (e.g. operator overwrite / partial write / manual edit); inline payloads are NOT subject to this recheck because their bytes travel with the metadata
- WHEN `load_run_metadata` reaches that entry and calls `self._registry.read(art.payload_ref)` followed by `hash_payload(current) != art.hash`
- THEN the loader `continue`s past the drifted entry without registering it, so a subsequent `CheckpointStore.find_hit()` returns MISS rather than treating the drifted bytes as a valid cache hit and propagating broken data to downstream Steps; `tests/unit/test_codex_audit_fixes.py::test_resume_yields_cache_hits_after_reload` (line 697) covers the happy resume path and `::test_load_run_metadata_skips_corrupted_payload` (line 896) fences the hash-drift skip — the recheck is scoped strictly to `file` / `blob` kinds and does NOT apply to inline payloads

### Requirement: TransitionEngine is isolated per `arun`

The system SHALL call `cloned_for_run()` at the `Orchestrator.arun()` entrypoint so that sequential or concurrent Runs never share Transition counters; the clone MUST preserve subclass identity and instance attributes.

#### Scenario: Two concurrent Orchestrator.arun() invocations get distinct TransitionEngine clones with isolated retry / revise counters

- GIVEN an `Orchestrator` with a single `TransitionEngine` instance attached at construction time, two concurrent `arun()` invocations on independent `(task, workflow, run_id)` triples that each issue `revise` / `retry_same_step` Verdicts
- WHEN each `arun()` entrypoint calls `transitions = self.transition_engine.cloned_for_run()` (`src/framework/runtime/transition_engine.py:42-55` — uses `copy.copy(self)` then resets `clone.counters = TransitionCounters()`) and routes its Verdicts through that clone
- THEN the two runs maintain independent retry / revise counters: one run's `inc_retry(step_id)` does NOT advance the other run's counter for the same `step_id`, and a `max_retries` exhaustion in run A does not prematurely terminate run B; the clone preserves subclass identity and any caller-set instance attributes (no attribute loss); `tests/unit/test_codex_audit_fixes.py::test_orchestrator_uses_fresh_transition_engine_per_arun` (line 370) and `::test_orchestrator_concurrent_arun_does_not_share_counters` (line 420) and `::test_transition_engine_clone_preserves_subclass_and_attrs` (line 741) fence all three invariants (ADR-006)

### Requirement: Cost is persisted before Checkpoint

The system SHALL write `cost_usd` into `exec_result.metrics` BEFORE `checkpoints.record(metrics=...)` so a cross-process resume recovers the budget from `cp.metrics["cost_usd"]`.

#### Scenario: Cache-hit replays cost into a fresh BudgetTracker

- GIVEN a Run resumed in a fresh process with `task.budget_policy` set
- WHEN `find_hit` returns a cached entry
- THEN the Orchestrator re-records `cp.metrics["cost_usd"]` into BudgetTracker, de-duplicated by `spend.by_step`

### Requirement: Unsupported-response short-circuit at three layers

The system SHALL exclude `*UnsupportedResponse` from `with_transient_retry_async.transient_check`, SHALL re-raise it in `CapabilityRouter` before the generic `except ProviderError` branch, and SHALL return False from the four executors' `_should_retry` first line — all three layers are required; missing any one produces an extra billable call.

#### Scenario: Layer 1 with_transient_retry_async treats *UnsupportedResponse as non-transient and re-raises after a single attempt

- GIVEN a provider call wrapped in `with_transient_retry_async(fn, max_attempts=N, transient_check=<callsite>)` (`src/framework/providers/_retry_async.py:22-36`) where `<callsite>` is the per-call `transient_check(exc) -> bool` callable supplied by the adapter / worker layer; the wrapped call raises `ProviderUnsupportedResponse` (or its subclass `MeshWorkerUnsupportedResponse`) on the first attempt
- WHEN `with_transient_retry_async` runs and the per-callsite `transient_check(exc)` returns False for `*UnsupportedResponse`
- THEN the helper short-circuits immediately (`if attempt + 1 >= max_attempts or not transient_check(exc): raise` at line 36) and does NOT enter the back-off loop for additional attempts; the original exception escapes upward unchanged so downstream layers can route it deterministically. `tests/unit/test_codex_audit_fixes.py::test_hunyuan_unsupported_response_skips_transient_retry` (line 765) / `::test_qwen_unsupported_response_skips_transient_retry` (line 794) / `::test_mesh_worker_unsupported_response_skips_transient_retry` (line 870) fence the three adapter / worker callsites

#### Scenario: Layer 2 CapabilityRouter re-raises ProviderUnsupportedResponse before the generic ProviderError branch, and Layer 3 every executor _should_retry returns False on *UnsupportedResponse

- GIVEN a `CapabilityRouter` request whose chosen route raises `ProviderUnsupportedResponse`; the four downstream executors (`generate_image`, `generate_image_edit`, `generate_structured`, `generate_mesh`) each implement an outer retry loop guarded by `_should_retry(policy, exc)`
- WHEN routing reaches one of the four router methods (`completion` / `astructured` / `image_generation` / `image_edit`) at `src/framework/providers/capability_router.py:97 / 139 / 175 / 208`, AND the executor catches the propagated exception
- THEN Layer 2 — each router method has an `except ProviderUnsupportedResponse:` branch placed BEFORE the generic `except ProviderError:` so the unsupported case re-raises directly without entering the multi-route fallback loop (which would burn another billable call against the same deterministic-bad shape); Layer 3 — every executor's `_should_retry` opens with an `isinstance(exc, *UnsupportedResponse)` check that returns False (`generate_image.py:418-425`, `generate_image_edit.py:216-220`, `generate_structured.py:159-163`, `generate_mesh.py:310-316`), so the outer retry loop also short-circuits. `tests/unit/test_codex_audit_fixes.py::test_router_does_not_fallback_on_unsupported_response` (line 926) fences Layer 2; `::test_image_executor_does_not_retry_on_unsupported_response` (line 816) fences Layer 3 — all three layers MUST hold; missing any one produces an extra billable call

### Requirement: Premium-API single-attempt contract

The system SHALL force `attempts = 1` for `capability_ref="mesh.generation"` inside `GenerateMeshExecutor` and SHALL NOT wrap `mesh_worker._apost` in `with_transient_retry_async`; on failure the CLI SHALL surface `job_id` on stderr so the user can query remote state before deciding to `--resume`.

#### Scenario: GenerateMeshExecutor forces attempts=1 for capability_ref="mesh.generation" and surfaces job_id / worker / model on stderr alongside probe_hunyuan_3d_query guidance

- GIVEN a `generate_mesh` Step whose declared `RetryPolicy.max_attempts` MAY exceed 1, but whose `capability_ref` equals `"mesh.generation"`; the upstream `MeshWorker._apost` call fails (timeout / HTML body / explicit `failed` status from `/query`) and carries a remote `job_id`
- WHEN the executor enters its retry loop at `src/framework/runtime/executors/generate_mesh.py:76-81` and computes the effective `attempts`
- THEN `attempts = max(1, policy.max_attempts)` is then forced down to `1` because `self.capability_ref == "mesh.generation"`, the executor's outer retry loop runs exactly one body iteration, and on failure the CLI's `[mesh] <step_id>` block at `src/framework/run.py:240-264` prints to stderr the `failure_mode`, `job_id`, `worker`, `model`, and the recommended remediation order — first run `FORGEUE_PROBE_HUNYUAN_3D=1 python -m probes.provider.probe_hunyuan_3d_query --job-id <id>` to check whether the server already completed the job (avoiding a re-bill), then optionally `framework.run --resume` only after the user confirms a real failure. The Scenario is scoped strictly to the runtime-side `mesh.generation` single-attempt contract (`tests/unit/test_mesh_no_silent_retry.py` L1-L3 fences + `tests/integration/test_mesh_failure_visibility.py`) and does NOT extend to ordinary LLM retry policy, which remains governed by `RetryPolicy` for non-mesh capabilities

### Requirement: Budget exceeded synthesizes a Verdict

The system SHALL detect a cost cap miss via `BudgetTracker.check()` returning `False` (`src/framework/runtime/budget_tracker.py:68-71`) inside `Orchestrator` after each Step's `record(...)` call (or after a resume cache-hit's replayed `cost_usd`). On a cap miss, `Orchestrator` (`src/framework/runtime/orchestrator.py`) SHALL terminate the Run directly through the bool-branch path — the `BudgetExceeded` exception class and `BudgetTracker.assert_within(...)` exist on the `BudgetTracker` API but are NOT used by the orchestrator main path; `Orchestrator` does NOT catch `BudgetExceeded` and does NOT call `assert_within`.

Both cap-miss paths SHALL share the following termination state: `run.metrics["termination_reason"] = "budget_exceeded(cap=<cap>, spent=<spent>)"`, `run.metrics["last_failure_mode"] = "budget_exceeded"`, `run.status = RunStatus.failed`, and a terminating `_StepOutcome(terminate=True, next_step_id=None)` so no further Step executes.

The two cap-miss paths differ on the `failure_events` axis:

- **Fresh-execution path** (`orchestrator.py:566-580`, after `budget_tracker.record(...)` for the just-completed Step): Orchestrator additionally appends `result.failure_events` with `{"step_id": step.step_id, "mode": "budget_exceeded", "decision": "human_review_required", "cap_usd": ..., "spent_usd": ...}` — the `decision` tag is a real `Decision` enum member declared in `framework.core.enums.Decision`.
- **Fresh-process resume cache-hit path** (`orchestrator.py:428-435`, when a cached Step's persisted `cost_usd` is replayed into a freshly-constructed `BudgetTracker`): Orchestrator stops short of the `failure_events.append(...)` call but still writes the four shared termination fields above.

The Run MUST NOT silently exit on either path. The Requirement title `Budget exceeded synthesizes a Verdict` is preserved as a historical name; the authoritative termination mechanism is the `budget_tracker.check() → Orchestrator direct termination` path described above, NOT a synthesised `Verdict` flowing through `TransitionEngine` (the historical phrasing referenced a `budget_exceeded` enum value that does NOT exist in `framework.core.enums.Decision`).

#### Scenario: BudgetTracker.check returns False on a cap miss; Orchestrator records termination_reason and fails the Run without silent exit

- GIVEN a Run whose `task.budget_policy.total_cost_cap_usd` is set, with a Step whose execution (or, on resume, a cached Step's replayed `cost_usd` from `hit.metrics["cost_usd"]`) calls `budget_tracker.record(step_id=..., model=..., cost_usd=...)` and pushes `BudgetTracker.spend.total_usd` above the cap
- WHEN the next `if not budget_tracker.check():` branch evaluates `True` (cap miss) — `Orchestrator` reaches the bool-branch cap-miss handler at line 566-580 (fresh-execution) or line 428-435 (resume cache-hit cost replay); `BudgetTracker.assert_within(...)` is NOT called, `BudgetExceeded` is NOT raised, and no `try/except` for `BudgetExceeded` runs in `Orchestrator`
- THEN both paths write the four shared termination fields — `run.metrics["termination_reason"] = "budget_exceeded(cap=<cap>, spent=<spent>)"`, `run.metrics["last_failure_mode"] = "budget_exceeded"`, `run.status = RunStatus.failed`, and return `_StepOutcome(terminate=True, next_step_id=None)`; the **fresh-execution path additionally** appends `result.failure_events` with `decision: "human_review_required"` (line 572-578), while the **resume cache-hit path stops short** of that append (line 428-435 contains only the four shared writes); the Run MUST NOT silently exit on either path; `tests/unit/test_budget_tracker.py::test_assert_within_raises_when_over_cap` (line 49) fences the standalone `BudgetTracker` API, and `tests/unit/test_review_budget.py` exercises the orchestrator-side cap-miss propagation

### Requirement: EventBus is loop-aware and thread-safe

The system SHALL use a `threading.Lock` around `_subs` and SHALL publish cross-thread events via `loop.call_soon_threadsafe` so a subscription registered on one event loop never blocks on another thread's emission.

#### Scenario: EventBus.publish from a worker thread hops onto the subscription's owning loop via call_soon_threadsafe without blocking the publisher

- GIVEN an `EventBus` (`src/framework/observability/event_bus.py`) whose `_subs` list is guarded by `self._lock = threading.Lock()` (line 59); a `Subscription` registered on event loop L1 (the main / orchestrator loop) and a worker thread T2 that is NOT running on L1
- WHEN T2 calls `bus.publish(...)` (or `publish_nowait`) with an event matching the subscription's filter
- THEN the publish path takes the `_lock` to snapshot matching `(queue, loop)` pairs, then for each pair hops to the subscription's owning loop via `loop.call_soon_threadsafe(queue.put_nowait, event)` (line 87-90) instead of awaiting the queue from T2 (which would either block T2 or raise because the queue belongs to L1's loop); the publisher returns without blocking on subscriber processing, and a subscribe / unsubscribe call from a third thread cannot race against the publish iteration because `_lock` serialises mutations of `_subs`. `tests/unit/test_event_bus.py::test_publish_from_worker_thread_is_safe` (line 111) and `::test_subscribe_count_is_lock_guarded` (line 154) fence the cross-thread hop and the lock-guarded subscribe-count contract; this Scenario describes in-process `asyncio` + `threading` coordination only and does NOT extend to a distributed message bus

### Requirement: WebSocket idle-disconnect is leak-free

The system SHALL run each WS handler under `asyncio.wait(FIRST_COMPLETED)` covering both the event queue and `receive_disconnect`, and SHALL release the Subscription when the client disconnects.

#### Scenario: Idle WebSocket client disconnect releases the subscription; the handler task exits cleanly with no orphaned task or queue

- GIVEN a WebSocket client connected to the framework's progress server (`src/framework/server/ws_server.py`) and receiving zero events for an extended idle window, then the client disconnects (or the connection drops)
- WHEN the per-connection handler is parked on `asyncio.wait({sub.__anext__(), receive_disconnect}, return_when=FIRST_COMPLETED)` (line 50-61) and the disconnect future completes first
- THEN the `done_set` carries the disconnect future, the handler exits its loop, the still-pending event-fetch task is cancelled, and the `Subscription` is released so the corresponding `_subs` entry is removed and its queue is freed; `tests/integration/test_ws_progress.py::test_ws_idle_disconnect_cleans_up_subscription` (line 56) fences this clean-up — confirming that an idle disconnect during a quiet period does NOT leave an orphaned handler task or an unreferenced subscription queue holding loop resources. The Scenario asserts the FIRST_COMPLETED race + subscription release mechanism rather than a specific idle-timeout duration

### Requirement: Run comparison is a read-only consumer

The system SHALL provide a `framework.comparison` module that reads two completed Run directories and produces a structured comparison report. The module MUST NOT invoke Orchestrator, Scheduler, TransitionEngine, or any executor; it MUST NOT create new Artifacts inside the Run under comparison.

#### Scenario: Comparing two completed Runs does not mutate their state

- GIVEN two Run directories `<root>/<date>/<run_a>/` and `<root>/<date>/<run_b>/`, each with a valid `run_summary.json` + `_artifacts.json`
- WHEN the user invokes `python -m framework.comparison --baseline-run <run_a> --candidate-run <run_b>`
- THEN a `comparison_report.json` + `comparison_summary.md` are written to `--output-dir` and neither source Run directory is modified (no new artifact files, no timestamp changes on existing artifact files)

### Requirement: Comparison refuses to run on incomplete Runs

The system SHALL require both Run directories to contain a `run_summary.json` whose `status` field has been finalized (e.g. `succeeded` / `failed` / `cancelled`). If either is missing the status field, the loader SHALL raise `RunSnapshotCorrupt` and the CLI SHALL exit with code 2.

#### Scenario: Run with missing status field is rejected

- GIVEN the baseline `run_summary.json` is a valid JSON object that lacks the `status` field
- WHEN the user invokes `python -m framework.comparison --baseline-run <run_a> --candidate-run <run_b>`
- THEN the loader raises `RunSnapshotCorrupt`, the CLI prints `[ERR] RunSnapshotCorrupt: ...` to stderr, and exits with code 2

### Requirement: Comparison reuses the existing hashing module

The system SHALL call `framework.artifact_store.hashing` to recompute payload byte hashes; the comparison module MUST NOT reimplement its own hashing.

#### Scenario: Loader recomputes payload hash via hash_payload

- GIVEN an Artifact whose `_artifacts.json` entry records `hash=H` and whose payload file is present on disk
- WHEN `load_run_snapshot(..., include_payload_hash_check=True)` runs
- THEN it calls `framework.artifact_store.hashing.hash_payload(path.read_bytes())` and compares the result to `H`; the comparison module ships no alternate hashing implementation, and on mismatch surfaces `ArtifactDiff.kind="content_changed"` with a tampered-payload note rather than re-deriving any hash

### Requirement: Cost comparison reads from `cp.metrics["cost_usd"]`

The system SHALL compare per-step and per-run cost by reading the already-persisted `cp.metrics["cost_usd"]` field, which is guaranteed by the main runtime-core Requirement "Cost is persisted before Checkpoint"; the comparison module MUST NOT attempt to re-estimate cost via BudgetTracker.

#### Scenario: Run-level cost diff reads cp.metrics verbatim

- GIVEN baseline checkpoints carry `metrics["cost_usd"] = 0.10` (summed across the run) and candidate checkpoints carry `0.12`
- WHEN `diff_engine.compare(...)` computes the run-level metric diff
- THEN the resulting `MetricDiff(metric="cost_usd", scope="run")` has `baseline_value=0.10`, `candidate_value=0.12`, `delta=0.02`, `delta_pct=20.0`; no `BudgetTracker` re-estimation is invoked, and no provider call is issued

### Requirement: CLI exit codes carve out comparison-specific meanings

The system SHALL use the following exit code convention for `python -m framework.comparison`:

- `0` — comparison completed, regardless of how many diffs were found
- `2` — Run directory could not be located, or `run_summary.json` / `_artifacts.json` schema is corrupt
- `3` — strict mode is enabled and at least one artifact payload is missing on disk

Exit code `0` MUST NOT be redefined as "non-zero when any diff exists"; CI callers are responsible for consuming `summary_counts` from the JSON report to decide gating.

#### Scenario: Diff-bearing comparison still exits 0

- GIVEN baseline and candidate Run dirs differ in `artifact:content_changed` / `artifact:metadata_only` / run-level `cost_usd` MetricDiff
- WHEN the user runs `python -m framework.comparison --baseline-run <a> --candidate-run <b> --output-dir <out>`
- THEN the CLI writes `comparison_report.json` + `comparison_summary.md` under `<out>` and exits with code 0; the existence of diffs MUST NOT promote the exit code to non-zero. CI gating is the caller's responsibility via consuming `summary_counts` from the JSON report

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
