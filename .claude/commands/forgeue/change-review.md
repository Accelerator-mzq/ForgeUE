---
name: "ForgeUE: Change Review"
description: S5→S6;Superpowers requesting-code-review finalize + codex /codex:adversarial-review mixed scope + blocker 回写
category: ForgeUE Workflow
tags: [forgeue, workflow, S5-to-S6, review]
---

S5→S6 transition:Superpowers `requesting-code-review` skill + `code-reviewer` subagent finalize 自评;codex `/codex:adversarial-review --background` mixed scope(doc + code)对抗评审;每条 blocker 由 Claude 独立验证 file:line 真实性(沿 `feedback_verify_external_reviews`)再决定接受;涉及 design choice 的 blocker 必回写 design.md。

**Input**: 必须指定 change name(`/forgeue:change-review <id>`)。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`。
2. **绑定 active change** — abort if missing。
3. **检查 S5 进入条件**:`verification/verify_report.md` 落盘 + 无 [FAIL] + 上轮 writeback-check exit 0。
4. **Superpowers `requesting-code-review` skill + `code-reviewer` subagent auto-trigger**:
   - skill 主导自评 + subagent finalize
   - 输出汇总到 `review/superpowers_review.md`(S4 增量 + S6 finalize;`evidence_type: superpowers_review`)
5. **codex adversarial review hook**(claude-code + plugin REQUIRED;否则 OPTIONAL;**mixed scope:doc + code**;**不**走 cross-check):
   - 跑 `/codex:adversarial-review --background "<full focus on change>"`
   - 输出落 `review/codex_adversarial_review.md`(`evidence_type: codex_adversarial_review`)
6. **blocker 独立验证**(沿 ForgeUE memory `feedback_verify_external_reviews`):
   - 每条 codex / superpowers blocker 由 Claude 对照真实 file:line evidence 验证
   - 虚构 / 不准确 → 标记 `verified=false`,reject
   - 真实 → accept;按性质分类:
     - 涉及 design choice → 回写 design.md(`drift_decision: written-back-to-design`)或标 `disputed-permanent-drift` + design.md `## Reasoning Notes` anchor
     - 涉及 tasks 缺失 → 回写 tasks.md
     - 涉及代码 bug → 修代码
7. **回写检测** — `python tools/forgeue_change_state.py --change <id> --writeback-check --json`;DRIFT 出现 → 阻断 S7。
8. **状态推进** — superpowers_review finalize + codex_adversarial_review evidence + blocker 全清(0 unresolved) → 进 S7。

**Output Format**

```
## ForgeUE Change Review: <change-id> (S5→S6)

### Superpowers review
- review/superpowers_review.md: finalized; <findings count>

### codex adversarial review
- review/codex_adversarial_review.md: <findings count>
- mixed scope (doc + code)

### Blocker resolution
- blockers found: <N>
- verified true: <count>; rejected as inaccurate: <count>
- written-back-to-*: <count> (artifacts touched: <list>)
- disputed-permanent-drift: <count> (with reasoning_notes_anchor)

### Writeback check
- DRIFT count: <N>
- next: <S7 ready | blocked + reason>
```

**Guardrails**

- **必绑 active change**。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**(同 change-plan)。
- **adversarial review 不走 cross-check**(design.md §3 Cross-check Protocol carve-out:adversarial 已含挑战式视角 + mixed scope;blocker 独立验证 file:line);仅 doc-level S2 design / S3 plan 走 cross-check。
- **每条 blocker 必独立验证 file:line**(沿 `feedback_verify_external_reviews`):不把 codex/superpowers claim 当结论,实测对照后才接受。
- **evidence 不能成新规范源**:涉及 design choice 的 blocker 必回写 design.md(`written-back-to-design` + 真实 commit)或标 `disputed-permanent-drift`(reason ≥ 50 字 + Reasoning Notes anchor)。
- **必跑 writeback 检测**;DRIFT 阻断 S7。

**References**

- `design.md` §4 commands 表(`/forgeue:change-review` 行)— hook 真源:`Superpowers requesting-code-review + /codex:adversarial-review`
- `design.md` §3 Cross-check Protocol(adversarial carve-out:不走 cross-check)
- `forgeue_integrated_ai_workflow.md` §B.4 / §D
- ForgeUE memory `feedback_verify_external_reviews`(逐条 file:line 独立验证)
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
