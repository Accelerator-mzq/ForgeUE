---
change_id: enhance-workflow-automation-ledger-binding
stage: S2
evidence_type: codex_adversarial_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: false
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_adversarial_review_review_round2.md
review_round: 2
codex_thread_id: 019dfbf3-70fb-7f63-a383-8f7fde5c43dc
codex_verdict: needs-attention
findings_count: 3
findings_severity: high=2, medium=1
prior_round_status: round 1 closed (F1 closed / F2 partial-reopen / F3 closed / F4 closed / F5 closed); round 1 commit 81edd63
drift_decision: written-back-to-design.md+spec.md+tasks.md+proposal.md
writeback_commit: d96076f
drift_reason: 3 codex round 2 finding 全 valid;round2-F1 (承 round1-F2) ledger_archived_replay opt-in 仍可被 active change LLM 滥用绕 fail-closed;round2-F2 unknown protocol_version 未定义 → fail-open;round2-F3 (承 round1-F2/F3) proposal.md 与 final contract 不同步
reasoning_notes_anchor: design.md#reasoning-notes
created_at: 2026-05-06T14:30:00+08:00
---

# Codex Adversarial Review — Round 2 (verbatim)

> **Verbatim-first 协议**:本文件保留 codex companion 输出的原文(round 2)。Round 1 verbatim 在 `notes/codex_adversarial_review_review_round1.md`。Round 2 cross-check Resolution 落 `review/design_cross_check.md` `## B round 2` 段(后续追加)。

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

No-ship: F1 closed, F2 partial/reopen, F3 closed, F4 closed, F5 closed. Round 1 writeback mostly landed, but the archived-replay escape hatch and undefined protocol-version behavior still leave practical fail-open paths.

Findings:
- [high] (round2-F1, 承 round1-F2) archived replay opt-in can still disable HMAC on active evidence (openspec/changes/enhance-workflow-automation-ledger-binding/design.md:230-253)
  The default key_id mismatch path is now fail-closed, but the same design allows `ledger_archived_replay: true` plus `--allow-archived-replay` to skip HMAC and return WARN. The risk section explicitly leaves active-change misuse as only a WARN drift signal / P9.6 follow-on. Because evidence frontmatter is controller-written, an active change can mark itself archived replay, rotate/replace the key, and get the unverifiable ledger accepted on the escape path. That reopens the core round1-F2 bypass under a different flag.
  Recommendation: Do not defer this to P9.6. In this change, make `ledger_archived_replay: true` a BLOCKER unless finish_gate is explicitly running an archived-replay mode and verifies archived change identity/path/metadata; add spec scenarios and tests for active evidence using the opt-in.

- [high] (round2-F2) unknown runtime protocol versions are unspecified and likely fail open (openspec/changes/enhance-workflow-automation-ledger-binding/specs/examples-and-acceptance/spec.md:139-146)
  The dispatch matrix defines only absent/v1/v2/v3 behavior and says future v4/v5 can be added later, but it never states that a present unknown value must fail. Existing gate helpers use exact equality for active protocol checks, so a v3 implementation following the same pattern can treat `runtime_enforcement_protocol_version: v4` or a typo as inactive rather than invalid. That gives a controller-written frontmatter field a simple way to skip v2/v3 fences while not being true legacy evidence.
  Recommendation: Add a protocol-version validity fence: absent means legacy pass-through, but any present value outside `{v1,v2,v3}` is BLOCKER. Add spec scenarios and tests for `v4`, typo values, and empty-string values.

- [medium] (round2-F3, 承 round1-F2/F3) proposal still describes rejected WARN path and omits terminal proof fields (openspec/changes/enhance-workflow-automation-ledger-binding/proposal.md:35-43)
  The proposal's What Changes section still says `cmd_verify` adds exit code 6 as `key_rotation_detected`, WARN rather than fail, and the command-template bullet only upgrades to v3 plus `ledger_forgery_resistance: cryptographic`. It does not mention the required `ledger_line_count` / `ledger_final_hmac` terminal proof fields. This contradicts the corrected spec/design and can drive implementation back toward the round1-F2 WARN behavior or an incomplete round1-F3 terminal-proof implementation.
  Recommendation: Update proposal.md to match the final contract: default key_id mismatch is exit 5 BLOCKER, exit 6 is only explicit archived replay override, and command templates must include `ledger_line_count` plus `ledger_final_hmac` copied from wrapper stdout.

Next steps:
- Block active-change `ledger_archived_replay: true` in the current change, not a later follow-on.
- Add unknown protocol-version fail-fast requirements and tests.
- Sync proposal.md with the corrected design/spec before S3.
```

# Independent Verification(file:line claim 独立验证)

| Codex round 2 claim | 独立 verify | Result |
|---|---|---|
| design.md:230-253 D-KeyRotationHandling Risk + Mitigation 段 | Read line 230-253 — line 253 字面"finish_gate 强校 archived replay 模式不允许 written-by-this-change 的 evidence;本 change ship 后新 v3 evidence 用此字段 = drift signal,**留 follow-on tracking 在 P9.6**" | confirmed — 实际是 defer 到 P9.6,Codex 反驳 valid |
| spec.md:139-146 fence dispatch matrix | Read line 139-146 — 4 档(absent/v1/v2/v3)无 unknown value 处理 | confirmed — 矩阵未覆盖 unknown protocol value 路径,Codex 反驳 valid |
| proposal.md:35-43 What Changes 段 | Read line 37 字面"`cmd_verify`:protocol_version dispatch — `v3` 走整链 verify 分支;exit code 加 6(`key_rotation_detected`,WARN 而非 fail)";line 42 命令模板字段没提 `ledger_line_count` / `ledger_final_hmac` | confirmed — proposal 沿 round 1 原文未跟改,与 round 1 inline writeback 后的 final contract 不同步 |

3/3 round 2 codex finding file:line claim 独立验证通过。无 phantom claim / 无 stale anchor。

# Review session 元数据

- thread id: `019dfbf3-70fb-7f63-a383-8f7fde5c43dc`(round 2)
- broker exit code: 0
- review duration: ~10 min(turn started 14:09 → next-steps 落 14:20 区间)
- 命令调用:`codex-companion.mjs adversarial-review --background "本次 review 是 round 2..."`(round counter & context bridge 协议自动注入 round 1 → round 2 fence,但本次 invoke 已显式 prepend 同款 fence 到 prompt 头)
- companion subprocess trace 完整记录在 `bw9a819yh.output` 同款 broker 输出(round 2 在 `by7xc9p2c.output`)
- 注意:bash heredoc 解析过程出现 4 行 stderr "command not found"(line 1-4),不影响 review 内容(codex 收到的是完整 prompt;heredoc 内的 `$_check...` 等 shell expansion 在 bash 试图 expand 时失败,但实际作为 prompt 字符串传给 node 子进程)
