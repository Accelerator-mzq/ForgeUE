"""Unit tests for ``tools/forgeue_change_state.py``.

Covers tasks.md §5.2.2: state inference S1-S9 + 4 named DRIFT detectors +
helper-vs-formal evidence filtering + frontmatter health auxiliary checks
+ ``--validate-state`` + ``--list-active`` + structural inconsistency
exit 3 + JSON output shape + ASCII-only stdout.
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

import forgeue_change_state as fcs  # noqa: E402
from builders import (  # noqa: E402
    ChangeBuilder,
    make_complete_change,
    make_drift_change,
    make_minimal_change,
)

TOOL = _TOOLS / "forgeue_change_state.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli(
    repo: Path, args: list[str], extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# State inference S1-S9
# ---------------------------------------------------------------------------


def test_infer_state_S1_only_proposal(tmp_path):
    b = make_minimal_change(tmp_path, "fc-s1")
    state, reasons = fcs.infer_state(b.change_dir, archived=False)
    assert state == "S1"
    assert any("missing" in r for r in reasons)


def test_infer_state_S2_all_three_present(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-s2")
    b.write_proposal()
    b.write_design()
    b.write_tasks()
    state, _ = fcs.infer_state(b.change_dir, archived=False)
    assert state == "S2"


def test_infer_state_S3_with_execution_plan(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-s3")
    b.write_proposal()
    b.write_design()
    b.write_tasks()
    b.write_evidence(
        "execution",
        "execution_plan.md",
        evidence_type="execution_plan",
        stage="S3",
    )
    state, _ = fcs.infer_state(b.change_dir, archived=False)
    assert state == "S3"


def test_infer_state_S4_with_section_3_checkmarks(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-s4")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True)
    state, _ = fcs.infer_state(b.change_dir, archived=False)
    assert state == "S4"


def test_infer_state_S5_with_verify_report_no_fail(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-s5")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True)
    b.write_evidence(
        "verification",
        "verify_report.md",
        evidence_type="verify_report",
        stage="S5",
        body="all OK\n",
    )
    state, _ = fcs.infer_state(b.change_dir, archived=False)
    assert state == "S5"


def test_infer_state_remains_S4_if_verify_report_has_fail(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-s4-fail")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True)
    b.write_evidence(
        "verification",
        "verify_report.md",
        evidence_type="verify_report",
        stage="S5",
        body="[FAIL] some step\n",
    )
    state, _ = fcs.infer_state(b.change_dir, archived=False)
    assert state == "S4"


def test_infer_state_S6_with_finalize_marker(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-s6")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True)
    b.write_evidence(
        "verification",
        "verify_report.md",
        evidence_type="verify_report",
        stage="S5",
        body="ok\n",
    )
    b.write_evidence(
        "review",
        "superpowers_review.md",
        evidence_type="superpowers_review",
        stage="S6",
        body="## Final\nfinalize complete\n",
    )
    state, _ = fcs.infer_state(b.change_dir, archived=False)
    assert state == "S6"


def test_infer_state_S7_with_doc_sync_report(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-s7")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"], checkmarks_under_3=True)
    b.write_evidence(
        "verification",
        "verify_report.md",
        evidence_type="verify_report",
        stage="S5",
        body="ok\n",
    )
    b.write_evidence(
        "review",
        "superpowers_review.md",
        evidence_type="superpowers_review",
        stage="S6",
        body="## Final\n",
    )
    b.write_evidence(
        "verification",
        "doc_sync_report.md",
        evidence_type="doc_sync_report",
        stage="S7",
        body="DRIFT 0\n",
    )
    state, _ = fcs.infer_state(b.change_dir, archived=False)
    assert state == "S7"


def test_infer_state_S8_with_finish_gate_pass(tmp_path):
    make_complete_change(tmp_path, "fc-s8")
    state, _ = fcs.infer_state(tmp_path / "openspec" / "changes" / "fc-s8", archived=False)
    assert state == "S8"


def test_infer_state_S9_archived_short_circuit(tmp_path):
    # archived=True skips body inspection
    state, reasons = fcs.infer_state(tmp_path, archived=True)
    assert state == "S9"
    assert reasons == ["change is under openspec/changes/archive/"]


def test_infer_state_S0_when_nothing_present(tmp_path):
    cd = tmp_path / "openspec" / "changes" / "empty"
    cd.mkdir(parents=True)
    state, _ = fcs.infer_state(cd, archived=False)
    assert state == "S0"


# ---------------------------------------------------------------------------
# 4 named DRIFT detectors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "drift_type,expected_drift_type",
    [
        ("intro", fcs.DRIFT_INTRO),
        ("anchor", fcs.DRIFT_ANCHOR),
        ("contra", fcs.DRIFT_CONTRA),
        ("gap", fcs.DRIFT_GAP),
    ],
)
def test_named_drift_detected_via_build_report(tmp_path, drift_type, expected_drift_type):
    b = make_drift_change(tmp_path, drift_type, change_id=f"fd-{drift_type}")
    report = fcs.build_report(
        repo=tmp_path, change_id=b.change_id, writeback_check=True
    )
    assert report is not None
    types = [d.type for d in report.drifts]
    assert expected_drift_type in types


def test_complete_fixture_no_drift(tmp_path):
    b = make_complete_change(tmp_path, "fc-clean")
    report = fcs.build_report(
        repo=tmp_path, change_id=b.change_id, writeback_check=True
    )
    assert report is not None
    assert report.drifts == []
    assert report.frontmatter_issues == []


# DRIFT 1 narrowing: cross-check evidence intra-review D-XXX skipped.
def test_drift_intro_skips_cross_check_evidence(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-cc-skip")
    b.write_proposal()
    b.write_design(decision_ids=["D-Real"])
    b.write_tasks(anchors=["1.1"])
    b.write_evidence(
        "review",
        "design_cross_check.md",
        evidence_type="design_cross_check",
        stage="S2",
        body=(
            "## A. Decision Summary\n- D-Tracking1: cross-check id\n"
            "## B. Cross-check Matrix\n## C. Disputed\ndisputed_open: 0\n"
            "## D. Verification\n"
        ),
        extra_frontmatter={"disputed_open": 0},
    )
    report = fcs.build_report(
        repo=tmp_path, change_id=b.change_id, writeback_check=True
    )
    assert report is not None
    drift_intro_records = [d for d in report.drifts if d.type == fcs.DRIFT_INTRO]
    assert drift_intro_records == []


# DRIFT 2 narrowing: only execution_plan / micro_tasks evidence_type.
def test_drift_anchor_skips_codex_review_quoting_anchor(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-anchor-skip")
    b.write_proposal()
    b.write_design()
    b.write_tasks(anchors=["1.1"])
    # codex_design_review may quote tasks.md#99.1 as illustrative example
    b.write_evidence(
        "review",
        "codex_design_review.md",
        evidence_type="codex_design_review",
        stage="S2",
        body="## Finding\nrefers to tasks.md#99.1 as a placeholder example\n",
    )
    report = fcs.build_report(
        repo=tmp_path, change_id=b.change_id, writeback_check=True
    )
    assert report is not None
    anchor_drifts = [d for d in report.drifts if d.type == fcs.DRIFT_ANCHOR]
    assert anchor_drifts == []


# Helper-vs-formal evidence subdir filter.
def test_writeback_check_filters_helper_notes(tmp_path):
    b = ChangeBuilder(repo=tmp_path, change_id="fc-helper")
    b.write_proposal()
    b.write_design(decision_ids=["D-Real"])
    b.write_tasks(anchors=["1.1"])
    # notes/helper.md has D-MysteryDecision and tasks.md#99.1 but no
    # change_id+evidence_type => filtered out by _filter_formal_evidence
    b.write_helper_note(
        "helper.md",
        body="onboarding helper mentions D-MysteryDecision and tasks.md#99.1.\n",
    )
    report = fcs.build_report(
        repo=tmp_path, change_id=b.change_id, writeback_check=True
    )
    assert report is not None
    assert report.drifts == []


# ---------------------------------------------------------------------------
# Frontmatter health auxiliary checks (NOT exit 5; exposed for finish_gate)
# ---------------------------------------------------------------------------


def test_aligned_false_no_drift_recorded_in_fm_issues(tmp_path):
    b = make_drift_change(tmp_path, "frontmatter_aligned_false_no_drift", "fc-fm-1")
    report = fcs.build_report(
        repo=tmp_path, change_id=b.change_id, writeback_check=True
    )
    assert report is not None
    issues = [fi for fi in report.frontmatter_issues if fi.type == "aligned_false_no_drift"]
    assert issues, f"expected aligned_false_no_drift, got {report.frontmatter_issues}"
    # auxiliary checks do NOT trigger exit 5
    assert report.drifts == []


def test_writeback_commit_bogus_recorded(tmp_path):
    b = make_drift_change(tmp_path, "frontmatter_writeback_commit_bogus", "fc-fm-2")
    report = fcs.build_report(
        repo=tmp_path, change_id=b.change_id, writeback_check=True
    )
    assert report is not None
    issues = [
        fi for fi in report.frontmatter_issues
        if fi.type == "writeback_commit_not_found"
    ]
    assert issues


# ---------------------------------------------------------------------------
# CLI: --validate-state, --list-active, structural, exit codes
# ---------------------------------------------------------------------------


def test_cli_change_not_found_exits_1(tmp_path):
    proc = _run_cli(tmp_path, ["--change", "no-such-change"])
    assert proc.returncode == 1
    assert "not found" in proc.stderr


def test_cli_list_active_excludes_archive(tmp_path):
    # active change
    ChangeBuilder(repo=tmp_path, change_id="active-1").write_proposal()
    # archived change (in archive/)
    ChangeBuilder(repo=tmp_path, change_id="old", archived=True).write_proposal()
    proc = _run_cli(tmp_path, ["--list-active", "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "active-1" in data["active_changes"]
    assert not any("old" in c for c in data["active_changes"])


def test_cli_validate_state_pass(tmp_path):
    make_complete_change(tmp_path, "fc-cc-vs")
    proc = _run_cli(
        tmp_path, ["--change", "fc-cc-vs", "--validate-state", "S8", "--json"]
    )
    assert proc.returncode == 0


def test_cli_validate_state_mismatch_exits_2(tmp_path):
    make_minimal_change(tmp_path, "fc-min-vs")
    proc = _run_cli(
        tmp_path, ["--change", "fc-min-vs", "--validate-state", "S8", "--json"]
    )
    assert proc.returncode == 2


def test_cli_writeback_check_drift_exits_5(tmp_path):
    make_drift_change(tmp_path, "anchor", change_id="fc-d-anchor")
    proc = _run_cli(
        tmp_path, ["--change", "fc-d-anchor", "--writeback-check", "--json"]
    )
    assert proc.returncode == 5
    data = json.loads(proc.stdout)
    types = [d["type"] for d in data["drifts"]]
    assert fcs.DRIFT_ANCHOR in types


def test_cli_structural_inconsistency_exits_3(tmp_path):
    # Both active + archived directory present for the same id
    ChangeBuilder(repo=tmp_path, change_id="dup", archived=False).write_proposal()
    ChangeBuilder(repo=tmp_path, change_id="dup", archived=True).write_proposal()
    proc = _run_cli(tmp_path, ["--change", "dup", "--json"])
    assert proc.returncode == 3
    data = json.loads(proc.stdout)
    assert data["structural_issues"]


def test_cli_json_no_human_marker_prefix_lines(tmp_path):
    """In --json mode no line starts with an ASCII marker (markers belong
    to the human-readable code path). String values inside the JSON may
    contain ``[FAIL]`` as data (e.g. infer_state reasons mention it)."""
    make_complete_change(tmp_path, "fc-cc-json")
    proc = _run_cli(tmp_path, ["--change", "fc-cc-json", "--json"])
    assert proc.returncode == 0
    # Parses as JSON => no human-prefix banner ahead of the document.
    json.loads(proc.stdout)
    for line in proc.stdout.splitlines():
        stripped = line.lstrip()
        for marker in ("[OK]", "[FAIL]", "[SKIP]", "[WARN]", "[DRIFT]"):
            assert not stripped.startswith(marker), f"line begins with marker: {line!r}"


def test_cli_human_output_uses_ascii_markers(tmp_path):
    make_complete_change(tmp_path, "fc-cc-hum")
    proc = _run_cli(tmp_path, ["--change", "fc-cc-hum"])
    assert proc.returncode == 0
    assert "[OK]" in proc.stdout


def test_cli_stdout_pure_ascii(tmp_path):
    make_drift_change(tmp_path, "anchor", change_id="fc-asc")
    proc = _run_cli(tmp_path, ["--change", "fc-asc", "--writeback-check"])
    assert proc.returncode == 5
    raw = proc.stdout.encode("utf-8")
    non_ascii = [b for b in raw if b > 127]
    assert not non_ascii


def test_cli_dry_run_no_side_effects(tmp_path):
    make_complete_change(tmp_path, "fc-dry")
    cd = tmp_path / "openspec" / "changes" / "fc-dry"
    snapshot = sorted(p.name for p in cd.rglob("*") if p.is_file())
    proc = _run_cli(tmp_path, ["--change", "fc-dry", "--dry-run", "--json"])
    assert proc.returncode == 0
    after = sorted(p.name for p in cd.rglob("*") if p.is_file())
    assert snapshot == after


def test_cli_no_change_arg_errors_out(tmp_path):
    proc = _run_cli(tmp_path, [])
    assert proc.returncode == 1
    assert "--change" in proc.stderr


# ---------------------------------------------------------------------------
# JSON shape matches StateReport dataclass
# ---------------------------------------------------------------------------


def test_cli_json_shape_complete(tmp_path):
    make_complete_change(tmp_path, "fc-shape")
    proc = _run_cli(tmp_path, ["--change", "fc-shape", "--writeback-check", "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    expected_keys = {
        "change_id",
        "change_path",
        "archived",
        "state",
        "state_reasons",
        "drifts",
        "frontmatter_issues",
        "structural_issues",
    }
    assert expected_keys <= set(data)
    assert data["change_id"] == "fc-shape"
    assert data["state"] == "S8"
