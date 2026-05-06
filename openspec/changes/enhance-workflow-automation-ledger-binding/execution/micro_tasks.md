---
change_id: enhance-workflow-automation-ledger-binding
stage: S2
evidence_type: micro_tasks
contract_refs:
  - tasks.md#P1
  - tasks.md#P2
  - tasks.md#P3
  - tasks.md#P4
  - tasks.md#P5
  - tasks.md#P6
  - tasks.md#P7
  - design.md#decisions
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v2
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
task_granularity: phase
created_at: 2026-05-06T15:00:00+08:00
---

# Micro Tasks — enhance-workflow-automation-ledger-binding

> 沿 `execution_plan.md` Phase Map;每 phase 1 micro section,TDD 4-step 节奏(failing test → minimal impl → regress green → commit)。
> P0 已完成本会话(commit 81edd63 round 1 + commit d96076f round 2);本文件覆盖 P1-P9。
> Implementer 走 `/forgeue:change-apply-direct` 路径,沿 `executing-plans` + `test-driven-development` SKILL。

---

## P1 — `tools/_forgeue_ledger_crypto.py` 新建 + 单元测试

**对应 tasks.md**:[P1.1 ~ P1.4](../tasks.md#p1--crypto-helper-module-toolsforgeueledgercrypto.py)

### micro-P1.1 Read 参考工具

- [ ] Read `tools/forgeue_dispatch_ledger.py` 全部(stdlib argparse 风格 + JSONL append-only pattern)
- [ ] Read `tools/forgeue_finish_gate.py:_check_dispatch_ledger`(line 2026-2120,v2 verify 现状 + Sync drift 警告段)
- [ ] Read `openspec/changes/enhance-workflow-automation-ledger-binding/design.md`:D-CanonicalJSON / D-HashChain / D-LedgerTerminalProof / D-KeyRotationHandling / D-Scope-F3-MergeWithP12.8 5 段
- [ ] Read `openspec/changes/enhance-workflow-automation-ledger-binding/specs/examples-and-acceptance/spec.md`:6 ADDED + 2 MODIFIED Requirement(全部 Scenario)

### micro-P1.2 写 _forgeue_ledger_crypto.py 失败测试(canonical + compute_hmac)

- [ ] Create `tests/unit/test_dispatch_ledger.py` 加导入(若已存在则在末尾追加 v3 case 段):

```python
# 沿现有 v2 测试模式
import pytest
import hashlib
import hmac
import json
from pathlib import Path

# 路径 sys.path 加 tools/(沿现有 forgeue_dispatch_ledger 测试)
import sys
TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))
import _forgeue_ledger_crypto as crypto
import forgeue_dispatch_ledger as ledger_cli  # for cmd_append / cmd_verify integration
```

- [ ] 加 canonical / HMAC core 测试(沿 spec.md "v3 ledger schema with HMAC chain" Scenario):

```python
def test_canonical_payload_excludes_hmac_includes_prev_hmac():
    """canonical bytes 不含 hmac 字段,含 prev_hmac 字段(沿 D-CanonicalJSON)。"""
    record = {
        "agent_id": "abc1234567890def0",
        "round": 1,
        "role": "implementer",
        "prev_hmac": "0" * 64,
        "hmac": "deadbeef" * 8,  # 64 hex
    }
    canonical = crypto.canonical_payload(record)
    parsed = json.loads(canonical.decode("utf-8"))
    assert "hmac" not in parsed
    assert "prev_hmac" in parsed
    assert parsed["prev_hmac"] == "0" * 64

def test_canonical_payload_field_order_invariant():
    """打乱 record 字段插入顺序,canonical bytes 相同(sort_keys=True)。"""
    r1 = {"agent_id": "a", "round": 1, "role": "implementer", "prev_hmac": "0"*64, "hmac": "x"*64}
    r2 = {"hmac": "x"*64, "role": "implementer", "round": 1, "prev_hmac": "0"*64, "agent_id": "a"}
    assert crypto.canonical_payload(r1) == crypto.canonical_payload(r2)

def test_compute_hmac_deterministic():
    """同 input 同 key 产生同 hmac。"""
    key = b"test_key_32_bytes_long_dummy_!!!"  # 32 bytes
    record = {"agent_id": "a", "round": 1, "role": "implementer", "prev_hmac": "0"*64}
    h1 = crypto.compute_hmac(key, record)
    h2 = crypto.compute_hmac(key, record)
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex

def test_compute_hmac_key_sensitive():
    """不同 key 产生不同 hmac。"""
    record = {"agent_id": "a", "round": 1, "role": "implementer", "prev_hmac": "0"*64}
    h1 = crypto.compute_hmac(b"key1" + b"\x00" * 28, record)
    h2 = crypto.compute_hmac(b"key2" + b"\x00" * 28, record)
    assert h1 != h2

def test_compute_key_id_truncated_sha256():
    """key_id == sha256(key)[:16](16 hex chars = 64-bit fingerprint)。"""
    key = b"\x42" * 32
    expected = hashlib.sha256(key).hexdigest()[:16]
    assert crypto.compute_key_id(key) == expected
    assert len(crypto.compute_key_id(key)) == 16
```

- [ ] Run: `python -m pytest tests/unit/test_dispatch_ledger.py::test_canonical_payload_excludes_hmac_includes_prev_hmac -v`
  Expected: FAIL with "ModuleNotFoundError: No module named '_forgeue_ledger_crypto'"

### micro-P1.3 实施 _forgeue_ledger_crypto.py(最小可过测试版)

- [ ] Create `tools/_forgeue_ledger_crypto.py`:

```python
#!/usr/bin/env python3
"""ForgeUE v3 ledger HMAC chain crypto helper (stdlib-only).

D-CanonicalJSON / D-HashChain / D-KeyLocation / D-KeyRotationHandling /
D-LedgerTerminalProof / D-Scope-F3-MergeWithP12.8 / D-ArchivedReplayPathBoundary。

模块顶层零副作用(沿 probes 协定);下划线前缀 internal,不暴露 CLI。
"""
from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path

_KEY_FILE_PATH = Path.home() / ".claude" / "forgeue_ledger_key"
_KEY_VERSION = 1
_KEY_BYTES_LEN = 32  # 256-bit HMAC key
_KEY_HEX_LEN = 64  # 32 bytes = 64 hex chars

EXIT_OK = 0
EXIT_VERIFY_FAIL = 5
EXIT_KEY_ROTATION_USER_OVERRIDE = 6
EXIT_KEY_FILE_CORRUPTED = 7

VALID_ROLES = frozenset({
    "implementer", "spec_reviewer", "code_quality_reviewer",
    "final_reviewer", "implementer_round_2_fix", "spec_reviewer_round_2_review",
})


def canonical_payload(record: dict) -> bytes:
    """canonical JSON 序列化(沿 D-CanonicalJSON):排除 hmac + sort_keys + 无空格 + UTF-8。"""
    payload = {k: v for k, v in record.items() if k != "hmac"}
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_hmac(key: bytes, record: dict) -> str:
    """HMAC-SHA256 over canonical_payload。返回 hex。"""
    canonical = canonical_payload(record)
    return hmac_mod.new(key, canonical, hashlib.sha256).hexdigest()


def compute_key_id(key: bytes) -> str:
    """key_id = sha256(key).hexdigest()[:16](16 hex chars = 64-bit fingerprint)。"""
    return hashlib.sha256(key).hexdigest()[:16]


def load_or_init_key(key_file_path: Path | None = None) -> tuple[bytes, str]:
    """Lifecycle 6 状态(沿 D-KeyRotationHandling round 1 inline writeback 后):
    - 首次 init: 文件不存在 + os.O_EXCL 创建 + secrets.token_bytes(32) + chmod 0600 + 打印 INFO
    - 正常 load: 已存在 + JSON 合法 + key_hex 64 chars
    - 文件损坏: JSON 解析失败 / key_hex 长度错 / version ≠ 1 → 抛 SystemExit(7)

    返回 (key_bytes, key_id)。
    """
    path = key_file_path or _KEY_FILE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        # 首次 init,os.O_EXCL 防 race
        key = secrets.token_bytes(_KEY_BYTES_LEN)
        payload = {
            "version": _KEY_VERSION,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "key_hex": key.hex(),
        }
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            # race 情况:并发 init,另一进程刚创建,retry-load
            return load_or_init_key(key_file_path)
        try:
            os.write(fd, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
        finally:
            os.close(fd)
        # Linux/Mac chmod 0600(Windows 上 chmod 等价于 read-only bit,obscurity-not-strict-permission)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        key_id = compute_key_id(key)
        print(f"[INFO] HMAC key initialized at {path} (key_id={key_id})")
        return (key, key_id)

    # 正常 load
    try:
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERROR] key file corrupted at {path}: {exc}; backup + remove file to re-init", file=os.sys.stderr)
        raise SystemExit(EXIT_KEY_FILE_CORRUPTED)

    if payload.get("version") != _KEY_VERSION:
        print(f"[ERROR] key file corrupted at {path}: unknown version {payload.get('version')}; backup + remove file to re-init", file=os.sys.stderr)
        raise SystemExit(EXIT_KEY_FILE_CORRUPTED)

    key_hex = payload.get("key_hex", "")
    if len(key_hex) != _KEY_HEX_LEN:
        print(f"[ERROR] key file corrupted at {path}: key_hex length {len(key_hex)} != 64; backup + remove file to re-init", file=os.sys.stderr)
        raise SystemExit(EXIT_KEY_FILE_CORRUPTED)

    try:
        key = bytes.fromhex(key_hex)
    except ValueError:
        print(f"[ERROR] key file corrupted at {path}: key_hex not valid hex; backup + remove file to re-init", file=os.sys.stderr)
        raise SystemExit(EXIT_KEY_FILE_CORRUPTED)

    return (key, compute_key_id(key))


def verify_chain_v3(key: bytes, lines: list[dict], evidence_frontmatter: dict | None = None) -> tuple[str, str | None]:
    """整链 verify(D-HashChain + D-KeyRotationHandling 双路径)。

    返回 (status, error_msg);status ∈ {ok, hmac_mismatch, chain_break, key_id_inconsistent,
    key_id_mismatch, key_rotation_user_override_required}。
    """
    if not lines:
        return ("ok", None)

    current_key_id = compute_key_id(key)
    ledger_key_id = lines[0].get("key_id")

    # 同一 ledger 内 key_id 一致性
    for line_no, record in enumerate(lines, 1):
        if record.get("key_id") != ledger_key_id:
            return ("key_id_inconsistent", f"line {line_no}: expected {ledger_key_id}, got {record.get('key_id')}")

    # ledger key_id vs 当前 file key_id(D-KeyRotationHandling 双路径)
    if ledger_key_id != current_key_id:
        # archived replay opt-in 路径
        if evidence_frontmatter and evidence_frontmatter.get("ledger_archived_replay") is True:
            return ("key_rotation_user_override_required", f"ledger key_id {ledger_key_id} != current file key_id {current_key_id}; HMAC verify skipped per opt-in")
        # default fail-closed
        return ("key_id_mismatch", f"ledger key_id {ledger_key_id} != current file key_id {current_key_id}; HMAC verify cannot proceed without rotated-from key")

    # chain verify
    expected_prev = "0" * 64
    for line_no, record in enumerate(lines, 1):
        if record.get("prev_hmac") != expected_prev:
            return ("chain_break", f"line {line_no}: prev_hmac mismatch")

        expected_hmac = compute_hmac(key, record)
        if record.get("hmac") != expected_hmac:
            return ("hmac_mismatch", f"line {line_no}: HMAC recompute mismatch")

        expected_prev = record["hmac"]

    return ("ok", None)


def verify_terminal_proof(lines: list[dict], evidence_line_count: int, evidence_final_hmac: str) -> tuple[str, str | None]:
    """terminal proof verify(D-LedgerTerminalProof)。

    返回 (status, error_msg);status ∈ {ok, tail_truncation_detected, final_hmac_mismatch}。
    """
    actual_count = len(lines)
    if actual_count != evidence_line_count:
        return ("tail_truncation_detected", f"declared {evidence_line_count} lines, actual {actual_count}")

    if not lines:
        # 空 ledger 但 evidence 声明 0 行 — 接受(虽实践不会发生 v3 evidence + 0 行 ledger)
        return ("ok", None) if evidence_final_hmac == "0" * 64 else ("final_hmac_mismatch", "empty ledger but final_hmac != all zeros")

    actual_final_hmac = lines[-1].get("hmac", "")
    if actual_final_hmac != evidence_final_hmac:
        return ("final_hmac_mismatch", f"declared {evidence_final_hmac}, actual {actual_final_hmac}")

    return ("ok", None)


_AGENT_ID_RE = re.compile(r"^[a-f0-9]{17,}$")
_KEY_ID_RE = re.compile(r"^[a-f0-9]{16}$")
_HMAC_RE = re.compile(r"^[a-f0-9]{64}$")
_WRAPPER_VERSION_RE = re.compile(r"^\d+\.\d+$")
_TASK_SUBJECT_HASH_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
_PARENT_SESSION_ID_RE = re.compile(r"^[a-f0-9-]{36}$")

_V3_EXPECTED_FIELDS = frozenset({
    "agent_id", "round", "role", "task_subject_hash", "dispatched_at",
    "parent_session_id", "wrapper_version", "protocol_version",
    "key_id", "prev_hmac", "hmac",
})


def verify_strict_schema_v3(lines: list[dict]) -> tuple[str, str | None]:
    """strict 11-field schema validation(D-Scope-F3-MergeWithP12.8)。

    返回 (status, error_msg);status ∈ {ok, schema_violation}。
    """
    for line_no, record in enumerate(lines, 1):
        # 字段集精确 11 字段
        actual_fields = set(record.keys())
        unknown = actual_fields - _V3_EXPECTED_FIELDS
        if unknown:
            return ("schema_violation", f"line {line_no}: unknown field(s) {sorted(unknown)}")
        missing = _V3_EXPECTED_FIELDS - actual_fields
        if missing:
            return ("schema_violation", f"line {line_no}: missing field(s) {sorted(missing)}")

        # agent_id format
        if not isinstance(record["agent_id"], str) or not _AGENT_ID_RE.match(record["agent_id"]):
            return ("schema_violation", f"line {line_no}: field 'agent_id' MUST match ^[a-f0-9]{{17,}}$")

        # round positive int(显式拒 bool;Python bool 是 int 子类)
        round_val = record["round"]
        if isinstance(round_val, bool) or not isinstance(round_val, int) or round_val <= 0:
            return ("schema_violation", f"line {line_no}: field 'round' MUST be positive integer (not bool / float), got {round_val!r}")

        # role enum
        if record["role"] not in VALID_ROLES:
            return ("schema_violation", f"line {line_no}: field 'role' MUST be in VALID_ROLES, got {record['role']!r}")

        # task_subject_hash null or sha256 format
        tsh = record["task_subject_hash"]
        if tsh is not None and (not isinstance(tsh, str) or not _TASK_SUBJECT_HASH_RE.match(tsh)):
            return ("schema_violation", f"line {line_no}: field 'task_subject_hash' MUST be null or ^sha256:[a-f0-9]{{64}}$")

        # dispatched_at ISO8601 tz-aware
        try:
            dt = datetime.fromisoformat(record["dispatched_at"])
            if dt.tzinfo is None:
                return ("schema_violation", f"line {line_no}: field 'dispatched_at' MUST be ISO8601 tz-aware")
        except (ValueError, TypeError):
            return ("schema_violation", f"line {line_no}: field 'dispatched_at' MUST be parseable ISO8601 string")

        # parent_session_id null or UUID
        psid = record["parent_session_id"]
        if psid is not None and (not isinstance(psid, str) or not _PARENT_SESSION_ID_RE.match(psid)):
            return ("schema_violation", f"line {line_no}: field 'parent_session_id' MUST be null or UUID format")

        # wrapper_version major.minor
        if not isinstance(record["wrapper_version"], str) or not _WRAPPER_VERSION_RE.match(record["wrapper_version"]):
            return ("schema_violation", f"line {line_no}: field 'wrapper_version' MUST match ^\\d+\\.\\d+$")

        # protocol_version exact "v3"
        if record["protocol_version"] != "v3":
            return ("schema_violation", f"line {line_no}: field 'protocol_version' MUST be exactly 'v3', got {record['protocol_version']!r}")

        # key_id format
        if not isinstance(record["key_id"], str) or not _KEY_ID_RE.match(record["key_id"]):
            return ("schema_violation", f"line {line_no}: field 'key_id' MUST match ^[a-f0-9]{{16}}$")

        # prev_hmac format
        if not isinstance(record["prev_hmac"], str) or not _HMAC_RE.match(record["prev_hmac"]):
            return ("schema_violation", f"line {line_no}: field 'prev_hmac' MUST match ^[a-f0-9]{{64}}$")

        # hmac format
        if not isinstance(record["hmac"], str) or not _HMAC_RE.match(record["hmac"]):
            return ("schema_violation", f"line {line_no}: field 'hmac' MUST match ^[a-f0-9]{{64}}$")

    return ("ok", None)
```

- [ ] Run: `python -m pytest tests/unit/test_dispatch_ledger.py::test_canonical_payload_excludes_hmac_includes_prev_hmac -v`
  Expected: PASS
- [ ] Run: `python -m pytest tests/unit/test_dispatch_ledger.py -k 'canonical or compute_hmac or compute_key_id' -v`
  Expected: PASS(5 case)

### micro-P1.4 加 load_or_init_key 测试

- [ ] 加 lifecycle 6 状态测试到 `tests/unit/test_dispatch_ledger.py`(沿 spec.md "HMAC key lifecycle for v3 cryptographic ledger binding" Scenario):

```python
def test_load_or_init_key_creates_file_if_missing(tmp_path, monkeypatch):
    """首次 init:文件不存在 + secrets.token_bytes(32) + 0o600 + INFO 行。"""
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", tmp_path / ".claude" / "forgeue_ledger_key")
    key, key_id = crypto.load_or_init_key()
    assert len(key) == 32
    assert len(key_id) == 16
    key_file = tmp_path / ".claude" / "forgeue_ledger_key"
    assert key_file.exists()
    payload = json.loads(key_file.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert len(payload["key_hex"]) == 64
    assert "created_at" in payload

def test_load_or_init_key_returns_existing(tmp_path, monkeypatch):
    """已存在 + 二次调用返回相同 key_bytes / key_id。"""
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", tmp_path / ".claude" / "forgeue_ledger_key")
    key1, kid1 = crypto.load_or_init_key()
    key2, kid2 = crypto.load_or_init_key()
    assert key1 == key2
    assert kid1 == kid2

def test_load_or_init_key_corrupted_raises_json(tmp_path, monkeypatch):
    """JSON 损坏 → exit 7。"""
    key_file = tmp_path / ".claude" / "forgeue_ledger_key"
    key_file.parent.mkdir(parents=True)
    key_file.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", key_file)
    with pytest.raises(SystemExit) as excinfo:
        crypto.load_or_init_key()
    assert excinfo.value.code == 7

def test_load_or_init_key_corrupted_raises_short_key_hex(tmp_path, monkeypatch):
    """key_hex 长度 ≠ 64 → exit 7。"""
    key_file = tmp_path / ".claude" / "forgeue_ledger_key"
    key_file.parent.mkdir(parents=True)
    key_file.write_text(json.dumps({"version": 1, "created_at": "2026-05-06T00:00:00+08:00", "key_hex": "abc"}), encoding="utf-8")
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", key_file)
    with pytest.raises(SystemExit) as excinfo:
        crypto.load_or_init_key()
    assert excinfo.value.code == 7

def test_load_or_init_key_corrupted_raises_unknown_version(tmp_path, monkeypatch):
    """version ≠ 1 → exit 7。"""
    key_file = tmp_path / ".claude" / "forgeue_ledger_key"
    key_file.parent.mkdir(parents=True)
    key_file.write_text(json.dumps({"version": 99, "created_at": "x", "key_hex": "0" * 64}), encoding="utf-8")
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", key_file)
    with pytest.raises(SystemExit) as excinfo:
        crypto.load_or_init_key()
    assert excinfo.value.code == 7
```

- [ ] Run: `python -m pytest tests/unit/test_dispatch_ledger.py -k 'load_or_init_key' -v`
  Expected: PASS(5 case)

### micro-P1.5 commit P1

- [ ] Run: `python -m pytest tests/unit/test_dispatch_ledger.py -v`
  Expected: 全 P1 case pass(canonical / compute_hmac / compute_key_id / load_or_init_key 共 ~10 case)
- [ ] Run: `git add tools/_forgeue_ledger_crypto.py tests/unit/test_dispatch_ledger.py && git commit -m "feat(forgeue): _forgeue_ledger_crypto.py — stdlib HMAC chain helper for v3 ledger binding"`

---

## P2 — `tools/forgeue_dispatch_ledger.py` 升级 v3

**对应 tasks.md**:[P2.1 ~ P2.4](../tasks.md#p2--toolsforgeue_dispatch_ledger.py-升级-v3)

### micro-P2.1 写 cmd_append v3 失败测试

- [ ] 加 cmd_append v3 测试 case 到 `tests/unit/test_dispatch_ledger.py`(沿 spec.md MODIFIED "Dispatch ledger append-only contract" Scenario):

```python
import subprocess
import sys
from datetime import datetime

DISPATCH_LEDGER_PY = TOOLS_DIR / "forgeue_dispatch_ledger.py"

def _run_append(change_dir, args, monkey_key_path=None, env=None):
    """helper: 跑 cmd_append + 返回 (returncode, stdout, stderr, ledger_path)。"""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    cmd = [sys.executable, str(DISPATCH_LEDGER_PY), "append"] + args
    result = subprocess.run(cmd, cwd=str(change_dir.parent.parent.parent), capture_output=True, text=True, env=full_env)
    return result

def test_v3_append_writes_11_field_schema(tmp_path, monkeypatch):
    """wrapper_version="2.0" + append + 校输出行 JSON 含 11 字段。"""
    # monkey-patch key path 隔离
    monkeypatch.setattr(crypto, "_KEY_FILE_PATH", tmp_path / ".claude" / "forgeue_ledger_key")
    # ... 测试 cmd_append 写 11 字段 + 行内 protocol_version: "v3" + key_id 16 chars + prev_hmac == "0"*64 + hmac 64 chars

def test_v3_append_first_line_prev_hmac_zeros(tmp_path):
    """首行 prev_hmac == '0' * 64。"""

def test_v3_append_chain_links_prev_hmac(tmp_path):
    """第 N+1 行 prev_hmac == 第 N 行 hmac。"""

def test_v3_append_stdout_emits_ledger_line(tmp_path):
    """append 后 stdout 含 [LEDGER] line_count=<N> final_hmac=<hex>(D-LedgerTerminalProof)。"""

# ... 类似展开 ~5 测试
```

- [ ] Run: `python -m pytest tests/unit/test_dispatch_ledger.py -k 'v3_append' -v`
  Expected: FAIL(cmd_append 还是 v2 schema)

### micro-P2.2 升级 forgeue_dispatch_ledger.py(WRAPPER_VERSION + cmd_append + cmd_verify dispatch + flag)

- [ ] Edit `tools/forgeue_dispatch_ledger.py`:
  - `WRAPPER_VERSION = "2.0"`(常量从 1.0 升)
  - `cmd_append`:沿 design.md "写入流程"(读 prev_hmac + 算 hmac + 写 11 字段);加 `_forgeue_ledger_crypto` import
  - `cmd_verify`:沿 protocol_version 字段 dispatch(v3 → `verify_chain_v3` + `verify_terminal_proof`(若 `--evidence-line-count` + `--evidence-final-hmac` flag 提供)+ `verify_strict_schema_v3`);加 `--allow-archived-replay` flag
  - exit code 5(verify_fail)/ 6(`key_rotation_user_override_required`,仅在 archive/ 路径 + flag)/ 7(`key_file_corrupted`)
  - cmd_append 末尾 stdout 打印 `[LEDGER] line_count=<N> final_hmac=<hex>`(沿 D-LedgerTerminalProof)

```python
# 关键升级片段(完整代码沿现有 cmd_append 风格扩展)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _forgeue_ledger_crypto as crypto

WRAPPER_VERSION = "2.0"

def cmd_append(args):
    """v3 升级:加载 key + 读 prev_hmac + 算 hmac + 写 11 字段 + stdout [LEDGER] 行。

    **并发 append invariant**(round 3 codex F4 inline writeback;沿 design.md R3 + spec
    "Append serial invariant"):本函数**不**实施 cross-platform file lock(`fcntl` /
    `msvcrt`);并发安全由命令模板 `/forgeue:change-apply-{subagent,parallel}` 的主 session
    串行 append 提供(implementer subagent dispatch 之间 parallel,但 append 是主 session
    跑,自然 serialize)。若 ship 后实证非 ForgeUE 工作流外部并发跑 wrapper 触发 race →
    follow-on `enhance-workflow-automation-ledger-append-lock`(P9.7)。
    """
    ledger = Path(args.ledger_path) if args.ledger_path else _default_ledger_path(args.change)
    ledger.parent.mkdir(parents=True, exist_ok=True)

    if args.role not in crypto.VALID_ROLES:
        print(f"[ERROR] invalid role: {args.role}", file=sys.stderr)
        return crypto.EXIT_VERIFY_FAIL

    key, key_id = crypto.load_or_init_key()

    # 读 prev_hmac(若 ledger 已存在且非空)
    prev_hmac = "0" * 64
    if ledger.exists():
        with ledger.open("r", encoding="utf-8") as fh:
            for line in fh:
                line_stripped = line.strip()
                if line_stripped:
                    try:
                        last_record = json.loads(line_stripped)
                        prev_hmac = last_record.get("hmac", "0" * 64)
                    except json.JSONDecodeError:
                        pass

    # 构建 11 字段 record
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
    record["hmac"] = crypto.compute_hmac(key, record)

    # 写 (sort_keys 同 canonical;为了 git diff 可读保持 sort_keys=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()

    # 计算实际 line_count(写后)+ stdout 打印 [LEDGER] 行(D-LedgerTerminalProof)
    line_count = sum(1 for _ in ledger.read_text(encoding="utf-8").splitlines() if _.strip())
    print(f"[LEDGER] line_count={line_count} final_hmac={record['hmac']}")

    return crypto.EXIT_OK


def cmd_verify(args):
    """沿 protocol_version 字段 dispatch + --allow-archived-replay flag 路径限定。"""
    ledger = Path(args.ledger_path) if args.ledger_path else _default_ledger_path(args.change)

    if not ledger.exists():
        print(f"[ERROR] ledger missing: {ledger}", file=sys.stderr)
        return crypto.EXIT_VERIFY_FAIL

    # ... archived replay 路径限定:沿 D-ArchivedReplayPathBoundary
    if args.allow_archived_replay:
        # ledger 路径 must be in archive/
        if "/archive/" not in str(ledger.resolve()).replace("\\", "/"):
            print(f"[ERROR] ledger {ledger} not in archive/ path; --allow-archived-replay rejected", file=sys.stderr)
            return crypto.EXIT_VERIFY_FAIL

    # 解析 ledger 全行
    lines = []
    for line_no, raw in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        if raw.strip():
            try:
                lines.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                print(f"[ERROR] ledger {ledger} line {line_no}: not JSON: {exc}", file=sys.stderr)
                return crypto.EXIT_VERIFY_FAIL

    # ANY v3 信号 dispatch(round 3 codex F1 inline writeback;防 LLM 改所有行 protocol_version 降级 v2 path)
    # v3 信号:任一 v3 字段(hmac / prev_hmac / key_id)出现 OR wrapper_version=="2.0" OR protocol_version=="v3"
    has_v3_signal = any(
        ("hmac" in line) or ("prev_hmac" in line) or ("key_id" in line)
        or (line.get("wrapper_version") == "2.0")
        or (line.get("protocol_version") == "v3")
        for line in lines
    )
    if has_v3_signal:
        # v3 strict schema validation(round 3 codex F2 inline writeback:cmd_verify 不实施 terminal proof,
        # terminal proof 由 finish_gate `_check_ledger_terminal_proof` fence 实施;cmd_verify 仅校
        # strict schema + chain HMAC + key rotation;沿 spec MODIFIED "Dispatch ledger append-only contract"
        # cmd_verify scope boundary)
        # strict schema 内校 protocol_version 必须精确 "v3"(LLM 改 v2/v4/缺失 → schema_violation)
        sstatus, smsg = crypto.verify_strict_schema_v3(lines)
        if sstatus != "ok":
            print(f"[schema_violation] {smsg}", file=sys.stderr)
            return crypto.EXIT_VERIFY_FAIL

        key, _ = crypto.load_or_init_key()
        # archived replay opt-in only via cmd_verify --allow-archived-replay flag (CLI level);
        # finish_gate 走 evidence frontmatter `ledger_archived_replay: true` 路径
        evidence_fm = {"ledger_archived_replay": True} if args.allow_archived_replay else None
        cstatus, cmsg = crypto.verify_chain_v3(key, lines, evidence_fm)
        if cstatus == "key_rotation_user_override_required":
            print(f"[WARN] {cmsg}", file=sys.stderr)
            return crypto.EXIT_KEY_ROTATION_USER_OVERRIDE
        if cstatus != "ok":
            print(f"[{cstatus}] {cmsg}", file=sys.stderr)
            return crypto.EXIT_VERIFY_FAIL
        # NOTE: terminal proof verify_terminal_proof() NOT called here;由 finish_gate 实施
    else:
        # v2 schema-only(沿现有 v2 verify;timestamp 单调 + wrapper_version 非空)
        # ... 沿 archived 现有逻辑
        pass

    return crypto.EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(...)
    sub = parser.add_subparsers(dest="cmd", required=True)
    ap = sub.add_parser("append", ...)
    # ... existing args
    vp = sub.add_parser("verify", ...)
    vp.add_argument("--allow-archived-replay", action="store_true",
                    help="archived replay opt-in (only valid if ledger path in archive/ segment;沿 D-ArchivedReplayPathBoundary)")
    # NOTE: NOT 加 --evidence-line-count / --evidence-final-hmac flag(round 3 codex F2 inline writeback:
    # cmd_verify 不实施 terminal proof;terminal proof 由 finish_gate fence 实施)
    # ... existing args
```

- [ ] Run: `python -m pytest tests/unit/test_dispatch_ledger.py -k 'v3_append' -v`
  Expected: PASS(~5 case)

### micro-P2.2.1 写 cmd_verify v3 测试 ~22 case(round 1+2 codex inline writeback 后)

- [ ] 加测试 case(沿 tasks.md P2.1 列表)到 `tests/unit/test_dispatch_ledger.py`:
  - happy path:`test_v3_verify_pass_on_valid_chain`
  - forge:`test_v3_verify_fail_hand_edit_agent_id` / `test_v3_verify_fail_delete_middle_line` / `test_v3_verify_fail_reorder_lines` / `test_v3_verify_fail_first_line_prev_hmac_nonzero` / `test_v3_verify_fail_mixed_key_id_in_ledger`
  - round 1 F2:`test_v3_verify_fail_key_id_mismatch_active_default_blocker` / `test_v3_verify_warn_key_rotation_with_allow_archived_replay_flag`
  - round 1 F3:`test_v3_verify_fail_tail_truncation` / `test_v3_verify_fail_final_hmac_mismatch` / `test_v3_single_line_ledger_terminal_proof`
  - round 1 F5:9 schema strict case(unknown / missing / negative round / float / bool / oversize agent_id / invalid role / naive dispatched_at / wrong protocol_version)
  - round 2 F1:cmd_verify `--allow-archived-replay` flag + ledger 不在 archive/ 路径 → exit 5
  - key 文件 corrupted:`test_v3_verify_exit_7_key_file_corrupted`

每个 case 4-step:
- [ ] Step 1: 写 fixture(用 cmd_append 真跑生成 v3 ledger,然后 hand-edit 模拟 forge / tamper)
- [ ] Step 2: 跑 cmd_verify 通过 subprocess,assert 退出码 + stderr prefix
- [ ] Step 3: 实施(若需要修 cmd_verify 内部 logic)
- [ ] Step 4: assert pass

### micro-P2.3 跑 P1+P2 测试

- [ ] Run: `python -m pytest tests/unit/test_dispatch_ledger.py -v`
  Expected: 全 P1+P2 v3 case pass(~30 case)

### micro-P2.4 commit P2

- [ ] Run: `git add tools/forgeue_dispatch_ledger.py tools/_forgeue_ledger_crypto.py tests/unit/test_dispatch_ledger.py && git commit -m "feat(forgeue): forgeue_dispatch_ledger.py — v3 schema with HMAC chain (wrapper 2.0)"`

---

## P3 — `tools/forgeue_finish_gate.py` 升级 v3 fence

**对应 tasks.md**:[P3.1 ~ P3.4](../tasks.md#p3--toolsforgeue_finish_gate.py-升级-v3-fence)

### micro-P3.1 写 4 新 fence 失败测试 + dispatch_ledger v3 分支 + round_fix_continuity v3 + audit consistency

- [ ] Read `tools/forgeue_finish_gate.py:_check_dispatch_ledger`(line 2026-2120,v2 现状)+ `_check_round_fix_continuity`(找现有定义)+ `_check_skill_cascade` + `_check_round_fix_continuity` + `_check_task_granularity` + `_check_worktree_path` 等 v1/v2 fence 实施风格
- [ ] 加 v3 fence test 到 `tests/unit/test_forgeue_finish_gate.py`(沿 tasks.md P3.1 列表):

| Test | 对应 fence | scope |
|---|---|---|
| `test_finish_gate_v3_fence_pass_on_valid_v3_ledger` | `_check_dispatch_ledger` v3 | happy path |
| `test_finish_gate_v3_fence_blocker_on_hmac_mismatch` | 同 | hand-edit |
| `test_finish_gate_v3_fence_blocker_on_chain_break` | 同 | 删中间行 |
| `test_finish_gate_v3_fence_blocker_on_key_id_inconsistent` | 同 | 混 key_id |
| `test_finish_gate_v3_fence_blocker_on_key_id_mismatch_default` | 同 + D-KeyRotationHandling | active fail-closed |
| `test_finish_gate_v3_fence_warn_on_key_id_mismatch_with_archived_replay_optin` | 同 + D-ArchivedReplayPathBoundary | archive/ + opt-in |
| `test_finish_gate_v3_fence_blocker_on_archived_replay_optin_active_change` | `_check_archived_replay_path_boundary` | active + opt-in BLOCKER |
| `test_finish_gate_v3_fence_blocker_on_tail_truncation` | `_check_ledger_terminal_proof` | 删尾行 |
| `test_finish_gate_v3_fence_blocker_on_final_hmac_mismatch` | 同 | 改末行 |
| `test_finish_gate_v3_fence_blocker_on_missing_ledger_line_count` | 同 | 缺字段 |
| `test_finish_gate_v3_fence_blocker_on_missing_ledger_final_hmac` | 同 | 缺字段 |
| `test_finish_gate_v3_evidence_with_advisory_blocked` | `_check_ledger_forgery_resistance_consistency` | v3 + advisory |
| `test_finish_gate_v2_evidence_with_cryptographic_blocked` | 同 | v2 + cryptographic |
| `test_finish_gate_v3_evidence_with_cryptographic_pass` | 同 | v3 + cryptographic |
| `test_finish_gate_v2_evidence_with_advisory_pass` | 同 | v2 + advisory |
| `test_finish_gate_v3_fence_blocker_on_schema_unknown_field` | `verify_strict_schema_v3` 内嵌 | unknown field |
| `test_finish_gate_v3_fence_blocker_on_schema_negative_round` | 同 | round: -1 |
| `test_finish_gate_unknown_protocol_v4_blocker` | `_check_runtime_enforcement_protocol_version_validity` | v4 |
| `test_finish_gate_unknown_protocol_typo_blocker` | 同 | typo |
| `test_finish_gate_unknown_protocol_empty_string_blocker` | 同 | empty |
| `test_finish_gate_unknown_protocol_null_blocker` | 同 | null |
| `test_finish_gate_legacy_absent_protocol_pass_through` | 同 | absent legacy |
| `test_finish_gate_protocol_validity_runs_before_dispatch_ledger` | 同 | 顺序约束 |
| `test_finish_gate_v2_evidence_skips_v3_fence` | dispatch matrix | v2 路径 |
| `test_finish_gate_legacy_evidence_skips_all` | dispatch matrix | legacy |
| `test_finish_gate_v3_double_fence_round_fix_continuity_also_fails` | `_check_round_fix_continuity` v3 | 双重守门 |

每个 case 4-step:fixture(写 v3 evidence + ledger)→ 跑 finish_gate(call 内部函数;沿现有 v2 测试 helper)→ assert Blocker.type + error message prefix → 实施修复

### micro-P3.2 实施 4 新 fence + dispatch_ledger v3 + round_fix_continuity v3 + matrix

- [ ] Edit `tools/forgeue_finish_gate.py`:
  - 加模块常量 `_VALID_PROTOCOL_VERSIONS = frozenset({"v1", "v2", "v3"})`
  - 加 helper `_runtime_enforcement_v3_active(frontmatter) -> bool`
  - 加 4 新 fence 函数:
    - `_check_runtime_enforcement_protocol_version_validity(evidence_path, frontmatter, change_root) -> list[str]`
    - `_check_archived_replay_path_boundary(evidence_path, frontmatter, change_root) -> list[str]`
    - `_check_ledger_terminal_proof(evidence_path, frontmatter, change_root) -> list[str]`
    - `_check_ledger_forgery_resistance_consistency(evidence_path, frontmatter, change_root) -> list[str]`
  - 现有 `_check_dispatch_ledger` v3 分支:import `_forgeue_ledger_crypto.verify_chain_v3` + `verify_strict_schema_v3` + `verify_terminal_proof`(if evidence frontmatter 有 ledger_line_count + ledger_final_hmac)+ error message prefix 9 类
  - 现有 `_check_round_fix_continuity` v3 路径:在 v2 cross-check 基础上加 chain verify + terminal proof
  - finish_gate 主入口 fence dispatch order:`_check_runtime_enforcement_protocol_version_validity` 先跑(防 unknown value silent skip)→ 后续 fence 走 protocol-version 分支

- [ ] Run: `python -m pytest tests/unit/test_forgeue_finish_gate.py -k 'v3' -v`
  Expected: PASS(全 ~22 v3 case)

### micro-P3.3 加 forgeue_change_state.py 测试 + 实施(round 3 codex F3 inline writeback;沿 D-ArchivedReplayPathBoundary writeback-check 早期 drift signal)

- [ ] Read `tools/forgeue_change_state.py:--writeback-check` 现有 4 类 named DRIFT 检测逻辑
- [ ] Add test `test_writeback_check_archived_replay_active_drift_via_change_state` to `tests/unit/test_forgeue_change_state.py`(或现有相关测试文件;若不存在 search `test_forgeue_change_state*`):

```python
def test_writeback_check_archived_replay_active_drift_via_change_state(tmp_path):
    """active change evidence 含 ledger_archived_replay: true → forgeue_change_state.py
    --writeback-check exit 5 + DRIFT signal(沿 round 2 codex F1 + round 3 codex F3 inline writeback)。"""
    # fixture: active change(非 archive/)evidence 含 ledger_archived_replay: true
    change_root = tmp_path / "openspec" / "changes" / "test-change"
    change_root.mkdir(parents=True)
    evidence = change_root / "review" / "test.md"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        "---\n"
        "change_id: test-change\n"
        "stage: S5\n"
        "evidence_type: review\n"
        "ledger_archived_replay: true\n"  # ← drift signal in active change
        "---\n"
        "test\n",
        encoding="utf-8",
    )
    # 跑 forgeue_change_state.py --writeback-check
    result = subprocess.run(
        [sys.executable, "tools/forgeue_change_state.py",
         "--change", "test-change", "--writeback-check", "--json"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert result.returncode == 5, f"expected exit 5 (DRIFT detected), got {result.returncode}"
    parsed = json.loads(result.stdout)
    drifts = parsed.get("drifts", [])
    assert any(d.get("type") == "archived_replay_path_violation" for d in drifts), \
        f"expected archived_replay_path_violation drift, got: {drifts}"
```

- [ ] Run: `python -m pytest tests/unit/test_forgeue_change_state.py -k 'archived_replay' -v`
  Expected: FAIL initially(forgeue_change_state.py 还没实施)
- [ ] Edit `tools/forgeue_change_state.py:_writeback_check` 加 `archived_replay_path_violation` 检测分支:
  - 扫 `<change>/**/*.md` 全 evidence 文件 frontmatter
  - 检测 `ledger_archived_replay == True` 字段
  - 校 evidence 文件路径 `Path.resolve()` 是否含 `archive/` segment
  - 不含 → 加 drift entry `{"type": "archived_replay_path_violation", "file": <rel_path>, "detail": "active change evidence 含 ledger_archived_replay: true; 仅 archived (openspec/changes/archive/) evidence 允许此字段"}`
  - 沿现有 DRIFT 4 类 named 模式(`evidence_introduces_decision_not_in_contract` / `evidence_references_missing_anchor` / `evidence_contradicts_contract` / `evidence_exposes_contract_gap`)— 此为第 5 类 drift,加进 _writeback_check 返回的 drifts list
- [ ] Run: `python -m pytest tests/unit/test_forgeue_change_state.py -k 'archived_replay' -v`
  Expected: PASS

### micro-P3.4 跑全套 + commit P3

- [ ] Run: `python -m pytest -q`(包含 P1+P2+P3 + 现有 549 case)
  Expected: 全过(基线 549 + 本 change ~53 → 602;实际数以 pytest collect 为准)
- [ ] Run: `git add tools/forgeue_finish_gate.py tools/forgeue_change_state.py tests/unit/test_forgeue_finish_gate.py tests/unit/test_forgeue_change_state.py && git commit -m "feat(forgeue): forgeue_finish_gate.py + forgeue_change_state.py — v3 fence dispatch + HMAC chain verify + writeback-check archived_replay drift (round 3 codex F3 inline writeback)"`
- [ ] **Round 3 codex F3 inline writeback note**:P3 commit scope 加 `tools/forgeue_change_state.py`(原 plan 漏)+ regression test for writeback-check;沿 D-ArchivedReplayPathBoundary writeback-check 早期 drift signal,与 finish_gate fence 双重守门

---

## P4 — 命令模板 frontmatter 升级 + e2e fixture v3

**对应 tasks.md**:[P4.1 ~ P4.5](../tasks.md#p4--命令模板-frontmatter-升级--e2e-fixture-v3)

### micro-P4.1 升级 change-apply-subagent.md frontmatter

- [ ] Read `.claude/commands/forgeue/change-apply-subagent.md` 现有 frontmatter 模板段(line 87 + line 262 area;沿 grep `dispatch_ledger_path` / `runtime_enforcement_protocol_version`)
- [ ] Edit frontmatter 模板:
  - `runtime_enforcement_protocol_version: v3`(从 v2 升)
  - `ledger_forgery_resistance: cryptographic`(从 advisory 升;沿 D-FrontmatterAuditConsistency)
  - `ledger_line_count: <int>`(必填 v3;LLM 复制 wrapper stdout `[LEDGER]` 行;沿 D-LedgerTerminalProof)
  - `ledger_final_hmac: <64 hex>`(同上)
  - **不写** `ledger_archived_replay`(default 不在;archived replay 时由 user 显式标 true)
- [ ] Edit Step 10a:加"读 wrapper stdout `[LEDGER] line_count=<N> final_hmac=<hex>` + 复制到 evidence frontmatter `ledger_line_count` / `ledger_final_hmac` 字段"明确指令(沿 round 1 codex F3 inline writeback)
- [ ] Edit Step 10a 同时加 **main session serial append invariant**(round 3 codex F4 inline writeback;沿 spec "Append serial invariant" + design R3):
  - 显式声明:"主 session SHALL 顺序调 cmd_append wrapper(每次 Skill(Task) 返回后串行调一次),**不**并发调 wrapper"
  - 沿 archived `executable-enforcement` Step 10a "post-dispatch capture 真实 agent_id" 同款 sequential 实施模式
  - parallel 模式下 implementer subagent dispatch 之间 parallel,但主 session 收集 dispatch return + append wrapper 是 sequential — implementer dispatch parallel 与 append serial 不冲突
- [ ] 加注释 `# v3 协议自 enhance-workflow-automation-ledger-binding change 起;line_count + final_hmac 复制自 wrapper stdout`

### micro-P4.2 升级 change-apply-parallel.md(同 P4.1)

- [ ] Read + Edit `.claude/commands/forgeue/change-apply-parallel.md`(同 P4.1 frontmatter + Step 10a)

### micro-P4.3 写 e2e v3 平行 case + 4 negative

- [ ] Read `tests/integration/test_v2_e2e_synthetic_change.py` 现有 v2 case(fixture 模式 + finish_gate 调用)
- [ ] 加 v3 e2e case 5 个(沿 tasks.md P4.3 列表):
  - `test_v3_e2e_cryptographic_synthetic_change`(monkey-patched `Path.home()` + fixture v3 evidence + v3 ledger 真跑生成 + `[LEDGER]` stdout 模拟 LLM 复制 + finish_gate 跑通)
  - `test_v3_e2e_negative_hmac_mismatch`(tamper 中间行 → BLOCKER)
  - `test_v3_e2e_negative_tail_truncation`(删尾行 + evidence frontmatter `ledger_line_count` 未跟改 → BLOCKER)
  - `test_v3_e2e_negative_key_id_mismatch_default_fail_closed`(切 key + 无 `--allow-archived-replay` → BLOCKER)
  - `test_v3_e2e_negative_audit_inconsistency`(v3 evidence + `ledger_forgery_resistance: advisory` → BLOCKER)

### micro-P4.4 跑全套 + commit P4

- [ ] Run: `python -m pytest -q`(全 549 + ~57 → 606 测试;实际以 collect 为准)
- [ ] Run: `git add .claude/commands/forgeue/change-apply-subagent.md .claude/commands/forgeue/change-apply-parallel.md tests/integration/test_v2_e2e_synthetic_change.py && git commit -m "feat(forgeue): change-apply-{subagent,parallel} v3 frontmatter + e2e fixture (round 1+2 codex inline writeback)"`

---

## P5 — 验证 hook + codex `/codex:review --base main`

**对应 tasks.md**:[P5.1 ~ P5.5](../tasks.md#p5--验证-hook--codex-codex-review---base-main)

### micro-P5.1 跑 `/forgeue:change-verify` Level 0/1/2

- [ ] L0:`openspec validate --strict enhance-workflow-automation-ledger-binding` → exit 0
- [ ] L1:`python -m pytest -q tests/unit/test_dispatch_ledger.py tests/unit/test_forgeue_finish_gate.py tests/integration/test_v2_e2e_synthetic_change.py` → 全过
- [ ] L2:`python tools/forgeue_dispatch_ledger.py append --change <id> --agent-id <fake_18_hex> --round 1 --role implementer --task-subject-hash sha256:<...>`(自 fixture invoke;新建 v3 schema 行 + 校 hmac 字段)+ `python tools/forgeue_dispatch_ledger.py verify --change <id>`(verify 通过)
- [ ] 落 `verification/verify_report.md`(12-key audit frontmatter)

### micro-P5.2 跑 codex `/codex:review --base main`

- [ ] Skill(codex:review)`--base main`(本 change diff 全 review;background 跑;不是 adversarial)
- [ ] 等 result + 读完整 output

### micro-P5.3 finding 落 verification/verification_cross_check.md

- [ ] Write `review/codex_verification_review.md`(verbatim)+ `verification/verification_cross_check.md`(`## A` Claude 立场 + `## B/C/D` Resolution + 独立 file:line verify);disputed_open == 0

### micro-P5.4 inline writeback finding(若有)+ commit

- [ ] 若 codex `/codex:review` raise blocker → inline writeback(改代码 / 测试 / docs)+ commit
- [ ] 若无 blocker → P5 closed,commit verification 文件

---

## P6 — `/forgeue:change-doc-sync` Documentation Sync Gate

**对应 tasks.md**:[P6.1 ~ P6.5](../tasks.md#p6--forgeuechange-doc-sync-documentation-sync-gate)

### micro-P6.1 跑 forgeue_doc_sync_check + forgeue_enum_cross_ref_check

- [ ] Run: `python tools/forgeue_doc_sync_check.py --change enhance-workflow-automation-ledger-binding`
  Expected: 输出 [REQUIRED] / [OPTIONAL] / [SKIP] / [DRIFT] 标记
- [ ] Run: `python tools/forgeue_enum_cross_ref_check.py`
  Expected: exit 0 / 2(若有 drift 标 advisory)

### micro-P6.2 应用 [REQUIRED] doc 同步

- [ ] Edit `docs/ai_workflow/forgeue_integrated_ai_workflow.md`:
  - §C protocol matrix 扩到 4 档(legacy / v1 / v2 / v3 + unknown BLOCKER)
  - 新加 §C.10 "Cryptographic Ledger Binding"(D-decision 摘要 + key 文件 lifecycle + verify 流程 + threat model 边界 + archived replay 路径限定)
- [ ] Edit `CLAUDE.md`:Runtime enforcement frontmatter 字段段加 v3 说明 + 4 档 dispatch matrix + 工具清单 stdlib helper(`_forgeue_ledger_crypto.py`)
- [ ] Edit `CHANGELOG.md`:[Unreleased] 加本 change entry
- [ ] Edit `AGENTS.md`:加 v3 protocol 摘要

### micro-P6.3 commit P6

- [ ] Run: `git add docs/ai_workflow/forgeue_integrated_ai_workflow.md CLAUDE.md CHANGELOG.md AGENTS.md && git commit -m "docs(forgeue): v3 cryptographic ledger binding (forgeue_integrated_ai_workflow §C.10 + CLAUDE.md)"`

---

## P7 — Final review + Finish gate

**对应 tasks.md**:[P7.1 ~ P7.3](../tasks.md#p7--final-review--finish-gate)

### micro-P7.1 跑 /forgeue:change-review

- [ ] Skill(superpowers:requesting-code-review)retrospective(主 session;沿 forgeue:change-review)
- [ ] Skill(codex:adversarial-review)`--background` mixed scope(design + spec + impl 全 review)
- [ ] 等 result + 读完整 output
- [ ] Write `review/superpowers_review.md` + `review/codex_adversarial_review.md`(round 3)+ `review/review_cross_check.md`
- [ ] blocker 回写 design.md / specs / tasks.md(若有);非 blocker 列 follow-on 候选

### micro-P7.2 跑 /forgeue:change-finish

- [ ] Run: `python tools/forgeue_finish_gate.py --change enhance-workflow-automation-ledger-binding`
  Expected: exit 0 — 12-key frontmatter 全检 + writeback 真实性 + cross-check disputed_open == 0 + tasks unchecked == 0 + openspec validate --strict + 4 v1 + 6 v2 fence pass(本 change 自身 evidence 沿 v2 self-dogfood)
- [ ] 落 `verification/finish_gate_report.md`(12-key audit frontmatter)
- [ ] commit `feat(forgeue): ledger-binding change finalize`(若 P5.5 / P7.1 触发额外 inline writeback)

---

## P8 — Archive change(user-required)

**对应 tasks.md**:[P8.1 ~ P8.4](../tasks.md#p8--archive-change)

### micro-P8.1 user 授权后 archive

- [ ] **Fence #1 不可逆,user 显式授权才执行**(沿 ADR-010 + memory `feedback_push_requires_per_commit_auth.md`)
- [ ] Run: `openspec archive enhance-workflow-automation-ledger-binding`
  Expected: archived 路径 `openspec/changes/archive/2026-MM-DD-enhance-workflow-automation-ledger-binding/`
- [ ] Run: `git add openspec/ && git commit -m "feat(forgeue): ship enhance-workflow-automation-ledger-binding (squash merge)"`

### micro-P8.2 push(user 单独请示)

- [ ] **Fence #1 不可逆 push,user 单独请示**(沿 memory `feedback_push_requires_per_commit_auth.md`,前序 push 授权不延续)
- [ ] Run: `git push`(待 user 授权)

---

## P9 — MEMORY.md update + follow-on tracking(后置可选)

**对应 tasks.md**:[P9.1 ~ P9.6](../tasks.md#p9--memory.md-update--follow-on-tracking后置可选)

### micro-P9.1 MEMORY.md update

- [ ] Write `~/.claude/projects/.../memory/project_ledger_binding_change.md`(沿 forgeue auto memory 协议;15 D-decision + threat model 边界 + commit SHA + follow-on tracking)
- [ ] Edit `MEMORY.md` index entry

### micro-P9.2-P9.6 follow-on tracking 状态确认

- [ ] P9.2(`enhance-workflow-automation-skill-tool-binding`):F2 wrapper-bound dispatch deferred;触发条件:本 change ship 后实证 F3 cryptographic 仍不足以挡 controller drift
- [ ] P9.3(`enhance-workflow-automation-os-keystore`):OS-level secret store;触发条件:LLM 主动恶意 forge 实际发生
- [ ] P9.4 P12.7 单独评估:本 change ship 后实证下一个 active change 用 v3 + SKIP stub pattern 是否仍误通过
- [ ] P9.4 P12.8(`v2-fence-hardening`):**已 superseded**(本 change ship 后正式 cancel)
- [ ] P9.5 已纳入 P9.3
- [ ] P9.6(`archived-replay-audit`):**已 RETIRED**(round 2 codex F1 inline writeback 已实施)
