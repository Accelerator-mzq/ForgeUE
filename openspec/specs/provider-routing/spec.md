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

Adapters ship for four protocol families: LiteLLM (OpenAI-compatible + Anthropic via proxies such as PackyCode / MiniMax), DashScope (`qwen_multimodal_adapter.py`), Hunyuan tokenhub (image via `hunyuan_tokenhub_adapter.py`, 3D via `providers/workers/mesh_worker.py`), and ComfyUI HTTP (`providers/workers/comfy_worker.py`). A Tripo3D scaffold exists in `mesh_worker.py` but its pricing parser is guarded by `NotImplementedError` until an authoritative per-task price is published. Mesh-worker downloads rank URLs (`strong` > `ok` > `key` > `other` > `zip`), iterate the fallthrough loop, and validate via magic bytes (`glb` must start with `b"glTF"`); `data:` URI detection is case-insensitive (RFC 2397).

Pricing flows in two directions. The `pricing_probe` CLI (`httpx` for static pages + `playwright` for JS SPAs) refreshes `pricing_autogen.status=fresh` entries but NEVER overwrites a `status=manual` entry. At request time, the chosen route's pricing block is stashed in `ProviderResult.raw["_route_pricing"]` (no tuple-signature break) so every paid executor can feed the right unit cost into `BudgetTracker`. For mesh generation specifically (ADR-007), ForgeUE refuses to silently retry: `GenerateMeshExecutor` forces `attempts=1`, `mesh_worker._apost` is NOT wrapped in transient retry, and the CLI surfaces `job_id` on failure so the user can run the `probe_hunyuan_3d_query` opt-in probe before deciding to `--resume`.

## Requirements

### Requirement: Three-section ModelRegistry is the single source

The system SHALL treat `config/models.yaml` (sections: `providers`, `models`, `aliases`) as the sole source of truth for provider endpoints, model ids, and capability aliases (ADR-002).

### Requirement: Alias reference expansion in the loader

The system SHALL expand every bundle's `provider_policy.models_ref: "<alias>"` into `prepared_routes` before Pydantic validation; each route contains `model_id`, `api_key_env`, `api_base`, `kind`.

### Requirement: OpenAI-compatible endpoints add zero code

The system SHALL let an operator add a new OpenAI-compatible provider by editing only `config/models.yaml` (providers block + models block), with the bundle writing `openai/<id>` and no new adapter code.

### Requirement: Non-OpenAI protocols ship dedicated adapters

The system SHALL route non-OpenAI protocols via `model.startswith(...)` prefix matching inside dedicated adapters under `src/framework/providers/`.

### Requirement: Wildcard adapter is registered last

The system SHALL register `LiteLLMAdapter` (wildcard) LAST in the adapter chain so that prefixed adapters (`qwen/`, `hunyuan/`) claim their models first (ADR-003).

#### Scenario: Qwen model routed to the DashScope adapter

- GIVEN a registry where `QwenMultimodalAdapter` precedes `LiteLLMAdapter`
- WHEN a request targets `qwen/qwen-image-2.0`
- THEN `QwenMultimodalAdapter.supports(model)` returns True first and the request goes through DashScope, not LiteLLM

### Requirement: Capability aliases drive provider selection

The system SHALL expose the current capability alias set (`text_cheap`, `text_strong`, `review_judge`, `review_judge_visual`, `ue5_api_assist`, `image_fast`, `image_strong`, `image_edit`, `mesh_from_image`); bundles SHALL refer to aliases, not raw model ids, unless a bundle explicitly overrides via `preferred_models` / `fallback_models`.

### Requirement: Route pricing is stashed on every ProviderResult

The system SHALL place the chosen route's pricing block into `ProviderResult.raw["_route_pricing"]`; the public tuple signature MUST NOT break.

### Requirement: Pricing probe defaults to dry-run

The system SHALL default the pricing probe to dry-run; `--apply` is required to mutate `config/models.yaml`; entries with `pricing_autogen.status=manual` MUST NOT be overwritten.

### Requirement: External factual pricing requires a verifiable source

The system SHALL either carry a `pricing_autogen` block with `status`, `sourced_on`, `source_url`, and `cny_original` (when applicable) on every `pricing` entry, OR leave `pricing` null with a TODO comment (ADR-004).

### Requirement: URL-rank fallthrough for mesh worker

The system SHALL rank mesh-worker result URLs as `strong > ok > key > other > zip` and iterate the ranked list; `MeshWorkerUnsupportedResponse` continues to the next candidate; `MeshWorkerError` terminates.

### Requirement: Range-resume integrity

The system SHALL use `chunked_download_async()` with Range continuation; a resume response MUST be `206` with a `Content-Range` header whose start offset matches the expected offset.

### Requirement: Magic-bytes format gate

The system SHALL validate mesh format magic bytes — `fmt == "glb"` MUST have `data[:4] == b"glTF"`; mismatch raises `MeshWorkerUnsupportedResponse`. glTF external buffer payloads MUST raise (not fall back to `missing_materials=True`).

### Requirement: Case-insensitive data: URI

The system SHALL treat `data:` URI scheme detection as case-insensitive (RFC 2397).

### Requirement: tokenhub poll timeout is clamped

The system SHALL clamp every tokenhub `/query` HTTP timeout to `min(<per_poll_cap>, max(1.0, budget_s - elapsed))`; when only 1 s of budget remains, a single poll MUST NOT block for 20-30 s.

### Requirement: HTML-body pollution wraps as unsupported

The system SHALL, on a 200 response whose body is not JSON, catch `ValueError` / `JSONDecodeError` and wrap it as `ProviderUnsupportedResponse` or `MeshWorkerUnsupportedResponse`; the raw JSON error MUST NOT escape the adapter.

### Requirement: Premium-API single-attempt guard

The system SHALL forbid framework-level silent retry for `mesh.generation` (ADR-007). On failure, the CLI MUST surface `job_id` on stderr and point the user at `probes.provider.probe_hunyuan_3d_query --job-id <...>`.

### Requirement: Parallel candidates are homogeneous

The system SHALL require `parallel_candidates=True` runs to share a single route (same `chosen_model` + same `_route_pricing`); heterogeneous routes MUST raise explicitly so cost accounting stays faithful.

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
