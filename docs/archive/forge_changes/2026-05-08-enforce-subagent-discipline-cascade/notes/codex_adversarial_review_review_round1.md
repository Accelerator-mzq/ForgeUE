---
change_id: enforce-subagent-discipline-cascade
stage: S2
evidence_type: codex_adversarial_review
review_type: codex_adversarial_review
round: 1
contract_refs:
  - openspec/changes/enforce-subagent-discipline-cascade/design.md
  - openspec/changes/enforce-subagent-discipline-cascade/proposal.md
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md
  - openspec/changes/enforce-subagent-discipline-cascade/review/design_cross_check.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
codex_thread_id: 019e07ce-a127-7340-a107-67275dc41802
codex_turn_id: 019e07ce-a5b6-7922-a697-f59f7a3743e3
verdict: needs-attention
total_findings: 2
disputed_open: 0
resolved_at: 2026-05-08T13:36:01Z
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_adversarial_review_review_round1.md
---

# Codex Adversarial Review (Round 1)

Target: working tree diff
Verdict: needs-attention

不建议放行：当前协议草案的自验证和 fence 设计仍允许关键路径漏接 cascade 而不被测试发现。

Findings:
- [high] D3 fence 只按出现次数检查，无法证明所有目标命令都接入 discipline cascade (openspec/changes/enforce-subagent-discipline-cascade/review/design_cross_check.md:42-55)
  计划里 Phase A 明确是"mechanical replace 3 处 markdown"，但风险表把静态扫缓解描述成检查特定字符串 `subagent-driven-discipline` 且出现次数 `>= 2`。由此可推断：3 个目标命令模板中漏改任意 1 个，测试仍可能通过。影响是某条 subagent dispatch 路径继续不声明 discipline dependency，后续 model tier / cascade dogfood 协议在该入口静默失效。
  Recommendation: 把 D3 改成枚举精确文件/section 的断言：每个应接入的命令模板都必须在 Skill Cascade/Preflight 段包含 `subagent-driven-discipline`；同时显式断言 direct 路径不包含、archived 路径不扫描或不要求。不要用全仓出现次数作为通过条件。
- [medium] D6 dogfood 存在启动顺序悖论，Phase A 不能证明新协议已经生效 (openspec/changes/enforce-subagent-discipline-cascade/review/design_cross_check.md:76-80)
  草案要求 Phase A implementer dispatch 时 `--invoked` 已含 `subagent-driven-discipline`，但又说 Phase A 修订生效 commit 在前、Phase B/D dispatch 在后。若 Phase A 正是在实现命令模板修订，则第一次 Phase A dispatch 发生时新模板尚不存在；它只能靠人工手动带参满足，不能证明修订后的协议路径有效。影响是 self-reference evidence 可能把 bootstrap 行为误当成协议生效证据。
  Recommendation: 把 D6 拆成两段：Phase A 允许作为 manual bootstrap evidence；真正的 self-dogfood acceptance 从 Phase B 开始，必须在 Phase A commit 之后通过更新后的 command template 触发，并在 tasks/final reviewer evidence 中记录这一顺序。

Next steps:
- 收紧 D3 静态测试为逐文件逐 section 断言。
- 重写 D6 的 dogfood 验收顺序，区分 bootstrap 与协议生效后的 dispatch 证据。

---

## Resolution(由 Claude controller 写入,沿 review/design_cross_check.md ## B)

| Finding | Severity | Resolution | Writeback target |
|---|---|---|---|
| F1 | high | accepted-codex | design.md D3 + tasks.md §2 + execution/execution_plan.md Task 2(加 `test_change_apply_direct_does_not_reference_subagent_driven_discipline` negative assertion)|
| F2 | medium | accepted-codex | design.md D6.1 + execution/execution_plan.md Bootstrap Phase 协议段 + Task 4 Final reviewer 4 项验证责任 |

`disputed_open: 0`(沿 cross-check `## C`)→ S3 unblocked。
