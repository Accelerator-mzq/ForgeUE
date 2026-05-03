# provider-routing

## Purpose

Provider-routing hides the heterogeneity of every external model and worker behind a four-method `ProviderAdapter` interface plus a capability-alias registry. Workflows refer to aliases (`text_cheap`, `review_judge_visual`, `mesh_from_image`, etc.); the registry expands each alias into a `PreparedRoute`, the router selects an adapter by `supports(model)` in registration order, and BudgetTracker reads the route's pricing block. Adding a cheap OpenAI-compatible endpoint is a pure YAML edit — no code — while non-OpenAI protocols bolt on as dedicated adapters under `src/framework/providers/`.

## Source Documents

- `docs/requirements/SRS.md` §3.3 (FR-MODEL-001~008), §3.8 (FR-WORKER-001~010), §3.10 (FR-COST-001~009), §5.3 provider interface table, §4.8 ADR-002 / ADR-003 / ADR-004 / ADR-007
- `docs/design/HLD.md` §3 subsystems (providers, workers)
- `docs/api_des/GLM-Image.md`, `GLM-4.6V.md`, `QWEN-Image.md`, `QWEN-Image-Edit.md`, `HunYuan.md` (external API contracts)
- `config/models.yaml` (providers / models / aliases — the single source of truth)
- `CHANGELOG.md` [Unreleased] TBD-007 (mesh retry collapse, ADR-007) and [0.1.0] provider integrations
- Source: `src/framework/providers/base.py`, `capability_router.py`, `model_registry.py`
- Source: `src/framework/providers/litellm_adapter.py` (wildcard, registered last), `qwen_multimodal_adapter.py`, `hunyuan_tokenhub_adapter.py`, `fake_adapter.py`
- Source: `src/framework/providers/_retry.py`, `_retry_async.py`, `_download_async.py`
- Source: `src/framework/providers/workers/comfy_worker.py`, `mesh_worker.py`
- Source: `src/framework/pricing_probe/` (dry-run + --apply)
- Source: `src/framework/run.py:62-73` (adapter registration order)

## Current Behavior

`ModelRegistry` parses `config/models.yaml` in three sections: `providers` (endpoint + auth env var), `models` (`id`, `provider`, `kind`, optional `pricing` + `pricing_autogen` audit block), and `aliases` (scenario-named lists of `preferred` / `fallback` model names). Bundles declare `provider_policy.models_ref: "<alias>"`, and the workflow loader expands it into `prepared_routes` — each route is a tuple of `(model_id, api_key_env, api_base, kind)`. At runtime, `CapabilityRouter` walks the registered adapters in order, calling `supports(model)` until one claims the model; `LiteLLMAdapter` is a wildcard (`supports(*) == True`) and must be registered LAST so the prefixed adapters (`qwen/`, `hunyuan/`) are given first chance.

Adapters ship for four protocol families: LiteLLM (OpenAI-compatible + Anthropic via proxies such as PackyCode / MiniMax), DashScope (`qwen_multimodal_adapter.py`), Hunyuan tokenhub (image via `hunyuan_tokenhub_adapter.py`, 3D via `providers/workers/mesh_worker.py`), and ComfyUI agent CLI subprocess (`providers/workers/comfy_worker.py::ComfyAgentWorker`, invoking `python -m comfyui_api` per OpenSpec change `2026-05-02-comfy-agent-cli-adoption`; superseded the prior HTTP `/prompt` + `/history` + `/view` adapter). A Tripo3D scaffold exists in `mesh_worker.py` but its pricing parser is guarded by `NotImplementedError` until an authoritative per-task price is published. Mesh-worker downloads rank URLs (`strong` > `ok` > `key` > `other` > `zip`), iterate the fallthrough loop, and validate via magic bytes (`glb` must start with `b"glTF"`); `data:` URI detection is case-insensitive (RFC 2397).

Pricing flows in two directions. The `pricing_probe` CLI (`httpx` for static pages + `playwright` for JS SPAs) refreshes `pricing_autogen.status=fresh` entries but NEVER overwrites a `status=manual` entry. At request time, the chosen route's pricing block is stashed in `ProviderResult.raw["_route_pricing"]` (no tuple-signature break) so every paid executor can feed the right unit cost into `BudgetTracker`. For mesh generation specifically (ADR-007), ForgeUE refuses to silently retry: `GenerateMeshExecutor` forces `attempts=1`, `mesh_worker._apost` is NOT wrapped in transient retry, and the CLI surfaces `job_id` on failure so the user can run the `probe_hunyuan_3d_query` opt-in probe before deciding to `--resume`.
## Requirements
### Requirement: Three-section ModelRegistry is the single source

The system SHALL treat `config/models.yaml` (sections: `providers`, `models`, `aliases`) as the sole source of truth for provider endpoints, model ids, and capability aliases (ADR-002).

#### Scenario: ModelRegistry parses config/models.yaml into providers + models + aliases sections

- GIVEN a `config/models.yaml` file laid out as documented in `src/framework/providers/model_registry.py` module docstring (top-level keys `providers:` / `models:` / `aliases:` only, with cross-section references `model.provider → providers[*]` and `alias.preferred|fallback → models[*]`)
- WHEN `ModelRegistry.from_yaml(path)` parses the file
- THEN the registry exposes the three named sections separately (provider endpoints + auth env vars, model defs with `id` / `provider` / `kind`, alias lists), cross-section references are validated at load time so unknown `model.provider` raises `RegistryReferenceError` and unknown `alias.preferred|fallback` items raise the same, and `tests/unit/test_model_registry.py::test_from_yaml_parses_three_sections` plus `::test_unknown_provider_reference_rejected` / `::test_unknown_model_reference_rejected` enforce this contract

### Requirement: Alias reference expansion in the loader

The system SHALL expand every bundle's `provider_policy.models_ref: "<alias>"` into `prepared_routes` before Pydantic validation; each route contains `model_id`, `api_key_env`, `api_base`, `kind`.

#### Scenario: Loader expands provider_policy.models_ref into prepared_routes before Pydantic validation

- GIVEN a bundle whose Step declares `provider_policy.models_ref: "<alias>"` and no inline `prepared_routes`
- WHEN `framework.workflows.loader.load_task_bundle(path)` runs `expand_model_refs(raw, get_model_registry())` on the parsed dict before any `Step.model_validate` call
- THEN the loader replaces `models_ref` in-place with concrete `prepared_routes`, each carrying its own `(model_id, api_key_env, api_base, kind)` tuple drawn from the alias's preferred-then-fallback model list — so one alias can mix multiple providers (e.g. preferred = MiniMax proxy, fallback = direct Anthropic) without cross-talk; `tests/unit/test_model_registry.py::test_expand_produces_prepared_routes_with_per_route_auth` and `::test_expand_unknown_ref_raises` fence this contract

### Requirement: OpenAI-compatible endpoints add zero code

The system SHALL let an operator add a new OpenAI-compatible provider by editing only `config/models.yaml` (providers block + models block), with the bundle writing `openai/<id>` and no new adapter code.

#### Scenario: New OpenAI-compatible vendor is added by editing config/models.yaml without writing adapter code

- GIVEN a new OpenAI-compatible vendor (such as the existing `zhipu_openai_compat` / `dashscope_openai_compat` / `tencent_hunyuan_openai_compat` providers in `config/models.yaml`) for which only an HTTPS endpoint URL and an API-key env var name are known
- WHEN an operator adds a new entry under `providers:` with `api_base` + `api_key_env`, registers one or more entries under `models:` whose `id` is `openai/<vendor-id>`, and (optionally) plugs them into an alias list under `aliases:` — without touching any file under `src/framework/providers/`
- THEN the request flows through `LiteLLMAdapter` because `LiteLLMAdapter.supports(model)` is permissive (`supports(*) → True`, registered LAST in the adapter chain); no specialised adapter file needs to be created, and the only required edits are to the YAML registry

### Requirement: Non-OpenAI protocols ship dedicated adapters

The system SHALL route non-OpenAI protocols via one of three patterns under `src/framework/providers/`:

- (a) `CapabilityRouter` adapter chain with `model.startswith(...)` prefix matching — used by `qwen/`, `hunyuan/` image (DashScope, Hunyuan tokenhub image)
- (b) **Worker injected at executor construction time** — used by mesh: `framework.run` selects `HunyuanTokenhubMeshWorker` (or future mesh worker) based on env/API keys and **injects** the instance into `GenerateMeshExecutor` (see `generate_mesh.py:194` "Mesh workers are injected directly into `GenerateMeshExecutor`"; `generate_mesh.py:167` reads `prepared_routes` only for pricing — NOT for dispatch). `CapabilityRouter` is NOT involved.
- (c) **Executor-side model-id exact-match branch** — NEW pattern introduced by this change for ComfyUI: `GenerateImageExecutor` checks `prepared_routes` for `model == "comfy/local"` and constructs `ComfyAgentWorker` inline from env config + `StepContext`. `CapabilityRouter` is NOT involved.

Each non-OpenAI protocol family SHALL ship its own adapter / worker module: DashScope (`qwen_multimodal_adapter.py`), Hunyuan tokenhub image (`hunyuan_tokenhub_adapter.py`), Hunyuan 3D mesh (`providers/workers/mesh_worker.py`, dispatched via pattern (b)), and ComfyUI agent CLI (`providers/workers/comfy_worker.py::ComfyAgentWorker` invoking the agent CLI as a subprocess, dispatched via pattern (c); supersedes the previous ComfyUI HTTP adapter).

#### Scenario: qwen/ and hunyuan/ prefixes route to their dedicated adapters via supports() prefix match (pattern a)

- GIVEN `CapabilityRouter` with `QwenMultimodalAdapter` and `HunyuanImageAdapter` registered ahead of the wildcard `LiteLLMAdapter`
- WHEN a request targets a model whose id begins with `qwen/` or `hunyuan/`
- THEN routing reaches the matching dedicated adapter first because `QwenMultimodalAdapter.supports(model)` returns `model.startswith("qwen/")` (`src/framework/providers/qwen_multimodal_adapter.py`) and `HunyuanImageAdapter.supports(model)` returns `model.startswith("hunyuan/")` (`src/framework/providers/hunyuan_tokenhub_adapter.py`); the call therefore bypasses LiteLLM's OpenAI-compatible chat path and uses the protocol-specific submit / poll / download flow built into the dedicated adapter

#### Scenario: Mesh worker is injected into GenerateMeshExecutor by framework.run, not dispatched by model id (pattern b)

- GIVEN `framework.run.main` builds an Orchestrator and detects mesh capability needs based on env vars + bundle declarations
- WHEN it constructs `GenerateMeshExecutor`
- THEN it passes a concrete `HunyuanTokenhubMeshWorker` instance (or a `FakeMeshWorker` for offline tests) directly into the executor's constructor; the executor stores the worker as an attribute and uses it without consulting `prepared_routes` for dispatch (`generate_mesh.py:194` "Mesh workers are injected directly into `GenerateMeshExecutor`"); `CapabilityRouter.mesh_generation` is NOT in the dispatch path; this change does NOT modify the mesh dispatch pattern

#### Scenario: comfy/local routes to ComfyAgentWorker via executor-side model-id branch (pattern c, NEW for this change)

- GIVEN a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local", ...)` and `GenerateImageExecutor` extended (per the new `GenerateImageExecutor dispatches comfy/local to ComfyAgentWorker without going through router` Requirement) with a `_should_use_worker_path` + `_generate_via_worker` branch
- WHEN the executor's `execute(ctx)` runs and `_should_use_worker_path(ctx)` returns True (any prepared_route has `model == "comfy/local"`)
- THEN the executor takes the worker dispatch branch and constructs `ComfyAgentWorker` inline from environment config (`FORGEUE_COMFY_*`) + `ctx.run_dir` + `ctx.task.project_id` + `ctx.run.run_id` (keyword-only signature per H3 fix); it calls the SYNC ABC method `worker.generate(spec=..., num_candidates=..., seed=..., timeout_s=...)` directly returning `list[ImageCandidate]` (G11 R4 writeback: NO `asyncio.run` bridge, NO async helper — `ComfyWorker` ABC `generate` is sync, see `generate_image.py:286`); `CapabilityRouter.image_generation` is NOT called for this step; LiteLLM's wildcard never sees `comfy/local`. This is a NEW dispatch pattern for ForgeUE — distinct from mesh's pattern (b) which uses constructor injection

### Requirement: Wildcard adapter is registered last

The system SHALL register `LiteLLMAdapter` (wildcard) LAST in the adapter chain so that prefixed adapters (`qwen/`, `hunyuan/`) claim their models first (ADR-003).

#### Scenario: Qwen model routed to the DashScope adapter

- GIVEN a registry where `QwenMultimodalAdapter` precedes `LiteLLMAdapter`
- WHEN a request targets `qwen/qwen-image-2.0`
- THEN `QwenMultimodalAdapter.supports(model)` returns True first and the request goes through DashScope, not LiteLLM

### Requirement: Capability aliases drive provider selection

The system SHALL expose the current capability alias set (`text_cheap`, `text_strong`, `review_judge`, `review_judge_visual`, `ue5_api_assist`, `image_fast`, `image_strong`, `image_edit`, `mesh_from_image`); bundles SHALL refer to aliases, not raw model ids, unless a bundle explicitly overrides via `preferred_models` / `fallback_models`.

#### Scenario: Registered aliases cover the documented capability surface and resolve through ModelRegistry

- GIVEN the capability axes the framework supports today — text generation, structured / report review, vision review, UE5 API assist, image generation, image edit, image-to-3D mesh
- WHEN the alias section of `config/models.yaml` is loaded through `ModelRegistry`
- THEN every documented capability axis has at least one matching alias (current witnesses: `text_cheap` / `text_strong` for text, `review_judge` / `review_judge_visual` for report and vision review, `ue5_api_assist` for UE5 API queries, `image_fast` / `image_strong` for image generation, `image_edit` for image edits, `mesh_from_image` for 3D), each alias resolves to `kind`-tagged routes through the registry, and the cross-cutting properties of named-witness aliases are enforced by `tests/unit/test_model_registry.py::test_review_judge_visual_alias_is_vision_kind` / `::test_image_edit_alias_carries_image_edit_kind` / `::test_mesh_from_image_alias_is_cross_provider`; the alias set MAY grow over time, so the Scenario asserts capability coverage rather than a frozen alias-name list

### Requirement: Route pricing is stashed on every ProviderResult

The system SHALL place the chosen route's pricing block into `ProviderResult.raw["_route_pricing"]`; the public tuple signature MUST NOT break.

#### Scenario: ProviderResult.raw carries _route_pricing for priced routes and stays clean for unpriced routes

- GIVEN a `CapabilityRouter` request resolving against a `PreparedRoute` whose registry entry MAY or MAY NOT carry a `pricing:` block
- WHEN the router invokes `acompletion` / `astructured` / `aimage_generation` / `aimage_edit` and returns a `ProviderResult`
- THEN, when the chosen route IS priced, `ProviderResult.raw["_route_pricing"]` carries that route's pricing block on every result (including each candidate of a multi-image generation), so paid executors can feed the right unit cost into `BudgetTracker`; when the chosen route is NOT priced, `ProviderResult.raw` stays free of a `_route_pricing` key — and the public tuple signature of the router methods does NOT change. `tests/unit/test_router_pricing_stash.py::test_router_acompletion_stashes_pricing_into_raw` / `::test_router_acompletion_no_pricing_when_route_unpriced` / `::test_router_aimage_generation_stashes_pricing_on_every_result` / `::test_router_aimage_generation_unpriced_route_leaves_raw_clean` fence both sides

### Requirement: Pricing probe defaults to dry-run

The system SHALL default the pricing probe to dry-run; `--apply` is required to mutate `config/models.yaml`; entries with `pricing_autogen.status=manual` MUST NOT be overwritten.

#### Scenario: pricing_probe without --apply leaves config/models.yaml on disk unchanged and prints a DRY-RUN banner

- GIVEN `python -m framework.pricing_probe` invoked without the `--apply` flag against a `config/models.yaml` whose contents are captured as `before`
- WHEN the probe completes
- THEN the file's bytes on disk equal `before` (no mutation), the CLI prints a `=== pricing_probe DRY-RUN ===` banner followed by the proposed diff text, and stdout closes with `(dry-run -- no file changes. Re-run with --apply to write.)` per `src/framework/pricing_probe/cli.py`; `tests/unit/test_pricing_probe_framework.py::test_yaml_writer_dry_run_never_writes` fences this invariant by asserting `before == after` after a `dry_run=True` call

#### Scenario: pricing_probe --apply writes config/models.yaml while preserving manual pricing entries

- GIVEN a `config/models.yaml` containing a mix of models with `pricing_autogen.status: fresh` (subject to refresh) and `pricing_autogen.status: manual` (operator-curated, e.g. contract pricing different from public list price)
- WHEN `python -m framework.pricing_probe --apply` runs and the parser produces fresh proposals for both kinds of entries
- THEN `apply_results_to_yaml(... dry_run=False)` mutates the YAML file: for `fresh` / unset / `stale` entries the proposal updates the `pricing:` block in place and stamps `pricing_autogen.sourced_on` / `source_url` / `cny_original`; for `pricing_autogen.status: manual` entries the writer logs `MANUAL: skipping` in the diff and leaves both `pricing:` and `pricing_autogen` untouched; ruamel.yaml round-tripping preserves comments and indentation. `tests/unit/test_pricing_probe_framework.py::test_yaml_writer_applies_fresh_proposal` / `::test_yaml_writer_skips_manual_pricing` / `::test_yaml_writer_preserves_comments` fence the three sides of this contract. The `demo_artifacts/<YYYY-MM-DD>/pricing/<HHMMSS>/` path mentioned in `CLAUDE.md` §产物路径约定 is a path-naming convention rather than an assertion target of this Scenario

### Requirement: External factual pricing requires a verifiable source

The system SHALL either carry a `pricing_autogen` block with `status`, `sourced_on`, `source_url`, and `cny_original` (when applicable) on every `pricing` entry, OR leave `pricing` null with a TODO comment (ADR-004).

#### Scenario: pricing_autogen subfield names and status enum are validated at registry parse time

- GIVEN a `config/models.yaml` whose `pricing_autogen` block on a model entry carries an unknown subfield (anything outside `status` / `sourced_on` / `source_url` / `cny_original`) or an out-of-enum `status` value (anything outside `fresh` / `stale` / `manual`)
- WHEN `ModelRegistry.from_yaml(path)` parses the file
- THEN the registry rejects the entry: `tests/unit/test_pricing_probe_framework.py::test_pricing_autogen_invalid_status_raises` fences the status-enum side and `::test_pricing_autogen_unknown_subfield_raises` fences the subfield-allowlist side; conversely `::test_pricing_autogen_valid_parses` confirms a well-formed audit block (with `status` / `sourced_on` / `source_url` / optional `cny_original`) passes, and `::test_pricing_autogen_missing_is_none` confirms that a model with `pricing: null` and no `pricing_autogen` block is also valid (the ADR-004 escape hatch for unknown future pricing)

### Requirement: URL-rank fallthrough for mesh worker

The system SHALL rank mesh-worker result URLs as `strong > ok > key > other > zip` and iterate the ranked list; `MeshWorkerUnsupportedResponse` continues to the next candidate; `MeshWorkerError` terminates.

#### Scenario: Mesh worker iterates ranked URL buckets in strong → ok → key → other → zip order

- GIVEN a Hunyuan-3D `/query` DONE response carrying multiple candidate URLs spanning more than one bucket
- WHEN `_rank_hunyuan_3d_urls(resp)` (`src/framework/providers/workers/mesh_worker.py`) classifies the URLs into the five named buckets `strong_hits` (`.glb` only) / `ok_hits` / `key_hits` / `other_hits` / `zip_hits`, and `_one(...)` iterates the concatenated ranked list
- THEN the worker tries URLs in `strong_hits` first, then `ok_hits`, then `key_hits`, then `other_hits`, then `zip_hits`; a `MeshWorkerUnsupportedResponse` from one URL falls through to the next ranked URL, while a generic `MeshWorkerError` (network / 5xx) is recorded as `last_download_error` and the loop continues — the final raise prefers `last_download_error` when any network failure occurred (a resubmit might yield fresh URLs) and only raises the deterministic `MeshWorkerUnsupportedResponse` when every URL was malformed; `tests/unit/test_cn_image_adapters.py` rank-helper tests fence the bucket order and the fallthrough invariant

### Requirement: Range-resume integrity

The system SHALL use `chunked_download_async()` with Range continuation; a resume response MUST be `206` with a `Content-Range` header whose start offset matches the expected offset.

#### Scenario: chunked_download_async resumes only when the server returns 206 with a matching Content-Range start offset

- GIVEN a partial download where the client has buffered `len(buf)` bytes and reissues the request with a `Range: bytes=<len(buf)>-` header
- WHEN the server responds
- THEN `src/framework/providers/_download_async.py` accepts the resume only if `resp.status_code == 206` AND `resp.headers["Content-Range"]` parses to a start offset equal to `len(buf)`; any other shape — a 200 full body, a 206 with a different / missing `Content-Range`, or no header — resets the buffer and refuses to splice partial bytes; `tests/unit/test_download_async.py::test_range_206_with_matching_offset_resumes` covers the happy path, `::test_range_206_with_wrong_offset_resets_buffer` and `::test_range_ignored_server_resets_buffer` cover the two reject paths, and the final hash check on the assembled bytes guarantees integrity end-to-end

### Requirement: Magic-bytes format gate

The system SHALL validate mesh format magic bytes — `fmt == "glb"` MUST have `data[:4] == b"glTF"`; mismatch raises `MeshWorkerUnsupportedResponse`. glTF external buffer payloads MUST raise (not fall back to `missing_materials=True`).

#### Scenario: GLB candidate whose first four bytes are not b"glTF" raises MeshWorkerUnsupportedResponse

- GIVEN a candidate URL declared by the provider as `.glb` whose downloaded payload's first four bytes do NOT equal `b"glTF"` (e.g. an `.obj` ASCII header, an HTML error page, or a ZIP signature)
- WHEN `_build_candidate(...)` (`src/framework/providers/workers/mesh_worker.py`) inspects the payload's magic bytes against the requested format
- THEN `_build_candidate` raises `MeshWorkerUnsupportedResponse` rather than wrapping the bytes into a `MeshCandidate`, so the fallthrough loop in `_one(...)` advances to the next ranked URL; a text-glTF payload that references external `.bin` buffers without inlining them also raises (the `geometry_only` escape applies to external textures only, never to external geometry buffers), preventing the worker from silently delivering a candidate UE would later reject on import

### Requirement: Case-insensitive data: URI

The system SHALL treat `data:` URI scheme detection as case-insensitive (RFC 2397).

#### Scenario: data: URI scheme detection treats DATA: / Data: / data: identically per RFC 2397

- GIVEN a glTF / OBJ payload whose embedded resources are tagged with the `data:` URI scheme written in mixed case (`DATA:image/png;base64,...`, `Data:image/png;base64,...`, or `data:image/png;base64,...`)
- WHEN the self-contained-payload detector runs (`src/framework/providers/workers/mesh_worker.py::_is_data_uri` at the helper layer, plus `_is_self_contained_obj` and `_is_self_contained_gltf` consumers) and applies `value.lstrip().lower().startswith("data:")`
- THEN every casing variant is treated identically — RFC 2397 defines URI schemes as case-insensitive, and the historical bug where a mixed-case `DATA:` was rejected as non-self-contained is fenced by `tests/unit/test_cn_image_adapters.py::test_data_uri_check_is_case_insensitive` plus the peer fence `tests/unit/test_pr3_cleanup_fences.py::test_is_http_url_case_insensitive` for the analogous `_is_http_url` helper

### Requirement: tokenhub poll timeout is clamped

The system SHALL clamp every tokenhub `/query` HTTP timeout to `min(<per_poll_cap>, max(1.0, budget_s - elapsed))`; when only 1 s of budget remains, a single poll MUST NOT block for 20-30 s.

#### Scenario: tokenhub /query single-poll timeout is clamped to min(per_poll_cap, max(1.0, budget_s − elapsed))

- GIVEN an `HunyuanMeshWorker._atokenhub_poll` loop with `budget_s` remaining; the per-poll ceiling is `30.0` seconds for the Hunyuan-3D `/query` call (`src/framework/providers/workers/mesh_worker.py`) and `20.0` seconds for the analogous Tripo3D path
- WHEN the loop computes `remaining = budget_s - elapsed` and the next poll's `timeout_s` argument
- THEN the timeout is set to `min(per_poll_cap, max(1.0, remaining))`, so a step with only 1 second of budget left issues a 1-second `/query` rather than a 20-30 second one — preventing one slow poll from blowing the orchestrator's nominal step budget; `tests/unit/test_codex_audit_fixes.py::test_mesh_poll_clamps_timeout_to_remaining_budget` and `::test_hunyuan_poll_clamps_timeout_to_remaining_budget` fence the clamp formula on the mesh and image paths respectively

### Requirement: HTML-body pollution wraps as unsupported

The system SHALL, on a 200 response whose body is not JSON, catch `ValueError` / `JSONDecodeError` and wrap it as `ProviderUnsupportedResponse` or `MeshWorkerUnsupportedResponse`; the raw JSON error MUST NOT escape the adapter.

#### Scenario: 200 response carrying HTML body is wrapped as unsupported, not surfaced as raw JSONDecodeError

- GIVEN an upstream tokenhub / DashScope / mesh endpoint that returns HTTP 200 but with an HTML body (e.g. `<html>nginx error</html>`, `<html>cdn block</html>`, `<html>proxy</html>`) instead of JSON — typically when a CDN edge intercepts the request
- WHEN the adapter calls `httpx`'s `resp.json()` and a `ValueError` / `json.JSONDecodeError` is raised
- THEN the adapter catches it and re-raises as `ProviderUnsupportedResponse` (`HunyuanImageAdapter`, `QwenMultimodalAdapter`) or `MeshWorkerUnsupportedResponse` (`HunyuanMeshWorker._apost`); the raw `JSONDecodeError` does NOT escape the adapter boundary, so `FailureModeMap` can route the failure to `abort_or_fallback` rather than treating it as a transient retryable error. `tests/unit/test_codex_audit_fixes.py::test_hunyuan_tokenhub_post_raises_unsupported_on_html_body` / `::test_qwen_dashscope_post_raises_unsupported_on_html_body` / `::test_mesh_worker_apost_raises_unsupported_on_html_body` fence each adapter

### Requirement: Premium-API single-attempt guard

The system SHALL forbid framework-level silent retry for `mesh.generation` (ADR-007). On failure, the CLI MUST surface `job_id` on stderr and point the user at `probes.provider.probe_hunyuan_3d_query --job-id <...>`.

#### Scenario: mesh.generation failure surfaces job_id on stderr without a framework-level second attempt

- GIVEN a `mesh.generation` step backed by `HunyuanMeshWorker` that fails (timeout, HTML body, or explicit `failed` status from `/query`); the failure carries a remote `job_id`
- WHEN the failure propagates upward — through `mesh_worker._apost` (which the docstring explicitly forbids transient retry on, per TBD-007), through `GenerateMeshExecutor` (which forces `attempts=1` for the mesh capability), and through `failure_mode_map` (which routes mesh-specific failures to `abort_or_fallback`)
- THEN no framework layer reissues a second submit for the same step; the CLI surfaces `job_id` / `worker` / `model` on stderr and points the operator at `python -m probes.provider.probe_hunyuan_3d_query --job-id <id>` so the user can inspect remote job state before deciding to `--resume` (preventing the per-call billing double-charge documented in ADR-007); `tests/unit/test_mesh_no_silent_retry.py` enforces this through three layered fences — L1 `_apost` no transient retry, L2 `GenerateMeshExecutor` no internal retry, L3 `failure_mode_map` mesh timeout / error route to abort. The Scenario applies only to `mesh.generation` per ADR-007 and does NOT extend to ordinary LLM retry policy, which remains governed by `RetryPolicy`

### Requirement: Parallel candidates are homogeneous

The system SHALL require `parallel_candidates=True` runs to share a single route (same `chosen_model` + same `_route_pricing`); heterogeneous routes MUST raise explicitly so cost accounting stays faithful.

#### Scenario: parallel_candidates step rejects heterogeneous routing so cost accounting stays faithful to a single chosen_model

- GIVEN a `generate_image` step configured with `parallel_candidates=True` (or `num_candidates > 1`) whose `prepared_routes` would resolve to more than one distinct `chosen_model` if dispatched separately
- WHEN the executor prepares the parallel batch
- THEN the executor raises explicitly rather than silently issuing N calls against heterogeneous routes — preserving the invariant that every candidate in a parallel batch shares the same `chosen_model` and the same `_route_pricing` block, so `BudgetTracker` can attribute cost faithfully to one model. `tests/unit/test_codex_audit_fixes.py::test_generate_image_parallel_rejects_heterogeneous_models` is the canonical fence (Codex audit finding `# #9`); cross-provider ensembles are explicitly out of scope for this Scenario

### Requirement: ComfyUI worker invokes the agent CLI via subprocess

The system SHALL invoke ComfyUI through `python -m comfyui_api run` as a subprocess and parse the stdout JSON envelope, replacing direct `/prompt` + `/history` + `/view` HTTP calls. The worker class `ComfyAgentWorker` SHALL accept `scripts_dir`, `python_exe`, `default_lifecycle`, `run_id`, `project_id`, and `artifacts_dir` as constructor parameters; the **first three** SHALL come from environment variables (`FORGEUE_COMFY_SCRIPTS_DIR`, `FORGEUE_COMFY_PYTHON_EXE`, `FORGEUE_COMFY_LIFECYCLE`) read at executor construction time, NOT from `ProviderDef` fields (the existing `ProviderDef` schema in `src/framework/providers/model_registry.py:117-122` only has `name / api_key_env / api_base` and SHALL NOT be extended in this change — see design.md D7 + D-FutureScope TBD-011 for the deferred schema-extension change). `default_lifecycle` SHALL default to `"none"` if `FORGEUE_COMFY_LIFECYCLE` is unset, and SHALL be restricted to the single value `"none"` in this change scope (see D6 in design.md for the rationale). Each call SHALL pass `--workflow <manifest_name>` + `--params <json>` + `--project <task.project_id>` + `--lifecycle none` + `--timeout <s>`, and parse the resulting JSON whose `outputs.images` field carries absolute PNG paths. The worker MUST NOT speak ComfyUI HTTP directly.

#### Scenario: ComfyAgentWorker reads env config and calls comfyui_api with task.project_id

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`, `FORGEUE_COMFY_PYTHON_EXE` unset (defaults to `sys.executable`), `FORGEUE_COMFY_LIFECYCLE` unset (defaults to `"none"`); a `ctx.run.run_id="run_abc"`; a `ctx.task.project_id="proj_comfy_smoke"`; a `ctx.run_dir=Path("artifacts/2026-05-02/run_abc")` (run_dir injected by Orchestrator per the runtime-core spec delta in this change)
- **WHEN** an executor constructs `worker = ComfyAgentWorker(scripts_dir=Path(env["FORGEUE_COMFY_SCRIPTS_DIR"]), python_exe=None, default_lifecycle=env.get("FORGEUE_COMFY_LIFECYCLE", "none"), run_id=ctx.run.run_id, project_id=ctx.task.project_id, artifacts_dir=ctx.run_dir)` and calls the SYNC ABC method `worker.generate(spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {"text": "oak barrel", "seed": 42}, "comfy_lifecycle": "none"}, num_candidates=1, seed=42, timeout_s=300)` (G11 R4 writeback: ABC `ComfyWorker.generate` is sync; no `worker.submit` async method exists)
- **THEN** the worker spawns `subprocess` with argv `[sys.executable, "-m", "comfyui_api", "run", "--workflow", "GameAssets/01b_singleview_sdxl", "--params", '{"text":"oak barrel","seed":42}', "--project", "proj_comfy_smoke", "--lifecycle", "none", "--timeout", "300"]` and `cwd=scripts_dir`; the worker decodes `result.stdout` as JSON, asserts `data["ok"] is True`, copies each path in `data["outputs"]["images"]` into `artifacts_dir / "comfy" /`, and reads PNG bytes from the copied paths; the worker MUST NOT issue any HTTP request to `localhost:8188`; `project_id` is REQUIRED (not optional with `None` default — `ComfyAgentWorker.__init__` SHALL raise `WorkerUnsupportedResponse` if `project_id is None` or empty)

### Requirement: ComfyUI bundle spec uses manifest workflow + JSON params

The system SHALL accept `step.config.spec.comfy_workflow` (string, manifest name as listed by `python -m comfyui_api list`), `step.config.spec.comfy_params` (dict, passed to `--params`), and optional `step.config.spec.comfy_lifecycle` (string; in this change scope MUST be `"none"`; defaults to `"none"`). The system SHALL reject the legacy `step.config.spec.workflow_graph` field with `WorkerUnsupportedResponse` so a partially migrated bundle fails fast rather than silently going to the wrong code path. The system SHALL also reject any `comfy_lifecycle` value other than `"none"` with `WorkerUnsupportedResponse` until the future `executor-async-rewrite` change (TBD-010) lifts the cancel-reachability constraint.

#### Scenario: Bundle declaring comfy_workflow + comfy_params resolves through ComfyAgentWorker via worker dispatch

- **GIVEN** a step config `{"spec": {"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {"text": "oak barrel", "seed": 42}, "comfy_lifecycle": "none"}, "num_candidates": 1, "worker_timeout_s": 300}` whose `provider_policy.models_ref` resolves to a `prepared_routes` containing `ResolvedRoute(model="comfy/local", ...)`
- **WHEN** the `generate_image` executor's `_resolve_spec` reads the config AND `_should_use_api_path` (the worker-dispatch variant) detects the `comfy/local` model id
- **THEN** the executor takes the worker-dispatch branch (NOT the router-dispatch branch); it constructs `ComfyAgentWorker` from env config + ctx fields, then calls the SYNC ABC method `worker.generate(spec={"comfy_workflow": ..., "comfy_params": ..., "comfy_lifecycle": "none"}, num_candidates=1, seed=..., timeout_s=300)` directly returning `list[ImageCandidate]` (G11 R4 writeback: NO `await`, NO `worker.submit`, NO `asyncio.run` bridge); the executor MUST NOT route through `router.image_generation(prompt, n, size, extra)` for `comfy/local`-bearing routes; the executor MUST NOT read or accept any `workflow_graph` field

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

The current ModelRegistry loader (`_parse_providers` line 262-278, `_parse_models` line 281+) reads known keys with `cfg.get(...)` and **silently ignores unrelated provider/model/alias subfields** — this change does NOT add subfield-rejection (codex round 3 H4 round 1 silent-ignore footgun acknowledged but not fixed in this scope; future enhancement registered in design.md Risks). Implementers SHOULD NOT instinctively put ComfyUI worker config like `providers.comfy_api.scripts_dir: ...` into the YAML — those fields would be silently ignored and the worker would fail with `WorkerUnsupportedResponse("FORGEUE_COMFY_SCRIPTS_DIR not set")` at first run. The `comfy/local` model id is a virtual placeholder — ComfyUI's real "model" is the `comfy_workflow` manifest name carried in `step.config.spec.comfy_workflow`, but the placeholder lets the standard alias-resolution path produce a `ResolvedRoute` so the executor can dispatch on `model == "comfy/local"`. NOTE: `HunyuanTokenhubMeshWorker` is **NOT** dispatched via model id — it is **injected** into `GenerateMeshExecutor` at construction time by `framework.run`. ComfyAgentWorker introduces a NEW dispatch pattern (executor-side branch on `model == "comfy/local"`) for this change.

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
- **THEN** the registry exposes the `comfy_api` provider with `name="comfy_api"`, `api_key_env=None`, `api_base=None` (no extra fields expected); the `comfy/local` model with `id="comfy/local"` / `provider=ProviderDef(name="comfy_api", ...)` / `kind="image"` / `pricing=None`; the `image_local` alias resolves to `[ResolvedRoute(model="comfy/local", api_key_env=None, api_base=None, kind="image", pricing=None)]`; if the `models.comfy/local.id` field is missing, the loader raises `ValueError("model 'comfy/local' missing 'id'")` per `_parse_models` line 290-293; **unknown subfields are silently ignored by the existing loader (NOT raised)** — see future-enhancement note in design.md Risks (codex round 3 H4)

#### Scenario: Bundle declaring models_ref image_local is expanded via ModelRegistry

- **GIVEN** a bundle Step whose `provider_policy` declares `models_ref: "image_local"` (e.g. the rewritten `examples/comfy_local_smoke.json`)
- **WHEN** `load_task_bundle` runs `expand_model_refs(raw, get_model_registry())` on the parsed dict before any `Step.model_validate` call
- **THEN** the alias is replaced in-place by concrete `preferred_models: ["comfy/local"]` + `fallback_models: []`, the resulting Step passes Pydantic validation, and the bundle never reaches the runtime carrying a bare `models_ref: "image_local"` string; downstream `GenerateImageExecutor._should_use_api_path` (worker-dispatch variant) detects the `comfy/local` model id and takes the worker dispatch branch instead of `_generate_via_router`

### Requirement: GenerateImageExecutor dispatches comfy/local to ComfyAgentWorker without going through router

The system SHALL extend `GenerateImageExecutor` to detect when any `prepared_route.model == "comfy/local"` is present and, in that case, take a dedicated **worker dispatch branch** that constructs `ComfyAgentWorker` from environment config + `StepContext` and invokes the **synchronous** ABC method `worker.generate(spec=..., num_candidates=..., seed=..., timeout_s=...)` directly (no `asyncio.run` bridge — `ComfyWorker` ABC `generate` is sync, see `generate_image.py:286` and design.md G4 drift writeback). The router-dispatch branch (`_generate_via_router` calling `router.image_generation(prompt, n, size, extra)` from `spec.prompt_summary`) SHALL NOT be reached for `comfy/local`-bearing routes — that path expects `prompt_summary` which the new ComfyUI bundle spec does not provide, and `LiteLLMAdapter` wildcard would otherwise wrongly claim `model="comfy/local"`. The Comfy worker dispatch shape is **NOT parallel** to mesh worker dispatch: `GenerateMeshExecutor` receives a `HunyuanTokenhubMeshWorker` instance **injected at construction time** by `framework.run` (see `generate_mesh.py:194` "Mesh workers are injected directly into `GenerateMeshExecutor`"); Comfy uses a **NEW pattern** of executor-side branching on `model == "comfy/local"` followed by inline worker construction from env config + `StepContext`.

#### Scenario: Executor takes worker dispatch branch when prepared_routes contains comfy/local

- **GIVEN** a step whose `provider_policy.prepared_routes` contains `ResolvedRoute(model="comfy/local", api_key_env=None, api_base=None, kind="image", pricing=None)` (resolved from `models_ref: "image_local"`)
- **WHEN** `GenerateImageExecutor._should_use_worker_path(ctx)` is called (the new post-change branch detector that checks for `comfy/local` model id) and returns True
- **THEN** the executor calls `_generate_via_worker(ctx=..., spec=..., num=..., seed=..., timeout_s=...)` (a new SYNC method that constructs `ComfyAgentWorker(*, scripts_dir=..., run_id=ctx.run.run_id, project_id=ctx.task.project_id, artifacts_dir=ctx.run_dir, python_exe=..., default_lifecycle="none")` — keyword-only signature per H3 fix; required args first per Python rules) and invokes the SYNC ABC method `worker.generate(spec=spec, num_candidates=num, seed=seed, timeout_s=timeout_s)` directly returning `list[ImageCandidate]` (NO `asyncio.run` bridge, NO `worker.submit`, NO async helper — the ABC is sync; see G11 codex implementation review R4 writeback); `_generate_via_router` is NOT called for this step; `router.image_generation(prompt, ...)` is NOT invoked

#### Scenario: Executor still uses router dispatch for non-comfy/local image routes

- **GIVEN** a step whose `provider_policy.prepared_routes` contains only routes with model ids like `qwen/qwen-image-2.0` or `glm-4.6v` (no `comfy/local`)
- **WHEN** `GenerateImageExecutor._should_use_api_path(ctx)` is called
- **THEN** the method returns True (existing behavior preserved); the executor calls `_generate_via_router` which invokes `router.image_generation(prompt, n, size, extra)`; the worker-dispatch branch is NOT taken; existing qwen / glm image paths are unaffected by this change

### Requirement: Dry-run pass validates ComfyUI subprocess reachability when comfy/local is in prepared_routes

The system SHALL extend the dry-run pass (FR-LC-002) to validate ComfyUI reachability ONLY when the resolved `prepared_routes` actually contain a route with `model == "comfy/local"` (this uses the model id as the dispatch key because `ResolvedRoute` does NOT carry `provider` info — see design.md D7 + Round 2 codex G1 finding for why provider.kind dispatch was rejected in this change scope). The validation SHALL be implemented as a **synchronous** classmethod `ComfyAgentWorker.probe_sync(scripts_dir, python_exe, timeout_s=30) -> None` using `subprocess.run([..., "-m", "comfyui_api", "status"], cwd=scripts_dir, timeout=timeout_s, capture_output=True, text=True)` (NOT `asyncio.create_subprocess_exec` + `asyncio.run`) because `DryRunPass.run` (`src/framework/runtime/dry_run_pass.py:49`) is itself synchronous and is invoked at `orchestrator.py:124` from inside the `arun` event loop — nesting `asyncio.run` there raises `RuntimeError: asyncio.run() cannot be called from a running event loop` (Round 3 plan-stage codex P2 finding). The probe SHALL check `Path(scripts_dir).exists()` AND `(Path(scripts_dir) / "comfyui_api").is_dir()` AND that the subprocess returns exit code 0 within the 30-second timeout. **Implementation note (G8 commit 7 drift writeback)**: the probe failure SHALL emit a `DryRunReport.warnings` entry and `comfy.{env_configured|cli_reachable}` checks set to True with `warning_only=True` — NOT a hard `errors` entry that blocks `report.passed`. Reason: `tests/integration/test_example_bundles_smoke.py::test_bundle_dry_run_passes` is a generic structural fence run against ALL `examples/*.json` bundles on CI hosts without ComfyUI installed; making the probe failure block dry-run would break this generic fence. The hard fail-fast invariant is preserved at step time:`GenerateImageExecutor._generate_via_worker` constructs `ComfyAgentWorker(...)` from env config; if env unset or worker init fails, `WorkerUnsupportedResponse` raises and routes through `FailureModeMap` to `Decision.abort_or_fallback`. Bundles that do not resolve to `comfy/local` (e.g. those using `image_fast` / `image_strong` aliases routing to qwen / glm) SHALL NOT trigger the probe. The error message in the warning SHALL tell the user how to start ComfyUI (`python -m comfyui_api serve` then re-run) AND remind to set `FORGEUE_COMFY_SCRIPTS_DIR` env var if scripts_dir is unset.

#### Scenario: Dry-run pass surfaces missing scripts_dir as a warning when bundle uses comfy/local

- **GIVEN** a bundle whose `step_image` resolves through `image_local` alias → `comfy/local` model, and either the env var `FORGEUE_COMFY_SCRIPTS_DIR` is unset OR points to a non-existent directory
- **WHEN** `framework.run` invokes `DryRunPass.run(...)` before reaching the scheduler
- **THEN** `DryRunReport.warnings` contains a `comfy_unreachable` entry naming the missing env var or scripts_dir path AND telling the user to either set `FORGEUE_COMFY_SCRIPTS_DIR` or start ComfyUI via `python (module flag) comfyui_api serve`; `comfy.env_configured` and `comfy.cli_reachable` checks are emitted with `warning_only=True`; `report.passed` remains True so the generic structural fence `tests/integration/test_example_bundles_smoke.py::test_bundle_dry_run_passes` (run on CI hosts without ComfyUI installed) is NOT broken; the Run does NOT fail at dry-run time and proceeds to scheduling — the hard failure is enforced at step time by the scenario "ComfyAgentWorker fails fast at step time when env var unset" below (G11 codex implementation review R5 writeback)

#### Scenario: ComfyAgentWorker fails fast at step time when env var unset

- **GIVEN** a bundle whose `step_image` resolves through `image_local` alias → `comfy/local` model, the env var `FORGEUE_COMFY_SCRIPTS_DIR` is unset, AND the dry-run only emitted a warning (not a hard error)
- **WHEN** the scheduler reaches the image step and `GenerateImageExecutor._generate_via_worker(ctx=..., spec=..., ...)` is invoked
- **THEN** the missing env var check at `generate_image.py:270-275` raises `WorkerUnsupportedResponse("FORGEUE_COMFY_SCRIPTS_DIR env var unset; ...")`; `FailureModeMap` resolves the failure to `unsupported_response` → `Decision.abort_or_fallback`; the same step is NOT retried; the run transitions to `failed` with a structured failure reason — proving that the dry-run `warning_only` choice does NOT mask production breakage, the hard fail-fast invariant is preserved one layer deeper

#### Scenario: Dry-run pass skips ComfyUI probe when bundle does not use comfy/local

- **GIVEN** a bundle whose all `image.generation` steps resolve through `image_fast` alias → qwen / glm models (no route in `prepared_routes` has `model == "comfy/local"`)
- **WHEN** `framework.run` invokes `DryRunPass.run(...)`
- **THEN** the dry-run does NOT spawn `python (module flag) comfyui_api status` or otherwise touch `D:/AI/ComfyUI/scripts/`; the Run proceeds to scheduling normally even on a host where ComfyUI is not installed and `FORGEUE_COMFY_SCRIPTS_DIR` is unset

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

`asyncio.CancelledError` propagation is governed by a separate Requirement ("ComfyAgentWorker cancel is best-effort under orchestrator to_thread wrapping") below — it is NOT mapped through `FailureModeMap` because the cancel signal does not actually reach the synchronous `worker.generate(...)` invocation in the current orchestrator architecture (sync executors run inside `asyncio.to_thread`, see D6 in design.md). G11 R4 writeback: text updated from "worker.submit" to "worker.generate" because the ABC is sync.

#### Scenario: Exit code 2 with Missing required param raises WorkerUnsupportedResponse

- **GIVEN** a `ComfyAgentWorker.generate` whose subprocess returns exit code 2 with stdout `{"ok": false, "error": "ValueError: Missing required param 'text'"}`
- **WHEN** the worker parses the result
- **THEN** the worker raises `WorkerUnsupportedResponse` with a message preserving the original error string; the executor's `_should_retry` returns False; `FailureModeMap` resolves the failure to `unsupported_response` → `Decision.abort_or_fallback`; the same step is NOT retried

#### Scenario: Exit code 2 with TimeoutError raises WorkerTimeout

- **GIVEN** a `ComfyAgentWorker.generate` whose subprocess returns exit code 2 with stdout `{"ok": false, "error": "TimeoutError: Prompt did not complete within 300s"}`
- **WHEN** the worker parses the result
- **THEN** the worker raises `WorkerTimeout`; `FailureModeMap` resolves to `worker_timeout` → `Decision.retry_same_step` (default at most 2 retries)

### Requirement: ComfyAgentWorker cancel is best-effort under orchestrator to_thread wrapping

The system SHALL document that `CancelledError` propagation does NOT reach `ComfyAgentWorker.generate` while the synchronous `GenerateImageExecutor.execute` is wrapped by `asyncio.to_thread(executor.execute, ctx)` in `src/framework/runtime/orchestrator.py:474` (see orchestrator.py:286-296 inline notes — "sync executors in `asyncio.to_thread` can't be interrupted"). Under the `lifecycle="none"` constraint mandated by this change (D6), the `comfyui_api` subprocess naturally exits when ComfyUI completes the request; the worker thread then completes; the outer Future has already been cancelled by the orchestrator and its result is discarded. No orphan processes are produced because lifecycle=none does NOT spawn the ComfyUI server process — the server is owned by the user. The future `executor-async-rewrite` change (TBD-010) SHALL re-evaluate this contract once the orchestrator path can `await` worker calls directly.

#### Scenario: Cancel during ComfyAgentWorker run does not produce orphan processes

- **GIVEN** a step running through `ComfyAgentWorker.generate` with a `comfyui_api` subprocess in flight, and a sibling DAG step raising an exception that triggers `cascade_terminate`
- **WHEN** the orchestrator cancels the outer Future for the in-flight image step
- **THEN** the `comfyui_api` subprocess continues to run in the worker thread until ComfyUI finishes the request naturally (or the worker `timeout_s` fires); the worker thread completes; no `comfyui_api` or ComfyUI server child process is left as an orphan because lifecycle=none does NOT spawn a server child; the orchestrator's already-set `cancel()` on the Future means the result is discarded; the run terminates as expected by the cascade-cancel path

### Requirement: ComfyAgentWorker rejects non-image outputs in the image-generation path

The system SHALL treat a non-empty `outputs.audio` or `outputs.glb` field in the agent CLI response as `WorkerUnsupportedResponse` when invoked through `ComfyAgentWorker` in the `image.generation` capability path. Mesh, audio, and video workflows are out of scope for this change; mixing them into the image generation path would silently drop produced bytes (image executor only constructs `ImageCandidate`s) and would skip the modality-specific metadata required by the `artifact-contract` mesh / audio requirements. A future change SHALL introduce dedicated mesh / audio paths before non-empty values in those fields are accepted.

#### Scenario: Workflow accidentally selected that produces a GLB raises rather than silently dropping it

- **GIVEN** a step config mistakenly using `comfy_workflow: "GameAssets/02_mini_textured_3d_hunyuan"` (a manifest that produces both a PNG preview and a GLB), invoked via the image-generation executor
- **WHEN** `ComfyAgentWorker.generate` parses the agent CLI stdout and finds `outputs.glb = ["D:/.../barrel_textured_00001_.glb"]` non-empty
- **THEN** the worker raises `WorkerUnsupportedResponse` with a message naming the unexpected non-empty field and pointing the user at the future mesh-path change; no `ImageCandidate` is constructed; no GLB is copied into the artifact tree; `FailureModeMap` resolves to `unsupported_response` → `Decision.abort_or_fallback` (no same-step retry, no silent data loss)

## Invariants

- `FakeAdapter` is the offline test provider; it never performs network I/O.
- Tripo3D parser stays at `NotImplementedError` until an authoritative per-task price is published (SRS TBD-005).
- `pricing_autogen.status=manual` is the sacred opt-out from the probe.
- Adapter base methods are the four-method interface; new adapters conform without expanding the base.
- ComfyUI integration requires a user-owned local ComfyUI at `http://127.0.0.1:8188` (no framework-managed lifecycle).

## Validation

- Unit: `tests/unit/test_model_registry.py`, `test_providers.py`, `test_providers_async.py`, `test_router_fallback_errors.py`, `test_router_pricing_stash.py`, `test_adapter_budget_clamp.py`
- Unit: `tests/unit/test_cn_image_adapters.py`, `test_download_async.py`, `test_mesh_no_silent_retry.py`, `test_comfy_http_unsupported.py`, `test_tripo3d_unsupported.py`, `test_generate_mesh_cost.py`, `test_multi_candidate_parallel.py`, `test_retry_async.py`, `test_transient_retry.py`
- Unit pricing: `test_registry_pricing.py`, `test_budget_tracker_pricing.py`, `test_pricing_probe_framework.py`, `test_pricing_parser_{zhipu,dashscope,hunyuan_image,hunyuan_3d}.py`
- Integration: `tests/integration/test_mesh_failure_visibility.py`, `test_l4_image_to_3d.py`, `test_image_edit.py`, `test_example_bundles_smoke.py`
- Level 1 live (opt-in): `python -m probes.provider.probe_packycode`, `probe_glm_image_debug`, `probe_glm_watermark_param`
- Level 2 premium (opt-in): `FORGEUE_PROBE_HUNYUAN_3D=1 python -m probes.provider.probe_hunyuan_3d_submit`, `probe_hunyuan_3d_query --job-id <...>`, `probe_hunyuan_3d_format`
- Pricing data refresh: `python -m framework.pricing_probe --apply` (writes `demo_artifacts/<YYYY-MM-DD>/pricing/<HHMMSS>/`)
- Test totals: see `python -m pytest -q` actual output.

## Non-Goals

- Audio worker (AudioCraft / other; SRS TBD-002).
- Real-time streaming generation.
- Tripo3D live pricing parser (waits for public tariff; SRS TBD-005).
- Framework-managed ComfyUI process lifecycle (users own their ComfyUI).
