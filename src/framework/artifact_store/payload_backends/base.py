"""Base contract for payload backends (§D.2)."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from framework.core.artifact import PayloadRef
from framework.core.enums import PayloadKind


class PayloadTooLarge(Exception):
    """Raised when payload size exceeds backend cap."""


@dataclass(frozen=True)
class WriteResult:
    """Backend 写入结果:PayloadRef + 已验证落盘内容 hash。"""

    ref: PayloadRef
    content_hash: str


# D10 D-NullValueAmbiguity 私有 sentinel — 用 identity 区分 "未传" vs "显式 None"
# (`value=None` 是合法 inline JSON null payload,既有 13 处 inline 调用契约保留)
_MISSING: Any = object()


class PayloadBackend(ABC):
    """Backend responsible for writing & reading payload bytes/values."""

    kind: PayloadKind

    @abstractmethod
    def write(
        self,
        value: Any = _MISSING,
        *,
        run_id: str,
        artifact_id: str,
        suffix: str = "",
        source_path: str | os.PathLike | None = None,
    ) -> WriteResult:
        """Persist *value* (or zero-copy from *source_path* on FileBackend) and
        return a WriteResult carrying PayloadRef + content hash.

        FileBackend and BlobBackend honor *source_path*; InlineBackend raises.
        `value=_MISSING` is the unset sentinel; `value=None` is a legitimate
        inline JSON null payload (different identity, D10).
        """

    @abstractmethod
    def read(self, ref: PayloadRef) -> Any:
        """Return the original payload value for *ref*."""

    @abstractmethod
    def exists(self, ref: PayloadRef) -> bool: ...

    @abstractmethod
    def absolute_path(self, ref: PayloadRef) -> Path:
        """Return the on-disk absolute path for *ref*.

        Only FileBackend has a meaningful local-path implementation;
        InlineBackend and BlobBackend SHALL raise ValueError.
        """


class PayloadBackendRegistry:
    """Dispatch backends by PayloadRef.kind."""

    def __init__(self) -> None:
        self._backends: dict[PayloadKind, PayloadBackend] = {}

    def register(self, backend: PayloadBackend) -> None:
        self._backends[backend.kind] = backend

    def get(self, kind: PayloadKind) -> PayloadBackend:
        if kind not in self._backends:
            raise KeyError(f"No backend registered for kind={kind}")
        return self._backends[kind]

    def write(self, kind: PayloadKind, value: Any = _MISSING, **kwargs: Any) -> WriteResult:
        return self.get(kind).write(value, **kwargs)

    def read(self, ref: PayloadRef) -> Any:
        return self.get(ref.kind).read(ref)

    def exists(self, ref: PayloadRef) -> bool:
        return self.get(ref.kind).exists(ref)


_default_registry: PayloadBackendRegistry | None = None


def get_backend_registry(*, artifact_root: str | None = None) -> PayloadBackendRegistry:
    """Return the process-wide default backend registry.

    On first call, registers Inline + File + Blob backends. Pass *artifact_root*
    to override the default `./artifacts` directory used by FileBackend.
    """
    global _default_registry
    if _default_registry is None or artifact_root is not None:
        from framework.artifact_store.payload_backends.inline_backend import InlineBackend
        from framework.artifact_store.payload_backends.file_backend import FileBackend
        from framework.artifact_store.payload_backends.blob_backend import BlobBackend

        reg = PayloadBackendRegistry()
        reg.register(InlineBackend())
        reg.register(FileBackend(root=artifact_root or "artifacts"))
        reg.register(BlobBackend())
        _default_registry = reg
    return _default_registry
