"""Unit tests for ``tools/forgeue_verify.py``.

Covers tasks.md §5.2.3:
- Level 0 default runs (pytest + offline-bundle-smoke);
  Level 1 adds live-llm; Level 2 adds mesh / UE / comfy.
- ``FORGEUE_VERIFY_LIVE_*`` env guards are truthy
  (``{1, true, yes, on}`` case-insensitive); falsy values SKIP.
- ``--dry-run`` emits the plan without spawning subprocesses.
- ``--report-out`` writes a 12-key frontmatter markdown report.
- exit 2 on FAIL; exit 3 on change-not-found.
- ASCII-only stdout (em-dash banished post P3).
- pytest count is parsed from real output, never hardcoded.
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
import forgeue_verify as fv  # noqa: E402
from builders import make_complete_change, make_minimal_change  # noqa: E402

TOOL = _TOOLS / "forgeue_verify.py"


# ---------------------------------------------------------------------------
# Plan construction
# ---------------------------------------------------------------------------


def test_build_plan_level_0_has_pytest_and_offline_smoke():
    plan = fv.build_plan(0)
    names = [s.name for s in plan]
    assert "pytest" in names
    assert "offline-bundle-smoke" in names
    # Level 0 steps have no env_var guard
    for step in plan:
        if step.level == 0:
            assert step.env_var is None


def test_build_plan_level_1_adds_live_llm_only():
    plan = fv.build_plan(1)
    names = [s.name for s in plan]
    assert "live-llm-character-extract" in names
    # No mesh / UE / comfy at level 1
    assert "live-mesh-generation" not in names
    assert "live-ue-export" not in names
    assert "live-comfy-pipeline" not in names


def test_build_plan_level_2_adds_mesh_ue_comfy():
    plan = fv.build_plan(2)
    names = [s.name for s in plan]
    for live_step in (
        "live-llm-character-extract",
        "live-mesh-generation",
        "live-ue-export",
        "live-comfy-pipeline",
    ):
        assert live_step in names


def test_build_plan_level_0_steps_have_no_paid_env_guard():
    plan = fv.build_plan(0)
    for step in plan:
        if step.level == 0:
            assert step.env_var is None, f"L0 step {step.name!r} unexpectedly env-gated"


def test_build_plan_level_1_2_steps_have_env_guard():
    plan = fv.build_plan(2)
    for step in plan:
        if step.level >= 1:
            assert step.env_var is not None, f"L{step.level} step {step.name!r} not env-gated"
            assert step.env_var.startswith("FORGEUE_VERIFY_LIVE_")


# ---------------------------------------------------------------------------
# env_truthy guard ({1, true, yes, on} case-insensitive)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "True", "yes", "YES", "on", "ON", "On"])
def test_env_truthy_accepts_truthy_set(monkeypatch, val):
    monkeypatch.setenv("X_TRUTHY", val)
    assert _common.env_truthy("X_TRUTHY") is True


@pytest.mark.parametrize("val", ["0", "false", "FALSE", "no", "off", "", "2", "trueish"])
def test_env_truthy_rejects_outside_set(monkeypatch, val):
    monkeypatch.setenv("X_TRUTHY", val)
    assert _common.env_truthy("X_TRUTHY") is False


def test_env_truthy_unset_is_false(monkeypatch):
    monkeypatch.delenv("X_TRUTHY", raising=False)
    assert _common.env_truthy("X_TRUTHY") is False


# ---------------------------------------------------------------------------
# run_step: SKIP / OK / FAIL paths via stub commands
# ---------------------------------------------------------------------------


def test_run_step_skips_when_env_guard_not_truthy(monkeypatch, tmp_path):
    monkeypatch.delenv("FORGEUE_VERIFY_LIVE_MESH", raising=False)
    step = fv.StepPlan(
        name="stub",
        command=[sys.executable, "-c", "print('would-have-run')"],
        level=2,
        env_var="FORGEUE_VERIFY_LIVE_MESH",
    )
    result = fv.run_step(step, repo=tmp_path)
    assert result.status == "SKIP"
    assert result.exit_code is None
    assert "FORGEUE_VERIFY_LIVE_MESH" in result.reason
    assert "{1,true,yes,on}" in result.reason


def test_run_step_skips_when_env_guard_falsy(monkeypatch, tmp_path):
    monkeypatch.setenv("FORGEUE_VERIFY_LIVE_MESH", "0")
    step = fv.StepPlan(
        name="stub",
        command=[sys.executable, "-c", "print('still-skipped')"],
        level=2,
        env_var="FORGEUE_VERIFY_LIVE_MESH",
    )
    result = fv.run_step(step, repo=tmp_path)
    assert result.status == "SKIP"


def test_run_step_runs_when_env_guard_truthy(monkeypatch, tmp_path):
    monkeypatch.setenv("FORGEUE_VERIFY_LIVE_MESH", "1")
    step = fv.StepPlan(
        name="stub-ok",
        command=[sys.executable, "-c", "print('ok')"],
        level=2,
        env_var="FORGEUE_VERIFY_LIVE_MESH",
    )
    result = fv.run_step(step, repo=tmp_path)
    assert result.status == "OK"
    assert result.exit_code == 0


def test_run_step_fail_records_exit_code(monkeypatch, tmp_path):
    step = fv.StepPlan(
        name="stub-fail",
        command=[sys.executable, "-c", "import sys; sys.exit(7)"],
        level=0,
    )
    result = fv.run_step(step, repo=tmp_path)
    assert result.status == "FAIL"
    assert result.exit_code == 7


def test_run_step_command_not_found_records_FAIL(monkeypatch, tmp_path):
    step = fv.StepPlan(
        name="stub-missing",
        command=["definitely-not-a-real-binary-xyz123"],
        level=0,
    )
    result = fv.run_step(step, repo=tmp_path)
    assert result.status == "FAIL"
    assert result.exit_code is None


def test_run_step_pytest_summary_extracted(monkeypatch, tmp_path):
    step = fv.StepPlan(
        name="pytest",
        command=[sys.executable, "-c", "print('=== 42 passed in 0.10s ===')"],
        level=0,
    )
    result = fv.run_step(step, repo=tmp_path)
    assert result.status == "OK"
    assert result.pytest_summary is not None
    assert "42 passed" in result.pytest_summary


# ---------------------------------------------------------------------------
# pytest summary parser
# ---------------------------------------------------------------------------


def test_extract_pytest_summary_quiet_mode():
    # pytest -q can emit `1 passed in 0.05s` without === decoration
    assert fv._extract_pytest_summary("1 passed in 0.05s") == "1 passed in 0.05s"


def test_extract_pytest_summary_verbose_mode():
    assert (
        fv._extract_pytest_summary("=== 5 passed, 2 skipped in 0.5s ===")
        == "5 passed, 2 skipped in 0.5s"
    )


def test_extract_pytest_summary_with_failures():
    assert (
        fv._extract_pytest_summary("3 passed, 1 failed in 0.20s")
        == "3 passed, 1 failed in 0.20s"
    )


def test_extract_pytest_summary_returns_none_on_no_match():
    assert fv._extract_pytest_summary("no pytest output here\nrandom text") is None


def test_extract_pytest_summary_walks_from_bottom():
    # Should pick the LAST count-bearing line, not the first
    text = "warnings: 5\n=== 100 passed in 1.0s ==="
    summary = fv._extract_pytest_summary(text)
    assert summary is not None
    assert "100 passed" in summary


# ---------------------------------------------------------------------------
# render_report: 12-key frontmatter contract
# ---------------------------------------------------------------------------


def _make_results(*, fail: bool = False, skip: bool = False) -> list[fv.StepResult]:
    results = [
        fv.StepResult(
            name="pytest", level=0, status="OK", exit_code=0, duration_sec=1.0,
            pytest_summary="848 passed in 1.0s",
        ),
        fv.StepResult(
            name="offline-bundle-smoke", level=0, status="OK",
            exit_code=0, duration_sec=2.0,
        ),
    ]
    if fail:
        results[0] = fv.StepResult(
            name="pytest", level=0, status="FAIL", exit_code=1, duration_sec=1.0,
            pytest_summary="847 passed, 1 failed", reason="step failed",
        )
    if skip:
        results.append(
            fv.StepResult(
                name="live-mesh-generation", level=2, status="SKIP",
                exit_code=None, duration_sec=0.0,
                reason="opt-in env FORGEUE_VERIFY_LIVE_MESH not truthy",
            )
        )
    return results


def test_render_report_has_12_key_frontmatter():
    results = _make_results()
    text = fv.render_report(change_id="abc", level=0, results=results)
    # Find the frontmatter block
    assert text.startswith("---\n")
    fm_end = text.find("\n---\n", 4)
    fm_block = text[4:fm_end]
    for required_key in (
        "change_id",
        "stage",
        "evidence_type",
        "contract_refs",
        "aligned_with_contract",
        "drift_decision",
        "writeback_commit",
        "drift_reason",
        "reasoning_notes_anchor",
        "detected_env",
        "triggered_by",
        "codex_plugin_available",
    ):
        assert f"\n{required_key}:" in "\n" + fm_block, (
            f"missing frontmatter key {required_key!r}"
        )


def test_render_report_aligned_true_when_no_fail():
    results = _make_results()
    text = fv.render_report(change_id="abc", level=0, results=results)
    assert "aligned_with_contract: true" in text


def test_render_report_aligned_false_when_fail():
    results = _make_results(fail=True)
    text = fv.render_report(change_id="abc", level=0, results=results)
    assert "aligned_with_contract: false" in text


def test_render_report_evidence_type_is_verify_report():
    text = fv.render_report(change_id="abc", level=0, results=_make_results())
    assert "evidence_type: verify_report" in text


def test_render_report_stage_is_S5():
    text = fv.render_report(change_id="abc", level=0, results=_make_results())
    assert "stage: S5" in text


def test_render_report_no_hardcoded_pytest_count():
    """The report records the pytest summary from output, not hardcoded."""
    results = _make_results()
    text = fv.render_report(change_id="abc", level=0, results=results)
    # The pytest_summary in our fixture says "848 passed"; report quotes it
    assert "848 passed" in text
    # Render again with different count -> different number propagates
    results2 = [
        fv.StepResult(
            name="pytest", level=0, status="OK", exit_code=0, duration_sec=1.0,
            pytest_summary="999 passed in 2.0s",
        ),
        fv.StepResult(
            name="offline-bundle-smoke", level=0, status="OK",
            exit_code=0, duration_sec=2.0,
        ),
    ]
    text2 = fv.render_report(change_id="abc", level=0, results=results2)
    assert "999 passed" in text2
    assert "848 passed" not in text2


def test_render_report_summary_counts_match():
    results = _make_results(skip=True)
    text = fv.render_report(change_id="abc", level=2, results=results)
    assert "[OK]: 2" in text
    assert "[FAIL]: 0" in text
    assert "[SKIP]: 1" in text


# ---------------------------------------------------------------------------
# CLI: --dry-run, --json, exit codes, ASCII only
# ---------------------------------------------------------------------------


def _run_cli(
    repo: Path, args: list[str], extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ}
    # Strip any live-* guards from inherited env so dry-run never escalates.
    for var in (
        "FORGEUE_VERIFY_LIVE_LLM",
        "FORGEUE_VERIFY_LIVE_MESH",
        "FORGEUE_VERIFY_LIVE_UE",
        "FORGEUE_VERIFY_LIVE_COMFY",
    ):
        env.pop(var, None)
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
        timeout=60,
    )


def test_cli_change_not_found_exits_3(tmp_path):
    proc = _run_cli(tmp_path, ["--change", "no-such", "--level", "0"])
    assert proc.returncode == 3


def test_cli_dry_run_emits_plan_no_subprocess(tmp_path):
    make_complete_change(tmp_path, "fc-dry")
    proc = _run_cli(
        tmp_path, ["--change", "fc-dry", "--level", "0", "--dry-run", "--json"]
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["dry_run"] is True
    assert data["change_id"] == "fc-dry"
    assert data["level"] == 0
    names = [s["name"] for s in data["plan"]]
    assert "pytest" in names
    assert "offline-bundle-smoke" in names


def test_cli_dry_run_writes_no_report(tmp_path):
    make_complete_change(tmp_path, "fc-no-write")
    cd = tmp_path / "openspec" / "changes" / "fc-no-write"
    # remove existing verify_report so we can detect any creation
    (cd / "verification" / "verify_report.md").unlink()
    proc = _run_cli(
        tmp_path, ["--change", "fc-no-write", "--level", "0", "--dry-run"]
    )
    assert proc.returncode == 0
    assert not (cd / "verification" / "verify_report.md").exists()


def test_cli_dry_run_higher_level_includes_more_steps(tmp_path):
    make_minimal_change(tmp_path, "fc-lvl")
    # minimal change is fine for plan-only emission
    proc0 = _run_cli(
        tmp_path, ["--change", "fc-lvl", "--level", "0", "--dry-run", "--json"]
    )
    proc2 = _run_cli(
        tmp_path, ["--change", "fc-lvl", "--level", "2", "--dry-run", "--json"]
    )
    plan0 = json.loads(proc0.stdout)["plan"]
    plan2 = json.loads(proc2.stdout)["plan"]
    assert len(plan2) > len(plan0)


def test_cli_dry_run_human_output_ascii_only(tmp_path):
    make_minimal_change(tmp_path, "fc-asc")
    proc = _run_cli(tmp_path, ["--change", "fc-asc", "--level", "0", "--dry-run"])
    assert proc.returncode == 0
    raw = proc.stdout.encode("utf-8")
    non_ascii = [b for b in raw if b > 127]
    assert not non_ascii, f"non-ASCII bytes in stdout: {non_ascii[:20]!r}"


def test_cli_dry_run_uses_ascii_markers(tmp_path):
    make_minimal_change(tmp_path, "fc-mk")
    proc = _run_cli(tmp_path, ["--change", "fc-mk", "--level", "0", "--dry-run"])
    assert proc.returncode == 0
    assert "[OK]" in proc.stdout


def test_cli_argparse_rejects_invalid_level():
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--change", "x", "--level", "99"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert proc.returncode == 2


def test_cli_no_change_arg_argparse_exits_2():
    proc = subprocess.run(
        [sys.executable, str(TOOL), "--level", "0"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert proc.returncode == 2


def test_cli_missing_pytest_count_does_not_crash(monkeypatch, tmp_path):
    """Sanity: the SOURCE FILE must not reference any hardcoded pytest count
    like ``== 848`` / ``== 491``. The number always comes from real output.
    """
    src = (TOOL).read_text(encoding="utf-8")
    # No literal ``== 848`` style hardcoded pytest count comparisons in source.
    for forbidden in ("== 848", "== 491", "==848", "==491"):
        assert forbidden not in src, f"hardcoded count {forbidden!r} found in {TOOL}"
