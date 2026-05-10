## Context

ForgeUE 自 `fuse-openspec-superpowers-workflow` change(2026-04-27 ship)起接入 OpenSpec × Superpowers × codex CLI 三层融合工作流,中心化在 `tools/forgeue_*.py` 8 工具 + 9 个 `/forgeue:change-*` 命令模板 + 2 sister skill + 12-key audit frontmatter + cross-check A/B/C/D 模板 + 4 类 DRIFT taxonomy + Lean Apply Mode + skill cascade + subagent-driven-discipline 28-subtype + follow-on backlog registry 守门 fence。

过去 60 天的 audit 数据(本会话 3 个 audit subagent 报告引用进 proposal.md)证明:协议层在 produce 协议自我治理 > 业务价值。具体证据:

- `finish_gate` BLOCKER 跨 11 个 archived business change 触发率 = 0
- 5 个 ADR-level change ship→retire 平均 lifetime 0.5 天
- 76 finding 中 14 个是 PROTO-SELF;47/51 BUS-BUG 由 codex review hook 抓到
- ForgeUE-specific 协议层独立增量 = 2-3 DES-GAP / 13 changes,代价是 14 PROTO-SELF + 平均 2-3 倍 review round + 9 份 placeholder evidence

User(2026-05-10)在评估"全面转 Superpowers"vs"精准切割"两条路径后,反复权衡决定走"激进全面转 Superpowers"路径(B 路径),整 retire ForgeUE-specific 协议层,切到 OpenSpec(contract anchor)+ Superpowers(evidence 流)+ codex CLI(opt-in via convention)三层精简栈。

## Goals / Non-Goals

**Goals:**

- 整删 9 个 `/forgeue:change-*` 命令 + 2 sister skill + 8 个 `tools/forgeue_*.py` 工具 + 2 个协议文档 + `docs/ai_workflow/README.md` Documentation Sync Gate 段
- 整删协议机制:cross-check A/B/C/D / 12-key audit frontmatter / 4 类 DRIFT taxonomy / writeback 协议 / Lean Apply Mode / skill cascade check / subagent-driven-discipline 28-subtype 强制 / budget tracker fence
- 整删 backlog 守门 fence(只砍 fence,**目录保留**):follow-on continuity / SRS registry consistency / 4 类 cancel tag fence / tombstone consistency / archived.md append-only fence / 13th `followon_continuity` frontmatter 字段
- 精简 CLAUDE.md "OpenSpec 工作流" / "Follow-on Backlog Registry" / "ForgeUE Integrated AI Change Workflow" 三大段到 ≤ 30 行
- 加 CLAUDE.md 一行 strong convention,preserve audit ~30-40% latent smell catch leverage
- 13 active workflow-protocol follow-on 留在 `openspec/backlog/active.md` 自然演化
- 修改 2 个 capability spec(`examples-and-acceptance` 大段 retire / `probe-and-validation` 单 Requirement retire)

**Non-Goals:**

- 不动 `openspec/changes/archive/*` 24 changes evidence(沿"归档即冻结"D-ArchivedReplayCompat)
- 不动 `src/framework/*` ForgeUE 业务运行时(ComfyUI / mesh / audio / video / UE bridge / runtime / providers / review_engine)
- 不动 `docs/{requirements,design,testing,acceptance}/*` 五件套长期权威文档
- 不动 `openspec/specs/*` 其他 6 个 capability(runtime-core / artifact-contract / workflow-orchestrator / review-engine / provider-routing / ue-export-bridge)
- 不动 `openspec/backlog/{active,archived,README}.md` schema 与 5 个 tombstones audit trail(只砍守门 fence)
- 不重新设计工作流(直接走 OpenSpec `/opsx:propose` + Superpowers 全套 + codex CLI opt-in,没自家 wrapper)
- 不向后兼容(B 路径明确 sunk cost accept)
- 不转 follow-on 到 GitHub Issues(留在 active.md 自然演化)
- 不实施 Phase 化 fence guarded migration(走完整一刀切 retire,沿 `retire-parallel-and-worktree-fully` 同类 retire 模板)

## Decisions

### D1:Retire change 自身走 OpenSpec `/opsx:propose` + Superpowers,不走自家 9 命令

**问题**:自家命令是 retire 目标,讽刺自指 — 走自家命令验证 retire 自身有什么意义?

**决策**:走 OpenSpec `/opsx:propose` 起 change + Superpowers writing-plans / subagent-driven-development / executing-plans / TDD / requesting-code-review 实施 + codex CLI opt-in(`/codex:adversarial-review` design hook + `/codex:review --base main` final hook)。**本 change 自身就是新工作流的第一个 dogfood sample**。

**Alternatives 拒绝**:
- (a) 走自家 9 命令最后一次 dogfood(讽刺自指,产生 self-referential finding 类似 retire-parallel-and-worktree-fully)— 拒绝原因:9 命令是 retire 目标,deep self-reference 浪费 budget 且 audit 数据已证明协议层翻烧饼
- (b) 混合 P0-P2 走自家命令 + P3+ 切 Superpowers — 拒绝原因:中间态"工具被删了但 fence 还在跑"难以维护 Phase 边界

**沿前例**:`retire-parallel-and-worktree-fully`(2026-05-06)是同类 wide retire 模板;但本 change 比其更激进(retire 自家 9 命令本身,非仅 retire 部分协议)。

### D2:Archived 24 changes evidence 不动,沿 D-ArchivedReplayCompat

**问题**:archived 24 changes 含 12-key frontmatter / cross-check A/B/C/D / writeback 协议引用;若 retire 协议机制后 replay 这些 archived changes 会怎样?

**决策**:**完全不动** archived 路径 evidence。沿 `retire-parallel-and-worktree-fully` D-ArchivedReplayCompat 决策:archived evidence 含 unknown protocol value(`v2` / `v3` / `worktree_consent_outcome` / `ledger_forgery_resistance` 等)→ legacy pass-through。本 change 直接将 finish_gate 整删,所有 fence 不再存在 → archived 路径自动通过(没有 fence 跑了)。

**Alternatives 拒绝**:
- (a) Backfill archived 24 changes 的 frontmatter 为新简化 schema — 拒绝原因:违"归档即冻结"原则,而且 sunk cost
- (b) 留 finish_gate `--archived-replay` mode 兼容 archived — 拒绝原因:`finish_gate` 整删

### D3:`openspec/backlog/` 目录保留,只砍守门 fence

**问题**:`centralize-followon-backlog-registry`(2026-05-07 ship)立 backlog registry 协议 + active.md / archived.md / README.md schema + 6 个 守门 fence + 13th frontmatter 字段。User 拍板:整删 vs 简化保留 vs 全保留?

**决策**(user 2026-05-10 拍板):**目录保留**作信息容器。砍 fence(随 finish_gate 整删一并消失):
- `_check_followon_continuity`(P2.f orchestrator)
- `_check_srs_registry_consistency`(P2.g)
- 4 类 cancel tag fence(`_validate_cancel_tag_superseded` / `_validate_cancel_tag_not_applicable` / `_validate_cancel_tag_completed` / `_validate_cancel_refs`,P2.d.{1,2,3,4})
- `_validate_tombstone_consistency`(P2.b.4)
- `_check_archived_md_append_only`(P2.e)
- 13th `followon_continuity` frontmatter 字段(随 12-key 整删)

active.md / archived.md / README.md schema 不动;5 个 tombstones audit trail 保留;双源 cross-link 至 SRS §7.3 active TBD 保留。13 个 active workflow-protocol follow-on 留在 active.md 自然演化(下个 change 路过时按需 sweep,大半未来 `cancelled-not-applicable: scope-changed`)。

**Alternatives 拒绝**:
- (a) 整 retire 用 GitHub Issues — user 拍板 reject;`openspec/backlog/` 目录保留
- (b) 整 retire 用极简 `BACKLOG.md` — user 拍板 reject;同上
- (c) 全保留含 fence — 与 retire 主旨矛盾

### D4:Codex hook 改 opt-in via CLAUDE.md convention

**问题**:Audit 数据显示 cluster-2 类 ~30-40% 业务 catch 来自 codex `/codex:adversarial-review` design hook 的 cross-archive scope。命令模板 mandatory 改 opt-in 后会丢这部分价值。

**决策**:加 CLAUDE.md 一行 **strong convention**(不强制但 documented):

> **Convention**:重要 design 阶段先跑 `/codex:adversarial-review`(catch latent design smell);final review 跑 `/codex:review --base main`(catch cross-archive mixed-scope)。

**Risk**:用户高风险 design 忘调 → ~30-40% catch 漏掉。失败模式是 silent skip,无 audit trail(round 1 codex P2 finding accept)。

**Mitigation**(round 1 codex P2 writeback):
1. CLAUDE.md convention + 沿用户决策风格"先给论证再请求授权"
2. **每个 change retrospective.md MUST 含 codex review run/skip record 字段**:`codex_design_review: <run | explicitly skipped with reason>` + `codex_final_review: <run | explicitly skipped with reason>`(沿 design.md `## Reasoning Notes` 段 anchor convention,不强制但 documented;若 skip 必给 ≥ 30 字 reason)
3. 不引入 git pre-commit hook(过度工程,违 retire 主旨)

**Alternatives 拒绝**:
- (a) 命令模板 mandatory(走路径 A 精准切割)— user 拍板选 B 路径,reject
- (b) 不写 convention 完全 user 自觉 — Risk 太大,reject
- (c) Git pre-commit hook 触发 codex — 过度工程,reject

### D5:13 active workflow-protocol follow-on 留在 active.md 自然演化

**问题**:13 active workflow-protocol entries(`enhance-workflow-automation-handoff-persistence` / `add-forgeue-brainstorm-stage` / `enhance-workflow-automation-finishing-branch` / `enhance-workflow-automation-final-review-fence-strictness` / `analyze-superpowers-skills-openspec-integration-gaps` / `fix-cross-check-format-test-enum-extension` / `fix-finish-gate-completed-cancel-uses-baseline-entries` / `fix-finish-gate-followon-regex-allow-tbd-uppercase` / `fix-finish-gate-tombstone-empty-cancel-tag-bypass` / `fix-finish-gate-archived-md-protected-field-deletion` / `fix-enum-cross-ref-check-windows-gbk-print` / `audit-archived-subagent-budget-true-cost-vs-discipline-tier` / `fix-pretest-pre-existing-fence-baseline-drift`)retire 后是否一并 cancel?

**决策**:**不动** active.md。13 entries 留在 active.md 自然演化:
- 大半(`fix-finish-gate-*` 系列 4 + `fix-enum-cross-ref-check-windows-gbk-print` + `audit-archived-subagent-budget-*`)未来按需 `cancelled-not-applicable: scope-changed`(因为对应工具 retire);但**本 change 不强制立即 cancel**,留下个 change 路过时 sweep
- 其他(`add-forgeue-brainstorm-stage` / `enhance-workflow-automation-finishing-branch` / `analyze-superpowers-skills-openspec-integration-gaps`)在新工作流下仍可能有意义,自然 lifecycle

**Alternatives 拒绝**:
- (a) 立即批量 cancel 全部 — 违反 cancel 协议(每个 cancel 需要 commit-touches 或 escape hatch),工作量大;且违 D3"backlog 自然演化"
- (b) 全部 retire 转 GitHub Issues — D3 已 reject
- (c) 立即 cancel 协议自身 follow-on(`fix-finish-gate-*` 系列 4 + 1 + 1)+ 留 strategic 类 — 部分合理但工作量与净收益不匹配,留下个 change

### D6:CLAUDE.md 三大段精简到 ≤ 30 行 + 加 codex convention 一行

**问题**:CLAUDE.md 当前 ~1100 行,其中 ForgeUE 协议层段(OpenSpec 工作流 / Follow-on Backlog Registry / ForgeUE Integrated AI Change Workflow)~200 行,占 ~20%。retire 后留多少?

**决策**:精简到 ≤ 30 行,只留:
1. OpenSpec 何时用(非平凡 vs 小 bugfix)
2. Superpowers 何时用 + 流程参考(brainstorming → writing-plans → subagent-driven-development → requesting-code-review)
3. codex CLI 何时用(strong convention)
4. follow-on tracking pointer 至 `openspec/backlog/`(无 fence,信息容器)

完全删除:S0-S9 状态机表 / 9 命令矩阵 / 8 工具列表 / 12-key frontmatter audit / 4 类 DRIFT taxonomy / dispatch matrix / autonomy boundary 6 fence / Documentation Sync Gate 段。

### D7:`examples-and-acceptance` spec 用 REMOVED 而非 MODIFIED

**问题**:协议层在 `examples-and-acceptance/spec.md` 占 ~600+ LOC(大量 Requirement 段:12-key frontmatter / cross-check / 9 命令系列 / fence / Worktree / parallel dispatch / runtime enforcement protocol / task granularity / dispatch wrapper / dispatch ledger / model tier 等)。MODIFIED 还是 REMOVED?

**决策**:用 **REMOVED** 整段 retire ForgeUE 协议层 Requirements,**保留** Requirement 与 ForgeUE 业务 acceptance 相关(L2 ComfyUI smoke / P4 UE commandlet / examples bundle 端到端验收)。

**理由**:
- 协议层 Requirements 是"如何用 ForgeUE 协议跑 change"的契约,retire 后契约消失,完整 REMOVED 比 MODIFIED 清晰
- MODIFIED 保留旧契约 stub 会被 archive 时 OpenSpec validate 视为 incomplete delta
- 沿 `retire-parallel-and-worktree-fully` REMOVED 模板(同 spec 内 retire ADR-011/012/013 段)

**操作**:在 `specs/examples-and-acceptance/spec.md` delta 文件用 `## REMOVED Requirements`,每个 REMOVED 段含 `**Reason**: ForgeUE 协议层全 retire(见 proposal.md / design.md)` + `**Migration**: 改用 OpenSpec /opsx:propose + Superpowers <skill> + codex /codex:adversarial-review opt-in convention(见 CLAUDE.md)`。

### D8:`probe-and-validation` spec 用 REMOVED 单 Requirement

**问题**:`probe-and-validation/spec.md` 含 1 个 Requirement(`Requirement: forgeue_verify.py Level 2 ComfyUI steps SHALL exercise the agent CLI subprocess path`)是 ForgeUE 自家工具。

**决策**:REMOVED 该 Requirement。Migration 段:Level 2 ComfyUI 验证由用户手工跑 `python -m pytest tests/integration/test_p3_capability_image.py` + `python -m framework.run --task examples/comfy_local_smoke*.json --live-llm` 替代。文档化到 `docs/testing/test_spec.md` Level 2 验证章节(本 change 不动 docs 五件套,Migration 是后续 follow-on,但记录在 design.md 里)。

### D9:Phase 划分(P0-P8)

完整 Phase 见 `tasks.md`。简述:
- P0:baseline + scope freeze(audit data 引用 + sunk cost 列表)
- P1:retire 9 命令 + 2 sister skill
- P2:retire 8 工具 + 配套测试
- P3:retire 3 协议文档 + `docs/ai_workflow/README.md` 段删
- P4:`openspec/backlog/` 目录保留,只砍 fence(随 P2 finish_gate 一并消失)
- P5:CLAUDE.md 三大段精简到 ≤ 30 行 + 加 codex convention 一行
- P6:13 active workflow-protocol follow-on 不动(自然演化)
- P7:全套 pytest baseline(catch-up 2 pre-existing baseline fail)
- P8:retrospective + archive(走 `/opsx:archive`)

### D11:Subagent-driven-discipline SKILL 保留(round 1 codex writeback P1-1 partial-dispute)

**问题**:Codex round 1 adversarial review P1-1 finding 主张:`.claude/skills/subagent-driven-discipline/SKILL.md` 是 ForgeUE 协议核心组件,本 retire 应整删。

**Verify(沿 ForgeUE memory `feedback_verify_external_reviews`)**:Claude 独立 read SKILL.md 全文,发现:

- L3 description: "Subagent task type taxonomy + cheap-model reliability playbook" — pure generic
- L5 compatibility: "sister to `superpowers:subagent-driven-development`(generic 3-stage process)"
- L15 opening: "**Universal** controller-side discipline for `superpowers:subagent-driven-development` workflows"
- L17-19 立场: "**重场景轻业务**...**业务无关**:具体项目用法属于 case studies 增量层,不染入 scenario taxonomy"
- L22 启用条件: "**任何项目**使用 `superpowers:subagent-driven-development` 派 subagent 时"

**结论**:Codex P1-1 finding 部分误读 — SKILL 内容实际是 **generic universal subagent discipline**,可独立给任何 superpowers 用户使用,不是 ForgeUE-specific 协议组件。`author: forgeue` 只是 origin label 不是 binding。

**决策**:**Partial-dispute codex P1-1**(Resolution = `accepted-claude` 沿 design.md §3 Cross-check Protocol Resolution enum):

- **保留** `.claude/skills/subagent-driven-discipline/SKILL.md`(generic advice 给所有 superpowers 用户)
- **解除** ForgeUE-specific hard-wire(随 9 命令 / 8 工具 / 12-key frontmatter retire 自然消失):
  - `change-apply-subagent` 命令 Preflight Skill Cascade `--invoked subagent-driven-discipline` → 整命令删 → 引用消失
  - `forgeue_finish_gate.py::_check_skill_cascade` fence verify subagent-driven-discipline invoked → 整 fence 删 → 守门消失
  - `skill_cascade_audit.invoked_skills` frontmatter 字段强制含 subagent-driven-discipline → 12-key frontmatter 整删 → 字段消失
- SKILL frontmatter `author: forgeue` label + `metadata.worktree_consent_policy` + §3.4 Trigger Type Matrix 等不动(case studies 是增量层,沿 L19 "业务无关")
- `tasks.md` P1.13 修订为"保留 SKILL,只 audit retire scope 内 ForgeUE-specific hard-wire 是否随 9 命令 / 8 工具自然消失"

**Sunk-cost note**:`enforce-subagent-discipline-cascade`(2026-05-08 ship)的 ForgeUE-specific cascade enforcement 协议(命令模板 mandatory invoke + skill_cascade_audit fence)retire,但**底层 28-subtype × model tier × cheap-model reliability playbook 内容由 SKILL 自身承载,不需要 cascade 协议背书也可用**。该 change 的核心 deliverable(generic discipline)实际上以更轻量形式 preserved。

### D10:Sunk cost 显式 accept

**问题**:`centralize-followon-backlog-registry`(2026-05-07 ship,3 天前;15 D-decision + 3 round codex review + 45 commits + ~3028 LOC code + ~969 LOC `forgeue_finish_gate.py` 增量 fence)+ `enforce-subagent-discipline-cascade`(2026-05-08 ship,2 天前;cascade discipline 协议化 + model tier sub-step + Phase A/B subagent dispatch evidence)如何处理?

**决策**:**显式 accept sunk cost**。这两个 change 的核心 deliverable(backlog 守门 fence + cascade discipline 协议)在 B 路径下整 retire。理由:
- audit 数据明确显示协议层在守自己,这两个 change 加深了协议自治 churn
- 不 retire 等于半砍,违 B 路径主旨
- 两个 change 自身的 D-decision / D-ArchivedReplayCompat archived evidence 不动(沿 D2)

## Risks / Trade-offs

- **Risk 1**: `codex` hook opt-in → 用户高风险 design 忘调 — Mitigation:CLAUDE.md strong convention(D4)
- **Risk 2**: 没有 Documentation Sync Gate 守门 docs drift — Mitigation:archive 时人工 sweep;docs 五件套作长期权威,自然 git review 守
- **Risk 3**: ADR-007 vendor API 双扣边界 / scope guard / 越界检测全砍 — Mitigation:Superpowers `requesting-code-review` 在 final 阶段 catch 越界;codex `/codex:review --base main` 在 archive 前 catch
- **Risk 4**: 24 archived changes evidence 含 12-key frontmatter 引用 retire 后不存在的字段 — Mitigation:沿 D2 D-ArchivedReplayCompat,archived 路径不动;finish_gate 整删后没有 fence 跑 → 自动 pass
- **Risk 5**: `centralize-followon-backlog-registry` + `enforce-subagent-discipline-cascade` sunk cost — D10 显式 accept
- **Risk 6**: 13 active workflow-protocol follow-on 中部分(`add-forgeue-brainstorm-stage` / `enhance-workflow-automation-finishing-branch` / `analyze-superpowers-skills-openspec-integration-gaps`)在新工作流下仍可能 trigger,但自然 lifecycle(D5)— Mitigation:active.md 留作信息容器
- **Risk 7**: 本 change 自身走 Superpowers 工作流(D1),但 user 不熟悉 raw Superpowers + codex CLI opt-in pattern — Mitigation:本 change 自身就是 dogfood,完成后 user 熟悉新流程
- **Risk 8**: P7 catch-up 2 pre-existing baseline fail(`fix-pretest-pre-existing-fence-baseline-drift` follow-on)— Mitigation:retire 期顺手 cleanup,baseline 0 fail 是新工作流的最小起点
- **Trade-off 1**: 工作流 simplification 的 cost 是 ~30-40% latent design smell catch leverage 转 user 自律 — accept(B 路径明确决策)
- **Trade-off 2**: LOC delete ~9500 大于 retire-parallel-and-worktree-fully 5066 — accept(retire 范围更广,一次到底比分批清晰)

## Migration Plan

**前置**(无):本 change 不依赖任何前置 change(自身是 dogfood sample)。

**实施顺序**(沿 P0-P8,见 tasks.md):
1. P0 freeze baseline:`openspec validate retire-forgeue-protocol-layer-fully --strict`
2. P1 retire 命令 + skill:`git rm` 9 命令 + 2 skill
3. P2 retire 工具:`git rm` 8 `tools/forgeue_*.py` + 配套 `tests/unit/test_forgeue_*.py`
4. P3 retire 文档:`git rm` `docs/ai_workflow/forgeue_integrated_ai_workflow.md` + `forgeue_quickstart.md`;`docs/ai_workflow/README.md` 段删
5. P4 backlog fence 已随 P2 整删 finish_gate 消失,目录保留(无独立 P4 commit,验证 P2 commit 含 fence 全删)
6. P5 CLAUDE.md 精简:三大段精简到 ≤ 30 行 + 加 codex convention 一行
7. P6 13 active follow-on 不动
8. P7 全套 pytest baseline 0 fail(可能含 P7.1 catch-up `fix-pretest-pre-existing-fence-baseline-drift` 2 pre-existing fail)
9. P8 retrospective + archive `/opsx:archive`

**Rollback strategy**:本 change 是 wide retire,rollback 通过 `git revert <merge-commit>` 一次性恢复。但 archived changes evidence 不动 + 业务代码不动 → rollback 风险低(只是 8 工具 / 9 命令 / 2 skill / 3 文档 + CLAUDE.md 段恢复)。

**新工作流上手**:retire 完成后,新流程是:
1. 起 change:`/opsx:propose <name>`(OpenSpec)
2. 实施:Superpowers `writing-plans` → `subagent-driven-development` → `executing-plans`(选其一)
3. 验证:Superpowers `requesting-code-review` + `verification-before-completion`
4. Optional:codex `/codex:adversarial-review` design hook + `/codex:review --base main` final hook(strong convention,不强制)
5. Archive:`/opsx:archive`

## Open Questions

(无 — user 2026-05-10 已拍板全部 D-decision;round 1 codex adversarial review 后 5 finding accept + 1 partial-dispute,全部 inline writeback 完成,disputed_open=0。)

## Round 1 Codex Adversarial Review Writeback(2026-05-10)

**Codex output**: `notes/codex_adversarial_review_review_round1.md`(verbatim 完整保留)
**Verdict**: needs-attention(6 finding:5 P1 high + 1 P2 medium)
**Independent verify**: Claude 独立对照代码 file:line verify 全部 6 finding,verify 结果见上一轮 conversation table(沿 ForgeUE memory `feedback_verify_external_reviews`)

**Resolution(沿 design.md §3 Cross-check Protocol Resolution enum)**:

| Finding | Codex priority | Verify | Resolution | 落地 |
|---|---|---|---|---|
| **P1-1** subagent-driven-discipline 保留 vs 删除 | high | confirmed real (SKILL 真实存在),但 codex 误读 SKILL 性质 | **accepted-claude**(partial-dispute) | 加 D11(SKILL keep policy);tasks.md P1.13 修订 |
| **P1-2** AGENTS.md / README.md 未在 retire scope | high | confirmed real(AGENTS.md L212-274 + README.md L360-391 多处引用) | **accepted-codex** | proposal Impact 加;tasks.md P5 加 |
| **P1-3** 测试清单漏 7+5 个 | high | confirmed real(`tests/unit/test_forgeue_*.py` 实际 17 个;`tests/fixtures/forgeue_workflow/` 5 个 fixture) | **accepted-codex** | tasks.md P2 改 grep-driven cleanup |
| **P1-4** capability-boundary requirement 孤立 | high | confirmed real(主 spec L2107 依赖被 REMOVED 的 base registry contract) | **accepted-codex** | specs/examples-and-acceptance/spec.md `Centralized follow-on backlog registry` REMOVED→MODIFIED 保留最小 schema |
| **P1-5** Level 2 subprocess contract 过早删除 | high | confirmed real(原 requirement 守 3 contract:`comfy/local*` 虚拟模型 + 禁 `--comfy-url` + 禁 LiteLLM wildcard fallback) | **accepted-codex** | specs/probe-and-validation/spec.md `forgeue_verify.py Level 2` REMOVED→MODIFIED 保留工具无关 contract;tasks.md `docs/testing/test_spec.md` 更新从 P9 optional 升 P3.5 必做 |
| **P2** codex hook silent skip 风险 | medium | confirmed real(D4 mitigation 只有 CLAUDE.md convention) | **accepted-codex** | D4 mitigation 加 retrospective record convention;tasks.md P8.1 retrospective 加 codex run/skip record |

**disputed_open**: 0(全部 6 finding 已 inline writeback,P1-1 partial-dispute 走 `accepted-claude` 不计 disputed)
