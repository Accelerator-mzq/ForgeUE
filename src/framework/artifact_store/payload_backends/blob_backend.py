"""Blob backend — interface reserved (§D.2). Not implemented in MVP."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from framework.artifact_store.payload_backends.base import (
    PayloadBackend,
    WriteResult,
    _MISSING,
)
from framework.core.artifact import PayloadRef
from framework.core.enums import PayloadKind


class BlobBackend(PayloadBackend):
    """Stub for object-store-backed blobs (S3/MinIO). Deferred to G stage."""

    kind = PayloadKind.blob

    def write(
        self,
        value: Any = _MISSING,
        *,
        run_id: str,
        artifact_id: str,
        suffix: str = "",
        source_path: str | os.PathLike | None = None,
    ) -> WriteResult:
        # D10 守门:BlobBackend 不支持 source_path 零拷贝路径
        if source_path is not None:
            raise ValueError(
                "source_path is only supported by FileBackend, not BlobBackend"
            )
        # R1-F1 spec 对等守门:value 缺失 + source_path=None → ValueError(与 InlineBackend 一致)
        if value is _MISSING and source_path is None:
            raise ValueError(
                "BlobBackend.write requires value or source_path (got _MISSING + None)"
            )
        raise NotImplementedError("BlobBackend.write is deferred (post-MVP)")

    def read(self, ref: PayloadRef) -> Any:
        raise NotImplementedError("BlobBackend.read is deferred (post-MVP)")

    def exists(self, ref: PayloadRef) -> bool:
        raise NotImplementedError("BlobBackend.exists is deferred (post-MVP)")

    def absolute_path(self, ref: PayloadRef) -> Path:
        """Blob backend 路径解析延后,stub 一致语义 raise NotImplementedError。"""
        raise NotImplementedError("BlobBackend.absolute_path is deferred (post-MVP)")
