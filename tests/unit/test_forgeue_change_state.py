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


# ---------------------------------------------------------------------------
# P7 review fixup F-E: S5 inference must use real-failure helper
# ---------------------------------------------------------------------------


def test_S5_inferred_when_verify_report_has_only_zero_fail_count_summary(tmp_path):
    """P7 F-E: S5 inference must use the real-failure helper, not naive
    ``[FAIL]`` substring matching. The autogenerated ``- [FAIL]: 0``
    summary line must NOT prevent S5 inference; otherwise every PASS
    verify_report stalls state at S4 and the state machine silently
    skips S5 (verified live during P7: state reached S7 via
    superpowers_review + doc_sync_report while S5 was never inferred).
    """
    b = make_complete_change(tmp_path, "fc-fe-s5", with_codex=False, with_cross_check=False)
    # Replace verify_report body with the autogenerated PASS shape
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
                "- [OK] **L0 pytest** (exit=0, 40.0s)",
                "  - pytest summary: 1126 passed in 32.0s",
                "- [OK] **L0 offline-bundle-smoke** (exit=0, 0.5s)",
                "",
                "## Summary",
                "",
                "- total steps: 2",
                "- [OK]: 2",
                "- [FAIL]: 0",
                "- [SKIP]: 0",
                "",
            ]
        ),
    )
    # Remove evidence beyond S5 so we observe S5 cleanly (not S6/S7)
    for sub, fn in [
        ("review", "superpowers_review.md"),
        ("verification", "doc_sync_report.md"),
        ("verification", "finish_gate_report.md"),
    ]:
        p = b.change_dir / sub / fn
        if p.exists():
            p.unlink()

    proc = _run_cli(tmp_path, ["--change", "fc-fe-s5", "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["state"] == "S5", (
        f"S5 should be inferred when verify_report only contains [FAIL]: 0 summary; "
        f"got state={data['state']!r}, reasons={data['state_reasons']!r}"
    )
    # Reason must reflect "no real [FAIL] step" wording, not naive substring match
    assert any(
        "no real [FAIL]" in r or "S5" in r for r in data["state_reasons"]
    )


def test_S4_stays_when_verify_report_has_real_fail_step(tmp_path):
    """P7 F-E regression: a real per-step ``[FAIL]`` marker MUST keep state
    below S5 (the change has not actually verified).
    """
    b = make_complete_change(tmp_path, "fc-fe-s4", with_codex=False, with_cross_check=False)
    b.write_evidence(
        "verification",
        "verify_report.md",
        evidence_type="verify_report",
        stage="S5",
        aligned_with_contract=False,
        drift_decision="pending",
        drift_reason="step failed",
        body="\n".join(
            [
                "- [FAIL] **L0 pytest** (exit=1)",
                "  - reason: 5 tests failed",
                "## Summary",
                "- [FAIL]: 1",
            ]
        ),
    )
    for sub, fn in [
        ("review", "superpowers_review.md"),
        ("verification", "doc_sync_report.md"),
        ("verification", "finish_gate_report.md"),
    ]:
        p = b.change_dir / sub / fn
        if p.exists():
            p.unlink()

    proc = _run_cli(tmp_path, ["--change", "fc-fe-s4", "--json"])
    data = json.loads(proc.stdout) if proc.stdout else {"state": None}
    assert data.get("state") != "S5", (
        f"Real [FAIL] step must NOT infer S5; got state={data.get('state')!r}"
    )


# ---------------------------------------------------------------------------
# adopt-subagent-driven-development §5.6 (F3): subagent_* evidence types
# participate in DRIFT detection (contradicts contract / exposes gap)
# ---------------------------------------------------------------------------


def test_subagent_implementer_def_outside_design_triggers_drift_contra(tmp_path):
    """§5.6 case 1 (F3 fence): a ``subagent_implementer_report`` body that
    declares ``def``/``class`` identifiers absent from design.md fenced code
    MUST trip ``evidence_contradicts_contract`` DRIFT (exit 5). Mirrors
    legacy ``tdd_log`` behavior.
    """
    b = ChangeBuilder(repo=tmp_path, change_id="fc-sub-contra")
    b.write_proposal()
    # design.md only declares LegitFunc; the implementer body introduces
    # ``UnknownHelper`` which is NOT in the contract.
    b.write_design(
        with_reasoning_notes=True,
        python_idents=["LegitFunc"],
        backticked_idents=["LegitClass"],
        decision_ids=["D-Existing"],
    )
    b.write_tasks(anchors=["1.1"])
    b.write_evidence(
        "execution",
        "task_1_implementer.md",
        evidence_type="subagent_implementer_report",
        stage="S4",
        body=(
            "## Status: DONE\n\n"
            "Added a helper class.\n\n"
            "```python\n"
            "class UnknownHelper:\n"
            "    pass\n"
            "```\n"
        ),
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )
    report = fcs.build_report(
        repo=tmp_path, change_id="fc-sub-contra", writeback_check=True
    )
    assert report is not None
    contra = [d for d in report.drifts if d.type == fcs.DRIFT_CONTRA]
    assert contra, (
        f"subagent_implementer_report def outside design.md MUST trigger DRIFT_CONTRA; "
        f"got drifts: {[(d.type, d.ref) for d in report.drifts]}"
    )
    assert any(d.ref == "UnknownHelper" for d in contra)


def test_subagent_spec_review_failure_keyword_triggers_drift_gap(tmp_path):
    """§5.6 case 2 (F3 fence): a ``subagent_spec_review`` body that
    surfaces a ``_KNOWN_FAILURE_KEYWORDS`` token absent from design.md
    MUST trip ``evidence_exposes_contract_gap`` DRIFT (exit 5). Mirrors
    legacy ``debug_log`` behavior — covers the spec-review "missing
    requirement" / "extra feature" / "misunderstood" gap-keyword case.
    """
    b = ChangeBuilder(repo=tmp_path, change_id="fc-sub-gap")
    b.write_proposal()
    # design.md declares BudgetExceeded but NOT WorkerTimeout.
    b.write_design(
        with_reasoning_notes=True,
        failure_keywords=["BudgetExceeded"],
        decision_ids=["D-Existing"],
    )
    b.write_tasks(anchors=["1.1"])
    b.write_evidence(
        "execution",
        "task_1_spec_review.md",
        evidence_type="subagent_spec_review",
        stage="S4",
        body=(
            "## Status: missing requirement\n\n"
            "Spec review surfaced WorkerTimeout failure mode that is NOT "
            "documented in design.md — extra feature / misunderstood scope.\n"
        ),
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )
    report = fcs.build_report(
        repo=tmp_path, change_id="fc-sub-gap", writeback_check=True
    )
    assert report is not None
    gaps = [d for d in report.drifts if d.type == fcs.DRIFT_GAP]
    assert gaps, (
        f"subagent_spec_review with WorkerTimeout absent from design.md MUST trigger "
        f"DRIFT_GAP; got drifts: {[(d.type, d.ref) for d in report.drifts]}"
    )
    assert any(d.ref == "WorkerTimeout" for d in gaps)


def test_subagent_spec_review_reviewer_gap_keyword_triggers_drift_gap(tmp_path):
    """F8 fix from codex S6 round 2: reviewer gap keyword(`missing requirement` /
    `extra feature` / `misunderstood` / `Critical issue` / `Important issue`)
    必须触发 DRIFT_GAP,即使没有 framework runtime failure mode keyword。
    F8 修复前 ``_KNOWN_FAILURE_KEYWORDS`` 只含 runtime token,reviewer 只写
    "missing requirement: X" 不会 trip DRIFT。F8 修复后 keyword list 扩展,
    reviewer gap keyword 与 design.md 不含的 X cross-check 触发 DRIFT_GAP。
    """
    b = ChangeBuilder(repo=tmp_path, change_id="fc-sub-reviewer-gap")
    b.write_proposal()
    # design.md 不含任何 reviewer gap keyword
    b.write_design(
        with_reasoning_notes=True,
        failure_keywords=[],
        decision_ids=["D-Existing"],
    )
    b.write_tasks(anchors=["1.1"])
    # spec_review body 含 `missing requirement` keyword(F8 新加 keyword)
    # 但**没有** WorkerTimeout / BudgetExceeded 等 runtime keyword
    b.write_evidence(
        "execution",
        "task_1_spec_review.md",
        evidence_type="subagent_spec_review",
        stage="S4",
        body=(
            "## Status: ❌ Issues found\n\n"
            "Spec review found:\n"
            "- missing requirement: implementer 漏建造 X feature\n"
        ),
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )
    report = fcs.build_report(
        repo=tmp_path, change_id="fc-sub-reviewer-gap", writeback_check=True
    )
    assert report is not None
    # F8 修复:`missing requirement` keyword 与 design.md 不含 → DRIFT_GAP
    gaps = [d for d in report.drifts if d.type == fcs.DRIFT_GAP]
    assert gaps, (
        f"F8 fix: subagent_spec_review with reviewer gap keyword 'missing requirement' "
        f"absent from design.md MUST trigger DRIFT_GAP; got drifts: "
        f"{[(d.type, d.ref) for d in report.drifts]}"
    )
    # 验证触发的是 reviewer gap keyword(冒号限定,不是 runtime keyword)
    assert any(d.ref == "missing requirement:" for d in gaps), (
        f"F8 fix: DRIFT_GAP ref must be 'missing requirement:' (with colon, "
        f"reviewer finding form), got refs: {[d.ref for d in gaps]}"
    )


def test_subagent_code_quality_review_critical_failure_mode_triggers_drift_gap(tmp_path):
    """§5.6 case 3 (F3 fence): a ``subagent_code_quality_review`` body that
    flags a Critical issue referencing an undocumented failure mode MUST
    trip DRIFT_GAP (exit 5).
    """
    b = ChangeBuilder(repo=tmp_path, change_id="fc-sub-cq-gap")
    b.write_proposal()
    b.write_design(
        with_reasoning_notes=True,
        failure_keywords=["BudgetExceeded"],
        decision_ids=["D-Existing"],
    )
    b.write_tasks(anchors=["1.1"])
    b.write_evidence(
        "execution",
        "task_1_code_quality_review.md",
        evidence_type="subagent_code_quality_review",
        stage="S4",
        body=(
            "## Status: APPROVED_WITH_CONCERNS\n\n"
            "## Issues (Critical)\n\n"
            "- ProviderTimeout failure mode is observed in tests but design.md "
            "does not document it. Critical contract gap.\n"
        ),
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )
    report = fcs.build_report(
        repo=tmp_path, change_id="fc-sub-cq-gap", writeback_check=True
    )
    assert report is not None
    gaps = [d for d in report.drifts if d.type == fcs.DRIFT_GAP]
    assert gaps, (
        f"subagent_code_quality_review Critical issue referencing undocumented "
        f"failure mode MUST trigger DRIFT_GAP; got drifts: "
        f"{[(d.type, d.ref) for d in report.drifts]}"
    )
    assert any(d.ref == "ProviderTimeout" for d in gaps)


def test_subagent_final_review_def_outside_design_triggers_drift_contra(tmp_path):
    """§5.6 reinforcement: ``subagent_final_review`` shares the same allow-list
    as the per-task reviews; out-of-contract identifiers in fenced code
    blocks MUST trigger DRIFT_CONTRA exit 5.
    """
    b = ChangeBuilder(repo=tmp_path, change_id="fc-sub-final")
    b.write_proposal()
    b.write_design(
        with_reasoning_notes=True,
        python_idents=["LegitFunc"],
        backticked_idents=["LegitClass"],
        decision_ids=["D-Existing"],
    )
    b.write_tasks(anchors=["1.1"])
    b.write_evidence(
        "review",
        "subagent_final_review.md",
        evidence_type="subagent_final_review",
        stage="S6",
        body=(
            "## Status: APPROVED\n\n"
            "```python\n"
            "def stealth_helper():\n"
            "    return 1\n"
            "```\n"
        ),
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )
    report = fcs.build_report(
        repo=tmp_path, change_id="fc-sub-final", writeback_check=True
    )
    assert report is not None
    contra = [d for d in report.drifts if d.type == fcs.DRIFT_CONTRA]
    assert any(d.ref == "stealth_helper" for d in contra), (
        f"subagent_final_review def outside design.md MUST trigger DRIFT_CONTRA; "
        f"got drifts: {[(d.type, d.ref) for d in report.drifts]}"
    )


def test_subagent_drift_cli_exits_5(tmp_path):
    """§5.6 CLI integration: subagent_* DRIFT detection MUST surface as
    exit 5 from ``--writeback-check --json`` (sames as legacy DRIFT types).
    """
    b = ChangeBuilder(repo=tmp_path, change_id="fc-sub-cli")
    b.write_proposal()
    b.write_design(
        with_reasoning_notes=True,
        python_idents=["LegitFunc"],
        decision_ids=["D-Existing"],
    )
    b.write_tasks(anchors=["1.1"])
    b.write_evidence(
        "execution",
        "task_1_implementer.md",
        evidence_type="subagent_implementer_report",
        stage="S4",
        body=(
            "## Status: DONE\n\n"
            "```python\n"
            "class OffPiste:\n    pass\n"
            "```\n"
        ),
        extra_frontmatter={"triggered_by_command": "change-apply-subagent"},
    )
    proc = _run_cli(
        tmp_path, ["--change", "fc-sub-cli", "--writeback-check", "--json"]
    )
    assert proc.returncode == 5
    data = json.loads(proc.stdout)
    types = [d["type"] for d in data["drifts"]]
    assert fcs.DRIFT_CONTRA in types


# ---------------------------------------------------------------------------
# P3 Sub-task 1: list_followon_inherited
# ---------------------------------------------------------------------------


def test_list_followon_inherited_extracts_inherited_entries(tmp_path):
    """有 inherited 标记的条目被正确提取,cancelled 条目不混入。"""
    from tools.forgeue_change_state import list_followon_inherited

    change_dir = tmp_path / "change"
    change_dir.mkdir()
    (change_dir / "tasks.md").write_text(
        """# Tasks

## P12 (follow-on tracking)
- [x] P12.1 (follow-on tracking): **followon-a** (沿前一 change 继承) — desc
- [x] P12.2 (follow-on tracking): **followon-b** [cancelled-completed: abc1234] — desc
- [ ] P12.3 (follow-on tracking): **followon-c** (沿前一 change 继承) — desc unchecked but inherited
- [x] P12.4 (follow-on tracking): **followon-d** [cancelled-superseded by some-id] — desc
""",
        encoding="utf-8",
    )
    result = list_followon_inherited(change_dir)
    assert "followon-a" in result
    assert "followon-c" in result
    assert "followon-b" not in result  # cancelled-completed, 不是 inherited
    assert "followon-d" not in result  # cancelled-superseded, 不是 inherited


def test_list_followon_inherited_empty_when_no_inherited(tmp_path):
    """无 inherited 文字时返回空列表。"""
    from tools.forgeue_change_state import list_followon_inherited

    change_dir = tmp_path / "change"
    change_dir.mkdir()
    (change_dir / "tasks.md").write_text(
        """## P12 (follow-on tracking)
- [x] P12.1 (follow-on tracking): **only-cancelled** [cancelled-completed: abc] — desc
""",
        encoding="utf-8",
    )
    assert list_followon_inherited(change_dir) == []


def test_list_followon_inherited_no_tasks_md_returns_empty(tmp_path):
    """tasks.md 不存在时容错返回空列表。"""
    from tools.forgeue_change_state import list_followon_inherited

    change_dir = tmp_path / "change"
    change_dir.mkdir()
    assert list_followon_inherited(change_dir) == []


# ---------------------------------------------------------------------------
# P3 Sub-task 2: list_followon_cancelled
# ---------------------------------------------------------------------------


def test_list_followon_cancelled_categorizes_by_type(tmp_path):
    """3 类 cancelled tag 被正确分组,每条含 id + ref 字段。"""
    from tools.forgeue_change_state import list_followon_cancelled

    change_dir = tmp_path / "change"
    change_dir.mkdir()
    (change_dir / "tasks.md").write_text(
        """## P12 (follow-on tracking)
- [x] P12.1 (follow-on tracking): **followon-a** [cancelled-superseded by new-change] — desc
- [x] P12.2 (follow-on tracking): **followon-b** [cancelled-not-applicable: out-of-scope] — desc
- [x] P12.3 (follow-on tracking): **followon-c** [cancelled-completed: abc1234] — desc
- [x] P12.4 (follow-on tracking): **followon-d** [cancelled-completed: def5678 evidence: notes/foo.md] — desc
""",
        encoding="utf-8",
    )
    result = list_followon_cancelled(change_dir)
    # cancelled-superseded
    assert len(result["cancelled_superseded"]) == 1
    assert result["cancelled_superseded"][0]["id"] == "followon-a"
    # cancelled-not-applicable
    assert len(result["cancelled_not_applicable"]) == 1
    assert "out-of-scope" in result["cancelled_not_applicable"][0]["ref"]
    # cancelled-completed(含 2 条)
    assert len(result["cancelled_completed"]) == 2
    completed_ids = [e["id"] for e in result["cancelled_completed"]]
    assert "followon-c" in completed_ids
    assert "followon-d" in completed_ids


def test_list_followon_cancelled_empty_when_no_cancelled(tmp_path):
    """无 cancelled 条目时,3 个 key 均返回空列表。"""
    from tools.forgeue_change_state import list_followon_cancelled

    change_dir = tmp_path / "change"
    change_dir.mkdir()
    (change_dir / "tasks.md").write_text(
        "## P0 baseline\n- [x] 1.1 baseline\n",
        encoding="utf-8",
    )
    result = list_followon_cancelled(change_dir)
    assert all(v == [] for v in result.values())


def test_list_followon_cancelled_no_tasks_md_returns_empty_structure(tmp_path):
    """tasks.md 不存在时返回含 3 个空列表的 dict。"""
    from tools.forgeue_change_state import list_followon_cancelled

    change_dir = tmp_path / "change"
    change_dir.mkdir()
    result = list_followon_cancelled(change_dir)
    assert set(result.keys()) == {"cancelled_superseded", "cancelled_not_applicable", "cancelled_completed"}
    assert all(v == [] for v in result.values())
