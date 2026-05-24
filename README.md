# forgeue

> 多引擎内容交付多模型运行时框架 · vNext

ForgeUE 是多引擎内容交付框架。Game Build Compiler Phase A 提供 engine-neutral GDD-to-game-build planning contract；核心 runtime 负责多模型生成、Artifact 治理、review、workflow execution 与 provider routing。具体引擎交付由 `EngineAdapter` 实现。Unreal 是默认 adapter；Godot 4.x 通过 headless import adapter 支持。

- **三种运行模式**：`basic_llm`（结构化问答）· `production`（多模态生成 + 内嵌评审）· `standalone_review`（独立评审链）
- **Game Build Compiler Phase A**：把 GDD 提炼为 `Contract → Graph → Build IR → Handoff` 的结构化 planning artifact；当前为 contract-only，不生成 workflow bundle、UE/Godot 工程文件或可玩 demo
- **Engine Bridge / Godot 4**：`ExportExecutor` 按 `engine_target / legacy ue_target` dispatch 到引擎 adapter；Godot 4.x 支持 `headless_import`
- **Unreal adapter（manifest-only）**：沿用 `UEAssetManifest + UEImportPlan + Evidence` 文件契约，UE 侧 Python 脚本执行导入
- **基础层直接用开源**：[LiteLLM](https://github.com/BerriAI/litellm) 统一 provider 调用 + [Instructor](https://github.com/567-labs/instructor) 做结构化输出；**运行时、评审、多引擎交付边界全自研**
- **测试驱动**：覆盖 P0–P4 全阶段 + 单元级断言，全部可离线跑（`FakeAdapter` + `FakeComfyWorker`）；测试数量以 `pytest -q` 实测为准

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

权威设计文档见 [`docs/INDEX.md`](docs/INDEX.md) 与五件套;旧 plan_v1 仅作归档史料。

### 核心对象（§B）

```
GameBuildContract ─▶ GameBuildGraph ─▶ GameBuildIR ─▶ GameBuildHandoff
       │                  │                  │                  │
       └────── engine-neutral GDD-to-game-build planning contract ┘

Task ──▶ Run ──▶ Workflow ──▶ Step[*]
                                  │
                                  ├─▶ 产出 Artifact[*]   （text / image / audio / mesh / bundle / ue / report）
                                  ├─▶ 写 Checkpoint      （step_id + input_hash + artifact_hashes）
                                  └─▶ 评审步额外产出 ReviewReport + Verdict
```

- **`Task`**：用户意图（含 `task_type` / `run_mode` / `engine_target` / legacy `ue_target` / `review_policy`）
- **`Run`**：一次执行实例，带 OTel `trace_id` + metrics
- **`Workflow`**：有控制语义的 Step 图（MVP 线性 + 一级分支）
- **`Step`**：11 种类型，每个带 `risk_level` + 5 类 Policy（Transition/Retry/Provider/Budget/Escalation）
- **`Artifact`**：一等公民产物，`PayloadRef` 三态（`inline` / `file` / `blob`），带 `Lineage` + `Validation`
- **`ReviewNode / ReviewReport / Verdict`**：评审三件套，**分析对象与流程控制对象分离**
- **`Verdict.decision`**：9 种枚举（`approve_one` / `revise` / `retry_same_step` / `fallback_model` / `human_review_required` / ...）

### Game Build Compiler（Phase A）

Game Build Compiler 是 runtime 上方的 planning contract 层，来源于 AGENT_UE5 Design Compiler 中可泛化的设计编译语义。当前 Phase A 只落五个结构化 schema refs：`game_build.contract` / `game_build.clarification_report` / `game_build.graph` / `game_build.build_ir` / `game_build.handoff`。`GameBuildIR` 会拒绝 `Source/`、`/Game/`、`Content/`、`res://`、`.uasset`、`.umap`、`.h`、`.cpp`、`.gd`、`.tscn` 等具体引擎路径，确保后续 lowering 仍由 Unreal / Godot adapter 接管。

完整契约见 [`docs/contracts/game-build-compiler/spec.md`](docs/contracts/game-build-compiler/spec.md)。

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
| **P4** Engine Bridge + Unreal adapter `manifest_only` | `EngineTarget` · `EngineAdapterRegistry` · `UnrealAdapter` · `UEAssetManifest` · `UEImportPlan` · `EvidenceWriter` · `engine_scripts/unreal/*` | `examples/ue_export_pipeline.json` |
| **P4-Godot** Godot 4 `headless_import` MVP | `Godot4Adapter` · staging · `godot_manifest.json` · `godot_import_plan.json` · `EngineEvidence` | `examples/godot4_export_smoke.json` |

---

## 目录结构

```
D:\ClaudeProject\ForgeUE_claude\
├── src/framework/                   # 运行时主包
│   ├── core/                    # 对象模型（Task / Run / Artifact / Policies / Review / Engine / UE）
│   ├── artifact_store/          # PayloadRef 三态后端 + Repository + Lineage + VariantTracker
│   ├── runtime/                 # Orchestrator / Scheduler / TransitionEngine / DryRunPass / CheckpointStore
│   │   ├── executors/           # generate_structured / generate_image / validate / review / select / export / mock
│   │   └── failure_mode_map.py  # §C.6 exception → Decision 映射
│   ├── providers/               # LiteLLM + Fake adapters + CapabilityRouter + ModelRegistry
│   │   └── workers/             # ComfyWorker（FakeComfyWorker + HTTPComfyWorker）
│   ├── review_engine/           # LLMJudge / ChiefJudge / ReportVerdictEmitter + rubric YAML
│   ├── schemas/                 # Pydantic 业务 schema（UECharacter / ImageSpec / Game Build Compiler）注册
│   ├── engine_bridge/           # EngineTarget / EngineAdapter / UnrealAdapter / Godot4Adapter
│   │   └── unreal/contract/     # Unreal manifest-only 文件契约主实现
│   ├── ue_bridge/               # FOR-32 人工删除清单中的 legacy path,不作为当前入口
│   ├── workflows/               # load_task_bundle
│   ├── observability/           # OTel tracing + secrets 管理
│   └── run.py                   # CLI 入口
│
├── engine_scripts/unreal/       # UE 5.x 编辑器内 Python（不依赖 framework 包）
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
├── examples/                    # TaskBundle JSON（Task + Workflow + Steps）
│
├── docs/                        # 当前文档入口与架构权威
│   ├── INDEX.md                  # 文档导航入口
│   ├── requirements/SRS.md       # 需求规格
│   ├── design/HLD.md             # 概要设计
│   ├── design/LLD.md             # 详细设计
│   ├── testing/test_spec.md      # 测试规格
│   ├── acceptance/acceptance_report.md
│   ├── contracts/                # 当前行为契约
│   └── archive/                  # 历史 plan_v1 等归档史料
│
├── tests/
│   ├── integration/             # 阶段闭环 + 场景级 + Run Comparison 集成测试
│   ├── unit/                    # 单元测试（含 Run Comparison;详见 docs/testing/test_spec.md §2.2）
│   └── fixtures/                # 共享测试 fixture（review_images / comparison / ...）
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
| `examples/ue_export_pipeline.json` | P4 | 同 P3 + 尾端 Unreal manifest-only 导出 | ✅ + Unreal 路径 |
| `examples/godot4_export_smoke.json` | P4-Godot | `engine_target.engine="godot4"` 的 headless import bundle shape | ❌（离线 loader / dry-run smoke）|

跑任意 bundle：

```bash
python -m framework.run --task <path-to-bundle.json> --run-id <run-id> [--live-llm] [--resume] [--trace-console]
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
| **Dry-run Pass**（零副作用预检）| Claude 原创 | `src/framework/runtime/dry_run_pass.py` |
| **Checkpoint + content hash 缓存** | Claude 原创 | `src/framework/runtime/checkpoint_store.py` · resume 时命中哈希跳执行 |
| **PayloadRef 三态**（inline/file/blob）| Claude 原创 | `src/framework/artifact_store/payload_backends/` · MVP 实现 inline + file + blob |
| **Artifact Lineage + VariantTracker** | 自研 | `src/framework/artifact_store/lineage.py` · `variant_tracker.py` |
| **5 维 rubric scoring + 5 类 Policy** | assistant 方案 | `src/framework/core/policies.py` · `review_engine/` |
| **Verdict ↔ TransitionPolicy 引擎** | 共识 | `src/framework/runtime/transition_engine.py` · 支持 9 种 Decision |
| **`revision_hint` 回环** | §F3-4 | 评审 `revise` → 自动注入下一 step 的 `inputs["revision_hint"]` |
| **FailureModeMap**（§C.6）| 交叉评审新增 | exception → Decision → transition · `src/framework/runtime/failure_mode_map.py` |
| **Engine Bridge dispatch** | Engine Bridge 抽象 | `src/framework/engine_bridge/` · `ExportExecutor` wildcard dispatch |
| **Game Build Compiler Phase A** | AGENT_UE5 Design Compiler 可泛化迁移 | `src/framework/schemas/game_build_compiler.py` · `docs/contracts/game-build-compiler/spec.md` |
| **`risk_level` 调度** | Claude 原创 | `Scheduler.runnable_after` 按 low→medium→high 排序 |
| **DeterminismPolicy**（seed 传递 + 模型版本锁）| 共识 | `Task.determinism_policy` |
| **OTel tracing**（Run → Step → Provider）| 共识 | `src/framework/observability/tracing.py` |

### Engine Bridge / Unreal Adapter 边界

```
ExportExecutor
  → resolve_engine_target(task.engine_target or legacy task.ue_target)
  → EngineAdapterRegistry.resolve(target.engine)
  → adapter.export(ctx, target=target)
```

内置 adapter：

| Adapter | engine | import_mode | 交付方式 |
|---|---|---|---|
| `UnrealAdapter` | `unreal` | `manifest_only` | 产出 `manifest.json + import_plan.json + evidence.json`，`engine_scripts/unreal/run_import.py` 在 UE 侧导入 |
| `Godot4Adapter` | `godot4` | `headless_import` | stage 到 `<project_root>/<asset_root>/<run_id>/`，写 `godot_manifest.json` / `godot_import_plan.json` / `evidence.json`，调用 Godot `--headless --path <project_root> --import` |

Godot 4.x 第一阶段支持 `image/png`、`image/jpg`、`image/jpeg`、`audio/wav`、`audio/mp3`、`mesh/glb`；`video/mp4` 先写 `skipped` evidence，不自动映射为 runtime asset。Godot 可执行文件解析顺序为 `engine_target.executable_path` → `GODOT4_EXE` → fail-fast。

Unreal adapter 继续使用 Unreal manifest-only 文件契约：

manifest_only  ← MVP 默认
  框架 → 产出 manifest.json + import_plan.json + evidence.json 到 <UE>/Content/Generated/<run_id>/
  UE   → 独立 Python 脚本（engine_scripts/unreal/run_import.py）读 manifest 逐项导入

bridge_execute ← 后置（Phase G 扩展）
  框架直调 UE Python Editor API · MVP 未启用
```

权限策略 5 档（§E.4）：`create_folder` / `import_texture` / `import_audio` / `import_static_mesh` 默认允许；`create_material` / `create_sound_cue` 默认关；修改已有资产 / 蓝图 / 地图 / 配置 / 删除**恒禁**。

---

## 测试

```bash
python -m pytest                    # 跑全部
python -m pytest tests/integration/ # 只跑集成测试目录（P0-P4 + 场景级 + Run Comparison）
python -m pytest tests/unit/        # 只跑单元（含 Run Comparison;具体文件以 ls 实时查为准）
python -m pytest -v -k p3           # 关键字过滤
```

### 当前覆盖

- **测试全部离线可跑**（无 API key、无 UE 工程、无 ComfyUI）；当前数量以 `pytest -q` 实测为准
- 真实 LLM 调用路径被 `FakeAdapter`（`framework.providers.fake_adapter`）替换
- ComfyUI 路径被 `FakeComfyWorker`（`framework.providers.workers.comfy_worker`）替换
- Unreal 侧导入路径用 `sys.modules` 注入的 `unreal` stub 驱通
- Engine Bridge / Godot 4 路径用 `test_engine_target.py`、`test_engine_adapter_registry.py`、`test_godot4_adapter.py` 与 example smoke 覆盖

### 覆盖分布

| 测试文件 | 条数 | 覆盖目标 |
|---|---:|---|
| `test_p0_mock_linear.py` | 4 | Run 全生命周期 · resume 缓存命中 · dry-run 失败 · OTel span |
| `test_p1_structured_extraction.py` | 4 | schema 成功 / retry / 耗尽 / 上游坏数据 |
| `test_p2_standalone_review.py` | 4 | single_judge · chief_judge 分歧 · select 按 Verdict 过滤 |
| `test_p3_production_pipeline.py` | 6 | happy · revise 收敛 · max_revise 封顶 · worker timeout 恢复 · 失败映射 · risk 排序 |
| `test_p4_ue_manifest_only.py` | 5 | 落盘 · PermissionPolicy skip · Verdict.reject 短路 · UE stub 驱通 · builder 纯函数 |
| `test_engine_target.py` / `test_engine_adapter_registry.py` / `test_godot4_adapter.py` | 以 `pytest -q` 实测为准 | `EngineTarget` legacy 兼容 · adapter registry · Godot staging / evidence / fresh import guard |
| `test_*.py`（unit，多个）| 以 `pytest -q` 实测为准 | schema / artifact / checkpoint / policies / judges / engine bridge / failure_mode / registry / Run Comparison ... |

---

## 端到端验收路径

### 分档验证（由浅入深）

| 档 | 命令 | 验证目标 |
|---|---|---|
| **1** | `python -m pytest` | 全用例通过 = 全逻辑正确(以 `pytest -q` 实测为准)|
| **2** | `pip install -e ".[llm]"` + `python -c "import litellm, instructor"` | 开源包装好，版本 ≥ pyproject 声明 |
| **3** | `python -m framework.run --task examples/character_extract.json --run-id r1 --live-llm` | `.env` 密钥 + LiteLLM 真实调用 OK |
| **4** | `python -m framework.run --task examples/ue_export_pipeline.json --run-id r2 --live-llm`（改 `engine_target.project_root` 或 legacy `ue_target.project_root` 到临时目录）| 全链 + 产 Unreal manifest + evidence |
| **5** | `python -m framework.run --task examples/godot4_export_smoke.json --run-id r_godot`（真实导入前设置 `GODOT4_EXE` 或 `engine_target.executable_path`）| Godot 4 bundle shape + headless import 交付路径;本机 Godot 4.6.2 L2 evidence 见 `demo_artifacts/2026-05-24/adhoc/godot4_headless/engine_bridge_godot4_l2_20260524_091408/godot4_headless_validation.md` |
| **6** | ComfyUI agent CLI live smoke:默认 `lifecycle=none` 时先确保 ComfyUI server running(本机推荐 `python -m factory_v3 serve` 作为启停 helper),再跑 `examples/comfy_local_smoke*.json`;也可设 `ensure_running` / `ensure_release` / `self_managed_session` 由框架托管 | 真实 image / mesh / audio / video 产物;ForgeUE 生成仍走 `python -m comfyui_api run`(manifest 名,不再 inline `workflow_graph`;不再用 `--comfy-url`)|
| **7** | 空白 UE 5.x 工程 → 跑档 4 → UE Python Console `exec(open('engine_scripts/unreal/run_import.py').read())` | `Content Browser` 出资产 + `evidence.json` 完整追溯 |

当前文档入口见 [`docs/INDEX.md`](docs/INDEX.md)；历史 plan_v1 已归档到 [`docs/archive/claude_unified_architecture_plan_v1.md`](docs/archive/claude_unified_architecture_plan_v1.md)。

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

2026-04-22 文档重构,采用五件套:

| 层次 | 文档 | 作用 |
|---|---|---|
| 入口 | [`docs/INDEX.md`](docs/INDEX.md) | 文档索引 + 读者导览 |
| 需求 | [`docs/requirements/SRS.md`](docs/requirements/SRS.md) | 需求规格说明书(FR/NFR/接口/约束) |
| 概要设计 | [`docs/design/HLD.md`](docs/design/HLD.md) | 分层 / 子系统 / 对象模型概览 |
| 详细设计 | [`docs/design/LLD.md`](docs/design/LLD.md) | 字段 / 方法 / 算法 / 异常体系 |
| 测试 | [`docs/testing/test_spec.md`](docs/testing/test_spec.md) | 测试索引 + fence 清单(用例数以 `pytest -q` 实测为准) |
| 验收 | [`docs/acceptance/acceptance_report.md`](docs/acceptance/acceptance_report.md) | FR/NFR 验收状态矩阵 |
| 参考 | [`docs/api_des/`](docs/api_des/) | 五家 provider API 契约 |
| 归档 | [`docs/archive/`](docs/archive/) | 历史方案与 plan_v1 史料(不再更新) |

根目录还有两份 AI 编码代理上下文文件(协作约定 + 常踩坑点,与五件套互补):

| 文件 | 读者 |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Claude Code |
| [`AGENTS.md`](AGENTS.md) | Codex CLI / Cursor / Aider 等通用 agent |

两份内容保持同步,修改项目约定时两份一起改。

---

## AI 工作流 / Superpowers

ForgeUE_codex 采用 Superpowers-first 作为 AI 主工作流。非平凡需求先用 `superpowers:brainstorming` 明确目标、约束和方案;方案确认后用 `superpowers:writing-plans` 生成实施计划;实现阶段按任务性质使用 TDD、systematic debugging、executing-plans 或 subagent-driven-development;完成前用 verification-before-completion 做证据化验证。涉及文档同步、归档、backlog 或五件套更新时,使用项目级 skill `document-release` 做文档发布检查。Codex review 保留为可选辅助(`/codex:adversarial-review` design hook + `/codex:review --base main` final hook),但外部 review 结论必须独立核验。

| 入口 | 用途 |
|---|---|
| [`docs/ai_workflow/validation_matrix.md`](docs/ai_workflow/validation_matrix.md) | Level 0 / 1 / 2 验证命令矩阵(不硬编码测试总数) |
| [`docs/contracts/`](docs/contracts/) | 当前行为契约层:10 个 contract(`runtime-core` / `artifact-contract` / `workflow-orchestrator` / `review-engine` / `provider-routing` / `engine-export-bridge` / `ue-export-bridge` / `probe-and-validation` / `examples-and-acceptance` / `game-build-compiler`) |
| [`docs/archive/forge_changes/`](docs/archive/forge_changes/) | 历史 forge change evidence 归档,只读参考 |
| [`docs/backlog/active.md`](docs/backlog/active.md) | Backlog —— 项目当前待办集合 |
| [`.agents/skills/document-release/SKILL.md`](.agents/skills/document-release/SKILL.md) | 项目级文档发布 / 归档 / backlog 同步 skill |

`docs/` 五件套仍是长期权威;`docs/contracts/` 是从原 forge contract 迁移来的精简契约层,不替代五件套。

---

## 后续扩展

按优先级排序（§G）：

1. **Unreal RemoteControl adapter / `bridge_execute` 模式** —— future bridge_execute reserved follow-on,不在当前 `framework.engine_bridge.unreal.contract` manifest_only 主实现中启用
2. **多模态扩展** —— AudioCraft / TRELLIS / TripoSR worker（`providers/workers/` 已留位）
3. **DAG Workflow** —— 非线性 + 分支 + merge（`Step.depends_on` 已支持多依赖）
4. **Workflow 模板继承** —— `Workflow.template_ref` 字段已预留
5. **Blob 存储云 SDK adapter** —— `BlobBackend` MVP 已支持可注入 client + 内存默认实现;真实 S3/MinIO/Azure SDK adapter 可按 `BlobClient` protocol 后续接入
6. **Resource Budget / GPU 调度** —— `BudgetPolicy.gpu_seconds_cap` 已有
7. **Run Comparison / 基线回归** —— ✅ 已实装(2026-04-25,见 `src/framework/comparison/`)。CLI 入口 `python -m framework.comparison --baseline-run <id_a> --candidate-run <id_b> --artifact-root <root>`,read-only 比较两个完成的 Run 目录,产出 `comparison_report.json` + `comparison_summary.md`(覆盖 artifact / verdict / metric diff)。完整 flag 列表见 `--help`
8. **Human-in-the-loop 标准协议** —— `human_gate` Step.type + `EscalationPolicy.notify_channel`
9. **Schema Registry + 演化规则**
10. **多租户/多项目隔离** —— `Task.project_id` + Artifact Store 按 project 分目录已做
11. **Game Build Compiler lowering** —— Phase A 只提供 planning contract；后续再把 `GameBuildIR` lowering 为 Workflow bundle 与 Unreal / Godot adapter handoff

明确放弃：聊天式 agent 框架接入 · UE 反向控制 · 非 Pydantic 对象模型 · PydanticAI 作主力。

---

## 许可

内部项目，暂未开源。

## 一句话定位

> **以 `GameBuildContract → GameBuildGraph → GameBuildIR → GameBuildHandoff` 承接 GDD-to-game-build planning，以 `Task/Run/Workflow/Artifact` 为一等公民、`Review` 为合法节点、`EngineTarget` 为通用交付入口、`EngineAdapter` 分发具体引擎交付、5 类 Policy 分离、`Dry-run + Checkpoint` 保障可复现的多模型运行时**；基础层（LiteLLM / Instructor）直接用，多模态生成工具（ComfyUI / AudioCraft / TRELLIS / TripoSR）外挂为 worker，Unreal / Godot 等引擎交付边界与运行时工程化部分全自研。
