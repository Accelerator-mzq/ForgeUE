---
change_id: fix-export-d12-and-skipped-evidence-filter
stage: S3
evidence_type: baseline
contract_refs:
  - tasks.md
  - design.md
  - execution/execution_plan.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-apply-subagent
codex_plugin_available: true
autonomy_decision: claude_autonomous
created_at: 2026-05-07T20:35:00Z
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
    - superpowers:requesting-code-review
    - superpowers:finishing-a-development-branch
  cascade_check_pass_at: 2026-05-07T19:48:00Z
---

# fix-export-d12-and-skipped-evidence-filter — P0 Baseline

> P0 baseline 数据 — 进入 Phase A 实施前固定基线 / Phase E final verify 时对照。

## pytest baseline

`python -m pytest -q` 实测:

```
1700 passed, 1 failed, 1 skipped in 57.30s
```

- **1 pre-existing fail**:`tests/unit/test_forgeue_cross_check_format.py::test_real_cross_check_files_have_evidence_type` — 沿 active follow-on `fix-cross-check-format-test-enum-extension`(archived ledger-binding `review_cross_check.md` 用 `evidence_type: review_cross_check` 不在 test 允许 enum;**非本 change 引入**)
- **1 skipped**:`tests/unit/test_comfy_subprocess_video.py:523` Windows symlink admin permission(POSIX 全覆盖,Windows skip 是预期)
- **本 change 实施后预期**:`baseline + ~18 fence case 增加`(Phase A 9 + Phase B 9)→ ~1718 passed,1 pre-existing fail,1 skipped

## forgeue_finish_gate baseline JSON

跑 `python tools/forgeue_finish_gate.py --change fix-export-d12-and-skipped-evidence-filter --json` 期望多 evidence_missing blocker(verify_report / doc_sync_report / superpowers_review / codex_verification_review / codex_adversarial_review 等)— 这些是 finish stage(S5+)evidence,本 P0 baseline 时 **预期 missing**,不阻断 plan stage 实施;Phase E 各 stage gate 触发后逐步补齐。

## forgeue_change_state baseline JSON

```json
{
  "change_id": "fix-export-d12-and-skipped-evidence-filter",
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

S3 baseline:全部 plan stage artifact 落地(proposal / design / tasks / specs delta / execution / review cross-check / notes round counter);writeback-check exit 0;无 DRIFT。

## Commit chain pre-implementation

```
c9618a5 chore(forgeue): S3 sweep writeback_commit
718b0a1 feat(forgeue): S3 plan codex round 2 inline writeback
8c790ec chore(forgeue): S2 sweep writeback_commit
efd2129 feat(forgeue): S2 plan
582c8eb feat(forgeue): centralize-followon-backlog-registry P10 archive(prior change)
```

## Files Touched expected(execution_plan.md `## Files Touched`)

| Phase | Files |
|---|---|
| A | src/framework/core/ue.py + src/framework/ue_bridge/manifest_builder.py + src/framework/runtime/executors/export.py + 2 new test files |
| B | ue_scripts/evidence_writer.py + ue_scripts/run_import.py + ue_scripts/domain_video.py + 3 new test files |
| C | tests/integration/test_p4_ue_manifest_only.py(modify) |
| D | docs/design/LLD.md + HLD.md + test_spec.md + acceptance + CLAUDE.md + AGENTS.md + CHANGELOG.md + openspec/specs/ + openspec/backlog/active+archived |
| E | (no code change;evidence + commit chain only) |

## P0 完成

P0 baseline 落地 → 进入 Phase A subagent dispatch。
