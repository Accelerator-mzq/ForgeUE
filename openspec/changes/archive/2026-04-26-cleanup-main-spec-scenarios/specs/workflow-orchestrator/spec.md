# Delta Spec: workflow-orchestrator (cleanup-main-spec-scenarios)

> 给 `openspec/specs/workflow-orchestrator/spec.md` 的 5 个已有 Requirement 补 `#### Scenario:` 块(共 5 个 Scenario,各 1 个)。**不**新增 Requirement,**不**改 Requirement 标题。其中 `Eleven step types are supported` 一条按方案 A 收紧描述以对齐真实代码(主 spec 描述列出了 `StepType` 中不存在的 `inspect` / `plan` / `execute` / `custom`,并未列出实际存在的 `merge` / `retry` / `branch` / `human_gate`),其余 4 条复用主 spec 描述。`Risk-ordered scheduling` 与 `Revise loop with cap` 已有 Scenario,不在本 delta 范围。

## MODIFIED Requirements

### Requirement: Three RunModes share one scheduler

The system SHALL implement a single Scheduler that serves `basic_llm`, `production`, and `standalone_review` RunModes without forking the scheduling codepath.

#### Scenario: All three RunMode values share the same Scheduler class without per-mode subclasses or codepath branches

- GIVEN `framework.core.enums.RunMode(str, Enum)` declaring exactly three members — `basic_llm`, `production`, `standalone_review` (`src/framework/core/enums.py:7-10`); the `Scheduler` class lives in `src/framework/runtime/scheduler.py:24-71` as a single class with `prepare` / `default_next` / `risk_sort` / `runnable_after` and does NOT import `RunMode`
- WHEN integration tests exercise each RunMode separately — `tests/integration/test_p0_mock_linear.py` (`basic_llm`), `tests/integration/test_p2_standalone_review.py` (`standalone_review`), `tests/integration/test_p3_production_pipeline.py` (`production`)
- THEN the same `Scheduler` instance handles all three RunModes through identical `prepare(workflow, steps)` / `runnable_after(completed, steps)` calls; there is no `Scheduler` subclass per RunMode, no `if run_mode == ...` branching inside the scheduling codepath, and the `Orchestrator` does not fork its dispatch loop on RunMode either — RunMode is a Task-level metadata field consumed by callers / observability, not by the scheduler

### Requirement: Eleven step types are supported

The system SHALL constrain `Step.type` to the closed `StepType` enum declared in `src/framework/core/enums.py`. As of 2026-04-26 the enum's actual members are: `generate`, `transform`, `review`, `select`, `merge`, `validate`, `export`, `import_` (`"import"`), `retry`, `branch`, `human_gate` (11 members). Step dispatch is keyed by `(step_type, capability_ref)` through `framework.runtime.executors.base.ExecutorRegistry`; not every `StepType` has a default executor registered out of the box — the default `framework.run._build_orchestrator` registers executors covering `generate` / `validate` / `review` / `select` / `export` plus the mock variants. Other `StepType` values are reserved enum members that callers MAY register custom executors for via `ExecutorRegistry.register(...)`. Resolving a `Step` whose `(step_type, capability_ref)` has no registered match raises a clear `KeyError(f"No executor for step_type=... capability_ref=...")` at `ExecutorRegistry.resolve` time. The Requirement title `Eleven step types are supported` is preserved as a historical name; the authoritative member list is `StepType` itself.

#### Scenario: StepType is constrained to the closed enum declared in framework.core.enums; Orchestrator dispatches via ExecutorRegistry keyed by (step_type, capability_ref)

- GIVEN `framework.core.enums.StepType(str, Enum)` declaring its current closed member set (`generate`, `transform`, `review`, `select`, `merge`, `validate`, `export`, `import_` exposed as `"import"`, `retry`, `branch`, `human_gate`); a default `Orchestrator` constructed via `framework.run._build_orchestrator` that registers executors for the `generate` / `validate` / `review` / `select` / `export` axes plus mock variants through `register_mock_executors(execs)`
- WHEN `Step.model_validate(...)` parses a Step (Pydantic enforces the `StepType` enum at construction time) and `Orchestrator` dispatches it via `framework.runtime.executors.base.ExecutorRegistry.resolve(step)` (`src/framework/runtime/executors/base.py:54-67`) using the `(step.type, step.capability_ref)` key
- THEN any string outside the `StepType` member set is rejected at Pydantic validation; for an in-enum `Step`, the registry returns the matching executor when one was registered for that `(step_type, capability_ref)` pair (or for the `(step_type, None)` wildcard fallback), and raises `KeyError(f"No executor for step_type={step.type} capability_ref={step.capability_ref}")` when neither key matches — so reserved StepTypes such as `merge` / `retry` / `branch` / `human_gate` either get a custom executor via `ExecutorRegistry.register(...)` from the calling layer or surface a deterministic resolve-time error rather than silently no-op

### Requirement: Opt-in DAG concurrency

The system SHALL execute ready Steps concurrently when and only when `task.constraints["parallel_dag"] == True` or `workflow.metadata["parallel_dag"] == True`.

#### Scenario: parallel_dag opt-in flag activates concurrent fan-out via either task.constraints or workflow.metadata; without the flag execution stays sequential

- GIVEN a Workflow whose dependency graph has multiple ready siblings (e.g. a fan-out fixture in `tests/integration/test_dag_concurrency.py`); the `parallel_dag` opt-in flag MAY be declared on `task.constraints["parallel_dag"]` OR `workflow.metadata["parallel_dag"]`
- WHEN `Orchestrator.arun` evaluates `dag_mode = bool((task.constraints or {}).get("parallel_dag") or (getattr(workflow, "metadata", None) or {}).get("parallel_dag"))` (`src/framework/runtime/orchestrator.py:157-162`) — a short-circuit OR where either truthy source activates the flag
- THEN, when the flag is set on either source, the orchestrator fans out simultaneously-ready siblings concurrently (`tests/integration/test_dag_concurrency.py::test_dag_fans_out_leaves_concurrently` line 110 covers the `task.constraints` path; `::test_workflow_metadata_parallel_dag_activates_fanout` line 124 covers the `workflow.metadata` path); when neither source is truthy, the orchestrator stays in sequential mode and `::test_linear_mode_still_sequential` (line 177) confirms the no-flag default — `parallel_dag` is strictly opt-in, the flag never auto-enables based on workflow shape

### Requirement: Bundle loading goes through the loader

The system SHALL require callers to use `framework.workflows.loader.load_task_bundle`; direct `json.load(open(...))` is forbidden because it breaks on Windows gbk stdin with UTF-8 full-width quotes.

#### Scenario: framework.workflows.loader.load_task_bundle is the single supported bundle entry point; framework.run and integration tests load via this helper rather than calling json.load directly

- GIVEN `framework.workflows.loader.load_task_bundle(path)` (`src/framework/workflows/loader.py:31-37`) declaring the canonical bundle entry path with explicit `Path(path).read_text(encoding="utf-8")` followed by `json.loads(...)` and Pydantic validation; CLAUDE.md §"Bundle JSON 编码" articulates the gbk-vs-UTF-8 rationale
- WHEN framework code loads a bundle — the CLI `framework.run.main` at `src/framework/run.py:140` calls `load_task_bundle(args.task)`, integration tests under `tests/integration/test_p[0-4]_*.py` use `from framework.workflows import load_task_bundle`, and the parametrized fence `tests/integration/test_example_bundles_smoke.py::test_bundle_loads` (line 81) loads every bundle under `examples/` through the same helper
- THEN bundle ingest inside framework / CLI / integration tests goes through `load_task_bundle` rather than ad-hoc `json.load(open(...))` calls; this Scenario asserts the orchestrator-side single entry point and the project's documented expectation, and does NOT impose a global ban on user-authored scripts that may legitimately call `json.load` for their own purposes

### Requirement: Model reference expansion happens before validation

The system SHALL expand `provider_policy.models_ref` into `prepared_routes` before Pydantic validation; bundles that skip the loader and pass raw dicts will fail downstream `ProviderPolicy has no preferred or fallback models` errors.

#### Scenario: expand_model_refs runs against the registry before any Pydantic Step / Task / Workflow validation, so alias misses fail at expansion time and bundles never reach the runtime carrying a bare models_ref string

- GIVEN a bundle declaring `provider_policy.models_ref: "<alias>"` on one or more Steps; `framework.providers.model_registry.expand_model_refs(raw, registry)` walks the parsed dict in-place; `framework.workflows.loader.load_task_bundle` orders its operations strictly as: `Path.read_text(encoding="utf-8")` → `json.loads(...)` → `expand_model_refs(raw, get_model_registry())` → `Task.model_validate(raw["task"])` / `Workflow.model_validate(raw["workflow"])` / `Step.model_validate(s)` (`src/framework/workflows/loader.py:32-37`)
- WHEN the loader is invoked against a bundle whose alias is registered (e.g. `text_cheap`) versus a bundle whose alias is NOT registered (e.g. `nonexistent_alias`)
- THEN the registered-alias path replaces every `models_ref` key in-place with concrete `prepared_routes` BEFORE any Pydantic validation runs, so the runtime receives Steps whose `provider_policy` is fully expanded and never carries a bare `models_ref` string; the unregistered-alias path raises `UnknownModelAlias` (a `KeyError` subclass) inside `expand_model_refs` at expansion time, fenced by `tests/unit/test_model_registry.py::test_expand_unknown_ref_raises` — the failure surfaces with a clear "alias not found" message before the dict reaches `Task.model_validate`, so the misleading `ProviderPolicy has no preferred or fallback models` Pydantic error never has a chance to fire on the alias-miss path
