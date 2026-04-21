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
| `ModelRegistry`                                              | 三段式(providers / models / aliases)模型注册,`config/models.yaml` 为单一真源 | 实装(D-plan)           | —                                       |
| `PreparedRoute`                                              | `(model_id, api_key_env, api_base, kind)` 四元组,ModelRegistry 产出;同一别名可混合多家 provider | 实装(D-plan)           | ProviderPolicy 直写 api_key/base        |
| `capability_alias`                                           | 能力语义命名(`text_cheap` / `image_fast` / `mesh_from_image` 等),bundle 里通过 `models_ref` 引用 | 实装                    | —                                       |
| `BudgetTracker`                                              | Run 级成本累加器,超 `BudgetPolicy.total_cost_cap_usd` 合成 `budget_exceeded` Verdict | 实装(F1)               | —                                       |
| `CompactionReport`                                           | `compact_messages()` 结果对象,记录原始/最终 token 数与丢弃条数 | 实装(F4)               | —                                       |

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
    # Legacy 单别名级 auth(手写 bundle 走这里)
    api_key_env: str | None = None
    api_base: str | None = None
    # D-plan 每路由级 auth。workflows loader 在 bundle 使用
    # `models_ref: "<alias>"` 时由 ModelRegistry 展开填充,每条路由
    # 自带 api_key_env + api_base,使一个别名可混合多家 provider。
    prepared_routes: list[PreparedRoute] = []

class PreparedRoute(BaseModel):
    model: str                       # LiteLLM model id
    api_key_env: str | None = None
    api_base: str | None = None
    kind: str = "text"               # text / image / image_edit / mesh / vision / audio

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
- `budget.cap_declared` —— production / ue_export 任务若含付费步 (`capability_ref` 起自 `text./image./mesh./review.`) 却未声明 `total_cost_cap_usd`,写入 `report.warnings`（不阻断,F1 新增）
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
| worker_timeout         | Comfy/Mesh worker 长任务超时        | retry_same_step                  | worker 自身 `default_timeout_s` |
| worker_error           | Worker 异常（3D/ComfyUI 非 4xx 错误）| fallback_model                   | ProviderPolicy.fallback_models |
| disk_full              | Artifact Store 写失败               | rollback → stop                  | —                             |

每个 FailureMode 绑定一组 Exception 类族,详见 `framework/runtime/failure_mode_map.py`。`budget_exceeded` 由 `BudgetTracker.check()` 触发(每步后检查),无需 Executor 主动抛。

### C.7 运行时可靠性工具集（F1–F4，实装）

四项附加能力,独立于主 Workflow 语义,可按 step / Run 粒度 opt-in。

| ID   | 能力                    | 位置                                                      | 触发/接入方式                                                |
| ---- | ----------------------- | --------------------------------------------------------- | ------------------------------------------------------------ |
| F1   | Budget 累计 + 软终止    | `framework/runtime/budget_tracker.py`                     | Task 声明 `BudgetPolicy.total_cost_cap_usd`。Orchestrator 每步后从 `exec_result.metrics[cost_usd\|usage\|model]` 累计;超 cap 合成 `budget_exceeded` Verdict 走 TransitionEngine,run 以 `termination_reason="budget_exceeded(cap=…,spent=…)"` 终止。结果写入 `RunResult.budget_summary`。 |
| F2   | 分块下载 + Range 续传 + 轮询进度 | `framework/providers/_download.py` `chunked_download()` ; `framework/providers/_download_async.py` `chunked_download_async()` ; `hunyuan_tokenhub_adapter.TokenhubMixin._th_poll` | 1 MB 分块,中断走 HTTP Range 续传(最多 3 次重试)。**续传分支强校验**:`buf` 非空时响应必须是 `206` 且 `Content-Range` 起始偏移 = `len(buf)`;任何其他形态(CDN/代理忽略 Range 回 200 全量、206 但 offset 错)都清空 buf 从头重下,避免坏图/坏 GLB 静默落盘。下载进度回调 `(downloaded, total_or_none)`。轮询进度回调自适应 `(status, elapsed_s)` 或 `(status, elapsed_s, raw_resp)`,消费端可从 raw_resp 自行挖 `progress`/`percent` 字段。消费路径:Qwen / Hunyuan Image / Hunyuan3D / Tripo3D。 |
| F3   | Anthropic Prompt Cache  | `framework/providers/litellm_adapter.py` `_maybe_apply_prompt_cache()` | `ProviderCall.extra["_forge_prompt_cache"]=True` 且模型 Anthropic 家族 → 给首条 system + 首条大 user block 注入 `cache_control: {"type": "ephemeral"}`。已默认在 `LLMJudge.judge()` 打开(rubric 前缀稳定)。 |
| F4   | 消息自动压缩            | `framework/observability/compactor.py` `compact_messages()` | `ProviderCall.extra["_forge_auto_compact_tokens"]=N` 触发。保留首条 system + 末 `keep_tail_turns` 轮,从中段剔除最旧消息直到 ≤ N token,插入 `[auto-compact: N earlier message(s) omitted]` 占位符。默认 4 字符/token 估算,可注入真实 tokenizer。 |

**瞬态重试(Plan X,F2 同族)**:`framework/providers/_retry.py` + `_retry_async.py` 提供 `with_transient_retry()` / `with_transient_retry_async()` + `is_transient_network_message()`,所有自研 adapter (Qwen / Hunyuan tokenhub / HunyuanMeshWorker) 的 POST 路径默认一次瞬态重试(SSL EOF / 超时 / 5xx → 2s 回退)。LiteLLM 路径沿用自身重试策略。

### C.8 异步执行模型(Plan C,实装)

**动机**:ChiefJudge 面板串行、多候选 for 循环、`time.sleep` 轮询完全阻塞事件循环 → 三类可并行场景被浪费;而且 CLI 无法取消长任务。

**设计**:async-first + sync-shim 双层。`ProviderAdapter` / `CapabilityRouter` 主接口是 `acompletion / astructured / aimage_generation / aimage_edit`,同名 sync 方法自动 `asyncio.run` 桥接,旧代码零改动。

**关键边界**:
- **底层 HTTP**:`httpx.AsyncClient`(替换 urllib)+ `chunked_download_async()` 带 Range 续传
- **轮询**:所有 `_th_poll` / `_tokenhub_poll` 的 `time.sleep(interval)` 换成 `await asyncio.sleep(interval)`,`CancelledError` 传播立即中断
- **Instructor**:走 `instructor.from_litellm(litellm.acompletion)` 异步客户端
- **多候选并行**:Step 配置 `parallel_candidates=True` 时 `asyncio.gather` 并发 `n=1` 调用
- **ChiefJudge 面板**:`ajudge_with_panel` 用 `asyncio.gather` 同时跑所有 judge,总延迟 ≈ 最慢 judge

**取消/超时中断(§D7)**:
- poll 循环里每个 `await asyncio.sleep` 后不得吞 `CancelledError`;已由 adapter 保证
- `asyncio.wait_for(adapter.acompletion(call), timeout=T)` 可外层硬超时
- DAG 失败时级联取消用 `asyncio.wait(FIRST_EXCEPTION)` → 取消 siblings
- **限制**:同步 Executor 内的 `time.sleep` 无法中断(Python 线程无法强制终止);仅限 async 原生路径获得即时取消

### C.9 DAG 并发调度(Plan C,实装;§G #3 提前落地)

**机制**:`Orchestrator.arun` 用 `asyncio.wait(FIRST_EXCEPTION)` 在 `depends_on` 入度为 0 的多个 step 间并发调度。Opt-in via `task.constraints["parallel_dag"]=True`(默认保持线性,严格向后兼容 P0–P4 测试)。

**示例**:root → {leaf_a, leaf_b, leaf_c} 的 fan-out,若每个 leaf 耗时 0.2s,总墙钟从 0.6s(串行)降到 ~0.2s(并行)。

**级联语义**:若任一 step raise 未分类异常,orchestrator 立刻 cancel 其他 siblings 并 re-raise。 线性 workflow 的 revise 回环、checkpoint 缓存、BudgetTracker 软终止逻辑不变。

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

### F.6 L 层能力扩展（P4 之后,按需启用,实装中）

在 P0–P4 骨架之上追加四个横切能力,每层都走已有 `capability_alias` + `ProviderPolicy` + `Step` 路径,不改 §B 对象模型。

| ID   | 能力                 | 新增 Executor / Worker                                    | 关键 Artifact / Schema            | capability alias        |
| ---- | -------------------- | --------------------------------------------------------- | --------------------------------- | ----------------------- |
| L1   | UE5 API 查询         | 复用 `generate_structured`                                | `ue.api_answer`                   | `ue5_api_assist`        |
| L2   | 图像生成 API 路径    | `runtime/executors/generate_image.py`(非 ComfyUI 的 API 直出) | `image.raster`                    | `image_fast` / `image_strong` / `image_edit` |
| L3   | 视觉 QA              | 复用 `review.judge` + 视觉 LLM 别名                       | `report.review`（输入含 image）   | `review_judge_visual`   |
| L4   | image → 3D mesh      | `runtime/executors/generate_mesh.py` + `providers/workers/mesh_worker.py`(Tripo3D HTTP + Hunyuan3D tokenhub) | `mesh.gltf` / `mesh.fbx` / `mesh.obj`,spec 见 `framework/schemas/mesh_spec.py` | `mesh_from_image`       |

L4 为 P4 manifest_builder 增加了 `("mesh","obj"): "static_mesh"` 映射与按扩展名选择 domain_mesh 工厂。

### F.7 MVP 合计（含缓冲）：约 9 周

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

### H.1 实装 Provider 清单（通过 ModelRegistry / 自研 Adapter 接入）

文档 §H 之外,实装通过 `config/models.yaml` 接入了下列 provider。接入路径分两类:
- **OpenAI 兼容端口(经 LiteLLM)**:只需在 registry 里填 `api_base` + `api_key_env`,bundle 写 `openai/<id>`;零新代码
- **自研 adapter**:协议不兼容 OpenAI,在 `framework/providers/` 加 adapter,`CapabilityRouter` 按 `model.startswith(...)` 前缀匹配

| Provider                     | 主用途                    | 接入路径                          | 代码                                         |
| ---------------------------- | ------------------------- | --------------------------------- | -------------------------------------------- |
| PackyCode                    | Claude 系聚合(opus/sonnet/haiku) | OpenAI 兼容(LiteLLM)            | —                                            |
| MiniMax(Anthropic 兼容)    | 便宜强 LLM                | Anthropic 兼容(LiteLLM)         | —                                            |
| 智谱 GLM                     | 文本 / 视觉 / 图像        | OpenAI 兼容(LiteLLM)            | —                                            |
| 阿里 Qwen (DashScope 多模态) | 图像 / 视觉 / 图像编辑    | 自研                              | `providers/qwen_multimodal_adapter.py`        |
| 腾讯 Hunyuan (OpenAI compat) | 文本                      | OpenAI 兼容(LiteLLM)            | —                                            |
| 腾讯 Hunyuan Image (tokenhub)| 图像 / 图像编辑           | 自研(异步 submit+poll+download) | `providers/hunyuan_tokenhub_adapter.py`       |
| 腾讯 Hunyuan 3D (tokenhub)   | image → 3D                | 自研 Worker                       | `providers/workers/mesh_worker.py` HunyuanMeshWorker |
| Tripo3D                      | image → 3D (备选)         | 自研 Worker(requests)           | `providers/workers/mesh_worker.py` Tripo3DWorker |

路由优先级:`CapabilityRouter` 注册顺序为"专用 adapter 先、LiteLLM wildcard 后",保证 Qwen/Hunyuan 前缀不会被 LiteLLM 捕获。

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

---

## M. 实装状态快照（2026-04-22）

与 §F / §H 计划的交叉对账。所有勾选项均有测试覆盖(491 单测/集成测试全绿)。

### 主线进度

| 阶段 | 范围                         | 状态 | 备注                                                         |
| ---- | ---------------------------- | ---- | ------------------------------------------------------------ |
| P0   | 对象模型 + 运行时骨架        | ✅    | F0-1 ~ F0-7 全部                                             |
| P1   | basic_llm + LiteLLM + Instructor | ✅    | `litellm.drop_params=True` 绕过 Anthropic 不认识 `seed`      |
| P2   | standalone_review            | ✅    | F2-1 ~ F2-4 全部                                             |
| P3   | production + 内嵌 review     | ✅    | revise 回环 + Checkpoint 缓存的 Verdict 回放已对齐           |
| P4   | UE Bridge manifest_only      | ✅    | F4-1 ~ F4-6 全部                                             |

### L 层能力(§F.6)

| ID   | 能力            | 状态 |
| ---- | --------------- | ---- |
| L1   | UE5 API 查询    | ✅    |
| L2   | 图像生成 API 路径 | ✅    |
| L3   | 视觉 QA         | ✅    |
| L4   | image → 3D mesh | ✅    |

### F 附加能力(§C.7)

| ID   | 能力                              | 状态 |
| ---- | --------------------------------- | ---- |
| F1   | BudgetTracker + Dry-run budget warn | ✅    |
| F2   | Chunked download + 轮询进度 + raw_resp 透传 | ✅    |
| F3   | Anthropic Prompt Cache            | ✅    |
| F4   | `compact_messages()` helper       | ✅    |
| F5   | 取消 / 超时中断(`asyncio.CancelledError`) | ✅    |
| Plan X | 瞬态重试                        | ✅    |

### Plan C:Provider 全异步 + DAG + EventBus(实装)

| 能力                           | 状态 | 关键位置 |
| ------------------------------ | ---- | -------- |
| `ProviderAdapter` 四方法 async + sync shim | ✅    | `providers/base.py` |
| LiteLLM `acompletion` / `aimage_generation` | ✅    | `providers/litellm_adapter.py` |
| Qwen / Hunyuan tokenhub `httpx.AsyncClient` | ✅    | `providers/qwen_multimodal_adapter.py` / `hunyuan_tokenhub_adapter.py`。Hunyuan `aimage_generation(n>1)` 用 `asyncio.gather(*[_one(i) for i in range(n)])` 真正并发 N 条 submit/poll/download;tokenhub 每次 submit 只接一条 prompt,不能靠 `n` 参数伪造。 |
| HunyuanMeshWorker.agenerate + `asyncio.gather` 候选 | ✅    | `providers/workers/mesh_worker.py` |
| CapabilityRouter 4 方法 async | ✅    | `providers/capability_router.py` |
| ChiefJudge panel `asyncio.gather` | ✅    | `review_engine/chief_judge.py` |
| `Orchestrator.arun` + DAG 并发(opt-in) | ✅    | `runtime/orchestrator.py` |
| EventBus + ProgressEvent schema (loop-aware) | ✅    | `observability/event_bus.py`。`Subscription` 捕获自身 event loop;`publish_nowait` 检测跨线程后 `loop.call_soon_threadsafe` hop 到 queue 的 owning loop;`_subs` 用 `threading.Lock` 保护。asyncio.Queue 不是线程安全容器,这步避免"GIL 下直接 put_nowait"的潜伏错觉。 |
| WebSocket 进度推送 server (idle-safe) | ✅    | `server/ws_server.py`。`ws_run` / `ws_step` 用 `asyncio.wait(FIRST_COMPLETED)` 同时等事件和 `receive_disconnect`;空闲期客户端关连不会留下泄露的 `Subscription`。 |
| `framework.run --serve` CLI | ✅    | `run.py` |

### 已接入的真实 Provider

MiniMax(M2.x)、PackyCode(Claude Opus/Sonnet/Haiku 4.x)、GLM 4.6v/Image、Qwen Image 2 / 2 Pro / Edit Plus / Edit Max、Hunyuan Image v3 / Style、Hunyuan 3D、Tripo3D(预留)。别名定义参见 `config/models.yaml`,实际跑通的别名:`text_cheap / text_strong / review_judge / review_judge_visual / ue5_api_assist / image_fast / image_strong / image_edit / mesh_from_image`。

### 近期加固(两轮 Codex review + 一轮 adversarial review)

Plan C 完工后经过两轮独立代码审查 + 一轮 adversarial review,共落 9 条修复,281 → 287 测试。按严重级别排列:

| 条目 | 症状 → 修复 | 关键位置 |
|---|---|---|
| DAG `retry_same_step` 被吞 | `asyncio.wait` 分支的 `if next_id == current: break` 把 `Decision.retry_same_step` 当终止信号了,`provider_timeout` / `schema_validation_fail` / `worker_timeout` 三条失败模式的 DAG-mode 重试全部失效。改成 `done.discard(current)` 允许同 step 重新进入循环。 | `runtime/orchestrator.py` |
| review 步 `cost_usd` 缺失 | `ReviewExecutor` 不透传 judge 用量,BudgetTracker 对 review 路径"看不见"成本,设了 `total_cost_cap_usd` 的 Run 可以无上限烧 judge。新增 `ProviderAdapter.astructured_with_usage` 返回 `(obj, usage)` 2-tuple,经 `CapabilityRouter.structured` 扩成 `(obj, model, usage)` 3-tuple,`ReviewExecutor` 聚合每 judge usage 写 `metrics["cost_usd"]`。 | `providers/base.py` / `review_engine/judge.py` / `runtime/executors/review.py` |
| Hunyuan 3D submit 字段名错 | submit body 用了 `image_url`,tokenhub 实际期望 `image` 且内容必须是 `data:image/png;base64,...` data URL(与 `HunyuanImageAdapter` 一致)。 | `providers/workers/mesh_worker.py` |
| `workflow.metadata["parallel_dag"]` 死代码 | 文档宣称 task.constraints 和 workflow.metadata 都能开 DAG,但 `Workflow` Pydantic 模型根本没 `metadata` 字段。补 `metadata: dict = Field(default_factory=dict)`。 | `core/task.py` |
| WS idle disconnect 订阅泄露 | 旧 `ws_run`/`ws_step` 只在 `send_json` 失败时才察觉断连,空闲期客户端关连 `Subscription` 留在 bus 里污染 `subscriber_count`。改为 `asyncio.wait(FIRST_COMPLETED)` 同时 race 事件与 `receive_disconnect`。 | `server/ws_server.py` |
| **续传 Range 强校验**(adv #1) | `chunked_download` / `chunked_download_async` 续传分支只加 `Range` 头就无脑 `buf.extend(chunk)`,没校验响应是 `206` 还是 `200`,也没对齐 `Content-Range` 起始偏移。CDN/代理忽略 Range 回 200 全量时就会把完整 body 拼在残缺前缀上,生成坏图/坏 GLB 静默落盘(`ValidationRecord` 只检查 bytes_nonempty,数据完整性失守)。现改为 `buf` 非空时必须 `206` + `Content-Range` 起始偏移 = `len(buf)`,其他形态一律清空重下。 | `providers/_download_async.py` / `providers/_download.py` |
| **EventBus loop-aware**(adv #2) | `publish_nowait` 直接对 `asyncio.Queue.put_nowait`,但 asyncio.Queue 不是线程安全容器,`_subs` 列表也无锁。ambient `publish()` 的接口语义鼓励从 `asyncio.to_thread` 的 sync executor 发事件,只要有人这么调就会踩坑。改为 `Subscription` 创建时捕获 owning loop,`_dispatch` 检测跨线程后 `loop.call_soon_threadsafe(put_nowait, ...)` hop 到 queue 的 owning loop;`_subs` 用 `threading.Lock` 保护增删读。 | `observability/event_bus.py` |
| **Hunyuan `aimage_generation(n>1)` fan-out**(adv #3) | tokenhub `/submit` 单次只接一条 prompt,旧实现收到 `n=3` 只做一次 submit/poll/download,把 `n` 塞进 `raw["n_requested"]` 就返回 1 张图。`GenerateImageExecutor` 默认 `num_candidates=3`,未开 `parallel_candidates=True` 时路由到 Hunyuan 会静默降级成 1 候选,下游 selection/review 在错误规模的集合上跑。改为 `asyncio.gather(*[_one(i) for i in range(n)])` 真正并发 N 条独立链,与 `HunyuanMeshWorker.agenerate` 对齐。 | `providers/hunyuan_tokenhub_adapter.py` |

### 近期加固(2026-04 Codex 多轮 review,mesh worker + 探针 + 失败路由)

Plan C 之后围绕 Hunyuan 3D mesh worker / 失败路由 / 运行期探针,又跑了 6 轮 Codex review;每条 claim 独立对照代码核对后才落修,每个修复都配独立 fence 测试。共 14 条修复,287 → 388 测试。按主题排列:

| 主题 | 症状 → 修复 | 关键位置 |
|---|---|---|
| glTF external-buffer 落盘 | `geometry_only` 模式对非自包含 `.gltf` 一律降级为 `missing_materials=True`,但 `buffers[].uri` 外挂意味着 `.bin` 承载顶点/索引,落盘的 `.gltf` 就是空几何。拆出 `_gltf_has_external_geometry`,外部 buffer 一律 raise,仅纯 image 外挂才走 geometry_only 放行。 | `providers/workers/mesh_worker.py` |
| URL 候选 fallthrough | 原 `_extract_hunyuan_3d_url` 只给 `_one()` 一个最佳 URL,.obj(mtllib)+.gltf(self-contained) 混合响应会在 .obj 上 raise 退出,不回头试 .gltf。拆出 `_rank_hunyuan_3d_urls` 返回 ranked list,`_one()` 遍历并 catch `MeshWorkerUnsupportedResponse` fallthrough。 | 同上 |
| 多 URL 回退吃 budget | fallthrough 每次用硬编码 `timeout_s=90`,`worker_timeout_s=60` 步骤能被 3×90s 阻塞。改为 per-iter `remaining = budget - elapsed`、clamp 到 `min(90, remaining)`,耗尽即 `MeshWorkerTimeout`。 | 同上 |
| 下载错误 fallthrough | 回退循环只 catch `MeshWorkerUnsupportedResponse`,CDN 404/5xx/timeout 的 `MeshWorkerError` 直接中止步骤。catch 范围扩到 `MeshWorkerError`,所有 URL 耗尽后:有 download 错误优先 raise(→ fallback_model 重试),否则 raise 最后一个 unsupported(→ abort_or_fallback)。 | 同上 |
| 空 ranked URL 误分类 | `/3d/query` 返回全 `.usd`/`preview_*` 被 ranker 过滤为空时抛通用 `MeshWorkerError`,归类 `worker_error` 会重复提交重计费。改抛 `MeshWorkerUnsupportedResponse`。 | 同上 |
| 无后缀 URL 排 ZIP 后 | 桶序 `(..., zip_hits, other_hits)` 让签名 CDN 的无后缀 URL(其中可能含真实 mesh)晚于已知必失败的 `.zip`,小 budget 下真正可用 URL 从未被尝试。桶序改为 `(strong, ok, key, other, zip)`。 | 同上 |
| `.fbx` 无校验却优先 | `_build_candidate` 对 OBJ/glTF 做 sidecar 校验,但 FBX 无校验。原 `_MESH_EXTS_OK = (".fbx", ".obj", ".gltf")` 让不可验证的 `.fbx` 优先,坏 FBX + 好 gltf 混合响应会 ship FBX 丢材质。改为 `(".gltf", ".obj", ".fbx")`,已验证格式排前。 | 同上 |
| ASCII FBX 误标 GLB | `_detect_mesh_format` 只识别二进制 FBX(`Kaydara FBX Binary`),ASCII FBX(`; FBX` 注释头 + `FBXHeaderExtension:` 顶层节点)漏检落入 GLB 默认。加 ASCII FBX 识别分支。 | 同上 |
| 损坏 glTF 被当自包含 | `_is_self_contained_gltf` JSON 解析失败时 `return True`,但 `_detect_mesh_format` 2KB 松检测会把截断/损坏 glTF 也标成 gltf,corrupt 字节随 `missing_materials=True` 落盘。parse-fail 改为 `return False`,同步 `_gltf_has_external_geometry` parse-fail `return True`,双保险保证即使 geometry_only 也 raise。 | 同上 |
| `data:` scheme 大小写 | `uri.lstrip().startswith("data:")` 大小写敏感,但 RFC 2397 规定 scheme 大小写不敏感,`DATA:`/`Data:` 合法内联被误判为外部 sidecar。抽出 `_is_data_uri()` 统一 `lower()` 前缀匹配。 | 同上 |
| unsupported 绕过 on_fallback | `MeshWorkerUnsupportedResponse` → `Decision.reject` 只看 `on_reject`,已配 `on_fallback` 的工作流无法走恢复分支。新增 `Decision.abort_or_fallback`:target=`on_fallback`,未配则终止(不像 `fallback_model` 回到同 step 重计费)。 | `core/enums.py` / `runtime/transition_engine.py` / `runtime/failure_mode_map.py` |
| 探针 runtime 检测一致 | `probe_hunyuan_3d_format._magic` 不识别文本 glTF / 多种 OBJ 起头(`o `/`g `/`vn` 等)。改委托 runtime `_detect_mesh_format`,并在 `fmt == "glb"` 分支加魔数二次校验(`data[:4] == b"glTF"`),避免 legacy fallback 把 HTML 错误页误报为 GLB。 | `probe_hunyuan_3d_format.py` |
| GLM 探针 import 副作用 | `probe_glm_image_debug` / `probe_glm_watermark_param` / `probe_glm_watermark_via_framework` 三个新探针在 module level 直接 `hydrate_env()` / `mkdir()` / `os.environ[...]`,只读 CI 或无 key 环境 import 即崩,阻塞 `inspect.getsource` 静态 fence。全部改 lazy-init。 | 三个 probe 文件 |

### 近期加固(2026-04 共性平移,把 mesh 已修原则搬到其他 adapter)

上一轮 14 条修复集中在 `mesh_worker` + 失败路由 + 探针。复盘时按"每条修复背后的设计原则"反查代码库,找出 7 条共性问题仍活在 Comfy / Tripo3D / Hunyuan image / Qwen multimodal / LiteLLM URL 下载 / 两个老 probe 上。分 3 个 PR 系统平移,388 → 424 测试。

**PR-1:所有 adapter 统一 `UnsupportedResponse` 分类**

`MeshWorkerUnsupportedResponse` 之前只在 mesh 路径上存在,其它 adapter 的"确定性空/坏响应"都 raise 通用 `ProviderError` / `WorkerError`,被 `failure_mode_map.classify()` 归类为 `provider_error` / `worker_error` → `fallback_model` → 同步重试 + 重计费。Hunyuan / Qwen / Tripo3D / DashScope 都是按次计费,重试 2-3 次就是白烧配额。

| 主题 | 症状 → 修复 | 关键位置 |
|---|---|---|
| `ProviderUnsupportedResponse` 基类 | 新增 `ProviderError` 子类,语义对齐 `MeshWorkerUnsupportedResponse`;`WorkerUnsupportedResponse` 作为 `WorkerError` 子类同理。`failure_mode_map.classify()` 在通用 Error 分支**之前**捕捉三个 unsupported 子类,映射到 `FailureMode.unsupported_response` → `Decision.abort_or_fallback`(honour `on_fallback`,未配则终止,绝不回 same step)。 | `providers/base.py` / `providers/workers/comfy_worker.py` / `runtime/failure_mode_map.py` |
| ComfyUI 三处 deterministic bad shape | spec 缺 `workflow_graph`、`/prompt` 无 `prompt_id`、`/history` outputs 无图片三条都改 raise `WorkerUnsupportedResponse`。三条都是"retry same step 不会变好"类。 | `providers/workers/comfy_worker.py` |
| Tripo3D 两处 deterministic bad shape | `/task` 无 `task_id`、轮询 success 但 output 无 URL 都改 raise `MeshWorkerUnsupportedResponse`。与 mesh 侧 Hunyuan 空 URL 列表是 1:1 镜像。 | `providers/workers/mesh_worker.py` |
| Hunyuan image `submit` 无 id | tokenhub `/submit` 返回无 id 改 raise `ProviderUnsupportedResponse`,不再走 fallback_model 重提重计费。 | `providers/hunyuan_tokenhub_adapter.py` |
| DashScope 空 choices / 无 image content | Qwen multimodal 两处 raise 改 `ProviderUnsupportedResponse`。 | `providers/qwen_multimodal_adapter.py` |
| LiteLLM image_generation 无 data | `_acollect_image_results` "returned no data" + "item has neither b64_json nor url" 两处同步 raise `ProviderUnsupportedResponse`。 | `providers/litellm_adapter.py` |

**PR-2:所有 HTTP 下载吃 remaining budget**

§M 上一轮只修了 Hunyuan mesh `_one()` 的 fallthrough 循环。同样设计缺陷(硬编码 timeout 不看 budget)在 ComfyWorker 下载 N 张图、Tripo3D 轮询 + 下载、LiteLLM URL 下载上都没改。9 张图 × 30s 能在 `timeout_s=60` 的步骤上阻塞 270s,defeat orchestrator timeout policy。

| 主题 | 症状 → 修复 | 关键位置 |
|---|---|---|
| ComfyUI `_collect_outputs` 硬编码 30s | N 个 `/view` 图片下载每张 `timeout=30.0`,不剪 budget。改为 signature 接 `budget_s` + `start_monotonic`,per-image `min(30, remaining)` clamp,耗尽即 `WorkerTimeout`。 | `providers/workers/comfy_worker.py` |
| Tripo3D 轮询 20s / 下载 60s 硬编码 | 轮询每次 `timeout=20.0`,下载 `timeout=60.0`,都不看 budget。改为 per-iter `remaining = budget - elapsed`,poll clamp 到 `min(20, remaining)`,下载 clamp 到 `min(60, remaining)`,耗尽即 `MeshWorkerTimeout("... before model download")`。 | `providers/workers/mesh_worker.py` |
| LiteLLM `_afetch_url_bytes` 硬编码 60s | 图生返回 URL 列表时,每个 URL 的 httpx `timeout=60.0` 固定。改为 `_acollect_image_results(budget_s=...)` 接可选 budget,per-URL clamp 到 `min(60, remaining)`。`aimage_generation`/`aimage_edit` 默认把 `timeout_s or _default_timeout_s` 传下去。 | `providers/litellm_adapter.py` |

**PR-3:清洁度平移(魔数 gate / image URL ranker / scheme 大小写 / 老 probe lazy)**

| 主题 | 症状 → 修复 | 关键位置 |
|---|---|---|
| runtime `_build_candidate` 未做魔数二次校验 | 上一轮 probe 对 `fmt == "glb"` 加了 `data[:4] == b"glTF"` gate,runtime 侧没同步。HTML 错误页 / 截断 payload 经 detector 的 legacy fallback 被标为 `"glb"` 落盘,UE 导入失败。`_build_candidate` 加同一 gate,非魔数字节 raise `MeshWorkerUnsupportedResponse`。 | `providers/workers/mesh_worker.py` |
| Hunyuan image 单 URL 无 fallthrough | `TokenhubMixin._extract_result_url` 只返回 `ranked[0]`,DONE 响应里有两个 URL 时第一个 404 就整个 job 失败。新增 `_extract_result_urls_ranked()` 返回 list,`HunyuanImageAdapter._one()` 遍历试到一个 download 成功为止,空列表 raise `ProviderUnsupportedResponse`。对齐 mesh 侧 `_rank_hunyuan_3d_urls` 的结构。 | `providers/hunyuan_tokenhub_adapter.py` |
| `startswith("http")` scheme 大小写敏感 | mesh URL walker + tokenhub URL walker 都用 `startswith("http")` 直接匹配,`HTTPS://`/`Https://` 被误判为非 URL(RFC 3986 规定 scheme 大小写不敏感)。两处各抽 `_is_http_url()` 谓词,lower-case 前缀匹配;加跨文件的参数化 fence 保证两个拷贝同步演进。 | 同上 + `providers/workers/mesh_worker.py` |
| `probe_aliases` / `probe_framework` module-level I/O | 两个老 probe 在 module 顶层 `hydrate_env()` / `reset_model_registry()`,与 GLM probe 同形。全部移到 `main()` 内部,对齐 `probe_hunyuan_3d_format.py` 的 lazy-init 模式。 | `probe_aliases.py` / `probe_framework.py` |

**未平移项**

- `ue_character._accept_json_string` parse-fail 原样返回字符串 —— 下游 pydantic `Stats` 是强类型 int 字段,实际 fail-closed。改 fail-fast 会破 MiniMax-M2.x 的 stringified-object 场景,目前 388 + 36 全绿证明现状可接受,不动。

### 近期加固(2026-04 pricing wiring,yaml 定价接入 BudgetTracker)

上一轮共性平移完工后,BudgetTracker 对国内 provider 和 mesh 路径的成本估算仍然失真 —— `litellm.completion_cost()` 查不到 Hunyuan / Qwen / GLM / Tripo3D 的 token 价,退回 `fallback_cost_per_1k` 粗估;`GenerateMeshExecutor` 更是干脆把 `cost_usd=0.0` 硬编码,`total_cost_cap_usd` 对 Hunyuan 3D / Tripo3D 完全失效。端到端把 `config/models.yaml` 的定价字段接进 BudgetTracker,424 → 454 测试。

| 主题 | 症状 → 修复 | 关键位置 |
|---|---|---|
| YAML schema 扩展 | `models.<name>` 下可选 `pricing:` block(`input_per_1k_usd` / `output_per_1k_usd` / `per_image_usd` / `per_task_usd`,全部 USD)。未知子字段在 YAML load 时 raise `RegistryReferenceError`,避免 typo 静默变成 $0。 | `config/models.yaml` / `providers/model_registry.py` |
| Registry 翻译层 | 新增 `ModelPricing` dataclass;`ModelDef.pricing` → `ResolvedRoute.pricing` → `ModelAlias.as_policy_fields()["prepared_routes"][i]["pricing"]` 全链传递。`PreparedRoute`(Pydantic bundle schema)加 `pricing: dict[str, float] \| None` 字段。 | `providers/model_registry.py` / `core/policies.py` |
| BudgetTracker 三 estimator | `estimate_call_cost_usd` / `estimate_image_call_cost_usd` 都加 `route_pricing` 可选参数,优先于 litellm 查表。新增 `estimate_mesh_call_cost_usd(num_candidates, route_pricing)` —— 之前根本不存在,mesh 步骤永远是 $0。 | `runtime/budget_tracker.py` |
| Router 回传选中 route 的 pricing | `CapabilityRouter` 四方法不改 tuple 签名,而是把 pricing 塞进 `ProviderResult.raw["_route_pricing"]` / `ImageResult.raw["_route_pricing"]` / 结构化调用的 `usage["_route_pricing"]`。执行器读这几个 key 再喂给 BudgetTracker。新 helper `_stash_route_pricing_on_result` / `_stash_route_pricing_on_usage` 统一实现。 | `providers/capability_router.py` |
| Executor 写 cost_usd | `GenerateImageExecutor._generate_via_router` 返回值扩到 3-tuple,把 route_pricing 单独拎出来(不再污染 `ImageCandidate.metadata`),调用 `estimate_image_call_cost_usd(..., route_pricing=...)`。`ReviewExecutor` 从 `r.usage.get("_route_pricing")` 读。`GenerateMeshExecutor` 从 `ctx.step.provider_policy.prepared_routes[0].pricing` 读(mesh 不走 router,直接从 step 取),写 `metrics["cost_usd"]`。`orchestrator` 的 fallback 路径也 forward `usage["_route_pricing"]`。 | `runtime/executors/generate_image.py` / `runtime/executors/review.py` / `runtime/executors/generate_mesh.py` / `runtime/orchestrator.py` |
| 实填国内 provider 价 | `config/models.yaml` 为 Zhipu GLM-4.6v / GLM-4.6v-flashx / GLM-Image、DashScope Qwen-Plus / Qwen-Image-2.0(+Pro) / Qwen-Image-Edit-(Plus/Max)、Hunyuan Image v3 / Hunyuan 3D-3.1 都填了 2026-04-21 官网 CNY 报价 × 汇率 7.2 换算。国外 provider(OpenAI / Anthropic via PackyCode / Google / MiniMax)留空继续让 litellm 查表;合同价不同的客户就地覆写即可。 | `config/models.yaml` |

未启动:`cache_read` / `reasoning` tokens 预留 key 但不连 estimator(Claude / GPT-4 专有);`per_image_by_size` 档位化待 size 分档成为实际需求再接;CNY 汇率自动换算不做,yaml 注释就地写 CNY 原价 + 换算日期。

### 近期加固(2026-04 pricing probe,替换 fabricated 定价)

上一轮 pricing wiring 完工后,user 追问 "hy-3d-3.1 的 pricing 你是从哪里获取的",抓出 CN provider 所有定价数字都是 claude 凭印象编的(无 verified 来源)。止血 + 长期方案一并落:

| 主题 | 症状 → 修复 | 关键位置 |
|---|---|---|
| 止血:清 fabricated 数字 | `config/models.yaml` 里 GLM / Qwen / Hunyuan / Tripo3D 等 7 个模型的 `pricing:` 数字全部回退成 `null` + TODO 注释,指向 `python -m framework.pricing_probe` 工具。保留字段结构,但 runtime 退回 `fallback_cost_per_1k` 粗估 —— 粗估诚实 > 假数字装作精确。 | `config/models.yaml` |
| `pricing_autogen` 元数据 | 新增 `PricingAutogen` dataclass(status: fresh/stale/manual,sourced_on,source_url,cny_original)挂在 `ModelDef` 上。运行时不参与成本计算,仅供 probe 审计 + operator 看价格新鲜度。未知字段 + 非白名单 status 都在 YAML load 时 raise 防止 typo 静默生效。 | `providers/model_registry.py` |
| 探针 CLI 框架 | `framework/pricing_probe/` 新包:types / fetcher(httpx+UA+retry) / yaml_writer(ruamel.yaml 保留 inline 注释 + diff 输出) / per-provider parser 基类 + 5 个占位实现(zhipu/dashscope/hunyuan_image/hunyuan_3d/tripo3d)/ CLI(`python -m framework.pricing_probe [--only X] [--apply]`)。dry-run 默认,必须 `--apply` 才改 yaml。pricing_autogen.status=manual 永不被覆盖(给合同价留出口)。单家 parser 失败只标该家模型 `status: stale` 不影响其他家。 | `framework/pricing_probe/` 包共 7 个文件 |
| 关键发现:5 家全 SPA | 实测 httpx 拉每家定价页返回不到 4KB 骨架(zhipu 4.2KB / tripo3d 689B / dashscope 3.5MB JS bundle 但 0 个价格 token / hunyuan 文档页有"价格"字样但无数字)。user 选的 httpx+BS4 技术栈对所有目标 provider 都不够用 —— parser 实装必须从**手工 browser view-source 存 fixture** 开始。 | N/A(诊断结论) |
| Parser 实装留门 | 5 个 parser 都 `raise NotImplementedError(..."fixture")` 作为**反 fabrication fence**:正则确保消息含 "fixture" 关键字,`test_every_parser_currently_raises_notimplemented` parametrize 校验。任何人想"实装"一家必须先交 `tests/fixtures/pricing/<provider>.html` + parser + 单测三件套,写贡献指南 `tests/fixtures/pricing/README.md`。 | 五个 parser 文件 + fixtures README |

配套记忆 `feedback_no_fabricate_external_data.md` 落盘(外部事实性数据禁止凭印象写数字 + 伪造 sourced_on 注释)。

### 近期加固(2026-04 pricing probe playwright 实装,替代 httpx 骨架)

上一轮 pricing probe 骨架完工后发现 **5 家目标 provider 全部是 JS SPA**:httpx 静态拉取只返回 <5KB chrome 页面框架,价格在 JS 渲染后才出现。按 user 选项引入 playwright+chromium 后端,并用真实 fixture 实装 3/5 家 parser,把 fabricated 定价全替换。

| 主题 | 症状 → 修复 | 关键位置 |
|---|---|---|
| playwright 后端 | `fetcher.fetch_html_rendered()` 用 `sync_playwright` + chromium headless,`wait_for_selector` 优先、`networkidle` fallback;`PricingParser.requires_js` 类属性驱动 CLI 在 httpx / playwright 之间分发;playwright lazy-import,未装时报可操作错误("run pip install playwright && playwright install chromium")。 | `framework/pricing_probe/fetcher.py` / `parsers/base.py` / `cli.py` |
| Hunyuan 3D parser(fabrication 事件起因) | 真实定价**不是**简单 per-task CNY,而是积分制(credit-based):Image-to-3D 15 积分/次 × 后付费 ¥0.12/积分 = **¥1.80/次 ≈ USD 0.25**。上一轮 fabricate 的 $0.14 **低估 44%**。parser 联合解析两个 table(后付费积分单价 + API 积分消耗)合成 per_task 价。fixture 存 `tests/fixtures/pricing/hunyuan_3d.html`(280KB)。 | `parsers/hunyuan_3d.py` + 3 fixture tests |
| Zhipu parser(3 model) | Zhipu 视觉模型按 input 长度**分层**(`[0, 32)` vs `[32, 128)`),parser 取最便宜的短 context tier(大多数 review 用例适配)。GLM-4.6V 真实 $0.000139/1K input(**fabrication 高估 20×**),FlashX $0.000021/1K(**高估 13×**),GLM-Image $0.0139/张(fabrication 巧合对上)。 | `parsers/zhipu.py` + 5 fixture tests |
| Hunyuan Image parser(2 model) | 真实报价 ¥0.5/张 postpaid(`<1万/月` tier),**fabrication $0.0083 低估 8×**。实际 USD 0.0694/张。与 hy-3d 共用 `tencent_doc_table_rows` helper(抽到 `parsers/base.py`),同一 Tencent 文档 table 格式二处复用。 | `parsers/hunyuan_image.py` + 2 fixture tests |
| DashScope parser(6 model,延伸第二批) | 2026-04-22 补做。找到 `help.aliyun.com/zh/model-studio/model-pricing` 是聚合定价页(帮助文档模型大全),按模型名**精确匹配首列**(排除 Batch/cache/dated 变体)+ 按表头文本(而非列序)定位输入/输出单价列。qwen-plus 两个 tier(`≤128K` ¥0.8/¥2 vs `≤256K` ¥2.936/¥8.807)取便宜的 128K(框架默认用例)。5 个图像 /图像编辑模型从"输出单价"列提 ¥/张。**fabrication 对比**:qwen-image-2-pro 实际 $0.0694 vs 编的 $0.022(低估 **3.2×**),qwen-image-edit-max $0.0694 vs $0.028(低估 **2.5×**),qwen-image-edit $0.0417 vs $0.019(低估 2.2×)。qwen-plus 巧合一致。 | `parsers/dashscope.py` + 4 fixture tests |
| Tripo3D:公开页无 API 单价 | 2026-04-22 调研发现 Tripo3D 公开页**只有订阅档**(Free / Starter $19.9/月 3000 积分 / Creator $49.9/月 / Premium $139.9/月),**API per-task 单价未公开**——`www.tripo3d.ai/api` 页的"View API Pricing"按钮直接跳回同一订阅页,企业 API 合同价需 Contact Us。parser 保留 scaffold,`NotImplementedError` 消息更新为真实描述(引用 fixture + 指引 operator 改 `status: manual`)。`tripo3d_v2` 目前无 alias 引用,零运行时影响。有合同价的用户在 yaml 设 `pricing_autogen.status: manual` 后探针永不覆盖。 | `parsers/tripo3d.py` 注释 + `tests/fixtures/pricing/tripo3d.html`(reference) |
| 反 fabrication 守门 | `test_every_scaffold_parser_still_raises_notimplemented` parametrize 覆盖剩余 2 家 scaffold,强制任何人想实装必须先交 fixture(`match="fixture"` assertion)。3 家已实装的从 `_IMPLEMENTED_PARSERS` set 排除。 | `tests/unit/test_pricing_probe_framework.py` |
| 端到端 --apply | `python -m framework.pricing_probe --apply` 跑一次后 `config/models.yaml` 里 6 个 model(glm_4_6v / _flashX / glm_image / hunyuan_image_v3 / _style / hunyuan_3d)全部带上 `pricing:` 真值 + `pricing_autogen: { status: fresh, sourced_on: 2026-04-21, source_url, cny_original }` 审计块。dashscope / tripo3d 下辖的 8 个 model 继续等 parser 实装。 | `config/models.yaml` |

### 后续(未启动)

- **bridge_execute 模式**(§G #1):manifest_only 稳定运行后再评估。
- **Audio worker**(§G #2):mesh 已完,audio 保留占位。
- **Bridge 自动 rollback**(§G #13):待 Phase C 材质创建启用后。
- **WebSocket 鉴权 / 多租户 session**:目前 `--serve` 绑定 `127.0.0.1`,未来接入 UI 时再加。
- **FBX self-containment 校验**:当前 OK 桶里 `.fbx` 排最后,因为无法 inline 解析 FBX 依赖关系;后续若有需要可引入 PyFBX 或 `ufbx` 绑定,配合 `_build_candidate` 做外部 media 审计。

---

## N. EventBus + WebSocket 进度推送(Plan C Phase 8)

### 事件流拓扑

```
Adapter (poll loop) ──publish(ProgressEvent)──> EventBus (asyncio.Queue × N subscribers)
Orchestrator (step_start/step_done) ──┘
Workers (mesh_poll) ──────────────────┘
                                           ↓ fan-out per subscriber
                                  Starlette WebSocket handler
                                           ↓ JSON
                                   Client (UI / CLI watcher)
```

### ProgressEvent schema

```python
class ProgressEvent(BaseModel):
    run_id: str
    step_id: str | None = None
    phase: str                    # "step_start" / "tokenhub_poll" / "mesh_poll" / "step_done" / ...
    elapsed_s: float = 0.0
    progress_pct: float | None = None
    raw: dict[str, Any] = {}
    timestamp: datetime            # UTC,服务器端生成
```

### 端点

| 端点 | 语义 |
|------|------|
| `GET /healthz` | 订阅者数量探活 |
| `WS  /ws/runs/{run_id}` | 订阅指定 run 的所有事件 |
| `WS  /ws/runs/{run_id}/steps/{step_id}` | 订阅单 step 事件 |

### CLI 用法

```bash
# 启动 run + WebSocket server(一键自包含)
python -m framework.run --task examples/image_to_3d_pipeline.json \
    --run-id run_01 --serve --serve-port 8080

# 客户端
wscat -c ws://127.0.0.1:8080/ws/runs/run_01
```

### 限制

- 内存 `asyncio.Queue`,不跨进程。多机 / 多进程场景需替换 Redis Pub/Sub 后端
- 无鉴权,仅适合单机开发机
- 队列满时丢弃最旧事件(subscriber 慢 backpressure 策略)