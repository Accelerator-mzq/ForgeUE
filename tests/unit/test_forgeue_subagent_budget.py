"""Unit tests for ``tools/forgeue_subagent_budget.py``.

Covers tasks.md §6.2 — fence cases for the informational subagent
token-budget tracker (per design.md D-ADR009):

1. ``--status`` always exits 0 + JSON output well-formed (when ``--json``).
2. ``--record`` appends JSON Lines + multi-record accumulation correct.
3. Exceeding WARN threshold does not affect exit code (only stdout WARN).
4. ``FORGEUE_SUBAGENT_BUDGET_DISABLE=1`` suppresses ``[WARN]`` lines.
5. I/O failure (parent path collision / unreadable log) returns exit 1.

Mirrors the subprocess + tmp_path style of
``tests/unit/test_forgeue_finish_gate.py`` and
``tests/unit/test_forgeue_change_state.py`` to keep fence pattern
consistent across the ForgeUE workflow tool suite.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import forgeue_subagent_budget as fsb  # noqa: E402

TOOL = _TOOLS / "forgeue_subagent_budget.py"

_CHANGE_ID = "fake-budget-change"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


# Env vars whose presence on the developer host could leak into a subprocess
# and shift WARN thresholds — scrubbed in every CLI call.
_BUDGET_ENV_VARS = (
    "FORGEUE_SUBAGENT_BUDGET_WARN_USD",
    "FORGEUE_SUBAGENT_BUDGET_WARN_PER_TASK_USD",
    "FORGEUE_SUBAGENT_BUDGET_DISABLE",
)


def _clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build a subprocess env dict with budget vars cleared, then overlay extras."""
    base = {**os.environ}
    for var in _BUDGET_ENV_VARS:
        base.pop(var, None)
    if extra:
        base.update(extra)
    return base


def _make_repo(tmp_path: Path, change_id: str = _CHANGE_ID) -> Path:
    """Lay out a minimal repo so ``find_repo_root`` resolves to ``tmp_path``.

    Creates ``.git/`` marker (no real git history needed — the tracker does
    NOT call ``git rev-parse``) plus an empty change dir with a placeholder
    proposal so ``list_active_changes`` would also see it if probed.
    """
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    cdir = tmp_path / "openspec" / "changes" / change_id
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "proposal.md").write_text("# placeholder\n", encoding="utf-8")
    return tmp_path


def _run_cli(
    repo: Path,
    args: list[str],
    *,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_clean_env(env_extra),
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Fence 1 — --status always exits 0; --json output well-formed
# ---------------------------------------------------------------------------


def test_status_exits_zero_on_empty_log(tmp_path):
    """No log file yet → status exits 0 and reports zero accumulated USD."""
    repo = _make_repo(tmp_path)
    proc = _run_cli(repo, ["--status", "--change", _CHANGE_ID])
    assert proc.returncode == 0, proc.stderr
    assert "[OK]" in proc.stdout
    # No WARN line on an empty log.
    assert "[WARN]" not in proc.stdout


def test_json_output_shape_well_formed(tmp_path):
    """``--json`` emits a payload containing the four contract keys.

    Per design.md D-ADR009: ``{"total_usd", "limit_usd", "exceeded",
    "warnings"}``. Implementation also surfaces ``per_task_usd`` /
    ``per_task_limit_usd`` / ``entry_count`` for telemetry; assert the
    contract keys exist + types are correct, and tolerate extras.
    """
    repo = _make_repo(tmp_path)
    proc = _run_cli(repo, ["--json", "--change", _CHANGE_ID])
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)
    for key in ("total_usd", "limit_usd", "exceeded", "warnings"):
        assert key in payload, f"missing JSON key: {key}"
    assert isinstance(payload["total_usd"], (int, float))
    assert isinstance(payload["limit_usd"], (int, float))
    assert isinstance(payload["exceeded"], bool)
    assert isinstance(payload["warnings"], list)
    # Empty log → exceeded must be False.
    assert payload["exceeded"] is False
    assert payload["warnings"] == []


def test_status_exits_zero_with_default_thresholds(tmp_path):
    """Default thresholds (WARN_USD=2.0 / PER_TASK=0.30) on a small log
    keep exit 0 + no WARN."""
    repo = _make_repo(tmp_path)
    _record(repo, task_n=1, subagent_type="implementer", usd=0.05)
    proc = _run_cli(repo, ["--status", "--change", _CHANGE_ID])
    assert proc.returncode == 0
    assert "[WARN]" not in proc.stdout


# ---------------------------------------------------------------------------
# Fence 2 — --record JSON Lines append + multi-record accumulation
# ---------------------------------------------------------------------------


def _record(
    repo: Path,
    *,
    task_n: int,
    subagent_type: str,
    usd: float,
    tokens_input: int = 1000,
    tokens_output: int = 500,
    model: str = "claude-sonnet-4-6",
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Helper to invoke ``--record`` with full required arg set."""
    args = [
        "--record",
        "--change", _CHANGE_ID,
        "--task-n", str(task_n),
        "--subagent-type", subagent_type,
        "--tokens-input", str(tokens_input),
        "--tokens-output", str(tokens_output),
        "--model", model,
        "--usd", f"{usd:.6f}",
    ]
    return _run_cli(repo, args, env_extra=env_extra)


def test_record_appends_jsonl_line(tmp_path):
    repo = _make_repo(tmp_path)
    proc = _record(repo, task_n=1, subagent_type="implementer", usd=0.05)
    assert proc.returncode == 0, proc.stderr

    log_path = (
        repo / "openspec" / "changes" / _CHANGE_ID
        / "verification" / "subagent_budget.log"
    )
    assert log_path.is_file(), "subagent_budget.log not created"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["task_n"] == 1
    assert obj["subagent_type"] == "implementer"
    assert obj["usd"] == pytest.approx(0.05)
    assert obj["tokens_input"] == 1000
    assert obj["tokens_output"] == 500
    assert obj["model"] == "claude-sonnet-4-6"
    # Timestamp must be present + ISO-shaped (contains 'T' separator).
    assert "T" in obj["timestamp"]


def test_record_accumulates_across_multiple_calls(tmp_path):
    """4 records (one per subagent role) → log has 4 lines + JSON total_usd
    equals the per-record sum."""
    repo = _make_repo(tmp_path)
    records = [
        (1, "implementer", 0.05),
        (1, "spec_review", 0.02),
        (1, "code_quality_review", 0.03),
        (2, "implementer", 0.04),
    ]
    for task_n, role, usd in records:
        proc = _record(repo, task_n=task_n, subagent_type=role, usd=usd)
        assert proc.returncode == 0, proc.stderr

    proc = _run_cli(repo, ["--json", "--change", _CHANGE_ID])
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    expected_total = sum(usd for _, _, usd in records)
    assert payload["total_usd"] == pytest.approx(expected_total, abs=1e-4)
    assert payload["entry_count"] == 4
    # Per-task breakdown
    per_task = payload["per_task_usd"]
    assert per_task["1"] == pytest.approx(0.10, abs=1e-4)
    assert per_task["2"] == pytest.approx(0.04, abs=1e-4)


def test_record_rejects_invalid_subagent_type(tmp_path):
    """Argparse choices rejects typos before they corrupt the log."""
    repo = _make_repo(tmp_path)
    args = [
        "--record",
        "--change", _CHANGE_ID,
        "--task-n", "1",
        "--subagent-type", "implmenter",  # typo
        "--tokens-input", "10",
        "--tokens-output", "5",
        "--model", "claude-sonnet-4-6",
        "--usd", "0.01",
    ]
    proc = _run_cli(repo, args)
    # argparse choices rejects with exit 2 (argparse default for bad arg).
    assert proc.returncode != 0


def test_record_missing_required_args_returns_one(tmp_path):
    """``--record`` without required fields → exit 1 (clean diagnostic)."""
    repo = _make_repo(tmp_path)
    proc = _run_cli(
        repo,
        ["--record", "--change", _CHANGE_ID, "--task-n", "1"],
    )
    assert proc.returncode == 1, proc.stderr


# ---------------------------------------------------------------------------
# Fence 3 — exceeding WARN threshold does NOT affect exit code
# ---------------------------------------------------------------------------


def test_warn_threshold_breach_keeps_exit_zero(tmp_path):
    """Total > WARN_USD → ``[WARN] budget exceeded`` on stdout but exit 0.

    Sets WARN_USD=0.10 + records $0.50 → total $0.50 / limit $0.10 = 500%.
    """
    repo = _make_repo(tmp_path)
    env = {"FORGEUE_SUBAGENT_BUDGET_WARN_USD": "0.10"}
    proc = _record(repo, task_n=1, subagent_type="implementer", usd=0.50, env_extra=env)
    assert proc.returncode == 0, proc.stderr

    # Re-query status with same threshold; exit 0 + WARN line present.
    proc = _run_cli(
        repo,
        ["--status", "--change", _CHANGE_ID],
        env_extra=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "[WARN] budget exceeded" in proc.stdout
    assert "$0.50" in proc.stdout
    assert "$0.10" in proc.stdout


def test_warn_threshold_breach_via_json_marks_exceeded(tmp_path):
    """JSON payload's ``exceeded`` flips True when total > limit."""
    repo = _make_repo(tmp_path)
    env = {"FORGEUE_SUBAGENT_BUDGET_WARN_USD": "0.10"}
    _record(repo, task_n=1, subagent_type="implementer", usd=0.50, env_extra=env)

    proc = _run_cli(repo, ["--json", "--change", _CHANGE_ID], env_extra=env)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["exceeded"] is True
    assert any("budget exceeded" in w for w in payload["warnings"])


def test_per_task_threshold_breach_warns_independently(tmp_path):
    """Per-task limit can fire even when total stays under WARN_USD."""
    repo = _make_repo(tmp_path)
    env = {
        "FORGEUE_SUBAGENT_BUDGET_WARN_USD": "10.00",       # high total
        "FORGEUE_SUBAGENT_BUDGET_WARN_PER_TASK_USD": "0.10",  # tight per-task
    }
    _record(repo, task_n=1, subagent_type="implementer", usd=0.50, env_extra=env)
    proc = _run_cli(repo, ["--status", "--change", _CHANGE_ID], env_extra=env)
    assert proc.returncode == 0
    assert "[WARN]" in proc.stdout
    assert "task 1 budget exceeded" in proc.stdout


# ---------------------------------------------------------------------------
# Fence 4 — FORGEUE_SUBAGENT_BUDGET_DISABLE suppresses [WARN]
# ---------------------------------------------------------------------------


def test_disable_suppresses_warn_lines(tmp_path):
    """``DISABLE=1`` silences the [WARN] line but JSON still reports exceeded.

    Per design.md D-ADR009 the JSON consumer must retain visibility — the
    DISABLE flag is purely a stdout chrome toggle for noisy automation.
    """
    repo = _make_repo(tmp_path)
    env_breach = {"FORGEUE_SUBAGENT_BUDGET_WARN_USD": "0.10"}
    _record(repo, task_n=1, subagent_type="implementer", usd=0.50, env_extra=env_breach)

    # With DISABLE on: stdout has no [WARN] line.
    env_disabled = {**env_breach, "FORGEUE_SUBAGENT_BUDGET_DISABLE": "1"}
    proc = _run_cli(repo, ["--status", "--change", _CHANGE_ID], env_extra=env_disabled)
    assert proc.returncode == 0
    assert "[WARN]" not in proc.stdout

    # JSON still exposes exceeded + warnings list (data, not chrome).
    proc = _run_cli(repo, ["--json", "--change", _CHANGE_ID], env_extra=env_disabled)
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["exceeded"] is True
    assert payload["warnings"], "JSON warnings list must remain populated"


@pytest.mark.parametrize("flag_value", ["1", "true", "yes", "on", "TRUE", "On"])
def test_disable_truthy_variants(tmp_path, flag_value):
    """All truthy spellings recognised by ``_common.env_truthy``."""
    repo = _make_repo(tmp_path)
    env_breach = {"FORGEUE_SUBAGENT_BUDGET_WARN_USD": "0.10"}
    _record(repo, task_n=1, subagent_type="implementer", usd=0.50, env_extra=env_breach)
    env_disabled = {**env_breach, "FORGEUE_SUBAGENT_BUDGET_DISABLE": flag_value}
    proc = _run_cli(repo, ["--status", "--change", _CHANGE_ID], env_extra=env_disabled)
    assert proc.returncode == 0
    assert "[WARN]" not in proc.stdout


def test_disable_falsy_variants_keep_warn(tmp_path):
    """``DISABLE=0`` / ``=false`` are NOT truthy → WARN still emitted."""
    repo = _make_repo(tmp_path)
    env_breach = {"FORGEUE_SUBAGENT_BUDGET_WARN_USD": "0.10"}
    _record(repo, task_n=1, subagent_type="implementer", usd=0.50, env_extra=env_breach)
    env_falsy = {**env_breach, "FORGEUE_SUBAGENT_BUDGET_DISABLE": "0"}
    proc = _run_cli(repo, ["--status", "--change", _CHANGE_ID], env_extra=env_falsy)
    assert proc.returncode == 0
    assert "[WARN]" in proc.stdout


# ---------------------------------------------------------------------------
# Fence 5 — I/O failure path returns exit 1
# ---------------------------------------------------------------------------


def test_io_failure_returns_one_when_log_path_blocked(tmp_path):
    """Make ``verification/`` a regular file, so ``mkdir(parents=True)`` for
    the log directory raises ``OSError`` → ``--record`` returns exit 1.

    This is portable across Windows + POSIX (no permission-bit dependency).
    """
    repo = _make_repo(tmp_path)
    cdir = repo / "openspec" / "changes" / _CHANGE_ID
    # Block creation of the verification/ subdir by occupying its name with a
    # plain file. ``mkdir(parents=True, exist_ok=True)`` will raise
    # FileExistsError (subclass of OSError) on the parent component.
    (cdir / "verification").write_text("not a dir\n", encoding="utf-8")

    proc = _record(repo, task_n=1, subagent_type="implementer", usd=0.05)
    assert proc.returncode == 1, proc.stderr
    assert "[FAIL]" in proc.stderr or "[FAIL]" in proc.stdout


def test_io_failure_returns_one_when_log_path_is_directory(tmp_path):
    """``--record`` with the log path itself occupied by a directory → exit 1.

    ``open(path, "a")`` raises ``IsADirectoryError`` (subclass of OSError)
    when the target is an existing directory. This is portable across
    Windows + POSIX (no permission-bit dependency).

    Note: ``--status`` on the same shape returns exit 0 by design — the
    reader is intentionally robust to absent / non-file logs (matches the
    ``parse_frontmatter`` "silent skip on malformed" convention used by
    ``_common``); only the writer surfaces the error since that is the
    code path that actually needs the path to be writable.
    """
    repo = _make_repo(tmp_path)
    cdir = repo / "openspec" / "changes" / _CHANGE_ID
    vdir = cdir / "verification"
    vdir.mkdir(parents=True, exist_ok=True)
    # Substitute log path with a directory so ``open("a")`` raises.
    bogus_log = vdir / "subagent_budget.log"
    bogus_log.mkdir()

    proc = _record(repo, task_n=1, subagent_type="implementer", usd=0.05)
    assert proc.returncode == 1, proc.stderr
    assert "[FAIL]" in proc.stderr or "[FAIL]" in proc.stdout


# ---------------------------------------------------------------------------
# Module-level smoke (importability, function purity)
# ---------------------------------------------------------------------------


def test_module_constants_match_design_doc():
    """Sanity-check that the exported defaults match design.md D-ADR009."""
    assert fsb._DEFAULT_WARN_TOTAL_USD == 2.0
    assert fsb._DEFAULT_WARN_PER_TASK_USD == 0.30
    assert fsb._ENV_WARN_TOTAL == "FORGEUE_SUBAGENT_BUDGET_WARN_USD"
    assert fsb._ENV_WARN_PER_TASK == "FORGEUE_SUBAGENT_BUDGET_WARN_PER_TASK_USD"
    assert fsb._ENV_DISABLE == "FORGEUE_SUBAGENT_BUDGET_DISABLE"
    assert "implementer" in fsb._SUBAGENT_TYPES
    assert "spec_review" in fsb._SUBAGENT_TYPES
    assert "code_quality_review" in fsb._SUBAGENT_TYPES
    assert "final_review" in fsb._SUBAGENT_TYPES


def test_summarize_pure_function():
    """``summarize`` is pure — no I/O, no env reads."""
    entries = [
        fsb.BudgetEntry("t1", 1, "implementer", 100, 50, "m", 0.10),
        fsb.BudgetEntry("t2", 1, "spec_review", 50, 25, "m", 0.05),
        fsb.BudgetEntry("t3", 2, "implementer", 200, 100, "m", 0.20),
    ]
    s = fsb.summarize(entries)
    assert s.entry_count == 3
    assert s.total_usd == pytest.approx(0.35)
    assert s.per_task_usd[1] == pytest.approx(0.15)
    assert s.per_task_usd[2] == pytest.approx(0.20)
