"""Unit tests for framework.comparison.reporter.

The reporter is a pure presentation layer: it consumes a pre-built
RunComparisonReport and renders JSON + Markdown. Tests construct reports
directly via Pydantic — no loader and no compare() involvement — which (in
combination with the subprocess-isolated import-fence below) demonstrates
that the reporter does not depend on the diff or load layers.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args

from framework.comparison.models import (
    ArtifactDiff,
    ArtifactDiffKind,
    MetricDiff,
    RunComparisonInput,
    RunComparisonReport,
    StepDiff,
    VerdictDiff,
    VerdictDiffKind,
)
from framework.comparison.reporter import (
    JSON_FILENAME,
    MARKDOWN_FILENAME,
    _count,
    _escape_cell,
    _line_safe,
    render_json,
    render_markdown,
    write_reports,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIXED_GEN_AT = datetime(2000, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_input(
    *,
    baseline_run_id: str = "run_a",
    candidate_run_id: str = "run_b",
    strict: bool = True,
    include_payload_hash_check: bool = True,
) -> RunComparisonInput:
    return RunComparisonInput(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        artifact_root=Path("./artifacts"),
        strict=strict,
        include_payload_hash_check=include_payload_hash_check,
    )


def _make_report(
    *,
    baseline_run_id: str = "run_a",
    candidate_run_id: str = "run_b",
    status_match: bool = True,
    step_diffs: list[StepDiff] | None = None,
    run_level_metric_diffs: list[MetricDiff] | None = None,
    summary_counts: dict[str, int] | None = None,
    baseline_run_meta: dict[str, Any] | None = None,
    candidate_run_meta: dict[str, Any] | None = None,
    generated_at: datetime = _FIXED_GEN_AT,
) -> RunComparisonReport:
    return RunComparisonReport(
        input=_make_input(
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
        ),
        status_match=status_match,
        generated_at=generated_at,
        baseline_run_meta=baseline_run_meta or {"run_id": baseline_run_id, "status": "succeeded"},
        candidate_run_meta=(candidate_run_meta or {"run_id": candidate_run_id, "status": "succeeded"}),
        step_diffs=step_diffs or [],
        run_level_metric_diffs=run_level_metric_diffs or [],
        summary_counts=summary_counts or {},
    )


def _step_with_all_artifact_kinds() -> StepDiff:
    return StepDiff(
        step_id="s_artifacts",
        status_baseline="succeeded",
        status_candidate="succeeded",
        artifact_diffs=[
            ArtifactDiff(
                artifact_id="a_unchanged",
                kind="unchanged",
                baseline_hash="H",
                candidate_hash="H",
            ),
            ArtifactDiff(
                artifact_id="a_content_changed",
                kind="content_changed",
                baseline_hash="H1",
                candidate_hash="H2",
            ),
            ArtifactDiff(
                artifact_id="a_metadata_only",
                kind="metadata_only",
                baseline_hash="H",
                candidate_hash="H",
                metadata_delta={"format": ("png", "webp")},
            ),
            ArtifactDiff(
                artifact_id="a_missing_in_baseline",
                kind="missing_in_baseline",
                candidate_hash="HC",
            ),
            ArtifactDiff(
                artifact_id="a_missing_in_candidate",
                kind="missing_in_candidate",
                baseline_hash="HB",
            ),
            ArtifactDiff(
                artifact_id="a_payload_missing",
                kind="payload_missing_on_disk",
                baseline_hash="H",
                candidate_hash="H",
                note="payload missing on disk: baseline",
            ),
        ],
    )


def _step_with_all_verdict_kinds() -> StepDiff:
    return StepDiff(
        step_id="s_verdicts",
        status_baseline="succeeded",
        status_candidate="succeeded",
        verdict_diffs=[
            VerdictDiff(
                step_id="s_verdicts",
                kind="unchanged",
                baseline_decision="approve",
                candidate_decision="approve",
            ),
            VerdictDiff(
                step_id="s_verdicts",
                kind="decision_changed",
                baseline_decision="approve",
                candidate_decision="reject",
            ),
            VerdictDiff(
                step_id="s_verdicts",
                kind="confidence_changed",
                baseline_decision="approve",
                candidate_decision="approve",
                baseline_confidence=0.9,
                candidate_confidence=0.5,
            ),
            VerdictDiff(
                step_id="s_verdicts",
                kind="selected_candidates_changed",
                baseline_decision="approve_one",
                candidate_decision="approve_one",
                selected_delta={"added": ["c2"], "removed": ["c0"]},
            ),
            VerdictDiff(
                step_id="s_verdicts",
                kind="missing_in_baseline",
                candidate_decision="approve",
            ),
            VerdictDiff(
                step_id="s_verdicts",
                kind="missing_in_candidate",
                baseline_decision="approve",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# TestRenderJson
# ---------------------------------------------------------------------------


class TestRenderJson:
    def test_round_trips_via_json_loads(self) -> None:
        report = _make_report()
        out = render_json(report)
        parsed = json.loads(out)
        assert parsed["schema_version"] == "1"

    def test_trailing_newline(self) -> None:
        out = render_json(_make_report())
        assert out.endswith("\n")
        # Exactly one trailing newline (D6).
        assert not out.endswith("\n\n")

    def test_deterministic(self) -> None:
        report = _make_report(
            step_diffs=[_step_with_all_artifact_kinds(), _step_with_all_verdict_kinds()],
            summary_counts={"steps_total": 2, "artifact:unchanged": 1},
        )
        assert render_json(report) == render_json(report)

    def test_indented_two_spaces(self) -> None:
        out = render_json(_make_report())
        # `model_dump_json(indent=2)` emits two-space indentation; presence
        # of "\n  " confirms the indent setting is applied.
        assert "\n  " in out


# ---------------------------------------------------------------------------
# TestRenderMarkdownEmpty
# ---------------------------------------------------------------------------


class TestRenderMarkdownEmpty:
    def test_empty_report_renders_without_keyerror(self) -> None:
        # summary_counts is intentionally empty: missing the always-present
        # `steps_total` etc. AND every artifact:* / verdict:* kind. The
        # renderer MUST go through `_count` (.get(key, 0)) not subscript.
        report = _make_report(summary_counts={})
        out = render_markdown(report)
        assert "| steps_total | 0 |" in out
        assert "| steps_with_artifact_change | 0 |" in out
        assert "| steps_with_verdict_change | 0 |" in out
        for k in get_args(ArtifactDiffKind):
            assert f"| artifact:{k} | 0 |" in out, f"artifact:{k} row missing in counts table"
        for k in get_args(VerdictDiffKind):
            assert f"| verdict:{k} | 0 |" in out, f"verdict:{k} row missing in counts table"

    def test_empty_report_anomalies_none(self) -> None:
        out = render_markdown(_make_report(summary_counts={}))
        assert "## Anomalies\n\n(none)" in out

    def test_empty_report_step_diffs_none(self) -> None:
        out = render_markdown(_make_report(summary_counts={}))
        assert "## Step diffs\n\n(none)" in out

    def test_empty_report_run_metrics_none(self) -> None:
        out = render_markdown(_make_report(summary_counts={}))
        assert "## Run-level metrics\n\n(none)" in out

    def test_counts_table_lists_all_twelve_kinds_even_when_unused(self) -> None:
        # D1: full Counts table even when no diff of that kind occurred.
        out = render_markdown(_make_report(summary_counts={}))
        artifact_lines = [line for line in out.splitlines() if line.startswith("| artifact:")]
        verdict_lines = [line for line in out.splitlines() if line.startswith("| verdict:")]
        assert len(artifact_lines) == len(get_args(ArtifactDiffKind))
        assert len(verdict_lines) == len(get_args(VerdictDiffKind))


# ---------------------------------------------------------------------------
# TestRenderMarkdownAllKinds
# ---------------------------------------------------------------------------


class TestRenderMarkdownAllKinds:
    def test_each_artifact_kind_label_appears(self) -> None:
        report = _make_report(step_diffs=[_step_with_all_artifact_kinds()])
        out = render_markdown(report)
        for k in get_args(ArtifactDiffKind):
            assert k in out, f"artifact kind {k!r} missing from markdown"

    def test_each_verdict_kind_label_appears(self) -> None:
        report = _make_report(step_diffs=[_step_with_all_verdict_kinds()])
        out = render_markdown(report)
        for k in get_args(VerdictDiffKind):
            assert k in out, f"verdict kind {k!r} missing from markdown"


# ---------------------------------------------------------------------------
# TestRenderMarkdownStableOrder
# ---------------------------------------------------------------------------


class TestRenderMarkdownStableOrder:
    def test_same_input_byte_identical(self) -> None:
        report = _make_report(
            step_diffs=[_step_with_all_artifact_kinds(), _step_with_all_verdict_kinds()],
            summary_counts={"steps_total": 2, "artifact:unchanged": 1},
        )
        assert render_markdown(report) == render_markdown(report)


# ---------------------------------------------------------------------------
# TestRenderMarkdownAsciiOnly
# ---------------------------------------------------------------------------


class TestRenderMarkdownAsciiOnly:
    def test_pure_ascii_input_strict_encodes(self) -> None:
        report = _make_report(
            step_diffs=[_step_with_all_artifact_kinds(), _step_with_all_verdict_kinds()],
        )
        out = render_markdown(report)
        # Markdown output must be ASCII-only — strict encode raises if not.
        out.encode("ascii", errors="strict")

    def test_non_ascii_input_coerced_to_backslash_escapes(self) -> None:
        # Defensive: if a non-ASCII run_id sneaks through into a built
        # report, the rendered Markdown must remain ASCII (via
        # backslashreplace) rather than crashing a downstream Windows GBK
        # stdout / cat.
        report = _make_report(
            baseline_run_id="run_测试",
            baseline_run_meta={"run_id": "run_测试", "status": "succeeded"},
        )
        out = render_markdown(report)
        out.encode("ascii", errors="strict")
        # Non-ASCII characters surface as \uXXXX escape literals.
        assert "\\u6d4b" in out
        assert "\\u8bd5" in out


# ---------------------------------------------------------------------------
# TestRenderMarkdownIntegrityNotes
# ---------------------------------------------------------------------------


class TestRenderMarkdownIntegrityNotes:
    def test_note_appears_in_step_section(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="a1",
                    kind="content_changed",
                    baseline_hash="HB",
                    candidate_hash="HC",
                    note="baseline payload tampered: recorded='HB', recomputed='HB_real'",
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        assert "baseline payload tampered" in out

    def test_anomalies_section_lists_payload_missing(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="a1",
                    kind="payload_missing_on_disk",
                    baseline_hash="H",
                    candidate_hash="H",
                    note="payload missing on disk: baseline",
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        anomalies = out.split("## Anomalies", 1)[1]
        assert "step=s1" in anomalies
        assert "artifact=a1" in anomalies
        assert "kind=payload_missing_on_disk" in anomalies

    def test_anomalies_section_lists_missing_in_candidate(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="missing",
            artifact_diffs=[
                ArtifactDiff(artifact_id="a1", kind="missing_in_candidate", baseline_hash="HB"),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        anomalies = out.split("## Anomalies", 1)[1]
        assert "step=s1" in anomalies
        assert "kind=missing_in_candidate" in anomalies

    def test_anomalies_section_lists_content_changed_with_note(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="a1",
                    kind="content_changed",
                    baseline_hash="HB",
                    candidate_hash="HC",
                    note="candidate payload tampered: recorded='HC', recomputed='HC_real'",
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        anomalies = out.split("## Anomalies", 1)[1]
        # content_changed is not itself an anomaly kind, but the tamper note
        # signals the integrity contract — the anomaly section MUST surface
        # it via the `note is not None` branch.
        assert "step=s1" in anomalies
        assert "kind=content_changed" in anomalies
        assert "candidate payload tampered" in anomalies

    def test_unchanged_artifact_not_in_anomalies(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="a1",
                    kind="unchanged",
                    baseline_hash="H",
                    candidate_hash="H",
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        anomalies = out.split("## Anomalies", 1)[1]
        # Anomalies section is present and shows "(none)" rather than
        # listing the unchanged artifact.
        assert "(none)" in anomalies
        assert "step=s1" not in anomalies


# ---------------------------------------------------------------------------
# TestRenderMarkdownSelectedDelta
# ---------------------------------------------------------------------------


class TestRenderMarkdownSelectedDelta:
    def test_selected_delta_with_rejected_keys(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            verdict_diffs=[
                VerdictDiff(
                    step_id="s1",
                    kind="selected_candidates_changed",
                    baseline_decision="approve_one",
                    candidate_decision="approve_one",
                    selected_delta={
                        "added": ["c2"],
                        "removed": ["c0"],
                        "rejected_added": ["c5"],
                        "rejected_removed": ["c4"],
                    },
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        assert "added=['c2']" in out
        assert "removed=['c0']" in out
        assert "rejected_added=['c5']" in out
        assert "rejected_removed=['c4']" in out

    def test_selected_delta_skips_absent_rejected_keys(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            verdict_diffs=[
                VerdictDiff(
                    step_id="s1",
                    kind="selected_candidates_changed",
                    baseline_decision="approve_one",
                    candidate_decision="approve_one",
                    selected_delta={"added": ["c2"], "removed": ["c0"]},
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        assert "added=['c2']" in out
        assert "removed=['c0']" in out
        assert "rejected_added" not in out
        assert "rejected_removed" not in out


# ---------------------------------------------------------------------------
# TestRenderMarkdownMetadataDelta
# ---------------------------------------------------------------------------


class TestRenderMarkdownMetadataDelta:
    def test_format_change_uses_repr(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="a1",
                    kind="metadata_only",
                    baseline_hash="H",
                    candidate_hash="H",
                    metadata_delta={"format": ("png", "webp")},
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        assert "format='png'->'webp'" in out

    def test_tags_tuple_of_tuple_uses_repr(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="a1",
                    kind="metadata_only",
                    baseline_hash="H",
                    candidate_hash="H",
                    metadata_delta={"tags": (("alpha",), ("beta",))},
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        assert "tags=('alpha',)->('beta',)" in out

    def test_metadata_delta_keys_sorted(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="a1",
                    kind="metadata_only",
                    baseline_hash="H",
                    candidate_hash="H",
                    metadata_delta={"zeta": ("a", "b"), "alpha": ("x", "y")},
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        a_idx = out.find("alpha=")
        z_idx = out.find("zeta=")
        assert a_idx >= 0 and z_idx >= 0
        assert a_idx < z_idx, "metadata_delta keys must render in sorted order"

    def test_lineage_delta_renders(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="a1",
                    kind="metadata_only",
                    baseline_hash="H",
                    candidate_hash="H",
                    lineage_delta={"selected_by_verdict_id": ("v1", "v2")},
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        assert "selected_by_verdict_id='v1'->'v2'" in out


# ---------------------------------------------------------------------------
# TestRenderMarkdownMetricNoneValues
# ---------------------------------------------------------------------------


class TestRenderMarkdownMetricNoneValues:
    def test_step_metric_one_side_none_renders_dash(self) -> None:
        m = MetricDiff(
            metric="cost_usd",
            scope="step",
            step_id="s1",
            baseline_value=0.10,
            candidate_value=None,
            delta=None,
            delta_pct=None,
        )
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            metric_diffs=[m],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        # Find the cost_usd row and check None placeholders.
        cost_lines = [line for line in out.splitlines() if line.startswith("| cost_usd ")]
        assert cost_lines, "cost_usd row missing in step metrics table"
        # The row contains "0.1" for baseline and three "-" for candidate / delta / delta_pct.
        row = cost_lines[0]
        assert "0.1" in row
        assert row.count(" - ") >= 3
        assert "None" not in row

    def test_run_level_metric_baseline_zero_pct_dash(self) -> None:
        m = MetricDiff(
            metric="cost_usd",
            scope="run",
            step_id=None,
            baseline_value=0.0,
            candidate_value=0.10,
            delta=0.10,
            delta_pct=None,
        )
        out = render_markdown(_make_report(run_level_metric_diffs=[m]))
        run_section = out.split("## Run-level metrics", 1)[1].split("##", 1)[0]
        # delta_pct=None must render as "-", not "None".
        assert "None" not in run_section
        assert " - |" in run_section


# ---------------------------------------------------------------------------
# TestEscapeCell
# ---------------------------------------------------------------------------


class TestEscapeCell:
    def test_none_to_dash(self) -> None:
        assert _escape_cell(None) == "-"

    def test_newline_to_space(self) -> None:
        assert _escape_cell("a\nb") == "a b"

    def test_carriage_return_to_space(self) -> None:
        assert _escape_cell("a\rb") == "a b"

    def test_pipe_escaped(self) -> None:
        assert _escape_cell("a|b") == "a\\|b"

    def test_combined_cr_lf_pipe(self) -> None:
        # CR/LF first -> spaces, then pipe -> "\\|"
        assert _escape_cell("a\r\nb|c") == "a  b\\|c"

    def test_non_ascii_backslash_escaped(self) -> None:
        result = _escape_cell("测试")
        # Must round-trip through ascii-strict encoding.
        result.encode("ascii", errors="strict")
        assert "\\u6d4b" in result
        assert "\\u8bd5" in result

    def test_int_str_passthrough(self) -> None:
        assert _escape_cell(42) == "42"

    def test_empty_string_preserved(self) -> None:
        # Empty string is a valid value distinct from None; the cell renders
        # empty rather than collapsing to "-".
        assert _escape_cell("") == ""


# ---------------------------------------------------------------------------
# TestCountHelper
# ---------------------------------------------------------------------------


class TestCountHelper:
    def test_present_key_returns_value(self) -> None:
        report = _make_report(summary_counts={"artifact:unchanged": 5})
        assert _count(report, "artifact:unchanged") == 5

    def test_absent_key_returns_zero(self) -> None:
        report = _make_report(summary_counts={})
        assert _count(report, "artifact:metadata_only") == 0

    def test_no_keyerror_on_sparse_summary_counts(self) -> None:
        # Critical guard: summary_counts is sparse — kinds that did not
        # appear in this comparison are absent from the dict (NOT zero).
        # _count must always go through .get(key, 0) per D2.
        report = _make_report(summary_counts={})
        for kind in get_args(ArtifactDiffKind):
            assert _count(report, f"artifact:{kind}") == 0
        for kind in get_args(VerdictDiffKind):
            assert _count(report, f"verdict:{kind}") == 0
        assert _count(report, "steps_total") == 0
        assert _count(report, "completely_unknown_key") == 0


# ---------------------------------------------------------------------------
# TestRenderMarkdownReportNotMutated
# ---------------------------------------------------------------------------


class TestRenderMarkdownReportNotMutated:
    def test_render_does_not_mutate_report(self) -> None:
        # D8: reporter must not mutate the RunComparisonReport. Verify by
        # snapshotting model_dump() before and after multiple render passes.
        report = _make_report(
            step_diffs=[_step_with_all_artifact_kinds(), _step_with_all_verdict_kinds()],
            summary_counts={"artifact:unchanged": 1},
        )
        before = report.model_dump()
        render_markdown(report)
        render_json(report)
        render_markdown(report)
        after = report.model_dump()
        assert before == after


# ---------------------------------------------------------------------------
# TestRenderMarkdownGeneratedAtFromReport
# ---------------------------------------------------------------------------


class TestRenderMarkdownGeneratedAtFromReport:
    def test_render_uses_report_generated_at_only(self) -> None:
        # D9: render_* takes no `now` injection — `report.generated_at` is
        # the single source of truth for the timestamp shown in Summary.
        fixed = datetime(2099, 6, 15, 9, 30, 0, tzinfo=UTC)
        report = _make_report(generated_at=fixed)
        out = render_markdown(report)
        assert "2099-06-15T09:30:00+00:00" in out


# ---------------------------------------------------------------------------
# TestWriteReports
# ---------------------------------------------------------------------------


class TestWriteReports:
    def test_returns_two_paths_with_fixed_filenames(self, tmp_path: Path) -> None:
        report = _make_report()
        json_path, md_path = write_reports(report, tmp_path)
        # Fixed filenames per the user-mandated contract.
        assert JSON_FILENAME == "comparison_report.json"
        assert MARKDOWN_FILENAME == "comparison_summary.md"
        assert json_path == tmp_path / JSON_FILENAME
        assert md_path == tmp_path / MARKDOWN_FILENAME
        assert json_path.is_file()
        assert md_path.is_file()

    def test_json_content_matches_render_json(self, tmp_path: Path) -> None:
        report = _make_report()
        json_path, _ = write_reports(report, tmp_path)
        assert json_path.read_text(encoding="utf-8") == render_json(report)

    def test_markdown_content_matches_render_markdown(self, tmp_path: Path) -> None:
        report = _make_report()
        _, md_path = write_reports(report, tmp_path)
        assert md_path.read_text(encoding="utf-8") == render_markdown(report)

    def test_creates_nonexistent_output_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "out"
        assert not target.exists()
        json_path, md_path = write_reports(_make_report(), target)
        assert target.is_dir()
        assert json_path.is_file()
        assert md_path.is_file()

    def test_lf_line_endings_no_crlf(self, tmp_path: Path) -> None:
        # D7: UTF-8 + LF — Windows CRLF would change byte hashes.
        json_path, md_path = write_reports(_make_report(), tmp_path)
        assert b"\r\n" not in json_path.read_bytes()
        assert b"\r\n" not in md_path.read_bytes()
        # Markdown body must also be ASCII-only on disk.
        md_path.read_text(encoding="utf-8").encode("ascii", errors="strict")

    def test_overwrites_existing_files(self, tmp_path: Path) -> None:
        # D10: write_reports overwrites the fixed filenames in place.
        # The CLI is responsible for creating a unique output_dir; the
        # writer itself does not protect against collision.
        write_reports(_make_report(baseline_run_id="OLD_RUN_ID_XYZ"), tmp_path)
        write_reports(_make_report(baseline_run_id="NEW_RUN_ID_ABC"), tmp_path)
        md = (tmp_path / MARKDOWN_FILENAME).read_text(encoding="utf-8")
        assert "OLD_RUN_ID_XYZ" not in md
        assert "NEW_RUN_ID_ABC" in md

    def test_returns_paths_for_chaining(self, tmp_path: Path) -> None:
        # The (json_path, md_path) tuple is the documented return shape (D5);
        # callers rely on positional unpacking.
        result = write_reports(_make_report(), tmp_path)
        assert isinstance(result, tuple)
        assert len(result) == 2
        json_path, md_path = result
        assert isinstance(json_path, Path)
        assert isinstance(md_path, Path)


# ---------------------------------------------------------------------------
# TestReporterImportFence
# ---------------------------------------------------------------------------
#
# Importing framework.comparison.reporter MUST NOT pull in any execution
# layer module, any artifact_store WRITE-side module, NOR the comparison
# loader / diff_engine themselves. The reporter is a strict presentation
# layer over RunComparisonReport — its only framework dependency must be
# framework.comparison.models.

_FORBIDDEN_FRAMEWORK_MODULES_REPORTER: tuple[str, ...] = (
    "framework.comparison.loader",
    "framework.comparison.diff_engine",
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


class TestReporterImportFence:
    def test_reporter_import_does_not_pull_in_forbidden_modules(self) -> None:
        src_dir = Path(__file__).resolve().parents[2] / "src"
        assert (
            src_dir / "framework" / "comparison" / "reporter.py"
        ).is_file(), f"cannot locate framework.comparison.reporter under {src_dir}"

        probe = (
            "import sys\n"
            f"sys.path.insert(0, {str(src_dir)!r})\n"
            "import framework.comparison.reporter  # noqa: F401\n"
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

        for forbidden in _FORBIDDEN_FRAMEWORK_MODULES_REPORTER:
            leaked = [m for m in loaded if m == forbidden or m.startswith(forbidden + ".")]
            assert not leaked, (
                f"framework.comparison.reporter transitively imported "
                f"forbidden module(s): {leaked}. Reporter must stay a pure "
                f"presentation layer with no loader / diff engine / execution "
                f"layer dependency."
            )

        # Sanity: reporter and its sole framework dep loaded.
        assert "framework.comparison" in loaded
        assert "framework.comparison.reporter" in loaded
        assert "framework.comparison.models" in loaded


# ---------------------------------------------------------------------------
# TestReporterImportFenceViaLazyPublicExport
# ---------------------------------------------------------------------------
#
# Direct `import framework.comparison.reporter` is one entry path. The
# package also exposes the same symbols via lazy `__getattr__` lookup on
# `framework.comparison`, which is what the public API documents:
#
#     from framework.comparison import render_markdown, write_reports
#
# The lazy path triggers `__getattr__` -> `from framework.comparison import
# reporter`, so it must satisfy the same import fence: no loader /
# diff_engine / execution layer / artifact_store write-side leakage. This
# test independently verifies the lazy path so a future refactor of
# `__init__.py` cannot silently widen the dependency surface.


class TestReporterImportFenceViaLazyPublicExport:
    def test_lazy_public_export_does_not_pull_in_forbidden_modules(self) -> None:
        src_dir = Path(__file__).resolve().parents[2] / "src"
        probe = (
            "import sys\n"
            f"sys.path.insert(0, {str(src_dir)!r})\n"
            "from framework.comparison import render_markdown, write_reports  # noqa: F401\n"
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

        for forbidden in _FORBIDDEN_FRAMEWORK_MODULES_REPORTER:
            leaked = [m for m in loaded if m == forbidden or m.startswith(forbidden + ".")]
            assert not leaked, (
                f"lazy public export `from framework.comparison import "
                f"render_markdown, write_reports` transitively imported "
                f"forbidden module(s): {leaked}. The lazy `__getattr__` path "
                f"must not widen the reporter import surface."
            )

        assert "framework.comparison" in loaded
        assert "framework.comparison.reporter" in loaded
        assert "framework.comparison.models" in loaded


# ---------------------------------------------------------------------------
# TestLineSafe
# ---------------------------------------------------------------------------


class TestLineSafe:
    def test_none_to_dash(self) -> None:
        assert _line_safe(None) == "-"

    def test_newline_to_space(self) -> None:
        assert _line_safe("a\nb") == "a b"

    def test_carriage_return_to_space(self) -> None:
        assert _line_safe("a\rb") == "a b"

    def test_crlf_collapses_to_two_spaces(self) -> None:
        # Two-pass replace: \r -> " " first (still leaves \n), then \n -> " ".
        # So a literal CRLF produces two consecutive spaces. This is fine for
        # safety (single-line invariant preserved) and matches `_escape_cell`.
        assert _line_safe("a\r\nb") == "a  b"

    def test_pipe_not_escaped_in_line_safe(self) -> None:
        # Divergence from `_escape_cell`: non-table contexts have no column
        # boundary, so a literal pipe is preserved verbatim.
        assert _line_safe("a|b") == "a|b"

    def test_non_ascii_backslash_escaped(self) -> None:
        result = _line_safe("测试")
        result.encode("ascii", errors="strict")
        assert "\\u6d4b" in result
        assert "\\u8bd5" in result

    def test_int_str_passthrough(self) -> None:
        assert _line_safe(42) == "42"

    def test_empty_string_preserved(self) -> None:
        assert _line_safe("") == ""


# ---------------------------------------------------------------------------
# TestRenderMarkdownLineSafetyForNonTableValues
# ---------------------------------------------------------------------------


class TestRenderMarkdownLineSafetyForNonTableValues:
    def test_run_id_with_newline_does_not_split_header(self) -> None:
        report = _make_report(
            baseline_run_id="run\nbaseline",
            candidate_run_id="run\r\ncandidate",
        )
        out = render_markdown(report)
        # Exactly one header line is emitted regardless of embedded CR/LF.
        header_lines = [line for line in out.splitlines() if line.startswith("# Run Comparison:")]
        assert len(header_lines) == 1
        # \n  -> single space; \r\n -> two consecutive spaces (two-pass replace).
        h = header_lines[0]
        assert "baseline=run baseline " in h
        assert "candidate=run  candidate" in h

    def test_step_id_with_newline_does_not_split_heading(self) -> None:
        sd = StepDiff(
            step_id="s\n1",
            status_baseline="succeeded",
            status_candidate="succeeded",
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        # The `### step_<id>` heading must remain a single line.
        heading_lines = [line for line in out.splitlines() if line.startswith("### step_")]
        assert len(heading_lines) == 1
        assert heading_lines[0] == "### step_s 1"

    def test_anomaly_note_with_newline_does_not_split_bullet(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="a1",
                    kind="payload_missing_on_disk",
                    baseline_hash="H",
                    candidate_hash="H",
                    note="payload\nmissing\non disk",
                ),
            ],
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        anomalies = out.split("## Anomalies", 1)[1]
        bullet_lines = [line for line in anomalies.splitlines() if line.startswith("- step=")]
        # Exactly one anomaly bullet despite two embedded "\n" in the note.
        assert len(bullet_lines) == 1
        assert "note=payload missing on disk" in bullet_lines[0]

    def test_baseline_meta_status_with_crlf_does_not_split_bullet(self) -> None:
        report = _make_report(
            baseline_run_meta={"run_id": "run_a", "status": "succeed\r\ned"},
        )
        out = render_markdown(report)
        baseline_lines = [line for line in out.splitlines() if line.startswith("- Baseline:")]
        assert len(baseline_lines) == 1
        # CRLF -> two consecutive spaces (matches _escape_cell semantics).
        assert "status=succeed  ed" in baseline_lines[0]

    def test_chosen_model_with_newline_does_not_split_bullet(self) -> None:
        sd = StepDiff(
            step_id="s1",
            status_baseline="succeeded",
            status_candidate="succeeded",
            chosen_model_baseline="model\nA",
            chosen_model_candidate="model\r\nB",
        )
        out = render_markdown(_make_report(step_diffs=[sd]))
        chosen_lines = [line for line in out.splitlines() if line.startswith("- chosen_model:")]
        assert len(chosen_lines) == 1
        assert "model A -> model  B" in chosen_lines[0]

    def test_full_report_with_crlf_remains_ascii_only(self) -> None:
        # End-to-end: every non-table dynamic surface contains CR/LF, and
        # the rendered Markdown must remain ASCII-only AND single-line per
        # logical entry.
        sd = StepDiff(
            step_id="s\n1",
            status_baseline="succ\reeded",
            status_candidate="succeeded",
            chosen_model_baseline="model\nX",
            chosen_model_candidate=None,
            artifact_diffs=[
                ArtifactDiff(
                    artifact_id="a\r\n1",
                    kind="payload_missing_on_disk",
                    baseline_hash="H",
                    candidate_hash="H",
                    note="bad\r\nnote",
                ),
            ],
        )
        report = _make_report(
            baseline_run_id="run\nbaseline",
            step_diffs=[sd],
            baseline_run_meta={"run_id": "run\nbaseline", "status": "succ\reeded"},
        )
        out = render_markdown(report)
        # ASCII-only invariant holds.
        out.encode("ascii", errors="strict")
        # No accidental new-section headings produced by an injected newline.
        assert out.count("# Run Comparison:") == 1
        assert out.count("## Summary") == 1
        assert out.count("### step_") == 1
        # Anomaly carries the (folded) tampered note exactly once.
        anomalies = out.split("## Anomalies", 1)[1]
        bullet_lines = [line for line in anomalies.splitlines() if line.startswith("- step=")]
        assert len(bullet_lines) == 1


# ---------------------------------------------------------------------------
# TestRenderMarkdownTrailingNewline
# ---------------------------------------------------------------------------


class TestRenderMarkdownTrailingNewline:
    def test_empty_report_ends_with_exactly_one_newline(self) -> None:
        out = render_markdown(_make_report())
        assert out.endswith("\n")
        assert not out.endswith("\n\n")

    def test_full_report_ends_with_exactly_one_newline(self) -> None:
        out = render_markdown(
            _make_report(
                step_diffs=[
                    _step_with_all_artifact_kinds(),
                    _step_with_all_verdict_kinds(),
                ],
                summary_counts={"steps_total": 2, "artifact:unchanged": 1},
            )
        )
        assert out.endswith("\n")
        assert not out.endswith("\n\n")
