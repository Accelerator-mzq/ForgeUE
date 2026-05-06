#!/usr/bin/env python3
"""W3 dispatch ledger v3 — D-W3-LedgerFormat + D-DispatchWrapperBoundary + cryptographic enforcement。

JSONL append-only;wrapper-only write;LLM context 隔离。
支持 append(向 ledger 追加 11-字段 v3 记录,含 HMAC chain)和 verify(沿 ANY v3 信号 dispatch
strict schema + chain HMAC + key rotation 双路径)两个子命令。

v3 升级(沿 enhance-workflow-automation-ledger-binding change;round 1+2+3 codex inline writeback):

- WRAPPER_VERSION 1.0 → 2.0(D-WrapperVersionBump)
- cmd_append 写 11 字段 v3 schema(原 7 字段 + protocol_version + key_id + prev_hmac + hmac);
  stdout 打印 [LEDGER] line_count=<N> final_hmac=<hex>(D-LedgerTerminalProof,LLM 复制到 evidence frontmatter)
- cmd_verify 沿 ANY v3 信号 dispatch(round 3 codex F1 inline writeback):任何行含 hmac /
  prev_hmac / key_id 字段 OR wrapper_version="2.0" OR protocol_version="v3" → 触发 v3 strict
  validation(strict 11-field schema + chain HMAC + key rotation);否则走 v2 schema-only
  legacy 路径(archived v2 ledger backward compatible)
- cmd_verify 加 --allow-archived-replay flag(round 1 codex F2 + round 2 codex F1 inline writeback);
  仅在 ledger 路径含 archive/ segment 才 honor flag(D-ArchivedReplayPathBoundary)
- cmd_verify NOT 实施 terminal proof(round 3 codex F2 inline writeback);留 finish_gate
  `_check_ledger_terminal_proof` fence 实施(因为 finish_gate 有 evidence frontmatter context)
- cmd_append NOT 实施 cross-platform file lock(round 3 codex F4 inline writeback);并发安全
  由命令模板主 session 串行 append 提供(implementer subagent dispatch 之间 parallel,但 append
  是主 session 串行调 wrapper)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# 沿 ForgeUE 测试 sys.path 风格(让 _forgeue_ledger_crypto 可 import)
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
import _forgeue_ledger_crypto as _crypto  # noqa: E402

WRAPPER_VERSION = "2.0"  # D-WrapperVersionBump:v3 schema break
EXIT_OK = 0
EXIT_VERIFY_FAIL = 5
EXIT_KEY_ROTATION_USER_OVERRIDE = 6
EXIT_KEY_FILE_CORRUPTED = 7

# W3 角色枚举(re-export 给 backward compat;实际 schema enum 校在 _forgeue_ledger_crypto)
VALID_ROLES = _crypto.VALID_ROLES


def _iso_now() -> str:
    """返回当前 ISO8601 格式时间戳(本地时区精确到秒;tz-aware,沿 strict schema 校)。"""
    return datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def _default_ledger_path(change_id: str) -> Path:
    """计算默认 ledger 路径:openspec/changes/<change-id>/dispatch_ledger.jsonl。"""
    return Path("openspec/changes") / change_id / "dispatch_ledger.jsonl"


def _read_ledger_lines(ledger: Path) -> list[dict]:
    """读 ledger 文件,解析每行为 dict;空行跳过。

    Returns:
        list of dict(每行 1 dict);若 JSON 解析失败,该行 raise。
    """
    if not ledger.exists():
        return []
    lines = []
    for raw in ledger.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            lines.append(json.loads(raw))
    return lines


def _has_v3_signal(lines: list[dict]) -> bool:
    """ANY v3 信号 dispatch(round 3 codex F1 inline writeback)。

    任一行含 v3 信号 → trigger v3 strict validation:
    - hmac / prev_hmac / key_id 字段任一出现
    - wrapper_version == "2.0"
    - protocol_version == "v3"

    防 LLM 改所有行 protocol_version 字段企图绕 v3 fence。
    """
    return any(
        ("hmac" in line) or ("prev_hmac" in line) or ("key_id" in line)
        or (line.get("wrapper_version") == "2.0")
        or (line.get("protocol_version") == "v3")
        for line in lines
    )


def cmd_append(args: argparse.Namespace) -> int:
    """append 子命令:向 ledger 追加一行 v3 11-字段 JSON 记录(HMAC chain)。

    并发 append invariant(round 3 codex F4 inline writeback;沿 design.md R3 + spec
    "Append serial invariant"):本函数**不**实施 cross-platform file lock;并发安全由
    命令模板 main session 串行 append 提供。若 ship 后实证非 ForgeUE 工作流外部并发跑
    wrapper 触发 race → follow-on `enhance-workflow-automation-ledger-append-lock`。

    Args:
        args: 包含 --change、--agent-id、--round、--role、
              --task-subject-hash (可选)、--parent-session-id (可选)、
              --ledger-path (可选) 的命名空间对象。

    Returns:
        EXIT_OK (0) 成功;EXIT_VERIFY_FAIL (5) role 枚举校验失败;
        EXIT_KEY_FILE_CORRUPTED (7) key 文件损坏(由 _crypto.load_or_init_key raise SystemExit)。
    """
    ledger = Path(args.ledger_path) if args.ledger_path else _default_ledger_path(args.change)

    # 创建 ledger 父目录
    ledger.parent.mkdir(parents=True, exist_ok=True)

    # 校验 role 枚举
    if args.role not in VALID_ROLES:
        print(f"[ERROR] invalid role: {args.role}", file=sys.stderr)
        return EXIT_VERIFY_FAIL

    # 加载或初始化 HMAC key(D-KeyLocation;首次 init 自动生成 + chmod 0600)
    key, key_id = _crypto.load_or_init_key()

    # 读 prev_hmac:若 ledger 已存在且非空,取最后一行 hmac;否则首行用 "0" * 64
    prev_hmac = "0" * 64
    if ledger.exists():
        for raw in ledger.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if stripped:
                try:
                    last_record = json.loads(stripped)
                    candidate = last_record.get("hmac")
                    if isinstance(candidate, str) and candidate:
                        prev_hmac = candidate
                except json.JSONDecodeError:
                    # 沿现有 cmd_verify 错误处理风格;若末尾有损坏行,prev_hmac 保留前一合法行的 hmac
                    pass

    # 构建 v3 record(11 字段;hmac 字段先留空,后填)
    record = {
        "agent_id": args.agent_id,
        "round": args.round,
        "role": args.role,
        "task_subject_hash": args.task_subject_hash,
        "dispatched_at": _iso_now(),
        "parent_session_id": args.parent_session_id,
        "wrapper_version": WRAPPER_VERSION,
        "protocol_version": "v3",
        "key_id": key_id,
        "prev_hmac": prev_hmac,
    }

    # 计算 hmac(D-CanonicalJSON 排除 hmac + 含 prev_hmac;D-HashChain 链接前一行)
    record["hmac"] = _crypto.compute_hmac(key, record)

    # 序列化为 canonical JSON 并追加一行(沿 canonical 同款 sort_keys + separators 保持一致性)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()

    # 统计实际行数 + 末行 hmac(D-LedgerTerminalProof:LLM 复制到 evidence frontmatter
    # `ledger_line_count` + `ledger_final_hmac` 字段)
    actual_lines = sum(
        1 for raw in ledger.read_text(encoding="utf-8").splitlines() if raw.strip()
    )
    print(f"[LEDGER] line_count={actual_lines} final_hmac={record['hmac']}")

    return EXIT_OK


def _verify_v3_strict(
    lines: list[dict],
    allow_archived_replay: bool,
) -> tuple[int, str | None]:
    """v3 strict validation:strict 11-field schema + chain HMAC + key rotation 双路径。

    NOT 实施 terminal proof(round 3 codex F2 inline writeback;留 finish_gate)。

    Args:
        lines: ledger 行 dict 列表
        allow_archived_replay: cmd_verify --allow-archived-replay flag 值;True 时
            evidence_frontmatter 模拟为 {"ledger_archived_replay": True} 触发
            verify_chain_v3 user override 路径

    Returns:
        (exit_code, error_msg) tuple;exit_code ∈ {EXIT_OK, EXIT_VERIFY_FAIL,
        EXIT_KEY_ROTATION_USER_OVERRIDE}
    """
    # strict schema 校(沿 D-Scope-F3-MergeWithP12.8;round 1 codex F5 scope expansion)
    sstatus, smsg = _crypto.verify_strict_schema_v3(lines)
    if sstatus != "ok":
        return (EXIT_VERIFY_FAIL, f"[schema_violation] {smsg}")

    # 加载 HMAC key
    key, _key_id = _crypto.load_or_init_key()

    # chain HMAC verify + key rotation 双路径(沿 D-HashChain + D-KeyRotationHandling)
    evidence_fm = {"ledger_archived_replay": True} if allow_archived_replay else None
    cstatus, cmsg = _crypto.verify_chain_v3(key, lines, evidence_fm)

    if cstatus == "key_rotation_user_override_required":
        return (EXIT_KEY_ROTATION_USER_OVERRIDE, f"[key_rotation_user_override] {cmsg}")
    if cstatus != "ok":
        return (EXIT_VERIFY_FAIL, f"[{cstatus}] {cmsg}")

    return (EXIT_OK, None)


def _verify_v2_legacy(lines: list[dict]) -> tuple[int, str | None]:
    """v2 schema-only legacy verify(沿现有 v2 实施;archived v2 ledger backward compatible)。

    校验:
    - 每行 wrapper_version 字段非空
    - dispatched_at timestamp 单调递增

    Returns:
        (exit_code, error_msg)
    """
    prev_ts = ""
    for line_no, payload in enumerate(lines, 1):
        if not payload.get("wrapper_version"):
            return (EXIT_VERIFY_FAIL, f"line {line_no}: wrapper_version missing")
        ts = payload.get("dispatched_at", "")
        if prev_ts and ts < prev_ts:
            return (EXIT_VERIFY_FAIL, f"line {line_no}: timestamp not monotonic")
        prev_ts = ts
    return (EXIT_OK, None)


def cmd_verify(args: argparse.Namespace) -> int:
    """verify 子命令:校验 ledger JSONL 完整性(沿 ANY v3 信号 dispatch)。

    Dispatch matrix(round 3 codex F1 inline writeback):
    - ANY v3 信号(hmac / prev_hmac / key_id 字段任一 OR wrapper_version="2.0" OR
      protocol_version="v3")→ v3 strict validation(strict schema + chain HMAC + key rotation)
    - 否则(纯 v2 ledger,7 字段,wrapper_version="1.0")→ v2 schema-only legacy 路径

    --allow-archived-replay flag(沿 D-ArchivedReplayPathBoundary):
    - 仅在 ledger 路径含 `archive/` segment 才 honor flag(防 LLM 在 active change forge
      此字段 + 替换 key 文件绕 fail-closed);active path + flag → BLOCKER

    NOT 实施 terminal proof(round 3 codex F2 inline writeback);留 finish_gate fence。

    Returns:
        EXIT_OK (0) 校验通过;EXIT_VERIFY_FAIL (5) verify 失败;
        EXIT_KEY_ROTATION_USER_OVERRIDE (6) archived replay user override(WARN);
        EXIT_KEY_FILE_CORRUPTED (7) key 文件损坏。
    """
    ledger = Path(args.ledger_path) if args.ledger_path else _default_ledger_path(args.change)

    if not ledger.exists():
        print(f"[ERROR] ledger missing: {ledger}", file=sys.stderr)
        return EXIT_VERIFY_FAIL

    # --allow-archived-replay 路径限定(沿 D-ArchivedReplayPathBoundary)
    if args.allow_archived_replay:
        # ledger 路径必须含 archive/ segment(沿 spec "Archived replay path boundary" Scenario)
        ledger_resolved = str(ledger.resolve()).replace("\\", "/")
        if "/archive/" not in ledger_resolved:
            print(
                f"[ERROR] ledger {ledger} not in archive/ path; "
                "--allow-archived-replay rejected",
                file=sys.stderr,
            )
            return EXIT_VERIFY_FAIL

    # 解析 ledger 全行
    lines: list[dict] = []
    for line_no, raw in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            print(f"[ERROR] ledger {ledger} line {line_no}: not JSON: {exc}", file=sys.stderr)
            return EXIT_VERIFY_FAIL

    # ANY v3 信号 dispatch(round 3 codex F1 inline writeback)
    if _has_v3_signal(lines):
        exit_code, err = _verify_v3_strict(lines, args.allow_archived_replay)
        if err:
            stream = sys.stderr if exit_code != EXIT_OK else sys.stdout
            level = "WARN" if exit_code == EXIT_KEY_ROTATION_USER_OVERRIDE else "ERROR"
            print(f"[{level}] {err}", file=stream)
        return exit_code

    # v2 legacy 路径(archived v2 ledger backward compatible)
    exit_code, err = _verify_v2_legacy(lines)
    if err:
        print(f"[ERROR] {err}", file=sys.stderr)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    """CLI 入口点。"""
    parser = argparse.ArgumentParser(
        description="W3 dispatch ledger v3: append-only JSONL with HMAC chain (wrapper 2.0)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # append 子命令
    ap = sub.add_parser("append", help="Append a v3 dispatch record (11 fields with HMAC chain) to ledger")
    ap.add_argument("--change", required=True, help="Change ID")
    ap.add_argument("--agent-id", required=True, help="Agent ID dispatched")
    ap.add_argument("--round", type=int, required=True, help="Round number (1, 2, ...)")
    ap.add_argument(
        "--role",
        required=True,
        help=f"Role in dispatch (one of: {', '.join(sorted(VALID_ROLES))})",
    )
    ap.add_argument(
        "--task-subject-hash",
        default=None,
        help="Optional task subject hash (sha256:...)",
    )
    ap.add_argument(
        "--parent-session-id",
        default=None,
        help="Optional parent session UUID",
    )
    ap.add_argument(
        "--ledger-path",
        default=None,
        help="Optional explicit ledger path (default: openspec/changes/<change>/dispatch_ledger.jsonl)",
    )
    ap.set_defaults(func=cmd_append)

    # verify 子命令
    vp = sub.add_parser(
        "verify",
        help="Verify ledger JSONL integrity (v3 strict + chain HMAC OR v2 schema-only)",
    )
    vp.add_argument("--change", required=True, help="Change ID")
    vp.add_argument("--ledger-path", default=None, help="Optional explicit ledger path")
    vp.add_argument(
        "--allow-archived-replay",
        action="store_true",
        help=(
            "archived replay opt-in (only valid if ledger path in archive/ segment; "
            "fail-closed default; sole D-ArchivedReplayPathBoundary)"
        ),
    )
    # NOTE: NOT 加 --evidence-line-count / --evidence-final-hmac flag
    # (round 3 codex F2 inline writeback: cmd_verify 不实施 terminal proof;
    #  terminal proof 由 finish_gate `_check_ledger_terminal_proof` fence 实施)
    vp.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
