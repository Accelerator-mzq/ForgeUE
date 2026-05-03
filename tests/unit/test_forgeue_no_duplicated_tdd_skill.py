"""tasks.md §5.5.2 anti-pattern fence:
``.claude/skills/forgeue-superpowers-tdd-execution/`` must NOT exist.

Per design.md §6 + proposal §3.3.1: Superpowers already ships a
``test-driven-development`` skill; ForgeUE must NOT shadow it with
``forgeue-superpowers-tdd-execution``. This fence prevents accidental
re-introduction.
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def test_no_duplicated_tdd_skill_dir():
    forbidden = _REPO / ".claude" / "skills" / "forgeue-superpowers-tdd-execution"
    assert not forbidden.exists(), (
        "anti-pattern: forgeue-superpowers-tdd-execution exists at "
        f"{forbidden}; remove and rely on Superpowers test-driven-development "
        "skill (decision 14.18 / proposal §3.3.1)"
    )


def test_no_duplicated_tdd_skill_md_anywhere():
    """Belt-and-suspenders: also ban a stray SKILL.md anywhere named
    ``forgeue-superpowers-tdd-execution``."""
    skills_dir = _REPO / ".claude" / "skills"
    if not skills_dir.is_dir():
        return
    matches = sorted(
        d for d in skills_dir.iterdir()
        if d.is_dir() and d.name == "forgeue-superpowers-tdd-execution"
    )
    assert not matches, f"forbidden TDD skill found: {matches}"
