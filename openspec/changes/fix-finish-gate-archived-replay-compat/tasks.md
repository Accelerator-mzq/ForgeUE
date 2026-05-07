# Tasks: fix-finish-gate-archived-replay-compat

## 1. P0 — 准入 baseline + 评估实测

- [ ] 1.1 grep 确认 `tools/forgeue_finish_gate.py:1385` `_SECTION_HEADING_RE` 当前定义匹配 design.md `D-RegexExtension` 描述
- [ ] 1.2 跑 `python -m pytest -q tests/unit/test_forgeue_finish_gate.py -k "tasks_unchecked or self_stage"` 记录 P0 baseline(2 既有 case 必绿;`test_finish_gate_skips_p8_p9_self_stage_unchecked` + `test_finish_gate_does_not_skip_pre_p8_unchecked`)
- [ ] 1.3 跑 `python tools/forgeue_finish_gate.py --change archive/2026-05-06-retire-parallel-and-worktree-fully` 记录 archived replay 当前 blocker 数(应 ~1,沿 retire P0 baseline 实测)
- [ ] 1.4 写 P0 baseline.md 落 `verification/baseline.md`(12-key audit frontmatter + 实测数据)

## 2. P1 — TDD red:加 9 个失败测试(round 1 codex F1+F2+F3 inline writeback 后)

- [ ] 2.1 在 `tests/unit/test_forgeue_finish_gate.py` 加 `test_check_tasks_unchecked_recognizes_p_prefixed_em_dash`(archived `## P10 — Archive` / `## P11 — Documentation Sync footer` 格式 self-stage filter 正确;archived 阈值 ≥10 → skip;沿 specs.md Scenario 2 + 10)
- [ ] 2.2 加 `test_check_tasks_unchecked_p_prefix_optional_active_format_unchanged`(active `## 9. P8 Finish Gate` 格式仍命中;backward-compat 守门;沿 Scenario 1)
- [ ] 2.3 加 `test_check_tasks_unchecked_yagni_decimal_subsection_not_matched`(假阴性边界 `## 1.5 sub-section` 不命中)+ `test_check_tasks_unchecked_p_non_digit_not_matched`(假阴性 `## PX — title` 不命中;沿 Scenario 3+4)
- [ ] 2.4 加 `test_finish_gate_skips_openspec_validate_for_archive_path`(archived change `change_dir.is_relative_to(_common.archive_dir(repo))` True → `openspec validate` skip + monkeypatch + count == 0 + finish_gate report 含 rationale + 拒绝任何 validate-related blocker type;沿 Scenario 6 + 11,**round 1 codex F3 改造 monkeypatch + count assertion**)
- [ ] 2.5 加 `test_finish_gate_invokes_openspec_validate_for_active_path`(active change `change_dir` 不在 archive subtree → monkeypatch + count == 1;backward-compat 守门;沿 Scenario 5)
- [ ] 2.6 加 `test_archive_segment_detection_uses_path_parts_not_substring`(`add-archive-feature` 这种 active change 名含 `archive` 子串但路径不在 archive subtree → 不 skip;沿 Scenario 7;**round 1 codex F1 改造**:`is_relative_to(_common.archive_dir(repo))` 替代 `parts` substring 检测)
- [ ] 2.7 加 `test_finish_gate_invokes_openspec_validate_when_repo_path_contains_archive_segment`(repo = `tmp_path / "archive" / "repo"` + active change → 仍 invoke openspec validate + count == 1;沿 Scenario 9;**round 1 codex F1 inline writeback 高危守门**)
- [ ] 2.8 加 `test_check_tasks_unchecked_archived_p9_doc_sync_gate_blocks`(archived `## P9 — Documentation Sync Gate` workflow prerequisite + unchecked 项 → 报 `tasks_unchecked` blocker;沿 Scenario 8;**round 1 codex F2 inline writeback 中危守门**)
- [ ] 2.9 跑 `pytest tests/unit/test_forgeue_finish_gate.py -k "p_prefixed or archive_path or yagni or active_path or path_parts or under_archive_parent or archived_p9_doc_sync" -v`,确认 9 case 全 fail(red)— 部分 case 因 baseline behavior subset 可能 PASS(如 backward-compat / yagni 边界);active path / archive path 主体 case 必须 fail

## 3. P2 — TDD green:实施修复(round 1 codex F1+F2 inline writeback 后)

- [ ] 3.1 修改 `tools/forgeue_finish_gate.py:1385` `_SECTION_HEADING_RE` regex 为 `re.compile(r"^##\s+(P)?(\d+)(?:\.|\s+—)\s+", re.MULTILINE)`(双 capture group;沿 D-RegexExtension round 1 修订)
- [ ] 3.2 在 `forgeue_finish_gate.py` 加常量 `_SELF_STAGE_SECTION_THRESHOLD_ARCHIVED = 10`(沿 D-PerFormatThreshold round 1 新增);改 `check_tasks_unchecked` 函数体用 group(2) 抽 integer + group(1) 决定 per-format threshold(active ≥9 / archived ≥10)
- [ ] 3.3 在 `forgeue_finish_gate.py::build_report` 内 invoke `openspec validate` 之前加 `change_dir.is_relative_to(_common.archive_dir(repo))` repo-relative 检测,若 True 则 skip subprocess + record `openspec_validate_skipped: archive_path_unsupported_by_upstream_cli` 到 finish_gate report warnings(沿 D-OpenSpecValidateArchiveSkip + D-DispatchPathDetection round 1 修订:`is_relative_to` 替代 `parts` substring)
- [ ] 3.4 跑 `pytest tests/unit/test_forgeue_finish_gate.py -k "p_prefixed or archive_path or yagni or active_path or path_parts or under_archive_parent or archived_p9_doc_sync" -v` 确认 9 case 全绿(green)
- [ ] 3.5 跑全套 `python -m pytest -q tests/unit/test_forgeue_finish_gate.py` 确认所有既有 case 不 regression

## 4. P3 — Verify(L0 + L1)

- [ ] 4.1 L0:跑 `python tools/forgeue_finish_gate.py --change archive/2026-05-06-retire-parallel-and-worktree-fully` 实测 `tasks_unchecked` + `openspec_validate_failed` blocker 总数 archived 4 change 从 29 → 0(沿 design.md goals)
- [ ] 4.2 L0:跑 archived 其他 3 change(`runtime-enforcement` / `executable-enforcement` / `restore-consent-gate` / `ledger-binding`)finish_gate replay,确认 `tasks_unchecked` + `openspec_validate_failed` blocker 全消(总 0;v2 fence 已在 retire 中消失,本 change 再去 25 + 4 noise)
- [ ] 4.3 L1:跑 `python -m pytest -q` 全套 1746(retire P5 baseline)+ 7 新增 = 1753 必绿;无 regression
- [ ] 4.4 写 `verification/verify_report.md`(12-key audit frontmatter + L0 archived replay 对账表 + L1 实测数据)

## 5. P4 — Codex `/codex:review --base main` 验证 hook

- [ ] 5.1 触发 `codex:review` background job(`/codex:review --base main`)
- [ ] 5.2 等 codex 输出,把 review 报告落 `review/codex_verification_review.md`(12-key audit frontmatter + verdict + finding 表)
- [ ] 5.3 处理 codex finding(若有):in-scope inline writeback fix(`disputed_open: 0`);out-of-scope 标 follow-on backlog
- [ ] 5.4 (skip 沿 micro-bugfix 通道)`/codex:adversarial-review` 不跑 — 本 change 无 cross-cutting / 无 new dependency / 无 security 影响,沿 enum_cross_ref_check 同款 skip 模式

## 6. P5 — Superpowers `requesting-code-review` finalize

- [ ] 6.1 走 `superpowers:requesting-code-review` skill;落 `review/superpowers_review.md`(12-key audit frontmatter + 检查 design.md ↔ specs.md ↔ tasks.md ↔ code 一致性)
- [ ] 6.2 处理 review finding(若有):cross-check `disputed_open == 0`

## 7. P6 — Documentation Sync Gate

- [ ] 7.1 跑 `python tools/forgeue_doc_sync_check.py --change fix-finish-gate-archived-replay-compat`(10 文档静态扫,标 [REQUIRED] / [OPTIONAL] / [SKIP] / [DRIFT])
- [ ] 7.2 应用 [REQUIRED] 文档同步:CHANGELOG.md `[Unreleased]` Fixed 子段 +1 条记录两 bug 修复 + 关联 follow-on id
- [ ] 7.3 其他 9 文档(SRS / HLD / LLD / test_spec / acceptance_report / README.md / CLAUDE.md / AGENTS.md / openspec/specs/* 主 spec)预期 [SKIP](无契约改动)— 若 doc_sync_check 报 [REQUIRED] 则按文档实读者 usefulness 评估再写
- [ ] 7.4 写 `verification/doc_sync_report.md`(12-key audit frontmatter + 10 文档分类决策 + reasoning notes anchor)

## 8. P7 — Pre-archive cross-check

- [ ] 8.1 跑 `python tools/forgeue_change_state.py --change fix-finish-gate-archived-replay-compat --writeback-check` 确认 4 类 named DRIFT 检测全 PASS(本 change 无 evidence drift,无写回违规)
- [ ] 8.2 cross-check evidence frontmatter 与 D-decision 一致性:design.md 3 D-decision(`D-RegexExtension` / `D-OpenSpecValidateArchiveSkip` / `D-DispatchPathDetection`)在 specs.md scenario 全 covered

## 9. P8 — Finish Gate

- [ ] 9.1 跑 `python tools/forgeue_finish_gate.py --change fix-finish-gate-archived-replay-compat` exit 0
- [ ] 9.2 finish_gate report 落 `verification/finish_gate_report.md`(沿 12-key audit frontmatter)
- [ ] 9.3 settings.json review-gate hook 检查(若用户启 `--enable-review-gate` 则 finish_gate WARN 提示 disable;沿 ForgeUE Integrated Workflow 禁令)

## 10. P9 — Archive(用户授权 fence #1 不可逆)

- [ ] 10.1 用户显式授权后跑 `/opsx:archive fix-finish-gate-archived-replay-compat`
- [ ] 10.2 commit + push 用户授权后(沿 user feedback `Push requires explicit per-commit auth` — 每 push 单独请示)

## 11. Documentation Sync footer

- [ ] 11.1 sync gate items closed(P6 P7.3 已 cover)
