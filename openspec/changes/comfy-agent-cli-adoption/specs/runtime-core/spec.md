## ADDED Requirements

### Requirement: StepContext exposes run_dir for in-tree artifact placement

The system SHALL extend `StepContext` (`src/framework/runtime/executors/base.py:16-24`) with a new field `run_dir: Path` that resolves to the absolute path `<artifact_root>/<date_bucket>/<run_id>/`. The Orchestrator SHALL inject this field when constructing `StepContext` for each Step execution, so executors and workers that need to place files inside the project artifact tree (e.g. `ComfyAgentWorker` copying ComfyUI outputs from `D:/AI/ComfyUI/outputs/...` to `<run_dir>/comfy/`) have a single canonical source for the run-scoped artifact directory. The field SHALL satisfy the existing `<run_dir>/_artifacts.json` convention (`runtime-core/spec.md:37`) — i.e. `run_dir == ArtifactRepository`'s working directory for that run. The field SHALL be REQUIRED (not Optional) and SHALL be a `Path` instance pointing to a directory that exists at executor invocation time.

#### Scenario: StepContext.run_dir is injected by Orchestrator and resolves to artifact_root/<date>/<run_id>/

- **GIVEN** an `Orchestrator` constructed with `artifact_root=Path("artifacts")` and a `Run` whose `run_id="run_abc"`, started at 2026-05-02
- **WHEN** the Orchestrator constructs `StepContext(run=run, task=task, step=step, repository=repo, run_dir=...)` for each Step
- **THEN** `ctx.run_dir == Path("artifacts/2026-05-02/run_abc")` (existing artifact-root + date bucket + run_id convention from `framework.run --artifact-root` flag); `ctx.run_dir.is_dir()` is True (Orchestrator ensures the directory exists before invoking the first Step); workers that need to place outputs in-tree (e.g. ComfyAgentWorker) read this field directly via `ctx.run_dir`

#### Scenario: Workers requiring artifact-tree placement use ctx.run_dir as the canonical source

- **GIVEN** a `ComfyAgentWorker` (or any future worker that needs to copy externally-produced files into the project tree per the `artifact-contract` "External worker outputs are copied into the project artifact tree" Requirement)
- **WHEN** the executor constructs the worker
- **THEN** the executor passes `artifacts_dir=ctx.run_dir` (the new field) — NOT `ctx.run.artifact_dir` (which does NOT exist on the `Run` model per `src/framework/core/task.py:83-95`); the worker uses `artifacts_dir / "<worker_subdir>" /` as its copy target; if `ctx.run_dir` is somehow `None` or missing, the worker raises `WorkerUnsupportedResponse` immediately at construction (defense-in-depth — the Orchestrator-side injection invariant must hold)
