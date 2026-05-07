---
change_id: fix-finish-gate-archived-replay-compat
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - tasks.md
  - design.md
  - proposal.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-plan fix-finish-gate-archived-replay-compat
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
disputed_open: 0
created_at: 2026-05-06T23:05:00Z
---

# Plan Cross-check — fix-finish-gate-archived-replay-compat (S3 consolidated stub)

> **Consolidated reference stub**(沿 archived `retire-parallel-and-worktree-fully/review/plan_cross_check.md` 同款模式)。

本 change 在 S2→S3 plan stage transition 只跑一轮 `/codex:adversarial-review`(round 1),覆盖 design + plan artifacts 全部 review 范围;cross-check Decision Summary + Findings 对照 + disputed_open + 独立 file:line 验证已落 [`review/design_cross_check.md`](design_cross_check.md)。本文件做轻量复述给 finish_gate 的 plan_cross_check evidence_type 守门。

## A. Decision Summary(plan-stage 视角)

详见 [`design_cross_check.md ## A`](design_cross_check.md);plan-stage 视角下:
- A.1 In-scope:`tools/forgeue_finish_gate.py` 4 edits + `tests/unit/test_forgeue_finish_gate.py` 9 cases + `CHANGELOG.md` Fixed entry
- A.2 4 D-decision(round 1 codex F1+F2 修订/新增后):D-RegexExtension(round 1 修订)/ D-PerFormatThreshold(round 1 新增)/ D-OpenSpecValidateArchiveSkip / D-DispatchPathDetection(round 1 修订)
- A.3-A.7:11 specs.md scenario / 5 risk + mitigations / L0+L1 验收标准 / 4 disputed-pending hypothesis(全部 codex 没挑战 → A.6 hypothesis 4 项守住 + 暴露 3 项 A.6 没预见的 finding)/ writeback 预期

## B. Codex 3 finding 对照

详见 [`design_cross_check.md ## B`](design_cross_check.md);3 finding(F1 high / F2 medium / F3 medium)全 accepted-codex inline writeback。`disputed_open: 0`。

## C. disputed_open

`disputed_open: 0`(全 accepted-codex 无 round 2 challenge)。

## D. Independent file:line Verification

详见 [`design_cross_check.md ## D`](design_cross_check.md);3 finding 独立验证全 confirmed:
- F1 verify:`tools/_common.py:466-467` archive_dir / `tools/_common.py:484-498` change_path 实证支持 codex F1 root cause(repo 父目录段 false-positive)
- F2 verify:`grep "^## P9 \|^## P10 " openspec/changes/archive/2026-05-06-*/tasks.md` 实测 P9 ambiguous(Documentation Sync Gate workflow prereq + MEMORY.md update self-stage 同号)
- F3 verify:既有 active path test `monkeypatch + count == 1` pattern 是正确,archive case 缺同款监控守门

plan-stage 不重复 verify(共享 raw codex round 1 + 同款 verify table)。

## Round 1 Cross-check Summary

- **Status**:closed(全 3 accepted-codex;0 disputed;0 permanent-drift)
- **`disputed_open`**:0
- **Writeback**:design.md(改 D-RegexExtension + 加 D-PerFormatThreshold + 改 D-DispatchPathDetection + Risks+3 行 + Reasoning Notes)+ specs.md(改 Scenario 7 + 加 Scenario 8/9/10/11)+ execution/micro_tasks.md(改 task_p1 9 case + task_p2 4 edits + task_p3 expected 表)+ tasks.md(改 P1 9 case + P2 5 edits)+ execution/execution_plan.md(File Structure / Contract refs / Phase 总览同步)
- **Next**:S3 ready,进 S4-S5 implementation
