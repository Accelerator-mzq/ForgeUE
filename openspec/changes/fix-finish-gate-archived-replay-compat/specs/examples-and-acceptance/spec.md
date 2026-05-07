# Spec delta — examples-and-acceptance (fix-finish-gate-archived-replay-compat)

## ADDED Requirements

### Requirement: `_check_tasks_unchecked` 双格式 section heading 识别 + per-format threshold

`tools/forgeue_finish_gate.py::_check_tasks_unchecked` SHALL 用 regex `_SECTION_HEADING_RE = re.compile(r"^##\s+(P)?(\d+)(?:\.|\s+—)\s+", re.MULTILINE)`(round 1 codex F2 inline writeback 修订:**双 capture group**)同时识别两种 tasks.md section heading 格式:

- **active changes 现行格式**:`## <int>. <text>`(例:`## 9. P8 Finish Gate`);group(1) = `None`,group(2) = section integer
- **archived 历史格式**:`## P<int> — <text>`(P-prefix + em-dash U+2014;例:`## P10 — Archive` / `## P11 — Documentation Sync footer`);group(1) = `"P"`,group(2) = section integer

`_check_tasks_unchecked` SHALL 按 group(1) 选 per-format self-stage threshold(沿 design.md 新 `D-PerFormatThreshold`):

- **Active 格式**(`group(1) is None`):threshold ≥9(`_SELF_STAGE_SECTION_THRESHOLD = 9`,沿原 baseline,P8 finish gate = section 9)
- **Archived 格式**(`group(1) == "P"`):threshold ≥10(archived P0-P9 全 workflow prerequisite 应 block;P10+ self-stage 应 skip;沿 codex round 1 F2 实证 archived P9 ambiguous 不安全用 ≥9)

section number ≥ threshold 的 `[ ]` 行视为 self-stage,不阻断 finish_gate 自身(避免 chicken-and-egg)。Active workflow 路径(active `openspec/changes/<id>/`)行为 unchanged — `## <int>. <text>` 仍命中 + 阈值 ≥9 不变,backward-compat 守门。本 requirement 沿 design.md `D-RegexExtension`(round 1 修订)+ `D-PerFormatThreshold`(round 1 新增)决策。

#### Scenario: active change `## <int>. <text>` 格式仍命中(backward-compat)

- **GIVEN** active change tasks.md 含 `## 9. P8 Finish Gate` 后跟 `- [ ] 9.1 finish_gate exit 0`
- **WHEN** `forgeue_finish_gate.py::_check_tasks_unchecked` 跑
- **THEN** regex 命中 section 9
- **AND** §9.1 unchecked 行被识别为 self-stage(9 ≥ 9)→ 不报 blocker
- **AND** 行为与 commit `a4334db` baseline 一致(backward-compat 守门)

#### Scenario: archived change `## P<N> — <text>` 格式命中(本 change 新增)

- **GIVEN** archived change tasks.md 含 `## P10 — Archive` 后跟 `- [ ] 10.1 /opsx:archive`,以及 `## P11 — Documentation Sync footer` 后跟 `- [ ] 11.1 sync gate items closed`
- **WHEN** `forgeue_finish_gate.py::_check_tasks_unchecked` 跑(`change_dir = openspec/changes/archive/2026-MM-DD-<id>/`)
- **THEN** regex 命中 section 10 + 11
- **AND** §10.1 + §11.1 unchecked 行均识别为 self-stage(10/11 ≥ 9)→ 不报 blocker
- **AND** archived 4 change finish_gate replay `tasks_unchecked` blocker 总数从 25 → 0

#### Scenario: 假阴性边界守门 — `## 1.5 sub-section` 不命中

- **GIVEN** tasks.md 含假想小数点格式 `## 1.5 sub-section`(实测 active / archived 均无此模式)
- **WHEN** regex 跑
- **THEN** 不命中(`(\d+)` 后必须是 `.` 或 `\s+—`,`1.5` 后是 `5` 不命中,`1.` 后必须紧跟空格)
- **AND** YAGNI 边界守住,不 over-permissive

#### Scenario: P-prefix 必须紧跟整数 — `## PX — title` 不命中

- **GIVEN** tasks.md 含 `## PX — title`(P 后非数字)
- **WHEN** regex 跑
- **THEN** 不命中(`(P)?(\d+)` 要求 `\d+` 至少 1 位)
- **AND** parse 安全 — `current_section` 不受污染

#### Scenario: archived `## P9 — Documentation Sync Gate` workflow prerequisite 应 block(round 1 codex F2 inline writeback)

- **GIVEN** archived change tasks.md 含 `## P9 — Documentation Sync Gate` 后跟 `- [ ] P9.1 sync gate items closed`(workflow prerequisite stage,doc sync gate 在 finish gate **之前**)
- **WHEN** `forgeue_finish_gate.py::_check_tasks_unchecked` 跑(`change_dir` 在 archive 路径下)
- **THEN** regex 命中 group(1)="P" + group(2)=9
- **AND** archived format threshold ≥10 → 9 < 10 → **NOT** self-stage skip
- **AND** §P9.1 unchecked 行报 `tasks_unchecked` blocker(workflow prereq 漏报 fail-loud,不静默 skip)
- **AND** 沿 design.md `D-PerFormatThreshold` archived ≥10 + codex round 1 F2 实证

#### Scenario: archived `## P10 — Finish Gate` self-stage 应 skip

- **GIVEN** archived change tasks.md 含 `## P10 — Finish Gate` 后跟 `- [ ] P10.1 finish_gate exit 0`,以及 `## P11 — Archive` 后跟 `- [ ] P11.1 /opsx:archive`,以及 `## P12 — 后置(可选)` 后跟 `- [ ] P12.1 follow-on tracking`
- **WHEN** `forgeue_finish_gate.py::_check_tasks_unchecked` 跑(archive 路径下)
- **THEN** regex 命中 group(1)="P" + group(2)=10/11/12
- **AND** archived format threshold ≥10 → 10/11/12 ≥ 10 → self-stage skip
- **AND** §P10.1 / §P11.1 / §P12.1 unchecked 行均**不**报 blocker
- **AND** archived 4 change finish_gate replay `tasks_unchecked` blocker 25 → 0(对账 design.md Goals)

### Requirement: `forgeue_finish_gate.py` openspec validate archive/ 路径分流 skip

`tools/forgeue_finish_gate.py` 在 invoke `openspec validate <id> --strict` subprocess 前 SHALL 用 **repo-relative + segment-precise** 方式检测 `change_dir` 是否在 archived 物理布局下(沿 design.md `D-DispatchPathDetection` round 1 codex F1 inline writeback 修订:`change_dir.is_relative_to(_common.archive_dir(repo))`);若是则 skip subprocess invocation 并写 rationale 字段到 finish_gate report 标 `openspec_validate_skipped: archive_path_unsupported_by_upstream_cli`,**不**生成 `openspec_validate_failed` blocker。Active change 路径(不在 `_common.archive_dir(repo)` 下)行为 unchanged — 继续 invoke,失败时 BLOCKER。本 requirement 沿 design.md `D-OpenSpecValidateArchiveSkip` 决策(archive/ 路径下短期 mitigation;长期方案给上游 openspec CLI 提 PR 留 follow-on `enhance-openspec-cli-archived-change-support`)。

#### Scenario: active change openspec validate 仍 invoke(backward-compat)

- **GIVEN** active change `openspec/changes/<id>/`(`change_dir.parts` 不含 `archive`)
- **WHEN** `forgeue_finish_gate.py` 跑
- **THEN** invoke `openspec validate <id> --strict` subprocess
- **AND** failure 时仍报 `openspec_validate_failed` BLOCKER(active 路径行为 unchanged)

#### Scenario: archived change openspec validate skip(本 change 新增)

- **GIVEN** archived change `openspec/changes/archive/2026-MM-DD-<id>/`(`change_dir.parts` 含 `archive` segment)
- **WHEN** `forgeue_finish_gate.py` 跑
- **THEN** **不** invoke `openspec validate` subprocess
- **AND** finish_gate report 含 rationale `openspec_validate_skipped: archive_path_unsupported_by_upstream_cli`
- **AND** archived 4 change replay `openspec_validate_failed` blocker 总数从 4 → 0

#### Scenario: archive 路径检测稳定性 — repo-relative `is_relative_to` 而非 substring-of-parts

- **GIVEN** 假想 active change 命名 `add-archive-feature`(`change_dir = <repo>/openspec/changes/add-archive-feature/`,change-id 含 `archive` 子串但路径不在 `_common.archive_dir(repo)` 下)
- **WHEN** `forgeue_finish_gate.py` 跑
- **THEN** `change_dir.is_relative_to(_common.archive_dir(repo))` 返回 False(active path 不在 archived 布局下)
- **AND** 检测 negative,继续 invoke `openspec validate`(active 路径行为 unchanged)
- **AND** `D-DispatchPathDetection` 边界守住 — 不 false-positive 命中

#### Scenario: repo 父目录路径含 `archive` segment 不应 false-positive(round 1 codex F1 inline writeback)

- **GIVEN** repo 整体路径含 `archive` segment(如 `tmp_path / "archive" / "repo"` — repo 父目录名是 `archive`),内有 active change `<repo>/openspec/changes/<active-id>/`
- **WHEN** `forgeue_finish_gate.py` 跑(`change_dir = <repo>/openspec/changes/<active-id>/`)
- **THEN** `change_dir.is_relative_to(_common.archive_dir(repo))` 返回 False(`_common.archive_dir(repo) = <repo>/openspec/changes/archive/`,active change_dir **不**在此 subtree 下)
- **AND** **NOT** 走 archive skip 分支
- **AND** 继续 invoke `openspec validate <id> --strict` subprocess(monkeypatch 守门 count == 1)
- **AND** 守门 round 1 codex F1 高危 finding 修复:`"archive" in Path(change_dir).parts` 旧检测会 false-positive(repo 路径含 `archive` segment 但 active change_dir 不在 archive subtree 下),让 active change 的 openspec validate BLOCKER 静默漏报

#### Scenario: archive-skip test 必须用 monkeypatch 验证 invocation 实际 skipped(round 1 codex F3 inline writeback)

- **GIVEN** archived change `change_dir.is_relative_to(_common.archive_dir(repo))` True + env 无 openspec CLI(`shutil.which("openspec")` 返回 None)
- **WHEN** test 用 `monkeypatch.setattr(fg, "run_openspec_validate", _spy)` + 跑 `fg.build_report(...)`,_spy 计数 invocation
- **THEN** `_spy invocation count == 0`(archive 路径分流 skip 在 `run_openspec_validate` 之前)
- **AND** report blockers 不含任何 validate-related blocker type:`openspec_validate_failed` ✗ + `openspec_cli_missing` ✗ + `openspec_validate_error` ✗
- **AND** report warnings 含 `openspec_validate_skipped: archive_path_unsupported_by_upstream_cli` rationale(audit trail)
- **AND** 守门 round 1 codex F3 medium finding 修复:仅 assert `openspec_validate_failed` 不在不足以证明 skip — env 无 CLI 时 blocker type 是 `openspec_cli_missing` escapes assertion → false-pass
