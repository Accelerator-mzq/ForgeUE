#!/usr/bin/env python3
"""ForgeUE v3 ledger HMAC chain crypto helper (stdlib-only)。

支撑 enhance-workflow-automation-ledger-binding change ship 的 v3 cryptographic
enforcement 协议。涉及 D-decision:

- D-CanonicalJSON:canonical JSON 序列化排除 hmac + 包含 prev_hmac + sort_keys + UTF-8
- D-HashChain:HMAC-SHA256 over canonical 含 prev_hmac;首行 prev_hmac 全 0
- D-KeyLocation:HMAC key 持久化到 ~/.claude/forgeue_ledger_key (JSON 单文件,跨 change 共享)
- D-KeyRotationHandling:key 文件 lifecycle 6 状态(round 1+2 codex inline writeback);
  active v3 evidence + key_id mismatch → fail-closed BLOCKER;archived replay 走
  evidence frontmatter `ledger_archived_replay: true` opt-in
- D-LedgerTerminalProof:evidence frontmatter `ledger_line_count` + `ledger_final_hmac`
  必填 v3,fence cross-check 防 tail truncation
- D-Scope-F3-MergeWithP12.8:strict 11-field schema(精确字段集 + 字段类型 + 字段 format)

模块顶层零副作用(沿 ForgeUE probes 协定);下划线前缀标 internal,不暴露 CLI 入口。
"""
from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import os
import re
import secrets
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 模块常量
# ---------------------------------------------------------------------------

# HMAC key 持久化路径(沿 D-KeyLocation;跨 change 共享)
_KEY_FILE_PATH = Path.home() / ".claude" / "forgeue_ledger_key"

# Key 文件 schema version(预留 future schema 扩展)
_KEY_VERSION = 1

# HMAC key 字节长度(256-bit HMAC-SHA256 key)
_KEY_BYTES_LEN = 32
_KEY_HEX_LEN = 64  # 32 bytes * 2 = 64 hex chars

# Exit codes(沿 forgeue_dispatch_ledger.py 同款);round 1+2 codex inline writeback 后扩展
EXIT_OK = 0
EXIT_VERIFY_FAIL = 5
EXIT_KEY_ROTATION_USER_OVERRIDE = 6
EXIT_KEY_FILE_CORRUPTED = 7

# W3 角色枚举(沿 forgeue_dispatch_ledger.py VALID_ROLES;在此模块 re-export 给 schema 校验)
VALID_ROLES = frozenset({
    "implementer", "spec_reviewer", "code_quality_reviewer",
    "final_reviewer", "implementer_round_2_fix", "spec_reviewer_round_2_review",
})

# v3 ledger 行 strict schema 字段集(沿 D-Scope-F3-MergeWithP12.8 精确 11 字段)
_V3_EXPECTED_FIELDS = frozenset({
    "agent_id", "round", "role", "task_subject_hash", "dispatched_at",
    "parent_session_id", "wrapper_version", "protocol_version",
    "key_id", "prev_hmac", "hmac",
})

# Strict schema field format 正则
_AGENT_ID_RE = re.compile(r"^[a-f0-9]{17,}$")
_KEY_ID_RE = re.compile(r"^[a-f0-9]{16}$")
_HMAC_RE = re.compile(r"^[a-f0-9]{64}$")
_WRAPPER_VERSION_RE = re.compile(r"^\d+\.\d+$")
_TASK_SUBJECT_HASH_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
_PARENT_SESSION_ID_RE = re.compile(r"^[a-f0-9-]{36}$")


# ---------------------------------------------------------------------------
# canonical JSON + HMAC core(D-CanonicalJSON + D-HashChain)
# ---------------------------------------------------------------------------


def canonical_payload(record: dict) -> bytes:
    """canonical JSON 序列化(沿 D-CanonicalJSON)。

    规范化输出 bytes,作为 HMAC 输入。关键约束:

    - **排除 hmac 字段**(避免循环依赖;hmac 是输出而非输入)
    - **包含 prev_hmac 字段**(它是 hash chain 输入)
    - sort_keys=True:跨 Python 版本字段顺序一致
    - separators=(",", ":"):无 whitespace 歧义
    - ensure_ascii=False:UTF-8 编码 unicode(与 ledger 文件 encoding 一致)

    Args:
        record: 11 字段 v3 ledger 行 dict(含或不含 hmac 字段都接受)

    Returns:
        UTF-8 encoded canonical bytes(用于 HMAC 输入)。
    """
    payload = {k: v for k, v in record.items() if k != "hmac"}
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_hmac(key: bytes, record: dict) -> str:
    """HMAC-SHA256 over canonical_payload(沿 D-HashChain)。

    Args:
        key: 32-byte HMAC key
        record: ledger 行 dict(必须含 prev_hmac 字段;hmac 字段被 canonical 排除)

    Returns:
        HMAC hex digest(64 hex chars = SHA256 输出)
    """
    canonical = canonical_payload(record)
    return hmac_mod.new(key, canonical, hashlib.sha256).hexdigest()


def compute_key_id(key: bytes) -> str:
    """key_id = sha256(key).hexdigest()[:16](沿 D-KeyLocation 同款 16-char fingerprint)。

    Args:
        key: 32-byte HMAC key

    Returns:
        16 hex chars(64-bit fingerprint;不暴露 raw key,fence error 可显示)
    """
    return hashlib.sha256(key).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Key file lifecycle(D-KeyLocation + D-KeyRotationHandling)
# ---------------------------------------------------------------------------


def load_or_init_key(key_file_path: Path | None = None) -> tuple[bytes, str]:
    """Key 文件 lifecycle 管理(沿 D-KeyRotationHandling 6 状态);返回 (key_bytes, key_id)。

    生命周期状态:

    1. **首次 init**:文件不存在 + `secrets.token_bytes(32)` 生成 + `os.O_EXCL` flag
       创建文件 + chmod 0600(Linux/Mac;Windows obscurity-not-strict-permission)
       + 打印 INFO 行
    2. **正常 load**:文件存在 + JSON 合法 + key_hex 64 chars + version == 1 → 读 key
    3. **文件损坏**:JSON 解析失败 / key_hex 长度错 / version 不识别
       → SystemExit(EXIT_KEY_FILE_CORRUPTED=7);不静默重建(避免静默丢失 verify 旧
       ledger 能力)
    4. **race 路径**:并发 init 触发 EEXIST → retry-load(读另一进程刚创建的 key)

    Args:
        key_file_path: 可选 override key 文件路径(默认 _KEY_FILE_PATH = ~/.claude/forgeue_ledger_key)

    Returns:
        (key_bytes, key_id) tuple

    Raises:
        SystemExit(7): key 文件损坏(JSON / key_hex 长度 / version)
    """
    path = key_file_path if key_file_path is not None else _KEY_FILE_PATH
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        # 首次 init,os.O_EXCL 防 race(沿 design.md R2 mitigation)
        key = secrets.token_bytes(_KEY_BYTES_LEN)
        payload = {
            "version": _KEY_VERSION,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "key_hex": key.hex(),
        }
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            # race:另一进程刚创建,retry-load
            return load_or_init_key(key_file_path)
        try:
            os.write(fd, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
        finally:
            os.close(fd)
        # Linux/Mac chmod 0600(Windows 上 chmod 等价于 read-only bit;沿 D-KeyLocation
        # obscurity-not-strict-permission)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        key_id = compute_key_id(key)
        print(f"[INFO] HMAC key initialized at {path} (key_id={key_id})")
        return (key, key_id)

    # 正常 load 路径
    try:
        text = path.read_text(encoding="utf-8")
        loaded = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"[ERROR] key file corrupted at {path}: {exc}; backup + remove file to re-init",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_KEY_FILE_CORRUPTED)

    if loaded.get("version") != _KEY_VERSION:
        print(
            f"[ERROR] key file corrupted at {path}: unknown version "
            f"{loaded.get('version')!r}; backup + remove file to re-init",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_KEY_FILE_CORRUPTED)

    key_hex = loaded.get("key_hex", "")
    if not isinstance(key_hex, str) or len(key_hex) != _KEY_HEX_LEN:
        print(
            f"[ERROR] key file corrupted at {path}: key_hex length "
            f"{len(key_hex) if isinstance(key_hex, str) else 'non-str'} != {_KEY_HEX_LEN}; "
            "backup + remove file to re-init",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_KEY_FILE_CORRUPTED)

    try:
        key = bytes.fromhex(key_hex)
    except ValueError:
        print(
            f"[ERROR] key file corrupted at {path}: key_hex not valid hex; "
            "backup + remove file to re-init",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_KEY_FILE_CORRUPTED)

    return (key, compute_key_id(key))


# ---------------------------------------------------------------------------
# v3 chain verify(D-HashChain + D-KeyRotationHandling)
# ---------------------------------------------------------------------------


def verify_chain_v3(
    key: bytes,
    lines: list[dict],
    evidence_frontmatter: dict | None = None,
) -> tuple[str, str | None]:
    """整链 verify(沿 D-HashChain + D-KeyRotationHandling 双路径)。

    流程(沿 spec.md "v3 ledger schema with HMAC chain" Scenario):

    1. 检查 ledger 内所有行 key_id 一致(同 ledger 同 key invariant)
    2. 检查 ledger key_id vs 当前 file key_id:
       - active v3 evidence(`ledger_archived_replay` ≠ True)+ 不一致 → key_id_mismatch BLOCKER
       - archived replay opt-in(`ledger_archived_replay` == True)→ user override WARN
    3. 从首行起整链 verify(仅 key_id 一致时跑;archived replay 模式 skip):
       - 首行 prev_hmac 必须 "0" * 64
       - 每行 hmac == compute_hmac(key, record)(canonical 重算)
       - 每行 prev_hmac == 上一行 hmac(chain 连续)

    Args:
        key: 当前文件 HMAC key
        lines: ledger 行 dict 列表
        evidence_frontmatter: 可选 evidence frontmatter dict(用于检测
            `ledger_archived_replay: true` opt-in 路径;沿 round 1+2 codex inline writeback)

    Returns:
        (status, error_msg) tuple;status ∈ {ok, hmac_mismatch, chain_break,
        key_id_inconsistent, key_id_mismatch, key_rotation_user_override_required}
    """
    if not lines:
        return ("ok", None)

    current_key_id = compute_key_id(key)
    ledger_key_id = lines[0].get("key_id")

    # 同一 ledger 内 key_id 一致性(LLM 中途切换 key 的 forge 信号)
    for line_no, record in enumerate(lines, 1):
        if record.get("key_id") != ledger_key_id:
            return (
                "key_id_inconsistent",
                f"line {line_no}: expected key_id={ledger_key_id}, got {record.get('key_id')}",
            )

    # ledger key_id vs 当前 file key_id(D-KeyRotationHandling 双路径)
    if ledger_key_id != current_key_id:
        # archived replay opt-in 路径(沿 round 1 codex F2 + round 2 codex F1 inline writeback)
        if evidence_frontmatter and evidence_frontmatter.get("ledger_archived_replay") is True:
            return (
                "key_rotation_user_override_required",
                f"ledger key_id {ledger_key_id} != current file key_id "
                f"{current_key_id}; HMAC verify skipped per opt-in",
            )
        # default fail-closed(攻击场景:LLM 替换 key 文件即可降级 HMAC 校 — 必须 fail-closed)
        return (
            "key_id_mismatch",
            f"ledger key_id {ledger_key_id} != current file key_id "
            f"{current_key_id}; HMAC verify cannot proceed without rotated-from key",
        )

    # chain verify(仅 key_id 一致时跑)
    expected_prev = "0" * 64
    for line_no, record in enumerate(lines, 1):
        if record.get("prev_hmac") != expected_prev:
            return (
                "chain_break",
                f"line {line_no}: prev_hmac mismatch (expected {expected_prev!r}, "
                f"got {record.get('prev_hmac')!r})",
            )

        expected_hmac = compute_hmac(key, record)
        if record.get("hmac") != expected_hmac:
            return (
                "hmac_mismatch",
                f"line {line_no}: HMAC recompute mismatch",
            )

        expected_prev = record["hmac"]

    return ("ok", None)


# ---------------------------------------------------------------------------
# Terminal proof verify(D-LedgerTerminalProof)
# ---------------------------------------------------------------------------


def verify_terminal_proof(
    lines: list[dict],
    evidence_line_count: int,
    evidence_final_hmac: str,
) -> tuple[str, str | None]:
    """Terminal proof verify(沿 D-LedgerTerminalProof;round 1 codex F3 inline writeback)。

    抓 tail truncation attack — hash chain 抓不住"删除最后 N 行"(剩余前缀仍是合法链);
    evidence frontmatter `ledger_line_count` + `ledger_final_hmac` 是 audit anchor。

    Args:
        lines: ledger 行 dict 列表
        evidence_line_count: evidence frontmatter 声明的 ledger 行数
        evidence_final_hmac: evidence frontmatter 声明的末行 hmac 值

    Returns:
        (status, error_msg);status ∈ {ok, tail_truncation_detected, final_hmac_mismatch}
    """
    actual_count = len(lines)
    if actual_count != evidence_line_count:
        return (
            "tail_truncation_detected",
            f"declared {evidence_line_count} lines, actual {actual_count}",
        )

    if not lines:
        # 空 ledger + evidence 声明 0 行 — 边缘 case,通常不发生
        if evidence_final_hmac == "0" * 64:
            return ("ok", None)
        return ("final_hmac_mismatch", "empty ledger but final_hmac != all zeros")

    actual_final_hmac = lines[-1].get("hmac", "")
    if actual_final_hmac != evidence_final_hmac:
        return (
            "final_hmac_mismatch",
            f"declared {evidence_final_hmac}, actual {actual_final_hmac}",
        )

    return ("ok", None)


# ---------------------------------------------------------------------------
# Strict 11-field schema validation(D-Scope-F3-MergeWithP12.8;round 1 codex F5 scope expansion)
# ---------------------------------------------------------------------------


def verify_strict_schema_v3(lines: list[dict]) -> tuple[str, str | None]:
    """Strict 11-field schema validation(沿 D-Scope-F3-MergeWithP12.8;合并 archived
    `executable-enforcement` P12.8 schema 部分进本 change)。

    HMAC 仅保护字节完整性,不校 schema 语义。本函数加 schema strict:
    - 字段集精确 11 字段(拒未知字段 + 拒缺字段)
    - 字段类型 strict(round 拒 bool / float;Python bool 是 int 子类要显式拒)
    - 字段 format 正则匹配(agent_id / key_id / hmac / prev_hmac / wrapper_version /
      task_subject_hash / parent_session_id 各有正则)
    - dispatched_at ISO8601 tz-aware
    - protocol_version 精确 "v3"
    - role enum

    Args:
        lines: ledger 行 dict 列表

    Returns:
        (status, error_msg);status ∈ {ok, schema_violation}
    """
    for line_no, record in enumerate(lines, 1):
        # 字段集精确 11 字段
        actual_fields = set(record.keys())
        unknown = actual_fields - _V3_EXPECTED_FIELDS
        if unknown:
            return (
                "schema_violation",
                f"line {line_no}: unknown field(s) {sorted(unknown)}",
            )
        missing = _V3_EXPECTED_FIELDS - actual_fields
        if missing:
            return (
                "schema_violation",
                f"line {line_no}: missing field(s) {sorted(missing)}",
            )

        # agent_id format
        if not isinstance(record["agent_id"], str) or not _AGENT_ID_RE.match(record["agent_id"]):
            return (
                "schema_violation",
                f"line {line_no}: field 'agent_id' MUST match ^[a-f0-9]{{17,}}$, "
                f"got {record['agent_id']!r}",
            )

        # round positive int(显式拒 bool;Python bool 是 int 子类)
        round_val = record["round"]
        if isinstance(round_val, bool) or not isinstance(round_val, int) or round_val <= 0:
            return (
                "schema_violation",
                f"line {line_no}: field 'round' MUST be positive integer (not bool / float), "
                f"got {round_val!r}",
            )

        # role enum
        if record["role"] not in VALID_ROLES:
            return (
                "schema_violation",
                f"line {line_no}: field 'role' MUST be in VALID_ROLES, got {record['role']!r}",
            )

        # task_subject_hash null or sha256 format
        tsh = record["task_subject_hash"]
        if tsh is not None and (not isinstance(tsh, str) or not _TASK_SUBJECT_HASH_RE.match(tsh)):
            return (
                "schema_violation",
                f"line {line_no}: field 'task_subject_hash' MUST be null or "
                f"^sha256:[a-f0-9]{{64}}$, got {tsh!r}",
            )

        # dispatched_at ISO8601 tz-aware
        dispatched_at = record["dispatched_at"]
        if not isinstance(dispatched_at, str):
            return (
                "schema_violation",
                f"line {line_no}: field 'dispatched_at' MUST be string, got {type(dispatched_at).__name__}",
            )
        try:
            dt = datetime.fromisoformat(dispatched_at)
            if dt.tzinfo is None:
                return (
                    "schema_violation",
                    f"line {line_no}: field 'dispatched_at' MUST be ISO8601 tz-aware, "
                    f"got naive {dispatched_at!r}",
                )
        except ValueError:
            return (
                "schema_violation",
                f"line {line_no}: field 'dispatched_at' MUST be parseable ISO8601 string, "
                f"got {dispatched_at!r}",
            )

        # parent_session_id null or UUID
        psid = record["parent_session_id"]
        if psid is not None and (not isinstance(psid, str) or not _PARENT_SESSION_ID_RE.match(psid)):
            return (
                "schema_violation",
                f"line {line_no}: field 'parent_session_id' MUST be null or UUID format, "
                f"got {psid!r}",
            )

        # wrapper_version major.minor
        wv = record["wrapper_version"]
        if not isinstance(wv, str) or not _WRAPPER_VERSION_RE.match(wv):
            return (
                "schema_violation",
                f"line {line_no}: field 'wrapper_version' MUST match ^\\d+\\.\\d+$, "
                f"got {wv!r}",
            )

        # protocol_version exact "v3"
        if record["protocol_version"] != "v3":
            return (
                "schema_violation",
                f"line {line_no}: field 'protocol_version' MUST be exactly 'v3', "
                f"got {record['protocol_version']!r}",
            )

        # key_id format
        if not isinstance(record["key_id"], str) or not _KEY_ID_RE.match(record["key_id"]):
            return (
                "schema_violation",
                f"line {line_no}: field 'key_id' MUST match ^[a-f0-9]{{16}}$, "
                f"got {record['key_id']!r}",
            )

        # prev_hmac format
        if not isinstance(record["prev_hmac"], str) or not _HMAC_RE.match(record["prev_hmac"]):
            return (
                "schema_violation",
                f"line {line_no}: field 'prev_hmac' MUST match ^[a-f0-9]{{64}}$, "
                f"got {record['prev_hmac']!r}",
            )

        # hmac format
        if not isinstance(record["hmac"], str) or not _HMAC_RE.match(record["hmac"]):
            return (
                "schema_violation",
                f"line {line_no}: field 'hmac' MUST match ^[a-f0-9]{{64}}$, "
                f"got {record['hmac']!r}",
            )

    return ("ok", None)
