---
change_id: restore-superpowers-worktree-consent-gate
stage: S2
evidence_type: micro_tasks
contract_refs:
  - tasks.md#Pre-P0
  - tasks.md#P0
  - tasks.md#P1
  - tasks.md#P2
  - tasks.md#P3
  - tasks.md#P4
  - tasks.md#P5
  - tasks.md#P6
  - tasks.md#P7
  - tasks.md#P8
  - tasks.md#P9
  - tasks.md#P10
  - tasks.md#P11
  - tasks.md#P12
  - design.md#decisions
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:brainstorming
    - superpowers:writing-plans
  cascade_check_pass_at: 2026-05-05T22:24:00+08:00
created_at: 2026-05-05T22:35:00+08:00
---

# Micro Tasks — restore-superpowers-worktree-consent-gate

> 沿 `tasks.md` 78 sub-task 索引;按 phase + sub-task anchor 编号。每行格式:`tasks.md#X.Y → action description`。

> **codex round 1 影响**:本 micro_tasks 主体反映 Pre-P0 codex round 1 完成 + writeback 后的 final 状态。
> 若 user 否决 Resolution Plan(W1-W4),本 micro_tasks 需在 user 决议后 refine — 当前以 ✅ accepted-codex 全 writeback 路径为基线。

## Pre-P0 — codex round 1 + writeback(S2→S3 transition;**进行中**)

- `tasks.md#Pre-P0.1` → codex round 1 dispatch 完成(harness task `brhc9296l`,output 落 `notes/codex_adversarial_review_review_round1.md`)
- `tasks.md#Pre-P0.2` → `notes/pre_p0/codex_review_round1.md` reference stub(本 phase 内合并到 `notes/codex_adversarial_review_review_round1.md`)
- `tasks.md#Pre-P0.3` → `review/design_cross_check.md` ## D 段 file:line 验证完成(F1 spec.md:96-101 / F2 spec.md:40-51 / F3 spec.md:5-33 全 verified)
- `tasks.md#Pre-P0.4` → writeback W1-W4(待 user 授权 — 见 Resolution Plan):
  - W1 `design.md`:加 `D-ConsentOutcomeStateMachine` + `D-ParallelDeclineFallback`
  - W2 `proposal.md`:`## What Changes` 加 `worktree_consent_outcome` enum + `worktree_mode` enum + parallel decline auto-fallback
  - W3 `spec.md`:`Preflight Worktree runtime enforcement` Requirement 主文 + 实装 + 3 Scenario 改;`Implementation parallel dispatch` Requirement Scenario 改
  - W4 `tasks.md`:Pre-P0.4 displayed step + P0.2/P0.3 命令模板 MUST invoke + Step 0 outcome capture + P0.3 parallel decline auto-fallback + P1.4 fence 加 `_check_worktree_consent_outcome` + `_check_worktree_mode_consistency`
- `tasks.md#Pre-P0.5` → `notes/pre_p0/plan_cross_check.md`(plan-level cross-check;本 change 沿 archived ADR-012 同款 reference 模式 → `review/plan_cross_check.md` reference stub)
- `tasks.md#Pre-P0.6` → `disputed_open: 0` 验证(已确认:3 finding 全 accepted-codex)

## P0 — 命令模板更新(D-RestoreConsentGate + 待 codex round 1 writeback)

- `tasks.md#P0.1` → Read `.claude/commands/forgeue/change-apply-subagent.md` + `change-apply-parallel.md`(archived ADR-012 P3 mandatory 版)
- `tasks.md#P0.2` → `change-apply-subagent.md` `## Preflight Worktree` section 重写:
  - **MUST invoke** `Skill(superpowers:using-git-worktrees)`(沿 codex F3 writeback;不再 MAY invoke)
  - default decline at Step 0 → main repo cwd(`worktree_consent_outcome: declined` + `worktree_mode: in_place`)
  - opt-in for bug-fix iteration(`worktree_consent_outcome: accepted` + `worktree_mode: skill_worktree`)
  - opt-in W1 wrapper(`worktree_mode: wrapper_worktree` + 必填 `worktree_receipt_path`)
  - 撤 mandatory `python tools/forgeue_preflight_wrapper.py` invocation step
  - evidence frontmatter `worktree_consent_outcome` + `worktree_mode` 必填(沿 codex F2 writeback)
- `tasks.md#P0.3` → `change-apply-parallel.md` 同款重写 + parallel-specific:
  - 同 P0.2 全 4 项
  - **parallel decline → 自动降级 sequential**(沿 codex F1 writeback;无 main repo + parallel + W2 路径)
  - W2 actual diff 段保留但仅在 `worktree_mode ∈ {skill_worktree, wrapper_worktree}` 时 trigger
  - W3 ledger append step 保留(与 worktree 解耦)
- `tasks.md#P0.4` → `change-apply-direct.md` 不动(沿 D-AllChangeApplyMainRepoDefault align;direct 是 < 3 micro-task fallback)
- `tasks.md#P0.5` → fence test 调整:
  - `test_subagent_parallel_have_preflight_worktree_section` 仍 PASS
  - `test_*_invokes_preflight_wrapper` 改 NEGATIVE(不再 mandatory)
  - 加 `test_apply_subagent_parallel_preflight_worktree_must_invoke_skill`(沿 F3 writeback,verify section 内含 `MUST invoke `Skill(superpowers:using-git-worktrees)`` + `worktree_consent_outcome` 字段提示)
  - 加 `test_apply_parallel_decline_auto_fallback_sequential_narrative`(沿 F1 writeback)
- `tasks.md#P0.6` → `pytest tests/unit/test_forgeue_command_markdown.py -v` 全绿
- `tasks.md#P0.7` → `python -m pytest -q` 全套 regress 全绿

## P1 — `forgeue_finish_gate.py` advisory fence(D-AdvisoryFenceMode + codex F2 state machine)

- `tasks.md#P1.1` → Read `tools/forgeue_finish_gate.py` `_check_worktree_path` v1 + `_check_worktree_path_v2` 现状
- `tasks.md#P1.2` → `_check_worktree_path` v1 改 advisory + 加 mode disambiguation:
  - 入口加 `worktree_mode` field check
  - `worktree_mode: in_place` → require `worktree_path` absent(沿 F2 writeback,禁写歧义);若写 → Blocker
  - `worktree_mode: skill_worktree` → require `worktree_path` present + path exists
  - `worktree_mode: wrapper_worktree` → require `worktree_path` + `worktree_receipt_path` 都 present + 都 validate
  - `worktree_mode` field absent → return [](legacy / archived evidence pass-through)
  - `_WORKTREE_REQUIRED_COMMANDS` frozenset retire
- `tasks.md#P1.3` → `_check_worktree_path_v2` 改 advisory + receipt mode-conditional:
  - `worktree_mode: wrapper_worktree` 强制 receipt cross-check(沿 ADR-012 既有 logic)
  - `worktree_mode ∈ {in_place, skill_worktree}` → 不要求 receipt
  - field absent → return [](legacy pass-through)
- 加新 fence `_check_worktree_consent_outcome`(沿 codex F3 writeback):
  - evidence frontmatter `worktree_consent_outcome` 必填(`triggered_by_command ∈ {change-apply-subagent, change-apply-parallel}` 时);取值 `{declined, accepted, already_isolated, sandbox_fallback}`;非法值 → Blocker
  - `worktree_consent_outcome: declined` → require `worktree_mode: in_place`
  - `worktree_consent_outcome: accepted` → require `worktree_mode ∈ {skill_worktree, wrapper_worktree}`
- `tasks.md#P1.4` → fence test 调整:
  - 改 NEGATIVE / advisory:`test_worktree_path_missing_for_change_apply_blocks` → `test_worktree_path_advisory_pass_through_when_mode_in_place`
  - 加 `test_worktree_mode_in_place_rejects_worktree_path_field`(F2 disambiguation)
  - 加 `test_worktree_mode_wrapper_requires_receipt_path`(F2 mode-conditional)
  - 加 `test_worktree_consent_outcome_invalid_blocks`(F3 enum validate)
  - 加 `test_worktree_consent_outcome_declined_requires_mode_in_place`(F3 cross-check)
  - 保留:`test_worktree_path_validates_existing_path_when_provided`
- `tasks.md#P1.5` → `pytest tests/unit/test_forgeue_finish_gate.py -v` 全绿
- `tasks.md#P1.6` → `tests/integration/test_v2_e2e_synthetic_change.py` 11 test review,预计 2-3 调整(加 `worktree_mode` + `worktree_consent_outcome` 字段)
- `tasks.md#P1.7` → `python -m pytest -q` 全套绿

## P2 — wrapper deprecate(D-WrapperDeprecate)

- `tasks.md#P2.1` → `tools/forgeue_preflight_wrapper.py` 顶部加 `__deprecated_note__` + module docstring [DEPRECATED in default flow]
- `tasks.md#P2.2` → `--help` argparse description 加 deprecation notice
- `tasks.md#P2.3` → `pytest tests/unit/test_preflight_wrapper.py -v` 全绿(行为不变)
- `tasks.md#P2.4` → `python -m pytest -q` 全套绿

## P3 — sister skill subagent-driven-discipline v2.3(D-CrossCheckUpstreamCascade + F3 writeback)

- `tasks.md#P3.1` → Pattern 2 STRICT cwd verify 重写:"when `worktree_mode ∈ {skill_worktree, wrapper_worktree}`(after Step 0 consent gate accepted)"
- `tasks.md#P3.2` → 加新 §3.5 "Worktree Consent Policy"(default decline + opt-in for bug-fix + 4 enum outcome 状态机)
- `tasks.md#P3.3` → Case 1 P3 worktree leak scope-down note
- `tasks.md#P3.4` → frontmatter `version: 2.2 → 2.3` + `worktree_consent_policy: default-decline-in-implementation` + `consent_outcome_enum: [declined, accepted, already_isolated, sandbox_fallback]`
- `tasks.md#P3.5` → fence test 校验 sister skill SKILL.md 含 "Worktree Consent Policy" + outcome enum

## P4 — backbone skill `forgeue-integrated-change-workflow` 更新(D-CrossArchiveADRSupersede)

- `tasks.md#P4.1` → Superpowers 集成边界表 `using-git-worktrees` 行重写:"consent-gated;default decline in implementation;opt-in for bug-fix iteration;outcome enum {declined / accepted / already_isolated / sandbox_fallback}(ADR-013)"
- `tasks.md#P4.2` → Runtime Enforcement Protocol(ADR-011)段加 superseded note + outcome state machine 摘要
- `tasks.md#P4.3` → Runtime Enforcement Protocol v2(ADR-012)段加 superseded note + worktree_mode enum 摘要
- `tasks.md#P4.4` → 加新 "ADR-013:Restore Superpowers Worktree Consent Gate" 段(含 outcome state machine + parallel decline auto-fallback)

## P5 — 9 处文档同步(沿 archived ADR-012 P5 模式)

- `tasks.md#P5.1` → `forgeue_integrated_ai_workflow.md` §C.7 + §C.8 superseded + §C.9 ADR-013(含 state machine)
- `tasks.md#P5.2` → `docs/ai_workflow/README.md` §4.4-bis + §4.4-ter superseded + §4.4-quater ADR-013
- `tasks.md#P5.3` → `forgeue_quickstart.md` S3→S4-S5 stage outcome enum + parallel decline 行为
- `tasks.md#P5.4` → `CLAUDE.md` Runtime enforcement frontmatter 段 v1+v2 字段 OPTIONAL 标注 + 加 ADR-013 段(含 outcome enum + mode enum)
- `tasks.md#P5.5` → `README.md` ForgeUE Workflow 表 9 工具不变 + ADR-013 摘要
- `tasks.md#P5.6` → `AGENTS.md` 加 ADR-013 段(沿 ADR-011/012 结构)
- `tasks.md#P5.7` → `CHANGELOG.md` [Unreleased] 加本 change entry(含 codex round 1 finding mention)
- `tasks.md#P5.8` → `SRS.md` 加 ADR-013 行 + ADR-011/012 加 supersede cross-reference
- `tasks.md#P5.9` → `acceptance_report.md` 加 ADR-013 status 行 + ADR-011/012 supersede note

## P6 — verify

- `tasks.md#P6.1` → Level 0 verify 全绿
- `tasks.md#P6.2` → Level 1 verify 全绿(L1 SKIP opt-in)
- `tasks.md#P6.3` → 产 `verification/verify_report.md`(12-key audit frontmatter)

## P7 — codex S6 mixed-scope review

- `tasks.md#P7.1` → `/codex:review --base main --scope branch` mixed-scope(default background)
- `tasks.md#P7.2` → 落 `review/codex_mixed_scope_review.md`
- `tasks.md#P7.3` → writeback finding(沿 simplified protocol)
- `tasks.md#P7.4` → `disputed_open: 0` 验证
- pre-commit P7 替代 stub:codex_design_review.md / codex_plan_review.md / codex_verification_review.md / codex_adversarial_review.md / design_cross_check.md / plan_cross_check.md(沿 archived ADR-012 P7 同款 reference 模式)

## P8 — SKIP superpowers requesting-code-review(沿 archived ADR-012 P8)

- `tasks.md#P8.1` → 写 `review/superpowers_review.md` SKIP rationale stub

## P9 — Documentation Sync Gate

- `tasks.md#P9.1` → `python tools/forgeue_doc_sync_check.py --change <id>` 0 DRIFT
- `tasks.md#P9.2` → 落 `verification/doc_sync_report.md` evidence
- `tasks.md#P9.3` → 任何 [DRIFT] 项 → 修复

## P10 — Finish Gate

- `tasks.md#P10.1` → `python tools/forgeue_finish_gate.py --change <id> --no-validate` 跑(预期 P11 unchecked sole blockers)
- `tasks.md#P10.2-P10.7` → 12-key frontmatter 全填 / cross-check `disputed_open: 0` / evidence v1 protocol_version / writeback_commit 真实性 / tasks.md P0-P10 全 [x] / `openspec validate --strict` 全绿
- `tasks.md#P10.8` → `verification/finish_gate_report.md`(自动生成)

## P11 — Archive(用户授权 fence #1 不可逆)

- `tasks.md#P11.1` → 用户授权(fence #1)
- `tasks.md#P11.2` → `openspec archive <id> --skip-specs --yes`
- `tasks.md#P11.3-P11.4` → 手工 sync 3 MODIFIED Requirement;`openspec validate --strict` 全绿
- `tasks.md#P11.5` → archive stub 加 cross_check fence-required frontmatter
- `tasks.md#P11.6` → `git rm -r openspec/changes/<id>/`(防 duplicate bug)
- `tasks.md#P11.7` → commit + push(用户授权 fence #1)

## P12 — 后置 + Follow-on tracking

- `tasks.md#P12.1` → MEMORY.md 加 ADR-013 摘要(含 outcome state machine)
- `tasks.md#P12.2` → dogfood 验证下一个 active change 按 ADR-013 流程跑
- `tasks.md#P12.3` → 7 follow-on track(`enhance-workflow-automation-ledger-binding` / `handoff-persistence` / `add-forgeue-brainstorm-stage` / `finishing-branch` / `final-review-fence-strictness` / `v2-fence-hardening`)
- `tasks.md#P12.4` → `analyze-superpowers-skills-openspec-integration-gaps` follow-on(6 技能 systematic 适配 audit)

## Self-Review

**Spec coverage**:7 D-decision(包括 codex round 1 writeback 引入的 D-ConsentOutcomeStateMachine + D-ParallelDeclineFallback 2 新 D)全部映射。3 codex finding 全部 writeback 落地到 P0/P1 sub-task。

**Placeholder scan**:无 TBD / TODO;每 sub-task tasks.md anchor 真实存在 + writeback action 具体。

**Type consistency**:`worktree_consent_outcome` enum 4 值统一(declined / accepted / already_isolated / sandbox_fallback);`worktree_mode` enum 3 值统一(in_place / skill_worktree / wrapper_worktree);跨 P0/P1/P3/P5 命名一致。

## References

- `tasks.md` Pre-P0 → P12 phase + sub-task anchor 真源
- `design.md` `## Decisions`(待 codex round 1 writeback W1 加 2 D)
- `review/design_cross_check.md` ## A/B/C/D + Resolution Plan W1-W4
- `notes/codex_adversarial_review_review_round1.md`(codex round 1 raw output)
- archived `2026-05-05-enhance-workflow-automation-executable-enforcement/execution/micro_tasks.md`(模板源)
