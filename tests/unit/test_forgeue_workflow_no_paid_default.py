"""tasks.md §5.6.1 cross-cutting fence: no paid / live default in tools or
forgeue command markdown.

Constraints (per design.md §5 + risk R3 + ADR-007):

- ``forgeue_verify.py`` argparse ``--level`` default MUST be 0.
- Each Level >= 1 StepPlan in ``build_plan(2)`` MUST carry an env_var guard
  matching the ``FORGEUE_VERIFY_LIVE_*`` family.
- Every ``paid`` / ``live`` mention in ``.claude/commands/forgeue/*.md``
  MUST appear with a negation or env-guard marker (``不引入`` / ``不开`` /
  ``opt-in`` / ``env guard`` / ``{1,true,yes,on}`` / ``Level 0`` /
  ``默认``).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import forgeue_verify as fv  # noqa: E402

CMD_DIR = _REPO / ".claude" / "commands" / "forgeue"


# ---------------------------------------------------------------------------
# Tool defaults (argparse + StepPlan env_var)
# ---------------------------------------------------------------------------


def test_forgeue_verify_argparse_default_level_is_zero():
    parser = fv._build_parser()
    ns = parser.parse_args(["--change", "x"])
    assert ns.level == 0, f"--level default must be 0, got {ns.level}"


def test_each_l1_l2_step_has_env_guard():
    plan = fv.build_plan(2)
    bad = []
    for s in plan:
        if s.level >= 1 and s.env_var is None:
            bad.append(f"L{s.level} step {s.name!r} has no env_var")
    assert not bad, "; ".join(bad)


def test_each_l1_l2_step_env_guard_uses_forgeue_verify_live_prefix():
    plan = fv.build_plan(2)
    bad = []
    for s in plan:
        if s.level >= 1 and s.env_var is not None:
            if not s.env_var.startswith("FORGEUE_VERIFY_LIVE_"):
                bad.append(f"L{s.level} step {s.name!r} env_var={s.env_var!r}")
    assert not bad, "; ".join(bad)


# ---------------------------------------------------------------------------
# Cmd md: paid / live mentions must be qualified
# ---------------------------------------------------------------------------


_NEG_OR_GUARD_MARKERS = (
    "不引入",
    "不开",
    "不强制",
    "默认不开",
    "默认走",
    "opt-in",
    "env guard",
    "{1,true,yes,on}",
    "Level 0",
    "level 0",
    "默认 0",
    "(默认)",
    "SKIP",
    "需",
    "FORGEUE_",
    "Pre-P0",
)


@pytest.fixture(scope="module")
def cmd_files() -> list[Path]:
    files = sorted(CMD_DIR.glob("change-*.md"))
    assert len(files) == 8
    return files


def test_paid_mentions_qualified(cmd_files):
    bad = []
    for f in cmd_files:
        for ln_no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "paid" not in line.lower():
                continue
            # bare reference to "paid" (e.g. in description text) is OK iff line
            # ALSO has a negation/guard marker.
            if not any(m in line for m in _NEG_OR_GUARD_MARKERS):
                bad.append(f"{f.name}:{ln_no}: {line.strip()}")
    assert not bad, "paid mention without guard:\n  " + "\n  ".join(bad)


def test_live_mentions_qualified(cmd_files):
    bad = []
    for f in cmd_files:
        for ln_no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            # Skip obviously unrelated "live" tokens (e.g. words like "delivery"
            # don't contain "live" but "alive" does — we want only standalone
            # "live"). Use word-boundary check.
            lower = line.lower()
            if " live " not in (" " + lower + " ") and "live-" not in lower and "live UE" not in line and "live LLM" not in line and "live ComfyUI" not in line and "live mesh" not in line and "live provider" not in line and "live mode" not in line:
                continue
            if not any(m in line for m in _NEG_OR_GUARD_MARKERS):
                bad.append(f"{f.name}:{ln_no}: {line.strip()}")
    assert not bad, "live mention without guard:\n  " + "\n  ".join(bad)


def test_no_default_higher_level_invocation_in_cmd_md(cmd_files):
    """No cmd md should suggest invoking ``--level 1`` or ``--level 2`` by
    default. Allowed: explicit examples that pair with env-guard text on
    the same line (or contiguous lines)."""
    bad = []
    for f in cmd_files:
        text = f.read_text(encoding="utf-8")
        for forbidden in ("--level 1", "--level 2"):
            # Find each occurrence and check surrounding context (same line).
            for ln_no, line in enumerate(text.splitlines(), 1):
                if forbidden in line:
                    if not any(m in line for m in _NEG_OR_GUARD_MARKERS):
                        bad.append(f"{f.name}:{ln_no}: {line.strip()}")
    assert not bad, f"--level 1/2 invocation without guard:\n  " + "\n  ".join(bad)
