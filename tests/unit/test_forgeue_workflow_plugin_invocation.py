"""tasks.md §5.4.1 fence: 8 forgeue command md must reference codex hooks
+ forgeue_env_detect; must NOT invoke /codex:rescue or --enable-review-gate.

Lines that mention banned tokens are allowed only in negation context
(``不调`` / ``禁`` / ``Don't`` / ``do not``) or detection context
(``WARN`` / ``disable`` / ``检测``).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_CMD_DIR = _REPO / ".claude" / "commands" / "forgeue"


@pytest.fixture(scope="module")
def cmd_files() -> list[Path]:
    files = sorted(_CMD_DIR.glob("change-*.md"))
    assert len(files) == 8, f"expected exactly 8 forgeue command files, found {len(files)}"
    return files


# ---------------------------------------------------------------------------
# Positive presence: codex hook + forgeue_env_detect
# ---------------------------------------------------------------------------


def test_each_cmd_mentions_codex_hook(cmd_files):
    """Every command file must reference at least one of /codex:adversarial-review
    or /codex:review (either as invocation or as explicit non-invocation)."""
    bad = []
    for f in cmd_files:
        text = f.read_text(encoding="utf-8")
        if "/codex:adversarial-review" not in text and "/codex:review" not in text:
            bad.append(f.name)
    assert not bad, f"missing codex hook reference: {bad}"


def test_each_cmd_references_forgeue_env_detect(cmd_files):
    bad = []
    for f in cmd_files:
        text = f.read_text(encoding="utf-8")
        if "forgeue_env_detect" not in text:
            bad.append(f.name)
    assert not bad, f"missing forgeue_env_detect reference: {bad}"


# ---------------------------------------------------------------------------
# Banned: /codex:rescue / --enable-review-gate as INVOCATION
# ---------------------------------------------------------------------------


_RESCUE_NEG_MARKERS = ("不调", "禁", "Don't", "do not", "ban", "豁免", "fence")
_REVIEW_GATE_NEG_MARKERS = (
    "不启",
    "禁",
    "WARN",
    "disable",
    "检测",
    "Don't",
    "do not",
    "豁免",
    "review-gate hook",
)


def _line_has_marker(line: str, markers: tuple[str, ...]) -> bool:
    return any(m in line for m in markers)


def test_no_codex_rescue_invocation(cmd_files):
    r"""Each ``/codex:rescue`` mention must be in negation context.

    The literal token may appear (e.g. ``**不调 \`/codex:rescue\`**``) for
    explicit don't-do-this guidance, but no line should *invoke* it.
    """
    bad = []
    for f in cmd_files:
        for ln_no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "/codex:rescue" in line and not _line_has_marker(line, _RESCUE_NEG_MARKERS):
                bad.append(f"{f.name}:{ln_no}: {line.strip()}")
    assert not bad, f"/codex:rescue mentioned without negation:\n  " + "\n  ".join(bad)


def test_no_enable_review_gate_invocation(cmd_files):
    bad = []
    for f in cmd_files:
        for ln_no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "--enable-review-gate" in line and not _line_has_marker(
                line, _REVIEW_GATE_NEG_MARKERS
            ):
                bad.append(f"{f.name}:{ln_no}: {line.strip()}")
    assert not bad, f"--enable-review-gate mentioned without negation:\n  " + "\n  ".join(bad)


# ---------------------------------------------------------------------------
# Sanity: 8 expected command names
# ---------------------------------------------------------------------------


def test_expected_eight_commands_present(cmd_files):
    names = {f.stem for f in cmd_files}
    expected = {
        "change-status",
        "change-plan",
        "change-apply",
        "change-debug",
        "change-verify",
        "change-review",
        "change-doc-sync",
        "change-finish",
    }
    assert names == expected, f"command set mismatch: missing={expected - names}, extra={names - expected}"
