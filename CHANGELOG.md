# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **TBD-007** `probes/provider/probe_hunyuan_3d_query.py` — read-only /query probe for historical Hunyuan 3D job_ids(opt-in `FORGEUE_PROBE_HUNYUAN_3D=1`,接受 `--job-id` repeated flag);用于失败后查 server 端 job 真实状态,避免 blind retry 双扣
- **TBD-007** `tests/unit/test_mesh_no_silent_retry.py` (4 fences) + `tests/integration/test_mesh_failure_visibility.py` (1 fence)
- Modern Python project layout: `src/framework/` (PEP 621 src layout)
- `src/framework/py.typed` marker — declares package ships type information (PEP 561)
- `tests/conftest.py` centralized: pinned test ModelRegistry + repo-root sys.path + `stub_hydrate_env` fixture
- `[tool.ruff.lint]` balanced rule set (E/F/W/I/B/UP/SIM/RUF) + per-file ignores for tests/probes
- `[tool.ruff.format]` configuration replacing black
- `[tool.mypy]` baseline configuration (non-strict, third-party `ignore_missing_imports`)
- `[tool.coverage]` source/branch/omit/exclude_lines configuration
- `LICENSE` (MIT)
- `.editorconfig` for cross-IDE indent / line-ending / encoding consistency
- `.pre-commit-config.yaml` (ruff check + ruff format + standard hygiene hooks)
- `probes/` package: handler scripts moved out of repo root into `probes/{smoke,provider}/`
- `probes/_output.py` `probe_output_dir(tier, name)` helper for consistent output paths
- `probes/README.md` — probe authoring conventions
- Documentation five-piece set: `docs/{requirements/SRS.md,design/HLD.md,design/LLD.md,testing/test_spec.md,acceptance/acceptance_report.md}`
- `docs/INDEX.md` — documentation entry navigation
- `docs/archive/README.md` — historical document index
- `AGENTS.md` — AI agent collaboration context (mirror of `CLAUDE.md`)

### Changed
- **TBD-007 — mesh 重试塌缩**(Codex 独立 review 协助找出第 4 层): 用户实测 1 个 mesh job 在腾讯云控制台被扣 16 调用 × 20 积分 = 320 积分,根因是 4 层叠加重试(L1 `_apost` transient × L2 `GenerateMeshExecutor` 内部循环 × L3 orchestrator `worker_*` retry × L4 download Range resume)。修法:
  - `mesh_worker._apost` 移除 `with_transient_retry_async` wrapper(L1 拆掉)
  - `GenerateMeshExecutor` 对 `capability_ref="mesh.generation"` 强制 attempts=1(L2 短路)
  - `failure_mode_map` 新增 `mesh_worker_timeout` / `mesh_worker_error` mode → `Decision.abort_or_fallback`,classify 优先匹配 mesh 子类(L3 改路由)
  - `MeshWorkerError` / `MeshWorkerTimeout` 加 `(*, job_id, worker, model)` kwargs;`_atokenhub_*` 失败处填字段
  - `orchestrator` failure_event 写入 `context.{job_id, worker, model}`
  - `framework/run.py` mesh 失败时 stderr 提示用户先跑 `probe_hunyuan_3d_query --job-id <...>` 查 server 端 job 状态(避免双扣已完成 job),再决定 `--resume`
  - HYPOTHESIS 验证(probe_hunyuan_3d_query):abandoned mesh job 后台仍生成完成,blind retry 真双扣
  - 5 条新 fence + 3 条翻转(原"重试 2 次成功" → 现"单次 raise");测试基数 536 → 541
- Bumped `requires-python` from `>=3.11` to `>=3.12` (project actually uses 3.12+ features: `match`/`asyncio.TaskGroup`)
- `--artifact-root` CLI default now auto-buckets by date: `artifacts/<YYYY-MM-DD>`
- All probe scripts now write to `./demo_artifacts/<YYYY-MM-DD>/probes/<tier>/<name>/<HHMMSS>/`
- `[tool.ruff] target-version` bumped to `py312`
- Documentation references updated from `framework/` to `src/framework/` paths
- `claude_unified_architecture_plan_v1.md` moved from `docs/` to `docs/archive/`; demoted from authoritative to historical reference (ADR-005)

### Removed
- `framework/providers/_download.py` (sync download path; only async survives)
- Empty placeholder dirs: `framework/ue_bridge/{execute,plan}/`, `framework/workflows/templates/`
- 9 `probe_*.py` scripts removed from repo root (relocated to `probes/`)

### Fixed
- 21 Codex audit fixes covered by `tests/unit/test_codex_audit_fixes.py` (29 new fence tests)
  - FR-LC-006/007/008: cross-process Artifact metadata persistence + length-mismatch cache miss
  - FR-REVIEW-009: SelectExecutor bare-approve / explicit-reject semantics
  - FR-WORKER-009/010: tokenhub poll timeout clamp + 200/non-JSON wrap as `unsupported_response`
- TBD-006 visual review image compression (acceptance_report §6.5; Codex independent review co-authored).
  Two bugs co-fixed:
  - **Bug A**: `_build_candidates` placed raw image bytes into `CandidateInput.payload`,
    rendered through `json.dumps(default=str)` as `b'\x89PNG\\xNN...'` repr (~4x inflation).
    Now image candidates carry a metadata summary; raw bytes flow only via `image_bytes`.
  - **Bug B**: visual_mode base64-inlined unbounded image_url blocks. New
    `framework.review_engine.image_prep.compress_for_vision` (Pillow + EXIF transpose +
    768px thumbnail + alpha flatten + JPEG q=80) wired into `_attach_image_bytes`,
    raw < 256KB short-circuits to preserve Anthropic small-image path.
  - Pillow added to `[project.optional-dependencies].llm` extras (lazy import).
  - 10 new fences: `tests/unit/test_visual_review_image_compress.py` (8) +
    `tests/unit/test_review_payload_summarization.py` (2)

## [0.1.0] - 2026-04-22

### Added
- Initial baseline: P0–P4 main pipeline, L1–L4 capabilities, F1–F5 runtime features, Plan C async
- 491 passing tests (unit + integration)
- Provider integrations: LiteLLM (OpenAI-compat / Anthropic), DashScope (Qwen), Hunyuan tokenhub (Image + 3D), MiniMax, ComfyUI HTTP, Tripo3D scaffold
- UE Bridge `manifest_only` mode: `UEAssetManifest` + `UEImportPlan` + `Evidence` file contract
- WebSocket progress server (`framework.server.ws_server`)
- `framework.pricing_probe` CLI for provider pricing automation (httpx + playwright backends)

[Unreleased]: https://example.com/releases/unreleased
[0.1.0]: https://example.com/releases/0.1.0
