---
change_id: retire-parallel-and-worktree-fully
stage: S4
evidence_type: p3_pytest_summary
contract_refs:
  - tasks.md#4
  - design.md#decisions
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-apply-direct retire-parallel-and-worktree-fully
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_adversarial_review_review_round1.md
runtime_enforcement_protocol_version: v1
created_at: 2026-05-06T13:00:00Z
---

# P3 pytest summary — retire-parallel-and-worktree-fully

## P3 file/dir deletions(USER executed)

| Path | LOC | Type |
|------|-----|------|
| `tools/forgeue_preflight_wrapper.py` | 615 | W1 wrapper |
| `tools/forgeue_dispatch_ledger.py` | 353 | W3 ledger CLI |
| `tools/_forgeue_ledger_crypto.py` | 507 | ledger-binding internal helper |
| `.claude/commands/forgeue/change-apply-parallel.md` | 433 | parallel command template |
| `tests/unit/test_dispatch_ledger.py` | 1021 | W3 + ledger-binding 测试 |
| `tests/unit/test_preflight_wrapper.py` | 902 | W1 wrapper 测试 |
| `tests/integration/test_v2_e2e_synthetic_change.py` | 1235 | v2 e2e fixture(100% v2/v3 case;沿 P0 实测) |
| **总** | **5066** | 7 file deletions |

**Sister skill SKIP**(沿 D-SisterSkillRewrite P3 writeback,user push back 修正前判断"功能和 worktree 还有 parallel 没关系吧";改 P4 inside-file rewrite)。

## P3 inside-file edits(Claude executed,沿 actor split)

P3 file deletions 暴露下游 test 文件 stale references → 同 P3 阶段 inside-file edit 处理(file 内容 retire-related 删除 = Claude 范围):

### `tests/unit/test_forgeue_command_markdown.py`(697 → 272 LOC,-425)

- 修正 fixture `cmd_files` 命令矩阵 10 → 9(parallel.md 已删)
- 修正 `_APPLY_CMD_NAMES` tuple 移除 `change-apply-parallel.md`
- 删除 `_APPLY_CMD_WITH_WORKTREE` constant(retire 后无 worktree-required cmd)
- 删除 17 个 retire-related 测试函数:
  - `test_subagent_parallel_have_preflight_worktree_section`
  - `test_change_apply_direct_does_not_have_preflight_worktree_section`
  - `test_change_apply_parallel_command_exists`
  - `test_change_apply_subagent_invokes_preflight_wrapper`
  - `test_change_apply_parallel_invokes_preflight_wrapper`
  - `test_change_apply_subagent_invokes_dispatch_ledger_append`
  - `test_change_apply_parallel_invokes_dispatch_ledger_append`
  - `test_change_apply_subagent_protocol_version_v2_in_evidence_template`
  - `test_change_apply_parallel_protocol_version_v2_in_evidence_template`
  - `test_change_apply_ledger_append_after_skill_task_dispatch`
  - `test_change_apply_parallel_actual_diff_uses_git_status_porcelain_and_ls_files_others`
  - `test_apply_subagent_parallel_invoke_subagent_discipline_skill`
  - `test_apply_subagent_parallel_must_invoke_skill_using_git_worktrees`
  - `test_apply_subagent_parallel_preflight_outcome_capture_field`
  - `test_apply_parallel_decline_auto_fallback_sequential_narrative`
  - `test_preflight_worktree_section_bodies_identical`
  - `test_apply_subagent_parallel_steps_branch_by_outcome_mode`

### `tests/unit/test_forgeue_workflow_no_paid_default.py`

- 修正 fixture `cmd_files` 命令矩阵 10 → 9 + 注释更新

### `tests/unit/test_forgeue_workflow_plugin_invocation.py`

- 修正 fixture `cmd_files` 命令矩阵 10 → 9 + 注释更新
- 修正 `test_expected_active_commands_present` `expected` set 移除 `change-apply-parallel`

## Pytest result

```bash
python -m pytest -q 2>&1 | tail -5
```

```
1576 passed, 1 failed, 1 skipped in 69.54s (0:01:09)
```

### Pass/fail breakdown

| Phase | Passed | Failed | Net change vs prev |
|-------|--------|--------|---|
| P0 baseline(整 collect) | 1746 | — | — |
| P1 commit | 1674 | 1(pre-existing) | -72 |
| P2 commit | 1669 | 6(4 v2/v3 e2e + 1 enum_cross_ref + 1 pre-existing) | -5 |
| P3 commit(本) | **1576** | **1(pre-existing only)** | **-93;5 P2 fail 全消失(v2/v3 e2e 整文件 git rm + enum_cross_ref P2 已修 + 命令模板测试 inline edit 修复)** |

**Final fail**:`tests/unit/test_forgeue_cross_check_format.py::test_real_cross_check_files_have_evidence_type` — pre-existing fail(P0 baseline 之前就有;archived ledger-binding `review_cross_check.md` `evidence_type: review_cross_check` 不在 test 允许 enum 内)。**非 P3 引入**。

### Pytest collect tally

```bash
python -m pytest --collect-only -q 2>&1 | tail -3
```

预期(基线对账):
- P0 baseline collect:**1746**
- P1 删除测试 case:~70(从 P1 collect 1746 → 1676)
- P3 删除测试 case:**~98**(test_dispatch_ledger 47 case + test_preflight_wrapper ~46 case + test_v2_e2e ~16 case + test_forgeue_command_markdown 17 retire test)
- 总删除:~168
- 期望最终 collect:1746 - 168 = **~1578**(实测 1576 + 1 fail = 1577,差 1 个 case 在精度范围内 acceptable)

## Grep audit retire 关键字

```bash
grep -rnE 'forgeue_preflight_wrapper|forgeue_dispatch_ledger|_forgeue_ledger_crypto|change-apply-parallel|ledger_forgery_resistance|ledger_line_count|ledger_final_hmac|HMAC.*chain' src/ tools/ tests/ 2>&1 | grep -v __pycache__ | head -10
```

期望:仅 P4 待编辑文件残留(`tests/unit/test_forgeue_command_markdown.py` 已 P3 inline edit 清完;`tests/unit/test_forgeue_workflow_plugin_invocation.py` `change-apply-parallel` 已删 in expected set;active source 全清)。

实测残留:仅 `__pycache__/*.pyc` 字节码(build artifact;`python -B` 或 `find -name '*.pyc' -delete` 自然清理,**非 retire scope 问题**)。

## 进入 P4 准入条件

- [x] 7 file deletions 完成(user executed)
- [x] 3 test files inside-file edit 修复 fixture / constants / retire-related tests(Claude executed)
- [x] import smoke pass(`python -c "from tools import forgeue_finish_gate, forgeue_change_state; print('ok')"`)
- [x] pytest 全跑无新引入 fail(1576 passed,仅 1 pre-existing)
- [x] retire 关键字 grep audit 全清(active code,允许 archived narrative + .pyc 字节码)
- [ ] P4 阶段处理:命令模板 5 文件 inside-file edit + backbone skill rewrite + sister skill rewrite

## Followup

- `*.pyc` 字节码残留(`tools/__pycache__/forgeue_dispatch_ledger.cpython-313.pyc` 等)— Python 自动清理(import 时检测源文件不存在);user 可选 `find . -name '*.pyc' -delete` 主动清。
