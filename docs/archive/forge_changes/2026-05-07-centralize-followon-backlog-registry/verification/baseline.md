---
change_id: centralize-followon-backlog-registry
stage: S4
evidence_type: verify_baseline
contract_refs:
  - tasks.md#P0
  - design.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-apply-subagent
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
created_at: 2026-05-07T17:35:00Z
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
    - superpowers:requesting-code-review
    - superpowers:finishing-a-development-branch
  cascade_check_pass_at: 2026-05-07T17:30:00Z
---

# Baseline — centralize-followon-backlog-registry P0

## P0.1 — pytest baseline

```
1589 passed, 1 failed, 1 skipped in 69.58s
```

**Pre-existing fail**(沿 retire P5 verify_report.md L72 同款,**非本 change 引入**):

```
FAILED tests/unit/test_forgeue_cross_check_format.py::test_real_cross_check_files_have_evidence_type
AssertionError: review_cross_check.md has unexpected evidence_type='review_cross_check'
assert 'review_cross_check' in ('design_cross_check', 'plan_cross_check', 'implementation_cross_check')
```

**根因**:archived `enhance-workflow-automation-ledger-binding/review/review_cross_check.md` evidence_type 字段值 `review_cross_check` 不在 `test_real_cross_check_files_have_evidence_type` 的允许 enum 内。

**Skipped**:`test_comfy_subprocess_video.py:523`(symlink 在 Windows 需要 admin 权限,POSIX 全过)。

### Dogfood 暴露 — registry backfill scope adjustment

P0.1 实测 confirms `fix-cross-check-format-test-enum-extension` follow-on 仍 active(retire 时已识别但未在 retire P12 tracking)。这是 centralize 协议设计要 catch 的**典型 systemic gap**:

- retire `verification/verify_report.md` L72 标过该 follow-on
- 但**不在** retire `tasks.md` P12 follow-on tracking section
- 后续 fix-finish-gate-archived-replay-compat micro-bugfix(`88a8aec`)未包含
- 当前 P0.1 实测确认仍 active

本 change 自家 P0 baseline pytest dogfood 直接暴露此 gap。

**Action**:本 change 把它**纳入 P1.3.8 backfill** 入 active.md(workflow-protocol 7 → 8;total 22 → 23 active)。proposal.md / design.md / specs/.../spec.md / tasks.md 同步更新(本 P0 phase 内 batch)。

> 注:这是协议 dogfood 价值实证 — 若没有 P0.1 baseline pytest + 实测 fail 检验,fix-cross-check-format-test-enum-extension 会以"sub-conscious followon"状态继续被错过。registry 启用即 catch。

## P0.2 — finish_gate baseline

```
exit code 0 (CLI itself OK; report.summary.blocker_count = 90)
```

**90 blocker breakdown**:全 `tasks_unchecked` type — P0 phase 时 tasks.md 中所有 P1-P8 task checkbox 仍 `- [ ]`(本 change 实施期会逐个 checked off;P7 retro / P8 archive 时 checkbox 全 checked,fence 应 PASS)。

**预期路径**:P0 baseline 时 90 blocker → 实施期 phase by phase mark complete → P7 finish_gate 应 PASS。这是 expected workflow,fence 在 P5/P7 才作终态守门。

## P0.3 — change_state state inference

```json
{
  "change_id": "centralize-followon-backlog-registry",
  "archived": false,
  "state": "S3",
  "state_reasons": [
    "proposal+design+tasks all present (S2 baseline)",
    "execution/execution_plan.md present (S3)"
  ],
  "drifts": [],
  "frontmatter_issues": [],
  "structural_issues": []
}
```

State S3 plan complete + DRIFT 0,准备进 S4-S5 implementation。

## P0.4 — Backfill 数据源汇总

### 8 项 workflow-protocol active(adjusted from 7 → 8;P0.1 dogfood 暴露 +1):

| # | id | source | trigger | retire-impact |
|---|---|---|---|---|
| 1 | `fix-video-export-path-split-d12-violation` | retire `verify_report.md` L83 + `review_cross_check.md` F3 | export.py video drop loop 触发 D12 路径分流违规修 | unaffected |
| 2 | `fix-run-import-skipped-filter-permission-only` | retire `verify_report.md` L84 + `review_cross_check.md` F4 | run_import.py skipped filter 触发非 permission skip 误吞修 | unaffected |
| 3 | `enhance-workflow-automation-handoff-persistence` | enhance-workflow-automation `tasks.md` P10.3 / `subagent_final_review.md` F6 | codex 命令 allowed-tools vs Polling Convention 写文件能力 mismatch arch 改造 | unaffected |
| 4 | `add-forgeue-brainstorm-stage` | adopt-subagent-driven-development `design.md:23` Out of Scope | Superpowers brainstorming skill 接入 S0/S1 stage | unaffected |
| 5 | `enhance-workflow-automation-finishing-branch` | runtime-enforcement `tasks.md` P11.6 | `superpowers:finishing-a-development-branch` skill 接入 `/forgeue:change-finish` 命令 | unaffected |
| 6 | `enhance-workflow-automation-final-review-fence-strictness` | executable-enforcement `tasks.md` P12.7 | `_check_evidence_dispatch_authenticity` fence 区分真 dispatch evidence vs SKIP stub | scope-narrowed(原 v2 fence cross-check coverage 提议在 retire 后失效;v1 fence gap 持续) |
| 7 | `analyze-superpowers-skills-openspec-integration-gaps` | restore-consent-gate `tasks.md` P12.4 | 5 Superpowers 技能 × ForgeUE workflow 适配缺口 systematic audit(原 6 缩 5,剔 dispatching-parallel-agents) | scope-narrowed(retire 后 6 → 5) |
| 8 | `fix-cross-check-format-test-enum-extension` | retire `verify_report.md` L72(non-P12 mention)+ **本 change P0.1 dogfood 暴露** | `test_real_cross_check_files_have_evidence_type` 允许 enum 扩 `review_cross_check`(archived ledger-binding 用此 evidence_type 类型) | unaffected |

### 9 项 requirements-tbd-pointer(SRS §7.3 active TBD):

- TBD-001 / TBD-002 / TBD-003 / TBD-004 / TBD-005 / TBD-010 / TBD-011 / TBD-012 / TBD-013

### 6 项 capability-boundary(LLD inline 注释):

- `audio-metadata-parser`(LLD §<audio> + LLD:191 inline)
- `video-metadata-parser`(LLD §<video> + LLD:256 inline)
- `comfy-video-webm-adoption`(LLD §<video> + LLD:254 inline + CLAUDE.md ComfyUI Video section)
- `comfy-video-v2v-adoption`(CLAUDE.md ComfyUI Video Phase 3 D7 限制段)
- `comfy-video-image-sequence-adoption`(CLAUDE.md ComfyUI Video Phase 3 D1 (β) FileMediaSource 优先段)
- `video-bmff-largesize-support`(CLAUDE.md ComfyUI Video BMFF strict header 段 + Phase 3 round-2 F4)

### 3 项 archived.md 首批 tombstone:

| id | cancellation_reason | archived_at_commit | archived_in_change |
|---|---|---|---|
| `enhance-workflow-automation-v2-fence-hardening` | cancelled-superseded by `enhance-workflow-automation-ledger-binding` | `8a42c71` | enhance-workflow-automation-ledger-binding |
| `fix-finish-gate-section-regex-for-p-prefixed` | cancelled-completed: `88a8aec` | `88a8aec` | fix-finish-gate-archived-replay-compat |
| `fix-openspec-validate-archived-change-support` | cancelled-completed: `88a8aec` | `88a8aec` | fix-finish-gate-archived-replay-compat |

## Notes

- P0 phase 全 controller direct 模式(纯数据汇总,无 implementation 决策);本 baseline.md 是 P0.5 evidence
- P1 phase 也 direct(纯 .md 写入 23 + 3 = 26 entries + README + SRS cross-link),无 subagent dispatch
- P2.a 起进 subagent dispatch 模式
