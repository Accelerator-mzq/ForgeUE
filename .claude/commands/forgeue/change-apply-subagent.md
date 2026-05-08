---
name: "ForgeUE: Change Apply (Subagent)"
description: S3→S4-S5;invoke superpowers:subagent-driven-development + 4 类 per-task evidence + budget tracker informational
category: ForgeUE Workflow
tags: [forgeue, workflow, S3-to-S5, apply, subagent]
---

S3→S4-S5 transition(default 路径,自 `adopt-subagent-driven-development` change 起):执行 execution_plan + micro_tasks 中的代码改动,通过 invoke `superpowers:subagent-driven-development` skill 派 fresh subagent per task(implementer + spec compliance reviewer + code quality reviewer)+ 全 task 完成后 final reviewer subagent;每 task 4 类 evidence 落 `execution/` + `review/`;ADR-009 token-budget tracker informational + soft WARNING(`tools/forgeue_subagent_budget.py`)。

**Input**: 必须指定 change name(`/forgeue:change-apply-subagent <id>`)。

**适用场景**: 多 micro-task / 需要强 review checkpoint;轻量 change(< 3 micro-task)/ budget 紧张时改走 `/forgeue:change-apply-direct`。

## Preflight(D-PreflightProtocol)

实施 Steps 之前 controller MUST 顺序完成以下 3 个 preflight 检查;任一 fail → 命令 abort + 详细错误,不进入 Steps 主流程。每项均要求在 evidence frontmatter 留 audit 字段。

> **Worktree consent**:沿 Superpowers upstream `using-git-worktrees` SKILL 自家 consent gate;ForgeUE 不加任何强制层(`retire-parallel-and-worktree-fully` retire ADR-011/012/013 worktree 强制层)。controller 可在 dispatch 前自由 invoke `Skill(superpowers:using-git-worktrees)` 决定是否 isolation;default decline → main repo cwd。

### Preflight Skill Cascade(D-SkillCascadeCheck)

实施前 controller MUST 验证主 SKILL(`superpowers:subagent-driven-development`)所有 declared dependency 已被 invoke;漏 invoke 立即 abort。

强制项(在 dispatch 第一个 implementer subagent **之前**执行):

```bash
python tools/forgeue_skill_cascade_check.py \
    --skill superpowers:subagent-driven-development \
    --invoked superpowers:test-driven-development,superpowers:requesting-code-review,superpowers:finishing-a-development-branch,subagent-driven-discipline
```

- exit 0 → cascade OK,记录 invoked skill 列表
- exit 5 → missing dependency → 命令 abort + 提示主动 invoke 缺失 SKILL 后 retry

evidence frontmatter MUST 加 `skill_cascade_audit` 字段(对象,含 `invoked_skills` list + `cascade_check_pass_at` ISO 8601 timestamp);`forgeue_finish_gate.py::_check_skill_cascade` fence 守门 audit。

### Preflight Task Granularity(D-TaskGranularityDeclaration)

Controller MUST 在 dispatch 前显式声明本次 task 粒度,枚举值 `phase` / `per-file` / `sub-task`:

- `phase` — 整个 phase(如 P0/P1/P2)整体作为 1 implementer dispatch(本命令常用模式)
- `per-file` — 每个修改文件 1 implementer dispatch
- `sub-task` — tasks.md 每个 `- [ ] X.Y` 1 implementer dispatch(细粒度 fresh context)

evidence frontmatter MUST 加 `task_granularity: <value>` 字段;`forgeue_finish_gate.py::_check_task_granularity` fence 守门。

### Preflight 协议版本标记(D-ProtocolVersionMigration)

evidence frontmatter MUST 加 `runtime_enforcement_protocol_version: v1` 字段。此字段触发 v1 advisory fence(`skill_cascade` / `round_fix_continuity` / `task_granularity`)。无字段视为 pre-v1 legacy → 全 fence pass-through(archived ADR-010 时期 evidence 兼容)。

**Active 路径 evidence + present-but-invalid value**(`v2` / `v3` / typo / null / empty / `v4`)→ BLOCKER `unknown_protocol_version`(沿 D-ActiveVsArchivedReplayBoundary;`forgeue_finish_gate.py` `check_frontmatter_protocol` 内联 inline check)。**Archived 路径 evidence + 任何 unknown value** → legacy pass-through(归档不动;沿 D-ArchivedReplayCompat)。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`(同 change-plan 步骤 1)。
2. **绑定 active change** — abort if missing。
3. **检查 S3 进入条件**:`execution/execution_plan.md` + `execution/micro_tasks.md` 落盘;上轮 writeback-check exit 0。
4. **冻结 plan cross-check `## A`** — Claude 在调用 codex 之前写好 `review/plan_cross_check.md` `## A`(同 change-plan 协议)。
5. **codex plan review hook**(claude-code + plugin REQUIRED;否则 OPTIONAL):
   - 跑 `/codex:adversarial-review --background "<plan focus>"`
   - 输出落 `review/codex_plan_review.md`(`evidence_type: codex_plan_review`)
6. **Claude 写 plan cross-check `## B/C/D`**(沿 design.md §3 Cross-check Protocol;独立验证 file:line)。
7. **快照 active change artifacts**:`git add openspec/changes/<id>/`(含 `proposal.md` / `design.md` / `tasks.md` / `specs/<cap>/spec.md` / `notes/pre_p0/*` / 任何已生成的 `execution/` / `review/` evidence)+ `git commit -m "wip: snapshot active change artifacts"`(在 main repo dev branch 直接 commit)。
8. **invoke `superpowers:subagent-driven-development` skill**(D-SkillInvoke / D-TaskInput):
    - 主 session Claude 从 `execution/micro_tasks.md` extract task list
    - 主 session Claude 从 `execution/execution_plan.md` 提取 per-task context(包含 design.md modules / 接口字段 / 测试要求)
    - **完整文本作为 prompt 内容传 implementer subagent**(沿 SKILL.md Red Flag "Make subagent read plan file (provide full text instead)")
    - subagent **不被授权**读 `execution/micro_tasks.md` / `execution/execution_plan.md` 任何 plan 文件 — 仅接收主 session 提取后的完整 prompt 文本
    - `tasks.md#X.Y` 锚点引用作 audit trail 进 evidence frontmatter `contract_refs`,**不**直接进入 subagent prompt(subagent 不知道 tasks.md 存在)
    - skill 内部协议(implementer / spec reviewer / code quality reviewer prompt 模板)由 Superpowers 自管,ForgeUE 不复制 / 不引用
    - **Sub-step 8.x: Model tier 显式选择(沿 `subagent-driven-discipline` skill §1)**:每个 dispatch 前 controller MUST 按 discipline §1 28-subtype × model tier 表选 model,且显式在 `Agent` tool 调用传 `model:` 参数(不依赖 parent session inherit default)。Quick reference:

      | Subagent role | discipline §1 subtype | model 默认 |
      |---|---|---|
      | implementer(完整 plan inline)| §1.1.1 mechanical | `haiku` |
      | implementer(pattern matching)| §1.1.2 | `haiku` 或 `sonnet` |
      | implementer(multi-file integration)| §1.1.3 | `sonnet` |
      | implementer(algorithmic / architectural design)| §1.1.4 / §1.1.5 | `opus` MANDATORY |
      | spec_reviewer(string matching)| §1.2.1 / §1.2.2 | `haiku` |
      | spec_reviewer(cross-phase reasoning)| §1.2.3 | `sonnet` |
      | code_quality(style / lint)| §1.3.1 | `haiku` |
      | code_quality(runtime correctness)| §1.3.4 | `sonnet` MANDATORY |
      | final reviewer(cross-phase consistency)| §1.3.3 + §1.3.4 | `sonnet` |
      | doc-sync(mechanical replace)| §1.5.1 | `haiku` 或 direct(no subagent)|
      | doc-sync(semantic rewrite)| §1.5.2 | `sonnet` |

      完整 28-subtype 决策见 `subagent-driven-discipline` skill §1。Override 路径:若 task subtype 难判 / 跨多 subtype,controller 可选 higher tier(如把 §1.1.2 default `haiku` 升 `sonnet`),但 evidence body Token usage 段必须显式记录决策理由。
9. **每 task 完成后 evidence 收口**(D-EvidenceSchema 4 类 evidence):
    - 主 session Claude 把每个 subagent return 落盘为 4 类 per-task evidence 文件(全部 12-key frontmatter):
      - `execution/task_<n>_implementer.md` — `evidence_type: subagent_implementer_report`
      - `execution/task_<n>_spec_review.md` — `evidence_type: subagent_spec_review`
      - `execution/task_<n>_code_quality_review.md` — `evidence_type: subagent_code_quality_review`
    - 全部 task 完成后 final reviewer return 落 `review/subagent_final_review.md` — `evidence_type: subagent_final_review`
    - **所有 4 类 evidence frontmatter 必含额外 audit 字段** `triggered_by_command: change-apply-subagent`(`forgeue_finish_gate.py` 完整性检查从此字段判定 dispatch mode)
    - **Token usage 写 evidence body 末尾段**(12-key frontmatter 不含 token / model / usd 字段):
      - 段标题 `## Token usage`
      - 段内含 `input_tokens=N` / `output_tokens=M` / `model=<name>` / `estimated_usd=$X.XX` / `data_source=<source>`
      - 数据来自 Task tool return 的 token usage 字段;若不可获取 → `data_source: estimated only, not gate-grade`
10. **budget record(每次 dispatch return 后)**(D-ADR009):
    - 调 `python tools/forgeue_subagent_budget.py --change <id> --record --task-n <n> --subagent-type <implementer|spec_review|code_quality_review|final_review> --tokens-input <N> --tokens-output <M> --usd <X> --model <name>`
    - 参数从 Task tool return 的 token usage **直接传**,**不**从 evidence frontmatter 读取
    - 工具仅 informational + soft WARN,exit 0;超 `FORGEUE_SUBAGENT_BUDGET_WARN_USD`(default `$2.0`)stdout 打 `[WARN]` 行
    - 追加 JSON Lines 到 `verification/subagent_budget.log`
11. **越界检测**(命令字面契约要求):
    - `git diff` vs design.md 列出的 modules
    - 若改动文件超出 design.md scope → 报告越界 + 建议:回写 design.md scope 或缩窄改动
12. **回写检测** — `python tools/forgeue_change_state.py --change <id> --writeback-check --json`:
    - DRIFT type 3(`evidence_contradicts_contract`):per-task evidence 与 design.md 接口不一致 → exit 5
    - DRIFT type 4(`evidence_exposes_contract_gap`):per-task evidence 揭示 design.md 异常段缺失 → exit 5
    - 出现 DRIFT → 回写 design.md 或标 `disputed-permanent-drift`
13. **状态推进** — 所有 micro-task done(全部 4 类 evidence 齐)+ Level 0 PASS + writeback-check exit 0 + cross-check `disputed_open: 0` + 越界检测 in-scope → 进 S5。

**Output Format**

```
## ForgeUE Change Apply Subagent: <change-id> (S3→S4-S5)

### codex plan review
- review/codex_plan_review.md: <findings>
- review/plan_cross_check.md: disputed_open=<N>

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

**Evidence Frontmatter Template (v1 baseline)**

每个 per-task evidence 和 final reviewer evidence MUST 含以下 12-key frontmatter + v1 advisory audit 字段:

```yaml
---
change_id: <change-id>
stage: S4-S5
evidence_type: subagent_implementer_report | subagent_spec_review | subagent_code_quality_review | subagent_final_review
contract_refs:
  - openspec/changes/<id>/tasks.md#X.Y
  # ... add more as needed (block-list YAML;_common.parse_frontmatter 不支持 flow-list `[...]`)
aligned_with_contract: true | false
detected_env: <env_detect_result>
triggered_by: /forgeue:change-apply-subagent
codex_plugin_available: true | false
# --- 4 个 conditional key(仅 aligned_with_contract: false 时必填) ---
drift_decision: written-back-to-design | written-back-to-tasks | written-back-to-proposal | disputed-permanent-drift
writeback_commit: <sha>(若 drift_decision != disputed-permanent-drift)
drift_reason: <reason>
reasoning_notes_anchor: <file>:<line>
# --- v1 advisory audit 字段 ---
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - subagent-driven-discipline
    # ... add more as needed (block-list)
  cascade_check_pass_at: <ISO-8601-timestamp>
task_granularity: phase | per-file | sub-task
subagent_continuity:  # round 2+ fix 同 implementer / 同 reviewer 一致性
  round_1_implementer_id: <agent-id>
  round_2_fix_implementer_id: <agent-id>  # MUST same as round_1
  round_1_reviewer_id: <agent-id>
  round_2_review_reviewer_id: <agent-id>  # MUST same as round_1_reviewer
autonomy_decision: claude_codex_concurred | claude_autonomous | user_required | user_overrode
codex_review_ref: <reference>(若 autonomy_decision == claude_codex_concurred)
# --- followon_continuity(可空字段;archive 阶段 evidence required;非 archive evidence 可空)---
followon_continuity:  # 自 centralize-followon-backlog-registry 起;仅 archive-stage evidence 强制
  inherited: [<followon-id>, ...]
  cancelled_superseded: [{id: ..., supersedes: <new-change-id>}, ...]
  cancelled_not_applicable: [{id: ..., reason: <enum>+free-form}, ...]
  cancelled_completed: [{id: ..., commit: <commit-ref>}, ...]
---
```

**Guardrails**

- **必绑 active change**。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**(同 change-plan;markdown lint fence 守门)。
- **`## A` 冻结**(plan_cross_check.md 同样适用;Claude 写 `## A` 必须在调 codex **之前**完成,禁止看完 codex 后回填)。
- **越界检测是字面契约要求**(design.md §4):改动超 design.md scope 必须阻断或回写 design.md,**不可静默扩大 scope**。
- **evidence 不能成新规范源**:per-task evidence 暴露的 contract 漏洞必须回写到 design.md / proposal.md / tasks.md。
- **必跑 writeback 检测**;DRIFT type 3/4 阻断 S5。
- **(D-SkillInvoke)不复制 / 不引用 implementer-prompt.md / spec-reviewer-prompt.md / code-quality-reviewer-prompt.md 文本**(由 Superpowers 自管;ForgeUE 仅做 evidence wrapper)。
- **(D-TaskInput)subagent 不被授权读 micro_tasks.md / execution_plan.md**;主 session Claude 必须 extract 完整文本作为 prompt 内容传入(沿 SKILL.md Red Flag "Make subagent read plan file (provide full text instead)")。
- **多 implementer subagent 串行 dispatch only**(沿 SKILL.md Red Flag "Never dispatch multiple implementation subagents in parallel"):本命令仅接受 fresh subagent per task,**禁止**并行。

## Decision Delegation

本命令在 ForgeUE Integrated AI Change Workflow **S3→S4-S5(apply subagent)** 阶段触发。Claude controller 默认按 design.md `D-AutonomyBoundary` + `D-FenceTaxonomy`(Fence #1-#6 trigger keyword 真源)决策升级路径:

**默认自主路径**(`autonomy_decision: claude_codex_concurred` 常规实施 / `user_required` 每 task 边界 review):
- 跑 codex plan review hook + 写 `review/plan_cross_check.md`
- snapshot active change artifacts(commit on main repo dev branch)
- dispatch `superpowers:subagent-driven-development` 串行 per-task(implementer + spec_review + code_quality_review + final_review)
- 收口 4 类 per-task evidence + 越界检测 + writeback-check
- cross-check `disputed_open: 0` + Level 0 PASS → 自主推进 S5

**必须升级用户的 boundary fence**:
- **Fence #1 不可逆**:`git push` / archive change / `git reset --hard` → 升级确认;每 task 完成的 mark-complete 动作(无跨 change 影响)→ 自主执行
- **Fence #2 跨 change**:越界检测发现改动超出 design.md scope 且需同步修改其他 change 文档 → 升级确认
- **Fence #3 review 冲突**:codex plan review 返回与 Claude 立场 disputed 且 `plan_cross_check.md` 无法解决(`disputed_open > 0`) → 升级用户裁决
- **Fence #4 用户约束**:用户指定 task 执行顺序或范围限制 → 升级确认
- **Fence #5 钱**:task 实施中需触发 L2 vendor API paid call(mesh.generation / live ComfyUI 等,opt-in 场景)→ 升级确认
- **Fence #6 安全**:task 实施中需 read `.env` / FORGEUE_COMFY_SCRIPTS_DIR 等 secret → 升级确认

evidence frontmatter MUST 含 `autonomy_decision` 字段,值取自 `{claude_autonomous, claude_codex_concurred, user_required, user_overrode}`。`claude_codex_concurred` MUST 配套 `codex_review_ref` 字段。

**References**

- `design.md` §D-AutonomyBoundary / §D-FenceTaxonomy / §D-SkillInvoke / §D-TaskInput / §D-ADR009(本命令 hook 真源)
- `forgeue_integrated_ai_workflow.md` §B.6 subagent-driven-development 集成边界
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
- Superpowers skills: `superpowers:subagent-driven-development`(default dispatch)/ `superpowers:using-git-worktrees`(OPTIONAL — controller 自由 invoke)
