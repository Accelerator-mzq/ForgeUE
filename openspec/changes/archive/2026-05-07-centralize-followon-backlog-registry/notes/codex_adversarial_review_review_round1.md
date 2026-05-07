---
change_id: centralize-followon-backlog-registry
stage: S2
evidence_type: codex_adversarial_review
review_round: 1
contract_refs:
  - design.md
  - proposal.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: false
drift_decision: written-back-to-design
writeback_commit: 125eae1d1c3682cd7a5e18e7fb3706c34e482e9a
drift_reason: Round 1 4 finding(F1 active.md hard source-of-truth + F2 cancel ref strict + F3 SRS↔registry fence enforce + F4 followon_continuity 4-list schema)全 accepted-codex inline writeback;design.md / proposal.md / specs/.../spec.md / tasks.md 同 batch update。详见 review/design_cross_check.md ## B/C/D + commit 125eae1。
reasoning_notes_anchor: review/design_cross_check.md#b-codex-findings--resolution
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
codex_job_id: bddjc7ohy
created_at: 2026-05-07T13:50:00Z
runtime_enforcement_protocol_version: v1
---

# Codex Adversarial Review — round 1(verbatim output)

> 沿 ForgeUE codex output exposure protocol(verbatim-first):本文件原样保留 codex stdout `# Codex Adversarial Review` 段;Claude 独立 file:line 验证 + Resolution disposition 落 `review/design_cross_check.md` `## B/C/D` 段。

---

# Codex Adversarial Review

Target: working tree diff
Verdict: needs-attention

不建议进入实现。当前设计仍允许 follow-on 从 registry 或 SRS 双源中静默丢失，并且 cancel 协议能被手写字符串绕过。

Findings:
- [high] [P1][in-scope] Fence 仍以链式 tasks.md 为真源，registry 丢项不会被阻断 (openspec/changes/centralize-followon-backlog-registry/specs/examples-and-acceptance/spec.md:22-24)
  设计目标是建立 centralized registry，但硬 gate 只扫描"latest archived change"的 tasks.md unchecked follow-on。推论：只要某个 active registry entry 不在最近一次 archive 的 unchecked P-section 中，或 active.md 被手工删除但未写 archived.md tombstone，_check_followon_continuity 不会发现；change-status 的 registry diff 只是输出格式，不是 blocker。这会保留原始链断风险，只是换了一个可见文档位置。
  Recommendation: 把 openspec/backlog/active.md 纳入 hard source-of-truth 校验：archive 时校验 active.md 上一版本与当前版本的增删改，删除/取消必须有 archived.md append-only tombstone；current tasks.md 声明必须覆盖 active registry 中仍 active 的相关 entry，而不是只覆盖 latest archived tasks.md。
- [high] [P1][in-scope] Cancel 协议只校验语法，足以绕过 backlog continuity (openspec/changes/centralize-followon-backlog-registry/design.md:76-83)
  D-FenceStrictness 允许 cancelled-superseded by <new-change-id>、cancelled-not-applicable: <reason>、cancelled-completed: <commit-ref>，但设计没有定义 new-change-id 必须存在、commit 必须触达相关代码/契约、reason 必须来自受控枚举或附证据。spec 的 superseded 场景标题写"valid"，正文只展示 tag 后直接接受。对一个防 controller hand-edit drift 的 fence 来说，这等价于允许把任意 follow-on 标成 scope-changed/out-of-scope 后移出 active registry。
  Recommendation: 收紧 cancel contract：superseded change id 必须解析到 active/archived change；completed commit 必须存在且触达 source/contract_refs 或 evidence 指向的相关文件；not-applicable reason 使用小枚举并要求 evidence/ref；同一 archive cycle 必须完成 active.md→archived.md 原子迁移，不能留到 next archive。
- [medium] [P2][in-scope] SRS 双源同步被写成约定，spec 没有可执行守门 (openspec/changes/centralize-followon-backlog-registry/design.md:148-156)
  D-CrossLinkSync 声称 SRS §7.3 新增 TBD 时由 _check_followon_continuity 扫 SRS diff 守门，并要求 TBD pointer status 变化同步回 SRS。但 spec 的 fence requirement 只扫描 latest archived tasks.md，centralized registry requirement 也只要求一次性 24 项和 header cross-link，没有 SRS 新增、完成、移除或状态变化的场景。结果是 TBD 变成 ✅ 后 registry pointer 可以继续残留，或 SRS 新增 TBD 后 registry 无 pointer，且 archive 不阻断。
  Recommendation: 在 spec 中新增 SRS↔registry consistency requirement 和场景：requirements-tbd-pointer 集合必须等于 SRS §7.3 active TBD 集合；SRS 状态变化必须同步 registry 或产生 archived tombstone；_check_followon_continuity/registry test 明确校验该 diff。
- [medium] [P2][in-scope] followon_continuity frontmatter schema 在 proposal 与 design/spec 间冲突 (openspec/changes/centralize-followon-backlog-registry/proposal.md:9-14)
  proposal 定义 followon_continuity 为 inherited_count/cancelled_count/cancellation_refs；design 和 spec 定义为 inherited、cancelled_superseded、cancelled_not_applicable、cancelled_completed 四个 list。该字段会被 finish_gate、change_state、change-status 同时消费；schema 未统一时，实施者可按不同文档写出互不兼容的 parser/template，导致 status 统计错或 archive evidence 被误判。
  Recommendation: 选定一个 canonical schema，建议采用 design/spec 的四 list 结构；同步 proposal、tasks、命令模板描述和 tests，并加一条 schema round-trip 测试覆盖 finish_gate evidence 与 change_state 输出。

Next steps:
- 先回写 design/spec/proposal，关闭上述 contract gap 后再进入 implementation plan。
- 补充 fence 测试：registry 删除无 tombstone、fake superseded id、not-applicable enum 违规、SRS TBD 状态变更未同步。

---

## Codex 工具操作日志(stdout 工具调用部分,reproducibility 留痕)

```
[codex] git status --short
[codex] rg -n "^### D-|^### Requirement:|categor..." (3 invocations spec/design/proposal)
[codex] rg -n "留 follow-on|follow-on|followon|..." (LLD/CLAUDE.md 内联注释扫描)
[codex] (4× Get-Content 命令 declined — 沙箱限制 LiteralPath 大文件分块读;codex 改用 rg -C 3 上下文搜索)
[codex] rg -n -C 3 "latest archived|cancelled-..." (fence 边界搜索)
[codex] rg -n -C 3 "archive 阶段|cancelled-superseded..." (cancel 协议搜索)
[codex] rg -n -C 3 "D-CrossLinkSync|SRS §7.3 新..." (cross-link 单向 vs 双向搜索)
[codex] rg -n -C 3 "followon_continuity|inheri..." (frontmatter schema 一致性搜索)
[codex] rg -n "follow-on tracking|留 follow-on|..." (P11/P12 section 命名兼容性搜索)
```

参考:`bddjc7ohy.output` 完整 codex stdout(包含 thread / turn id 用于审计追溯)。
