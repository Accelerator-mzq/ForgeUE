"""Unit tests for framework.comparison.models.

Covers:
- Literal enumeration closed-sets (ArtifactDiffKind / VerdictDiffKind / MetricScope)
- RunComparisonInput default values + frozen semantics
- ArtifactDiff / VerdictDiff / MetricDiff / StepDiff construction shapes
- RunComparisonReport schema_version lock + JSON roundtrip
- Static isolation: loading framework.comparison.models MUST NOT pull in
  runtime / providers / review_engine / ue_bridge / artifact_store / workflows

Test count is not hardcoded; `python -m pytest -q` actual output is authoritative.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from framework.comparison.models import (
    ArtifactDiff,
    MetricDiff,
    RunComparisonInput,
    RunComparisonReport,
    StepDiff,
    VerdictDiff,
)

# ---------------------------------------------------------------------------
# Literal enumerations are closed
# ---------------------------------------------------------------------------


class TestLiteralEnumsClosed:
    @pytest.mark.parametrize(
        "kind",
        [
            "unchanged",
            "content_changed",
            "metadata_only",
            "missing_in_baseline",
            "missing_in_candidate",
            "payload_missing_on_disk",
        ],
    )
    def test_artifact_diff_kind_accepts_all_six_values(self, kind: str) -> None:
        diff = ArtifactDiff(artifact_id="a", kind=kind)  # type: ignore[arg-type]
        assert diff.kind == kind

    def test_artifact_diff_kind_rejects_unknown_value(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactDiff(artifact_id="a", kind="exploded")  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "kind",
        [
            "unchanged",
            "decision_changed",
            "confidence_changed",
            "selected_candidates_changed",
            "missing_in_baseline",
            "missing_in_candidate",
        ],
    )
    def test_verdict_diff_kind_accepts_all_six_values(self, kind: str) -> None:
        diff = VerdictDiff(step_id="s", kind=kind)  # type: ignore[arg-type]
        assert diff.kind == kind

    def test_verdict_diff_kind_rejects_unknown_value(self) -> None:
        with pytest.raises(ValidationError):
            VerdictDiff(step_id="s", kind="nope")  # type: ignore[arg-type]

    @pytest.mark.parametrize("scope", ["run", "step"])
    def test_metric_scope_accepts_run_and_step(self, scope: str) -> None:
        metric = MetricDiff(metric="cost_usd", scope=scope)  # type: ignore[arg-type]
        assert metric.scope == scope

    def test_metric_scope_rejects_unknown_value(self) -> None:
        with pytest.raises(ValidationError):
            MetricDiff(metric="cost_usd", scope="cluster")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RunComparisonInput defaults + frozen
# ---------------------------------------------------------------------------


class TestRunComparisonInputDefaults:
    def _build(self, **overrides) -> RunComparisonInput:
        base = dict(
            baseline_run_id="run_a",
            candidate_run_id="run_b",
            artifact_root=Path("./artifacts"),
        )
        base.update(overrides)
        return RunComparisonInput(**base)

    def test_input_constructs_with_minimum_fields(self) -> None:
        inp = self._build()
        assert inp.baseline_run_id == "run_a"
        assert inp.candidate_run_id == "run_b"
        assert inp.artifact_root == Path("./artifacts")

    def test_input_default_strict_is_true(self) -> None:
        assert self._build().strict is True

    def test_input_default_include_hash_check_is_true(self) -> None:
        assert self._build().include_payload_hash_check is True

    def test_input_default_date_buckets_are_none(self) -> None:
        inp = self._build()
        assert inp.baseline_date_bucket is None
        assert inp.candidate_date_bucket is None

    def test_input_is_frozen_assignment_raises(self) -> None:
        inp = self._build()
        with pytest.raises(ValidationError):
            inp.strict = False  # type: ignore[misc]

    def test_input_accepts_explicit_date_bucket(self) -> None:
        inp = self._build(baseline_date_bucket="2000-01-01")
        assert inp.baseline_date_bucket == "2000-01-01"


# ---------------------------------------------------------------------------
# ArtifactDiff construction
# ---------------------------------------------------------------------------


class TestArtifactDiffConstruction:
    def test_artifact_diff_unchanged_minimal_fields(self) -> None:
        diff = ArtifactDiff(artifact_id="img_0", kind="unchanged")
        assert diff.baseline_hash is None
        assert diff.candidate_hash is None
        assert diff.metadata_delta == {}
        assert diff.lineage_delta is None
        assert diff.note is None

    def test_artifact_diff_content_changed_with_hashes(self) -> None:
        diff = ArtifactDiff(
            artifact_id="img_0",
            kind="content_changed",
            baseline_hash="abc",
            candidate_hash="def",
        )
        assert diff.baseline_hash == "abc"
        assert diff.candidate_hash == "def"

    def test_artifact_diff_missing_in_baseline_has_only_candidate_hash(self) -> None:
        diff = ArtifactDiff(
            artifact_id="new_art",
            kind="missing_in_baseline",
            candidate_hash="hashC",
        )
        assert diff.baseline_hash is None
        assert diff.candidate_hash == "hashC"

    def test_artifact_diff_metadata_delta_carries_before_after_tuples(self) -> None:
        diff = ArtifactDiff(
            artifact_id="img_0",
            kind="metadata_only",
            metadata_delta={"width": (512, 1024)},
        )
        assert diff.metadata_delta == {"width": (512, 1024)}

    def test_artifact_diff_lineage_delta_optional(self) -> None:
        diff = ArtifactDiff(
            artifact_id="img_0",
            kind="unchanged",
            lineage_delta={"selected_by_verdict_id": ("v1", "v2")},
        )
        assert diff.lineage_delta == {"selected_by_verdict_id": ("v1", "v2")}

    def test_artifact_diff_payload_missing_on_disk_allows_note(self) -> None:
        diff = ArtifactDiff(
            artifact_id="img_0",
            kind="payload_missing_on_disk",
            baseline_hash="abc",
            note="baseline backend exists()==False",
        )
        assert diff.note == "baseline backend exists()==False"


# ---------------------------------------------------------------------------
# VerdictDiff construction
# ---------------------------------------------------------------------------


class TestVerdictDiffConstruction:
    def test_verdict_diff_unchanged_minimal(self) -> None:
        diff = VerdictDiff(step_id="step_review", kind="unchanged")
        assert diff.baseline_decision is None
        assert diff.candidate_decision is None
        assert diff.selected_delta is None

    def test_verdict_diff_decision_changed_carries_both_decisions(self) -> None:
        diff = VerdictDiff(
            step_id="step_review",
            kind="decision_changed",
            baseline_decision="accept",
            candidate_decision="revise",
        )
        assert diff.baseline_decision == "accept"
        assert diff.candidate_decision == "revise"

    def test_verdict_diff_confidence_changed_carries_both_floats(self) -> None:
        diff = VerdictDiff(
            step_id="step_review",
            kind="confidence_changed",
            baseline_confidence=0.82,
            candidate_confidence=0.67,
        )
        assert diff.baseline_confidence == pytest.approx(0.82)
        assert diff.candidate_confidence == pytest.approx(0.67)

    def test_verdict_diff_selected_delta_added_removed_shape(self) -> None:
        diff = VerdictDiff(
            step_id="step_review",
            kind="selected_candidates_changed",
            selected_delta={"added": ["cand_2"], "removed": ["cand_0"]},
        )
        assert diff.selected_delta is not None
        assert set(diff.selected_delta.keys()) == {"added", "removed"}
        assert diff.selected_delta["added"] == ["cand_2"]
        assert diff.selected_delta["removed"] == ["cand_0"]

    def test_verdict_diff_missing_in_candidate(self) -> None:
        diff = VerdictDiff(
            step_id="step_review",
            kind="missing_in_candidate",
            baseline_decision="accept",
        )
        assert diff.candidate_decision is None


# ---------------------------------------------------------------------------
# MetricDiff construction (no business validator per Task 1 constraint)
# ---------------------------------------------------------------------------


class TestMetricDiffConstruction:
    def test_metric_diff_run_scope_without_step_id(self) -> None:
        m = MetricDiff(metric="cost_usd", scope="run", baseline_value=0.10, candidate_value=0.12)
        assert m.step_id is None

    def test_metric_diff_step_scope_with_step_id(self) -> None:
        m = MetricDiff(metric="prompt_tokens", scope="step", step_id="step_spec")
        assert m.step_id == "step_spec"

    def test_metric_diff_step_scope_with_missing_step_id_is_allowed_at_model_layer(self) -> None:
        # Business rule "scope=step requires step_id" lives in diff_engine / reporter,
        # not in the model layer — Task 1 only ships the data shape.
        m = MetricDiff(metric="wall_clock_s", scope="step", step_id=None)
        assert m.scope == "step"
        assert m.step_id is None

    def test_metric_diff_cost_delta_and_pct(self) -> None:
        m = MetricDiff(
            metric="cost_usd",
            scope="run",
            baseline_value=0.10,
            candidate_value=0.12,
            delta=0.02,
            delta_pct=20.0,
        )
        assert m.delta == pytest.approx(0.02)
        assert m.delta_pct == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# StepDiff aggregation
# ---------------------------------------------------------------------------


class TestStepDiffAggregation:
    def test_step_diff_minimal_no_sub_diffs(self) -> None:
        sd = StepDiff(
            step_id="step_spec",
            status_baseline="succeeded",
            status_candidate="succeeded",
        )
        assert sd.artifact_diffs == []
        assert sd.verdict_diffs == []
        assert sd.metric_diffs == []
        assert sd.chosen_model_baseline is None
        assert sd.chosen_model_candidate is None

    def test_step_diff_nested_artifact_and_verdict_diffs(self) -> None:
        sd = StepDiff(
            step_id="step_review",
            status_baseline="succeeded",
            status_candidate="succeeded",
            chosen_model_baseline="pc_opus_4_6",
            chosen_model_candidate="pc_sonnet_4_6",
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="rep_0", kind="content_changed", baseline_hash="a", candidate_hash="b"
                ),
            ],
            verdict_diffs=[
                VerdictDiff(
                    step_id="step_review",
                    kind="decision_changed",
                    baseline_decision="accept",
                    candidate_decision="revise",
                ),
            ],
        )
        assert len(sd.artifact_diffs) == 1
        assert len(sd.verdict_diffs) == 1
        assert sd.chosen_model_baseline == "pc_opus_4_6"
        assert sd.chosen_model_candidate == "pc_sonnet_4_6"


# ---------------------------------------------------------------------------
# RunComparisonReport schema-version lock + JSON roundtrip
# ---------------------------------------------------------------------------


def _make_input() -> RunComparisonInput:
    return RunComparisonInput(
        baseline_run_id="run_a",
        candidate_run_id="run_b",
        artifact_root=Path("./artifacts"),
    )


def _make_report(**overrides) -> RunComparisonReport:
    base = dict(
        input=_make_input(),
        status_match=True,
        generated_at=datetime(2000, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    base.update(overrides)
    return RunComparisonReport(**base)


class TestRunComparisonReportSchemaLock:
    def test_report_schema_version_locked_to_1_by_default(self) -> None:
        r = _make_report()
        assert r.schema_version == "1"

    def test_report_schema_version_rejects_other_string(self) -> None:
        with pytest.raises(ValidationError):
            _make_report(schema_version="2")

    def test_report_status_match_is_required(self) -> None:
        with pytest.raises(ValidationError):
            RunComparisonReport(
                input=_make_input(),
                generated_at=datetime(2000, 1, 1, tzinfo=UTC),
            )  # type: ignore[call-arg]

    def test_report_defaults_for_collections_are_empty(self) -> None:
        r = _make_report()
        assert r.baseline_run_meta == {}
        assert r.candidate_run_meta == {}
        assert r.step_diffs == []
        assert r.run_level_metric_diffs == []
        assert r.summary_counts == {}

    def test_report_model_dump_json_roundtrip(self) -> None:
        r = _make_report(
            summary_counts={"unchanged": 3, "content_changed": 1},
            run_level_metric_diffs=[
                MetricDiff(
                    metric="cost_usd",
                    scope="run",
                    baseline_value=0.10,
                    candidate_value=0.12,
                    delta=0.02,
                    delta_pct=20.0,
                ),
            ],
        )
        dumped = r.model_dump_json()
        parsed = json.loads(dumped)
        assert parsed["schema_version"] == "1"
        assert parsed["status_match"] is True
        assert parsed["summary_counts"]["content_changed"] == 1

        restored = RunComparisonReport.model_validate_json(dumped)
        assert restored.schema_version == "1"
        assert restored.summary_counts == {"unchanged": 3, "content_changed": 1}
        assert len(restored.run_level_metric_diffs) == 1
        assert restored.run_level_metric_diffs[0].metric == "cost_usd"

    def test_report_nested_step_diffs_roundtrip(self) -> None:
        r = _make_report(
            step_diffs=[
                StepDiff(
                    step_id="step_spec",
                    status_baseline="succeeded",
                    status_candidate="succeeded",
                    artifact_diffs=[
                        ArtifactDiff(artifact_id="spec_0", kind="unchanged"),
                    ],
                ),
            ],
        )
        restored = RunComparisonReport.model_validate_json(r.model_dump_json())
        assert len(restored.step_diffs) == 1
        assert restored.step_diffs[0].step_id == "step_spec"
        assert restored.step_diffs[0].artifact_diffs[0].kind == "unchanged"


# ---------------------------------------------------------------------------
# JSON roundtrip contracts (H1 + H2 from Review Fix Pack)
#
# H1: dict[str, tuple[Any, Any]] in metadata_delta / lineage_delta MUST survive
#     model_dump_json -> model_validate_json with the tuple type preserved
#     (JSON has no tuple — Pydantic v2 must coerce 2-elem list back to tuple).
# H2: RunComparisonInput.artifact_root: Path MUST survive the same roundtrip
#     and remain a Path on the reconstructed object (cross-platform Windows-safe).
# ---------------------------------------------------------------------------


class TestJsonRoundtripContracts:
    def test_artifact_diff_metadata_delta_tuple_survives_json_roundtrip(self) -> None:
        diff = ArtifactDiff(
            artifact_id="img_0",
            kind="metadata_only",
            metadata_delta={"width": (512, 1024), "fmt": ("png", "webp")},
        )
        restored = ArtifactDiff.model_validate_json(diff.model_dump_json())
        assert isinstance(restored.metadata_delta["width"], tuple)
        assert isinstance(restored.metadata_delta["fmt"], tuple)
        assert restored.metadata_delta == {"width": (512, 1024), "fmt": ("png", "webp")}

    def test_artifact_diff_lineage_delta_tuple_survives_json_roundtrip(self) -> None:
        diff = ArtifactDiff(
            artifact_id="img_0",
            kind="unchanged",
            lineage_delta={
                "selected_by_verdict_id": ("v1", "v2"),
                "variant_group_id": ("vg_a", "vg_b"),
            },
        )
        restored = ArtifactDiff.model_validate_json(diff.model_dump_json())
        assert restored.lineage_delta is not None
        assert isinstance(restored.lineage_delta["selected_by_verdict_id"], tuple)
        assert isinstance(restored.lineage_delta["variant_group_id"], tuple)
        assert restored.lineage_delta["selected_by_verdict_id"] == ("v1", "v2")
        assert restored.lineage_delta["variant_group_id"] == ("vg_a", "vg_b")

    def test_artifact_diff_metadata_delta_tuple_survives_via_full_report(self) -> None:
        # End-to-end: ensures tuples survive when nested deep inside
        # RunComparisonReport -> StepDiff -> ArtifactDiff.metadata_delta.
        report = _make_report(
            step_diffs=[
                StepDiff(
                    step_id="s1",
                    status_baseline="succeeded",
                    status_candidate="succeeded",
                    artifact_diffs=[
                        ArtifactDiff(
                            artifact_id="img_0",
                            kind="metadata_only",
                            metadata_delta={"width": (512, 1024)},
                        )
                    ],
                )
            ]
        )
        restored = RunComparisonReport.model_validate_json(report.model_dump_json())
        nested = restored.step_diffs[0].artifact_diffs[0].metadata_delta["width"]
        assert isinstance(nested, tuple)
        assert nested == (512, 1024)

    def test_input_artifact_root_path_survives_json_roundtrip(self) -> None:
        # Use Path("./artifacts") via _make_input(); the assertion is
        # type-isinstance + value-equality against the original Path object
        # (no hardcoded slash), so this is Windows-safe.
        report = _make_report()
        restored = RunComparisonReport.model_validate_json(report.model_dump_json())
        assert isinstance(restored.input.artifact_root, Path)
        assert restored.input.artifact_root == report.input.artifact_root

    def test_input_artifact_root_path_roundtrip_with_subdir(self) -> None:
        # Multi-segment path also survives (catches separator-handling bugs).
        original = RunComparisonInput(
            baseline_run_id="run_a",
            candidate_run_id="run_b",
            artifact_root=Path("artifacts") / "buckets",
        )
        report = RunComparisonReport(
            input=original,
            status_match=True,
            generated_at=datetime(2000, 1, 1, tzinfo=UTC),
        )
        restored = RunComparisonReport.model_validate_json(report.model_dump_json())
        assert isinstance(restored.input.artifact_root, Path)
        assert restored.input.artifact_root == original.artifact_root


# ---------------------------------------------------------------------------
# Static isolation: models module must not import framework execution layers
# ---------------------------------------------------------------------------


_FORBIDDEN_FRAMEWORK_MODULES = (
    "framework.runtime",
    "framework.providers",
    "framework.review_engine",
    "framework.ue_bridge",
    "framework.artifact_store",
    "framework.workflows",
    "framework.observability",
    "framework.server",
    "framework.schemas",
    "framework.pricing_probe",
)


class TestNoUnexpectedFrameworkImports:
    """Fence: importing framework.comparison.models must not transitively load
    runtime / providers / review_engine / ue_bridge / artifact_store / workflows.

    Runs in a subprocess so that modules already loaded by tests/conftest.py
    (notably framework.providers.model_registry) cannot cause false positives.
    """

    def test_models_import_does_not_pull_in_execution_layers(self) -> None:
        # Locate the repo's src/ directory so the subprocess can import
        # `framework.*` without relying on `pip install -e .` or conftest's
        # sys.path tweak (subprocesses do not inherit either).
        src_dir = Path(__file__).resolve().parents[2] / "src"
        assert (
            src_dir / "framework" / "comparison" / "models.py"
        ).is_file(), f"cannot locate framework.comparison.models under {src_dir}"

        probe = (
            "import sys\n"
            f"sys.path.insert(0, {str(src_dir)!r})\n"
            "import framework.comparison.models  # noqa: F401\n"
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

        for forbidden in _FORBIDDEN_FRAMEWORK_MODULES:
            leaked = [m for m in loaded if m == forbidden or m.startswith(forbidden + ".")]
            assert not leaked, (
                f"framework.comparison.models transitively imported forbidden module(s): {leaked}. "
                f"The comparison module must stay a read-only consumer with no execution-layer dependency."
            )

        # Sanity: the module itself and its ancestor package should be loaded.
        assert "framework" in loaded
        assert "framework.comparison" in loaded
        assert "framework.comparison.models" in loaded
