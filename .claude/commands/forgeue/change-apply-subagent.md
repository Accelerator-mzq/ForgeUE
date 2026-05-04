---
name: "ForgeUE: Change Apply (Subagent)"
description: S3→S4-S5;invoke superpowers:subagent-driven-development + 4 类 per-task evidence + budget tracker informational
category: ForgeUE Workflow
tags: [forgeue, workflow, S3-to-S5, apply, subagent]
---

S3→S4-S5 transition(default 路径,自 `adopt-subagent-driven-development` change 起):执行 execution_plan + micro_tasks 中的代码改动,通过 invoke `superpowers:subagent-driven-development` skill 派 fresh subagent per task(implementer + spec compliance reviewer + code quality reviewer)+ 全 task 完成后 final reviewer subagent;每 task 4 类 evidence 落 `execution/` + `review/`;ADR-009 token-budget tracker informational + soft WARNING(`tools/forgeue_subagent_budget.py`)。

**Input**: 必须指定 change name(`/forgeue:change-apply-subagent <id>`)。

**适用场景**: 多 micro-task / 需要强 review checkpoint;轻量 change(< 3 micro-task)/ budget 紧张时改走 `/forgeue:change-apply-direct`。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`(同 change-plan 步骤 1)。
2. **绑定 active change** — abort if missing。
3. **检查 S3 进入条件**:`execution/execution_plan.md` + `execution/micro_tasks.md` 落盘;上轮 writeback-check exit 0。
4. **冻结 plan cross-check `## A`** — Claude 在调用 codex 之前写好 `review/plan_cross_check.md` `## A`(同 change-plan 协议)。
5. **codex plan review hook**(claude-code + plugin REQUIRED;否则 OPTIONAL):
   - 跑 `/codex:adversarial-review --background "<plan focus>"`
   - 输出落 `review/codex_plan_review.md`(`evidence_type: codex_plan_review`)
6. **Claude 写 plan cross-check `## B/C/D`**(沿 design.md §3 Cross-check Protocol;独立验证 file:line)。
7. **commit active change artifacts 到当前分支**(F1 修复 — design.md D-Worktree-Detail 第 1 项):
   - `git add openspec/changes/<id>/`(含 `proposal.md` / `design.md` / `tasks.md` / `specs/<cap>/spec.md` / `notes/pre_p0/*` / 任何已生成的 `execution/` / `review/` evidence)
   - `git commit -m "wip: snapshot active change artifacts before isolated worktree"`
   - **必要原因**:`git worktree add` 不复制 untracked / unstaged 文件,跨 worktree 不可见;不 commit 则 isolated worktree 内 active change 目录为空,subagent dispatch 拿不到 plan / micro_tasks 文本
8. **创建 isolated worktree**(D-Worktree-Detail 第 2 项):
   - invoke `superpowers:using-git-worktrees` skill 起 isolated worktree
   - worktree 路径例 `<repo>-worktrees/<change-id>/`(由 skill 决定具体位置;跟随 SKILL.md "smart directory selection")
9. **cwd 切换到 isolated worktree**(D-Worktree-Detail 第 3 项):
   - `cd` 到 isolated worktree
   - **所有后续命令(本命令 step 10+ 的 dispatch / evidence 落盘 / 越界检测 / 回写检测;后续 `/forgeue:change-verify` Level 0 / `/forgeue:change-review` / `/forgeue:change-doc-sync` / `/forgeue:change-finish` 全部以该 worktree 为 cwd 执行)**
   - **主 worktree 不能跨 worktree 检查 isolated worktree 的 evidence**(沿 D-Worktree-Detail 第 6 项 "条件透明")
10. **invoke `superpowers:subagent-driven-development` skill**(D-SkillInvoke / D-TaskInput 重写):
    - 主 session Claude 从 `execution/micro_tasks.md` extract task list
    - 主 session Claude 从 `execution/execution_plan.md` 提取 per-task context(包含 design.md modules / 接口字段 / 测试要求)
    - **完整文本作为 prompt 内容传 implementer subagent**(沿 SKILL.md Red Flag "Make subagent read plan file (provide full text instead)")
    - subagent **不被授权**读 `execution/micro_tasks.md` / `execution/execution_plan.md` 任何 plan 文件 — 仅接收主 session 提取后的完整 prompt 文本
    - `tasks.md#X.Y` 锚点引用作 audit trail 进 evidence frontmatter `contract_refs`,**不**直接进入 subagent prompt(subagent 不知道 tasks.md 存在)
    - skill 内部协议(implementer / spec reviewer / code quality reviewer prompt 模板)由 Superpowers 自管,ForgeUE 不复制 / 不引用
11. **每 task 完成后 evidence 收口**(D-EvidenceSchema 4 类 evidence):
    - 主 session Claude 把每个 subagent return 落盘为 4 类 per-task evidence 文件(全部 12-key frontmatter):
      - `execution/task_<n>_implementer.md` — `evidence_type: subagent_implementer_report`
      - `execution/task_<n>_spec_review.md` — `evidence_type: subagent_spec_review`
      - `execution/task_<n>_code_quality_review.md` — `evidence_type: subagent_code_quality_review`
    - 全部 task 完成后 final reviewer return 落 `review/subagent_final_review.md` — `evidence_type: subagent_final_review`
    - **所有 4 类 evidence frontmatter 必含额外 audit 字段** `triggered_by_command: change-apply-subagent`(F2 修复;`forgeue_finish_gate.py` 完整性检查从此字段判定 dispatch mode,**不**依赖 helper marker file)
    - **Token usage 写 evidence body 末尾段**(F5 修复 — 12-key frontmatter 不含 token / model / usd 字段):
      - 段标题 `## Token usage`
      - 段内含 `input_tokens=N` / `output_tokens=M` / `model=<name>` / `estimated_usd=$X.XX` / `data_source=<source>`
      - 数据来自 Task tool return 的 token usage 字段;若不可获取 → `data_source: estimated only, not gate-grade`,且**不**追加到正式 `verification/subagent_budget.log`
12. **budget record(每次 dispatch return 后)**(D-ADR009):
    - 调 `python tools/forgeue_subagent_budget.py --change <id> --record --task-n <n> --subagent-type <implementer|spec_review|code_quality_review|final_review> --tokens-input <N> --tokens-output <M> --usd <X> --model <name>`(F6 修复:6 必填 args 沿 forgeue_subagent_budget._validate_record_args 实装)
    - 参数从 Task tool return 的 token usage **直接传**,**不**从 evidence frontmatter 读取(沿 F5 修复)
    - 工具仅 informational + soft WARN,exit 0;超 `FORGEUE_SUBAGENT_BUDGET_WARN_USD`(default `$2.0`)stdout 打 `[WARN]` 行
    - 追加 JSON Lines 到 `verification/subagent_budget.log`
13. **越界检测**(命令字面契约要求,round-2 H4.1 修过的字段;以 isolated worktree 为 cwd):
    - `git diff` vs design.md 列出的 modules
    - 若改动文件超出 design.md scope → 报告越界 + 建议:回写 design.md scope 或缩窄改动
14. **回写检测** — `python tools/forgeue_change_state.py --change <id> --writeback-check --json`(以 isolated worktree 为 cwd):
    - DRIFT type 3(`evidence_contradicts_contract`):per-task evidence 与 design.md 接口不一致 → exit 5
    - DRIFT type 4(`evidence_exposes_contract_gap`):per-task evidence 揭示 design.md 异常段缺失 → exit 5
    - 出现 DRIFT → 回写 design.md 或标 `disputed-permanent-drift`
15. **状态推进** — 所有 micro-task done(全部 4 类 evidence 齐)+ Level 0 PASS + writeback-check exit 0 + cross-check `disputed_open: 0` + 越界检测 in-scope → 进 S5。
16. **squash merge / cherry-pick + worktree 清理**(F1 修复 — D-Worktree-Detail 第 4 项):
    - 全部 micro-task done + Level 0 全绿 + finish_gate exit 0 后(通常本命令在 step 15 状态推进,`/forgeue:change-finish` 跑完后再做本步)
    - **squash merge 或 cherry-pick** isolated worktree 全部 commits(含 evidence 落盘 commits)回主分支
    - 然后 `git worktree remove <isolated-path>` 清理
    - **禁止** force-push 或 evidence 文件手工 cp 到主 worktree(违 D-Worktree-Detail 协议)

**Output Format**

```
## ForgeUE Change Apply Subagent: <change-id> (S3→S4-S5)

### codex plan review
- review/codex_plan_review.md: <findings>
- review/plan_cross_check.md: disputed_open=<N>

### Worktree
- isolated worktree path: <path>
- cwd: <isolated worktree>
- commit before worktree: <sha>

### Implementation (subagent-driven-development)
- micro-tasks done: X/Y
- subagent dispatches: <N>(implementer + spec_review + code_quality_review per task)
- per-task evidence: execution/task_<n>_*.md
- final reviewer: review/subagent_final_review.md
- budget record: verification/subagent_budget.log

### Boundary check
- in-scope vs design.md modules: <PASS | OUT-OF-SCOPE: <files>>

### Writeback check
- DRIFT count: <N>; types: <list>
- next: <S5 ready | blocked + reason>
```

**Guardrails**

- **必绑 active change**。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**(同 change-plan;Pre-P0 是 fuse change 一次性附录例外,本命令不豁免;markdown lint fence 守门)。
- **`## A` 冻结**(plan_cross_check.md 同样适用;Claude 写 `## A` 必须在调 codex **之前**完成,禁止看完 codex 后回填)。
- **越界检测是字面契约要求**(design.md §4 / round-2 H4.1 修过):改动超 design.md scope 必须阻断或回写 design.md,**不可静默扩大 scope**。
- **evidence 不能成新规范源**:per-task evidence 暴露的 contract 漏洞必须回写到 design.md / proposal.md / tasks.md。
- **必跑 writeback 检测**;DRIFT type 3/4 阻断 S5。
- **(D-SkillInvoke 新增)不复制 / 不引用 implementer-prompt.md / spec-reviewer-prompt.md / code-quality-reviewer-prompt.md 文本**(由 Superpowers 自管;ForgeUE 仅做 evidence wrapper;若需了解 subagent 内部协议直接读 plugin 源)。
- **(D-TaskInput 新增)subagent 不被授权读 micro_tasks.md / execution_plan.md**;主 session Claude 必须 extract 完整文本作为 prompt 内容传入(沿 SKILL.md Red Flag "Make subagent read plan file (provide full text instead)")。
- **(D-Worktree-Detail 新增)isolated worktree 内执行所有后续命令**;evidence 同步回主分支前**禁止删 worktree**;主 worktree 不能跨 worktree 检查 isolated worktree 的 evidence。
- **(F2 audit)evidence frontmatter 必含 `triggered_by_command: change-apply-subagent`**(在标准 12-key 之外的 audit 字段;`forgeue_finish_gate.py` 从此字段判定 dispatch mode → 4 类 subagent_* evidence_type 全部 REQUIRED;**不**依赖 helper marker file)。
- **(F5 audit)Token / model / usd 不进 12-key frontmatter**;以 evidence body 末尾 `## Token usage` 段记录;`forgeue_subagent_budget.py --record` 参数从 Task tool return 直接传,不从 frontmatter 读。
- **多 implementer subagent 串行 dispatch only**(沿 SKILL.md Red Flag "Never dispatch multiple implementation subagents in parallel"):本命令仅接受 fresh subagent per task,**禁止**并行。

## Decision Delegation

本命令在 ForgeUE Integrated AI Change Workflow **S3→S4-S5(apply subagent)** 阶段触发。Claude controller 默认按 D-AutonomyBoundary 6 类 fence 决策升级路径:

**默认自主路径**(`autonomy_decision: claude_codex_concurred` 常规实施 / `user_required` 每 task 边界 review):
- 跑 codex plan review hook + 写 `review/plan_cross_check.md`
- 创建 isolated worktree + commit change artifacts 快照
- dispatch `superpowers:subagent-driven-development` 串行 per-task(implementer + spec_review + code_quality_review + final_review)
- 收口 4 类 per-task evidence + 越界检测 + writeback-check
- cross-check `disputed_open: 0` + Level 0 PASS → 自主推进 S5

**必须升级用户的 boundary fence**:
- **Fence #1 不可逆**:squash merge isolated worktree 回主分支 / `git worktree remove` 清理 → 升级确认;每 task 完成的 mark-complete 动作(无跨 change 影响)→ 自主执行
- **Fence #2 跨 change**:越界检测发现改动超出 design.md scope 且需同步修改其他 change 文档 → 升级确认
- **Fence #3 review 冲突**:codex plan review 返回与 Claude 立场 disputed 且 `plan_cross_check.md` 无法解决(`disputed_open > 0`) → 升级用户裁决
- **Fence #4 用户约束**:用户指定 task 执行顺序或范围限制 → 升级确认
- **Fence #5 钱**:task 实施中需触发 L2 vendor API paid call(mesh.generation / live ComfyUI 等,opt-in 场景)→ 升级确认
- **Fence #6 安全**:task 实施中需 read `.env` / FORGEUE_COMFY_SCRIPTS_DIR 等 secret → 升级确认

evidence frontmatter MUST 含 `autonomy_decision` 字段,值取自 `{claude_autonomous, claude_codex_concurred, user_required, user_overrode}`。`claude_codex_concurred` MUST 配套 `codex_review_ref` 字段。

**References**

- `design.md` §D-Worktree-Detail / §D-Default / §D-EvidenceSchema / §D-SkillInvoke / §D-TaskInput / §D-ADR009(本命令 hook 真源)
- `forgeue_integrated_ai_workflow.md` §B.6 subagent-driven-development 集成边界
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
- Superpowers skills: `superpowers:subagent-driven-development`(default dispatch)/ `superpowers:using-git-worktrees`(REQUIRED isolation)
