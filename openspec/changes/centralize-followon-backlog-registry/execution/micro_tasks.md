---
change_id: centralize-followon-backlog-registry
stage: S2
evidence_type: micro_tasks
contract_refs:
  - tasks.md
  - design.md
  - execution/execution_plan.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
created_at: 2026-05-07T14:20:00Z
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
    - superpowers:brainstorming
  cascade_check_pass_at: 2026-05-07T14:20:00Z
---

# centralize-followon-backlog-registry Micro-tasks

> Per-task TDD 步骤 + actual code + commit 指引。沿 ForgeUE protocol(`/forgeue:change-apply-subagent`,memory `feedback_self_reference_overcaution.md` 强制):P2.a-h fence + P3 change_state 子命令 + tests 派 subagent(implementer + spec_review + code_quality_review + final_review);P0 / P1 / P4-P8 走 controller 主流程 direct。每 sub-task 走 red → green → commit;commit message 含 `tasks.md#PX.Y` anchor + subagent evidence ref。

## P0. Baseline + 22 项 backfill 数据源准备

### tasks.md#P0.1 跑 baseline pytest

- [ ] 跑 `python -m pytest -q` 期望 `1753 passed`(retire P5 + fix-finish-gate-archived-replay-compat 7 case)
- [ ] 若 fail → 检查 working tree 是否有遗留 modified file;不动其他 active change 的状态

### tasks.md#P0.2-P0.3 启动状态查询

- [ ] `python tools/forgeue_finish_gate.py --change centralize-followon-backlog-registry --json`(无 fence 实装前预期 PASS — fence 未触发新阻断)
- [ ] `python tools/forgeue_change_state.py --change centralize-followon-backlog-registry --json`(预期 state: S2)

### tasks.md#P0.4 backfill 数据源整理

- [ ] 从 `openspec/changes/archive/` 各 archived change 的 `tasks.md P11/P12/Pn (follow-on tracking)` + `verification/baseline.md` + `review/codex_*.md` 提取 7 项 workflow-protocol 描述 + source anchor + trigger 条件
- [ ] 从 `docs/requirements/SRS.md` §7.3 提取 9 项 active TBD pointer
- [ ] 从 `docs/design/LLD.md` + `CLAUDE.md` ComfyUI section grep `留 follow-on '<name>'` 内联注释提取 6 项 capability-boundary
- [ ] 整理 3 项 archived.md 首批 tombstone 数据(commit ref 准确性):
  - `enhance-workflow-automation-v2-fence-hardening`:`8a42c71`(实测 archived/2026-05-06-enhance-workflow-automation-ledger-binding archive 时 commit)
  - `fix-finish-gate-section-regex-for-p-prefixed`:`88a8aec`(实测 fix-finish-gate-archived-replay-compat archive commit)
  - `fix-openspec-validate-archived-change-support`:`88a8aec`(同上)

### tasks.md#P0.5 写 baseline.md

- [ ] 落 `openspec/changes/centralize-followon-backlog-registry/verification/baseline.md`,12-key audit frontmatter + 实测 pytest 1753 PASS + finish_gate / change_state 启动 JSON 截图 + 22 + 3 项 backfill 数据源汇总表

### Commit P0

```bash
git add openspec/changes/centralize-followon-backlog-registry/verification/baseline.md
git commit -m "$(cat <<'EOF'
feat(forgeue): centralize-followon-backlog-registry P0 — baseline + backfill data prep

Tasks: tasks.md#P0.1 P0.2 P0.3 P0.4 P0.5

- pytest 1753 PASS (retire P5 + fix-finish-gate-archived-replay-compat 7 case)
- finish_gate / change_state baseline JSON
- 22 active + 3 archived backfill data source consolidated

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## P1. Registry 文件创建

### tasks.md#P1.1 创建 `openspec/backlog/` 目录

- [ ] `mkdir -p openspec/backlog/`(沿 OpenSpec `changes/` / `specs/` 同级)

### tasks.md#P1.2 写 `openspec/backlog/README.md`

- [ ] Schema header 描述 8 字段:`id` / `source` / `description` / `trigger` / `category` / `retire-impact-status` / `priority` / `status`
- [ ] 双源关系说明:active.md 收 archive-tracking 类(workflow-protocol + capability-boundary)+ requirements-tbd-pointer 类(SRS §7.3 cross-link);SRS §7.3 仍是需求层 backlog
- [ ] 协议链接:`_check_followon_continuity` + `_check_srs_registry_consistency` fence 守门
- [ ] cross-link 同步策略简述(沿 design.md D-CrossLinkSync)

### tasks.md#P1.3 写 active.md schema header + 7 workflow-protocol entries

- [ ] schema header(8 字段说明 + 4 类 status enum)
- [ ] entry 模板(沿 spec.md scenario 1):
  ```markdown
  ### `<followon-id>`

  - **source**: `archived/<change-id>/tasks.md` § P12.X
  - **description**: <1-2 句 description>
  - **trigger**: <触发条件>
  - **category**: workflow-protocol
  - **retire-impact-status**: unaffected
  - **priority**: (空)
  - **status**: active
  ```
- [ ] 7 entries 写入(P1.3.1-P1.3.7,沿 design.md D-BackfillScope)

### tasks.md#P1.4 写 9 requirements-tbd-pointer entries

- [ ] 9 项 1 行 pointer entry(简化 schema — 仅 id + source + description + status):
  ```markdown
  ### `TBD-001`

  - **source**: `docs/requirements/SRS.md` §7.3 TBD-001
  - **description**: bridge_execute 模式启用条件
  - **category**: requirements-tbd-pointer
  - **status**: active
  ```
- [ ] 9 entries 写入

### tasks.md#P1.5 写 6 capability-boundary entries

- [ ] 6 entries(沿 LLD inline 注释):
  ```markdown
  ### `audio-metadata-parser`

  - **source**: `docs/design/LLD.md` §<section> + `openspec/specs/examples-and-acceptance/spec.md` ≈line
  - **description**: AudioCandidate.duration_seconds / sample_rate parser
  - **trigger**: 第一个 audio metadata-aware use case
  - **category**: capability-boundary
  - **retire-impact-status**: unaffected
  - **priority**: (空)
  - **status**: active
  ```

### tasks.md#P1.6 写 `archived.md` schema + 3 tombstone

- [ ] Schema header(append-only 协议 + 4 字段说明 + git diff 守门提示)
- [ ] 3 tombstone entries(沿 spec.md scenario `tombstone schema with all 4 fields`):
  ```markdown
  ### `enhance-workflow-automation-v2-fence-hardening`

  - **archived_at_commit**: 8a42c71...(40-char full sha,`git rev-parse 8a42c71` 取整)
  - **archived_in_change**: enhance-workflow-automation-ledger-binding
  - **cancellation_reason**: cancelled-superseded by enhance-workflow-automation-ledger-binding
  - **registry_entry_snapshot**: {"id":"enhance-workflow-automation-v2-fence-hardening","source":"archived/2026-05-05-enhance-workflow-automation-executable-enforcement/tasks.md § P12.8","description":"v2 _check_dispatch_ledger 7-field schema + path traversal validation","category":"workflow-protocol","status":"cancelled-superseded"}
  ```
- [ ] 第 2 + 3 tombstone(`fix-finish-gate-section-regex-for-p-prefixed` + `fix-openspec-validate-archived-change-support` 同款 schema,`archived_at_commit: 88a8aec...`)

### tasks.md#P1.7 改 `docs/requirements/SRS.md` §7.3 cross-link

- [ ] 在 §7.3 "未决事项"标题下加 header note(放表前):
  ```markdown
  > **Cross-link**:本表是 requirements-tbd 类 backlog;workflow-protocol + capability-boundary 类 follow-on backlog 见 [`openspec/backlog/active.md`](../../openspec/backlog/active.md)(自 `centralize-followon-backlog-registry` change 起,2026-05-07)。
  ```
- [ ] 不改 §7.3 表本体(双源不重复)

### Commit P1

```bash
git add openspec/backlog/ docs/requirements/SRS.md
git commit -m "$(cat <<'EOF'
feat(forgeue): centralize-followon-backlog-registry P1 — registry files (active.md + archived.md + README + SRS cross-link)

Tasks: tasks.md#P1.1 P1.2 P1.3.1-7 P1.4 P1.5 P1.6 P1.7

- openspec/backlog/active.md: 22 entries (7 wf-protocol + 9 SRS pointer + 6 cap-boundary)
- openspec/backlog/archived.md: 3 first-batch tombstones
- openspec/backlog/README.md: protocol description
- docs/requirements/SRS.md §7.3: cross-link header note

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## P2.a — Markdown 解析 helpers

### tasks.md#P2.a.1 `_extract_followon_tracking_section`

**Files**: Modify `tools/forgeue_finish_gate.py`(append helper after existing private helpers)

- [ ] **Step 1: 写 failing test** at `tests/unit/test_forgeue_finish_gate.py`(append):

```python
def test_extract_followon_tracking_section_finds_unchecked_p12():
    from tools.forgeue_finish_gate import _extract_followon_tracking_section
    tasks_md_content = """
## P0 (baseline)
- [x] 1.1 baseline

## P12 (follow-on tracking)
- [ ] P12.1 (follow-on tracking): **followon-a** — desc
- [x] P12.2 (follow-on tracking): **followon-b** [cancelled-completed: abc1234] — desc
"""
    tmp_path.joinpath("tasks.md").write_text(tasks_md_content, encoding="utf-8")
    items = _extract_followon_tracking_section(tmp_path / "tasks.md")
    assert items["unchecked"] == ["followon-a"]
    assert items["resolved"] == [
        {"id": "followon-b", "tag_type": "cancelled-completed", "tag_value": "abc1234"}
    ]
```

- [ ] **Step 2: 跑 fail**:`pytest tests/unit/test_forgeue_finish_gate.py::test_extract_followon_tracking_section_finds_unchecked_p12 -v` 期望 `ImportError` or `AttributeError`

- [ ] **Step 3: 写 minimal implementation** at `tools/forgeue_finish_gate.py`:

```python
import re
from pathlib import Path
from typing import TypedDict

_FOLLOWON_SECTION_HEADING_RE = re.compile(
    r"^##\s+(?:P\d+\s*[—-]?\s*|Phase\s+\d+\s+|\d+\.\s+P\d+\s+—\s+).*\(follow-on\s+tracking\)",
    re.MULTILINE,
)
_FOLLOWON_ITEM_RE = re.compile(
    r"^-\s+\[(\s|x)\]\s+P\d+(?:\.\d+)?(?:\s+\(follow-on\s+tracking\))?\s*[:：]\s*\*\*(?P<id>[a-z0-9-]+)\*\*"
    r"(?:\s+\[(?P<tag_type>cancelled-superseded|cancelled-not-applicable|cancelled-completed)(?:\s+by\s+|:\s*)(?P<tag_value>[^\]]+)\])?",
    re.MULTILINE,
)

def _extract_followon_tracking_section(tasks_md_path: Path) -> dict[str, list]:
    text = tasks_md_path.read_text(encoding="utf-8")
    section_match = _FOLLOWON_SECTION_HEADING_RE.search(text)
    if not section_match:
        return {"unchecked": [], "resolved": []}
    section_start = section_match.start()
    next_h2 = re.search(r"^##\s+", text[section_match.end():], re.MULTILINE)
    section_end = section_match.end() + next_h2.start() if next_h2 else len(text)
    section_text = text[section_start:section_end]
    unchecked: list[str] = []
    resolved: list[dict] = []
    for m in _FOLLOWON_ITEM_RE.finditer(section_text):
        checked = m.group(1) == "x"
        item_id = m.group("id")
        tag_type = m.group("tag_type")
        tag_value = (m.group("tag_value") or "").strip()
        if checked and tag_type:
            resolved.append({"id": item_id, "tag_type": tag_type, "tag_value": tag_value})
        elif not checked:
            unchecked.append(item_id)
    return {"unchecked": unchecked, "resolved": resolved}
```

- [ ] **Step 4: 跑 PASS**:同 step 2 命令期望 PASS

### tasks.md#P2.a.2 `_find_latest_archived_change`

- [ ] **Step 1: 写 test**:

```python
def test_find_latest_archived_change_returns_most_recent(tmp_path, monkeypatch):
    from tools.forgeue_finish_gate import _find_latest_archived_change
    archive_dir = tmp_path / "openspec" / "changes" / "archive"
    archive_dir.mkdir(parents=True)
    (archive_dir / "2026-05-06-retire-parallel-and-worktree-fully").mkdir()
    (archive_dir / "2026-05-07-fix-finish-gate-archived-replay-compat").mkdir()
    monkeypatch.chdir(tmp_path)
    result = _find_latest_archived_change()
    assert result.name == "2026-05-07-fix-finish-gate-archived-replay-compat"
```

- [ ] **Step 2-4 红→绿**:实装 `_find_latest_archived_change`:

```python
def _find_latest_archived_change(repo: Path | None = None) -> Path | None:
    repo = repo or Path.cwd()
    archive_root = repo / "openspec" / "changes" / "archive"
    if not archive_root.is_dir():
        return None
    candidates = sorted(
        (p for p in archive_root.iterdir() if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}-", p.name)),
        key=lambda p: p.name,
        reverse=True,
    )
    return candidates[0] if candidates else None
```

### tasks.md#P2.a.3 `_parse_registry_md`

- [ ] **Step 1: 写 test**:

```python
def test_parse_registry_md_extracts_8_field_entries(tmp_path):
    from tools.forgeue_finish_gate import _parse_registry_md
    registry = tmp_path / "active.md"
    registry.write_text("""
# Active Follow-on Backlog

### `entry-a`

- **source**: archived/foo/tasks.md
- **description**: foo desc
- **trigger**: foo trigger
- **category**: workflow-protocol
- **retire-impact-status**: unaffected
- **priority**: high
- **status**: active

### `entry-b`

- **source**: SRS.md §7.3
- **description**: bar
- **category**: requirements-tbd-pointer
- **status**: active
""", encoding="utf-8")
    entries = _parse_registry_md(registry)
    assert set(entries.keys()) == {"entry-a", "entry-b"}
    assert entries["entry-a"]["status"] == "active"
    assert entries["entry-a"]["category"] == "workflow-protocol"
```

- [ ] **Step 2-4 红→绿**:实装 `_parse_registry_md`(沿 既有 `_parse_yaml_subset` 风格)

### tasks.md#P2.a.4 `_parse_archived_md`

- [ ] **Step 1: 写 test**(沿 spec.md scenario `tombstone schema with all 4 fields passes parse`)
- [ ] **Step 2-4 红→绿**:实装 `_parse_archived_md` 解析 4 字段(`archived_at_commit` / `archived_in_change` / `cancellation_reason` / `registry_entry_snapshot`)

### Commit P2.a

```bash
git add tools/forgeue_finish_gate.py tests/unit/test_forgeue_finish_gate.py
git commit -m "feat(forgeue): centralize-followon-backlog-registry P2.a — Markdown 解析 helpers (4 functions)

Tasks: tasks.md#P2.a.1 P2.a.2 P2.a.3 P2.a.4

- _extract_followon_tracking_section
- _find_latest_archived_change
- _parse_registry_md (active.md schema)
- _parse_archived_md (archived.md tombstone schema)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P2.b — Fence 阶段 1:active.md self-diff(F1 + F1-r2 + F2-r2 fix)

### tasks.md#P2.b.1-P2.b.5

- [ ] **Step 1: 写 test**(沿 spec.md scenarios "active.md entry deletion without tombstone" + "self-diff baseline anchors to last archive commit"):

```python
def test_followon_continuity_baseline_anchors_to_archive_commit_not_active_md_path(tmp_path, monkeypatch):
    """Round 2 F1-r2 fix: baseline must come from latest archive directory commit,
    not from `git log -1 -- active.md` (which would track active.md mods and miss
    early-commit deletions in the current change)."""
    # Setup: tmp git repo + archived dir + active.md with entry-X
    # Simulate early-commit deletion of entry-X from active.md without tombstone
    # Run fence; expect tombstone_missing_for_entry-X BLOCKER
    ...
```

- [ ] **Step 2-4 红→绿**:实装 `_get_change_baseline_commit` + `_get_active_md_at_commit` + `_diff_registry_entries` + `_validate_tombstone_consistency` + 主流程 self-diff 校验

```python
def _get_change_baseline_commit(repo: Path) -> str | None:
    """Round 2 F1-r2 fix: baseline = last archive commit (anchor to archived dir
    last touched commit), NOT active.md path commit (which drifts when current
    change commits modify active.md)."""
    latest_archived = _find_latest_archived_change(repo)
    if latest_archived is None:
        return None
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", str(latest_archived)],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    sha = result.stdout.strip()
    return sha if sha else None

def _get_active_md_at_commit(repo: Path, sha: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{sha}:openspec/backlog/active.md"],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    return result.stdout if result.returncode == 0 else ""

def _diff_registry_entries(prior: dict, current: dict) -> dict[str, list[str]]:
    prior_ids = set(prior.keys())
    current_ids = set(current.keys())
    return {
        "added": list(current_ids - prior_ids),
        "removed": list(prior_ids - current_ids),
        "status_changed_to_cancelled": [
            id_ for id_ in (prior_ids & current_ids)
            if prior[id_].get("status") == "active"
            and current[id_].get("status", "").startswith("cancelled-")
        ],
    }

def _validate_tombstone_consistency(
    tombstone: dict,
    baseline_entry: dict,
    current_change_id: str,
    tasks_cancel_tag: dict,
) -> str | None:
    """Round 2 F2-r2 fix: 5-point consistency check for tombstone vs baseline + cancel tag."""
    import json
    if tombstone.get("id") != baseline_entry.get("id"):
        return f"tombstone_id_mismatch_got_{tombstone.get('id')}_expected_{baseline_entry.get('id')}"
    snapshot_raw = tombstone.get("registry_entry_snapshot", "")
    try:
        snapshot = json.loads(snapshot_raw) if isinstance(snapshot_raw, str) else snapshot_raw
    except json.JSONDecodeError:
        return f"tombstone_snapshot_invalid_{tombstone.get('id')}_malformed_json"
    if not isinstance(snapshot, dict):
        return f"tombstone_snapshot_invalid_{tombstone.get('id')}_not_object"
    required = {"id", "source", "description", "trigger", "category", "retire-impact-status", "priority", "status"}
    missing = required - set(snapshot.keys())
    if missing:
        return f"tombstone_snapshot_invalid_{tombstone.get('id')}_missing_field_{','.join(sorted(missing))}"
    for field in ("category", "source"):  # critical fields that must match baseline
        if snapshot.get(field) != baseline_entry.get(field):
            return f"tombstone_snapshot_mismatch_{tombstone.get('id')}_{field}_got_{snapshot.get(field)}_baseline_{baseline_entry.get(field)}"
    if tombstone.get("archived_in_change") != current_change_id:
        return f"tombstone_archived_in_change_mismatch_{tombstone.get('id')}_got_{tombstone.get('archived_in_change')}_expected_{current_change_id}"
    expected_reason_prefix = tasks_cancel_tag.get("type")  # cancelled-superseded | cancelled-not-applicable | cancelled-completed
    if not tombstone.get("cancellation_reason", "").startswith(expected_reason_prefix):
        return f"tombstone_cancellation_reason_mismatch_{tombstone.get('id')}_tombstone_{tombstone.get('cancellation_reason')}_tasks_{expected_reason_prefix}"
    return None
```

### Commit P2.b

```bash
git commit -m "feat(forgeue): centralize-followon-backlog-registry P2.b — fence stage 1 active.md self-diff + tombstone consistency (F1 + F1-r2 + F2-r2 fix)

Tasks: tasks.md#P2.b.1 P2.b.2 P2.b.3 P2.b.4 P2.b.5
- Round 1 F1: active.md hard source-of-truth + tombstone protocol
- Round 2 F1-r2: baseline anchors to last archive commit (not active.md path commit)
- Round 2 F2-r2: 5-point tombstone consistency check (id + snapshot 8-fields + archived_in_change + cancellation_reason vs tasks tag)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P2.c — Fence 阶段 2:archived tasks.md 兜底源

### tasks.md#P2.c.1

- [ ] **Step 1: 写 test**(`test_check_followon_continuity_archived_tasks_md_unchecked_blocks` + `test_check_followon_continuity_no_p12_section_in_latest_archive_passes` 沿 fix-finish-gate-archived-replay-compat 实测样例 88a8aec)
- [ ] **Step 2-4 红→绿**:fence 主流程兜底源调用 P2.a.1 helper + 与本 change tasks.md 同款 section 比对;缺漏 BLOCKER `archived_followon_not_declared_<id>`

### Commit P2.c

```bash
git commit -m "feat(forgeue): centralize-followon-backlog-registry P2.c — fence stage 2 archived tasks.md fallback source

Tasks: tasks.md#P2.c.1

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P2.d — Fence 阶段 3:cancel ref strict validation(F2 fix)

### tasks.md#P2.d.1 `_validate_cancel_tag_superseded`

- [ ] **Step 1: 写 test**(沿 spec.md scenarios "valid supersedes ref" PASS + "non-existent change-id" BLOCKER):

```python
def test_validate_cancel_tag_superseded_existing_id_passes(tmp_path, monkeypatch):
    from tools.forgeue_finish_gate import _validate_cancel_tag_superseded
    (tmp_path / "openspec" / "changes" / "real-change-id").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    assert _validate_cancel_tag_superseded("real-change-id") is None  # PASS

def test_validate_cancel_tag_superseded_nonexistent_id_blocks(tmp_path, monkeypatch):
    from tools.forgeue_finish_gate import _validate_cancel_tag_superseded
    monkeypatch.chdir(tmp_path)
    err = _validate_cancel_tag_superseded("fictional-change-id-xyz")
    assert err is not None
    assert "cancel_ref_not_found" in err
```

- [ ] **Step 2-4 红→绿**:

```python
def _validate_cancel_tag_superseded(change_id: str, repo: Path | None = None) -> str | None:
    repo = repo or Path.cwd()
    active_path = repo / "openspec" / "changes" / change_id
    archived_pattern = (repo / "openspec" / "changes" / "archive").glob(f"*-{change_id}")
    if active_path.is_dir() or any(archived_pattern):
        return None
    return f"cancel_ref_not_found_superseded_by_{change_id}"
```

### tasks.md#P2.d.2 `_validate_cancel_tag_not_applicable`(reason enum)

- [ ] **Step 1: 写 test**:

```python
_VALID_CANCEL_REASON_PREFIXES = frozenset({
    "retire-superseded", "out-of-scope", "scope-changed", "obsolete", "infeasible"
})

def test_validate_cancel_tag_not_applicable_enum_prefix_passes():
    from tools.forgeue_finish_gate import _validate_cancel_tag_not_applicable
    assert _validate_cancel_tag_not_applicable("out-of-scope (本 change 不修)") is None
    assert _validate_cancel_tag_not_applicable("retire-superseded") is None

def test_validate_cancel_tag_not_applicable_invalid_reason_blocks():
    from tools.forgeue_finish_gate import _validate_cancel_tag_not_applicable
    err = _validate_cancel_tag_not_applicable("我懒")
    assert err is not None
    assert "cancel_reason_not_in_enum" in err
```

- [ ] **Step 2-4 红→绿**:

```python
def _validate_cancel_tag_not_applicable(reason: str) -> str | None:
    first_token = reason.split(maxsplit=1)[0] if reason else ""
    first_token = first_token.rstrip(":,)")
    if first_token in _VALID_CANCEL_REASON_PREFIXES:
        return None
    return f"cancel_reason_not_in_enum_got_{first_token}"
```

### tasks.md#P2.d.3 `_validate_cancel_tag_completed`(round 2 F3-r2 fix:strict commit-touches + escape hatch)

- [ ] **Step 1: 写 test**(沿 spec scenarios "cancelled-completed with commit not touching follow-on source fails" + "cancelled-completed with evidence escape hatch passes")
- [ ] **Step 2-4 红→绿**:

```python
def _validate_cancel_tag_completed(
    tag: str,
    followon_entry: dict,
    repo: Path | None = None,
) -> str | None:
    """Round 2 F3-r2 fix: strict commit-touches + evidence escape hatch.

    tag format: '<commit-ref>' OR '<commit-ref> evidence: <path>'
    """
    repo = repo or Path.cwd()
    parts = tag.split(" evidence: ", maxsplit=1)
    commit_ref = parts[0].strip()
    evidence_path = parts[1].strip() if len(parts) == 2 else None

    # Step 3.1: commit existence
    result = subprocess.run(
        ["git", "rev-parse", "--verify", commit_ref],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return f"cancel_commit_not_found_got_{commit_ref}"

    # Step 3.2: get touched files
    diff_tree = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_ref],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    touched_files = set(diff_tree.stdout.strip().split("\n")) if diff_tree.returncode == 0 else set()

    # Step 3.3: relevant paths from follow-on entry
    relevant_paths = set()
    if followon_entry.get("source"):
        relevant_paths.add(followon_entry["source"].strip())
    contract_refs = followon_entry.get("contract_refs", [])
    if isinstance(contract_refs, list):
        relevant_paths.update(p.strip() for p in contract_refs)

    # Step 3.4: commit-touches intersection
    if touched_files & relevant_paths:
        return None  # PASS

    # Step 3.5: evidence escape hatch
    if evidence_path:
        if (repo / evidence_path).exists():
            return None  # PASS via escape
        return f"cancel_evidence_path_not_found_{commit_ref}_evidence_{evidence_path}"

    # Step 3.6: BLOCKER
    return f"cancel_commit_does_not_touch_followon_or_provide_evidence_got_{commit_ref}"
```

### tasks.md#P2.d.4 fence 主流程 cancel 校验

- [ ] **Step 1: 写 test**(`test_check_followon_continuity_dispatches_to_correct_validator`)
- [ ] **Step 2-4 红→绿**:fence 主流程 iter resolved entries(沿 P2.a.1 返回 dict),根据 tag_type 调对应 validator,汇总 BLOCKER

### Commit P2.d

```bash
git commit -m "feat(forgeue): centralize-followon-backlog-registry P2.d — cancel ref strict validation (F2 fix)

Tasks: tasks.md#P2.d.1 P2.d.2 P2.d.3 P2.d.4
Codex round 1 F2 inline writeback (5 reason enum + Path/git ref strict)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P2.e — archived.md append-only 校验

### tasks.md#P2.e.1-P2.e.2

- [ ] **Step 1: 写 test**(沿 spec scenario "deletion of an existing tombstone entry fails fence")
- [ ] **Step 2-4 红→绿**:实装 `_check_archived_md_append_only`(`subprocess.run(["git", "diff", prior_sha, "HEAD", "--", "openspec/backlog/archived.md"])` 输出 per-line 分析,deletion line 触及 entry block → BLOCKER)

### Commit P2.e

```bash
git commit -m "feat(forgeue): centralize-followon-backlog-registry P2.e — archived.md append-only protection

Tasks: tasks.md#P2.e.1 P2.e.2

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P2.f — fence dispatch loop register(round 3 codex F2-r3 inline writeback:TDD 端到端守门)

### tasks.md#P2.f.1-P2.f.5

- [ ] **Step 1: 写 failing TDD 红灯 test**(tests/unit/test_forgeue_finish_gate.py append):

```python
def test_check_followon_continuity_runs_via_build_report(tmp_path, monkeypatch):
    """Round 3 F2-r3 fix: end-to-end fence-register guardrail. If
    _check_followon_continuity is not registered into build_report dispatch
    loop, helper unit tests still pass but the fence is silently no-op'd
    at archive-stage finish_gate (false-green risk)."""
    # Setup: tmp git repo + fixture change with active.md entry-X removed without tombstone
    ...
    result = subprocess.run(
        ["python", "tools/forgeue_finish_gate.py", "--change", "<fixture-id>", "--json"],
        capture_output=True, text=True
    )
    assert result.returncode == 2  # BLOCKER
    assert "_check_followon_continuity" in result.stdout
    assert "tombstone_missing_for_entry-X" in result.stdout

def test_check_srs_registry_consistency_runs_via_build_report(tmp_path, monkeypatch):
    """Same end-to-end guardrail for SRS↔registry consistency fence."""
    # Setup: SRS §7.3 has TBD-XXX active but active.md missing pointer
    ...
    result = subprocess.run(
        ["python", "tools/forgeue_finish_gate.py", "--change", "<fixture-id>", "--json"],
        capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "_check_srs_registry_consistency" in result.stdout
    assert "srs_registry_set_mismatch" in result.stdout

def test_followon_fences_remain_registered():
    """Regression guard: prevent register tuple from being silently
    removed by future refactors."""
    from tools.forgeue_finish_gate import _FENCE_REGISTRY  # or equivalent
    fence_names = {name for name, _fn in _FENCE_REGISTRY}
    assert "_check_followon_continuity" in fence_names
    assert "_check_srs_registry_consistency" in fence_names
```

- [ ] **Step 2: 跑测试期望 fail**:`pytest tests/unit/test_forgeue_finish_gate.py::test_check_followon_continuity_runs_via_build_report -v` 期望 fail(fence 未 register)

- [ ] **Step 3: 在 `tools/forgeue_finish_gate.py` 主 dispatch loop 注册两 fence**(沿 既有 `_check_skill_cascade` 等 register 模式):

```python
# In _FENCE_REGISTRY tuple (or equivalent dispatch loop):
("_check_followon_continuity", _check_followon_continuity),
("_check_srs_registry_consistency", _check_srs_registry_consistency),
```

- [ ] **Step 4: 跑测试期望 PASS**:相同命令 + `test_check_srs_registry_consistency_runs_via_build_report` + `test_followon_fences_remain_registered` 全 PASS(green)

- [ ] **Step 5: fence 输出统一格式**:[PASS] / [FAIL] + reason list(沿 v1 advisory fence 出错信息风格)

### Commit P2.f

```bash
git commit -m "feat(forgeue): centralize-followon-backlog-registry P2.f — register followon fences with TDD end-to-end guardrail (round 3 F2-r3 inline writeback)

Tasks: tasks.md#P2.f.1 P2.f.2 P2.f.3 P2.f.4 P2.f.5

- TDD red→green: fence_register guardrail tests prove fences run via build_report
- Register _check_followon_continuity + _check_srs_registry_consistency
- Anti-regression test: assert both fences remain in dispatch tuple

Round 3 F2-r3 inline writeback (full CLI fixture exercises both new fences;
prevents implementer forgetting register from causing false-green at P5.3).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P2.g — SRS↔registry consistency fence(F3 fix)

### tasks.md#P2.g.1-P2.g.4

- [ ] **Step 1: 写 test**(沿 spec scenarios "SRS adds new TBD without registry pointer" + "SRS TBD completes but registry pointer remains active")
- [ ] **Step 2-4 红→绿**:实装 `_parse_srs_tbd_table` + `_check_srs_registry_consistency` fence(register 由 P2.f.3 一并完成 — round 3 F2-r3 inline writeback)

### Commit P2.g

```bash
git commit -m "feat(forgeue): centralize-followon-backlog-registry P2.g — _check_srs_registry_consistency fence (F3 fix)

Tasks: tasks.md#P2.g.1 P2.g.2 P2.g.3 P2.g.4
Codex round 1 F3 inline writeback (SRS↔registry set equivalence + state sync)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P2.h — Unit 测试 ~16 case

### tasks.md#P2.h.1-P2.h.6

每 sub-task 内包括前序 P2.b-P2.g 已写部分测试 + 补完整覆盖至 ~16 case:

- [ ] P2.h.1 happy-path 4 case(已部分在 P2.d.1-3 写)
- [ ] P2.h.2 strict validation 3 BLOCKER case(已部分在 P2.d.1-3 写)
- [ ] P2.h.3 active.md self-diff 3 case(2 已在 P2.b 写,补 status_changed-to-cancelled 1 case)
- [ ] P2.h.4 archived.md append-only 3 case(已部分在 P2.e 写,补 modify 1 case)
- [ ] P2.h.5 兜底源 2 case(已在 P2.c 写)
- [ ] P2.h.6 SRS↔registry consistency 3 case(已在 P2.g 写)
- [ ] **新增** `tests/unit/test_followon_registry.py`:registry schema parse + tombstone schema validation + 24 entry count(注:本 change scope 22 + 3 archive,test 用 fixture 校验 schema 而非数字)

### Commit P2.h

```bash
git commit -m "test(forgeue): centralize-followon-backlog-registry P2.h — unit tests 16 cases for fence + registry parser

Tasks: tasks.md#P2.h.1 P2.h.2 P2.h.3 P2.h.4 P2.h.5 P2.h.6
- test_forgeue_finish_gate.py +13 cases (followon fence + SRS consistency)
- test_followon_registry.py +3 cases (schema parse + tombstone)

pytest: 1753 -> 1769 passing (+16 new cases, 0 regression)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P3 — `forgeue_change_state.py` 子命令

### tasks.md#P3.1-P3.4

- [ ] P3.1 在 `tools/forgeue_change_state.py` argparse 加 `--list-followon-inherited` / `--list-followon-cancelled` flag
- [ ] P3.2 实装 `list_followon_inherited(change_dir)` 调用 P2.a.1 helper 提取 inherited entries
- [ ] P3.3 实装 `list_followon_cancelled(change_dir)` 提取 cancelled-* 分类
- [ ] P3.4 写 `tests/unit/test_forgeue_change_state.py::test_list_followon_*`(4-6 case)

### Commit P3

```bash
git commit -m "feat(forgeue): centralize-followon-backlog-registry P3 — change_state --list-followon-{inherited,cancelled} subcommands

Tasks: tasks.md#P3.1 P3.2 P3.3 P3.4

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P4 — 命令模板更新

### tasks.md#P4.1-P4.6

- [ ] P4.1 改 `change-finish.md` `## Preflight` 段加 followon continuity check 子段:调 aggregate `python tools/forgeue_finish_gate.py --change <id>`(沿既有 fence dispatch loop;两 fence P2.f register 后 build_report 自动 run;**round 3 F1-r3 inline writeback** — 删原 `--check-followon-continuity` 专用 flag 避免 argparse 失败)
- [ ] P4.2-P4.3 改 `change-status.md` 加 `### Followon Backlog` block + Steps 调 `--list-followon-*`
- [ ] P4.4-P4.5 改 `change-apply-{subagent,direct}.md` evidence frontmatter 模板加 `followon_continuity` 字段(可空)
- [ ] P4.6 跑 `pytest tests/unit/test_forgeue_workflow_plugin_invocation.py` 确认命令模板 markdown lint 不破

### Commit P4

```bash
git commit -m "feat(forgeue): centralize-followon-backlog-registry P4 — command templates (change-finish + change-status + change-apply-{subagent,direct})

Tasks: tasks.md#P4.1 P4.2 P4.3 P4.4 P4.5 P4.6

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P5 — Verify L0/L1/L2

### tasks.md#P5.1-P5.5

- [ ] P5.1 L0:`python tools/forgeue_verify.py --level 0 --change centralize-followon-backlog-registry`
- [ ] P5.2 L1:`python -m pytest -q` 期望 1769 PASS(+16 new cases vs P0 baseline 1753)
- [ ] P5.3 L2:`python tools/forgeue_finish_gate.py --change centralize-followon-backlog-registry --json` 全 fence PASS(含本 change 自家 _check_followon_continuity dogfood)
- [ ] P5.4 invoke `/codex:review --base main`(verification hook;预期 disputed_open=0 或 finding 全 inline writeback)
- [ ] P5.5 写 `verification/verify_report.md`(12-key + L0/L1/L2 + codex review writeback)

### Commit P5

```bash
git commit -m "feat(forgeue): centralize-followon-backlog-registry P5 — verify L0/L1/L2 + codex review hook

Tasks: tasks.md#P5.1 P5.2 P5.3 P5.4 P5.5

L0 PASS, L1 1769 PASS, L2 finish_gate PASS, codex review disputed_open=0

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P6 — Documentation Sync Gate

### tasks.md#P6.1-P6.12

详见 tasks.md;每文档单独 sub-task 写入对应内容(README + CLAUDE/AGENTS + CHANGELOG + ai_workflow/* + SRS/test_spec/acceptance);走 `forgeue:change-doc-sync` 命令编排。

### Commit P6

```bash
git commit -m "docs(forgeue): centralize-followon-backlog-registry P6 — Documentation Sync Gate (10 docs)

Tasks: tasks.md#P6.1 P6.2 ... P6.12

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P7 — retrospective + cross-check + finish_gate

### tasks.md#P7.1-P7.5

- [ ] P7.1 retrospective.md(沿 retire 模板)
- [ ] P7.2 review_cross_check.md A/B/C/D
- [ ] P7.3 final finish_gate exit 0
- [ ] P7.4 finish_gate_report.md(12-key + 13th `followon_continuity` PASS)
- [ ] P7.5 update MEMORY.md 加 `project_centralize_followon_backlog_shipped.md`

### Commit P7

```bash
git commit -m "feat(forgeue): centralize-followon-backlog-registry P7 — retrospective + cross-check + finish_gate

Tasks: tasks.md#P7.1 P7.2 P7.3 P7.4 P7.5

disputed_open=0; ready-to-ship

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## P8 — Archive(USER 范围 Fence #1)

### tasks.md#P8.1-P8.3

- [ ] P8.1 用户显式授权 archive
- [ ] P8.2 `openspec archive centralize-followon-backlog-registry`
- [ ] P8.3 git commit + tag(squash merge pattern;commit message reference design.md 章节)

---

## Round 2 codex re-review(S2 round 1 close 后,推 S3 前)

按 design.md 预估总 2 round。Round 1 已 close(disputed_open=0,commit `905cecd`)。Round 2 codex `/codex:adversarial-review` 验证 F1+F2 大改是否引入新 risk surface;若 disputed_open=0 → S3 ready;若引入新 finding → 走 round 2 inline writeback close。
