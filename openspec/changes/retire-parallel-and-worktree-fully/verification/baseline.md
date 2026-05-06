---
change_id: retire-parallel-and-worktree-fully
stage: S3
evidence_type: baseline
contract_refs:
  - tasks.md#1.1
  - tasks.md#1.2
  - design.md#decisions
aligned_with_contract: false
drift_decision: written-back-to-design
writeback_commit: 9fc4262
drift_reason: "P0.1.2 archived 4 change finish_gate replay 全 FAIL(blockers 29 个);D-ArchivedReplayCompat 原 PASS 期望与实测矛盾,根因是 finish_gate `_SECTION_HEADING_RE` regex 不匹配 `## P<N>` 格式(pre-existing bug 自 a4334db 起),archived 历史 evidence 内 `## P10` / `## P11` 被解析为 < threshold 触发 tasks_unchecked"
detected_env: claude-code
triggered_by: /forgeue:change-apply-direct retire-parallel-and-worktree-fully
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: notes/codex_adversarial_review_review_round1.md
runtime_enforcement_protocol_version: v1
created_at: 2026-05-06T11:00:00Z
---

# Baseline — retire-parallel-and-worktree-fully P0

## P0.1.1 pytest baseline

```bash
$ python -m pytest -q --collect-only 2>&1 | tail -3
tests/unit/test_visual_review_image_compress.py::test_attach_visual_payload_under_provider_limit_for_three_candidates

1746 tests collected in 0.51s
```

**Baseline pytest collected**:`1746`(实测 2026-05-06,本 change S3→S4 transition 时刻)

注:CLAUDE.md 历史记载 549 baseline 是早期 framework runtime 测试 + audit fence 子集;1746 是当前完整 test suite。本 change 期望删除 ~30-50 case → P3 / P5 实测期望 `1746 - <deleted> = <expected>`。

## P0.1.2 git HEAD SHA

```bash
$ git rev-parse HEAD
9f0a2a0a104b9eea86b0f875f1d088593ed797e8
```

**Baseline HEAD**:`9f0a2a0`(本 change S3→S4 transition 决定 commit;sequence:875e801 scaffold + S2→S3 → 60ae6e2 SHA backfill → a6cf7b4 subagent 推荐修正 → 9f0a2a0 direct path 决定)

## P0.2.0 archive 目录前置校验(沿 codex round 1 F2 inline writeback)

```bash
$ ls openspec/changes/archive/ | grep -E "runtime-enforcement|executable-enforcement|consent-gate|ledger-binding"
2026-05-05-enhance-workflow-automation-executable-enforcement
2026-05-05-enhance-workflow-automation-runtime-enforcement
2026-05-06-enhance-workflow-automation-ledger-binding
2026-05-06-restore-superpowers-worktree-consent-gate
```

**4 archive 目录全在**(verified)。

## P0.2.1 archived 4 change finish_gate replay status

⚠️ **CRITICAL FINDING**:4 archive 全 FAIL(non-pass);**D-ArchivedReplayCompat 原"PASS"期望与实测矛盾**,需要 writeback design.md 修正 criterion。

### 实测 blocker 分布

| Archive | tasks_unchecked | openspec_validate_failed | round_fix_continuity_v2 | dispatch_ledger_violation | 总 blocker | all_checks_passed |
|---------|---|---|---|---|---|---|
| 2026-05-05-enhance-workflow-automation-runtime-enforcement | 11 | 1 | 0 | 0 | 12 | None(False) |
| 2026-05-05-enhance-workflow-automation-executable-enforcement | 14 | 1 | 0 | 0 | 15 | None(False) |
| 2026-05-06-restore-superpowers-worktree-consent-gate | 0 | 1 | 1 | 1 | 3 | None(False) |
| 2026-05-06-enhance-workflow-automation-ledger-binding | 0 | 1 | 0 | 0 | 1 | None(False) |
| **总计** | **25** | **4** | **1** | **1** | **31** | — |

### Root cause 分析

**(1) `tasks_unchecked` 25 个 — pre-existing finish_gate regex bug**:

`tools/forgeue_finish_gate.py:2535` 内 `_SECTION_HEADING_RE` 定义为 `re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)` — **仅匹配 `## <int>. ` 格式,不匹配 `## P<N> — ` 格式**(P-prefixed + em-dash separator)。

archived runtime-enforcement / executable-enforcement 的 tasks.md 用 `## P10 — Archive` / `## P11 — 后置(可选)` section 命名 → regex 不命中 → `current_section` 残留为前个匹配 section 编号(< `_SELF_STAGE_SECTION_THRESHOLD = 9` 阈值)→ P10/P11 内 unchecked 项被误报为 blocker。

**实际 archived 状态**:P10 是已执行的 archive operation(checkbox 没人来 marked);P11 是 "follow-on tracking" 前向引用 entries(本来就不该 check off,是 backlog)。

**Bug 来源**:commit `a4334db` "P8 finish gate landed for fuse-openspec-superpowers-workflow" 起就有此 regex,**所有** archived ForgeUE change replay 都受影响,**非本 change 引入**。

**修复 scope**:**不在本 change scope**(本 change 是 retire ADR-011/012/013 + ledger-binding,不修无关 bug);留 follow-on `fix-finish-gate-section-regex-for-p-prefixed`。

**(2) `openspec_validate_failed` 4 个 — pre-existing tool limitation**:

```bash
$ openspec validate enhance-workflow-automation-runtime-enforcement --strict
Unknown item 'enhance-workflow-automation-runtime-enforcement'
Did you mean: ...
```

`openspec validate` CLI 仅支持 active change(`openspec/changes/<id>/`)+ active capability spec(`openspec/specs/<id>/`)— **不识别 archived change id**(`openspec/changes/archive/<*>/`)。finish_gate 调用 `openspec validate <archive-id> --strict` 必 fail。

**Bug 来源**:openspec CLI tool design;**非本 change 引入**。

**修复 scope**:**不在本 change scope**(留 follow-on `fix-openspec-validate-archived-change-support`)。

**(3) `round_fix_continuity_v2_violation` + `dispatch_ledger_violation`(1 + 1)— restore-consent-gate 内 v2 fence cross-check 失败**:

archived restore-consent-gate evidence frontmatter 写 v2 protocol 字段(`runtime_enforcement_protocol_version: v2` + `dispatch_ledger_path`)+ 期望 ledger 文件存在。但 ADR-012/013 实施时 ledger 文件可能未真正落盘,或 v2 cross-check 逻辑与 evidence 写法不严格 align。

**预期变化**:本 change retire `_check_dispatch_ledger` + `_check_round_fix_continuity` v2 cross-check 后,这 2 blocker **应消失**(archived evidence 走 legacy pass-through 不走 v2 cross-check)。

**Bug 来源**:archived restore-consent-gate 自身 evidence vs 当时 v2 fence cross-check 的协议 fragility;**非本 change 引入,但本 change retire 后会修复**。

## D-ArchivedReplayCompat criterion 修正(writeback to design.md)

**原 criterion**(design.md initial 版本):"archived 4 change 全 PASS"。**与实测矛盾**(全 FAIL 31 个 blocker 累积)。

**修正 criterion**(本 P0 baseline 后 writeback):
- Pre-existing 失败模式不变(25 个 `tasks_unchecked` regex bug + 4 个 `openspec_validate_failed` tool limitation = 29 个 blocker)
- 本 change retire 后**预期 2 个 v2 fence blocker(`round_fix_continuity_v2_violation` + `dispatch_ledger_violation`)消失**(archived evidence 走 legacy pass-through)
- **总 blocker 应从 31 → 29**;**不引入新 blocker type**

P5 verify 阶段对账标准:
- runtime-enforcement:11 + 1 = 12(不变)
- executable-enforcement:14 + 1 = 15(不变)
- restore-consent-gate:0 + 1 = 1(原 3 → 1,2 个 v2 blocker 消失)
- ledger-binding:0 + 1 = 1(不变)
- **总:29**(原 31)

若 P5 实测 blocker 不符合上表 → DRIFT type 3(`evidence_contradicts_contract`)阻断 archive。

## P0 实施 lesson(写入 retrospective + tasks/micro_tasks 修正)

P0.2.1 第一次 invoke `python tools/forgeue_finish_gate.py --change <archived-id> --json` **漏 `--dry-run` flag**,工具副作用写入 4 个 archived `verification/finish_gate_report.md`(diff:`change_id` field 改为 P0 命令传入的 `2026-05-05-...` 格式 + timestamp 更新 + "Did you mean" 提示 cache miss 重算)。**违 "归档即冻结" 原则**;tasks.md / micro_tasks.md `--dry-run` 修正已 inline writeback 防止 P5 verify 重蹈覆辙。

4 archive 修改文件 unstaged 留在 working tree(沿 user-driven deletion 约束):
- `openspec/changes/archive/2026-05-05-enhance-workflow-automation-runtime-enforcement/verification/finish_gate_report.md`
- `openspec/changes/archive/2026-05-05-enhance-workflow-automation-executable-enforcement/verification/finish_gate_report.md`
- `openspec/changes/archive/2026-05-06-restore-superpowers-worktree-consent-gate/verification/finish_gate_report.md`
- `openspec/changes/archive/2026-05-06-enhance-workflow-automation-ledger-binding/verification/finish_gate_report.md`

需 user `git restore` 这 4 个文件(本 evidence commit 不含 archive 修改;user 范围 deletion-equivalent 操作)。

## Followup tracking(2 个 follow-on backlog)

1. **`fix-finish-gate-section-regex-for-p-prefixed`**:`_SECTION_HEADING_RE` 扩展支持 `## P<N> — ` 格式
2. **`fix-openspec-validate-archived-change-support`**:openspec CLI tool 支持 archived change validate(可能需上游 openspec PR;短期可在 finish_gate 内捕获 archive/ 路径自动 skip 或走 alternative path)

## 进入 P1 准入条件

- [x] pytest collected = 1746(已记)
- [x] git HEAD = 9f0a2a0(已记)
- [x] 4 archive 目录存在(已验证)
- [x] D-ArchivedReplayCompat 修正 criterion 已 writeback design.md(待 P0 commit 后 backfill SHA)
- [x] P0 评估 archived replay 失败 root cause 全为 pre-existing(non-blocking)
- [ ] User 确认 D-ArchivedReplayCompat 修正 criterion(本 evidence 写完后由 user review)
