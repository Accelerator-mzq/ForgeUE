# AGENT_UE5 to ForgeUE 迁移设计

| 字段 | 内容 |
| --- | --- |
| 日期 | 2026-05-24 |
| 状态 | Draft for msc review |
| 范围 | 迁移 AGENT_UE5 中适合 ForgeUE 产品愿景的设计编译能力 |
| 本机 AGENT_UE5 源 | `D:\UnrealProjects\Mvpv4TestCodex` |

## 1. 背景

msc 对 ForgeUE 的目标不是“再做一个资产导入工具”，而是让用户把一份 GDD / 游戏设计文档交给 ForgeUE 后，系统能逐步生成高质量 playable demo。当前 ForgeUE 已具备多模型生成、Artifact 治理、Review、Workflow execution、Provider routing 和 EngineAdapter 交付底座；AGENT_UE5 则验证过一条从 GDD 到 UE5 playable template 的设计编译链。

本迁移的核心判断：

- AGENT_UE5 不应整库搬进 ForgeUE。
- 应迁移它的 Design Compiler 思路和契约层。
- UE5 C++ 插件、Monopoly demo、UE 路径命名、Bridge Passthrough 工具只作为参考，不作为 ForgeUE 主干依赖。

## 2. 事实来源

ForgeUE 当前事实：

- ForgeUE 是多引擎内容交付框架，核心 runtime 负责多模型生成、Artifact、Review、Workflow 和 Provider routing，具体引擎由 `EngineAdapter` 交付。
  证据：[README.md:5](/D:/ClaudeProject/ForgeUE_codex/README.md:5)
- ForgeUE 的核心对象是 `Task -> Run -> Workflow -> Step -> Artifact`。
  证据：[README.md:81](/D:/ClaudeProject/ForgeUE_codex/README.md:81)
- Engine Bridge 明确要求 `StepType.export` 通过 `EngineAdapter` 分发，不把具体引擎交付逻辑塞回 runtime。
  证据：[docs/design/HLD.md:118](/D:/ClaudeProject/ForgeUE_codex/docs/design/HLD.md:118)
- Godot 4 当前是 headless import MVP，说明 ForgeUE 已有跨引擎交付边界。
  证据：[docs/contracts/engine-export-bridge/spec.md:59](/D:/ClaudeProject/ForgeUE_codex/docs/contracts/engine-export-bridge/spec.md:59)

AGENT_UE5 当前事实：

- AGENT_UE5 的 Phase 11 主链是 `GDD -> Root Skill Contract -> Clarification Gate -> Skill Graph Planning -> Domain Skill Runtime -> Cross Review v2 -> Build IR v2 -> Reviewed Handoff v3 -> UE5 关卡 -> runtime evidence`。
  证据：[README.md:13](/D:/UnrealProjects/Mvpv4TestCodex/README.md:13)
- AgentBridge 把项目实例和通用机制分层：项目层保存输入、实例和治理；插件层提供通用编译、执行、验证框架。
  证据：[architecture_overview.md:73](/D:/UnrealProjects/Mvpv4TestCodex/Plugins/AgentBridge/Docs/architecture_overview.md:73)
- Root Skill Contract 是能力骨架和约束容器，不是 realization、Build IR 或 Handoff。
  证据：[root_skill_contract_standard.md:6](/D:/UnrealProjects/Mvpv4TestCodex/Plugins/AgentBridge/Docs/root_skill_contract_standard.md:6)
- Skill Graph 是“谁先做、谁关联、谁收敛优先”的规划产物，不是执行计划。
  证据：[skill_graph_and_domain_skill.md:6](/D:/UnrealProjects/Mvpv4TestCodex/Plugins/AgentBridge/Docs/skill_graph_and_domain_skill.md:6)
- Clarification Gate 把不确定性分成 explicit/default/discovery/required 四类，并允许 provisional 传播。
  证据：[clarification_gate_rules.md:9](/D:/UnrealProjects/Mvpv4TestCodex/Plugins/AgentBridge/Docs/clarification_gate_rules.md:9)
- AGENT_UE5 的实现当前有明显 Monopoly / UE5 耦合，不适合直接复制。
  证据：[root_skill_contract.py:76](/D:/UnrealProjects/Mvpv4TestCodex/Plugins/AgentBridge/Compiler/stages/root_skill_contract.py:76)、[skill_graph_planning.py:30](/D:/UnrealProjects/Mvpv4TestCodex/Plugins/AgentBridge/Compiler/stages/skill_graph_planning.py:30)、[lowering_v2.py:154](/D:/UnrealProjects/Mvpv4TestCodex/Plugins/AgentBridge/Compiler/stages/lowering_v2.py:154)

## 3. 产品定位

迁移后，ForgeUE 应新增一个上层产品能力：**Game Build Compiler**。

Game Build Compiler 的第一性原理：

1. GDD 不是执行计划，只是意图和约束来源。
2. 高质量 playable build 不是资产堆叠，而是玩法、UI、反馈、规则、引擎交付和可验证证据的闭环。
3. ForgeUE 当前最强的底座是 Workflow + Artifact + Review + EngineAdapter，所以新能力应把 GDD 编译成 ForgeUE 可消费的结构化产物，而不是绕过 runtime 直接写 UE/Godot 工程。

目标产品承诺分三层：

| 层级 | 用户感知 | 系统输出 |
| --- | --- | --- |
| L1 Game Build Plan | 丢 GDD，得到可审查 game build 方案 | `GameBuildContract` / `GameBuildGraph` / 资产清单 / 风险问题 |
| L2 Game Build Handoff | 丢 GDD，得到可执行交接物 | `GameBuildIR` / `GameBuildHandoff` / ForgeUE Workflow bundle 草案 |
| L3 Playable Slice | 丢 GDD，得到可运行 demo | EngineAdapter 产物 + runtime evidence + review report |

本迁移设计只覆盖 L1-L2 的基础形态，为 L3 留接口，不在第一阶段承诺完整 playable slice。

## 4. 可迁移内容

### 4.1 直接泛化

| AGENT_UE5 概念 | ForgeUE 目标名 | 迁移方式 |
| --- | --- | --- |
| Root Skill Contract | `GameBuildContract` | 抽象为 GDD 约束、变量空间、baseline 能力、玩法能力 |
| Clarification Gate | `GameBuildClarificationReport` | 保留四类决策和 provisional 传播 |
| Skill Graph | `GameBuildGraph` | 保留 dependency / coupling / convergence_order，但不绑定 SkillTemplate 目录 |
| Design Space Discovery | `GameBuildDesignSpaceReport` | 作为 LLM / heuristic 生成阶段的中间 Artifact |
| Build IR v2 | `GameBuildIR` | 改成 engine-neutral action，不直接生成 UE 路径 |
| Reviewed Handoff v3 | `GameBuildHandoff` | 作为 Game Build Compiler 到 ForgeUE Workflow / EngineAdapter 的唯一边界 |
| Run Isolation / compare / promote | 复用 ForgeUE Run + comparison | 只迁移语义，不迁移 `ProjectState/` 目录结构 |

### 4.2 需要改造后迁移

| AGENT_UE5 内容 | 原因 | ForgeUE 改造方向 |
| --- | --- | --- |
| Stage 4 三路生成策略 | 思路好，但 MCP agent 路径不应成为 ForgeUE 第一依赖 | 先支持 `llm` + `heuristic_fallback`，MCP agent 作为后续外部交互模式 |
| Baseline Domain Template | 产品价值高，但 UE widget/C++ 输出耦合 | 抽象为 `start_screen` / `menu` / `settings` / `hud` / `pause` / `results` 能力模板 |
| Cross Review v2 | ForgeUE 已有 Review Engine | 把它变成新的 rubric / review_scope，而不是复制评审实现 |
| Run promote | ForgeUE 已有 run comparison | 先用 read-only compare，后续再定义 promote 写入目标 |

### 4.3 明确不迁移

- 不迁移 `Source/` 下 UE5 C++ 游戏代码。
- 不迁移 `Content/` 下 UE 资产。
- 不迁移 AgentBridge C++ Editor Plugin 到 ForgeUE 主 runtime。
- 不迁移 MCP Bridge Passthrough 28 工具作为首阶段依赖。
- 不迁移 Monopoly hardcoded extraction / planning 逻辑。
- 不迁移 UE5-specific `Source/<Module>/<Group>/<Name>.h`、`/Game/<Module>/<Group>/<Asset>` lowering 规则到 engine-neutral 层。

## 5. 目标架构

新增上层子系统建议名：`game_build_compiler`。

```text
GDD / Design Doc
  -> GameBuildCompiler
       -> GameBuildContract
       -> GameBuildClarificationReport
       -> GameBuildGraph
       -> GameBuildDesignSpaceReport
       -> GameBuildIR
       -> GameBuildHandoff
  -> ForgeUE Workflow Bundle
       -> generate text / image / audio / mesh / video
       -> review
       -> select
       -> export
  -> EngineAdapter
       -> Unreal manifest_only
       -> Godot4 headless_import
```

边界要求：

- `game_build_compiler` 只产结构化 Artifact，不直接写 UE/Godot 项目。
- `GameBuildIR` 使用 engine-neutral action，例如 `create_scene`, `create_ui_screen`, `create_rule_system`, `create_asset_request`, `create_validation_check`。
- 引擎差异只在 lower 到 `engine_target` 或 adapter-specific plan 时出现。
- Review 仍走 ForgeUE 的 Review Engine。
- 资产生成仍走 ForgeUE provider / worker 体系。
- 最终交付仍走 `EngineAdapter`。

## 6. 第一阶段 MVP

第一阶段目标：**GDD -> Game Build Plan + Game Build Graph + Game Build Handoff**。

输入：

- 一份 Markdown / text GDD。
- 目标引擎：`unreal` 或 `godot4`。
- playable build 目标：默认 5 分钟 vertical slice。
- 默认类型：经营/模拟/规则驱动类优先。

输出 Artifact：

| Artifact | 类型建议 | 说明 |
| --- | --- | --- |
| `game_build_contract.json` | `text.structured` | GDD 约束、variant、baseline、玩法能力 |
| `game_build_clarification_report.json` | `report.clarification` | 缺失/冲突/高风险问题 |
| `game_build_graph.json` | `text.structured` | 玩法、UI、资产、验证节点图 |
| `game_build_ir.json` | `text.structured` | engine-neutral build actions |
| `game_build_handoff.json` | `bundle.game_build_handoff` | 可转 Workflow bundle 的最终交接物 |

第一阶段不做：

- 不直接生成 C++ / GDScript 源码。
- 不直接改 UE/Godot 工程。
- 不做视觉精修。
- 不做完整运行时自动测试。
- 不引入新 MCP server。

## 7. 数据模型草案

### 7.1 GameBuildContract

核心字段：

```json
{
  "contract_version": "1.0",
  "source_gdd": {
    "file_path": "ProjectInputs/GDD/shop_management_demo.md",
    "hash": "sha256:example-gdd-hash"
  },
  "game_identity": {
    "genre": "simulation",
    "subgenre": "shop_management",
    "camera": "top_down",
    "session_length_minutes": [5, 10]
  },
  "constraints": {},
  "variants": {},
  "baseline_capabilities": [],
  "gameplay_capabilities": [],
  "target_engines": ["unreal", "godot4"]
}
```

### 7.2 GameBuildGraph

核心字段：

```json
{
  "graph_version": "1.0",
  "nodes": [
    {
      "node_id": "gameplay-core-loop",
      "domain": "gameplay",
      "kind": "rule_system",
      "depends_on": [],
      "couples_with": ["ui-hud", "validation-playability"],
      "priority": 1
    }
  ],
  "edges": [
    {
      "from": "gameplay-core-loop",
      "to": "ui-hud",
      "type": "coupling",
      "reason": "HUD must expose loop state"
    }
  ]
}
```

### 7.3 GameBuildIR

核心字段：

```json
{
  "ir_version": "1.0",
  "actions": [
    {
      "action_id": "act-create-core-loop",
      "action_type": "create_rule_system",
      "domain": "gameplay",
      "inputs": ["gameplay-core-loop"],
      "engine_requirements": {
        "unreal": {"preferred_layer": "blueprint_or_cpp"},
        "godot4": {"preferred_layer": "scene_plus_gdscript"}
      }
    }
  ],
  "asset_requests": [],
  "validation_checks": []
}
```

## 8. 与 ForgeUE 现有系统的集成

### 8.1 Workflow

新增一类 example bundle：`examples/game_build_compiler_plan_smoke.json`。

建议 Workflow：

```text
step_contract
  -> step_clarify
  -> step_graph
  -> step_build_ir
  -> step_review
  -> step_handoff
```

这些 step 第一阶段都可以是 structured generation + validation + review，不需要新增复杂 executor。等契约稳定后，再考虑把常用逻辑沉淀成专用 executor。

### 8.2 Artifact

所有 Game Build Compiler 产物都必须进入 Artifact Store，并携带 lineage：

- `game_build_clarification_report` 来源于 `game_build_contract`
- `game_build_graph` 来源于 `game_build_contract` + `game_build_clarification_report`
- `game_build_ir` 来源于 `game_build_graph`
- `game_build_handoff` 来源于 `game_build_ir` + review verdict

### 8.3 Review

新增 review scope：`game_build_plan_quality`。

rubric 维度：

- GDD constraint 保持性。
- 玩法闭环完整性。
- 5 分钟 demo 可实现性。
- UI / feedback / baseline 完整性。
- engine-neutral 程度。
- 风险与 clarification 标注质量。

### 8.4 EngineAdapter

第一阶段只把 `GameBuildHandoff` lower 成计划，不直接交付引擎。

第二阶段再做：

```text
GameBuildHandoff
  -> ForgeUE Workflow bundle
  -> generate assets
  -> review/select
  -> export via EngineAdapter
```

Unreal / Godot 的分叉点必须在 EngineAdapter 或 adapter-specific lowering，不应出现在 `GameBuildContract` 和 `GameBuildGraph`。

## 9. 实施路线

### Phase A: Contract-only

交付：

- 新增 `docs/contracts/game-build-compiler/spec.md`
- 新增 Game Build Compiler schema 草案
- 新增一个 GDD fixture
- 新增 schema validation tests

验收：

- GDD fixture 可生成或校验 `game_build_contract`、`game_build_graph`、`game_build_handoff` 示例。
- 示例不包含 UE-only 路径。

### Phase B: Workflow smoke

交付：

- 新增 `examples/game_build_compiler_plan_smoke.json`
- 复用 `generate_structured` + `review` + `validate`
- 输出 5 个 Game Build Compiler Artifact

验收：

- 离线 fake adapter smoke 通过。
- live LLM opt-in smoke 可跑。

### Phase C: First vertical slice plan

交付：

- 固定一个经营/模拟类 GDD。
- 产出可审查 Game Build Plan。
- 产出资产请求清单和引擎交付计划。

验收：

- Review verdict 能指出缺失项、风险项和可实现性。
- Handoff 可被人类工程师按步骤实现。

### Phase D: Engine handoff bridge

交付：

- `GameBuildHandoff -> Workflow bundle` 转换器。
- Unreal / Godot adapter-specific lowering 草案。

验收：

- 能把 Game Build Plan 的资产请求进入 ForgeUE 现有生成、review、export 流程。

## 10. 风险与约束

| 风险 | 处理方式 |
| --- | --- |
| AGENT_UE5 代码过度 UE/Monopoly 耦合 | 只迁移契约和流程语义，不复制 hardcoded stage 实现 |
| 第一阶段承诺过大 | 第一阶段只做 plan/handoff，不宣称 playable demo |
| Game Build Compiler 与 Workflow 重叠 | Game Build Compiler 只做上游编译，Workflow 仍是执行真源 |
| Godot 交付能力弱于 UE | 先保持 engine-neutral handoff，Godot L3/L4 后续按 adapter 能力演进 |
| LLM 输出不稳定 | 所有输出走 schema validation + review + artifact lineage |

## 11. 通过标准

这份迁移设计进入 implementation plan 前，需要 msc 确认三点：

1. ForgeUE 新增 `game_build_compiler` 上层子系统是正确方向。
2. 第一阶段只做 `GDD -> Game Build Plan / Game Build Graph / Game Build Handoff`，不直接承诺 playable demo。
3. AGENT_UE5 只作为设计编译参考源，不作为 ForgeUE runtime 依赖。

确认后再进入 `superpowers:writing-plans`，拆 Phase A 的实施计划。
