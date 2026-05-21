"""Blob backend — interface reserved (§D.2). Not implemented in MVP."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from framework.artifact_store.payload_backends.base import PayloadBackend
from framework.core.artifact import PayloadRef
from framework.core.enums import PayloadKind


class BlobBackend(PayloadBackend):
    """Stub for object-store-backed blobs (S3/MinIO). Deferred to G stage."""

    kind = PayloadKind.blob

    def write(self, value: Any, *, run_id: str, artifact_id: str, suffix: str = "") -> PayloadRef:
        raise NotImplementedError("BlobBackend.write is deferred (post-MVP)")

    def read(self, ref: PayloadRef) -> Any:
        raise NotImplementedError("BlobBackend.read is deferred (post-MVP)")

    def exists(self, ref: PayloadRef) -> bool:
        raise NotImplementedError("BlobBackend.exists is deferred (post-MVP)")

    def absolute_path(self, ref: PayloadRef) -> Path:
        """Blob backend 路径解析延后,stub 一致语义 raise NotImplementedError。"""
        raise NotImplementedError("BlobBackend.absolute_path is deferred (post-MVP)")
