---
change_id: enhance-workflow-automation
stage: S6
evidence_type: codex_mixed_scope_review
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
  - notes/pre_p0/codex_review_round1.md
aligned_with_contract: false
drift_decision: accepted-codex-2-deferred-1
writeback_commit: 47a58b2
drift_reason: codex P5 round 2 mixed-scope adversarial review raised 3 findings (2 high + 1 medium); F5 + F7 reconciled via 2026-05-05 user feedback D-AutonomyBoundary protocol simplification (commit 47a58b2 — design.md fence list simplified to 6 categories with framework modification + design.md mismatch replacing original fence #3 codex verdict conflict;F5 replay vulnerability eliminated by routing routine implementation evidence to default claude_autonomous which does not require codex_review_ref;F7 spec/impl scoping inconsistency reconciled by limiting finish_gate enforcement to implementation evidence types in spec.md scenario);F6 codex command allowed-tools vs Polling Convention write capability mismatch DEFERRED to follow-on change `enhance-workflow-automation-handoff-persistence`
reasoning_notes_anchor: notes/pre_p0/codex_review_round1.md
detected_env: claude-code
triggered_by: forced (S6 mixed-scope review post P0-P3 implementation)
codex_plugin_available: true
triggered_by_command: change-review
disputed_open: 0
created_at: 2026-05-05T03:30:00+08:00
resolved_at: 2026-05-05T03:50:00+08:00
---

# Codex P5 Mixed-Scope Adversarial Review Round 2 — enhance-workflow-automation

**Codex verdict**: needs-attention
**Codex summary**: 不建议 ship。当前 autonomy boundary 仍可被同一 change 内旧 Codex evidence 重放,默认 background 的 round/poll 状态也没有可执行的持久化保障。

**Scope**: `--base 6939ab5` mixed-scope review(本 change 全 11 commits,35 files / 2739 insertions / 105 deletions)
**Round**: P5 round 2(round 1 是 Pre-P0 在 propose stage 的 4 finding adversarial review,见 `notes/pre_p0/codex_review_round1.md`;本 round 2 review P0-P3 实施 + Pre-P0 writeback 完整性)
**Counter file** (D-CodexContextBridge `_REVIEW_TYPES`): `notes/codex_mixed_scope_review_round_counter.txt` = 1 (P5 round 1 mixed-scope counter — 与 codex_adversarial_review_round_counter 独立 per F1 writeback)

## Codex Findings (verbatim)

```
Findings:
- [high] codex_review_ref 校验可被旧 review 重放,不能证明当前 evidence 已被 Codex 审过 (tools/forgeue_finish_gate.py:967-979)
  _check_autonomy_boundary 只验证 ref 在当前 change 下、evidence_type 属于 codex review 白名单、disputed_open 为 0;没有验证 review_type/stage/被审 commit/当前 evidence scope,也没有要求 ref frontmatter 有 verdict 或调用 _check_verdict_normalization。实际 evidence 已经利用了这个空洞:execution/task_p3_implementer.md:18-19 声称 claude_codex_concurred,却指向 notes/pre_p0/codex_review_round1.md;该 ref 是 stage S2 的 Pre-P0 方案审查,不是 P3 实装/文档同步后的 review。这样任何后续 implementation evidence 都能复用同一个旧 ref 通过 finish gate,Claude+Codex concurrence 退化成可重放 token。
  Recommendation: 让 codex review evidence 携带并校验 review_type、target_stage/scope、reviewed_commit、verdict;_check_autonomy_boundary 或 finish_gate 应拒绝当前 evidence 指向不匹配/过旧的 ref,并对 ref 运行 verdict normalization。补一个 P3/S4 evidence 指向 Pre-P0 ref 必须 block 的回归测试。

- [high] Polling 和 round counter 需要写文件,但 codex 命令没有可验证的写入能力 (.claude/commands/codex/review.md:4)
  review.md 的 allowed-tools 只有 Read/Glob/Grep/Bash(node:*)/Bash(git:*),但同一模板后续要求写 round counter、保存 review output、append active_jobs 文件。adversarial-review.md 也是同样的 allowed-tools。当前测试只断言 markdown 里出现 counter 路径和 _active_jobs.txt 字符串,未证明 slash command 能实际创建这些文件。若命令按 tool allowlist 执行,background job id、round counter 和 review evidence 可能根本不会持久化,W1/W4 仍会在真实 workflow 中丢状态或跳过 poll handoff。
  Recommendation: 给命令显式授予 Write/Edit,或提供一个允许的 node helper 来原子写入 counter/active_jobs/evidence,并在测试中执行/模拟该 helper 验证文件实际创建与更新;同时让 finish_gate/change_state 能检测未消费的 active job。

- [medium] finish_gate 只对 implementation evidence 强制 autonomy_decision,和 spec 的"任意 evidence"守门不一致 (tools/forgeue_finish_gate.py:743-749)
  check_frontmatter_protocol 只有在 evidence_type 属于 _IMPLEMENTATION_EV_TYPES 或 frontmatter 已存在 autonomy_decision 时才调用 _check_autonomy_boundary。可是 spec.md 的 finish_gate scenario 写的是扫描 execution/review/verification 时"任意 evidence 缺 autonomy_decision 字段 → exit 非 0"。当前 verification/verify_report.md 有 formal frontmatter 和 evidence_type: verify_report,但没有 autonomy_decision;按现有条件它不会触发 autonomy_boundary_violation。这使 verify/doc-sync/review 类 evidence 可以完全绕过 autonomy audit,至少是 contract 与实现不一致。
  Recommendation: 二选一:要么按 spec 对所有 formal evidence 强制 autonomy_decision,并更新 verify/doc-sync 生成器与 fixtures;要么把 spec/docs 明确改成 implementation-only,并为 verify_report/doc_sync_report/superpowers_review/codex review 的豁免写测试,避免当前这种隐式放行。
```

## Claude 独立验证(round 1 reference 已读 — 4 finding F1-F4 全 accepted-codex,无重复)

| ID | Severity | Codex 推荐 | Claude 独立 verify | Verdict | Resolution |
|---|---|---|---|---|---|
| F5 | high | 加 `target_stage` / `reviewed_commit` / `verdict` 字段 + freshness 校验 + 拒绝过旧 ref + verdict normalization on ref | F5 真实 vulnerability(task_p3_implementer.md 用 Pre-P0 round 1 ref 作 P3 implementation `claude_codex_concurred` credential — replay attack)| **accepted-codex,resolved via simplification** | **2026-05-05 user feedback simplification** 消解 F5 root cause:routine implementation evidence 改用 default `claude_autonomous` (不强制 `codex_review_ref`),消除 ref reuse 路径。**12 evidence files cleanup**(commit 47a58b2):8 个改 frontmatter `claude_codex_concurred`→`claude_autonomous` + 删 `codex_review_ref` + audit note;4 个原已正确;F5 root cause(fake concurrence + 重放 ref)消除 |
| F6 | high | allowed-tools 加 Write/Edit 或 helper 原子写入 + 测试覆盖 | F6 真实功能 gap(命令模板要求写 counter/job_id 但 allowed-tools 只读)| **accepted-codex,deferred** | F6 修复涉及架构选择(allowed-tools 加 Write vs controller 主 session 写状态),scope 较大;**DEFERRED 到 follow-on change** `enhance-workflow-automation-handoff-persistence`;本 change 内 W4 Polling Convention 文档化已完成,实装 enforcement 留 follow-on |
| F7 | medium | 二选一:全 evidence 强制 autonomy_decision OR spec 改 implementation-only + 豁免测试 | F7 真实 spec/impl 不一致(spec.md 字面"任意 evidence",实装 implementation-only)| **accepted-codex,reconciled** | 选 (b) 路径:**spec.md scenario 改为 implementation evidence 限定**(commit 47a58b2 包含)+ design.md D-AutonomyBoundary "implementation evidence" 显式限定;实装 P0 `_IMPLEMENTATION_EV_TYPES` 枚举 6 类型(`subagent_implementer_report` / `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review` / `tdd_log` / `debug_log`)与 spec 一致,不需要再改实装 |

## Resolution Path Summary(per user 2026-05-05 feedback)

User 在 P5 round 2 finding 后给出新指令:**简化 D-AutonomyBoundary fence**,只保留 framework modification / design.md mismatch / 不可逆 / 跨 change / 钱 / 安全 6 类必须升级用户;原 fence #3 "Claude+Codex review verdict 冲突" 删除(Claude 独立 verify 后自主拍板)。

User 显式选 (c) 路径:F5+F7 inline 修,F6 follow-on。

实装路径(commit 47a58b2):
- design.md D-AutonomyBoundary fence list 重写(6 fence 简化版)+ D-FenceTaxonomy 表 row 3/4 重写
- spec.md "Workflow autonomy boundary fence" Requirement 6 fence + scenarios 重写
- spec.md `finish_gate 守门` scenario 加深 "implementation evidence 限定"(F7 reconcile)
- 8 evidence files cleanup `claude_codex_concurred` → `claude_autonomous` + 删 `codex_review_ref`
- saved memory `feedback_autonomy_boundary_simplified.md` 落 user 偏好(后续会话使用)

## Disputed Open

`disputed_open: 0`(F5 + F7 resolved via simplification + spec reconcile;F6 deferred-not-disputed)

## Round Counter

P5 round 2 mixed-scope review 完成。Counter `notes/codex_mixed_scope_review_round_counter.txt` += 1。下一轮(若需要)落 `notes/codex_mixed_scope_review_round3.md`,prompt 注入 round 2 reference。

## Reference

- 详细 codex round 2 finding:`/tmp/p5_codex_mixed_review_v2.txt`(verbatim,本 evidence 已 paste)
- 协议简化 evidence:design.md `D-AutonomyBoundary` 段(2026-05-05 simplification)+ saved memory `feedback_autonomy_boundary_simplified.md`
- F5 cleanup commit:47a58b2(12 evidence files normalized + design + spec simplified)
- F6 follow-on tracking:tasks.md(本 change 末尾追加 P10.3 follow-on note)
