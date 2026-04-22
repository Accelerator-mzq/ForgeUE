# ForgeUE 详细设计说明书 (Low-Level Design)

| 字段 | 内容 |
| --- | --- |
| 文档编号 | FORGEUE-LLD-001 |
| 版本 | v1.0 |
| 基线日期 | 2026-04-22 |
| 文档性质 | 详细设计(类 / 方法 / 字段 / 算法级) |
| 上位文档 | `docs/design/HLD.md` |
| 下位文档 | `docs/testing/test_spec.md`、源代码 |

---

## 1. 引言

### 1.1 编写目的

本文档基于 HLD 分层,对每个子系统描述:

- Pydantic 对象字段定义
- 类与方法签名
- 关键算法与数据流
- 异常体系
- 错误处理路径

**设计原则**:详细设计的最终真源是源码(Pydantic schema + docstring)。本文档提供结构化索引与关键算法的文字描述,字段定义以表格化呈现,避免逐字段抄写造成漂移。

### 1.2 阅读约定

| 约定 | 说明 |
| --- | --- |
| `T?` | 可选字段 (Optional / 可为 None) |
| `list[T]` | Python 列表 |
| `dict[K, V]` | Python 字典 |
| `Literal["a","b"]` | 枚举字符串 |
| 文件路径 | 相对 `src/framework/` 或 `ue_scripts/` 的路径 |

---

## 2. Core 对象模型(`src/framework/core/`)

### 2.1 枚举(`enums.py`)

| 枚举 | 取值 | 用途 |
| --- | --- | --- |
| `RunMode` | `basic_llm` / `production` / `standalone_review` | 顶层运行语义 |
| `TaskType` | `structured_extraction` / `plan_generation` / `asset_generation` / `asset_review` / `ue_export` | 任务意图(可扩展) |
| `StepType` | `generate` / `transform` / `review` / `select` / `merge` / `validate` / `export` / `import_` / `retry` / `branch` / `human_gate` | 11 种 Step 类型 |
| `RiskLevel` | `low` / `medium` / `high` | 调度风险级 |
| `ReviewMode` | `single_judge` / `multi_judge` / `council` / `chief_judge` | 评审模式 |
| `Decision` | `approve` / `approve_one` / `approve_many` / `reject` / `revise` / `retry_same_step` / `fallback_model` / `rollback` / `human_review_required` / `abort_or_fallback` | Verdict 决策 |
| `FailureMode` | `provider_timeout` / `schema_validation_fail` / `review_below_threshold` / `ue_path_conflict` / `budget_exceeded` / `worker_timeout` / `worker_error` / `unsupported_response` / `disk_full` | 失败模式分类 |

### 2.2 Task(`task.py`)

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `task_id` | str | ✓ | 唯一标识 |
| `task_type` | TaskType | ✓ | 任务意图 |
| `run_mode` | RunMode | ✓ | 运行模式 |
| `title` | str | ✓ | 显示标题 |
| `description` | str? | — | 描述 |
| `input_payload` | dict | ✓ | 输入载荷 |
| `constraints` | dict | — | style/resolution/budget/latency/`parallel_dag`/`parallel_candidates` |
| `expected_output` | dict | ✓ | artifact_types 声明 |
| `review_policy` | ReviewPolicy? | — | 评审配置 |
| `ue_target` | UEOutputTarget? | △ | production/ue_export 必填 |
| `determinism_policy` | DeterminismPolicy? | — | seed / version / hash lock |
| `project_id` | str | ✓ | 多租户 |

### 2.3 Run(`runtime.py`)

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | str | 唯一标识 |
| `task_id` | str | 引用 Task |
| `project_id` | str | 多租户 |
| `status` | `pending / running / paused / succeeded / failed / escalated` | Run 状态机 |
| `started_at` / `ended_at` | datetime / datetime? | 时间戳 |
| `workflow_id` | str | 引用 Workflow |
| `current_step_id` | str? | 执行中的 Step |
| `artifact_ids` | list[str] | 产出 Artifact 引用 |
| `checkpoints` | list[Checkpoint] | 完成快照 |
| `trace_id` | str | OTel trace |
| `metrics` | dict | cost/latency/retries 汇总 |

### 2.4 Workflow / Step

**Workflow**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `workflow_id` / `name` / `version` | str | 标识 |
| `entry_step_id` | str | 入口 Step |
| `step_ids` | list[str] | 所有 Step id |
| `transition_policy` | TransitionPolicy | 全局默认转移策略 |
| `metadata` | dict | 含 `parallel_dag` 等 opt-in 开关 |

**Step**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `step_id` | str | 唯一 |
| `type` | StepType | 11 种 |
| `name` | str | 显示名 |
| `risk_level` | RiskLevel | 默认 low |
| `capability_ref` | str | `text.structured` / `image.generation` / `review.judge` 等 |
| `provider_policy` | ProviderPolicy? | — |
| `retry_policy` | RetryPolicy? | — |
| `transition_policy` | TransitionPolicy? | Step 级覆盖 Workflow |
| `input_bindings` | list[InputBinding] | 绑定 Task.input 或上游 Artifact |
| `output_schema` | dict | Pydantic / JSONSchema |
| `depends_on` | list[str] | DAG 依赖 |
| `config` | dict | Executor 特定 |
| `metadata` | dict | 杂项 |

### 2.5 Artifact(`artifact.py`)

**PayloadRef**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `kind` | `inline / file / blob` | 载体态 |
| `inline_value` | Any? | `kind=inline` 时填 |
| `file_path` | str? | 相对 Artifact Store root |
| `blob_key` | str? | 对象存储 key(blob 预留) |
| `size_bytes` | int | 体积 |

**ArtifactType**

| 字段 | 类型 | 示例 |
| --- | --- | --- |
| `modality` | `text/image/audio/mesh/material/bundle/ue` | `image` |
| `shape` | str | `raster` / `gltf` / `sprite_sheet` |
| `display_name` | str | `concept_image` / `mesh_asset` |

**Artifact**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `artifact_id` | str | 唯一 |
| `artifact_type` | ArtifactType | — |
| `role` | `intermediate/final/reference/rejected` | — |
| `format` | str | png / glb / json |
| `mime_type` | str | — |
| `payload_ref` | PayloadRef | — |
| `schema_version` | str | — |
| `hash` | str | 内容哈希 |
| `producer` | ProducerRef | `{run_id, step_id, provider, model}` |
| `lineage` | Lineage | §2.6 |
| `metadata` | dict | 按 modality 扩展 |
| `validation` | ValidationRecord | 4 层校验结果 |
| `tags` | list[str] | — |
| `created_at` | datetime | — |

### 2.6 Lineage

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source_artifact_ids` | list[str] | 上游输入 |
| `source_step_ids` | list[str] | 产生 Step |
| `transformation_kind` | str? | `image_to_3d` / `image_edit` / ... |
| `selected_by_verdict_id` | str? | Verdict 选出 |
| `variant_group_id` | str? | 同族多版本 |
| `variant_kind` | str? | `original/compressed/lod_0/lod_1/retouched` |

### 2.7 Modality 专属 metadata

**image**

```
{ width, height, color_space, style_tags, prompt_summary, seed?,
  transparent_background, intended_use, alpha_channel, tileable,
  texture_usage_hint: "albedo|roughness|normal|...",
  variation_group_id? }
```

**audio**

```
{ duration_sec, sample_rate, channels, bit_depth,
  loopable, loop_in_sec?, loop_out_sec?,
  mood_tags, tempo_bpm?, intended_use: "bgm|sfx|...",
  peak_db?, lufs? }
```

**mesh**

```
{ mesh_format: "glb|fbx|usd", poly_count, material_slots,
  has_uv, has_rig, scale_unit: "cm|m", up_axis: "Y|Z",
  bounding_box: [x, y, z], intended_use: "static_mesh|skeletal_mesh",
  lod_count?, collision_hint? }
```

**text.structured**

```
{ schema_name, schema_version, language: "zh-CN|en-US|...", fields_complete }
```

### 2.8 Candidate / CandidateSet

**Candidate**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `candidate_id` | str | — |
| `artifact_id` | str | — |
| `source_step_id` | str | — |
| `source_model` | str | — |
| `score_hint` | float? | provider 侧评分 |
| `notes` | str? | — |

**CandidateSet**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `candidate_set_id` | str | — |
| `source_step_id` | str | — |
| `candidate_ids` | list[str] | — |
| `selection_goal` | str | 人类可读 |
| `selection_policy` | `single_best/multi_keep/threshold_pass` | — |
| `selection_constraints` | dict | — |

### 2.9 Review 对象族

**ReviewNode**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `review_id` | str | — |
| `review_scope` | `answer/image/audio/mesh/asset/workflow_step_output` | — |
| `review_mode` | ReviewMode | — |
| `target_kind` | `artifact/candidate_set` | — |
| `target_id` | str | — |
| `rubric` | Rubric | — |
| `judge_policy` | ProviderPolicy | — |

**ReviewReport**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `report_id` | str | — |
| `review_id` | str | — |
| `summary` | str | — |
| `scores_by_candidate` | dict[str, DimensionScores] | — |
| `issues_per_candidate` | dict[str, list[str]] | — |

**DimensionScores**(5 维)

| 维度 | 说明 |
| --- | --- |
| `constraint_fit` | 是否满足约束 |
| `style_consistency` | 风格一致 |
| `production_readiness` | 可上线度 |
| `technical_validity` | 技术合法性 |
| `risk_score` | 风险评估 |

**Verdict**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `verdict_id` | str | — |
| `review_id` / `report_id` | str | 双指针 |
| `decision` | Decision | 9 种 |
| `selected_candidate_ids` / `rejected_candidate_ids` | list[str] | — |
| `confidence` | float | 0-1 |
| `reasons` | list[str] | — |
| `dissent` | list[str] | 不同意见 |
| `recommended_next_step_id` | str? | — |
| `revision_hint` | dict? | 回传 Generator |
| `followup_actions` | list[str] | — |

### 2.10 UE 相关对象(`ue.py`)

**UEOutputTarget**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `project_name` | str | — |
| `project_root` | str | 本地 UE 工程绝对路径 |
| `asset_root` | str | `/Game/Generated/Tavern` 形式 |
| `asset_naming_policy` | `gdd_mandated/house_rules/gdd_preferred_then_house_rules` | — |
| `expected_asset_kinds` | list[str] | texture/static_mesh/sound_wave/... |
| `import_mode` | `manifest_only/bridge_execute` | MVP 默认 manifest_only |
| `validation_hooks` | list[str] | — |

**UEAssetManifest / UEAssetEntry / UEImportPlan / UEImportOperation / Evidence**:字段定义见 `src/framework/core/ue.py`,用法见 §10。

### 2.11 Checkpoint / ValidationRecord

**Checkpoint**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `step_id` | str | — |
| `artifact_hashes` | list[str] | 产物哈希快照 |
| `completed_at` | datetime | — |

**ValidationRecord**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | `pending/passed/failed` | — |
| `checks` | list[ValidationCheck] | — |
| `warnings` | list[str] | — |
| `errors` | list[str] | — |

**ValidationCheck**: `{ name, result: passed/failed/skipped, detail? }`

---

## 3. Policies 五件套(`core/policies.py`)

### 3.1 TransitionPolicy

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `on_success` | None | 成功转移目标 step_id |
| `on_approve` / `on_reject` / `on_revise` / `on_retry` / `on_fallback` / `on_rollback` / `on_human` | None | 按 Decision 分支 |
| `max_retries` | 2 | retry_same_step 上限 |
| `max_revise` | 2 | revise 回环硬上限 |
| `timeout_sec` | None | Step 级超时 |

**关键语义**:

- `abort_or_fallback` Decision 优先 honour `on_fallback`,未配则终止
- `fallback_model` 回同 step 重试(换 model)
- DAG 模式的 `retry_same_step` 通过 `done.discard(current)` 允许同 step 重新进入循环

### 3.2 RetryPolicy

| 字段 | 说明 |
| --- | --- |
| `max_attempts` | 总尝试次数 |
| `backoff` | `fixed/exponential` |
| `retry_on` | `["timeout","schema_fail","provider_error"]` 等 FailureMode 字符串 |

### 3.3 ProviderPolicy

| 字段 | 说明 |
| --- | --- |
| `capability_required` | `text.structured` 等 capability key |
| `preferred_models` | 首选 model id 列表 |
| `fallback_models` | 降级列表 |
| `cost_limit` / `latency_limit_ms` | 单调用上限 |
| `api_key_env` / `api_base` | Legacy 单别名级 auth(手写 bundle 用) |
| `prepared_routes` | list[PreparedRoute],loader 展开 `models_ref` 时填充 |

**PreparedRoute**

| 字段 | 说明 |
| --- | --- |
| `model` | LiteLLM model id |
| `api_key_env` / `api_base` | 路由级 auth(允许同 alias 混合多家 provider) |
| `kind` | `text/image/image_edit/mesh/vision/audio` |
| `pricing` | `dict? { input_per_1k_usd, output_per_1k_usd, per_image_usd, per_task_usd }` |

### 3.4 BudgetPolicy

| 字段 | 说明 |
| --- | --- |
| `total_cost_cap_usd` | Run 级成本封顶 |
| `gpu_seconds_cap` | GPU 时上限(预留) |

### 3.5 EscalationPolicy

| 字段 | 说明 |
| --- | --- |
| `on_exhausted` | `human_gate/stop/log_only` |
| `notify_channel` | 邮件 / Slack / 飞书 channel id(预留) |

### 3.6 ReviewPolicy(Task 层)

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `enabled` | True | — |
| `default_mode` | `single_judge` | — |
| `pass_threshold` | 0.75 | 默认通过门槛 |

### 3.7 DeterminismPolicy

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `seed_propagation` | True | seed 向下游传递 |
| `model_version_lock` | True | 禁止 model 版本漂移 |
| `hash_verify_on_resume` | True | resume 前核对 artifact_hash |

### 3.8 Rubric

**RubricCriterion**

| 字段 | 说明 |
| --- | --- |
| `name` | 5 维之一(见 §2.9) |
| `weight` | 权重 |
| `min_score` | 最低分,默认 0.0 |

**Rubric**

| 字段 | 说明 |
| --- | --- |
| `criteria` | list[RubricCriterion] |
| `pass_threshold` | 综合通过门槛 |

---

## 4. Schemas(`src/framework/schemas/`)

### 4.1 业务 schema 注册(`registry.py`)

| Schema | 用途 |
| --- | --- |
| `UECharacter` | UE 角色结构化(Stats / Skills / Inventory) |
| `UEApiAnswer` | UE5 API 查询问答 |
| `ImageSpec` | 图像生成规格 |
| `MeshSpec` | 网格生成规格 |

### 4.2 Instructor 接入

所有结构化生成走 `instructor.from_litellm(litellm.acompletion)`。schema 校验失败 → `FailureMode.schema_validation_fail` → `Decision.retry_same_step`。

### 4.3 UECharacter 容错分支

`_accept_json_string` 在 MiniMax-M2.x 的 stringified-object 场景下原样返回 str,下游 Pydantic `Stats` 强类型 int 字段做 fail-closed。**不**改为 fail-fast,避免破该场景(权衡见 plan_v1 §M "未平移项")。

---

## 5. Runtime 子系统(`src/framework/runtime/`)

### 5.1 Orchestrator(`orchestrator.py`)

**核心方法**

```
async def arun(self, task: Task, workflow: Workflow, steps: list[Step],
               artifact_root: Path, run_id: str | None = None,
               resume: bool = False) -> RunResult
```

**九阶段实现**:Task ingestion → Workflow resolution → DryRunPass → Scheduling plan → Step execution(async loop)→ Verdict dispatching → Validation gates → Export → Run finalize。

**DAG 并发**:

```
if task.constraints.get("parallel_dag") or workflow.metadata.get("parallel_dag"):
    # 多 depends_on 入度为 0 的 step 通过 asyncio.wait(FIRST_EXCEPTION) 并发
    done, pending = await asyncio.wait(tasks, return_when=FIRST_EXCEPTION)
    # 任一异常 → cancel siblings,re-raise
```

**retry_same_step 修复**(plan_v1 §M 第一轮):

```
# 错误实现:
if next_id == current: break   # DAG 分支把 retry_same_step 当终止

# 正确实现:
done.discard(current)           # 允许同 step 重新入循环
```

**取消 / 超时**:外层 `asyncio.wait_for(adapter.acompletion(call), timeout=T)`;内部 poll 的 `await asyncio.sleep` 不吞 `CancelledError`。

### 5.2 Scheduler(`scheduler.py`)

**调度算法**:

1. 构建 DAG,计算入度
2. 入度为 0 的 Step → ready queue
3. Ready queue 按 `risk_level` 升序(low → medium → high)
4. 完成后触发下游入度减 1
5. 并发上限由 `ResourceBudget` 约束

**Risk ordering fence**:见 `tests/unit/test_scheduler_risk_ordering.py`。

### 5.3 DryRunPass(`dry_run_pass.py`)

预检项清单(见 SRS FR-LC-002):

| 预检 | 失败行为 |
| --- | --- |
| manifest 解析成功 | Run = failed |
| Step `output_schema` 合法 | Run = failed |
| ProviderPolicy.preferred_models 可达 | Run = failed |
| input_bindings 能解析 | Run = failed |
| UEOutputTarget.project_root 可访问 | Run = failed |
| UE 侧路径无同名冲突 | warn(不阻断) |
| Budget 估算不超 cap | Run = failed |
| 付费步未声明 cap | `warnings.budget.cap_declared`(不阻断,F1) |
| Secrets 齐全 | Run = failed |
| Resume: artifact_hash 一致 | Run = failed |

### 5.4 CheckpointStore(`checkpoint_store.py`)

| 方法 | 说明 |
| --- | --- |
| `record(run_id, step_id, input_hash, artifact_ids, artifact_hashes, metrics)` | 写 Checkpoint(每步完成后) |
| `find_hit(run_id, step_id, input_hash, repository) -> Checkpoint?` | resume / 重入 cache 命中查找 |
| `latest_for_step(run_id, step_id) -> Checkpoint?` | 取最近一个 |
| `load_from_disk(run_id)` | resume 入口,加载 `_checkpoints.json` |

**find_hit 不变量**(`test_checkpoint_store::test_miss_on_length_mismatch` 守门):

1. `cp.input_hash != input_hash` → miss
2. `len(cp.artifact_ids) != len(cp.artifact_hashes)` → miss(`zip()` 会静默截断,显式守门避免外部数据污染)
3. 任何 `repository.exists(aid) == False` → miss
4. 任何 `repository.get(aid).hash != recorded_hash` → miss

**cp.metrics 字段契约**(供 cache-hit 路径回放):

| 键 | 类型 | 写入时机 |
| --- | --- | --- |
| `cost_usd` | float | Orchestrator 估算后**先**写入 `exec_result.metrics`,再 `record()` 落盘 |
| `chosen_model` / `model` | str | executor 自己写 |
| `usage` | dict | executor 自己写(text 路径含 `_route_pricing`) |
| `attempts` / `candidate_count` 等 | int | executor 自己写 |

**关键顺序**(orchestrator.py `_aexec_one_body`):
- ❶ `executor.execute()` → ❷ 估算并写 `cost_usd` 到 `metrics` → ❸ `checkpoints.record(metrics=exec_result.metrics)` → ❹ `_dump_run_artifacts_if_possible()` → ❺ `budget_tracker.record() + check()`

颠倒 ❷❸ 顺序会导致 `GenerateStructuredExecutor` 等 executor 自身不算 cost 的步骤,checkpoint 永远不带 `cost_usd`,跨进程 resume 无法回放预算(`test_codex_audit_fixes::test_structured_step_persists_cost_for_resume` 守门)。

#### 5.4.1 ArtifactRepository 跨进程持久化(`artifact_store/repository.py`)

CheckpointStore 只持久化 hash + metrics;Artifact 元数据(`payload_ref` / `lineage` / `producer` 等)也必须落盘,fresh-process `--resume` 才能让 `find_hit` 调 `repository.exists(aid)` 命中(否则即使 `_checkpoints.json` 存在,`exists()` 永远 False,整个 pipeline 静默重跑)。

| 方法 | 说明 |
| --- | --- |
| `dump_run_metadata(run_id, run_dir) -> int` | 写 `<run_dir>/_artifacts.json`,只含 producer.run_id 匹配的条目;`find_by_producer` 内部 `list()` snapshot,DAG 并发下不会 `dictionary changed size during iteration` |
| `load_run_metadata(run_id, run_dir) -> int` | 从 `_artifacts.json` 反序列化 + register;**三道过滤**:已存在 id skip / 后端 `exists()` False skip / file/blob 实际字节 hash 漂移 skip(inline 不需要二次校验,payload 直接随元数据走) |

**Orchestrator 集成**:`_aexec_one_body` 在 `record()` 之后调 `_dump_run_artifacts_if_possible()`;CheckpointStore 在内存模式(`_root is None`)时 no-op,与 `_checkpoints.json` 对齐。dump 不再吞写盘异常 — 失败必须抛,免得 resume 时静默 cache miss。

**fence 守门**(`test_codex_audit_fixes`):
- `test_load_run_metadata_skips_missing_payload` — 文件被删后不重注册
- `test_load_run_metadata_skips_corrupted_payload` — 文件被改后不重注册
- `test_resume_yields_cache_hits_after_reload` — 端到端往返
- `test_find_by_producer_safe_under_concurrent_put` — 并发安全

### 5.5 TransitionEngine(`transition_engine.py`)

**核心方法**

```
def on_verdict(*, step: Step, verdict: Verdict, default_next: str|None) -> TransitionResult
def on_success(step: Step, *, default_next: str|None) -> TransitionResult
def cloned_for_run() -> "TransitionEngine"      # 每个 arun 用一个独立 counters
```

**决策映射**

| Decision | 目标字段 | 降级 |
| --- | --- | --- |
| `approve` / `approve_one` / `approve_many` | `on_approve` / `on_success` | 无配置 → 自然下一步 |
| `reject` | `on_reject` | 无配置 → 终止 |
| `revise` | `on_revise` | revise_count > max_revise → 终止 |
| `retry_same_step` | **`on_retry` 优先**,未配则同 step | retry_count > max_retries → 终止 |
| `fallback_model` | `on_fallback` 或同 step | retry_count > max_retries → 终止 |
| `abort_or_fallback` | `on_fallback` | 未配 → 终止(**不回 same step 重计费**) |
| `rollback` | `on_rollback` | — |
| `human_review_required` | `on_human` | — |

**`on_retry` 字段语义**(`test_codex_audit_fixes::test_retry_same_step_honours_policy_on_retry` 守门):

`TransitionPolicy.on_retry: str | None = None` 长期存在但无人读;`retry_same_step` 要么走 `policy.on_retry`(workflow 想把 retry 重定向到 sanitiser step / 别的 capability),要么 fallback 到 `step.step_id`。

**counters 生命周期** — **per-arun 隔离**:

`TransitionCounters{retry: dict, revise: dict}` 不可跨 run 共享:
- 同 instance 顺序两个 `arun()` → 第二个 run 不能背着第一个 run 的 retry 计数
- 同 instance 并发两个 `arun()` → 两个 run 不能竞争同一 `counters` 字典

实现:`Orchestrator.arun` 入口调 `transitions = self.transitions.cloned_for_run()`,所有 `_aexec_one_body` 透传该 local 实例,不动 `self.transitions`。

`cloned_for_run()` 用 `copy.copy(self)` + 重置 `counters`:
- 保留子类身份(注入 `Orchestrator(transition_engine=MyEngine(label="L1"))` 的扩展点不被吞)
- 保留实例属性(子类 `__init__` 装的字段)
- 只重置 `TransitionCounters` 这一个字段

**ADR-006**(per-arun TransitionEngine 隔离):
- 早期实现 `Orchestrator.__init__` 把 engine 当成单例 instance,counters 生命周期 = orchestrator;Codex 第 1 / 第 3 轮 audit 揭露此模式破坏跨 run 隔离 + 子类不兼容。
- 改为 per-arun clone:行为正确,API 兼容(注入的 engine 仍可作为 prototype)。

fence 守门:
- `test_codex_audit_fixes::test_orchestrator_uses_fresh_transition_engine_per_arun` — 顺序两 run sentinel 不被覆盖
- `test_codex_audit_fixes::test_orchestrator_concurrent_arun_does_not_share_counters` — 并发两 run sentinel 不被覆盖
- `test_codex_audit_fixes::test_transition_engine_clone_preserves_subclass_and_attrs` — 子类身份保留

### 5.6 BudgetTracker(`budget_tracker.py`)

**状态**

```
total_cost_usd: float = 0.0
prompt_tokens: int = 0
completion_tokens: int = 0
total_tokens: int = 0
per_step: dict[str, dict]
```

**三 estimator**

| 方法 | 签名 |
| --- | --- |
| `estimate_call_cost_usd(usage, model, route_pricing=None) -> float` | text 调用 |
| `estimate_image_call_cost_usd(num_images, model, route_pricing=None) -> float` | 图像生成 |
| `estimate_mesh_call_cost_usd(num_candidates, model, route_pricing=None) -> float` | mesh 生成 |

**定价查找优先级**:

1. `route_pricing` 参数(来自 `_route_pricing` 透传)
2. `litellm.completion_cost()`(只对国外 provider 有效)
3. `fallback_cost_per_1k` 粗估(退底)

**软终止**:每步后 `check()`,超 `total_cost_cap_usd` → 合成 `budget_exceeded` Verdict → TransitionEngine 终止。

**写 RunResult**:`budget_summary = { total_cost_usd, prompt/completion/total_tokens, per_step }`。

**Cache-hit 回放规则**(fresh-process `--resume` 不绕预算):

跨进程 `--resume` 时 BudgetTracker 是空的,但 checkpoint 的 `cp.metrics["cost_usd"]` 已经持久化(见 §5.4 字段契约);`Orchestrator._aexec_one_body` cache-hit 路径必须把这笔 cost 重算入 tracker:

```
if hit and task.budget_policy:
    cached = hit.metrics.get("cost_usd") or 0.0
    if cached > 0 and budget_tracker.spend.by_step.get(step.step_id, 0) == 0:
        budget_tracker.record(step_id, model, cost_usd=cached)
        if not budget_tracker.check(): terminate(budget_exceeded)
```

**去重判据**:`spend.by_step.get(step_id, 0) == 0`。同进程 cache hit(retry / revise 重入)`by_step` 已经累计过,跳过避免双计;跨进程 fresh tracker `by_step` 全空,自动 record。

fence 守门:
- `test_codex_audit_fixes::test_orchestrator_replays_cached_cost_into_budget_tracker` — 第一次 run 写 $0.5,fresh 进程开 $0.1 cap resume,cache hit → terminate(budget_exceeded)

### 5.7 FailureModeMap(`failure_mode_map.py`)

**分类函数**

```
def classify(exc: Exception) -> FailureMode
```

**映射表**

| Exception | FailureMode | Decision |
| --- | --- | --- |
| `asyncio.TimeoutError` | `provider_timeout` | retry_same_step → fallback_model |
| `pydantic.ValidationError` | `schema_validation_fail` | retry_same_step |
| `MeshWorkerTimeout` / `WorkerTimeout` | `worker_timeout` | retry_same_step |
| `MeshWorkerUnsupportedResponse` / `WorkerUnsupportedResponse` / `ProviderUnsupportedResponse` | `unsupported_response` | abort_or_fallback |
| `MeshWorkerError` / `WorkerError` | `worker_error` | fallback_model |
| `BudgetExceededError`(合成) | `budget_exceeded` | escalate_human → stop |
| `ue_path_conflict`(manifest 校验) | `ue_path_conflict` | human_review_required |
| `OSError(ENOSPC)` | `disk_full` | rollback → stop |

**分类顺序**:unsupported 子类在通用 Error 分支**之前**捕捉,避免被 `worker_error` 吞。

#### 5.7.1 Unsupported 三层拦截(避免 deterministic bad shape 重复计费)

`*UnsupportedResponse` 既是 `*Error` 子类,需要在所有"自动 retry / fallback"路径前显式 short-circuit;否则一次 deterministic 200+HTML 响应会触发 1~3 次额外付费调用。

| 层 | 文件 | 拦截方式 | fence |
| --- | --- | --- | --- |
| **L1 transient retry** | `providers/_retry_async.py` 调用方(三处:`hunyuan_tokenhub_adapter`/`qwen_multimodal_adapter`/`mesh_worker._apost`) | `transient_check` lambda 显式 `not isinstance(e, *Unsupported*)`,因为 HTML body 含 "Service Unavailable" 等关键词会被 `is_transient_network_message` 误判 | `test_codex_audit_fixes::test_*_unsupported_response_skips_transient_retry` × 3 |
| **L2 router fallback loop** | `providers/capability_router.py` 4 方法(`acompletion` / `astructured` / `aimage_generation` / `aimage_edit`) | `except ProviderUnsupportedResponse: raise` **先于** `except ProviderError` 捕捉,直接跳出 fallback loop | `test_codex_audit_fixes::test_router_does_not_fallback_on_unsupported_response` |
| **L3 executor `_should_retry`** | 4 个 executor:`generate_structured` / `generate_image` / `generate_image_edit` / `generate_mesh` | 函数首行 `if isinstance(exc, *Unsupported*): return False`,生效于 `RetryPolicy.max_attempts > 1` 场景 | `test_codex_audit_fixes::test_image_executor_does_not_retry_on_unsupported_response` |

三层全部 short-circuit 后,exception 才升到 `_aexec_one_body` 的 `except BaseException`,经 `classify_failure` → `unsupported_response` → `Decision.abort_or_fallback` → `on_fallback`(未配则终止)。

### 5.8 Executors(`src/framework/runtime/executors/`)

| Executor | 文件 | 用途 |
| --- | --- | --- |
| GenerateStructured | `generate_structured.py` | 结构化 LLM(Instructor) |
| GenerateImage | `generate_image.py` | 图像生成(N 候选) |
| GenerateImageEdit | `generate_image_edit.py` | 图像编辑 |
| GenerateMesh | `generate_mesh.py` | 网格生成 |
| Review | `review.py` | 调 ChiefJudge |
| Select | `select.py` | CandidateSet → 选型 |
| Validate | `validate.py` | 独立验证 Step |
| Export | `export.py` | UEAssetManifest 生成 |
| Mock | `mock_executors.py` | P0 / 离线冒烟 |

**GenerateImageExecutor 关键**:

- `_generate_via_router(...)` 返回 3-tuple `(ImageResult, model, route_pricing)`
- `parallel_candidates=True` → `asyncio.gather(*[_one(i) for i in range(n)])`
- `num_candidates` 默认 3,对齐 Hunyuan `aimage_generation(n=3)` 真并发
- **同质性约束**:`parallel_candidates=True` 时若 N 个并发候选落到不同 route(preferred 部分失败转 fallback),`metrics["chosen_model"]` / `_route_pricing` 无法单值表达 → 显式 `raise RuntimeError("heterogeneous routes")`,要求工作流拆 step 或关 `parallel_candidates`(`test_codex_audit_fixes::test_generate_image_parallel_rejects_heterogeneous_models` 守门)

**GenerateImageEditExecutor 关键**:

- 走 `router.image_edit(...)`,从 `result.raw["_route_pricing"]` 取 pricing 后用 `estimate_image_call_cost_usd(...)` 算 `metrics["cost_usd"]`
- 早期版本只写 `attempts/edit_count/chosen_model/...`,`cost_usd` 缺失 → BudgetTracker 按 $0 计费 → 预算可被绕过(`test_codex_audit_fixes::test_image_edit_emits_cost_usd` 守门)

**ReviewExecutor 关键**:

- 调 `ChiefJudge.ajudge_with_panel(...)`
- 聚合每 judge 的 `usage` 写 `metrics["cost_usd"]`,喂 BudgetTracker(修复了 review 路径 cost 失计)

**GenerateMeshExecutor 关键**:

- mesh 不走 router,直接从 `ctx.step.provider_policy.prepared_routes[0].pricing` 读定价
- 写 `metrics["cost_usd"] = estimate_mesh_call_cost_usd(...)`

**SelectExecutor 关键**:

- 输入:upstream verdict artifact + candidate_set bundle / 直接 candidate artifacts
- 默认行为:`kept = [cid for cid in candidate_pool if cid in verdict.selected_candidate_ids]`
- **bare-approve 语义**:`verdict.decision in {approve, approve_one, approve_many}` 且 `selected_candidate_ids == []` → `kept = candidate_pool - rejected_candidate_ids`,与 `ExportExecutor._approve_filter` 的 "approve all upstream" 语义对齐
  - 关键修正:`rejected_candidate_ids` 必须从 `kept` 排除,而不是同时进 `selected` 和 `dropped`(下游只看 `selected_ids`,后者会让显式拒绝失效)
  - fence:`test_codex_audit_fixes::test_select_bare_approve_keeps_whole_pool` + `test_select_bare_approve_excludes_explicit_rejects`

---

## 6. Providers(`src/framework/providers/`)

### 6.1 ProviderAdapter 基类(`base.py`)

**四方法 async 接口**

```
async def acompletion(self, call: ProviderCall) -> ProviderResult
async def astructured(self, call: ProviderCall, schema: type[BaseModel]) -> BaseModel
async def astructured_with_usage(self, call: ProviderCall, schema) -> tuple[BaseModel, dict]
async def aimage_generation(self, call: ProviderCall, n: int = 1) -> ImageResult
async def aimage_edit(self, call: ProviderCall, image_bytes: bytes) -> ImageResult
def supports(self, model: str) -> bool
```

**sync-shim**:同名 sync 方法通过 `asyncio.run` 桥接,旧代码零改动。

**异常类族**

```
ProviderError                         # 基类
├── ProviderUnsupportedResponse      # 确定性坏响应,走 abort_or_fallback
└── ProviderTimeout
WorkerError                           # worker 基类
├── WorkerUnsupportedResponse        # 确定性坏响应,走 abort_or_fallback
├── WorkerTimeout
└── MeshWorkerError
    ├── MeshWorkerUnsupportedResponse
    └── MeshWorkerTimeout
```

### 6.2 CapabilityRouter(`capability_router.py`)

**核心方法**(4 方法 async)

```
async def completion(self, capability: str, call: ProviderCall) -> ProviderResult
async def structured(self, capability, call, schema) -> tuple[BaseModel, str, dict]
async def image_generation(self, capability, call, n=1) -> ImageResult
async def image_edit(self, capability, call, image_bytes) -> ImageResult
```

**分发算法**

1. 按注册顺序遍历 `self.adapters`
2. 每个 adapter 调 `adapter.supports(call.model)`
3. 命中第一个即 break,调 `adapter.acompletion(call)`
4. 把 route 的 pricing 塞进 `result.raw["_route_pricing"]`(或 `usage["_route_pricing"]`)

**注册顺序约束**:`LiteLLMAdapter`(wildcard `supports(*) == True`)必须最后注册。

**Fallback loop 异常分流**(4 方法都遵守):

```
except ProviderUnsupportedResponse:
    raise              # 先捕,绝不进 fallback —— 详见 §5.7.1 L2
except NotImplementedError:
    last = ProviderError("adapter does not support ..."); continue
except ProviderError as exc:
    last = exc; continue
```

`ProviderUnsupportedResponse` 是 `ProviderError` 子类,`except ProviderError` 会吞掉它把 deterministic 200+HTML 当成 route 故障,继续请求下一条 fallback model → 多付一次费。必须**先**捕 unsupported。

**Stash 辅助**:`_stash_route_pricing_on_result(result, pricing)` / `_stash_route_pricing_on_usage(usage, pricing)`。

### 6.3 ModelRegistry(`model_registry.py`)

**三段式 YAML 解析**

```
providers:
  <provider_id>:
    api_base: str
    api_key_env: str
    protocol: openai_compatible | dashscope | tokenhub | comfy | tripo3d

models:
  <model_name>:
    provider: <provider_id>
    model_id: str
    capability: [<capability_key>, ...]
    pricing:                      # 可选
      input_per_1k_usd: float
      output_per_1k_usd: float
      per_image_usd: float
      per_task_usd: float
    pricing_autogen:              # 可选,不参与成本计算
      status: fresh | stale | manual
      sourced_on: YYYY-MM-DD
      source_url: str
      cny_original: str | null

aliases:
  <alias_name>:
    models: [<model_name>, ...]
```

**解析产物**

```
ModelDef:   # 每个 models.<name> 条目
  provider: ProviderDef
  model_id: str
  capability: list[str]
  pricing: ModelPricing?
  pricing_autogen: PricingAutogen?

ModelAlias:  # 每个 aliases.<name> 条目
  candidates: list[ResolvedRoute]

ResolvedRoute:
  model: str (LiteLLM id)
  api_key_env: str
  api_base: str
  kind: str
  pricing: ModelPricing?

PreparedRoute: Pydantic bundle schema,字段同 ResolvedRoute
```

**错误**:`RegistryReferenceError`(未知字段 / 非白名单 status / alias 引用不存在的 model)。

### 6.4 具体 Adapter

#### 6.4.1 LiteLLMAdapter(`litellm_adapter.py`)

- `supports(*) == True`(wildcard)
- `acompletion` → `litellm.acompletion(...)`
- `aimage_generation` → `litellm.aimage_generation(...)`
- `_acollect_image_results(budget_s=None)` 收集 URL → `_afetch_url_bytes`,per-URL clamp 到 `min(60, remaining)`
- `_maybe_apply_prompt_cache()`:Anthropic 家族 + `_forge_prompt_cache=True` → 注入 `cache_control: { type: ephemeral }`
- `drop_params=True`:绕过 Anthropic 不识别的 `seed`

#### 6.4.2 QwenMultimodalAdapter(`qwen_multimodal_adapter.py`)

- DashScope 协议 via `httpx.AsyncClient`
- 空 choices / 无 image content → `ProviderUnsupportedResponse`
- 默认一次瞬态重试

#### 6.4.3 HunyuanTokenhubAdapter(`hunyuan_tokenhub_adapter.py`)

- Tencent tokenhub 协议(`/submit` + `/query` 轮询 + `/download`)
- `TokenhubMixin._th_poll`:`await asyncio.sleep(interval)`;`CancelledError` 透传
- `_th_poll` 回调自适应 `(status, elapsed_s)` 或 `(status, elapsed_s, raw_resp)`
- **单次 poll timeout clamp**:`min(20.0, max(1.0, budget_s - elapsed))`,避免剩余 1s 时单次 `/query` 仍阻塞 20s 突破 step timeout(`test_codex_audit_fixes::test_hunyuan_poll_clamps_timeout_to_remaining_budget` 守门;`HunyuanMeshWorker._atokenhub_poll` 同款 clamp 上限 30s)
- `submit` 无 id → `ProviderUnsupportedResponse`
- **200 + 非 JSON body**(代理/WAF 返回 HTML)→ `ProviderUnsupportedResponse`(`r.json()` 抛 `ValueError` 显式捕,不让 `JSONDecodeError` 逃出 try block);`HunyuanMeshWorker` / `qwen_multimodal_adapter` 同款修复
- `_extract_result_urls_ranked()` 返回 list,`_one()` 遍历试到一个 download 成功为止
- Image data URL:`data:image/png;base64,...`(`aimage_generation` 的 input)
- `aimage_generation(n>1)` 用 `asyncio.gather(*[_one(i) for i in range(n)])` 真并发(tokenhub 单次只接一条 prompt)

#### 6.4.4 FakeAdapter(`fake_adapter.py`)

P0 / 离线冒烟用,返回预置响应。

### 6.5 Workers

#### 6.5.1 ComfyWorker(`workers/comfy_worker.py`)

- HTTP `/prompt` + `/history` + `/view`
- 三处 deterministic bad shape → `WorkerUnsupportedResponse`:
  - spec 缺 `workflow_graph`
  - `/prompt` 响应无 `prompt_id`
  - `/history` outputs 无图片
- `_collect_outputs(budget_s, start_monotonic)`:per-image `min(30, remaining)` clamp,耗尽 → `WorkerTimeout`

#### 6.5.2 MeshWorker(`workers/mesh_worker.py`)

**HunyuanMeshWorker**

- submit 字段名 `image`(不是 `image_url`),data URL 编码
- `_rank_hunyuan_3d_urls()` 返回 ranked list,桶序 `(strong, ok, key, other, zip)`
- `_one()` 遍历 ranked list,catch `MeshWorkerUnsupportedResponse` fallthrough,catch `MeshWorkerError` 记最后一个(budget 耗尽时优先 raise download 错误)
- per-iter `remaining = budget - elapsed`,clamp `min(90, remaining)`,耗尽 → `MeshWorkerTimeout`
- 空 ranked URL → `MeshWorkerUnsupportedResponse`(不是 `MeshWorkerError`,避免重提重计费)
- `_extract_hunyuan_3d_url` 已下线(现用 ranker)
- `agenerate + asyncio.gather` 并发候选

**Tripo3DMeshWorker**

- `/task` 无 task_id / 轮询 success 但 output 无 URL → `MeshWorkerUnsupportedResponse`
- 轮询 clamp `min(20, remaining)`,下载 clamp `min(60, remaining)`,耗尽 → `MeshWorkerTimeout("... before model download")`

**mesh 格式检测 `_detect_mesh_format`**

| 格式 | 识别 | 备注 |
| --- | --- | --- |
| glb | `data[:4] == b"glTF"` | 魔数,2KB 松检测 |
| gltf | 自包含 JSON(`_is_self_contained_gltf`) | parse-fail → False |
| obj | `o ` / `g ` / `vn` / `v ` 起头 | ASCII |
| fbx(binary) | `Kaydara FBX Binary` | — |
| fbx(ASCII) | `; FBX` 注释头 + `FBXHeaderExtension:` | 新增分支 |
| zip | PKZIP 魔数 | 多 mesh 打包 |

**魔数 gate**

```
if fmt == "glb" and data[:4] != b"glTF":
    raise MeshWorkerUnsupportedResponse(...)
```

**glTF external-buffer 检测 `_gltf_has_external_geometry`**

- `buffers[].uri` 含非 `data:` 前缀的外部引用(顶点/索引)→ raise
- 仅纯 image 外挂允许 `missing_materials=True`
- JSON parse-fail → `return True`(保守,double-guard)

**`data:` URI 识别**

```
def _is_data_uri(uri: str) -> bool:
    return uri.lstrip().lower().startswith("data:")
```

RFC 2397 大小写不敏感。

**HTTP URL 识别**

```
def _is_http_url(uri: str) -> bool:
    return uri.lstrip().lower().startswith(("http://", "https://"))
```

RFC 3986 scheme 大小写不敏感。

### 6.6 下载(`_download.py` / `_download_async.py`)

**chunked_download_async**

```
async def chunked_download_async(
    url: str, dest: Path, client: httpx.AsyncClient,
    chunk_size: int = 1024*1024,
    max_retries: int = 3,
    progress_cb: Callable? = None,
    timeout_s: float? = None,
) -> int (bytes written)
```

**续传强校验**

```
if buf:  # 有残缺前缀,走 Range
    headers["Range"] = f"bytes={len(buf)}-"
    resp = await client.get(url, headers=headers)
    # 强校验:必须 206 且 Content-Range 起始 = len(buf)
    if resp.status_code != 206:
        buf.clear()  # 清空重下
    else:
        cr = resp.headers.get("Content-Range", "")
        m = re.match(r"bytes (\d+)-", cr)
        if not m or int(m.group(1)) != len(buf):
            buf.clear()
```

**瞬态重试**:SSL EOF / 超时 / 5xx → 2s 回退 × 1 次(`is_transient_network_message`)。

### 6.7 瞬态重试(`_retry.py` / `_retry_async.py`)

| 函数 | 签名 |
| --- | --- |
| `with_transient_retry(fn, *args, max_retries=1, backoff_s=2.0, **kwargs)` | sync |
| `with_transient_retry_async(afn, *args, ...)` | async |
| `is_transient_network_message(msg: str) -> bool` | 判定 |

覆盖 Qwen / Hunyuan tokenhub / HunyuanMeshWorker 的 POST 路径。LiteLLM 沿用自身重试。

---

## 7. Review Engine(`src/framework/review_engine/`)

### 7.1 LLMJudge(`judge.py`)

```
async def ajudge(self, candidate, rubric, provider_call) -> tuple[DimensionScores, list[str]]
```

- 内部调 `router.astructured(...)` 返回 `(ReviewJSON, usage)` 2-tuple
- `usage` 透传到 `metrics["cost_usd"]`
- 默认开启 `_forge_prompt_cache=True`(rubric 前缀稳定)

### 7.2 ChiefJudge(`chief_judge.py`)

```
async def ajudge_with_panel(
    self, candidate_set, rubric, judge_policies: list[ProviderPolicy]
) -> tuple[ReviewReport, Verdict]
```

- `asyncio.gather(*[judge.ajudge(...) for judge in self.judges])`
- 总延迟 ≈ 最慢 judge
- 聚合 scores → `DimensionScores`(按 rubric weight 加权)
- 综合分 > `pass_threshold` → `Decision.approve`;< 0.5×threshold → `reject`;中间 → `revise`

### 7.3 RubricLoader(`rubric_loader.py`)

- 从 `rubric_templates/*.yaml` 加载
- 当前模板:`ue_asset_quality` / `ue_character_quality` / `ue_visual_quality`

### 7.4 ReportVerdictEmitter(`report_verdict_emitter.py`)

- 把 ChiefJudge 输出拆成 `ReviewReport` + `Verdict` 两独立对象
- 同时落 Artifact Store

---

## 8. Artifact Store(`src/framework/artifact_store/`)

### 8.1 Repository(`repository.py`)

```
def put(self, artifact: Artifact) -> None
def get(self, artifact_id: str) -> Artifact
def by_run(self, run_id: str) -> list[Artifact]
def by_lineage(self, source_artifact_id: str) -> list[Artifact]
```

### 8.2 PayloadBackends(`payload_backends/`)

| Backend | 文件 | 触发 |
| --- | --- | --- |
| Inline | `inline_backend.py` | `PayloadRef.kind=inline`,上限 64 KB |
| File | `file_backend.py` | `kind=file`,落 `<artifact_root>/<run_id>/<artifact_id>.<ext>` |
| Blob | `blob_backend.py` | 预留,MVP 不启用 |

### 8.3 Hashing(`hashing.py`)

```
def hash_bytes(data: bytes) -> str    # sha256
def hash_file(path: Path) -> str
def hash_dict(obj: dict) -> str       # canonical JSON
```

### 8.4 Lineage(`lineage.py`)

追踪 artifact 间的 `source_artifact_ids` + `source_step_ids`,`transformation_kind`,`selected_by_verdict_id`。

### 8.5 VariantTracker(`variant_tracker.py`)

- `variant_group_id`:同族多版本标识(原始 / 压缩 / LOD_0 / 修图等)
- `variant_kind`:具体变体类型

---

## 9. UE Bridge(`src/framework/ue_bridge/`)

### 9.1 ManifestBuilder(`manifest_builder.py`)

```
def build(self, run_id: str, ue_target: UEOutputTarget,
          artifacts: list[Artifact]) -> UEAssetManifest
```

**关键检查**:

- Modality 映射:`image.raster` → `texture`,`mesh.gltf` → `static_mesh`,`audio.waveform` → `sound_wave`
- `validation.selected_filter=True` 的 artifact 跳过
- `inline` 载体的 importable artifact → raise(只接受 `file` 载体)
- `expected_asset_kinds` 声明了但 manifest 里缺 kind → flag warning

### 9.2 ImportPlanBuilder(`import_plan_builder.py`)

```
def build(self, manifest: UEAssetManifest) -> UEImportPlan
```

**算法**:

1. 每个 UEAssetEntry 的父目录 → 生成 `create_folder` op,`depends_on=[]`
2. `import_<kind>` op,`depends_on=[folder_op_id]`
3. 若启用 Phase C(允许材质 / 音频 cue 创建)→ 额外加 `create_material_from_template` op

### 9.3 PermissionPolicy(`permission_policy.py`)

**默认拒绝**:

| 操作 | 默认 | 开启方式 |
| --- | --- | --- |
| `import_texture` / `import_static_mesh` / `import_audio` | ✅ 允许 | — |
| `create_material_from_template` | ❌ 拒绝 | `ue_target.validation_hooks.include_phase_c=True` |
| `create_sound_cue_from_template` | ❌ 拒绝 | 同上 |

### 9.4 Inspect(`inspect/project.py`)

```
def inspect_project(project_root: Path) -> ProjectReadiness
def inspect_content_path(project_root: Path, asset_root: str) -> list[str]
def inspect_asset_exists(project_root: Path, object_path: str) -> bool
```

- `.uproject` 不存在 → 标记 missing
- 非 `/Game/` 开头的 asset_root → 返回空列表

### 9.5 Evidence(`evidence.py`)

```
def make_record(op_id, kind, status, source_uri=None,
                target_object_path=None, log_ref=None, error=None) -> dict
def append(path: Path, record: dict) -> None    # 原子追加
```

**原子写**:临时文件 + `os.replace`,避免半行写入。

### 9.6 validate_manifest

```
def validate_manifest(manifest: UEAssetManifest) -> list[str]  # errors
```

检测 `target_object_path` / `target_package_path` 的重复路径(冲突 → raise)。

---

## 10. Observability(`src/framework/observability/`)

### 10.1 EventBus(`event_bus.py`)

**Subscription**

```
class Subscription:
    queue: asyncio.Queue
    owning_loop: asyncio.AbstractEventLoop    # 创建时 asyncio.get_running_loop()
    filters: dict
```

**发布**

```
def publish_nowait(event: ProgressEvent) -> None:
    with self._subs_lock:                     # threading.Lock
        subs = list(self._subs)
    for sub in subs:
        if not _match(sub.filters, event):
            continue
        current_loop = asyncio.get_event_loop_policy().get_event_loop(...)
        if current_loop is sub.owning_loop:
            sub.queue.put_nowait(event)
        else:
            sub.owning_loop.call_soon_threadsafe(
                sub.queue.put_nowait, event
            )
```

**跨线程 hop 理由**:asyncio.Queue 不是线程安全容器;ambient `publish()` 的接口语义允许从 `asyncio.to_thread` 的 sync executor 发事件。

### 10.2 ProgressEvent schema

```
class ProgressEvent(BaseModel):
    event_type: Literal["run_start","run_done","run_failed",
                        "step_start","step_progress","step_done","step_failed",
                        "adapter_poll","worker_poll"]
    run_id: str
    step_id: str | None = None
    timestamp: datetime
    payload: dict
```

### 10.3 Compactor(`compactor.py`)

```
def compact_messages(
    messages: list[dict], target_tokens: int,
    keep_tail_turns: int = 4,
    tokenizer: Callable[[str], int] | None = None,
) -> tuple[list[dict], CompactionReport]
```

**算法**:

1. 保留首条 system
2. 保留末 `keep_tail_turns` 轮
3. 从中段剔除最旧消息,直到 ≤ target_tokens
4. 插入 `[auto-compact: N earlier message(s) omitted]` 占位符
5. Token 估算默认 4 字符 / token,可注入 tiktoken

### 10.4 Secrets(`secrets.py`)

```
def redact(text: str) -> str     # 掩盖 API key 样式字符串
def get_secret(env_key: str) -> str   # 读环境变量,缺失 raise
```

日志 / trace / event 输出前 `redact`。

### 10.5 Tracing(`tracing.py`)

- OTel tracer 可选启用
- Run 级 span:`run_id` 作为 trace_id
- Step 级 child span

---

## 11. Server(`src/framework/server/ws_server.py`)

### 11.1 端点

| Path | 用途 |
| --- | --- |
| `/ws/run/{run_id}` | Run 下所有事件推流 |
| `/ws/step/{run_id}/{step_id}` | 单个 Step 事件过滤推流 |

### 11.2 Handler 骨架(idle-safe)

```
async def ws_run(ws: WebSocket, run_id: str, bus: EventBus):
    await ws.accept()
    sub = bus.subscribe(filters={"run_id": run_id})
    try:
        while True:
            recv_task = asyncio.create_task(ws.receive_disconnect())
            event_task = asyncio.create_task(sub.queue.get())
            done, pending = await asyncio.wait(
                {recv_task, event_task}, return_when=FIRST_COMPLETED
            )
            for t in pending: t.cancel()
            if recv_task in done:
                break
            event = event_task.result()
            await ws.send_json(event.model_dump(mode="json"))
    finally:
        bus.unsubscribe(sub)
```

**idle-safe**:空闲期客户端关连不会留泄露 `Subscription`。

### 11.3 CLI 接入

```
python -m framework.run --serve [--host 127.0.0.1 --port 8000]
```

---

## 12. Pricing Probe(`src/framework/pricing_probe/`)

### 12.1 子模块

| 文件 | 用途 |
| --- | --- |
| `types.py` | `PriceRow` / `ParserResult` / `ApplyDiff` 等 dataclass |
| `fetcher.py` | httpx + UA + retry;`fetch_html_rendered()` playwright 后端 |
| `parsers/base.py` | `PricingParser` 基类(`requires_js` 类属性 + `tencent_doc_table_rows` helper) |
| `parsers/*.py` | 五家具体 parser |
| `yaml_writer.py` | `ruamel.yaml` 保留 inline 注释 + diff 输出 |
| `cli.py` | `__main__` 入口,`--only <provider>` / `--apply` flags |

### 12.2 Fetcher 分发

```
if parser.requires_js:
    html = await fetch_html_rendered(url, wait_selector=parser.wait_selector)
else:
    html = await fetch_html(url)
```

**playwright lazy import**:未装时 `ImportError` 转换为 "run pip install playwright && playwright install chromium" 可操作错误。

### 12.3 Parser 契约

```
class PricingParser:
    requires_js: ClassVar[bool] = False
    wait_selector: ClassVar[str | None] = None
    providers: ClassVar[list[str]]         # 覆盖的模型名
    
    def parse(self, html: str) -> dict[str, PriceRow]:
        ...
```

**反 fabrication fence**:未实装 parser 必须 `raise NotImplementedError(".../fixture")`,`test_every_scaffold_parser_still_raises_notimplemented` parametrize 守门。

### 12.4 YAML writer

```
def apply_prices(yaml_path: Path, updates: dict[str, PriceRow],
                 sourced_on: date, status: Literal["fresh","stale"]) -> ApplyDiff
```

- `pricing_autogen.status=manual` 永不覆盖(合同价出口)
- 单家失败只标该家 `status: stale`,不影响其他家
- inline 注释保留(ruamel.yaml)

### 12.5 CLI 语义

```
python -m framework.pricing_probe           # dry-run default
python -m framework.pricing_probe --apply   # 才真正改 YAML
python -m framework.pricing_probe --only zhipu
```

---

## 13. Workflows(`src/framework/workflows/`)

### 13.1 loader.py

```
def load_task_bundle(path: Path) -> tuple[Task, Workflow, list[Step]]
```

- UTF-8 读文件(**不**用 `json.load(open(...))`,Windows gbk 会 crash)
- JSON 解析后构造 Pydantic 对象
- `provider_policy.models_ref` 若存在,调 `ModelRegistry.resolve(alias)` 展开为 `prepared_routes`

### 13.2 templates/

workflow template library 占位目录(未启动)。

---

## 14. UE Scripts(`ue_scripts/`)

### 14.1 run_import.py

```
def run(run_folder: str | Path | None = None) -> None
```

- 通过 `FORGEUE_RUN_FOLDER` env 或参数传入
- `manifest_reader.discover_bundle(folder)` 读 manifest / plan / evidence 三件套
- `topological_ops(plan)` 拓扑排序
- 按 op.kind 分发到 domain handler
- 每个 op 完成 append 一条 Evidence

### 14.2 domain handler 签名

```
def import_texture_entry(unreal_module, bundle, op, entry) -> dict  # evidence fields
def import_static_mesh_entry(unreal_module, bundle, op, entry) -> dict
def import_audio_entry(unreal_module, bundle, op, entry) -> dict
```

- 第一参数 `unreal` 模块,允许 stub 单测(`test_p4_ue_scripts_run_import_with_stub_unreal`)

### 14.3 evidence_writer.append

原子追加(临时文件 + rename),避免半行写入。

### 14.4 manifest_reader

```
def discover_bundle(folder: Path) -> Bundle
def topological_ops(plan: UEImportPlan) -> list[UEImportOperation]
```

拓扑排序:Kahn 算法,入度为 0 的 op 依次弹出。

---

## 15. 关键算法详述

### 15.1 DAG cascade cancel(orchestrator.arun)

```
tasks = { step_id: asyncio.create_task(execute_step(s)) for s in ready }
done, pending = await asyncio.wait(tasks.values(), return_when=FIRST_EXCEPTION)
for exc_task in done:
    if exc_task.exception():
        for p in pending:
            p.cancel()
        raise exc_task.exception()
```

**不变量**:任一异常立即 cancel siblings + re-raise,不留孤儿任务。

**retry_same_step 修复**:done.discard(current) 允许同 step 重入(§5.1)。

### 15.2 Range 续传强校验(_download_async.chunked_download_async)

见 §6.6。**失守场景**(修复前):CDN/代理忽略 Range 回 200 全量,buf 非空时被直接 `buf.extend(chunk)` → 坏图 / 坏 GLB 静默落盘,`ValidationRecord` 只检查 bytes_nonempty 失守。

### 15.3 URL ranking + fallthrough(mesh_worker._one)

```
urls = _rank_hunyuan_3d_urls(raw)  # 桶序 (strong, ok, key, other, zip)
if not urls:
    raise MeshWorkerUnsupportedResponse(...)  # 不重提重计费

last_unsupported = None
last_download_err = None
for u in urls:
    remaining = budget_s - (time.monotonic() - start)
    if remaining <= 0:
        raise MeshWorkerTimeout(...)
    try:
        return await _download_and_validate(u, min(90, remaining))
    except MeshWorkerUnsupportedResponse as e:
        last_unsupported = e
    except MeshWorkerError as e:
        last_download_err = e

if last_download_err:
    raise last_download_err       # fallback_model 重试(换 model 有价值)
raise last_unsupported             # abort_or_fallback
```

### 15.4 mesh format 检测 + magic gate(_build_candidate)

```
fmt = _detect_mesh_format(data)
if fmt == "glb" and data[:4] != b"glTF":
    raise MeshWorkerUnsupportedResponse("bytes not glTF magic")
if fmt == "gltf":
    obj = json.loads(data)
    if _gltf_has_external_geometry(obj):
        raise MeshWorkerError("external buffers")
    missing_materials = _gltf_has_external_images(obj)
elif fmt == "fbx" or ...
```

**双保险**:parse-fail 的 glTF,`_is_self_contained_gltf` 返回 False,`_gltf_has_external_geometry` 返回 True,即使进 geometry_only 分支也会 raise。

### 15.5 EventBus 跨线程 hop(event_bus.publish_nowait)

见 §10.1。

### 15.6 Failure classify(failure_mode_map.classify)

**分类顺序**(关键):

```
1. unsupported 子类先捕获(避免被通用 Error 吞)
2. timeout 类
3. schema 类
4. budget 类(合成 Exception)
5. worker_error / provider_error 通用
6. disk_full
7. 其他 → raise 原样(不分类异常)
```

### 15.7 Hunyuan n>1 真并发

```
async def aimage_generation(self, call, n=1):
    if n == 1:
        return await self._one(call)
    return await asyncio.gather(*[
        self._one(_clone_with_seed(call, i)) for i in range(n)
    ])
```

tokenhub 单次只接一条 prompt,硬伪造 `raw["n_requested"]` 会让 `GenerateImageExecutor` 默认 `num_candidates=3` 的路径静默降级为 1 候选。

### 15.8 Review cost 透传 3-tuple

```
# ProviderAdapter
async def astructured_with_usage(self, call, schema) -> tuple[BaseModel, dict]:
    ...returns (obj, usage)

# CapabilityRouter
async def structured(self, capability, call, schema) -> tuple[BaseModel, str, dict]:
    obj, usage = await adapter.astructured_with_usage(call, schema)
    usage = _stash_route_pricing_on_usage(usage, route_pricing)
    return obj, adapter.model, usage

# ReviewExecutor
obj, model, usage = await router.structured(...)
cost = tracker.estimate_call_cost_usd(usage, model, route_pricing=usage.get("_route_pricing"))
step.metrics["cost_usd"] = cost
```

---

## 16. 异常类族总览

```
Exception
├── ProviderError
│   ├── ProviderUnsupportedResponse
│   └── ProviderTimeout
├── WorkerError
│   ├── WorkerUnsupportedResponse
│   ├── WorkerTimeout
│   └── MeshWorkerError
│       ├── MeshWorkerUnsupportedResponse
│       └── MeshWorkerTimeout
├── RegistryReferenceError         # ModelRegistry 解析
├── BundleLoadError                # Workflow loader
├── CheckpointMismatchError        # resume hash 不对
├── BudgetExceededError(合成)     # BudgetTracker
└── DryRunValidationError           # DryRunPass
```

`pydantic.ValidationError` 保持原生,由 `failure_mode_map` 分类为 `schema_validation_fail`。

---

## 17. 附录

### 17.1 字段级真源

本文档所有字段定义的真源是:

- `src/framework/core/*.py`(Pydantic schema + docstring)
- `src/framework/schemas/*.py`(业务 schema)
- `src/framework/providers/base.py`(异常类族)

### 17.2 算法真源

- `src/framework/runtime/orchestrator.py` — DAG 调度 / 生命周期
- `src/framework/runtime/failure_mode_map.py` — 分类
- `src/framework/providers/workers/mesh_worker.py` — URL ranker / 格式检测 / magic gate
- `src/framework/providers/_download_async.py` — Range 续传
- `src/framework/observability/event_bus.py` — 跨线程 hop

### 17.3 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0 | 2026-04-22 | 初始基线,从 plan_v1 §B + §C.6 + §D + §E + §F + §H + §N + 源码实装拆分重组 |
| v1.1 | 2026-04-22 | Codex 21 条 audit 修复落实装契约:§5.4 find_hit 长度校验 + cost_usd 持久化 + ArtifactRepository 跨进程持久化(`_artifacts.json`)+ payload tampering 校验、§5.5 `on_retry` override + `cloned_for_run()` per-arun 隔离(ADR-006)、§5.6 cache-hit 回放规则、§5.7.1 unsupported 三层拦截(transient retry / router fallback / executor `_should_retry`)、§5.x SelectExecutor bare-approve 语义 + GenerateImageEdit cost_usd + parallel_candidates 同质性、§6.2 router fallback 异常分流、§6.4 hunyuan poll timeout clamp + 200/non-JSON 包装。回归 520 用例(基线 491 + `tests/unit/test_codex_audit_fixes.py` 29 个 fence)|
