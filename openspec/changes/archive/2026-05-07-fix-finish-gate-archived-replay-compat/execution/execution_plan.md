---
change_id: fix-finish-gate-archived-replay-compat
stage: S2
evidence_type: execution_plan
contract_refs:
  - openspec/changes/fix-finish-gate-archived-replay-compat/design.md#decisions
  - openspec/changes/fix-finish-gate-archived-replay-compat/specs/examples-and-acceptance/spec.md
  - openspec/changes/fix-finish-gate-archived-replay-compat/tasks.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-plan fix-finish-gate-archived-replay-compat
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-plan
skill_cascade_audit:
  invoked_skills:
    - superpowers:brainstorming
    - superpowers:writing-plans
  cascade_check_pass_at: 2026-05-06T00:00:00Z
task_granularity: phase
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_plan_review.md
---

# Implementation Plan — fix-finish-gate-archived-replay-compat

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Per micro_task,fresh subagent receives the full prompt text from `micro_tasks.md`(沿 ForgeUE Integrated Workflow `change-apply-subagent` task input protocol,subagent 不被授权读 plan files,仅接收主 session 提取后完整 prompt 文本)。

**Goal**:修复 `tools/forgeue_finish_gate.py` 在对 archived 历史 change 做 `D-ArchivedReplayCompat` 二次 replay 时的两类 spurious blocker(25 `tasks_unchecked` + 4 `openspec_validate_failed`),让 archived 4 change replay baseline 从 29 → 0 噪声 blocker。

**Architecture**:单文件改动 `tools/forgeue_finish_gate.py`(2 micro 修改:regex 1 行扩展 + `build_report` 内加 archive segment 检测分流 skip openspec validate);测试守门 `tests/unit/test_forgeue_finish_gate.py`(7 新 case 覆盖 backward-compat / archived 双格式 / 假阴性边界 / Path.parts 检测稳定性)。两改动遵循 design.md 3 D-decision(`D-RegexExtension` / `D-OpenSpecValidateArchiveSkip` / `D-DispatchPathDetection`)。

**Tech Stack**:Python 3.12+ stdlib only(`re` / `pathlib` / `subprocess`);pytest 测试 framework;ForgeUE 项目内部 `tools/_common.py` helper(已有);**不引入**新 dependency。

---

## File Structure

| File | Action | Responsibility | LoC |
|------|--------|----------------|-----|
| `tools/forgeue_finish_gate.py` | Modify | (a) 扩展 `_SECTION_HEADING_RE` regex 双 capture group(P-prefix optional + integer)+ (b) `_check_tasks_unchecked` 选 per-format threshold(active ≥9 / archived ≥10)+ (c) `build_report` 加 `change_dir.is_relative_to(_common.archive_dir(repo))` repo-relative 检测分流 skip `run_openspec_validate`(round 1 codex F1+F2 inline writeback 修订) | ~25 改动 |
| `tests/unit/test_forgeue_finish_gate.py` | Modify | 加 9 个新 test case(原 7 + round 1 F1 加 1 + F2 加 1 + F3 改造 1)守门 backward-compat / archived 格式 / 假阴性边界 / `is_relative_to` 稳定性 / repo 父目录 segment 不 false-positive / archived P9 prereq block / monkeypatch invocation count | ~250 新增 |
| `CHANGELOG.md` | Modify | `[Unreleased]` Fixed 子段 +1 条 | ~5 行 |

**关键 file/line refs**(implementer 必须知道,round 1 codex F1+F2 inline writeback 后):

- `tools/forgeue_finish_gate.py:1385` — `_SECTION_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)` 单行 regex 改 `r"^##\s+(P)?(\d+)(?:\.|\s+—)\s+"`(双 capture group 暴露 P-prefix)
- `tools/forgeue_finish_gate.py:1383` 周边 — 加新常量 `_SELF_STAGE_SECTION_THRESHOLD_ARCHIVED = 10`(archived ≥10,沿 D-PerFormatThreshold)
- `tools/forgeue_finish_gate.py:1388-1426` — `check_tasks_unchecked` 函数体改:section_match.group(2) 抽 integer + group(1) 决定 per-format threshold;详见 `micro_tasks.md` task_p2 Step 1 完整代码
- `tools/forgeue_finish_gate.py:1451-1487` — `run_openspec_validate(repo, change_id)` 函数体不动(职责仅 invoke openspec CLI)
- `tools/forgeue_finish_gate.py:1567-1570` — `build_report` 内 openspec validate 调用点;改用 `change_dir.is_relative_to(_common.archive_dir(repo))` repo-relative 检测分流 skip(round 1 codex F1 inline writeback 修订;旧 `"archive" in change_dir.parts` 在 repo 父目录名含 `archive` 时 false-positive)
- `tools/_common.py:466-467` — `archive_dir(repo) = repo / "openspec" / "changes" / "archive"`(implementer 不改此文件,仅用 helper)
- `tests/unit/test_forgeue_finish_gate.py:822-893` — 既有 `test_finish_gate_skips_p8_p9_self_stage_unchecked` + `test_finish_gate_does_not_skip_pre_p8_unchecked` 是 backward-compat 守门 baseline,**不动**

## Contract refs

design.md 4 D-decision(round 1 codex F1+F2 inline writeback 后)是实施依据:

- **D-RegexExtension**(round 1 修订):`r"^##\s+(P)?(\d+)(?:\.|\s+—)\s+"` 单 regex + **双 capture group**;group(1) = `"P"` or `None`(选 per-format threshold)/ group(2) = section integer。
- **D-PerFormatThreshold**(round 1 新增):active 格式 ≥9(`_SELF_STAGE_SECTION_THRESHOLD = 9`)/ archived 格式 ≥10(`_SELF_STAGE_SECTION_THRESHOLD_ARCHIVED = 10`);避免 archived P9 ambiguous 项静默 skip。
- **D-OpenSpecValidateArchiveSkip**:archive/ 路径下 skip subprocess + 写 rationale `openspec_validate_skipped: archive_path_unsupported_by_upstream_cli` 到 finish_gate report warning 字段(**不**生成 BLOCKER);active 路径行为 unchanged。
- **D-DispatchPathDetection**(round 1 修订):`change_dir.is_relative_to(_common.archive_dir(repo))` repo-relative + segment-precise 检测,**不**用 `"archive" in Path(change_dir).parts`(round 1 F1 实证不安全:repo 父目录名含 `archive` segment 时 active change 被误判 archived)。

specs.md 11 scenario(round 1 codex F1+F2+F3 inline writeback 加 4 new + 改造 2)是 spec compliance 真源(spec reviewer subagent 必检):

- Scenario 1:active `## <int>. <text>` 格式仍命中(backward-compat)
- Scenario 2:archived `## P<N> — <text>` 格式命中(本 change 新增,含 P10/P11 self-stage skip)
- Scenario 3:假阴性 `## 1.5 sub-section` 不命中
- Scenario 4:假阴性 `## PX — title` 不命中
- Scenario 5:active change openspec validate 仍 invoke(monkeypatch + count == 1)
- Scenario 6:archived change openspec validate skip(monkeypatch + count == 0,round 1 F3 改造)
- Scenario 7:`is_relative_to` 检测稳定性 — active 名含 `archive` 子串(`add-archive-feature`)不 false-positive
- Scenario 8(round 1 F2 新加):archived `## P9 — Documentation Sync Gate` workflow prerequisite 应 block(archived ≥10 threshold → P9 < 10 fail-loud)
- Scenario 9(round 1 F1 新加):repo 父目录路径含 `archive` segment(`tmp_path / "archive" / "repo"`)不 false-positive,active change 仍 invoke openspec validate
- Scenario 10:archived `## P10 — Finish Gate` / `## P11 — Archive` self-stage 应 skip(archived ≥10 threshold)
- Scenario 11(round 1 F3 强化):monkeypatch invocation count + 拒绝任何 validate-related blocker type(`openspec_validate_failed` / `openspec_cli_missing` / `openspec_validate_error`)

## Phase 总览

| Phase | tasks.md# | micro_task ID | 目标 | TDD 阶段 |
|-------|-----------|---------------|------|---------|
| P0 | 1.1-1.4 | task_p0_baseline | 跑 finish_gate replay archived 4 change 记 baseline blocker 数 + 写 verification/baseline.md | — |
| P1 | 2.1-2.7 | task_p1_tdd_red | 在 test 文件加 9 case(原 7 + round 1 F1 加 1 + F2 加 1 + F3 改造 1) + 跑 pytest 确认全 fail | red |
| P2 | 3.1-3.4 | task_p2_tdd_green | regex 改双 capture group + per-format threshold + `is_relative_to` 检测分流 + 跑 pytest 确认 9 case 全绿 + 全套不 regression | green |
| P3 | 4.1-4.4 | task_p3_verify | L0 archived replay 实测 29 → 0 + L1 全套 pytest + 写 verification/verify_report.md | verify |

P4-P9 是后置 review / doc-sync / finish-gate / archive,不在 implementer subagent dispatch scope(由主 session 推进)。

## Boundary

**In-scope**(本 plan 列出 modules):
- `tools/forgeue_finish_gate.py`
- `tests/unit/test_forgeue_finish_gate.py`
- `CHANGELOG.md`(P6 doc-sync 阶段;不在 implementer dispatch 内)

**Out-of-scope**(implementer 不得动):
- `tools/forgeue_change_state.py` / 其他 tools/* 文件
- `src/framework/**`(framework runtime,无关本 fix)
- `docs/` 五件套(SRS / HLD / LLD / test_spec / acceptance_report)— design.md Non-Goals 显式排除
- `openspec/specs/examples-and-acceptance/spec.md`(active baseline,本 change spec delta 是 added requirements 不是 modified)
- 其他 active change(无 cross-change 影响)

## Testing strategy

- **TDD red-green-commit**:每 micro_task 先写测试 fail,再 minimal implementation,再绿,再 commit(沿 ForgeUE memory `feedback_dont_punt_executable_tasks` + 工程化纪律)
- **Backward-compat 守门**:既有 2 case 必绿(`test_finish_gate_skips_p8_p9_self_stage_unchecked` + `test_finish_gate_does_not_skip_pre_p8_unchecked`)
- **L0 实测**:跑 finish_gate replay archived 4 change 实测 blocker 数(verification/baseline.md → verification/verify_report.md 对账)
- **L1 全套**:`python -m pytest -q` 1746 (retire P5 baseline) + 7 新 = 1753 必绿,无 regression
- **不需要 L2**(无 live LLM / 无 ComfyUI smoke / 无 vendor API paid call)

## 提交节奏

每 micro_task 完成后 commit 一次(沿 Frequent commits + Bite-sized task granularity):

- P0:`feat(forgeue): fix-finish-gate-archived-replay-compat P0 — baseline 29 blocker recorded`
- P1:`test(forgeue): fix-finish-gate-archived-replay-compat P1 — 7 TDD red cases added`
- P2:`feat(forgeue): fix-finish-gate-archived-replay-compat P2 — regex extension + archive validate skip(green)`
- P3:`test(forgeue): fix-finish-gate-archived-replay-compat P3 — verify L0 archived replay 29→0 + L1 1753 PASS`

每次 commit 由 controller(主 session)请示用户授权(沿 user feedback `Push requires explicit per-commit auth`,虽然这是 commit 不是 push,但 commit 也走默认请示路径,沿 ForgeUE Integrated Workflow protocol 的 autonomy boundary fence #1 不可逆 / `claude_autonomous` 自主路径模糊地带的保守做法)。
