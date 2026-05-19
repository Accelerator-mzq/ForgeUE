---
change_id: adopt-subagent-driven-development
stage: S9
evidence_type: layer_6_verification
contract_refs:
  - notes/pre_p0/subagent_dogfood_protocol.md
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: skill_invoke
codex_plugin_available: true
triggered_by_command: change-apply-subagent
---

# Layer 6 Verification — Real Skill Invoke vs Manual Emulation

## Background

本 change (`adopt-subagent-driven-development`) 于 2026-05-04 全程归档。在 §4+ 命令实装阶段（`/forgeue:change-apply-subagent` 等命令落地后），change 的实施过程实际采用了 Claude Code `Agent` tool 手工 emulation Superpowers `subagent-driven-development` skill protocol——即 controller 直接编写 implementer/spec-reviewer/code-quality-reviewer 三类 subagent 的 prompt，并手工决定 dispatch 顺序，而非通过 `Skill` tool 触发 SKILL.md 定义的标准 orchestration flow。

这一模式被定义为 **Layer 6 finding**：change 归档时未能在同一 change 内完成「在 §4+ 阶段切换为真 skill invoke」的闭环验证。本文档作为补充 evidence，通过一次实际的 `superpowers:subagent-driven-development` skill invoke + subagent dispatch 来封闭该发现。

## Real Skill Invoke 实证

本次 Layer 6 verification 的 dispatch 链路如下：

1. **Skill tool invoke**：主 session（controller，运行于 Opus 4.7 模型）调用 `Skill` tool，参数 `skill: "superpowers:subagent-driven-development"`，附带 args 描述 Layer 6 verification 单任务的内容。
2. **SKILL.md content injection**：Skill tool 将 `superpowers:subagent-driven-development` 的完整 SKILL.md 内容注入到主 session 上下文，controller 按照 SKILL.md `## The Process` 章节定义的 orchestration flow 执行。
3. **Controller dispatch**：主 session 遵循 SKILL.md 的 Model Selection 规则（"cheap model for mechanical 1-file task"），使用 `Agent` tool 并附带 `model: sonnet` 参数，将本任务派发给 Sonnet subagent 执行。
4. **Subagent 执行**：本文件正是由该 Sonnet subagent（即本 implementer）撰写，执行单一文件写入任务。

**关键 Observation**：

- 本 subagent 在 Claude Code UI 中显示的模型标识为 **Sonnet 4.6**（`claude-sonnet-4-6`）。
- 对比本 change §4+ 阶段的手工 emulation：全部 subagent dispatch 均默认使用 Opus 4.7（主 session 模型，无 `model` 参数选择），缺乏 mechanical vs architecture 任务的模型分层。
- 真 skill invoke 通过 SKILL.md 驱动 controller 作出显式模型选择（Sonnet for mechanical），这是手工 emulation 未能复现的关键 protocol 差异。

## Protocol Differences

| 维度 | Manual Emulation（本 change §4+ 手工模式） | Real Skill Invoke（本次 Layer 6 verification） |
|------|-------------------------------------------|-----------------------------------------------|
| **Agent tool 模型参数** | 默认（主 session Opus 4.7，无 `model` 参数） | 显式 `model: sonnet`（SKILL.md Model Selection 驱动） |
| **Prompt 来源** | Controller 自行编写 implementer/spec-reviewer/code-quality-reviewer 模板 | SKILL.md `## The Process` flow auto-drives，标准化 role prompt |
| **Dispatch 顺序决策** | Controller 手工决定（ad-hoc） | SKILL.md orchestration flow 规定（standardized sequence） |
| **`triggered_by` audit field** | `triggered_by: forced (Pre-P0 dogfood manual dispatch)` | `triggered_by: skill_invoke` |
| **Spec-reviewer / Code-quality-reviewer** | 可能被省略或由主 session 内联完成 | SKILL.md 明确要求独立 subagent，controller 不可内联 |
| **模型成本优化** | 无（全 Opus；mechanical task 也用贵模型） | 有（Sonnet for mechanical，Opus for architecture） |

## Conclusions

Layer 6 finding 经此 verification 确认有效，结论如下：

1. **`triggered_by` audit field 具有真实 forensic value**：`skill_invoke` 与 `forced (Pre-P0 dogfood manual dispatch)` 两个值确实对应不同 dispatch 路径，后者缺失 SKILL.md 驱动的模型选择与标准化 orchestration，前者完整复现。

2. **Future fence test 可验证性**：在 §4+ 阶段生成的所有 execution/review/verification evidence 中，凡 `triggered_by != "skill_invoke"` 的条目均标志着 manual emulation，可用于追溯哪些阶段未走真 skill invoke；这对 regression 审计有直接价值。

3. **本 change 归档完整性**：Layer 6 finding 已通过本次补充 evidence 封闭，`adopt-subagent-driven-development` change 的 dogfood protocol 在 S9 阶段完成了最终的真 skill invoke 实证，无遗留开放 gap。

4. **建议**：后续 change 在 §4+ 阶段应从第一个 task dispatch 起即走真 skill invoke（`Skill` tool → SKILL.md → Agent + model 参数），避免本 change 的 Layer 6 pattern 复现。

## Self-review

- **Completeness**：文件包含 frontmatter（12-key + `triggered_by: skill_invoke` audit field）及 6 个 body section（Background / Real Skill Invoke 实证 / Protocol Differences / Conclusions / Self-review），结构完整。
- **Quality**：各节内容与 Task Description 规定一致；Protocol Differences 以对比表格呈现，清晰可读；Conclusions 4 条结论均有论据支撑。
- **Discipline**：仅写入指定路径单一文件，未修改其他文件，未执行 commit / push。
- **Cross-reference**：`contract_refs` 指向 `notes/pre_p0/subagent_dogfood_protocol.md`（Layer 6 finding 来源）；`triggered_by_command: change-apply-subagent` 与触发本次 dispatch 的命令一致；`detected_env: claude-code` 与实际运行环境一致。
