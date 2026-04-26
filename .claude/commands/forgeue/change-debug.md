---
name: "ForgeUE: Change Debug"
description: bug 时显式调 Superpowers systematic-debugging skill;debug_log 增量;暴露 design 异常缺口必回写
category: ForgeUE Workflow
tags: [forgeue, workflow, S4, debug]
---

S4 实施过程中遇到 bug / 测试失败 / 意外行为时显式调用 Superpowers `systematic-debugging` skill;debug 过程产物落 `execution/debug_log.md`(增量);若 debug log 揭示 design.md 异常段缺失 → DRIFT type 4 → 回写 design.md。

**Input**: 必须指定 change name(`/forgeue:change-debug <id>`);可选附加 bug 描述。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`;debug 不强依赖 codex,non-claude-code env 仍可跑(无 codex hook)。
2. **绑定 active change** — abort if missing。
3. **检查 S4 进入条件**:已在 implementation 阶段(execution_plan + micro_tasks 落盘 + 至少部分 tdd_log)。
4. **Superpowers `systematic-debugging` skill auto-trigger**:
   - 形成 hypothesis → 验证 → narrow root cause(skill 主导)
   - debug 过程笔记追加到 `execution/debug_log.md`(`evidence_type: debug_log` / 12-key frontmatter / `aligned_with_contract: true` 默认,若发现异常 design 缺口则 false + drift_decision)
5. **回写检测**(若 debug 完成有 design 漏洞暴露):
   - 跑 `python tools/forgeue_change_state.py --change <id> --writeback-check --json`
   - DRIFT type 4(`evidence_exposes_contract_gap`)— 例如:重试策略缺失 / 异常段不全 → exit 5;回写 design.md `§5.7 Failure Mode Map` 或类似段
6. **不**自动推进状态(本命令是辅助 debug,不属状态机推进步骤;状态推进由 change-apply / change-verify 决定)。

**Output Format**

```
## ForgeUE Change Debug: <change-id>

### Debug Session
- bug description: <user-input or extracted from logs>
- hypothesis tested: <list>
- root cause: <description>

### Evidence
- execution/debug_log.md: <append count> lines added (frontmatter: aligned_with_contract=<bool>)

### Writeback check (if debug exposes design gap)
- DRIFT type 4 count: <N>
- write-back target: design.md §<X>
- recommended action: <回写文本 draft or "no design gap exposed">
```

**Guardrails**

- **必绑 active change**。
- **不调 `/codex:rescue`** 在 debug 流程内(违 review-only;Pre-P0 是本 fusion change 一次性附录例外,本命令不豁免;markdown lint fence 守门)。
- **不启 `--enable-review-gate`**。
- **不引入 paid provider / live UE / live ComfyUI 调用**:debug 默认走 Level 0(env guard 严格 `{1,true,yes,on}`)。
- **不让 evidence 成新规范源**:debug_log 揭示的 design 缺口必须回写 design.md(DRIFT type 4 protocol)。
- **本命令不直接触发 `/codex:adversarial-review` / `/codex:review`**(本命令是 systematic-debugging,bug 排查不属 stage review;若需 review 走 `/forgeue:change-{plan,apply,verify,review}` 对应 stage hook)。

**References**

- `design.md` §4 commands 表(`/forgeue:change-debug` 行)— hook 真源:`Superpowers debugging skill`
- `forgeue_integrated_ai_workflow.md` §B.3(Superpowers `systematic-debugging` 集成边界)+ §D.3(DRIFT type 4)
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
- ForgeUE memory `feedback_no_silent_retry_on_billable_api`(debug 涉及 mesh.generation 等贵族 API:不静默重试)
