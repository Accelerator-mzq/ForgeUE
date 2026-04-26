"""Unit tests for framework.comparison.diff_engine.

Strategy: construct RunSnapshot dataclasses directly (no disk I/O, no loader
involvement). diff_engine is a pure function on RunSnapshot data — so the test
fixtures bypass the loader entirely and exercise compare() against handcrafted
snapshots that cover every artifact / verdict / metric diff branch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from framework.comparison.diff_engine import compare
from framework.comparison.loader import RunSnapshot
from framework.comparison.models import (
    ArtifactDiff,
    MetricDiff,
    RunComparisonInput,
    RunComparisonReport,
    StepDiff,
    VerdictDiff,
)
from framework.core.artifact import (
    Artifact,
    ArtifactType,
    Lineage,
    PayloadRef,
    ProducerRef,
    ValidationCheck,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, PayloadKind
from framework.core.runtime import Checkpoint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_input(
    *,
    baseline_run_id: str = "run_a",
    candidate_run_id: str = "run_b",
) -> RunComparisonInput:
    return RunComparisonInput(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        artifact_root=Path("./artifacts"),
    )


def _make_artifact(
    *,
    aid: str = "a1",
    run_id: str = "r1",
    step_id: str = "s1",
    modality: str = "image",
    shape: str = "png",
    payload_kind: PayloadKind = PayloadKind.file,
    file_path: str | None = None,
    inline_value: Any | None = None,
    hash_str: str = "h_default",
    role: ArtifactRole = ArtifactRole.intermediate,
    fmt: str = "png",
    mime_type: str = "image/png",
    schema_version: str = "1.0.0",
    validation_status: str = "pending",
    validation_warnings: list[str] | None = None,
    validation_errors: list[str] | None = None,
    validation_checks: list[ValidationCheck] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    lineage_kwargs: dict[str, Any] | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> Artifact:
    if payload_kind == PayloadKind.file:
        ref = PayloadRef(
            kind=PayloadKind.file,
            file_path=file_path or f"{run_id}/{aid}.bin",
            size_bytes=4,
        )
    elif payload_kind == PayloadKind.inline:
        ref = PayloadRef(
            kind=PayloadKind.inline,
            inline_value=inline_value if inline_value is not None else {"v": 1},
            size_bytes=8,
        )
    else:
        ref = PayloadRef(kind=PayloadKind.blob, blob_key=f"blob_{aid}", size_bytes=4)
    return Artifact(
        artifact_id=aid,
        artifact_type=ArtifactType(modality=modality, shape=shape, display_name=f"{modality}.{shape}"),
        role=role,
        format=fmt,
        mime_type=mime_type,
        payload_ref=ref,
        schema_version=schema_version,
        hash=hash_str,
        producer=ProducerRef(run_id=run_id, step_id=step_id, provider=provider, model=model),
        lineage=Lineage(**(lineage_kwargs or {})),
        metadata=metadata or {},
        tags=tags or [],
        validation=ValidationRecord(
            status=validation_status,  # type: ignore[arg-type]
            checks=validation_checks or [],
            warnings=validation_warnings or [],
            errors=validation_errors or [],
        ),
        created_at=datetime(2000, 1, 1, tzinfo=UTC),
    )


def _make_checkpoint(
    *,
    run_id: str = "r1",
    step_id: str = "s1",
    artifact_ids: list[str] | None = None,
    artifact_hashes: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
) -> Checkpoint:
    return Checkpoint(
        checkpoint_id=f"cp_{run_id}_{step_id}",
        run_id=run_id,
        step_id=step_id,
        artifact_ids=artifact_ids or [],
        artifact_hashes=artifact_hashes or [],
        input_hash=f"ih_{step_id}",
        completed_at=datetime(2000, 1, 1, tzinfo=UTC),
        metrics=metrics or {},
    )


def _make_snapshot(
    *,
    run_id: str = "r1",
    date_bucket: str | None = "2000-01-01",
    status: str = "succeeded",
    artifacts: list[Artifact] = (),
    checkpoints: list[Checkpoint] = (),
    visited_steps: list[str] | None = None,
    failure_events: list[dict[str, Any]] | None = None,
    revise_events: list[dict[str, Any]] | None = None,
    review_payloads: dict[str, dict[str, Any]] | None = None,
    payload_hash_mismatches: dict[str, tuple[str | None, str | None]] | None = None,
    payload_missing_on_disk: set[str] | None = None,
    extra_summary: dict[str, Any] | None = None,
) -> RunSnapshot:
    summary: dict[str, Any] = {
        "run_id": run_id,
        "status": status,
        "visited_steps": visited_steps or [],
        "failure_events": failure_events or [],
        "revise_events": revise_events or [],
    }
    if extra_summary:
        summary.update(extra_summary)
    return RunSnapshot(
        run_dir=Path("/fake") / (date_bucket or "_no_bucket") / run_id,
        run_id=run_id,
        date_bucket=date_bucket,
        run_summary=summary,
        artifacts={a.artifact_id: a for a in artifacts},
        checkpoints=list(checkpoints),
        review_payloads=review_payloads or {},
        payload_hash_mismatches=payload_hash_mismatches or {},
        payload_missing_on_disk=payload_missing_on_disk or set(),
    )


_FIXED_GEN_AT = datetime(2000, 1, 1, 12, 0, 0, tzinfo=UTC)


def _run_compare(baseline: RunSnapshot, candidate: RunSnapshot, **kwargs: Any) -> RunComparisonReport:
    return compare(
        _make_input(),
        baseline,
        candidate,
        generated_at=_FIXED_GEN_AT,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# TestCompareIdentical
# ---------------------------------------------------------------------------


class TestCompareIdentical:
    def test_identical_snapshots_yield_all_unchanged(self) -> None:
        art = _make_artifact(aid="a1", hash_str="H1")
        b = _make_snapshot(artifacts=[art])
        c = _make_snapshot(artifacts=[art])
        report = _run_compare(b, c)
        assert report.status_match is True
        assert len(report.step_diffs) == 1
        sd = report.step_diffs[0]
        assert sd.step_id == "s1"
        assert len(sd.artifact_diffs) == 1
        assert sd.artifact_diffs[0].kind == "unchanged"
        assert sd.artifact_diffs[0].baseline_hash == "H1"
        assert sd.artifact_diffs[0].candidate_hash == "H1"
        assert report.summary_counts["artifact:unchanged"] == 1
        assert report.summary_counts["steps_with_artifact_change"] == 0


# ---------------------------------------------------------------------------
# TestCompareHashContentChange
# ---------------------------------------------------------------------------


class TestCompareHashContentChange:
    def test_hash_differs_yields_content_changed_with_both_hashes(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HB")
        c_art = _make_artifact(aid="a1", hash_str="HC")
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "content_changed"
        assert ad.baseline_hash == "HB"
        assert ad.candidate_hash == "HC"
        assert ad.note is None  # no tampered note when both sides hash-clean


# ---------------------------------------------------------------------------
# TestCompareMetadataOnly
# ---------------------------------------------------------------------------


class TestCompareMetadataOnly:
    def test_same_hash_different_format_yields_metadata_only(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HX", fmt="png")
        c_art = _make_artifact(aid="a1", hash_str="HX", fmt="webp")
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "metadata_only"
        assert ad.baseline_hash == "HX"
        assert ad.candidate_hash == "HX"
        assert ad.metadata_delta == {"format": ("png", "webp")}

    def test_metadata_dict_shallow_diff(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HX", metadata={"width": 512})
        c_art = _make_artifact(aid="a1", hash_str="HX", metadata={"width": 1024, "added": True})
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "metadata_only"
        assert ad.metadata_delta["metadata.width"] == (512, 1024)
        assert ad.metadata_delta["metadata.added"] == (None, True)

    def test_tags_normalized_to_sorted_tuple(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HX", tags=["alpha", "beta"])
        c_art = _make_artifact(aid="a1", hash_str="HX", tags=["beta", "alpha"])
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        # Same after sort -> no diff -> kind="unchanged"
        assert ad.kind == "unchanged"

    def test_tags_actually_different_surfaces_in_metadata_delta(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HX", tags=["alpha"])
        c_art = _make_artifact(aid="a1", hash_str="HX", tags=["beta"])
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "metadata_only"
        assert ad.metadata_delta["tags"] == (("alpha",), ("beta",))

    def test_producer_model_change_surfaces(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HX", model="qwen-vl-max")
        c_art = _make_artifact(aid="a1", hash_str="HX", model="qwen-vl-plus")
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "metadata_only"
        assert ad.metadata_delta["producer.model"] == ("qwen-vl-max", "qwen-vl-plus")


# ---------------------------------------------------------------------------
# TestCompareLineageDelta
# ---------------------------------------------------------------------------


class TestCompareLineageDelta:
    def test_lineage_selected_by_verdict_id_change(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HX", lineage_kwargs={"selected_by_verdict_id": "v1"})
        c_art = _make_artifact(aid="a1", hash_str="HX", lineage_kwargs={"selected_by_verdict_id": "v2"})
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "metadata_only"
        assert ad.lineage_delta == {"selected_by_verdict_id": ("v1", "v2")}

    def test_lineage_source_artifact_ids_normalized_sorted(self) -> None:
        b_art = _make_artifact(
            aid="a1",
            hash_str="HX",
            lineage_kwargs={"source_artifact_ids": ["x", "y"]},
        )
        c_art = _make_artifact(
            aid="a1",
            hash_str="HX",
            lineage_kwargs={"source_artifact_ids": ["y", "x"]},
        )
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        # Same sorted -> no diff -> kind="unchanged"
        assert ad.kind == "unchanged"

    def test_lineage_change_with_hash_change_emits_both_deltas(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HB", lineage_kwargs={"transformation_kind": "T1"})
        c_art = _make_artifact(aid="a1", hash_str="HC", lineage_kwargs={"transformation_kind": "T2"})
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "content_changed"
        assert ad.lineage_delta == {"transformation_kind": ("T1", "T2")}


# ---------------------------------------------------------------------------
# TestCompareMissing
# ---------------------------------------------------------------------------


class TestCompareMissing:
    def test_baseline_only_artifact_marked_missing_in_candidate(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HB")
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "missing_in_candidate"
        assert ad.baseline_hash == "HB"
        assert ad.candidate_hash is None

    def test_candidate_only_artifact_marked_missing_in_baseline(self) -> None:
        c_art = _make_artifact(aid="a1", hash_str="HC")
        report = _run_compare(
            _make_snapshot(artifacts=[]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "missing_in_baseline"
        assert ad.baseline_hash is None
        assert ad.candidate_hash == "HC"


# ---------------------------------------------------------------------------
# TestComparePayloadMissingOnDisk
# ---------------------------------------------------------------------------


class TestComparePayloadMissingOnDisk:
    def test_baseline_payload_missing_on_disk(self) -> None:
        art = _make_artifact(aid="a1", hash_str="H1")
        b = _make_snapshot(artifacts=[art], payload_missing_on_disk={"a1"})
        c = _make_snapshot(artifacts=[art])
        report = _run_compare(b, c)
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "payload_missing_on_disk"
        assert ad.note is not None
        assert "baseline" in ad.note
        assert "candidate" not in ad.note

    def test_both_sides_payload_missing(self) -> None:
        art = _make_artifact(aid="a1", hash_str="H1")
        b = _make_snapshot(artifacts=[art], payload_missing_on_disk={"a1"})
        c = _make_snapshot(artifacts=[art], payload_missing_on_disk={"a1"})
        report = _run_compare(b, c)
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "payload_missing_on_disk"
        assert ad.note is not None
        assert "baseline" in ad.note and "candidate" in ad.note


# ---------------------------------------------------------------------------
# TestComparePayloadHashMismatch
# ---------------------------------------------------------------------------


class TestComparePayloadHashMismatch:
    def test_baseline_hash_mismatch_yields_content_changed_with_note(self) -> None:
        art = _make_artifact(aid="a1", hash_str="H1")
        b = _make_snapshot(artifacts=[art], payload_hash_mismatches={"a1": ("H1", "H1_real")})
        c = _make_snapshot(artifacts=[art])
        report = _run_compare(b, c)
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "content_changed"
        assert ad.note is not None
        assert "baseline payload tampered" in ad.note
        assert "H1_real" in ad.note

    def test_both_sides_mismatch_emits_combined_note(self) -> None:
        art = _make_artifact(aid="a1", hash_str="H1")
        b = _make_snapshot(artifacts=[art], payload_hash_mismatches={"a1": ("H1", "H1_real_b")})
        c = _make_snapshot(artifacts=[art], payload_hash_mismatches={"a1": ("H1", "H1_real_c")})
        report = _run_compare(b, c)
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "content_changed"
        assert ad.note is not None
        assert "baseline payload tampered" in ad.note
        assert "candidate payload tampered" in ad.note

    def test_payload_missing_takes_precedence_over_hash_mismatch(self) -> None:
        # If the loader reported both payload_missing_on_disk AND
        # payload_hash_mismatch for the same aid (defensive: shouldn't happen
        # because hash check reads bytes, but be deterministic if it does),
        # missing-on-disk wins because we cannot meaningfully reason about
        # bytes that aren't there.
        art = _make_artifact(aid="a1", hash_str="H1")
        b = _make_snapshot(
            artifacts=[art],
            payload_missing_on_disk={"a1"},
            payload_hash_mismatches={"a1": ("H1", "H1_real")},
        )
        c = _make_snapshot(artifacts=[art])
        report = _run_compare(b, c)
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "payload_missing_on_disk"


# ---------------------------------------------------------------------------
# TestCompareVerdictDecisionChange
# ---------------------------------------------------------------------------


def _verdict_artifact(*, aid: str, step_id: str = "s_review") -> Artifact:
    return _make_artifact(
        aid=aid,
        step_id=step_id,
        modality="report",
        shape="verdict",
        fmt="json",
        mime_type="application/json",
        hash_str=f"hash_{aid}",
    )


class TestCompareVerdictDecisionChange:
    def test_decision_changed_kind(self) -> None:
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[v_art],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.9}},
        )
        c = _make_snapshot(
            artifacts=[v_art],
            review_payloads={"v1": {"decision": "revise", "confidence": 0.9}},
        )
        report = _run_compare(b, c)
        vd = report.step_diffs[0].verdict_diffs[0]
        assert vd.kind == "decision_changed"
        assert vd.baseline_decision == "approve"
        assert vd.candidate_decision == "revise"


# ---------------------------------------------------------------------------
# TestCompareVerdictConfidenceChange
# ---------------------------------------------------------------------------


class TestCompareVerdictConfidenceChange:
    def test_confidence_changed_kind(self) -> None:
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[v_art],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.85}},
        )
        c = _make_snapshot(
            artifacts=[v_art],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.55}},
        )
        report = _run_compare(b, c)
        vd = report.step_diffs[0].verdict_diffs[0]
        assert vd.kind == "confidence_changed"
        assert vd.baseline_confidence == pytest.approx(0.85)
        assert vd.candidate_confidence == pytest.approx(0.55)

    def test_confidence_within_epsilon_treated_as_unchanged(self) -> None:
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[v_art],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.9000000000001}},
        )
        c = _make_snapshot(
            artifacts=[v_art],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.9}},
        )
        report = _run_compare(b, c)
        vd = report.step_diffs[0].verdict_diffs[0]
        assert vd.kind == "unchanged"


# ---------------------------------------------------------------------------
# TestCompareVerdictSelectedChange
# ---------------------------------------------------------------------------


class TestCompareVerdictSelectedChange:
    def test_selected_candidates_changed_added_and_removed(self) -> None:
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[v_art],
            review_payloads={
                "v1": {
                    "decision": "approve_one",
                    "confidence": 0.8,
                    "selected_candidate_ids": ["c0", "c1"],
                }
            },
        )
        c = _make_snapshot(
            artifacts=[v_art],
            review_payloads={
                "v1": {
                    "decision": "approve_one",
                    "confidence": 0.8,
                    "selected_candidate_ids": ["c1", "c2"],
                }
            },
        )
        report = _run_compare(b, c)
        vd = report.step_diffs[0].verdict_diffs[0]
        assert vd.kind == "selected_candidates_changed"
        assert vd.selected_delta == {"added": ["c2"], "removed": ["c0"]}

    def test_rejected_candidates_change_only_yields_selected_candidates_changed(
        self,
    ) -> None:
        # Selected sets identical, but rejected sets differ. Per design.md §4
        # and tasks.md §3.3, rejected_candidate_ids divergence MUST surface as
        # a verdict diff (folded into selected_candidates_changed because
        # VerdictDiffKind is a closed Literal at 6 values).
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[v_art],
            review_payloads={
                "v1": {
                    "decision": "approve_one",
                    "confidence": 0.8,
                    "selected_candidate_ids": ["c1"],
                    "rejected_candidate_ids": ["c0", "c2"],
                }
            },
        )
        c = _make_snapshot(
            artifacts=[v_art],
            review_payloads={
                "v1": {
                    "decision": "approve_one",
                    "confidence": 0.8,
                    "selected_candidate_ids": ["c1"],
                    "rejected_candidate_ids": ["c0", "c3"],
                }
            },
        )
        report = _run_compare(b, c)
        vd = report.step_diffs[0].verdict_diffs[0]
        assert vd.kind == "selected_candidates_changed"
        assert vd.selected_delta is not None
        # selected unchanged -> empty added / removed
        assert vd.selected_delta["added"] == []
        assert vd.selected_delta["removed"] == []
        # rejected delta carried via dedicated keys
        assert vd.selected_delta["rejected_added"] == ["c3"]
        assert vd.selected_delta["rejected_removed"] == ["c2"]

    def test_selected_and_rejected_both_change(self) -> None:
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[v_art],
            review_payloads={
                "v1": {
                    "decision": "approve_one",
                    "confidence": 0.8,
                    "selected_candidate_ids": ["c1"],
                    "rejected_candidate_ids": ["c0"],
                }
            },
        )
        c = _make_snapshot(
            artifacts=[v_art],
            review_payloads={
                "v1": {
                    "decision": "approve_one",
                    "confidence": 0.8,
                    "selected_candidate_ids": ["c2"],
                    "rejected_candidate_ids": ["c1"],
                }
            },
        )
        report = _run_compare(b, c)
        vd = report.step_diffs[0].verdict_diffs[0]
        assert vd.kind == "selected_candidates_changed"
        assert vd.selected_delta is not None
        assert vd.selected_delta["added"] == ["c2"]
        assert vd.selected_delta["removed"] == ["c1"]
        assert vd.selected_delta["rejected_added"] == ["c1"]
        assert vd.selected_delta["rejected_removed"] == ["c0"]

    def test_rejected_unchanged_no_extra_keys(self) -> None:
        # When rejected sets match across sides, the rejected_added /
        # rejected_removed keys MUST NOT appear in selected_delta — keeps
        # the dict compact for reporters that key-introspect.
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[v_art],
            review_payloads={
                "v1": {
                    "decision": "approve_one",
                    "confidence": 0.8,
                    "selected_candidate_ids": ["c0"],
                    "rejected_candidate_ids": ["c1"],
                }
            },
        )
        c = _make_snapshot(
            artifacts=[v_art],
            review_payloads={
                "v1": {
                    "decision": "approve_one",
                    "confidence": 0.8,
                    "selected_candidate_ids": ["c2"],
                    "rejected_candidate_ids": ["c1"],
                }
            },
        )
        report = _run_compare(b, c)
        vd = report.step_diffs[0].verdict_diffs[0]
        assert vd.kind == "selected_candidates_changed"
        assert vd.selected_delta is not None
        assert "rejected_added" not in vd.selected_delta
        assert "rejected_removed" not in vd.selected_delta

    def test_only_rejected_change_unchanged_when_selected_kind_disabled(self) -> None:
        # Sanity: identical rejected and identical selected -> kind="unchanged"
        # (no false positive from the new rejected branch).
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[v_art],
            review_payloads={
                "v1": {
                    "decision": "approve_one",
                    "confidence": 0.8,
                    "selected_candidate_ids": ["c0"],
                    "rejected_candidate_ids": ["c1"],
                }
            },
        )
        c = _make_snapshot(
            artifacts=[v_art],
            review_payloads={
                "v1": {
                    "decision": "approve_one",
                    "confidence": 0.8,
                    "selected_candidate_ids": ["c0"],
                    "rejected_candidate_ids": ["c1"],
                }
            },
        )
        report = _run_compare(b, c)
        vd = report.step_diffs[0].verdict_diffs[0]
        assert vd.kind == "unchanged"


# ---------------------------------------------------------------------------
# TestCompareSingleSideIntegrityNote (P2 fix: missing_in_* + tamper signal)
# ---------------------------------------------------------------------------


class TestCompareSingleSideIntegrityNote:
    def test_missing_in_baseline_with_candidate_hash_mismatch_carries_note(
        self,
    ) -> None:
        # Artifact appears only on candidate side AND the loader recorded a
        # payload tamper warning. The diff must surface that warning via note
        # so the data-integrity contract isn't silently downgraded to a plain
        # missing_in_baseline.
        c_art = _make_artifact(aid="v1", hash_str="HC")
        b = _make_snapshot(artifacts=[])
        c = _make_snapshot(
            artifacts=[c_art],
            payload_hash_mismatches={"v1": ("HC", "HC_real")},
        )
        report = _run_compare(b, c)
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "missing_in_baseline"
        assert ad.candidate_hash == "HC"
        assert ad.note is not None
        assert "candidate payload tampered" in ad.note
        assert "HC_real" in ad.note

    def test_missing_in_candidate_with_baseline_hash_mismatch_carries_note(
        self,
    ) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HB")
        b = _make_snapshot(
            artifacts=[b_art],
            payload_hash_mismatches={"a1": ("HB", "HB_real")},
        )
        c = _make_snapshot(artifacts=[])
        report = _run_compare(b, c)
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "missing_in_candidate"
        assert ad.baseline_hash == "HB"
        assert ad.note is not None
        assert "baseline payload tampered" in ad.note
        assert "HB_real" in ad.note

    def test_missing_in_baseline_with_candidate_payload_missing_on_disk(
        self,
    ) -> None:
        # Single-sided artifact whose payload is also recorded as
        # missing-on-disk by the loader. Note should surface that signal.
        c_art = _make_artifact(aid="a1", hash_str="HC")
        b = _make_snapshot(artifacts=[])
        c = _make_snapshot(
            artifacts=[c_art],
            payload_missing_on_disk={"a1"},
        )
        report = _run_compare(b, c)
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "missing_in_baseline"
        assert ad.note is not None
        assert "candidate payload missing on disk" in ad.note

    def test_missing_in_baseline_clean_no_note(self) -> None:
        # Baseline-clean missing case: no tamper, no on-disk-missing.
        # note must remain None to avoid false positive signals.
        c_art = _make_artifact(aid="a1", hash_str="HC")
        b = _make_snapshot(artifacts=[])
        c = _make_snapshot(artifacts=[c_art])
        report = _run_compare(b, c)
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "missing_in_baseline"
        assert ad.note is None


# ---------------------------------------------------------------------------
# TestCompareVerdictMissing
# ---------------------------------------------------------------------------


class TestCompareVerdictMissing:
    def test_verdict_artifact_only_in_candidate(self) -> None:
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(artifacts=[])
        c = _make_snapshot(
            artifacts=[v_art],
            review_payloads={"v1": {"decision": "reject", "confidence": 0.4}},
        )
        report = _run_compare(b, c)
        # Verdict artifact appears in candidate only -> ArtifactDiff missing_in_baseline
        # AND VerdictDiff missing_in_baseline (since baseline body is None).
        sd = report.step_diffs[0]
        assert any(ad.kind == "missing_in_baseline" for ad in sd.artifact_diffs)
        assert len(sd.verdict_diffs) == 1
        assert sd.verdict_diffs[0].kind == "missing_in_baseline"
        assert sd.verdict_diffs[0].candidate_decision == "reject"

    def test_verdict_artifact_only_in_baseline(self) -> None:
        # t4 (Task 3 Review Fix Pack): mirror of only_in_candidate. Guards
        # the symmetric branch from one-directional regression.
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[v_art],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.9}},
        )
        c = _make_snapshot(artifacts=[])
        report = _run_compare(b, c)
        sd = report.step_diffs[0]
        assert any(ad.kind == "missing_in_candidate" for ad in sd.artifact_diffs)
        assert len(sd.verdict_diffs) == 1
        assert sd.verdict_diffs[0].kind == "missing_in_candidate"
        assert sd.verdict_diffs[0].baseline_decision == "approve"
        assert sd.verdict_diffs[0].baseline_confidence == pytest.approx(0.9)

    def test_review_payload_loader_could_not_extract_skipped(self) -> None:
        # Both sides have the verdict artifact recorded but neither side has a
        # parseable review_payloads body (loader best-effort failed). The diff
        # engine emits no VerdictDiff to avoid a misleading missing_in_*.
        v_art = _verdict_artifact(aid="v1")
        b = _make_snapshot(artifacts=[v_art], review_payloads={})
        c = _make_snapshot(artifacts=[v_art], review_payloads={})
        report = _run_compare(b, c)
        assert report.step_diffs[0].verdict_diffs == []


# ---------------------------------------------------------------------------
# TestCompareMultipleVerdictsPerStep
# ---------------------------------------------------------------------------


class TestCompareMultipleVerdictsPerStep:
    def test_two_verdicts_emit_two_diffs_sorted_by_aid(self) -> None:
        v1 = _verdict_artifact(aid="v_alpha")
        v2 = _verdict_artifact(aid="v_beta")
        b = _make_snapshot(
            artifacts=[v1, v2],
            review_payloads={
                "v_alpha": {"decision": "approve", "confidence": 0.8},
                "v_beta": {"decision": "approve", "confidence": 0.7},
            },
        )
        c = _make_snapshot(
            artifacts=[v1, v2],
            review_payloads={
                "v_alpha": {"decision": "reject", "confidence": 0.8},
                "v_beta": {"decision": "approve", "confidence": 0.7},
            },
        )
        report = _run_compare(b, c)
        sd = report.step_diffs[0]
        assert len(sd.verdict_diffs) == 2
        # Ordering by step_id (same here) then by ... actually VerdictDiff has
        # step_id only; the natural order is by aid (verdict artifact id).
        # verdict_diffs are emitted in artifact_id order (alpha < beta).
        kinds = [vd.kind for vd in sd.verdict_diffs]
        assert kinds == ["decision_changed", "unchanged"]


# ---------------------------------------------------------------------------
# TestCompareStepMetrics
# ---------------------------------------------------------------------------


class TestCompareStepMetrics:
    def test_step_cost_delta_and_pct(self) -> None:
        cp_b = _make_checkpoint(metrics={"cost_usd": 0.10})
        cp_c = _make_checkpoint(metrics={"cost_usd": 0.12})
        b = _make_snapshot(checkpoints=[cp_b])
        c = _make_snapshot(checkpoints=[cp_c])
        report = _run_compare(b, c)
        metrics = report.step_diffs[0].metric_diffs
        cost_diff = next(m for m in metrics if m.metric == "cost_usd")
        assert cost_diff.scope == "step"
        assert cost_diff.step_id == "s1"
        assert cost_diff.baseline_value == pytest.approx(0.10)
        assert cost_diff.candidate_value == pytest.approx(0.12)
        assert cost_diff.delta == pytest.approx(0.02)
        assert cost_diff.delta_pct == pytest.approx(20.0)

    def test_step_metric_only_one_side_present_emits_diff_with_none_delta(self) -> None:
        cp_b = _make_checkpoint(metrics={"cost_usd": 0.10})
        cp_c = _make_checkpoint(metrics={})  # no cost_usd
        b = _make_snapshot(checkpoints=[cp_b])
        c = _make_snapshot(checkpoints=[cp_c])
        report = _run_compare(b, c)
        cost = next(m for m in report.step_diffs[0].metric_diffs if m.metric == "cost_usd")
        assert cost.baseline_value == pytest.approx(0.10)
        assert cost.candidate_value is None
        assert cost.delta is None
        assert cost.delta_pct is None

    def test_step_wall_clock_s_included_at_step_level(self) -> None:
        cp_b = _make_checkpoint(metrics={"wall_clock_s": 1.0})
        cp_c = _make_checkpoint(metrics={"wall_clock_s": 1.5})
        b = _make_snapshot(checkpoints=[cp_b])
        c = _make_snapshot(checkpoints=[cp_c])
        report = _run_compare(b, c)
        metrics = report.step_diffs[0].metric_diffs
        wc = next(m for m in metrics if m.metric == "wall_clock_s")
        assert wc.scope == "step"
        assert wc.delta == pytest.approx(0.5)

    def test_step_metric_diffs_in_alphabetic_order(self) -> None:
        # M4 (Task 3 Review Fix Pack): metric iteration must be lexicographic
        # (matches plan §3 promise of stable sorted order). Verifies all 5
        # known step-level metrics emit in alphabetic order.
        cp_b = _make_checkpoint(
            metrics={
                "cost_usd": 0.1,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "wall_clock_s": 1.0,
            }
        )
        cp_c = _make_checkpoint(
            metrics={
                "cost_usd": 0.2,
                "prompt_tokens": 200,
                "completion_tokens": 100,
                "total_tokens": 300,
                "wall_clock_s": 2.0,
            }
        )
        b = _make_snapshot(checkpoints=[cp_b])
        c = _make_snapshot(checkpoints=[cp_c])
        report = _run_compare(b, c)
        metric_names = [m.metric for m in report.step_diffs[0].metric_diffs]
        assert metric_names == [
            "completion_tokens",
            "cost_usd",
            "prompt_tokens",
            "total_tokens",
            "wall_clock_s",
        ]


# ---------------------------------------------------------------------------
# TestCompareRunLevelMetrics
# ---------------------------------------------------------------------------


class TestCompareRunLevelMetrics:
    def test_run_level_cost_sums_across_checkpoints(self) -> None:
        cp_b1 = _make_checkpoint(step_id="s1", metrics={"cost_usd": 0.05})
        cp_b2 = _make_checkpoint(step_id="s2", metrics={"cost_usd": 0.05})
        cp_c1 = _make_checkpoint(step_id="s1", metrics={"cost_usd": 0.06})
        cp_c2 = _make_checkpoint(step_id="s2", metrics={"cost_usd": 0.06})
        b = _make_snapshot(checkpoints=[cp_b1, cp_b2])
        c = _make_snapshot(checkpoints=[cp_c1, cp_c2])
        report = _run_compare(b, c)
        run_metrics = report.run_level_metric_diffs
        cost = next(m for m in run_metrics if m.metric == "cost_usd")
        assert cost.scope == "run"
        assert cost.step_id is None
        assert cost.baseline_value == pytest.approx(0.10)
        assert cost.candidate_value == pytest.approx(0.12)
        assert cost.delta == pytest.approx(0.02)

    def test_run_metric_diffs_in_alphabetic_order_no_wall_clock(self) -> None:
        # M4 (Task 3 Review Fix Pack): run-level metric iteration is
        # lexicographic AND wall_clock_s is excluded (D5).
        cp_b = _make_checkpoint(
            metrics={
                "cost_usd": 0.1,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "wall_clock_s": 1.0,
            }
        )
        cp_c = _make_checkpoint(
            metrics={
                "cost_usd": 0.2,
                "prompt_tokens": 200,
                "completion_tokens": 100,
                "total_tokens": 300,
                "wall_clock_s": 2.0,
            }
        )
        b = _make_snapshot(checkpoints=[cp_b])
        c = _make_snapshot(checkpoints=[cp_c])
        report = _run_compare(b, c)
        metric_names = [m.metric for m in report.run_level_metric_diffs]
        assert metric_names == [
            "completion_tokens",
            "cost_usd",
            "prompt_tokens",
            "total_tokens",
        ]

    def test_run_level_excludes_wall_clock_s(self) -> None:
        cp_b = _make_checkpoint(metrics={"wall_clock_s": 1.0, "cost_usd": 0.1})
        cp_c = _make_checkpoint(metrics={"wall_clock_s": 1.5, "cost_usd": 0.1})
        b = _make_snapshot(checkpoints=[cp_b])
        c = _make_snapshot(checkpoints=[cp_c])
        report = _run_compare(b, c)
        names = [m.metric for m in report.run_level_metric_diffs]
        assert "wall_clock_s" not in names
        assert "cost_usd" in names


# ---------------------------------------------------------------------------
# TestCompareMetricEdgeCases
# ---------------------------------------------------------------------------


class TestCompareMetricEdgeCases:
    def test_baseline_zero_delta_pct_is_none(self) -> None:
        cp_b = _make_checkpoint(metrics={"cost_usd": 0.0})
        cp_c = _make_checkpoint(metrics={"cost_usd": 0.10})
        b = _make_snapshot(checkpoints=[cp_b])
        c = _make_snapshot(checkpoints=[cp_c])
        report = _run_compare(b, c)
        cost = next(m for m in report.step_diffs[0].metric_diffs if m.metric == "cost_usd")
        assert cost.delta == pytest.approx(0.10)
        assert cost.delta_pct is None

    def test_metric_absent_on_both_sides_no_diff_emitted(self) -> None:
        cp_b = _make_checkpoint(metrics={})
        cp_c = _make_checkpoint(metrics={})
        b = _make_snapshot(checkpoints=[cp_b])
        c = _make_snapshot(checkpoints=[cp_c])
        report = _run_compare(b, c)
        assert report.step_diffs[0].metric_diffs == []

    def test_bool_value_in_metrics_treated_as_none(self) -> None:
        # Defensive: cp.metrics could contain bool from a misbehaving runtime;
        # _get_metric_float should reject it (bool is technically int subclass).
        cp_b = _make_checkpoint(metrics={"cost_usd": True})  # type: ignore[dict-item]
        cp_c = _make_checkpoint(metrics={"cost_usd": 0.1})
        b = _make_snapshot(checkpoints=[cp_b])
        c = _make_snapshot(checkpoints=[cp_c])
        report = _run_compare(b, c)
        cost = next(m for m in report.step_diffs[0].metric_diffs if m.metric == "cost_usd")
        assert cost.baseline_value is None
        assert cost.candidate_value == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# TestCompareStepUnion
# ---------------------------------------------------------------------------


class TestCompareStepUnion:
    def test_step_union_sorted_and_missing_status_assigned(self) -> None:
        b_art = _make_artifact(aid="a1", step_id="s1")
        c_art = _make_artifact(aid="a1", step_id="s2")  # different step
        c_art_extra = _make_artifact(aid="a2", step_id="s3")
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art, c_art_extra]),
        )
        step_ids = [sd.step_id for sd in report.step_diffs]
        assert step_ids == ["s1", "s2", "s3"]
        # s1: baseline only -> status_baseline derived (not 'missing'),
        # status_candidate='missing'
        s1 = next(sd for sd in report.step_diffs if sd.step_id == "s1")
        assert s1.status_candidate == "missing"
        # s3: candidate only -> status_baseline='missing'
        s3 = next(sd for sd in report.step_diffs if sd.step_id == "s3")
        assert s3.status_baseline == "missing"


# ---------------------------------------------------------------------------
# TestCompareStatusMatch
# ---------------------------------------------------------------------------


class TestCompareStatusMatch:
    def test_status_match_true_when_both_succeeded(self) -> None:
        b = _make_snapshot(status="succeeded")
        c = _make_snapshot(status="succeeded")
        report = _run_compare(b, c)
        assert report.status_match is True

    def test_status_match_false_when_diverging(self) -> None:
        b = _make_snapshot(status="succeeded")
        c = _make_snapshot(status="failed")
        report = _run_compare(b, c)
        assert report.status_match is False
        assert report.baseline_run_meta["status"] == "succeeded"
        assert report.candidate_run_meta["status"] == "failed"


# ---------------------------------------------------------------------------
# TestCompareChosenModel
# ---------------------------------------------------------------------------


class TestCompareChosenModel:
    def test_chosen_model_picks_lex_smallest_when_multiple(self) -> None:
        # Two artifacts in same step, different models — chosen_model picks
        # the lexicographically smallest for determinism.
        a1 = _make_artifact(aid="a1", step_id="s1", model="qwen-vl-max")
        a2 = _make_artifact(aid="a2", step_id="s1", model="claude-opus-4-7")
        report = _run_compare(
            _make_snapshot(artifacts=[a1, a2]),
            _make_snapshot(artifacts=[a1, a2]),
        )
        sd = report.step_diffs[0]
        assert sd.chosen_model_baseline == "claude-opus-4-7"
        assert sd.chosen_model_candidate == "claude-opus-4-7"

    def test_chosen_model_none_when_no_producer_model(self) -> None:
        a1 = _make_artifact(aid="a1", model=None)
        report = _run_compare(
            _make_snapshot(artifacts=[a1]),
            _make_snapshot(artifacts=[a1]),
        )
        sd = report.step_diffs[0]
        assert sd.chosen_model_baseline is None
        assert sd.chosen_model_candidate is None

    def test_chosen_model_differs_between_sides(self) -> None:
        b_art = _make_artifact(aid="a1", model="model_b")
        c_art = _make_artifact(aid="a1", model="model_c", hash_str="HC")
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        sd = report.step_diffs[0]
        assert sd.chosen_model_baseline == "model_b"
        assert sd.chosen_model_candidate == "model_c"


# ---------------------------------------------------------------------------
# TestCompareSummaryCounts
# ---------------------------------------------------------------------------


class TestCompareSummaryCounts:
    def test_summary_counts_use_kind_prefixes(self) -> None:
        a1 = _make_artifact(aid="a1", hash_str="HX")  # unchanged
        b_a2 = _make_artifact(aid="a2", hash_str="HB2")
        c_a2 = _make_artifact(aid="a2", hash_str="HC2")  # content_changed
        b = _make_snapshot(artifacts=[a1, b_a2])
        c = _make_snapshot(artifacts=[a1, c_a2])
        report = _run_compare(b, c)
        sc = report.summary_counts
        assert sc["artifact:unchanged"] == 1
        assert sc["artifact:content_changed"] == 1
        assert sc["steps_total"] == 1
        assert sc["steps_with_artifact_change"] == 1
        assert sc["steps_with_verdict_change"] == 0

    def test_summary_counts_separates_artifact_and_verdict_unchanged(self) -> None:
        # Both an unchanged artifact and an unchanged verdict — the prefixed
        # keys must not collide.
        a1 = _make_artifact(aid="a1", hash_str="HX")
        v1 = _verdict_artifact(aid="v1", step_id="s1")
        b = _make_snapshot(
            artifacts=[a1, v1],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.9}},
        )
        c = _make_snapshot(
            artifacts=[a1, v1],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.9}},
        )
        report = _run_compare(b, c)
        sc = report.summary_counts
        assert sc["artifact:unchanged"] == 2  # a1 + v1 (verdict art is also an artifact)
        assert sc["verdict:unchanged"] == 1


# ---------------------------------------------------------------------------
# TestCompareDeterminism
# ---------------------------------------------------------------------------


class TestCompareDeterminism:
    def test_compare_is_deterministic_given_same_inputs(self) -> None:
        a1 = _make_artifact(aid="a1", hash_str="HB")
        a2 = _make_artifact(aid="a1", hash_str="HC")
        v1 = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[a1, v1],
            checkpoints=[_make_checkpoint(metrics={"cost_usd": 0.1})],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.9}},
        )
        c = _make_snapshot(
            artifacts=[a2, v1],
            checkpoints=[_make_checkpoint(metrics={"cost_usd": 0.12})],
            review_payloads={"v1": {"decision": "revise", "confidence": 0.7}},
        )
        r1 = _run_compare(b, c)
        r2 = _run_compare(b, c)
        assert r1.model_dump_json() == r2.model_dump_json()


# ---------------------------------------------------------------------------
# TestCompareDoesNotMutateInputs
# ---------------------------------------------------------------------------


class TestCompareDoesNotMutateInputs:
    def test_compare_does_not_mutate_baseline_or_candidate(self) -> None:
        a1 = _make_artifact(aid="a1", hash_str="HB")
        a2 = _make_artifact(aid="a1", hash_str="HC")
        v1 = _verdict_artifact(aid="v1")
        b = _make_snapshot(
            artifacts=[a1, v1],
            checkpoints=[_make_checkpoint(metrics={"cost_usd": 0.1})],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.9}},
            payload_missing_on_disk={"a1"},
            payload_hash_mismatches={"a1": ("HB", "HB_real")},
        )
        c = _make_snapshot(
            artifacts=[a2, v1],
            review_payloads={"v1": {"decision": "approve", "confidence": 0.9}},
        )

        b_artifacts_snapshot = dict(b.artifacts)
        b_review_snapshot = {k: dict(v) for k, v in b.review_payloads.items()}
        b_missing_snapshot = set(b.payload_missing_on_disk)
        b_mismatch_snapshot = dict(b.payload_hash_mismatches)
        b_summary_snapshot = dict(b.run_summary)
        b_checkpoints_snapshot = list(b.checkpoints)
        c_artifacts_snapshot = dict(c.artifacts)
        c_review_snapshot = {k: dict(v) for k, v in c.review_payloads.items()}

        _run_compare(b, c)

        assert b.artifacts == b_artifacts_snapshot
        assert b.review_payloads == b_review_snapshot
        assert b.payload_missing_on_disk == b_missing_snapshot
        assert b.payload_hash_mismatches == b_mismatch_snapshot
        assert b.run_summary == b_summary_snapshot
        assert b.checkpoints == b_checkpoints_snapshot
        assert c.artifacts == c_artifacts_snapshot
        assert c.review_payloads == c_review_snapshot


# ---------------------------------------------------------------------------
# TestCompareReportSchemaVersionLocked
# ---------------------------------------------------------------------------


class TestCompareReportSchemaVersionLocked:
    def test_report_schema_version_is_one(self) -> None:
        report = _run_compare(_make_snapshot(), _make_snapshot())
        assert report.schema_version == "1"


# ---------------------------------------------------------------------------
# TestCompareEmptySnapshots
# ---------------------------------------------------------------------------


class TestCompareEmptySnapshots:
    def test_two_empty_snapshots_yield_no_step_diffs(self) -> None:
        b = _make_snapshot()
        c = _make_snapshot()
        report = _run_compare(b, c)
        assert report.step_diffs == []
        assert report.run_level_metric_diffs == []
        assert report.summary_counts["steps_total"] == 0
        assert report.summary_counts["steps_with_artifact_change"] == 0
        assert report.summary_counts["steps_with_verdict_change"] == 0
        assert report.status_match is True


# ---------------------------------------------------------------------------
# TestCompareGeneratedAt
# ---------------------------------------------------------------------------


class TestCompareGeneratedAt:
    def test_generated_at_injection_used_verbatim(self) -> None:
        fixed = datetime(2099, 6, 15, 9, 30, 0, tzinfo=UTC)
        report = compare(_make_input(), _make_snapshot(), _make_snapshot(), generated_at=fixed)
        assert report.generated_at == fixed

    def test_generated_at_default_is_recent_utc(self) -> None:
        before = datetime.now(UTC)
        report = compare(_make_input(), _make_snapshot(), _make_snapshot())
        after = datetime.now(UTC)
        assert before <= report.generated_at <= after


# ---------------------------------------------------------------------------
# TestCompareStepStatusDerivation
# ---------------------------------------------------------------------------


class TestCompareStepStatusDerivation:
    def test_status_failed_takes_priority_over_succeeded(self) -> None:
        a1 = _make_artifact(aid="a1", step_id="s_x")
        cp = _make_checkpoint(step_id="s_x")
        snap = _make_snapshot(
            artifacts=[a1],
            checkpoints=[cp],  # would normally yield 'succeeded'
            failure_events=[{"step_id": "s_x", "mode": "provider_timeout"}],
        )
        report = _run_compare(snap, _make_snapshot(artifacts=[a1], checkpoints=[cp]))
        sd = report.step_diffs[0]
        assert sd.status_baseline == "failed"
        assert sd.status_candidate == "succeeded"

    def test_status_revised_when_only_revise_event(self) -> None:
        a1 = _make_artifact(aid="a1", step_id="s_x")
        snap = _make_snapshot(
            artifacts=[a1],
            revise_events=[{"step_id": "s_x"}],
        )
        report = _run_compare(snap, _make_snapshot(artifacts=[a1]))
        sd = report.step_diffs[0]
        assert sd.status_baseline == "revised"

    def test_status_visited_when_in_visited_steps_only(self) -> None:
        # No artifact, no checkpoint, but visited_steps contains it.
        snap = _make_snapshot(visited_steps=["s_only_visited"])
        empty = _make_snapshot()
        report = compare(_make_input(), snap, empty, generated_at=_FIXED_GEN_AT)
        sd = next(s for s in report.step_diffs if s.step_id == "s_only_visited")
        assert sd.status_baseline == "visited"
        assert sd.status_candidate == "missing"

    def test_status_missing_when_step_unknown_to_snapshot(self) -> None:
        # Step appears in candidate only -> baseline status='missing'.
        a1 = _make_artifact(aid="a1", step_id="s_only_in_c")
        report = _run_compare(_make_snapshot(), _make_snapshot(artifacts=[a1]))
        sd = report.step_diffs[0]
        assert sd.status_baseline == "missing"

    def test_step_id_only_in_failure_events_appears_in_step_diffs(self) -> None:
        # H1 (Task 3 Review Fix Pack): a step that fails before producing any
        # artifact / checkpoint / visited_steps marker — its step_id MUST
        # still appear in step_diffs so reporters can surface the failure
        # root cause. Without _collect_step_ids unioning failure_events,
        # such steps would be silently dropped from the comparison report.
        snap = _make_snapshot(
            failure_events=[{"step_id": "s_orphan_failed", "mode": "provider_timeout"}],
        )
        empty = _make_snapshot()
        report = compare(_make_input(), snap, empty, generated_at=_FIXED_GEN_AT)
        step_ids = [sd.step_id for sd in report.step_diffs]
        assert "s_orphan_failed" in step_ids
        sd = next(s for s in report.step_diffs if s.step_id == "s_orphan_failed")
        assert sd.status_baseline == "failed"
        assert sd.status_candidate == "missing"

    def test_step_id_only_in_revise_events_appears_in_step_diffs(self) -> None:
        # Mirror of the failure-only case for revise_events: must not vanish
        # from step_diffs when no other source mentions the step.
        snap = _make_snapshot(
            revise_events=[{"step_id": "s_orphan_revised"}],
        )
        empty = _make_snapshot()
        report = compare(_make_input(), snap, empty, generated_at=_FIXED_GEN_AT)
        step_ids = [sd.step_id for sd in report.step_diffs]
        assert "s_orphan_revised" in step_ids
        sd = next(s for s in report.step_diffs if s.step_id == "s_orphan_revised")
        assert sd.status_baseline == "revised"
        assert sd.status_candidate == "missing"


# ---------------------------------------------------------------------------
# TestCompareValidationDiff (M2: validation shallow expansion)
# ---------------------------------------------------------------------------


class TestCompareValidationDiff:
    def test_validation_warnings_difference_surfaces(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HX", validation_warnings=["w1", "w2"])
        c_art = _make_artifact(aid="a1", hash_str="HX", validation_warnings=["w1", "w3"])
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "metadata_only"
        assert ad.metadata_delta["validation.warnings"] == (("w1", "w2"), ("w1", "w3"))

    def test_validation_errors_difference_surfaces(self) -> None:
        b_art = _make_artifact(aid="a1", hash_str="HX", validation_errors=[])
        c_art = _make_artifact(aid="a1", hash_str="HX", validation_errors=["e1"])
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "metadata_only"
        assert ad.metadata_delta["validation.errors"] == ((), ("e1",))

    def test_validation_checks_count_difference_surfaces(self) -> None:
        b_checks = [ValidationCheck(name=f"c{i}", result="passed") for i in range(2)]
        c_checks = [ValidationCheck(name=f"c{i}", result="passed") for i in range(5)]
        b_art = _make_artifact(aid="a1", hash_str="HX", validation_checks=b_checks)
        c_art = _make_artifact(aid="a1", hash_str="HX", validation_checks=c_checks)
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "metadata_only"
        assert ad.metadata_delta["validation.checks_count"] == (2, 5)

    def test_validation_individual_check_details_not_deep_walked(self) -> None:
        # Same checks count + same warnings + same errors, but different
        # individual ValidationCheck attributes. Per Task 3 Review Fix Pack
        # constraint, deep-walk is OUT of scope — diff engine sees only the
        # count, so the metadata_delta surfaces NO validation.* keys.
        b_checks = [ValidationCheck(name="schema", result="passed")]
        c_checks = [ValidationCheck(name="schema", result="failed", detail="oops")]
        b_art = _make_artifact(aid="a1", hash_str="HX", validation_checks=b_checks)
        c_art = _make_artifact(aid="a1", hash_str="HX", validation_checks=c_checks)
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        # checks count is equal -> no validation.checks_count entry
        assert "validation.checks_count" not in ad.metadata_delta
        # individual check.result drift -> NOT surfaced (deep-walk skipped)
        for key in ad.metadata_delta:
            assert not key.startswith("validation."), (
                f"unexpected validation diff key {key!r} — deep-walk should skip "
                f"individual ValidationCheck attributes"
            )

    def test_validation_warnings_normalized_sorted(self) -> None:
        # Sorting normalization: same multiset, different order -> not a diff.
        b_art = _make_artifact(aid="a1", hash_str="HX", validation_warnings=["w_a", "w_b"])
        c_art = _make_artifact(aid="a1", hash_str="HX", validation_warnings=["w_b", "w_a"])
        report = _run_compare(
            _make_snapshot(artifacts=[b_art]),
            _make_snapshot(artifacts=[c_art]),
        )
        ad = report.step_diffs[0].artifact_diffs[0]
        assert ad.kind == "unchanged"


# ---------------------------------------------------------------------------
# TestDiffEngineImportFence (Task 3 hard requirement)
# ---------------------------------------------------------------------------
#
# Importing framework.comparison.diff_engine MUST NOT pull in any execution
# layer module nor any artifact_store WRITE-side module (repository,
# payload_backends). This is stricter than Task 2's loader fence: diff_engine
# achieves the stricter surface by referencing RunSnapshot / Artifact /
# Checkpoint only inside TYPE_CHECKING, so the runtime import chain stops at
# framework.comparison.models.


_FORBIDDEN_FRAMEWORK_MODULES_DIFF_ENGINE: tuple[str, ...] = (
    "framework.runtime",
    "framework.providers",
    "framework.review_engine",
    "framework.ue_bridge",
    "framework.workflows",
    "framework.observability",
    "framework.server",
    "framework.schemas",
    "framework.pricing_probe",
    "framework.artifact_store.repository",
    "framework.artifact_store.payload_backends",
)


class TestDiffEngineImportFence:
    def test_diff_engine_import_does_not_pull_in_execution_or_write_layers(
        self,
    ) -> None:
        src_dir = Path(__file__).resolve().parents[2] / "src"
        assert (
            src_dir / "framework" / "comparison" / "diff_engine.py"
        ).is_file(), f"cannot locate framework.comparison.diff_engine under {src_dir}"

        probe = (
            "import sys\n"
            f"sys.path.insert(0, {str(src_dir)!r})\n"
            "import framework.comparison.diff_engine  # noqa: F401\n"
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

        for forbidden in _FORBIDDEN_FRAMEWORK_MODULES_DIFF_ENGINE:
            leaked = [m for m in loaded if m == forbidden or m.startswith(forbidden + ".")]
            assert not leaked, (
                f"framework.comparison.diff_engine transitively imported "
                f"forbidden module(s): {leaked}. The diff engine must stay a "
                f"pure compute layer with no execution-layer or write-side dependency."
            )

        # Sanity: the module itself and its compile-time dep (models) loaded.
        assert "framework.comparison" in loaded
        assert "framework.comparison.diff_engine" in loaded
        assert "framework.comparison.models" in loaded
