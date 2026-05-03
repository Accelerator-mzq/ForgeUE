---
name: "ForgeUE: Change Status"
description: 调 forgeue_change_state;列 active changes / state / evidence + 回写状态(只读;无 codex hook)
category: ForgeUE Workflow
tags: [forgeue, workflow, status, readonly]
---

列出 active OpenSpec change 的状态(state machine S0-S9 + evidence 完整度 + 回写状态)。**只读命令**;不触发任何 codex review hook 或 Superpowers skill。

**Input**: 可选指定 change name(`/forgeue:change-status <id>`);省略则列出所有 active changes。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`;读 `detected_env` / `codex_plugin_available` / `superpowers_plugin_available`;env=unknown 仅 WARN 不阻断(本命令只读)。
2. **绑定 active change** — 若指定 `<id>`,直接用;否则调 `openspec list --json` 列 active changes。
3. **查 state + evidence** — `python tools/forgeue_change_state.py --change <id> --json`(无 `--writeback-check`,只查询不阻断):
   - 推断当前 state(S0-S9)
   - evidence 子目录文件清单(`notes/` / `execution/` / `review/` / `verification/`)
   - 每份 evidence frontmatter 的 `aligned_with_contract` / `drift_decision` / `writeback_commit`
4. **渲染报告** — 见 Output Format。

**Output Format**

```
## ForgeUE Change Status: <change-id>

**State**: S<N> (<state-name>)
**Tasks**: X/Y complete

### Evidence
- notes/ — N files
- execution/ — execution_plan.md / micro_tasks.md / tdd_log.md / debug_log.md
- review/ — superpowers_review.md / codex_*.md / *_cross_check.md
- verification/ — verify_report.md / doc_sync_report.md / finish_gate_report.md

### Writeback Status
- aligned_with_contract: true — <count> files
- drift_decision pending — <count>
- written-back-to-* — <count> (with commit refs)
- disputed-permanent-drift — <count> (with reasoning_notes_anchor)

### Next Actions
<state-specific suggestion: e.g., "S2 → S3: run /forgeue:change-plan <id>">
```

**Guardrails**

- **必绑 active change**:无 `<id>` 又无 active changes → 报告 "no active change" 退出。
- **只读**:不调 `forgeue_change_state.py --writeback-check`(那是阻断命令);本命令只查询。
- **不调 `/codex:rescue`**(违 review-only 原则;Pre-P0 是本 fusion change 一次性附录例外,本命令不豁免;markdown lint fence `test_forgeue_workflow_plugin_invocation.py` 守门)。
- **不启 `--enable-review-gate`**(plugin 自警告 long loop)。
- **evidence 不能成新规范源**:报告中 "writeback pending" 项需提示用户回写到 contract artifact(proposal.md / design.md / tasks.md / specs/<cap>/spec.md)。
- **本命令不直接触发 `/codex:adversarial-review` / `/codex:review`**(本命令是只读 state listing,不属 stage review;若需 review 走 `/forgeue:change-{plan,apply,verify,review}` 对应 stage hook)。

**References**

- `design.md` §4 commands 表(`/forgeue:change-status` 行)— hook 真源:`调 forgeue_change_state`
- `forgeue_integrated_ai_workflow.md` §B.1(状态机 S0-S9)+ §D.1(evidence 子目录结构)
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
