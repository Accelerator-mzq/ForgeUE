## ADDED Requirements

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
