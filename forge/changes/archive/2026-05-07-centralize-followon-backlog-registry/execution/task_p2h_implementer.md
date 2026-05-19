---
change_id: centralize-followon-backlog-registry
stage: S4-S5
evidence_type: subagent_implementer_report
contract_refs:
  - openspec/changes/centralize-followon-backlog-registry/tasks.md#P2.h
  - openspec/changes/centralize-followon-backlog-registry/design.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-apply-subagent
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
  cascade_check_pass_at: 2026-05-07T17:30:00Z
subagent_continuity:
  round_1_implementer_id: a4f91199f34b4f334
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
created_at: 2026-05-07T20:55:00Z
---

# P2.h Implementer Report

## Phase scope

P2.h — registry schema integration tests(`tests/unit/test_followon_registry.py` 新建);P2.h.1-P2.h.6 unit cases for fence/helpers 大部分已在 P2.b/P2.d/P2.g phases 通过 TDD red→green 完成。

## Implementation

| Component | Tests | Commit |
|---|---|---|
| `tests/unit/test_followon_registry.py` 新建 | 24 | `deb9d51` |
| `openspec/backlog/active.md` 重排(TBD section 前置防 parser bleed) | (data) | `deb9d51` |
| `_parse_tbd_pointer_entries` body boundary fix(controller direct;P2.h dogfood reveal) | 1 threshold 调整 | `5427f18` |

3 test classes:
- `TestActiveMdSchema`(13 tests)— 8-field schema + status: active + category enum + entry counts
- `TestArchivedMdSchema`(7 tests)— 4-field tombstone + valid SHA + valid JSON snapshot + 3 first-batch tombstones
- `TestRegistryReadme`(4 tests)— README.md exists + documents schema/fence/cancel protocol

## Regression

1666 → 1690(+24);P2.h subagent dispatch 后再加 parser fix + 1 threshold 调整 → 207 PASS in `test_followon_registry.py + test_forgeue_finish_gate.py`(combined run)

## Dogfood value

P2.h test exposed REAL parser bug:`_parse_tbd_pointer_entries` body boundary 仅用 TBD heading 截止 → 最后 TBD entry body bleeds into lowercase section,category 被覆盖致 filter-dropped。

Real impact:`_check_srs_registry_consistency` 会假触发 BLOCKER `srs_registry_set_mismatch_added_[TBD-013]` even though entry exists in active.md。

**Fix(controller direct micro-cleanup)**:body boundary 加 H2/H3 (任意 case) 约束 — 5-line change in `_parse_tbd_pointer_entries`(commit `5427f18`)+ test threshold 8 → 9。

## Constraint compliance

- ✅ stdlib only(json / pathlib / pytest)
- ✅ append-only(test file 新建;parser micro-fix 是 P2.h dogfood 必需)
- ✅ single commit + parser micro-fix commit
- ✅ no plan file read

## Deviation(by subagent + controller follow-up)

1. **active.md section 重排**(by subagent):TBD section 前置(原最后)防 parser body-boundary bleed。**Disposition**:retain — disclosed in active.md L7 注释
2. **Parser threshold 8 → 9**(by controller post-subagent):subagent 暂用 ≥ 8 阈值 disclose limitation;controller 修 parser bug 后阈值升回 schema-correct ≥ 9

## Token usage

- input ~57000;output ~25000;total 81559
- model: claude-sonnet-4-6;estimated_usd: $0.55
- duration_ms: 921196;tool_uses: 39
