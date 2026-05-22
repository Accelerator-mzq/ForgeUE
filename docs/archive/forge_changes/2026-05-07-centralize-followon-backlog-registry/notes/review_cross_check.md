---
change_id: centralize-followon-backlog-registry
stage: S7
evidence_type: implementation_cross_check
contract_refs:
  - design.md
  - tasks.md
  - review/codex_design_review.md
  - review/codex_plan_review.md
  - review/design_cross_check.md
  - review/plan_cross_check.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-apply-subagent
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
  cascade_check_pass_at: 2026-05-07T17:30:00Z
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
created_at: 2026-05-07T22:25:00Z
resolved_at: 2026-05-07T22:25:00Z
disputed_open: 0
---

# Implementation Cross-Check — centralize-followon-backlog-registry

> Implementation phase final cross-check(沿 retire-parallel-and-worktree-fully `notes/review_cross_check.md` 同款 A/B/C/D pattern,但本文件是 implementation cross-check 而非 design/plan cross-check)。

## A. Implementation summary vs contract

| Contract item(design.md / spec.md) | Implementation evidence | Status |
|---|---|---|
| Registry `openspec/backlog/active.md` 23 entries(8 wf + 9 SRS + 6 cap-bound) | P1.3.1-P1.3.8 + P1.4 + P1.5 落 active.md;test_followon_registry.py TestActiveMdSchema 13 tests verify | ✅ aligned |
| Registry `openspec/backlog/archived.md` 3 first-batch tombstones | P1.6 + test_followon_registry.py TestArchivedMdSchema 7 tests verify | ✅ aligned |
| `_check_followon_continuity` blocker fence(active.md self-diff + archived tasks.md fallback + cancel ref strict + tombstone 5-point + archived.md append-only) | P2.a-P2.f 实施 + P2.f register + 端到端 TDD red→green test 验证 wired into build_report | ✅ aligned |
| `_check_srs_registry_consistency` blocker fence(set 等价 + 状态变化同步) | P2.g 实施 + register + anti-regression test | ✅ aligned |
| Cancel ref strict validation(supersedes Path.exists / commit rev-parse + commit-touches + evidence escape hatch / reason 5-class enum) | P2.d.1-P2.d.4 + 31 unit tests cover all branches + P5 dogfood verified working on real repo | ✅ aligned |
| `followon_continuity` evidence frontmatter 13th conditional 字段(4-list) | change-apply-{subagent,direct}.md template updates(P4) | ✅ aligned |
| `/forgeue:change-status` `### Followon Backlog` block + `--list-followon-*` calls | P3 + P4(change-status.md template) | ✅ aligned |
| Tombstone schema 4 fields(archived_at_commit / archived_in_change / cancellation_reason / registry_entry_snapshot) | P1.6 archived.md + spec.md ADDED Requirement scenarios | ✅ aligned |
| 3 round codex adversarial review,disputed_open=0 | round 1 + round 2 + round 3 close(详 §B) | ✅ aligned |

无 contract gap。

## B. Codex Findings × Implementation

(Cross-references for traceability;详细 disposition 见 design_cross_check.md ## B/F + plan_cross_check.md ## B)

| Round | Finding | Resolution | Implementation evidence |
|---|---|---|---|
| R1 F1 | active.md hard source-of-truth | accepted-codex stance flip | P2.b `_get_change_baseline_commit` + `_validate_tombstone_consistency` |
| R1 F2 | cancel ref strict validation | accepted-codex 5-class enum + Path/git ref | P2.d 4 helpers + 31 tests |
| R1 F3 | SRS↔registry consistency fence enforce | accepted-codex(D-CrossLinkSync 升级) | P2.g `_check_srs_registry_consistency` + register |
| R1 F4 | followon_continuity 4-list canonical | accepted-codex schema unify | proposal/design/spec all aligned |
| R2 F1-r2 | baseline anchor via `last archive commit` not `active.md path commit` | accepted-codex implementation correctness | P2.b.1 `_get_change_baseline_commit` ✓ |
| R2 F2-r2 | tombstone 5-point consistency | accepted-codex(JSON parse + 8-field + critical fields + archived_in_change + cancellation_reason) | P2.b.4 `_validate_tombstone_consistency` + 7 tests |
| R2 F3-r2 | commit-touches strict + escape hatch(scope expansion) | user 拍板 (α) accept | P2.d.3 `_validate_cancel_tag_completed` + 8 tests |
| R3 F1-r3 | drop `--check-followon-continuity` flag(use aggregate) | accepted-codex inline | P4.1 change-finish.md updated |
| R3 F2-r3 | TDD end-to-end fence-register guardrail | accepted-codex inline | P2.f.1-P2.f.5 TDD red→green + anti-regression test |
| R3 F3-r3 | phase decision table single Mode column | accepted-codex inline | execution_plan.md table rewrite |

10 finding 全 inline writeback;无 disputed-permanent-drift in design/plan stages。

## C. Disputed Count

- **Design + plan stages**(round 1 / 2 / 3):`disputed_open: 0` across all
- **Verify stage**(P5):`disputed-permanent-drift: 1`(`fix-cross-check-format-test-enum-extension` pre-existing pytest fail;非本 change 引入;follow-on 已 backfill;Reasoning Notes anchor `pre-existing-pytest-fail-disputed-permanent-drift` in design.md ✓)
- **Final implementation cross-check**:`disputed_open: 0`

## D. Independent verification(Implementation phase)

| Item | Independent verify | Verdict |
|---|---|---|
| Registry 23 entries 数 | `pytest test_followon_registry.py::test_active_md_total_entry_count_matches_p0_backfill` PASS | ✅ |
| Tombstone 3 first-batch | `test_archived_md_first_batch_three_tombstones` PASS | ✅ |
| `_check_followon_continuity` wired into build_report | `test_check_followon_continuity_runs_via_build_report_when_active_md_entry_deleted_without_tombstone` PASS(TDD red→green guardrail) | ✅ |
| `_check_srs_registry_consistency` wired | `test_srs_registry_consistency_fence_remains_registered` PASS | ✅ |
| Cancel ref strict validation each branch | 31 unit tests in `test_validate_cancel_tag_*` | ✅ |
| Tombstone 5-point consistency | 7 unit tests + `test_check_followon_continuity_runs_via_build_report` end-to-end | ✅ |
| Round 2 F3-r2 scope expansion implemented | spec.md scenarios + P2.d.3 `_validate_cancel_tag_completed` + 2 escape hatch tests | ✅ |
| Round 3 F2-r3 fence register guardrail | `test_followon_fences_remain_registered` + end-to-end test PASS | ✅ |
| P5 dogfood 2 bugs fixed | commit `646989c` GBK encoding + SRS sync(TBD-009 ✅ + TBD-013 row);re-run fence `[]` empty list PASS | ✅ |

无 implementation gap;无 spec scenario 缺测试;无 contract drift。

## E. Cross-check disposition

`disputed_open: 0`,implementation cross-check close。Ready to P7.3 finish_gate dogfood self-check(blocker count 应在 P7 mark all tasks done + write final reviewer evidence 后 接近 0 — 仅留 expected 自身 self-stage tasks_unchecked,沿 archive 时 fence 的"self-stage threshold" 行为)。
