"""Markdown + JSON renderers for the comparison module.

See openspec/changes/add-run-comparison-baseline-regression/design.md §5 and
the runtime-core / artifact-contract delta specs for behavior contracts.

The reporter is a pure presentation layer over a pre-computed
`RunComparisonReport`. It MUST NOT:
- import or call `framework.comparison.diff_engine` (no diff recompute)
- import or call `framework.comparison.loader` (no run-snapshot read)
- read `config/models.yaml` or recompute payload hashes
- perform any disk I/O outside the dedicated `write_reports` boundary

Allowed framework imports: `framework.comparison.models` only. The two
`render_*` helpers are pure functions; `write_reports` is the sole I/O
boundary and produces fixed filenames `comparison_report.json` and
`comparison_summary.md` so callers can locate the outputs without inspection.

Markdown output must be ASCII-only — `_ascii_safe` coerces every dynamic
value via `encode('ascii', errors='backslashreplace')` so non-ASCII content
surfaces as `\\uXXXX` escapes rather than crashing a Windows GBK stdout
downstream. Table cells additionally collapse CR/LF to spaces and escape
literal pipes, so dynamic values cannot break the Markdown grid.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, get_args

from framework.comparison.models import (
    ArtifactDiff,
    ArtifactDiffKind,
    MetricDiff,
    RunComparisonReport,
    StepDiff,
    VerdictDiff,
    VerdictDiffKind,
)

JSON_FILENAME = "comparison_report.json"
MARKDOWN_FILENAME = "comparison_summary.md"

_ARTIFACT_KINDS: tuple[str, ...] = tuple(get_args(ArtifactDiffKind))
_VERDICT_KINDS: tuple[str, ...] = tuple(get_args(VerdictDiffKind))
_SELECTED_DELTA_KEYS: tuple[str, ...] = (
    "added",
    "removed",
    "rejected_added",
    "rejected_removed",
)
_ANOMALY_ARTIFACT_KINDS: frozenset[str] = frozenset(
    {"missing_in_baseline", "missing_in_candidate", "payload_missing_on_disk"}
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_json(report: RunComparisonReport) -> str:
    """Serialize `report` as indented JSON with a trailing newline.

    Uses Pydantic's `model_dump_json(indent=2)` so the field order matches
    the model definition; deterministic given the same input."""
    return report.model_dump_json(indent=2) + "\n"


def render_markdown(report: RunComparisonReport) -> str:
    """Render an ASCII-only Markdown summary of `report`.

    Pure function: does not mutate the report, performs no I/O, and emits
    byte-identical output across calls with the same input."""
    lines: list[str] = []
    lines.extend(_render_header(report))
    lines.append("")
    lines.extend(_render_summary(report))
    lines.append("")
    lines.extend(_render_counts(report))
    lines.append("")
    lines.extend(_render_run_metrics(report))
    lines.append("")
    lines.extend(_render_step_diffs(report))
    lines.append("")
    lines.extend(_render_anomalies(report))
    lines.append("")
    return "\n".join(lines)


def write_reports(report: RunComparisonReport, output_dir: Path) -> tuple[Path, Path]:
    """Write JSON + Markdown side by side under `output_dir`.

    Returns `(json_path, md_path)` with the fixed filenames
    `comparison_report.json` and `comparison_summary.md`. Creates `output_dir`
    if it does not already exist. Existing files at the fixed filenames are
    overwritten — the CLI is responsible for picking a unique `output_dir`
    per invocation. Encoding is UTF-8 with LF line endings to keep byte
    hashes deterministic across Windows / macOS / Linux.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / JSON_FILENAME
    md_path = output_dir / MARKDOWN_FILENAME
    json_path.write_text(render_json(report), encoding="utf-8", newline="\n")
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return json_path, md_path


# ---------------------------------------------------------------------------
# Cell escape + value formatting
# ---------------------------------------------------------------------------


def _ascii_safe(value: Any) -> str:
    """ASCII-coerce a value for inclusion in any Markdown context.

    None becomes the placeholder ``-``. Non-ASCII characters are escaped via
    `backslashreplace` so they appear as `\\uXXXX` literals rather than
    crashing a Windows GBK stdout downstream.
    """
    if value is None:
        return "-"
    s = str(value)
    return s.encode("ascii", errors="backslashreplace").decode("ascii")


def _line_safe(value: Any) -> str:
    """ASCII-coerce + CR/LF flatten for non-table Markdown contexts.

    Use this for values placed into headers, summary bullets, step headings,
    or anomaly entries — anywhere a literal newline in the value would
    otherwise split the host Markdown line. Pipes are NOT escaped (the
    surrounding context is not a table cell, so there is no column boundary
    to protect). Table cells must use `_escape_cell` instead, which adds
    pipe escaping on top of the same CR/LF handling.
    """
    if value is None:
        return "-"
    s = _ascii_safe(value)
    return s.replace("\r", " ").replace("\n", " ")


def _escape_cell(value: Any) -> str:
    """Escape a value for safe insertion into a Markdown table cell.

    None -> ``-``. CR/LF collapsed to single space. Literal ``|`` escaped to
    ``\\|`` so it does not split the cell. ASCII coercion is applied via
    `_ascii_safe`. ALL dynamic values placed inside table cells must go
    through this helper.
    """
    if value is None:
        return "-"
    s = _ascii_safe(value)
    s = s.replace("\r", " ").replace("\n", " ")
    s = s.replace("|", "\\|")
    return s


def _format_float(value: float | None) -> str:
    if value is None:
        return "-"
    return _ascii_safe(f"{value:g}")


def _format_metadata_delta(delta: dict[str, tuple[Any, Any]]) -> str:
    if not delta:
        return "-"
    parts = [f"{k}={b!r}->{c!r}" for k, (b, c) in sorted(delta.items())]
    return "; ".join(parts)


def _format_lineage_delta(delta: dict[str, tuple[Any, Any]] | None) -> str:
    if not delta:
        return "-"
    return _format_metadata_delta(delta)


def _format_selected_delta(delta: dict[str, list[str]] | None) -> str:
    if not delta:
        return "-"
    parts = [f"{key}={delta[key]!r}" for key in _SELECTED_DELTA_KEYS if key in delta]
    return "; ".join(parts) if parts else "-"


def _count(report: RunComparisonReport, key: str) -> int:
    """Sparse-dict-safe count lookup.

    All ``summary_counts`` reads MUST go through this helper — the dict only
    carries keys that actually appeared in the diff, so direct subscript
    access raises ``KeyError`` for any kind that did not occur. The
    diff_engine module documents this sparseness invariant explicitly.
    """
    return report.summary_counts.get(key, 0)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def _render_header(report: RunComparisonReport) -> list[str]:
    return [
        f"# Run Comparison: baseline={_line_safe(report.input.baseline_run_id)} "
        f"vs candidate={_line_safe(report.input.candidate_run_id)}",
    ]


def _render_summary(report: RunComparisonReport) -> list[str]:
    inp = report.input
    b = report.baseline_run_meta
    c = report.candidate_run_meta
    return [
        "## Summary",
        f"- Status match: {_line_safe(report.status_match)}",
        f"- Generated at: {_line_safe(report.generated_at.isoformat())}",
        f"- Schema version: {_line_safe(report.schema_version)}",
        f"- Strict / hash check: {_line_safe(inp.strict)} / " f"{_line_safe(inp.include_payload_hash_check)}",
        "- Baseline: "
        f"run_id={_line_safe(b.get('run_id'))} "
        f"status={_line_safe(b.get('status'))} "
        f"trace_id={_line_safe(b.get('trace_id'))} "
        f"termination_reason={_line_safe(b.get('termination_reason'))}",
        "- Candidate: "
        f"run_id={_line_safe(c.get('run_id'))} "
        f"status={_line_safe(c.get('status'))} "
        f"trace_id={_line_safe(c.get('trace_id'))} "
        f"termination_reason={_line_safe(c.get('termination_reason'))}",
    ]


def _render_counts(report: RunComparisonReport) -> list[str]:
    rows: list[tuple[str, int]] = [
        ("steps_total", _count(report, "steps_total")),
        ("steps_with_artifact_change", _count(report, "steps_with_artifact_change")),
        ("steps_with_verdict_change", _count(report, "steps_with_verdict_change")),
    ]
    rows.extend((f"artifact:{k}", _count(report, f"artifact:{k}")) for k in _ARTIFACT_KINDS)
    rows.extend((f"verdict:{k}", _count(report, f"verdict:{k}")) for k in _VERDICT_KINDS)
    out = ["## Counts", "", "| key | count |", "|-----|-------|"]
    out.extend(f"| {_escape_cell(k)} | {_escape_cell(v)} |" for k, v in rows)
    return out


def _render_run_metrics(report: RunComparisonReport) -> list[str]:
    out = ["## Run-level metrics"]
    if not report.run_level_metric_diffs:
        out.extend(["", "(none)"])
        return out
    out.extend(
        [
            "",
            "| metric | baseline | candidate | delta | delta_pct |",
            "|--------|----------|-----------|-------|-----------|",
        ]
    )
    out.extend(_format_run_metric_row(m) for m in report.run_level_metric_diffs)
    return out


def _format_run_metric_row(m: MetricDiff) -> str:
    return (
        f"| {_escape_cell(m.metric)} "
        f"| {_escape_cell(_format_float(m.baseline_value))} "
        f"| {_escape_cell(_format_float(m.candidate_value))} "
        f"| {_escape_cell(_format_float(m.delta))} "
        f"| {_escape_cell(_format_float(m.delta_pct))} |"
    )


def _render_step_diffs(report: RunComparisonReport) -> list[str]:
    out = ["## Step diffs"]
    if not report.step_diffs:
        out.extend(["", "(none)"])
        return out
    for sd in report.step_diffs:
        out.append("")
        out.extend(_render_one_step(sd))
    return out


def _render_one_step(sd: StepDiff) -> list[str]:
    out = [
        f"### step_{_line_safe(sd.step_id)}",
        f"- status: {_line_safe(sd.status_baseline)} -> {_line_safe(sd.status_candidate)}",
        f"- chosen_model: {_line_safe(sd.chosen_model_baseline)} -> "
        f"{_line_safe(sd.chosen_model_candidate)}",
        "",
        "#### Artifact diffs",
    ]
    if not sd.artifact_diffs:
        out.extend(["", "(none)"])
    else:
        out.extend(
            [
                "",
                "| artifact_id | kind | baseline_hash | candidate_hash | "
                "metadata_delta | lineage_delta | note |",
                "|-------------|------|---------------|----------------|"
                "----------------|---------------|------|",
            ]
        )
        out.extend(_format_artifact_row(ad) for ad in sd.artifact_diffs)

    out.extend(["", "#### Verdict diffs"])
    if not sd.verdict_diffs:
        out.extend(["", "(none)"])
    else:
        out.extend(
            [
                "",
                "| step_id | kind | baseline_decision | candidate_decision | "
                "baseline_confidence | candidate_confidence | selected_delta |",
                "|---------|------|-------------------|--------------------|"
                "---------------------|----------------------|----------------|",
            ]
        )
        out.extend(_format_verdict_row(vd) for vd in sd.verdict_diffs)

    out.extend(["", "#### Metric diffs"])
    if not sd.metric_diffs:
        out.extend(["", "(none)"])
    else:
        out.extend(
            [
                "",
                "| metric | scope | baseline | candidate | delta | delta_pct |",
                "|--------|-------|----------|-----------|-------|-----------|",
            ]
        )
        out.extend(_format_step_metric_row(m) for m in sd.metric_diffs)
    return out


def _format_artifact_row(ad: ArtifactDiff) -> str:
    return (
        f"| {_escape_cell(ad.artifact_id)} "
        f"| {_escape_cell(ad.kind)} "
        f"| {_escape_cell(ad.baseline_hash)} "
        f"| {_escape_cell(ad.candidate_hash)} "
        f"| {_escape_cell(_format_metadata_delta(ad.metadata_delta))} "
        f"| {_escape_cell(_format_lineage_delta(ad.lineage_delta))} "
        f"| {_escape_cell(ad.note)} |"
    )


def _format_verdict_row(vd: VerdictDiff) -> str:
    return (
        f"| {_escape_cell(vd.step_id)} "
        f"| {_escape_cell(vd.kind)} "
        f"| {_escape_cell(vd.baseline_decision)} "
        f"| {_escape_cell(vd.candidate_decision)} "
        f"| {_escape_cell(_format_float(vd.baseline_confidence))} "
        f"| {_escape_cell(_format_float(vd.candidate_confidence))} "
        f"| {_escape_cell(_format_selected_delta(vd.selected_delta))} |"
    )


def _format_step_metric_row(m: MetricDiff) -> str:
    return (
        f"| {_escape_cell(m.metric)} "
        f"| {_escape_cell(m.scope)} "
        f"| {_escape_cell(_format_float(m.baseline_value))} "
        f"| {_escape_cell(_format_float(m.candidate_value))} "
        f"| {_escape_cell(_format_float(m.delta))} "
        f"| {_escape_cell(_format_float(m.delta_pct))} |"
    )


def _render_anomalies(report: RunComparisonReport) -> list[str]:
    items: list[str] = []
    for sd in report.step_diffs:
        for ad in sd.artifact_diffs:
            if ad.kind in _ANOMALY_ARTIFACT_KINDS or ad.note is not None:
                note = ad.note if ad.note is not None else "(none)"
                items.append(
                    f"- step={_line_safe(sd.step_id)} "
                    f"artifact={_line_safe(ad.artifact_id)} "
                    f"kind={_line_safe(ad.kind)} "
                    f"note={_line_safe(note)}"
                )
    out = ["## Anomalies", ""]
    if not items:
        out.append("(none)")
        return out
    out.extend(items)
    return out
