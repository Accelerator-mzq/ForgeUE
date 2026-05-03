# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **ForgeUE Integrated AI Change Workflow**(2026-04-27,OpenSpec change `fuse-openspec-superpowers-workflow`):
  - 中心化融合 OpenSpec(契约锚点)× Superpowers(evidence 生成器)× codex-plugin-cc(stage cross-review hook)三方工作流。OpenSpec change artifact 是唯一规范源,evidence 服务于契约,实施暴露的契约漏洞必须回写。
  - 8 个 Claude slash 命令:`/forgeue:change-{status,plan,apply,debug,verify,review,doc-sync,finish}`,每个对应 S0-S9 状态机的某个 stage,内部按需触发 Superpowers skill + codex `/codex:*` review hook + writeback 检测。
  - 5 个 stdlib-only Python 工具:`tools/forgeue_env_detect.py`(5 层 env 检测 + plugin 可用性启发式)/ `forgeue_change_state.py`(state 推断 + `--writeback-check` 4 类 named DRIFT 检测,回写检测主力)/ `forgeue_verify.py`(Level 0/1/2 编排,产 verify_report.md)/ `forgeue_doc_sync_check.py`(10 文档静态扫,标 [REQUIRED]/[OPTIONAL]/[SKIP]/[DRIFT])/ `forgeue_finish_gate.py`(中心化最后防线,evidence 完整性 + 12-key frontmatter + cross-check + writeback 真实性)。
  - 2 个 ForgeUE skills:`.claude/skills/forgeue-integrated-change-workflow/`(中心化编排器主 skill)与 `.claude/skills/forgeue-doc-sync-gate/`(Sync Gate 编排)。
  - 1 个 OpenSpec spec delta:`openspec/specs/examples-and-acceptance/spec.md` ADDED Requirement「Active change evidence is captured under OpenSpec change subdirectories with writeback protocol」(3 scenarios;P9 archive 时由 `/opsx:archive` sync-specs 合入主 spec)。
  - 1 份合并主文档:`docs/ai_workflow/forgeue_integrated_ai_workflow.md`(4 section — fusion contract / agent phase gate policy / documentation sync gate / state machine + writeback);`docs/ai_workflow/README.md` §5 / §8 同步更新表格描述。
  - 12-key audit frontmatter 协议(11 audit + 1 wrapper):每份 formal evidence 必含 `change_id` / `stage` / `evidence_type` / `contract_refs` / `aligned_with_contract` / `detected_env` / `triggered_by` / `codex_plugin_available` 8 个 always-required key,`drift_decision` / `writeback_commit` / `drift_reason` / `reasoning_notes_anchor` 4 个 conditional key 在 `aligned_with_contract: false` 时必填。
  - 4 类 DRIFT taxonomy:`evidence_introduces_decision_not_in_contract` / `evidence_references_missing_anchor` / `evidence_contradicts_contract` / `evidence_exposes_contract_gap`;由 `forgeue_change_state.py --writeback-check` exit 5 触发。
  - 工作流内禁令:不调 `/codex:rescue`(单点修复 helper,与 stage gate 协议正交);不启 codex review-gate hook(stage gate 与 review-gate 重复且常冲突,由 `forgeue_finish_gate` WARN 提示);不让 evidence 取代 contract 作规范源。
  - 测试覆盖:262 P4 fence(`tests/unit/test_forgeue_*.py`)+ 13 P4 codex-review fixup fence(diff_engine stable-key + finish_gate 8 always-required key + env_detect SSE_PORT + doc_sync_check non-core detection)+ 3 P5 verify subprocess env fence(PYTHONPATH=src 注入)= pytest baseline 1126(848 P3 + 278)。
- **Run Comparison / 基线回归**(2026-04-25,OpenSpec change `add-run-comparison-baseline-regression`):
  - 新增模块 `src/framework/comparison/`,含 `models.py`(`RunComparisonInput` / `ArtifactDiff` / `VerdictDiff` / `MetricDiff` / `StepDiff` / `RunComparisonReport`,`schema_version="1"`)/ `loader.py`(只读消费,异常族 `RunDirNotFound` / `RunDirAmbiguous` / `RunSnapshotCorrupt` / `PayloadMissingOnDisk`)/ `diff_engine.py`(纯函数 `compare()`,sparse `summary_counts`)/ `reporter.py`(`render_json` + `render_markdown` + `write_reports`,固定文件名 `comparison_report.json` + `comparison_summary.md`,ASCII-only)/ `cli.py` + `__main__.py`(CLI 入口)。
  - CLI 入口:`python -m framework.comparison --artifact-root <root> --baseline-run <id_a> --candidate-run <id_b> [--output-dir <out>]`。Exit codes 0 / 2(RunDir 定位失败 / schema 损坏)/ 3(strict 模式 payload 缺失)/ 1(其他未识别异常)。`--no-hash-check` / `--non-strict` / `--json-only` / `--markdown-only` / `--quiet` flags 均见 `--help`。
  - 离线 fixture:`tests/fixtures/comparison/builders.py::build_fixture_pair(root)` deterministic 构造 baseline / candidate run 目录(覆盖 unchanged / content_changed / metadata_only ArtifactDiff + run-level cost_usd MetricDiff + lineage_delta `transformation_kind`)。
  - 测试覆盖:`tests/unit/test_run_comparison_{models,loader,diff_engine,reporter,cli}.py`(共 ~295 unit 用例)+ `tests/integration/test_run_comparison_cli.py`(4 用例,含 happy path、不污染 `<repo>/demo_artifacts/` 递归快照、lineage diff 端到端、`examples/mock_linear.json` + FakeAdapter 双跑离线集成)。pytest -q 实测 848 通过(基线 549 + Run Comparison ~299)。
  - Codex Review Gate 双轮 PASS(Task 4 / 5 / 6 各两轮);Task 5 第一轮捕获 stdout/stderr ASCII-safe Blocker(由 `_console_safe` + 13 个新测试解决);Task 6 第一轮捕获 spec validation gate 缺失 Blocker(由 FakeAdapter 双跑 + `_snapshot_tree` 递归解决)。
  - **Deferred follow-up**:`lazy-artifact-store-package-exports`(尚未创建 OpenSpec change)。Task 5 实装时发现 `framework.comparison.loader` 顶层 `from framework.artifact_store.hashing import ...` 必然触发 `framework/artifact_store/__init__.py` 执行,而该 `__init__` 当前 eager-import `repository` / `payload_backends`,导致这两个模块作为 transitive 出现在 `sys.modules` 里。当前 fence 与 Task 2 loader fence 对齐(只锁 9 个执行链路前缀);**未**修改 `artifact_store/__init__.py`,跨子系统改动留后续独立 change 评估 PEP 562 lazy export 方案。详见 `openspec/changes/add-run-comparison-baseline-regression/tasks.md` §"Deferred Follow-ups"。
- **TBD-008**(Codex B+C 分层)`tests/fixtures/review_images/` 目录 + `tavern_door_v{1,2,3}.png` 真 Qwen PNG 加上 `tests/fixtures/__init__.py.load_review_image()` helper,供视觉 review 测试复用;repo 增 ~4.4MB(一次性)
- **TBD-008** `probes/provider/probe_visual_review.py` — opt-in `FORGEUE_PROBE_VISUAL_REVIEW=1` probe,对比 `review_judge`(Anthropic Opus 4.6)vs `review_judge_visual`(GLM-4.6V)对同 3 张真图的打分分布,落 `comparison_table.md`;首跑确认 Anthropic 判别度更高(0.62-0.88 跨度),GLM 打分更压缩(0.80-0.95)
- **TBD-008** `tests/integration/test_l4_image_to_3d.py` 新增 2 条 fence(Codex Phase G 两轮 review 后):
  - `test_l4_mesh_reads_selected_candidate_from_review_verdict` — **真实生产路径**,验证 mesh 从 `report.verdict.selected_candidate_ids[0]` 读图
  - `test_l4_mesh_resolves_selected_image_from_selected_set_bundle` — forward-compat,守 SelectExecutor 流程的 `bundle.selected_set` 路径
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
- **TBD-008 — visual review 契约 / 质量分层**(Codex 独立 review 指出盲区 + 采纳 B+C 分层):
  - `tests/integration/test_p2_standalone_review.py::test_p2_visual_mode_attaches_image_bytes_to_judge_prompt` 升级:`VISUAL_A/B/C` 伪字节 → fixture 真 PNG;FakeAdapter 打分从 "按位置" 改为 "按 candidate_id" 映射;新增 winner/confidence 断言 + JPEG 压缩路径断言
  - `tests/integration/test_p3_production_pipeline.py` 升级:`ORIGINAL_` / `REVISED_` / `API_` / `OK` prefix 伪字节 → fixture 真 PNG;revise + api_path + worker_timeout 三条路径全走真 PNG;原有断言保留
  - `tests/integration/test_l4_image_to_3d.py::_seed_image_artifact` helper 升级:`fake-source-image-bytes` → fixture 真 PNG;所有 L4 mesh 测试自动受益
  - `a2_image` / `a2_review` bundle 的"视觉 review 证据力"在 `docs/acceptance/acceptance_report.md` §6.2 修订:明确标为 "text-only / schema smoke",真视觉证据在 `test_p2/p3/l4` integration + `probe_visual_review.py`
  - `src/framework/runtime/executors/generate_mesh.py::_resolve_source_image` 优先级重写(Codex Phase G R1+R2):**verdict > selected_set > 直接 image > candidate_set**。之前扁平 image 优先导致真实 workflow 静默取 cand_0 无视 review verdict;本次修复让 mesh 读 verdict 选中的候选
  - 测试基数 541 → 543(2 新 fence + 3 翻转不变数)
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
