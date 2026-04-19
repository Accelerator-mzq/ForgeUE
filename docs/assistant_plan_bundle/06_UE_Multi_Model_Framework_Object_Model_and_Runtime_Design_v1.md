# UE 多模型框架：对象模型与运行时设计草案 v1

## 0. 文档目的

本文承接上一份《UE_Multi_Model_Framework_Repo_Mapping_and_Execution_Plan.md》，不再重复讨论“有哪些可借鉴 repo”，而是进一步给出一套**可直接指导实现**的统一对象模型与运行时设计。

目标不是做一个通用聊天式 llm_client，而是定义一套**面向 UE 游戏生产链**的多模型框架，使其同时支持：

1. **普通模式（Basic LLM Mode）**：输入任务，获得结构化回答或指定格式数据。
2. **生产模式（Production Mode）**：多模型协作生成文本、图片、音频、资产及中间产物。
3. **独立评审模式（Standalone Review Mode）**：对问题答案、候选产物、设计方案进行比较、打分、裁决。
4. **生产流内嵌评审（Embedded Review in Production）**：生产流程中任意阶段插入 review 节点，对候选结果筛选、回退、放行、分支。

本文的重点是：

- 统一三类运行方式的对象模型
- 定义生产流中 review 节点的合法地位
- 定义 Artifact / Candidate / Verdict / TransitionPolicy 等核心对象
- 为 UE 资产链、目录链、导入链预留接口
- 给出最小可运行的实现边界

---

## 1. 一句话结论

**该框架的正确形态，不是“一个 llm_client + 几个 if/else 模式”，而是一套以 Workflow 为主干、以 Artifact 为流转介质、以 ReviewEngine 为可独立/可嵌入能力的多模型运行时。**

更具体地说：

- **Basic LLM Mode** 是单步或少步的结构化回答路径。
- **Production Mode** 是主生产链，负责多模型生成与转换。
- **ReviewEngine** 既可作为顶层独立运行模式存在，也可作为 Production Workflow 中的 `review` 节点存在。
- UE 落地不是附属动作，而是生产链的目标出口之一。

---

## 2. 顶层设计原则

### 2.1 模式不是全部互斥的

顶层运行入口可以区分为：

- `basic_llm`
- `production`
- `standalone_review`

但在运行时语义上，`review` 不应只被理解为“顶层模式”，还必须被建模为生产工作流中的合法节点类型。

### 2.2 不以 message 为核心，以 task/workflow/artifact 为核心

普通聊天式 client 往往把 `messages[]` 当核心对象。

对你的场景，这不够。

这里真正应该成为一等公民的是：

- `Task`
- `Run`
- `Workflow`
- `Step`
- `Artifact`
- `CandidateSet`
- `ReviewNode`
- `Verdict`
- `TransitionPolicy`

### 2.3 统一入口，分层执行

同一个框架必须允许：

- 简单问答任务走 `basic_llm`
- 复杂多模态任务走 `production`
- 单独评审任务走 `standalone_review`
- 生产流中自动触发 review gate

### 2.4 产物优先于文本

在生产模式中，文本只是一类 Artifact。

框架必须把以下都视为可追踪的 Artifact：

- 结构化 JSON
- 纯文本说明
- 概念图
- 贴图
- 音乐片段
- 音效
- 3D 资产中间件
- UE 导入描述
- UE 资源清单
- 评审报告

### 2.5 评审不只是“评价”，还是流程控制机制

在生产流里，review 节点需要承担：

- 质量评估
- 候选筛选
- 进入下一步的放行
- 失败后的回退
- 改用其他 provider 的切换
- 保留多分支
- 人工介入升级

---

## 3. 顶层运行模型

## 3.1 RunMode

```json
{
  "run_mode": "basic_llm | production | standalone_review"
}
```

说明：

- `basic_llm`：单次结构化输出为主
- `production`：主生产链
- `standalone_review`：独立评审任务

注意：`review` 作为节点类型，不等于 `standalone_review` 这个顶层运行模式。

---

## 3.2 TaskType

建议显式区分任务类型：

```json
{
  "task_type": "question_answer | structured_extraction | plan_generation | image_generation | audio_generation | asset_derivation | workflow_production | review | ue_export"
}
```

说明：

- `task_type` 用于表征任务意图
- `run_mode` 用于表征运行策略

两者不要混用。

例如：

- “请把这个需求提取成 JSON” → `task_type=structured_extraction`, `run_mode=basic_llm`
- “根据角色说明生成图、再生成资产” → `task_type=workflow_production`, `run_mode=production`
- “对三张候选图做打分并选最优” → `task_type=review`, `run_mode=standalone_review`

---

## 4. 核心对象模型

## 4.1 Task

`Task` 表示用户要完成的目标，是整个运行的顶层输入对象。

### 建议结构

```json
{
  "task_id": "task_001",
  "task_type": "workflow_production",
  "run_mode": "production",
  "title": "Generate UE character asset chain",
  "description": "根据角色说明生成概念图并派生资产",
  "input": {},
  "constraints": {},
  "expected_output": {},
  "review_policy": {},
  "ue_target": {}
}
```

### 字段解释

- `task_id`：任务唯一标识
- `task_type`：任务意图类型
- `run_mode`：运行策略
- `title`：任务名称
- `description`：任务说明
- `input`：原始输入
- `constraints`：全局约束，如分辨率、风格、成本上限、时限
- `expected_output`：输出期望
- `review_policy`：评审规则，可以是全局默认规则
- `ue_target`：UE 落地目标，如项目名、目标目录、资产类型、命名规则

---

## 4.2 Run

`Run` 表示一次具体执行实例，用于支持同一 Task 的多次试运行、多版本对比、失败恢复。

### 建议结构

```json
{
  "run_id": "run_20260419_001",
  "task_id": "task_001",
  "status": "pending | running | paused | succeeded | failed | escalated",
  "started_at": "2026-04-19T10:00:00Z",
  "ended_at": null,
  "workflow_id": "wf_character_v1",
  "current_step_id": "step_generate_concept",
  "artifacts": [],
  "logs": [],
  "metrics": {}
}
```

### 作用

- 支持同一 Task 多次运行
- 保存中间状态
- 记录当前执行到哪一步
- 保存 Artifact 列表和指标
- 为后续对比“发散生成”或 A/B 试验打基础

---

## 4.3 Workflow

`Workflow` 是生产模式的主骨架，也是普通模式在复杂化后的统一抽象。

### 建议结构

```json
{
  "workflow_id": "wf_character_v1",
  "name": "Character Asset Pipeline",
  "version": "v1",
  "steps": [
    "step_extract_spec",
    "step_generate_concepts",
    "step_review_concepts",
    "step_derive_asset",
    "step_review_asset",
    "step_export_ue"
  ],
  "entry_step": "step_extract_spec"
}
```

### 说明

- `Workflow` 是图，不一定只能是线性数组
- 最小实现可以先做有向线性/分支流
- 后续可以扩展为 DAG

---

## 4.4 Step

`Step` 是工作流节点，是最关键的执行单位。

### 建议结构

```json
{
  "step_id": "step_generate_concepts",
  "type": "generate | transform | review | select | export | route | merge | human_gate",
  "name": "Generate concept images",
  "provider_policy": {},
  "input_bindings": [],
  "output_schema": {},
  "retry_policy": {},
  "transition_policy": {},
  "metadata": {}
}
```

### 关键说明

#### 合法节点类型建议

- `generate`：生成型节点（文本、图像、音频等）
- `transform`：转换型节点（图→图、图→资产描述、文本→结构化 JSON）
- `review`：评审节点
- `select`：候选选择节点
- `route`：条件路由节点
- `merge`：多分支汇合节点
- `export`：导出节点（如 UE 输出）
- `human_gate`：人工确认节点

这里最重要的一点是：

**`review` 必须是一等合法节点类型。**

---

## 4.5 Artifact

`Artifact` 是整个框架的核心流转介质。

### 建议结构

```json
{
  "artifact_id": "art_001",
  "artifact_type": "text | structured_json | image | audio | mesh | material | ue_manifest | review_report",
  "producer_step_id": "step_generate_concepts",
  "producer_model": "model_x",
  "uri": "file://...",
  "inline_data": null,
  "metadata": {},
  "parent_artifact_ids": [],
  "tags": []
}
```

### 关键字段解释

- `artifact_type`：必须显式声明产物类型
- `producer_step_id`：由哪个步骤生成
- `producer_model`：由哪个模型/服务生成
- `uri`：文件地址、对象存储地址、项目内路径
- `inline_data`：适用于小型 JSON、文本
- `metadata`：分辨率、格式、时长、采样率、风格标签、UE 目标类型等
- `parent_artifact_ids`：明确上游来源链

### 为什么它重要

你的场景里，“前一个模型生成的图片，后一个模型继续消费”是刚需。

没有 Artifact 这个对象，后续根本没法严肃管理依赖链、回放链、命名链、导出链。

---

## 4.6 Candidate 与 CandidateSet

评审节点不能只吃“单个结果”，还必须能处理候选集。

### Candidate

```json
{
  "candidate_id": "cand_a",
  "artifact_id": "art_img_a",
  "source_step_id": "step_generate_concepts",
  "source_model": "image_model_a",
  "score_hint": null,
  "notes": null
}
```

### CandidateSet

```json
{
  "candidate_set_id": "cset_001",
  "task_scope": "concept_images",
  "candidate_ids": ["cand_a", "cand_b", "cand_c"],
  "selection_policy": "single_best | multi_keep | threshold_pass"
}
```

### 作用

- 明确区分“产物”与“候选位”
- 为 review / select / merge 提供统一输入

---

## 4.7 ReviewNode

`ReviewNode` 本质上是 `Step(type=review)` 的增强配置对象，用于描述如何评审。

### 建议结构

```json
{
  "review_id": "rev_001",
  "review_scope": "answer | image | audio | asset | workflow_step_output",
  "review_mode": "single_judge | multi_judge | council | chief_judge",
  "candidate_set_id": "cset_001",
  "rubric": {},
  "judge_policy": {},
  "output_format": "review_report + verdict"
}
```

### review_mode 建议

- `single_judge`：单裁判模型
- `multi_judge`：多个裁判并行打分
- `council`：多个模型互评/交叉批判
- `chief_judge`：先收集评审意见，再由主裁判做终裁

### rubric 示例

```json
{
  "criteria": [
    "correctness",
    "completeness",
    "style_alignment",
    "ue_compatibility",
    "production_readiness"
  ],
  "weights": {
    "correctness": 0.25,
    "completeness": 0.2,
    "style_alignment": 0.2,
    "ue_compatibility": 0.2,
    "production_readiness": 0.15
  },
  "pass_threshold": 0.75
}
```

---

## 4.8 Verdict

`Verdict` 是评审节点输出的裁决对象。

### 建议结构

```json
{
  "verdict_id": "ver_001",
  "review_id": "rev_001",
  "decision": "approve | reject | retry_same | retry_other_model | rollback | escalate_human | keep_multiple",
  "selected_candidate_ids": ["cand_b"],
  "rejected_candidate_ids": ["cand_a", "cand_c"],
  "confidence": 0.81,
  "reasons": [],
  "followup_actions": []
}
```

### 为什么要单独建模

很多系统会把“评审报告”和“流程决策”混成一段自然语言。

这不够。

你这里必须明确区分：

- `review_report`：分析说明
- `verdict`：流程控制结论

因为只有 `verdict` 才能被 Orchestrator 继续消费。

---

## 4.9 TransitionPolicy

`TransitionPolicy` 用于描述节点执行完成后，如何根据结果决定下一步。

### 建议结构

```json
{
  "on_success": "next:step_derive_asset",
  "on_review_approve": "next:step_export_ue",
  "on_review_reject": "next:step_generate_concepts_retry",
  "on_retry_exhausted": "next:step_human_gate",
  "on_escalate": "pause"
}
```

### 作用

这是把 review 真正嵌进 production 的关键点之一。

没有 TransitionPolicy，review 只能“评价”；
有了 TransitionPolicy，review 才能成为生产流控制机制。

---

## 4.10 ProviderPolicy

`ProviderPolicy` 描述某节点选模型的规则。

### 建议结构

```json
{
  "capability_required": "image_generation",
  "preferred_models": ["provider_a/model_x", "provider_b/model_y"],
  "fallback_models": ["provider_c/model_z"],
  "cost_limit": 5.0,
  "latency_limit_ms": 60000,
  "must_support_inputs": ["text"],
  "must_support_outputs": ["image"]
}
```

### 为什么重要

因为你的场景里不是“一个模型做全部事”，而是**按能力路由**。

---

## 4.11 UEOutputTarget

这是为 UE 落地预留的目标对象。

### 建议结构

```json
{
  "project_name": "MyUEProject",
  "asset_root": "/Game/Generated/Characters/HeroA",
  "asset_naming_policy": "gdd_preferred_then_house_rules",
  "expected_asset_types": ["texture", "material", "sound", "mesh"],
  "import_mode": "manifest_only | bridge_execute",
  "validation_hooks": ["path_check", "name_check", "type_check"]
}
```

### 说明

`UEOutputTarget` 不是“最后才考虑”的东西。

生产模式在早期就要知道最终目标，以便前面节点的分辨率、格式、命名、目录选择都与目标一致。

---

## 5. 三种顶层运行模式的统一建模

## 5.1 Basic LLM Mode

### 目标

获取结构化回答或指定格式数据。

### 最小路径

```text
Task -> Single/Small Workflow -> Structured Output Artifact
```

### 适合的任务

- 需求抽取
- GDD 字段提取
- 计划生成
- JSON/YAML 生成
- 提示词转换
- Spec Fragment 生成

### 运行特点

- 通常 1~3 步
- 可以没有 review
- 也可以在高风险场景加一个 review step

---

## 5.2 Production Mode

### 目标

生成可继续流转的 Artifact，最终导向 UE 可接入输出。

### 典型路径

```text
Task
  -> Spec Extract
  -> Generate Candidates
  -> Review Gate
  -> Derive Asset
  -> Review Gate
  -> Export UE
```

### 运行特点

- 多步骤
- 多 provider
- 强依赖 Artifact 链
- review 是高频合法节点

---

## 5.3 Standalone Review Mode

### 目标

独立对问题答案、候选图片、候选音频、候选资产或某一步结果做裁决。

### 典型路径

```text
Question / CandidateSet
  -> Judge(s)
  -> ReviewReport
  -> Verdict
```

### 适合的任务

- 多模型回答比选
- 多张图比选
- 多个音乐草案评估
- 对已有资产的质量审查
- 对某一步结果做独立验收

---

## 6. 生产流内嵌评审的标准语义

这是本设计最关键的部分。

## 6.1 review 不是附属功能，而是 workflow 的原生节点

必须明确：

- `review` 节点可以出现在任意生成节点之后
- `review` 节点必须能消费 CandidateSet 或单个 Artifact
- `review` 节点必须输出 `review_report` + `verdict`
- `verdict` 必须进入 TransitionPolicy

---

## 6.2 review 节点的合法结果

建议至少支持以下决策：

- `approve`
- `reject`
- `retry_same`
- `retry_other_model`
- `rollback`
- `keep_multiple`
- `escalate_human`

这意味着 review 节点可以直接控制：

- 是否进入下一步
- 是否重跑当前步
- 是否切换 provider
- 是否退回前一步
- 是否保留多候选继续 downstream
- 是否转人工

---

## 6.3 典型嵌套评审例子

### 例 1：角色概念图生产链

```text
角色需求
  -> 基础结构化提取
  -> 生成概念图 A/B/C
  -> review：筛选最优图
  -> 根据选中图派生贴图/材质描述
  -> review：检查风格一致性与 UE 可用性
  -> 导出 UE 资源描述
```

### 例 2：场景音乐链

```text
场景说明
  -> 提取音乐标签
  -> 生成音乐草案 1/2/3
  -> review：选中最符合情绪目标者
  -> 后处理与元数据整理
  -> review：检查时长/风格/循环点
  -> 输出 UE 音频清单
```

### 例 3：图到资产链

```text
输入概念图
  -> 图像理解 / 结构化特征提取
  -> 派生 3D 草模 / 材质描述
  -> review：检查几何合理性、纹理风格、命名与路径
  -> 输出资产中间件 + UE 导入清单
```

---

## 7. 最小 Schema 草案

## 7.1 顶层任务请求

```json
{
  "task_id": "task_001",
  "task_type": "workflow_production",
  "run_mode": "production",
  "title": "Generate stylized character asset chain",
  "description": "从角色设定到概念图，再到 UE 可导入资源描述",
  "input": {
    "character_brief": "..."
  },
  "constraints": {
    "style": "stylized fantasy",
    "image_resolution": "1024x1024",
    "max_cost": 20
  },
  "expected_output": {
    "artifacts": ["image", "structured_json", "ue_manifest"]
  },
  "review_policy": {
    "enabled": true,
    "default_mode": "chief_judge"
  },
  "ue_target": {
    "project_name": "DemoProject",
    "asset_root": "/Game/Generated/Characters/Hero01"
  }
}
```

---

## 7.2 生成节点输出示例

```json
{
  "artifact_id": "art_concept_001",
  "artifact_type": "image",
  "producer_step_id": "step_generate_concepts",
  "producer_model": "providerA/image-gen-v1",
  "uri": "s3://bucket/run_001/concept_a.png",
  "metadata": {
    "resolution": "1024x1024",
    "style": "stylized fantasy",
    "seed": 12345
  },
  "parent_artifact_ids": ["art_character_spec_001"],
  "tags": ["concept", "character", "candidate_a"]
}
```

---

## 7.3 评审输出示例

```json
{
  "review_report": {
    "review_id": "rev_001",
    "summary": "candidate_b 在风格统一性和角色辨识度上更优",
    "scores": {
      "cand_a": 0.62,
      "cand_b": 0.84,
      "cand_c": 0.71
    },
    "issues": {
      "cand_a": ["配色不稳定"],
      "cand_c": ["轮廓识别度偏低"]
    }
  },
  "verdict": {
    "verdict_id": "ver_001",
    "review_id": "rev_001",
    "decision": "approve",
    "selected_candidate_ids": ["cand_b"],
    "rejected_candidate_ids": ["cand_a", "cand_c"],
    "confidence": 0.82,
    "reasons": ["风格一致性最高", "便于后续资产派生"],
    "followup_actions": ["next:step_derive_asset"]
  }
}
```

---

## 8. 运行时组件建议

## 8.1 Orchestrator

负责：

- 加载 Task
- 确定 RunMode
- 解析 Workflow
- 调度 Step 执行
- 根据 Verdict 和 TransitionPolicy 决定下一步
- 保存 Run 状态

## 8.2 Provider Adapter Layer

负责：

- 统一调用文本、图像、音频、3D/资产服务
- 标准化输入输出
- 处理重试/超时/fallback
- 把原始结果封装成 Artifact

## 8.3 Artifact Store

负责：

- 保存各类 Artifact
- 建立 parent-child 链
- 提供 URI / inline_data 访问
- 为 review 与 export 提供输入

## 8.4 Review Engine

负责：

- 消费 CandidateSet 或 Artifact
- 调用一个或多个 judge model
- 输出 review_report + verdict

## 8.5 Policy Engine

负责：

- TransitionPolicy
- RetryPolicy
- ProviderPolicy
- BudgetPolicy
- EscalationPolicy

## 8.6 UE Bridge

负责：

- 将 `ue_manifest` 或其他输出变成 UE 可执行输入
- 检查命名、路径、类型、资源依赖
- 可选：触发实际导入或只生成清单

---

## 9. 推荐目录结构（实现侧）

```text
framework/
├── core/
│   ├── task.py
│   ├── run.py
│   ├── workflow.py
│   ├── step.py
│   ├── artifact.py
│   ├── candidate.py
│   ├── review.py
│   ├── verdict.py
│   └── policies.py
├── runtime/
│   ├── orchestrator.py
│   ├── dispatcher.py
│   ├── state_store.py
│   └── transition_engine.py
├── providers/
│   ├── base_adapter.py
│   ├── text/
│   ├── image/
│   ├── audio/
│   └── asset/
├── review_engine/
│   ├── judges.py
│   ├── rubric.py
│   ├── council.py
│   └── chief_judge.py
├── artifact_store/
│   ├── repository.py
│   ├── serializers.py
│   └── lineage.py
├── ue_bridge/
│   ├── manifest.py
│   ├── validators.py
│   ├── exporters.py
│   └── adapters/
├── workflows/
│   ├── basic/
│   ├── production/
│   └── review/
└── schemas/
    ├── task_schema.json
    ├── artifact_schema.json
    ├── review_schema.json
    └── ue_manifest_schema.json
```

---

## 10. 最小可运行版本（MVP）边界

不建议一开始就做全图编排 + 任意多模态 + 真正 UE 自动导入全链。

建议先做如下 MVP：

### 10.1 必做

- 支持 3 种顶层运行模式
- 支持线性 production workflow
- 支持 `review` 作为 production 内嵌节点
- 支持 Artifact 对象与 lineage
- 支持至少一种结构化输出 schema
- 支持至少一种 CandidateSet -> Review -> Verdict 闭环
- 支持导出 `ue_manifest`

### 10.2 可暂缓

- 任意 DAG
- 复杂多分支 merge
- 真正 UE 编辑器内即时导入
- 太多 provider 类型
- 高级预算调度
- 人工交互 UI

### 10.3 MVP 推荐示例链

**示例链 A：普通模式**

```text
需求文本 -> 结构化提取 -> JSON Artifact
```

**示例链 B：生产模式 + 内嵌评审**

```text
角色说明 -> 概念图候选 -> review -> 选中图 -> UE Manifest
```

**示例链 C：独立评审模式**

```text
候选图 A/B/C -> multi_judge -> verdict
```

---

## 11. 与 UE 场景对齐的额外要求

## 11.1 命名与目录不应后置处理

前面步骤就要知道：

- 目标目录
- 资源类型
- 命名规则
- 是否遵循 GDD 指定命名

## 11.2 产物元数据必须完整

例如：

- 图片：分辨率、色彩空间、风格标签
- 音频：采样率、时长、循环信息
- 资产：格式、拓扑复杂度、目标用途
- UE 输出：目标路径、目标资产类、依赖关系

## 11.3 评审 rubric 必须加入 UE 兼容维度

不能只评“看起来好不好”，还要评：

- 是否适合 UE 使用
- 是否满足资源命名/目录规则
- 是否适合继续下游加工
- 是否符合项目风格基线

---

## 12. 常见错误设计（应避免）

### 12.1 把三种模式都写进一个超大 `run_task()` 函数

后果：

- 分支过多
- review 逻辑散落
- Artifact 无法稳定管理

### 12.2 把 review 只做成一条 prompt

后果：

- 无法输出稳定 verdict
- 无法作为流程控制节点使用

### 12.3 不建 Artifact lineage

后果：

- 无法回答“这个资产来自哪张图”
- 无法做失败回滚
- 无法对比多次 run

### 12.4 不区分 review_report 和 verdict

后果：

- 分析文本无法驱动 runtime

### 12.5 UE 输出只在最后一步临时拼接

后果：

- 前面的分辨率、命名、路径、格式无法保证与 UE 目标一致

---

## 13. 执行侧落地顺序建议

### Phase 1：对象模型定稿

先落定这些 schema：

- Task
- Run
- Workflow
- Step
- Artifact
- CandidateSet
- ReviewNode
- Verdict
- UEOutputTarget

### Phase 2：最小运行时

- Orchestrator
- Artifact Store
- Basic LLM 执行链
- Standalone Review 执行链

### Phase 3：生产流 + review gate

- Production Workflow Runner
- `review` 节点嵌入
- TransitionPolicy 实装

### Phase 4：UE Manifest 与桥接

- `ue_manifest` schema
- 路径/命名/类型校验
- 生成 UE 侧输入描述

### Phase 5：多模态扩展

- image adapters
- audio adapters
- asset adapters
- 上下游 Artifact 传递

---

## 14. 最终结论

你的框架不应被定义成“一个支持三种模式的 llm_client”。

更准确的定义应该是：

**一个以 Workflow 为主干、以 Artifact 为介质、支持普通结构化输出、支持多模型生产、支持独立评审与生产流内嵌评审，并以 UE 落地为目标出口的多模型运行时框架。**

在这个框架里：

- `basic_llm` 解决“给我返回指定格式数据”
- `production` 解决“多模型协作生成与流转产物”
- `review` 既能独立运行，也能嵌入生产流中承担质量闸门与流程控制
- `UEOutputTarget` 保证整个系统从前期就与 UE 目标对齐

这才是后续实现不会跑偏的正确抽象。

