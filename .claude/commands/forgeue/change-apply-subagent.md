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

### Preflight Worktree(D-WorktreeEnforce)

实施前 isolated worktree 必须存在。此 preflight 通过 `python tools/forgeue_preflight_wrapper.py` 自管 worktree(不再 invoke `Skill(superpowers:using-git-worktrees)` 直接):

- **Bash 调用 wrapper**:
  ```bash
  python tools/forgeue_preflight_wrapper.py --change <change-id>
  ```
  - wrapper 创建 isolated worktree(git worktree subprocess)
  - stdout 返回 13-field receipt JSON(relative path)
  - 失败:exit 5 (env error) / exit 6 (path resolution error,需 cd 到 wrapper-managed worktree 后重试) / exit 7 (other)

- **capture receipt 和 worktree path**:
  - LLM 从 receipt JSON 复制 `worktree_path` 字段(绝对路径)到 evidence frontmatter
  - LLM 从 receipt JSON 复制 `receipt_path` 字段(相对路径)到 evidence frontmatter `worktree_receipt_path`
  - 若 exit 6:stderr 含 path resolution 提示;cd 到 wrapper-managed worktree 后重新调用 wrapper

- **cwd 切换到 isolated worktree**(沿 Step 9);后续 dispatch / evidence 落盘 / writeback 检测全部以该 worktree 为 cwd

- evidence frontmatter MUST 加 `worktree_path: <path>` + `worktree_receipt_path: <relative_path>` 字段(non-null);`forgeue_finish_gate.py::_check_worktree_path_v2` fence 守门(`triggered_by_command: change-apply-subagent` 触发强制)

Preflight 失败(wrapper exit != 0 / receipt JSON malformed / clean baseline test 不绿)→ 命令 abort。

### Preflight Skill Cascade(D-SkillCascadeCheck)

实施前 controller MUST 验证主 SKILL(`superpowers:subagent-driven-development`)所有 declared dependency 已被 invoke;漏 invoke 立即 abort。

强制项(在 Step 8 invoke `using-git-worktrees` 之后、Step 10 invoke `subagent-driven-development` 之前执行):

```bash
python tools/forgeue_skill_cascade_check.py \
    --skill superpowers:subagent-driven-development \
    --invoked superpowers:using-git-worktrees,superpowers:test-driven-development,superpowers:requesting-code-review,superpowers:finishing-a-development-branch
```

- exit 0 → cascade OK,记录 invoked skill 列表
- exit 5 → missing dependency → 命令 abort + 提示主动 invoke 缺失 SKILL 后 retry

evidence frontmatter MUST 加 `skill_cascade_audit` 字段(对象,含 `invoked_skills` list + `cascade_check_pass_at` ISO 8601 timestamp);`forgeue_finish_gate.py::_check_skill_cascade` fence 守门 audit。

### Preflight Task Granularity(D-TaskGranularityDeclaration)

Controller MUST 在 dispatch 前显式声明本次 task 粒度,枚举值 `phase` / `per-file` / `sub-task`:

- `phase` — 整个 phase(如 P0/P1/P2)整体作为 1 implementer dispatch(本命令常用模式)
- `per-file` — 每个修改文件 1 implementer dispatch(独立 file scope 时改走 `/forgeue:change-apply-parallel`)
- `sub-task` — tasks.md 每个 `- [ ] X.Y` 1 implementer dispatch(细粒度 fresh context)

evidence frontmatter MUST 加 `task_granularity: <value>` 字段;`forgeue_finish_gate.py::_check_task_granularity` fence 守门。

### Preflight 协议版本标记(D-ProtocolVersionMigration)

evidence frontmatter MUST 加 `runtime_enforcement_protocol_version: v1` 字段。此字段触发 4 fence(`skill_cascade` / `round_fix_continuity` / `task_granularity` / `worktree_path`)生效;无此字段的 evidence 视为 legacy,fence pass-through(archived enhance-workflow-automation 等历史 change replay 兼容)。

### Preflight Subagent Discipline(MANDATORY before any Skill(Task) dispatch)

Controller MUST 在 Step 10 dispatch 第一个 implementer subagent **之前**显式 invoke `Skill(subagent-driven-discipline)`,加载 skill 内容到 working context。

**Skill content 应用点**(controller 自检):

| Phase | 应用 skill 段 | 强制性 |
|---|---|---|
| **Dispatch 前** | §1 scenario taxonomy 选 model(显式传 `model:` 参数;不让 subagent inherit 父 session model)| MANDATORY |
| **Dispatch 前** | §2 cheap-model reliability prompt 元素(STRICT cwd verify + pre-verified data + specific verification list + phase boundary 显式 — 全 4 元素必含 reviewer prompt) | MANDATORY |
| **Dispatch 前** | §3.1 STRICT cwd verify section 必含 dispatch prompt | MANDATORY |
| **Dispatch 后(每 subagent return)** | §3.2 controller cross-verify(测试 count / commit SHA / branch / spec strings — 不接受 subagent self-report)| MANDATORY |
| **Phase complete(3-stage all ✅)** | §3.4.0 判定 Trigger Type → 跑对应 retrospect:Type 1 = 3-stage full(MANDATORY Opus full Q1-Q6) | MANDATORY |
| **Retrospect 任一 Yes** | §8 update protocol 加 case study + 视情况 §6 catalog + §1 subtype | MANDATORY |
| **Retrospect 全 No** | SKIP skill update — phase silent pass | OK |

**Discipline 缺失后果**(若 controller 漏 invoke 本 skill):
- Subagent inherit 父 session model(往往 Opus over-cost,如 Case 1 P0 的 6.7x cost over-budget 教训)
- Reviewer prompt open-ended → cheap model scope-bleed / 幻觉(如 Case 1 P1/P2 教训)
- Worktree-scope leak 无 detection(如 Case 1 P3 cwd 漂移到 dev branch 教训)
- Skill 不 auto-grow → 后续 change 重蹈覆辙

**Trigger** 时机(沿 §3.4.0 matrix):
- 本命令(`/forgeue:change-apply-subagent`)= **Type 1 3-stage full**(implementer + spec_reviewer + code_quality_reviewer 串行)
- Phase complete 后 controller MUST 跑 Type 1 retrospect(Opus actor;Q1-Q6 full)

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

10a. **dispatch implementer subagent 后立即 append dispatch ledger**(F1 round 2 inline writeback,post-dispatch capture):
     - Skill(Task) dispatch implementer subagent → capture return metadata → parse 真实 `agent_id`
     - Bash:
       ```bash
       python tools/forgeue_dispatch_ledger.py append \
           --change <change-id> \
           --agent-id <真实_agent_id_from_Skill_return> \
           --round 1 \
           --role implementer \
           --task-subject-hash $(echo -n "$TASK_SUBJECT" | sha256sum | cut -d' ' -f1)
       ```
     - 此步必须在 Skill dispatch **之后** 执行(post-dispatch order;capture 真实 agent_id 而非 synthetic UUID)
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

**Evidence Frontmatter Template (v2)**

每个 per-task evidence 和 final reviewer evidence MUST 含以下 12-key frontmatter + 8 个 runtime enforcement audit 字段:

```yaml
---
change_id: <change-id>
stage: S4-S5
evidence_type: subagent_implementer_report | subagent_spec_review | subagent_code_quality_review | subagent_final_review
contract_refs: ["openspec/changes/<id>/tasks.md#X.Y", ...]
aligned_with_contract: true | false
detected_env: <env_detect_result>
triggered_by: /forgeue:change-apply-subagent
codex_plugin_available: true | false
# --- 4 个 conditional key(仅 aligned_with_contract: false 时必填) ---
drift_decision: written-back-to-design | written-back-to-tasks | written-back-to-proposal | unresolved-permanent-drift
writeback_commit: <sha>(若 drift_decision != unresolved-permanent-drift)
drift_reason: <reason>
reasoning_notes_anchor: <file>:<line>
# --- 8 个 runtime enforcement audit 字段(v2) ---
runtime_enforcement_protocol_version: v2
triggered_by_command: change-apply-subagent
worktree_path: <absolute-path-from-receipt>
worktree_receipt_path: <relative-path-to-receipt.json>
dispatch_ledger_path: dispatch_ledger.jsonl
pre_dispatch_metadata: advisory
ledger_forgery_resistance: advisory
autonomy_decision: claude_codex_concurred | claude_autonomous | user_required | user_overrode
codex_review_ref: <reference>(若 autonomy_decision == claude_codex_concurred)
---
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

本命令在 ForgeUE Integrated AI Change Workflow **S3→S4-S5(apply subagent)** 阶段触发。Claude controller 默认按 design.md `D-AutonomyBoundary` + `D-FenceTaxonomy`(Fence #1-#6 trigger keyword 真源)决策升级路径:

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
