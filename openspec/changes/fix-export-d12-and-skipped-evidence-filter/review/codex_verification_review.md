---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S5
evidence_type: codex_verification_review
contract_refs:
  - design.md
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/verification/verify_report.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-verify
codex_plugin_available: true
codex_session_id: 019e0747-39e8-7a80-aac2-44f6c5754f02
codex_job_id: bwp5dfg15
verdict: needs-attention
findings_count: 5
findings_severity:
  high: 0
  medium: 4
  low: 1
disputed_open: 0
runtime_enforcement_protocol_version: v1
review_type: codex_mixed_scope_review
review_round: 1
created_at: 2026-05-08T19:15:00Z
resolved_at: 2026-05-08T19:18:00Z
resolution_summary: codex /codex:review --base main mixed-scope review;5 finding(4 P2 + 1 P3)全部 out-of-current-change-scope — 来自 archived `2026-05-07-centralize-followon-backlog-registry`(commits 646989c / 5427f18 / df049e8 / 320cda1 / 4487c60 / 1a13d89 / 0554caa / 703f848 / ea8d3e6 / 1bd5079)+ enum_cross_ref_check 微 bugfix(2026-05-06)。本 change `fix-export-d12-and-skipped-evidence-filter` 实施代码(`src/framework/runtime/executors/export.py` + `manifest_builder.py` + `core/ue.py` + `ue_scripts/*.py`)codex 0 finding。沿 ForgeUE memory `feedback_partial_vs_whole_retire_audit`(严控 scope 边界)+ archived `2026-05-06-retire-parallel-and-worktree-fully` F3+F4 同款 cross-archive scope 处理先例(out-of-retire-scope finding 标 follow-on backlog 而非 inline 修)— 5 finding 全标 follow-on backlog,不在本 change 修;disputed_open: 0(无本 change scope 内 disputed)。
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_verification_review_review_round1.md
---

# Codex Verification Review — fix-export-d12-and-skipped-evidence-filter (S5)

> S5 verification stage codex `/codex:review --base main` mixed-scope review。沿 backbone `forgeue:change-verify` Step 6:codex 单向挑错,不走 cross-check,Claude 独立 file:line verify 后决定接受。

## Round Summary

| Round | Thread ID | Verdict | Findings | Disposition |
|---|---|---|---|---|
| 1 | `019e0747-39e8-7a80-aac2-44f6c5754f02` | needs-attention | 5(0 high + 4 medium + 1 low)| **全部 out-of-current-change-scope** → follow-on backlog;**disputed_open: 0**(本 change scope 内 0 finding)|

## Findings 摘要 + scope 边界 verify

| F# | severity | claim | file:line | 触发 commit | scope? | resolution |
|----|----------|-------|-----------|-------------|---------|---|
| F1 | P2 | `_validate_cancel_tag_completed` 用当前 active.md 构造 registry_entries,已删除 id 查不到,误拦正常 completed | `tools/forgeue_finish_gate.py:2529-2532` | `703f848`(2026-05-07,centralize-followon)| ❌ **out-of-current-change-scope** | follow-on backlog `fix-finish-gate-completed-cancel-uses-baseline-entries` |
| F2 | P2 | follow-on item / registry heading 正则只接受 `[a-z0-9-]+`,SRS TBD 大写编号(`TBD-001`)不匹配 → tombstone/cancel 校验跳过 | `tools/forgeue_finish_gate.py:1464-1471` | `4487c60`(2026-05-07,centralize-followon)| ❌ out-of-current-change-scope | follow-on backlog `fix-finish-gate-followon-regex-allow-tbd-uppercase` |
| F3 | P2 | tasks_cancel_tag 缺失时 expected_reason_prefix 为空,startswith("") 永远 true,tombstone 5-point 一致性 fence 失效 | `tools/forgeue_finish_gate.py:1741-1743` | `703f848`(2026-05-07,centralize-followon)| ❌ out-of-current-change-scope | follow-on backlog `fix-finish-gate-tombstone-empty-cancel-tag-bypass` |
| F4 | P2 | append-only fence 仅在 4 行内找 `+ **field**` 才 raise,直接删字段不补不会报 → archived `centralize-followon-backlog-registry` design 的 tombstone protected fields 协议受保护字段删除漏报 | `tools/forgeue_finish_gate.py:2388-2396` | `1a13d89`(2026-05-07,centralize-followon)| ❌ out-of-current-change-scope | follow-on backlog `fix-finish-gate-archived-md-protected-field-deletion` |
| F5 | P3 | enum_cross_ref_check 输出 Unicode `∈` `…` 但 `main()` 未调 `setup_utf8_stdout` → Windows GBK 环境 print 可能 raise UnicodeEncodeError | `tools/forgeue_enum_cross_ref_check.py:330` | 微 bugfix commit(2026-05-06)| ❌ out-of-current-change-scope | follow-on backlog `fix-enum-cross-ref-check-windows-gbk-print` |

## Independent verification(沿 ForgeUE memory `feedback_verify_external_reviews`)

| F# | 验证步骤 | 结论 |
|----|---------|------|
| F1 | `git log --oneline 8c31a8b..fcc83e5 -- tools/forgeue_finish_gate.py` 查 `_validate_cancel_tag_completed` 引入 commit | ✅ commit `703f848` 来自 archived `centralize-followon-backlog-registry`,**非本 change**(本 change 实施代码全部在 `src/framework/` + `ue_scripts/`)|
| F2 | 同上,查 follow-on 正则引入 commit | ✅ commit `4487c60` 来自同 archived change |
| F3 | 同上,查 tombstone 5-point 一致性 fence 引入 commit | ✅ commit `703f848` 同源 |
| F4 | 同上,查 append-only fence 引入 commit | ✅ commit `1a13d89` 来自同 archived change |
| F5 | `git log --oneline -- tools/forgeue_enum_cross_ref_check.py` 查 enum checker file 引入 commit | ✅ 微 bugfix 2026-05-06 commit,**非本 change**(本 change `fix-export-d12-and-skipped-evidence-filter` proposal 创建 2026-05-07)|

**5 finding 全部 verified out-of-current-change-scope**,本 change 实施代码 codex 0 finding。

## 为什么 codex `--base main` 会 catch out-of-scope finding

`/codex:review --base main` 是 mixed-scope review(沿命令模板 `review_type: codex_mixed_scope_review`),review 范围是 branch diff vs main 全部 commits(本 branch 含 30+ commits 跨多个 archived change)。codex 不区分 scope 边界,所有触及代码都可能 raise finding。

**ForgeUE 处理协议**(沿 memory `feedback_partial_vs_whole_retire_audit` 严控 scope 边界 + archived `2026-05-06-retire-parallel-and-worktree-fully` F3+F4 同款 cross-archive scope 处理先例 — out-of-retire-scope finding 标 follow-on backlog 而非 inline 修):

1. Claude **独立 file:line verify** 每条 finding 触发 commit
2. 若 finding 来自 archived change commits → **out-of-current-change-scope**,标 follow-on backlog
3. 若 finding 来自本 change commits → 评估是否 inline writeback fix
4. **disputed_open** 仅计本 change scope 内未解决 finding;cross-archive finding 不计入

本轮 5/5 finding 全 out-of-scope → disputed_open: 0,S5 推进就绪。

## Follow-on backlog tracked(5 entries to add post-archive)

按 ForgeUE backlog protocol,本 change archive 阶段(Phase E.5 finish_gate)要在 `openspec/backlog/active.md` workflow-protocol section 加 5 entries:

1. **`fix-finish-gate-completed-cancel-uses-baseline-entries`**(P2):`_validate_cancel_tag_completed` 用 baseline/prior entry 或 tombstone snapshot 校验 completed commit,而非当前 active.md(已 archived id 找不到导致误拦)
2. **`fix-finish-gate-followon-regex-allow-tbd-uppercase`**(P2):follow-on item / registry heading regex 加 `[A-Z]` 支持 SRS TBD-XXX 大写编号
3. **`fix-finish-gate-tombstone-empty-cancel-tag-bypass`**(P2):tombstone 5-point fence 显式要求 tag type 非空,避免 startswith("") 全 true 让 tombstone 漏检 cancel tag
4. **`fix-finish-gate-archived-md-protected-field-deletion`**(P2):append-only fence 加"protected field 删除不补"路径检测,不只看 `- ... + ...` modify pair
5. **`fix-enum-cross-ref-check-windows-gbk-print`**(P3):`forgeue_enum_cross_ref_check.py` warning 文本去 Unicode `∈` `…` ASCII coercion 或 main() 调 `_common.setup_utf8_stdout()`

完整 finding 内容 + Recommendation 见 `notes/codex_verification_review_review_round1.md`(verbatim)。
