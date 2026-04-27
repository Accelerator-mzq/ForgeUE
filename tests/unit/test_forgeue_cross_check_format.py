"""tasks.md §5.4.2 fence: cross-check evidence files have valid frontmatter
+ A/B/C/D body sections.

Scans BOTH:

- Real cross-check files in ``openspec/changes/<active-id>/review/*cross_check*.md``
  (regression fence on self-host evidence).
- A builder-generated fixture (forward fence on the
  ``make_complete_change`` factory).

Per design.md §3 Cross-check Protocol:

- frontmatter MUST carry ``disputed_open`` (int).
- body MUST contain ``## A.`` / ``## B.`` / ``## C.`` / ``## D.`` headings.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))
_FIXTURES = _REPO / "tests" / "fixtures" / "forgeue_workflow"
if str(_FIXTURES) not in sys.path:
    sys.path.insert(0, str(_FIXTURES))

import _common  # noqa: E402
from builders import make_complete_change  # noqa: E402

CHANGES_DIR = _REPO / "openspec" / "changes"


def _real_cross_check_files() -> list[Path]:
    out: list[Path] = []
    if not CHANGES_DIR.is_dir():
        return out
    for change in CHANGES_DIR.iterdir():
        if not change.is_dir() or change.name == "archive":
            continue
        review = change / "review"
        if not review.is_dir():
            continue
        out.extend(sorted(review.glob("*cross_check*.md")))
    # Also walk archive (cross-check files in archived changes are also fence-targeted)
    archive = CHANGES_DIR / "archive"
    if archive.is_dir():
        for change in archive.iterdir():
            if not change.is_dir():
                continue
            review = change / "review"
            if not review.is_dir():
                continue
            out.extend(sorted(review.glob("*cross_check*.md")))
    return out


@pytest.mark.parametrize("path", _real_cross_check_files(), ids=lambda p: p.name)
def test_real_cross_check_file_format(path):
    text = path.read_text(encoding="utf-8")
    fm, body = _common.parse_frontmatter(text)
    # frontmatter must carry disputed_open
    assert "disputed_open" in fm, f"{path.name} missing disputed_open in frontmatter"
    # disputed_open must be an int
    assert isinstance(fm["disputed_open"], int), (
        f"{path.name} disputed_open not int: {fm['disputed_open']!r}"
    )
    # body must contain A/B/C/D section headings
    for marker in ("## A.", "## B.", "## C.", "## D."):
        assert marker in body, f"{path.name} body missing section heading {marker!r}"


def test_builder_complete_fixture_cross_check_format(tmp_path):
    b = make_complete_change(tmp_path, "fc-cc-fixture", with_cross_check=True)
    cc_paths = list((tmp_path / "openspec" / "changes" / "fc-cc-fixture" / "review").glob("*cross_check*.md"))
    assert len(cc_paths) == 2  # design + plan cross-check
    for cc in cc_paths:
        text = cc.read_text(encoding="utf-8")
        fm, body = _common.parse_frontmatter(text)
        assert "disputed_open" in fm
        assert fm["disputed_open"] == 0
        for marker in ("## A.", "## B.", "## C.", "## D."):
            assert marker in body


def test_real_cross_check_files_have_evidence_type(test_files=_real_cross_check_files()):
    """All real cross-check files must have evidence_type ∈ {design_cross_check,
    plan_cross_check}."""
    for f in test_files:
        text = f.read_text(encoding="utf-8")
        fm, _ = _common.parse_frontmatter(text)
        ev_type = fm.get("evidence_type")
        assert ev_type in ("design_cross_check", "plan_cross_check"), (
            f"{f.name} has unexpected evidence_type={ev_type!r}"
        )


def test_at_least_one_real_cross_check_exists():
    """Sanity: self-host change should produce at least one cross-check file."""
    files = _real_cross_check_files()
    assert files, "no cross-check files found under openspec/changes/**/review/"
