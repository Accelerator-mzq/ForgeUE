"""File payload backend — writes to local Artifact Store root (§D.2).

Layout: <root>/<run_id>/<artifact_id><suffix>
Cap: 500 MB per file.
"""
from __future__ import annotations

import json
import os
import shutil
import stat as _stat
import uuid
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
        rel = f"{run_id}/{artifact_id}{suffix}"
        abs_path = self._resolve(rel)
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        # R6-F3 D-BackendMutexGuard:backend 层守二选一,作为 repo.put 次级 fence
        if value is not _MISSING and source_path is not None:
            raise ValueError(
                "FileBackend.write: value and source_path are mutually exclusive"
            )
        if value is _MISSING and source_path is None:
            raise ValueError(
                "FileBackend.write: requires either value or source_path"
            )

        if source_path is not None:
            # Zero-copy 分支(D1 + D4 D-Atomic + R4-F3 regular file guard)
            src = Path(source_path)
            src_stat = src.stat()  # 不存在则 raise FileNotFoundError
            # R4-F3 D-RegularFileGuard:拒目录 / FIFO / device / socket
            if not _stat.S_ISREG(src_stat.st_mode):
                raise ValueError(
                    f"source_path must be a regular file, "
                    f"got mode 0o{src_stat.st_mode:o} ({src})"
                )
            # Pre-copy fail-fast cap 校验(避免浪费 IO)
            if src_stat.st_size > FILE_MAX_BYTES:
                raise PayloadTooLarge(
                    f"file payload {src_stat.st_size} bytes exceeds cap {FILE_MAX_BYTES}"
                )
            # D4 D-Atomic:tmp → chmod → stat → os.replace(永不直接写 abs_path)
            tmp_dest = abs_path.with_name(
                f"{abs_path.name}.part.{os.getpid()}.{uuid.uuid4().hex[:8]}"
            )
            try:
                # R5-F4 D-PermissionNormalize:copyfile(不复制 metadata)+ 显式
                # chmod 归一化权限,避免 source 只读位污染 artifact store
                shutil.copyfile(src, tmp_dest)
                os.chmod(tmp_dest, 0o644)
                # D9 D-HashSource-vs-Dest:size_bytes 取 dest stat,与落盘数据同源
                dest_size = tmp_dest.stat().st_size
                # Post-copy cap recheck(竞态窗口:source 在 stat 与 copy 之间被扩写)
                if dest_size > FILE_MAX_BYTES:
                    raise PayloadTooLarge(
                        f"file payload {dest_size} bytes (post-copy) exceeds cap {FILE_MAX_BYTES}"
                    )
                # 同盘 atomic replace;tmp 被替换为 abs_path
                os.replace(tmp_dest, abs_path)
            except BaseException:
                # R4-F1 D-Atomic:任何异常清理 tmp,绝不触碰 abs_path
                tmp_dest.unlink(missing_ok=True)
                raise
            return PayloadRef(
                kind=PayloadKind.file,
                file_path=rel,
                size_bytes=dest_size,
            )

        # Value 分支(既有路径,完全保留)
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
