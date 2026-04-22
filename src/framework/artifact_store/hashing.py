"""Content hashing helpers for Artifact + Checkpoint (§B.6, F0-6)."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonicalize(value: Any) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")


def hash_payload(value: Any) -> str:
    """Stable SHA-256 hex for arbitrary payload value."""
    return hashlib.sha256(_canonicalize(value)).hexdigest()


def hash_inputs(*parts: Any) -> str:
    """Composite hash over multiple parts for Checkpoint input_hash."""
    h = hashlib.sha256()
    for p in parts:
        h.update(_canonicalize(p))
        h.update(b"\x1f")  # separator
    return h.hexdigest()
