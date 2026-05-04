> **★ CONTRACT IS THE SOURCE OF TRUTH ★** — 本 `tasks.md` 是 `proposal.md` + `design.md` + `specs/examples-and-acceptance/spec.md` 的 derived task list。本文件与 design / spec 冲突时,**优先 design / spec**。Implementer 在每个 commit 前先读对应 design 段 + spec Requirement,task 描述只作 actionable checklist 用。
>
> **Scope:** 把 Superpowers `subagent-driven-development` skill 从 ForgeUE §B.3 的 OPTIONAL 名义占位升级为 `/forgeue:change-apply-subagent` 命令的 default 路径;新增 ADR-009 把 token-budget 边界与 ADR-007 vendor API 双扣边界**根本切分**;解禁 `using-git-worktrees`;per-task subagent return 固化为 OpenSpec change evidence。
>
> **8 项 D-fixed 决策(用户 2026-05-04 拍板;详见 `design.md` ## Decisions D-Worktree / D-Default / D-EvidenceSchema / D-SkillInvoke / D-TaskInput / D-ADR008 / D-BudgetMode / D-SelfHost)**:
> - **D-Worktree**(P1-a):解禁 `using-git-worktrees`;`forgeue_integrated_ai_workflow.md` §B.3 表 `using-git-worktrees` 行从 `禁用` 改为 `REQUIRED for change-apply-subagent`;**纯文档级修改**,代码 0 改动
> - **D-Default**(P2-a / D1-b):`/forgeue:change-apply` 拆分为 `change-apply-subagent`(default subagent)+ `change-apply-direct`(executing-plans fallback);现 `change-apply.md` 标 deprecated 重定向
> - **D-EvidenceSchema**(D2-a):per-task evidence 扁平命名 `execution/task_<n>_{implementer,spec_review,code_quality_review}.md` + `review/subagent_final_review.md`;沿 `forgeue_finish_gate.py` frontmatter-indexed 范式
> - **D-SkillInvoke**:`change-apply-subagent` 命令直接 invoke `superpowers:subagent-driven-development` skill,**不**重写 / 不复制 skill 内部 3 个 prompt 模板
> - **D-TaskInput**:主 session Claude 从 `execution/micro_tasks.md` extract task list,完整文本作为 prompt 传 implementer subagent;subagent 不读 plan 文件
> - **D-ADR008**:新增 ADR-009 把 token-budget 边界与 ADR-007 切分;ADR-007 拦截 vendor API 双扣已完成 job(浪费),ADR-009 仅记录 LLM token 持续消耗(打断 = 损失)
> - **D-BudgetMode**(D3-a / 用户 informational 调整):`tools/forgeue_subagent_budget.py` 是 informational tracker,**不**做 hard gate / auto fallback;超阈值仅 stdout `[WARN]`;exit 0 始终
> - **D-SelfHost**(P3 / D4-a):本 change 自身用 subagent-driven-development 跑 dogfooding;Pre-P0 一次性附录 + Claude 主 session 用 Task tool 手工模拟 fresh subagent dispatch
>
> **本 change 实施模式:self-host bootstrap dogfooding**
>
> 由于 `change-apply-subagent` 命令本身在本 change 实施过程中才被创建(P3 阶段),存在 chicken-and-egg。沿 `fuse-openspec-superpowers-workflow` self-host 模式:
> - **§1 Pre-P0**:Claude 主 session 用 Task tool **手工模拟** subagent-driven-development 流程,产物落 `notes/pre_p0/subagent_dogfood_*.md`
> - **§2-§10 实施**:每个 micro-task 走 "手工派 implementer subagent → spec reviewer → code quality reviewer",per-task evidence 落 `execution/task_<n>_*.md` + `review/subagent_final_review.md`
> - **§11 Archive close-out**:tasks unchecked tick + 单 commit close

## 1. Pre-P0 self-host bootstrap

- [ ] 1.1 写 `notes/pre_p0/subagent_dogfood_protocol.md`(沿 `fuse-openspec-superpowers-workflow/notes/pre_p0/forgeue-fusion-claude.md` 范式):说明 Claude 主 session 如何用 Task tool 手工模拟 implementer / spec reviewer / code quality reviewer subagent dispatch;包含 4 段:dispatching protocol / per-task evidence schema / final review trigger / chicken-and-egg 处理
- [ ] 1.2 写 `notes/pre_p0/plan_cross_check.md`(plan-level cross-check,沿 design.md §3 Cross-check Protocol 4 段结构 ## A/B/C/D):`## A` 冻结于 codex hook 调用之前;`## B` 在调 `/codex:adversarial-review --background "<本 change 整体方案>"` 之后填;disputed_open=0 才能进 §2
- [ ] 1.3 codex 调 `/codex:adversarial-review --background "本 change 整体方案 + design.md 8 项 D 决策 + tasks.md self-host bootstrap 模式"`,产物落 `notes/pre_p0/codex_review_round1.md`
- [ ] 1.4 Claude 独立验证 codex 每条 finding(沿 ForgeUE memory `feedback_verify_external_reviews`);填 `plan_cross_check.md` ## B/C/D;blocker 涉及 design 必回写 design.md 或标 disputed-permanent-drift
- [ ] 1.5 `disputed_open == 0` + `notes/pre_p0/` 全部 frontmatter 完整 + `tools/forgeue_change_state.py --change adopt-subagent-driven-development --writeback-check --json` exit 0 → 进 §2

## 2. 文档同步(ForgeUE workflow 文档层)

- [ ] 2.1 编辑 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.3 表:
  - `using-git-worktrees` 行:`禁用` → `REQUIRED for change-apply-subagent`(沿 D-Worktree)
  - `subagent-driven-development` 行:`OPTIONAL | paid API 拦截:env guard {1,true,yes,on} + ADR-007 引用` → `default for change-apply-subagent | ADR-009 token-budget tracker informational`
- [ ] 2.1b 编辑 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.1 状态机表(line 113-124):
  - **S3 行** "允许命令" 列 `ForgeUE change-{apply,debug,status}` → `ForgeUE change-{apply-subagent,apply-direct,debug,status}`
  - **S4 行** 同 S3 行同款修改
- [ ] 2.2 编辑 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.4 表后加新段 §B.6 `subagent-driven-development 集成边界`,描述 4 类 per-task evidence_type + 命令分流(`change-apply-subagent` vs `change-apply-direct`)
- [ ] 2.3 编辑 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §A.6 命令边界段:加 `change-apply-subagent` / `change-apply-direct` 两个 ForgeUE 命令的描述行;现 `change-apply` 行标 deprecated
- [ ] 2.4 编辑 `docs/ai_workflow/README.md` §5 Agent 分工表 Superpowers 行:删 `subagent-driven-development paid API 拦截(env guard + ADR-007)` 描述,改成 `subagent-driven-development default for /forgeue:change-apply-subagent;ADR-009 token-budget tracker informational`;`using-git-worktrees 禁用` 改 `using-git-worktrees REQUIRED for subagent path`
- [ ] 2.4b 编辑 `docs/ai_workflow/README.md` §8 入口表(line 283):"进入 S3→S4-S5:implementation" 行 `/forgeue:change-apply <id>(...)` → 拆 2 行:`/forgeue:change-apply-subagent <id>(default;invoke superpowers:subagent-driven-development + 4 类 per-task evidence + budget tracker informational)` + `/forgeue:change-apply-direct <id>(fallback;executing-plans + TDD + tdd_log/debug_log)`
- [ ] 2.4c 编辑 **repo 根 `README.md`**(非 `docs/ai_workflow/README.md`)line 380-388 ForgeUE 命令清单表:`/forgeue:change-apply` 行(line 383)拆成 `/forgeue:change-apply-subagent`(default subagent dispatch + 4 类 per-task evidence + budget tracker informational)+ `/forgeue:change-apply-direct`(fallback executing-plans + TDD)两行;命令总数从 8 → 9
- [ ] 2.5 编辑 `CLAUDE.md` `### ForgeUE Integrated AI Change Workflow` 段:更新 8 个 `/forgeue:change-*` 命令描述,把 `change-apply` 拆成 `change-apply-subagent` + `change-apply-direct`(命令数从 8 → 9);加 ADR-009 引用
- [ ] 2.6 编辑 `AGENTS.md` 同段(与 `CLAUDE.md` 对齐;Codex CLI / Cursor / Aider 视角)
- [ ] 2.7 编辑 `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` Superpowers 集成边界表 + 命令清单;沿 `forgeue_integrated_ai_workflow.md` §B.3 / §B.6 同步
- [ ] 2.8 编辑 `docs/ai_workflow/forgeue_quickstart.md`(3 处必改):
  - **line 35** 9 stage 全景图 `/forgeue:change-apply <id>            ← 实施(bug 时 /forgeue:change-debug)` → 拆 2 行(default subagent + fallback direct);S4 stage 标 `(impl in progress)  TDD + executing-plans / subagent-driven-development + 越界检测`
  - **§3.3 S3→S4-S5 实施段(line 109-133)整段重写**:命令拆 2 个;**做什么** 段加 subagent-driven-development 路径(per-task 4 类 evidence + budget tracker)+ direct 路径(executing-plans + tdd_log);**关键检查** 段加 "subagent path:每个 task 必有 spec_review + code_quality_review";**深读** 引用更新到 §B.6 新段
  - **§6 速查卡(line 286)**:"实施代码 + TDD + plan review" 行 `/forgeue:change-apply <id>` → 拆成 "实施(default subagent path)" + "实施(fallback direct path)" 两行
- [ ] 2.9 验证 `docs/ai_workflow/validation_matrix.md` 不需要改(grep 已确认无 `change-apply` 字面引用,只涉及 Level 0/1/2 验证矩阵,与命令拆分无关)

## 3. SRS / acceptance_report 加 ADR-009

- [ ] 3.1 编辑 `docs/requirements/SRS.md` § ADR 表:在 ADR-007 行后新增 ADR-009 行
  - 描述:`subagent dispatch token-budget tracker(informational + soft WARNING);与 ADR-007 vendor API 双扣边界根本不同`
  - 决策正文:`framework 不对 LLM token cost 做 hard gate;tools/forgeue_subagent_budget.py 仅记录 + 超阈值 stdout WARN;exit 0 始终(I/O 异常 exit 1 例外);用户保留 dispatch 中断判断权(沿 ForgeUE memory feedback_decisive_approval)`
  - 与 ADR-007 对比段:`ADR-007 拦截 mesh.generation 重试时双扣已完成 job(浪费);ADR-009 仅记录 LLM token 持续产生价值的消耗(拦截 = 打断)`
- [ ] 3.2 编辑 `docs/acceptance/acceptance_report.md` § ADR 状态表:新增 ADR-009 行,状态 `✅ 已批准 + 工具实施待 §6 完成`

## 4. ForgeUE 命令重构(`/forgeue:change-apply` 拆 2)

- [ ] 4.1 新建 `.claude/commands/forgeue/change-apply-subagent.md`(default subagent dispatch 路径):
  - frontmatter `name: "ForgeUE: Change Apply (Subagent)"` + `description: S3→S4-S5;invoke superpowers:subagent-driven-development + 4 类 per-task evidence + budget tracker informational`
  - Steps 1-6:沿现 `change-apply.md` step 1-6 不变(env_detect / 绑 active change / 检查 S3 进入条件 / 冻结 plan_cross_check ## A / codex plan review hook / 写 plan_cross_check ## B/C/D)
  - **Step 6.5 新增**(F1 修复 — worktree 协议硬性步骤,沿 design.md D-Worktree-Detail):commit active change artifacts 到当前分支(`git add openspec/changes/<id>/` + `git commit -m "wip: snapshot before isolated worktree"`)。**必要原因**:`git worktree add` 不复制 untracked / unstaged 文件,跨 worktree 不可见;若 step 6.5 跳过,后续 subagent 在 isolated worktree 看不到本 change contract / micro_tasks.md
  - **Step 6.6 新增**:invoke `superpowers:using-git-worktrees` skill 起 isolated worktree(沿 D-Worktree REQUIRED 依赖);worktree 路径例 `<repo>-worktrees/<change-id>/`
  - **Step 6.7 新增**:`cd` 到 isolated worktree,**所有后续命令(step 7-10 dispatch + evidence 落盘 + 越界检测 + 回写检测;以及 §8 verify / §9 review / §10 doc-sync + finish-gate)以该 worktree 为 cwd 执行**(沿 D-Worktree-Detail 第 3 项)
  - **Step 7 重写**:invoke `superpowers:subagent-driven-development` skill;主 session Claude 从 `execution/micro_tasks.md` extract task list + `execution/execution_plan.md` 提取 per-task context,完整文本作为 prompt 传 implementer subagent(沿 D-TaskInput)
  - **Step 8 新增 evidence 收口**:每个 task 完成后落 `execution/task_<n>_implementer.md` / `task_<n>_spec_review.md` / `task_<n>_code_quality_review.md`(12-key frontmatter 完整);全 task 完成后落 `review/subagent_final_review.md`。**所有 4 类 subagent evidence frontmatter 必含额外 audit 字段** `triggered_by_command: change-apply-subagent`(F2 修复 — `forgeue_finish_gate.py` 完整性检查从此字段判定 dispatch mode,不依赖 helper marker);**Token usage 写 evidence body 末尾段**(F5 修复 — `## Token usage` 段含 input_tokens / output_tokens / model / estimated_usd / data_source,沿 design.md D-ADR008 / dogfood protocol §5)
  - **Step 8.5 新增 budget record**:每次 dispatch return 后调 `python tools/forgeue_subagent_budget.py --change <id> --record --task-n <n> --subagent-type <implementer|spec_review|code_quality_review|final_review> --tokens-input <N> --tokens-output <M> --usd <X> --model <name>`(参数从 Task tool return 的 token usage 直接传,**不**从 evidence frontmatter 读;沿 F5 修复 + F6 修复 6 args 全列)
  - Step 9-10:越界检测 + 回写检测 + 状态推进(沿 change-apply.md 不变;**以 isolated worktree 为 cwd** 执行)
  - **Step 10.5 新增**(F1 修复 — evidence 同步回主分支):全部 micro-task done + Level 0 全绿 + finish_gate exit 0 后,squash merge 或 cherry-pick isolated worktree 全部 commits(含 evidence 落盘 commits)回主分支;然后 `git worktree remove <isolated-path>` 清理。**禁止** force-push 或 evidence 文件手工 cp(沿 D-Worktree-Detail 第 4 项)
  - Guardrails:加 `不复制 / 不引用 implementer-prompt.md / spec-reviewer-prompt.md / code-quality-reviewer-prompt.md 文本`(沿 D-SkillInvoke);加 `subagent 不被授权读 micro_tasks.md / execution_plan.md`(沿 D-TaskInput)
- [ ] 4.2 新建 `.claude/commands/forgeue/change-apply-direct.md`(executing-plans fallback 路径):
  - 内容 = 现 `change-apply.md` step 1-10 完全照搬(executing-plans + TDD + tdd_log.md / debug_log.md evidence)
  - frontmatter description 改为 `S3→S4-S5 fallback;executing-plans + TDD;不派 subagent;轻量场景 / budget 紧张时使用`
- [ ] 4.3 改写现 `.claude/commands/forgeue/change-apply.md`:删除现 step 流程内容,替换为 deprecated banner:
  ```markdown
  > **DEPRECATED**:本命令已废弃,根据 change 复杂度选择:
  > - 多 micro-task / 需要强 review checkpoint → `/forgeue:change-apply-subagent <id>`
  > - 小 change(< 3 task)/ budget 紧张 → `/forgeue:change-apply-direct <id>`
  > 本文件保留 1 个 archive cycle 过渡,下一 change(`add-forgeue-brainstorm-stage`)删除。
  ```
- [ ] 4.4 验证现 `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` 引用更新:把 `/forgeue:change-apply` 替换为 `/forgeue:change-apply-{subagent,direct}` 二选一

## 5. `forgeue_finish_gate.py` 扩 evidence_type enum

- [ ] 5.1 编辑 `tools/forgeue_finish_gate.py` `_VALID_EVIDENCE_TYPES` 等 enum 集合,加 4 项:
  - `subagent_implementer_report`
  - `subagent_spec_review`
  - `subagent_code_quality_review`
  - `subagent_final_review`
- [ ] 5.2 编辑同文件 `_DEFAULT_PATHS_BY_TYPE`(默认 path 表),加 4 项:
  - `subagent_implementer_report` → `execution/task_*_implementer.md`(glob)
  - `subagent_spec_review` → `execution/task_*_spec_review.md`
  - `subagent_code_quality_review` → `execution/task_*_code_quality_review.md`
  - `subagent_final_review` → `review/subagent_final_review.md`
- [ ] 5.3 完整性检查规则(F2 修复 — 不依赖 helper marker file):`change-apply-subagent` 路径下 4 类 evidence_type **全部 REQUIRED**;`change-apply-direct` 路径下 4 类 evidence_type 都不 REQUIRED(沿用 `tdd_log` / `debug_log` 即可)。**判定路径改为从 evidence frontmatter `triggered_by_command` 字段扫描**:
  - 若 `openspec/changes/<id>/{notes,execution,review,verification}/**/*.md` 任意 evidence frontmatter 含 `triggered_by_command: change-apply-subagent` → 判定为 subagent 路径 → 4 类 subagent_* evidence REQUIRED → 缺失 exit 2
  - 若所有 evidence frontmatter 都不含 `triggered_by_command` 字段或值是其他(`change-apply-direct` / 旧 change)→ 判定为 direct 路径 → 4 类 subagent_* 不 REQUIRED → 沿用 `tdd_log` / `debug_log`
  - **不依赖** `notes/pre_p0/dispatch_mode.txt` helper marker(F2 揭示该 marker 可缺失 + 缺失时 silent WARN 等于绕过 gate;改用命令必写的 evidence frontmatter 字段)
- [ ] 5.4 fence test `tests/unit/test_forgeue_finish_gate.py` 加 case(F2 + F1 修复):
  - 4 类新 evidence_type frontmatter 校验通过
  - **(F2 case)**任意 evidence frontmatter `triggered_by_command: change-apply-subagent` 但 4 类 subagent_* evidence 缺失 → exit 2(必 fail,不允许 silent WARN)
  - 所有 evidence 都不含 `triggered_by_command` 字段(direct / 旧 change)→ exit 0(不要求 subagent_* evidence)
  - **(F1 worktree case)**simulate isolated worktree 场景:active change artifacts 在主 worktree 是 untracked → fence test 验证 `git worktree add` 后 isolated worktree 看不到这些文件 → tasks.md §4.1 step 6.5(commit untracked)缺失则 fence test 必 fail(防回归)
- [ ] 5.5 编辑 `tools/forgeue_change_state.py` DRIFT detector(F3 修复;line 369 + line 396):
  - `detect_drift_contradicts` line 369 evidence_type 白名单加 4 项:`subagent_implementer_report` / `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review`
  - `detect_drift_gap` line 396 evidence_type 白名单同样加 4 项
  - subagent review body 中包含 contract gap / missing requirement / failure keyword / 引入新决策 / 越界 module → DRIFT detector 报相应 DRIFT type → `forgeue_change_state.py --writeback-check --json` exit 5(阻断 S5 / S7 / S8 推进)
- [ ] 5.6 加 fence test `tests/unit/test_forgeue_change_state.py`(F3 fence):
  - `subagent_spec_review` body 含 "missing requirement" / "extra feature" / "misunderstood" 等 contract gap 关键字 → `--writeback-check` exit 5(沿 4 类 named DRIFT taxonomy)
  - `subagent_code_quality_review` body 含 Critical issue → exit 5
  - `subagent_implementer_report` body 内 `def`/`class` identifier 不在 design.md fenced code 内 → exit 5(沿 detect_drift_contradicts 现有 _RE_PY_DEF 检测)
- [ ] 5.7 修 task 2 引入的 fence count regression(task 3 §5 dogfood code_quality_reviewer 独立验证暴露;`evidence_exposes_contract_gap` DRIFT writeback,16 errors outstanding):
  - **背景**:task 2 commit `af2892a` 引入 `change-apply-direct.md` + `change-apply-subagent.md`,让 `.claude/commands/forgeue/` 实际有 10 个 .md 文件;但 3 个 fixture (`tests/unit/test_forgeue_command_markdown.py` + `test_forgeue_workflow_no_paid_default.py` + `test_forgeue_workflow_plugin_invocation.py`)硬编码 "expected exactly 8 forgeue command files",导致全量 pytest 16 errors。task 2 dogfood loop reviewer 当时未跑全量 pytest 漏抓(systematic gap)
  - **修复路径**:**不是**简单 `8` → `10` mechanical replacement(reviewer 验证)— `change-apply.md` 现是 deprecated stub(只有 frontmatter + 一段 banner,无 `Steps` / `Output Format` / `Guardrails` body sections),fixture 里多个 assert(`test_each_cmd_mentions_codex_hook` / `test_each_cmd_references_forgeue_env_detect` / `test_each_cmd_has_required_body_sections` / `test_paid_mentions_qualified`)都会对 stub fail
  - **正确修复**:在 3 个 fixture 文件:(a)`files = sorted(p for p in CMD_DIR.glob("change-*.md") if p.name != "change-apply.md")` 排除 deprecated stub + assertion 改 `len == 9`;(b) 或归档 deprecated stub 到 `.claude/commands/forgeue/_deprecated/change-apply.md`(更彻底,但跨 archive cycle 处置)
  - **dogfood 价值**:让此修复**走完整 dogfood loop**(implementer + spec_review + code_quality_review),是双重价值:既修 16 errors,又当 后续 task dogfood evidence subject
  - **lessons learned**(写入 forgeue_integrated_ai_workflow.md follow-on,non-blocker):dogfood reviewer 应该跑全量 pytest 而非仅相关测试,否则会漏抓 cross-file regression
  - **完成标准**:全量 pytest exit 0,1 SKIP / 0 ERRORS;3 个 erroring fixture 文件 PASS;`change-apply.md` deprecated stub 处置策略明确(fixture-level exclude vs file move);spec compliance reviewer + code quality reviewer 走完整 dogfood loop

## 6. `tools/forgeue_subagent_budget.py` 新建 + fence test

- [ ] 6.1 新建 `tools/forgeue_subagent_budget.py`(stdlib only,~100 行,沿 forgeue_finish_gate.py 范式):
  - argparse 子命令:`--status` / `--record` / `--json`
  - `--record` 参数:`--task-n <n>` `--subagent-type <implementer|spec_review|code_quality_review|final_review>` `--tokens-input <N>` `--tokens-output <M>` `--model <name>` `--usd <X>`
  - 输出 JSON Lines 到 `openspec/changes/<id>/verification/subagent_budget.log`
  - env 读取:`FORGEUE_SUBAGENT_BUDGET_WARN_USD`(default `2.0`)/ `FORGEUE_SUBAGENT_BUDGET_WARN_PER_TASK_USD`(default `0.30`)/ `FORGEUE_SUBAGENT_BUDGET_DISABLE`
  - 累积消耗超 WARN 阈值时 stdout 打 `[WARN] budget exceeded: $<X.XX> of $<Y.YY> (<Z>%)`
  - **始终 `exit 0`**(I/O 异常 `exit 1` 例外)
  - `sys.stdout.reconfigure(encoding="utf-8")` + ASCII fallback(沿 ForgeUE memory `feedback_ascii_only_in_adhoc_scripts`)
- [ ] 6.2 新建 `tests/unit/test_forgeue_subagent_budget.py` fence test:
  - `--status` 始终 exit 0 + JSON 输出格式 + WARN line 触发条件
  - `--record` JSON Lines append + 多次 record 累积正确
  - 超 WARN 阈值不影响 exit code(只 stdout 警告)
  - `FORGEUE_SUBAGENT_BUDGET_DISABLE=1` 时不输出 WARN
  - I/O 异常路径 exit 1(权限拒绝 / 路径不存在等)
- [ ] 6.3 跑 `python -m pytest tests/unit/test_forgeue_subagent_budget.py -v` 全绿

## 7. capability spec delta sync(自动,archive 时跑)

- [ ] 7.1 验证 `openspec/changes/adopt-subagent-driven-development/specs/examples-and-acceptance/spec.md` 通过 strict validate(本任务在 §10.1 Finish Gate 中跑,本条只确认 spec delta 文件存在);archive 时 `openspec archive` 自动跑 sync-specs 把 ADDED Requirement 合入 `openspec/specs/examples-and-acceptance/spec.md` 主 spec

## 8. Level 0 验证

- [ ] 8.1 跑 `python -m pytest -q`(预期 549 + 新增 ~5 fence test = ~554 全绿;以实测为准,**不硬编码总数**)
- [ ] 8.2 跑 `python tools/forgeue_subagent_budget.py --status --change adopt-subagent-driven-development`(可执行,JSON 格式正确)
- [ ] 8.3 跑 `python tools/forgeue_finish_gate.py --change adopt-subagent-driven-development --json`(预期不 FAIL;evidence 完整性从 evidence frontmatter `triggered_by_command` 字段判定 dispatch mode,沿 §5.3 修正后规则,**不依赖** `dispatch_mode.txt` helper marker)
- [ ] 8.4 跑 `python tools/forgeue_change_state.py --change adopt-subagent-driven-development --writeback-check --json`(预期 exit 0)
- [ ] 8.5 写 `verification/verify_report.md`(`evidence_type: verify_report`,12-key frontmatter):body summary `[OK]: N / [FAIL]: 0 / [SKIP]: M`;Level 1/2 SKIP 必有 reason(本 change 不涉及 LLM live / paid provider / UE,Level 1/2 全 SKIP)

## 9. S6 review

- [ ] 9.1 invoke `superpowers:requesting-code-review` skill 跑 self-review;产物落 `review/superpowers_review.md`(`evidence_type: superpowers_review`)
- [ ] 9.2 codex 调 `/codex:adversarial-review --background "<本 change 整体 + 实施 + evidence>"` mixed scope post-implementation review;产物落 `review/codex_adversarial_review.md`
- [ ] 9.3 Claude 独立验证 codex 每条 finding(沿 ForgeUE memory `feedback_verify_external_reviews`);blocker 涉及 design 必回写或标 disputed-permanent-drift
- [ ] 9.4 review blocker 0 + superpowers_review.md frontmatter `aligned_with_contract: true`(或带 drift 标记)→ 进 §10

## 10. Documentation Sync Gate + Finish Gate

- [ ] 10.1 跑 `python tools/forgeue_doc_sync_check.py --change adopt-subagent-driven-development --json`(预期触发 [REQUIRED]:**repo 根 `README.md`**(已在 §2.4c 处理 ForgeUE 命令清单表)/ `CLAUDE.md`(§2.5 已处理)/ `AGENTS.md`(§2.6 已处理)/ `SRS.md`(§3.1 已处理 ADR-009)/ `acceptance_report.md`(§3.2 已处理 ADR 表)/ `CHANGELOG.md`([Unreleased] 段在 §11.4 archive close-out 时加新条目记录 9 命令变更 + ADR-009,**不**改 line 88-89 fuse change 的历史描述);[OPTIONAL]:`HLD.md`(本 change 不动架构边界 / 子系统职责,HLD §5.5 ADR-007 worker 边界与 ADR-009 LLM token 边界不重叠,无需交叉引用)/ `LLD.md`(grep 确认 LLD 0 处引用 ADR-007 / ForgeUE 工具,新增 `tools/forgeue_subagent_budget.py` 是 stdlib 工具不进 LLD framework runtime 范畴);[SKIP]:`test_spec.md`(无新测试策略,只加 fence test);[SKIP]:`openspec/specs/*`(已通过 spec delta 自动 sync;主 spec `provider-routing` / `runtime-core` / `probe-and-validation` 的 ADR-007 引用全部是 mesh/audio/video worker 双扣边界,与 ADR-009 LLM token 不重叠,无需交叉引用))。注:`docs/ai_workflow/` 子文档(`forgeue_integrated_ai_workflow.md` / `forgeue_quickstart.md` / `validation_matrix.md`)**不在** doc_sync_check 工具扫描的 10 份主清单内,但本 change 已通过 §2.1-§2.9 直接编辑同步,§10.1 工具结果不应再标记它们 DRIFT
- [ ] 10.2 应用 [REQUIRED] 项 patch(已在 §2 + §3 实施);写 `verification/doc_sync_report.md`(`evidence_type: doc_sync_report`):DRIFT 0 + REQUIRED 全应用 + SKIP reason 全记
- [ ] 10.3 跑 `python tools/forgeue_finish_gate.py --change adopt-subagent-driven-development --json`(11 项检查全过;新增 evidence_type enum 已在 §5 验证;cross-check `disputed_open == 0`)
- [ ] 10.4 写 `verification/finish_gate_report.md`(`evidence_type: finish_gate_report`):0 blockers + 0 warnings(`--enable-review-gate` 检查仅 WARN);exit 0
- [ ] 10.5 跑 rg fence(F4 防回归):`rg -n "FORGEUE_APPLY_MODE|env / flag 切换|env flag 切换" openspec/changes/adopt-subagent-driven-development/ docs/ai_workflow/ .claude/commands/forgeue/ .claude/skills/forgeue-integrated-change-workflow/`,预期 0 hit;若有 hit → 删除残留并补 fence test `tests/unit/test_no_forgeue_apply_mode_residual.py`(grep 本 change 实施 touched 的 docs / commands / skills 文件,exit 1 if found)

## 11. Archive close-out

- [ ] 11.0 **(F10 修复 — pre-tick before finish_gate)** 在 §10.3 finish_gate 之前 tick §1-§9 已完成 task `[x]`(防 finish_gate `tasks_unchecked` blocker 永久阻塞;沿 codex S6 round 2 F10 finding accepted)
- [ ] 11.1 tasks unchecked tick:把本文件全部 task 改 `[x]`(§10-§11 self-stage 在 finish_gate 跑后 `[x]`)
- [ ] 11.2 单 commit close:`feat(openspec): adopt subagent-driven-development as default change-apply path + ADR-009 budget tracker`
- [ ] 11.3 用户调 `openspec archive adopt-subagent-driven-development -y`(自动跑 sync-specs 合入主 spec + mv 到 `openspec/changes/archive/<date>-adopt-subagent-driven-development/`)
- [ ] 11.4 archive 后 commit:`chore(openspec): archive adopt-subagent-driven-development + sync examples-and-acceptance ADDED requirement`

## Documentation Sync

- [ ] Check whether openspec/specs/* needs update after archive(本 change 已写 spec delta,archive 时 sync-specs 自动合并)
- [ ] Check whether docs/requirements/SRS.md needs update(本 change §3.1 新增 ADR-009,REQUIRED)
- [ ] Check whether docs/design/HLD.md needs update(预期 SKIP:本 change 不触及架构边界 / 子系统职责;若 §6 实施暴露 ForgeUE workflow 子系统重新定义,re-evaluate)
- [ ] Check whether docs/design/LLD.md needs update(预期 SKIP:本 change 不触及接口 / 模型 / CLI entry;`tools/forgeue_subagent_budget.py` 新工具规模太小,不进 LLD)
- [ ] Check whether docs/testing/test_spec.md needs update(预期 SKIP:本 change 只加 1 个 fence test,无新测试策略)
- [ ] Check whether docs/acceptance/acceptance_report.md needs update(本 change §3.2 新增 ADR-009 行,REQUIRED)
- [ ] Check whether README.md needs update(预期 SKIP:本 change 不改用户可见工作流 / 命令入口;`/forgeue:change-apply-{subagent,direct}` 是工作流内部演化,不直接面向终端用户)
- [ ] Check whether CHANGELOG.md needs update(REQUIRED:加 [Unreleased] 段记 ADR-009 + change-apply 拆分 + subagent-driven-development default)
- [ ] Check whether CLAUDE.md needs update(本 change §2.5 REQUIRED)
- [ ] Check whether AGENTS.md needs update(本 change §2.6 REQUIRED)
- [ ] Record skipped docs with reason(写到 §10.2 doc_sync_report.md)
- [ ] Mark doc drift for human confirmation if sources conflict
