# UE 生产链多模型框架 —— 架构评审与统一方案 vNext

## Context

作为架构评审员，逐项比较两组方案：

- **A. Claude 独立方案**（docs/claude_independent_plan_v1.md / 亦即先前 v2 repo-informed 修订稿）
- **B. assistant 方案包**（docs/assistant_plan_bundle/ 下 6 份 v1 文档）
  - 01 三模式统一对象模型
  - 02 Production 内嵌 Review 设计
  - 03 Artifact Contract 与 UE Manifest
  - 04 UE Bridge 最小实现
  - 05 开源项目映射与执行计划
  - 06 对象模型与运行时设计

输出目标：不选边站、指明重复造轮子点、指明必须自研点、给出合并后的 vNext。

---

## A. 一致项（两边实质相同，可直接纳入 vNext 基线）

| #    | 主题                 | 两边共识                                                     |
| ---- | -------------------- | ------------------------------------------------------------ |
| 1    | 顶层运行模式         | `basic_llm / production / standalone_review` 三模式作入口语义 |
| 2    | 一等公民             | `Task / Run / Workflow / Step / Artifact / Verdict` 为核心对象；message 不是 |
| 3    | Review 地位          | 既是顶层 RunMode，也是 production workflow 内的合法 Step.type |
| 4    | Verdict 驱动         | Verdict 不只是评语，必须驱动流程转移                         |
| 5    | Artifact Lineage     | 必须保留上游依赖链，支持回放与回滚                           |
| 6    | 先读后写             | 写入前必须预检                                               |
| 7    | 先低风险后高风险     | UE Bridge 分阶段，先只读/轻量导入，再涉及已有资产修改        |
| 8    | Manifest 先于 Bridge | 先产出 UE Asset Manifest，Bridge 再消费                      |
| 9    | MVP 推迟项           | 复杂 DAG / 人工 UI / 任意蓝图与关卡写操作都放后期            |
| 10   | 开源项目不选单体     | 都承认不存在覆盖"三模式 + UE 落地"的单体项目                 |

这 10 条是**无争议基线**，vNext 直接沿用。

---

## B. 差异项（逐项对比，按维度分列）

### B.1 顶层运行模式

| 维度                        | Claude                       | assistant                                                    | 评估                                                       |
| --------------------------- | ---------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| RunMode 枚举                | 同                           | 同                                                           | 一致                                                       |
| TaskType                    | 未显式建模，合进 Task.intent | 显式字段（question_answer / workflow_production / review / ue_export 等） | **assistant 更完整**：意图与策略分离，便于 Dispatcher 路由 |
| TaskType ↔ RunMode 组合关系 | 未定义                       | §3 给出映射示例                                              | assistant 有；Claude 无                                    |

### B.2 Production 内嵌 Review 机制

| 维度                     | Claude                                 | assistant                                                    | 评估                                                         |
| ------------------------ | -------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 内嵌方式                 | Reviewer + Gate 组合                   | Step(type=review) + TransitionPolicy                         | **命名冲突**：Claude 的 Gate 在 assistant 中不存在（逻辑等价但结构不同） |
| review_mode              | 只提"多 Reviewer 并联 + 聚合"          | 明确 4 种（single_judge / multi_judge / council / chief_judge） | **assistant 更完整**                                         |
| review_report vs verdict | 合并在 Verdict（字段 reasons/dissent） | 分离为两对象（report 是分析，verdict 是决策）                | **assistant 更清晰**：分析与控制解耦                         |
| 多维 scoring             | Verdict.scores 字段（无维度指导）      | 5 维度（constraint_fit / style_consistency / production_readiness / technical_validity / risk_score） | **assistant 给出 UE 领域专门维度**                           |
| revise 回环上限          | Policy.max_revise 显式                 | Workflow 级 retry 与 review 的回环隐式                       | **Claude 更严格**                                            |
| 失败分支 recovery        | Gate 聚合                              | RecoveryReview 专门节点类型                                  | **assistant 更清晰**                                         |

### B.3 Artifact Contract / Manifest

| 维度                                | Claude                                                       | assistant                                                    | 评估                                                         |
| ----------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| artifact_type 命名                  | 两段式 `<modality>.<shape>`（`image.raster / mesh.gltf`）    | 扁平枚举（`concept_image / texture_image / mesh_asset`）     | **命名冲突**：两段式扩展性更强；扁平枚举在 UE 领域更直白     |
| Payload 抽象                        | PayloadRef 三态（inline / file / blob）                      | `uri` + `inline_data` 两字段                                 | **Claude 更抽象且可扩展**；assistant 字段组合略 ad-hoc       |
| Artifact.role                       | 只 `intermediate/finalized` 隐式区分                         | 显式枚举（intermediate / final / reference / rejected）      | **assistant 更完整**                                         |
| Candidate 建模                      | CandidateSet 作为 Artifact 的 bundle 子类型                  | CandidateSet + Candidate **双层建模**（Candidate 带 score_hint/notes/source_model） | **对象模型冲突**：assistant 双层明确，Claude 丢失"候选位"语义 |
| UE Manifest 结构                    | 提纲式（assets/import_rules/naming_policy/path_policy/dependencies） | 同方向，但字段更细（target_object_path / target_package_path / ue_naming / import_options / metadata_overrides） | **assistant 更可落地**                                       |
| ue_asset_manifest vs ue_import_plan | 未区分                                                       | 分离：前者声明式，后者执行式                                 | **assistant 正确**：声明与执行解耦，便于 dry-run             |
| UEOutputTarget 前置                 | 无；UE 目标放在 export step.config                           | Task 层显式 `ue_target`，贯穿全流程                          | **流程边界冲突**：assistant 让前端节点就知道 UE 目标，避免后期命名/目录/分辨率不对齐 |

### B.4 UE Bridge 边界

| 维度          | Claude                                                       | assistant                                                    | 评估                  |
| ------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | --------------------- |
| Bridge 定位   | **单向投递器**：只写文件+清单，UE 侧脚本自行导入；Bridge 不触 UE | **UE 执行器**：validate/dry-run/execute 全链，直接用 Python Editor Scripting 调 UE API | **流程边界重大冲突**  |
| 阶段划分维度  | 按"交互形态"：F-0 文件落地 / F-1 清单驱动 / F-2 事件通道     | 按"权限范围"：Phase A 只读 / B 低风险导入 / C 低风险关联 / D 高风险编辑 | 两种维度互补，不冲突  |
| 权限颗粒度    | 未显式细化                                                   | 每类操作一个 flag（allow_create_folder / allow_import_texture / allow_modify_existing_assets） | **assistant 更完整**  |
| 工具分层      | 未分层                                                       | Inspect / Plan / Execute 三类工具                            | **assistant 更完整**  |
| Evidence 对象 | 仅讲审计日志                                                 | 每操作返回结构化 Evidence（源路径 / UE 目标路径 / 状态 / log_ref） | **assistant 更完整**  |
| Rollback      | 仅讲"回滚 hook"                                              | 给出最小策略（记录已创建对象 / 失败停后续 / 输出人工清理清单） | **assistant 更具体**  |
| 审计借鉴来源  | 借 Autonomix 思路                                            | 独立设计                                                     | 相似方向              |
| UE 版本耦合   | 边界锁在文件+清单，UE 侧脚本随版本自维护                     | Python Scripting 依赖 UE 版本 API                            | **Claude 解耦更彻底** |

### B.5 开源项目借鉴策略

| 项目                           | Claude 策略                                                  | assistant 策略                       | 评估                                                         |
| ------------------------------ | ------------------------------------------------------------ | ------------------------------------ | ------------------------------------------------------------ |
| LangGraph                      | **仅借鉴 StateGraph 语义**，自研薄骨架（理由：LangChain 生态锁定） | **作主骨架直接用**                   | **借鉴策略冲突**：assistant 更务实（直接用省时），Claude 更保守（避免生态绑死） |
| LiteLLM                        | 直接用                                                       | 直接用                               | 一致                                                         |
| Instructor                     | 直接用（明确选它而非 PydanticAI）                            | Instructor 或 PydanticAI 二选一      | **Claude 更果断**                                            |
| judges                         | 仅借鉴 rubric 模板                                           | 仅借鉴思路                           | 一致                                                         |
| ComfyUI                        | 外部 worker 挂载（headless API）                             | 作子链组件（也建议独立化）           | 同方向                                                       |
| AudioCraft / TRELLIS / TripoSR | 外部 worker                                                  | 子链                                 | 同方向                                                       |
| Autonomix                      | **仅审计/撤销思路**（因是 UE 内插件方向相反）                | **作 UE 执行桥核心参考**             | **借鉴策略冲突**                                             |
| VibeUE                         | 借鉴域服务分层（texture/mesh/material/audio）                | 借鉴 UE 域服务、MCP、Python 服务拆分 | 同方向                                                       |
| BlenderMCP                     | 仅参考思路                                                   | 作 Blender 中转桥                    | assistant 更积极                                             |

### B.6 运行时语义（Claude 原创部分）

| 特性                      | Claude                                          | assistant                                           | 评估                                                 |
| ------------------------- | ----------------------------------------------- | --------------------------------------------------- | ---------------------------------------------------- |
| Step.risk_level           | 显式分级（low/medium/high），同层按风险升序调度 | 未涉及                                              | **Claude 原创合理**：把"先低风险后高风险"原则工程化  |
| Run 级 Dry-run Pass       | 显式阶段（零副作用预检）                        | 仅 UE Bridge 层有 dry_run_import                    | **Claude 原创合理**：Run 级预检覆盖面更广            |
| Checkpoint + content hash | Step 完成后持久化 hash，resume 按 hash 命中     | Run.current_step_id + logs，无 hash 缓存            | **Claude 原创合理**：UE 资产级幂等性对大资产至关重要 |
| Policy 类型数             | 只 TransitionPolicy                             | 5 类（Transition/Retry/Provider/Budget/Escalation） | **assistant 更完整**                                 |
| ProviderPolicy 独立对象   | 无（provider 放 adapter 层）                    | §4.10 独立建模                                      | **assistant 更灵活**：能力路由与 fallback 集中管理   |

---

## C. Claude 方案优于 assistant 方案的地方（必须坚持自研的部分）

以下 5 点是 Claude 方案的原创合理点，**vNext 必须坚持**：

1. **PayloadRef 三态抽象（inline / file / blob）**
   - 理由：assistant 的 `uri + inline_data` 并列字段在大资产（图/音/mesh）场景会反复判断边界；三态统一。
   - 替代方案：保留 `uri / inline_data` 作为字段级兼容写法，但逻辑上收敛到 PayloadRef。

2. **两段式 artifact_type 命名（`<modality>.<shape>`）**
   - 理由：扁平枚举每增加新类型（如 `mesh.usd / image.exr`）都要改核心；两段式按 modality 路由 worker 更顺。
   - 替代方案：assistant 的扁平枚举作**外部显示名**（用户友好），两段式作**内部类型**（dispatch 用），一一映射。

3. **Step.risk_level + 风险分级调度**
   - 理由：assistant 只讲"先低风险后高风险"原则，没有执行机制；Claude 直接落成 Step 属性 + 调度规则。
   - 替代方案：assistant 的 Bridge Phase A/B/C/D 分级是"资源权限"维度，Claude 的 risk_level 是"节点属性"维度，两者**互补**不冲突。

4. **Run 级 Dry-run Pass**
   - 理由：assistant 只在 UE Bridge 有 dry_run_import；Claude 在 Run 启动前跑一次零副作用预检（解析 Manifest / 校验 Schema / 检查 Adapter 可达 / 预判 UE 路径冲突）——覆盖面更广。
   - 替代方案：保留 Run 级 Dry-run Pass，UE Bridge 的 dry_run_import 作为 Pass 中的一个子 check。

5. **Checkpoint + content hash 缓存**
   - 理由：UE 资产生产是大文件、长耗时；hash 级幂等能避免重跑生成。assistant 的 Run.status + logs 不支持精确 resume。
   - 替代方案：LangGraph 的 Checkpointer 验证了社区认可，但存储格式与对象模型不匹配，必须自研。

6. **对开源项目的"借鉴点 / 不借鉴点 / 风险 / 替代方案"四栏决策**
   - 理由：assistant 的 Repo Mapping 给推荐级别，但不明确"能借鉴什么、不能借鉴什么"；Claude 的四栏更能防御被生态绑死。
   - 替代方案：vNext 中保留这套决策表，将 assistant 的推荐列表作为输入。

7. **UE Bridge 的"单向写"边界（文件+清单，Bridge 不触 UE）**
   - 理由：assistant 的 Bridge 直接 Python Editor Scripting 调 UE API，UE 版本耦合强、进程耦合强；Claude 的单向投递让 UE 侧脚本与框架解耦。
   - **注意**：此点与 assistant 的 Phase B/C 有根本分歧——见 §E 第 1 点的统一建议。

---

## D. assistant 方案优于 Claude 方案的地方（必须采纳）

以下 11 点是 assistant 的原创合理点，**vNext 必须采纳**：

1. **TaskType 与 RunMode 显式分离**
   - Claude 未显式建模 TaskType；assistant §3.2 让意图（task_type）与策略（run_mode）解耦。
   - vNext 采纳。

2. **UEOutputTarget 在 Task 层前置声明**
   - Claude 把 UE 目标放在 export step.config，可能让前端节点分辨率/命名/目录不对齐；assistant §4.11 让前置知道 UE 目标。
   - vNext 采纳。

3. **CandidateSet + Candidate 双层建模**
   - Claude 把 CandidateSet 作 Artifact bundle，丢失"候选位"语义（每候选的 source_model、score_hint、notes）；assistant §4.6 双层明确。
   - vNext 采纳。

4. **review_report 与 verdict 分对象**
   - Claude 把评论塞在 Verdict.reasons/dissent，分析与控制耦合；assistant 让分析归 report、决策归 verdict。
   - vNext 采纳。

5. **ReviewNode 的 review_mode 4 分类**
   - Claude 只说"多 Reviewer 并联"；assistant 显式 single_judge / multi_judge / council / chief_judge。
   - vNext 采纳。

6. **多维 scoring 维度（面向 UE 生产链）**
   - Claude 只给 `scores` 字段；assistant 给 5 维度（constraint_fit / style_consistency / production_readiness / technical_validity / risk_score）。
   - vNext 采纳。

7. **Policy Engine 完整性（5 类策略分离）**
   - Claude 只 TransitionPolicy；assistant 分 Transition / Retry / Provider / Budget / Escalation。
   - vNext 采纳（但 Claude 的 max_revise 保留为 TransitionPolicy 字段）。

8. **ProviderPolicy 独立对象**
   - Claude 把 provider 配置藏在 adapter 层；assistant §4.10 让 capability 路由 + fallback 集中。
   - vNext 采纳。

9. **UE Bridge 的权限策略颗粒度**
   - Claude 未细化；assistant 每类操作一个 allow_flag。
   - vNext 采纳。

10. **UE Bridge 的 Inspect / Plan / Execute 工具三层**
    - Claude 无此分层；assistant 让只读能力、计划能力、执行能力分工。
    - vNext 采纳。

11. **Evidence 对象**
    - Claude 仅讲审计日志；assistant 给结构化 Evidence（源路径 / UE 路径 / 状态 / log_ref）。
    - vNext 采纳。

12. **ue_asset_manifest vs ue_import_plan 分离**
    - Claude 未区分；assistant 让声明与执行分对象。
    - vNext 采纳。

13. **具体的 framework/ 目录结构**
    - Claude 只给高层边界；assistant §9 给 core/runtime/providers/review_engine/artifact_store/ue_bridge/workflows/schemas。
    - vNext 采纳（但部分命名可微调）。

---

## E. 两边都遗漏或不足的地方（vNext 必须新增）

| #    | 主题                                     | 两边现状                                                     | vNext 必须补                                                 |
| ---- | ---------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 1    | **UE Bridge 的"单向写 vs 直接执行"分歧** | Claude 主张单向写；assistant 主张直接执行                    | 折中：MVP 采用 **F-0 单向写 + UE 侧脚本执行**；Phase C/D 成熟后可选接入 Python Editor Scripting 的**可选 Execute 通道**（但必须过 Inspect → Plan → Execute 三层且有 Evidence） |
| 2    | **Artifact 多版本演化**                  | 同一逻辑 Artifact 有多版本（原始/压缩/LOD/变体）的命名与索引 | 引入 `artifact_lineage.variant_group_id` + `variant_kind`，避免版本散落 |
| 3    | **Workflow 模板继承与复用**              | 多 Task 共用链骨架时重复定义                                 | 引入 `workflow_template` 概念（v2 后置）                     |
| 4    | **长时推理资源治理**                     | 多 Run 并发时 GPU 分配/配额/优先级未提                       | 引入 ResourceBudget（GPU/显存/时段），与 BudgetPolicy 联动   |
| 5    | **失败模式矩阵**                         | 零散列举（provider 超时/schema 失败/导入冲突/磁盘满）        | 建立 FailureMode ↔ Verdict.decision 映射表                   |
| 6    | **评测与基线回归**                       | 都讲"可保存"但无"如何对比"                                   | 引入 RunComparison（同 Task 多 Run 的指标对比）              |
| 7    | **Secrets / Credentials 管理**           | 都未涉及                                                     | LiteLLM 配置 + env 隔离 + 密钥轮换策略                       |
| 8    | **分布式追踪与 cost tracking**           | Claude 提 LiteLLM cost logging；跨 step trace 都未展开       | OpenTelemetry 风格的 trace_id 贯穿 Run → Step → Provider Call |
| 9    | **多租户/多项目隔离**                    | 都未提                                                       | Run 带 project_id；Artifact Store 与 UE Bridge 按 project 分目录 |
| 10   | **确定性与可复现性**                     | Claude 有 hash 缓存但无 seed 传递；assistant 仅讲 seed 元数据 | 引入 DeterminismPolicy（seed 传递链 + 模型版本锁 + hash 校验） |
| 11   | **Human-in-the-loop 协议**               | 都提 human_gate 但无标准化协议                               | HumanGate 需定义：通知机制、超时策略、断点恢复语义           |
| 12   | **Schema 演化策略**                      | Artifact Contract 有 schema_version 但未讲兼容规则           | 引入 Schema Registry + 向前兼容规则（加字段可/删字段不可）   |

---

## F. 推荐的统一架构原则（vNext 核心 10 条）

1. **三模式共享实现**：`basic_llm / production / standalone_review` 是入口语义，不是分裂实现。Orchestrator / Step Executor / Artifact Store 共享。

2. **TaskType 与 RunMode 显式分离**：意图归 task_type，策略归 run_mode；两者不混用。

3. **Artifact 是一等公民**，message 不是；**两段式 type 命名** + **PayloadRef 三态**；多版本用 variant_group_id 追踪。

4. **CandidateSet + Candidate 双层建模**；review 的标准输入是 CandidateSet 或单 Artifact。

5. **Review 是 Step.type，不是外挂**；`review_report`（分析）与 `verdict`（控制）分对象；4 种 review_mode；5 维 UE 专门 scoring。

6. **UEOutputTarget 在 Task 层前置**，前端节点就知道 UE 目标，保证命名/目录/分辨率全程对齐。

7. **五类 Policy 分离**（Transition / Retry / Provider / Budget / Escalation）+ `Step.risk_level` 属性；Scheduler 按风险升序执行同层节点。

8. **Run 级 Dry-run Pass + UE Bridge dry-run**：前者零副作用预检，后者操作前 dry-run；**Evidence First**：每操作返回结构化证据。

9. **UE Bridge 双模并存**：默认**单向写**（文件+清单，UE 侧脚本导入）；可选**Execute 通道**（Inspect → Plan → Execute 三层，过权限 allow_flag 与 Evidence）。

10. **开源项目三分类**：
    - **直接用**：LiteLLM（provider）、Instructor（structured output）
    - **借鉴不接运行时**：LangGraph（StateGraph 语义）、judges（rubric 模板）
    - **外部 worker 挂载**：ComfyUI / AudioCraft / TRELLIS / TripoSR
    - **仅思路参考**：Autonomix（审计/撤销）、VibeUE（UE 域服务分层）、BlenderMCP（中转桥思路）

---

## G. 统一后的 vNext 方案建议

### G.1 对象模型（合并 assistant 的 9 对象 + Claude 的 4 原创）

```
RunMode ∈ {basic_llm, production, standalone_review}

Task:
  task_id, task_type, run_mode, title, description,
  input, constraints, expected_output,
  review_policy, ue_target   # 前置 UEOutputTarget
  determinism_policy          # 新增：seed 传递 + 模型版本锁

Run:
  run_id, task_id, status, started_at, ended_at,
  workflow_id, current_step_id, artifacts[],
  checkpoints[],              # Claude 新增
  trace_id,                   # 新增：OTel 风格 trace
  project_id                  # 新增：多租户隔离

Workflow:
  workflow_id, name, version, steps[], entry_step, transition_policy
  template_ref                # v2 后置：模板继承

Step:
  step_id, type, name,
  provider_policy, retry_policy, transition_policy,
  risk_level,                 # Claude 新增：low/medium/high
  input_bindings, output_schema,
  capability_ref              # assistant：能力解耦

Step.type ∈ {
  generate, transform, review, select, merge, validate,
  export, import, retry, branch, human_gate, route
}

Artifact:
  artifact_id, artifact_type,   # 内部两段式 / 外部扁平名，一一映射
  role ∈ {intermediate, final, reference, rejected},
  payload_ref,                  # Claude 三态：inline / file / blob
  format, mime_type,
  producer (嵌套: run_id/step_id/provider/model),
  lineage (source_artifact_ids, variant_group_id, variant_kind),
  metadata, validation, tags

Candidate:
  candidate_id, artifact_id, source_step_id, source_model,
  score_hint, notes

CandidateSet:
  candidate_set_id, task_scope, candidate_ids[], selection_policy

ReviewNode:
  review_id, review_scope, review_mode, candidate_set_id,
  rubric (criteria/weights/thresholds), judge_policy,
  output_format = review_report + verdict

ReviewReport:                   # assistant：与 verdict 分离
  review_id, summary, scores_by_dimension, issues_per_candidate

Verdict:
  verdict_id, review_id,
  decision ∈ {approve, approve_one, approve_many, reject, revise,
              retry_same_step, fallback_model, rollback, human_review_required},
  selected_candidate_ids, rejected_candidate_ids,
  confidence, reasons, followup_actions,
  recommended_next_step_id

TransitionPolicy / RetryPolicy / ProviderPolicy / BudgetPolicy / EscalationPolicy   # 五类

UEOutputTarget:
  project_name, asset_root, asset_naming_policy,
  expected_asset_types, import_mode ∈ {manifest_only, bridge_execute},
  validation_hooks

UEAssetManifest:                # 声明式
  manifest_id, project_target, assets[],
  import_rules, naming_policy, path_policy, dependencies

UEImportPlan:                   # 执行式
  plan_id, manifest_id, operations[]  # 显式顺序

Evidence:                       # assistant：执行证据
  evidence_item_id, op_id, kind, status,
  source_uri, target_object_path, log_ref
```

### G.2 运行时分层

```
┌───────────────────────────────────────────────────────────┐
│ Mode Router（basic_llm / production / standalone_review）│
├───────────────────────────────────────────────────────────┤
│ Orchestrator                                              │
│   Manifest 解析 → Run → DAG 调度 → Dry-run Pass → 状态机   │
│   Checkpoint + hash 缓存 + trace_id 贯穿                   │
│   借鉴：LangGraph StateGraph 语义（不接运行时）            │
├───────────────────────────────────────────────────────────┤
│ Step Executors                                            │
│   generate (text)   → Instructor + LiteLLM                │
│   generate (image)  → ComfyUI worker（HTTP）              │
│   generate (audio)  → AudioCraft worker（子进程）         │
│   transform (3d)    → TRELLIS / TripoSR worker            │
│   review            → 自研 ReviewEngine + judges rubric    │
│   validate / export → 自研                                 │
├───────────────────────────────────────────────────────────┤
│ Policy Engine                                             │
│   Transition / Retry / Provider / Budget / Escalation     │
├───────────────────────────────────────────────────────────┤
│ Provider Layer                                            │
│   LiteLLM（100+ provider + fallback + budget/cost）       │
├───────────────────────────────────────────────────────────┤
│ Artifact Store                                            │
│   PayloadRef 三态 + variant_group_id + lineage            │
│   按 project_id 分目录（多租户隔离）                       │
├───────────────────────────────────────────────────────────┤
│ UE Bridge（双模并存）                                     │
│   默认：F-0 单向写（文件+清单，UE 侧脚本导入）             │
│   可选：Execute 通道（Inspect → Plan → Execute）          │
│   权限 allow_flag + Evidence First + Rollback hint         │
│   参考 VibeUE 域服务分层 + Autonomix 审计思路              │
└───────────────────────────────────────────────────────────┘
```

### G.3 目录结构（基于 assistant §9 + Claude 原创字段）

```
framework/
├── core/                    # 对象模型
│   ├── task.py / run.py / workflow.py / step.py
│   ├── artifact.py (PayloadRef / two-segment type / lineage)
│   ├── candidate.py / review.py / verdict.py
│   └── policies.py (5 类 Policy)
├── runtime/
│   ├── orchestrator.py
│   ├── scheduler.py (risk_level 排序)
│   ├── dry_run_pass.py (Claude 原创)
│   ├── checkpoint_store.py (hash 缓存)
│   └── transition_engine.py
├── providers/
│   ├── litellm_adapter.py
│   └── capability_router.py
├── review_engine/
│   ├── judges.py / rubric.py / council.py / chief_judge.py
│   └── report_verdict_emitter.py (分离输出)
├── artifact_store/
│   ├── repository.py / lineage.py / variant_tracker.py
│   └── payload_backends/ (inline/file/blob)
├── ue_bridge/
│   ├── manifest.py / import_plan.py / evidence.py
│   ├── inspect/ plan/ execute/  (assistant 三层工具)
│   ├── file_drop_adapter.py (Claude 单向写)
│   └── python_editor_adapter.py (可选执行通道)
├── workflows/
│   ├── basic/ production/ review/
│   └── templates/ (v2 后置)
├── observability/
│   ├── tracing.py / cost_tracker.py / run_comparison.py
└── schemas/
    ├── task / artifact / review / ue_manifest / evidence
```

### G.4 vNext MVP 路线（融合两边，5 个阶段，每阶段有端到端 Demo）

| Phase  | 目标                              | 引入的开源组件                                             | 端到端验收                                                   |
| :----: | --------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------ |
| **P0** | 对象模型与骨架                    | 纯自研（Pydantic）；LangGraph 仅语义参考                   | 3-step mock DAG，所有对象落库，Dry-run Pass 跑通             |
| **P1** | basic_llm 模式                    | **LiteLLM** + **Instructor**                               | 给定 UE 角色 schema，稳定产出 JSON（+ retry-on-validation）  |
| **P2** | standalone_review                 | 借鉴 **judges** rubric 模板                                | 3 候选方案 → ReviewReport + Verdict（含 5 维 scoring 与 dissent） |
| **P3** | production workflow + 内嵌 review | **ComfyUI** headless worker；风险调度启用；checkpoint+hash | prompt → 图像生成 → review 打回 → 回环 → 通过；完整 lineage  |
| **P4** | UE Bridge F-0 + 参考 VibeUE 分层  | UE 侧 Python 脚本（texture/mesh/sound_wave 三域）          | Run 完成后 UE 脚本一次执行把资产导入，含 Evidence 与审计日志 |
| **P5** | 多模态扩展                        | **AudioCraft / TRELLIS / TripoSR** 作外部 worker           | 一次 Run 同时产出文本+图像+音频+mesh，批量导入 UE            |

**明确推迟到 MVP 之后**：
- UE Bridge 的 Execute 通道（Python Editor Scripting 直调 UE）
- 任意 DAG / Workflow 模板继承
- 分布式 worker 调度
- 反向 UE 控制
- 可视化 DAG 编辑器
- 人工交互完整 UI（MVP 仅 CLI + 简单事件通知）

---

## H. 评审结论

1. **两份方案互补大于冲突**：Claude 强在运行时工程化（PayloadRef / risk_level / Dry-run / Checkpoint）与开源项目策略判断；assistant 强在对象模型完整度与 UE Bridge 细节。
2. **真正的架构分歧只有 1 处**：UE Bridge 是"单向写"（Claude）还是"直接执行"（assistant）。vNext 以**双模并存**解决——默认单向写保稳健，可选 Execute 通道满足高阶需求。
3. **重复造轮子点**：Claude 的 Adapter 层（被 assistant 的 ProviderPolicy + LiteLLM 替代）；Claude 的 Gate 角色（被 assistant 的 review + TransitionPolicy 替代）。vNext 按 assistant 模型为准。
4. **必须坚持自研的 5 点**（见 §C）：PayloadRef 三态 / 两段式 type / risk_level 调度 / Run 级 Dry-run / Checkpoint+hash——这是 Claude 对 UE 大资产生产链的原创工程化贡献，任何开源项目都未覆盖。
5. **必须采纳的 13 点**（见 §D）：以 assistant 的对象模型完整度为 vNext 的结构基线。
6. **必须新增的 12 点**（见 §E）：两边都未覆盖的工程治理短板，vNext 不能再缺。

**vNext 一句话定位**：
> **一套以 Task/Run/Workflow/Artifact 为核心、Review 为合法节点、UEOutputTarget 前置、双模 UE Bridge、五类 Policy 分离的多模型运行时；基础设施层（LiteLLM/Instructor）直接用；StateGraph 与 rubric 语义借鉴（LangGraph/judges）；多模态生成外挂（ComfyUI/AudioCraft/TRELLIS/TripoSR）；UE 领域与运行时工程化部分全自研。**