# probe-and-validation

## Purpose

Probe-and-validation is the supporting layer that keeps ForgeUE's test pyramid honest. `tests/` is the automated fence, `probes/` is the opt-in diagnostic entry point for paid / external providers, and the repository's validation posture is stratified into Level 0 (offline, no key), Level 1 (LLM key), and Level 2 (ComfyUI / UE / premium APIs). The rules in this spec exist so every Codex / adversarial review fix has a named fence and so ad-hoc scripts do not double-bill users or crash Windows stdout.

## Source Documents

- `probes/README.md` (authoring conventions + §5 output helper)
- `CLAUDE.md` §"Probe 脚本约定", §"测试纪律", §"手工验收"
- `AGENTS.md` (mirrors CLAUDE.md with Codex-agent wording)
- `docs/requirements/SRS.md` §4.6 (NFR-MAINT-001~005 testing discipline)
- `docs/testing/test_spec.md` §2 test pyramid + levels
- `CHANGELOG.md` [Unreleased] TBD-007 (premium-API opt-in policy) and TBD-008 (contract vs quality layering)
- Source: `probes/_output.py::probe_output_dir(tier, name)`
- Source: `probes/smoke/probe_{framework,aliases,chat,models}.py`, `probes/provider/probe_*.py`
- Source: `tests/conftest.py` (pinned test ModelRegistry, repo-root sys.path, `stub_hydrate_env` fixture)
- Source: `tests/unit/test_probe_framework.py` (probe-level fences)

## Current Behavior

Ad-hoc diagnostic scripts live under `probes/` (never in the repo root, never in `tests/`) and split into two tiers: `probes/smoke/` runs without any provider key, while `probes/provider/` talks to real external APIs. Every paid call is opt-in via an environment flag (e.g. `FORGEUE_PROBE_VISUAL_REVIEW=1`, `FORGEUE_PROBE_HUNYUAN_3D=1`); the flag check accepts only `1`, not `false` or `0`. Probe output is routed through `probes._output.probe_output_dir(tier, name)`, which lands under `./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/`. Scripts emit ASCII markers (`[OK]` / `[FAIL]` / `[SKIP]`) because Windows GBK stdout crashes on emoji. Exit code is 0 for all-pass (including skips) and 1 for real failures.

Probe modules must be side-effect-free at import time: `hydrate_env()`, `os.environ[...]` writes, and `OUT.mkdir()` calls are all deferred to `main()` or a `_get_*()` helper. The fence `tests/unit/test_probe_framework.py` guards this invariant alongside opt-in handling, lazy initialisation, and format detection.

The test corpus is organised as `tests/unit/*` for per-module behaviour and `tests/integration/*` for end-to-end scenarios. Every Codex / adversarial review fix adds a named regression fence — the pattern is documented in `CLAUDE.md` and backed by concrete exemplars (`test_cascade_cancel.py`, `test_review_budget.py`, `test_download_async.py`, `test_event_bus.py`, `test_codex_audit_fixes.py`). Validation is stratified into three levels; the runnable commands live in `docs/ai_workflow/validation_matrix.md`.

## Requirements

### Requirement: Probe directory layout

The system SHALL place ad-hoc diagnostic scripts under `probes/smoke/` (no provider key required) or `probes/provider/` (paid / external API); scripts MUST NOT live in the repo root or under `tests/`.

### Requirement: Probe naming

The system SHALL name probes `probe_<domain>.py` or `probe_<provider>_<aspect>.py` and invoke them via the dotted path `python -m probes.<tier>.<probe_name>`.

### Requirement: Opt-in gate on paid calls

The system SHALL require an environment flag of the form `FORGEUE_PROBE_*=1` for any probe that performs a paid call; the handler MUST accept only `"1"` and MUST reject `"0"` / `"false"` / `"FALSE"` as inactive.

#### Scenario: Mesh probe run without flag skips cleanly

- GIVEN `FORGEUE_PROBE_HUNYUAN_3D` is unset
- WHEN `python -m probes.provider.probe_hunyuan_3d_submit` is executed
- THEN the probe prints `[SKIP]` with an explanation and exits 0

### Requirement: Module-level side-effect ban

The system SHALL keep probe modules free of top-level side effects: no `hydrate_env()` call, no `os.environ[...]` mutation, no `mkdir()`; such actions MUST be deferred into `main()` or a `_get_*()` helper.

### Requirement: ASCII output markers

The system SHALL restrict probe stdout to ASCII markers `[OK]` / `[FAIL]` / `[SKIP]` (and plain ASCII prose); emoji and non-ASCII glyphs MUST NOT be emitted on stdout because Windows GBK stdout will crash on them.

### Requirement: Probe exit code convention

The system SHALL exit 0 when every probe assertion passes or is skipped, and 1 when any probe assertion really fails.

### Requirement: Probe output path convention

The system SHALL route probe output through `probes._output.probe_output_dir(tier, name)`, which produces `./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/`.

### Requirement: Regression fence per review fix

The system SHALL add a named regression fence (unit or integration test) for every Codex / adversarial review fix; the pattern is enforced by `CLAUDE.md` / `AGENTS.md` and witnessed by `test_codex_audit_fixes.py` and peer fence files.

### Requirement: Critical-boundary objects are real, not mocked

The system SHALL exercise download, EventBus, DAG scheduling, BudgetTracker, and bundle-level Artifact flow through real objects in tests; mocks MUST NOT replace those boundaries (NFR-MAINT-004 / 005).

### Requirement: Validation stratification into three levels

The system SHALL maintain a three-level validation matrix in `docs/ai_workflow/validation_matrix.md`: Level 0 runs offline (no key), Level 1 needs LLM keys, Level 2 needs ComfyUI / UE / premium external services.

### Requirement: Test totals are never hardcoded

The system SHALL NOT hardcode the aggregate test-count in specs or in `validation_matrix.md`; the source of truth is the actual output of `python -m pytest -q`.

## Invariants

- `probes/__init__.py` and `probes/smoke/__init__.py` / `probes/provider/__init__.py` exist only to mark packages; they carry no logic.
- `tests/conftest.py` provides a pinned test `ModelRegistry`, a repo-root `sys.path` injection, and `stub_hydrate_env`; tests do not hit `config/models.yaml` on disk unless a specific test chooses to.
- Offline contract tests under `tests/` never depend on a real provider; real-provider exercise belongs in `probes/provider/` and is opt-in.
- Total test count shifts every time a fence is added; do not encode a number anywhere except in `docs/` long-form narrative or commit messages.

## Validation

- Unit: `tests/unit/test_probe_framework.py` (side-effect ban, opt-in handling, format detection, output-path helper)
- Source invariant: `probes/README.md` §5 describes the output-path helper and asserts the ASCII-only rule; treat as authoritative for probe authors.
- Offline fence run: `python -m pytest -q` (Level 0)
- Smoke probe: `python -m probes.smoke.probe_framework`
- Test totals: see `python -m pytest -q` actual output (do not hardcode).

## Non-Goals

- Linux CI runner (SRS TBD-T-001; no pipeline is maintained in this repo today).
- Probe coverage statistics (probes are deliberately outside coverage reporting).
- Cross-OS stdout universality (GBK constraint is Windows-specific; macOS / Linux users simply benefit from the same ASCII convention).
