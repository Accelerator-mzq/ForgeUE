"""ForgeUE Level 0 / 1 / 2 verification orchestrator.

This is a thin wrapper over the commands documented in
``docs/ai_workflow/validation_matrix.md`` — it does not invent any new
verification semantics (per p1_docs_review_codex.md H1.1 lesson). The matrix
is the contract; this tool is its machine version.

- **Level 0** (always runs unless ``--dry-run``): ``python -m pytest -q``
  plus the offline bundle smoke ``python -m framework.run --task
  examples/mock_linear.json``. No API keys, no paid calls.
- **Level 1** (opt-in via ``FORGEUE_VERIFY_LIVE_LLM``): one live LLM bundle
  (``examples/character_extract.json``). Requires a configured ``.env``.
- **Level 2** (opt-in via ``FORGEUE_VERIFY_LIVE_MESH`` / ``_UE`` /
  ``_COMFY``): mesh.generation / UE commandlet / ComfyUI bundles. Per
  ADR-007 + ForgeUE memory ``feedback_no_silent_retry_on_billable_api``,
  the tool never auto-retries paid endpoints; failure surfaces job_id and
  exits non-zero. Truthy values follow the strict
  ``{1, true, yes, on}`` set, case-insensitive.

CLI:

- ``--change <id>`` — change id (used to default ``--report-out`` to
  ``openspec/changes/<id>/verification/verify_report.md``).
- ``--level {0,1,2}`` — highest level to attempt; lower levels still run.
- ``--report-out <path>`` — explicit report path (overrides default).
- ``--json`` / ``--dry-run`` — standard semantics.

Exit codes:

- ``0`` — every selected step ``[OK]`` or ``[SKIP]`` (SKIP requires reason).
- ``2`` — at least one ``[FAIL]``.
- ``3`` — change id supplied but not found, or report path parent missing.
- ``1`` — unexpected I/O / OS exception.

The pytest count is never hardcoded in this source. The report records the
"passed=N" / "failed=N" line that pytest itself prints; downstream
consumers parse from that line.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402


VALID_LEVELS = (0, 1, 2)
DEFAULT_TIMEOUT_SEC = 60 * 30  # 30 min cap per step (live UE can be slow)


# ---------------------------------------------------------------------------
# Plan model
# ---------------------------------------------------------------------------


@dataclass
class StepPlan:
    name: str
    command: list[str]
    level: int
    env_var: str | None = None  # truthy-required to actually run
    description: str = ""


@dataclass
class StepResult:
    name: str
    level: int
    status: str  # "OK" | "FAIL" | "SKIP"
    exit_code: int | None
    duration_sec: float
    reason: str = ""
    pytest_summary: str | None = None
    command: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Plan construction
# ---------------------------------------------------------------------------


def build_plan(level: int) -> list[StepPlan]:
    plan: list[StepPlan] = [
        StepPlan(
            name="pytest",
            level=0,
            command=[sys.executable, "-m", "pytest", "-q"],
            description="full pytest suite (count from actual output, not hardcoded)",
        ),
        StepPlan(
            name="offline-bundle-smoke",
            level=0,
            command=[
                sys.executable,
                "-m",
                "framework.run",
                "--task",
                "examples/mock_linear.json",
                "--run-id",
                "forgeue_verify_smoke",
            ],
            description="offline mock_linear bundle smoke (validation_matrix §1.2)",
        ),
    ]
    if level >= 1:
        plan.append(
            StepPlan(
                name="live-llm-character-extract",
                level=1,
                env_var="FORGEUE_VERIFY_LIVE_LLM",
                command=[
                    sys.executable,
                    "-m",
                    "framework.run",
                    "--task",
                    "examples/character_extract.json",
                    "--run-id",
                    "forgeue_verify_live_llm",
                    "--live-llm",
                ],
                description="live LLM structured extraction (validation_matrix §2.1)",
            )
        )
    if level >= 2:
        plan.extend(
            [
                StepPlan(
                    name="live-mesh-generation",
                    level=2,
                    env_var="FORGEUE_VERIFY_LIVE_MESH",
                    command=[
                        sys.executable,
                        "-m",
                        "framework.run",
                        "--task",
                        "examples/image_to_3d_pipeline_live.json",
                        "--run-id",
                        "forgeue_verify_live_mesh",
                        "--live-llm",
                    ],
                    description=(
                        "live mesh.generation (validation_matrix §3.2). "
                        "Failure surfaces job_id; do NOT auto-retry (ADR-007)."
                    ),
                ),
                StepPlan(
                    name="live-ue-export",
                    level=2,
                    env_var="FORGEUE_VERIFY_LIVE_UE",
                    command=[
                        sys.executable,
                        "-m",
                        "framework.run",
                        "--task",
                        "examples/ue_export_pipeline_live.json",
                        "--run-id",
                        "forgeue_verify_live_ue",
                        "--live-llm",
                    ],
                    description="live UE export (validation_matrix §3.3 step 1)",
                ),
                StepPlan(
                    name="live-comfy-pipeline",
                    level=2,
                    env_var="FORGEUE_VERIFY_LIVE_COMFY",
                    command=[
                        sys.executable,
                        "-m",
                        "framework.run",
                        "--task",
                        "examples/image_pipeline.json",
                        "--run-id",
                        "forgeue_verify_live_comfy",
                        "--live-llm",
                        "--comfy-url",
                        "http://127.0.0.1:8188",
                    ],
                    description="live ComfyUI HTTP pipeline (validation_matrix §3.1)",
                ),
            ]
        )
    return plan


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------


_PYTEST_RESULT_LINE_RE = re.compile(
    r"\b(\d+)\s+(passed|failed|error|errors|skipped|deselected|xfailed|xpassed|warning|warnings)\b",
    re.IGNORECASE,
)


def _extract_pytest_summary(stdout: str) -> str | None:
    """Parse the trailing pytest summary line in any of pytest's output modes.

    Modern pytest under ``-q`` may emit ``1 passed in 0.05s`` without ``=``
    border decoration; verbose mode emits ``=== 1 passed in 0.05s ===``.
    Walk from the bottom and accept any line that matches the result-count
    regex, stripping any ``=`` decoration.
    """
    for line in reversed(stdout.splitlines()):
        ls = line.strip().strip("=").strip()
        if not ls:
            continue
        if _PYTEST_RESULT_LINE_RE.search(ls):
            return ls
    return None


def run_step(step: StepPlan, *, repo: Path) -> StepResult:
    if step.env_var and not _common.env_truthy(step.env_var):
        return StepResult(
            name=step.name,
            level=step.level,
            status="SKIP",
            exit_code=None,
            duration_sec=0.0,
            reason=f"opt-in env {step.env_var} not truthy ({{1,true,yes,on}} required)",
            command=list(step.command),
        )
    start = time.monotonic()
    try:
        completed = subprocess.run(
            step.command,
            cwd=str(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DEFAULT_TIMEOUT_SEC,
        )
    except FileNotFoundError as exc:
        return StepResult(
            name=step.name,
            level=step.level,
            status="FAIL",
            exit_code=None,
            duration_sec=time.monotonic() - start,
            reason=f"command not found: {_common.console_safe(exc)}",
            command=list(step.command),
        )
    except subprocess.TimeoutExpired as exc:
        # ADR-007 + memory feedback_no_silent_retry_on_billable_api: even on
        # timeout, mesh.generation may have already printed job_id before the
        # cap fired. Capture exc.stdout / exc.stderr (Python ≥3.5) and grep
        # for the id so the user can `probe_hunyuan_3d_query` it instead of
        # blind-retrying.
        partial_stdout = exc.stdout if isinstance(exc.stdout, str) else (
            exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        )
        partial_stderr = exc.stderr if isinstance(exc.stderr, str) else (
            exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        )
        partial_full = (partial_stderr or "") + "\n" + (partial_stdout or "")
        reason = f"timeout > {DEFAULT_TIMEOUT_SEC}s"
        if step.name == "live-mesh-generation" and partial_full.strip():
            job_match = re.search(
                r"job[_-]?id\s*[:=]?\s*['\"]?([\w-]{8,})['\"]?",
                partial_full,
                re.IGNORECASE,
            )
            if job_match:
                reason = (
                    f"job_id={job_match.group(1)} | timeout > {DEFAULT_TIMEOUT_SEC}s "
                    "(partial output captured)"
                )
        return StepResult(
            name=step.name,
            level=step.level,
            status="FAIL",
            exit_code=None,
            duration_sec=time.monotonic() - start,
            reason=_common.console_safe(reason)[:240],
            command=list(step.command),
        )
    duration = time.monotonic() - start
    status = "OK" if completed.returncode == 0 else "FAIL"
    summary: str | None = None
    if step.name == "pytest":
        summary = _extract_pytest_summary(completed.stdout) or _extract_pytest_summary(
            completed.stderr
        )
    reason = ""
    if status == "FAIL":
        full = (completed.stderr or "") + "\n" + (completed.stdout or "")
        last_lines = full.strip().splitlines()[-1:]
        reason = last_lines[0] if last_lines else f"exit {completed.returncode}"
        # ADR-007 + memory feedback_no_silent_retry_on_billable_api: mesh.generation
        # failure MUST surface job_id so the user can `probe_hunyuan_3d_query` it
        # before deciding to --resume. Last-line-only extraction can miss the id
        # if it was logged earlier in stderr.
        if step.name == "live-mesh-generation":
            job_match = re.search(
                r"job[_-]?id\s*[:=]?\s*['\"]?([\w-]{8,})['\"]?",
                full,
                re.IGNORECASE,
            )
            if job_match:
                reason = f"job_id={job_match.group(1)} | {reason}"
    return StepResult(
        name=step.name,
        level=step.level,
        status=status,
        exit_code=completed.returncode,
        duration_sec=duration,
        reason=_common.console_safe(reason)[:200] if reason else "",
        pytest_summary=summary,
        command=list(step.command),
    )


# ---------------------------------------------------------------------------
# Report rendering (verification/verify_report.md)
# ---------------------------------------------------------------------------


def render_report(
    *,
    change_id: str,
    level: int,
    results: list[StepResult],
) -> str:
    overall_aligned = all(r.status != "FAIL" for r in results)
    now = datetime.now(timezone.utc).isoformat()
    env, plugin = _common.quick_detect_env()
    # frontmatter is strictly the 12-key schema (1 wrapper change_id + 11 audit
    # fields per design.md §3); auxiliary info like verification level lives
    # in the markdown body, not in frontmatter.
    fm_lines = [
        "---",
        f"change_id: {change_id}",
        "stage: S5",
        "evidence_type: verify_report",
        "contract_refs:",
        "  - docs/ai_workflow/validation_matrix.md",
        "  - design.md",
        f"aligned_with_contract: {'true' if overall_aligned else 'false'}",
        "drift_decision: null",
        "writeback_commit: null",
        "drift_reason: null",
        "reasoning_notes_anchor: null",
        f"detected_env: {env}",
        "triggered_by: cli-flag",
        f"codex_plugin_available: {'true' if plugin else 'false'}",
        "---",
        "",
        f"# Verify Report: {change_id}",
        "",
        f"_Generated by `tools/forgeue_verify.py --level {level}` at {now}._",
        "",
        f"## Steps (level {level})",
        "",
    ]
    for r in results:
        marker = {"OK": "[OK]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}.get(r.status, "[WARN]")
        fm_lines.append(f"- {marker} **L{r.level} {r.name}** "
                        f"(exit={r.exit_code}, {r.duration_sec:.1f}s)")
        if r.pytest_summary:
            fm_lines.append(f"  - pytest summary: {r.pytest_summary}")
        if r.reason:
            fm_lines.append(f"  - reason: {r.reason}")
        fm_lines.append(f"  - command: `{' '.join(shlex.quote(c) for c in r.command)}`")
    fm_lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- total steps: {len(results)}",
            f"- [OK]: {sum(1 for r in results if r.status == 'OK')}",
            f"- [FAIL]: {sum(1 for r in results if r.status == 'FAIL')}",
            f"- [SKIP]: {sum(1 for r in results if r.status == 'SKIP')}",
            "",
        ]
    )
    return "\n".join(fm_lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python tools/forgeue_verify.py",
        description="Run Level 0 / 1 / 2 verification per validation_matrix.md.",
    )
    p.add_argument("--change", required=True, help="Change id (also used for default report path).")
    p.add_argument(
        "--level",
        type=int,
        choices=VALID_LEVELS,
        default=0,
        help="Highest verification level to attempt (default: 0).",
    )
    p.add_argument(
        "--report-out",
        default=None,
        help="Path to write verify_report.md (default: openspec/changes/<id>/verification/verify_report.md).",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON only (no ASCII markers).")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit the planned step list without spawning any subprocess or writing files.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    _common.setup_utf8_stdout()
    args = _build_parser().parse_args(argv)
    try:
        repo = _common.find_repo_root()
        change_dir = _common.change_path(repo, args.change)
        if change_dir is None and not args.dry_run:
            print(
                f"[FAIL] change {args.change!r} not found under "
                "openspec/changes/ or openspec/changes/archive/",
                file=sys.stderr,
            )
            return 3

        plan = build_plan(args.level)

        if args.dry_run:
            return _emit_plan(plan, change_id=args.change, level=args.level, json_out=args.json)

        results: list[StepResult] = [run_step(s, repo=repo) for s in plan]
        report_text = render_report(
            change_id=args.change, level=args.level, results=results
        )
        report_path = _resolve_report_path(args.report_out, change_dir)
        if report_path is not None:
            try:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(report_text, encoding="utf-8", newline="\n")
            except OSError as exc:
                print(f"[FAIL] cannot write report: {_common.console_safe(exc)}", file=sys.stderr)
                return 3

        if args.json:
            print(
                json.dumps(
                    {
                        "change_id": args.change,
                        "level": args.level,
                        "report_out": str(report_path) if report_path else None,
                        "results": [asdict(r) for r in results],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            for r in results:
                marker = {"OK": "[OK]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}.get(r.status, "[WARN]")
                line = f"{marker} L{r.level} {r.name}"
                if r.pytest_summary:
                    line += f" ({r.pytest_summary})"
                if r.reason:
                    line += f" — {r.reason}"
                print(line)
            if report_path is not None:
                print(f"[OK] report: {report_path}")

        if any(r.status == "FAIL" for r in results):
            return 2
        return 0

    except OSError as exc:
        print(f"[FAIL] {_common.console_safe(exc)}", file=sys.stderr)
        return 1


def _resolve_report_path(report_out: str | None, change_dir: Path | None) -> Path | None:
    if report_out:
        return Path(report_out)
    if change_dir is not None:
        return change_dir / "verification" / "verify_report.md"
    return None


def _emit_plan(
    plan: list[StepPlan], *, change_id: str, level: int, json_out: bool
) -> int:
    if json_out:
        payload = {
            "change_id": change_id,
            "level": level,
            "dry_run": True,
            "plan": [
                {
                    "name": s.name,
                    "level": s.level,
                    "command": s.command,
                    "env_var": s.env_var,
                    "description": s.description,
                }
                for s in plan
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"[OK] forgeue_verify --dry-run plan (change={change_id}, level={level})")
    for s in plan:
        gate = f" [opt-in env {s.env_var}]" if s.env_var else ""
        print(f"  L{s.level} {s.name}{gate}")
        print(f"    {s.description}")
        print(f"    cmd: {' '.join(shlex.quote(c) for c in s.command)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
