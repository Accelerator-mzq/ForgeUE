## ADDED Requirements

### Requirement: ComfyUI worker invokes the agent CLI via subprocess

The system SHALL invoke ComfyUI through `python -m comfyui_api run` as a subprocess and parse the stdout JSON envelope, replacing direct `/prompt` + `/history` + `/view` HTTP calls. The worker `ComfyAgentWorker` SHALL accept `scripts_dir` (path to `D:/AI/ComfyUI/scripts/`), optional `python_exe`, and `default_lifecycle` (one of `none` / `ensure_running` / `ensure_release` / `self_managed_session`). Each call SHALL pass `--workflow <manifest_name>` (e.g. `GameAssets/01b_singleview_sdxl`) + `--params <json>` + `--project <run_id>` + `--lifecycle <mode>` + `--timeout <s>`, and parse the resulting JSON whose `outputs.images` field carries absolute PNG paths. The worker MUST NOT speak ComfyUI HTTP directly.

#### Scenario: ComfyAgentWorker calls comfyui_api with the manifest workflow name and JSON params

- **GIVEN** a `ComfyAgentWorker(scripts_dir=Path("D:/AI/ComfyUI/scripts"), default_lifecycle="ensure_running", run_id="run_abc", project_id="proj_comfy_smoke", artifacts_dir=Path("artifacts/2026-05-02/run_abc"))` constructed by the executor with `project_id=ctx.task.project_id` (the ForgeUE business project id, not the run id)
- **WHEN** an executor calls `worker.submit(spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {"text": "oak barrel", "seed": 42}, "comfy_lifecycle": "ensure_running"}, timeout_s=300)`
- **THEN** the worker spawns `subprocess` with argv `[sys.executable, "-m", "comfyui_api", "run", "--workflow", "GameAssets/01b_singleview_sdxl", "--params", '{"text":"oak barrel","seed":42}', "--project", "proj_comfy_smoke", "--lifecycle", "ensure_running", "--timeout", "300"]` and `cwd=scripts_dir`; `python_exe=None` in the registry resolves to `sys.executable`; the worker decodes `result.stdout` as JSON, asserts `data["ok"] is True` and reads PNG bytes from each path in `data["outputs"]["images"]`; the worker MUST NOT issue any HTTP request to `localhost:8188`

### Requirement: ComfyUI bundle spec uses manifest workflow + JSON params

The system SHALL accept `step.config.spec.comfy_workflow` (string, manifest name as listed by `python -m comfyui_api list`), `step.config.spec.comfy_params` (dict, passed to `--params`), and optional `step.config.spec.comfy_lifecycle` (string, one of the four lifecycle modes; defaults to the worker's `default_lifecycle`). The system SHALL reject the legacy `step.config.spec.workflow_graph` field with `WorkerUnsupportedResponse` so a partially migrated bundle fails fast rather than silently going to the wrong code path.

#### Scenario: Bundle declaring comfy_workflow + comfy_params resolves through ComfyAgentWorker

- **GIVEN** a step config `{"spec": {"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {"text": "oak barrel", "seed": 42}, "comfy_lifecycle": "ensure_running"}, "num_candidates": 1, "worker_timeout_s": 300}`
- **WHEN** the `generate_image` executor's `_resolve_spec` reads the config
- **THEN** the executor passes `{"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {...}, "comfy_lifecycle": "ensure_running"}` to `ComfyAgentWorker.submit`; the executor MUST NOT read or accept any `workflow_graph` field

#### Scenario: Bundle still carrying legacy workflow_graph fails fast

- **GIVEN** a step config still containing `step.config.spec.workflow_graph` (a leftover from the v1 inline-workflow bundle path captured at commit 292420a)
- **WHEN** the executor or worker resolves the spec
- **THEN** `WorkerUnsupportedResponse` is raised with a message naming the deprecated field and pointing at the new contract; no subprocess is spawned, no HTTP call is made, and `FailureModeMap` routes the failure to `unsupported_response` → `Decision.abort_or_fallback`

### Requirement: comfy_api provider entry registers with ModelRegistry

The system SHALL register a `comfy_api` provider entry in `config/models.yaml` `providers:` section with `kind: subprocess_cli`, `scripts_dir: <absolute path>`, optional `python_exe`, and `default_lifecycle`. The ModelRegistry loader SHALL accept `subprocess_cli` as a valid `kind` and SHALL surface a `RegistryReferenceError` on unknown subfields under the `comfy_api` block (consistent with the existing typo-protection contract for pricing fields).

#### Scenario: config/models.yaml comfy_api entry parses with the new subprocess_cli kind

- **GIVEN** a `config/models.yaml` containing
  ```yaml
  providers:
    comfy_api:
      kind: subprocess_cli
      scripts_dir: "D:/AI/ComfyUI/scripts"
      python_exe: null
      default_lifecycle: "ensure_running"
  ```
- **WHEN** `ModelRegistry.from_yaml(path)` parses the file
- **THEN** the registry exposes the `comfy_api` provider with `kind="subprocess_cli"`, `scripts_dir=Path("D:/AI/ComfyUI/scripts")`, `python_exe=None`, `default_lifecycle="ensure_running"`; an unknown subfield (e.g. `comfy_api.foo: bar`) raises `RegistryReferenceError` so typos do not silently degrade to defaults

### Requirement: Dry-run pass validates ComfyUI subprocess reachability

The system SHALL extend the dry-run pass (FR-LC-002) to validate, when any step references the `image.generation` capability via `comfy_api`, that `Path(scripts_dir).exists()` AND `(Path(scripts_dir) / "comfyui_api").is_dir()` AND `python -m comfyui_api status` returns exit code 0 within a 10-second probe timeout. Any failure SHALL fail the Run before step execution begins.

#### Scenario: Dry-run pass surfaces missing scripts_dir before any step runs

- **GIVEN** a bundle whose `step_image` resolves to `comfy_api`, and `config/models.yaml` `providers.comfy_api.scripts_dir` points to a non-existent directory
- **WHEN** `framework.run` invokes `DryRunPass.run(...)` before reaching the scheduler
- **THEN** the Run transitions to `failed` immediately, the failure reason names the missing `scripts_dir` path, and no `subprocess.run` of `python -m comfyui_api` is ever spawned for actual generation

### Requirement: ComfyUI subprocess failure modes map into the existing exception hierarchy

The system SHALL map subprocess failures into the existing three-tier worker exception hierarchy, preserving the FR-RUNTIME-012 invariant that `*UnsupportedResponse` short-circuits same-step retries:

| Subprocess condition | Mapped exception | FailureMode | Verdict |
|---|---|---|---|
| `scripts_dir` missing OR `python -m comfyui_api` module not found | `WorkerUnsupportedResponse` | `unsupported_response` | `abort_or_fallback` |
| Exit code 2 + stdout `error` matches `Missing required param` / `value out of range` / `value_not_in_list` | `WorkerUnsupportedResponse` | `unsupported_response` | `abort_or_fallback` |
| Stdout is not valid JSON OR JSON missing `outputs` field | `WorkerUnsupportedResponse` | `unsupported_response` | `abort_or_fallback` |
| Exit code 2 + stdout `error` matches `TimeoutError` | `WorkerTimeout` | `worker_timeout` | `retry_same_step` |
| Other exit code 2 with unrecognised error string | `WorkerError` | `worker_error` | `fallback_model` |
| `asyncio.CancelledError` propagated to `submit()` | re-raise `CancelledError` (subprocess SIGTERM'd) | n/a | cancel chain |

#### Scenario: Exit code 2 with Missing required param raises WorkerUnsupportedResponse

- **GIVEN** a `ComfyAgentWorker.submit` whose subprocess returns exit code 2 with stdout `{"ok": false, "error": "ValueError: Missing required param 'text'"}`
- **WHEN** the worker parses the result
- **THEN** the worker raises `WorkerUnsupportedResponse` with a message preserving the original error string; the executor's `_should_retry` returns False; `FailureModeMap` resolves the failure to `unsupported_response` → `Decision.abort_or_fallback`; the same step is NOT retried

#### Scenario: Exit code 2 with TimeoutError raises WorkerTimeout

- **GIVEN** a `ComfyAgentWorker.submit` whose subprocess returns exit code 2 with stdout `{"ok": false, "error": "TimeoutError: Prompt did not complete within 300s"}`
- **WHEN** the worker parses the result
- **THEN** the worker raises `WorkerTimeout`; `FailureModeMap` resolves to `worker_timeout` → `Decision.retry_same_step` (default at most 2 retries)

#### Scenario: Cancel propagation terminates the subprocess

- **GIVEN** a long-running `ComfyAgentWorker.submit` that has spawned a `comfyui_api` subprocess
- **WHEN** the asyncio task wrapping `submit` receives `CancelledError` (run cancellation, run-level timeout, or sibling step failure in DAG mode)
- **THEN** the worker terminates the child subprocess (SIGTERM on POSIX, equivalent on Windows) before re-raising `CancelledError`; no orphan `comfyui_api` process is left after `submit` returns

### Requirement: ComfyAgentWorker rejects non-image outputs in the image-generation path

The system SHALL treat a non-empty `outputs.audio` or `outputs.glb` field in the agent CLI response as `WorkerUnsupportedResponse` when invoked through `ComfyAgentWorker` in the `image.generation` capability path. Mesh, audio, and video workflows are out of scope for this change; mixing them into the image generation path would silently drop produced bytes (image executor only constructs `ImageCandidate`s) and would skip the modality-specific metadata required by the `artifact-contract` mesh / audio requirements. A future change SHALL introduce dedicated mesh / audio paths before non-empty values in those fields are accepted.

#### Scenario: Workflow accidentally selected that produces a GLB raises rather than silently dropping it

- **GIVEN** a step config mistakenly using `comfy_workflow: "GameAssets/02_mini_textured_3d_hunyuan"` (a manifest that produces both a PNG preview and a GLB), invoked via the image-generation executor
- **WHEN** `ComfyAgentWorker.submit` parses the agent CLI stdout and finds `outputs.glb = ["D:/.../barrel_textured_00001_.glb"]` non-empty
- **THEN** the worker raises `WorkerUnsupportedResponse` with a message naming the unexpected non-empty field and pointing the user at the future mesh-path change; no `ImageCandidate` is constructed; no GLB is copied into the artifact tree; `FailureModeMap` resolves to `unsupported_response` → `Decision.abort_or_fallback` (no same-step retry, no silent data loss)
