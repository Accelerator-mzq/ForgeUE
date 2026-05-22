---
change_id: adopt-subagent-driven-development
stage: S5
evidence_type: subagent_final_review
contract_refs:
  - tasks.md#9.1
  - tasks.md#9.2
  - tasks.md#9.3
  - tasks.md#9.4
  - design.md#D-EvidenceSchema
  - design.md#D-SkillInvoke
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: forced (Pre-P0 dogfood manual dispatch — final reviewer S6)
codex_plugin_available: true
triggered_by_command: change-apply-subagent
---

# Subagent Final Review (S6 Holistic Post-Implementation — APPROVED_WITH_CONCERNS)

## Status: APPROVED_WITH_CONCERNS

All Critical and Important checks pass;3 Minor informational items 不 archive-blocking。

## Cross-task consistency: ✅

- 16 execution evidence files 全携带一致 12-key + audit `triggered_by_command: change-apply-subagent` frontmatter(5 implementer + 5 spec_review + 5 code_quality_review + task_1 round-1 blocked archive)
- Stage labels uniformly `S4` for execution / `S5` for verification — matches state machine
- Contract refs bind every evidence file 到 specific tasks.md / design.md anchors(no orphan evidence)
- 8 项 design decisions(D-Worktree / D-Default / D-EvidenceSchema / D-SkillInvoke / D-TaskInput / D-ADR009 / D-BudgetMode / D-SelfHost)全部 reflected;**no decision silently bypassed**

## Cross-file integration: ✅

- `change-apply-subagent.md` step 8/8.5 evidence schema(4 类 + Token usage body + audit field)与 `tools/forgeue_finish_gate.py` `_REQUIRED_EVIDENCE_SUBAGENT` enum(line 89-93)+ `_DISPATCH_MODE_FIELD = "triggered_by_command"`(line 103)**fully aligned** — 同 evidence_type 名 + 同 default glob paths
- `tools/forgeue_change_state.py` DRIFT detector lines 369 + 396 都 extended 同款 4 subagent_* evidence_types — no missing / no extra
- `tools/forgeue_subagent_budget.py` `--record` 接受 CLI args 直接(`--tokens-input` / `--tokens-output` / `--model` / `--usd`);evidence body `## Token usage` section 用 separate names(`input_tokens` / `output_tokens` / `model` / `estimated_usd`)。Per design.md F5,controller passes args directly **不读 frontmatter** — 分离 intentional,not bug

## Discipline accumulation: ✅

- `git diff 5fef620..HEAD --stat src/framework/` → **0 lines changed**(sacred — confirmed)
- All 5 F1-F5 codex round-1 findings have **real, verified writeback_commit SHAs** that exist in git:`2ec9cfd`(scaffold + design.md F1+F2+F3+F4+F5 + tasks.md + dogfood)/ `051ef9f`(ADR-008→ADR-009 collision fix)/ `0b59cc9`(task 3 §5 dogfood + tasks.md §5.7 writeback)
- `git rev-parse` on all 3 SHAs succeeds(no fabricated commits)
- 20 commits granular and discipline-aligned:scaffold → 11 docs sync → ADR-009 → command split → finish_gate / change_state extension → fence count fix → budget tool → verify_report — 每个 commit narrow scope,no out-of-bound refactors
- §5.7 fence count regression fix 用 Option C(tags-aware skip via frontmatter)across 3 fixture files — extensible(future deprecated commands 只需 `tags: [..., deprecated]`),preserves discipline boundary

## Final pytest: ✅ 1448 PASS / 1 SKIP / 0 ERRORS confirmed(55-68s wall)

- 1 SKIP = `test_comfy_subprocess_video.py:523`(Windows symlink admin),unrelated
- F1 worktree fence:`test_worktree_isolation_requires_committed_change_artifacts` PASSED
- F2 dispatch mode fence:`test_subagent_dispatch_mode_required_evidence_missing_blocks` PASSED
- F3 DRIFT fence:`test_subagent_spec_review_failure_keyword_triggers_drift_gap` PASSED
- D-BudgetMode fence:`test_warn_threshold_breach_keeps_exit_zero` PASSED
- 62 finish_gate cases + 62 change_state/budget cases all green

## Documentation readiness preview: ✅

- `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.3(line 148-149)`using-git-worktrees: REQUIRED` + `subagent-driven-development: default` ✓
- §B.6 newly added(line 166+)— full subagent integration boundary documented ✓
- §B.1 state machine table S3/S4 rows reflect command split ✓
- `docs/ai_workflow/forgeue_quickstart.md` §3.3(line 111)— split default subagent + fallback direct ✓
- `CLAUDE.md` line 226-245 — 9 commands + ADR-009 + 6 stdlib tools ✓
- `README.md` line 377-391 — 9 command rows + ADR-009 budget tool reference ✓

## Strengths(holistic)

1. **Self-host bootstrap dogfood honesty** — Pre-P0 codex round-1 found 5 contract gaps(F1-F5),Claude verified each at file:line,all 5 written back to design.md / tasks.md / proposal.md / dogfood protocol with real SHAs。**No "evidence as second-source" violations**
2. **Discipline preserved across 4 dogfood task loops** — `src/framework/` untouched;只 `tools/` + `.claude/commands/forgeue/` + docs touched,exactly as Non-Goals declared
3. **Cross-file enum alignment is mechanically verified** — `_REQUIRED_EVIDENCE_SUBAGENT`(finish_gate)+ DRIFT detector lines 369/396(change_state)share same 4 subagent_* names,same order,**no drift between tools**
4. **F2 fix is architecturally cleaner than the original** — Codex F2 finding caught helper marker file(`dispatch_mode.txt`)could be silently omitted。Replacement(`triggered_by_command` audit field on every evidence)makes dispatch mode unforgeable since command itself writes it
5. **§5.7 16-errors regression handled with full dogfood loop** — task 3.5 implementer + spec_review + code_quality_review evidence 全 landed;meta-finding(dogfood reviewer should run full pytest)captured as lesson
6. **F5 token / cost separation principle codified** — token fields explicitly excluded from 12-key contract frontmatter;budget tool `--record` takes CLI args directly。**Two audits**(contract compliance vs cost tracking)cleanly separated

## Critical issues

**None.**

## Important issues

**None.**

## Minor issues(informational, non-blocker)

1. **`review/` directory was empty before this file** — `openspec/changes/adopt-subagent-driven-development/review/` 第一次有文件;本 review file landing 创建该 directory。沿 §9.1-9.4 task `[ ]` unchecked。**Non-blocker — landing this file satisfies it**
2. **Budget tool field-naming asymmetry across boundaries** — `subagent_budget.log` JSON Lines 用 `tokens_input` / `tokens_output` 而 evidence body `## Token usage` section 用 `input_tokens` / `output_tokens`。Both documented in design.md / dogfood protocol;spec_review accepted as separate concerns。Cosmetic only(controller passes CLI args directly — no field-mapping at runtime)。**Could be unified in follow-on cosmetic PR;non-blocker**
3. **`verify_report.md` ## State machine section minor stale** — Earlier note suggested algorithm 不 detect S5;current writeback-check confirms S5 already。**Minor doc-stale;backfill when verify_report.md updated post-§9**

## Archive-readiness verdict: ✅ ready for §10 / §11(after §9 review evidence lands)

§9.4 transition condition(review blocker == 0 + superpowers_review.md frontmatter `aligned_with_contract: true`)is **satisfied** by this final review when it lands as `review/subagent_final_review.md` with appropriate 12-key + audit frontmatter。No critical/important issues remain。

## Token usage

- input_tokens: ~38,000(full design.md + tasks.md + plan_cross_check + 16 evidence frontmatter + verify_report + 3 fence subset + tool source spot-checks + long-term docs spot-check + git verifications)
- output_tokens: ~3,500
- model: claude-opus-4-7[1m]
- estimated_usd: ~$0.62
- data_source: manual_estimate, not gate-grade(沿 dogfood §5 协议)

## Recommendation

✅ **Proceed to §10 Documentation Sync Gate**

After landing this review as `review/subagent_final_review.md`(with `evidence_type: subagent_final_review` + `triggered_by_command: change-apply-subagent` audit field + 12-key frontmatter),change ready for §10 doc_sync_check + §11 archive cycle。

## Key files referenced

- `openspec/changes/adopt-subagent-driven-development/design.md`
- `openspec/changes/adopt-subagent-driven-development/tasks.md`
- `openspec/changes/adopt-subagent-driven-development/notes/pre_p0/plan_cross_check.md`
- `openspec/changes/adopt-subagent-driven-development/verification/verify_report.md`
- `tools/forgeue_finish_gate.py`(lines 87-103, 268-328)
- `tools/forgeue_change_state.py`(lines 369-421)
- `tools/forgeue_subagent_budget.py`
- `.claude/commands/forgeue/change-apply-subagent.md`
- `.claude/commands/forgeue/change-apply-direct.md`
- `.claude/commands/forgeue/change-apply.md`(deprecated stub)
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(§B.3 / §B.6)
- `docs/ai_workflow/forgeue_quickstart.md` §3.3
- `CLAUDE.md` line 226-245
- `README.md` line 377-391
