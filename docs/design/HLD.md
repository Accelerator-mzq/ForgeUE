# ForgeUE 概要设计说明书 (High-Level Design)

| 字段 | 内容 |
| --- | --- |
| 文档编号 | FORGEUE-HLD-001 |
| 版本 | v1.0 |
| 基线日期 | 2026-04-22 |
| 文档性质 | 概要设计(High-Level Design) |
| 上位文档 | `docs/requirements/SRS.md` |
| 下位文档 | `docs/design/LLD.md` |

---

## 1. 引言

### 1.1 编写目的

本文档基于 SRS(需求规格说明书),从**系统分层 / 子系统划分 / 模块间协作 / 关键设计决策**层面描述 ForgeUE 架构,不涉及类 / 方法 / 字段级细节(那部分在 LLD)。

### 1.2 设计目标

| 目标 | 映射 SRS 需求 |
| --- | --- |
| 三 `RunMode` 共享调度器,不分裂实现 | FR-WF-002 |
| Provider 统一抽象 + 能力别名解耦 | FR-MODEL-001, FR-MODEL-006 |
| UE 侧文件契约交付,框架与 UE 进程解耦 | ADR-001, FR-UE-002 |
| async-first 执行 + sync-shim 兼容 | FR-RUNTIME-004, NFR-PERF-001 |
| 失败模式 → Decision 映射完备 | FR-RUNTIME-007, NFR-REL-001 |
| 可观测事件流 loop-aware + 线程安全 | FR-OBS-001, FR-OBS-004 |

### 1.3 关键术语

见 SRS §1.4,本文档沿用。

---

## 2. 总体架构

### 2.1 分层视图

```
┌────────────────────────────────────────────────────────────────────┐
│ 用户 / TA / UI / CI                                                 │
├────────────────────────────────────────────────────────────────────┤
│  入口层                                                              │
│  ├── CLI  (framework.run)                                           │
│  ├── WS Server (framework.server.ws_server)                         │
│  └── Python API (framework.run.Orchestrator.arun)                   │
├────────────────────────────────────────────────────────────────────┤
│  编排层 (src/framework/runtime/)                                         │
│  ├── Orchestrator   — 9 阶段 Run 生命周期                            │
│  ├── Scheduler      — risk_level 排序 / depends_on 拓扑              │
│  ├── DryRunPass     — 零副作用预检                                    │
│  ├── CheckpointStore — hash 快照 + resume                           │
│  ├── TransitionEngine — Verdict → 下一步                             │
│  ├── BudgetTracker  — 成本累加 + 软终止                               │
│  └── FailureModeMap — Exception → FailureMode → Decision            │
├────────────────────────────────────────────────────────────────────┤
│  执行器层 (src/framework/runtime/executors/)                             │
│  generate_structured / generate_image / generate_image_edit         │
│  generate_mesh / review / select / validate / export / mock         │
├────────────────────────────────────────────────────────────────────┤
│  能力路由层 (src/framework/providers/)                                   │
│  ├── CapabilityRouter — 按能力别名分发                                │
│  ├── ModelRegistry    — YAML 三段式注册 → PreparedRoute              │
│  └── ProviderAdapter  — 统一 4 方法接口                              │
│      ├── LiteLLMAdapter            (wildcard,最后注册)              │
│      ├── QwenMultimodalAdapter     (DashScope)                      │
│      ├── HunyuanTokenhubAdapter    (Image + 3D 基类)                │
│      └── FakeAdapter               (测试)                           │
│  └── workers/                                                       │
│      ├── ComfyWorker  (HTTP)                                        │
│      └── MeshWorker   (Hunyuan 3D / Tripo3D)                        │
├────────────────────────────────────────────────────────────────────┤
│  评审引擎 (src/framework/review_engine/)                                 │
│  LLMJudge / ChiefJudge (asyncio.gather panel)                       │
│  ReportVerdictEmitter / RubricLoader                                │
├────────────────────────────────────────────────────────────────────┤
│  对象与合约层 (src/framework/core/, src/framework/schemas/)                  │
│  Task / Run / Workflow / Step / Artifact                            │
│  UEOutputTarget / UEAssetManifest / UEImportPlan / Evidence         │
│  ReviewReport / Verdict / Checkpoint / Policies                     │
├────────────────────────────────────────────────────────────────────┤
│  存储层 (src/framework/artifact_store/)                                  │
│  Repository / PayloadBackend × 3(inline/file/blob)                  │
│  Lineage / VariantTracker / Hashing                                 │
├────────────────────────────────────────────────────────────────────┤
│  UE Bridge 层 (src/framework/ue_bridge/)                                 │
│  Inspect → Plan → (Execute 预留) → Evidence                         │
│  ManifestBuilder / ImportPlanBuilder / PermissionPolicy             │
├────────────────────────────────────────────────────────────────────┤
│  可观测 (src/framework/observability/)                                   │
│  EventBus (loop-aware) / ProgressEvent / Compactor / Secrets / OTel │
├────────────────────────────────────────────────────────────────────┤
│  UE 端代理 (ue_scripts/) — 独立 Python 包,仅依赖 import unreal      │
│  run_import / manifest_reader / domain_* / evidence_writer          │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 分层职责

| 层次 | 职责 | 边界 |
| --- | --- | --- |
| 入口层 | 暴露 CLI / WS / Python API | 不含业务逻辑 |
| 编排层 | Run 生命周期调度 | 不感知 provider 协议 |
| 执行器层 | Step 类型特定逻辑 | 通过 CapabilityRouter 获取能力 |
| 能力路由层 | Provider 抽象与选型 | 不感知 Workflow 语义 |
| 评审引擎 | Rubric 加载 + LLM judge 并发 | 被 ReviewExecutor 调用 |
| 对象与合约层 | Pydantic schema 定义 | 无运行时逻辑 |
| 存储层 | Artifact 落盘 + 血缘 | 不决定内容 |
| UE Bridge 层 | Manifest / Plan 构建 + 权限 | 不直接调 UE API |
| 可观测 | 事件 / 追踪 / 密钥 | 横切关注点 |
| UE 端代理 | UE 内 Python 导入 | 独立进程,文件契约通信 |

### 2.3 进程拓扑

```
┌─────────────────────────┐          文件契约           ┌──────────────────────┐
│ ForgeUE Python Process  │  ────────────────────▶      │  UE 5.x Editor       │
│                         │   manifest.json             │                      │
│  framework.run          │   import_plan.json          │  Python Console:     │
│  + Artifact Store       │   evidence.json  (seeded)   │  exec(run_import.py) │
│  + WS Server (可选)     │   texture.png/glb/wav       │                      │
│                         │                             │  ue_scripts/*.py     │
│                         │  (UE 侧 append 新的)         │  + import unreal     │
│                         │ ◀───── evidence.json  ──── │                      │
└─────────────────────────┘                             └──────────────────────┘

        │                                                        │
        │ WS (/ws/run/{run_id})                                   │
        ▼                                                        │
┌─────────────────────────┐                                      │
│ UI / CLI watcher        │                                      │
│ (浏览器 / 命令行)        │                                      │
└─────────────────────────┘                                      │

        │                                                        │
        │ HTTPS                                                  │
        ▼                                                        │
┌─────────────────────────┐                                      │
│  各 Provider API        │                                      │
│  OpenAI / Anthropic /   │                                      │
│  DashScope / Hunyuan /  │                                      │
│  GLM / MiniMax /        │                                      │
│  ComfyUI / Tripo3D      │                                      │
└─────────────────────────┘                                      │
```

---

## 3. 子系统划分

### 3.1 子系统清单

| 子系统 | 目录 | 对外接口 | 关键职责 |
| --- | --- | --- | --- |
| Core | `src/framework/core/` | Pydantic schema | 对象模型 + 枚举 + Policy |
| Schemas | `src/framework/schemas/` | `registry.py` | 业务 schema 注册 |
| Workflows | `src/framework/workflows/` | `load_task_bundle` | Bundle JSON 解析 |
| Providers | `src/framework/providers/` | `ProviderAdapter` / `CapabilityRouter` | 模型接入 + 路由 |
| Runtime | `src/framework/runtime/` | `Orchestrator.arun` | 生命周期编排 |
| Review Engine | `src/framework/review_engine/` | `ChiefJudge.ajudge_with_panel` | 评审与决策 |
| Artifact Store | `src/framework/artifact_store/` | `Repository.put / get` | Artifact 持久化 |
| UE Bridge | `src/framework/ue_bridge/` | `ManifestBuilder` / `ImportPlanBuilder` | UE 侧文件契约构建 |
| Observability | `src/framework/observability/` | `EventBus.publish` / `compact_messages` | 事件 + 追踪 + 密钥 |
| Server | `src/framework/server/` | `/ws/run` / `/ws/step` | WS 进度推送 |
| Pricing Probe | `src/framework/pricing_probe/` | CLI `--apply` | 定价自动化 |
| UE Scripts | `ue_scripts/` | `run_import.run()` | UE 内导入 |

### 3.2 依赖方向

```
server ──► runtime ──► providers ──► core
   │         │             │           ▲
   │         ▼             │           │
   │      executors ───────┘           │
   │         │                          │
   │         ▼                          │
   │      review_engine ────────────────┤
   │         │                          │
   │         ▼                          │
   │      artifact_store ───────────────┤
   │         │                          │
   │         ▼                          │
   │      ue_bridge ────────────────────┘
   │
   └──► observability (横切,所有层可调)

pricing_probe: 独立工具链,只读 config/models.yaml + 写入 (--apply)

ue_scripts/: 完全独立,不 import framework.*;仅依赖 import unreal
```

单向依赖,无循环。

---

## 4. 对象模型概览

### 4.1 核心对象关系

```
        Task                          (用户意图标准化入口)
         │
         ├── RunMode (三选一)
         ├── TaskType
         ├── input_payload
         ├── UEOutputTarget?           ───┐
         ├── ReviewPolicy?                │
         └── DeterminismPolicy?           │
         │                                 │
         ▼ 一对多                          │
        Run                                │
         │                                 │
         ├── Workflow                      │
         │    ├── Step × N                 │
         │    │   ├── type (11 种)         │
         │    │   ├── risk_level           │
         │    │   ├── depends_on           │
         │    │   ├── ProviderPolicy       │
         │    │   ├── RetryPolicy          │
         │    │   ├── TransitionPolicy     │
         │    │   └── output_schema        │
         │    │                            │
         │    └── metadata.parallel_dag?   │
         │                                 │
         ├── Artifact × N                  │
         │    ├── artifact_type            │
         │    ├── PayloadRef (3 态)        │
         │    ├── metadata (modality 专属) │
         │    ├── Lineage                  │
         │    └── ValidationRecord         │
         │                                 │
         ├── ReviewReport × N ────────────┐│
         ├── Verdict × N ─────────────────┤│
         ├── Checkpoint × N                ││
         ├── Evidence × N ─────────────────┘│
         └── RunResult                      │
              └── budget_summary            │
                                            │
        UEAssetManifest  ◄──────────────────┘
         ├── UEAssetEntry × N
         └── UEDependency × N
        UEImportPlan
         └── UEImportOperation × N
```

### 4.2 关键对象职责

| 对象 | 职责 | 备注 |
| --- | --- | --- |
| Task | 用户意图入口,声明 RunMode / 输入 / 输出期望 | 由 `load_task_bundle` 构造 |
| Run | Task 的一次执行,承载执行状态 | `run_id` 唯一 |
| Workflow | 带 Step 图的执行计划 | 支持线性 + DAG |
| Step | 最小执行单元 | 11 种 type |
| Artifact | 一等公民产物 | 三态 PayloadRef |
| Candidate / CandidateSet | 高发散生成的候选族 | 用于 review 前的选型 |
| ReviewReport | 分析说明(供人读) | 与 Verdict 分离 |
| Verdict | 流程控制结论(供机器读) | 9 种 decision |
| Checkpoint | Step 完成后的 hash 快照 | 支持 resume |
| UEAssetManifest | 声明式资产清单 | 交付 UE 侧 |
| UEImportPlan | 执行式导入计划 | UE 侧消费 |
| Evidence | UE 侧操作审计 | seeded by framework + appended by UE |
| PayloadRef | Artifact 载体抽象 | inline / file / blob |
| Lineage | 血缘关系 | source + transformation |
| ValidationRecord | 4 层校验结果 | 文件 / 元数据 / 业务 / UE |

字段级定义见 LLD。

---

## 5. Workflow 调度机制

### 5.1 Run 生命周期(9 阶段)

```
1. Task ingestion         → 解析 Task → RunMode → 加载 Workflow
2. Workflow resolution    → Step 实例化
3. Dry-run Pass           → 零副作用预检(失败 Run 直接 failed)
4. Scheduling plan        → depends_on + risk_level 生成计划
5. Step execution         → Executor 执行 → Checkpoint
6. Verdict dispatching    → review 产出 Verdict → TransitionEngine
7. Validation gates       → Artifact 入 Store 前 4 层校验
8. Export                 → UEAssetManifest + UEImportPlan
9. Run finalize           → 指标 / trace / lineage 归档
```

### 5.2 DryRunPass 预检项

```
- manifest 解析成功
- 所有 Step 的 output_schema 合法
- ProviderPolicy.preferred_models 可达
- input_bindings 能解析
- UEOutputTarget.project_root 可访问
- UE 侧路径无同名冲突(warn)
- Budget 估算不超 cap
- 付费步未声明 cap → warnings.budget.cap_declared
- Secrets 齐全
- Resume 时 artifact_hash 一致
```

### 5.3 调度规则

1. 构建 DAG(MVP 支持线性 + 分支,DAG 并发 opt-in)
2. 入度为 0 的 Step 先跑,同层按 `risk_level` 升序
3. 每 Step 完成:计算 `artifact_hash` → 写 Checkpoint → `TransitionEngine` 决策
4. revise 回环:每次触发 `max_revise` +1,超限自动 `Decision.reject`
5. DAG 并发:`asyncio.wait(FIRST_EXCEPTION)`,任一异常 cancel siblings
6. 并发上限:`ResourceBudget` 约束

### 5.4 Review 嵌入规则

标准插入位置:

- 高发散输出后(candidate review)
- 高成本转换前(quality gate)
- 导入 UE 前(compliance review)
- 失败分岔点(recovery review)

产出:`ReviewReport`(分析)+ `Verdict`(决策),两对象同时落库。

### 5.5 FailureMode ↔ Decision 映射

| FailureMode | 默认 Decision |
| --- | --- |
| provider_timeout | retry_same_step → fallback_model |
| schema_validation_fail | retry_same_step |
| review_below_threshold | revise |
| ue_path_conflict | human_review_required |
| budget_exceeded | escalate_human → stop |
| worker_timeout | retry_same_step |
| worker_error | fallback_model |
| unsupported_response | abort_or_fallback |
| disk_full | rollback → stop |

详见 LLD §5 `failure_mode_map.py`。

---

## 6. Policy 五件套

ForgeUE 将策略分为 5 类,互不覆盖:

| Policy | 作用域 | 关键字段 |
| --- | --- | --- |
| **TransitionPolicy** | Step 间转移 | `on_accept` / `on_revise` / `on_reject` / `on_fallback` / `max_revise` |
| **RetryPolicy** | Step 内部重试 | `max_attempts` / `retry_on`(FailureMode list) |
| **ProviderPolicy** | 模型选型 | `models_ref`(alias)/ `preferred_models` / `fallback_models` / `capability_required` |
| **BudgetPolicy** | Run 级成本封顶 | `total_cost_cap_usd` / `prompt_tokens_cap` |
| **EscalationPolicy** | 人工介入 | `on_exhausted`(retry 耗尽时)/ `on_budget_exceeded` |

附加 `DeterminismPolicy`(seed / version lock / hash verify)与 `ReviewPolicy`(pass_threshold / default_mode)独立存在。

---

## 7. UE Bridge 边界

### 7.1 双模并存

| 模式 | 触发 | 框架动作 | UE 侧动作 |
| --- | --- | --- | --- |
| **manifest_only**(MVP 默认) | `UEOutputTarget.import_mode="manifest_only"` | 产出 manifest + plan + evidence + 资产文件到 `<UE项目>/Content/Generated/<run_id>/` | UE Python Console 手动 `exec(run_import.py)` |
| **bridge_execute**(后置) | `import_mode="bridge_execute"` | 额外调用 Python Editor Scripting | 框架进程直接操作 UE(需 UE 已启动) |

**MVP 只启用 manifest_only**,bridge_execute 待稳定后评估。

### 7.2 职责边界

| ✅ 做 | ❌ 不做 |
| --- | --- |
| 读 manifest | 决定资产应该长什么样 |
| 生成 import plan | 自己生成资产 |
| 执行低风险导入 | 修改已有关键资产 |
| 返回 evidence | 绕过 Verdict |
| 写审计日志 | 改 GameMode / 默认地图 |
| 记录 rollback hint | 跨项目批量操作 |

### 7.3 权限层

`PermissionPolicy` 默认拒绝 Phase C 操作(创建材质 / 音频 cue),需显式 allow_flag。

### 7.4 导入能力矩阵

| 资产类 | Manifest 支持 | UE Bridge MVP | Phase C |
| --- | --- | --- | --- |
| Texture | ✅ | ✅ | — |
| Static Mesh | ✅ | ✅ | — |
| Sound Wave | ✅ | ✅ | — |
| Material | 定义 | 只读 | 创建(需 allow) |
| Sound Cue | 定义 | 只读 | 创建(需 allow) |

---

## 8. Provider 层与 ModelRegistry

### 8.1 三段式 YAML

```
providers:      # 连接信息(api_base / api_key_env / protocol)
  zhipu: { api_base: ..., api_key_env: GLM_API_KEY }
  dashscope: { ... }
  ...

models:         # 模型身份 + 能力 + 定价
  glm_4_6v:
    provider: zhipu
    model_id: glm-4.6v
    capability: [text.structured, review.visual]
    pricing: { input_per_1k_usd: 0.000139, ... }
    pricing_autogen: { status: fresh, sourced_on: ..., source_url: ... }

aliases:        # 能力别名 → 模型候选链
  review_judge_visual:
    models: [glm_4_6v, qwen_vl_max]
```

### 8.2 PreparedRoute

`ModelRegistry` 为每条 alias 展开 `(model_id, api_key_env, api_base, kind)` 四元组列表,供 `ProviderAdapter.supports(model_id)` 匹配。

### 8.3 CapabilityRouter 分发

```
call_site → CapabilityRouter.completion(capability, call)
          → for adapter in registered_adapters:
                if adapter.supports(call.model): break
          → adapter.acompletion(call)
          → 把 route_pricing 塞进 result.raw["_route_pricing"]
```

注册顺序约束:`LiteLLMAdapter`(wildcard `supports(*) == True`)**必须最后注册**,否则专用前缀(`qwen/` / `hunyuan/`)会被它吞掉。

### 8.4 接入新 Provider

| 类型 | 成本 |
| --- | --- |
| OpenAI 兼容端口 | **零代码**,只改 YAML(`api_base` + `api_key_env`,bundle 写 `openai/<id>`) |
| 非 OpenAI 协议 | 加一个 `providers/*_adapter.py`,实现 4 方法 async 接口 |

---

## 9. 异步与并发模型(Plan C)

### 9.1 async-first + sync-shim

`ProviderAdapter` 主接口是 `acompletion / astructured / aimage_generation / aimage_edit`,同名 sync 方法自动 `asyncio.run` 桥接。旧代码零改动。

### 9.2 关键并发场景

| 场景 | 机制 | 收益 |
| --- | --- | --- |
| 多候选生成 | Step 配置 `parallel_candidates=True`,`asyncio.gather(*[_one(i) for i in range(n)])` | N 倍加速 |
| ChiefJudge panel | `ajudge_with_panel` 内 `asyncio.gather` | 总延迟 ≈ 最慢 judge |
| Hunyuan `n>1` fan-out | `aimage_generation` 内 `asyncio.gather(N submit/poll/download)` | N 倍加速(tokenhub 单次只接一条 prompt) |
| DAG 并发 | `Orchestrator.arun` + `asyncio.wait(FIRST_EXCEPTION)` | fan-out 3 step → 墙钟 ≈ 单步 |

### 9.3 取消 / 超时

- Poll 循环 `await asyncio.sleep` 后不吞 `CancelledError`
- 外层硬超时:`asyncio.wait_for(adapter.acompletion(call), timeout=T)`
- DAG 级联:任一 step 异常立即 cancel siblings + re-raise
- 限制:同步 Executor 内的 `time.sleep` 无法强制中断(Python 线程限制)

### 9.4 下载与 Range 续传

- `chunked_download_async()` 1MB 分块,中断走 HTTP Range 续传(最多 3 次重试)
- **续传强校验**:buf 非空时必须 `206` + `Content-Range` 起始偏移 = `len(buf)`;其他形态一律清空重下
- 轮询进度回调:`(status, elapsed_s, raw_resp)` 自适应签名

---

## 10. 可观测与 EventBus

### 10.1 事件流拓扑

```
Adapter (poll loop) ──publish(ProgressEvent)──> EventBus
Orchestrator (step_start/step_done) ──┘   (asyncio.Queue × N subscribers)
Workers (mesh_poll / comfy_poll) ─────┘
                                             ↓ fan-out per subscriber
                                      Starlette WebSocket handler
                                             ↓ JSON
                                      Client (UI / CLI watcher)
```

### 10.2 EventBus loop-aware

- `Subscription` 捕获 owning event loop
- `publish_nowait` 检测跨线程后走 `loop.call_soon_threadsafe(put_nowait, ...)` hop 到 queue 的 owning loop
- `_subs` 用 `threading.Lock` 保护增删
- 解决"asyncio.Queue 非线程安全 + 无锁 _subs 列表"的跨线程隐患

### 10.3 WS server 空闲态安全

`ws_run` / `ws_step` 用 `asyncio.wait(FIRST_COMPLETED)` 同时 race 事件与 `receive_disconnect`,空闲期客户端关连不留泄露 `Subscription`。

### 10.4 ProgressEvent schema

```
event_type: step_start | step_progress | step_done | step_failed
          | adapter_poll | worker_poll
          | run_start | run_done | run_failed
run_id, step_id?, timestamp
payload: { status, elapsed_s?, progress?, cost_usd?, ... }
```

---

## 11. 跨功能视图

### 11.1 可靠性

- 所有异常 → FailureMode → Decision(`failure_mode_map.py`)
- 瞬态重试:SSL EOF / 超时 / 5xx → 2s 回退 × 1 次(`with_transient_retry*`)
- Checkpoint resume:hash 不匹配直接失败
- DAG 级联 cancel

### 11.2 可复现

- `DeterminismPolicy.seed_propagation`:seed 向下游传递
- `model_version_lock`:禁止版本漂移
- `hash_verify_on_resume`:resume 前核对
- LiteLLM `drop_params=True`:Anthropic 不认识的 `seed` 自动丢弃

### 11.3 成本追踪

- `BudgetTracker` 每步累计
- 超 `total_cost_cap_usd` → 合成 `budget_exceeded` Verdict → 终止
- `models.yaml` 三 estimator:`estimate_call_cost_usd` / `estimate_image_call_cost_usd` / `estimate_mesh_call_cost_usd`
- Route pricing 通过 `raw["_route_pricing"]` 透传(不破 tuple 签名)
- Pricing probe 自动刷新:httpx + playwright 双后端,`pricing_autogen.status` 审计

### 11.4 安全

- `.env` + 环境变量注入
- `observability/secrets.py` 统一脱敏
- WS 默认绑定 `127.0.0.1`

---

## 12. 外部接口总览

| 接口 | 协议 | 子系统 |
| --- | --- | --- |
| CLI | argparse | `src/framework/run.py` |
| WebSocket | JSON over WS | `src/framework/server/ws_server.py` |
| HTTPS(Provider) | 各 provider REST | `src/framework/providers/*` |
| File(UE 契约) | JSON / 资产文件 | `src/framework/ue_bridge/*` + `ue_scripts/*` |
| YAML / JSON 配置 | 文件读 | `config/models.yaml` / `examples/*.json` |

详细字段见 LLD §9 与 SRS §5。

---

## 13. 关键设计决策摘要

| ADR | 决策 | 影响 |
| --- | --- | --- |
| ADR-001 | ForgeUE 不做 UE 插件 | 保持 CI 可跑 + 网络合规 + 多工程复用 |
| ADR-002 | `config/models.yaml` 单一真源 | 避免 schema 漂移 |
| ADR-003 | `LiteLLMAdapter` 必须最后注册 | wildcard 匹配问题 |
| ADR-004 | 外部事实性数据必须可验证 | 拒绝 fabrication |
| ADR-005 | `plan_v1` 降级为归档 | 权威转为五件套 |

---

## 14. 附录

### 14.1 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0 | 2026-04-22 | 初始基线,从 plan_v1 §A-C+E+L+N 拆分重组 |

### 14.2 参考

- `docs/requirements/SRS.md` — 需求基线
- `docs/design/LLD.md` — 详细设计(字段 / 方法 / 算法)
- `docs/archive/claude_unified_architecture_plan_v1.md` — 原稿史料
