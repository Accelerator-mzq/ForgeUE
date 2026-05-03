---
name: "ForgeUE: Change Plan"
description: S2→S3 transition;codex-plugin-cc /codex:adversarial-review + 写 cross-check;Superpowers writing-plans 配路径 + 锚点检测
category: ForgeUE Workflow
tags: [forgeue, workflow, S2-to-S3, plan]
---

S2→S3 transition:把 OpenSpec contract artifact 转为 execution plan + micro tasks(Superpowers writing-plans skill 输出落 `execution/`),并跑 codex /codex:adversarial-review design hook + design cross-check + 锚点检测。

**Input**: 必须指定 change name(`/forgeue:change-plan <id>`)。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`;读 `auto_codex_review` / `codex_plugin_available`;non-claude-code env 时 codex hook 降级 OPTIONAL,不阻断 archive。
2. **绑定 active change** — 若 `<id>` 不存在或无 active changes → abort。
3. **检查 S2 进入条件**:proposal/design/tasks 三件套齐 + `openspec validate <id> --strict` PASS。
4. **冻结 cross-check `## A`** — Claude 在 codex 调用之前写好 `review/design_cross_check.md` `## A. Decision Summary` 段(锁定本次 review 的 Claude 立场,protocol 自我保护);frontmatter 含 `created_at` 时间戳。
5. **codex design review hook**(claude-code env + plugin available 时 REQUIRED;否则 OPTIONAL):
   - 跑 `/codex:adversarial-review --background "<design focus from contract>"`
   - 输出落 `review/codex_design_review.md`(由 codex-plugin-cc 写;12-key frontmatter 含 `evidence_type: codex_design_review`)
6. **Claude 写 cross-check `## B/C/D`**(沿 design.md §3 Cross-check Protocol 模板):
   - `## B`:逐条 codex finding 对照 + Resolution(`aligned` / `accepted-codex` / `accepted-claude` / `disputed-pending` / `disputed-permanent-drift`)
   - `## C`:`disputed_open: <count>`;> 0 阻断 S3
   - `## D`:**独立验证 file:line**(沿 ForgeUE memory `feedback_verify_external_reviews`,不把 codex claim 当结论)
7. **Superpowers writing-plans skill auto-trigger**:输出落 `execution/execution_plan.md` + `execution/micro_tasks.md`;引用 `tasks.md#X.Y` 锚点;12-key frontmatter(`stage: S2` / `evidence_type: execution_plan` / `contract_refs: [tasks.md#X.Y, ...]` / `aligned_with_contract: true`)。
8. **锚点 + 回写检测** — `python tools/forgeue_change_state.py --change <id> --writeback-check --json`:
   - DRIFT type 2(`evidence_references_missing_anchor`)→ exit 5 阻断
   - DRIFT type 1/3/4 出现 → exit 5;回写 design.md / proposal.md / tasks.md 或标 `disputed-permanent-drift`
9. **状态推进** — cross-check `disputed_open: 0` + writeback-check exit 0 → 进 S3。

**Output Format**

```
## ForgeUE Change Plan: <change-id> (S2→S3)

### codex design review
- review/codex_design_review.md: <findings count> findings
- review/design_cross_check.md: disputed_open=<N>

### Superpowers writing-plans
- execution/execution_plan.md: <line count> lines, <anchor count> tasks.md anchors
- execution/micro_tasks.md: <task count> tasks

### Writeback check
- DRIFT count: <N>; types: <list>
- next: <S3 ready | blocked + reason>
```

**Guardrails**

- **必绑 active change**:无 `<id>` → abort。
- **不调 `/codex:rescue`**(违 review-only;Pre-P0 是本 fusion change 一次性附录例外,本命令不豁免;markdown lint fence 守门)。
- **不启 `--enable-review-gate`**(plugin 自警告 long loop)。
- **`## A` 冻结**:Claude 写 cross-check `## A` 段必须在调用 codex **之前**完成,**禁止**看完 codex 后回填(协议自我保护)。
- **evidence 不能成新规范源**:codex finding 暴露 contract 漏洞 → 回写到 design.md / proposal.md / tasks.md(`drift_decision: written-back-to-<artifact>` + 真实 commit);否则 `disputed-permanent-drift` 必有 ≥ 50 字 reason + design.md `## Reasoning Notes` anchor。
- **必跑 writeback 检测**:`forgeue_change_state.py --writeback-check` exit 5 阻断 S3。

**References**

- `design.md` §4 commands 表(`/forgeue:change-plan` 行)— hook 真源:`codex-plugin-cc /codex:adversarial-review + 写 cross-check`
- `design.md` §3 Cross-check Protocol — A/B/C/D 模板 + Resolution enum + frontmatter 必含字段
- `forgeue_integrated_ai_workflow.md` §B.4(codex stage hook)+ §D.5/§D.6(cross-check 模板复述)
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
