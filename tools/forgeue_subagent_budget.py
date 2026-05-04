"""ForgeUE subagent dispatch token-budget tracker — informational only.

Per design.md ``D-ADR009`` (the ``adopt-subagent-driven-development`` change),
this tool is an **informational + soft WARNING** budget tracker for the
subagent-driven-development dispatch path. Its boundary is **fundamentally
different** from ADR-007:

- ADR-007 (vendor API double-charge guard) intercepts the situation where a
  retry would double-bill an already-completed paid mesh.generation job
  (``per_task_usd > 0``). The cost there is **wasted** if not blocked.
- ADR-009 (this tool) only records LLM token consumption that **continues
  producing value** as the subagent dispatch progresses. Blocking here would
  interrupt useful work; the framework therefore must NOT make a dispatch
  abort decision on the user's behalf — only surface visibility.

Three CLI subcommands (mutually exclusive, dispatched via positional flags):

- ``--status`` — print accumulated USD vs WARN thresholds; ``exit 0`` always
  (I/O exception → ``exit 1``); when accumulated cost exceeds
  ``FORGEUE_SUBAGENT_BUDGET_WARN_USD`` (default ``2.0``) AND
  ``FORGEUE_SUBAGENT_BUDGET_DISABLE`` is not truthy, stdout carries
  ``[WARN] budget exceeded: $<X.XX> of $<Y.YY> (<Z>%)`` lines (one for the
  total, one per task that breaches ``WARN_PER_TASK_USD``).
- ``--record`` — append one JSON Lines record to
  ``openspec/changes/<id>/verification/subagent_budget.log``. Required
  per-call args: ``--task-n`` / ``--subagent-type`` /
  ``--tokens-input`` / ``--tokens-output`` / ``--model`` / ``--usd``.
  ``exit 0`` on success; ``exit 1`` on I/O failure.
- ``--json`` — machine-readable status payload
  ``{"total_usd": X, "limit_usd": Y, "exceeded": bool, "warnings": [...]}``;
  ``exit 0`` always.

Env vars (per design.md D-ADR009):

- ``FORGEUE_SUBAGENT_BUDGET_WARN_USD`` — total accumulated WARN threshold
  (default ``2.0``).
- ``FORGEUE_SUBAGENT_BUDGET_WARN_PER_TASK_USD`` — per-task WARN threshold
  (default ``0.30``).
- ``FORGEUE_SUBAGENT_BUDGET_DISABLE`` — truthy (``1`` / ``true`` / ``yes`` /
  ``on``) suppresses the ``[WARN]`` lines but accumulator + JSON output
  are unchanged (the controller still receives full visibility).

Exit codes:

- ``0`` — operation succeeded (OR threshold breached but tool is
  informational; ``exit 0`` is the design contract — see D-ADR009).
- ``1`` — I/O failure (``OSError`` reading or writing the log file).

Module layout follows ``tools/forgeue_finish_gate.py`` and
``tools/forgeue_change_state.py``: stdlib-only argparse CLI; utf-8 stdout
reconfigure with ASCII-coercion fallback (``feedback_ascii_only_in_adhoc_scripts``);
JSON Lines append-only (no truncation) so parallel record calls compose.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402


# ---------------------------------------------------------------------------
# Defaults / constants
# ---------------------------------------------------------------------------


# Default WARN thresholds (USD). Per design.md D-ADR009; mid-task experience
# in the dogfood self-host run showed total_usd ~$1.5-2.0 / per-task ~$0.20,
# so these are deliberately tight enough to surface a budget anomaly without
# tripping on baseline runs.
_DEFAULT_WARN_TOTAL_USD = 2.0
_DEFAULT_WARN_PER_TASK_USD = 0.30

# Env var names — kept in a tuple constant so test fixtures can reference
# them by symbol when scrubbing test environments.
_ENV_WARN_TOTAL = "FORGEUE_SUBAGENT_BUDGET_WARN_USD"
_ENV_WARN_PER_TASK = "FORGEUE_SUBAGENT_BUDGET_WARN_PER_TASK_USD"
_ENV_DISABLE = "FORGEUE_SUBAGENT_BUDGET_DISABLE"

# Recognised subagent types — fixed enum per design.md D-EvidenceSchema row
# ``evidence_type`` mapping. ``--record --subagent-type <x>`` rejects values
# outside this set so a typo doesn't silently land in the log.
_SUBAGENT_TYPES = ("implementer", "spec_review", "code_quality_review", "final_review")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BudgetEntry:
    """One JSON Lines log record (= one subagent dispatch return)."""

    timestamp: str
    task_n: int
    subagent_type: str
    tokens_input: int
    tokens_output: int
    model: str
    usd: float

    def to_json(self) -> str:
        """Render as a single-line JSON object (newline-delimited via writer)."""
        # ensure_ascii=True keeps the log GBK-safe on Windows even if a model
        # name happens to contain a non-ASCII byte; we do not rely on the
        # JSON Lines reader being utf-8-aware.
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "task_n": self.task_n,
                "subagent_type": self.subagent_type,
                "tokens_input": self.tokens_input,
                "tokens_output": self.tokens_output,
                "model": self.model,
                "usd": self.usd,
            },
            ensure_ascii=True,
        )


@dataclass
class BudgetSummary:
    """Aggregated state across all entries in one ``subagent_budget.log``."""

    total_usd: float = 0.0
    limit_usd: float = _DEFAULT_WARN_TOTAL_USD
    per_task_limit_usd: float = _DEFAULT_WARN_PER_TASK_USD
    per_task_usd: dict[int, float] = field(default_factory=dict)
    entry_count: int = 0
    exceeded: bool = False
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------


def _env_float(name: str, default: float) -> float:
    """Read a USD threshold from env; fall back to default on parse failure.

    Sentinel ``""`` (empty string) treated as unset — matches ``os.environ``
    convention used by the rest of the ForgeUE tool suite.
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _disable_warnings() -> bool:
    """Return True iff ``FORGEUE_SUBAGENT_BUDGET_DISABLE`` is set truthy."""
    return _common.env_truthy(_ENV_DISABLE)


# ---------------------------------------------------------------------------
# Log path / I/O
# ---------------------------------------------------------------------------


def log_path_for(repo: Path, change_id: str) -> Path:
    """Return ``openspec/changes/<id>/verification/subagent_budget.log``.

    Intentionally does not create the directory — that is the writer's
    responsibility; readers tolerate the file being absent (``read_log``
    returns an empty list).
    """
    cdir = _common.change_path(repo, change_id)
    if cdir is None:
        # Fall back to the active path even if the change dir has not yet
        # been created (so the writer can mkdir on first --record).
        cdir = _common.changes_dir(repo) / change_id
    return cdir / "verification" / "subagent_budget.log"


def read_log(path: Path) -> list[BudgetEntry]:
    """Parse JSON Lines log → entries; return ``[]`` if file is absent.

    Malformed lines are silently skipped to keep --status robust against
    hand-edited logs (matches the parse_frontmatter robustness convention
    used by ``_common``).
    """
    if not path.is_file():
        return []
    out: list[BudgetEntry] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        # Re-raise so the caller's main() can map this to ``exit 1``.
        raise
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        try:
            out.append(
                BudgetEntry(
                    timestamp=str(obj.get("timestamp", "")),
                    task_n=int(obj.get("task_n", 0)),
                    subagent_type=str(obj.get("subagent_type", "")),
                    tokens_input=int(obj.get("tokens_input", 0)),
                    tokens_output=int(obj.get("tokens_output", 0)),
                    model=str(obj.get("model", "")),
                    usd=float(obj.get("usd", 0.0)),
                )
            )
        except (TypeError, ValueError):
            # Bad type for one of the int / float fields — skip rather than
            # corrupt the summary.
            continue
    return out


def append_log(path: Path, entry: BudgetEntry) -> None:
    """Append one JSON line; raises ``OSError`` on I/O failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(entry.to_json())
        fh.write("\n")


# ---------------------------------------------------------------------------
# Summary / WARN computation
# ---------------------------------------------------------------------------


def summarize(entries: list[BudgetEntry]) -> BudgetSummary:
    """Aggregate entries → BudgetSummary (no env reads inside; pure func).

    Caller is responsible for setting ``limit_usd`` / ``per_task_limit_usd``
    from env vars before computing ``warnings``.
    """
    s = BudgetSummary()
    s.entry_count = len(entries)
    for e in entries:
        s.total_usd += e.usd
        s.per_task_usd[e.task_n] = s.per_task_usd.get(e.task_n, 0.0) + e.usd
    return s


def compute_warnings(summary: BudgetSummary) -> None:
    """Mutate summary.warnings + summary.exceeded based on configured limits.

    Two-tier WARN model per design.md D-ADR009:

    1. Total accumulated USD vs ``FORGEUE_SUBAGENT_BUDGET_WARN_USD``.
    2. Each task's accumulated USD vs ``FORGEUE_SUBAGENT_BUDGET_WARN_PER_TASK_USD``.

    Both checks emit ``[WARN] budget exceeded: $X.XX of $Y.YY (Z%)``. The
    ``exceeded`` flag flips on EITHER check (so the JSON consumer can
    distinguish PASS from any-WARN without scanning the warnings list).
    """
    if summary.limit_usd > 0 and summary.total_usd > summary.limit_usd:
        pct = (summary.total_usd / summary.limit_usd) * 100.0
        summary.warnings.append(
            f"budget exceeded: ${summary.total_usd:.2f} of "
            f"${summary.limit_usd:.2f} ({pct:.0f}%)"
        )
        summary.exceeded = True
    if summary.per_task_limit_usd > 0:
        for task_n, usd in sorted(summary.per_task_usd.items()):
            if usd > summary.per_task_limit_usd:
                pct = (usd / summary.per_task_limit_usd) * 100.0
                summary.warnings.append(
                    f"task {task_n} budget exceeded: ${usd:.2f} of "
                    f"${summary.per_task_limit_usd:.2f} ({pct:.0f}%)"
                )
                summary.exceeded = True


def build_summary(repo: Path, change_id: str) -> BudgetSummary:
    """End-to-end: read log → summarize → apply env limits → compute warnings.

    Pure orchestration (no stdout side effect). Used by both ``--status``
    and ``--json`` paths so they share aggregation semantics.
    """
    path = log_path_for(repo, change_id)
    entries = read_log(path)
    summary = summarize(entries)
    summary.limit_usd = _env_float(_ENV_WARN_TOTAL, _DEFAULT_WARN_TOTAL_USD)
    summary.per_task_limit_usd = _env_float(
        _ENV_WARN_PER_TASK, _DEFAULT_WARN_PER_TASK_USD
    )
    compute_warnings(summary)
    return summary


# ---------------------------------------------------------------------------
# CLI argparse
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python tools/forgeue_subagent_budget.py",
        description=(
            "Informational subagent dispatch token-budget tracker "
            "(per design.md D-ADR009; soft WARNING only, never blocks)."
        ),
    )
    p.add_argument(
        "--change",
        required=True,
        help="Change id (under openspec/changes/ or archive/).",
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--status",
        action="store_true",
        help="Print accumulated USD + WARN status; exit 0 always.",
    )
    mode.add_argument(
        "--record",
        action="store_true",
        help=(
            "Append one JSON Lines record to verification/subagent_budget.log. "
            "Requires --task-n / --subagent-type / --tokens-input / "
            "--tokens-output / --model / --usd."
        ),
    )
    mode.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable status payload (total_usd / limit_usd / exceeded / warnings).",
    )
    # --record-only fields. Validated post-parse so --status / --json don't
    # need to supply them.
    p.add_argument("--task-n", type=int, default=None, help="Micro-task index (for --record).")
    p.add_argument(
        "--subagent-type",
        choices=_SUBAGENT_TYPES,
        default=None,
        help="Subagent role (for --record).",
    )
    p.add_argument(
        "--tokens-input",
        type=int,
        default=None,
        help="Input token count from Task tool return (for --record).",
    )
    p.add_argument(
        "--tokens-output",
        type=int,
        default=None,
        help="Output token count from Task tool return (for --record).",
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name string (e.g. claude-sonnet-4-6) for --record.",
    )
    p.add_argument(
        "--usd",
        type=float,
        default=None,
        help="USD cost from Task tool return (for --record).",
    )
    return p


def _validate_record_args(args: argparse.Namespace) -> str | None:
    """Return error message if --record args are incomplete; else None."""
    missing: list[str] = []
    if args.task_n is None:
        missing.append("--task-n")
    if args.subagent_type is None:
        missing.append("--subagent-type")
    if args.tokens_input is None:
        missing.append("--tokens-input")
    if args.tokens_output is None:
        missing.append("--tokens-output")
    if not args.model:
        missing.append("--model")
    if args.usd is None:
        missing.append("--usd")
    if missing:
        return "missing required --record args: " + ", ".join(missing)
    return None


# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------


def _emit_status_text(summary: BudgetSummary) -> None:
    """Render --status output to stdout; honours WARN_DISABLE for [WARN] lines."""
    print(
        f"[OK] subagent budget: ${summary.total_usd:.2f} of "
        f"${summary.limit_usd:.2f} (per-task limit ${summary.per_task_limit_usd:.2f}; "
        f"{summary.entry_count} entries)"
    )
    if summary.warnings and not _disable_warnings():
        for w in summary.warnings:
            print(f"[WARN] {w}")


def _emit_status_json(summary: BudgetSummary) -> None:
    """Render --json payload (always emits warnings list, regardless of WARN_DISABLE).

    The warnings list is data, not stdout chrome — silencing it would make
    the JSON consumer (e.g. controller logging) lose visibility, defeating
    the design intent (informational, not enforcement).
    """
    payload = {
        "total_usd": round(summary.total_usd, 4),
        "limit_usd": round(summary.limit_usd, 4),
        "per_task_limit_usd": round(summary.per_task_limit_usd, 4),
        "per_task_usd": {str(k): round(v, 4) for k, v in summary.per_task_usd.items()},
        "entry_count": summary.entry_count,
        "exceeded": summary.exceeded,
        "warnings": summary.warnings,
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def _now_iso() -> str:
    """Return a tz-aware ISO-8601 timestamp; default tz = local (offset)."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _do_record(repo: Path, args: argparse.Namespace) -> int:
    """Append one BudgetEntry; print updated status. Returns exit code."""
    err = _validate_record_args(args)
    if err:
        print(f"[FAIL] {err}", file=sys.stderr)
        return 1
    entry = BudgetEntry(
        timestamp=_now_iso(),
        task_n=int(args.task_n),
        subagent_type=str(args.subagent_type),
        tokens_input=int(args.tokens_input),
        tokens_output=int(args.tokens_output),
        model=str(args.model),
        usd=float(args.usd),
    )
    path = log_path_for(repo, args.change)
    try:
        append_log(path, entry)
    except OSError as exc:
        print(
            f"[FAIL] cannot write {path}: {_common.console_safe(exc)}",
            file=sys.stderr,
        )
        return 1
    # Re-read the log so the [WARN] line reflects the entry just written.
    try:
        summary = build_summary(repo, args.change)
    except OSError as exc:
        print(
            f"[FAIL] cannot read {path}: {_common.console_safe(exc)}",
            file=sys.stderr,
        )
        return 1
    print(
        f"[OK] recorded task {entry.task_n} {entry.subagent_type} "
        f"${entry.usd:.4f} (total ${summary.total_usd:.2f})"
    )
    if summary.warnings and not _disable_warnings():
        for w in summary.warnings:
            print(f"[WARN] {w}")
    return 0


def _do_status(repo: Path, change_id: str) -> int:
    try:
        summary = build_summary(repo, change_id)
    except OSError as exc:
        print(f"[FAIL] {_common.console_safe(exc)}", file=sys.stderr)
        return 1
    _emit_status_text(summary)
    return 0


def _do_json(repo: Path, change_id: str) -> int:
    try:
        summary = build_summary(repo, change_id)
    except OSError as exc:
        print(f"[FAIL] {_common.console_safe(exc)}", file=sys.stderr)
        return 1
    _emit_status_json(summary)
    return 0


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    _common.setup_utf8_stdout()
    args = _build_parser().parse_args(argv)
    repo = _common.find_repo_root()
    if args.record:
        return _do_record(repo, args)
    if args.status:
        return _do_status(repo, args.change)
    if args.json:
        return _do_json(repo, args.change)
    # Should be unreachable thanks to the mutually_exclusive required group;
    # defensive default keeps the contract (exit 0) intact.
    return 0


if __name__ == "__main__":
    sys.exit(main())
