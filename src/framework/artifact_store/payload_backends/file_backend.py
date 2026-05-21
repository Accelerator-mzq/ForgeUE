"""File payload backend — writes to local Artifact Store root (§D.2).

Layout: <root>/<run_id>/<artifact_id><suffix>
Cap: 500 MB per file.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from framework.artifact_store.payload_backends.base import PayloadBackend, PayloadTooLarge, _MISSING
from framework.core.artifact import PayloadRef
from framework.core.enums import PayloadKind

FILE_MAX_BYTES = 500 * 1024 * 1024


def _coerce_bytes(value: Any, suffix: str) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    # structured value → JSON
    return json.dumps(value, ensure_ascii=False, default=str, indent=2).encode("utf-8")


class FileBackend(PayloadBackend):
    kind = PayloadKind.file

    def __init__(self, root: str) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, rel_path: str) -> Path:
        p = (self._root / rel_path).resolve()
        root_resolved = self._root.resolve()
        # Protect against path traversal
        if os.path.commonpath([str(p), str(root_resolved)]) != str(root_resolved):
            raise ValueError(f"file_path {rel_path} escapes artifact root")
        return p

    def write(
        self,
        value: Any = _MISSING,
        *,
        run_id: str,
        artifact_id: str,
        suffix: str = "",
        source_path: str | os.PathLike | None = None,
    ) -> PayloadRef:
        # Task 3:zero-copy 分支留 Task 4 实装;source_path 非空暂 raise
        if source_path is not None:
            raise NotImplementedError(
                "FileBackend zero-copy branch is implemented in TBD-012 Task 4"
            )
        if value is _MISSING:
            raise ValueError("FileBackend.write requires value or source_path")

        # 既有 value 路径完全保留
        rel = f"{run_id}/{artifact_id}{suffix}"
        abs_path = self._resolve(rel)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        data = _coerce_bytes(value, suffix)
        if len(data) > FILE_MAX_BYTES:
            raise PayloadTooLarge(
                f"file payload {len(data)} bytes exceeds cap {FILE_MAX_BYTES}"
            )
        abs_path.write_bytes(data)
        return PayloadRef(
            kind=PayloadKind.file,
            file_path=rel,
            size_bytes=len(data),
        )

    def read(self, ref: PayloadRef) -> bytes:
        if ref.file_path is None:
            raise ValueError("PayloadRef.file_path is None")
        return self._resolve(ref.file_path).read_bytes()

    def exists(self, ref: PayloadRef) -> bool:
        if ref.file_path is None:
            return False
        return self._resolve(ref.file_path).is_file()

    def absolute_path(self, ref: PayloadRef) -> Path:
        """Return resolved absolute Path;复用 _resolve traversal guard。"""
        if ref.file_path is None:
            raise ValueError("PayloadRef.file_path is None")
        return self._resolve(ref.file_path)
