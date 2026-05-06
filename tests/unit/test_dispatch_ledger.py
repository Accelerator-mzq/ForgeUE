"""单元测试：W3 dispatch ledger append + verify 命令。

测试 tools/forgeue_dispatch_ledger.py JSONL append-only 合约、role 枚举、
timestamp 单调性、默认路径、错误处理。
"""
from __future__ import annotations

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
    assert payload["wrapper_version"]


def test_ledger_append_n_lines_appended_in_order(tmp_path: Path):
    """N 个 sequential append → N 行，JSON 解析通过，dispatched_at 单调递增。"""
    change_id = "test-change-n"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    # append 3 times
    for i, role in enumerate(["implementer", "spec_reviewer", "code_quality_reviewer"], 1):
        result = subprocess.run(
            [
                sys.executable, "tools/forgeue_dispatch_ledger.py", "append",
                "--change", change_id,
                "--agent-id", f"agent{i:02d}",
                "--round", "1",
                "--role", role,
                "--ledger-path", str(ledger_path),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"append {i} failed: {result.stderr}"

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3

    # 验证 JSON 解析 + timestamp 单调性
    timestamps = []
    for j, line in enumerate(lines):
        payload = json.loads(line)
        ts = payload.get("dispatched_at", "")
        timestamps.append(ts)
        assert payload["role"] == ["implementer", "spec_reviewer", "code_quality_reviewer"][j]

    # timestamp 单调递增（允许相等）
    for k in range(len(timestamps) - 1):
        assert timestamps[k] <= timestamps[k + 1], f"timestamps not monotonic: {timestamps}"


def test_ledger_append_creates_parent_dir_if_missing(tmp_path: Path):
    """ledger_path.parent 不存在 → mkdir 不报错。"""
    change_id = "test-nested-change"
    ledger_path = tmp_path / "openspec" / "changes" / change_id / "dispatch_ledger.jsonl"
    # 注意：change_root 不先创建

    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_dispatch_ledger.py", "append",
            "--change", change_id,
            "--agent-id", "ad79e93a40414763e",
            "--round", "1",
            "--role", "implementer",
            "--ledger-path", str(ledger_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert ledger_path.exists()


def test_ledger_append_invalid_role_exit_5(tmp_path: Path):
    """--role unknown_role → exit 5 + stderr "invalid role"。"""
    change_id = "test-invalid-role"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_dispatch_ledger.py", "append",
            "--change", change_id,
            "--agent-id", "ad79e93a40414763e",
            "--round", "1",
            "--role", "unknown_role",
            "--ledger-path", str(ledger_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 5
    assert "invalid role" in result.stderr


def test_ledger_append_default_path_when_unset(tmp_path: Path):
    """no --ledger-path → 使用 openspec/changes/<id>/dispatch_ledger.jsonl default。"""
    change_id = "test-default-path"
    # 创建 default path 会需要的目录在 tmp_path 根目录
    openspec_root = tmp_path / "openspec" / "changes" / change_id
    openspec_root.mkdir(parents=True)

    # 模拟：在 tmp_path 作为工作目录，default path 会是相对 tmp_path 的路径
    # 但我们需要改变 cwd 同时还保持对工具的访问，所以采用另一种方式：
    # 直接在当前项目目录内构造 tmp 目录结构，然后用相对路径

    # 构造 openspec/changes/<id> 在当前项目
    from pathlib import Path as PathlibPath
    import tempfile
    import os

    # 在项目内临时创建 openspec/changes/<id> 目录
    project_change_dir = PathlibPath("openspec") / "changes" / change_id
    project_change_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [
                sys.executable, "tools/forgeue_dispatch_ledger.py", "append",
                "--change", change_id,
                "--agent-id", "ad79e93a40414763e",
                "--round", "1",
                "--role", "implementer",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        ledger_path = project_change_dir / "dispatch_ledger.jsonl"
        assert ledger_path.exists()
    finally:
        # 清理临时目录
        if ledger_path.exists():
            ledger_path.unlink()
        if project_change_dir.exists():
            project_change_dir.rmdir()
        # 尝试清理空的父目录
        try:
            (PathlibPath("openspec") / "changes").rmdir()
        except OSError:
            pass
        try:
            PathlibPath("openspec").rmdir()
        except OSError:
            pass


def test_ledger_verify_passes_well_formed(tmp_path: Path):
    """2 行 monotonic timestamps + wrapper_version → exit 0。"""
    change_id = "test-verify-pass"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    # 写 2 行 well-formed ledger
    lines = [
        json.dumps({
            "agent_id": "ad79e93a40414763e",
            "round": 1,
            "role": "implementer",
            "task_subject_hash": "sha256:abc",
            "dispatched_at": "2026-05-05T12:00:00+08:00",
            "wrapper_version": "1.0",
        }, ensure_ascii=False),
        json.dumps({
            "agent_id": "ad20e8a4019787c51",
            "round": 1,
            "role": "spec_reviewer",
            "task_subject_hash": "sha256:def",
            "dispatched_at": "2026-05-05T12:01:00+08:00",
            "wrapper_version": "1.0",
        }, ensure_ascii=False),
    ]
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_dispatch_ledger.py", "verify",
            "--change", change_id,
            "--ledger-path", str(ledger_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_ledger_verify_missing_file_exit_5(tmp_path: Path):
    """--ledger-path 不存在 → exit 5 + stderr "ledger missing"。"""
    change_id = "test-verify-missing"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"
    # 不创建文件

    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_dispatch_ledger.py", "verify",
            "--change", change_id,
            "--ledger-path", str(ledger_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 5
    assert "ledger missing" in result.stderr


def test_ledger_verify_timestamp_not_monotonic_exit_5(tmp_path: Path):
    """模拟 ledger 文件含 timestamp 倒流 → exit 5 + stderr "timestamp not monotonic"。"""
    change_id = "test-verify-not-monotonic"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    # 写 2 行，第二行 timestamp 倒流
    lines = [
        json.dumps({
            "agent_id": "ad79e93a40414763e",
            "round": 1,
            "role": "implementer",
            "dispatched_at": "2026-05-05T12:02:00+08:00",
            "wrapper_version": "1.0",
        }, ensure_ascii=False),
        json.dumps({
            "agent_id": "ad20e8a4019787c51",
            "round": 1,
            "role": "spec_reviewer",
            "dispatched_at": "2026-05-05T12:01:00+08:00",  # 早于第一行
            "wrapper_version": "1.0",
        }, ensure_ascii=False),
    ]
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_dispatch_ledger.py", "verify",
            "--change", change_id,
            "--ledger-path", str(ledger_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 5
    assert "timestamp not monotonic" in result.stderr


def test_ledger_verify_wrapper_version_missing_exit_5(tmp_path: Path):
    """模拟 line 缺 wrapper_version 字段 → exit 5 + stderr "wrapper_version missing"。"""
    change_id = "test-verify-no-version"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    # 写 1 行缺 wrapper_version
    line = json.dumps({
        "agent_id": "ad79e93a40414763e",
        "round": 1,
        "role": "implementer",
        "dispatched_at": "2026-05-05T12:00:00+08:00",
        # 故意缺 wrapper_version
    }, ensure_ascii=False)
    ledger_path.write_text(line + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_dispatch_ledger.py", "verify",
            "--change", change_id,
            "--ledger-path", str(ledger_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 5
    assert "wrapper_version missing" in result.stderr


def test_ledger_verify_invalid_json_line_exit_5(tmp_path: Path):
    """模拟 ledger 含 non-JSON line → exit 5 + stderr "not JSON"。"""
    change_id = "test-verify-invalid-json"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    # 写非 JSON 行
    ledger_path.write_text("this is not json\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_dispatch_ledger.py", "verify",
            "--change", change_id,
            "--ledger-path", str(ledger_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 5
    assert "not JSON" in result.stderr


def test_ledger_role_enum_validation(tmp_path: Path):
    """VALID_ROLES 6 个 role 全 accept；invalid reject。"""
    change_id = "test-role-enum"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    valid_roles = [
        "implementer", "spec_reviewer", "code_quality_reviewer",
        "final_reviewer", "implementer_round_2_fix", "spec_reviewer_round_2_review",
    ]

    # 每个 valid role 应该 accept
    for role in valid_roles:
        result = subprocess.run(
            [
                sys.executable, "tools/forgeue_dispatch_ledger.py", "append",
                "--change", change_id,
                "--agent-id", f"agent_{role}",
                "--round", "1",
                "--role", role,
                "--ledger-path", str(ledger_path),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"valid role {role} should accept; stderr: {result.stderr}"

    # 验证写入的所有行
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(valid_roles)

    # 无效 role 应该 reject
    result = subprocess.run(
        [
            sys.executable, "tools/forgeue_dispatch_ledger.py", "append",
            "--change", change_id,
            "--agent-id", "agent_invalid",
            "--round", "1",
            "--role", "invalid_role",
            "--ledger-path", str(ledger_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 5
    assert "invalid role" in result.stderr


def test_cli_help_exit_0():
    """python tools/forgeue_dispatch_ledger.py --help exit 0。"""
    result = subprocess.run(
        [sys.executable, "tools/forgeue_dispatch_ledger.py", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "append" in result.stdout
    assert "verify" in result.stdout


# =============================================================================
# v3 cryptographic ledger binding 测试
#
# 沿 enhance-workflow-automation-ledger-binding change(round 1+2 codex inline writeback 后)
# 涉及 D-decision:D-CanonicalJSON / D-HashChain / D-KeyLocation / D-KeyRotationHandling /
# D-LedgerTerminalProof / D-Scope-F3-MergeWithP12.8(strict 11-field schema)。
#
# P1 phase scope:`tools/_forgeue_ledger_crypto.py` 内部函数(canonical / compute_hmac /
# compute_key_id / load_or_init_key 各 case);P2/P3 phase 测试 cmd_append / cmd_verify /
# finish_gate v3 fence 在后续 phase。
# =============================================================================

# import _forgeue_ledger_crypto module(沿 ForgeUE 测试 sys.path 风格)
import hashlib
import importlib

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
_crypto = importlib.import_module("_forgeue_ledger_crypto")


# -----------------------------------------------------------------------------
# canonical_payload 测试(D-CanonicalJSON)
# -----------------------------------------------------------------------------


def test_canonical_payload_excludes_hmac_includes_prev_hmac():
    """canonical bytes 不含 hmac 字段,含 prev_hmac 字段(D-CanonicalJSON 核心 invariant)。"""
    record = {
        "agent_id": "abc1234567890def0",
        "round": 1,
        "role": "implementer",
        "prev_hmac": "0" * 64,
        "hmac": "deadbeef" * 8,  # 64 hex
    }
    canonical = _crypto.canonical_payload(record)
    parsed = json.loads(canonical.decode("utf-8"))
    assert "hmac" not in parsed
    assert "prev_hmac" in parsed
    assert parsed["prev_hmac"] == "0" * 64


def test_canonical_payload_field_order_invariant():
    """打乱 record 字段插入顺序,canonical bytes 相同(sort_keys=True 保证)。"""
    r1 = {
        "agent_id": "a", "round": 1, "role": "implementer",
        "prev_hmac": "0" * 64, "hmac": "x" * 64,
    }
    r2 = {
        "hmac": "x" * 64, "role": "implementer", "round": 1,
        "prev_hmac": "0" * 64, "agent_id": "a",
    }
    assert _crypto.canonical_payload(r1) == _crypto.canonical_payload(r2)


def test_canonical_payload_no_whitespace():
    """canonical bytes 无 whitespace(separators=(",", ":");跨实现一致性)。"""
    record = {"a": 1, "b": 2}
    canonical = _crypto.canonical_payload(record).decode("utf-8")
    assert canonical == '{"a":1,"b":2}'  # 无空格 + sort_keys


def test_canonical_payload_unicode_utf8():
    """canonical bytes UTF-8 encoded(ensure_ascii=False;与 ledger 文件 encoding 一致)。"""
    record = {"role": "测试", "prev_hmac": "0" * 64}
    canonical = _crypto.canonical_payload(record)
    assert "测试".encode("utf-8") in canonical


# -----------------------------------------------------------------------------
# compute_hmac 测试(D-HashChain core)
# -----------------------------------------------------------------------------


def test_compute_hmac_deterministic():
    """同 input 同 key 产生同 hmac(HMAC-SHA256 deterministic)。"""
    key = b"test_key_32_bytes_long_dummy_!!!"  # exactly 32 bytes
    record = {
        "agent_id": "a", "round": 1, "role": "implementer",
        "prev_hmac": "0" * 64,
    }
    h1 = _crypto.compute_hmac(key, record)
    h2 = _crypto.compute_hmac(key, record)
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex
    # hex format
    assert all(c in "0123456789abcdef" for c in h1)


def test_compute_hmac_key_sensitive():
    """不同 key 产生不同 hmac(HMAC 安全性)。"""
    record = {
        "agent_id": "a", "round": 1, "role": "implementer",
        "prev_hmac": "0" * 64,
    }
    h1 = _crypto.compute_hmac(b"key1" + b"\x00" * 28, record)
    h2 = _crypto.compute_hmac(b"key2" + b"\x00" * 28, record)
    assert h1 != h2


def test_compute_hmac_record_sensitive():
    """同 key 不同 record 产生不同 hmac(完整性保证)。"""
    key = b"\x42" * 32
    r1 = {"agent_id": "a", "round": 1, "role": "implementer", "prev_hmac": "0" * 64}
    r2 = {"agent_id": "b", "round": 1, "role": "implementer", "prev_hmac": "0" * 64}
    assert _crypto.compute_hmac(key, r1) != _crypto.compute_hmac(key, r2)


# -----------------------------------------------------------------------------
# compute_key_id 测试(D-KeyLocation;16-char fingerprint)
# -----------------------------------------------------------------------------


def test_compute_key_id_truncated_sha256():
    """key_id == sha256(key)[:16](16 hex chars = 64-bit fingerprint)。"""
    key = b"\x42" * 32
    expected = hashlib.sha256(key).hexdigest()[:16]
    actual = _crypto.compute_key_id(key)
    assert actual == expected
    assert len(actual) == 16
    assert all(c in "0123456789abcdef" for c in actual)


def test_compute_key_id_different_keys_produce_different_ids():
    """不同 key 产生不同 key_id(fingerprint 区分性)。"""
    k1 = b"\x42" * 32
    k2 = b"\x43" * 32
    assert _crypto.compute_key_id(k1) != _crypto.compute_key_id(k2)


# -----------------------------------------------------------------------------
# load_or_init_key 测试(D-KeyRotationHandling 6 状态)
# -----------------------------------------------------------------------------


def test_load_or_init_key_creates_file_if_missing(tmp_path: Path):
    """首次 init:文件不存在 + secrets.token_bytes(32) + JSON 写入(D-KeyRotationHandling state 1)。"""
    key_file = tmp_path / ".claude" / "forgeue_ledger_key"
    key, key_id = _crypto.load_or_init_key(key_file)

    # 返回值 sanity
    assert len(key) == 32
    assert len(key_id) == 16

    # 文件落盘 + JSON schema
    assert key_file.exists()
    payload = json.loads(key_file.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert len(payload["key_hex"]) == 64
    assert "created_at" in payload
    # key_hex 与返回 key bytes 对应
    assert bytes.fromhex(payload["key_hex"]) == key


def test_load_or_init_key_returns_existing(tmp_path: Path):
    """已存在 + 二次调用返回相同 key_bytes / key_id(D-KeyRotationHandling state 2)。"""
    key_file = tmp_path / ".claude" / "forgeue_ledger_key"
    key1, kid1 = _crypto.load_or_init_key(key_file)
    key2, kid2 = _crypto.load_or_init_key(key_file)
    assert key1 == key2
    assert kid1 == kid2


def test_load_or_init_key_corrupted_raises_json(tmp_path: Path):
    """JSON 损坏 → SystemExit(7)(D-KeyRotationHandling state 3 fail-closed)。"""
    key_file = tmp_path / ".claude" / "forgeue_ledger_key"
    key_file.parent.mkdir(parents=True)
    key_file.write_text("{not valid json", encoding="utf-8")

    import pytest
    with pytest.raises(SystemExit) as excinfo:
        _crypto.load_or_init_key(key_file)
    assert excinfo.value.code == 7


def test_load_or_init_key_corrupted_raises_short_key_hex(tmp_path: Path):
    """key_hex 长度 ≠ 64 → SystemExit(7)(round 1 codex 测试 gap 补)。"""
    key_file = tmp_path / ".claude" / "forgeue_ledger_key"
    key_file.parent.mkdir(parents=True)
    key_file.write_text(
        json.dumps({
            "version": 1,
            "created_at": "2026-05-06T00:00:00+08:00",
            "key_hex": "abc",  # length 3, not 64
        }),
        encoding="utf-8",
    )

    import pytest
    with pytest.raises(SystemExit) as excinfo:
        _crypto.load_or_init_key(key_file)
    assert excinfo.value.code == 7


def test_load_or_init_key_corrupted_raises_unknown_version(tmp_path: Path):
    """version ≠ 1 → SystemExit(7)(D-KeyRotationHandling state 3)。"""
    key_file = tmp_path / ".claude" / "forgeue_ledger_key"
    key_file.parent.mkdir(parents=True)
    key_file.write_text(
        json.dumps({"version": 99, "created_at": "x", "key_hex": "0" * 64}),
        encoding="utf-8",
    )

    import pytest
    with pytest.raises(SystemExit) as excinfo:
        _crypto.load_or_init_key(key_file)
    assert excinfo.value.code == 7


def test_load_or_init_key_corrupted_raises_invalid_hex(tmp_path: Path):
    """key_hex 长度 64 但含非 hex 字符 → SystemExit(7)。"""
    key_file = tmp_path / ".claude" / "forgeue_ledger_key"
    key_file.parent.mkdir(parents=True)
    key_file.write_text(
        json.dumps({
            "version": 1,
            "created_at": "x",
            "key_hex": "z" * 64,  # length 64 but invalid hex
        }),
        encoding="utf-8",
    )

    import pytest
    with pytest.raises(SystemExit) as excinfo:
        _crypto.load_or_init_key(key_file)
    assert excinfo.value.code == 7


def test_load_or_init_key_creates_claude_dir_if_missing(tmp_path: Path):
    """~/.claude/ 不存在自动 mkdir(round 1 codex 测试 gap 补)。"""
    nested = tmp_path / "deeply" / "nested" / ".claude" / "forgeue_ledger_key"
    assert not nested.parent.exists()
    key, key_id = _crypto.load_or_init_key(nested)
    assert nested.exists()
    assert nested.parent.exists()


# =============================================================================
# P2 phase scope: forgeue_dispatch_ledger.py cmd_append + cmd_verify v3 升级测试
#
# 沿 micro_tasks P2.1 + P2.2.1(round 1+2+3 codex inline writeback 后):
# - happy path:append + verify 整链
# - forge:hand-edit / delete / reorder / first line prev_hmac nonzero
# - key boundary:rotation default fail-closed / archived replay opt-in / corrupted
# - schema strict 11-field(round 1 F5 scope expansion;round / agent_id / role /
#   dispatched_at / unknown field 等)
# - dispatch:ANY v3 信号 trigger v3 strict(round 3 F1 inline writeback);archived
#   ledger 路径限定(round 2 F1 + round 3 F1)
# =============================================================================

import hmac as _hmac_mod


def _seed_v3_ledger_via_append(
    tmp_path: Path,
    monkeypatch,
    n_lines: int = 1,
    change_id: str = "ldg-test",
    role: str = "implementer",
) -> tuple[Path, list[dict]]:
    """helper:用 cmd_append 真跑生成 N 行 v3 ledger;返回 (ledger_path, lines)。

    monkey-patch _crypto._KEY_FILE_PATH 隔离真实 user home。
    """
    monkeypatch.setattr(
        _crypto, "_KEY_FILE_PATH", tmp_path / ".claude" / "forgeue_ledger_key"
    )
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    # 沿 cmd_append CLI subprocess 调用(确保 wrapper 内部 import _crypto 用 monkey-patched path)
    # 但 subprocess 跑独立 Python 进程,monkey-patch 不传递。改为直接 in-process call cmd_append。
    import importlib
    ledger_cli = importlib.import_module("forgeue_dispatch_ledger")

    for i in range(n_lines):
        args = argparse.Namespace(
            change=change_id,
            agent_id=f"abc{i:014x}def",  # 17+ hex chars
            round=1,
            role=role,
            task_subject_hash=None,
            parent_session_id=None,
            ledger_path=str(ledger_path),
        )
        rc = ledger_cli.cmd_append(args)
        assert rc == 0, f"cmd_append iteration {i} failed"

    # 重新解析 ledger 行
    lines = [json.loads(raw) for raw in ledger_path.read_text(encoding="utf-8").splitlines() if raw.strip()]
    return (ledger_path, lines)


def _verify_via_subprocess_inproc(
    ledger_path: Path,
    change_id: str,
    monkeypatch_key_path: Path,
    allow_archived_replay: bool = False,
) -> tuple[int, str]:
    """helper:in-process call cmd_verify(monkey-patched key path)。返回 (exit_code, captured_stderr)。"""
    # in-process call(避免 subprocess 不传递 monkey-patch);沿 cmd_append 同款
    import importlib
    import io
    ledger_cli = importlib.import_module("forgeue_dispatch_ledger")

    args = argparse.Namespace(
        change=change_id,
        ledger_path=str(ledger_path),
        allow_archived_replay=allow_archived_replay,
    )
    # capture stderr
    captured_err = io.StringIO()
    captured_out = io.StringIO()
    saved_err, saved_out = sys.stderr, sys.stdout
    sys.stderr = captured_err
    sys.stdout = captured_out
    try:
        rc = ledger_cli.cmd_verify(args)
    finally:
        sys.stderr = saved_err
        sys.stdout = saved_out
    return (rc, captured_err.getvalue() + captured_out.getvalue())


# -----------------------------------------------------------------------------
# P2.1: cmd_append v3 测试(round 1+2+3 codex inline writeback 后)
# -----------------------------------------------------------------------------

import argparse  # noqa: E402(test 内部需要)


def test_v3_append_writes_11_field_schema(tmp_path: Path, monkeypatch):
    """wrapper_version="2.0" + append + 校输出行 JSON 含 11 字段。"""
    ledger, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=1)
    assert len(lines) == 1
    rec = lines[0]
    expected = {
        "agent_id", "round", "role", "task_subject_hash", "dispatched_at",
        "parent_session_id", "wrapper_version", "protocol_version",
        "key_id", "prev_hmac", "hmac",
    }
    assert set(rec.keys()) == expected, f"expected 11 fields, got {set(rec.keys())}"
    assert rec["wrapper_version"] == "2.0"
    assert rec["protocol_version"] == "v3"


def test_v3_append_first_line_prev_hmac_zeros(tmp_path: Path, monkeypatch):
    """首行 prev_hmac == '0' * 64。"""
    _, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=1)
    assert lines[0]["prev_hmac"] == "0" * 64


def test_v3_append_chain_links_prev_hmac(tmp_path: Path, monkeypatch):
    """第 N+1 行 prev_hmac == 第 N 行 hmac(D-HashChain)。"""
    _, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=3)
    assert len(lines) == 3
    for i in range(1, 3):
        assert lines[i]["prev_hmac"] == lines[i - 1]["hmac"], f"chain break at line {i+1}"


def test_v3_append_stdout_emits_ledger_line(tmp_path: Path, monkeypatch, capsys):
    """append 后 stdout 含 [LEDGER] line_count=<N> final_hmac=<hex>(D-LedgerTerminalProof)。"""
    monkeypatch.setattr(
        _crypto, "_KEY_FILE_PATH", tmp_path / ".claude" / "forgeue_ledger_key"
    )
    change_root = tmp_path / "openspec" / "changes" / "stdout-test"
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    import importlib
    ledger_cli = importlib.import_module("forgeue_dispatch_ledger")
    args = argparse.Namespace(
        change="stdout-test",
        agent_id="abcdef0123456789a",  # 17 chars
        round=1,
        role="implementer",
        task_subject_hash=None,
        parent_session_id=None,
        ledger_path=str(ledger_path),
    )
    rc = ledger_cli.cmd_append(args)
    assert rc == 0
    captured = capsys.readouterr()
    assert "[LEDGER]" in captured.out
    assert "line_count=1" in captured.out
    assert "final_hmac=" in captured.out


def test_v3_append_role_enum_validation(tmp_path: Path, monkeypatch):
    """invalid role → exit 5(沿现有 v2 行为;v3 不变)。"""
    monkeypatch.setattr(
        _crypto, "_KEY_FILE_PATH", tmp_path / ".claude" / "forgeue_ledger_key"
    )
    change_root = tmp_path / "openspec" / "changes" / "role-test"
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    import importlib
    ledger_cli = importlib.import_module("forgeue_dispatch_ledger")
    args = argparse.Namespace(
        change="role-test",
        agent_id="abcdef0123456789a",
        round=1,
        role="unknown_role",  # invalid
        task_subject_hash=None,
        parent_session_id=None,
        ledger_path=str(ledger_path),
    )
    rc = ledger_cli.cmd_append(args)
    assert rc == 5


# -----------------------------------------------------------------------------
# P2.2.1: cmd_verify v3 测试(round 1+2+3 codex inline writeback 后)
# -----------------------------------------------------------------------------


def test_v3_verify_pass_on_valid_chain(tmp_path: Path, monkeypatch):
    """N 行合法 v3 ledger → exit 0(happy path)。"""
    ledger, _ = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=3)
    rc, _ = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key")
    assert rc == 0


def test_v3_verify_fail_hand_edit_agent_id(tmp_path: Path, monkeypatch):
    """修改任意行 agent_id(保持 schema 合法 hex format)→ exit 5,error message prefix
    [hmac_mismatch](HMAC 重算 ≠ 行内 hmac 字段)。"""
    ledger, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=2)
    # hand-edit 第 2 行 agent_id(改 hex 字符但 schema 仍合法 — 17 chars all hex;
    # 保持行内 hmac 字段不变,触发 hmac_mismatch 路径而非 schema_violation)
    lines[1]["agent_id"] = "bcdef0123456789ab"  # 17 chars all hex,schema valid
    new_text = "\n".join(json.dumps(l, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for l in lines) + "\n"
    ledger.write_text(new_text, encoding="utf-8")

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key")
    assert rc == 5
    assert "[hmac_mismatch]" in err


def test_v3_verify_fail_delete_middle_line(tmp_path: Path, monkeypatch):
    """删除中间一行 → exit 5 [chain_break](D-HashChain catch 中间删行)。"""
    ledger, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=3)
    # 删除第 2 行
    new_lines = [lines[0], lines[2]]
    new_text = "\n".join(json.dumps(l, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for l in new_lines) + "\n"
    ledger.write_text(new_text, encoding="utf-8")

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key")
    assert rc == 5
    assert "[chain_break]" in err


def test_v3_verify_fail_reorder_lines(tmp_path: Path, monkeypatch):
    """交换两行 → exit 5 [chain_break]。"""
    ledger, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=3)
    # reorder:swap 第 1+2 行
    new_lines = [lines[1], lines[0], lines[2]]
    new_text = "\n".join(json.dumps(l, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for l in new_lines) + "\n"
    ledger.write_text(new_text, encoding="utf-8")

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key")
    assert rc == 5
    assert "[chain_break]" in err


def test_v3_verify_fail_first_line_prev_hmac_nonzero(tmp_path: Path, monkeypatch):
    """首行 prev_hmac != all-zeros → exit 5 [chain_break]。"""
    ledger, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=1)
    lines[0]["prev_hmac"] = "f" * 64  # 改首行 prev_hmac
    new_text = json.dumps(lines[0], ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ledger.write_text(new_text, encoding="utf-8")

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key")
    assert rc == 5
    assert "[chain_break]" in err


def test_v3_verify_fail_mixed_key_id_in_ledger(tmp_path: Path, monkeypatch):
    """同 ledger 内不同 key_id → exit 5 [key_id_inconsistent]。"""
    ledger, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=2)
    lines[1]["key_id"] = "deadbeef12345678"  # 不同 key_id
    new_text = "\n".join(json.dumps(l, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for l in lines) + "\n"
    ledger.write_text(new_text, encoding="utf-8")

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key")
    assert rc == 5
    assert "[key_id_inconsistent]" in err


# round 1 codex F2 inline writeback: key_id mismatch active default fail-closed
def test_v3_verify_fail_key_id_mismatch_active_default_blocker(tmp_path: Path, monkeypatch):
    """active v3 evidence + 切 key 后 ledger key_id 不一致 → default fail-closed BLOCKER。"""
    ledger, _ = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=2)

    # 删除 key 文件 + 重新 init(模拟 user rotation key)
    key_path = tmp_path / ".claude" / "forgeue_ledger_key"
    key_path.unlink()
    # 重新 load 创建新 key(monkeypatch 仍生效)
    new_key, new_kid = _crypto.load_or_init_key()
    # 现在 ledger 里的行 key_id 与文件 key_id 不同

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", key_path, allow_archived_replay=False)
    assert rc == 5
    assert "[key_id_mismatch]" in err


# round 1 + round 2 codex F1 inline writeback: archived replay opt-in 路径限定
def test_v3_verify_archived_replay_optin_archived_path_warn(tmp_path: Path, monkeypatch):
    """archive/ 路径 + --allow-archived-replay flag + ledger key_id mismatch → exit 6 user override。"""
    monkeypatch.setattr(
        _crypto, "_KEY_FILE_PATH", tmp_path / ".claude" / "forgeue_ledger_key"
    )
    # 在 archive/ 路径下创建 ledger
    change_id = "archived-ldg"
    change_root = tmp_path / "openspec" / "changes" / "archive" / "2026-05-06-archived-ldg"
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    import importlib
    ledger_cli = importlib.import_module("forgeue_dispatch_ledger")
    # append 写一行 v3 ledger
    args = argparse.Namespace(
        change=change_id,
        agent_id="aaa00000000000000a",
        round=1,
        role="implementer",
        task_subject_hash=None,
        parent_session_id=None,
        ledger_path=str(ledger_path),
    )
    ledger_cli.cmd_append(args)

    # 删除 key 重新 init(模拟 rotation)
    key_path = tmp_path / ".claude" / "forgeue_ledger_key"
    key_path.unlink()
    _crypto.load_or_init_key()  # 新 key,key_id 不同

    # cmd_verify --allow-archived-replay
    rc, err = _verify_via_subprocess_inproc(ledger_path, change_id, key_path, allow_archived_replay=True)
    assert rc == 6
    assert "[key_rotation_user_override]" in err


# round 2 codex F1 inline writeback: --allow-archived-replay flag + active path → BLOCKER
def test_v3_verify_allow_archived_replay_flag_active_path_rejected(tmp_path: Path, monkeypatch):
    """active path(无 archive/ segment)+ --allow-archived-replay flag → exit 5。"""
    ledger, _ = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=1)
    # ledger 路径 tmp_path/openspec/changes/ldg-test/dispatch_ledger.jsonl 不含 archive/

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key", allow_archived_replay=True)
    assert rc == 5
    assert "not in archive/ path" in err.lower() or "not in archive/" in err


# round 1 codex F5 scope expansion: strict schema 11-field
def test_v3_verify_fail_unknown_field(tmp_path: Path, monkeypatch):
    """ledger 行加未知字段 → exit 5 [schema_violation]。"""
    ledger, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=1)
    lines[0]["extra_field_xyz"] = "anything"  # unknown field
    new_text = json.dumps(lines[0], ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ledger.write_text(new_text, encoding="utf-8")

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key")
    assert rc == 5
    assert "[schema_violation]" in err


def test_v3_verify_fail_negative_round(tmp_path: Path, monkeypatch):
    """ledger 行 round: -1 → exit 5 [schema_violation]。"""
    ledger, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=1)
    lines[0]["round"] = -1  # negative
    new_text = json.dumps(lines[0], ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ledger.write_text(new_text, encoding="utf-8")

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key")
    assert rc == 5
    assert "[schema_violation]" in err


def test_v3_verify_fail_invalid_role(tmp_path: Path, monkeypatch):
    """ledger 行 role: 'unknown_role' → exit 5 [schema_violation]。

    NOTE: cmd_append role enum 校验在 wrapper 层 (early reject);本测试模拟 LLM hand-edit
    ledger 文件后的场景(直接写文件,不通过 cmd_append)。
    """
    ledger, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=1)
    lines[0]["role"] = "unknown_role"
    new_text = json.dumps(lines[0], ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ledger.write_text(new_text, encoding="utf-8")

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key")
    assert rc == 5
    assert "[schema_violation]" in err


# round 3 codex F1 inline writeback: ANY v3 信号 dispatch
def test_v3_dispatch_via_hmac_field_only(tmp_path: Path, monkeypatch):
    """LLM 改所有行 protocol_version='v2' 但漏改 hmac 字段 → 仍触发 v3 strict validation
    (round 3 codex F1 inline writeback 防降级 attack)。"""
    ledger, lines = _seed_v3_ledger_via_append(tmp_path, monkeypatch, n_lines=1)
    # 把 protocol_version 改 'v2'(LLM 试图降级)+ 删除部分 v3 字段(但留 hmac)
    lines[0]["protocol_version"] = "v2"  # 降级企图
    new_text = json.dumps(lines[0], ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ledger.write_text(new_text, encoding="utf-8")

    rc, err = _verify_via_subprocess_inproc(ledger, "ldg-test", tmp_path / ".claude" / "forgeue_ledger_key")
    # ANY v3 信号(hmac/prev_hmac/key_id)仍存在 → 触发 v3 strict;strict 校 protocol_version='v3' fail
    assert rc == 5
    assert "[schema_violation]" in err
    assert "protocol_version" in err.lower() or "'v3'" in err


def test_v2_legacy_ledger_no_v3_signal_pass(tmp_path: Path, monkeypatch):
    """纯 v2 ledger(无 hmac/prev_hmac/key_id 字段;wrapper_version='1.0';无 protocol_version)
    → 走 v2 schema-only legacy 路径 pass(archived backward compatible)。"""
    monkeypatch.setattr(
        _crypto, "_KEY_FILE_PATH", tmp_path / ".claude" / "forgeue_ledger_key"
    )
    change_id = "legacy-v2"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    ledger_path = change_root / "dispatch_ledger.jsonl"

    # 手工写纯 v2 ledger(7 字段,wrapper_version="1.0",无 v3 信号)
    v2_record = {
        "agent_id": "v2agent000000000a",
        "round": 1,
        "role": "implementer",
        "task_subject_hash": None,
        "dispatched_at": _crypto.datetime.now().astimezone().isoformat(timespec="seconds"),
        "parent_session_id": None,
        "wrapper_version": "1.0",  # v2 marker
    }
    ledger_path.write_text(json.dumps(v2_record, ensure_ascii=False) + "\n", encoding="utf-8")

    rc, _ = _verify_via_subprocess_inproc(ledger_path, change_id, tmp_path / ".claude" / "forgeue_ledger_key")
    assert rc == 0  # v2 legacy schema-only pass
