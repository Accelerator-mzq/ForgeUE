# Delta Spec: runtime-core (add-run-comparison-baseline-regression)

> 本文件只描述本 change 对 `openspec/specs/runtime-core/spec.md` 的**增量**行为。完整契约以主 spec 为准,本文件**不**复制主 spec 的 Requirement / Invariant / Validation / Non-Goals。

---

## ADDED Requirements

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

## ADDED Invariants

- The `comparison` module lives at `src/framework/comparison/` as a sibling of `observability/` and `pricing_probe/`. It is NOT placed inside `runtime/` or `observability/`, because it is a read-only consumer outside the Run lifecycle.
- The module introduces NO new FailureMode enum values; its exceptions (`RunDirNotFound`, `RunDirAmbiguous`, `RunSnapshotCorrupt`) are local to the CLI and do not feed into `FailureModeMap`.
- The module introduces NO new Step type and NO new Verdict decision value.

## MODIFIED Requirements

None. This change only adds a new module; it does not modify existing runtime-core Requirements.

## REMOVED Requirements

None.

## Non-Goals for this delta

- Does not introduce real-time Run comparison (both Runs must be already finalized).
- Does not re-run judges, workers, or providers.
- Does not merge two Runs into one (no "best-of" selection logic).
- Does not change Checkpoint or Artifact schema; only reads them.
- Does not add a new subcommand to `python -m framework.run`; comparison is its own CLI entry (`python -m framework.comparison`).

## Validation for this delta

- Implementation-phase unit tests covering models / loader / diff engine / reporter / CLI, co-located under `tests/unit/test_run_comparison_*.py`.
- At least one integration test under `tests/integration/test_run_comparison_cli.py` exercising the full CLI path against fixture Run directories.
- Test count is NOT hardcoded; the authoritative number is `python -m pytest -q` after implementation lands.
- Cross-reference to main spec: `openspec/specs/runtime-core/spec.md` Requirements "Checkpoint persistence survives cross-process resume" and "Cost is persisted before Checkpoint" — this delta treats those as pre-conditions for comparison, not as behaviors to re-verify here.
