## ADDED Requirements

### Requirement: ComfyAgentWorker dispatches by capability inferred from model id

The system SHALL extend `ComfyAgentWorker` to support multiple ComfyUI capabilities (image, mesh, and future audio / video) via a single worker class with capability dispatch driven by the resolved model id, NOT by an explicit bundle field. The worker SHALL maintain an internal table `_CAPABILITY_BY_MODEL_ID` mapping concrete `comfy/local*` model ids to capability tags (`comfy/local` → `image`, `comfy/local-mesh` → `mesh`); future audio / video capabilities will extend this table in their own follow-on changes (`comfy-agent-cli-audio-adoption` / `comfy-agent-cli-video-adoption`). The worker constructor SHALL accept the resolved `model_id` (in addition to the existing `scripts_dir` / `python_exe` / `default_lifecycle` / `run_id` / `project_id` / `artifacts_dir` parameters established by `comfy-agent-cli-adoption`); if `model_id` is not in `_CAPABILITY_BY_MODEL_ID`, the constructor SHALL raise `WorkerUnsupportedResponse` with a message naming the unknown id and listing supported ids — capability inference SHALL NOT silently fall back to image-mode. Bundle protocol (`step.config.spec.comfy_workflow` + `comfy_params` + `comfy_lifecycle: "none"`) SHALL remain unchanged from the image-only contract; users do NOT add an `outputs_kind` field. Mesh-capable bundles MAY add the optional `step.config.spec.comfy_image_param_key` field (default `"image_path"`) to declare which `comfy_params` key receives the upstream source image path (see Requirement "GenerateMeshExecutor injects upstream source image path into comfy_params before subprocess invocation").

#### Scenario: ComfyAgentWorker constructed with comfy/local-mesh enters mesh capability mode

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`, `FORGEUE_COMFY_LIFECYCLE` unset (defaults to `"none"`); a resolved `ResolvedRoute(model="comfy/local-mesh", api_key_env=None, api_base=None, kind="mesh", pricing=None)`; `ctx.run.run_id="run_mesh_smoke"`; `ctx.task.project_id="proj_mesh"`; `ctx.run_dir=Path("artifacts/2026-05-XX/run_mesh_smoke")`
- **WHEN** `GenerateMeshExecutor._generate_via_comfy_worker` constructs `ComfyAgentWorker(scripts_dir=..., model_id="comfy/local-mesh", run_id=..., project_id=..., artifacts_dir=..., default_lifecycle="none")`
- **THEN** the worker's `self._capability` attribute equals `"mesh"`; subsequent `worker.generate_mesh(spec=..., source_image_path=..., num_candidates=1, seed=42, timeout_s=600)` calls validate outputs against the mesh capability rules per the Requirement "ComfyAgentWorker output validation is capability-aware (REQUIRED + auxiliary + rejected)" below; the worker MUST NOT silently fall back to image-mode parsing

#### Scenario: ComfyAgentWorker rejects unknown model id at construction time

- **GIVEN** a hypothetical resolved route with `model="comfy/local-bogus"` (not in `_CAPABILITY_BY_MODEL_ID`)
- **WHEN** `ComfyAgentWorker(model_id="comfy/local-bogus", ...)` is invoked
- **THEN** the constructor raises `WorkerUnsupportedResponse` with a message naming the unknown id and listing the supported ids (`"comfy/local", "comfy/local-mesh"`); no subprocess is spawned; `FailureModeMap` resolves to `unsupported_response` → `Decision.abort_or_fallback`

### Requirement: ComfyAgentWorker output validation is capability-aware (REQUIRED + auxiliary + rejected)

The system SHALL validate the agent CLI stdout JSON `outputs` field against the worker's resolved capability via a single table-driven method `_validate_outputs(outputs: dict) -> None` using a three-tier rule per capability (REQUIRED key / auxiliary key set / rejected key set). The tables SHALL be:

| capability | REQUIRED non-empty key | auxiliary keys (allowed non-empty, NOT consumed) | rejected keys (raise on non-empty) |
|---|---|---|---|
| `image` | `outputs.images` | (none) | `outputs.glb`, `outputs.audio`, `outputs.video` |
| `mesh` | `outputs.glb` | `outputs.images` (PNG preview from mesh manifests like `02_mini_textured_3d_hunyuan` — tolerated, not consumed) | `outputs.audio`, `outputs.video` |
| `audio` (future) | `outputs.audio` | TBD by `comfy-agent-cli-audio-adoption` | TBD |
| `video` (future) | `outputs.video` | TBD by `comfy-agent-cli-video-adoption` | TBD |

The validation logic SHALL be:

1. If the REQUIRED key is missing or its value is empty → raise `WorkerUnsupportedResponse` naming the capability and missing key
2. If any rejected key has a non-empty value → raise `WorkerUnsupportedResponse` listing the unexpected non-empty keys
3. Auxiliary keys with non-empty values SHALL NOT raise; the worker SHALL emit an INFO-level log line recording auxiliary output count + paths for diagnostics (R2-F4 修订:MAY → SHALL,固定 logger 名 + level + 字段,确保 caplog 默认抓得到且 live smoke 不丢失辅助 preview 诊断证据), but MUST NOT construct any candidate object from auxiliary outputs. The log line SHALL be emitted via `logging.getLogger("framework.providers.workers.comfy_worker").info(...)` with structured fields `count: int`, `paths: list[str]`, `capability: str` (formatted as `f"mesh-mode auxiliary outputs.images: count={N} paths={paths!r} capability={cap!r}"` or equivalent message that contains all three fields verbatim)

This three-tier model accommodates the reality that ComfyUI mesh workflows often produce auxiliary PNG previews alongside the GLB (B4 codex finding accepted-codex 2026-05-03: image-change archived spec line 157 documents `02_mini_textured_3d_hunyuan` as a "manifest that produces both a PNG preview and a GLB"). Strict rejection of `outputs.images` in mesh-mode would render most real ComfyUI mesh manifests unusable.

#### Scenario: Mesh-mode worker raises on missing outputs.glb

- **GIVEN** a `ComfyAgentWorker` with `_capability="mesh"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"glb": [], "images": ["preview.png"]}}`
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker raises `WorkerUnsupportedResponse` with a message naming `capability='mesh'` and missing required `outputs.glb`; no `MeshCandidate` is constructed; `FailureModeMap` routes to `unsupported_response` → `Decision.abort_or_fallback`

#### Scenario: Mesh-mode worker accepts non-empty outputs.images as auxiliary preview (tolerated, not consumed)

- **GIVEN** a `ComfyAgentWorker` with `_capability="mesh"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"glb": ["asset.glb"], "images": ["preview.png"]}}` (workflow produced both a GLB and a PNG preview)
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker does NOT raise (auxiliary `outputs.images` tolerated); only `MeshCandidate` instances are constructed from `outputs.glb` (the PNG preview path is NOT loaded into bytes, NOT registered as any artifact, NOT returned in the candidate list); the worker SHALL emit an INFO log line via `logging.getLogger("framework.providers.workers.comfy_worker").info(f"mesh-mode auxiliary outputs.images: count=1 paths=['preview.png'] capability='mesh'")` (R2-F4 修订:logger 名 / level / 三字段固定;`caplog.set_level(logging.INFO, logger="framework.providers.workers.comfy_worker")` 测试可断言)

#### Scenario: Mesh-mode worker raises on rejected outputs.audio

- **GIVEN** a `ComfyAgentWorker` with `_capability="mesh"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"glb": ["asset.glb"], "audio": ["unexpected.wav"]}}`
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker raises `WorkerUnsupportedResponse` listing `outputs.audio` as a rejected non-empty key in mesh-mode

#### Scenario: Image-mode worker still rejects non-empty outputs.glb (regression of image change)

- **GIVEN** a `ComfyAgentWorker` with `_capability="image"`, whose subprocess returns stdout JSON `{"ok": true, "outputs": {"images": ["x.png"], "glb": ["x.glb"]}}`
- **WHEN** `_validate_outputs(outputs)` is called
- **THEN** the worker raises `WorkerUnsupportedResponse` (image-mode contract from `comfy-agent-cli-adoption` preserved; image-mode auxiliary set is empty so `outputs.glb` is firmly in the rejected set)

### Requirement: comfy/local-mesh model and mesh_local alias register with ModelRegistry without extending ProviderDef schema

The system SHALL register two additional entries in `config/models.yaml` (in addition to the `providers.comfy_api` + `models.comfy/local` + `aliases.image_local` entries from `comfy-agent-cli-adoption`):

1. A `models.comfy/local-mesh` entry with REQUIRED `id: "comfy/local-mesh"`, `provider: comfy_api`, `kind: mesh`, `pricing: null` (local GPU has no per-call cost; the `pricing.per_task_usd` field is therefore absent / None, which the ADR-007 boundary check treats as non-premium per the Requirement "Local ComfyUI mesh worker is NOT a premium API per the per_task_usd boundary" below).
2. An `aliases.mesh_local` entry with `preferred: ["comfy/local-mesh"]` and `fallback: []` (no cross-provider fallback — local ComfyUI mesh is independent from remote Hunyuan3D mesh; bundles wanting cloud fallback declare it explicitly via Step-level `fallback_models`).

The `providers.comfy_api` entry from `comfy-agent-cli-adoption` SHALL be reused without modification; ComfyUI worker config still lives in `FORGEUE_COMFY_*` env vars (`ProviderDef` schema extension remains TBD-011 scope). The `comfy/local-mesh` model id is a virtual placeholder — the real "model" is the ComfyUI mesh manifest name carried in `step.config.spec.comfy_workflow` — but the placeholder lets standard alias resolution produce a `ResolvedRoute` so `GenerateMeshExecutor` can dispatch on `model == "comfy/local-mesh"`.

#### Scenario: config/models.yaml mesh_local + comfy/local-mesh parse cleanly

- **GIVEN** a `config/models.yaml` extending the image-change baseline with
  ```yaml
  models:
    comfy/local-mesh:
      id: "comfy/local-mesh"
      provider: comfy_api
      kind: mesh
      pricing: null

  aliases:
    mesh_local:
      preferred: ["comfy/local-mesh"]
      fallback: []
  ```
- **WHEN** `ModelRegistry.from_yaml(path)` parses the file
- **THEN** the registry exposes `comfy/local-mesh` model with `kind="mesh"` and `pricing=None`; the `mesh_local` alias resolves to `[ResolvedRoute(model="comfy/local-mesh", api_key_env=None, api_base=None, kind="mesh", pricing=None)]`; if the `id` field is missing, the loader raises `ValueError("model 'comfy/local-mesh' missing 'id'")` per existing `_parse_models` validation

#### Scenario: Bundle declaring models_ref mesh_local is expanded via ModelRegistry

- **GIVEN** a bundle Step (e.g. the new `examples/comfy_local_smoke_mesh.json` mesh step) whose `provider_policy.models_ref: "mesh_local"`
- **WHEN** `load_task_bundle` runs `expand_model_refs(raw, get_model_registry())` before Pydantic validation
- **THEN** the alias is replaced in-place by concrete `preferred_models: ["comfy/local-mesh"]` + `fallback_models: []`; the resulting Step passes Pydantic validation; downstream `GenerateMeshExecutor._should_use_comfy_worker_path` detects the `comfy/local-mesh` model id and takes the comfy-worker dispatch branch

### Requirement: GenerateMeshExecutor dispatches comfy/local-mesh to ComfyAgentWorker via image-to-mesh path (preserves _resolve_source_image flow)

The system SHALL extend `GenerateMeshExecutor` with two pieces:

1. A helper `_should_use_comfy_worker_path(self, ctx) -> bool` returning True iff any `ctx.step.provider_policy.prepared_routes` route has `model == "comfy/local-mesh"` (R2-F1 codex finding accepted-codex 2026-05-03: `provider_policy` lives at `Step` top level per `task.py:36`, NOT nested under `step.config`; existing `generate_mesh.py:202` uses `pp = ctx.step.provider_policy` and `generate_image.py:254-257` uses the same top-level path).
2. A new method `_generate_via_comfy_worker(self, *, ctx, spec, source_image_bytes, source_image_artifact_id, num, seed, timeout_s) -> list[MeshCandidate]` that constructs `ComfyAgentWorker(model_id="comfy/local-mesh", ...)` from environment config + `StepContext`, writes `source_image_bytes` to an in-tree input file `<ctx.run_dir>/comfy/input/<sha1_hex>.png` (idempotent via hash), invokes the new public method `worker.generate_mesh(spec=..., source_image_path=...)`, and returns `list[MeshCandidate]`.

The `execute(ctx)` method SHALL call `_resolve_source_image(ctx)` UNCHANGED at the start (before any worker dispatch), then branch:

```python
source_bytes, source_image_artifact_id = _resolve_source_image(ctx)  # 不动
if self._should_use_comfy_worker_path(ctx):
    candidates = self._generate_via_comfy_worker(
        ctx=ctx, spec=spec,
        source_image_bytes=source_bytes,
        source_image_artifact_id=source_image_artifact_id,
        num=num, seed=cfg.get("seed"), timeout_s=timeout_s,    # R3-F3 修订:cfg 是 dict (`ctx.step.config or {}`);num/timeout_s 已由 executor 提前从 cfg.get(...) 算好
    )
else:
    # Existing Hunyuan / Tripo3D path (constructor-injected `self._worker.generate(source_image_bytes=..., spec=..., ...)`)
    candidates = self._worker.generate(source_image_bytes=source_bytes, spec=spec, ...)
```

The existing constructor-injected `HunyuanTokenhubMeshWorker` / `Tripo3DMeshWorker` path SHALL NOT be invoked when `comfy/local-mesh` is the route. The downstream `repo.put` loop (`generate_mesh.py:114-160`) SHALL be UNCHANGED — both comfy-mesh and remote-mesh `MeshCandidate`s share the same persistence path, with `metadata={..., "worker_metadata": dict(cand.metadata)}` carrying provenance per the artifact-contract spec.

This is a NEW dispatch mode for `GenerateMeshExecutor` parallel to the executor-side branch pattern established by `GenerateImageExecutor` for `comfy/local`: mesh dispatch now supports BOTH constructor-injected worker (remote Hunyuan3D / Tripo3D, dispatched by injection at `framework.run` time, see `generate_mesh.py:194`) AND executor-side model-id branch (local ComfyUI mesh, dispatched by route inspection in `execute`). **The image-to-mesh contract from `MeshWorker` ABC is preserved**: ComfyUI mesh sources its image from the same `_resolve_source_image(ctx)` priority chain (verdict / selected_set / direct image / candidate_set, see `generate_mesh.py:233-301`) as Hunyuan / Tripo3D — no standalone (text-to-mesh) mesh worker mode is introduced (B2 codex finding accepted-codex 2026-05-03: design D7 chose image-to-mesh path to avoid extending `MeshWorker` ABC and to keep lineage uniform across mesh worker brands).

#### Scenario: GenerateMeshExecutor takes comfy-worker dispatch branch when prepared_routes contains comfy/local-mesh

- **GIVEN** a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local-mesh", ...)`; the orchestrator has constructed `GenerateMeshExecutor` with a default `HunyuanTokenhubMeshWorker` injected; an upstream image step has produced a source image artifact resolvable by `_resolve_source_image(ctx)`
- **WHEN** `GenerateMeshExecutor.execute(ctx)` runs and `_should_use_comfy_worker_path(ctx)` returns True (any prepared_route has `model == "comfy/local-mesh"`)
- **THEN** the executor calls `_resolve_source_image(ctx)` first (unchanged from the existing path; raises if no upstream image is available — this is the same fail-fast behavior as Hunyuan / Tripo3D mesh paths); then calls `_generate_via_comfy_worker(ctx=ctx, spec=spec, source_image_bytes=source_bytes, source_image_artifact_id=source_image_artifact_id, ...)` which constructs `ComfyAgentWorker(model_id="comfy/local-mesh", ...)` inline and invokes `worker.generate_mesh(spec=..., source_image_path=Path("<ctx.run_dir>/comfy/input/<sha1_hex>.png"), ...)`; the constructor-injected `HunyuanTokenhubMeshWorker.generate` is NOT invoked

#### Scenario: GenerateMeshExecutor still uses constructor-injected worker for remote hunyuan/mesh-generation routes

- **GIVEN** a step whose `provider_policy.prepared_routes` contains only `ResolvedRoute(model="hunyuan/hy-3d-3.1", ...)` (no `comfy/local-mesh`)
- **WHEN** `GenerateMeshExecutor._should_use_comfy_worker_path(ctx)` is called
- **THEN** the method returns False; the executor takes the existing constructor-injected worker path (calls `self._worker.generate(source_image_bytes=..., spec=..., ...)`); existing remote Hunyuan3D mesh path is unaffected by this change; ADR-007 strict no-silent-retry contract continues to apply unchanged for the remote path (see Requirement "Local ComfyUI mesh worker is NOT a premium API per the per_task_usd boundary" below)

### Requirement: GenerateMeshExecutor injects upstream source image path into comfy_params before subprocess invocation

The system SHALL guarantee that `_generate_via_comfy_worker` writes the upstream `source_image_bytes` to an in-tree input file under `<ctx.run_dir>/comfy/input/<sha1_hex>.png` (where `<sha1_hex> = hashlib.sha1(source_image_bytes).hexdigest()[:16]`) before invoking the worker subprocess. The path string SHALL be passed to `ComfyAgentWorker.generate_mesh(source_image_path=...)`, which injects it into a copy of `spec["comfy_params"]` under the key resolved from `spec.get("comfy_image_param_key", "image_path")` (the optional bundle field `comfy_image_param_key` defaults to `"image_path"` per design D8; bundles SHALL declare it explicitly when the selected manifest's image input parameter has a different name like `input_image` / `image` / `source_image`). The worker SHALL NOT mutate the caller's `spec["comfy_params"]` in place — it SHALL deep-copy via `dict(spec.get("comfy_params") or {})` before injection so retries see a clean baseline.

#### Scenario: Source image bytes are written to in-tree path and injected into comfy_params under the configured key

- **GIVEN** an upstream `_resolve_source_image(ctx)` returning `(source_bytes=b"<png>", source_image_artifact_id="run_X_step_image_1")` where `hashlib.sha1(b"<png>").hexdigest()[:16] == "abc123def456"`; a step `spec` containing `comfy_workflow="Mesh/02_mini_textured_3d_hunyuan"`, `comfy_params={"seed": 42}`, `comfy_image_param_key="image_path"`, `comfy_lifecycle="none"`
- **WHEN** `_generate_via_comfy_worker(ctx, spec, source_image_bytes=source_bytes, source_image_artifact_id=..., num=1, seed=42, timeout_s=600)` is invoked
- **THEN** the executor writes `source_bytes` to `<ctx.run_dir>/comfy/input/abc123def456.png` (creating the directory if missing); calls `ComfyAgentWorker.generate_mesh(spec=spec, source_image_path=Path("<ctx.run_dir>/comfy/input/abc123def456.png"), num_candidates=1, seed=42, timeout_s=600)`; the worker constructs an enriched params dict `{"seed": 42, "image_path": "<ctx.run_dir>/comfy/input/abc123def456.png"}` (NOT mutating the caller's `spec["comfy_params"]`); the subprocess argv contains `--params '{"seed":42,"image_path":"..."}'`

#### Scenario: Bundle with custom comfy_image_param_key uses the declared key instead of default

- **GIVEN** a step `spec` with `comfy_image_param_key: "input_image"` (instead of default `"image_path"`)
- **WHEN** `worker.generate_mesh(...)` is invoked
- **THEN** the enriched params dict uses key `"input_image"` (not `"image_path"`); subprocess argv contains `--params '{...,"input_image":"<path>"}'`

### Requirement: Local ComfyUI mesh worker is NOT a premium API per the per_task_usd boundary

The system SHALL judge whether a given mesh worker route is "premium" (subject to ADR-007 strict no-silent-retry) based on the existing pricing schema field `pricing.per_task_usd` — specifically: `is_premium = (route_pricing or {}).get("per_task_usd", 0) > 0`. This boundary check SHALL be performed inline (NO new `BudgetTracker.is_premium(route)` API is introduced; B3 codex finding accepted-codex 2026-05-03 rejected the round-1 proposal of a new `input_cost_per_call` field — that field does not exist in the current pricing schema, and `BudgetTracker.estimate_mesh_call_cost_usd` already reads `per_task_usd` exclusively).

The expected boundary behavior **and the implementation locus** (R2-F2 修订 2026-05-03 — `generate_mesh.py:80-81` strict `attempts=1` for ALL `mesh.generation` is preserved unchanged for the remote path; the local-comfy retry budget is owned by `_generate_via_comfy_worker` internally, NOT by relaxing the executor main-loop strict cap):

- Local ComfyUI mesh `comfy/local-mesh` has `models.comfy/local-mesh.pricing: null` → `(None or {}).get("per_task_usd", 0) == 0` → NOT premium → `GenerateMeshExecutor` dispatches to `_generate_via_comfy_worker` BEFORE the existing `attempts=1` strict cap;`_generate_via_comfy_worker` runs its OWN retry loop using `policy.max_attempts` (where `policy = ctx.step.retry_policy or RetryPolicy()`); the "standard local retry" semantics is fully owned by this internal loop. **After all internal retries are exhausted**, the wrapped `MeshWorkerTimeout` propagates out of `_generate_via_comfy_worker`; `FailureModeMap` routes the wrapped exception to `FailureMode.mesh_worker_timeout` → `Decision.abort_or_fallback` (per `failure_mode_map.py:83-87, 142-145` — MeshWorkerTimeout matched BEFORE generic WorkerTimeout, mapped to mesh-specific terminal mode; same terminal behavior as remote Hunyuan3D mesh by design — "all retries exhausted, no further executor-level retry"). R4-F1 修订(round 4 codex finding accepted-codex 2026-05-03):round-2/3 描述的 `Decision.retry_same_step` 不真实(那是 generic `worker_timeout` mode 的 decision,wrapped MeshWorkerTimeout 走的是 mesh-specific path)。The executor main-loop `attempts=1` strict cap (line 80-81) is NOT modified — it still applies to the remote-mesh else-branch.
- Remote Hunyuan3D `models.hunyuan_3d.pricing.per_task_usd: 0.25` (per `config/models.yaml:310`) → premium → `GenerateMeshExecutor` else-branch continues to enforce ADR-007 strict no-silent-retry via the existing `attempts=1` cap and `mesh_worker._apost` not wrapped in transient retry; CLI surfaces `job_id` so user runs `probe_hunyuan_3d_query` before deciding `--resume`.

This boundary SHALL be documented in `docs/design/HLD.md` ADR-007 section as a formalization of the premium / non-premium distinction (Documentation Sync Gate task), so any future local or remote mesh worker integration inherits the correct retry semantics by reading the formalized rule rather than re-deriving it.

#### Scenario: Local ComfyUI mesh worker_timeout retries inside _generate_via_comfy_worker max_attempts times, then surfaces as wrapped MeshWorkerTimeout → abort_or_fallback (R3-F1 修订)

- **GIVEN** a `ComfyAgentWorker` with `_capability="mesh"`, route `pricing=None` (so `per_task_usd > 0` evaluates to False); `policy.max_attempts == 2`; subprocess raises `WorkerTimeout("Prompt did not complete within 600s")` on every call
- **WHEN** `GenerateMeshExecutor._generate_via_comfy_worker(...)` runs its internal retry loop
- **THEN** `worker.generate_mesh(...)` is invoked exactly **2 times** (`policy.max_attempts`); on the second failure the `WorkerTimeout` is wrapped to `MeshWorkerTimeout(str(exc)) from exc` and raised; the wrapped `MeshWorkerTimeout` propagates out of `_generate_via_comfy_worker` to `FailureModeMap.resolve(...)`; per `failure_mode_map.py:142-145` (MeshWorkerTimeout matched BEFORE generic WorkerTimeout) it is mapped to `FailureMode.mesh_worker_timeout` mode → `Decision.abort_or_fallback` (per `failure_mode_map.py:83-87` — same terminal behavior as remote Hunyuan3D mesh failures by design; the "standard retry" semantics for local mesh is owned by `_generate_via_comfy_worker` internal loop, NOT by FailureModeMap routing); `BudgetTracker.estimate_mesh_call_cost_usd(route_pricing=None)` records `cost_usd=0.0` so internal retries do not accumulate spend; `metrics["cost_usd"]=0.0` is emitted; the executor then surfaces the failure to the orchestrator transition engine which honours `Decision.abort_or_fallback` per existing `on_fallback` semantics

#### Scenario: Remote Hunyuan3D mesh continues to refuse silent retry per ADR-007 (per_task_usd > 0)

- **GIVEN** a `HunyuanTokenhubMeshWorker` (constructor-injected; `route.pricing.per_task_usd: 0.25`, so `per_task_usd > 0` evaluates to True) whose request times out
- **WHEN** the failure is raised
- **THEN** `GenerateMeshExecutor` continues to enforce `attempts=1` for the remote path (no transient retry wrapping in `mesh_worker._apost`); the CLI surfaces `job_id` so the user can run `probe_hunyuan_3d_query` before deciding `--resume`; this change does NOT modify ADR-007 enforcement for remote mesh; the `(route_pricing or {}).get("per_task_usd", 0) > 0` boundary check correctly identifies the route as premium

### Requirement: ComfyAgentWorker exceptions wrapped to MeshWorker exceptions in _generate_via_comfy_worker

The system SHALL wrap `ComfyAgentWorker` exception classes (`WorkerTimeout` / `WorkerError` / `WorkerUnsupportedResponse`, defined at `comfy_worker.py:57-65` as a hierarchy independent from `MeshWorker*` exceptions) into `MeshWorker*` exception classes (`MeshWorkerTimeout` / `MeshWorkerError` / `MeshWorkerUnsupportedResponse`, defined at `mesh_worker.py:30-61`) inside `_generate_via_comfy_worker` BEFORE the exceptions propagate out of the comfy-mesh dispatch branch (R2-F2 codex finding accepted-codex 2026-05-03: the two exception hierarchies do not intersect, so the existing `GenerateMeshExecutor` retry loop `except (MeshWorkerTimeout, MeshWorkerError)` at `generate_mesh.py:95` cannot catch ComfyWorker exceptions; without wrapping, `FailureModeMap` would also see an unfamiliar exception class and route incorrectly).

The wrapping rules SHALL be:

| ComfyWorker exception | MeshWorker exception (wrapped) | Behavior in _generate_via_comfy_worker internal retry loop |
|---|---|---|
| `WorkerTimeout` (subclass of `WorkerError`) | `MeshWorkerTimeout(str(exc)) from exc` | retried per `policy.max_attempts` + `_should_retry(policy, wrapped)` (standard local-mesh retry budget) |
| `WorkerUnsupportedResponse` (subclass of `WorkerError`) | `MeshWorkerUnsupportedResponse(str(exc)) from exc` | NOT retried (raised immediately; matches existing `_should_retry` default for unsupported responses) |
| Other `WorkerError` (base class catch) | `MeshWorkerError(str(exc)) from exc` | NOT retried (raised immediately; matches existing `_should_retry` default for generic worker errors) |

The wrap SHALL preserve the original ComfyWorker exception via `from exc` for diagnostic stack-trace integrity. The wrapped exception is what propagates to `FailureModeMap.resolve(...)` in the orchestrator failure path; downstream code (orchestrator / FailureModeMap / BudgetTracker) sees only `MeshWorker*` exceptions and behaves identically for local-comfy-mesh and remote-Hunyuan-mesh failures.

#### Scenario: ComfyAgentWorker WorkerTimeout wrapped to MeshWorkerTimeout for executor retry loop compatibility

- **GIVEN** a `_generate_via_comfy_worker` call where `worker.generate_mesh(...)` raises `WorkerTimeout("subprocess exceeded 600s")` on the first attempt; `policy.max_attempts == 2`
- **WHEN** `_generate_via_comfy_worker` catches the exception in its internal retry loop
- **THEN** the exception is wrapped as `MeshWorkerTimeout("subprocess exceeded 600s") from exc` (preserving the original ComfyWorker `WorkerTimeout` chain via `from exc`); the wrapped exception is passed to `_should_retry(policy, wrapped)` (existing helper in `generate_mesh.py:317-319` matches `MeshWorkerTimeout` by `isinstance` check); `_should_retry` returns True; `_backoff(policy, attempt=0)` is invoked; the retry loop continues to attempt 2

#### Scenario: ComfyAgentWorker WorkerUnsupportedResponse wrapped to MeshWorkerUnsupportedResponse and NOT retried

- **GIVEN** a `_generate_via_comfy_worker` call where `worker.generate_mesh(...)` raises `WorkerUnsupportedResponse("rejected outputs.audio in mesh-mode")` on the first attempt; `policy.max_attempts == 2`
- **WHEN** `_generate_via_comfy_worker` catches the exception
- **THEN** the exception is wrapped as `MeshWorkerUnsupportedResponse("rejected outputs.audio in mesh-mode") from exc`; the wrapped exception is RAISED immediately (NOT passed through the retry loop because `_should_retry` semantics for `*UnsupportedResponse` is False per FR-RUNTIME-012); `worker.generate_mesh` is called exactly 1 time; `FailureModeMap` resolves the wrapped `MeshWorkerUnsupportedResponse` to `unsupported_response` → `Decision.abort_or_fallback` (consistent with remote-mesh `MeshWorkerUnsupportedResponse` handling)

#### Scenario: Local comfy mesh executor calls worker generate_mesh max_attempts times on transient timeout (succeed on 2nd attempt)

- **GIVEN** a `GenerateMeshExecutor` with route `comfy/local-mesh` (pricing None, non-premium); `ctx.step.retry_policy.max_attempts == 2`; mocked `ComfyAgentWorker.generate_mesh` raises `WorkerTimeout` on the first call and returns `[MeshCandidate(...)]` on the second call
- **WHEN** `GenerateMeshExecutor.execute(ctx)` runs
- **THEN** `worker.generate_mesh` is invoked exactly **2 times** (R2-F2 修订关键 fence:本地走 standard retry,不被 executor 主流程 `attempts=1` 强制阻断;`_generate_via_comfy_worker` 自带 retry loop;wrapping happens in the except clause but is NOT raised because attempt-1 wraps to `MeshWorkerTimeout`,attempt-2 succeeds before any raise);after the second successful call, `MeshCandidate` is persisted via `repo.put`; the executor returns `ExecutorResult` normally; no exception propagates to FailureModeMap

#### Scenario: Local comfy mesh executor calls worker max_attempts times on persistent timeout, then wrapped MeshWorkerTimeout reaches FailureModeMap (R3-F1 修订)

- **GIVEN** a `GenerateMeshExecutor` with route `comfy/local-mesh` (pricing None, non-premium); `ctx.step.retry_policy.max_attempts == 2`; mocked `ComfyAgentWorker.generate_mesh` raises `WorkerTimeout("subprocess exceeded")` on **both** calls
- **WHEN** `GenerateMeshExecutor.execute(ctx)` runs
- **THEN** `worker.generate_mesh` is invoked exactly **2 times** (`policy.max_attempts`); after the second failure the `WorkerTimeout` is wrapped to `MeshWorkerTimeout from exc` and raised out of `_generate_via_comfy_worker`; FailureModeMap routes the wrapped `MeshWorkerTimeout` to `FailureMode.mesh_worker_timeout` → `Decision.abort_or_fallback` (consistent with remote Hunyuan3D mesh terminal behavior; the "local standard retry" semantics is owned by the internal loop and finished before this point — the FailureModeMap routing represents "all local retries exhausted, no further executor-level retry")

#### Scenario: Remote hunyuan mesh executor still calls worker generate exactly one time on timeout per ADR-007

- **GIVEN** a `GenerateMeshExecutor` with route `hunyuan/hy-3d-3.1` (pricing `per_task_usd: 0.25`, premium); `ctx.step.retry_policy.max_attempts == 2`; mocked `HunyuanTokenhubMeshWorker.generate` raises `MeshWorkerTimeout` on the first call
- **WHEN** `GenerateMeshExecutor.execute(ctx)` runs
- **THEN** `_should_use_comfy_worker_path(ctx)` returns False; the executor takes the original constructor-injected worker path; `attempts=1` strict cap applies (`generate_mesh.py:80-81` unchanged); `worker.generate` is invoked exactly **1 time**; the `MeshWorkerTimeout` propagates out per ADR-007 strict no-silent-retry; CLI surfaces `job_id` for `probe_hunyuan_3d_query` workflow

#### Scenario: BudgetTracker records zero cost for local ComfyUI mesh route

- **GIVEN** a `_generate_via_comfy_worker` call producing 2 `MeshCandidate`s; the route is `ResolvedRoute(model="comfy/local-mesh", ..., pricing=None)`
- **WHEN** the executor reaches `cost_usd = estimate_mesh_call_cost_usd(model=..., num_candidates=2, route_pricing=route_pricing)` (existing call at `generate_mesh.py:171-175`) with `route_pricing=None`
- **THEN** `cost_usd` equals `0.0` (because `(None or {}).get("per_task_usd")` returns None, which `estimate_mesh_call_cost_usd` treats as `fallback_per_task_usd=0.0` per `budget_tracker.py:230-232`); `BudgetTracker` accumulates 0.0 for this step; `metrics["cost_usd"]=0.0` is emitted to the WS event and the FR-COST interface is preserved

## MODIFIED Requirements

### Requirement: ComfyUI worker invokes the agent CLI via subprocess

The system SHALL invoke ComfyUI through `python -m comfyui_api run` as a subprocess and parse the stdout JSON envelope, replacing direct `/prompt` + `/history` + `/view` HTTP calls. The worker class `ComfyAgentWorker` SHALL accept the following constructor parameters (keyword-only):

- `scripts_dir: Path` — REQUIRED, from `FORGEUE_COMFY_SCRIPTS_DIR`
- `model_id: str` — REQUIRED (NEW for `comfy-agent-cli-mesh-audio-video-adoption`), used to infer `_capability` via `_CAPABILITY_BY_MODEL_ID` table; unknown id raises `WorkerUnsupportedResponse` per the Requirement "ComfyAgentWorker dispatches by capability inferred from model id" above
- `run_id: str` — REQUIRED, from `ctx.run.run_id`
- `project_id: str` — REQUIRED, from `ctx.task.project_id` (raises `WorkerUnsupportedResponse` if None or empty)
- `artifacts_dir: Path` — REQUIRED, from `ctx.run_dir` (raises `WorkerUnsupportedResponse` if None or not a directory)
- `python_exe: Path | None = None` — OPTIONAL, defaults to `sys.executable` if None
- `default_lifecycle: str = "none"` — OPTIONAL, MUST be `"none"` in this change scope (constraint inherited from `comfy-agent-cli-adoption` D6); other values raise `WorkerUnsupportedResponse`

The `model_id` parameter is the ONLY signature extension introduced by `comfy-agent-cli-mesh-audio-video-adoption`; all other parameters and their semantics inherit from `comfy-agent-cli-adoption` unchanged.

Each call SHALL pass `--workflow <manifest_name>` + `--params <json>` + `--project <task.project_id>` + `--lifecycle none` + `--timeout <s>`, and parse the resulting JSON whose `outputs.<key>` field carries absolute paths per the resolved capability (`outputs.images` for image-mode, `outputs.glb` for mesh-mode). The worker MUST NOT speak ComfyUI HTTP directly. The image-mode entry point is the existing ABC method `ComfyWorker.generate(spec, num_candidates, seed, timeout_s) -> list[ImageCandidate]`; the mesh-mode entry point is the new public method `ComfyAgentWorker.generate_mesh(spec, source_image_path, num_candidates, seed, timeout_s) -> list[MeshCandidate]` (NOT part of `ComfyWorker` ABC, since the ABC return type is `list[ImageCandidate]`; mesh-mode has its own dispatch via `GenerateMeshExecutor._generate_via_comfy_worker` per design D7). Both methods share a private helper `_run_subprocess_and_validate(spec, timeout_s) -> dict` that runs the subprocess, parses stdout JSON, and invokes capability-aware `_validate_outputs(outputs)`.

#### Scenario: ComfyAgentWorker (image) reads env config and calls comfyui_api with task.project_id

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`, `FORGEUE_COMFY_PYTHON_EXE` unset, `FORGEUE_COMFY_LIFECYCLE` unset; resolved route `ResolvedRoute(model="comfy/local", ...)`; `ctx.run.run_id="run_abc"`; `ctx.task.project_id="proj_comfy_smoke"`; `ctx.run_dir=Path("artifacts/2026-05-02/run_abc")`
- **WHEN** `GenerateImageExecutor._generate_via_worker` constructs `worker = ComfyAgentWorker(scripts_dir=..., model_id="comfy/local", run_id=..., project_id=..., artifacts_dir=..., default_lifecycle="none")` and calls the SYNC ABC method `worker.generate(spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {...}, "comfy_lifecycle": "none"}, num_candidates=1, seed=42, timeout_s=300)`
- **THEN** the worker's `_capability == "image"`; the worker spawns subprocess with argv `[sys.executable, "-m", "comfyui_api", "run", "--workflow", "GameAssets/01b_singleview_sdxl", "--params", '{...}', "--project", "proj_comfy_smoke", "--lifecycle", "none", "--timeout", "300"]`; `_validate_outputs` accepts `outputs.images` non-empty and rejects `outputs.glb / audio / video` per the capability-aware Requirement; the worker reads PNG bytes from `outputs.images` paths, copies them to `artifacts_dir/comfy/`, and returns `list[ImageCandidate]` per the image-change contract

#### Scenario: ComfyAgentWorker (mesh) calls generate_mesh with source_image_path injected

- **GIVEN** environment variables as above; resolved route `ResolvedRoute(model="comfy/local-mesh", ..., pricing=None)`; an upstream image step has produced source bytes resolved via `_resolve_source_image(ctx)` and written to `<ctx.run_dir>/comfy/input/abc123def456.png` by `_generate_via_comfy_worker`
- **WHEN** `GenerateMeshExecutor._generate_via_comfy_worker` constructs `worker = ComfyAgentWorker(scripts_dir=..., model_id="comfy/local-mesh", run_id=..., project_id=..., artifacts_dir=..., default_lifecycle="none")` and calls `worker.generate_mesh(spec={"comfy_workflow": "Mesh/02_mini_textured_3d_hunyuan", "comfy_params": {"seed": 42}, "comfy_image_param_key": "image_path", "comfy_lifecycle": "none"}, source_image_path=Path("<ctx.run_dir>/comfy/input/abc123def456.png"), num_candidates=1, seed=42, timeout_s=600)`
- **THEN** the worker's `_capability == "mesh"`; the worker constructs enriched params `{"seed": 42, "image_path": "<ctx.run_dir>/comfy/input/abc123def456.png"}` (without mutating caller's `spec["comfy_params"]`); the worker spawns subprocess with argv `[..., "--workflow", "Mesh/02_mini_textured_3d_hunyuan", "--params", '{"seed":42,"image_path":"..."}', ...]`; `_validate_outputs` accepts `outputs.glb` non-empty, tolerates `outputs.images` (auxiliary preview, not consumed), rejects `outputs.audio / video`; the worker reads GLB bytes from `outputs.glb` paths and returns `list[MeshCandidate(data=..., format="glb", metadata={...comfy provenance...})]` per the artifact-contract spec

### Requirement: Non-OpenAI protocols ship dedicated adapters

The system SHALL route non-OpenAI protocols via one of three patterns under `src/framework/providers/`:

- (a) `CapabilityRouter` adapter chain with `model.startswith(...)` prefix matching — used by `qwen/`, `hunyuan/` image (DashScope, Hunyuan tokenhub image)
- (b) **Worker injected at executor construction time** — used by remote mesh: `framework.run` selects `HunyuanTokenhubMeshWorker` (or future remote mesh worker) based on env / API keys and **injects** the instance into `GenerateMeshExecutor` (see `generate_mesh.py:194` "Mesh workers are injected directly into `GenerateMeshExecutor`"); `CapabilityRouter` is NOT involved
- (c) **Executor-side model-id exact-match branch** — used by ComfyUI agent CLI subprocess: `GenerateImageExecutor` checks `prepared_routes` for `model == "comfy/local"` (image), and `GenerateMeshExecutor` checks for `model == "comfy/local-mesh"` (mesh, NEW for `comfy-agent-cli-mesh-audio-video-adoption`); both executors construct `ComfyAgentWorker` inline from env config + `StepContext`; `CapabilityRouter` is NOT involved. Future audio / video capabilities (out of scope of this change, see follow-on changes `comfy-agent-cli-audio-adoption` / `comfy-agent-cli-video-adoption`) will extend pattern (c) to `GenerateAudioExecutor` / `GenerateVideoExecutor`

Each non-OpenAI protocol family SHALL ship its own adapter / worker module: DashScope (`qwen_multimodal_adapter.py`), Hunyuan tokenhub image (`hunyuan_tokenhub_adapter.py`), Hunyuan 3D mesh (`providers/workers/mesh_worker.py`, dispatched via pattern (b)), and ComfyUI agent CLI (`providers/workers/comfy_worker.py::ComfyAgentWorker` — single class, capability-aware dispatch driven by resolved model id, currently supporting image + mesh; image-mode dispatched via pattern (c) on `GenerateImageExecutor`, mesh-mode dispatched via pattern (c) on `GenerateMeshExecutor`).

#### Scenario: qwen/ and hunyuan/ prefixes route to their dedicated adapters via supports() prefix match (pattern a)

- GIVEN `CapabilityRouter` with `QwenMultimodalAdapter` and `HunyuanImageAdapter` registered ahead of the wildcard `LiteLLMAdapter`
- WHEN a request targets a model whose id begins with `qwen/` or `hunyuan/`
- THEN routing reaches the matching dedicated adapter first because `QwenMultimodalAdapter.supports(model)` returns `model.startswith("qwen/")` and `HunyuanImageAdapter.supports(model)` returns `model.startswith("hunyuan/")`; the call therefore bypasses LiteLLM's OpenAI-compatible chat path

#### Scenario: Remote Hunyuan3D mesh worker is injected into GenerateMeshExecutor by framework.run, not dispatched by model id (pattern b)

- GIVEN `framework.run.main` builds an Orchestrator and detects remote mesh capability needs based on env vars + bundle declarations
- WHEN it constructs `GenerateMeshExecutor`
- THEN it passes a concrete `HunyuanTokenhubMeshWorker` instance (or a `FakeMeshWorker` for offline tests) directly into the executor's constructor; the executor stores the worker as an attribute; this change does NOT modify the remote mesh dispatch pattern; ADR-007 strict no-silent-retry continues to apply for the remote path per the `pricing.per_task_usd > 0` boundary

#### Scenario: comfy/local routes to ComfyAgentWorker (image) via executor-side model-id branch (pattern c, image)

- GIVEN a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local", ...)`
- WHEN `GenerateImageExecutor._should_use_worker_path(ctx)` returns True
- THEN the executor takes the comfy-worker dispatch branch and constructs `ComfyAgentWorker(model_id="comfy/local", ...)` inline; `_capability="image"` is inferred; output validation expects `outputs.images` non-empty and rejects `outputs.glb / audio / video`

#### Scenario: comfy/local-mesh routes to ComfyAgentWorker (mesh) via executor-side model-id branch (pattern c, mesh, NEW for this change)

- GIVEN a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local-mesh", ...)`; an upstream image step provides source bytes via the `_resolve_source_image(ctx)` chain
- WHEN `GenerateMeshExecutor._should_use_comfy_worker_path(ctx)` returns True
- THEN the executor takes the comfy-worker dispatch branch (NOT the constructor-injected `HunyuanTokenhubMeshWorker` path) and calls `_generate_via_comfy_worker(...)` which writes source bytes to `<ctx.run_dir>/comfy/input/<sha1>.png`, constructs `ComfyAgentWorker(model_id="comfy/local-mesh", ...)` inline, and invokes `worker.generate_mesh(spec=..., source_image_path=...)`; `_capability="mesh"` is inferred; output validation requires `outputs.glb` non-empty, tolerates `outputs.images`, rejects `outputs.audio / video`; returned `MeshCandidate`s carry comfy provenance in `metadata={...}` and are persisted via the existing `repo.put` loop with `metadata={"worker_metadata": dict(cand.metadata), ...}`
