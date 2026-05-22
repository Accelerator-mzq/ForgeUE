"""PayloadRef three-state backends (§D.2).

MVP implements inline + file + blob. Blob uses an injectable object-store
client protocol with an in-memory default client.
"""
from __future__ import annotations

from framework.artifact_store.payload_backends.base import (
    PayloadBackend,
    PayloadBackendRegistry,
    PayloadTooLarge,
    WriteResult,
    get_backend_registry,
)
from framework.artifact_store.payload_backends.inline_backend import InlineBackend
from framework.artifact_store.payload_backends.file_backend import FileBackend
from framework.artifact_store.payload_backends.blob_backend import (
    BlobBackend,
    BlobClient,
    InMemoryBlobClient,
)

__all__ = [
    "PayloadBackend",
    "PayloadBackendRegistry",
    "PayloadTooLarge",
    "WriteResult",
    "InlineBackend",
    "FileBackend",
    "BlobBackend",
    "BlobClient",
    "InMemoryBlobClient",
    "get_backend_registry",
]
