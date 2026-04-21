# UE 三模式统一框架对象模型定义 v1

## 0. 文档目的

本文用于为 UE 游戏领域的多模型框架建立一套统一对象模型，使以下三类运行方式共享同一套核心抽象，而不是各写一套分裂实现：

- `basic_llm`：普通 LLM Client 模式，目标是返回稳定的结构化数据
- `production`：生产模式，目标是驱动多模型、多步骤、多 Artifact 的生成与转换链
- `standalone_review`：独立评审模式，目标是对答案、方案或资产进行比较、裁决、选优

本文只定义对象模型与运行时语义，不讨论具体 provider SDK 接法、UE 编辑器 API 细节或特定模型选型。

---

## 1. 顶层设计原则

### 1.1 三模式统一，但不混写

三模式并非三套完全独立系统，而是：

- 共用统一的 `Task / Run / Workflow / Step / Artifact / Verdict`
- 根据 `RunMode` 决定执行语义
- 允许 `production` 流内嵌 `review` 节点
- 允许 `basic_llm` 产物进入 `production`
- 允许 `production` 产物进入 `standalone_review`

### 1.2 框架的一等公民不是 message，而是 Task 与 Artifact

对于 UE 游戏生产链，聊天消息不是核心对象。真正应被建模的是：

- 用户要完成什么任务
- 任务被拆成哪些步骤
- 每一步产生什么中间产物
- 哪些产物可继续流转
- 哪些节点负责评审与裁决
- 最终如何导向 UE 可消费输出

### 1.3 Review 是通用能力，不只是顶层模式

Review 不应只作为独立模式存在，还应作为 `production` 工作流里的合法节点类型。
因此对象模型中必须同时支持：

- `standalone_review` 作为顶层运行模式
- `Step.type = review` 作为生产流节点类型

---

## 2. 核心对象总览

```text
RunMode
  └── Task
        └── Run
              ├── Workflow
              │     └── Step[*]
              ├── Artifact[*]
              ├── CandidateSet[*]
              ├── Verdict[*]
              └── TransitionPolicy
```

---

## 3. RunMode

### 3.1 定义

`RunMode` 用于声明本次运行的顶层语义。

建议枚举值：

- `basic_llm`
- `production`
- `standalone_review`

### 3.2 语义

#### `basic_llm`
适合：

- 结构化问答
- 信息抽取
- JSON/YAML 输出
- GDD 拆解
- 规则转换
- Spec Fragment 生成

运行特征：

- 可单步完成
- 通常不需要复杂 Artifact 链
- 重点是 schema 稳定与字段可消费

#### `production`
适合：

- 文本 → 图片 → 3D/资产
- 文本 → 音乐/音效
- 多模型串行/并行协作
- 资产候选生成与筛选
- 导入清单与元数据整理
- 导向 UE 侧落地

运行特征：

- 存在显式 Workflow
- 存在中间 Artifact
- 允许 review/select/branch/retry 节点

#### `standalone_review`
适合：

- 多答案比较
- 多张图选优
- 多个音乐候选评审
- 单一资产质量复审
- 多模型互评与主模型裁决

运行特征：

- 输入通常是 CandidateSet
- 输出通常是 Verdict
- 重点是比较、裁决与保留异议

---

## 4. Task

### 4.1 定义

`Task` 表示用户意图经过标准化后的任务对象，是运行的入口载体。

### 4.2 建议字段

```json
{
  "task_id": "task_001",
  "title": "Generate tavern environment art pack",
  "task_type": "asset_generation",
  "run_mode": "production",
  "domain": "ue_game_content",
  "intent_summary": "为 UE 场景生成酒馆主题资产链",
  "input_payload": {},
  "constraints": {},
  "expected_output": {},
  "review_policy": {}
}
```

### 4.3 字段说明

- `task_id`：任务唯一标识
- `title`：任务标题
- `task_type`：任务类别，如 `question_answer / structured_extraction / asset_generation / asset_review`
- `run_mode`：顶层运行模式
- `domain`：建议显式标识业务域，如 `ue_game_content`
- `intent_summary`：面向编排器的简述
- `input_payload`：原始输入
- `constraints`：风格、格式、预算、时延、分辨率、许可等约束
- `expected_output`：期望产物形式
- `review_policy`：是否需要评审、评审阈值、失败回退策略

---

## 5. Run

### 5.1 定义

`Run` 表示某次 Task 的具体执行实例。
同一 Task 可有多次 Run，例如不同随机种子、不同模型组合、不同预算策略下的运行。

### 5.2 建议字段

```json
{
  "run_id": "run_2026_04_19_001",
  "task_id": "task_001",
  "run_mode": "production",
  "status": "running",
  "created_at": "2026-04-19T12:00:00Z",
  "updated_at": "2026-04-19T12:03:00Z",
  "workflow_id": "wf_env_art_v1",
  "selected_profile": "quality_first",
  "execution_trace": []
}
```

### 5.3 说明

Run 是：

- 日志挂载点
- Artifact 生命周期挂载点
- 评审结果挂载点
- 重试与分支比较挂载点

建议任何可回放、可比对、可审计的信息都挂在 Run 维度，而不是仅散落在 Step 本地日志里。

---

## 6. Workflow

### 6.1 定义

`Workflow` 表示一张带有控制语义的任务图。
在 `basic_llm` 中可退化为单步流；在 `production` 中通常是多步 DAG；在 `standalone_review` 中可表现为“收集候选 → 审查 → 裁决”。

### 6.2 建议字段

```json
{
  "workflow_id": "wf_env_art_v1",
  "name": "Tavern Environment Pipeline",
  "version": "1.0",
  "entry_step_ids": ["step_extract_spec"],
  "steps": [],
  "transition_policy": {}
}
```

### 6.3 运行特征

Workflow 应支持：

- 串行步骤
- 并行 fan-out
- review gate
- select gate
- retry branch
- fallback path
- human escalation
- partial completion

---

## 7. Step

### 7.1 定义

`Step` 是 Workflow 中的最小执行单元。

### 7.2 建议枚举类型

- `generate`
- `transform`
- `review`
- `select`
- `merge`
- `validate`
- `export`
- `import`
- `retry`
- `branch`
- `human_gate`

### 7.3 建议字段

```json
{
  "step_id": "step_generate_concepts",
  "type": "generate",
  "name": "Generate concept images",
  "status": "pending",
  "provider_ref": "image_provider.main",
  "model_ref": "image_model_A",
  "inputs": [],
  "outputs": [],
  "depends_on": ["step_extract_spec"],
  "config": {},
  "transition_policy": {}
}
```

### 7.4 关键语义

- `inputs`：可引用 Task 输入或上游 Artifact
- `outputs`：生成的 Artifact 引用
- `depends_on`：依赖的 Step
- `config`：该步执行参数
- `transition_policy`：通过/失败/重试/升级逻辑

### 7.5 Step 与模式关系

#### 在 `basic_llm` 中
通常只有 1～3 个 Step：

- normalize input
- ask model
- validate schema

#### 在 `production` 中
Step 构成完整生产链，可能出现：

- 文本 spec 生成
- 图像生成
- 多候选筛选
- 图转 3D
- 资产打包
- UE 清单导出

#### 在 `standalone_review` 中
Step 常表现为：

- collect candidates
- anonymize
- review
- aggregate verdict

---

## 8. Artifact

### 8.1 定义

`Artifact` 是框架里的中间或最终产物。

### 8.2 Artifact 的重要性

在该框架中，Artifact 不是日志附件，而是生产链的核心输入输出单位。
后续节点不直接消费自然语言对话，而消费标准化 Artifact。

### 8.3 建议字段

```json
{
  "artifact_id": "art_001",
  "artifact_type": "concept_image",
  "role": "intermediate",
  "format": "png",
  "uri": "artifacts/run_001/concept_01.png",
  "producer_step_id": "step_generate_concepts",
  "metadata": {},
  "lineage": {},
  "validation": {}
}
```

### 8.4 建议 artifact_type

- `structured_answer`
- `spec_fragment`
- `design_brief`
- `concept_image`
- `texture_pack`
- `music_track`
- `sfx_clip`
- `mesh_asset`
- `material_asset`
- `candidate_bundle`
- `review_report`
- `ue_asset_manifest`
- `ue_import_plan`

### 8.5 关键属性

- `role`：`intermediate / final / reference / rejected`
- `format`：如 `json / png / wav / glb / uasset_manifest_json`
- `uri`：文件或对象存储路径
- `producer_step_id`：生成来源
- `metadata`：风格、分辨率、时长、许可、tags 等
- `lineage`：上游依赖关系
- `validation`：校验状态

---

## 9. CandidateSet

### 9.1 定义

`CandidateSet` 表示多个候选产物的集合，主要用于 review/select。

### 9.2 建议字段

```json
{
  "candidate_set_id": "candset_001",
  "source_step_id": "step_generate_concepts",
  "artifact_ids": ["art_001", "art_002", "art_003"],
  "selection_goal": "pick_best tavern concept image",
  "selection_constraints": {}
}
```

### 9.3 使用场景

- 多图选优
- 多音乐草案选优
- 多结构化回答比较
- 多资产版本对比
- 多模型输出裁决

---

## 10. Verdict

### 10.1 定义

`Verdict` 表示 review/select/validate 节点的结论对象。

### 10.2 建议字段

```json
{
  "verdict_id": "verdict_001",
  "target_type": "candidate_set",
  "target_id": "candset_001",
  "decision": "approve_one",
  "selected_artifact_ids": ["art_002"],
  "rejected_artifact_ids": ["art_001", "art_003"],
  "confidence": 0.82,
  "reasons": [],
  "dissent": [],
  "next_action": "continue"
}
```

### 10.3 常见 decision

- `approve`
- `approve_one`
- `approve_many`
- `reject`
- `revise`
- `retry_same_step`
- `fallback_model`
- `rollback`
- `human_review_required`

### 10.4 Verdict 的作用

Verdict 不只是“评语”，还会驱动流程控制：

- 是否进入下一步
- 是否重试当前步
- 是否切换模型
- 是否回退上一步
- 是否终止运行
- 是否要求人工确认

---

## 11. TransitionPolicy

### 11.1 定义

`TransitionPolicy` 定义从一个 Step 或 Verdict 进入下一个控制分支的规则。

### 11.2 建议字段

```json
{
  "on_success": "step_convert_to_mesh",
  "on_low_confidence": "step_review_second_pass",
  "on_reject": "step_regenerate_concepts",
  "on_human_required": "step_human_gate",
  "max_retries": 2
}
```

### 11.3 典型用途

- review 未通过则重试
- review 低置信度则二次评审
- validate 失败则回退
- 连续失败超过阈值则人工介入
- 某 provider 超时则 fallback

---

## 12. ProviderRef / ModelRef / CapabilityRef

虽然本文主轴不是 provider 设计，但对象模型里至少应预留引用位：

- `provider_ref`
- `model_ref`
- `capability_ref`

建议不要把 provider 细节硬编码到 Step.type 里。
同一种 `generate` 节点，可能会被：

- 文本模型执行
- 图像模型执行
- 音频模型执行
- 图转 3D 模型执行

因此应由 capability 层决定“谁能执行”，而非让 Step 自带业务耦合。

---

## 13. 三模式对象使用示例

### 13.1 basic_llm 示例

```json
{
  "task_type": "structured_extraction",
  "run_mode": "basic_llm",
  "workflow": {
    "steps": [
      {"step_id": "normalize_input", "type": "transform"},
      {"step_id": "generate_schema_output", "type": "generate"},
      {"step_id": "validate_json_schema", "type": "validate"}
    ]
  }
}
```

### 13.2 production 示例

```json
{
  "task_type": "asset_generation",
  "run_mode": "production",
  "workflow": {
    "steps": [
      {"step_id": "extract_design_spec", "type": "generate"},
      {"step_id": "generate_concepts", "type": "generate"},
      {"step_id": "review_concepts", "type": "review"},
      {"step_id": "convert_to_3d", "type": "transform"},
      {"step_id": "validate_assets", "type": "validate"},
      {"step_id": "export_manifest", "type": "export"}
    ]
  }
}
```

### 13.3 standalone_review 示例

```json
{
  "task_type": "asset_review",
  "run_mode": "standalone_review",
  "workflow": {
    "steps": [
      {"step_id": "collect_candidates", "type": "transform"},
      {"step_id": "review_candidates", "type": "review"},
      {"step_id": "emit_verdict", "type": "export"}
    ]
  }
}
```

---

## 14. 与 UE 落地的关系

对象模型必须对 UE 侧留出标准出口，但不应把 UE 侧编辑器操作耦死在核心模型里。
因此建议核心层只负责：

- 产出 `ue_asset_manifest`
- 产出 `ue_import_plan`
- 产出命名、路径、依赖和元数据

而真正的 UE 编辑器操作，由 Bridge 层处理。

这样做的好处是：

- 核心编排层可离线测试
- Artifact 与 Verdict 可脱离 UE 先验证
- UE Bridge 失败不污染上游对象模型
- 可以支持 Blender / DCC 中转链路

---

## 15. MVP 最小落地建议

若按最小闭环实现，建议先只落以下对象：

- `RunMode`
- `Task`
- `Run`
- `Workflow`
- `Step`
- `Artifact`
- `CandidateSet`
- `Verdict`
- `TransitionPolicy`

首批只支持以下 Step.type：

- `generate`
- `review`
- `validate`
- `export`

首批只支持以下 Artifact.type：

- `structured_answer`
- `concept_image`
- `music_track`
- `review_report`
- `ue_asset_manifest`

---

## 16. 不建议的错误建模方式

### 16.1 只围绕聊天消息建模
会导致生产链和资产链难以标准化。

### 16.2 把 review 当成 prompt 技巧
会失去它作为流程控制器的价值。

### 16.3 把 provider 细节写死在业务步骤里
会导致模型更换与 fallback 成本过高。

### 16.4 不给 Artifact 建 lineage
会导致后续追踪“这张图来自哪个描述、由哪个模型生成、为何被选中”变得困难。

---

## 17. 结论

这套对象模型的核心收敛点是：

- 三模式统一在一套数据结构下
- 生产流以内嵌 review 节点为合法机制
- Artifact 成为主输入输出单位
- Verdict 驱动流程控制，而不只是写评语
- UE 侧执行与核心编排层解耦

这使后续文档可以分别向下展开为：

1. `Production Workflow + Nested Review` 机制设计
2. `Artifact Contract 与 UE Asset Manifest` 设计
3. `UE Bridge` 最小可运行实现方案
