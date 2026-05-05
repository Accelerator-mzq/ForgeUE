# Tasks — restore-superpowers-worktree-consent-gate

> **沿 ADR-013** revert ADR-011 D-WorktreeEnforce + ADR-012 D-W1-ReceiptSchema worktree mandatory parts;restore Superpowers upstream Step 0 user-consent gate;default decline in implementation phases / opt-in for bug-fix iteration。

## Pre-P0(self-host bootstrap;沿 archived ADR-012 同款 sequential pattern)

- [ ] Pre-P0.1:`/codex:adversarial-review` round 1 挑战 D-RestoreConsentGate / D-AdvisoryFenceMode / D-WrapperDeprecate / D-AllChangeApplyMainRepoDefault / D-CrossArchiveADRSupersede / D-WrapperRetentionRationale / D-CrossCheckUpstreamCascade 7 D-decision + Open Questions OQ-1/2/3
- [ ] Pre-P0.2:落 `notes/pre_p0/codex_review_round1.md` evidence
- [ ] Pre-P0.3:Claude 独立验证 codex finding(file:line)+ verdict 矩阵
- [ ] Pre-P0.4:writeback finding 到 design.md / proposal.md / spec.md / tasks.md
- [ ] Pre-P0.5:落 `notes/pre_p0/plan_cross_check.md`(plan-level cross-check)
- [ ] Pre-P0.6:`disputed_open: 0` 验证

## P0 — 命令模板更新(D-RestoreConsentGate)

- [ ] P0.1:Read 现有 `.claude/commands/forgeue/change-apply-subagent.md` + `.claude/commands/forgeue/change-apply-parallel.md`(archived ADR-012 P3 mandatory 版)
- [ ] P0.2:`change-apply-subagent.md` `## Preflight Worktree` section 重写:
  - 仍 invoke `Skill(superpowers:using-git-worktrees)`(沿 upstream cascade)
  - 显式 "default decline at Step 0 → work in main repo cwd"
  - "opt-in for bug-fix iteration / explicit isolation"
  - 撤 mandatory `python tools/forgeue_preflight_wrapper.py` invocation step
  - evidence frontmatter `worktree_path` 字段标 OPTIONAL
- [ ] P0.3:`change-apply-parallel.md` 同款重写:
  - 同 P0.2 Preflight Worktree section
  - W2 actual diff 段保留(与 worktree 解耦,沿 D-AllChangeApplyMainRepoDefault main repo path)
  - W3 ledger append step 保留
- [ ] P0.4:`change-apply-direct.md` 不动(沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项 + ADR-013 D-AllChangeApplyMainRepoDefault align)
- [ ] P0.5:`tests/unit/test_forgeue_command_markdown.py` fence test 调整:
  - `test_subagent_parallel_have_preflight_worktree_section` 仍 PASS(section 仍存在;只是内容改 OPT-IN)
  - `test_change_apply_subagent_invokes_preflight_wrapper` + `test_change_apply_parallel_invokes_preflight_wrapper` 改 NEGATIVE fence(不再 mandatory invoke;模板**不强制**含 `python tools/forgeue_preflight_wrapper.py` 字符串)— 或改 advisory fence 校验 Skill invoke + decline-default narrative 出现
  - 加新 fence `test_apply_subagent_parallel_preflight_worktree_decline_default`(校验 "default decline" 或 "opt-in" 字符串出现)
- [ ] P0.6:`pytest tests/unit/test_forgeue_command_markdown.py -v` 全绿
- [ ] P0.7:`python -m pytest -q` 全套 regress 全绿(无回归)

## P1 — `forgeue_finish_gate.py` advisory fence(D-AdvisoryFenceMode)

- [ ] P1.1:Read `tools/forgeue_finish_gate.py` `_check_worktree_path` v1 + `_check_worktree_path_v2` 现状
- [ ] P1.2:`_check_worktree_path` v1 改 advisory:
  - 入口加 "worktree_path field present check":若 absent → return [](pass-through)
  - 若 present → 沿原 logic validate(non-empty + path 存在 if absolute)
  - `_WORKTREE_REQUIRED_COMMANDS` frozenset retire(改空集合)or 移除 fence 入口的 "triggered_by_command in set" 检查
- [ ] P1.3:`_check_worktree_path_v2` 改 advisory:
  - 入口加 "worktree_receipt_path field present check":若 absent → return [](pass-through)
  - 若 present → 沿原 logic validate(receipt 文件存在 + JSON well-formed + receipt path matches evidence path)
- [ ] P1.4:`tests/unit/test_forgeue_finish_gate.py` 调整:
  - `test_worktree_path_missing_for_change_apply_blocks` → 改 NEGATIVE / advisory(missing 不再 block;沿 ADR-013)
  - `test_worktree_path_v2_missing_*` 同款
  - 加新 fence `test_worktree_path_advisory_pass_through_when_field_absent`
  - 加新 fence `test_worktree_path_v2_advisory_pass_through_when_receipt_absent`
  - 保留:`test_worktree_path_validates_existing_path_when_provided`(写了就要真)+ v2 receipt cross-check 同款
- [ ] P1.5:`pytest tests/unit/test_forgeue_finish_gate.py -v` 全绿
- [ ] P1.6:`tests/integration/test_v2_e2e_synthetic_change.py` 11 test review:
  - W1 wrapper test 仍 PASS(opt-in 路径仍 functional)
  - finish_gate v2 fence test 仍 PASS(advisory 模式 — 显式 provide receipt 仍 cross-check)
  - 若有 test 依赖 mandatory blocker 行为 → 调整(预计 1-2 test)
- [ ] P1.7:`python -m pytest -q` 全套 regress 全绿

## P2 — wrapper deprecate(D-WrapperDeprecate)

- [ ] P2.1:`tools/forgeue_preflight_wrapper.py` 模块顶部加 `__deprecated_note__` 字符串 + module docstring 加 "[DEPRECATED in default flow]" 标记
- [ ] P2.2:`--help` argparse description 加 deprecation notice("Deprecated in default flow per ADR-013;remains functional for opt-in bug-fix iteration use case")
- [ ] P2.3:`tests/unit/test_preflight_wrapper.py` 18 fence test 全 PASS(行为不变;只 docstring/help notice 加 — 现 test 不依赖 docstring 内容)
- [ ] P2.4:`python -m pytest -q` 全套 regress 全绿

## P3 — sister skill subagent-driven-discipline v2.3 update(D-CrossCheckUpstreamCascade)

- [ ] P3.1:`.claude/skills/subagent-driven-discipline/SKILL.md` Pattern 2 STRICT cwd verify 重写:
  - "STRICT cwd verify when worktree IS used (after user consent at Step 0)"
  - 显式说明 default = main repo cwd;cwd verify 仅在 worktree opt-in 后 trigger
- [ ] P3.2:加新 §3.5 "Worktree Consent Policy"(沿 D-RestoreConsentGate):
  - default decline in implementation phases
  - opt-in for bug-fix iteration / explicit isolation
  - W1 wrapper 作 opt-in tool retain
- [ ] P3.3:Case 1 P3 worktree leak incident scope-down:
  - 标 "本 incident 在 ADR-013 default decline policy 下不会触发(implementation 默认 main repo,无 worktree-scope leak 风险)"
  - 留作 historical reference + bug-fix iteration use case 时仍 relevant
- [ ] P3.4:frontmatter `version: 2.2 → 2.3`;`case_study_count` 不变(2);加 `worktree_consent_policy: default-decline-in-implementation` 字段
- [ ] P3.5:fence test 校验 sister skill SKILL.md 含 "Worktree Consent Policy" 字符串(若有;沿 archived 同款 fence)

## P4 — backbone skill `forgeue-integrated-change-workflow` update(D-CrossArchiveADRSupersede)

- [ ] P4.1:`.claude/skills/forgeue-integrated-change-workflow/SKILL.md` Superpowers 集成边界表 `using-git-worktrees` 行重写:
  - 原:"REQUIRED for `/forgeue:change-apply-subagent` + `/forgeue:change-apply-parallel`"
  - 新:"consent-gated;default decline in implementation;opt-in for bug-fix iteration / explicit isolation(ADR-013)"
- [ ] P4.2:Runtime Enforcement Protocol(ADR-011)段加 superseded note:"D-WorktreeEnforce mandatory 部分由 ADR-013 superseded — restore Step 0 user-consent gate;_check_worktree_path fence 改 advisory"
- [ ] P4.3:Runtime Enforcement Protocol v2(ADR-012)段加 superseded note:"D-W1-ReceiptSchema mandatory invocation 部分由 ADR-013 superseded — wrapper 改 opt-in"
- [ ] P4.4:加新 "ADR-013:Restore Superpowers Worktree Consent Gate" section(简短摘要 + cross-link 本 change archive path)

## P5 — 9 处文档同步(沿 archived ADR-012 P5 模式)

- [ ] P5.1:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C.7 Runtime Enforcement(ADR-011)+ §C.8 v2(ADR-012)加 superseded note + 加 §C.9 "ADR-013 Restore Superpowers Worktree Consent Gate"
- [ ] P5.2:`docs/ai_workflow/README.md` §4.4-bis(ADR-011)+ §4.4-ter(ADR-012)加 superseded note + 加 §4.4-quater "Worktree Consent Gate Restored(ADR-013)"
- [ ] P5.3:`docs/ai_workflow/forgeue_quickstart.md` S3→S4-S5 stage 更新 — wrapper 改 opt-in 描述 + decline-default 行为
- [ ] P5.4:`CLAUDE.md` 工具清单 9 工具不变(wrapper 留)+ Runtime enforcement frontmatter 段 v1 + v2 字段 OPTIONAL 标注 + 加 ADR-013 段
- [ ] P5.5:`README.md` ForgeUE Workflow 表 9 工具不变 + ADR-013 摘要段
- [ ] P5.6:`AGENTS.md` 加 ADR-013 段(沿 ADR-011 / ADR-012 同款结构)
- [ ] P5.7:`CHANGELOG.md` `[Unreleased]` 加本 change entry
- [ ] P5.8:`docs/requirements/SRS.md` ADR-013 行 + ADR-011 + ADR-012 行加 `Superseded by ADR-013 (worktree mandatory parts)` cross-reference
- [ ] P5.9:`docs/acceptance/acceptance_report.md` ADR-013 status 行(✅ 已实装)+ ADR-011 / ADR-012 status 行加 supersede note

## P6 — verify

- [ ] P6.1:`python tools/forgeue_verify.py --change restore-superpowers-worktree-consent-gate --level 0` 全绿
- [ ] P6.2:`--level 1` 全绿(L1 SKIP opt-in 沿 ADR-007)
- [ ] P6.3:产 `verification/verify_report.md`(12-key audit frontmatter)

## P7 — codex S6 mixed-scope review

- [ ] P7.1:`/codex:review --base main --scope branch` mixed-scope 评(default background)
- [ ] P7.2:落 `review/codex_mixed_scope_review.md`(verdict + finding verbatim + Claude file:line verify + Cross-check Matrix + Resolution Plan)
- [ ] P7.3:writeback finding(沿 simplified protocol)
- [ ] P7.4:`disputed_open: 0` 验证

**Pre-commit P7 替代落地**(沿 archived ADR-012 P7 同款 reference stub):
- [ ] `review/codex_design_review.md`(reference Pre-P0 round 1)
- [ ] `review/codex_plan_review.md`(reference Pre-P0 round 1)
- [ ] `review/codex_verification_review.md`(reference verify_report)
- [ ] `review/codex_adversarial_review.md`(reference Pre-P0 + mixed-scope)
- [ ] `review/design_cross_check.md`(A/B/C/D 4 段)
- [ ] `review/plan_cross_check.md`(A/B/C/D 4 段)

## P8 — 跳过 superpowers requesting-code-review(沿 archived ADR-012 P8 同款 SKIP)

- [ ] P8.1:写 `review/superpowers_review.md` SKIP rationale stub

## P9 — Documentation Sync Gate

- [ ] P9.1:`python tools/forgeue_doc_sync_check.py --change restore-superpowers-worktree-consent-gate` 静态扫(0 DRIFT)
- [ ] P9.2:落 `verification/doc_sync_report.md` evidence
- [ ] P9.3:任何 [DRIFT] 项 → 修复

## P10 — Finish Gate

- [ ] P10.1:`python tools/forgeue_finish_gate.py --change restore-superpowers-worktree-consent-gate --no-validate` 跑(预期 P11 unchecked sole blockers)
- [ ] P10.2:验证 12-key frontmatter 全填
- [ ] P10.3:验证 cross-check `disputed_open: 0`
- [ ] P10.4:验证 evidence 全部 `runtime_enforcement_protocol_version: v1`(沿 archived ADR-012 自 dogfood gap 同款 — wrapper 仍 opt-in 不强制 v2)
- [ ] P10.5:验证 writeback_commit 真实性
- [ ] P10.6:验证 tasks.md P0-P10 全 [x](P11/P12 留 archive)
- [ ] P10.7:`openspec validate restore-superpowers-worktree-consent-gate --strict` 全绿
- [ ] P10.8:落 `verification/finish_gate_report.md`(自 finish_gate 自动生成)

## P11 — Archive(用户授权 fence #1)

- [ ] P11.1:**用户授权确认**(D-AutonomyBoundary fence #1 不可逆)
- [ ] P11.2:`openspec archive restore-superpowers-worktree-consent-gate --skip-specs --yes`
- [ ] P11.3:手工 sync 3 MODIFIED Requirement to `openspec/specs/examples-and-acceptance/spec.md`(替换原 ADR-011/012 mandatory 版)
- [ ] P11.4:`openspec validate examples-and-acceptance --strict` 全绿
- [ ] P11.5:archive stub 加 cross_check fence-required frontmatter(沿 ADR-012 P11.5)
- [ ] P11.6:`git rm -r openspec/changes/<id>/`(防 archived ADR-012 同款 duplicate bug)
- [ ] P11.7:commit + push(用户授权 fence #1)

## P12 — 后置(可选)+ Follow-on tracking

- [ ] P12.1:更新 `MEMORY.md` 加 ADR-013 摘要(沿 forgeue auto memory 协议)
- [ ] P12.2:实战 dogfood 验证 — 下一个 active change 按 ADR-013 default decline 流程跑(controller 默认 main repo cwd;不 invoke wrapper)
- [ ] P12.3 (follow-on tracking 沿 archived ADR-012 P12.3-P12.8):**`enhance-workflow-automation-ledger-binding`** / **`enhance-workflow-automation-handoff-persistence`** / **`add-forgeue-brainstorm-stage`** / **`enhance-workflow-automation-finishing-branch`** / **`enhance-workflow-automation-final-review-fence-strictness`** / **`enhance-workflow-automation-v2-fence-hardening`** — 全保留 in tracking;本 change 不影响 these follow-ons(都与 worktree 解耦)
- [ ] P12.4 (follow-on tracking;user 拍板 2026-05-05 retrospect):**`analyze-superpowers-skills-openspec-integration-gaps`** — 6 个 Superpowers 技能与 OpenSpec / ForgeUE workflow 体系**适配缺口**系统分析(brainstorming / explore stage,先 scope discovery 再 fix):
  - **scope 的 6 技能**:
    1. `superpowers:verification-before-completion` × 12-key audit frontmatter / cross-verify ritual — "声明 → 验证命令 → 观察输出 → 对比"仪式没显式 wire 入 forgeue 命令(本 change archived 期 ADR-012 P3 implementer "1547 PASS" 自我汇报幻觉根因之一)
    2. `superpowers:receiving-code-review` × cross-check A/B/C/D 模板 — 技术 rigor 框架(claim 验证 / 不 blind implement)只在 cross-check ## D 段隐式;ADR-012 期 4 次 codex review 出 finding 时未显式 invoke,沿"informally cross-verify"路径
    3. `superpowers:systematic-debugging` × debug_log evidence — hypothesize-test-narrow framework 只 mention 在 forgeue:change-debug 命令描述;ADR-012 P5.5 F2 修复时 17GB 死循环 incident 暴露 controller 没 systematically debug(没 reproduce in isolation / 没 hypothesis-driven test)
    4. `superpowers:finishing-a-development-branch` × P11 archive + push — merge / PR / cleanup 决策框架未 wire 入 forgeue:change-finish;ADR-012 archive 期 controller improvised + 漏 git rm 致 duplicate bug + force push 修
    5. `superpowers:test-driven-development` × tdd_log evidence — per-task TDD 4-step 节奏在 implementer prompt 隐式提示;无 explicit `Skill(superpowers:test-driven-development)` invocation 在 forgeue 命令模板;P3 markdown lint phase 完全没 TDD(implementer 直接 markdown edit)
    6. `superpowers:dispatching-parallel-agents` × W2 actual diff — borrowed-pattern note 在 forgeue:change-apply-parallel 但 actual skill content 与 ForgeUE W2 actual diff 协议不对应(skill 是 debugging-focused dispatch;W2 是 implementation actual overlap detection)
  - **scope 不属本 change**:这是 6 技能 × ForgeUE workflow 7 stage(S0-S9)+ 12-key audit frontmatter / cross-check matrix / fence / evidence type 的 **systematic 适配 audit**;不是单 change 能 fix
  - **建议 stage 类型**:explore / brainstorming(scope discovery first;沿 `superpowers:explore` 或 `superpowers:brainstorming` skill 框架)→ 然后拆 N 个 sub-change(per-skill wiring)
  - **触发条件**:本 change(restore-superpowers-worktree-consent-gate)ship 后,user 拍板启动;或在另一 change 实施期再次 incident 暴露同款 gap → 启动 priority bump
  - **依据**:本会话 retrospect 实证 — ADR-012 P3 implementer 自我汇报幻觉 / P5.5 F2 死循环 / archive duplicate / inline fix vs round 2 决策 ad-hoc / TDD 隐式 等 5+ incident 都 attributable to "Superpowers thinking discipline 没显式 wire 入 ForgeUE process discipline"。**ForgeUE process thick / Superpowers thinking thin** 是 systemic gap,不是单 incident
