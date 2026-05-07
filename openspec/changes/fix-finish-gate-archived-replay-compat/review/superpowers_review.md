---
change_id: fix-finish-gate-archived-replay-compat
stage: S6
evidence_type: superpowers_review
contract_refs:
  - openspec/changes/fix-finish-gate-archived-replay-compat/proposal.md
  - openspec/changes/fix-finish-gate-archived-replay-compat/design.md
  - openspec/changes/fix-finish-gate-archived-replay-compat/specs/examples-and-acceptance/spec.md
  - openspec/changes/fix-finish-gate-archived-replay-compat/tasks.md
  - tools/forgeue_finish_gate.py
  - tests/unit/test_forgeue_finish_gate.py
aligned_with_contract: true
detected_env: claude-code
triggered_by: /forgeue:change-review fix-finish-gate-archived-replay-compat
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
triggered_by_command: change-apply-subagent
skill_cascade_audit:
  invoked_skills:
    - superpowers:requesting-code-review
  cascade_check_pass_at: 2026-05-07T07:53:46Z
task_granularity: phase
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md + review/codex_verification_review.md
verdict: approve
disputed_open: 0
review_round: 1
created_at: 2026-05-07T07:53:46Z
---

# Superpowers Code Review — fix-finish-gate-archived-replay-compat (S6)

## Strengths

**1. 精准 root cause 定位 + 最小化 fix**

两个 bug(F-A regex 不认 P-prefix em-dash 格式 / F-B openspec CLI 不感知 archive/ 路径)都有独立 L0 baseline 实证支撑(25 + 5 blocker 数据),修复严格限定 `tools/forgeue_finish_gate.py` 4 处 edit,没有顺手重构无关 fence。boundary 守门(`git diff --name-only` 确认仅 2 生产文件 + 26 openspec change 文件)。

**2. round 1 codex 3 finding 全正确接受,inline writeback 质量高**

F1(D-DispatchPathDetection repo 父目录 false-positive)、F2(archived P9 ambiguous 阈值)、F3(archive-skip test invocation 验证不足)三条都经 controller 独立 file:line 验证为真实 bug,且接受前给出完整 rationale(见 `review/codex_design_review.md §F1/F2/F3 verify`)。没有 performative agreement 或 blind accept。

**3. D-DispatchPathDetection `is_relative_to` 实现正确**

`change_dir.is_relative_to(_common.archive_dir(repo))` 使用 repo-relative + segment-precise invariant,直接验证:
- `repo = /some/archive/repo` + active change → `is_relative_to` 返回 False → 继续 invoke(F1 守门)
- archived change → 返回 True → skip
- change-id 含 `archive` 子串(`add-archive-feature`)但路径不在 archive subtree → 返回 False → 继续 invoke

实测 `tools/_common.py:466-467` 确认 `archive_dir(repo) = repo / "openspec" / "changes" / "archive"` 正确。

**4. D-PerFormatThreshold 逻辑清晰,conservative 选择合理**

archived threshold ≥10(vs active ≥9)让 archived P0-P9 全 block,P10+ skip。实测 archived P9 真的有 `Documentation Sync Gate`(prerequisite)和 `MEMORY.md update(后置可选)`(self-stage)两种语义,共用 ≥9 会产生 false PASS。≥10 是 conservative fail-loud 策略正确。

**5. 9 个新 test case 覆盖完整,monkeypatch 模式正确**

`test_finish_gate_skips_openspec_validate_for_archive_path` 用 monkeypatch + count == 0 + 拒绝全部 validate-related blocker type(`openspec_validate_failed` / `openspec_cli_missing` / `openspec_validate_error`),不存在 env 无 CLI 时 false-pass 漏洞(F3 修复守门)。`test_finish_gate_invokes_openspec_validate_when_repo_path_contains_archive_segment` 用 `tmp_path / "archive" / "repo"` + count == 1 守门 F1 修复。

**6. L0 实测 evidence 可信**

archived 5 change replay: 31 → 1 blocker(残留 1 = `writeback_commit_unrelated`,已明确标为本 change scope 外的预期残留)。L1 全套 pytest 1585 passed,2 failed 均为 pre-existing(`git stash` 验证确认)。

**7. codex verification review 2 finding 正确 scope-out**

F1(`forgeue_finish_gate.py:843` explicit null bypass)和 F2(`.claude/commands/codex/review.md:170` stage flag strip)经 `git blame` 确认都是 prior shipped changes 引入的 pre-existing bug,不在本 change 4 P2 edit 范围内。follow-on backlog 标记正确。

---

## Issues

### Critical (Must Fix)

无。

### Important (Should Fix)

**I-1: `design.md` 有 `### D-OpenSpecValidateArchiveSkip` 章节重复(lines 71-87 + lines 88-104)**

`design.md` 中 `D-OpenSpecValidateArchiveSkip` 出现两次,标题和正文高度重叠:
- **L71-87(第一份)**:**决定** 段引用 `change_dir.is_relative_to(_common.archive_dir(repo))`(round 1 修订后的正确版本)
- **L88-104(第二份)**:**决定** 段仍用旧 `archive/` segment 检测方式(`Path.parts` contains `"archive"`)

产生原因:round 1 inline writeback 在 L71 前插入了修订版,但没删除 L88 起的旧版。两个 `### D-OpenSpecValidateArchiveSkip` heading 重名让文档读者无法区分哪份是权威,且第二份的决定内容与实现(`is_relative_to`)不一致,会误导未来 reviewer。

**建议**:删除 `design.md:88-104` 旧版 `D-OpenSpecValidateArchiveSkip` 章节。第一份(L71)含有 `D-DispatchPathDetection` round 1 修订的正确引用,是权威版本。

**I-2: `design_cross_check.md` A.2 表头仍写"3 D-decision",但 design.md 实际有 4 个**

`design_cross_check.md` A.2 节标题:`### A.2 3 D-decision 立场(Claude approve)`。表中只有 `D-RegexExtension`、`D-OpenSpecValidateArchiveSkip`、`D-DispatchPathDetection` 三条,缺少 round 1 inline writeback 新增的 `D-PerFormatThreshold`。

A.2 是 cross-check 的 Claude 立场锁定段,其功能是让未来 reviewer 对照 D-decision 全集做审查。缺 `D-PerFormatThreshold` 意味着 cross-check 不完整,archived P9 ambiguous 的阈值决策没有在 A.2 展现。

**建议**:在 `design_cross_check.md` A.2 表中补一行 `D-PerFormatThreshold`,更新标题为"4 D-decision"。

### Minor (Nice to Have)

**M-1: `spec.md` Scenario 2 的阈值说明不准确**

`spec.md` L32:`§10.1 + §11.1 unchecked 行均识别为 self-stage(10/11 ≥ 9)→ 不报 blocker`

实际 archived format threshold 是 ≥10(由 `D-PerFormatThreshold` 决定),不是 ≥9。P10 和 P11 都满足 10/11 ≥ 10,结论正确,但说明中写的 `≥ 9` 是 active format 的阈值,放在 archived format context 里误导读者。应改为 `(10/11 ≥ 10 archived 阈值)`。

对行为没有影响——10 和 11 在两个阈值下都满足跳过条件——但未来审计该 scenario 时会造成困惑。

**M-2: 5 个测试 docstring 的 spec.md scenario 编号与实际 spec.md 章节顺序不匹配**

round 1 inline writeback 重新排列了 spec.md 的 scenario 顺序(在两个 Requirement 段内插入新增 scenario),导致 spec.md 最终顺序与 design.md Reasoning Notes 所写的 "Scenario 7/8/9/10/11" 编号含义产生偏差。测试 docstring 引用的是 design.md 里的编号而非 spec.md 最终顺序:

| 测试函数 | docstring 引用 | spec.md 实际 scenario | 内容是否匹配 |
|---------|--------------|----------------------|------------|
| `test_check_tasks_unchecked_archived_p9_doc_sync_gate_blocks` | Scenario 8 | Scenario 5(archived P9 prereq) | 否 |
| `test_finish_gate_skips_openspec_validate_for_archive_path` | Scenario 6+11 | Scenario 8+11(archive skip+monkeypatch) | 否 |
| `test_finish_gate_invokes_openspec_validate_for_active_path` | Scenario 5 | Scenario 7(active validate invoked) | 否 |
| `test_archive_segment_detection_uses_path_parts_not_substring` | Scenario 7 | Scenario 9(stability) | 否 |
| `test_finish_gate_invokes_openspec_validate_when_repo_path_contains_archive_segment` | Scenario 9 | Scenario 10(repo-path false-positive) | 否 |

测试的语义覆盖是完整正确的(所有 11 个 spec.md scenario 都有对应测试),仅 docstring 注释编号与 spec.md 现行顺序不对。对 CI 无影响,但维护者在用 docstring 追溯 spec scenario 时会花额外时间。

---

## Recommendations

1. **I-1 优先处理**:删除 `design.md` 中重复的旧版 `D-OpenSpecValidateArchiveSkip` 章节(L88-104)。这是唯一会让未来 reviewer 看到内容矛盾(决定段与实现不符)的地方,影响文档可信度。

2. **I-2 处理**:在 `design_cross_check.md` A.2 补 `D-PerFormatThreshold` 行。修改量极小(一行表格 + 标题数字改 4),但 cross-check 完整性对下次类似 change 的参考价值较高。

3. **M-1/M-2 可在 doc-sync gate(P6/P7)一并处理**:spec.md Scenario 2 阈值说明纠正 + test docstring scenario 编号同步到 spec.md 现行顺序,属于文档精度修正,不影响行为。可合并到 P6 doc-sync 阶段处理,不需要单独 fix commit。

4. **follow-on backlog 两条已正确标记**:`fix-runtime-enforcement-protocol-version-explicit-null-bypass`(F1)和 `fix-codex-review-stage-flag-strip`(F2)均有 `git blame` 实证为 prior shipped change 引入,不在本 change scope。scope-out 判定正确,不阻断 archive。

5. **2 个 pre-existing test fail 确认**:全套 pytest 1585 passed / 2 failed / 1 skipped。2 failed 均与本 change 无关:
   - `test_real_cross_check_file_format[design_cross_check.md0]` — sibling change `centralize-followon-backlog-registry` 自身问题(`disputed_open: None`)
   - `test_real_cross_check_files_have_evidence_type` — archived `review_cross_check.md` evidence_type 白名单扩展 pre-existing since retire P5

---

## Assessment

**Ready to merge?** Yes,With fixes(I-1 + I-2 建议修复后进入 doc-sync gate;M-1/M-2 可在 doc-sync gate 同批处理)

**Reasoning**

实现正确性:4 个 production edits 字面对应 4 个 D-decision,`is_relative_to` 实现 F1-correct,dual capture group regex 实现 F2-correct,monkeypatch count 模式实现 F3-correct。L0 实测证据确实(31 → 1 blocker),L1 全套 1585 passed 无回归。9 个新 test case 覆盖全部 11 spec scenarios,backward-compat 2 基线 test 全绿。

阻断理由缺失:两个 Important 问题(I-1 重复 section / I-2 A.2 遗漏 D-PerFormatThreshold)是文档缺陷,不影响代码运行。scope 内 codex verification review 没有 raise 任何 in-scope finding。

建议修复路径:I-1 + I-2 是低成本 doc-only 修改,可在本 change P6 doc-sync gate 阶段(tasks.md §7)内处理,不需要回到 S3/S4 重新实施。处理后 `disputed_open` 维持 0。
