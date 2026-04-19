# UE 生产链多模型框架 —— 统一架构方案 vNext

> 本文为权威方案。本文与先前任何文档冲突时，以本文为准。
> 原始计划文件：`C:\Users\mzq\.claude-pro\plans\github-snug-leaf.md`

## Context

合并三份输入产出统一方案：
- Claude 独立方案 v1（PayloadRef / 两段式 type / risk_level / Dry-run Pass / Checkpoint+hash / UE Bridge 单向写边界）
- Claude 交叉评审报告 v1（识别了两边互补点、1 处架构分歧、13 项必须采纳、12 项必须新增）
- assistant 方案包 v1（9 对象模型、TaskType/RunMode 分离、UEOutputTarget 前置、CandidateSet+Candidate 双层、review_report/verdict 分离、5 维 scoring、5 类 Policy、UE Bridge Inspect/Plan/Execute + Evidence）

---

## A. 统一术语表

| 术语 | 定义 | 来源 |
|---|---|---|
| `RunMode` | `basic_llm` / `production` / `standalone_review` | 共识 |
| `TaskType` | 任务意图枚举，与 RunMode 正交 | assistant |
| `Task` | 用户意图标准化入口对象 | 共识 |
| `Run` | Task 的一次执行实例 | 共识 |
| `Workflow` | 带控制语义的 Step 图 | 共识 |
| `Step` | Workflow 最小执行单元（替代旧 Node） | 共识 |
| `Step.type` | 11 种合法类型（§B.5） | assistant |
| `Step.risk_level` | 调度风险级别 low/medium/high | Claude 原创 |
| `Artifact` | 生产链中间/最终产物，一等公民 | 共识 |
| `artifact_type` | 内部两段式 `<modality>.<shape>` / 外部扁平显示名 | Claude + assistant 映射 |
| `PayloadRef` | Artifact 载体三态：inline/file/blob | Claude 原创 |
| `Candidate` + `CandidateSet` | 候选双层 | assistant |
| `ReviewNode` / `ReviewReport` / `Verdict` | 评审配置 / 分析对象 / 流程控制对象（三者分离） | assistant |
| `Verdict.decision` | 9 种枚举（§B.8） | assistant |
| `TransitionPolicy` / `RetryPolicy` / `ProviderPolicy` / `BudgetPolicy` / `EscalationPolicy` | 5 类策略 | assistant |
| `UEOutputTarget` | Task 层前置的 UE 目标对象 | assistant |
| `UEAssetManifest` / `UEImportPlan` / `Evidence` | 声明式清单 / 执行式计划 / 操作证据 | assistant |
| `Checkpoint` | Step 完成后的 hash 快照 | Claude 原创 |
| `DryRunPass` | Run 启动前零副作用预检 | Claude 原创 |
| `DeterminismPolicy` | seed 传递 + 模型版本锁 | 交叉评审新增 |

---

## B. 统一对象模型（Pydantic v2）

详见 `framework/core/` 目录，每个对象均为 Pydantic BaseModel。权威结构参见计划原文 §B（字段、可选必填、默认值）。

关键枚举：

```python
class RunMode(str, Enum):
    basic_llm = "basic_llm"
    production = "production"
    standalone_review = "standalone_review"

class StepType(str, Enum):
    generate / transform / review / select / merge / validate
    export / import_ / retry / branch / human_gate

class RiskLevel(str, Enum):
    low / medium / high

class Decision(str, Enum):
    approve / approve_one / approve_many / reject / revise
    retry_same_step / fallback_model / rollback / human_review_required

class ReviewMode(str, Enum):
    single_judge / multi_judge / council / chief_judge
```

---

## C. 统一 Workflow 机制

三种 RunMode 共享同一调度器，形态差异由 Workflow template 体现：

| RunMode | Workflow 形态 | Step 数量 | 必选 Step |
|---|---|---|---|
| basic_llm | 单步或线性 2-3 步 | 1-3 | generate + validate |
| production | 有向线性 + 分支（MVP）→ DAG | 5-15 | generate + review + transform + validate + export |
| standalone_review | 线性评审链 | 3-5 | transform(collect) + review + export(verdict) |

Run 生命周期 9 阶段：Task ingestion → Workflow resolution → **Dry-run Pass** → Scheduling plan → Step execution → Verdict dispatching → Validation gates → Export → Run finalize。

Failure Mode ↔ Decision 映射表见计划 §C.6。

---

## D. Unified Artifact Contract

### D.1 两段式 ↔ 扁平名映射

| 内部 modality.shape | 外部 display_name |
|---|---|
| text.structured | structured_answer |
| image.raster | concept_image / texture_image |
| audio.waveform | music_track / sfx_clip |
| mesh.gltf | mesh_asset |
| bundle.candidate_set | candidate_bundle |
| ue.asset_manifest | ue_asset_manifest |
| ue.import_plan | ue_import_plan |
| report.review | review_report |

### D.2 PayloadRef 三态落盘规则

| kind | 适用 | 后端 | 体积 |
|---|---|---|---|
| inline | 小 JSON / Verdict | 嵌入对象 | ≤ 64 KB |
| file | 图像 / 音频 / mesh | `artifacts/<run_id>/` | ≤ 500 MB |
| blob | 跨机共享 | 对象存储 | — |

**MVP 只实现 inline + file**，blob 接口预留。

---

## E. Unified UE Bridge Boundary

### E.1 双模并存

- **manifest_only（MVP 默认）**：框架落文件 + manifest 到 `<UE>/Content/Generated/<run_id>/`；UE 侧独立 Python 脚本导入
- **bridge_execute（后置）**：框架直调 UE Python Editor Scripting；需过 Inspect → Plan → Execute 三层

### E.2 Phase A/B/C/D

| Phase | 动作 | MVP 状态 |
|---|---|---|
| A 只读探测 | Inspect 全部 | **启用** |
| B 低风险导入 | create_folder / import_texture / import_audio / import_static_mesh | **启用** |
| C 低风险派生 | create_material_from_template / create_sound_cue_from_template | 默认关 |
| D 高风险编辑 | 修改蓝图/地图/配置 | **MVP 恒禁** |

### E.3 Verdict ↔ Bridge 耦合

- `reject` → Bridge 不执行
- `human_review_required` → Bridge 仅 dry-run
- `approve / approve_one / approve_many` → 进入执行

---

## F. MVP 第一阶段开发范围

| Phase | 周 | 范围 |
|---|---|---|
| P0 | 2 | 对象模型 + 运行时骨架（F0-1 ~ F0-7） |
| P1 | 1.5 | basic_llm（LiteLLM + Instructor） |
| P2 | 1.5 | standalone_review |
| P3 | 2 | production + 内嵌 review（ComfyUI worker） |
| P4 | 2 | UE Bridge manifest_only |

合计含缓冲 ≈ 9 周。

---

## G. 后续扩展项（预留位）

bridge_execute 模式 / 多模态扩展（AudioCraft/TRELLIS/TripoSR）/ DAG Workflow / Workflow 模板继承 / Blob 存储 / GPU 调度 / Run Comparison / HITL 协议 / Schema Registry / 多租户 / LangGraph 评估 / Bridge 自动 rollback / BlenderMCP 中转 / 可视化编辑器。

---

## H. 开源项目决策表

| 项目 | 决策 |
|---|---|
| LiteLLM | **直接用**（P1） |
| Instructor | **直接用**（P1） |
| judges | 借鉴 rubric 模板（P2） |
| LangGraph | 仅参考 StateGraph 语义 |
| ComfyUI | 外部 headless worker（P3） |
| AudioCraft / TRELLIS / TripoSR | 外部 worker（MVP 后） |
| Autonomix / VibeUE / BlenderMCP / UE5-MCP | 仅思路参考 |
| PydanticAI / AG2 / CrewAI / Diffusers / llm-council / MS Agent Framework | 放弃 |

---

## L. 一句话定位

vNext 是一套以 Task/Run/Workflow/Artifact 为一等公民、Review 为合法节点、UEOutputTarget 前置、双模 UE Bridge、5 类 Policy 分离、Dry-run + Checkpoint 保障可复现的多模型运行时；基础层（LiteLLM / Instructor）直接用，StateGraph 与 rubric 仅借语义，多模态生成工具外挂为 worker，UE 领域与运行时工程化部分全自研。
