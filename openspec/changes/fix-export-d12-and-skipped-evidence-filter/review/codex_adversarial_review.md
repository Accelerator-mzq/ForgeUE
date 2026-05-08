---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S6
evidence_type: codex_adversarial_review
contract_refs:
  - design.md
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/specs/ue-export-bridge/spec.md
  - openspec/changes/fix-export-d12-and-skipped-evidence-filter/verification/verify_report.md
aligned_with_contract: false
drift_decision: written-back-to-design
writeback_commit: pending
drift_reason: S6 finalize round 3 codex adversarial mixed-scope review 2 finding 全 accepted-codex inline writeback;F1 (P2 medium) 承 round1-F3 evidence drop path Windows backslash 与 manifest POSIX source_uri 不一致 → fix `export.py:134` 改 `.as_posix()` + P4 integration test 删 `.replace("\\", "/")` normalize;F2 (P2 medium) S5 verification review 5 follow-on(F1-F5)未入 active.md → 5 entry 加 active.md workflow-protocol section(13 entries 总,从 8 上升)。详 review/subagent_final_review.md final assessment + notes/codex_adversarial_review_review_round3.md verbatim。
reasoning_notes_anchor: review/subagent_final_review.md
detected_env: claude-code
triggered_by: /forgeue:change-review
codex_plugin_available: true
codex_session_id: pending
codex_job_id: bpattvrld
verdict: needs-attention
findings_count: 2
findings_severity:
  high: 0
  medium: 2
  low: 0
disputed_open: 0
runtime_enforcement_protocol_version: v1
review_type: codex_adversarial_review
review_round: 3
created_at: 2026-05-08T19:30:00Z
resolved_at: 2026-05-08T19:35:00Z
resolution_summary: round 3 finalize stage 2 finding 全 accepted-codex inline writeback;F1 fix `src/framework/runtime/executors/export.py:134` 改 `.as_posix()` + P4 test L1330 删 `.replace("\\", "/")`;F2 fix `openspec/backlog/active.md` 加 5 follow-on workflow-protocol entries(`fix-finish-gate-completed-cancel-uses-baseline-entries` + `fix-finish-gate-followon-regex-allow-tbd-uppercase` + `fix-finish-gate-tombstone-empty-cancel-tag-bypass` + `fix-finish-gate-archived-md-protected-field-deletion` + `fix-enum-cross-ref-check-windows-gbk-print`);disputed_open: 0;writeback_commit pending → 真实 hash sweep。
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_adversarial_review_review_round3.md
---

# Codex Adversarial Review — fix-export-d12-and-skipped-evidence-filter (S6 finalize round 3)

> S6 finalize stage codex `/codex:adversarial-review` mixed-scope review。沿 backbone `/forgeue:change-review` Step 5。

## Round Summary

| Round | Stage | Job ID | Verdict | Findings | Disposition |
|---|---|---|---|---|---|
| 1 | S2 design | be6046t7v | needs-attention | 4(3 P1 + 1 P2)| 全 accepted-codex inline writeback;design D1+D2+D6+新 D10 + spec ADDED/MODIFIED |
| 2 | S3 plan | bgxq8degl | needs-attention | 2(1 P1 + 1 P2)| 全 accepted-codex inline writeback;tasks.md 3.1 加 2 case + 3.3 双路径必需 evidence |
| **3** | **S6 finalize** | **bpattvrld** | needs-attention | 2 medium | **全 accepted-codex inline writeback** — F1 export.py 改 `.as_posix()` + P4 test 删 normalize / F2 active.md 加 5 follow-on entries |

**Total**:3 round 8 finding 全 accepted-codex,disputed_open=0 across all rounds。

## Findings(round 3 finalize)

### F1 [P2 medium] Evidence drop path 在 Windows 下不是 POSIX(承 round1-F3)

- **file:line**:`src/framework/runtime/executors/export.py:134`
- **claim**:`str(target_fs.relative_to(Path(target.project_root)))` Windows 产生 `Content\Movies\...`,与 manifest `source_uri` POSIX `Content/Movies/...` 不一致;L2 evidence 已记录(`evidence.json` `target_object_path`)+ P4 integration test `.replace("\\", "/")` normalize 规避
- **resolution**:**accepted-codex** — Phase A.5 implementer 严格按 spec verbatim L32 实施 `str(...)`,但 spec 自身是 latent design smell(承 round1-F3 单源契约只覆盖 manifest 不覆盖 evidence)。Inline fix:
  - `src/framework/runtime/executors/export.py:134` 改 `.as_posix()`(注释引用 round 3 codex F1)
  - `tests/integration/test_p4_ue_manifest_only.py:1330` 删 `.replace("\\", "/")` normalize,改 raw equality(注释 round 3 codex F1 修订)
  - 跑 `pytest tests/unit/test_export_video_path_split.py tests/integration/test_p4_ue_manifest_only.py -q`:24 PASS + 2 skip(无回归)

### F2 [P2 medium] S5 verification review 5 follow-on 没入 active.md

- **file:line**:`openspec/changes/fix-export-d12-and-skipped-evidence-filter/review/codex_verification_review.md:76-84`
- **claim**:S5 verification review 明确列 5 P2/P3 follow-on candidate(`fix-finish-gate-completed-cancel-uses-baseline-entries` / `fix-finish-gate-followon-regex-allow-tbd-uppercase` / `fix-finish-gate-tombstone-empty-cancel-tag-bypass` / `fix-finish-gate-archived-md-protected-field-deletion` / `fix-enum-cross-ref-check-windows-gbk-print`)+ 文档中说"archive 阶段加 active.md",但 active registry 当前没这 5 id;post-archive 处理 = finish gate 跟踪不到 + accepted out-of-scope findings 归档后丢失追踪
- **resolution**:**accepted-codex** — 修复轨迹 S5 verification 自身写错(说"archive 阶段加")。Inline fix:
  - `openspec/backlog/active.md` 在 `fix-cross-check-format-test-enum-extension` 之后 / `## Capability-boundary(6)` 之前加 5 entries(workflow-protocol section)
  - active.md 头部计数从 `23 entries 总(8 workflow-protocol + ...)` 更新为 `28 entries 总(13 workflow-protocol + ...)`
  - 每 entry 含完整 8-field schema:source(refs codex_verification_review F# + trigger commit)+ description(细节 + line refs + 故障原理)+ trigger(实证 / 用户)+ category(workflow-protocol)+ retire-impact-status(unaffected)+ priority(P2 medium / P3 low)+ status(active)

## Independent verification(沿 ForgeUE memory `feedback_verify_external_reviews`)

| F# | 验证步骤 | 结论 |
|----|---------|------|
| F1 | Read `src/framework/runtime/executors/export.py:134` 实测 `str(target_fs.relative_to(Path(target.project_root)))` + Read `tests/integration/test_p4_ue_manifest_only.py:1330` 实测 `.replace("\\", "/")` normalize | ✅ 验证成立。spec verbatim L32 写 `str(...)` 但 spec 设计 oversight(round1-F3 单源契约只盖 manifest;evidence path 单源缺漏)|
| F2 | grep `openspec/backlog/active.md` 看 5 follow-on id 是否存在 | ✅ 验证成立。S5 verification review evidence 写"archive 阶段补"但 finish gate Preflight 之前补才合规(防止丢失追踪)|

## Conclusion

round 3 finalize stage 2 finding 全 accepted-codex inline writeback;**disputed_open: 0**;`/forgeue:change-review` Step 8 推进就绪(进 S7)。

完整 finding 内容 + Recommendation 见 `notes/codex_adversarial_review_review_round3.md`(verbatim)。
