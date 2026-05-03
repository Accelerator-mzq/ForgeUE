## ADDED Requirements

### Requirement: AudioWorker ABC, AudioCandidate dataclass, and AudioWorker exception tree establish audio worker baseline

The system SHALL establish an audio worker baseline at `src/framework/providers/workers/audio_worker.py` that mirrors the structure of `mesh_worker.py` (sibling to `MeshWorker` / `MeshCandidate`):

- `AudioCandidate` dataclass with required fields: `data: bytes` (audio file bytes), `format: Literal["flac", "mp3", "wav"]` (lowercase, no leading dot), `metadata: dict[str, Any]` (provenance: `comfy_manifest`, `comfy_params_snapshot`, `comfy_capability="audio"`, `comfy_original_filename`, `comfy_subprocess_run_metadata`, plus optional `duration_seconds`, `sample_rate`, `format_detected`); the `metadata` field is the source of `Artifact.metadata.worker_metadata` after `repo.put` per the Phase 1 mesh `MeshCandidate.metadata["worker_metadata"]` modeling

- `AudioWorker(ABC)` abstract base class with one `@abstractmethod`:

  ```python
  def generate_audio(
      self,
      *,
      spec: dict,
      num_candidates: int,
      seed: int | None,
      timeout_s: float,
  ) -> list[AudioCandidate]: ...
  ```

  The signature SHALL NOT include a `prompt: str` parameter — bundle authors place prompt strings inside `spec["comfy_params"]` directly (per the design D7 / D8 decision); concrete implementations parse `spec` according to their own provider conventions

- Exception tree mirrors `mesh_worker`:

  ```python
  class AudioWorkerError(RuntimeError): ...
  class AudioWorkerTimeout(AudioWorkerError): ...
  class AudioWorkerUnsupportedResponse(AudioWorkerError): ...
  ```

- A `FakeAudioWorker(AudioWorker)` test fixture SHALL be provided under `src/framework/providers/workers/audio_worker.py` (or `tests/fakes/`) producing minimal valid FLAC bytes (~50 bytes, magic `fLaC` + minimal STREAMINFO header) without third-party codec dependencies, suitable for offline unit / integration tests

#### Scenario: AudioWorker ABC enforces generate_audio signature

- **GIVEN** a hypothetical concrete subclass `class MyAudioWorker(AudioWorker):` that omits `generate_audio` implementation
- **WHEN** `MyAudioWorker(...)` is instantiated
- **THEN** Python raises `TypeError: Can't instantiate abstract class MyAudioWorker with abstract method generate_audio`; the ABC contract is enforced; `tests/unit/test_audio_worker.py::test_audio_worker_abc_requires_generate_audio` fences this

#### Scenario: AudioCandidate format field is restricted to flac, mp3, wav whitelist

- **GIVEN** an attempt to construct `AudioCandidate(data=b"...", format="ogg", metadata={}, ...)`
- **WHEN** the dataclass is instantiated
- **THEN** Pydantic / `Literal["flac","mp3","wav"]` constraint raises `ValidationError` (or runtime `TypeError` if dataclass without validation); `tests/unit/test_audio_worker.py::test_audio_candidate_format_whitelist` fences the three accepted formats and rejects unknown formats. The whitelist SHALL match the formats supported by UE `import_audio` (`unreal.SoundFactory`)

#### Scenario: AudioWorkerTimeout inherits from AudioWorkerError

- **GIVEN** Python's standard `isinstance` check
- **WHEN** code catches `AudioWorkerError` to handle all audio worker failures
- **THEN** `AudioWorkerTimeout` and `AudioWorkerUnsupportedResponse` are caught (parent `AudioWorkerError`); `tests/unit/test_audio_worker.py::test_audio_worker_exception_tree_inheritance` fences `issubclass(AudioWorkerTimeout, AudioWorkerError) is True` and the same for `AudioWorkerUnsupportedResponse`

### Requirement: comfy/local-audio model and audio_local alias register with ModelRegistry without extending ProviderDef schema

The system SHALL register a third virtual ComfyUI model in `config/models.yaml` (and the test fixture `tests/fixtures/test_models.yaml`) using only the existing `ProviderDef` / `ModelDef` / `Alias` schema established by `comfy-agent-cli-adoption`:

- `models.comfy_local_audio` entry: `id: "comfy/local-audio"` (REQUIRED, MUST match `_CAPABILITY_BY_MODEL_ID` key) + `provider: comfy_api` (reuses the `providers.comfy_api` entry registered by `comfy-agent-cli-adoption`; this change does NOT add a new provider) + `kind: audio` + `pricing: null` (local GPU, no per-task cost; `pricing_autogen.status: manual` with `sourced_on` set to the change archive date and a comment documenting the local-GPU exemption per ADR-004)

- `aliases.audio_local` entry: `preferred: ["comfy_local_audio"]` + `fallback: []` (no fallback to remote audio worker in this change scope; future remote audio workers will be added by their own follow-on changes per the design D3 split)

- The `providers.comfy_api` entry SHALL NOT be modified by this change (already registered by `comfy-agent-cli-adoption`); the `ProviderDef` schema (current fields: `api_base`, `api_key_env`) SHALL NOT be extended to carry `lifecycle` / `scripts_dir` / `python_exe` (those continue to flow via `FORGEUE_COMFY_*` env vars, deferred to SRS TBD-011 follow-on `model-registry-provider-kind-schema` change)

- SRS FR-MODEL-007 alias list SHALL be updated to include `audio_local` as the eleventh alias (Phase 1 added `mesh_local` as the tenth)

#### Scenario: ModelRegistry.from_yaml parses comfy/local-audio without ProviderDef schema extension

- **GIVEN** a `config/models.yaml` containing `models.comfy_local_audio.id: "comfy/local-audio"`, `provider: comfy_api`, `kind: audio`, `pricing: null`, `pricing_autogen.status: manual`, plus `aliases.audio_local.preferred: ["comfy_local_audio"]`
- **WHEN** `ModelRegistry.from_yaml(path)` parses the file
- **THEN** the resolved `ResolvedRoute(model="comfy/local-audio", api_key_env=None, api_base=None, kind="audio", pricing=None)` is exposed via `registry.resolve_alias("audio_local")`; the `providers.comfy_api` `ProviderDef` carries no new fields beyond the existing two; `tests/unit/test_model_registry.py::test_comfy_local_audio_model_resolves_via_audio_local_alias` and `::test_audio_local_alias_kind_is_audio` fence both directions

#### Scenario: BundleLoader rejects unknown comfy/local-* model id

- **GIVEN** a bundle whose `provider_policy.models_ref` resolves to an alias preferring `comfy/local-bogus` (not registered in `config/models.yaml`)
- **WHEN** `loader.load_task_bundle(path)` runs
- **THEN** the loader raises `ModelRegistryError` (or equivalent) before any executor is constructed; no `ComfyAgentWorker` is built; `tests/unit/test_bundle_loader.py::test_unknown_comfy_local_model_id_raises_at_load` fences this

### Requirement: GenerateAudioExecutor dispatches comfy/local-audio to ComfyAgentWorker via text-to-audio path (no source bytes resolution)

The system SHALL extend the executor table with `GenerateAudioExecutor` (new file `src/framework/runtime/executors/generate_audio.py`) declaring `step_type = StepType.generate` and `capability_ref = "audio.t2a"` (mirror of `generate_image.py:56-57` and `generate_mesh.py:66-67`). `framework.run` SHALL register the executor into `ExecutorRegistry`. The executor SHALL:

- Detect ComfyUI dispatch via a private helper `_should_use_comfy_worker_path(ctx) -> bool` returning True when `prepared_routes` contains `ResolvedRoute(model="comfy/local-audio", ...)` (mirrors `GenerateMeshExecutor._should_use_comfy_worker_path` from `comfy-agent-cli-mesh-audio-video-adoption`)

- When the comfy-worker path is selected, call `_generate_via_comfy_worker(ctx, spec, num, seed, timeout_s) -> list[AudioCandidate]` which:
  1. Constructs `ComfyAgentWorker(scripts_dir=..., model_id="comfy/local-audio", run_id=ctx.run.run_id, project_id=ctx.task.project_id, artifacts_dir=ctx.run_dir, default_lifecycle="none")` inline (mirrors mesh path)
  2. Runs an internal retry loop bounded by `(ctx.step.retry_policy or RetryPolicy()).max_attempts` (default 2; F-Plan-R2-A round-2 plan 修订:`retry_policy` is a top-level Step field per `src/framework/core/task.py:30-42` — NOT under `step.config`; mirrors mesh implementation `policy = ctx.step.retry_policy or RetryPolicy()` at `src/framework/runtime/executors/generate_mesh.py:146` and `:191`. Local audio is NOT premium per the `pricing.per_task_usd > 0` boundary, so the executor MAY retry without ADR-007 single-attempt restrictions)
  3. Calls `worker.generate_audio(spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s)` and returns the resulting `list[AudioCandidate]`
  4. Persists each candidate via `repo.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=f".{cand.format}", metadata={"worker_metadata": dict(cand.metadata), ...})` (mirrors mesh `repo.put` with `file_suffix=".glb"`; format-aware `file_suffix` keeps the artifact tree extensions consistent with payload bytes)

- The executor SHALL NOT call `_resolve_source_image(ctx)` or any source-bytes resolution helper — audio is text-to-audio (no upstream image step required); the bundle's `step.depends_on` (top-level field per task.py:41) SHALL be empty for `audio.t2a` capability_ref steps using `audio_local` alias unless the bundle explicitly pipelines audio from another step (out of scope for this change). Per design D7, the prompt and all manifest-specific parameters live entirely in `spec["comfy_params"]` and the executor SHALL NOT inject any params (in contrast to mesh which injects `comfy_params["input_image"] = "<filename>"` per `comfy-agent-cli-mesh-audio-video-adoption` design D8)

- The executor SHALL NOT require or read any `FORGEUE_COMFY_INPUT_DIR` env var (no source bytes copy); audio path is independent of the mesh source-bytes-write protocol

#### Scenario: comfy/local-audio routes to ComfyAgentWorker (audio) via executor-side model-id branch (pattern c, audio, NEW for this change)

- **GIVEN** a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local-audio", api_key_env=None, api_base=None, kind="audio", pricing=None)`; `step.type=StepType.generate`; `step.capability_ref="audio.t2a"`; `step.depends_on=[]` (top-level per task.py:41); `step.config.spec={"comfy_workflow": "Audio_Workflows/audio_stable_audio_example", "comfy_params": {"text": "uplifting electronic music, 130bpm", "duration_seconds": 10.0, "seed": 42, "steps": 50}, "comfy_lifecycle": "none"}`
- **WHEN** `GenerateAudioExecutor._should_use_comfy_worker_path(ctx)` returns True
- **THEN** the executor takes the comfy-worker dispatch branch and calls `_generate_via_comfy_worker(...)` which constructs `ComfyAgentWorker(model_id="comfy/local-audio", ...)` inline (NO `_resolve_source_image` call, NO source bytes write to ComfyUI input/) and invokes `worker.generate_audio(spec=..., num_candidates=1, seed=42, timeout_s=300)`; `_capability="audio"` is inferred; output validation requires `outputs.audio` non-empty and rejects `outputs.images / glb / video`; returned `AudioCandidate`s carry comfy provenance in `metadata={comfy_manifest, comfy_params_snapshot, comfy_capability="audio", comfy_original_filename, ...}` and are persisted via `repo.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=f".{cand.format}", metadata={"worker_metadata": dict(cand.metadata), ...})`

#### Scenario: GenerateAudioExecutor does NOT call _resolve_source_image even if a depends_on is present

- **GIVEN** a hypothetical bundle where an `audio.t2a` step has a `depends_on: ["upstream_step"]` (perhaps a text generation that produced the prompt, but the prompt is pre-injected into `comfy_params`)
- **WHEN** `GenerateAudioExecutor.execute(ctx)` runs
- **THEN** the executor does NOT call `_resolve_source_image(ctx)` (audio has no source image protocol); upstream Artifacts MAY be referenced for lineage purposes but are NOT loaded as input bytes; `tests/unit/test_generate_audio_comfy.py::test_executor_no_source_image_resolution` fences absence of source-bytes wiring

### Requirement: ComfyAgentWorker.generate_audio reads audio bytes and detects format from file extension

The system SHALL implement `ComfyAgentWorker.generate_audio(spec: dict, num_candidates: int, seed: int | None, timeout_s: float) -> list[AudioCandidate]` as the audio-mode entry point. The method SHALL:

1. Call the existing private helper `_run_subprocess_and_validate(spec, timeout_s) -> dict` (established by `comfy-agent-cli-adoption` for image, extended by `comfy-agent-cli-mesh-audio-video-adoption` for mesh) which spawns subprocess `python -m comfyui_api run --workflow <manifest> --params <json> --project <task.project_id> --lifecycle none --timeout <s>` and parses stdout JSON. The shared helper SHALL NOT be specialized for audio — capability dispatch happens entirely through the 4-dict `_validate_outputs` table

2. Validate outputs via the capability-aware `_validate_outputs(outputs)` table-driven method per the existing Requirement "ComfyAgentWorker output validation is capability-aware (REQUIRED + auxiliary + rejected)" (which this change MODIFIES to fill in the audio row)

3. For each path in `outputs.audio` (string list of **absolute paths** per `D:/AI/ComfyUI/scripts/comfyui_api/runner.py::extract_outputs` — the agent CLI returns absolute paths under `D:/AI/ComfyUI/outputs/main/<date>/<project>/...`, NOT relative paths; F4 round-1 修订基于 probe 实测结果):
   - `src = Path(abs_path)`
   - **Path trust-boundary 防护**(F-Plan-4 round-2 plan 修订:mirror image / mesh G11 R2 fix at `src/framework/providers/workers/comfy_worker.py:541-554` and `:805-814`, which reject symlinks "to prevent a buggy / compromised agent CLI from redirecting reads to arbitrary host files (e.g. /etc/secrets via ../symlink)"):
     - If `not src.is_file()`: raise `WorkerUnsupportedResponse(f"ComfyAgentWorker: outputs.audio path does not exist: {src}")`
     - If `src.is_symlink()`: raise `WorkerUnsupportedResponse(f"ComfyAgentWorker: outputs.audio path is a symlink, refusing to follow: {src}")`
   - Detect the format by `src.suffix.lower()[1:]` (strip leading dot); the bare format string MUST be in the whitelist `{"flac", "mp3", "wav"}`; if the extension is not in the whitelist, raise `WorkerUnsupportedResponse` listing the unsupported extension and the supported whitelist (the wrapper layer at `_generate_via_comfy_worker` will translate this to `AudioWorkerUnsupportedResponse`)
   - Read the file bytes via `data = src.read_bytes()`

4. **Magic bytes second-pass validation** (F5 round-2 修订:mandatory, mirrors Phase 1 mesh FR-WORKER-006 GLB magic gate):
   - `flac` → `data[:4] == b"fLaC"` (FLAC magic per RFC 9639)
   - `mp3` → `data[:3] == b"ID3"` OR `data[:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2")` (ID3v2 tag or MPEG frame sync)
   - `wav` → `data[:4] == b"RIFF"` AND `data[8:12] == b"WAVE"` (RIFF chunk + WAVE format)
   - On mismatch: raise `WorkerUnsupportedResponse(f"audio format mismatch: extension={ext} but magic bytes={data[:12].hex()}")` (the wrapper layer at `_generate_via_comfy_worker` will translate this to `AudioWorkerUnsupportedResponse`)

5. Construct `AudioCandidate(data=data, format=ext, metadata={"comfy_manifest": spec["comfy_workflow"], "comfy_params_snapshot": dict(spec.get("comfy_params") or {}), "comfy_capability": "audio", "comfy_original_filename": Path(abs_path).name, "comfy_subprocess_run_metadata": {...exit_code, total_seconds, ...}}, duration_seconds=None, sample_rate=None)` (F3 round-2:duration_seconds / sample_rate are top-level fields; F4 round-2:both are `None` in this change scope because ComfyUI agent CLI `extract_outputs` does NOT expose audio metadata — the `outputs.metadata.audio` JSON path does NOT exist in the agent CLI envelope per probe in `notes/audio_subprocess_probe_20260503.md`; follow-on change `audio-metadata-parser` may introduce mutagen / stdlib `wave` parsing)

6. Return `list[AudioCandidate]` aggregated across all `num_candidates` per-candidate subprocess invocations (F-Plan-3 round-2 plan 修订:`generate_audio` SHALL implement an internal `for i in range(max(1, num_candidates)): call_seed = (seed or 0) + i; ...` loop calling a private `_run_once_audio` helper per candidate — mirroring image / mesh worker patterns at `src/framework/providers/workers/comfy_worker.py:427` and `:689`. Per F4 round-1 probe, the registered audio manifests have a single SaveAudioMP3 node producing 1 file per subprocess run, so `num_candidates > 1` requires multiple subprocess invocations; the wrapper layer at `_generate_via_comfy_worker` SHALL NOT need a second outer loop — `generate_audio` aggregates internally)

#### Scenario: generate_audio detects FLAC format from file extension and reads bytes

- **GIVEN** a `ComfyAgentWorker` with `_capability="audio"`; subprocess returns stdout JSON `{"ok": true, "outputs": {"audio": ["audio/ComfyUI_00001_.flac"]}}`; the file at the resolved absolute path contains valid FLAC bytes (magic `fLaC`)
- **WHEN** `worker.generate_audio(spec=..., num_candidates=1, seed=42, timeout_s=300)` is called
- **THEN** the worker reads the bytes, detects `format="flac"` from `.flac` extension, constructs `AudioCandidate(data=<file bytes>, format="flac", metadata={..., "comfy_original_filename": "ComfyUI_00001_.flac", "comfy_capability": "audio", ...})`; the candidate list has length 1; `tests/unit/test_comfy_subprocess.py::test_generate_audio_flac_extension_detection_reads_bytes` fences this

#### Scenario: generate_audio rejects unsupported file extension

- **GIVEN** a `ComfyAgentWorker` with `_capability="audio"`; subprocess returns stdout JSON `{"ok": true, "outputs": {"audio": ["audio/strange_output.ogg"]}}`
- **WHEN** `worker.generate_audio(...)` is called
- **THEN** the worker raises `WorkerUnsupportedResponse` with a message naming the unsupported extension `.ogg` and listing the supported whitelist `{"flac", "mp3", "wav"}`; no `AudioCandidate` is constructed; the wrapper layer at `_generate_via_comfy_worker` MAY translate this to `AudioWorkerUnsupportedResponse` per the wrap-with-cause contract

#### Scenario: generate_audio leaves duration_seconds and sample_rate as None when ComfyUI does not emit them

- **GIVEN** a `ComfyAgentWorker` with `_capability="audio"`; subprocess returns stdout JSON `{"ok": true, "outputs": {"audio": ["audio/x.flac"]}}` with NO `outputs.metadata.audio` field
- **WHEN** `worker.generate_audio(...)` runs
- **THEN** the returned `AudioCandidate.duration_seconds is None` and `.sample_rate is None`; the `format` field is correctly set; `metadata` contains the four required `comfy_*` keys plus `comfy_subprocess_run_metadata`; `tests/unit/test_comfy_subprocess.py::test_generate_audio_metadata_best_effort_when_comfy_does_not_emit` fences this

### Requirement: Local ComfyUI audio worker is NOT a premium API per the per_task_usd boundary

The system SHALL apply the ADR-007 premium-API boundary to local ComfyUI audio identically to local ComfyUI mesh: `comfy_local_audio.pricing` is null → `pricing.per_task_usd` resolves to None / 0 → the model is NOT premium → `GenerateAudioExecutor._generate_via_comfy_worker` SHALL run an internal retry loop bounded by `(ctx.step.retry_policy or RetryPolicy()).max_attempts` (default 2;F-Plan-R2-A round-2 plan 修订:`retry_policy` is top-level Step field per `task.py:30-42`,NOT under `step.config`;mirrors mesh impl `generate_mesh.py:146`+`:191`)without ADR-007 strict-single-attempt restrictions.

In contrast, future remote audio workers (e.g. AudioCraft hosted endpoints registered with `pricing.per_task_usd > 0`) SHALL be premium and SHALL be subject to ADR-007's strict-single-attempt contract on the executor main path; this future behavior is NOT implemented by this change but the contract is preserved to avoid future drift.

The wrapped `AudioWorkerTimeout` / `AudioWorkerUnsupportedResponse` exceptions SHALL still resolve through `FailureModeMap` to `audio_worker_timeout` / `audio_worker_unsupported` modes terminating in `Decision.abort_or_fallback` (NOT `retry_same_step`); the internal retry happens implicitly inside `_generate_via_comfy_worker` before the wrapper exception is raised, mirroring the Phase 1 mesh round-5 R4-F1 routing decision.

#### Scenario: Local ComfyUI audio retry loop runs up to policy.max_attempts before raising

- **GIVEN** a step with `policy.max_attempts=2`; `comfy/local-audio` resolved route with `pricing=None`; the first subprocess invocation raises `ComfyWorkerTimeout` (transient ComfyUI server hiccup)
- **WHEN** `GenerateAudioExecutor._generate_via_comfy_worker(...)` runs
- **THEN** the helper catches `ComfyWorkerTimeout`, increments attempt counter to 2, retries; if the second attempt succeeds, candidates are returned normally; if the second attempt also fails with `ComfyWorkerTimeout`, the helper wraps it as `AudioWorkerTimeout` with `__cause__` set and raises; `tests/unit/test_generate_audio_comfy.py::test_local_audio_retry_loop_uses_max_attempts` fences both the success-on-retry and exhaust-and-raise paths

#### Scenario: Wrapped AudioWorkerTimeout maps to audio_worker_timeout mode → abort_or_fallback (not retry_same_step)

- **GIVEN** a `_generate_via_comfy_worker` exhausts all `policy.max_attempts` retries and raises `AudioWorkerTimeout` (with `__cause__` set to the inner `ComfyWorkerTimeout`)
- **WHEN** `FailureModeMap.from_exception(exc)` is called
- **THEN** the resolved mode is `audio_worker_timeout` and the resolved decision is `Decision.abort_or_fallback` (NOT `retry_same_step` — the internal retry already happened inside `_generate_via_comfy_worker`); the orchestrator honors `on_fallback` configuration per the existing failure-mode contract; `tests/unit/test_failure_mode_map.py::test_audio_worker_timeout_maps_to_abort_or_fallback` fences this

### Requirement: ComfyAgentWorker exceptions wrapped to AudioWorker exceptions in _generate_via_comfy_worker

The system SHALL wrap `ComfyWorkerError` family exceptions raised inside `worker.generate_audio(...)` with `AudioWorker*` family exceptions before re-raising at the `GenerateAudioExecutor._generate_via_comfy_worker` layer. The wrap mapping SHALL be (mirrors the Phase 1 mesh wrap mapping):

| inner `ComfyWorker*` exception | wrapped `AudioWorker*` exception | `FailureModeMap` mode | `Decision` |
|---|---|---|---|
| `ComfyWorkerTimeout` | `AudioWorkerTimeout` | `audio_worker_timeout` | `abort_or_fallback` |
| `ComfyWorkerUnsupportedResponse` | `AudioWorkerUnsupportedResponse` | `audio_worker_unsupported` | `abort_or_fallback` |
| `ComfyWorkerError` (generic) | `AudioWorkerError` | `audio_worker_unsupported` (categorized as unsupported) | `abort_or_fallback` |

The wrap SHALL preserve the original exception via `wrapped.__cause__ = inner_exc` (or `raise wrapped from inner_exc` semantics) so traceback chains remain debuggable. `FailureModeMap.from_exception` SHALL be extended to recognize `AudioWorkerTimeout` and `AudioWorkerUnsupportedResponse` as audio-specific modes (mirrors Phase 1 mesh extension).

#### Scenario: ComfyWorkerTimeout from generate_audio is wrapped as AudioWorkerTimeout with __cause__ chain

- **GIVEN** `ComfyAgentWorker.generate_audio(...)` raises `ComfyWorkerTimeout("subprocess hit 300s wall clock")`
- **WHEN** `GenerateAudioExecutor._generate_via_comfy_worker(...)` catches the exception (after exhausting `policy.max_attempts`)
- **THEN** the helper raises `AudioWorkerTimeout("subprocess hit 300s wall clock")` with `__cause__` set to the inner `ComfyWorkerTimeout`; `traceback` shows both layers; `tests/unit/test_generate_audio_comfy.py::test_comfy_timeout_wrapped_as_audio_timeout_with_cause` fences this

#### Scenario: ComfyWorkerUnsupportedResponse from generate_audio is wrapped as AudioWorkerUnsupportedResponse

- **GIVEN** `ComfyAgentWorker.generate_audio(...)` raises `ComfyWorkerUnsupportedResponse("outputs.audio missing for capability=audio")` (e.g. the manifest fails and ComfyUI returns empty outputs)
- **WHEN** `_generate_via_comfy_worker(...)` catches the exception
- **THEN** it wraps to `AudioWorkerUnsupportedResponse(...)` (NOT `AudioWorkerTimeout`, NOT generic `AudioWorkerError`); `FailureModeMap` resolves to `audio_worker_unsupported` mode → `Decision.abort_or_fallback`; `tests/unit/test_generate_audio_comfy.py::test_comfy_unsupported_wrapped_as_audio_unsupported` fences this

## MODIFIED Requirements

### Requirement: ComfyAgentWorker dispatches by capability inferred from model id

The system SHALL extend `ComfyAgentWorker` to support multiple ComfyUI capabilities (image, mesh, audio, and future video) via a single worker class with capability dispatch driven by the resolved model id, NOT by an explicit bundle field. The worker SHALL maintain an internal table `_CAPABILITY_BY_MODEL_ID` mapping concrete `comfy/local*` model ids to capability tags (`comfy/local` → `image`, `comfy/local-mesh` → `mesh`, `comfy/local-audio` → `audio`); future video capability will extend this table in its own follow-on change (`comfy-agent-cli-video-adoption`). The worker constructor SHALL accept the resolved `model_id` (in addition to the existing `scripts_dir` / `python_exe` / `default_lifecycle` / `run_id` / `project_id` / `artifacts_dir` parameters established by `comfy-agent-cli-adoption`); if `model_id` is not in `_CAPABILITY_BY_MODEL_ID`, the constructor SHALL raise `WorkerUnsupportedResponse` with a message naming the unknown id and listing supported ids — capability inference SHALL NOT silently fall back to image-mode. Bundle protocol (`step.config.spec.comfy_workflow` + `comfy_params` + `comfy_lifecycle: "none"`) SHALL remain unchanged from the image-only contract; users do NOT add an `outputs_kind` field. Mesh-capable bundles MAY add the optional `step.config.spec.comfy_image_param_key` field (default `"input_image"` per Phase 1 round-5 D8) to declare which `comfy_params` key receives the upstream source image filename. Audio-capable bundles SHALL place all manifest-specific parameters (positive prompt, negative prompt, tags, lyrics, duration_seconds, seed, steps, filename_prefix) inside `step.config.spec.comfy_params` directly without any executor injection (per design D7 / D8); audio bundles SHALL NOT use `comfy_image_param_key` (no source bytes path).

#### Scenario: ComfyAgentWorker constructed with comfy/local-mesh enters mesh capability mode

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`, `FORGEUE_COMFY_LIFECYCLE` unset (defaults to `"none"`); a resolved `ResolvedRoute(model="comfy/local-mesh", api_key_env=None, api_base=None, kind="mesh", pricing=None)`; `ctx.run.run_id="run_mesh_smoke"`; `ctx.task.project_id="proj_mesh"`; `ctx.run_dir=Path("artifacts/2026-05-XX/run_mesh_smoke")`
- **WHEN** `GenerateMeshExecutor._generate_via_comfy_worker` constructs `ComfyAgentWorker(scripts_dir=..., model_id="comfy/local-mesh", run_id=..., project_id=..., artifacts_dir=..., default_lifecycle="none")`
- **THEN** the worker's `self._capability` attribute equals `"mesh"`; subsequent `worker.generate_mesh(spec=..., source_image_filename=..., num_candidates=1, seed=42, timeout_s=600)` calls validate outputs against the mesh capability rules; the worker MUST NOT silently fall back to image-mode parsing

#### Scenario: ComfyAgentWorker constructed with comfy/local-audio enters audio capability mode (NEW for this change)

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`, `FORGEUE_COMFY_LIFECYCLE` unset (defaults to `"none"`); a resolved `ResolvedRoute(model="comfy/local-audio", api_key_env=None, api_base=None, kind="audio", pricing=None)`; `ctx.run.run_id="run_audio_smoke"`; `ctx.task.project_id="proj_audio"`; `ctx.run_dir=Path("artifacts/2026-05-XX/run_audio_smoke")`
- **WHEN** `GenerateAudioExecutor._generate_via_comfy_worker` constructs `ComfyAgentWorker(scripts_dir=..., model_id="comfy/local-audio", run_id=..., project_id=..., artifacts_dir=..., default_lifecycle="none")`
- **THEN** the worker's `self._capability` attribute equals `"audio"`; subsequent `worker.generate_audio(spec=..., num_candidates=1, seed=42, timeout_s=300)` calls validate outputs against the audio capability rules per the Requirement "ComfyAgentWorker output validation is capability-aware (REQUIRED + auxiliary + rejected)"; the worker MUST NOT silently fall back to image-mode or mesh-mode parsing; **NO** `FORGEUE_COMFY_INPUT_DIR` env var is read (audio has no source bytes path)

#### Scenario: ComfyAgentWorker rejects unknown model id at construction time

- **GIVEN** a hypothetical resolved route with `model="comfy/local-bogus"` (not in `_CAPABILITY_BY_MODEL_ID`)
- **WHEN** `ComfyAgentWorker(model_id="comfy/local-bogus", ...)` is invoked
- **THEN** the constructor raises `WorkerUnsupportedResponse` with a message naming the unknown id and listing the supported ids (`"comfy/local", "comfy/local-mesh", "comfy/local-audio"`); no subprocess is spawned; `FailureModeMap` resolves to `unsupported_response` → `Decision.abort_or_fallback`

### Requirement: ComfyAgentWorker output validation is capability-aware (REQUIRED + auxiliary + rejected)

The system SHALL validate the agent CLI stdout JSON `outputs` field against the worker's resolved capability via a single table-driven method `_validate_outputs(outputs: dict) -> None` using a three-tier rule per capability (REQUIRED key / auxiliary key set / rejected key set). The tables SHALL be:

| capability | REQUIRED non-empty key | auxiliary keys (allowed non-empty, NOT consumed) | rejected keys (raise on non-empty) |
|---|---|---|---|
| `image` | `outputs.images` | (none) | `outputs.glb`, `outputs.audio`, `outputs.video` |
| `mesh` | `outputs.glb` | `outputs.images` (PNG preview from mesh manifests like `02_mini_textured_3d_hunyuan` — tolerated, not consumed) | `outputs.audio`, `outputs.video` |
| `audio` | `outputs.audio` | (none) | `outputs.images`, `outputs.glb`, `outputs.video` |
| `video` (future) | `outputs.video` | TBD by `comfy-agent-cli-video-adoption` | TBD |

The validation logic SHALL be:

1. If the REQUIRED key is missing or its value is empty → raise `WorkerUnsupportedResponse` naming the capability and missing key
2. If any rejected key has a non-empty value → raise `WorkerUnsupportedResponse` listing the unexpected non-empty keys
3. Auxiliary keys with non-empty values SHALL NOT raise; the worker SHALL emit an INFO-level log line recording auxiliary output count + paths for diagnostics, but MUST NOT construct any candidate object from auxiliary outputs. The log line SHALL be emitted via `logging.getLogger("framework.providers.workers.comfy_worker").info(...)` with structured fields `count: int`, `paths: list[str]`, `capability: str`. Audio-mode has no auxiliary keys, so no INFO log is emitted on the audio path

This three-tier model accommodates the reality that ComfyUI mesh workflows often produce auxiliary PNG previews alongside the GLB. Audio manifests in the registered set (`audio_ace_step_1_t2a_instrumentals`, `audio_stable_audio_example`) do NOT produce auxiliary visual or geometry outputs; if a future audio manifest emits auxiliary outputs (e.g. a spectrogram PNG preview), a follow-on change MAY widen the audio auxiliary set rather than relaxing the rejected set.

#### Scenario: Audio-mode worker raises on missing outputs.audio

- **GIVEN** a `ComfyAgentWorker` with `_capability="audio"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"audio": [], "images": ["preview.png"]}}`
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker raises `WorkerUnsupportedResponse` with a message naming `capability='audio'` and missing required `outputs.audio`; no `AudioCandidate` is constructed; `FailureModeMap` routes to `unsupported_response` → `Decision.abort_or_fallback`

#### Scenario: Audio-mode worker raises on rejected outputs.images (no auxiliary tolerance for visual outputs in audio capability)

- **GIVEN** a `ComfyAgentWorker` with `_capability="audio"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"audio": ["x.flac"], "images": ["unexpected_spectrogram.png"]}}`
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker raises `WorkerUnsupportedResponse` listing `outputs.images` as a rejected non-empty key in audio-mode (audio capability auxiliary set is empty per the table); `tests/unit/test_comfy_subprocess.py::test_audio_mode_rejects_outputs_images` fences this

#### Scenario: Audio-mode worker raises on rejected outputs.glb

- **GIVEN** a `ComfyAgentWorker` with `_capability="audio"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"audio": ["x.flac"], "glb": ["unexpected.glb"]}}`
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker raises `WorkerUnsupportedResponse` listing `outputs.glb` as a rejected non-empty key in audio-mode; `tests/unit/test_comfy_subprocess.py::test_audio_mode_rejects_outputs_glb` fences this

#### Scenario: Audio-mode worker raises on rejected outputs.video

- **GIVEN** a `ComfyAgentWorker` with `_capability="audio"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"audio": ["x.flac"], "video": ["unexpected.mp4"]}}`
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker raises `WorkerUnsupportedResponse` listing `outputs.video` as a rejected non-empty key in audio-mode; `tests/unit/test_comfy_subprocess.py::test_audio_mode_rejects_outputs_video` fences this

#### Scenario: Mesh-mode worker raises on missing outputs.glb (regression of mesh change)

- **GIVEN** a `ComfyAgentWorker` with `_capability="mesh"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"glb": [], "images": ["preview.png"]}}`
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker raises `WorkerUnsupportedResponse` (mesh-mode contract from `comfy-agent-cli-mesh-audio-video-adoption` preserved)

#### Scenario: Mesh-mode worker accepts non-empty outputs.images as auxiliary preview (regression)

- **GIVEN** a `ComfyAgentWorker` with `_capability="mesh"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"glb": ["asset.glb"], "images": ["preview.png"]}}`
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker does NOT raise; INFO log emitted via `logging.getLogger("framework.providers.workers.comfy_worker").info(...)` with `count=1 paths=['preview.png'] capability='mesh'` (mesh-mode contract preserved)

#### Scenario: Image-mode worker still rejects non-empty outputs.glb (regression)

- **GIVEN** a `ComfyAgentWorker` with `_capability="image"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"images": ["x.png"], "glb": ["x.glb"]}}`
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker raises `WorkerUnsupportedResponse` (image-mode contract from `comfy-agent-cli-adoption` preserved)

### Requirement: Non-OpenAI protocols ship dedicated adapters

The system SHALL route non-OpenAI protocols via one of three patterns under `src/framework/providers/`:

- (a) `CapabilityRouter` adapter chain with `model.startswith(...)` prefix matching — used by `qwen/`, `hunyuan/` image (DashScope, Hunyuan tokenhub image)
- (b) **Worker injected at executor construction time** — used by remote mesh: `framework.run` selects `HunyuanTokenhubMeshWorker` (or future remote mesh worker) based on env / API keys and **injects** the instance into `GenerateMeshExecutor` (see `generate_mesh.py:194` "Mesh workers are injected directly into `GenerateMeshExecutor`"); `CapabilityRouter` is NOT involved. Future remote audio workers (e.g. AudioCraft) will extend pattern (b) to `GenerateAudioExecutor` (out of scope of this change; see follow-on `audio-worker-audiocraft-adoption` per design D3)
- (c) **Executor-side model-id exact-match branch** — used by ComfyUI agent CLI subprocess: `GenerateImageExecutor` checks `prepared_routes` for `model == "comfy/local"` (image), `GenerateMeshExecutor` checks for `model == "comfy/local-mesh"` (mesh), and `GenerateAudioExecutor` checks for `model == "comfy/local-audio"` (audio, NEW for `comfy-agent-cli-audio-adoption`); all three executors construct `ComfyAgentWorker` inline from env config + `StepContext`; `CapabilityRouter` is NOT involved. Future video capability (out of scope, see follow-on `comfy-agent-cli-video-adoption`) will extend pattern (c) to `GenerateVideoExecutor`

Each non-OpenAI protocol family SHALL ship its own adapter / worker module: DashScope (`qwen_multimodal_adapter.py`), Hunyuan tokenhub image (`hunyuan_tokenhub_adapter.py`), Hunyuan 3D mesh (`providers/workers/mesh_worker.py`, dispatched via pattern (b)), audio worker baseline (`providers/workers/audio_worker.py` — the new ABC `AudioWorker` + `AudioCandidate` + exception tree established by this change; remote concrete implementations dispatched via pattern (b) in follow-on changes), and ComfyUI agent CLI (`providers/workers/comfy_worker.py::ComfyAgentWorker` — single class, capability-aware dispatch driven by resolved model id, currently supporting image + mesh + audio; image-mode dispatched via pattern (c) on `GenerateImageExecutor`, mesh-mode dispatched via pattern (c) on `GenerateMeshExecutor`, audio-mode dispatched via pattern (c) on `GenerateAudioExecutor`).

#### Scenario: qwen/ and hunyuan/ prefixes route to their dedicated adapters via supports() prefix match (pattern a, regression)

- GIVEN `CapabilityRouter` with `QwenMultimodalAdapter` and `HunyuanImageAdapter` registered ahead of the wildcard `LiteLLMAdapter`
- WHEN a request targets a model whose id begins with `qwen/` or `hunyuan/`
- THEN routing reaches the matching dedicated adapter first; the call therefore bypasses LiteLLM's OpenAI-compatible chat path

#### Scenario: Remote Hunyuan3D mesh worker is injected into GenerateMeshExecutor by framework.run (pattern b, regression)

- GIVEN `framework.run.main` builds an Orchestrator and detects remote mesh capability needs based on env vars + bundle declarations
- WHEN it constructs `GenerateMeshExecutor`
- THEN it passes a concrete `HunyuanTokenhubMeshWorker` instance directly into the executor's constructor; ADR-007 strict no-silent-retry continues to apply for the remote path per the `pricing.per_task_usd > 0` boundary

#### Scenario: comfy/local routes to ComfyAgentWorker (image) via executor-side model-id branch (pattern c, image, regression)

- GIVEN a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local", ...)`
- WHEN `GenerateImageExecutor._should_use_worker_path(ctx)` returns True
- THEN the executor takes the comfy-worker dispatch branch and constructs `ComfyAgentWorker(model_id="comfy/local", ...)` inline; `_capability="image"` is inferred

#### Scenario: comfy/local-mesh routes to ComfyAgentWorker (mesh) via executor-side model-id branch (pattern c, mesh, regression)

- GIVEN a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local-mesh", ...)`; an upstream image step provides source bytes via the `_resolve_source_image(ctx)` chain
- WHEN `GenerateMeshExecutor._should_use_comfy_worker_path(ctx)` returns True
- THEN the executor takes the comfy-worker dispatch branch and calls `_generate_via_comfy_worker(...)` which writes source bytes to `Path(FORGEUE_COMFY_INPUT_DIR) / "forgeue_<sha1>.png"`, constructs `ComfyAgentWorker(model_id="comfy/local-mesh", ...)` inline, and invokes `worker.generate_mesh(...)`

#### Scenario: comfy/local-audio routes to ComfyAgentWorker (audio) via executor-side model-id branch (pattern c, audio, NEW for this change)

- GIVEN a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local-audio", ...)`; `step.type=StepType.generate`; `step.capability_ref="audio.t2a"`; `step.depends_on=[]`
- WHEN `GenerateAudioExecutor._should_use_comfy_worker_path(ctx)` returns True
- THEN the executor takes the comfy-worker dispatch branch and calls `_generate_via_comfy_worker(...)` which constructs `ComfyAgentWorker(model_id="comfy/local-audio", ...)` inline (NO source bytes write to ComfyUI input/, NO `_resolve_source_image` call, NO `FORGEUE_COMFY_INPUT_DIR` read) and invokes `worker.generate_audio(spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s)`; `_capability="audio"` is inferred; output validation requires `outputs.audio` non-empty and rejects `outputs.images / glb / video`; returned `AudioCandidate`s carry comfy provenance in `metadata={comfy_manifest, comfy_params_snapshot, comfy_capability="audio", comfy_original_filename, comfy_subprocess_run_metadata}` and are persisted via `repo.put(value=cand.data, payload_kind=PayloadKind.file, file_suffix=f".{cand.format}", metadata={"worker_metadata": dict(cand.metadata), ...})`

### Requirement: ComfyUI worker invokes the agent CLI via subprocess

The system SHALL invoke ComfyUI through `python -m comfyui_api run` as a subprocess and parse the stdout JSON envelope, replacing direct `/prompt` + `/history` + `/view` HTTP calls. The worker class `ComfyAgentWorker` SHALL accept the following constructor parameters (keyword-only):

- `scripts_dir: Path` — REQUIRED, from `FORGEUE_COMFY_SCRIPTS_DIR`
- `model_id: str` — REQUIRED, used to infer `_capability` via `_CAPABILITY_BY_MODEL_ID` table; supported ids `"comfy/local"` (image) / `"comfy/local-mesh"` (mesh) / `"comfy/local-audio"` (audio); unknown id raises `WorkerUnsupportedResponse` per the Requirement "ComfyAgentWorker dispatches by capability inferred from model id"
- `run_id: str` — REQUIRED, from `ctx.run.run_id`
- `project_id: str` — REQUIRED, from `ctx.task.project_id` (raises `WorkerUnsupportedResponse` if None or empty)
- `artifacts_dir: Path` — REQUIRED, from `ctx.run_dir` (raises `WorkerUnsupportedResponse` if None or not a directory)
- `python_exe: Path | None = None` — OPTIONAL, defaults to `sys.executable` if None
- `default_lifecycle: str = "none"` — OPTIONAL, MUST be `"none"` in this change scope (constraint inherited from `comfy-agent-cli-adoption` D6); other values raise `WorkerUnsupportedResponse`

The `model_id` parameter is the signature extension introduced by `comfy-agent-cli-mesh-audio-video-adoption` (image+mesh) and reused by this change (image+mesh+audio without further constructor extension).

Each call SHALL pass `--workflow <manifest_name>` + `--params <json>` + `--project <task.project_id>` + `--lifecycle none` + `--timeout <s>`, and parse the resulting JSON whose `outputs.<key>` field carries absolute paths per the resolved capability (`outputs.images` for image-mode, `outputs.glb` for mesh-mode, `outputs.audio` for audio-mode). The worker MUST NOT speak ComfyUI HTTP directly. The dispatch-method-by-capability table is:

| capability | entry point method | return type | source bytes input |
|---|---|---|---|
| `image` | `ComfyWorker.generate(spec, num_candidates, seed, timeout_s)` (existing ABC method) | `list[ImageCandidate]` | none (text-to-image) |
| `mesh` | `ComfyAgentWorker.generate_mesh(spec, source_image_filename, num_candidates, seed, timeout_s)` (NOT part of `ComfyWorker` ABC; mesh dispatch via `GenerateMeshExecutor._generate_via_comfy_worker` per Phase 1 D7) | `list[MeshCandidate]` | source image filename inside ComfyUI input/ directory (filename only, written by executor before subprocess invocation) |
| `audio` | `ComfyAgentWorker.generate_audio(spec, num_candidates, seed, timeout_s)` (NEW for this change; NOT part of `ComfyWorker` ABC; audio dispatch via `GenerateAudioExecutor._generate_via_comfy_worker` per design D7) | `list[AudioCandidate]` | none (text-to-audio; prompt lives in `spec["comfy_params"]`) |

All three methods share a private helper `_run_subprocess_and_validate(spec, timeout_s) -> dict` that runs the subprocess, parses stdout JSON, and invokes capability-aware `_validate_outputs(outputs)`.

#### Scenario: ComfyAgentWorker (image) reads env config and calls comfyui_api with task.project_id (regression)

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`, `FORGEUE_COMFY_PYTHON_EXE` unset, `FORGEUE_COMFY_LIFECYCLE` unset; resolved route `ResolvedRoute(model="comfy/local", ...)`; `ctx.run.run_id="run_abc"`; `ctx.task.project_id="proj_comfy_smoke"`; `ctx.run_dir=Path("artifacts/2026-05-02/run_abc")`
- **WHEN** `GenerateImageExecutor._generate_via_worker` constructs `worker = ComfyAgentWorker(scripts_dir=..., model_id="comfy/local", ...)` and calls `worker.generate(spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl", ...}, num_candidates=1, seed=42, timeout_s=300)`
- **THEN** the worker's `_capability == "image"`; the worker spawns subprocess and reads PNG bytes from `outputs.images`; returns `list[ImageCandidate]`

#### Scenario: ComfyAgentWorker (mesh) calls generate_mesh with source_image_filename injected (regression)

- **GIVEN** environment variables as above + `FORGEUE_COMFY_INPUT_DIR=D:/AI/ComfyUI/apps/official-main-git-v092/input`; resolved route `ResolvedRoute(model="comfy/local-mesh", ..., pricing=None)`; an upstream image step has produced source bytes resolved via `_resolve_source_image(ctx)` and written to `D:/AI/ComfyUI/apps/official-main-git-v092/input/forgeue_abc123def456.png`
- **WHEN** `GenerateMeshExecutor._generate_via_comfy_worker` constructs `worker = ComfyAgentWorker(model_id="comfy/local-mesh", ...)` and calls `worker.generate_mesh(spec=..., source_image_filename="forgeue_abc123def456.png", ...)`
- **THEN** the worker's `_capability == "mesh"`; reads GLB bytes from `outputs.glb`; returns `list[MeshCandidate]`

#### Scenario: ComfyAgentWorker (audio) calls generate_audio with prompt embedded in spec.comfy_params (NEW for this change)

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`, `FORGEUE_COMFY_LIFECYCLE` unset; resolved route `ResolvedRoute(model="comfy/local-audio", api_key_env=None, api_base=None, kind="audio", pricing=None)`; `ctx.run.run_id="run_audio_smoke"`; `ctx.task.project_id="proj_audio_smoke"`; `ctx.run_dir=Path("artifacts/2026-05-XX/run_audio_smoke")`; **NO** `FORGEUE_COMFY_INPUT_DIR` env var read (audio has no source bytes path)
- **WHEN** `GenerateAudioExecutor._generate_via_comfy_worker` constructs `worker = ComfyAgentWorker(scripts_dir=..., model_id="comfy/local-audio", run_id="run_audio_smoke", project_id="proj_audio_smoke", artifacts_dir=..., default_lifecycle="none")` and calls `worker.generate_audio(spec={"comfy_workflow": "Audio_Workflows/audio_stable_audio_example", "comfy_params": {"text": "uplifting electronic dance music, 130bpm", "negative_prompt": "", "duration_seconds": 10.0, "seed": 42, "steps": 50}, "comfy_lifecycle": "none"}, num_candidates=1, seed=42, timeout_s=300)`
- **THEN** the worker's `_capability == "audio"`; the worker spawns subprocess with argv `[sys.executable, "-m", "comfyui_api", "run", "--workflow", "Audio_Workflows/audio_stable_audio_example", "--params", '{"text":"uplifting...","negative_prompt":"","duration_seconds":10.0,"seed":42,"steps":50}', "--project", "proj_audio_smoke", "--lifecycle", "none", "--timeout", "300"]`; the executor does NOT mutate `spec["comfy_params"]` (no injection per design D8); `_validate_outputs` accepts `outputs.audio` non-empty and rejects `outputs.images / glb / video` per the audio capability rules; the worker reads FLAC / MP3 / WAV bytes from `outputs.audio` paths, detects format from file extension, validates magic bytes (F5 round-1), and returns `list[AudioCandidate(data=..., format=..., metadata={comfy_manifest, comfy_params_snapshot, comfy_capability="audio", comfy_original_filename, ...}, duration_seconds=None, sample_rate=None)]` (F-Plan-R4-B round-4 修订:`duration_seconds` / `sample_rate` 在本 change scope 始终 `None`,与 design D5/D10 + artifact-contract spec + F4 round-1 probe 决策一致;ComfyUI agent CLI `extract_outputs` 不暴露 audio metadata;follow-on `audio-metadata-parser` change 才引入解析)
