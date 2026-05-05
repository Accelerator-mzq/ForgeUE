# Tasks — restore-superpowers-worktree-consent-gate

> **沿 ADR-013** revert ADR-011 D-WorktreeEnforce + ADR-012 D-W1-ReceiptSchema worktree mandatory parts;restore Superpowers upstream Step 0 user-consent gate;default decline in implementation phases / opt-in for bug-fix iteration。

## Pre-P0(self-host bootstrap;沿 archived ADR-012 同款 sequential pattern)

- [x] Pre-P0.1:`/codex:adversarial-review` round 1 挑战 7 D-decision + 3 OQ + 5 Risks(verdict: needs-attention;3 finding F1/F2 high + F3 medium;raw output 落 `notes/codex_adversarial_review_review_round1.md`)
- [x] Pre-P0.2:`notes/codex_adversarial_review_review_round1.md` evidence(沿 codex-plugin-cc default 路径,不需独立 `pre_p0/codex_review_round1.md` stub)
- [x] Pre-P0.3:Claude 独立验证 codex finding file:line(F1 spec.md:96-101 / F2 spec.md:40-51 / F3 spec.md:5-33 全 verified;`review/design_cross_check.md` ## D 段)
- [x] Pre-P0.4:writeback 3 finding 到 contract artifact(全 accepted-codex):
  - **W1 design.md**:加 `D-ConsentOutcomeStateMachine` + `D-ParallelDeclineFallback` 2 新 D-decision(替换原 D-AdvisoryFenceMode 隐式状态推断 + 关闭 F1 W2 attribution 漏洞)
  - **W2 proposal.md**:`## What Changes` 加 `worktree_consent_outcome` enum + `worktree_mode` enum 必填字段 + parallel decline 自动降级 sequential
  - **W3 spec.md**:`Preflight Worktree runtime enforcement` Requirement 主文 `MAY invoke` → `MUST invoke` + outcome / mode 状态机 + 4 新 Scenario;`Implementation parallel dispatch` Requirement Scenario `ADR-013 default main repo cwd` → `parallel decline 自动降级 sequential`
  - **W4 tasks.md**:本段 Pre-P0.4 + P0.2 / P0.3 / P0.5 / P1.2 / P1.3 / P1.4 sub-task 加 outcome / mode / decline auto-fallback writeback
- [x] Pre-P0.5:`review/plan_cross_check.md`(plan-level cross-check;沿 archived ADR-012 同款 reference 模式 → 落到 P7 阶段一并写)
- [x] Pre-P0.6:`disputed_open: 0` 验证(已确认:3 finding 全 accepted-codex,无 disputed)

## P0 — 命令模板更新(D-RestoreConsentGate)

- [ ] P0.1:Read 现有 `.claude/commands/forgeue/change-apply-subagent.md` + `.claude/commands/forgeue/change-apply-parallel.md`(archived ADR-012 P3 mandatory 版)
- [ ] P0.2:`change-apply-subagent.md` `## Preflight Worktree` section 重写(沿 codex round 1 F3 writeback):
  - **MUST invoke** `Skill(superpowers:using-git-worktrees)`(沿 upstream Required cascade;不允许只放字符串)
  - Step 0 consent gate outcome capture step → evidence frontmatter `worktree_consent_outcome` 字段(`declined` / `accepted` / `already_isolated` / `sandbox_fallback`)
  - 显式 mode capture step → evidence frontmatter `worktree_mode` 字段(`in_place` / `skill_worktree` / `wrapper_worktree`)
  - "default outcome = declined → work in main repo cwd"(`worktree_mode: in_place`)
  - "opt-in outcome = accepted → worktree creation"(`worktree_mode: skill_worktree`;若 user 显式 invoke W1 wrapper → `worktree_mode: wrapper_worktree`)
  - 撤 mandatory `python tools/forgeue_preflight_wrapper.py` invocation step(wrapper 仅 wrapper_worktree mode opt-in)
- [ ] P0.3:`change-apply-parallel.md` 同款重写 + parallel-specific(沿 codex round 1 F1 writeback):
  - 同 P0.2 Preflight Worktree section(MUST invoke + outcome / mode capture)
  - **parallel decline 自动降级 sequential**:`worktree_consent_outcome: declined` → 命令 abort + 自动 fallback `/forgeue:change-apply-subagent` sequential(无 user prompt;沿 R-no-continue-prompts);evidence frontmatter `degraded_to: change-apply-subagent` + `degradation_reason: parallel_requires_isolated_workspace`
  - W2 actual diff 段保留 但仅在 `worktree_mode ∈ {skill_worktree, wrapper_worktree}` 时 trigger(与 worktree 隔离 attribution boundary)
  - W3 ledger append step 保留(与 worktree 解耦)
- [ ] P0.4:`change-apply-direct.md` 不动(沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项 + ADR-013 D-AllChangeApplyMainRepoDefault align)
- [ ] P0.5:`tests/unit/test_forgeue_command_markdown.py` fence test 调整(沿 codex round 1 F1+F3 writeback):
  - `test_subagent_parallel_have_preflight_worktree_section` 仍 PASS(section 仍存在)
  - `test_change_apply_subagent_invokes_preflight_wrapper` + `test_change_apply_parallel_invokes_preflight_wrapper` 改 NEGATIVE fence(不再 mandatory invoke wrapper)
  - 加新 fence `test_apply_subagent_parallel_must_invoke_skill_using_git_worktrees`(校验 section 内含 `MUST invoke Skill(superpowers:using-git-worktrees)`,不再允许 MAY invoke 或字符串占位)
  - 加新 fence `test_apply_subagent_parallel_preflight_outcome_capture_field`(校验 section 内含 `worktree_consent_outcome` 字段提示)
  - 加新 fence `test_apply_parallel_decline_auto_fallback_sequential_narrative`(校验 parallel section 内含 "decline" → "降级 sequential" / "auto-fallback" 字符串)
- [ ] P0.6:`pytest tests/unit/test_forgeue_command_markdown.py -v` 全绿
- [ ] P0.7:`python -m pytest -q` 全套 regress 全绿(无回归)

## P1 — `forgeue_finish_gate.py` advisory fence(D-AdvisoryFenceMode)

- [ ] P1.1:Read `tools/forgeue_finish_gate.py` `_check_worktree_path` v1 + `_check_worktree_path_v2` 现状
- [ ] P1.2:`_check_worktree_path` v1 改 mode-conditional advisory(沿 codex round 1 F2 writeback):
  - 入口加 `worktree_consent_outcome` field present check:absent(legacy archived)→ return [](pass-through)
  - 入口加 `worktree_mode` field present check:absent → return [](legacy 兼容)
  - `worktree_mode: in_place` → require `worktree_path` absent(违反 → Blocker,关闭 F2 双歧义);present → return []
  - `worktree_mode: skill_worktree` → require `worktree_path` present + path exists
  - `worktree_mode: wrapper_worktree` → require `worktree_path` + `worktree_receipt_path` 都 present(deferred 到 _check_worktree_path_v2 做 receipt cross-check)
  - `_WORKTREE_REQUIRED_COMMANDS` frozenset retire(改空集合;沿 ADR-013 不强制 worktree)
- [ ] P1.3:`_check_worktree_path_v2` 改 mode-conditional advisory:
  - 入口加 `worktree_mode` field present check:absent → return [](legacy 兼容)
  - `worktree_mode: wrapper_worktree` → require `worktree_receipt_path` present + receipt JSON well-formed + receipt `worktree_path` == evidence `worktree_path` + receipt `is_isolated_worktree: true`
  - `worktree_mode ∈ {in_place, skill_worktree}` → 不要求 receipt;若写了 → Blocker(skill_worktree mode 禁写 receipt)
- [ ] P1.4:加新 fence `_check_worktree_consent_outcome` + `_check_worktree_mode_consistency`(沿 codex round 1 F2+F3 writeback):
  - `_check_worktree_consent_outcome`:
    - field absent(legacy archived)→ return []
    - field present + `triggered_by_command ∈ {change-apply-subagent, change-apply-parallel}` → enum value validate(`{declined, accepted, already_isolated, sandbox_fallback}`);非法 → Blocker
    - 校验 invariants:`declined ↔ in_place`;`accepted → mode ∈ {skill_worktree, wrapper_worktree}`;违 invariant → Blocker
  - `_check_worktree_mode_consistency`:
    - field absent(legacy archived)→ return []
    - `mode: in_place` + `worktree_path` present → Blocker(关闭 F2 双歧义)
    - `mode: wrapper_worktree` + `worktree_receipt_path` absent → Blocker(关闭 F2 receipt provenance)
    - `mode: skill_worktree` + `worktree_receipt_path` present → Blocker(skill_worktree 禁写 receipt)
- [ ] P1.5:`tests/unit/test_forgeue_finish_gate.py` 调整 + 加新 fence test:
  - 改 NEGATIVE / advisory:`test_worktree_path_missing_for_change_apply_blocks` → `test_worktree_path_advisory_pass_through_when_mode_in_place`
  - 加 `test_worktree_consent_outcome_invalid_blocks`(F3 enum validate)
  - 加 `test_worktree_consent_outcome_declined_requires_mode_in_place`(F3 invariant)
  - 加 `test_worktree_consent_outcome_accepted_requires_mode_worktree_or_wrapper`(F3 invariant)
  - 加 `test_worktree_mode_in_place_rejects_worktree_path_field`(F2 disambiguation)
  - 加 `test_worktree_mode_wrapper_requires_receipt_path`(F2 mode-conditional)
  - 加 `test_worktree_mode_skill_rejects_receipt_path_field`(F2 mode-conditional)
  - 加 `test_legacy_evidence_no_consent_outcome_field_pass_through`(legacy 兼容)
  - 保留:`test_worktree_path_validates_existing_path_when_provided` + v2 receipt cross-check 同款
- [ ] P1.6:`pytest tests/unit/test_forgeue_finish_gate.py -v` 全绿
- [ ] P1.7:`tests/integration/test_v2_e2e_synthetic_change.py` 11 test review:
  - W1 wrapper test 仍 PASS(opt-in 路径仍 functional;沿 wrapper_worktree mode)
  - finish_gate v2 fence test 调整(加 `worktree_consent_outcome` + `worktree_mode` 字段到 evidence fixture)
  - 若有 test 依赖 mandatory blocker 行为 → 调整(预计 2-3 test)
- [ ] P1.8:`python -m pytest -q` 全套 regress 全绿

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
