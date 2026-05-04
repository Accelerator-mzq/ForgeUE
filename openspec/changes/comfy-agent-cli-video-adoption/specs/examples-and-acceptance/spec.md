## ADDED Requirements

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
