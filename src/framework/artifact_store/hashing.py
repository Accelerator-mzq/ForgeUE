"""Content hashing helpers for Artifact + Checkpoint (§B.6, F0-6)."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
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


async def ahash_path(
    path: str | os.PathLike,
    *,
    chunk_size: int = 8 * 1024 * 1024,
) -> str:
    """hash_path 的 asyncio 变体,用于 executor 链路避免阻塞 event loop。"""
    return await asyncio.to_thread(hash_path, path, chunk_size=chunk_size)


def hash_path(
    path: str | os.PathLike,
    *,
    chunk_size: int = 8 * 1024 * 1024,
) -> str:
    """文件流式 SHA-256,等价于 hash_payload(Path(path).read_bytes()) 但 RSS bounded。

    Output equivalent to `hash_payload(Path(path).read_bytes())` but with
    bounded RSS (chunk_size + small overhead).

    R4-F4:chunk_size <= 0 raises ValueError —— `f.read(0)` 会返回空 bytes 让
    非空文件得到 empty file hash(silent corruption)。
    """
    if chunk_size <= 0:
        raise ValueError(
            f"hash_path chunk_size must be positive, got {chunk_size}"
        )
    h = hashlib.sha256()
    p = Path(path)
    with p.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
