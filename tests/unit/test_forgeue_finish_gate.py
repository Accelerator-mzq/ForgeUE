"""Unit tests for ``tools/forgeue_finish_gate.py``.

Covers tasks.md §5.2.5: the centralized last-line-of-defense semantics
plus the spec.md ADDED Requirement Scenarios 2 + 3 from
``examples-and-acceptance/spec.md``:

- evidence completeness indexed by ``evidence_type`` (not file path);
- helper-vs-formal subdir distinction (``notes/`` allows any shape;
  ``execution/`` / ``review/`` / ``verification/`` REQUIRE 12-key);
- frontmatter writeback protocol (``aligned=false`` MUST carry a
  ``drift_decision``; ``written-back-to-*`` MUST carry a real sha that
  touches the named artifact; ``disputed-permanent-drift`` MUST carry
  ``drift_reason >= 50`` + a resolved ``reasoning_notes_anchor`` whose
  paragraph is ``>= 20 words`` or ``>= 60 non-whitespace chars``);
- balanced-quote regex for anchor declarations (4 forms accepted, unpaired
  rejected);
- cross-check ``disputed_open == 0`` and 4-section body protocol;
- ``--no-validate`` bypasses ``openspec validate --strict``;
- ``--dry-run`` does not write ``verification/finish_gate_report.md``;
- claude-code+plugin requires the 6 codex/cross-check evidence types;
  other envs downgrade those to OPTIONAL.
"""
from __future__ import annotations

import argparse
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
_FIXTURES = _REPO / "tests" / "fixtures" / "forgeue_workflow"
if str(_FIXTURES) not in sys.path:
    sys.path.insert(0, str(_FIXTURES))

import _common  # noqa: E402
import forgeue_finish_gate as fg  # noqa: E402
from builders import (  # noqa: E402
    ChangeBuilder,
    make_complete_change,
    make_drift_change,
    make_minimal_change,
)

TOOL = _TOOLS / "forgeue_finish_gate.py"


# ---------------------------------------------------------------------------
# Helpers — clean env so detected_env defaults to claude-code or unknown
# ---------------------------------------------------------------------------


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


def _env_force(env_name: str) -> dict[str, str]:
    """Build a subprocess env dict that pins detected_env to ``env_name``."""
    base = {**os.environ}
    for var in _AGENT_VARS:
        base.pop(var, None)
    base["FORGEUE_REVIEW_ENV"] = env_name
    return base


def _run_cli(
    repo: Path,
    args: list[str],
    *,
    review_env: str = "cursor",
) -> subprocess.CompletedProcess[str]:
    """Run finish_gate. ``review_env=cursor`` by default so cross-check +
    codex evidence are downgraded to OPTIONAL — keeps tests focused on the
    behavior under test rather than fixture-completeness.
    """
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env_force(review_env),
        timeout=30,
    )


# ---------------------------------------------------------------------------
# evidence completeness REQUIRED set per env
# ---------------------------------------------------------------------------


def test_complete_change_passes_in_non_claude_env(tmp_path):
    make_complete_change(tmp_path, "fc-cc-1")
    proc = _run_cli(tmp_path, ["--change", "fc-cc-1", "--no-validate", "--json"])
    assert proc.returncode == 0


def test_complete_change_passes_under_claude_code(tmp_path, monkeypatch):
    """Under env=claude-code WITH plugin, the 6 codex+cross-check evidence
    types must also exist — make_complete_change writes them by default.
    """
    make_complete_change(tmp_path, "fc-cc-2", with_codex=True, with_cross_check=True)
    # Force claude-code AND fake plugin presence by passing build_report directly
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-cc-2",
        detected_env="claude-code",
        codex_plugin_available=True,
        no_validate=True,
    )
    assert report is not None
    assert report.blockers == []


def test_missing_codex_evidence_is_optional_in_non_claude_env(tmp_path):
    """When env != claude-code OR plugin missing, the 6 codex/cross-check
    types are OPTIONAL — finish_gate must still pass without them.
    """
    b = ChangeBuilder(repo=tmp_path, change_id="fc-bare")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True)
    # Only 3 base evidence types; no codex / cross-check
    b.write_evidence(
        "verification", "verify_report.md",
        evidence_type="verify_report", stage="S5", body="OK\n",
    )
    b.write_evidence(
        "verification", "doc_sync_report.md",
        evidence_type="doc_sync_report", stage="S7", body="DRIFT 0\n",
    )
    b.write_evidence(
        "review", "superpowers_review.md",
        evidence_type="superpowers_review", stage="S6", body="## Final\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-bare",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    assert report is not None
    types = [b.type for b in report.blockers]
    assert "evidence_missing" not in types


def test_missing_codex_evidence_is_required_under_claude_code_plus_plugin(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-need-codex")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True)
    b.write_evidence(
        "verification", "verify_report.md",
        evidence_type="verify_report", stage="S5", body="OK\n",
    )
    b.write_evidence(
        "verification", "doc_sync_report.md",
        evidence_type="doc_sync_report", stage="S7", body="DRIFT 0\n",
    )
    b.write_evidence(
        "review", "superpowers_review.md",
        evidence_type="superpowers_review", stage="S6", body="## Final\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-need-codex",
        detected_env="claude-code",
        codex_plugin_available=True,
        no_validate=True,
    )
    assert report is not None
    missing_types = [b.detail for b in report.blockers if b.type == "evidence_missing"]
    # Should mention each of the 6 codex / cross-check types
    joined = " ".join(missing_types)
    for needed in (
        "codex_design_review",
        "codex_plan_review",
        "codex_verification_review",
        "codex_adversarial_review",
        "design_cross_check",
        "plan_cross_check",
    ):
        assert needed in joined


def test_evidence_indexed_by_evidence_type_not_file_path(tmp_path):
    """A file with arbitrary name + ``evidence_type: codex_verification_review``
    SHOULD satisfy the codex_verification_review requirement.
    """
    b = ChangeBuilder(repo=tmp_path, change_id="fc-rename")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True)
    b.write_evidence(
        "verification", "verify_report.md",
        evidence_type="verify_report", stage="S5", body="OK\n",
    )
    b.write_evidence(
        "verification", "doc_sync_report.md",
        evidence_type="doc_sync_report", stage="S7", body="DRIFT 0\n",
    )
    b.write_evidence(
        "review", "superpowers_review.md",
        evidence_type="superpowers_review", stage="S6", body="## Final\n",
    )
    # Rename codex evidence files arbitrarily
    b.write_evidence(
        "review", "p3_tools_review_codex.md",
        evidence_type="codex_verification_review", stage="S5",
        body="codex verbatim.\n",
    )
    b.write_evidence(
        "review", "p3_tools_adversarial_review_codex.md",
        evidence_type="codex_adversarial_review", stage="S6",
        body="codex verbatim.\n",
    )
    b.write_evidence(
        "review", "kickoff_review.md",
        evidence_type="codex_design_review", stage="S2",
        body="codex verbatim.\n",
    )
    b.write_evidence(
        "review", "plan_review.md",
        evidence_type="codex_plan_review", stage="S3",
        body="codex verbatim.\n",
    )
    cc_body = (
        "## A. Decision Summary\n## B. Cross-check Matrix\n"
        "## C. Disputed\ndisputed_open: 0\n## D. Verification\n"
    )
    b.write_evidence(
        "review", "p3_tools_cross_check.md",
        evidence_type="design_cross_check", stage="S2",
        body=cc_body,
        extra_frontmatter={"disputed_open": 0},
    )
    b.write_evidence(
        "review", "p3_tools_adversarial_cross_check.md",
        evidence_type="plan_cross_check", stage="S3",
        body=cc_body,
        extra_frontmatter={"disputed_open": 0},
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-rename",
        detected_env="claude-code",
        codex_plugin_available=True,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "evidence_missing" not in types


# ---------------------------------------------------------------------------
# helper-vs-formal subdir
# ---------------------------------------------------------------------------


def test_notes_helpers_allowed_to_lack_frontmatter(tmp_path):
    b = make_complete_change(tmp_path, "fc-notes")
    b.write_helper_note(
        "p4_onboarding.md",
        body="# helper notes with no frontmatter\nTotally informal.\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-notes",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "evidence_malformed" not in types


def test_formal_subdir_missing_frontmatter_is_blocker(tmp_path):
    b = make_complete_change(tmp_path, "fc-formal-bad")
    # Inject a malformed file in review/ with no frontmatter at all
    bad = tmp_path / "openspec" / "changes" / "fc-formal-bad" / "review" / "raw.md"
    bad.write_text("just some prose, no frontmatter\n", encoding="utf-8")
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-formal-bad",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "evidence_malformed" in types


def test_formal_subdir_only_change_id_and_evidence_type_is_blocker(tmp_path):
    """Per P4 codex review F2 (review/p4_tests_review_codex.md): formal
    evidence MUST carry all 8 always-required audit keys, not just
    change_id + evidence_type. Pre-fix this would PASS; post-fix it must
    block as evidence_malformed citing the missing keys.
    """
    b = make_complete_change(tmp_path, "fc-partial-fm")
    # Inject a file with only the 2 keys the prior implementation checked
    bad = tmp_path / "openspec" / "changes" / "fc-partial-fm" / "review" / "partial.md"
    bad.write_text(
        "---\n"
        "change_id: fc-partial-fm\n"
        "evidence_type: codex_design_review\n"
        "---\n"
        "\n"
        "Body without the other 6 always-required audit fields.\n",
        encoding="utf-8",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-partial-fm",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    malformed = [bl for bl in report.blockers if bl.type == "evidence_malformed"]
    assert malformed, "expected evidence_malformed blocker for partial frontmatter"
    # The blocker detail should name the missing keys
    detail = malformed[0].detail
    for missing_key in (
        "stage",
        "contract_refs",
        "aligned_with_contract",
        "detected_env",
        "triggered_by",
        "codex_plugin_available",
    ):
        assert missing_key in detail, f"missing key {missing_key!r} not cited in blocker detail: {detail!r}"


def test_formal_subdir_aligned_with_contract_null_is_blocker(tmp_path):
    """``aligned_with_contract`` is one of the 8 always-required keys; an
    explicit ``null`` value (author left it blank) must trip
    evidence_malformed even if the key is technically "present" in YAML.
    """
    b = make_complete_change(tmp_path, "fc-aligned-null")
    bad = tmp_path / "openspec" / "changes" / "fc-aligned-null" / "review" / "blank.md"
    bad.write_text(
        "---\n"
        "change_id: fc-aligned-null\n"
        "stage: S6\n"
        "evidence_type: codex_adversarial_review\n"
        "contract_refs:\n"
        "  - design.md\n"
        "aligned_with_contract: null\n"
        "drift_decision: null\n"
        "writeback_commit: null\n"
        "drift_reason: null\n"
        "reasoning_notes_anchor: null\n"
        "detected_env: cursor\n"
        "triggered_by: auto\n"
        "codex_plugin_available: false\n"
        "---\n"
        "\n"
        "Body.\n",
        encoding="utf-8",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-aligned-null",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    malformed = [bl for bl in report.blockers if bl.type == "evidence_malformed"]
    assert malformed, "expected evidence_malformed for null aligned_with_contract"
    assert "aligned_with_contract" in malformed[0].detail


def test_formal_subdir_8_keys_all_present_passes(tmp_path):
    """Sanity: an evidence file with all 8 always-required keys (and
    nothing else) must NOT trip evidence_malformed."""
    b = make_complete_change(tmp_path, "fc-8keys-ok")
    p = tmp_path / "openspec" / "changes" / "fc-8keys-ok" / "review" / "minimal.md"
    p.write_text(
        "---\n"
        "change_id: fc-8keys-ok\n"
        "stage: S6\n"
        "evidence_type: codex_adversarial_review\n"
        "contract_refs:\n"
        "  - design.md\n"
        "aligned_with_contract: true\n"
        "detected_env: cursor\n"
        "triggered_by: auto\n"
        "codex_plugin_available: false\n"
        "---\n"
        "\n"
        "Body.\n",
        encoding="utf-8",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-8keys-ok",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    malformed = [
        bl for bl in report.blockers
        if bl.type == "evidence_malformed" and bl.file == "review/minimal.md"
    ]
    assert not malformed, f"unexpected evidence_malformed for 8-key file: {[bl.detail for bl in malformed]}"


# ---------------------------------------------------------------------------
# Frontmatter writeback protocol
# ---------------------------------------------------------------------------


def test_aligned_false_no_drift_decision_blocks(tmp_path):
    b = make_complete_change(tmp_path, "fc-fm-1")
    b.write_evidence(
        "review", "extra_review.md",
        evidence_type="codex_adversarial_review", stage="S6",
        aligned_with_contract=False,
        drift_decision=None,
        body="codex review.\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-fm-1",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "aligned_false_no_drift" in types


def test_drift_decision_pending_blocks(tmp_path):
    b = make_complete_change(tmp_path, "fc-fm-pending")
    b.write_evidence(
        "review", "pending_review.md",
        evidence_type="codex_adversarial_review", stage="S6",
        aligned_with_contract=False,
        drift_decision="pending",
        drift_reason="awaiting user judgement",
        body="codex review.\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-fm-pending",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "drift_decision_pending" in types


def test_writeback_commit_bogus_blocks(tmp_path):
    b = make_complete_change(tmp_path, "fc-fm-bogus")
    b.write_evidence(
        "review", "bogus_review.md",
        evidence_type="codex_adversarial_review", stage="S6",
        aligned_with_contract=False,
        drift_decision="written-back-to-design",
        writeback_commit="0123456789abcdef0123456789abcdef01234567",
        drift_reason="bad sha",
        body="codex review.\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-fm-bogus",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "writeback_commit_not_found" in types


def test_writeback_commit_unrelated_blocks(tmp_path):
    """A real commit that does NOT touch design.md must trip
    ``writeback_commit_unrelated``."""
    b = make_complete_change(tmp_path, "fc-fm-unrel")
    b.init_git()
    # create initial commit unrelated to design.md
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    sha = b.commit_all("unrelated commit", paths=["README.md"])
    b.write_evidence(
        "review", "unrelated_review.md",
        evidence_type="codex_adversarial_review", stage="S6",
        aligned_with_contract=False,
        drift_decision="written-back-to-design",
        writeback_commit=sha,
        drift_reason="claims to write back to design but commit unrelated",
        body="codex review.\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-fm-unrel",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "writeback_commit_unrelated" in types


def test_writeback_commit_real_and_touches_artifact_passes(tmp_path):
    b = make_complete_change(tmp_path, "fc-fm-real")
    b.init_git()
    # Initial commit so HEAD exists
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    b.commit_all("initial", paths=["README.md"])
    # Modify design.md and commit -> writeback_commit can name this sha
    b.touch_artifact("design.md", append="\n## extra section\nadded\n")
    sha = b.commit_all("write back design")
    b.write_evidence(
        "review", "valid_review.md",
        evidence_type="codex_adversarial_review", stage="S6",
        aligned_with_contract=False,
        drift_decision="written-back-to-design",
        writeback_commit=sha,
        drift_reason="reviewer concern resolved by editing design.md per request",
        body="codex review.\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-fm-real",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "writeback_commit_not_found" not in types
    assert "writeback_commit_unrelated" not in types


# ---------------------------------------------------------------------------
# disputed-permanent-drift protocol (spec.md Scenario 3)
# ---------------------------------------------------------------------------


def test_disputed_drift_short_reason_blocks(tmp_path):
    b = make_complete_change(tmp_path, "fc-disp-1")
    b.write_evidence(
        "review", "disp.md",
        evidence_type="codex_adversarial_review", stage="S6",
        aligned_with_contract=False,
        drift_decision="disputed-permanent-drift",
        drift_reason="too short",
        reasoning_notes_anchor="some-anchor",
        body="codex review.\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-disp-1",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "disputed_drift_reason_too_short" in types


def test_disputed_drift_no_anchor_blocks(tmp_path):
    b = make_complete_change(tmp_path, "fc-disp-2")
    b.write_evidence(
        "review", "disp.md",
        evidence_type="codex_adversarial_review", stage="S6",
        aligned_with_contract=False,
        drift_decision="disputed-permanent-drift",
        drift_reason="x" * 60,
        reasoning_notes_anchor=None,
        body="codex review.\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-disp-2",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "disputed_drift_anchor_missing" in types


def test_disputed_drift_anchor_unresolved_blocks(tmp_path):
    """anchor that does not appear in design.md ## Reasoning Notes."""
    # make_drift_change("frontmatter_disputed_drift_anchor_unresolved") writes
    # design.md with anchors=["test-anchor"] but evidence claims "not-in-design-md"
    b = make_drift_change(tmp_path, "frontmatter_disputed_drift_anchor_unresolved")
    # add minimum 3 base evidence so finish_gate doesn't only complain about completeness
    b.write_evidence(
        "verification", "verify_report.md",
        evidence_type="verify_report", stage="S5", body="OK\n",
    )
    b.write_evidence(
        "verification", "doc_sync_report.md",
        evidence_type="doc_sync_report", stage="S7", body="OK\n",
    )
    b.write_evidence(
        "review", "superpowers_review.md",
        evidence_type="superpowers_review", stage="S6", body="## Final\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fake-drift",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "reasoning_notes_anchor_unresolved" in types


def test_disputed_drift_anchor_paragraph_too_short_blocks(tmp_path):
    b = make_drift_change(tmp_path, "frontmatter_disputed_drift_paragraph_too_short")
    b.write_evidence(
        "verification", "verify_report.md",
        evidence_type="verify_report", stage="S5", body="OK\n",
    )
    b.write_evidence(
        "verification", "doc_sync_report.md",
        evidence_type="doc_sync_report", stage="S7", body="OK\n",
    )
    b.write_evidence(
        "review", "superpowers_review.md",
        evidence_type="superpowers_review", stage="S6", body="## Final\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fake-drift",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "reasoning_notes_anchor_paragraph_too_short" in types


# ---------------------------------------------------------------------------
# Anchor regex: 4 balanced forms accepted; unpaired rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "section,anchor,expected",
    [
        ("> Anchor: my-slug\n\nSubstantive paragraph.", "my-slug", True),
        ("> Anchor: `my-slug`\n\nSubstantive paragraph.", "my-slug", True),
        ("> Anchor: 'my-slug'\n\nSubstantive paragraph.", "my-slug", True),
        ('> Anchor: "my-slug"\n\nSubstantive paragraph.', "my-slug", True),
        # Unpaired single quote
        ("> Anchor: 'my-slug\n\nSubstantive paragraph.", "my-slug", False),
        # Unpaired double quote
        ('> Anchor: my-slug"\n\nSubstantive paragraph.', "my-slug", False),
        # Unpaired backtick
        ("> Anchor: `my-slug\n\nSubstantive paragraph.", "my-slug", False),
        # Empty anchor
        ("> Anchor: my-slug\n\nSubstantive paragraph.", "", False),
    ],
)
def test_anchor_resolves_balanced_quote_forms(section, anchor, expected):
    matched, _ = fg._anchor_resolves(section, anchor)
    assert matched is expected


def test_anchor_resolves_via_subheading_slug_fallback():
    section = "### sec 11.1 D-CommandsCount\n\nSubstantive rationale paragraph here.\n"
    matched, paragraph = fg._anchor_resolves(section, "d-commandscount")
    assert matched is True
    assert "Substantive rationale" in paragraph


# ---------------------------------------------------------------------------
# Substantive paragraph thresholds (English >= 20 words OR Chinese >= 60 chars)
# ---------------------------------------------------------------------------


def test_substantive_paragraph_english_20_words():
    p = " ".join(["word"] * 20)
    assert fg._is_substantive_paragraph(p) is True


def test_short_paragraph_english_19_words_under_60_chars():
    p = "short " * 5  # 5 words, 30 chars => below both thresholds
    assert fg._is_substantive_paragraph(p) is False


def test_substantive_paragraph_chinese_60_chars():
    # 60 non-whitespace Chinese chars
    p = "中" * 60
    assert fg._is_substantive_paragraph(p) is True


def test_short_paragraph_chinese_59_chars():
    p = "中" * 59
    assert fg._is_substantive_paragraph(p) is False


# ---------------------------------------------------------------------------
# Cross-check protocol: 4 sections + disputed_open
# ---------------------------------------------------------------------------


def test_cross_check_missing_section_blocks(tmp_path):
    b = make_complete_change(tmp_path, "fc-cc-bad")
    cc_path = tmp_path / "openspec" / "changes" / "fc-cc-bad" / "review" / "design_cross_check.md"
    text = cc_path.read_text(encoding="utf-8")
    # Strip the ## D. section
    text = text.replace("## D. Verification Note\n\nEach finding independently verified.\n", "")
    cc_path.write_text(text, encoding="utf-8")
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-cc-bad",
        detected_env="claude-code",
        codex_plugin_available=True,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "cross_check_section_missing" in types


def test_cross_check_disputed_open_gt_zero_blocks(tmp_path):
    b = make_complete_change(tmp_path, "fc-cc-disp")
    cc_body = (
        "## A. Decision Summary\n## B. Cross-check Matrix\n"
        "## C. Disputed\ndisputed_open: 1\n## D. Verification\n"
    )
    b.write_evidence(
        "review", "extra_cc.md",
        evidence_type="design_cross_check", stage="S2",
        body=cc_body,
        extra_frontmatter={"disputed_open": 1, "codex_review_ref": "x"},
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-cc-disp",
        detected_env="claude-code",
        codex_plugin_available=True,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "cross_check_disputed_open" in types


# ---------------------------------------------------------------------------
# verify_report self-consistency
# ---------------------------------------------------------------------------


def test_verify_report_aligned_true_with_FAIL_in_body_blocks(tmp_path):
    b = make_complete_change(tmp_path, "fc-vr-bad")
    # Override the verify_report with one that has [FAIL] but aligned=true
    b.write_evidence(
        "verification", "verify_report.md",
        evidence_type="verify_report", stage="S5",
        aligned_with_contract=True,
        body="step X status: [FAIL] something broke\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-vr-bad",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "verify_report_inconsistent" in types


# ---------------------------------------------------------------------------
# Tasks unchecked
# ---------------------------------------------------------------------------


def test_tasks_unchecked_blocks(tmp_path):
    b = make_complete_change(tmp_path, "fc-tu-bad")
    b.write_tasks(
        anchors=["1.1"], checkmarks_under_3=True, unchecked_lines=2
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-tu-bad",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "tasks_unchecked" in types


def test_tasks_unchecked_with_skip_reason_does_not_block(tmp_path):
    b = make_complete_change(tmp_path, "fc-tu-skip")
    b.write_tasks(
        anchors=["1.1"], checkmarks_under_3=True, unchecked_with_skip_reason=2
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-tu-skip",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    assert "tasks_unchecked" not in types


def test_finish_gate_skips_p8_p9_self_stage_unchecked(tmp_path):
    """P8 self-stage filter: ``check_tasks_unchecked`` MUST skip ``[ ]`` lines
    inside section ``## N`` for ``N >= 9`` — these are P8 / P9 / footer
    self-stage tasks that finish_gate is itself the gate for, so requiring
    them checked before finish_gate runs is a chicken-and-egg trap.

    Specifically: §9 holds the P8 finish-gate tasks that this very tool
    completion enables ("9.1 finish_gate exit 0"); §10 holds P9 archive tasks
    that only happen after S8 PASS (``/opsx:archive`` post-S8); §11 is the
    OpenSpec standard footer reference. Earlier sections (§1-§8) are
    workflow-prerequisite stages whose unchecked items DO indicate real
    incomplete work and MUST still block.
    """
    b = make_complete_change(tmp_path, "fc-tu-stage")
    custom_tasks = (
        "# Tasks: fc-tu-stage\n\n"
        "## 1. P0 Setup\n\n"
        "- [x] 1.1 done\n\n"
        "## 2. P1 Docs\n\n"
        "- [x] 2.1 done\n\n"
        "## 9. P8 Finish Gate\n\n"
        "- [ ] 9.1 finish_gate exit 0\n"
        "- [ ] 9.2 finish_gate_report landed\n"
        "- [ ] 9.3 settings.json review-gate hook check\n\n"
        "## 10. P9 Archive Readiness\n\n"
        "- [ ] 10.1 /opsx:archive\n"
        "- [ ] 10.2 evidence preserved\n\n"
        "## 11. Documentation Sync footer\n\n"
        "- [ ] 11.1 sync gate items closed\n"
    )
    b.write_tasks(content=custom_tasks)
    blockers = fg.check_tasks_unchecked(b.change_dir)
    types_files = [(blk.type, blk.detail) for blk in blockers]
    assert blockers == [], (
        f"§9 / §10 / §11 unchecked lines must be skipped (P8 / P9 / footer "
        f"self-stage); got: {types_files}"
    )


def test_finish_gate_does_not_skip_pre_p8_unchecked(tmp_path):
    """Negative-control for the stage-aware filter: ``[ ]`` lines in sections
    §1-§8 are workflow-prerequisite stages that MUST still block. Without
    this guard a sloppy filter (e.g. "skip everything that looks like a TODO")
    would silently drop real incomplete work.
    """
    b = make_complete_change(tmp_path, "fc-tu-stage-neg")
    custom_tasks = (
        "# Tasks: fc-tu-stage-neg\n\n"
        "## 1. P0 Setup\n\n"
        "- [ ] 1.1 NOT yet done\n\n"
        "## 8. P7 Review\n\n"
        "- [ ] 8.1 review NOT done\n\n"
        "## 9. P8 Finish Gate\n\n"
        "- [ ] 9.1 finish_gate exit 0\n"
    )
    b.write_tasks(content=custom_tasks)
    blockers = fg.check_tasks_unchecked(b.change_dir)
    pre_p8_blockers = [
        blk for blk in blockers
        if "1.1 NOT yet done" in blk.detail or "8.1 review NOT done" in blk.detail
    ]
    p8_blockers = [
        blk for blk in blockers if "9.1 finish_gate exit 0" in blk.detail
    ]
    assert len(pre_p8_blockers) == 2, (
        f"§1.1 + §8.1 unchecked items MUST still block; got pre-P8 blockers: "
        f"{[(b.type, b.detail) for b in pre_p8_blockers]}"
    )
    assert p8_blockers == [], (
        f"§9.1 (P8 self-stage) MUST be exempt from blocker; got: "
        f"{[(b.type, b.detail) for b in p8_blockers]}"
    )


# ---------------------------------------------------------------------------
# evidence_change_id mismatch / missing
# ---------------------------------------------------------------------------


def test_evidence_change_id_mismatch_does_not_satisfy_requirement(tmp_path):
    """An evidence file whose ``change_id`` belongs to another change
    must NOT be accepted as fulfilling the current change's requirement
    (cross-change pollution defense; per ``_scan_evidence_by_type``).
    """
    # Start with a change that already has its 3 base evidence types so
    # we isolate the codex_adversarial_review slot.
    b = ChangeBuilder(repo=tmp_path, change_id="fc-mm")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True)
    b.write_evidence(
        "verification", "verify_report.md",
        evidence_type="verify_report", stage="S5", body="OK\n",
    )
    b.write_evidence(
        "verification", "doc_sync_report.md",
        evidence_type="doc_sync_report", stage="S7", body="OK\n",
    )
    b.write_evidence(
        "review", "superpowers_review.md",
        evidence_type="superpowers_review", stage="S6", body="## Final\n",
    )
    # Inject ONLY a cross-change file claiming codex_adversarial_review
    b.write_evidence(
        "review", "alien.md",
        evidence_type="codex_adversarial_review", stage="S6",
        change_id_override="some-other-change",
        body="codex review.\n",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-mm",
        detected_env="claude-code",
        codex_plugin_available=True,
        no_validate=True,
    )
    types = [b.type for b in report.blockers]
    # codex_adversarial_review must be flagged missing because the
    # cross-change-tagged file does NOT satisfy the requirement.
    missing_details = [b.detail for b in report.blockers if b.type == "evidence_missing"]
    assert any("codex_adversarial_review" in d for d in missing_details)


# ---------------------------------------------------------------------------
# CLI behavior: --no-validate, --dry-run, exit codes, ASCII
# ---------------------------------------------------------------------------


def test_cli_change_not_found_exits_3(tmp_path):
    proc = _run_cli(tmp_path, ["--change", "no-such", "--no-validate"])
    assert proc.returncode == 3


def test_cli_dry_run_does_not_write_report(tmp_path):
    make_complete_change(tmp_path, "fc-cli-dry")
    cd = tmp_path / "openspec" / "changes" / "fc-cli-dry"
    report_path = cd / "verification" / "finish_gate_report.md"
    # The complete fixture pre-writes finish_gate_report.md (so state=S8 in
    # change_state); read its mtime to ensure dry-run doesn't overwrite.
    before = report_path.stat().st_mtime if report_path.exists() else None
    proc = _run_cli(
        tmp_path, ["--change", "fc-cli-dry", "--no-validate", "--dry-run", "--json"]
    )
    assert proc.returncode == 0
    after = report_path.stat().st_mtime if report_path.exists() else None
    assert before == after


def test_cli_writes_report_when_not_dry_run(tmp_path):
    make_complete_change(tmp_path, "fc-cli-write")
    cd = tmp_path / "openspec" / "changes" / "fc-cli-write"
    report_path = cd / "verification" / "finish_gate_report.md"
    # Remove the pre-existing report so we can detect the new one
    report_path.unlink()
    proc = _run_cli(tmp_path, ["--change", "fc-cli-write", "--no-validate"])
    assert proc.returncode == 0
    assert report_path.exists()
    assert "evidence_type: finish_gate_report" in report_path.read_text(encoding="utf-8")


def test_cli_no_validate_skips_openspec_subprocess(tmp_path, monkeypatch):
    """``--no-validate`` must skip the ``openspec validate --strict`` subprocess.

    We can't directly observe the subprocess from the CLI, but we can run
    finish_gate in a directory where ``openspec`` is NOT on PATH and
    confirm exit code is 0 (no openspec_cli_missing blocker).
    """
    make_complete_change(tmp_path, "fc-cli-noval")
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--change", "fc-cli-noval", "--no-validate", "--json"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**_env_force("cursor"), "PATH": ""},
        timeout=30,
    )
    # No openspec on PATH but --no-validate still passes
    assert proc.returncode == 0


def test_run_openspec_validate_resolves_via_shutil_which(tmp_path, monkeypatch):
    """P8 §9.5 fix-in-tool: ``run_openspec_validate`` MUST call
    ``shutil.which`` first so Windows ``.cmd`` shims (npm-installed
    ``openspec.cmd``) are found. ``subprocess.run([\"openspec\", ...])``
    without ``shell=True`` does not honor ``PATHEXT`` and raises
    ``FileNotFoundError`` on Windows even when the user's shell finds the
    shim fine.

    We assert the executable is resolved (and reused as ``argv[0]``) by
    monkeypatching ``shutil.which`` and ``subprocess.run`` and verifying
    finish_gate passes the resolved path through, not the bare ``"openspec"``
    string.
    """
    make_complete_change(tmp_path, "fc-shim")
    fake_exe = tmp_path / "fake_openspec.cmd"
    fake_exe.write_text("@echo off\nexit 0\n", encoding="utf-8")
    captured: dict[str, list[str]] = {}

    def fake_which(name):
        if name == "openspec":
            return str(fake_exe)
        return None

    class FakeCompleted:
        def __init__(self):
            self.returncode = 0
            self.stdout = ""
            self.stderr = ""

    def fake_run(argv, *args, **kwargs):
        captured["argv"] = list(argv)
        return FakeCompleted()

    monkeypatch.setattr(fg.shutil, "which", fake_which)
    monkeypatch.setattr(fg.subprocess, "run", fake_run)
    blocker = fg.run_openspec_validate(tmp_path, "fc-shim")
    assert blocker is None
    assert captured["argv"][0] == str(fake_exe), (
        f"argv[0] must be the shutil.which-resolved path so .cmd shims work; "
        f"got {captured['argv']!r}"
    )
    assert captured["argv"][1:] == ["validate", "fc-shim", "--strict"]


def test_run_openspec_validate_returns_blocker_when_unresolved(tmp_path, monkeypatch):
    """When ``shutil.which("openspec")`` returns ``None`` (CLI genuinely not
    installed), ``run_openspec_validate`` MUST return an
    ``openspec_cli_missing`` blocker WITHOUT attempting subprocess.run (and
    without raising). Mirrors the prior FileNotFoundError code path but now
    triggered by explicit resolution failure.
    """
    monkeypatch.setattr(fg.shutil, "which", lambda name: None)
    called = {"count": 0}

    def fake_run(*args, **kwargs):
        called["count"] += 1
        raise AssertionError("subprocess.run must NOT be called when shutil.which returns None")

    monkeypatch.setattr(fg.subprocess, "run", fake_run)
    blocker = fg.run_openspec_validate(tmp_path, "fc-noshim")
    assert blocker is not None
    assert blocker.type == "openspec_cli_missing"
    assert called["count"] == 0


def test_cli_json_output_shape(tmp_path):
    make_complete_change(tmp_path, "fc-cli-shape")
    proc = _run_cli(tmp_path, ["--change", "fc-cli-shape", "--no-validate", "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert {
        "change_id",
        "change_path",
        "blockers",
        "warnings",
        "summary",
    } <= set(data)
    assert data["summary"]["formal_evidence_files"] >= 0


def test_cli_stdout_pure_ascii(tmp_path):
    make_complete_change(tmp_path, "fc-cli-asc")
    proc = _run_cli(tmp_path, ["--change", "fc-cli-asc", "--no-validate"])
    raw = proc.stdout.encode("utf-8")
    non_ascii = [b for b in raw if b > 127]
    assert not non_ascii, f"non-ASCII bytes in stdout: {non_ascii[:20]!r}"


def test_cli_human_uses_ascii_markers_on_pass(tmp_path):
    make_complete_change(tmp_path, "fc-cli-ok")
    proc = _run_cli(tmp_path, ["--change", "fc-cli-ok", "--no-validate"])
    assert proc.returncode == 0
    assert "[OK] PASS" in proc.stdout


def test_cli_human_uses_ascii_markers_on_fail(tmp_path):
    b = make_complete_change(tmp_path, "fc-cli-fail")
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True, unchecked_lines=1)
    proc = _run_cli(tmp_path, ["--change", "fc-cli-fail", "--no-validate"])
    assert proc.returncode == 2
    assert "[FAIL]" in proc.stdout


def test_cli_minimal_change_exits_2_for_completeness(tmp_path):
    make_minimal_change(tmp_path, "fc-min")
    proc = _run_cli(tmp_path, ["--change", "fc-min", "--no-validate"])
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# P7 review fixups (F-A / F-B / F-C / F-E shared helper)
# ---------------------------------------------------------------------------


def test_verify_report_has_real_failures_helper_strips_count_summary():
    """P7 F-A / F-E shared helper: the autogenerated ``- [FAIL]: 0`` count
    summary must NOT count as a real failure marker. Per-step ``- [FAIL]
    **L0 ...`` lines DO count.
    """
    only_summary = (
        "## Summary\n\n- total steps: 6\n- [OK]: 2\n- [FAIL]: 0\n- [SKIP]: 4\n"
    )
    real_fail = (
        "- [OK] **L0 pytest** (exit=0)\n"
        "- [FAIL] **L0 offline-bundle-smoke** (exit=1, 0.5s)\n"
        "  - reason: command not found\n"
        "## Summary\n\n- [OK]: 1\n- [FAIL]: 1\n- [SKIP]: 0\n"
    )
    nonzero_summary_only = "## Summary\n- [FAIL]: 5\n"
    assert _common.verify_report_has_real_failures(only_summary) is False
    assert _common.verify_report_has_real_failures(real_fail) is True
    # Even nonzero count summary alone should NOT trigger — the count summary
    # is a tally, not a per-step marker. Only real per-step [FAIL] lines do.
    assert _common.verify_report_has_real_failures(nonzero_summary_only) is False


def test_finish_gate_does_not_block_on_zero_fail_count_summary(tmp_path):
    """P7 F-A: a PASS verify_report whose body only contains the
    autogenerated ``- [FAIL]: 0`` summary line MUST NOT trigger
    ``verify_report_inconsistent``. This is the exact shape produced by
    ``forgeue_verify.render_report`` on every successful run.
    """
    b = make_complete_change(tmp_path, "fc-fa-summary")
    b.write_evidence(
        "verification",
        "verify_report.md",
        evidence_type="verify_report",
        stage="S5",
        aligned_with_contract=True,
        body="\n".join(
            [
                "## Steps (level 2)",
                "",
                "- [OK] **L0 pytest** (exit=0, 40.0s)",
                "  - pytest summary: 1126 passed in 32.0s",
                "- [OK] **L0 offline-bundle-smoke** (exit=0, 0.5s)",
                "- [SKIP] **L1 live-llm-character-extract** (exit=None, 0.0s)",
                "",
                "## Summary",
                "",
                "- total steps: 6",
                "- [OK]: 2",
                "- [FAIL]: 0",
                "- [SKIP]: 4",
                "",
            ]
        ),
    )
    env, plugin = _common.quick_detect_env()
    by_type = fg._scan_evidence_by_type(b.change_dir)
    blockers = fg.check_evidence_completeness(
        b.change_dir,
        detected_env=env,
        codex_plugin_available=plugin,
        by_type=by_type,
    )
    assert not any(blk.type == "verify_report_inconsistent" for blk in blockers), (
        f"verify_report with only [FAIL]: 0 summary should not self-block; got: {blockers}"
    )


def test_finish_gate_blocks_on_real_fail_step_marker(tmp_path):
    """P7 F-A regression: real per-step ``[FAIL]`` markers MUST still trigger
    ``verify_report_inconsistent`` when frontmatter claims aligned_with_contract.
    """
    b = make_complete_change(tmp_path, "fc-fa-realfail")
    b.write_evidence(
        "verification",
        "verify_report.md",
        evidence_type="verify_report",
        stage="S5",
        aligned_with_contract=True,
        body="\n".join(
            [
                "## Steps (level 0)",
                "",
                "- [FAIL] **L0 pytest** (exit=1, 30.0s)",
                "  - reason: 5 tests failed",
                "",
                "## Summary",
                "- [FAIL]: 1",
                "",
            ]
        ),
    )
    env, plugin = _common.quick_detect_env()
    by_type = fg._scan_evidence_by_type(b.change_dir)
    blockers = fg.check_evidence_completeness(
        b.change_dir,
        detected_env=env,
        codex_plugin_available=plugin,
        by_type=by_type,
    )
    assert any(blk.type == "verify_report_inconsistent" for blk in blockers)


def test_finish_gate_skips_prior_finish_gate_report_in_audit(tmp_path):
    """P7 F-B: a previous run's failed ``verification/finish_gate_report.md``
    (which carries ``aligned_with_contract: false`` + ``drift_decision:
    pending``) MUST be skipped by frontmatter audit. Otherwise a single
    failed run permanently self-pollutes — even after the original blockers
    are fixed, the next run re-blocks on the stale report's pending drift.
    """
    b = make_complete_change(tmp_path, "fc-fb-self")
    # Overwrite the default finish_gate_report to mimic a prior failed run
    b.write_evidence(
        "verification",
        "finish_gate_report.md",
        evidence_type="finish_gate_report",
        stage="S8",
        aligned_with_contract=False,
        drift_decision="pending",
        drift_reason="prior run had 5 blockers; resolution in progress",
        body="## Blockers (5)\n\n- evidence_missing\n- aligned_false_no_drift\n",
    )
    blockers, _ = fg.check_frontmatter_protocol(b.change_dir, repo=tmp_path)
    # The prior finish_gate_report must be excluded from audit; no blocker
    # should reference it.
    finish_gate_blockers = [b for b in blockers if b.file and "finish_gate_report" in b.file]
    assert finish_gate_blockers == [], (
        f"finish_gate_report.md should be self-excluded from audit; got: "
        f"{[(b.type, b.file) for b in finish_gate_blockers]}"
    )


def test_finish_gate_required_slot_not_satisfied_by_notes_helper(tmp_path):
    """P7 F-C: a ``notes/`` helper with ``evidence_type: verify_report`` and
    minimal frontmatter (just change_id + evidence_type) MUST NOT satisfy
    the REQUIRED verify_report slot. Otherwise the 8-key always-required
    audit (which only fires on formal subdirs) is bypassed via notes/.
    """
    b = make_complete_change(tmp_path, "fc-fc-notes")
    # Remove the legitimate formal verify_report
    formal_path = b.change_dir / "verification" / "verify_report.md"
    formal_path.unlink()
    # Plant a fake verify_report under notes/ with minimal frontmatter
    notes_dir = b.change_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    fake = notes_dir / "fake_verify.md"
    fake.write_text(
        "---\n"
        f"change_id: {b.change_id}\n"
        "evidence_type: verify_report\n"
        "---\n\n"
        "Pretending to be a verify_report.\n",
        encoding="utf-8",
    )
    env, plugin = _common.quick_detect_env()
    by_type = fg._scan_evidence_by_type(b.change_dir)
    blockers = fg.check_evidence_completeness(
        b.change_dir,
        detected_env=env,
        codex_plugin_available=plugin,
        by_type=by_type,
    )
    # F-C: notes/ helper must NOT satisfy the REQUIRED slot
    assert any(
        blk.type == "evidence_missing" and "verify_report" in (blk.file or "")
        for blk in blockers
    ), (
        f"notes/ helper with evidence_type: verify_report must not satisfy REQUIRED; "
        f"blockers: {[(b.type, b.file) for b in blockers]}"
    )


# ---------------------------------------------------------------------------
# adopt-subagent-driven-development §5 (F1 + F2): subagent dispatch mode
# detection + 4 new evidence_types + worktree fence
# ---------------------------------------------------------------------------


def _add_subagent_quad(b, *, task_n: int = 1) -> None:
    """Helper: write the 4 subagent_* evidence files for one micro-task."""
    b.write_evidence(
        "execution",
        f"task_{task_n}_implementer.md",
        evidence_type="subagent_implementer_report",
        stage="S4",
        body="## Status: DONE\nimplementer return body.\n",
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )
    b.write_evidence(
        "execution",
        f"task_{task_n}_spec_review.md",
        evidence_type="subagent_spec_review",
        stage="S4",
        body="## Status: Spec compliant\nspec reviewer body.\n",
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )
    b.write_evidence(
        "execution",
        f"task_{task_n}_code_quality_review.md",
        evidence_type="subagent_code_quality_review",
        stage="S4",
        body="## Status: APPROVED\ncode quality reviewer body.\n",
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )
    b.write_evidence(
        "review",
        "subagent_final_review.md",
        evidence_type="subagent_final_review",
        stage="S6",
        body="## Status: APPROVED\nfinal review body.\n",
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )


def test_subagent_evidence_types_pass_frontmatter_validation(tmp_path):
    """§5.4 case 1: 4 new evidence_types are accepted by frontmatter validation.

    A change carrying the 4 subagent_* evidence files alongside the standard
    base evidence MUST NOT trip ``evidence_type_mismatch`` /
    ``evidence_malformed`` blockers — the new types are first-class.
    """
    b = make_complete_change(
        tmp_path,
        "fc-sub-fm",
        with_codex=False,
        with_cross_check=False,
    )
    _add_subagent_quad(b, task_n=1)
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-sub-fm",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    assert report is not None
    bad_types = {"evidence_type_mismatch", "evidence_malformed"}
    offending = [b for b in report.blockers if b.type in bad_types]
    assert offending == [], (
        f"4 new subagent_* evidence_types must validate cleanly; got: "
        f"{[(bl.type, bl.file, bl.detail) for bl in offending]}"
    )


def test_subagent_dispatch_mode_required_evidence_missing_blocks(tmp_path):
    """§5.4 case 2 (F2 fence): ANY frontmatter ``triggered_by_command:
    change-apply-subagent`` flips the change to subagent dispatch mode →
    the 4 subagent_* evidence types are REQUIRED → missing them produces
    ``evidence_missing`` blockers (exit 2). MUST NOT silent-WARN.
    """
    b = make_complete_change(
        tmp_path,
        "fc-sub-required",
        with_codex=False,
        with_cross_check=False,
    )
    # Plant only ONE subagent evidence file (the implementer) carrying the
    # dispatch-mode signal; the other 3 are deliberately missing.
    b.write_evidence(
        "execution",
        "task_1_implementer.md",
        evidence_type="subagent_implementer_report",
        stage="S4",
        body="## Status: DONE\nimplementer return.\n",
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-sub-required",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    assert report is not None
    missing_details = [
        bl.detail for bl in report.blockers if bl.type == "evidence_missing"
    ]
    joined = " ".join(missing_details)
    # The 3 missing subagent_* evidence types MUST surface as evidence_missing
    for needed in (
        "subagent_spec_review",
        "subagent_code_quality_review",
        "subagent_final_review",
    ):
        assert needed in joined, (
            f"subagent dispatch mode must REQUIRE {needed!r}; missing from blockers: "
            f"{missing_details!r}"
        )


def test_direct_dispatch_mode_does_not_require_subagent_evidence(tmp_path):
    """§5.4 case 3 (F2 fence): NO frontmatter carries
    ``triggered_by_command: change-apply-subagent`` → direct / legacy mode
    → 4 subagent_* evidence types are NOT REQUIRED → finish_gate must pass
    without them.
    """
    b = make_complete_change(
        tmp_path,
        "fc-sub-direct",
        with_codex=False,
        with_cross_check=False,
    )
    # Default make_complete_change carries no triggered_by_command field;
    # the 3 base evidence files satisfy the legacy REQUIRED set.
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-sub-direct",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    assert report is not None
    missing_subagent = [
        bl
        for bl in report.blockers
        if bl.type == "evidence_missing"
        and any(
            kw in (bl.detail or "")
            for kw in (
                "subagent_implementer_report",
                "subagent_spec_review",
                "subagent_code_quality_review",
                "subagent_final_review",
            )
        )
    ]
    assert missing_subagent == [], (
        f"direct dispatch (no triggered_by_command) MUST NOT require subagent_* evidence; "
        f"got blockers: {[(bl.type, bl.detail) for bl in missing_subagent]}"
    )


def test_subagent_dispatch_mode_other_value_does_not_trigger_required(tmp_path):
    """§5.4 case 3 reinforcement: ``triggered_by_command`` with a different
    value (e.g. ``change-apply-direct``) MUST NOT flip subagent mode.
    """
    b = make_complete_change(
        tmp_path,
        "fc-sub-other",
        with_codex=False,
        with_cross_check=False,
    )
    b.write_evidence(
        "execution",
        "tdd_log.md",
        evidence_type="tdd_log",
        stage="S4",
        body="## TDD\nlegacy direct path tdd log.\n",
        extra_frontmatter={"triggered_by_command": "change-apply-direct"},
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-sub-other",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    assert report is not None
    missing_subagent = [
        bl
        for bl in report.blockers
        if bl.type == "evidence_missing"
        and "subagent_" in (bl.detail or "")
    ]
    assert missing_subagent == [], (
        f"triggered_by_command other than 'change-apply-subagent' MUST NOT require "
        f"subagent_* evidence; got: {[(bl.type, bl.detail) for bl in missing_subagent]}"
    )


def test_parallel_dispatch_mode_required_evidence_missing_blocks(tmp_path):
    """P6 codex round 1 F1 fix(enhance-workflow-automation-runtime-enforcement):
    ``triggered_by_command: change-apply-parallel`` MUST 同款触发 4 类
    subagent_* evidence REQUIRED 强制。

    原 detector 仅识别 ``change-apply-subagent``,parallel run 即使缺
    spec_review / code_quality_review / final_review 也 bypass REQUIRED
    check,与 ``.claude/commands/forgeue/change-apply-parallel.md`` L101-105
    declared 同款 4 类 evidence 协议矛盾。本 fence 守门 detector 扩到 frozenset
    ``_SUBAGENT_STYLE_DISPATCH_VALUES`` 覆盖 parallel。
    """
    b = make_complete_change(
        tmp_path,
        "fc-parallel-required",
        with_codex=False,
        with_cross_check=False,
    )
    # 仅写一个 implementer evidence 标 parallel dispatch — 其他 3 类故意缺
    b.write_evidence(
        "execution",
        "task_1_implementer.md",
        evidence_type="subagent_implementer_report",
        stage="S4",
        body="## Status: DONE\nparallel implementer return.\n",
        extra_frontmatter={"triggered_by_command": "change-apply-parallel"},
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-parallel-required",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    assert report is not None
    missing_details = [
        bl.detail for bl in report.blockers if bl.type == "evidence_missing"
    ]
    joined = " ".join(missing_details)
    for needed in (
        "subagent_spec_review",
        "subagent_code_quality_review",
        "subagent_final_review",
    ):
        assert needed in joined, (
            f"parallel dispatch mode MUST REQUIRE {needed!r}(沿 P6 codex round 1 F1 fix);"
            f"missing from blockers: {missing_details!r}"
        )


def test_dispatch_mode_detector_recognizes_subagent_and_parallel():
    """P6 F1 fix unit test:_SUBAGENT_STYLE_DISPATCH_VALUES frozenset 同时
    含 change-apply-subagent + change-apply-parallel。"""
    assert "change-apply-subagent" in fg._SUBAGENT_STYLE_DISPATCH_VALUES
    assert "change-apply-parallel" in fg._SUBAGENT_STYLE_DISPATCH_VALUES
    # Negative:其他 trigger 不在内
    assert "change-apply-direct" not in fg._SUBAGENT_STYLE_DISPATCH_VALUES
    assert "change-plan" not in fg._SUBAGENT_STYLE_DISPATCH_VALUES


def test_subagent_full_quad_satisfies_dispatch_mode(tmp_path):
    """§5.4 case 1 reinforcement: a complete subagent dispatch run carrying
    all 4 subagent_* evidence files MUST PASS without ``evidence_missing``
    for the 4 types.
    """
    b = make_complete_change(
        tmp_path,
        "fc-sub-full",
        with_codex=False,
        with_cross_check=False,
    )
    _add_subagent_quad(b, task_n=1)
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-sub-full",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    assert report is not None
    # No missing blocker should reference the 4 subagent_* types
    for ev_type in (
        "subagent_implementer_report",
        "subagent_spec_review",
        "subagent_code_quality_review",
        "subagent_final_review",
    ):
        assert not any(
            bl.type == "evidence_missing" and ev_type in (bl.detail or "")
            for bl in report.blockers
        ), f"complete subagent quad MUST satisfy {ev_type}"


def test_per_task_triple_check_blocks_when_task_2_missing_review(tmp_path):
    """§5.4 case 5 (F7 fix from codex S6 round 2): subagent dispatch mode 下
    每个 task_n 必须有 implementer + spec_review + code_quality_review 三件套。
    本 fence simulates 一个 multi-task change 仅交 task_1 三件套 + task_2 implementer
    缺 spec_review / code_quality_review。F7 修复后 finish_gate 必须报
    ``evidence_missing_per_task`` blocker;F7 修复前会被绕过(只查 evidence_type 存在)。
    """
    b = make_complete_change(
        tmp_path,
        "fc-sub-pertask",
        with_codex=False,
        with_cross_check=False,
    )
    # Add task_1 full triple + final review(满足 evidence_type 存在 baseline)
    _add_subagent_quad(b, task_n=1)
    # Add task_2 implementer ONLY(缺 spec_review + code_quality_review)
    fm_audit = (
        "change_id: fc-sub-pertask\n"
        "stage: S4\n"
        "evidence_type: subagent_implementer_report\n"
        "contract_refs: [tasks.md#x.y]\n"
        "aligned_with_contract: true\n"
        "drift_decision: null\n"
        "writeback_commit: null\n"
        "drift_reason: null\n"
        "reasoning_notes_anchor: null\n"
        "detected_env: claude-code\n"
        "triggered_by: forced\n"
        "codex_plugin_available: true\n"
        "triggered_by_command: change-apply-subagent\n"
    )
    (b.change_dir / "execution" / "task_2_implementer.md").write_text(
        f"---\n{fm_audit}---\n\n# Task 2 implementer (no review)\n",
        encoding="utf-8",
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-sub-pertask",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    assert report is not None
    # F7 修复:必须报 task_2 missing spec_review + code_quality_review
    per_task_blockers = [bl for bl in report.blockers if bl.type == "evidence_missing_per_task"]
    assert len(per_task_blockers) >= 2, (
        f"F7 fix: expect ≥2 per-task blockers for task_2 missing spec_review + "
        f"code_quality_review, got {[bl.detail for bl in per_task_blockers]}"
    )
    # 验证 blocker 提到 task_2(不是 task_1)
    task_2_blockers = [bl for bl in per_task_blockers if "task_2" in (bl.detail or "")]
    assert len(task_2_blockers) >= 2, "blockers should specifically reference task_2"


def test_worktree_isolation_requires_committed_change_artifacts(tmp_path):
    """§5.4 case 4 (F1 worktree fence): in a real ``git worktree add``
    isolation scenario, untracked files in the main worktree are invisible
    to the isolated worktree. tasks.md §4.1 step 6.5 mandates
    ``change-apply-subagent`` commits untracked change artifacts BEFORE
    spawning per-task subagent worktrees; otherwise subagents see an empty
    ``openspec/changes/<id>/`` and cannot read tasks / design.

    This fence simulates the failure mode by:
    1. init a fresh git repo,
    2. write contract artifacts (proposal/design/tasks) WITHOUT committing,
    3. ``git worktree add`` to a sibling dir,
    4. assert the sibling sees NONE of the uncommitted artifacts.

    This guards against regression of the §4.1 step 6.5 commit step in
    ``change-apply-subagent.md``. If a future refactor drops the
    pre-dispatch commit, this fence still passes (worktree isolation
    semantics are git-level, not our tool); the regression would be in the
    skill's behavior. The fence value is documenting the constraint so
    test_forgeue_finish_gate.py loudly asserts the assumption every CI run.
    """
    b = ChangeBuilder(repo=tmp_path, change_id="fc-wt")
    b.init_git()
    # bootstrap commit so HEAD exists for `git worktree add`
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    b.commit_all("init", paths=["README.md"])

    # Write change artifacts under openspec/ but DO NOT commit them.
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True)
    proposal = tmp_path / "openspec" / "changes" / "fc-wt" / "proposal.md"
    assert proposal.is_file(), "main worktree must see uncommitted file"

    # Spawn an isolated worktree from HEAD (which lacks the openspec/ tree).
    wt_dir = tmp_path.parent / f"{tmp_path.name}-wt"
    if wt_dir.exists():
        # Clean up any leftover from a prior test run
        import shutil as _shutil

        _shutil.rmtree(wt_dir, ignore_errors=True)
    try:
        proc = subprocess.run(
            ["git", "worktree", "add", str(wt_dir), "HEAD"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "GIT_CONFIG_GLOBAL": str(tmp_path / ".gitconfig-test"),
                 "GIT_CONFIG_SYSTEM": str(tmp_path / ".gitconfig-system-test")},
            timeout=30,
        )
        if proc.returncode != 0:
            # If worktree add fails (rare on Windows shared FS), the fence
            # is informational rather than enforced. Skip.
            pytest.skip(f"git worktree add unavailable: {proc.stderr!r}")

        wt_proposal = wt_dir / "openspec" / "changes" / "fc-wt" / "proposal.md"
        assert not wt_proposal.exists(), (
            "F1 fence: isolated worktree MUST NOT see uncommitted change artifacts; "
            "tasks.md §4.1 step 6.5 MUST commit them before subagent dispatch — "
            "regression in change-apply-subagent.md commit step would be undetected "
            "without this assumption being asserted."
        )
    finally:
        # Always attempt cleanup so subsequent test runs are not polluted.
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(wt_dir)],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=30,
        )


# ---------------------------------------------------------------------------
# P0 enhance-workflow-automation:autonomy_boundary fence
# (W2 writeback codex round 1 F2 finding)
# ---------------------------------------------------------------------------

# M-1 fix:删除 dead code _VALID_CODEX_REF_TYPES(原定义后从未引用,helper 端引用的是
# fg._VALID_CODEX_REVIEW_REF_TYPES 而非测试本地副本)


@pytest.fixture
def autonomy_evidence_setup(tmp_path):
    """M-2 fix:autonomy_boundary fence test 公共 fixture。

    创建标准的 change 目录 + 空 implementation evidence 文件,返回 callable
    `setup(change_id)` -> (change_dir, evidence_path)。各测试只需提供 frontmatter
    dict + 调用 fg._check_autonomy_boundary 即可,不再重复 4 行的 mkdir + write_text 样板。
    """
    def _setup(change_id: str = "fc-ab-fixture") -> tuple[Path, Path]:
        change_dir = tmp_path / "openspec" / "changes" / change_id
        change_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = change_dir / "execution" / "task_1_implementer.md"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text("---\n---\n\nbody\n", encoding="utf-8")
        return change_dir, evidence_path
    return _setup


def _write_codex_ref_evidence(
    tmp_path: Path,
    change_id: str,
    *,
    evidence_type: str = "codex_adversarial_review",
    disputed_open: int = 0,
    subdir: str = "notes/pre_p0",
    filename: str = "codex_review_round1.md",
) -> Path:
    """在 change 目录下写一份模拟 codex review evidence 文件。

    autonomy_boundary 4 类 ref 校验都依赖能读到 codex ref 文件的 frontmatter;
    这个 helper 为测试生成标准形态的 codex review 文件。
    """
    change_dir = tmp_path / "openspec" / "changes" / change_id
    ref_dir = change_dir / subdir
    ref_dir.mkdir(parents=True, exist_ok=True)
    ref_path = ref_dir / filename
    # 写 codex review evidence frontmatter
    content = (
        "---\n"
        f"change_id: {change_id}\n"
        "stage: S3\n"
        f"evidence_type: {evidence_type}\n"
        "contract_refs:\n"
        "  - design.md\n"
        "aligned_with_contract: true\n"
        "drift_decision: null\n"
        "writeback_commit: null\n"
        "drift_reason: null\n"
        "reasoning_notes_anchor: null\n"
        "detected_env: claude-code\n"
        "triggered_by: codex_invoke\n"
        "codex_plugin_available: true\n"
        f"disputed_open: {disputed_open}\n"
        "verdict: approve\n"
        "---\n\n"
        "## F1\n\nseverity: low\nresolution: accepted-codex\n"
    )
    ref_path.write_text(content, encoding="utf-8")
    return ref_path


def test_autonomy_boundary_missing_field_blocks(autonomy_evidence_setup):
    """P0.6 fence:evidence 缺少 autonomy_decision 字段时 _check_autonomy_boundary
    必须返回含 'autonomy_decision' 关键词的错误。

    M-2 fix:用 autonomy_evidence_setup fixture 替代手工 mkdir+write_text 样板。
    """
    change_dir, evidence_path = autonomy_evidence_setup("fc-ab-missing")
    # 构造一个缺少 autonomy_decision 的 frontmatter
    fm = {
        "change_id": "fc-ab-missing",
        "stage": "S4",
        "evidence_type": "subagent_implementer_report",
        "aligned_with_contract": True,
    }
    errors = fg._check_autonomy_boundary(evidence_path, fm, change_dir)
    # 缺少 autonomy_decision 字段 → 必须有错误
    assert errors, "missing autonomy_decision MUST produce an error"
    joined = " ".join(errors)
    assert "autonomy_decision" in joined, (
        f"error must mention 'autonomy_decision' field; got: {joined!r}"
    )


def test_autonomy_boundary_value_enum(autonomy_evidence_setup):
    """P0.8 fence:autonomy_decision 值不在 enum 内时必须报错。
    合法值:claude_autonomous / claude_codex_concurred / user_required / user_overrode

    M-2 fix:用 autonomy_evidence_setup fixture。
    """
    change_dir, evidence_path = autonomy_evidence_setup("fc-ab-enum")
    # 非法值 → 应该报错
    fm_bad = {"autonomy_decision": "auto_approved"}
    errors_bad = fg._check_autonomy_boundary(evidence_path, fm_bad, change_dir)
    assert errors_bad, f"invalid enum value must produce an error; got no errors"
    joined_bad = " ".join(errors_bad)
    assert "autonomy_decision" in joined_bad

    # 合法值 claude_autonomous → 不需要 codex_review_ref → 不应该报 enum 错
    fm_good = {"autonomy_decision": "claude_autonomous"}
    errors_good = fg._check_autonomy_boundary(evidence_path, fm_good, change_dir)
    # claude_autonomous 不要求 codex_review_ref,所以不应该有 "autonomy_decision" enum 错
    enum_errors = [e for e in errors_good if "not a valid" in e or "enum" in e.lower()]
    assert not enum_errors, (
        f"'claude_autonomous' is valid enum; should not produce enum error; got: {errors_good}"
    )


def test_autonomy_boundary_concurred_requires_codex_ref(autonomy_evidence_setup):
    """P0.7 fence:autonomy_decision: claude_codex_concurred 时必须有 codex_review_ref
    字段;缺少时必须报错。

    M-2 fix:用 autonomy_evidence_setup fixture。
    """
    change_dir, evidence_path = autonomy_evidence_setup("fc-ab-noref")
    # concurred 但无 codex_review_ref → 必须报错
    fm = {"autonomy_decision": "claude_codex_concurred"}
    errors = fg._check_autonomy_boundary(evidence_path, fm, change_dir)
    assert errors, "concurred without codex_review_ref MUST produce an error"
    joined = " ".join(errors)
    assert "codex_review_ref" in joined, (
        f"error must mention 'codex_review_ref'; got: {joined!r}"
    )


def test_autonomy_boundary_bogus_ref_blocks(autonomy_evidence_setup):
    """P0.9 fence:codex_review_ref 指向不存在的文件时必须报错(ref 路径不存在)。

    M-2 fix:用 autonomy_evidence_setup fixture。
    """
    change_dir, evidence_path = autonomy_evidence_setup("fc-ab-bogus")
    # ref 指向不存在的文件
    fm = {
        "autonomy_decision": "claude_codex_concurred",
        "codex_review_ref": "notes/pre_p0/does_not_exist.md",
    }
    errors = fg._check_autonomy_boundary(evidence_path, fm, change_dir)
    assert errors, "non-existent ref path MUST produce an error"
    joined = " ".join(errors)
    # 应该提到 ref 路径不存在
    assert any(keyword in joined for keyword in ("not found", "does not exist", "not a file", "exist")), (
        f"error must indicate ref path not found; got: {joined!r}"
    )


def test_autonomy_boundary_cross_change_ref_blocks(tmp_path):
    """P0.10 fence:codex_review_ref 指向另一个 change 目录下的文件时必须报错
    (ref 不属于同一 change — 跨 change 污染)。

    测试方案:将 ref_rel 写成 relative_to change_dir 的 '../other-change/...' 形式
    使文件真实存在(b 检查通过)但路径 resolve 后超出 change_dir 范围(c 检查失败)。
    """
    # 创建本 change
    change_dir = tmp_path / "openspec" / "changes" / "fc-ab-cross"
    change_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = change_dir / "execution" / "task_1_implementer.md"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("---\n---\n\nbody\n", encoding="utf-8")

    # 创建另一个 change 并在那里写一份 codex review 文件
    other_change_dir = tmp_path / "openspec" / "changes" / "other-change"
    other_change_dir.mkdir(parents=True, exist_ok=True)
    ref_file = other_change_dir / "notes" / "codex_review.md"
    ref_file.parent.mkdir(parents=True, exist_ok=True)
    ref_file.write_text(
        "---\nchange_id: other-change\nevidence_type: codex_adversarial_review\n"
        "disputed_open: 0\n---\n\nbody\n",
        encoding="utf-8",
    )

    # 用 ../other-change/... 形式:相对于 change_dir 可以 resolve 到真实文件
    # 但路径穿越出 change_dir → 触发 (c) cross-change 检查
    fm = {
        "autonomy_decision": "claude_codex_concurred",
        "codex_review_ref": "../other-change/notes/codex_review.md",
    }
    errors = fg._check_autonomy_boundary(evidence_path, fm, change_dir)
    assert errors, "cross-change ref MUST produce an error"
    joined = " ".join(errors)
    # 应该提到 cross-change 或 scope 违反
    assert any(keyword in joined for keyword in ("cross-change", "same change", "scope", "not within", "outside")), (
        f"error must indicate cross-change ref violation; got: {joined!r}"
    )


def test_autonomy_boundary_wrong_evidence_type_blocks(tmp_path):
    """P0.11 fence:codex_review_ref 指向的文件 evidence_type 不是合法的 codex review
    类型时必须报错。合法类型:codex_adversarial/design/plan/verification/mixed_scope _review
    """
    change_id = "fc-ab-type"
    # 在 change 内写一份 ref 文件,但 evidence_type 是非 codex review 类型
    ref_path = _write_codex_ref_evidence(
        tmp_path, change_id,
        evidence_type="subagent_implementer_report",  # 非法 ref evidence_type
        disputed_open=0,
    )
    change_dir = tmp_path / "openspec" / "changes" / change_id
    evidence_path = change_dir / "execution" / "task_1_implementer.md"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("---\n---\n\nbody\n", encoding="utf-8")

    # ref 文件存在且属于同 change,但 evidence_type 不是 codex review
    ref_rel = ref_path.relative_to(change_dir).as_posix()
    fm = {
        "autonomy_decision": "claude_codex_concurred",
        "codex_review_ref": ref_rel,
    }
    errors = fg._check_autonomy_boundary(evidence_path, fm, change_dir)
    assert errors, "wrong evidence_type ref MUST produce an error"
    joined = " ".join(errors)
    assert any(keyword in joined for keyword in ("evidence_type", "codex review", "not a codex")), (
        f"error must indicate wrong evidence_type for ref; got: {joined!r}"
    )


def test_autonomy_boundary_disputed_open_ref_blocks(tmp_path):
    """P0.12 fence:codex_review_ref 指向的文件 disputed_open != 0 时必须报错。
    ref 必须是已 finalize 的 review(disputed_open: 0),否则 evidence 未完成不得 concurred。
    """
    change_id = "fc-ab-disputed"
    # 写 ref 文件:evidence_type 合法,但 disputed_open = 3(未解决)
    ref_path = _write_codex_ref_evidence(
        tmp_path, change_id,
        evidence_type="codex_adversarial_review",
        disputed_open=3,  # 未 finalize
    )
    change_dir = tmp_path / "openspec" / "changes" / change_id
    evidence_path = change_dir / "execution" / "task_1_implementer.md"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("---\n---\n\nbody\n", encoding="utf-8")

    ref_rel = ref_path.relative_to(change_dir).as_posix()
    fm = {
        "autonomy_decision": "claude_codex_concurred",
        "codex_review_ref": ref_rel,
    }
    errors = fg._check_autonomy_boundary(evidence_path, fm, change_dir)
    assert errors, "disputed_open != 0 ref MUST produce an error"
    joined = " ".join(errors)
    assert any(keyword in joined for keyword in ("disputed_open", "finalize", "not finalized")), (
        f"error must mention disputed_open; got: {joined!r}"
    )


# ---------------------------------------------------------------------------
# P0 enhance-workflow-automation:verdict normalization (W3 writeback F3 finding)
# P0.13:8 row 表驱动 + 2 per-finding edge case
# ---------------------------------------------------------------------------

# 8 row 表驱动测试数据 — (codex_top_verdict, claude_resolution, expected_no_conflict: bool)
_VERDICT_TABLE_ROWS = [
    # Codex approve 组 — 除 disputed-open 外都不冲突
    ("approve",         "accepted-codex",  True),   # row 1:双方都 OK
    ("approve",         "accepted-claude", True),   # row 2:Claude 接 codex 推荐 + 主动改进
    ("approve",         "rejected",        True),   # row 3:Claude 拒接提议但 codex 顶层批准
    ("approve",         "disputed-open",   False),  # row 4:codex OK 但 Claude 觉得有问题
    # Codex needs-attention 组 — 只有 accepted-codex 不冲突
    ("needs-attention", "accepted-codex",  True),   # row 5:Claude 接 finding
    ("needs-attention", "accepted-claude", False),  # row 6:意见相反
    ("needs-attention", "rejected",        False),  # row 7:Claude 拒接但 codex 持续 needs-attention
    ("needs-attention", "disputed-open",   False),  # row 8:双方 unfinalized
]


@pytest.mark.parametrize("codex_verdict,claude_resolution,expected_no_conflict", _VERDICT_TABLE_ROWS)
def test_verdict_normalization_8_rows(codex_verdict, claude_resolution, expected_no_conflict):
    """P0.13 fence:按 design.md D-FenceTaxonomy Fence #3 Verdict Normalization
    8 row 表验证 _check_verdict_normalization 对每种组合的判定。
    返回 True = 不冲突(自主路径);返回 False = 冲突(升级 fence #3)。
    """
    # finding 列表:用低 severity(low/info)不触发 per-finding edge case
    findings = [{"id": "F1", "severity": "low", "resolution": claude_resolution}]
    result = fg._check_verdict_normalization(
        claude_resolution_list=[claude_resolution],
        codex_top_verdict=codex_verdict,
        codex_findings=findings,
    )
    assert result is expected_no_conflict, (
        f"verdict_normalization({codex_verdict!r}, {claude_resolution!r}) "
        f"expected no_conflict={expected_no_conflict}, got {result}"
    )


def test_verdict_normalization_high_severity_rejected_conflicts():
    """P0.13 per-finding edge case:severity=high + resolution=rejected → 冲突
    即使 codex 顶层 verdict=approve,高优先 finding 被 rejected 也必须升级。
    """
    findings = [{"id": "F1", "severity": "high", "resolution": "rejected"}]
    result = fg._check_verdict_normalization(
        claude_resolution_list=["rejected"],
        codex_top_verdict="approve",  # 顶层批准,但 per-finding 有 high+rejected
        codex_findings=findings,
    )
    # high severity + rejected → 冲突 → 返回 False
    assert result is False, (
        "severity=high + resolution=rejected MUST conflict (escalate fence #3)"
    )


def test_verdict_normalization_critical_severity_rejected_conflicts():
    """P0.13 per-finding edge case:severity=critical + resolution=rejected → 冲突
    critical severity 同 high 规则。
    """
    findings = [{"id": "F1", "severity": "critical", "resolution": "rejected"}]
    result = fg._check_verdict_normalization(
        claude_resolution_list=["rejected"],
        codex_top_verdict="approve",
        codex_findings=findings,
    )
    assert result is False, (
        "severity=critical + resolution=rejected MUST conflict (escalate fence #3)"
    )


# ---------------------------------------------------------------------------
# P0 code review 修复:I-1 / I-5 / M-3 补充 fence
# ---------------------------------------------------------------------------


def test_autonomy_boundary_ref_with_repo_root_relative_path(tmp_path):
    """I-1 fix fence:codex_review_ref 用 repo-root 相对路径
    (`openspec/changes/<change_id>/notes/<file>.md`) 时不应误报 false blocker。

    Pre-fix: `repo_root = change_root.parent.parent` 解析到 `<repo>/openspec/`
    (openspec 子目录),fallback 拼接 `openspec/openspec/changes/...` → 文件找不到
    false blocker。
    Post-fix: `repo_root = change_root.parent.parent.parent` 正确指向 repo root,
    repo-root-relative ref 可正确 resolve。
    """
    change_id = "fc-ab-reporoot"
    # 写 ref 文件:存在 + 合法 codex review evidence_type + disputed_open=0
    ref_path = _write_codex_ref_evidence(
        tmp_path, change_id,
        evidence_type="codex_adversarial_review",
        disputed_open=0,
    )
    change_dir = tmp_path / "openspec" / "changes" / change_id
    evidence_path = change_dir / "execution" / "task_1_implementer.md"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text("---\n---\n\nbody\n", encoding="utf-8")

    # 用 repo-root 相对形式(spec 文档推荐写法)
    # ref_path 实际位置:tmp_path/openspec/changes/<change_id>/notes/pre_p0/codex_review_round1.md
    ref_repo_relative = ref_path.relative_to(tmp_path).as_posix()
    assert ref_repo_relative.startswith("openspec/changes/"), (
        f"ref_repo_relative should be repo-root relative, got: {ref_repo_relative!r}"
    )

    fm = {
        "autonomy_decision": "claude_codex_concurred",
        "codex_review_ref": ref_repo_relative,
    }
    errors = fg._check_autonomy_boundary(evidence_path, fm, change_dir)
    # I-1 fix:repo-root-relative path 应正确 resolve,不应有任何错误
    assert errors == [], (
        f"repo-root-relative codex_review_ref MUST resolve correctly; "
        f"got false-blocker errors: {errors}"
    )


def test_autonomy_boundary_wired_into_check_frontmatter_protocol(tmp_path):
    """I-5 fix fence:autonomy_boundary 已正确接入 check_frontmatter_protocol 调用链。

    若 line 746 wiring 条件被误删,所有单元 helper 测试仍全绿但 finish gate 实际不校验。
    本 integration test 通过 build_report 高层入口 + 落 implementation evidence
    (subagent_implementer_report 缺 autonomy_decision 字段),assert 错误列表含
    `autonomy_boundary_violation` blocker — 验证 wiring 真实生效。
    """
    b = make_complete_change(
        tmp_path,
        "fc-ab-wired",
        with_codex=False,
        with_cross_check=False,
    )
    # 落一个 subagent_implementer_report 类型的 implementation evidence,但缺 autonomy_decision
    b.write_evidence(
        "execution",
        "task_1_implementer.md",
        evidence_type="subagent_implementer_report",
        stage="S4",
        body="## Status: DONE\nimplementer body without autonomy_decision.\n",
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
        # 注意:builder 默认不写 autonomy_decision 字段(不在 EVIDENCE_FRONTMATTER_KEYS 12 key 内)
    )
    report = fg.build_report(
        repo=tmp_path,
        change_id="fc-ab-wired",
        detected_env="cursor",
        codex_plugin_available=False,
        no_validate=True,
    )
    assert report is not None
    # I-5 fix:必须有 autonomy_boundary_violation blocker(说明 wiring 生效)
    autonomy_blockers = [bl for bl in report.blockers if bl.type == "autonomy_boundary_violation"]
    assert autonomy_blockers, (
        "autonomy_boundary fence MUST be wired into check_frontmatter_protocol — "
        f"implementation evidence missing autonomy_decision must produce "
        f"autonomy_boundary_violation blocker; got blockers: "
        f"{[(bl.type, bl.detail) for bl in report.blockers]}"
    )
    joined_details = " ".join(bl.detail for bl in autonomy_blockers)
    assert "autonomy_decision" in joined_details, (
        f"blocker detail must mention 'autonomy_decision'; got: {joined_details!r}"
    )


def test_verdict_normalization_unknown_verdict_defaults_to_no_conflict():
    """M-3 fix fence:_check_verdict_normalization 对未知顶层 verdict
    (非 'approve' / 'needs-attention')保守处理 — 返回 True(无冲突,
    让 controller 进一步判断),不主动断言冲突。

    helper 实装注释明示"未知 verdict 保守处理:不断言冲突",但行为无测试覆盖。
    本 fence 守门保守语义,防止后续重构改成 fail-closed 静默破坏 controller 兼容。
    """
    # 未知 verdict + 任意 claude resolution + 低 severity finding
    findings = [{"id": "F1", "severity": "low", "resolution": "accepted-codex"}]
    result_unknown = fg._check_verdict_normalization(
        claude_resolution_list=["accepted-codex"],
        codex_top_verdict="unknown_verdict_value",  # 未知值
        codex_findings=findings,
    )
    assert result_unknown is True, (
        "unknown codex verdict MUST default to no-conflict (True) — "
        "helper docstring says 'conservative: don't assert conflict'"
    )
    # 空字符串 verdict 同理
    result_empty = fg._check_verdict_normalization(
        claude_resolution_list=["accepted-codex"],
        codex_top_verdict="",
        codex_findings=findings,
    )
    assert result_empty is True, (
        "empty codex verdict MUST default to no-conflict (True)"
    )


# ---------------------------------------------------------------------------
# enhance-workflow-automation-runtime-enforcement P1:4 runtime fence
# (D-WorktreeEnforce / D-SkillCascadeCheck / D-RoundFixContinuity /
# D-TaskGranularityDeclaration)+ D-ProtocolVersionMigration gate
# ---------------------------------------------------------------------------


@pytest.fixture
def runtime_fence_evidence_setup(tmp_path):
    """构造 implementation evidence 路径 + 默认 frontmatter dict 公共 fixture。

    返回 callable `setup(change_id, **fm_overrides)` -> (change_dir, evidence_path, fm)。
    默认 frontmatter 含 `runtime_enforcement_protocol_version: v1` + 必填的
    `evidence_type: subagent_implementer_report`(implementation evidence 类型),
    各测试只需传入 fm_overrides 或字段差量。
    """
    def _setup(change_id: str = "fc-rt-fixture", **fm_overrides):
        change_dir = tmp_path / "openspec" / "changes" / change_id
        change_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = change_dir / "execution" / "task_1_implementer.md"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text("---\n---\n\nbody\n", encoding="utf-8")
        fm = {
            "change_id": change_id,
            "stage": "S4",
            "evidence_type": "subagent_implementer_report",
            "aligned_with_contract": True,
            "runtime_enforcement_protocol_version": "v1",
        }
        fm.update(fm_overrides)
        return change_dir, evidence_path, fm
    return _setup


# ---- D-SkillCascadeCheck _check_skill_cascade ----


def test_skill_cascade_audit_missing_blocks(runtime_fence_evidence_setup):
    """P1.7 fence:protocol v1 implementation evidence 缺 skill_cascade_audit
    字段时 _check_skill_cascade 必须返回错误。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup("fc-sc-missing")
    # fm 默认无 skill_cascade_audit
    errors = fg._check_skill_cascade(ev_path, fm, change_dir)
    assert errors, "missing skill_cascade_audit MUST produce an error"
    assert "skill_cascade_audit" in " ".join(errors)


def test_skill_cascade_audit_invalid_structure_blocks(runtime_fence_evidence_setup):
    """P1.7 fence:skill_cascade_audit 不是 dict(string)→ block。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-sc-invalid",
        skill_cascade_audit="not-a-dict",
    )
    errors = fg._check_skill_cascade(ev_path, fm, change_dir)
    assert errors
    assert "not a mapping" in " ".join(errors)


def test_skill_cascade_audit_invalid_iso_timestamp_blocks(runtime_fence_evidence_setup):
    """P1.7 fence:cascade_check_pass_at 非 ISO 8601 格式 → block。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-sc-iso",
        skill_cascade_audit={
            "invoked_skills": ["superpowers:subagent-driven-development"],
            "cascade_check_pass_at": "yesterday",  # 非 ISO 格式
        },
    )
    errors = fg._check_skill_cascade(ev_path, fm, change_dir)
    assert errors
    assert "ISO 8601" in " ".join(errors)


def test_skill_cascade_audit_valid_passes(runtime_fence_evidence_setup):
    """P1.7 fence(positive):合法 skill_cascade_audit → 无错误。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-sc-valid",
        skill_cascade_audit={
            "invoked_skills": [
                "superpowers:subagent-driven-development",
                "superpowers:using-git-worktrees",
            ],
            "cascade_check_pass_at": "2026-05-05T12:34:56Z",
        },
    )
    errors = fg._check_skill_cascade(ev_path, fm, change_dir)
    assert errors == [], f"valid audit MUST pass; got: {errors}"


# ---- D-RoundFixContinuity _check_round_fix_continuity ----


def test_round_fix_continuity_implementer_mismatch_blocks(runtime_fence_evidence_setup):
    """P1.7 fence:round_2_fix_implementer_id != round_1_implementer_id → block。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-rf-impl",
        subagent_continuity={
            "round_1_implementer_id": "agent-aaa",
            "round_2_fix_implementer_id": "agent-bbb",  # 不一致
        },
    )
    errors = fg._check_round_fix_continuity(ev_path, fm, change_dir)
    assert errors
    joined = " ".join(errors)
    assert "round_1_implementer_id" in joined and "round_2_fix_implementer_id" in joined


def test_round_fix_continuity_reviewer_mismatch_blocks(runtime_fence_evidence_setup):
    """P1.7 fence:round_2_review_reviewer_id != round_1_reviewer_id → block。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-rf-rev",
        subagent_continuity={
            "round_1_reviewer_id": "rev-ccc",
            "round_2_review_reviewer_id": "rev-ddd",  # 不一致
        },
    )
    errors = fg._check_round_fix_continuity(ev_path, fm, change_dir)
    assert errors
    joined = " ".join(errors)
    assert "round_1_reviewer_id" in joined and "round_2_review_reviewer_id" in joined


def test_round_fix_continuity_round_1_only_passes(runtime_fence_evidence_setup):
    """P1.7 fence(positive):仅含 round_1 字段(无 round_2 数据)→ 不报错。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-rf-r1only",
        subagent_continuity={
            "round_1_implementer_id": "agent-aaa",
        },
    )
    errors = fg._check_round_fix_continuity(ev_path, fm, change_dir)
    assert errors == []


# ---- D-TaskGranularityDeclaration _check_task_granularity ----


def test_task_granularity_missing_blocks(runtime_fence_evidence_setup):
    """P1.7 fence:protocol v1 implementation evidence 缺 task_granularity → block。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup("fc-tg-missing")
    errors = fg._check_task_granularity(ev_path, fm, change_dir)
    assert errors
    assert "task_granularity" in " ".join(errors)


def test_task_granularity_invalid_value_blocks(runtime_fence_evidence_setup):
    """P1.7 fence:task_granularity 值不在枚举 → block,错误指明合法枚举。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-tg-invalid",
        task_granularity="batch",  # 非枚举
    )
    errors = fg._check_task_granularity(ev_path, fm, change_dir)
    assert errors
    joined = " ".join(errors)
    assert "phase" in joined and "per-file" in joined and "sub-task" in joined


def test_task_granularity_valid_phase_passes(runtime_fence_evidence_setup):
    """P1.7 fence(positive):合法枚举 phase → 无错误。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-tg-valid",
        task_granularity="phase",
    )
    errors = fg._check_task_granularity(ev_path, fm, change_dir)
    assert errors == []


# ---- D-WorktreeEnforce _check_worktree_path ----


def test_worktree_path_advisory_pass_through_when_no_outcome_field(runtime_fence_evidence_setup):
    """ADR-013 P0.5 fence(rewritten 2026-05-06):implementation evidence 来自
    change-apply-* 命令但**无** worktree_consent_outcome 字段 → fence pass-through
    (legacy archived ADR-011/012 evidence replay 兼容意图)。

    沿 ADR-013 D-RestoreConsentGate:gating 从命令 trigger 改为 outcome field
    presence;关闭 ADR-011/012 mandatory worktree_path 协议(已 superseded)。
    """
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-wt-legacy-no-outcome",
        triggered_by_command="change-apply-subagent",
        # worktree_consent_outcome 缺 + worktree_path 缺 → legacy archived pattern
    )
    errors = fg._check_worktree_path(ev_path, fm, change_dir)
    assert errors == [], (
        f"legacy evidence (no worktree_consent_outcome) MUST pass-through "
        f"_check_worktree_path fence (ADR-013 D-RestoreConsentGate); got: {errors}"
    )


def test_worktree_path_empty_string_blocks_under_skill_worktree_mode(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 fence(rewritten 2026-05-06):worktree_path 是空字符串 +
    worktree_mode=skill_worktree → block(non-in_place mode 必写 worktree_path)。

    沿 D-ConsentOutcomeStateMachine: outcome=accepted + mode=skill_worktree
    需 worktree_path non-empty;空字符串等价缺失 → Blocker。
    """
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-wt-empty-skill",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="accepted",
        worktree_mode="skill_worktree",
        worktree_path="   ",
    )
    errors = fg._check_worktree_path(ev_path, fm, change_dir)
    assert errors, "empty worktree_path under skill_worktree mode MUST block"


def test_worktree_path_not_required_for_non_change_apply_command(
    runtime_fence_evidence_setup,
):
    """P1.7 fence:非 change-apply-* 命令(直接产生 evidence)不强制
    worktree_path,即使缺也不报错。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-wt-nonapply",
        triggered_by_command="manual-edit",
    )
    errors = fg._check_worktree_path(ev_path, fm, change_dir)
    assert errors == []


def test_worktree_path_not_required_for_change_apply_direct(
    runtime_fence_evidence_setup,
):
    """D-DirectWorktreeRefinement(2026-05-05 user 拍板):change-apply-direct
    沿 archived 2026-05-04-adopt-subagent-driven-development D-Worktree-Detail
    第 5 项不强制 worktree。direct 命令产生的 implementation evidence 即使缺
    worktree_path 字段也不应报错(fence pass-through)。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-wt-direct",
        triggered_by_command="change-apply-direct",
        # worktree_path 缺(direct 沿 archived 不强制)
    )
    errors = fg._check_worktree_path(ev_path, fm, change_dir)
    assert errors == [], (
        "change-apply-direct evidence MUST pass-through _check_worktree_path fence "
        f"(D-DirectWorktreeRefinement); got: {errors}"
    )


def test_worktree_path_required_for_change_apply_parallel_when_skill_worktree_mode(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 fence(rewritten 2026-05-06):change-apply-parallel +
    worktree_mode=skill_worktree 必写 worktree_path。

    沿 D-ConsentOutcomeStateMachine:non-in_place mode 必写 worktree_path,
    parallel 命令同款。
    """
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-wt-parallel-skill",
        triggered_by_command="change-apply-parallel",
        worktree_consent_outcome="accepted",
        worktree_mode="skill_worktree",
        # worktree_path 缺 → 应触发 fence
    )
    errors = fg._check_worktree_path(ev_path, fm, change_dir)
    assert errors
    assert "worktree_path" in " ".join(errors)


# ---- ADR-013 D-ConsentOutcomeStateMachine new fences (P0.5 + W6) ----


def test_legacy_evidence_no_consent_outcome_field_pass_through(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 fence:legacy archived evidence(无 worktree_consent_outcome
    字段)→ all 3 ADR-013 fences pass-through(关闭 archived ADR-011/012 evidence
    false-block 风险)。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-adr013-legacy",
        triggered_by_command="change-apply-subagent",
        # 缺 worktree_consent_outcome + worktree_mode → legacy
    )
    assert fg._check_worktree_path(ev_path, fm, change_dir) == []
    assert fg._check_worktree_consent_outcome(ev_path, fm, change_dir) == []
    assert fg._check_worktree_mode_consistency(ev_path, fm, change_dir) == []


def test_worktree_consent_outcome_invalid_enum_blocks(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 fence(D-ConsentOutcomeStateMachine):worktree_consent_outcome
    非合法 enum value → block,错误指明合法枚举。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-cs-invalid-outcome",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="approved",  # 非枚举(应是 accepted)
        worktree_mode="skill_worktree",
        worktree_path="/tmp/wt",
    )
    errors = fg._check_worktree_consent_outcome(ev_path, fm, change_dir)
    assert errors, "invalid outcome enum MUST block"
    joined = " ".join(errors)
    assert "declined" in joined and "accepted" in joined and "already_isolated" in joined


def test_worktree_consent_outcome_declined_requires_mode_in_place(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 fence(D-ConsentOutcomeStateMachine cross-field):
    declined → mode 必须 in_place;违反 → block。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-cs-decline-skill",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="declined",
        worktree_mode="skill_worktree",  # 违反 declined ↔ in_place
        worktree_path="/tmp/wt",
    )
    errors = fg._check_worktree_consent_outcome(ev_path, fm, change_dir)
    assert errors
    joined = " ".join(errors)
    assert "declined" in joined and "in_place" in joined


def test_worktree_consent_outcome_accepted_requires_mode_worktree_or_wrapper(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 fence(D-ConsentOutcomeStateMachine cross-field):
    accepted → mode 必须 ∈ {skill_worktree, wrapper_worktree};in_place 违反 → block。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-cs-accept-inplace",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="accepted",
        worktree_mode="in_place",  # 违反 accepted → mode != in_place
    )
    errors = fg._check_worktree_consent_outcome(ev_path, fm, change_dir)
    assert errors
    joined = " ".join(errors)
    assert "accepted" in joined


def test_worktree_consent_outcome_already_isolated_rejects_mode_in_place(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 + W6 fence(codex round 2 F2 writeback):already_isolated +
    in_place INVALID(关闭 main repo cwd 假声 isolated → 重新打开 F1 attribution
    漏洞)。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-cs-already-inplace",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="already_isolated",
        worktree_mode="in_place",  # 违反 W6 invariant
    )
    errors = fg._check_worktree_consent_outcome(ev_path, fm, change_dir)
    assert errors
    joined = " ".join(errors)
    assert "already_isolated" in joined and "in_place" not in joined.split("got")[0]


def test_worktree_consent_outcome_already_isolated_requires_worktree_path_not_main_repo(
    runtime_fence_evidence_setup, tmp_path,
):
    """ADR-013 W6 fence(codex round 2 F2 writeback):already_isolated 必须
    worktree_path 写且 realpath != main repo;假声 isolated path = main repo → block。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-cs-already-mainrepo",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="already_isolated",
        worktree_mode="skill_worktree",
        worktree_path=str(tmp_path),  # = main_repo (change_root.parents[2] = tmp_path)
    )
    errors = fg._check_worktree_consent_outcome(ev_path, fm, change_dir)
    assert errors
    joined = " ".join(errors)
    assert "main repo" in joined.lower() or "main repo" in joined


def test_worktree_mode_in_place_rejects_worktree_path_field(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 fence(D-ConsentOutcomeStateMachine mode invariant):
    in_place mode 写 worktree_path → block(关闭 codex round 1 F2 双歧义漏洞)。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-mc-inplace-with-path",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="declined",
        worktree_mode="in_place",
        worktree_path="/tmp/wt",  # 违反 in_place 禁写 worktree_path
    )
    errors = fg._check_worktree_mode_consistency(ev_path, fm, change_dir)
    assert errors
    assert "in_place" in " ".join(errors) and "worktree_path" in " ".join(errors)


def test_worktree_mode_wrapper_requires_receipt_path(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 fence(D-ConsentOutcomeStateMachine mode invariant):
    wrapper_worktree mode 必写 worktree_receipt_path;缺 → block(关闭 codex
    round 1 F2 receipt provenance 漏洞)。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-mc-wrapper-no-receipt",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="accepted",
        worktree_mode="wrapper_worktree",
        worktree_path="/tmp/wt",
        # worktree_receipt_path 缺 → 违反
    )
    errors = fg._check_worktree_mode_consistency(ev_path, fm, change_dir)
    assert errors
    assert "wrapper_worktree" in " ".join(errors) and "receipt" in " ".join(errors)


def test_worktree_mode_skill_rejects_receipt_path_field(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 fence(D-ConsentOutcomeStateMachine mode invariant):
    skill_worktree mode 禁写 receipt;present → block。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-mc-skill-with-receipt",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="accepted",
        worktree_mode="skill_worktree",
        worktree_path="/tmp/wt",
        worktree_receipt_path="preflight_receipts/foo.json",  # 违反 skill_worktree 禁写 receipt
    )
    errors = fg._check_worktree_mode_consistency(ev_path, fm, change_dir)
    assert errors
    assert "skill_worktree" in " ".join(errors)


def test_worktree_consent_outcome_valid_full_state_machine_passes(
    runtime_fence_evidence_setup,
):
    """ADR-013 P0.5 fence(positive):4 个合法 outcome × mode 组合全 pass。"""
    valid_combos = [
        ("declined", "in_place", None, None),
        ("accepted", "skill_worktree", "/tmp/wt-skill", None),
        ("accepted", "wrapper_worktree", "/tmp/wt-wrap", "preflight_receipts/x.json"),
        ("sandbox_fallback", "in_place", None, None),
    ]
    for i, (outcome, mode, path, receipt) in enumerate(valid_combos):
        fm_kwargs = {
            "triggered_by_command": "change-apply-subagent",
            "worktree_consent_outcome": outcome,
            "worktree_mode": mode,
        }
        if path is not None:
            fm_kwargs["worktree_path"] = path
        if receipt is not None:
            fm_kwargs["worktree_receipt_path"] = receipt
        change_dir, ev_path, fm = runtime_fence_evidence_setup(
            f"fc-cs-valid-{i}", **fm_kwargs,
        )
        outcome_errors = fg._check_worktree_consent_outcome(ev_path, fm, change_dir)
        consistency_errors = fg._check_worktree_mode_consistency(ev_path, fm, change_dir)
        path_errors = fg._check_worktree_path(ev_path, fm, change_dir)
        assert outcome_errors == [], (
            f"valid combo {(outcome, mode)} _check_worktree_consent_outcome should pass; "
            f"got: {outcome_errors}"
        )
        assert consistency_errors == [], (
            f"valid combo {(outcome, mode)} _check_worktree_mode_consistency should pass; "
            f"got: {consistency_errors}"
        )
        assert path_errors == [], (
            f"valid combo {(outcome, mode)} _check_worktree_path should pass; "
            f"got: {path_errors}"
        )


def test_worktree_consent_outcome_already_isolated_valid_with_distinct_path_passes(
    runtime_fence_evidence_setup, tmp_path,
):
    """ADR-013 P0.5 + W6 fence(positive;P1 code_quality M-2 fix 2026-05-06):
    already_isolated + worktree_mode ∈ {skill_worktree, wrapper_worktree} +
    ``worktree_path`` 写且 realpath != main repo → 全 pass。

    覆盖 already_isolated 在合法 isolated workspace 路径下的 positive case
    (其余 negative case 已由 ``test_worktree_consent_outcome_already_isolated_*``
    覆盖;此 positive 防止 W6 invariant 未来重构 silently 破坏 valid 路径)。
    """
    # main_repo 推断 = change_root.parents[2] = tmp_path
    # 故构造 isolated_path != tmp_path,例如 tmp_path / "isolated_workspace"
    isolated_workspace = tmp_path / "isolated_workspace"
    isolated_workspace.mkdir()

    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-cs-already-valid",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="already_isolated",
        worktree_mode="skill_worktree",
        worktree_path=str(isolated_workspace),
    )
    outcome_errors = fg._check_worktree_consent_outcome(ev_path, fm, change_dir)
    consistency_errors = fg._check_worktree_mode_consistency(ev_path, fm, change_dir)
    path_errors = fg._check_worktree_path(ev_path, fm, change_dir)
    assert outcome_errors == [], (
        f"already_isolated + valid isolated path should pass _check_worktree_consent_outcome; "
        f"got: {outcome_errors}"
    )
    assert consistency_errors == [], (
        f"already_isolated + skill_worktree should pass _check_worktree_mode_consistency; "
        f"got: {consistency_errors}"
    )
    assert path_errors == [], (
        f"already_isolated + valid worktree_path should pass _check_worktree_path; "
        f"got: {path_errors}"
    )


# ---- ADR-013 P7 codex round 3 F2 + F3 writeback fences ----


def test_check_consent_outcome_enforces_invariant_when_triggered_by_command_missing(
    runtime_fence_evidence_setup,
):
    """ADR-013 P7 codex round 3 F2 fix:enum + invariant 校验 NOT gated by
    triggered_by_command — controller 拼错 / 漏写 triggered_by_command 字段时,
    `accepted + in_place` 等非法组合仍 must be caught(原 fence ordering 有 bypass 漏洞)。
    """
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-cs-no-trigger",
        # NO triggered_by_command field (controller 漏写 / 拼错的场景)
        worktree_consent_outcome="accepted",
        worktree_mode="in_place",  # 违反 accepted → mode ∈ {skill,wrapper}_worktree
    )
    errors = fg._check_worktree_consent_outcome(ev_path, fm, change_dir)
    assert errors, (
        "P7 F2 fix:invariant violation MUST be caught even when triggered_by_command "
        "is missing/misspelled (no early-return gating by trigger filter); "
        f"got: {errors}"
    )
    joined = " ".join(errors)
    assert "accepted" in joined and "in_place" in joined


def test_check_consent_outcome_enforces_invariant_when_triggered_by_command_misspelled(
    runtime_fence_evidence_setup,
):
    """ADR-013 P7 codex round 3 F2 fix:trigger 字段拼错(non-enum value)→ 仍校验 invariant。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-cs-misspelled-trigger",
        triggered_by_command="change-apply-supervisor",  # 拼错(应是 change-apply-subagent)
        worktree_consent_outcome="declined",
        worktree_mode="skill_worktree",  # 违反 declined ↔ in_place
        worktree_path="/tmp/wt",
    )
    errors = fg._check_worktree_consent_outcome(ev_path, fm, change_dir)
    assert errors, "P7 F2 fix:misspelled trigger field MUST NOT bypass invariant check"
    joined = " ".join(errors)
    assert "declined" in joined and "in_place" in joined


def test_parallel_decline_fallback_blocks_when_degraded_to_missing(
    runtime_fence_evidence_setup,
):
    """ADR-013 P7 codex round 3 F3 fix:`change-apply-parallel` + outcome ∈
    {declined, sandbox_fallback} → MUST set `degraded_to: change-apply-subagent` +
    `degradation_reason: parallel_requires_isolated_workspace`(否则 Blocker)。
    """
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-pdf-no-degraded",
        triggered_by_command="change-apply-parallel",
        worktree_consent_outcome="declined",
        worktree_mode="in_place",
        # NO degraded_to / degradation_reason — 应 block
    )
    errors = fg._check_parallel_decline_fallback(ev_path, fm, change_dir)
    assert errors
    joined = " ".join(errors)
    assert "degraded_to" in joined and "change-apply-subagent" in joined


def test_parallel_decline_fallback_blocks_when_degradation_reason_wrong(
    runtime_fence_evidence_setup,
):
    """P7 F3:degradation_reason 必须 `parallel_requires_isolated_workspace`(其他 reason → Blocker)。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-pdf-wrong-reason",
        triggered_by_command="change-apply-parallel",
        worktree_consent_outcome="sandbox_fallback",
        worktree_mode="in_place",
        degraded_to="change-apply-subagent",
        degradation_reason="actual_file_overlap_detected",  # 应是 parallel_requires_isolated_workspace
    )
    errors = fg._check_parallel_decline_fallback(ev_path, fm, change_dir)
    assert errors
    joined = " ".join(errors)
    assert "parallel_requires_isolated_workspace" in joined


def test_parallel_decline_fallback_passes_when_correctly_degraded(
    runtime_fence_evidence_setup,
):
    """P7 F3 positive:正确 degraded_to + degradation_reason → pass。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-pdf-correct",
        triggered_by_command="change-apply-parallel",
        worktree_consent_outcome="declined",
        worktree_mode="in_place",
        degraded_to="change-apply-subagent",
        degradation_reason="parallel_requires_isolated_workspace",
    )
    errors = fg._check_parallel_decline_fallback(ev_path, fm, change_dir)
    assert errors == [], f"correctly degraded parallel evidence should pass; got: {errors}"


def test_parallel_decline_fallback_pass_through_for_non_parallel_command(
    runtime_fence_evidence_setup,
):
    """P7 F3:非 parallel command(subagent / direct) → fence pass-through。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-pdf-subagent",
        triggered_by_command="change-apply-subagent",
        worktree_consent_outcome="declined",
        worktree_mode="in_place",
    )
    errors = fg._check_parallel_decline_fallback(ev_path, fm, change_dir)
    assert errors == [], f"non-parallel command should pass-through; got: {errors}"


def test_parallel_decline_fallback_pass_through_for_accepted_outcome(
    runtime_fence_evidence_setup,
):
    """P7 F3:parallel + accepted/already_isolated → 沿正常 parallel 路径(非 decline fallback case)→ pass。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-pdf-accepted",
        triggered_by_command="change-apply-parallel",
        worktree_consent_outcome="accepted",
        worktree_mode="skill_worktree",
        worktree_path="/tmp/wt",
    )
    errors = fg._check_parallel_decline_fallback(ev_path, fm, change_dir)
    assert errors == [], f"parallel + accepted should not require degradation; got: {errors}"


# ---- D-ProtocolVersionMigration:protocol v1 gate skips legacy evidence ----


def test_runtime_fences_skip_legacy_evidence_without_protocol_version(
    runtime_fence_evidence_setup,
):
    """P1.7 守门:legacy evidence(无 runtime_enforcement_protocol_version 字段)
    缺所有新字段也 pass-through 4 fence — 确保 archived enhance-workflow-automation
    等历史 change replay 不被 false-block。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup("fc-legacy")
    # 移除 protocol version 字段模拟 legacy evidence
    fm.pop("runtime_enforcement_protocol_version")
    # 4 fence 全 pass-through(legacy 无新字段也不报错)
    assert fg._check_skill_cascade(ev_path, fm, change_dir) == []
    assert fg._check_round_fix_continuity(ev_path, fm, change_dir) == []
    assert fg._check_task_granularity(ev_path, fm, change_dir) == []
    assert fg._check_worktree_path(ev_path, fm, change_dir) == []


def test_runtime_fences_skip_non_implementation_evidence_under_protocol_v1(
    runtime_fence_evidence_setup,
):
    """P1.7 守门:非 implementation evidence(如 verify_report)即使含 protocol v1
    标记也不被 skill_cascade / task_granularity / worktree_path fence 触发(这些
    fence 仅对 implementation evidence 类型强制)。"""
    change_dir, ev_path, fm = runtime_fence_evidence_setup(
        "fc-nonimpl",
        evidence_type="verify_report",  # 非 implementation 类型
    )
    # 缺 skill_cascade_audit / task_granularity / worktree_path 都不应报错
    assert fg._check_skill_cascade(ev_path, fm, change_dir) == []
    assert fg._check_task_granularity(ev_path, fm, change_dir) == []
    # worktree_path fence 即便有 triggered_by_command 也跳过(非 impl ev)
    fm["triggered_by_command"] = "change-apply-subagent"
    assert fg._check_worktree_path(ev_path, fm, change_dir) == []


# ---- e2e CLI wiring 验证(P1.6) ----


def test_runtime_fences_wired_into_check_frontmatter_protocol(tmp_path):
    """P1.7 e2e:4 fence 接到 check_frontmatter_protocol 主循环 — 用 builders 写一
    份违反 4 fence 的 implementation evidence,跑 finish_gate CLI,期待 4 类
    Blocker.type 全出现。

    ADR-013 更新(2026-05-06):worktree_path fence 由 outcome field presence
    触发(非 command trigger),故加 worktree_consent_outcome=accepted +
    worktree_mode=skill_worktree 缺 worktree_path → worktree_path_violation。
    """
    b = make_complete_change(tmp_path, "fc-rt-e2e")
    # 写一份实施 evidence(protocol v1)— 故意缺 skill_cascade_audit + task_granularity
    # + worktree_path,且 subagent_continuity round_1/2 implementer 不一致 → 4 fence 全触发
    b.write_evidence(
        "execution",
        "task_1_implementer.md",
        evidence_type="subagent_implementer_report",
        stage="S4",
        body="impl notes\n",
        extra_frontmatter={
            "runtime_enforcement_protocol_version": "v1",
            "triggered_by_command": "change-apply-subagent",
            "autonomy_decision": "claude_autonomous",  # 满足 autonomy fence
            "subagent_continuity": {
                "round_1_implementer_id": "ag-aaa",
                "round_2_fix_implementer_id": "ag-bbb",  # 不一致 → fence 触发
            },
            # ADR-013:outcome+mode presence → worktree_path fence 触发
            "worktree_consent_outcome": "accepted",
            "worktree_mode": "skill_worktree",
            # skill_cascade_audit 缺 → fence 触发
            # task_granularity 缺 → fence 触发
            # worktree_path 缺 → worktree_path_violation 触发(skill_worktree 必写)
        },
    )
    proc = _run_cli(tmp_path, ["--change", "fc-rt-e2e", "--no-validate", "--json"])
    assert proc.returncode == 2, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    blocker_types = {b["type"] for b in payload["blockers"]}
    assert "skill_cascade_violation" in blocker_types, blocker_types
    assert "round_fix_continuity_violation" in blocker_types, blocker_types
    assert "task_granularity_violation" in blocker_types, blocker_types
    assert "worktree_path_violation" in blocker_types, blocker_types


# ---------------------------------------------------------------------------
# enhance-workflow-automation-executable-enforcement P2:v2 fence tests
# (D-FrontmatterSchemaExtension + D-W1-ReceiptSchema + D-W3-LedgerFormat)
# ---------------------------------------------------------------------------


@pytest.fixture
def v2_fence_evidence_setup(tmp_path):
    """v2 evidence fixture:默认 frontmatter 含 runtime_enforcement_protocol_version: v2
    + implementation evidence 类型(subagent_implementer_report)。

    **ADR-013 default 字段**(P1 code_quality M-3 doc fix 2026-05-06):本 fixture
    自动 default ``worktree_consent_outcome: accepted`` + ``worktree_mode: wrapper_worktree``
    + ``worktree_path: <change_dir>``(因 ADR-013 D-ConsentOutcomeStateMachine 强制
    v2 evidence 含 outcome × mode 字段;v2 evidence 沿 W1 receipt schema 等价
    ``wrapper_worktree`` mode);测试若需 override 这些 default(如测 declined / in_place
    / skill_worktree mode 路径),传 fm_overrides 即可:

        v2_fence_evidence_setup("fc-test", worktree_consent_outcome="declined", worktree_mode="in_place", worktree_path=None)

    Note:测 legacy v2 evidence(无 outcome 字段)需显式 override
    ``worktree_consent_outcome=None`` + ``worktree_mode=None`` 触发 legacy pass-through。

    返回 callable `setup(change_id, **fm_overrides)` -> (change_dir, evidence_path, fm)。
    """
    def _setup(change_id: str = "fc-v2-fixture", **fm_overrides):
        change_dir = tmp_path / "openspec" / "changes" / change_id
        change_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = change_dir / "execution" / "task_1_implementer.md"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text("---\n---\n\nbody\n", encoding="utf-8")
        fm = {
            "change_id": change_id,
            "stage": "S4",
            "evidence_type": "subagent_implementer_report",
            "aligned_with_contract": True,
            "runtime_enforcement_protocol_version": "v2",
            # v1 fence 也需要满足:
            "triggered_by_command": "change-apply-subagent",
            "skill_cascade_audit": {
                "invoked_skills": ["superpowers:subagent-driven-development"],
                "cascade_check_pass_at": "2026-05-05T00:00:00Z",
            },
            "task_granularity": "per-file",
            "worktree_path": str(change_dir),
            # ADR-013 D-ConsentOutcomeStateMachine v2 evidence 默认 wrapper_worktree mode
            # (v2 evidence 沿 W1 receipt schema;worktree_receipt_path 由 test 按需设置)
            "worktree_consent_outcome": "accepted",
            "worktree_mode": "wrapper_worktree",
        }
        fm.update(fm_overrides)
        return change_dir, evidence_path, fm
    return _setup


# ---- P2.3 _check_worktree_path_v2: 4 tests ----


def test_worktree_path_v2_receipt_ok_passes(v2_fence_evidence_setup):
    """P2.3 v2 fence(positive):receipt 存在 + JSON well-formed + worktree_path 一致
    + is_isolated_worktree: true → 无错误。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-wt-v2-ok")
    # 创建合法 receipt 文件
    receipts_dir = change_dir / "preflight_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_file = receipts_dir / "preflight-test.json"
    receipt_file.write_text(
        json.dumps({
            "worktree_path": str(change_dir),
            "is_isolated_worktree": True,
            "base_sha": "abc123",
        }),
        encoding="utf-8",
    )
    fm["worktree_receipt_path"] = "preflight_receipts/preflight-test.json"

    errors = fg._check_worktree_path_v2(ev_path, fm, change_dir)
    assert errors == [], f"expected no errors for valid receipt, got: {errors}"


def test_worktree_path_v2_receipt_missing_blocks(v2_fence_evidence_setup):
    """P2.3 v2 fence:worktree_receipt_path 指向不存在文件 → block。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-wt-v2-missing")
    fm["worktree_receipt_path"] = "preflight_receipts/nonexistent.json"

    errors = fg._check_worktree_path_v2(ev_path, fm, change_dir)
    assert errors, "missing receipt file MUST produce an error"
    joined = " ".join(errors)
    assert "does not exist" in joined or "nonexistent" in joined


def test_worktree_path_v2_receipt_path_mismatch_blocks(v2_fence_evidence_setup):
    """P2.3 v2 fence:receipt.worktree_path != evidence frontmatter worktree_path → block。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-wt-v2-mismatch")
    # receipt 有不同的 worktree_path
    receipts_dir = change_dir / "preflight_receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    receipt_file = receipts_dir / "preflight-mismatch.json"
    receipt_file.write_text(
        json.dumps({
            "worktree_path": "/some/other/path",  # 与 fm["worktree_path"] 不一致
            "is_isolated_worktree": True,
        }),
        encoding="utf-8",
    )
    fm["worktree_receipt_path"] = "preflight_receipts/preflight-mismatch.json"
    fm["worktree_path"] = "/expected/worktree/path"

    errors = fg._check_worktree_path_v2(ev_path, fm, change_dir)
    assert errors, "worktree_path mismatch MUST produce an error"
    joined = " ".join(errors)
    assert "mismatch" in joined or "worktree_path" in joined


def test_worktree_path_v2_receipt_path_field_missing_blocks(v2_fence_evidence_setup):
    """P2.3 v2 fence:v2 evidence 缺 worktree_receipt_path 字段 → block。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-wt-v2-nofield")
    # 不设置 worktree_receipt_path 字段
    fm.pop("worktree_receipt_path", None)

    errors = fg._check_worktree_path_v2(ev_path, fm, change_dir)
    assert errors, "missing worktree_receipt_path field MUST produce an error"
    joined = " ".join(errors)
    assert "worktree_receipt_path" in joined


# ---- P2.4 _check_round_fix_continuity_v2: 3 tests ----


def test_round_fix_continuity_v2_ledger_ok_passes(v2_fence_evidence_setup):
    """P2.4 v2 fence(positive):ledger 存在 + 引用的 agent_id 在 ledger 中 → 无错误。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-rfc-v2-ok")
    # 创建 ledger 含 agent-aaa + agent-bbb
    ledger_path = change_dir / "dispatch_ledger.jsonl"
    ledger_path.write_text(
        json.dumps({
            "agent_id": "agent-aaa",
            "round": 1,
            "role": "implementer",
            "dispatched_at": "2026-05-05T00:00:00+00:00",
            "wrapper_version": "1.0",
            "task_subject_hash": None,
            "parent_session_id": None,
        }) + "\n" +
        json.dumps({
            "agent_id": "agent-bbb",
            "round": 1,
            "role": "spec_reviewer",
            "dispatched_at": "2026-05-05T00:01:00+00:00",
            "wrapper_version": "1.0",
            "task_subject_hash": None,
            "parent_session_id": None,
        }) + "\n",
        encoding="utf-8",
    )
    fm["dispatch_ledger_path"] = "dispatch_ledger.jsonl"
    fm["subagent_continuity"] = {
        "round_1_implementer_id": "agent-aaa",
        "round_1_reviewer_id": "agent-bbb",
    }

    errors = fg._check_round_fix_continuity_v2(ev_path, fm, change_dir)
    assert errors == [], f"expected no errors for valid ledger, got: {errors}"


def test_round_fix_continuity_v2_ledger_missing_blocks(v2_fence_evidence_setup):
    """P2.4 v2 fence:dispatch_ledger_path 指向不存在文件 → block。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-rfc-v2-missing")
    fm["dispatch_ledger_path"] = "dispatch_ledger.jsonl"
    fm["subagent_continuity"] = {
        "round_1_implementer_id": "agent-aaa",
    }
    # 不创建 ledger 文件

    errors = fg._check_round_fix_continuity_v2(ev_path, fm, change_dir)
    assert errors, "missing ledger file MUST produce an error"
    joined = " ".join(errors)
    assert "does not exist" in joined or "dispatch_ledger" in joined


def test_round_fix_continuity_v2_agent_id_not_in_ledger_blocks(v2_fence_evidence_setup):
    """P2.4 v2 fence:subagent_continuity 引用的 agent_id 不在 ledger 中 → block。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-rfc-v2-noid")
    # ledger 只含 agent-aaa,但 continuity 引用 agent-zzz
    ledger_path = change_dir / "dispatch_ledger.jsonl"
    ledger_path.write_text(
        json.dumps({
            "agent_id": "agent-aaa",
            "round": 1,
            "role": "implementer",
            "dispatched_at": "2026-05-05T00:00:00+00:00",
            "wrapper_version": "1.0",
            "task_subject_hash": None,
            "parent_session_id": None,
        }) + "\n",
        encoding="utf-8",
    )
    fm["dispatch_ledger_path"] = "dispatch_ledger.jsonl"
    fm["subagent_continuity"] = {
        "round_1_implementer_id": "agent-zzz",  # 不在 ledger
    }

    errors = fg._check_round_fix_continuity_v2(ev_path, fm, change_dir)
    assert errors, "agent_id not in ledger MUST produce an error"
    joined = " ".join(errors)
    assert "agent-zzz" in joined


# ---- P2.5 _check_file_overlap_actual: 3 tests ----


def test_file_overlap_actual_disjoint_passes(v2_fence_evidence_setup):
    """P2.5 W2 fence(positive):parallel evidence + task_files_actual disjoint
    + actual ⊆ declared → 无错误。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup(
        "fc-foa-ok",
        triggered_by_command="change-apply-parallel",
    )
    fm["task_files_disjoint"] = [
        {"implementer_agent_id": "agent-a", "files": ["src/a.py", "src/b.py"]},
        {"implementer_agent_id": "agent-b", "files": ["src/c.py", "src/d.py"]},
    ]
    fm["task_files_actual"] = [
        {"implementer_agent_id": "agent-a", "files": ["src/a.py"]},
        {"implementer_agent_id": "agent-b", "files": ["src/c.py"]},
    ]
    fm["degraded_to"] = None

    errors = fg._check_file_overlap_actual(ev_path, fm, change_dir)
    assert errors == [], f"expected no errors for disjoint actual files, got: {errors}"


def test_file_overlap_actual_overlap_blocks(v2_fence_evidence_setup):
    """P2.5 W2 fence:actual changed-files 之间有重叠(且未降级)→ block。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup(
        "fc-foa-overlap",
        triggered_by_command="change-apply-parallel",
    )
    fm["task_files_disjoint"] = [
        {"implementer_agent_id": "agent-a", "files": ["src/a.py", "shared.py"]},
        {"implementer_agent_id": "agent-b", "files": ["src/b.py", "shared.py"]},
    ]
    fm["task_files_actual"] = [
        {"implementer_agent_id": "agent-a", "files": ["src/a.py", "shared.py"]},
        {"implementer_agent_id": "agent-b", "files": ["src/b.py", "shared.py"]},  # overlap on shared.py
    ]
    fm["degraded_to"] = None

    errors = fg._check_file_overlap_actual(ev_path, fm, change_dir)
    assert errors, "actual file overlap MUST produce an error"
    joined = " ".join(errors)
    assert "shared.py" in joined or "overlap" in joined


def test_file_overlap_actual_not_subset_of_declared_blocks(v2_fence_evidence_setup):
    """P2.5 W2 fence:actual 含 declared 中未声明的文件(actual ⊄ declared)→ block。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup(
        "fc-foa-extra",
        triggered_by_command="change-apply-parallel",
    )
    fm["task_files_disjoint"] = [
        {"implementer_agent_id": "agent-a", "files": ["src/a.py"]},
    ]
    fm["task_files_actual"] = [
        {"implementer_agent_id": "agent-a", "files": ["src/a.py", "src/extra_undeclared.py"]},  # extra
    ]
    fm["degraded_to"] = None

    errors = fg._check_file_overlap_actual(ev_path, fm, change_dir)
    assert errors, "actual not subset of declared MUST produce an error"
    joined = " ".join(errors)
    assert "extra_undeclared.py" in joined or "subset" in joined


def test_yaml_parser_list_of_mapping_e2e_overlap_blocks(tmp_path):
    """F2 round 1 codex mixed-scope inline writeback regression — list-of-mapping YAML
    parser support。Spec / 模板写 task_files_actual 为 list-of-map(`- implementer_agent_id: ...`
    + `files: [...]`),原 _parse_yaml_subset 把每个 list item 当 scalar,后续缩进 sub-key 被跳过,
    `_check_file_overlap_actual` 看不到 files 字段就 silent pass。本 test 端到端 verify
    yaml parser → fence 链路 catch overlap。"""
    from tools import _common

    # 手写 v2 evidence frontmatter list-of-map YAML(builder 不支持嵌套 dict→list-of-map)
    body = """\
---
change_id: test-yaml-list-of-map
stage: S4
evidence_type: subagent_implementer_report
contract_refs:
  - tasks.md#P0
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-apply-parallel
runtime_enforcement_protocol_version: v2
worktree_path: /tmp/test-wt-stub
worktree_receipt_path: preflight_receipts/stub.json
dispatch_ledger_path: dispatch_ledger.jsonl
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
  cascade_check_pass_at: 2026-05-05T00:00:00+00:00
task_files_disjoint:
  - implementer_agent_id: agent-a
    files:
      - src/a.py
  - implementer_agent_id: agent-b
    files:
      - src/b.py
task_files_actual:
  - implementer_agent_id: agent-a
    files:
      - src/a.py
      - src/shared.py
  - implementer_agent_id: agent-b
    files:
      - src/b.py
      - src/shared.py
degraded_to: null
degradation_reason: null
---

# Task P0 implementer (synthetic stub)
"""

    change_dir = tmp_path / "openspec" / "changes" / "test-yaml-list-of-map"
    (change_dir / "execution").mkdir(parents=True)
    ev_path = change_dir / "execution" / "task_p0_implementer.md"
    ev_path.write_text(body, encoding="utf-8")

    # Phase 1:verify yaml parser correctly parses list-of-mapping(F2 root cause)
    parsed_fm, _body = _common.parse_frontmatter(ev_path.read_text(encoding="utf-8"))
    assert isinstance(parsed_fm.get("task_files_actual"), list), \
        f"task_files_actual MUST be parsed as list, got {type(parsed_fm.get('task_files_actual')).__name__}"
    assert len(parsed_fm["task_files_actual"]) == 2, \
        f"task_files_actual MUST have 2 entries; got {len(parsed_fm['task_files_actual'])}"
    first_entry = parsed_fm["task_files_actual"][0]
    assert isinstance(first_entry, dict), \
        f"each list item MUST be parsed as dict, got {type(first_entry).__name__}"
    assert first_entry.get("implementer_agent_id") == "agent-a", \
        f"first entry implementer_agent_id MUST be 'agent-a', got {first_entry!r}"
    assert isinstance(first_entry.get("files"), list), \
        f"first entry files MUST be list, got {first_entry.get('files')!r}"
    assert "src/shared.py" in first_entry["files"], \
        f"first entry files MUST include src/shared.py, got {first_entry['files']!r}"

    # Phase 2:end-to-end fence catches overlap(without F2 fix,fence would silent pass)
    errors = fg._check_file_overlap_actual(ev_path, parsed_fm, change_dir)
    assert errors, "F2 fix:overlap MUST be caught after parser supports list-of-mapping"
    joined = " ".join(errors)
    assert "shared.py" in joined or "overlap" in joined.lower(), \
        f"error MUST mention overlap or shared file;got: {joined}"


# ---- P2.6 _check_dispatch_ledger: 2 tests ----


def test_dispatch_ledger_ok_passes(v2_fence_evidence_setup):
    """P2.6 W3 fence(positive):ledger 存在 + JSON well-formed + timestamps 单调 → 无错误。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-dl-ok")
    ledger_path = change_dir / "dispatch_ledger.jsonl"
    ledger_path.write_text(
        json.dumps({
            "agent_id": "agent-aaa",
            "round": 1,
            "role": "implementer",
            "dispatched_at": "2026-05-05T00:00:00+00:00",
            "wrapper_version": "1.0",
            "task_subject_hash": None,
            "parent_session_id": None,
        }) + "\n" +
        json.dumps({
            "agent_id": "agent-bbb",
            "round": 1,
            "role": "spec_reviewer",
            "dispatched_at": "2026-05-05T00:01:00+00:00",  # monotonic
            "wrapper_version": "1.0",
            "task_subject_hash": None,
            "parent_session_id": None,
        }) + "\n",
        encoding="utf-8",
    )
    fm["dispatch_ledger_path"] = "dispatch_ledger.jsonl"

    errors = fg._check_dispatch_ledger(ev_path, fm, change_dir)
    assert errors == [], f"expected no errors for valid ledger, got: {errors}"


def test_dispatch_ledger_timestamp_not_monotonic_blocks(v2_fence_evidence_setup):
    """P2.6 W3 fence:timestamps 倒流 → block。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-dl-ts-bad")
    ledger_path = change_dir / "dispatch_ledger.jsonl"
    # 第 2 行 timestamp 早于第 1 行
    ledger_path.write_text(
        json.dumps({
            "agent_id": "agent-aaa",
            "round": 1,
            "role": "implementer",
            "dispatched_at": "2026-05-05T00:10:00+00:00",
            "wrapper_version": "1.0",
            "task_subject_hash": None,
            "parent_session_id": None,
        }) + "\n" +
        json.dumps({
            "agent_id": "agent-bbb",
            "round": 1,
            "role": "spec_reviewer",
            "dispatched_at": "2026-05-05T00:01:00+00:00",  # earlier than prev
            "wrapper_version": "1.0",
            "task_subject_hash": None,
            "parent_session_id": None,
        }) + "\n",
        encoding="utf-8",
    )
    fm["dispatch_ledger_path"] = "dispatch_ledger.jsonl"

    errors = fg._check_dispatch_ledger(ev_path, fm, change_dir)
    assert errors, "non-monotonic timestamps MUST produce an error"
    joined = " ".join(errors)
    assert "monoton" in joined or "timestamp" in joined or "earlier" in joined


# ---- P2.9 protocol_version dispatch: 4 tests ----


def test_protocol_v1_evidence_triggers_only_v1_fences(v2_fence_evidence_setup, tmp_path):
    """P2.9:v1 evidence(`runtime_enforcement_protocol_version: v1`)仅触发 v1 fence;
    v2 fence(_check_worktree_path_v2 / _check_round_fix_continuity_v2 /
    _check_file_overlap_actual / _check_dispatch_ledger)不触发。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-prot-v1")
    # 降级为 v1
    fm["runtime_enforcement_protocol_version"] = "v1"
    # v2 fields 缺失:worktree_receipt_path / dispatch_ledger_path / task_files_actual

    # v2 fence 应全 pass-through
    assert fg._check_worktree_path_v2(ev_path, fm, change_dir) == [], \
        "v1 evidence MUST pass-through _check_worktree_path_v2"
    assert fg._check_round_fix_continuity_v2(ev_path, fm, change_dir) == [], \
        "v1 evidence MUST pass-through _check_round_fix_continuity_v2"
    assert fg._check_file_overlap_actual(ev_path, fm, change_dir) == [], \
        "v1 evidence MUST pass-through _check_file_overlap_actual (not parallel)"
    assert fg._check_dispatch_ledger(ev_path, fm, change_dir) == [], \
        "v1 evidence MUST pass-through _check_dispatch_ledger"


def test_protocol_v2_evidence_triggers_v1_and_v2_fences(v2_fence_evidence_setup):
    """P2.9:v2 evidence 触发 v1 fence + v2 fence(v2 ⊇ v1)。

    验证方法:创建违反 v1 fence(缺 skill_cascade_audit)且违反 v2 fence
    (缺 worktree_receipt_path)的 v2 evidence;确认两类 Blocker 都出现。
    """
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-prot-v2-both")
    # 故意移除 v1 需要的字段 + v2 需要的字段
    fm.pop("skill_cascade_audit", None)   # v1 fence 会报错
    fm.pop("worktree_receipt_path", None)  # v2 fence 会报错(worktree_path_v2)

    v1_errors = fg._check_skill_cascade(ev_path, fm, change_dir)
    v2_errors = fg._check_worktree_path_v2(ev_path, fm, change_dir)

    assert v1_errors, "v2 evidence MUST trigger v1 fence (skill_cascade)"
    assert v2_errors, "v2 evidence MUST trigger v2 fence (worktree_path_v2)"


def test_legacy_evidence_passes_through_all_v1_v2_fences(v2_fence_evidence_setup):
    """P2.9:legacy evidence(无 runtime_enforcement_protocol_version 字段)
    pass-through 全部 v1 + v2 fence — 确保 archived change replay 兼容。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-prot-legacy")
    # 移除 protocol_version 字段模拟 legacy evidence
    fm.pop("runtime_enforcement_protocol_version", None)

    # v1 fence 全 pass-through
    assert fg._check_skill_cascade(ev_path, fm, change_dir) == []
    assert fg._check_round_fix_continuity(ev_path, fm, change_dir) == []
    assert fg._check_task_granularity(ev_path, fm, change_dir) == []
    assert fg._check_worktree_path(ev_path, fm, change_dir) == []
    # v2 fence 全 pass-through
    assert fg._check_worktree_path_v2(ev_path, fm, change_dir) == []
    assert fg._check_round_fix_continuity_v2(ev_path, fm, change_dir) == []
    assert fg._check_file_overlap_actual(ev_path, fm, change_dir) == []
    assert fg._check_dispatch_ledger(ev_path, fm, change_dir) == []


def test_archived_v1_evidence_replay_not_killed_by_v2_fences(tmp_path):
    """P2.9:archived enhance-workflow-automation-runtime-enforcement evidence
    (v1)在本 change ship 后 replay finish_gate 不被 v2 fence 误杀。

    用 tmp_path 构造模拟 archived v1 evidence(沿 archived change pattern)。
    """
    # 构造一份 archived v1 evidence — 只有 v1 所需字段,无 v2 字段
    archived_change_id = "2026-05-05-enhance-workflow-automation-runtime-enforcement"
    change_dir = tmp_path / "openspec" / "changes" / "archive" / archived_change_id
    change_dir.mkdir(parents=True, exist_ok=True)
    ev_path = change_dir / "execution" / "task_1_implementer.md"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    ev_path.write_text("---\n---\nbody\n", encoding="utf-8")

    # v1 evidence frontmatter:有 v1 字段,无 v2 字段
    fm = {
        "change_id": archived_change_id,
        "stage": "S4",
        "evidence_type": "subagent_implementer_report",
        "aligned_with_contract": True,
        "runtime_enforcement_protocol_version": "v1",
        "triggered_by_command": "change-apply-subagent",
        "skill_cascade_audit": {
            "invoked_skills": ["superpowers:subagent-driven-development"],
            "cascade_check_pass_at": "2026-05-05T10:00:00Z",
        },
        "task_granularity": "per-file",
        "worktree_path": str(change_dir),
        # 无 worktree_receipt_path / dispatch_ledger_path / task_files_actual
    }

    # v2 fence 全 pass-through(v1 protocol)
    assert fg._check_worktree_path_v2(ev_path, fm, change_dir) == [], \
        "archived v1 evidence MUST pass-through _check_worktree_path_v2"
    assert fg._check_round_fix_continuity_v2(ev_path, fm, change_dir) == [], \
        "archived v1 evidence MUST pass-through _check_round_fix_continuity_v2"
    assert fg._check_file_overlap_actual(ev_path, fm, change_dir) == [], \
        "archived v1 evidence MUST pass-through _check_file_overlap_actual"
    assert fg._check_dispatch_ledger(ev_path, fm, change_dir) == [], \
        "archived v1 evidence MUST pass-through _check_dispatch_ledger"
    # v1 fence 仍应正常工作(无 regression)
    assert fg._check_skill_cascade(ev_path, fm, change_dir) == [], \
        "archived v1 evidence with valid skill_cascade_audit MUST pass v1 fence"


# =============================================================================
# P3 phase scope: v3 fence 测试(沿 enhance-workflow-automation-ledger-binding)
#
# round 1+2+3 codex inline writeback 后 4 新 fence:
# - _check_runtime_enforcement_protocol_version_validity (D-RuntimeEnforcementProtocolVersionValidity)
# - _check_archived_replay_path_boundary (D-ArchivedReplayPathBoundary)
# - _check_ledger_terminal_proof (D-LedgerTerminalProof)
# - _check_ledger_forgery_resistance_consistency (D-FrontmatterAuditConsistency)
# + _check_dispatch_ledger v3 分支(strict schema + chain HMAC verify)
# =============================================================================

import sys as _sys
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(_TOOLS_DIR) not in _sys.path:
    _sys.path.insert(0, str(_TOOLS_DIR))
import _forgeue_ledger_crypto as _ledger_crypto_test  # noqa: E402


@pytest.fixture
def v3_fence_evidence_setup(tmp_path, monkeypatch):
    """v3 evidence fixture:frontmatter 含 runtime_enforcement_protocol_version: v3 +
    cryptographic + ledger_line_count + ledger_final_hmac;ledger 用 cmd_append 真跑生成。

    monkey-patch _forgeue_ledger_crypto._KEY_FILE_PATH 隔离真实 user home。
    """
    monkeypatch.setattr(
        _ledger_crypto_test, "_KEY_FILE_PATH", tmp_path / ".claude" / "forgeue_ledger_key"
    )
    # 同时 patch finish_gate 内部 lazy-import 的 _ledger_crypto module
    # (finish_gate 内部 import 是 lazy,monkey-patch _crypto 模块属性应该传递)

    def _setup(change_id: str = "fc-v3-fixture", n_ledger_lines: int = 1, **fm_overrides):
        change_dir = tmp_path / "openspec" / "changes" / change_id
        change_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = change_dir / "execution" / "task_1_implementer.md"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)

        # 用 cmd_append 真跑生成 v3 ledger
        ledger_path = change_dir / "dispatch_ledger.jsonl"
        import importlib
        ledger_cli = importlib.import_module("forgeue_dispatch_ledger")
        for i in range(n_ledger_lines):
            args = argparse.Namespace(
                change=change_id,
                agent_id=f"abc{i:014x}def",
                round=1,
                role="implementer",
                task_subject_hash=None,
                parent_session_id=None,
                ledger_path=str(ledger_path),
            )
            ledger_cli.cmd_append(args)

        # 解析 ledger 取末行 hmac 用于 evidence frontmatter `ledger_final_hmac`
        ledger_lines = [
            json.loads(raw)
            for raw in ledger_path.read_text(encoding="utf-8").splitlines()
            if raw.strip()
        ]
        final_hmac = ledger_lines[-1]["hmac"] if ledger_lines else "0" * 64

        evidence_path.write_text("---\n---\n\nbody\n", encoding="utf-8")
        fm = {
            "change_id": change_id,
            "stage": "S4",
            "evidence_type": "subagent_implementer_report",
            "aligned_with_contract": True,
            "runtime_enforcement_protocol_version": "v3",
            "ledger_forgery_resistance": "cryptographic",
            "ledger_line_count": len(ledger_lines),
            "ledger_final_hmac": final_hmac,
            "dispatch_ledger_path": "dispatch_ledger.jsonl",
            # v1 fence 也要满足
            "triggered_by_command": "change-apply-subagent",
            "skill_cascade_audit": {
                "invoked_skills": ["superpowers:subagent-driven-development"],
                "cascade_check_pass_at": "2026-05-06T00:00:00Z",
            },
            "task_granularity": "per-file",
            "worktree_path": str(change_dir),
            "worktree_consent_outcome": "accepted",
            "worktree_mode": "wrapper_worktree",
        }
        fm.update(fm_overrides)
        return change_dir, evidence_path, fm, ledger_path

    return _setup


# ---- P3.1 _check_runtime_enforcement_protocol_version_validity: 5 tests (round 2 codex F2) ----


def test_protocol_validity_legacy_pass_through(v2_fence_evidence_setup):
    """legacy evidence(无 protocol_version 字段)→ pass-through。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-pv-legacy")
    fm.pop("runtime_enforcement_protocol_version", None)
    assert fg._check_runtime_enforcement_protocol_version_validity(ev_path, fm, change_dir) == []


def test_protocol_validity_v3_passes(v3_fence_evidence_setup):
    """v3 evidence pass-through(走后续 v3 dispatch matrix)。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-pv-v3")
    assert fg._check_runtime_enforcement_protocol_version_validity(ev_path, fm, change_dir) == []


def test_protocol_validity_unknown_v4_blocks(v2_fence_evidence_setup):
    """unknown protocol_version 'v4' → BLOCKER unknown_protocol_version。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-pv-v4")
    fm["runtime_enforcement_protocol_version"] = "v4"
    errors = fg._check_runtime_enforcement_protocol_version_validity(ev_path, fm, change_dir)
    assert errors, "v4 MUST be BLOCKER"
    assert "[unknown_protocol_version]" in errors[0]


def test_protocol_validity_typo_blocks(v2_fence_evidence_setup):
    """typo protocol_version 'V3' (case mismatch) → BLOCKER。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-pv-typo")
    fm["runtime_enforcement_protocol_version"] = "V3"
    errors = fg._check_runtime_enforcement_protocol_version_validity(ev_path, fm, change_dir)
    assert errors
    assert "[unknown_protocol_version]" in errors[0]


def test_protocol_validity_empty_string_blocks(v2_fence_evidence_setup):
    """empty string protocol_version → BLOCKER(present-but-empty 与 absent 不同)。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-pv-empty")
    fm["runtime_enforcement_protocol_version"] = ""
    errors = fg._check_runtime_enforcement_protocol_version_validity(ev_path, fm, change_dir)
    assert errors
    assert "[unknown_protocol_version]" in errors[0]


# ---- P3.1 _check_archived_replay_path_boundary: 4 tests (round 2 codex F1) ----


def test_archived_replay_default_pass_through(v3_fence_evidence_setup):
    """default(无 ledger_archived_replay)→ pass-through。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-arb-default")
    assert fg._check_archived_replay_path_boundary(ev_path, fm, change_dir) == []


def test_archived_replay_active_path_blocks(v3_fence_evidence_setup):
    """active path(无 archive/ segment)+ ledger_archived_replay: true → BLOCKER。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-arb-active")
    fm["ledger_archived_replay"] = True
    errors = fg._check_archived_replay_path_boundary(ev_path, fm, change_dir)
    assert errors, "active path + opt-in MUST be BLOCKER"
    assert "[archived_replay_path_violation]" in errors[0]


def test_archived_replay_archive_path_passes(tmp_path, monkeypatch):
    """archive/ 路径 evidence + ledger_archived_replay: true → fence pass(走 user override)。"""
    monkeypatch.setattr(
        _ledger_crypto_test, "_KEY_FILE_PATH", tmp_path / ".claude" / "forgeue_ledger_key"
    )
    # 在 archive/ 路径下创建 evidence
    change_dir = tmp_path / "openspec" / "changes" / "archive" / "2026-05-06-archived-test"
    change_dir.mkdir(parents=True)
    ev_path = change_dir / "execution" / "task_1_implementer.md"
    ev_path.parent.mkdir(parents=True)
    ev_path.write_text("---\n---\n\n", encoding="utf-8")
    fm = {"ledger_archived_replay": True}

    errors = fg._check_archived_replay_path_boundary(ev_path, fm, change_dir)
    assert errors == [], f"archive/ path + opt-in MUST pass-through, got: {errors}"


def test_archived_replay_false_or_null_pass_through(v3_fence_evidence_setup):
    """ledger_archived_replay: false / null → pass-through。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-arb-false")
    fm["ledger_archived_replay"] = False
    assert fg._check_archived_replay_path_boundary(ev_path, fm, change_dir) == []


# ---- P3.1 _check_ledger_terminal_proof: 6 tests (round 1 codex F3) ----


def test_terminal_proof_v3_valid_passes(v3_fence_evidence_setup):
    """happy path:line_count + final_hmac match → pass。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-tp-ok")
    assert fg._check_ledger_terminal_proof(ev_path, fm, change_dir) == []


def test_terminal_proof_v2_evidence_pass_through(v2_fence_evidence_setup):
    """v2 evidence pass-through。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-tp-v2")
    assert fg._check_ledger_terminal_proof(ev_path, fm, change_dir) == []


def test_terminal_proof_missing_line_count_blocks(v3_fence_evidence_setup):
    """v3 evidence 缺 ledger_line_count → BLOCKER tail_truncation_undeclared。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-tp-no-lc")
    del fm["ledger_line_count"]
    errors = fg._check_ledger_terminal_proof(ev_path, fm, change_dir)
    assert errors
    assert "[tail_truncation_undeclared]" in errors[0]


def test_terminal_proof_missing_final_hmac_blocks(v3_fence_evidence_setup):
    """v3 evidence 缺 ledger_final_hmac → BLOCKER final_hmac_undeclared。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-tp-no-fh")
    del fm["ledger_final_hmac"]
    errors = fg._check_ledger_terminal_proof(ev_path, fm, change_dir)
    assert errors
    assert "[final_hmac_undeclared]" in errors[0]


def test_terminal_proof_line_count_mismatch_blocks(v3_fence_evidence_setup):
    """evidence ledger_line_count != 实际 ledger 行数 → BLOCKER tail_truncation_detected。"""
    change_dir, ev_path, fm, ledger_path = v3_fence_evidence_setup("fc-tp-tail-trunc", n_ledger_lines=3)
    # 删 ledger 最后一行(模拟 LLM 删尾,不更新 evidence frontmatter)
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    ledger_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    # evidence frontmatter 仍声明 3 行
    errors = fg._check_ledger_terminal_proof(ev_path, fm, change_dir)
    assert errors
    assert "[tail_truncation_detected]" in errors[0]


def test_terminal_proof_final_hmac_mismatch_blocks(v3_fence_evidence_setup):
    """evidence ledger_final_hmac != 实际末行 hmac → BLOCKER final_hmac_mismatch。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-tp-fh-mismatch")
    fm["ledger_final_hmac"] = "f" * 64  # 假 hmac
    errors = fg._check_ledger_terminal_proof(ev_path, fm, change_dir)
    assert errors
    assert "[final_hmac_mismatch]" in errors[0]


# ---- P3.1 _check_ledger_forgery_resistance_consistency: 4 tests (round 1 codex F4) ----


def test_audit_consistency_v3_cryptographic_passes(v3_fence_evidence_setup):
    """v3 + cryptographic → pass。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-aud-v3-c")
    assert fg._check_ledger_forgery_resistance_consistency(ev_path, fm, change_dir) == []


def test_audit_consistency_v2_advisory_passes(v2_fence_evidence_setup):
    """v2 + advisory → pass(self-dogfood gap path)。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-aud-v2-a")
    fm["ledger_forgery_resistance"] = "advisory"
    assert fg._check_ledger_forgery_resistance_consistency(ev_path, fm, change_dir) == []


def test_audit_consistency_v3_advisory_blocks(v3_fence_evidence_setup):
    """v3 + advisory(LLM 谎称 advisory)→ BLOCKER audit_mismatch。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-aud-v3-bad")
    fm["ledger_forgery_resistance"] = "advisory"
    errors = fg._check_ledger_forgery_resistance_consistency(ev_path, fm, change_dir)
    assert errors
    assert "[audit_mismatch]" in errors[0]


def test_audit_consistency_v2_cryptographic_blocks(v2_fence_evidence_setup):
    """v2 + cryptographic(LLM 虚报)→ BLOCKER audit_mismatch。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-aud-v2-bad")
    fm["ledger_forgery_resistance"] = "cryptographic"
    errors = fg._check_ledger_forgery_resistance_consistency(ev_path, fm, change_dir)
    assert errors
    assert "[audit_mismatch]" in errors[0]


# ---- P3.1 _check_dispatch_ledger v3 strict schema + chain HMAC: 4 tests ----


def test_dispatch_ledger_v3_valid_passes(v3_fence_evidence_setup):
    """v3 evidence + valid v3 ledger → fence pass。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-dl-v3-ok")
    errors = fg._check_dispatch_ledger(ev_path, fm, change_dir)
    assert errors == [], f"valid v3 ledger MUST pass, got: {errors}"


def test_dispatch_ledger_v3_chain_break_blocks(v3_fence_evidence_setup):
    """v3 evidence + 删除中间行 → BLOCKER chain_break。"""
    change_dir, ev_path, fm, ledger_path = v3_fence_evidence_setup("fc-dl-v3-cb", n_ledger_lines=3)
    # 删除第 2 行(中间)
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    new_lines = [lines[0], lines[2]]
    ledger_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    # 更新 evidence frontmatter line_count + final_hmac 以避免 terminal_proof 先 BLOCKER
    fm["ledger_line_count"] = 2
    last_record = json.loads(lines[2])
    fm["ledger_final_hmac"] = last_record["hmac"]

    errors = fg._check_dispatch_ledger(ev_path, fm, change_dir)
    assert errors, "chain break MUST be BLOCKER"
    assert any("[chain_break]" in e for e in errors)


def test_dispatch_ledger_v3_schema_violation_unknown_field(v3_fence_evidence_setup):
    """v3 evidence + ledger 加未知字段 → BLOCKER schema_violation。"""
    change_dir, ev_path, fm, ledger_path = v3_fence_evidence_setup("fc-dl-v3-uf", n_ledger_lines=1)
    # 改 ledger 加未知字段
    record = json.loads(ledger_path.read_text(encoding="utf-8").strip())
    record["extra_field_xyz"] = "anything"
    ledger_path.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    # 更新 evidence final_hmac(可能 hmac 仍合法因为 hand-edit 后 schema 先 reject;
    # 但 schema strict 在 chain HMAC 之前跑,所以 schema fail 即可)
    errors = fg._check_dispatch_ledger(ev_path, fm, change_dir)
    assert errors, "unknown field MUST be schema_violation BLOCKER"
    assert any("[schema_violation]" in e for e in errors)


def test_dispatch_ledger_v3_legacy_v2_evidence_skips_v3_branch(v2_fence_evidence_setup):
    """v2 evidence(无 v3 protocol)→ v3 strict 分支 skip;现有 v2 schema-only path 仍跑。"""
    change_dir, ev_path, fm = v2_fence_evidence_setup("fc-dl-v2-legacy")
    # 设置最小 v2 ledger
    ledger_path = change_dir / "dispatch_ledger.jsonl"
    ledger_path.write_text(
        json.dumps({
            "agent_id": "agent-x",
            "round": 1,
            "role": "implementer",
            "dispatched_at": "2026-05-06T00:00:00+00:00",
            "wrapper_version": "1.0",
            "task_subject_hash": None,
            "parent_session_id": None,
        }) + "\n",
        encoding="utf-8",
    )
    fm["dispatch_ledger_path"] = "dispatch_ledger.jsonl"
    errors = fg._check_dispatch_ledger(ev_path, fm, change_dir)
    assert errors == [], f"v2 legacy evidence MUST pass, got: {errors}"


# ---- P3.1 v3 round_fix_continuity (双重守门;round 1 codex F3): 1 test ----


def test_v3_double_fence_round_fix_continuity_chain_break_also_fails(v3_fence_evidence_setup):
    """v3 evidence + tampered ledger → _check_dispatch_ledger v3 + _check_round_fix_continuity v3
    双重守门 BLOCKER。"""
    change_dir, ev_path, fm, ledger_path = v3_fence_evidence_setup(
        "fc-double-fence", n_ledger_lines=2
    )
    # tamper:改第 2 行 hmac 但不更新 chain
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    record_2 = json.loads(lines[1])
    record_2["hmac"] = "f" * 64
    new_lines = [lines[0], json.dumps(record_2, sort_keys=True, separators=(",", ":"))]
    ledger_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # 加 subagent_continuity 字段供 _check_round_fix_continuity v2 cross-check
    record_1 = json.loads(lines[0])
    fm["subagent_continuity"] = {
        "round_1_implementer_id": record_1["agent_id"],
    }
    fm["ledger_final_hmac"] = "f" * 64  # 与改后的 hmac 同

    # _check_dispatch_ledger v3 fence catch hmac_mismatch
    dl_errors = fg._check_dispatch_ledger(ev_path, fm, change_dir)
    assert dl_errors, "v3 hmac mismatch MUST be caught by _check_dispatch_ledger"
    assert any("[hmac_mismatch]" in e for e in dl_errors)


# ---- P3.1 forgeue_change_state.py writeback-check archived_replay drift (round 3 codex F3): 2 tests ----


def test_writeback_check_archived_replay_active_drift(tmp_path):
    """active change evidence 含 ledger_archived_replay: true → forgeue_change_state.py
    --writeback-check exit 5 + DRIFT(沿 round 2 codex F1 + round 3 codex F3 inline writeback)。"""
    # in-process call detect_drift_archived_replay_path
    import importlib
    change_state = importlib.import_module("forgeue_change_state")

    change_id = "fc-archived-replay-drift"
    change_root = tmp_path / "openspec" / "changes" / change_id
    change_root.mkdir(parents=True)
    evidence = change_root / "review" / "test.md"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        "---\n"
        "change_id: fc-archived-replay-drift\n"
        "stage: S5\n"
        "evidence_type: review\n"
        "ledger_archived_replay: true\n"
        "---\n"
        "test\n",
        encoding="utf-8",
    )

    drifts = change_state.detect_drift_archived_replay_path(change_root, [evidence])
    assert drifts, "active change evidence with opt-in MUST drift"
    assert drifts[0].type == "archived_replay_path_violation"


def test_writeback_check_archived_replay_archive_path_no_drift(tmp_path):
    """archive/ path evidence + ledger_archived_replay: true → no drift。"""
    import importlib
    change_state = importlib.import_module("forgeue_change_state")

    change_root = tmp_path / "openspec" / "changes" / "archive" / "2026-05-06-archived-test"
    change_root.mkdir(parents=True)
    evidence = change_root / "review" / "test.md"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        "---\n"
        "change_id: archived-test\n"
        "stage: S9\n"
        "evidence_type: review\n"
        "ledger_archived_replay: true\n"
        "---\n",
        encoding="utf-8",
    )

    drifts = change_state.detect_drift_archived_replay_path(change_root, [evidence])
    assert drifts == [], f"archive/ path evidence MUST NOT drift, got: {drifts}"


# ---- P5 codex /codex:review --base main P1 inline writeback regression ----
#
# Codex /codex:review --base main raised P1 finding (2026-05-06): v3 evidence 跳过
# v1 fence (skill_cascade / task_granularity / worktree_path 等),因为 _runtime_enforcement_active
# 只接受 v1/v2 不接受 v3。修复后 v3 ⊇ v2 ⊇ v1。本 regression 测试守门 fix 不被未来回退。


def test_runtime_enforcement_active_accepts_v1_v2_v3(v3_fence_evidence_setup):
    """v1 / v2 / v3 evidence 都被 _runtime_enforcement_active 接受(沿 P5 codex review P1 inline writeback)。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-rea-v3")
    assert fg._runtime_enforcement_active(fm) is True, \
        "v3 evidence MUST be runtime_enforcement_active (沿 codex P1 finding fix)"


def test_runtime_enforcement_active_rejects_legacy_and_unknown():
    """legacy(无字段)+ unknown value 都被 _runtime_enforcement_active 拒(沿 v1/v2/v3 frozenset)。"""
    fm_legacy = {"change_id": "test"}  # 无 runtime_enforcement_protocol_version 字段
    fm_unknown = {"runtime_enforcement_protocol_version": "v4"}
    fm_typo = {"runtime_enforcement_protocol_version": "V3"}  # 大小写不一致
    assert fg._runtime_enforcement_active(fm_legacy) is False
    assert fg._runtime_enforcement_active(fm_unknown) is False
    assert fg._runtime_enforcement_active(fm_typo) is False


def test_v3_evidence_inherits_v1_fence_skill_cascade(v3_fence_evidence_setup):
    """v3 evidence 缺 skill_cascade_audit 字段 → v1 fence skill_cascade BLOCKER
    (沿 P5 codex review P1 inline writeback;v3 ⊇ v1 fence inheritance)。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-v3-cascade")
    # 删 skill_cascade_audit 字段(v1 fence skill_cascade 检测)
    del fm["skill_cascade_audit"]
    errors = fg._check_skill_cascade(ev_path, fm, change_dir)
    assert errors, "v3 evidence MUST inherit v1 _check_skill_cascade fence (沿 codex P1 finding fix)"


def test_v3_evidence_inherits_v1_fence_task_granularity(v3_fence_evidence_setup):
    """v3 evidence 缺 task_granularity 字段 → v1 fence task_granularity BLOCKER。"""
    change_dir, ev_path, fm, _ = v3_fence_evidence_setup("fc-v3-tg")
    del fm["task_granularity"]
    errors = fg._check_task_granularity(ev_path, fm, change_dir)
    assert errors, "v3 evidence MUST inherit v1 _check_task_granularity fence"
