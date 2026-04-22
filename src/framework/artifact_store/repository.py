"""Artifact repository — single entry point for writing and reading Artifacts (§F0-3).

Combines:
- PayloadRef backends (inline/file/blob)
- Lineage index
- Variant tracker
- Content hashing

MVP: in-process dict-backed store. Persistence is via file payload backend.
Run-scoped metadata (Artifact records minus the bytes themselves) can be
dumped to / loaded from `<run_dir>/_artifacts.json` so a fresh CLI process
with `--resume` can rebuild the repository and let CheckpointStore.find_hit
actually report cache hits instead of silently rerunning the pipeline.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from framework.artifact_store.hashing import hash_payload
from framework.core.enums import PayloadKind as _PayloadKind
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
        # Snapshot via list() to avoid `dictionary changed size during
        # iteration` when concurrent steps in DAG mode mutate the dict
        # from worker threads while a main-loop dump is in flight.
        out = []
        for a in list(self._artifacts.values()):
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

    # ---- per-run metadata persistence ----

    def dump_run_metadata(self, *, run_id: str, run_dir: Path) -> int:
        """Write Artifact metadata for *run_id* to `<run_dir>/_artifacts.json`.
        Payload bytes themselves are NOT duplicated — file/blob backends
        already keep them on disk; this dump records artifact_id → hash,
        payload_ref, lineage etc. so a fresh-process resume can rebuild
        the in-memory index.
        """
        run_arts = self.find_by_producer(run_id=run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        target = run_dir / "_artifacts.json"
        data = [a.model_dump(mode="json") for a in run_arts]
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        return len(run_arts)

    def load_run_metadata(self, *, run_id: str, run_dir: Path) -> int:
        """Re-hydrate Artifact records produced by *run_id* from
        `<run_dir>/_artifacts.json`. Returns the count of newly-registered
        artifacts (pre-existing ids skipped, missing-payload entries
        skipped, hash-drift entries skipped). Returns 0 silently when
        the dump file is absent.

        For file/blob-backed artifacts, the persisted hash MUST match the
        current bytes on disk before we register the record — otherwise
        `CheckpointStore.find_hit()` would treat externally-modified or
        corrupted payloads as valid cache hits and propagate broken
        bytes to downstream steps. Inline artifacts skip the recheck
        because their payload travels with the metadata (no external
        bytes to drift).
        """
        target = run_dir / "_artifacts.json"
        if not target.is_file():
            return 0
        raw = json.loads(target.read_text(encoding="utf-8"))
        n = 0
        for d in raw:
            art = Artifact.model_validate(d)
            if art.artifact_id in self._artifacts:
                continue
            try:
                payload_present = self._registry.exists(art.payload_ref)
            except KeyError:
                payload_present = False
            if not payload_present:
                continue
            # For external-bytes payloads, verify the bytes haven't
            # drifted since the dump (overwrite, partial write, manual
            # edit). hash_payload re-canonicalizes via the same path as
            # the original write, so the comparison is apples-to-apples.
            if art.payload_ref.kind in (_PayloadKind.file, _PayloadKind.blob):
                try:
                    current = self._registry.read(art.payload_ref)
                except Exception:
                    continue
                if hash_payload(current) != art.hash:
                    continue
            self.register_existing(art)
            n += 1
        return n
