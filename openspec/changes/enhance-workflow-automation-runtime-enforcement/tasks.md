# Tasks — enhance-workflow-automation-runtime-enforcement

## Pre-P0(self-host bootstrap;沿 D-SelfHost 模式;**本 change 实施期间 sequential dispatch**因为 parallel 协议未 land)

- [x] Pre-P0.1:`/codex:adversarial-review` round 1 挑战 D-ParallelDispatch / D-WorktreeEnforce / D-SkillCascadeCheck / D-RoundFixContinuity / D-TaskGranularityDeclaration / D-PreflightProtocol 6 个 D-decision + Open Questions OQ-1/2/3
- [x] Pre-P0.2:落 `notes/pre_p0/codex_review_round1.md` evidence
- [x] Pre-P0.3:Claude 独立验证 codex finding(file:line 引用)+ verdict 矩阵
- [x] Pre-P0.4:writeback finding 到 design.md / proposal.md / spec.md / tasks.md(double-commit;commit 7300173 + amend 3de6165)
- [x] Pre-P0.5:落 `notes/pre_p0/plan_cross_check.md`(plan-level cross-check 覆盖 design + plan + spec + tasks 四 scope)
- [x] Pre-P0.6:`disputed_open: 0` 验证(2 inline writeback F4/F5 + 3 deferred-tracking F1/F2/F3)

## P0 — `tools/forgeue_skill_cascade_check.py` 新建 + 测试 fence

- [x] P0.1:Read 一个 sample SKILL.md(`subagent-driven-development` / `using-git-worktrees`)了解 `## Integration` 段格式
- [x] P0.2:加 `tools/forgeue_skill_cascade_check.py`(stdlib only):
  - argparse:`--skill <name>` + `--invoked <comma-separated-skill-list>` + `--skill-root <path>`(D-SkillRootMultiSource override)
  - SKILL.md 路径推断:8 root probe 链(CLI flag / env var / repo-local / Anthropic plugin cache 拿最新 version / 其他 plugin / Codex / `${CODEX_HOME}` / `.agents/skills`),首个命中即返回
  - 解析 `## Integration` 段 / `**Required workflow skills:**` 子段 / `REQUIRED` 标记
  - 输出 missing dependency 列表 + exit 0 / 5(unknown skill 与 missing dep 都用 5,通过 sentinel 区分)
- [x] P0.3:加 `tests/unit/test_skill_cascade_check.py`(新建)fence(共 18 个):
  - 5 base fence:cascade resolves / missing dep blocks / no Integration → skip / unknown skill → exit 5 / format drift(大小写 + 空格)
  - 6 D-SkillRootMultiSource fence:CLI flag / env var / repo-local / Anthropic plugin default / Anthropic latest version / Codex / CODEX_HOME / unknown
  - 3 CLI smoke(subprocess 验证 exit code + stderr 内容)
  - 4 辅助(two-deps all-invoked / partial-invoke listing / etc.)
- [x] P0.4:`pytest -q tests/unit/test_skill_cascade_check.py` 全绿(18 passed in 0.54s)
- [x] P0.5:`pytest -q` 全套 regress(1503 passed + 1 skipped(Windows symlink) in 60.64s)

## P1 — `forgeue_finish_gate.py` 加 4 fence + 测试

- [x] P1.1:Read `tools/forgeue_finish_gate.py` 现状(P5/F5/F7 simplified protocol 之后版)
- [x] P1.2:加 `_check_skill_cascade(evidence_path: Path, frontmatter: dict, change_root: Path) -> list[str]` fence:
  - `skill_cascade_audit` 字段存在
  - 字段是 dict + 含 `invoked_skills` (list) + `cascade_check_pass_at` (ISO timestamp)
  - implementation evidence(`_IMPLEMENTATION_EV_TYPES`)缺该字段 → 错误
- [x] P1.3:加 `_check_round_fix_continuity` fence:
  - `subagent_continuity` 字段存在(若 evidence_type 含 round 2 round 标识 / 或 evidence 内含 round 2 append 段)
  - `round_2_fix_implementer_id == round_1_implementer_id`
  - `round_2_review_reviewer_id == round_1_reviewer_id`
- [x] P1.4:加 `_check_task_granularity` fence:
  - `task_granularity` 字段存在(implementation evidence)
  - 值 ∈ `{phase, per-file, sub-task}`
- [x] P1.5:加 `_check_worktree_path` fence(D-WorktreeEnforce 配套):
  - implementation evidence 来自 change-apply-* 命令 → MUST 含 `worktree_path` 字段(non-null)
- [x] P1.6:在 `check_frontmatter_protocol` 调用链插入 4 个新 fence(各独立 Blocker.type:`skill_cascade_violation` / `round_fix_continuity_violation` / `task_granularity_violation` / `worktree_path_violation`)
- [x] P1.7:加 `tests/unit/test_forgeue_finish_gate.py` 16 个 fence 测试:
  - 7 必需(`test_skill_cascade_audit_missing_blocks` / `..._invalid_structure_blocks` / `test_round_fix_continuity_implementer_mismatch_blocks` / `..._reviewer_mismatch_blocks` / `test_task_granularity_missing_blocks` / `..._invalid_value_blocks` / `test_worktree_path_missing_for_change_apply_blocks`)
  - 5 positive / negative 守门(`..._invalid_iso_timestamp_blocks` / `..._valid_passes` × 3 / `..._round_1_only_passes` / `..._empty_string_blocks` / `..._not_required_for_non_change_apply_command`)
  - 2 protocol gate 守门(`test_runtime_fences_skip_legacy_evidence_without_protocol_version` / `..._skip_non_implementation_evidence_under_protocol_v1`)
  - 1 e2e wiring(`test_runtime_fences_wired_into_check_frontmatter_protocol`)
  - 配套基建:扩 `tools/_common.py::_parse_yaml_subset` 支持 nested mapping(subagent_continuity / skill_cascade_audit dict 字段);扩 `tests/fixtures/forgeue_workflow/builders.py::_render_frontmatter` 支持 dict 值
- [x] P1.8:`pytest -q tests/unit/test_forgeue_finish_gate.py` 全绿(99 passed)
- [x] P1.9:`pytest -q` 全套 regress(1519 passed + 1 skipped Windows symlink in 68.38s)

## P2 — 10 forgeue 命令模板加 Preflight section + drift writeback D-DirectWorktreeRefinement

- [x] **Drift writeback**(P2.2 实施前发现 spec.md / design.md / archived D-Worktree-Detail 第 5 项三方契约冲突;按 `feedback_autonomy_boundary_simplified.md` framework / design 不匹配 fence 升级 user 拍板;2026-05-05 user 拍板 (B):direct 不走 worktree,沿 archived 第 5 项):
  - 落 `notes/p2/d_direct_worktree_refinement.md` evidence(三方冲突来源 + user 拍板裁决 + 双向 writeback 摘要)
  - 写回 `specs/examples-and-acceptance/spec.md` Preflight Worktree Requirement 收窄到 subagent + parallel + 加 direct pass-through scenarios
  - 写回 `design.md` D-WorktreeEnforce statement 同款收窄 + 新增 D-DirectWorktreeRefinement decision(含 Why / Trigger origin / Alternatives considered + user 拍板)
  - 改 `tools/forgeue_finish_gate.py::_check_worktree_path` fence:`_CHANGE_APPLY_COMMAND_PREFIX` prefix 改为 `_WORKTREE_REQUIRED_COMMANDS = {change-apply-subagent, change-apply-parallel}` frozenset
  - 加 fence test:`test_worktree_path_not_required_for_change_apply_direct` + `test_worktree_path_required_for_change_apply_parallel`(锁住 direct pass-through + parallel 与 subagent 同等强制)
  - commit `15ae851`(单 commit 双向 writeback + 测试 + evidence)
- [x] P2.1:`.claude/commands/forgeue/change-apply-subagent.md` 加 `## Preflight Worktree` + `## Preflight Skill Cascade` + `## Preflight Task Granularity` 三段 + 协议版本标记说明
- [x] P2.2:`.claude/commands/forgeue/change-apply-direct.md` 加 **2 段** Preflight(Skill Cascade + Task Granularity);**沿 D-DirectWorktreeRefinement 不加 Preflight Worktree**;disclaimer 段引 archived 第 5 项 + fence pass-through 说明
- [x] P2.3:**新建** `.claude/commands/forgeue/change-apply-parallel.md`(invoke `superpowers:dispatching-parallel-agents` SKILL)+ 3 段 Preflight + 借用模式 disclaimer + task independence assertion 协议(`task_independence_assertion: true` + `task_files_disjoint: [<file-set>...]` 字段 + 命令前自动 verify file overlap → 任一交集 abort)
- [x] P2.4:5 个 SKILL-invoke 命令加 `## Preflight Skill Cascade` 段:`change-plan` / `change-debug` / `change-verify` / `change-review` / `change-doc-sync`;**`change-finish` + `change-status` 不 invoke SKILL,沿 task 描述跳过**(纯工具调用 / 只读)
- [x] P2.5:`.claude/commands/forgeue/change-apply.md`(deprecated stub)— deprecation 提示 update 加 `change-apply-parallel` 选项 + 完整 D-ParallelDispatch 路由决策树
- [x] P2.6:`tests/unit/test_forgeue_command_markdown.py` 加 7 个 fence:
  - `test_apply_cmds_have_preflight_skill_cascade_section`(3 apply 命令必含)
  - `test_apply_cmds_have_preflight_task_granularity_section`(3 apply 命令必含)
  - `test_subagent_parallel_have_preflight_worktree_section`(2 命令必含,direct 排除)
  - `test_change_apply_direct_does_not_have_preflight_worktree_section`(D-DirectWorktreeRefinement negative fence,锁住 direct 不含 Preflight Worktree section)
  - `test_change_apply_parallel_command_exists`(新文件存在 + 含 dispatching-parallel-agents 引用 + 借用 disclaimer + task_independence_assertion)
  - `test_skill_invoking_cmds_have_preflight_skill_cascade`(8 个 SKILL-invoking 命令 = 3 apply + 5 SKILL-invoke;`forgeue_skill_cascade_check` 工具引用)
  - `test_change_finish_status_skip_preflight_skill_cascade`(negative fence,锁住 change-finish + change-status 不含 Preflight Skill Cascade section)
  - 配套 fixture 更新:`tests/unit/test_forgeue_command_markdown.py` + `tests/unit/test_forgeue_workflow_plugin_invocation.py` + `tests/unit/test_forgeue_workflow_no_paid_default.py` 中 active 命令计数 9 → 10
- [x] P2.7:`pytest -q tests/unit/test_forgeue_command_markdown.py` 全绿(16 passed,原 9 + 新加 7 P2 fence);`pytest -q` 全套 regress 全绿(1528 passed + 1 skipped Windows symlink in 45.02s)

## P3 — codex 命令模板 同款 preflight skill cascade(disclaimer 路径)

- [x] P3.1:`.claude/commands/codex/review.md` + `adversarial-review.md` 加 `## Preflight Skill Cascade — N/A` disclaimer section — codex 命令是纯 codex CLI dispatch(codex-companion broker 跑 GPT-5.4 review),**不 invoke Superpowers SKILL**,沿 D-SkillCascadeCheck disclaimer 协议 N/A;转移 cascade check 责任到 caller forgeue 命令
- [x] P3.2:`tests/unit/test_codex_command_markdown.py` 加 `test_codex_cmds_have_preflight_skill_cascade_disclaimer` fence(锁住 disclaimer section 存在 + N/A 原因关键词 + caller 责任转移关键词)
- [x] P3.3:`pytest -q tests/unit/test_codex_command_markdown.py` 全绿(11 passed,原 10 + 新 1);`pytest -q` 全套 regress 全绿(1529 passed + 1 skipped Windows symlink in 45.02s)

## P4 — 11 处文档同步(沿 enhance-workflow-automation P3 模式)

- [x] P4.1:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C 加 §C.7 "Runtime Enforcement Protocol"(4 fence 表 + protocol gating + 新命令 `/forgeue:change-apply-parallel` + 8 Preflight section 表 + D-DirectWorktreeRefinement 摘要 + advisory not deterministic R6 limitation)
- [x] P4.2:`docs/ai_workflow/README.md` §4 加 §4.4-bis "Runtime Enforcement"(4 fence 列表 + protocol gating + 新命令 + 8 Preflight section + follow-on `enhance-workflow-automation-executable-enforcement` 引用)
- [x] P4.3:`docs/ai_workflow/forgeue_quickstart.md` S3→S4-S5 stage 加 路由决策树(parallel / subagent / direct 三选一)+ Preflight 三项摘要 + change-apply-parallel 命令引用;§2 全景图加 parallel 命令行
- [x] P4.4:`CLAUDE.md` `## OpenSpec 工作流` 段:命令清单 9→10(加 `/forgeue:change-apply-parallel` 行 + D-DirectWorktreeRefinement 修订 direct 行);工具清单 6→7(加 `forgeue_skill_cascade_check.py`);finish_gate 描述加 4 runtime fence + protocol gate;新增 "Runtime enforcement frontmatter 字段" 段
- [x] P4.5:`README.md` ForgeUE Workflow 表 9→10 命令(加 `/forgeue:change-apply-parallel` + D-DirectWorktreeRefinement direct 修订);6→7 工具(加 cascade check);新增 ADR-011 摘要段
- [x] P4.6:`AGENTS.md` 加 4 条 runtime enforcement 摘要(parallel 命令 / 8 SKILL-invoke 命令 Preflight section / 4 runtime fence / cascade check 工具)
- [x] P4.7:`CHANGELOG.md` `[Unreleased]` 加本 change entry(完整覆盖 ADR-011 + 4 fence + 新命令 + 8 Preflight + 5 commit SHA + 测试覆盖)
- [x] P4.8:`.claude/skills/forgeue-integrated-change-workflow/SKILL.md` 同步:命令清单 9→10;Superpowers 集成边界表加 `dispatching-parallel-agents` 行 + 改 `using-git-worktrees` 行说明 direct 不强制;新增 "Runtime Enforcement Protocol(ADR-011)" 段
- [x] P4.9:`docs/requirements/SRS.md` 加 ADR-011 行(沿 ADR-007/008/009/010 格式;含 8 D-decision 摘要 + advisory not deterministic R6 + follow-on 引用 + D-DirectWorktreeRefinement drift writeback commit `15ae851` 标记)
- [x] P4.10:`docs/acceptance/acceptance_report.md` 加 ADR-011 status 行(✅ 已实装,全条目对应 SRS ADR-011)
- [x] P4.11:`openspec/specs/examples-and-acceptance/spec.md` — sync archive 时 auto-sync(本 task 不动;P10 archive 协议处理)

## P5 — verify

- [ ] P5.1:`python tools/forgeue_verify.py --change enhance-workflow-automation-runtime-enforcement --level 0` 全绿
- [ ] P5.2:`--level 1` 全绿(pytest 全套)
- [ ] P5.3:产 `verification/verify_report.md`(12-key audit frontmatter)

## P6 — codex S6 mixed-scope review

- [ ] P6.1:`/codex:review --base <pre-change-SHA>` mixed-scope 评(default background)
- [ ] P6.2:落 `review/codex_mixed_scope_review.md`
- [ ] P6.3:writeback finding(若有)
- [ ] P6.4:`disputed_open: 0` 验证

## P7 — 跳过 superpowers requesting-code-review(沿 enhance-workflow-automation 模式;per-task 已 cover)

- [ ] P7.1:写 `review/superpowers_review.md` SKIP rationale stub

## P8 — Documentation Sync Gate

- [ ] P8.1:`python tools/forgeue_doc_sync_check.py --change <id>` 静态扫
- [ ] P8.2:落 `verification/doc_sync_report.md` evidence
- [ ] P8.3:任何 [DRIFT] 项 → 修复或显式 `drift_decision`

## P9 — Finish Gate

- [ ] P9.1:`python tools/forgeue_finish_gate.py --change <id>` 全检
- [ ] P9.2:验证 12-key frontmatter 全填
- [ ] P9.3:验证 cross-check `disputed_open: 0`
- [ ] P9.4:验证 worktree_path / skill_cascade_audit / subagent_continuity / task_granularity 字段全填
- [ ] P9.5:验证 writeback_commit 真实性
- [ ] P9.6:验证 tasks.md 全 [x] 勾选(P11 follow-on 除外)
- [ ] P9.7:`openspec validate <id> --strict` 全绿
- [ ] P9.8:落 `verification/finish_gate_report.md`

## P10 — Archive(用户授权)

- [ ] P10.1:**用户授权确认**(D-AutonomyBoundary fence #1 不可逆)
- [ ] P10.2:`openspec archive enhance-workflow-automation-runtime-enforcement --skip-specs --yes`
- [ ] P10.3:手工 sync 5 ADDED Requirement 到 `openspec/specs/examples-and-acceptance/spec.md`(29 → 34 Requirements)
- [ ] P10.4:`openspec validate examples-and-acceptance --strict` 全绿
- [ ] P10.5:archive stub 加 cross_check fence-required frontmatter(沿 enhance-workflow-automation 模式)
- [ ] P10.6:commit + push(用户授权 fence #1)

## P11 — 后置(可选)+ Follow-on tracking(2026-05-05 codex round 1 F1/F2/F3 deferred)

- [ ] P11.1:更新 `MEMORY.md` 加 enhance-workflow-automation-runtime-enforcement 摘要
- [ ] P11.2:实测验证 — 下次 change 应用本 change 协议跑一次,验证 wall-clock 节省 + protocol advisory(注:advisory not deterministic;follow-on change 实施 deterministic enforcement 后才能真验证 enforce 严格性)
- [ ] P11.3 (follow-on tracking):**`enhance-workflow-automation-executable-enforcement`** — 接 F1/F2/F3 deferred 的 deterministic enforcement layer:
  - **W1**(F1):`tools/forgeue_preflight_wrapper.py`(executable script) — 脚本创建 worktree + 写 machine-generated receipt JSON(含 base SHA / cwd / worktree path / cascade check status)+ 命令模板**只能消费** receipt path,不允许 LLM 直接写 worktree_path 字段;finish_gate 校验 receipt 文件存在 + receipt content 与 evidence frontmatter 一致
  - **W2**(F2):parallel dispatch 前主 session 自动跑每个 subagent worktree 内 `git diff --name-only` 获取**实际** changed-files set + cross-check disjoint;阻断 undeclared / actual overlap / 共享 fixture 修改;无法机器证明时自动降级 `/forgeue:change-apply-subagent` sequential
  - **W3**(F3):`<change>/dispatch_ledger.jsonl`(append-only) — 命令层 wrapper(executable script)记录每次 Task / SendMessage 调用的真实 agent ID / round / role / timestamp;LLM 不能直接写 ledger;finish_gate 比较 ledger 与 evidence `subagent_continuity` 字段一致性
  - **依据**:本 change `notes/pre_p0/codex_review_round1.md` F1 / F2 / F3 finding(全 accepted-codex,deferred to executable enforcement layer)
  - **触发条件**:本 change ship 后,实测 controller drift 类风险持续(若 advisory protocol + finish_gate audit 已经足够,可 cancel follow-on);否则按 F1/F2/F3 推荐方案启动新 change
- [ ] P11.4 (follow-on tracking):**`enhance-workflow-automation-handoff-persistence`**(沿 enhance-workflow-automation P5 round 2 F6 deferred)— codex 命令 allowed-tools vs Polling Convention 写文件能力 mismatch 的 architectural 选择
- [ ] P11.5 (follow-on tracking):**`add-forgeue-brainstorm-stage`**(沿 adopt-subagent-driven-development 已 deferred)— Superpowers brainstorming skill 接入 S0/S1 stage
- [ ] P11.6 (follow-on tracking):**`enhance-workflow-automation-finishing-branch`**(本 change 标识)— `superpowers:finishing-a-development-branch` skill 接入 `/forgeue:change-finish` 命令(team scale 协作时 PR / squash merge 路径)
