# workflow-orchestrator

## Purpose

Workflow-orchestrator is the graph layer: it translates a declarative TaskBundle JSON into a Workflow of typed Steps, enforces risk-ordered scheduling, routes Verdicts back into `revise` loops, and lets the same scheduler handle all three RunModes without forking codepaths.

## Source Documents

- `docs/requirements/SRS.md` §3.1 (FR-WF-001~007), §4.1 (NFR-PERF-001, DAG fan-out wall-clock), §6.1 (C-003 bundle JSON encoding)
- `docs/design/HLD.md` §2 layered view, §5 collaboration (single scheduler for all three RunModes)
- `CHANGELOG.md` [Unreleased] context on bundle format and parametrized live bundles
- Source: `src/framework/core/task.py`, `runtime.py`, `enums.py` (Task, Workflow, Step, StepType, RunMode)
- Source: `src/framework/workflows/loader.py` (`load_task_bundle`, `expand_model_refs`)
- Source: `src/framework/runtime/executors/` (eleven step executors)
- Source: `src/framework/runtime/scheduler.py` (risk ordering, DAG ready-set)
- Source: `examples/*.json` (ten bundle files, one per scenario)

## Current Behavior

A Workflow is a directed graph of Steps. Each Step has one of eleven `StepType` values (`generate` / `transform` / `validate` / `review` / `select` / `export` / `import` / `inspect` / `plan` / `execute` / `custom`) and a `risk_level` (`low` / `medium` / `high`). The Scheduler releases ready steps in risk-ascending order; DAG concurrency is opt-in via `task.constraints["parallel_dag"] = True` or `workflow.metadata["parallel_dag"] = True`. Three RunModes (`basic_llm` / `production` / `standalone_review`) share the same Scheduler — no mode-specific branches. `depends_on` encodes the DAG edges; a `revise` Verdict injects `inputs["revision_hint"]` into the next Step and increments the revise counter, which is capped by `max_revise`.

Bundle JSON is UTF-8 and must be loaded through `framework.workflows.loader.load_task_bundle` (Windows stdin is gbk by default, so direct `json.load(open(...))` will raise `UnicodeDecodeError` on bundles containing full-width quotes). The loader also expands `provider_policy.models_ref: "<alias>"` into `prepared_routes` before Pydantic validation.

## Requirements

### Requirement: Three RunModes share one scheduler

The system SHALL implement a single Scheduler that serves `basic_llm`, `production`, and `standalone_review` RunModes without forking the scheduling codepath.

### Requirement: Eleven step types are supported

The system SHALL recognize exactly these StepType values: `generate`, `transform`, `validate`, `review`, `select`, `export`, `import`, `inspect`, `plan`, `execute`, `custom`.

### Requirement: Risk-ordered scheduling

The system SHALL order ready steps by `risk_level` ascending (`low` < `medium` < `high`).

#### Scenario: Two ready steps of different risk

- GIVEN two Steps whose dependencies are satisfied simultaneously
- WHEN the Scheduler picks the next to execute
- THEN the `low`-risk Step runs before the `medium`-risk Step

### Requirement: Opt-in DAG concurrency

The system SHALL execute ready Steps concurrently when and only when `task.constraints["parallel_dag"] == True` or `workflow.metadata["parallel_dag"] == True`.

### Requirement: Revise loop with cap

The system SHALL inject the Verdict's `revision_hint` into the downstream Step's `inputs["revision_hint"]` and SHALL convert a `revise` into `Decision.reject` once `revise_count >= max_revise`.

#### Scenario: Revise count exceeds cap

- GIVEN a Workflow with `max_revise=2` and two consecutive `revise` Verdicts
- WHEN a third `revise` Verdict arrives
- THEN TransitionEngine converts it to `reject` and the Run terminates

### Requirement: Bundle loading goes through the loader

The system SHALL require callers to use `framework.workflows.loader.load_task_bundle`; direct `json.load(open(...))` is forbidden because it breaks on Windows gbk stdin with UTF-8 full-width quotes.

### Requirement: Model reference expansion happens before validation

The system SHALL expand `provider_policy.models_ref` into `prepared_routes` before Pydantic validation; bundles that skip the loader and pass raw dicts will fail downstream `ProviderPolicy has no preferred or fallback models` errors.

## Invariants

- Bundle Artifact flow is end-to-end real objects — no mocking across Step boundaries (NFR-MAINT-005).
- DAG fan-out wall-clock is expected to scale near-linearly (NFR-PERF-001); a 3-step fan-out at 0.2s/step should complete within ~0.25s.
- `depends_on` is the single source of graph edges; the executor layer never reorders based on its own heuristics.
- Workflow `template_ref` is reserved but not yet used.

## Validation

- Unit: `tests/unit/test_scheduler_risk_ordering.py`, `test_core_schemas.py`, `test_transition_engine.py`
- Integration: `tests/integration/test_p0_mock_linear.py`, `test_p1_structured_extraction.py`, `test_p2_standalone_review.py`, `test_p3_production_pipeline.py`, `test_dag_concurrency.py`, `test_example_bundles_smoke.py`
- Offline smoke: `python -m framework.run --task examples/mock_linear.json --run-id demo --artifact-root ./artifacts`
- Bundle parsing fence: `test_example_bundles_smoke.py` loads every JSON under `examples/` through `load_task_bundle`.
- Test totals: see `python -m pytest -q` actual output.

## Non-Goals

- Workflow template inheritance (`template_ref` reserved, TBD).
- Chat-style agent framework integration (SRS §2.5).
- Auto-generated bundles (hand-authored first).
