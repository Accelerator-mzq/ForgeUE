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
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from framework.artifact_store.hashing import hash_path, hash_payload
from framework.core.enums import PayloadKind as _PayloadKind
from framework.artifact_store.lineage import LineageIndex
from framework.artifact_store.payload_backends.base import (
    PayloadBackendRegistry,
    _MISSING,
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


_ARTIFACTS_FILENAME = "_artifacts.json"
_ARTIFACTS_INTEGRITY_FILENAME = "_artifacts.integrity.json"
_ARTIFACTS_INTEGRITY_SCHEMA_VERSION = "1.0"
_ARTIFACTS_INTEGRITY_ALGORITHM = "sha256"


class ArtifactMetadataIntegrityError(RuntimeError):
    """`_artifacts.json` integrity 校验失败。"""

    def __init__(self, run_dir: Path, reason: str) -> None:
        super().__init__(f"artifact metadata integrity failed for {run_dir}: {reason}")
        self.run_dir = run_dir
        self.reason = reason


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
        value: Any = _MISSING,
        source_path: str | os.PathLike | None = None,
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
        """Persist the payload, compute hash, and register the Artifact.

        Either *value* (any type, including None for inline JSON null) OR
        *source_path* MUST be provided (mutually exclusive, D10 sentinel-based).
        *source_path* requires payload_kind in {PayloadKind.file, PayloadKind.blob}.

        D10 D-NullValueAmbiguity: 用 _MISSING identity 区分 "未传" vs "显式 None"
        (value=None 是合法 inline JSON null payload,不能当 '未传' 处理)。
        """
        # 三守门:互斥 / 两者都缺 / payload_kind 错误
        if value is _MISSING and source_path is None:
            raise ValueError("repo.put requires either value or source_path")
        if value is not _MISSING and source_path is not None:
            raise ValueError("repo.put: value and source_path are mutually exclusive")
        if source_path is not None and payload_kind not in {
            PayloadKind.file,
            PayloadKind.blob,
        }:
            raise ValueError(
                "repo.put: source_path requires payload_kind=file or blob "
                f"(got {payload_kind!r})"
            )

        # 落盘并接收 backend 已验证的内容 hash。
        # FOR-12:source_path 分支的 hash 在 staging tmp 上完成,repo 不再
        # 在 replace 后重算 final hash,避免 payload/metadata 半提交窗口。
        result = self._registry.write(
            payload_kind, value,
            run_id=producer.run_id, artifact_id=artifact_id, suffix=file_suffix,
            source_path=source_path,
        )
        ref = result.ref
        content_hash = result.content_hash

        art = Artifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            role=role,
            format=format,
            mime_type=mime_type,
            payload_ref=ref,
            schema_version=schema_version,
            hash=content_hash,
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
        target = run_dir / _ARTIFACTS_FILENAME
        data = [a.model_dump(mode="json") for a in run_arts]
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        self._write_metadata_integrity(run_dir=run_dir, artifacts=run_arts)
        return len(run_arts)

    def _write_metadata_integrity(
        self,
        *,
        run_dir: Path,
        artifacts: list[Artifact],
    ) -> None:
        """写入绑定最终 `_artifacts.json` 字节的 checksum metadata。"""
        artifacts_path = run_dir / _ARTIFACTS_FILENAME
        integrity_path = run_dir / _ARTIFACTS_INTEGRITY_FILENAME
        data = {
            "schema_version": _ARTIFACTS_INTEGRITY_SCHEMA_VERSION,
            "artifacts_file": _ARTIFACTS_FILENAME,
            "algorithm": _ARTIFACTS_INTEGRITY_ALGORITHM,
            "artifacts_sha256": hash_path(artifacts_path),
            "artifact_count": len(artifacts),
            "artifact_ids": [a.artifact_id for a in artifacts],
        }
        integrity_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _verify_metadata_integrity(self, *, run_dir: Path) -> None:
        """发现 `_artifacts.json` 与 integrity 文件不一致时立即失败。"""
        integrity_path = run_dir / _ARTIFACTS_INTEGRITY_FILENAME
        if not integrity_path.is_file():
            return

        try:
            integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ArtifactMetadataIntegrityError(
                run_dir, f"integrity file invalid JSON: {exc}"
            ) from exc

        if not isinstance(integrity, dict):
            raise ArtifactMetadataIntegrityError(
                run_dir, "integrity file must be a JSON object"
            )
        if integrity.get("schema_version") != _ARTIFACTS_INTEGRITY_SCHEMA_VERSION:
            raise ArtifactMetadataIntegrityError(
                run_dir,
                f"unsupported integrity schema_version: {integrity.get('schema_version')!r}",
            )
        if integrity.get("artifacts_file") != _ARTIFACTS_FILENAME:
            raise ArtifactMetadataIntegrityError(
                run_dir,
                f"unexpected integrity artifacts_file: {integrity.get('artifacts_file')!r}",
            )
        if integrity.get("algorithm") != _ARTIFACTS_INTEGRITY_ALGORITHM:
            raise ArtifactMetadataIntegrityError(
                run_dir,
                f"unsupported integrity algorithm: {integrity.get('algorithm')!r}",
            )

        artifacts_path = run_dir / _ARTIFACTS_FILENAME
        expected_hash = integrity.get("artifacts_sha256")
        actual_hash = hash_path(artifacts_path)
        if expected_hash != actual_hash:
            raise ArtifactMetadataIntegrityError(
                run_dir,
                f"_artifacts.json hash mismatch: expected {expected_hash!r}, got {actual_hash!r}",
            )

        try:
            artifacts_raw = json.loads(artifacts_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ArtifactMetadataIntegrityError(
                run_dir, f"_artifacts.json invalid JSON: {exc}"
            ) from exc
        if not isinstance(artifacts_raw, list):
            raise ArtifactMetadataIntegrityError(
                run_dir, "_artifacts.json must be a JSON array"
            )

        actual_ids: list[str] = []
        for entry in artifacts_raw:
            if not isinstance(entry, dict) or not isinstance(
                entry.get("artifact_id"), str
            ):
                raise ArtifactMetadataIntegrityError(
                    run_dir,
                    "_artifacts.json contains entry without string artifact_id",
                )
            actual_ids.append(entry["artifact_id"])

        if integrity.get("artifact_count") != len(artifacts_raw):
            raise ArtifactMetadataIntegrityError(
                run_dir,
                f"artifact count mismatch: expected {integrity.get('artifact_count')!r}, got {len(artifacts_raw)!r}",
            )
        if integrity.get("artifact_ids") != actual_ids:
            raise ArtifactMetadataIntegrityError(
                run_dir,
                f"artifact id list mismatch: expected {integrity.get('artifact_ids')!r}, got {actual_ids!r}",
            )

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
        target = run_dir / _ARTIFACTS_FILENAME
        if not target.is_file():
            return 0
        self._verify_metadata_integrity(run_dir=run_dir)
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
            # For external-bytes payloads, verify the bytes haven't drifted
            # since the dump (overwrite, partial write, manual edit).
            # file kind 走本地 hash_path;blob kind 走 backend.read()+hash_payload,
            # 因对象存储没有可用的本地 absolute_path。
            if art.payload_ref.kind == _PayloadKind.file:
                # File-kind stream drift:hash_path(absolute_path),不全读;
                # 8 MB chunks → bounded RSS even for large video / mesh artifacts
                try:
                    backend = self._registry.get(_PayloadKind.file)
                    abs_path = backend.absolute_path(art.payload_ref)
                except (KeyError, ValueError):
                    continue
                try:
                    current_hash = hash_path(abs_path)
                except (FileNotFoundError, OSError):
                    continue
                if current_hash != art.hash:
                    continue
            elif art.payload_ref.kind == _PayloadKind.blob:
                # BlobBackend MVP:读回 object bytes 后按 Artifact.hash 比对。
                # 后续真实云 adapter 可在 read 内部用 SDK 实现下载;更高级的
                # etag / Last-Modified 优化不改变本层语义。
                try:
                    current = self._registry.read(art.payload_ref)
                except Exception:
                    continue
                if hash_payload(current) != art.hash:
                    continue
            # inline 路径不变(在更上面的代码段处理)
            self.register_existing(art)
            n += 1
        return n
