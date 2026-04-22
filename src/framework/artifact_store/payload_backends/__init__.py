"""PayloadRef three-state backends (§D.2).

MVP implements inline + file. Blob is stubbed and raises NotImplementedError.
"""
from __future__ import annotations

from framework.artifact_store.payload_backends.base import (
    PayloadBackend,
    PayloadBackendRegistry,
    PayloadTooLarge,
    get_backend_registry,
)
from framework.artifact_store.payload_backends.inline_backend import InlineBackend
from framework.artifact_store.payload_backends.file_backend import FileBackend
from framework.artifact_store.payload_backends.blob_backend import BlobBackend

__all__ = [
    "PayloadBackend",
    "PayloadBackendRegistry",
    "PayloadTooLarge",
    "InlineBackend",
    "FileBackend",
    "BlobBackend",
    "get_backend_registry",
]
