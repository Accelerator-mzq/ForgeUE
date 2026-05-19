# Delta Spec: examples-and-acceptance (cleanup-main-spec-scenarios)

> 给 `openspec/specs/examples-and-acceptance/spec.md` 的 7 个已有 Requirement 补 `#### Scenario:` 块。**不**新增 Requirement,**不**改 Requirement 标题。其中 `No hardcoded provider model ids` 一条按方案 A 收紧描述(硬约束 `models_ref`,保留已注册 model id 的 Step-scoped 逃生口),其余 6 条复用主 spec 描述。

## MODIFIED Requirements

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
