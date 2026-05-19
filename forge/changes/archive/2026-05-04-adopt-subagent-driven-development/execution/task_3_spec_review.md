---
change_id: adopt-subagent-driven-development
stage: S4
evidence_type: subagent_spec_review
contract_refs:
  - tasks.md#5.1
  - tasks.md#5.2
  - tasks.md#5.3
  - tasks.md#5.4
  - tasks.md#5.5
  - tasks.md#5.6
  - design.md#D-EvidenceSchema
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: forced (Pre-P0 dogfood manual dispatch round 1)
codex_plugin_available: true
triggered_by_command: change-apply-subagent
---

# Task 3 Spec Compliance Review (Round 1 — ✅ Spec compliant)

## Status: ✅ Spec compliant

## Verification method (independent)

- `git show --stat 3498e91` + `git diff 3498e91^ 3498e91` 全文 diff
- Read `tools/forgeue_finish_gate.py:55-347` 确认 enum + path mapping + dispatch detection
- Grep `_VALID_EVIDENCE_TYPES|subagent_*` on finish_gate.py
- `python -m pytest tests/unit/test_forgeue_finish_gate.py -q` → 62 PASS
- `python -m pytest tests/unit/test_forgeue_change_state.py -q` → 40 PASS
- `python -m pytest -q` 全量 → 1410 passed, 1 skipped, 16 errors
- 单跑 3 个 erroring 测试文件 → 3 passed, 16 errors(隔离归属)
- `git log --oneline ...` 确认最近触碰来自 `cb445c0` / `af2892a`(task 2)
- `python -m pytest --collect-only -q` → 1427 tests(1410 + 1 + 16 = 1427 ✓)

## §5.1-§5.6 verification — 6/6 ✅

- **§5.1 enum 4 项 add** ✅ `tools/forgeue_finish_gate.py:89-94`(实装常量名 `_REQUIRED_EVIDENCE_SUBAGENT` list of `(evidence_type, default_path)` tuple,合二为一是 codebase 既有 idiom,见 `_REQUIRED_EVIDENCE_BASE` line 65 / `_REQUIRED_EVIDENCE_CLAUDE_PLUGIN` line 74 同款)。4 个新 evidence_type 全部存在
- **§5.2 path mapping 4 项** ✅ 同上 line 90-93,glob 路径与规范字面一致
- **§5.3 dispatch from frontmatter** ✅ `forgeue_finish_gate.py:267-297` `_detect_subagent_dispatch_mode` 扫 formal subdirs frontmatter `triggered_by_command: change-apply-subagent`;line 327 `if _detect_subagent_dispatch_mode(change_dir): required.extend(_REQUIRED_EVIDENCE_SUBAGENT)`。**未**依赖 `notes/pre_p0/dispatch_mode.txt` marker(全文 grep 无引用)。F2 修复符合
- **§5.4 fence cases** ✅ 6 case 全在 `tests/unit/test_forgeue_finish_gate.py:1289-1592`:
  1. `test_subagent_evidence_types_pass_frontmatter_validation`(4 类校验通过)
  2. `test_subagent_dispatch_mode_required_evidence_missing_blocks`(F2 缺失 → exit 2)
  3. `test_direct_dispatch_mode_does_not_require_subagent_evidence`(direct path)
  4. `test_subagent_dispatch_mode_other_value_does_not_trigger_required`(reinforcement)
  5. `test_subagent_full_quad_satisfies_dispatch_mode`(reinforcement)
  6. `test_worktree_isolation_requires_committed_change_artifacts`(F1 真实 `git worktree add` 隔离 fence)
- **§5.5 DRIFT detector enum** ✅ `tools/forgeue_change_state.py:369-383` `detect_drift_contra` allow-list 扩 4 项;line 396-419 `detect_drift_gap` 同款扩 4 项。detector 内部逻辑未动
- **§5.6 fence cases** ✅ 5 case 在 `tests/unit/test_forgeue_change_state.py:577-772`:
  1. `test_subagent_implementer_def_outside_design_triggers_drift_contra`
  2. `test_subagent_spec_review_failure_keyword_triggers_drift_gap`
  3. `test_subagent_code_quality_review_critical_failure_mode_triggers_drift_gap`
  4. `test_subagent_final_review_def_outside_design_triggers_drift_contra`(reinforcement)
  5. `test_subagent_drift_cli_exits_5`(CLI 集成)

## 16 errors归属 verification: ✅ task 2 scope (implementer claim verified)

- 16 errors 全部来自 3 个 fixture 文件:
  - `test_forgeue_command_markdown.py`(8 errors)
  - `test_forgeue_workflow_no_paid_default.py`(3 errors)
  - `test_forgeue_workflow_plugin_invocation.py`(5 errors)
- 关键错误证据:`test_forgeue_workflow_plugin_invocation.py:22 AssertionError: expected exactly 8 forgeue command files, found 10`
- 实际目录有 10 个 command:`change-apply.md` + `change-apply-direct.md`(commit `af2892a` 引入)+ `change-apply-subagent.md`(commit `af2892a` 引入)+ 7 个原 command
- 这 3 个 erroring 测试文件的最近触碰提交是 `cb445c0` 和 `af2892a`(task 2),task 3 commit `3498e91` 完全没碰它们
- 单独跑 3 个测试文件:3 passed, 16 errors,与全量结果一致 → errors 确实独立于 task 3

## Scope compliance: ✅

`git diff --name-only` 严格 4 行:两个 tools + 两个 tests。

## Discipline: ✅ no existing logic modified

- finish_gate.py 修改全是新增(`_REQUIRED_EVIDENCE_SUBAGENT` / dispatch detection 常量 / `_detect_subagent_dispatch_mode` 函数 / 2 行 required.extend 调用),不动 `_REQUIRED_EVIDENCE_BASE` / `_REQUIRED_EVIDENCE_CLAUDE_PLUGIN` / `_validate_evidence_file` / `check_evidence_completeness` 处理流程
- change_state.py 删除的两行(`if ev_type not in (...): continue` 和 `if fm.get("evidence_type") not in (...): continue`)纯粹为了**扩展 tuple**,detector 算法主体(正则、关键词比对、DriftRecord 构造)完全未动 — 严格符合"只扩 allow-list"

## Findings

无问题。

## Important note: 16 errors task 2 deferred regression

虽然 task 3 自身 ✅ Spec compliant 且 not introduce new errors,**但 16 errors 是 outstanding deferred regression**(task 2 dogfood loop 漏抓的 fence count fixture 硬编码 8 vs 实际 10)。

**Lessons learned for dogfood protocol**:reviewer 应该在 spec_review / code_quality_review 阶段跑全量 pytest 而非仅相关测试,否则会漏抓 cross-file regression。本 task 3 spec_review 抓到了,但 task 2 reviewer 当时没跑全量 — 这是 dogfood protocol 的一个 systematic gap,值得 follow-on.

**16 errors 处理建议**:
- (a) Controller direct fix(简单 sed `8` → `10` 在 3 个 fixture 文件;outside §5 scope 但与 task 2 紧耦合)
- (b) 加 task §5.7 显式修 fence count(写回 tasks.md drift_decision pending)
- (c) Defer 到独立 follow-on(单独 commit 修)

Code quality reviewer 应给出最优处理路径建议。

## Token usage

- input_tokens: ~58,000
- output_tokens: ~3,500
- model: claude-opus-4-7[1m]
- estimated_usd: ~$1.13(Opus 4.7 1M tier:input $15/M + output $75/M)
- data_source: manual_estimate, not gate-grade

## Recommendation

✅ **Proceed to code quality review**

Implementer 严格按照 §5.1-§5.6 规范实施,无 scope creep,无 discipline 违规。16 errors 归属 task 2 commit 的 claim **独立验证通过**(根因是命令文件 fixture 硬编码 8 vs 实际 10)。可进入 code quality reviewer 阶段。
