"""Writeback detection fence (tasks.md §5.3.1).

This fence is the spec-level integration test mapping
``openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md``
ADDED Requirement Scenarios 1-3 + the 4 named DRIFT taxonomy from
``design.md`` §3 to actual tool exit codes:

- 4 named DRIFTs in ``forgeue_change_state --writeback-check`` ⇒ exit 5
- 5 frontmatter-health auxiliary cases in ``forgeue_finish_gate`` ⇒ exit 2

Each scenario uses ``builders.make_drift_change(...)`` so the fixture
shape is owned in one place; here we only assert tool behavior.
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

from builders import (  # noqa: E402
    ChangeBuilder,
    make_complete_change,
    make_drift_change,
)

CHANGE_STATE_TOOL = _TOOLS / "forgeue_change_state.py"
FINISH_GATE_TOOL = _TOOLS / "forgeue_finish_gate.py"


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


def _env_with_review(env_name: str) -> dict[str, str]:
    base = {**os.environ}
    for v in _AGENT_VARS:
        base.pop(v, None)
    base["FORGEUE_REVIEW_ENV"] = env_name
    return base


def _run(tool: Path, repo: Path, args: list[str], *, env_name: str = "cursor"):
    return subprocess.run(
        [sys.executable, str(tool), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env_with_review(env_name),
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Named DRIFT taxonomy (4 types) -> change_state exit 5
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "drift_type,expected_drift_type",
    [
        ("intro", "evidence_introduces_decision_not_in_contract"),
        ("anchor", "evidence_references_missing_anchor"),
        ("contra", "evidence_contradicts_contract"),
        ("gap", "evidence_exposes_contract_gap"),
    ],
)
def test_named_drift_taxonomy_exits_5_with_matching_type(
    tmp_path, drift_type, expected_drift_type
):
    b = make_drift_change(tmp_path, drift_type, change_id=f"fd-{drift_type}")
    proc = _run(
        CHANGE_STATE_TOOL,
        tmp_path,
        ["--change", f"fd-{drift_type}", "--writeback-check", "--json"],
    )
    assert proc.returncode == 5, (
        f"expected exit 5 for {drift_type}, got {proc.returncode}; stdout={proc.stdout!r}"
    )
    data = json.loads(proc.stdout)
    types = [d["type"] for d in data["drifts"]]
    assert expected_drift_type in types


def test_drift_anchor_exposes_file_and_ref_fields(tmp_path):
    """Spec scenario 1: anchor drift records ``file`` + ``ref`` for the
    operator to see exactly which evidence and which anchor are in
    conflict."""
    b = make_drift_change(tmp_path, "anchor", change_id="fd-anchor-fields")
    proc = _run(
        CHANGE_STATE_TOOL,
        tmp_path,
        ["--change", "fd-anchor-fields", "--writeback-check", "--json"],
    )
    assert proc.returncode == 5
    data = json.loads(proc.stdout)
    matching = [
        d for d in data["drifts"]
        if d["type"] == "evidence_references_missing_anchor"
    ]
    assert matching, "expected at least one evidence_references_missing_anchor"
    rec = matching[0]
    assert rec["file"] == "execution/execution_plan.md"
    assert rec["ref"] == "tasks.md#99.1"


def test_no_drift_on_complete_aligned_change(tmp_path):
    make_complete_change(tmp_path, "fd-clean")
    proc = _run(
        CHANGE_STATE_TOOL,
        tmp_path,
        ["--change", "fd-clean", "--writeback-check", "--json"],
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["drifts"] == []


# ---------------------------------------------------------------------------
# DRIFT scope narrowing (per design.md §3 heuristic notes)
# ---------------------------------------------------------------------------


def test_drift_intro_skips_cross_check_evidence(tmp_path):
    """Cross-check protocol bodies use D-XXX as intra-review tracking IDs;
    DRIFT 1 must NOT flag those (design.md §3 narrowing)."""
    b = ChangeBuilder(repo=tmp_path, change_id="fd-cc-skip")
    b.write_proposal()
    b.write_design(decision_ids=["D-Real"])
    b.write_tasks(anchors=["1.1"])
    b.write_evidence(
        "review",
        "design_cross_check.md",
        evidence_type="design_cross_check",
        stage="S2",
        body=(
            "## A. Decision Summary\n- D-TrackerX: cross-check tracker id\n"
            "## B. Cross-check Matrix\n## C. Disputed\ndisputed_open: 0\n"
            "## D. Verification\n"
        ),
        extra_frontmatter={"disputed_open": 0},
    )
    proc = _run(
        CHANGE_STATE_TOOL,
        tmp_path,
        ["--change", "fd-cc-skip", "--writeback-check", "--json"],
    )
    assert proc.returncode == 0


def test_drift_anchor_only_for_execution_plan_or_micro_tasks(tmp_path):
    """codex review evidence may quote ``tasks.md#99.1`` as illustrative
    example without dispatching workflow against it (design.md §3 narrowing)."""
    b = ChangeBuilder(repo=tmp_path, change_id="fd-anchor-skip")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"])
    b.write_evidence(
        "review",
        "codex_design_review.md",
        evidence_type="codex_design_review",
        stage="S2",
        body="quotes tasks.md#99.1 as a doc example, not a real reference\n",
    )
    proc = _run(
        CHANGE_STATE_TOOL,
        tmp_path,
        ["--change", "fd-anchor-skip", "--writeback-check", "--json"],
    )
    assert proc.returncode == 0


# ---------------------------------------------------------------------------
# Frontmatter health auxiliary cases -> finish_gate exit 2
# ---------------------------------------------------------------------------


def _seed_base_evidence(b: ChangeBuilder) -> None:
    """Add the 3 base evidence types so finish_gate's completeness check
    isn't the dominant failure mode in frontmatter-health scenarios."""
    b.write_evidence(
        "verification",
        "verify_report.md",
        evidence_type="verify_report",
        stage="S5",
        body="OK\n",
    )
    b.write_evidence(
        "verification",
        "doc_sync_report.md",
        evidence_type="doc_sync_report",
        stage="S7",
        body="OK\n",
    )
    b.write_evidence(
        "review",
        "superpowers_review.md",
        evidence_type="superpowers_review",
        stage="S6",
        body="## Final\n",
    )


@pytest.mark.parametrize(
    "drift_type,expected_blocker_type",
    [
        ("frontmatter_aligned_false_no_drift", "aligned_false_no_drift"),
        ("frontmatter_writeback_commit_bogus", "writeback_commit_not_found"),
        ("frontmatter_disputed_drift_short_reason", "disputed_drift_reason_too_short"),
        ("frontmatter_disputed_drift_no_anchor", "disputed_drift_anchor_missing"),
        (
            "frontmatter_disputed_drift_anchor_unresolved",
            "reasoning_notes_anchor_unresolved",
        ),
        (
            "frontmatter_disputed_drift_paragraph_too_short",
            "reasoning_notes_anchor_paragraph_too_short",
        ),
    ],
)
def test_frontmatter_health_blocks_finish_gate(
    tmp_path, drift_type, expected_blocker_type
):
    b = make_drift_change(tmp_path, drift_type, change_id=f"fd-fm-{drift_type}")
    _seed_base_evidence(b)
    proc = _run(
        FINISH_GATE_TOOL,
        tmp_path,
        ["--change", f"fd-fm-{drift_type}", "--no-validate", "--json"],
    )
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    types = [b["type"] for b in data["blockers"]]
    assert expected_blocker_type in types, (
        f"expected blocker {expected_blocker_type} for {drift_type}; got {types}"
    )


# ---------------------------------------------------------------------------
# Spec.md ADDED Requirement Scenario 2: aligned=false + drift_decision=null
# ---------------------------------------------------------------------------


def test_scenario_2_aligned_false_drift_decision_null(tmp_path):
    """Verbatim from spec.md ADDED Requirement Scenario 2."""
    b = make_complete_change(tmp_path, "fd-s2")
    # Inject the offending review evidence that scenario describes
    b.write_evidence(
        "review",
        "codex_design_review_extra.md",
        evidence_type="codex_design_review",
        stage="S2",
        aligned_with_contract=False,
        drift_decision=None,
        body="surfaced an undocumented decision not in design.md\n",
    )
    proc = _run(
        FINISH_GATE_TOOL,
        tmp_path,
        ["--change", "fd-s2", "--no-validate", "--json"],
    )
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    types = [b["type"] for b in data["blockers"]]
    assert "aligned_false_no_drift" in types


# ---------------------------------------------------------------------------
# Spec.md ADDED Requirement Scenario 3: disputed-permanent-drift requires
# real Reasoning Notes anchor
# ---------------------------------------------------------------------------


def test_scenario_3_disputed_drift_with_real_anchor_passes(tmp_path):
    """Anchor exists in design.md ## Reasoning Notes with substantive
    paragraph -> passes finish gate."""
    b = make_complete_change(tmp_path, "fd-s3-ok")
    b.write_design(
        with_reasoning_notes=True,
        reasoning_anchors=["reasoning-notes-commands-count"],
    )
    b.write_evidence(
        "review",
        "valid_disputed.md",
        evidence_type="codex_adversarial_review",
        stage="S6",
        aligned_with_contract=False,
        drift_decision="disputed-permanent-drift",
        drift_reason="x" * 60,
        reasoning_notes_anchor="reasoning-notes-commands-count",
        body="codex review.\n",
    )
    proc = _run(
        FINISH_GATE_TOOL,
        tmp_path,
        ["--change", "fd-s3-ok", "--no-validate", "--json"],
    )
    assert proc.returncode == 0


def test_scenario_3_disputed_drift_with_missing_section_blocks(tmp_path):
    """When design.md has NO ``## Reasoning Notes`` section at all, anchor
    cannot resolve."""
    b = make_complete_change(tmp_path, "fd-s3-no-section")
    # Override design without Reasoning Notes
    b.write_design(with_reasoning_notes=False)
    b.write_evidence(
        "review",
        "disp.md",
        evidence_type="codex_adversarial_review",
        stage="S6",
        aligned_with_contract=False,
        drift_decision="disputed-permanent-drift",
        drift_reason="x" * 60,
        reasoning_notes_anchor="reasoning-notes-commands-count",
        body="codex review.\n",
    )
    proc = _run(
        FINISH_GATE_TOOL,
        tmp_path,
        ["--change", "fd-s3-no-section", "--no-validate", "--json"],
    )
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    types = [b["type"] for b in data["blockers"]]
    # Either reasoning_notes_section_missing OR reasoning_notes_anchor_unresolved
    assert any(
        t in types
        for t in (
            "reasoning_notes_section_missing",
            "reasoning_notes_anchor_unresolved",
        )
    )


# ---------------------------------------------------------------------------
# JSON output shape sanity
# ---------------------------------------------------------------------------


def test_change_state_drift_json_includes_required_fields(tmp_path):
    b = make_drift_change(tmp_path, "intro", change_id="fd-shape")
    proc = _run(
        CHANGE_STATE_TOOL,
        tmp_path,
        ["--change", "fd-shape", "--writeback-check", "--json"],
    )
    assert proc.returncode == 5
    data = json.loads(proc.stdout)
    assert data["drifts"]
    rec = data["drifts"][0]
    assert {"type", "file", "detail"} <= set(rec)
