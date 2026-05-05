---
change_id: restore-superpowers-worktree-consent-gate
stage: S3
evidence_type: plan_cross_check
contract_refs:
  - execution/execution_plan.md
  - execution/micro_tasks.md
  - tasks.md
  - design.md
  - proposal.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-apply-subagent
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
disputed_open: 0
writeback_commit: pending
created_at: 2026-05-05T23:25:00+08:00
resolved_at: null
worktree_consent_outcome: declined
worktree_mode: in_place
task_granularity: phase
task_independence_assertion: false
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
    - superpowers:requesting-code-review
    - superpowers:finishing-a-development-branch
    - superpowers:using-git-worktrees
  cascade_check_pass_at: 2026-05-05T23:24:00+08:00
---

# Plan Cross-check — restore-superpowers-worktree-consent-gate

## A. Decision Summary(Claude 立场,冻结于 codex plan review 之前)

> **协议自我保护**:本段在 `/codex:adversarial-review` plan review 调用之前完成,锁定 Claude 对 plan(`execution/execution_plan.md` + `micro_tasks.md`)+ Phase 2 D-DogfoodSelfHostMode path B 立场。codex 输出之后只填 `## B/C/D`,不回填 `## A`。

### A.1 Phase 2 路径决议(D-DogfoodSelfHostMode path B)

**Claude 立场**:本 change 实施期走 **path B self-host main repo cwd + ADR-013 新 schema dogfood**。理由 design.md G11 / ## Migration Plan 已述:wrapper bug 阻断 path A literal compliance 已实测;path B self-host 是 ADR-013 真正 dogfood;每 evidence 写 `worktree_consent_outcome: declined` + `worktree_mode: in_place`,不写 `runtime_enforcement_protocol_version`(legacy fence pass-through)。

**Anticipated codex challenge**:
- (a) "self-host evidence 不写 protocol_version 实质等价 advisory bypass" → 不接受;evidence 写 ADR-013 新 schema 字段 self-evidence 协议;protocol_version 不写沿 spec.md "legacy archived evidence pass-through" 同款 fence 兼容意图;P11 archive 时正常跑(无需 bypass)
- (b) "wrapper bug 应该先 fix 再 implement 本 change" → 不接受;wrapper bug 是 archived ADR-012 已 tracking 的 follow-on,不是本 change scope;且本 change 协议本身就让 wrapper 默认不调用,fix 它的紧迫性反而降低
- (c) "main repo dev branch sequential dispatch 仍可能污染" → 接受 R1 trade-off(已在 design.md ## Risks);mitigation:每 subagent commit 完成后下一个开始,顺序保证 attribution

### A.2 P0 命令模板更新策略

**Claude 立场**:`change-apply-subagent.md` + `change-apply-parallel.md` `## Preflight Worktree` section 重写为 OPT-IN narrative + MUST invoke `Skill(superpowers:using-git-worktrees)` + outcome / mode capture step;撤 mandatory `forgeue_preflight_wrapper.py` invocation。`change-apply-direct.md` 不动(沿 archived 第 5 项)。

**Anticipated codex challenge**:
- (a) "MUST invoke vs MAY invoke 区别只在文档,LLM 是否真跑 Step 0 仍无法 enforce" → 接受 limitation;沿 codex round 1 F3 writeback 已落 `worktree_consent_outcome` evidence 字段(P1 fence validate);命令模板 MUST 是 narrative 层,fence enforce 是 schema 层;两层组合关闭 Option B' → Option C 滑坡
- (b) "保留 wrapper invocation 段(opt-in)是否徒增 narrative 复杂度" → 接受;沿 OQ-2 wrapper deprecate 但 functional 立场

### A.3 P1 finish_gate 改造策略

**Claude 立场**:`_check_worktree_path` v1 + v2 改 mode-conditional advisory(沿 codex round 1 F2 writeback);加 `_check_worktree_consent_outcome` + `_check_worktree_mode_consistency` 2 新 fence(沿 F3 writeback);`_WORKTREE_REQUIRED_COMMANDS` frozenset 改空集合;legacy archived evidence(无 protocol_version 或无 worktree_mode 字段)pass-through。

**Anticipated codex challenge**:
- (a) "改 _WORKTREE_REQUIRED_COMMANDS 为空集合等价 retire field-presence-conditional" → 不接受;两个新 fence(consent_outcome + mode_consistency)关闭 F2 受质疑的双歧义漏洞;state machine 比 field-presence 强约束
- (b) "fence 测试矩阵新增 8 个 + 调整 N 个,test 复杂度上升" → 接受 cost;state machine 完整性必需

### A.4 P2 wrapper deprecate 策略

**Claude 立场**:`__deprecated_note__` 字符串 + module docstring [DEPRECATED in default flow] + argparse `--help` notice;不改 wrapper core code(避免 follow-on `enhance-workflow-automation-v2-fence-hardening` scope creep)。

**Anticipated codex challenge**:
- (a) "wrapper 既已 deprecated 应直接删 + tests 一并删" → 不接受;v2 e2e fixture 11 test + unit 18 fence test 仍跑;opt-in 路径 user 显式 invoke 仍 functional;沿 OQ-2 倾向

### A.5 P3 sister skill v2.3 update 策略

**Claude 立场**:`subagent-driven-discipline/SKILL.md` Pattern 2 STRICT cwd verify 改 "when worktree IS used (after user consent at Step 0)";加新 §3.5 "Worktree Consent Policy";Case 1 P3 worktree leak scope-down note;frontmatter `version: 2.2 → 2.3` + `worktree_consent_policy: default-decline-in-implementation` + `consent_outcome_enum`。

**Anticipated codex challenge**:
- (a) "Case 1 P3 实证 worktree leak 在 ADR-013 default decline 下不会触发,但 sister skill 仍记录该 case study 是否过期" → 不接受;留作 historical reference + bug-fix iteration use case 时(opt-in worktree)仍 relevant;scope-down 是 narrative update 不是删除

### A.6 P4 backbone skill update 策略

**Claude 立场**:`forgeue-integrated-change-workflow/SKILL.md` Superpowers 集成边界表 `using-git-worktrees` 行重写;Runtime Enforcement Protocol(ADR-011)+ Runtime Enforcement Protocol v2(ADR-012)段加 superseded note;加新 "ADR-013:Restore Superpowers Worktree Consent Gate" 段含 outcome state machine + parallel decline auto-fallback。

**Anticipated codex challenge**:
- (a) "backbone skill 既加 superseded note 又加 ADR-013 新段是否冗余" → 不接受;ADR-011/012 的 superseded note 是 cross-reference;ADR-013 新段是完整协议描述;两层互补

### A.7 P5 9 doc sync 策略

**Claude 立场**:沿 archived ADR-012 P5 同款 9 doc 同步模式;无新增 doc;每 doc 加 ADR-013 段或行 + ADR-011/012 supersede cross-reference。

**Anticipated codex challenge**:
- (a) "9 doc 同步是否包含 docs/design/HLD.md / LLD.md" → 不接受;HLD/LLD 是 architecture 层,本 change 是协议层 narrative + fence,不动 architecture;沿 D-CrossArchiveADRSupersede metadata-level supersede 范围

### A.8 P6-P10 verify / codex / doc-sync / finish gate 策略

**Claude 立场**:沿 archived ADR-012 P6-P10 同款编排:
- P6 Level 0/1 verify(L1 SKIP opt-in)
- P7 codex `/codex:review --base main` mixed-scope(default background)+ writeback;pre-commit P7 替代 stub 沿 reference 模式
- P8 SKIP `superpowers:requesting-code-review`(沿 archived ADR-012 同款)
- P9 Documentation Sync Gate
- P10 Finish Gate(全 fence;evidence 不含 protocol_version 沿 path B)

**Anticipated codex challenge**:
- (a) "P10 finish_gate 跑当前版本 fence + 含 ADR-013 新 fence(若 P1 已 ship)是否产生 evidence self-validation" → 不接受;P1 ship 后新 fence 跑本 change evidence 时,evidence 含 ADR-013 新 schema 字段(consent_outcome / mode)→ fence validate 通过(consent_outcome ↔ mode invariant 满足);self-validation 是好事不是坏事

### A.9 R1-R5 trade-offs(沿 design.md ## Risks)

| Risk | Claude 立场 |
|---|---|
| R1 implementer subagent isolation buffer | 接受;sister skill controller cross-verify + commit 前 main session 验证 |
| R2 archived advisory fence replay 兼容性 | 接受;advisory 是 mandatory 的 superset 行为 |
| R3 wrapper deprecated 用户体验 | 接受;wrapper `--help` + sister skill §3.5 mitigation |
| R4 v2 e2e fixture 11 test 影响 | 接受;预计 2-3 test 调整 |
| R5 ADR-013 metadata-level supersede | 接受;SRS cross-reference + 反向 link mitigation |

## B. Cross-check Matrix(待 codex plan review 后填)

> codex `/codex:adversarial-review` plan review 完成后,逐条 finding 对照填表;Resolution 取值同 design cross-check 协议(`aligned` / `accepted-codex` / `accepted-claude` / `disputed-pending` / `disputed-permanent-drift`)。

| codex finding | Claude 立场(`## A` 冻结) | Resolution | Note |
|---|---|---|---|
| _(pending codex round 1 plan review)_ | | | |

## C. Disputed Items Pending Resolution

> `disputed_open: pending`(待 ## B 填完后更新;> 0 阻断 S5)。

_(pending)_

## D. Verification Note(独立验证 file:line)

> 沿 ForgeUE memory `feedback_verify_external_reviews` — 不把 codex claim 当结论,逐条 file:line 独立验证。

_(pending — 待 codex finding 后逐条验证)_

## References

- `execution/execution_plan.md`(plan 主体)
- `execution/micro_tasks.md`(sub-task index)
- `design.md` G11 D-DogfoodSelfHostMode + ## Migration Plan Phase 2(path B 决议)
- `review/design_cross_check.md`(design cross-check;Pre-P0 codex round 1 已落 disputed_open: 0)
- archived `2026-05-05-enhance-workflow-automation-executable-enforcement/review/plan_cross_check.md`(模板源)
