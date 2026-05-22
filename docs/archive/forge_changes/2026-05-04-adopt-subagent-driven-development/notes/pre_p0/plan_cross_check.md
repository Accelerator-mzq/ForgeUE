---
scope: plan-level (Pre-P0 manual rehearsal,沿 fuse-openspec-superpowers-workflow self-host 模式)
change_id: adopt-subagent-driven-development
codex_review_ref: notes/pre_p0/codex_review_round1.md
claude_plan_ref: proposal.md + design.md + tasks.md + specs/examples-and-acceptance/spec.md
codex_invocation: /codex:adversarial-review --background "<本 change 整体方案 + design.md 8 项 D 决议 + tasks.md self-host bootstrap 模式 + spec delta 3 ADDED Requirements>"
codex_model: gpt-5
codex_effort: high
detected_env: claude-code (Claude Code session)
triggered_by: forced (Pre-P0 一次性,plan §1.2-1.5 路径 A)
created_at: 2026-05-04T22:30:00+08:00
disputed_open: 0
resolved_at: 2026-05-04T23:15:00+08:00
writeback_commit: 2ec9cfd36e16a19b8f775b0dc902b9fa1b6a602c
note: |
  本 cross-check 是 plan-level 手工预演,非 S2/S3 正式 lifecycle-level cross-check。
  ## A. Claude's Decision Summary 段冻结于 codex 调用之前,Claude 不允许在写 ## B/C/D 时回填 ## A
  (沿 ForgeUE design.md §3 Cross-check Protocol 防 anchoring bias)。
  Pre-P0 一次性,disputed_open 由用户手工裁决,不依赖 forgeue_finish_gate.py(§5 才扩 enum)。
  本 change §4 命令实装后,后续 stage 走正式 cross-check 流程(`change-plan` / `change-apply-subagent` 内置)。
---

# Plan-level Cross-Check(Pre-P0 一次性)

## A. Claude's Decision Summary (frozen before codex run)

> 冻结时间:2026-05-04T22:30:00+08:00。
> Claude 不允许在写 ## B/C/D 时回填 ## A。
> 本段冻结的是 proposal.md / design.md / tasks.md / specs/examples-and-acceptance/spec.md 的当前状态决议,作为 codex review 的输入基线。

### A.1 8 项 D 决议(design.md ## Decisions 段冻结)

- **D-Worktree**(P1-a 用户拍板):解禁 `superpowers:using-git-worktrees`;`forgeue_integrated_ai_workflow.md` §B.3 表 `using-git-worktrees` 行从 `禁用` 改为 `REQUIRED for change-apply-subagent`;**纯文档级修改**,代码 0 改动(摸排已确认 7 处 `worktree` 字符串全在 docs/archived/SKILL.md;`tools/` + `src/framework/` 0 处硬编码)。Evidence:`docs/ai_workflow/forgeue_integrated_ai_workflow.md:147`(原"禁用"行)
- **D-Default**(P2-a + D1-b 用户拍板):`/forgeue:change-apply` 拆分为 `/forgeue:change-apply-subagent`(default subagent dispatch)+ `/forgeue:change-apply-direct`(executing-plans fallback);现 `change-apply.md` 标 deprecated 重定向 1 个 archive cycle。理由:用户根据 change 复杂度自然分流(small change 走 direct / 多 micro-task change 走 subagent),沿 §A.6 显式声明角色边界
- **D-EvidenceSchema**(D2-a 用户拍板):per-task evidence 扁平命名 `execution/task_<n>_{implementer,spec_review,code_quality_review}.md` + `review/subagent_final_review.md`;沿 `forgeue_finish_gate.py` line 60-62 frontmatter-indexed 范式(已证不依赖文件路径绑定);通过 review 的 task evidence 允许 body 一行 summary,未通过的 task MUST 完整 issues 列表
- **D-SkillInvoke**(用户独立指出):`change-apply-subagent` 命令直接 invoke `superpowers:subagent-driven-development` skill,**不**重写 / 不复制 / 不引用 skill 内部 3 个 prompt 模板(`implementer-prompt.md` / `spec-reviewer-prompt.md` / `code-quality-reviewer-prompt.md`),Superpowers 自管;ForgeUE 角色 = OpenSpec evidence wrapper,仅做收口
- **D-TaskInput**:`change-apply-subagent` 主 session Claude 从 `execution/micro_tasks.md` extract task list、从 `execution/execution_plan.md` 提取 per-task context,**完整文本作为 prompt 传 implementer subagent**(沿 `subagent-driven-development/SKILL.md` Red Flag "Make subagent read plan file (provide full text instead)");subagent 不被授权读 plan 文件
- **D-ADR008**(用户 informational 调整后):新增 ADR-009 把 token-budget 边界与 ADR-007 vendor API 双扣边界**根本切分**。ADR-007 拦截 mesh.generation 重试时双扣已完成 job(浪费);ADR-009 仅记录 LLM token 持续产生价值的消耗(打断 = 损失);两者**不是同一安全边界**
- **D-BudgetMode**(D3-a + 用户 informational 调整):`tools/forgeue_subagent_budget.py` 是 informational tracker,仅 `--status` / `--record` / `--json` + 超阈值 stdout `[WARN]` 行,**始终 `exit 0`**(I/O 异常 `exit 1` 例外),**不**做 hard gate / auto fallback;用户保留 dispatch 中断判断权(沿 ForgeUE memory `feedback_decisive_approval`)
- **D-SelfHost**(P3 / D4-a 用户拍板):本 change 自身用 subagent-driven-development 跑 dogfooding;Pre-P0 一次性附录(本文件 + `subagent_dogfood_protocol.md`)+ §3-§6 阶段 Claude 主 session 用 Task tool 手工模拟 subagent dispatch,沿 fuse-openspec-superpowers-workflow self-host 模式

### A.2 tasks.md 阶段大纲(冻结)

- §1 Pre-P0 self-host bootstrap(本文件 + dogfood protocol + codex hook + cross-check)
- §2 文档同步:**11 处编辑**(已扩充覆盖)
  - §2.1 + §2.1b:`forgeue_integrated_ai_workflow.md` §B.3 表 + §B.1 状态机表 S3/S4 行
  - §2.2:`forgeue_integrated_ai_workflow.md` 加新段 §B.6
  - §2.3:`forgeue_integrated_ai_workflow.md` §A.6 命令边界段
  - §2.4 + §2.4b + §2.4c:`docs/ai_workflow/README.md` §5 + §8 + repo 根 `README.md` line 380-388
  - §2.5 + §2.6:CLAUDE.md / AGENTS.md
  - §2.7:`.claude/skills/forgeue-integrated-change-workflow/SKILL.md`
  - §2.8 + §2.9:`docs/ai_workflow/forgeue_quickstart.md` 3 处 + `validation_matrix.md` SKIP
- §3 SRS / acceptance_report 加 ADR-009
- §4 ForgeUE 命令重构:新建 2 个 + deprecated 1 个
- §5 `forgeue_finish_gate.py` 扩 evidence_type enum 4 项 + fence test
- §6 `tools/forgeue_subagent_budget.py` 新建(stdlib only ~100 行)+ fence test
- §7 capability spec delta sync(自动)
- §8 Level 0 验证 + verify_report
- §9 S6 review(superpowers + codex adversarial)
- §10 Documentation Sync Gate + Finish Gate
- §11 Archive close-out(单 commit close + sync-specs + CHANGELOG [Unreleased] 加新条目)

### A.3 spec delta 3 个 ADDED Requirement(冻结)

`openspec/changes/adopt-subagent-driven-development/specs/examples-and-acceptance/spec.md`:

1. **Requirement: subagent-driven-development per-task evidence schema**:4 类 evidence_type + 文件命名 + 12-key frontmatter + 轻量化语义(通过 review 一行 summary;未通过完整 issues)+ 2 个 Scenario
2. **Requirement: change-apply-subagent 命令直接 invoke Superpowers skill**:不重写 prompt 模板 + plan 文件不进 subagent prompt + 2 个 Scenario
3. **Requirement: subagent token-budget tracker 是 informational 不是 enforcement**:工具 `exit 0` 始终 / 仅 stdout WARN / 与 ADR-007 边界对比 + 2 个 Scenario

### A.4 实施成本预估(冻结)

- **文档同步**:11 处编辑(§2 全部)
- **Python 代码**:1 工具新建(`forgeue_subagent_budget.py`,~100 行 stdlib)+ 1 工具扩展(`forgeue_finish_gate.py` evidence_type enum + 默认 path 表)+ 1 fence test 新建 + finish_gate fence test 4 个 case 新增
- **命令文件**:2 个新建(`change-apply-subagent.md` / `change-apply-direct.md`)+ 1 个改写为 deprecated banner
- **SRS / acceptance**:1 个 ADR(ADR-009)+ ADR 表加行
- **Subagent dispatch 估算**:30+ micro-task × 4 subagent ≈ 120 次 Task tool 调用(self-host dogfood);每次 Task tool 是一次 LLM 调用
- **Budget 估算**:按平均 $0.30/task × 30 task = $9.0(超 default WARN 阈值 $2.0,但 informational 不阻断)

### A.5 决策依据来源(冻结)

- 用户 P1-a / P2-a / P3 / D1-b / D2-a / D3-a / D4-a 拍板(对话历史)
- 用户 informational 调整(D-BudgetMode):"forgeue_subagent_budget.py 可以统计消耗量,但是不要禁止 subagent 功能,默认开启 subagent 功能,token 消耗异常只是给我警告"
- 用户独立提问 D-SkillInvoke:"这里不能直接使用 superpowers 的技能吗,还要单独调用 prompt"
- 摸排证据:`Grep "worktree"` 项目内 7 处全在 docs / archived / SKILL.md(代码 0 引用)→ D-Worktree 纯文档级
- 摸排证据:ADR-007 现役引用全部是 worker 双扣边界 → D-ADR008 边界切分有据

## B. Cross-check Matrix

> Codex review return at 2026-05-04T22:45:00+08:00(`notes/pre_p0/codex_review_round1.md`,verdict `needs-attention`,5 findings)。
> 5 条 finding 全部经 Claude 独立 file:line 验证(详 ## D.1),全部 verdict TRUE,Resolution = `accepted-codex`,disputed_open == 0。

| ID | Claude's choice(## A 冻结)| Codex's verdict | Codex's reasoning(摘要 + 引用) | Resolution | 修复操作 |
|---|---|---|---|---|---|
| F1 | D-Worktree:`change-apply-subagent` step 6.5 invoke `using-git-worktrees` skill 起 isolated worktree | **needs-attention [high]** | `tasks.md:65-69` step 6.5 只 invoke skill;step 7-10 没规定 controller cwd 切换 / active change artifacts 复制(全部 `??` untracked git worktree 不带)/ evidence 从 isolated 回主 worktree 同步策略 → subagent 看不到 contract / finish_gate 主 worktree 检查不到 evidence | `accepted-codex` | 回写 `design.md` D-Worktree-Detail + `tasks.md` §4.1 step 6.5/7/8/9-10 详细化 cwd / artifact 复制 / evidence 同步 + `tasks.md` §5.4 加 worktree fence test |
| F2 | D-EvidenceSchema:`change-apply-subagent` 路径 4 类 evidence REQUIRED;判定路径从 `notes/pre_p0/dispatch_mode.txt` 读 marker;缺失 finish_gate WARN | **needs-attention [high]** | `tasks.md:95-99` §5.3 marker 缺失只 WARN(不 FAIL);§4.1/4.2 命令创建 0 处写入 marker → 漏写 marker 即可绕过完整性 gate(可被 gate 漏检的路径) | `accepted-codex` | 回写 `design.md` D-EvidenceSchema:从命令生成的正式 evidence frontmatter 判定模式,不依赖 marker + `tasks.md` §4.1 step 8 evidence 落盘必含 dispatch mode 字段 + `tasks.md` §5.3 改判定规则 + §5.4 加 "marker missing 但 subagent 命令已执行" 必 fail 测试 |
| F3 | tasks.md §5 仅扩 `forgeue_finish_gate.py` evidence_type enum | **needs-attention [high]** | `tools/forgeue_change_state.py:369` + `:396` DRIFT detector `if ev_type not in ("tdd_log","debug_log","implementation_log"): continue` / `not in ("debug_log","tdd_log"): continue` → subagent_spec_review / code_quality_review 报出 contract gap / 越界实现 / 新决策时,writeback-check 仍 exit 0 | `accepted-codex` | 回写 `tasks.md` 加 §5.5(扩 `forgeue_change_state.py` DRIFT detector 4 个 evidence_type 接收 contract gap / missing anchor / decision / failure keyword)+ `tasks.md` §6 加 fence test 验证 subagent review body 中 gap 阻断 |
| F4 | D-Default:`FORGEUE_APPLY_MODE` env flag 不再需要,用户显式选择命令(design.md ## Decisions 段) | **needs-attention [medium]** | `proposal.md:49` 残留 "用户应根据 change 复杂度通过 FORGEUE_APPLY_MODE={subagent,direct} env flag 显式选择" 与 D-Default 自相矛盾;`subagent_dogfood_protocol.md` 表格也提 env/flag 切换 fallback | `accepted-codex` | 删 `proposal.md:49` FORGEUE_APPLY_MODE 残留 + 删 `subagent_dogfood_protocol.md §6` 表格中 env/flag 切换字眼,改为 "用户显式调用 `change-apply-direct`" + `tasks.md` 加 rg fence "FORGEUE_APPLY_MODE\|env / flag 切换" 在本 change 文件下为 0 |
| F5 | D-BudgetMode + dogfood §5:Pre-P0 §1-§5 不调 record;§6 实装后回填补 record 从 evidence frontmatter 估算 token 消耗 | **needs-attention [medium]** | `subagent_dogfood_protocol.md:125-127` §5 回填来自 frontmatter,但同文件 §4 12-key frontmatter 模板(line 100-118)没有 `tokens_input` / `tokens_output` / `usd` / `model` 字段 → 事后估算 = 不可审计成本日志 | `accepted-codex` | 回写 `subagent_dogfood_protocol.md §5`:Pre-P0 §1-§5 在 evidence body(不是 frontmatter / budget log)立即记录真实 token/model/usd 字段;**先实装** `forgeue_subagent_budget.py`(§6 提前到 §1.5 之后 / §2 之前)再开始 task-level dogfood;若无法获得真实 token,evidence 标 "人工估算,不进 gate / 阈值判断" + `design.md` D-BudgetMode 加边界声明 |

## C. Disputed Items Pending Resolution

```
disputed_open: 0
```

无 disputed-pending 项。5 条 finding 全部 `accepted-codex`,5 条全部回写。本段在用户 verdict 后保持 0,可进入 §1.5 前置检查。

## D. Verification Note

### D.1 独立验证(沿 ForgeUE memory feedback_verify_external_reviews)

逐条 file:line 实测,**不把 codex claim 当结论**:

- **F1 worktree cwd / artifact 同步缺失**:Read `tasks.md:60-82`(§4.1 完整 step 列表)— step 6.5 line 65 仅 `invoke superpowers:using-git-worktrees skill`;step 7-10 line 66-70 全部聚焦 dispatch + evidence 收口 + 越界检测,**0 处** 提及 controller cwd / active change artifacts 复制 / evidence 同步策略;`git status --short --untracked-files=all` 实测显示本 change 全部 7 个文件 `??` untracked。**TRUE,accepted-codex**。
- **F2 marker 缺失只 WARN + §4 命令未写入 marker**:Read `tasks.md:95-99`(§5.3 line 95)原文 `若文件不存在则 finish_gate 标 WARN(不 FAIL,因为旧 change 没这个标记)`;Read `tasks.md:62-73`(§4.1+§4.2 命令创建 step 列表)**0 处** 提及写入 `notes/pre_p0/dispatch_mode.txt`。**TRUE,accepted-codex**。
- **F3 forgeue_change_state.py DRIFT detector 漏 subagent evidence**:Read `tools/forgeue_change_state.py:365-399`(detect_drift_contradicts + detect_drift_gap)— line 369 `if ev_type not in ("tdd_log", "debug_log", "implementation_log"): continue`;line 396 `if fm.get("evidence_type") not in ("debug_log", "tdd_log"): continue`。Read `tasks.md` §5(line 83-99)— 只列 finish_gate enum 扩展,**0 处** 提及 forgeue_change_state.py DRIFT detector 扩展。**TRUE,accepted-codex**。
- **F4 FORGEUE_APPLY_MODE 残留**:Read `proposal.md:49` 原文 `用户应根据 change 复杂度通过 FORGEUE_APPLY_MODE={subagent,direct} env flag 显式选择(决议 D-Default 选 default subagent + env flag opt-out 到 direct)`。Read `design.md` ## Decisions D-Default 段原文 `FORGEUE_APPLY_MODE env flag 不再需要 — 用户**显式选择命令**`。**自相矛盾,TRUE,accepted-codex**。
- **F5 budget 回填靠 frontmatter 估算 token,frontmatter 无 token 字段**:Read `subagent_dogfood_protocol.md:125-127` §5 原文 `§6 实装完成后回填补 record(从 §1-§5 的 evidence 文件 frontmatter 估算 token 消耗)`;Read 同文件 §4 12-key frontmatter 模板(line 100-118)— 12 个字段:change_id / stage / evidence_type / contract_refs / aligned_with_contract / drift_decision / writeback_commit / drift_reason / reasoning_notes_anchor / detected_env / triggered_by / codex_plugin_available。**0 处 token / model / usd 字段。TRUE,accepted-codex**。

5/5 finding 验证全部 TRUE,Codex 给的 file:line 引用全部精确(无虚构、无 hand-wave)。

### D.2 修复完整性

5 条全部 `accepted-codex`,2026-05-04T23:30:00+08:00 完成回写到 contract artifact:

- [x] F1 → `design.md` D-Worktree-Detail 段扩展(7 项硬性步骤:commit untracked / 起 worktree / cwd 切换 / evidence 同步 / direct 路径不 worktree / 工具条件透明 / fence test)+ `tasks.md` §4.1 step 6.5 拆为 6.5/6.6/6.7 + 加 step 10.5 evidence 同步 + `tasks.md` §5.4 加 worktree fence test case
- [x] F2 → `design.md` D-EvidenceSchema 段扩展(`triggered_by_command: change-apply-subagent` audit 字段 + 不依赖 helper marker 的 finish_gate 判定规则)+ `tasks.md` §4.1 step 8 evidence frontmatter 必含 `triggered_by_command` + `tasks.md` §5.3 改判定规则(从 evidence frontmatter 扫描)+ §5.4 加 "marker missing 但 subagent 命令已执行" 必 fail 测试 + §8.3 改 finish_gate 描述去掉 dispatch_mode.txt
- [x] F3 → `tasks.md` 加 §5.5(扩 `forgeue_change_state.py:369` + `:396` DRIFT detector evidence_type 白名单 4 项)+ `tasks.md` §5.6 加 fence test(subagent review body gap / Critical issue / 越界 identifier 阻断 writeback-check exit 5)
- [x] F4 → 删 `proposal.md:49` FORGEUE_APPLY_MODE 残留(改"用户显式选择两个独立命令之一")+ 改 `subagent_dogfood_protocol.md §6` 表第 5 行 env/flag 字眼为"用户显式调用 change-apply-direct"+ `tasks.md` §10.5 加 rg fence(`FORGEUE_APPLY_MODE` 在本 change touched files 0 处)
- [x] F5 → 改 `subagent_dogfood_protocol.md §5`(Pre-P0 §1-§5 在 evidence body 立即记录真实 token / model / usd 段;`data_source: task_tool_return` / `manual_estimate` 区分;`manual_estimate` 不进正式 budget log)+ `design.md` D-BudgetMode 加 "Token / cost 字段不进 12-key frontmatter" 边界声明 + tasks.md §6.1 工具实装时一并约定 controller 直接传参不读 frontmatter

5 项回写完成,strict validate 仍 PASS;writeback_commit sha 由后续 git commit 留底,本文件本身在 commit 后 amend frontmatter 填该 sha(双 commit 模式)。

### D.3 进 §2 前置

- [x] disputed_open == 0(✅ 5/5 accepted-codex)
- [x] 所有 `accepted-codex` 已回写到 design.md / proposal.md / tasks.md / dogfood protocol(F1-F5 5 项 2026-05-04T23:30 完成,见 ## D.2)
- [x] `disputed-permanent-drift` 不适用(disputed_open 0)
- [x] `openspec validate adopt-subagent-driven-development --strict` PASS(回写后)
- [x] `python tools/forgeue_change_state.py --change adopt-subagent-driven-development --writeback-check --json` exit 0(commit `2ec9cfd` 之前已实测 state: S2 / drifts: [] / 无 issues)
- [x] git commit + amend cross-check frontmatter 填 `writeback_commit: 2ec9cfd36e16a19b8f775b0dc902b9fa1b6a602c`(commit 1 sha;commit 2 backfill 本字段)
