---
name: "ForgeUE: Change Apply (Direct)"
description: S3→S4-S5 fallback;executing-plans + TDD;不派 subagent;轻量 change(< 3 micro-task)/ budget 紧张时使用
category: ForgeUE Workflow
tags: [forgeue, workflow, S3-to-S5, apply, direct]
---

S3→S4-S5 transition(fallback 路径,自 `adopt-subagent-driven-development` change 起):执行 execution_plan + micro_tasks 中的代码改动(Superpowers `executing-plans` / `test-driven-development` auto-trigger),跑 codex `/codex:adversarial-review` plan hook + plan cross-check + git diff 越界检测。

**Input**: 必须指定 change name(`/forgeue:change-apply-direct <id>`)。

**适用场景**: 轻量 change(< 3 micro-task)/ budget 紧张 / 不需要 4× LLM dispatch 强 review checkpoint;多 micro-task / 需要 spec compliance 强约束时改走 `/forgeue:change-apply-subagent`。

## Preflight(D-PreflightProtocol)

实施 Steps 之前 controller MUST 顺序完成以下 2 个 preflight 检查;任一 fail → 命令 abort + 详细错误,不进入 Steps 主流程。

> **本命令 NOT 含 Preflight Worktree**(沿 D-DirectWorktreeRefinement 2026-05-05 user 拍板 + retire-parallel-and-worktree-fully 进一步 retire ForgeUE-level worktree 强制层):direct 路径**仍跑在主 worktree**,不强制 isolated worktree。controller 可在 dispatch 前自由 invoke `Skill(superpowers:using-git-worktrees)` SKILL 决定是否 isolation(default decline → main repo cwd)。需要 worktree 隔离请走 `/forgeue:change-apply-subagent`。

### Preflight Skill Cascade(D-SkillCascadeCheck)

实施前 controller MUST 验证 Superpowers `executing-plans` + `test-driven-development` SKILL 已被 invoke(direct 路径主 SKILL 是 `executing-plans`,test-driven-development auto-trigger):

```bash
python tools/forgeue_skill_cascade_check.py \
    --skill superpowers:executing-plans \
    --invoked superpowers:test-driven-development,superpowers:writing-plans,superpowers:verification-before-completion
```

- exit 0 → cascade OK
- exit 5 → missing dependency → 命令 abort + 提示主动 invoke 缺失 SKILL 后 retry

evidence frontmatter MUST 加 `skill_cascade_audit` 字段(对象,含 `invoked_skills` list + `cascade_check_pass_at` ISO 8601 timestamp);`forgeue_finish_gate.py::_check_skill_cascade` fence 守门 audit。

### Preflight Task Granularity(D-TaskGranularityDeclaration)

Controller MUST 在实施前显式声明本次 task 粒度,枚举值 `phase` / `per-file` / `sub-task`:

- `phase` — 整个 phase(如 P0/P1)整体在主 worktree 实施(direct 默认 — 单 task / 微调场景常用)
- `per-file` — 每个修改文件 1 round 实施
- `sub-task` — tasks.md 每个 `- [ ] X.Y` 1 round 实施(细粒度场景;此粒度通常配 subagent dispatch,建议改走 `/forgeue:change-apply-subagent`)

evidence frontmatter MUST 加 `task_granularity: <value>` 字段;`forgeue_finish_gate.py::_check_task_granularity` fence 守门。

### Preflight 协议版本标记(D-ProtocolVersionMigration)

evidence frontmatter MUST 加 `runtime_enforcement_protocol_version: v1` 字段。此字段触发 v1 advisory fence(skill_cascade / round_fix_continuity / task_granularity)生效;无此字段的 evidence 视为 legacy → 全 fence pass-through(archived ADR-010 时期 evidence 兼容)。

**Active 路径 evidence + present-but-invalid value**(`v2` / `v3` / typo / null / empty / `v4`)→ BLOCKER `unknown_protocol_version`(沿 D-ActiveVsArchivedReplayBoundary)。**Archived 路径 evidence + 任何 unknown value** → legacy pass-through(归档不动)。

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
## ForgeUE Change Apply Direct: <change-id> (S3→S4-S5)

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
- **direct 路径不进 isolated worktree**(主 worktree 实施;如需 worktree 隔离请改走 `/forgeue:change-apply-subagent` 或自由 invoke `Skill(superpowers:using-git-worktrees)`)。
- **direct 路径 evidence shape 与 subagent 路径不同**:本路径产 `tdd_log` + `debug_log`(沿现 evidence 协议),**不产** `subagent_implementer_report` / `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review` 4 类 per-task evidence。`forgeue_finish_gate.py` 从 evidence frontmatter `triggered_by_command` 字段判定 dispatch mode,direct 路径无该 audit field → 不报缺失 4 类 subagent evidence。
- **`followon_continuity` 字段**(自 `centralize-followon-backlog-registry` 起):archive-stage evidence(`verification/finish_gate_report.md` / `review/superpowers_review.md` final / `notes/retrospective.md`)MUST 含此 13th conditional 字段(4-list:`inherited` / `cancelled_superseded` / `cancelled_not_applicable` / `cancelled_completed`);非 archive-stage evidence(tdd_log / debug_log)可空。

## Decision Delegation

本命令在 ForgeUE Integrated AI Change Workflow **S3→S4-S5(apply direct,fallback 路径)** 阶段触发。Claude controller 默认按 design.md `D-AutonomyBoundary` + `D-FenceTaxonomy`(Fence #1-#6 trigger keyword 真源)决策升级路径:

**默认自主路径**(`autonomy_decision: claude_codex_concurred` 常规实施 / `user_required` 当 micro-task 边界超 scope):
- 跑 codex plan review hook + 写 `review/plan_cross_check.md`
- 调 Superpowers `executing-plans` + `test-driven-development`(无 subagent dispatch,Claude 主体实施)
- 越界检测 + writeback-check + 推进 S5(cross-check `disputed_open: 0` + Level 0 PASS)

**必须升级用户的 boundary fence**:
- **Fence #1 不可逆**:本命令不进 isolated worktree / 无 squash merge 步骤;直接主 worktree 提交 → 需确认提交内容
- **Fence #2 跨 change**:越界检测发现改动超 design.md scope 且需同步修改其他 change 文档 → 升级确认
- **Fence #3 review 冲突**:codex plan review 返回 `disputed_open > 0` 无法解决 → 升级用户裁决
- **Fence #4 用户约束**:用户指定 task 执行顺序或范围限制 → 升级确认
- **Fence #5 钱**:task 实施中需触发 L2 vendor API paid call(opt-in)→ 升级确认
- **Fence #6 安全**:task 实施中需 read `.env` / 敏感凭证 → 升级确认

evidence frontmatter MUST 含 `autonomy_decision` 字段,值取自 `{claude_autonomous, claude_codex_concurred, user_required, user_overrode}`。`claude_codex_concurred` MUST 配套 `codex_review_ref` 字段。

**References**

- `design.md` §4 commands 表(`/forgeue:change-apply-direct` 行)— hook + 越界检测 真源
- `design.md` §3 Cross-check Protocol(plan_cross_check 同协议)
- `forgeue_integrated_ai_workflow.md` §B.4 / §B.6(direct vs subagent 路径分流)/ §E(原 §D 在 enhance-workflow-automation change 后顺延)
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
