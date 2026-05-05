---
change_id: enhance-workflow-automation-executable-enforcement
stage: S2
evidence_type: micro_tasks
contract_refs:
  - tasks.md#P0
  - tasks.md#P1
  - tasks.md#P2
  - tasks.md#P3
  - tasks.md#P4
  - tasks.md#P5
  - design.md#decisions
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
task_granularity: phase
created_at: 2026-05-05T13:35:00+08:00
---

# Micro Tasks — enhance-workflow-automation-executable-enforcement

> 沿 `execution_plan.md` Phase Map;每 phase 1 implementer subagent dispatch(`task_granularity: phase`)。
> TDD 4-step 节奏:failing test → minimal impl → regress green → commit。
> Pre-P0 见 `notes/pre_p0/codex_review_round1.md`(本会话当前阶段)+ `review/design_cross_check.md`。

---

## P0 — `tools/forgeue_preflight_wrapper.py`(W1)

**对应 tasks.md**:[P0.1 ~ P0.5](../tasks.md#p0--toolsforgeue_preflight_wrapperpy-新建--测试-fencew1)

### micro-P0.1 Read 参考工具

- [ ] Read `tools/forgeue_skill_cascade_check.py` 全部(stdlib argparse 风格 + multi-root probe 模式)
- [ ] Read `tools/forgeue_finish_gate.py` 前 200 行(`_common.py` 引用 + Blocker.type 风格)
- [ ] 笔记 wrapper Python 启动模式:`#!/usr/bin/env python3` shebang(Windows 无效但保留)+ `from __future__ import annotations` + argparse subcommand pattern

### micro-P0.2 写 wrapper 失败测试

- [ ] Create `tests/unit/test_preflight_wrapper.py`,加首个 fence:

```python
import json
import subprocess
import sys
from pathlib import Path

def test_wrapper_writes_receipt_with_11_fields(tmp_path: Path):
    """W1 wrapper 写 receipt JSON,含 D-W1-ReceiptSchema 全 11 字段。"""
    change_id = "test-change"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    receipts_dir = change_root / "preflight_receipts"

    # invoke wrapper
    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_preflight_wrapper.py",
            "--change", change_id,
            "--skill", "superpowers:using-git-worktrees",
            "--cwd", str(tmp_path),
            "--receipts-dir", str(receipts_dir),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    # capture receipt path from stdout
    receipt_rel_path = result.stdout.strip()
    receipt_abs_path = change_root / receipt_rel_path
    assert receipt_abs_path.exists()

    payload = json.loads(receipt_abs_path.read_text(encoding="utf-8"))
    expected_fields = {
        "receipt_id", "change_id", "protocol_version",
        "worktree_path", "base_sha", "base_branch",
        "cwd_at_invocation", "skill_cascade_check",
        "created_at", "wrapper_version",
    }
    assert expected_fields.issubset(payload.keys())
    assert payload["protocol_version"] == "v2"
    assert payload["change_id"] == change_id
    assert payload["skill_cascade_check"]["exit_code"] == 0
```

- [ ] Run: `pytest tests/unit/test_preflight_wrapper.py::test_wrapper_writes_receipt_with_11_fields -v`
- [ ] Expected: FAIL with "FileNotFoundError" / `tools/forgeue_preflight_wrapper.py` not exist

### micro-P0.3 写 wrapper 最小实现

- [ ] Create `tools/forgeue_preflight_wrapper.py`(stdlib only;~200-300 lines):

```python
"""W1 preflight wrapper — D-W1-ReceiptSchema + D-DispatchWrapperBoundary。

沿 design.md D-W1-ReceiptSchema 11-field receipt JSON。
LLM 只需复制 worktree_path + receipt_id 两字段到 evidence frontmatter。
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WRAPPER_VERSION = "1.0"
PROTOCOL_VERSION = "v2"

EXIT_OK = 0
EXIT_CASCADE_FAIL = 5
EXIT_GIT_FAIL = 6
EXIT_RECEIPT_FAIL = 7


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def _short_random() -> str:
    return secrets.token_hex(4)


def _resolve_git_state(cwd: Path) -> tuple[str, str]:
    """返回 (base_sha, base_branch);非 git 仓库 raise CalledProcessError。"""
    base_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(cwd), text=True,
    ).strip()
    base_branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(cwd), text=True,
    ).strip()
    return base_sha, base_branch


def _run_cascade_check(skill: str) -> tuple[int, str]:
    """子调 forgeue_skill_cascade_check.py;返回 (exit_code, iso_timestamp)。"""
    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_skill_cascade_check.py",
            "--skill", skill,
            "--invoked", skill,
        ],
        capture_output=True, text=True,
    )
    return result.returncode, _iso_now()


def _build_receipt(*, change_id: str, skill: str, cwd: Path) -> dict:
    base_sha, base_branch = _resolve_git_state(cwd)
    cascade_exit, cascade_at = _run_cascade_check(skill)
    if cascade_exit != 0:
        raise SystemExit(EXIT_CASCADE_FAIL)
    receipt_id = f"preflight-{change_id}-{_iso_now()}-{_short_random()}"
    return {
        "receipt_id": receipt_id,
        "change_id": change_id,
        "protocol_version": PROTOCOL_VERSION,
        "worktree_path": str(cwd.resolve()),
        "base_sha": base_sha,
        "base_branch": base_branch,
        "cwd_at_invocation": str(cwd.resolve()),
        "skill_cascade_check": {
            "skill_invoked": skill,
            "exit_code": cascade_exit,
            "checked_at": cascade_at,
        },
        "created_at": _iso_now(),
        "wrapper_version": WRAPPER_VERSION,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--change", required=True)
    parser.add_argument("--skill", default="superpowers:using-git-worktrees")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--receipts-dir", default=None)
    parser.add_argument("--reuse-if-clean", action="store_true")
    args = parser.parse_args(argv)

    cwd = Path(args.cwd)
    receipts_dir = Path(args.receipts_dir) if args.receipts_dir else (
        Path("openspec/changes") / args.change / "preflight_receipts"
    )
    receipts_dir.mkdir(parents=True, exist_ok=True)

    try:
        receipt = _build_receipt(change_id=args.change, skill=args.skill, cwd=cwd)
    except subprocess.CalledProcessError:
        return EXIT_GIT_FAIL

    receipt_filename = f"{receipt['receipt_id']}.json"
    receipt_abs_path = receipts_dir / receipt_filename
    try:
        receipt_abs_path.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        return EXIT_RECEIPT_FAIL

    receipt_rel_path = f"preflight_receipts/{receipt_filename}"
    print(receipt_rel_path)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] Run: `pytest tests/unit/test_preflight_wrapper.py::test_wrapper_writes_receipt_with_11_fields -v`
- [ ] Expected: PASS

### micro-P0.4 加剩余 13 fence(沿 tasks.md P0.3)

- [ ] 加 5 base 剩余:`receipt_json_well_formed` / `worktree_path_absolute` / `cascade_exit_code_zero` / `wrapper_stdout_relative_path` / `default_receipts_dir_when_unset`
- [ ] 加 4 失败路径:`cascade_check_fail_exit_5` / `git_not_repo_exit_6` / `receipt_dir_not_writable_exit_7` / `unknown_skill_exit_5`
- [ ] 加 2 D-OQ-1 reuse:`reuse_if_clean_returns_old_receipt` / `reuse_if_clean_dirty_tree_creates_new`
- [ ] 加 2 CLI smoke:`cli_help_exit_0` / `cli_minimal_invocation_smoke`
- [ ] Run: `pytest tests/unit/test_preflight_wrapper.py -v` → 14 PASS

### micro-P0.5 全套 regress + commit

- [ ] Run: `pytest -q` → 全绿无回归(基线 1529 + 14 = 1543 expected)
- [ ] Commit:

```bash
git add tools/forgeue_preflight_wrapper.py tests/unit/test_preflight_wrapper.py
git commit -m "feat(executable-enforcement): P0 W1 preflight wrapper + 14 fence test"
```

---

## P1 — `tools/forgeue_dispatch_ledger.py`(W3)

**对应 tasks.md**:[P1.1 ~ P1.4](../tasks.md#p1--toolsforgeue_dispatch_ledgerpy-新建--测试-fencew3)

### micro-P1.1 写 ledger append 失败测试

- [ ] Create `tests/unit/test_dispatch_ledger.py`,首个 fence:

```python
import json
import subprocess
import sys
from pathlib import Path


def test_ledger_append_writes_one_jsonl_line(tmp_path: Path):
    """W3 ledger append 子命令写一行 JSON 含 D-W3-LedgerFormat 字段。"""
    change_id = "test-change"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_dispatch_ledger.py", "append",
            "--change", change_id,
            "--agent-id", "ad79e93a40414763e",
            "--round", "1",
            "--role", "implementer",
            "--task-subject-hash", "sha256:abc",
            "--ledger-path", str(ledger_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    expected = {"agent_id", "round", "role", "task_subject_hash", "dispatched_at", "wrapper_version"}
    assert expected.issubset(payload.keys())
    assert payload["agent_id"] == "ad79e93a40414763e"
    assert payload["round"] == 1
    assert payload["role"] == "implementer"
    assert payload["wrapper_version"]  # non-empty
```

- [ ] Run: `pytest tests/unit/test_dispatch_ledger.py::test_ledger_append_writes_one_jsonl_line -v`
- [ ] Expected: FAIL

### micro-P1.2 写 ledger 最小实现

- [ ] Create `tools/forgeue_dispatch_ledger.py`(stdlib only;~150-200 lines):

```python
"""W3 dispatch ledger — D-W3-LedgerFormat + D-DispatchWrapperBoundary。

JSONL append-only;wrapper-only write;LLM context isolation。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WRAPPER_VERSION = "1.0"
EXIT_OK = 0
EXIT_VERIFY_FAIL = 5

VALID_ROLES = frozenset({
    "implementer", "spec_reviewer", "code_quality_reviewer",
    "final_reviewer", "implementer_round_2_fix", "spec_reviewer_round_2_review",
})


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def _default_ledger_path(change_id: str) -> Path:
    return Path("openspec/changes") / change_id / "dispatch_ledger.jsonl"


def cmd_append(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger_path) if args.ledger_path else _default_ledger_path(args.change)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    if args.role not in VALID_ROLES:
        print(f"[ERROR] invalid role: {args.role}", file=sys.stderr)
        return EXIT_VERIFY_FAIL
    payload = {
        "agent_id": args.agent_id,
        "round": args.round,
        "role": args.role,
        "task_subject_hash": args.task_subject_hash,
        "dispatched_at": _iso_now(),
        "parent_session_id": args.parent_session_id,
        "wrapper_version": WRAPPER_VERSION,
    }
    line = json.dumps(payload, ensure_ascii=False)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    ledger = Path(args.ledger_path) if args.ledger_path else _default_ledger_path(args.change)
    if not ledger.exists():
        print(f"[ERROR] ledger missing: {ledger}", file=sys.stderr)
        return EXIT_VERIFY_FAIL
    prev_ts = ""
    for line_no, raw in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[ERROR] line {line_no}: not JSON", file=sys.stderr)
            return EXIT_VERIFY_FAIL
        if not payload.get("wrapper_version"):
            print(f"[ERROR] line {line_no}: wrapper_version missing", file=sys.stderr)
            return EXIT_VERIFY_FAIL
        ts = payload.get("dispatched_at", "")
        if prev_ts and ts < prev_ts:
            print(f"[ERROR] line {line_no}: timestamp not monotonic", file=sys.stderr)
            return EXIT_VERIFY_FAIL
        prev_ts = ts
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    ap = sub.add_parser("append")
    ap.add_argument("--change", required=True)
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--role", required=True)
    ap.add_argument("--task-subject-hash", default=None)
    ap.add_argument("--parent-session-id", default=None)
    ap.add_argument("--ledger-path", default=None)
    ap.set_defaults(func=cmd_append)

    vp = sub.add_parser("verify")
    vp.add_argument("--change", required=True)
    vp.add_argument("--ledger-path", default=None)
    vp.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] Run: `pytest tests/unit/test_dispatch_ledger.py::test_ledger_append_writes_one_jsonl_line -v` → PASS

### micro-P1.3 加剩余 11 fence

- [ ] 沿 tasks.md P1.2:5 append + 4 verify + 2 schema + 1 CLI smoke
- [ ] Run: `pytest tests/unit/test_dispatch_ledger.py -v` → 12 PASS

### micro-P1.4 全套 regress + commit

- [ ] Run: `pytest -q` → 全绿(1543 + 12 = 1555 expected)
- [ ] Commit:

```bash
git add tools/forgeue_dispatch_ledger.py tests/unit/test_dispatch_ledger.py
git commit -m "feat(executable-enforcement): P1 W3 dispatch ledger + 12 fence test"
```

---

## P2 — `forgeue_finish_gate.py` 升级 + protocol v2 dispatch

**对应 tasks.md**:[P2.1 ~ P2.11](../tasks.md#p2--forgeue_finish_gatepy-升级-4-fence--协议-v2-dispatch--测试)

### micro-P2.1 ~ P2.7 finish_gate 升级(沿 tasks.md 顺序;TDD per fence)

依次实施 P2.2 protocol_version dispatch → P2.3 `_check_worktree_path` v2 → P2.4 `_check_round_fix_continuity` v2 → P2.5 `_check_file_overlap_actual` 新 → P2.6 `_check_dispatch_ledger` 新 → P2.7 wiring。

每 fence 4-step TDD:写 failing test → 写最小实现 → 跑 fence test → 跑全套 regress。

### micro-P2.8/P2.9 fence test 全集

- [ ] 12 v2 fence test + 4 protocol_version dispatch test
- [ ] Run: `pytest tests/unit/test_forgeue_finish_gate.py -v` → 全绿
- [ ] Run: `pytest -q` → 全绿(1555 + 16 = 1571 expected)
- [ ] Commit:

```bash
git add tools/forgeue_finish_gate.py tests/unit/test_forgeue_finish_gate.py
git commit -m "feat(executable-enforcement): P2 finish_gate v2 fences + protocol dispatch + 16 fence test"
```

---

## P3 — 命令模板加 wrapper invocation + ledger append + actual diff

**对应 tasks.md**:[P3.1 ~ P3.6](../tasks.md#p3--forgeuechange-apply-subagentparallel-命令模板加-wrapper-invocation-step)

### micro-P3.1 Read 现状

- [ ] Read `.claude/commands/forgeue/change-apply-subagent.md` 全部
- [ ] Read `.claude/commands/forgeue/change-apply-parallel.md` 全部
- [ ] 笔记 P2 既有 Preflight 三段位置 + Skill(Task) dispatch step 位置

### micro-P3.2 升级 change-apply-subagent.md

- [ ] 改 `## Preflight Worktree` step 1:从 `Skill(superpowers:using-git-worktrees)` 直接 invoke → `python tools/forgeue_preflight_wrapper.py --change <change-id> --skill superpowers:using-git-worktrees` Bash invoke
- [ ] 加 step 2:capture wrapper stdout receipt 相对路径 → 注入 evidence frontmatter `worktree_receipt_path`(LLM 复制)+ 读 receipt 内 `worktree_path` 复制到 frontmatter `worktree_path`
- [ ] 加 step 3(每 Skill(Task) dispatch 前):
  ```bash
  python tools/forgeue_dispatch_ledger.py append --change <change-id> --agent-id $AGENT_ID --round 1 --role implementer --task-subject-hash $(echo -n "$TASK" | sha256sum | cut -d' ' -f1)
  ```
- [ ] evidence frontmatter 模板 protocol_version v1 → v2 + 加 `dispatch_ledger_path: dispatch_ledger.jsonl`

### micro-P3.3 升级 change-apply-parallel.md

- [ ] 同 micro-P3.2 全部
- [ ] 加 dispatch 后 W2 actual diff Bash 段:
  ```bash
  for IMPL_WORKTREE in <implementer-worktrees>; do
      git -C "$IMPL_WORKTREE" diff --name-only "$BASE_SHA"..HEAD
  done | sort | uniq -d > /tmp/actual_overlap.txt
  if [ -s /tmp/actual_overlap.txt ]; then
      echo "[ABORT] actual file overlap detected" > <change>/parallel_abort_$(date -Iseconds).log
      cat /tmp/actual_overlap.txt >> <change>/parallel_abort_$(date -Iseconds).log
      exec /forgeue:change-apply-subagent <change-id>
  fi
  ```
- [ ] 加 evidence frontmatter `task_files_actual` 字段填入逻辑 + `degraded_to: null` + `degradation_reason: null`(降级时填非 null)

### micro-P3.4 change-apply-direct.md 不动

- [ ] 验证未触碰(沿 D-DirectWorktreeRefinement);若需要 — 加注释段说明本 change 不修改 direct

### micro-P3.5 6 fence test

- [ ] 沿 tasks.md P3.5 加 6 个 markdown lint fence
- [ ] Run: `pytest tests/unit/test_forgeue_command_markdown.py -v` → 全绿
- [ ] Run: `pytest -q` → 全绿(1571 + 6 = 1577 expected)

### micro-P3.6 commit

- [ ] Commit:

```bash
git add .claude/commands/forgeue/change-apply-subagent.md .claude/commands/forgeue/change-apply-parallel.md tests/unit/test_forgeue_command_markdown.py
git commit -m "feat(executable-enforcement): P3 cmd templates wrap preflight wrapper + dispatch ledger + W2 actual diff + 6 fence"
```

---

## P4 — backbone SKILL.md 同步

**对应 tasks.md**:[P4.1 ~ P4.3](../tasks.md#p4--backbone-skill-skillmd-同步-w1w2w3-wrapper-invocation-协议)

### micro-P4.1 编辑 SKILL.md

- [ ] Read `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` 全部
- [ ] 加 "Runtime Enforcement Protocol v2(自 enhance-workflow-automation-executable-enforcement change 起)" 段
  - W1 wrapper invocation 协议 + 11 字段 receipt
  - W2 actual diff + 自动降级
  - W3 ledger append-only + LLM isolation
  - protocol v1 vs v2 dispatch matrix
  - DogfoodGap 说明

### micro-P4.2 命令清单 / Superpowers 集成边界表更新(如必要)

- [ ] 命令数无变化(W1/W2/W3 是 wrapper 加强,不新增命令);若 SKILL.md 含命令清单仅描述更新

### micro-P4.3 commit

- [ ] Commit:

```bash
git add .claude/skills/forgeue-integrated-change-workflow/SKILL.md
git commit -m "docs(executable-enforcement): P4 backbone SKILL.md sync W1/W2/W3 protocol v2"
```

---

## P5 — 11 处文档同步(沿 archived runtime-enforcement P4 模式)

**对应 tasks.md**:[P5.1 ~ P5.11](../tasks.md#p5--11-处文档同步沿-enhance-workflow-automation-runtime-enforcement-p4-模式)

每个文档 1 micro task:Read → Edit → grep verify → commit。

| micro task | 文件 | tasks.md 锚点 |
|---|---|---|
| micro-P5.1 | `docs/ai_workflow/forgeue_integrated_ai_workflow.md` | P5.1 |
| micro-P5.2 | `docs/ai_workflow/README.md` | P5.2 |
| micro-P5.3 | `docs/ai_workflow/forgeue_quickstart.md` | P5.3 |
| micro-P5.4 | `CLAUDE.md` | P5.4 |
| micro-P5.5 | `README.md` | P5.5 |
| micro-P5.6 | `AGENTS.md` | P5.6 |
| micro-P5.7 | `CHANGELOG.md` | P5.7 |
| micro-P5.8 | `docs/requirements/SRS.md` | P5.8 |
| micro-P5.9 | `docs/acceptance/acceptance_report.md` | P5.9 |
| micro-P5.10 | `docs/design/HLD.md` | P5.10 |
| micro-P5.11 | `openspec/specs/examples-and-acceptance/spec.md`(P11.3 archive 时 sync) | P5.11 |

合并 commit(沿 archived runtime-enforcement P4 同款一次性 doc-sync commit):

```bash
git add docs/ README.md CLAUDE.md AGENTS.md CHANGELOG.md
git commit -m "docs(executable-enforcement): P5 sync 11 docs + ADR-012"
```

---

## P6-P12 — verify / codex review / superpowers skip / doc sync gate / finish gate / archive / follow-on

沿 [tasks.md P6-P12](../tasks.md#p6--verify) 编排,与 archived runtime-enforcement P5-P11 同款顺序。各 phase 1 commit:

- P6:`verify_report.md` evidence
- P7:`codex_mixed_scope_review.md` + 6 reference stub
- P8:`superpowers_review.md` SKIP rationale stub
- P9:`doc_sync_report.md` evidence
- P10:`finish_gate_report.md` evidence
- P11:archive(用户授权 fence #1)
- P12:`MEMORY.md` 更新 + follow-on tracking

---

## Self-Review

### Spec coverage

| spec.md Requirement | execution_plan / micro_tasks 覆盖 |
|---|---|
| Preflight wrapper receipt JSON contract(ADDED) | P0(11 字段 wrapper + 14 fence) |
| Dispatch ledger append-only contract(ADDED) | P1(append/verify subcommand + 12 fence) |
| Parallel dispatch actual file overlap detection(ADDED) | P2.5 + P3.3 |
| Runtime enforcement protocol version v2 migration(ADDED) | P2.2 + P2.9(protocol dispatch + matrix test) |
| Implementation parallel dispatch(MODIFIED v2)| P3.3(actual diff + 自动降级) |
| Preflight Worktree runtime enforcement(MODIFIED v2)| P3.2 + P3.3(wrapper invocation) |
| Round 2+ fix subagent continuity(MODIFIED v2)| P2.4(ledger cross-check) |

无 gap。

### Placeholder scan

- 无 "TBD" / "TODO" / "implement later"(全部 inline 代码示例 + 具体 fence test 命名 + commit message 模板)
- "Add appropriate error handling" / "Add validation" 0 个

### Type consistency

- `agent_id` / `round` / `role` 在 ledger schema(P1)+ finish_gate fence(P2.4)+ 命令模板 ledger append step(P3.2)三处一致
- `worktree_path` / `worktree_receipt_path` / `dispatch_ledger_path` 在 receipt JSON(P0)+ evidence frontmatter(P3.2)+ finish_gate fence(P2.3 + P2.4)三处一致
- `protocol_version: v2` 在 receipt + evidence + finish_gate dispatch logic 三处一致

### DogfoodGap 显式标注

- execution_plan.md "Self-Host Bootstrap 限制" 段 + tasks.md P10.4 + design.md D-DogfoodGap 三处呼应

---

## Execution Handoff

**完成 propose stage 后**(本 cross-check 通过 + writeback OK):
- **推荐路径**:`/forgeue:change-apply-subagent enhance-workflow-automation-executable-enforcement`(default sequential;沿 D-DogfoodGap)
- **不推荐路径**:`/forgeue:change-apply-parallel`(W2 协议未 ship,不能机器证明 task 独立)/ `/forgeue:change-apply-direct`(超过 < 3 micro-task 边界)
