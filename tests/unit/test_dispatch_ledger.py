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
