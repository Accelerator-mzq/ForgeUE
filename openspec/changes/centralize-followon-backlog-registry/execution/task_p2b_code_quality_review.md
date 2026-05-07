---
change_id: centralize-followon-backlog-registry
stage: S4-S5
evidence_type: subagent_code_quality_review
contract_refs:
  - openspec/changes/centralize-followon-backlog-registry/tasks.md#P2.b
  - openspec/changes/centralize-followon-backlog-registry/execution/task_p2b_implementer.md
  - openspec/changes/centralize-followon-backlog-registry/execution/task_p2b_spec_review.md
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
    - superpowers:requesting-code-review
  cascade_check_pass_at: 2026-05-07T17:30:00Z
subagent_continuity:
  round_1_implementer_id: a27ddb2675fc2bef6
  round_1_spec_reviewer_id: ac7b73496ccd50028
  round_1_code_quality_reviewer_id: a674f41d6c782ca7b
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
created_at: 2026-05-07T19:00:00Z
---

# P2.b Code Quality Review

## Verdict

**pass**(0 blocking;3 P3 nitpick non-blocking)

## Findings(advisory only)

### F1 [P3 nitpick] `import subprocess as _sp` 重复 import

- File: `tests/unit/test_forgeue_finish_gate.py:2764`
- Issue: 文件顶 L28 已有 `import subprocess`,L2764 P2.b tests append 段重复 `import subprocess as _sp` 别名。`_git` helper 用 `_sp.run(...)`,与文件其余风格不一致。
- Recommendation: 删 L2764 重复 import,`_git` helper 直接用 `subprocess.run(...)` 沿文件顶部 import。
- **Disposition**: non-blocking advisory;P2.c+ 实施时 sync 改

### F2 [P3 advisory] Check 5 `expected_reason_prefix` 空字符串静默 pass

- File: `tools/forgeue_finish_gate.py:1696` (`_validate_tombstone_consistency` Check 5)
- Issue: `tasks_cancel_tag.get("type", "")` default empty;`startswith("")` 永远 True。upchain `_extract_followon_tracking_section` L1508 guard `if checked and tag_type:` 保证 resolved list 中 type 非空,所以 happy path 不触发。但 future caller 直接传 `{}` cancel_tag 会静默 pass。
- Recommendation: 在 docstring 明示 caller 约定 OR 加 `if not expected_reason_prefix: return ...` defensive guard
- **Disposition**: non-blocking advisory(upchain guard 在实际流程中有效);若 future P2.f 主流程暴露 caller 误用 → P2.f 时 inline fix

### F3 [P3 nitpick] `_git` helper 在 P2.b 段定义,non-top placement

- File: `tests/unit/test_forgeue_finish_gate.py:2767`
- Issue: `_git` test helper 定义在 P2.b section 开始处,非文件顶 module-level fixture 区。后续 P2.c+ 新增 git 测试看不到。
- Recommendation: 移至文件顶部 import 后 / module fixture 区。
- **Disposition**: non-blocking advisory;P2.c+ 时 reorganize

## Strengths(5 项)

1. subprocess 用法一致(`cwd=repo` + `check=False` + `capture_output=True` + `text=True`)
2. 5-point check 顺序合理(fail-fast 代价递增 — id O(1) → JSON parse O(n) → schema 集合运算 → str 比较)
3. JSON tolerant branch 设计正确(`isinstance(snapshot_raw, str)` ternary + `if not isinstance(snapshot, dict)` 二次守门)
4. 真实 git init 测试策略(避免 mock git 掩盖路径/格式问题;`tmp_path` 自动 cleanup)
5. `_diff_registry_entries` cancelled-* 前缀过滤明确边界(`active → inherited` 等非 cancelled-* 不误报,有独立测试)

## Independent verification

- 131 PASS in `pytest -q tests/unit/test_forgeue_finish_gate.py`(zero regression)
- subprocess 调用模式 + Check 5 edge case + Check 2 dict branch 实测验证

## Token usage

- input_tokens: ~37000;output_tokens: ~16000;total_tokens: 53146
- model: claude-sonnet-4-6;estimated_usd: $0.35
- data_source: estimated only, not gate-grade
- duration_ms: 267403;tool_uses: 22
