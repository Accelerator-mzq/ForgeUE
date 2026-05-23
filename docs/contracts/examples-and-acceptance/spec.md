# examples-and-acceptance

## Purpose

Examples-and-acceptance treats each bundle under `examples/` as an end-to-end acceptance artifact: a TaskBundle JSON is simultaneously a user-facing how-to, a loader contract test, an integration-test fixture, and a live-run entry point. This spec pins the bundle contract, the P0-P4 / L-layer mapping, and the offline-versus-live split so a future change never breaks the "one bundle, one acceptance path" promise.

## Source Documents

- `docs/requirements/SRS.md` §5.5 (configuration interface: `examples/*.json` row)
- `docs/acceptance/acceptance_report.md` §3 (P0-P4 / L1-L4 / F1-F5 / Plan C status), §6.1 (A1 UE 5.7.4 hardware smoke), §6.2 (bundle evidence taxonomy updated under TBD-008)
- `README.md` §"Bundle 与 Example" (original five bundles; see doc-drift note below)
- `CHANGELOG.md` [Unreleased] (parametrized live bundles, A1 / a2_mesh live bundle expansion)
- Source: `examples/mock_linear.json`, `character_extract.json`, `review_3_images.json`, `image_pipeline.json`, `image_edit_pipeline.json`, `image_to_3d_pipeline.json`, `image_to_3d_pipeline_live.json`, `ue_export_pipeline.json`, `ue_export_pipeline_live.json`, `godot4_export_smoke.json`, `ue5_api_query.json`
- Source: `src/framework/workflows/loader.py::load_task_bundle`
- Source: `src/framework/workflows/loader.py::expand_model_refs`
- Source: `tests/integration/test_p{0,1,2,3,4}_*.py`, `test_l4_image_to_3d.py`, `test_image_edit.py`, `test_dag_concurrency.py`, `test_example_bundles_smoke.py`, `test_ws_progress.py`

## Current Behavior

A bundle is a JSON document containing three sections: a `Task` (with `task_type`, `run_mode`, `engine_target` or legacy `ue_target`, `review_policy`, bundled Policies), a `Workflow` (control-semantic Step graph with metadata), and a `Steps` array. The loader is `load_task_bundle`, which reads UTF-8 (avoiding Windows stdin gbk), expands `provider_policy.models_ref` into `prepared_routes` via `expand_model_refs(raw, get_model_registry())`, and then runs Pydantic validation. Callers that bypass the loader will hit `generate_structured failed: ProviderPolicy has no preferred or fallback models`.

Bundles under `examples/` each tie to one acceptance scenario:

- `mock_linear.json` — P0, pure-mock linear three-step (offline, no API key)
- `character_extract.json` — P1, LLM structured extraction into `UECharacter` (requires `--live-llm`)
- `review_3_images.json` — P2, standalone review with three inline candidates
- `image_pipeline.json` — P3, production pipeline with ComfyUI generation + inline review + export
- `image_edit_pipeline.json` — L5-A, prompt + source image → edited image via `image_edit` alias
- `image_to_3d_pipeline.json` — L4, image → 3D mesh contract bundle
- `image_to_3d_pipeline_live.json` — L4, live-provider variant (Hunyuan 3D opt-in)
- `ue_export_pipeline.json` — P4, UE manifest-only export via FakeComfy placeholder
- `ue_export_pipeline_live.json` — A1, live-provider variant used for the 2026-04-23 UE 5.7.4 commandlet hardware smoke
- `godot4_export_smoke.json` — P4-Godot, `engine_target.engine="godot4"` headless import bundle shape
- `ue5_api_query.json` — L1, UE5 Python API question answering via `ue5_api_assist` alias

Each bundle is covered by at least one integration test; `test_example_bundles_smoke.py` is the loader-contract fence that ensures every JSON under `examples/` can still be parsed after any change.
## Requirements
## Requirement: Bundle is the end-to-end acceptance artifact

The system SHALL treat every JSON file under `examples/` as simultaneously a how-to, a loader contract test, and (for P0-P4 / L-layer files) an integration-test fixture.

## Scenario: examples/mock_linear.json runs the P0 acceptance pipeline end-to-end

- GIVEN `examples/mock_linear.json` declaring three mock steps (`generate-mock` → `validate` → `export-noop`) and `tests/integration/test_p0_mock_linear.py::test_first_run_produces_3_artifacts_and_3_checkpoints` referencing it as `bundle_path`
- WHEN the test loads the bundle via `load_task_bundle` and runs it through the offline `Orchestrator` with mock executors
- THEN the run reaches `RunStatus.succeeded`, visits all three step ids in declaration order, persists three Checkpoints + at least three Artifacts, and reports zero cache hits on first run — the same JSON file is both the user-facing example and the P0 acceptance fixture

## Requirement: UTF-8 bundles go through the loader

The system SHALL require callers to read bundles via `framework.workflows.loader.load_task_bundle`; direct `json.load(open(...))` is forbidden because Windows stdin is gbk and bundles may carry UTF-8 full-width quotes.

## Scenario: load_task_bundle reads UTF-8 bundle without UnicodeDecodeError on Windows

- GIVEN a bundle under `examples/` whose `task.title` or `task.description` contains UTF-8 non-ASCII characters (e.g. full-width quotes / Chinese description text such as `examples/ue_export_pipeline_live.json`)
- WHEN code calls `framework.workflows.loader.load_task_bundle(path)` on a Windows host whose default locale encoding is gbk
- THEN the loader reads the file as UTF-8 (`Path(path).read_text(encoding="utf-8")` at `src/framework/workflows/loader.py`) and returns a populated `TaskBundle` without `UnicodeDecodeError`, while a hypothetical `json.load(open(path))` call without explicit encoding would have crashed under the same locale

## Requirement: Alias-based model references

The system SHALL resolve `provider_policy.models_ref: "<alias>"` via `expand_model_refs(raw, get_model_registry())` before Pydantic validation; a bundle MAY additionally declare `preferred_models` / `fallback_models` to override the alias at Step scope.

## Scenario: Bundle declaring models_ref text_cheap is expanded via ModelRegistry before validation

- GIVEN a bundle Step whose `provider_policy` declares `models_ref: "text_cheap"` and no inline `preferred_models` / `fallback_models` (e.g. `examples/character_extract.json` `step_extract`)
- WHEN `load_task_bundle` runs `expand_model_refs(raw, get_model_registry())` on the parsed dict before any `Step.model_validate` call
- THEN the alias is replaced in-place by concrete `preferred_models` / `fallback_models` lists drawn from `config/models.yaml` `aliases.text_cheap`, the resulting Step passes Pydantic validation, and the bundle never reaches the runtime carrying a bare `models_ref` string

## Requirement: No hardcoded provider model ids

The system SHALL declare model selection via `provider_policy.models_ref` for every bundle under `examples/`. Concrete provider model ids MUST live in `config/models.yaml`'s `models` section, not in the bundle. A Step MAY additionally declare `preferred_models` / `fallback_models` as a Step-scoped override, but every entry MUST be a model id already registered in `config/models.yaml.models` so the registry remains the single source of routing config.

## Scenario: Every bundle under examples/ resolves model selection via models_ref

- GIVEN the ten bundles currently shipped under `examples/` (`mock_linear.json`, `character_extract.json`, `review_3_images.json`, `image_pipeline.json`, `image_edit_pipeline.json`, `image_to_3d_pipeline.json`, `image_to_3d_pipeline_live.json`, `ue_export_pipeline.json`, `ue_export_pipeline_live.json`, `ue5_api_query.json`)
- WHEN their `provider_policy` blocks are inspected (mock-only bundles such as `mock_linear.json` exempt because they declare no `provider_policy`)
- THEN every non-mock Step declares `provider_policy.models_ref: "<alias>"` (e.g. `text_cheap` / `image_fast` / `review_judge_visual` / `image_edit` / `ue5_api_assist`), no Step inlines a concrete provider model id (no `qwen/...` / `hunyuan/...` / `openai/...` literal in the bundle JSON), and any future Step adding `preferred_models` / `fallback_models` MUST list ids that resolve through `config/models.yaml` `models` section

## Requirement: Loader-contract fence for every bundle

The system SHALL load every JSON under `examples/` through `load_task_bundle` in `tests/integration/test_example_bundles_smoke.py`; adding a new bundle MUST be accompanied by at least one integration-test assertion for it.

## Scenario: examples/godot4_export_smoke.json documents the Godot 4 engine_target shape

- GIVEN `examples/godot4_export_smoke.json` declares `task.engine_target.engine == "godot4"` and a final export step with `capability_ref == "engine.export"`
- WHEN `tests/integration/test_example_bundles_smoke.py::test_godot4_export_smoke_bundle_loads` loads the bundle through `load_task_bundle`
- THEN the Task validates with a populated `engine_target`, the workflow exposes the export step, and future Godot example edits stay covered by the loader-contract fence

## Scenario: A new bundle is added

- GIVEN a new `examples/<new>.json` is committed
- WHEN the test suite runs
- THEN `test_example_bundles_smoke.py` loads the file through `load_task_bundle` without error and an integration test exercises at least its loader + execution path

## Requirement: Stage-aligned acceptance coverage

The system SHALL keep the P0 / P1 / P2 / P3 / P4 / L1 / L4 coverage mapping: each stage has a matching bundle + integration test, and bundle-level changes that affect a stage SHALL update the corresponding integration test in the same change.

## Scenario: Each P0-P4 stage has a dedicated integration test referencing its bundle

- GIVEN the P0-P4 acceptance taxonomy declared in `docs/acceptance/acceptance_report.md` §3
- WHEN `tests/integration/` is inspected for stage-aligned tests
- THEN `test_p0_mock_linear.py` references `examples/mock_linear.json`, `test_p1_structured_extraction.py` references `examples/character_extract.json`, `test_p2_standalone_review.py` references `examples/review_3_images.json`, `test_p3_production_pipeline.py` references `examples/image_pipeline.json`, and `test_p4_ue_manifest_only.py` references `examples/ue_export_pipeline.json` — and a bundle change touching any stage MUST land alongside an update to the matching `test_p[0-4]_*.py` file in the same commit

## Requirement: Live bundles carry premium-API warnings

The system SHALL mark any bundle that triggers a premium per-call API (mesh.generation via `image_to_3d_pipeline_live.json`, `ue_export_pipeline_live.json`) with a review-policy or documentation note pointing to ADR-007 and to the corresponding `probes/provider/probe_*` opt-in fallback.

## Scenario: image_to_3d_pipeline_live.json fails closed at routing time when run without --live-llm

- GIVEN `examples/image_to_3d_pipeline_live.json` whose `step_image` declares `provider_policy.models_ref: "image_fast"` (an alias that resolves to real provider model ids in `config/models.yaml`)
- WHEN `framework.run.main` is invoked on this bundle without the `--live-llm` flag, so `_build_orchestrator` constructs a `CapabilityRouter` that does NOT register `LiteLLMAdapter` / `QwenMultimodalAdapter` / `HunyuanImageAdapter` (see `src/framework/run.py` adapter-registration block guarded by `if use_live_llm:`)
- THEN at routing time the run fails closed because no registered adapter reports `supports(model)=True` for the resolved real-provider model ids, surfacing a routing / no-available-adapter error rather than silently substituting a fake provider — and this fail-closed behaviour holds without the loader needing to inspect the `--live-llm` flag itself

## Requirement: UE hardware smoke is reachable via commandlet

The system SHALL provide an entry point for the UE 5.x hardware smoke that does not require GUI interaction: `PYTHONPATH=src python -m framework.run --task examples/ue_export_pipeline_live.json --live-llm --run-id a1_demo` followed by a commandlet invocation of `ue_scripts/a1_run.py`.

## Scenario: ue_scripts/a1_run.py boots a UE Python session and consumes ue_export_pipeline_live.json import_plan without GUI

- GIVEN `ue_scripts/a1_run.py` is invoked from a UE 5.x Python session via either `Tools / File → Execute Python Script...` or `exec(open(...).read())` in the Python Console / commandlet (per the module docstring) on a host where the prior `framework.run --task examples/ue_export_pipeline_live.json --live-llm` step has materialised an `import_plan.json` under `Content/Generated/a1_demo/`
- WHEN the script runs
- THEN it sets `FORGEUE_RUN_FOLDER` to the run directory, prepends `ue_scripts/` to `sys.path`, imports `run_import`, and calls `run_import.run()` to consume the existing `import_plan` — providing a GUI-free, commandlet-reachable entry point, without asserting that any particular host machine succeeds end-to-end (UE install / asset content correctness remain the human operator's responsibility, see `docs/acceptance/acceptance_report.md` §6.1 for the 2026-04-23 UE 5.7.4 reference run)

## Requirement: Fixture Run directories for comparison tests

The system SHALL provide Run-directory fixtures under `tests/fixtures/comparison/` that simulate the output layout of a completed Run (`run_summary.json` + `_artifacts.json` + payload files + optional `ReviewReport` / `Verdict` JSON files). These fixtures MUST be consumable by the comparison module without invoking the full Orchestrator pipeline.

## Scenario: A static fixture pair drives a deterministic diff test

- GIVEN `tests/fixtures/comparison/baseline_run/` and `tests/fixtures/comparison/candidate_run/` prepared with known per-artifact divergences
- WHEN a unit test calls `framework.comparison.diff_engine.compare(...)` against both snapshots
- THEN the resulting `RunComparisonReport.summary_counts` matches the expected diff taxonomy (unchanged / content_changed / metadata_only / missing / decision_changed)

## Requirement: Fixture Runs are offline and provider-key-free

The system SHALL author all comparison fixtures such that no API key, no network call, and no UE / ComfyUI process is required to generate or consume them; either the fixture is authored statically (JSON + placeholder bytes on disk) or it is generated by rerunning `examples/mock_linear.json` through the offline `FakeAdapter` + `FakeComfyWorker` path.

## Scenario: Fixture pipeline runs without API keys, network, or external processes

- GIVEN the test environment has no `.env` and no provider API keys exported, no network is reachable, and no UE editor / ComfyUI process is running
- WHEN `tests/fixtures/comparison/builders.py::build_fixture_pair(root)` is called, OR `python -m framework.run --task examples/mock_linear.json --run-id <id> --artifact-root <root>` is invoked without `--live-llm` and without `--comfy-url`
- THEN the resulting Run directories materialise on disk and are immediately consumable by `python -m framework.comparison`; no provider key is read, no HTTP request is issued, no UE / ComfyUI process is started, and the FakeAdapter + FakeComfyWorker handle every generation step

## Requirement: Fixture Runs do not pollute top-level artifact buckets

The system SHALL place all comparison test fixtures under `tests/fixtures/comparison/`; they MUST NOT be committed under `./artifacts/` or `./demo_artifacts/` (both of which remain gitignored per the project-level .gitignore). Dynamic fixture output (e.g. comparison report produced during a test) MUST land in `tmp_path` or the pytest-provided temporary directory, never in `./artifacts/` or `./demo_artifacts/`.

## Scenario: Fixture builders write only to caller-provided root

- GIVEN an integration test invokes `build_fixture_pair(tmp_path / "real_artifacts" / "2000-01-01")` and then runs `python -m framework.comparison --artifact-root <...>/real_artifacts --output-dir tmp_path / "out"`
- WHEN the test completes
- THEN every produced file is rooted under the caller-provided `tmp_path`; a recursive pre/post snapshot of `<repo>/demo_artifacts/` and `<repo>/artifacts/` shows byte-identical contents (no added / removed / modified files), proving the comparison run did not leak into either gitignored top-level bucket

## Requirement: Date bucket handling in fixtures

The system SHALL NOT hardcode real calendar dates into fixture Run directories; fixtures MUST either use a synthetic date bucket (e.g. `2000-01-01`) or mock the date resolution path so tests remain stable over time.

## Scenario: Builder uses a synthetic date bucket regardless of wall clock

- GIVEN the test runs on any calendar day (e.g. 2026-04-25 or 2030-01-01)
- WHEN `build_fixture_pair(root)` lays out fixture Run directories
- THEN they live under `<root>/2000-01-01/<run_id>/` regardless of `datetime.now()`; payload bytes, recorded `created_at`, and `Checkpoint.completed_at` are all derived from fixed constants, so fixture output stays byte-deterministic over time and no real calendar date leaks into hashes or paths

## Requirement: ComfyUI live smoke bundle uses manifest workflow not inline graph

The system SHALL ship `examples/comfy_local_smoke.json` as the canonical live smoke entry for ComfyUI integration. The bundle SHALL declare its image generation step via `step.config.spec.comfy_workflow` (manifest name, e.g. `GameAssets/01b_singleview_sdxl`) + `step.config.spec.comfy_params` (JSON dict of params accepted by that manifest's `python -m comfyui_api params --workflow <name>` schema) + `step.config.spec.comfy_lifecycle` (one of the four lifecycle modes). The bundle MUST NOT inline a `workflow_graph` JSON. The legacy v1 inline-workflow bundle path (and its supporting `examples/comfy/build_bundle.py` + `examples/comfy/tavern_door.api.json` + `examples/comfy/image_z_image_turbo.json` files) is preserved in git history at commit `292420a` for diff reference and SHALL NOT be reintroduced.

## Scenario: examples/comfy_local_smoke.json declares manifest workflow name + params

**Given** the post-change `examples/comfy_local_smoke.json` loaded via `framework.workflows.loader.load_task_bundle`
**When** the loader reads `steps[0].config.spec`
**Then** the spec contains `comfy_workflow` (string, e.g. `"GameAssets/01b_singleview_sdxl"`), `comfy_params` (dict), optionally `comfy_lifecycle` (string), and contains NO `workflow_graph` field; the bundle is < 5 KB (the v1 path with inlined SD1.5 workflow_graph at commit 292420a is 154 lines / ~5 KB on its own)

## Scenario: examples/comfy/ legacy helper directory is removed

**Given** the post-change repository tree
**When** the contents of `examples/comfy/` are inspected
**Then** `examples/comfy/build_bundle.py`, `examples/comfy/tavern_door.api.json`, and `examples/comfy/image_z_image_turbo.json` no longer exist on the working tree (commit history retains them through `git show 292420a:examples/comfy/<file>`); the `examples/comfy/` directory itself MAY remain only if it carries the new manifest-style assets, otherwise it SHALL be removed

## Requirement: Live ComfyUI smoke is gated behind agent-CLI availability

The system SHALL document in the bundle's loader-test smoke + in CLAUDE.md that running `examples/comfy_local_smoke.json` end-to-end requires (1) ComfyUI installed under a host-specific path, (2) `python -m comfyui_api` agent CLI available under the path declared in `config/models.yaml` `providers.comfy_api.scripts_dir`, and (3) `python -m framework.run --task examples/comfy_local_smoke.json --live-llm`. The offline loader-contract test SHALL still pass without any of those preconditions because the loader does not invoke the worker.

## Scenario: comfy_local_smoke.json passes the offline loader-contract fence without a real ComfyUI

**Given** a CI runner without ComfyUI installed and without `D:/AI/ComfyUI/scripts/`
**When** `tests/integration/test_example_bundles_smoke.py` loads `examples/comfy_local_smoke.json` through `load_task_bundle`
**Then** the bundle parses cleanly into a `TaskBundle`, no subprocess is spawned, and the smoke test asserts only loader-level invariants (`comfy_workflow` is a string, `comfy_params` is a dict, alias / model-id rules satisfied) — exactly mirroring the existing fence pattern for `image_to_3d_pipeline_live.json`

## Requirement: ComfyUI mesh live smoke bundle is image-to-mesh with upstream image step + DAG dependency

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

## Scenario: examples/comfy_local_smoke_mesh.json declares image-to-mesh DAG with mesh_local alias

**Given** the post-change `examples/comfy_local_smoke_mesh.json` loaded via `framework.workflows.loader.load_task_bundle`
**When** the loader reads the bundle structure
**Then** the bundle contains AT LEAST two steps; the upstream image step's `provider_policy.models_ref` is `"image_local"` (or `"image_fast"`) and produces an `image.candidate` Artifact; the mesh step's `provider_policy.models_ref` is `"mesh_local"`, has a DAG `depends_on` reference to the image step, and `step.config.spec` contains `comfy_workflow` (string, real ComfyUI mesh manifest name), `comfy_params` (dict, NOT containing the image input key — that's injected at runtime), `comfy_image_param_key` (optional, defaults to `"image_path"`), `comfy_lifecycle: "none"`, and contains NO `workflow_graph` field; after `expand_model_refs`, the mesh step's resolved `prepared_routes` contains exactly one route with `model="comfy/local-mesh"`

## Scenario: examples/comfy_local_smoke.json (image-mode) is preserved and unchanged

**Given** the post-change repository tree
**When** `examples/comfy_local_smoke.json` is inspected
**Then** the image-mode smoke bundle from `comfy-agent-cli-adoption` exists unchanged at the same path; both bundles coexist and exercise different ComfyAgentWorker capability modes; users selecting between them via `--task examples/comfy_local_smoke.json` (single image step) vs `--task examples/comfy_local_smoke_mesh.json` (image step → mesh step) get image-only vs full image-to-mesh pipeline respectively

## Requirement: Live ComfyUI mesh smoke is gated behind agent-CLI mesh manifest availability + image manifest availability

The system SHALL document in the bundle's loader-test smoke + in CLAUDE.md (ComfyUI section) that running `examples/comfy_local_smoke_mesh.json` end-to-end requires:

1. ComfyUI installed under a host-specific path with at least one image workflow manifest available (for the upstream image step) AND at least one image-to-mesh workflow manifest available (for the mesh step)
2. `python -m comfyui_api list` output containing both manifest names referenced by the bundle
3. `FORGEUE_COMFY_SCRIPTS_DIR` pointing to that ComfyUI's `scripts/` directory
4. (If using `image_fast` for the upstream step instead of `image_local`) the cloud image provider API key (`DASHSCOPE_API_KEY` etc.)
5. `python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm`

The offline loader-contract test SHALL still pass without any of those preconditions because the loader does not invoke any worker. CLAUDE.md SHALL be updated to reflect the dual smoke bundles (image-only + image-to-mesh) and to note that mesh smoke produces a `.glb` file under `artifacts/<today>/<run_id>/<artifact_id>.glb` (the in-tree filename is `<artifact_id>.glb` via `repo.put` + `file_suffix=".glb"`, NOT the original ComfyUI filename — see artifact-contract spec).

## Scenario: comfy_local_smoke_mesh.json passes the offline loader-contract fence without a real ComfyUI

**Given** a CI runner without ComfyUI installed and without `D:/AI/ComfyUI/scripts/`
**When** `tests/integration/test_example_bundles_smoke.py` loads `examples/comfy_local_smoke_mesh.json` through `load_task_bundle`
**Then** the bundle parses cleanly into a `TaskBundle` (both image step and mesh step), no subprocess is spawned, and the smoke test asserts only loader-level invariants (image step's `comfy_workflow` is a string, mesh step's `comfy_workflow` is a string, mesh step's `comfy_params` is a dict, both lifecycles equal `"none"`, mesh step's `prepared_routes` contains `comfy/local-mesh`, mesh step has DAG `depends_on` reference to image step); the same generic structural fence (`test_bundle_dry_run_passes` etc.) applies and SHALL continue to emit only `warning_only=True` for the missing ComfyUI probe (per `comfy-agent-cli-adoption` G8 commit 7 drift writeback contract)

## Scenario: Live mesh smoke evidence is captured in change notes after manual run

**Given** the implementer has run `python -m framework.run --task examples/comfy_local_smoke_mesh.json --live-llm --run-id mesh_smoke_<date>` on a host with ComfyUI installed and both image + mesh manifests available
**When** the run completes successfully (image step produces an image artifact, mesh step consumes it via `_resolve_source_image` and produces a GLB artifact)
**Then** the resulting `.glb` file lives under `artifacts/<date>/mesh_smoke_<date>/<mesh_artifact_id>.glb` (in-tree, NFR-PORT-004 satisfied via `repo.put` + `FileBackend`); the GLB passes magic-bytes validation (starts with `b"glTF"`); the source image PNG is preserved at `artifacts/<date>/mesh_smoke_<date>/comfy/input/<sha1>.png` (in-tree per artifact-contract); a live smoke evidence file is written to `openspec/changes/comfy-agent-cli-mesh-audio-video-adoption/notes/live_smoke_mesh_<date>.md` recording: image manifest name, mesh manifest name, mesh `comfy_image_param_key` actual value, mesh `comfy_params`, run_id, GLB artifact_id + file path + size, source image artifact_id + path, `Artifact.metadata["worker_metadata"]` dump showing comfy provenance — mirroring the format of the image-change `live_smoke_20260503.md` evidence file

## Requirement: ComfyUI audio live smoke bundle is text-to-audio with single generate / capability_ref="audio.t2a" step

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

## Scenario: examples/comfy_local_smoke_audio.json declares text-to-audio single step with audio_local alias and canonical loader schema

**Given** the post-change `examples/comfy_local_smoke_audio.json` loaded via `framework.workflows.loader.load_task_bundle`
**When** the loader reads the bundle structure
**Then** (F-Plan-1 round-2 plan 修订:bundle has canonical top-level three-section schema) the JSON has top-level keys `task` + `workflow` + `steps` (NOT nested `workflow.steps[]`); `Task.model_validate(raw["task"])` parses cleanly; `Workflow.model_validate(raw["workflow"])` parses cleanly with `step_ids` listing one step (no `steps` nested under workflow); `[Step.model_validate(s) for s in raw["steps"]]` produces exactly one Step; the step's `type == StepType.generate` (`"generate"` in JSON); `step.capability_ref == "audio.t2a"`; `step.provider_policy.models_ref == "audio_local"`; `step.provider_policy.capability_required == "audio.t2a"`; (F-Plan-6 round-2 plan 修订) `step.retry_policy` if present contains only `max_attempts/backoff/retry_on` (no `timeout_seconds`); `step.config.worker_timeout_s` is the subprocess timeout source (e.g. 300); `step.config.spec` contains `comfy_workflow` (string, real ComfyUI audio manifest name), `comfy_params` (dict containing prompt key matching the manifest's expected schema, e.g. `text` for Stable Audio or `tags` for ACE-Step), `comfy_lifecycle: "none"`, and contains NO `workflow_graph` field, NO `comfy_image_param_key` field; after `expand_model_refs`, the resolved `prepared_routes` contains exactly one route with `model="comfy/local-audio"`

## Scenario: examples/comfy_local_smoke.json (image) and examples/comfy_local_smoke_mesh.json (mesh) are preserved unchanged

**Given** the post-change repository tree
**When** `examples/comfy_local_smoke.json` and `examples/comfy_local_smoke_mesh.json` are inspected
**Then** both prior smoke bundles exist unchanged at the same paths; all three bundles coexist and exercise different ComfyAgentWorker capability modes; users selecting between them via `--task examples/comfy_local_smoke.json` (image), `--task examples/comfy_local_smoke_mesh.json` (image-to-mesh), or `--task examples/comfy_local_smoke_audio.json` (text-to-audio) get the corresponding capability path

## Requirement: Live ComfyUI audio smoke is gated behind agent-CLI audio manifest availability

The system SHALL document in the bundle's loader-test smoke + in CLAUDE.md (ComfyUI section) that running `examples/comfy_local_smoke_audio.json` end-to-end requires:

1. ComfyUI installed under a host-specific path with at least one audio workflow manifest available (default: `Audio_Workflows/audio_stable_audio_example` — Stable Audio Open 1.0; alternative: `Audio_Workflows/audio_ace_step_1_t2a_instrumentals` — ACE-Step v1 3.5B, requires ACE-Step custom node installation)
2. `python -m comfyui_api list` output containing the manifest name referenced by the bundle
3. `FORGEUE_COMFY_SCRIPTS_DIR` pointing to that ComfyUI's `scripts/` directory; **NO** `FORGEUE_COMFY_INPUT_DIR` env var required (audio has no source bytes path — that env var is mesh-specific)
4. First run: ComfyUI auto-downloads model weights from HuggingFace (Stable Audio Open ~2GB, ACE-Step ~7GB); subsequent runs use the cache
5. `python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm`

The offline loader-contract test SHALL still pass without any of those preconditions because the loader does not invoke any worker. CLAUDE.md SHALL be updated to reflect the triple smoke bundles (image / mesh / audio) and to note that audio smoke produces a `.flac` (or `.mp3` / `.wav` depending on manifest output) file under `artifacts/<today>/<run_id>/<artifact_id>.flac` (the in-tree filename is `<artifact_id>.<format>` via `repo.put` + `file_suffix=f".{cand.format}"`, NOT the original ComfyUI filename — see artifact-contract spec).

## Scenario: comfy_local_smoke_audio.json passes the offline loader-contract fence without a real ComfyUI

**Given** a CI runner without ComfyUI installed and without `D:/AI/ComfyUI/scripts/`
**When** `tests/integration/test_example_bundles_smoke.py` loads `examples/comfy_local_smoke_audio.json` through `load_task_bundle`
**Then** the bundle parses cleanly into a `TaskBundle`, no subprocess is spawned, and the smoke test asserts only loader-level invariants (`comfy_workflow` is a string, `comfy_params` is a dict containing at least one prompt-like key, `audio_local` alias resolves to `comfy/local-audio`, no `workflow_graph` field, no `comfy_image_param_key` field, `depends_on` is empty); mirrors the existing fence pattern for `comfy_local_smoke.json` and `comfy_local_smoke_mesh.json`

## Requirement: Remote audio smoke bundle uses audio_remote alias

The system SHALL ship `examples/remote_audio_smoke.json` as an offline loader/dry-run smoke for FOR-26. The bundle SHALL contain one `StepType.generate` step with `capability_ref == "audio.t2a"` and `provider_policy.models_ref == "audio_remote"`. The bundle SHALL not embed a provider endpoint or API key; real endpoint selection remains runtime env (`FORGEUE_REMOTE_AUDIO_URL` / optional API key/model).

## Scenario: examples/remote_audio_smoke.json loads and dry-runs without network I/O

**Given** `examples/remote_audio_smoke.json`
**When** `load_task_bundle(path)` and `DryRunPass.run(...)` execute in tests
**Then** the bundle parses cleanly, `audio_remote` resolves to `remote/audio`, no network call is made, and `tests/integration/test_example_bundles_smoke.py` auto-discovers the bundle.

## Requirement: MiniMax music smoke bundle uses audio_minimax alias

The system SHALL ship `examples/minimax_music_smoke.json` as an offline loader/dry-run smoke for the FOR-26 MiniMax direct worker. The bundle SHALL contain one `StepType.generate` step with `capability_ref == "audio.t2a"` and `provider_policy.models_ref == "audio_minimax"`. The bundle SHALL not embed an API key; runtime auth comes from `MINIMAX_KEY`.

## Scenario: examples/minimax_music_smoke.json loads and dry-runs without network I/O

**Given** `examples/minimax_music_smoke.json`
**When** `load_task_bundle(path)` and `DryRunPass.run(...)` execute in tests
**Then** the bundle parses cleanly, `audio_minimax` resolves to `minimax/music-2.6`, no network call is made, and `tests/integration/test_example_bundles_smoke.py` auto-discovers the bundle.

## Scenario: Live audio smoke L2 evidence file is real audio bytes under in-tree artifact path

**Given** a host with ComfyUI + Stable Audio Open model weights cached + `FORGEUE_COMFY_SCRIPTS_DIR` configured + `python -m factory_v3 serve` running
**When** the user runs `python -m framework.run --task examples/comfy_local_smoke_audio.json --live-llm --run-id audio_smoke_<timestamp>`
**Then** the resulting `artifacts/<today>/audio_smoke_<timestamp>/<artifact_id>.flac` (or `.mp3` / `.wav` depending on manifest output) file: (1) exists, (2) has size > 100 KB (avoids 0-byte false positives), (3) header bytes match the format-specific magic table (`flac → b"fLaC"`; `mp3 → b"ID3"` or MPEG frame sync `b"\xFF\xFB" / b"\xFF\xFA" / b"\xFF\xF3" / b"\xFF\xF2"`; `wav → b"RIFF"` at offset 0 AND `b"WAVE"` at offset 8). The L2 evidence note `notes/live_smoke_audio_<date>.md` SHALL record these three objective checks; subjective audio quality is left to human spot-check. (F-Plan-5 round-2 plan 修订:duration ±10% check is OUT OF SCOPE for this change — design D10 + this spec lock `AudioCandidate.duration_seconds=None always` because ComfyUI agent CLI does not expose audio metadata; ForgeUE does not introduce mutagen / `wave` / `aifc` parsing in this change scope; a follow-on `audio-metadata-parser` change MAY add the duration check after introducing a parser dependency)

## Requirement: .env.example MUST list the env var names that are actually read at runtime

The system SHALL keep `.env.example` template in sync with the env var names that
runtime code (`config/models.yaml` + `src/framework/run.py` + provider workers)
actually reads at startup. Specifically, for any provider listed in the template,
the variable names commented in `.env.example` MUST match the names appearing in
`config/models.yaml::providers.<provider>.api_key_env` and any direct `os.environ.
get("...")` lookup in `src/framework/run.py`. Cross-references SHOULD be added as
inline comments next to the placeholder so future env-var renames are easy to audit.

## Scenario: Hunyuan 3D mesh provider env var alignment

**Given** a fresh user copies `.env.example` to `.env` and fills in the Hunyuan 3D mesh provider section
**When** they run `python -m framework.run --task <bundle> --live-llm`
**Then** the env var name they configured MUST be `HUNYUAN_3D_KEY` (matching `config/models.yaml:95 api_key_env: HUNYUAN_3D_KEY` and `src/framework/run.py:100 os.environ.get("HUNYUAN_3D_KEY")`)
**And** template MUST NOT show TC3-HMAC-SHA256-style three-segment placeholders (`HUNYUAN_3D_SECRET_ID` / `HUNYUAN_3D_SECRET_KEY` / `HUNYUAN_3D_REGION`) which no longer correspond to any runtime read path
**And** template SHOULD inline a comment cross-referencing the runtime read location so future renames are surfaced

## Scenario: Existing .env files configured with old TC3 fields are not broken

**Given** a `.env` file already configured with the old TC3-HMAC-SHA256 fields (`HUNYUAN_3D_SECRET_ID/SECRET_KEY/REGION`)
**When** runtime starts
**Then** those env vars are NOT read by any current code path
**And** they SHALL NOT cause any error (they are simply ignored as unrecognized env vars)
**And** Hunyuan 3D mesh provider falls back to FakeMeshWorker / Tripo3D / provider auth failure (existing behavior; outside this change's scope)

## Requirement: ComfyUI video live smoke bundle is text-to-video with single generate / capability_ref="video.t2v" step

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

## Scenario: examples/comfy_local_smoke_video.json declares text-to-video single step with video_local alias and canonical loader schema

**Given** the post-change `examples/comfy_local_smoke_video.json` loaded via `framework.workflows.loader.load_task_bundle`
**When** the loader reads the bundle structure
**Then** (sweep-mirror of audio Phase 2: bundle has canonical top-level three-section schema) the JSON has top-level keys `task` + `workflow` + `steps` (NOT nested `workflow.steps[]`); `Task.model_validate(raw["task"])` parses cleanly; `Workflow.model_validate(raw["workflow"])` parses cleanly with `step_ids` listing one step (no `steps` nested under workflow); `[Step.model_validate(s) for s in raw["steps"]]` produces exactly one Step; the step's `type == StepType.generate` (`"generate"` in JSON); `step.capability_ref == "video.t2v"`; `step.provider_policy.models_ref == "video_local"`; `step.provider_policy.capability_required == "video.t2v"`; `step.retry_policy` if present contains only `max_attempts/backoff/retry_on` (no `timeout_seconds`); `step.config.worker_timeout_s == 600`; `step.config.spec` contains `comfy_workflow` (string starting with `"Vedio/"` — D5 upstream typo intentional), `comfy_params` (dict containing prompt key matching the manifest's expected schema, e.g. `positive_prompt` for Wan T2V), `comfy_lifecycle: "none"`, and contains NO `workflow_graph` field, NO `comfy_image_param_key` field; after `expand_model_refs`, the resolved `prepared_routes` contains exactly one route with `model="comfy/local-video"`

## Scenario: examples/comfy_local_smoke.json (image), comfy_local_smoke_mesh.json (mesh), comfy_local_smoke_audio.json (audio) are preserved unchanged

**Given** the post-change repository tree
**When** `examples/comfy_local_smoke.json`, `examples/comfy_local_smoke_mesh.json`, `examples/comfy_local_smoke_audio.json` are inspected
**Then** all three prior smoke bundles exist unchanged at the same paths; all four bundles coexist and exercise different ComfyAgentWorker capability modes; users selecting between them via `--task examples/comfy_local_smoke.json` (image), `--task examples/comfy_local_smoke_mesh.json` (image-to-mesh), `--task examples/comfy_local_smoke_audio.json` (text-to-audio), or `--task examples/comfy_local_smoke_video.json` (text-to-video) get the corresponding capability path

## Requirement: Live ComfyUI video smoke is gated behind agent-CLI video manifest availability + Wan model weights

The system SHALL document in the bundle's loader-test smoke + in CLAUDE.md (ComfyUI section) that running `examples/comfy_local_smoke_video.json` end-to-end requires:

1. ComfyUI installed under a host-specific path with at least one video workflow manifest available (default: `Vedio/Wan2.1-T2V-1.3B_native_5sec` — Wan 2.1 1.3B T2V with 5-second clip; alternative: `Vedio/Wan2.1-T2V-1.3B_native_teacache` requires TeaCache custom node; `Vedio/Wan2.2-T2V-A14B_GGUF` requires 14+ GB VRAM and longer generation time ≥30 min)
2. `python -m comfyui_api list` output containing the manifest name referenced by the bundle (note: D5 upstream `Vedio/` typo — `list` output uses the same path)
3. `FORGEUE_COMFY_SCRIPTS_DIR` pointing to that ComfyUI's `scripts/` directory; **NO** `FORGEUE_COMFY_INPUT_DIR` env var required (text-to-video has no source bytes path — that env var is mesh-specific)
4. First run: ComfyUI auto-downloads Wan model weights from HuggingFace (Wan 2.1 1.3B ~3 GB; A14B ~14 GB+); subsequent runs use the cache; users SHOULD pre-warm ComfyUI to avoid `worker_timeout_s` exhaustion during first cold start
5. `python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id video_smoke_<timestamp>`

The offline loader-contract test SHALL still pass without any of those preconditions because the loader does not invoke any worker. CLAUDE.md SHALL be updated to reflect the four smoke bundles (image / mesh / audio / video) and to note that video smoke produces a `.mp4` file under `artifacts/<today>/<run_id>/<artifact_id>.mp4` (round-2 F2 + round-3 PF3 sweep:**mp4-only**,webm follow-on `comfy-video-webm-adoption`;the in-tree filename is `<artifact_id>.<format>` via `repo.put` + `file_suffix=f".{cand.format}"` which post-F2 evaluates to `.mp4` only, NOT the original ComfyUI filename — see artifact-contract spec).

## Scenario: comfy_local_smoke_video.json passes the offline loader-contract fence without a real ComfyUI

**Given** a CI runner without ComfyUI installed and without `D:/AI/ComfyUI/scripts/`
**When** `tests/integration/test_example_bundles_smoke.py` loads `examples/comfy_local_smoke_video.json` through `load_task_bundle`
**Then** the bundle parses cleanly into a `TaskBundle`, no subprocess is spawned, and the smoke test asserts only loader-level invariants (`comfy_workflow` is a string starting with `"Vedio/"`, `comfy_params` is a dict containing at least one prompt-like key, `video_local` alias resolves to `comfy/local-video`, no `workflow_graph` field, no `comfy_image_param_key` field, `depends_on` is empty); mirrors the existing fence pattern for image / mesh / audio bundles

## Scenario: Live video smoke L2 evidence file is real video bytes under in-tree artifact path

**Given** a host with ComfyUI + Wan 2.1 1.3B model weights cached + `FORGEUE_COMFY_SCRIPTS_DIR` configured + `python -m factory_v3 serve` running (ComfyUI pre-warmed)
**When** the user runs `python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id video_smoke_<timestamp>`
**Then** the resulting `artifacts/<today>/video_smoke_<timestamp>/<artifact_id>.mp4` file (round-2 F2 修订:mp4-only;webm follow-on): (1) exists, (2) has size > 1 MB (avoids 0-byte false positives; Wan 1.3B 5sec @ 832x480 typically produces 5-15 MB), (3) BMFF strict header validation (round-2 F4 + **round-3 PF2 修订**): `len(data) >= 16` AND `data[4:8] == b"ftyp"` AND `box_size = int.from_bytes(data[0:4], "big")` is in range `[8, len(data)]` (round-3 PF2:**reject `box_size == 1`** for 64-bit largesize, follow-on `video-bmff-largesize-support`) AND `data[8:12]` major_brand is non-empty / non-zero / non-spaces. The L2 evidence note `notes/live_smoke_video_<date>.md` SHALL record all four objective checks; subjective video quality is left to human spot-check. Frame count / duration / resolution checks are OUT OF SCOPE for this change — design D8 + this spec lock `VideoCandidate.duration_seconds=None / frame_count=None / width=None / height=None / fps=None always` because ComfyUI agent CLI does not expose video metadata; ForgeUE does not introduce ffprobe / mutagen parsing in this change scope; a follow-on `video-metadata-parser` change MAY add the duration / frame_count / resolution checks after introducing a parser dependency

## Requirement: a2_video UE 真机 P4 acceptance via commandlet automation

The system SHALL provide an `a2_video` UE 真机 P4 acceptance path documented in `docs/acceptance/acceptance_report.md` and exercised once on a UE 5.x install (sweep-mirror of `a2_mesh` 2026-04-23 UE 5.7.4 commandlet模式;D15 user决定走 commandlet 自动化,**not** GUI Python Console manual paste). The acceptance SHALL:

- Run `python -m framework.run --task examples/comfy_local_smoke_video.json --live-llm --run-id a2_video_<date>` to produce `artifacts/<today>/a2_video_<date>/<artifact_id>.mp4` + matching `manifest.json` / `import_plan.json` / `evidence.json`
- Run `<UE_path>/Engine/Binaries/Win64/UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<repo>/ue_scripts/run_import.py"` with `FORGEUE_RUN_FOLDER` env pointing to the artifact run folder (Bash 直接驱动,Claude 不需要用户手工点 Python Console)
- Verify the resulting UE project tree contains:
  - `<project_root>/Content/Movies/<run_id>/MS_<base>.mp4` — the mp4 source file copied to UE Movies subdirectory (D12 packaging path分流)
  - `<project_root>/Content/Generated/<run_id>/MS_<base>.uasset` — the FileMediaSource `.uasset` asset (NOT mp4-embedded; just a reference)
- Append `evidence.json` with one record per import operation, status `success`
- Documented evidence file: `notes/live_smoke_video_<date>.md` records (a) framework-side `artifacts/.../<artifact_id>.mp4` size + magic bytes check, (b) UE-side `Content/Movies/<run_id>/MS_<base>.mp4` existence + size, (c) UE-side `Content/Generated/<run_id>/MS_<base>.uasset` existence, (d) `unreal.FileMediaSource.cast(asset).get_editor_property("file_path")` resolved value matching the Movies path, (e) `Artifact.metadata.worker_metadata.comfy_capability == "video"` + producer = `comfy_agent_cli` + model = `comfy/local-video` for producer attribution

## Scenario: a2_video commandlet round-trip produces both `.mp4` source and `.uasset` reference

**Given** a host with UE 5.x installed (UE 5.7+ recommended), `PythonScriptPlugin` enabled in the target `.uproject`, framework-side `artifacts/<today>/a2_video_<date>/` containing the prior `framework.run` outputs, and `FORGEUE_RUN_FOLDER` env set to that path
**When** the operator invokes `UnrealEditor-Cmd.exe <project>.uproject -ExecutePythonScript="<repo>/ue_scripts/run_import.py"` from a Bash shell
**Then** UE 加载 project,执行 `run_import.run()`,for the video entry: framework drop loop 已预先把 mp4 source 放到 `Content/Movies/<run_id>/MS_<base>.mp4`;`domain_video.import_video_entry` does not copy the mp4, but invokes `unreal.FileMediaSourceFactoryNew()` + `unreal.AssetTools.create_asset(...)` to create `Content/Generated/<run_id>/MS_<base>.uasset` and sets its `file_path` editor property to the Movies-relative path; `evidence.json` gets a `status="success"` record for this operation; the operator visually verifies via UE Editor Content Browser double-click on `MS_<base>.uasset` showing the FileMediaSource asset details panel with the file_path field populated; the `notes/live_smoke_video_<date>.md` evidence file documents all five checks above

## Requirement: Centralized follow-on backlog registry under `docs/backlog/`

The system SHALL maintain a centralized follow-on backlog registry at `docs/backlog/active.md` (active items) and `docs/backlog/archived.md` (cancelled / completed items). The active registry SHALL collect archive-tracking class follow-ons (workflow-protocol class + capability-boundary class) and pointer entries to `docs/requirements/SRS.md` §7.3 TBD entries (requirements-tbd-pointer class). The active registry SHALL NOT duplicate full TBD content from SRS §7.3 (dual-source cross-link, not single-source). Each registry entry SHALL carry the following fields: `id` (kebab-case), `source` (archived change tasks.md anchor or SRS §7.3 TBD-XXX pointer), `description`, `trigger` (trigger condition for promotion to a real change), `category` (one of `workflow-protocol` / `capability-boundary` / `requirements-tbd-pointer`), `retire-impact-status` (one of `unaffected` / `scope-narrowed` / `partial-superseded`), `priority` (one of `high` / `medium` / `low` / empty), `status` (active registry entries SHALL always carry `status: active`). The schema SHALL be documented in `docs/backlog/README.md` for reader reference; no automated fence (e.g., `_check_followon_continuity` / `_check_srs_registry_consistency` / 4 类 cancel tag fence / `_validate_tombstone_consistency` / `_check_archived_md_append_only`) SHALL enforce schema integrity (round 1 codex P1-4 writeback: schema 描述保留作 reference,fence enforcement 整删随 finish_gate retire 一并消失;沿 design.md D3:目录保留 + 砍 fence)。Schema drift 由 user 自由维护,git history 提供 audit trail 替代 append-only fence。

## Scenario: registry file exists with 8-field schema documented

**Given** the change `retire-forgeue-protocol-layer-fully` has shipped
**When** a reader opens `docs/backlog/active.md` and `docs/backlog/README.md`
**Then** `active.md` SHALL contain entries each carrying the 8 schema fields (priority MAY be empty)
**And** `README.md` SHALL document the 8-field schema as reader reference
**And** **no automated fence** SHALL run on schema integrity (`_check_followon_continuity` / `_check_srs_registry_consistency` / 4 类 cancel tag fence / `_validate_tombstone_consistency` / `_check_archived_md_append_only` 全部随 `forgeue_finish_gate.py` retire 整删)
**And** SRS §7.3 TBD table SHALL carry a cross-link header note pointing to `docs/backlog/active.md` for workflow-protocol + capability-boundary class follow-ons

## Scenario: archived.md tombstone schema documented but append-only by convention only

**Given** `docs/backlog/archived.md` contains tombstone entries each with 4 fields (`archived_at_commit` / `archived_in_change` / `cancellation_reason` / `registry_entry_snapshot`)
**When** a user manually edits `archived.md` (e.g., 修 typo / 补漏 entry / 删错 entry)
**Then** **no fence** SHALL block the edit; git history(`git log --follow docs/backlog/archived.md`)是 audit trail 唯一来源
**And** README.md SHALL note "tombstone is append-only by convention, enforced by git review only (no programmatic fence post-`retire-forgeue-protocol-layer-fully`)"

## Requirement: Capability boundary follow-on entries cover the 6 multimodal LLD-inline annotations

The active registry SHALL contain capability-boundary class entries for each LLD-inline `留 follow-on <name>` annotation that has not been promoted to a real change. The 6 entries SHALL be: `audio-metadata-parser` (audio `duration_seconds` / `sample_rate` parser), `video-metadata-parser` (video 5-tuple `duration_seconds` / `frame_count` / `width` / `height` / `fps` parser), `comfy-video-webm-adoption` (webm format support post mp4-only sweep), `comfy-video-v2v-adoption` (video-to-video path beyond text-to-video), `comfy-video-image-sequence-adoption` (image_sequence cinematic high-quality path), `video-bmff-largesize-support` (BMFF `box_size == 1` largesize box). Each entry SHALL reference the LLD section or CLAUDE.md ComfyUI-section line containing the inline annotation as `source`.

## Scenario: each LLD inline annotation has a corresponding registry entry

**Given** `docs/design/LLD.md` contains 6 inline annotations of the form `留 follow-on '<name>'` for multimodal capability boundaries
**When** a reader greps `docs/backlog/active.md` for category `capability-boundary`
**Then** the reader finds 6 entries matching the 6 annotation ids
**And** each entry's `source` field references the LLD section or CLAUDE.md line where the annotation appears

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
