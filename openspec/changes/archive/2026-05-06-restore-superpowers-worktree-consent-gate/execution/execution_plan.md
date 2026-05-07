---
change_id: restore-superpowers-worktree-consent-gate
stage: S2
evidence_type: execution_plan
contract_refs:
  - tasks.md#Pre-P0
  - tasks.md#P0
  - tasks.md#P1
  - tasks.md#P2
  - tasks.md#P3
  - tasks.md#P4
  - tasks.md#P5
  - tasks.md#P6
  - tasks.md#P7
  - tasks.md#P8
  - tasks.md#P9
  - tasks.md#P10
  - tasks.md#P11
  - tasks.md#P12
  - design.md#decisions
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:brainstorming
    - superpowers:writing-plans
  cascade_check_pass_at: 2026-05-05T22:24:00+08:00
created_at: 2026-05-05T22:30:00+08:00
---

# Execution Plan — restore-superpowers-worktree-consent-gate

> **For agentic workers**:本 plan 沿 ForgeUE Integrated AI Change Workflow S3→S4-S5 阶段执行。
> 推荐路径:`/forgeue:change-apply-subagent`(默认 sequential — 本 change scope 含 spec / fence / skill / doc 4 类独立面,subagent 4 类 evidence 价值 > overhead)。
> 不推荐 `/forgeue:change-apply-parallel`(沿 ADR-013 D-AllChangeApplyMainRepoDefault default main repo;W2 actual diff 协议在 default main repo 路径下不 trigger;parallel benefit 不显著)。
> 不推荐 `/forgeue:change-apply-direct`(P0/P1/P3/P5 各 ≥ 3 sub-task,P5 含 9 doc edit,超过 < 3 micro-task direct 适用边界)。

**Goal**:revert ADR-011 D-WorktreeEnforce + ADR-012 D-W1-ReceiptSchema mandatory invocation 部分,restore Superpowers upstream `using-git-worktrees` Step 0 user-consent gate(default decline in implementation / opt-in for bug-fix iteration);命令模板 Preflight Worktree section 改 OPT-IN narrative;`forgeue_finish_gate.py::_check_worktree_path` v1+v2 改 field-presence-conditional advisory;`forgeue_preflight_wrapper.py` 标 deprecated 但 functional;SRS ADR-013 metadata-level supersede ADR-011/012 worktree mandatory 部分。

**Architecture**:三层 narrative + advisory revert — (1) 命令模板 narrative 层撤 mandatory worktree(default decline + opt-in for bug-fix)/ (2) finish_gate advisory 层(写了 worktree_path 字段 → validate;不写 → pass-through)/ (3) wrapper deprecation marker(opt-in path retain functional code)。worktree-coupled fence 改 advisory,W2/W3/其他 v2 fence 与 worktree 解耦保留。

**Tech Stack**:Python 3.12+ stdlib(沿既有 `tools/forgeue_*.py` 风格);ForgeUE 命令模板 markdown(`.claude/commands/forgeue/*.md`);Superpowers / ForgeUE skill markdown;OpenSpec change artifact + `openspec validate --strict`;pytest fence test 矩阵(沿 archived ADR-011/012 同款 fence pattern)。

---

## File Structure

| 路径 | 类型 | 责任 |
|---|---|---|
| `.claude/commands/forgeue/change-apply-subagent.md` | 修改 | `## Preflight Worktree` section 重写为 OPT-IN narrative(default decline + opt-in for bug-fix);保留 Skill invoke step(沿 D-CrossCheckUpstreamCascade);撤 mandatory wrapper invocation step |
| `.claude/commands/forgeue/change-apply-parallel.md` | 修改 | 同 subagent;W2 actual diff 段保留(沿 D-WrapperRetentionRationale,user opt-in worktree + parallel 时 trigger);W3 ledger append step 保留 |
| `.claude/commands/forgeue/change-apply-direct.md` | 不动 | 沿 archived `2026-05-04-adopt-subagent-driven-development` D-Worktree-Detail 第 5 项 + ADR-013 D-AllChangeApplyMainRepoDefault align |
| `tools/forgeue_finish_gate.py` | 修改 | `_check_worktree_path` v1 改 field-presence-conditional advisory;`_check_worktree_path_v2` 改同款;`_WORKTREE_REQUIRED_COMMANDS` frozenset retire(改空集合)|
| `tools/forgeue_preflight_wrapper.py` | 修改 | 模块顶部加 `__deprecated_note__` + module docstring [DEPRECATED in default flow] 标记;`--help` argparse description 加 deprecation notice |
| `tests/unit/test_forgeue_finish_gate.py` | 修改 | ~8-10 fence test 调整 advisory 行为;改 NEGATIVE test(missing 不再 block);加 advisory pass-through test;保留 written-then-validated test |
| `tests/unit/test_forgeue_command_markdown.py` | 修改 | `test_*_invokes_preflight_wrapper` 改 NEGATIVE / advisory(不再 mandatory);加新 fence `test_apply_subagent_parallel_preflight_worktree_decline_default` |
| `tests/unit/test_preflight_wrapper.py` | 不动 | 18 fence test 行为不变(只 docstring/help notice 加,test 不依赖 docstring 内容) |
| `tests/integration/test_v2_e2e_synthetic_change.py` | 可能微调 | 11 e2e test review;预计 1-2 test 调整(若依赖 mandatory blocker 行为) |
| `.claude/skills/subagent-driven-discipline/SKILL.md` | 修改 | Pattern 2 STRICT cwd verify 改 "when worktree IS used (after consent)";加新 §3.5 "Worktree Consent Policy";frontmatter `version: 2.2 → 2.3` + `worktree_consent_policy: default-decline-in-implementation` |
| `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` | 修改 | Superpowers 集成边界表 `using-git-worktrees` 行重写;Runtime Enforcement Protocol(v1)+ Runtime Enforcement Protocol v2(v2)段加 superseded note;加新 "ADR-013 Restore Superpowers Worktree Consent Gate" 段 |
| `docs/ai_workflow/forgeue_integrated_ai_workflow.md` | 修改 | §C.7 v1 + §C.8 v2 加 superseded note;加新 §C.9 "ADR-013 Restore Superpowers Worktree Consent Gate" |
| `docs/ai_workflow/README.md` | 修改 | §4.4-bis(v1)+ §4.4-ter(v2)加 superseded note;加新 §4.4-quater "Worktree Consent Gate Restored(ADR-013)" |
| `docs/ai_workflow/forgeue_quickstart.md` | 修改 | S3→S4-S5 stage wrapper 改 opt-in 描述;decline-default 行为 |
| `CLAUDE.md` | 修改 | 工具清单 9 工具不变;Runtime enforcement frontmatter 段 v1+v2 字段 OPTIONAL 标注;加 ADR-013 段 |
| `README.md` | 修改 | ForgeUE Workflow 表 9 工具不变;加 ADR-013 摘要 |
| `AGENTS.md` | 修改 | 加 ADR-013 段(沿 ADR-011/012 同款结构) |
| `CHANGELOG.md` | 修改 | [Unreleased] 加本 change entry |
| `docs/requirements/SRS.md` | 修改 | 加 ADR-013 行;ADR-011 + ADR-012 行加 `Superseded by ADR-013 (worktree mandatory parts)` cross-reference |
| `docs/acceptance/acceptance_report.md` | 修改 | 加 ADR-013 status 行(✅ 已实装);ADR-011 / ADR-012 status 行加 supersede note |
| `openspec/specs/examples-and-acceptance/spec.md` | archive 时 sync | 3 MODIFIED Requirement(替换原 ADR-011/012 mandatory 版) |

---

## Execution Phases

### Pre-P0 — codex round 1 + writeback(S2→S3 transition;**进行中**)

> 本 phase 是 S2→S3 plan stage 的一部分,通过 `/forgeue:change-plan` 命令编排;S3 进入实施前完成。

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| `notes/pre_p0/codex_review_round1.md` | tasks.md#Pre-P0.1, Pre-P0.2 | 落 codex `/codex:adversarial-review` round 1 raw output evidence(reference `notes/codex_adversarial_review_review_round1.md`) |
| `review/codex_design_review.md` | tasks.md#Pre-P0.1 | reference codex round 1 verdict(沿 archived ADR-012 同款 stub 模式) |
| `review/design_cross_check.md` | tasks.md#Pre-P0.3, Pre-P0.5 | A/B/C/D 4 段;`disputed_open: 0` 必须;Resolution 矩阵 + Verification Note(file:line) |
| writeback to design.md / proposal.md / spec.md / tasks.md | tasks.md#Pre-P0.4 | accepted-codex finding 回写 contract artifact;`writeback_commit` 真实 sha |

### P0 — 命令模板更新(D-RestoreConsentGate)

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| Read existing 命令模板 | P0.1 | Read `.claude/commands/forgeue/change-apply-subagent.md` + `change-apply-parallel.md`(archived ADR-012 P3 mandatory 版) |
| `change-apply-subagent.md` Preflight Worktree 重写 | P0.2 | 仍 invoke `Skill(superpowers:using-git-worktrees)`;default decline at Step 0 → main repo cwd;opt-in for bug-fix iteration / explicit isolation;撤 mandatory `python tools/forgeue_preflight_wrapper.py` invocation step;evidence frontmatter `worktree_path` OPTIONAL |
| `change-apply-parallel.md` 同款 | P0.3 | 同 P0.2 + W2 actual diff 段保留(只在 user opt-in worktree + parallel 时 trigger)+ W3 ledger append step 保留 |
| `change-apply-direct.md` 不动 | P0.4 | 沿 D-AllChangeApplyMainRepoDefault align |
| fence test 调整 | P0.5 | `test_subagent_parallel_have_preflight_worktree_section` 仍 PASS(section 仍存在,内容改);`test_*_invokes_preflight_wrapper` 改 NEGATIVE / advisory;加 `test_apply_subagent_parallel_preflight_worktree_decline_default` 新 fence |
| 单元测试 | P0.6, P0.7 | `pytest tests/unit/test_forgeue_command_markdown.py -v` 全绿;`python -m pytest -q` 全套 regress 全绿 |

### P1 — `forgeue_finish_gate.py` advisory fence(D-AdvisoryFenceMode)

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| Read existing fence | P1.1 | Read `tools/forgeue_finish_gate.py` `_check_worktree_path` v1 + `_check_worktree_path_v2` 现状 |
| `_check_worktree_path` v1 改 advisory | P1.2 | 入口加 worktree_path field present check;absent → return [];present → 沿原 logic validate;`_WORKTREE_REQUIRED_COMMANDS` frozenset retire(改空集合) |
| `_check_worktree_path_v2` 改 advisory | P1.3 | 入口加 worktree_receipt_path field present check;absent → return [];present → 沿原 logic validate(receipt 存在 + JSON well-formed + matches evidence) |
| fence test 调整 | P1.4 | `test_worktree_path_missing_for_change_apply_blocks` 改 NEGATIVE / advisory;`test_worktree_path_v2_missing_*` 同款;加 `test_worktree_path_advisory_pass_through_when_field_absent` + `test_worktree_path_v2_advisory_pass_through_when_receipt_absent`;保留 written-then-validated test |
| 单元测试 + e2e fixture review | P1.5, P1.6 | `pytest tests/unit/test_forgeue_finish_gate.py -v` 全绿;`tests/integration/test_v2_e2e_synthetic_change.py` 11 test review,预计 1-2 调整 |
| 全套 regress | P1.7 | `python -m pytest -q` 全套绿 |

### P2 — wrapper deprecate notice(D-WrapperDeprecate)

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| 模块 docstring | P2.1 | `tools/forgeue_preflight_wrapper.py` 顶部加 `__deprecated_note__ = "Deprecated in default flow per ADR-013;remains functional for opt-in bug-fix iteration use case"` + module docstring 加 [DEPRECATED in default flow] |
| `--help` notice | P2.2 | argparse description 加 deprecation notice |
| 单元测试 | P2.3, P2.4 | `pytest tests/unit/test_preflight_wrapper.py -v` 全绿(行为不变);全套 regress 全绿 |

### P3 — sister skill `subagent-driven-discipline` v2.3(D-CrossCheckUpstreamCascade)

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| Pattern 2 重写 | P3.1 | "STRICT cwd verify when worktree IS used (after user consent at Step 0)";显式 default = main repo cwd;cwd verify 仅在 worktree opt-in 后 trigger |
| §3.5 Worktree Consent Policy | P3.2 | 加新段:default decline in implementation;opt-in for bug-fix iteration / explicit isolation;W1 wrapper 作 opt-in tool retain |
| Case 1 P3 worktree leak scope-down | P3.3 | 标 "本 incident 在 ADR-013 default decline policy 下不会触发";留作 historical reference + bug-fix iteration use case |
| frontmatter 升级 | P3.4 | `version: 2.2 → 2.3`;`case_study_count: 2`(不变);加 `worktree_consent_policy: default-decline-in-implementation` |
| fence test | P3.5 | 校验 sister skill SKILL.md 含 "Worktree Consent Policy" 字符串(若有 fence test) |

### P4 — backbone skill `forgeue-integrated-change-workflow` 更新(D-CrossArchiveADRSupersede)

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| Superpowers 集成边界表 | P4.1 | `using-git-worktrees` 行原 "REQUIRED for ..." → "consent-gated;default decline in implementation;opt-in for bug-fix iteration / explicit isolation(ADR-013)" |
| Runtime Enforcement Protocol(ADR-011)段 | P4.2 | 加 superseded note:"D-WorktreeEnforce mandatory 部分由 ADR-013 superseded — restore Step 0 user-consent gate;_check_worktree_path fence 改 advisory" |
| Runtime Enforcement Protocol v2(ADR-012)段 | P4.3 | 加 superseded note:"D-W1-ReceiptSchema mandatory invocation 部分由 ADR-013 superseded — wrapper 改 opt-in" |
| 加新 ADR-013 段 | P4.4 | "ADR-013:Restore Superpowers Worktree Consent Gate" 简短摘要 + cross-link archive path |

### P5 — 9 处文档同步(沿 archived ADR-012 P5 模式)

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| `forgeue_integrated_ai_workflow.md` | P5.1 | §C.7 + §C.8 加 superseded note;加 §C.9 ADR-013 |
| `docs/ai_workflow/README.md` | P5.2 | §4.4-bis + §4.4-ter 加 superseded note;加 §4.4-quater ADR-013 |
| `forgeue_quickstart.md` | P5.3 | S3→S4-S5 stage wrapper 改 opt-in 描述 |
| `CLAUDE.md` | P5.4 | Runtime enforcement frontmatter 段 v1+v2 字段 OPTIONAL 标注;加 ADR-013 段 |
| `README.md` | P5.5 | ForgeUE Workflow 表 9 工具不变;加 ADR-013 摘要 |
| `AGENTS.md` | P5.6 | 加 ADR-013 段(沿 ADR-011/012 结构) |
| `CHANGELOG.md` | P5.7 | [Unreleased] 加本 change entry |
| `SRS.md` | P5.8 | 加 ADR-013 行;ADR-011/012 行加 supersede cross-reference |
| `acceptance_report.md` | P5.9 | 加 ADR-013 status 行;ADR-011/012 加 supersede note |

### P6 — verify

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| Level 0 + Level 1 | P6.1, P6.2 | `python tools/forgeue_verify.py --change <id> --level 0`;Level 1(L1 SKIP opt-in 沿 ADR-007) |
| evidence | P6.3 | 产 `verification/verify_report.md`(12-key audit frontmatter) |

### P7 — codex S6 mixed-scope review

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| dispatch | P7.1 | `/codex:review --base main --scope branch` mixed-scope(default background) |
| evidence + writeback | P7.2, P7.3, P7.4 | 落 `review/codex_mixed_scope_review.md`(verdict + finding verbatim + Claude file:line verify + Cross-check Matrix + Resolution Plan);writeback;`disputed_open: 0` 验证 |
| pre-commit P7 替代 stub | P7.X | reference 模式落 codex_design_review.md / codex_plan_review.md / codex_verification_review.md / codex_adversarial_review.md / design_cross_check.md / plan_cross_check.md(沿 archived ADR-012 P7 同款) |

### P8 — SKIP superpowers requesting-code-review(沿 archived ADR-012 P8 同款)

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| SKIP rationale stub | P8.1 | 写 `review/superpowers_review.md` SKIP rationale stub |

### P9 — Documentation Sync Gate

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| 静态扫 | P9.1 | `python tools/forgeue_doc_sync_check.py --change <id>` 0 DRIFT |
| evidence | P9.2 | 落 `verification/doc_sync_report.md` |
| DRIFT 修复 | P9.3 | 任何 [DRIFT] 项 → 修复 |

### P10 — Finish Gate

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| finish_gate run | P10.1 | `python tools/forgeue_finish_gate.py --change <id> --no-validate`(预期 P11 unchecked sole blockers) |
| 全检 | P10.2-P10.7 | 12-key frontmatter / cross-check disputed_open=0 / evidence v1 protocol_version / writeback_commit 真实性 / tasks.md P0-P10 全 [x] / `openspec validate --strict` 全绿 |
| evidence | P10.8 | `verification/finish_gate_report.md` 自动生成 |

### P11 — Archive(用户授权 fence #1 不可逆)

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| 用户授权 | P11.1 | D-AutonomyBoundary fence #1 升级用户授权 |
| archive | P11.2 | `openspec archive <id> --skip-specs --yes` |
| spec sync | P11.3, P11.4 | 手工 sync 3 MODIFIED Requirement;`openspec validate examples-and-acceptance --strict` 全绿 |
| archive stub | P11.5 | 加 cross_check fence-required frontmatter |
| duplicate prevent | P11.6 | `git rm -r openspec/changes/<id>/`(防 archived ADR-012 同款 duplicate bug) |
| commit + push | P11.7 | 用户授权 fence #1 |

### P12 — 后置 + Follow-on tracking

| Sub-task | tasks.md anchor | Description |
|---|---|---|
| MEMORY.md update | P12.1 | 加 ADR-013 摘要(沿 forgeue auto memory 协议) |
| dogfood 验证 | P12.2 | 实战:下一个 active change 按 ADR-013 default decline 流程跑 |
| follow-on tracking | P12.3, P12.4 | `enhance-workflow-automation-ledger-binding` / `enhance-workflow-automation-handoff-persistence` / `add-forgeue-brainstorm-stage` / `enhance-workflow-automation-finishing-branch` / `enhance-workflow-automation-final-review-fence-strictness` / `enhance-workflow-automation-v2-fence-hardening` / `analyze-superpowers-skills-openspec-integration-gaps` |

---

## Self-Review

**1. Spec coverage**:7 D-decision 全部映射到 tasks.md P0-P5 phase + tasks.md Pre-P0 / P6-P12 supporting infrastructure。3 OQ 在 design.md `## Open Questions` 段记录,Pre-P0 codex round 1 挑战。5 Risks 在 design.md `## Risks / Trade-offs` 段记录 + R1 mitigation 在 P3.1 Pattern 2 + P3.2 §3.5 + P3.3 Case 1 scope-down 落地。

**2. Placeholder scan**:无 TBD / TODO / "fill in later"。每 sub-task tasks.md anchor 真实存在 + 行为说明。

**3. Type consistency**:`worktree_path` / `worktree_receipt_path` field 命名统一;`_check_worktree_path` v1 + `_check_worktree_path_v2` 函数名沿 archived ADR-011/012 既有;`_WORKTREE_REQUIRED_COMMANDS` frozenset 名称沿 ADR-011 既有。

## References

- archived `2026-05-05-enhance-workflow-automation-executable-enforcement/execution/execution_plan.md`(模板复用源)
- `design.md` `## Decisions` 7 D-decision + `## Open Questions` 3 OQ + `## Risks / Trade-offs` 5 Risks
- `tasks.md` Pre-P0 → P12 phase + sub-task anchor 真源
- `forgeue_integrated_ai_workflow.md` §B.1 状态机 + §E.1 evidence subdir + §C.7/C.8 Runtime Enforcement Protocol
