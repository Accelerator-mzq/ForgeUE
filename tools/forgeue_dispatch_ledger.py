#!/usr/bin/env python3
"""W3 dispatch ledger — D-W3-LedgerFormat + D-DispatchWrapperBoundary。

JSONL append-only；wrapper-only write；LLM context 隔离。
支持 append（向 ledger 追加记录）和 verify（校验 ledger 完整性）两个子命令。
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

# W3 角色枚举：round 1 + round 2 各角色
VALID_ROLES = frozenset({
    "implementer", "spec_reviewer", "code_quality_reviewer",
    "final_reviewer", "implementer_round_2_fix", "spec_reviewer_round_2_review",
})


def _iso_now() -> str:
    """返回当前 ISO8601 格式时间戳（本地时区精确到秒）。"""
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def _default_ledger_path(change_id: str) -> Path:
    """计算默认 ledger 路径：openspec/changes/<change-id>/dispatch_ledger.jsonl。"""
    return Path("openspec/changes") / change_id / "dispatch_ledger.jsonl"


def cmd_append(args: argparse.Namespace) -> int:
    """append 子命令：向 ledger 追加一行 JSON 记录。

    Args:
        args: 包含 --change、--agent-id、--round、--role、
              --task-subject-hash (可选)、--parent-session-id (可选)、
              --ledger-path (可选) 的命名空间对象。

    Returns:
        EXIT_OK (0) 成功；EXIT_VERIFY_FAIL (5) 角色无效。
    """
    ledger = Path(args.ledger_path) if args.ledger_path else _default_ledger_path(args.change)

    # 创建 ledger 父目录
    ledger.parent.mkdir(parents=True, exist_ok=True)

    # 校验 role 枚举
    if args.role not in VALID_ROLES:
        print(f"[ERROR] invalid role: {args.role}", file=sys.stderr)
        return EXIT_VERIFY_FAIL

    # 构建 payload：W3 ledger format 字段
    payload = {
        "agent_id": args.agent_id,
        "round": args.round,
        "role": args.role,
        "task_subject_hash": args.task_subject_hash,
        "dispatched_at": _iso_now(),
        "parent_session_id": args.parent_session_id,
        "wrapper_version": WRAPPER_VERSION,
    }

    # 序列化为 JSON 并追加一行
    line = json.dumps(payload, ensure_ascii=False)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()

    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    """verify 子命令：校验 ledger JSONL 完整性。

    校验内容：
    - 所有行都是合法 JSON
    - 所有行都包含 wrapper_version 字段
    - dispatched_at 时间戳单调递增

    Args:
        args: 包含 --change、--ledger-path (可选) 的命名空间对象。

    Returns:
        EXIT_OK (0) 校验通过；EXIT_VERIFY_FAIL (5) 校验失败。
    """
    ledger = Path(args.ledger_path) if args.ledger_path else _default_ledger_path(args.change)

    if not ledger.exists():
        print(f"[ERROR] ledger missing: {ledger}", file=sys.stderr)
        return EXIT_VERIFY_FAIL

    prev_ts = ""
    for line_no, raw in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        # 校验 JSON 格式
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[ERROR] line {line_no}: not JSON", file=sys.stderr)
            return EXIT_VERIFY_FAIL

        # 校验 wrapper_version 字段存在
        if not payload.get("wrapper_version"):
            print(f"[ERROR] line {line_no}: wrapper_version missing", file=sys.stderr)
            return EXIT_VERIFY_FAIL

        # 校验时间戳单调性
        ts = payload.get("dispatched_at", "")
        if prev_ts and ts < prev_ts:
            print(f"[ERROR] line {line_no}: timestamp not monotonic", file=sys.stderr)
            return EXIT_VERIFY_FAIL
        prev_ts = ts

    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """CLI 入口点。"""
    parser = argparse.ArgumentParser(
        description="W3 dispatch ledger: append-only JSONL for wrapper-only dispatch tracking"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # append 子命令
    ap = sub.add_parser("append", help="Append a dispatch record to ledger")
    ap.add_argument("--change", required=True, help="Change ID")
    ap.add_argument("--agent-id", required=True, help="Agent ID dispatched")
    ap.add_argument("--round", type=int, required=True, help="Round number (1, 2, ...)")
    ap.add_argument("--role", required=True, help=f"Role in dispatch (one of: {', '.join(sorted(VALID_ROLES))})")
    ap.add_argument("--task-subject-hash", default=None, help="Optional task subject hash (sha256:...)")
    ap.add_argument("--parent-session-id", default=None, help="Optional parent session UUID")
    ap.add_argument("--ledger-path", default=None, help="Optional explicit ledger path (default: openspec/changes/<change>/dispatch_ledger.jsonl)")
    ap.set_defaults(func=cmd_append)

    # verify 子命令
    vp = sub.add_parser("verify", help="Verify ledger JSONL integrity")
    vp.add_argument("--change", required=True, help="Change ID")
    vp.add_argument("--ledger-path", default=None, help="Optional explicit ledger path")
    vp.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
