---
change_id: centralize-followon-backlog-registry
stage: S2
evidence_type: codex_adversarial_review
review_round: 2
contract_refs:
  - design.md
  - proposal.md
  - specs/examples-and-acceptance/spec.md
  - tasks.md
  - execution/execution_plan.md
  - execution/micro_tasks.md
aligned_with_contract: false
drift_decision: pending
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
codex_job_id: b876734jn
created_at: 2026-05-07T16:48:00Z
runtime_enforcement_protocol_version: v1
---

# Codex Adversarial Review — round 2(verbatim output)

> 沿 ForgeUE codex output exposure protocol(verbatim-first)。Round 2 是 round 1 F1+F2 立场翻转后的 NEW design surface adversarial pass。round 1 verdict 见 `codex_adversarial_review_review_round1.md`。

---

# Codex Adversarial Review

Target: branch diff against main
Verdict: needs-attention

不建议 ship。round 1 F1/F2 的立场翻转仍有可绕过路径：active.md diff 锚点选错会漏掉已提交删除，tombstone 没有绑定原 entry/cancel 声明，cancelled-completed 仍只挡 typo 不挡 controller drift。

Findings:
- [high] [P1][in-scope][承 round1-F1] active.md self-diff 基线用最新 path commit，已提交删除可绕过 tombstone fence (openspec/changes/centralize-followon-backlog-registry/design.md:148-155)
  设计目标写的是比较 <last_archive_commit> 到 HEAD，但实施步骤把基线定义为 `git log -1 -- openspec/backlog/active.md`。在真实变更中，controller 可以在本 change 的早期 commit 删除 active.md entry 且不写 tombstone；finish_gate 运行时 `git log -1` 会返回这个删除 commit，随后 `git diff <that_commit> HEAD` 为空，删除不会被检测。影响是 active registry 作为 hard source-of-truth 的核心保护只覆盖未提交工作区或删除后又改动的 happy path，不能阻断已提交的 backlog 数据丢失。
  Recommendation: 把 self-diff 基线绑定到当前 change 的启动基线/上一 archive commit，而不是 active.md 的最新 path commit；为"删除 entry 已提交在早期 phase、archive 前无后续 active.md diff"的场景加 BLOCKER 测试。
- [high] [P1][in-scope][承 round1-F1] tombstone 只要求字段存在，未绑定删除 entry、cancel tag 与原始 snapshot (openspec/changes/centralize-followon-backlog-registry/design.md:177-194)
  D-TombstoneProtocol 要求 archived.md 有 4 字段，但 `registry_entry_snapshot` 明确留 trace 且 fence 不解析；self-diff 阶段也只说查 tombstone 行的 id/archived_at_commit/archived_in_change。推论：controller 删除 active.md entry 后，只要 append 同 id 的 tombstone，即使 `archived_in_change` 指向别的 change、`cancellation_reason` 与 tasks.md tag 不一致、snapshot 是 `{}` 或不含原 8 字段，也可能通过。影响是 F1 的"删除必须有墓碑"退化成"删除必须有一行看似墓碑的文本"，审计恢复数据仍可被静默破坏。
  Recommendation: tombstone 校验应解析 `registry_entry_snapshot` 为 JSON object，并校验 id 匹配、8 字段齐全、snapshot 与 prior active.md entry 一致、`archived_in_change` 等于当前 change、`cancellation_reason` 与 tasks.md cancel tag 一致；补字段错/快照错但 id 正确的 BLOCKER 测试。
- [medium] [P2][in-scope][承 round1-F2] cancelled-completed 只校 commit 存在，仍可用无关 commit 移除 backlog (openspec/changes/centralize-followon-backlog-registry/specs/examples-and-acceptance/spec.md:25-28)
  round 1 F2 要求 cancel ref strict validation，但 spec 将 `cancelled-completed` 收敛为 `git rev-parse --verify` 存在性检查，并明确 commit-touches 校验留 follow-on。这个检查只挡拼写错误或不存在 hash；任何历史 commit、doc-only commit 或刚产生的无关 commit 都能让 follow-on 进入 cancelled-completed 并从 active.md 迁出。对防 hand-edit drift 的 blocker fence 来说，这条出口仍是语义绕过，不只是 ergonomics 问题。
  Recommendation: 本 change 内至少要求 completed commit 触达该 follow-on 的 `source`、`contract_refs`、registry entry 或声明的 evidence path；如确有 cross-cutting commit，增加显式 `evidence:` escape hatch 并验证路径存在，避免任意 commit ref 通过。

Next steps:
- 先修正 active.md diff 基线与 tombstone 语义绑定，再进入实现。
- 将 `cancelled-completed` 的 commit 语义校验从 follow-on 拉回当前 change，或明确降级该 cancel 类型为 advisory-only。

---

## Codex 工具操作日志

```
[codex] Get-Content -Raw -LiteralPath openspec/changes/centralize-followon-backlog-registry/notes/codex_adversarial_review_review_round1.md
[codex] rg -n "D-TombstoneProtocol|registry_en..." (round 2 surface targeting)
[codex] rg -n "followon_continuity|archived|ca..." (frontmatter + tombstone scan)
[codex] rg -n "P[0-9]|TDD|test|fence|active.md..." (execution plan granularity)
[codex] rg -n "Requirement:|Scenario:|archived..." (spec scenario coverage)
[codex] rg -n "Phase|P[0-9]|TDD|Red|Green|test..." (TDD step rigor)
[codex] rg -n "M[0-9]|P[0-9]|TDD|Red|Green|tes..." (micro_tasks step rigor)
[codex] git diff --stat origin/main...HEAD -- ... (branch diff scope)
[codex] Get-Content -Raw ... (specific file deep-read)
[codex] rg -n "start_commit|baseline_commit|me..." (baseline anchor probe)
```

参考:`b876734jn.output` 完整 codex stdout(thread `019e0199-df85-7df1-aa14-1a9ed6c7d1d3` / turn `019e0199-e415-7132-80d6-863bdc989468`)。

> **注**:bash 反引号 substitution 让 prompt 中一处 `_check_srs_registry_consistency` fence 名拼写损失,但主体 prompt 传达了重点;codex 仍 raise 了 D-TombstoneProtocol 等核心 round 2 surface,review 质量未受实质影响。
