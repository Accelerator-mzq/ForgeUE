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
| L0 自动化 | `pytest -q` 全绿 | **848 用例通过 ✅**(2026-04-25 实测;历史基线 549 = 491 + Codex audit fence 29 + src-layout / router-obs 根因定位 fence 6 + TBD-006 视觉 review 图像压缩 fence 10 + TBD-007 mesh 重试塌缩 fence 5 + TBD-008 visual review contract fence 2 + A1 + a2_mesh live bundle parametrize 6;本轮 +299 = Run Comparison 模块,详见 §6.8 与 §8.1) |
| L1 CLI 离线冒烟 | `python -m framework.run --task examples/mock_linear.json` | 不抛异常,有产物落盘 |
| L2 Live LLM smoke | `python -m framework.run --task <bundle> --live-llm` | 需 API key |
| L3 UE 真机冒烟 | UE commandlet `UnrealEditor-Cmd.exe -ExecutePythonScript=ue_scripts/a1_run.py`(0 GUI 依赖)或 GUI Python Console `exec(run_import.py)` | 需 UE 装机 + 空项目 + PythonScriptPlugin |
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
| P4 | UE Bridge manifest_only | `integration/test_p4_ue_manifest_only.py`(stub unreal) | ✅ `examples/ue_export_pipeline.json` | ✅ UE 5.7.4 真机(2026-04-23 commandlet) | ✅ |

### 3.2 L 层能力

| ID | 能力 | 对应需求 | 状态 |
| --- | --- | --- | --- |
| L1 | UE5 API 查询 | FR-STRUCT-* + rubric `ue5_api_assist` | ✅ |
| L2 | 图像生成 API 路径 | FR-WORKER-001(ComfyUI) + `image.*` capability | ✅ |
| L3 | 视觉 QA | FR-REVIEW-* + rubric `ue_visual_quality` | ✅ |
| L4 | image → 3D mesh | `integration/test_l4_image_to_3d.py` + Hunyuan 3D + UE 5.7 真 import(2026-04-23 a2_mesh_0423)| ✅ |

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
| FR-UE-003 UE Python Console 导入 | stub unreal(`test_p4`) + UE 5.7.4 commandlet 真机 | ✅(2026-04-23 A1 通过,见 §6.1)|
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
| ADR-008 | 启用 UE 自带 plugin(PythonScriptPlugin / 未来 RemoteControl)不算违反 ADR-001 | ✅(2026-04-23 A1 立项):ADR-001 禁止**"我们自己写 UE 插件"**;启用 Epic 维护、UE 引擎自带的 plugin 不在禁令范围。逐条对照 SRS:374 的 6 个顾虑:**Python 版本绑定** — UE 自带 plugin 已随 UE 版本编译,不强制我们绑特定 Python;**阻塞 game thread** — 我们不在 game thread 写代码,plugin 已在 editor 模块隔离;**无法跑纯 Python 单测套件**(2026-04-23 ADR-008 立项时基线 543+ 单测)— 启用 plugin 不影响纯 Python 单测套件,framework 侧仍 0 UE 依赖;**隔离网络合规** — 启用 plugin 不引入新网络通道;**多工程复用** — `.uproject` Plugins 段是工程级配置,跨工程同样可声明;**开发环境门槛** — 启用是 1 行 .uproject + 1 行 commandlet,不像写 plugin 要 VS + UE source 编译。注意:ADR-007 在 SRS:380 是"贵族 API 不允许 framework 静默重试",与本条无关 |

---

## 6. 待验收项(需执行)

### 6.1 A1 — UE 5.x 真机冒烟 ✅(2026-04-23 通过,a2_ue 同次合并)

**目标**:验证 `ue_scripts/run_import.py` 在真实 UE 进程中调用 `unreal.AssetImportTask` 系列 API,Content Browser 出现资产,evidence.json 追加成功记录。

**实际执行**(commandlet 全自动化路径,0 GUI 操作):
- UE 5.7.4 装在 `E:\Epic Games\UE_5.7\`
- C++ 项目 `D:\UnrealProjects\ForgeUEDemo\`,本地编译过
- `.uproject` Plugins 段加 `PythonScriptPlugin: Enabled`(注意:不是 `PythonAutomationTest` —— 后者是测试框架,易混淆)
- 新建 live bundle `examples/ue_export_pipeline_live.json`(原 `ue_export_pipeline.json` 留 ComfyUI 接口给 P4 集成测试),关键 diff:
  - `step_image` 走真 `image_fast`(qwen_image_2 → glm_image fallback),替代 FakeComfy 占位
  - `step_review` 切 `review_judge_visual` + `visual_mode: true` + `rubric_ref: ue_visual_quality`,与 `image_to_3d_pipeline.json` 对齐
  - 显式 `on_reject: null` 防御
- 入口脚本 `ue_scripts/a1_run.py`(设 `FORGEUE_RUN_FOLDER` + 调 `run_import.run()`)

**执行步骤**:

```bash
# Step 1 — framework 侧 live 跑(~60s,$0.12 USD)
PYTHONPATH=src python -m framework.run \
    --task examples/ue_export_pipeline_live.json \
    --live-llm --run-id a1_demo

# Step 2 — UE 5.7 commandlet 真机 import(~20s,无 GUI)
"E:/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" \
    "D:/UnrealProjects/ForgeUEDemo/ForgeUEDemo.uproject" \
    -ExecutePythonScript="D:/ClaudeProject/ForgeUE_claude/ue_scripts/a1_run.py" \
    -stdout -unattended -nopause
```

**实测结果**:

| 阶段 | 状态 | 关键指标 |
| --- | --- | --- |
| framework run | ✅ succeeded | 4 步全访问 + 0 failure_event + verdict approve_one @ 0.89 |
| step_image | ✅ | Qwen-image-2.0 真生成 3 张 candidate(1920×1080 PNG,各 ~3 MB) |
| step_review | ✅ | GLM-4.6V-flashX 视觉 review:cand_0 加权 0.89(其他全过线,single_best 选最高) |
| step_export | ✅ | manifest + plan + evidence + 选中 PNG 落 `D:/UnrealProjects/ForgeUEDemo/Content/Generated/a1_demo/` |
| commandlet | ✅ exit=0 | UE 5.7.4 启动 + load C++ project + Interchange import + shutdown 共 20s |
| UE Interchange | ✅ | `LogInterchangeEngine: Interchange import completed`,`LogTexture: 正在构建纹理：/Game/Generated/Tavern/a1_demo/T_xxx (TFO_AutoDXT, 1920x1080)` |
| evidence.json | ✅ | 3 条全 success:`drop_file` + `create_folder` + `import_texture` |
| .uasset 落盘 | ✅ | `D:/UnrealProjects/ForgeUEDemo/Content/Generated/Tavern/a1_demo/T_a1_demo_step_image_cand_a6a96ca7_0.uasset`(3.15 MB) |
| Content Browser 视觉确认 | ✅ | 用户 GUI 双击 .uasset,Texture 预览出现 oak tavern door |

**架构突破**:用 UE commandlet 模式 (`-ExecutePythonScript`) 让 Claude 通过 Bash 直接驱动 `unreal` Python API,不需要 UE 编辑器 GUI 开着、不需要用户手工点 Python Console。三通道分析(A=Python commandlet / B=RemoteControl HTTP / C=C++ Subsystem)详见 `C:\Users\mzq\.claude-max\plans\ue-ue5-gui-a-greedy-umbrella.md`,A1 选 A 通道,B 通道作为长期 bridge_execute 的 future TBD-009。

**状态**:✅ 通过(2026-04-23)

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
| `a2_mesh` | ✅ | 全链跑通(2026-04-22 18:38 v6 重跑):3 张 Qwen 真图(~1.5MB/张) → `step_review_image` GLM-4.6V approve → `step_mesh_spec` MiniMax → **`step_mesh` Hunyuan 3D 真生成 30.6MB .glb**;`step_export` 按预期 raise(C: 占位路径,绑 A1 真机)。**2026-04-23 重跑(`image_to_3d_pipeline_live.json` + run_id `a2_mesh_0423`):全链一次过(approve_one @ 0.90)+ 33.3MB .glb 真生成 + UE 5.7 commandlet 真 import → `Generated/Props/a2_mesh_0423/.../{StaticMeshes/SM_*, Materials/Material_001, Textures/texture_20250901}.uasset` 三类资产落盘 + 用户 GUI 视觉确认 oak barrel 3D mesh** |
| `a2_ue` | ✅(2026-04-23 与 A1 合并) | 用 `examples/ue_export_pipeline_live.json`(原 `ue_export_pipeline.json` 留 ComfyUI 接口给 P4 集成测试)+ 真 UE 5.7.4 项目 `D:/UnrealProjects/ForgeUEDemo/`,framework live + commandlet 全自动化跑通,export bundle 真落到 UE 项目,见 §6.1 |

**状态**:✅ 通过(5/5 绿,a2_ue 在 2026-04-23 与 A1 合并跑过)

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
- 536 测试仍全绿

**状态**:✅ 已通过(2026-04-22 dry-run + --apply,所有 12 个 model 返 `fresh`,真实页面数值与 YAML 一致,`--apply` 无 diff;DashScope parser 已随 2026-04-22 工作树并入,tripo3d 维持 `no_parser`)

### 6.4 手工验收计划时序

```
顺序 1: A3(本地 + playwright)                  ✅ 已完成(2026-04-22)
顺序 2: B — 结构整理后 commit 工作树(含 pricing probe 那一轮) ✅ 已完成(commit 293979f / 74c0849)
顺序 3: A2 qwen/hunyuan 图像链 live smoke       ✅ 已完成(2026-04-22):4/5 绿(a2_char / a2_image / a2_review / a2_mesh),a2_ue 绑 A1 跳过
顺序 4: A2 mesh_from_image live smoke           ✅ 已完成(2026-04-22 18:38 v6 重跑 + 2026-04-23 重跑):前者证 mesh 生成 + 后者证 UE 真 import 闭合(`image_to_3d_pipeline_live.json` → `Generated/Props/a2_mesh_0423/.../SM_*.uasset` + 用户视觉确认 oak barrel)
顺序 5: A1 UE 真机冒烟 + a2_ue 合并              ✅ 已完成(2026-04-23):UE 5.7.4 commandlet 全自动化路径,framework live + commandlet 总 ~80s,Texture .uasset 落盘 + Content Browser 视觉确认,见 §6.1
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
| `step_mesh` | ❌ 16:48 当时阻塞 / ✅ v6 18:38 真生成 30.6 MB .glb | 见下方"A2 顺序 4 v6 重跑"行 + "收官"段 |
| `step_export` | 未触达 | mesh 没产出,export 步未执行 |

**A2 顺序 4 多轮 resume 真实错误形态(2026-04-22 16:48 ~ 18:00)**:

| 轮次 | 时间 | mesh 步错误形态 |
| --- | --- | --- |
| v3 | 16:48 | 3 次 attempt 全 `httpx.ConnectError: All connection attempts failed` |
| v4 | 17:27 | 第 1 次 attempt `{'message': '配额超限', 'code': 'FailedOperation.InnerError'}`,第 2、3 次 ConnectError |
| v5 | 18:00 | 3 次 attempt 全 ConnectError,零"配额超限" |
| probe solo | 17:45 / 17:50 | **完全正常**:submit → job_id → 60s completed → 返 .glb / .obj + preview URL |
| **v6(从头跑)** | **18:38** | **✅ 全链通过**:3 张 Qwen 真图 → review approve → MiniMax mesh_spec → **Hunyuan 3D 真生成 30.6 MB .glb**;step_export 按预期 raise C: 占位路径 |

**关键定位步骤**:

- 用户去腾讯云控制台**确认 `HUNYUAN_3D_KEY` 额度未耗尽**
- `probes/provider/probe_hunyuan_3d_submit.py` 独立 Python httpx 打 tokenhub(绕开 framework),用同 key / 同 body / 同 endpoint,submit + poll **完全正常**:60s 完成,返 `status=completed` + .glb / .obj URL + preview
- 三轮 framework resume 错误形态**每次不同**(ConnectError / "配额超限" / 混合),甚至**同一 key 短时间内**表现不一致

**根因**:Hunyuan 3D tokenhub 服务端**时段/负载相关的 transient 状态**。对同一 key 的同一合法请求,在某些时段给出"配额超限"业务错或 TCP 连接级 reset(与真实配额状态脱钩)。非 framework bug,非 key 耗尽,非网络问题,非请求格式问题。

**关于 `code: FailedOperation.InnerError`**:腾讯云通用"内部错误"码(不是专门的配额错误码 `FailedOperation.QuotaExceeded` / `LimitExceeded.*`),`message: '配额超限'` 只是人类可读文案占位,**不能当作真实配额耗尽的证据**。

**一次错误假设 + 已撤回(2026-04-22 17:45 ~ 18:15,commit a0ffa6c 发布、此提交 revert)**:

v4 抓到"配额超限"文案后,我误把它当成"确定性配额耗尽"根因,顺手在 `mesh_worker._atokenhub_poll` 加了 `_is_quota_or_rate_limit_error` 分类器,命中时 escalate 到 `MeshWorkerUnsupportedResponse` → `abort_or_fallback` 直接终止。19 条 fence 守门,commit `a0ffa6c` 推送。

v5 打脸:同 key 同请求这次返 ConnectError 而非"配额超限",solo probe 证明 key 正常。**假设破产**:"配额超限"文案不是确定性,是 transient 的。留着分类器的风险:下次 provider 又返"配额超限"时会把实际可 retry 的场景永久终止。

撤回:revert `mesh_worker.py` 的 `_QUOTA_KEYWORDS` + `_is_quota_or_rate_limit_error` + poll 分叉,删 `tests/unit/test_mesh_worker_quota_errors.py`,测试基数 555 → 536。

**教训**:provider 的 error `message` **不能字面当结论**(正是 `feedback_verify_external_reviews.md` 规矩防的坑)。应该拿**独立证据**(控制台额度、独立 probe、多时段观察)验证才能定性。framework 不该在单次错误 message 上建立"确定性 / 永久终止"的分类语义 —— 需要多次实证确认才升级。

**结论**:TBD-006 修复完全验证 —— 视觉 review payload 超限的根因(Bug A + Bug B 双修复)真实环境下闭合,review_judge_visual 在 GLM 上正常工作。

**A2 顺序 4 收官(2026-04-22 18:38 v6 从头跑)**:Hunyuan 3D tokenhub 服务稳定后,从头跑全链一次过 —— 3 张 Qwen 1024×1024 真图 → GLM-4.6V approve → MiniMax mesh_spec → **Hunyuan 3D 30.6 MB .glb 真生成落盘** → step_export 按预期 raise C: 占位路径(绑 A1 真机)。**A2 顺序 4 ✅ 升级**;先前判定的"transient 阻塞"得到反向验证 —— 服务恢复后链路完全打通。

**a2_image / a2_review 的证据力修订(2026-04-22 TBD-008)**:经 Codex 独立 review,`a2_image`(FakeComfy 4.5KB 占位 + `review_judge` 无 visual_mode)与 `a2_review`(inline 文字 metadata,无 visual_mode)**均不是视觉 review 证据** —— 它们测的是 "占位图被拒的工作流终止路径" 和 "判官解析文字 schema 的契约",属于 smoke 价值,留作现状不扩大。真正的视觉 review 证据现在归:
- **offline 契约** — `test_p2/p3/l4` 用真 PNG fixture 驱动(见 §6.7 TBD-008)
- **provider 质量抽检** — `FORGEUE_PROBE_VISUAL_REVIEW=1 python -m probes.provider.probe_visual_review` 手跑,对比 Anthropic Opus 4.6 vs GLM-4.6V 对同 3 张真图的打分分布

### 6.6 TBD-007 mesh 重试塌缩 + 失败 visibility(Codex 独立 review 协助)

**触发**:用户对账腾讯云控制台,A2 a2_mesh 一次"用户视角的单 mesh job"实际计费 **16 调用 × 20 积分 = 320 积分**。

**根因 — 4 层叠加重试**(我第一轮只看出 3 层,Codex 独立 review 找到第 4 层):

| 层 | 位置 | 默认乘数 | 我第一轮 | Codex |
|---|---|---|---|---|
| L1 TCP transient | `mesh_worker._apost` 套 `with_transient_retry_async(max_attempts=2)` | ×2 | ✅ 找到 | ✅ |
| L2 **executor 内部 for 循环** | `GenerateMeshExecutor.execute()` 按 `policy.max_attempts` 调 `worker.generate()` | ×2 | **❌ 漏了** | ✅ 找到 |
| L3 orchestrator | `MeshWorkerTimeout → worker_timeout → retry_same_step` | ×2 | 部分(`worker_error → fallback_model`)| ✅ 找到 |
| L4 download Range resume | `chunked_download_async _MAX_RETRIES=3`(只补缺字节,经济意义不同)| ×3 字节 | ❌ 漏了 | ✅ 找到 |

最坏组合 **2 × 2 × 2 = 8 logical attempts × (1 submit + 1 poll = 2 计费 each)= 16 次**,与实测吻合。

**HYPOTHESIS 验证(2026-04-22 19:53,probe_hunyuan_3d_query)**:Codex 提出"客户端断开后远端 job 可能继续跑"是关键架构洞察。我用独立 /query probe 对历史 job_id 验证:

| job_id | 提交时间 | 当时本地观察 | 17.5h 后远端真实状态 |
|---|---|---|---|
| `1438459300615168000` | 17:18 | failed: '配额超限' | 仍 failed(状态稳定) |
| `1438465104214892544` | 17:46 | abandoned at 'queued'(probe 单 poll 离开) | **completed**,有完整 .glb / .obj URL,签名到 2026-04-23 19:54 |

**HYPOTHESIS 完全确证** ✅。abandoned job 的 mesh 实际生成完成、用户已付费、产物在 CDN。意味着:framework 的 blind retry 真的会**双扣已完成 job**。

**修法**(本轮全做):

| 阶段 | 内容 | 文件 |
|---|---|---|
| Phase 0 | 写 `probes/provider/probe_hunyuan_3d_query.py`(read-only /query) | new |
| Phase A1 | `GenerateMeshExecutor` 对 `capability_ref="mesh.generation"` 强制 `attempts=1` | `executors/generate_mesh.py` |
| Phase A2 | `mesh_worker._apost` 拆 `with_transient_retry_async`,单次直发 | `workers/mesh_worker.py` |
| Phase A3 | `failure_mode_map` 新增 `mesh_worker_timeout` / `mesh_worker_error` mode → `Decision.abort_or_fallback`;classify 优先匹配 mesh 子类 | `failure_mode_map.py` |
| Phase A4 | Download Range resume **不动**(字节断点,经济意义不同),只补 ADR | `LLD.md` |
| Phase B1 | `MeshWorkerError/Timeout` 加 `(*, job_id, worker, model)` kwargs;`_atokenhub_*` 失败处填字段 | `workers/mesh_worker.py` |
| Phase B2 | `orchestrator` failure_event 写 `context.{job_id, worker, model}` | `runtime/orchestrator.py` |
| Phase B3 | `framework/run.py` mesh 失败检测 + stderr 提示(job_id + 推荐先跑 query probe + 才 --resume)| `run.py` |

**测试基数 536 → 541**:
- 翻转 `test_mesh_worker_does_NOT_retry_on_winerror_10060`(原断言重试 2 次成功 → 现断言单次 raise)
- 翻转 `test_mesh_executor_does_NOT_retry_on_worker_error`(同上,executor 层)
- 修订 `test_failure_mode_map.py::test_classify_known_exceptions`(2 个 parametrize 行从 worker_* 改 mesh_worker_*)
- 新增 `tests/unit/test_mesh_no_silent_retry.py`(4 fence:L1 transport / L2 executor / L3 mesh_timeout abort / L3 mesh_error abort)
- 新增 `tests/integration/test_mesh_failure_visibility.py`(1 fence:end-to-end orchestrator failure_event + CLI stderr hint)

**不做**(scope 收缩):
- 不动 `_retry_async.py` helper(image / qwen adapter 仍依赖)
- 不动 `_download_async.py`(Range resume 是字节级,与 API call 经济意义不同)
- 不动 `hunyuan_tokenhub_adapter.py` / `qwen_multimodal_adapter.py`(image 单价低一个量级,留单独评估)
- 不引入新 FailureMode `pause_for_user_query` / `--resume-job` flag(stretch goal,本轮 stderr hint 已让用户能手工 query)

**Codex 还提了哪些我没采纳**:
- "manual-retry class + human gate" 长期方向正确,但需新 framework 级 pause/resume 状态机,scope 太大,本轮维持 batch CLI + stderr hint
- Layer 4 download Range resume 也"零静默重试"洁癖性删除 —— 我判经济意义低于 API call 重发,保留有真实续传价值;LLD 加 ADR 段记录区分

### 6.7 TBD-008 visual review 契约 / 质量分层(Codex B+C 分层采纳)

**触发**:用户观察 — "a2_image 拿占位图测试 / a2_review 文字 metadata 候选,看不出打分优势"。我第一轮 plan(新 live bundle)被 Codex 独立 review 指出**绕开了真盲区** — `tests/integration/test_p2_standalone_review.py:203,221,298` / `test_p3_production_pipeline.py:214,220,398` / `test_l4_image_to_3d.py:41,147` 成片的 `VISUAL_A/B/C` / `ORIGINAL_/REVISED_/API_` / `fake-source-image-bytes` 伪字节,让"视觉 review"退化为"计算 image_url block 数量 + 按 candidate_id 位置打分"。新加 live bundle 在旁边另起一摊,老盲区仍在。

**修法分层**(Codex):
1. **契约层(offline 稳定,$0 CI)**:`tests/fixtures/review_images/tavern_door_v{1,2,3}.png` 真 Qwen 1024×1024 PNG + `FakeAdapter` 脚本化打分,测 review pipeline 流水线正确性
2. **质量层(opt-in 偶发)**:`probes/provider/probe_visual_review.py` FORGEUE_PROBE_VISUAL_REVIEW=1 opt-in,真 Anthropic / GLM 对真图打分对比,测 provider 判别能力

**实施点**:
- `tests/fixtures/review_images/` 新目录 + `tavern_door_v{1,2,3}.png`(~4.4MB)+ `__init__.py.load_review_image(name)` helper
- `test_p2_standalone_review::test_p2_visual_mode_attaches_image_bytes_to_judge_prompt`:VISUAL_A/B/C → fixture;断言升级 "winner=cand_primary + confidence>0.7" + JPEG 压缩路径验证(TBD-006 真跑)
- `test_p3_production_pipeline`:ORIGINAL_/REVISED_/API_ → fixture;assertions 不变,字节源升级
- `test_l4_image_to_3d::test_l4_mesh_reads_selected_candidate_from_review_verdict`(新增,**真实生产路径**):验证 mesh 从 `report.verdict.selected_candidate_ids[0]` 读图,匹配 `image_to_3d_pipeline.json` 的 depends_on 链(无 SelectExecutor)
- `test_l4_image_to_3d::test_l4_mesh_resolves_selected_image_from_selected_set_bundle`(新增,forward-compat):验证 `bundle.selected_set` resolution,覆盖未来可能引入 SelectExecutor 的工作流
- `src/framework/runtime/executors/generate_mesh.py:_resolve_source_image` 优先级重写:verdict > selected_set > 直接 image > candidate_set(Codex Phase G 两轮 review 的核心产出)
- `probes/provider/probe_visual_review.py`:两家 judge 同 3 图对比,落 `demo_artifacts/<today>/probes/provider/visual_review/<HHMMSS>/comparison_table.md`

**HYPOTHESIS 意外验证**:`review_judge` 别名在 `config/models.yaml` 里**无 `kind: vision` 标签**,但 probe 实跑证实 Anthropic Opus 4.6 vision 路径工作正常(`visual_mode=true` + image_url block + TBD-006 JPEG 压缩一路通到 PackyCode 返 approve_one @ 0.85 confidence)。消息 shape 是 provider 无关的,`kind` 标签只影响 router 优选逻辑(不 gate 路由)。fallback 方案(补标签)**未触发**。

**probe 首跑打分分布对比(2026-04-22 23:03)**:
| 判官 | cand_0 五维分 | cand_1 | cand_2 | winner | confidence |
|---|---|---|---|---|---|
| `review_judge`(Anthropic Opus 4.6)| 0.82-0.88 | 0.62-0.78 | 0.78-0.85 | cand_0 | **0.8515** |
| `review_judge_visual`(GLM-4.6V) | 0.85-0.95 | 0.80-0.90 | 0.80-0.90 | cand_0 | **0.8925** |

观察:Anthropic 打分跨度更大(0.62-0.88),**判别度更好**;GLM 打分更"压缩"(0.80-0.95 挤在一起),判别度弱但置信度更高。这是用户诉求的"看出打分优势"的直接证据。

**测试基数 541 → 543**(1 新 fence + 3 翻转:翻转不变数,新增 1)。

**未做**(scope 收缩):
- ❌ 不新建 `a2_image_live.json` / `a2_review_live.json`(我原 P1,被 B+C 覆盖)
- ❌ 不把 `examples/review_3_images.json` 改造成 visual bundle(留文字 schema smoke 独立价值)
- ❌ 不引入新 executor / 新 candidate 摄入路径

### 6.8 Run Comparison / Baseline Regression(2026-04-25,OpenSpec change `add-run-comparison-baseline-regression`)

**触发**:`README.md` §"后续扩展" 第 7 项 "Run Comparison / 基线回归 — `observability/run_comparison.py` 待补" 占位关闭。proposal.md 列 4 条 Success criteria(future implementation phase),全部达成。

**实装产出**:`src/framework/comparison/`(`models.py` / `loader.py` / `diff_engine.py` / `reporter.py` / `cli.py` / `__main__.py`)+ `tests/fixtures/comparison/builders.py`(deterministic builder)+ 5 unit + 1 integration 测试文件。CLI 入口 `python -m framework.comparison`。详见 `docs/design/LLD.md` §15 接口签名 + `docs/testing/test_spec.md` §3.11 / §3.11A 测试索引。

**proposal 4 条 Success criteria 验收**:
- ✅ CLI 跑通离线 fixture,产出 JSON + Markdown(`tests/integration/test_run_comparison_cli.py::test_python_m_framework_comparison_happy_path` + `..._lineage_diff_surfaces_in_json` + `..._does_not_pollute_repo_demo_artifacts`)
- ✅ ≥1 condition integration test 覆盖 `unchanged` / `content_changed` / `metadata_only` / `lineage_delta` / `cost_usd metric diff`(builder fixture 端到端)+ `examples/mock_linear.json` + FakeAdapter 双跑离线 integration(`..._offline_real_run_pair_via_framework_run`,守门 examples-and-acceptance delta spec Validation gate)
- ✅ 不依赖 `.env` / provider key — 全 offline,subprocess 跑 `python -m framework.run` 时无 `--live-llm` / 无 `--comfy-url`,自动 FakeAdapter + FakeComfyWorker
- ✅ 测试数实测(**未硬编码**),pytest -q 实测 **848 通过**(基线 549 + Run Comparison 模块 299 新用例,per-file:models 52 + loader 50 + diff_engine 69 + reporter 65 + cli 59 + integration 4)

**Codex Review Gate**:已通过(Task 4 / 5 / 6 各两轮)。具体 thread / agent ID 见本地 conversation records,本文件不重复列出避免随会话漂移。
- Task 4 第一轮 PASS + 3 条 nice-to-have polish(吸收后第二轮可选验证)
- Task 5 第一轮 BLOCK(stdout/stderr ASCII-safe + CR/LF compaction Blocker;由 `_console_safe` + 13 个 ConsoleSafe / EndToEnd / NoHashCheck 测试解决);第二轮 PASS
- Task 6 第一轮 BLOCK(spec validation gate 缺失 / `demo_artifacts` 浅层快照 / 源 run dir read-only 未守门;由 `test_offline_real_run_pair_via_framework_run` + `_snapshot_tree` 递归 + pre/post 快照断言解决);第二轮 PASS,2 条 Low Risk polish(`_run_comparison_cli` timeout + `_diff_snapshots` helper)吸收

**Deferred follow-up**:`lazy-artifact-store-package-exports`(尚未创建独立 OpenSpec change)。`framework.comparison.loader` 顶层 `from framework.artifact_store.hashing import hash_payload` 必然触发 `framework/artifact_store/__init__.py` 执行,而该 `__init__` 当前 eager-import `repository` / `payload_backends`,导致两者作为 transitive 出现在 `sys.modules`。当前 fence 与 Task 2 loader fence 对齐(只锁 9 个执行链路前缀);**未**改 `artifact_store/__init__.py`,跨子系统改动留独立 change 评估 PEP 562 lazy export。详见 `openspec/changes/add-run-comparison-baseline-regression/tasks.md §"Deferred Follow-ups"`。

**Non-goals 验证**:
- ❌ 不改现有 Run 执行链路(Orchestrator / Scheduler / TransitionEngine / Executors 全未触动)— 实测 git diff 仅含 `src/framework/comparison/` + `tests/{unit,integration,fixtures}/comparison*` + 6 份 docs / openspec sync
- ❌ 不改 Artifact / Checkpoint / ReviewReport / Verdict schema — model 未触动
- ❌ 不做实时对比(两端必须已结束)— loader 强制要求 `run_summary.json` 含 `status` 字段,不满足时 `RunSnapshotCorrupt` exit 2
- ❌ 不做 content-semantic 比较(图像 / mesh 几何相似度)— 止于 hash + metadata + Verdict 语义
- ❌ 不做 Run 合并 / 选优 / 人工审核 — `compare()` 是 read-only 函数

---

## 7. 未启动项(超出当前基线)

| 编号 | 项 | 对应 SRS | 状态 | 计划 |
| --- | --- | --- | --- | --- |
| TBD-001 | bridge_execute 模式 | FR-UE-001 | ❌ | manifest_only 稳定 3 个月后评估 |
| TBD-002 | Audio worker(AudioCraft) | FR-WORKER-* | ❌ | 音频需求明确后 |
| TBD-003 | WS 鉴权 / 多租户 | NFR-SEC-005 | ❌ | 接入 UI 时 |
| TBD-004 | FBX self-containment 校验 | FR-WORKER-* | ❌ | 引入 PyFBX / ufbx 后 |
| TBD-005 | Tripo3D parser 实装 | FR-COST-006 | ⚠️ scaffold(DashScope 已于 2026-04-22 前并入) | 有工作流真实使用时 |
| ~~TBD-006~~ | ~~视觉 review 图像压缩~~ | FR-REVIEW-001, A2 顺序 3+4 | ✅ 已实施 + live 验证通过(2026-04-22 18:38)| 见 §6.5;代码 + 10 条 fence 就位,a2_mesh 从头跑全链通过(step_review_image GLM-4.6V approve + step_mesh Hunyuan 3D 真生成 30.6 MB .glb) |
| ~~TBD-007~~ | ~~mesh 重试塌缩 + 失败 visibility~~ | NFR-COST-*, A2 顺序 4 | ✅ 已实施 + HYPOTHESIS probe 验证(2026-04-22) | 见 §6.6;Codex 独立 review 协助找出 4 层中第 2 层(executor 内部 retry);job_id 持久化暴露给 CLI;5 条 fence 就位 |
| ~~TBD-008~~ | ~~visual review 契约质量分层(fixture + opt-in probe)~~ | FR-REVIEW-*, NFR-MAINT | ✅ 已实施(2026-04-22)| 见 §6.7;Codex 独立 review 指出 p2/p3/l4 伪字节盲区;fixture 真图驱动 offline + `probe_visual_review.py` opt-in live 抽检;1 新 fence + 3 翻转;a2_image/a2_review bundle 降级为 "schema smoke" 不再当视觉证据 |
| TBD-T-001 | Linux CI runner | NFR-PORT-002 | ⏳ | 项目外部协作启动时 |
| TBD-T-002 | 覆盖率工具 | NFR-MAINT-* | ⏳ | 测试规模再增后 |
| TBD-T-003 | Live LLM CI job | A2 | ⏳ | 有稳定付费账号后 |
| TBD-009 | RemoteControl HTTP bridge(future bridge_execute) | FR-UE-001 | ⏳ | A1 立项(2026-04-23):启用 UE 自带 `RemoteControl` + `WebRemoteControl` plugin,Claude 通过 `PUT :30010/remote/object/call` 控制运行中 editor。**适用**:长会话多次操作(免重启 editor)/ 实时反馈(PIE 截图回 review)/ 真正"agent 与 live editor 协同"。**关键约束**:UE editor 必须常驻进程(端口非独立 daemon)+ 30010 防火墙放通 + reflection 调用拼 ObjectPath/UFUNCTION 比 Python API 繁琐脆。**不在 A1 scope**:commandlet 冷启 20s 已够,无 GUI 依赖更稳。**ADR**:见 ADR-008 |

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
| L0 pytest 全量 | ✅ **848 通过 / 0 失败**(2026-04-25 OpenSpec change `add-run-comparison-baseline-regression` 完成后实测,~28s;基线 549 + Run Comparison 模块 299 用例[`test_run_comparison_models.py` 52 + `test_run_comparison_loader.py` 50 + `test_run_comparison_diff_engine.py` 69 + `test_run_comparison_reporter.py` 65 + `test_run_comparison_cli.py` 59 + integration 4]) |
| L1 CLI 离线冒烟 | ✅ 5 份 examples bundle 全部可跑 |
| L3 UE 真机 | ✅ UE 5.7.4 commandlet 通过(2026-04-23,见 §6.1) |
| L4 文档评审 | ⏳ 本五件套本轮交付后待用户评审 |

### 8.2 实装成熟度

| 维度 | 等级 |
| --- | --- |
| 主线闭环(P0-P4 含 UE 真机) | ✅ 完整(2026-04-23 A1 + a2_ue 真机闭合) |
| 失败路由 | ✅ 9 FailureMode 全覆盖 |
| 多 provider | ✅ 6 家已接入,5 家已走过真实调用 |
| 成本追踪 | ✅ 定价接入 + probe 止血 |
| 可观测 | ✅ EventBus + WS 端到端 |
| 测试覆盖 | ✅ 当前 848 用例(2026-04-25 实测);历史基线 549(491 + Codex 5 轮 audit 29 fence + 2026-04-22 A2 根因定位 6 fence + TBD-006 视觉 review 图像压缩 10 fence + TBD-007 mesh 重试塌缩 5 fence + TBD-008 visual review contract 2 fence + A1 + a2_mesh live bundle parametrize 6 自动收);本轮 Run Comparison 模块 +299;另有 60+ L3 fence |

### 8.3 整体结论

**ForgeUE vNext 基线满足验收条件**:

- 所有 FR/NFR 项已有自动化或指定手工手段覆盖
- 自动化部分 100% 通过
- 手工验收 A1 / A2 / A3 全部通过(2026-04-23 收尾)
- 不做项与未启动项有明确 ADR 或 TBD 条目

**vNext 主线闭合状态**(2026-04-23):
- A3 pricing probe ✅(2026-04-22)
- A2 char/image/review/mesh live ✅(2026-04-22)
- **A1 + a2_ue UE 真机 ✅(2026-04-23,UE 5.7.4 commandlet 全自动化)**
- L0 自动化 **848 用例全绿** ✅(2026-04-25 实测;历史基线 549,本轮 Run Comparison 模块 +299)
- 长期 bridge_execute 路径有 TBD-009(RemoteControl HTTP)+ ADR-008 兜底

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
| v1.2 | 2026-04-23 | A1 UE 真机 + a2_ue 合并通过(UE 5.7.4 commandlet 全自动化路径,Texture .uasset 真落盘 + 视觉确认):P4 ⚠️→✅ / FR-UE-003 ⏳→✅ / a2_ue 跳过→✅ / §3.1 + §4.7 + §6.1 + §6.2 + §6.4 五处状态升级;新增 ADR-008(启用 UE 自带 plugin 不算违反 ADR-001)+ TBD-009(RemoteControl HTTP bridge,future bridge_execute);新增 live bundle `examples/ue_export_pipeline_live.json`(原 `ue_export_pipeline.json` 留 ComfyUI 接口给 P4 集成测试)+ 入口脚本 `ue_scripts/a1_run.py`(后扩展为读 `FORGEUE_RUN_FOLDER` env 优先,支持复用跑不同 run_id) |
| v1.3 | 2026-04-23 | A2 全集 5/5 ✅ 重跑收尾(0423 重跑 a2_char/image/review/mesh):a2_mesh_0423 用新 `examples/image_to_3d_pipeline_live.json` 跑 Hunyuan 3D 33.3MB .glb + UE 5.7 commandlet 真 import → `Generated/Props/a2_mesh_0423/.../{StaticMeshes/SM_*, Materials/Material_001, Textures/texture_20250901}.uasset` 三类资产 + 用户 GUI 视觉确认 oak barrel 3D mesh;`test_example_bundles_smoke` 自动 parametrize 收 6 用例(2 个新 bundle × 3),总数 546 → 549 |
| v1.4 | 2026-04-25 | Run Comparison / 基线回归落地(OpenSpec change `add-run-comparison-baseline-regression`):新增 §6.8 验收记录,关闭 `README.md` §"后续扩展" 第 7 项 "`observability/run_comparison.py` 待补" 占位;Codex Review Gate 双轮 PASS(Task 4/5/6 各两轮);proposal.md 4 条 Success criteria 全部达成;Deferred follow-up `lazy-artifact-store-package-exports` 单独 change 待启;§8.1 自动化验收基线 549 → 848(基线 549 + Run Comparison 模块 ~299 新用例)|

### 9.3 签收区

| 角色 | 姓名 | 日期 | 签字 |
| --- | --- | --- | --- |
| 开发代表 | | | |
| QA / TA | | | |
| 项目发起人 | | | |
