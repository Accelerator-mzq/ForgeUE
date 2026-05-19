# Plan: provider-routing — Task 4 Scenarios needing addition

> 从 cleanup-main-spec-scenarios skeleton 移出(2026-04-25);保留为 Task 4 实装清单。Task 4 启动时把以下 Plan 转为正式 `openspec/changes/cleanup-main-spec-scenarios/specs/provider-routing/spec.md` 的 `## MODIFIED Requirements` 块。本 cleanup 中**最大**份,16 个 Requirement。**不**新增 Requirement,**不**改 Requirement 标题。

## Plan: Requirements needing Scenario

### Three-section ModelRegistry is the single source
- 标记:[Min 1]
- 现状:主 spec line 31;providers + models + aliases 三段式 YAML
- Scenario 草案:"Loader expands `models_ref` via ModelRegistry alias section"
- 真源:`config/models.yaml`、`src/framework/providers/model_registry.py`

### Alias reference expansion in the loader
- 标记:[Min 1]
- 现状:主 spec line 35
- Scenario 草案:"Bundle alias `text_cheap` resolves to `qwen-turbo` route via models.yaml"
- 真源:`src/framework/workflows/loader.py`

### OpenAI-compatible endpoints add zero code
- 标记:[Min 1]
- 现状:主 spec line 39;OpenAI 兼容端口在 registry 填 `api_base` + `api_key_env`,bundle 写 `openai/<id>`
- Scenario 草案:"Adding new OpenAI-compatible vendor requires only registry entry, no adapter code"
- 真源:`config/models.yaml`、`src/framework/providers/litellm_adapter.py`

### Non-OpenAI protocols ship dedicated adapters
- 标记:[Min 1]
- 现状:主 spec line 43
- Scenario 草案:"`hunyuan/<id>` model routes to `HunyuanAdapter` via prefix match"
- 真源:`src/framework/providers/{capability_router,hunyuan_adapter}.py`

### Capability aliases drive provider selection
- 标记:[Min 1]
- 现状:主 spec line 57
- Scenario 草案:"`image.text_to_image` capability alias selects `qwen-vl-max` provider per registry"
- 真源:`src/framework/providers/capability_router.py`、`config/models.yaml`

### Route pricing is stashed on every ProviderResult
- 标记:[Min 1]
- 现状:主 spec line 61
- Scenario 草案:"Every `ProviderResult.usage.cost_usd` matches the registry route price for its model"
- 真源:`src/framework/providers/litellm_adapter.py`、`tests/unit/test_review_budget.py`

### Pricing probe defaults to dry-run
- 标记:[+1]
- 现状:主 spec line 65
- Scenario 草案:
  - "`pricing_probe` without `--apply` leaves `config/models.yaml` untouched"
  - "`pricing_probe --apply` writes a snapshot under `demo_artifacts/<date>/pricing/<HHMMSS>/`"
- 真源:`src/framework/pricing_probe/cli.py`

### External factual pricing requires a verifiable source
- 标记:[Min 1]
- 现状:主 spec line 69;ADR-004
- Scenario 草案:"Pricing entry without `sourced_on` field is rejected by registry validator"
- 真源:`src/framework/pricing_probe/{validator,writer}.py`、`config/models.yaml`

### URL-rank fallthrough for mesh worker
- 标记:[Min 1]
- 现状:主 spec line 73
- Scenario 草案:"Mesh worker tries URLs in registry rank order; first non-error URL wins"
- 真源:`src/framework/providers/workers/mesh_worker.py::_one`、LLD §16.3

### Range-resume integrity
- 标记:[Min 1]
- 现状:主 spec line 77
- Scenario 草案:"Partial download resumes from byte offset; final hash equals full file hash"
- 真源:`src/framework/providers/_download_async.py::chunked_download_async`、`tests/unit/test_download_async.py`

### Magic-bytes format gate
- 标记:[Min 1]
- 现状:主 spec line 81
- Scenario 草案:"URL declared as `.glb` with `.obj` magic bytes is rejected by `_build_candidate`"
- 真源:`src/framework/providers/workers/mesh_worker.py::_build_candidate`、LLD §16.4

### Case-insensitive data: URI
- 标记:[Min 1]
- 现状:主 spec line 85
- Scenario 草案:"`data:Image/PNG;...` is treated identical to `data:image/png;...`"
- 真源:`src/framework/providers/_download_async.py`

### tokenhub poll timeout is clamped
- 标记:[Min 1]
- 现状:主 spec line 89
- Scenario 草案:"Server-quoted poll timeout above ceiling is clamped to the project-wide max"
- 真源:`src/framework/providers/workers/mesh_worker.py`、`tests/unit/test_codex_audit_fixes.py`(FR-WORKER-009 fence)

### HTML-body pollution wraps as unsupported
- 标记:[Min 1]
- 现状:主 spec line 93
- Scenario 草案:"`200 OK` response with HTML body is wrapped as `unsupported_response` failure mode"
- 真源:`src/framework/providers/workers/mesh_worker.py`、`tests/unit/test_codex_audit_fixes.py`(FR-WORKER-010 fence)

### Premium-API single-attempt guard
- 标记:[Min 1]
- 现状:主 spec line 97;ADR-007
- Scenario 草案:"`mesh.generation` 502 surfaces `job_id` to caller, framework does NOT issue a second attempt"
- 真源:`src/framework/runtime/{executors/generate_mesh,failure_mode_map}.py`、`tests/unit/test_mesh_no_silent_retry.py`

### Parallel candidates are homogeneous
- 标记:[Min 1]
- 现状:主 spec line 101
- Scenario 草案:"`parallel_candidates=3` issues 3 calls to the same provider with identical params"
- 真源:`src/framework/runtime/scheduler.py`、`tests/unit/test_codex_audit_fixes.py`(FR-COST-009 fence)
