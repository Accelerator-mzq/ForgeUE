---
change_id: fuse-openspec-superpowers-workflow
stage: S2
evidence_type: codex_design_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
drift_decision: written-back-to-design
writeback_commit: 73f18e6c4967c07269cf8a3677bafd497d20b946
drift_reason: |
  S2 review found contract drift: proposal/tasks still declared no capability delta/spec sync while design and delta spec added an examples-and-acceptance requirement; P3/P4 tasks also did not faithfully cover the named DRIFT protocol. **Resolution**: the 6 codex blockers + 2 non-blockers were addressed pre-P0 inside the bootstrap commit `73f18e6c4967c07269cf8a3677bafd497d20b946` (see `tasks.md` §1.6 "openspec validate fuse-openspec-superpowers-workflow --strict PASS (二次通过 — 经 codex S2→S3 design review hook 手工预演 cross-check, 6 blocker + 2 non-blocker accepted-codex 修完 contract, 1 non-blocker accepted-claude)") which (a) added the `examples-and-acceptance` ADDED Requirement to spec.md, (b) extended design.md §3 with the 4-named DRIFT taxonomy, (c) updated tasks.md to track P3 DRIFT tool implementation. **Frontmatter backfill**: P7 self-review C2 + codex F-D both surfaced that this evidence still carried `aligned_with_contract: false` + `drift_decision: null` + `writeback_commit: null` — pure frontmatter rot, not a remaining contract gap. Per P3 / P4 review evidence backfill pattern (commits `1c0da37` / `2aceee3`), this commit corrects the audit trail to record `written-back-to-design` + the P0 resolution sha. No contract change required.
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: "forced (manual rehearsal of /forgeue:change-plan codex hook before tool implementation)"
codex_plugin_available: "false (codex CLI direct via codex exec, codex-plugin-cc not installed)"
plugin_command: "codex exec --sandbox read-only -o ... (path B equivalent of /codex:adversarial-review --background)"
task_id: codex-s2s3-review-20260426-001
model: gpt-5
effort: high
created_at: 2026-04-26T00:00:00+08:00
scope: design (S2 stage gate)
base_ref: "null (this is design-stage review, not code-level diff)"
---

# Codex S2→S3 Design Review: fuse-openspec-superpowers-workflow

## Summary
- Total findings: 9
- Blockers: 6
- Non-blockers: 3
- Verdict: BLOCK

## Blockers (must fix before /forgeue:change-apply)

### B1. proposal.md 的 capability 段仍是旧的“无 delta”叙述
- **Where**: [proposal.md:25](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/proposal.md:25)
- **Concern**: 关注点 1, 关注点 4
- **Claim**: `proposal.md` 与当前 contract 不一致：它仍声明 `Modified Capabilities: 无`、`不需要 delta spec`，但 `design.md` 和 delta spec 已经把本 change 定义为 `examples-and-acceptance` 的 ADDED Requirement。
- **Evidence**: [proposal.md:25](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/proposal.md:25), [proposal.md:26](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/proposal.md:26), [proposal.md:27](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/proposal.md:27), [design.md:216](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:216), [spec.md:11](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:11)
- **Suggested fix**: 改 `proposal.md`：`New Capabilities: 无` 保留；`Modified Capabilities` 改为 `examples-and-acceptance`；`Why/Capabilities` 明确说明这是 active change acceptance evidence 行为延伸，不是纯 process-only；删掉 `design.md §13 "Why no delta spec"` 旧引用。
- **Independently verified by Claude/user before accepting**: pending

### B2. tasks.md Documentation Sync Gate 仍会跳过 openspec/specs 同步
- **Where**: [tasks.md:158](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:158)
- **Concern**: 关注点 4, 关注点 7
- **Claim**: P6 文档同步任务仍写“本 change 无 capability delta, SKIP”，会直接漏掉 archive 后把 ADDED Requirement 合入主 spec 的必需动作。
- **Evidence**: [tasks.md:158](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:158), [design.md:228](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:228), [design.md:230](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:230)
- **Suggested fix**: 把 `7.5.1` 改成 REQUIRED：archive/sync-specs 后必须检查 `openspec/specs/examples-and-acceptance/spec.md` 是否合入该 ADDED Requirement；其他 7 个 capability 才是 SKIP。
- **Independently verified by Claude/user before accepting**: pending

### B3. delta spec 缺少项目规则要求的 Validation 和 Non-Goals
- **Where**: [spec.md:9](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:9)
- **Concern**: 关注点 6
- **Claim**: delta spec 只有 ADDED Requirement 和 3 个 Scenario，缺少 `openspec/config.yaml` 明确要求的 `Validation` 和 `Non-Goals` section。
- **Evidence**: [openspec/config.yaml:84](/D:/ClaudeProject/ForgeUE_claude/openspec/config.yaml:84), [openspec/config.yaml:86](/D:/ClaudeProject/ForgeUE_claude/openspec/config.yaml:86), [openspec/config.yaml:87](/D:/ClaudeProject/ForgeUE_claude/openspec/config.yaml:87), [spec.md:32](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:32)
- **Suggested fix**: 在 delta spec 末尾补 `## Validation`，指向计划中的具体测试文件，如 `tests/unit/test_forgeue_writeback_detection.py` 和 `tests/unit/test_forgeue_finish_gate.py`；补 `## Non-Goals`，说明不改变 runtime bundle acceptance、不修改其他 7 个 capability。
- **Independently verified by Claude/user before accepting**: pending

### B4. P3/P4 task 拆解没有忠实覆盖 design.md 的 4 类 DRIFT
- **Where**: [tasks.md:74](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:74)
- **Concern**: 关注点 3, 关注点 7
- **Claim**: `design.md` 定义的 4 类 DRIFT 是 named protocol；`tasks.md` P3/P4 却拆成“锚点 / diff vs design modules / aligned 字段 / writeback_commit 真实”，其中后两项是 frontmatter/writeback 校验，不是 `design.md` 的 4 类 DRIFT。
- **Evidence**: [design.md:120](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:120), [design.md:122](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:122), [design.md:125](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:125), [tasks.md:74](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:74), [tasks.md:113](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:113)
- **Suggested fix**: P3/P4 显式拆出 4 个 named DRIFT 测试：`evidence_introduces_decision_not_in_contract`、`evidence_references_missing_anchor`、`evidence_contradicts_contract`、`evidence_exposes_contract_gap`。`aligned=false` 和 `writeback_commit` 真实性保留为 separate frontmatter/finish-gate 校验。
- **Independently verified by Claude/user before accepting**: pending

### B5. Reasoning Notes anchor 协议的 heading 不一致
- **Where**: [spec.md:31](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:31)
- **Concern**: 关注点 5, 关注点 6
- **Claim**: Scenario 3 要求 `forgeue_finish_gate.py` 解析 `design.md` 的 `## Reasoning Notes` section，但实际 `design.md` 是 `### §11 Reasoning Notes(...)`。若工具按字面查 `## Reasoning Notes`，会误报缺 anchor。
- **Evidence**: [spec.md:31](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:31), [spec.md:32](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:32), [design.md:232](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:232), [design.md:238](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:238)
- **Suggested fix**: 统一协议：要么把 design heading 改为 `## Reasoning Notes`，要么在 spec/design/tool task 中明确解析“任意 heading level 且标题包含 `Reasoning Notes` 的 section”。
- **Independently verified by Claude/user before accepting**: pending

### B6. disputed-permanent-drift 的 reason 长度不足被 tasks.md 降成 WARN
- **Where**: [tasks.md:118](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:118)
- **Concern**: 关注点 3, 关注点 6, 关注点 7
- **Claim**: contract 说 `disputed-permanent-drift` 必须有 ≥50 字/字符 `drift_reason`，但测试任务写成 `<50 字 → WARN`，这会允许不合格 permanent drift 进入 finish gate。
- **Evidence**: [design.md:118](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:118), [spec.md:13](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:13), [tasks.md:118](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:118)
- **Suggested fix**: 把 `<50` 从 WARN 改为 blocker：`forgeue_finish_gate.py` exit 2，`forgeue_change_state.py --writeback-check` 可 exit 5；测试断言必须阻断 archive。
- **Independently verified by Claude/user before accepting**: pending

## Non-Blockers (recommend, not required)

### N1. examples-and-acceptance 的承载理由可再补一层桥接
- **Where**: [design.md:216](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:216)
- **Concern**: 关注点 4
- **Claim**: §10 的理由基本站得住，但主 spec 当前 Purpose 仍偏 `examples/` bundle acceptance；未来 reviewer 可能质疑 active change evidence 是否该进新 `ai-workflow` capability。
- **Evidence**: [openspec/specs/examples-and-acceptance/spec.md:5](/D:/ClaudeProject/ForgeUE_claude/openspec/specs/examples-and-acceptance/spec.md:5), [design.md:216](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:216), [design.md:262](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:262)
- **Suggested fix**: 在 §10 加一句桥接：本 delta 临时归入 `examples-and-acceptance` 是因为它定义“acceptance evidence handling”，不是建立长期 AI workflow capability；第 9 capability 需按 §11.3 触发条件另起 change。
- **Independently verified by Claude/user before accepting**: pending

### N2. micro_tasks anchor 校验没有独立 scenario
- **Where**: [design.md:133](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:133)
- **Concern**: 关注点 3, 关注点 6, 关注点 7
- **Claim**: state machine 和 artifact map 把 `execution_plan.md` 与 `micro_tasks.md` 都列为 S3 必需，但 delta Scenario 1 和 P4 fence 只显式覆盖 `execution_plan.md`。
- **Evidence**: [design.md:72](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:72), [design.md:132](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:132), [design.md:133](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:133), [spec.md:17](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:17), [tasks.md:114](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:114)
- **Suggested fix**: 增加一个 micro_tasks 引用不存在 `tasks.md#X.Y` 的测试，或明确 micro_tasks 只复用同一 parser，不需要单独 scenario。
- **Independently verified by Claude/user before accepting**: pending

### N3. frontmatter “11 字段”标签与实际 key 数不一致
- **Where**: [proposal.md:20](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/proposal.md:20)
- **Concern**: 关注点 3, 关注点 6
- **Claim**: 文档反复称“11 字段”，但列出的 key 包含 `change_id` 加上原 11 个审计字段，实际是 12 个。工具实现若按数量写死会出错。
- **Evidence**: [proposal.md:20](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/proposal.md:20), [design.md:94](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:94), [forgeue-fusion-cross_check.md:130](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/notes/pre_p0/forgeue-fusion-cross_check.md:130)
- **Suggested fix**: 统一叫“12 字段”，或明确 `change_id` 是 wrapper metadata、不计入 11-field audit schema。
- **Independently verified by Claude/user before accepting**: pending

## 7 关注点逐项答复

### 关注点 1: proposal.md "Why" 中心化
partial。中心化主旨本身清楚，`OpenSpec contract artifact` 是唯一规范锚点、Superpowers/codex/ForgeUE evidence 都服务于它，这一点在 [proposal.md:11](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/proposal.md:11) 可一遍 grasp。但 Capabilities 段仍说 Modified none/no delta，和当前 delta spec 冲突，且没有解释“为什么这是 capability 行为延伸而不是 process-only”：[proposal.md:25](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/proposal.md:25)。

### 关注点 2: design.md §1-§2 中心化架构图
passed。架构图把 `OpenSpec Contract Artifact` 放中心，Superpowers/codex/tools 都是 evidence/DRIFT 服务者，ForgeUE 明确是 guard tools，不是并立 layer：[design.md:51](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:51), [design.md:56](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:56), [design.md:62](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:62)。这不是单纯改图，语义上已经从“三层并立”改成“中心 + 服务者”。

### 关注点 3: design.md §3 状态机表 contract 中心动作
partial。S2/S4/S6/S8 的中心动作方向清楚，且 P3 tool mapping 写到 `forgeue_change_state.py --writeback-check` 和 `forgeue_finish_gate.py`：[design.md:72](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:72), [design.md:74](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:74), [design.md:76](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:76), [design.md:176](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:176)。但 P3/P4 task 没忠实覆盖 §3 的 4 类 named DRIFT，且 Reasoning Notes anchor heading 还不一致，见 B4/B5/B6。

### 关注点 4: design.md §10 Capability Delta Scope
partial。§10 从“无 delta”改为 `examples-and-acceptance` ADDED Requirement 的论证基本可接受，且清楚区分 7 个不动 capability 与 1 个延伸 capability：[design.md:216](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:216), [design.md:218](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:218), [design.md:228](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:228)。阻断点是 proposal 和 tasks 还停留在旧结论，见 B1/B2。

### 关注点 5: design.md §11 Reasoning Notes 4 项 disputed 落地
passed with one protocol caveat。§11.1 D-CommandsCount reason 足够，且明确用 8 个命令来保持 OpenSpec 中心地位：[design.md:242](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:242)。§11.2 D-DocsCount reason 充分，解释了子文档脱链风险和 single source：[design.md:252](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:252)。§11.3 当前不抽 `ai-workflow` 的理由和未来触发条件具体可验证：[design.md:260](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:260), [design.md:262](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:262)。§11.4 `/codex:rescue` 豁免范围明确仅本 change Pre-P0，未来不适用：[design.md:268](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/design.md:268)。

### 关注点 6: specs delta 3 个 Scenario 可执行性
partial。Scenario 1 的文件路径和 exit 5 可执行性成立，能造 `tasks.md#99.1` 失链 plan：[spec.md:17](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:17), [spec.md:20](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:20)。Scenario 2 的 finish gate exit 2 也可达：[spec.md:24](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:24), [spec.md:26](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:26)。Scenario 3 逻辑可达，但 `## Reasoning Notes` 与实际 `### §11 Reasoning Notes` heading 不一致；此外 delta spec 缺 Validation/Non-Goals，见 B3/B5。

### 关注点 7: tasks.md §3-§5 工作分解
partial。§3 的 8 commands + 2 skills + 2 anti-pattern fence 足够小，一次会话可完成：[tasks.md:45](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:45), [tasks.md:58](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:58), [tasks.md:65](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:65)。§4 的 5 tools 有关键能力拆分，但 `forgeue_change_state.py` 的 DRIFT taxonomy 不匹配 design：[tasks.md:72](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:72), [tasks.md:74](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:74)。§5 覆盖面广，但漏 named DRIFT 全量断言，且 reason 长度不足被降为 WARN：[tasks.md:113](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:113), [tasks.md:118](/D:/ClaudeProject/ForgeUE_claude/openspec/changes/fuse-openspec-superpowers-workflow/tasks.md:118)。

## Out-of-scope notes
- 未读取 `notes/pre_p0/forgeue-fusion-claude.md` 和 `notes/pre_p0/forgeue-fusion-codex.md`，遵守本次限制；只用 `forgeue-fusion-cross_check.md` 作为 Pre-P0 裁决事实基线。
- 未做 code-level diff review；本报告只审 S2 contract artifacts。
- `openspec validate fuse-openspec-superpowers-workflow --strict` 在当前命令策略下被拦截，未作为本报告证据来源。

## Cross-check protocol reminder

ForgeUE memory `feedback_verify_external_reviews` 要求:Claude 必须独立验证每条 blocker 的 file:line evidence 真实性后才接受 — 标 `pending` 直至 Claude 确认。