## ADDED Requirements

### Requirement: ComfyUI worker invokes the agent CLI via subprocess

The system SHALL invoke ComfyUI through `python -m comfyui_api run` as a subprocess and parse the stdout JSON envelope, replacing direct `/prompt` + `/history` + `/view` HTTP calls. The worker class `ComfyAgentWorker` SHALL accept `scripts_dir`, `python_exe`, `default_lifecycle`, `run_id`, `project_id`, and `artifacts_dir` as constructor parameters; the **first three** SHALL come from environment variables (`FORGEUE_COMFY_SCRIPTS_DIR`, `FORGEUE_COMFY_PYTHON_EXE`, `FORGEUE_COMFY_LIFECYCLE`) read at executor construction time, NOT from `ProviderDef` fields (the existing `ProviderDef` schema in `src/framework/providers/model_registry.py:117-122` only has `name / api_key_env / api_base` and SHALL NOT be extended in this change — see design.md D7 + D-FutureScope TBD-011 for the deferred schema-extension change). `default_lifecycle` SHALL default to `"none"` if `FORGEUE_COMFY_LIFECYCLE` is unset, and SHALL be restricted to the single value `"none"` in this change scope (see D6 in design.md for the rationale). Each call SHALL pass `--workflow <manifest_name>` + `--params <json>` + `--project <task.project_id>` + `--lifecycle none` + `--timeout <s>`, and parse the resulting JSON whose `outputs.images` field carries absolute PNG paths. The worker MUST NOT speak ComfyUI HTTP directly.

#### Scenario: ComfyAgentWorker reads env config and calls comfyui_api with task.project_id

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`, `FORGEUE_COMFY_PYTHON_EXE` unset (defaults to `sys.executable`), `FORGEUE_COMFY_LIFECYCLE` unset (defaults to `"none"`); a `ctx.run.run_id="run_abc"`; a `ctx.task.project_id="proj_comfy_smoke"`; a `ctx.run_dir=Path("artifacts/2026-05-02/run_abc")` (run_dir injected by Orchestrator per the runtime-core spec delta in this change)
- **WHEN** an executor constructs `worker = ComfyAgentWorker(scripts_dir=Path(env["FORGEUE_COMFY_SCRIPTS_DIR"]), python_exe=None, default_lifecycle=env.get("FORGEUE_COMFY_LIFECYCLE", "none"), run_id=ctx.run.run_id, project_id=ctx.task.project_id, artifacts_dir=ctx.run_dir)` and calls `worker.submit(spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {"text": "oak barrel", "seed": 42}, "comfy_lifecycle": "none"}, timeout_s=300)`
- **THEN** the worker spawns `subprocess` with argv `[sys.executable, "-m", "comfyui_api", "run", "--workflow", "GameAssets/01b_singleview_sdxl", "--params", '{"text":"oak barrel","seed":42}', "--project", "proj_comfy_smoke", "--lifecycle", "none", "--timeout", "300"]` and `cwd=scripts_dir`; the worker decodes `result.stdout` as JSON, asserts `data["ok"] is True`, copies each path in `data["outputs"]["images"]` into `artifacts_dir / "comfy" /`, and reads PNG bytes from the copied paths; the worker MUST NOT issue any HTTP request to `localhost:8188`; `project_id` is REQUIRED (not optional with `None` default — `ComfyAgentWorker.__init__` SHALL raise `WorkerUnsupportedResponse` if `project_id is None` or empty)

### Requirement: ComfyUI bundle spec uses manifest workflow + JSON params

The system SHALL accept `step.config.spec.comfy_workflow` (string, manifest name as listed by `python -m comfyui_api list`), `step.config.spec.comfy_params` (dict, passed to `--params`), and optional `step.config.spec.comfy_lifecycle` (string; in this change scope MUST be `"none"`; defaults to `"none"`). The system SHALL reject the legacy `step.config.spec.workflow_graph` field with `WorkerUnsupportedResponse` so a partially migrated bundle fails fast rather than silently going to the wrong code path. The system SHALL also reject any `comfy_lifecycle` value other than `"none"` with `WorkerUnsupportedResponse` until the future `executor-async-rewrite` change (TBD-010) lifts the cancel-reachability constraint.

#### Scenario: Bundle declaring comfy_workflow + comfy_params resolves through ComfyAgentWorker via worker dispatch

- **GIVEN** a step config `{"spec": {"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {"text": "oak barrel", "seed": 42}, "comfy_lifecycle": "none"}, "num_candidates": 1, "worker_timeout_s": 300}` whose `provider_policy.models_ref` resolves to a `prepared_routes` containing `ResolvedRoute(model="comfy/local", ...)`
- **WHEN** the `generate_image` executor's `_resolve_spec` reads the config AND `_should_use_api_path` (the worker-dispatch variant) detects the `comfy/local` model id
- **THEN** the executor takes the worker-dispatch branch (NOT the router-dispatch branch); it constructs `ComfyAgentWorker` from env config + ctx fields, then calls `await worker.submit(spec={"comfy_workflow": ..., "comfy_params": ..., "comfy_lifecycle": "none"}, timeout_s=300)`; the executor MUST NOT route through `router.image_generation(prompt, n, size, extra)` for `comfy/local`-bearing routes; the executor MUST NOT read or accept any `workflow_graph` field

#### Scenario: Bundle still carrying legacy workflow_graph fails fast

- **GIVEN** a step config still containing `step.config.spec.workflow_graph` (a leftover from the v1 inline-workflow bundle path captured at commit 292420a)
- **WHEN** the executor or worker resolves the spec
- **THEN** `WorkerUnsupportedResponse` is raised with a message naming the deprecated field and pointing at the new contract; no subprocess is spawned, no HTTP call is made, and `FailureModeMap` routes the failure to `unsupported_response` → `Decision.abort_or_fallback`

#### Scenario: Bundle requesting a non-none comfy_lifecycle is rejected

- **GIVEN** a step config with `step.config.spec.comfy_lifecycle: "ensure_running"` (or any other value besides `"none"`)
- **WHEN** the executor or worker resolves the spec
- **THEN** `WorkerUnsupportedResponse` is raised with a message naming the unsupported lifecycle value and citing TBD-010 (`executor-async-rewrite`) as the future change that will lift the restriction; no subprocess is spawned

### Requirement: comfy_api provider, virtual model id, and alias register with ModelRegistry without extending ProviderDef schema

The system SHALL register three concrete entries in `config/models.yaml` so that ComfyUI integration flows through the standard `provider_policy.models_ref` resolution path (FR-MODEL-001 + ADR-002 single source of truth), WITHOUT extending the existing `ProviderDef` schema:

1. A `providers.comfy_api` entry with ONLY the `ProviderDef`-supported fields `api_key_env: null` and `api_base: null` (the `comfy_api` provider exists in the registry as a placeholder so `models.comfy/local` can reference it; ComfyUI worker config like `scripts_dir` / `python_exe` / `default_lifecycle` lives in environment variables `FORGEUE_COMFY_*`, NOT in the YAML — see design.md D7).
2. A `models.comfy/local` entry with REQUIRED `id: "comfy/local"` field (the loader at `src/framework/providers/model_registry.py:290-293` raises `ValueError` if `id` is missing — round 1 contract sketch omitted this), plus `provider: comfy_api`, `kind: image`, `pricing: null` (local GPU has no per-call cost; the FR-COST-008/009 `metrics["cost_usd"]` interface is preserved at `0.0`).
3. An `aliases.image_local` entry with `preferred: ["comfy/local"]` and `fallback: []` (no cross-provider fallback — local ComfyUI is treated as an independent capability path; bundles that want cloud fallback declare it explicitly via Step-level `fallback_models`).

The ModelRegistry loader SHALL surface a `RegistryReferenceError` on unknown subfields under any of the three entries (consistent with the existing typo-protection contract for pricing fields). The `comfy/local` model id is a virtual placeholder — ComfyUI's real "model" is the `comfy_workflow` manifest name carried in `step.config.spec.comfy_workflow`, but the placeholder lets the standard alias-resolution path produce a `ResolvedRoute` so the executor can dispatch on `model == "comfy/local"` uniformly with all other providers (mesh worker uses the same model-id-based dispatch pattern via `HunyuanTokenhubMeshWorker`).

#### Scenario: config/models.yaml comfy_api + comfy/local + image_local parse cleanly without ProviderDef schema extension

- **GIVEN** a `config/models.yaml` containing
  ```yaml
  providers:
    comfy_api:
      api_key_env: null     # placeholder; worker config lives in env vars
      api_base: null

  models:
    comfy/local:
      id: "comfy/local"     # REQUIRED (loader raises if missing)
      provider: comfy_api
      kind: image
      pricing: null

  aliases:
    image_local:
      preferred: ["comfy/local"]
      fallback: []
  ```
- **WHEN** `ModelRegistry.from_yaml(path)` parses the file
- **THEN** the registry exposes the `comfy_api` provider with `name="comfy_api"`, `api_key_env=None`, `api_base=None` (no extra fields expected); the `comfy/local` model with `id="comfy/local"` / `provider=ProviderDef(name="comfy_api", ...)` / `kind="image"` / `pricing=None`; the `image_local` alias resolves to `[ResolvedRoute(model="comfy/local", api_key_env=None, api_base=None, kind="image", pricing=None)]`; an unknown subfield in any of the three entries raises `RegistryReferenceError`; if the `models.comfy/local.id` field is missing, the loader raises `ValueError("model 'comfy/local' missing 'id'")` per `_parse_models` line 290-293

#### Scenario: Bundle declaring models_ref image_local is expanded via ModelRegistry

- **GIVEN** a bundle Step whose `provider_policy` declares `models_ref: "image_local"` (e.g. the rewritten `examples/comfy_local_smoke.json`)
- **WHEN** `load_task_bundle` runs `expand_model_refs(raw, get_model_registry())` on the parsed dict before any `Step.model_validate` call
- **THEN** the alias is replaced in-place by concrete `preferred_models: ["comfy/local"]` + `fallback_models: []`, the resulting Step passes Pydantic validation, and the bundle never reaches the runtime carrying a bare `models_ref: "image_local"` string; downstream `GenerateImageExecutor._should_use_api_path` (worker-dispatch variant) detects the `comfy/local` model id and takes the worker dispatch branch instead of `_generate_via_router`

### Requirement: GenerateImageExecutor dispatches comfy/local to ComfyAgentWorker without going through router

The system SHALL extend `GenerateImageExecutor` to detect when any `prepared_route.model == "comfy/local"` is present and, in that case, take a dedicated **worker dispatch branch** that constructs `ComfyAgentWorker` from environment config + `StepContext` and invokes `worker.submit(spec, *, timeout_s)` directly, parallel to how `GenerateMeshExecutor` invokes `HunyuanTokenhubMeshWorker` without going through `CapabilityRouter.image_generation`. The router-dispatch branch (`_generate_via_router` calling `router.image_generation(prompt, n, size, extra)` from `spec.prompt_summary`) SHALL NOT be reached for `comfy/local`-bearing routes — that path expects `prompt_summary` which the new ComfyUI bundle spec does not provide, and `LiteLLMAdapter` wildcard would otherwise wrongly claim `model="comfy/local"`.

#### Scenario: Executor takes worker dispatch branch when prepared_routes contains comfy/local

- **GIVEN** a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local", api_key_env=None, api_base=None, kind="image", pricing=None)` (resolved from `models_ref: "image_local"`)
- **WHEN** `GenerateImageExecutor._should_use_api_path(ctx)` is called (the post-change variant that checks for `comfy/local` model id)
- **THEN** the method returns False (or routes to a new `_should_use_worker_path` variant returning True for comfy/local); the executor calls `_generate_via_worker(ctx, spec)` (a new method) which constructs `ComfyAgentWorker` from env + ctx and calls `await worker.submit(spec, timeout_s=...)`; `_generate_via_router` is NOT called for this step; `router.image_generation(prompt, ...)` is NOT invoked

#### Scenario: Executor still uses router dispatch for non-comfy/local image routes

- **GIVEN** a step whose `provider_policy.prepared_routes` contains only routes with model ids like `qwen/qwen-image-2.0` or `glm-4.6v` (no `comfy/local`)
- **WHEN** `GenerateImageExecutor._should_use_api_path(ctx)` is called
- **THEN** the method returns True (existing behavior preserved); the executor calls `_generate_via_router` which invokes `router.image_generation(prompt, n, size, extra)`; the worker-dispatch branch is NOT taken; existing qwen / glm image paths are unaffected by this change

### Requirement: Dry-run pass validates ComfyUI subprocess reachability when comfy/local is in prepared_routes

The system SHALL extend the dry-run pass (FR-LC-002) to validate ComfyUI reachability ONLY when the resolved `prepared_routes` actually contain a route with `model == "comfy/local"` (this uses the model id as the dispatch key because `ResolvedRoute` does NOT carry `provider` info — see design.md D7 + Round 2 codex G1 finding for why provider.kind dispatch was rejected in this change scope). The validation SHALL check `Path(scripts_dir).exists()` AND `(Path(scripts_dir) / "comfyui_api").is_dir()` AND `python -m comfyui_api status` returns exit code 0 within a 30-second probe timeout. Any failure SHALL fail the Run before step execution begins, and the error message SHALL tell the user how to start ComfyUI (`python -m comfyui_api serve` then re-run) AND remind to set `FORGEUE_COMFY_SCRIPTS_DIR` env var if scripts_dir is unset. Bundles that do not resolve to `comfy/local` (e.g. those using `image_fast` / `image_strong` aliases routing to qwen / glm) SHALL NOT trigger the probe.

#### Scenario: Dry-run pass surfaces missing scripts_dir when bundle uses comfy/local

- **GIVEN** a bundle whose `step_image` resolves through `image_local` alias → `comfy/local` model, and either the env var `FORGEUE_COMFY_SCRIPTS_DIR` is unset OR points to a non-existent directory
- **WHEN** `framework.run` invokes `DryRunPass.run(...)` before reaching the scheduler
- **THEN** the Run transitions to `failed` immediately, the failure reason names the missing env var or scripts_dir path AND tells the user to either set `FORGEUE_COMFY_SCRIPTS_DIR` or start ComfyUI via `python -m comfyui_api serve`; no `subprocess.run` of `python -m comfyui_api` is ever spawned for actual generation

#### Scenario: Dry-run pass skips ComfyUI probe when bundle does not use comfy/local

- **GIVEN** a bundle whose all `image.generation` steps resolve through `image_fast` alias → qwen / glm models (no route in `prepared_routes` has `model == "comfy/local"`)
- **WHEN** `framework.run` invokes `DryRunPass.run(...)`
- **THEN** the dry-run does NOT spawn `python -m comfyui_api status` or otherwise touch `D:/AI/ComfyUI/scripts/`; the Run proceeds to scheduling normally even on a host where ComfyUI is not installed and `FORGEUE_COMFY_SCRIPTS_DIR` is unset

### Requirement: ComfyUI subprocess failure modes map into the existing exception hierarchy

The system SHALL map subprocess failures into the existing three-tier worker exception hierarchy, preserving the FR-RUNTIME-012 invariant that `*UnsupportedResponse` short-circuits same-step retries:

| Subprocess condition | Mapped exception | FailureMode | Verdict |
|---|---|---|---|
| `FORGEUE_COMFY_SCRIPTS_DIR` env unset OR `scripts_dir` missing OR `python -m comfyui_api` module not found | `WorkerUnsupportedResponse` | `unsupported_response` | `abort_or_fallback` |
| `project_id` is `None` or empty when constructing `ComfyAgentWorker` | `WorkerUnsupportedResponse` | `unsupported_response` | `abort_or_fallback` |
| `artifacts_dir` is `None` when constructing `ComfyAgentWorker` (G3 fix — `ctx.run_dir` was not injected) | `WorkerUnsupportedResponse` | `unsupported_response` | `abort_or_fallback` |
| Exit code 2 + stdout `error` matches `Missing required param` / `value out of range` / `value_not_in_list` | `WorkerUnsupportedResponse` | `unsupported_response` | `abort_or_fallback` |
| Stdout is not valid JSON OR JSON missing `outputs` field | `WorkerUnsupportedResponse` | `unsupported_response` | `abort_or_fallback` |
| Exit code 2 + stdout `error` matches `TimeoutError` | `WorkerTimeout` | `worker_timeout` | `retry_same_step` |
| Other exit code 2 with unrecognised error string | `WorkerError` | `worker_error` | `fallback_model` |

`asyncio.CancelledError` propagation is governed by a separate Requirement ("ComfyAgentWorker cancel is best-effort under orchestrator to_thread wrapping") below — it is NOT mapped through `FailureModeMap` because the cancel signal does not actually reach `worker.submit` in the current orchestrator architecture (see D6 in design.md).

#### Scenario: Exit code 2 with Missing required param raises WorkerUnsupportedResponse

- **GIVEN** a `ComfyAgentWorker.submit` whose subprocess returns exit code 2 with stdout `{"ok": false, "error": "ValueError: Missing required param 'text'"}`
- **WHEN** the worker parses the result
- **THEN** the worker raises `WorkerUnsupportedResponse` with a message preserving the original error string; the executor's `_should_retry` returns False; `FailureModeMap` resolves the failure to `unsupported_response` → `Decision.abort_or_fallback`; the same step is NOT retried

#### Scenario: Exit code 2 with TimeoutError raises WorkerTimeout

- **GIVEN** a `ComfyAgentWorker.submit` whose subprocess returns exit code 2 with stdout `{"ok": false, "error": "TimeoutError: Prompt did not complete within 300s"}`
- **WHEN** the worker parses the result
- **THEN** the worker raises `WorkerTimeout`; `FailureModeMap` resolves to `worker_timeout` → `Decision.retry_same_step` (default at most 2 retries)

### Requirement: ComfyAgentWorker cancel is best-effort under orchestrator to_thread wrapping

The system SHALL document that `CancelledError` propagation does NOT reach `ComfyAgentWorker.submit` while the synchronous `GenerateImageExecutor.execute` is wrapped by `asyncio.to_thread(executor.execute, ctx)` in `src/framework/runtime/orchestrator.py:474` (see orchestrator.py:286-296 inline notes — "sync executors in `asyncio.to_thread` can't be interrupted"). Under the `lifecycle="none"` constraint mandated by this change (D6), the `comfyui_api` subprocess naturally exits when ComfyUI completes the request; the worker thread then completes; the outer Future has already been cancelled by the orchestrator and its result is discarded. No orphan processes are produced because lifecycle=none does NOT spawn the ComfyUI server process — the server is owned by the user. The future `executor-async-rewrite` change (TBD-010) SHALL re-evaluate this contract once the orchestrator path can `await` worker submit directly.

#### Scenario: Cancel during ComfyAgentWorker run does not produce orphan processes

- **GIVEN** a step running through `ComfyAgentWorker.submit` with a `comfyui_api` subprocess in flight, and a sibling DAG step raising an exception that triggers `cascade_terminate`
- **WHEN** the orchestrator cancels the outer Future for the in-flight image step
- **THEN** the `comfyui_api` subprocess continues to run in the worker thread until ComfyUI finishes the request naturally (or the worker `timeout_s` fires); the worker thread completes; no `comfyui_api` or ComfyUI server child process is left as an orphan because lifecycle=none does NOT spawn a server child; the orchestrator's already-set `cancel()` on the Future means the result is discarded; the run terminates as expected by the cascade-cancel path

### Requirement: ComfyAgentWorker rejects non-image outputs in the image-generation path

The system SHALL treat a non-empty `outputs.audio` or `outputs.glb` field in the agent CLI response as `WorkerUnsupportedResponse` when invoked through `ComfyAgentWorker` in the `image.generation` capability path. Mesh, audio, and video workflows are out of scope for this change; mixing them into the image generation path would silently drop produced bytes (image executor only constructs `ImageCandidate`s) and would skip the modality-specific metadata required by the `artifact-contract` mesh / audio requirements. A future change SHALL introduce dedicated mesh / audio paths before non-empty values in those fields are accepted.

#### Scenario: Workflow accidentally selected that produces a GLB raises rather than silently dropping it

- **GIVEN** a step config mistakenly using `comfy_workflow: "GameAssets/02_mini_textured_3d_hunyuan"` (a manifest that produces both a PNG preview and a GLB), invoked via the image-generation executor
- **WHEN** `ComfyAgentWorker.submit` parses the agent CLI stdout and finds `outputs.glb = ["D:/.../barrel_textured_00001_.glb"]` non-empty
- **THEN** the worker raises `WorkerUnsupportedResponse` with a message naming the unexpected non-empty field and pointing the user at the future mesh-path change; no `ImageCandidate` is constructed; no GLB is copied into the artifact tree; `FailureModeMap` resolves to `unsupported_response` → `Decision.abort_or_fallback` (no same-step retry, no silent data loss)

## MODIFIED Requirements

### Requirement: Non-OpenAI protocols ship dedicated adapters

The system SHALL route non-OpenAI protocols via either (a) `model.startswith(...)` prefix matching inside dedicated adapters under `src/framework/providers/` (used by qwen/, hunyuan/), OR (b) executor-side **model-id exact-match dispatch** to dedicated worker classes (used by `HunyuanTokenhubMeshWorker` for mesh and, after this change, `ComfyAgentWorker` for ComfyUI image generation). Each non-OpenAI protocol family SHALL ship its own adapter / worker module: DashScope (`qwen_multimodal_adapter.py`), Hunyuan tokenhub image (`hunyuan_tokenhub_adapter.py`), Hunyuan 3D mesh (`providers/workers/mesh_worker.py`), and ComfyUI agent CLI (`providers/workers/comfy_worker.py::ComfyAgentWorker` invoking `python -m comfyui_api` as a subprocess; supersedes the previous ComfyUI HTTP adapter). The executor for the relevant capability (e.g. `GenerateImageExecutor` for image, `GenerateMeshExecutor` for mesh) SHALL detect the dispatch model id and route to the dedicated worker without going through `CapabilityRouter.image_generation` / `mesh_generation` for those routes.

#### Scenario: qwen/ and hunyuan/ prefixes route to their dedicated adapters via supports() prefix match

- GIVEN `CapabilityRouter` with `QwenMultimodalAdapter` and `HunyuanImageAdapter` registered ahead of the wildcard `LiteLLMAdapter`
- WHEN a request targets a model whose id begins with `qwen/` or `hunyuan/`
- THEN routing reaches the matching dedicated adapter first because `QwenMultimodalAdapter.supports(model)` returns `model.startswith("qwen/")` (`src/framework/providers/qwen_multimodal_adapter.py`) and `HunyuanImageAdapter.supports(model)` returns `model.startswith("hunyuan/")` (`src/framework/providers/hunyuan_tokenhub_adapter.py`); the call therefore bypasses LiteLLM's OpenAI-compatible chat path and uses the protocol-specific submit / poll / download flow built into the dedicated adapter

#### Scenario: comfy/local routes to ComfyAgentWorker via executor-side model-id exact match (NOT through router)

- GIVEN a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local", ...)` and `GenerateImageExecutor` extended (per the new `GenerateImageExecutor dispatches comfy/local to ComfyAgentWorker without going through router` Requirement) with a worker-dispatch branch
- WHEN the executor's `execute(ctx)` runs and `_should_use_api_path` (post-change variant) detects the `comfy/local` model id
- THEN the executor takes the worker dispatch branch and constructs `ComfyAgentWorker` from environment config (`FORGEUE_COMFY_*`) + `ctx.run_dir` + `ctx.task.project_id` + `ctx.run.run_id`; it calls `await worker.submit(spec, timeout_s)`; `CapabilityRouter.image_generation` is NOT called for this step because the dispatch happens upstream of the adapter chain; LiteLLM's wildcard never sees `comfy/local`. This dispatch shape is parallel to how `GenerateMeshExecutor` invokes `HunyuanTokenhubMeshWorker` for mesh routes
