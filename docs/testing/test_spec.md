# ForgeUE 系统测试用例说明书 (System Test Specification)

| 字段 | 内容 |
| --- | --- |
| 文档编号 | FORGEUE-TEST-001 |
| 版本 | v1.0 |
| 基线日期 | 2026-04-22 |
| 文档性质 | 系统测试用例规格 |
| 上位文档 | `docs/requirements/SRS.md`、`docs/design/LLD.md` |
| 下位文档 | 源代码 `tests/` 与 `docs/acceptance/acceptance_report.md` |

---

## 1. 引言

### 1.1 编写目的

本文档规定 ForgeUE 的测试**策略、组织、用例矩阵、覆盖分析、测试环境与数据**,与 SRS 的 FR/NFR 需求条目一一追溯,为验收提供可执行的检查清单。

### 1.2 测试原则

| 原则 | 说明 |
| --- | --- |
| **测试即可执行规范** | 491 个 pytest 用例本身是测试规范,本文档不重复描述每个用例的断言细节,只建立索引与矩阵 |
| **零 mock 关键边界** | download / EventBus / DAG / Budget / artifact 流端到端真实对象,不得 mock |
| **每次修复配一个 fence** | Codex / adversarial review 每条修复对应一个新回归测试 |
| **单元测试快** | `pytest -q` 全量 ≤ 15s,CI 节奏保证 |
| **集成测试表意清晰** | 每个 P0–P4 集成测试一个闭环场景,命名与 SRS 章节对齐 |
| **fence 测试守门** | 反 fabrication / 反 regression / 反语法回退 |

### 1.3 术语

| 术语 | 说明 |
| --- | --- |
| 单元测试 | `tests/unit/*.py`,单模块行为 |
| 集成测试 | `tests/integration/*.py`,端到端场景 |
| fence 测试 | 守门类测试,检测特定修复不得再次退化 |
| fixture | 测试固定数据,含 HTML / bundle / stub 模块 |
| smoke 测试 | 冒烟测试,快速检查主干可用性 |
| stub | 假对象,替代真实依赖(如 UE `unreal` 模块) |

---

## 2. 测试策略

### 2.1 测试金字塔

```
           ┌─────────────────────────┐
           │ 手工验收(A1 UE 真机)   │   ← 验收文档管辖
           ├─────────────────────────┤
           │ Live LLM smoke(A2)     │   ← 可选,需 API key
           ├─────────────────────────┤
           │ 集成测试 × 10 文件      │   ← P0-P4 + 场景级
           ├─────────────────────────┤
           │ 单元测试 × 42 文件 481 用例│   ← 主体
           └─────────────────────────┘
```

### 2.2 测试分类

| 类别 | 目录 | 文件数 | 用例数 | 运行时间 |
| --- | --- | --- | --- | --- |
| 单元测试 | `tests/unit/` | 42 | ~481 | < 10s |
| 集成测试 | `tests/integration/` | 10 | ~10 | < 5s |
| **合计** | — | **52** | **491** | **< 15s** |

### 2.3 执行方式

```bash
# 全量
python -m pytest -q

# 阶段集成
python -m pytest tests/integration/test_p{0,1,2,3,4}_*.py -v

# 指定模块单测
python -m pytest tests/unit/test_event_bus.py -v

# 手工产物落盘(不回收 tmp_path)
python -m pytest <test> --basetemp=./demo_artifacts/<name>

# CLI 离线冒烟(无需 API key)
python -m framework.run --task examples/mock_linear.json \
    --run-id demo --artifact-root ./artifacts

# CLI live smoke(需 .env 配置 provider key)
python -m framework.run --task examples/image_pipeline.json --live-llm ...
```

### 2.4 测试级别定义

| Level | 含义 |
| --- | --- |
| L0 smoke | 启动能跑,基础流程不抛异常 |
| L1 feature | 单功能正确性 |
| L2 edge | 边界 / 异常 / 错误处理 |
| L3 regression fence | 守门已修复问题不复发 |
| L4 integration | 多模块串联端到端 |

---

## 3. 单元测试用例矩阵

### 3.1 核心对象与 Schema

| 文件 | 覆盖模块 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_core_schemas.py` | `core/*.py` Pydantic 对象 | FR-STORE-*, FR-REVIEW-* | L1 | Task/Run/Artifact/Verdict 字段校验 |
| `test_model_registry.py` | `providers/model_registry.py` | FR-MODEL-001 | L1,L2 | 三段式解析、alias resolve、未知字段 raise |
| `test_registry_pricing.py` | `providers/model_registry.py` pricing 扩展 | FR-COST-001, FR-COST-002 | L1,L2 | `pricing:` block 解析、`pricing_autogen` 审计块、typo raise |
| `test_payload_backends.py` | `artifact_store/payload_backends/*` | FR-STORE-002, FR-STORE-003 | L1 | inline 64KB 上限、file 落盘、blob 预留 |
| `test_artifact_repository.py` | `artifact_store/repository.py` | FR-STORE-001 | L1 | put / get / by_run / by_lineage |
| `test_checkpoint_store.py` | `runtime/checkpoint_store.py` | FR-LC-004, FR-LC-005 | L1,L2 | save/load/hash verify on resume |

### 3.2 Runtime

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_scheduler_risk_ordering.py` | `runtime/scheduler.py` | FR-WF-005 | L1 | 同层按 risk_level 升序 |
| `test_dry_run_pass.py` | `runtime/dry_run_pass.py` | FR-LC-002, FR-LC-003 | L1,L2 | manifest / schema / provider / secrets 预检 |
| `test_cascade_cancel.py` | `runtime/orchestrator.py` | FR-WF-007, NFR-REL-006 | L3 | DAG retry/terminate 级联语义,`test_dag_retry_same_step_reexecutes` 守门 plan_v1 §M 第一轮修复 |
| `test_failure_mode_map.py` | `runtime/failure_mode_map.py` | FR-RUNTIME-007, NFR-REL-001 | L1,L2 | 9 类 FailureMode 分类、unsupported 子类顺序 |
| `test_transition_engine.py` | `runtime/transition_engine.py` | FR-REVIEW-003 | L1,L2 | 9 Decision 分支、revise / retry caps、abort_or_fallback honour on_fallback |
| `test_budget_tracker.py` | `runtime/budget_tracker.py` | FR-RUNTIME-001 | L1,L2 | 累计、超 cap 终止 |
| `test_budget_tracker_pricing.py` | 同上 + pricing | FR-COST-003, FR-COST-004 | L1 | 三 estimator、route_pricing 优先级 |
| `test_retry_async.py` | `providers/_retry_async.py` | FR-RUNTIME-005 | L1 | 瞬态重试成功/失败路径 |
| `test_transient_retry.py` | `providers/_retry.py` | FR-RUNTIME-005 | L1 | sync 同上 |
| `test_cancellation.py` | async 取消 | FR-RUNTIME-004, NFR-REL-006 | L2 | poll CancelledError 透传、超时 |

### 3.3 Providers

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_providers.py` | 基础注册 + 路由 | FR-MODEL-006 | L1 | wildcard 最后注册、alias 展开 |
| `test_providers_async.py` | async 四方法 | FR-MODEL-001 | L1 | acompletion / astructured / aimage / aimage_edit 契约 |
| `test_cn_image_adapters.py` | Qwen / Hunyuan Image | FR-MODEL-003, FR-WORKER-005 | L1,L2,L3 | 国内 image adapter 全路径、Range 续传、n>1 真并发 |
| `test_download_async.py` | `_download_async.py` | FR-WORKER-005, NFR-REL-* | L2,L3 | Range 强校验、200 fallback、Content-Range offset 不对齐清空重下 |
| `test_adapter_budget_clamp.py` | HTTP 下载 budget clamp | FR-WORKER-004, NFR-REL-* | L3 | per-image 30s clamp / mesh 90s clamp / LiteLLM 60s clamp |
| `test_comfy_http_unsupported.py` | ComfyWorker 三处 unsupported | FR-WORKER-*, NFR-REL-005 | L3 | spec 缺 workflow_graph / /prompt 无 id / outputs 无图 |
| `test_tripo3d_unsupported.py` | Tripo3D 两处 unsupported | 同上 | L3 | /task 无 task_id / success 无 URL |
| `test_multi_candidate_parallel.py` | `parallel_candidates=True` | NFR-PERF-003 | L2 | asyncio.gather 真并发,墙钟验证 |
| `test_router_pricing_stash.py` | route_pricing 透传 | FR-COST-004 | L1 | `_route_pricing` 塞进 raw / usage |

### 3.4 Review Engine

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_chief_judge_parallel.py` | `chief_judge.py` panel | FR-REVIEW-007, NFR-PERF-002 | L2 | asyncio.gather 并发,墙钟 ≈ 最慢 judge |
| `test_review_budget.py` | ReviewExecutor cost 透传 | FR-REVIEW-008, FR-COST-* | L3 | usage 3-tuple 透传到 BudgetTracker |

### 3.5 Observability

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_event_bus.py` | `event_bus.py` | FR-OBS-001, FR-OBS-002 | L2,L3 | Subscription 捕获 owning loop、跨线程 hop 通过 call_soon_threadsafe、threading.Lock 保护 _subs |
| `test_progress_passthrough.py` | adapter → ProgressEvent | FR-OBS-002, NFR-OBS-004 | L2 | mesh/comfy poll 事件传递 |
| `test_compactor.py` | `compactor.py` | FR-RUNTIME-003 | L1 | target_tokens 压缩、占位符插入 |
| `test_secrets.py` | `secrets.py` | NFR-SEC-002, NFR-SEC-003 | L1 | API key 脱敏 |

### 3.6 UE Bridge

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_ue_bridge.py` | `ue_bridge/*` | FR-UE-001 ~ FR-UE-008 | L1,L2 | ManifestBuilder modality 映射、PlanBuilder depends_on、Permission Phase C 默认拒绝、inspect_project / asset_exists、validate_manifest 重复路径、evidence 原子追加 |

### 3.7 Mesh / Generate

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_generate_mesh_cost.py` | `executors/generate_mesh.py` | FR-COST-003, FR-MODEL-003 | L1,L3 | mesh 从 prepared_routes 读 pricing,metrics["cost_usd"] 非 0 |

### 3.8 Pricing Probe

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_pricing_probe_framework.py` | 框架级 + scaffold fence | FR-COST-005 ~ FR-COST-007 | L1,L3 | CLI dry-run / --apply 语义、ruamel.yaml 保留注释、scaffold parser 仍 raise NotImplementedError |
| `test_pricing_parser_zhipu.py` | Zhipu parser | FR-COST-006 | L1 | GLM-4.6V 短 context tier 单价、GLM-Image 单张价 |
| `test_pricing_parser_hunyuan_3d.py` | Hunyuan 3D parser | FR-COST-006 | L1 | 15 积分 × ¥0.12/积分 = ¥1.80/次 ≈ USD 0.25 |
| `test_pricing_parser_hunyuan_image.py` | Hunyuan Image parser | FR-COST-006 | L1 | ¥0.5/张 postpaid tier |
| `test_pricing_parser_dashscope.py` | DashScope parser(6 模型) | FR-COST-006 | L1 | 精确匹配首列 + 按表头定位价格列、qwen-plus 128K tier |

### 3.9 Probe / Cleanup

| 文件 | 覆盖 | 对应需求 | Level | 关键用例 |
| --- | --- | --- | --- | --- |
| `test_probe_framework.py` | `probe_*.py` 的 lazy-init | NFR-MAINT-* | L3 | 无 API key 环境 import 不崩 |
| `test_pr3_cleanup_fences.py` | URL scheme 大小写 / magic gate / module-level I/O | — | L3 | PR-3 共性平移守门 |

---

## 4. 集成测试场景

### 4.1 P0–P4 主线闭环

| 文件 | RunMode | 对应需求 | 验证内容 |
| --- | --- | --- | --- |
| `test_p0_mock_linear.py` | basic_llm | FR-WF-001, FR-LC-* | 3 个 Checkpoint 落库,resume 命中 |
| `test_p1_structured_extraction.py` | basic_llm | FR-STRUCT-* | schema 合法 JSON,retry 次数 ≤ 2 |
| `test_p2_standalone_review.py` | standalone_review | FR-REVIEW-001, FR-REVIEW-002 | ReviewReport + Verdict 落库,scores_by_dimension 齐 |
| `test_p3_production_pipeline.py` | production | FR-WF-001, FR-WF-006 | prompt → review 收敛,max_revise 内 |
| `test_p4_ue_manifest_only.py` | production + ue_export | FR-UE-002, FR-UE-003 | manifest + plan + evidence 三件套落盘,stub unreal 跑通 `run_import.py` |

### 4.2 场景级

| 文件 | 对应需求 | 验证内容 |
| --- | --- | --- |
| `test_l4_image_to_3d.py` | FR-WORKER-002 | image.raster → mesh.gltf 全链 |
| `test_image_edit.py` | FR-MODEL-003 | image_edit capability |
| `test_dag_concurrency.py` | FR-WF-007, NFR-PERF-001 | `parallel_dag=True` fan-out,墙钟验证 |
| `test_ws_progress.py` | FR-OBS-003, FR-OBS-004 | WS endpoint 订阅 + 事件推送 + idle disconnect |
| `test_example_bundles_smoke.py` | FR-WF-001 | `examples/*.json` 每份 loader + Orchestrator 不抛 |

---

## 5. Fence 测试清单(L3 专属)

以下 fence 每条对应 plan_v1 §M 一次修复,防止回退。

| Fence | 守护修复 | 文件 |
| --- | --- | --- |
| DAG retry_same_step 被吞 | plan_v1 §M 第一轮 adv #1 | `test_cascade_cancel::test_dag_retry_same_step_reexecutes` |
| Review cost_usd 缺失 | 第一轮 | `test_review_budget` |
| Range 续传强校验 | 第一轮 adv #1 | `test_download_async::test_continue_requires_206_with_matching_offset` |
| EventBus loop-aware | 第一轮 adv #2 | `test_event_bus::test_cross_thread_publish_hops_to_owning_loop` |
| Hunyuan n>1 真并发 | 第一轮 adv #3 | `test_cn_image_adapters::test_hunyuan_aimage_n3_runs_three_submits` |
| Mesh glTF external-buffer | 第二轮 | `test_cn_image_adapters`(mesh 侧) |
| Mesh URL fallthrough | 第二轮 | 同上 |
| Mesh 多 URL 吃 budget | 第二轮 | 同上 |
| Mesh download error fallthrough | 第二轮 | 同上 |
| Mesh 空 ranked → unsupported | 第二轮 | 同上 |
| Mesh ASCII FBX 识别 | 第二轮 | 同上 |
| Mesh glTF parse-fail double-guard | 第二轮 | 同上 |
| `data:` URI 大小写 | 第二轮 | 同上 |
| unsupported → abort_or_fallback | 第二轮 | `test_transition_engine::test_abort_or_fallback_honours_on_fallback` |
| Probe runtime 格式检测一致 | 第二轮 | `test_probe_framework` |
| GLM probe import 副作用 | 第二轮 | `test_probe_framework::test_glm_probes_lazy_init` |
| Comfy 三处 unsupported | 第三轮 PR-1 | `test_comfy_http_unsupported` |
| Tripo3D 两处 unsupported | 第三轮 PR-1 | `test_tripo3d_unsupported` |
| Hunyuan image submit 无 id | 第三轮 PR-1 | `test_cn_image_adapters` |
| DashScope 空 choices | 第三轮 PR-1 | `test_cn_image_adapters` |
| LiteLLM image_generation 无 data | 第三轮 PR-1 | `test_providers_async` |
| 下载 remaining budget(3 家) | 第三轮 PR-2 | `test_adapter_budget_clamp` |
| Magic bytes gate(runtime) | 第三轮 PR-3 | `test_cn_image_adapters` |
| Hunyuan image URL fallthrough | 第三轮 PR-3 | `test_cn_image_adapters` |
| HTTP URL scheme 大小写 | 第三轮 PR-3 | `test_pr3_cleanup_fences` |
| Probe lazy-init | 第三轮 PR-3 | `test_pr3_cleanup_fences` / `test_probe_framework` |
| Pricing YAML typo 子字段 raise | 第四轮 | `test_registry_pricing` |
| Route pricing 透传 raw["_route_pricing"] | 第四轮 | `test_router_pricing_stash` |
| Mesh cost 非 0 | 第四轮 | `test_generate_mesh_cost` |
| Fabricated pricing 止血 | 第五轮 | `test_registry_pricing`(YAML null + TODO) |
| Scaffold parser must raise NotImplementedError | 第五轮 | `test_pricing_probe_framework::test_every_scaffold_parser_still_raises_notimplemented` |
| Playwright 后端 + fixture | 第六轮 | `test_pricing_parser_*`(3 家)|

---

## 6. 覆盖分析

### 6.1 需求覆盖矩阵(摘要)

| SRS 需求族 | 覆盖测试文件 | 状态 |
| --- | --- | --- |
| FR-WF(工作流) | integration/test_p0~p4, test_dag_concurrency, test_scheduler_risk_ordering, test_cascade_cancel | ✅ |
| FR-LC(生命周期) | test_dry_run_pass, test_checkpoint_store, integration/test_p0 | ✅ |
| FR-MODEL(编排) | test_model_registry, test_providers(_async), test_cn_image_adapters | ✅ |
| FR-STRUCT(结构化) | integration/test_p1 | ✅ |
| FR-REVIEW(评审) | integration/test_p2, test_chief_judge_parallel, test_review_budget | ✅ |
| FR-STORE(Artifact) | test_core_schemas, test_artifact_repository, test_payload_backends | ✅ |
| FR-UE(UE Bridge) | test_ue_bridge, integration/test_p4 | ✅(stub) |
| FR-WORKER(多模态) | test_cn_image_adapters, test_comfy_http_unsupported, test_tripo3d_unsupported, integration/test_l4 | ✅ |
| FR-RUNTIME(工程化) | test_failure_mode_map, test_transition_engine, test_budget_tracker, test_cancellation, test_transient_retry, test_retry_async, test_cascade_cancel | ✅ |
| FR-COST(定价) | test_registry_pricing, test_budget_tracker_pricing, test_router_pricing_stash, test_generate_mesh_cost, test_pricing_* | ✅ |
| FR-OBS(观测) | test_event_bus, test_progress_passthrough, test_compactor, test_secrets, integration/test_ws_progress | ✅ |

### 6.2 NFR 覆盖

| NFR 族 | 覆盖方式 |
| --- | --- |
| NFR-PERF | test_dag_concurrency(墙钟),test_chief_judge_parallel(并发),test_multi_candidate_parallel(N 候选) |
| NFR-REL | test_failure_mode_map,test_cascade_cancel,test_transition_engine |
| NFR-REPRO | test_checkpoint_store(hash verify),integration/test_p0(resume) |
| NFR-SEC | test_secrets |
| NFR-OBS | test_event_bus,test_progress_passthrough |
| NFR-MAINT | 所有 L3 fence 守门 + 总用例数 491 |
| NFR-PORT | CI 能在 Linux 跑(491 全绿,stub unreal 覆盖 P4) |

### 6.3 未覆盖 / 部分覆盖

| 项 | 状态 | 说明 |
| --- | --- | --- |
| A1 UE 真机冒烟 | **手工验收** | stub 覆盖框架侧,真 UE API 调用无自动化 |
| Live LLM 端到端 | **手工验收** | 需 provider key,默认不在 CI 跑 |
| Pricing probe `--apply` 真跑 | **手工验收** | playwright + chromium + 供应商页面可达 |
| bridge_execute 模式 | **未启动** | §G #1 |
| Audio worker | **未启动** | §G #2 |
| WS 鉴权 | **未启动** | 默认绑 127.0.0.1 |
| FBX self-containment | **未启动** | 无 PyFBX 绑定 |
| DashScope / Tripo3D parser 实装 | **部分** | 8 model scaffold,实装待真实用例 |

---

## 7. 测试环境

### 7.1 软件环境

| 项 | 版本 |
| --- | --- |
| Python | 3.12+ |
| pytest | 7.x+ |
| httpx | 0.27+ |
| pydantic | 2.x |
| litellm | 最新稳定 |
| instructor | 最新稳定 |
| ruamel.yaml | 0.18+ |
| playwright(可选) | 1.40+,需 `playwright install chromium` |
| UE(真机验收) | 5.3+ |

### 7.2 硬件建议

| 用途 | 要求 |
| --- | --- |
| 单元测试 | 4GB RAM,无 GPU |
| 集成测试 | 8GB RAM |
| Live LLM smoke | 外网可达 provider endpoint |
| Pricing probe --apply | 4GB+ 空闲(playwright/chromium) |
| UE 真机 | UE 5.3+ 装机,推荐 16GB RAM |

### 7.3 测试数据

| 位置 | 内容 |
| --- | --- |
| `tests/fixtures/pricing/*.html` | 5 家 provider 定价页真实 HTML 快照(280KB Hunyuan 3D 最大) |
| `examples/*.json` | 5 份 TaskBundle JSON |
| `framework/review_engine/rubric_templates/*.yaml` | 3 份 rubric |
| `config/models.yaml` | 模型注册表(测试通过 `ModelRegistry.reset()` 隔离) |
| 临时产物 | `pytest --basetemp=./demo_artifacts/<name>` 手工保留 |

### 7.4 环境变量

| Key | 用途 | 单元测试 | Live smoke |
| --- | --- | --- | --- |
| `DASHSCOPE_API_KEY` | Qwen | ❌ | ✅ |
| `HUNYUAN_API_KEY` | Hunyuan Image | ❌ | ✅ |
| `HUNYUAN_3D_KEY` | Hunyuan 3D | ❌ | ✅ |
| `GLM_API_KEY` | Zhipu | ❌ | ✅ |
| `PACKYCODE_API_KEY` | Claude via Packy | ❌ | ✅ |
| `MINIMAX_API_KEY` | MiniMax | ❌ | ✅ |
| `FORGEUE_RUN_FOLDER` | UE 真机 run 目录 | ❌ | ❌(UE 侧) |

---

## 8. 测试通过标准

| 级别 | 标准 |
| --- | --- |
| 单元测试 | 100% 通过(491 用例) |
| 集成测试 | P0–P4 + 5 场景全绿 |
| Fence 测试 | 每条守护修复不得回退 |
| 覆盖率 | 每条 FR 至少 1 个对应测试(矩阵 §6.1 全部 ✅) |
| 性能 | 全量 `pytest -q` ≤ 15s |
| 手工验收 | A1 UE 真机、A2 live LLM、A3 pricing probe 按验收文档勾选 |

---

## 9. 测试变更管理

### 9.1 新增测试触发条件

| 触发 | 行动 |
| --- | --- |
| 新增 FR / NFR | 配对至少一个单测 + 更新矩阵 §6.1 |
| Codex / adversarial review 修复 | 配对一个 L3 fence + 更新 §5 清单 |
| 新 Provider 接入 | 扩 `test_providers_async` + adapter 专属 fence |
| 新 Executor 类型 | 扩集成场景 + 对应单测 |

### 9.2 废弃测试流程

- 单元测试对应功能删除 → 同步删除测试
- Fence 测试守护的代码重写但语义不变 → 保留 fence
- 测试因环境不可达间歇性失败 → 加 `pytest.mark.skipif` + 注释说明原因

---

## 10. 附录

### 10.1 追溯矩阵

每条 SRS FR/NFR → 测试文件 → plan_v1 或 HLD/LLD 章节:见 §3、§4、§6 交叉表。

### 10.2 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0 | 2026-04-22 | 初始基线,491 用例索引化,fence 清单对齐 plan_v1 §M |

### 10.3 未决事项

| 编号 | 事项 |
| --- | --- |
| TBD-T-001 | 接入 Linux CI(当前仅本地 Windows 验证) |
| TBD-T-002 | 覆盖率工具接入(`pytest-cov` 补量化指标) |
| TBD-T-003 | Live LLM smoke 固化为可选 CI job |
