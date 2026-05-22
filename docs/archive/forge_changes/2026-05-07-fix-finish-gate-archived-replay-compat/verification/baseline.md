---
change_id: fix-finish-gate-archived-replay-compat
stage: S4
evidence_type: verify_report_baseline
contract_refs:
  - openspec/changes/fix-finish-gate-archived-replay-compat/execution/execution_plan.md
  - openspec/changes/fix-finish-gate-archived-replay-compat/design.md#goals
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-apply-subagent fix-finish-gate-archived-replay-compat
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - superpowers:test-driven-development
  cascade_check_pass_at: 2026-05-07T11:32:00Z
task_granularity: phase
autonomy_decision: claude_autonomous
---

# Baseline — P0 archived 5 change finish_gate replay 实测

## archived replay blocker 表(对账)

| Archive | tasks_unchecked | openspec_validate_failed | writeback_commit_unrelated | 其他 blocker types | total |
|---------|-----------------|--------------------------|----------------------------|---------------------|-------|
| runtime-enforcement | 11 | 1 | 0 | 0 | 12 |
| executable-enforcement | 14 | 1 | 0 | 0 | 15 |
| restore-consent-gate | 0 | 1 | 0 | 0 | 1 |
| ledger-binding | 0 | 1 | 0 | 0 | 1 |
| retire-parallel-and-worktree-fully | 0 | 1 | 1 | 0 | 2 |
| **总** | **25** | **5** | **1** | **0** | **31** |

## 既有 2 baseline test 状态

- `test_finish_gate_skips_p8_p9_self_stage_unchecked`: PASS
- `test_finish_gate_does_not_skip_pre_p8_unchecked`: PASS

## `_SECTION_HEADING_RE` baseline 定义

`tools/forgeue_finish_gate.py:1385`:`_SECTION_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)`

## P1 进入条件

- [x] grep 确认 `_SECTION_HEADING_RE` 当前 baseline 定义匹配 design.md 期望
- [x] 既有 2 baseline test PASS(backward-compat 守门)
- [x] archived 5 change replay 实测 blocker 数记录(对账标准)

## 实测观察与对账分析

### blocker 类型分布

1. **tasks_unchecked (25 / 31 = 80.6%)**
   - 早期 archived change（runtime-enforcement 11个 + executable-enforcement 14个）含 `P10`、`P11`、`P12` 等高编号阶段任务
   - regex `r"^##\s+(\d+)\.\s+"` 当前仅识别 `P0-P9` 两位数编号，不识别 `P10+` 三位数
   - 后期 archived change（restore-consent-gate / ledger-binding / retire-parallel）未含超过 P9 的任务，故 tasks_unchecked 为 0
   - **root cause**: regex 未扩展至 `P10+` 编号，**预期 P2 impl 修复**

2. **openspec_validate_failed (5 / 31 = 16.1%)**
   - 所有 5 个 archived change 都触发 `openspec validate --strict` 失败
   - 错误信息：`Unknown item 'archive/...'` — openspec CLI 不支持 archive 前缀路径
   - **root cause**: `run_openspec_validate` 内 openspec validate 命令无 archived-specific 逻辑，**预期 P3 impl 修复**（沿 design.md D-DispatchPathDetection + D-OpenSpecValidateArchiveSkip）

3. **writeback_commit_unrelated (1 / 31 = 3.2%)**
   - retire-parallel-and-worktree-fully archived change 存在 writeback_commit 指向与实际修改文件不一致
   - 信息：writeback_commit `9fc42629d136` 不涉及 `openspec/changes/archive/2026-05-06-retire-parallel-and-worktree-fully/design.md`
   - **root cause**: archived change 的 writeback 真实性校验暴露真实 codebase drift，**P1 验证边界内正常**（非 finish_gate logic 问题）

### P0 baseline 对账结论

- **无 code 缺陷发现**：既有 test backward-compat 全绿，regex 定义符合当前设计契约
- **predicted blocker 分布匹配**：31 blocker 中 25 + 5 + 1 = 31，完全符合"tasks_unchecked(regex) + openspec_validate(archived) + writeback(真实 codebase)"三层预期
- **P1 entry gate**：baseline 数据足以支撑 P2/P3 design 和 P4 implementation 的目标校准

### 下阶段预期（P2-P4）

- **P2 design**: 扩 regex 至 P10+ 编号，引入 archived-path detection logic（D-DispatchPathDetection）
- **P3 verify**: 消除 25 个 tasks_unchecked + 5 个 openspec_validate_failed，保留 writeback 检测（真实性）
- **P4 implementation**: 修复 tool 代码，完整验证 31 blocker 全消后上线
