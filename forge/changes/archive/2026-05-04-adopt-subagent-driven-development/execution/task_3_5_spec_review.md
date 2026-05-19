---
change_id: adopt-subagent-driven-development
stage: S4
evidence_type: subagent_spec_review
contract_refs:
  - tasks.md#5.7
  - design.md#D-EvidenceSchema
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: forced (Pre-P0 dogfood manual dispatch round 1 — task 3.5)
codex_plugin_available: true
triggered_by_command: change-apply-subagent
---

# Task 3.5 §5.7 Spec Compliance Review (Round 1 — ✅ Spec compliant)

## Status: ✅ Spec compliant

## Verification method (independent)

- `git show af2892a:.claude/commands/forgeue/change-apply.md` — 验证 task 2 commit 的文件 frontmatter `tags`
- `git show 653ba2d:.claude/commands/forgeue/change-apply.md` — 验证当前 deprecated 标记保留
- `git show 653ba2d --stat` — 验证仅 3 fixture 改动(90 insertions / 11 deletions)
- `git diff 653ba2d^ 653ba2d -- .claude/commands/forgeue/ .claude/skills/ src/framework/` — discipline 0 改动验证(empty output)
- Read 3 fixture 文件完整内容
- `pytest tests/unit/test_forgeue_command_markdown.py test_forgeue_workflow_no_paid_default.py test_forgeue_workflow_plugin_invocation.py -v` — 19 PASS
- `pytest -q` — 1426 passed, 1 skipped, 0 errors

## Option C verification: ✅ tags exist + claim 完全验证

- `change-apply.md` frontmatter `tags: [forgeue, deprecated]` 在 task 2 commit `af2892a` **已写入**(L5,与 implementer 声明一致)
- 当前 commit `653ba2d` 文件 frontmatter 完全一致(0 改动)
- helper 行为正确:`parse_frontmatter` 把 flow-style list `[forgeue, deprecated]` 解析成 raw string,`tags_str` substring 检测覆盖 list / string 双风格(沿用 `test_each_cmd_tags_includes_forgeue` 同款)

## Implementation completeness: ✅ 全部满足

- 3 个 fixture 各加 `_is_deprecated(path)` helper(行为完全一致)
- `cmd_files` fixture 改为 `glob("change-*.md") if not _is_deprecated(p)`
- assertion `len == 9`(由 8 改 9,理由准确:7 keep + 2 new)
- import `_common` 在 3 文件中 path 操作一致(`_REPO/tools` insert into `sys.path`)
- `test_expected_eight_commands_present` 改名 `test_expected_active_commands_present`,expected 集合 9 个名字精确(改名合理 — 数字 hardcode 在测试名是 anti-pattern)
- 3 fixture 单测:19 PASS / 0 FAIL / 0 ERROR
- 全量 pytest:1426 passed / 1 skipped / **0 ERRORS**(数学:1410 + 16 = 1426 一致)

## Discipline compliance: ✅ 完全合规

- `.claude/commands/forgeue/` 0 改动(命令文件 body 不动 ✅)
- `.claude/skills/` 0 改动(SKILL.md 不动 ✅)
- `src/framework/` 0 改动 ✅
- 仅引入 `_common.parse_frontmatter` 既有 helper,stdlib only ✅

## Option C systemic advantage: ✅ confirmed

- **Magic string count**:Option A 3 处 `"change-apply.md"` 字面量 vs Option C 0 处 magic string
- **Future deprecated 命令处理**:Option A 每加一个 deprecated 命令需手动改 3 个 fixture;Option C 只需新命令 frontmatter 加 `deprecated` tag,fixture 自动 skip
- **Fixture style consistency**:Option C 复用既有 `_common.parse_frontmatter` + 沿 `test_each_cmd_tags_includes_forgeue` 同款 list/string 双兼容
- **Cross-file dependency**:Option A 把 lifecycle 信息藏在 fixture 代码里;Option C 把 lifecycle 信息留在命令文件 frontmatter(契约层)— **单一真源更佳**
- **Migration Plan 兼容**:design.md `## Migration Plan` 要求"保留 1 archive cycle",Option B(物理移动)违反此精神;Option C 完全兼容
- **不需回写 design.md**:Option C 走既有 frontmatter 字段,无新决策,无 drift ✅

## Cross-file fixture style consistency: ✅ 三文件高度一致

- 3 个 `_is_deprecated(path)` helper 函数体**完全相同**
- 3 个 import 风格相同(`sys.path.insert(0, str(_TOOLS))` + `import _common  # noqa: E402`)
- 3 个 cmd_files fixture 用相同 `sorted(p for p in CMD_DIR.glob("change-*.md") if not _is_deprecated(p))` pattern
- 3 个 assertion `len == 9` 一致

### Minor 观察(non-blocking)

helper 函数复制 3 份而非提到 `_common` 共享,有轻微 DRY 违反,但保持 fixture 文件独立性(无 cross-test-file dependency)是合理 trade-off,且 helper 仅 ~10 行。

## Findings

无问题。

## Token usage

- input_tokens: ~10,000(读 3 fixture 文件 + 2 commit show + pytest output + git diff)
- output_tokens: ~2,000(本报告)
- model: claude-opus-4-7[1m]
- estimated_usd: ~$0.30(Opus 4.7 1M tier)
- data_source: manual_estimate, not gate-grade

## Recommendation

✅ **Proceed to code quality review**

Implementer 选 Option C 决策合理(systemic advantage 已 5 维度独立验证);implementation 完整 + 全量 pytest 0 errors;discipline 0 violation。可进入 code quality reviewer 阶段。

## 关键证据文件路径

- `.claude/commands/forgeue/change-apply.md` L5 frontmatter `tags: [forgeue, deprecated]`(task 2 commit `af2892a` 已写入)
- `tests/unit/test_forgeue_command_markdown.py:35-48`(`_is_deprecated` helper)
- `tests/unit/test_forgeue_command_markdown.py:51-57`(cmd_files fixture)
- `tests/unit/test_forgeue_workflow_no_paid_default.py:32-41`(同款 helper)
- `tests/unit/test_forgeue_workflow_plugin_invocation.py:30-39`(同款 helper)
- `tests/unit/test_forgeue_workflow_plugin_invocation.py:127-147`(`test_expected_active_commands_present` 改名 + expected 9 个名字)
