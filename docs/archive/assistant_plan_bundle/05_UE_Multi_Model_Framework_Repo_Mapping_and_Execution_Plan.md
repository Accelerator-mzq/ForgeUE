# UE 多模型框架：可借鉴能力映射表与执行方案 v1

## 0. 文档目的

本文基于你的真实需求整理：

1. **普通 LLM Client 模式**：输入任务，稳定返回结构化数据。
2. **生产模式**：多模型协作生成文本、图片、音乐、图转资产等中间产物，并可继续流转到后续节点。
3. **评审模式**：可独立运行，也可**嵌套在生产流程内部**，作为质量闸门（Review Gate / Review Node）。
4. **UE 落地**：最终结果不是停留在聊天文本里，而是要进入 Unreal Engine 的资产、蓝图、材质、音频或项目配置链路。

结论先行：

- **GitHub 上没有一个单体开源项目能完整覆盖你的三种模式 + UE 落地。**
- 更可行的方案是：**“一个主编排骨架 + 一个统一 Provider 层 + 一个结构化输出层 + 一个评审层 + 多模态生产子链 + UE Bridge 层”**。
- 也就是说，这不是“选一个 repo 直接开干”，而是“选一组 repo 分层借鉴，再做你的统一框架”。

---

## 1. 你的框架应该长什么样

### 1.1 三种顶层运行方式

- **Basic LLM Mode**
  - 目标：拿到结构化结果
  - 产物：JSON / YAML / schema 化字段 / Spec Fragment

- **Production Mode**
  - 目标：拿到可继续流转的产物
  - 产物：文本方案、图片、音乐、资产描述、图转 3D 结果、UE 导入清单

- **Standalone Review Mode**
  - 目标：比较多个候选结果，裁决并生成最终结论
  - 产物：打分、排序、异议、最终裁决

### 1.2 关键修正：Review 不是只能独立运行

你的核心需求是：

> **生产模式中允许嵌套评审模式。**

所以更准确的架构不是三个互斥模式，而是：

```text
Framework
├── Basic LLM Mode
├── Production Mode
│   ├── Generate Step
│   ├── Transform Step
│   ├── Review Node
│   ├── Select Node
│   ├── Retry / Branch / Approve / Reject
│   └── Finalize to UE-ready Output
└── Standalone Review Mode
```

---

## 2. 可借鉴能力映射表（按你的三种模式 + UE 落地）

> 说明：
> - “适合”表示值得作为主要参考。
> - “可借鉴”表示适合作为局部能力参考。
> - “不建议作为核心底座”表示可以读，但不适合作为你的主骨架。

| Repo | 主要定位 | 普通模式 | 生产模式 | 嵌套评审 | UE 落地 | 借鉴等级 | 建议怎么用 | 主要注意点 |
|---|---|---:|---:|---:|---:|---|---|---|
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | 状态化、长流程、图式 AI 编排 | 可借鉴 | **适合** | **适合** | 间接 | **核心骨架** | 作为你的主 Workflow/Graph Engine | 不自带 UE 专属能力，需要你自己定义节点与协议 |
| [microsoft/agent-framework](https://github.com/microsoft/agent-framework) | Python/.NET 多智能体与图式工作流 | 可借鉴 | **适合** | **适合** | 间接 | 重要备选 | 如果你想更靠近 .NET / 企业式工作流，可重点参考 | 新、变化快，UE 侧仍需自建桥接层 |
| [ag2ai/ag2](https://github.com/ag2ai/ag2) | 多智能体协作与 agent OS | 可借鉴 | 可借鉴 | 可借鉴 | 间接 | 备选 | 适合参考多 Agent 协作模式 | 更偏 agent conversation，不如 LangGraph 贴合“生产图 + 审查节点” |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | 多角色 AI 协作与流程 | 可借鉴 | 可借鉴 | 可借鉴 | 间接 | 备选 | 适合参考角色化分工 | 更偏 crew/role 思维，不是你最核心的需求中心 |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | 统一多 Provider 调用 / Router / Fallback | **适合** | **适合** | **适合** | 间接 | **核心基础层** | 统一接 OpenAI / Anthropic / Gemini / OpenRouter 等 | 适合做网关与统一接口，不负责工作流语义 |
| [567-labs/instructor](https://github.com/567-labs/instructor) | 结构化输出 / Pydantic 验证 | **适合** | 可借鉴 | 可借鉴 | 间接 | **核心基础层** | 用于普通模式的稳定 schema 输出 | 偏结构化输出层，不是流程引擎 |
| [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | 强类型 AI Agent / Workflow | **适合** | 适合 | 可借鉴 | 间接 | 重要备选 | 适合“结构化输出 + 图式工作流”统一思路 | 若同时上 LangGraph，需避免双重抽象过厚 |
| [quotient-ai/judges](https://github.com/quotient-ai/judges) | LLM Judge / Jury / 裁决库 | 可借鉴 | 可借鉴 | **适合** | 间接 | **评审核心层** | 作为 Review Engine 的核心参考 | 偏 judge 组件，不是全流程框架 |
| [karpathy/llm-council](https://github.com/karpathy/llm-council) | 多模型回答 + 互评 + Chairman 总结 | 可借鉴 | 不适合 | **适合** | 不适合 | 思路参考 | 学它的多阶段评审流 | 更像样板/演示，不建议当生产骨架 |
| [comfy-org/ComfyUI](https://github.com/comfy-org/ComfyUI) | 图像生成节点图 / 流程图系统 | 不适合 | **适合** | 可借鉴 | 间接 | **图像生产核心参考** | 图像工作流子链、候选图批量生成 | 适合当图像子系统，不适合当总编排器 |
| [huggingface/diffusers](https://github.com/huggingface/diffusers) | 图像/视频/音频扩散模型工具箱 | 不适合 | **适合** | 不适合 | 间接 | 重要补充 | 作为代码级多模态生成底座 | 更偏算法工具箱，非最终产品式工作流 |
| [facebookresearch/audiocraft](https://github.com/facebookresearch/audiocraft) | 音频处理与音乐/音效生成 | 不适合 | **适合** | 可借鉴 | 间接 | **音频生产核心参考** | 场景音乐、SFX 草案生成 | 推理较重，需单独资源治理 |
| [microsoft/TRELLIS](https://github.com/microsoft/TRELLIS) | text/image -> 3D assets | 不适合 | **适合** | 可借鉴 | 间接 | **图转 3D 关键参考** | 图片到 3D 资产分支的关键候选 | 质量、速度、资产可用性需要你自己验收 |
| [VAST-AI-Research/TripoSR](https://github.com/VAST-AI-Research/TripoSR) | 单图快速 3D 重建 | 不适合 | **适合** | 可借鉴 | 间接 | 重要补充 | 做 image-to-3D 快速重建支线 | 更像重建工具，不替代完整资产流程 |
| [PRQELT/Autonomix](https://github.com/PRQELT/Autonomix) | UE 编辑器内 AI 执行插件 | 不适合 | 可借鉴 | 可借鉴 | **适合** | **UE 执行桥核心参考** | 参考 UE 编辑器内动作执行、审计、撤销 | 更像执行器，不是外部 orchestrator |
| [kevinpbuckley/VibeUE](https://github.com/kevinpbuckley/VibeUE) | UE 编辑器内 AI Chat + MCP + Python 服务 | 可借鉴 | **适合** | 可借鉴 | **适合** | **UE 能力面参考** | 参考 UE 域服务拆分、skills、MCP 接口 | 需要 VibeUE API key 才能启用 MCP/AI Chat 关键能力 |
| [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) | Blender MCP 控制桥 | 不适合 | **适合** | 可借鉴 | 间接 | 重要补充 | 作为 Blender 中转层、资产预处理桥 | 需严控安全边界和可执行代码能力 |
| [VedantRGosavi/UE5-MCP](https://github.com/VedantRGosavi/UE5-MCP) | Blender + UE5 端到端 MCP 管线思路 | 不适合 | 可借鉴 | 可借鉴 | **适合** | 思路参考 | 参考 Blender->UE5 资产流转思路 | 更适合参考方向，不建议直接做骨架 |

---

## 3. 我对这些 repo 的最终归类

### 3.1 你最应该优先看的“核心骨架组”

这组最接近“能拼出你的框架”：

1. **LangGraph**
2. **LiteLLM**
3. **Instructor** 或 **PydanticAI**
4. **judges**

这四个分别解决：

- 图式生产编排
- 多 provider 调用统一
- 结构化输出
- 评审 / 裁决

### 3.2 你最应该优先看的“生产子链组”

1. **ComfyUI**：图像生成/图像工作流子系统
2. **AudioCraft**：音乐 / SFX 子系统
3. **TRELLIS / TripoSR**：图 -> 3D / 资产子系统
4. **Diffusers**：代码级扩展生成能力

### 3.3 你最应该优先看的“UE 桥接组”

1. **Autonomix**：UE 编辑器内执行桥思路
2. **VibeUE**：UE 域服务、MCP、Python 服务拆分方式
3. **BlenderMCP**：Blender 中转桥
4. **UE5-MCP**：Blender + UE5 端到端流转参考

### 3.4 只建议看思路，不建议当核心底座

1. **llm-council**
2. **UE5-MCP**

原因不是它们没价值，而是：

- 一个更像评审样板
- 一个更像方向性实验/集成思路

都不适合作为你整套框架的主骨架。

---

## 4. 推荐的总体技术路线

## 4.1 最推荐的拼装方式

```text
[User / Task Input]
        ↓
[Task Classifier / Mode Router]
        ↓
+---------------------------+
|   Basic LLM Mode          |
|   - LiteLLM               |
|   - Instructor/PydanticAI |
+---------------------------+
        ↓
+---------------------------+
|   Production Workflow     |
|   - LangGraph             |
|   - Generate / Transform  |
|   - Review Nodes          |
|   - Select / Retry        |
+---------------------------+
        ↓
+---------------------------+
|   Multimodal Workers      |
|   - ComfyUI               |
|   - AudioCraft            |
|   - TRELLIS / TripoSR     |
|   - Diffusers             |
+---------------------------+
        ↓
+---------------------------+
|   Review Engine           |
|   - judges                |
|   - custom rubrics        |
|   - optional llm-council  |
+---------------------------+
        ↓
+---------------------------+
|   UE / Blender Bridge     |
|   - UE plugin layer       |
|   - Autonomix/VibeUE refs |
|   - BlenderMCP refs       |
+---------------------------+
        ↓
[UE-ready Output / Asset Package / Reports]
```

---

## 5. 执行方案（建议按阶段推进）

> 这里不写“多久完成”，只写顺序和产物。

### Phase 0：先锁死边界，不先写大而全代码

#### 目标
把你的框架对象模型先定义清楚，避免后面写成巨大 if-else。

#### 必须先定义的核心对象

- `RunMode`
  - `basic_llm`
  - `production`
  - `standalone_review`

- `Task`
  - 这次任务要做什么

- `Artifact`
  - 文本、JSON、图片、音频、3D、UE 资源描述

- `Workflow`
  - 一组步骤与依赖关系

- `Step`
  - `generate`
  - `transform`
  - `review`
  - `select`
  - `retry`
  - `branch`
  - `approve`
  - `reject`

- `CandidateSet`
  - 多个候选结果的集合

- `Verdict`
  - 评审后的结论

- `TransitionPolicy`
  - 通过、回退、重试、换模型、人工确认的策略

#### 产物
- 框架对象定义文档
- JSON Schema / Pydantic Models
- Workflow DSL 草案

---

### Phase 1：先把普通模式做稳

#### 目标
做出一个真正可用的 **Basic LLM Mode**，作为三种模式的基础层。

#### 推荐实现
- Provider：**LiteLLM**
- Schema：**Instructor** 或 **PydanticAI**

#### 能力范围
- 文本问答
- 结构化抽取
- 任务拆解
- 规划输出
- Spec / metadata / asset manifest 生成

#### 关键要求
- 强制 schema 输出
- 自动重试
- 输出校验失败可回退重发
- 保存原始响应 + 解析后响应

#### 产物
- `basic_llm_client.py`
- `schemas/`
- `providers/`
- `response_validators/`

---

### Phase 2：独立评审模式先跑通

#### 目标
在不接 UE、不接多模态复杂链的前提下，先把 **Standalone Review Mode** 跑通。

#### 推荐实现
- Judge core：**judges**
- 流程参考：**llm-council**

#### 最小闭环
1. 多个模型独立回答
2. 统一转成 `Candidate` schema
3. 进入 `ReviewNode`
4. 输出 `Verdict`
5. 生成最终结论

#### 建议裁决输出结构

```json
{
  "final_answer": "...",
  "selected_candidates": ["cand_b"],
  "rejected_candidates": ["cand_a", "cand_c"],
  "dissent_summary": ["..."],
  "confidence": 0.82,
  "needs_human_review": false
}
```

#### 产物
- `review_engine/`
- `judge_rubrics/`
- `review_policies/`
- `standalone_review_runner.py`

---

### Phase 3：生产模式主链先做“无 UE 写入”版本

#### 目标
先做外部生产链，不急着直接改 UE 项目。

#### 为什么这样做
如果一上来就把“生成 + 评审 + UE 写入”全绑死，调试成本会急剧上升。

#### 推荐第一批工作流

##### Workflow A：文本 -> 图片候选 -> 评审 -> 选图
- 文本模型出图片 prompt / style spec
- ComfyUI / Diffusers 生成候选图
- ReviewNode 比较候选图
- 输出选中图与评审报告

##### Workflow B：文本 -> 音乐候选 -> 评审 -> 选曲
- 文本模型出风格标签、节奏、情绪
- AudioCraft 生成音乐草案
- ReviewNode 做筛选
- 输出被选中版本与报告

##### Workflow C：图片 -> 3D 候选 -> 评审 -> 选资产
- 选中概念图
- TRELLIS / TripoSR 做图转 3D
- ReviewNode 检查可用性
- 输出资产与报告

#### 产物
- `workflows/image_pipeline/`
- `workflows/audio_pipeline/`
- `workflows/image_to_3d_pipeline/`
- `artifact_store/`

---

### Phase 4：把 Review Node 真正嵌进 Production Workflow

#### 目标
落实你最核心的需求：**生产模式中嵌套评审模式。**

#### 关键不是“能评审”，而是“评审影响流转”

每个 Review Node 不能只出评论，还必须决定：

- 进入下一步
- 回退上一步
- 当前步骤重试
- 更换模型
- 并行保留两个分支
- 转人工确认

#### 推荐的 `Verdict` 结构

```json
{
  "decision": "approve | reject | retry | branch | escalate",
  "score": 0.0,
  "reason": "...",
  "selected_candidates": ["..."],
  "retry_with": {
    "model": "...",
    "params": {}
  },
  "next_transition": "step_x"
}
```

#### 产物
- `review_nodes/`
- `transition_engine/`
- `candidate_selector/`
- `branch_manager/`

---

### Phase 5：接 UE Bridge，但先做“只读 / 低风险动作”

#### 目标
开始接 Unreal Engine，但先走低风险路径。

#### 优先做的 UE 能力
- 读取项目结构
- 读取资产信息
- 读取日志
- 读取地图 / 蓝图元信息
- 读取配置
- 生成导入清单
- 生成资产命名建议

#### 主要参考
- **VibeUE**：Python 服务拆分、MCP 工具层、域能力组织
- **Autonomix**：编辑器内执行与审计/撤销思路

#### 产物
- `ue_bridge/read_only/`
- `ue_asset_manifest/`
- `ue_project_inspector/`

---

### Phase 6：再接 UE 写路径，但必须做“可审计、可回滚、可限制”

#### 目标
把生产结果真正推进到 UE 工程里。

#### 推荐原则
- **不要上来就给 AI 任意写 UE 项目。**
- 所有写操作都要经过：
  1. manifest
  2. review gate
  3. apply step
  4. audit log
  5. rollback hook

#### 写路径优先级建议
1. 导入资源文件
2. 生成/更新元数据
3. 绑定材质/音频资源
4. 创建受控资产容器
5. 最后才考虑更高风险的蓝图/关卡修改

#### 产物
- `ue_bridge/write_controlled/`
- `audit_logs/`
- `rollback/`
- `apply_manifests/`

---

### Phase 7：评测体系与运行管理

#### 目标
你的系统不是“能跑一次”，而是“多次运行可比较”。

#### 这一步特别重要
你前面的需求天然要求：

- 同一输入可产生多个候选版本
- 每次评审结果可追踪
- 多条生产链可比较
- UE 导入后可回看来源

#### 必须保存的东西
- 输入任务
- 每一步 prompt / schema / provider / 参数
- 每一步 artifact
- 每一次评审报告
- 最终 verdict
- 是否写入 UE
- 对应的 UE 资产路径

#### 产物
- `run_registry/`
- `artifact_versions/`
- `review_reports/`
- `comparison_reports/`

---

## 6. 我对你这套框架的最终落地建议

### 6.1 推荐的首选组合

#### 主骨架
- **LangGraph**

#### Provider 统一层
- **LiteLLM**

#### 普通模式结构化输出
- **Instructor**
- 或者 **PydanticAI**（若你想把强类型与工作流绑得更紧）

#### 评审层
- **judges**
- 参考 **llm-council** 的多阶段 deliberation 流

#### 图像生产
- **ComfyUI**
- 需要更细控制时补 **Diffusers**

#### 音频生产
- **AudioCraft**

#### 图转 3D
- **TRELLIS**
- **TripoSR**

#### UE / Blender 桥
- **Autonomix**
- **VibeUE**
- **BlenderMCP**
- **UE5-MCP**（作为思路参考）

---

## 7. 不建议的错误路线

### 错误路线 A：直接找一个“万能 repo”全盘照搬

问题：不存在真正覆盖你三模式 + UE 落地的单体 repo。

### 错误路线 B：先把所有外部模型和 UE 全打通，再补协议

问题：会迅速失控，难以调试。

### 错误路线 C：把评审当作附加功能

问题：你这里的评审不是“锦上添花”，而是生产流的质量闸门。

### 错误路线 D：把所有 UE 写操作直接开放给模型

问题：风险太高，必须 manifest + review + audit + rollback。

---

## 8. 最终建议：你的主线应该怎么选

如果只给一个最务实的实现路线，我建议是：

### 建议主线

1. **LangGraph** 做总编排骨架
2. **LiteLLM** 做 provider 统一层
3. **Instructor** 做普通模式强结构化输出
4. **judges** 做评审节点底座
5. **ComfyUI / AudioCraft / TRELLIS / TripoSR** 分别做图像、音频、图转 3D 子链
6. **参考 Autonomix + VibeUE** 做 UE Bridge
7. **参考 BlenderMCP + UE5-MCP** 做 Blender 中转与资产流转扩展

### 这条路线的优点

- 最贴合你的三种模式
- 最贴合“生产流可嵌套评审”的核心需求
- 最容易逐步实现，不必一次吃掉全部复杂度
- 最容易在 UE 领域逐步落地

---

## 9. 我建议你下一份配套文档该写什么

如果你继续往下推进，最应该马上补的是下面 4 份：

1. **《UE 三模式统一框架对象模型定义 v1》**
   - RunMode / Task / Workflow / Step / Artifact / Verdict / TransitionPolicy

2. **《Production Workflow + Nested Review 机制设计 v1》**
   - ReviewNode 怎么嵌到生产流里

3. **《Artifact Contract 与 UE Asset Manifest 设计 v1》**
   - 图片、音乐、3D、导入清单、元数据怎么统一表示

4. **《UE Bridge 最小可运行实现方案 v1》**
   - 先读后写、先低风险后高风险的实现边界

---

## 10. 参考仓库链接清单

### 核心骨架 / 路由 / 结构化 / 评审
- LangGraph: https://github.com/langchain-ai/langgraph
- Microsoft Agent Framework: https://github.com/microsoft/agent-framework
- AG2: https://github.com/ag2ai/ag2
- CrewAI: https://github.com/crewAIInc/crewAI
- LiteLLM: https://github.com/BerriAI/litellm
- Instructor: https://github.com/567-labs/instructor
- PydanticAI: https://github.com/pydantic/pydantic-ai
- judges: https://github.com/quotient-ai/judges
- llm-council: https://github.com/karpathy/llm-council

### 多模态生产子链
- ComfyUI: https://github.com/comfy-org/ComfyUI
- Diffusers: https://github.com/huggingface/diffusers
- AudioCraft: https://github.com/facebookresearch/audiocraft
- TRELLIS: https://github.com/microsoft/TRELLIS
- TripoSR: https://github.com/VAST-AI-Research/TripoSR

### UE / Blender 桥接
- Autonomix: https://github.com/PRQELT/Autonomix
- VibeUE: https://github.com/kevinpbuckley/VibeUE
- BlenderMCP: https://github.com/ahujasid/blender-mcp
- UE5-MCP: https://github.com/VedantRGosavi/UE5-MCP

---

## 11. 一句话结论

**最适合你的不是“某个单一 repo”，而是一套分层组合：LangGraph + LiteLLM + Instructor/PydanticAI + judges + 多模态生产子链 + UE Bridge。**

这套组合比“找一个万能开源项目”更符合你现在的真实需求，也更适合做成真正面向 Unreal Engine 游戏生产链的统一多模型框架。
