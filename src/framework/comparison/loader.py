"""Run-directory loader for the comparison module — read-only consumer.

See openspec/changes/add-run-comparison-baseline-regression/design.md §3 and
the runtime-core delta spec for behavior contracts.

Allowed framework imports (read-only validation + hash recompute only):
- framework.core.artifact.Artifact
- framework.core.enums.PayloadKind
- framework.core.runtime.Checkpoint
- framework.artifact_store.hashing.hash_payload

MUST NOT import framework.artifact_store.repository, payload_backends, runtime,
providers, review_engine, ue_bridge, workflows. The loader is a read-only
consumer outside the Run lifecycle and never writes through ArtifactRepository.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from framework.artifact_store.hashing import hash_payload
from framework.core.artifact import Artifact
from framework.core.enums import PayloadKind
from framework.core.runtime import Checkpoint

_DATE_BUCKET_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REVIEW_SHAPES = frozenset({"verdict", "review_report"})


class ComparisonLoaderError(Exception):
    """Base class for all comparison-loader errors.

    Local to framework.comparison; NOT registered into FailureModeMap and NOT
    surfaced through Run lifecycle exceptions.
    """


class RunDirNotFound(ComparisonLoaderError):
    """The run directory could not be located under the given artifact_root."""

    def __init__(
        self,
        run_id: str,
        artifact_root: Path,
        *,
        scanned: list[str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.artifact_root = artifact_root
        self.scanned = list(scanned or [])
        hint = f" scanned date buckets: {self.scanned}" if scanned is not None else ""
        super().__init__(f"run directory not found for run_id={run_id!r} under {artifact_root}.{hint}")


class RunDirAmbiguous(ComparisonLoaderError):
    """run_id matches multiple date buckets — caller must specify one."""

    def __init__(self, run_id: str, matches: list[Path]) -> None:
        self.run_id = run_id
        self.matches = list(matches)
        match_str = ", ".join(str(p) for p in self.matches)
        super().__init__(
            f"run_id={run_id!r} matches multiple date buckets: [{match_str}]. "
            f"Pass --baseline-date / --candidate-date to disambiguate."
        )


class RunSnapshotCorrupt(ComparisonLoaderError):
    """run_summary.json or _artifacts.json is missing, unparseable, or schema-invalid."""

    def __init__(self, run_dir: Path, what: str) -> None:
        self.run_dir = run_dir
        self.what = what
        super().__init__(f"run snapshot at {run_dir} is corrupt: {what}")


class PayloadMissingOnDisk(ComparisonLoaderError):
    """Strict mode: an Artifact record exists but its on-disk payload is missing."""

    def __init__(self, run_dir: Path, artifact_id: str, expected_path: Path) -> None:
        self.run_dir = run_dir
        self.artifact_id = artifact_id
        self.expected_path = expected_path
        super().__init__(
            f"payload missing on disk for artifact_id={artifact_id!r} "
            f"under {run_dir}: expected {expected_path}"
        )


@dataclass(frozen=True)
class RunSnapshot:
    """Read-only snapshot of one Run directory consumed by diff_engine."""

    run_dir: Path
    run_id: str
    date_bucket: str | None
    run_summary: dict[str, Any]
    artifacts: dict[str, Artifact]
    checkpoints: list[Checkpoint]
    payload_hashes: dict[str, str] = field(default_factory=dict)
    payload_hash_mismatches: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)
    payload_missing_on_disk: set[str] = field(default_factory=set)
    review_payloads: dict[str, dict[str, Any]] = field(default_factory=dict)


def resolve_run_dir(
    artifact_root: Path,
    run_id: str,
    date_bucket: str | None = None,
) -> Path:
    """Resolve the absolute path of <artifact_root>/<date_bucket>/<run_id>/.

    If `date_bucket` is given, the path is validated to exist as a directory.
    Otherwise the immediate children of `artifact_root` are scanned: only those
    whose name matches `^\\d{4}-\\d{2}-\\d{2}$` are considered date buckets.
    """
    artifact_root = Path(artifact_root)
    if not artifact_root.is_dir():
        raise RunDirNotFound(run_id, artifact_root)

    if date_bucket is not None:
        target = artifact_root / date_bucket / run_id
        if not target.is_dir():
            raise RunDirNotFound(run_id, artifact_root.resolve())
        return target.resolve()

    scanned: list[str] = []
    matches: list[Path] = []
    for child in sorted(artifact_root.iterdir()):
        if not child.is_dir():
            continue
        if not _DATE_BUCKET_RE.match(child.name):
            continue
        scanned.append(child.name)
        candidate = child / run_id
        if candidate.is_dir():
            matches.append(candidate.resolve())

    if not matches:
        raise RunDirNotFound(run_id, artifact_root.resolve(), scanned=scanned)
    if len(matches) > 1:
        raise RunDirAmbiguous(run_id, matches)
    return matches[0]


def _load_json(path: Path, *, run_dir: Path, what: str) -> Any:
    if not path.is_file():
        raise RunSnapshotCorrupt(run_dir, f"{what} not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RunSnapshotCorrupt(run_dir, f"{what} is not valid JSON: {exc}") from exc


def _payload_path(run_dir: Path, artifact: Artifact) -> Path | None:
    """Resolve the absolute on-disk path for a file-backed payload, or None
    when the artifact uses inline / blob backend or has no recorded file_path.

    Mirrors FileBackend layout `<root>/<run_id>/<artifact_id><suffix>` where
    backend root equals `run_dir.parent` (the artifact_root passed into
    `framework.run` when the original Run started, e.g. `artifacts/<date>/`).

    Raises `RunSnapshotCorrupt` when `payload_ref.file_path` escapes the
    file-backend root via path traversal — that is a data-integrity violation
    of `_artifacts.json`, NOT a missing-payload condition, so it must surface
    independently of the include_payload_hash_check / strict flags.
    """
    ref = artifact.payload_ref
    if ref.kind != PayloadKind.file:
        return None
    if not ref.file_path:
        return None
    file_backend_root = run_dir.parent.resolve()
    candidate = (file_backend_root / ref.file_path).resolve()
    try:
        candidate.relative_to(file_backend_root)
    except ValueError:
        raise RunSnapshotCorrupt(
            run_dir,
            f"file_path traversal escape for artifact_id={artifact.artifact_id!r}: "
            f"{ref.file_path!r} escapes backend root {file_backend_root}",
        ) from None
    return candidate


def load_run_snapshot(
    run_dir: Path,
    *,
    include_payload_hash_check: bool = True,
    strict: bool = True,
) -> RunSnapshot:
    """Load run_summary.json + _artifacts.json + (optional) _checkpoints.json
    and (optionally) recompute file-backed payload hashes.

    Behavior matrix
    ---------------
    include_payload_hash_check=False
        No payload reading at all. payload_hashes, payload_hash_mismatches,
        and payload_missing_on_disk are empty regardless of `strict`.
    include_payload_hash_check=True, strict=True
        Missing on-disk payload raises `PayloadMissingOnDisk`.
    include_payload_hash_check=True, strict=False
        Missing on-disk payload is recorded in `payload_missing_on_disk` set;
        no exception.

    `review_payloads` is populated best-effort and is independent of the
    hash-check / strict flags. It silently skips any verdict / review_report
    artifact whose payload cannot be read or parsed as a JSON object. It does
    NOT validate against ReviewReport / Verdict pydantic schemas.
    """
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_dir():
        raise RunSnapshotCorrupt(run_dir, "run_dir is not a directory")

    summary_raw = _load_json(run_dir / "run_summary.json", run_dir=run_dir, what="run_summary.json")
    if not isinstance(summary_raw, dict):
        raise RunSnapshotCorrupt(run_dir, "run_summary.json is not a JSON object")
    if "status" not in summary_raw:
        raise RunSnapshotCorrupt(run_dir, "run_summary.json missing required 'status' field")

    artifacts_raw = _load_json(run_dir / "_artifacts.json", run_dir=run_dir, what="_artifacts.json")
    if not isinstance(artifacts_raw, list):
        raise RunSnapshotCorrupt(run_dir, "_artifacts.json is not a JSON array")
    artifacts: dict[str, Artifact] = {}
    for entry in artifacts_raw:
        try:
            art = Artifact.model_validate(entry)
        except Exception as exc:
            raise RunSnapshotCorrupt(
                run_dir, f"_artifacts.json contains invalid Artifact record: {exc}"
            ) from exc
        artifacts[art.artifact_id] = art

    checkpoints: list[Checkpoint] = []
    cp_path = run_dir / "_checkpoints.json"
    if cp_path.is_file():
        cp_raw = _load_json(cp_path, run_dir=run_dir, what="_checkpoints.json")
        if not isinstance(cp_raw, list):
            raise RunSnapshotCorrupt(run_dir, "_checkpoints.json is not a JSON array")
        for entry in cp_raw:
            try:
                checkpoints.append(Checkpoint.model_validate(entry))
            except Exception as exc:
                raise RunSnapshotCorrupt(
                    run_dir,
                    f"_checkpoints.json contains invalid Checkpoint record: {exc}",
                ) from exc

    parent_name = run_dir.parent.name if run_dir.parent != run_dir else ""
    date_bucket = parent_name if _DATE_BUCKET_RE.match(parent_name) else None

    # Pre-resolve every artifact's on-disk payload path. This pass is the single
    # entry point that raises RunSnapshotCorrupt on file_path traversal escape,
    # so the behavior is uniform regardless of include_payload_hash_check /
    # strict / artifact modality.
    payload_paths: dict[str, Path | None] = {
        aid: _payload_path(run_dir, art) for aid, art in artifacts.items()
    }

    payload_hashes: dict[str, str] = {}
    payload_hash_mismatches: dict[str, tuple[str | None, str | None]] = {}
    payload_missing_on_disk: set[str] = set()

    if include_payload_hash_check:
        for aid, art in artifacts.items():
            if art.payload_ref.kind != PayloadKind.file:
                continue
            path = payload_paths[aid]
            if path is None or not path.is_file():
                # path is None only if file_path was empty, which the
                # PayloadRef validator already rejects. Defensive fallback:
                # surface the recorded file_path verbatim in the error.
                expected = path if path is not None else run_dir.parent / (art.payload_ref.file_path or "")
                if strict:
                    raise PayloadMissingOnDisk(run_dir, aid, expected)
                payload_missing_on_disk.add(aid)
                continue
            recomputed = hash_payload(path.read_bytes())
            payload_hashes[aid] = recomputed
            if recomputed != art.hash:
                payload_hash_mismatches[aid] = (art.hash, recomputed)

    review_payloads: dict[str, dict[str, Any]] = {}
    for aid, art in artifacts.items():
        if art.artifact_type.modality != "report":
            continue
        if art.artifact_type.shape not in _REVIEW_SHAPES:
            continue
        if art.payload_ref.kind == PayloadKind.inline:
            inline = art.payload_ref.inline_value
            if isinstance(inline, dict):
                review_payloads[aid] = inline
            continue
        if art.payload_ref.kind != PayloadKind.file:
            continue
        if aid in payload_missing_on_disk:
            continue
        path = payload_paths[aid]
        if path is None or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            review_payloads[aid] = data

    return RunSnapshot(
        run_dir=run_dir,
        run_id=run_dir.name,
        date_bucket=date_bucket,
        run_summary=summary_raw,
        artifacts=artifacts,
        checkpoints=checkpoints,
        payload_hashes=payload_hashes,
        payload_hash_mismatches=payload_hash_mismatches,
        payload_missing_on_disk=payload_missing_on_disk,
        review_payloads=review_payloads,
    )
