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

## P2 — 9 + 1 forgeue 命令模板加 Preflight section

- [ ] P2.1:`.claude/commands/forgeue/change-apply-subagent.md` 加 `## Preflight Worktree` + `## Preflight Skill Cascade` + `## Preflight Task Granularity` 三段
- [ ] P2.2:`.claude/commands/forgeue/change-apply-direct.md` 同款 3 段
- [ ] P2.3:**新建** `.claude/commands/forgeue/change-apply-parallel.md`(invoke `superpowers:dispatching-parallel-agents` SKILL)+ 3 段 Preflight + 借用模式 disclaimer + task independence assertion 协议
- [ ] P2.4:`.claude/commands/forgeue/{change-status,change-plan,change-debug,change-verify,change-review,change-doc-sync,change-finish}.md`(7 个命令)加 `## Preflight Skill Cascade` 段(若命令 invoke SKILL;若纯只读如 change-status 跳过)
- [ ] P2.5:`.claude/commands/forgeue/change-apply.md`(deprecated stub)— 加 deprecation 提示 update,引用 change-apply-parallel 作为新选项
- [ ] P2.6:`tests/unit/test_forgeue_command_markdown.py` 加 fence:
  - `test_each_apply_cmd_has_preflight_worktree_section`(3 个 apply 命令)
  - `test_each_apply_cmd_has_preflight_skill_cascade_section`(3 个 apply 命令)
  - `test_each_apply_cmd_has_preflight_task_granularity_section`(3 个 apply 命令)
  - `test_change_apply_parallel_command_exists`(新文件存在 + 含 dispatching-parallel-agents skill 引用)
  - `test_skill_invoking_cmds_have_preflight_skill_cascade`(7 个 + 3 个 = 10 个 SKILL-invoking 命令)
- [ ] P2.7:`pytest -q tests/unit/test_forgeue_command_markdown.py` 全绿

## P3 — codex 命令模板 同款 preflight skill cascade

- [ ] P3.1:`.claude/commands/codex/review.md` + `adversarial-review.md` 加 `## Preflight Skill Cascade` 段(若有 SKILL invoke;若纯 codex CLI dispatch 则 N/A 但加 doc disclaimer)
- [ ] P3.2:`tests/unit/test_codex_command_markdown.py` 加 fence(若适用)
- [ ] P3.3:`pytest -q tests/unit/test_codex_command_markdown.py` 全绿

## P4 — 11 处文档同步(沿 enhance-workflow-automation P3 模式)

- [ ] P4.1:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C 加 D-ParallelDispatch / D-WorktreeEnforce / D-SkillCascadeCheck 描述;状态机加 preflight phase
- [ ] P4.2:`docs/ai_workflow/README.md` §4 加 runtime enforcement 摘要
- [ ] P4.3:`docs/ai_workflow/forgeue_quickstart.md` S2/S3/S4-S5 stage 加 preflight 说明
- [ ] P4.4:`CLAUDE.md` `## OpenSpec 工作流` § 加 runtime enforcement 摘要 + change-apply-parallel 命令引用
- [ ] P4.5:`README.md` 工作流概述加并行 / worktree 说明
- [ ] P4.6:`AGENTS.md` 同步 runtime enforcement
- [ ] P4.7:`CHANGELOG.md` `[Unreleased]` 加本 change entry
- [ ] P4.8:`.claude/skills/forgeue-integrated-change-workflow/SKILL.md` 同步
- [ ] P4.9:`docs/requirements/SRS.md` 加 ADR-011 行(沿 ADR-007/008/009/010 格式)
- [ ] P4.10:`docs/acceptance/acceptance_report.md` 加 ADR-011 status 行
- [ ] P4.11:`openspec/specs/examples-and-acceptance/spec.md` — sync archive 时 auto-sync(本 task 不动)

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
