"""Unit tests for framework.comparison.cli.

The CLI is a pure orchestration layer over loader / diff_engine / reporter.
Tests construct minimal Run directories under `tmp_path` (no shared
fixtures — those land in Task 6) and exercise `main(argv, *, now=...)`
directly so exit codes can be asserted without process boundary tricks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from framework.comparison.cli import (
    _build_input,
    _build_parser,
    _console_safe,
    _render_only_json,
    _render_only_markdown,
    _resolve_default_output_dir,
    _safe_path_segment,
    main,
)
from framework.comparison.models import RunComparisonInput
from framework.comparison.reporter import JSON_FILENAME, MARKDOWN_FILENAME
from framework.core.artifact import (
    Artifact,
    ArtifactType,
    Lineage,
    PayloadRef,
    ProducerRef,
    ValidationRecord,
)
from framework.core.enums import ArtifactRole, PayloadKind

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIXED_NOW = datetime(2099, 6, 15, 9, 30, 45)


def _now_fixed() -> datetime:
    return _FIXED_NOW


def _write_run_dir(
    artifact_root: Path,
    *,
    run_id: str,
    date_bucket: str = "2000-01-01",
    status: str = "succeeded",
    artifacts: list[dict[str, Any]] | None = None,
) -> Path:
    run_dir = artifact_root / date_bucket / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_summary.json").write_text(
        json.dumps({"run_id": run_id, "status": status}),
        encoding="utf-8",
    )
    (run_dir / "_artifacts.json").write_text(
        json.dumps(artifacts or []),
        encoding="utf-8",
    )
    return run_dir


def _make_file_artifact_entry(
    *,
    aid: str,
    run_id: str,
    step_id: str = "s1",
    file_path: str | None = None,
    hash_str: str = "h1",
) -> dict[str, Any]:
    art = Artifact(
        artifact_id=aid,
        artifact_type=ArtifactType(modality="image", shape="png", display_name="image.png"),
        role=ArtifactRole.intermediate,
        format="png",
        mime_type="image/png",
        payload_ref=PayloadRef(
            kind=PayloadKind.file,
            file_path=file_path or f"{run_id}/{aid}.bin",
            size_bytes=4,
        ),
        schema_version="1.0.0",
        hash=hash_str,
        producer=ProducerRef(run_id=run_id, step_id=step_id),
        lineage=Lineage(),
        metadata={},
        tags=[],
        validation=ValidationRecord(status="pending"),
        created_at=datetime(2000, 1, 1, tzinfo=UTC),
    )
    return art.model_dump(mode="json")


def _basic_argv(
    artifact_root: Path,
    *,
    baseline: str = "run_a",
    candidate: str = "run_b",
    output_dir: Path | None = None,
    extra: list[str] | None = None,
) -> list[str]:
    argv = [
        "--artifact-root",
        str(artifact_root),
        "--baseline-run",
        baseline,
        "--candidate-run",
        candidate,
    ]
    if output_dir is not None:
        argv += ["--output-dir", str(output_dir)]
    if extra:
        argv += extra
    return argv


# ---------------------------------------------------------------------------
# TestSafePathSegment
# ---------------------------------------------------------------------------


class TestSafePathSegment:
    def test_slash(self) -> None:
        assert _safe_path_segment("a/b") == "a_b"

    def test_backslash(self) -> None:
        assert _safe_path_segment("a\\b") == "a_b"

    def test_colon(self) -> None:
        assert _safe_path_segment("c:run") == "c_run"

    def test_newline(self) -> None:
        assert _safe_path_segment("a\nb") == "a_b"

    def test_carriage_return(self) -> None:
        assert _safe_path_segment("a\rb") == "a_b"

    def test_crlf_double_underscore(self) -> None:
        # \r and \n are replaced sequentially -> two underscores.
        assert _safe_path_segment("a\r\nb") == "a__b"

    def test_empty_to_underscore(self) -> None:
        assert _safe_path_segment("") == "_"

    def test_combined_chars(self) -> None:
        assert _safe_path_segment("a/b\\c:d\ne") == "a_b_c_d_e"

    def test_safe_passthrough(self) -> None:
        # Common run_id characters survive untouched.
        assert _safe_path_segment("run_abc-123.v2") == "run_abc-123.v2"


# ---------------------------------------------------------------------------
# TestBuildParser
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_baseline_run_required(self) -> None:
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--candidate-run", "b"])

    def test_candidate_run_required(self) -> None:
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--baseline-run", "a"])

    def test_artifact_root_default_artifacts(self) -> None:
        parser = _build_parser()
        ns = parser.parse_args(["--baseline-run", "a", "--candidate-run", "b"])
        assert ns.artifact_root == Path("./artifacts")

    def test_default_flag_states(self) -> None:
        parser = _build_parser()
        ns = parser.parse_args(["--baseline-run", "a", "--candidate-run", "b"])
        assert ns.no_hash_check is False
        assert ns.non_strict is False
        assert ns.json_only is False
        assert ns.markdown_only is False
        assert ns.quiet is False
        assert ns.baseline_date is None
        assert ns.candidate_date is None
        assert ns.output_dir is None


# ---------------------------------------------------------------------------
# TestBuildInput
# ---------------------------------------------------------------------------


class TestBuildInput:
    def test_default_flags_to_input(self, tmp_path: Path) -> None:
        parser = _build_parser()
        ns = parser.parse_args(
            [
                "--artifact-root",
                str(tmp_path),
                "--baseline-run",
                "a",
                "--candidate-run",
                "b",
            ]
        )
        inp = _build_input(ns)
        assert inp.baseline_run_id == "a"
        assert inp.candidate_run_id == "b"
        assert inp.artifact_root == tmp_path
        assert inp.baseline_date_bucket is None
        assert inp.candidate_date_bucket is None
        assert inp.strict is True
        assert inp.include_payload_hash_check is True

    def test_non_strict_flips_strict(self, tmp_path: Path) -> None:
        parser = _build_parser()
        ns = parser.parse_args(
            [
                "--artifact-root",
                str(tmp_path),
                "--baseline-run",
                "a",
                "--candidate-run",
                "b",
                "--non-strict",
            ]
        )
        inp = _build_input(ns)
        assert inp.strict is False

    def test_no_hash_check_flips_hash_check(self, tmp_path: Path) -> None:
        parser = _build_parser()
        ns = parser.parse_args(
            [
                "--artifact-root",
                str(tmp_path),
                "--baseline-run",
                "a",
                "--candidate-run",
                "b",
                "--no-hash-check",
            ]
        )
        inp = _build_input(ns)
        assert inp.include_payload_hash_check is False

    def test_dates_passthrough(self, tmp_path: Path) -> None:
        parser = _build_parser()
        ns = parser.parse_args(
            [
                "--artifact-root",
                str(tmp_path),
                "--baseline-run",
                "a",
                "--candidate-run",
                "b",
                "--baseline-date",
                "2020-01-01",
                "--candidate-date",
                "2020-02-02",
            ]
        )
        inp = _build_input(ns)
        assert inp.baseline_date_bucket == "2020-01-01"
        assert inp.candidate_date_bucket == "2020-02-02"


# ---------------------------------------------------------------------------
# TestResolveDefaultOutputDir
# ---------------------------------------------------------------------------


class TestResolveDefaultOutputDir:
    def test_path_structure_basic(self) -> None:
        inp = RunComparisonInput(
            baseline_run_id="run_a",
            candidate_run_id="run_b",
            artifact_root=Path("./artifacts"),
        )
        out = _resolve_default_output_dir(inp, _FIXED_NOW)
        parts = out.parts
        assert "demo_artifacts" in parts
        assert "2099-06-15" in parts
        assert "comparison" in parts
        assert "run_a__vs__run_b" in parts
        assert "093045" in parts

    def test_unsafe_chars_in_run_id_are_sanitized_in_path_only(self) -> None:
        # Slash / backslash / colon must be replaced in the path segment,
        # but the original RunComparisonInput keeps the verbatim run_id.
        inp = RunComparisonInput(
            baseline_run_id="run/a",
            candidate_run_id="run\\b:x",
            artifact_root=Path("./artifacts"),
        )
        out = _resolve_default_output_dir(inp, _FIXED_NOW)
        assert "run_a__vs__run_b_x" in out.parts
        # Raw run_id strings are NOT mutated.
        assert inp.baseline_run_id == "run/a"
        assert inp.candidate_run_id == "run\\b:x"


# ---------------------------------------------------------------------------
# TestCliHappyPath
# ---------------------------------------------------------------------------


class TestCliHappyPath:
    def test_exit_zero_with_default_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")

        # Switch cwd so the default ./demo_artifacts/ lands inside tmp_path.
        monkeypatch.chdir(tmp_path)
        rc = main(_basic_argv(artifact_root), now=_now_fixed)
        assert rc == 0

        out_dir = tmp_path / "demo_artifacts" / "2099-06-15" / "comparison" / "run_a__vs__run_b" / "093045"
        assert (out_dir / JSON_FILENAME).is_file()
        assert (out_dir / MARKDOWN_FILENAME).is_file()

    def test_exit_zero_with_explicit_output(self, tmp_path: Path) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"

        rc = main(_basic_argv(artifact_root, output_dir=out_dir), now=_now_fixed)
        assert rc == 0
        assert (out_dir / JSON_FILENAME).is_file()
        assert (out_dir / MARKDOWN_FILENAME).is_file()

    def test_json_content_parses_and_carries_schema_version(self, tmp_path: Path) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        main(_basic_argv(artifact_root, output_dir=out_dir), now=_now_fixed)
        parsed = json.loads((out_dir / JSON_FILENAME).read_text(encoding="utf-8"))
        assert parsed["schema_version"] == "1"
        assert parsed["input"]["baseline_run_id"] == "run_a"
        assert parsed["input"]["candidate_run_id"] == "run_b"


# ---------------------------------------------------------------------------
# TestCliRunDirNotFound
# ---------------------------------------------------------------------------


class TestCliRunDirNotFound:
    def test_baseline_not_found_returns_2(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        artifact_root = tmp_path / "artifacts"
        artifact_root.mkdir()
        # Only candidate exists; baseline missing.
        _write_run_dir(artifact_root, run_id="run_b")
        rc = main(_basic_argv(artifact_root), now=_now_fixed)
        assert rc == 2
        captured = capsys.readouterr()
        assert "RunDirNotFound" in captured.err


# ---------------------------------------------------------------------------
# TestCliRunDirAmbiguous
# ---------------------------------------------------------------------------


class TestCliRunDirAmbiguous:
    def test_ambiguous_returns_2_with_disambiguation_hint(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        artifact_root = tmp_path / "artifacts"
        # Same baseline run_id under two date buckets -> RunDirAmbiguous.
        _write_run_dir(artifact_root, run_id="run_a", date_bucket="2000-01-01")
        _write_run_dir(artifact_root, run_id="run_a", date_bucket="2001-02-02")
        _write_run_dir(artifact_root, run_id="run_b", date_bucket="2000-01-01")
        rc = main(_basic_argv(artifact_root), now=_now_fixed)
        assert rc == 2
        captured = capsys.readouterr()
        assert "RunDirAmbiguous" in captured.err
        assert "--baseline-date" in captured.err

    def test_ambiguous_resolved_by_explicit_date(self, tmp_path: Path) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a", date_bucket="2000-01-01")
        _write_run_dir(artifact_root, run_id="run_a", date_bucket="2001-02-02")
        _write_run_dir(artifact_root, run_id="run_b", date_bucket="2000-01-01")
        out_dir = tmp_path / "out"
        rc = main(
            _basic_argv(
                artifact_root,
                output_dir=out_dir,
                extra=["--baseline-date", "2000-01-01"],
            ),
            now=_now_fixed,
        )
        assert rc == 0


# ---------------------------------------------------------------------------
# TestCliRunSnapshotCorrupt
# ---------------------------------------------------------------------------


class TestCliRunSnapshotCorrupt:
    def test_run_summary_missing_status_returns_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        artifact_root = tmp_path / "artifacts"
        # Hand-write a run_summary.json without the required `status` field.
        run_a = artifact_root / "2000-01-01" / "run_a"
        run_a.mkdir(parents=True)
        (run_a / "run_summary.json").write_text(
            json.dumps({"run_id": "run_a"}),  # status absent -> corrupt
            encoding="utf-8",
        )
        (run_a / "_artifacts.json").write_text("[]", encoding="utf-8")
        _write_run_dir(artifact_root, run_id="run_b")

        rc = main(_basic_argv(artifact_root), now=_now_fixed)
        assert rc == 2
        captured = capsys.readouterr()
        assert "RunSnapshotCorrupt" in captured.err


# ---------------------------------------------------------------------------
# TestCliPayloadMissingStrict
# ---------------------------------------------------------------------------


class TestCliPayloadMissingStrict:
    def test_strict_payload_missing_returns_3(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        artifact_root = tmp_path / "artifacts"
        # baseline has an artifact whose payload file is NOT created on disk.
        _write_run_dir(
            artifact_root,
            run_id="run_a",
            artifacts=[_make_file_artifact_entry(aid="a1", run_id="run_a")],
        )
        _write_run_dir(artifact_root, run_id="run_b")
        rc = main(_basic_argv(artifact_root), now=_now_fixed)
        assert rc == 3
        captured = capsys.readouterr()
        assert "PayloadMissingOnDisk" in captured.err


# ---------------------------------------------------------------------------
# TestCliPayloadMissingNonStrict
# ---------------------------------------------------------------------------


class TestCliPayloadMissingNonStrict:
    def test_non_strict_payload_missing_returns_0_and_records_anomaly(self, tmp_path: Path) -> None:
        # diff_engine emits kind="payload_missing_on_disk" only when BOTH
        # sides have the artifact entry (single-sided cases collapse to
        # missing_in_baseline / missing_in_candidate first). Put the same
        # artifact on both sides, with neither payload file written to disk.
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(
            artifact_root,
            run_id="run_a",
            artifacts=[_make_file_artifact_entry(aid="a1", run_id="run_a")],
        )
        _write_run_dir(
            artifact_root,
            run_id="run_b",
            artifacts=[_make_file_artifact_entry(aid="a1", run_id="run_b")],
        )
        out_dir = tmp_path / "out"
        rc = main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--non-strict"]),
            now=_now_fixed,
        )
        assert rc == 0
        # summary_counts is sparse: the kind only appears when at least
        # one such diff was produced.
        report = json.loads((out_dir / JSON_FILENAME).read_text(encoding="utf-8"))
        assert report["summary_counts"].get("artifact:payload_missing_on_disk", 0) == 1

    def test_non_strict_baseline_only_artifact_with_missing_payload_is_missing_in_candidate(
        self, tmp_path: Path
    ) -> None:
        # Sanity: when only baseline has the artifact entry AND its payload
        # is missing on disk, --non-strict still completes cleanly (exit 0)
        # and the diff is classified as missing_in_candidate (single-sided
        # absence wins over the payload-missing classification per the
        # diff_engine precedence rules).
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(
            artifact_root,
            run_id="run_a",
            artifacts=[_make_file_artifact_entry(aid="a1", run_id="run_a")],
        )
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        rc = main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--non-strict"]),
            now=_now_fixed,
        )
        assert rc == 0
        report = json.loads((out_dir / JSON_FILENAME).read_text(encoding="utf-8"))
        assert report["summary_counts"].get("artifact:missing_in_candidate", 0) == 1


# ---------------------------------------------------------------------------
# TestCliJsonOnly
# ---------------------------------------------------------------------------


class TestCliJsonOnly:
    def test_json_only_writes_only_json(self, tmp_path: Path) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        rc = main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--json-only"]),
            now=_now_fixed,
        )
        assert rc == 0
        assert (out_dir / JSON_FILENAME).is_file()
        assert not (out_dir / MARKDOWN_FILENAME).exists()

    def test_json_only_uses_reporter_filename_constant(self, tmp_path: Path) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--json-only"]),
            now=_now_fixed,
        )
        # Sanity: filename equals the reporter constant, not a CLI invention.
        assert (out_dir / "comparison_report.json").is_file()
        assert JSON_FILENAME == "comparison_report.json"

    def test_json_only_byte_identical_to_render_json(self, tmp_path: Path) -> None:
        # The CLI's --json-only path must produce exactly the same bytes as
        # render_json(report) (same trailing newline, same encoding) — i.e.
        # the CLI does NOT re-implement render logic.
        from framework.comparison.reporter import render_json

        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--json-only"]),
            now=_now_fixed,
        )
        on_disk = (out_dir / JSON_FILENAME).read_text(encoding="utf-8")
        # Re-parse + re-render: the in-memory report rebuilt from disk must
        # round-trip to the same bytes (same `model_dump_json(indent=2)+"\n"`).
        from framework.comparison.models import RunComparisonReport

        parsed = RunComparisonReport.model_validate_json(on_disk)
        assert on_disk == render_json(parsed)


# ---------------------------------------------------------------------------
# TestCliMarkdownOnly
# ---------------------------------------------------------------------------


class TestCliMarkdownOnly:
    def test_markdown_only_writes_only_markdown(self, tmp_path: Path) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        rc = main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--markdown-only"]),
            now=_now_fixed,
        )
        assert rc == 0
        assert (out_dir / MARKDOWN_FILENAME).is_file()
        assert not (out_dir / JSON_FILENAME).exists()

    def test_markdown_only_uses_reporter_filename_constant(self, tmp_path: Path) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--markdown-only"]),
            now=_now_fixed,
        )
        assert (out_dir / "comparison_summary.md").is_file()
        assert MARKDOWN_FILENAME == "comparison_summary.md"


# ---------------------------------------------------------------------------
# TestCliJsonAndMarkdownMutuallyExclusive
# ---------------------------------------------------------------------------


class TestCliJsonAndMarkdownMutuallyExclusive:
    def test_both_flags_argparse_exits_2(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        artifact_root = tmp_path / "artifacts"
        artifact_root.mkdir()
        with pytest.raises(SystemExit) as exc_info:
            main(
                _basic_argv(artifact_root, extra=["--json-only", "--markdown-only"]),
                now=_now_fixed,
            )
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        # argparse writes the mutually-exclusive error to stderr.
        err_lower = captured.err.lower()
        assert "not allowed with argument" in err_lower or "mutually exclusive" in err_lower


# ---------------------------------------------------------------------------
# TestCliQuietMode
# ---------------------------------------------------------------------------


class TestCliQuietMode:
    def test_default_stdout_has_summary(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        main(_basic_argv(artifact_root, output_dir=out_dir), now=_now_fixed)
        captured = capsys.readouterr()
        assert "[OK] Run comparison complete" in captured.out
        assert "status_match" in captured.out
        assert "steps_total" in captured.out
        # Both file paths surface.
        assert str(out_dir / JSON_FILENAME) in captured.out
        assert str(out_dir / MARKDOWN_FILENAME) in captured.out

    def test_quiet_stdout_only_paths(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--quiet"]),
            now=_now_fixed,
        )
        captured = capsys.readouterr()
        assert "[OK]" not in captured.out
        assert "status_match" not in captured.out
        # Both file paths still present.
        assert str(out_dir / JSON_FILENAME) in captured.out
        assert str(out_dir / MARKDOWN_FILENAME) in captured.out

    def test_quiet_with_json_only_emits_one_path(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--quiet", "--json-only"]),
            now=_now_fixed,
        )
        captured = capsys.readouterr()
        assert str(out_dir / JSON_FILENAME) in captured.out
        # Markdown was not written, so its filename must NOT appear in stdout.
        assert MARKDOWN_FILENAME not in captured.out

    def test_quiet_with_markdown_only_emits_one_path(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--quiet", "--markdown-only"]),
            now=_now_fixed,
        )
        captured = capsys.readouterr()
        assert str(out_dir / MARKDOWN_FILENAME) in captured.out
        assert JSON_FILENAME not in captured.out


# ---------------------------------------------------------------------------
# TestCliUnexpectedException
# ---------------------------------------------------------------------------


class TestCliUnexpectedException:
    def test_unknown_exception_returns_1(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")

        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("simulated catastrophic failure")

        # Patch the symbol bound inside cli.py (it imported `compare`
        # from diff_engine, so the bound name is framework.comparison.cli.compare).
        monkeypatch.setattr("framework.comparison.cli.compare", _boom)

        rc = main(
            _basic_argv(artifact_root, output_dir=tmp_path / "out"),
            now=_now_fixed,
        )
        assert rc == 1
        captured = capsys.readouterr()
        assert "RuntimeError" in captured.err
        assert "simulated catastrophic failure" in captured.err


# ---------------------------------------------------------------------------
# TestCliRenderOnlyHelpers
# ---------------------------------------------------------------------------


class TestCliRenderOnlyHelpers:
    def test_render_only_json_creates_dir_and_file(self, tmp_path: Path) -> None:
        from framework.comparison.models import RunComparisonReport

        report = RunComparisonReport(
            input=RunComparisonInput(
                baseline_run_id="a",
                candidate_run_id="b",
                artifact_root=Path("./artifacts"),
            ),
            status_match=True,
            generated_at=datetime(2000, 1, 1, tzinfo=UTC),
        )
        target = tmp_path / "nested" / "out"
        json_path = _render_only_json(report, target)
        assert json_path == target / JSON_FILENAME
        assert json_path.is_file()
        # LF line endings preserved.
        assert b"\r\n" not in json_path.read_bytes()

    def test_render_only_markdown_creates_dir_and_file(self, tmp_path: Path) -> None:
        from framework.comparison.models import RunComparisonReport

        report = RunComparisonReport(
            input=RunComparisonInput(
                baseline_run_id="a",
                candidate_run_id="b",
                artifact_root=Path("./artifacts"),
            ),
            status_match=True,
            generated_at=datetime(2000, 1, 1, tzinfo=UTC),
        )
        target = tmp_path / "nested" / "out"
        md_path = _render_only_markdown(report, target)
        assert md_path == target / MARKDOWN_FILENAME
        assert md_path.is_file()
        assert b"\r\n" not in md_path.read_bytes()


# ---------------------------------------------------------------------------
# TestCliMainAsModule
# ---------------------------------------------------------------------------


class TestCliMainAsModule:
    def test_module_help_runs_clean(self) -> None:
        # `python -m framework.comparison --help` must invoke argparse's
        # built-in help (exit 0) without importing any forbidden module.
        # Use PYTHONPATH so the subprocess can find framework regardless of
        # whether the project was installed editable.
        src_dir = Path(__file__).resolve().parents[2] / "src"
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(src_dir) + (os.pathsep + existing if existing else "")
        result = subprocess.run(
            [sys.executable, "-m", "framework.comparison", "--help"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, f"--help exited {result.returncode}; stderr={result.stderr!r}"
        assert "--baseline-run" in result.stdout
        assert "--candidate-run" in result.stdout


# ---------------------------------------------------------------------------
# TestCliImportFence
# ---------------------------------------------------------------------------
#
# CLI import-fence is intentionally aligned with the Task 2 loader fence,
# NOT with the stricter reporter / diff_engine fence. Background:
#
# - The CLI must depend on `framework.comparison.loader` to do its job
#   (resolve_run_dir + load_run_snapshot are its core orchestration).
# - The loader currently imports `framework.artifact_store.hashing` to
#   recompute payload byte hashes. Python's package import semantics
#   require executing `framework/artifact_store/__init__.py` before any
#   submodule import resolves.
# - The current `framework/artifact_store/__init__.py` eager-imports
#   `repository`, `payload_backends`, `lineage`, and `variant_tracker` to
#   expose the artifact_store public API. Therefore importing
#   `framework.artifact_store.hashing` transitively pulls
#   `framework.artifact_store.repository` and
#   `framework.artifact_store.payload_backends` into `sys.modules`.
# - This is NOT a license for the CLI to call `ArtifactRepository.put`,
#   any payload backend write path, or any artifact_store write operation;
#   it is purely an acceptance of the import surface the current package
#   structure makes inevitable. CLI source code remains forbidden from
#   directly invoking write-side APIs, runtime executors, providers,
#   review engine, ue_bridge, or workflows.
# - A future OpenSpec change `lazy-artifact-store-package-exports` is
#   tracked as Known follow-up to evaluate converting the artifact_store
#   package init to PEP 562 lazy exports. Until then this fence stays
#   aligned with the loader's fence.

_FORBIDDEN_FRAMEWORK_MODULES_CLI: tuple[str, ...] = (
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


class TestCliImportFence:
    def test_cli_import_does_not_pull_in_execution_layers(self) -> None:
        """Verify importing `framework.comparison.cli` does not pull in any
        execution-layer module.

        The forbidden list deliberately excludes
        `framework.artifact_store.repository` and
        `framework.artifact_store.payload_backends` because they are
        transitively imported by `framework.artifact_store.hashing` (which
        the loader genuinely needs) — the current
        `framework/artifact_store/__init__.py` eager-imports them as part
        of its public API surface, so banning them here would penalize CLI
        for an existing package-init structure decision rather than for a
        real CLI dependency. The Task 2 loader fence makes the same
        carve-out for the same reason; CLI fence aligns with it.

        See Known follow-up `lazy-artifact-store-package-exports` for the
        proposed structural fix.
        """
        src_dir = Path(__file__).resolve().parents[2] / "src"
        assert (src_dir / "framework" / "comparison" / "cli.py").is_file()

        probe = (
            "import sys\n"
            f"sys.path.insert(0, {str(src_dir)!r})\n"
            "import framework.comparison.cli  # noqa: F401\n"
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

        for forbidden in _FORBIDDEN_FRAMEWORK_MODULES_CLI:
            leaked = [m for m in loaded if m == forbidden or m.startswith(forbidden + ".")]
            assert not leaked, (
                f"framework.comparison.cli pulled forbidden execution-layer "
                f"module(s): {leaked}. CLI must remain a read-only "
                f"orchestration over loader / diff_engine / reporter."
            )

        # Sanity: cli + its declared deps all load.
        assert "framework.comparison.cli" in loaded
        assert "framework.comparison.loader" in loaded
        assert "framework.comparison.diff_engine" in loaded
        assert "framework.comparison.reporter" in loaded
        assert "framework.comparison.models" in loaded


# ---------------------------------------------------------------------------
# TestConsoleSafe
# ---------------------------------------------------------------------------


class TestConsoleSafe:
    def test_none_to_dash(self) -> None:
        assert _console_safe(None) == "-"

    def test_pure_ascii_passthrough(self) -> None:
        assert _console_safe("abc def") == "abc def"

    def test_int_str_coerced(self) -> None:
        assert _console_safe(42) == "42"

    def test_bool_str_coerced(self) -> None:
        assert _console_safe(True) == "True"

    def test_non_ascii_to_unicode_escape(self) -> None:
        result = _console_safe("测试")
        result.encode("ascii", errors="strict")
        assert "\\u6d4b" in result
        assert "\\u8bd5" in result

    def test_emoji_to_unicode_escape(self) -> None:
        # Emoji surface as backslash-escaped sequences (\\UXXXXXXXX or
        # surrogate pairs depending on platform). The contract: output is
        # pure ASCII, with the original codepoint not embedded raw.
        result = _console_safe("ok ✅")
        result.encode("ascii", errors="strict")
        assert "ok " in result
        # The check-mark codepoint U+2705 is not present as a raw character.
        assert "✅" not in result

    def test_newline_to_visible_two_char_sequence(self) -> None:
        # The output must NOT contain a real \n; instead it carries the
        # two literal characters: backslash + n.
        result = _console_safe("abc\ndef")
        assert "\n" not in result
        assert result == "abc\\ndef"

    def test_carriage_return_to_visible_two_char_sequence(self) -> None:
        result = _console_safe("abc\rdef")
        assert "\r" not in result
        assert result == "abc\\rdef"

    def test_crlf_to_visible_four_char_sequence(self) -> None:
        # \r and \n are independently rewritten -> "\\r\\n".
        result = _console_safe("abc\r\ndef")
        assert "\r" not in result
        assert "\n" not in result
        assert result == "abc\\r\\ndef"

    def test_combined_non_ascii_and_crlf(self) -> None:
        # Non-ASCII first via backslashreplace, then CR/LF rewrite. The
        # final output must be ASCII-only and single-line.
        result = _console_safe("测试\n失败")
        result.encode("ascii", errors="strict")
        assert "\n" not in result
        assert "\r" not in result
        assert "\\u6d4b" in result
        assert "\\u8bd5" in result
        assert "\\n" in result


# ---------------------------------------------------------------------------
# TestCliConsoleAsciiSafetyEndToEnd
# ---------------------------------------------------------------------------


class TestCliConsoleAsciiSafetyEndToEnd:
    def test_non_ascii_run_id_stdout_is_ascii_only(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Even when the user passes a non-ASCII run_id, stdout must remain
        # ASCII-only so a Windows GBK terminal / a script consumer never
        # sees a raw non-ASCII byte.
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_测试_a")
        _write_run_dir(artifact_root, run_id="run_b")
        out_dir = tmp_path / "out"
        rc = main(
            _basic_argv(artifact_root, baseline="run_测试_a", output_dir=out_dir),
            now=_now_fixed,
        )
        assert rc == 0
        captured = capsys.readouterr()
        # stdout: pure ASCII; the non-ASCII codepoint surfaces as \uXXXX.
        captured.out.encode("ascii", errors="strict")
        assert "\\u6d4b" in captured.out
        assert "\\u8bd5" in captured.out

    def test_print_error_handles_multiline_non_ascii_exception(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Simulate the loader.RunSnapshotCorrupt-wrapping-Pydantic case
        # via a monkeypatched compare that raises with a multi-line, mixed
        # ASCII / non-ASCII message. _print_error must collapse it to a
        # single ASCII line on stderr.
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")

        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("first line 测试\nsecond line\r\nthird line 失败")

        monkeypatch.setattr("framework.comparison.cli.compare", _boom)

        rc = main(
            _basic_argv(artifact_root, output_dir=tmp_path / "out"),
            now=_now_fixed,
        )
        assert rc == 1
        captured = capsys.readouterr()

        # stderr is ASCII-only.
        captured.err.encode("ascii", errors="strict")

        # The trailing newline added by `print` itself is allowed; embedded
        # CR / LF in the message must NOT survive as real characters.
        body = captured.err.rstrip("\n")
        assert "\r" not in body
        assert "\n" not in body, f"_print_error leaked a real newline into stderr body: {body!r}"

        # Same body holds all three message fragments + the visible \n / \r
        # markers + the unicode-escaped non-ASCII fragments.
        assert "RuntimeError" in body
        assert "first line" in body
        assert "second line" in body
        assert "third line" in body
        assert "\\n" in body
        assert "\\r" in body
        assert "\\u6d4b" in body  # part of "测"
        assert "\\u8bd5" in body  # part of "试"
        assert "\\u8d25" in body  # part of "败"

    def test_print_error_single_trailing_newline_only(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The stderr output must be exactly one logical line: one trailing
        # newline added by `print`, and no embedded CR/LF in the body.
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(artifact_root, run_id="run_a")
        _write_run_dir(artifact_root, run_id="run_b")

        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("multi\nline\nfailure")

        monkeypatch.setattr("framework.comparison.cli.compare", _boom)

        main(
            _basic_argv(artifact_root, output_dir=tmp_path / "out"),
            now=_now_fixed,
        )
        captured = capsys.readouterr()
        # Exactly one newline at the end -> splitlines() yields exactly 1.
        assert captured.err.endswith("\n")
        assert not captured.err.endswith("\n\n")
        assert len(captured.err.splitlines()) == 1


# ---------------------------------------------------------------------------
# TestCliNoHashCheckEndToEnd
# ---------------------------------------------------------------------------


class TestCliNoHashCheckEndToEnd:
    def test_no_hash_check_skips_payload_check_in_strict_mode(self, tmp_path: Path) -> None:
        # Default strict=True + missing payload normally returns 3 (covered
        # by TestCliPayloadMissingStrict). With --no-hash-check the loader
        # must skip the entire payload-check loop, so the run completes
        # cleanly even though the file is absent.
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(
            artifact_root,
            run_id="run_a",
            artifacts=[_make_file_artifact_entry(aid="a1", run_id="run_a")],
        )
        _write_run_dir(
            artifact_root,
            run_id="run_b",
            artifacts=[_make_file_artifact_entry(aid="a1", run_id="run_b")],
        )
        out_dir = tmp_path / "out"
        rc = main(
            _basic_argv(artifact_root, output_dir=out_dir, extra=["--no-hash-check"]),
            now=_now_fixed,
        )
        assert rc == 0

        report = json.loads((out_dir / JSON_FILENAME).read_text(encoding="utf-8"))
        # No payload-missing entries because the loader's hash-check loop
        # never ran -> the loader's payload_missing_on_disk set stayed
        # empty -> the diff_engine never produced that kind.
        assert report["summary_counts"].get("artifact:payload_missing_on_disk", 0) == 0

    def test_no_hash_check_does_not_collide_with_non_strict(self, tmp_path: Path) -> None:
        # Sanity: --no-hash-check + --non-strict together still return 0
        # and produce no payload-missing entries (skip wins over record).
        artifact_root = tmp_path / "artifacts"
        _write_run_dir(
            artifact_root,
            run_id="run_a",
            artifacts=[_make_file_artifact_entry(aid="a1", run_id="run_a")],
        )
        _write_run_dir(
            artifact_root,
            run_id="run_b",
            artifacts=[_make_file_artifact_entry(aid="a1", run_id="run_b")],
        )
        out_dir = tmp_path / "out"
        rc = main(
            _basic_argv(
                artifact_root,
                output_dir=out_dir,
                extra=["--no-hash-check", "--non-strict"],
            ),
            now=_now_fixed,
        )
        assert rc == 0
        report = json.loads((out_dir / JSON_FILENAME).read_text(encoding="utf-8"))
        assert report["summary_counts"].get("artifact:payload_missing_on_disk", 0) == 0
