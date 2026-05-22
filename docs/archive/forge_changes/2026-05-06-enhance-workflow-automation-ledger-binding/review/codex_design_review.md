---
change_id: enhance-workflow-automation-ledger-binding
stage: S2
evidence_type: codex_design_review
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
codex_review_ref: notes/codex_adversarial_review_review_round1.md
codex_thread_id: 019dfbdc-e826-77e1-a9f9-4faac793ba9b
codex_verdict: needs-attention
review_round: 1
findings_count: 5
findings_severity: high=3, medium=2
drift_decision: written-back-to-design.md+spec.md+tasks.md
writeback_commit: 81edd63
drift_reason: 5 codex round 1 finding 全 valid (round 1 inline writeback commit 81edd63);round 2 加 3 finding 全 closed (commit d96076f);F1 spec/design 文本 contradict;F2 key_rotation WARN 把 unverifiable 当 pass;F3 hash chain 抓不住 tail truncation;F4 audit 字段未 gate 绑定;F5 HMAC 不替代 schema validation;round2-F1+F2+F3 见 review/design_cross_check.md ## E 段
reasoning_notes_anchor: design.md#reasoning-notes
created_at: 2026-05-06T13:53:29+08:00
---

# Codex Design Review (verbatim) — Round 1

> **Verbatim-first 协议**(沿 forgeue:change-plan step 5):本文件保留 codex companion 输出的原文。Resolution + 独立验证落 `review/design_cross_check.md` `## B/C/D` 段。round counter audit trail 保留在 `notes/codex_adversarial_review_review_round1.md`(同款 verbatim 副本)。

```
# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议进入实现阶段:当前 S2 设计在 F2 边界、key rotation、hash-chain 语义和审计字段上存在会让 v3 enforcement 误报安全强度的缺口。

Findings:
- [high] F1 — Spec 重新引入了已明确 out-of-scope 的 pre-dispatch ledger 写入 (specs/examples-and-acceptance/spec.md:264)
  proposal/design 明确本 change 只做 F3,F2 wrapper-bound dispatch 不在 scope;当前命令模板也在 Skill(Task) 返回后 capture 真实 agent_id 再 append ledger。但新 spec 要求"每次 Skill(Task) / SendMessage 调用前先 wrapper append"。append CLI 必填 --agent-id,调用前没有真实 agent_id,只能失败或退回 synthetic ID,等于重新打开 archived F2。
  Recommendation: inline writeback:把 spec 改成 post-dispatch capture 真实 agent_id 后 append,并保留 pre_dispatch_metadata: advisory;若坚持 pre-dispatch,则 scope expansion 到 F2 hook/wrapper-bound dispatch。

- [high] F2 — key_rotation WARN 会把无法验证的 ledger 当成可接受状态 (specs/examples-and-acceptance/spec.md:148-165)
  v3 verify 流程只有当前 key_bytes,却又规定 ledger key_id 与当前 key_id 不一致时 WARN 且不阻断。没有旧 key 时无法重算旧 HMAC:如果先重算,会全部 hmac_mismatch;如果先返回 key_rotation_warn,就接受了一条未验证 ledger。攻击/事故场景里替换 key 文件即可把 HMAC 校验降级成 WARN。
  Recommendation: inline writeback:active v3 finish_gate 对 key_id mismatch fail-closed;若要支持 archived replay,增加 key history/ledger terminal proof 或显式 user override,不要把 unverifiable 当 pass。

- [high] F3 — hash chain 抓不住 tail truncation,却声称任何删除都会 break chain (design.md:93-100)
  设计只用 prev_hmac 串联行,能抓中间删行和 reorder,但删除最后 N 行后剩余前缀仍是一条合法链;单行 ledger 也没有实际链约束。当前 v2 round_fix_continuity 在无 subagent_continuity 或无引用 ID 时会直接跳过 ledger 计数约束,v3 设计也没有 ledger_line_count/final_hmac 这样的外部锚点。结果是删除失败的尾部 reviewer/fix 记录可能不破坏 HMAC。
  Recommendation: inline writeback:在 evidence frontmatter 或独立 receipt 中记录 ledger_line_count + ledger_final_hmac + expected dispatch role count,finish_gate 必须交叉校验;补 delete-last-line 和 one-line-ledger 负例。

- [medium] F4 — v3 protocol 与 cryptographic audit 字段没有被 gate 绑定 (specs/examples-and-acceptance/spec.md:217-223)
  spec 要求 v3 evidence 写 ledger_forgery_resistance: cryptographic,但同一段又明确 finish_gate 不强制该字段 enum。这样 v2 evidence 可以自称 cryptographic,v3 evidence 也可以写 advisory,审计字段与实际 protocol_version 脱钩。考虑到 tasks 还计划用本 change 评估取消后续 hardening,这会制造错误的安全信号。
  Recommendation: inline writeback:finish_gate 增加字段一致性检查:v3 必须 cryptographic,v2 必须 advisory;不匹配作为 dispatch_ledger_violation 或 frontmatter schema violation。

- [medium] F5 — HMAC 只保护字节完整性,不能替代 v2 schema hardening (specs/examples-and-acceptance/spec.md:238-256)
  spec 的 cmd_verify 仍描述为 well-formed JSON、timestamp、wrapper_version 加 v3 HMAC chain;没有要求 exact 11-field schema、round 为正整数、agent_id 格式/长度、protocol_version/wrapper_version 一致、拒绝未知字段等语义校验。当前 v2 append 只校 role,agent_id 可任意字符串,round 是 argparse int 但可为负数。v3 会把无效记录签得很完整,后续若因此取消 v2-fence-hardening 会漏掉 P12.8 原本要补的 schema 风险。
  Recommendation: scope expansion:v3 verify 同时做 strict schema validation,拒绝 unknown fields、缺字段、负 round、float/bool round、超长 agent_id、混合 v2/v3 ledger;P12.8 不应仅因 HMAC ship 自动取消。

Next steps:
- 先对上述 finding 做 inline writeback,尤其修正 spec line 264 的 pre/post-dispatch 矛盾。
- round 2 adversarial review 前补 tail truncation、key rotation mismatch、v3/v2 audit mismatch、strict schema invalid ledger 的测试任务。
```

# Independent Verification(file:line claim 独立验证)

| Codex claim | 独立 verify | Result |
|---|---|---|
| spec.md:264 "调用前先 wrapper append" | Claude Read line 264 字面 confirmed:"命令模板 ... SHALL 在每次 Skill(Task) / Skill(SendMessage) 调用前先 wrapper append" | confirmed |
| spec.md:148-165 v3 verify 流程 + key_rotation WARN | Claude Read line 148-165 verify 流程 step 4 "不一致触发 key_rotation WARN(非 BLOCKER)";line 162-165 verify 状态枚举确含 `key_rotation_detected: WARN` | confirmed |
| design.md:93-100 D-HashChain "任何修改/删除/reorder 必然 break chain" | Claude Read design.md D-HashChain section 字面 confirmed | confirmed |
| spec.md:217-223 finish_gate 不强制 ledger_forgery_resistance enum | Claude Read line 221 字面"`forgeue_finish_gate.py` **不**强制 `ledger_forgery_resistance` 字段值的 enum" | confirmed |
| spec.md:238-256 cmd_verify schema 校 | Claude Read 周边 line — cmd_verify 描述沿 v2 schema-only(仅 wrapper_version 非空 + JSON well-formed + timestamp 单调)+ v3 HMAC chain;无字段 enum / round positive / agent_id format 校 | confirmed |

5/5 codex finding file:line claim 独立验证通过(沿 ForgeUE memory `feedback_verify_external_reviews`,不把 codex claim 当结论)。

# Review session 元数据

- thread id: `019dfbdc-e826-77e1-a9f9-4faac793ba9b`
- broker exit code: 0
- review duration: ~12 min(turn started 13:54 → next-steps 落 14:06)
- 命令调用:`node codex-companion.mjs adversarial-review --background "..."` (background 模式)
- companion subprocess trace 完整记录在 `notes/codex_adversarial_review_review_round1.md` 的"Codex stdout 上下文"段
