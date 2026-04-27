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
