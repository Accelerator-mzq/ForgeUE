---
name: "ForgeUE: Change Apply"
description: S3→S4-S5;codex plan review hook + Superpowers executing-plans/TDD + 越界检测 + cross-check
category: ForgeUE Workflow
tags: [forgeue, workflow, S3-to-S5, apply]
---

S3→S4-S5 transition:执行 execution_plan + micro_tasks 中的代码改动(Superpowers executing-plans / test-driven-development auto-trigger),跑 codex /codex:adversarial-review plan hook + plan cross-check + git diff 越界检测。

**Input**: 必须指定 change name(`/forgeue:change-apply <id>`)。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`(同 change-plan 步骤 1)。
2. **绑定 active change** — abort if missing。
3. **检查 S3 进入条件**:`execution/execution_plan.md` + `execution/micro_tasks.md` 落盘;上轮 writeback-check exit 0。
4. **冻结 plan cross-check `## A`** — Claude 在调用 codex 之前写好 `review/plan_cross_check.md` `## A`(同 change-plan 协议)。
5. **codex plan review hook**(claude-code + plugin REQUIRED;否则 OPTIONAL):
   - 跑 `/codex:adversarial-review --background "<plan focus>"`
   - 输出落 `review/codex_plan_review.md`(`evidence_type: codex_plan_review`)
6. **Claude 写 plan cross-check `## B/C/D`**(沿 design.md §3 Cross-check Protocol;独立验证 file:line)。
7. **Superpowers executing-plans + TDD auto-trigger**:
   - tdd_log 增量落 `execution/tdd_log.md`(`evidence_type: tdd_log` / 12-key frontmatter)
   - 实施代码改动,**范围限于 design.md 列出的 modules**
8. **越界检测**(命令字面契约要求,round-2 H4.1 修过的字段):
   - `git diff` vs design.md 列出的 modules
   - 若改动文件超出 design.md scope → 报告越界 + 建议:回写 design.md scope 或缩窄改动
9. **回写检测** — `python tools/forgeue_change_state.py --change <id> --writeback-check --json`:
   - DRIFT type 3(`evidence_contradicts_contract`):tdd_log 与 design.md 接口不一致 → exit 5
   - DRIFT type 4(`evidence_exposes_contract_gap`):debug_log 揭示 design.md 异常段缺失 → exit 5
   - 出现 DRIFT → 回写 design.md 或标 `disputed-permanent-drift`
10. **状态推进** — 所有 micro-task done + Level 0 PASS + writeback-check exit 0 + cross-check `disputed_open: 0` + 越界检测 in-scope → 进 S5。

**Output Format**

```
## ForgeUE Change Apply: <change-id> (S3→S4-S5)

### codex plan review
- review/codex_plan_review.md: <findings>
- review/plan_cross_check.md: disputed_open=<N>

### Implementation
- micro-tasks done: X/Y
- TDD log: <line count> lines
- modified files: <count>

### Boundary check
- in-scope vs design.md modules: <PASS | OUT-OF-SCOPE: <files>>

### Writeback check
- DRIFT count: <N>; types: <list>
- next: <S5 ready | blocked + reason>
```

**Guardrails**

- **必绑 active change**。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**(同 change-plan)。
- **`## A` 冻结**(plan_cross_check.md 同样适用)。
- **越界检测是字面契约要求**(design.md §4 / round-2 H4.1 修过):改动超 design.md scope 必须阻断或回写 design.md,**不可静默扩大 scope**。
- **evidence 不能成新规范源**:tdd_log / debug_log 暴露的 contract 漏洞必须回写到 design.md / proposal.md / tasks.md。
- **必跑 writeback 检测**;DRIFT type 3/4 阻断 S5。

**References**

- `design.md` §4 commands 表(`/forgeue:change-apply` 行)— hook + 越界检测 真源
- `design.md` §3 Cross-check Protocol(plan_cross_check 同协议)
- `forgeue_integrated_ai_workflow.md` §B.4 / §D
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
