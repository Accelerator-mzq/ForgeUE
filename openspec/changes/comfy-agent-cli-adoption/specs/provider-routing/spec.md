## ADDED Requirements

### Requirement: ComfyUI worker invokes the agent CLI via subprocess

The system SHALL invoke ComfyUI through `python -m comfyui_api run` as a subprocess and parse the stdout JSON envelope, replacing direct `/prompt` + `/history` + `/view` HTTP calls. The worker `ComfyAgentWorker` SHALL accept `scripts_dir` (path to `D:/AI/ComfyUI/scripts/`), optional `python_exe` (default `sys.executable`), and `default_lifecycle` (currently restricted to the single value `"none"` — see D6 in design.md for the rationale; the agent CLI itself supports four lifecycle modes but ForgeUE in this change only allows `none` because the orchestrator's `asyncio.to_thread` wrapping in `src/framework/runtime/orchestrator.py:474` makes upstream `CancelledError` unable to reach `worker.submit`, so any framework-managed lifecycle that spawns a ComfyUI server child process would risk orphan processes on cancel). Each call SHALL pass `--workflow <manifest_name>` (e.g. `GameAssets/01b_singleview_sdxl`) + `--params <json>` + `--project <task.project_id>` (the ForgeUE business project id, NOT the run id) + `--lifecycle none` + `--timeout <s>`, and parse the resulting JSON whose `outputs.images` field carries absolute PNG paths. The worker MUST NOT speak ComfyUI HTTP directly.

#### Scenario: ComfyAgentWorker calls comfyui_api with the manifest workflow name and JSON params

- **GIVEN** a `ComfyAgentWorker(scripts_dir=Path("D:/AI/ComfyUI/scripts"), default_lifecycle="none", run_id="run_abc", project_id="proj_comfy_smoke", artifacts_dir=Path("artifacts/2026-05-02/run_abc"))` constructed by the executor with `project_id=ctx.task.project_id` (the ForgeUE business project id, not the run id)
- **WHEN** an executor calls `worker.submit(spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {"text": "oak barrel", "seed": 42}, "comfy_lifecycle": "none"}, timeout_s=300)`
- **THEN** the worker spawns `subprocess` with argv `[sys.executable, "-m", "comfyui_api", "run", "--workflow", "GameAssets/01b_singleview_sdxl", "--params", '{"text":"oak barrel","seed":42}', "--project", "proj_comfy_smoke", "--lifecycle", "none", "--timeout", "300"]` and `cwd=scripts_dir`; `python_exe=None` in the registry resolves to `sys.executable`; the worker decodes `result.stdout` as JSON, asserts `data["ok"] is True` and reads PNG bytes from each path in `data["outputs"]["images"]`; the worker MUST NOT issue any HTTP request to `localhost:8188`

### Requirement: ComfyUI bundle spec uses manifest workflow + JSON params

The system SHALL accept `step.config.spec.comfy_workflow` (string, manifest name as listed by `python -m comfyui_api list`), `step.config.spec.comfy_params` (dict, passed to `--params`), and optional `step.config.spec.comfy_lifecycle` (string; in this change scope MUST be `"none"`; defaults to the worker's `default_lifecycle="none"`). The system SHALL reject the legacy `step.config.spec.workflow_graph` field with `WorkerUnsupportedResponse` so a partially migrated bundle fails fast rather than silently going to the wrong code path. The system SHALL also reject any `comfy_lifecycle` value other than `"none"` with `WorkerUnsupportedResponse` until the future `executor-async-rewrite` change (TBD-010) lifts the cancel-reachability constraint.

#### Scenario: Bundle declaring comfy_workflow + comfy_params resolves through ComfyAgentWorker

- **GIVEN** a step config `{"spec": {"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {"text": "oak barrel", "seed": 42}, "comfy_lifecycle": "none"}, "num_candidates": 1, "worker_timeout_s": 300}`
- **WHEN** the `generate_image` executor's `_resolve_spec` reads the config
- **THEN** the executor passes `{"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {...}, "comfy_lifecycle": "none"}` to `ComfyAgentWorker.submit`; the executor MUST NOT read or accept any `workflow_graph` field

#### Scenario: Bundle still carrying legacy workflow_graph fails fast

- **GIVEN** a step config still containing `step.config.spec.workflow_graph` (a leftover from the v1 inline-workflow bundle path captured at commit 292420a)
- **WHEN** the executor or worker resolves the spec
- **THEN** `WorkerUnsupportedResponse` is raised with a message naming the deprecated field and pointing at the new contract; no subprocess is spawned, no HTTP call is made, and `FailureModeMap` routes the failure to `unsupported_response` → `Decision.abort_or_fallback`

#### Scenario: Bundle requesting a non-none comfy_lifecycle is rejected

- **GIVEN** a step config with `step.config.spec.comfy_lifecycle: "ensure_running"` (or any other value besides `"none"`)
- **WHEN** the executor or worker resolves the spec
- **THEN** `WorkerUnsupportedResponse` is raised with a message naming the unsupported lifecycle value and citing TBD-010 (`executor-async-rewrite`) as the future change that will lift the restriction; no subprocess is spawned

### Requirement: comfy_api provider, virtual model id, and alias register with ModelRegistry

The system SHALL register three concrete entries in `config/models.yaml` so that ComfyUI integration flows through the standard `provider_policy.models_ref` resolution path (FR-MODEL-001 + ADR-002 single source of truth):

1. A `providers.comfy_api` entry with `kind: subprocess_cli`, `scripts_dir: <absolute path>`, optional `python_exe` (null = `sys.executable`), and `default_lifecycle: "none"` (only value supported in this change scope per D6).
2. A `models.comfy/local` entry with `provider: comfy_api`, `kind: image`, `pricing: null` (local GPU has no per-call cost; the FR-COST-008/009 `metrics["cost_usd"]` interface is preserved at `0.0`).
3. An `aliases.image_local` entry with `preferred: ["comfy/local"]` and `fallback: []` (no cross-provider fallback — local ComfyUI is treated as an independent capability path; bundles that want cloud fallback declare it explicitly via Step-level `fallback_models`).

The ModelRegistry loader SHALL accept `subprocess_cli` as a valid `kind` and SHALL surface a `RegistryReferenceError` on unknown subfields under any of the three entries (consistent with the existing typo-protection contract for pricing fields). The `comfy/local` model id is a virtual placeholder — ComfyUI's real "model" is the `comfy_workflow` manifest name carried in `step.config.spec.comfy_workflow`, but the placeholder lets the standard alias-resolution path produce a `PreparedRoute` so `CapabilityRouter` can dispatch to `ComfyAgentWorker` uniformly with all other providers.

#### Scenario: config/models.yaml comfy_api provider + comfy/local model + image_local alias parse cleanly

- **GIVEN** a `config/models.yaml` containing
  ```yaml
  providers:
    comfy_api:
      kind: subprocess_cli
      scripts_dir: "D:/AI/ComfyUI/scripts"
      python_exe: null
      default_lifecycle: "none"

  models:
    comfy/local:
      provider: comfy_api
      kind: image
      pricing: null

  aliases:
    image_local:
      preferred: ["comfy/local"]
      fallback: []
  ```
- **WHEN** `ModelRegistry.from_yaml(path)` parses the file
- **THEN** the registry exposes the `comfy_api` provider with the four declared fields, the `comfy/local` model with `provider="comfy_api"` / `kind="image"` / `pricing=None`, and the `image_local` alias resolves to `[ResolvedRoute(model="comfy/local", api_key_env=None, api_base=None, kind="image", pricing=None)]`; an unknown subfield in any of the three entries (e.g. `comfy_api.foo: bar`, `models["comfy/local"].bar: baz`, `aliases.image_local.zzz: 1`) raises `RegistryReferenceError` so typos do not silently degrade to defaults

#### Scenario: Bundle declaring models_ref image_local is expanded via ModelRegistry

- **GIVEN** a bundle Step whose `provider_policy` declares `models_ref: "image_local"` (e.g. the rewritten `examples/comfy_local_smoke.json`)
- **WHEN** `load_task_bundle` runs `expand_model_refs(raw, get_model_registry())` on the parsed dict before any `Step.model_validate` call
- **THEN** the alias is replaced in-place by concrete `preferred_models: ["comfy/local"]` + `fallback_models: []`, the resulting Step passes Pydantic validation, and the bundle never reaches the runtime carrying a bare `models_ref: "image_local"` string; downstream `CapabilityRouter` matches `comfy/local` to the (yet-to-be-registered) `ComfyAgentWorker` adapter (registration order: `ComfyAgentWorker` BEFORE `LiteLLMAdapter` wildcard, per the Wildcard-last invariant)

### Requirement: Dry-run pass validates ComfyUI subprocess reachability when comfy_api is in prepared_routes

The system SHALL extend the dry-run pass (FR-LC-002) to validate ComfyUI reachability ONLY when the resolved `prepared_routes` actually contain a route whose underlying provider is `comfy_api`. The validation SHALL check `Path(scripts_dir).exists()` AND `(Path(scripts_dir) / "comfyui_api").is_dir()` AND `python -m comfyui_api status` returns exit code 0 within a 30-second probe timeout. Any failure SHALL fail the Run before step execution begins, and the error message SHALL tell the user how to start ComfyUI (`python -m comfyui_api serve` then re-run). Bundles that do not resolve to `comfy_api` (e.g. those using `image_fast` / `image_strong` aliases routing to qwen / glm) SHALL NOT trigger the probe.

#### Scenario: Dry-run pass surfaces missing scripts_dir when bundle uses comfy_api

- **GIVEN** a bundle whose `step_image` resolves through `image_local` alias → `comfy/local` model → `comfy_api` provider, and `config/models.yaml` `providers.comfy_api.scripts_dir` points to a non-existent directory
- **WHEN** `framework.run` invokes `DryRunPass.run(...)` before reaching the scheduler
- **THEN** the Run transitions to `failed` immediately, the failure reason names the missing `scripts_dir` path AND tells the user to verify the path or start ComfyUI via `python -m comfyui_api serve`, and no `subprocess.run` of `python -m comfyui_api` is ever spawned for actual generation

#### Scenario: Dry-run pass skips ComfyUI probe when bundle does not use comfy_api

- **GIVEN** a bundle whose all `image.generation` steps resolve through `image_fast` alias → qwen / glm models (no route in `prepared_routes` references the `comfy_api` provider)
- **WHEN** `framework.run` invokes `DryRunPass.run(...)`
- **THEN** the dry-run does NOT spawn `python -m comfyui_api status` or otherwise touch `D:/AI/ComfyUI/scripts/`; the Run proceeds to scheduling normally even on a host where ComfyUI is not installed

### Requirement: ComfyUI subprocess failure modes map into the existing exception hierarchy

The system SHALL map subprocess failures into the existing three-tier worker exception hierarchy, preserving the FR-RUNTIME-012 invariant that `*UnsupportedResponse` short-circuits same-step retries:

| Subprocess condition | Mapped exception | FailureMode | Verdict |
|---|---|---|---|
| `scripts_dir` missing OR `python -m comfyui_api` module not found | `WorkerUnsupportedResponse` | `unsupported_response` | `abort_or_fallback` |
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

The system SHALL route non-OpenAI protocols via `model.startswith(...)` prefix matching inside dedicated adapters under `src/framework/providers/`, OR via `provider.kind`-based dispatch for non-HTTP protocols (currently `subprocess_cli` for ComfyUI agent CLI). Each non-OpenAI protocol family SHALL ship its own adapter / worker module: DashScope (`qwen_multimodal_adapter.py`), Hunyuan tokenhub (`hunyuan_tokenhub_adapter.py` for image, `providers/workers/mesh_worker.py` for 3D), and ComfyUI agent CLI (`providers/workers/comfy_worker.py::ComfyAgentWorker` invoking `python -m comfyui_api` as a subprocess; supersedes the previous ComfyUI HTTP adapter).

#### Scenario: qwen/ and hunyuan/ prefixes route to their dedicated adapters via supports() prefix match

- GIVEN `CapabilityRouter` with `QwenMultimodalAdapter` and `HunyuanImageAdapter` registered ahead of the wildcard `LiteLLMAdapter`
- WHEN a request targets a model whose id begins with `qwen/` or `hunyuan/`
- THEN routing reaches the matching dedicated adapter first because `QwenMultimodalAdapter.supports(model)` returns `model.startswith("qwen/")` (`src/framework/providers/qwen_multimodal_adapter.py`) and `HunyuanImageAdapter.supports(model)` returns `model.startswith("hunyuan/")` (`src/framework/providers/hunyuan_tokenhub_adapter.py`); the call therefore bypasses LiteLLM's OpenAI-compatible chat path and uses the protocol-specific submit / poll / download flow built into the dedicated adapter

#### Scenario: comfy/local routes to ComfyAgentWorker via provider.kind=subprocess_cli dispatch

- GIVEN `CapabilityRouter` with the ComfyUI dispatch path registered ahead of the wildcard `LiteLLMAdapter`, and `config/models.yaml` declaring `providers.comfy_api.kind: subprocess_cli` + `models.comfy/local.provider: comfy_api`
- WHEN a request targets the `comfy/local` model id (resolved via `image_local` alias)
- THEN routing dispatches to `ComfyAgentWorker` (matched on `prepared_route.kind == "image"` AND `provider_kind == "subprocess_cli"`) which spawns `python -m comfyui_api run` as a subprocess; the call therefore bypasses the HTTP adapter chain and uses the subprocess JSON envelope flow built into `ComfyAgentWorker`; LiteLLM's wildcard never sees `comfy/local` because the dispatch happens before the adapter chain is walked
