# UE 生产链多模型框架 —— Repo-Informed 方案修订 v2

## Context

这是对 v1 独立方案（纯自研骨架）的 **repo-informed 修订**。

**修订触发点**：
1. v1 未参考任何开源项目，虽然概念自洽，但未回答「自研 vs 复用」这个关键问题。
2. 已存在基线文档（`docs/UE_Multi_Model_Framework_Repo_Mapping_and_Execution_Plan.md` 及其 4 份子设计）给出了 17 个候选项目与既定对象模型（Task/Run/Workflow/Step/Artifact/CandidateSet/Verdict/TransitionPolicy）。v2 必须在 benchmark 的基础上给出统一的修订结论，并与基线对象模型对齐。
3. 用户明确要求：**不直接拼装 + 不简单照抄** + **必须写清借鉴点 / 不借鉴点 / 风险 / 替代方案**。

**修订结论（先行）**：
- **主骨架不直接用 LangGraph 作底座，但借鉴其 StateGraph 模型。** 自研一层薄薄的 DAG/StateGraph 引擎，以锁死 `Task/Run/Workflow/Step/Artifact/Verdict` 的一等地位与 Artifact 驱动语义。
- **Provider 层直接用 LiteLLM。** 这一层没有复杂业务语义，自研等于浪费时间。
- **结构化输出用 Instructor**（而非 PydanticAI），避免与自研 Workflow 引擎争抽象层。
- **评审 rubric / 裁决模板借鉴 judges**，但 Verdict → TransitionPolicy 的映射自研。
- **多模态子链以"外部工作流"方式挂载（ComfyUI / AudioCraft / TRELLIS / TripoSR）**，不纳入主引擎生命周期。
- **UE Bridge 全自研**，只读 VibeUE / Autonomix / BlenderMCP / UE5-MCP 的实现思路，不引入其运行时。

---

## A. 开源项目能力映射表

**评分方法**：对每个项目沿四个能力轴（basic_llm / production workflow / nested review / UE-Blender bridge）独立打分，再单列一列「能否作底座」的判断。不沿用基线文档的评分，重新独立评估。

| 项目                          | basic_llm | production | nested review | UE/Blender bridge |          能否作底座          | 我的判断                                                     |
| ----------------------------- | :-------: | :--------: | :-----------: | :---------------: | :--------------------------: | ------------------------------------------------------------ |
| **LangGraph**                 |     ◯     |     ◎      |       ◎       |         ✗         | 可作主骨架参考，不直接当底座 | StateGraph + Checkpointer + Interrupt 模型非常贴合"production + nested review"，但 Python 生态 + Pydantic + LangChain 级联依赖会把我们锁死在一条技术栈上。**借鉴其语义，自研薄骨架**。 |
| **Microsoft Agent Framework** |     ◯     |     ◯      |       ◯       |         ✗         |            不建议            | .NET 优先、仍在演进、UE 侧无任何契合点。可作为"企业编排"参考，不投入。 |
| **AG2 / CrewAI**              |     ✗     |     ◯      |       ◯       |         ✗         |            不建议            | 以"Agent 会话"为一等公民，与 Artifact-first 范式不合。我们的核心对象不是对话，是产物。 |
| **LiteLLM**                   |     ◎     | ◎（间接）  |   ◎（间接）   |         ✗         |    **直接作 Provider 层**    | 100+ provider 统一、retry / fallback / budget / cost logging 齐全。自研等于纯粹造轮子。 |
| **Instructor**                |     ◎     |     ◯      |       ◯       |         ✗         |    **直接作结构化输出层**    | Pydantic-based、retry-on-validation-fail、与任何 provider 兼容（含 LiteLLM）。适合 basic_llm 模式主力与生产流中的 generate/validate 节点。 |
| **PydanticAI**                |     ◎     |     ◯      |       ✗       |         ✗         |            不建议            | 同时提供 Agent + Workflow 抽象，与 LangGraph 互相内卷。若采用，要么放弃 LangGraph 借鉴，要么双抽象叠加。选 Instructor 更清爽。 |
| **judges**                    |     ✗     |     ◯      |       ◎       |         ✗         |    **评审 rubric 参考库**    | 30+ 已研究的 judge/jury 模式。适合抽 rubric & scoring 维度做参考。裁决→流程控制的映射仍自研。 |
| **llm-council**               |     ✗     |     ✗      |       ◎       |         ✗         |          仅思路参考          | Demo 性质，多阶段 deliberation 流值得读，代码不值得拉。      |
| **ComfyUI**                   |     ✗     |     ◎      |       ◯       |         ✗         |   **图像子系统，外部挂载**   | 节点图 + 社区 workflow 资源极丰富。以"API / headless 模式"挂在主引擎外，输入 prompt spec，输出 Artifact。**不**作主骨架，节点图语义与我们的 DAG 不是同一层抽象。 |
| **Diffusers**                 |     ✗     |     ◎      |       ✗       |         ✗         |          代码级补充          | 当 ComfyUI 不够灵活时直接用 diffusers 做特定 pipeline。维护成本：高。 |
| **AudioCraft**                |     ✗     |     ◎      |       ✗       |         ✗         |        **音频子系统**        | MusicGen / AudioGen 是目前开源最强组合。推理资源重，作为独立 worker 进程。 |
| **TRELLIS**                   |     ✗     |     ◎      |       ◯       |         ✗         |        **图→3D 主选**        | text/image → 3D 质量目前最强的开源选项。研究项目特质：API 稳定性、工程化不足，需要自建 worker 封装层。 |
| **TripoSR**                   |     ✗     |     ◎      |       ✗       |         ✗         |        图→3D 快速备选        | 单图快速重建，速度优势明显，质量略逊 TRELLIS。与 TRELLIS 互为 fallback。 |
| **Autonomix**                 |     ✗     |     ◯      |       ◯       |  ◎（UE 内执行）   |        **仅思路参考**        | UE 编辑器内 AI 执行插件，带审计/撤销，方向与我们相反（我们做 UE 外框架）。但**审计 + 撤销 + 动作清单**的设计值得全盘借鉴。 |
| **VibeUE**                    |     ◯     |     ◎      |       ◯       |         ◎         |     **UE 内能力面参考**      | UE 域服务拆分、MCP 工具层、Python 桥。问题：需要 VibeUE API key。参考其**领域分层**（材质/蓝图/关卡/资产），不接入其运行时。 |
| **BlenderMCP**                |     ✗     |     ◎      |       ◯       |   ◎（Blender）    |     **Blender 中转参考**     | 若走 image→3D→Blender 清理→UE 流程，这是必读。安全边界要守死（不开放任意代码执行）。 |
| **UE5-MCP**                   |     ✗     |     ◯      |       ◯       |         ◎         |        **仅思路参考**        | 端到端 Blender↔UE5 MCP 管线的早期尝试，方向对但工程化不够。  |

**符号**：◎ = 核心适配；◯ = 局部借鉴；✗ = 不适用。

**独立判断 vs 基线文档的关键不同**：
1. 基线把 LangGraph 标为"核心骨架"，我**降级为"骨架参考"**——直接用会绑死 Python + LangChain 生态，对 UE 生产链来说是过重承诺。
2. 基线把 ComfyUI 标为"生产主力"，我定位为**外挂子系统**——它的节点图与我们的 DAG 不是同一层，混用会让两套 workflow 概念打架。
3. 基线把 Autonomix 标为"UE 执行桥核心参考"，我降级为**仅审计/撤销思路参考**——它是 UE 内插件，我们是 UE 外框架，方向不同。

---

## B. 与 v1 独立方案的差异

### B.1 架构层差异

| 维度          | v1（独立）                   | v2（repo-informed）                                          |
| ------------- | ---------------------------- | ------------------------------------------------------------ |
| Provider 抽象 | 自研 Adapter 层              | **直接用 LiteLLM**                                           |
| 结构化输出    | 自研 Schema 校验 Transformer | **Instructor + 自研 validation hook**                        |
| 评审引擎      | 纯自研 Reviewer + Gate       | 自研 ReviewNode 骨架 + **借鉴 judges 的 rubric 模板**        |
| 多模态生成    | 模型作 Adapter 直调          | **外部 worker（ComfyUI/AudioCraft/TRELLIS）+ 自研调用封装**  |
| UE Bridge     | 文件落地 + manifest 两阶段   | 同方向，**+ 借鉴 Autonomix 的审计/撤销 + 借鉴 VibeUE 的域服务拆分** |

### B.2 对象模型差异（与基线 v1 文档对齐）

| v1 独立方案                                            | 基线文档                                                     | v2 修订                     | 理由                                                         |
| ------------------------------------------------------ | ------------------------------------------------------------ | --------------------------- | ------------------------------------------------------------ |
| `Node`                                                 | `Step`                                                       | **采用 `Step`**             | 基线文档已扎根；`Node` 在图论里有更多重含义。                |
| `Node.role ∈ {Generator, Transformer, Reviewer, Gate}` | `Step.type ∈ {generate, transform, review, select, merge, validate, export, import, retry, branch, human_gate}` | **采用基线枚举集**          | 基线集更贴近 UE 生产链真实节点类型；`Gate` 拆分成 `review` + `TransitionPolicy` 更清晰。 |
| 无 `CandidateSet`                                      | `CandidateSet`                                               | **引入 `CandidateSet`**     | review/select 是围绕多候选展开的，v1 把这层隐式化是错的。    |
| `Verdict.decision ∈ {approve, revise, reject}`         | 9 种 decision                                                | **扩展到 9 种**             | UE 生产链的失败恢复路径（fallback_model / rollback / human_review_required）必须显式表达。 |
| `Policy`                                               | `TransitionPolicy`                                           | **采用 `TransitionPolicy`** | 名字更准确——它驱动的是"转移"而不是泛指"策略"。               |
| 无 `ProviderRef/ModelRef/CapabilityRef`                | 预留这三个引用                                               | **保留预留位**              | 方便 LiteLLM 接入时不改对象模型。                            |

### B.3 执行语义差异

| 语义                    | v1           | v2                                                           |
| ----------------------- | ------------ | ------------------------------------------------------------ |
| 先读后写 / Dry-run Pass | ✅ 独创       | **保留**，并新增"UE 工程路径策略预检"——参考 Autonomix 的 manifest 预审思路 |
| 风险分级调度            | ✅ 独创       | **保留**                                                     |
| Checkpoint + hash       | ✅ 独创       | **保留**；LangGraph 的 Checkpointer 模型验证了这个思路在社区层面是主流，不是我想太多 |
| 多模态节点调用          | 自研 Adapter | **改为"外部 worker 协议"**：ComfyUI / AudioCraft / TRELLIS 以 HTTP / 子进程方式作独立 worker，主引擎只发任务+收 Artifact |

### B.4 UE Bridge 差异

| 维度         | v1                                         | v2                                                           |
| ------------ | ------------------------------------------ | ------------------------------------------------------------ |
| 边界         | 单向写 + 文件+清单                         | **保留**                                                     |
| 阶段         | F-0 文件落地 / F-1 清单驱动 / F-2 事件通道 | **F-0 保持；F-1 新增"审计日志 + rollback hook"（借 Autonomix）；F-2 推迟** |
| UE 内脚本    | UE Editor Utility / Python                 | **保留**，**参考 VibeUE 域服务拆分**（texture / mesh / material / audio 四个域各一个导入 handler） |
| 写路径优先级 | 未细化                                     | **明确分级**：导入资源文件 → 元数据 → 材质/音频绑定 → 受控资产容器 → 蓝图/关卡（基线文档 §Phase 6） |

---

## C. 需要修正的对象模型

以下是 v1 对象模型在 v2 中需要的五点修订，**直接指向实现时的类/schema 定义**。

### C.1 `Step` 代替 `Node`，扩充 `Step.type` 枚举

```
Step.type ∈ {
  generate     # 产出 Artifact
  transform    # Artifact → Artifact
  review       # Artifact/CandidateSet → Verdict
  select       # 基于 Verdict 做候选选择
  merge        # 多个 Artifact 合并
  validate     # schema/format/UE-rule 校验
  export       # 产出 UE Manifest 或外部交付物
  import       # 从外部系统读入 Artifact（UE 项目、外部素材库）
  retry        # 显式重试节点
  branch       # 显式分支节点
  human_gate   # 人工介入节点
}
```

**v1 的 Gate 角色**：不作为 Step.type，而是通过 `review → TransitionPolicy` 的组合实现。这样 Gate 就从"对象"降级为"关系"，避免对象膨胀。

### C.2 引入 `CandidateSet` 作为一等公民

```
CandidateSet {
  candidate_set_id
  source_step_id
  artifact_ids        # 成员候选
  selection_goal      # 人类可读说明
  selection_constraints
}
```

**为什么必须一等公民**：review/select 的输入不是单个 Artifact，而是"候选集合 + 选择目标"。把它隐式化会让 review 的 rubric 评分、selected/rejected 分流、dissent 记录都没处挂。

### C.3 扩展 `Verdict.decision` 到 9 种

```
decision ∈ {
  approve, approve_one, approve_many, reject, revise,
  retry_same_step, fallback_model, rollback, human_review_required
}
```

加 `scores`（多维评分）、`dissent`（异议保留）、`recommended_next_step_id`（直接建议转移目标）。

### C.4 `TransitionPolicy` 替代 `Policy`

```
TransitionPolicy {
  on_success, on_reject, on_revise, on_retry, on_fallback, on_rollback, on_human,
  max_retries, max_revise, timeout_sec, budget_cap
}
```

决策从"node.policy"提到"step.transition_policy"层级，使所有节点的流转规则统一定义，而不是分散在各 Reviewer/Gate 里。

### C.5 预留 `ProviderRef / ModelRef / CapabilityRef`

```
Step {
  ...
  provider_ref   # 指向 LiteLLM 配置中的某个 provider
  model_ref      # 具体模型标识
  capability_ref # 能力类别（text / image_gen / audio_gen / image_to_3d / judge）
}
```

**目的**：同一种 `generate` step，在文本/图像/音频/3D 场景下由不同 capability 执行。capability 与 step.type 解耦，避免"generate_image / generate_audio"这种业务枚举污染。

---

## D. 需要保留的原创设计

v1 方案里以下几点与任何开源项目都不冲突，且对 UE 场景有独特价值——**保留**。

### D.1 两段式 artifact type 命名（`<modality>.<shape>`）
虽然基线文档用的是扁平枚举（`concept_image / music_track / mesh_asset`），但两段式更利于：
- dispatch 路由（按 modality 路由 worker）
- 未来扩展（新增 `mesh.usd` 不用改核心）
- 校验模板映射

**方案**：基线枚举作为 **外部显示名**，两段式作为 **内部类型**。二者一一映射。

### D.2 payload_ref 三态（inline / file / blob）

Artifact 不内联二进制，统一走 `PayloadRef`。对 UE 资产链（图、音、3D 都是大文件）尤为重要。基线文档没有这一层设计，必须加入。

### D.3 风险分级调度 + Dry-run Pass

同层节点按 `risk_level` 升序执行；整个 Run 启动前跑一次零副作用预检。**这是我对"先读后写、先低风险后高风险"原则的工程化**，基线文档只提原则未给执行机制。保留并写入 Scheduler 合约。

### D.4 Checkpoint + content hash 缓存

每个 Step 完成后持久化 `{step_id, artifact_hashes}`，resume 时按 hash 命中即复用。LangGraph 的 Checkpointer 验证了这套思路，但**我们要的是 UE 资产级别的幂等**，不是 LLM token 级别——**仍需自研**，不直接用 LangGraph 的 Checkpointer（存储格式与对象模型不匹配）。

### D.5 UE Bridge 分阶段边界（F-0 / F-1 / F-2）

F-0（只落文件+清单）、F-1（UE 侧脚本读清单导入）、F-2（事件通道）三阶段切得很干净，且与 Autonomix/VibeUE 的实现思路正交。**保留**，在 F-1 阶段融入 Autonomix 的审计/回滚机制。

---

## E. 推荐的组合式架构

### E.1 整体分层

```
┌─────────────────────────────────────────────────────────────┐
│ Task Entry / Mode Router                                    │
│   basic_llm / production / standalone_review                │
├─────────────────────────────────────────────────────────────┤
│ Orchestration Engine（自研，薄骨架）                         │
│   Manifest 解析 → Run → DAG 调度 → Checkpoint + Dry-run      │
│   借鉴：LangGraph StateGraph / Checkpointer 语义             │
├─────────────────────────────────────────────────────────────┤
│ Step Executors（自研接口 + 外部实现挂载）                     │
│   ├── generate (text)    → Instructor + LiteLLM             │
│   ├── generate (image)   → ComfyUI worker（HTTP API）        │
│   ├── generate (audio)   → AudioCraft worker（子进程/HTTP）  │
│   ├── transform (img→3d) → TRELLIS/TripoSR worker           │
│   ├── review             → 自研 ReviewNode + judges rubric   │
│   ├── validate           → 自研（schema + UE rule）          │
│   └── export             → 自研（UE Manifest 产出）          │
├─────────────────────────────────────────────────────────────┤
│ Provider Layer                                              │
│   LiteLLM（100+ provider + fallback + budget）              │
├─────────────────────────────────────────────────────────────┤
│ Artifact Store                                              │
│   自研（PayloadRef 三态：inline / file / blob）              │
├─────────────────────────────────────────────────────────────┤
│ UE Bridge（自研，单向写）                                    │
│   F-0 文件+清单落地                                          │
│   F-1 UE 内脚本（参考 VibeUE 域服务分层）+ 审计日志（参考 Autonomix）│
│   F-2 事件通道（推迟）                                       │
└─────────────────────────────────────────────────────────────┘
```

### E.2 各组件的「借 vs 自研」决策表

| 组件                     | 方案                          | 借鉴点                                                      | 不借鉴点                                    | 主要风险                                          | 替代方案                                                     |
| ------------------------ | ----------------------------- | ----------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------ |
| **Orchestration Engine** | 自研（参考 LangGraph）        | StateGraph 状态传递、Checkpointer、Interrupt-for-human 语义 | LangChain 生态 / LCEL / 它的 Message 抽象   | 自研成本高；语义错配                              | 退路：直接用 LangGraph，包一层自研 adapter 对齐 Step/Artifact |
| **Provider Layer**       | 直接用 LiteLLM                | 全部                                                        | —                                           | LiteLLM 版本跳变大，需锁版本                      | 退路：自研 thin provider router（成本极高，不建议）          |
| **basic_llm 主力**       | Instructor + LiteLLM          | Pydantic 绑定、retry-on-validation                          | 无                                          | Instructor 生态略薄                               | 退路：PydanticAI（需放弃 LangGraph 借鉴）                    |
| **Review Engine**        | 自研骨架 + judges rubric 参考 | judges 的 rubric 库、scoring 维度定义                       | 它的 executor（我们已有自研 Step Executor） | rubric 语义要求 UE 领域特化，通用 judges 可能不贴 | 退路：多阶段 deliberation 参考 llm-council                   |
| **图像 worker**          | ComfyUI（headless API）       | 它的节点图资产、社区 workflow                               | 用它作主编排（冲突）                        | ComfyUI workflow 可复用性不稳                     | 退路：Diffusers 纯代码 pipeline                              |
| **音频 worker**          | AudioCraft                    | MusicGen / AudioGen 模型                                    | 无                                          | 推理资源重，需独立 GPU 资源治理                   | 退路：商业 API（Suno / Elevenlabs）                          |
| **3D worker**            | TRELLIS + TripoSR 双栈        | 两者都用，作 fallback 对                                    | 无                                          | 研究项目工程化不足，需自建封装                    | 退路：Blender + 手工 pipeline                                |
| **UE Bridge**            | 全自研                        | Autonomix 审计/回滚思路、VibeUE 域服务分层                  | 两者的运行时                                | UE 版本跨度大，脚本要分版本维护                   | 退路：走 BlenderMCP → UE 的中转链路                          |

### E.3 必须自研的部分（不可复用）

以下能力在开源生态中**没有直接可用方案**，必须自研：

1. **三模式 Mode Router**：basic_llm / production / standalone_review 语义切换。
2. **Artifact Contract + PayloadRef**：两段式 type 命名、三态 payload ref、UE 友好元数据。
3. **Verdict → TransitionPolicy 映射**：9 种 decision 与流程转移规则的桥接。
4. **CandidateSet 概念与 review 输入模型**：judges 库只提供裁决，不提供候选集管理。
5. **Risk-level 调度 + Dry-run Pass**：任何开源框架都没有这层。
6. **UE Manifest + Import Plan**：UE 领域独有。
7. **审计 + rollback hook**：Autonomix 的模式要在 UE 外框架里重新实现。
8. **Run 级别的可审计追溯链**（artifact → step → provider → verdict → ue asset path）。

---

## F. MVP 实施建议

**核心原则**：
- 先读后写、先低风险后高风险——基线文档已锁死。
- 每个 Phase 必须有一个**端到端可运行的 Demo**，不做"半成品堆叠"。
- **先对齐对象模型，再引入开源项目**——避免被外部项目的概念模型反向污染。

### Phase 0 — 对象模型与骨架（2-3 周，纯自研）

**目标**：把 §C 的对象模型落成 Pydantic schemas，跑通最小的 `Run` 调度器骨架。

**范围**：
- Pydantic models：`RunMode / Task / Run / Workflow / Step / Artifact / CandidateSet / Verdict / TransitionPolicy`
- `Artifact PayloadRef` 三态实现
- Run 调度器骨架：DAG 拓扑 + 状态机 + Dry-run Pass
- 本地 FS 做 Artifact Store

**验收**：能跑一个纯 mock 的 3-step DAG，所有对象落库、可回放。

### Phase 1 — basic_llm 模式（1-2 周，引入 LiteLLM + Instructor）

**目标**：`basic_llm` 模式跑稳结构化输出。

**范围**：
- LiteLLM 接入（至少 OpenAI + Anthropic + Gemini）
- Instructor 作 `generate(type=structured)` 的主力执行器
- `validate` step：schema 失败自动 retry
- `Task.review_policy` 可声明"无需评审"，让 basic_llm 单步通过

**验收**：给定一个 UE 角色概念 schema，稳定产出符合 schema 的 JSON。

### Phase 2 — standalone_review（1-2 周，引入 judges rubric）

**目标**：独立评审链跑通，不涉及生产流。

**范围**：
- `CandidateSet` + `review` step + `Verdict`
- 借 judges 的 rubric 模板（至少 `pairwise / rubric-scoring / jury`）
- 单主审 + 多陪审混合模式

**验收**：给定 3 个候选方案 JSON，输出 Verdict（selected + dissent + scores）。

### Phase 3 — production workflow（2-3 周，引入 ComfyUI）

**目标**：production 模式跑通文本→图像双模态，不嵌 review。

**范围**：
- ComfyUI headless worker + 调用封装
- `generate(type=image)` step 实现
- Risk-level 调度启用（image 标 medium，text 标 low）
- Checkpoint + hash 缓存

**验收**：`prompt → 结构化 image spec → ComfyUI 出图 → Artifact 带完整 lineage`。

### Phase 4 — Nested Review（1-2 周，核心需求）

**目标**：review 嵌入 production，revise 回环 + 次数上限。

**范围**：
- `TransitionPolicy` 驱动的分支
- revise 回环计数
- 多维 scoring
- 失败恢复策略（fallback_model / rollback）

**验收**：图像生成 → review 打回 → 回环重生成 → 最终通过。完整可追溯。

### Phase 5 — UE Bridge F-0 + F-1（2-3 周，参考 VibeUE 域服务）

**目标**：产物落到 UE 工程，可被 UE 侧脚本导入。

**范围**：
- UE Manifest + Import Plan 生成
- 文件落到 `Content/Generated/<run_id>/`
- UE 侧 Python 脚本（texture / static_mesh / sound_wave 三个域）
- 审计日志 + rollback hook（仅文件级，不触 UE 内部状态）

**验收**：Run 完成后，UE 侧脚本一次执行把资产导入对应目录并记录审计日志。

### Phase 6 — 音频 + 3D 生产链（3-4 周，引入 AudioCraft + TRELLIS）

**目标**：多模态全面支持。

**范围**：
- AudioCraft worker（MusicGen BGM）
- TRELLIS + TripoSR worker（image → mesh）
- asset_kind 扩展到 sound_wave / static_mesh
- Bundle 打包

**验收**：一次 Run 同时产出文本 + 图像 + 音频 + mesh，UE 侧完成批量导入。

### Phase 7 — 评测与运行管理（2 周）

**目标**：可复现、可对比、可审计。

**范围**：
- Run Registry（所有 Run 的输入/中间产物/Verdict/最终输出）
- Artifact 版本对比
- 多条生产链的对比报告

**验收**：给定同一 Task，跑两次不同模型组合，能自动产出对比报告。

### 明确推迟到 MVP 之后
- F-2 事件通道（UE ↔ 框架 实时通知）
- 分布式 worker 调度
- Manifest include/模板继承
- UE 内蓝图/关卡写操作
- 反向 UE 控制（UE 主动调度框架）
- 可视化 DAG 编辑器

---

## 关键参考文件

- `docs/UE_Multi_Model_Framework_Repo_Mapping_and_Execution_Plan.md` — 开源项目清单与基线执行计划（本方案的 benchmark 依据）
- `docs/UE_Three_Mode_Framework_Object_Model_Definition_v1.md` — 基线对象模型（本方案 §C 对齐基线）
- `docs/Production_Workflow_Nested_Review_Design_v1.md` — Nested Review 设计（本方案 §F Phase 4 对齐）
- `docs/Artifact_Contract_and_UE_Asset_Manifest_Design_v1.md` — Artifact / Manifest 设计（本方案 §C.1–C.5 对齐）
- `docs/UE_Bridge_Minimal_Runnable_Implementation_Plan_v1.md` — UE Bridge MVP（本方案 §F Phase 5 对齐）
- `docs/UE_Multi_Model_Framework_Object_Model_and_Runtime_Design_v1.md` — 基线 runtime 设计

## 验证方式

- 每个 Phase 结束前产出 **一条可复现命令 + 一份 Run 快照**（Task + Workflow + Artifacts + Verdicts），作为回归基线。
- Phase 5 的验证在一个**空白 UE 5.x 工程**内完成：运行框架 → 执行 UE 内脚本 → 资产出现在 Content Browser 且审计日志可追溯。
- Phase 7 完成后，全套系统应能重放任意历史 Run，产物 hash 一致。

## 一句话结论

**v2 不是"直接拼装开源项目"，也不是"纯自研"，而是"自研薄骨架 + 外挂成熟组件 + UE 领域层全自研"。LiteLLM / Instructor 这种无业务语义的基础设施直接用；LangGraph / judges / ComfyUI 这种有自己抽象的成熟组件借鉴思路不接运行时；UE 侧与 Artifact 契约这种领域特化的能力，必须自研且不可妥协。**