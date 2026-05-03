"""tasks.md §5.4.3 fence: 2 forgeue-* SKILL.md files have required
frontmatter keys (name / description / license / compatibility / metadata).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import _common  # noqa: E402

SKILL_DIR = _REPO / ".claude" / "skills"


@pytest.fixture(scope="module")
def forgeue_skill_files() -> list[Path]:
    files = sorted(SKILL_DIR.glob("forgeue-*/SKILL.md"))
    assert len(files) == 2, (
        f"expected exactly 2 forgeue-* SKILL.md files, found {len(files)}"
    )
    return files


def test_expected_two_skills_present(forgeue_skill_files):
    names = sorted(f.parent.name for f in forgeue_skill_files)
    expected = ["forgeue-doc-sync-gate", "forgeue-integrated-change-workflow"]
    assert names == expected, f"skill set mismatch: {names}"


def test_each_skill_has_required_frontmatter_keys(forgeue_skill_files):
    required_keys = {
        "name",
        "description",
        "license",
        "compatibility",
        "metadata",
    }
    bad: list[str] = []
    for f in forgeue_skill_files:
        text = f.read_text(encoding="utf-8")
        fm, _ = _common.parse_frontmatter(text)
        missing = required_keys - set(fm.keys())
        if missing:
            bad.append(f"{f.parent.name}: missing {sorted(missing)}")
    assert not bad, "skill md missing required keys:\n  " + "\n  ".join(bad)


def test_each_skill_license_is_mit(forgeue_skill_files):
    for f in forgeue_skill_files:
        fm, _ = _common.parse_frontmatter(f.read_text(encoding="utf-8"))
        assert fm.get("license") == "MIT", (
            f"{f.parent.name} license={fm.get('license')!r} (expected MIT)"
        )


def test_each_skill_metadata_block_has_author_and_version(forgeue_skill_files):
    """The minimal YAML subset parser does not unfold nested mappings, so
    look for ``author:`` / ``version:`` literals inside the raw frontmatter
    block (between the leading ``---`` markers)."""
    for f in forgeue_skill_files:
        text = f.read_text(encoding="utf-8")
        fm_text, _ = _common.split_frontmatter(text)
        assert "author" in fm_text, f"{f.parent.name} frontmatter missing author"
        assert "version" in fm_text, f"{f.parent.name} frontmatter missing version"


def test_skill_name_starts_with_forgeue(forgeue_skill_files):
    for f in forgeue_skill_files:
        fm, _ = _common.parse_frontmatter(f.read_text(encoding="utf-8"))
        name = fm.get("name", "")
        assert isinstance(name, str) and name.startswith("forgeue-"), (
            f"{f.parent.name} frontmatter name={name!r}"
        )


def test_no_duplicated_tdd_skill_present():
    """Anti-pattern: ``forgeue-superpowers-tdd-execution`` must NOT exist
    (duplicates Superpowers ``test-driven-development`` skill, decision
    14.18 / proposal §3.3.1)."""
    forbidden = SKILL_DIR / "forgeue-superpowers-tdd-execution"
    assert not forbidden.exists(), (
        f"duplicated TDD skill exists at {forbidden}; remove per design.md §6 + tasks.md §3.3.1"
    )
