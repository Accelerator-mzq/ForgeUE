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
- THEN the executor takes the comfy-worker dispatch branch (NOT the constructor-injected `HunyuanTokenhubMeshWorker` path) and calls `_generate_via_comfy_worker(...)` which writes source bytes to `Path(FORGEUE_COMFY_INPUT_DIR) / "forgeue_<sha1>.png"`(round 5 D10 修订:ComfyUI input/ 而非 in-tree), constructs `ComfyAgentWorker(model_id="comfy/local-mesh", ...)` inline, and invokes `worker.generate_mesh(spec=..., source_image_filename="forgeue_<sha1>.png")`(filename only); `_capability="mesh"` is inferred; output validation requires `outputs.glb` non-empty, tolerates `outputs.images`, rejects `outputs.audio / video`; returned `MeshCandidate`s carry comfy provenance in `metadata={...}` and are persisted via the existing `repo.put` loop with `metadata={"worker_metadata": dict(cand.metadata), ...}`

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

The system SHALL invoke ComfyUI through `python -m comfyui_api run` as a subprocess and parse the stdout JSON envelope, replacing direct `/prompt` + `/history` + `/view` HTTP calls. The worker class `ComfyAgentWorker` SHALL accept the following constructor parameters (keyword-only):

- `scripts_dir: Path` — REQUIRED, from `FORGEUE_COMFY_SCRIPTS_DIR`
- `model_id: str` — REQUIRED (NEW for `comfy-agent-cli-mesh-audio-video-adoption`), used to infer `_capability` via `_CAPABILITY_BY_MODEL_ID` table; unknown id raises `WorkerUnsupportedResponse` per the Requirement "ComfyAgentWorker dispatches by capability inferred from model id" above
- `run_id: str` — REQUIRED, from `ctx.run.run_id`
- `project_id: str` — REQUIRED, from `ctx.task.project_id` (raises `WorkerUnsupportedResponse` if None or empty)
- `artifacts_dir: Path` — REQUIRED, from `ctx.run_dir` (raises `WorkerUnsupportedResponse` if None or not a directory)
- `python_exe: Path | None = None` — OPTIONAL, defaults to `sys.executable` if None
- `default_lifecycle: str = "none"` — OPTIONAL, MUST be `"none"` in this change scope (constraint inherited from `comfy-agent-cli-adoption` D6); other values raise `WorkerUnsupportedResponse`

The `model_id` parameter is the ONLY signature extension introduced by `comfy-agent-cli-mesh-audio-video-adoption`; all other parameters and their semantics inherit from `comfy-agent-cli-adoption` unchanged.

Each call SHALL pass `--workflow <manifest_name>` + `--params <json>` + `--project <task.project_id>` + `--lifecycle none` + `--timeout <s>`, and parse the resulting JSON whose `outputs.<key>` field carries absolute paths per the resolved capability (`outputs.images` for image-mode, `outputs.glb` for mesh-mode). The worker MUST NOT speak ComfyUI HTTP directly. The image-mode entry point is the existing ABC method `ComfyWorker.generate(spec, num_candidates, seed, timeout_s) -> list[ImageCandidate]`; the mesh-mode entry point is the new public method `ComfyAgentWorker.generate_mesh(spec, source_image_filename: str, num_candidates, seed, timeout_s) -> list[MeshCandidate]` (round 5 D10 修订:`source_image_filename` 是 ComfyUI input/ 内的 filename 不是绝对路径;NOT part of `ComfyWorker` ABC, since the ABC return type is `list[ImageCandidate]`; mesh-mode has its own dispatch via `GenerateMeshExecutor._generate_via_comfy_worker` per design D7). Both methods share a private helper `_run_subprocess_and_validate(spec, timeout_s) -> dict` that runs the subprocess, parses stdout JSON, and invokes capability-aware `_validate_outputs(outputs)`.

#### Scenario: ComfyAgentWorker (image) reads env config and calls comfyui_api with task.project_id

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`, `FORGEUE_COMFY_PYTHON_EXE` unset, `FORGEUE_COMFY_LIFECYCLE` unset; resolved route `ResolvedRoute(model="comfy/local", ...)`; `ctx.run.run_id="run_abc"`; `ctx.task.project_id="proj_comfy_smoke"`; `ctx.run_dir=Path("artifacts/2026-05-02/run_abc")`
- **WHEN** `GenerateImageExecutor._generate_via_worker` constructs `worker = ComfyAgentWorker(scripts_dir=..., model_id="comfy/local", run_id=..., project_id=..., artifacts_dir=..., default_lifecycle="none")` and calls the SYNC ABC method `worker.generate(spec={"comfy_workflow": "GameAssets/01b_singleview_sdxl", "comfy_params": {...}, "comfy_lifecycle": "none"}, num_candidates=1, seed=42, timeout_s=300)`
- **THEN** the worker's `_capability == "image"`; the worker spawns subprocess with argv `[sys.executable, "-m", "comfyui_api", "run", "--workflow", "GameAssets/01b_singleview_sdxl", "--params", '{...}', "--project", "proj_comfy_smoke", "--lifecycle", "none", "--timeout", "300"]`; `_validate_outputs` accepts `outputs.images` non-empty and rejects `outputs.glb / audio / video` per the capability-aware Requirement; the worker reads PNG bytes from `outputs.images` paths, copies them to `artifacts_dir/comfy/`, and returns `list[ImageCandidate]` per the image-change contract

#### Scenario: ComfyAgentWorker (mesh) calls generate_mesh with source_image_filename injected

- **GIVEN** environment variables as above + `FORGEUE_COMFY_INPUT_DIR=D:/AI/ComfyUI/apps/official-main-git-v092/input`; resolved route `ResolvedRoute(model="comfy/local-mesh", ..., pricing=None)`; an upstream image step has produced source bytes resolved via `_resolve_source_image(ctx)` and written to `D:/AI/ComfyUI/apps/official-main-git-v092/input/forgeue_abc123def456.png` by `_generate_via_comfy_worker` (round 5 D10:写到 ComfyUI input/ 而非 in-tree)
- **WHEN** `GenerateMeshExecutor._generate_via_comfy_worker` constructs `worker = ComfyAgentWorker(scripts_dir=..., model_id="comfy/local-mesh", run_id=..., project_id=..., artifacts_dir=..., default_lifecycle="none")` and calls `worker.generate_mesh(spec={"comfy_workflow": "3D_Hunyuan/3d_hunyuan3d-v2.1", "comfy_params": {"seed": 42, "steps": 30}, "comfy_lifecycle": "none"}, source_image_filename="forgeue_abc123def456.png", num_candidates=1, seed=42, timeout_s=600)`(round 5 D10:filename only)
- **THEN** the worker's `_capability == "mesh"`; the worker constructs enriched params `{"seed": 42, "steps": 30, "input_image": "forgeue_abc123def456.png"}` (round 5 D8 默认 `input_image`;not mutating caller's `spec["comfy_params"]`); the worker spawns subprocess with argv `[..., "--workflow", "3D_Hunyuan/3d_hunyuan3d-v2.1", "--params", '{"seed":42,"steps":30,"input_image":"forgeue_abc123def456.png"}', ...]`; ComfyUI's `LoadImage` node resolves the filename inside its own `input/` directory and reads the source PNG; `_validate_outputs` accepts `outputs.glb` non-empty, tolerates `outputs.images` (auxiliary preview, not consumed), rejects `outputs.audio / video`; the worker reads GLB bytes from `outputs.glb` paths and returns `list[MeshCandidate(data=..., format="glb", metadata={...comfy provenance including comfy_input_filename + comfy_input_dir...})]` per the artifact-contract spec

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

The system SHALL extend the dry-run pass (FR-LC-002) to validate ComfyUI reachability ONLY when the resolved `prepared_routes` actually contain a route with `model == "comfy/local"` (this uses the model id as the dispatch key because `ResolvedRoute` does NOT carry `provider` info — see design.md D7 + Round 2 codex G1 finding for why provider.kind dispatch was rejected in this change scope). The validation SHALL be implemented as a **synchronous** classmethod `ComfyAgentWorker.probe_sync(scripts_dir, python_exe, timeout_s=30) -> None` using `subprocess.run([..., "-m", "comfyui_api", "status"], cwd=scripts_dir, timeout=timeout_s, capture_output=True, text=True)` (NOT `asyncio.create_subprocess_exec` + `asyncio.run`) because `DryRunPass.run` (`src/framework/runtime/dry_run_pass.py:49`) is itself synchronous and is invoked at `orchestrator.py:124` from inside the `arun` event loop — nesting `asyncio.run` there raises `RuntimeError: asyncio.run() cannot be called from a running event loop` (Round 3 plan-stage codex P2 finding). The probe SHALL check `Path(scripts_dir).exists()` AND `(Path(scripts_dir) / "comfyui_api").is_dir()` AND that the subprocess returns exit code 0 within the 30-second timeout. **Implementation note (G8 commit 7 drift writeback)**: the probe failure SHALL emit a `DryRunReport.warnings` entry and `comfy.{env_configured|cli_reachable}` checks set to True with `warning_only=True` — NOT a hard `errors` entry that blocks `report.passed`. Reason: `tests/integration/test_example_bundles_smoke.py::test_bundle_dry_run_passes` is a generic structural fence run against ALL `examples/*.json` bundles on CI hosts without ComfyUI installed; making the probe failure block dry-run would break this generic fence. The hard fail-fast invariant is preserved at step time:`GenerateImageExecutor._generate_via_worker` constructs `ComfyAgentWorker(...)` from env config; if env unset or worker init fails, `WorkerUnsupportedResponse` raises and routes through `FailureModeMap` to `Decision.abort_or_fallback`. Bundles that do not resolve to `comfy/local` (e.g. those using `image_fast` / `image_strong` aliases routing to qwen / glm) SHALL NOT trigger the probe. The error message in the warning SHALL tell the user how to start ComfyUI (`python -m factory_v3 serve` then re-run; the `comfyui_api` sister CLI under the same `scripts/` directory does NOT have a `serve` subcommand — it only handles `{list, params, run, batch, status, cancel}` — so service start is provided by `factory_v3 serve` per L2 live smoke evidence at `openspec/changes/archive/2026-05-02-comfy-agent-cli-adoption/notes/live_smoke_20260503.md`) AND remind to set `FORGEUE_COMFY_SCRIPTS_DIR` env var if scripts_dir is unset.

#### Scenario: Dry-run pass surfaces missing scripts_dir as a warning when bundle uses comfy/local

- **GIVEN** a bundle whose `step_image` resolves through `image_local` alias → `comfy/local` model, and either the env var `FORGEUE_COMFY_SCRIPTS_DIR` is unset OR points to a non-existent directory
- **WHEN** `framework.run` invokes `DryRunPass.run(...)` before reaching the scheduler
- **THEN** `DryRunReport.warnings` contains a `comfy_unreachable` entry naming the missing env var or scripts_dir path AND telling the user to either set `FORGEUE_COMFY_SCRIPTS_DIR` or start ComfyUI via `python (module flag) factory_v3 serve` (NOT `comfyui_api serve` — that subcommand does not exist; see the parent Requirement's implementation note for the full rationale); `comfy.env_configured` and `comfy.cli_reachable` checks are emitted with `warning_only=True`; `report.passed` remains True so the generic structural fence `tests/integration/test_example_bundles_smoke.py::test_bundle_dry_run_passes` (run on CI hosts without ComfyUI installed) is NOT broken; the Run does NOT fail at dry-run time and proceeds to scheduling — the hard failure is enforced at step time by the scenario "ComfyAgentWorker fails fast at step time when env var unset" below (G11 codex implementation review R5 writeback)

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

### Requirement: ComfyAgentWorker dispatches by capability inferred from model id

The system SHALL extend `ComfyAgentWorker` to support multiple ComfyUI capabilities (image, mesh, and future audio / video) via a single worker class with capability dispatch driven by the resolved model id, NOT by an explicit bundle field. The worker SHALL maintain an internal table `_CAPABILITY_BY_MODEL_ID` mapping concrete `comfy/local*` model ids to capability tags (`comfy/local` → `image`, `comfy/local-mesh` → `mesh`); future audio / video capabilities will extend this table in their own follow-on changes (`comfy-agent-cli-audio-adoption` / `comfy-agent-cli-video-adoption`). The worker constructor SHALL accept the resolved `model_id` (in addition to the existing `scripts_dir` / `python_exe` / `default_lifecycle` / `run_id` / `project_id` / `artifacts_dir` parameters established by `comfy-agent-cli-adoption`); if `model_id` is not in `_CAPABILITY_BY_MODEL_ID`, the constructor SHALL raise `WorkerUnsupportedResponse` with a message naming the unknown id and listing supported ids — capability inference SHALL NOT silently fall back to image-mode. Bundle protocol (`step.config.spec.comfy_workflow` + `comfy_params` + `comfy_lifecycle: "none"`) SHALL remain unchanged from the image-only contract; users do NOT add an `outputs_kind` field. Mesh-capable bundles MAY add the optional `step.config.spec.comfy_image_param_key` field (**round 5 修订** default `"input_image"`,与 `3D_Hunyuan/3d_hunyuan3d-v2.1` 等 LoadImage-based mesh manifest 一致;round 1-4 默认 `"image_path"` 是凭直觉,Phase B Task 1.3 实地 probe 修订) to declare which `comfy_params` key receives the upstream source image **filename** (NOT absolute path; see Requirement "GenerateMeshExecutor writes source image bytes to ComfyUI input/ directory and injects filename into comfy_params").

#### Scenario: ComfyAgentWorker constructed with comfy/local-mesh enters mesh capability mode

- **GIVEN** environment variables `FORGEUE_COMFY_SCRIPTS_DIR=D:/AI/ComfyUI/scripts`, `FORGEUE_COMFY_LIFECYCLE` unset (defaults to `"none"`); a resolved `ResolvedRoute(model="comfy/local-mesh", api_key_env=None, api_base=None, kind="mesh", pricing=None)`; `ctx.run.run_id="run_mesh_smoke"`; `ctx.task.project_id="proj_mesh"`; `ctx.run_dir=Path("artifacts/2026-05-XX/run_mesh_smoke")`
- **WHEN** `GenerateMeshExecutor._generate_via_comfy_worker` constructs `ComfyAgentWorker(scripts_dir=..., model_id="comfy/local-mesh", run_id=..., project_id=..., artifacts_dir=..., default_lifecycle="none")`
- **THEN** the worker's `self._capability` attribute equals `"mesh"`; subsequent `worker.generate_mesh(spec=..., source_image_filename=..., num_candidates=1, seed=42, timeout_s=600)` calls validate outputs against the mesh capability rules per the Requirement "ComfyAgentWorker output validation is capability-aware (REQUIRED + auxiliary + rejected)" below; the worker MUST NOT silently fall back to image-mode parsing (round 5 修订:`source_image_path` → `source_image_filename` per D10:LoadImage 节点接 filename 而非绝对路径)

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
2. A new method `_generate_via_comfy_worker(self, *, ctx, spec, source_image_bytes, source_image_artifact_id, num, seed, timeout_s) -> list[MeshCandidate]` that constructs `ComfyAgentWorker(model_id="comfy/local-mesh", ...)` from environment config + `StepContext`, writes `source_image_bytes` to **the ComfyUI installation's `input/` directory** under filename `forgeue_<sha1_hex>.png` (round 5 D10 修订:directory resolved via REQUIRED env var `FORGEUE_COMFY_INPUT_DIR`, e.g. `D:/AI/ComfyUI/apps/<install>/input`; was `<ctx.run_dir>/comfy/input/...` round 1-4 但 ComfyUI LoadImage 节点不接受任意绝对路径,实测必失败), invokes the new public method `worker.generate_mesh(spec=..., source_image_filename="forgeue_<sha1>.png")` (filename only, NOT absolute path), and returns `list[MeshCandidate]`.

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
- **THEN** the executor calls `_resolve_source_image(ctx)` first (unchanged from the existing path; raises if no upstream image is available — this is the same fail-fast behavior as Hunyuan / Tripo3D mesh paths); then calls `_generate_via_comfy_worker(ctx=ctx, spec=spec, source_image_bytes=source_bytes, source_image_artifact_id=source_image_artifact_id, ...)` which constructs `ComfyAgentWorker(model_id="comfy/local-mesh", ...)` inline and invokes `worker.generate_mesh(spec=..., source_image_filename="forgeue_<sha1>.png", ...)` (round 5 修订:filename only,实际文件已写入 `Path(FORGEUE_COMFY_INPUT_DIR) / "forgeue_<sha1>.png"`,LoadImage 节点会自动 prefix ComfyUI 自家 input/);the constructor-injected `HunyuanTokenhubMeshWorker.generate` is NOT invoked

#### Scenario: GenerateMeshExecutor still uses constructor-injected worker for remote hunyuan/mesh-generation routes

- **GIVEN** a step whose `provider_policy.prepared_routes` contains only `ResolvedRoute(model="hunyuan/hy-3d-3.1", ...)` (no `comfy/local-mesh`)
- **WHEN** `GenerateMeshExecutor._should_use_comfy_worker_path(ctx)` is called
- **THEN** the method returns False; the executor takes the existing constructor-injected worker path (calls `self._worker.generate(source_image_bytes=..., spec=..., ...)`); existing remote Hunyuan3D mesh path is unaffected by this change; ADR-007 strict no-silent-retry contract continues to apply unchanged for the remote path (see Requirement "Local ComfyUI mesh worker is NOT a premium API per the per_task_usd boundary" below)

### Requirement: GenerateMeshExecutor writes source image bytes to ComfyUI input/ directory and injects filename into comfy_params

The system SHALL guarantee that `_generate_via_comfy_worker` writes the upstream `source_image_bytes` to **the ComfyUI installation's `input/` directory** (path resolved via REQUIRED env var `FORGEUE_COMFY_INPUT_DIR`, e.g. `D:/AI/ComfyUI/apps/official-main-git-v092/input`) under filename `forgeue_<sha1_hex>.png` (where `<sha1_hex> = hashlib.sha1(source_image_bytes).hexdigest()[:16]`;`forgeue_` filename prefix avoids collision with ComfyUI's own input files) before invoking the worker subprocess. The **filename only** (NOT absolute path) SHALL be passed to `ComfyAgentWorker.generate_mesh(source_image_filename=...)`, which injects it into a copy of `spec["comfy_params"]` under the key resolved from `spec.get("comfy_image_param_key", "input_image")` (round 5 修订:default `"input_image"` matches `LoadImage` node parameter name; bundles SHALL declare `comfy_image_param_key` explicitly when the selected manifest's image input parameter has a different name). The worker SHALL NOT mutate the caller's `spec["comfy_params"]` in place — it SHALL deep-copy via `dict(spec.get("comfy_params") or {})` before injection so retries see a clean baseline.

If `FORGEUE_COMFY_INPUT_DIR` is unset or empty, `_generate_via_comfy_worker` SHALL raise `MeshWorkerUnsupportedResponse` with a message naming the missing env var and a hint pointing at the typical ComfyUI input/ path.

#### Scenario: Source image bytes are written to ComfyUI input/ directory with sha1-derived filename and forgeue_ prefix; injected into comfy_params under default 'input_image' key

- **GIVEN** env var `FORGEUE_COMFY_INPUT_DIR=D:/AI/ComfyUI/apps/official-main-git-v092/input`; an upstream `_resolve_source_image(ctx)` returning `(source_bytes=b"<png>", source_image_artifact_id="run_X_step_image_1")` where `hashlib.sha1(b"<png>").hexdigest()[:16] == "abc123def456"`; a step `spec` containing `comfy_workflow="3D_Hunyuan/3d_hunyuan3d-v2.1"`, `comfy_params={"seed": 42, "steps": 30}`, `comfy_lifecycle="none"`(no explicit `comfy_image_param_key` → uses default `"input_image"`)
- **WHEN** `_generate_via_comfy_worker(ctx, spec, source_image_bytes=source_bytes, source_image_artifact_id=..., num=1, seed=42, timeout_s=600)` is invoked
- **THEN** the executor writes `source_bytes` to `D:/AI/ComfyUI/apps/official-main-git-v092/input/forgeue_abc123def456.png` (creating the directory if missing; idempotent on subsequent calls with same bytes); calls `ComfyAgentWorker.generate_mesh(spec=spec, source_image_filename="forgeue_abc123def456.png", num_candidates=1, seed=42, timeout_s=600)`(filename only, NOT absolute path); the worker constructs an enriched params dict `{"seed": 42, "steps": 30, "input_image": "forgeue_abc123def456.png"}`(NOT mutating the caller's `spec["comfy_params"]`); the subprocess argv contains `--params '{"seed":42,"steps":30,"input_image":"forgeue_abc123def456.png"}'` and ComfyUI's `LoadImage` node resolves the filename inside its own input/ directory

#### Scenario: Bundle with custom comfy_image_param_key uses the declared key instead of default 'input_image'

- **GIVEN** a step `spec` with `comfy_image_param_key: "image"` (some hypothetical mesh manifest using key `image` instead of default `input_image`)
- **WHEN** `worker.generate_mesh(...)` is invoked
- **THEN** the enriched params dict uses key `"image"` (not default `"input_image"`); subprocess argv contains `--params '{...,"image":"forgeue_<sha1>.png"}'`

#### Scenario: Missing FORGEUE_COMFY_INPUT_DIR env var raises MeshWorkerUnsupportedResponse

- **GIVEN** env var `FORGEUE_COMFY_INPUT_DIR` unset (other `FORGEUE_COMFY_*` vars correctly set);comfy/local-mesh route resolved
- **WHEN** `_generate_via_comfy_worker(ctx, spec, source_image_bytes=..., ...)` is invoked
- **THEN** the executor raises `MeshWorkerUnsupportedResponse` with a message naming `FORGEUE_COMFY_INPUT_DIR` and a hint pointing at the typical ComfyUI input/ path; no source image bytes are written; no subprocess is spawned; `FailureModeMap` resolves the failure to `mesh_worker_unsupported_response` → `Decision.abort_or_fallback`

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
