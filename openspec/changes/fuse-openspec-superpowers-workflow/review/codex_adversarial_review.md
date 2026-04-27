---
change_id: fuse-openspec-superpowers-workflow
stage: S6
evidence_type: codex_adversarial_review
contract_refs:
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
  - tools/forgeue_finish_gate.py
  - tools/forgeue_change_state.py
  - tools/_common.py
codex_review_command: "/codex:adversarial-review --background \"<full prompt focused on 7 areas — see body §Codex Output Verbatim>\""
codex_session_id: 019dce76-c5cc-7662-b93f-cd0c355304a1
codex_thread_id: 019dce76-c5cc-7662-b93f-cd0c355304a1
codex_turn_id: 019dce76-c933-7f23-85fc-5e7267260194
codex_background_task_id: btg63drbp
codex_plugin_available: true
detected_env: claude-code
triggered_by: forced
aligned_with_contract: false
drift_decision: pending
writeback_commit: null
drift_reason: |
  P7 codex /codex:adversarial-review --background (mixed-scope, post-self-review) surfaced 6 findings: 1 critical + 3 high + 2 medium. All 6 independently re-verified TRUE by Claude (file:line + live tool reproduction) per ForgeUE memory feedback_verify_external_reviews. 2 of the 6 (F-A=self-review C1, F-D=self-review C2) confirm the Superpowers self-review findings; 4 are NEW (F-B = finish_gate_report self-pollution, F-C = notes/ REQUIRED bypass, F-E = change_state S5 substring, F-F = spec.md test-claim drift). User selected plan A "全改" (P4 §5.8 pattern). Resolution: 7 finding fix (6 codex + I4 from self-review) lands in the resolution-commit alongside this evidence; frontmatter writeback_commit will be amended in a follow-up evidence-backfill commit per P3 / P4 protocol (commits 1c0da37 / 2aceee3). drift_decision = pending until resolution lands.
reasoning_notes_anchor: null
---

# Codex Adversarial Review: fuse-openspec-superpowers-workflow

_Stage S6 mixed-scope adversarial review. Generated 2026-04-27 by `/codex:adversarial-review --background` slash command (gpt-5.4 thread `019dce76-c5cc-7662-b93f-cd0c355304a1`, codex broker session); independently re-verified by Claude per ForgeUE memory `feedback_verify_external_reviews` — full reproduction commands captured in §Independent Verification._

## Scope

- Branch: `chore/openspec-superpowers` @ HEAD `e68e459` (P6 doc sync gate); range `a481682..e68e459` (17 commits, 96 files, +21010 / -21).
- 7 focus areas dispatched to codex (challenge stance, not pure defect pass): design coherence (proposal/design/tasks/spec); tool boundary (5 stdlib tools); test honesty; workflow soundness (8 forgeue commands); doc-patch consistency (P6 README/CLAUDE/AGENTS/CHANGELOG); Reasoning Notes substantiveness; self-host hazard (this change uses its own tools to validate itself).
- Self-review delta given to codex: P7 self-review (`review/superpowers_review.md`) found 2 critical + 5 important + 5 minor; codex was asked to independently re-derive without taking findings for granted.
- Sandbox: codex ran read-only via the codex-plugin-cc broker (commit `37288fe` broker discovery fix; `disable-model-invocation: true` lifted at commit `5dd870c`). No sandbox boundary violations.

## Codex Output (verbatim, per design.md §3 verbatim-first protocol)

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不应发版：finish gate 当前会自阻塞，且 evidence 审计边界存在可绕过路径，P7 前置条件没有被真实满足。

Findings:
- [critical] PASS 的 verify_report 会被 finish gate 当失败处理 (tools/forgeue_finish_gate.py:222-227)
  `forgeue_finish_gate` 只做子串匹配：只要 verify_report body 含 `[FAIL]` 且 frontmatter 为 aligned=true 就报 `verify_report_inconsistent`。但 `forgeue_verify.render_report` 固定输出汇总行 `- [FAIL]: 0`，当前自托管报告也是这一形状。这会让成功验证报告在归档前被 finish gate 自己阻断。
  Recommendation: 改为解析实际失败步骤或只匹配失败步骤行，明确排除汇总计数 `- [FAIL]: 0`；补一个使用真实 render_report 输出的回归测试。
- [high] 失败的 finish_gate_report 会污染后续重跑 (tools/forgeue_finish_gate.py:836-839)
  失败时 `render_report_md` 把自身 frontmatter 写成 `aligned_with_contract: false` 和 `drift_decision: pending`，而 CLI 随后无条件写入 `verification/finish_gate_report.md`。下一次重跑时，`check_frontmatter_protocol` 会扫描这个旧 formal evidence 并因 pending 再次阻断，即使原始 blocker 已修复，用户也会被迫手动删除报告才能恢复。
  Recommendation: 不要把失败尝试写成会参与下一轮 gate 的 formal evidence；可只在无 blocker 时写 `finish_gate_report.md`，或在计算 gate 时忽略上一轮 `finish_gate_report`，失败草稿落到 `notes/`。
- [high] notes/ 可以冒充 REQUIRED evidence 并绕过 12-key 审计 (tools/forgeue_finish_gate.py:249-272)
  required evidence 按 `evidence_type` 从所有 evidence dirs 聚合，诊断文案也允许任意路径位于 `{notes,execution,review,verification}`；但 8-key/12-key 审计只对 `execution/review/verification` 生效。结果是 `notes/foo.md` 只要带 `change_id` 和 `evidence_type: verify_report` 等最小 frontmatter，就能满足 REQUIRED 槽位，同时绕过 `stage/contract_refs/aligned_with_contract/detected_env/...` 校验。
  Recommendation: REQUIRED evidence 只能由 formal subdirs 满足，或任何带 REQUIRED `evidence_type` 的文件无论位于何处都必须通过完整 frontmatter 校验；同步修正 spec/design 对 `notes/` 的边界描述。
- [high] 当前 codex_design_review 证据仍是未决 drift (openspec/changes/fuse-openspec-superpowers-workflow/review/codex_design_review.md:10-12)
  当前 working tree 中 `review/codex_design_review.md` 写着 `aligned_with_contract: false`、`drift_decision: null`、`writeback_commit: null`。这正是 spec Scenario 2 要阻断的形状；即使工具 bug 修好，finish gate 仍会因为这份 P0-era evidence rot 阻断归档。
  Recommendation: 如果该 finding 已在历史 commit 中回写，修正 frontmatter 为对应 `written-back-to-*` 和真实 `writeback_commit`；否则保持 pending 并在 P7 修完后再归档。
- [medium] change_state 同样用 `[FAIL]` 子串破坏 S5 推进 (tools/forgeue_change_state.py:192-199)
  S5 推断用 `if "[FAIL]" not in verify_text`。由 `forgeue_verify` 生成的成功报告固定包含汇总行 `- [FAIL]: 0`，所以刚完成验证的 change 会停在 S4；后续如果出现 review/doc-sync 文件又可能跳到 S6/S7，状态机既无法可靠表达 S5，也会隐藏缺失有效验证的路径。
  Recommendation: 和 finish gate 共用一个 verify_report 解析 helper，按实际 StepResult/失败步骤行判断，不按裸子串判断；补成功报告含 `[FAIL]: 0` 时推断 S5 的测试。
- [medium] spec 声称冻结校验有测试，但测试只查标题存在 (openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md:38-41)
  spec 的 Validation 段声称 `test_forgeue_cross_check_format.py` 覆盖 `## A` frozen-before-codex-call timestamp comparison；实际测试只检查 `disputed_open` 是 int 以及 body 包含 `## A/B/C/D` 标题。也就是说最关键的 anti-bias 约束没有机器校验，文档却声称已验证。
  Recommendation: 要么增加可机器验证的时间戳字段并测试 `A_frozen_at < codex_started_at`，要么删除 timestamp-comparison 的验证声明，把它降级为人工协议。

Next steps:
- 先修 finish_gate/verify_report 的 `[FAIL]: 0` 误判，并补真实报告形状回归。
- 修复 finish_gate_report 自污染与 notes/ REQUIRED evidence 绕过，再重跑 finish gate。
- 回填或纠正 `codex_design_review.md` frontmatter；最后再处理 cross-check frozen 测试声明。
```

## Independent Verification

Each codex finding was independently re-checked by Claude (file:line + live tool reproduction). Reproduction commands captured here so the audit trail does not depend on the verbatim claim alone.

### F-A — verify_report substring self-block (Critical, TRUE)

```bash
$ python tools/forgeue_finish_gate.py --change fuse-openspec-superpowers-workflow --no-validate --json --dry-run \
  | python -c "import json, sys; d=json.load(sys.stdin); print(d['blockers'][0])"
{'type': 'verify_report_inconsistent', 'detail': 'aligned_with_contract: true but body contains [FAIL]', 'file': 'verification/verify_report.md'}
```

Verified at `tools/forgeue_finish_gate.py:223` (substring `[FAIL] in body`); root cause at `tools/forgeue_verify.py:383` (always emits `f"- [FAIL]: {sum(...)}"` summary line). Confirms self-review C1.

### F-B — failed finish_gate_report self-pollution (High, TRUE — NEW)

`tools/forgeue_finish_gate.py:836-839` (`render_report_md`):
```python
aligned = "true" if not report.blockers else "false"
drift_decision = "null" if not report.blockers else "pending"
```
combined with `tools/forgeue_finish_gate.py:944-947` (`main` writes `verification/finish_gate_report.md` unconditionally unless `--dry-run`). On the next run, `_filter_formal_evidence` (line 382-392) keeps the file (it has `change_id` + `evidence_type`); `check_frontmatter_protocol` then sees `drift_decision: pending` → blocker `aligned_false_pending` even though original failures were fixed.

Verified by reading both code blocks; matches codex's claim verbatim.

### F-C — notes/ REQUIRED bypass (High, TRUE — NEW)

`_scan_evidence_by_type` (line 122-151) iterates `_common.EVIDENCE_DIRS = ("notes", "execution", "review", "verification")`. A `notes/foo.md` with frontmatter `change_id: <id>` + `evidence_type: verify_report` enters the `verify_report` bucket; `check_evidence_completeness` then deems the REQUIRED slot satisfied. `_validate_evidence_file` (line 154-202) checks change_id + evidence_type only — NOT the 8 always-required keys. The 8-key audit happens in `check_malformed_evidence` (line 295+) which runs `_filter_formal_evidence` (line 382-392) — but that only checks `change_id + evidence_type` presence, NOT path-formal-ness. So `notes/foo.md` with minimal frontmatter satisfies REQUIRED while bypassing `stage`/`contract_refs`/`aligned_with_contract`/`detected_env`/`triggered_by`/`codex_plugin_available` audit.

Verified by tracing both code paths; codex's claim is precise.

### F-D — codex_design_review frontmatter rot (High/Critical, TRUE)

```bash
$ head -15 openspec/changes/fuse-openspec-superpowers-workflow/review/codex_design_review.md
... aligned_with_contract: false
... drift_decision: null
... writeback_commit: null
```

Per spec.md ADDED Requirement Scenario 2 (`aligned=false MUST set drift_decision != null`), this is a blocker. Confirms self-review C2. Resolution is mechanical frontmatter amend; the actual contract drift was closed at P0 commit `73f18e6c4967c07269cf8a3677bafd497d20b946` per `tasks.md` §1.6.

### F-E — change_state S5 substring (Medium, TRUE — NEW)

```bash
$ python tools/forgeue_change_state.py --change fuse-openspec-superpowers-workflow --json \
  | python -c "import json, sys; print(json.load(sys.stdin)['state'])"
S7   # before fix; reasons listed verify_report_present_but_contains_[FAIL]
```

Verified at `tools/forgeue_change_state.py:195` (`if "[FAIL]" not in verify_text:`). Same `[FAIL]: 0` substring trap as F-A. Live observation: state jumped to S7 via `superpowers_review` + `doc_sync_report` while S5 was never inferred — the state machine silently skipped the verify-pass milestone.

### F-F — spec.md test-claim drift (Medium, TRUE — NEW)

```bash
$ grep -nE "frozen|timestamp" tests/unit/test_forgeue_cross_check_format.py
14:- body MUST contain ``## A.`` / ``## B.`` / ``## C.`` / ``## D.`` headings.
$ # i.e. zero matches for "frozen" or "timestamp" — only structural test
```

`spec.md:41` claimed `## A decision summary frozen-before-codex-call timestamp comparison`. Actual test (`tests/unit/test_forgeue_cross_check_format.py:72-95`) only checks `## A. / ## B. / ## C. / ## D.` heading presence + `disputed_open` field shape. Spec's claim was overstated. The frozen rule is a process protocol (Claude must write `## A` before invoking codex), not a YAML-asserted timestamp comparison.

## Resolution Plan (P4 §5.8 pattern: resolution-commit + evidence-backfill)

7 findings consolidated for single-batch fix in the resolution-commit lands alongside this evidence:

1. **F-A fix-in-tool**: replace `forgeue_finish_gate.py:223` substring check with `_common.verify_report_has_real_failures` helper (regex strips `^- \[FAIL\]: \d+$` count-summary lines). 3 fence tests added (`test_verify_report_has_real_failures_helper_strips_count_summary`, `test_finish_gate_does_not_block_on_zero_fail_count_summary`, `test_finish_gate_blocks_on_real_fail_step_marker`).
2. **F-B fix-in-tool**: `_filter_formal_evidence` excludes `evidence_type: finish_gate_report` (self-evidence — current run rebuilds report each invocation; prior runs carry no audit-relevant signal). 1 fence test (`test_finish_gate_skips_prior_finish_gate_report_in_audit`).
3. **F-C fix-in-tool + written-back-to-design**: `_scan_evidence_by_type` switches from `_common.EVIDENCE_DIRS` to `_FORMAL_EVIDENCE_SUBDIRS` (only formal subdirs participate in REQUIRED satisfaction). `design.md` §3 "Helper vs formal evidence subdir" table extended with new column "是否参与 REQUIRED 满足" (notes/ = 否) + new explanatory paragraph "REQUIRED slot 来源约束". 1 fence test (`test_finish_gate_required_slot_not_satisfied_by_notes_helper`).
4. **F-D written-back-to-evidence**: amend `review/codex_design_review.md` frontmatter `aligned_with_contract: true` + `drift_decision: written-back-to-design` + `writeback_commit: 73f18e6c4967c07269cf8a3677bafd497d20b946` + drift_reason expanded with resolution narrative pointing at the P0 bootstrap that closed the 6 codex blockers per tasks.md §1.6.
5. **F-E fix-in-tool**: `forgeue_change_state.py:195` switches from naive substring to `_common.verify_report_has_real_failures` helper (shared with F-A; same root cause, same fix). 2 fence tests (`test_S5_inferred_when_verify_report_has_only_zero_fail_count_summary`, `test_S4_stays_when_verify_report_has_real_fail_step`).
6. **F-F written-back-to-spec**: `spec.md` Validation §41 entry rewritten — drop the false "timestamp comparison" claim; clarify that `## A frozen before codex run` is a human-attested process protocol enforced by Claude during cross-check workflow, not a YAML chronology. Tests guard structure + `disputed_open`; freeze ordering is in evidence body, not test suite.
7. **I4 fix-in-tool (doc)** [from self-review, not codex]: `CLAUDE.md:162` and `AGENTS.md:172` ban list expanded to all 4 OpenSpec default-product paths (`.claude/commands/opsx/*` / `.claude/skills/openspec-*` / `.codex/commands/opsx/*` / `.codex/skills/openspec-*`).

**Test count delta**: 1126 (P5 baseline) → 1133 (= 1126 + 7 new fences: 3 finish_gate F-A + 1 finish_gate F-B + 1 finish_gate F-C + 2 change_state F-E). Verified `python -m pytest -q` 1133 passed in 44.91s.

**Frontmatter writeback**: this evidence (`codex_adversarial_review.md`) and `review/superpowers_review.md` will be amended in a follow-up evidence-backfill commit to set `aligned_with_contract: true` + `drift_decision: written-back-to-tool` + `writeback_commit: <X.1 sha>` per P3 / P4 backfill protocol (commits `1c0da37` / `2aceee3`).

## Verdict

**With fixes — Resolution lands in this commit.** All 6 codex findings + 1 self-review remainder (I4) verified TRUE and resolved as fix-in-tool / written-back-to-{design,spec,evidence,doc}. No contract write-back needed beyond the design.md §3 helper-vs-formal table extension (F-C) and spec.md Validation entry rewrite (F-F) — both are mechanical clarifications of existing protocol, not new contract decisions. Fence count grew by 7; pytest baseline 1126 → 1133. Ready for P8 finish gate after evidence-backfill commit lands writeback shas in this evidence + superpowers_review.md.
