---
change_id: fuse-openspec-superpowers-workflow
stage: S3
evidence_type: codex_plan_review
contract_refs:
  - design.md
  - tasks.md
  - notes/pre_p0/forgeue-fusion-codex.md
  - review/codex_design_review.md
  - review/design_cross_check.md
codex_review_command: "n/a (no independent plan-stage codex review run; merged with design-stage hook)"
codex_session_id: "n/a"
codex_thread_id: "n/a"
codex_turn_id: "n/a"
codex_background_task_id: "n/a"
codex_plugin_available: false
detected_env: claude-code
triggered_by: forced
aligned_with_contract: false
drift_decision: disputed-permanent-drift
writeback_commit: null
drift_reason: |
  This change has no independent plan-stage codex review. The plan stage (S2 to S3
  transition) was merged with the design stage at Pre-P0 / P0 time: the plan-level
  cross-check happened at notes/pre_p0/forgeue-fusion-cross_check.md (Pre-P0
  rehearsal, plan v3 vs codex independent alternative, 4 disputed items resolved
  by user verdict — disputed_open == 0), and the design-stage codex
  /codex:adversarial-review hook was rehearsed via codex exec path B at
  review/codex_design_review.md (S2 to S3 hook surfaced 6 blockers + 3 non-blockers,
  all resolved per review/design_cross_check.md). Together those two reviews
  provide the substance the plan-stage REQUIRED slot was meant to deliver:
  independent codex evaluation of the implementation approach plus a structured
  Claude vs codex matrix with disputed_open tracking. Spinning up a fresh
  /codex:adversarial-review hook now (post P7) would re-evaluate already-stable
  contract surface, not the plan stage, and would not retroactively change the
  decision history. Disputed-permanent-drift is the honest accounting: the
  REQUIRED slot stays unfilled in the conventional sense, the rationale lives in
  design.md ## Reasoning Notes anchor reasoning-notes-plan-merged-with-design,
  and future changes that follow the standard S0-S9 lifecycle will produce a
  proper codex_plan_review evidence at S3.
reasoning_notes_anchor: reasoning-notes-plan-merged-with-design
created_at: 2026-04-27T00:00:00+08:00
resolved_at: 2026-04-27T00:00:00+08:00
note: |
  本 evidence 是 thin disputed-permanent-drift accounting,记录 plan-stage codex
  review 与 design-stage 合并的事实。本 change 是首个跑 ForgeUE Integrated AI
  Change Workflow self-host 的 change,Pre-P0 + P0 阶段 plan-level 与 design-level
  cross-check 已用 notes/pre_p0/* + review/codex_design_review.md 完整覆盖,
  disputed_open == 0 已锁。
---

# S3 Plan Review (disputed-permanent-drift accounting): fuse-openspec-superpowers-workflow

## Status

`disputed-permanent-drift` — REQUIRED slot intentionally left unfilled in its
strict form. See frontmatter `drift_reason` (≥ 50 chars) and `design.md`
`## Reasoning Notes` anchor `reasoning-notes-plan-merged-with-design`.

## Substantive Reviews That Cover Plan-Stage Concerns

| Review | Path | What it covers |
|---|---|---|
| Pre-P0 plan-level cross-check | `notes/pre_p0/forgeue-fusion-cross_check.md` | Plan v3 vs codex independent alternative;4 disputed items resolved by user verdict;`disputed_open == 0` |
| Pre-P0 codex independent plan | `notes/pre_p0/forgeue-fusion-codex.md` | 605 lines, 14 sections, full plan-level adversarial output (`codex exec --sandbox read-only` path B) |
| S2 to S3 design cross-check | `review/design_cross_check.md` | 9 findings (6 blockers + 3 non-blockers);`disputed_open == 0` after user verdict;design-stage codex hook rehearsal that addresses all plan-implementation interface concerns |
| S2 to S3 codex design review | `review/codex_design_review.md` | codex `/codex:adversarial-review` rehearsal output (`written-back-to-design` per P7 F-D backfill, `writeback_commit: 73f18e6c4967c07269cf8a3677bafd497d20b946`) |

These four documents together provide what an independent S3 plan review would
have provided: codex-side adversarial reasoning on the implementation approach,
structured Claude vs codex matrix with explicit disputed-open accounting, and
user-resolved verdicts. No plan-implementation choice in `tasks.md` §1-§9 is
unreviewed.

## Why Not Generate Fresh Plan-Stage Codex Review Now

1. **Stage drift.** P7 has already shipped; running `/codex:adversarial-review`
   now would review the post-implementation state, not the S2 to S3 plan stage.
   It would not change which decisions were made nor when they were made.
2. **Contract surface stable.** Subsequent stages (P1-P7) all explicitly
   recorded their decisions in `tasks.md` and `design.md` write-backs;
   re-reviewing the plan stage retroactively would yield duplicates of
   findings already closed in `review/codex_adversarial_review.md` (P7 mixed
   scope) and `review/p4_tests_review_codex.md` (P4 close-out).
3. **Process integrity.** Fabricating a plan_review evidence after the fact
   would violate the very contract this change establishes (`design.md` §3
   "evidence MUST NOT introduce new normative decisions"). The honest account
   is `disputed-permanent-drift` plus a `Reasoning Notes` anchor.

## Future Changes

The standard S0-S9 lifecycle (`design.md` §2) requires `codex_plan_review` +
`plan_cross_check` to be produced at S3. Future changes following this
workflow will run `/codex:adversarial-review` at the S2 to S3 transition and
produce real plan-stage evidence. This change is the self-host bootstrap; the
exemption is one-time.

## Reference

- `design.md` `## Reasoning Notes` anchor `reasoning-notes-plan-merged-with-design`
- `tasks.md` §9.5 (P8 review fixups, type A handling)
- spec.md ADDED Requirement Scenario 3 (`disputed-permanent-drift` protocol)
