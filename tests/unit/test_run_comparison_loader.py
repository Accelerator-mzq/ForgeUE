"""Unit tests for framework.comparison.loader.

Covers resolve_run_dir + load_run_snapshot, including:
- Date bucket resolution (explicit / auto-discover / ambiguous / not found)
- run_summary.json + _artifacts.json + _checkpoints.json parsing
- Payload hash recompute matrix (include_payload_hash_check x strict)
- review_payloads best-effort extraction (no review_engine import)
- RunSnapshot frozen-dataclass invariant
- Exception hierarchy
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from framework.comparison.loader import (
    ComparisonLoaderError,
    PayloadMissingOnDisk,
    RunDirAmbiguous,
    RunDirNotFound,
    RunSnapshot,
    RunSnapshotCorrupt,
    load_run_snapshot,
    resolve_run_dir,
)
from framework.core.artifact import (
    Artifact,
    ArtifactType,
    Lineage,
    PayloadRef,
    ProducerRef,
)
from framework.core.enums import ArtifactRole, PayloadKind
from framework.core.runtime import Checkpoint

# ----- helpers -----


def _make_file_artifact(
    *,
    aid: str = "a1",
    run_id: str = "r1",
    suffix: str = ".bin",
    hash_str: str = "deadbeef",
    modality: str = "image",
    shape: str = "png",
    metadata: dict[str, Any] | None = None,
    lineage_kwargs: dict[str, Any] | None = None,
) -> Artifact:
    rel = f"{run_id}/{aid}{suffix}"
    return Artifact(
        artifact_id=aid,
        artifact_type=ArtifactType(modality=modality, shape=shape, display_name=f"{modality}.{shape}"),
        role=ArtifactRole.intermediate,
        format=shape,
        mime_type=f"application/{shape}",
        payload_ref=PayloadRef(kind=PayloadKind.file, file_path=rel, size_bytes=4),
        schema_version="1.0.0",
        hash=hash_str,
        producer=ProducerRef(run_id=run_id, step_id="s1"),
        lineage=Lineage(**(lineage_kwargs or {})),
        metadata=metadata or {},
        created_at=datetime(2000, 1, 1, tzinfo=UTC),
    )


def _make_inline_artifact(
    *,
    aid: str = "inline_a1",
    run_id: str = "r1",
    inline_value: Any | None = None,
    hash_str: str = "feedface",
    modality: str = "report",
    shape: str = "verdict",
) -> Artifact:
    if inline_value is None:
        inline_value = {"decision": "approve"}
    return Artifact(
        artifact_id=aid,
        artifact_type=ArtifactType(modality=modality, shape=shape, display_name=f"{modality}.{shape}"),
        role=ArtifactRole.intermediate,
        format="json",
        mime_type="application/json",
        payload_ref=PayloadRef(kind=PayloadKind.inline, inline_value=inline_value, size_bytes=16),
        schema_version="1.0.0",
        hash=hash_str,
        producer=ProducerRef(run_id=run_id, step_id="s1"),
        created_at=datetime(2000, 1, 1, tzinfo=UTC),
    )


def _make_blob_artifact(
    *,
    aid: str = "blob_a1",
    run_id: str = "r1",
    hash_str: str = "cafebabe",
) -> Artifact:
    return Artifact(
        artifact_id=aid,
        artifact_type=ArtifactType(modality="mesh", shape="glb", display_name="mesh.glb"),
        role=ArtifactRole.intermediate,
        format="glb",
        mime_type="model/gltf-binary",
        payload_ref=PayloadRef(kind=PayloadKind.blob, blob_key=f"blob_{aid}", size_bytes=4),
        schema_version="1.0.0",
        hash=hash_str,
        producer=ProducerRef(run_id=run_id, step_id="s1"),
        created_at=datetime(2000, 1, 1, tzinfo=UTC),
    )


def _make_checkpoint(*, run_id: str = "r1", step_id: str = "s1") -> Checkpoint:
    return Checkpoint(
        checkpoint_id=f"cp_{run_id}_{step_id}",
        run_id=run_id,
        step_id=step_id,
        artifact_ids=["a1"],
        artifact_hashes=["deadbeef"],
        input_hash="input_hash_1",
        completed_at=datetime(2000, 1, 1, tzinfo=UTC),
        metrics={"cost_usd": 0.001},
    )


@pytest.fixture
def make_run(tmp_path: Path):
    """Build a minimal run dir at <tmp_path>/artifacts/<date>/<run_id>/.

    Returns (artifact_root, run_dir). Caller controls every section explicitly:
    use `omit=` to skip writing one of {run_summary, artifacts, checkpoints}.
    """

    def _make(
        *,
        run_id: str = "r1",
        date: str = "2000-01-01",
        status: str | None = "succeeded",
        run_summary_extra: dict[str, Any] | None = None,
        run_summary_raw: Any = None,  # if given, written verbatim (overrides everything)
        artifacts: list[Artifact] | None = None,
        artifacts_raw: Any = None,  # bypass model_dump and write verbatim
        checkpoints: list[Checkpoint] | None = None,
        checkpoints_raw: Any = None,
        payloads: dict[str, bytes] | None = None,
        omit: set[str] | None = None,
    ) -> tuple[Path, Path]:
        omit = omit or set()
        artifact_root = tmp_path / "artifacts"
        run_dir = artifact_root / date / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        if "run_summary" not in omit:
            if run_summary_raw is not None:
                if isinstance(run_summary_raw, str):
                    (run_dir / "run_summary.json").write_text(run_summary_raw, encoding="utf-8")
                else:
                    (run_dir / "run_summary.json").write_text(json.dumps(run_summary_raw), encoding="utf-8")
            else:
                summary: dict[str, Any] = {"run_id": run_id}
                if status is not None:
                    summary["status"] = status
                if run_summary_extra:
                    summary.update(run_summary_extra)
                (run_dir / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")

        if "artifacts" not in omit:
            if artifacts_raw is not None:
                if isinstance(artifacts_raw, str):
                    (run_dir / "_artifacts.json").write_text(artifacts_raw, encoding="utf-8")
                else:
                    (run_dir / "_artifacts.json").write_text(json.dumps(artifacts_raw), encoding="utf-8")
            else:
                arts = artifacts or []
                (run_dir / "_artifacts.json").write_text(
                    json.dumps([a.model_dump(mode="json") for a in arts]),
                    encoding="utf-8",
                )

        if checkpoints_raw is not None:
            if isinstance(checkpoints_raw, str):
                (run_dir / "_checkpoints.json").write_text(checkpoints_raw, encoding="utf-8")
            else:
                (run_dir / "_checkpoints.json").write_text(json.dumps(checkpoints_raw), encoding="utf-8")
        elif checkpoints is not None:
            (run_dir / "_checkpoints.json").write_text(
                json.dumps([c.model_dump(mode="json") for c in checkpoints]),
                encoding="utf-8",
            )

        if payloads:
            for fname, data in payloads.items():
                target = artifact_root / date / fname
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)

        return artifact_root, run_dir

    return _make


# ----- TestResolveRunDir -----


class TestResolveRunDir:
    def test_explicit_date_bucket_hit(self, make_run):
        artifact_root, run_dir = make_run()
        resolved = resolve_run_dir(artifact_root, "r1", date_bucket="2000-01-01")
        assert resolved == run_dir.resolve()

    def test_auto_discover_single_match(self, make_run):
        artifact_root, run_dir = make_run()
        resolved = resolve_run_dir(artifact_root, "r1")
        assert resolved == run_dir.resolve()

    def test_auto_discover_multi_match_raises_ambiguous(self, make_run):
        artifact_root, run_dir_a = make_run(date="2000-01-01")
        _, run_dir_b = make_run(date="2000-01-02")
        with pytest.raises(RunDirAmbiguous) as excinfo:
            resolve_run_dir(artifact_root, "r1")
        assert excinfo.value.run_id == "r1"
        assert len(excinfo.value.matches) == 2
        assert "--baseline-date" in str(excinfo.value)

    def test_auto_discover_zero_match_raises_not_found(self, make_run):
        artifact_root, _ = make_run(run_id="r1")
        with pytest.raises(RunDirNotFound) as excinfo:
            resolve_run_dir(artifact_root, "different_run")
        assert excinfo.value.run_id == "different_run"
        assert excinfo.value.scanned == ["2000-01-01"]

    def test_artifact_root_missing_raises_not_found(self, tmp_path):
        with pytest.raises(RunDirNotFound):
            resolve_run_dir(tmp_path / "nonexistent", "r1")

    def test_artifact_root_is_file_raises_not_found(self, tmp_path):
        f = tmp_path / "not_a_dir.txt"
        f.write_text("hi")
        with pytest.raises(RunDirNotFound):
            resolve_run_dir(f, "r1")

    def test_explicit_date_with_run_id_absent_raises_not_found(self, make_run):
        artifact_root, _ = make_run(run_id="r1", date="2000-01-01")
        with pytest.raises(RunDirNotFound):
            resolve_run_dir(artifact_root, "missing_run", date_bucket="2000-01-01")

    def test_explicit_date_when_bucket_absent_raises_not_found(self, make_run):
        artifact_root, _ = make_run(run_id="r1", date="2000-01-01")
        with pytest.raises(RunDirNotFound):
            resolve_run_dir(artifact_root, "r1", date_bucket="2099-12-31")

    def test_skips_non_date_buckets(self, make_run, tmp_path):
        artifact_root, run_dir = make_run()
        # Pollute with non-date siblings
        (artifact_root / "_metadata").mkdir()
        (artifact_root / "_metadata" / "r1").mkdir()
        (artifact_root / "notes.txt").write_text("noise")
        (artifact_root / "2026").mkdir()
        (artifact_root / "2026" / "r1").mkdir()
        resolved = resolve_run_dir(artifact_root, "r1")
        # The non-date siblings should be ignored even though one literally has a r1/ child.
        assert resolved == run_dir.resolve()


# ----- TestLoadRunSnapshotSchema -----


class TestLoadRunSnapshotSchema:
    def test_happy_path_returns_run_snapshot(self, make_run):
        art = _make_file_artifact()
        cp = _make_checkpoint()
        _, run_dir = make_run(artifacts=[art], checkpoints=[cp], payloads={"r1/a1.bin": b"\x01\x02\x03\x04"})
        snap = load_run_snapshot(run_dir, include_payload_hash_check=False)
        assert isinstance(snap, RunSnapshot)
        assert snap.run_id == "r1"
        assert snap.date_bucket == "2000-01-01"
        assert snap.run_summary["status"] == "succeeded"
        assert "a1" in snap.artifacts
        assert isinstance(snap.artifacts["a1"], Artifact)
        assert len(snap.checkpoints) == 1
        assert snap.checkpoints[0].step_id == "s1"

    def test_run_dir_not_a_directory_raises_corrupt(self, tmp_path):
        with pytest.raises(RunSnapshotCorrupt):
            load_run_snapshot(tmp_path / "nonexistent_run")

    def test_missing_run_summary_raises_corrupt(self, make_run):
        _, run_dir = make_run(omit={"run_summary"})
        with pytest.raises(RunSnapshotCorrupt) as excinfo:
            load_run_snapshot(run_dir)
        assert "run_summary" in str(excinfo.value)

    def test_run_summary_lacks_status_raises_corrupt(self, make_run):
        _, run_dir = make_run(status=None)
        with pytest.raises(RunSnapshotCorrupt) as excinfo:
            load_run_snapshot(run_dir)
        assert "status" in str(excinfo.value)

    def test_run_summary_invalid_json_raises_corrupt(self, make_run):
        _, run_dir = make_run(run_summary_raw="not { valid json")
        with pytest.raises(RunSnapshotCorrupt) as excinfo:
            load_run_snapshot(run_dir)
        assert "run_summary.json" in str(excinfo.value)

    def test_run_summary_not_object_raises_corrupt(self, make_run):
        _, run_dir = make_run(run_summary_raw=["array", "not", "object"])
        with pytest.raises(RunSnapshotCorrupt):
            load_run_snapshot(run_dir)

    def test_missing_artifacts_raises_corrupt(self, make_run):
        _, run_dir = make_run(omit={"artifacts"})
        with pytest.raises(RunSnapshotCorrupt) as excinfo:
            load_run_snapshot(run_dir)
        assert "_artifacts" in str(excinfo.value)

    def test_artifacts_invalid_json_raises_corrupt(self, make_run):
        _, run_dir = make_run(artifacts_raw="{not json")
        with pytest.raises(RunSnapshotCorrupt):
            load_run_snapshot(run_dir)

    def test_artifacts_not_array_raises_corrupt(self, make_run):
        _, run_dir = make_run(artifacts_raw={"map": "not array"})
        with pytest.raises(RunSnapshotCorrupt):
            load_run_snapshot(run_dir)

    def test_artifacts_invalid_record_raises_corrupt(self, make_run):
        _, run_dir = make_run(artifacts_raw=[{"artifact_id": "missing_required_fields"}])
        with pytest.raises(RunSnapshotCorrupt) as excinfo:
            load_run_snapshot(run_dir)
        assert "Artifact record" in str(excinfo.value)

    def test_no_checkpoints_file_returns_empty_list(self, make_run):
        _, run_dir = make_run(artifacts=[_make_file_artifact()])
        snap = load_run_snapshot(run_dir, include_payload_hash_check=False)
        assert snap.checkpoints == []

    def test_checkpoints_invalid_record_raises_corrupt(self, make_run):
        _, run_dir = make_run(checkpoints_raw=[{"checkpoint_id": "incomplete"}])
        with pytest.raises(RunSnapshotCorrupt) as excinfo:
            load_run_snapshot(run_dir, include_payload_hash_check=False)
        assert "Checkpoint record" in str(excinfo.value)

    def test_checkpoints_not_array_raises_corrupt(self, make_run):
        _, run_dir = make_run(checkpoints_raw={"map": "not array"})
        with pytest.raises(RunSnapshotCorrupt):
            load_run_snapshot(run_dir, include_payload_hash_check=False)

    def test_artifacts_returned_as_pydantic_instances(self, make_run):
        art = _make_file_artifact(aid="img_0")
        _, run_dir = make_run(artifacts=[art], payloads={"r1/img_0.bin": b"hi"})
        snap = load_run_snapshot(run_dir, include_payload_hash_check=False)
        assert isinstance(snap.artifacts["img_0"], Artifact)
        assert snap.artifacts["img_0"].artifact_type.modality == "image"


# ----- TestLoadRunSnapshotPayloadHash -----


class TestLoadRunSnapshotPayloadHash:
    def _build(self, make_run, *, payload: bytes, recorded_hash: str):
        art = _make_file_artifact(aid="a1", hash_str=recorded_hash)
        return make_run(artifacts=[art], payloads={"r1/a1.bin": payload})

    def test_hash_matches_no_mismatch(self, make_run):
        from framework.artifact_store.hashing import hash_payload as _hp

        payload = b"\xde\xad\xbe\xef"
        _, run_dir = self._build(make_run, payload=payload, recorded_hash=_hp(payload))
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        assert snap.payload_hashes["a1"] == _hp(payload)
        assert snap.payload_hash_mismatches == {}
        assert snap.payload_missing_on_disk == set()

    def test_hash_mismatch_recorded(self, make_run):
        _, run_dir = self._build(make_run, payload=b"actual_bytes", recorded_hash="recorded_but_wrong")
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        assert "a1" in snap.payload_hash_mismatches
        recorded, recomputed = snap.payload_hash_mismatches["a1"]
        assert recorded == "recorded_but_wrong"
        assert recomputed != recorded
        assert snap.payload_hashes["a1"] == recomputed

    def test_inline_artifact_skipped_in_hash_check(self, make_run):
        art = _make_inline_artifact()
        _, run_dir = make_run(artifacts=[art])
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        assert snap.payload_hashes == {}
        assert snap.payload_hash_mismatches == {}

    def test_blob_artifact_skipped_in_hash_check(self, make_run):
        art = _make_blob_artifact()
        _, run_dir = make_run(artifacts=[art])
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        assert snap.payload_hashes == {}
        assert snap.payload_missing_on_disk == set()

    def test_strict_true_payload_missing_raises(self, make_run):
        art = _make_file_artifact(aid="a1")
        _, run_dir = make_run(artifacts=[art])  # no payloads written
        with pytest.raises(PayloadMissingOnDisk) as excinfo:
            load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        assert excinfo.value.artifact_id == "a1"

    def test_strict_false_payload_missing_recorded(self, make_run):
        art = _make_file_artifact(aid="a1")
        _, run_dir = make_run(artifacts=[art])  # no payloads written
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=False)
        assert snap.payload_missing_on_disk == {"a1"}
        assert snap.payload_hashes == {}

    def test_include_payload_hash_check_false_skips_all(self, make_run):
        art = _make_file_artifact(aid="a1")
        _, run_dir = make_run(artifacts=[art])  # no payloads
        snap = load_run_snapshot(run_dir, include_payload_hash_check=False, strict=True)
        assert snap.payload_hashes == {}
        assert snap.payload_hash_mismatches == {}
        assert snap.payload_missing_on_disk == set()


# ----- TestLoadRunSnapshotReviewPayloads -----


class TestLoadRunSnapshotReviewPayloads:
    def test_extracts_verdict_payload_from_file(self, make_run):
        from framework.artifact_store.hashing import hash_payload as _hp

        body = {"decision": "approve", "confidence": 0.9, "selected_candidate_ids": ["c1"]}
        body_bytes = json.dumps(body).encode("utf-8")
        art = _make_file_artifact(
            aid="v1",
            suffix=".json",
            modality="report",
            shape="verdict",
            hash_str=_hp(body_bytes),
        )
        _, run_dir = make_run(artifacts=[art], payloads={"r1/v1.json": body_bytes})
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        assert "v1" in snap.review_payloads
        assert snap.review_payloads["v1"]["decision"] == "approve"

    def test_extracts_review_report_payload_from_file(self, make_run):
        from framework.artifact_store.hashing import hash_payload as _hp

        body = {"summary": "ok", "scores": {"composition": 0.8}}
        body_bytes = json.dumps(body).encode("utf-8")
        art = _make_file_artifact(
            aid="rr1",
            suffix=".json",
            modality="report",
            shape="review_report",
            hash_str=_hp(body_bytes),
        )
        _, run_dir = make_run(artifacts=[art], payloads={"r1/rr1.json": body_bytes})
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        assert "rr1" in snap.review_payloads
        assert snap.review_payloads["rr1"]["summary"] == "ok"

    def test_inline_verdict_payload_extracted(self, make_run):
        body = {"decision": "reject", "confidence": 0.2}
        art = _make_inline_artifact(aid="iv1", inline_value=body, shape="verdict")
        _, run_dir = make_run(artifacts=[art])
        snap = load_run_snapshot(run_dir, include_payload_hash_check=False)
        assert snap.review_payloads.get("iv1") == body

    def test_missing_verdict_file_silently_skipped_when_non_strict(self, make_run):
        art = _make_file_artifact(aid="v1", suffix=".json", modality="report", shape="verdict")
        _, run_dir = make_run(artifacts=[art])  # no payloads written
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=False)
        assert "v1" not in snap.review_payloads
        assert snap.payload_missing_on_disk == {"v1"}

    def test_invalid_json_verdict_silently_skipped(self, make_run):
        from framework.artifact_store.hashing import hash_payload as _hp

        bad_bytes = b"{{not json"
        art = _make_file_artifact(
            aid="v1",
            suffix=".json",
            modality="report",
            shape="verdict",
            hash_str=_hp(bad_bytes),
        )
        _, run_dir = make_run(artifacts=[art], payloads={"r1/v1.json": bad_bytes})
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        assert "v1" not in snap.review_payloads

    def test_non_report_artifact_excluded_from_review_payloads(self, make_run):
        from framework.artifact_store.hashing import hash_payload as _hp

        body = b'{"some":"data"}'
        art = _make_file_artifact(aid="img_a", modality="image", shape="png", hash_str=_hp(body))
        _, run_dir = make_run(artifacts=[art], payloads={"r1/img_a.bin": body})
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        assert "img_a" not in snap.review_payloads

    def test_report_with_non_dict_json_silently_skipped(self, make_run):
        from framework.artifact_store.hashing import hash_payload as _hp

        body_bytes = b'["array", "not", "dict"]'
        art = _make_file_artifact(
            aid="v1",
            suffix=".json",
            modality="report",
            shape="verdict",
            hash_str=_hp(body_bytes),
        )
        _, run_dir = make_run(artifacts=[art], payloads={"r1/v1.json": body_bytes})
        snap = load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        assert "v1" not in snap.review_payloads


# ----- TestLoadRunSnapshotMisc -----


class TestLoadRunSnapshotMisc:
    def test_date_bucket_extracted_from_parent_name(self, make_run):
        _, run_dir = make_run(date="2099-12-31", run_id="rX")
        snap = load_run_snapshot(run_dir, include_payload_hash_check=False)
        assert snap.date_bucket == "2099-12-31"

    def test_date_bucket_none_when_parent_not_date_format(self, tmp_path):
        # Build a run dir whose parent is not a YYYY-MM-DD bucket.
        run_dir = tmp_path / "weird_parent" / "rX"
        run_dir.mkdir(parents=True)
        (run_dir / "run_summary.json").write_text(json.dumps({"status": "succeeded"}), encoding="utf-8")
        (run_dir / "_artifacts.json").write_text("[]", encoding="utf-8")
        snap = load_run_snapshot(run_dir, include_payload_hash_check=False)
        assert snap.date_bucket is None

    def test_run_id_taken_from_run_dir_basename(self, make_run):
        _, run_dir = make_run(run_id="my_special_run")
        snap = load_run_snapshot(run_dir, include_payload_hash_check=False)
        assert snap.run_id == "my_special_run"


# ----- TestRunSnapshotImmutability -----


class TestRunSnapshotImmutability:
    def test_run_snapshot_is_frozen(self):
        snap = RunSnapshot(
            run_dir=Path("/tmp"),
            run_id="r",
            date_bucket=None,
            run_summary={},
            artifacts={},
            checkpoints=[],
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.run_id = "changed"  # type: ignore[misc]


# ----- TestExceptionHierarchy -----


class TestExceptionHierarchy:
    def test_all_exceptions_inherit_from_base(self):
        assert issubclass(RunDirNotFound, ComparisonLoaderError)
        assert issubclass(RunDirAmbiguous, ComparisonLoaderError)
        assert issubclass(RunSnapshotCorrupt, ComparisonLoaderError)
        assert issubclass(PayloadMissingOnDisk, ComparisonLoaderError)
        assert issubclass(ComparisonLoaderError, Exception)

    def test_run_dir_not_found_message_includes_run_id(self):
        err = RunDirNotFound("my_run", Path("/some/root"))
        assert "my_run" in str(err)
        assert "/some/root" in str(err) or "some" in str(err)

    def test_run_dir_ambiguous_lists_matches(self):
        err = RunDirAmbiguous("r1", [Path("/a/2000-01-01/r1"), Path("/a/2000-01-02/r1")])
        msg = str(err)
        assert "r1" in msg
        assert "2000-01-01" in msg
        assert "2000-01-02" in msg

    def test_payload_missing_on_disk_carries_artifact_id(self):
        err = PayloadMissingOnDisk(Path("/run"), "img_0", Path("/run/img_0.bin"))
        assert err.artifact_id == "img_0"
        assert "img_0" in str(err)


# ----- TestPayloadFilePathTraversal (M1 / M4 from Review Fix Pack) -----
#
# file_path traversal escape (e.g. "../../escape.bin") is a data-integrity
# violation of _artifacts.json, NOT a missing-payload condition. It must
# raise RunSnapshotCorrupt regardless of include_payload_hash_check / strict.


def _make_traversal_artifact(*, aid: str = "evil", file_path: str = "../../escape.bin") -> Artifact:
    return Artifact(
        artifact_id=aid,
        artifact_type=ArtifactType(modality="image", shape="png", display_name="image.png"),
        role=ArtifactRole.intermediate,
        format="png",
        mime_type="image/png",
        payload_ref=PayloadRef(kind=PayloadKind.file, file_path=file_path, size_bytes=4),
        schema_version="1.0.0",
        hash="x",
        producer=ProducerRef(run_id="r1", step_id="s1"),
        created_at=datetime(2000, 1, 1, tzinfo=UTC),
    )


class TestPayloadFilePathTraversal:
    def test_traversal_raises_corrupt_under_strict_true(self, make_run):
        _, run_dir = make_run(artifacts=[_make_traversal_artifact()])
        with pytest.raises(RunSnapshotCorrupt) as excinfo:
            load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        msg = str(excinfo.value).lower()
        assert ("traversal" in msg) or ("escape" in msg)

    def test_traversal_raises_corrupt_under_strict_false(self, make_run):
        # Even non-strict mode must surface traversal as corrupt — this is a
        # security / data-integrity issue, NOT a "soft missing payload".
        _, run_dir = make_run(artifacts=[_make_traversal_artifact()])
        with pytest.raises(RunSnapshotCorrupt):
            load_run_snapshot(run_dir, include_payload_hash_check=True, strict=False)

    def test_traversal_raises_corrupt_when_hash_check_disabled(self, make_run):
        # The pre-validation pass must catch traversal even when neither the
        # hash-check loop nor the review-payloads loop would otherwise inspect
        # this artifact (image is non-report, hash check is off).
        _, run_dir = make_run(artifacts=[_make_traversal_artifact()])
        with pytest.raises(RunSnapshotCorrupt):
            load_run_snapshot(run_dir, include_payload_hash_check=False)

    def test_traversal_not_misreported_as_payload_missing(self, make_run):
        _, run_dir = make_run(artifacts=[_make_traversal_artifact()])
        # PayloadMissingOnDisk is a sibling exception in ComparisonLoaderError;
        # asserting the negative branch protects against future regressions
        # where someone re-collapses the two paths.
        with pytest.raises(RunSnapshotCorrupt):
            load_run_snapshot(run_dir, include_payload_hash_check=True, strict=True)
        # Sanity: same fixture without traversal raises PayloadMissingOnDisk
        # under strict=True, confirming the two paths really diverge.
        plain = _make_file_artifact(aid="plain")  # file_path="r1/plain.bin"
        _, plain_run_dir = make_run(artifacts=[plain])  # no payload written
        with pytest.raises(PayloadMissingOnDisk):
            load_run_snapshot(plain_run_dir, include_payload_hash_check=True, strict=True)


# ----- TestLoaderImportFence (H3 from Review Fix Pack) -----
#
# Importing framework.comparison.loader is allowed to pull in framework.core
# (schema) and framework.artifact_store.hashing (byte-hash recompute). It MUST
# NOT pull in any execution-layer module: runtime / providers / review_engine
# / ue_bridge / workflows / observability / server / schemas / pricing_probe.
#
# Run in a subprocess so tests/conftest.py — which auto-loads
# framework.providers.model_registry — cannot create a false positive.


_FORBIDDEN_FRAMEWORK_MODULES_LOADER = (
    "framework.runtime",
    "framework.providers",
    "framework.review_engine",
    "framework.ue_bridge",
    "framework.workflows",
    "framework.observability",
    "framework.server",
    "framework.schemas",
    "framework.pricing_probe",
)


class TestLoaderImportFence:
    def test_loader_import_does_not_pull_in_execution_layers(self) -> None:
        src_dir = Path(__file__).resolve().parents[2] / "src"
        assert (
            src_dir / "framework" / "comparison" / "loader.py"
        ).is_file(), f"cannot locate framework.comparison.loader under {src_dir}"

        probe = (
            "import sys\n"
            f"sys.path.insert(0, {str(src_dir)!r})\n"
            "import framework.comparison.loader  # noqa: F401\n"
            "import json\n"
            "loaded = sorted(m for m in sys.modules if m.startswith('framework'))\n"
            "print(json.dumps(loaded))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            check=True,
        )
        loaded = json.loads(result.stdout.strip())

        for forbidden in _FORBIDDEN_FRAMEWORK_MODULES_LOADER:
            leaked = [m for m in loaded if m == forbidden or m.startswith(forbidden + ".")]
            assert not leaked, (
                f"framework.comparison.loader transitively imported forbidden module(s): {leaked}. "
                f"The loader must stay a read-only consumer outside the Run lifecycle."
            )

        # Sanity: the loader module itself, its package, and its allowed
        # framework.core / framework.artifact_store.hashing dependencies should
        # be present.
        assert "framework.comparison" in loaded
        assert "framework.comparison.loader" in loaded
        assert "framework.core.artifact" in loaded
        assert "framework.core.runtime" in loaded
        assert "framework.artifact_store.hashing" in loaded
