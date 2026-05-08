"""UE-side Evidence append-only writer (§F4-5).

Mirrors `framework/ue_bridge/evidence.py` but imports nothing from the
framework package — UE Python runs in its own environment without the
framework installed. Reads/writes the same evidence.json file that the
export step seeded on disk.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path


def new_evidence_id(prefix: str = "ev") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def append(evidence_path: str | Path, record: dict) -> None:
    p = Path(evidence_path)
    existing: list[dict] = []
    if p.is_file():
        existing = json.loads(p.read_text(encoding="utf-8"))
    existing.append(record)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def make_record(
    *, op_id: str, kind: str, status: str,
    source_uri: str | None = None, target_object_path: str | None = None,
    log_ref: str | None = None, error: str | None = None,
    skip_reason: str | None = None,
) -> dict:
    """构造一条 Evidence 记录 dict。

    OpenSpec change fix-export-d12-and-skipped-evidence-filter Phase B.1:
    新增 optional `skip_reason` kwarg(双侧统一协议)。
    - framework `ExportExecutor` 写 `skip_reason="permission_denied"` 表示
      PermissionPolicy 拒绝;
    - UE-side `run_import.py` 写 `skip_reason="no_handler"` 表示无对应
      handler dispatch(unknown op kind)。
    legacy 调用(不传 kwarg)时字段 = None,与既有 dict 风格一致(其他
    optional 字段如 source_uri / target_object_path / log_ref / error 也都
    None default)。
    """
    return {
        "evidence_item_id": new_evidence_id(),
        "op_id": op_id,
        "kind": kind,
        "status": status,
        "source_uri": source_uri,
        "target_object_path": target_object_path,
        "log_ref": log_ref,
        "error": error,
        "skip_reason": skip_reason,
    }
