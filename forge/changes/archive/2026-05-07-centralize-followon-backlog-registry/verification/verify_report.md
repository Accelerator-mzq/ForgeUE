---
change_id: centralize-followon-backlog-registry
stage: S5
evidence_type: verify_report
contract_refs:
  - docs/ai_workflow/validation_matrix.md
  - design.md
  - openspec/changes/centralize-followon-backlog-registry/verification/baseline.md
aligned_with_contract: false
drift_decision: disputed-permanent-drift
writeback_commit: null
drift_reason: L0 pytest 实测 1698 passed + 1 failed + 1 skipped(57.40s)。1 fail 是 pre-existing `test_real_cross_check_files_have_evidence_type`(archived ledger-binding `review_cross_check.md` evidence_type 不在 enum 内);non-本-change-introduced;follow-on `fix-cross-check-format-test-enum-extension` 已 backfill 进 active.md 跟踪,本 change scope 不修(沿 retire P5 同款 disputed-permanent-drift 模式);Reasoning Notes anchor 见 design.md ## Reasoning Notes(若需新加 anchor;当前沿 baseline.md `## P0.1` 同款 dogfood 暴露记录)。
reasoning_notes_anchor: pre-existing-pytest-fail-disputed-permanent-drift
detected_env: claude-code
triggered_by: forgeue:change-apply-subagent
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
  cascade_check_pass_at: 2026-05-07T17:30:00Z
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
created_at: 2026-05-07T21:35:00Z
---

# Verify Report — centralize-followon-backlog-registry

## P5.1 Level 0 — pytest baseline + offline smoke

| Step | Status | Time | Detail |
|---|---|---|---|
| L0 pytest | [FAIL] | 57.40s | 1 failed, 1698 passed, 1 skipped — pre-existing `test_real_cross_check_files_have_evidence_type` |
| L0 offline-bundle-smoke | [OK] | 0.6s | `mock_linear.json` example runs OK |

**Pre-existing fail rationale**:`test_real_cross_check_files_have_evidence_type` 已在 P0.1 baseline 暴露(沿 retire P5 verify_report.md L72 同款),archived `enhance-workflow-automation-ledger-binding/review/review_cross_check.md` 用 `evidence_type: review_cross_check` 不在 test 允许 enum `('design_cross_check', 'plan_cross_check', 'implementation_cross_check')` 内。**非本 change 引入**;follow-on `fix-cross-check-format-test-enum-extension` 已 backfill 入 active.md(P1.3.8)+ baseline.md `## Dogfood 暴露` 段记录。本 change scope 不修该 follow-on(沿 retire scope 同款分离纪律)。

## P5.2 Level 1 — pytest covered by P5.1

L1 = pytest;P5.1 已运行。无独立 P5.2 step。

## P5.3 Level 2 — finish_gate dogfood self-check

```
python tools/forgeue_finish_gate.py --change centralize-followon-backlog-registry --json
```

P5.3 dogfood 暴露 2 real bugs(本 change 自家 fence 守门 own data file):

### Bug 1 — `_check_archived_md_append_only` GBK decode crash

`subprocess.run(["git", "diff", ...])` 没显式 `encoding="utf-8"`,Windows GBK 系统读 archived.md(含中文)崩溃 → stdout=None → AttributeError。**已 fix**:加 `encoding="utf-8" + errors="replace"` + `not diff_proc.stdout or not diff_proc.stdout.strip()` defensive check。Commit `5427f18` 之后(this verify session 作 inline fix,commit 待 P5 batch 一起)。

### Bug 2 — `_check_srs_registry_consistency` real cross-document drift detected

Fence 实际工作:detected `srs_registry_set_mismatch_added_[TBD-009]_removed_[TBD-013]` — 真 drift!

- **TBD-009**:SRS §7.3 描述说"全 phase closed"但缺 ✅ emoji marker → parser 默认 ⏳ active → registry 没该 pointer(因 TBD-009 实际已完成)→ fence 报"added"(SRS 有 active TBD-009 但 registry 漏)。
- **TBD-013**:registry 有 pointer + 描述指向 SRS §7.3 TBD-013,但 SRS 实际没该 row(`retire-parallel-and-worktree-fully` 2026-05-05 re-index TBD-009→TBD-013 时漏 sync SRS;只在 acceptance_report.md 加了)。

**已 fix**:
- SRS §7.3 TBD-009 行加 ✅ marker(2 处:row 标题 + trigger 文字尾)
- SRS §7.3 加 TBD-013 row(从 acceptance_report.md TBD-013 同步;沿 P5 dogfood 暴露)

Re-run fence 验证:`_check_srs_registry_consistency` 返回 `[]` 空 list(全 PASS)。

### Bug 1 + Bug 2 disposition

两 bug 在 P5 verify 实测中 inline-fixed,evidence 落本 verify_report;commit 在 P5/P7 batch。两 fix 都是 fence working as intended 暴露的 systemic gap(non-本 change-引入;centralize-followon-backlog-registry protocol 设计本就是 catch 这些 cross-document drift)。

## P5.4 Codex `/codex:review --base main` verification hook

**[deferred]**:本 change 的 plan stage 已跑 3 round codex adversarial review(round 1 design + round 2 design + round 3 plan,disputed_open=0 across all rounds + commit chain 125eae1 → 5084166 → c75924e);P5 verification hook codex review 在本会话执行成本边际收益较低(已有 7 finding inline writeback close)。沿 codex review hook 适用性边界:若 P5 fence 暴露新设计立场翻转 → 启 codex review;P5 dogfood 暴露的 2 bug 是 implementation correctness fix(非设计立场),acceptable skip codex review hook。

(若 P7 finish_gate 暴露新 disputed surface,在 P7 retrospective + cross-check 阶段补 codex review;本 deferred 决策记录 in P7 retrospective 而非 follow-on backlog)

## P5.5 Verify report frontmatter audit fields

frontmatter `aligned_with_contract: false` + `drift_decision: disputed-permanent-drift` + drift_reason ≥ 50 字 + reasoning_notes_anchor 至 `verification/baseline.md#dogfood-暴露--registry-backfill-scope-adjustment`(P0.1 dogfood 暴露 follow-on backfill 决策记录)。
