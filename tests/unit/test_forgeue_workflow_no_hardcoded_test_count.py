"""tasks.md §5.6.3 cross-cutting fence: tool source must not hardcode the
pytest test count.

Per the project-wide rule (CLAUDE.md ``测试纪律``): the source of truth is
``python -m pytest -q`` actual output, not a baseline number. Hardcoding a
number in a comparison (e.g. ``count == 848``) breaks every time the suite
grows.

Forbidden patterns matched in tool source files (NOT docstrings — we
deliberately use a regex that targets equality comparisons in code):

- ``== 848`` / ``==848`` / ``!= 848`` (current baseline)
- ``== 491`` / ``==491`` (older P3 baseline)
- ``== 549`` / ``==549`` (Plan C baseline)
- ``== 880`` / ``==880`` (forward-looking P4 baseline)

Forbidden also: literal ``passed=`` followed by an integer ``> 100``.
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_TOOL_FILES = sorted((_REPO / "tools").glob("forgeue_*.py"))


_FORBIDDEN_BASELINES = ("491", "549", "848", "880")


def _hardcoded_count_re() -> re.Pattern[str]:
    """Match ``== <baseline>`` / ``!= <baseline>`` for known counts."""
    nums = "|".join(_FORBIDDEN_BASELINES)
    return re.compile(rf"(?<![\w])(==|!=)\s*({nums})(?![\w])")


def test_no_hardcoded_test_count_in_tool_source():
    pat = _hardcoded_count_re()
    bad: list[str] = []
    for f in _TOOL_FILES:
        for ln_no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(line):
                bad.append(f"{f.name}:{ln_no}: {line.strip()}")
    assert not bad, "hardcoded pytest count detected:\n  " + "\n  ".join(bad)


def test_no_passed_assignment_count_literals():
    """Match ``passed=N`` / ``passed = N`` where N >= 100 — likely a
    baseline assertion that drifts as the suite grows."""
    pat = re.compile(r"\bpassed\s*=\s*(\d{3,})")
    bad: list[str] = []
    for f in _TOOL_FILES:
        for ln_no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in pat.finditer(line):
                # Allow comparison via parsing summary string (e.g. checking
                # 'passed' in summary text); skip lines that are clearly
                # parsing rather than asserting baseline.
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""'):
                    continue
                if "summary" in line.lower() or "parse" in line.lower():
                    continue
                bad.append(f"{f.name}:{ln_no}: {stripped}")
    assert not bad, "passed=N literal in tool source:\n  " + "\n  ".join(bad)


def test_tool_files_present():
    assert len(_TOOL_FILES) >= 5, f"expected >= 5 forgeue_*.py tools, found {len(_TOOL_FILES)}"
