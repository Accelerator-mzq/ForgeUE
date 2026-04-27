"""tasks.md §5.6.2 cross-cutting fence: stdout / stderr from each forgeue
tool is pure ASCII (no em-dash, no §, no other emoji or non-ASCII chars).

Strategy: run each tool in a benign mode (``--help`` or ``--dry-run``) and
assert the captured ``stdout`` + ``stderr`` are ASCII-only. The 7
canonical markers (``[OK] [FAIL] [SKIP] [WARN] [DRIFT] [REQUIRED]
[OPTIONAL]``) are all ASCII; this fence catches accidental introductions
of non-ASCII separator characters anywhere in the output path.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
_FIXTURES = _REPO / "tests" / "fixtures" / "forgeue_workflow"
if str(_FIXTURES) not in sys.path:
    sys.path.insert(0, str(_FIXTURES))

from builders import make_complete_change, make_drift_change, make_minimal_change  # noqa: E402

TOOL_FILES = sorted(_TOOLS.glob("forgeue_*.py"))


_AGENT_VARS = (
    "FORGEUE_REVIEW_ENV",
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_SSE_PORT",
    "CLAUDE_PROJECT_DIR",
    "CURSOR_TRACE_ID",
    "CURSOR_AGENT",
    "CURSOR_PROJECT_PATH",
    "AIDER_PROJECT_DIR",
    "AIDER_AUTO_LINTS",
    "AIDER_MODEL",
)


def _clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {**os.environ}
    for v in _AGENT_VARS:
        env.pop(v, None)
    if extra:
        env.update(extra)
    return env


def _check_ascii(text: str, where: str) -> None:
    raw = text.encode("utf-8")
    non_ascii = [(i, b) for i, b in enumerate(raw) if b > 127]
    if non_ascii:
        offsets = [i for i, _ in non_ascii[:5]]
        sample = raw[max(0, offsets[0] - 20) : offsets[0] + 20]
        pytest.fail(
            f"{where}: non-ASCII bytes at offsets {[i for i, _ in non_ascii[:10]]} "
            f"sample={sample!r}"
        )


def test_each_tool_help_is_ascii():
    for tool in TOOL_FILES:
        proc = subprocess.run(
            [sys.executable, str(tool), "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_clean_env(),
            timeout=30,
        )
        _check_ascii(proc.stdout, f"{tool.name} --help stdout")
        _check_ascii(proc.stderr, f"{tool.name} --help stderr")


def test_env_detect_ascii_outputs(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(_TOOLS / "forgeue_env_detect.py"), "--review-env", "unknown"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_clean_env(),
        timeout=30,
    )
    _check_ascii(proc.stdout, "env_detect human")
    _check_ascii(proc.stderr, "env_detect stderr")


def test_change_state_ascii_outputs(tmp_path):
    make_drift_change(tmp_path, "anchor", change_id="fc-asc")
    proc = subprocess.run(
        [
            sys.executable,
            str(_TOOLS / "forgeue_change_state.py"),
            "--change",
            "fc-asc",
            "--writeback-check",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_clean_env(),
        timeout=30,
    )
    _check_ascii(proc.stdout, "change_state human")
    _check_ascii(proc.stderr, "change_state stderr")


def test_verify_dry_run_ascii_outputs(tmp_path):
    make_minimal_change(tmp_path, "fc-asc")
    proc = subprocess.run(
        [
            sys.executable,
            str(_TOOLS / "forgeue_verify.py"),
            "--change",
            "fc-asc",
            "--level",
            "2",
            "--dry-run",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_clean_env(),
        timeout=30,
    )
    _check_ascii(proc.stdout, "verify --dry-run human")
    _check_ascii(proc.stderr, "verify --dry-run stderr")


def test_doc_sync_check_ascii_outputs(tmp_path):
    make_minimal_change(tmp_path, "fc-asc")
    (tmp_path / ".git").mkdir()
    proc = subprocess.run(
        [
            sys.executable,
            str(_TOOLS / "forgeue_doc_sync_check.py"),
            "--change",
            "fc-asc",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_clean_env(),
        timeout=30,
    )
    _check_ascii(proc.stdout, "doc_sync_check human")
    _check_ascii(proc.stderr, "doc_sync_check stderr")


def test_finish_gate_ascii_outputs(tmp_path):
    make_complete_change(tmp_path, "fc-asc")
    proc = subprocess.run(
        [
            sys.executable,
            str(_TOOLS / "forgeue_finish_gate.py"),
            "--change",
            "fc-asc",
            "--no-validate",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_clean_env({"FORGEUE_REVIEW_ENV": "cursor"}),
        timeout=30,
    )
    _check_ascii(proc.stdout, "finish_gate human")
    _check_ascii(proc.stderr, "finish_gate stderr")


def test_finish_gate_drift_ascii_outputs(tmp_path):
    make_drift_change(
        tmp_path,
        "frontmatter_disputed_drift_anchor_unresolved",
        change_id="fc-asc-drift",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(_TOOLS / "forgeue_finish_gate.py"),
            "--change",
            "fc-asc-drift",
            "--no-validate",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_clean_env({"FORGEUE_REVIEW_ENV": "cursor"}),
        timeout=30,
    )
    _check_ascii(proc.stdout, "finish_gate drift human")
    _check_ascii(proc.stderr, "finish_gate drift stderr")
