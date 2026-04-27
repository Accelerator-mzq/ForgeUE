"""Lazy public API surface for the framework.artifact_store package.

PEP 562 __getattr__ + __dir__ lazy export: top-level package import does NOT
transitively load repository / payload_backends / lineage / variant_tracker
into sys.modules. Read-only consumers (framework.comparison.loader / cli)
get a clean import surface without paying the cost of write-side machinery.

Eager: hash_inputs / hash_payload (zero framework deps, used by hash recompute).
Lazy: ArtifactRepository, PayloadBackend / PayloadBackendRegistry / PayloadTooLarge /
get_backend_registry, LineageIndex, VariantTracker.

See openspec/specs/artifact-contract/spec.md "Package import surface is lazy-load
by default" for the behavioral contract.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from framework.artifact_store.hashing import hash_inputs, hash_payload

if TYPE_CHECKING:
    from framework.artifact_store.lineage import LineageIndex
    from framework.artifact_store.payload_backends import (
        PayloadBackend,
        PayloadBackendRegistry,
        PayloadTooLarge,
        get_backend_registry,
    )
    from framework.artifact_store.repository import ArtifactRepository
    from framework.artifact_store.variant_tracker import VariantTracker

_LAZY_REPOSITORY_NAMES = frozenset({"ArtifactRepository"})
_LAZY_PAYLOAD_BACKEND_NAMES = frozenset(
    {
        "PayloadBackend",
        "PayloadBackendRegistry",
        "PayloadTooLarge",
        "get_backend_registry",
    }
)
_LAZY_LINEAGE_NAMES = frozenset({"LineageIndex"})
_LAZY_VARIANT_NAMES = frozenset({"VariantTracker"})


def __getattr__(name: str) -> Any:
    if name in _LAZY_REPOSITORY_NAMES:
        from framework.artifact_store import repository

        value = getattr(repository, name)
        globals()[name] = value
        return value
    if name in _LAZY_PAYLOAD_BACKEND_NAMES:
        from framework.artifact_store import payload_backends

        value = getattr(payload_backends, name)
        globals()[name] = value
        return value
    if name in _LAZY_LINEAGE_NAMES:
        from framework.artifact_store import lineage

        value = getattr(lineage, name)
        globals()[name] = value
        return value
    if name in _LAZY_VARIANT_NAMES:
        from framework.artifact_store import variant_tracker

        value = getattr(variant_tracker, name)
        globals()[name] = value
        return value
    raise AttributeError(
        f"module 'framework.artifact_store' has no attribute {name!r}"
    )


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(globals()))


__all__ = [
    "ArtifactRepository",
    "LineageIndex",
    "PayloadBackend",
    "PayloadBackendRegistry",
    "PayloadTooLarge",
    "VariantTracker",
    "get_backend_registry",
    "hash_inputs",
    "hash_payload",
]
