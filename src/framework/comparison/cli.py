"""Command-line entry point for the comparison module.

See openspec/changes/add-run-comparison-baseline-regression/design.md §6 and
the runtime-core delta spec ADDED Requirement "CLI exit codes carve out
comparison-specific meanings" for the exit-code contract.

The CLI is a pure orchestration layer over the already-tested loader,
diff engine, and reporter modules. It MUST NOT:

- import or call `framework.runtime` / `framework.providers` /
  `framework.review_engine` / `framework.ue_bridge` / `framework.workflows`
- DIRECTLY import or call `framework.artifact_store` write-side APIs:
  `ArtifactRepository.put`, `load_run_metadata`, any payload-backend
  write operation, `CheckpointStore` write paths, etc.
- recompute hashes (loader does that)
- re-render JSON or Markdown (reporter does that)
- redefine the JSON / Markdown filenames (reporter constants are
  re-used verbatim)

Allowed framework imports: `framework.comparison.{models, loader,
diff_engine, reporter}`. The loader transitively pulls in
`framework.artifact_store.hashing` + `framework.core.{artifact, enums,
runtime}`, which is permitted.

Known transitive-import carve-out: `framework.artifact_store.repository`
and `framework.artifact_store.payload_backends` will appear in
`sys.modules` after this module loads, because the current
`framework/artifact_store/__init__.py` eager-imports them as part of
its public-API surface; the loader's import of
`framework.artifact_store.hashing` therefore unavoidably triggers that
package init. This carve-out is aligned with the Task 2 loader fence
and is NOT a license for the CLI source to invoke any write-side API.
A follow-up OpenSpec change (`lazy-artifact-store-package-exports`)
tracks converting the artifact_store package init to PEP 562 lazy
exports so this carve-out can eventually be retired.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from framework.comparison.diff_engine import compare
from framework.comparison.loader import (
    PayloadMissingOnDisk,
    RunDirAmbiguous,
    RunDirNotFound,
    RunSnapshotCorrupt,
    load_run_snapshot,
    resolve_run_dir,
)
from framework.comparison.models import RunComparisonInput, RunComparisonReport
from framework.comparison.reporter import (
    JSON_FILENAME,
    MARKDOWN_FILENAME,
    render_json,
    render_markdown,
    write_reports,
)

_UNSAFE_PATH_SEGMENT_CHARS: tuple[str, ...] = ("/", "\\", ":", "\r", "\n")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def main(
    argv: Sequence[str] | None = None,
    *,
    now: Callable[[], datetime] | None = None,
) -> int:
    """CLI entry point. Returns the exit code; never calls `sys.exit`.

    `argv` defaults to `sys.argv[1:]` (argparse default). `now` is a clock
    callable used only to stamp the default `output_dir`; injecting it lets
    tests assert deterministic path segments without freezing real time.

    Exit codes (per runtime-core delta spec):

    - `0` — comparison completed (regardless of how many diffs were found)
    - `2` — Run dir not found, ambiguous, or `_artifacts.json` /
            `run_summary.json` schema corrupt
    - `3` — strict mode + at least one artifact payload missing on disk
    - `1` — any other unexpected exception (defensive bucket; not in the
            spec's exhaustive list, but does not collide with 0/2/3)

    argparse itself exits 2 on bad args (missing required / mutually
    exclusive group conflict); that exit happens before any code in the
    try-block runs and is the standard argparse convention.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        inp = _build_input(args)
        baseline_dir = resolve_run_dir(
            inp.artifact_root,
            inp.baseline_run_id,
            inp.baseline_date_bucket,
        )
        candidate_dir = resolve_run_dir(
            inp.artifact_root,
            inp.candidate_run_id,
            inp.candidate_date_bucket,
        )
        baseline_snap = load_run_snapshot(
            baseline_dir,
            include_payload_hash_check=inp.include_payload_hash_check,
            strict=inp.strict,
        )
        candidate_snap = load_run_snapshot(
            candidate_dir,
            include_payload_hash_check=inp.include_payload_hash_check,
            strict=inp.strict,
        )
        report = compare(inp, baseline_snap, candidate_snap)

        now_dt = now() if now is not None else datetime.now()
        output_dir = (
            Path(args.output_dir) if args.output_dir is not None else _resolve_default_output_dir(inp, now_dt)
        )

        json_path: Path | None
        md_path: Path | None
        if args.json_only:
            json_path = _render_only_json(report, output_dir)
            md_path = None
        elif args.markdown_only:
            json_path = None
            md_path = _render_only_markdown(report, output_dir)
        else:
            json_path, md_path = write_reports(report, output_dir)

        _print_success(
            json_path=json_path,
            md_path=md_path,
            report=report,
            quiet=args.quiet,
        )
        return 0

    except (RunDirNotFound, RunDirAmbiguous, RunSnapshotCorrupt) as exc:
        _print_error(exc)
        return 2
    except PayloadMissingOnDisk as exc:
        _print_error(exc)
        return 3
    except Exception as exc:
        _print_error(exc)
        return 1


# ---------------------------------------------------------------------------
# Argparse + Input construction
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m framework.comparison",
        description="Read-only comparison of two completed Run directories.",
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("./artifacts"),
        help="Root directory containing date-bucketed run dirs (default: ./artifacts).",
    )
    parser.add_argument(
        "--baseline-run",
        required=True,
        help="run_id of the baseline run.",
    )
    parser.add_argument(
        "--candidate-run",
        required=True,
        help="run_id of the candidate run.",
    )
    parser.add_argument(
        "--baseline-date",
        default=None,
        help=(
            "Optional YYYY-MM-DD date bucket for the baseline run; auto-resolves "
            "across date buckets when omitted (raises RunDirAmbiguous on conflict)."
        ),
    )
    parser.add_argument(
        "--candidate-date",
        default=None,
        help=(
            "Optional YYYY-MM-DD date bucket for the candidate run; same "
            "auto-resolve semantics as --baseline-date."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Directory to write reports into. Defaults to "
            "./demo_artifacts/<YYYY-MM-DD>/comparison/"
            "<baseline>__vs__<candidate>/<HHMMSS>/. Both segments are "
            "sanitized via _safe_path_segment to avoid filesystem traversal."
        ),
    )
    parser.add_argument(
        "--no-hash-check",
        action="store_true",
        help="Skip on-disk payload byte-hash recomputation.",
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        help=(
            "Treat missing-payload-on-disk as a recorded anomaly instead of "
            "raising; does NOT bypass schema corruption checks."
        ),
    )
    fmt_group = parser.add_mutually_exclusive_group()
    fmt_group.add_argument(
        "--json-only",
        action="store_true",
        help="Write only the JSON report (comparison_report.json).",
    )
    fmt_group.add_argument(
        "--markdown-only",
        action="store_true",
        help="Write only the Markdown summary (comparison_summary.md).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the human-readable summary; print only the produced file path(s).",
    )
    return parser


def _build_input(args: argparse.Namespace) -> RunComparisonInput:
    return RunComparisonInput(
        baseline_run_id=args.baseline_run,
        candidate_run_id=args.candidate_run,
        artifact_root=args.artifact_root,
        baseline_date_bucket=args.baseline_date,
        candidate_date_bucket=args.candidate_date,
        strict=not args.non_strict,
        include_payload_hash_check=not args.no_hash_check,
    )


# ---------------------------------------------------------------------------
# Default output directory + path-segment safety
# ---------------------------------------------------------------------------


def _safe_path_segment(value: str) -> str:
    """Sanitize a string for use as a single filesystem path segment.

    Replaces characters that would either split the path (``/``, ``\\``),
    fight Windows drive parsing (``:``), or break Markdown line structure
    if echoed back (``\\r``, ``\\n``) with a single underscore. Empty input
    becomes ``_`` so a missing run_id still produces a valid directory name.

    This affects ONLY the directory path. The original
    ``RunComparisonInput.baseline_run_id`` / ``candidate_run_id`` are kept
    verbatim and surface unchanged in the report body.
    """
    if not value:
        return "_"
    out = value
    for ch in _UNSAFE_PATH_SEGMENT_CHARS:
        out = out.replace(ch, "_")
    return out or "_"


def _resolve_default_output_dir(inp: RunComparisonInput, now_dt: datetime) -> Path:
    """Compute the default output directory.

    Layout (matches design.md §5):
        ./demo_artifacts/<YYYY-MM-DD>/comparison/<baseline>__vs__<candidate>/<HHMMSS>/

    Date and time use the locally-injected ``now_dt`` (typically
    ``datetime.now()``) so users find their reports under their own
    timezone's date. ``report.generated_at`` is independently UTC, which
    is fine — the path is for humans, the JSON timestamp is for tools.
    """
    date_str = now_dt.strftime("%Y-%m-%d")
    time_str = now_dt.strftime("%H%M%S")
    base_seg = _safe_path_segment(inp.baseline_run_id)
    cand_seg = _safe_path_segment(inp.candidate_run_id)
    pair = f"{base_seg}__vs__{cand_seg}"
    return Path("./demo_artifacts") / date_str / "comparison" / pair / time_str


# ---------------------------------------------------------------------------
# Single-format writers (json-only / markdown-only)
# ---------------------------------------------------------------------------


def _render_only_json(report: RunComparisonReport, output_dir: Path) -> Path:
    """Write only the JSON report, reusing the reporter's filename / encoding."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / JSON_FILENAME
    json_path.write_text(render_json(report), encoding="utf-8", newline="\n")
    return json_path


def _render_only_markdown(report: RunComparisonReport, output_dir: Path) -> Path:
    """Write only the Markdown summary, reusing the reporter's filename / encoding."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / MARKDOWN_FILENAME
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return md_path


# ---------------------------------------------------------------------------
# stdout / stderr helpers
# ---------------------------------------------------------------------------


def _console_safe(value: object) -> str:
    """ASCII-coerce + visible-CR/LF rewrite for any console-bound dynamic value.

    Used by `_print_success` and `_print_error` to keep stdout / stderr
    safe for script consumers and Windows GBK terminals:

    - ``None`` -> ``"-"`` (shared placeholder convention with the reporter
      module's ``_ascii_safe`` / ``_escape_cell``).
    - Non-ASCII characters are replaced via ``backslashreplace`` so they
      render as ``\\uXXXX`` / ``\\UXXXXXXXX`` literals rather than
      crashing GBK stdout downstream.
    - Real CR / LF characters in the value become the visible two-char
      sequences ``\\r`` / ``\\n`` so a single-line output contract is
      preserved even when the value is a multi-line message (e.g. a
      Pydantic ValidationError wrapped inside ``RunSnapshotCorrupt``).
      ``print`` itself still adds its own trailing newline; only
      embedded CR/LF in the value are rewritten.

    This helper does NOT alter any value that lands in the JSON or
    Markdown report files — those continue to go through the reporter's
    own escape path. It is purely a console-output guard.
    """
    if value is None:
        return "-"
    s = str(value)
    s = s.encode("ascii", errors="backslashreplace").decode("ascii")
    return s.replace("\r", "\\r").replace("\n", "\\n")


def _print_success(
    *,
    json_path: Path | None,
    md_path: Path | None,
    report: RunComparisonReport,
    quiet: bool,
) -> None:
    if quiet:
        if json_path is not None:
            print(_console_safe(json_path))
        if md_path is not None:
            print(_console_safe(md_path))
        return

    sc = report.summary_counts
    print("[OK] Run comparison complete")
    print(f"  baseline:  {_console_safe(report.input.baseline_run_id)}")
    print(f"  candidate: {_console_safe(report.input.candidate_run_id)}")
    print(f"  status_match: {_console_safe(report.status_match)}")
    print(f"  steps_total: {_console_safe(sc.get('steps_total', 0))}")
    print(f"  steps_with_artifact_change: " f"{_console_safe(sc.get('steps_with_artifact_change', 0))}")
    print(f"  steps_with_verdict_change: " f"{_console_safe(sc.get('steps_with_verdict_change', 0))}")
    if json_path is not None:
        print(f"  json: {_console_safe(json_path)}")
    if md_path is not None:
        print(f"  markdown: {_console_safe(md_path)}")


def _print_error(exc: Exception) -> None:
    """Emit a single-line ASCII-marker error to stderr.

    Format: ``[ERR] <ExceptionClassName>: <str(exc)>``. The class name and
    message both go through `_console_safe`, so multi-line Pydantic errors
    or non-ASCII content collapse into one ASCII-only line; only the
    trailing newline emitted by ``print`` itself remains. No traceback —
    rerun with ``PYTHONFAULTHANDLER=1`` or under ``pdb`` if needed.
    """
    print(
        f"[ERR] {_console_safe(type(exc).__name__)}: {_console_safe(exc)}",
        file=sys.stderr,
    )
