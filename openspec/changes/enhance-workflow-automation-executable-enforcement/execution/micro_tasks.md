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

## P0 — `tools/forgeue_preflight_wrapper.py`(W1;F2 round 2 codex inline writeback 后:13 字段 + wrapper self-managed worktree + 18 fence)

**对应 tasks.md**:[P0.1 ~ P0.5](../tasks.md#p0--toolsforgeue_preflight_wrapperpy-新建--测试-fencew1)

### micro-P0.1 Read 参考工具

- [ ] Read `tools/forgeue_skill_cascade_check.py` 全部(stdlib argparse 风格 + multi-root probe 模式)
- [ ] Read `tools/forgeue_finish_gate.py` 前 200 行(`_common.py` 引用 + Blocker.type 风格)
- [ ] 笔记 wrapper Python 启动模式:`#!/usr/bin/env python3` shebang(Windows 无效但保留)+ `from __future__ import annotations` + argparse subcommand pattern

### micro-P0.2 写 wrapper contract-first 失败测试(F2 round 2 inline writeback:13 字段 + wrapper-managed worktree + cwd realpath 校验)

- [ ] Create `tests/unit/test_preflight_wrapper.py`,加首个 fence:

```python
import json
import subprocess
import sys
from pathlib import Path

def test_wrapper_self_manages_worktree_and_writes_receipt_with_13_fields(tmp_path: Path):
    """W1 wrapper 自管 isolated worktree(git worktree subprocess)+ 13 字段 receipt(含 is_isolated_worktree + worktree_action)。

    F1 round 1 inline writeback:wrapper 自创/校验 worktree + 强制 cwd 在 worktree 内 fail-closed exit 6。
    F2 round 2 inline writeback:test 断言 13 字段(原 stale 测试只断言 10 字段漏 is_isolated_worktree + worktree_action;文档说 11 字段也错)。
    """
    # 准备临时 git repo
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=test@test", "-c", "user.name=test",
         "commit", "--allow-empty", "-m", "init"],
        cwd=str(repo), check=True, capture_output=True,
    )

    change_id = "test-change"
    worktrees_root = repo / ".worktrees"
    target_worktree = (worktrees_root / change_id).resolve()
    wrapper = Path(__file__).resolve().parents[2] / "tools" / "forgeue_preflight_wrapper.py"

    # First call from main repo should attempt worktree creation, then exit 6 (rejected_wrong_cwd)
    first = subprocess.run(
        [sys.executable, str(wrapper),
         "--change", change_id,
         "--cwd", str(repo),
         "--worktrees-root", str(worktrees_root)],
        capture_output=True, text=True,
    )
    assert first.returncode == 6, f"first invoke expected exit 6 (wrong-cwd after worktree create), got {first.returncode}; stderr: {first.stderr}"
    assert target_worktree.exists(), "wrapper should have created the target worktree even when cwd != target"
    assert "isolated worktree" in first.stderr.lower(), f"stderr should explain worktree requirement: {first.stderr}"

    # Second call from inside the wrapper-created worktree should succeed
    second = subprocess.run(
        [sys.executable, str(wrapper),
         "--change", change_id,
         "--cwd", str(target_worktree),
         "--worktrees-root", str(worktrees_root)],
        capture_output=True, text=True,
    )
    assert second.returncode == 0, f"second invoke should succeed; stderr: {second.stderr}"

    # Receipt landed inside the worktree's openspec/changes/<id>/preflight_receipts/
    receipt_rel_path = second.stdout.strip()
    receipt_abs_path = target_worktree / "openspec" / "changes" / change_id / receipt_rel_path
    assert receipt_abs_path.exists(), f"receipt missing at {receipt_abs_path}"

    payload = json.loads(receipt_abs_path.read_text(encoding="utf-8"))
    expected_fields = {
        "receipt_id", "change_id", "protocol_version",
        "worktree_path", "is_isolated_worktree", "worktree_action",
        "base_sha", "base_branch", "cwd_at_invocation",
        "skill_cascade_check", "created_at", "wrapper_version",
    }  # 12 top-level (skill_cascade_check 是 nested dict;design 13 字段含 nested 计数)
    assert expected_fields.issubset(set(payload.keys())), f"missing: {expected_fields - set(payload.keys())}"
    assert payload["protocol_version"] == "v2"
    assert payload["change_id"] == change_id
    assert payload["is_isolated_worktree"] is True
    assert payload["worktree_action"] in {"created", "reused"}
    assert payload["skill_cascade_check"]["exit_code"] == 0
```

- [ ] Run: `pytest tests/unit/test_preflight_wrapper.py::test_wrapper_self_manages_worktree_and_writes_receipt_with_13_fields -v`
- [ ] Expected: FAIL with "FileNotFoundError" / `tools/forgeue_preflight_wrapper.py` not exist

### micro-P0.3 写 wrapper 最小实现(F1 round 1 inline writeback:wrapper 自管 worktree;F2 round 2 inline writeback:13 字段)

- [ ] Create `tools/forgeue_preflight_wrapper.py`(stdlib only;~280-350 lines):

```python
"""W1 preflight wrapper — D-W1-ReceiptSchema(F1 round 1 inline:wrapper 自管 worktree)+ D-DispatchWrapperBoundary。

沿 design.md D-W1-ReceiptSchema 13-field receipt JSON(含 is_isolated_worktree + worktree_action)。
Wrapper 自己用 git worktree subprocess 创建 / 验证 isolated worktree + 强制 cwd realpath 校验。
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

WRAPPER_VERSION = "1.1"  # F1 round 1 + F2 round 2 inline writeback bump
PROTOCOL_VERSION = "v2"

EXIT_OK = 0
EXIT_CASCADE_FAIL = 5
EXIT_GIT_FAIL = 6  # 含 wrong-cwd / dirty / git not repo / worktree create fail
EXIT_RECEIPT_FAIL = 7


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def _short_random() -> str:
    return secrets.token_hex(4)


def _resolve_repo_root(cwd: Path) -> Path:
    out = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=str(cwd), text=True,
    ).strip()
    return Path(out)


def _list_worktrees(repo: Path) -> dict[str, dict]:
    """parse `git worktree list --porcelain`;返回 {worktree_realpath: {branch, prunable}}。"""
    out = subprocess.check_output(
        ["git", "worktree", "list", "--porcelain"], cwd=str(repo), text=True,
    )
    result: dict[str, dict] = {}
    current_path: str | None = None
    current: dict | None = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            if current_path is not None:
                result[os.path.realpath(current_path)] = current or {}
            current_path = line.split(" ", 1)[1].strip()
            current = {}
        elif current is not None and line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1].strip()
        elif current is not None and line == "prunable":
            current["prunable"] = True
    if current_path is not None:
        result[os.path.realpath(current_path)] = current or {}
    return result


def _ensure_isolated_worktree(repo: Path, worktrees_root: Path, change_id: str) -> tuple[Path, str]:
    """返回 (worktree_realpath, worktree_action ∈ {created, reused});
    rejected_dirty / rejected_wrong_cwd 由 caller 路径 raise。
    """
    target = (worktrees_root / change_id).resolve()
    worktrees_root.mkdir(parents=True, exist_ok=True)
    existing = _list_worktrees(repo)
    if str(target) in existing:
        # 校验 clean
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(target), text=True,
        )
        if status.strip():
            print(f"[ERROR] wrapper-managed worktree dirty: {target}", file=sys.stderr)
            raise SystemExit(EXIT_GIT_FAIL)  # rejected_dirty
        return target, "reused"
    branch_name = f"worktree-{change_id}"
    subprocess.check_call(
        ["git", "worktree", "add", str(target), "-b", branch_name],
        cwd=str(repo),
    )
    return target, "created"


def _verify_cwd_in_worktree(cwd: Path, worktree: Path) -> None:
    if os.path.realpath(cwd) != os.path.realpath(worktree):
        print(
            f"[ERROR] wrapper 必须在 isolated worktree 内调用;"
            f"当前 cwd={cwd},应为 {worktree};请 cd 到 {worktree} 重新调用 wrapper",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_GIT_FAIL)  # rejected_wrong_cwd


def _resolve_git_state(cwd: Path) -> tuple[str, str]:
    base_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(cwd), text=True,
    ).strip()
    base_branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(cwd), text=True,
    ).strip()
    return base_sha, base_branch


def _run_cascade_check(skill: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "tools/forgeue_skill_cascade_check.py",
         "--skill", skill, "--invoked", skill],
        capture_output=True, text=True,
    )
    return result.returncode, _iso_now()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--change", required=True)
    parser.add_argument("--skill", default="superpowers:using-git-worktrees")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--worktrees-root", default=None)
    parser.add_argument("--receipts-dir", default=None)
    parser.add_argument("--reuse-if-clean", action="store_true")
    args = parser.parse_args(argv)

    cwd = Path(args.cwd).resolve()

    try:
        repo = _resolve_repo_root(cwd)
    except subprocess.CalledProcessError:
        print("[ERROR] not in a git repo", file=sys.stderr)
        return EXIT_GIT_FAIL

    worktrees_root = Path(args.worktrees_root) if args.worktrees_root else (repo / ".worktrees")

    # F1 round 1 inline writeback:wrapper 自管 worktree
    try:
        worktree, worktree_action = _ensure_isolated_worktree(repo, worktrees_root, args.change)
    except subprocess.CalledProcessError:
        print("[ERROR] git worktree add failed", file=sys.stderr)
        return EXIT_GIT_FAIL

    # 强制 cwd 校验 — 必须在 wrapper-managed worktree 内调用
    try:
        _verify_cwd_in_worktree(cwd, worktree)
    except SystemExit as exc:
        return int(exc.code or 0)

    # cascade check
    cascade_exit, cascade_at = _run_cascade_check(args.skill)
    if cascade_exit != 0:
        return EXIT_CASCADE_FAIL

    base_sha, base_branch = _resolve_git_state(worktree)

    receipt_id = f"preflight-{args.change}-{_iso_now()}-{_short_random()}"
    receipt = {
        "receipt_id": receipt_id,
        "change_id": args.change,
        "protocol_version": PROTOCOL_VERSION,
        "worktree_path": str(worktree),
        "is_isolated_worktree": True,
        "worktree_action": worktree_action,
        "base_sha": base_sha,
        "base_branch": base_branch,
        "cwd_at_invocation": str(cwd),
        "skill_cascade_check": {
            "skill_invoked": args.skill,
            "exit_code": cascade_exit,
            "checked_at": cascade_at,
        },
        "created_at": _iso_now(),
        "wrapper_version": WRAPPER_VERSION,
    }

    receipts_dir = Path(args.receipts_dir) if args.receipts_dir else (
        worktree / "openspec" / "changes" / args.change / "preflight_receipts"
    )
    try:
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt_filename = f"{receipt['receipt_id']}.json"
        (receipts_dir / receipt_filename).write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        return EXIT_RECEIPT_FAIL

    print(f"preflight_receipts/{receipt_filename}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] Run: `pytest tests/unit/test_preflight_wrapper.py::test_wrapper_self_manages_worktree_and_writes_receipt_with_13_fields -v`
- [ ] Expected: PASS

### micro-P0.4 加剩余 17 fence(F2 round 2 inline writeback:总数 14 → 18;沿 tasks.md P0.3 + F1 round 1 加的 wrong-cwd / dirty negative test)

- [ ] 加 6 base 剩余:`receipt_json_well_formed` / `worktree_path_absolute` / `cascade_exit_code_zero` / `wrapper_stdout_relative_path` / `default_receipts_dir_when_unset` / `worktree_action_enum_in_created_or_reused`
- [ ] 加 6 失败路径:`cascade_check_fail_exit_5` / **`wrong_cwd_exit_6_stderr_contains_isolated_worktree`**(F1 inline negative)/ **`dirty_worktree_exit_6_stderr_contains_dirty`**(F1 inline negative)/ `git_not_repo_exit_6` / `receipt_dir_not_writable_exit_7` / `unknown_skill_exit_5`
- [ ] 加 3 D-OQ-1 reuse:`reuse_if_clean_returns_old_receipt`(同 base_sha,clean tree)/ `reuse_if_clean_dirty_tree_rejects` / `different_base_sha_recreates`
- [ ] 加 2 CLI smoke:`cli_help_exit_0` / `cli_minimal_invocation_smoke`
- [ ] Run: `pytest tests/unit/test_preflight_wrapper.py -v` → 18 PASS

### micro-P0.5 全套 regress + commit

- [ ] Run: `pytest -q` → 全绿无回归(基线 1529 + 18 = 1547 expected)
- [ ] Commit:

```bash
git add tools/forgeue_preflight_wrapper.py tests/unit/test_preflight_wrapper.py
git commit -m "feat(executable-enforcement): P0 W1 preflight wrapper(self-managed worktree)+ 18 fence test"
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

- [ ] Run: `pytest -q` → 全绿(1547 + 12 = 1559 expected;F2 round 2 inline 后 P0 fence 14 → 18 调整 baseline)
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
- [ ] Run: `pytest -q` → 全绿(1559 + 16 = 1575 expected)
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

### micro-P3.2 升级 change-apply-subagent.md(F1 round 2 inline writeback:post-dispatch ledger capture)

- [ ] 改 `## Preflight Worktree` step 1:从 `Skill(superpowers:using-git-worktrees)` 直接 invoke → `python tools/forgeue_preflight_wrapper.py --change <change-id>` Bash invoke(wrapper 自管 worktree;不需 `--skill` flag 因为 wrapper 内部默认)
- [ ] 加 step 2:capture wrapper stdout receipt 相对路径 → 注入 evidence frontmatter `worktree_receipt_path`(LLM 复制)+ 读 receipt 内 `worktree_path` 复制到 frontmatter `worktree_path`
- [ ] **改 ledger append 时序为 post-dispatch(F1 round 2 codex inline writeback;关闭"前 append 写 synthetic uuid_v4 与真实 agent_id 无关"漏洞)**:
  - 命令模板里 ledger append step 必须**在 Skill(Task) dispatch 之后**(从 Skill tool return capture 真实 agent_id),不是之前
  - 命令模板伪代码:
    ```
    a. Skill(Task): dispatch implementer subagent → capture return → parse 真实 agent_id from response metadata
    b. Bash: python tools/forgeue_dispatch_ledger.py append \
         --change <change-id> --agent-id <真实_agent_id_from_Skill_return> \
         --round 1 --role implementer \
         --task-subject-hash $(echo -n "$TASK" | sha256sum | cut -d' ' -f1)
    c. continue
    ```
  - markdown lint fence 必须校验 ledger append step 在 Skill(Task) step **之后**(沿 design.md D-W3-WrapperImpl post-dispatch capture statement)
- [ ] evidence frontmatter 模板 protocol_version v1 → v2 + 加 `dispatch_ledger_path: dispatch_ledger.jsonl` + 加 `pre_dispatch_metadata: advisory`(F2 round 1 inline writeback advisory 标注)+ 加 `ledger_forgery_resistance: advisory`(F3 round 1 inline writeback)

### micro-P3.3 升级 change-apply-parallel.md(F1 round 2 inline writeback:post-dispatch ledger capture;F3 round 2 inline writeback:git status --porcelain + ls-files --others 合集 + 不 /tmp)

- [ ] 同 micro-P3.2 全部(post-dispatch ledger capture)
- [ ] **改 dispatch 后 W2 actual diff Bash 段(F3 round 2 codex inline writeback)** — 沿 design.md D-W2-OverlapDetection step 0/1 contract:
  ```bash
  # Step 0: implementer worktree clean precondition fail-closed(F4 round 1 inline writeback)
  for IMPL_WORKTREE in "${IMPL_WORKTREES[@]}"; do
      DIRTY=$(git -C "$IMPL_WORKTREE" status --porcelain=v1)
      if [ -n "$DIRTY" ]; then
          ABORT_LOG="<change>/parallel_abort_dirty_$(date +%Y%m%dT%H%M%S).log"
          echo "[ABORT] dirty implementer worktree: $IMPL_WORKTREE" > "$ABORT_LOG"
          echo "$DIRTY" >> "$ABORT_LOG"
          # evidence: degradation_reason=dirty_implementer_worktree
          exec /forgeue:change-apply-subagent <change-id>
      fi
  done

  # Step 1: actual changed-files 收集(committed + untracked,NUL-separated)
  declare -A IMPL_FILES
  for IMPL_WORKTREE in "${IMPL_WORKTREES[@]}"; do
      AGENT_ID="${IMPL_WORKTREE_TO_AGENT[$IMPL_WORKTREE]}"
      # committed diff
      mapfile -d $'\0' COMMITTED < <(git -C "$IMPL_WORKTREE" diff --name-only -z "$BASE_SHA"..HEAD)
      # untracked(exclude .gitignore-matched)
      mapfile -d $'\0' UNTRACKED < <(git -C "$IMPL_WORKTREE" ls-files --others --exclude-standard -z)
      IMPL_FILES["$AGENT_ID"]="$(printf '%s\n' "${COMMITTED[@]}" "${UNTRACKED[@]}" | sort -u)"
  done

  # Step 2: cross-implementer set intersection(stdlib python helper 或 awk)
  python3 -c "
import sys, os, json
files_by_agent = json.loads(os.environ['IMPL_FILES_JSON'])  # {agent_id: [files...]}
agents = list(files_by_agent.keys())
overlaps = []
for i in range(len(agents)):
    for j in range(i+1, len(agents)):
        intersect = set(files_by_agent[agents[i]]) & set(files_by_agent[agents[j]])
        if intersect:
            overlaps.append({'a': agents[i], 'b': agents[j], 'files': sorted(intersect)})
sys.exit(0 if not overlaps else 1)
print(json.dumps(overlaps))
"
  if [ $? -ne 0 ]; then
      ABORT_LOG="<change>/parallel_abort_$(date +%Y%m%dT%H%M%S).log"
      echo "[ABORT] actual file overlap detected" > "$ABORT_LOG"
      # evidence: degradation_reason=actual_file_overlap_detected
      exec /forgeue:change-apply-subagent <change-id>
  fi
  ```
- [ ] **abort log 落 `<change>/parallel_abort_<iso>.log`(沿 ForgeUE 产物路径约定;不用 `/tmp/...`)**
- [ ] 加 evidence frontmatter `task_files_actual: [{implementer_agent_id, files: [...]}]` 字段填入逻辑(含 untracked file)+ `degraded_to: null` 或 `change-apply-subagent` + `degradation_reason: null` 或 `actual_file_overlap_detected` 或 `dirty_implementer_worktree`

### micro-P3.4 change-apply-direct.md 不动

- [ ] 验证未触碰(沿 D-DirectWorktreeRefinement);若需要 — 加注释段说明本 change 不修改 direct

### micro-P3.5 8 fence test(F1 + F3 round 2 inline writeback:6 → 8 加 post-dispatch order + git status --porcelain 关键词)

- [ ] 沿 tasks.md P3.5 加 8 个 markdown lint fence(原 6 + F1 round 2 加 1 + F3 round 2 加 1):
  - 6 base 沿 tasks.md P3.5
  - **`test_change_apply_ledger_append_after_skill_task_dispatch`**(F1 round 2 inline:校验命令模板 ledger append step 在 Skill(Task) step **之后**;regex 匹配 `Skill(Task).*?\n.*?(?:python tools/forgeue_dispatch_ledger.py append|forgeue_dispatch_ledger.*?append)` order)
  - **`test_change_apply_parallel_actual_diff_uses_git_status_porcelain_and_ls_files_others`**(F3 round 2 inline:模板内含 `git status --porcelain=v1` 字符串(precondition)+ `git ls-files --others --exclude-standard -z` 字符串(untracked 收集)+ **不**含 `/tmp/` 字符串)
- [ ] Run: `pytest tests/unit/test_forgeue_command_markdown.py -v` → 全绿
- [ ] Run: `pytest -q` → 全绿(1575 + 8 = 1583 expected)

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
  - W1 wrapper invocation 协议 + **13 字段 receipt(含 is_isolated_worktree + worktree_action;F1 round 1 / F2 round 2 inline writeback)**
  - W1 wrapper 自管 worktree(`git worktree add/list` subprocess + cwd realpath 校验)
  - W2 actual diff:**git status --porcelain precondition + diff -z + ls-files --others 合集 + 不 /tmp**(F4 round 1 / F3 round 2 inline writeback)+ 自动降级
  - W3 ledger append-only + LLM isolation + **post-dispatch capture 真实 agent_id**(F2 round 1 / F1 round 2 inline writeback)
  - protocol v1 vs v2 dispatch matrix
  - DogfoodGap 说明
  - F2/F3 deferred 标注:`pre_dispatch_metadata: advisory` + `ledger_forgery_resistance: advisory` evidence 字段;真 wrapper-bound dispatch + cryptographic enforcement 留 `enhance-workflow-automation-ledger-binding` follow-on

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

## P5.5 — v2 e2e integration test fixture(F5 round 1 codex inline writeback;F4 round 2 codex inline writeback:加独立 phase row;archive 前必过 gate)

**对应 tasks.md**:[P5.5](../tasks.md#p55--v2-e2e-integration-test-fixturef5-round-1-codex-inline-writeback;archive-前必过-gate)

### micro-P5.5.1 Read 参考

- [ ] Read `tests/integration/test_p3_*.py` 1-2 个文件,了解 ForgeUE integration test 风格(tmp_path + 端到端 bundle + stdlib mock)

### micro-P5.5.2 写 fixture(沿 D-W4-IntegrationGate;预计 8-12 test case + ~250 LOC)

- [ ] Create `tests/integration/test_v2_e2e_synthetic_change.py`:
  - fixture 用 `tmp_path` + `subprocess` 创建 synthetic git repo + active change 目录(`openspec/changes/test-v2-synthetic/` 内 4 制品 minimal stub)
  - **W1 全链路**:跑 `tools/forgeue_preflight_wrapper.py` → 校验 receipt 13 字段 + `is_isolated_worktree: true` + cwd 校验
  - **W3 全链路**:mock Skill(Task) 返回真实 agent_id 格式([a-f0-9]{17}+)→ 跑 `tools/forgeue_dispatch_ledger.py append --agent-id <真实>` post-dispatch → 跑 `tools/forgeue_dispatch_ledger.py verify` PASS
  - **W2 全链路**:模拟 2 implementer 各 commit 不同文件 → 跑 actual diff 合集(`git diff -z` + `git ls-files --others -z`)→ disjoint 通过
  - **W2 overlap 负例**:模拟 2 implementer 修改同一文件 → 触发自动降级 sequential(evidence `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected`)
  - **W2 dirty 负例**:模拟 implementer 漏 commit dirty file → 触发降级(`degradation_reason: dirty_implementer_worktree`)
  - **finish_gate 全 6 fence**:on synthetic v2 evidence(skill_cascade / round_fix_continuity v2 / task_granularity / worktree_path v2 / file_overlap_actual / dispatch_ledger)— 全 PASS
  - **v1 evidence 兼容**:synthetic v1 evidence 不被 v2 fence 误杀
  - **legacy evidence pass-through**:无 protocol_version 字段 → 全 fence pass-through

### micro-P5.5.3 全套绿

- [ ] Run: `pytest -q tests/integration/test_v2_e2e_synthetic_change.py -v` → 全绿(8-12 test case)
- [ ] Run: `pytest -q` → 全绿(1583 + 8-12 = 1591-1595 expected)

### micro-P5.5.4 commit

- [ ] Commit:

```bash
git add tests/integration/test_v2_e2e_synthetic_change.py
git commit -m "test(executable-enforcement): P5.5 v2 e2e integration fixture (D-W4-IntegrationGate;archive must-pass)"
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
| Preflight wrapper receipt JSON contract(ADDED) | P0(13 字段 wrapper + wrapper self-managed worktree + 18 fence;F1 round 1 + F2 round 2 inline writeback) |
| Dispatch ledger append-only contract(ADDED) | P1(append/verify subcommand + 12 fence) |
| Parallel dispatch actual file overlap detection(ADDED) | P2.5 + P3.3(git status --porcelain precondition + diff -z + ls-files --others 合集 + 不 /tmp;F4 round 1 + F3 round 2 inline writeback) |
| v2 e2e integration test fixture(ADDED) | P5.5(独立 phase;F5 round 1 inline writeback)+ P10.0 archive 必过 gate |
| Runtime enforcement protocol version v2 migration(ADDED) | P2.2 + P2.9(protocol dispatch + matrix test)+ evidence 字段 7 个含 advisory 标注(F2/F3 round 1 inline) |
| Implementation parallel dispatch(MODIFIED v2)| P3.3(actual diff + 自动降级 + clean precondition) |
| Preflight Worktree runtime enforcement(MODIFIED v2)| P3.2 + P3.3(wrapper invocation;wrapper 自管 worktree) |
| Round 2+ fix subagent continuity(MODIFIED v2)| P2.4(ledger cross-check)+ P3.2/P3.3 post-dispatch ledger capture(F1 round 2 inline writeback) |

无 gap。

### Placeholder scan

- 无 "TBD" / "TODO" / "implement later"(全部 inline 代码示例 + 具体 fence test 命名 + commit message 模板)
- "Add appropriate error handling" / "Add validation" 0 个

### Type consistency

- `agent_id` / `round` / `role` 在 ledger schema(P1)+ finish_gate fence(P2.4)+ 命令模板 ledger append step(P3.2 post-dispatch capture)三处一致
- `worktree_path` / `worktree_receipt_path` / `dispatch_ledger_path` 在 receipt JSON(P0)+ evidence frontmatter(P3.2)+ finish_gate fence(P2.3 + P2.4)三处一致
- `is_isolated_worktree: true` + `worktree_action ∈ {created, reused}` 在 receipt JSON(P0;F1 round 1 inline)+ test 断言(micro-P0.2 + micro-P0.4)+ finish_gate fence(P2.3 v2 cross-check)三处一致
- `protocol_version: v2` 在 receipt + evidence + finish_gate dispatch logic 三处一致
- `pre_dispatch_metadata: advisory` + `ledger_forgery_resistance: advisory`(F2/F3 round 1 inline)在 evidence frontmatter 模板(P3.2)+ design.md statement 两处一致

### DogfoodGap 显式标注

- execution_plan.md "Self-Host Bootstrap 限制" 段 + tasks.md P10.4 + design.md D-DogfoodGap 三处呼应
- F5 round 1 inline writeback 后:**P5.5 v2 e2e fixture 是 archive 前必过 gate**(P10.0 二次确认),DogfoodGap 不再是单纯 advisory accept,有 synthetic fixture 自证物

---

## Execution Handoff

**完成 propose stage 后**(本 cross-check 通过 + writeback OK):
- **推荐路径**:`/forgeue:change-apply-subagent enhance-workflow-automation-executable-enforcement`(default sequential;沿 D-DogfoodGap)
- **不推荐路径**:`/forgeue:change-apply-parallel`(W2 协议未 ship,不能机器证明 task 独立)/ `/forgeue:change-apply-direct`(超过 < 3 micro-task 边界)
