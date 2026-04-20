# forgeue

> UE 生产链多模型运行时框架 · vNext

以 `Task / Run / Workflow / Artifact` 为一等公民，把"**多模型生成 + 评审闸门 + UE 落地**"串成一条可复现、可审计、可重放的生产链。

- **三种运行模式**：`basic_llm`（结构化问答）· `production`（多模态生成 + 内嵌评审）· `standalone_review`（独立评审链）
- **UE Bridge（manifest-only）**：产出 `UEAssetManifest + UEImportPlan + Evidence`，UE 侧 Python 脚本一键执行导入
- **基础层直接用开源**：[LiteLLM](https://github.com/BerriAI/litellm) 统一 provider 调用 + [Instructor](https://github.com/567-labs/instructor) 做结构化输出；**运行时、评审、UE 领域全自研**
- **测试驱动**：143 条测试覆盖 P0–P4 全阶段 + 单元级断言，全部可离线跑（`FakeAdapter` + `FakeComfyWorker`）

---

## 目录

- [快速开始](#快速开始)
- [架构概览](#架构概览)
- [目录结构](#目录结构)
- [Bundle 与 Example](#bundle-与-example)
- [模型别名注册表](#模型别名注册表)
- [运行时特性](#运行时特性)
- [测试](#测试)
- [端到端验收路径](#端到端验收路径)
- [文档导航](#文档导航)
- [后续扩展](#后续扩展)

---

## 快速开始

### 1. 安装依赖

```bash
# 基础 + dev + LLM 依赖一次性装好
pip install -e ".[dev,llm]"
```

说明：
- `[dev]` = `pytest` + `pytest-cov`
- `[llm]` = `litellm` + `instructor`（从 PyPI 拉开源包，不是本仓库源码）
- 不装 `[llm]` 也能跑全部测试（测试用 `FakeAdapter` 绕过真实 LLM）

### 2. 配置密钥

```bash
cp .env.example .env       # Windows: copy .env.example .env
# 然后编辑 .env，填真实 API key（至少一个 provider）
```

`.env` 已在 `.gitignore` 内，不会被提交。`.env.example` 里标出了所有 provider 及其对应的 `<VENDOR>_API_KEY` + `<VENDOR>_API_BASE`（第三方代理也走同一套）。

### 3. 选模型

编辑 `config/models.yaml`，决定每个"场景别名"实际用哪个模型。**bundle JSON 里永远引用别名**（如 `models_ref: "text_cheap"`），换底座只改 YAML 一个文件，不动 bundle。详见[模型别名注册表](#模型别名注册表)。

### 4. 跑一个 demo

```bash
# 最小离线自检（不需要 API key）
python -m pytest

# P0：纯 mock 线性流水线（不需要 API key）
python -m framework.run --task examples/mock_linear.json --run-id run_demo_p0

# P1：真实 LLM 结构化抽取（需要 .env 填好）
python -m framework.run --task examples/character_extract.json --run-id run_demo_p1 --live-llm
```

成功标志：终端打印 `status: succeeded`，`artifacts/<run_id>/run_summary.json` 落盘。

---

## 架构概览

权威设计文档：[`docs/claude_unified_architecture_plan_v1.md`](docs/claude_unified_architecture_plan_v1.md)

### 核心对象（§B）

```
Task ──▶ Run ──▶ Workflow ──▶ Step[*]
                                  │
                                  ├─▶ 产出 Artifact[*]   （text / image / audio / mesh / bundle / ue / report）
                                  ├─▶ 写 Checkpoint      （step_id + input_hash + artifact_hashes）
                                  └─▶ 评审步额外产出 ReviewReport + Verdict
```

- **`Task`**：用户意图（含 `task_type` / `run_mode` / `ue_target` / `review_policy`）
- **`Run`**：一次执行实例，带 OTel `trace_id` + metrics
- **`Workflow`**：有控制语义的 Step 图（MVP 线性 + 一级分支）
- **`Step`**：11 种类型，每个带 `risk_level` + 5 类 Policy（Transition/Retry/Provider/Budget/Escalation）
- **`Artifact`**：一等公民产物，`PayloadRef` 三态（`inline` / `file` / `blob`），带 `Lineage` + `Validation`
- **`ReviewNode / ReviewReport / Verdict`**：评审三件套，**分析对象与流程控制对象分离**
- **`Verdict.decision`**：9 种枚举（`approve_one` / `revise` / `retry_same_step` / `fallback_model` / `human_review_required` / ...）

### 9 阶段 Run 生命周期（§C.2）

```
1. Task ingestion         → 2. Workflow resolution    → 3. Dry-run Pass (零副作用预检)
4. Scheduling plan        → 5. Step execution          → 6. Verdict dispatching
7. Validation gates       → 8. Export                  → 9. Run finalize
```

### MVP 五阶段（§F，已全部闭环）

| 阶段 | 范围 | 验收入口 |
|---|---|---|
| **P0** 对象模型 + 运行时骨架 | Pydantic schemas · Artifact Store · Orchestrator · Scheduler · TransitionEngine · Dry-run Pass · Checkpoint · OTel tracing | `examples/mock_linear.json` |
| **P1** `basic_llm` 模式 | LiteLLM 接入 · Instructor 结构化抽取 · CapabilityRouter · RetryPolicy · Secrets | `examples/character_extract.json` |
| **P2** `standalone_review` 模式 | 5 维 rubric scoring · single_judge / chief_judge · ReviewReport + Verdict 分离 · Select step | `examples/review_3_images.json` |
| **P3** `production` + 内嵌 review | ComfyUI 外挂 worker · `generate(image)` · `risk_level` 调度 · revise 回环 + `revision_hint` · FailureModeMap | `examples/image_pipeline.json` |
| **P4** UE Bridge `manifest_only` | `UEAssetManifest` · `UEImportPlan` · `PermissionPolicy` · Inspect 只读工具 · `EvidenceWriter` · `ue_scripts/*` | `examples/ue_export_pipeline.json` |

---

## 目录结构

```
D:\ClaudeProject\ForgeUE_claude\
├── framework/                   # 运行时主包
│   ├── core/                    # 对象模型（Task / Run / Artifact / Policies / Review / UE）
│   ├── artifact_store/          # PayloadRef 三态后端 + Repository + Lineage + VariantTracker
│   ├── runtime/                 # Orchestrator / Scheduler / TransitionEngine / DryRunPass / CheckpointStore
│   │   ├── executors/           # generate_structured / generate_image / validate / review / select / export / mock
│   │   └── failure_mode_map.py  # §C.6 exception → Decision 映射
│   ├── providers/               # LiteLLM + Fake adapters + CapabilityRouter + ModelRegistry
│   │   └── workers/             # ComfyWorker（FakeComfyWorker + HTTPComfyWorker）
│   ├── review_engine/           # LLMJudge / ChiefJudge / ReportVerdictEmitter + rubric YAML
│   ├── schemas/                 # Pydantic 业务 schema（UECharacter / ImageSpec）注册
│   ├── ue_bridge/               # manifest_builder / import_plan_builder / permission / inspect / evidence
│   ├── workflows/               # load_task_bundle
│   ├── observability/           # OTel tracing + secrets 管理
│   └── run.py                   # CLI 入口
│
├── ue_scripts/                  # UE 5.x 编辑器内 Python（不依赖 framework 包）
│   ├── manifest_reader.py       # 读 manifest + plan，拓扑排序
│   ├── domain_texture.py        # 贴图导入域
│   ├── domain_mesh.py           # 静态网格导入域
│   ├── domain_audio.py          # 音频导入域
│   ├── domain_material.py       # 材质（Phase C，MVP 只读）
│   ├── evidence_writer.py       # Evidence 追加写
│   └── run_import.py            # UE Python Console 入口
│
├── config/
│   └── models.yaml              # 模型别名注册表（见下文）
│
├── examples/                    # 5 个 TaskBundle JSON（Task + Workflow + Steps）
│
├── docs/                        # 架构文档
│   ├── claude_unified_architecture_plan_v1.md      # 唯一权威设计
│   ├── unified_architecture_vNext.md               # 精简版
│   ├── claude_cross_review_report_v1.md            # 交叉评审
│   ├── claude_independent_plan_v1.md               # 独立方案 v1
│   └── assistant_plan_bundle/                      # 详细分章节设计
│
├── tests/
│   ├── integration/             # 5 份阶段闭环测试（test_p0 ~ test_p4）
│   └── unit/                    # 11 份单元测试
│
├── artifacts/                   # 运行产物（gitignored，file-backed Artifact 落这里）
│
├── .env                         # 本地密钥（gitignored）
├── .env.example                 # 密钥模板（入库）
├── pyproject.toml
└── README.md
```

---

## Bundle 与 Example

**Bundle** = `Task` + `Workflow` + `Steps` 三段的 JSON 打包文件，由 `framework.workflows.load_task_bundle` 加载。

| 文件 | 阶段 | 用途 | 是否需要 `--live-llm` |
|---|---|---|---|
| `examples/mock_linear.json` | P0 | 纯 mock 三步线性验收 | ❌ |
| `examples/character_extract.json` | P1 | prompt → `UECharacter` 20 字段结构化 | ✅ |
| `examples/review_3_images.json` | P2 | 3 内联候选 → single_judge → Verdict | ✅ |
| `examples/image_pipeline.json` | P3 | prompt → ImageSpec → ComfyUI 候选 → review → export | ✅ |
| `examples/ue_export_pipeline.json` | P4 | 同 P3 + 尾端 UE manifest-only 导出 | ✅ + UE 路径 |

跑任意 bundle：

```bash
python -m framework.run --task <path-to-bundle.json> --run-id <run-id> [--live-llm] [--comfy-url URL] [--resume] [--trace-console]
```

---

## 模型别名注册表

`config/models.yaml` 集中管理所有 bundle 引用的"模型组"。bundle 里只写**场景别名**，真实模型名在 YAML 里维护。

### 当前三个别名

| 别名 | 用途 | 被谁引用 |
|---|---|---|
| `text_cheap` | 轻量文本结构化（prompt → JSON/ImageSpec） | `character_extract.step_generate` · `image_pipeline.step_spec` · `ue_export_pipeline.step_spec` |
| `review_judge` | 评审打分 / Verdict 决策 | `review_3_images.step_review` · `image_pipeline.step_review` · `ue_export_pipeline.step_review` |
| `text_strong` | 复杂推理（MVP 预留，当前 0 处引用） | — |

### 换模型的流程

**只改 `config/models.yaml` 一个文件**：

```yaml
aliases:
  text_cheap:
    preferred: ["your-preferred-model-id"]
    fallback:  ["anthropic/claude-haiku-4-5-20251001"]
```

所有引用 `text_cheap` 的 bundle step 自动跟着变。`CapabilityRouter` 按 `preferred → fallback` 顺序试，第一个没抛 `ProviderError` 的就用它。

### bundle 里如何引用

```json
"provider_policy": {
  "capability_required": "text.structured",
  "models_ref": "text_cheap"
}
```

**显式覆盖**（单 step 级别微调）：`models_ref` 旁边再写 `preferred_models` / `fallback_models`，显式值优先。

### 新增别名

直接往 `config/models.yaml` 的 `aliases` 下加一块：

```yaml
aliases:
  image_fast:
    preferred: ["openrouter/flux-1-schnell"]
    fallback:  []
```

bundle 立即能 `"models_ref": "image_fast"`。注册表是进程单例，热加载只需重启 Python。

---

## 运行时特性

### 核心能力

| 能力 | 来源 | 实现位置 |
|---|---|---|
| **Dry-run Pass**（零副作用预检）| Claude 原创 | `framework/runtime/dry_run_pass.py` |
| **Checkpoint + content hash 缓存** | Claude 原创 | `framework/runtime/checkpoint_store.py` · resume 时命中哈希跳执行 |
| **PayloadRef 三态**（inline/file/blob）| Claude 原创 | `framework/artifact_store/payload_backends/` · MVP 实现 inline + file |
| **Artifact Lineage + VariantTracker** | 自研 | `framework/artifact_store/lineage.py` · `variant_tracker.py` |
| **5 维 rubric scoring + 5 类 Policy** | assistant 方案 | `framework/core/policies.py` · `review_engine/` |
| **Verdict ↔ TransitionPolicy 引擎** | 共识 | `framework/runtime/transition_engine.py` · 支持 9 种 Decision |
| **`revision_hint` 回环** | §F3-4 | 评审 `revise` → 自动注入下一 step 的 `inputs["revision_hint"]` |
| **FailureModeMap**（§C.6）| 交叉评审新增 | exception → Decision → transition · `framework/runtime/failure_mode_map.py` |
| **`risk_level` 调度** | Claude 原创 | `Scheduler.runnable_after` 按 low→medium→high 排序 |
| **DeterminismPolicy**（seed 传递 + 模型版本锁）| 共识 | `Task.determinism_policy` |
| **OTel tracing**（Run → Step → Provider）| 共识 | `framework/observability/tracing.py` |

### UE Bridge 边界（§E）

```
双模式（由 UEOutputTarget.import_mode 选择）：

manifest_only  ← MVP 默认
  框架 → 产出 manifest.json + import_plan.json + evidence.json 到 <UE>/Content/Generated/<run_id>/
  UE   → 独立 Python 脚本（ue_scripts/run_import.py）读 manifest 逐项导入

bridge_execute ← 后置（Phase G 扩展）
  框架直调 UE Python Editor API · MVP 未启用
```

权限策略 5 档（§E.4）：`create_folder` / `import_texture` / `import_audio` / `import_static_mesh` 默认允许；`create_material` / `create_sound_cue` 默认关；修改已有资产 / 蓝图 / 地图 / 配置 / 删除**恒禁**。

---

## 测试

```bash
python -m pytest                    # 跑全部
python -m pytest tests/integration/ # 只跑阶段闭环（5 份）
python -m pytest tests/unit/        # 只跑单元（12 份）
python -m pytest -v -k p3           # 关键字过滤
```

### 当前覆盖

- **143 条测试，全部离线可跑**（无 API key、无 UE 工程、无 ComfyUI）
- 真实 LLM 调用路径被 `FakeAdapter`（`framework.providers.fake_adapter`）替换
- ComfyUI 路径被 `FakeComfyWorker`（`framework.providers.workers.comfy_worker`）替换
- UE 侧导入路径用 `sys.modules` 注入的 `unreal` stub 驱通

### 覆盖分布

| 测试文件 | 条数 | 覆盖目标 |
|---|---:|---|
| `test_p0_mock_linear.py` | 4 | Run 全生命周期 · resume 缓存命中 · dry-run 失败 · OTel span |
| `test_p1_structured_extraction.py` | 4 | schema 成功 / retry / 耗尽 / 上游坏数据 |
| `test_p2_standalone_review.py` | 4 | single_judge · chief_judge 分歧 · select 按 Verdict 过滤 |
| `test_p3_production_pipeline.py` | 6 | happy · revise 收敛 · max_revise 封顶 · worker timeout 恢复 · 失败映射 · risk 排序 |
| `test_p4_ue_manifest_only.py` | 5 | 落盘 · PermissionPolicy skip · Verdict.reject 短路 · UE stub 驱通 · builder 纯函数 |
| `test_*.py`（unit，12 份）| 120 | schema / artifact / checkpoint / policies / judges / bridge / failure_mode / registry ... |

---

## 端到端验收路径

### 分档验证（由浅入深）

| 档 | 命令 | 验证目标 |
|---|---|---|
| **1** | `python -m pytest` | 143 passed = 全逻辑正确 |
| **2** | `pip install -e ".[llm]"` + `python -c "import litellm, instructor"` | 开源包装好，版本 ≥ pyproject 声明 |
| **3** | `python -m framework.run --task examples/character_extract.json --run-id r1 --live-llm` | `.env` 密钥 + LiteLLM 真实调用 OK |
| **4** | `python -m framework.run --task examples/ue_export_pipeline.json --run-id r2 --live-llm`（改 `ue_target.project_root` 到临时目录）| 全链 + 产 manifest + evidence |
| **5** | 起 ComfyUI `http://127.0.0.1:8188`，`--comfy-url` 接入 | 真实出图（需手动补 `workflow_graph`）|
| **6** | 空白 UE 5.x 工程 → 跑档 4 → UE Python Console `exec(open('ue_scripts/run_import.py').read())` | `Content Browser` 出资产 + `evidence.json` 完整追溯 |

详见 [`docs/claude_unified_architecture_plan_v1.md` §K](docs/claude_unified_architecture_plan_v1.md)。

### 常见错误速查

| 现象 | 原因 | 解决 |
|---|---|---|
| `ModuleNotFoundError: litellm` | 未装 `[llm]` extra | `pip install -e ".[llm]"` |
| `ProviderError: no adapter registered for model=...` | CLI 跑实模型但忘了 `--live-llm` | 加 `--live-llm` |
| `UnknownModelAlias: 'xxx' not in registry` | bundle 里 `models_ref` 拼错或未在 YAML 注册 | 检查 `config/models.yaml` |
| `DRY-RUN FAILED: unresolved bindings` | `input_bindings.source` 路径错 / 未在 Task 里 | 查 bundle 步骤定义 |
| `generate_structured failed: ProviderPolicy has no preferred or fallback models` | `models_ref` 没被展开（绕过了 loader）| 调 `expand_model_refs(raw, get_model_registry())` 或改用 `load_task_bundle` |

---

## 文档导航

| 文档 | 作用 |
|---|---|
| [`docs/claude_unified_architecture_plan_v1.md`](docs/claude_unified_architecture_plan_v1.md) | **唯一权威设计**，对象模型 + 工作流 + UE Bridge + MVP 5 阶段范围 |
| [`docs/unified_architecture_vNext.md`](docs/unified_architecture_vNext.md) | 精简版架构说明 |
| [`docs/claude_cross_review_report_v1.md`](docs/claude_cross_review_report_v1.md) | 权威文档合并前的交叉评审记录 |
| [`docs/assistant_plan_bundle/`](docs/assistant_plan_bundle/) | 按主题拆分的设计细则（对象字段、review 嵌入、modality metadata、Bridge 三层、开源项目映射、运行时组件）|

---

## 后续扩展

按优先级排序（§G）：

1. **Bridge `bridge_execute` 模式** —— 框架直调 UE Python Editor API（`ue_bridge/execute/` 目录已占位）
2. **多模态扩展** —— AudioCraft / TRELLIS / TripoSR worker（`providers/workers/` 已留位）
3. **DAG Workflow** —— 非线性 + 分支 + merge（`Step.depends_on` 已支持多依赖）
4. **Workflow 模板继承** —— `Workflow.template_ref` 字段已预留
5. **Blob 存储后端** —— S3/MinIO（`PayloadRef.kind="blob"` 已支持，`payload_backends/blob.py` 空实现）
6. **Resource Budget / GPU 调度** —— `BudgetPolicy.gpu_seconds_cap` 已有
7. **Run Comparison / 基线回归** —— `observability/run_comparison.py` 待补
8. **Human-in-the-loop 标准协议** —— `human_gate` Step.type + `EscalationPolicy.notify_channel`
9. **Schema Registry + 演化规则**
10. **多租户/多项目隔离** —— `Task.project_id` + Artifact Store 按 project 分目录已做

明确放弃：聊天式 agent 框架接入 · UE 反向控制 · 非 Pydantic 对象模型 · PydanticAI 作主力。

---

## 许可

内部项目，暂未开源。

## 一句话定位

> **以 `Task/Run/Workflow/Artifact` 为一等公民、`Review` 为合法节点、`UEOutputTarget` 前置、双模 UE Bridge、5 类 Policy 分离、`Dry-run + Checkpoint` 保障可复现的多模型运行时**；基础层（LiteLLM / Instructor）直接用，多模态生成工具（ComfyUI / AudioCraft / TRELLIS / TripoSR）外挂为 worker，UE 领域与运行时工程化部分全自研。
