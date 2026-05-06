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

### Requirement: Active change evidence is captured under OpenSpec change subdirectories with writeback protocol

The system SHALL store all implementation, review, and verification evidence (brainstorming notes / execution plan / micro tasks / TDD log / debug log / Superpowers review / codex stage reviews / cross-checks / verify report / doc sync report / finish gate report) under the active OpenSpec change at `openspec/changes/<id>/{notes,execution,review,verification}/`. Each evidence file SHALL carry a 12-key frontmatter (1 wrapper key `change_id` plus 11 audit fields: `stage`, `evidence_type`, `contract_refs`, `aligned_with_contract`, `drift_decision`, `writeback_commit`, `drift_reason`, `reasoning_notes_anchor`, `detected_env`, `triggered_by`, `codex_plugin_available`). When `aligned_with_contract: false`, the file MUST carry a `drift_decision` of `pending` / `written-back-to-<artifact>` / `disputed-permanent-drift`; `written-back-to-*` MUST reference a real `writeback_commit` that actually modifies the named contract artifact (proposal.md / design.md / tasks.md / specs/<cap>/spec.md); `disputed-permanent-drift` MUST carry a ≥ 50 character `drift_reason` plus a corresponding `reasoning_notes_anchor` in the change's `design.md` `## Reasoning Notes` section (heading level 2). Evidence files MUST NOT introduce new normative decisions; any decision exposed during implementation MUST be written back to the OpenSpec contract artifact, never declared inside an evidence file as a new contract source.

#### Scenario: Implementation plan that references a non-existent tasks.md anchor is blocked at the S2 to S3 transition

- GIVEN an active OpenSpec change at `openspec/changes/<change-id>/` with a populated `tasks.md` declaring task groups 1-N and an `execution/execution_plan.md` produced by Superpowers writing-plans skill referencing tasks via `tasks.md#<group>.<index>` anchors
- AND `execution/execution_plan.md` contains an entry that references `tasks.md#99.1` which is NOT present in `tasks.md`
- WHEN the implementing agent runs `python tools/forgeue_change_state.py --change <change-id> --writeback-check --json` to gate the S2 to S3 transition
- THEN the tool emits a structured DRIFT record `{"type": "evidence_references_missing_anchor", "file": "execution/execution_plan.md", "ref": "tasks.md#99.1"}` and exits with code 5, blocking the transition; the implementing agent MUST either remove the offending plan entry or write back a corresponding task to `tasks.md` (creating a real `writeback_commit`) and re-run the writeback-check before proceeding to S3

#### Scenario: Codex stage review evidence with aligned_with_contract false but no drift_decision is blocked at finish gate

- GIVEN `review/codex_design_review.md` produced by `/codex:adversarial-review --background` that surfaces a design choice not present in `design.md`, where the implementing agent left frontmatter `aligned_with_contract: false` together with `drift_decision: null` (i.e. did neither write back nor mark as permanent drift)
- WHEN the implementing agent runs `python tools/forgeue_finish_gate.py --change <change-id> --json` before invoking `/opsx:archive`
- THEN the tool emits `[FAIL] aligned_with_contract=false but drift_decision=null in review/codex_design_review.md` and exits with code 2, preventing archive; the implementing agent MUST either (a) write back the surfaced decision to `design.md` and update `writeback_commit` to a real git commit sha that touches `design.md`, or (b) mark `drift_decision: disputed-permanent-drift` with a ≥ 50 character `drift_reason` and a `reasoning_notes_anchor` whose target paragraph exists in `design.md`'s `## Reasoning Notes` section

#### Scenario: disputed-permanent-drift requires a real Reasoning Notes anchor in design.md

- GIVEN an evidence file with frontmatter `drift_decision: disputed-permanent-drift`, `reasoning_notes_anchor: reasoning-notes-commands-count`, and `drift_reason` of length 87 characters
- WHEN `forgeue_finish_gate.py` parses `design.md`'s `## Reasoning Notes` section searching for an anchor `reasoning-notes-commands-count`
- THEN if the named anchor exists in `design.md` with a substantive paragraph (≥ 20 words) explaining the rationale, the evidence file passes finish gate; otherwise the tool emits `[FAIL] disputed-permanent-drift in <file>: missing Reasoning Notes anchor 'reasoning-notes-commands-count' in design.md` and exits with code 2; the implementing agent MUST add the anchor and an explanatory paragraph in `design.md` `## Reasoning Notes` before retrying finish gate

### Requirement: ComfyUI live smoke bundle uses manifest workflow not inline graph

The system SHALL ship `examples/comfy_local_smoke.json` as the canonical live smoke entry for ComfyUI integration. The bundle SHALL declare its image generation step via `step.config.spec.comfy_workflow` (manifest name, e.g. `GameAssets/01b_singleview_sdxl`) + `step.config.spec.comfy_params` (JSON dict of params accepted by that manifest's `python -m comfyui_api params --workflow <name>` schema) + `step.config.spec.comfy_lifecycle` (one of the four lifecycle modes). The bundle MUST NOT inline a `workflow_graph` JSON. The legacy v1 inline-workflow bundle path (and its supporting `examples/comfy/build_bundle.py` + `examples/comfy/tavern_door.api.json` + `examples/comfy/image_z_image_turbo.json` files) is preserved in git history at commit `292420a` for diff reference and SHALL NOT be reintroduced.

#### Scenario: examples/comfy_local_smoke.json declares manifest workflow name + params

- **GIVEN** the post-change `examples/comfy_local_smoke.json` loaded via `framework.workflows.loader.load_task_bundle`
- **WHEN** the loader reads `steps[0].config.spec`
- **THEN** the spec contains `comfy_workflow` (string, e.g. `"GameAssets/01b_singleview_sdxl"`), `comfy_params` (dict), optionally `comfy_lifecycle` (string), and contains NO `workflow_graph` field; the bundle is < 5 KB (the v1 path with inlined SD1.5 workflow_graph at commit 292420a is 154 lines / ~5 KB on its own)

#### Scenario: examples/comfy/ legacy helper directory is removed

- **GIVEN** the post-change repository tree
- **WHEN** the contents of `examples/comfy/` are inspected
- **THEN** `examples/comfy/build_bundle.py`, `examples/comfy/tavern_door.api.json`, and `examples/comfy/image_z_image_turbo.json` no longer exist on the working tree (commit history retains them through `git show 292420a:examples/comfy/<file>`); the `examples/comfy/` directory itself MAY remain only if it carries the new manifest-style assets, otherwise it SHALL be removed

### Requirement: Live ComfyUI smoke is gated behind agent-CLI availability

The system SHALL document in the bundle's loader-test smoke + in CLAUDE.md that running `examples/comfy_local_smoke.json` end-to-end requires (1) ComfyUI installed under a host-specific path, (2) `python -m comfyui_api` agent CLI available under the path declared in `config/models.yaml` `providers.comfy_api.scripts_dir`, and (3) `python -m framework.run --task examples/comfy_local_smoke.json --live-llm`. The offline loader-contract test SHALL still pass without any of those preconditions because the loader does not invoke the worker.

#### Scenario: comfy_local_smoke.json passes the offline loader-contract fence without a real ComfyUI

- **GIVEN** a CI runner without ComfyUI installed and without `D:/AI/ComfyUI/scripts/`
- **WHEN** `tests/integration/test_example_bundles_smoke.py` loads `examples/comfy_local_smoke.json` through `load_task_bundle`
- **THEN** the bundle parses cleanly into a `TaskBundle`, no subprocess is spawned, and the smoke test asserts only loader-level invariants (`comfy_workflow` is a string, `comfy_params` is a dict, alias / model-id rules satisfied) — exactly mirroring the existing fence pattern for `image_to_3d_pipeline_live.json`

### Requirement: ComfyUI mesh live smoke bundle is image-to-mesh with upstream image step + DAG dependency

The system SHALL ship `examples/comfy_local_smoke_mesh.json` as the canonical live smoke entry for the ComfyUI mesh capability. The bundle SHALL be **image-to-mesh** (B2 codex finding accepted-codex 2026-05-03 + design D7): it contains AT LEAST two steps in DAG order:

1. **Upstream image step** (e.g. `image_step`):
   - `kind: image.generation`
   - `provider_policy.models_ref: "image_local"` (uses ComfyUI for the image step too — keeps the live smoke self-contained without remote API key dependency) OR `"image_fast"` (uses cloud image provider — requires DASHSCOPE_API_KEY etc.). The smoke bundle SHALL default to `image_local` for symmetry; the alternative is documented in CLAUDE.md.
   - Standard `comfy_workflow / comfy_params / comfy_lifecycle` for an image manifest (e.g. `GameAssets/01b_singleview_sdxl`)
   - Produces an `image.candidate` Artifact

2. **Mesh step** (e.g. `mesh_step`):
   - `kind: mesh.generation`
   - `provider_policy.models_ref: "mesh_local"` (resolves to `comfy/local-mesh`)
   - DAG dependency: `depends_on: ["image_step"]` (or equivalent)
   - `step.config.spec.comfy_workflow: "<selected mesh manifest name>"` (string, determined at implementation time by enumerating `python -m comfyui_api list` output and selecting one that produces `outputs.glb` REQUIRED — auxiliary `outputs.images` preview is tolerated per the provider-routing capability-aware validation)
   - `step.config.spec.comfy_params: {<manifest-specific params from `python -m comfyui_api params --workflow <name>`, EXCLUDING the image-input key>}` — the source image path is injected by `GenerateMeshExecutor._generate_via_comfy_worker` (NOT by the bundle author); see the artifact-contract spec Requirement "Mesh worker source image bytes are written to in-tree input file before subprocess invocation"
   - `step.config.spec.comfy_image_param_key: "input_image"` (round 5 修订 default,与 `LoadImage` 节点参数名一致;bundles MAY override if a specific manifest uses different key like `image` / `source_image`)
   - `step.config.spec.comfy_lifecycle: "none"`

The bundle MUST NOT inline a `workflow_graph` JSON. The bundle SHALL be a sibling file to `examples/comfy_local_smoke.json` (image-mode smoke from the prior change), NOT a replacement. The DAG structure SHALL match the pattern of the existing `examples/image_to_3d_pipeline.json` reference bundle (image step → mesh step) — implementers MAY consult that file for layout details; ComfyUI mesh substitutes for Hunyuan3D mesh as the mesh worker target.

#### Scenario: examples/comfy_local_smoke_mesh.json declares image-to-mesh DAG with mesh_local alias

- **GIVEN** the post-change `examples/comfy_local_smoke_mesh.json` loaded via `framework.workflows.loader.load_task_bundle`
- **WHEN** the loader reads the bundle structure
- **THEN** the bundle contains AT LEAST two steps; the upstream image step's `provider_policy.models_ref` is `"image_local"` (or `"image_fast"`) and produces an `image.candidate` Artifact; the mesh step's `provider_policy.models_ref` is `"mesh_local"`, has a DAG `depends_on` reference to the image step, and `step.config.spec` contains `comfy_workflow` (string, real ComfyUI mesh manifest name), `comfy_params` (dict, NOT containing the image input key — that's injected at runtime), `comfy_image_param_key` (optional, defaults to `"image_path"`), `comfy_lifecycle: "none"`, and contains NO `workflow_graph` field; after `expand_model_refs`, the mesh step's resolved `prepared_routes` contains exactly one route with `model="comfy/local-mesh"`

#### Scenario: examples/comfy_local_smoke.json (image-mode) is preserved and unchanged

- **GIVEN** the post-change repository tree
- **WHEN** `examples/comfy_local_smoke.json` is inspected
- **THEN** the image-mode smoke bundle from `comfy-agent-cli-adoption` exists unchanged at the same path; both bundles coexist and exercise different ComfyAgentWorker capability modes; users selecting between them via `--task examples/comfy_local_smoke.json` (single image step) vs `--task examples/comfy_local_smoke_mesh.json` (image step → mesh step) get image-only vs full image-to-mesh pipeline respectively

### Requirement: Live ComfyUI mesh smoke is gated behind agent-CLI mesh manifest availability + image manifest availability

The system SHALL document in the bundle's loader-test smoke + in CLAUDE.md (ComfyUI section) that running `examples/comfy_local_smoke_mesh.json` end-to-end requires:

1. ComfyUI installed under a host-specific path with at least one image workflow manifest available (for the upstream image step) AND at least one image-to-mesh workflow manifest available (for the mesh step)
2. `python -m comfyui_api list` output containing both manifest names referenced by the bundle
3. `FORGEUE_COMFY_SCRIPTS_DIR` pointing to that ComfyUI's `scripts/` directory
4. (If using `image_fast` for the upstream step instead of `image_local`) the cloud image provider API key (`DASHSCOPE_API_KEY` etc.)
5. `python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm`

The offline loader-contract test SHALL still pass without any of those preconditions because the loader does not invoke any worker. CLAUDE.md SHALL be updated to reflect the dual smoke bundles (image-only + image-to-mesh) and to note that mesh smoke produces a `.glb` file under `artifacts/<today>/<run_id>/<artifact_id>.glb` (the in-tree filename is `<artifact_id>.glb` via `repo.put` + `file_suffix=".glb"`, NOT the original ComfyUI filename — see artifact-contract spec).

#### Scenario: comfy_local_smoke_mesh.json passes the offline loader-contract fence without a real ComfyUI

- **GIVEN** a CI runner without ComfyUI installed and without `D:/AI/ComfyUI/scripts/`
- **WHEN** `tests/integration/test_example_bundles_smoke.py` loads `examples/comfy_local_smoke_mesh.json` through `load_task_bundle`
- **THEN** the bundle parses cleanly into a `TaskBundle` (both image step and mesh step), no subprocess is spawned, and the smoke test asserts only loader-level invariants (image step's `comfy_workflow` is a string, mesh step's `comfy_workflow` is a string, mesh step's `comfy_params` is a dict, both lifecycles equal `"none"`, mesh step's `prepared_routes` contains `comfy/local-mesh`, mesh step has DAG `depends_on` reference to image step); the same generic structural fence (`test_bundle_dry_run_passes` etc.) applies and SHALL continue to emit only `warning_only=True` for the missing ComfyUI probe (per `comfy-agent-cli-adoption` G8 commit 7 drift writeback contract)

#### Scenario: Live mesh smoke evidence is captured in change notes after manual run

- **GIVEN** the implementer has run `python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id mesh_smoke_<date>` on a host with ComfyUI installed and both image + mesh manifests available
- **WHEN** the run completes successfully (image step produces an image artifact, mesh step consumes it via `_resolve_source_image` and produces a GLB artifact)
- **THEN** the resulting `.glb` file lives under `artifacts/<date>/mesh_smoke_<date>/<mesh_artifact_id>.glb` (in-tree, NFR-PORT-004 satisfied via `repo.put` + `FileBackend`); the GLB passes magic-bytes validation (starts with `b"glTF"`); the source image PNG is preserved at `artifacts/<date>/mesh_smoke_<date>/comfy/input/<sha1>.png` (in-tree per artifact-contract); a live smoke evidence file is written to `openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/notes/live_smoke_mesh_<date>.md` recording: image manifest name, mesh manifest name, mesh `comfy_image_param_key` actual value, mesh `comfy_params`, run_id, GLB artifact_id + file path + size, source image artifact_id + path, `Artifact.metadata["worker_metadata"]` dump showing comfy provenance — mirroring the format of the image-change `live_smoke_20260503.md` evidence file

### Requirement: ComfyUI audio live smoke bundle is text-to-audio with single generate / capability_ref="audio.t2a" step

The system SHALL ship `examples/comfy_local_smoke_audio.json` as the canonical live smoke entry for the ComfyUI audio capability. The bundle SHALL be **text-to-audio** (per provider-routing design D7): it contains exactly one `Step` whose `type == StepType.generate` (the existing enum value, NOT a new step type) and `capability_ref == "audio.t2a"`, with all manifest-specific parameters living inside `step.config.spec.comfy_params`:

The bundle JSON SHALL use the canonical loader top-level three-section schema (F-Plan-1 round-2 plan 修订:`task` / `workflow`(no `steps` nested)/ `steps` array — mirrors `examples/comfy_local_smoke.json` and `examples/comfy_local_smoke_mesh.json` real schema; `src/framework/workflows/loader.py:34-36` reads `raw["task"]` + `raw["workflow"]` + `[s for s in raw["steps"]]`):

- Top-level `task` object: `task_id`, `task_type: "asset_generation"`, `run_mode: "basic_llm"`, `title`, `input_payload.prompt`, `expected_output.artifact_types: ["audio_asset"]`, `project_id`
- Top-level `workflow` object: `workflow_id`, `name`, `version`, `entry_step_id: "step_audio"`, `step_ids: ["step_audio"]` (NO `steps` nested — `steps` is at top level)
- Top-level `steps` array containing exactly one Step object:
  - `step_id`: e.g. `"step_audio"`
  - `type`: `"generate"` (serialized from `StepType.generate`)
  - `name`: human-readable
  - `risk_level`: `"medium"`
  - `capability_ref`: `"audio.t2a"`
  - `provider_policy`: `{"capability_required": "audio.t2a", "models_ref": "audio_local"}` (resolves to `comfy/local-audio`)
  - `retry_policy` (top-level Step field, OPTIONAL): `{"max_attempts": 2, "backoff": "fixed", "retry_on": ["timeout", "provider_error"]}` — F-Plan-6 round-2 plan 修订:`RetryPolicy` schema in `src/framework/core/policies.py:25-30` only contains `max_attempts/backoff/retry_on`; the bundle SHALL NOT place `timeout_seconds` here
  - `config`: executor-specific free-form dict containing:
    - `num_candidates`: 1 (or > 1 — F-Plan-3 round-2 plan: implementation supports per-candidate loop in `generate_audio`)
    - `seed`: same value as `comfy_params.seed` (or absent if random)
    - `worker_timeout_s`: 300 (F-Plan-6 round-2 plan 修订:subprocess timeout lives in `step.config.worker_timeout_s`,NOT in `retry_policy`;mirrors `cfg.get("worker_timeout_s")` reading at `src/framework/runtime/executors/generate_image.py:83` and `generate_mesh.py:190`)
    - `spec.comfy_workflow`: `"Audio_Workflows/audio_stable_audio_example"` (default selection per provider-routing design D11; users MAY swap to `Audio_Workflows/audio_ace_step_1_t2a_instrumentals` if ACE-Step custom node is installed)
    - `spec.comfy_params`: `{<manifest-specific params from `python -m comfyui_api params --workflow Audio_Workflows/audio_stable_audio_example`>}` — for the Stable Audio default, this includes `text` (REQUIRED, positive prompt), `negative_prompt` (OPTIONAL, default `""`), `duration_seconds` (OPTIONAL, default `47.6` per manifest, smoke bundle uses `10.0` to keep L2 evidence short), `seed` (OPTIONAL), `steps` (OPTIONAL, default `50`), `filename_prefix` (OPTIONAL); the bundle SHALL NOT use `comfy_image_param_key` (audio has no source image path)
    - `spec.comfy_lifecycle`: `"none"`

The bundle MUST NOT inline a `workflow_graph` JSON. The bundle SHALL be a sibling file to `examples/comfy_local_smoke.json` (image-mode) and `examples/comfy_local_smoke_mesh.json` (mesh-mode), NOT a replacement. The single-step structure differs from the mesh bundle's two-step DAG because audio has no source bytes input requirement.

#### Scenario: examples/comfy_local_smoke_audio.json declares text-to-audio single step with audio_local alias and canonical loader schema

- **GIVEN** the post-change `examples/comfy_local_smoke_audio.json` loaded via `framework.workflows.loader.load_task_bundle`
- **WHEN** the loader reads the bundle structure
- **THEN** (F-Plan-1 round-2 plan 修订:bundle has canonical top-level three-section schema) the JSON has top-level keys `task` + `workflow` + `steps` (NOT nested `workflow.steps[]`); `Task.model_validate(raw["task"])` parses cleanly; `Workflow.model_validate(raw["workflow"])` parses cleanly with `step_ids` listing one step (no `steps` nested under workflow); `[Step.model_validate(s) for s in raw["steps"]]` produces exactly one Step; the step's `type == StepType.generate` (`"generate"` in JSON); `step.capability_ref == "audio.t2a"`; `step.provider_policy.models_ref == "audio_local"`; `step.provider_policy.capability_required == "audio.t2a"`; (F-Plan-6 round-2 plan 修订) `step.retry_policy` if present contains only `max_attempts/backoff/retry_on` (no `timeout_seconds`); `step.config.worker_timeout_s` is the subprocess timeout source (e.g. 300); `step.config.spec` contains `comfy_workflow` (string, real ComfyUI audio manifest name), `comfy_params` (dict containing prompt key matching the manifest's expected schema, e.g. `text` for Stable Audio or `tags` for ACE-Step), `comfy_lifecycle: "none"`, and contains NO `workflow_graph` field, NO `comfy_image_param_key` field; after `expand_model_refs`, the resolved `prepared_routes` contains exactly one route with `model="comfy/local-audio"`

#### Scenario: examples/comfy_local_smoke.json (image) and examples/comfy_local_smoke_mesh.json (mesh) are preserved unchanged

- **GIVEN** the post-change repository tree
- **WHEN** `examples/comfy_local_smoke.json` and `examples/comfy_local_smoke_mesh.json` are inspected
- **THEN** both prior smoke bundles exist unchanged at the same paths; all three bundles coexist and exercise different ComfyAgentWorker capability modes; users selecting between them via `--task examples/comfy_local_smoke.json` (image), `--task examples/comfy_local_smoke_mesh.json` (image-to-mesh), or `--task examples/comfy_local_smoke_audio.json` (text-to-audio) get the corresponding capability path

### Requirement: Live ComfyUI audio smoke is gated behind agent-CLI audio manifest availability

The system SHALL document in the bundle's loader-test smoke + in CLAUDE.md (ComfyUI section) that running `examples/comfy_local_smoke_audio.json` end-to-end requires:

1. ComfyUI installed under a host-specific path with at least one audio workflow manifest available (default: `Audio_Workflows/audio_stable_audio_example` — Stable Audio Open 1.0; alternative: `Audio_Workflows/audio_ace_step_1_t2a_instrumentals` — ACE-Step v1 3.5B, requires ACE-Step custom node installation)
2. `python -m comfyui_api list` output containing the manifest name referenced by the bundle
3. `FORGEUE_COMFY_SCRIPTS_DIR` pointing to that ComfyUI's `scripts/` directory; **NO** `FORGEUE_COMFY_INPUT_DIR` env var required (audio has no source bytes path — that env var is mesh-specific)
4. First run: ComfyUI auto-downloads model weights from HuggingFace (Stable Audio Open ~2GB, ACE-Step ~7GB); subsequent runs use the cache
5. `python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm`

The offline loader-contract test SHALL still pass without any of those preconditions because the loader does not invoke any worker. CLAUDE.md SHALL be updated to reflect the triple smoke bundles (image / mesh / audio) and to note that audio smoke produces a `.flac` (or `.mp3` / `.wav` depending on manifest output) file under `artifacts/<today>/<run_id>/<artifact_id>.flac` (the in-tree filename is `<artifact_id>.<format>` via `repo.put` + `file_suffix=f".{cand.format}"`, NOT the original ComfyUI filename — see artifact-contract spec).

#### Scenario: comfy_local_smoke_audio.json passes the offline loader-contract fence without a real ComfyUI

- **GIVEN** a CI runner without ComfyUI installed and without `D:/AI/ComfyUI/scripts/`
- **WHEN** `tests/integration/test_example_bundles_smoke.py` loads `examples/comfy_local_smoke_audio.json` through `load_task_bundle`
- **THEN** the bundle parses cleanly into a `TaskBundle`, no subprocess is spawned, and the smoke test asserts only loader-level invariants (`comfy_workflow` is a string, `comfy_params` is a dict containing at least one prompt-like key, `audio_local` alias resolves to `comfy/local-audio`, no `workflow_graph` field, no `comfy_image_param_key` field, `depends_on` is empty); mirrors the existing fence pattern for `comfy_local_smoke.json` and `comfy_local_smoke_mesh.json`

#### Scenario: Live audio smoke L2 evidence file is real audio bytes under in-tree artifact path

- **GIVEN** a host with ComfyUI + Stable Audio Open model weights cached + `FORGEUE_COMFY_SCRIPTS_DIR` configured + `python -m factory_v3 serve` running
- **WHEN** the user runs `python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id audio_smoke_<timestamp>`
- **THEN** the resulting `artifacts/<today>/audio_smoke_<timestamp>/<artifact_id>.flac` (or `.mp3` / `.wav` depending on manifest output) file: (1) exists, (2) has size > 100 KB (avoids 0-byte false positives), (3) header bytes match the format-specific magic table (`flac → b"fLaC"`; `mp3 → b"ID3"` or MPEG frame sync `b"\xFF\xFB" / b"\xFF\xFA" / b"\xFF\xF3" / b"\xFF\xF2"`; `wav → b"RIFF"` at offset 0 AND `b"WAVE"` at offset 8). The L2 evidence note `notes/live_smoke_audio_<date>.md` SHALL record these three objective checks; subjective audio quality is left to human spot-check. (F-Plan-5 round-2 plan 修订:duration ±10% check is OUT OF SCOPE for this change — design D10 + this spec lock `AudioCandidate.duration_seconds=None always` because ComfyUI agent CLI does not expose audio metadata; ForgeUE does not introduce mutagen / `wave` / `aifc` parsing in this change scope; a follow-on `audio-metadata-parser` change MAY add the duration check after introducing a parser dependency)

### Requirement: .env.example MUST list the env var names that are actually read at runtime

The system SHALL keep `.env.example` template in sync with the env var names that
runtime code (`config/models.yaml` + `src/framework/run.py` + provider workers)
actually reads at startup. Specifically, for any provider listed in the template,
the variable names commented in `.env.example` MUST match the names appearing in
`config/models.yaml::providers.<provider>.api_key_env` and any direct `os.environ.
get("...")` lookup in `src/framework/run.py`. Cross-references SHOULD be added as
inline comments next to the placeholder so future env-var renames are easy to audit.

#### Scenario: Hunyuan 3D mesh provider env var alignment

- **GIVEN** a fresh user copies `.env.example` to `.env` and fills in the Hunyuan
  3D mesh provider section
- **WHEN** they run `python -m framework.run --task <bundle> --live-llm`
- **THEN** the env var name they configured MUST be `HUNYUAN_3D_KEY` (matching
  `config/models.yaml:95 api_key_env: HUNYUAN_3D_KEY` and `src/framework/run.py:100
  os.environ.get("HUNYUAN_3D_KEY")`)
- **AND** template MUST NOT show TC3-HMAC-SHA256-style three-segment placeholders
  (`HUNYUAN_3D_SECRET_ID` / `HUNYUAN_3D_SECRET_KEY` / `HUNYUAN_3D_REGION`) which
  no longer correspond to any runtime read path
- **AND** template SHOULD inline a comment cross-referencing the runtime read
  location so future renames are surfaced

#### Scenario: Existing .env files configured with old TC3 fields are not broken

- **GIVEN** a `.env` file already configured with the old TC3-HMAC-SHA256 fields
  (`HUNYUAN_3D_SECRET_ID/SECRET_KEY/REGION`)
- **WHEN** runtime starts
- **THEN** those env vars are NOT read by any current code path
- **AND** they SHALL NOT cause any error (they are simply ignored as unrecognized
  env vars)
- **AND** Hunyuan 3D mesh provider falls back to FakeMeshWorker / Tripo3D /
  provider auth failure (existing behavior; outside this change's scope)

### Requirement: ComfyUI video live smoke bundle is text-to-video with single generate / capability_ref="video.t2v" step

The system SHALL ship `examples/comfy_local_smoke_video.json` as the canonical live smoke entry for the ComfyUI video capability. The bundle SHALL be **text-to-video** (per provider-routing design D7): it contains exactly one `Step` whose `type == StepType.generate` (the existing enum value, NOT a new step type) and `capability_ref == "video.t2v"`, with all manifest-specific parameters living inside `step.config.spec.comfy_params`:

The bundle JSON SHALL use the canonical loader top-level three-section schema (sweep-mirror of audio Phase 2 schema: `task` / `workflow` (no `steps` nested) / `steps` array — mirrors `examples/comfy_local_smoke.json` / `comfy_local_smoke_mesh.json` / `comfy_local_smoke_audio.json` real schema; `src/framework/workflows/loader.py:34-36` reads `raw["task"]` + `raw["workflow"]` + `[s for s in raw["steps"]]`):

- Top-level `task` object: `task_id`, `task_type: "asset_generation"`, `run_mode: "basic_llm"`, `title`, `input_payload.prompt`, `expected_output.artifact_types: ["video_asset"]`, `project_id`
- Top-level `workflow` object: `workflow_id`, `name`, `version`, `entry_step_id: "step_video"`, `step_ids: ["step_video"]` (NO `steps` nested — `steps` is at top level)
- Top-level `steps` array containing exactly one Step object:
  - `step_id`: e.g. `"step_video"`
  - `type`: `"generate"` (serialized from `StepType.generate`)
  - `name`: human-readable
  - `risk_level`: `"medium"`
  - `capability_ref`: `"video.t2v"`
  - `provider_policy`: `{"capability_required": "video.t2v", "models_ref": "video_local"}` (resolves to `comfy/local-video`)
  - `retry_policy` (top-level Step field, OPTIONAL): `{"max_attempts": 2, "backoff": "fixed", "retry_on": ["timeout", "provider_error"]}` — sweep-mirror of audio Phase 2 schema lock: `RetryPolicy` schema in `src/framework/core/policies.py:25-30` only contains `max_attempts/backoff/retry_on`; the bundle SHALL NOT place `timeout_seconds` here
  - `config`: executor-specific free-form dict containing:
    - `num_candidates`: 1 (or > 1 — per-candidate loop in `generate_video` supports it; sweep-mirror of audio F-Plan-3 round-2)
    - `seed`: same value as `comfy_params.seed` (or absent if random)
    - `worker_timeout_s`: **600** (D3: Wan T2V manifest `estimated_time_s: 420` ≈ 7 分钟 + ComfyUI 启动 + 模型加载余量;sweep-mirror of audio Phase 2 `worker_timeout_s` placement at `step.config.worker_timeout_s`, NOT in `retry_policy`)
    - `spec.comfy_workflow`: **`"Vedio/Wan2.1-T2V-1.3B_native_5sec"`** (D3 default; D5: `Vedio/` upstream拼写照实跟随,**不**做翻译;users MAY swap to `Vedio/Wan2.1-T2V-1.3B_native_teacache` for TeaCache-accelerated variant if custom node installed, or to `Vedio/Wan2.2-T2V-A14B_GGUF` for higher quality with 14+ GB VRAM)
    - `spec.comfy_params`: `{<manifest-specific params from `python -m comfyui_api params --workflow Vedio/Wan2.1-T2V-1.3B_native_5sec`>}` — for the Wan 1.3B 5sec default, this includes `positive_prompt` (REQUIRED), `negative_prompt` (OPTIONAL, default `"blurry, low quality, distorted, watermark, worst quality, jpeg artifacts"` per manifest), `width` (OPTIONAL, default `832`), `height` (OPTIONAL, default `480`), `num_frames` (OPTIONAL, default `81`), `seed` (OPTIONAL, default `5042`), `steps` (OPTIONAL, default `25`), `filename_prefix` (OPTIONAL, default `"wan21_1.3b_5sec"`); the bundle SHALL NOT use `comfy_image_param_key` (text-to-video has no source image path, sweep-mirror of audio)
    - `spec.comfy_lifecycle`: `"none"`

The bundle MUST NOT inline a `workflow_graph` JSON. The bundle SHALL be a sibling file to `examples/comfy_local_smoke.json` (image-mode), `examples/comfy_local_smoke_mesh.json` (mesh-mode), and `examples/comfy_local_smoke_audio.json` (audio-mode), NOT a replacement. The single-step structure mirrors the audio bundle (text-to-something, no source bytes input).

#### Scenario: examples/comfy_local_smoke_video.json declares text-to-video single step with video_local alias and canonical loader schema

- **GIVEN** the post-change `examples/comfy_local_smoke_video.json` loaded via `framework.workflows.loader.load_task_bundle`
- **WHEN** the loader reads the bundle structure
- **THEN** (sweep-mirror of audio Phase 2: bundle has canonical top-level three-section schema) the JSON has top-level keys `task` + `workflow` + `steps` (NOT nested `workflow.steps[]`); `Task.model_validate(raw["task"])` parses cleanly; `Workflow.model_validate(raw["workflow"])` parses cleanly with `step_ids` listing one step (no `steps` nested under workflow); `[Step.model_validate(s) for s in raw["steps"]]` produces exactly one Step; the step's `type == StepType.generate` (`"generate"` in JSON); `step.capability_ref == "video.t2v"`; `step.provider_policy.models_ref == "video_local"`; `step.provider_policy.capability_required == "video.t2v"`; `step.retry_policy` if present contains only `max_attempts/backoff/retry_on` (no `timeout_seconds`); `step.config.worker_timeout_s == 600`; `step.config.spec` contains `comfy_workflow` (string starting with `"Vedio/"` — D5 upstream typo intentional), `comfy_params` (dict containing prompt key matching the manifest's expected schema, e.g. `positive_prompt` for Wan T2V), `comfy_lifecycle: "none"`, and contains NO `workflow_graph` field, NO `comfy_image_param_key` field; after `expand_model_refs`, the resolved `prepared_routes` contains exactly one route with `model="comfy/local-video"`

#### Scenario: examples/comfy_local_smoke.json (image), comfy_local_smoke_mesh.json (mesh), comfy_local_smoke_audio.json (audio) are preserved unchanged

- **GIVEN** the post-change repository tree
- **WHEN** `examples/comfy_local_smoke.json`, `examples/comfy_local_smoke_mesh.json`, `examples/comfy_local_smoke_audio.json` are inspected
- **THEN** all three prior smoke bundles exist unchanged at the same paths; all four bundles coexist and exercise different ComfyAgentWorker capability modes; users selecting between them via `--task examples/comfy_local_smoke.json` (image), `--task examples/comfy_local_smoke_mesh.json` (image-to-mesh), `--task examples/comfy_local_smoke_audio.json` (text-to-audio), or `--task examples/comfy_local_smoke_video.json` (text-to-video) get the corresponding capability path

### Requirement: Live ComfyUI video smoke is gated behind agent-CLI video manifest availability + Wan model weights

The system SHALL document in the bundle's loader-test smoke + in CLAUDE.md (ComfyUI section) that running `examples/comfy_local_smoke_video.json` end-to-end requires:

1. ComfyUI installed under a host-specific path with at least one video workflow manifest available (default: `Vedio/Wan2.1-T2V-1.3B_native_5sec` — Wan 2.1 1.3B T2V with 5-second clip; alternative: `Vedio/Wan2.1-T2V-1.3B_native_teacache` requires TeaCache custom node; `Vedio/Wan2.2-T2V-A14B_GGUF` requires 14+ GB VRAM and longer generation time ≥30 min)
2. `python -m comfyui_api list` output containing the manifest name referenced by the bundle (note: D5 upstream `Vedio/` typo — `list` output uses the same path)
3. `FORGEUE_COMFY_SCRIPTS_DIR` pointing to that ComfyUI's `scripts/` directory; **NO** `FORGEUE_COMFY_INPUT_DIR` env var required (text-to-video has no source bytes path — that env var is mesh-specific)
4. First run: ComfyUI auto-downloads Wan model weights from HuggingFace (Wan 2.1 1.3B ~3 GB; A14B ~14 GB+); subsequent runs use the cache; users SHOULD pre-warm ComfyUI to avoid `worker_timeout_s` exhaustion during first cold start
5. `python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id video_smoke_<timestamp>`

The offline loader-contract test SHALL still pass without any of those preconditions because the loader does not invoke any worker. CLAUDE.md SHALL be updated to reflect the four smoke bundles (image / mesh / audio / video) and to note that video smoke produces a `.mp4` file under `artifacts/<today>/<run_id>/<artifact_id>.mp4` (round-2 F2 + round-3 PF3 sweep:**mp4-only**,webm follow-on `comfy-video-webm-adoption`;the in-tree filename is `<artifact_id>.<format>` via `repo.put` + `file_suffix=f".{cand.format}"` which post-F2 evaluates to `.mp4` only, NOT the original ComfyUI filename — see artifact-contract spec).

#### Scenario: comfy_local_smoke_video.json passes the offline loader-contract fence without a real ComfyUI

- **GIVEN** a CI runner without ComfyUI installed and without `D:/AI/ComfyUI/scripts/`
- **WHEN** `tests/integration/test_example_bundles_smoke.py` loads `examples/comfy_local_smoke_video.json` through `load_task_bundle`
- **THEN** the bundle parses cleanly into a `TaskBundle`, no subprocess is spawned, and the smoke test asserts only loader-level invariants (`comfy_workflow` is a string starting with `"Vedio/"`, `comfy_params` is a dict containing at least one prompt-like key, `video_local` alias resolves to `comfy/local-video`, no `workflow_graph` field, no `comfy_image_param_key` field, `depends_on` is empty); mirrors the existing fence pattern for image / mesh / audio bundles

#### Scenario: Live video smoke L2 evidence file is real video bytes under in-tree artifact path

- **GIVEN** a host with ComfyUI + Wan 2.1 1.3B model weights cached + `FORGEUE_COMFY_SCRIPTS_DIR` configured + `python -m factory_v3 serve` running (ComfyUI pre-warmed)
- **WHEN** the user runs `python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id video_smoke_<timestamp>`
- **THEN** the resulting `artifacts/<today>/video_smoke_<timestamp>/<artifact_id>.mp4` file (round-2 F2 修订:mp4-only;webm follow-on): (1) exists, (2) has size > 1 MB (avoids 0-byte false positives; Wan 1.3B 5sec @ 832x480 typically produces 5-15 MB), (3) BMFF strict header validation (round-2 F4 + **round-3 PF2 修订**): `len(data) >= 16` AND `data[4:8] == b"ftyp"` AND `box_size = int.from_bytes(data[0:4], "big")` is in range `[8, len(data)]` (round-3 PF2:**reject `box_size == 1`** for 64-bit largesize, follow-on `video-bmff-largesize-support`) AND `data[8:12]` major_brand is non-empty / non-zero / non-spaces. The L2 evidence note `notes/live_smoke_video_<date>.md` SHALL record all four objective checks; subjective video quality is left to human spot-check. Frame count / duration / resolution checks are OUT OF SCOPE for this change — design D8 + this spec lock `VideoCandidate.duration_seconds=None / frame_count=None / width=None / height=None / fps=None always` because ComfyUI agent CLI does not expose video metadata; ForgeUE does not introduce ffprobe / mutagen parsing in this change scope; a follow-on `video-metadata-parser` change MAY add the duration / frame_count / resolution checks after introducing a parser dependency

### Requirement: a2_video UE 真机 P4 acceptance via commandlet automation

The system SHALL provide an `a2_video` UE 真机 P4 acceptance path documented in `docs/acceptance/acceptance_report.md` and exercised once on a UE 5.x install (sweep-mirror of `a2_mesh` 2026-04-23 UE 5.7.4 commandlet模式;D15 user决定走 commandlet 自动化,**not** GUI Python Console manual paste). The acceptance SHALL:

- Run `python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id a2_video_<date>` to produce `artifacts/<today>/a2_video_<date>/<artifact_id>.mp4` + matching `manifest.json` / `import_plan.json` / `evidence.json`
- Run `<UE_path>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<repo>/ue_scripts/run_import.py"` with `FORGEUE_RUN_FOLDER` env pointing to the artifact run folder (Bash 直接驱动,Claude 不需要用户手工点 Python Console)
- Verify the resulting UE project tree contains:
  - `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4` — the mp4 source file copied to UE Movies subdirectory (D12 packaging path分流)
  - `<project_root>/Content/Generated/<run_id>/MS_<base>.uasset` — the FileMediaSource `.uasset` asset (NOT mp4-embedded; just a reference)
- Append `evidence.json` with one record per import operation, status `success`
- Documented evidence file: `notes/live_smoke_video_<date>.md` records (a) framework-side `artifacts/.../<artifact_id>.mp4` size + magic bytes check, (b) UE-side `Content/Movies/<run_id>/MS_<base>.mp4` existence + size, (c) UE-side `Content/Generated/<run_id>/MS_<base>.uasset` existence, (d) `unreal.FileMediaSource.cast(asset).get_editor_property("file_path")` resolved value matching the Movies path, (e) `Artifact.metadata.worker_metadata.comfy_capability == "video"` + producer = `comfy_agent_cli` + model = `comfy/local-video` for producer attribution

#### Scenario: a2_video commandlet round-trip produces both `.mp4` source and `.uasset` reference

- **GIVEN** a host with UE 5.x installed (UE 5.7+ recommended), `PythonScriptPlugin` enabled in the target `.uproject`, framework-side `artifacts/<today>/a2_video_<date>/` containing the prior `framework.run` outputs, and `FORGEUE_RUN_FOLDER` env set to that path
- **WHEN** the operator invokes `UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<repo>/ue_scripts/run_import.py"` from a Bash shell
- **THEN** UE 加载 project,执行 `run_import.run()`,for the video entry: `domain_video.import_video_entry` copies the mp4 source to `Content/Movies/<run_id>/MS_<base>.mp4`, then invokes `unreal.FileMediaSourceFactory()` + `unreal.AssetTools.import_assets(...)` to create `Content/Generated/<run_id>/MS_<base>.uasset` whose `file_path` editor property resolves to the Movies path; `evidence.json` gets a `status="success"` record for this operation; the operator visually verifies via UE Editor Content Browser double-click on `MS_<base>.uasset` showing the FileMediaSource asset details panel with the file_path field populated; the `notes/live_smoke_video_<date>.md` evidence file documents all five checks above

### Requirement: subagent-driven-development per-task evidence schema

当用户调用 `/forgeue:change-apply-subagent <id>` 命令时,系统 SHALL 把 Superpowers `subagent-driven-development` skill 派发的每个 subagent return 内容固化为 OpenSpec change 内的 4 类 per-task evidence 文件,采用扁平命名 + frontmatter-indexed `evidence_type` 字段:

| 文件路径 | `evidence_type` | 来源 subagent |
|---|---|---|
| `execution/task_<n>_implementer.md` | `subagent_implementer_report` | implementer subagent return |
| `execution/task_<n>_spec_review.md` | `subagent_spec_review` | spec compliance reviewer return |
| `execution/task_<n>_code_quality_review.md` | `subagent_code_quality_review` | code quality reviewer return |
| `review/subagent_final_review.md` | `subagent_final_review` | final code reviewer return(全 task 完成后) |

`<n>` SHALL 是 `execution/micro_tasks.md` 中 task 的递增编号(从 1 起)。每个文件 SHALL 携带完整的 12-key frontmatter(沿 `Active change evidence is captured under OpenSpec change subdirectories with writeback protocol` Requirement 的全部 frontmatter 约束),包括 `change_id` / `stage` / `evidence_type` / `contract_refs` / `aligned_with_contract` / `drift_decision` / `writeback_commit` / `drift_reason` / `reasoning_notes_anchor` / `detected_env` / `triggered_by` / `codex_plugin_available`。

`stage` 字段 SHALL 为 `S4`(对应实施阶段);通过 review 的 task evidence 允许"frontmatter + 一行 summary"轻量化形态(不强制复制 subagent return 全文),但未通过 review 的 task evidence MUST 包含完整的 issues 列表(`spec_review` 的 missing/extra/misunderstandings + file:line refs;`code_quality_review` 的 Critical/Important/Minor issues)以便后续 implementer 修复参照。

#### Scenario: change-apply-subagent 派发完成后 4 类 evidence 落盘且 frontmatter 完整

- GIVEN 一个 active OpenSpec change `<change-id>`,其 `execution/micro_tasks.md` 含 3 个 micro-task,用户调用 `/forgeue:change-apply-subagent <change-id>`
- WHEN 主 session Claude 完成 Superpowers `subagent-driven-development` skill 派发流程,3 个 task 全部 implementer return DONE + spec_review ✅ + code_quality_review ✅
- THEN `openspec/changes/<change-id>/execution/` 下产生 9 个文件 `task_1_implementer.md` / `task_1_spec_review.md` / `task_1_code_quality_review.md` / `task_2_*` / `task_3_*`,`openspec/changes/<change-id>/review/` 下产生 1 个文件 `subagent_final_review.md`,所有 10 个文件携带完整 12-key frontmatter,`evidence_type` 字段分别为 `subagent_implementer_report` / `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review`,`stage` 字段全部为 `S4`,`change_id` 全部为 `<change-id>`

#### Scenario: spec_review 发现 missing requirement 时 evidence 包含完整 issues 列表

- GIVEN 一个 active change,task 5 的 implementer subagent return DONE,但 spec compliance reviewer 发现 implementer 漏建造一个 requirement
- WHEN 主 session Claude 把 spec_review return 落盘为 `execution/task_5_spec_review.md`
- THEN 该 evidence 文件 body 包含完整的 `❌ Issues found` 段,列出 missing requirement 名称 + file:line refs;不允许只写"frontmatter + ❌ summary"轻量化形态(因为 implementer 后续修复需要参照该 issues 列表);frontmatter `evidence_type: subagent_spec_review`

### Requirement: change-apply-subagent 命令直接 invoke Superpowers skill

`/forgeue:change-apply-subagent` 命令 SHALL 直接 invoke `superpowers:subagent-driven-development` skill,不重写 / 不分叉 / 不复制 skill 内部的 3 个 prompt 模板(`implementer-prompt.md` / `spec-reviewer-prompt.md` / `code-quality-reviewer-prompt.md`)。ForgeUE 命令文件 SHALL NOT 在自身内容中引用、嵌入或镜像这些 prompt 模板的文本。

主 session Claude 在 invoke skill 之前 SHALL 从 `openspec/changes/<id>/execution/micro_tasks.md` extract task list,从 `openspec/changes/<id>/execution/execution_plan.md` 提取 per-task context,**完整文本作为 prompt 内容传给 implementer subagent**(沿 `subagent-driven-development/SKILL.md` Red Flag "Make subagent read plan file (provide full text instead)")。subagent SHALL NOT 被授权读 `micro_tasks.md` / `execution_plan.md` 等 plan 文件。

#### Scenario: change-apply-subagent.md 命令文件不包含 implementer-prompt 文本副本

- GIVEN `.claude/commands/forgeue/change-apply-subagent.md` 命令文件
- WHEN 用 `grep -F "You are implementing Task" .claude/commands/forgeue/change-apply-subagent.md` 或类似命令搜索 implementer-prompt 模板的标志性短语
- THEN 命令文件中 SHALL NOT 出现该短语(因为 ForgeUE 不复制 / 不重写 Superpowers skill 内部 prompt);命令文件 SHALL 仅在 step 描述中说明"invoke `superpowers:subagent-driven-development` skill",并在后续 step 描述 evidence 收口协议

#### Scenario: subagent prompt 包含完整 task 文本而非文件路径引用

- GIVEN 一个 active change `<change-id>`,主 session Claude 准备派发 task 1 的 implementer subagent
- WHEN 主 session Claude 构造 Task tool 的 prompt 参数
- THEN prompt 字符串内容 SHALL 包含 `execution/micro_tasks.md` 中 task 1 的完整文本 + `execution/execution_plan.md` 中对应 task 1 的 context 段完整文本;prompt SHALL NOT 含有 `请读 openspec/changes/<id>/execution/micro_tasks.md` 这类引用 plan 文件路径的指令(沿 SKILL.md Red Flag);subagent 收到 prompt 后无需访问 plan 文件即可独立完成 task

### Requirement: subagent token-budget tracker 是 informational 不是 enforcement

系统 SHALL 提供 `tools/forgeue_subagent_budget.py` 工具用于追踪 `/forgeue:change-apply-subagent` 命令派发的 LLM token 消耗。该工具的所有 CLI 子命令(`--status` / `--record` / `--json`)始终以 `exit 0` 返回(I/O 异常返回 `exit 1` 例外),**不对 dispatch 流程做 hard gate / abort / auto fallback**。

当累积消耗超过 `FORGEUE_SUBAGENT_BUDGET_WARN_USD`(default `2.0` USD,可通过环境变量 override)阈值时,工具 SHALL 在 stdout 输出 `[WARN] budget exceeded: $<X.XX> of $<Y.YY> (<Z>%)` 形式的警告行;但 `change-apply-subagent` 命令流程 SHALL 继续 dispatch,由用户根据 WARN 自行决定是否中断切换到 `/forgeue:change-apply-direct` 兜底路径。

`/forgeue:change-apply-subagent` 命令 SHALL 在每次派发 implementer / spec_reviewer / code_quality_reviewer subagent 之后调用 `python tools/forgeue_subagent_budget.py --change <id> --record ...` 把该次 dispatch 的 token 消耗追加到 `verification/subagent_budget.log`(JSON Lines 格式)。

#### Scenario: budget warn 阈值超出后 dispatch 继续不被阻断

- GIVEN 用户在调 `/forgeue:change-apply-subagent <change-id>`,环境变量 `FORGEUE_SUBAGENT_BUDGET_WARN_USD=1.0`,前 5 个 task 已累积消耗 1.20 USD
- WHEN 主 session Claude 调用 `python tools/forgeue_subagent_budget.py --change <change-id> --status` 在 task 6 dispatch 之前
- THEN 工具 stdout 输出 `[WARN] budget exceeded: $1.20 of $1.00 (120%)` 警告行,`exit 0`;主 session Claude 继续 dispatch task 6 的 implementer subagent(命令流程不因 WARN 中断);`change-apply-subagent` 命令 step 流程 SHALL 不调用任何 abort / fallback 分支;用户在阅读控制台输出时看到 WARN 警告,可手工 Ctrl-C 中止后切换到 `/forgeue:change-apply-direct`(用户判断,不是工具自动)

#### Scenario: budget tracker 与 ADR-007 vendor API 双扣边界根本不同

- GIVEN ADR-007 在 `docs/requirements/SRS.md` 约束 framework 不得对 mesh.generation 等 vendor 外部 API 做静默重试,因为重试会双扣已完成 job
- WHEN 把 LLM token 消耗(persist value-producing,不会双扣)纳入考虑
- THEN ADR-009 在 `docs/requirements/SRS.md` SHALL 显式声明 token-budget tracker 与 ADR-007 是不同的安全边界:ADR-007 拦截 "重试时双扣已完成 job"(浪费),ADR-009 budget tracker 仅记录 "持续产生价值的 token 消耗"(打断 = 损失);框架 SHALL NOT 对 token cost 做 hard gate;ADR-009 描述 SHALL 包含与 ADR-007 的对比段说明边界不同

### Requirement: Codex review default background dispatch policy

`/codex:review` 与 `/codex:adversarial-review` 命令模板 SHALL default 到 background 模式分发,仅当**全部三个条件同时满足**时才走前台 wait 路径:

- 变更范围 ≤ 2 files **且** 总 diff ≤ 50 lines(`git diff --shortstat` / `git diff --shortstat --cached` 实测)
- 调用模式非 `adversarial-review`(adversarial 永远 background)
- main session 下一动作必须依赖 review 结果(由 controller 显式判断)

命令模板 SHALL 保留 `--wait` / `--background` 显式 flag 作为用户 override 通道,显式 flag 优先于 size estimation。

#### Scenario: 大 scope 变更默认走 background

- **WHEN** 用户 invoke `/codex:review` 且当前 working tree `git diff --shortstat` 显示 ≥ 3 files 或 ≥ 51 lines
- **THEN** 命令直接走 background 路径(`Bash(..., run_in_background: true)`),不弹 `AskUserQuestion`
- **AND** main session 在下一次需要 codex 输出前 SHALL 主动 BashOutput 拉结果

#### Scenario: 极小 scope 变更走前台 wait

- **WHEN** 用户 invoke `/codex:review` 且 working tree ≤ 2 files **且** ≤ 50 lines diff **且** 非 adversarial-review **且** controller 判定下一动作必须等结果
- **THEN** 命令走前台 wait 路径,foreground node 调用 codex-companion.mjs
- **AND** 不弹 `AskUserQuestion` 二选一

#### Scenario: adversarial-review 永远 background

- **WHEN** 用户 invoke `/codex:adversarial-review`(无论 scope 大小)
- **THEN** 命令走 background 路径
- **AND** 不弹 `AskUserQuestion`

#### Scenario: 显式 flag override

- **WHEN** 用户 invoke `/codex:review --wait`(显式要求前台)
- **THEN** 命令走前台 wait,忽略 size estimation 默认
- **AND** 不弹 `AskUserQuestion`

#### Scenario: background launch 必须 capture job id(W4 writeback codex round 1 F4 finding)

- **WHEN** 命令走 background 路径(D-DefaultBackground default 或 `--background` 显式)
- **THEN** job id SHALL 从 codex-companion.mjs stdout 第一行 `Codex review started in the background. Job id: <id>` 解析并写入 `notes/<review_type>_active_jobs.txt`(per change_id)
- **AND** 命令模板告知 main session "Run `/codex:status --wait <job>` and `/codex:result <job>` to consume verdict"

#### Scenario: 未获取 codex result 不得写 concurred evidence(W4 writeback)

- **WHEN** Claude 计划在 evidence frontmatter 写 `autonomy_decision: claude_codex_concurred` + `codex_review_ref: <path>`
- **THEN** controller MUST 先 `/codex:status --wait <job>` 确认 job done **且** `/codex:result <job>` 拿完整 output 落 evidence
- **AND** 若 ref evidence 未 finalize(round counter 未 increment / `disputed_open != 0` / `verdict` 字段缺)→ MUST 改为 `autonomy_decision: user_required` 升级到用户

#### Scenario: 命令模板移除 "Do not call BashOutput" 矛盾文本(W4 writeback)

- **WHEN** 静态扫 `.claude/commands/codex/{review,adversarial-review}.md`
- **THEN** **不**含字符串 `Do not call BashOutput or wait for completion in this turn.`(原 plugin upstream text,与 default background 协议冲突)
- **AND** 含字符串 `Main session MUST poll job before consuming verdict via /codex:status --wait + /codex:result.`(替换文本)

### Requirement: Codex multi-round review same-subject context bridge

Codex 同 `change_id` + 同 `review_type` 的多轮 review 中,round N+1 (N≥1) prompt SHALL 自动注入对 round N evidence 文件的 read 引用,使 codex 在 review 前理解上轮 verdict。**仅 same-task / same-change scope 共享上下文**,跨 task / 跨 change 绝不共享。

实装路径:
- Round 1 codex review 输出 SHALL 落 `openspec/changes/<change_id>/notes/codex_<review_type>_review_round1.md`
- Round 2+ codex review prompt SHALL 包含 fence:`本次 review 是 round {N+1}(继承 round {N} verdict)。**强制要求**:开始 review 前 MUST 先读 openspec/changes/<change_id>/notes/codex_<review_type>_review_round{N}.md`
- Round counter 状态 SHALL 落 `notes/codex_<review_type>_round_counter.txt`(每个 review subject 一份,sticky)

约束:
- Round 1 不引用任何上轮(无前置)
- Round N+1 仅引用直接前驱 round N(不引用 round N-1 / N-2)
- 跨 `change_id` 不共享(change A round 1 verdict 不进 change B 任何 round)
- 跨 `review_type` 不共享(同 change 内 design_review round 1 verdict 不进 plan_review round 1)

#### Scenario: round 1 review 不注入任何上轮 reference

- **WHEN** 用户 invoke `/codex:review` 且 `notes/codex_<review_type>_round_counter.txt` 不存在或读出 0
- **THEN** prompt 不包含 round-bridge fence
- **AND** round counter 写入 1
- **AND** codex output 落 `notes/codex_<review_type>_review_round1.md`

#### Scenario: round 2 review 自动注入 round 1 reference

- **WHEN** 用户 invoke `/codex:review` 且同 change_id + 同 review_type 的 round counter 读出 1
- **THEN** prompt 首段包含 fence:`本次 review 是 round 2(继承 round 1 verdict)。**强制要求**:开始 review 前 MUST 先读 openspec/changes/<change_id>/notes/codex_<review_type>_review_round1.md`
- **AND** round counter 增到 2
- **AND** codex output 落 `notes/codex_<review_type>_review_round2.md`

#### Scenario: 跨 change 不共享上下文

- **WHEN** change A 完成 round 1 review 落 `notes/codex_<type>_review_round1.md` + counter=1,然后用户在 change B 第一次 invoke `/codex:review`
- **THEN** change B prompt 不包含 change A round 1 reference
- **AND** change B counter 从 1 起记(独立)
- **AND** change A counter 文件不被 change B 修改

#### Scenario: bridge violation 检测

- **WHEN** round 2 codex output 中 raise 与 round 1 已 accepted finding 重叠的问题但无 `(承 round1-FN)` tag
- **THEN** controller SHALL 在 evidence frontmatter 标注 `bridge_violation: true`
- **AND** controller 评估是否 retry round 2 或升级 D-AutonomyBoundary fence #3(review 冲突)

### Requirement: Workflow autonomy boundary fence

ForgeUE Integrated AI Change Workflow controller(Claude main session) SHALL 默认走自主路径执行 routine workflow step。**仅 6 类 boundary 触发时** MUST 升级到用户拍板(2026-05-05 user feedback simplification — 原 fence #3 "Claude+Codex review 冲突" 已**删除**;Claude 独立 verify codex finding 后自主拍板,不再升级用户作中间裁判):

1. **不可逆操作** — `git push` / `git push --force` / archive change(`mv openspec/changes/<id> archive/`)/ `git reset --hard` / `git branch -D` / 删除非 `/tmp/` 临时文件 / `git commit --amend` 已 push 的 commit
2. **跨 change 决策** — 修改非本 change scope 的 D-decision / 修改其他 active change 的 contract artifact / 删除其他 change 的 evidence 文件
3. **框架修改(framework modification)** — 修改 D-decision content / fence taxonomy / autonomy 协议自身 / Superpowers 集成边界 / codex 集成边界 / S0-S9 状态机定义
4. **design.md 不匹配(design.md mismatch)** — 实施暴露的 contract 漏洞与 design.md text 矛盾(原 4 类 DRIFT 中的 `evidence_contradicts_contract` / `evidence_introduces_decision_not_in_contract` / `evidence_exposes_contract_gap` 类)
5. **钱** — 任何 vendor API paid call(ADR-007 边界:Hunyuan3D / Tripo3D / 远端付费 LLM live 调用 / `--live-llm` flag dispatch)
6. **Secret / 安全** — `.env` 写入 / `*api_key*` / `*credential*` / `*secret*` 文件操作 / mock production credentials 写文件系统

(原 fence "用户先验显式约束" 隐含到 memory read 行为 — Claude controller 每 step 主动 read `MEMORY.md` / `<feedback>` saved memory + 遵守;不作为独立 fence trigger,但效果等价)

每条 implementation evidence frontmatter MUST 含 `autonomy_decision` 字段,枚举(2026-05-05 简化):
- `claude_autonomous` — **default**(routine step / Claude 独立 verify codex finding 后拍板)
- `claude_codex_concurred` — 显式 codex 二次验证 + 一致(可选 verify path,不强制;若用 MUST 配 `codex_review_ref`)
- `user_required` — 6 类 fence 触发(不可逆 / 跨 change / framework / design mismatch / 钱 / 安全)
- `user_overrode` — 用户主动否决 Claude 推荐

`autonomy_decision: claude_codex_concurred` 字段值 MUST 配套 `codex_review_ref` 字段(指向具体 round N evidence 文件)。`autonomy_decision: claude_autonomous`(default 路径)**不强制** `codex_review_ref` 字段。

`forgeue_finish_gate.py` SHALL 含 `_check_autonomy_boundary` fence 守门 implementation evidence frontmatter `autonomy_decision` 字段必填且值合法(scope 限定 implementation evidence 类型,不强制 verify_report / doc_sync_report / superpowers_review / codex review 类输出 evidence)。

#### Scenario: routine step Claude 自主执行(default 路径)

- **WHEN** Claude 提案修改 evidence file 是 routine step(无 framework 修改 / design.md mismatch / 不可逆 / 钱 / 安全 触发)
- **THEN** Claude 直接执行修改不弹 `AskUserQuestion`,**不强制** invoke codex review
- **AND** evidence frontmatter 写入 `autonomy_decision: claude_autonomous`(不强制 `codex_review_ref`)

#### Scenario: 显式 codex 二次验证后自主执行(可选 path)

- **WHEN** Claude 显式 invoke `/codex:review` background 作为 second opinion + 解析 codex output + Claude 独立 verify finding 后自主决策
- **THEN** evidence frontmatter 写入 `autonomy_decision: claude_codex_concurred` + `codex_review_ref: notes/<review_type>_round_N.md`
- **AND** **不**因 codex verdict 与 Claude 不同而升级用户(Claude 自主 verify + 自主拍板)

#### Scenario: 不可逆操作必须用户授权

- **WHEN** Claude 计划走 `git push origin dev` / `archive change` / `git reset --hard`
- **THEN** Claude MUST 先用 `AskUserQuestion` 请求授权
- **AND** evidence frontmatter 标 `autonomy_decision: user_required`

#### Scenario: 框架修改必须用户授权(简化协议新 fence)

- **WHEN** Claude 计划修改 D-decision content / fence taxonomy / autonomy 协议 / Superpowers 集成边界 / codex 集成边界 / S0-S9 状态机定义
- **THEN** Claude MUST 用 `AskUserQuestion` 列出修改 scope + 影响范围 + 推荐方案
- **AND** evidence frontmatter 标 `autonomy_decision: user_required`

#### Scenario: design.md mismatch 必须用户授权(简化协议新 fence)

- **WHEN** Claude 实施暴露的 contract 漏洞与 design.md text 矛盾(原 4 类 DRIFT 子集:`contradicts_contract` / `introduces_decision_not_in_contract` / `exposes_contract_gap`)
- **THEN** Claude MUST 用 `AskUserQuestion` 列出 mismatch 内容 + 推荐 reconcile path(改 design or 改 implementation)
- **AND** evidence frontmatter 标 `autonomy_decision: user_required` + `drift_decision: <type>`

#### Scenario: vendor API paid call 必须用户授权

- **WHEN** Claude 计划走 `--live-llm` 启 mesh.generation / Hunyuan3D / Tripo3D / 任何 vendor API paid call
- **THEN** Claude MUST 用 `AskUserQuestion` 列出预估 cost + provider + 失败回退
- **AND** evidence frontmatter 标 `autonomy_decision: user_required`

#### Scenario: secret 文件操作必须用户授权

- **WHEN** Claude 计划写入 `.env` / `*api_key*` / `*credential*` / `*secret*` 类文件
- **THEN** Claude MUST 用 `AskUserQuestion` 请求授权(包括 read-and-update)
- **AND** evidence frontmatter 标 `autonomy_decision: user_required`

#### Scenario: finish_gate 守门 autonomy_decision 字段(implementation evidence 限定)

- **WHEN** `forgeue_finish_gate.py` 扫描 `execution/` / `review/` / `verification/` 内 evidence frontmatter
- **THEN** **implementation evidence 类型**(`subagent_implementer_report` / `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review` / `tdd_log` / `debug_log`)缺 `autonomy_decision` 字段 → exit 非 0 + 错误指明缺字段的 evidence 文件
- **AND** non-implementation evidence(`verify_report` / `doc_sync_report` / `finish_gate_report` / `superpowers_review` / `codex_*_review` / `*_cross_check`)**不强制** `autonomy_decision` 字段(F7 spec/impl reconciliation;沿 design.md D-AutonomyBoundary "implementation evidence" 限定)
- **AND** `autonomy_decision: claude_codex_concurred` 缺 `codex_review_ref` → exit 非 0
- **AND** `autonomy_decision` 值不在合法枚举内 → exit 非 0
- **AND** `claude_codex_concurred` 配套 `codex_review_ref` 路径不存在(`(change_root / codex_review_ref).is_file() == False`)→ exit 非 0
- **AND** `codex_review_ref` 跨 change(不在当前 change_root 下,如 ref `archive/<other>/notes/...`)→ exit 非 0
- **AND** `codex_review_ref` 自身 frontmatter `evidence_type` 不在 `{codex_adversarial_review, codex_design_review, codex_plan_review, codex_verification_review, codex_mixed_scope_review}` 之一 → exit 非 0
- **AND** `codex_review_ref` 自身 frontmatter `disputed_open != 0`(round 未 finalize)→ exit 非 0

#### Scenario: verdict normalization 判定 conflict(W3 writeback codex round 1 F3 finding)

- **WHEN** controller 准备写 `autonomy_decision: claude_codex_concurred` evidence,先调用 `_check_verdict_normalization(claude_resolution_list, codex_top_verdict, codex_findings)` helper
- **THEN** 按 design.md `D-FenceTaxonomy` Fence #3 Verdict Normalization 8 row 表 + 2 个 per-finding 维度判定 conflict
- **AND** 不冲突路径(`approve` × `accepted-codex` / `approve` × `accepted-claude` / `approve` × `rejected` / `needs-attention` × `accepted-codex`)→ 自主路径,写 `claude_codex_concurred`
- **AND** 冲突路径(`approve` × `disputed-open` / `needs-attention` × `accepted-claude` / `needs-attention` × `rejected` / `needs-attention` × `disputed-open` / 任何 finding `severity ∈ {critical, high}` × Claude `rejected` / writeback diff 与 codex 推荐方向相反)→ 升级 fence #3 用户,写 `user_required`

### Requirement: Preflight Worktree runtime enforcement

`/forgeue:change-apply-{subagent,parallel}` 两个命令模板 SHALL 在 step 1 含 `## Preflight Worktree` section,且 SHALL **MUST invoke** `Skill(superpowers:using-git-worktrees)`(沿 Superpowers upstream `subagent-driven-development/SKILL.md` `## Integration` 段声明的 Required cascade — 不允许只放字符串占位)。Step 0 consent gate outcome 必须显式记录到 evidence frontmatter。

**Default 行为(D-RestoreConsentGate;ADR-013)**:user 在 Step 0 consent gate decline → work in main repo cwd(`worktree_consent_outcome: declined` + `worktree_mode: in_place`);bug-fix iteration / explicit isolation 需要时 user 在 Step 0 同意 → worktree 创建(`worktree_consent_outcome: accepted` + `worktree_mode ∈ {skill_worktree, wrapper_worktree}`)。

**Opt-in tool**:`tools/forgeue_preflight_wrapper.py`(W1 wrapper)留 deprecated 但 functional;user 显式 invoke 时 wrapper 自管 worktree + 13-field receipt JSON(`worktree_mode: wrapper_worktree`);命令模板**不再 mandatory invoke**(改 OPT-IN 引用)。

`/forgeue:change-apply-direct` **沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项不强制** Preflight Worktree(direct 路径定位 < 3 micro-task / budget 紧张的轻量 fallback;archived 决策保留)。

**Outcome / Mode 显式状态机**(D-ConsentOutcomeStateMachine;codex round 1 F2+F3 writeback):

| `worktree_consent_outcome` | 必配 `worktree_mode` | `worktree_path` | `worktree_receipt_path` | parallel-route allowed? |
|---|---|---|---|---|
| `declined` | `in_place`(强制) | **禁写** | absent | NO(自动降级 sequential)|
| `accepted` | `skill_worktree` | required + path exists | absent | YES |
| `accepted` | `wrapper_worktree` | required + path exists | required + JSON valid + receipt path matches | YES |
| `already_isolated` | `skill_worktree` 或 `wrapper_worktree`(**必须** isolated workspace mode;codex round 2 plan review F2 writeback) | required + path exists + path != main repo root | mode-conditional | YES |
| `sandbox_fallback` | `in_place` | **禁写** | absent | NO(自动降级 sequential)|

**`already_isolated` 强 invariant**(W6 / codex round 2 plan review F2 writeback;关闭 already_isolated → in_place 绕过 parallel decline auto-fallback 漏洞):

- `worktree_consent_outcome: already_isolated` MUST 配 `worktree_mode ∈ {skill_worktree, wrapper_worktree}`(**禁** `in_place`)
- `worktree_path` MUST 写 + path exists + `os.path.realpath(worktree_path) != os.path.realpath(main_repo_root)`(防 controller 写 `worktree_path: <main_repo>` 假声 isolated)
- 任一违反 → `_check_worktree_consent_outcome` Blocker
- `parallel` Step 0 决策表对 `already_isolated` 仅在以上 invariant 全满足时允许 parallel 路径;违反 → 自动降级 sequential(同 declined 处理)

实装路径:

- 命令模板首段 MUST 显式声明 "MUST invoke `Skill(superpowers:using-git-worktrees)`;Step 0 consent outcome capture to evidence frontmatter;default outcome = declined → work in place;opt-in outcome = accepted → worktree creation"
- evidence frontmatter 必填字段(`triggered_by_command ∈ {change-apply-subagent, change-apply-parallel}`):
  - `worktree_consent_outcome: <enum>`
  - `worktree_mode: <enum>`
- evidence frontmatter conditional 字段:`worktree_path` / `worktree_receipt_path` 按 outcome × mode 表填
- `forgeue_finish_gate.py` 加 2 新 fence:
  - `_check_worktree_consent_outcome`:enum value validate + outcome ↔ mode invariant
  - `_check_worktree_mode_consistency`:mode 决定 worktree_path / worktree_receipt_path 是否必填 / 禁写
- 既有 fence 升级:
  - `_check_worktree_path` v1 / `_check_worktree_path_v2` 入口加 `worktree_consent_outcome` field present check;legacy archived evidence(不含本字段)→ pass-through(沿 D-AdvisoryFenceMode 兼容意图);本 change 自身及后续 evidence 必填字段 → mode-conditional validate

**Supersedes**:archived `enhance-workflow-automation-runtime-enforcement` D-WorktreeEnforce(L2 mandatory)+ archived `enhance-workflow-automation-executable-enforcement` D-W1-ReceiptSchema mandatory invocation 部分。Cross-archive ADR table:SRS ADR-011 + ADR-012 加 `Superseded by ADR-013 (worktree mandatory parts)`。

#### Scenario: change-apply-subagent 命令模板 MUST invoke Skill + outcome capture

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-subagent.md`
- **THEN** 文件内含 `## Preflight Worktree` section(精确匹配)
- **AND** section 内含 `MUST invoke Skill(superpowers:using-git-worktrees)` 字符串(沿 Required cascade,且写明 MUST 而非 MAY)
- **AND** section 内含 `worktree_consent_outcome` 字段提示(显式 outcome capture)
- **AND** section 内含 "default decline" 或 "opt-in" 字符串(显式声明 default 行为)

#### Scenario: change-apply-parallel 命令模板 MUST invoke Skill + outcome capture + decline auto-fallback

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-parallel.md`
- **THEN** 文件内含 `## Preflight Worktree` section
- **AND** section 内含 `MUST invoke Skill(superpowers:using-git-worktrees)` 字符串
- **AND** section 内含 `worktree_consent_outcome` 字段提示
- **AND** section 内含 "decline" → "auto-fallback" / "降级 sequential" 字符串(沿 D-ParallelDeclineFallback)

#### Scenario: change-apply-direct 沿 archived 第 5 项不强制 Preflight Worktree

- **WHEN** 静态扫 `.claude/commands/forgeue/change-apply-direct.md`
- **THEN** 文件不需要含 `## Preflight Worktree` section(沿 archived 2026-05-04-adopt-subagent-driven-development D-Worktree-Detail 第 5 项)

#### Scenario: implementation evidence outcome=declined + mode=in_place

- **WHEN** evidence frontmatter `worktree_consent_outcome: declined` + `worktree_mode: in_place`
- **THEN** `_check_worktree_consent_outcome` fence 通过(invariant:declined ↔ in_place)
- **AND** evidence 不含 `worktree_path` 字段(in_place 禁写)
- **AND** `_check_worktree_path` v1 / v2 fence pass-through

#### Scenario: implementation evidence outcome=accepted + mode=skill_worktree

- **WHEN** evidence frontmatter `worktree_consent_outcome: accepted` + `worktree_mode: skill_worktree` + `worktree_path: <abs_path>`
- **THEN** `_check_worktree_consent_outcome` 通过(accepted → skill_worktree 或 wrapper_worktree)
- **AND** `_check_worktree_path` v1 fence validate path 存在
- **AND** evidence 不含 `worktree_receipt_path`(skill_worktree mode 不要求 receipt)

#### Scenario: implementation evidence outcome=accepted + mode=wrapper_worktree

- **WHEN** evidence frontmatter `worktree_consent_outcome: accepted` + `worktree_mode: wrapper_worktree` + `worktree_path: <abs_path>` + `worktree_receipt_path: <relative_path>`
- **THEN** `_check_worktree_path` v1 + `_check_worktree_path_v2` 全 validate(path 存在 + receipt JSON 解析 + receipt `worktree_path` == evidence `worktree_path` + receipt `is_isolated_worktree: true`)
- **AND** 任一不一致 → Blocker(写了就要真)

#### Scenario: implementation evidence outcome=accepted + mode=in_place 阻断(不一致)

- **WHEN** evidence frontmatter `worktree_consent_outcome: accepted` + `worktree_mode: in_place`
- **THEN** `_check_worktree_consent_outcome` exit 非 0(违 invariant:accepted → mode ∈ {skill_worktree, wrapper_worktree})
- **AND** 错误指明 outcome / mode 矛盾

#### Scenario: implementation evidence mode=in_place 写 worktree_path 阻断

- **WHEN** evidence frontmatter `worktree_mode: in_place` + `worktree_path: <any>`
- **THEN** `_check_worktree_mode_consistency` exit 非 0(in_place mode 禁写 worktree_path,关闭 F2 双歧义漏洞)

#### Scenario: implementation evidence mode=wrapper_worktree 缺 receipt 阻断

- **WHEN** evidence frontmatter `worktree_mode: wrapper_worktree` + `worktree_path: <abs>` + 缺 `worktree_receipt_path`
- **THEN** `_check_worktree_mode_consistency` exit 非 0(wrapper_worktree 必配 receipt;关闭 F2 receipt provenance 漏洞)

#### Scenario: legacy archived evidence 不含 worktree_consent_outcome → pass-through

- **WHEN** archived `enhance-workflow-automation-runtime-enforcement` 或 `enhance-workflow-automation-executable-enforcement` evidence 替换 / replay 时(不含 `worktree_consent_outcome` 字段)
- **THEN** `_check_worktree_consent_outcome` + `_check_worktree_mode_consistency` 入口 field-present check → pass-through(legacy 兼容)
- **AND** `_check_worktree_path` v1 / v2 沿 archived 行为(写了字段就 validate)

#### Scenario: implementation evidence already_isolated + in_place 阻断(W6 codex round 2 F2)

- **WHEN** evidence frontmatter `worktree_consent_outcome: already_isolated` + `worktree_mode: in_place`
- **THEN** `_check_worktree_consent_outcome` exit 非 0(违 invariant:already_isolated 必须 mode ∈ {skill_worktree, wrapper_worktree})
- **AND** 错误指明 already_isolated 不允许 in_place(消除"已隔离 + main repo cwd 重新打开 F1 attribution"漏洞)

#### Scenario: implementation evidence already_isolated + worktree_path == main repo 阻断(W6 codex round 2 F2)

- **WHEN** evidence frontmatter `worktree_consent_outcome: already_isolated` + `worktree_mode: skill_worktree` + `worktree_path: <main_repo_root>`(controller 写假声 isolated)
- **THEN** `_check_worktree_consent_outcome` exit 非 0(违 invariant:`os.path.realpath(worktree_path) != os.path.realpath(main_repo_root)`)
- **AND** 错误指明 worktree_path 不能等于 main repo root

#### Scenario: parallel + already_isolated valid 路径走 parallel(W6)

- **WHEN** controller invoke `/forgeue:change-apply-parallel` + `worktree_consent_outcome: already_isolated` + `worktree_mode: skill_worktree` + `worktree_path` 写且 != main repo
- **THEN** parallel 路径正常跑(W6 invariant 守门通过)
- **AND** W2 actual diff 收集 in 各自 implementer workspace

#### Scenario: opt-in W1 wrapper 仍 functional(含 worktree-internal call 路径;W7-a)

- **WHEN** user 显式 `python tools/forgeue_preflight_wrapper.py --change <id>` 调用(无论 cwd 在 main repo 还是已存在 wrapper-managed worktree 内)
- **THEN** wrapper 行为(沿 archived `enhance-workflow-automation-executable-enforcement` D-W1-ReceiptSchema + 本 change W7-a bug fix):
  - 用 `git rev-parse --git-common-dir` 推断 main repo root(**不**用 `--show-toplevel`,避免 worktree 内调用返 worktree 自身造成 nested target);main / worktree 两种调用上下文返同一 main repo
  - 自管 worktree(`git worktree add` from main repo;already exists → reuse)+ 13-field receipt JSON + cwd realpath 校验
- **AND** wrapper `--help` 含 `[DEPRECATED in default flow]` deprecation notice
- **AND** regression test:`tests/unit/test_preflight_wrapper.py::test_git_repo_root_from_inside_worktree_returns_main_repo` + `test_wrapper_reuse_path_works_when_invoked_from_existing_worktree`(W7-a fence)

### Requirement: Implementation parallel dispatch via `/forgeue:change-apply-parallel`

ForgeUE Integrated AI Change Workflow SHALL 提供独立命令 `/forgeue:change-apply-parallel`,invoke `superpowers:dispatching-parallel-agents` SKILL,作为 multi-task implementation 的并行 dispatch 路径。Controller 显式判定 task 独立性(无 shared state / 无 sequential dependency / 无 file scope 交叉)后 route 到此命令。

`/forgeue:change-apply-subagent` 命令保留默认 sequential(`subagent-driven-development` SKILL),不内嵌自动 task independence routing(避免 LLM 误判 race condition)。

evidence frontmatter MUST 含 `task_independence_assertion` 字段(`true` / `false`),表示 controller 是否声明 task 独立。`true` 时配套 `task_files_disjoint: <list of file path sets>` 字段(controller declaration),parallel dispatch 前自动 verify 文件 set 不交。

**v2 升级(archived `enhance-workflow-automation-executable-enforcement`,F4 round 1 + F3 round 2 codex inline writeback)**:dispatch 后主 session 自动在每个 implementer 跑 `git diff --name-only -z <base_sha>..HEAD` + `git ls-files --others --exclude-standard -z` 合集收集 actual changed-files set;先 `git status --porcelain=v1` precondition fail-closed 校验 implementer worktree clean(若 dirty → 自动降级 sequential)。任意两 implementer actual set 交集非空 → 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt);evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected` 或 `dirty_implementer_worktree`。

**ADR-013 update**(D-ParallelDeclineFallback;codex round 1 F1 writeback + codex round 2 F2 writeback):`/forgeue:change-apply-parallel` Step 0 outcome 决策表:

- `worktree_consent_outcome: declined` → 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt;沿 R-no-continue-prompts);evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: parallel_requires_isolated_workspace` + `worktree_consent_outcome: declined` + `worktree_mode: in_place`。**main repo + multi-implementer + W2 路径 SHALL NOT 走**(F1 attribution 漏洞:多 implementer 同 working tree git state 全局污染)。
- `worktree_consent_outcome: accepted` + `worktree_mode ∈ {skill_worktree, wrapper_worktree}` → parallel 路径正常跑 + W2 actual diff 收集 in 各自 worktree(沿 archived ADR-012 `task_files_actual` 含 `implementer_agent_id` + `files`)
- `worktree_consent_outcome: already_isolated` + `worktree_mode ∈ {skill_worktree, wrapper_worktree}` + `worktree_path` 写且 != main repo → parallel 路径正常跑(W6 codex round 2 F2 writeback:已 enforce isolated workspace invariant;不再绕过 F1 attribution 守门)
- `worktree_consent_outcome: already_isolated` + `worktree_mode: in_place` → **invalid**;`_check_worktree_consent_outcome` Blocker(消除 W6 codex round 2 F2 揭示的"已隔离 + main repo cwd 重新打开 F1"漏洞);**自动降级 sequential**(同 declined 处理)
- `worktree_consent_outcome: sandbox_fallback` → 警告 + 降级 sequential(sandbox 与 parallel 不兼容)

#### Scenario: controller 显式声明 task 独立 + parallel dispatch

- **WHEN** controller 准备 dispatch 多 task 且判定 task 独立
- **THEN** controller MUST invoke `/forgeue:change-apply-parallel` 而不是 `change-apply-subagent`
- **AND** evidence frontmatter `task_independence_assertion: true` + `task_files_disjoint: [<file-set-1>, <file-set-2>, ...]`(declaration)
- **AND** parallel dispatch 前 wrapper 自动 verify declared file sets 不交,任意交集 → 命令 abort

#### Scenario: file scope 交叉(declared)dispatch 前 abort

- **WHEN** controller invoke `/forgeue:change-apply-parallel` 但 declared task file sets 实际有交集
- **THEN** 命令在 dispatch 前自动 abort + 错误提示 "task A and task B have overlapping files: <files>"
- **AND** controller MUST 改 task 划分 OR 切换到 `/forgeue:change-apply-subagent` sequential

#### Scenario: actual file overlap detected dispatch 后自动降级 sequential(v2)

- **WHEN** declared file sets disjoint 通过初检 + dispatch 后实际 git diff 发现 implementer 间 file overlap
- **THEN** 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt)
- **AND** evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected`

#### Scenario: 默认 sequential 路径不变

- **WHEN** controller invoke `/forgeue:change-apply-subagent`
- **THEN** 命令路由 `subagent-driven-development` SKILL,sequential dispatch per-task
- **AND** evidence frontmatter `task_independence_assertion: false`(默认值)

#### Scenario: ADR-013 parallel decline 自动降级 sequential(D-ParallelDeclineFallback)

- **WHEN** controller invoke `/forgeue:change-apply-parallel` 且 user 在 Step 0 consent gate decline(`worktree_consent_outcome: declined`)
- **THEN** 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt)
- **AND** evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: parallel_requires_isolated_workspace`
- **AND** evidence frontmatter `worktree_consent_outcome: declined` + `worktree_mode: in_place`
- **AND** main repo + multi-implementer + W2 路径 NOT 走(F1 attribution 漏洞 — 沿 codex round 1 F1 writeback)

#### Scenario: ADR-013 parallel accepted worktree(skill 或 wrapper mode)

- **WHEN** controller invoke `/forgeue:change-apply-parallel` 且 user 在 Step 0 consent gate accept(`worktree_consent_outcome: accepted` + `worktree_mode ∈ {skill_worktree, wrapper_worktree}`)
- **THEN** parallel implementer 各自在 isolated worktree cwd(沿 D-ConsentOutcomeStateMachine)
- **AND** W2 actual diff 收集 in 各自 worktree(implementer 间 boundary 由 worktree 隔离)
- **AND** evidence frontmatter `worktree_path` 必填 + path exists;`worktree_mode: wrapper_worktree` 时 `worktree_receipt_path` 必填 + receipt JSON valid

### Requirement: Round 2+ fix subagent continuity

`subagent-driven-development` 协议中,round 1 reviewer 找问题后 round 2 fix MUST 通过 `SendMessage` 给 same implementer subagent;round 2 reviewer re-review MUST 给 same reviewer subagent。

evidence frontmatter MUST 含 `subagent_continuity` 字段(对象):

```yaml
subagent_continuity:
  round_1_implementer_id: <agent-id>
  round_2_fix_implementer_id: <agent-id>  # MUST same as round_1
  round_1_reviewer_id: <agent-id>
  round_2_review_reviewer_id: <agent-id>  # MUST same as round_1_reviewer
```

`forgeue_finish_gate.py` SHALL 含 `_check_round_fix_continuity` fence 守门 round 1 / round 2 agent ID 一致性。

**v2 升级**(archived `enhance-workflow-automation-executable-enforcement`):`_check_round_fix_continuity` v2 fence 升级为 ledger cross-check — 校验 evidence frontmatter `subagent_continuity` 中所有 agent_id 都在 `<change>/dispatch_ledger.jsonl` 中**有真实记录**(沿 D-DispatchWrapperBoundary 防 LLM 伪造 agent_id);ledger 缺失 → fail-closed。v1 evidence(无 `dispatch_ledger_path` 字段)沿 v1 fence 行为(仅校验 frontmatter 字段 round_1 == round_2 字符串相等)。

**v3 升级**(本 change `enhance-workflow-automation-ledger-binding`):`_check_round_fix_continuity` v3 fence 在 v2 cross-check 基础上加 HMAC chain 整链 verify — 校验 ledger 全行 `_forgeue_ledger_crypto.verify_chain_v3(key_bytes, lines)` 整链通过(任何 hand-edit / 删除 / reorder → break chain → fence exit 非 0);v2 evidence(`runtime_enforcement_protocol_version: v2`)仍走 v2 schema-only 路径,不触 v3 chain verify。

**ADR-013 update**:本 change 调整 default cwd 为 main repo(沿 D-AllChangeApplyMainRepoDefault),W3 dispatch ledger 仍 active(与 worktree 解耦)— ledger 路径 `<change>/dispatch_ledger.jsonl` 在 main repo cwd(`worktree_mode: in_place`)或 worktree(`worktree_mode ∈ {skill_worktree, wrapper_worktree}`)内创建;v2/v3 fence cross-check 行为不变(沿 archived `enhance-workflow-automation-executable-enforcement` 同款)。**注**:parallel + decline 路径下 W3 仍跑但 sequential dispatch(沿 D-ParallelDeclineFallback 自动降级)。

#### Scenario: round 2 fix 用 same implementer agent ID(v1 + v2 + v3)

- **WHEN** evidence frontmatter 含 `subagent_continuity` + `round_2_fix_implementer_id`
- **THEN** `round_2_fix_implementer_id` MUST 等于 `round_1_implementer_id`,否则 `_check_round_fix_continuity` exit 非 0

#### Scenario: round 2 reviewer 用 same reviewer agent ID(v1 + v2 + v3)

- **WHEN** evidence frontmatter 含 `round_2_review_reviewer_id`
- **THEN** `round_2_review_reviewer_id` MUST 等于 `round_1_reviewer_id`,否则 fence exit 非 0

#### Scenario: v2 evidence ledger cross-check 通过

- **WHEN** v2 evidence `subagent_continuity.round_1_implementer_id: ad79e93a40414763e` + `<change>/dispatch_ledger.jsonl` 中含此 agent_id 行(round=1, role=implementer)
- **THEN** fence pass

#### Scenario: v2 evidence ledger 缺失 agent_id 阻断

- **WHEN** v2 evidence `subagent_continuity.round_1_implementer_id` 在 ledger 中**无对应行**
- **THEN** `_check_round_fix_continuity` v2 fence exit 非 0
- **AND** 错误信息指明 evidence agent_id 不在 ledger 中

#### Scenario: v2 evidence dispatch_ledger.jsonl 文件缺失阻断

- **WHEN** v2 evidence `dispatch_ledger_path: dispatch_ledger.jsonl` 但 `<change>/dispatch_ledger.jsonl` 文件不存在
- **THEN** `_check_round_fix_continuity` v2 fence + `_check_dispatch_ledger` v2 fence 都 exit 非 0(双重守门)

#### Scenario: ADR-013 main repo cwd ledger 路径不变

- **WHEN** controller default 在 main repo cwd 跑 `/forgeue:change-apply-subagent` + W3 ledger append
- **THEN** ledger 路径 `<repo>/openspec/changes/<id>/dispatch_ledger.jsonl`(沿 archived ADR-012 同款 main repo path)
- **AND** v2/v3 fence cross-check 行为不变

#### Scenario: v3 evidence ledger HMAC chain 整链 verify 通过

- **WHEN** v3 evidence `runtime_enforcement_protocol_version: v3` + ledger 含 N 行 v3 schema 合法行(整链 HMAC + key_id 一致)
- **THEN** `_check_round_fix_continuity` v3 fence + `_check_dispatch_ledger` v3 fence pass
- **AND** evidence frontmatter `ledger_forgery_resistance: cryptographic`

#### Scenario: v3 evidence ledger 行被 hand-edit 触发 BLOCKER(double fence)

- **WHEN** v3 evidence + ledger 任意一行 `agent_id` 被 hand-edit
- **THEN** `_check_dispatch_ledger` v3 fence exit 非 0(hmac_mismatch)
- **AND** `_check_round_fix_continuity` v3 fence 也 exit 非 0(双重守门)

#### Scenario: v2 evidence 不触 v3 chain verify(self-dogfood gap)

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2`(本 change 自身 evidence 沿 self-dogfood gap)
- **THEN** v3 fence 分支 pass-through(不 inspect ledger 的 hmac 字段)
- **AND** v2 advisory schema-only 校验仍生效

### Requirement: Task granularity declaration

Controller in `/forgeue:change-apply-*` 命令调用时 MUST 显式声明 task 粒度,evidence frontmatter 加 `task_granularity` 字段,枚举 `phase` / `per-file` / `sub-task`。

`forgeue_finish_gate.py` SHALL 含 `_check_task_granularity` fence 守门:
- `task_granularity` 字段必填
- 值在 enum 内
- evidence 数量与粒度一致(若 declared `phase`,evidence 数量 = phase 数;若 `sub-task`,evidence 数量 = sub-task 数;`per-file` 介于二者之间)

#### Scenario: phase-level granularity declaration

- **WHEN** controller 把 P0(15 sub-task)打包为 1 个 implementation task dispatch
- **THEN** evidence frontmatter `task_granularity: phase`
- **AND** 该 phase 1 个 implementer + 1 spec_review + 1 code_quality 共 3 evidence(round 1 round 2 各算 1 evidence file 含 round_2 append 段或独立 round_2 file)

#### Scenario: per-file granularity declaration

- **WHEN** controller 把 P1(11 sub-task,涉及 9 命令模板 + 1 fence test 文件)按 file 划分为 10 implementation task dispatch
- **THEN** evidence frontmatter `task_granularity: per-file` + 10 个 implementer evidence files

#### Scenario: sub-task granularity declaration

- **WHEN** controller 严格按 tasks.md 每个 `- [ ] X.Y` 1 implementer dispatch
- **THEN** evidence frontmatter `task_granularity: sub-task` + 与 sub-task 数一致的 evidence files

#### Scenario: granularity 与 evidence 数量不一致 finish_gate 阻断

- **WHEN** evidence frontmatter declared `task_granularity: phase` 但实际 evidence 数量超过 phase 数
- **THEN** `_check_task_granularity` exit 非 0 + 错误指明粒度声明 vs 实际 evidence 数量不一致

### Requirement: Preflight wrapper receipt JSON contract

ForgeUE SHALL 提供 stdlib-only 工具 `tools/forgeue_preflight_wrapper.py`,在任何 subagent dispatch 前由命令模板调用,wrapper **自己** 用 `git worktree` subprocess 创建 / 验证 isolated worktree(沿 design.md D-W1-ReceiptSchema 自管 worktree 算法,**不依赖** `superpowers:using-git-worktrees` SKILL — F1 round 1 codex inline writeback)+ 强制 cwd 校验在 wrapper-managed worktree 内(否则 fail-closed exit 6)+ 跑 `forgeue_skill_cascade_check.py` 内嵌 cascade 校验 + 写 machine-generated receipt JSON 到 `<change>/preflight_receipts/<receipt_id>.json`。

Receipt JSON SHALL 含字段(13 个,F1 round 1 inline writeback 加 2 新字段 `is_isolated_worktree` + `worktree_action`):`receipt_id` / `change_id` / `protocol_version: v2` / `worktree_path`(绝对路径)/ `is_isolated_worktree`(bool;wrapper 自管 worktree 的物证)/ `worktree_action`(enum:created / reused;rejected_dirty / rejected_wrong_cwd 时 wrapper exit 6 不写 receipt)/ `base_sha` / `base_branch` / `cwd_at_invocation` / `skill_cascade_check`(对象,含 skill_invoked + exit_code + checked_at)/ `created_at` / `wrapper_version`。

命令模板 `/forgeue:change-apply-{subagent,parallel}` SHALL 在 dispatch 前 wrapper invocation,**仅消费** receipt 路径(LLM 把 receipt 内 `worktree_path` 字符串复制到 evidence frontmatter `worktree_path` 字段;LLM 把 receipt 相对路径写到 evidence frontmatter `worktree_receipt_path` 字段);**不允许** LLM 直接手写 evidence frontmatter `worktree_path` 不经过 receipt(沿 D-DispatchWrapperBoundary)。

#### Scenario: wrapper 自创 worktree + 写 receipt(F1 round 1 inline)

- **WHEN** 跑 `python tools/forgeue_preflight_wrapper.py --change <change-id>`
- **THEN** wrapper 用 `git worktree add <repo>/.worktrees/<change-id>` subprocess 自创 isolated worktree(若不存在;clean reused 路径见单独 scenario)
- **AND** wrapper 跑 cascade check 校验 dependency 全 invoke
- **AND** wrapper 写 receipt 到 `<change>/preflight_receipts/<receipt_id>.json`(JSON well-formed,含全 13 字段含 `is_isolated_worktree: true` + `worktree_action: created`)
- **AND** wrapper stdout 输出 receipt 相对路径供命令模板 capture

#### Scenario: wrapper 拒绝 wrong-cwd(F1 round 1 inline negative test)

- **WHEN** 跑 wrapper 调用时 cwd 不在 wrapper-managed worktree 内(如 main repo 而非 `.worktrees/<change-id>/`)
- **THEN** wrapper exit 6(`worktree_action: rejected_wrong_cwd`)
- **AND** wrapper 不写 receipt
- **AND** stderr 提示 "wrapper 必须在 isolated worktree 内调用"

#### Scenario: wrapper 拒绝 dirty worktree(F1 round 1 inline negative test)

- **WHEN** 跑 wrapper 调用时 wrapper-managed worktree 存在但 `git status --porcelain` 返回非空(dirty 或 untracked)
- **THEN** wrapper exit 6(`worktree_action: rejected_dirty`)
- **AND** wrapper 不写 receipt
- **AND** stderr 提示 "wrapper-managed worktree dirty,请先 commit 或 reset"

#### Scenario: receipt JSON schema 校验

- **WHEN** 读取任意 wrapper 写的 receipt JSON
- **THEN** JSON 解析无错
- **AND** 含字段 `receipt_id` / `change_id` / `protocol_version: "v2"` / `worktree_path` / `is_isolated_worktree: true` / `worktree_action ∈ {created, reused}` / `base_sha` / `base_branch` / `cwd_at_invocation` / `skill_cascade_check` / `created_at` / `wrapper_version`
- **AND** `worktree_path` 是绝对路径且文件系统存在
- **AND** `skill_cascade_check.exit_code == 0`

#### Scenario: receipt 缺失 finish_gate 阻断

- **WHEN** evidence frontmatter `triggered_by_command: change-apply-subagent`(或 `change-apply-parallel`)+ `runtime_enforcement_protocol_version: v2` + `worktree_receipt_path: preflight_receipts/<id>.json` 但实际文件不存在
- **THEN** `forgeue_finish_gate.py::_check_worktree_path` v2 fence exit 非 0
- **AND** 错误信息指明 evidence 文件 + 缺失的 receipt 路径

#### Scenario: receipt worktree_path 与 evidence frontmatter 不一致 finish_gate 阻断

- **WHEN** receipt JSON `worktree_path` 字段 != evidence frontmatter `worktree_path` 字符串
- **THEN** `_check_worktree_path` v2 fence exit 非 0
- **AND** 错误信息指明 receipt 与 evidence 两侧 path 字符串

### Requirement: Dispatch ledger append-only contract

ForgeUE SHALL 提供 stdlib-only 工具 `tools/forgeue_dispatch_ledger.py`,提供子命令:
- `append --change <id> --agent-id <id> --round <N> --role <role> [--task-subject-hash <sha256>]`:向 `<change>/dispatch_ledger.jsonl` append 一行 JSON
- `verify --change <id>`:校验 ledger JSONL 每行 well-formed + timestamp 单调递增 + wrapper_version 字段非空 + (v3 协议)HMAC chain 整链 verify

`<change>/dispatch_ledger.jsonl` SHALL 是 append-only 文件,每行一个 JSON 记录。schema 沿 `runtime_enforcement_protocol_version` 字段分两档:

**v2 schema(7 字段;archived `executable-enforcement` ship)**:`agent_id` / `round`(int)/ `role` / `task_subject_hash`(可空)/ `dispatched_at`(ISO8601)/ `parent_session_id`(可空)/ `wrapper_version`。

**v3 schema(11 字段;本 change ship)**:v2 7 字段 + `protocol_version: "v3"` / `key_id`(SHA256(key)[:16] fingerprint)/ `prev_hmac`(64 hex chars,首行全 0)/ `hmac`(HMAC-SHA256 over canonical JSON)。

`tools/forgeue_dispatch_ledger.py` SHALL 在 `cmd_append` 中按当前 wrapper 版本(`WRAPPER_VERSION`)决定写哪档 schema:
- v2 wrapper(`WRAPPER_VERSION = "1.0"`):写 7 字段
- v3 wrapper(`WRAPPER_VERSION = "2.0"`,本 change ship):写 11 字段(含 HMAC chain)

`cmd_verify` SHALL 沿 ledger 行的 `protocol_version` 字段 dispatch:
- 行内无 `protocol_version` 字段(v2 ledger):走 schema-only 校验(timestamp 单调 + wrapper_version 非空 + JSON well-formed)
- 行内 `protocol_version: "v3"`:走 schema-only + HMAC chain 整链 verify

`cmd_verify` exit code(round 1 codex F2 inline writeback 后):
- 0:校验通过
- 5:`verify_fail`(任何 schema / HMAC / chain / terminal proof / frontmatter audit 错误,BLOCKER)— 含 `hmac_mismatch` / `chain_break` / `key_id_inconsistent` / `key_id_mismatch`(active v3,默认 fail-closed)/ `tail_truncation_detected` / `final_hmac_mismatch` / `schema_violation` / `frontmatter_audit_inconsistency`
- 6:`key_rotation_user_override_required`(仅在 evidence frontmatter `ledger_archived_replay: true` opt-in 时触发;user 显式承担"无法重算 HMAC"风险;archived ledger replay 兼容路径)
- 7:`key_file_corrupted`

命令模板 `/forgeue:change-apply-{subagent,parallel}` SHALL 在每次 Skill(Task) / Skill(SendMessage) 调用**之后**(post-dispatch capture 真实 agent_id)wrapper append(沿 archived `enhance-workflow-automation-executable-enforcement` F2 round 1 inline writeback 协议 — pre-dispatch 写入 synthetic agent_id 与真实 agent_id 无关,本 change F3-only scope 不 reopen F2)。命令模板**不暴露** ledger 文件路径给 LLM Read / Write / Edit tool(沿 D-DispatchWrapperBoundary 防 LLM 篡改);**不暴露** key 文件路径给 LLM(沿 D-KeyLocation,key 文件在 LLM 不主动 read 的 `~/.claude/` 用户目录)。

evidence frontmatter `pre_dispatch_metadata: advisory` 标注沿 archived 同款保留(post-dispatch capture 模型的 advisory 限制说明:agent_id 在 dispatch 后 capture,F3 cryptographic enforcement 不解决"LLM 在 post-dispatch 后伪造 agent_id"威胁,本边界留 follow-on `enhance-workflow-automation-skill-tool-binding`)。

evidence frontmatter SHALL 含 `dispatch_ledger_path` 字段,值固定为 `dispatch_ledger.jsonl`(相对 `<change>/`)。

#### Scenario: wrapper append 写一行 JSONL(v2 路径,archived 兼容)

- **WHEN** wrapper version `1.0` + 跑 `python tools/forgeue_dispatch_ledger.py append --change <id> --agent-id ad79e93a40414763e --round 1 --role implementer --task-subject-hash sha256:abc...`
- **THEN** 文件 `<change>/dispatch_ledger.jsonl` 末尾 append 一行 JSON
- **AND** JSON 含 7 字段 v2 schema(无 `protocol_version` / `key_id` / `prev_hmac` / `hmac`)

#### Scenario: wrapper append 写一行 JSONL(v3 路径,本 change ship)

- **WHEN** wrapper version `2.0`(本 change ship 后)+ 跑 append
- **THEN** 文件末尾 append 一行 11 字段 v3 schema JSON
- **AND** JSON 含 `protocol_version: "v3"` / `key_id` / `prev_hmac`(首行全 0,后续行链接前一行 hmac)/ `hmac`(HMAC-SHA256 over canonical)

#### Scenario: ledger timestamp 单调性 verify

- **WHEN** 跑 `python tools/forgeue_dispatch_ledger.py verify --change <id>`
- **THEN** 工具校验所有行 `dispatched_at` 字段单调递增
- **AND** 任意行 timestamp 倒流 → exit 5 + 错误指明行号

#### Scenario: ledger 缺失 finish_gate 阻断

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2` 或 `v3` + `dispatch_ledger_path: dispatch_ledger.jsonl` + `subagent_continuity` 字段 declared dispatch 但实际 `<change>/dispatch_ledger.jsonl` 文件不存在
- **THEN** `forgeue_finish_gate.py::_check_dispatch_ledger` v2/v3 fence exit 非 0
- **AND** 错误信息指明缺失的 ledger 文件

#### Scenario: ledger agent_id 集合 与 evidence subagent_continuity 不一致 finish_gate 阻断

- **WHEN** evidence frontmatter `subagent_continuity.round_1_implementer_id: ad79e93a40414763e` 但 ledger 中**无**此 agent_id 行
- **THEN** `_check_dispatch_ledger` fence exit 非 0
- **AND** 错误信息指明 evidence agent_id 不在 ledger 中

#### Scenario: ledger wrapper_version 字段缺失 finish_gate 阻断

- **WHEN** ledger JSONL 任意行缺 `wrapper_version` 字段(可能 LLM 手工伪造行)
- **THEN** `_check_dispatch_ledger` fence exit 非 0

#### Scenario: v3 ledger 行 hmac 字段缺失 finish_gate 阻断(v3 路径)

- **WHEN** evidence v3 + ledger 行 `protocol_version: "v3"` 但缺 `hmac` 字段
- **THEN** `_check_dispatch_ledger` v3 fence exit 非 0,error message prefix `[hmac_mismatch] line <N>: hmac field missing`

#### Scenario: cmd_verify active v3 默认 key_id mismatch BLOCKER(round 1 codex F2 inline writeback)

- **WHEN** 跑 `python tools/forgeue_dispatch_ledger.py verify --change <id>` + ledger 是 v3 + ledger 内 key_id 与当前 file key_id 不一致 + 命令未指定 `--allow-archived-replay` flag
- **THEN** verify exit 5(`key_id_mismatch`,BLOCKER)
- **AND** stderr 打印 `[ERROR] ledger key_id <X> ≠ current key_id <Y>; HMAC verify cannot proceed; if this is archived replay, set evidence_frontmatter ledger_archived_replay: true OR pass --allow-archived-replay flag`

#### Scenario: cmd_verify archived replay user override 路径 exit 6(round 1 codex F2 inline writeback)

- **WHEN** 跑 `python tools/forgeue_dispatch_ledger.py verify --change <id> --allow-archived-replay` + ledger 是 v3 + ledger 内 key_id 与当前 file key_id 不一致
- **THEN** verify exit 6(`key_rotation_user_override_required`,user opt-in WARN)
- **AND** stderr 打印 `[WARN] ledger key_id <X> ≠ current key_id <Y>; HMAC verify skipped per --allow-archived-replay flag; archived ledger replay accepted`
- **AND** finish_gate 接受 user override 路径(evidence frontmatter `ledger_archived_replay: true` 配套必须;否则 finish_gate 自身不接受 cmd_verify exit 6)

#### Scenario: cmd_verify exit code 7 区分 key_file_corrupted

- **WHEN** 跑 `python tools/forgeue_dispatch_ledger.py verify --change <id>` + key 文件存在但 JSON parse 失败 / key_hex 长度错
- **THEN** verify exit 7(`key_file_corrupted`)
- **AND** stderr 打印 `[ERROR] key file corrupted at <path>: <reason>; backup + remove file to re-init`

#### Scenario: cmd_verify v3 dispatch by ANY v3 fingerprint signal(round 3 codex F1 inline writeback)

- **WHEN** ledger 任意行含 v3 信号字段任一(`hmac` / `prev_hmac` / `key_id`)OR `wrapper_version: "2.0"` OR `protocol_version: "v3"`
- **THEN** cmd_verify SHALL 走 v3 strict validation 路径(strict 11-field schema + chain HMAC + key rotation),**不**降级到 v2 schema-only;此规则防 LLM hand-edit 全部行 protocol_version 字段企图绕 v3 fence
- **AND** strict schema validation 校 `protocol_version` 字段必须精确 `"v3"`(若被改为 `"v2"` / `"v4"` / 缺失 → BLOCKER `[schema_violation]`)

#### Scenario: cmd_verify v3 strict trigger via hmac field only(LLM 改 protocol_version 但漏改 hmac)

- **WHEN** ledger 行含 `hmac` / `prev_hmac` / `key_id` 字段任一,但所有行 `protocol_version` 被改为 `"v2"` / 缺失
- **THEN** cmd_verify trigger v3 strict validation(沿 ANY v3 信号 dispatch);strict schema 校 `protocol_version` 必须 `"v3"` → BLOCKER `[schema_violation]`
- **AND** verify exit 5,error message prefix `[schema_violation] line <N>: field 'protocol_version' MUST be exactly 'v3', got <X>`

#### Scenario: cmd_verify v3 strict trigger via wrapper_version 2.0(LLM 漏改 wrapper_version)

- **WHEN** ledger 行 `wrapper_version: "2.0"` + 所有行 `protocol_version` 改 / 缺失 + 所有 v3 字段(hmac / prev_hmac / key_id)被删
- **THEN** cmd_verify trigger v3 strict validation(`wrapper_version=2.0` 是 v3 信号之一);strict schema 校 v3 字段缺失 → BLOCKER `[schema_violation]`

#### Scenario: cmd_verify pure v2 ledger(无 v3 信号)走 v2 schema-only

- **WHEN** ledger 全行 7-字段 v2 schema(无 hmac / prev_hmac / key_id;`wrapper_version: "1.0"`;无 `protocol_version`)
- **THEN** cmd_verify 走 v2 schema-only 路径(JSON well-formed + wrapper_version 非空 + timestamp 单调);不触发 v3 strict
- **AND** verify exit 0(archived v2 ledger 完全 backward compatible)

**cmd_verify scope boundary(round 3 codex F2 inline writeback;terminal proof 由 finish_gate 而非 cmd_verify 实施)**:

`cmd_verify` SHALL 实施:strict 11-field schema validation(沿 D-Scope-F3-MergeWithP12.8)+ chain HMAC verify(沿 D-HashChain)+ key rotation 双路径(沿 D-KeyRotationHandling)+ ANY v3 信号 dispatch(round 3 codex F1)。

`cmd_verify` SHALL **不**实施 terminal proof(`ledger_line_count` + `ledger_final_hmac` 与 evidence frontmatter cross-check)— 此责任由 `forgeue_finish_gate.py::_check_ledger_terminal_proof` fence 实施(沿 D-LedgerTerminalProof);finish_gate 是 evidence-aware fence locus,有 evidence frontmatter context;cmd_verify 是 standalone CLI verify 工具,无 evidence context,加 `--evidence-line-count` / `--evidence-final-hmac` flag 是工具职责过度扩展。

**Append serial invariant**(round 3 codex F4 inline writeback):

命令模板 `/forgeue:change-apply-{subagent,parallel}` SHALL **主 session 串行 append wrapper**(implementer subagent dispatch 之间 parallel,但 append 是主 session 跑 — Skill(Task) 返回后由 controller 主 session 调 wrapper,自然 serialize)。本 invariant 防并发 append race(同时读 prev_hmac → 写两行同 prev_hmac → chain 断)。

`tools/forgeue_dispatch_ledger.py::cmd_append` 自身**不**强制 cross-platform file lock(`fcntl` / `msvcrt`);并发安全由命令模板 main session serial 提供。若 ship 后实证 race 实际发生(如非 ForgeUE 工作流外部并发跑 wrapper)→ 触发 follow-on `enhance-workflow-automation-ledger-append-lock`。

#### Scenario: 命令模板 main session 串行 append invariant(round 3 codex F4 inline writeback)

- **WHEN** `/forgeue:change-apply-parallel` dispatch N 个 implementer subagent(parallel)+ 每个 implementer 完成后回到主 session
- **THEN** 主 session **顺序**调 cmd_append wrapper(每次 Skill(Task) 返回后串行调一次),**不**并发调 wrapper
- **AND** ledger 行依次 append,prev_hmac 链接前一行 hmac;chain 完整无断

#### Scenario: 外部并发 append(本 change scope 外)race 不被 fence 防御

- **WHEN** 用户外部 script 在命令模板之外并发跑 `python tools/forgeue_dispatch_ledger.py append ...` 多次
- **THEN** 可能产生并发 append race(沿 R3 deferred follow-on);本 change 不防御此场景
- **AND** finish_gate verify chain 时若发现 chain 断 → BLOCKER(沿 chain_break);但 BLOCKER 后 user 需自己 debug 是不是外部 race

### Requirement: Parallel dispatch actual file overlap detection

`/forgeue:change-apply-parallel` 命令模板 SHALL 在所有 implementer subagent commit 完成后,主 session 自动跑两步收集 **actual** changed-files set(F4 round 1 codex inline writeback — 原 `git diff --name-only` 漏 untracked file):

**Precondition**:对每个 implementer worktree 跑 `git status --porcelain=v1 -z`;若返回非空(任何 dirty / untracked / staged 但 uncommitted file)→ 命令 abort + 自动降级 sequential + evidence frontmatter `degradation_reason: dirty_implementer_worktree`(implementer 漏 add 文件触发的 fail-closed 路径)。

**Actual changed-files 收集**:在每个 clean implementer worktree 内合并:
- `git diff --name-only -z <base_sha>..HEAD`(committed diff)
- `git ls-files --others --exclude-standard -z`(untracked but ignored exclusion 后)
- 解析 NUL-separated 输出为 file path set

主 session SHALL 计算所有 implementer set intersection;intersection 非空 → 命令 abort + 自动降级 `/forgeue:change-apply-subagent` sequential(无 user prompt,沿 user feedback `feedback_no_continue_prompts_between_phases.md`)。

evidence frontmatter SHALL 含字段:
- `task_files_actual`:list of `{implementer_agent_id, files: [...]}`(actual collection 后写;包含 untracked)
- `degraded_to`:`null` 或 `change-apply-subagent`(降级时填)
- `degradation_reason`:`null` / `actual_file_overlap_detected` / `dirty_implementer_worktree`

`forgeue_finish_gate.py` SHALL 含 `_check_file_overlap_actual` v2 fence,校验:
- evidence frontmatter `task_files_actual` 与 declared `task_files_disjoint` 一致(actual ⊆ declared 或者声明 + 错误回滚)
- actual changed-files set 之间确实 disjoint(若 `degraded_to: null`)
- `degraded_to: change-apply-subagent` 时改走 sequential 路径校验逻辑(4 类 evidence 完整性,跳过 disjoint 校验)

#### Scenario: parallel dispatch 后主 session 收集 actual files(committed + untracked,F4 round 1 inline)

- **WHEN** parallel 命令模板 dispatch N 个 implementer subagent + 全部 commit 完成 + worktree clean(precondition pass)
- **THEN** 主 session 在每个 implementer worktree 跑 `git diff --name-only -z <base_sha>..HEAD` + `git ls-files --others --exclude-standard -z` 合集
- **AND** evidence frontmatter `task_files_actual` 字段填入 N 个 `{implementer_agent_id, files: [...]}` 记录(含 untracked)

#### Scenario: dirty implementer worktree 触发降级(F4 round 1 inline negative)

- **WHEN** 任意 implementer worktree `git status --porcelain=v1` 返回非空(implementer 漏 commit / 漏 add 新文件)
- **THEN** 命令 abort + 自动降级 sequential + evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: dirty_implementer_worktree`
- **AND** Bash 写 `<change>/parallel_abort_dirty_<iso>.log` 含 implementer agent_id + dirty files 列表

#### Scenario: actual disjoint 通过

- **WHEN** N 个 implementer 的 actual changed-files set 两两 intersect 全部为空
- **THEN** 命令继续走 spec_review / code_quality / final_review subagent
- **AND** evidence frontmatter `degraded_to: null` + `task_independence_assertion: true`

#### Scenario: actual overlap detected 自动降级 sequential

- **WHEN** 任意两个 implementer 的 actual changed-files set 有交集
- **THEN** 主 session 写 `<change>/parallel_abort_<iso>.log` 记录 overlap files + 涉及 agent_id
- **AND** 命令自动 invoke `/forgeue:change-apply-subagent` sequential(无 user prompt)
- **AND** evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected`

#### Scenario: declared task_files_disjoint 与 actual 不一致 finish_gate audit fail

- **WHEN** evidence frontmatter `task_files_disjoint` 字段(declaration)与 `task_files_actual` 字段(实际 diff)不一致(如 implementer 改了未声明的文件)
- **THEN** `_check_file_overlap_actual` v2 fence exit 非 0
- **AND** 错误信息指明 declared vs actual 差异 file list

### Requirement: v2 e2e integration test fixture(F5 round 1 codex inline writeback)

ForgeUE SHALL 提供 `tests/integration/test_v2_e2e_synthetic_change.py` 集成测试 fixture(stdlib + pytest),在 archive 前必跑全绿,作为 archive 阻断 gate。

fixture 必须覆盖 v2 协议端到端实跑(沿 design.md D-W4-IntegrationGate):
- 用 `tmp_path` 创建 synthetic active change 目录
- 跑 W1 wrapper 创建 worktree + 写 receipt
- mock Skill(Task) 返回真实 agent_id 格式 + 跑 W3 ledger append + verify
- 模拟 parallel 场景:2 implementer 各 commit + 跑 W2 actual diff + overlap 负例
- 跑 finish_gate 全 6 fence on synthetic v2 evidence
- 跑 v1 evidence 兼容 + legacy evidence pass-through 回归

`forgeue_finish_gate.py` SHALL 在 archive 前跑 `pytest -q tests/integration/test_v2_e2e_synthetic_change.py` 全绿(原文件不在 archive blocker 集合,本 fixture 加入 P10.0 必过 gate)。

#### Scenario: v2 e2e fixture 全链路通过

- **WHEN** 跑 `pytest -q tests/integration/test_v2_e2e_synthetic_change.py`
- **THEN** W1 wrapper / W2 actual diff / W3 ledger / finish_gate 全部 pass
- **AND** synthetic overlap 负例正确触发自动降级 sequential
- **AND** v1 evidence 兼容 + legacy pass-through 回归通过

#### Scenario: archive 前 v2 e2e gate 不绿阻断

- **WHEN** 跑 `pytest -q tests/integration/test_v2_e2e_synthetic_change.py` 不全绿
- **THEN** archive 命令拒绝(P10.0 gate failed)
- **AND** finish_gate report 含详细 fixture 失败原因

### Requirement: Runtime enforcement protocol version v2 migration

ForgeUE evidence frontmatter SHALL 在 v1 12-key 基础上加 v2-only 字段(仅当 `runtime_enforcement_protocol_version: v2` 时强制):
- `worktree_receipt_path`:相对 `<change>/` 的 receipt JSON 路径(W1)
- `dispatch_ledger_path`:固定值 `dispatch_ledger.jsonl`(W3)
- `task_files_actual`:list(parallel only;sequential evidence 该字段为空 list)(W2)
- `degraded_to` + `degradation_reason`:可空(W2 降级标识)
- `pre_dispatch_metadata: advisory`(F2 round 1 inline writeback;诚实标注 agent_id 是 dispatch 后 capture,无 pre-dispatch 物证)
- `ledger_forgery_resistance: advisory`(F3 round 1 inline writeback;诚实标注 well-formed forge 不阻断;follow-on `enhance-workflow-automation-ledger-binding` ship 后改为 cryptographic)

`forgeue_finish_gate.py` 新增 fence(`_check_file_overlap_actual` / `_check_dispatch_ledger`)+ 升级 fence(`_check_worktree_path` v2 / `_check_round_fix_continuity` v2) **仅对** evidence frontmatter `runtime_enforcement_protocol_version: v2` 的文件生效。

v1 evidence(含 `runtime_enforcement_protocol_version: v1`)沿用 v1 fence 行为(advisory + frontmatter audit);archived enhance-workflow-automation-runtime-enforcement evidence(v1)在本 change ship 后 replay finish_gate 不被 v2 fence 误杀。

无 `runtime_enforcement_protocol_version` 字段的 legacy evidence(archived enhance-workflow-automation 等)继续 fence pass-through。

#### Scenario: v2 evidence 触发 v2 fence

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2`
- **THEN** finish_gate dispatch 6 个 fence(skill_cascade / round_fix_continuity v2 / task_granularity / worktree_path v2 / file_overlap_actual / dispatch_ledger)全部 enforce

#### Scenario: v1 evidence 沿 v1 fence

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v1`
- **THEN** finish_gate 仅 enforce v1 fence(skill_cascade / round_fix_continuity v1 / task_granularity / worktree_path v1)
- **AND** 不 enforce file_overlap_actual / dispatch_ledger / worktree_path v2 加严

#### Scenario: legacy evidence(无 protocol_version)pass-through

- **WHEN** evidence frontmatter 无 `runtime_enforcement_protocol_version` 字段(legacy archived 如 2026-05-04-adopt-subagent-driven-development)
- **THEN** finish_gate v1 / v2 fence 全部 pass-through
- **AND** archived fixture replay 测试通过

#### Scenario: archived enhance-workflow-automation-runtime-enforcement replay 兼容

- **WHEN** finish_gate 跑 `python tools/forgeue_finish_gate.py --change archive/2026-05-05-enhance-workflow-automation-runtime-enforcement`
- **THEN** v1 evidence 全部按 v1 fence 校验
- **AND** v2 fence 不被触发(无 v2 字段 → pass-through)
- **AND** 整个 archive 通过 finish_gate(不 false-block)

### Requirement: HMAC key lifecycle for v3 cryptographic ledger binding

ForgeUE SHALL 提供 stdlib-only helper module `tools/_forgeue_ledger_crypto.py`,负责 HMAC key 文件 lifecycle 管理。

**Key 文件路径**:`Path.home() / ".claude" / "forgeue_ledger_key"`(跨 change 共享;Windows / Linux / Mac 都解析到当前用户 home)。

**Key 文件 schema**(JSON 单文件):
```json
{
  "version": 1,
  "created_at": "<ISO8601 timestamp>",
  "key_hex": "<64 hex chars = 32 bytes random>"
}
```

**`load_or_init_key()` 函数 SHALL 返回 `(key_bytes: bytes, key_id: str)` tuple**:
- `key_bytes`:32 字节 raw key(`bytes.fromhex(key_hex)`)
- `key_id`:`hashlib.sha256(key_bytes).hexdigest()[:16]`(16 hex chars = 64-bit fingerprint;不暴露 raw key)

**Lifecycle 4 状态**:

| 状态 | 触发条件 | wrapper 行为 | 退出/返回 |
|---|---|---|---|
| 首次 init | key 文件不存在 + `append` 调用 | `secrets.token_bytes(32)` 生成 + 用 `os.O_EXCL` flag 创建文件 + Linux/Mac `os.chmod(0o600)` + 打印 `[INFO] HMAC key initialized at <path> (key_id=<fingerprint>)` | 0 (继续 append) |
| 正常 load | 文件存在 + JSON 合法 + key_hex 长度恰好 64 chars | 读 key + 计算 key_id | 0 |
| 文件损坏 | 文件存在但 JSON 解析失败 / key_hex 长度错误 / version 不识别 | abort,**不**静默重建;打印 ERROR 提示 user backup + 删除 + 重新 init | 7 (`key_file_corrupted`) |
| key rotation 检测 | (verify 时)ledger 行 key_id ≠ 当前 file key_id,但 ledger 自身 key_id 一致 | WARN,不阻断 | 6 (`key_rotation_detected`) |

**关键约束**:
- Key 文件**不**进 git 追踪(由用户目录自然隔离;`.gitignore` 不需加入,因为不在 repo 内)
- 命令模板**不暴露** key 文件路径给 LLM Read / Write / Edit tool(LLM 不直接接触 key)
- 实施 stdlib-only:`secrets` / `hashlib` / `hmac` / `json` / `pathlib` / `os.chmod`,无第三方依赖

#### Scenario: 首次 init 自动生成 key 文件

- **WHEN** `~/.claude/forgeue_ledger_key` 不存在 + 跑 `forgeue_dispatch_ledger.py append`
- **THEN** wrapper 自动 `secrets.token_bytes(32)` 生成 32 字节 random + 用 `os.O_EXCL` flag 创建 JSON 文件
- **AND** 文件含 `version: 1` + `created_at` ISO8601 + `key_hex`(64 hex chars)
- **AND** Linux/Mac 文件权限 `0600`(stat 校 `S_IRUSR | S_IWUSR`,无 group/other 位)
- **AND** stdout 打印 `[INFO] HMAC key initialized at <path> (key_id=<16 hex>)` 一行

#### Scenario: 正常 load 已存在 key 文件

- **WHEN** key 文件已存在 + JSON 合法 + key_hex 长度 64 chars + 跑 append/verify
- **THEN** wrapper 读文件 + 解析 JSON + 用 key_hex 派生 key_bytes 与 key_id
- **AND** key_id == sha256(key_bytes).hexdigest()[:16]

#### Scenario: 文件损坏 fail-closed

- **WHEN** key 文件存在但 JSON 解析失败(如末尾被 truncate) OR key_hex 长度 ≠ 64 OR version 字段不是 1
- **THEN** wrapper exit 7
- **AND** stderr 打印 `[ERROR] key file corrupted at <path>: <reason>; backup + remove file to re-init`
- **AND** **不**自动重建 key(避免静默丢失 verify 旧 ledger 能力)

#### Scenario: 文件锁防 race(并发 init)

- **WHEN** 两个 wrapper 进程同时检测 key 文件不存在并尝试 init
- **THEN** 用 `os.open(path, O_CREAT | O_EXCL | O_WRONLY)` 创建文件
- **AND** 第二个进程触发 EEXIST,捕获后 retry-load,读到第一个进程刚写入的 key
- **AND** 两个 wrapper 最终用同一 key + 同一 key_id

### Requirement: v3 ledger schema with HMAC chain

ForgeUE SHALL 升级 ledger 行 schema 到 v3 — v2 的 7 字段基础上加 4 字段:`protocol_version` / `key_id` / `prev_hmac` / `hmac`。

**v3 ledger 行 schema**(11 字段):
```json
{
  "agent_id": "<hex>",
  "round": <int>,
  "role": "<implementer|spec_reviewer|code_quality_reviewer|final_reviewer|implementer_round_2_fix|spec_reviewer_round_2_review>",
  "task_subject_hash": "<sha256:...|null>",
  "dispatched_at": "<ISO8601>",
  "parent_session_id": "<uuid|null>",
  "wrapper_version": "2.0",
  "protocol_version": "v3",
  "key_id": "<16 hex chars>",
  "prev_hmac": "<64 hex chars; first line: '0' * 64>",
  "hmac": "<64 hex chars = HMAC-SHA256(key, canonical_payload)>"
}
```

**Wrapper 版本**:`tools/forgeue_dispatch_ledger.py::WRAPPER_VERSION` SHALL 升到 `"2.0"`(标记 v3 schema break)。

**HMAC 计算规则**:
- `canonical_payload(record)` 函数:`json.dumps(record_without_hmac_field, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`
- `hmac` 字段从 canonical 中**排除**(避免循环依赖)
- `prev_hmac` 字段**包含**(它是 chain 输入)
- `compute_hmac(key, record)` 调 `hmac.new(key, canonical_payload(record), hashlib.sha256).hexdigest()`

**Hash chain 协议**:
- 首行 `prev_hmac` 固定 `"0" * 64`(64 个 0)
- 第 N 行(N >= 2)`prev_hmac` 等于第 N-1 行的 `hmac` 字段值
- 任何修改 / 删除 / reorder 必然 break chain(后续行 prev_hmac 不匹配新"上一行" hmac)

**Append 流程**(`cmd_append` 升级):
1. 加载或初始化 key (`load_or_init_key()`)
2. 读 ledger 末尾行的 hmac(若 ledger 不存在或为空 → 用 `"0" * 64`)
3. 构建 record(11 字段全填,`hmac` 字段先留空)
4. 算 `hmac = compute_hmac(key, record)`,填入 record
5. 写一行(json.dumps 同 canonical 规则,逐行 append)

#### Scenario: 首行 prev_hmac 全 0

- **WHEN** ledger 文件不存在 + wrapper append 第一行
- **THEN** record 含 `prev_hmac: "0000000000000000000000000000000000000000000000000000000000000000"`(64 chars)
- **AND** record 的 hmac 字段 = `compute_hmac(key, record_with_prev_hmac_zeros)`

#### Scenario: 后续行 prev_hmac 链接上一行 hmac

- **WHEN** ledger 已有 N 行 + wrapper append 第 (N+1) 行
- **THEN** 新行 `prev_hmac` 等于第 N 行的 `hmac` 值(64 hex chars)
- **AND** 新行 `hmac = compute_hmac(key, new_record_with_prev_hmac_chained)`

#### Scenario: hmac 字段从 canonical 排除

- **WHEN** wrapper 计算 `canonical_payload(record)` 用于 HMAC 输入
- **THEN** canonical bytes 不含 `hmac` 字段(避免循环依赖)
- **AND** canonical bytes 含 `prev_hmac` 字段(它是 chain 输入)

#### Scenario: canonical JSON 字段顺序无关

- **WHEN** 同一 record 字段以不同写入顺序构造(insertion order 1 vs insertion order 2)
- **THEN** `canonical_payload(record)` 返回完全相同的 bytes(`sort_keys=True` 保证)
- **AND** `compute_hmac` 输出 hex 也相同

#### Scenario: wrapper_version 升到 "2.0"

- **WHEN** v3 wrapper append 一行
- **THEN** record 含 `wrapper_version: "2.0"`(常量,不可配置)
- **AND** archived v2 ledger 行(`wrapper_version: "1.0"`)在 v2 fence 路径下仍合法(fence 不强制具体值,仅校非空)

### Requirement: v3 fence dispatch matrix and HMAC chain verification

`forgeue_finish_gate.py::_check_dispatch_ledger` SHALL 加入 v3 dispatch 分支,fence dispatch matrix 扩到 4 档:

| evidence frontmatter `runtime_enforcement_protocol_version` | fence 行为 |
|---|---|
| 无字段(legacy) | 全 v1/v2/v3 fence pass-through |
| `v1` | 走 v1 fence(沿 ADR-011) |
| `v2` | 走 v1 + v2 fence(advisory schema-only,沿 ADR-012) |
| `v3` | 走 v1 + v2 + v3 fence(v3 = v2 schema check + HMAC chain verify + terminal proof + audit consistency + strict 11-field schema) |
| 其他 present value(`v4` / typo / empty / null)| **BLOCKER `unknown_protocol_version`**(沿 D-RuntimeEnforcementProtocolVersionValidity 沿 round 2 codex F2 inline writeback;**fence skip 必须由 absence 决定,不能由 invalid value 决定**) |

**新 helper**:`_runtime_enforcement_v3_active(frontmatter) -> bool`,检测 `frontmatter.get("runtime_enforcement_protocol_version") == "v3"`。

**新 helper**(round 2 codex F2 inline writeback):`_VALID_PROTOCOL_VERSIONS = frozenset({"v1", "v2", "v3"})` 模块常量;新 fence `_check_runtime_enforcement_protocol_version_validity` 在所有 protocol-version-dependent fence 之前跑(防 unknown value 走 skip 路径)。

**v3 verify 流程**(`_forgeue_ledger_crypto.verify_chain_v3(key_bytes, lines, evidence_frontmatter)`):
1. 解析 ledger 全行为 list of dict
2. 检查 ledger 内所有行 `key_id` 一致(沿"同 ledger 同 key" invariant)
3. 检查 ledger 内 key_id vs 当前文件 key_id(**round 1 codex F2 inline writeback,key_rotation 默认 fail-closed**):
   - **active v3 evidence**(`evidence_frontmatter.get("ledger_archived_replay") != True`):key_id 不一致 → `key_id_mismatch` BLOCKER(攻击场景:LLM 替换 key 文件即可降级 HMAC 校 — 必须 fail-closed)
   - **archived replay 模式**(`evidence_frontmatter.ledger_archived_replay: true` opt-in):key_id 不一致 → `key_rotation_user_override_required` 走 user explicit override 路径(audit 友好,user 显式承担"无法重算 HMAC"风险)
4. 从首行起整链 verify(仅在 key_id 与当前 file 一致时跑;archived replay 模式 skip 此步)`:
   - 首行 `prev_hmac` 必须 `"0" * 64`
   - 每行 `hmac == compute_hmac(key, record)`(canonical 重算)
   - 每行 `prev_hmac == 上一行 hmac`(chain 连续)
5. 检查 ledger terminal proof(沿 round 1 codex F3 inline writeback,新加;`evidence_frontmatter.ledger_line_count` + `ledger_final_hmac` 字段必填 v3 evidence;cross-check 与实际 ledger 一致)— 见独立 Requirement "v3 ledger terminal proof"

**verify 状态枚举 + 处理**(round 1 codex F2 inline writeback 后):

| 状态 | 触发 | 等级 | exit code |
|---|---|---|---|
| `ok` | 全链 HMAC 正确 + key_id 一致 + terminal proof 一致 | pass | 0 |
| `hmac_mismatch` | 某行 HMAC 重算 ≠ 写入值 | BLOCKER | 5 |
| `chain_break` | 某行 prev_hmac ≠ 上一行 hmac OR 首行 prev_hmac ≠ all-zeros | BLOCKER | 5 |
| `key_id_inconsistent` | 同一 ledger 内不同行 key_id 不一致 | BLOCKER | 5 |
| `key_id_mismatch` | active v3 evidence + ledger key_id ≠ 当前 file key_id | BLOCKER | 5 |
| `tail_truncation_detected` | evidence `ledger_line_count` ≠ 实际 ledger 行数 | BLOCKER | 5 |
| `final_hmac_mismatch` | evidence `ledger_final_hmac` ≠ 实际 ledger 最后一行 hmac | BLOCKER | 5 |
| `schema_violation` | ledger 行 strict schema 违反(沿 F5 scope expansion;字段集 / 字段类型 / 字段 format) | BLOCKER | 5 |
| `frontmatter_audit_inconsistency` | evidence frontmatter `ledger_forgery_resistance` 与 `runtime_enforcement_protocol_version` 不一致 | BLOCKER | 5 |
| `key_rotation_user_override_required` | archived replay 模式 + ledger key_id ≠ 当前 file key_id | user override(WARN 输出,exit 6) | 6 |
| `key_file_corrupted` | key 文件 JSON 损坏 / key_hex 长度错 / version 不识别 | wrapper abort | 7 |

**关键 invariants**(round 1 codex inline writeback 后):
- v3 fence 仅 inspect ledger + evidence frontmatter,**不**修改 ledger 内容
- v3 fence 走 fail-closed — verify 失败时 finish_gate exit 非 0(BLOCKER 级别)
- **key_id mismatch 默认 BLOCKER**(round 1 codex F2 inline writeback;不再 WARN 自动 pass);archived replay 兼容走 evidence frontmatter `ledger_archived_replay: true` explicit user opt-in 路径(exit 6 仅在此路径触发,user 显式承担风险)
- evidence frontmatter `ledger_line_count` + `ledger_final_hmac` 是 v3 必填(F3 inline writeback);缺失或与实际不一致 → BLOCKER
- ledger 行 strict 11-field schema(F5 scope expansion):字段集精确 + 字段类型 strict + 字段 format 正则校

#### Scenario: v3 evidence + 合法 v3 ledger 整链 verify 通过

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v3` + ledger 含 N 行 v3 schema 合法行(chain 连续 + key_id 一致 + HMAC 正确)
- **THEN** `_check_dispatch_ledger` v3 fence pass + 无 Blocker

#### Scenario: hand-edit 某行字段触发 hmac_mismatch BLOCKER

- **WHEN** v3 ledger 任意一行的 `agent_id` / `dispatched_at` / 其他原 7 字段 / `protocol_version` / `key_id` / `prev_hmac` 被 hand-edit 修改
- **THEN** `verify_chain_v3` 重算 HMAC ≠ 行内 hmac 字段
- **AND** fence exit 非 0,Blocker.type `dispatch_ledger_violation`,error message prefix `[hmac_mismatch] line <N>`

#### Scenario: 删除中间一行触发 chain_break BLOCKER

- **WHEN** v3 ledger 第 K 行(2 ≤ K ≤ N-1)被删除
- **THEN** 第 K+1 行的 `prev_hmac` ≠ 第 K-1 行的 `hmac`(chain 断裂)
- **AND** fence exit 非 0,error message prefix `[chain_break] line <K+1>`

#### Scenario: reorder 两行触发 chain_break BLOCKER

- **WHEN** v3 ledger 第 K 行与第 K+1 行交换顺序
- **THEN** 第 K+1 行(原第 K 行)的 `prev_hmac` ≠ 上一行(原第 K+1 行)的 `hmac`
- **AND** fence exit 非 0,error message prefix `[chain_break] line <K+1>`

#### Scenario: 首行 prev_hmac 非全 0 触发 chain_break BLOCKER

- **WHEN** v3 ledger 首行 `prev_hmac` ≠ `"0" * 64`(LLM 伪造首行 hmac)
- **THEN** fence exit 非 0,error message prefix `[chain_break] line 1: first-line prev_hmac MUST be all zeros`

#### Scenario: 同 ledger 内不同 key_id 触发 key_id_inconsistent BLOCKER

- **WHEN** v3 ledger 内不同行 `key_id` 不一致(如 LLM 中途切换 key)
- **THEN** fence exit 非 0,error message prefix `[key_id_inconsistent] line <N>: expected <key_id>, got <key_id>`

#### Scenario: ledger key_id ≠ 文件 key_id active v3 evidence 默认 fail-closed BLOCKER(round 1 codex F2 inline writeback)

- **WHEN** active v3 evidence(`evidence_frontmatter.ledger_archived_replay` 字段缺失或 `false` / `null`)+ ledger key_id 与当前 `~/.claude/forgeue_ledger_key` 派生的 key_id 不一致
- **THEN** fence BLOCKER(`key_id_mismatch`),error message prefix `[key_id_mismatch] ledger key_id <X> ≠ current file key_id <Y>; HMAC verify cannot proceed without rotated-from key — finish_gate fail-closed`
- **AND** **不**走 WARN 路径(攻击场景:LLM 替换 key 文件即可降级 HMAC 校 — 必须 fail-closed)
- **AND** Blocker.type `dispatch_ledger_violation`

#### Scenario: ledger key_id ≠ 文件 key_id archived replay 模式 user override(round 1 codex F2 inline writeback)

- **WHEN** evidence frontmatter `ledger_archived_replay: true`(opt-in user override;archived `enhance-workflow-automation-ledger-binding` 之前的归档 v3 evidence replay 时 user 显式标注)+ ledger key_id ≠ 当前 file key_id + ledger 自身 key_id 一致
- **THEN** fence WARN(`key_rotation_user_override_required`,exit 6 from cmd_verify;非 BLOCKER 但 audit 友好);error message prefix `[key_rotation_user_override] ledger key_id <X> ≠ current key_id <Y>; HMAC verify skipped per user opt-in — risk acknowledged`
- **AND** finish_gate 接受 archived replay,**但** evidence frontmatter `ledger_archived_replay: true` 字段 audit trail(任何回写 / archive 都保留此字段)
- **AND** `ledger_archived_replay: true` 字段需 user 显式手工添加(命令模板 default 不写入此字段;LLM 可在 controller drift 检测时 alert user 是否需要 opt-in)

#### Scenario: legacy / v1 / v2 evidence 不触 v3 fence

- **WHEN** evidence frontmatter 无 `runtime_enforcement_protocol_version` 字段 OR 值是 `v1` / `v2`
- **THEN** v3 fence 分支 pass-through(不 inspect ledger 的 v3 字段)
- **AND** archived v2 ledger 行(无 hmac 字段)在 v2 路径走 schema-only 校验,不强制 hmac 字段存在

### Requirement: ledger_forgery_resistance frontmatter field upgrade to cryptographic with strict gate

evidence frontmatter SHALL 含 `ledger_forgery_resistance` 字段(字符串字面值;沿 archived `enhance-workflow-automation-executable-enforcement` 同款字段);本字段 SHALL 与 `runtime_enforcement_protocol_version` 字段强 enum 绑定(沿 round 1 codex F4 inline writeback,审计字段必须与协议版本一致才能 audit 有意义)。

`forgeue_finish_gate.py` SHALL 含新 fence `_check_ledger_forgery_resistance_consistency`(本 change ship 加,沿 D-FrontmatterAuditConsistency)守门字段一致性:

| `runtime_enforcement_protocol_version` | `ledger_forgery_resistance` 强制值 | 不匹配处理 |
|---|---|---|
| 无字段(legacy) | 无字段约束(legacy pass-through) | — |
| `v1` | 无字段约束(v1 advisory pass-through) | — |
| `v2` | 必须 `advisory` | BLOCKER `frontmatter_audit_inconsistency` |
| `v3` | 必须 `cryptographic` | BLOCKER `frontmatter_audit_inconsistency` |

未来若加 multi-level enforcement(如 `cryptographic_strict` / `cryptographic_advisory`),扩 enum 时**同步扩 fence dispatch matrix**;不允许字段单独扩值不扩 fence(避免 audit 信号脱钩重现)。

命令模板 `change-apply-{subagent,parallel}.md` 的 evidence frontmatter 模板 SHALL 在 v3 协议路径下写 `ledger_forgery_resistance: cryptographic`;v2 路径写 `advisory`(self-dogfood gap 路径,沿 D-SelfDogfoodGap)。

#### Scenario: v3 evidence frontmatter 含 cryptographic 标注 fence pass

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v3` + `ledger_forgery_resistance: cryptographic`
- **THEN** `_check_ledger_forgery_resistance_consistency` fence pass

#### Scenario: v2 evidence frontmatter 含 advisory 标注 fence pass

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: advisory`(self-dogfood gap 路径)
- **THEN** `_check_ledger_forgery_resistance_consistency` fence pass

#### Scenario: v3 evidence 标 advisory(LLM 自降级伪造)BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v3` + `ledger_forgery_resistance: advisory`
- **THEN** `_check_ledger_forgery_resistance_consistency` fence exit 非 0
- **AND** Blocker.type `frontmatter_audit_inconsistency`,error message prefix `[audit_mismatch] v3 protocol requires ledger_forgery_resistance: cryptographic, got: advisory`

#### Scenario: v2 evidence 自称 cryptographic(LLM 虚报)BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: cryptographic`
- **THEN** `_check_ledger_forgery_resistance_consistency` fence exit 非 0
- **AND** Blocker.type `frontmatter_audit_inconsistency`,error message prefix `[audit_mismatch] v2 protocol requires ledger_forgery_resistance: advisory, got: cryptographic`

#### Scenario: legacy / v1 evidence 不强制字段(pass-through)

- **WHEN** evidence frontmatter 无 `runtime_enforcement_protocol_version` 字段 OR 值为 `v1`
- **THEN** `_check_ledger_forgery_resistance_consistency` fence pass-through(advisory pass)

### Requirement: v3 ledger terminal proof (line_count + final_hmac frontmatter audit)

evidence frontmatter SHALL 含 v3 必填字段(沿 round 1 codex F3 inline writeback;hash chain 抓不住 tail truncation 的 mitigation):

- `ledger_line_count: <int>`(声明 ledger 行数;**LLM 复制 wrapper `cmd_append` stdout 提示的行数**;wrapper-side 不自动写入 evidence;fence 校验与实际 ledger 行数一致)
- `ledger_final_hmac: <64 hex chars>`(声明 ledger 最后一行 hmac 值;**LLM 复制 wrapper `cmd_append` stdout 提示的 hmac**;fence 校验与实际 ledger 最后一行 hmac 一致)

`tools/forgeue_dispatch_ledger.py::cmd_append` SHALL 在每次成功 append 后 stdout 打印 `[LEDGER] line_count=<N> final_hmac=<hex>`(LLM 可读取此输出复制到 evidence frontmatter)。

`forgeue_finish_gate.py` SHALL 含新 fence `_check_ledger_terminal_proof`(本 change ship 加;沿 D-LedgerTerminalProof D-decision):

- v3 evidence(`runtime_enforcement_protocol_version: v3`)缺 `ledger_line_count` 字段 → BLOCKER `tail_truncation_undeclared`
- v3 evidence 缺 `ledger_final_hmac` 字段 → BLOCKER `final_hmac_undeclared`
- evidence `ledger_line_count` 不是正整数 → BLOCKER `tail_truncation_undeclared`(format check)
- evidence `ledger_final_hmac` 不是 `^[a-f0-9]{64}$` → BLOCKER `final_hmac_undeclared`(format check)
- evidence `ledger_line_count` ≠ 实际 ledger 非空行数 → BLOCKER `tail_truncation_detected`
- evidence `ledger_final_hmac` ≠ 实际 ledger 最后一行 hmac → BLOCKER `final_hmac_mismatch`
- v2 evidence 不强制本字段(pass-through)
- legacy / v1 evidence 不强制本字段(pass-through)

**Threat model 边界**(沿 design.md threat model 段):本 fence 抓 **常见 sloppy bypass**(LLM 删除尾部不更新 evidence frontmatter)+ **wrapper 跑过的 happy path**(LLM 不能伪造 wrapper stdout)。但 **不**承担 willful forge — LLM 可同时 forge ledger + 重写 evidence frontmatter line_count + final_hmac;那是 `enhance-workflow-automation-os-keystore` follow-on 的 threat model。

#### Scenario: v3 evidence 缺 ledger_line_count 字段 BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v3` + 缺 `ledger_line_count` 字段
- **THEN** `_check_ledger_terminal_proof` fence exit 非 0
- **AND** Blocker.type `dispatch_ledger_violation`,error message prefix `[tail_truncation_undeclared] v3 evidence MUST carry ledger_line_count field`

#### Scenario: v3 evidence 缺 ledger_final_hmac 字段 BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v3` + 缺 `ledger_final_hmac` 字段
- **THEN** `_check_ledger_terminal_proof` fence exit 非 0,error message prefix `[final_hmac_undeclared]`

#### Scenario: v3 evidence ledger_line_count 不匹配实际行数 BLOCKER(tail truncation 抓)

- **WHEN** v3 evidence `ledger_line_count: 5` 但实际 ledger 4 行(LLM 删了最后 1 行未更新 evidence)
- **THEN** `_check_ledger_terminal_proof` fence exit 非 0,error message prefix `[tail_truncation_detected] declared 5 lines, actual 4 lines`

#### Scenario: v3 evidence ledger_final_hmac 不匹配实际末行 BLOCKER

- **WHEN** v3 evidence `ledger_final_hmac: <X>` 但实际 ledger 最后一行 hmac = `<Y>`(LLM 删行后 evidence 字段未跟改 OR forge 攻击)
- **THEN** `_check_ledger_terminal_proof` fence exit 非 0,error message prefix `[final_hmac_mismatch] declared <X>, actual <Y>`

#### Scenario: v3 evidence terminal proof 全对 + chain verify 全对 fence pass

- **WHEN** v3 evidence + ledger N 行 chain 合法 + evidence `ledger_line_count: N` + `ledger_final_hmac` 等于实际末行 hmac
- **THEN** `_check_ledger_terminal_proof` fence pass + `_check_dispatch_ledger` v3 fence pass

#### Scenario: 单行 ledger v3 evidence 必含 line_count: 1

- **WHEN** v3 evidence + ledger 仅 1 行(prev_hmac 全 0)
- **THEN** evidence frontmatter MUST 含 `ledger_line_count: 1`(否则 BLOCKER tail_truncation_undeclared)
- **AND** evidence frontmatter MUST 含 `ledger_final_hmac` 等于该唯一行的 hmac(否则 BLOCKER final_hmac_mismatch)

### Requirement: v3 ledger strict 11-field schema validation

`tools/forgeue_dispatch_ledger.py::cmd_verify` v3 路径 + `forgeue_finish_gate.py::_check_dispatch_ledger` v3 分支 SHALL 在 HMAC chain verify 之外加 strict schema validation(沿 round 1 codex F5 scope expansion;HMAC 仅保护字节完整性,schema 校验是 orthogonal 必需层;本 change 合并 archived `executable-enforcement` P12.8 follow-on `enhance-workflow-automation-v2-fence-hardening` 的 schema 部分,P12.8 follow-on superseded)。

**v3 ledger 行 strict schema(11 字段精确)**:

| 字段 | 类型 | format / 约束 | 缺失行为 |
|---|---|---|---|
| `agent_id` | str | `^[a-f0-9]{17,}$`(沿 archived 同款 hex format,长度 ≥ 17) | BLOCKER `schema_violation` |
| `round` | int | 正整数(`isinstance(round, int) and round > 0 and not isinstance(round, bool)`,显式拒 bool;Python `bool` 是 `int` 子类) | BLOCKER |
| `role` | str | `VALID_ROLES` enum(沿 forgeue_dispatch_ledger 现有 frozenset:`implementer` / `spec_reviewer` / `code_quality_reviewer` / `final_reviewer` / `implementer_round_2_fix` / `spec_reviewer_round_2_review`) | BLOCKER |
| `task_subject_hash` | str / null | `null` 或 `^sha256:[a-f0-9]{64}$` | BLOCKER 若类型不对 |
| `dispatched_at` | str | ISO8601 tz-aware(`datetime.fromisoformat(...)` parse-able + `tzinfo is not None`) | BLOCKER |
| `parent_session_id` | str / null | `null` 或 UUID v4 format(`^[a-f0-9-]{36}$`) | BLOCKER 若类型不对 |
| `wrapper_version` | str | `^\d+\.\d+$`(major.minor) | BLOCKER |
| `protocol_version` | str | 精确 `"v3"` | BLOCKER |
| `key_id` | str | `^[a-f0-9]{16}$`(64-bit fingerprint) | BLOCKER |
| `prev_hmac` | str | `^[a-f0-9]{64}$` | BLOCKER |
| `hmac` | str | `^[a-f0-9]{64}$` | BLOCKER |

**严格性约束**:
- ledger 行字段集 **精确 11 字段**(任何 unknown 字段 → BLOCKER `schema_violation`,error prefix `[schema_violation] unknown field <field_name>`)
- 任何字段缺失 → BLOCKER `schema_violation`,error prefix `[schema_violation] missing field <field_name>`
- 字段类型 strict(`type(value) is <expected>`;不接受隐式转换 / 子类如 bool→int)
- 字段 format 正则严格匹配(全字符串)

**v2 ledger 行 schema validation**(沿现有 v2 fence advisory,本 change **不**加 v2 schema strict — 留给 cancelled P12.8 之外的独立 follow-on 若需要;沿 D-Scope-F3-MergeWithP12.8 边界本 change 仅做 v3 schema strict)。

#### Scenario: v3 ledger 行字段集精确 11 字段

- **WHEN** v3 ledger 行字段集恰好 11 字段(无多无少)+ 每字段类型 + format 正确
- **THEN** `_check_dispatch_ledger` v3 schema check pass

#### Scenario: v3 ledger 行未知字段 BLOCKER

- **WHEN** v3 ledger 行含 12 字段(11 标准 + `extra_field_xyz`)
- **THEN** fence exit 非 0,error prefix `[schema_violation] unknown field 'extra_field_xyz' at line <N>`

#### Scenario: v3 ledger 行字段缺失 BLOCKER

- **WHEN** v3 ledger 行缺 `key_id` 字段(其他 10 字段都在)
- **THEN** fence exit 非 0,error prefix `[schema_violation] missing field 'key_id' at line <N>`

#### Scenario: v3 ledger 行 round 为负数 BLOCKER

- **WHEN** v3 ledger 行 `round: -1`
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'round' MUST be positive integer, got: -1`

#### Scenario: v3 ledger 行 round 为 bool BLOCKER

- **WHEN** v3 ledger 行 `round: true`(JSON true 序列化为 Python bool;Python bool 是 int 子类但 schema 应显式拒)
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'round' MUST be positive integer (not bool), got: True`

#### Scenario: v3 ledger 行 round 为 float BLOCKER

- **WHEN** v3 ledger 行 `round: 1.0`
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'round' MUST be int, got: float`

#### Scenario: v3 ledger 行 agent_id 格式不对 BLOCKER

- **WHEN** v3 ledger 行 `agent_id: "not-a-hex"` OR `agent_id: ""`
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'agent_id' MUST match ^[a-f0-9]{17,}$`

#### Scenario: v3 ledger 行 role 不在 enum BLOCKER

- **WHEN** v3 ledger 行 `role: "unknown_role"`
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'role' MUST be in VALID_ROLES`

#### Scenario: v3 ledger 行 dispatched_at 无 tzinfo BLOCKER

- **WHEN** v3 ledger 行 `dispatched_at: "2026-05-06T14:00:00"`(无 timezone offset)
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'dispatched_at' MUST be ISO8601 tz-aware`

#### Scenario: v3 ledger 行 protocol_version 不是 "v3" BLOCKER

- **WHEN** v3 ledger 行 `protocol_version: "v2"` OR 任何其他值
- **THEN** fence exit 非 0,error prefix `[schema_violation] field 'protocol_version' MUST be exactly "v3"`

### Requirement: Runtime enforcement protocol_version validity gate

`forgeue_finish_gate.py` SHALL 含新 fence `_check_runtime_enforcement_protocol_version_validity`(本 change ship 加;沿 round 2 codex F2 inline writeback + D-RuntimeEnforcementProtocolVersionValidity)守门 evidence frontmatter `runtime_enforcement_protocol_version` 字段值合法性;此 fence SHALL 在所有 protocol-version-dependent fence 之前跑(`_check_dispatch_ledger` / `_check_round_fix_continuity` / `_check_skill_cascade` / `_check_ledger_terminal_proof` / `_check_ledger_forgery_resistance_consistency` / `_check_archived_replay_path_boundary`)以防 unknown value 走 skip 路径。

**核心 invariant**:fence skip 必须由 absence 决定(legacy pass-through),**不能**由 invalid value 决定(LLM 写错值不应该意外 unlock fence skip)。

**字段值合法性 dispatch**:

| evidence frontmatter `runtime_enforcement_protocol_version` | fence 行为 |
|---|---|
| 字段缺失(legacy) | pass-through(全 v1/v2/v3 fence skip) |
| 字段值 `v1` / `v2` / `v3`(in `_VALID_PROTOCOL_VERSIONS = frozenset({"v1", "v2", "v3"})`) | 走对应 fence dispatch matrix |
| 字段值 present 但不在 frozenset 内(`v4` / typo / empty / null) | **BLOCKER `unknown_protocol_version`** |

`_VALID_PROTOCOL_VERSIONS` SHALL 在 `tools/forgeue_finish_gate.py` / `tools/forgeue_change_state.py` / docs(`CLAUDE.md` + `forgeue_integrated_ai_workflow.md`)中保持一致;扩 frozenset 时同步扩 docs(沿 `forgeue_enum_cross_ref_check.py` 协议)。

#### Scenario: legacy evidence 无字段 pass-through

- **WHEN** evidence frontmatter 无 `runtime_enforcement_protocol_version` 字段
- **THEN** `_check_runtime_enforcement_protocol_version_validity` fence pass(legacy pass-through)
- **AND** 后续 protocol-version-dependent fence 全 skip(legacy 兼容)

#### Scenario: v1 / v2 / v3 evidence 走对应 fence dispatch

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v1` OR `v2` OR `v3`
- **THEN** `_check_runtime_enforcement_protocol_version_validity` fence pass
- **AND** 后续 fence 走对应 dispatch 路径

#### Scenario: unknown protocol_version v4 BLOCKER(round 2 codex F2 inline writeback)

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: v4`
- **THEN** `_check_runtime_enforcement_protocol_version_validity` fence exit 非 0
- **AND** Blocker.type `dispatch_ledger_violation`,error message prefix `[unknown_protocol_version] runtime_enforcement_protocol_version='v4' not in valid set {v1, v2, v3}; fence skip MUST come from absence not invalid value`

#### Scenario: typo protocol_version `v 3` BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: 'v 3'`(空格 typo)OR `'v3 '`(尾空格)OR `'V3'`(大小写不一致)
- **THEN** fence exit 非 0,error prefix `[unknown_protocol_version]`(LLM typo 不能 silent skip fence)

#### Scenario: empty / null protocol_version BLOCKER

- **WHEN** evidence frontmatter `runtime_enforcement_protocol_version: ''` OR `runtime_enforcement_protocol_version: null`
- **THEN** fence exit 非 0,error prefix `[unknown_protocol_version]`(present 但空值不等于 absent;absent 是字段完全不在 frontmatter 中)
- **NOTE**:absent(字段完全不在 frontmatter)走 legacy pass-through;present-but-empty 走 BLOCKER

### Requirement: Archived replay path boundary

`forgeue_finish_gate.py` SHALL 含新 fence `_check_archived_replay_path_boundary`(本 change ship 加;沿 round 2 codex F1 inline writeback + D-ArchivedReplayPathBoundary)守门 `ledger_archived_replay` evidence frontmatter 字段使用边界。

**字段使用规则**:

| evidence 文件路径 | `ledger_archived_replay` 字段值 | fence 行为 |
|---|---|---|
| 任何路径 | 缺失 / `false` / `null` | pass-through(default 路径) |
| 含 `openspec/changes/archive/` segment(`Path.resolve()` 后) | `true` | 接受 archived replay opt-in;走 D-KeyRotationHandling user override 路径(WARN exit 6) |
| 不含 `archive/` segment(active change `openspec/changes/<id>/`) | `true` | **BLOCKER `archived_replay_path_violation`**(LLM 在 active change forge 此字段企图绕 fail-closed) |

`tools/forgeue_dispatch_ledger.py::cmd_verify` `--allow-archived-replay` flag 同款边界 — 仅在 ledger 路径在 `openspec/changes/archive/` 内才 honor flag;active change ledger 路径 + flag → BLOCKER + 提示 ledger 不在 archive 路径。

`tools/forgeue_change_state.py --writeback-check` SHALL 同步加此 invariant 检测(active change evidence 出现 `ledger_archived_replay: true` = drift signal,作为 4 类 named DRIFT 之一)。

**核心 invariant**:archived replay 路径不仅要 user explicit opt-in(双 flag),还要 evidence 物理位置在 archive/ 目录(物证驱动);LLM 即使 forge frontmatter + 替换 key 文件,只要 evidence 不在 archive/ 段,fence BLOCKER。

#### Scenario: active change evidence + ledger_archived_replay: true BLOCKER(round 2 codex F1 inline writeback)

- **WHEN** evidence 文件路径 `openspec/changes/<id>/review/foo.md`(active change,不在 archive/)+ frontmatter `ledger_archived_replay: true`
- **THEN** `_check_archived_replay_path_boundary` fence exit 非 0
- **AND** Blocker.type `dispatch_ledger_violation`,error message prefix `[archived_replay_path_violation] evidence path '<path>' does not contain 'archive/' segment but ledger_archived_replay=true; archived replay opt-in only allowed for archived evidence`

#### Scenario: archive evidence + ledger_archived_replay: true 走 user override(allowed)

- **WHEN** evidence 文件路径 `openspec/changes/archive/2026-MM-DD-<id>/review/foo.md`(archived)+ frontmatter `ledger_archived_replay: true` + cmd_verify 配套 `--allow-archived-replay` flag + ledger key_id ≠ 当前 file key_id
- **THEN** `_check_archived_replay_path_boundary` fence pass(在 archive/ 路径,字段允许)
- **AND** 后续 v3 verify 走 D-KeyRotationHandling user override 路径(WARN exit 6)

#### Scenario: archive evidence + ledger_archived_replay: true 但缺 cmd_verify flag

- **WHEN** evidence 在 archive/ 路径 + frontmatter `ledger_archived_replay: true` + cmd_verify 缺 `--allow-archived-replay` flag
- **THEN** `_check_archived_replay_path_boundary` fence pass(字段允许),但 cmd_verify v3 verify 走 default 路径
- **AND** key_id mismatch → BLOCKER(default fail-closed,沿 D-KeyRotationHandling default 路径)
- **AND** 仅在 user 显式加 flag + frontmatter 字段 + archive/ 路径**三重 explicit opt-in** 时才走 user override

#### Scenario: cmd_verify --allow-archived-replay flag + ledger 不在 archive/ 路径 BLOCKER

- **WHEN** ledger 路径 `openspec/changes/<active-id>/dispatch_ledger.jsonl`(active)+ cmd_verify `--allow-archived-replay` flag
- **THEN** cmd_verify exit 5(`archived_replay_path_violation`),stderr 提示 ledger 不在 archive/ 路径,`--allow-archived-replay` flag rejected

#### Scenario: forgeue_change_state.py --writeback-check 检测 active change evidence 误用

- **WHEN** 跑 `python tools/forgeue_change_state.py --change <active-id> --writeback-check --json` + active change evidence 含 `ledger_archived_replay: true`
- **THEN** writeback-check exit 5 + 4 类 named DRIFT 之一标记
- **AND** alert user 字段使用错误,提示移除字段或 archive change 后再标

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
