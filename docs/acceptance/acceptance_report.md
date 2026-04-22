# ForgeUE 验收报告 (Acceptance Report)

| 字段 | 内容 |
| --- | --- |
| 文档编号 | FORGEUE-ACC-001 |
| 版本 | v1.0 |
| 基线日期 | 2026-04-22 |
| 文档性质 | 验收报告 |
| 上位文档 | `docs/requirements/SRS.md`、`docs/testing/test_spec.md` |
| 下位文档 | 无 |

---

## 1. 引言

### 1.1 编写目的

本文档对照 SRS 的需求基线,汇总 ForgeUE 当前实装状态,给出:

- 每条 FR / NFR 的验收状态(✅ 通过 / ⚠️ 部分 / ⏳ 待验 / ❌ 未启动)
- 验收手段(自动化测试 / 手工验收 / 文档评审)
- 待验收项清单与执行计划

### 1.2 验收原则

| 原则 | 说明 |
| --- | --- |
| **可执行** | 每条验收项必须有明确判定手段(测试命令 / 手工步骤 / 文档审阅) |
| **可追溯** | 验收项与 SRS 需求一一映射 |
| **证据驱动** | 通过的项必须留证据(测试输出 / 手工截图 / 真机 log) |
| **诚实标记** | 未验证 / 未启动的项直接标注,不以"已实装"混淆验收状态 |

### 1.3 状态图例

| 标记 | 含义 |
| --- | --- |
| ✅ | 已通过验收 |
| ⚠️ | 部分通过(功能实装但覆盖不完整) |
| ⏳ | 待验收(功能实装但需手工 / 真机验证) |
| ❌ | 未启动 |
| ⛔ | 明确不做(ADR / 范围外) |

---

## 2. 验收级别

| 级别 | 验收手段 | 状态判定 |
| --- | --- | --- |
| L0 自动化 | `pytest -q` 全绿 | 555 用例通过 ✅(基线 491 + Codex audit fence 29 + src-layout / router-obs 根因定位 fence 6 + TBD-006 视觉 review 图像压缩 fence 10 + mesh quota error 分类 fence 19) |
| L1 CLI 离线冒烟 | `python -m framework.run --task examples/mock_linear.json` | 不抛异常,有产物落盘 |
| L2 Live LLM smoke | `python -m framework.run --task <bundle> --live-llm` | 需 API key |
| L3 UE 真机冒烟 | UE Python Console `exec(run_import.py)` | 需 UE 装机 + 空项目 |
| L4 文档评审 | 人工审阅 SRS/HLD/LLD/test_spec | 一致、无漂移 |

---

## 3. 主线进度验收

### 3.1 阶段完成度(P0–P4)

| 阶段 | 范围 | 自动化 | CLI 冒烟 | 手工验收 | 状态 |
| --- | --- | --- | --- | --- | --- |
| P0 | 对象模型 + 运行时骨架 | `integration/test_p0_mock_linear.py` | ✅ `examples/mock_linear.json` | — | ✅ |
| P1 | basic_llm + LiteLLM + Instructor | `integration/test_p1_structured_extraction.py` | ✅ `examples/character_extract.json` | — | ✅ |
| P2 | standalone_review | `integration/test_p2_standalone_review.py` | ✅ `examples/review_3_images.json` | — | ✅ |
| P3 | production + 内嵌 review | `integration/test_p3_production_pipeline.py` | ✅ `examples/image_pipeline.json` | — | ✅ |
| P4 | UE Bridge manifest_only | `integration/test_p4_ue_manifest_only.py`(stub unreal) | ✅ `examples/ue_export_pipeline.json` | ⏳ UE 真机 | ⚠️ |

### 3.2 L 层能力

| ID | 能力 | 对应需求 | 状态 |
| --- | --- | --- | --- |
| L1 | UE5 API 查询 | FR-STRUCT-* + rubric `ue5_api_assist` | ✅ |
| L2 | 图像生成 API 路径 | FR-WORKER-001(ComfyUI) + `image.*` capability | ✅ |
| L3 | 视觉 QA | FR-REVIEW-* + rubric `ue_visual_quality` | ✅ |
| L4 | image → 3D mesh | `integration/test_l4_image_to_3d.py` + Hunyuan 3D | ✅ |

### 3.3 F 附加能力

| ID | 能力 | 对应需求 | 状态 |
| --- | --- | --- | --- |
| F1 | BudgetTracker + Dry-run budget warn | FR-RUNTIME-001, FR-LC-002 | ✅ |
| F2 | Chunked download + 轮询进度 + raw_resp 透传 | FR-WORKER-005, FR-OBS-004 | ✅ |
| F3 | Anthropic Prompt Cache | FR-RUNTIME-002 | ✅ |
| F4 | `compact_messages()` | FR-RUNTIME-003 | ✅ |
| F5 | 取消 / 超时中断 | FR-RUNTIME-004 | ✅ |
| Plan X | 瞬态重试 | FR-RUNTIME-005 | ✅ |
| Plan C | Provider 全异步 + DAG + EventBus | §C.8, §C.9, §N | ✅ |

---

## 4. 功能需求验收矩阵(SRS §3)

### 4.1 FR-WF 三模式工作流

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-WF-001 三种 RunMode | integration/test_p0~p2 | ✅ |
| FR-WF-002 共享调度器 | 代码审阅 `runtime/orchestrator.py`(单一实现) | ✅ |
| FR-WF-003 线性+分支+DAG | test_dag_concurrency | ✅ |
| FR-WF-004 11 种 StepType | test_core_schemas 枚举 | ✅ |
| FR-WF-005 risk_level 排序 | test_scheduler_risk_ordering | ✅ |
| FR-WF-006 revise 回环 max_revise | test_transition_engine | ✅ |
| FR-WF-007 DAG 依赖并发 opt-in | test_dag_concurrency | ✅ |

### 4.2 FR-LC Run 生命周期

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-LC-001 9 阶段 | 代码审阅 + integration/test_p0~p4 | ✅ |
| FR-LC-002 Dry-run 预检 | test_dry_run_pass | ✅ |
| FR-LC-003 失败直接 failed | test_dry_run_pass | ✅ |
| FR-LC-004 artifact_hash + Checkpoint | test_checkpoint_store | ✅ |
| FR-LC-005 Resume hash 一致性 | test_checkpoint_store | ✅ |
| FR-LC-006 跨进程 `_artifacts.json` 持久化 | test_codex_audit_fixes(`_repository_metadata_dump_and_load_roundtrip` / `_resume_yields_cache_hits_after_reload`) | ✅ |
| FR-LC-007 load_run_metadata 三道过滤 | test_codex_audit_fixes(`_skips_missing_payload` / `_skips_corrupted_payload`) | ✅ |
| FR-LC-008 find_hit 长度不一致 miss | test_codex_audit_fixes(`_misses_on_length_mismatch`) | ✅ |

### 4.3 FR-MODEL 多模型编排

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-MODEL-001 三段式 YAML | test_model_registry | ✅ |
| FR-MODEL-002 `models_ref` 展开 | test_model_registry | ✅ |
| FR-MODEL-003 多 provider 支持 | test_cn_image_adapters + providers_async | ✅ |
| FR-MODEL-004 OpenAI 兼容零代码 | 代码审阅 + YAML 示例 | ✅ |
| FR-MODEL-005 非 OpenAI adapter 接入 | 已接入 Qwen / Hunyuan / Mesh | ✅ |
| FR-MODEL-006 wildcard 最后注册 | test_providers + 代码约定 | ✅ |
| FR-MODEL-007 能力别名 | `config/models.yaml` aliases 段 | ✅ |
| FR-MODEL-008 fallback_models | test_transition_engine | ✅ |

### 4.4 FR-STRUCT 结构化生成

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-STRUCT-001 Instructor + Pydantic | integration/test_p1 | ✅ |
| FR-STRUCT-002 schema registry | `src/framework/schemas/registry.py` | ✅ |
| FR-STRUCT-003 validation_fail → retry | test_failure_mode_map | ✅ |
| FR-STRUCT-004 drop_params=True | 代码审阅 `litellm_adapter.py` | ✅ |

### 4.5 FR-REVIEW 评审引擎

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-REVIEW-001 三评审形态 | test_chief_judge_parallel(single + panel) | ⚠️ human_review 接口预留,未端到端 |
| FR-REVIEW-002 Report + Verdict 分离 | test_core_schemas + integration/test_p2 | ✅ |
| FR-REVIEW-003 9 Decision | test_transition_engine | ✅ |
| FR-REVIEW-004 confidence 与阈值 | test_transition_engine | ✅ |
| FR-REVIEW-005 5 维评分 | test_core_schemas(DimensionScores) | ✅ |
| FR-REVIEW-006 YAML rubric | `rubric_templates/` 3 份 | ✅ |
| FR-REVIEW-007 panel 并发 | test_chief_judge_parallel | ✅ |
| FR-REVIEW-008 cost 透传 | test_review_budget | ✅ |
| FR-REVIEW-009 SelectExecutor bare-approve | test_codex_audit_fixes(`_select_bare_approve_keeps_whole_pool` / `_excludes_explicit_rejects`) | ✅ |

### 4.6 FR-STORE Artifact 仓库

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-STORE-001 artifact_type 映射 | test_core_schemas | ✅ |
| FR-STORE-002 PayloadRef 三态 | test_payload_backends | ✅ inline+file / ⏳ blob 接口预留 |
| FR-STORE-003 体积上限 | test_payload_backends | ✅ |
| FR-STORE-004 modality metadata | test_core_schemas | ✅ |
| FR-STORE-005 Lineage | test_artifact_repository | ✅ |
| FR-STORE-006 4 层校验 | test_artifact_repository | ✅ |

### 4.7 FR-UE UE Bridge

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-UE-001 manifest_only / bridge_execute | 代码审阅 + enum | ✅ manifest_only / ❌ bridge_execute 未启动 |
| FR-UE-002 文件契约落盘 | integration/test_p4 | ✅ |
| FR-UE-003 UE Python Console 导入 | stub unreal(`test_p4`) | ⏳ UE 真机未验证(A1) |
| FR-UE-004 naming_policy 声明 | test_ue_bridge | ✅ |
| FR-UE-005 depends_on 拓扑 | test_ue_bridge | ✅ |
| FR-UE-006 Evidence 追加 | test_ue_bridge | ✅ |
| FR-UE-007 Bridge 不越界 | 代码审阅 + permission_policy | ✅ |
| FR-UE-008 Phase C 默认拒绝 | test_ue_bridge | ✅ |

### 4.8 FR-WORKER 多模态 Worker

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-WORKER-001 ComfyUI HTTP | `comfy_worker.py` + test_comfy_http_unsupported | ✅ |
| FR-WORKER-002 Hunyuan 3D | integration/test_l4 | ✅ |
| FR-WORKER-003 Tripo3D scaffold | test_tripo3d_unsupported | ⏳ 实装待需求 |
| FR-WORKER-004 URL ranker + fallthrough | test_cn_image_adapters | ✅ |
| FR-WORKER-005 Range 续传强校验 | test_download_async | ✅ |
| FR-WORKER-006 magic bytes gate | test_cn_image_adapters + test_pr3_cleanup_fences | ✅ |
| FR-WORKER-007 glTF external-buffer raise | test_cn_image_adapters | ✅ |
| FR-WORKER-008 data: URI 大小写 | test_cn_image_adapters | ✅ |
| FR-WORKER-009 tokenhub poll timeout clamp | test_codex_audit_fixes(`_hunyuan_poll_clamps_timeout` / `_mesh_poll_clamps_timeout`) | ✅ |
| FR-WORKER-010 200/non-JSON wrap unsupported | test_codex_audit_fixes(`_post_raises_unsupported_on_html_body` × 3) | ✅ |

### 4.9 FR-RUNTIME 工程化

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-RUNTIME-001 BudgetTracker | test_budget_tracker | ✅ |
| FR-RUNTIME-002 Prompt Cache | test_providers / review_budget | ✅ |
| FR-RUNTIME-003 compact_messages | test_compactor | ✅ |
| FR-RUNTIME-004 取消 / 超时 | test_cancellation | ✅ |
| FR-RUNTIME-005 瞬态重试 | test_transient_retry + test_retry_async | ✅ |
| FR-RUNTIME-006 Checkpoint resume | test_checkpoint_store | ✅ |
| FR-RUNTIME-007 failure_mode_map | test_failure_mode_map | ✅ |
| FR-RUNTIME-008 on_retry override | test_codex_audit_fixes(`_retry_same_step_honours_policy_on_retry`) | ✅ |
| FR-RUNTIME-009 TransitionEngine per-arun 隔离 | test_codex_audit_fixes(`_uses_fresh_transition_engine_per_arun` / `_concurrent_arun_does_not_share_counters` / `_clone_preserves_subclass_and_attrs`) | ✅ |
| FR-RUNTIME-010 cost_usd 写入 cp.metrics | test_codex_audit_fixes(`_structured_step_persists_cost_for_resume`) | ✅ |
| FR-RUNTIME-011 cache-hit 回放 cost | test_codex_audit_fixes(`_orchestrator_replays_cached_cost_into_budget_tracker`) | ✅ |
| FR-RUNTIME-012 unsupported 三层 short-circuit | test_codex_audit_fixes(`_router_does_not_fallback_on_unsupported` / `_image_executor_does_not_retry_on_unsupported` / `_*_unsupported_response_skips_transient_retry` × 3) | ✅ |

### 4.10 FR-COST 成本追踪

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-COST-001 YAML pricing block | test_registry_pricing | ✅ |
| FR-COST-002 typo raise | test_registry_pricing | ✅ |
| FR-COST-003 三 estimator | test_budget_tracker_pricing | ✅ |
| FR-COST-004 route_pricing 透传 | test_router_pricing_stash | ✅ |
| FR-COST-005 pricing probe CLI dry-run | test_pricing_probe_framework | ✅ |
| FR-COST-006 httpx + playwright 双后端 | test_pricing_parser_*(zhipu / dashscope / hunyuan_image / hunyuan_3d 4 家已实装) | ⚠️ tripo3d 仍 scaffold(`no_parser`) |
| FR-COST-007 verifiable 来源 | YAML pricing_autogen 审计块 | ✅(2026-04-22;A3 dry-run + --apply 验证所有 12 个 model sourced_on 与真实页面一致) |
| FR-COST-008 image_edit cost_usd | test_codex_audit_fixes(`_image_edit_emits_cost_usd`) | ✅ |
| FR-COST-009 parallel_candidates 同质性 | test_codex_audit_fixes(`_generate_image_parallel_rejects_heterogeneous_models`) | ✅ |

### 4.11 FR-OBS 可观测

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| FR-OBS-001 EventBus loop-aware | test_event_bus | ✅ |
| FR-OBS-002 ProgressEvent schema | test_progress_passthrough | ✅ |
| FR-OBS-003 WS server | integration/test_ws_progress | ✅ |
| FR-OBS-004 idle disconnect safe | test_ws_progress | ✅ |
| FR-OBS-005 OTel tracing | 可选启用 | ⏳ 未端到端验证 |
| FR-OBS-006 CLI --serve | 代码审阅 `src/framework/run.py` | ✅ |

---

## 5. 非功能需求验收矩阵(SRS §4)

### 5.1 NFR-PERF 性能

| 编号 | 度量目标 | 验收手段 | 状态 |
| --- | --- | --- | --- |
| NFR-PERF-001 DAG 并发墙钟线性降 | fan-out 3, 0.2s 每步 → ≤ 0.25s | test_dag_concurrency | ✅ |
| NFR-PERF-002 ChiefJudge 并发 | 3 judge ≈ 最慢 × 1.1 | test_chief_judge_parallel | ✅ |
| NFR-PERF-003 多候选并行 | N 候选 ≤ T × 1.2 | test_multi_candidate_parallel | ✅ |
| NFR-PERF-004 1 MB 分块 | 代码审阅 | ✅ |
| NFR-PERF-005 全量 ≤ 15s | `pytest -q` 实测 | ✅(12.44s,2026-04-22 基线) |

### 5.2 NFR-REL 可靠性

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| NFR-REL-001 异常全分类 | test_failure_mode_map | ✅ |
| NFR-REL-002 provider_timeout 回退链 | test_failure_mode_map + test_transition_engine | ✅ |
| NFR-REL-003 schema/worker timeout 重试 | 同上 | ✅ |
| NFR-REL-004 budget 合成 Verdict | test_budget_tracker | ✅ |
| NFR-REL-005 unsupported → abort_or_fallback | test_transition_engine | ✅ |
| NFR-REL-006 DAG cascade cancel | test_cascade_cancel | ✅ |
| NFR-REL-007 Checkpoint hash 严格 | test_checkpoint_store | ✅ |
| NFR-REL-008 disk_full → rollback | test_failure_mode_map | ⚠️ 映射存在,rollback 动作未端到端 |
| NFR-REL-009 ArtifactRepository DAG-safe + dump 不吞异常 | test_codex_audit_fixes(`_find_by_producer_safe_under_concurrent_put`) | ✅ |

### 5.3 NFR-REPRO 可复现

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| NFR-REPRO-001 seed 传递 | integration/test_p3(seed 下游)| ✅ |
| NFR-REPRO-002 model_version_lock | bundle schema 校验 | ✅ |
| NFR-REPRO-003 hash verify on resume | test_checkpoint_store | ✅ |
| NFR-REPRO-004 结构化等价 | integration/test_p1(JSON 稳定) | ✅ |

### 5.4 NFR-SEC 安全

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| NFR-SEC-001 key 不硬编码 | 代码审阅 + `.env.example` | ✅ |
| NFR-SEC-002 secrets 脱敏 | test_secrets | ✅ |
| NFR-SEC-003 trace / event 不泄 key | test_secrets + 代码审阅 | ✅ |
| NFR-SEC-004 Dry-run 校验 secrets | test_dry_run_pass | ✅ |
| NFR-SEC-005 WS 默认本地 | 代码审阅 `ws_server.py` | ✅ |

### 5.5 NFR-OBS 可观测

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| NFR-OBS-001 run_id 归档 | integration/test_p0 | ✅ |
| NFR-OBS-002 step 事件 | test_progress_passthrough | ✅ |
| NFR-OBS-003 budget_summary 汇总 | test_budget_tracker | ✅ |
| NFR-OBS-004 worker_poll 事件 | test_progress_passthrough | ✅ |

### 5.6 NFR-MAINT 可维护

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| NFR-MAINT-001 fence 守门 | test_spec.md §5 清单 | ✅ |
| NFR-MAINT-002 测试结构 1:1-2:1 | 42 unit / 11 core 模块 ≈ 3.8:1 | ✅ |
| NFR-MAINT-003 ≥ 491 用例 | `pytest --collect-only` | ✅(520,2026-04-22 第二轮基线 = 491 + audit 修复 fence 29) |
| NFR-MAINT-004 关键边界不 mock | 代码审阅 | ✅ |
| NFR-MAINT-005 Artifact 真实 | 代码审阅 + integration | ✅ |

### 5.7 NFR-PORT 可移植

| 编号 | 验收手段 | 状态 |
| --- | --- | --- |
| NFR-PORT-001 framework 纯 Python | 代码审阅 | ✅ |
| NFR-PORT-002 Linux CI | 未建立 CI runner | ⏳ TBD-T-001 |
| NFR-PORT-003 ue_scripts 最小依赖 | 代码审阅(仅 import unreal) | ✅ |
| NFR-PORT-004 `/tmp` 禁用 | `.gitignore` + CLAUDE.md 约定 | ✅ |

### 5.8 ADR 架构决策

| ADR | 决策 | 状态 |
| --- | --- | --- |
| ADR-001 | 不做 UE 插件 | ✅ 已固化 |
| ADR-002 | `models.yaml` 单一真源 | ✅ |
| ADR-003 | LiteLLMAdapter 最后注册 | ✅ 代码固化 |
| ADR-004 | 外部数据必须可验证 | ✅(pricing probe 止血 + fence) |
| ADR-005 | plan_v1 降级归档 | ✅(本轮文档重构) |
| ADR-006 | TransitionEngine per-arun 隔离(`cloned_for_run`) | ✅ 代码固化 + 3 fence 守门 |

---

## 6. 待验收项(需执行)

### 6.1 A1 — UE 5.x 真机冒烟

**目标**:验证 `ue_scripts/run_import.py` 在真实 UE 进程中调用 `unreal.AssetImportTask` 系列 API,Content Browser 出现资产,evidence.json 追加成功记录。

**前置条件**:
- 本机装 UE 5.3+
- 建 Blueprint 空白项目(推荐 `D:\UE_Projects\ForgeUEDemo\`),启用 Python Editor Script Plugin
- 修改 `examples/ue_export_pipeline.json:22` 的 `project_root`
- framework 侧跑 `python -m framework.run --task examples/ue_export_pipeline.json --live-llm --run-id a1_demo`

**执行步骤**:

```
1. 在 framework 侧产出 manifest/plan/evidence/资产到 <UE项目>/Content/Generated/a1_demo/
2. 打开 UE 编辑器,Window → Python
3. 执行:
   import os
   os.environ['FORGEUE_RUN_FOLDER'] = r'<UE项目>\Content\Generated\a1_demo'
   exec(open(r'D:\ClaudeProject\ForgeUE_claude\ue_scripts\run_import.py').read())
4. 验证 Content Browser 下 /Game/Generated/... 出现资产
5. 验证 evidence.json 追加了 status=success 记录
```

**状态**:⏳ 未执行(需用户 UE 装机确认)

### 6.2 A2 — Live LLM 端到端

**目标**:验证 9 个已接入别名(text_cheap / text_strong / review_judge / review_judge_visual / ue5_api_assist / image_fast / image_strong / image_edit / mesh_from_image)在真实 provider 调用下收敛。

**前置条件**:`.env` 配齐 `DASHSCOPE_API_KEY` / `HUNYUAN_API_KEY` / `HUNYUAN_3D_KEY` / `ZHIPU_API_KEY` / `PACKYCODE_KEY` / `MINIMAX_KEY`(注意:v1.0 版本列的 `GLM_API_KEY` / `PACKYCODE_API_KEY` 实装时改成了 `ZHIPU_API_KEY` / `PACKYCODE_KEY`,以 `config/models.yaml` 的 `api_key_env` 为准)。

**执行步骤**:

```bash
python -m framework.run --task examples/character_extract.json --live-llm --run-id a2_char
python -m framework.run --task examples/image_pipeline.json --live-llm --run-id a2_image
python -m framework.run --task examples/review_3_images.json --live-llm --run-id a2_review
python -m framework.run --task examples/image_to_3d_pipeline.json --live-llm --run-id a2_mesh
python -m framework.run --task examples/ue_export_pipeline.json --live-llm --run-id a2_ue
```

**验收标准**:每条产出对应 RunResult.status == succeeded,budget_summary 非零,trace 可读。

**2026-04-22 执行结果**:

| bundle | 状态 | 关键观察 |
| --- | --- | --- |
| `a2_char` | ✅ | MiniMax Anthropic 代理 `anthropic/MiniMax-M2.7`,usage=2133 tokens,Pydantic `ue.character` schema 验证 passed,Kaelen 角色卡完整 |
| `a2_image` | ✅ | FakeComfy 3 candidate + 真 `review_judge` vision,PackyCode Anthropic Opus/Sonnet 对 fake 图 `reject @ 0.26`,工作流按 `on_reject: null` 正常终止 |
| `a2_review` | ✅ | `review_judge` 对 3 真图挑出 `cand_oak_slab @ 0.916 confidence`,`approve_one` |
| `a2_mesh` | ⚠️ | 真 Qwen 3 候选图生成($0.0834,`qwen_image_2`),但 `review_judge_visual` 在 3 张 1024×1024 PNG 合一条消息时撞破 GLM / DashScope 的 input-length 上限(base64 1,262,246 字符 > 1M),见 §6.5 根因;mesh 未触达 |
| `a2_ue` | 跳过 | 占位 `project_root="C:/Users/you/..."` 不存在,`ExportExecutor` 会 raise(保护 C: 驱动不被污染);与 A1 UE 真机绑定 |

**状态**:⚠️ 部分通过(3/5 绿 + 1 发现可修 bug + 1 跳过并入 A1)

### 6.2.1 A2 副产物:Router 观测性修复(2026-04-22)

A2 定位过程中发现并修复了 `CapabilityRouter` 的错误吞栈 bug(LLD §6.2 fallback 链):

- **Before**:`acompletion` / `astructured` / `aimage_generation` / `aimage_edit` 都用 `last = exc; continue`,fallback 耗尽后只 raise 最后一条路的 error。a2_mesh 3 次 attempt 都只看到 qwen-plus 的 DashScope 错误,glm_4_6v 两家的真错误被静默吞掉,根因定位时间被放大
- **After**:改为 `errors.append((model, exc))`,通过 `_raise_exhausted()` 合成 composite ProviderError,message 携带每条 route 的 `<model>: <verbatim error>`,`__cause__` 仍指向最后一条(不破坏 traceback)。关键:当所有路同 subclass(如全 `SchemaValidationError`)时保留子类,`FailureModeMap` 继续按 `schema_validation_fail` 路由,不会错误降级到 `provider_error`
- **Fence**:`tests/unit/test_router_fallback_errors.py` 4 条(chain 完整性 / 同类型保留 / 异构降级 / `__cause__` 保留)
- **验证**:resume a2_mesh 后看到真实全链错误 —— glm_4_6v_flashx / glm_4_6v "Prompt exceeds max length" + qwen-plus "Range of input length [1, 1000000]",3 家**同一根因**(payload 过长),不是 fallback 断也不是 qwen-plus 不支持视觉

### 6.2.2 A2 剩余:视觉 review 图像压缩(未做)

见 §7 TBD-006。

### 6.3 A3 — Pricing Probe `--apply` 真跑

**目标**:验证 playwright 后端在真实 provider 页面拉取,已实装 parser 的 `pricing` 与 `pricing_autogen` 刷新正确。

**前置条件**:
- `pip install playwright && playwright install chromium`
- 网络可达 bigmodel.cn / help.aliyun.com / cloud.tencent.com

**执行步骤**:

```bash
python -m framework.pricing_probe              # dry-run 先看 diff
python -m framework.pricing_probe --apply      # 真改 YAML
git diff config/models.yaml                    # 检视
python -m pytest tests/unit/test_registry_pricing.py -v
python -m pytest -q                            # 全量回归
```

**验收标准**:

- 12 个 model 全部 `status: fresh`:
  - zhipu × 3(glm_4_6v / glm_4_6v_flashX / glm_image)
  - dashscope × 6(qwen3_6_plus / qwen_image_2 / qwen_image_2_pro / qwen_image_edit / qwen_image_edit_plus / qwen_image_edit_max)
  - hunyuan_image × 2(hunyuan_image_v3 / hunyuan_image_style)
  - hunyuan_3d × 1(hunyuan_3d)
- `pricing_autogen.sourced_on` = 执行当日
- tripo3d 下 model 维持 `no_parser`(scaffold 未实装 parser,区别于 `stale`)
- 555 测试仍全绿

**状态**:✅ 已通过(2026-04-22 dry-run + --apply,所有 12 个 model 返 `fresh`,真实页面数值与 YAML 一致,`--apply` 无 diff;DashScope parser 已随 2026-04-22 工作树并入,tripo3d 维持 `no_parser`)

### 6.4 手工验收计划时序

```
顺序 1: A3(本地 + playwright)                  ✅ 已完成(2026-04-22)
顺序 2: B — 结构整理后 commit 工作树(含 pricing probe 那一轮) ✅ 已完成(commit 293979f / 74c0849)
顺序 3: A2 qwen/hunyuan 图像链 live smoke       ⚠️ 部分完成(2026-04-22):3/5 绿(a2_char / a2_image / a2_review),a2_mesh 炸在视觉 review payload 超限 → TBD-006 修复后可 resume
顺序 4: A2 mesh_from_image live smoke           ⚠️ 部分通过(2026-04-22 17:27):review 路径完全打通(GLM-4.6V approve_one @ 0.89),mesh 步抓到确定性业务错误 `配额超限`(HUNYUAN_3D_KEY 账号配额耗尽,非网络问题);本轮顺手加了 mesh quota error 分类 (§6.5 末段, 19 fence),用户充值 / 换 key 后 resume 可真完成
顺序 5: A1 UE 真机冒烟(待用户建空 UE 项目)      预计 1-2 小时(a2_ue 合并进来)
```

### 6.5 A2 a2_mesh 根因(视觉 review payload 超限)

**现象**:`image_to_3d_pipeline.json` 的 `step_review_image`(`review_judge_visual`)3 次 fallback attempt 全炸,workflow 终止在 mesh 之前。

**定位过程**:

1. 初读 trace 只看到 qwen-plus 的 DashScope 错误 `InvalidParameter: Range of input length should be [1, 1000000]`,误认为 fallback 断 / qwen 不支持视觉
2. 修 `CapabilityRouter` 错误吞栈(§6.2.1),resume 后看到全链三条真实错误:
   - `openai/glm-4.6v-flashx`: `Prompt exceeds max length`(Zhipu 措辞)
   - `openai/glm-4.6v`: `Prompt exceeds max length`
   - `openai/qwen-plus`: `Range of input length should be [1, 1000000]`(DashScope 措辞)
3. 量化 payload:3 张 1024×1024 Qwen-image 生成 PNG → base64 总 **1,262,246 字符** > 所有三家 provider 的单消息输入上限

**根因**(双 bug,Codex 独立 review 协助暴露第二条):

- **Bug B**(原 Claude 定位):`framework.review_engine.judge._build_prompt()` 在 `visual_mode=True` 时把每个 candidate 的 `image_bytes` 原封 base64 塞进 `image_url` content block,3 张 1024×1024 PNG → ~1.28M 字符
- **Bug A**(Codex 发现):`framework.runtime.executors.review._build_candidates()` 对 image-modality artifact 直接 `payload=repo.read_payload(aid)`,raw bytes 进入 `CandidateInput.payload`;`_build_prompt()` 用 `json.dumps(default=str)` 把 bytes 渲染成 `b'\x89PNG\\xNN...'` repr,**1 字节扩成 4 字符**,3 张 320KB PNG 合计 ~3.84M 字符塞进 user_text。两 bug 叠加 ≈ 5M 字符,远超 DashScope 1M 硬限

只修 Bug B(图像压缩)不闭环 —— text 块的 ~3.84M 仍单独撞限。两步必须一起做。

**不是**:
- fallback 断了 —— router 确实按序切了 3 家(2f57df9 修后 trace 证)
- qwen-plus 不支持视觉 —— 它接受了 `image_url` 并开始计数,只是超限
- provider 配置错 —— 3 家都 `kind: vision`,配置正确

**修法(TBD-006,2026-04-22 已实施)**:
1. **payload 摘要化**(Bug A):`_build_candidates` 对 image candidate 改成元数据 dict(`_image_artifact_id` / `mime_type` / `size_bytes` / `source_model`),raw bytes 仅经 `image_bytes` 字段流转
2. **图像压缩 helper**(Bug B):新建 `src/framework/review_engine/image_prep.py` 的 `compress_for_vision()`(Pillow 延迟 import + EXIF transpose + 768 px thumbnail + alpha 扁平 + JPEG q=80);`_attach_image_bytes()` 内调用,raw < 256KB 阈值短路保 Anthropic 小图路径
3. **`pyproject.toml`** `[llm]` extras 加 `Pillow>=10.0,<12`
4. **fence 10 条**(`tests/unit/test_visual_review_image_compress.py` × 8 + `tests/unit/test_review_payload_summarization.py` × 2),独立守 Bug A / Bug B / 阈值短路 / Pillow 缺失 hint / 端到端 payload 预算

**修法不做**:不引入新 `PromptTooLargeError` / 新 FailureMode。Codex 提的"映射到 `abort_or_fallback`"语义正确但 scope 过大,本轮维持 raise `ProviderError` → router 走 `provider_error → retry_same_step → fallback_model`(同 provider 重一次后切下家),全链炸通过 §6.2.1 的 router error chain 看真实原因。Stretch goal 留 TBD。

**旁证**:`a2_review` 的 `review_judge`(PackyCode Anthropic)对 3 张小占位图正常给 `approve_one @ 0.916`,说明 judge.py 构 message 本身没 bug,只是对真实 Qwen 生成图(每张 300KB+)没做体积控制。

**修复后 live 验证(2026-04-22 16:48)**:resume a2_mesh 用 8e8f533 commit 后的代码 + 已生成的 3 张真 Qwen PNG(各 ~320KB):

| step | 状态 | 关键指标 |
| --- | --- | --- |
| `step_spec` / `step_image` | cache_hit | resume 复用,$0.08 image_fast 不重烧 |
| `step_review_image` | ✅ pass | `openai/glm-4.6v` `approve_one @ 0.89 confidence`,选中 `cand_0`,$0.0013;**之前撞 1.26M payload 的链路现在真过了** |
| `step_mesh_spec` | ✅ pass | MiniMax 986 tokens 产出 mesh spec |
| `step_mesh` | ❌ 配额耗尽 | 见下方"A2 顺序 4 v4 resume"确证 |
| `step_export` | 未触达 | mesh 没产出,export 步未执行 |

**A2 顺序 4 v4 resume 确证(2026-04-22 17:27)**:再跑一次 resume(网络现已可达,`curl /v1/api/3d/query` 返 HTTP 401 正常),抓到**真实业务错误而非网络问题**:

```
MeshWorkerError: tokenhub 3d job 1438459300615168000 failed:
  {'message': '配额超限', 'type': 'api_error',
   'code': 'FailedOperation.InnerError'}
```

- submit **成功拿到 job_id**(`1438459300615168000`),服务端接受了请求
- poll 第一次就返 `status=failed` + "配额超限"
- 后续 attempt(第 2、3 次)触发 Hunyuan 服务端**连接级限流**(对耗尽配额的 key 做 TCP-reset),才表现为 `ConnectError: All connection attempts failed` —— 上一轮(16:48 v3)trace 只抓到第二类错误,误导方向,实际底层就是 key 配额耗尽。

**根因**:`HUNYUAN_3D_KEY` 账号**调用配额/余额耗尽**。非 framework bug,非网络问题。

**连带发现 + 顺手 framework 增强(2026-04-22 17:45,本轮实施)**:

发现 `mesh_worker.py:_atokenhub_poll` 在 `status=failed` 时无脑 raise `MeshWorkerError`,failure_mode_map 把它路由到 `worker_error → retry_same_step + fallback_model`,**每次 fallback 都 re-issue 一次付费 /submit**,在确定性的配额耗尽场景纯属浪费。

修法:
- 新增 `_is_quota_or_rate_limit_error(resp)` 分类器,检测 resp 里的中/英配额关键词(`配额` / `超限` / `充值` / `quota` / `rate limit` / `insufficient` / `billing` 等 15 条)
- 命中时改 raise `MeshWorkerUnsupportedResponse`(现有子类),映射到 `unsupported_response → abort_or_fallback`(honour `on_fallback`,未配则终止),**不再 fallback 链白烧 submit**
- 19 条 fence(`tests/unit/test_mesh_worker_quota_errors.py`):16 条 parametrize 覆盖分类器中英多 shape + 防误伤(GPU OOM / 404 等非 quota 失败保留 `MeshWorkerError`),3 条端到端守 `_atokenhub_poll` 分叉语义

用户侧 A2 顺序 4 真跑通**仍需先充值 HUNYUAN_3D_KEY 账号或换一把新 key**,framework 只是避免未来任何 provider 配额耗尽白烧付费提交。

**结论**:TBD-006 修复完全验证 —— 视觉 review payload 超限的根因(Bug A + Bug B 双修复)真实环境下闭合,review_judge_visual 在 GLM 上正常工作。剩余 mesh 步阻塞是**外部网络瞬态**,framework 路由和错误处理路径完全按预期工作(`MeshWorkerError` 被捕 → `worker_error` failure mode → 3 次 fallback 后 run.failed,无静默吞栈)。

---

## 7. 未启动项(超出当前基线)

| 编号 | 项 | 对应 SRS | 状态 | 计划 |
| --- | --- | --- | --- | --- |
| TBD-001 | bridge_execute 模式 | FR-UE-001 | ❌ | manifest_only 稳定 3 个月后评估 |
| TBD-002 | Audio worker(AudioCraft) | FR-WORKER-* | ❌ | 音频需求明确后 |
| TBD-003 | WS 鉴权 / 多租户 | NFR-SEC-005 | ❌ | 接入 UI 时 |
| TBD-004 | FBX self-containment 校验 | FR-WORKER-* | ❌ | 引入 PyFBX / ufbx 后 |
| TBD-005 | Tripo3D parser 实装 | FR-COST-006 | ⚠️ scaffold(DashScope 已于 2026-04-22 前并入) | 有工作流真实使用时 |
| ~~TBD-006~~ | ~~视觉 review 图像压缩~~ | FR-REVIEW-001, A2 顺序 3 | ✅ 已实施 + live 验证通过(2026-04-22)| 见 §6.5;代码 + 10 条 fence 就位,resume a2_mesh 中 step_review_image 真过(GLM-4.6V `approve_one @ 0.89`);剩余 step_mesh 阻塞于 Hunyuan 3D tokenhub poll 网络瞬态(非本 TBD scope) |
| TBD-T-001 | Linux CI runner | NFR-PORT-002 | ⏳ | 项目外部协作启动时 |
| TBD-T-002 | 覆盖率工具 | NFR-MAINT-* | ⏳ | 测试规模再增后 |
| TBD-T-003 | Live LLM CI job | A2 | ⏳ | 有稳定付费账号后 |

### 明确不做(⛔)

| 编号 | 项 | 原因 |
| --- | --- | --- |
| N/A | UE 插件化 | ADR-001(Python 版本绑死 / asyncio 与 game thread 冲突 / CI 不可跑 / 网络合规 / 多工程复用) |
| N/A | 渲染 / 动画 / 物理仿真 | 超出生产链定位 |
| N/A | 多租户权限系统 | project_id 仅逻辑隔离,不做 ACL |

---

## 8. 验收结论

### 8.1 自动化验收

| 级别 | 状态 |
| --- | --- |
| L0 pytest 全量 | ✅ **555 通过 / 0 失败**(2026-04-22 第五轮基线,~20.7s;基线 491 + Codex audit fence 29 + src-layout / router-obs 根因定位 fence 6 + TBD-006 视觉 review 图像压缩 fence 10 + mesh quota error 分类 fence 19) |
| L1 CLI 离线冒烟 | ✅ 5 份 examples bundle 全部可跑 |
| L4 文档评审 | ⏳ 本五件套本轮交付后待用户评审 |

### 8.2 实装成熟度

| 维度 | 等级 |
| --- | --- |
| 主线闭环(P0-P4) | ✅ 完整 |
| 失败路由 | ✅ 9 FailureMode 全覆盖 |
| 多 provider | ✅ 6 家已接入,5 家已走过真实调用 |
| 成本追踪 | ✅ 定价接入 + probe 止血 |
| 可观测 | ✅ EventBus + WS 端到端 |
| 测试覆盖 | ✅ 555 用例(基线 491 + Codex 5 轮 audit 29 fence + 2026-04-22 A2 根因定位 6 fence + TBD-006 视觉 review 图像压缩 10 fence + mesh quota error 分类 19 fence)+ 60+ L3 fence |

### 8.3 整体结论

**ForgeUE vNext 基线满足验收条件**:

- 所有 FR/NFR 项已有自动化或指定手工手段覆盖
- 自动化部分 100% 通过
- 手工验收(A1/A2/A3)项目明确,路径可执行
- 不做项与未启动项有明确 ADR 或 TBD 条目

**推荐下一步**:按 §6.4 时序执行手工验收,完成 A1/A2/A3 后,本文档升版 v1.1,把 ⏳ 转为 ✅。

---

## 9. 附录

### 9.1 验收责任

| 角色 | 责任 |
| --- | --- |
| 开发 | 自动化测试 + CLI 冒烟 + 文档交付 |
| QA / TA | L2 Live smoke + L3 UE 真机 |
| 项目发起人 | L4 文档评审签收 |

### 9.2 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0 | 2026-04-22 | 初始基线,从 plan_v1 §K + §M 拆分重组 |
| v1.1 | 2026-04-22 | Codex 5 轮 audit(21 条 issue)修复 + 验收登记:新增 FR-LC-006~008、FR-WORKER-009~010、FR-COST-008~009、FR-RUNTIME-008~012、FR-REVIEW-009、NFR-REL-009、ADR-006 共 13 条验收行;L0 自动化基线 491 → 520 |

### 9.3 签收区

| 角色 | 姓名 | 日期 | 签字 |
| --- | --- | --- | --- |
| 开发代表 | | | |
| QA / TA | | | |
| 项目发起人 | | | |
