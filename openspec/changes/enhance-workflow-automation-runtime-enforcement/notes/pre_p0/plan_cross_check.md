---
change_id: enhance-workflow-automation-runtime-enforcement
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
  - notes/pre_p0/codex_review_round1.md
aligned_with_contract: true
drift_decision: written-back-to-design+proposal+tasks (F4+F5 inline) + deferred-to-follow-on (F1+F2+F3)
writeback_commit: pending
drift_reason: codex round 1 raised 5 findings (3 high + 2 medium); F4 + F5 inline writeback (skill root multi-source via D-SkillRootMultiSource + protocol version migration via D-ProtocolVersionMigration);F1 + F2 + F3 deferred 到 follow-on `enhance-workflow-automation-executable-enforcement`(W1 executable preflight wrapper / W2 actual diff overlap detection / W3 dispatch ledger 命令层 wrapper);本 change scope 调整为 markdown advisory protocol + skill cascade check + protocol version migration(诚实标注 advisory not deterministic)
reasoning_notes_anchor: notes/pre_p0/codex_review_round1.md
detected_env: claude-code
triggered_by: forced (Pre-P0 self-host bootstrap)
codex_plugin_available: true
triggered_by_command: change-apply-subagent
disputed_open: 0
codex_review_ref: notes/pre_p0/codex_review_round1.md
created_at: 2026-05-05T05:30:00+08:00
resolved_at: 2026-05-05T05:50:00+08:00
---

# Plan Cross-Check — enhance-workflow-automation-runtime-enforcement Pre-P0

## Status: disputed_open: 0(2 inline writeback + 3 deferred-tracking)

本 change self-host bootstrap 模式 — Pre-P0 cross-check 是 plan-level(沿 fuse-openspec-superpowers + adopt-subagent-driven-development + enhance-workflow-automation 一次性附录模式),覆盖 design + plan + spec + tasks 四 scope。

## A. Claude's Decision Summary (frozen before codex round 1)

**6 个 D-decision frozen**(propose 时):
- D-ParallelDispatch / D-WorktreeEnforce / D-SkillCascadeCheck / D-RoundFixContinuity / D-TaskGranularityDeclaration / D-PreflightProtocol

**Spec delta frozen**:`examples-and-acceptance` ADD 5 Requirement(对应 5 D-decision;D-PreflightProtocol 内嵌于其他 Requirement)

**Tasks 阶段大纲 frozen**:Pre-P0 + P0 (skill_cascade_check 工具)+ P1 (finish_gate 4 fence)+ P2 (forgeue 命令模板 + parallel)+ P3 (codex 命令模板)+ P4 (11 docs sync)+ P5-P10

## A'. Post-codex-round-1 Decision Summary 调整(2026-05-05 user feedback path b)

User 选 **(b) 路径**(F4+F5 inline,F1+F2+F3 deferred 到 follow-on),scope 调整:

- **D-ParallelDispatch**:**降级**为"加 `/forgeue:change-apply-parallel` 命令暴露并行路径,task independence assertion 是 advisory 不 enforce"
- **D-WorktreeEnforce**:**降级**为"命令模板 advisory `## Preflight Worktree` declaration"(标注 markdown advisory not deterministic)
- **D-SkillCascadeCheck**:**保留 + 加强**(F4 inline writeback 后加 D-SkillRootMultiSource — 多 root 探测 + `--skill-root` override)
- **D-RoundFixContinuity**:**降级**为"evidence frontmatter `subagent_continuity` 字段 advisory + finish_gate audit"(不阻断,只记录)
- **D-TaskGranularityDeclaration**:**保留**(advisory + finish_gate audit)
- **D-PreflightProtocol**:**保留**(advisory section pattern)
- **加 D-ProtocolVersionMigration**(F5 inline writeback):evidence frontmatter `runtime_enforcement_protocol_version: v1` + finish_gate fence 只对 v1+ evidence 生效 + archived fixture 回归
- **加 D-SkillRootMultiSource**(F4 inline writeback):skill root 多 root 探测 + `--skill-root` override

总 D-decision:**6 → 8**(原 6 + F4/F5 加 2)

## B. Cross-check Matrix(F1-F5 codex round 1 findings)

| ID | Severity | Codex 推荐 | Claude 独立 verify(file:line)| Verdict | Resolution path |
|---|---|---|---|---|---|
| F1 | high | executable preflight wrapper + machine-generated receipt | design.md:70-88 D-WorktreeEnforce 是 markdown step + finish_gate audit;真漏洞 | **accepted-codex,deferred** | `enhance-workflow-automation-executable-enforcement` follow-on W1 |
| F2 | high | parallel base SHA + actual changed-files diff + 阻断 undeclared / overlap | spec.md:9-16 `task_files_disjoint` 是 declaration 不是 actual diff;真漏洞 | **accepted-codex,deferred** | 同 follow-on W2 |
| F3 | high | dispatch ledger 命令层生成 + 不可手写 + finish_gate cross-check | spec.md:89-98 `subagent_continuity` 字段 LLM 写可伪造;真漏洞 | **accepted-codex,deferred** | 同 follow-on W3 |
| F4 | medium | skill root 多 root 探测 + `--skill-root` override + 测试矩阵 | tasks.md P0.2 硬编码 plugin cache 路径;真漏洞 | **accepted-codex,inline writeback** | 加 D-SkillRootMultiSource(design.md);tasks.md P0.2 改 |
| F5 | medium | protocol version field + archived 回归测试 | tools/_common.py:411-419 archived evidence 没新字段会 false-block;真漏洞 | **accepted-codex,inline writeback** | 加 D-ProtocolVersionMigration(design.md);spec.md scenario 加 protocol version field;archived fixture test |

## C. Disputed Items Pending Resolution

`disputed_open: 0`
- 2 inline writeback(F4 / F5)= 已 apply 到 design.md / proposal.md / spec.md / tasks.md(commit pending)
- 3 deferred-tracking(F1 / F2 / F3)= 留 follow-on `enhance-workflow-automation-executable-enforcement`,不 dispute(decision is "deferred" not "rejected")

## D. Verification Note

### D.1 独立 verify(5/5 TRUE)

| Finding | Claude 独立 grep / read | TRUE/FALSE |
|---|---|---|
| F1 (markdown advisory) | design.md D-WorktreeEnforce 段实装是 markdown step + finish_gate audit;controller 跳过 markdown step 时 fence 在 archive 时才扫 — Codex 揭示对 | TRUE |
| F2 (declaration vs actual diff) | spec.md `task_files_disjoint` frontmatter 字段定义是 declaration not actual diff | TRUE |
| F3 (forgeable agent ID) | spec.md `subagent_continuity` 字段 LLM 自报 + 无 dispatch ledger binding | TRUE |
| F4 (硬编码 plugin path) | tasks.md P0.2 line 17-19 硬编码 plugin cache 路径,不覆盖其他 root | TRUE |
| F5 (没 migration scope) | tools/_common.py:411-419 `change_path` archived fallback;新 fence 实装计划缺 protocol version | TRUE |

### D.2 修复完整性(2/5 inline + 3/5 deferred = 5/5 全 covered)

- [x] F4 → 加 D-SkillRootMultiSource decision(design.md)+ tasks.md P0.2 改 + 测试矩阵 P0.3
- [x] F5 → 加 D-ProtocolVersionMigration decision(design.md)+ archived fixture test
- [x] F1 → P11.3 follow-on tracking(`enhance-workflow-automation-executable-enforcement` W1)
- [x] F2 → 同 follow-on W2
- [x] F3 → 同 follow-on W3

### D.3 进 §2 前置(5/5 ✅)

- ✅ codex round 1 verdict needs-attention(可接受;writeback + deferred 后 contract 与 codex 推荐对齐 — F1/F2/F3 deferred 是显式 scope 调整,不是漏洞遗忘)
- ✅ 5/5 finding accepted-codex(2 inline + 3 deferred-with-tracking)
- ✅ writeback content + follow-on tracking 已 apply 到 4 artifact + tasks.md P11
- ✅ openspec validate enhance-workflow-automation-runtime-enforcement --strict 全绿
- ✅ 本 change scope 调整 honest disclosure(advisory not deterministic 显式标注)— design.md R6 Risk + proposal.md Out of scope

## Reference

- 详细 codex finding:`notes/pre_p0/codex_review_round1.md`(verbatim codex output + Claude 独立 verify 表 + writeback plan)
- Follow-on change:`enhance-workflow-automation-executable-enforcement`(尚未启动;待本 change ship 后实测决策)
- 协议依据:design.md `D-SelfHost` 借用 from `adopt-subagent-driven-development`(本 change Pre-P0 一次性附录沿同模式)
