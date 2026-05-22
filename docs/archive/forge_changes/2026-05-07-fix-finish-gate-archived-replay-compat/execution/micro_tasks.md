---
change_id: fix-finish-gate-archived-replay-compat
stage: S2
evidence_type: micro_tasks
contract_refs:
  - openspec/changes/fix-finish-gate-archived-replay-compat/execution/execution_plan.md
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

# Micro Tasks — fix-finish-gate-archived-replay-compat

> **For controller(主 session Claude)**:每个 task 完整 prompt 文本作为 implementer subagent 的 input(沿 ForgeUE Integrated Workflow `change-apply-subagent` task input protocol,subagent 不被授权读 plan files)。每个 task contract refs 用作 audit trail 进 evidence frontmatter,**不**直接进入 subagent prompt。

> **For implementer subagent**:你是 fresh context,只看本 prompt 文本。**严禁** read `execution/execution_plan.md` / `execution/micro_tasks.md` 任何 plan 文件 — 你只接收主 session 提取后的完整 prompt。**严禁**改 design.md / specs.md / tasks.md(contract artifact 不能被 implementer 改);若发现 design / spec gap → return back to controller 不自行回写。

---

## task_p0_baseline (tasks.md#1.1-1.4)

**Phase**:P0 — Baseline 评估实测(沿 design.md Goals 实测对账标准)

**Files**:
- Read: `tools/forgeue_finish_gate.py`(line 1385 `_SECTION_HEADING_RE` 当前定义;line 1451-1487 `run_openspec_validate`;line 1567-1570 `build_report` 内 invoke 点)
- Read: `tests/unit/test_forgeue_finish_gate.py:822-893`(既有 2 baseline case)
- Run: `python tools/forgeue_finish_gate.py --change archive/2026-05-06-retire-parallel-and-worktree-fully` 等 4 个 archived change(见下)
- Create: `openspec/changes/fix-finish-gate-archived-replay-compat/verification/baseline.md`

**Task content**:

- [ ] **Step 1: grep 确认 `_SECTION_HEADING_RE` 当前定义**

```bash
grep -n "_SECTION_HEADING_RE" tools/forgeue_finish_gate.py
```

Expected:line 1385 `_SECTION_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)`(若与此 expected 不符 → return back to controller,可能 codebase 已 drift)

- [ ] **Step 2: 跑 既有 2 baseline test case 必绿**

```bash
python -m pytest tests/unit/test_forgeue_finish_gate.py::test_finish_gate_skips_p8_p9_self_stage_unchecked tests/unit/test_forgeue_finish_gate.py::test_finish_gate_does_not_skip_pre_p8_unchecked -v
```

Expected:2 PASS(若任一 fail → return back to controller,backward-compat baseline 已 broken)

- [ ] **Step 3: 跑 finish_gate replay archived 4 change 记 blocker 数**

```bash
python tools/forgeue_finish_gate.py --change archive/2026-05-05-enhance-workflow-automation-runtime-enforcement
python tools/forgeue_finish_gate.py --change archive/2026-05-05-enhance-workflow-automation-executable-enforcement
python tools/forgeue_finish_gate.py --change archive/2026-05-06-restore-superpowers-worktree-consent-gate
python tools/forgeue_finish_gate.py --change archive/2026-05-06-enhance-workflow-automation-ledger-binding
python tools/forgeue_finish_gate.py --change archive/2026-05-06-retire-parallel-and-worktree-fully
```

Expected(沿 retire P5 baseline.md 实测):
| Archive | tasks_unchecked | openspec_validate_failed | total |
|---------|-----------------|--------------------------|-------|
| runtime-enforcement | 11 | 1 | 12 |
| executable-enforcement | 14 | 1 | 15 |
| restore-consent-gate | 0 | 1 | 1 |
| ledger-binding | 0 | 1 | 1 |
| retire-parallel-and-worktree-fully | 0 | 1 | 1 |
| **总** | **25** | **5** | **30** |

(注:retire P5 baseline 实测 archived 4 change = 29;加 retire 自己 archive 后第 5 个 = 30。预期数字以本 P0 实测为准 — 可能略有偏差,记录实测即可)

- [ ] **Step 4: 写 verification/baseline.md**

落 `openspec/changes/fix-finish-gate-archived-replay-compat/verification/baseline.md`,内容:

```markdown
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
  cascade_check_pass_at: <ISO 8601 NOW>
task_granularity: phase
autonomy_decision: claude_autonomous
---

# Baseline — P0 archived 4 change finish_gate replay 实测

## archived replay blocker 表(对账)

| Archive | tasks_unchecked | openspec_validate_failed | total |
|---------|-----------------|--------------------------|-------|
| <fill in 实测数> | | | |
| **总** | **<fill in>** | **<fill in>** | **<fill in>** |

## 既有 2 baseline test 状态

- `test_finish_gate_skips_p8_p9_self_stage_unchecked`: PASS
- `test_finish_gate_does_not_skip_pre_p8_unchecked`: PASS

## P1 进入条件

- [x] grep 确认 `_SECTION_HEADING_RE` 当前 baseline 定义匹配 design.md 期望
- [x] 既有 2 baseline test PASS(backward-compat 守门)
- [x] archived 4 change replay 实测 blocker 数记录(对账标准)
```

- [ ] **Step 5: Commit**

```bash
git add openspec/changes/fix-finish-gate-archived-replay-compat/verification/baseline.md
git commit -m "feat(forgeue): fix-finish-gate-archived-replay-compat P0 — baseline <N> blocker recorded

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

(commit 由 controller 决定 — implementer subagent 不直接 commit,只在 prompt return 提示 baseline.md 已写好。controller 负责 user 授权 + commit)

**Return to controller**:Step 1-4 done summary + 实测 blocker 表 + baseline.md 路径。

---

## task_p1_tdd_red (tasks.md#2.1-2.7)

**Phase**:P1 — TDD red 加 7 测试 case 全 fail

**Files**:
- Modify: `tests/unit/test_forgeue_finish_gate.py`(新增 ~150 行 7 case)
- 既有 case 2 不动:`test_finish_gate_skips_p8_p9_self_stage_unchecked`(line ~822)+ `test_finish_gate_does_not_skip_pre_p8_unchecked`(line ~861)

**Task content**:

- [ ] **Step 1: 加 7 test case 到 `tests/unit/test_forgeue_finish_gate.py` 文件末尾** (沿 design.md `D-RegexExtension` + `D-OpenSpecValidateArchiveSkip` + `D-DispatchPathDetection` 决策)

每 case 引用本 plan specs.md scenario:

```python
# ---------------------------------------------------------------------------
# fix-finish-gate-archived-replay-compat: 双格式 section heading 识别
# ---------------------------------------------------------------------------


def test_check_tasks_unchecked_recognizes_p_prefixed_em_dash(tmp_path):
    """archived 历史 change tasks.md 的 ``## P<N> — <text>`` 格式 section heading
    必须命中 ``_SECTION_HEADING_RE`` 并触发 self-stage filter(N ≥ 9 → skip)。
    沿 specs.md Scenario 2(archived `## P<N> — <text>` 格式命中)+
    design.md D-RegexExtension。
    """
    b = make_complete_change(tmp_path, "fc-tu-p-prefix")
    custom_tasks = (
        "# Tasks: fc-tu-p-prefix\n\n"
        "## P0 — 命令模板更新\n\n"
        "- [x] P0.1 done\n\n"
        "## P10 — Archive\n\n"
        "- [ ] P10.1 /opsx:archive\n"
        "- [ ] P10.2 evidence preserved\n\n"
        "## P11 — Documentation Sync footer\n\n"
        "- [ ] P11.1 sync gate items closed\n"
    )
    b.write_tasks(content=custom_tasks)
    blockers = fg.check_tasks_unchecked(b.change_dir)
    assert blockers == [], (
        f"§P10 / §P11 unchecked lines must be skipped (P-prefixed em-dash + N ≥ 9 "
        f"self-stage); got: {[(blk.type, blk.detail) for blk in blockers]}"
    )


def test_check_tasks_unchecked_p_prefix_optional_active_format_unchanged(tmp_path):
    """active 现行 ``## <N>. <text>`` 格式必须仍命中(backward-compat 守门)。
    沿 specs.md Scenario 1(active `## <int>. <text>` 仍命中)+ 守门 commit a4334db
    起 baseline 行为不破。
    """
    b = make_complete_change(tmp_path, "fc-tu-active-fmt")
    custom_tasks = (
        "# Tasks: fc-tu-active-fmt\n\n"
        "## 1. P0 Setup\n\n"
        "- [x] 1.1 done\n\n"
        "## 9. P8 Finish Gate\n\n"
        "- [ ] 9.1 finish_gate exit 0\n"
        "- [ ] 9.2 finish_gate_report landed\n"
    )
    b.write_tasks(content=custom_tasks)
    blockers = fg.check_tasks_unchecked(b.change_dir)
    assert blockers == [], (
        f"§9 (active `## N.` 格式) unchecked lines must be skipped (N ≥ 9 self-stage); "
        f"backward-compat 守门; got: {[(blk.type, blk.detail) for blk in blockers]}"
    )


def test_check_tasks_unchecked_yagni_decimal_subsection_not_matched(tmp_path):
    """假阴性边界:``## 1.5 sub-section``(小数点 sub-section,实测 active / archived
    均无此模式)不应命中 ``_SECTION_HEADING_RE`` regex。沿 specs.md Scenario 3
    (假阴性边界)+ design.md D-RegexExtension YAGNI 边界。
    """
    b = make_complete_change(tmp_path, "fc-tu-yagni-dec")
    custom_tasks = (
        "# Tasks: fc-tu-yagni-dec\n\n"
        "## 1. P0 Setup\n\n"
        "- [x] 1.1 done\n\n"
        "## 1.5 sub-section假想格式\n\n"
        "- [ ] 1.5.1 should still block (no section number captured;current_section=1)\n"
    )
    b.write_tasks(content=custom_tasks)
    blockers = fg.check_tasks_unchecked(b.change_dir)
    # `## 1.5 sub-section` 不命中 → current_section 滞留 1(< 9 threshold)→ §1.5.1 unchecked 仍 block
    types = [blk.type for blk in blockers]
    assert "tasks_unchecked" in types, (
        f"§1.5 sub-section header should NOT match new regex (YAGNI 边界);§1.5.1 unchecked "
        f"应仍 block(current_section 滞留 1 < 9); got: {types}"
    )


def test_check_tasks_unchecked_p_non_digit_not_matched(tmp_path):
    """假阴性边界:``## PX — title``(P 后非数字)不应命中 regex。沿 specs.md
    Scenario 4(假阴性 `## PX — title`)— `P?(\\d+)` 要求 \\d+ 至少 1 位。
    """
    b = make_complete_change(tmp_path, "fc-tu-p-non-digit")
    custom_tasks = (
        "# Tasks: fc-tu-p-non-digit\n\n"
        "## 1. P0 Setup\n\n"
        "- [x] 1.1 done\n\n"
        "## PX — invalid heading\n\n"
        "- [ ] PX.1 should still block (no section number captured)\n"
    )
    b.write_tasks(content=custom_tasks)
    blockers = fg.check_tasks_unchecked(b.change_dir)
    types = [blk.type for blk in blockers]
    assert "tasks_unchecked" in types, (
        f"§PX header (P 后非数字) should NOT match regex; PX.1 应仍 block; got: {types}"
    )


# ---------------------------------------------------------------------------
# fix-finish-gate-archived-replay-compat: archive 路径 openspec validate skip
# ---------------------------------------------------------------------------


def test_finish_gate_skips_openspec_validate_for_archive_path(tmp_path, monkeypatch):
    """archived change(``change_dir.is_relative_to(_common.archive_dir(repo))`` True)→
    ``run_openspec_validate`` **不被 invoke**(monkeypatch + count == 0 守门)+ finish_gate
    report blocker 不含**任何** validate-related type(`openspec_validate_failed` /
    `openspec_cli_missing` / `openspec_validate_error`)+ warning 含 rationale prefix。
    沿 specs.md Scenario 6(archived skip)+ Scenario 11(monkeypatch invocation count
    必备,round 1 codex F3 inline writeback)+ design.md D-OpenSpecValidateArchiveSkip +
    D-DispatchPathDetection round 1 修订。
    """
    # 在 tmp_path 内建立 archive/ 路径布局,模拟 openspec/changes/archive/<id>/
    # 用 ChangeBuilder 等价 helper 在 archived 布局下建 fixture(沿 codex F3 推荐)
    archive_id = "2026-05-06-fc-archive"
    # repo = tmp_path; archive_dir(repo) = tmp_path/openspec/changes/archive
    archived_change_dir = tmp_path / "openspec" / "changes" / "archive" / archive_id
    archived_change_dir.mkdir(parents=True)
    b = make_complete_change(archived_change_dir.parent, archive_id)
    # monkeypatch run_openspec_validate 计数 invocation(沿 codex F3 + active path test 同款 pattern)
    invoked = {"count": 0}
    def _spy(repo, change_id):
        invoked["count"] += 1
        # 返回 sentinel blocker 让"如果被错误 invoke 则 fence 会报"的路径走通,test 仍能区分
        return fg.Blocker(
            type="openspec_validate_failed",
            detail="sentinel - this should NOT be reachable in archive path",
        )
    monkeypatch.setattr(fg, "run_openspec_validate", _spy)
    report = fg.build_report(
        repo=tmp_path,
        change_id=archive_id,
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=False,  # 意图 invoke,但 archive 路径应触发 skip 不进 _spy
    )
    # 核心 assert:invocation count == 0(round 1 F3 inline writeback)
    assert invoked["count"] == 0, (
        f"archive path MUST skip run_openspec_validate (count == 0); "
        f"got count={invoked['count']}; round 1 F3 守门"
    )
    # 拒绝任何 validate-related blocker type(env 无 CLI 也 false-pass 守门)
    types = [blk.type for blk in report.blockers]
    for forbidden in ("openspec_validate_failed", "openspec_cli_missing", "openspec_validate_error"):
        assert forbidden not in types, (
            f"archive path skip MUST not produce {forbidden!r} blocker; got types: {types}"
        )
    # warning 含 skip rationale(audit trail)
    assert any("openspec_validate_skipped" in w for w in report.warnings), (
        f"archive path skip should emit rationale warning; got warnings: {report.warnings}"
    )


def test_finish_gate_invokes_openspec_validate_when_repo_path_contains_archive_segment(
    tmp_path, monkeypatch,
):
    """repo 整体路径含 ``archive`` segment(如 ``tmp_path / "archive" / "repo"`` —
    repo 父目录名是 ``archive``)+ active change → ``run_openspec_validate`` **仍被
    invoke**(monkeypatch + count == 1)。守门 round 1 codex F1 高危 finding:
    旧 ``"archive" in Path(change_dir).parts`` 检测在此场景 false-positive,让
    active change 的 openspec validate BLOCKER 漏报。沿 specs.md Scenario 9(repo 父
    目录路径 segment false-positive 守门)+ design.md D-DispatchPathDetection round 1
    修订(改用 ``change_dir.is_relative_to(_common.archive_dir(repo))``)。
    """
    # 构造 repo 父目录名是 'archive' 的场景
    repo = tmp_path / "archive" / "repo"
    repo.mkdir(parents=True)
    # 在该 repo 下建 active change(不在 archive subtree)
    active_id = "fc-active-under-archive-parent"
    b = make_complete_change(repo, active_id)
    # monkeypatch run_openspec_validate 计数
    invoked = {"count": 0}
    def _spy(repo_arg, change_id):
        invoked["count"] += 1
        return None  # active path success,不报 blocker
    monkeypatch.setattr(fg, "run_openspec_validate", _spy)
    fg.build_report(
        repo=repo,
        change_id=active_id,
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=False,
    )
    # 关键 assert:active change 即使 repo 父目录含 'archive' 仍 invoke validation(F1 守门)
    assert invoked["count"] == 1, (
        f"active change MUST invoke run_openspec_validate (count == 1) even when "
        f"repo path contains 'archive' segment; got count={invoked['count']}; round 1 F1 守门"
    )


def test_check_tasks_unchecked_archived_p9_doc_sync_gate_blocks(tmp_path):
    """archived ``## P9 — Documentation Sync Gate``(workflow prerequisite stage,
    doc sync gate 在 finish gate 之前)unchecked 项 MUST 报 blocker — archived format
    threshold ≥10 → P9 < 10 不 self-stage skip。沿 specs.md Scenario 8(archived P9
    prereq block)+ design.md D-PerFormatThreshold(round 1 codex F2 inline writeback)。
    """
    b = make_complete_change(tmp_path, "fc-tu-archived-p9-prereq")
    custom_tasks = (
        "# Tasks: fc-tu-archived-p9-prereq\n\n"
        "## P0 — 命令模板更新\n\n"
        "- [x] P0.1 done\n\n"
        "## P9 — Documentation Sync Gate\n\n"
        "- [ ] P9.1 sync gate items closed\n"
        "- [ ] P9.2 doc drift 标记\n"
    )
    b.write_tasks(content=custom_tasks)
    blockers = fg.check_tasks_unchecked(b.change_dir)
    types = [blk.type for blk in blockers]
    # archived P9 < threshold ≥10 → 必报 tasks_unchecked(prereq 漏报 fail-loud)
    assert "tasks_unchecked" in types, (
        f"archived `## P9 — Documentation Sync Gate` (workflow prerequisite) unchecked "
        f"items MUST block; archived format threshold ≥10 → P9=9 < 10 not self-stage; "
        f"got types: {types}"
    )
    # 详细确认两条 P9.x unchecked 都被标
    p9_blockers = [
        blk for blk in blockers
        if "P9.1 sync gate items closed" in blk.detail or "P9.2 doc drift" in blk.detail
    ]
    assert len(p9_blockers) == 2, (
        f"both P9.1 + P9.2 unchecked items must block; got: "
        f"{[(blk.type, blk.detail) for blk in p9_blockers]}"
    )


def test_finish_gate_invokes_openspec_validate_for_active_path(tmp_path, monkeypatch):
    """active change(``change_dir`` 不含 ``archive`` segment)→ ``run_openspec_validate``
    仍 invoke(backward-compat 守门)。沿 specs.md Scenario 5(active 路径仍 invoke)。
    用 monkeypatch 拦截 ``run_openspec_validate`` 验证它被调用。
    """
    b = make_complete_change(tmp_path, "fc-active-path")
    invoked = {"count": 0}
    real_validate = fg.run_openspec_validate
    def _spy(repo, change_id):
        invoked["count"] += 1
        return real_validate(repo, change_id)
    monkeypatch.setattr(fg, "run_openspec_validate", _spy)
    fg.build_report(
        repo=tmp_path,
        change_id="fc-active-path",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=False,
    )
    assert invoked["count"] == 1, (
        f"active path should invoke run_openspec_validate exactly 1 time (backward-compat); "
        f"got {invoked['count']}"
    )


def test_archive_segment_detection_uses_path_parts_not_substring(tmp_path, monkeypatch):
    """active change 名含 ``archive`` 子串(e.g., ``add-archive-feature``)但路径不含
    ``archive`` segment → 不应被检测为 archive 路径(active 行为不变,继续 invoke
    openspec validate)。沿 specs.md Scenario 7(Path.parts 检测稳定性)+ design.md
    D-DispatchPathDetection。
    """
    # change_dir = openspec/changes/add-archive-feature/(active,但名含 'archive' 子串)
    b = make_complete_change(tmp_path, "add-archive-feature")
    invoked = {"count": 0}
    real_validate = fg.run_openspec_validate
    def _spy(repo, change_id):
        invoked["count"] += 1
        return real_validate(repo, change_id)
    monkeypatch.setattr(fg, "run_openspec_validate", _spy)
    fg.build_report(
        repo=tmp_path,
        change_id="add-archive-feature",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=False,
    )
    # active path: substring contains 'archive' 但 segment 不含 'archive' → 仍 invoke
    assert invoked["count"] == 1, (
        f"active change containing 'archive' substring in name (NOT segment) should still "
        f"invoke openspec validate (Path.parts segment detection); got {invoked['count']}"
    )
```

- [ ] **Step 2: 跑 7 case 全 fail(red)**

```bash
python -m pytest tests/unit/test_forgeue_finish_gate.py -k "p_prefixed or yagni or p_non_digit or archive_path or active_path or path_parts" -v
```

Expected:7 case 全 FAIL(因 implementation 还没改,regex / archive 检测都不在;TDD red 阶段正确状态)

具体 expected error:
- `test_check_tasks_unchecked_recognizes_p_prefixed_em_dash`:assert blockers == [] fail(报多个 tasks_unchecked)
- `test_check_tasks_unchecked_p_prefix_optional_active_format_unchanged`:**应该 PASS**(P-prefix optional 是 superset,active 格式仍命中)— 若此 case fail 说明既有 baseline 已破,return back
- `test_check_tasks_unchecked_yagni_decimal_subsection_not_matched`:可能 PASS(因 baseline regex 也不命中 `## 1.5`)
- `test_check_tasks_unchecked_p_non_digit_not_matched`:可能 PASS(同上)
- `test_finish_gate_skips_openspec_validate_for_archive_path`:fail(archive 路径仍 invoke + 仍报 openspec_validate_failed blocker)
- `test_finish_gate_invokes_openspec_validate_for_active_path`:**应该 PASS**(active 路径本来就 invoke,backward-compat 守门)
- `test_archive_segment_detection_uses_path_parts_not_substring`:**应该 PASS**(active 路径本来就 invoke)

实际 red count 应在 2-3 之间(p_prefixed 大概率 fail + archive_path fail;其他 case 是 backward-compat 守门可能 baseline 已 PASS)。

- [ ] **Step 3: Commit**(controller 决定;implementer return 时报告 fail count + case 分布即可)

**Return to controller**:7 case 加完 + 实测 fail / pass 分布 + 7 case test code 路径(line range)。

---

## task_p2_tdd_green (tasks.md#3.1-3.4)

**Phase**:P2 — TDD green 实施修复 + 跑 7 case 全绿 + 全套 pytest 不 regression

**Files**:
- Modify: `tools/forgeue_finish_gate.py:1385`(regex 1 行扩展)
- Modify: `tools/forgeue_finish_gate.py:1567-1570 周边`(在 `if not no_validate:` block 内或 `build_report` 内加 archive segment 检测分流)

**Task content**:

- [ ] **Step 1: 修改 `_SECTION_HEADING_RE` regex(D-RegexExtension round 1 修订)+ per-format threshold(D-PerFormatThreshold)**

`tools/forgeue_finish_gate.py:1385`:

```python
# 原:
# _SECTION_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)

# 改:支持双格式 + 双 capture group 暴露 P-prefix 标识
# group(1) = "P" or None(P-prefix 标识,选 per-format threshold);group(2) = section integer
# (?:\.|\s+—) non-capturing alternation 匹配 `.`(active)或 `\s+—`(archived em-dash U+2014)
# 沿 design.md D-RegexExtension(round 1 codex F2 inline writeback 修订)。
_SECTION_HEADING_RE = re.compile(r"^##\s+(P)?(\d+)(?:\.|\s+—)\s+", re.MULTILINE)
```

`check_tasks_unchecked` 函数体改 — 选 per-format threshold(沿 D-PerFormatThreshold):

```python
def check_tasks_unchecked(change_dir: Path) -> list[Blocker]:
    tasks_path = change_dir / "tasks.md"
    if not tasks_path.is_file():
        return []
    try:
        text = tasks_path.read_text(encoding="utf-8")
    except OSError:
        return []
    blockers: list[Blocker] = []
    current_section: int | None = None
    current_threshold: int = _SELF_STAGE_SECTION_THRESHOLD  # default active 阈值
    for ln_no, line in enumerate(text.splitlines(), 1):
        section_match = _SECTION_HEADING_RE.match(line)
        if section_match:
            try:
                current_section = int(section_match.group(2))  # group(2) = integer
            except ValueError:
                current_section = None
            # per-format threshold(沿 D-PerFormatThreshold round 1 codex F2):
            # group(1) == "P" → archived 格式,threshold ≥10(P0-P9 全 prerequisite 应 block)
            # group(1) is None → active 格式,threshold ≥9(原 baseline,P8 finish gate = section 9)
            if section_match.group(1) == "P":
                current_threshold = _SELF_STAGE_SECTION_THRESHOLD_ARCHIVED  # = 10
            else:
                current_threshold = _SELF_STAGE_SECTION_THRESHOLD  # = 9(active)
            continue
        m = re.match(r"^- \[ \]\s+(.+)", line)
        if not m:
            continue
        rest = m.group(1)
        if "(SKIP" in rest or "(skip" in rest or "SKIP:" in rest:
            continue
        if current_section is not None and current_section >= current_threshold:
            # P8 self-stage / P9 archive / footer — finish_gate 是 these self-stage 的 gate
            continue
        blockers.append(
            Blocker(
                type="tasks_unchecked",
                detail=f"tasks.md:{ln_no}: {rest[:120]}",
                file="tasks.md",
            )
        )
    return blockers
```

并在常量段加 `_SELF_STAGE_SECTION_THRESHOLD_ARCHIVED = 10`(沿 D-PerFormatThreshold archived ≥10)。

**注意**:em-dash 是 U+2014 字面 unicode 字符(而非 `--` 半角双连字符)。Python 3 source 默认 UTF-8,直接写。

- [ ] **Step 2: 加 archive 路径检测分流(D-OpenSpecValidateArchiveSkip + D-DispatchPathDetection round 1 修订)**

`tools/forgeue_finish_gate.py:1567-1570` 周边修改 `build_report` 内 openspec validate 调用块。

原块:
```python
    if not no_validate:
        validate_blocker = run_openspec_validate(repo, change_id)
        if validate_blocker:
            blockers.append(validate_blocker)
```

改为(round 1 codex F1 inline writeback 修订:`is_relative_to(_common.archive_dir(repo))` repo-relative + segment-precise):
```python
    if not no_validate:
        # archive/ 路径下 skip openspec validate(沿 design.md D-OpenSpecValidateArchiveSkip):
        # upstream openspec CLI 不识别 `openspec/changes/archive/<dated-id>/` 路径,
        # 强制 invoke 必 fail 报噪声 BLOCKER。short-term mitigation 路径 skip + warning。
        # 长期方案给上游 openspec CLI 提 PR 留 follow-on `enhance-openspec-cli-archived-change-support`。
        # repo-relative + segment-precise 检测(沿 D-DispatchPathDetection round 1 codex F1
        # inline writeback 修订:旧 `"archive" in change_dir.parts` 在 repo 父目录名含
        # `archive` 时 false-positive 让 active change 静默漏报真 BLOCKER)。
        if change_dir.is_relative_to(_common.archive_dir(repo)):
            warnings.append(
                "openspec_validate_skipped: archive_path_unsupported_by_upstream_cli "
                "(change_dir is in archive/ subtree; openspec CLI doesn't recognize archived "
                "change ids; long-term fix tracked as follow-on enhance-openspec-cli-"
                "archived-change-support)"
            )
        else:
            validate_blocker = run_openspec_validate(repo, change_id)
            if validate_blocker:
                blockers.append(validate_blocker)
```

**注意**:
- `change_dir` 是 `Path` 对象(从 `_common.change_path(repo, change_id)` 返回)
- `_common.archive_dir(repo)` = `repo / "openspec" / "changes" / "archive"`(沿 `tools/_common.py:466-467`)
- `Path.is_relative_to(...)` 是 Python 3.9+ stdlib API,repo-relative + segment-precise + 跨 archive layout 未来变化 robust
- warning 字符串 prefix `openspec_validate_skipped:` 测试需匹配(沿 test_finish_gate_skips_openspec_validate_for_archive_path)
- 实施前 grep 确认 `_common` 模块已 import 在 `forgeue_finish_gate.py` 内(应已 import,沿其他 fence 用法)

- [ ] **Step 3: 跑全部新增 9 case 全绿(green)**(round 1 codex F1+F2+F3 inline writeback 后,P1 加了 2 新 case + 改造 1 case → 9 case 总)

```bash
python -m pytest tests/unit/test_forgeue_finish_gate.py -k "p_prefixed or yagni or p_non_digit or archive_path or active_path or path_parts or under_archive_parent or archived_p9_doc_sync" -v
```

Expected:9 case 全 PASS(原 7 + F1 加 `test_finish_gate_invokes_openspec_validate_when_repo_path_contains_archive_segment` + F2 加 `test_check_tasks_unchecked_archived_p9_doc_sync_gate_blocks` + F3 改造 `test_finish_gate_skips_openspec_validate_for_archive_path` 加 monkeypatch)

- [ ] **Step 4: 跑全套 pytest_test_forgeue_finish_gate.py 不 regression**

```bash
python -m pytest tests/unit/test_forgeue_finish_gate.py -v
```

Expected:既有 case 全绿 + 7 新 case 绿;total ~150+ case PASS(retire P5 baseline 内 138 finish_gate case + 本 change 7 = 145 左右,具体以实际数为准)。无 FAIL / SKIP 异常。

- [ ] **Step 5: Commit**(controller 决定)

**Return to controller**:Step 1-4 done summary + 7 case PASS + 全套 finish_gate test 数 + 无 regression confirm + diff 文件 line range。

---

## task_p3_verify (tasks.md#4.1-4.4)

**Phase**:P3 — Verify L0 archived replay 实测 29 → 0 + L1 全套 pytest 1746 + 7 = 1753

**Files**:
- Run: `python tools/forgeue_finish_gate.py --change archive/...`(同 P0 Step 3 的 5 archive)
- Run: `python -m pytest -q`(全套)
- Create: `openspec/changes/fix-finish-gate-archived-replay-compat/verification/verify_report.md`

**Task content**:

- [ ] **Step 1: L0 — 跑 finish_gate replay archived 5 change 实测**

```bash
python tools/forgeue_finish_gate.py --change archive/2026-05-05-enhance-workflow-automation-runtime-enforcement
python tools/forgeue_finish_gate.py --change archive/2026-05-05-enhance-workflow-automation-executable-enforcement
python tools/forgeue_finish_gate.py --change archive/2026-05-06-restore-superpowers-worktree-consent-gate
python tools/forgeue_finish_gate.py --change archive/2026-05-06-enhance-workflow-automation-ledger-binding
python tools/forgeue_finish_gate.py --change archive/2026-05-06-retire-parallel-and-worktree-fully
```

Expected post-fix(沿 design.md Goals 对账 29 → 0 标准 + round 1 codex F2 archived ≥10 threshold 修订;archived P0-P9 的 unchecked 应 block 但**这 5 archived change 实际 P0-P9 全 done [x]**,所以仍预期 `tasks_unchecked` = 0):

| Archive | tasks_unchecked | openspec_validate_failed | total | warnings |
|---------|-----------------|--------------------------|-------|----------|
| runtime-enforcement | **0** | **0**(skip) | **0** | 1 (skipped rationale) |
| executable-enforcement | **0** | **0**(skip) | **0** | 1 |
| restore-consent-gate | **0** | **0**(skip) | **0** | 1 |
| ledger-binding | **0** | **0**(skip) | **0** | 1 |
| retire | **0** | **0**(skip) | **0** | 1 |
| **总** | **0** | **0** | **0** | **5** |

`tasks_unchecked` 25 → 0(P10/P11 self-stage 由 archived ≥10 threshold skip;P0-P9 prereq 因 实测 5 archived change P0-P9 全 [x] 不报);`openspec_validate_failed` 4-5 → 0(archive subtree skip);warnings 含 skip rationale audit trail。

**注意**:若 P3 实测某 archived change P0-P9 仍有 unchecked 项(workflow prereq 漏报),应正常 block(沿 D-PerFormatThreshold archived ≥10 fail-loud 语义)— 这是修复 round 1 F2 的**期望**新行为(prereq fail-loud 而非静默 skip),不是 regression。implementer return 时报告实测每 change blocker 数 + 若有 P0-P9 unchecked block 则附 detail。

若实测与 expected 不符 → return back to controller(不自行 fix;契约违反需要 controller 决策)。

- [ ] **Step 2: L1 — 跑全套 pytest 不 regression**

```bash
python -m pytest -q 2>&1 | tail -20
```

Expected:1753 passed(retire P5 baseline 1746 + 本 change 7 新 case)+ 1 skipped(retire 既有 pre-existing skip 不 regression)+ 0 failed。

(若 pre-existing 1 fail 仍在 — 沿 retire P5 实测 `test_real_cross_check_files_have_evidence_type` pre-existing fail 已被 retire 标记;不阻断)

- [ ] **Step 3: 写 verification/verify_report.md**

落 `openspec/changes/fix-finish-gate-archived-replay-compat/verification/verify_report.md`,内容含:

- 12-key audit frontmatter(`evidence_type: verify_report`,`stage: S5`,`triggered_by_command: change-apply-subagent`,`runtime_enforcement_protocol_version: v1`,`task_granularity: phase`,`autonomy_decision: claude_autonomous`)
- L0 archived 5 change replay 对账表(P0 baseline vs P3 实测 + Δ + status)
- L1 pytest 数 + pre-existing fail 状态
- D-ArchivedReplayCompat 修订 criterion:archived 4 change replay 噪声 baseline 从 29 → 0 truly hold
- P4(codex review hook)进入条件 checklist

- [ ] **Step 4: Commit**(controller 决定)

**Return to controller**:Step 1-3 done + L0 实测对账表 + L1 数 + verify_report.md 路径 + (若有 anomaly)return reason。

---

## Self-Review checklist(controller 主 session 跑;不在 implementer 范围)

- [x] Spec coverage:specs.md 11 scenario(round 1 codex F1+F2+F3 加 4 new)是否每个都有 task 覆盖?
  - Scenario 1(active backward-compat)→ task_p1 test_check_tasks_unchecked_p_prefix_optional_active_format_unchanged
  - Scenario 2(archived 命中)→ task_p1 test_check_tasks_unchecked_recognizes_p_prefixed_em_dash
  - Scenario 3(假阴性 1.5)→ task_p1 test_check_tasks_unchecked_yagni_decimal_subsection_not_matched
  - Scenario 4(假阴性 PX)→ task_p1 test_check_tasks_unchecked_p_non_digit_not_matched
  - Scenario 5(active 路径仍 invoke)→ task_p1 test_finish_gate_invokes_openspec_validate_for_active_path
  - Scenario 6(archived 路径 skip)→ task_p1 test_finish_gate_skips_openspec_validate_for_archive_path(改造 monkeypatch + count == 0)
  - Scenario 7(`is_relative_to` 稳定性 active 名含 `archive` 子串不 false-positive)→ task_p1 test_archive_segment_detection_uses_path_parts_not_substring(改造)
  - Scenario 8(archived P9 prereq block)→ task_p1 test_check_tasks_unchecked_archived_p9_doc_sync_gate_blocks(round 1 F2 新加)
  - Scenario 9(repo 父目录路径 segment 不 false-positive)→ task_p1 test_finish_gate_invokes_openspec_validate_when_repo_path_contains_archive_segment(round 1 F1 新加)
  - Scenario 10(archived P10 self-stage skip)→ task_p1 test_check_tasks_unchecked_recognizes_p_prefixed_em_dash(已含 P10/P11 unchecked skip 的 inline assert)
  - Scenario 11(monkeypatch invocation count 必备)→ task_p1 test_finish_gate_skips_openspec_validate_for_archive_path(改造覆盖)
  - **全 11 scenario covered ✓**(round 1 inline writeback 后)
- [x] Placeholder scan:无 TBD / TODO / "implement later" / "fill in details"
- [x] Type consistency:`change_dir` 在 build_report 内是 Path 对象(从 `_common.change_path(repo, change_id)` 返回);`Path.is_relative_to(...)` 是 Python 3.9+ stdlib API;`warnings` 是 list of str;`_common.archive_dir(repo)` = `repo / "openspec" / "changes" / "archive"`(`tools/_common.py:466-467`)
- [x] tasks.md# 锚点全部 referenced(P0 #1.1-1.4 / P1 #2.1-2.7 / P2 #3.1-3.4 / P3 #4.1-4.4)
- [x] codex round 1 inline writeback 完成(F1+F2+F3 全 accepted-codex,3 新 D-decision 修订/新增 + 4 新 scenario + 2 新 test case + 1 改造 test case)
