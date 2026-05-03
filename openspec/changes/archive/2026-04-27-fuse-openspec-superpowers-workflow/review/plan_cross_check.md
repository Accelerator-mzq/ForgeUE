---
change_id: fuse-openspec-superpowers-workflow
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - design.md
  - tasks.md
  - notes/pre_p0/forgeue-fusion-cross_check.md
  - review/codex_plan_review.md
  - review/design_cross_check.md
codex_review_ref: review/codex_plan_review.md
plugin_command: "n/a (merged with design-stage hook + Pre-P0 plan-level rehearsal)"
plugin_task_id: "n/a"
detected_env: claude-code
triggered_by: forced
codex_plugin_available: false
created_at: 2026-04-27T00:00:00+08:00
resolved_at: 2026-04-27T00:00:00+08:00
disputed_open: 0
aligned_with_contract: false
drift_decision: disputed-permanent-drift
writeback_commit: null
drift_reason: |
  This change has no independent plan-stage cross-check artifact. Plan-stage
  cross-check happened in two documents authored at Pre-P0 / P0 time:
  notes/pre_p0/forgeue-fusion-cross_check.md (plan-level rehearsal, plan v3 vs
  codex alternative, 4 disputed items resolved by user verdict, disputed_open
  == 0) and review/design_cross_check.md (S2 to S3 design hook rehearsal, 9
  findings resolved with disputed_open == 0). Together they cover the plan
  cross-check protocol's substance — Claude vs codex matrix, disputed_open
  tracking, user verdict resolution, ## A frozen-before-codex-call
  attestation. Producing a third cross-check artifact now would either (a)
  duplicate disputed_open: 0 outcomes already locked, or (b) re-evaluate
  post-implementation state which is no longer the plan stage. Disputed-
  permanent-drift is the honest accounting: the REQUIRED slot stays unfilled
  in its conventional shape, the rationale lives in design.md ## Reasoning
  Notes anchor reasoning-notes-plan-merged-with-design, and future changes
  will produce a proper plan_cross_check at S3 per the standard S0-S9 flow.
reasoning_notes_anchor: reasoning-notes-plan-merged-with-design
note: |
  本 cross-check evidence 是 thin disputed-permanent-drift accounting,记录
  plan-stage cross-check 与 Pre-P0 plan-level + P0 design-level 合并的事实。
  ## A 段不是真正"frozen before codex run"(因无独立 codex 调用),而是引述
  Pre-P0 + design cross-check 已冻结过的 ## A 段(已是 archive-quality
  accounting)。
---

# S3 Plan Cross-check (disputed-permanent-drift accounting): fuse-openspec-superpowers-workflow

## A. Claude's Decision Summary (referenced from already-frozen Pre-P0 + design cross-checks)

> 本段引述既有的两份 cross-check 已冻结过的 Decision Summary,而非新冻结一份。
> 原因见 frontmatter `drift_reason` 与 `## D.1` 段。

**From `notes/pre_p0/forgeue-fusion-cross_check.md` ## A**(plan-level,2026-04-26 P0 草稿前):

- D-Architecture-Centralization:OpenSpec 中心化 vs 三方并立 — Claude 选中心化(plan v3 §1)
- D-WriteBackProtocol:回写不可绕过(`aligned_with_contract: false` MUST 带 `drift_decision`;evidence 不能成新规范源)— Claude 选 mandatory(plan v3 §3)
- D-DRIFTTaxonomy:4 类 named DRIFT(`evidence_introduces_decision_not_in_contract` / `evidence_references_missing_anchor` / `evidence_contradicts_contract` / `evidence_exposes_contract_gap`)— Claude 选独立 named taxonomy(plan v3 §3)
- D-CommandsCount:`/forgeue:change-*` 命令数量 — Claude 选 8 个,不包 OpenSpec contract create/archive(plan v3 §4 + 用户裁决 2026-04-26 accepted-claude)
- D-DocsCount:integrated workflow 文档份数 — Claude v3 §14.1 推迟到 P1 决,Codex 推荐 1 份合并,用户裁决 2026-04-26 accepted-codex(plan v3 §A1 推迟项)

**From `review/design_cross_check.md` ## A**(P0 contract 起草后,design-stage,2026-04-26 22:30):

- D-Capabilities / D-DeltaScope / D-DRIFT-Taxonomy / D-ReasoningNotesHeading / D-FrontmatterSize / D-DocSyncP6-7.5.1 / D-DisputedReasonLength-Severity / D-DeltaSpec-Validation/Non-Goals(8 项,见原文)

两份 ## A 在各自 codex 调用前冻结(Pre-P0 = `codex exec --sandbox read-only` 路径 B 之前;design = `codex_design_review` 调用之前),Claude 未回填,符合 cross-check 协议 R6(防 anchoring bias)。

## B. Cross-check Matrix (referenced from existing two cross-checks)

本 evidence 不重新跑 Claude vs codex matrix(无新 codex 调用)。引述既有两份:

| Source | Findings | disputed_open at resolution | Final state |
|---|---|---|---|
| `notes/pre_p0/forgeue-fusion-cross_check.md` ## B | 4 disputed items(C.1 D-CommandsCount = accepted-claude / C.2 D-DocsCount = accepted-codex / C.3 D-FutureCapabilitySpec = accepted-claude / C.4 D-FrontmatterSchema = accepted-codex) | 0 | locked at Pre-P0 |
| `review/design_cross_check.md` ## B | 9 findings (B1-B6 blockers all accepted-codex / N1-N3 non-blockers: 2 accepted-codex + 1 accepted-claude) | 0 | locked at P0 |

**No item from these two cross-checks was disputed-pending at resolution.** All
disputed-blocker items received user verdicts at the time the cross-check was
authored. None were re-opened by P1-P7 implementation work.

## C. Disputed Items Pending Resolution

`disputed_open: 0`. No `disputed-pending` / `disputed-blocker` items remain
from either referenced cross-check.

This `plan_cross_check.md` itself is **`disputed-permanent-drift`** in
frontmatter (`drift_decision: disputed-permanent-drift`), but that is a
classification of the artifact-level REQUIRED slot, not an unresolved
cross-check item. The classification is documented in `design.md` `##
Reasoning Notes` anchor `reasoning-notes-plan-merged-with-design` per the
spec.md ADDED Requirement Scenario 3 protocol.

## D. Verification Note

### D.1 Why no independent plan-stage cross-check exists

Plan-stage cross-check is conceptually `Claude plan vs codex independent plan
+ structured matrix with disputed_open tracking`. This change satisfied that
substance via two artifacts authored at Pre-P0 / P0 time:

1. **Pre-P0 plan-level rehearsal** (`notes/pre_p0/forgeue-fusion-*.md`) —
   actual plan-level rehearsal: Claude wrote plan v3, Codex wrote independent
   alternative via `codex exec --sandbox read-only` path B, Claude authored
   cross-check matrix, user resolved 4 disputed items. `disputed_open: 0`.
   This IS plan-level cross-check substance, just stored in `notes/` as a
   one-time rehearsal evidence per `design.md` §11.4 (Pre-P0 codex-rescue
   exemption is a one-time exception; the plan-level cross-check itself is
   contract-quality).
2. **S2 to S3 design hook rehearsal** (`review/design_cross_check.md`) — the
   design cross-check spans plan-implementation interface concerns (DRIFT
   taxonomy / frontmatter schema / heading levels / severity) that an S3
   plan review would have caught. 9 findings resolved with
   `disputed_open: 0`.

A fresh `plan_cross_check` would either duplicate items already locked
(disputed_open: 0 → 0) or re-evaluate post-P7 state which is no longer the
plan stage.

### D.2 Resolution completeness

- All Pre-P0 4 disputed items: user verdict 2026-04-26, `disputed_open: 0` ✓
- All design cross-check 9 findings: B1-B6 + N1-N2 accepted-codex (contract write-back); N3 accepted-claude (≥ 20 char reason) ✓
- No plan-implementation choice in `tasks.md` §1-§9 is post-resolution
  unreviewed (P4 codex review + P7 self+adversarial review provide the missing
  post-implementation perspective)
- frontmatter `disputed_open: 0` self-consistent with body ✓

### D.3 P8 archive prerequisite

For finish gate to PASS this `plan_cross_check.md` evidence file:

- 4 cross-check sections (`## A.` / `## B.` / `## C.` / `## D.`) present ✓
- frontmatter `disputed_open: 0` ✓
- frontmatter `drift_reason` ≥ 50 chars ✓
- frontmatter `reasoning_notes_anchor` resolves to `design.md` `## Reasoning
  Notes` paragraph ≥ 20 words / ≥ 60 non-whitespace chars ✓ (added in same
  P8 commit alongside this evidence)
- `disputed_open == 0` ⇒ no `cross_check_disputed_open` blocker ✓

### D.4 Future changes

Standard S0-S9 lifecycle requires `plan_cross_check` at S3. Future changes
following this workflow run `/codex:adversarial-review` at S2 to S3 and
produce a real `plan_cross_check.md` with a fresh `## A` frozen before the
codex call. This change is the self-host bootstrap; the
`disputed-permanent-drift` accounting is one-time.
