"""Artifact repository — single entry point for writing and reading Artifacts (§F0-3).

Combines:
- PayloadRef backends (inline/file/blob)
- Lineage index
- Variant tracker
- Content hashing

MVP: in-process dict-backed store. Persistence is via file payload backend.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Iterator

from framework.artifact_store.hashing import hash_payload
from framework.artifact_store.lineage import LineageIndex
from framework.artifact_store.payload_backends.base import (
    PayloadBackendRegistry,
    get_backend_registry,
)
from framework.artifact_store.variant_tracker import VariantTracker
from framework.core.artifact import (
    Artifact,
    ArtifactType,
    Lineage,
    PayloadRef,
    ProducerRef,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, PayloadKind


class ArtifactRepository:
    def __init__(
        self,
        *,
        backend_registry: PayloadBackendRegistry | None = None,
        artifact_root: str | None = None,
    ) -> None:
        self._registry = backend_registry or get_backend_registry(artifact_root=artifact_root)
        self._artifacts: dict[str, Artifact] = {}
        self._lineage = LineageIndex()
        self._variants = VariantTracker()

    # ---- write ----

    def put(
        self,
        *,
        artifact_id: str,
        value: Any,
        artifact_type: ArtifactType,
        role: ArtifactRole,
        format: str,
        mime_type: str,
        payload_kind: PayloadKind,
        producer: ProducerRef,
        schema_version: str = "1.0.0",
        lineage: Lineage | None = None,
        metadata: dict | None = None,
        tags: list[str] | None = None,
        validation: ValidationRecord | None = None,
        file_suffix: str = "",
    ) -> Artifact:
        """Persist the payload, compute hash, and register the Artifact."""
        ref = self._registry.write(
            payload_kind, value,
            run_id=producer.run_id, artifact_id=artifact_id, suffix=file_suffix,
        )
        art = Artifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            role=role,
            format=format,
            mime_type=mime_type,
            payload_ref=ref,
            schema_version=schema_version,
            hash=hash_payload(value),
            producer=producer,
            lineage=lineage or Lineage(),
            metadata=metadata or {},
            tags=tags or [],
            validation=validation or ValidationRecord(status="pending"),
            created_at=datetime.now(timezone.utc),
        )
        self._artifacts[artifact_id] = art
        self._lineage.register(art)
        self._variants.register(art)
        return art

    def register_existing(self, artifact: Artifact) -> None:
        """Add an already-built Artifact (e.g. reconstructed from checkpoint)."""
        self._artifacts[artifact.artifact_id] = artifact
        self._lineage.register(artifact)
        self._variants.register(artifact)

    # ---- read ----

    def get(self, artifact_id: str) -> Artifact:
        if artifact_id not in self._artifacts:
            raise KeyError(f"artifact {artifact_id} not found")
        return self._artifacts[artifact_id]

    def read_payload(self, artifact_id: str) -> Any:
        art = self.get(artifact_id)
        return self._registry.read(art.payload_ref)

    def exists(self, artifact_id: str) -> bool:
        return artifact_id in self._artifacts

    def __iter__(self) -> Iterator[Artifact]:
        return iter(self._artifacts.values())

    def all(self) -> list[Artifact]:
        return list(self._artifacts.values())

    # ---- queries ----

    def parents_of(self, artifact_id: str) -> list[Artifact]:
        return [self._artifacts[i] for i in self._lineage.parents_of(artifact_id) if i in self._artifacts]

    def children_of(self, artifact_id: str) -> list[Artifact]:
        return [self._artifacts[i] for i in self._lineage.children_of(artifact_id) if i in self._artifacts]

    def ancestors_of(self, artifact_id: str) -> list[Artifact]:
        return [self._artifacts[i] for i in self._lineage.ancestors_of(artifact_id) if i in self._artifacts]

    def siblings_of(self, artifact_id: str) -> list[Artifact]:
        return [self._artifacts[i] for i in self._variants.siblings_of(artifact_id) if i in self._artifacts]

    def find_by_hash(self, h: str) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.hash == h]

    def find_by_tag(self, tag: str) -> list[Artifact]:
        return [a for a in self._artifacts.values() if tag in a.tags]

    def find_by_producer(self, *, run_id: str | None = None, step_id: str | None = None) -> list[Artifact]:
        out = []
        for a in self._artifacts.values():
            if run_id and a.producer.run_id != run_id:
                continue
            if step_id and a.producer.step_id != step_id:
                continue
            out.append(a)
        return out

    # ---- bulk ----

    def bulk_register(self, artifacts: Iterable[Artifact]) -> None:
        for a in artifacts:
            self.register_existing(a)

    @property
    def backend_registry(self) -> PayloadBackendRegistry:
        return self._registry
