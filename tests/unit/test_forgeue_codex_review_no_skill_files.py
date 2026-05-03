"""tasks.md §5.5.1 anti-pattern fence: ``.codex/skills/forgeue-*-review/``
must NOT exist.

Per design.md §6 + proposal §3.3.2: codex review uses the codex-plugin-cc
``/codex:*`` slash commands directly, not a wrapper skill under
``.codex/skills/``. Adding wrapper skills duplicates plugin behavior and
risks divergence; this fence prevents accidental re-introduction.
"""
from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def test_no_codex_skills_forgeue_review_dirs():
    codex_skills = _REPO / ".codex" / "skills"
    if not codex_skills.is_dir():
        return
    bad = list(codex_skills.glob("forgeue-*-review"))
    bad.extend(codex_skills.glob("forgeue-*-review/SKILL.md"))
    assert not bad, (
        "anti-pattern detected: forgeue-*-review skill files under "
        f".codex/skills/ -- {bad}"
    )


def test_no_codex_skills_forgeue_review_files_anywhere():
    codex_skills = _REPO / ".codex" / "skills"
    if not codex_skills.is_dir():
        return
    forbidden_pattern_dirs = sorted(
        d for d in codex_skills.iterdir()
        if d.is_dir() and d.name.startswith("forgeue-") and d.name.endswith("-review")
    )
    assert not forbidden_pattern_dirs, (
        f"forgeue-*-review skill directories must not exist: {forbidden_pattern_dirs}"
    )
