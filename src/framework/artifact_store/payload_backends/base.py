"""Base contract for payload backends (§D.2)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from framework.core.artifact import PayloadRef
from framework.core.enums import PayloadKind


class PayloadTooLarge(Exception):
    """Raised when payload size exceeds backend cap."""


class PayloadBackend(ABC):
    """Backend responsible for writing & reading payload bytes/values."""

    kind: PayloadKind

    @abstractmethod
    def write(self, value: Any, *, run_id: str, artifact_id: str, suffix: str = "") -> PayloadRef:
        """Persist *value* and return a PayloadRef that can later be read back."""

    @abstractmethod
    def read(self, ref: PayloadRef) -> Any:
        """Return the original payload value for *ref*."""

    @abstractmethod
    def exists(self, ref: PayloadRef) -> bool: ...


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

    def write(self, kind: PayloadKind, value: Any, **kwargs: Any) -> PayloadRef:
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
