# Plan: runtime-core — Task 6 Scenarios needing addition

> 从 cleanup-main-spec-scenarios skeleton 移出(2026-04-25);保留为 Task 6 实装清单。Task 6 启动时把以下 Plan 转为正式 `openspec/changes/cleanup-main-spec-scenarios/specs/runtime-core/spec.md` 的 `## MODIFIED Requirements` 块。**不**新增 Requirement,**不**改 Requirement 标题。

## Plan: Requirements needing Scenario

### `load_run_metadata` performs three-stage filtering
- 标记:[+1]
- 现状:主 spec line 53;FR-LC-006 三阶段过滤(run_id / artifact_id / hash)
- Scenario 草案:
  - "Filter rejects entry whose `producer.run_id` does not match the target run"
  - "Filter accepts well-formed entry and counts cache hits"
- 真源:`src/framework/artifact_store/repository.py::load_run_metadata`、`tests/unit/test_codex_audit_fixes.py`(FR-LC-006/007 fence)

### TransitionEngine is isolated per `arun`
- 标记:[Min 1]
- 现状:主 spec line 57;ADR-006(`cloned_for_run`)
- Scenario 草案:"Two concurrent `arun` invocations do not share `RetryPolicy._current_attempt` state"
- 真源:`src/framework/runtime/transition_engine.py::cloned_for_run`、`tests/unit/test_codex_audit_fixes.py`(ADR-006 3 fence)

### Unsupported-response short-circuit at three layers
- 标记:[+1]
- 现状:主 spec line 71;三层拦截(transient retry / router fallback / executor `_should_retry`)
- Scenario 草案:
  - "Layer 1 (`with_transient_retry_async`) skips `unsupported_response` and does not retry"
  - "Layer 3 (executor `_should_retry`) raises after a single attempt instead of looping"
- 真源:`src/framework/providers/_transient_retry.py`、`src/framework/runtime/executors/base.py`、`tests/unit/test_codex_audit_fixes.py`(FR-RUNTIME-008/009 fence)

### Premium-API single-attempt contract
- 标记:[Min 1]
- 现状:主 spec line 75;ADR-007(贵族 API 不静默重试)
- Scenario 草案:"`mesh.generation` failure raises `MeshWorkerError` with `job_id`/`worker`/`model`; framework does NOT retry, and `framework.run` stderr instructs user to query server before `--resume`"
- 真源:`src/framework/runtime/{executors/generate_mesh,failure_mode_map}.py`、`src/framework/run.py`、`tests/unit/test_mesh_no_silent_retry.py`、`tests/integration/test_mesh_failure_visibility.py`

### Budget exceeded synthesizes a Verdict
- 标记:[Min 1]
- 现状:主 spec line 79
- Scenario 草案:"`BudgetTracker.check()` over `cost_cap` synthesizes a `Verdict(decision='abort')` consumed by `TransitionEngine` to terminate the run"
- 真源:`src/framework/runtime/budget_tracker.py`、`tests/unit/test_review_budget.py`

### EventBus is loop-aware and thread-safe
- 标记:[Min 1]
- 现状:主 spec line 83;LLD §16.5
- Scenario 草案:"`EventBus.publish_nowait` from a non-event-loop thread schedules the publish onto the bus's loop via `loop.call_soon_threadsafe`"
- 真源:`src/framework/observability/event_bus.py::publish_nowait`、`tests/unit/test_event_bus.py`

### WebSocket idle-disconnect is leak-free
- 标记:[Min 1]
- 现状:主 spec line 87
- Scenario 草案:"Idle WebSocket client times out and disconnects within the configured idle window; the server-side handler task exits cleanly with no orphaned task or queue"
- 真源:`src/framework/server/ws_server.py`、`tests/integration/test_ws_progress.py`
