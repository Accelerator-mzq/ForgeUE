# UE 生产链多模型框架 —— 统一架构方案 vNext

## Context

合并三份输入产出统一方案：
- Claude 独立方案 v1（PayloadRef / 两段式 type / risk_level / Dry-run Pass / Checkpoint+hash / UE Bridge 单向写边界）
- Claude 交叉评审报告 v1（识别了两边互补点、1 处架构分歧、13 项必须采纳、12 项必须新增）
- assistant 方案包 v1（9 对象模型、TaskType/RunMode 分离、UEOutputTarget 前置、CandidateSet+Candidate 双层、review_report/verdict 分离、5 维 scoring、5 类 Policy、UE Bridge Inspect/Plan/Execute + Evidence）

**本方案是唯一权威。**凡与本方案冲突的先前文档，以本方案为准。vNext 后所有实现直接照本方案拆解任务，不再回头辩论对象模型。

---

## A. 统一术语表

下表为 vNext 的**权威命名**。出现差异命名一律以本表为准。

| 术语                                                         | 定义                                                         | 来源                    | 旧命名（作废）                          |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ----------------------- | --------------------------------------- |
| `RunMode`                                                    | 顶层运行语义枚举：`basic_llm` / `production` / `standalone_review` | 共识                    | —                                       |
| `TaskType`                                                   | 任务意图枚举，与 RunMode 正交                                | assistant               | Task.intent（Claude）                   |
| `Task`                                                       | 用户意图经标准化后的入口对象                                 | 共识                    | —                                       |
| `Run`                                                        | Task 的一次执行实例                                          | 共识                    | —                                       |
| `Workflow`                                                   | 带控制语义的 Step 图                                         | 共识                    | —                                       |
| `Step`                                                       | Workflow 最小执行单元                                        | 共识                    | `Node`（Claude）                        |
| `Step.type`                                                  | 11 种合法类型（§B.5）                                        | assistant               | `Node.role`（Claude）                   |
| `Step.risk_level`                                            | 调度风险级别：`low / medium / high`                          | Claude 原创             | —                                       |
| `Artifact`                                                   | 生产链中间/最终产物，一等公民                                | 共识                    | —                                       |
| `artifact_type`                                              | 内部两段式 `<modality>.<shape>` / 外部扁平显示名             | Claude + assistant 映射 | 纯扁平枚举（assistant）                 |
| `PayloadRef`                                                 | Artifact 载体三态：`inline / file / blob`                    | Claude 原创             | `uri + inline_data` 两字段（assistant） |
| `Artifact.role`                                              | `intermediate / final / reference / rejected`                | assistant               | —                                       |
| `Candidate`                                                  | CandidateSet 成员，携带 score_hint/notes/source_model        | assistant               | —                                       |
| `CandidateSet`                                               | Candidate 容器 + selection_policy                            | assistant               | Bundle.pack（Claude）                   |
| `ReviewNode`                                                 | `Step(type=review)` 的增强配置对象                           | assistant               | `Reviewer + Gate`（Claude）             |
| `ReviewReport`                                               | 评审分析说明对象                                             | assistant               | Verdict.reasons（Claude 旧）            |
| `Verdict`                                                    | 流程控制结论对象（与 ReviewReport 分离）                     | assistant               | 合并在 Verdict（Claude 旧）             |
| `Verdict.decision`                                           | 9 种枚举（§B.8）                                             | assistant               | 3 种（Claude v1）                       |
| `TransitionPolicy`                                           | 节点转移策略                                                 | 共识                    | `Policy`（Claude 旧）                   |
| `RetryPolicy / ProviderPolicy / BudgetPolicy / EscalationPolicy` | 其余 4 类策略                                                | assistant               | —                                       |
| `UEOutputTarget`                                             | Task 层前置的 UE 目标对象                                    | assistant               | 放在 export.config（Claude 旧）         |
| `UEAssetManifest`                                            | 声明式资产清单                                               | assistant               | —                                       |
| `UEImportPlan`                                               | 执行式导入计划                                               | assistant               | —                                       |
| `Evidence`                                                   | UE Bridge 操作证据对象                                       | assistant               | 审计日志（Claude 模糊）                 |
| `Checkpoint`                                                 | Step 完成后的 hash 快照                                      | Claude 原创             | —                                       |
| `DryRunPass`                                                 | Run 启动前零副作用预检阶段                                   | Claude 原创             | —                                       |
| `DeterminismPolicy`                                          | seed 传递 + 模型版本锁                                       | 交叉评审新增            | —                                       |

---

## B. 统一对象模型

所有字段均为 Pydantic schema，括号内标注「必填 / 可选」与类型。

### B.1 RunMode + TaskType

```python
class RunMode(str, Enum):
    basic_llm = "basic_llm"
    production = "production"
    standalone_review = "standalone_review"

class TaskType(str, Enum):
    structured_extraction = "structured_extraction"
    plan_generation = "plan_generation"
    asset_generation = "asset_generation"
    asset_review = "asset_review"
    ue_export = "ue_export"
    # 可扩展
```

### B.2 Task（必填 + 可选清晰区分）

```python
class Task(BaseModel):
    task_id: str                     # 必填
    task_type: TaskType              # 必填
    run_mode: RunMode                # 必填
    title: str                       # 必填
    description: str | None = None
    input_payload: dict              # 必填
    constraints: dict = {}           # 可选（style/resolution/budget/latency）
    expected_output: dict            # 必填（至少声明 artifact types）
    review_policy: ReviewPolicy | None = None
    ue_target: UEOutputTarget | None = None   # production/ue_export 时必填
    determinism_policy: DeterminismPolicy | None = None
    project_id: str                  # 必填（多租户）
```

### B.3 Run

```python
class Run(BaseModel):
    run_id: str
    task_id: str
    project_id: str
    status: Literal["pending","running","paused","succeeded","failed","escalated"]
    started_at: datetime
    ended_at: datetime | None = None
    workflow_id: str
    current_step_id: str | None = None
    artifact_ids: list[str] = []
    checkpoints: list[Checkpoint] = []
    trace_id: str                    # OTel trace
    metrics: dict = {}               # cost / latency / retries
```

### B.4 Workflow

```python
class Workflow(BaseModel):
    workflow_id: str
    name: str
    version: str
    entry_step_id: str
    step_ids: list[str]
    transition_policy: TransitionPolicy
    # MVP 先支持有向线性+分支；DAG 拓扑保留接口
    # template_ref 字段在 G 阶段引入
```

### B.5 Step

```python
class StepType(str, Enum):
    generate = "generate"
    transform = "transform"
    review = "review"
    select = "select"
    merge = "merge"
    validate = "validate"
    export = "export"
    import_ = "import"
    retry = "retry"
    branch = "branch"
    human_gate = "human_gate"
    # MVP 优先实现：generate / transform / review / validate / export / human_gate

class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class Step(BaseModel):
    step_id: str
    type: StepType
    name: str
    risk_level: RiskLevel = RiskLevel.low
    capability_ref: str              # e.g. "text.structured" / "image.generation" / "review.judge"
    provider_policy: ProviderPolicy | None = None
    retry_policy: RetryPolicy | None = None
    transition_policy: TransitionPolicy | None = None
    input_bindings: list[InputBinding]
    output_schema: dict              # Pydantic/JSONSchema
    depends_on: list[str] = []
    config: dict = {}
    metadata: dict = {}
```

### B.6 Artifact

```python
class PayloadRef(BaseModel):
    kind: Literal["inline","file","blob"]
    inline_value: Any | None = None  # 当 kind=inline
    file_path: str | None = None     # 当 kind=file（相对 Artifact Store root）
    blob_key: str | None = None      # 当 kind=blob
    size_bytes: int

class ArtifactType(BaseModel):
    """两段式: <modality>.<shape>"""
    modality: Literal["text","image","audio","mesh","material","bundle","ue"]
    shape: str                        # e.g. "structured","raster","waveform","gltf","asset_ref","pack"
    display_name: str                 # 对外扁平名: "concept_image" / "music_track" / ...

class Artifact(BaseModel):
    artifact_id: str
    artifact_type: ArtifactType
    role: Literal["intermediate","final","reference","rejected"]
    format: str
    mime_type: str
    payload_ref: PayloadRef
    schema_version: str
    hash: str                         # 内容哈希（用于 Checkpoint 命中）
    producer: ProducerRef             # {run_id, step_id, provider, model}
    lineage: Lineage                  # {source_artifact_ids, variant_group_id, variant_kind, transformation_kind, selected_by_verdict_id}
    metadata: dict                    # 按 modality 扩展（§D）
    validation: ValidationRecord
    tags: list[str] = []
    created_at: datetime
```

### B.7 Candidate / CandidateSet

```python
class Candidate(BaseModel):
    candidate_id: str
    artifact_id: str
    source_step_id: str
    source_model: str
    score_hint: float | None = None
    notes: str | None = None

class CandidateSet(BaseModel):
    candidate_set_id: str
    source_step_id: str
    candidate_ids: list[str]
    selection_goal: str              # 人类可读
    selection_policy: Literal["single_best","multi_keep","threshold_pass"]
    selection_constraints: dict = {}
```

### B.8 ReviewNode / ReviewReport / Verdict

```python
class ReviewMode(str, Enum):
    single_judge = "single_judge"
    multi_judge = "multi_judge"
    council = "council"
    chief_judge = "chief_judge"

class ReviewNode(BaseModel):
    review_id: str
    review_scope: Literal["answer","image","audio","mesh","asset","workflow_step_output"]
    review_mode: ReviewMode
    target_kind: Literal["artifact","candidate_set"]
    target_id: str
    rubric: Rubric                   # §B.10
    judge_policy: ProviderPolicy

class ReviewReport(BaseModel):      # 分析对象
    report_id: str
    review_id: str
    summary: str
    scores_by_candidate: dict[str, DimensionScores]
    issues_per_candidate: dict[str, list[str]]

class DimensionScores(BaseModel):
    constraint_fit: float
    style_consistency: float
    production_readiness: float
    technical_validity: float
    risk_score: float

class Decision(str, Enum):
    approve = "approve"
    approve_one = "approve_one"
    approve_many = "approve_many"
    reject = "reject"
    revise = "revise"
    retry_same_step = "retry_same_step"
    fallback_model = "fallback_model"
    rollback = "rollback"
    human_review_required = "human_review_required"

class Verdict(BaseModel):           # 流程控制对象
    verdict_id: str
    review_id: str
    report_id: str                   # 指向 ReviewReport
    decision: Decision
    selected_candidate_ids: list[str] = []
    rejected_candidate_ids: list[str] = []
    confidence: float
    reasons: list[str] = []
    dissent: list[str] = []
    recommended_next_step_id: str | None = None
    revision_hint: dict | None = None  # 传给上游 Generator 的结构化提示
    followup_actions: list[str] = []
```

### B.9 Policies（5 类）

```python
class TransitionPolicy(BaseModel):
    on_success: str | None = None
    on_approve: str | None = None
    on_reject: str | None = None
    on_revise: str | None = None
    on_retry: str | None = None
    on_fallback: str | None = None
    on_rollback: str | None = None
    on_human: str | None = None
    max_retries: int = 2
    max_revise: int = 2              # Claude 原创硬上限
    timeout_sec: int | None = None

class RetryPolicy(BaseModel):
    max_attempts: int
    backoff: Literal["fixed","exponential"]
    retry_on: list[str]              # e.g. ["timeout","schema_fail","provider_error"]

class ProviderPolicy(BaseModel):
    capability_required: str
    preferred_models: list[str]
    fallback_models: list[str]
    cost_limit: float | None = None
    latency_limit_ms: int | None = None

class BudgetPolicy(BaseModel):
    total_cost_cap_usd: float | None = None
    gpu_seconds_cap: float | None = None

class EscalationPolicy(BaseModel):
    on_exhausted: Literal["human_gate","stop","log_only"]
    notify_channel: str | None = None

class ReviewPolicy(BaseModel):      # Task 层默认评审配置
    enabled: bool = True
    default_mode: ReviewMode = ReviewMode.single_judge
    pass_threshold: float = 0.75
```

### B.10 Rubric

```python
class RubricCriterion(BaseModel):
    name: Literal["constraint_fit","style_consistency","production_readiness","technical_validity","risk_score"]
    weight: float
    min_score: float = 0.0

class Rubric(BaseModel):
    criteria: list[RubricCriterion]
    pass_threshold: float
```

### B.11 UE 相关对象

```python
class UEOutputTarget(BaseModel):
    project_name: str
    project_root: str               # 本地 UE 工程绝对路径
    asset_root: str                 # e.g. "/Game/Generated/Tavern"
    asset_naming_policy: Literal["gdd_mandated","house_rules","gdd_preferred_then_house_rules"]
    expected_asset_kinds: list[str] # texture/static_mesh/sound_wave/...
    import_mode: Literal["manifest_only","bridge_execute"]  # MVP 默认 manifest_only
    validation_hooks: list[str]

class UEAssetManifest(BaseModel):   # 声明式
    manifest_id: str
    schema_version: str
    run_id: str
    project_target: dict
    assets: list[UEAssetEntry]
    import_rules: dict
    naming_policy: dict
    path_policy: dict
    dependencies: list[UEDependency]

class UEAssetEntry(BaseModel):
    asset_entry_id: str
    artifact_id: str
    asset_kind: str                 # texture/static_mesh/sound_wave/material/...
    source_uri: str
    target_object_path: str
    target_package_path: str
    ue_naming: dict
    import_options: dict
    metadata_overrides: dict = {}

class UEImportPlan(BaseModel):      # 执行式
    plan_id: str
    manifest_id: str
    operations: list[UEImportOperation]

class UEImportOperation(BaseModel):
    op_id: str
    kind: Literal["create_folder","import_texture","import_audio","import_static_mesh",
                   "create_material_from_template","create_sound_cue_from_template"]
    asset_entry_id: str
    depends_on: list[str] = []      # 内部依赖顺序

class Evidence(BaseModel):
    evidence_item_id: str
    op_id: str
    kind: str
    status: Literal["success","failed","skipped"]
    source_uri: str | None = None
    target_object_path: str | None = None
    log_ref: str | None = None
    error: str | None = None
```

### B.12 运行时辅助对象

```python
class Checkpoint(BaseModel):
    step_id: str
    artifact_hashes: list[str]
    completed_at: datetime

class ValidationRecord(BaseModel):
    status: Literal["pending","passed","failed"]
    checks: list[ValidationCheck]
    warnings: list[str] = []
    errors: list[str] = []

class ValidationCheck(BaseModel):
    name: str
    result: Literal["passed","failed","skipped"]
    detail: str | None = None

class DeterminismPolicy(BaseModel):
    seed_propagation: bool = True
    model_version_lock: bool = True
    hash_verify_on_resume: bool = True
```

---

## C. 统一 Workflow 机制

### C.1 三模式共享调度器，不分裂实现

| RunMode             | Workflow 形态                       | Step 数量级 | 必选 Step 类型                                    |
| ------------------- | ----------------------------------- | ----------- | ------------------------------------------------- |
| `basic_llm`         | 单步或线性 2–3 步                   | 1–3         | generate + validate                               |
| `production`        | 有向线性 + 分支（MVP）；DAG（后置） | 5–15        | generate + review + transform + validate + export |
| `standalone_review` | 线性评审链                          | 3–5         | transform(collect) + review + export(verdict)     |

### C.2 Run 生命周期（9 阶段，严格顺序）

```
1. Task ingestion         → 解析 Task，确定 RunMode，加载 Workflow
2. Workflow resolution    → 解析 Workflow template，构造 Step 实例
3. Dry-run Pass           → §C.3，零副作用预检；失败则 Run 直接置 failed，不进入执行
4. Scheduling plan        → §C.4，按 depends_on + risk_level 生成执行计划
5. Step execution         → 逐 Step 调用对应 Executor；完成后写 Checkpoint
6. Verdict dispatching    → review Step 产出 Verdict 后由 transition_engine 决定下一步
7. Validation gates       → 每次产物入 Store 前校验 schema / 格式 / UE 规则
8. Export                 → 生成 UEAssetManifest（+ UEImportPlan）
9. Run finalize           → 写 Run 指标、trace、artifact lineage 归档
```

### C.3 Dry-run Pass 预检项（Run 启动前必跑，Claude 原创 + 评审扩展）

```
- manifest 解析成功
- 所有 Step 的 output_schema 合法（Pydantic/JSONSchema）
- ProviderPolicy 中的 preferred_models 在 LiteLLM 中可达
- 所有 input_bindings 能解析（Task.input 或上游 Artifact 存在）
- UEOutputTarget.project_root 可访问，asset_root 合法
- UE 侧路径无当前同名冲突（warn-level，不阻断）
- Budget 估算不超 BudgetPolicy.total_cost_cap_usd
- Secrets 齐全（所需 provider 的 API key 已注入）
- 若 resume：所有已有 Checkpoint 的 artifact_hash 与现存 Artifact 一致
```

### C.4 调度规则（Scheduler）

```
1. 构建 DAG（MVP 限制为线性 + 一级分支）
2. 入度为 0 的 Step 先跑；同层按 risk_level 升序
3. 每个 Step 完成后：
   - 计算 artifact_hash
   - 写 Checkpoint
   - 触发 transition_engine：按 Verdict.decision 或 on_success 走下一步
4. revise 回环：每次触发把 max_revise 计数 +1；超上限自动转 Decision.reject
5. 并发上限：ResourceBudget 约束同时执行的 Step 数
```

### C.5 Review 嵌入规则

```
在任何 generate/transform 之后允许插入 review 节点。
标准插入位置：
- 高发散输出后（candidate review）
- 高成本转换前（quality gate）
- 导入 UE 前（compliance review）
- 失败分岔点（recovery review）

嵌入形式：
- review Step 消费 Artifact 或 CandidateSet
- 产出 ReviewReport + Verdict（两对象同时落库）
- 下游由 TransitionPolicy.on_{decision} 决定转向
```

### C.6 Failure Mode ↔ Decision 映射（交叉评审新增）

| FailureMode            | 触发条件                            | 默认 Decision                    | 可配置项                      |
| ---------------------- | ----------------------------------- | -------------------------------- | ----------------------------- |
| provider_timeout       | LiteLLM 超时                        | retry_same_step → fallback_model | RetryPolicy.max_attempts      |
| schema_validation_fail | Instructor 返回 schema 不符         | retry_same_step                  | RetryPolicy.retry_on          |
| review_below_threshold | Verdict.confidence < pass_threshold | revise                           | TransitionPolicy.max_revise   |
| ue_path_conflict       | UE Bridge 发现目标路径已有资产      | human_review_required            | import_rules.allow_overwrite  |
| budget_exceeded        | 累计成本超 cap                      | escalate_human → stop            | EscalationPolicy.on_exhausted |
| disk_full              | Artifact Store 写失败               | rollback → stop                  | —                             |

---

## D. Unified Artifact Contract

### D.1 artifact_type 两段式 ↔ 扁平显示名映射（必须一一对应）

| 内部 modality.shape    | 外部 display_name                 | 典型 format |
| ---------------------- | --------------------------------- | ----------- |
| `text.structured`      | `structured_answer`               | json        |
| `text.freeform`        | `design_brief` / `spec_fragment`  | md/txt      |
| `image.raster`         | `concept_image` / `texture_image` | png/jpg     |
| `image.sprite_sheet`   | `sprite_sheet`                    | png         |
| `audio.waveform`       | `music_track` / `sfx_clip`        | wav/mp3     |
| `audio.midi`           | `music_midi`                      | mid         |
| `mesh.gltf`            | `mesh_asset`                      | glb/gltf    |
| `mesh.fbx`             | `mesh_asset`                      | fbx         |
| `material.definition`  | `material_definition`             | json        |
| `bundle.pack`          | `asset_bundle`                    | —           |
| `bundle.candidate_set` | `candidate_bundle`                | —           |
| `ue.asset_manifest`    | `ue_asset_manifest`               | json        |
| `ue.import_plan`       | `ue_import_plan`                  | json        |
| `report.review`        | `review_report`                   | json        |

### D.2 PayloadRef 三态落盘规则

| kind     | 适用                       | 存储后端                   | 体积上限    |
| -------- | -------------------------- | -------------------------- | ----------- |
| `inline` | 小 JSON / 短文本 / Verdict | 嵌入 Artifact 对象         | 64 KB       |
| `file`   | 图像 / 音频 / mesh         | 本地 `artifacts/<run_id>/` | 500 MB/文件 |
| `blob`   | 跨机共享（后置）           | 对象存储                   | —           |

**MVP 阶段只实现 inline + file**；blob 接口预留。

### D.3 各 modality 专属 metadata

```python
# image
{
  "width": int, "height": int, "color_space": "sRGB|Linear",
  "style_tags": list[str], "prompt_summary": str, "seed": int | None,
  "transparent_background": bool, "intended_use": str,
  "alpha_channel": bool, "tileable": bool,
  "texture_usage_hint": "albedo|roughness|normal|...",
  "variation_group_id": str | None,
}

# audio
{
  "duration_sec": float, "sample_rate": int, "channels": int, "bit_depth": int,
  "loopable": bool, "loop_in_sec": float | None, "loop_out_sec": float | None,
  "mood_tags": list[str], "tempo_bpm": int | None, "intended_use": "bgm|sfx|...",
  "peak_db": float | None, "lufs": float | None,
}

# mesh
{
  "mesh_format": "glb|fbx|usd", "poly_count": int, "material_slots": int,
  "has_uv": bool, "has_rig": bool,
  "scale_unit": "cm|m", "up_axis": "Y|Z",
  "bounding_box": [float, float, float],
  "intended_use": "static_mesh|skeletal_mesh",
  "lod_count": int | None, "collision_hint": str | None,
}

# text.structured
{
  "schema_name": str, "schema_version": str,
  "language": "zh-CN|en-US|...", "fields_complete": bool,
}
```

### D.4 Lineage 字段

```python
class Lineage(BaseModel):
    source_artifact_ids: list[str] = []
    source_step_ids: list[str] = []
    transformation_kind: str | None = None   # e.g. "image_to_3d"
    selected_by_verdict_id: str | None = None
    variant_group_id: str | None = None      # 多版本同族标识
    variant_kind: str | None = None          # "original|compressed|lod_0|lod_1|retouched"
```

### D.5 Validation 分层

```
- 文件层: 路径可达 / 格式签名合法 / 大小合理
- 元数据层: modality 专属必填字段齐全
- 业务层: 满足当前 Step 约束（resolution / duration / poly_count）
- UE 层: 命名前缀合规 / 路径落在 asset_root 内 / 格式在 UE 支持列表
```

Artifact 入 Store 前必须通过前 3 层；UE 层校验在 `export` step 做。

---

## E. Unified UE Bridge Boundary

### E.1 Bridge 职责与非职责

| 职责（做）           | 非职责（不做）                    |
| -------------------- | --------------------------------- |
| 读取 UEAssetManifest | 决定资产应该长什么样              |
| 生成 UEImportPlan    | 自己生成资产                      |
| 执行低风险导入       | 修改已有关键资产                  |
| 返回 Evidence        | 绕过上游 Verdict 执行             |
| 写审计日志           | 改 GameMode / 默认地图 / 项目配置 |
| 记录 rollback hint   | 跨项目批量操作                    |

### E.2 双模并存（解决原架构分歧）

Bridge 支持两种执行形态，由 `UEOutputTarget.import_mode` 选择：

**模式 1：manifest_only（默认，MVP 采用）**
- 框架侧：产出 UEAssetManifest + 落文件到 `<UE项目>/Content/Generated/<run_id>/`
- UE 侧：独立 Python 脚本（非框架进程）读 manifest，逐项导入
- 边界：框架不直接调 UE API
- 优点：UE 版本解耦、进程隔离、易回滚

**模式 2：bridge_execute（后置，评估后开启）**
- 框架侧：产出 UEAssetManifest + UEImportPlan + 调用 Python Editor Scripting
- UE 侧：框架直接操作 UE 进程（需 UE 已启动）
- 边界：过 Inspect → Plan → Execute 三层 + 权限 allow_flag + Evidence
- 优点：实时感知、可自动回滚
- **MVP 不启用**

### E.3 Inspect / Plan / Execute 三层工具

```python
# Inspect（只读）
inspect_project(project_root) -> ProjectReadiness
inspect_content_path(path) -> PathStatus
inspect_asset_exists(object_path) -> bool
validate_manifest(manifest) -> ManifestReport

# Plan（生成 UEImportPlan，不执行）
build_import_plan(manifest) -> UEImportPlan
check_permission_scope(plan, permission_policy) -> PermissionReport
dry_run_import(plan) -> DryRunReport

# Execute（仅在 bridge_execute 模式启用）
create_folder(path) -> Evidence
import_texture(entry) -> Evidence
import_audio(entry) -> Evidence
import_static_mesh(entry) -> Evidence
create_material_from_template(entry) -> Evidence
create_sound_cue_from_template(entry) -> Evidence
```

### E.4 权限策略（PermissionPolicy）

```python
class PermissionPolicy(BaseModel):
    allow_create_folder: bool = True
    allow_import_texture: bool = True
    allow_import_audio: bool = True
    allow_import_static_mesh: bool = True
    allow_create_material: bool = False         # MVP 禁
    allow_create_sound_cue: bool = False        # MVP 禁
    allow_modify_existing_assets: bool = False  # 恒禁（需显式覆盖）
    allow_modify_blueprints: bool = False       # 恒禁
    allow_modify_maps: bool = False             # 恒禁
    allow_modify_project_config: bool = False   # 恒禁
    allow_delete: bool = False                  # 恒禁
```

### E.5 Bridge 阶段划分（权限维度 A/B/C/D）

| Phase          | 允许的动作                                                   | MVP 状态     |
| -------------- | ------------------------------------------------------------ | ------------ |
| A — 只读探测   | Inspect 全部                                                 | **启用**     |
| B — 低风险导入 | create_folder / import_texture / import_audio / import_static_mesh | **启用**     |
| C — 低风险关联 | create_material_from_template / create_sound_cue_from_template | 允许但默认关 |
| D — 高风险编辑 | 修改已有资产 / 蓝图 / 地图 / 配置                            | **MVP 恒禁** |

### E.6 Bridge 与 Verdict 的耦合

```
Verdict.decision == "reject"               → Bridge 不执行
Verdict.decision == "human_review_required" → Bridge 仅输出 dry-run DryRunReport
Verdict.decision in {"approve","approve_one","approve_many"} → Bridge 进入执行
其他 decision → 不触发 Bridge
```

### E.7 Rollback（MVP 最小策略）

```
- 每次 execute 前记录"此 op 会创建哪些对象"
- 失败时：停止后续 op，输出已创建对象清单（manual_cleanup_list）
- 不做自动撤销（推迟到 Phase D 之后，参考 Autonomix 思路）
```

### E.8 UE 侧 Python 脚本分层（参考 VibeUE 域服务）

```
ue_scripts/
├── domain_texture.py       # 贴图域
├── domain_mesh.py          # 网格域
├── domain_audio.py         # 音频域
├── domain_material.py      # 材质域（MVP 只读）
├── manifest_reader.py      # 读 manifest_only 模式下的清单
└── evidence_writer.py      # 写 Evidence 回 <run_id>/evidence.json
```

---

## F. MVP 第一阶段开发范围

**原则**：P0 与 P1 是刚性范围；P2 之后视 P1 产出再细化。

### F.1 P0 — 对象模型 + 运行时骨架（2 周）

| 任务                          | 产出                                                         | 验收                                                         |
| ----------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| F0-1 Pydantic schemas         | `core/*.py`：Task / Run / Workflow / Step / Artifact / Candidate / ReviewNode / ReviewReport / Verdict / 5 类 Policy / UEOutputTarget / UEAssetManifest / UEImportPlan / Evidence / Checkpoint / Rubric | schema 单测全绿                                              |
| F0-2 PayloadRef 三态实现      | `artifact_store/payload_backends/{inline,file}.py`           | 10MB 图与 200 byte JSON 各能正确存取                         |
| F0-3 Artifact Store + lineage | `artifact_store/repository.py` + `lineage.py` + `variant_tracker.py` | 写/读/查 lineage 全跑通                                      |
| F0-4 Orchestrator 骨架        | `runtime/orchestrator.py` + `scheduler.py` + `transition_engine.py` | mock 3-step 线性 workflow 能走完                             |
| F0-5 Dry-run Pass             | `runtime/dry_run_pass.py`                                    | 给定缺失 input_bindings 的 Task 能在 Dry-run 阶段失败并输出预检报告 |
| F0-6 Checkpoint store         | `runtime/checkpoint_store.py` + hash 命中逻辑                | 同输入跑两次，第二次命中缓存跳过                             |
| F0-7 OTel trace 接入          | `observability/tracing.py`                                   | Run → Step → Provider call 三层 span 可视化                  |

**验收闭环**：一个纯 mock 的 3-step 线性 workflow（generate-mock → validate → export-noop）能跑完、落 Artifact、生成 Checkpoint、被 resume 命中。

### F.2 P1 — basic_llm 模式（1.5 周）

| 任务                                          | 产出                                                      | 验收                                      |
| --------------------------------------------- | --------------------------------------------------------- | ----------------------------------------- |
| F1-1 LiteLLM 接入                             | `providers/litellm_adapter.py`（至少 OpenAI + Anthropic） | call(input) → Artifact(modality=text)     |
| F1-2 Instructor 封装为 generate step executor | `runtime/executors/generate_structured.py`                | schema 失败触发 retry；通过则落库         |
| F1-3 validate step executor                   | `runtime/executors/validate.py`                           | 用 Pydantic 校验，失败按 RetryPolicy      |
| F1-4 ProviderPolicy + capability router       | `providers/capability_router.py`                          | preferred_models 失败时切 fallback_models |
| F1-5 Secrets 管理                             | `observability/secrets.py`（env + .env 文件）             | API key 不落日志                          |

**验收闭环**：给定 UE 角色 schema（20 字段 JSON），`basic_llm` 模式稳定产出符合 schema 的 Artifact(text.structured)；schema 失败自动 retry 2 次。

### F.3 P2 — standalone_review（1.5 周）

| 任务                                 | 产出                                                         | 验收                                                  |
| ------------------------------------ | ------------------------------------------------------------ | ----------------------------------------------------- |
| F2-1 review step executor            | `runtime/executors/review.py`（支持 single_judge + chief_judge） | CandidateSet → ReviewReport + Verdict                 |
| F2-2 Rubric 模板库（借 judges）      | `review_engine/rubric_templates/*.yaml`                      | UE 领域 5 维度打分可用                                |
| F2-3 ReviewReport + Verdict 分离落库 | `review_engine/report_verdict_emitter.py`                    | 两对象独立可查，互相引用                              |
| F2-4 select step                     | `runtime/executors/select.py`                                | 根据 Verdict.selected_candidate_ids 过滤 CandidateSet |

**验收闭环**：3 个候选方案 JSON → `standalone_review` → ReviewReport（含 5 维 scoring）+ Verdict（decision=approve_one / 含 dissent）。

### F.4 P3 — production + 内嵌 review（2 周）

| 任务                               | 产出                                            | 验收                                               |
| ---------------------------------- | ----------------------------------------------- | -------------------------------------------------- |
| F3-1 ComfyUI headless worker 封装  | `providers/workers/comfy_worker.py` + HTTP 调用 | prompt + style spec → image Artifact               |
| F3-2 generate(image) step executor | `runtime/executors/generate_image.py`           | 同 generate 接口但路由到 ComfyUI worker            |
| F3-3 risk_level 调度启用           | 更新 `runtime/scheduler.py`                     | image step 标 medium，文本 low；同层按风险升序     |
| F3-4 revise 回环 + max_revise 计数 | `runtime/transition_engine.py` 扩展             | review 打回 → 回到上游 generate 并带 revision_hint |
| F3-5 Failure Mode 映射             | `runtime/failure_mode_map.py`（§C.6 表）        | provider_timeout → fallback_model 自动切           |

**验收闭环**：prompt → 结构化 image spec → ComfyUI 出图（3 候选）→ review → revise → 重生成 → 通过；完整 lineage + trace + 每步 Checkpoint。

### F.5 P4 — UE Bridge manifest_only（2 周）

| 任务                                                         | 产出                                                       | 验收                                                         |
| ------------------------------------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------ |
| F4-1 UEAssetManifest / UEImportPlan 生成                     | `ue_bridge/manifest_builder.py` + `import_plan_builder.py` | 给定 Artifact 集合产出合法 manifest + plan                   |
| F4-2 export step executor                                    | `runtime/executors/export.py`                              | 落文件到 `<UE>/Content/Generated/<run_id>/` + 写 manifest.json |
| F4-3 UE 侧 Python 脚本（texture / static_mesh / sound_wave 三域） | `ue_scripts/domain_*.py` + `manifest_reader.py`            | UE 编辑器内一次运行把资产导入                                |
| F4-4 Inspect 工具（只读）                                    | `ue_bridge/inspect/*.py`                                   | 检查 project / path / asset_exists                           |
| F4-5 Evidence writer                                         | `ue_bridge/evidence.py` + `ue_scripts/evidence_writer.py`  | 每 op 写一条 Evidence 回 `evidence.json`                     |
| F4-6 Permission policy                                       | `ue_bridge/permission_policy.py`（§E.4）                   | 非 allow 项自动 skip 并记 skipped Evidence                   |

**验收闭环**：一次空白 UE 5.x 工程：框架跑完 Run → `Content/Generated/<run_id>/` 下有 manifest + 文件 → UE 侧脚本一次执行 → Content Browser 出现资产 + evidence.json 可追溯。

### F.6 MVP 合计（含缓冲）：约 9 周

**每阶段结束交付**：
- 一条可复现命令
- 一份 Run 快照（Task + Workflow + Artifacts + ReviewReport/Verdict + 若涉及 UE 的 Evidence）
- 一次回归基线（hash 对比上一跑）

---

## G. 明确保留的后续扩展项（非 MVP）

按优先级排序。每项都不进入 MVP，但**对象模型与接口必须预留位**。

| #    | 扩展                                                  | 预留位                                                       | 何时启动                             |
| ---- | ----------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------ |
| 1    | Bridge **bridge_execute 模式**（直调 UE Python API）  | `UEOutputTarget.import_mode` 已有枚举；`ue_bridge/execute/` 目录保留空接口 | P4 稳定后评估                        |
| 2    | **多模态扩展**：AudioCraft / TRELLIS / TripoSR worker | `ArtifactType.modality` 已含 audio/mesh；`providers/workers/` 保留占位 | MVP 后第一优先                       |
| 3    | **DAG Workflow**（非线性 + 分支 + merge）             | Workflow.step_ids 已为 list；Step.depends_on 已支持多依赖    | MVP 后第二优先                       |
| 4    | **Workflow 模板继承与复用**                           | `Workflow.template_ref` 字段预留                             | 有 3+ workflow 时                    |
| 5    | **Blob 存储后端**（S3 / MinIO）                       | `PayloadRef.kind="blob"` 已支持；`payload_backends/blob.py` 空实现 | 跨机协作或大量 mesh 时               |
| 6    | **Resource Budget / GPU 调度**                        | `BudgetPolicy.gpu_seconds_cap` 已有                          | 多 Run 并发重推理时                  |
| 7    | **Run Comparison / 基线回归报告**                     | `observability/run_comparison.py` 空实现                     | P4 后第一优先                        |
| 8    | **Human-in-the-loop 标准协议**（通知/超时/恢复）      | `human_gate` Step.type 已有；`EscalationPolicy.notify_channel` 字段预留 | 有生产工单反馈时                     |
| 9    | **Schema Registry + 演化规则**                        | `Artifact.schema_version` 已有                               | schema 累计 10+ 后                   |
| 10   | **多租户/多项目隔离**                                 | `Task.project_id` + `Run.project_id` 已有；Artifact Store 按 project 分目录已做 | 接入第 2 个 UE 项目时                |
| 11   | **LangGraph 接入 evaluation**（仅评估，不一定采用）   | —                                                            | MVP 稳定后单独评估 1–2 周            |
| 12   | **CrewAI / AG2 角色化评估**（仅评估）                 | —                                                            | 仅在生产中发现多角色分工明显缺失时   |
| 13   | **Bridge 自动 rollback**（不只 hint）                 | `Evidence` 已有；`rollback/` 目录保留                        | Phase D 启动前必须有                 |
| 14   | **BlenderMCP 中转链路**（image → Blender 清理 → UE）  | —                                                            | TRELLIS/TripoSR 产出清理需求明确后   |
| 15   | **Workflow 可视化编辑器**                             | —                                                            | 仅在手写 Workflow DSL 出现维护痛点后 |

**明确放弃**（不预留、不再讨论）：
- 聊天式 agent 框架接入（AG2/CrewAI 作为"对话骨架"）
- UE 反向控制（UE 主动调度框架）
- 非 Pydantic 对象模型（放弃 dataclass/attrs 备选）
- PydanticAI 作主力（已选 Instructor）

---

## H. 开源项目最终决策表

| 项目                                                         | 决策                                | 理由                                                  |
| ------------------------------------------------------------ | ----------------------------------- | ----------------------------------------------------- |
| **LiteLLM**                                                  | **直接用**（P1 接入）               | 无业务语义，纯基础设施                                |
| **Instructor**                                               | **直接用**（P1 接入）               | Pydantic 绑定 + retry，作 generate(structured) 执行器 |
| **judges**                                                   | **借鉴 rubric 模板**（P2 参考）     | 不接运行时；rubric YAML 抄思路                        |
| **LangGraph**                                                | **仅参考 StateGraph 语义**          | 不直接接入；避免 LangChain 生态锁定                   |
| **ComfyUI**                                                  | **外部 headless worker**（P3 接入） | HTTP API 挂载；不作主编排                             |
| **AudioCraft**                                               | **外部 worker**（MVP 后）           | 独立子进程，资源治理隔离                              |
| **TRELLIS / TripoSR**                                        | **外部 worker**（MVP 后）           | 双栈互为 fallback                                     |
| **Autonomix**                                                | **仅审计/撤销思路参考**             | UE 内插件，方向相反                                   |
| **VibeUE**                                                   | **仅域服务分层思路参考**（P4 参考） | 不接入其运行时                                        |
| **BlenderMCP**                                               | **仅思路参考**（后置）              | 中转链路设计参考                                      |
| **UE5-MCP**                                                  | **仅思路参考**                      | 工程化不足                                            |
| **PydanticAI / AG2 / CrewAI / Diffusers / llm-council / Microsoft Agent Framework** | **放弃**                            | 与主线不契合或重复                                    |

---

## I. 必须自研、不可复用的能力（落到代码层）

1. **对象模型层**（§B 全部）— 没有任何开源项目精确匹配
2. **PayloadRef 三态 + 两段式 type**（§D.1–D.2）— 无对标
3. **Step.risk_level + 调度器**（§C.4）— 无对标
4. **Dry-run Pass**（§C.3）— 无对标
5. **Checkpoint + content hash 缓存**（§F0-6）— LangGraph Checkpointer 存储格式不匹配
6. **ReviewReport / Verdict 分离 + 5 维 scoring**（§B.8）— judges 只给裁决不给结构
7. **UEOutputTarget 前置 + UEAssetManifest + UEImportPlan + Evidence**（§B.11, E）— UE 领域独有
8. **Failure Mode 映射**（§C.6）— 无对标
9. **Verdict → TransitionPolicy 转换引擎**（§C.5）— 无对标
10. **多租户隔离 + Determinism 策略**（§G.10, B.12）— 无对标

---

## J. 关键参考文件（实现期查阅）

- `docs/assistant_plan_bundle/01_*.md` — 对象模型字段明细（对齐 §B）
- `docs/assistant_plan_bundle/02_*.md` — review 嵌入位置与 4 类场景（对齐 §C.5）
- `docs/assistant_plan_bundle/03_*.md` — modality metadata 清单（对齐 §D.3）
- `docs/assistant_plan_bundle/04_*.md` — Bridge 三层工具 + 权限策略（对齐 §E）
- `docs/assistant_plan_bundle/05_*.md` — 开源项目清单（对齐 §H）
- `docs/assistant_plan_bundle/06_*.md` — 运行时组件建议 + 目录结构（对齐 F0）

## K. 验证路径（端到端）

| 里程碑 | 验证命令                                                     | 通过标准                                                |
| ------ | ------------------------------------------------------------ | ------------------------------------------------------- |
| P0     | `python -m framework.run --task examples/mock_linear.json`   | 3 个 Checkpoint 落库、resume 命中                       |
| P1     | `python -m framework.run --task examples/character_extract.json` | schema 合法 JSON，retry 次数 ≤ 2                        |
| P2     | `python -m framework.run --task examples/review_3_images.json` | ReviewReport + Verdict 落库，scores_by_dimension 齐     |
| P3     | `python -m framework.run --task examples/image_pipeline.json` | 从 prompt 到通过 review 的完整 trace，max_revise 内收敛 |
| P4     | UE 空白工程内：先跑框架，再在 UE Python Console 执行 `exec(open(ue_scripts/run_import.py).read())` | Content Browser 出现导入资产 + evidence.json 完整       |

---

## L. 一句话定位

**vNext 是一套以 Task/Run/Workflow/Artifact 为一等公民、Review 为合法节点、UEOutputTarget 前置、双模 UE Bridge、5 类 Policy 分离、Dry-run + Checkpoint 保障可复现的多模型运行时；基础层（LiteLLM / Instructor）直接用，StateGraph 与 rubric 仅借语义，多模态生成工具（ComfyUI/AudioCraft/TRELLIS/TripoSR）外挂为 worker，UE 领域与运行时工程化部分全自研。**