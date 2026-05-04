"""tasks.md §5.4.1 fence: forgeue command md must reference codex hooks
+ forgeue_env_detect; must NOT invoke /codex:rescue or --enable-review-gate.

Active command count:9(post-task 2 split:change-apply-subagent +
change-apply-direct;旧 change-apply.md 标 ``tags: [forgeue, deprecated]``
作 deprecation banner stub,fixture 通过 tags-aware skip 排除,见
design.md ``## Migration Plan``)。

Lines that mention banned tokens are allowed only in negation context
(``不调`` / ``禁`` / ``Don't`` / ``do not``) or detection context
(``WARN`` / ``disable`` / ``检测``).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_CMD_DIR = _REPO / ".claude" / "commands" / "forgeue"
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import _common  # noqa: E402


def _is_deprecated(path: Path) -> bool:
    """Frontmatter ``tags`` includes ``deprecated``(见
    test_forgeue_command_markdown 同款 helper rationale)。"""
    fm, _ = _common.parse_frontmatter(path.read_text(encoding="utf-8"))
    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags_str = tags
    else:
        tags_str = ", ".join(str(t) for t in tags)
    return "deprecated" in tags_str


@pytest.fixture(scope="module")
def cmd_files() -> list[Path]:
    files = sorted(p for p in _CMD_DIR.glob("change-*.md") if not _is_deprecated(p))
    assert len(files) == 9, f"expected exactly 9 active forgeue command files, found {len(files)}"
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
# Sanity: 9 expected active command names(post-task 2 split)
# ---------------------------------------------------------------------------


def test_expected_active_commands_present(cmd_files):
    """Active(非 deprecated)命令名集合 = 9。

    旧 ``change-apply`` 被 task 2 split 为 ``change-apply-subagent``
    (default subagent path)+ ``change-apply-direct``(fallback direct path),
    旧 stub 保留 1 archive cycle 作 deprecation banner(见 design.md
    ``## Migration Plan``),通过 fixture tags-aware skip 排除。
    """
    names = {f.stem for f in cmd_files}
    expected = {
        "change-status",
        "change-plan",
        "change-apply-subagent",
        "change-apply-direct",
        "change-debug",
        "change-verify",
        "change-review",
        "change-doc-sync",
        "change-finish",
    }
    assert names == expected, f"command set mismatch: missing={expected - names}, extra={names - expected}"
