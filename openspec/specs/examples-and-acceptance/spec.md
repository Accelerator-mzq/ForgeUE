# examples-and-acceptance

## Purpose

Examples-and-acceptance treats each bundle under `examples/` as an end-to-end acceptance artifact: a TaskBundle JSON is simultaneously a user-facing how-to, a loader contract test, an integration-test fixture, and a live-run entry point. This spec pins the bundle contract, the P0-P4 / L-layer mapping, and the offline-versus-live split so a future change never breaks the "one bundle, one acceptance path" promise.

## Source Documents

- `docs/requirements/SRS.md` §5.5 (configuration interface: `examples/*.json` row)
- `docs/acceptance/acceptance_report.md` §3 (P0-P4 / L1-L4 / F1-F5 / Plan C status), §6.1 (A1 UE 5.7.4 hardware smoke), §6.2 (bundle evidence taxonomy updated under TBD-008)
- `README.md` §"Bundle 与 Example" (original five bundles; see doc-drift note below)
- `CHANGELOG.md` [Unreleased] (parametrized live bundles, A1 / a2_mesh live bundle expansion)
- Source: `examples/mock_linear.json`, `character_extract.json`, `review_3_images.json`, `image_pipeline.json`, `image_edit_pipeline.json`, `image_to_3d_pipeline.json`, `image_to_3d_pipeline_live.json`, `ue_export_pipeline.json`, `ue_export_pipeline_live.json`, `ue5_api_query.json`
- Source: `src/framework/workflows/loader.py::load_task_bundle`
- Source: `src/framework/workflows/loader.py::expand_model_refs`
- Source: `tests/integration/test_p{0,1,2,3,4}_*.py`, `test_l4_image_to_3d.py`, `test_image_edit.py`, `test_dag_concurrency.py`, `test_example_bundles_smoke.py`, `test_ws_progress.py`

## Current Behavior

A bundle is a JSON document containing three sections: a `Task` (with `task_type`, `run_mode`, `ue_target`, `review_policy`, bundled Policies), a `Workflow` (control-semantic Step graph with metadata), and a `Steps` array. The loader is `load_task_bundle`, which reads UTF-8 (avoiding Windows stdin gbk), expands `provider_policy.models_ref` into `prepared_routes` via `expand_model_refs(raw, get_model_registry())`, and then runs Pydantic validation. Callers that bypass the loader will hit `generate_structured failed: ProviderPolicy has no preferred or fallback models`.

Ten bundles currently ship under `examples/`, each tied to one acceptance scenario:

- `mock_linear.json` — P0, pure-mock linear three-step (offline, no API key)
- `character_extract.json` — P1, LLM structured extraction into `UECharacter` (requires `--live-llm`)
- `review_3_images.json` — P2, standalone review with three inline candidates
- `image_pipeline.json` — P3, production pipeline with ComfyUI generation + inline review + export
- `image_edit_pipeline.json` — L5-A, prompt + source image → edited image via `image_edit` alias
- `image_to_3d_pipeline.json` — L4, image → 3D mesh contract bundle
- `image_to_3d_pipeline_live.json` — L4, live-provider variant (Hunyuan 3D opt-in)
- `ue_export_pipeline.json` — P4, UE manifest-only export via FakeComfy placeholder
- `ue_export_pipeline_live.json` — A1, live-provider variant used for the 2026-04-23 UE 5.7.4 commandlet hardware smoke
- `ue5_api_query.json` — L1, UE5 Python API question answering via `ue5_api_assist` alias

Each bundle is covered by at least one integration test; `test_example_bundles_smoke.py` is the loader-contract fence that ensures every JSON under `examples/` can still be parsed after any change.
## Requirements
### Requirement: Bundle is the end-to-end acceptance artifact

The system SHALL treat every JSON file under `examples/` as simultaneously a how-to, a loader contract test, and (for P0-P4 / L-layer files) an integration-test fixture.

#### Scenario: examples/mock_linear.json runs the P0 acceptance pipeline end-to-end

- GIVEN `examples/mock_linear.json` declaring three mock steps (`generate-mock` → `validate` → `export-noop`) and `tests/integration/test_p0_mock_linear.py::test_first_run_produces_3_artifacts_and_3_checkpoints` referencing it as `bundle_path`
- WHEN the test loads the bundle via `load_task_bundle` and runs it through the offline `Orchestrator` with mock executors
- THEN the run reaches `RunStatus.succeeded`, visits all three step ids in declaration order, persists three Checkpoints + at least three Artifacts, and reports zero cache hits on first run — the same JSON file is both the user-facing example and the P0 acceptance fixture

### Requirement: UTF-8 bundles go through the loader

The system SHALL require callers to read bundles via `framework.workflows.loader.load_task_bundle`; direct `json.load(open(...))` is forbidden because Windows stdin is gbk and bundles may carry UTF-8 full-width quotes.

#### Scenario: load_task_bundle reads UTF-8 bundle without UnicodeDecodeError on Windows

- GIVEN a bundle under `examples/` whose `task.title` or `task.description` contains UTF-8 non-ASCII characters (e.g. full-width quotes / Chinese description text such as `examples/ue_export_pipeline_live.json`)
- WHEN code calls `framework.workflows.loader.load_task_bundle(path)` on a Windows host whose default locale encoding is gbk
- THEN the loader reads the file as UTF-8 (`Path(path).read_text(encoding="utf-8")` at `src/framework/workflows/loader.py`) and returns a populated `TaskBundle` without `UnicodeDecodeError`, while a hypothetical `json.load(open(path))` call without explicit encoding would have crashed under the same locale

### Requirement: Alias-based model references

The system SHALL resolve `provider_policy.models_ref: "<alias>"` via `expand_model_refs(raw, get_model_registry())` before Pydantic validation; a bundle MAY additionally declare `preferred_models` / `fallback_models` to override the alias at Step scope.

#### Scenario: Bundle declaring models_ref text_cheap is expanded via ModelRegistry before validation

- GIVEN a bundle Step whose `provider_policy` declares `models_ref: "text_cheap"` and no inline `preferred_models` / `fallback_models` (e.g. `examples/character_extract.json` `step_extract`)
- WHEN `load_task_bundle` runs `expand_model_refs(raw, get_model_registry())` on the parsed dict before any `Step.model_validate` call
- THEN the alias is replaced in-place by concrete `preferred_models` / `fallback_models` lists drawn from `config/models.yaml` `aliases.text_cheap`, the resulting Step passes Pydantic validation, and the bundle never reaches the runtime carrying a bare `models_ref` string

### Requirement: No hardcoded provider model ids

The system SHALL declare model selection via `provider_policy.models_ref` for every bundle under `examples/`. Concrete provider model ids MUST live in `config/models.yaml`'s `models` section, not in the bundle. A Step MAY additionally declare `preferred_models` / `fallback_models` as a Step-scoped override, but every entry MUST be a model id already registered in `config/models.yaml.models` so the registry remains the single source of routing config.

#### Scenario: Every bundle under examples/ resolves model selection via models_ref

- GIVEN the ten bundles currently shipped under `examples/` (`mock_linear.json`, `character_extract.json`, `review_3_images.json`, `image_pipeline.json`, `image_edit_pipeline.json`, `image_to_3d_pipeline.json`, `image_to_3d_pipeline_live.json`, `ue_export_pipeline.json`, `ue_export_pipeline_live.json`, `ue5_api_query.json`)
- WHEN their `provider_policy` blocks are inspected (mock-only bundles such as `mock_linear.json` exempt because they declare no `provider_policy`)
- THEN every non-mock Step declares `provider_policy.models_ref: "<alias>"` (e.g. `text_cheap` / `image_fast` / `review_judge_visual` / `image_edit` / `ue5_api_assist`), no Step inlines a concrete provider model id (no `qwen/...` / `hunyuan/...` / `openai/...` literal in the bundle JSON), and any future Step adding `preferred_models` / `fallback_models` MUST list ids that resolve through `config/models.yaml` `models` section

### Requirement: Loader-contract fence for every bundle

The system SHALL load every JSON under `examples/` through `load_task_bundle` in `tests/integration/test_example_bundles_smoke.py`; adding a new bundle MUST be accompanied by at least one integration-test assertion for it.

#### Scenario: A new bundle is added

- GIVEN a new `examples/<new>.json` is committed
- WHEN the test suite runs
- THEN `test_example_bundles_smoke.py` loads the file through `load_task_bundle` without error and an integration test exercises at least its loader + execution path

### Requirement: Stage-aligned acceptance coverage

The system SHALL keep the P0 / P1 / P2 / P3 / P4 / L1 / L4 coverage mapping: each stage has a matching bundle + integration test, and bundle-level changes that affect a stage SHALL update the corresponding integration test in the same change.

#### Scenario: Each P0-P4 stage has a dedicated integration test referencing its bundle

- GIVEN the P0-P4 acceptance taxonomy declared in `docs/acceptance/acceptance_report.md` §3
- WHEN `tests/integration/` is inspected for stage-aligned tests
- THEN `test_p0_mock_linear.py` references `examples/mock_linear.json`, `test_p1_structured_extraction.py` references `examples/character_extract.json`, `test_p2_standalone_review.py` references `examples/review_3_images.json`, `test_p3_production_pipeline.py` references `examples/image_pipeline.json`, and `test_p4_ue_manifest_only.py` references `examples/ue_export_pipeline.json` — and a bundle change touching any stage MUST land alongside an update to the matching `test_p[0-4]_*.py` file in the same commit

### Requirement: Live bundles carry premium-API warnings

The system SHALL mark any bundle that triggers a premium per-call API (mesh.generation via `image_to_3d_pipeline_live.json`, `ue_export_pipeline_live.json`) with a review-policy or documentation note pointing to ADR-007 and to the corresponding `probes/provider/probe_*` opt-in fallback.

#### Scenario: image_to_3d_pipeline_live.json fails closed at routing time when run without --live-llm

- GIVEN `examples/image_to_3d_pipeline_live.json` whose `step_image` declares `provider_policy.models_ref: "image_fast"` (an alias that resolves to real provider model ids in `config/models.yaml`)
- WHEN `framework.run.main` is invoked on this bundle without the `--live-llm` flag, so `_build_orchestrator` constructs a `CapabilityRouter` that does NOT register `LiteLLMAdapter` / `QwenMultimodalAdapter` / `HunyuanImageAdapter` (see `src/framework/run.py` adapter-registration block guarded by `if use_live_llm:`)
- THEN at routing time the run fails closed because no registered adapter reports `supports(model)=True` for the resolved real-provider model ids, surfacing a routing / no-available-adapter error rather than silently substituting a fake provider — and this fail-closed behaviour holds without the loader needing to inspect the `--live-llm` flag itself

### Requirement: UE hardware smoke is reachable via commandlet

The system SHALL provide an entry point for the UE 5.x hardware smoke that does not require GUI interaction: `PYTHONPATH=src python -m framework.run --task examples/ue_export_pipeline_live.json --live-llm --run-id a1_demo` followed by a commandlet invocation of `ue_scripts/a1_run.py`.

#### Scenario: ue_scripts/a1_run.py boots a UE Python session and consumes ue_export_pipeline_live.json import_plan without GUI

- GIVEN `ue_scripts/a1_run.py` is invoked from a UE 5.x Python session via either `Tools / File → Execute Python Script...` or `exec(open(...).read())` in the Python Console / commandlet (per the module docstring) on a host where the prior `framework.run --task examples/ue_export_pipeline_live.json --live-llm` step has materialised an `import_plan.json` under `Content/Generated/a1_demo/`
- WHEN the script runs
- THEN it sets `FORGEUE_RUN_FOLDER` to the run directory, prepends `ue_scripts/` to `sys.path`, imports `run_import`, and calls `run_import.run()` to consume the existing `import_plan` — providing a GUI-free, commandlet-reachable entry point, without asserting that any particular host machine succeeds end-to-end (UE install / asset content correctness remain the human operator's responsibility, see `docs/acceptance/acceptance_report.md` §6.1 for the 2026-04-23 UE 5.7.4 reference run)

### Requirement: Fixture Run directories for comparison tests

The system SHALL provide Run-directory fixtures under `tests/fixtures/comparison/` that simulate the output layout of a completed Run (`run_summary.json` + `_artifacts.json` + payload files + optional `ReviewReport` / `Verdict` JSON files). These fixtures MUST be consumable by the comparison module without invoking the full Orchestrator pipeline.

#### Scenario: A static fixture pair drives a deterministic diff test

- GIVEN `tests/fixtures/comparison/baseline_run/` and `tests/fixtures/comparison/candidate_run/` prepared with known per-artifact divergences
- WHEN a unit test calls `framework.comparison.diff_engine.compare(...)` against both snapshots
- THEN the resulting `RunComparisonReport.summary_counts` matches the expected diff taxonomy (unchanged / content_changed / metadata_only / missing / decision_changed)

### Requirement: Fixture Runs are offline and provider-key-free

The system SHALL author all comparison fixtures such that no API key, no network call, and no UE / ComfyUI process is required to generate or consume them; either the fixture is authored statically (JSON + placeholder bytes on disk) or it is generated by rerunning `examples/mock_linear.json` through the offline `FakeAdapter` + `FakeComfyWorker` path.

#### Scenario: Fixture pipeline runs without API keys, network, or external processes

- GIVEN the test environment has no `.env` and no provider API keys exported, no network is reachable, and no UE editor / ComfyUI process is running
- WHEN `tests/fixtures/comparison/builders.py::build_fixture_pair(root)` is called, OR `python -m framework.run --task examples/mock_linear.json --run-id <id> --artifact-root <root>` is invoked without `--live-llm` and without `--comfy-url`
- THEN the resulting Run directories materialise on disk and are immediately consumable by `python -m framework.comparison`; no provider key is read, no HTTP request is issued, no UE / ComfyUI process is started, and the FakeAdapter + FakeComfyWorker handle every generation step

### Requirement: Fixture Runs do not pollute top-level artifact buckets

The system SHALL place all comparison test fixtures under `tests/fixtures/comparison/`; they MUST NOT be committed under `./artifacts/` or `./demo_artifacts/` (both of which remain gitignored per the project-level .gitignore). Dynamic fixture output (e.g. comparison report produced during a test) MUST land in `tmp_path` or the pytest-provided temporary directory, never in `./artifacts/` or `./demo_artifacts/`.

#### Scenario: Fixture builders write only to caller-provided root

- GIVEN an integration test invokes `build_fixture_pair(tmp_path / "real_artifacts" / "2000-01-01")` and then runs `python -m framework.comparison --artifact-root <...>/real_artifacts --output-dir tmp_path / "out"`
- WHEN the test completes
- THEN every produced file is rooted under the caller-provided `tmp_path`; a recursive pre/post snapshot of `<repo>/demo_artifacts/` and `<repo>/artifacts/` shows byte-identical contents (no added / removed / modified files), proving the comparison run did not leak into either gitignored top-level bucket

### Requirement: Date bucket handling in fixtures

The system SHALL NOT hardcode real calendar dates into fixture Run directories; fixtures MUST either use a synthetic date bucket (e.g. `2000-01-01`) or mock the date resolution path so tests remain stable over time.

#### Scenario: Builder uses a synthetic date bucket regardless of wall clock

- GIVEN the test runs on any calendar day (e.g. 2026-04-25 or 2030-01-01)
- WHEN `build_fixture_pair(root)` lays out fixture Run directories
- THEN they live under `<root>/2000-01-01/<run_id>/` regardless of `datetime.now()`; payload bytes, recorded `created_at`, and `Checkpoint.completed_at` are all derived from fixed constants, so fixture output stays byte-deterministic over time and no real calendar date leaks into hashes or paths

## Invariants

- Bundle Artifact flow is end-to-end real objects — no mocks across Step boundaries (NFR-MAINT-005).
- Bundles MUST be UTF-8 with LF line endings.
- Bundles MUST NOT commit `artifact_root` paths that depend on machine-absolute directories; the default is the CLI-provided `--artifact-root` argument.
- Test totals shift with every Codex / adversarial review fix; the authoritative count always comes from `python -m pytest -q`.

## Validation

- Unit: `tests/integration/test_example_bundles_smoke.py` (loader contract for every JSON under `examples/`)
- Integration (stage-aligned): `tests/integration/test_p{0,1,2,3,4}_*.py`, `test_l4_image_to_3d.py`, `test_image_edit.py`, `test_dag_concurrency.py`, `test_ws_progress.py`
- Level 0 offline smoke: `python -m framework.run --task examples/mock_linear.json --run-id demo --artifact-root ./artifacts`
- Level 1 live smoke examples: `python -m framework.run --task examples/character_extract.json --run-id r1 --live-llm`, `python -m framework.run --task examples/image_pipeline.json --run-id r2 --live-llm`
- Level 2 hardware smoke: `docs/ai_workflow/validation_matrix.md` Level 2 section (commandlet path)
- Test totals: see `python -m pytest -q` actual output.

## Non-Goals

- Bundle template inheritance (Workflow `template_ref` is reserved; hand-authoring remains the default).
- Auto-generated bundles from prompts (not currently in scope).
- Cross-repo bundle sharing / registry.

## Notes on doc drift

- `README.md` §"Bundle 与 Example" historically lists the original five bundles (`mock_linear` / `character_extract` / `review_3_images` / `image_pipeline` / `ue_export_pipeline`). The actual `examples/` directory now holds ten bundles. The doc-drift reconciliation is deferred to a later change; the present spec treats `ls examples/` as authoritative.
