---
change_id: fix-finish-gate-archived-replay-compat
stage: S7
evidence_type: doc_sync_report
contract_refs:
  - openspec/changes/fix-finish-gate-archived-replay-compat/proposal.md#impact
  - openspec/changes/fix-finish-gate-archived-replay-compat/design.md#non-goals
  - CHANGELOG.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-doc-sync fix-finish-gate-archived-replay-compat
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
skill_cascade_audit:
  invoked_skills:
    - forgeue-doc-sync-gate
    - forgeue-integrated-change-workflow
  cascade_check_pass_at: 2026-05-07T08:30:00Z
task_granularity: phase
autonomy_decision: claude_autonomous
---

# Documentation Sync Gate Report — fix-finish-gate-archived-replay-compat (S6→S7)

## forgeue_doc_sync_check 静态扫描

`python tools/forgeue_doc_sync_check.py --change fix-finish-gate-archived-replay-compat`:

| Doc | Label | Reason | Apply |
|-----|-------|--------|-------|
| `openspec/specs/*` | REQUIRED(auto)| spec delta `examples-and-acceptance` archive 时 auto-merged at `/opsx:archive sync-specs` | N/A(自动 sync,P9 阶段)|
| `docs/requirements/SRS.md` | SKIP | 无 FR/NFR 需求改动;tools/forgeue_finish_gate.py 是 audit tool 不在 SRS scope | — |
| `docs/design/HLD.md` | SKIP | 无架构 / 子系统 / 协作改动 | — |
| `docs/design/LLD.md` | SKIP | 无 src/framework/core/ 字段 / 方法 / 算法改动 | — |
| `docs/testing/test_spec.md` | SKIP | finish_gate fence test 数变化是 forgeue tooling 内部增量,不在 549 主 test spec 索引 | — |
| `docs/acceptance/acceptance_report.md` | SKIP | 无 FR/NFR 验收状态变化 | — |
| `README.md` | OPTIONAL(no apply)| 无 user-facing 行为变化(纯 backward-compat regex 扩展 + per-format threshold + repo-relative path detection) | — |
| `CHANGELOG.md` | **REQUIRED → APPLIED** | commit-touching change;`[Unreleased]` Fixed 子段 +1 条记录两 bug 修复 + 4 D-decision + 2 codex review round + 2 follow-on backlog | ✅ applied |
| `CLAUDE.md` | OPTIONAL(no apply)| 无新工具 / 新协议 / 新 fence 引入(纯 backward-compat regex 扩展) | — |
| `AGENTS.md` | OPTIONAL(no apply)| 同 CLAUDE.md,无 agent 行为变化 | — |

## forgeue_enum_cross_ref_check

`python -m tools.forgeue_enum_cross_ref_check`:**0 drift**(canonical=8 / mapped=3 / doc-occurrences=6 / actionable warnings=4 全 pre-existing,non-blocking)。

## README §4.3 Agent Classification

### A. 必须更新(REQUIRED applied)

- **CHANGELOG.md** `[Unreleased]` Fixed 子段 +1 条:涵盖
  - 4 P2 edits to `tools/forgeue_finish_gate.py`(line 1390 / 1396 / 1407-1445 / 1586-1604)
  - closes 2 follow-on backlog(`fix-finish-gate-section-regex-for-p-prefixed` + `fix-openspec-validate-archived-change-support`)
  - L0 archived replay 31 → 1 + L1 全套 pytest 0 regression
  - 4 D-decision(round 1 codex 修订/新增)+ 2 codex review round + 2 follow-on backlog
  - 9 new unit fence test in `tests/unit/test_forgeue_finish_gate.py`

### B. 不需要更新

- `docs/requirements/SRS.md`:本 change 修复 audit tool 缺陷,无 FR/NFR 改动
- `docs/design/HLD.md`:无架构边界改动(finish_gate 不在 HLD §子系统层)
- `docs/design/LLD.md`:无 `src/framework/**` 字段 / 方法 / 算法改动
- `docs/testing/test_spec.md`:9 新 fence test 是 forgeue tooling 内部测试增量,不在 549 整体 test spec 索引
- `docs/acceptance/acceptance_report.md`:无 FR/NFR 验收状态变化(不动 acceptance matrix)
- `README.md`:无 user-facing CLI / 行为变化(本 change 是 internal audit tool fix)
- `CLAUDE.md`:无新工具引入(`forgeue_finish_gate.py` 行为 backward-compat 扩展)+ 无新工作流协议(无 D-decision 进入 protocol 层 enum)
- `AGENTS.md`:同 CLAUDE.md

### C. doc drift

无。codex review round 1 + S5 verification round 1 暴露的 2 finding 全 out-of-scope follow-on(F1 retire-parallel-and-worktree-fully `b593b20` 引入 / F2 fuse-openspec-superpowers-workflow `37288fe7` 引入),不在本 change scope。

### D. 建议 patch

CHANGELOG.md `[Unreleased]` Fixed 子段(已 applied)。

## Followup tracking

延续 retire-parallel-and-worktree-fully P5 已 tracked 的 2 follow-on(`fix-finish-gate-section-regex-for-p-prefixed` / `fix-openspec-validate-archived-change-support`)— **本 change 已 close 这 2 个**。

S5 codex `/codex:review --base main` round 1 暴露 2 个新 follow-on backlog(out-of-scope,沿 retire 同款"out-of-retire-scope follow-on"模式):
1. `fix-runtime-enforcement-protocol-version-explicit-null-bypass`(F1 [P1] retire-parallel `b593b20` 引入)
2. `fix-codex-review-stage-flag-strip`(F2 [P2] fuse-openspec `37288fe7` 引入)

## 进入 S8 准入条件

- [x] forgeue_doc_sync_check 静态扫 [REQUIRED] CHANGELOG.md applied
- [x] forgeue_enum_cross_ref_check 0 drift
- [x] README §4.3 Agent Classification A/B/C/D 完整
- [x] 10 文档分类决策 + reason 全记录
- [x] DRIFT 0(post-apply,commit 后)
- [x] doc_sync_report.md 12-key audit frontmatter 全合规

可进入 S8(Finish Gate)。
