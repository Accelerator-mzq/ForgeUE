---
change_id: enhance-workflow-automation-ledger-binding
stage: S3
evidence_type: codex_adversarial_review
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: false
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-apply-direct
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_adversarial_review_review_round3.md
review_round: 3
codex_thread_id: 019dfc0e-0619-73b1-8dd0-066b99bd9c9a
codex_verdict: needs-attention
findings_count: 4
findings_severity: high=2, medium=2
prior_round_status: round 1 closed (commit 81edd63) / round 2 closed (commit d96076f)
drift_decision: written-back-to-execution_plan.md+micro_tasks.md+spec.md+tasks.md+forgeue_dispatch_ledger.py
writeback_commit: pending
drift_reason: 4 codex round 3 finding 全 valid;round3-F1 cmd_verify dispatch fragile (LLM 改所有行 protocol_version 降级 v2 path);round3-F2 cmd_verify terminal proof 无 CLI input path;round3-F3 writeback-check archived replay 检测漏 micro plan;round3-F4 append 缺 cross-platform file lock
reasoning_notes_anchor: design.md#reasoning-notes
created_at: 2026-05-06T15:35:00+08:00
---

# Codex Adversarial Review — Round 3 (verbatim, plan focus)

> **Verbatim-first 协议**(沿 forgeue:change-apply-direct step 5):本文件保留 codex companion 输出原文(round 3 plan focus)。Round 1+2 verbatim 在 `notes/codex_adversarial_review_review_round1.md` + `round2.md`。Round 3 cross-check Resolution 落 `review/plan_cross_check.md` `## B/C/D` 段。

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

No-ship: round 3 plan still has executable gaps that can reopen round1-F3/F5 protections in `cmd_verify`, plus one round2-F1 plan-coverage omission.

Findings:
- [high] round3-F1: cmd_verify can downgrade tampered v3 rows to v2 verification (execution/micro_tasks.md:597-620)
  Round 3 new finding,承 round1-F5/round2-F2. The P2 sketch dispatches v3 only when any ledger line has `protocol_version == "v3"`; otherwise it falls back to the existing v2 schema-only path. Existing v2 verify only checks JSON, `wrapper_version`, and timestamp monotonicity, so if all v3 rows are hand-edited to `protocol_version: "v2"`/`"v4"` or the field is removed while HMAC fields remain, `cmd_verify` can skip strict schema and HMAC verification entirely. That contradicts the listed wrong-protocol test and lets standalone verify/L2 evidence bless a forged ledger.
  Recommendation: inline writeback: make any v3-only field or wrapper_version 2.0 force v3 strict validation, reject any present line `protocol_version` not exactly `v3`, and add tests where every row is downgraded to `v2`/`v4`/absent.

- [high] round3-F2: cmd_verify terminal proof has no actionable input path (execution/micro_tasks.md:507-632)
  承 round1-F3. P2 says `cmd_verify` runs `verify_terminal_proof` only if `--evidence-line-count` and `--evidence-final-hmac` are provided, but the parser sketch only adds `--allow-archived-replay`; P2.2.1 also says to run `cmd_verify` by subprocess without specifying how those evidence values are passed. The spec and tests expect `cmd_verify` to detect `tail_truncation_detected`/`final_hmac_mismatch`, and P5 L2 calls plain `verify --change <id>`. As planned, standalone verify cannot observe the terminal proof, so the round1-F3 mitigation is not test-driven or implementable for that CLI path.
  Recommendation: inline writeback: either add explicit CLI args and update P2/P5 tests to pass them, or remove terminal-proof responsibility from `cmd_verify` and limit it to finish_gate with matching spec/task edits.

- [medium] round3-F3: writeback-check path for archived replay misuse drops out of micro plan (execution/micro_tasks.md:671-728)
  Round 3 new finding,承 round2-F1. execution_plan includes `tools/forgeue_change_state.py` for `archived_replay_path_violation`, and spec/tasks require `--writeback-check` to detect active evidence with `ledger_archived_replay: true`. But micro-P3 only enumerates finish_gate tests/functions and the commit only adds `tools/forgeue_finish_gate.py` plus its tests. An implementer following this plan can ship the finish_gate blocker while leaving the writeback/status drift detector unchanged, losing the early drift signal that round2-F1 explicitly added.
  Recommendation: inline writeback: add a P3 micro-step and regression test for `forgeue_change_state.py --writeback-check`, and include `tools/forgeue_change_state.py` in the P3 commit scope.

- [medium] round3-F4: append sketch omits ledger locking despite parallel command upgrade (execution/micro_tasks.md:531-562)
  Round 3 new finding. The plan upgrades `change-apply-parallel` to v3, but the P2 append sketch reads the previous HMAC and appends without any file lock. Design risk R3 says this read+write sequence needs a cross-platform lock (`fcntl`/`msvcrt`) because concurrent appends can read the same tail and write two records with the same `prev_hmac`; both appends can report success, then finish_gate later sees a broken chain. execution_plan Risks also omit this implementation risk, so the plan can ship a false-blocking race on a supported dispatch path.
  Recommendation: inline writeback: add a cross-platform append lock or explicitly serialize wrapper append calls in command templates, document the risk, and add at least one concurrent append regression test or a justified deferred follow-on.

Next steps:
- Patch micro_tasks.md before S4 so P2 cmd_verify dispatch and terminal-proof tests are executable.
- Add the missing change_state writeback-check task/test to P3.
- Decide whether ledger append locking is in-scope now or explicitly deferred with a non-parallel serialization guarantee.
```

# Independent Verification(file:line claim 独立验证)

| Codex round 3 finding | claimed file:line | Claude 独立 verify | match |
|---|---|---|---|
| round3-F1 | `micro_tasks.md:597-620` cmd_verify dispatch sketch | Read line 597-620 — `has_v3 = any(line.get("protocol_version") == "v3" for line in lines)` 确实是 fragile dispatch | ✅ |
| round3-F2 | `micro_tasks.md:507-632` cmd_verify terminal proof + parser sketch | Read line 507-632 — parser 只加 `--allow-archived-replay` flag,无 `--evidence-line-count` / `--evidence-final-hmac`;P5 L2 也只 `verify --change <id>` | ✅ |
| round3-F3 | `micro_tasks.md:671-728` micro-P3 commit scope | Read line 671-728 — `git add tools/forgeue_finish_gate.py tests/unit/test_forgeue_finish_gate.py`(漏 forgeue_change_state.py) | ✅ |
| round3-F4 | `micro_tasks.md:531-562` cmd_append sketch | Read line 531-562 — append 读 prev_hmac + 写 record 无 file lock | ✅ |

4/4 codex round 3 file:line claim 独立验证通过。

# Review session 元数据

- thread id: `019dfc0e-0619-73b1-8dd0-066b99bd9c9a`(round 3)
- broker exit code: 0
- review duration: ~9 min(turn started 15:30 → next-steps 落 15:39 区间)
- 命令调用:`codex-companion.mjs adversarial-review --background "本次 review 是 round 3..."`
- companion subprocess trace 完整记录在 `bp2tyyojo.output`(round 3)
