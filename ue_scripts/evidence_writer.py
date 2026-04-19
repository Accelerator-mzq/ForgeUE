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
) -> dict:
    return {
        "evidence_item_id": new_evidence_id(),
        "op_id": op_id,
        "kind": kind,
        "status": status,
        "source_uri": source_uri,
        "target_object_path": target_object_path,
        "log_ref": log_ref,
        "error": error,
    }
