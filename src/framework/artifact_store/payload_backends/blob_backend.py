"""Blob payload backend — injectable object-store client MVP (§D.2)."""
from __future__ import annotations

import json
import os
import stat as _stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from framework.artifact_store.hashing import hash_path, hash_payload
from framework.artifact_store.payload_backends.base import (
    PayloadBackend,
    WriteResult,
    _MISSING,
)
from framework.core.artifact import PayloadRef
from framework.core.enums import PayloadKind


@dataclass
class BlobObject:
    """内存对象存储记录:bytes + 调试 metadata。"""

    data: bytes
    metadata: dict[str, str]


class BlobClient(Protocol):
    """BlobBackend 依赖的最小对象存储协议。

    真实 S3 / MinIO / Azure adapter 只要实现这个协议即可接入,框架不硬依赖
    第三方 SDK。
    """

    def upload_bytes(
        self, key: str, data: bytes, *, metadata: dict[str, str]
    ) -> None: ...

    def upload_path(
        self, key: str, source_path: str | os.PathLike, *, metadata: dict[str, str]
    ) -> None: ...

    def read_bytes(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


class InMemoryBlobClient:
    """测试 / MVP 默认对象存储 client,无网络与第三方依赖。"""

    def __init__(self) -> None:
        self._objects: dict[str, BlobObject] = {}

    def upload_bytes(
        self, key: str, data: bytes, *, metadata: dict[str, str]
    ) -> None:
        self._objects[key] = BlobObject(data=bytes(data), metadata=dict(metadata))

    def upload_path(
        self, key: str, source_path: str | os.PathLike, *, metadata: dict[str, str]
    ) -> None:
        data = bytearray()
        with Path(source_path).open("rb") as f:
            while True:
                chunk = f.read(8 * 1024 * 1024)
                if not chunk:
                    break
                data.extend(chunk)
        self.upload_bytes(key, bytes(data), metadata=metadata)

    def read_bytes(self, key: str) -> bytes:
        return self._objects[key].data

    def exists(self, key: str) -> bool:
        return key in self._objects


def _coerce_bytes(value: Any) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return json.dumps(value, ensure_ascii=False, default=str, indent=2).encode("utf-8")


class BlobBackend(PayloadBackend):
    """Object-store-backed payload backend.

    默认使用 InMemoryBlobClient,让本地测试和离线 run 可确定性执行。生产侧
    S3 / MinIO / Azure Blob adapter 可通过 client 注入,不改变 Repository API。
    """

    kind = PayloadKind.blob

    def __init__(
        self,
        *,
        bucket: str = "forgeue-artifacts",
        client: BlobClient | None = None,
    ) -> None:
        self._bucket = bucket.strip("/")
        self._client = client or InMemoryBlobClient()

    def write(
        self,
        value: Any = _MISSING,
        *,
        run_id: str,
        artifact_id: str,
        suffix: str = "",
        source_path: str | os.PathLike | None = None,
    ) -> WriteResult:
        # 与 FileBackend 保持同一输入互斥契约。
        if value is not _MISSING and source_path is not None:
            raise ValueError(
                "BlobBackend.write: value and source_path are mutually exclusive"
            )
        if value is _MISSING and source_path is None:
            raise ValueError(
                "BlobBackend.write: requires either value or source_path"
            )

        key = self._key(run_id=run_id, artifact_id=artifact_id, suffix=suffix)
        if source_path is not None:
            src = Path(source_path)
            src_stat = src.stat()
            if not _stat.S_ISREG(src_stat.st_mode):
                raise ValueError(
                    f"source_path must be a regular file, "
                    f"got mode 0o{src_stat.st_mode:o} ({src})"
                )
            content_hash = hash_path(src)
            self._client.upload_path(
                key,
                src,
                metadata={"content_hash": content_hash, "source": "source_path"},
            )
            size_bytes = src_stat.st_size
        else:
            data = _coerce_bytes(value)
            content_hash = hash_payload(value)
            self._client.upload_bytes(
                key,
                data,
                metadata={"content_hash": content_hash, "source": "value"},
            )
            size_bytes = len(data)

        return WriteResult(
            ref=PayloadRef(
                kind=PayloadKind.blob,
                blob_key=key,
                size_bytes=size_bytes,
            ),
            content_hash=content_hash,
        )

    def read(self, ref: PayloadRef) -> Any:
        if ref.blob_key is None:
            raise ValueError("PayloadRef.blob_key is None")
        return self._client.read_bytes(ref.blob_key)

    def exists(self, ref: PayloadRef) -> bool:
        if ref.blob_key is None:
            return False
        return self._client.exists(ref.blob_key)

    def absolute_path(self, ref: PayloadRef) -> Path:
        """Blob payload 没有本地绝对路径,调用方应走 read/exists。"""
        raise ValueError("blob payload has no local path")

    def _key(self, *, run_id: str, artifact_id: str, suffix: str) -> str:
        return f"{self._bucket}/{run_id}/{artifact_id}{suffix}"
