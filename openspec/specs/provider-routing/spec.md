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

The system SHALL route non-OpenAI protocols via `model.startswith(...)` prefix matching inside dedicated adapters under `src/framework/providers/`.

#### Scenario: qwen/ and hunyuan/ prefixes route to their dedicated adapters via supports() prefix match

- GIVEN `CapabilityRouter` with `QwenMultimodalAdapter` and `HunyuanImageAdapter` registered ahead of the wildcard `LiteLLMAdapter`
- WHEN a request targets a model whose id begins with `qwen/` or `hunyuan/`
- THEN routing reaches the matching dedicated adapter first because `QwenMultimodalAdapter.supports(model)` returns `model.startswith("qwen/")` (`src/framework/providers/qwen_multimodal_adapter.py`) and `HunyuanImageAdapter.supports(model)` returns `model.startswith("hunyuan/")` (`src/framework/providers/hunyuan_tokenhub_adapter.py`); the call therefore bypasses LiteLLM's OpenAI-compatible chat path and uses the protocol-specific submit / poll / download flow built into the dedicated adapter

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
